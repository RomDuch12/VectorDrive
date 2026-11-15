"""Round 328 : échelle par référence (comme ÉCHELLE ▸ Référence en DAO) —
longueur de référence par deux points, nouvelle longueur cliquée ou saisie."""
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


class TestScaleRef(unittest.TestCase):
    def test_click_and_typed(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            s = Shape(path=geom.Path([geom.rect(0, 0, 10, 5)]))
            c.doc.add(s)
            c.select([s])
            w.set_tool('scale_ref')
            t = c.tool_obj
            for p in ((0, 0), (10, 0), (25, 0)):                     # 10 → 25 : × 2,5 autour de (0, 0)
                t.press(c.to_screen(*p), p, ev())
            self.assertEqual(tuple(round(v, 6) for v in c.selection[0].bbox()), (0, 0, 25, 12.5))
            w.set_tool('scale_ref')
            t = c.tool_obj
            c.select([c.selection[0]])
            c.ask_length_fn = lambda ref: 5.0                        # 25 → 5
            t.press(c.to_screen(0, 0), (0.0, 0.0), ev())
            t.press(c.to_screen(25, 0), (25.0, 0.0), ev())
            self.assertTrue(t.key(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)))
            self.assertAlmostEqual(c.selection[0].bbox()[2], 5.0, 6)
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
