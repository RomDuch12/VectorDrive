"""Round 793 : polycourbe, liens de la disposition TypeEdit."""
import math
import os
import tempfile
import unittest
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QEvent, QPointF, Qt

from vectordrive.core import geom
from vectordrive.core.document import Shape
from vectordrive.core.geom import Conic, Line


def close(a, b, places=7):
    return all(abs(x - y) < 10 ** -places for x, y in zip(a, b))


class TestTangentArc(unittest.TestCase):
    def test_quarter_to_the_left(self):
        segs, out = geom.tangent_arc((0, 0), (1, 0), (10, 10))
        self.assertTrue(close(out, (0, 1)))
        self.assertTrue(all(isinstance(s, Conic) for s in segs))
        for s in segs:
            x, y = s.point(0.5)
            self.assertAlmostEqual(math.hypot(x, y - 10), 10.0, places=6)      # centre (0, 10)

    def test_quarter_to_the_right(self):
        segs, out = geom.tangent_arc((0, 0), (1, 0), (10, -10))
        self.assertTrue(close(out, (0, -1)))
        x, y = segs[0].point(0.5)
        self.assertAlmostEqual(math.hypot(x, y + 10), 10.0, places=6)

    def test_leaves_along_the_direction(self):
        for direction in ((1, 0), (0, 1), (math.sqrt(.5), math.sqrt(.5))):
            segs, _out = geom.tangent_arc((3, 4), direction, (20, 9))
            c = segs[0]
            vx, vy = c.p1[0] - c.p0[0], c.p1[1] - c.p0[1]
            n = math.hypot(vx, vy)
            self.assertAlmostEqual(vx / n * direction[1] - vy / n * direction[0], 0.0, places=7)
            self.assertGreater(vx * direction[0] + vy * direction[1], 0)

    def test_ends_are_exact(self):
        segs, _out = geom.tangent_arc((1.5, 2.5), (1, 0), (7.25, -3.125))
        self.assertEqual(segs[0].start, (1.5, 2.5))
        self.assertEqual(segs[-1].end, (7.25, -3.125))

    def test_segments_are_chained(self):
        segs, _out = geom.tangent_arc((0, 0), (1, 0), (-5, 1))
        for a, b in zip(segs, segs[1:]):
            self.assertTrue(close(a.end, b.start, 9))

    def test_more_than_half_a_turn_goes_the_long_way(self):
        segs, _out = geom.tangent_arc((0, 0), (1, 0), (-5, 1))
        self.assertGreaterEqual(len(segs), 3)
        pts = [s.point(0.5) for s in segs]
        self.assertTrue(any(p[0] > 0 for p in pts))      # il part vers l'avant avant de revenir

    def test_leaving_direction_is_tangent_at_the_end(self):
        segs, out = geom.tangent_arc((0, 0), (1, 0), (6, 8))
        c = segs[-1]
        vx, vy = c.p2[0] - c.p1[0], c.p2[1] - c.p1[1]
        n = math.hypot(vx, vy)
        self.assertTrue(close((vx / n, vy / n), out, 7))

    def test_straight_ahead_is_a_segment(self):
        segs, out = geom.tangent_arc((0, 0), (1, 0), (10, 0))
        self.assertIsInstance(segs[0], Line)
        self.assertEqual(out, (1, 0))

    def test_straight_behind_is_impossible(self):
        self.assertIsNone(geom.tangent_arc((0, 0), (1, 0), (-10, 0)))

    def test_same_point_is_impossible(self):
        self.assertIsNone(geom.tangent_arc((3, 3), (1, 0), (3, 3)))


def key_event(key):
    from PySide6.QtGui import QKeyEvent
    return QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)


CTRL = SimpleNamespace(modifiers=lambda: Qt.KeyboardModifier.ControlModifier)
PLAIN = SimpleNamespace(modifiers=lambda: Qt.KeyboardModifier.NoModifier)


