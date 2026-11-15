"""Round 837 : Couper-supprimer, Transformer une portion, Effacer un contour au clic, Déconnecter plusieurs points."""
import math
import os
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core import nodes as N
from vectordrive.core import portion as P
from vectordrive.core.document import Group, Layer, Plate, Shape
from vectordrive.core.geom import Contour, Cubic, Line, Path
from vectordrive.ui import shortcuts as S
from vectordrive.ui.main_window import MainWindow

app = QApplication.instance() or QApplication([])


class Ev:
    def __init__(self, mods=Qt.KeyboardModifier.NoModifier):
        self.mods = mods

    def modifiers(self):
        return self.mods


SHIFT = Ev(Qt.KeyboardModifier.ShiftModifier)
PLAIN = Ev()
SQUARE = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]        # sens trigonométrique


def key(k):
    return QKeyEvent(QEvent.Type.KeyPress, k, Qt.KeyboardModifier.NoModifier)


class Core(unittest.TestCase):
    def square(self):
        return geom.polyline(SQUARE, closed=True).close()

    def test_span_clockwise_on_a_counter_clockwise_square(self):
        c = self.square()
        self.assertGreater(c.signed_area(), 0)
        self.assertEqual(P.span(c, 0.5, 2.5), (2.5, 0.5))
        self.assertEqual(P.span(c, 0.5, 2.5, clockwise=False), (0.5, 2.5))

    def test_span_clockwise_on_a_clockwise_square(self):
        c = self.square().reversed()
        self.assertLess(c.signed_area(), 0)
        self.assertEqual(P.span(c, 0.5, 2.5), (0.5, 2.5))

    def test_span_of_an_open_contour_is_ordered(self):
        c = geom.polyline(SQUARE)
        self.assertEqual(P.span(c, 2.5, 0.5), (0.5, 2.5))

    def test_delete_opens_a_closed_contour(self):
        c = self.square()
        out = P.delete(c, 0.5, 2.5)
        self.assertEqual(len(out), 1)
        self.assertFalse(out[0].closed)
        self.assertEqual(out[0].start, P.point_at(c, 2.5))
        self.assertEqual(out[0].end, (5.0, 0.0))
        self.assertAlmostEqual(sum(math.dist(s.start, s.end) for s in out[0].segments), 20.0)

    def test_delete_across_the_closure(self):
        c = self.square()
        out = P.delete(c, 3.5, 0.5)
        self.assertAlmostEqual(sum(math.dist(s.start, s.end) for s in out[0].segments), 30.0)

    def test_delete_in_an_open_contour_gives_two(self):
        c = geom.polyline(SQUARE)
        out = P.delete(c, 0.5, 2.5)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0].end, (5.0, 0.0))
        self.assertEqual(out[1].start, (5.0, 10.0))

    def test_delete_to_the_end_gives_one(self):
        c = geom.polyline(SQUARE)
        self.assertEqual(len(P.delete(c, 1.0, 3.0)), 1)
        self.assertEqual(P.delete(c, 0.0, 3.0), [])

    def test_a_curve_is_cut_exactly(self):
        c = Contour([Cubic((0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0))], False)
        out = P.delete(c, 0.25, 0.75)
        self.assertIsInstance(out[0].segments[0], Cubic)
        q = c.segments[0].point(0.25)
        self.assertAlmostEqual(out[0].end[0], q[0])
        self.assertAlmostEqual(out[0].end[1], q[1])

    def test_replace_closes_a_closed_contour(self):
        c = self.square()
        a, b = P.point_at(c, 0.5), P.point_at(c, 2.5)
        out = P.replace(c, 0.5, 2.5, [Line(a, b)])
        self.assertTrue(out.closed)
        self.assertLess(out.closing_gap(), 1e-6)
        self.assertEqual(len(out.segments), 4)

    def test_replace_in_an_open_contour(self):
        c = geom.polyline(SQUARE)
        a, b = P.point_at(c, 0.5), P.point_at(c, 2.5)
        out = P.replace(c, 0.5, 2.5, [Line(a, b)])
        self.assertFalse(out.closed)
        self.assertEqual(out.start, (0.0, 0.0))
        self.assertEqual(out.end, (0.0, 10.0))
        self.assertEqual(len(out.segments), 3)

    def test_new_segments(self):
        a, b, h = (0.0, 0.0), (10.0, 0.0), (5.0, 5.0)
        self.assertEqual(len(P.new_segments('segment', a, b)), 1)
        self.assertEqual(P.new_segments('angle', a, b, h)[0].end, h)
        arc = Contour(P.new_segments('arc', a, b, h), False)
        self.assertLess(min(math.dist(q, h) for q in arc.flatten(0.001)), 0.01)
        curve = P.new_segments('curve', a, b, h)[0]
        self.assertAlmostEqual(curve.point(0.5)[0], 5.0)
        self.assertAlmostEqual(curve.point(0.5)[1], 5.0)

    def test_aligned_arc_is_a_line(self):
        self.assertIsInstance(P.new_segments('arc', (0.0, 0.0), (10.0, 0.0), (5.0, 0.0))[0], Line)


