"""Round 202 : bloc de programme paramétré ({p1} … {p6})."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import instructions as INS, model, strategies as S
from vectordrive.core.document import Document


class TestBloc(unittest.TestCase):
    def test_substitution(self):
        lines = INS.bloc_lines({'texte': 'Absolute X={p1} Y={p2}\n\n  Feed {p3}\n{p7}', 'p1': 12.5, 'p2': -3,
                                'p3': 0.000125})
        self.assertEqual(lines, ['Absolute X=12.5 Y=-3', '  Feed 0.000125', '{p7}'])     # inconnu laissé
        self.assertEqual(INS.number(1e-7), '0')
        self.assertEqual(INS.number(2.0), '2')
        self.assertEqual(INS.params_of('bloc', {})['p6'], 0.0)

    def test_cycle_params(self):
        s = model.CamSetup()
        op = model.Operation(kind='instruction', instruction='bloc', params={'texte': 'Rpm {p1}', 'p1': 18000})
        s.operations = [op]
        tp = S.compute(Document(), s, op)
        self.assertEqual(INS.bloc_lines(tp.cycles[0]['params']), ['Rpm 18000'])


if __name__ == '__main__':
    unittest.main()
