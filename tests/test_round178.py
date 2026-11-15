"""Round 178 : LED de TypeEdit (enseignes lumineuses)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication
from shapely.geometry import Point, Polygon

from vectordrive.core import geom, leds as L
from vectordrive.core.document import Shape


class TestLeds(unittest.TestCase):
    def test_spacing_on_closed_contour(self):
        sq = geom.rect(0, 0, 100, 100)                                             # 400 mm
        pts = L.along(sq, L.LedSpec(spacing_min=20, spacing_max=30))
        self.assertEqual(len(pts), 14)                                             # 400 / 14 ≈ 28,6 : dans [20, 30]
        gaps = [math.dist(a, b) for a, b in zip(pts, pts[1:] + pts[:1])]
        self.assertTrue(all(g <= 30 + 1e-6 for g in gaps))
        self.assertEqual(len(L.along(sq, L.LedSpec(count=8))), 8)

    def test_open_with_offsets(self):
        line = geom.polyline([(0, 0), (100, 0)])
        pts = L.along(line, L.LedSpec(spacing_min=20, spacing_max=25, offset_start=10, offset_end=10))
        self.assertAlmostEqual(pts[0][0], 10)
        self.assertAlmostEqual(pts[-1][0], 90)
        self.assertEqual(len(pts), 5)                                              # 80 mm en 4 écarts de 20

    def test_corners_and_collisions(self):
        sq = geom.rect(0, 0, 100, 100)
        pts = L.along(sq, L.LedSpec(count=6, corners=True, spacing_min=20))
        for c in ((0, 0), (100, 0), (100, 100), (0, 100)):
            self.assertTrue(any(math.dist(c, p) < 1e-6 for p in pts), c)
        kept = L.drop_collisions([(0, 0), (3, 0), (10, 0)], 5)
        self.assertEqual(kept, [(0, 0), (10, 0)])

    def test_grid_inside(self):
        ring = geom.Path([geom.rect(0, 0, 100, 60), geom.rect(40, 20, 20, 20)])
        spec = L.LedSpec(layout='interieur', diameter=6, grid_x=10, grid_y=10)
        pts = L.layout(ring, spec)
        outer = Polygon([(0, 0), (100, 0), (100, 60), (0, 60)])
        hole = Polygon([(40, 20), (60, 20), (60, 40), (40, 40)])
        self.assertTrue(pts)
        for p in pts:
            self.assertTrue(outer.buffer(-3 + 1e-6).contains(Point(p)))           # diode entière
            self.assertGreaterEqual(hole.distance(Point(p)), 3 - 1e-6)

    def test_command(self):
        app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual(TE_ACTIONS['ID_CMD_LED'], 'leds')
        w = MainWindow()
        try:
            s = w.canvas.doc.add(Shape(path=geom.Path([geom.circle((0, 0), 50)])))
            w.canvas.select([s])
            g = w.leds(L.LedSpec(count=12, diameter=5))[0]
            self.assertEqual(len(g.children[0].path.contours), 12)
            self.assertIn('12', g.name)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
