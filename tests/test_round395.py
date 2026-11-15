"""Round 395 : relief et surface 3D — surépaisseur (ébauche qui laisse de
la matière autour de la surface)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np

from vectordrive.cam import advanced as A, model as M


def plateau():
    H = np.full((101, 101), -2.0)                       # pas 0,1 : 10 × 10 mm
    H[40:61, 40:61] = 0.0                               # plateau de 2 × 2 mm au centre
    return H


class TestStock(unittest.TestCase):
    def test_flat(self):
        t = M.CamTool(name='F2', kind='droite', diameter=2.0)
        T0 = A.with_stock(plateau(), 0.1, t, 0.0)
        T = A.with_stock(plateau(), 0.1, t, 0.5)
        self.assertAlmostEqual(T0[50, 20], -2.0, 6)
        self.assertAlmostEqual(T[50, 20], -1.5, 6)                   # loin du plateau : 0,5 au-dessus du fond
        self.assertAlmostEqual(T[50, 50], 0.5, 6)                   # sur le plateau : 0,5 au-dessus
        self.assertAlmostEqual(T0[50, 27], -2.0, 6)                 # 1,3 mm du bord : l'outil Ø2 descend
        self.assertAlmostEqual(T[50, 27], 0.5, 6)                   # avec 0,5 de surépaisseur : il reste haut
        self.assertTrue((T[20:81, 20:81] >= T0[20:81, 20:81] + 0.5 - 1e-9).all())               # jamais plus bas que sans surépaisseur

    def test_ball(self):
        t = M.CamTool(name='B2', kind='boule', diameter=2.0)
        T = A.with_stock(plateau(), 0.1, t, 0.3)
        T0 = A.with_stock(plateau(), 0.1, t, 0.0)
        self.assertTrue((T[20:81, 20:81] >= T0[20:81, 20:81] + 0.3 - 1e-6).all())
        self.assertAlmostEqual(T[50, 50], 0.3, 6)


if __name__ == '__main__':
    unittest.main()
