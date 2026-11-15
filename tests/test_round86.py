"""Round 86 : clone collé déplacé aux flèches, déplacement à la souris après
un maintien, Maj au relâchement = copie."""
import os
import time
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent

from vectordrive.core import geom
from vectordrive.core.document import Shape


def mouse(kind, pos, mods=Qt.KeyboardModifier.NoModifier, button=Qt.MouseButton.LeftButton):
    t = {'press': QMouseEvent.Type.MouseButtonPress, 'move': QMouseEvent.Type.MouseMove,
         'release': QMouseEvent.Type.MouseButtonRelease}[kind]
    buttons = Qt.MouseButton.NoButton if kind == 'release' else button
    return QMouseEvent(t, QPointF(pos), QPointF(pos), button, buttons, mods)


class TestMoveAndClone(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.resize(1200, 800)
        self.w.show()
        self.app.processEvents()
        self.sq = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]))
        self.w._add_items([self.sq])
        self.w.canvas.fit((0, 0, 100, 50))                    # vue de l'ancienne plaque par défaut
        self.c = self.w.canvas

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def bboxes(self):
        return sorted(tuple(round(v, 6) for v in it.bbox()) for it in self.c.doc.iter_items())

    def drag(self, dx_px, hold_s, mods_release=Qt.KeyboardModifier.NoModifier):
        bb = next(self.c.doc.iter_items()).bbox()
        a = self.c.to_screen(bb[0] + 3, bb[1])              # sur le contour, loin des poignées
        b = QPointF(a.x() + dx_px, a.y())
        self.c.mousePressEvent(mouse('press', a))
        self.c.mouseMoveEvent(mouse('move', QPointF(a.x() + dx_px / 2, a.y())))
        if hold_s:
            t = time.monotonic()
            while time.monotonic() - t < hold_s:
                self.app.processEvents()
                time.sleep(0.02)
        self.c.mouseMoveEvent(mouse('move', b))
        self.c.mouseReleaseEvent(mouse('release', b, mods_release))

    def test_quick_drag_does_not_move(self):
        self.c.move_delay_ms = 600
        self.drag(80, 0)
        self.assertEqual(self.bboxes(), [(0, 0, 10, 10)])

    def test_held_drag_moves_and_shift_copies(self):
        self.c.move_delay_ms = 150
        self.drag(80, 0.25)
        moved = self.bboxes()
        self.assertEqual(len(moved), 1)
        self.assertGreater(moved[0][0], 1)
        self.assertEqual(self.c.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.c.select(list(self.c.doc.iter_items()))
        self.drag(80, 0.25, Qt.KeyboardModifier.ShiftModifier)
        after = self.bboxes()
        self.assertEqual(len(after), 2)                       # l'original reste, la copie est déplacée
        self.assertIn(moved[0], after)
        self.w.undo()
        self.assertEqual(self.bboxes(), moved)

    def test_paste_then_ctrl_arrow_moves_clone_even_from_panel(self):
        from PySide6.QtTest import QTest
        self.c.select([self.sq])
        self.w.copy()
        self.w.dims.fields['x'].setFocus()                    # focus dans le panneau des dimensions
        self.app.processEvents()
        self.w.paste()
        self.app.processEvents()
        self.assertIs(self.app.focusWidget(), self.c)
        from PySide6.QtWidgets import QInputDialog
        old = QInputDialog.getDouble
        QInputDialog.getDouble = staticmethod(lambda parent, title, label, start, *a: (start, True))
        try:
            QTest.keyClick(self.c, Qt.Key.Key_Right, Qt.KeyboardModifier.ControlModifier)   # pas : sa largeur
        finally:
            QInputDialog.getDouble = old
        b = self.bboxes()
        self.assertEqual(len(b), 2)
        self.assertIn((0, 0, 10, 10), b)                      # l'original n'a pas bougé
        self.assertIn((10.0, 0.0, 20.0, 10.0), b)              # clone accolé dès Ctrl+flèche validé (257)

    def test_enter_in_dimension_field_returns_to_canvas(self):
        sb = self.w.dims.fields['w']
        sb.setFocus()
        self.app.processEvents()
        sb.lineEdit().returnPressed.emit()
        self.app.processEvents()
        self.assertIs(self.app.focusWidget(), self.c)


if __name__ == '__main__':
    unittest.main()
