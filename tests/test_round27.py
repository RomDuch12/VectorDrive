"""Round 27 : imbrication sur la plaque."""
import os
import random
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom
from vectordrive.core import nesting as N
from vectordrive.core.document import Plate, Shape, Text
from vectordrive.core.geom import Path


def rect(x, y, w, h):
    return Shape(path=Path([geom.rect(x, y, w, h)]))


def overlaps(boxes, gap):
    n = 0
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            if (a[0] < b[2] + gap - 1e-6 and b[0] < a[2] + gap - 1e-6
                    and a[1] < b[3] + gap - 1e-6 and b[1] < a[3] + gap - 1e-6):
                n += 1
    return n


class TestSkyline(unittest.TestCase):
    def test_fill_exactly(self):
        sk = N.Skyline(10, 10)
        for _ in range(4):
            top, x, i, y = sk.find(5, 5)
            sk.place(i, y, 5, 5)
        self.assertIsNone(sk.find(5, 5))
        self.assertEqual(sk.segs, [[0.0, 10.0, 10.0]])


class TestNest(unittest.TestCase):
    def test_random_parts(self):
        rnd = random.Random(7)
        items = [rect(rnd.uniform(-80, 80), rnd.uniform(-80, 80), rnd.uniform(4, 70), rnd.uniform(4, 35))
                 for _ in range(80)]
        pl = Plate(300, 200, x=10, y=20)
        spec = N.NestSpec(margin=3, gap=2)
        r = N.nest(items, pl, spec)
        self.assertEqual(len(r.placed), 80)
        self.assertEqual(r.unplaced, [])
        boxes = [o.bbox() for o in r.items()]
        self.assertEqual(overlaps(boxes, 2.0), 0)
        for b in boxes:
            k = round((b[0] - pl.x) // (pl.width + N.PLATE_GAP))
            x0 = pl.x + k * (pl.width + N.PLATE_GAP)
            self.assertGreaterEqual(b[0], x0 + 3 - 1e-6)
            self.assertLessEqual(b[2], x0 + pl.width - 3 + 1e-6)
            self.assertGreaterEqual(b[1], pl.y + 3 - 1e-6)
            self.assertLessEqual(b[3], pl.y + pl.height - 3 + 1e-6)
        # sizes kept (rotation swaps them)
        sizes = sorted(sorted((round(b[2] - b[0], 6), round(b[3] - b[1], 6))) for b in boxes)
        orig = sorted(sorted((round(it.bbox()[2] - it.bbox()[0], 6), round(it.bbox()[3] - it.bbox()[1], 6)))
                      for it in items)
        self.assertEqual(sizes, orig)

    def test_rotation_needed(self):
        pl = Plate(50, 100)
        r = N.nest([rect(0, 0, 90, 20)], pl, N.NestSpec(margin=2, gap=0))
        self.assertEqual(r.rotated, 1)
        b = r.items()[0].bbox()
        self.assertAlmostEqual(b[2] - b[0], 20)
        self.assertAlmostEqual(b[0], 2)
        self.assertAlmostEqual(b[3], 98)                           # coin haut gauche
        r = N.nest([rect(0, 0, 90, 20)], pl, N.NestSpec(margin=2, gap=0, allow_rotate=False))
        self.assertEqual(len(r.unplaced), 1)

    def test_several_plates_and_copies(self):
        pl = Plate(100, 50)
        r = N.nest([rect(0, 0, 45, 20)], pl, N.NestSpec(margin=0, gap=0, allow_rotate=False, copies=10))
        self.assertEqual(len(r.placed), 10)
        self.assertEqual(r.plates, 3)                              # 4 par plaque
        self.assertEqual(overlaps([o.bbox() for o in r.items()], 0), 0)

    def test_typeedit_text_stays_live_when_only_moved(self):
        t = Text(text='A', outline=Path([geom.rect(0, 0, 4, 6)]))
        t.extra['vnd_obj'] = object()
        r = N.nest([t], Plate(100, 50), N.NestSpec(margin=5, gap=0))
        moved = r.items()[0]
        self.assertIn('vnd_shift', moved.extra)
        self.assertFalse(moved.extra.get('vnd_moved'))


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_apply_with_copies(self):
        w = self.w
        w.canvas.doc.plate = Plate(200, 100)
        a, b = rect(500, 500, 30, 20), rect(-300, 0, 10, 10)
        w._add_items([a, b])
        r = w.apply_nesting([a, b], N.NestSpec(margin=5, gap=2, copies=3))
        self.assertEqual(len(r.placed), 6)
        self.assertEqual(len(w.canvas.selection), 6)
        self.assertEqual(len({it.id for it in w.canvas.selection}), 6)       # copies distinctes
        self.assertEqual(len(list(w.canvas.doc.iter_items())), 6)
        w.undo()
        self.assertEqual(len(list(w.canvas.doc.iter_items())), 2)


if __name__ == '__main__':
    unittest.main()
