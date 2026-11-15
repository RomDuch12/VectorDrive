"""Round 797 : esquisse contrainte."""
import json
import math
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from vectordrive.core import sketch as SK
from vectordrive.core.document import Shape
from vectordrive.core.geom import Conic, Contour, Line, Path, arc_conics, circle, polyline, rect


def dist(sk, a, b):
    return math.hypot(sk.points[a][0] - sk.points[b][0], sk.points[a][1] - sk.points[b][1])


def line(sk, x0, y0, x1, y1):
    a, b = sk.add_point(x0, y0), sk.add_point(x1, y1)
    return sk.add_line(a, b), a, b


def angle_of(sk, ln):
    v = sk.lines[ln]
    p, q = sk.points[v['p']], sk.points[v['q']]
    return math.atan2(q[1] - p[1], q[0] - p[0])


class TestSolve(unittest.TestCase):
    def test_empty(self):
        rep = SK.Sketch().solve()
        self.assertTrue(rep.ok)
        self.assertEqual(rep.dof, 0)

    def test_free_point(self):
        s = SK.Sketch()
        s.add_point(1, 2)
        self.assertEqual(s.solve().dof, 2)

    def test_horizontal(self):
        s = SK.Sketch()
        ln, a, b = line(s, 0, 0, 10, 1)
        s.add_constraint('horizontal', ln)
        rep = s.solve()
        self.assertTrue(rep.ok)
        self.assertAlmostEqual(s.points[a][1], s.points[b][1], places=7)
        self.assertEqual(rep.dof, 3)

    def test_least_motion(self):
        s = SK.Sketch()
        ln, a, b = line(s, 0, 0, 10, 1)
        s.add_constraint('horizontal', ln)
        s.solve()
        self.assertAlmostEqual(s.points[a][1], 0.5, places=6)
        self.assertAlmostEqual(s.points[a][0], 0.0, places=6)

    def test_vertical(self):
        s = SK.Sketch()
        ln, a, b = line(s, 0, 0, 1, 10)
        s.add_constraint('vertical', ln)
        self.assertTrue(s.solve().ok)
        self.assertAlmostEqual(s.points[a][0], s.points[b][0], places=7)

    def test_coincident_merges(self):
        s = SK.Sketch()
        a, b = s.add_point(0, 0), s.add_point(1, 1)
        s.add_constraint('coincident', a, b)
        self.assertTrue(s.solve().ok)
        self.assertAlmostEqual(dist(s, a, b), 0, places=7)

    def test_distance(self):
        s = SK.Sketch()
        a, b = s.add_point(0, 0), s.add_point(3, 4)
        s.add_constraint('distance', a, b, value=10.0)
        self.assertTrue(s.solve().ok)
        self.assertAlmostEqual(dist(s, a, b), 10, places=6)

    def test_length(self):
        s = SK.Sketch()
        ln, a, b = line(s, 0, 0, 3, 0)
        s.add_constraint('length', ln, value=40.0)
        self.assertTrue(s.solve().ok)
        self.assertAlmostEqual(dist(s, a, b), 40, places=6)

    def test_distance_x_keeps_the_side(self):
        s = SK.Sketch()
        a, b = s.add_point(10, 0), s.add_point(2, 0)
        s.add_constraint('distance_x', a, b, value=20.0)
        self.assertTrue(s.solve().ok)
        self.assertAlmostEqual(s.points[a][0] - s.points[b][0], 20, places=6)

    def test_distance_y(self):
        s = SK.Sketch()
        a, b = s.add_point(0, 1), s.add_point(0, 2)
        s.add_constraint('distance_y', a, b, value=7.0)
        self.assertTrue(s.solve().ok)
        self.assertAlmostEqual(s.points[b][1] - s.points[a][1], 7, places=6)

    def test_parallel(self):
        s = SK.Sketch()
        a = line(s, 0, 0, 10, 0)[0]
        b = line(s, 0, 5, 10, 8)[0]
        s.add_constraint('parallel', a, b)
        self.assertTrue(s.solve().ok)
        self.assertAlmostEqual(math.sin(angle_of(s, a) - angle_of(s, b)), 0, places=6)

    def test_perpendicular(self):
        s = SK.Sketch()
        a = line(s, 0, 0, 10, 0)[0]
        b = line(s, 0, 5, 9, 8)[0]
        s.add_constraint('perpendicular', a, b)
        self.assertTrue(s.solve().ok)
        self.assertAlmostEqual(math.cos(angle_of(s, a) - angle_of(s, b)), 0, places=6)

    def test_collinear(self):
        s = SK.Sketch()
        a, *_ = line(s, 0, 0, 10, 0)
        b, c, d = line(s, 20, 3, 30, 5)
        s.add_constraint('collinear', a, b)
        self.assertTrue(s.solve().ok)
        for p in (c, d):
            v = s.lines[a]
            P, Q = s.points[v['p']], s.points[v['q']]
            R = s.points[p]
            self.assertAlmostEqual((Q[0] - P[0]) * (R[1] - P[1]) - (Q[1] - P[1]) * (R[0] - P[0]), 0, places=5)

    def test_equal_lines(self):
        s = SK.Sketch()
        a, p, q = line(s, 0, 0, 10, 0)
        b, u, v = line(s, 0, 5, 3, 5)
        s.add_constraint('equal_ll', a, b)
        self.assertTrue(s.solve().ok)
        self.assertAlmostEqual(dist(s, p, q), dist(s, u, v), places=6)

    def test_radius_and_diameter(self):
        s = SK.Sketch()
        c = s.add_circle(s.add_point(0, 0), 3)
        d = s.add_circle(s.add_point(9, 0), 3)
        s.add_constraint('radius', c, value=5.0)
        s.add_constraint('diameter', d, value=5.0)
        self.assertTrue(s.solve().ok)
        self.assertAlmostEqual(s.circles[c]['r'], 5, places=6)
        self.assertAlmostEqual(s.circles[d]['r'], 2.5, places=6)

    def test_equal_circles(self):
        s = SK.Sketch()
        c, d = s.add_circle(s.add_point(0, 0), 3), s.add_circle(s.add_point(9, 0), 5)
        s.add_constraint('equal_cc', c, d)
        self.assertTrue(s.solve().ok)
        self.assertAlmostEqual(s.circles[c]['r'], s.circles[d]['r'], places=6)

    def test_concentric(self):
        s = SK.Sketch()
        c, d = s.add_circle(s.add_point(0, 0), 3), s.add_circle(s.add_point(1, 1), 5)
        s.add_constraint('concentric', c, d)
        self.assertTrue(s.solve().ok)
        self.assertAlmostEqual(dist(s, s.circles[c]['c'], s.circles[d]['c']), 0, places=6)

    def test_tangent_line_circle(self):
        s = SK.Sketch()
        ln, *_ = line(s, -20, 7, 20, 7)
        c = s.add_circle(s.add_point(0, 0), 5)
        s.add_constraint('tangent_lc', ln, c)
        self.assertTrue(s.solve().ok)
        g = SK._Reader(s, *s._vector())
        self.assertAlmostEqual(abs(g.side(s.circles[c]['c'], ln)), s.circles[c]['r'], places=6)

    def test_tangent_circles_outside(self):
        s = SK.Sketch()
        c, d = s.add_circle(s.add_point(0, 0), 5), s.add_circle(s.add_point(12, 0), 5)
        s.add_constraint('tangent_cc', c, d)
        self.assertTrue(s.solve().ok)
        self.assertAlmostEqual(dist(s, s.circles[c]['c'], s.circles[d]['c']), s.circles[c]['r'] + s.circles[d]['r'], places=6)

    def test_tangent_circles_inside(self):
        s = SK.Sketch()
        c, d = s.add_circle(s.add_point(0, 0), 10), s.add_circle(s.add_point(1, 0), 3)
        s.add_constraint('tangent_cc', c, d)
        self.assertTrue(s.solve().ok)
        self.assertAlmostEqual(dist(s, s.circles[c]['c'], s.circles[d]['c']), s.circles[c]['r'] - s.circles[d]['r'], places=6)

    def test_midpoint(self):
        s = SK.Sketch()
        ln, a, b = line(s, 0, 0, 10, 0)
        m = s.add_point(3, 2)
        s.add_constraint('midpoint', m, ln)
        self.assertTrue(s.solve().ok)
        self.assertAlmostEqual(dist(s, m, a), dist(s, m, b), places=6)

    def test_symmetric(self):
        s = SK.Sketch()
        axis, u, v = line(s, 0, -10, 0, 10)
        s.add_constraint('fix', u)
        s.add_constraint('fix', v)
        a, b = s.add_point(-4, 1), s.add_point(5, 2)
        s.add_constraint('symmetric', a, b, axis)
        self.assertTrue(s.solve().ok)
        self.assertAlmostEqual(s.points[a][1], s.points[b][1], places=5)
        self.assertAlmostEqual(s.points[a][0], -s.points[b][0], places=5)

    def test_on_line_and_circle(self):
        s = SK.Sketch()
        ln, *_ = line(s, 0, 0, 10, 0)
        p = s.add_point(5, 3)
        s.add_constraint('on_line', p, ln)
        c = s.add_circle(s.add_point(0, 20), 5)
        q = s.add_point(1, 21)
        s.add_constraint('on_circle', q, c)
        self.assertTrue(s.solve().ok)
        self.assertAlmostEqual(dist(s, q, s.circles[c]['c']), s.circles[c]['r'], places=6)

    def test_point_line_distance(self):
        s = SK.Sketch()
        ln, *_ = line(s, 0, 0, 10, 0)
        p = s.add_point(5, 3)
        s.add_constraint('point_line', p, ln, value=8.0)
        self.assertTrue(s.solve().ok)
        g = SK._Reader(s, *s._vector())
        self.assertAlmostEqual(abs(g.side(p, ln)), 8, places=6)

    def test_angle(self):
        s = SK.Sketch()
        a, *_ = line(s, 0, 0, 10, 0)
        b, *_ = line(s, 0, 0, 10, 2)
        s.add_constraint('angle', a, b, value=30.0)
        self.assertTrue(s.solve().ok)
        self.assertAlmostEqual(math.degrees(angle_of(s, b) - angle_of(s, a)), 30, places=5)

    def test_fix(self):
        s = SK.Sketch()
        ln, a, b = line(s, 0, 0, 10, 0)
        s.add_constraint('fix', a)
        s.add_constraint('length', ln, value=20.0)
        self.assertTrue(s.solve().ok)
        self.assertEqual([round(v, 6) for v in s.points[a]], [0, 0])

    def test_arc_ends_stay_on_it(self):
        s = SK.Sketch()
        c = s.add_point(0, 0)
        a, b = s.add_point(10, 0), s.add_point(0, 10)
        k = s.add_arc(c, a, b)
        s.add_constraint('radius', k, value=20.0)
        self.assertTrue(s.solve().ok)
        self.assertAlmostEqual(dist(s, a, c), 20, places=6)
        self.assertAlmostEqual(dist(s, b, c), 20, places=6)


