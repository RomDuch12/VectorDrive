"""Round 270 : FAO — profondeurs de passe variables (« 0,8 0,6 0,4 », la
dernière répétée) ; modèles TypeEdit : passes NBSLICES différentes,
plongée angulaire (angle), finition (surépaisseur, sans le cadre)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M, strategies as S, tpp
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


class TestPasses(unittest.TestCase):
    def test_parse_and_levels(self):
        self.assertEqual(S.parse_depths('0,8 0.6 ; 0,4 / x -1'), [0.8, 0.6, 0.4])
        op = M.Operation(depth=2.0, pass_depths='0,8 0,6 0,4')
        self.assertEqual(S.op_levels(op, M.CamTool()), [-0.8, -1.4, -1.8, -2.0])
        op.pass_depths = '0.5'
        self.assertEqual(S.op_levels(op, M.CamTool()), [-0.5, -1.0, -1.5, -2.0])
        op.pass_depths = ''
        op.step_down = 1.0
        self.assertEqual(S.op_levels(op, M.CamTool()), [-1.0, -2.0])

    def test_used_by_contour(self):
        d = Document()
        d.plate = None
        d.add(Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]), tool=1))
        setup = M.setup_of(d)
        t = M.CamTool(name='F2', diameter=2)
        setup.tools = [t]
        tp = S.compute(d, setup, M.Operation(kind='contour', side='exterieur', depth=1.5, tool_id=t.id,
                                             pass_depths='1 0.5'))
        zs = sorted({round(m.z, 6) for m in tp.moves if m.kind == 'feed'}, reverse=True)
        self.assertEqual(zs, [-1.0, -1.5])


class TestTypeEdit(unittest.TestCase):
    def preset(self, sections, kind='CP_Cutting_3D'):
        return tpp.Preset(name='essai', kind=kind, sections=sections)

    def test_mapping(self):
        p = self.preset({'PROFONDEUR': {'ZBOTTOM': '1.2e-003', 'NBSLICES': '2', 'NBSLICES1': '8.e-004',
                                        'NBSLICES2': '4.e-004'},
                         'FAO_NEWPARAMGLOB': {'PLONGEEANGULAIRE_ATIVE': '1',
                                              'PLONGEEANGULAIRE_ANGLE': str(math.radians(9))},
                         'Properties': {'iEnable': '0'}})
        o = tpp.to_template(p)['operations'][0]
        self.assertEqual(o['pass_depths'], '0.8 0.4')
        self.assertTrue(o['ramp'])
        self.assertAlmostEqual(o['ramp_angle'], 9.0)
        same = self.preset({'PROFONDEUR': {'ZBOTTOM': '1.e-003', 'NBSLICES': '2', 'NBSLICES1': '5.e-004',
                                           'NBSLICES2': '5.e-004'},
                            'FAO_NEWPARAMGLOB': {'PLONGEEANGULAIRE_ATIVE': '0'}})
        o2 = tpp.to_template(same)['operations'][0]
        self.assertEqual(o2['pass_depths'], '')                                    # passes égales : step_down
        self.assertFalse(o2['ramp'])
        fin = self.preset({'SPECIALFINITION': {'Allowance': '1.e-004', 'SkipExternal': '1'}}, 'CP_Finishing')
        o3 = tpp.to_template(fin)['operations'][0]
        self.assertAlmostEqual(o3['stock'], 0.1)
        self.assertTrue(o3['finish_skip_frame'])


if __name__ == '__main__':
    unittest.main()
