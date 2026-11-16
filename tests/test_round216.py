"""Round 216 : FAO à la manière de TypeEdit — colonne de gauche des
parcours (Outils, usinage de la sélection par défaut, familles, modèles),
formulaire avec modèles (enregistrer, reprendre), Z de départ, pontets
espacés, calcul du seul parcours validé, liste à droite ou détachée,
modèles de parcours de TypeEdit (PathParam_*.TPP) importés."""
import os
import pathlib
import struct
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


# --- fichier TPP synthétique (même structure que TypeEdit, valeurs inventées) ---------------------
def lenstr(s: str) -> bytes:
    b = s.encode('latin-1')
    return bytes([len(b)]) + b


def tpp_preset(name: str, kind: str, group: str, sections: dict) -> bytes:
    out = lenstr(name) + struct.pack('<III', 7, len(name), 7) + lenstr(kind) + b'\x01\x01\x00\x00\x00'
    out += lenstr(group) + b'\x01' + struct.pack('<I', len(sections))
    for sec, kv in sections.items():
        out += lenstr(sec) + struct.pack('<I', len(kv))
        for k, v in kv.items():
            out += lenstr(k) + lenstr(v)
    return out + b'\0' * 24


def tpp_folder(name: str, n: int) -> bytes:
    return b'\xff' * 8 + struct.pack('<I', n) + lenstr(name) + struct.pack('<IIII', 0, 1, 7, 7) + b'\xff' * 4


def tpp_bytes() -> bytes:
    cut = {'PARAMPCR': {'MODE': 'CREATION'},
           'PROFONDEUR': {'NBSLICES': '4', 'PROFPASSE': '1.e-003', 'ZBOTTOM': '4.e-003', 'ZUP': '2.e-004'},
           'SPECIALDECOUPE': {'AllowanceEdit': '3.e-004', 'DecInternal': '2', 'climbMilling': '0', 'AddLinks': '1',
                              'HeightOfBridge': '1.e-003', 'LengthOfBridge': '5.e-003',
                              'DistanceUnderBridge': '3.e-002'},
           'Properties': {'iEnable': '1'}}
    hole = {'PARAMPCR': {'MODE': 'CREATION'},
            'PROFONDEUR': {'NBSLICES': '1', 'ZBOTTOM': '6.e-003', 'ZUP': '0.'},
            'SPECIALDECOUPE': {'DecInternal': '1', 'climbMilling': '1', 'AddLinks': '0'}}
    sweep = {'PARAMPCR': {'MODE': 'CREATION'}, 'PROFONDEUR': {'NBSLICES': '1', 'ZBOTTOM': '1.e-004'}}
    art = {'PARAMPCR': {'MODE': 'CREATION'}}
    return (struct.pack('<IIII', 0xCF0B, 2, 1, 1) + tpp_folder('Atelier', 2)
            + tpp_preset('Découpe Ø3 Pz4/4p a0.3 ponts', 'CP_Cutting_3D', 'TEMP', cut)
            + tpp_preset('Trou Pz6', 'CP_Cutting_3D', 'TEMP', hole)
            + tpp_folder('Gravure', 2)
            + tpp_preset('Balayage 0.1', 'CP_Sweeping', 'PRISME', sweep)
            + tpp_preset('Art', 'CP_TypeArt', 'TEMP', art))


class TestTpp(unittest.TestCase):
    def test_parse_and_templates(self):
        from vectordrive.cam import tpp
        ps = tpp.parse(tpp_bytes())
        self.assertEqual([(p.folder, p.name, p.kind) for p in ps],
                         [('Atelier', 'Découpe Ø3 Pz4/4p a0.3 ponts', 'CP_Cutting_3D'),
                          ('Atelier', 'Trou Pz6', 'CP_Cutting_3D'),
                          ('Gravure', 'Balayage 0.1', 'CP_Sweeping'), ('Gravure', 'Art', 'CP_TypeArt')])
        t = tpp.to_template(ps[0])
        o = t['operations'][0]
        self.assertEqual((t['preset'], t['dossier'], t['name']), ('decoupe', 'Atelier',
                                                                  'Atelier / Découpe Ø3 Pz4/4p a0.3 ponts'))
        self.assertEqual((o['kind'], o['depth'], o['step_down'], o['z_start'], o['stock']),
                         ('contour', 4.0, 1.0, 0.2, 0.3))
        self.assertEqual((o['side'], o['climb'], o['tab_gap'], o['tab_height'], o['tab_width'], o['tabs']),
                         ('exterieur', False, 30.0, 1.0, 5.0, 0))
        self.assertTrue(o['ramp'])
        self.assertEqual(t['tools'], [])                                       # l'outil se choisit au formulaire
        o2 = tpp.to_template(ps[1])['operations'][0]
        self.assertEqual((o2['side'], o2['depth'], o2['tabs'], o2['tab_gap']), ('interieur', 6.0, 0, 0.0))
        self.assertEqual(tpp.to_template(ps[2])['preset'], 'gravure')
        self.assertEqual(tpp.to_template(ps[3])['operations'][0]['kind'], 'relief')   # TypeArt : Relief (281)
        self.assertEqual(tpp.parse(b'\0' * 100), [])