class TestWhole(unittest.TestCase):
    def fully(self):
        s = SK.Sketch()
        ls = s.add_rect(1, 2, 31, 22)
        p0 = s.lines[ls[0]]['p']
        s.add_constraint('fix', p0)
        s.add_constraint('length', ls[0], value=40.0)
        s.add_constraint('length', ls[1], value=25.0)
        return s, ls, p0

    def test_rect_dimensions(self):
        s, ls, p0 = self.fully()
        rep = s.solve()
        self.assertTrue(rep.ok)
        self.assertEqual(rep.dof, 0)
        self.assertTrue(rep.complete)
        box = s.to_path().bbox()
        self.assertAlmostEqual(box[2] - box[0], 40, places=5)
        self.assertAlmostEqual(box[3] - box[1], 25, places=5)

    def test_rect_alone_has_four_free(self):
        s = SK.Sketch()
        s.add_rect(0, 0, 10, 10)
        rep = s.solve()
        self.assertEqual(rep.dof, 4)

    def test_change_a_dimension(self):
        s, ls, p0 = self.fully()
        s.solve()
        next(c for c in s.constraints if c.kind == 'length' and c.refs == (ls[0],)).value = 100.0
        self.assertTrue(s.solve().ok)
        box = s.to_path().bbox()
        self.assertAlmostEqual(box[2] - box[0], 100, places=5)
        self.assertAlmostEqual(box[3] - box[1], 25, places=5)

    def test_big_jump(self):
        s, ls, p0 = self.fully()
        s.solve()
        next(c for c in s.constraints if c.kind == 'length' and c.refs == (ls[0],)).value = 5000.0
        self.assertTrue(s.solve().ok)
        box = s.to_path().bbox()
        self.assertAlmostEqual(box[2] - box[0], 5000, places=4)

    def test_conflict_leaves_the_drawing_alone(self):
        s = SK.Sketch()
        ln, a, b = line(s, 0, 0, 10, 0)
        s.add_constraint('length', ln, value=10.0)
        before = {k: list(v) for k, v in s.points.items()}
        d = s.add_constraint('length', ln, value=20.0)
        rep = s.solve()
        self.assertFalse(rep.ok)
        self.assertEqual(s.points, before)
        self.assertIn(d.id, rep.conflicts)

    def test_conflict_names_the_culprits(self):
        s = SK.Sketch()
        ln, a, b = line(s, 0, 0, 10, 0)
        h = s.add_constraint('horizontal', ln)
        v = s.add_constraint('vertical', ln)
        d = s.add_constraint('length', ln, value=10.0)
        rep = s.solve()
        self.assertFalse(rep.ok)
        self.assertIn(d.id, rep.conflicts)
        self.assertIn(h.id, rep.conflicts)
        self.assertIn(v.id, rep.conflicts)

    def test_redundant_is_said(self):
        s = SK.Sketch()
        ln, a, b = line(s, 0, 0, 10, 0)
        s.add_constraint('horizontal', ln)
        again = s.add_constraint('h_points', a, b)
        rep = s.solve()
        self.assertTrue(rep.ok)
        self.assertEqual(rep.redundant, [again.id])

    def test_rectangle_with_four_right_angles_is_redundant(self):
        s = SK.Sketch()
        pts = [s.add_point(x, y) for x, y in ((0, 0), (10, 1), (10, 8), (0, 9))]
        ls = [s.add_line(pts[i], pts[(i + 1) % 4]) for i in range(4)]
        for i in range(4):
            s.add_constraint('perpendicular', ls[i], ls[(i + 1) % 4])
        rep = s.solve()
        self.assertTrue(rep.ok)
        self.assertEqual(len(rep.redundant), 1)

    def test_free_points_listed(self):
        s = SK.Sketch()
        ln, a, b = line(s, 0, 0, 10, 0)
        s.add_constraint('fix', a)
        rep = s.solve()
        self.assertNotIn(a, rep.free_points)
        self.assertIn(b, rep.free_points)

    def test_tangent_arc_to_line_profile(self):
        """Un profil en U : deux traits, un arc tangent."""
        s = SK.Sketch()
        p1, p2 = s.add_point(0, 30), s.add_point(0, 0)
        p3, p4 = s.add_point(20, 0), s.add_point(20, 30)
        c = s.add_point(10, 0)
        l1, l2 = s.add_line(p1, p2), s.add_line(p3, p4)
        k = s.add_arc(c, p2, p3, ccw=True)
        s.add_constraint('tangent_lc', l1, k)
        s.add_constraint('tangent_lc', l2, k)
        s.add_constraint('vertical', l1)
        s.add_constraint('vertical', l2)
        s.add_constraint('equal_ll', l1, l2)
        s.add_constraint('radius', k, value=15.0)
        self.assertTrue(s.solve().ok)
        self.assertAlmostEqual(s.points[p3][0] - s.points[p2][0], 30, places=4)
        self.assertEqual(len(s.to_path().contours), 1)

    def test_triangle_from_three_sides(self):
        s = SK.Sketch()
        a, b, c = s.add_point(0, 0), s.add_point(10, 0), s.add_point(3, 5)
        x, y, z = s.add_line(a, b), s.add_line(b, c), s.add_line(c, a)
        s.add_constraint('fix', a)
        s.add_constraint('horizontal', x)
        s.add_constraint('length', x, value=30.0)
        s.add_constraint('length', y, value=40.0)
        s.add_constraint('length', z, value=50.0)
        rep = s.solve()
        self.assertTrue(rep.ok)
        self.assertEqual(rep.dof, 0)
        self.assertAlmostEqual(dist(s, c, a), 50, places=5)
        self.assertAlmostEqual(dist(s, c, b), 40, places=5)

    def test_impossible_triangle(self):
        s = SK.Sketch()
        a, b, c = s.add_point(0, 0), s.add_point(10, 0), s.add_point(3, 5)
        x, y, z = s.add_line(a, b), s.add_line(b, c), s.add_line(c, a)
        s.add_constraint('length', x, value=10.0)
        s.add_constraint('length', y, value=10.0)
        s.add_constraint('length', z, value=100.0)
        self.assertFalse(s.solve().ok)

    def test_radius_cannot_vanish(self):
        s = SK.Sketch()
        c = s.add_circle(s.add_point(0, 0), 5)
        s.add_constraint('radius', c, value=-3.0)
        self.assertFalse(s.solve().ok)
        self.assertEqual(s.circles[c]['r'], 5)

    def test_skip(self):
        s = SK.Sketch()
        ln, a, b = line(s, 0, 0, 10, 0)
        s.add_constraint('length', ln, value=10.0)
        d = s.add_constraint('length', ln, value=20.0)
        self.assertTrue(s.solve(skip=(d.id,)).ok)

    def test_value_of(self):
        s = SK.Sketch()
        ln, a, b = line(s, 0, 0, 10, 0)
        probe = SK.Constraint(99, 'length', (ln,), 0.0)
        self.assertAlmostEqual(s.value_of(probe), 10)
        m, *_ = line(s, 0, 0, 0, 10)
        self.assertAlmostEqual(s.value_of(SK.Constraint(98, 'angle', (ln, m), 0.0)), 90)


