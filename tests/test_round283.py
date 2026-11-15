"""Round 283 : sens d'usinage des modèles TypeEdit — climbMilling 1 = en
opposition, 2 = en avalant (ordre des boutons des fenêtres de TypeEdit 13) ;
gravure 3D TypeEdit (SPECIALGRAVURE : pas, sens, cadre)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import tpp


def op(kind, **sections):
    return tpp.to_template(tpp.Preset(name='m', kind=kind, sections=sections))['operations'][0]


class TestClimb(unittest.TestCase):
    def test_cutting(self):
        self.assertFalse(op('CP_Cutting_3D', SPECIALDECOUPE={'climbMilling': '1'})['climb'])
        self.assertTrue(op('CP_Cutting_3D', SPECIALDECOUPE={'climbMilling': '2'})['climb'])

    def test_engraving_and_finishing(self):
        g = op('CP_Engraving_3D', SPECIALGRAVURE={'climbMilling': '2', 'Stepover': '5.e-005', 'SkipExternal': '1'})
        self.assertEqual((g['climb'], g['resolution'], g['finish_skip_frame']), (True, 0.05, True))
        self.assertFalse(op('CP_Engraving_3D', SPECIALGRAVURE={'climbMilling': '1'})['climb'])
        self.assertTrue(op('CP_Finishing', SPECIALFINITION={'climbMilling': '2'})['climb'])


if __name__ == '__main__':
    unittest.main()
