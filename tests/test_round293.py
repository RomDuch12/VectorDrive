"""Round 293 : texture raccordable — le relief fondu avec sa copie décalée
d'une demi-taille ; ses bords opposés se raccordent."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np

from vectordrive.core import relief_ops as R
from vectordrive.ui import shortcuts as SC


class TestSeamless(unittest.TestCase):
    def test_seam(self):
        x, y = np.linspace(0, 1, 80), np.linspace(0, 1, 60)
        H = np.add.outer(np.sin(y * 5) * 2, x * 3)
        S = R.make_seamless(H)
        inner = float(np.abs(np.diff(S, axis=1)).mean())
        self.assertLess(float(np.abs(S[:, 0] - S[:, -1]).mean()), inner)          # couture invisible
        self.assertLess(float(np.abs(S[0] - S[-1]).mean()), float(np.abs(np.diff(S, axis=0)).mean()) * 1.5)
        self.assertEqual(S.shape, H.shape)
        self.assertEqual(SC.TE_ACTIONS['ID_CMD_MAKESEAMLESS'], 'relief_seamless')


if __name__ == '__main__':
    unittest.main()
