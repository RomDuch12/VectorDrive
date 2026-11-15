"""Round 184 : lignes du remplissage laser par balayage (mêmes segments, rapide)."""
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


def reference(reg, angle, pitch):
    """L'ancien calcul (une intersection par rangée), pour comparer."""
    from shapely import affinity
    from shapely.geometry import LineString
    rot = affinity.rotate(reg, -angle, origin=(0, 0))
    x0, y0, x1, y1 = rot.bounds
    n = int((y1 - y0) / pitch)
    rows = []
    for k in range(n + 1):
        y = y0 + (k + 0.5) * pitch
        if y >= y1:
            break
        cut = rot.intersection(LineString([(x0 - 1, y), (x1 + 1, y)]))
        segs = [list(g.coords) for g in getattr(cut, 'geoms', [cut]) if g.geom_type == 'LineString' and not g.is_empty]
        segs.sort(key=lambda c: min(c[0][0], c[-1][0]))
        segs = [c if c[0][0] <= c[-1][0] else c[::-1] for c in segs]
        if len(rows) % 2:
            segs = [c[::-1] for c in reversed(segs)]
        rows.append(segs)
    ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    return [[[(x * ca - y * sa, x * sa + y * ca) for x, y in c] for c in segs] for segs in rows]


def scene(seed):
    rnd = random.Random(seed)
    paths = []
    for _ in range(40):
        cx, cy, r = rnd.uniform(0, 80), rnd.uniform(0, 50), rnd.uniform(1, 6)
        paths.append(geom.Path([geom.circle((cx, cy), r)]))
        if rnd.random() < 0.4:                                                  # trou (lettre)
            paths.append(geom.Path([geom.circle((cx + r / 5, cy), r / 2)]))
    paths.append(geom.Path([geom.rect(-10, -10, 30, 20)]))
    paths.append(geom.Path([geom.rect(-5, -5, 10, 8)]))
    return S.region(paths, 0.01)


def ends(rows):
    return [[(c[0], c[-1]) for c in segs] for segs in rows]


class TestHatch(unittest.TestCase):
    def assertSameRows(self, new, old):
        self.assertEqual(len(new), len(old))
        for rn, ro in zip(ends(new), ends(old)):
            self.assertEqual(len(rn), len(ro))
            for (a, b), (c, d) in zip(rn, ro):
                for p, q in ((a, c), (b, d)):
                    self.assertLess(math.dist(p, q), 1e-7)

    def test_same_segments(self):
        for seed in range(3):
            reg = scene(seed)
            for angle in (0.0, 30.0, 45.0, 90.0, 117.5):
                for pitch in (0.37, 0.11):
                    self.assertSameRows(S._hatch_rows(reg, angle, pitch), reference(reg, angle, pitch))

    def test_polygon_shapes(self):
        from shapely.geometry import MultiPolygon, Polygon
        sq = Polygon([(0, 0), (20, 0), (20, 20), (0, 20)], [[(5, 5), (15, 5), (10, 12)]])
        tri = Polygon([(30, 0), (50, 3), (35, 17)])
        for reg in (sq, MultiPolygon([sq, tri])):
            for angle in (0.0, 10.0, 63.0):
                self.assertSameRows(S._hatch_rows(reg, angle, 0.3), reference(reg, angle, 0.3))
        self.assertEqual(S._hatch_rows(Polygon(), 0.0, 0.3), [])
        self.assertIsNone(S._hatch_rows(sq, 0.0, 1e-5))                                # pas trop fin

    def test_speed(self):
        rnd = random.Random(5)
        paths = [geom.Path([geom.circle((rnd.uniform(0, 300), rnd.uniform(0, 200)), 1.2)]) for _ in range(3000)]
        reg = S.region(paths, 0.01)
        t = time.perf_counter()
        rows = S._hatch_rows(reg, 30.0, 0.1)
        self.assertLess(time.perf_counter() - t, 8.0)
        self.assertGreater(sum(len(r) for r in rows), 1000)


if __name__ == '__main__':
    unittest.main()
