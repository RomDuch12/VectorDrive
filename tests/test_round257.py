"""Round 257 : point du pavé numérique quand le champ lui-même a le focus
(Ctrl+flèche, F2…) ; Ctrl+flèche validé déplace ; « Traitement par lots… »
au clic droit de l'explorateur ; origine du dessin (repère, règles, F2,
coin des règles) ; paramètres exportés / importés (.vdparam)."""
import os
import pathlib
import tempfile
import unittest
import zipfile
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QLocale, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QSpinBox

from vectordrive.core import geom
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])
CTRL = Qt.KeyboardModifier.ControlModifier


class TestKeypadPoint(unittest.TestCase):
    def test_spinbox_with_focus(self):
        from vectordrive.ui.fields import install
        install(app)
        sb = QDoubleSpinBox()
        sb.setLocale(QLocale(QLocale.Language.French, QLocale.Country.France))
        sb.setDecimals(3)
        sb.setRange(0, 1000)
        sb.show()
        sb.lineEdit().selectAll()
        QTest.keyClicks(sb, '12')
        QTest.keyClick(sb, Qt.Key.Key_Period, Qt.KeyboardModifier.KeypadModifier)     # point du pavé
        QTest.keyClicks(sb, '5')
        self.assertEqual(sb.lineEdit().text(), '12,5')
        sb.interpretText()
        self.assertAlmostEqual(sb.value(), 12.5)
        n = QSpinBox()
        n.show()
        n.lineEdit().selectAll()
        QTest.keyClicks(n, '7')
        QTest.keyClick(n, Qt.Key.Key_Period, Qt.KeyboardModifier.KeypadModifier)
        self.assertEqual(n.lineEdit().text(), '7')                                    # entier : ignoré
        sb.close()
        n.close()


