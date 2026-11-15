"""Imbriquer selon la vraie forme : les objets s'emboîtent, jamais plus près que l'écart."""
import itertools
import math
import os
import tempfile
import time
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())

import shapely
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union
from PySide6.QtWidgets import QApplication

from vectordrive.core import nesting as N
from vectordrive.core import nesting_shape as NS
from vectordrive.core import text as TX
from vectordrive.core.document import Group, Layer, Plate, Shape, Text
from vectordrive.core.geom import Affine, Contour, Line, Path, polyline, rect
from vectordrive.ui.main_window import MainWindow

app = QApplication.instance() or QApplication([])


def shape_of(points, closed=True):
    return Shape(path=Path([polyline(points, closed)]))


def ell(size=40.0, arm=10.0, x=0.0, y=0.0):
    """Un L : son rectangle est presque vide."""
    return shape_of([(x, y), (x + size, y), (x + size, y + arm), (x + arm, y + arm), (x + arm, y + size), (x, y + size)])


def square(side=10.0, x=0.0, y=0.0):
    return Shape(path=Path([rect(x, y, side, side)]))


def disc(r=10.0, n=64, x=0.0, y=0.0):
    return shape_of([(x + r * math.cos(i * math.tau / n), y + r * math.sin(i * math.tau / n)) for i in range(n)])


def ring(R=30.0, r=20.0, n=64):
    out = disc(R, n)
    out.path = Path(out.path.contours + disc(r, n).path.contours)
    return out


def geometry(it):
    """Le tracé exact pour vérifier : surface si fermé, trait sinon."""
    if isinstance(it, Group):
        return unary_union([geometry(ch) for ch in it.children])
    path = it.outline if isinstance(it, Text) else it.path
    parts = []
    for c in path.contours:
        pts = [c.segments[0].start]
        for s in c.segments:
            pts.extend(s.flatten(0.01))
        parts.append(Polygon(pts).buffer(0) if c.closed and len(pts) > 3 else LineString(pts))
    return unary_union(parts)


def spec(**kw):
    kw.setdefault('margin', 0.0)
    kw.setdefault('gap', 2.0)
    kw.setdefault('shape', True)
    return N.NestSpec(**kw)


def plate(w=100.0, h=100.0, x=0.0, y=0.0):
    return Plate(x=x, y=y, width=w, height=h)


