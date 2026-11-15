"""Round 82 : repli shapely en n log n (région pair-impair de nombreux
contours)."""
import math
import os
import time
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom, pathops
from vectordrive.core.geom import Path


class TestShapelyFallback(unittest.TestCase):
    def test_even_odd_many_contours_fast(self):
        cs = [geom.circle((i % 20 * 3, i // 20 * 3), 1) for i in range(400)]
        cs += [geom.rect(-5, -5, 70, 70), geom.rect(-2, -2, 64, 64)]
        t = time.perf_counter()
        g = pathops._to_shapely(Path(cs))
        self.assertLess(time.perf_counter() - t, 5)
        self.assertAlmostEqual(g.area, 70 * 70 - 64 * 64 + 400 * math.pi, delta=5)      # polygones à 2 µm

    def test_even_odd_semantics(self):
        same = Path([geom.circle((0, 0), 10), geom.circle((0, 0), 5)])            # trou tracé dans le même sens
        self.assertAlmostEqual(pathops._to_shapely(same).area, math.pi * 75, delta=0.05)
        three = Path([geom.rect(0, 0, 10, 10), geom.rect(2, 2, 6, 6), geom.rect(4, 4, 2, 2)])
        self.assertAlmostEqual(pathops._to_shapely(three).area, 100 - 36 + 4, places=6)


class TestExactLimit(unittest.TestCase):
    def test_huge_drawings_use_native(self):
        from vectordrive.core import parallel
        many = Path([geom.polygon((i % 70 * 3.0, i // 70 * 3.0), 1, 64) for i in range(70)])   # 4 480 segments
        self.assertGreater(many.segment_count(), parallel.EXACT_LIMIT)
        t = time.perf_counter()
        res, exact = parallel.offset_checked(many, 0.2)
        self.assertFalse(exact)
        self.assertLess(time.perf_counter() - t, 10)
        self.assertGreater(pathops.area(res), pathops.area(many))
        small = Path([geom.circle((0, 0), 5)])
        self.assertTrue(parallel.offset_checked(small, 0.2)[1])


if __name__ == '__main__':
    unittest.main()
