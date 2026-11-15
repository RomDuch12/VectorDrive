"""Round 251 : lecture de l'usinage pas à pas dans la vue 3D — curseur sur
les mouvements, lecture, pas à pas, vitesse ; outil dessiné à sa place,
suite des parcours estompée, matière enlevée progressivement (étapes de
simulation reprises les unes des autres, identiques à la simulation
complète)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


def setup_and_path():
    from vectordrive.cam import model
    s = model.CamSetup()
    t = model.CamTool(name='F2', kind='fraise', diameter=2.0)
    s.tools = [t]
    tp = model.Toolpath('o', t.id, name='Poche')
    tp.moves = [model.Move('rapid', 0, 0, 5), model.Move('feed', 0, 0, -1), model.Move('feed', 20, 0, -1),
                model.Move('feed', 20, 10, -1), model.Move('feed', 0, 10, -1), model.Move('rapid', 0, 10, 5)]
    return s, tp


class TestCore(unittest.TestCase):
    def test_stages_add_up(self):
        import numpy as np
        from vectordrive.cam import simulate as S
        s, tp = setup_and_path()
        full = S.simulate([tp], s, res=0.1)
        z = S.SimResult(np.zeros_like(full.H), full.x0, full.y0, full.res)
        a = S.simulate_range([tp], s, z, 0, 3)
        b = S.simulate_range([tp], s, a, 3, 6)
        self.assertLess(a.removed, full.removed)
        self.assertEqual(float(np.abs(b.H - full.H).max()), 0.0)

    def test_path_indices_and_tool(self):
        from vectordrive.ui.view3d import path_lines, tool_lines
        _s, tp = setup_and_path()
        lines = path_lines([tp], rapids=True)
        idx = sorted({int(v) for ln in lines for v in ln[:, 4]})
        self.assertEqual(idx, [0, 1, 2, 3, 4, 5])                       # numéro du mouvement de chaque sommet
        cyl = tool_lines((5, 5, -1), 2.0)
        self.assertAlmostEqual(float(cyl[:, 2].min()), -1.0, 6)         # bout de l'outil au point
        cone = tool_lines((5, 5, -1), 6.0, 'conique', 60.0)
        self.assertAlmostEqual(float(cone[:, 2].min()), -1.0, 6)
        self.assertGreater(len(cone), len(cyl))


class TestPlayer(unittest.TestCase):
    def test_playback(self):
        from vectordrive.cam import relief as RL
        from vectordrive.core.document import Document
        from vectordrive.ui.main_window import MainWindow
        s, tp = setup_and_path()
        w = MainWindow()
        try:
            w.cam_panel.save(s)
            p = w._ensure_panel3d()
            doc = w.canvas.doc
            r = RL.from_paths(doc, [tp], cut=True, max_cells=20_000)
            p.view.set_relief(r)
            pl = p.player
            pl.load([tp], r)
            self.assertTrue(pl.isVisibleTo(p))
            self.assertEqual(pl.slider.maximum(), 6)
            pl.command('debut')
            self.assertEqual(p.view.playhead, -0.5)
            pl.command('avant')
            pl.command('avant')
            self.assertEqual(pl.slider.value(), 2)
            self.assertIn('Mouvement 2 / 6', pl.label.text())
            self.assertIsNotNone(p.view._tool_arr)                       # l'outil est dessiné
            st = pl.stage(3)
            self.assertLess(st.removed, r.sim.removed)
            self.assertGreater(st.removed, 0.0)
            pl._material()
            self.assertIsNot(p.view.relief, r)                           # matière à l'étape
            pl.command('fin')
            pl._material()
            self.assertIs(p.view.relief, r)
            self.assertEqual(p.view.playhead, 1e12)
            pl.speed.setCurrentIndex(0)                                  # ×1
            pl.command('lecture')                                        # à la fin : repart du début
            self.assertTrue(pl.timer.isActive())
            pl._tick()
            self.assertEqual(pl.slider.value(), 1)
            pl.command('lecture')
            self.assertFalse(pl.timer.isActive())
            pl.load([])
            self.assertFalse(pl.isVisibleTo(p))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
