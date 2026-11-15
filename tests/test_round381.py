"""Round 381 : couper avec point de base (DAO : Cut with Base Point)."""
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


class TestCutBase(unittest.TestCase):
    def test_cut_then_paste(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            s = Shape(path=geom.Path([geom.rect(10, 10, 4, 2)]))
            c.doc.add(s)
            c.select([s])
            self.assertTrue(w.copy_base(cut=True))
            self.assertEqual(len(c.doc.layers[0].items), 1)          # rien d'effacé avant le point
            click(c, 14, 12)
            self.assertEqual(len(c.doc.layers[0].items), 0)          # coupé
            new = w.paste_at((0, 0))
            self.assertEqual(tuple(round(v, 6) for v in new[0].bbox()), (-4, -2, 0, 0))
            self.assertIn('cut_base', w.A)
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
