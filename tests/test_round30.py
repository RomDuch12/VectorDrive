"""Round 30 : accrochage aux intersections et sur le contour."""
import math
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom
from vectordrive.core import snap as S
from vectordrive.core.document import Shape
from vectordrive.core.geom import Contour, Cubic, Line, Path


def line(a, b):
    return Shape(path=Path([Contour([Line(a, b)], False)]))


class TestIntersections(unittest.TestCase):
    def setUp(self):
        self.sn = S.Snap(enabled=True)

    def test_line_circle_exact(self):
        a = line((0, 0), (100, 50))
        c = Shape(path=Path([geom.circle((50, 25), 20)]))
        u = (100 / math.hypot(100, 50), 50 / math.hypot(100, 50))
        exp = (50 + 20 * u[0], 25 + 20 * u[1])
        h = self.sn.query(exp[0] + 0.3, exp[1] - 0.2, 1.0, [a, c])
        self.assertEqual(h.kind, 'intersection')
        self.assertLess(math.dist((h.x, h.y), exp), 1e-9)
        self.assertIsInstance(h.x, float)

    def test_two_circles(self):
        b = Shape(path=Path([geom.circle((50, 25), 20)]))
        c = Shape(path=Path([geom.circle((75, 25), 20)]))
        ey = 25 - math.sqrt(400 - 12.5 ** 2)
        h = self.sn.query(62.3, ey + 0.3, 1.0, [b, c])
        self.assertEqual(h.kind, 'intersection')
        self.assertLess(math.dist((h.x, h.y), (62.5, ey)), 1e-9)

    def test_curve_self_crossing(self):
        # boucle d'une seule Bézier : se croise elle-même ; avec une droite qui la coupe
        seg = Cubic((0, 0), (100, 60), (-40, 60), (60, 0))
        bez = Shape(path=Path([Contour([seg], False)]))
        ln = line((-10, 20), (70, 20))
        # croisements attendus : t où y(t) = 20, calculés à part
        ts = [t / 4000 for t in range(4001)]
        near = [seg.point(t) for t in ts if abs(seg.point(t)[1] - 20) < 0.05]
        self.assertTrue(near)
        x0 = near[0][0]
        self.sn.modes = {'intersection'}
        h = self.sn.query(x0 + 0.5, 20.4, 2.0, [bez, ln])
        self.assertIsNotNone(h)
        self.assertAlmostEqual(h.y, 20, places=9)
        self.assertAlmostEqual(h.x, x0, delta=0.1)

    def test_adjacent_segments_are_nodes(self):
        r = Shape(path=Path([geom.rect(0, 0, 20, 10)]))
        self.sn.modes = {'intersection'}
        self.assertIsNone(self.sn.query(0.2, 0.2, 1.0, [r]))
        self.sn.modes = {'node', 'intersection'}
        self.assertEqual(self.sn.query(0.2, 0.2, 1.0, [r]).kind, 'node')

    def test_node_wins_over_intersection_on_tie(self):
        a = line((0, 0), (10, 10))
        b = line((0, 10), (10, 0))
        c = line((5, 5), (5, 20))                                # nœud au croisement
        self.sn.modes = {'node', 'intersection'}
        self.assertEqual(self.sn.query(5.1, 5.1, 1.0, [a, b, c]).kind, 'node')

    def test_nearest_only_when_nothing_else(self):
        c = Shape(path=Path([geom.circle((0, 0), 10)]))
        self.sn.modes = {'node', 'nearest'}
        h = self.sn.query(7.3, 7.3, 1.0, [c])                     # loin des 4 nœuds du cercle
        self.assertEqual(h.kind, 'nearest')
        self.assertAlmostEqual(math.hypot(h.x, h.y), 10, places=3)
        h = self.sn.query(10.2, 0.1, 1.0, [c])                    # près du nœud (10, 0)
        self.assertEqual(h.kind, 'node')

    def test_default_modes(self):
        self.assertIn('intersection', S.Snap().modes)
        self.assertNotIn('nearest', S.Snap().modes)


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_actions_and_presets(self):
        w = self.w
        self.assertTrue(w.A['snap_intersection'].isChecked())
        self.assertFalse(w.A['snap_nearest'].isChecked())
        w.A['snap_nearest'].setChecked(True)
        self.assertIn('nearest', w.canvas.snap.modes)
        names = []
        for _ in range(len(w.SNAP_PRESETS)):
            w._cycle_snap(1)
            names.append(frozenset(w.canvas.snap.modes))
        self.assertIn(frozenset({'intersection'}), names)
        self.assertIn(frozenset({'nearest'}), names)


if __name__ == '__main__':
    unittest.main()
