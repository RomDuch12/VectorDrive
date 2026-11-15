"""Round 192 : laser plus grand que le champ, en morceaux (TauDrive)."""
import math
import os
import re
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import model, tiling as T
from vectordrive.cam.model import Move, Toolpath


def length(polys):
    return sum(math.dist(a, b) for pl in polys for a, b in zip(pl, pl[1:]))


def laser_setup(**kw):
    s = model.CamSetup(post='cielle', **kw)
    t = model.CamTool(name='Laser', kind='laser', diameter=0.05, power=60, frequency=30, feed=2000.0)
    s.tools = [t]
    s.operations = [model.Operation(kind='laser', tool_id=t.id)]
    return s


def toolpath(s, polylines):
    tp = Toolpath(op_id=s.operations[0].id, tool_id=s.tools[0].id, name='Marquage')
    for pl in polylines:
        tp.moves.append(Move('rapid', pl[0][0], pl[0][1], 5.0))
        tp.moves.append(Move('rapid', pl[0][0], pl[0][1], 0.0))
        for x, y in pl[1:]:
            tp.moves.append(Move('feed', x, y, 0.0))
    return tp


class TestPlan(unittest.TestCase):
    def test_single_and_grid(self):
        self.assertEqual(len(T.plan((-50, -50, 50, 50), 110, 110)), 1)            # tient : tel quel
        tiles = T.plan((0, 0, 250, 100), 110, 110, 2.0)                           # utile 106 mm
        self.assertEqual([(t.col, t.row) for t in tiles], [(1, 1), (2, 1), (3, 1)])
        self.assertAlmostEqual(tiles[0].width, 250 / 3)
        self.assertAlmostEqual(tiles[1].dx, -250 / 3)                             # la pièce part à gauche
        g = T.plan((0, 0, 200, 200), 110, 110, 2.0)
        self.assertEqual([(t.col, t.row) for t in g], [(1, 1), (2, 1), (2, 2), (1, 2)])   # serpentin
        self.assertAlmostEqual(g[2].dy, 100.0)                                     # rangée du bas : la pièce monte
        self.assertTrue(T.needed((0, 0, 107, 10), 110, 110, 2.0))
        self.assertFalse(T.needed((0, 0, 105, 10), 110, 110, 2.0))
        self.assertTrue(T.outside((0, 0, 60, 10), 110, 110))
        self.assertFalse(T.outside((-55, -5, 55, 5), 110, 110))

    def test_nothing_twice(self):
        tiles = T.plan((0, 0, 200, 200), 110, 110, 2.0)
        polys = [[(0, 0), (200, 200)], [(100, 0), (100, 200)], [(0, 100), (200, 100), (200, 0)],
                 [(10, 10), (190, 15), (20, 180), (10, 10)]]
        total = sum(length(T.cut(polys, t)) for t in tiles)
        self.assertAlmostEqual(total, length(polys), places=6)                      # frontières comprises une fois
        for t in tiles:
            for pl in T.cut(polys, t):
                for x, y in pl:
                    self.assertLessEqual(abs(x), t.width / 2 + 1e-6)              # recentré
                    self.assertLessEqual(abs(y), t.height / 2 + 1e-6)

    def test_marks_and_instructions(self):
        tiles = T.plan((0, 0, 200, 90), 110, 110, 2.0)
        self.assertEqual(len(T.join_marks(tiles[0])), 1)                          # un voisin à droite
        text = T.instructions(tiles, (0, 0, 200, 90), 'plaque', (110, 110), 2.0, True, '2026-10-18 17:00')
        text.encode('ascii')
        self.assertIn('GRAVURE EN 2 MORCEAUX', text)
        self.assertIn('Deplacer la piece de 100,0 mm vers X- (gauche)', text)
        self.assertIn('plaque_M02.CLJOB', text)


class TestUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_panel_row(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            panel = w.cam_panel
            s = model.setup_of(w.canvas.doc)
            s.post = 'gcode'
            model.store(w.canvas.doc, s)
            panel.refresh()
            self.assertTrue(panel.laser_row.isHidden())
            s.post = 'cielle'
            model.store(w.canvas.doc, s)
            panel.refresh()
            self.assertFalse(panel.laser_row.isHidden())
            panel.laser_tiles.setChecked(True)
            self.assertTrue(model.setup_of(w.canvas.doc).laser_tiles)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
