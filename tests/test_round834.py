"""Round 834 : Arc 3 points fidèle à l'aperçu, Maj pour la courbure en dernier, F2 sur les arcs et les cercles."""
import math
import os
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core.document import Layer, Plate, Shape
from vectordrive.ui.main_window import MainWindow
from vectordrive.ui.points_dialog import PointsDialog

app = QApplication.instance() or QApplication([])
KEYS = ('arc/rayon', 'arc/depart', 'arc/arrivee', 'arc/horaire')


class Ev:
    def __init__(self, mods=Qt.KeyboardModifier.NoModifier):
        self.mods = mods

    def modifiers(self):
        return self.mods


SHIFT = Ev(Qt.KeyboardModifier.ShiftModifier)
PLAIN = Ev()


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
        self.c.scale = 8.0

    def tearDown(self):
        for k in KEYS:
            self.win.settings.remove(k)
        self.win.set_tool('select')

    def tool(self, name):
        self.win.A[f'tool_{name}'].trigger()
        return self.c.tool_obj

    def click(self, tool, p, ev=PLAIN):
        tool.press(QPointF(0, 0), p, ev)

    def shapes(self):
        return [i for i in self.layer.items if isinstance(i, Shape)]

    def contour(self):
        return self.shapes()[-1].path.contours[0]

    def passes_through(self, contour, p, tol=1e-3):
        pts = contour.flatten(0.001)
        return min(math.dist(q, p) for q in pts) < tol


class Arc3(Base):
    def test_second_click_is_the_passage(self):
        t = self.tool('arc')
        for p in ((0.0, 0.0), (10.0, 10.0), (20.0, 0.0)):
            self.click(t, p)
        c = self.contour()
        self.assertAlmostEqual(c.start[0], 0.0)
        self.assertAlmostEqual(c.end[0], 20.0)
        self.assertTrue(self.passes_through(c, (10.0, 10.0)))

    def test_shift_third_click_is_the_curvature(self):
        t = self.tool('arc')
        self.click(t, (0.0, 0.0))
        self.click(t, (20.0, 0.0))
        self.click(t, (10.0, 10.0), SHIFT)
        c = self.contour()
        self.assertAlmostEqual(c.end[0], 20.0)
        self.assertAlmostEqual(c.end[1], 0.0)
        self.assertTrue(self.passes_through(c, (10.0, 10.0)))

    def preview_of(self, t, hover, ev):
        seen = []
        t.move(QPointF(0, 0), hover, ev)
        with mock.patch.object(t, 'preview', lambda p, path, color=None: seen.append(path)):
            t.paint(None)
        return seen[-1].contours[0]

    def test_the_preview_is_what_gets_drawn(self):
        for ev in (PLAIN, SHIFT):
            t = self.tool('arc')
            self.click(t, (0.0, 0.0))
            self.click(t, (15.0, 12.0))
            shown = self.preview_of(t, (30.0, 2.0), ev)
            self.click(t, (30.0, 2.0), ev)
            made = self.contour()
            self.assertAlmostEqual(shown.start[0], made.start[0])
            self.assertAlmostEqual(shown.start[1], made.start[1])
            self.assertAlmostEqual(shown.end[0], made.end[0])
            self.assertAlmostEqual(shown.end[1], made.end[1])
            self.assertEqual(shown.digest(), made.digest())

    def test_aligned_points_draw_nothing(self):
        t = self.tool('arc')
        for p in ((0.0, 0.0), (10.0, 0.0), (20.0, 0.0)):
            self.click(t, p)
        self.assertEqual(self.shapes(), [])
        self.assertEqual(t.pts, [])


class Points(Base):
    def test_arc_window_shows_three_points_without_finish(self):
        t = self.tool('arc')
        self.click(t, (1.0, 2.0))
        d = self.win.tool_points_dialog(t, exec_dialog=False)
        self.assertEqual(len(d.points()), 3)
        self.assertEqual(d.points()[0], (1.0, 2.0))
        self.assertTrue(d.b_finish.isHidden())

    def test_three_points_draw_the_arc(self):
        t = self.tool('arc')
        self.win.apply_tool_points(t, [(0.0, 0.0), (10.0, 10.0), (20.0, 0.0)])
        self.assertTrue(self.passes_through(self.contour(), (10.0, 10.0)))

    def test_fewer_points_continue_with_the_mouse(self):
        t = self.tool('arc')
        self.win.apply_tool_points(t, [(0.0, 0.0), (10.0, 10.0)])
        self.assertEqual(self.shapes(), [])
        self.assertEqual(t.pts, [(0.0, 0.0), (10.0, 10.0)])
        self.click(t, (20.0, 0.0))
        self.assertEqual(len(self.shapes()), 1)

    def test_extra_points_are_ignored(self):
        t = self.tool('arc')
        self.win.apply_tool_points(t, [(0.0, 0.0), (10.0, 10.0), (20.0, 0.0), (5.0, 5.0)])
        self.assertEqual(len(self.shapes()), 1)
        self.assertEqual(t.pts, [])

    def test_circle_by_three_points(self):
        t = self.tool('circle3')
        self.win.apply_tool_points(t, [(0.0, 0.0), (10.0, 10.0), (20.0, 0.0)])
        c = self.contour()
        self.assertTrue(c.closed)
        b = c.bbox()
        self.assertAlmostEqual(b[2] - b[0], 20.0, places=3)

    def test_circle_by_two_points(self):
        t = self.tool('circle2')
        d = self.win.tool_points_dialog(t, exec_dialog=False)
        self.assertEqual(len(d.points()), 2)
        self.win.apply_tool_points(t, [(0.0, 0.0), (20.0, 0.0)])
        b = self.contour().bbox()
        self.assertAlmostEqual(b[2] - b[0], 20.0, places=3)

    def test_polyline_window_unchanged(self):
        t = self.tool('polyline')
        self.click(t, (1.0, 2.0))
        d = self.win.tool_points_dialog(t, exec_dialog=False)
        self.assertEqual(len(d.points()), 1)
        self.assertFalse(d.b_finish.isHidden())

    def test_f2_goes_to_the_window(self):
        t = self.tool('arc')
        with mock.patch.object(PointsDialog, 'exec', return_value=False) as ask:
            self.win.f2()
        ask.assert_called_once()
        self.assertIs(self.c.tool_obj, t)


