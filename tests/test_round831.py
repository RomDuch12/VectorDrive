"""Round 831 : F2 pendant le geste."""
import os
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QInputDialog

from vectordrive.core import geom
from vectordrive.core.document import Layer, Plate, Shape
from vectordrive.core.geom import Affine, Path
from vectordrive.ui import tools as T
from vectordrive.ui.dialogs import ParamsDialog
from vectordrive.ui.main_window import MainWindow
from vectordrive.ui.points_dialog import PointsDialog

app = QApplication.instance() or QApplication([])


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = MainWindow()

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
        self.win.set_tool('select')
        self.c._drag = None
        self.c.rot_mode = False

    def tearDown(self):
        self.c._drag = None
        self.c.rot_mode = False
        self.win.set_tool('select')
        self.doc.extra.pop('guides', None)


class Dialog(Base):
    def test_rows(self):
        d = PointsDialog(None, [(1.0, 2.0), (3.0, 4.0)])
        self.assertEqual(d.points(), [(1.0, 2.0), (3.0, 4.0)])
        d.add_row()
        self.assertEqual(d.points()[-1], (3.0, 4.0))
        self.assertEqual(len(d.points()), 3)
        d.table.cellWidget(2, 0).setValue(-7.5)
        self.assertEqual(d.points()[2], (-7.5, 4.0))
        d.table.setCurrentCell(0, 0)
        d.remove_row()
        self.assertEqual(d.points()[0], (3.0, 4.0))

    def test_empty_and_remove_everything(self):
        d = PointsDialog(None, [])
        self.assertEqual(d.points(), [])
        d.remove_row()
        d.add_row()
        self.assertEqual(d.points(), [(0.0, 0.0)])

    def test_finish_button(self):
        d = PointsDialog(None, [(1.0, 2.0)])
        self.assertFalse(d.finish)
        d.b_finish.click()
        self.assertTrue(d.finish)


