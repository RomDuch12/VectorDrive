"""Round 63 : Décaler exact (somme de Minkowski avec un disque)."""
import math
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom, pathops
from vectordrive.core import parallel as PA
from vectordrive.core.document import Shape
from vectordrive.core.geom import Contour, Cubic, Line, Path


def dev_circle(p, r):
    return max(abs(math.hypot(*q) - r) for c in p.contours for q in c.flatten(1e-5))


class TestOffsetRegion(unittest.TestCase):
    def test_circle_exact(self):
        for d in (1, -3):
            out = PA.offset_region(Path([geom.circle((0, 0), 10)]), d)
            self.assertLess(dev_circle(out, 10 + d), 1e-8)
            self.assertGreater(dev_circle(pathops.offset(Path([geom.circle((0, 0), 10)]), d), 10 + d), 1e-3)  # l'ancien

    def test_ring_and_stroke(self):
        ring = Path([geom.circle((0, 0), 10), geom.circle((0, 0), 5)])
        for d, R, r in ((1, 11, 4), (-1, 9, 6)):
            self.assertAlmostEqual(pathops.area(PA.offset_region(ring, d)), math.pi * (R * R - r * r), places=6)
        self.assertAlmostEqual(pathops.area(PA.offset_region(ring, 6)), math.pi * 256, places=6)    # trou bouché
        line = Path([Contour([Line((0, 0), (10, 0))], False)])
        self.assertAlmostEqual(pathops.area(PA.offset_region(line, 1)), 20 + math.pi, places=6)

    def test_square_corners(self):
        sq = Path([geom.rect(0, 0, 10, 10)])
        self.assertAlmostEqual(pathops.area(PA.offset_region(sq, 1)), 100 + 40 + math.pi, places=6)
        self.assertAlmostEqual(pathops.area(PA.offset_region(sq, -1)), 64, places=6)
        two = Path([geom.rect(0, 0, 10, 10), geom.rect(11, 0, 10, 10)])
        self.assertEqual(len(PA.offset_region(two, 1).contours), 1)                     # fusionnés

    def test_checked_fallback(self):
        spike = Path([Contour([Cubic((0, 0), (0.002, 0.03), (0.004, 0.06), (0.003, 0.1)),
                               Cubic((0.003, 0.1), (0.004, 0.07), (0.002, 0.03), (0, 0))], True)])
        res, exact = PA.offset_checked(spike, 0.3)
        self.assertGreater(pathops.area(res), 0.25)                                      # ≈ π·0,09 + 0,06
        res, exact = PA.offset_checked(Path([geom.circle((0, 0), 10)]), 1)
        self.assertTrue(exact)


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_offset_dialog_exact(self):
        from vectordrive.ui import dialogs
        from vectordrive.ui.main_window import MainWindow

        class Fake:
            def __init__(self, *a, **k):
                pass

            def exec(self):
                return True

            def values(self):
                return {'distance': 1.0, 'count': 1, 'join': 'round', 'keep': False}
        old = dialogs.OffsetDialog
        dialogs.OffsetDialog = Fake
        w = MainWindow()
        try:
            c = Shape(path=Path([geom.circle((0, 0), 10)]))
            w._add_items([c])
            w.canvas.select([c])
            w.offset_dialog()
            got = w.canvas.selection[0]
            self.assertLess(dev_circle(got.path, 11), 1e-8)
        finally:
            dialogs.OffsetDialog = old
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
