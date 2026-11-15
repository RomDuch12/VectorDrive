"""Round 816 : largeur variable : profils à points, côtés séparés, bande robuste ; outil Largeur."""
import math
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication
from shapely.geometry import LineString, Point
from shapely.geometry import Polygon as SPoly

from vectordrive.core import varstroke as VS
from vectordrive.core.document import Layer, Plate, Shape
from vectordrive.core.geom import Path, circle, polyline
from vectordrive.ui import tools as T

app = QApplication.instance() or QApplication([])


def line(*pts, closed=False):
    return Shape(path=Path([polyline(list(pts), closed=closed)]))


def spec_points(*knots):
    return VS.VarStrokeSpec(profile='points', knots=list(knots))


class Sides(unittest.TestCase):
    def test_without_knots_nothing(self):
        self.assertEqual(VS.sides_at(spec_points(), 0.5), (0.0, 0.0))

    def test_one_knot_is_constant(self):
        s = spec_points((0.3, 1.0, 2.0))
        for t in (0.0, 0.3, 1.0):
            self.assertEqual(VS.sides_at(s, t), (1.0, 2.0))

    def test_between_knots(self):
        s = spec_points((0.0, 0.0, 0.0), (1.0, 4.0, 2.0))
        self.assertEqual(VS.sides_at(s, 0.25), (1.0, 0.5))

    def test_no_kink_and_no_overshoot_between_knots(self):
        s = spec_points((0.0, 1.0, 1.0), (0.3, 5.0, 5.0), (0.6, 2.0, 2.0), (1.0, 2.0, 2.0))
        values = [VS.sides_at(s, k / 1000.0)[0] for k in range(1001)]
        self.assertLessEqual(max(values), 5.0 + 1e-9)
        self.assertGreaterEqual(min(values), 1.0 - 1e-9)
        steps = [b - a for a, b in zip(values, values[1:])]
        self.assertLess(max(abs(b - a) for a, b in zip(steps, steps[1:])), 0.002)  # pente continue, y compris aux points
        self.assertAlmostEqual(VS.sides_at(s, 0.3)[0], 5.0)
        self.assertLess(max(values[600:]) - 2.0, 1e-9)                     # plat après le dernier changement

    def test_knots_any_order(self):
        s = spec_points((1.0, 4.0, 4.0), (0.0, 0.0, 0.0))
        self.assertEqual(VS.sides_at(s, 0.5), (2.0, 2.0))

    def test_same_abscissa_does_not_divide_by_zero(self):
        s = spec_points((0.5, 1.0, 1.0), (0.5, 3.0, 3.0))
        self.assertEqual(VS.sides_at(s, 0.4), (1.0, 1.0))
        self.assertEqual(VS.sides_at(s, 0.6), (3.0, 3.0))
        s = spec_points((0.0, 0.0, 0.0), (0.5, 1.0, 1.0), (0.5, 3.0, 3.0), (1.0, 3.0, 3.0))
        self.assertEqual(VS.sides_at(s, 0.5), (3.0, 3.0))

    def test_negative_width_is_zero(self):
        self.assertEqual(VS.sides_at(spec_points((0.0, -2.0, -2.0)), 0.0), (0.0, 0.0))

    def test_old_profiles_are_symmetric(self):
        s = VS.VarStrokeSpec(profile='lineaire', w_start=2.0, w_end=2.0)
        self.assertEqual(VS.sides_at(s, 0.5), (1.0, 1.0))


class Presets(unittest.TestCase):
    def test_each_ends_as_announced(self):
        def w(name, t):
            return VS.width_at(VS.VarStrokeSpec(profile=name, w_end=2.0), t)
        self.assertEqual(w('pointe_debut', 0.0), 0.0)
        self.assertEqual(w('pointe_debut', 1.0), 2.0)
        self.assertEqual(w('pointe_fin', 0.0), 2.0)
        self.assertEqual(w('pointe_fin', 1.0), 0.0)
        self.assertEqual(w('pincement', 0.5), 0.5)
        self.assertEqual(w('goutte', 0.2), 2.0)
        self.assertEqual(w('goutte', 1.0), 0.0)
        self.assertEqual(w('vague', 0.25), 2.0)
        self.assertEqual(w('vague', 0.5), 0.6)

    def test_area_of_a_teardrop(self):
        path = VS.var_stroke(line((0, 0), (100, 0)).path, VS.VarStrokeSpec(profile='goutte', w_end=10.0))
        self.assertEqual(len(path.contours), 1)
        area = abs(path.contours[0].signed_area())
        self.assertAlmostEqual(area, 583.33, delta=1.0)                     # intégrale de la cubique monotone


