"""Round 739 : Polygone par côté (option Côté de POLYGON, d'après CADCraft)
— deux clics donnent un côté ; polygone paramétré à gauche, Ctrl à droite."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core.forms import Polygon, polygon_on_edge


def _verts(p):
    return [s.p0 for s in p.build().contours[0].segments]


def _has(pts, q):
    return any(math.dist(p, q) < 1e-6 for p in pts)


class TestCore(unittest.TestCase):
    def test_hexagon_left(self):
        p = polygon_on_edge((0, 0), (10, 0), 6)
        v = _verts(p)
        self.assertEqual(len(v), 6)
        self.assertTrue(_has(v, (0, 0)) and _has(v, (10, 0)))
        self.assertTrue(all(q[1] > -1e-6 for q in v))                       # à gauche de (0,0)→(10,0) : au-dessus
        self.assertTrue(all(abs(math.dist(v[i], v[i - 1]) - 10) < 1e-6 for i in range(6)))
        self.assertEqual((p.size_mode, p.size, p.sides), ('longueur', 10, 6))

    def test_square_right_and_oblique(self):
        v = _verts(polygon_on_edge((0, 0), (10, 0), 4, right=True))
        self.assertTrue(_has(v, (0, -10)) and _has(v, (10, -10)))
        v = _verts(polygon_on_edge((2, 3), (5, 7), 3))                      # côté oblique de 5
        self.assertTrue(_has(v, (2, 3)) and _has(v, (5, 7)))
        self.assertTrue(all(abs(math.dist(v[i], v[i - 1]) - 5) < 1e-6 for i in range(3)))

    def test_base_and_degenerate(self):
        p = polygon_on_edge((0, 0), (10, 0), 5, base=Polygon(rounding=1.5))
        self.assertEqual(p.rounding, 1.5)                                    # réglages repris
        self.assertIsNone(polygon_on_edge((1, 1), (1, 1), 5))
        self.assertEqual(polygon_on_edge((0, 0), (10, 0), 2).sides, 3)       # au moins trois côtés


class TestTool(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.resize(1000, 700)

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def click(self, *pts, ctrl=False):
        from PySide6.QtCore import QEvent, QPointF, Qt
        from PySide6.QtGui import QMouseEvent
        t = self.w.canvas.tool_obj
        mods = Qt.KeyboardModifier.ControlModifier if ctrl else Qt.KeyboardModifier.NoModifier
        for p in pts:
            ev = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton,
                             Qt.MouseButton.LeftButton, mods)
            t.move(QPointF(0, 0), p, ev)
            t.press(QPointF(0, 0), p, ev)

    def test_tool(self):
        w = self.w
        w.canvas.doc.active_layer.items = []
        w.canvas.poly_sides = 8
        w.set_tool('polygon_edge')
        self.click((0, 0), (10, 0))
        it = w.canvas.doc.active_layer.items[-1]
        v = [s.p0 for s in it.path.contours[0].segments]
        self.assertEqual(len(v), 8)
        self.assertTrue(all(q[1] > -1e-6 for q in v))
        w.set_tool('polygon_edge')
        self.click((0, 0), (10, 0), ctrl=True)                          # Ctrl : sous le côté
        v = [s.p0 for s in w.canvas.doc.active_layer.items[-1].path.contours[0].segments]
        self.assertTrue(all(q[1] < 1e-6 for q in v))
        w.set_tool('select')
        from vectordrive.ui import icons
        self.assertIn('polygon_edge', icons.ICONS)
        a = w.A['tool_polygon_edge']
        self.assertFalse(a.icon().isNull())
        self.assertTrue(a.toolTip())


if __name__ == '__main__':
    unittest.main()
