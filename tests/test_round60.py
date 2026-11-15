"""Round 60 : poinçonner, rogner à une forme."""
import math
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom, pathops
from vectordrive.core import punch as P
from vectordrive.core.document import Shape, Text
from vectordrive.core.geom import Contour, Line, Path


class TestPunch(unittest.TestCase):
    def test_strokes(self):
        disc = Path([geom.circle((0, 0), 5)])
        h = Path([Contour([Line((-10, 0), (10, 0))], False)])
        out = P.cut(h, disc, False, False)
        self.assertEqual(len(out.contours), 2)
        self.assertAlmostEqual(out.length(), 10, places=9)
        self.assertAlmostEqual(P.cut(h, disc, False, True).length(), 10, places=9)

    def test_closed_stroke_rechained(self):
        sq = Path([geom.rect(0, 0, 10, 10)])
        out = P.cut(sq, Path([geom.circle((10, 10), 4)]), False, False)
        self.assertEqual(len(out.contours), 1)                     # un seul morceau, rechaîné par la fermeture
        self.assertAlmostEqual(out.length(), 32, places=9)
        self.assertFalse(out.contours[0].closed)
        out = P.cut(sq, Path([geom.circle((0, 5), 2)]), False, True)
        self.assertAlmostEqual(out.length(), 4, places=9)          # bout du côté gauche dans le disque

    def test_surfaces_and_unchanged(self):
        sq = Path([geom.rect(0, 0, 10, 10)])
        a = pathops.area(P.cut(sq, Path([geom.circle((10, 10), 4)]), True, False))
        self.assertAlmostEqual(a, 100 - 4 * math.pi, places=6)
        self.assertIsNone(P.cut(Path([geom.circle((0, 0), 1)]), Path([geom.circle((0, 0), 5)]), False, True))
        self.assertIsNone(P.cut(Path([geom.circle((50, 0), 1)]), Path([geom.circle((0, 0), 5)]), False, False))
        self.assertEqual(P.cut(Path([geom.circle((50, 0), 1)]), Path([geom.circle((0, 0), 5)]), False, True).contours, [])

    def test_star_clip(self):
        st = Path([geom.star((0, 0), 12, 5, 5)])
        out = P.cut(Path([geom.circle((0, 0), 8)]), st, False, True)
        self.assertEqual(len(out.contours), 5)                     # un arc par branche
        for c in out.contours:
            for q in c.flatten(0.01):
                self.assertAlmostEqual(math.hypot(*q), 8, places=6)

    def test_inside(self):
        ring = P._polys(Path([geom.circle((0, 0), 10), geom.circle((0, 0), 5)]))
        self.assertTrue(P.inside((7, 0), ring))
        self.assertFalse(P.inside((1, 0), ring))
        self.assertFalse(P.inside((11, 0), ring))


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_punch_and_clip_with_shape(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            h = Shape(path=Path([Contour([Line((-10, 0), (10, 0))], False)]))
            t = Text(text='O', font='Arial', size=10)
            from vectordrive.core import text as TX
            t.outline = TX.outline_for(t)
            disc = Shape(path=Path([geom.circle((0, 0), 5)]))
            w._add_items([h, t, disc])
            w.canvas.select([h, t, disc])
            w.punch_items()
            items = list(w.canvas.doc.iter_items())
            self.assertIn(disc, items)                              # le poinçon reste
            line = next(i for i in items if isinstance(i, Shape) and not i.filled and i is not disc)
            self.assertAlmostEqual(line.path.length(), 10, places=9)
            w.undo()                                                # l'annulation rend des copies
            shapes = [i for i in w.canvas.doc.iter_items() if isinstance(i, Shape)]
            h = next(i for i in shapes if not i.path.contours[0].closed)
            disc = next(i for i in shapes if i.path.contours[0].closed)
            self.assertAlmostEqual(h.path.length(), 20, places=9)
            w.canvas.select([h, disc])
            # rogner : forme exacte du disque, pas sa boîte
            w.clip_items()
            line = next(i for i in w.canvas.doc.iter_items() if isinstance(i, Shape) and i is not disc)
            self.assertAlmostEqual(line.path.length(), 10, places=9)
            diamond = Shape(path=Path([geom.polygon((0, 0), 5, 4, 0)]))
            w._add_items([diamond])
            w.canvas.select([line, diamond])
            w.clip_items()
            line = next(i for i in w.canvas.doc.iter_items() if isinstance(i, Shape) and i not in (disc, diamond))
            self.assertAlmostEqual(line.path.length(), 10, places=9)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
