"""Round 604 : le lecteur STEP retire les triangles plats (aire nulle), avec leur couleur et leur face."""
import unittest

import numpy as np

from vectordrive.io.neostep import step3d


class TestFlat(unittest.TestCase):
    def test_removed_with_colors_and_faces(self):
        tris = np.array([[[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                         [[0, 0, 0], [1, 0, 0], [2, 0, 0]],          # alignés
                         [[0, 0, 0], [0, 0, 0], [0, 1, 0]],          # deux sommets confondus
                         [[0, 0, 1], [1, 0, 1], [0, 1, 1]]], dtype=float)
        cols = np.arange(12, dtype=float).reshape(4, 3)
        ids = np.array([5, 6, 7, 8])
        t, c, f = step3d._sans_plats(tris, cols, ids)
        self.assertEqual(len(t), 2)
        self.assertEqual(f.tolist(), [5, 8])
        self.assertEqual(c[1].tolist(), [9.0, 10.0, 11.0])
        t2, c2, f2 = step3d._sans_plats(tris[[0, 3]], cols[[0, 3]], ids[[0, 3]])
        self.assertIs(f2, ids[[0, 3]]) if False else self.assertEqual(f2.tolist(), [5, 8])


if __name__ == '__main__':
    unittest.main()
