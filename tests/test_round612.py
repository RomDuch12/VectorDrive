"""Round 612 : maillage fermé des corps d'un STEP — languettes posées en double par deux faces voisines (dos
à dos) retirées toutes les deux, trous qui se touchent en un sommet bouchés chacun, débris sans volume
écartés : les corps d'un moule se ferment et deviennent des volumes du dessin."""
import unittest

import numpy as np

from vectordrive.core import solids as SO
from vectordrive.core import watertight as WT

#: faces d'un cube : origine, u, v (u × v vers l'extérieur)
FACES = (((0, 0, 0), (0, 1, 0), (1, 0, 0)), ((0, 0, 1), (1, 0, 0), (0, 1, 0)), ((0, 0, 0), (1, 0, 0), (0, 0, 1)),
         ((0, 1, 0), (0, 0, 1), (1, 0, 0)), ((0, 0, 0), (0, 0, 1), (0, 1, 0)), ((1, 0, 0), (0, 1, 0), (0, 0, 1)))


def grid_box(n=4, size=10.0, skip=()):
    """Cube triangulé n × n par face, orienté vers l'extérieur ; `skip` : (face, i, j) des cases retirées."""
    out = []
    h = size / n
    for f, (o, u, v) in enumerate(FACES):
        o, u, v = np.array(o, float) * size, np.array(u, float), np.array(v, float)
        for i in range(n):
            for j in range(n):
                if (f, i, j) in skip:
                    continue
                p = [o + ((i + a) * u + (j + b) * v) * h for a, b in ((0, 0), (1, 0), (1, 1), (0, 1))]
                out += [[p[0], p[1], p[2]], [p[0], p[2], p[3]]]
    return np.array(out)


class TestLoops(unittest.TestCase):
    def test_simple_loops(self):
        self.assertEqual(WT.simple_loops([1, 2, 3, 4, 2, 5, 6]), [[2, 3, 4], [1, 2, 5, 6]])
        self.assertEqual(WT.simple_loops([1, 2, 3]), [[1, 2, 3]])
        self.assertEqual(WT.simple_loops([1, 2, 1, 3, 4]), [[1, 3, 4]])             # aller-retour : rien

    def test_drop_fins(self):
        idx = np.array([[0, 1, 2], [1, 0, 3], [0, 1, 3], [4, 5, 6], [5, 6, 4]])
        self.assertEqual(WT.drop_fins(idx).tolist(), [[0, 1, 2], [4, 5, 6], [5, 6, 4]])  # même sens : gardés


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestSolids(unittest.TestCase):
    def test_fin_back_to_back(self):
        box = grid_box(1)
        a, b, c = np.array([0, 0, 10.0]), np.array([10, 0, 10.0]), np.array([5, -3, 10.0])
        fin = np.array([[a, b, c], [b, a, c]])                            # languette posée par deux faces
        v, idx, rep = WT.repair(np.concatenate([box, fin]))
        self.assertEqual((rep['ailettes'], rep['bords'], rep['mauvaises']), (1, 0, 0))
        self.assertAlmostEqual(WT.to_solid(np.concatenate([box, fin])).volume(), 1000.0, 6)

    def test_holes_touching_at_a_vertex(self):
        box = grid_box(4, skip={(1, 1, 1), (1, 2, 2)})                    # deux cases en diagonale
        v, idx, rep = WT.repair(box)
        self.assertEqual((rep['bords'], rep['mauvaises']), (0, 0))
        self.assertAlmostEqual(WT.to_solid(box).volume(), 1000.0, 6)

    def test_zero_volume_debris_dropped(self):
        P = np.array([[20, 20, 20], [20.01, 20, 20], [20, 20.01, 20], [20, 20, 20.01]])
        tet = np.array([[P[0], P[2], P[1]], [P[0], P[1], P[3]], [P[0], P[3], P[2]], [P[1], P[2], P[3]]])
        s = WT.to_solid(np.concatenate([grid_box(2), tet]))
        self.assertAlmostEqual(s.volume(), 1000.0, 6)
        self.assertEqual(len(s.manifold().decompose()), 1)
        two = WT.to_solid(np.concatenate([grid_box(2), grid_box(1, 2.0) + 20]))   # un vrai second bloc : gardé
        self.assertAlmostEqual(two.volume(), 1008.0, 6)


if __name__ == '__main__':
    unittest.main()
