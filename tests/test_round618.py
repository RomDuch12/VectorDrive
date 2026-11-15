"""Round 618 : reprise 3D — le tour des parois de chaque zone à chaque palier, après le balayage : les lignes de
balayage, posées sur la grille, ne passent pas au ras des parois qui leur sont parallèles (un coin gardait une
bande de matière d'un pas) ; contours calculés sur la zone seule."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np

from tests.test_round591 import feeds, pocket_stl
from vectordrive.cam import mill3d, model, strategies
from vectordrive.core import solids as SO
from vectordrive.core.document import Document


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestRestContours(unittest.TestCase):
    def test_every_corner_cleaned(self):
        f = pocket_stl()                                                  # poche 20 × 10, coins (10|30, 5|15)
        big = model.CamTool(kind='fraise', diameter=6, stepover=0.4, step_down=1.0)
        small = model.CamTool(kind='fraise', diameter=2, stepover=0.4, step_down=1.0)
        st = model.CamSetup(tools=[big, small])
        op = model.Operation(kind='reprise3d', tool_id=small.id, ref_tool_id=big.id, depth=0, model_path=f,
                             resolution=0.1)
        fs = feeds(strategies.compute(Document(), st, op))
        P = np.array([(m.x, m.y, m.z) for m in fs])
        for c in ((10, 5), (30, 5), (10, 15), (30, 15)):
            near = P[np.linalg.norm(P[:, :2] - c, axis=1) < 1.6]
            self.assertTrue(len(near), c)                                 # centre à un rayon des parois (grille 0,1)
            self.assertAlmostEqual(float(near[:, 2].min()), -5.0, delta=0.01)   # au fond (5 µm au-dessus)
            for z in (-1.0, -3.0, -5.0):                                  # à chaque palier
                self.assertTrue((np.abs(near[:, 2] - z) < 0.01).any(), (c, z))

    def test_contours_on_the_zone_only(self):
        T = np.zeros((60, 80))
        T[20:40, 30:50] = -5.0                                            # une cuvette
        m = np.zeros(T.shape, bool)
        m[18:42, 28:52] = True

        class Em:
            def __init__(self):
                self.moves, self.pos = [], None

            def travel(self, x, y, near=None):
                self.pos = (x, y, near if near is not None else 5.0)

            def hop(self, x, y, over, near):
                self.pos = (x, y, near)

            def plunge(self, z):
                self.pos = (self.pos[0], self.pos[1], z)

            def feed(self, x, y, z):
                self.moves.append((x, y, z))
                self.pos = (x, y, z)

            def retract(self):
                pass
        em = Em()
        g = mill3d.Grid(0.0, 0.0, 80, 60, 0.1)
        st = model.CamSetup()
        tool = model.CamTool(kind='fraise', diameter=1)
        op = model.Operation(kind='reprise3d')
        n = mill3d._rest_contours(em, st, op, tool, T, g, -2.0, m)
        self.assertEqual(n, 1)
        P = np.array(em.moves)
        self.assertTrue(np.all((P[:, 0] > 2.8) & (P[:, 0] < 5.2) & (P[:, 1] > 1.8) & (P[:, 1] < 4.2)))   # sur la cuvette
        self.assertTrue(np.allclose(P[:, 2], -2.0))


if __name__ == '__main__':
    unittest.main()
