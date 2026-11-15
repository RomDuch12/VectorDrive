"""Round 306 : relief d'un modèle 3D (TypeEdit : surface en objet TypeArt) —
pièce maillée vue d'un côté, taille et hauteur réelles ou imposées."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.core import galbe as GB, mesh_relief as MR

app = QApplication.instance() or QApplication([])


def pyramid():
    # pyramide : base 20 × 10 à Z = 5, sommet (10, 5, 9) ; une face de dessous
    a, b, c, d, s = (0, 0, 5), (20, 0, 5), (20, 10, 5), (0, 10, 5), (10, 5, 9)
    return np.array([(a, b, s), (b, c, s), (c, d, s), (d, a, s), (a, c, b), (a, d, c)], float)


def at(img, x, y):
    H, x0, y1, res = GB.decode(img)
    return float(H[int((y1 - y) / res), int((x - x0) / res)])


class TestMeshRelief(unittest.TestCase):
    def test_top(self):
        img = MR.mesh_relief(pyramid(), MR.MeshReliefSpec(resolution=0.1, margin=0))
        self.assertAlmostEqual(at(img, 10, 5), 4.0, 1)             # sommet, bas posé à 0
        self.assertAlmostEqual(at(img, 5, 5), 2.0, 1)
        self.assertAlmostEqual(img.extra['galbe']['relief_depth'], 4.0, 1)

    def test_scale_and_height(self):
        img = MR.mesh_relief(pyramid(), MR.MeshReliefSpec(size=40, z_max=1.5, resolution=0.1, margin=0))
        b = img.bbox()
        self.assertAlmostEqual(b[2] - b[0], 40, 0)
        self.assertAlmostEqual(at(img, 20, 10), 1.5, 1)

    def test_views(self):
        T = MR.oriented(pyramid(), 'avant')                      # vu de l'avant : 20 de large, 4 de haut en Y
        hi = T.reshape(-1, 3).max(axis=0)
        self.assertEqual(tuple(np.round(hi, 6)), (20, 4, 10))
        T = MR.oriented(pyramid(), 'dessous')
        self.assertAlmostEqual(T.reshape(-1, 3).max(axis=0)[2], 4)
        for v, _l in MR.VIEWS:                                      # vraies rotations
            self.assertAlmostEqual(np.linalg.det(np.array(MR._ROT[v], float)), 1.0)

    def test_command(self):
        from vectordrive.io.stl_write import write_stl
        from vectordrive.ui.main_window import MainWindow
        path = os.path.join(tempfile.mkdtemp(), 'pyramide.stl')
        write_stl(path, pyramid())
        w = MainWindow()
        try:
            img = w.relief_model3d(path, MR.MeshReliefSpec(resolution=0.2, margin=0))
            self.assertIsNotNone(img)
            self.assertIn(img, w.canvas.doc.layers[0].items)
            self.assertAlmostEqual(img.extra['galbe']['relief_depth'], 4.0, 0)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