class BreakMany(unittest.TestCase):
    def test_closed_opens_at_each(self):
        c = geom.polyline(SQUARE, closed=True).close()
        out = N.break_many(c, [0, 2])
        self.assertEqual(len(out), 2)
        self.assertTrue(all(not x.closed for x in out))
        self.assertEqual(sum(len(x.segments) for x in out), 4)
        self.assertEqual(out[0].start, c.segments[0].end)
        self.assertEqual(out[0].end, c.segments[2].end)
        self.assertEqual(out[1].start, c.segments[2].end)

    def test_open_at_each(self):
        c = geom.polyline(SQUARE + [(-5.0, 10.0)])
        out = N.break_many(c, [1, 3])
        self.assertEqual([len(x.segments) for x in out], [1, 2, 1])

    def test_one_is_like_break_at(self):
        c = geom.polyline(SQUARE, closed=True).close()
        self.assertEqual(N.break_many(c, [2])[0].digest(), N.break_at(c, 2)[0].digest())

    def test_end_points_of_an_open_contour_change_nothing(self):
        c = geom.polyline(SQUARE)
        self.assertEqual(len(N.break_many(c, [0, 3])), 1)


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
        self.win.set_tool('select')

    def tool(self, name):
        self.win.A[f'tool_{name}'].trigger()
        return self.c.tool_obj

    def add(self, *contours):
        s = Shape(path=Path(list(contours)))
        self.layer.items.append(s)
        return s

    def click(self, tool, p, ev=PLAIN):
        tool.press(self.c.to_screen(*p), p, ev)


class Erase(Base):
    def test_one_contour_goes_the_other_stays(self):
        s = self.add(geom.rect(0.0, 0.0, 10.0, 10.0), geom.rect(20.0, 0.0, 10.0, 10.0))
        t = self.tool('contour_erase')
        self.click(t, (20.0, 5.0))
        self.assertEqual(len(s.path.contours), 1)
        self.assertEqual(s.path.bbox()[0], 0.0)

    def test_last_contour_takes_the_object(self):
        s = self.add(geom.rect(0.0, 0.0, 10.0, 10.0))
        self.c.select([s])
        t = self.tool('contour_erase')
        self.click(t, (0.0, 5.0))
        self.assertEqual(self.layer.items, [])
        self.assertEqual(self.c.selection, [])

    def test_undo(self):
        s = self.add(geom.rect(0.0, 0.0, 10.0, 10.0), geom.rect(20.0, 0.0, 10.0, 10.0))
        t = self.tool('contour_erase')
        self.click(t, (20.0, 5.0))
        self.win.undo()
        self.assertEqual(len(self.doc.layers[0].items[0].path.contours), 2)

    def test_shift_keeps_the_original(self):
        self.add(geom.rect(0.0, 0.0, 10.0, 10.0), geom.rect(20.0, 0.0, 10.0, 10.0))
        t = self.tool('contour_erase')
        self.click(t, (20.0, 5.0), SHIFT)
        self.assertEqual(sorted(len(i.path.contours) for i in self.layer.items), [1, 2])

    def test_missed_click_changes_nothing(self):
        s = self.add(geom.rect(0.0, 0.0, 10.0, 10.0))
        n = len(self.win._undo)
        t = self.tool('contour_erase')
        self.click(t, (50.0, 50.0))
        self.assertEqual(len(s.path.contours), 1)
        self.assertEqual(len(self.win._undo), n)

    def test_inside_a_group(self):
        s = Shape(path=Path([geom.rect(0.0, 0.0, 10.0, 10.0)]))
        k = Shape(path=Path([geom.rect(20.0, 0.0, 10.0, 10.0)]))
        g = Group(children=[s, k])
        self.layer.items.append(g)
        t = self.tool('contour_erase')
        self.click(t, (0.0, 5.0))
        self.assertEqual(g.children, [k])


