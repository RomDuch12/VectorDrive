"""Round 357 : accrochages perpendiculaire et tangente, depuis le dernier
point cliqué (ancre)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Shape
from vectordrive.core.snap import Snap

app = QApplication.instance() or QApplication([])


class TestRelative(unittest.TestCase):
    def test_perpendicular(self):
        line = Shape(path=geom.Path([geom.polyline([(0, 0), (20, 0)])]))
        sn = Snap(enabled=True, modes={'perpendicular'}, anchor=(7, 10))
        h = sn.query(7.3, 0.2, 0.6, [line])
        self.assertEqual((h.kind, round(h.x, 9), round(h.y, 9)), ('perpendicular', 7.0, 0.0))
        sn.anchor = None
        self.assertIsNone(sn.query(7.3, 0.2, 0.6, [line]))

    def test_tangent_and_circle_perp(self):
        circ = Shape(path=geom.Path([geom.circle((0, 0), 5)]))
        sn = Snap(enabled=True, modes={'tangent'}, anchor=(10, 0))
        # tangente depuis (10, 0) : point à 60° (cos φ = 5/10)
        tx, ty = 5 * math.cos(math.radians(60)), 5 * math.sin(math.radians(60))
        h = sn.query(tx + 0.1, ty + 0.1, 0.5, [circ])
        self.assertEqual(h.kind, 'tangent')
        self.assertAlmostEqual(h.x, tx, 6)
        self.assertAlmostEqual(h.y, ty, 6)
        sn.modes = {'perpendicular'}
        h = sn.query(5.1, 0.1, 0.5, [circ])
        self.assertEqual((h.kind, round(h.x, 9), round(h.y, 9)), ('perpendicular', 5.0, 0.0))

    def test_window(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            self.assertFalse(w.A['snap_tangent'].isChecked())
            w.A['snap_tangent'].setChecked(True)
            self.assertIn('tangent', w.canvas.snap.modes)
            win = w.snap_window()
            self.assertIn('perpendicular', win.boxes)
            win.close()
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
