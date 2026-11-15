"""Round 291 : SculptArt — pinceaux « pousser » (matière entraînée dans le
sens du geste) et « attirer » (resserrée vers le centre)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np

from vectordrive.core import sculpt as SC


def centroid_x(row):
    return float((row * np.arange(len(row))).sum() / row.sum()) * 0.1


class TestNewBrushes(unittest.TestCase):
    def test_push(self):
        H = np.zeros((100, 100))
        H[45:55, 20:30] = 1.0
        before = centroid_x(H[50])
        SC.stroke(H, 0, 10, 0.1, (2.5, 5), (4.5, 5), 1.0, 0, 'pousser')
        self.assertGreater(centroid_x(H[50]), before + 0.3)                   # entraîné vers +x
        self.assertAlmostEqual(float(H.max()), 1.0, 6)                         # pas de matière créée

    def test_pinch(self):
        H = np.zeros((100, 100))
        H[:, 70] = 1.0                                                         # un trait à 2 mm du centre
        SC.dab(H, 0, 10, 0.1, 5.0, 5.0, 3.0, 0.6, 'attirer')
        cols = np.nonzero(H[50] > 0.5)[0]
        self.assertTrue(cols.size and cols.min() < 70)                         # rapproché du centre
        self.assertIn(('pousser', 'Pousser'), SC.BRUSHES)


if __name__ == '__main__':
    unittest.main()
