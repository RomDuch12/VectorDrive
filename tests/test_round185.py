"""Round 185 : retraits et simplifications partie par partie (mêmes régions), rapides."""
import math
import os
import random
import tempfile
import time
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def scene(n, seed, spread=(200, 120)):
    rnd = random.Random(seed)
    paths = []
    for _ in range(n):
        cx, cy, r = rnd.uniform(0, spread[0]), rnd.uniform(0, spread[1]), rnd.uniform(0.8, 3)
        paths.append(geom.Path([geom.circle((cx, cy), r)]))
        if rnd.random() < 0.3:
            paths.append(geom.Path([geom.circle((cx, cy), r / 3)]))               # trou (lettre)
        if rnd.random() < 0.2:
            paths.append(geom.Path([geom.rect(cx - r, cy - r / 4, 2 * r, r / 2)]))  # recouvrement
    return paths


def doc_of(paths):
    d = Document()
    d.plate = None
    for p in paths:
        d.add(Shape(path=p, tool=0))
    return d


class TestErode(unittest.TestCase):
    def test_same_as_buffer(self):
        for seed in range(3):
            reg = S.region(scene(200, seed), 0.01)
            self.assertGreater(len(reg.geoms), S.MANY_PARTS)
            for d in (0.0, 0.3, 1.1, 5.0):
                new, old = S.erode(reg, d, 6), reg.buffer(-d, quad_segs=6)
                self.assertLess(new.symmetric_difference(old).area, 1e-6, (seed, d))
                self.assertEqual(len(getattr(new, 'geoms', [new])) if not new.is_empty else 0,
                                 len(getattr(old, 'geoms', [old])) if not old.is_empty else 0)
                self.assertTrue(new.is_valid)
        self.assertTrue(S.erode(reg, 50.0, 6).is_empty)

    def test_small_unchanged(self):
        reg = S.region(scene(10, 4), 0.01)
        self.assertTrue(S.erode(reg, 0.5, 6).equals_exact(reg.buffer(-0.5, quad_segs=6), 0))
        self.assertTrue(S.simplify_parts(reg, 0.05).equals_exact(reg.simplify(0.05), 0))

    def test_simplify_parts(self):
        reg = S.region(scene(200, 7), 0.01)
        new, old = S.simplify_parts(reg, 0.05), reg.simplify(0.05)
        self.assertEqual(len(new.geoms), len(reg.geoms))
        self.assertTrue(all(p.is_valid for p in new.geoms))                    # chaque partie (anneaux)
        self.assertEqual(new.geom_type, 'GeometryCollection')                   # pas une région
        self.assertLess(abs(new.area - old.area), 0.05 * reg.length)
        self.assertLessEqual(new.hausdorff_distance(reg), old.hausdorff_distance(reg) + 1e-9)
        self.assertEqual(len(S.rings_of(new, True)), len(S.rings_of(old, True)))

    def test_within(self):
        from shapely.geometry import LineString
        reg = S.region(scene(200, 3), 0.01)
        inside = S.within_test(reg)
        rnd = random.Random(2)
        for _ in range(400):
            x, y = rnd.uniform(0, 200), rnd.uniform(0, 120)
            seg = LineString([(x, y), (x + rnd.uniform(-4, 4), y + rnd.uniform(-4, 4))])
            self.assertEqual(inside(seg), reg.contains(seg))

    def test_toolpaths_fast_and_inside(self):
        rnd = random.Random(5)
        paths = [geom.Path([geom.circle((rnd.uniform(0, 300), rnd.uniform(0, 200)), rnd.uniform(0.8, 2.5))])
                 for _ in range(1500)]
        d = doc_of(paths)
        s = model.CamSetup()
        v = model.CamTool(name='V', kind='conique', diameter=6.0, angle=60.0, tip=0.1, feed=1000.0)
        f = model.CamTool(name='F', kind='plate', diameter=1.0, feed=1000.0, stepover=0.4, step_down=1.0)
        s.tools = [v, f]
        reg = S.region(paths, s.tolerance)
        for tool, kind in ((v, 'vcarve'), (f, 'poche')):
            op = model.Operation(tool_id=tool.id, kind=kind, depth=1.0)
            s.operations = [op]
            t = time.perf_counter()
            tp = S.compute(d, s, op)
            self.assertLess(time.perf_counter() - t, 25.0, kind)
            feeds = [m for m in tp.moves if m.kind == 'feed']
            self.assertGreater(len(feeds), 10000, kind)
            from shapely.geometry import Point
            grown = reg.buffer(0.01)
            sample = feeds[::max(1, len(feeds) // 300)]
            self.assertTrue(all(grown.contains(Point(m.x, m.y)) for m in sample), kind)


if __name__ == '__main__':
    unittest.main()
