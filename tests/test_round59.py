"""Round 59 : tronquer, prolonger."""
import math
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom
from vectordrive.core import trim as T
from vectordrive.core.document import Shape
from vectordrive.core.geom import Contour, Cubic, Line, Path


def ends(path):
    return [(tuple(round(v, 9) for v in c.start), tuple(round(v, 9) for v in c.end)) for c in path.contours]


class TestSplit(unittest.TestCase):
    def test_conic_split_exact(self):
        arc = geom.arc_conics((0, 0), 10, 10, 0, 90)[0]
        for t in (0.1, 0.5, 0.83):
            a, b = T.split_at(arc, t)
            self.assertEqual(a.end, b.start)
            for s in (a, b):
                for u in (0.0, 0.3, 0.7, 1.0):
                    self.assertAlmostEqual(math.hypot(*s.point(u)), 10, places=10)
            self.assertAlmostEqual(math.dist(a.end, arc.point(t)), 0, places=12)

    def test_sub_segment(self):
        c = Cubic((0, 0), (0, 10), (10, 10), (10, 0))
        s = T.sub_segment(c, 0.25, 0.75)
        self.assertAlmostEqual(math.dist(s.start, c.point(0.25)), 0, places=12)
        self.assertAlmostEqual(math.dist(s.end, c.point(0.75)), 0, places=12)
        self.assertAlmostEqual(math.dist(s.point(0.5), c.point(0.5)), 0, places=12)


class TestTrim(unittest.TestCase):
    def test_line_between_two_cutters(self):
        h = Path([Contour([Line((0, 0), (30, 0))], False)])
        cut = [Line((10, -5), (10, 5)), Line((20, -5), (20, 5))]
        self.assertEqual(ends(T.trim(h, cut, (15, 0.1))), [((0, 0), (10, 0)), ((20, 0), (30, 0))])
        self.assertEqual(ends(T.trim(h, cut, (3, 0))), [((10, 0), (30, 0))])
        self.assertEqual(ends(T.trim(h, cut, (29, 0))), [((0, 0), (20, 0))])
        self.assertIsNone(T.trim(h, [], (15, 0)))                    # sans intersection : rien

    def test_closed_contours(self):
        circ = Path([geom.circle((0, 0), 10)])
        res = T.trim(circ, [Line((-20, 0), (20, 0))], (0, 10))
        self.assertEqual(len(res.contours), 1)
        c = res.contours[0]
        self.assertFalse(c.closed)
        self.assertAlmostEqual(c.length(), math.pi * 10, places=6)
        self.assertLess(max(y for _, y in c.flatten(1e-4)), 1e-9)
        res = T.trim(circ, Path([geom.circle((10, 0), 10)]).contours[0].segments, (-10, 0))
        self.assertAlmostEqual(res.contours[0].length(), 20 * math.pi / 3, places=6)
        sq = Path([geom.rect(0, 0, 10, 10)])
        res = T.trim(sq, [Line((5, -1), (5, 11))], (0, 5))                   # côté gauche retiré
        self.assertAlmostEqual(res.contours[0].length(), 20, places=9)

    def test_self_intersection(self):
        # boucle : le trait se recoupe lui-même en (5, 0)
        c = Contour([Line((0, 0), (10, 0)), Line((10, 0), (10, 5)), Line((10, 5), (5, 5)), Line((5, 5), (5, -5))], False)
        cuts = T.cut_params(c, [])
        self.assertEqual(len(cuts), 2)
        res = T.trim(Path([c]), [], (5, -4))
        self.assertAlmostEqual(res.contours[0].length(), 25, places=9)        # queue de 5 retirée (30 − 5)

    def test_other_contour_of_same_shape_cuts(self):
        p = Path([Contour([Line((0, 0), (30, 0))], False), Contour([Line((15, -5), (15, 5))], False)])
        res = T.trim(p, [], (25, 0))
        self.assertEqual(ends(res)[0], ((0, 0), (15, 0)))
        self.assertEqual(len(res.contours), 2)


class TestExtend(unittest.TestCase):
    def test_to_circle_and_curve_end(self):
        e = T.extend(Path([Contour([Line((0, 0), (5, 0))], False)]), Path([geom.circle((20, 0), 5)]).contours[0].segments, (5, 0))
        self.assertEqual(len(e.contours[0].segments), 1)
        self.assertAlmostEqual(e.contours[0].end[0], 15, places=9)
        arc = Contour(geom.arc_conics((0, 0), 10, 10, 180, 90), False)    # arc qui finit vers +x en (0, -10)
        e = T.extend(Path([arc]), [Line((20, -20), (20, 20))], (0, -10))
        self.assertIsInstance(e.contours[0].segments[-1], Line)
        self.assertAlmostEqual(e.contours[0].end[0], 20, places=9)
        self.assertAlmostEqual(e.contours[0].end[1], -10, places=9)
        self.assertIsNone(T.extend(Path([geom.circle((0, 0), 1)]), [Line((5, -5), (5, 5))], (1, 0)))


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_tools(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.resize(1200, 800)
            h = Shape(path=Path([Contour([Line((0, 0), (30, 0))], False)]))
            v1 = Shape(path=Path([Contour([Line((10, -5), (10, 5))], False)]))
            v2 = Shape(path=Path([Contour([Line((40, -5), (40, 5))], False)]))
            w._add_items([h, v1, v2])
            w.canvas.fit((0, 0, 100, 50))                     # vue de l'ancienne plaque par défaut
            w.set_tool('trim')
            dp = (20, 0)
            w.canvas.tool_obj.press(w.canvas.to_screen(*dp), dp, None)
            self.assertEqual(ends(h.path), [((0, 0), (10, 0))])
            w.set_tool('extend')
            dp = (8, 0)                                   # sur le trait seul (en 10 : le trait vertical)
            w.canvas.tool_obj.press(w.canvas.to_screen(*dp), dp, None)
            self.assertAlmostEqual(h.path.contours[0].end[0], 40, places=9)
            w.undo()
            self.assertAlmostEqual(next(it for it in w.canvas.doc.iter_items() if it.path.contours[0].start == (0, 0)).path.contours[0].end[0], 10)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
