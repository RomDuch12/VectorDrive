"""Round 833 : Le centre de rotation se déplace ; garder l'original en tournant."""
import os
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Layer, Plate, Shape
from vectordrive.core.geom import Path
from vectordrive.ui.canvas import Canvas
from vectordrive.ui.main_window import MainWindow

app = QApplication.instance() or QApplication([])
NONE = Qt.KeyboardModifier.NoModifier
SHIFT = Qt.KeyboardModifier.ShiftModifier
CTRL = Qt.KeyboardModifier.ControlModifier
ALT = Qt.KeyboardModifier.AltModifier


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = MainWindow()
        cls.win.resize(1200, 800)

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()
        cls.win.deleteLater()

    def setUp(self):
        self.c = self.win.canvas
        self.doc = self.c.doc
        self.layer = Layer(name='Plan 1')
        self.doc.layers[:] = [self.layer]
        self.doc.active = self.layer.id
        self.doc.plate = Plate(width=200.0, height=100.0)
        self.win._undo.clear()
        self.c.scale = 8.0
        self.c.move_delay_ms = 0
        self.s = Shape(path=Path([geom.rect(0.0, 0.0, 20.0, 10.0)]))
        self.layer.items.append(self.s)
        self.win.set_tool('select')
        self.c.select([self.s])
        self.c.rot_mode = True

    def mouse(self, kind, pos, mods=NONE):
        button = Qt.MouseButton.NoButton if kind == QEvent.Type.MouseMove else Qt.MouseButton.LeftButton
        buttons = Qt.MouseButton.NoButton if kind == QEvent.Type.MouseButtonRelease else Qt.MouseButton.LeftButton
        glob = QPointF(self.c.mapToGlobal(QPoint(int(pos.x()), int(pos.y()))))
        ev = QMouseEvent(kind, QPointF(pos), glob, button, buttons, mods)
        if kind == QEvent.Type.MouseButtonPress:
            self.c.mousePressEvent(ev)
        elif kind == QEvent.Type.MouseMove:
            self.c.mouseMoveEvent(ev)
        else:
            self.c.mouseReleaseEvent(ev)

    def press(self, x, y, mods=NONE):
        self.mouse(QEvent.Type.MouseButtonPress, self.c.to_screen(x, y), mods)

    def move(self, x, y, mods=NONE):
        self.mouse(QEvent.Type.MouseMove, self.c.to_screen(x, y), mods)

    def release(self, x, y, mods=NONE):
        self.mouse(QEvent.Type.MouseButtonRelease, self.c.to_screen(x, y), mods)

    def drag(self, a, b, mods=NONE):
        self.press(*a, mods)
        self.move(*b, mods)
        self.release(*b, mods)

    def bbox(self):
        return self.layer.items[0].path.bbox()


class Matrices(unittest.TestCase):
    BB = (0.0, 0.0, 20.0, 10.0)

    def test_rotation_about_the_given_center(self):
        m, a = Canvas.rotation_matrix(self.BB, (10.0, 0.0), (0.0, 10.0), center=(0.0, 0.0))
        self.assertAlmostEqual(a, 90.0)
        x, y = m.apply((10.0, 0.0))
        self.assertAlmostEqual(x, 0.0)
        self.assertAlmostEqual(y, 10.0)

    def test_rotation_default_stays_the_middle(self):
        m, _a = Canvas.rotation_matrix(self.BB, (20.0, 5.0), (10.0, 15.0))
        x, y = m.apply((10.0, 5.0))
        self.assertAlmostEqual(x, 10.0)
        self.assertAlmostEqual(y, 5.0)

    def test_scale_anchor_stays_put(self):
        m = Canvas.scale_matrix(self.BB, 2, (40.0, 20.0), anchor=(0.0, 0.0))
        self.assertAlmostEqual(m.apply((0.0, 0.0))[0], 0.0)
        self.assertAlmostEqual(m.apply((20.0, 10.0))[0], 40.0)