class TestDrag(unittest.TestCase):
    def test_free_point_follows(self):
        s = SK.Sketch()
        a = s.add_point(0, 0)
        self.assertTrue(s.solve(hold={a: (5, 6)}).ok)
        self.assertEqual([round(v, 6) for v in s.points[a]], [5, 6])

    def test_slides_along_its_line(self):
        s = SK.Sketch()
        ln, a, b = line(s, 0, 0, 10, 0)
        s.add_constraint('fix', a)
        s.add_constraint('horizontal', ln)
        self.assertTrue(s.solve(hold={b: (30, 9)}).ok)
        self.assertAlmostEqual(s.points[b][0], 30, places=5)
        self.assertAlmostEqual(s.points[b][1], 0, places=5)

    def test_fixed_does_not_move(self):
        s = SK.Sketch()
        a = s.add_point(1, 2)
        s.add_constraint('fix', a)
        self.assertTrue(s.solve(hold={a: (50, 50)}).ok)
        self.assertEqual([round(v, 6) for v in s.points[a]], [1, 2])

    def test_on_a_length_turns_around(self):
        s = SK.Sketch()
        ln, a, b = line(s, 0, 0, 10, 0)
        s.add_constraint('fix', a)
        s.add_constraint('length', ln, value=10.0)
        self.assertTrue(s.solve(hold={b: (0, 30)}).ok)
        self.assertAlmostEqual(dist(s, a, b), 10, places=5)
        self.assertGreater(s.points[b][1], 9)

    def test_rectangle_keeps_its_right_angles(self):
        s = SK.Sketch()
        ls = s.add_rect(0, 0, 10, 10)
        p = s.lines[ls[1]]['q']
        self.assertTrue(s.solve(hold={p: (25, 18)}).ok)
        box = s.to_path().bbox()
        self.assertAlmostEqual(box[3] - box[1], 18, places=4)
        self.assertAlmostEqual(box[2] - box[0], 25, places=4)


