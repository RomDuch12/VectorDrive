"""Round 891 : la commande Décaler (et le contour de trait) ne garde le calcul exact que si aucun sommet du résultat n'est plus près du
tracé que la distance demandée. Sur de vrais dessins, la bande d'un contour en Bézier pouvait ne pas couvrir ce contour : le retrait
gardait un morceau collé au tracé, que le contrôle des aires laissait passer."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import parallel, pathops
from vectordrive.core.geom import Contour, Cubic, Line, Path


def rect(x, y, w, h):
    return Contour([Line((x, y), (x + w, y)), Line((x + w, y), (x + w, y + h)), Line((x + w, y + h), (x, y + h)),
                    Line((x, y + h), (x, y))], closed=True)


def rounded(x, y, w, h, r):
    """Rectangle aux coins en Bézier cubiques (comme les lettres d'une police)."""
    k = 0.5523 * r
    return Contour([
        Line((x + r, y), (x + w - r, y)), Cubic((x + w - r, y), (x + w - r + k, y), (x + w, y + r - k), (x + w, y + r)),
        Line((x + w, y + r), (x + w, y + h - r)), Cubic((x + w, y + h - r), (x + w, y + h - r + k), (x + w - r + k, y + h), (x + w - r, y + h)),
        Line((x + w - r, y + h), (x + r, y + h)), Cubic((x + r, y + h), (x + r - k, y + h), (x, y + h - r + k), (x, y + h - r)),
        Line((x, y + h - r), (x, y + r)), Cubic((x, y + r), (x, y + r - k), (x + r - k, y), (x + r, y))], closed=True)


def strokes():
    """Trente traits de 1,5 mm de large (un retrait de 1 mm les fait tous disparaître) et un petit, de 1,5 × 2 mm."""
    cs = [rounded(3 * i, 0, 1.5, 6, 0.5) for i in range(30)]
    small = rect(95, 0, 1.5, 2)
    return Path(cs + [small]), small


class Guard(unittest.TestCase):

    def holed_band(self, small):
        """La bande du petit contour ne le couvre pas (vide) : le défaut relevé, quelle qu'en soit la cause."""
        real = parallel.band
        return mock.patch.object(parallel, 'band', lambda c, r, tol=parallel.TOL: Path() if c is small else real(c, r, tol))

    def test_the_area_check_alone_let_it_through(self):
        path, small = strokes()
        with self.holed_band(small):
            exact = parallel.offset_region(path, -1.0)
        ref = pathops.offset(path, -1.0)
        self.assertAlmostEqual(pathops.area(ref), 0.0, places=6)                     # tout disparaît
        self.assertGreater(pathops.area(exact), 2.9)                                  # le petit contour reste entier
        self.assertLessEqual(abs(pathops.area(exact) - pathops.area(ref)), 0.012 * path.length())   # ancien contrôle : passé
        self.assertTrue(parallel.misses(exact, path, 1.0))

    def test_offset_falls_back_on_the_native_result(self):
        path, small = strokes()
        with self.holed_band(small):
            res, exact = parallel.offset_checked(path, -1.0)
        self.assertFalse(exact)
        self.assertAlmostEqual(pathops.area(res), 0.0, places=6)

    def test_the_offset_command_counts_it_as_approached(self):
        path, small = strokes()
        self.assertEqual(parallel.offset_job(path, [-1.0, 0.5])[1:], (2, 0))
        with self.holed_band(small):
            out, exact, approx = parallel.offset_job(path, [-1.0, 0.5])
        self.assertEqual((exact, approx), (0, 2))                                     # l'agrandissement aussi : petit contour non grossi


def d_shape():
    """Forme en D tirée au hasard (recherche synthétique) : à la pointe de la Bézier de gauche, plus serrée que 1,5 mm, la parallèle
    extérieure fait un aller-retour presque confondu avec le raccord rond du coin ; leur croisement échappait à la recherche."""
    return Contour([
        Line((0.0, 0.0), (0.723, 0.0)), Cubic((0.723, 0.0), (0.723, 0.111), (1.186, 7.625), (1.186, 7.755)),
        Line((1.186, 7.755), (3.454, 7.755)), Cubic((3.454, 7.755), (6.502, 7.755), (6.004, -0.456), (2.956, -0.456)),
        Line((2.956, -0.456), (0.611, -0.456)), Line((0.611, -0.456), (0.0, 0.0))], closed=True)


class Cause(unittest.TestCase):

    def test_the_outer_parallel_is_kept(self):
        c = d_shape()
        for d in (1.5, -1.5):
            out = parallel.parallel(c, d)
            self.assertEqual(len(out), 1, d)
            self.assertTrue(out[0].closed, d)
            self.assertFalse(parallel.misses(Path(out), Path([c]), 1.5), d)

    def test_the_band_covers_the_contour(self):
        c = d_shape()
        res = parallel.offset_region(Path([c]), -1.5)
        self.assertFalse(parallel.misses(res, Path([c]), 1.5))
        self.assertAlmostEqual(pathops.area(res), pathops.area(pathops.offset(Path([c]), -1.5)), delta=0.02)

    def test_both_offsets_stay_exact(self):
        path = Path([d_shape()])
        for d in (-1.5, 1.5):
            res, exact = parallel.offset_checked(path, d)
            self.assertTrue(exact, d)
            self.assertAlmostEqual(pathops.area(res), pathops.area(pathops.offset(path, d)), delta=0.02)

    def test_double_line_has_both_sides(self):
        self.assertEqual(len(parallel.double_line(Path([d_shape()]), 3.0).contours), 2)


class Exact(unittest.TestCase):

    def test_a_correct_offset_stays_exact(self):
        path = Path([rounded(0, 0, 20, 8, 2), rounded(2, 2, 4, 4, 1)])               # une lettre à trou
        for d in (-0.8, -0.3, 0.5, 2.0):
            res, exact = parallel.offset_checked(path, d)
            self.assertTrue(exact, d)
            self.assertFalse(parallel.misses(res, path, abs(d)), d)

    def test_a_correct_stroke_stays_exact(self):
        path = Path([rounded(0, 0, 20, 8, 2)])
        res, exact = parallel.stroke_checked(path, 1.0)
        self.assertTrue(exact)

    def test_misses_sees_a_contour_on_the_drawing(self):
        path = Path([rect(0, 0, 10, 10)])
        self.assertTrue(parallel.misses(Path([rect(0, 0, 10, 2)]), path, 1.0))       # un bord sur le tracé
        self.assertFalse(parallel.misses(Path([rect(1, 1, 8, 8)]), path, 1.0))       # à 1 mm partout
        self.assertTrue(parallel.misses(Path([rect(1.02, 1.02, 7.96, 7.96)]), path, 1.05))   # à 0,98 au lieu de 1,05 : non
        self.assertFalse(parallel.misses(Path([rect(1.004, 1.004, 7.992, 7.992)]), path, 1.0))   # à 4 µm près : oui
        self.assertFalse(parallel.misses(Path(), path, 1.0))


if __name__ == '__main__':
    unittest.main()
