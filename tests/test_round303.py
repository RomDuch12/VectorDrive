"""Round 303 : contour de zone (comme CONTOUR / BOUNDARY en DAO) — zone
fermée par des traits ouverts qui se croisent, îlots en trous ou non."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.boundary import boundary_at
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


def lines():
    # quatre traits qui dépassent et se croisent : un carré 10 × 10 au milieu
    return [geom.Path([geom.polyline(p)]) for p in (
        [(-2, 0), (12, 0)], [(-2, 10), (12, 10)], [(0, -2), (0, 12)], [(10, -2), (10, 12)])]


def area(path):
    from vectordrive.core.cadtools import mass_properties
    return mass_properties(path)['area']


class TestBoundary(unittest.TestCase):
    def test_open_lines(self):
        b = boundary_at(lines(), (5, 5))
        self.assertAlmostEqual(area(b), 100, 6)
        self.assertEqual(b.bbox(), (0, 0, 10, 10))
        self.assertIsNone(boundary_at(lines(), (11, 11)))                  # dehors : rien

    def test_islands(self):
        paths = lines() + [geom.Path([geom.circle((5, 5), 2)])]
        b = boundary_at(paths, (1, 1))
        self.assertEqual(len(b.contours), 2)                                 # carré moins le disque
        self.assertAlmostEqual(area(b), 100 - 3.14159 * 4, delta=0.2)
        b = boundary_at(paths, (1, 1), islands=False)
        self.assertEqual(len(b.contours), 1)
        b = boundary_at(paths, (5, 5))                                       # le disque lui-même
        self.assertAlmostEqual(area(b), 3.14159 * 4, delta=0.2)

    def test_tool(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            for p in lines():
                c.doc.add(Shape(path=p))
            w.set_tool('boundary')
            e = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton,
                            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            c.tool_obj.press(c.to_screen(5, 5), (5, 5), e)
            items = c.doc.layers[0].items
            self.assertEqual(len(items), 5)
            self.assertTrue(items[-1].path.contours[0].closed)
            w.undo()
            self.assertEqual(len(c.doc.layers[0].items), 4)
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
