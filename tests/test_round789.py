"""Round 789 : l'imbrication selon la forme reprend le jeu de sa grille."""
import copy
import math
import time
import unittest
from unittest import mock

import shapely
from shapely import affinity
from shapely.geometry import Polygon

from vectordrive.core import nesting as N
from vectordrive.core import nesting_shape as NS
from vectordrive.core import nesting_tight as NT
from vectordrive.core.document import Group, Plate, Shape
from vectordrive.core.geom import Path, circle, polyline, rect


def square(side=20.0):
    return Shape(path=Path([rect(0, 0, side, side)]))


def ell(a=40.0, b=10.0):
    return Shape(path=Path([polyline([(0, 0), (a, 0), (a, b), (b, b), (b, a), (0, a)], True)]))


def disc(r=10.0):
    return Shape(path=Path([circle((0, 0), r)]))


def ring(r=30.0, hole=20.0):
    return Shape(path=Path([circle((0, 0), r), circle((0, 0), hole)]))


def spec(**kw):
    base = dict(margin=3.0, gap=2.0, shape=True, allow_rotate=False, precision=1.0)
    base.update(kw)
    return N.NestSpec(**base)


def geometry(it, m, in_holes=False):
    return affinity.affine_transform(NT._piece(it, in_holes), [m.a, m.c, m.b, m.d, m.e, m.f])


def placed(res, in_holes=False):
    return [geometry(it, m, in_holes) for it, m in res.placed]


def closest(res, in_holes=False):
    gs = placed(res, in_holes)
    return min(gs[i].distance(gs[j]) for i in range(len(gs)) for j in range(i + 1, len(gs)))


def nest(items, plate=None, **kw):
    return N.nest(items, plate or Plate(x=0, y=0, width=200, height=150), spec(**kw))


class TestGapIsExact(unittest.TestCase):
    def test_two_squares_end_up_at_the_gap(self):
        res = nest([square(), square()])
        self.assertAlmostEqual(closest(res), 2.0, delta=0.05)

    def test_without_tightening_they_stay_further(self):
        res = nest([square(), square()], tighten=False)
        self.assertGreater(closest(res), 2.5)

    def test_never_closer_than_the_gap(self):
        for gap in (0.5, 1.0, 2.0, 5.0):
            res = nest([square(30), ell(), disc(), square(15), ell(30, 8), disc(6)], gap=gap)
            self.assertEqual(res.unplaced, [])
            self.assertGreaterEqual(closest(res), gap - 1e-6)

    def test_gap_zero_never_overlaps(self):
        res = nest([square(30), square(30), ell()], gap=0.0)
        gs = placed(res)
        for i in range(len(gs)):
            for j in range(i + 1, len(gs)):
                self.assertLess(gs[i].intersection(gs[j]).area, 1e-6)

    def test_true_curves_keep_the_gap(self):
        res = nest([disc(), disc(), disc()], gap=1.0)
        centres = [(m.e, m.f) for _it, m in res.placed]
        for i in range(3):
            for j in range(i + 1, 3):
                self.assertGreaterEqual(math.dist(centres[i], centres[j]), 21.0 - 1e-6)

    def test_rotated_pieces(self):
        res = nest([ell(), ell(), ell()], allow_rotate=True, angle_step=30.0)
        self.assertGreaterEqual(closest(res), 2.0 - 1e-6)

    def test_finer_than_the_grid_alone(self):
        items = [ell(), ell(), square(25), disc(12), square(12), disc(8)]
        loose = nest(items, tighten=False)
        tight = nest(items)

        def height(res):
            return max(g.bounds[3] for g in placed(res)) - min(g.bounds[1] for g in placed(res))
        self.assertLess(height(tight), height(loose) + 1e-9)


class TestPlate(unittest.TestCase):
    def test_stays_inside_the_margin(self):
        for corner in N.CORNERS:
            res = nest([square(30), ell(), disc(), square(20)], corner=corner)
            for g in placed(res):
                b = g.bounds
                self.assertGreaterEqual(b[0], 3.0 - 1e-6)
                self.assertGreaterEqual(b[1], 3.0 - 1e-6)
                self.assertLessEqual(b[2], 197.0 + 1e-6)
                self.assertLessEqual(b[3], 147.0 + 1e-6)

    def test_slides_toward_the_chosen_corner(self):
        for corner, xs, ys in (('haut_gauche', 3.0, 147.0), ('bas_droit', 197.0, 3.0)):
            res = nest([square(), square()], corner=corner)
            gs = placed(res)
            xedge = min(g.bounds[0] for g in gs) if xs < 100 else max(g.bounds[2] for g in gs)
            yedge = max(g.bounds[3] for g in gs) if ys > 100 else min(g.bounds[1] for g in gs)
            self.assertAlmostEqual(xedge, xs, delta=1e-6)
            self.assertAlmostEqual(yedge, ys, delta=1e-6)

    def test_rows_and_columns(self):
        res = nest([square(), square()])
        gs = placed(res)
        self.assertAlmostEqual(gs[0].bounds[3], gs[1].bounds[3], delta=1e-6)     # en rangée
        res = nest([square(), square()], vertical=True)
        gs = placed(res)
        self.assertAlmostEqual(gs[0].bounds[0], gs[1].bounds[0], delta=1e-6)     # en colonne

    def test_several_plates_stay_on_their_plate(self):
        plate = Plate(x=0, y=0, width=50, height=50)
        res = N.nest([square(40), square(40), square(40)], plate, spec())
        self.assertEqual(res.plates, 3)
        for (it, m), k in zip(res.placed, res.sheets):
            b = geometry(it, m).bounds
            left = k * (50 + N.PLATE_GAP)
            self.assertGreaterEqual(b[0], left + 3.0 - 1e-6)
            self.assertLessEqual(b[2], left + 47.0 + 1e-6)

    def test_same_item_many_copies(self):
        res = nest([square(10)], copies=12)
        self.assertEqual(len(res.placed), 12)
        self.assertGreaterEqual(closest(res), 2.0 - 1e-6)

    def test_fill(self):
        res = nest([square(30)], copies=0)
        self.assertGreater(len(res.placed), 10)
        self.assertGreaterEqual(closest(res), 2.0 - 1e-6)

    def test_open_lines_count(self):
        line = Shape(path=Path([polyline([(0, 0), (50, 0)], False)]))
        res = nest([line, line, square()], copies=1)
        self.assertGreaterEqual(closest(res), 2.0 - 1e-6)

    def test_group_of_shapes(self):
        grp = Group(children=[square(10), Shape(path=Path([rect(20, 0, 10, 10)]))])
        res = nest([grp, grp], copies=1)
        self.assertGreaterEqual(closest(res), 2.0 - 1e-6)

    def test_results_transform_real_items(self):
        res = nest([square(), square()])
        boxes = [it.bbox() for it in res.items()]
        self.assertAlmostEqual(boxes[1][0] - boxes[0][2], 2.0, delta=0.05)

    def test_original_items_not_touched(self):
        a = square()
        before = copy.deepcopy(a.path)
        nest([a, square()])
        self.assertEqual(a.path.bbox(), before.bbox())


