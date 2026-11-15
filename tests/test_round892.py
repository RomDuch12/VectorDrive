"""Round 892 : le décalage natif (vectorcraft-pathops, copie modifiée dans natif/vendor) ne jette plus une lettre dont le trou tombe
au milieu, et ne bouche plus le trou d'un cadre qui contient une île. Le point qui sert à reconnaître un contour parasite est pris
hors des trous du contour : avant, il tombait dans le trou ou sur son bord."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import parallel, pathops
from vectordrive.core.geom import Contour, Cubic, Line, Path

ROOT = pathlib.Path(__file__).resolve().parents[1]


def rect(x, y, w, h):
    return Contour([Line((x, y), (x + w, y)), Line((x + w, y), (x + w, y + h)), Line((x + w, y + h), (x, y + h)),
                    Line((x, y + h), (x, y))], closed=True)


def rounded(x, y, w, h, r):
    k = 0.5523 * r
    return Contour([
        Line((x + r, y), (x + w - r, y)), Cubic((x + w - r, y), (x + w - r + k, y), (x + w, y + r - k), (x + w, y + r)),
        Line((x + w, y + r), (x + w, y + h - r)), Cubic((x + w, y + h - r), (x + w, y + h - r + k), (x + w - r + k, y + h), (x + w - r, y + h)),
        Line((x + w - r, y + h), (x + r, y + h)), Cubic((x + r, y + h), (x + r - k, y + h), (x, y + h - r + k), (x, y + h - r)),
        Line((x, y + h - r), (x, y + r)), Cubic((x, y + r), (x, y + r - k), (x + r - k, y), (x + r, y))], closed=True)


def letter():
    """Lettre à trou dont le bord droit du trou passe au centre de la lettre."""
    return Path([rounded(0, 0, 20, 8, 2), rounded(4, 2, 6, 4, 1)])


def framed_island():
    """Cadre de 30 mm (trou de 20 mm) avec une île de 2 mm au milieu du trou."""
    return Path([rect(0, 0, 30, 30), rect(5, 5, 20, 20), rect(14, 14, 2, 2)])


class Native(unittest.TestCase):

    def setUp(self):
        if pathops.available() != 'vectorcraft-pathops':
            self.skipTest('moteur natif absent')

    def test_the_letter_survives_a_small_inset(self):
        for d in (-0.1, -0.3, -0.5):
            res = pathops.offset(letter(), d)
            self.assertEqual(len(res.contours), 2, d)                                 # avant : rien
            self.assertAlmostEqual(pathops.area(res), pathops.area(parallel.offset_region(letter(), d)), delta=0.01)

    def test_miter_and_bevel_joins_too(self):
        for join in ('miter', 'bevel'):
            res = pathops.offset(letter(), -0.3, join)
            self.assertEqual(len(res.contours), 2, join)
            self.assertGreater(pathops.area(res), 100, join)

    def test_the_hole_around_an_island_stays_open(self):
        res = pathops.offset(framed_island(), 1.2)
        self.assertEqual(len(res.contours), 3)
        self.assertAlmostEqual(pathops.area(res), pathops.area(parallel.offset_region(framed_island(), 1.2)), delta=0.05)
        self.assertLess(pathops.area(res), 800)                                       # avant : 1 048 mm², trou bouché

    def test_the_offset_command(self):
        res, exact = parallel.offset_checked(letter(), -0.3)                         # avant : comparé à un résultat vide, rendu vide
        self.assertTrue(exact)
        self.assertAlmostEqual(pathops.area(res), 112.17, delta=0.01)
        out, exact, approx = parallel.offset_job(letter(), [-0.3], 'miter')
        self.assertEqual(len(out), 1)
        self.assertEqual(len(out[0].contours), 2)


class Sources(unittest.TestCase):

    def test_the_modified_copy_is_declared(self):
        vend = ROOT / 'natif' / 'vendor' / 'vectorcraft-pathops'
        if not (ROOT / 'natif').is_dir():
            self.skipTest('sources natives absentes')
        self.assertIn('VectorDrive :', (vend / 'src' / 'offset.rs').read_text(encoding='utf-8'))
        for name in ('LICENSE-MIT', 'LICENSE-APACHE', 'NOTICE', 'Cargo.toml'):
            self.assertTrue((vend / name).is_file(), name)
        self.assertIn('path = "../vendor/vectorcraft-pathops"', (ROOT / 'natif' / 'vdpathops' / 'Cargo.toml').read_text(encoding='utf-8'))
        self.assertIn('natif/vendor/vectorcraft-pathops', (ROOT / 'THIRD_PARTY_NOTICES.md').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
