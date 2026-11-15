"""Round 330 : chanfrein entre deux traits (comme CHANFREIN en DAO)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core import fillet2 as F2, geom
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


class TestChamfer2(unittest.TestCase):
    def test_core(self):
        a, b = geom.polyline([(0, 0), (8, 0)]), geom.polyline([(10, -3), (10, 20)])
        na, nb, seg = F2.fillet(a, (2, 0), b, (10, 15), 2.0, chamfer=True)
        self.assertEqual(tuple(round(v, 9) for v in na.end), (8.0, 0.0))
        self.assertEqual(tuple(round(v, 9) for v in nb.start), (10.0, 2.0))
        self.assertEqual(len(seg.segments), 1)
        self.assertAlmostEqual(seg.length(), 2 * math.sqrt(2), 9)

    def test_tool(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            a = Shape(path=geom.Path([geom.polyline([(0, 0), (20, 0)])]))
            b = Shape(path=geom.Path([geom.polyline([(10, -5), (10, 20)])]))
            c.doc.add(a)
            c.doc.add(b)
            c.chamfer_size = 3.0
            w.set_tool('chamfer2')
            t = c.tool_obj
            e = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton,
                            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            t.press(c.to_screen(2, 0), (2.0, 0.0), e)
            t.press(c.to_screen(10, 15), (10.0, 15.0), e)
            items = c.doc.layers[0].items
            self.assertEqual(tuple(round(v, 6) for v in items[0].path.contours[0].end), (7.0, 0.0))  # coupé
            self.assertEqual(len(items[0].path.contours), 2)
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
