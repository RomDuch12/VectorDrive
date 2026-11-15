"""Round 17 : rogner (traits coupés, surfaces intersectées)."""
import math
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import clip as CL
from vectordrive.core import geom
from vectordrive.core.document import Group, Plate, Shape
from vectordrive.core.geom import Conic, Contour, Cubic, Line, Path

BOX = (0, 0, 10, 10)


class TestCrossings(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(CL.crossings(Line((-5, 5), (15, 5)), BOX), [0.25, 0.75])
        c = Cubic((-5, 5), (5, 20), (5, -10), (15, 5))
        for t in CL.crossings(c, BOX):
            x, y = c.point(t)
            self.assertTrue(min(abs(x), abs(x - 10), abs(y), abs(y - 10)) < 1e-9)
        arc = geom.circle((10, 5), 4).segments
        ts = [t for s in arc for t in CL.crossings(s, BOX)]
        self.assertEqual(len(ts), 0)            # les jonctions des quarts tombent sur x = 10 (bornes exclues)


class TestClip(unittest.TestCase):
    def test_strokes(self):
        p = CL.clip_strokes(Path([geom.circle((10, 5), 4)]), BOX)
        self.assertAlmostEqual(p.length(), 4 * math.pi, places=9)
        self.assertTrue(all(not c.closed for c in p.contours))
        inside = Path([geom.rect(2, 2, 3, 3)])
        self.assertIs(CL.clip_strokes(inside, BOX).contours[0], inside.contours[0])
        out = CL.clip_strokes(Path([geom.rect(20, 20, 3, 3)]), BOX)
        self.assertEqual(out.contours, [])

    def test_closed_contour_rejoined(self):
        # carré qui déborde à droite, départ à l'intérieur : un seul morceau
        sq = geom.polyline([(5, 2), (12, 2), (12, 8), (5, 8)], closed=True)
        p = CL.clip_strokes(Path([sq]), BOX)
        self.assertEqual(len(p.contours), 1)
        self.assertAlmostEqual(p.length(), 5 + 6 + 5, places=9)

    def test_regions(self):
        p = CL.clip_regions(Path([geom.circle((10, 5), 4)]), BOX)
        self.assertAlmostEqual(p.length(), 4 * math.pi + 8, delta=0.01)

    def test_window(self):
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            d = w.canvas.doc
            d.plate = Plate(10, 10)
            d.add(Shape(path=Path([geom.circle((10, 5), 4)])))                  # trait
            d.add(Shape(path=Path([geom.circle((0, 5), 4)]), filled=True))      # surface
            d.add(Shape(path=Path([geom.rect(30, 30, 2, 2)])))                  # dehors
            d.add(Group(children=[Shape(path=Path([geom.rect(2, 2, 2, 2)]))]))  # dedans
            w.canvas.select([])
            w.clip_items()
            items = d.layers[0].items
            self.assertEqual(len(items), 3)
            self.assertAlmostEqual(items[0].path.length(), 4 * math.pi, places=6)
            self.assertAlmostEqual(items[1].path.length(), 4 * math.pi + 8, delta=0.01)
            w.undo()
            self.assertEqual(len(w.canvas.doc.layers[0].items), 4)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
