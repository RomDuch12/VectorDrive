"""Round 64 : Mode Point — droite / courbe, lisse / symétrique, alignements."""
import math
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom
from vectordrive.core import nodes as N
from vectordrive.core.document import Shape
from vectordrive.core.geom import Conic, Contour, Cubic, Line, Path


def cross(u, v):
    return u[0] * v[1] - u[1] * v[0]


class TestNodes(unittest.TestCase):
    def test_segments_between(self):
        sq = geom.rect(0, 0, 10, 10)                     # fermé, 4 segments ; nœud k = fin du segment k
        self.assertEqual(N.segments_between(sq, {0, 1}), [1])
        self.assertEqual(N.segments_between(sq, {3, 0}), [0])
        self.assertEqual(N.segments_between(sq, {2}), [3])
        op = Contour([Line((0, 0), (1, 0)), Line((1, 0), (2, 0))], False)
        self.assertEqual(N.segments_between(op, {2}), [1])               # bout : segment qui arrive

    def test_line_curve_roundtrip(self):
        sq = geom.rect(0, 0, 10, 10)
        c = N.to_curves(sq, [0, 1])
        self.assertIsInstance(c.segments[0], Cubic)
        self.assertAlmostEqual(c.length(), 40, places=9)                 # même tracé
        back = N.to_lines(c, [0, 1])
        self.assertEqual(back.segments, sq.segments)
        arc = Contour(geom.arc_conics((0, 0), 10, 10, 0, 90), False)
        cu = N.to_curves(arc, [0])
        self.assertIsInstance(cu.segments[0], Cubic)
        self.assertLess(max(abs(math.hypot(*q) - 10) for q in cu.flatten(1e-4)), 0.003)
        quad = Contour([Conic((0, 0), (5, 10), (10, 0), 1.0)], False)
        e = N.to_curves(quad, [0]).segments[0]
        for t in (0.2, 0.5, 0.9):                                        # élévation exacte
            self.assertAlmostEqual(math.dist(e.point(t), quad.segments[0].point(t)), 0, places=12)

    def test_smooth_and_symmetric(self):
        c = Contour([Line((0, 0), (10, 0)), Line((10, 0), (10, 10))], False)
        s = N.smooth_node(c, 1)
        a, b = s.segments
        u = (a.p3[0] - a.p2[0], a.p3[1] - a.p2[1])
        v = (b.p1[0] - b.p0[0], b.p1[1] - b.p0[1])
        self.assertAlmostEqual(cross(u, v), 0, places=9)
        self.assertGreater(u[0] * v[0] + u[1] * v[1], 0)
        self.assertEqual((a.p0, b.p3), ((0, 0), (10, 10)))
        y = N.smooth_node(Contour([Line((0, 0), (10, 0)), Line((10, 0), (30, 10))], False), 1, symmetric=True)
        a, b = y.segments
        self.assertAlmostEqual(math.dist(a.p2, a.p3), math.dist(b.p0, b.p1), places=9)
        self.assertIs(N.smooth_node(c, 0), c)                             # bout d'un contour ouvert

    def test_align(self):
        sq = geom.rect(0, 0, 10, 10)
        out = N.align_nodes([sq], {(0, 0), (0, 1)}, 'v')                  # nœuds (10,0) et (10,10) : déjà alignés en x
        self.assertEqual(out[0].segments, sq.segments)
        out = N.align_nodes([sq], {(0, 1), (0, 2)}, 'h')                  # (10,10) et (0,10) : même y déjà
        out = N.align_nodes([sq], {(0, 0), (0, 2)}, 'h')                  # (10,0) et (0,10) → y = 5
        ys = [N.node_point(out[0], k)[1] for k in (0, 2)]
        self.assertEqual(ys, [5, 5])


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_node_commands(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            sh = Shape(path=Path([geom.rect(0, 0, 10, 10)]))
            w._add_items([sh])
            w.canvas.select([sh])
            w.set_tool('node')
            tool = w.canvas.tool_obj
            tool.sel = {(0, 0), (0, 1)}
            w.node_edit('node_curve')
            self.assertIsInstance(sh.path.contours[0].segments[1], Cubic)
            tool.sel = {(0, 1)}
            w.node_edit('node_smooth')
            tool.sel = {(0, 0), (0, 2)}
            w.node_edit('node_align_h')
            self.assertAlmostEqual(N.node_point(sh.path.contours[0], 0)[1], 5)
            w.undo()
            w.undo()
            w.undo()
            item = next(w.canvas.doc.iter_items())
            self.assertTrue(all(isinstance(s, Line) for s in item.path.contours[0].segments))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
