"""Round 382 : contour de zone — tolérance d'écart (DAO : HPGAPTOL) : une
zone presque fermée est acceptée."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.boundary import boundary_at
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])

# carré de 10 dont le côté haut s'arrête à 0,3 mm du coin
OPEN_SQUARE = [geom.Path([geom.polyline([(0, 10), (0, 0), (10, 0), (10, 10)])]),
               geom.Path([geom.polyline([(0.3, 10), (10, 10)])])]


class TestGap(unittest.TestCase):
    def test_gap(self):
        self.assertIsNone(boundary_at(OPEN_SQUARE, (5, 5)))
        self.assertIsNone(boundary_at(OPEN_SQUARE, (5, 5), gap=0.2))         # écart plus grand que la tolérance
        p = boundary_at(OPEN_SQUARE, (5, 5), gap=0.5)
        b = p.bbox()
        for v, e in zip(b, (0, 0, 10, 10)):
            self.assertAlmostEqual(v, e, 2)                                 # angles vifs retrouvés
        self.assertTrue(p.contours[0].closed)
        self.assertIsNone(boundary_at(OPEN_SQUARE, (50, 50), gap=0.5))

    def test_window(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            for path in OPEN_SQUARE:
                w.canvas.doc.add(Shape(path=path))
            self.assertEqual(w.boundary_gap_dialog(0.5), 0.5)
            sh = w.canvas.boundary_at((5, 5))
            self.assertIsNotNone(sh)
            w.boundary_gap_dialog(0.0)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
