"""Round 531 : retrait d'une pièce à nombreux trous (fond d'une plaque autour de lettres) par
décomposition — contour rétréci moins trous élargis — même surface, sans l'explosion du coût du retrait
direct avec la distance (poche du fond d'une plaque : plus de 6 min → 5 s)."""
import time
import unittest

import shapely
from shapely.geometry import MultiPolygon, Polygon, box

from vectordrive.cam import strategies as S


def plate(n=30):
    holes = [box(4 + 6 * (i % n), 4 + 6 * (i // n), 7 + 6 * (i % n), 8 + 6 * (i // n)).exterior.coords
             for i in range(n * 8)]
    return Polygon(box(0, 0, 6 * n + 6, 60).exterior.coords, holes)


class TestHolesSplit(unittest.TestCase):
    def test_same_region(self):
        p = plate()
        self.assertGreaterEqual(len(p.interiors), S.HOLES_SPLIT)
        for d in (0.5, 1.5, 4.0, 12.0):
            a = p.buffer(-d, quad_segs=8)
            b = S._erode_one(p, d, 8)
            self.assertLess(a.symmetric_difference(b).area, 1e-6, d)
        mixed = MultiPolygon([p, box(500, 0, 520, 20), box(600, 0, 640, 10)])
        for d in (0.5, 3.0):
            self.assertLess(mixed.buffer(-d, quad_segs=8).symmetric_difference(S.erode(mixed, d, 8)).area, 1e-6)

    def test_faster_far(self):
        p = plate(40)
        t = time.perf_counter()
        S._erode_one(p, 20.0, 8)
        split = time.perf_counter() - t
        t = time.perf_counter()
        p.buffer(-20.0, quad_segs=8)
        direct = time.perf_counter() - t
        self.assertLess(split, max(direct, 0.05) * 1.5)


if __name__ == '__main__':
    unittest.main()
