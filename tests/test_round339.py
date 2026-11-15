"""Round 339 : compensation d'une fraise plate (reliefs, surfaces 3D) par
maxima glissants — identique à la double boucle."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np

from vectordrive.cam import advanced as A
from vectordrive.cam.model import CamTool


def reference(H, res, tool):
    r = tool.diameter / 2
    k = max(0, int(math.ceil(r / res)))
    ny, nx = H.shape
    P = np.zeros((ny + 2 * k, nx + 2 * k))
    P[k:k + ny, k:k + nx] = H
    T = np.full(H.shape, -np.inf)
    for dy in range(-k, k + 1):
        for dx in range(-k, k + 1):
            prof = A.tool_profile(tool, np.array([math.hypot(dx, dy) * res]))[0]
            if math.isfinite(prof):
                np.maximum(T, P[k + dy:k + dy + ny, k + dx:k + dx + nx] - prof, out=T)
    return T


class TestFlat(unittest.TestCase):
    def test_same(self):
        rng = np.random.default_rng(7)
        H = rng.random((60, 80)) * 3 - 1
        for d, res in ((0.3, 0.1), (1.0, 0.1), (2.5, 0.1), (3.0, 0.07), (0.05, 0.1)):
            t = CamTool(kind='fraise', diameter=d)
            self.assertTrue(np.array_equal(A.compensate(H, res, t), reference(H, res, t)), (d, res))

    def test_ball_unchanged(self):
        rng = np.random.default_rng(8)
        H = rng.random((30, 30))
        t = CamTool(kind='boule', diameter=1.0)
        self.assertTrue(np.array_equal(A.compensate(H, 0.1, t), reference(H, 0.1, t)))


if __name__ == '__main__':
    unittest.main()
