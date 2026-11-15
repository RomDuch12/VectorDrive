"""Round 355 : gamme TypeEdit « chanfrein » importée en ses étapes —
chanfrein des bords puis découpes, outils de la fiche dans l'ordre."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M, tpp


def preset():
    g = {'ModeExternal': '1'}
    for i, (c2d, h, L, zb, n, allow) in enumerate(((1, 0.003, 0.00424264068711928, 0.003, 1, 0),
                                                    (0, 0.01, 0.01, 0.01, 1, 0), (0, 0.01, 0.01, 0.01, 2, -0.0005))):
        g.update({f'Chamfer2D_{i}': str(c2d), f'ChamferHeight_{i}': str(h), f'ChamferLength_{i}': str(L),
                  f'ZBottom_{i}': str(zb), f'NbSlices_{i}': str(n), f'AllowanceCutting_{i}': str(allow),
                  f'climbMilling_{i}': '2', f'AddLinks_{i}': '0'})
    p = tpp.Preset(name='Chanfrein', kind='CP_Gamme_Chamfer', sections={'SPECIALGAMME_NEW': g})
    p.tools = [M.CamTool(name='V45', kind='conique', diameter=12, angle=90, tip=0.2),
               M.CamTool(name='F6', diameter=6), M.CamTool(name='F3', diameter=3)]
    return p


class TestChamferGamme(unittest.TestCase):
    def test_steps(self):
        t = tpp.to_template(preset())
        ops = t['operations']
        self.assertEqual([o['kind'] for o in ops], ['chanfrein_bord', 'contour', 'contour'])
        self.assertAlmostEqual(ops[0]['chamfer_width'], 3.0, 3)
        self.assertEqual((ops[1]['depth'], ops[1]['step_down']), (10.0, 10.0))
        self.assertEqual((ops[2]['depth'], ops[2]['step_down']), (10.0, 5.0))
        self.assertEqual(ops[2]['stock'], 0.0)                              # surépaisseur négative ignorée
        self.assertTrue(all(o['side'] == 'exterieur' and o['climb'] for o in ops))
        ids = [x['id'] for x in t['tools']]
        self.assertEqual([o['tool_id'] for o in ops], ids)


if __name__ == '__main__':
    unittest.main()