class TestGuarantees(unittest.TestCase):
    def assertSafe(self, res, gap, pl, margin=0.0, sheet=0):
        placed = res.items()
        geoms = [geometry(it) for it in placed]
        for a, b in itertools.combinations(geoms, 2):
            self.assertGreaterEqual(a.distance(b), gap - 1e-6)
        for g in geoms:
            x0, y0, x1, y1 = g.bounds
            self.assertGreaterEqual(y0, pl.y + margin - 1e-6)
            self.assertLessEqual(y1, pl.y + pl.height - margin + 1e-6)
            self.assertGreaterEqual(x0, pl.x + margin - 1e-6)

    def test_gap_kept_for_various_shapes(self):
        items = [ell(), ell(), ell(30, 8), disc(12), disc(8), square(15), ring(14, 9)]
        pl = plate(150, 150)
        res = N.nest(items, pl, spec(gap=2.0, precision=1.0))
        self.assertEqual(res.plates, 1)
        self.assertEqual(len(res.placed), 7)
        self.assertSafe(res, 2.0, pl)

    def test_gap_tight_with_the_default_precision(self):
        pl = plate(100, 100)
        res = N.nest([square(20), square(20)], pl, spec(gap=2.0, allow_rotate=False))
        a, b = [geometry(it) for it in res.items()]
        self.assertLessEqual(a.distance(b), 2.5 + 1e-6)                                 # au plus une case de plus que l'écart
        self.assertGreaterEqual(a.distance(b), 2.0 - 1e-6)

    def test_gap_kept_with_rough_precision(self):
        items = [ell() for _ in range(5)]
        pl = plate(200, 200)
        res = N.nest(items, pl, spec(gap=1.0, precision=3.0))
        self.assertSafe(res, 1.0, pl)

    def test_gap_kept_with_fine_angles(self):
        items = [ell(30, 8) for _ in range(4)]
        pl = plate(120, 120)
        res = N.nest(items, pl, spec(gap=1.5, precision=1.0, angle_step=30.0))
        self.assertEqual(len(res.placed), 4)
        self.assertSafe(res, 1.5, pl)

    def test_zero_gap_never_overlaps(self):
        items = [square(10) for _ in range(6)]
        pl = plate(50, 50)
        res = N.nest(items, pl, spec(gap=0.0, precision=0.5))
        self.assertEqual(len(res.placed), 6)
        for a, b in itertools.combinations([geometry(it) for it in res.items()], 2):
            self.assertLess(a.intersection(b).area, 1e-6)

    def test_margin_kept(self):
        pl = plate(100, 100)
        res = N.nest([ell(), ell()], pl, spec(margin=5.0, precision=1.0))
        self.assertSafe(res, 2.0, pl, margin=5.0)
        x0, _y0, _x1, y1 = geometry(res.items()[0]).bounds
        self.assertAlmostEqual(x0, 5.0, delta=1e-6)                                     # dans le coin haut gauche
        self.assertAlmostEqual(y1, 95.0, delta=1e-6)

    def test_plate_elsewhere(self):
        pl = plate(100, 100, x=-50, y=30)
        res = N.nest([ell()], pl, spec(margin=5.0))
        x0, _y0, _x1, y1 = geometry(res.items()[0]).bounds
        self.assertAlmostEqual(x0, -45.0, delta=1e-6)
        self.assertAlmostEqual(y1, 125.0, delta=1e-6)

    def test_the_original_is_not_changed(self):
        it = ell()
        before = it.bbox()
        N.nest([it, ell()], plate(), spec())
        self.assertEqual(it.bbox(), before)


class TestInterlocking(unittest.TestCase):
    def test_saves_a_plate_over_rectangles(self):
        items = [ell(40, 10), ell(40, 10)]
        pl = plate(60, 42)                                                              # deux rectangles de 40 × 40 ne tiennent pas
        self.assertEqual(N.nest(items, pl, N.NestSpec(margin=0.0, gap=1.0, allow_rotate=True)).plates, 2)
        res = N.nest(items, pl, spec(gap=1.0, precision=0.25))
        self.assertEqual(res.plates, 1)
        self.assertEqual(res.rotated, 1)                                                # l'un tête-bêche dans l'autre

    def test_fits_more_on_a_plate(self):
        pl = plate(150, 150)
        by_rect = N.nest([ell(50, 8)], pl, N.NestSpec(margin=0.0, gap=1.0, copies=0))
        by_shape = N.nest([ell(50, 8)], pl, spec(gap=1.0, copies=0, precision=1.0))
        self.assertGreater(len(by_shape.placed), len(by_rect.placed))

    def test_without_rotation_keeps_the_angle(self):
        res = N.nest([ell(), ell()], plate(200, 200), spec(allow_rotate=False))
        self.assertEqual(res.rotated, 0)
        for _it, m in res.placed:
            self.assertEqual((m.a, m.b, m.c, m.d), (1.0, 0.0, 0.0, 1.0))

    def test_first_keeps_its_angle_when_equal(self):
        res = N.nest([square(10)], plate(), spec())
        self.assertEqual(res.rotated, 0)

    def test_square_tries_one_pose(self):
        self.assertEqual(len(NS._poses(square(10), spec(), 0.5, 5)), 1)
        self.assertEqual(len(NS._poses(ell(), spec(), 0.5, 5)), 4)
        self.assertEqual(len(NS._poses(ell(), spec(allow_rotate=False), 0.5, 5)), 1)
        self.assertEqual(len(NS._poses(ell(), spec(angle_step=45.0), 0.5, 5)), 8)

    def test_bad_angle_step_falls_back(self):
        for bad in (0.0, -10.0, 1000.0):
            self.assertEqual(len(NS._poses(ell(), spec(angle_step=bad), 0.5, 5)), 4)


