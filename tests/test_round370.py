"""Round 370 : détourage — matière restante en fin de contour (TypeEdit :
With remaining material) : la pièce reste tenue."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import strategies as S
from tests.test_round362 import run


def feed_length(tp):
    n, prev = 0.0, None
    for m in tp.moves:
        if m.kind == 'feed' and prev is not None and abs(m.z - prev[2]) < 1e-9:
            n += math.dist((m.x, m.y), prev[:2])
        prev = (m.x, m.y, m.z)
    return n


class TestUncut(unittest.TestCase):
    def test_cut_short(self):
        pts = [(0, 0), (10, 0), (10, 10)]
        self.assertEqual(S.cut_short(pts, 4), [(0, 0), (10, 0), (10, 6)])
        self.assertEqual(S.cut_short(pts, 25), [])

    def test_contour(self):
        full = run()                                         # 20 × 10, Ø2 : anneau de 64 mm environ
        part = run(leave_uncut=3.0)
        self.assertAlmostEqual(feed_length(full) - feed_length(part), 3.0, 1)
        self.assertEqual(sum(1 for m in part.moves if m.kind == 'plunge'), 1)   # une passe (profondeur 1)

    def test_with_lead_in(self):
        tp = run(leave_uncut=2.0, lead_in=1.0, lead_out=1.0)
        self.assertTrue(any('sortie tangente ignorée' in w for w in tp.warnings), tp.warnings)


if __name__ == '__main__':
    unittest.main()
