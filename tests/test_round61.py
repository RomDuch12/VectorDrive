"""Round 61 : courbes parallèles, trait double, gomme à boucles."""
import math
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom
from vectordrive.core import parallel as PA
from vectordrive.core.document import Shape
from vectordrive.core.geom import Contour, Cubic, Line, Path


class TestParallel(unittest.TestCase):
    def test_circle_is_exact(self):
        for d in (1, -3, 9.5):
            [c] = PA.parallel(geom.circle((2, 3), 10), d)
            self.assertTrue(c.closed)
            self.assertTrue(all(isinstance(s, geom.Conic) for s in c.segments))
            for q in c.flatten(1e-5):
                self.assertAlmostEqual(math.hypot(q[0] - 2, q[1] - 3), 10 - d, places=9)
        self.assertEqual(PA.parallel(geom.circle((0, 0), 1), 2), [])              # disparaît

    def test_square_joins(self):
        sq = geom.rect(0, 0, 10, 10)
        [out] = PA.parallel(sq, -1)                          # dehors (carré parcouru dans le sens trigo)
        self.assertAlmostEqual(out.length(), 40 + 2 * math.pi, places=9)
        [inn] = PA.parallel(sq, 1)
        self.assertAlmostEqual(inn.length(), 32, places=9)
        self.assertEqual(sorted(inn.nodes())[:1], [(1.0, 1.0)])

    def test_cubic_accuracy(self):
        S = Contour([Cubic((0, 0), (10, 20), (20, -20), (30, 0))], False)
        [c] = PA.parallel(S, 1)
        src = S.segments[0]
        pts = [src.point(k / 20000) for k in range(20001)]
        err = 0.0
        for q in c.flatten(1e-3)[::5]:
            d = min(math.hypot(q[0] - p[0], q[1] - p[1]) for p in pts)
            err = max(err, abs(d - 1))
        self.assertLess(err, 2e-4)

    def test_loops_removed(self):
        # U étroit : décalé vers l'intérieur de plus de la demi-largeur, les deux branches se croisent
        u = Contour([Line((0, 0), (20, 0)), Line((20, 0), (20, 2)), Line((20, 2), (0, 2))], False)
        from vectordrive.core.trim import self_crossings
        self.assertEqual(PA.parallel(u, 1.5), [])                       # U trop étroit : rien dedans
        [inner] = PA.parallel(u, 0.5)
        self.assertAlmostEqual(inner.length(), 19.5 + 1 + 19.5, places=9)
        [outer] = PA.parallel(u, -1.5)
        self.assertFalse(self_crossings(outer))
        # boucle d'une courbure trop forte : gommée
        tight = Contour([Line((0, 0), (10, 0)), *geom.arc_conics((10, 1), 1, 1, -90, 180), Line((10, 2), (0, 2))], False)
        res = PA.parallel(tight, 3)
        for c in res:
            self.assertFalse(self_crossings(c))

    def test_remove_loops_direct(self):
        loop = Contour([Line((0, 0), (10, 0)), Line((10, 0), (10, 5)), Line((10, 5), (5, 5)), Line((5, 5), (5, -5))], False)
        out = PA.remove_loops(loop)
        self.assertAlmostEqual(out.length(), 10, places=9)               # (0,0)→(5,0)→(5,−5)
        self.assertEqual(out.end, (5, -5))
        self.assertAlmostEqual(PA.remove_loops(loop, max_len=5).length(), 30, places=9)   # boucle de 15 gardée


class TestConicPieces(unittest.TestCase):
    def test_sub_arcs_meet_exactly(self):
        from vectordrive.core.trim import split_at, sub_segment
        arc = geom.arc_conics((0, 0), 10, 10, 10, 80)[0]
        a, b = sub_segment(arc, 0.2, 0.7), sub_segment(arc, 0.7, 0.9)
        self.assertLess(math.dist(a.end, b.start), 1e-12)               # paramètre non linéaire après découpe
        self.assertLess(math.dist(a.end, arc.point(0.7)), 1e-12)
        self.assertLess(math.dist(split_at(arc, 0.7)[0].end, a.end), 1e-12)
        for u in (0.0, 0.4, 1.0):
            self.assertAlmostEqual(math.hypot(*a.point(u)), 10, places=12)

    def test_specks_removed(self):
        c = Contour([Line((0, 0), (10, 0)), Line((10, 0), (10, 1e-4)), Line((10, 1e-4), (10, 10)),
                     Line((10, 10), (0, 10)), Line((0, 10), (0, 0))], True)
        [out] = PA.parallel(c, 1)
        self.assertTrue(out.closed)
        self.assertAlmostEqual(out.length(), 32, places=3)


class TestDoubleLine(unittest.TestCase):
    def test_ends(self):
        pl = Path([Contour([Line((0, 0), (10, 0)), Line((10, 0), (10, 10))], False)])
        lens = {e: [round(c.length(), 6) for c in PA.double_line(pl, 2, e).contours] for e in ('open', 'butt', 'round')}
        self.assertEqual(sorted(lens['open']), [18.0, round(20 + math.pi / 2, 6)])
        self.assertEqual(lens['butt'], [round(18 + 20 + math.pi / 2 + 4, 6)])
        self.assertEqual(lens['round'], [round(18 + 20 + math.pi / 2 + 2 * math.pi, 6)])
        closed = PA.double_line(Path([geom.circle((0, 0), 5)]), 2, 'round')
        self.assertEqual(len(closed.contours), 2)


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
            s = Shape(path=Path([Contour([Line((0, 0), (10, 0))], False)]))
            w._add_items([s])
            w.canvas.select([s])

            @dataclass
            class Spec:
                width: float = 2.0
                ends: str = 'butt'
            w._double_line_params = lambda: Spec()
            w.double_line_dialog()
            got = w.canvas.selection[0]
            self.assertAlmostEqual(got.path.length(), 24, places=9)
            self.assertTrue(got.path.contours[0].closed)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
