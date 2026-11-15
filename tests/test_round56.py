"""Round 56 : approximation et segmentation."""
import math
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import fitcurve as F
from vectordrive.core import geom
from vectordrive.core.document import Shape
from vectordrive.core.geom import Contour, Cubic, Line, Path


def kinds(p):
    out = {}
    for c in p.contours:
        for s in c.segments:
            out[type(s).__name__] = out.get(type(s).__name__, 0) + 1
    return out


class TestApproximate(unittest.TestCase):
    def test_dense_circle(self):
        circ = Path([geom.polyline(geom.circle((0, 0), 20).flatten(0.001), closed=True)])
        for tol in (0.1, 0.01):
            a = F.approximate(circ, tol)
            self.assertTrue(a.contours[0].closed)
            self.assertEqual(set(kinds(a)), {'Cubic'})
            self.assertLess(a.segment_count(), 20)
            dev = max(abs(math.hypot(*q) - 20) for q in a.contours[0].flatten(1e-4))
            self.assertLess(dev, tol)
            segs = a.contours[0].segments                     # lisse : raccords tangents, y compris à la fermeture
            for s1, s2 in zip(segs, segs[1:] + segs[:1]):
                t1 = (s1.p3[0] - s1.p2[0], s1.p3[1] - s1.p2[1])
                t2 = (s2.p1[0] - s2.p0[0], s2.p1[1] - s2.p0[1])
                self.assertLess(abs(t1[0] * t2[1] - t1[1] * t2[0]) / (math.hypot(*t1) * math.hypot(*t2)), 1e-6)

    def test_corners_and_straight_parts(self):
        pts = []
        for (x0, y0), (x1, y1) in zip([(0, 0), (30, 0), (30, 10), (0, 10)], [(30, 0), (30, 10), (0, 10), (0, 0)]):
            pts += [(x0 + (x1 - x0) * k / 50, y0 + (y1 - y0) * k / 50) for k in range(50)]
        a = F.approximate(Path([geom.polyline(pts, closed=True)]), 0.01)
        self.assertEqual(kinds(a), {'Line': 4})
        ob = Contour([Line((0, -5), (20, -5)), *geom.arc_conics((20, 0), 5, 5, -90, 180),
                      Line((20, 5), (0, 5)), *geom.arc_conics((0, 0), 5, 5, 90, 180)], True)
        a = F.approximate(Path([geom.polyline(ob.flatten(0.002), closed=True)]), 0.01)
        self.assertEqual(kinds(a).get('Line'), 2)

    def test_open_and_lines_only(self):
        pts = [(x / 10, math.sin(x / 10)) for x in range(0, 63)]
        a = F.approximate(Path([geom.polyline(pts)]), 0.002)
        c = a.contours[0]
        self.assertFalse(c.closed)
        self.assertEqual(c.start, (0.0, 0.0))
        self.assertAlmostEqual(c.end[0], 6.2)
        mixed = Contour([Line((0, 0), (1, 0.01)), Line((1, 0.01), (2, 0.04)), Line((2, 0.04), (3, 0.09)),
                         Cubic((3, 0.09), (4, 0), (5, 1), (6, 0))], False)
        b = F.approximate(Path([mixed]), 0.01, curves=False)
        self.assertIs(b.contours[0].segments[-1], mixed.segments[-1])     # courbe existante gardée telle quelle


class TestSegment(unittest.TestCase):
    def test_segment(self):
        s = F.segment(Path([geom.circle((0, 0), 10)]), 0.01, 0.3)
        segs = s.contours[0].segments
        self.assertTrue(all(isinstance(x, Line) for x in segs))
        self.assertTrue(s.contours[0].closed)
        self.assertLessEqual(max(x.length() for x in segs), 0.3 + 1e-9)
        dev = max(abs(math.hypot(*x.point(0.5)) - 10) for x in segs)
        self.assertLess(dev, 0.01)
        sq = F.segment(Path([geom.rect(0, 0, 10, 10)]), 0.01, 2.5)
        self.assertEqual(sq.segment_count(), 4)
        sq = F.segment(Path([geom.rect(0, 0, 10, 10)]), 0.01, 2.5, lines_too=True)
        self.assertEqual(sq.segment_count(), 16)


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_commands(self):
        from dataclasses import dataclass
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            dense = Shape(path=Path([geom.polyline(geom.circle((0, 0), 20).flatten(0.001), closed=True)]))
            w._add_items([dense])
            w.canvas.select([dense])

            @dataclass
            class A:
                tolerance: float = 0.01
                corner: float = 35.0
                curves: bool = True
            w._fit_params = lambda kind: A()
            w.approximate_dialog()
            got = w.canvas.selection[0]
            self.assertLess(got.path.segment_count(), 20)

            @dataclass
            class S:
                tolerance: float = 0.01
                max_len: float = 1.0
                lines_too: bool = False
            w._fit_params = lambda kind: S()
            w.segment_dialog()
            self.assertTrue(all(isinstance(x, Line) for x in w.canvas.selection[0].path.contours[0].segments))
            w.undo()
            w.undo()
            self.assertGreater(next(w.canvas.doc.iter_items()).path.segment_count(), 500)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
