"""Round 738 : Arc centre, départ, fin et Cercle 2 points (méthodes d'ARC et
de CIRCLE, d'après CADCraft)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core.shapes import arc_center, circle_2points


def _near(a, b):
    return math.dist(a, b) < 1e-6


class TestCore(unittest.TestCase):
    def test_circle_2points(self):
        c = circle_2points((0, 0), (10, 0))
        bb = c.bbox()
        self.assertTrue(_near(bb[:2], (0, -5)) and _near(bb[2:], (10, 5)))
        self.assertTrue(c.closed)
        self.assertIsNone(circle_2points((3, 3), (3, 3)))

    def test_arc_center(self):
        a = arc_center((0, 0), (10, 0), (0, 3))                 # quart de tour, sens trigonométrique
        self.assertTrue(_near(a.start, (10, 0)) and _near(a.end, (0, 10)))
        pts = a.flatten(0.01)
        self.assertTrue(all(abs(math.hypot(*p) - 10) < 0.02 for p in pts))
        self.assertTrue(all(p[0] > -1e-6 and p[1] > -1e-6 for p in pts))     # dans le premier quart
        b = arc_center((0, 0), (10, 0), (0, 3), clockwise=True)  # trois quarts, sens horaire
        self.assertTrue(_near(b.end, (0, 10)))
        self.assertTrue(any(p[1] < -9.9 for p in b.flatten(0.01)))           # passe par le bas
        self.assertFalse(b.closed)

    def test_degenerate(self):
        self.assertIsNone(arc_center((0, 0), (0, 0), (5, 5)))   # rayon nul
        self.assertIsNone(arc_center((0, 0), (5, 0), (0, 0)))   # fin sur le centre
        self.assertIsNone(arc_center((0, 0), (5, 0), (9, 0)))   # fin dans la direction du départ


class TestTools(unittest.TestCase):
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
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtCore import QEvent
        t = self.w.canvas.tool_obj
        mods = Qt.KeyboardModifier.ControlModifier if ctrl else Qt.KeyboardModifier.NoModifier
        for p in pts:
            ev = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton,
                             Qt.MouseButton.LeftButton, mods)
            t.move(QPointF(0, 0), p, ev)
            t.press(QPointF(0, 0), p, ev)

    def shapes(self):
        return list(self.w.canvas.doc.active_layer.items)

    def test_tools_draw(self):
        w = self.w
        w.canvas.doc.active_layer.items = []
        w.set_tool('circle2')
        self.click((0, 0), (20, 0))
        bb = self.shapes()[-1].bbox()
        self.assertAlmostEqual(bb[3] - bb[1], 20, 5)
        w.set_tool('arc_center')
        self.click((0, 0), (10, 0), (-5, 0))                    # demi-tour par le haut
        arc = self.shapes()[-1].path.contours[0]
        self.assertTrue(_near(arc.end, (-10, 0)))
        self.assertTrue(any(p[1] > 9.9 for p in arc.flatten(0.01)))
        w.set_tool('arc_center')                                # l'outil rend la main après chaque tracé
        self.click((0, 0), (10, 0), (0, -5), ctrl=True)         # Ctrl : sens horaire, un quart par le bas
        arc = self.shapes()[-1].path.contours[0]
        self.assertTrue(_near(arc.end, (0, -10)))
        self.assertTrue(all(p[1] < 1e-6 for p in arc.flatten(0.01)))
        self.assertEqual(len(self.shapes()), 3)
        w.set_tool('select')

    def test_ribbon_icons(self):
        from vectordrive.ui import icons
        for k in ('arc_center', 'circle2'):
            self.assertIn(k, icons.ICONS)
            a = self.w.A[f'tool_{k}']
            self.assertFalse(a.icon().isNull())
            self.assertTrue(a.toolTip())
            self.assertTrue(a.isCheckable())


if __name__ == '__main__':
    unittest.main()
