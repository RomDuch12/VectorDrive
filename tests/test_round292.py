"""Round 292 : remplissage par texture — un petit relief répété en pavage
dans une zone, sur un relief ou en nouveau relief."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.core import galbe as GB, geom, texture3d as T3
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


class TestTile(unittest.TestCase):
    def test_tile(self):
        T = np.zeros((10, 10))
        T[2:8, 2:8] = 1.0                                                       # motif 1 × 1 mm, bosse au milieu
        X, Y = np.meshgrid(np.arange(0.05, 5, 0.1), np.arange(4.95, 0, -0.1))
        H = T3.tile(X, Y, T, 0.0, 1.0, 0.1)
        self.assertEqual(float(H[int((1.0 - 0.55) / 0.1) + 0, 5]), 1.0)
        self.assertAlmostEqual(float(H.mean()), 0.36, 2)                        # 36 % de chaque motif
        G = T3.tile(X, Y, T, 0.0, 1.0, 0.1, gap=1.0)
        self.assertLess(float(G.mean()), float(H.mean()))

    def test_command(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            T = np.zeros((10, 10))
            T[2:8, 2:8] = 0.5
            motif = GB.encode(T, 40.0, 10.0, 0.1, GB.GalbeSpec())
            zone = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]))
            for it in (motif, zone):
                c.doc.add(it)
            c.select([motif, zone])
            img = w.relief_tile(0.0)
            self.assertIsNotNone(img)
            H, *_ = GB.decode(img)
            self.assertAlmostEqual(float(H.max()), 0.5, 2)
            self.assertGreater(int((H > 0.4).sum()), 20 * 36)                    # beaucoup de motifs
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
