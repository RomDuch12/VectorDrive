"""Round 279 : modèles TypeEdit « gamme » — une étape par outil (ébauche à
la poche, reprise des restes, finition 2,5D) avec passes, recouvrements,
profondeurs, balayage ; l'ancienne opération « gamme » est calculée en
finition avec un avertissement."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M, strategies as S, tpp
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def preset(tools, **gamme):
    p = tpp.Preset(name='Gamme essai', kind='CP_Sequence_MultiTool', sections={
        'SPECIALGAMME_NEW': {'ZBottom': '3.e-003', 'NbSlices_0': '2', 'Stepover_0': '1.5e-003', 'NbSlices_1': '3',
                             'Sweeping_0': '1', 'AngleDecal_0': str(math.pi / 2), 'Allowance': '1.e-004', **gamme}})
    p.tools = tools
    return p


class TestGamme(unittest.TestCase):
    def test_two_tools(self):
        rough = M.CamTool(name='Fr 3', kind='fraise', diameter=3)
        v = M.CamTool(name='V 45', kind='conique', diameter=6, angle=45, tip=0.4)
        ops = tpp.to_template(preset([rough, v]))['operations']
        self.assertEqual([o['kind'] for o in ops], ['poche', 'vcarve'])
        r, f = ops
        self.assertEqual((r['depth'], r['step_down'], r['pocket_mode'], r['sweep_angle']), (3.0, 1.5, 'balayage', 90.0))
        self.assertAlmostEqual(r['stepover_mm'], 1.5)
        self.assertAlmostEqual(r['stock'], 0.1 + 3 * math.tan(math.radians(22.5)))  # 886 : le rayon + la pente du cône
        self.assertAlmostEqual(f['stock'], 0.1)
        self.assertEqual((f['depth'], f['vcarve_step']), (3.0, 1.0))                # 886 : la profondeur de la gamme, en 3 passes
        self.assertEqual(f['ref_tool_id'], r['tool_id'])

    def test_three_tools(self):
        ts = [M.CamTool(name='Fr 3', diameter=3), M.CamTool(name='Fr 2', diameter=2),
              M.CamTool(name='V', kind='conique', diameter=6, angle=45, tip=0.4)]
        ops = tpp.to_template(preset(ts, NbSlices_2='2'))['operations']
        self.assertEqual([o['kind'] for o in ops], ['poche', 'reste', 'vcarve'])
        self.assertEqual(ops[1]['ref_tool_id'], ops[0]['tool_id'])
        self.assertEqual(ops[2]['ref_tool_id'], ops[1]['tool_id'])

    def test_legacy_gamme_op(self):
        d = Document()
        d.plate = None
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 6, 3)]), tool=1))
        setup = M.setup_of(d)
        v = M.CamTool(name='V', kind='conique', diameter=6, angle=60, tip=0.2)
        setup.tools = [v]
        tp = S.compute(d, setup, M.Operation(kind='gamme', depth=0.3, tool_id=v.id))
        self.assertTrue(any('réimporter' in w for w in tp.warnings))
        self.assertTrue(any(m.kind == 'feed' for m in tp.moves))


if __name__ == '__main__':
    unittest.main()
