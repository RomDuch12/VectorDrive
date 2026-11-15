"""Round 838 : Couper un contour comme TypeEdit : ouvert par défaut, Tab referme ; coupe exacte, courbes conservées."""
import math
import os
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core import knife as KN
from vectordrive.core.document import Group, Layer, Plate, Shape
from vectordrive.core.geom import Conic, Contour, Cubic, Line, Path
from vectordrive.core.pathops import _to_shapely
from vectordrive.ui.main_window import MainWindow

app = QApplication.instance() or QApplication([])


class Ev:
    def __init__(self, mods=Qt.KeyboardModifier.NoModifier):
        self.mods = mods

    def modifiers(self):
        return self.mods


PLAIN = Ev()
SHIFT = Ev(Qt.KeyboardModifier.ShiftModifier)


def line(a, b):
    return Path([geom.polyline([a, b])])


def kinds(path):
    return {type(s).__name__ for c in path.contours for s in c.segments}


def area(path):
    return _to_shapely(path).area


class OpenAlong(unittest.TestCase):
    def test_a_closed_contour_opens_at_each_crossing(self):
        p, n = KN.open_along(Path([geom.rect(0.0, 0.0, 10.0, 10.0)]), line((5.0, -2.0), (5.0, 12.0)))
        self.assertEqual(n, 2)
        self.assertTrue(all(not c.closed for c in p.contours))
        ends = sorted(tuple(round(v, 6) for v in c.start) for c in p.contours)
        self.assertEqual(ends, [(5.0, 0.0), (5.0, 10.0)])
        self.assertAlmostEqual(sum(geom.Path([c]).length() for c in p.contours), 40.0)

    def test_nothing_moves_the_pieces_touch(self):
        p, _n = KN.open_along(Path([geom.rect(0.0, 0.0, 10.0, 10.0)]), line((5.0, -2.0), (5.0, 12.0)))
        a, b = p.contours
        self.assertEqual(a.end, b.start)
        self.assertEqual(b.end, a.start)

    def test_an_open_contour_is_cut(self):
        p, n = KN.open_along(Path([geom.polyline([(0.0, 0.0), (30.0, 0.0)])]), line((10.0, -1.0), (10.0, 1.0)))
        self.assertEqual(n, 2)
        self.assertEqual([c.end for c in p.contours], [(10.0, 0.0), (30.0, 0.0)])

    def test_one_crossing_opens_a_closed_contour_once(self):
        p, n = KN.open_along(Path([geom.rect(0.0, 0.0, 10.0, 10.0)]), line((5.0, 5.0), (5.0, 12.0)))
        self.assertEqual(n, 1)
        self.assertFalse(p.contours[0].closed)
        self.assertEqual(p.contours[0].start, p.contours[0].end)

    def test_a_curve_stays_a_curve(self):
        p, _n = KN.open_along(Path([geom.circle((0.0, 0.0), 10.0)]), line((0.0, -20.0), (0.0, 20.0)))
        self.assertNotIn('Line', kinds(p))
        self.assertEqual(len(p.contours), 2)
        for c in p.contours:
            for q in c.flatten(0.01):
                self.assertAlmostEqual(math.hypot(*q), 10.0, delta=0.02)

    def test_no_crossing(self):
        self.assertEqual(KN.open_along(Path([geom.rect(0.0, 0.0, 10.0, 10.0)]), line((20.0, 0.0), (20.0, 10.0))), (None, 0))

    def test_untouched_contours_stay_as_they_are(self):
        far = geom.rect(50.0, 0.0, 10.0, 10.0)
        p, _n = KN.open_along(Path([geom.rect(0.0, 0.0, 10.0, 10.0), far]), line((5.0, -2.0), (5.0, 12.0)))
        self.assertIn(far, p.contours)

    def test_points_along(self):
        got = KN.points_along(Path([geom.rect(0.0, 0.0, 10.0, 10.0)]), line((5.0, -2.0), (5.0, 12.0)))
        self.assertEqual(sorted(got), [(5.0, 0.0), (5.0, 10.0)])


