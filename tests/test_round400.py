"""Round 400 : congé à rayon négatif (TypeEdit : angle arrondi vers
l'intérieur) — arc centré sur le coin, coin creusé."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import geom
from vectordrive.cam import strategies as S


class TestNotch(unittest.TestCase):
    def test_square(self):
        sq = geom.rect(0, 0, 10, 10)
        out = geom.corner_contour(sq, -2.0, 'fillet')
        self.assertTrue(out.closed)
        area = S.region([geom.Path([out])], 0.001).area
        self.assertAlmostEqual(area, 100 - 4 * math.pi * 4 / 4, delta=0.02)   # quatre quarts de disque de rayon 2 ôtés
        for x, y in out.flatten(0.001):                                     # aucun point dans les quarts de disque
            for cx, cy in ((0, 0), (10, 0), (10, 10), (0, 10)):
                self.assertGreaterEqual(math.hypot(x - cx, y - cy), 2.0 - 1e-3)

    def test_positive_unchanged(self):
        sq = geom.rect(0, 0, 10, 10)
        a = geom.corner_contour(sq, 2.0, 'fillet')
        area = S.region([geom.Path([a])], 0.001).area
        self.assertAlmostEqual(area, 100 - 4 * (4 - math.pi), delta=0.02)   # congé classique
        self.assertEqual(geom.corner_contour(sq, -1.0, 'chamfer').segments, sq.segments)   # chanfrein négatif : rien


if __name__ == '__main__':
    unittest.main()
