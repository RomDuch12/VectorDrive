"""Round 591 : usiner les faces ou les contours choisis dans la vue 3D — finition 3D limitée à la zone
(l'outil évite toujours toute la pièce), contours mis dans le dessin, poche jusqu'à un fond plat, zone
d'un usinage remplacée ou montrée ; la surface 3D lit aussi les STL et 3D XML."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.cam import mill3d, model, strategies
from vectordrive.core import faces3d as F
from vectordrive.core import solids as SO
from vectordrive.core.document import Document

app = QApplication.instance() or QApplication([])


def pocket_stl():
    """Bloc 40 × 20 × 10, poche 20 × 10 profonde de 5 (fond à Z 5), en STL."""
    from vectordrive.io import stl_write
    s = SO.boolean('subtract', [SO.box(0, 0, 0, 40, 20, 10), SO.box(10, 5, 5, 20, 10, 10)])
    f = pathlib.Path(tempfile.mkdtemp()) / 'poche.stl'
    stl_write.write_stl(str(f), s.triangles())
    return str(f)


def face_under(m, x, y):
    i, _d = F.ray_hit(m.triangles, (x, y, 100), (0, 0, -1))
    return int(m.face_ids()[i])


def feeds(tp):
    return [mv for mv in tp.moves if mv.kind == 'feed']


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestZone(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = pocket_stl()
        cls.m = mill3d.load_model(Document(), cls.f)
        cls.floor = face_under(cls.m, 20, 10)
        cls.top = face_under(cls.m, 3, 3)
        cls.setup = model.CamSetup(tools=[model.CamTool(kind='boule', diameter=4, stepover=0.25, step_down=10)])

    def op(self, **kw):
        return model.Operation(kind='surface3d', tool_id=self.setup.tools[0].id, depth=0, resolution=0.2,
                               model_path=self.f, **kw)

    def test_cache(self):
        self.assertIs(mill3d.load_model(Document(), self.f), self.m)

    def test_whole_piece_from_stl(self):
        tp = strategies.compute(Document(), self.setup, self.op())
        z = [mv.z for mv in feeds(tp)]
        self.assertAlmostEqual(min(z), -10.0, 6)              # autour de la pièce : jusqu'en bas (592)
        self.assertAlmostEqual(min(mv.z for mv in feeds(tp) if 12 < mv.x < 28 and 7 < mv.y < 13), -5.0, 6)
        self.assertLessEqual(max(z), 1e-9)
        self.assertLess(min(mv.x for mv in feeds(tp)), 0.0)   # tout autour de la pièce

    def test_floor_only(self):
        tp = strategies.compute(Document(), self.setup, self.op(faces3d=[self.floor]))
        fs = feeds(tp)
        self.assertTrue(fs)
        self.assertTrue(all(abs(mv.z + 5.0) < 1e-6 for mv in fs))          # rien que le fond
        self.assertGreaterEqual(min(mv.x for mv in fs), 12.0 - 1e-6)      # boule Ø4 : à 2 mm des parois
        self.assertLessEqual(max(mv.x for mv in fs), 28.0 + 1e-6)
        self.assertGreaterEqual(min(mv.y for mv in fs), 7.0 - 1e-6)
        self.assertLessEqual(max(mv.y for mv in fs), 13.0 + 1e-6)

    def test_top_only_skips_pocket(self):
        tp = strategies.compute(Document(), self.setup, self.op(faces3d=[self.top]))
        fs = feeds(tp)
        self.assertTrue(all(abs(mv.z) < 1e-6 for mv in fs))               # le dessus seul, à Z 0
        inside = [mv for mv in fs if 12 < mv.x < 28 and 7 < mv.y < 13]
        self.assertEqual(inside, [])                                      # la poche est sautée

    def test_contour_zone(self):
        sq = [[5, 2, 10], [35, 2, 10], [35, 18, 10], [5, 18, 10], [5, 2, 10]]
        tp = strategies.compute(Document(), self.setup, self.op(contours3d=[sq]))
        fs = feeds(tp)
        self.assertGreaterEqual(min(mv.x for mv in fs), 5.0 - 0.2)
        self.assertLessEqual(max(mv.x for mv in fs), 35.0 + 0.2)
        self.assertAlmostEqual(min(mv.z for mv in fs), -5.0, 6)

    def test_extension_widens(self):
        a = strategies.compute(Document(), self.setup, self.op(faces3d=[self.floor]))
        b = strategies.compute(Document(), self.setup, self.op(faces3d=[self.floor], extension=1.0))
        self.assertLessEqual(min(mv.x for mv in feeds(b)), min(mv.x for mv in feeds(a)))

    def test_vertical_faces_warn(self):
        wall = int(self.m.face_ids()[F.ray_hit(self.m.triangles, (20, 10, 7), (1, 0, 0))[0]])
        tp = strategies.compute(Document(), self.setup, self.op(faces3d=[wall]))
        self.assertTrue(any('Niveaux constants' in w for w in tp.warnings), tp.warnings)

    def test_helpers(self):
        self.assertEqual(mill3d.useful_levels([-1.0, -2.0, -3.0, -4.0], np.array([[-1.5, 0.0]])), [-1.0, -2.0])
        m = np.zeros((7, 7), bool)
        m[3, 3] = True
        self.assertEqual(int(mill3d.dilate(m, 1).sum()), 5)               # croix
        self.assertEqual(int(mill3d.dilate(m, 2).sum()), 21)
        outer = [[0, 0], [10, 0], [10, 10], [0, 10]]
        inner = [[3, 3], [6, 3], [6, 6], [3, 6]]
        reg = mill3d.contour_polygons([outer, inner])
        self.assertAlmostEqual(reg.area, 91.0, 9)                         # l'îlot reste hors zone
        op = model.Operation(contours3d=[outer])
        self.assertEqual(mill3d.zone_bbox(op, self.m), (0.0, 0.0, 10.0, 10.0))
        self.assertEqual(mill3d._runs([0, 1, 1, 0, 1]), [(1, 3), (4, 5)])

    def test_operation_round_trip(self):
        o = model.Operation(kind='surface3d', faces3d=[3, 5], contours3d=[[[0, 0, 1], [1, 0, 1], [0, 1, 1]]])
        back = model.Operation.from_dict(o.to_dict())
        self.assertEqual(back.faces3d, [3, 5])
        self.assertEqual(back.contours3d, o.contours3d)


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestWindow(unittest.TestCase):
    def test_panel_actions(self):
        from vectordrive.ui.main_window import MainWindow
        f = pocket_stl()
        w = MainWindow()
        try:
            w.open_file(f) if hasattr(w, 'open_file') else w.open_path(f)
            p = w._ensure_panel3d()
            p = p or w.panel3d
            self.assertTrue(p.refresh())
            self.assertIsNotNone(p.view.model)
            m = p.view.model
            floor = face_under(m, 20, 10)
            p.view.select_mode = 'faces'
            p.view.set_selection(faces=[floor])
            self.assertTrue(p.use.isEnabled())
            self.assertTrue(p.flat_selection())
            self.assertAlmostEqual(p.selection_depth(), 5.0, 4)
            loops = p.selection_loops()
            self.assertEqual(len(loops), 1)
            # finition 3D de la sélection
            o = p.machine_selection('surface3d', exec_dialog=False)
            self.assertEqual(o.faces3d, [floor])
            self.assertEqual(o.model_path, '')                           # la pièce du dessin
            self.assertAlmostEqual(o.depth, 5.0, 3)
            cp = w.cam_panel
            self.assertIn(o.id, [x.id for x in cp.ops_3d()])
            tp = next(t for t in cp.toolpaths if t.op_id == o.id)
            fs = feeds(tp)
            self.assertAlmostEqual(min(mv.z for mv in fs), -5.0, 6)        # paliers jusqu'au fond, pas plus bas
            self.assertTrue(all(10.0 < mv.x < 30.0 and 5.0 < mv.y < 15.0 for mv in fs))   # dans la poche
            # poche jusqu'au fond : contour dans le dessin, poche à 5 mm
            n_items = sum(len(L.items) for L in w.canvas.doc.layers)
            shapes = p.contours_to_drawing(pocket=True, exec_dialog=False)
            self.assertEqual(len(shapes), 1)
            self.assertEqual(sum(len(L.items) for L in w.canvas.doc.layers), n_items + 1)
            bb = shapes[0].bbox()
            self.assertAlmostEqual(bb[0], 10.0, 4)
            self.assertAlmostEqual(bb[3], 15.0, 4)
            pk = cp.setup().operations[-1]
            self.assertEqual(pk.kind, 'poche')
            self.assertAlmostEqual(pk.depth, 5.0, 3)
            self.assertEqual(pk.items, [shapes[0].id])
            # zone remplacée par le dessus, puis montrée
            top = face_under(m, 3, 3)
            p.view.set_selection(faces=[top])
            self.assertTrue(p.replace_zone(o.id))
            o2 = next(x for x in cp.setup().operations if x.id == o.id)
            self.assertEqual(o2.faces3d, [top])
            p.view.clear_selection()
            p.show_zone(o2)
            self.assertEqual(p.view.sel_faces, {top})
            self.assertEqual(p.select.currentData(), 'faces')
            p._fill_use_menu()
            labels = [a.text() for a in p.use_menu.actions()]
            self.assertTrue(any('Balayage 3D' in t for t in labels))
        finally:
            w.modified = False
            w.close()

    def test_form_zone_checkbox(self):
        from vectordrive.ui.cam_panel import FieldsDialog
        o = model.Operation(kind='surface3d', faces3d=[1, 2])
        dlg = FieldsDialog(None, 'x', o, Document(), [model.CamTool()])
        w = dlg.widgets['faces3d']
        self.assertTrue(w.isChecked())
        self.assertIn('2 face', w.text())
        w.setChecked(False)
        dlg.apply()
        self.assertEqual(o.faces3d, [])


if __name__ == '__main__':
    unittest.main()
