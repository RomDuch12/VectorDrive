"""Round 893 : le décalage natif (copie modifiée de vectorcraft-pathops) ne jette plus une forme mince, comme un anneau de 0,6 mm,
dans un petit retrait, ni une forme traversée par un trait ouvert. Le point qui sert à reconnaître un contour parasite est cherché
sur le contour aplati à 1 µm au plus (1 % de sa taille avant), et un retrait retire aussi la bande des tracés ouverts."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import parallel, pathops
from vectordrive.core.geom import Contour, Cubic, Line, Path

ROOT = pathlib.Path(__file__).resolve().parents[1]
K = 0.5523


def circle(r):
    pts = [(r, 0.0), (0.0, r), (-r, 0.0), (0.0, -r)]
    tans = [((0, K * r), (K * r, 0)), ((-K * r, 0), (0, K * r)), ((0, -K * r), (-K * r, 0)), ((K * r, 0), (0, -K * r))]
    segs = []
    for i in range(4):
        p0, p3 = pts[i], pts[(i + 1) % 4]
        (a, b), (c, e) = tans[i]
        segs.append(Cubic(p0, (p0[0] + a, p0[1] + b), (p3[0] + c, p3[1] + e), p3))
    return Contour(segs, closed=True)


def ring(r=12.0, w=0.6):
    """Anneau de 24 mm, 0,6 mm d'épaisseur."""
    return Path([circle(r), circle(r - w)])


def slotted(x=7.5, top=6.9):
    """Rectangle de 15 × 13 mm et un trait ouvert qui part de son bord bas."""
    rect = Contour([Line((0, 0), (15, 0)), Line((15, 0), (15, 13)), Line((15, 13), (0, 13)), Line((0, 13), (0, 0))], closed=True)
    return Path([rect, Contour([Line((x, 0), (x, top))], closed=False)])


class Native(unittest.TestCase):

    def setUp(self):
        if pathops.available() != 'vectorcraft-pathops':
            self.skipTest('moteur natif absent')

    def test_a_thin_ring_survives_a_small_inset(self):
        for d in (0.15, 0.2, 0.25):
            res = pathops.offset(ring(), -d)
            self.assertEqual(len(res.contours), 2, d)                                 # avant : rien
            self.assertAlmostEqual(pathops.area(res), pathops.area(parallel.offset_region(ring(), -d)), delta=0.02)

    def test_the_offset_command_keeps_the_ring(self):
        res, exact = parallel.offset_checked(ring(), -0.2)
        self.assertTrue(exact)
        self.assertAlmostEqual(pathops.area(res), 14.71, delta=0.01)
        out, exact, approx = parallel.offset_job(ring(), [-0.2], 'miter')
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(pathops.area(out[0]), 14.71, delta=0.02)

    def test_an_inset_cuts_along_an_open_stroke(self):
        for x, top in ((7.5, 6.9), (4.0, 6.0)):
            res = pathops.offset(slotted(x, top), -0.2)
            # bouts du trait en pointe dans le natif, ronds dans le calcul exact : π·0,2²/2 d'écart
            self.assertAlmostEqual(pathops.area(res), pathops.area(parallel.offset_region(slotted(x, top), -0.2)) + 0.0628, delta=0.01)
        self.assertLess(pathops.area(pathops.offset(slotted(4.0, 6.0), -0.2)), 182)    # avant : 183,96, trait ignoré
        res, exact = parallel.offset_checked(slotted(), -0.5)
        self.assertTrue(exact)

    def test_growth_is_unchanged(self):
        self.assertAlmostEqual(pathops.area(pathops.offset(ring(), 0.3)), pathops.area(parallel.offset_region(ring(), 0.3)), delta=0.02)
        self.assertAlmostEqual(pathops.area(pathops.offset(slotted(), 0.5)), 15 * 13 + 0.5 * 56 + 3.14159 * 0.25, delta=0.05)


class Sources(unittest.TestCase):

    def test_the_modified_copy_is_declared(self):
        if not (ROOT / 'natif').is_dir():
            self.skipTest('sources natives absentes')
        vend = ROOT / 'natif' / 'vendor' / 'vectorcraft-pathops'
        src = (vend / 'src' / 'offset.rs').read_text(encoding='utf-8')
        self.assertIn('const DEEP_TOL: f64 = 1e-3;', src)
        self.assertIn('m[0] && !m[1] && !m[2]', src)
        self.assertIn('1 µm', (vend / 'NOTICE').read_text(encoding='utf-8'))
        self.assertIn('tracés ouverts', (ROOT / 'THIRD_PARTY_NOTICES.md').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
