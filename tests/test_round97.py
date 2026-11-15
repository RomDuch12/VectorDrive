"""Round 97 : simulation d'enlèvement de matière (carte de hauteurs, outil
plat / boule / cône imprimé le long des parcours), fenêtre de simulation."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model, simulate, strategies
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def line_path(tool_id, z=-1.0, length=20.0):
    tp = model.Toolpath(op_id='', tool_id=tool_id, name='trait')
    tp.moves = [model.Move('rapid', 0, 0, 2), model.Move('plunge', 0, 0, z), model.Move('feed', length, 0, z),
                model.Move('rapid', length, 0, 2)]
    return tp


class TestSimulate(unittest.TestCase):
    def cell(self, r, x, y):
        return r.H[int(round((y - r.y0) / r.res)), int(round((x - r.x0) / r.res))]

    def test_flat_groove(self):
        s = model.CamSetup(tools=[model.CamTool(kind='fraise', diameter=2)])
        r = simulate.simulate([line_path(s.tools[0].id)], s, res=0.05)
        self.assertAlmostEqual(self.cell(r, 10, 0), -1.0, places=9)
        self.assertAlmostEqual(self.cell(r, 10, 0.9), -1.0, places=9)
        self.assertEqual(self.cell(r, 10, 1.2), 0.0)
        self.assertAlmostEqual(r.removed, 2 * 20 + math.pi, delta=1.5)    # sillon + deux demi-disques
        self.assertAlmostEqual(r.deepest, -1.0, places=9)

    def test_v_groove_profile(self):
        s = model.CamSetup(tools=[model.CamTool(kind='conique', diameter=6, angle=90, tip=0.0)])
        r = simulate.simulate([line_path(s.tools[0].id)], s, res=0.05)
        for d in (0.0, 0.5, 0.8):
            self.assertAlmostEqual(self.cell(r, 10, d), -1.0 + d, delta=0.03)   # 90° : flanc à 45°
        self.assertEqual(self.cell(r, 10, 1.2), 0.0)

    def test_ball(self):
        s = model.CamSetup(tools=[model.CamTool(kind='boule', diameter=2)])
        r = simulate.simulate([line_path(s.tools[0].id)], s, res=0.05)
        self.assertAlmostEqual(self.cell(r, 10, 0.5), -1.0 + (1 - math.sqrt(0.75)), delta=0.02)

    def test_pocket_volume_and_rapids_ignored(self):
        d = Document()
        d.layers[0].items.append(Shape(path=geom.Path([geom.rect(0, 0, 30, 15), geom.circle((8, 7.5), 3)])))
        s = model.CamSetup(tools=[model.CamTool(name='F2', diameter=2, step_down=0.5)])
        s.operations = [model.Operation(kind='poche', tool_id=s.tools[0].id, depth=1)]
        r = simulate.simulate(strategies.compute_all(d, s), s, res=0.1)
        self.assertAlmostEqual(r.deepest, -1.0, places=9)
        self.assertAlmostEqual(r.removed, 450 - math.pi * 9, delta=0.03 * 421)
        self.assertEqual(self.cell(r, 8, 7.5), 0.0)                        # îlot intact

    def test_bogus_tool_header(self):
        s = model.CamSetup(tools=[model.CamTool(kind='fraise', diameter=1000)])
        r = simulate.simulate([line_path(s.tools[0].id)], s, res=0.1)
        self.assertTrue(any('invraisemblable' in w for w in r.warnings))
        self.assertEqual(self.cell(r, 10, 1.5), 0.0)                        # outil ramené à 1 mm

    def test_render(self):
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        s = model.CamSetup(tools=[model.CamTool(kind='fraise', diameter=2)])
        r = simulate.simulate([line_path(s.tools[0].id)], s, res=0.1)
        img = simulate.render(r)
        self.assertFalse(img.isNull())
        self.assertEqual((img.width(), img.height()), (r.H.shape[1], r.H.shape[0]))


class TestDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_panel_simulation(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.canvas.doc.add(Shape(path=geom.Path([geom.rect(0, 0, 20, 10)])))
            w.cam_panel.ops_from_colors()
            dlg = w.cam_panel.simulate(exec_dialog=False)
            self.assertIn('mm³', dlg.info.text())
            with tempfile.TemporaryDirectory() as tmp:
                f = os.path.join(tmp, 'sim.png')
                dlg.save_image(f)
                self.assertGreater(os.path.getsize(f), 100)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