class CutPortion(Base):
    def test_clockwise_by_default(self):
        s = self.add(geom.polyline(SQUARE, closed=True))
        t = self.tool('cut_portion')
        self.click(t, (5.0, 0.0))
        self.click(t, (5.0, 10.0))
        c = s.path.contours[0]
        self.assertFalse(c.closed)
        self.assertEqual(c.start, (5.0, 0.0))                 # reste : par la droite, sens du contour
        self.assertEqual(c.end, (5.0, 10.0))
        self.assertGreater(c.bbox()[2], 9.0)
        self.assertGreater(c.bbox()[0], 4.0)

    def test_tab_takes_the_other_side(self):
        s = self.add(geom.polyline(SQUARE, closed=True))
        t = self.tool('cut_portion')
        self.click(t, (5.0, 0.0))
        self.assertTrue(t.wants_key(key(Qt.Key.Key_Tab)))
        self.assertTrue(t.key(key(Qt.Key.Key_Tab)))
        self.click(t, (5.0, 10.0))
        self.assertLess(s.path.contours[0].bbox()[2], 6.0)

    def test_open_contour_makes_two_pieces(self):
        s = self.add(geom.polyline([(0.0, 0.0), (30.0, 0.0)]))
        t = self.tool('cut_portion')
        self.click(t, (20.0, 0.0))
        self.click(t, (10.0, 0.0))
        self.assertEqual([x.end for x in s.path.contours], [(10.0, 0.0), (30.0, 0.0)])

    def test_other_contours_stay(self):
        s = self.add(geom.polyline([(0.0, 0.0), (30.0, 0.0)]), geom.rect(0.0, 20.0, 10.0, 10.0))
        t = self.tool('cut_portion')
        self.click(t, (10.0, 0.0))
        self.click(t, (20.0, 0.0))
        self.assertEqual(len(s.path.contours), 3)

    def test_undo_is_one_step(self):
        self.add(geom.polyline(SQUARE, closed=True))
        n = len(self.win._undo)
        t = self.tool('cut_portion')
        self.click(t, (5.0, 0.0))
        self.click(t, (5.0, 10.0))
        self.assertEqual(len(self.win._undo), n + 1)
        self.win.undo()
        self.assertTrue(self.doc.layers[0].items[0].path.contours[0].closed)

    def test_second_click_must_be_elsewhere_on_the_same_contour(self):
        s = self.add(geom.polyline(SQUARE, closed=True), geom.rect(50.0, 0.0, 10.0, 10.0))
        t = self.tool('cut_portion')
        self.click(t, (5.0, 0.0))
        self.click(t, (50.0, 5.0))
        self.click(t, (5.0, 0.0))
        self.assertEqual(len(s.path.contours), 2)
        self.assertTrue(s.path.contours[0].closed)
        self.assertIsNotNone(t.first)

    def test_backspace_steps_back(self):
        self.add(geom.polyline(SQUARE, closed=True))
        t = self.tool('cut_portion')
        self.click(t, (5.0, 0.0))
        self.assertTrue(t.key(key(Qt.Key.Key_Backspace)))
        self.assertIsNone(t.first)
        self.assertFalse(t.wants_key(key(Qt.Key.Key_Tab)))

    def test_the_tool_stays_for_the_next_one(self):
        self.add(geom.polyline(SQUARE, closed=True))
        t = self.tool('cut_portion')
        self.click(t, (5.0, 0.0))
        self.click(t, (5.0, 10.0))
        self.assertIs(self.c.tool_obj, t)
        self.assertIsNone(t.first)

    def test_preview_shows_the_portion(self):
        self.add(geom.polyline(SQUARE, closed=True))
        t = self.tool('cut_portion')
        self.click(t, (5.0, 0.0))
        t.move(self.c.to_screen(5.0, 10.0), (5.0, 10.0), PLAIN)
        seen = []
        painter = mock.MagicMock()
        with mock.patch.object(t, 'preview', lambda p, path, color=None: seen.append(path)):
            t.paint(painter)
        self.assertLess(seen[0].contours[0].bbox()[2], 6.0)

    def test_shift_keeps_the_original(self):
        self.add(geom.polyline(SQUARE, closed=True))
        t = self.tool('cut_portion')
        self.click(t, (5.0, 0.0))
        self.click(t, (5.0, 10.0), SHIFT)
        self.assertEqual(len(self.layer.items), 2)
        self.assertTrue(self.layer.items[0].path.contours[0].closed)
        self.assertFalse(self.layer.items[1].path.contours[0].closed)


