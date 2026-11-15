"""Round 337 : sonde de relief — cote Z en un point, profil entre deux
points (cotes mini et maxi, pente)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core import galbe as GB, relief_ops as R

app = QApplication.instance() or QApplication([])


def ramp():
    # rampe : z = x / 10 sur 0..10 mm (pas 0,1)
    xs = (np.arange(100) + 0.5) * 0.1
    return GB.encode(np.tile(xs / 10, (50, 1)), 0.0, 5.0, 0.1, GB.GalbeSpec())


class TestProbe(unittest.TestCase):
    def test_core(self):
        img = ramp()
        self.assertAlmostEqual(R.z_at(img, 5.0, 2.5), 0.5, 3)
        self.assertIsNone(R.z_at(img, 20, 2))
        prof = R.profile(img, (1, 2), (9, 2), 16)
        self.assertAlmostEqual(prof[-1][0], 8.0)
        self.assertAlmostEqual(prof[0][1], 0.1, 3)
        self.assertAlmostEqual(prof[-1][1], 0.9, 3)

    def test_tool(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            c.doc.add(ramp())
            w.set_tool('relief_probe')
            t = c.tool_obj
            got = []
            c.measured.connect(got.append)
            e = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton,
                            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            t.press(c.to_screen(5, 2.5), (5.0, 2.5), e)
            self.assertIn('0.500', got[-1])
            t.press(c.to_screen(9, 2.5), (9.0, 2.5), e)
            self.assertIn('Profil', got[-1])
            self.assertIn('5.7', got[-1])                                # pente 0,1 : 5,7°
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
