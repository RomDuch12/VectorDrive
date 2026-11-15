"""Round 183 : région pair-impair par groupes de contours (mêmes résultats, rapide)."""
import math
import os
import random
import tempfile
import time
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import strategies as S
from vectordrive.core import geom


def sequential(paths, tol):
    """L'ancienne construction (XOR successifs), pour comparer."""
    from shapely.geometry import Polygon
    rings = []
    for pts, closed in S.polylines(paths, tol):
        if closed and len(pts) >= 4:
            poly = Polygon(pts)
            if not poly.is_valid:
                poly = poly.buffer(0)
            if not poly.is_empty:
                rings.append(poly)
    g = None
    for r in sorted(rings, key=lambda x: -x.area):
        g = r if g is None else g.symmetric_difference(r)
    return g


def scene(n, seed):
    rnd = random.Random(seed)
    paths = []
    for _ in range(n):
        cx, cy, r = rnd.uniform(0, 100), rnd.uniform(0, 60), rnd.uniform(0.5, 4)
        paths.append(geom.Path([geom.circle((cx, cy), r)]))
        if rnd.random() < 0.3:                                                  # un trou dedans (lettre)
            paths.append(geom.Path([geom.circle((cx, cy), r / 2)]))
    return paths


class TestRegion(unittest.TestCase):
    def test_same_region(self):
        for seed in range(3):
            paths = scene(150, seed)
            new, old = S.region(paths, 0.01), sequential(paths, 0.01)
            self.assertAlmostEqual(new.area, old.area, places=6)
            self.assertLess(new.symmetric_difference(old).area, 1e-6)

    def test_nested_and_overlap(self):
        paths = [geom.Path([geom.rect(0, 0, 50, 50)]), geom.Path([geom.rect(10, 10, 30, 30)]),
                 geom.Path([geom.rect(20, 20, 10, 10)])] + [geom.Path([geom.circle((80 + i * 3, 10), 2)])
                                                             for i in range(70)]
        new, old = S.region(paths, 0.01), sequential(paths, 0.01)
        self.assertLess(new.symmetric_difference(old).area, 1e-6)
        self.assertTrue(new.is_valid)

    def test_speed(self):
        rnd = random.Random(5)
        paths = [geom.Path([geom.circle((rnd.uniform(0, 300), rnd.uniform(0, 200)), 1.2)]) for _ in range(3000)]
        t = time.perf_counter()
        reg = S.region(paths, 0.01)
        self.assertLess(time.perf_counter() - t, 10.0)
        self.assertGreater(reg.area, 0)


if __name__ == '__main__':
    unittest.main()
