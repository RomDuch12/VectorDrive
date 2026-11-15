"""Round 372 : ombrage — parties éclairées (TypeEdit : Effet ombrage) : le
liseré de l'objet du côté de la lumière."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import geom, shadow as SH
from vectordrive.core.document import Shape


def bbox(p):
    return tuple(round(v, 6) for v in p.bbox())


class TestLit(unittest.TestCase):
    def test_lit_rim(self):
        sq = geom.Path([geom.rect(0, 0, 10, 10)])
        spec = SH.ShadowSpec(kind='eclairage', angle=0.0, distance=2.0)      # ombre vers la droite : lumière à gauche
        lit = SH.shadow_path(sq, spec)
        self.assertEqual(bbox(lit), (0, 0, 2, 10))                          # bande de 2 mm du côté gauche
        spec.angle = -90.0                                                  # ombre vers le bas : bande du haut
        self.assertEqual(bbox(SH.shadow_path(sq, spec)), (0, 8, 10, 10))

    def test_gap_and_group(self):
        sq = geom.Path([geom.rect(0, 0, 10, 10)])
        spec = SH.ShadowSpec(kind='eclairage', angle=0.0, distance=2.0, gap=0.5)
        self.assertEqual(bbox(SH.shadow_path(sq, spec)), (0.5, 0.5, 2, 9.5))
        g = SH.build([Shape(path=sq)], spec)
        self.assertEqual(g.children[1].name, 'Éclairage')
        self.assertEqual(g.extra['shadow']['kind'], 'eclairage')


if __name__ == '__main__':
    unittest.main()
