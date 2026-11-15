"""Round 353 : modèles TypeEdit — entrée / sortie tangentielles reprises
(ENTRETANGENTIELLE ModeIOtgt, rayon ES_TANGEANCIELLE_RACORD)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import tpp


class TestLeads(unittest.TestCase):
    def test_mapping(self):
        p = tpp.Preset(name='d', kind='CP_Cutting_3D', sections={
            'SPECIALDECOUPE': {'DecInternal': '2'}, 'ENTRETANGENTIELLE': {'ModeIOtgt': '2'},
            'FAO_NEWPARAMGLOB': {'ES_TANGEANCIELLE_RACORD': '0.006', 'ES_TANGEANCIELLE_DIST': '0.012'}})
        o = tpp.to_template(p)['operations'][0]
        self.assertEqual((o['lead_mode'], o['lead_in'], o['lead_out'], o['lead_transition']), ('percage', 12.0, 12.0, 6.0))
        p.sections['ENTRETANGENTIELLE'] = {'ModeIOtgt': '0'}
        o = tpp.to_template(p)['operations'][0]
        self.assertEqual(o['lead_in'], 0.0)
        p.sections['ENTRETANGENTIELLE'] = {'ModeIOtgt': '2'}
        del p.sections['FAO_NEWPARAMGLOB']
        self.assertEqual(tpp.to_template(p)['operations'][0]['lead_in'], 2.0)


if __name__ == '__main__':
    unittest.main()
