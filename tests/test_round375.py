"""Round 375 : relief — effacer une partie, extraire une partie (TypeEdit :
Effets spéciaux TypeArt)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.core import galbe as GB, geom
from vectordrive.core.document import Shape
from vectordrive.core.relief_ops import z_at

app = QApplication.instance() or QApplication([])


def setup_window():
    from vectordrive.ui.main_window import MainWindow
    w = MainWindow()
    c = w.canvas
    img = GB.encode(np.full((200, 200), 2.0), 0.0, 20.0, 0.1, GB.GalbeSpec())   # 20 × 20 mm à Z 2
    zone = Shape(path=geom.Path([geom.rect(0, 0, 10, 20)]))                   # moitié gauche
    c.doc.add(img)
    c.doc.add(zone)
    c.select([img, zone])
    return w, img, zone


class TestKeepExtract(unittest.TestCase):
    def test_keep(self):
        w, img, zone = setup_window()
        try:
            new = w.relief_keep(invert=False)
            self.assertAlmostEqual(z_at(new, 5, 10), 2.0, 3)
            self.assertAlmostEqual(z_at(new, 15, 10), 0.0, 3)
            w.canvas.select([new, zone])
            gone = w.relief_keep(invert=True)
            self.assertAlmostEqual(z_at(gone, 5, 10), 0.0, 3)
        finally:
            w.modified = False
            w.close()

    def test_extract(self):
        w, img, zone = setup_window()
        try:
            part = w.relief_extract(cut=True)
            b = part.bbox()
            self.assertEqual(tuple(round(v, 3) for v in b), (0.0, 0.0, 10.0, 20.0))   # recadré sur la zone
            self.assertAlmostEqual(z_at(part, 5, 10), 2.0, 3)
            rest = next(it for it in w.canvas.doc.layers[0].items if it is not part and 'galbe' in it.extra)
            self.assertAlmostEqual(z_at(rest, 5, 10), 0.0, 3)                        # ôté de l'original
            self.assertAlmostEqual(z_at(rest, 15, 10), 2.0, 3)
            w.canvas.select([])
            self.assertIsNone(w.relief_extract())
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