class TestEdit(unittest.TestCase):
    def test_remove_constraint(self):
        s = SK.Sketch()
        ln, *_ = line(s, 0, 0, 10, 0)
        c = s.add_constraint('horizontal', ln)
        s.remove(c.id)
        self.assertEqual(s.constraints, [])
        self.assertIn(ln, s.lines)

    def test_remove_line_drops_lone_points(self):
        s = SK.Sketch()
        ln, a, b = line(s, 0, 0, 10, 0)
        s.remove(ln)
        self.assertEqual(s.points, {})

    def test_shared_point_stays(self):
        s = SK.Sketch()
        a, b, c = s.add_point(0, 0), s.add_point(1, 0), s.add_point(2, 0)
        x, y = s.add_line(a, b), s.add_line(b, c)
        s.remove(x)
        self.assertNotIn(a, s.points)
        self.assertIn(b, s.points)

    def test_remove_point_takes_its_lines(self):
        s = SK.Sketch()
        ln, a, b = line(s, 0, 0, 10, 0)
        c = s.add_constraint('horizontal', ln)
        s.remove(a)
        self.assertEqual(s.lines, {})
        self.assertNotIn(c, s.constraints)

    def test_remove_circle_takes_its_center(self):
        s = SK.Sketch()
        c = s.add_circle(s.add_point(0, 0), 3)
        s.remove(c)
        self.assertEqual(s.points, {})

    def test_bad_constraint_refused(self):
        s = SK.Sketch()
        with self.assertRaises(ValueError):
            s.add_constraint('horizontal', 123)
        with self.assertRaises(ValueError):
            s.add_constraint('nothing', 1)

    def test_round_trip_is_json(self):
        s = SK.Sketch()
        ls = s.add_rect(0, 0, 10, 10)
        k = s.add_arc(s.add_point(0, 0), s.add_point(5, 0), s.add_point(0, 5), ccw=False, construction=True)
        s.add_constraint('length', ls[0], value=10.0)
        s.add_constraint('fix', s.lines[ls[0]]['p'])
        back = SK.Sketch.from_dict(json.loads(json.dumps(s.to_dict())))
        self.assertEqual(back.to_dict(), s.to_dict())
        self.assertFalse(back.circles[k]['ccw'])
        self.assertTrue(back.solve().ok)

    def test_new_ids_after_reload(self):
        s = SK.Sketch()
        a = s.add_point(0, 0)
        back = SK.Sketch.from_dict(s.to_dict())
        self.assertNotEqual(back.add_point(1, 1), a)

    def test_copy_is_separate(self):
        s = SK.Sketch()
        a = s.add_point(0, 0)
        c = s.copy()
        c.points[a][0] = 9
        self.assertEqual(s.points[a][0], 0)


class TestPath(unittest.TestCase):
    def test_closed_rect(self):
        s = SK.Sketch()
        s.add_rect(0, 0, 10, 5)
        got = s.to_path()
        self.assertEqual(len(got.contours), 1)
        self.assertTrue(got.contours[0].closed)

    def test_open_chain(self):
        s = SK.Sketch()
        a, b, c = s.add_point(0, 0), s.add_point(1, 0), s.add_point(1, 1)
        s.add_line(a, b)
        s.add_line(b, c)
        got = s.to_path()
        self.assertEqual(len(got.contours), 1)
        self.assertFalse(got.contours[0].closed)
        self.assertEqual(len(got.contours[0].segments), 2)

    def test_chain_from_the_middle_of_the_list(self):
        s = SK.Sketch()
        a, b, c, d = s.add_point(0, 0), s.add_point(1, 0), s.add_point(1, 1), s.add_point(0, 1)
        s.add_line(b, c)
        s.add_line(c, d)
        s.add_line(a, b)
        got = s.to_path()
        self.assertEqual(len(got.contours), 1)
        self.assertEqual(len(got.contours[0].segments), 3)

    def test_lines_in_opposite_directions_chain(self):
        s = SK.Sketch()
        a, b, c = s.add_point(0, 0), s.add_point(5, 0), s.add_point(9, 0)
        s.add_line(a, b)
        s.add_line(c, b)
        got = s.to_path()
        self.assertEqual(len(got.contours), 1)
        segs = got.contours[0].segments
        for u, v in zip(segs, segs[1:]):
            self.assertEqual(u.end, v.start)

    def test_coincident_points_join(self):
        s = SK.Sketch()
        a, b, c, d = s.add_point(0, 0), s.add_point(5, 0), s.add_point(5, 0), s.add_point(5, 5)
        s.add_line(a, b)
        s.add_line(c, d)
        s.add_constraint('coincident', b, c)
        self.assertEqual(len(s.to_path().contours), 1)

    def test_construction_left_out(self):
        s = SK.Sketch()
        a, b = s.add_point(0, 0), s.add_point(1, 0)
        s.add_line(a, b, construction=True)
        s.add_circle(a, 3, construction=True)
        self.assertEqual(s.to_path().contours, [])

    def test_circle(self):
        s = SK.Sketch()
        s.add_circle(s.add_point(2, 3), 4)
        got = s.to_path()
        self.assertAlmostEqual(got.bbox()[2], 6, places=5)
        self.assertTrue(got.contours[0].closed)

    def test_arc_direction(self):
        s = SK.Sketch()
        s.add_arc(s.add_point(0, 0), s.add_point(10, 0), s.add_point(0, 10), ccw=True)
        box = s.to_path().bbox()
        self.assertAlmostEqual(box[0], 0, places=5)
        self.assertAlmostEqual(box[2], 10, places=5)
        t = SK.Sketch()
        t.add_arc(t.add_point(0, 0), t.add_point(10, 0), t.add_point(0, 10), ccw=False)
        box = t.to_path().bbox()
        self.assertAlmostEqual(box[0], -10, places=5)
        self.assertAlmostEqual(box[1], -10, places=5)

    def test_arc_walked_backward(self):
        s = SK.Sketch()
        c, a, b, d = s.add_point(0, 0), s.add_point(10, 0), s.add_point(0, 10), s.add_point(-5, 10)
        s.add_line(d, b)
        s.add_arc(c, a, b)
        got = s.to_path()
        self.assertEqual(len(got.contours), 1)
        segs = got.contours[0].segments
        for u, v in zip(segs, segs[1:]):
            self.assertAlmostEqual(u.end[0], v.start[0], places=6)
            self.assertAlmostEqual(u.end[1], v.start[1], places=6)
        self.assertAlmostEqual(segs[-1].end[0], 10, places=5)

    def test_closed_with_an_arc(self):
        s = SK.Sketch()
        c, a, b = s.add_point(0, 0), s.add_point(10, 0), s.add_point(0, 10)
        s.add_line(c, a)
        s.add_arc(c, a, b)
        s.add_line(b, c)
        got = s.to_path()
        self.assertEqual(len(got.contours), 1)
        self.assertTrue(got.contours[0].closed)

    def test_junction_gives_several_contours(self):
        s = SK.Sketch()
        o = s.add_point(0, 0)
        for x, y in ((1, 0), (-1, 0), (0, 1)):
            s.add_line(o, s.add_point(x, y))
        got = s.to_path()
        total = sum(len(c.segments) for c in got.contours)
        self.assertEqual(total, 3)


