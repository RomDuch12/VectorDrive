"""Round 405 : couteau au trait (TypeEdit : Couper un contour)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


def ev():
    return QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton,
                       Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)


class TestKnifeLine(unittest.TestCase):
    def test_cut(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            a = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]))
            far = Shape(path=geom.Path([geom.rect(50, 50, 5, 5)]))
            c.doc.add(a)
            c.doc.add(far)
            w.set_tool('knife_line')
            t = c.tool_obj
            t.closing = True
            t.press(None, (5.0, -2.0), ev())
            t.move(None, (5.0, 12.0), ev())
            t.release(None, (5.0, 12.0), ev())
            items = c.doc.layers[0].items
            self.assertEqual(len(items), 3)                       # deux moitiés + la forme lointaine intacte
            halves = sorted(round(s.bbox()[0], 6) for s in items if s is not far)
            self.assertEqual(halves, [0.0, 5.0])
            self.assertTrue(all(cc.closed for s in items for cc in s.path.contours))
            self.assertEqual(w.knife_line((100, 100), (110, 110)), 0)
            w.undo()
            self.assertEqual(len(c.doc.layers[0].items), 2)
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
