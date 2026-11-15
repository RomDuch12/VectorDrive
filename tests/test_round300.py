"""Round 300 : accrochage au centre de gravité des contours fermés (TypeEdit :
F3, Centre de gravité du contour) — trous retranchés, fenêtre et ruban."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Shape
from vectordrive.core.snap import Snap, centroid, item_points

app = QApplication.instance() or QApplication([])


class TestCentroid(unittest.TestCase):
    def test_points(self):
        L = geom.polyline([(0, 0), (4, 0), (4, 1), (1, 1), (1, 4), (0, 4)], closed=True)
        g = centroid(geom.Path([L]))
        self.assertAlmostEqual(g[0], 19 / 14, 6)                         # barres 4×1 et 1×3
        self.assertAlmostEqual(g[1], 19 / 14, 6)
        ring = geom.Path([geom.rect(0, 0, 10, 10), geom.rect(0, 0, 5, 5)])  # trou dans le coin
        g = centroid(ring)
        self.assertGreater(g[0], 5.0)
        self.assertEqual(item_points(Shape(path=geom.Path([geom.polyline([(0, 0), (5, 5)])])))['centroid'], [])

    def test_snap(self):
        L = geom.polyline([(0, 0), (4, 0), (4, 1), (1, 1), (1, 4), (0, 4)], closed=True)
        sn = Snap(enabled=True, modes={'centroid'})
        h = sn.query(1.4, 1.4, 0.3, [Shape(path=geom.Path([L]))])
        self.assertEqual(h.kind, 'centroid')
        self.assertAlmostEqual(h.x, 19 / 14, 6)

    def test_window(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            self.assertFalse(w.A['snap_centroid'].isChecked())
            w.A['snap_centroid'].setChecked(True)
            self.assertIn('centroid', w.canvas.snap.modes)
            win = w.snap_window()
            self.assertIn('centroid', win.boxes)
            win.close()
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
