"""Round 120 : couteau — formes fermées coupées le long d'un trait."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom, knife as KN
from vectordrive.core.document import Shape
from vectordrive.core.geom import Path


class TestKnife(unittest.TestCase):
    def test_rect_by_line(self):
        parts = KN.cut(Path([geom.rect(0, 0, 10, 4)]), Path([geom.polyline([(4, -1), (6, 5)])]))
        self.assertEqual(len(parts), 2)
        areas = sorted(round(abs(p.contours[0].signed_area()), 3) for p in parts)
        self.assertAlmostEqual(sum(areas), 40, places=3)

    def test_hole_kept_and_polyline(self):
        ring = Path([geom.rect(0, 0, 20, 20), geom.rect(5, 5, 10, 10)])
        parts = KN.cut(ring, Path([geom.polyline([(-1, 10), (25, 10)])]))
        self.assertEqual(len(parts), 2)                                       # anneau coupé en deux « U »
        self.assertAlmostEqual(sum(abs(p.contours[0].signed_area()) for p in parts), 400 - 100, places=3)
        zig = KN.cut(Path([geom.rect(0, 0, 30, 10)]), Path([geom.polyline([(-1, 5), (10, 5), (10, 11)])]))
        self.assertEqual(len(zig), 2)

    def test_not_crossing(self):
        p = Path([geom.rect(0, 0, 10, 10)])
        self.assertEqual(KN.cut(p, Path([geom.polyline([(2, 2), (5, 5)])])), [p])     # entre sans sortir
        self.assertEqual(KN.cut(p, Path([geom.polyline([(20, 0), (20, 10)])])), [p])

    def test_window(self):
        QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            a = Shape(path=Path([geom.rect(0, 0, 10, 10)]), tool=2)
            b = Shape(path=Path([geom.circle((30, 5), 4)]), tool=3)
            blade = Shape(path=Path([geom.polyline([(-5, 5), (40, 5)])]))
            w.canvas.doc.layers[0].items += [a, b, blade]
            w.canvas.select([a, b, blade])
            self.assertEqual(w.knife(), 4)
            items = w.canvas.doc.layers[0].items
            self.assertEqual(len(items), 5)                                    # 2 + 2 morceaux + le trait
            self.assertEqual(sorted(s.tool for s in items if s is not blade), [2, 2, 3, 3])
            self.assertEqual(len({s.id for s in items}), 5)
            w.undo()
            self.assertEqual(len(w.canvas.doc.layers[0].items), 3)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
