"""Round 332 : rotation par référence (comme ROTATION ▸ Référence en DAO)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


def ev():
    return QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton,
                       Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)


class TestRotateRef(unittest.TestCase):
    def test_clicks_and_typed(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            # trait penché de 30° : redressé à l'horizontale
            s = Shape(path=geom.Path([geom.polyline([(0, 0), (8.660254, 5)])]))
            c.doc.add(s)
            c.select([s])
            w.set_tool('rotate_ref')
            t = c.tool_obj
            for p in ((0, 0), (8.660254, 5), (10, 0)):
                t.press(c.to_screen(*p), p, ev())
            end = c.selection[0].path.contours[0].end
            self.assertAlmostEqual(end[1], 0.0, 5)
            self.assertAlmostEqual(end[0], 10.0, 4)
            w.set_tool('rotate_ref')
            t = c.tool_obj
            c.ask_angle_fn = lambda: 90.0                               # à la verticale
            t.press(c.to_screen(0, 0), (0.0, 0.0), ev())
            t.press(c.to_screen(10, 0), (10.0, 0.0), ev())
            self.assertTrue(t.key(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)))
            end = c.selection[0].path.contours[0].end
            self.assertAlmostEqual(end[0], 0.0, 4)
            self.assertAlmostEqual(end[1], 10.0, 4)
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()


class TestIcons(unittest.TestCase):
    def test_every_named_icon_exists(self):
        import inspect
        import re
        from vectordrive.ui import icons, main_window
        src = inspect.getsource(main_window)
        found = re.findall(r"a\('([a-z_0-9]+)', tr\([^)]*\)(?:, [^,]+)?, (?:None|'[^']*'|\[[^\]]*\]), '([a-z_0-9]+)'", src)
        found += re.findall(r"\('([a-z_0-9]+)', tr\('[^']*'\), '([a-z_0-9]+)'\)", src)
        self.assertGreater(len(found), 100)
        self.assertEqual([(k, i) for k, i in found if i not in icons.ICONS], [])


if __name__ == '__main__':
    unittest.main()