class TestHoles(unittest.TestCase):
    def test_small_part_in_the_hole(self):
        pl = plate(64, 64)
        res = N.nest([ring(30, 22), disc(8)], pl, spec(gap=1.0, in_holes=True, precision=0.5))
        self.assertEqual(res.plates, 1)
        self.assertEqual(len(res.placed), 2)
        self.assertEqual(res.unplaced, [])

    def test_holes_not_used_by_default(self):
        pl = plate(64, 64)
        res = N.nest([ring(30, 22), disc(8)], pl, spec(gap=1.0, precision=0.5))
        self.assertEqual(res.plates, 2)

    def test_gap_kept_inside_a_hole(self):
        pl = plate(64, 64)
        res = N.nest([ring(30, 22), disc(8)], pl, spec(gap=1.0, in_holes=True, precision=0.5))
        ring_lines = geometry(res.items()[0])
        small = geometry(res.items()[1])
        self.assertTrue(ring_lines.contains(small) is False or ring_lines.distance(small) >= 0)
        outer = res.items()[0].path.contours
        self.assertGreaterEqual(shapely.distance(Polygon([s.start for s in outer[1].segments]).exterior, small), 1.0 - 1e-6)


class TestItems(unittest.TestCase):
    def test_text(self):
        t = Text(text='LT', font='Arial', size=30.0)
        t.outline = TX.outline_for(t)
        res = N.nest([t], plate(), spec())
        self.assertEqual(len(res.items()), 1)
        self.assertIsInstance(res.items()[0], Text)

    def test_group_moves_as_one(self):
        g = Group(children=[square(10), square(10, 30)])
        res = N.nest([g], plate(), spec())
        moved = res.items()[0]
        a, b = moved.children
        self.assertAlmostEqual(b.bbox()[0] - a.bbox()[0], 30.0, places=6)

    def test_open_line_counts(self):
        line = Shape(path=Path([Contour([Line((0, 0), (40, 0))], False)]))
        pl = plate(100, 100)
        res = N.nest([line, line.transformed(Affine.translation(0, 0)), square(20)], pl, spec(gap=2.0, precision=0.5))
        self.assertEqual(len(res.placed), 3)
        for a, b in itertools.combinations([geometry(it) for it in res.items()], 2):
            self.assertGreaterEqual(a.distance(b), 2.0 - 1e-6)

    def test_empty_item_goes_unplaced(self):
        empty = Shape(path=Path([]))
        res = N.nest([empty, square(10)], plate(), spec())
        self.assertEqual(len(res.placed), 1)
        self.assertIs(res.unplaced[0], empty)


