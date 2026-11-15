"""Round 266 : FAO — lettres prismatiques (relief en V, arête au milieu) :
profondeur calculée d'après le rayon inscrit, flancs à la pente de l'outil,
fond dégagé par les passes latérales ; modèles TypeEdit prismatiques."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import advanced as A, model as M, simulate as SIM, strategies as S, tpp
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def setup_bar(width=10.0):
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 30, width)]), tool=1))
    setup = M.setup_of(d)
    v = M.CamTool(name='V90', kind='conique', diameter=12, angle=90, tip=0.2)
    setup.tools = [v]
    return d, setup, v


class TestPrismatic(unittest.TestCase):
    def test_heights(self):
        d, setup, v = setup_bar()
        reg = S.region([geom.Path([geom.rect(0, 0, 30, 10)]), geom.Path([geom.rect(40, 0, 30, 4)])], 0.01)
        top, low = A.prismatic_heights(reg, v)
        self.assertAlmostEqual(top, 4.9, 2)                                        # (5 − 0,1) / tan 45°
        self.assertAlmostEqual(low, 1.9, 2)

    def test_machined_profile(self):
        d, setup, v = setup_bar()
        op = M.Operation(name='p', kind='prismatique', depth=0.0, step_down=5.0, tool_id=v.id, extension=2.0, prism_rule=0)
        tp = S.compute(d, setup, op)
        self.assertTrue(any('4.900 mm' in w for w in tp.warnings))
        sim = SIM.simulate([tp], setup, res=0.05)

        def z(x, y):
            return float(sim.H[int(round((y - sim.y0) / sim.res)), int(round((x - sim.x0) / sim.res))])
        self.assertAlmostEqual(z(15, 5), 0.0, 2)                                   # arête affleurante
        self.assertAlmostEqual(z(15, 2.5), -2.4, 1)                                # flanc à 45°
        self.assertAlmostEqual(z(15, -1.5), -4.9, 2)                               # fond dégagé autour

    def test_checks_and_template(self):
        d, setup, _v = setup_bar()
        f = M.CamTool(name='F2', kind='fraise', diameter=2)
        setup.tools.append(f)
        tp = S.compute(d, setup, M.Operation(name='p', kind='prismatique', tool_id=f.id))
        self.assertTrue(any('outil conique' in w for w in tp.warnings))
        self.assertEqual(tpp.TYPES['CP_Engraving_Prismatic'][1], 'prismatique')
        self.assertIn('prismatique', M.OP_KINDS)


if __name__ == '__main__':
    unittest.main()