class ArcNumbers(Base):
    def fake(self, **values):
        test = self

        class Fake:
            def __init__(self, parent, title, params, labels, warning='', choices=None):
                self.params = params
                test.defaults = dict(vars(params)) if vars(params) else None
                test.start_default = params.start
                test.r_default = params.r
                test.x_default = params.x

            def exec(self):
                return True

            def result_params(self):
                for k, v in values.items():
                    setattr(self.params, k, v)
                return self.params
        return mock.patch('vectordrive.ui.dialogs.ParamsDialog', Fake)

    def test_counter_clockwise(self):
        self.tool('arc_center')
        with self.fake(x=10.0, y=20.0, r=5.0, start=0.0, end=90.0, clockwise=False):
            self.win.f2()
        c = self.contour()
        self.assertAlmostEqual(c.start[0], 15.0)
        self.assertAlmostEqual(c.start[1], 20.0)
        self.assertAlmostEqual(c.end[0], 10.0)
        self.assertAlmostEqual(c.end[1], 25.0)
        self.assertTrue(self.passes_through(c, (10.0 + 5.0 * math.cos(math.pi / 4), 20.0 + 5.0 * math.sin(math.pi / 4))))

    def test_clockwise_goes_the_other_way(self):
        self.tool('arc_center')
        with self.fake(x=0.0, y=0.0, r=5.0, start=0.0, end=90.0, clockwise=True):
            self.win.f2()
        c = self.contour()
        self.assertAlmostEqual(c.end[0], 0.0)
        self.assertAlmostEqual(c.end[1], 5.0)
        self.assertTrue(self.passes_through(c, (0.0, -5.0)))

    def test_same_angles_make_a_full_turn(self):
        self.tool('arc_center')
        with self.fake(x=0.0, y=0.0, r=5.0, start=30.0, end=30.0, clockwise=False):
            self.win.f2()
        self.assertTrue(self.passes_through(self.contour(), (-5.0 * math.cos(math.radians(30)), -5.0 * math.sin(math.radians(30)))))

    def test_clicks_already_made_fill_the_window(self):
        t = self.tool('arc_center')
        self.click(t, (10.0, 10.0))
        self.click(t, (10.0, 14.0))
        with self.fake():
            self.win.f2()
        self.assertEqual(self.x_default, 10.0)
        self.assertAlmostEqual(self.r_default, 4.0)
        self.assertAlmostEqual(self.start_default, 90.0)

    def test_values_are_kept(self):
        self.tool('arc_center')
        with self.fake(x=0.0, y=0.0, r=7.0, start=10.0, end=50.0, clockwise=True):
            self.win.f2()
        self.tool('arc_center')
        with self.fake(x=0.0, y=0.0):
            self.win.f2()
        self.assertEqual(self.r_default, 7.0)
        self.assertEqual(self.start_default, 10.0)

    def test_null_radius_draws_nothing(self):
        self.tool('arc_center')
        with self.fake(x=0.0, y=0.0, r=0.0, start=0.0, end=90.0, clockwise=False):
            self.win.f2()
        self.assertEqual(self.shapes(), [])


class Bezier(Base):
    def key(self, k):
        return QKeyEvent(QEvent.Type.KeyPress, k, Qt.KeyboardModifier.NoModifier)

    def test_backspace_goes_back_one_point(self):
        t = self.tool('bezier')
        for p in ((0.0, 0.0), (10.0, 0.0), (20.0, 5.0)):
            t.press(QPointF(0, 0), p, PLAIN)
            t.release(QPointF(0, 0), p, PLAIN)
        self.assertTrue(t.key(self.key(Qt.Key.Key_Backspace)))
        self.assertEqual(t.points(), [(0.0, 0.0), (10.0, 0.0)])
        self.assertTrue(t.key(self.key(Qt.Key.Key_Backspace)))
        self.assertTrue(t.key(self.key(Qt.Key.Key_Backspace)))
        self.assertEqual(t.points(), [])
        self.assertFalse(t.key(self.key(Qt.Key.Key_Backspace)))


if __name__ == '__main__':
    unittest.main()
