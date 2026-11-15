"""Round 354 : modèles TypeEdit — « Supprimer sur la dernière passe »
(AllowanceCheck) : la surépaisseur est enlevée par une passe de finition."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import tpp


class TestAllowance(unittest.TestCase):
    def test_mapping(self):
        p = tpp.Preset(name='d', kind='CP_Cutting_3D', sections={'SPECIALDECOUPE': {
            'DecInternal': '2', 'AllowanceEdit': '0.0002', 'AllowanceCheck': '1'}})
        o = tpp.to_template(p)['operations'][0]
        self.assertAlmostEqual(o['stock'], 0.2)
        self.assertTrue(o['finish'])
        p.sections['SPECIALDECOUPE']['AllowanceCheck'] = '0'
        self.assertFalse(tpp.to_template(p)['operations'][0]['finish'])


if __name__ == '__main__':
    unittest.main()