class TestHoles(unittest.TestCase):
    def test_piece_in_a_hole_keeps_the_gap(self):
        # plaque juste assez large : la seule place plus haute que sous l'anneau est son trou
        res = nest([ring(), disc(8)], Plate(x=0, y=0, width=66, height=130), in_holes=True)
        gs = placed(res, in_holes=True)
        self.assertEqual(len(gs), 2)
        outer = gs[0]
        inner = gs[1]
        self.assertTrue(outer.convex_hull.contains(inner))                       # dans le trou
        self.assertGreaterEqual(outer.distance(inner), 2.0 - 1e-6)

    def test_holes_stay_full_without_the_option(self):
        res = nest([ring(), disc(8)])
        gs = placed(res)
        self.assertFalse(gs[0].convex_hull.contains(gs[1]))


class TestRegion(unittest.TestCase):
    REGION = Path([rect(0, 0, 100, 60)])

    def test_stays_in_the_shape_with_its_margin(self):
        res = N.nest([square(20), square(20), disc(8)], Plate(x=0, y=0, width=1, height=1),
                     spec(region=self.REGION, margin=4.0))
        limit = Polygon([(0, 0), (100, 0), (100, 60), (0, 60)])
        for g in placed(res):
            self.assertTrue(limit.contains(g))
            self.assertGreaterEqual(limit.boundary.distance(g), 4.0 - 1e-6)

    def test_gets_closer_than_the_grid(self):
        items = [square(20), square(20)]
        plate = Plate(x=0, y=0, width=1, height=1)
        tight = N.nest(items, plate, spec(region=self.REGION))
        self.assertAlmostEqual(closest(tight), 2.0, delta=0.05)

    def test_non_rectangular_shape_is_respected(self):
        tri = Path([polyline([(0, 0), (120, 0), (0, 120)], True)])
        res = N.nest([square(20), square(20), square(20)], Plate(x=0, y=0, width=1, height=1), spec(region=tri, margin=1.0))
        limit = Polygon([(0, 0), (120, 0), (0, 120)])
        for g in placed(res):
            self.assertTrue(limit.contains(g))


class TestLimits(unittest.TestCase):
    def test_too_many_pieces_keep_the_grid(self):
        with mock.patch.object(NT, 'MAX_PIECES', 3):
            res = nest([square(10)], copies=4)
        self.assertGreater(closest(res), 2.5)

    def test_budget_stops_cleanly(self):
        with mock.patch.object(NT, 'MAX_TESTS', 10):
            res = nest([square(10)], copies=10)
        self.assertEqual(len(res.placed), 10)
        self.assertGreaterEqual(closest(res), 2.0 - 1e-6)

    def test_geometry_error_keeps_the_grid(self):
        err = shapely.errors.GEOSException('non')
        with mock.patch.object(NT, '_piece', side_effect=err):
            res = nest([square(), square()])
        self.assertEqual(len(res.placed), 2)
        self.assertGreater(res.placed[1][1].e, 0)

    def test_empty_nest(self):
        res = nest([], copies=1)
        self.assertEqual(res.placed, [])

    def test_time_stays_reasonable(self):
        t = time.time()
        res = nest([disc(6)], copies=0, plate=Plate(x=0, y=0, width=300, height=200), precision=1.0)
        self.assertLess(time.time() - t, 60)
        self.assertGreater(len(res.placed), 50)
        self.assertGreaterEqual(closest(res), 2.0 - 1e-6)

    def test_rectangles_unchanged(self):
        res = N.nest([square(), square()], Plate(x=0, y=0, width=200, height=150), spec(shape=False))
        self.assertEqual(len(res.placed), 2)

    def test_option_off_gives_the_grid(self):
        with mock.patch.object(NT, 'tighten') as called:
            nest([square(), square()], tighten=False)
        called.assert_not_called()


if __name__ == '__main__':
    unittest.main()
