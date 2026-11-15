"""Round 800 : Liquéfier (d'après VectorCraft)."""
import math
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

import numpy as np
from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication

from vectordrive.core import liquify as LQ
from vectordrive.core.document import Shape
from vectordrive.core.geom import Conic, Contour, Cubic, Line, Path, arc_conics, circle, polyline, rect

app = QApplication.instance() or QApplication([])


def square(a=40.0, x=0.0, y=0.0):
    return Path([polyline([(x, y), (x + a, y), (x + a, y + a), (x, y + a)], True)])


def area(path):
    return abs(sum(c.signed_area(1e-4) for c in path.contours))


def continuous(contour):
    segs = contour.segments
    for a, b in zip(segs, segs[1:] + (segs[:1] if contour.closed else [])):
        if math.dist(a.end, b.start) > 1e-7:
            return False
    return True


def stroke(path, points, **kw):
    return LQ.apply(path, points, LQ.params_from(kw))


class Dabs(unittest.TestCase):
    def test_spacing_along_the_stroke(self):
        p = LQ.params_from({'width': 10, 'height': 10})
        self.assertEqual(p.dab_spacing(), 1.0)
        d = LQ.Dabber(p)
        d.push((0, 0))
        d.push((3.5, 0))
        d.push((5.5, 0))
        self.assertEqual([q[0] for q in d.dabs], [0, 1, 2, 3, 4, 5])
        self.assertTrue(all(q[1] == 0 for q in d.dabs))

    def test_more_samples_only_add_dabs(self):
        p = LQ.params_from({'width': 10, 'height': 10})
        a, b = LQ.Dabber(p), LQ.Dabber(p)
        a.push((0, 0))
        a.push((10, 0))
        b.push((0, 0))
        for x in range(1, 11):
            b.push((x * 1.0, 0))
        self.assertEqual(len(a.dabs), len(b.dabs))
        np.testing.assert_allclose(a.dabs, b.dabs)

    def test_held_still(self):
        for kind, more in (('twirl', 1), ('pucker', 1), ('bloat', 1), ('warp', 0), ('wrinkle', 0)):
            d = LQ.Dabber(LQ.params_from({'kind': kind}))
            d.push((0, 0))
            self.assertEqual(len(d.push((0, 0))), more, kind)

    def test_cap(self):
        with mock.patch.object(LQ, 'MAX_DABS', 5):
            d = LQ.Dabber(LQ.params_from({'width': 1, 'height': 1}))
            d.push((0, 0))
            d.push((1000, 0))
        self.assertEqual(len(d.dabs), 5)


class Params(unittest.TestCase):
    def test_bad_values_are_brought_back(self):
        p = LQ.params_from({'kind': 'nonsense', 'intensity': 5, 'detail': 0, 'simplify': 500, 'width': -3, 'unknown': 1})
        self.assertEqual(p.kind, 'warp')
        self.assertEqual(p.intensity, 1.0)
        self.assertEqual(p.detail, 1.0)
        self.assertEqual(p.simplify, 100.0)
        self.assertEqual(p.width, 0.05)
        self.assertFalse(hasattr(p, 'unknown'))

    def test_falloff(self):
        p = LQ.Params(width=20, height=10)
        q = np.array([[0.0, 0.0], [10.0, 0.0], [0.0, 5.0], [5.0, 0.0], [11.0, 0.0]])
        f = p.falloff((0, 0), q)
        self.assertEqual(f[0], 1.0)
        self.assertEqual(f[1], 0.0)
        self.assertEqual(f[2], 0.0)
        self.assertAlmostEqual(f[3], (1 - 0.25) ** 2)
        self.assertEqual(f[4], 0.0)

    def test_falloff_turns_with_the_brush(self):
        p = LQ.Params(width=20, height=4, angle=90)
        self.assertGreater(p.falloff((0, 0), np.array([[0.0, 8.0]]))[0], 0.0)
        self.assertEqual(p.falloff((0, 0), np.array([[8.0, 0.0]]))[0], 0.0)