class TestFromPath(unittest.TestCase):
    def test_rect(self):
        s, ignored = SK.from_path(Path([rect(0, 0, 10, 5)]))
        self.assertEqual((len(s.lines), len(s.points), ignored), (4, 4, 0))
        self.assertTrue(s.to_path().contours[0].closed)

    def test_polyline(self):
        s, _i = SK.from_path(Path([polyline([(0, 0), (1, 0), (1, 1)])]))
        self.assertEqual(len(s.lines), 2)

    def test_circle(self):
        s, ignored = SK.from_path(Path([circle((3, 4), 5)]))
        self.assertEqual((len(s.circles), len(s.lines), ignored), (1, 0, 0))
        k = next(iter(s.circles.values()))
        self.assertAlmostEqual(k['r'], 5, places=6)
        self.assertAlmostEqual(s.points[k['c']][0], 3, places=6)
        self.assertAlmostEqual(s.points[k['c']][1], 4, places=6)

    def test_arc_merged(self):
        s, ignored = SK.from_path(Path([Contour(arc_conics((0, 0), 10, 10, 0, 200), False)]))
        self.assertEqual((len(s.circles), ignored), (1, 0))
        k = next(iter(s.circles.values()))
        self.assertTrue(k['ccw'])
        self.assertIsNotNone(k['a'])

    def test_arc_clockwise(self):
        s, _i = SK.from_path(Path([Contour(arc_conics((0, 0), 10, 10, 90, -60), False)]))
        self.assertFalse(next(iter(s.circles.values()))['ccw'])

    def test_rounded_rect(self):
        s, ignored = SK.from_path(Path([rect(0, 0, 40, 20, r=5)]))
        self.assertEqual((len(s.lines), len(s.circles), ignored), (4, 4, 0))
        back = s.to_path()
        self.assertEqual(len(back.contours), 1)
        self.assertTrue(back.contours[0].closed)
        box = back.bbox()
        self.assertAlmostEqual(box[2], 40, places=5)
        self.assertAlmostEqual(box[3], 20, places=5)

    def test_same_shape_after_the_trip(self):
        src = Path([rect(0, 0, 40, 20, r=5)])
        s, _i = SK.from_path(src)
        self.assertTrue(s.solve().ok)
        a, b = src.bbox(), s.to_path().bbox()
        for u, v in zip(a, b):
            self.assertAlmostEqual(u, v, places=5)

    def test_ellipse_not_taken(self):
        s, ignored = SK.from_path(Path([Contour(arc_conics((0, 0), 10, 5, 0, 90), False)]))
        self.assertEqual(len(s.circles), 0)
        self.assertGreater(ignored, 0)

    def test_two_contours_touching_share_a_point(self):
        s, _i = SK.from_path(Path([polyline([(0, 0), (1, 0)]), polyline([(1, 0), (2, 0)])]))
        self.assertEqual(len(s.points), 3)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def editor(self, sketch=None, ignored=0):
        from vectordrive.ui.sketch_editor import SketchEditor
        ed = SketchEditor(None, sketch, ignored)
        ed.resize(1100, 760)
        ed.show()
        self.app.processEvents()
        ed.view.k, ed.view.ox, ed.view.oy = 4.0, 60.0, 500.0
        self.addCleanup(ed.deleteLater)
        return ed

    def click(self, ed, x, y, button=Qt.MouseButton.LeftButton, mods=Qt.KeyboardModifier.NoModifier):
        p = ed.view.to_screen(x, y)
        QTest.mouseClick(ed.view, button, mods, QPoint(round(p.x()), round(p.y())))

    def drag(self, ed, a, b):
        pa, pb = ed.view.to_screen(*a), ed.view.to_screen(*b)
        qa, qb = QPoint(round(pa.x()), round(pa.y())), QPoint(round(pb.x()), round(pb.y()))
        QTest.mousePress(ed.view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, qa)
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtCore import QEvent
        ev = QMouseEvent(QEvent.Type.MouseMove, QPointF(qb), QPointF(qb), Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.NoModifier)
        ed.view.mouseMoveEvent(ev)
        QTest.mouseRelease(ed.view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, qb)


class TestDraw(Base):
    def test_opens_empty(self):
        ed = self.editor()
        self.assertEqual(ed.sketch.points, {})
        self.assertIn('vide', ed.status.text())

    def test_line_chain(self):
        ed = self.editor()
        ed.set_tool('line')
        ed.auto_box.setChecked(False)
        for x, y in ((0, 0), (30, 7), (60, 30)):
            self.click(ed, x, y)
        self.assertEqual(len(ed.sketch.lines), 2)
        self.assertEqual(len(ed.sketch.points), 3)

    def test_chain_closes_on_first_point(self):
        ed = self.editor()
        ed.set_tool('line')
        ed.auto_box.setChecked(False)
        for x, y in ((0, 0), (30, 3), (20, 30), (0, 0)):
            self.click(ed, x, y)
        self.assertEqual((len(ed.sketch.lines), len(ed.sketch.points)), (3, 3))
        self.assertTrue(ed.sketch.to_path().contours[0].closed)

    def test_auto_horizontal(self):
        ed = self.editor()
        ed.set_tool('line')
        self.click(ed, 0, 0)
        self.click(ed, 50, 1)
        self.assertEqual([c.kind for c in ed.sketch.constraints], ['horizontal'])

    def test_auto_vertical(self):
        ed = self.editor()
        ed.set_tool('line')
        self.click(ed, 0, 0)
        self.click(ed, 1, 50)
        self.assertEqual([c.kind for c in ed.sketch.constraints], ['vertical'])

    def test_no_auto_when_off(self):
        ed = self.editor()
        ed.auto_box.setChecked(False)
        ed.set_tool('line')
        self.click(ed, 0, 0)
        self.click(ed, 50, 1)
        self.assertEqual(ed.sketch.constraints, [])

    def test_slanted_stays_free(self):
        ed = self.editor()
        ed.set_tool('line')
        self.click(ed, 0, 0)
        self.click(ed, 50, 30)
        self.assertEqual(ed.sketch.constraints, [])

    def test_escape_ends_the_chain(self):
        ed = self.editor()
        ed.set_tool('line')
        self.click(ed, 0, 0)
        QTest.keyClick(ed.view, Qt.Key.Key_Escape)
        self.assertEqual(ed.view.clicks, [])
        self.assertEqual(ed.view.tool, 'line')
        QTest.keyClick(ed.view, Qt.Key.Key_Escape)
        self.assertEqual(ed.view.tool, 'select')

    def test_escape_never_closes(self):
        ed = self.editor()
        QTest.keyClick(ed, Qt.Key.Key_Escape)
        self.assertTrue(ed.isVisible())

    def test_right_click_ends_the_chain(self):
        ed = self.editor()
        ed.set_tool('line')
        self.click(ed, 0, 0)
        self.click(ed, 10, 10, Qt.MouseButton.RightButton)
        self.assertEqual(ed.view.clicks, [])

    def test_rect(self):
        ed = self.editor()
        ed.set_tool('rect')
        self.click(ed, 0, 0)
        self.click(ed, 40, 20)
        self.assertEqual(len(ed.sketch.lines), 4)
        self.assertEqual(sorted(c.kind for c in ed.sketch.constraints), ['horizontal'] * 2 + ['vertical'] * 2)

    def test_circle(self):
        ed = self.editor()
        ed.set_tool('circle')
        self.click(ed, 10, 10)
        self.click(ed, 30, 10)
        v = next(iter(ed.sketch.circles.values()))
        self.assertAlmostEqual(v['r'], 20, delta=0.5)

    def test_arc(self):
        ed = self.editor()
        ed.set_tool('arc')
        self.click(ed, 0, 0)
        self.click(ed, 20, 0)
        self.click(ed, 0, 25)
        v = next(iter(ed.sketch.circles.values()))
        self.assertTrue(v['ccw'])
        self.assertAlmostEqual(ed.sketch.points[v['b']][1], 20, delta=0.5)

    def test_arc_clockwise(self):
        ed = self.editor()
        ed.set_tool('arc')
        self.click(ed, 0, 0)
        self.click(ed, 20, 0)
        self.click(ed, 0, -20)
        self.assertFalse(next(iter(ed.sketch.circles.values()))['ccw'])

    def test_construction(self):
        ed = self.editor()
        ed.construction_box.setChecked(True)
        ed.set_tool('line')
        self.click(ed, 0, 0)
        self.click(ed, 30, 30)
        self.assertTrue(next(iter(ed.sketch.lines.values()))['construction'])

    def test_toggle_construction(self):
        s = SK.Sketch()
        ln = s.add_line(s.add_point(0, 0), s.add_point(9, 9))
        ed = self.editor(s)
        ed.view.selected = [ln]
        ed.toggle_construction()
        self.assertTrue(ed.sketch.lines[ln]['construction'])

    def test_paints_without_error(self):
        s = SK.Sketch()
        ls = s.add_rect(0, 0, 40, 20)
        c = s.add_circle(s.add_point(20, 10), 5)
        s.add_arc(s.add_point(0, 40), s.add_point(10, 40), s.add_point(0, 50), construction=True)
        s.add_constraint('length', ls[0], value=40.0)
        s.add_constraint('radius', c, value=5.0)
        s.add_constraint('fix', s.lines[ls[0]]['p'])
        ed = self.editor(s)
        ed.set_tool('rect')
        self.click(ed, 1, 1)
        ed.view.grab()
        self.assertTrue(ed.view.labels)


