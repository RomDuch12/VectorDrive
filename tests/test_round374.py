"""Round 374 : relief — bordure autour d'un contour (TypeEdit : Bordure) :
dans la continuité du bord, ou à plat à Z constant."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.core import galbe as GB, geom, relief_ops as R
from vectordrive.core.document import Shape
from vectordrive.core.relief_ops import z_at

app = QApplication.instance() or QApplication([])


class TestBorder(unittest.TestCase):
    def test_function(self):
        H = np.zeros((5, 9))
        inside = np.zeros((5, 9), bool)
        inside[:, :3] = True
        H[:, :3] = np.array([1.0, 2.0, 3.0])                       # pente vers la droite, bord à 3
        band = np.zeros((5, 9), bool)
        band[:, :6] = True
        out = R.border(H, inside, band)
        self.assertTrue(np.allclose(out[:, 3:6], 3.0))              # prolongé à la hauteur du bord
        self.assertTrue(np.allclose(out[:, 6:], 0.0))               # hors de la bande : intact
        flat = R.border(H, inside, band, 'z_constant', 0.5)
        self.assertTrue(np.allclose(flat[:, 3:6], 0.5))
        self.assertTrue(np.allclose(flat[:, :3], H[:, :3]))

    def test_window(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            H = np.zeros((200, 200))
            H[50:150, 50:150] = 2.0                                  # plateau de 10 × 10 au milieu (mm)
            img = GB.encode(H, 0.0, 20.0, 0.1, GB.GalbeSpec())
            zone = Shape(path=geom.Path([geom.rect(5, 5, 10, 10)]))
            c.doc.add(img)
            c.doc.add(zone)
            c.select([img, zone])
            new = w.relief_op('relief_border', {'width': 2.0, 'mode': 'continuite'})
            self.assertAlmostEqual(z_at(new, 4.0, 10.0), 2.0, 2)      # 1 mm hors du plateau : prolongé
            self.assertAlmostEqual(z_at(new, 2.0, 10.0), 0.0, 2)      # au-delà de la largeur : intact
            c.select([new])
            self.assertIsNone(w.relief_op('relief_border', {'width': 2.0}))   # sans contour : refusé
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
