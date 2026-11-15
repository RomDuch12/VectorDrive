"""Round 740 : Ellipse par axe (ELLIPSE par les bouts d'un axe, d'après
CADCraft) — ellipse inclinée d'un seul geste, paramétrée."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core.forms import ellipse_by_axis


class TestCore(unittest.TestCase):
    def test_level(self):
        e = ellipse_by_axis((0, 0), (20, 0), (10, 4))
        self.assertEqual((e.cx, e.cy, e.width, e.height, e.angle), (10, 0, 20, 8, 0))
        bb = e.build().bbox()
        self.assertAlmostEqual(bb[3] - bb[1], 8, 4)

    def test_tilted(self):
        e = ellipse_by_axis((0, 0), (10, 10), (2, 8))           # axe à 45°, l'autre demi-axe √18
        self.assertAlmostEqual(e.angle, 45)
        self.assertAlmostEqual(e.width, math.hypot(10, 10))
        self.assertAlmostEqual(e.height, 2 * math.hypot(3, 3))
        pts = e.build().contours[0].flatten(0.01)
        far = max(pts, key=lambda p: math.dist(p, (5, 5)))
        self.assertAlmostEqual(math.dist(far, (5, 5)), e.width / 2, 2)
        self.assertAlmostEqual(abs(far[0] - 5), abs(far[1] - 5), 1)          # le grand axe suit la diagonale

    def test_degenerate(self):
        self.assertIsNone(ellipse_by_axis((1, 1), (1, 1), (5, 5)))
        self.assertIsNone(ellipse_by_axis((0, 0), (10, 0), (5, 0)))      # autre demi-axe nul


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
        w.set_tool('ellipse_axis')
        t = w.canvas.tool_obj
        for p in ((0, 0), (0, 30), (5, 15)):                    # axe vertical de 30, demi-axe de 5
            ev = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton,
                             Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            t.move(QPointF(0, 0), p, ev)
            t.press(QPointF(0, 0), p, ev)
        it = w.canvas.doc.active_layer.items[-1]
        bb = it.bbox()
        self.assertAlmostEqual(bb[2] - bb[0], 10, 3)
        self.assertAlmostEqual(bb[3] - bb[1], 30, 3)
        spec = forms.spec_of(it)
        self.assertEqual(type(spec).__name__, 'Ellipse')        # forme paramétrée, retouchable
        self.assertAlmostEqual(spec.angle, 90)
        w.set_tool('select')
        from vectordrive.ui import icons
        self.assertIn('ellipse_axis', icons.ICONS)
        self.assertFalse(w.A['tool_ellipse_axis'].icon().isNull())
        self.assertTrue(w.A['tool_ellipse_axis'].toolTip())


if __name__ == '__main__':
    unittest.main()
