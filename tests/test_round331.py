"""Round 331 : repérage polaire (F12) — depuis le dernier point cliqué, le
curseur s'accroche aux angles multiples du pas ; ligne de repérage."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core.snap import Snap, polar

app = QApplication.instance() or QApplication([])


class TestPolar(unittest.TestCase):
    def test_polar(self):
        h, lines = polar(10, 0.3, 0.5, (0, 0), 15)
        self.assertEqual((round(h.x, 9), round(h.y, 9)), (10.0, 0.0))
        h, _ = polar(7.1, 7.0, 0.5, (0, 0), 15)                      # près de 45°
        self.assertAlmostEqual(math.degrees(math.atan2(h.y, h.x)), 45.0, 6)
        self.assertEqual(polar(7, 3, 0.5, (0, 0), 45), (None, []))   # loin d'un rayon
        sn = Snap(enabled=True, modes={'node'}, polar=True, anchor=(0, 0))
        h = sn.query(20, 0.2, 0.5, [])
        self.assertEqual((h.kind, round(h.y, 9)), ('tracking', 0.0))
        sn.clear_tracking()
        self.assertIsNone(sn.anchor)

    def test_window(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            w.polar_step_dialog(30.0)
            w.A['snap_polar'].setChecked(True)
            self.assertTrue(c.snap.enabled and c.snap.polar)
            self.assertEqual(c.snap.polar_step, 30.0)
            self.assertIn('30', w.lbl_snap.text())
            w.set_tool('line') if 'tool_line' in w.A else None
            c.snap.anchor = (0.0, 0.0)
            x, y = c.snap_doc(c.to_screen(8.66, 5.05))                    # près de 30°
            self.assertAlmostEqual(math.degrees(math.atan2(y, x)), 30.0, 6)
            w.A['snap_polar'].setChecked(False)
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