class Closing(unittest.TestCase):
    def check(self, path, blade, n):
        parts = KN.cut(path, blade)
        self.assertEqual(len(parts), n)
        self.assertAlmostEqual(sum(area(p) for p in parts), area(path), delta=0.05)
        return parts

    def test_a_circle_cut_in_two_keeps_its_arcs(self):
        parts = self.check(Path([geom.circle((0.0, 0.0), 10.0)]), line((0.0, -20.0), (0.0, 20.0)), 2)
        for p in parts:
            self.assertEqual(len(p.contours), 1)
            self.assertTrue(p.contours[0].closed)
            segs = p.contours[0].segments
            self.assertLess(len(segs), 12)                                  # pas des centaines de petits segments
            self.assertEqual(sum(isinstance(s, Line) for s in segs), 1)     # le trait de coupe
            self.assertAlmostEqual(area(p), math.pi * 50.0, delta=0.05)

    def test_cubic_is_kept(self):
        c = Contour([Cubic((0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0)), Line((10.0, 0.0), (0.0, 0.0))], True)
        parts = self.check(Path([c]), line((5.0, -1.0), (5.0, 20.0)), 2)
        self.assertTrue(all('Cubic' in kinds(p) for p in parts))

    def test_ends_touch_exactly(self):
        for p in KN.cut(Path([geom.circle((0.0, 0.0), 10.0)]), line((-3.0, -20.0), (4.0, 20.0))):
            c = p.contours[0]
            for s0, s1 in zip(c.segments, list(c.segments[1:]) + [c.segments[0]]):
                self.assertLess(geom.dist(s0.end, s1.start), 1e-9)

    def test_a_ring_cut_across_gives_two_c_shapes(self):
        ring = Path([geom.circle((0.0, 0.0), 10.0), geom.circle((0.0, 0.0), 5.0)])
        parts = self.check(ring, line((0.0, -20.0), (0.0, 20.0)), 2)
        for p in parts:
            self.assertEqual(len(p.contours), 1)
            self.assertAlmostEqual(area(p), math.pi * 75.0 / 2, delta=0.05)
            self.assertLess(len(p.contours[0].segments), 16)

    def test_a_hole_that_is_not_crossed_stays_in_its_piece(self):
        p = Path([geom.rect(0.0, 0.0, 30.0, 10.0), geom.rect(20.0, 3.0, 4.0, 4.0)])
        parts = self.check(p, line((10.0, -1.0), (10.0, 11.0)), 2)
        with_hole = [x for x in parts if len(x.contours) == 2]
        self.assertEqual(len(with_hole), 1)
        self.assertAlmostEqual(area(with_hole[0]), 200.0 - 16.0, delta=0.01)
        self.assertGreater(with_hole[0].bbox()[0], 9.0)

    def test_a_u_shape_gives_the_right_chords(self):
        p = Path([geom.polyline([(0.0, 0.0), (30.0, 0.0), (30.0, 10.0), (20.0, 10.0), (20.0, 3.0), (10.0, 3.0),
                                 (10.0, 10.0), (0.0, 10.0)], closed=True)])
        parts = self.check(p, line((-1.0, 5.0), (31.0, 5.0)), 3)
        self.assertEqual(sorted(round(area(x)) for x in parts), [50, 50, 130])

    def test_a_curved_blade_stays_curved(self):
        blade = Path([Contour([Cubic((5.0, -2.0), (0.0, 3.0), (10.0, 7.0), (5.0, 12.0))], False)])
        parts = self.check(Path([geom.rect(0.0, 0.0, 10.0, 10.0)]), blade, 2)
        self.assertTrue(all('Cubic' in kinds(p) for p in parts))

    def test_a_closed_blade_across_the_edge(self):
        blade = Path([geom.circle((10.0, 5.0), 3.0)])
        parts = self.check(Path([geom.rect(0.0, 0.0, 10.0, 10.0)]), blade, 2)
        self.assertTrue(all('Line' in kinds(p) for p in parts))
        self.assertTrue(any(kinds(p) & {'Conic', 'Cubic'} for p in parts))
        self.assertAlmostEqual(min(area(p) for p in parts), math.pi * 9.0 / 2, delta=0.05)

    def test_a_polyline_blade(self):
        parts = self.check(Path([geom.rect(0.0, 0.0, 30.0, 10.0)]), Path([geom.polyline([(-1.0, 5.0), (10.0, 5.0), (10.0, 11.0)])]), 2)
        self.assertEqual(sorted(round(area(p)) for p in parts), [50, 250])

    def test_the_line_that_stops_inside_cuts_nothing(self):
        p = Path([geom.rect(0.0, 0.0, 10.0, 10.0)])
        self.assertEqual(KN.cut(p, line((5.0, 5.0), (5.0, 20.0))), [p])

    def test_open_contours_of_the_object_are_not_lost(self):
        trait = geom.polyline([(0.0, 20.0), (10.0, 20.0)])
        parts = KN.cut(Path([geom.rect(0.0, 0.0, 10.0, 10.0), trait]), line((5.0, -1.0), (5.0, 11.0)))
        self.assertEqual(sum(1 for p in parts for c in p.contours if not c.closed), 1)

    def test_crossing_contours_fall_back_on_the_flat_result(self):
        p = Path([geom.rect(0.0, 0.0, 10.0, 10.0), geom.rect(5.0, 5.0, 10.0, 10.0)])
        parts = KN.cut(p, line((7.0, -1.0), (7.0, 20.0)))
        self.assertGreater(len(parts), 1)
        self.assertAlmostEqual(sum(area(x) for x in parts), area(p), delta=0.01)

    def test_several_blade_contours_still_work(self):
        p = Path([geom.rect(0.0, 0.0, 30.0, 10.0)])
        blade = Path([geom.polyline([(10.0, -1.0), (10.0, 11.0)]), geom.polyline([(20.0, -1.0), (20.0, 11.0)])])
        self.assertEqual(len(KN.cut(p, blade)), 3)

    def test_order_is_top_to_bottom_then_left_to_right(self):
        parts = KN.cut(Path([geom.rect(0.0, 0.0, 10.0, 10.0)]), line((-1.0, 5.0), (11.0, 5.0)))
        self.assertGreater(parts[0].bbox()[1], parts[1].bbox()[1] - 1e-9)
        parts = KN.cut(Path([geom.rect(0.0, 0.0, 10.0, 10.0)]), line((5.0, -1.0), (5.0, 11.0)))
        self.assertLess(parts[0].bbox()[0], parts[1].bbox()[0])

    def test_two_separate_shapes_in_one_object(self):
        p = Path([geom.rect(0.0, 0.0, 10.0, 10.0), geom.rect(20.0, 0.0, 10.0, 10.0)])
        parts = self.check(p, line((5.0, -1.0), (5.0, 11.0)), 3)
        self.assertEqual(sorted(round(area(x)) for x in parts), [50, 50, 100])


