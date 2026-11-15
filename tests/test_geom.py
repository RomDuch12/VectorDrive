import math
import unittest

from vectordrive.core import geom
from vectordrive.core.geom import Affine, Conic, Cubic, Line


class TestGeom(unittest.TestCase):
    def test_circle_exact(self):
        c = geom.circle((5, -3), 10)
        self.assertAlmostEqual(c.length(), 2 * math.pi * 10, places=9)
        self.assertTrue(c.closed)
        bb = c.bbox()
        for got, exp in zip(bb, (-5, -13, 15, 7)):
            self.assertAlmostEqual(got, exp, places=6)

    def test_conic_is_on_circle(self):
        for s in geom.arc_conics((0, 0), 7, 7, 10, 250):
            for t in (0.1, 0.33, 0.5, 0.9):
                x, y = s.point(t)
                self.assertAlmostEqual(math.hypot(x, y), 7, places=9)

    def test_circle_params(self):
        s = geom.arc_conics((1, 2), 3, 3, 0, 90)[0]
        c, r, a0, sweep = s.circle_params()
        self.assertAlmostEqual(c[0], 1)
        self.assertAlmostEqual(c[1], 2)
        self.assertAlmostEqual(r, 3)
        self.assertAlmostEqual(sweep, 90)

    def test_affine_keeps_arcs(self):
        m = Affine.rotation(33, (4, 4)) @ Affine.translation(10, -2)
        c = geom.circle((0, 0), 5).transformed(m)
        self.assertAlmostEqual(c.length(), 2 * math.pi * 5, places=9)

    def test_inverse(self):
        m = Affine(2, 0.5, -1, 3, 7, -4)
        p = (3.3, -1.1)
        q = m.inverse().apply(m.apply(p))
        self.assertAlmostEqual(q[0], p[0])
        self.assertAlmostEqual(q[1], p[1])

    def test_bulge(self):
        segs = geom.bulge_segment((0, 0), (2, 0), 1.0)      # demi-cercle trigo
        L = sum(s.length() for s in segs)
        self.assertAlmostEqual(L, math.pi, places=9)
        y = segs[0].point(0.5)[1]
        self.assertLess(y, 0)                                 # trigo de gauche à droite : passe dessous

    def test_rect_rounded_length(self):
        self.assertAlmostEqual(geom.rect(0, 0, 80, 40, 5).length(), 2 * 70 + 2 * 30 + 2 * math.pi * 5, places=9)

    def test_conic_to_cubics(self):
        s = geom.arc_conics((0, 0), 10, 10, 0, 90)[0]
        for cb in s.to_cubics(1e-4):
            for t in (0.25, 0.5, 0.75):
                x, y = cb.point(t)
                self.assertAlmostEqual(math.hypot(x, y), 10, delta=2e-4)

    def test_signed_area(self):
        c = geom.rect(0, 0, 10, 5)
        self.assertAlmostEqual(c.signed_area(), 50)
        self.assertAlmostEqual(c.reversed().signed_area(), -50)


if __name__ == '__main__':
    unittest.main()
