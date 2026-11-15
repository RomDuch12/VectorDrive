"""Round 29 : vectorisation en trait central (gravure en un passage)."""
import math
import unittest

import numpy as np

from vectordrive.core import trace as TR


def strokes():
    """Cercle r 50 (trait de 6 px) et croix de deux traits de 6 px."""
    H, W = 200, 300
    yy, xx = np.mgrid[0:H, 0:W] + 0.5
    g = np.ones((H, W))
    g[np.abs(np.hypot(xx - 80, yy - 100) - 50) < 3] = 0
    g[95:101, 160:280] = 0
    g[40:160, 217:223] = 0
    return g


class TestThin(unittest.TestCase):
    def test_one_pixel_wide(self):
        ink = np.zeros((20, 60), bool)
        ink[5:12, 5:55] = True
        sk = TR.thin(ink)
        cols = sk[:, 10:50]
        self.assertTrue((cols.sum(0) == 1).all())                 # une seule ligne
        self.assertLess(sk.sum(), ink.sum() / 5)

    def test_neighbours_no_triangles(self):
        sk = np.zeros((5, 5), bool)
        sk[2, 1] = sk[2, 2] = sk[1, 2] = True                     # coude
        self.assertEqual(sorted(TR._neighbours(sk, 1, 2)), [(2, 2)])  # pas de diagonale vers (2, 1)


class TestCenterline(unittest.TestCase):
    def test_circle_and_cross(self):
        cs = TR.trace_centerline(strokes(), TR.TraceSpec())
        closed = [c for c in cs if c.closed]
        opened = [c for c in cs if not c.closed]
        self.assertEqual(len(closed), 1)
        self.assertAlmostEqual(closed[0].length(), 2 * math.pi * 50, delta=2 * math.pi * 50 * 0.01)
        self.assertEqual(len(opened), 2)                          # la croix : deux traits d'un seul tenant
        for c in opened:
            bb = c.bbox()
            self.assertGreater(max(bb[2] - bb[0], bb[3] - bb[1]), 105)
            self.assertLess(min(bb[2] - bb[0], bb[3] - bb[1]), 1e-6)

    def test_spurs_removed(self):
        g = np.ones((60, 200))
        g[25:35, 10:190] = 0                                      # trait épais de 10 px
        g[20:25, 100:102] = 0                                     # petite bosse
        cs = TR.trace_centerline(g, TR.TraceSpec())
        self.assertEqual(len(cs), 1)
        self.assertFalse(cs[0].closed)

    def test_join_straight(self):
        a = (np.array([[0, 0], [5, 0], [10, 0]], float), False)
        b = (np.array([[10, 0], [15, 0], [20, 0]], float), False)
        c = (np.array([[10, 0], [10, 5], [10, 10]], float), False)
        out = TR.join_straight([a, b, c])
        self.assertEqual(len(out), 2)
        longest = max(out, key=lambda pc: len(pc[0]))
        self.assertEqual(longest[0][0].tolist(), [0, 0])
        self.assertEqual(longest[0][-1].tolist(), [20, 0])


if __name__ == '__main__':
    unittest.main()