class Tool(unittest.TestCase):
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
        self.c.select([])
        self.win.A['tool_knife_line'].trigger()
        self.t = self.c.tool_obj

    def tearDown(self):
        self.win.set_tool('select')

    def add(self, *contours):
        s = Shape(path=Path(list(contours)))
        self.layer.items.append(s)
        return s

    def cut(self, a, b, ev=PLAIN):
        self.t.press(None, a, ev)
        self.t.move(None, b, ev)
        self.t.release(None, b, ev)

    def test_plain_cut_opens_and_keeps_one_object(self):
        s = self.add(geom.rect(0.0, 0.0, 10.0, 10.0))
        self.cut((5.0, -2.0), (5.0, 12.0))
        self.assertEqual(self.layer.items, [s])
        self.assertEqual(len(s.path.contours), 2)
        self.assertTrue(all(not c.closed for c in s.path.contours))

    def test_tab_closes_for_this_stroke_only(self):
        self.add(geom.rect(0.0, 0.0, 10.0, 10.0))
        self.assertTrue(self.t.wants_key(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier)))
        self.t.key(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier))
        self.cut((5.0, -2.0), (5.0, 12.0))
        self.assertEqual(len(self.layer.items), 2)
        self.assertTrue(all(c.closed for s in self.layer.items for c in s.path.contours))
        self.assertFalse(self.t.closing)

    def test_shift_closes(self):
        self.add(geom.rect(0.0, 0.0, 10.0, 10.0))
        self.cut((5.0, -2.0), (5.0, 12.0), SHIFT)
        self.assertEqual(len(self.layer.items), 2)

    def test_an_open_contour_is_accepted(self):
        s = self.add(geom.polyline([(0.0, 0.0), (30.0, 0.0)]))
        self.cut((10.0, -1.0), (10.0, 1.0))
        self.assertEqual(len(s.path.contours), 2)

    def test_closing_leaves_open_contours_alone(self):
        s = self.add(geom.polyline([(0.0, 0.0), (30.0, 0.0)]))
        self.cut((10.0, -1.0), (10.0, 1.0), SHIFT)
        self.assertEqual(len(s.path.contours), 1)

    def test_undo_is_one_step(self):
        s = self.add(geom.rect(0.0, 0.0, 10.0, 10.0))
        n = len(self.win._undo)
        self.cut((5.0, -2.0), (5.0, 12.0))
        self.assertEqual(len(self.win._undo), n + 1)
        self.win.undo()
        self.assertEqual(len(self.doc.layers[0].items[0].path.contours), 1)
        del s

    def test_selection_limits_the_cut(self):
        a = self.add(geom.rect(0.0, 0.0, 10.0, 10.0))
        b = self.add(geom.rect(2.0, 2.0, 6.0, 6.0))
        self.c.select([b])
        self.cut((5.0, -2.0), (5.0, 12.0))
        self.assertEqual(len(a.path.contours), 1)
        self.assertEqual(len(b.path.contours), 2)

    def test_marks_during_the_gesture(self):
        self.add(geom.rect(0.0, 0.0, 10.0, 10.0))
        self.t.press(None, (5.0, -2.0), PLAIN)
        self.t.move(None, (5.0, 12.0), PLAIN)
        self.assertEqual(sorted(self.t.marks), [(5.0, 0.0), (5.0, 10.0)])
        painter = mock.MagicMock()
        with mock.patch.object(self.t, 'preview'):
            self.t.paint(painter)
        self.assertEqual(painter.drawRect.call_count, 4)
        self.t.cancel()
        self.assertEqual(self.t.marks, [])

    def test_marks_give_up_on_a_big_drawing(self):
        self.add(*[geom.rect(0.0, float(i), 10.0, 0.5) for i in range(201)])
        self.assertEqual(self.win.knife_marks((5.0, -2.0), (5.0, 300.0)), [])

    def test_nothing_crossed(self):
        s = self.add(geom.rect(0.0, 0.0, 10.0, 10.0))
        n = len(self.win._undo)
        self.cut((50.0, 0.0), (50.0, 10.0))
        self.assertEqual(len(s.path.contours), 1)
        self.assertEqual(len(self.win._undo), n)

    def test_inside_a_group_when_nothing_is_selected(self):
        s = Shape(path=Path([geom.rect(0.0, 0.0, 10.0, 10.0)]))
        g = Group(children=[s])
        self.layer.items.append(g)
        self.cut((5.0, -2.0), (5.0, 12.0))
        self.assertEqual(len(s.path.contours), 2)

    def test_closing_inside_a_group_really_cuts(self):
        s = Shape(path=Path([geom.rect(0.0, 0.0, 10.0, 10.0)]))
        g = Group(children=[s])
        self.layer.items.append(g)
        self.c.select([g])
        self.cut((5.0, -2.0), (5.0, 12.0), SHIFT)
        self.assertEqual(self.layer.items, [g])
        self.assertEqual(len(g.children), 2)
        self.assertEqual(self.c.selection, [g])

    def test_the_knife_command_also_reaches_groups_children(self):
        s = self.add(geom.circle((0.0, 0.0), 10.0))
        blade = self.add(geom.polyline([(0.0, -20.0), (0.0, 20.0)]))
        self.c.select([s, blade])
        self.assertEqual(self.win.knife(), 2)
        self.assertEqual(len(self.layer.items), 3)
        self.assertTrue(all(len(x.path.contours[0].segments) < 12 for x in self.layer.items))

    def test_the_action_has_the_typeedit_name(self):
        self.assertEqual(self.win.A['tool_knife_line'].text(), 'Couper un contour')


if __name__ == '__main__':
    unittest.main()