class Drawing(Base):
    def draw(self, key):
        self.win.set_tool(key)
        t = self.c.tool_obj
        for q in ((0.0, 0.0), (10.0, 0.0)):
            t.press(QPointF(0, 0), q, None)
        return t

    def test_each_tool_gives_its_points(self):
        for key in ('polyline', 'spline', 'dline', 'sym_ox', 'bezier'):
            with self.subTest(key), mock.patch.object(MainWindow, 'dline_dialog', lambda s, cur: {'left': 1.0, 'right': 1.0}):
                self.win.settings.remove('ligne_double/reglages')
                self.c.dline = None
                t = self.draw(key)
                self.assertEqual(t.points(), [(0.0, 0.0), (10.0, 0.0)])

    def test_other_tools_have_none(self):
        self.win.set_tool('select')
        self.assertIsNone(self.c.tool_obj)
        self.win.set_tool('rect')
        self.assertIsNone(self.c.tool_obj.points() if self.c.tool_obj else None)

    def test_correct_a_point(self):
        t = self.draw('polyline')
        self.win.apply_tool_points(t, [(0.0, 0.0), (10.0, 5.0), (20.0, 5.0)])
        self.assertEqual(t.pts, [(0.0, 0.0), (10.0, 5.0), (20.0, 5.0)])
        self.assertEqual(self.layer.items, [])

    def test_finish_makes_the_shape(self):
        t = self.draw('polyline')
        self.win.apply_tool_points(t, [(0.0, 0.0), (10.0, 5.0), (20.0, 5.0)], finish=True)
        self.assertEqual(len(self.layer.items), 1)
        self.assertEqual(len(self.layer.items[0].path.contours[0].segments), 2)

    def test_finish_with_one_point_draws_nothing(self):
        t = self.draw('polyline')
        self.win.apply_tool_points(t, [(0.0, 0.0)], finish=True)
        self.assertEqual(self.layer.items, [])

    def test_bezier_keeps_its_handles(self):
        self.win.set_tool('bezier')
        t = self.c.tool_obj
        t.press(QPointF(0, 0), (0.0, 0.0), None)
        t.nodes[0][1] = (3.0, 3.0)
        t.drag = False
        self.win.apply_tool_points(t, [(1.0, 1.0), (10.0, 0.0)])
        self.assertEqual(t.nodes, [[(1.0, 1.0), (3.0, 3.0)], [(10.0, 0.0), (0.0, 0.0)]])
        self.win.apply_tool_points(t, [(1.0, 1.0), (10.0, 0.0)], finish=True)
        self.assertEqual(len(self.layer.items), 1)

    def test_symmetric_curve_forgets_removed_corners(self):
        self.win.set_tool('sym_ox')
        t = self.c.tool_obj
        t.pts, t.corners = [(0.0, 10.0), (5.0, 10.0), (9.0, 10.0)], {0, 2}
        self.win.apply_tool_points(t, [(0.0, 10.0), (5.0, 10.0)])
        self.assertEqual(t.corners, {0})

    def test_f2_goes_to_the_points_during_a_drawing(self):
        t = self.draw('polyline')
        with mock.patch.object(PointsDialog, 'exec', return_value=True), \
                mock.patch.object(PointsDialog, 'points', return_value=[(1.0, 1.0), (2.0, 2.0)]):
            self.win.f2()
        self.assertEqual(t.pts, [(1.0, 1.0), (2.0, 2.0)])

    def test_f2_with_no_point_offers_the_view_centre(self):
        self.win.set_tool('polyline')
        d = self.win.tool_points_dialog(self.c.tool_obj, exec_dialog=False)
        self.assertEqual(len(d.points()), 1)
        d.deleteLater()

    def test_f2_cancelled(self):
        t = self.draw('polyline')
        with mock.patch.object(PointsDialog, 'exec', return_value=False):
            self.win.f2()
        self.assertEqual(t.pts, [(0.0, 0.0), (10.0, 0.0)])

    def test_f2_with_selection_and_no_tool_still_goes_to_the_form(self):
        with mock.patch.object(MainWindow, 'focus_dimensions') as focus:
            self.win.f2()
        focus.assert_called_once()


