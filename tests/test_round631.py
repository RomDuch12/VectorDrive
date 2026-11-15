"""Round 631 : moteur natif (vdpathops) — le balayage de linesweeper ne boucle
plus sans fin quand deux segments presque confondus s'échangent à la même
hauteur (borne de sûreté : erreur, repli immédiat) ; la forme du fuzz qui
bloquait 20 s (délai, puis fil abandonné qui tournait jusqu'à la fermeture)
se normalise en moins d'une seconde."""
import pathlib
import sys
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'outils'))

from vectordrive.core import pathops  # noqa: E402
from vectordrive.core.geom import Path  # noqa: E402


@unittest.skipUnless(pathops.available() == 'vectorcraft-pathops', 'moteur natif absent')
class TestSweepBound(unittest.TestCase):
    def test_fuzz_shape_no_longer_hangs(self):
        import fuzz_geom as F
        before = list(pathops.stuck_calls)
        t = time.perf_counter()
        problems = F.run_case(11001298)                # l'ombre portée de cette forme bloquait le moteur
        self.assertLess(time.perf_counter() - t, 8.0)                     # 20 s (délai) avant
        self.assertEqual(problems, [])
        self.assertEqual(pathops.stuck_calls, before)                     # aucun fil abandonné

    def test_ordinary_shapes_unchanged(self):
        from vectordrive.core import geom
        two = Path([geom.rect(0, 0, 10, 10), geom.rect(5, 5, 10, 10)])
        self.assertAlmostEqual(pathops.area(pathops.normalize(two, evenodd=False)), 175.0, delta=1e-6)   # union
        self.assertAlmostEqual(pathops.area(pathops.normalize(two)), 150.0, delta=1e-6)                  # pair-impair


if __name__ == '__main__':
    unittest.main()
