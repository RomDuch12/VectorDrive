"""Round 343 : pinceau à aplat — la surface peinte se fond avec les formes
fermées de l'outil courant qu'elle touche."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.cadtools import mass_properties
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


class TestBlob(unittest.TestCase):
    def test_tool(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            c.current_tool_index = 0
            a = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]), tool=0)
            other = Shape(path=geom.Path([geom.rect(30, 0, 10, 10)]), tool=1)          # autre outil
            c.doc.add(a)
            c.doc.add(other)
            c.eraser_radius = 1.0
            w.set_tool('blob')
            t = c.tool_obj

            def e(kind, buttons):
                return QMouseEvent(kind, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton, buttons,
                                   Qt.KeyboardModifier.NoModifier)
            t.press(c.to_screen(5, 5), (5.0, 5.0), e(QEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton))
            for x in range(6, 21):
                t.move(c.to_screen(x, 5), (float(x), 5.0), e(QEvent.Type.MouseMove, Qt.MouseButton.LeftButton))
            t.release(c.to_screen(20, 5), (20.0, 5.0), e(QEvent.Type.MouseButtonRelease, Qt.MouseButton.NoButton))
            items = c.doc.layers[0].items
            self.assertEqual(len(items), 2)                                      # fondu + l'autre outil
            blob = next(s for s in items if s.tool == 0)
            self.assertEqual(len(blob.path.contours), 1)
            self.assertGreater(mass_properties(blob.path)['area'], 100 + 10 * 2 - 1)
            self.assertTrue(blob.filled)
            w.undo()
            self.assertEqual(len(c.doc.layers[0].items), 2)
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
