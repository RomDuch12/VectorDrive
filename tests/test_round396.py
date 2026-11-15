"""Round 396 : relief — aligner un plan à zéro (TypeEdit) : un relief palpé
de travers redressé par trois marqueurs."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.core import forms as F, galbe as GB, relief_ops as R
from vectordrive.core.relief_ops import z_at

app = QApplication.instance() or QApplication([])


def tilted():
    """Plan incliné 0,1 mm/mm en X plus un plot de 1 mm au centre (20 × 20 mm, pas 0,1)."""
    X = (np.arange(200) + 0.5) * 0.1
    H = np.tile(0.1 * X, (200, 1))
    H[90:110, 90:110] += 1.0
    return H


class TestLevel(unittest.TestCase):
    def test_core(self):
        out = R.level_plane(tilted(), 0.0, 20.0, 0.1, [(1, 1), (19, 1), (1, 19)])
        self.assertAlmostEqual(float(out[180, 15]), 0.0, 3)          # le fond est à plat, à Z 0
        self.assertAlmostEqual(float(out[180, 185]), 0.0, 3)
        self.assertAlmostEqual(float(out[100, 100]), 1.0, 3)          # le plot garde sa hauteur
        with self.assertRaises(ValueError):
            R.level_plane(tilted(), 0.0, 20.0, 0.1, [(1, 1), (2, 2), (3, 3)])
        with self.assertRaises(ValueError):
            R.level_plane(tilted(), 0.0, 20.0, 0.1, [(1, 1), (50, 1), (1, 19)])

    def test_window(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            img = GB.encode(tilted(), 0.0, 20.0, 0.1, GB.GalbeSpec())
            ms = [F.make(F.Marker(cx=x, cy=y)) for x, y in ((1, 1), (19, 1), (1, 19))]
            for it in [img] + ms:
                w.canvas.doc.add(it)
            w.canvas.select([img] + ms)
            new = w.relief_level()
            self.assertAlmostEqual(z_at(new, 15, 2), z_at(new, 2, 2), 2)
            self.assertAlmostEqual(z_at(new, 10, 10) - z_at(new, 2, 2), 1.0, 2)
            w.canvas.select([new])
            self.assertIsNone(w.relief_level())
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
