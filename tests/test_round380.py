"""Round 380 : symbole de ligne de coupure (DAO : Break-line symbol)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core.cadtools import break_line

app = QApplication.instance() or QApplication([])


class TestBreakLine(unittest.TestCase):
    def test_shape(self):
        c = break_line((0, 0), (60, 0), 6.0, 2.0)
        pts = c.flatten(0.01)
        self.assertFalse(c.closed)
        self.assertEqual(tuple(round(v, 6) for v in pts[0]), (-2.0, 0.0))   # prolongé de 2
        self.assertEqual(tuple(round(v, 6) for v in pts[-1]), (62.0, 0.0))
        b = c.bbox()
        self.assertAlmostEqual(b[1], -3.0, 6)                               # zigzag de 6 de haut
        self.assertAlmostEqual(b[3], 3.0, 6)
        self.assertIsNone(break_line((1, 1), (1, 1)))
        auto = break_line((0, 0), (0, 30)).bbox()                          # vertical, hauteur 5 (30/6)
        self.assertAlmostEqual(auto[2] - auto[0], 5.0, 6)

    def test_tool(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.set_tool('breakline')
            c = w.canvas
            e = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton,
                            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            for pt in ((10.0, 10.0), (40.0, 10.0)):
                c.tool_obj.press(c.to_screen(*pt), pt, e)
            b = c.selection[0].path.bbox()
            self.assertAlmostEqual(b[0], 10.0, 6)
            self.assertAlmostEqual(b[2], 40.0, 6)
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
