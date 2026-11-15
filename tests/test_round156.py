"""Round 156 : question à l'opérateur (Oui / Non) et appel d'un programme
de la machine — instructions de NeoDrive."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import instructions as I, model, strategies as S
from vectordrive.core.document import Document


class TestInstructions(unittest.TestCase):
    def test_question(self):
        self.assertEqual(I.params_of('question', {}), {'message': 'Continuer l\'usinage ?', 'park': True})
        s = model.CamSetup()
        op = model.Operation(kind='instruction', instruction='question', params={'park': False})
        s.operations = [op]
        tp = S.compute(Document(), s, op)
        self.assertEqual((tp.moves, tp.warnings), ([], []))
        self.assertEqual(tp.cycles[0]['params']['park'], False)

    def test_program_call_warns_without_path(self):
        s = model.CamSetup()
        op = model.Operation(kind='instruction', instruction='appel_programme', params={'name': 'Série'})
        s.operations = [op]
        self.assertTrue(S.compute(Document(), s, op).warnings)
        op.params['path'] = r'C:\Programmes\serie.simpl'
        self.assertEqual(S.compute(Document(), s, op).warnings, [])


if __name__ == '__main__':
    unittest.main()
