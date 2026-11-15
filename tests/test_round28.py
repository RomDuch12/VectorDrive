"""Round 28 : vectorisation d'images noir et blanc."""
import math
import os
import pathlib
import tempfile
import unittest

import numpy as np

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import trace as TR
from vectordrive.core.geom import Line


def logo(H=120, W=200):
    """Anneau (r 15 à 40) centré en (60, 60), carré 60 × 60 en (130, 20)."""
    yy, xx = np.mgrid[0:H, 0:W] + 0.5
    g = np.ones((H, W))
    r = np.hypot(xx - 60, yy - 60)
    g[(r < 40) & (r >= 15)] = 0
    g[20:80, 130:190] = 0
    return g


class TestTrace(unittest.TestCase):
    def test_otsu(self):
        g = logo()
        t = TR.otsu(g)
        self.assertGreater(t, 0.0)
        self.assertLess(t, 1.0)

    def test_shapes(self):
        cs = TR.trace(logo(), TR.TraceSpec())
        self.assertEqual(len(cs), 3)
        by_area = sorted(cs, key=lambda c: c.signed_area())
        hole, square, disk = by_area[0], by_area[1], by_area[2]
        self.assertLess(hole.signed_area(), 0)                    # trou : autre sens
        self.assertGreater(disk.signed_area(), 0)
        for v, ref in zip(disk.bbox(), (20, 20, 100, 100)):
            self.assertAlmostEqual(v, ref, delta=0.3)
        for v, ref in zip(hole.bbox(), (45, 45, 75, 75)):
            self.assertAlmostEqual(v, ref, delta=0.3)
        self.assertAlmostEqual(disk.length(), 2 * math.pi * 40, delta=2 * math.pi * 40 * 0.015)
        self.assertEqual(square.bbox(), (130.0, 20.0, 190.0, 80.0))
        self.assertTrue(all(isinstance(s, Line) for s in square.segments))
        self.assertEqual(len(square.segments), 4)

    def test_corner_touching_pixels_stay_apart(self):
        g = np.ones((6, 6))
        g[2, 2] = g[3, 3] = 0
        loops = TR.trace_loops(TR.binarize(g, TR.TraceSpec(threshold=0.5)))
        self.assertEqual(sorted(TR._area(lp) for lp in loops), [1.0, 1.0])

    def test_options(self):
        g = logo()
        self.assertEqual(TR.trace(np.ones((10, 10)), TR.TraceSpec()), [])
        poly = TR.trace(g, TR.TraceSpec(smooth=False))
        self.assertTrue(all(isinstance(s, Line) for c in poly for s in c.segments))
        g2 = g.copy()
        g2[100, 100] = 0                                           # tache d'un pixel
        self.assertEqual(len(TR.trace(g2, TR.TraceSpec())), 3)
        self.assertEqual(len(TR.trace(g2, TR.TraceSpec(speckle=0.5))), 4)
        inv = TR.trace(1 - g, TR.TraceSpec(invert=True))
        self.assertEqual(len(inv), 3)


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

    def test_trace_file(self):
        from PySide6.QtGui import QImage
        from PySide6.QtWidgets import QFileDialog
        from vectordrive.ui import dialogs
        g = (logo() * 255).astype(np.uint8)
        img = QImage(g.data, g.shape[1], g.shape[0], g.shape[1], QImage.Format.Format_Grayscale8).copy()

        class Fake:
            def __init__(self, parent, title, params, labels, warning=''):
                self.p = params
                self.p.width = 100.0

            def exec(self):
                return True

            def result_params(self):
                return self.p
        saved = (dialogs.ParamsDialog, QFileDialog.getOpenFileName)
        with tempfile.TemporaryDirectory() as tmp:
            f = pathlib.Path(tmp) / 'logo.png'
            img.save(str(f))
            dialogs.ParamsDialog = Fake
            QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (str(f), ''))
            try:
                self.w.trace_image()
            finally:
                dialogs.ParamsDialog, QFileDialog.getOpenFileName = saved[0], staticmethod(saved[1])
        s = self.w.canvas.selection[0]
        self.assertEqual(len(s.path.contours), 3)
        bb = s.bbox()
        self.assertAlmostEqual(bb[2] - bb[0], 100 * (190 - 20) / 200, delta=0.3)   # 100 mm pour 200 px
        # l'anneau est dans le sens direct une fois l'image remise à l'endroit
        self.assertGreater(max(c.signed_area() for c in s.path.contours), 0)


if __name__ == '__main__':
    unittest.main()
