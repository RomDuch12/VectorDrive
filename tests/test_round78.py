"""Round 78 : contour du trait exact."""
import math
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom, pathops
from vectordrive.core import parallel as PA
from vectordrive.core.geom import Contour, Line, Path


class TestStroke(unittest.TestCase):
    def test_circle_exact(self):
        res, exact = PA.stroke_checked(Path([geom.circle((0, 0), 10)]), 2)
        self.assertTrue(exact)
        for c in res.contours:
            for q in c.flatten(1e-5):
                r = math.hypot(*q)
                self.assertLess(min(abs(r - 9), abs(r - 11)), 1e-8)

    def test_open_stroke_area(self):
        res, exact = PA.stroke_checked(Path([Contour([Line((0, 0), (10, 0)), Line((10, 0), (10, 10))], False)]), 2)
        self.assertTrue(exact)
        # deux rectangles 10 × 2 (réunion 39), quart de disque au coin extérieur, deux demi-disques aux bouts
        expected = 39 + math.pi / 4 + math.pi
        self.assertAlmostEqual(pathops.area(res), expected, places=5)

    def test_degenerate_falls_back(self):
        res, exact = PA.stroke_checked(Path([Contour([Line((0, 0), (10, 0))], False)]), 0)
        self.assertFalse(exact)


if __name__ == '__main__':
    unittest.main()
