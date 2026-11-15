"""Round 294 : fer à dorer gaufrant (TypeEdit : CP_Embossing) — formes
laissées en relief, demi-profil de galbe autour en passes 2D
concentriques."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import advanced as A, model as M, simulate as SIM, strategies as S, tpp
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


class TestEmboss(unittest.TestCase):
    def test_profile(self):
        op = M.Operation(depth=1.0, emboss_edge=0.3, emboss_width=2.0)
        zs = [A.emboss_depth(op, x) for x in (0, 0.3, 0.8, 1.3, 1.8, 2.3, 3)]
        self.assertEqual((zs[0], zs[1]), (0.0, 0.0))                              # largeur laissée au bord
        self.assertEqual(zs[-2:], [1.0, 1.0])
        self.assertTrue(all(a <= b + 1e-12 for a, b in zip(zs, zs[1:])))         # de plus en plus profond

    def test_machined(self):
        d = Document()
        d.plate = None
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 20, 8)]), tool=1))
        setup = M.setup_of(d)
        f = M.CamTool(name='F0.5', diameter=0.5, step_down=0.5)
        setup.tools = [f]
        op = M.Operation(kind='fer_dorer', depth=1.0, tool_id=f.id, emboss_edge=0.3, emboss_width=2.0,
                         resolution=0.1, emboss_side='autour')
        tp = S.compute(d, setup, op)
        sim = SIM.simulate([tp], setup, res=0.05)

        def z(x, y):
            return float(sim.H[int(round((y - sim.y0) / sim.res)), int(round((x - sim.x0) / sim.res))])
        self.assertEqual(z(10, 4), 0.0)                                           # la lettre reste
        self.assertAlmostEqual(z(10, -2.3), -1.0, 2)
        self.assertLess(z(10, -1.3), -0.5)                                        # le profil de TE13 : raide au bord, plat au fond
        self.assertGreater(z(10, -0.45), z(10, -1.3))
        self.assertEqual(tpp.TYPES['CP_Embossing'][1], 'fer_dorer')


if __name__ == '__main__':
    unittest.main()
