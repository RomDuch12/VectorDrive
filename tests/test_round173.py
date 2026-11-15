"""Round 173 : palpage Z mémorisé (NeoDrive)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import instructions as I, model, strategies as S
from vectordrive.core.document import Document


class TestMemo(unittest.TestCase):
    def test_description(self):
        p = I.params_of('palpage_memorise', {'mode': 'Inconnu'})
        self.assertEqual((p['mode'], p['variable'], p['approach_z']), ('Demander', 'dernierPalpage', 15.0))
        self.assertIn('variable', I.INSTRUCTIONS['palpage_memorise'].advanced)
        q = I.from_selection('palpage_memorise', {}, (0, 0, 40, 20))
        self.assertEqual((q['x'], q['y']), (20, 10))

    def test_compute(self):
        s = model.CamSetup()
        op = model.Operation(kind='instruction', instruction='palpage_memorise', params={'forget_after': True})
        s.operations = [op]
        tp = S.compute(Document(), s, op)
        self.assertEqual((tp.moves, tp.warnings), ([], []))
        self.assertTrue(tp.cycles[0]['params']['forget_after'])


if __name__ == '__main__':
    unittest.main()
