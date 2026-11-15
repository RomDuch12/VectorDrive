"""Round 15 : cadrans, multicopie."""
import math
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import dial as DL
from vectordrive.core import duplicate, fonts, geom
from vectordrive.core.document import Plate, Shape
from vectordrive.core.geom import Path


class TestDial(unittest.TestCase):
    def test_ticks(self):
        s = DL.DialSpec(start=-135, sweep=270, divisions=50, major_every=10, medium_every=5)
        t = DL.tick_angles(s)
        self.assertEqual(len(t), 51)                                   # secteur : extrémités incluses
        self.assertEqual([k for _a, k in t].count('major'), 6)
        self.assertEqual([k for _a, k in t].count('medium'), 5)
        full = DL.DialSpec(start=0, sweep=360, divisions=60, major_every=5, medium_every=0)
        self.assertEqual(len(DL.tick_angles(full)), 60)                 # cercle : pas de doublon à 360°

    def test_geometry(self):
        s = DL.DialSpec(radius=40, start=0, sweep=360, divisions=4, major_every=1, medium_every=0,
                        major_len=5, text_height=0)
        g = DL.build(s, (10, 20))
        ticks = g.children[0].path.contours
        ends = sorted((round(c.segments[0].end[0], 9), round(c.segments[0].end[1], 9)) for c in ticks)
        self.assertEqual(ends, sorted([(10.0, 60.0), (50.0, 20.0), (10.0, -20.0), (-30.0, 20.0)]))
        for c in ticks:
            self.assertAlmostEqual(c.length(), 5, places=9)
        self.assertAlmostEqual(g.children[1].path.length(), 2 * math.pi * 40, places=6)
        self.assertEqual(g.extra['dial']['center'], [10, 20])

    @unittest.skipUnless(fonts.find_font('Arial'), 'Arial absente')
    def test_labels(self):
        s = DL.DialSpec(radius=40, start=-90, sweep=180, divisions=10, major_every=5, medium_every=0,
                        value_from=0, value_to=10, text_height=4)
        g = DL.build(s)
        labels = g.children[2]
        bb = labels.bbox()
        # « 0 » à gauche, « 5 » en haut, « 10 » à droite, sous les graduations longues
        self.assertLess(bb[0], -25)
        self.assertGreater(bb[2], 25)
        self.assertLess(bb[3], 40 - 6 + 0.1)

    def test_thick_ticks(self):
        g = DL.build(DL.DialSpec(divisions=10, major_every=5, tick_width=0.5, text_height=0))
        self.assertTrue(g.children[0].filled)
        self.assertTrue(all(c.closed for c in g.children[0].path.contours))


class TestFill(unittest.TestCase):
    def test_layout(self):
        lay = duplicate.fill_layout(30, 10, (0, 0, 100, 50), 2, 2, 3)
        self.assertEqual((lay['cols'], lay['rows'], lay['rotated']), (3, 3, False))
        self.assertEqual(lay['origin'], (3.0, 8.0))
        lay = duplicate.fill_layout(30, 10, (0, 0, 50, 100), 2, 2, 3, allow_rotate=True)
        self.assertEqual((lay['cols'] * lay['rows'], lay['rotated']), (9, True))
        self.assertEqual(duplicate.fill_layout(200, 10, (0, 0, 100, 50), 2, 2, 3)['cols'], 0)

    def test_copies_inside_plate(self):
        sq = Shape(path=Path([geom.rect(5, 5, 30, 10)]))
        box = (0, 0, 50, 100)
        out, lay = duplicate.fill([sq], box, 2, 2, 3, allow_rotate=True)
        self.assertEqual(len(out), 9)
        for o in out:
            b = o.bbox()
            self.assertGreaterEqual(b[0], 3 - 1e-9)
            self.assertLessEqual(b[2], 47 + 1e-9)
            self.assertAlmostEqual(b[2] - b[0], 10)                    # tourné
        boxes = sorted(o.bbox() for o in out)
        for a, b in zip(boxes, boxes[1:]):                              # pas de chevauchement
            self.assertFalse(a[0] < b[2] - 1e-9 and b[0] < a[2] - 1e-9 and a[1] < b[3] - 1e-9 and b[1] < a[3] - 1e-9)

    def test_window(self):
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            d = w.canvas.doc
            d.plate = Plate(100, 50)
            circ = d.add(Shape(path=Path([geom.circle((20, 30), 12)])))
            w.canvas.select([circ])
            (cx, cy), r = w._circle_of_selection()
            self.assertAlmostEqual(cx, 20, places=9)
            self.assertAlmostEqual(cy, 30, places=9)
            self.assertAlmostEqual(r, 12, places=9)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
