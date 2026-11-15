"""Round 542 : mémoire des parcours FAO plafonnée en mouvements (gros vcarve : la mémoire ne gonfle plus
de plusieurs Go au fil des calculs)."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import strategies as S
from tests.test_round511 import setup_doc


class TestToolpathCacheCap(unittest.TestCase):
    def setUp(self):
        S.clear_toolpath_cache()

    def tearDown(self):
        S.clear_toolpath_cache()

    def test_cap(self):
        d, s = setup_doc()
        first = S.compute_all(d, s)
        total = sum(len(t.moves) for t in first)
        self.assertEqual(len(S._TP_CACHE), 2)
        S.clear_toolpath_cache()
        biggest = max(len(t.moves) for t in first)
        with mock.patch.object(S, 'TP_CACHE_MOVES', biggest):         # une seule tient : la plus ancienne part
            S.compute_all(d, s)
            self.assertEqual(len(S._TP_CACHE), 1)
            self.assertLessEqual(sum(len(t.moves) for t in S._TP_CACHE.values()), biggest)
        S.clear_toolpath_cache()
        with mock.patch.object(S, 'TP_CACHE_MOVES', min(len(t.moves) for t in first) - 1):
            S.compute_all(d, s)                                        # trop gros : pas gardés du tout
            self.assertEqual(len(S._TP_CACHE), 0)
        self.assertLess(total, S.TP_CACHE_MOVES)


if __name__ == '__main__':
    unittest.main()