class Pivot(Base):
    def test_drag_moves_the_center_and_nothing_else(self):
        before = self.bbox()
        n = len(self.win._undo)
        self.drag((10.0, 5.0), (30.0, 40.0))
        self.assertAlmostEqual(self.c.pivot[0], 30.0, delta=0.2)
        self.assertAlmostEqual(self.c.pivot[1], 40.0, delta=0.2)
        self.assertTrue(self.c.rot_mode)
        self.assertEqual(self.bbox(), before)
        self.assertEqual(len(self.win._undo), n)

    def test_rotation_turns_around_it(self):
        self.c.pivot = (40.0, 10.0)
        self.drag((20.0, 10.0), (40.0, 30.0))          # coin droit, un quart de tour autour de (40, 10)
        b = self.bbox()
        self.assertAlmostEqual(b[1], 30.0, delta=0.2)  # le bord droit de l'objet, à 20 du centre, passe au-dessus
        self.assertAlmostEqual(b[3], 50.0, delta=0.2)
        self.assertEqual(self.c.pivot, (40.0, 10.0))
        self.assertTrue(self.c.rot_mode)

    def test_ctrl_steps_around_it(self):
        _m, a = Canvas.rotation_matrix((0.0, 0.0, 20.0, 10.0), (20.0, 10.0), (25.0, 15.0), step=15.0, center=(30.0, 5.0))
        self.assertAlmostEqual(a % 15.0, 0.0)
        self.c.pivot = (40.0, 10.0)
        self.drag((20.0, 10.0), (40.0, 31.0), CTRL)
        self.assertAlmostEqual(self.bbox()[1], 30.0, delta=0.01)

    def test_shift_click_gives_the_middle_back(self):
        self.c.pivot = (30.0, 40.0)
        self.press(30.0, 40.0, SHIFT)
        self.release(30.0, 40.0, SHIFT)
        self.assertIsNone(self.c.pivot)

    def test_new_selection_forgets_it(self):
        self.c.pivot = (30.0, 40.0)
        self.c.select([self.s])
        self.assertIsNone(self.c.pivot)

    def test_default_center_does_not_hide_a_small_object_handle(self):
        small = Shape(path=Path([geom.rect(50.0, 50.0, 0.5, 0.5)]))
        self.layer.items.append(small)
        self.c.select([small])
        self.c.rot_mode = True
        self.press(50.5, 50.5)
        self.assertEqual(self.c._drag['kind'], 'rotate')
        self.release(50.5, 50.5)

    def test_a_moved_center_can_be_grabbed_over_a_handle(self):
        self.c.pivot = (20.0, 10.0)
        self.press(20.0, 10.0)
        self.assertEqual(self.c._drag['kind'], 'pivot')
        self.release(20.0, 10.0)

    def test_shift_keeps_the_original_when_turning(self):
        self.drag((20.0, 10.0), (10.0, 20.0), SHIFT)
        self.assertEqual(len(self.layer.items), 2)
        self.assertTrue(self.c.rot_mode)
        self.win.undo()
        self.assertEqual(len(self.doc.layers[0].items), 1)

    def test_alt_keeps_the_original_when_scaling(self):
        self.c.rot_mode = False
        self.drag((20.0, 10.0), (40.0, 20.0), ALT)
        self.assertEqual(len(self.layer.items), 2)
        self.assertEqual(self.s.path.bbox(), (0.0, 0.0, 20.0, 10.0))

    def test_plain_turn_keeps_one_object(self):
        self.drag((20.0, 10.0), (10.0, 20.0))
        self.assertEqual(len(self.layer.items), 1)

    def test_scale_uses_a_moved_center(self):
        self.c.pivot = (0.0, 0.0)
        self.c.rot_mode = False
        self.drag((20.0, 10.0), (40.0, 20.0))
        b = self.bbox()
        self.assertAlmostEqual(b[0], 0.0)
        self.assertAlmostEqual(b[2], 40.0, delta=0.2)
        self.assertEqual(self.c.pivot, (0.0, 0.0))

    def test_second_click_tells_the_keys(self):
        self.c.rot_mode = False
        seen = []
        self.c.measured.connect(seen.append)
        self.press(5.0, 0.0)
        self.release(5.0, 0.0)
        self.c.measured.disconnect(seen.append)
        self.assertTrue(self.c.rot_mode)
        self.assertTrue(any('15°' in s for s in seen))


class F2(Base):
    def fake(self, **values):
        test = self

        class Fake:
            def __init__(self, parent, title, params, labels, warning='', choices=None):
                self.params = params
                test.title, test.labels = title, labels

            def exec(self):
                return True

            def result_params(self):
                for k, v in values.items():
                    setattr(self.params, k, v)
                return self.params
        return mock.patch('vectordrive.ui.dialogs.ParamsDialog', Fake)

    def test_during_the_drag_of_the_center(self):
        self.press(10.0, 5.0)
        self.assertEqual(self.c._drag['kind'], 'pivot')
        with self.fake(x=3.0, y=4.0):
            self.win.f2()
        self.assertEqual(self.c.pivot, (3.0, 4.0))
        self.assertIsNone(self.c._drag)

    def test_in_rotation_mode_angle_and_center(self):
        with self.fake(angle=90.0, x=0.0, y=0.0):
            self.win.f2()
        self.assertIn('angle', self.labels)
        b = self.bbox()
        self.assertAlmostEqual(b[0], -10.0)
        self.assertAlmostEqual(b[3], 20.0)
        self.assertEqual(self.c.pivot, (0.0, 0.0))
        self.assertTrue(self.c.rot_mode)

    def test_untouched_center_stays_the_middle(self):
        with self.fake(angle=90.0):
            self.win.f2()
        self.assertIsNone(self.c.pivot)
        b = self.bbox()
        self.assertAlmostEqual((b[0] + b[2]) / 2, 10.0)

    def test_during_a_turn_uses_the_center(self):
        self.c.pivot = (0.0, 0.0)
        self.press(20.0, 10.0)
        self.move(10.0, 20.0)
        with self.fake(angle=180.0):
            self.win.f2()
        b = self.bbox()
        self.assertAlmostEqual(b[0], -20.0)
        self.assertAlmostEqual(b[3], 0.0)

    def test_outside_rotation_mode_unchanged(self):
        self.c.rot_mode = False
        with mock.patch.object(self.win, 'focus_dimensions') as focus:
            self.win.f2()
        focus.assert_called_once()


if __name__ == '__main__':
    unittest.main()
