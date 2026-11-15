"""Round 376 : relief — tranches (TypeEdit : Tranches) : contours aux cotes
successives, du haut ou du bas."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.core import galbe as GB, relief_ops as R

app = QApplication.instance() or QApplication([])


def pyramid():
    """Marches : 0 autour, 1 sur 10 × 10 mm, 2 sur 4 × 4 mm au centre (pas 0,1, carte 20 × 20)."""
    H = np.zeros((200, 200))
    H[50:150, 50:150] = 1.0
    H[80:120, 80:120] = 2.0
    return H


def bbox(cs):
    xs = [v for c in cs for p in c.flatten(0.01) for v in (p[0],)]
    ys = [p[1] for c in cs for p in c.flatten(0.01)]
    return round(min(xs), 1), round(min(ys), 1), round(max(xs), 1), round(max(ys), 1)


class TestSlices(unittest.TestCase):
    def test_top_down(self):
        out = R.slices(pyramid(), 0.0, 20.0, 0.1, 0.01, 1.0, 5)
        self.assertEqual([round(z, 2) for z, _ in out], [1.99, 0.99])      # au-delà du bas : arrêt
        self.assertEqual(bbox(out[0][1]), (8.0, 8.0, 12.0, 12.0))
        self.assertEqual(bbox(out[1][1]), (5.0, 5.0, 15.0, 15.0))

    def test_bottom_up_window(self):
        out = R.slices(pyramid(), 0.0, 20.0, 0.1, 0.5, 1.0, 2, top_down=False)
        self.assertEqual([round(z, 2) for z, _ in out], [0.5, 1.5])
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            img = GB.encode(pyramid(), 0.0, 20.0, 0.1, GB.GalbeSpec())
            w.canvas.doc.add(img)
            w.canvas.select([img])
            shapes = w.relief_slices({'first': 0.01, 'step': 1.0, 'count': 2, 'top_down': True})
            self.assertEqual(len(shapes), 2)
            self.assertTrue(all(c.closed for s in shapes for c in s.path.contours))
            self.assertIn('Z 1.990', shapes[0].name)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