class Effects(unittest.TestCase):
    def test_warp_pushes_the_side(self):
        out = stroke(square(), [(20, 0), (20, 10)], width=20, height=20, intensity=1.0)
        self.assertGreater(max(s.bbox()[3] for s in out.contours[0].segments if s.bbox()[1] < 5), 2.0)
        self.assertLess(area(out), 1600)
        self.assertTrue(continuous(out.contours[0]))

    def test_nothing_under_the_brush(self):
        base = square()
        out = stroke(base, [(100, 100), (120, 120)], width=10, height=10)
        self.assertIs(out, base)

    def test_warp_without_moving_changes_nothing(self):
        base = square()
        self.assertEqual(area(stroke(base, [(20, 0)], width=20, height=20)), area(base))

    def test_what_the_brush_does_not_reach_stays_as_it_was(self):
        arc = list(arc_conics((0, 0), 30, 30, 0, 180))
        c = Contour([Line((-30, 0), (30, 0))] + arc, True)
        base = Path([c])
        out = stroke(base, [(0, 0), (0, 5)], width=8, height=8, intensity=1.0)
        conics = [s for s in out.contours[0].segments if isinstance(s, Conic)]
        self.assertEqual(len(conics), len(arc))             # le pinceau ne touche pas l'arc
        self.assertTrue(continuous(out.contours[0]))
        self.assertTrue(any(isinstance(s, Cubic) for s in out.contours[0].segments))

    def test_other_contours_are_the_same_objects(self):
        base = Path(square().contours + square(10, 100, 100).contours)
        out = stroke(base, [(20, 0), (20, 10)], width=20, height=20)
        self.assertIs(out.contours[1], base.contours[1])
        self.assertIsNot(out.contours[0], base.contours[0])

    def test_pucker_draws_in_bloat_pushes_out(self):
        base = Path([circle((0, 0), 10)])
        smaller = stroke(base, [(0, 0), (0.001, 0)], kind='pucker', width=30, height=30, intensity=0.5)
        bigger = stroke(base, [(0, 0), (0.001, 0)], kind='bloat', width=30, height=30, intensity=0.5)
        self.assertLess(area(smaller), area(base))
        self.assertGreater(area(bigger), area(base))

    def test_twirl_turns_and_keeps_the_size(self):
        base = square(20, -10, -10)
        out = stroke(base, [(0, 0)] + [(0, 0)] * 8, kind='twirl', width=60, height=60, intensity=1.0, rate=60)
        box = out.bbox()
        self.assertGreater(box[2], 10.2)                    # les coins sont partis
        self.assertAlmostEqual(area(out) / area(base), 1.0, delta=0.05)

    def test_twirl_direction(self):
        q = LQ._anchor_field(LQ.Params(kind='twirl', width=100, height=100, intensity=1.0, rate=40), (0, 0), (0, 0),
                             np.array([[10.0, 0.0]]), 0, 0.0)
        self.assertGreater(q[0, 1], 0.0)
        q = LQ._anchor_field(LQ.Params(kind='twirl', width=100, height=100, intensity=1.0, rate=-40), (0, 0), (0, 0),
                             np.array([[10.0, 0.0]]), 0, 0.0)
        self.assertLess(q[0, 1], 0.0)

    def test_noisy_kinds_are_steady(self):
        for kind in ('scallop', 'crystallize', 'wrinkle'):
            with self.subTest(kind):
                base = square()
                a = stroke(base, [(20, 0), (22, 0)], kind=kind, width=20, height=20, intensity=1.0)
                b = stroke(base, [(20, 0), (22, 0)], kind=kind, width=20, height=20, intensity=1.0)
                self.assertEqual(len(a.contours[0].segments), len(b.contours[0].segments))
                for s, t in zip(a.contours[0].segments, b.contours[0].segments):
                    self.assertEqual(s.controls(), t.controls())
                self.assertTrue(continuous(a.contours[0]))
                self.assertGreater(len(a.contours[0].segments), 4)

    def test_wrinkle_goes_only_where_asked(self):
        side = dict(kind='wrinkle', width=30, height=30, intensity=1.0, simplify_on=False)
        up = stroke(square(), [(40, 20), (40, 21)], horizontal=0.0, vertical=1.0, **side)
        self.assertAlmostEqual(up.bbox()[2], 40.0, places=9)        # le côté droit reste à sa place
        self.assertGreater(len(up.contours[0].segments), 6)
        across = stroke(square(), [(20, 0), (21, 0)], horizontal=1.0, vertical=0.0, **side)
        self.assertAlmostEqual(across.bbox()[1], 0.0, places=9)
        self.assertGreater(len(across.contours[0].segments), 6)
        moved = stroke(square(), [(40, 20), (40, 21)], horizontal=1.0, vertical=0.0, **side)
        self.assertGreater(abs(moved.bbox()[2] - 40.0), 0.01)

    def test_a_narrow_brush_does_not_slip_through_a_long_line(self):
        base = Path([polyline([(0, 0), (1000, 0)], False)])
        out = stroke(base, [(437, 0), (437, 3)], width=2, height=2, intensity=1.0, simplify_on=False)
        self.assertGreater(out.bbox()[3], 0.5)

    def test_only_the_part_under_the_brush_gets_points(self):
        base = Path([polyline([(0, 0), (1000, 0)], False)])
        out = stroke(base, [(437, 0), (437, 3)], width=4, height=4, intensity=1.0, simplify_on=False)
        self.assertLess(len(out.contours[0].segments), 40)
        far = [s for s in out.contours[0].segments if isinstance(s, Line)]
        self.assertGreater(max(s.length() for s in far), 200.0)      # le reste du trait est resté un trait

    def test_a_short_gesture_still_does_something(self):
        p = LQ.params_from({'width': 20, 'height': 20, 'intensity': 1.0})
        self.assertGreater(p.dab_spacing(), 1.0)
        out = LQ.apply(square(), [(20, 0), (20, 1.0)], p)
        self.assertGreater(max(s.bbox()[3] for s in out.contours[0].segments if s.bbox()[1] < 5), 0.5)

    def test_tail(self):
        d = LQ.Dabber(LQ.params_from({'width': 10, 'height': 10}))
        self.assertEqual(d.tail(), [])
        d.push((0, 0))
        self.assertEqual(d.tail(), [])
        d.push((2.5, 0))
        self.assertEqual(d.tail(), [(2.5, 0.0)])
        self.assertEqual(d.tail(), [])

    def test_small_gaps_do_not_open(self):
        c = Contour([Line((0, 0), (40, 0)), Line((40, 0.0002), (40, 40)), Line((40, 40), (0, 40)), Line((0, 40.0001), (0, 0))], True)
        for kind in ('crystallize', 'wrinkle', 'scallop'):
            with self.subTest(kind):
                out = stroke(Path([c]), [(40, 0), (41, 2)], kind=kind, width=30, height=30, intensity=1.0, complexity=3.0)
                segs = out.contours[0].segments
                joints = [math.dist(a.end, b.start) for a, b in zip(segs, segs[1:])]
                self.assertLess(max(joints), 0.001)

    def test_detail_adds_more_points(self):
        low = stroke(square(), [(20, 0), (20, 5)], width=20, height=20, detail=1, simplify_on=False)
        high = stroke(square(), [(20, 0), (20, 5)], width=20, height=20, detail=8, simplify_on=False)
        self.assertGreater(len(high.contours[0].segments), len(low.contours[0].segments))

    def test_segment_cap(self):
        with mock.patch.object(LQ, 'MAX_SEGMENTS', 8):
            out = stroke(square(), [(20, 0), (20, 5)], width=20, height=20, detail=10, simplify_on=False)
        self.assertLess(len(out.contours[0].segments), 30)
        self.assertTrue(continuous(out.contours[0]))

    def test_simplify_removes_flat_points(self):
        along = [(10, 0), (20, 0)]                  # glisser le long du côté : il reste droit
        off = stroke(square(), along, width=20, height=20, intensity=0.5, simplify_on=False)
        on = stroke(square(), along, width=20, height=20, intensity=0.5, simplify=100)
        self.assertGreater(len(off.contours[0].segments), len(on.contours[0].segments))
        self.assertEqual(len(on.contours[0].segments), 4)
        self.assertTrue(all(isinstance(s, Line) for s in on.contours[0].segments))
        self.assertAlmostEqual(area(on), 1600, places=6)

    def test_straight_pieces_are_lines(self):
        cp = np.array([[0.0, 0], [1, 0], [2, 1e-9], [3, 0]])
        self.assertIsInstance(LQ._segment(cp), Line)
        cp = np.array([[0.0, 0], [1, 1], [2, 1], [3, 0]])
        self.assertIsInstance(LQ._segment(cp), Cubic)

    def test_flat_is_only_forward(self):
        a = np.array([[0.0, 0], [1, 0], [2, 0], [3, 0]])
        fwd = np.array([[3.0, 0], [4, 0], [5, 0], [6, 0]])
        back = np.array([[3.0, 0], [2, 0], [1, 0], [0, 0]])
        bent = np.array([[3.0, 0], [4, 1], [5, 1], [6, 0]])
        self.assertTrue(LQ._flat(a, fwd, 0.01))
        self.assertFalse(LQ._flat(a, back, 0.01))
        self.assertFalse(LQ._flat(a, bent, 0.01))

    def test_open_contour(self):
        base = Path([polyline([(0, 0), (40, 0)], False)])
        out = stroke(base, [(20, 0), (20, 6)], width=10, height=10, intensity=1.0)
        c = out.contours[0]
        self.assertFalse(c.closed)
        self.assertEqual(c.start, (0, 0))
        self.assertEqual(c.end, (40, 0))
        self.assertGreater(c.bbox()[3], 1.0)

    def test_halves_are_the_same_curve(self):
        cp = np.array([[0.0, 0], [10, 20], [20, -20], [30, 0]])
        a, b = LQ._halves(cp)
        full = Cubic(*map(tuple, cp))
        for t in (0.0, 0.3, 0.7, 1.0):
            np.testing.assert_allclose(Cubic(*map(tuple, a)).point(t), full.point(t / 2), atol=1e-9)
            np.testing.assert_allclose(Cubic(*map(tuple, b)).point(t), full.point(0.5 + t / 2), atol=1e-9)

    def test_refine_keeps_the_ends_and_the_order(self):
        p = LQ.params_from({'width': 4, 'height': 4})
        cp = np.array([[0.0, 0], [100, 0], [200, 0], [300, 0]])
        parts = LQ._refine(cp, p, (150, 0), 1.0, 1000)
        np.testing.assert_allclose(parts[0][0], (0, 0))
        np.testing.assert_allclose(parts[-1][3], (300, 0))
        for a, b in zip(parts, parts[1:]):
            np.testing.assert_allclose(a[3], b[0])
        self.assertLess(len(parts), 40)
        self.assertEqual(len(LQ._refine(cp, p, (150, 0), 1.0, 0)), 1)
        self.assertEqual(len(LQ._refine(cp, p, (150, 0), 1.0, 1)), 2)

    def test_hits(self):
        p = LQ.params_from({'width': 2, 'height': 2})
        cp = np.array([[0.0, 0], [100, 0], [200, 0], [300, 0]])
        self.assertTrue(LQ._hits(cp, p, (123.4, 0.5)))
        self.assertFalse(LQ._hits(cp, p, (123.4, 1.5)))
        self.assertFalse(LQ._hits(cp, p, (500.0, 0.0)))

    def test_all_kinds_on_all_segment_kinds(self):
        c = Contour([Line((0, 0), (30, 0)), Cubic((30, 0), (40, 10), (40, 20), (30, 30))] +
                    [Conic((30, 30), (15, 45), (0, 30), math.sqrt(0.5)), Line((0, 30), (0, 0))], True)
        for kind in LQ.KINDS:
            with self.subTest(kind):
                out = stroke(Path([c]), [(30, 0), (30, 30), (0, 30)], kind=kind, width=25, height=25, intensity=0.7)
                self.assertTrue(continuous(out.contours[0]))
                for s in out.contours[0].segments:
                    self.assertTrue(all(math.isfinite(v) for q in s.controls() for v in q))