class TestRules(Base):
    def line(self, *pts):
        s = SK.Sketch()
        return s, s.add_line(s.add_point(*pts[:2]), s.add_point(*pts[2:]))

    def test_buttons_follow_the_selection(self):
        s, ln = self.line(0, 0, 10, 2)
        ed = self.editor(s)
        self.assertFalse(ed.rule_buttons['horizontal'].isEnabled())
        ed.view.selected = [ln]
        ed.selection_changed()
        self.assertTrue(ed.rule_buttons['horizontal'].isEnabled())
        self.assertFalse(ed.rule_buttons['tangent'].isEnabled())
        self.assertTrue(ed.dim_buttons['auto'].isEnabled())
        self.assertFalse(ed.dim_buttons['diameter'].isEnabled())

    def test_horizontal(self):
        s, ln = self.line(0, 0, 10, 2)
        ed = self.editor(s)
        ed.view.selected = [ln]
        self.assertTrue(ed.apply_rule('horizontal').ok)
        v = ed.sketch.lines[ln]
        self.assertAlmostEqual(ed.sketch.points[v['p']][1], ed.sketch.points[v['q']][1], places=6)

    def test_each_rule_builds_the_right_constraint(self):
        s = SK.Sketch()
        p1, p2 = s.add_point(0, 0), s.add_point(5, 5)
        l1 = s.add_line(s.add_point(0, 10), s.add_point(10, 11))
        l2 = s.add_line(s.add_point(0, 20), s.add_point(10, 22))
        c1, c2 = s.add_circle(s.add_point(50, 0), 3), s.add_circle(s.add_point(60, 0), 4)
        ed = self.editor(s)
        for sel, rule, kinds in (([p1, p2], 'coincident', ['coincident']), ([p1, l1], 'coincident', ['on_line']),
                                 ([p1, c1], 'coincident', ['on_circle']), ([l1, l2], 'horizontal', ['horizontal', 'horizontal']),
                                 ([p1, p2], 'vertical', ['v_points']), ([l1, l2], 'parallel', ['parallel']),
                                 ([l1, l2], 'perpendicular', ['perpendicular']), ([l1, l2], 'collinear', ['collinear']),
                                 ([l1, c1], 'tangent', ['tangent_lc']), ([c1, c2], 'tangent', ['tangent_cc']),
                                 ([l1, l2], 'equal', ['equal_ll']), ([c1, c2], 'equal', ['equal_cc']),
                                 ([c1, c2], 'concentric', ['concentric']), ([p1, l1], 'midpoint', ['midpoint']),
                                 ([p1, p2, l1], 'symmetric', ['symmetric']), ([p1], 'fix', ['fix']), ([l1], 'fix', ['fix', 'fix'])):
            ed.view.selected = sel
            self.assertEqual([r[0] for r in ed._rule_refs(rule)], kinds, rule)

    def test_refused_when_it_contradicts(self):
        s = SK.Sketch()
        a, b = s.add_point(0, 0), s.add_point(10, 0)
        ln = s.add_line(a, b)
        s.add_constraint('fix', a)
        s.add_constraint('fix', b)
        ed = self.editor(s)
        ed.view.selected = [ln]
        rep = ed.add_dimension('auto', 50.0)
        self.assertFalse(rep.ok)
        self.assertEqual(len(ed.sketch.constraints), 2)
        self.assertEqual(ed.sketch.points[b], [10, 0])
        self.assertIn('Refusé', ed.status.text())
        self.assertTrue(ed.shown_constraints)

    def test_refused_leaves_no_undo(self):
        s = SK.Sketch()
        a, b = s.add_point(0, 0), s.add_point(10, 0)
        ln = s.add_line(a, b)
        s.add_constraint('fix', a)
        s.add_constraint('fix', b)
        ed = self.editor(s)
        ed.view.selected = [ln]
        ed.add_dimension('auto', 50.0)
        self.assertEqual(ed.undo_stack, [])

    def test_redundant_marked_in_the_list(self):
        s, ln = self.line(0, 0, 10, 0)
        s.add_constraint('horizontal', ln)
        v = s.lines[ln]
        ed = self.editor(s)
        ed.view.selected = [v['p'], v['q']]
        self.assertTrue(ed.apply_rule('horizontal').ok)
        self.assertIn('de trop', ed.listing.item(1).text())
        self.assertIn('de trop', ed.status.text())

    def test_status_counts_what_is_free(self):
        s, ln = self.line(0, 0, 10, 0)
        ed = self.editor(s)
        self.assertIn('4', ed.status.text())

    def test_status_complete(self):
        s, ln = self.line(0, 0, 10, 0)
        s.add_constraint('fix', s.lines[ln]['p'])
        s.add_constraint('fix', s.lines[ln]['q'])
        self.assertIn('Entièrement', self.editor(s).status.text())


