"""Round 177 : stratégies de découpe de TypeEdit (FAO ▸ Découpe)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import cutpatterns as CP


class TestPatterns(unittest.TestCase):
    def test_staggered_circles(self):
        plate, circles = CP.staggered_circles(100, 40, 10)
        self.assertEqual(len(plate.contours), 1)
        boxes = [c.bbox() for c in circles.contours]
        self.assertTrue(all(b[0] >= -1e-9 and b[2] <= 100 + 1e-9 and b[1] >= -1e-9 and b[3] <= 40 + 1e-9
                            for b in boxes))
        rows = sorted({round((b[1] + b[3]) / 2, 6) for b in boxes})
        self.assertAlmostEqual(rows[1] - rows[0], 10 * math.sqrt(3), places=6)      # quinconce
        self.assertEqual(len(circles.contours), 5 + 4)                              # 5 puis 4 (décalée)

    def test_octagons_tile(self):
        _plate, octs = CP.octagons(90, 60, 3)
        self.assertEqual(len(octs.contours), 3 * 2)
        b = octs.contours[0].bbox()
        self.assertAlmostEqual(b[2] - b[0], 30, places=6)
        pts = octs.contours[0].flatten(0.01)
        sides = [math.dist(a, c) for a, c in zip(pts, pts[1:])]
        self.assertAlmostEqual(max(sides), min(sides), places=6)                     # régulier

    def test_pie_and_washer(self):
        outer, spokes = CP.pie(50, 6, 10, 10)
        self.assertEqual(len(spokes.contours), 6)
        self.assertEqual(len(outer.contours), 1)
        self.assertEqual(CP.pie(50, 6, cut_outer=False)[0].contours, [])
        o, i = CP.washer(0, 0, 30, 10)
        self.assertEqual((len(o.contours), len(i.contours)), (1, 1))
        self.assertEqual(CP.washer(0, 0, 30, 40)[1].contours, [])

    def test_rectangles_and_triangles(self):
        _p, lines = CP.rectangles(60, 40, 3, 2)
        self.assertEqual(len(lines.contours), 2 + 1)                                # lignes communes seulement
        _p, tri = CP.triangles(60, 40, 3, 2, rising=False)
        self.assertEqual(len(tri.contours), 3 + 6)
        d = tri.contours[-1].segments[0]
        self.assertGreater(d.start[1], d.end[1])                                     # descendante

    def test_commands(self):
        app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.shortcuts import TE_ACTIONS
        for te, act in (('ID_WATERJET_OFFSETCIRCLES', 'cut_cercles'), ('ID_WATERJET_NESTEDCIRCLES', 'cut_rondelle')):
            self.assertEqual(TE_ACTIONS[te], act)
        w = MainWindow()
        try:
            g = w.cut_pattern('rectangles', {'length': 60, 'width': 40, 'nx': 3, 'ny': 2, 'mode': 1}, (5, 5))[0]
            self.assertEqual([c.name for c in g.children], ['Contour', 'Traits de découpe'])   # contour d'abord
            g = w.cut_pattern('rectangles', {'length': 60, 'width': 40, 'nx': 3, 'ny': 2, 'mode': 2})[0]
            self.assertEqual([c.name for c in g.children], ['Traits de découpe', 'Contour'])
            g = w.cut_pattern('rectangles', {'length': 60, 'width': 40, 'nx': 3, 'ny': 2, 'mode': 0})[0]
            self.assertEqual([c.name for c in g.children], ['Traits de découpe'])
            g = w.cut_pattern('rondelle', {'outer': 30, 'inner': 10}, (100, 100))[0]
            self.assertEqual(g.children[0].name, 'Traits de découpe')                   # intérieur d'abord
            self.assertEqual(len(w.canvas.doc.layers[0].items), 4)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