class Event:
    def __init__(self, key=None):
        self._key = key

    def key(self):
        return self._key


class Tool(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()
        cls.win.deleteLater()

    def setUp(self):
        self.c = self.win.canvas
        self.doc = self.c.doc
        self.doc.layers[0].items = []
        self.c.selection = []
        self.win._undo.clear()
        self.win.settings.remove('cad/liquefier')
        self.addCleanup(self.win.settings.remove, 'cad/liquefier')
        self.a = Shape(path=square(), name='a')
        self.b = Shape(path=square(40, 100, 0), name='b')
        self.doc.add(self.a)
        self.doc.add(self.b)
        self.win.set_tool('liquify')
        self.tool = self.c.tool_obj
        self.tool.params = LQ.params_from({'width': 20, 'height': 20, 'intensity': 1.0})
        self.addCleanup(self.win.set_tool, 'select')

    def drag(self, a, b, n=6):
        self.tool.press(QPointF(), a, None)
        for i in range(1, n + 1):
            q = (a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n)
            self.tool.move(QPointF(), q, None)
        self.tool.release(QPointF(), b, None)

    def test_is_the_tool(self):
        from vectordrive.ui.tools import LiquifyTool
        self.assertIsInstance(self.tool, LiquifyTool)

    def test_a_stroke_changes_what_it_meets_only(self):
        b0 = self.b.path
        self.drag((20, 0), (20, 10))
        self.assertLess(area(self.a.path), 1600)
        self.assertIs(self.b.path, b0)
        self.assertEqual(len(self.win._undo), 1)

    def test_selection_limits_the_stroke(self):
        a0 = self.a.path
        self.c.select([self.b])
        self.drag((20, 0), (20, 10))
        self.assertIs(self.a.path, a0)
        self.drag((120, 0), (120, 10))
        self.assertIsNot(self.b.path, None)
        self.assertLess(area(self.b.path), 1600)

    def test_nothing_changes_before_release(self):
        a0 = self.a.path
        self.tool.press(QPointF(), (20, 0), None)
        self.tool.move(QPointF(), (20, 10), None)
        self.assertIs(self.a.path, a0)
        self.assertTrue(self.tool.pool[0][1].changed)
        self.tool.release(QPointF(), (20, 10), None)
        self.assertIsNot(self.a.path, a0)

    def test_undo(self):
        a0 = self.a.path
        self.drag((20, 0), (20, 10))
        self.win.undo()
        self.assertEqual(area(self.doc.layers[0].items[0].path), area(a0))

    def test_stroke_elsewhere_leaves_no_undo(self):
        self.drag((500, 500), (510, 500))
        self.assertEqual(self.win._undo, [])

    def test_escape_abandons(self):
        a0 = self.a.path
        self.tool.press(QPointF(), (20, 0), None)
        self.tool.move(QPointF(), (20, 10), None)
        self.assertTrue(self.tool.key(Event(Qt.Key.Key_Escape)))
        self.assertIsNone(self.tool.pool)
        self.tool.release(QPointF(), (20, 10), None)
        self.assertIs(self.a.path, a0)
        self.assertEqual(self.win._undo, [])
        self.assertFalse(self.tool.key(Event(Qt.Key.Key_Escape)))

    def test_escape_key_reaches_the_tool_during_the_gesture_only(self):
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent
        a0 = self.a.path
        esc = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        self.tool.press(QPointF(), (20, 0), None)
        self.tool.move(QPointF(), (20, 10), None)
        self.c.keyPressEvent(esc)
        self.assertEqual(self.c.tool, 'liquify')        # le geste part, l'outil reste
        self.assertIsNone(self.tool.dabber)
        self.assertIs(self.a.path, a0)
        self.c.keyPressEvent(esc)
        self.assertEqual(self.c.tool, 'select')         # hors geste, comme partout

    def test_changing_tool_stops_the_hold(self):
        self.tool.params = LQ.params_from({'kind': 'bloat'})
        self.tool.press(QPointF(), (20, 20), None)
        self.assertIsNotNone(self.tool.timer)
        self.win.set_tool('select')
        self.assertIsNone(self.tool.timer)
        self.assertIsNone(self.tool.dabber)

    def test_short_drag_counts(self):
        self.tool.press(QPointF(), (20, 0), None)
        self.tool.release(QPointF(), (20, 0.8), None)
        self.assertLess(area(self.a.path), 1600)

    def test_brackets_change_the_size(self):
        w = self.tool.params.width
        self.assertTrue(self.tool.wants_key(Event(Qt.Key.Key_BracketRight)))
        self.assertTrue(self.tool.key(Event(Qt.Key.Key_BracketRight)))
        self.assertAlmostEqual(self.tool.params.width, w * 1.25)
        self.assertTrue(self.tool.key(Event(Qt.Key.Key_BracketLeft)))
        self.assertAlmostEqual(self.tool.params.height, w)

    def test_hold_keeps_going(self):
        self.tool.params = LQ.params_from({'kind': 'bloat', 'width': 60, 'height': 60, 'intensity': 0.3})
        self.tool.press(QPointF(), (20, 20), None)
        self.assertIsNotNone(self.tool.timer)
        self.assertEqual(self.tool.timer.interval(), self.tool.TICK_MS)
        one = self.tool.pool[0][1].count
        self.tool.tick()
        self.tool.tick()
        self.assertEqual(self.tool.pool[0][1].count, one + 2)
        self.tool.release(QPointF(), (20, 20), None)
        self.assertIsNone(self.tool.timer)
        self.assertGreater(area(self.a.path), 1600)

    def test_warp_has_no_timer(self):
        self.tool.press(QPointF(), (20, 0), None)
        self.assertIsNone(self.tool.timer)
        self.tool.release(QPointF(), (20, 0), None)

    def test_forms_become_plain_shapes(self):
        self.a.extra = {'forme': {'x': 1}, 'sketch': {'a': 1}, 'sketch_box': [0, 0, 1, 1], 'script': {'b': 1},
                        'corners': {'c': 1}, 'kept': 7}
        self.drag((20, 0), (20, 10))
        self.assertEqual(self.a.extra, {'kept': 7})

    def test_volumes_are_left_out(self):
        from vectordrive.core import solids as SO
        if not SO.available():
            self.skipTest('manifold3d absent')
        v = SO.make_shape(SO.box(0, 0, 0, 50, 50, 5))
        self.doc.add(v)
        self.assertNotIn(v, self.tool._targets())

    def test_hidden_and_locked_layers_are_left_out(self):
        self.doc.layers[0].locked = True
        self.addCleanup(setattr, self.doc.layers[0], 'locked', False)
        self.assertEqual(self.tool._targets(), [])

    def test_group_children_are_reached(self):
        from vectordrive.core.document import Group
        g = Group(children=[Shape(path=square(10, 300, 0), name='in')])
        self.doc.add(g)
        self.assertIn(g.children[0], self.tool._targets())

    def test_paint_does_not_fail(self):
        from PySide6.QtGui import QImage, QPainter
        self.tool.press(QPointF(), (20, 0), None)
        self.tool.move(QPointF(), (20, 10), None)
        img = QImage(200, 200, QImage.Format.Format_ARGB32)
        p = QPainter(img)
        self.tool.paint(p)
        p.end()
        self.tool.cancel()
        self.tool.hover = (5, 5)
        p = QPainter(img)
        self.tool.paint(p)
        p.end()

    def test_options_keep_and_apply(self):
        got = self.win.liquify_options(params={'kind': 'twirl', 'width': 33.0, 'height': 11.0, 'rate': -20.0})
        self.assertEqual(got.kind, 'twirl')
        self.assertIs(self.c.tool_obj.params, got)
        self.assertEqual(self.win.liquify_params().width, 33.0)
        self.assertEqual(self.win.liquify_params().rate, -20.0)

    def test_options_take_up_the_tool(self):
        self.win.set_tool('select')
        self.win.liquify_options(params={'kind': 'bloat'})
        self.assertEqual(self.c.tool, 'liquify')
        self.assertEqual(self.c.tool_obj.params.kind, 'bloat')

    def test_tool_starts_with_kept_settings(self):
        self.win.liquify_options(params={'kind': 'pucker', 'width': 7.0})
        self.win.set_tool('select')
        self.win.set_tool('liquify')
        self.assertEqual(self.c.tool_obj.params.kind, 'pucker')
        self.assertEqual(self.c.tool_obj.params.width, 7.0)

    def test_ribbon(self):
        for key in ('tool_liquify', 'liquify_options'):
            action = self.win.A[key]
            found = [b for i in range(self.win.ribbon.count()) for g in self.win.ribbon.page(i).groups()
                     for b in g.buttons() if b.defaultAction() is action]
            self.assertEqual(len(found), 1, key)


if __name__ == '__main__':
    unittest.main()
