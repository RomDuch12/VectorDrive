"""Round 217 : parcours calculés vus en 2D et en 3D (trajectoires au-dessus
de la matière), simulés en 2D et en 3D (ceux du panneau, pas un nouveau
calcul de tout) ; ruban FAO « Voir et simuler »."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


def drawing():
    from vectordrive.cam import model
    from vectordrive.core import geom
    from vectordrive.core.document import Document, Shape
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 30, 10)]), tool=0))
    s = model.CamSetup()
    t = model.CamTool(name='F1', kind='fraise', diameter=1.0, step_down=0.2, cut_length=5)
    s.tools = [t]
    s.operations = [model.Operation(kind='poche', tool_id=t.id, depth=0.4, step_down=0.2)]
    model.store(d, s)
    return d, s


class TestRelief(unittest.TestCase):
    def test_paths_and_simulation(self):
        from vectordrive.cam import relief as RL, strategies as S
        d, s = drawing()
        tps = S.compute_all(d, s)
        flat = RL.build(d, 'parcours', toolpaths=tps)
        self.assertEqual((flat.source, len(flat.toolpaths)), ('parcours', 1))
        self.assertEqual(float(flat.sim.H.min()), 0.0)                          # matière intacte
        self.assertAlmostEqual(flat.sim.deepest, -0.4, 6)                       # mais la profondeur est dite
        cut = RL.build(d, 'simulation', toolpaths=tps)
        self.assertEqual(cut.source, 'simulation')
        self.assertGreater(cut.sim.removed, 50)
        self.assertAlmostEqual(cut.sim.deepest, -0.4, 2)
        empty = RL.build(d, 'parcours', toolpaths=[])
        self.assertIn('aucun parcours calculé', empty.warnings)


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.close()

    def test_views(self):
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        w = self.w
        sh = Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]), tool=0)
        w.canvas.doc.add(sh)
        w.canvas.select([sh])
        op = w.cam_panel.new_operation('gravure', exec_dialog=False)
        self.assertEqual([t.op_id for t in w.cam_panel.toolpaths], [op.id])
        w.show_toolpaths('3d')
        self.assertEqual(w.view_mode(), '3d')
        self.assertEqual(w.panel3d.relief.source, 'parcours')
        self.assertEqual([t.op_id for t in w.panel3d.relief.toolpaths], [op.id])   # ceux du panneau
        self.assertTrue(w.panel3d.paths.isChecked())
        w.show_toolpaths('sim3d')
        self.assertEqual(w.panel3d.relief.source, 'simulation')
        self.assertGreater(w.panel3d.relief.sim.removed, 0)
        w.show_toolpaths('2d')
        self.assertEqual(w.view_mode(), '2d')

    def test_ribbon_and_typeedit(self):
        from vectordrive.ui.shortcuts import TE_ACTIONS
        w = self.w
        for k in ('cam_paths_2d', 'cam_paths_3d', 'cam_sim_3d', 'cam_simulate'):
            self.assertIn(k, w.A)
        r = w.ribbon
        fao = next(i for i in range(r.count()) if r.tabText(i) == 'FAO 2D')
        titles = [g.title.text() for g in r.page(fao).groups()]
        self.assertIn('Voir et simuler', titles)
        self.assertEqual(TE_ACTIONS['ID_CMD_SIMUL_VOL_NEW'], 'cam_sim_3d')
        from PySide6.QtWidgets import QPushButton
        texts = [b.text() for b in w.cam_panel.findChildren(QPushButton)]
        self.assertEqual(texts.count('3D'), 0)              # round 1002 : voir et simuler sont au ruban seulement
        self.assertIn('Parcours 3D', texts)                 # … et le panneau a son bouton « Parcours 3D »


if __name__ == '__main__':
    unittest.main()
