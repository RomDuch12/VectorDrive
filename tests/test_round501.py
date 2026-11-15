"""Round 501 : région pair-impair d'un grand groupe de contours sans XOR successifs (cadre autour de
milliers de lettres, contours qui se croisent) — même région, temps quasi linéaire."""
import random
import time
import unittest

import shapely
from shapely.geometry import Point, box

from vectordrive.cam import strategies as S
from vectordrive.core import geom


def xor_seq(members):
    g = None
    for r in sorted(members, key=lambda p: -p.area):
        g = r if g is None else g.symmetric_difference(r)
    return g


class TestEvenOdd(unittest.TestCase):
    def test_crossing_same_as_xor(self):
        rnd = random.Random(7)
        rings = []
        for i in range(120):
            x, y, r = rnd.uniform(0, 60), rnd.uniform(0, 60), rnd.uniform(1, 10)
            rings.append(Point(x, y).buffer(r, 6) if i % 2 else box(x, y, x + r, y + 0.6 * r))
        fast = shapely.union_all(S._even_odd(rings))
        self.assertLess(fast.symmetric_difference(xor_seq(rings)).area, 1e-6)

    def test_nested_frame_and_letters(self):
        rings = [box(-1, -1, 201, 201)]                      # cadre
        for i in range(40):
            for j in range(40):
                x, y = 5 * i, 5 * j
                rings.append(box(x, y, x + 4, y + 4))         # « lettre »
                rings.append(box(x + 1, y + 1, x + 3, y + 3))  # son trou
                rings.append(box(x + 1.5, y + 1.5, x + 2.5, y + 2.5))   # îlot dans le trou
        t = time.perf_counter()
        fast = shapely.union_all(S._even_odd(rings))
        self.assertLess(time.perf_counter() - t, 5.0)
        expect = 202 * 202 - 1600 * (16 - 4 + 1)
        self.assertAlmostEqual(fast.area, expect, places=6)
        part = rings[:1 + 3 * 30]
        self.assertLess(shapely.union_all(S._even_odd(part)).symmetric_difference(xor_seq(part)).area, 1e-6)

    def test_region_uses_it(self):
        paths = [geom.Path([geom.rect(-1, -1, 102, 102)])] + \
            [geom.Path([geom.rect(4 * i, 4 * j, 3, 3)]) for i in range(25) for j in range(25)]
        reg = S.region(paths, 0.02)
        self.assertAlmostEqual(reg.area, 102 * 102 - 625 * 9, places=6)
        self.assertTrue(reg.is_valid)


if __name__ == '__main__':
    unittest.main()