class TestStrategies(unittest.TestCase):
    def setUp(self):
        from vectordrive.cam import model
        from vectordrive.core import geom
        from vectordrive.core.document import Document, Shape
        self.d = Document()
        self.d.plate = None
        self.d.add(Shape(path=geom.Path([geom.rect(0, 0, 100, 50)]), tool=0))
        self.s = model.CamSetup()
        self.t = model.CamTool(name='F2', kind='fraise', diameter=2.0, step_down=1.0, cut_length=10)
        self.s.tools = [self.t]

    def test_z_start_shifts_everything(self):
        from vectordrive.cam import model, strategies as S
        op = model.Operation(kind='contour', tool_id=self.t.id, depth=2.0, step_down=1.0, safe_z=3.0)
        flat = S.compute(self.d, self.s, op)
        op.z_start = 0.5
        up = S.compute(self.d, self.s, op)
        self.assertEqual(len(flat.moves), len(up.moves))
        self.assertTrue(all(abs(b.z - a.z - 0.5) < 1e-9 for a, b in zip(flat.moves, up.moves)))
        self.assertAlmostEqual(min(m.z for m in up.moves), -1.5)

    def test_tab_spacing(self):
        from vectordrive.cam import model, strategies as S
        op = model.Operation(kind='contour', tool_id=self.t.id, depth=2.0, step_down=2.0, side='exterieur',
                             tab_spacing=60.0, tab_height=0.5, tab_width=4.0)
        self.assertTrue(S.has_tabs(op))
        tp = S.compute(self.d, self.s, op)
        self.assertTrue(any(abs(m.z + 1.5) < 1e-9 for m in tp.moves))         # l'outil remonte sur les pontets
        by_count = model.Operation.from_dict({**op.to_dict(), 'tab_spacing': 0.0, 'tabs': 5})
        same = S.compute(self.d, self.s, by_count)                             # 306 mm de contour / 60 : 5 pontets
        self.assertEqual([(m.x, m.y, m.z) for m in tp.moves], [(m.x, m.y, m.z) for m in same.moves])
        pts = [(0, 0), (100, 0)]
        self.assertEqual(S.tab_count(model.Operation(tabs=2, tab_spacing=30.0), pts), 3)
        self.assertEqual(S.tab_count(model.Operation(tabs=0), pts), 0)


def square(win, x=0.0):
    from vectordrive.core import geom
    from vectordrive.core.document import Shape
    sh = Shape(path=geom.Path([geom.rect(x, 0, 20, 10)]), tool=0)
    win.canvas.doc.add(sh)
    win.canvas.select([sh])
    return sh