class TestDimensions(Base):
    def test_length(self):
        s = SK.Sketch()
        a, b = s.add_point(0, 0), s.add_point(10, 0)
        ln = s.add_line(a, b)
        ed = self.editor(s)
        ed.view.selected = [ln]
        self.assertTrue(ed.add_dimension('auto', 40.0).ok)
        self.assertAlmostEqual(abs(ed.sketch.points[a][0] - ed.sketch.points[b][0]), 40, places=5)

    def test_asks_with_the_current_value(self):
        s = SK.Sketch()
        ln = s.add_line(s.add_point(0, 0), s.add_point(10, 0))
        ed = self.editor(s)
        ed.view.selected = [ln]
        with mock.patch.object(ed, 'ask_value', return_value=None) as ask:
            self.assertIsNone(ed.add_dimension('auto'))
        self.assertEqual(ask.call_args[0][1], 10)
        self.assertEqual(ed.sketch.constraints, [])

    def test_kinds(self):
        s = SK.Sketch()
        p, q = s.add_point(0, 0), s.add_point(3, 4)
        l1 = s.add_line(s.add_point(10, 0), s.add_point(20, 0))
        l2 = s.add_line(s.add_point(10, 5), s.add_point(20, 8))
        c = s.add_circle(s.add_point(50, 0), 3)
        ed = self.editor(s)
        for sel, rule, kind in (([l1], 'auto', 'length'), ([c], 'auto', 'radius'), ([c], 'diameter', 'diameter'),
                                ([p, q], 'auto', 'distance'), ([p, l1], 'auto', 'point_line'), ([l1, l2], 'auto', 'angle'),
                                ([p, q], 'distance_x', 'distance_x'), ([p, q], 'distance_y', 'distance_y')):
            ed.view.selected = sel
            self.assertEqual(ed._dim_kind(rule)[0], kind)

    def test_edit_value(self):
        s = SK.Sketch()
        a, b = s.add_point(0, 0), s.add_point(10, 0)
        ln = s.add_line(a, b)
        c = s.add_constraint('length', ln, value=10.0)
        ed = self.editor(s)
        self.assertTrue(ed.edit_value(ed.sketch.constraints[0], 25.0).ok)
        self.assertAlmostEqual(abs(ed.sketch.points[a][0] - ed.sketch.points[b][0]), 25, places=5)
        self.assertEqual(ed.sketch.constraints[0].id, c.id)

    def test_edit_refused_restores(self):
        s = SK.Sketch()
        a, b = s.add_point(0, 0), s.add_point(10, 0)
        ln = s.add_line(a, b)
        s.add_constraint('fix', a)
        s.add_constraint('horizontal', ln)
        c = s.add_constraint('distance_x', a, b, value=10.0)
        s.add_constraint('fix', b)
        ed = self.editor(s)
        self.assertFalse(ed.edit_value(next(o for o in ed.sketch.constraints if o.id == c.id), 30.0).ok)
        self.assertEqual(next(o for o in ed.sketch.constraints if o.id == c.id).value, 10.0)

    def test_double_click_on_a_value(self):
        s = SK.Sketch()
        ln = s.add_line(s.add_point(0, 0), s.add_point(40, 0))
        s.add_constraint('length', ln, value=40.0)
        ed = self.editor(s)
        ed.view.grab()
        box, c = ed.view.labels[0]
        with mock.patch.object(ed, 'ask_value', return_value=60.0):
            QTest.mouseDClick(ed.view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, box.center().toPoint())
        self.assertEqual(ed.sketch.constraints[0].value, 60.0)

    def test_list_edit_value(self):
        s = SK.Sketch()
        ln = s.add_line(s.add_point(0, 0), s.add_point(40, 0))
        s.add_constraint('length', ln, value=40.0)
        ed = self.editor(s)
        self.assertEqual(ed.constraint_of(ed.listing.item(0)).kind, 'length')
        self.assertIn('40', ed.listing.item(0).text())


