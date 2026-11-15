"""Round 741 : Rectangle 3 points (RECTANG incliné, d'après CADCraft) — un
côté par deux clics, l'autre côté par le troisième ; rectangle paramétré."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core.forms import Rect, rect_by_3points


def _verts(r):
    return [s.p0 for s in r.build().contours[0].segments]


def _has(pts, q):
    return any(math.dist(p, q) < 1e-6 for p in pts)


class TestCore(unittest.TestCase):
    def test_sides(self):
        r = rect_by_3points((0, 0), (20, 0), (5, 8))
        v = _verts(r)
        for q in ((0, 0), (20, 0), (20, 8), (0, 8)):
            self.assertTrue(_has(v, q), q)
        v = _verts(rect_by_3points((0, 0), (20, 0), (13, -8)))            # du côté du 3e point
        self.assertTrue(_has(v, (0, -8)) and _has(v, (20, -8)))

    def test_tilted(self):
        r = rect_by_3points((0, 0), (10, 10), (0, 10))                     # côté à 45°, l'autre de √50
        self.assertAlmostEqual(r.angle, 45)
        v = _verts(r)
        for q in ((0, 0), (10, 10), (5, 15), (-5, 5)):
            self.assertTrue(_has(v, q), q)

    def test_corners_kept_and_degenerate(self):
        r = rect_by_3points((0, 0), (30, 0), (0, 10), base=Rect(corner='arrondi', radius=2))
        self.assertEqual((r.corner, r.radius), ('arrondi', 2))
        self.assertGreater(len(r.build().contours[0].segments), 4)          # coins arrondis
        self.assertIsNone(rect_by_3points((1, 1), (1, 1), (5, 5)))
        self.assertIsNone(rect_by_3points((0, 0), (10, 0), (25, 0)))       # 3e point sur le côté


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

    def test_tool(self):
        from PySide6.QtCore import QEvent, QPointF, Qt
        from PySide6.QtGui import QMouseEvent
        from vectordrive.core import forms
        w = self.w
        w.canvas.doc.active_layer.items = []
        w.set_tool('rect3')
        t = w.canvas.tool_obj
        for p in ((0, 0), (0, 30), (-12, 4)):                   # côté vertical de 30, l'autre de 12 à gauche
            ev = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton,
                             Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            t.move(QPointF(0, 0), p, ev)
            t.press(QPointF(0, 0), p, ev)
        it = w.canvas.doc.active_layer.items[-1]
        bb = it.bbox()
        self.assertAlmostEqual(bb[0], -12, 4)
        self.assertAlmostEqual(bb[3], 30, 4)
        self.assertEqual(type(forms.spec_of(it)).__name__, 'Rect')    # forme paramétrée, retouchable
        w.set_tool('select')
        from vectordrive.ui import icons
        self.assertIn('rect3', icons.ICONS)
        self.assertFalse(w.A['tool_rect3'].icon().isNull())
        self.assertTrue(w.A['tool_rect3'].toolTip())


if __name__ == '__main__':
    unittest.main()
