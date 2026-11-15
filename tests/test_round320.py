"""Round 320 : enveloppes supplémentaires (déformations des logiciels de
dessin vectoriel) — arc inférieur, coquilles, drapeau, poisson, montée, œil
de poisson, gonfler, compresser, torsion."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import envelope as EN, geom
from vectordrive.core.document import Shape

BOX = (0.0, 0.0, 100.0, 20.0)


def f(kind, amount=50.0):
    return EN.mapping(EN.EnvelopeSpec(kind=kind, amount=amount), BOX)


class TestWarps(unittest.TestCase):
    def test_edges(self):
        self.assertEqual(f('arc_bas')((50, 20)), (50, 20))                  # haut droit
        self.assertAlmostEqual(f('arc_bas')((50, 0))[1], -10)                # bas arrondi
        self.assertAlmostEqual(f('coquille_haut')((0, 20))[1], 30)           # coins du haut tirés
        self.assertAlmostEqual(f('coquille_haut')((50, 20))[1], 20)
        self.assertAlmostEqual(f('montee')((100, 0))[1], 10)
        self.assertAlmostEqual(f('montee')((0, 0))[1], 0)
        self.assertAlmostEqual(f('drapeau')((0, 10))[1], 10)

    def test_radial(self):
        x, y = f('oeil')((60, 10))
        self.assertGreater(x, 60)                                           # grossi depuis le centre
        self.assertEqual(f('oeil')((50, 10)), (50, 10))
        x, y = f('torsion', 100)((55, 10))
        self.assertNotAlmostEqual(y, 10)                                    # tourné
        self.assertAlmostEqual(f('torsion', 100)((100, 20))[0], 100)        # coins fixes
        gx, gy = f('gonfler')((100, 10))
        self.assertGreater(gx, 100)
        cx, cy = f('compresser')((50, 20))
        self.assertLess(cy, 20)

    def test_build_all(self):
        s = Shape(path=geom.Path([geom.rect(0, 0, 100, 20)]))
        for k in EN.KINDS:
            self.assertIn(k, EN.NAMES)
            g = EN.build([s], EN.EnvelopeSpec(kind=k, amount=30))
            self.assertIsNotNone(g, k)


if __name__ == '__main__':
    unittest.main()
