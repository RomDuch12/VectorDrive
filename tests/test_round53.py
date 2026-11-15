"""Round 53 : hachures."""
import math
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom
from vectordrive.core import hatch as H
from vectordrive.core.document import Shape
from vectordrive.core.geom import Affine, Path


def ring():
    return Shape(path=Path([geom.circle((0, 0), 20), geom.circle((0, 0), 10)]))


class TestHatch(unittest.TestCase):
    def test_length_equals_area_over_spacing(self):
        g = H.build([ring()], H.HatchSpec(spacing=0.25, angle=17))
        L = sum(c.length() for c in g.children[1].path.contours)
        self.assertAlmostEqual(L, math.pi * 300 / 0.25, delta=math.pi * 300 / 0.25 * 0.005)

    def test_hole_left_empty_and_alternating(self):
        lines = H.build([ring()], H.HatchSpec(spacing=1, angle=0)).children[1].path.contours
        mids = [((c.start[0] + c.end[0]) / 2, (c.start[1] + c.end[1]) / 2) for c in lines]
        self.assertFalse(any(math.hypot(x, y) < 10 - 1e-6 for x, y in mids))
        dirs = {round(c.start[1], 6): c.end[0] - c.start[0] for c in lines}
        ys = sorted(dirs)
        self.assertNotEqual(dirs[ys[0]] > 0, dirs[ys[1]] > 0)        # sens alterné

    def test_cross_inset_outline_and_rebuild(self):
        g = H.build([ring()], H.HatchSpec(spacing=1, angle=0, cross=True, inset=0.5, outline=False))
        src = g.children[0]
        self.assertFalse(src.visible)                                # contour masqué, gardé pour modifier
        n = len(g.children[1].path.contours)
        moved = g.transformed(Affine.translation(50, 0))
        g2 = H.rebuild(moved, H.HatchSpec(spacing=2, angle=0))
        bb = g2.children[1].path.bbox()
        self.assertGreater(bb[0], 29)                                # suit le déplacement
        self.assertLess(len(g2.children[1].path.contours), n)

    def test_nothing_closed(self):
        from vectordrive.core.geom import Contour, Line
        self.assertIsNone(H.build([Shape(path=Path([Contour([Line((0, 0), (5, 0))], False)]))], H.HatchSpec()))


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_new_and_edit(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            r = ring()
            w._add_items([r])
            w._hatch_dialog = lambda spec: H.HatchSpec(spacing=1, angle=0)
            w.new_hatch()
            g = w.canvas.selection[0]
            self.assertIn('hatch', g.extra)
            w._hatch_dialog = lambda spec: H.HatchSpec(spacing=2, angle=90)
            w._item_double_clicked(g)
            g2 = w.canvas.selection[0]
            self.assertEqual(g2.extra['hatch']['spacing'], 2)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