class TestMouse(Base):
    def test_select(self):
        s = SK.Sketch()
        ln = s.add_line(s.add_point(0, 0), s.add_point(40, 0))
        ed = self.editor(s)
        self.click(ed, 20, 0)
        self.assertEqual(ed.view.selected, [ln])

    def test_ctrl_adds(self):
        s = SK.Sketch()
        a, b = s.add_point(0, 0), s.add_point(40, 0)
        ed = self.editor(s)
        self.click(ed, 0, 0)
        self.click(ed, 40, 0, mods=Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(ed.view.selected, [a, b])

    def test_click_in_the_void_clears(self):
        s = SK.Sketch()
        s.add_point(0, 0)
        ed = self.editor(s)
        self.click(ed, 0, 0)
        self.click(ed, 50, 50)
        self.assertEqual(ed.view.selected, [])

    def test_hit_on_arc_only_on_its_part(self):
        s = SK.Sketch()
        k = s.add_arc(s.add_point(0, 0), s.add_point(30, 0), s.add_point(0, 30))
        ed = self.editor(s)
        p = ed.view.to_screen(-30, 0)
        self.assertIsNone(ed.view.entity_at(p))
        q = ed.view.to_screen(21.2, 21.2)
        self.assertEqual(ed.view.entity_at(q), k)

    def test_hit_on_clockwise_arc(self):
        s = SK.Sketch()
        k = s.add_arc(s.add_point(0, 0), s.add_point(30, 0), s.add_point(0, 30), ccw=False)
        ed = self.editor(s)
        self.assertEqual(ed.view.entity_at(ed.view.to_screen(-30, 0)), k)
        self.assertIsNone(ed.view.entity_at(ed.view.to_screen(21.2, 21.2)))

    def test_drag_point(self):
        s = SK.Sketch()
        a, b = s.add_point(0, 0), s.add_point(40, 0)
        ln = s.add_line(a, b)
        s.add_constraint('horizontal', ln)
        s.add_constraint('fix', a)
        ed = self.editor(s)
        self.drag(ed, (40, 0), (60, 25))
        self.assertAlmostEqual(ed.sketch.points[b][0], 60, delta=0.5)
        self.assertAlmostEqual(ed.sketch.points[b][1], 0, places=5)
        self.assertEqual(len(ed.undo_stack), 1)

    def test_drag_line_moves_both_ends(self):
        s = SK.Sketch()
        a, b = s.add_point(0, 0), s.add_point(40, 0)
        s.add_line(a, b)
        ed = self.editor(s)
        self.drag(ed, (20, 0), (20, 30))
        self.assertAlmostEqual(ed.sketch.points[a][1], 30, delta=0.5)
        self.assertAlmostEqual(ed.sketch.points[b][1], 30, delta=0.5)

    def test_drag_circle_changes_its_radius(self):
        s = SK.Sketch()
        k = s.add_circle(s.add_point(0, 0), 20)
        ed = self.editor(s)
        self.drag(ed, (20, 0), (35, 0))
        self.assertAlmostEqual(ed.sketch.circles[k]['r'], 35, delta=0.5)

    def test_drag_fixed_radius_does_not_change_it(self):
        s = SK.Sketch()
        k = s.add_circle(s.add_point(0, 0), 20)
        s.add_constraint('radius', k, value=20.0)
        ed = self.editor(s)
        self.drag(ed, (20, 0), (35, 0))
        self.assertAlmostEqual(ed.sketch.circles[k]['r'], 20, places=5)

    def test_wheel_and_pan_keep_the_point_under_the_mouse(self):
        from PySide6.QtCore import QPointF
        ed = self.editor()
        ev = mock.Mock()
        ev.position.return_value = QPointF(200, 200)
        ev.angleDelta.return_value = QPoint(0, 120)
        before = ed.view.to_doc(QPointF(200, 200))
        ed.view.wheelEvent(ev)
        after = ed.view.to_doc(QPointF(200, 200))
        self.assertAlmostEqual(before[0], after[0], places=6)
        self.assertAlmostEqual(before[1], after[1], places=6)

    def test_fit(self):
        s = SK.Sketch()
        s.add_rect(1000, 1000, 1100, 1050)
        ed = self.editor(s)
        ed.view.fit()
        p = ed.view.to_screen(1050, 1025)
        self.assertAlmostEqual(p.x(), ed.view.width() / 2, delta=2)
        self.assertAlmostEqual(p.y(), ed.view.height() / 2, delta=2)


class TestUndo(Base):
    def test_undo_redo(self):
        s = SK.Sketch()
        ln = s.add_line(s.add_point(0, 0), s.add_point(10, 3))
        ed = self.editor(s)
        ed.view.selected = [ln]
        ed.apply_rule('horizontal')
        ed.undo()
        self.assertEqual(ed.sketch.constraints, [])
        ed.redo()
        self.assertEqual(len(ed.sketch.constraints), 1)

    def test_delete_selection(self):
        s = SK.Sketch()
        ln = s.add_line(s.add_point(0, 0), s.add_point(10, 3))
        ed = self.editor(s)
        ed.view.selected = [ln]
        ed.delete_selection()
        self.assertEqual(ed.sketch.lines, {})
        ed.undo()
        self.assertEqual(len(ed.sketch.lines), 1)

    def test_delete_constraint_from_the_list(self):
        s = SK.Sketch()
        ln = s.add_line(s.add_point(0, 0), s.add_point(10, 0))
        s.add_constraint('horizontal', ln)
        ed = self.editor(s)
        ed.listing.setCurrentRow(0)
        ed.delete_selection()
        self.assertEqual(ed.sketch.constraints, [])
        self.assertIn(ln, ed.sketch.lines)

    def test_original_untouched_when_cancelled(self):
        s = SK.Sketch()
        ln = s.add_line(s.add_point(0, 0), s.add_point(10, 3))
        ed = self.editor(s)
        ed.view.selected = [ln]
        ed.apply_rule('horizontal')
        self.assertEqual(s.constraints, [])

    def test_empty_refused(self):
        from vectordrive.ui import sketch_editor as M
        ed = self.editor()
        with mock.patch.object(M.QMessageBox, 'information') as box:
            ed.finish()
        box.assert_called_once()
        self.assertEqual(ed.result(), 0)

    def test_says_what_was_left_out(self):
        self.assertIn('2', self.editor(ignored=2).status.text())


class TestWindow(Base):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()

    def items(self):
        return self.w.canvas.doc.layers[0].items

    def put(self, *items):
        self.items()[:] = list(items)
        self.w.canvas.invalidate()
        self.w.canvas.select(list(items))

    def run_editor(self, change=None, accept=True):
        from vectordrive.ui import sketch_editor as M

        def fake(dlg):
            if change:
                change(dlg)
            return 1 if accept else 0
        return mock.patch.object(M.SketchEditor, 'exec', fake)

    def test_action(self):
        self.assertIn('sketch_edit', self.w.A)

    def test_new(self):
        def draw(d):
            d.sketch.add_rect(0, 0, 40, 20)
        self.w.canvas.select([])
        with self.run_editor(draw):
            got = self.w.sketch_edit()
        self.assertIn(got, self.items())
        self.assertIn('sketch', got.extra)
        box = got.bbox()
        self.assertAlmostEqual(box[2], 40, places=5)

    def test_cancel_adds_nothing(self):
        self.w.canvas.select([])
        with self.run_editor(lambda d: d.sketch.add_rect(0, 0, 40, 20), accept=False):
            self.assertIsNone(self.w.sketch_edit())
        self.assertEqual(self.items(), [])

    def test_from_selection_replaces_it(self):
        a = Shape(path=Path([rect(0, 0, 40, 20, r=4)]))
        self.put(a)
        with self.run_editor():
            got = self.w.sketch_edit()
        self.assertEqual(self.items(), [got])
        self.w.undo()
        self.assertEqual(len(self.items()), 1)
        self.assertNotIn('sketch', self.items()[0].extra)

    def test_curves_only_refused(self):
        from vectordrive.core.geom import Contour, Cubic
        from vectordrive.ui import main_window as M
        a = Shape(path=Path([Contour([Cubic((0, 0), (1, 5), (5, 5), (6, 0))], False)]))
        self.put(a)
        with mock.patch.object(M.QMessageBox, 'information') as box:
            self.assertIsNone(self.w.sketch_edit())
        box.assert_called_once()

    def test_double_click_edits(self):
        with self.run_editor(lambda d: d.sketch.add_rect(0, 0, 40, 20)):
            self.w.canvas.select([])
            got = self.w.sketch_edit()

        def wider(d):
            ln = next(iter(d.sketch.lines))
            d.sketch.add_constraint('length', ln, value=100.0)
            d.sketch.solve()
        with self.run_editor(wider):
            self.w._item_double_clicked(got)
        new = self.items()[0]
        self.assertIsNot(new, got)
        self.assertAlmostEqual(new.bbox()[2] - new.bbox()[0], 100, delta=0.01)
        self.w.undo()
        self.assertAlmostEqual(self.items()[0].bbox()[2] - self.items()[0].bbox()[0], 40, delta=0.01)

    def test_moved_keeps_its_place(self):
        from vectordrive.core.geom import Affine
        with self.run_editor(lambda d: d.sketch.add_rect(0, 0, 40, 20)):
            self.w.canvas.select([])
            got = self.w.sketch_edit()
        got.path = got.path.transformed(Affine.translation(100, 50))
        with self.run_editor():
            new = self.w.edit_sketch(got)
        self.assertAlmostEqual(new.bbox()[0], 100, places=5)
        self.assertAlmostEqual(new.bbox()[1], 50, places=5)
        with self.run_editor():
            again = self.w.edit_sketch(new)
        self.assertAlmostEqual(again.bbox()[0], 100, places=5)

    def test_moved_with_a_fixed_point(self):
        from vectordrive.core.geom import Affine

        def draw(d):
            ls = d.sketch.add_rect(0, 0, 40, 20)
            d.sketch.add_constraint('fix', d.sketch.lines[ls[0]]['p'])
        with self.run_editor(draw):
            self.w.canvas.select([])
            got = self.w.sketch_edit()
        got.path = got.path.transformed(Affine.translation(100, 50))
        with self.run_editor():
            new = self.w.edit_sketch(got)
        with self.run_editor():
            again = self.w.edit_sketch(new)
        self.assertAlmostEqual(again.bbox()[0], 100, places=5)
        self.assertAlmostEqual(again.bbox()[1], 50, places=5)

    def test_scaled_is_said(self):
        from vectordrive.core.geom import Affine
        with self.run_editor(lambda d: d.sketch.add_rect(0, 0, 40, 20)):
            self.w.canvas.select([])
            got = self.w.sketch_edit()
        got.path = got.path.transformed(Affine.scaling(2, 2))
        seen = {}

        def look(d):
            seen['text'] = d.status.text()
        with self.run_editor(look, accept=False):
            self.w.edit_sketch(got)
        self.assertIn('échelle', seen['text'])

    def test_saved_in_the_native_file(self):
        from vectordrive.core.document import Document
        from vectordrive.io import native
        with self.run_editor(lambda d: d.sketch.add_rect(0, 0, 40, 20)):
            self.w.canvas.select([])
            self.w.sketch_edit()
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, 'a.vdz')
            native.write(self.w.canvas.doc, f)
            back = native.read(f)
        self.assertIsInstance(back, Document)
        sk = SK.Sketch.from_dict(back.layers[0].items[0].extra['sketch'])
        self.assertEqual(len(sk.lines), 4)


if __name__ == '__main__':
    unittest.main()