class Band(unittest.TestCase):
    def test_area_follows_the_profile(self):
        s = spec_points((0.0, 1.0, 1.0), (1.0, 3.0, 3.0))
        g = VS.band([(0, 0), (100, 0)], s)
        self.assertAlmostEqual(g.area, (2 + 6) / 2 * 100, delta=0.5)

    def test_one_side_only(self):
        g = VS.band([(0, 0), (100, 0)], spec_points((0.0, 5.0, 0.0)))
        b = g.bounds
        self.assertAlmostEqual(b[1], 0.0)
        self.assertAlmostEqual(b[3], 5.0)                                 # à gauche d'un trait vers la droite : en haut

    def test_other_side_only(self):
        g = VS.band([(0, 0), (100, 0)], spec_points((0.0, 0.0, 5.0)))
        self.assertAlmostEqual(g.bounds[1], -5.0)
        self.assertAlmostEqual(g.bounds[3], 0.0)

    def test_bend_tighter_than_the_width_loses_nothing(self):
        """Une épingle : la bande se croise ; l'ancien nettoyage pouvait en perdre un morceau."""
        pts = [(0, 0), (50, 0), (50, 1), (0, 1)]
        s = VS.VarStrokeSpec(profile='lineaire', w_start=6.0, w_end=6.0)
        g = VS.band(pts, s)
        self.assertTrue(g.is_valid)
        for x in (5.0, 25.0, 45.0):
            self.assertTrue(g.contains(Point(x, 0.5)))
            self.assertTrue(g.contains(Point(x, 2.9)))
            self.assertTrue(g.contains(Point(x, -2.4)))

    def test_self_crossing_stroke_keeps_both_lobes(self):
        pts = [(0, 0), (100, 100), (100, 0), (0, 100)]
        g = VS.band(pts, VS.VarStrokeSpec(profile='lineaire', w_start=4.0, w_end=4.0))
        self.assertTrue(g.is_valid)
        for q in ((10, 10), (90, 90), (100, 50), (10, 90), (90, 10), (50, 50)):
            self.assertTrue(g.contains(Point(q)), q)
        self.assertAlmostEqual(g.area, LineString(pts).length * 4, delta=0.08 * LineString(pts).length * 4)

    def test_straight_case_stays_exact(self):
        g = VS.band([(0, 0), (10, 0)], VS.VarStrokeSpec(profile='lineaire', w_start=2.0, w_end=2.0))
        self.assertAlmostEqual(g.area, 20.0, places=6)

    def test_closed_with_knots_has_no_step_at_the_seam(self):
        c = Shape(path=Path([circle((0, 0), 50)])).path.contours[0]
        s = spec_points((0.25, 1.0, 1.0), (0.75, 5.0, 5.0))
        g = VS.band(c.flatten(0.01), s, True)
        self.assertTrue(g.is_valid)
        self.assertEqual(g.geom_type, 'Polygon')
        self.assertEqual(len(g.interiors), 1)
        ring = SPoly(g.exterior)
        # au raccord du tour (x = 50) : entre 1 et 5 mm de chaque côté, mais pas de marche
        before = LineString([(0, 0), (60 * math.cos(0.02), 60 * math.sin(0.02))]).intersection(ring).length
        after = LineString([(0, 0), (60 * math.cos(-0.02), 60 * math.sin(-0.02))]).intersection(ring).length
        self.assertAlmostEqual(before, after, delta=0.2)

    def test_closed_constant_ring(self):
        c = Shape(path=Path([circle((0, 0), 50)])).path.contours[0]
        g = VS.band(c.flatten(0.01), spec_points((0.0, 2.0, 2.0)), True)
        self.assertAlmostEqual(g.area, math.pi * (52 ** 2 - 48 ** 2), delta=4.0)

    def test_var_stroke_all_contours(self):
        p = Path([polyline([(0, 0), (10, 0)], closed=False), polyline([(0, 50), (10, 50)], closed=False)])
        got = VS.var_stroke(p, spec_points((0.0, 1.0, 1.0)))
        self.assertEqual(len(got.contours), 2)


class Canvas:
    """Ce que l'outil utilise du canevas."""

    def __init__(self, item=None):
        self.item = item
        self.scale = 1.0
        self.selection = []
        self.undo_push = mock.Mock()
        self.measured = mock.Mock()
        self.documentChanged = mock.Mock()
        self.overlay_update = mock.Mock()
        self.invalidate = mock.Mock()
        self.update = mock.Mock()

    def pick(self, _sp):
        return self.item

    def select(self, items):
        self.selection = items

    def to_screen(self, x, y):
        return QPointF(x, y)