class TestTool(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.layer = self.w.canvas.doc.layers[0]
        self.layer.items[:] = []
        self.w.canvas.scale = 10.0                       # le premier point n'attire qu'à moins d'un mm
        self.w.set_tool('polycurve')
        self.t = self.w.canvas.tool_obj

    def tearDown(self):
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()

    def click(self, *pts, ev=PLAIN):
        for p in pts:
            self.t.press(QPointF(), p, ev)

    def press_key(self, key):
        return self.t.key(key_event(key))

    def mode(self, name):
        while self.t.mode != name:
            self.press_key(Qt.Key.Key_Tab)

    def contour(self):
        shapes = [it for it in self.layer.items if isinstance(it, Shape)]
        self.assertEqual(len(shapes), 1)
        return shapes[0].path.contours[0]

    def test_is_the_right_tool(self):
        from vectordrive.ui.tools import PolyCurveTool
        self.assertIsInstance(self.t, PolyCurveTool)
        self.assertTrue(self.w.A['tool_polycurve'].isCheckable())

    def test_free_segments(self):
        self.click((0, 0), (10, 0), (10, 10))
        self.press_key(Qt.Key.Key_Return)
        c = self.contour()
        self.assertFalse(c.closed)
        self.assertEqual([type(s) for s in c.segments], [Line, Line])
        self.assertEqual(c.segments[-1].end, (10, 10))

    def test_tab_goes_round(self):
        seen = []
        for _ in range(3):
            self.press_key(Qt.Key.Key_Tab)
            seen.append(self.t.mode)
        self.assertEqual(seen, ['arc', 'tangent', 'line'])
        self.press_key(Qt.Key.Key_Backtab)
        self.assertEqual(self.t.mode, 'tangent')

    def test_tab_says_the_option(self):
        self.press_key(Qt.Key.Key_Tab)
        self.assertIn('arcs tangents', self.w.statusBar().currentMessage())

    def test_tab_reaches_the_tool_through_the_canvas(self):
        self.app.sendEvent(self.w.canvas, key_event(Qt.Key.Key_Tab))
        self.assertEqual(self.t.mode, 'arc')

    def test_enter_reaches_the_tool_through_the_canvas(self):
        self.click((0, 0), (10, 0))
        self.app.sendEvent(self.w.canvas, key_event(Qt.Key.Key_Return))
        self.assertEqual(len(self.contour().segments), 1)

    def test_arc_follows_the_segment(self):
        self.click((0, 0), (10, 0))
        self.mode('arc')
        self.click((20, 10))
        self.press_key(Qt.Key.Key_Return)
        c = self.contour()
        self.assertIsInstance(c.segments[1], Conic)
        s = c.segments[1]
        self.assertAlmostEqual(s.p1[1] - s.p0[1], 0.0, places=7)         # part à l'horizontale
        self.assertEqual(c.segments[-1].end, (20, 10))

    def test_first_arc_without_direction_is_a_segment(self):
        self.mode('arc')
        self.click((0, 0), (10, 0))
        self.press_key(Qt.Key.Key_Return)
        self.assertIsInstance(self.contour().segments[0], Line)

    def test_arcs_follow_each_other(self):
        self.click((0, 0), (10, 0))
        self.mode('arc')
        self.click((20, 10), (10, 20))
        self.press_key(Qt.Key.Key_Return)
        segs = self.contour().segments
        a, b = segs[-1], next(s for s in segs if isinstance(s, Conic) and s.start == (20, 10))
        before = next(s for s in segs if s.end == (20, 10))
        v0 = (before.p2[0] - before.p1[0], before.p2[1] - before.p1[1])
        v1 = (b.p1[0] - b.p0[0], b.p1[1] - b.p0[1])
        self.assertAlmostEqual(v0[0] * v1[1] - v0[1] * v1[0], 0.0, places=6)
        self.assertEqual(a.end, (10, 20))

    def test_tangent_segment_stays_on_the_tangent(self):
        self.click((0, 0), (10, 0))
        self.mode('tangent')
        self.click((25, 7))
        self.press_key(Qt.Key.Key_Return)
        self.assertTrue(close(self.contour().segments[-1].end, (25, 0)))

    def test_tangent_after_an_arc(self):
        self.click((0, 0), (10, 0))
        self.mode('arc')
        self.click((20, 10))
        self.mode('tangent')
        self.click((20, 30))
        self.press_key(Qt.Key.Key_Return)
        self.assertTrue(close(self.contour().segments[-1].end, (20, 30)))

    def test_tangent_backwards_adds_nothing(self):
        self.click((0, 0), (10, 0))
        self.mode('tangent')
        self.click((-5, 0))
        self.assertEqual(len(self.t.parts), 1)

    def test_impossible_arc_adds_nothing(self):
        self.click((0, 0), (10, 0))
        self.mode('arc')
        self.click((-5, 0))
        self.assertEqual(len(self.t.parts), 1)

    def test_same_point_adds_nothing(self):
        self.click((0, 0), (0, 0))
        self.assertEqual(self.t.parts, [])

    def test_closed_on_the_first_point(self):
        self.click((0, 0), (10, 0), (10, 10), (0, 0))
        c = self.contour()
        self.assertTrue(c.closed)
        self.assertEqual(c.segments[-1].end, (0, 0))
        self.assertEqual(len(c.segments), 3)

    def test_closed_by_an_arc(self):
        self.click((0, 0), (10, 0), (10, 10))
        self.mode('arc')
        self.click((0, 0))
        c = self.contour()
        self.assertTrue(c.closed)
        self.assertIsInstance(c.segments[-1], Conic)
        self.assertEqual(c.segments[-1].end, (0, 0))

    def test_no_arc_back_straight_behind(self):
        self.click((0, 0), (10, 0))
        self.mode('arc')
        self.click((0, 0))
        self.assertEqual(self.layer.items, [])
        self.assertEqual(len(self.t.parts), 1)

    def test_closing_in_tangent_mode_joins_the_first_point(self):
        self.click((0, 0), (10, 0), (10, 10))
        self.mode('tangent')
        self.click((0, 0))
        c = self.contour()
        self.assertTrue(c.closed)
        self.assertEqual(c.segments[-1].end, (0, 0))

    def test_two_points_cannot_close_on_a_segment(self):
        self.click((0, 0), (10, 0), (0, 0))
        self.assertEqual(self.layer.items, [])
        self.assertEqual(len(self.t.parts), 2)

    def test_backspace(self):
        self.click((0, 0), (10, 0), (10, 10))
        self.press_key(Qt.Key.Key_Backspace)
        self.assertEqual(len(self.t.parts), 1)
        self.press_key(Qt.Key.Key_Backspace)
        self.assertEqual(self.t.parts, [])
        self.assertEqual(self.t.first, (0, 0))
        self.press_key(Qt.Key.Key_Backspace)
        self.assertIsNone(self.t.first)
        self.assertFalse(self.press_key(Qt.Key.Key_Backspace))

    def test_backspace_after_an_arc_restores_the_direction(self):
        self.click((0, 0), (10, 0), (10, 10))
        self.mode('arc')
        self.click((20, 20))
        self.press_key(Qt.Key.Key_Backspace)
        self.assertEqual(self.t._direction(), (0.0, 1.0))

    def test_double_click_ends(self):
        self.click((0, 0), (10, 0))
        self.t.double(QPointF(), (10, 0), PLAIN)
        self.assertEqual(len(self.contour().segments), 1)

    def test_single_point_makes_nothing(self):
        self.click((0, 0))
        self.press_key(Qt.Key.Key_Return)
        self.assertEqual(self.layer.items, [])

    def test_ctrl_makes_45_degrees(self):
        self.click((0, 0))
        self.t.press(QPointF(), (10, 1), CTRL)
        self.press_key(Qt.Key.Key_Return)
        e = self.contour().segments[0].end
        self.assertAlmostEqual(e[1], 0.0, places=7)

    def test_cancel(self):
        self.click((0, 0), (10, 0))
        self.t.cancel()
        self.assertIsNone(self.t.first)
        self.assertEqual(self.t.parts, [])
        self.assertEqual(self.layer.items, [])

    def test_undo(self):
        self.click((0, 0), (10, 0))
        self.press_key(Qt.Key.Key_Return)
        self.assertEqual(len(self.w.canvas.doc.layers[0].items), 1)
        self.w.undo()
        self.assertEqual(self.w.canvas.doc.layers[0].items, [])

    def test_painting_does_not_fail(self):
        from PySide6.QtGui import QPainter, QPixmap
        pm = QPixmap(50, 50)
        p = QPainter(pm)
        self.t.paint(p)                                  # rien encore
        self.t.move(QPointF(), (5, 5), PLAIN)
        self.t.paint(p)
        self.click((0, 0), (10, 0))
        self.mode('arc')
        self.t.move(QPointF(), (20, 10), PLAIN)
        self.t.paint(p)
        self.t.move(QPointF(), (10, 0), PLAIN)
        self.t.paint(p)
        p.end()

    def test_moves_with_ctrl(self):
        self.click((0, 0))
        self.t.move(QPointF(), (10, 1), CTRL)
        self.assertAlmostEqual(self.t.hover[1], 0.0, places=7)


class TestLinks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_commands_go_to_their_own_tool(self):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.shortcuts import TE_ACTIONS
        w = MainWindow()
        try:
            for cmd, key in (('ID_PALETTE_POLYCURVE', 'tool_polycurve'), ('ID_PALETTE_DIGIT', 'tool_bezier'),
                             ('ID_PALETTE_DIGITDROITE', 'tool_dline'), ('ID_PALETTE_MESUREANGLE', 'tool_measure_angle'),
                             ('ID_COMPO_COPIE', 'tool_dup_free')):
                self.assertEqual(TE_ACTIONS[cmd], key)
                self.assertIn(key, w.A)
        finally:
            w.modified = False
            w.close()
            w.deleteLater()


if __name__ == '__main__':
    unittest.main()
