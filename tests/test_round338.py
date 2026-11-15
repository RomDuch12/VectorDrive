"""Round 338 : carte de hauteurs d'un maillage — petits triangles traités en
bloc, résultat identique à la boucle triangle par triangle."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np

from vectordrive.cam import advanced as A


def reference(tris, x0, y0, nx, ny, res):
    H = np.full((ny, nx), -np.inf)
    for t in tris:
        xs, ys, zs = t[:, 0], t[:, 1], t[:, 2]
        i0 = max(0, int(math.floor((xs.min() - x0) / res)))
        i1 = min(nx - 1, int(math.ceil((xs.max() - x0) / res)))
        j0 = max(0, int(math.floor((ys.min() - y0) / res)))
        j1 = min(ny - 1, int(math.ceil((ys.max() - y0) / res)))
        if i1 < i0 or j1 < j0:
            continue
        den = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
        if abs(den) < 1e-12:
            continue
        X, Y = np.meshgrid(x0 + np.arange(i0, i1 + 1) * res, y0 + np.arange(j0, j1 + 1) * res)
        l1 = ((ys[1] - ys[2]) * (X - xs[2]) + (xs[2] - xs[1]) * (Y - ys[2])) / den
        l2 = ((ys[2] - ys[0]) * (X - xs[2]) + (xs[0] - xs[2]) * (Y - ys[2])) / den
        l3 = 1.0 - l1 - l2
        inside = (l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9)
        Z = l1 * zs[0] + l2 * zs[1] + l3 * zs[2]
        sub = H[j0:j1 + 1, i0:i1 + 1]
        np.maximum(sub, np.where(inside, Z, -np.inf), out=sub)
    return H


class TestRaster(unittest.TestCase):
    def test_same_as_loop(self):
        rng = np.random.default_rng(3)
        small = rng.random((3000, 3, 3)) * [0.5, 0.5, 5] + rng.random((3000, 1, 3)) * [20, 20, 0]
        big = rng.random((40, 3, 3)) * [15, 15, 5]
        vertical = np.array([[[1, 1, 0], [2, 2, 0], [1, 1, 5]]], float)          # sans aire vue de dessus
        outside = np.array([[[50, 50, 1], [51, 50, 1], [50, 51, 1]]], float)
        tris = np.concatenate([small, big, vertical, outside])
        args = (-1.0, -1.0, 230, 230, 0.1)
        H = A.heightmap_from_triangles(tris, *args)
        self.assertTrue(np.array_equal(H, reference(tris, *args)))
        self.assertTrue(np.isfinite(H).any())
        self.assertEqual(A.heightmap_from_triangles(np.zeros((0, 3, 3)), *args).max(), -np.inf)


if __name__ == '__main__':
    unittest.main()
