"""Round 406 : étendre en arc (TypeEdit) — un arc prolongé sur son cercle
jusqu'au premier trait rencontré."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import geom, trim as TR


class TestExtendArc(unittest.TestCase):
    def test_extend(self):
        arc = geom.arc_3points((10, 0), (math.sqrt(50), math.sqrt(50)), (0, 10))   # quart de cercle r 10, anti-horaire
        wall = geom.polyline([(-20, 5), (0, 5)])                                       # trait à y = 5, côté gauche
        out = TR.extend_arc(geom.Path([arc]), list(wall.segments), (0, 10))
        c = out.contours[0]
        end = c.end
        self.assertAlmostEqual(end[1], 5.0, 3)                                         # arrêté sur le trait
        self.assertAlmostEqual(math.hypot(*end), 10.0, 6)                              # toujours sur le cercle
        self.assertLess(end[0], 0)
        for x, y in c.flatten(0.01):
            self.assertAlmostEqual(math.hypot(x, y), 10.0, 2)

    def test_not_arc(self):
        line = geom.polyline([(0, 0), (5, 0)])
        self.assertIsNone(TR.extend_arc(geom.Path([line]), [], (5, 0)))
        arc = geom.arc_3points((10, 0), (math.sqrt(50), math.sqrt(50)), (0, 10))
        self.assertIsNone(TR.extend_arc(geom.Path([arc]), [], (0, 10)))                # rien sur le cercle


if __name__ == '__main__':
    unittest.main()
