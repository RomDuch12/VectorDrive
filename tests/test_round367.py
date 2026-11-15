"""Round 367 : surface bilinéaire (TypeEdit) — hauteurs des quatre coins,
sur l'encombrement et l'intérieur des formes choisies."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom, primitives3d as P3
from vectordrive.core.document import Shape
from vectordrive.core.relief_ops import z_at

app = QApplication.instance() or QApplication([])


class TestBilinear(unittest.TestCase):
    def test_corners(self):
        sp = P3.BilinearSpec(z_bl=0, z_br=2, z_tl=4, z_tr=6, resolution=0.1)
        img = P3.bilinear_relief(sp, (0, 0, 10, 10))
        self.assertAlmostEqual(z_at(img, 0.05, 0.05), 0.0, 1)
        self.assertAlmostEqual(z_at(img, 9.95, 9.95), 6.0, 1)
        self.assertAlmostEqual(z_at(img, 5, 5), 3.0, 1)              # moyenne des coins au milieu
        self.assertAlmostEqual(z_at(img, 9.95, 0.05), 2.0, 1)
        self.assertIsNone(P3.bilinear_relief(sp, (0, 0, 0, 10)))

    def test_window_region(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            s = Shape(path=geom.Path([geom.ellipse((20, 20), 10, 10)]))  # disque : coins hors de la forme
            w.canvas.doc.add(s)
            w.canvas.select([s])
            img = w.relief_bilinear(P3.BilinearSpec(z_bl=1, z_br=1, z_tl=3, z_tr=3))
            self.assertAlmostEqual(z_at(img, 20, 20), 2.0, 1)
            self.assertAlmostEqual(z_at(img, 11, 11), 0.0, 3)          # coin du carré, hors du disque
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