class Ev:
    def __init__(self, mods=Qt.KeyboardModifier.NoModifier, key=None):
        self._mods, self._key = mods, key

    def modifiers(self):
        return self._mods

    def button(self):
        return Qt.MouseButton.LeftButton

    def key(self):
        return self._key


P = QPointF(0, 0)


class Tool(unittest.TestCase):
    def setUp(self):
        self.shape = line((0, 0), (100, 0))
        self.canvas = Canvas(self.shape)
        self.tool = T.WidthTool(self.canvas)

    def drag(self, a, b, mods=Qt.KeyboardModifier.NoModifier):
        self.tool.press(P, a, Ev(mods))
        self.tool.move(P, b, Ev(mods))
        self.tool.release(P, b, Ev(mods))

    def test_click_elsewhere_takes_nothing(self):
        self.canvas.item = None
        self.tool.press(P, (0, 500), Ev())
        self.assertIsNone(self.tool.item)
        self.canvas.measured.emit.assert_called()

    def test_a_text_is_no_stroke(self):
        self.canvas.item = object()
        self.tool.press(P, (0, 0), Ev())
        self.assertIsNone(self.tool.item)

    def test_drag_sets_both_sides(self):
        self.drag((50, 0), (50, 7))
        self.assertEqual(len(self.tool.knots), 1)
        t, left, right = self.tool.knots[0]
        self.assertAlmostEqual(t, 0.5)
        self.assertAlmostEqual(left, 7.0)
        self.assertAlmostEqual(right, 7.0)
        self.assertEqual(self.canvas.selection, [self.shape])

    def test_alt_sets_the_side_under_the_pointer(self):
        self.drag((50, 0), (50, 7))
        self.drag((50, -7), (50, -2), Qt.KeyboardModifier.AltModifier)
        t, left, right = self.tool.knots[0]
        self.assertAlmostEqual(left, 7.0)
        self.assertAlmostEqual(right, 2.0)

    def test_alt_on_a_new_knot(self):
        self.drag((50, 0), (50, 7))
        self.drag((20, 0), (20, 3), Qt.KeyboardModifier.AltModifier)
        k = self.tool.knots[0]
        self.assertAlmostEqual(k[0], 0.2)
        self.assertAlmostEqual(k[1], 3.0)
        self.assertAlmostEqual(k[2], 7.0)

    def test_new_knot_starts_at_the_width_of_the_stroke(self):
        self.drag((50, 0), (50, 8))
        self.tool.press(P, (80, 0), Ev())
        self.assertAlmostEqual(self.tool.knots[1][1], 8.0)
        self.tool.release(P, (80, 0), Ev())

    def test_handle_is_found_again(self):
        self.drag((50, 0), (50, 7))
        self.drag((50, 7), (50, 3))
        self.assertEqual(len(self.tool.knots), 1)
        self.assertAlmostEqual(self.tool.knots[0][1], 3.0)

    def test_ctrl_moves_along_the_stroke(self):
        self.drag((50, 0), (50, 7))
        self.drag((50, 7), (20, 7), Qt.KeyboardModifier.ControlModifier)
        self.assertAlmostEqual(self.tool.knots[0][0], 0.2)
        self.assertAlmostEqual(self.tool.knots[0][1], 7.0)

    def test_ctrl_past_a_neighbour_stays_in_order(self):
        self.drag((30, 0), (30, 7))
        self.drag((60, 0), (60, 2))
        self.drag((60, 2), (10, 2), Qt.KeyboardModifier.ControlModifier)
        ts = [k[0] for k in self.tool.knots]
        self.assertEqual(ts, sorted(ts))
        self.assertAlmostEqual(self.tool.knots[0][1], 2.0)

    def test_delete_under_the_pointer(self):
        self.drag((50, 0), (50, 7))
        self.tool.move(P, (50, 7), Ev())
        self.assertTrue(self.tool.wants_key(Ev(key=Qt.Key.Key_Delete)))
        self.assertTrue(self.tool.key(Ev(key=Qt.Key.Key_Delete)))
        self.assertEqual(self.tool.knots, [])

    def test_delete_elsewhere_removes_nothing(self):
        self.drag((50, 0), (50, 7))
        self.tool.move(P, (10, 40), Ev())
        self.tool.key(Ev(key=Qt.Key.Key_Delete))
        self.assertEqual(len(self.tool.knots), 1)

    def test_enter_makes_a_filled_band_and_can_be_undone(self):
        self.drag((50, 0), (50, 5))
        before = self.shape.path
        self.assertTrue(self.tool.key(Ev(key=Qt.Key.Key_Return)))
        self.canvas.undo_push.assert_called_once()
        self.assertIsNot(self.shape.path, before)
        self.assertTrue(self.shape.path.contours[0].closed)
        self.assertAlmostEqual(abs(self.shape.path.contours[0].signed_area()), 1000.0, delta=1.0)
        self.assertIsNone(self.tool.item)
        self.canvas.documentChanged.emit.assert_called()

    def test_enter_without_knots_changes_nothing(self):
        self.tool.take(self.shape)
        before = self.shape.path
        self.assertFalse(self.tool.apply())
        self.assertIs(self.shape.path, before)
        self.canvas.undo_push.assert_not_called()

    def test_escape_leaves_the_stroke(self):
        self.drag((50, 0), (50, 5))
        before = self.shape.path
        self.assertTrue(self.tool.key(Ev(key=Qt.Key.Key_Escape)))
        self.assertIs(self.shape.path, before)
        self.assertIsNone(self.tool.item)

    def test_keys_are_left_alone_when_idle(self):
        self.assertFalse(self.tool.wants_key(Ev(key=Qt.Key.Key_Delete)))
        self.assertFalse(self.tool.key(Ev(key=Qt.Key.Key_Delete)))

    def test_double_click_validates(self):
        self.drag((50, 0), (50, 5))
        self.tool.double(P, (50, 5), Ev())
        self.assertTrue(self.shape.path.contours[0].closed)

    def test_handles_follow_a_vertical_stroke(self):
        self.tool.take(line((0, 0), (0, 100)))
        self.tool.knots = [[0.5, 3.0, 1.0]]
        got = {side: q for _n, side, q in self.tool.handles()}
        self.assertAlmostEqual(got['left'][0], -3.0)
        self.assertAlmostEqual(got['right'][0], 1.0)
        self.assertAlmostEqual(got['left'][1], 50.0)

    def test_closed_contour_takes_its_whole_length(self):
        square = line((0, 0), (10, 0), (10, 10), (0, 10), closed=True)
        self.tool.take(square)
        self.assertTrue(self.tool.closed)
        self.assertAlmostEqual(self.tool.along[-1], 1.0)
        t = self.tool.foot((0, 5))[0]
        self.assertAlmostEqual(t, 0.875)

    def test_empty_shape_is_refused(self):
        self.assertFalse(self.tool.take(Shape()))

    def test_zoom_changes_the_reach(self):
        self.drag((50, 0), (50, 7))
        self.canvas.scale = 100.0
        self.assertIsNone(self.tool.handle_at((50, 7.5)))
        self.canvas.scale = 1.0
        self.assertIsNotNone(self.tool.handle_at((50, 7.5)))


