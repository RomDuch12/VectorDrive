"""Round 248 : cotes paramétrées (options de cotation de TypeEdit) —
alignée, horizontale, verticale, angulaire, radiale (Tab), symboles et
leur taille, ligne de cote intérieure / extérieure / absente, lignes
d'attache, texte (police, hauteur, écart, orientation, préfixe, suffixe,
unité, décimales) ; cote rouverte par double-clic, options de l'outil par
clic droit sur son bouton."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication, QDialog

app = QApplication.instance() or QApplication([])


class TestDims(unittest.TestCase):
    def test_values_and_labels(self):
        from vectordrive.core import dims as D
        self.assertEqual(D.Dim('libre', [(0, 0), (30, 40)], 5).label(), '50,00')
        self.assertEqual(D.Dim('horizontale', [(0, 0), (30, 40)], 5).label(), '30,00')
        self.assertEqual(D.Dim('verticale', [(0, 0), (30, 40)], 5).label(), '40,00')
        st = D.DimStyle(unit='cm', decimals=1, prefix='L=', suffix=' env.')
        self.assertEqual(D.Dim('libre', [(0, 0), (45, 0)], 5, st).label(), 'L=4,5 cm env.')
        self.assertEqual(D.Dim('libre', [(0, 0), (25.4, 0)], 5, D.DimStyle(unit='in', decimals=0)).label(), '1″')
        self.assertEqual(D.Dim('angulaire', [(10, 0), (0, 0), (0, 10)], 5, D.DimStyle(decimals=0)).label(), '90°')
        self.assertEqual(D.Dim('radiale', [(0, 0), (8, 0)], 5).label(), 'R8,00')
        self.assertEqual(D.Dim('radiale', [(0, 0), (8, 0)], 5, D.DimStyle(diameter=True)).label(), 'Ø16,00')

    def test_options_change_geometry(self):
        from vectordrive.core import dims as D
        base = D.Dim('libre', [(0, 0), (40, 0)], 10)
        lines, filled, _t = D.build(base)
        self.assertEqual(len(filled.contours), 2)                       # deux flèches pleines
        self.assertEqual(len(lines.contours), 3)                        # deux lignes d'attache, la ligne de cote
        ext = D.Dim('libre', [(0, 0), (40, 0)], 10, D.DimStyle(line='exterieure', start='oblique', end='ouverte',
                                                                ext_lines=False))
        lines, filled, _t = D.build(ext)
        self.assertEqual(len(filled.contours), 0)
        self.assertLess(lines.bbox()[0], -4.9)                           # lignes à l'extérieur (5 mm)
        cut = D.Dim('libre', [(0, 0), (40, 0)], 10, D.DimStyle(text_offset=0.0))
        self.assertEqual(len(D.build(cut)[0].contours), 4)               # ligne coupée par le texte
        none = D.Dim('libre', [(0, 0), (40, 0)], 10, D.DimStyle(line='aucune', ext_lines=False))
        self.assertTrue(D.build(none)[0].contours == [] and D.build(none)[1].contours == [])
        big = D.build(D.Dim('libre', [(0, 0), (40, 0)], 10, D.DimStyle(text_height=7.0)))[2].bbox()
        small = D.build(base)[2].bbox()
        self.assertGreater(big[3] - big[1], 1.8 * (small[3] - small[1]))
        ang = D.build(D.Dim('angulaire', [(10, 0), (0, 0), (0, 10)], 15))
        self.assertAlmostEqual(max(ang[0].bbox()[2:]), 16.5, 1)          # arc de rayon 15 + débord
        rad = D.build(D.Dim('radiale', [(0, 0), (8, 0)], 6))
        self.assertAlmostEqual(rad[0].bbox()[2], 14.0, 6)

    def test_group_follows_similarity(self):
        from vectordrive.core import dims as D, geom
        g = D.group(D.Dim('horizontale', [(0, 0), (30, 0)], 10))
        t = g.transformed(geom.Affine.translation(5, 5))
        self.assertEqual(D.dim_of(t).points[0], (5.0, 5.0))
        r = g.transformed(geom.Affine.rotation(30))
        self.assertEqual(D.dim_of(r).kind, 'libre')                     # tournée : plus horizontale
        self.assertIsNone(D.dim_of(g.transformed(geom.Affine.scaling(2, 1))))


class TestTool(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def _click(self, t, p):
        t.press(None, p, None)

    def test_linear_angular_radial(self):
        from vectordrive.core import dims as D, geom
        from vectordrive.core.document import Shape
        w = self.w
        w.set_tool('dim')
        t = w.canvas.tool_obj
        for p in ((0.0, 0.0), (30.0, 0.0), (15.0, 10.0)):
            self._click(t, p)
        g = w.canvas.selection[0]
        self.assertEqual((D.dim_of(g).kind, D.dim_of(g).offset), ('libre', 10.0))
        t.mode = 'angulaire'
        for p in ((10.0, 50.0), (0.0, 50.0), (0.0, 60.0), (12.0, 62.0)):
            self._click(t, p)
        a = D.dim_of(w.canvas.selection[0])
        self.assertEqual(a.kind, 'angulaire')
        self.assertAlmostEqual(a.value(), 90.0)
        circle = Shape(path=geom.Path([geom.circle((100.0, 100.0), 8.0)]))
        w.canvas.doc.layers[0].items.append(circle)
        t.mode = 'radiale'
        self._click(t, (108.0, 100.0))                                    # sur le cercle
        self._click(t, (120.0, 100.0))
        r = D.dim_of(w.canvas.selection[0])
        self.assertEqual(r.kind, 'radiale')
        self.assertAlmostEqual(r.value(), 8.0, 4)
        self.assertAlmostEqual(r.offset, 12.0, 4)

    def test_edit_and_defaults(self):
        from vectordrive.core import dims as D
        from vectordrive.ui import dim_dialog as DD
        w = self.w
        g = w.canvas.commit_dim(D.Dim('libre', [(0, 0), (40, 0)], 10))
        dlg = w.edit_dim(g, exec_dialog=False)
        dlg.set_field('unit', 'cm')                                     # aperçu en direct
        self.assertEqual(D.dim_of(g).style.unit, 'cm')
        dlg.reject()
        self.assertEqual(D.dim_of(g).style.unit, '')                     # annuler : comme avant
        dlg = w.edit_dim(g, exec_dialog=False)
        dlg.set_field('decimals', 0)
        dlg.set_field('offset', -8.0)
        dlg.accept()
        d = D.dim_of(g)
        self.assertEqual((d.style.decimals, d.offset), (0, -8.0))
        self.assertEqual(DD.default_style(w.settings).decimals, 0)       # devient le réglage de l'outil
        with mock.patch.object(w, 'edit_dim') as ed:
            w._item_double_clicked(g)
            ed.assert_called_once()
        w.canvas.select([])
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QContextMenuEvent
        from PySide6.QtWidgets import QToolButton
        btn = next((b for b in w.ribbon.findChildren(QToolButton) if b.defaultAction() is w.A['tool_dim']), None)
        if btn is not None:
            def fake_exec(d):
                d.set_field('start', 'point')
                return QDialog.DialogCode.Accepted
            def menu(*a, **k):                                           # le menu du bouton (round 1141) :
                self.assertIsNotNone(k.get('settings'))                  # ses réglages en tête
                k['settings']()
            with mock.patch.object(DD.DimDialog, 'exec', fake_exec), \
                    mock.patch.object(type(w), '_ribbon_button_menu', side_effect=menu):
                QApplication.sendEvent(btn, QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(2, 2),
                                                              btn.mapToGlobal(QPoint(2, 2))))
            self.assertEqual(DD.default_style(w.settings).start, 'point')
        w.settings.remove('cotes/style')


if __name__ == '__main__':
    unittest.main()
