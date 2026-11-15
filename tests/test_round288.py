"""Round 288 : Mode Point sur plusieurs formes (sélection multiple ou
groupe) — la première active, un clic sur un point d'une autre l'active."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Group, Shape

app = QApplication.instance() or QApplication([])


def ev():
    return QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton,
                       Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)


class TestMultiNodes(unittest.TestCase):
    def test_group_and_switch(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            a = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]))
            b = Shape(path=geom.Path([geom.rect(20, 0, 10, 10)]))
            g = Group(children=[a, b])
            c.doc.add(g)
            c.select([g])
            w.set_tool('node')
            t = c.tool_obj
            self.assertIs(t.shape(), a)                                            # groupe : la 1re forme
            self.assertEqual(len(t.shapes()), 2)
            self.assertFalse(w.grab().isNull())
            sp = c.to_screen(30, 10)
            t.press(sp, (30.0, 10.0), ev())
            t.release(sp, (30.0, 10.0), ev())
            self.assertIs(t.shape(), b)                                            # point de b cliqué : b active
            self.assertEqual(len(t.sel), 1)
            self.assertIs(c.selection[0], g)                                       # la sélection ne change pas
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