class Gesture(Base):
    def shape(self):
        s = Shape(path=Path([geom.rect(0.0, 0.0, 20.0, 10.0)]))
        self.layer.items.append(s)
        self.c.select([s])
        return s

    def answer(self, **values):
        import types
        fake = mock.MagicMock()
        fake.return_value.exec.return_value = bool(values)
        fake.return_value.result_params.return_value = types.SimpleNamespace(**values)
        return mock.patch('vectordrive.ui.dialogs.ParamsDialog', fake)

    def test_move_by_the_grabbed_point(self):
        s = self.shape()
        self.c._drag = {'kind': 'move', 'start': QPointF(0, 0), 'delta': (1.0, 1.0), 'grab': (5.0, 5.0), 'armed': True}
        with self.answer(x=50.0, y=-20.0), mock.patch.object(MainWindow, '_shift_held', staticmethod(lambda: False)):
            self.win.f2()
        self.assertIsNone(self.c._drag)
        b = self.layer.items[0].path.bbox()
        self.assertAlmostEqual(b[0], 45.0)
        self.assertAlmostEqual(b[1], -25.0)
        self.win.undo()
        self.assertAlmostEqual(self.doc.layers[0].items[0].path.bbox()[0], 0.0)
        self.assertIsNotNone(s)

    def test_move_with_shift_makes_a_copy(self):
        self.shape()
        self.c._drag = {'kind': 'move', 'start': QPointF(0, 0), 'delta': (0.0, 0.0), 'grab': (0.0, 0.0), 'armed': True}
        with self.answer(x=50.0, y=0.0), mock.patch.object(MainWindow, '_shift_held', staticmethod(lambda: True)):
            self.win.f2()
        self.assertEqual(len(self.layer.items), 2)

    def test_move_cancelled_changes_nothing(self):
        self.shape()
        self.c._drag = {'kind': 'move', 'start': QPointF(0, 0), 'delta': (3.0, 3.0), 'grab': (0.0, 0.0), 'armed': True}
        with self.answer():
            self.win.f2()
        self.assertIsNone(self.c._drag)
        self.assertAlmostEqual(self.layer.items[0].path.bbox()[0], 0.0)

    def test_move_not_armed_is_left_alone(self):
        self.shape()
        self.c._drag = {'kind': 'move', 'start': QPointF(0, 0), 'delta': (0.0, 0.0), 'grab': (0.0, 0.0), 'armed': False}
        self.assertIsNone(self.c.take_gesture())
        self.assertIsNotNone(self.c._drag)

    def test_other_gestures_are_left_alone(self):
        self.c._drag = {'kind': 'pan', 'start': QPointF(0, 0), 'ox': 0.0, 'oy': 0.0}
        self.assertIsNone(self.c.take_gesture())
        self.assertIsNotNone(self.c._drag)

    def test_rotation_angle(self):
        self.shape()
        bb = self.c.selection_bbox()
        self.c.rot_mode = True
        self.c._drag = {'kind': 'rotate', 'start': QPointF(0, 0), 'now': QPointF(0, 0), 'bb': bb, 'handle': 0,
                        'p0': (0.0, 0.0), 'm': None, 'angle': 12.0}
        with self.answer(angle=90.0, x=10.0, y=5.0):
            self.win.f2()
        b = self.layer.items[0].path.bbox()
        self.assertAlmostEqual(b[2] - b[0], 10.0, places=6)
        self.assertAlmostEqual(b[3] - b[1], 20.0, places=6)
        self.assertAlmostEqual((b[0] + b[2]) / 2, 10.0, places=6)
        self.assertTrue(self.c.rot_mode)

    def test_scale_from_the_opposite_handle(self):
        self.shape()
        bb = self.c.selection_bbox()
        handles = self.c.doc_handles(bb)
        i = min(range(8), key=lambda k: abs(handles[k][0] - bb[2]) + abs(handles[k][1] - bb[3]))
        self.c._drag = {'kind': 'scale', 'start': QPointF(0, 0), 'now': QPointF(0, 0), 'bb': bb, 'handle': i,
                        'p0': (0.0, 0.0), 'm': None}
        with self.answer(sx=200.0, sy=50.0):
            self.win.f2()
        b = self.layer.items[0].path.bbox()
        self.assertAlmostEqual(b[0], 0.0, places=6)                     # le coin opposé ne bouge pas
        self.assertAlmostEqual(b[1], 0.0, places=6)
        self.assertAlmostEqual(b[2], 40.0, places=6)
        self.assertAlmostEqual(b[3], 5.0, places=6)

    def test_scale_starts_from_the_current_scale(self):
        self.shape()
        bb = self.c.selection_bbox()
        m = Affine.scaling(1.5, 0.5)
        self.c._drag = {'kind': 'scale', 'start': QPointF(0, 0), 'now': QPointF(0, 0), 'bb': bb, 'handle': 0,
                        'p0': (0.0, 0.0), 'm': m}
        seen = {}

        def fake(parent, title, spec, labels):
            seen['spec'] = spec
            d = mock.MagicMock()
            d.exec.return_value = False
            return d
        with mock.patch('vectordrive.ui.dialogs.ParamsDialog', fake):
            self.win.f2()
        self.assertAlmostEqual(seen['spec'].sx, 150.0)
        self.assertAlmostEqual(seen['spec'].sy, 50.0)

    def mouse(self, kind, pos, buttons=Qt.MouseButton.LeftButton):
        button = Qt.MouseButton.NoButton if kind == QMouseEvent.Type.MouseMove else Qt.MouseButton.LeftButton
        return QMouseEvent(kind, pos, self.c.mapToGlobal(pos), button, buttons, Qt.KeyboardModifier.NoModifier)

    def test_real_mouse_then_f2_then_release(self):
        """Avec les vrais événements de souris : bouton enfoncé, déplacement, F2, relâchement sans effet de plus."""
        self.shape()
        self.c.scale = 4.0
        keep = self.c.move_delay_ms
        self.c.move_delay_ms = 0
        try:
            at = self.c.to_screen(5.0, 0.0)                     # sur le bord du rectangle, loin de ses poignées
            self.c.mousePressEvent(self.mouse(QMouseEvent.Type.MouseButtonPress, at))
            self.assertEqual(self.c._drag['kind'], 'move')
            self.c.mouseMoveEvent(self.mouse(QMouseEvent.Type.MouseMove, QPointF(at.x() + 40, at.y())))
            grab = self.c._drag['grab']
            with self.answer(x=grab[0] + 100.0, y=grab[1]), mock.patch.object(MainWindow, '_shift_held', staticmethod(lambda: False)):
                self.win.A['dims'].trigger()
            self.assertAlmostEqual(self.layer.items[0].path.bbox()[0], 100.0, places=6)
            self.c.mouseReleaseEvent(self.mouse(QMouseEvent.Type.MouseButtonRelease, QPointF(at.x() + 40, at.y()),
                                                Qt.MouseButton.NoButton))
            self.assertAlmostEqual(self.layer.items[0].path.bbox()[0], 100.0, places=6)
        finally:
            self.c.move_delay_ms = keep

    def test_negative_position_goes_through_the_real_dialog(self):
        from dataclasses import dataclass

        @dataclass
        class Spec:
            x: float = -50.5
        self.assertEqual(ParamsDialog(None, 't', Spec(), {'x': 'X'}).result_params().x, -50.5)


