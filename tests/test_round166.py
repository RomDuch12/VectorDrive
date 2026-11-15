"""Round 166 : saisie de l'opérateur au lancement (NeoDrive : Paramètres opérateur)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import instructions as I, model, strategies as S
from vectordrive.core.document import Document


class TestInputs(unittest.TestCase):
    def test_parse(self):
        fields, problems = I.input_fields('Commande ; texte ; A1\nZ\n\nX ; Couleur\nN ; Quantité ; 4 ; pièces ; nb')
        self.assertEqual([(f['label'], f['type'], f['default'], f['unit'], f['var']) for f in fields],
                         [('Commande', 'Texte', 'A1', '', ''), ('Z', 'Position', '', '', ''),
                          ('N', 'Quantité', '4', 'pièces', 'nb')])
        self.assertEqual(len(problems), 1)
        self.assertIn('ligne 4', problems[0])

    def test_compute_warnings(self):
        s = model.CamSetup()
        op = model.Operation(kind='instruction', instruction='saisie_operateur', params={'champs': 'A ; Couleur'})
        s.operations = [op]
        w = S.compute(Document(), s, op).warnings
        self.assertTrue(any('Couleur' in x for x in w) and any('aucun champ' in x for x in w))
        op.params = {}                                                        # défaut : un champ texte
        self.assertEqual(S.compute(Document(), s, op).warnings, [])

    def test_defaults(self):
        p = I.params_of('saisie_operateur', {})
        self.assertEqual(p['caption'], 'Réglages pièce')
        self.assertEqual(I.input_fields(p['champs'])[0][0]['type'], 'Texte')


if __name__ == '__main__':
    unittest.main()