class Transform(Base):
    def run_tool(self, name, third=None):
        s = self.add(geom.polyline([(0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0)]))
        t = self.tool(name)
        self.click(t, (5.0, 0.0))
        self.click(t, (25.0, 0.0))
        if third is not None:
            self.assertEqual(s.path.contours[0].end, (30.0, 0.0))
            self.assertEqual(len(s.path.contours[0].segments), 3)
            self.click(t, third)
        return s.path.contours[0]

    def test_segment_needs_two_clicks(self):
        c = self.run_tool('portion_segment')
        self.assertEqual([x.end for x in c.segments], [(5.0, 0.0), (25.0, 0.0), (30.0, 0.0)])

    def test_arc_passes_through_the_third(self):
        c = self.run_tool('portion_arc', (15.0, 8.0))
        self.assertEqual(c.start, (0.0, 0.0))
        self.assertEqual(c.end, (30.0, 0.0))
        self.assertLess(min(math.dist(q, (15.0, 8.0)) for q in c.flatten(0.001)), 0.01)

    def test_curve_has_the_third_in_its_middle(self):
        c = self.run_tool('portion_curve', (15.0, 8.0))
        self.assertTrue(any(isinstance(x, Cubic) for x in c.segments))
        self.assertLess(min(math.dist(q, (15.0, 8.0)) for q in c.flatten(0.001)), 0.01)

    def test_angle_has_its_top_at_the_third(self):
        c = self.run_tool('portion_angle', (15.0, 8.0))
        self.assertIn((15.0, 8.0), [x.end for x in c.segments])

    def test_closed_contour_stays_closed(self):
        s = self.add(geom.polyline(SQUARE, closed=True))
        t = self.tool('portion_segment')
        self.click(t, (5.0, 0.0))
        self.click(t, (5.0, 10.0))
        self.assertTrue(s.path.contours[0].closed)
        self.assertAlmostEqual(abs(s.path.contours[0].signed_area()), 50.0)

    def test_tab_during_the_setting_changes_the_side(self):
        s = self.add(geom.polyline(SQUARE, closed=True))
        t = self.tool('portion_angle')
        self.click(t, (5.0, 0.0))
        self.click(t, (5.0, 10.0))
        t.key(key(Qt.Key.Key_Tab))
        self.click(t, (-5.0, 5.0))
        self.assertLess(s.path.contours[0].bbox()[0], -4.0)      # l'angle à gauche...
        self.assertLess(s.path.contours[0].bbox()[2], 6.0)       # ...remplace le côté droit


class Links(unittest.TestCase):
    def test_typeedit_commands(self):
        for cmd, key_ in (('ID_CUT_AND_DESTROY', 'tool_cut_portion'), ('ID_REMOVE_CONTOUR', 'tool_contour_erase'),
                          ('ID_CONTOUR_SUP', 'tool_contour_erase'), ('ID_CONTOUR_RABOT', 'tool_portion_segment'),
                          ('ID_CONTOUR_ARC', 'tool_portion_arc'), ('ID_CONTOUR_Linear_BEZIER', 'tool_portion_curve'),
                          ('ID_CONTOUR_SETANGLE', 'tool_portion_angle')):
            self.assertEqual(S.TE_ACTIONS[cmd], key_)


class Disconnect(Base):
    def test_several_points(self):
        s = self.add(geom.polyline(SQUARE, closed=True).close())
        self.c.select([s])
        t = self.tool('node')
        t.sel.clear()
        t.sel.update({(0, 0), (0, 2)})
        with mock.patch.object(t, 'shape', return_value=s):
            self.win.node_break()
        self.assertEqual(len(s.path.contours), 2)
        self.assertTrue(all(not c.closed for c in s.path.contours))
        self.win.undo()

    def test_nothing_selected_explains(self):
        s = self.add(geom.polyline(SQUARE, closed=True).close())
        self.c.select([s])
        t = self.tool('node')
        t.sel.clear()
        with mock.patch('vectordrive.ui.main_window.QMessageBox.information') as say:
            self.win.node_break()
        say.assert_called_once()


if __name__ == '__main__':
    unittest.main()
