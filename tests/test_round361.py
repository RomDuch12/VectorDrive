"""Round 361 : saisies de point pendant un outil — milieu de deux points
cliqués, point de base plus décalage (comme M2P / FROM en DAO)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


def press(c, x, y):
    p = c.to_screen(x, y)
    e = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(p), QPointF(p), Qt.MouseButton.LeftButton,
                    Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    c.mousePressEvent(e)


class TestPointModes(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.c = self.w.canvas
        self.c.snap.enabled = False
        self.got = []

    def tearDown(self):
        self.w.set_tool('select')
        self.w.modified = False
        self.w.close()

    def _tool(self):
        self.w.set_tool('polyline')
        self.assertIsNotNone(self.c.tool_obj)
        self.c.tool_obj.press = lambda pos, dp, ev: self.got.append((round(dp[0], 3), round(dp[1], 3)))

    def test_without_tool(self):
        self.w.set_tool('select')
        self.assertFalse(self.w._point_mode('m2p'))
        self.assertIsNone(self.c.point_mode)

    def test_m2p(self):
        self._tool()
        self.assertTrue(self.w._point_mode('m2p'))
        press(self.c, 10, 10)
        self.assertEqual(self.got, [])                       # premier point : rien pour l'outil
        press(self.c, 30, 20)
        self.assertEqual(self.got, [(20.0, 15.0)])
        self.assertIsNone(self.c.point_mode)
        press(self.c, 5, 5)                                  # ensuite : clics normaux
        self.assertEqual(self.got[-1], (5.0, 5.0))

    def test_from(self):
        self._tool()
        self.c.ask_offset_fn = lambda: (3.0, -2.0)
        self.w._point_mode('from')
        press(self.c, 10, 10)
        self.assertEqual(self.got, [(13.0, 8.0)])
        self.c.ask_offset_fn = lambda: None                  # abandon : aucun point pour l'outil
        self.w._point_mode('from')
        press(self.c, 10, 10)
        self.assertEqual(len(self.got), 1)
        self.assertIsNone(self.c.point_mode)


if __name__ == '__main__':
    unittest.main()
