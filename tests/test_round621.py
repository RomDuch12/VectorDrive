"""Round 621 : zones d'un seul tenant (reprise 3D) réunies par segments de ligne — mêmes zones, mêmes numéros
(ordre du premier point), bien plus vite sur des zones compactes."""
import time
import unittest

import numpy as np

from vectordrive.cam import mill3d


def flood(m):
    """Référence : remplissage de proche en proche (voisins en croix), zones dans l'ordre du premier point."""
    lab = np.zeros(m.shape, dtype=np.int64)
    n = 0
    for y0, x0 in zip(*np.nonzero(m)):
        if lab[y0, x0]:
            continue
        n += 1
        lab[y0, x0] = n
        todo = [(y0, x0)]
        while todo:
            y, x = todo.pop()
            for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= yy < m.shape[0] and 0 <= xx < m.shape[1] and m[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = n
                    todo.append((yy, xx))
    return lab, n


class TestLabel(unittest.TestCase):
    def test_same_as_flood_fill(self):
        rng = np.random.default_rng(7)
        for shape, p in (((40, 60), 0.5), ((25, 25), 0.65), ((1, 30), 0.5), ((30, 1), 0.5)):
            m = rng.random(shape) < p
            lab, n = mill3d.label(m)
            ref, rn = flood(m)
            self.assertEqual(n, rn)
            self.assertTrue((lab == ref).all(), shape)
        self.assertEqual(mill3d.label(np.zeros((5, 5), bool))[1], 0)

    def test_u_shape_joined_late(self):
        m = np.zeros((5, 7), bool)
        m[0:4, 1] = m[0:4, 5] = True
        m[4, 1:6] = True                                                    # deux branches réunies en bas
        lab, n = mill3d.label(m)
        self.assertEqual(n, 1)
        self.assertEqual(int(lab[0, 5]), 1)

    def test_compact_zones_fast(self):
        Y, X = np.mgrid[0:800, 0:800]
        m = np.zeros((800, 800), bool)
        rng = np.random.default_rng(3)
        for _ in range(150):
            cx, cy, r = rng.integers(0, 800, 2).tolist() + [int(rng.integers(5, 40))]
            m |= (X - cx) ** 2 + (Y - cy) ** 2 < r * r
        t = time.time()
        _lab, n = mill3d.label(m)
        self.assertLess(time.time() - t, 0.5)                               # avant : plus d'une seconde
        self.assertGreater(n, 10)


if __name__ == '__main__':
    unittest.main()