class Rulers(Base):
    def press(self, ruler):
        ruler.mousePressEvent(QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(1, 1), QPointF(1, 1),
                                          Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))

    def test_f2_gives_the_position(self):
        n = len(self.c.guides)
        self.press(self.win.ruler_h)
        self.assertIs(self.c.ruler_dragging, self.win.ruler_h)
        with mock.patch.object(QInputDialog, 'getDouble', return_value=(42.5, True)) as ask:
            self.win.f2()
        self.assertEqual(len(self.c.guides), n + 1)
        self.assertEqual(list(self.c.guides[-1]), ['h', 42.5])
        self.assertIsNone(self.c.ruler_dragging)
        self.assertFalse(self.win.ruler_h._dragging)
        self.assertIn('Y', ask.call_args[0][2])

    def test_vertical_guide_from_the_left_ruler(self):
        self.press(self.win.ruler_v)
        with mock.patch.object(QInputDialog, 'getDouble', return_value=(7.0, True)) as ask:
            self.win.f2()
        self.assertEqual(list(self.c.guides[-1]), ['v', 7.0])
        self.assertIn('X', ask.call_args[0][2])

    def test_cancel_draws_no_guide(self):
        n = len(self.c.guides)
        self.press(self.win.ruler_h)
        with mock.patch.object(QInputDialog, 'getDouble', return_value=(1.0, False)):
            self.win.f2()
        self.assertEqual(len(self.c.guides), n)
        self.assertIsNone(self.c.ruler_dragging)

    def test_release_after_the_numbers_adds_nothing_more(self):
        n = len(self.c.guides)
        r = self.win.ruler_h
        self.press(r)
        with mock.patch.object(QInputDialog, 'getDouble', return_value=(1.0, True)):
            self.win.f2()
        r.mouseReleaseEvent(QMouseEvent(QMouseEvent.Type.MouseButtonRelease, QPointF(1, 1), QPointF(1, 1),
                                        Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier))
        self.assertEqual(len(self.c.guides), n + 1)

    def test_plain_release_still_works(self):
        r = self.win.ruler_h
        self.press(r)
        r.mouseReleaseEvent(QMouseEvent(QMouseEvent.Type.MouseButtonRelease, QPointF(1, 1), QPointF(1, 1),
                                        Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier))
        self.assertIsNone(self.c.ruler_dragging)


if __name__ == '__main__':
    unittest.main()
