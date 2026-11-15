"""Round 277 : chanfrein des bords à l'outil conique (TypeEdit : gamme
chanfrein) — largeur voulue sur le dessus, trous compris."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M, simulate as SIM, strategies as S, tpp
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def run(**kw):
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 20, 10), geom.circle((10, 5), 2)]), tool=1))
    setup = M.setup_of(d)
    v = M.CamTool(name='V90', kind='conique', diameter=6, angle=90, tip=0.1)
    setup.tools = [v]
    return S.compute(d, setup, M.Operation(kind='chanfrein_bord', side='exterieur', tool_id=v.id, **kw)), setup


class TestEdgeChamfer(unittest.TestCase):
    def test_width_on_top(self):
        tp, setup = run(chamfer_width=0.5)
        self.assertTrue(all(abs(m.z + 0.5) < 1e-9 for m in tp.moves if m.kind == 'feed'))   # 90° : profondeur = largeur
        sim = SIM.simulate([tp], setup, res=0.02)

        def z(x, y):
            return float(sim.H[int(round((y - sim.y0) / sim.res)), int(round((x - sim.x0) / sim.res))])
        self.assertLess(z(10, 0.3), -0.05)                                         # le bord du dessus est chanfreiné
        self.assertGreater(z(10, 0.6), -0.02)                                      # au-delà de 0,5 mm : intact
        self.assertLess(z(10, 3.2), -0.05)                                         # le trou aussi

    def test_checks(self):
        tp, _s = run(chamfer_width=5.0)
        self.assertTrue(any('trop grande' in w for w in tp.warnings))
        self.assertEqual(tpp.TYPES['CP_Gamme_Chamfer'][1], 'chanfrein_bord')


if __name__ == '__main__':
    unittest.main()
