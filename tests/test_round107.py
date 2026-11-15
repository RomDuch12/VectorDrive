"""Round 107 : plan de travail en mode 2D ou 3D — relief du dessin (traits à
la largeur de leur outil, profondeur de leur opération) ou des parcours FAO
simulés, vue OpenGL (bandes de triangles, côtés de la plaque, parcours)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.cam import model, relief as RL
from vectordrive.core import geom
from vectordrive.core.document import Document, Plate, Shape, Tool
from vectordrive.ui import progress as UP
from vectordrive.ui import view3d as V


def app():
    return QApplication.instance() or QApplication([])


def doc_square(width=0.5):
    d = Document()
    d.plate = Plate(width=40, height=30)
    d.tools = [Tool(1, '#000000', 'F', width)]
    d.layers[0].items.append(Shape(path=geom.Path([geom.rect(10, 10, 20, 10)]), tool=1))
    return d


def at(sim, x, y):
    i = int(round((x - sim.x0) / sim.res))
    j = int(round((y - sim.y0) / sim.res))
    return sim.H[j, i]


class TestReliefFromDrawing(unittest.TestCase):
    def setUp(self):
        app()

    def test_stroke_at_tool_width_and_default_depth(self):
        sim = RL.from_drawing(doc_square(), res=0.1)
        self.assertAlmostEqual(at(sim, 10, 15), -RL.DEFAULT_DEPTH)          # sur le trait
        self.assertAlmostEqual(at(sim, 20, 15), 0.0)                        # intérieur intact
        self.assertAlmostEqual(at(sim, 10.6, 15), 0.0)                      # hors de la largeur (0,5 mm)
        self.assertEqual((sim.x0, sim.y0), (0.0, 0.0))                      # la carte couvre la plaque
        self.assertGreaterEqual(sim.x0 + (sim.H.shape[1] - 1) * sim.res, 40 - 1e-9)
        self.assertAlmostEqual(sim.deepest, -RL.DEFAULT_DEPTH)
        self.assertGreater(sim.removed, 0)

    def test_fill_and_operation_depth(self):
        d = doc_square()
        model.store(d, model.CamSetup(operations=[model.Operation(kind='poche', depth=1.2, sources=[1],
                                                                  enabled=False)]))
        self.assertEqual(RL.tool_depths(d), {})                             # opération inactive
        s = model.setup_of(d)
        s.operations[0].enabled = True
        model.store(d, s)
        self.assertEqual(RL.tool_depths(d), {1: 1.2})
        sim = RL.from_drawing(d, res=0.1, fill_closed=True)
        self.assertAlmostEqual(at(sim, 20, 15), -1.2)

    def test_y_up_orientation(self):
        d = Document()
        d.plate = Plate(width=20, height=20)
        d.layers[0].items.append(Shape(path=geom.Path([geom.rect(2, 14, 4, 4)]), tool=1))
        sim = RL.from_drawing(d, res=0.1, fill_closed=True)
        self.assertLess(at(sim, 4, 16), 0)                                  # en haut à gauche
        self.assertEqual(at(sim, 4, 4), 0)

    def test_build_auto_and_fao(self):
        d = doc_square()
        r = RL.build(d, 'auto', res=0.2)
        self.assertEqual(r.source, 'dessin')
        self.assertEqual(r.plate[:4], (0.0, 0.0, 40.0, 30.0))
        r = RL.build(d, 'fao', res=0.2)
        self.assertEqual(r.source, 'dessin')
        self.assertTrue(r.warnings)
        s = model.CamSetup()
        s.tools = [model.CamTool(name='F1', diameter=1.0, step_down=0.5, number=1)]
        s.operations.append(model.Operation(kind='gravure', depth=0.4, tool_id=s.tools[0].id, sources=[1]))
        model.store(d, s)
        r = RL.build(d, 'auto', max_cells=200_000)
        self.assertEqual(r.source, 'fao')
        self.assertTrue(r.toolpaths)
        self.assertLess(r.sim.deepest, -0.3)
        x0, y0, x1, y1 = r.area
        self.assertLessEqual(x0, 0.0)
        self.assertGreaterEqual(x1, 40.0 - r.sim.res)

    def test_cancellable(self):
        UP.AUTO_CANCEL_AFTER_MS = 0
        try:
            d = doc_square()
            for k in range(200):
                d.layers[0].items.append(Shape(path=geom.Path([geom.circle((k % 40, k % 30), 1)]), tool=k % 50))
            with self.assertRaises(UP.Cancelled):
                UP.run(None, 'essai', RL.from_drawing, d, res=0.01)
        finally:
            UP.AUTO_CANCEL_AFTER_MS = None


class TestGeometry(unittest.TestCase):
    def test_pool_min(self):
        H = np.zeros((5, 7))
        H[3, 5] = -2
        P = V.pool_min(H, 2)
        self.assertEqual(P.shape, (3, 4))
        self.assertEqual(P.min(), -2)

    def test_mesh_strips(self):
        sim = RL.SimResult(np.zeros((10, 20)), 0.0, 0.0, 0.5)
        sim.H[4:6, 8:12] = -1
        strips, per = V.mesh(sim, exag=2.0)
        self.assertEqual(strips.shape, (9, 40, 9))
        self.assertEqual(per, 40)
        self.assertEqual(strips.dtype, np.float32)
        self.assertAlmostEqual(float(strips[..., 2].min()), -2.0)           # exagéré ×2
        normals = np.linalg.norm(strips[..., 3:6], axis=-1)
        self.assertTrue(np.allclose(normals, 1, atol=1e-4))
        big = RL.SimResult(np.zeros((2000, 1000)), 0.0, 0.0, 0.05)
        s2, per2 = V.mesh(big)
        self.assertLessEqual(max(s2.shape[0] + 1, per2 // 2), V.MAX_SIDE)

    def test_box_and_paths(self):
        b = V.box(0, 0, 10, 5, -2, 0)
        self.assertEqual(b.shape, (30, 9))
        tp = model.Toolpath('op', 'outil')
        tp.moves = [model.Move('rapid', 0, 0, 2), model.Move('feed', 0, 0, -0.5), model.Move('feed', 5, 0, -0.5),
                    model.Move('rapid', 5, 0, 2)]
        lines = V.path_lines([tp], exag=2.0)
        self.assertEqual(len(lines), 1)                                     # rapides masqués
        self.assertAlmostEqual(float(lines[0][:, 2].min()), -1.0)
        self.assertEqual(len(V.path_lines([tp], rapids=True)), 3)


class TestPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app()
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def test_switch_2d_3d(self):
        w = self.w
        w.canvas.doc.plate = Plate(width=50, height=30)
        w.canvas.doc.layers[0].items.append(Shape(path=geom.Path([geom.circle((25, 15), 8)]), tool=1))
        w.A['view_3d'].trigger()
        self.assertEqual(w.view_mode(), '3d')
        self.assertTrue(w.A['view_3d'].isChecked())
        p = w.panel3d
        self.assertIsNotNone(p.relief)
        self.assertFalse(p.stale)
        self.assertIn('mm', p.info.text())
        p.view.set_view('dessus')
        self.assertGreater(p.view.pitch, 89)
        p.exag.setValue(5)
        self.assertEqual(p.view.exag, 5)
        w._on_doc_changed()
        self.assertTrue(p.stale)
        w._refresh_3d_if_visible()
        self.assertFalse(p.stale)
        w.A['view_toggle'].trigger()
        self.assertEqual(w.view_mode(), '2d')
        self.assertTrue(w.A['view_2d'].isChecked())

    @unittest.skipIf(os.environ.get('QT_QPA_PLATFORM') == 'offscreen', 'pas d\'OpenGL en mode offscreen')
    def test_render(self):
        r = RL.build(doc_square(), 'dessin', res=0.1)
        v = V.View3D()
        v.resize(320, 200)
        v.set_relief(r)
        img = v.grabFramebuffer()
        self.assertTrue(v.ok)
        self.assertEqual(img.width(), 320)


if __name__ == '__main__':
    unittest.main()
