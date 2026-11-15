"""Round 176 : texture de TypeEdit — courbes qui remplissent l'espace."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication
from shapely.geometry import Point, Polygon

from vectordrive.core import geom, texture as T
from vectordrive.core.document import Shape


class TestCurves(unittest.TestCase):
    def test_counts_and_steps(self):
        self.assertEqual(len(T.curve_points('hilbert', 3)), 4 ** 3)                 # une case par point
        self.assertEqual(len(T.curve_points('lebesgue', 3)), 4 ** 3)
        self.assertEqual(len(T.curve_points('peano', 2)), 9 ** 2)
        for kind in ('hilbert', 'peano', 'moore', 'sierpinski'):
            pts = T.curve_points(kind, 3)
            step = math.sqrt(2) if kind == 'sierpinski' else 1                     # Sierpinski tourné de 45°
            self.assertTrue(all(abs(math.dist(a, b) - step) < 1e-9 for a, b in zip(pts, pts[1:])), kind)
            self.assertEqual(len(set(pts)), len(pts) - (1 if pts[0] == pts[-1] else 0), kind)  # sans repasser
        moore = T.curve_points('moore', 3)
        self.assertEqual(math.dist(moore[0], moore[-1]), 1)                        # presque fermée (Moore)
        self.assertEqual(len(T.curve_points('hilbert', 99)), 4 ** 8)               # itérations bornées

    def test_clip_with_hole(self):
        ring = geom.Path([geom.rect(0, 0, 40, 40), geom.rect(10, 10, 20, 20)])     # carré troué
        p = T.texture(ring, 'hilbert', 5)
        self.assertTrue(p.contours)
        outer = Polygon([(0, 0), (40, 0), (40, 40), (0, 40)])
        hole = Polygon([(10.5, 10.5), (29.5, 10.5), (29.5, 29.5), (10.5, 29.5)])
        for c in p.contours:
            self.assertFalse(c.closed)
            for pt in c.flatten(0.01):
                self.assertTrue(outer.buffer(1e-6).contains(Point(pt)))
                self.assertFalse(hole.contains(Point(pt)))                          # rien dans le trou
        with_border = T.texture(ring, 'hilbert', 3, border=True)
        self.assertEqual(sum(1 for c in with_border.contours if c.closed), 2)

    def test_empty(self):
        self.assertEqual(T.texture(geom.Path([geom.polyline([(0, 0), (5, 5)])]), 'peano', 2).contours, [])


class TestCommand(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_command(self):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual(TE_ACTIONS['ID_PALETTE_TEXTURE'], 'texture')
        w = MainWindow()
        try:
            s = w.canvas.doc.add(Shape(path=geom.Path([geom.circle((0, 0), 20)]), tool=2))
            w.canvas.select([s])
            new = w.texture_shapes('moore', 4)
            self.assertEqual(len(new), 1)
            self.assertEqual(new[0].tool, 2)
            self.assertIn(new[0], w.canvas.doc.layers[0].items)
            w.undo()
            self.assertEqual(len(w.canvas.doc.layers[0].items), 1)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