class Window(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.canvas.set_tool('select') if hasattr(cls.win.canvas, 'set_tool') else None
        cls.win.close()
        cls.win.deleteLater()

    def setUp(self):
        self.doc = self.win.canvas.doc
        self.layer = Layer(name='Plan 1')
        self.doc.layers[:] = [self.layer]
        self.doc.active = self.layer.id
        self.doc.plate = Plate(width=100.0, height=100.0)
        self.win._undo.clear()

    def test_action_opens_the_tool(self):
        self.assertIn('tool_width', self.win.A)
        self.win.A['tool_width'].trigger()
        self.assertIsInstance(self.win.canvas.tool_obj, T.WidthTool)
        self.win.A['tool_select'].trigger()

    def test_painting_the_tool_does_not_fail(self):
        from PySide6.QtGui import QImage, QPainter
        s = line((10, 10), (90, 10))
        self.layer.items.append(s)
        tool = T.WidthTool(self.win.canvas)
        tool.take(s)
        img = QImage(200, 200, QImage.Format.Format_RGB32)
        p = QPainter(img)
        tool.paint(p)
        tool.knots = [[0.5, 3.0, 1.0]]
        tool.paint(p)
        p.end()

    def test_undo_brings_the_stroke_back(self):
        s = line((10, 10), (90, 10))
        self.layer.items.append(s)
        tool = T.WidthTool(self.win.canvas)
        tool.take(s)
        tool.knots = [[0.5, 3.0, 3.0]]
        self.assertTrue(tool.apply())
        self.win.undo()
        back = self.win.canvas.doc.layers[0].items[0]
        self.assertFalse(back.path.contours[0].closed)

    def test_command_offers_the_new_profiles(self):
        s = line((10, 10), (90, 10))
        self.layer.items.append(s)
        self.win.canvas.select([s])
        new = self.win.var_stroke({'profile': 'goutte', 'w_end': 4.0})
        self.assertEqual(len(new), 1)
        self.assertAlmostEqual(new[0].bbox()[3] - new[0].bbox()[1], 4.0, delta=0.05)


if __name__ == '__main__':
    unittest.main()
