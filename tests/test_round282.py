"""Round 282 : gravure 2,5D en ligne médiane (TypeEdit : intaille
optimisée) — axe médian (Voronoï du bord), profondeur selon la
demi-largeur locale ; modèles TypeEdit Intaille."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import advanced as A, model as M, simulate as SIM, strategies as S, tpp
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


class TestMedialAxis(unittest.TestCase):
    def test_shapes(self):
        rect = S.region([geom.Path([geom.rect(0, 0, 20, 4)])], 0.01)
        ch = A.medial_axis(rect, 0.1)
        self.assertEqual(len(ch), 5)                                               # axe + 4 branches de coin
        longest = max(ch, key=len)
        self.assertTrue(all(abs(y - 2.0) < 1e-6 for _x, y in longest))
        penta = S.region([geom.Path([geom.polygon((0, 0), 10, 5, 90.0)])], 0.01)
        self.assertEqual(len(A.medial_axis(penta, 0.1)), 5)

    def test_vcarve_axis(self):
        d = Document()
        d.plate = None
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 20, 4)]), tool=1))
        setup = M.setup_of(d)
        v = M.CamTool(name='V60', kind='conique', diameter=6, angle=60, tip=0.1)
        setup.tools = [v]
        tp = S.compute(d, setup, M.Operation(kind='vcarve', depth=0.0, tool_id=v.id, vcarve_mode='axe', gravure_rule=880))
        want = (2 - 0.05) / math.tan(math.radians(30))
        self.assertAlmostEqual(min(m.z for m in tp.moves), -want, 2)
        self.assertEqual(sum(1 for m in tp.moves if m.kind == 'plunge'), 5)        # une descente par branche
        sim = SIM.simulate([tp], setup, res=0.02)

        def z(x, y):
            return float(sim.H[int(round((y - sim.y0) / sim.res)), int(round((x - sim.x0) / sim.res))])
        self.assertAlmostEqual(z(10, 2), -want, 1)
        self.assertGreater(z(10, -0.1), -0.01)                                     # rien hors de la lettre

    def test_typeedit(self):
        o = tpp.to_template(tpp.Preset(name='Intaille', kind='CP_Intaglio'))['operations'][0]
        self.assertEqual((o['kind'], o['vcarve_mode']), ('vcarve', 'axe'))


if __name__ == '__main__':
    unittest.main()