class TestPalette(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self._tpl = os.environ.get('VECTORDRIVE_CAM_TEMPLATES')
        os.environ['VECTORDRIVE_CAM_TEMPLATES'] = tempfile.mkdtemp()
        self.w = MainWindow()
        self.w.settings.setValue('fao/palette/unifiee', False)   # 0.917.0 : ces essais lisent les dossiers des 22 parcours
        self.w.cam_palette.refresh()

    def tearDown(self):
        self.w.settings.remove('fao/palette/unifiee')
        os.environ['VECTORDRIVE_CAM_TEMPLATES'] = self._tpl
        self.w.close()

    def test_docks_and_families(self):
        from PySide6.QtCore import Qt
        w = self.w
        self.assertEqual(w.dockWidgetArea(w.dock_cam), Qt.DockWidgetArea.LeftDockWidgetArea)
        self.assertIs(w.dock_cam.widget(), w.cam_palette)
        self.assertEqual(w.dockWidgetArea(w.dock_paths), Qt.DockWidgetArea.RightDockWidgetArea)
        self.assertIs(w.dock_paths.widget().widget(), w.cam_panel)      # dans un VScroll (round 219)
        base = w.cam_palette.tree.topLevelItem(0)                            # « Parcours type » (round 1036)
        tops = [base.child(i).text(0) for i in range(base.childCount())]
        for fam in ('Usinage 2D', 'Usinage 2D-3D', 'Usinage 3D', 'Laser'):
            self.assertIn(fam, tops)
        self.assertIn('cam_new_decoupe', w.cam_panel.palette_buttons)
        self.assertTrue(w.toggle_paths_window(True))                          # fenêtre détachée…
        self.assertTrue(w.dock_paths.isFloating())
        self.assertFalse(w.toggle_paths_window())                             # … ou panneau de droite
        self.assertFalse(w.dock_paths.isFloating())

    def test_selection_by_default(self):
        w, p = self.w, self.w.cam_panel
        self.assertEqual(p.machining_mode(), 'selection')
        self.assertIsNone(p.new_operation('decoupe', exec_dialog=False))      # rien de sélectionné
        self.assertIn('Sélectionnez', p.info.text())
        sh = square(w)
        op = p.new_operation('decoupe', exec_dialog=False)
        self.assertEqual((op.items, op.sources), ([sh.id], []))
        self.assertEqual([t.op_id for t in p.toolpaths], [op.id])             # le parcours validé est calculé
        w.cam_palette.set_mode('couleur')
        w.canvas.select([])
        op2 = p.new_operation('trace', exec_dialog=False)
        self.assertEqual((op2.items, op2.sources), ([], [w.canvas.doc.active_layer.tool]))
        self.assertEqual(sorted(t.op_id for t in p.toolpaths), sorted([op.id, op2.id]))   # l'autre est gardé
        w.cam_palette.set_mode('selection')
        w.cam_palette.color_on.setChecked(False)                     # round 429 : réglage partagé remis

    def test_template_from_form(self):
        from vectordrive.cam import model
        from vectordrive.ui.cam_panel import FieldsDialog
        w, p = self.w, self.w.cam_panel
        square(w)
        op = p.new_operation('decoupe', exec_dialog=False)
        s = p.setup()
        dlg = FieldsDialog(p, 'essai', model.Operation.from_dict(op.to_dict()), w.canvas.doc, s.tools,
                           templates=p.templates_for('decoupe'), preset='decoupe')
        dlg.widgets['depth'].setValue(3.3)
        dlg.widgets['z_start'].setValue(0.1)
        dlg.widgets['tab_spacing'].setValue(40.0)
        tpl = dlg.save_template('Détourage 3,3 pontets')
        self.assertEqual((tpl['preset'], len(tpl['tools'])), ('decoupe', 1))
        self.assertIn('Détourage 3,3 pontets', p.templates_for('decoupe'))
        mine = w.cam_palette.tree.topLevelItem(1)                            # « Mes modèles » (round 1036)
        self.assertTrue(any(mine.child(i).text(0).startswith('📄 Détourage 3,3 pontets')      # mémo de l'outil après
                            for i in range(mine.childCount())))
        op2 = p.new_operation('decoupe', exec_dialog=False, template='Détourage 3,3 pontets')
        self.assertEqual((op2.depth, op2.z_start, op2.tab_spacing, op2.tool_id), (3.3, 0.1, 40.0, op.tool_id))
        dlg2 = FieldsDialog(p, 'x', model.Operation(kind='contour'), w.canvas.doc, p.setup().tools,
                            templates=p.templates_for('decoupe'), preset='decoupe')
        self.assertTrue(dlg2.load_template('Détourage 3,3 pontets'))
        self.assertAlmostEqual(dlg2.widgets['depth'].value(), 3.3)
        self.assertEqual(dlg2.widgets['tool_id'].currentData(), op.tool_id)
        self.assertTrue(w.cam_palette.delete_template('Détourage 3,3 pontets', confirm=False))
        dlg.deleteLater()
        dlg2.deleteLater()

    def test_import_typeedit(self):
        w = self.w
        f = pathlib.Path(tempfile.mkdtemp()) / 'PathParam_Essai.TPP'
        f.write_bytes(tpp_bytes())
        n = w.cam_palette.import_typeedit([f], quiet=True)
        self.assertGreaterEqual(n, 3)
        names = w.cam_panel.templates_for('decoupe')
        self.assertIn('TypeEdit — Essai/Atelier / Trou Pz6', names)
        sh = square(w)
        op = w.cam_panel.new_operation('decoupe', exec_dialog=False, template='TypeEdit — Essai/Atelier / Trou Pz6')
        self.assertEqual((op.side, op.depth, op.items), ('interieur', 6.0, [sh.id]))


if __name__ == '__main__':
    unittest.main()
