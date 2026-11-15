"""Round 287 : aligner par points (comme ALIGNER en DAO) — déplacement et
rotation par deux paires de points, mise à l'échelle avec Maj, déplacement
seul avec Entrée."""
import math
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
from vectordrive.ui import tools as T

app = QApplication.instance() or QApplication([])


def ev(mods=Qt.KeyboardModifier.NoModifier):
    return QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton,
                       Qt.MouseButton.LeftButton, mods)


class TestAlign(unittest.TestCase):
    def test_matrix(self):
        m = T.align_matrix((0, 0), (10, 10), (1, 0), (10, 11))                   # +90° autour de la destination
        self.assertTrue(all(abs(a - b) < 1e-9 for a, b in zip(m.apply((1, 0)), (10, 11))))
        k = T.align_matrix((0, 0), (0, 0), (1, 0), (0, 2), scale=True)
        self.assertTrue(all(abs(a - b) < 1e-9 for a, b in zip(k.apply((1, 0)), (0, 2))))
        t = T.align_matrix((1, 1), (4, 5))
        self.assertEqual(t.apply((0, 0)), (3, 4))

    def test_tool(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            s = Shape(path=geom.Path([geom.rect(0, 0, 10, 2)]))
            c.doc.add(s)
            c.select([s])
            w.set_tool('align_points')
            t = c.tool_obj
            for p in ((0, 0), (20, 20), (10, 0), (20, 30)):
                t.press(c.to_screen(*p), p, ev(Qt.KeyboardModifier.ShiftModifier if p == (20, 30) else
                                               Qt.KeyboardModifier.NoModifier))
            b = c.selection[0].bbox()
            self.assertAlmostEqual(b[0], 18.0, 6)                                 # tourné de 90°, échelle 1
            self.assertAlmostEqual(b[3], 30.0, 6)
            w.set_tool('align_points')
            t = c.tool_obj
            c.select([c.selection[0]])
            t.press(c.to_screen(18, 20), (18.0, 20.0), ev())
            t.press(c.to_screen(0, 0), (0.0, 0.0), ev())
            self.assertTrue(t.key(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)))
            self.assertAlmostEqual(c.selection[0].bbox()[0], 0.0, 6)               # déplacement seul
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