class TestSheets(unittest.TestCase):
    def test_several_plates_side_by_side(self):
        pl = plate(30, 30)
        res = N.nest([square(25) for _ in range(3)], pl, spec())
        self.assertEqual(res.plates, 3)
        xs = sorted(round(it.bbox()[0]) for it in res.items())
        self.assertEqual(xs, [0, round(pl.width + N.PLATE_GAP), round(2 * (pl.width + N.PLATE_GAP))])

    def test_too_big(self):
        big = square(200)
        res = N.nest([big, square(10)], plate(), spec())
        self.assertEqual(len(res.placed), 1)
        self.assertEqual(res.unplaced, [big])
        self.assertEqual(res.plates, 1)

    def test_all_too_big(self):
        res = N.nest([square(200)], plate(), spec())
        self.assertEqual((res.placed, res.plates), ([], 0))

    def test_plate_smaller_than_margins(self):
        it = square(1)
        res = N.nest([it], plate(10, 10), spec(margin=6.0))
        self.assertEqual(res.unplaced, [it])

    def test_copies(self):
        res = N.nest([ell(30, 8)], plate(100, 100), spec(copies=3))
        self.assertEqual(len(res.placed), 3)

    def test_fill_stops_when_full(self):
        res = N.nest([square(20)], plate(103, 103), spec(copies=0, gap=0.0, precision=0.5))
        self.assertEqual(len(res.placed), 25)                                           # une demi-case de jeu par objet
        self.assertEqual(res.plates, 1)
        self.assertGreater(res.usage, 0.9)

    def test_fill_alternates_objects(self):
        a, b = square(30), square(20)
        res = N.nest([a, b], plate(100, 100), spec(copies=0, gap=1.0))
        self.assertTrue(any(it is a for it, _m in res.placed))
        self.assertTrue(any(it is b for it, _m in res.placed))

    def test_usage_reported(self):
        res = N.nest([square(50)], plate(100, 100), spec(gap=0.0, precision=0.5))
        self.assertAlmostEqual(res.usage, 0.25, delta=0.02)

    def test_same_every_time(self):
        items = [ell(), ell(30, 8), disc(9), square(12)]
        a = N.nest(items, plate(120, 120), spec(precision=1.0))
        b = N.nest(items, plate(120, 120), spec(precision=1.0))
        self.assertEqual([m for _i, m in a.placed], [m for _i, m in b.placed])

    def test_precision_limited_on_a_huge_plate(self):
        t0 = time.perf_counter()
        res = N.nest([square(100), square(100)], plate(50000, 50000), spec(precision=0.05))
        self.assertEqual(len(res.placed), 2)
        self.assertLess(time.perf_counter() - t0, 20.0)

    def test_many_parts_in_a_reasonable_time(self):
        t0 = time.perf_counter()
        res = N.nest([ell(20, 5), disc(6), square(9)], plate(300, 200), spec(copies=20, precision=1.0))
        self.assertEqual(len(res.placed), 60)
        self.assertLess(time.perf_counter() - t0, 40.0)


class TestRaster(unittest.TestCase):
    def test_fill_a_square(self):
        pts = [(0, 0), (4, 0), (4, 4), (0, 4)]
        import numpy as np
        m = NS._fill(np.array(pts, float), 0.0, 4.0, 1.0, (4, 4))
        self.assertTrue(m.all())

    def test_fill_a_triangle_top_row_narrow(self):
        import numpy as np
        m = NS._fill(np.array([(0, 0), (4, 0), (0, 4)], float), 0.0, 4.0, 1.0, (4, 4))
        self.assertTrue(m[3, :3].all())                                                 # bas : large
        self.assertLessEqual(int(m[0].sum()), 1)                                        # haut : étroit

    def test_fft_sizes(self):
        for n, want in ((1, 1), (7, 8), (11, 12), (13, 15), (1000, 1000), (1001, 1024)):
            self.assertEqual(NS._next_size(n), want)


class TestWindow(unittest.TestCase):
    def setUp(self):
        self.w = MainWindow()
        self.w.canvas.doc.plate = plate(60, 42)
        self.a, self.b = ell(40, 10), ell(40, 10)
        self.w.canvas.doc.layers[0].items[:] = [self.a, self.b]
        self.w.canvas.select([self.a, self.b])

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_applied_and_undone(self):
        res = self.w.apply_nesting([self.a, self.b], spec(gap=1.0, precision=0.25))
        self.assertEqual(res.plates, 1)
        items = self.w.canvas.doc.layers[0].items
        self.assertEqual(len(items), 2)
        self.assertGreaterEqual(geometry(items[0]).distance(geometry(items[1])), 1.0 - 1e-6)
        self.assertIn('occupation', self.w.statusBar().currentMessage())
        self.w.undo()
        self.assertEqual(self.w.canvas.doc.layers[0].items[0].bbox(), self.a.bbox())


if __name__ == '__main__':
    unittest.main()