class Win(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.c = self.w.canvas
        self.rect = Shape(path=geom.Path([geom.rect(0, 0, 20, 8)]))
        self.c.doc.add(self.rect)
        self.c.select([self.rect])

    def tearDown(self):
        self.w.modified = False
        self.w.close()


class TestArrowMove(Win):
    def test_validated_step_moves(self):
        self.c.nudge_mm = 1.0
        self.assertTrue(self.w.arrow_step_move(-1, 0, 5.0))
        self.assertAlmostEqual(self.c.selection_bbox()[0], -5)
        self.assertTrue(self.w.arrow_step_move(0, 1, 2.5))
        self.assertAlmostEqual(self.c.selection_bbox()[1], 2.5)
        self.assertFalse(self.w.arrow_step_move(1, 0, 0.0))                          # 0 : ne bouge pas
        self.assertAlmostEqual(self.c.selection_bbox()[0], -5)


class TestOrigin(Win):
    def test_origin_offsets_display(self):
        c = self.c
        self.assertEqual(c.origin, (0.0, 0.0))
        self.assertTrue(self.w.A['origin_visible'].isChecked())                      # visible par défaut
        c.set_origin(10, 5)
        self.assertEqual(c.doc.extra['origine'], [10.0, 5.0])
        self.w._on_cursor(12.0, 5.0)
        self.assertIn('2.000', self.w.lbl_pos.text())
        self.w.dims.refresh()
        self.assertAlmostEqual(self.w.dims.fields['x'].value(), 0.0)                 # centre 10 - origine 10
        self.assertAlmostEqual(self.w.dims.fields['y'].value(), -1.0)
        self.assertIn('Cx 0.000 mm  Cy -1.000 mm', self.w.lbl_sel.text())         # centre depuis l'origine
        self.w.dims.fields['x'].setValue(20.0)
        self.w.dims.apply()
        self.assertAlmostEqual(c.selection_bbox()[0], 20.0)                          # 20 depuis l'origine
        self.assertFalse(self.w.grab().isNull())                                     # repère peint
        c.set_origin(0, 0)
        self.assertNotIn('origine', c.doc.extra)

    def test_presets_dialog_and_corner(self):
        from vectordrive.core.document import Plate
        c = self.c
        c.doc.plate = Plate(width=100, height=50)
        self.assertEqual(self.w.origin_to('plate_center'), (c.doc.plate.x + 50, c.doc.plate.y + 25))
        self.assertEqual(self.w.origin_to('selection_bl'), (0.0, 0.0))
        self.assertTrue(self.w.origin_dialog((3.0, 4.0)))
        self.assertEqual(c.origin, (3.0, 4.0))
        self.w.show()
        QApplication.processEvents()
        corner = self.w.ruler_corner
        gp = c.mapToGlobal(QPoint(c.width() // 2, c.height() // 2))
        self.assertTrue(corner.drop_at(gp))
        x, y = c.to_doc(c.mapFromGlobal(gp).toPointF())
        self.assertAlmostEqual(c.origin[0], x, 3)
        self.assertAlmostEqual(c.origin[1], y, 3)
        QTest.mouseDClick(corner, Qt.MouseButton.LeftButton)
        self.assertEqual(c.origin, (0.0, 0.0))                                       # double-clic : zéro
        self.w.A['origin_visible'].setChecked(False)
        self.assertFalse(c.show_origin)
        self.w.A['origin_visible'].setChecked(True)

    def test_saved_with_drawing(self):
        from vectordrive.io import registry
        self.c.set_origin(7.5, -2)
        f = pathlib.Path(tempfile.mkdtemp()) / 'o.vdz'
        registry.save_document(self.c.doc, f)
        self.assertEqual(registry.open_document(f).extra.get('origine'), [7.5, -2.0])


class TestBatchFromExplorer(unittest.TestCase):
    def test_plan_has_lots_entries(self):
        from vectordrive import shellmenu as SM
        keys = dict(SM.plan((r'C:\VD\VectorDrive.exe', [])))
        cmd = keys[r'Software\Classes\VectorDrive.Convertir.dxf\shell\90lots\command']['']
        self.assertEqual(cmd, r'"C:\VD\VectorDrive.exe" --lots "%1"')
        d = r'Software\Classes\Directory\shell\VectorDrive.Lots'
        self.assertEqual(keys[d]['MUIVerb'], SM.LOTS_DIR_TITLE)
        self.assertEqual(keys[d + r'\command'][''], cmd)
        reg = {}
        SM.install(lambda k, v: reg.setdefault(k, {}).update(v), (r'C:\VD\VectorDrive.exe', []))

        def delete(root):
            gone = [k for k in reg if k == root or k.startswith(root + '\\')]
            for k in gone:
                del reg[k]
            return bool(gone)
        SM.uninstall(delete)
        self.assertEqual(reg, {})                                                    # dossiers compris

    def test_lines_and_dialog(self):
        from vectordrive.ui import instance
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            d = tempfile.mkdtemp()
            a, b = os.path.join(d, 'a.dxf'), os.path.join(d, 'b.svg')

            class Sock:
                def __init__(self, data):
                    self.data, self.props = data, {}

                def readAll(self):
                    out, self.data = self.data, b''
                    return out

                def property(self, k):
                    return self.props.get(k)

                def setProperty(self, k, v):
                    self.props[k] = v

                def write(self, _b):
                    pass

                def flush(self):
                    pass
            opened = []
            w.open_path = opened.append
            instance._read(w, Sock((instance.LOTS + a + '\n' + instance.LOTS + b + '\n').encode('utf-8')))
            dlg = w._batch_dlg
            self.assertEqual([dlg.list.item(i).text() for i in range(dlg.list.count())], [a, b])
            self.assertEqual(opened, [])                                             # pas ouverts en onglets
            self.assertIs(w.batch_add([a]), dlg)                                     # même fenêtre, sans doublon
            self.assertEqual(dlg.list.count(), 2)
            dlg.close()
        finally:
            w.modified = False
            w.close()


class TestParams(unittest.TestCase):
    def env(self, root):
        root = pathlib.Path(root)
        return mock.patch.dict(os.environ, {
            'VECTORDRIVE_TOOLS': str(root / 'outils' / 'tools.json'),
            'VECTORDRIVE_CAM_TEMPLATES': str(root / 'modeles_fao'),
            'VECTORDRIVE_DOC_TEMPLATES': str(root / 'modeles_dessin'),
            'VECTORDRIVE_THEMES': str(root / 'themes')})

    def test_export_import_roundtrip(self):
        from PySide6.QtCore import QSettings
        from vectordrive.cam import toollib
        from vectordrive.cam.model import CamTool
        from vectordrive.io import params
        local = ('fichiers/recents',)
        src_root, dst_root = tempfile.mkdtemp(), tempfile.mkdtemp()
        st_a = QSettings(os.path.join(src_root, 'a.ini'), QSettings.Format.IniFormat)
        st_a.setValue('options/grille', 2.5)
        st_a.setValue('fichiers/recents', ['C:/x.vdz'])
        out = pathlib.Path(tempfile.mkdtemp()) / ('p' + params.EXT)
        with self.env(src_root):
            toollib.save([CamTool(name='Fraise 2', diameter=2.0), CamTool(name='Gravure 60', diameter=0.2)],
                         toollib.default_path())
            (pathlib.Path(src_root) / 'modeles_fao').mkdir()
            (pathlib.Path(src_root) / 'modeles_fao' / 'alu.json').write_text('{"name": "alu"}', encoding='utf-8')
            (pathlib.Path(src_root) / 'themes').mkdir()
            (pathlib.Path(src_root) / 'themes' / 'perso.json').write_text('{"v": 2}', encoding='utf-8')
            counts = params.export(out, st_a, local_keys=local)
        self.assertEqual(counts, {'reglages': 1, 'outils': 2, 'modeles_fao': 1, 'modeles_dessin': 0, 'themes': 1})
        names = zipfile.ZipFile(out).namelist()
        self.assertIn('modeles_fao/alu.json', names)
        self.assertEqual(params.contents(out), {'reglages': 1, 'outils': 2, 'modeles_fao': 1, 'themes': 1})
        st_b = QSettings(os.path.join(dst_root, 'b.ini'), QSettings.Format.IniFormat)
        st_b.setValue('options/grille', 9.0)
        backup = pathlib.Path(tempfile.mkdtemp()) / 'sauvegarde'
        with self.env(dst_root):
            toollib.save([CamTool(name='Fraise 2', diameter=2.0)], toollib.default_path())
            (pathlib.Path(dst_root) / 'themes').mkdir()
            (pathlib.Path(dst_root) / 'themes' / 'perso.json').write_text('{"v": 1}', encoding='utf-8')
            got, bk = params.import_(out, st_b, local_keys=local, backup_dir=backup)
            names = [t.name for t in toollib.library()]
        self.assertEqual(got['outils'], 1)                                           # sans doublon
        self.assertEqual(sorted(names), ['Fraise 2', 'Gravure 60'])
        self.assertEqual(float(st_b.value('options/grille')), 2.5)
        self.assertIsNone(st_b.value('fichiers/recents'))                            # propre au poste
        self.assertEqual((pathlib.Path(dst_root) / 'themes' / 'perso.json').read_text(encoding='utf-8'), '{"v": 2}')
        self.assertEqual(bk, backup)
        self.assertEqual((backup / 'themes' / 'perso.json').read_text(encoding='utf-8'), '{"v": 1}')
        self.assertEqual(float(QSettings(str(backup / 'reglages.ini'), QSettings.Format.IniFormat)
                               .value('options/grille')), 9.0)
        self.assertTrue((backup / 'outils' / 'tools.json').is_file())

    def test_old_ini_and_bad_file(self):
        from PySide6.QtCore import QSettings
        from vectordrive.io import params
        d = pathlib.Path(tempfile.mkdtemp())
        ini = QSettings(str(d / 'old.ini'), QSettings.Format.IniFormat)
        ini.setValue('vue/theme', 'ardoise')
        ini.sync()
        self.assertEqual(params.contents(d / 'old.ini'), {'reglages': 1})
        st = QSettings(str(d / 'st.ini'), QSettings.Format.IniFormat)
        got, _bk = params.import_(d / 'old.ini', st, backup_dir=d / 'bk')
        self.assertEqual(got, {'reglages': 1})
        self.assertEqual(st.value('vue/theme'), 'ardoise')
        (d / 'faux.vdparam').write_bytes(b'pas un zip')
        with self.assertRaises(ValueError):
            params.contents(d / 'faux.vdparam')
        with zipfile.ZipFile(d / 'evil.vdparam', 'w') as z:
            z.writestr('manifeste.json', '{"format": "vectordrive-parametres"}')
            z.writestr('themes/../../evil.json', 'x')
        with self.env(d / 'u'):
            got, _bk = params.import_(d / 'evil.vdparam', st, ['themes'], backup_dir=d / 'bk2')
        self.assertFalse((d / 'evil.json').exists())                                 # chemin refusé

    def test_window_import_applies(self):
        from vectordrive.io import params
        from vectordrive.ui import theme
        from vectordrive.ui.main_window import MainWindow
        before = theme.current()                     # l'import applique le thème relu (Crépuscule par défaut)
        w = MainWindow()
        root = tempfile.mkdtemp()
        try:
            out = pathlib.Path(root) / ('p' + params.EXT)
            with self.env(root):
                w.settings.setValue('options/grille', 2.5)
                w.export_params(str(out), ['reglages'])
                w.settings.setValue('options/grille', 9.0)
                counts, bk = w.import_params(str(out), backup_dir=pathlib.Path(root) / 'bk')
            self.assertGreater(counts['reglages'], 0)
            self.assertAlmostEqual(w.canvas.snap.grid_step, 2.5)                     # appliqué
            self.assertEqual(w.A['settings_export'].text(), 'Exporter les paramètres…')
        finally:
            w.settings.remove('options/grille')
            w.modified = False
            w.close()
            theme.apply(app, before)                 # pas de thème sombre laissé aux essais suivants


if __name__ == '__main__':
    unittest.main()
