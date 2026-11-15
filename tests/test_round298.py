"""Round 298 : balayage — surépaisseur propre au cassé d'angle (TypeEdit :
AllowanceSweep, de 0 à la surépaisseur des hachures)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M, strategies as S, tpp
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def run(**kw):
    d = Document()
    d.plate = None
    d.add(Shape(path=geom.Path([geom.rect(0, 0, 30, 10)]), tool=1))
    setup = M.setup_of(d)
    t = M.CamTool(name='F2', diameter=2, stepover=0.4)
    setup.tools = [t]
    return S.compute(d, setup, M.Operation(kind='poche', depth=1, step_down=1, tool_id=t.id, pocket_mode='balayage',
                                           stock=0.5, sweep_contour='apres', **kw))


def lowest_x(tp):
    return min(m.x for m in tp.moves if m.kind == 'feed')


class TestSweepStock(unittest.TestCase):
    def test_contour_stock(self):
        self.assertAlmostEqual(lowest_x(run()), 1.5, 6)                         # rayon 1 + 0,5
        tp = run(sweep_contour_stock=0.1)
        self.assertAlmostEqual(lowest_x(tp), 1.1, 6)                            # cassé d'angle plus près
        self.assertTrue(any("cassé d'angle" in w for w in tp.warnings))
        self.assertAlmostEqual(lowest_x(run(sweep_contour_stock=0.9)), 1.5, 6)  # au plus celle des hachures

    def test_typeedit(self):
        p = tpp.Preset(name='b', kind='CP_Sweeping', sections={
            'SPECIALSWEEPING': {'SweepingMode': '1', 'BreakAngleMode': '3', 'Stepover': '7.e-004',
                                'Allowance': '5.e-004'},
            'Properties': {'AllowanceSweep': '2.e-004'}})
        o = tpp.to_template(p)['operations'][0]
        self.assertAlmostEqual(o['sweep_contour_stock'], 0.2)


if __name__ == '__main__':
    unittest.main()
