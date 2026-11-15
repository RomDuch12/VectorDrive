"""Round 119 : points par coordonnées (positionnement du curseur de
TypeEdit) ; rectangle, ellipse et trait passent par le même chemin que les
autres outils (symétries comprises)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core.document import Plate


class TestCoordinates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.resize(1000, 700)

    @classmethod
    def tearDownClass(cls):
        cls.w.A['sym_draw'].setChecked(False)
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        self.w.modified = False
        self.w.new_document()
        self.w.canvas.doc.plate = Plate(width=100, height=60)
        self.w.canvas.fit()
        self.w._last_xy = (0.0, 0.0)

    def items(self):
        return self.w.canvas.doc.layers[0].items

    def test_rect_two_points(self):
        w = self.w
        w.set_tool('rect')
        self.assertTrue(w.point_by_coordinates({'x1': 10, 'y1': 5, 'x2': 40.5, 'y2': 25.25}))
        self.assertEqual(len(self.items()), 1)
        self.assertEqual(tuple(round(v, 6) for v in self.items()[0].bbox()), (10, 5, 40.5, 25.25))

    def test_relative_points_with_circle3(self):
        w = self.w
        w.set_tool('circle3')
        w.point_by_coordinates({'x': 50, 'y': 30})
        w.point_by_coordinates({'x': 10, 'y': 0, 'relatif': True})              # (60, 30)
        w.point_by_coordinates({'x': -10, 'y': 10, 'relatif': True})            # (50, 40)
        self.assertEqual(len(self.items()), 1)
        bb = self.items()[0].bbox()
        self.assertAlmostEqual(bb[2] - bb[0], 2 * 50 ** 0.5, places=4)          # cercle centré (55, 35), rayon √50
        self.assertAlmostEqual((bb[0] + bb[2]) / 2, 55, places=4)
        w.set_tool('select')

    def test_select_tool_refuses(self):
        self.w.set_tool('select')
        from unittest import mock
        with mock.patch('vectordrive.ui.main_window.QMessageBox.information') as box:
            self.assertFalse(self.w.point_by_coordinates({'x': 1, 'y': 1}))
            box.assert_called_once()

    def test_mouse_rect_respects_symmetry(self):
        w = self.w
        w.A['sym_draw'].setChecked(True)
        w.set_tool('rect')
        c = w.canvas
        c.snap.enabled = False
        a, b = c.to_screen(10, 10), c.to_screen(20, 20)

        def ev(kind, p, btns):
            return QMouseEvent(kind, p, p, Qt.MouseButton.LeftButton, btns, Qt.KeyboardModifier.NoModifier)
        c.mousePressEvent(ev(QEvent.Type.MouseButtonPress, a, Qt.MouseButton.LeftButton))
        c.mouseMoveEvent(ev(QEvent.Type.MouseMove, b, Qt.MouseButton.LeftButton))
        c.mouseReleaseEvent(ev(QEvent.Type.MouseButtonRelease, b, Qt.MouseButton.NoButton))
        self.assertEqual(len(self.items()), 1)
        self.assertEqual(len(self.items()[0].path.contours), 2)                  # le reflet par rapport à x = 50
        bb = self.items()[0].bbox()
        self.assertAlmostEqual(bb[0], 10, places=3)
        self.assertAlmostEqual(bb[2], 90, places=3)
        w.A['sym_draw'].setChecked(False)
        self.assertTrue(QPointF(0, 0) is not None)


if __name__ == '__main__':
    unittest.main()
