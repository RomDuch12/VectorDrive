"""Round 340 : copier avec point de base, coller au point (comme COPYBASE en
DAO) — cliqués ou donnés, annulable."""
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


def click(c, x, y):
    e = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton,
                    Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    c.tool_obj.press(c.to_screen(x, y), (float(x), float(y)), e)


class TestCopyBase(unittest.TestCase):
    def test_clicked(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            s = Shape(path=geom.Path([geom.rect(10, 10, 4, 2)]))
            c.doc.add(s)
            c.select([s])
            self.assertTrue(w.copy_base())
            click(c, 14, 12)                                         # base : coin haut-droit
            self.assertEqual(w._paste_base, (14.0, 12.0))
            w.paste_at()
            click(c, 50, 50)
            new = c.selection[0]
            self.assertEqual(tuple(round(v, 6) for v in new.bbox()), (46, 48, 50, 50))
            self.assertEqual(len(c.doc.layers[0].items), 2)
            w.undo()
            self.assertEqual(len(c.doc.layers[0].items), 1)
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()

    def test_given_and_default_base(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            s = Shape(path=geom.Path([geom.rect(10, 10, 4, 2)]))
            c.doc.add(s)
            c.select([s])
            w.copy()
            new = w.paste_at((0, 0))                                 # sans base : coin bas-gauche
            self.assertEqual(tuple(round(v, 6) for v in new[0].bbox()), (0, 0, 4, 2))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
