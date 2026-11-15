"""Round 825 : les quatre courbes symétriques."""
import math
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from vectordrive.core.document import Layer, Plate, Shape
from vectordrive.core.geom import Affine, Cubic, Line
from vectordrive.core.symmetric import SYM_MODES, sym_curve, sym_points
from vectordrive.ui import shortcuts as S
from vectordrive.ui import tools as T
from vectordrive.ui.main_window import MainWindow

app = QApplication.instance() or QApplication([])
ARC = [(-20.0, 5.0), (0.0, 15.0), (20.0, 5.0)]


def close_to(contour, other, tol=1e-6):
    """Deux courbes passent par les mêmes points."""
    a = contour.flatten(0.01)
    b = other.flatten(0.01)
    return all(min(math.dist(p, q) for q in b) < 0.05 for p in a[::5]) and tol > 0


class Ev:
    def __init__(self, key=None, mods=Qt.KeyboardModifier.NoModifier):
        self._k, self._m = key, mods

    def key(self):
        return self._k

    def modifiers(self):
        return self._m


class CoreTest(unittest.TestCase):
    def test_ox_closed(self):
        c = sym_curve(ARC, 'ox', (0, 0))
        self.assertTrue(c.closed)
        self.assertEqual(len(c.segments), 6)
        self.assertTrue(close_to(c, c.transformed(Affine.mirror_x(0))))
        b = c.flatten(0.01)
        self.assertGreater(max(p[1] for p in b), 14.9)
        self.assertLess(min(p[1] for p in b), -14.9)

    def test_oy_closed(self):
        c = sym_curve([(5.0, -20.0), (15.0, 0.0), (5.0, 20.0)], 'oy', (0, 0))
        self.assertTrue(c.closed)
        self.assertTrue(close_to(c, c.transformed(Affine.mirror_y(0))))

    def test_both_symmetric_twice(self):
        c = sym_curve([(2.0, 20.0), (15.0, 15.0), (20.0, 2.0)], 'both', (0, 0))
        self.assertTrue(c.closed)
        self.assertEqual(len(c.segments), 12)
        self.assertTrue(close_to(c, c.transformed(Affine.mirror_x(0))))
        self.assertTrue(close_to(c, c.transformed(Affine.mirror_y(0))))

    def test_both_does_not_cross_itself_whichever_way_drawn(self):
        """Du haut vers la droite ou de la droite vers le haut : la même forme, pas de grand trait en travers."""
        pts = [(2.0, 20.0), (15.0, 15.0), (20.0, 2.0)]
        one = sym_curve(pts, 'both', (0, 0)).flatten(0.01)
        two = sym_curve(pts[::-1], 'both', (0, 0)).flatten(0.01)

        def length(p):
            return sum(math.dist(a, b) for a, b in zip(p, p[1:]))
        self.assertAlmostEqual(length(one), length(two), delta=0.5)

    def test_origin_is_a_half_turn_not_a_mirror(self):
        c = sym_curve([(-20.0, 0.0), (-10.0, 12.0), (10.0, 8.0)], 'origin', (0, 0))
        self.assertTrue(c.closed)
        self.assertEqual(len(c.segments), 6)
        self.assertTrue(close_to(c, c.transformed(Affine.rotation(180.0, (0, 0)))))
        self.assertFalse(close_to(c, c.transformed(Affine.mirror_x(0))))

    def test_open(self):
        c = sym_curve(ARC, 'ox', (0, 0), closed=False)
        self.assertFalse(c.closed)
        self.assertAlmostEqual(c.start[0], -20.0)
        self.assertAlmostEqual(c.start[1], 5.0)
        self.assertAlmostEqual(c.end[0], -20.0)
        self.assertAlmostEqual(c.end[1], -5.0)

    def test_point_on_the_axis_is_not_doubled(self):
        pts = sym_points([(-10.0, 0.0), (0.0, 10.0), (10.0, 0.0)], 'ox', (0, 0))
        self.assertEqual(len(pts), 5)
        c = sym_curve([(-10.0, 0.0), (0.0, 10.0), (10.0, 0.0)], 'ox', (0, 0))
        self.assertTrue(c.closed)
        self.assertEqual(len(c.segments), 4)

    def test_near_the_axis_lands_on_it(self):
        c = sym_curve([(-10.0, 0.04), (0.0, 10.0), (10.0, -0.04)], 'ox', (0, 0), tol=0.05)
        self.assertEqual(len(c.segments), 4)
        self.assertEqual(c.start[1], 0.0)

    def test_center_of_the_plate_not_zero(self):
        c = sym_curve([(90.0, 60.0), (100.0, 70.0), (110.0, 60.0)], 'ox', (100.0, 50.0))
        self.assertTrue(close_to(c, c.transformed(Affine.mirror_x(50.0))))
        self.assertAlmostEqual(min(p[1] for p in c.flatten(0.01)), 30.0, delta=0.1)

    def test_corners_stop_the_smoothing(self):
        all_corners = sym_curve(ARC, 'ox', (0, 0), corners={0, 1, 2})
        self.assertTrue(all(isinstance(s, Line) for s in all_corners.segments))
        self.assertTrue(all_corners.closed)
        self.assertEqual(len(all_corners.segments), 6)
        one = sym_curve(ARC, 'ox', (0, 0), corners={1})
        self.assertTrue(one.closed)
        self.assertEqual(len(one.segments), 6)
        self.assertTrue(any(isinstance(s, Cubic) for s in one.segments))
        at = [s for s in one.segments if abs(s.end[0]) < 1e-9 and s.end[1] > 14]
        following = [s for s in one.segments if abs(s.start[0]) < 1e-9 and s.start[1] > 14]
        d0 = (at[0].end[0] - at[0].p2[0], at[0].end[1] - at[0].p2[1])
        d1 = (following[0].p1[0] - following[0].start[0], following[0].p1[1] - following[0].start[1])
        self.assertGreater(abs(d0[0] * d1[1] - d0[1] * d1[0]), 1.0)      # vraie cassure

    def test_smooth_without_corner(self):
        c = sym_curve(ARC, 'ox', (0, 0))
        for a, b in zip(c.segments, c.segments[1:]):
            d0 = (a.end[0] - a.p2[0], a.end[1] - a.p2[1])
            d1 = (b.p1[0] - b.start[0], b.p1[1] - b.start[1])
            self.assertAlmostEqual(d0[0] * d1[1] - d0[1] * d1[0], 0.0, places=6)

    def test_no_loop_between_a_point_and_its_mirror(self):
        """Un point cliqué à 1 mm de l'axe : la courbe passe l'axe sans boucle ni pointe qui dépasse."""
        pts = [(1.0, 24.0), (10.0, 14.0), (24.0, 12.0), (24.0, 1.0)]
        for mode in ('both', 'oy'):
            b = sym_curve(pts, mode, (0, 0)).flatten(0.01)
            self.assertLess(max(p[1] for p in b), 25.0, mode)
        b = sym_curve(pts, 'both', (0, 0)).flatten(0.01)
        self.assertLess(max(p[0] for p in b), 25.0)
        for mode in SYM_MODES:
            c = sym_curve(pts, mode, (0, 0))
            for s in c.segments:
                for q in (s.p1, s.p2):
                    self.assertLess(math.dist(q, s.p0) + math.dist(q, s.p3), 2.0 * math.dist(s.p0, s.p3) + 1e-9)

    def test_degenerate(self):
        self.assertFalse(sym_curve([], 'ox', (0, 0)).segments)
        for mode in SYM_MODES:
            sym_curve([(0.0, 0.0)], mode, (0, 0))
            sym_curve([(0.0, 0.0), (0.0, 0.0)], mode, (0, 0))
        two_on_axis = sym_curve([(-5.0, 0.0), (5.0, 0.0)], 'ox', (0, 0))
        self.assertEqual(len(two_on_axis.segments), 1)
        self.assertFalse(two_on_axis.closed)


class WindowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()
        cls.win.deleteLater()

    def setUp(self):
        self.doc = self.win.canvas.doc
        self.layer = Layer(name='Plan 1')
        self.doc.layers[:] = [self.layer]
        self.doc.active = self.layer.id
        self.doc.plate = Plate(width=200.0, height=100.0)
        self.win._undo.clear()
        self.win.canvas.scale = 8.0              # l'accrochage à l'axe se compte en pixels
        self.win.set_tool('select')

    def tool(self, key='sym_ox'):
        self.win.set_tool(key)
        t = self.win.canvas.tool_obj
        self.assertIsInstance(t, T.SymCurveTool)
        return t

    def click(self, t, *pts):
        for p in pts:
            t.press(QPointF(0, 0), p, Ev())

    def shapes(self):
        return [i for i in self.doc.iter_items() if isinstance(i, Shape)]

    def test_draw_and_undo(self):
        cx, cy = self.win.canvas.symmetry_center()
        t = self.tool()
        self.click(t, (cx - 20, cy + 5), (cx, cy + 15), (cx + 20, cy + 5))
        t.double(QPointF(0, 0), (cx + 20, cy + 5), Ev())
        s = self.shapes()
        self.assertEqual(len(s), 1)
        c = s[0].path.contours[0]
        self.assertEqual(len(s[0].path.contours), 1)
        self.assertTrue(c.closed)
        self.assertEqual(len(c.nodes()), 6)                 # un tracé qu'on retouche en Mode Point
        self.assertTrue(self.win.A['tool_select'].isChecked())
        self.win.undo()
        self.assertEqual(self.shapes(), [])

    def test_each_tool_has_its_mode(self):
        for key, mode in (('sym_ox', 'ox'), ('sym_oy', 'oy'), ('sym_both', 'both'), ('sym_origin', 'origin')):
            self.assertEqual(self.tool(key).mode, mode)

    def test_f_opens_and_closes(self):
        cx, cy = self.win.canvas.symmetry_center()
        said = []
        self.win.canvas.measured.connect(said.append)
        try:
            t = self.tool()
            self.assertTrue(t.closed)
            self.assertIn('fermée', said[-1])
            ev = Ev(Qt.Key.Key_F)
            self.assertTrue(t.wants_key(ev))
            self.assertFalse(t.wants_key(Ev(Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)))
            self.assertTrue(t.key(ev))
            self.assertFalse(t.closed)
            self.assertIn('ouverte', said[-1])
        finally:
            self.win.canvas.measured.disconnect(said.append)
        self.click(t, (cx - 20, cy + 5), (cx, cy + 15))
        self.assertTrue(t.key(Ev(Qt.Key.Key_Return)))
        self.assertFalse(self.shapes()[0].path.contours[0].closed)

    def test_ctrl_adds_one_corner_for_each_hold(self):
        cx, cy = self.win.canvas.symmetry_center()
        t = self.tool()
        self.click(t, (cx - 20, cy + 5))
        ctrl = Ev(mods=Qt.KeyboardModifier.ControlModifier)
        t.move(QPointF(0, 0), (cx - 10, cy + 8), ctrl)
        t.move(QPointF(0, 0), (cx - 9, cy + 9), ctrl)
        self.assertEqual(len(t.pts), 2)
        self.assertEqual(t.corners, {1})
        t.move(QPointF(0, 0), (cx - 5, cy + 10), Ev())
        self.assertEqual(len(t.pts), 2)
        t.move(QPointF(0, 0), (cx, cy + 12), ctrl)
        self.assertEqual(len(t.pts), 3)
        self.assertEqual(t.corners, {1, 2})

    def test_shift_adds_a_tangent_point(self):
        cx, cy = self.win.canvas.symmetry_center()
        t = self.tool()
        self.click(t, (cx - 20, cy + 5))
        t.move(QPointF(0, 0), (cx - 10, cy + 8), Ev(mods=Qt.KeyboardModifier.ShiftModifier))
        self.assertEqual(len(t.pts), 2)
        self.assertEqual(t.corners, set())

    def test_ctrl_click_is_a_corner(self):
        cx, cy = self.win.canvas.symmetry_center()
        t = self.tool()
        t.press(QPointF(0, 0), (cx - 20, cy + 5), Ev(mods=Qt.KeyboardModifier.ControlModifier))
        self.assertEqual(t.corners, {0})

    def test_backspace_forgets_the_corner(self):
        cx, cy = self.win.canvas.symmetry_center()
        t = self.tool()
        self.click(t, (cx - 20, cy + 5))
        t.move(QPointF(0, 0), (cx - 10, cy + 8), Ev(mods=Qt.KeyboardModifier.ControlModifier))
        self.assertTrue(t.key(Ev(Qt.Key.Key_Backspace)))
        self.assertEqual(len(t.pts), 1)
        self.assertEqual(t.corners, set())

    def test_keys_without_points_go_elsewhere(self):
        t = self.tool()
        self.assertFalse(t.wants_key(Ev(Qt.Key.Key_Backspace)))
        self.assertFalse(t.wants_key(Ev(Qt.Key.Key_Return)))
        self.assertFalse(t.key(Ev(Qt.Key.Key_Delete)))

    def test_cancel_draws_nothing(self):
        cx, cy = self.win.canvas.symmetry_center()
        t = self.tool()
        self.click(t, (cx - 20, cy + 5), (cx, cy + 15))
        t.cancel()
        t.double(QPointF(0, 0), (cx, cy), Ev())
        self.assertEqual(self.shapes(), [])

    def test_free_symmetric_drawing_does_not_mirror_it_again(self):
        cx, cy = self.win.canvas.symmetry_center()
        c = self.win.canvas
        c.symmetric, c.cyclic = True, 4
        try:
            t = self.tool()
            self.click(t, (cx - 20, cy + 5), (cx, cy + 15), (cx + 20, cy + 5))
            t.double(QPointF(0, 0), (cx + 20, cy + 5), Ev())
            self.assertEqual(len(self.shapes()[0].path.contours), 1)
            self.assertTrue(c.symmetric)
            self.assertEqual(c.cyclic, 4)
        finally:
            c.symmetric, c.cyclic = False, 0

    def test_axis_is_the_middle_of_the_plate(self):
        self.doc.plate = Plate(width=200.0, height=100.0, x=10.0, y=20.0)
        cx, cy = self.win.canvas.symmetry_center()
        self.assertEqual((cx, cy), (110.0, 70.0))
        t = self.tool()
        self.click(t, (90.0, 80.0), (110.0, 90.0), (130.0, 80.0))
        t.key(Ev(Qt.Key.Key_Return))
        c = self.shapes()[0].path.contours[0]
        self.assertTrue(close_to(c, c.transformed(Affine.mirror_x(70.0))))

    def test_paint(self):
        img = QImage(200, 200, QImage.Format.Format_ARGB32)
        cx, cy = self.win.canvas.symmetry_center()
        for key in ('sym_ox', 'sym_oy', 'sym_both', 'sym_origin'):
            t = self.tool(key)
            p = QPainter(img)
            t.paint(p)                       # sans point : les axes seuls
            self.click(t, (cx - 20, cy + 5), (cx, cy + 15))
            t.move(QPointF(0, 0), (cx + 20, cy + 5), Ev())
            t.paint(p)
            p.end()

    def test_typeedit_commands(self):
        self.assertEqual(S.TE_ACTIONS['ID_SYMMETRICAL_CURVES_AXISX'], 'tool_sym_ox')
        self.assertEqual(S.TE_ACTIONS['ID_SYMMETRICAL_CURVES_AXISY'], 'tool_sym_oy')
        self.assertEqual(S.TE_ACTIONS['ID_SYMMETRICAL_CURVES_CYCLIC'], 'tool_sym_both')
        self.assertEqual(S.TE_ACTIONS['ID_SYMMETRICAL_CURVES_POINT'], 'tool_sym_origin')

    def test_free_drawing_toggles_stay(self):
        for k in ('sym_draw', 'sym_cyclic', 'sym_point'):
            self.assertIn(k, self.win.A)


if __name__ == '__main__':
    unittest.main()
