"""Round 377 : relief — poser un relief sur un autre (TypeEdit : Poser) :
trois façons de le poser."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.core import galbe as GB, relief_ops as R
from vectordrive.core.relief_ops import z_at

app = QApplication.instance() or QApplication([])


def reliefs():
    ramp = np.tile(np.linspace(0, 2, 200), (200, 1))                 # pente de 0 à 2 selon X (20 × 20 mm)
    base = GB.encode(ramp, 0.0, 20.0, 0.1, GB.GalbeSpec(), name='Base')
    T = np.zeros((40, 40))
    T[10:30, 10:30] = 1.0                                             # plot de 1 mm, socle à 0,5 autour
    T[T == 0] = 0.5
    top = GB.encode(T, 8.0, 12.0, 0.1, GB.GalbeSpec(), name='Plot')  # 4 × 4 mm, de x 8 à 12
    return base, top


class TestPlace(unittest.TestCase):
    def test_modes(self):
        base, top = reliefs()
        hi = z_at(base, 11.95, 10)                                    # point le plus haut sous le plot (≈ 1,2)
        a = R.place(base, top, 'zmin_zmax')
        self.assertAlmostEqual(z_at(a, 8.05, 10), hi, 1)                # socle (0,5) amené au plus haut
        self.assertAlmostEqual(z_at(a, 10, 10), hi + 0.5, 1)
        b = R.place(base, top, 'base_zmax')
        self.assertAlmostEqual(z_at(b, 10, 10), hi + 1.0, 1)          # Z 0 du plot au plus haut
        c = R.place(base, top, 'inclinaison')
        self.assertAlmostEqual(z_at(c, 10, 10), z_at(base, 10, 10) + 1.0, 1)
        self.assertAlmostEqual(z_at(c, 2, 10), z_at(base, 2, 10), 3)  # ailleurs : intact
        self.assertEqual(c.name, 'Base')

    def test_window(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            base, top = reliefs()
            w.canvas.doc.add(base)
            w.canvas.doc.add(top)
            w.canvas.select([base, top])
            img = w.relief_place('inclinaison')
            items = w.canvas.doc.layers[0].items
            self.assertIn(img, items)
            self.assertNotIn(top, items)
            self.assertNotIn(base, items)
            w.canvas.select([img])
            self.assertIsNone(w.relief_place('inclinaison'))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
