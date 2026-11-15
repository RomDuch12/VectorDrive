"""Round 136 : enregistrement des VND plus rapide — sens des contours par une
aire exacte (Green, Gauss) sans aplatir les courbes, comparaison des points
par numpy, source lue une seule fois. Fichiers écrits identiques à l'octet
(vérifié sur 17 VND de l'atelier, 3 cas chacun)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import geom
from vectordrive.core.geom import Conic, Contour, Cubic, Line
from vectordrive.io import vnd_write as W


def ellipse_arc_contour(cx, cy, rx, ry, reverse=False):
    """Ellipse en 4 coniques (w = cos 45°)."""
    w = math.cos(math.pi / 4)
    pts = [(cx + rx, cy), (cx, cy + ry), (cx - rx, cy), (cx, cy - ry)]
    ctl = [(cx + rx, cy + ry), (cx - rx, cy + ry), (cx - rx, cy - ry), (cx + rx, cy - ry)]
    segs = [Conic(pts[i], ctl[i], pts[(i + 1) % 4], w) for i in range(4)]
    c = Contour(segs, True)
    return c.reversed() if reverse else c


class TestArea(unittest.TestCase):
    def check(self, c, exact=None):
        a = W.fast_signed_area(c)
        b = c.signed_area()
        self.assertIsNotNone(a)
        self.assertAlmostEqual(a, b, delta=max(1e-6, abs(b) * 1e-3))       # aplatissement : par défaut
        if exact is not None:
            self.assertAlmostEqual(a, exact, delta=abs(exact) * 1e-9 + 1e-12)
        return a

    def test_lines(self):
        self.check(geom.rect(0, 0, 40, 20), 800.0)
        self.check(geom.rect(0, 0, 40, 20).reversed(), -800.0)

    def test_cubics_circle(self):
        c = geom.circle((10, 5), 3)
        a = self.check(c)
        self.assertAlmostEqual(a, math.pi * 9, delta=1e-9)                 # arcs : aire exacte
        self.assertLess(W.fast_signed_area(c.reversed()), 0)

    def test_conics_ellipse(self):
        a = self.check(ellipse_arc_contour(0, 0, 30, 10))
        self.assertAlmostEqual(a, math.pi * 300, delta=1e-6)               # coniques : exact
        self.assertLess(W.fast_signed_area(ellipse_arc_contour(0, 0, 30, 10, True)), 0)

    def test_mixed_and_open_closing(self):
        c = Contour([Line((0, 0), (10, 0)), Cubic((10, 0), (12, 4), (8, 8), (5, 10))], True)  # fermeture implicite
        self.check(c)

    def test_contour_type(self):
        self.assertEqual(W._contour_type(geom.rect(0, 0, 1, 1)), 1)
        self.assertEqual(W._contour_type(geom.rect(0, 0, 1, 1).reversed()), 2)
        self.assertEqual(W._contour_type(Contour([Line((0, 0), (1, 0))], False)), 0)
        # aire nulle (aller-retour) : repli sur le calcul d'origine
        flat = Contour([Line((0, 0), (10, 0)), Line((10, 0), (0, 0))], True)
        self.assertIn(W._contour_type(flat), (1, 2))


class TestClose(unittest.TestCase):
    def test_points(self):
        a = [(0.001 * i, 0.002, 0.0, 1.0, 13) for i in range(50)]
        b = [p for p in a]
        self.assertTrue(W._close(a, b))
        b2 = list(a)
        b2[30] = (b2[30][0] + 1e-9,) + b2[30][1:]
        self.assertFalse(W._close(a, b2))
        self.assertFalse(W._close(a, a[:-1]))
        self.assertTrue(W._close((1.0, 2.0), [1.0, 2.0 + 1e-13]))
        self.assertFalse(W._close((1.0, 'x'), (1.0, 2.0)))
        ragged = [(1.0, 2.0), (1.0, 2.0, 3.0)] * 6                          # formes irrégulières
        self.assertTrue(W._close(ragged, [tuple(p) for p in ragged]))


if __name__ == '__main__':
    unittest.main()
