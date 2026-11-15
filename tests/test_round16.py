"""Round 16 : arcs et segments (biarcs)."""
import math
import pathlib
import random
import re
import tempfile
import unittest

from vectordrive.core import biarc, geom
from vectordrive.core.document import Document, Shape
from vectordrive.core.geom import Conic, Contour, Cubic, Line, Path
from vectordrive.io import registry


class TestBiarc(unittest.TestCase):
    def test_random_curves_within_tolerance(self):
        rnd = random.Random(11)
        for _ in range(40):
            pts = [(rnd.uniform(-40, 40), rnd.uniform(-40, 40)) for _ in range(4)]
            for s in (Cubic(*pts), Conic(*pts[:3], rnd.uniform(0.2, 3))):
                for tol in (0.05, 0.01):
                    segs = biarc.segment_to_arcs(s, tol)
                    self.assertLessEqual(biarc._deviation(s, segs, 1.0), tol * 1.05 + 5e-4)
                    self.assertLess(math.dist(segs[0].start, s.start), 1e-9)
                    self.assertLess(math.dist(segs[-1].end, s.end), 1e-9)
                    for a, b in zip(segs, segs[1:]):
                        self.assertLess(math.dist(a.end, b.start), 1e-9)
                    for x in segs:                                   # droites et arcs seulement
                        self.assertTrue(isinstance(x, Line) or x.circle_params())

    def test_tangent_continuity(self):
        s = Cubic((0, 0), (10, 30), (40, -20), (50, 10))
        segs = biarc.segment_to_arcs(s, 0.01)
        for a, b in zip(segs, segs[1:]):
            ta = biarc._tangents(a)[1]
            tb = biarc._tangents(b)[0]
            self.assertGreater(ta[0] * tb[0] + ta[1] * tb[1], math.cos(math.radians(2)))   # < 2°

    def test_inflection(self):
        s = Cubic((0, 0), (10, 20), (20, -20), (30, 0))
        ts = biarc._inflections(s)
        self.assertEqual(len(ts), 1)
        self.assertAlmostEqual(ts[0], 0.5, places=9)

    def test_ellipse_and_untouched(self):
        e = Path([geom.ellipse((0, 0), 30, 15)])
        q = biarc.to_arcs(e, 0.01)
        st = biarc.stats(q)
        self.assertEqual(st['autres'], 0)
        self.assertGreater(st['arcs'], 8)
        self.assertAlmostEqual(q.length(), e.length(), delta=0.05)
        circle_rect = Path([geom.circle((0, 0), 5), geom.rect(0, 0, 10, 10, 2)])
        same = biarc.to_arcs(circle_rect, 0.01)
        self.assertEqual(biarc.stats(same), biarc.stats(circle_rect))


if __name__ == '__main__':
    unittest.main()
