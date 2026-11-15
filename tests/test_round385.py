"""Round 385 : traits de coupe et hirondelles de repérage."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import cropmarks as CM, geom
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


class TestCropMarks(unittest.TestCase):
    def test_corners(self):
        p = CM.marks((0, 0, 100, 50), CM.CropMarksSpec(kind='coins', length=5, gap=2))
        self.assertEqual(len(p.contours), 8)
        self.assertEqual(tuple(round(v, 6) for v in p.bbox()), (-7, -7, 107, 57))
        for c in p.contours:                              # aucun trait dans le cadre
            for x, y in c.flatten(0.01):
                self.assertFalse(0 < x < 100 and 0 < y < 50, (x, y))

    def test_targets_margin(self):
        p = CM.marks((0, 0, 100, 50), CM.CropMarksSpec(kind='les_deux', length=5, gap=2, target=4, margin=3))
        self.assertEqual(len(p.contours), 8 + 4 * 3)
        circles = [c for c in p.contours if c.closed]
        self.assertEqual(len(circles), 4)
        b = circles[0].bbox()
        self.assertAlmostEqual(b[2] - b[0], 4.0, 6)
        self.assertAlmostEqual((b[0] + b[2]) / 2, 50.0, 6)          # au milieu du côté bas
        self.assertAlmostEqual((b[1] + b[3]) / 2, -3 - 2 - 2.5, 6)   # sous le cadre agrandi

    def test_window(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            s = Shape(path=geom.Path([geom.rect(10, 10, 20, 10)]))
            w.canvas.doc.add(s)
            w.canvas.select([s])
            g = w.crop_marks(CM.CropMarksSpec(kind='coins'))
            self.assertEqual(len(g.children), 8)
            self.assertEqual(tuple(round(v, 6) for v in g.bbox()), (3, 3, 37, 27))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
