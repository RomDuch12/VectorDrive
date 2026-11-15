"""Round 62 : espacement imposé, même taille."""
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import combine as C
from vectordrive.core import geom
from vectordrive.core.document import Shape
from vectordrive.core.geom import Path


def box(x, y, w, h):
    return Shape(path=Path([geom.rect(x, y, w, h)]))


class TestLayout(unittest.TestCase):
    def test_space_fixed(self):
        items = [box(30, 0, 4, 4), box(0, 0, 10, 2), box(50, 5, 6, 6)]
        out = C.space_fixed(items, 'x', 2)
        bb = sorted((it.bbox() for it in out), key=lambda b: b[0])
        self.assertEqual([round(b[0], 9) for b in bb], [0, 12, 18])
        self.assertEqual([round(b[1], 9) for b in (o.bbox() for o in out)], [0, 0, 5])   # y inchangé
        out = C.space_fixed(items, 'y', 1)
        ys = sorted(round(o.bbox()[1], 9) for o in out)
        self.assertEqual(ys, [0, 3, 8])

    def test_same_size(self):
        items = [box(0, 0, 10, 2), box(20, 0, 4, 4), box(40, 0, 5, 8)]
        out = C.same_size(items, 'w')
        self.assertEqual([round(o.bbox()[2] - o.bbox()[0], 9) for o in out], [5, 5, 5])
        self.assertEqual([round(o.bbox()[3] - o.bbox()[1], 9) for o in out], [2, 4, 8])
        out = C.same_size(items, 'both')
        self.assertEqual([(round(o.bbox()[2] - o.bbox()[0], 9), round(o.bbox()[3] - o.bbox()[1], 9)) for o in out],
                         [(5, 8)] * 3)
        c0 = items[0].bbox()
        n0 = out[0].bbox()
        self.assertAlmostEqual((c0[0] + c0[2]) / 2, (n0[0] + n0[2]) / 2)                 # centre gardé
        out = C.same_size(items, 'h', keep_ratio=True)
        b = out[0].bbox()
        self.assertAlmostEqual(b[2] - b[0], 40)                                          # 10 × 8/2
        self.assertIs(out[2], items[2])                                                   # référence intacte


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_commands(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            items = [box(0, 0, 10, 2), box(20, 0, 4, 4)]
            w._add_items(items)
            w.canvas.select(items)
            w.same_size_items('h')
            hs = sorted(round(it.bbox()[3] - it.bbox()[1], 9) for it in w.canvas.doc.iter_items())
            self.assertEqual(hs, [2, 2])
            w.undo()
            hs = sorted(round(it.bbox()[3] - it.bbox()[1], 9) for it in w.canvas.doc.iter_items())
            self.assertEqual(hs, [2, 4])
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
