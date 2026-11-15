"""Round 841 : Alt+clic sur une poignée : sans geste, les objets superposés défilent ; avec un geste, l'original reste."""
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Layer, Plate, Shape
from vectordrive.ui.main_window import MainWindow

app = QApplication.instance() or QApplication([])
ALT = Qt.KeyboardModifier.AltModifier
LEFT = Qt.MouseButton.LeftButton
NONE = Qt.MouseButton.NoButton


def event(kind, p, button, buttons, mods=ALT):
    return QMouseEvent(kind, QPointF(p), QPointF(p), button, buttons, mods)


class AltOnHandle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()
        cls.win.deleteLater()

    def setUp(self):
        self.c = self.win.canvas
        self.layer = Layer(name='Plan 1')
        self.c.doc.layers[:] = [self.layer]
        self.c.doc.active = self.layer.id
        self.c.doc.plate = Plate(width=200.0, height=100.0)
        self.win._undo.clear()
        self.c.scale = 8.0
        self.shapes = [Shape(path=geom.Path([geom.rect(0.0, 0.0, 10.0, 10.0)])) for _ in range(2)]
        self.layer.items.extend(self.shapes)
        self.c.select([self.shapes[1]])

    def tearDown(self):
        self.c.rot_mode = False
        self.c.select([])

    def on_handle(self):
        p = self.c.to_screen(10.0, 5.0)
        self.assertIsNotNone(self.c.handle_at(QPointF(p)))
        return p

    def test_a_click_goes_to_the_next_object(self):
        p = self.on_handle()
        self.c.mousePressEvent(event(QEvent.Type.MouseButtonPress, p, LEFT, LEFT))
        self.c.mouseReleaseEvent(event(QEvent.Type.MouseButtonRelease, p, LEFT, NONE))
        self.assertEqual(self.c.selection, [self.shapes[0]])
        self.assertEqual(len(self.layer.items), 2)

    def test_a_gesture_still_keeps_the_original(self):
        p = self.on_handle()
        far = QPointF(p) + QPointF(80.0, 0.0)
        self.c.mousePressEvent(event(QEvent.Type.MouseButtonPress, p, LEFT, LEFT))
        self.c.mouseMoveEvent(event(QEvent.Type.MouseMove, far, NONE, LEFT))
        self.c.mouseReleaseEvent(event(QEvent.Type.MouseButtonRelease, far, LEFT, NONE))
        self.assertEqual(len(self.layer.items), 3)

    def test_a_click_without_alt_changes_nothing(self):
        p = self.on_handle()
        mods = Qt.KeyboardModifier.NoModifier
        self.c.mousePressEvent(event(QEvent.Type.MouseButtonPress, p, LEFT, LEFT, mods))
        self.c.mouseReleaseEvent(event(QEvent.Type.MouseButtonRelease, p, LEFT, NONE, mods))
        self.assertEqual(self.c.selection, [self.shapes[1]])


if __name__ == '__main__':
    unittest.main()
