"""Round 626 : maillage STEP — le tore est périodique aussi autour de son
tube : une face dont le bord passe par l'angle ±180° du tube (côté
intérieur de l'anneau) ne déborde plus de l'autre côté du tube (un quart
de tore recouvrait le congé voisin et le volume ne fermait pas)."""
import math
import unittest

import numpy as np

from vectordrive.io.neostep import step3d as ST

A, B = 16.0, 2.0


def quarter_loop(flip=True):
    """Bord d'un quart de tube sur un quart d'anneau : θ de 0 à π/2, φ de −π
    (côté intérieur, l'angle ±π) à −π/2 ; sur le côté intérieur, φ = +π et −π
    alternent (le même point, au sinus près)."""
    n = 24
    th = np.linspace(0, math.pi / 2, n)
    ph = np.linspace(-math.pi, -math.pi / 2, n)
    inner = [(t, (math.pi if (flip and k % 2) else -math.pi)) for k, t in enumerate(th)]
    side1 = [(math.pi / 2, p) for p in ph[1:]]
    outer = [(t, -math.pi / 2) for t in th[::-1][1:]]
    side0 = [(0.0, p) for p in ph[::-1][1:-1]]
    uv = np.array(inner + side1 + outer + side0)
    return uv


class TestTorusSeam(unittest.TestCase):
    def setUp(self):
        self.param = ST._Tore(np.eye(3), np.zeros(3), A, B, 0.01)

    def mesh(self, flip):
        uv = quarter_loop(flip)
        pts = self.param.point(np.column_stack([uv[:, 0] * A, uv[:, 1] * B]))
        return ST._trianguler(self.param, [(pts, True)], 0.01)

    def test_area_and_no_overflow(self):
        expected = B * (A * math.pi / 2 + B * (math.sin(-math.pi / 2) - math.sin(-math.pi))) * math.pi / 2
        for flip in (False, True):
            t = self.mesh(flip)
            self.assertIsNotNone(t)
            area = 0.5 * np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1).sum()
            self.assertAlmostEqual(area, expected, delta=0.02 * expected)        # pas l'autre côté du tube
            P = t.reshape(-1, 3)
            rho = np.hypot(P[:, 0], P[:, 1])
            self.assertTrue((rho <= A + 1e-6).all())                             # côté intérieur seulement
            self.assertTrue((P[:, 2] <= 1e-6).all())                             # moitié basse du tube

    def test_boundary_points_exact(self):
        uv = quarter_loop(True)
        pts = self.param.point(np.column_stack([uv[:, 0] * A, uv[:, 1] * B]))
        t = ST._trianguler(self.param, [(pts, True)], 0.01)
        V = {tuple(np.round(p, 12)) for p in t.reshape(-1, 3)}
        hits = sum(tuple(np.round(p, 12)) in V for p in pts)
        self.assertEqual(hits, len(pts))                                         # les points des arêtes, tels quels


if __name__ == '__main__':
    unittest.main()
