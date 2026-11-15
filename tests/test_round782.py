"""Round 782 : enveloppe par quatre courbes, grille de déformation du relief."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())

import numpy as np
from PySide6.QtWidgets import QApplication, QMessageBox

from vectordrive.core import coons as CO, envelope as EN, galbe as GB
from vectordrive.core.document import Group, Layer, Shape, Text
from vectordrive.core.geom import Contour, Cubic, Line, Path, circle, polyline, rect


def line(a, b):
    return Contour([Line(a, b)], False)


def box_lines(x=0.0, y=0.0, w=100.0, h=20.0):
    return [line((x, y), (x + w, y)), line((x + w, y), (x + w, y + h)),
            line((x + w, y + h), (x, y + h)), line((x, y + h), (x, y))]


def ends(side):
    return tuple(np.round(side[0], 6)), tuple(np.round(side[-1], 6))


class Sides(unittest.TestCase):
    def _check_box(self, sides):
        self.assertEqual(ends(sides[0]), ((0.0, 0.0), (100.0, 0.0)))
        self.assertEqual(ends(sides[1]), ((100.0, 0.0), (100.0, 20.0)))
        self.assertEqual(ends(sides[2]), ((100.0, 20.0), (0.0, 20.0)))
        self.assertEqual(ends(sides[3]), ((0.0, 20.0), (0.0, 0.0)))

    def test_four_curves(self):
        self._check_box(CO.sides_of(box_lines()))

    def test_any_order_and_direction(self):
        a, b, c, d = box_lines()
        self._check_box(CO.sides_of([c, a.reversed(), d, b.reversed()]))

    def test_clockwise_becomes_direct(self):
        self._check_box(CO.sides_of([c.reversed() for c in reversed(box_lines())]))

    def test_small_gap_accepted(self):
        a, b, c, d = box_lines()
        d = line((0.05, 20.0), (0.05, 0.1))
        self.assertEqual(len(CO.sides_of([a, b, c, d])), 4)

    def test_gap_refused(self):
        a, b, c, d = box_lines()
        with self.assertRaises(CO.EnvelopeError):
            CO.sides_of([a, b, c, line((5, 18), (5, 3))])

    def test_wrong_count(self):
        for parts in (box_lines()[:3], box_lines() + [line((0, 0), (1, 1))], []):
            with self.assertRaises(CO.EnvelopeError):
                CO.sides_of(parts)

    def test_one_open_curve_refused(self):
        with self.assertRaises(CO.EnvelopeError):
            CO.sides_of([line((0, 0), (10, 0))])

    def test_flat_refused(self):
        with self.assertRaises(CO.EnvelopeError):
            CO.sides_of([line((0, 0), (10, 0)), line((10, 0), (20, 0)), line((20, 0), (10, 0)), line((10, 0), (0, 0))])

    def test_closed_rectangle(self):
        self._check_box(CO.sides_of([rect(0, 0, 100, 20)]))

    def test_closed_quadrilateral(self):
        s = CO.sides_of([polyline([(0, 0), (100, 10), (90, 50), (5, 40)], True)])
        self.assertEqual(ends(s[0]), ((0.0, 0.0), (100.0, 10.0)))
        self.assertEqual(ends(s[2]), ((90.0, 50.0), (5.0, 40.0)))

    def test_closed_contour_with_more_corners(self):
        p = [(0, 0), (50, -5), (100, 0), (105, 25), (100, 50), (50, 55), (0, 50), (-5, 25)]
        s = CO.sides_of([polyline(p, True)])
        self.assertEqual(len(s), 4)
        self.assertEqual(ends(s[0])[0], (0.0, 0.0))
        self.assertEqual(ends(s[0])[1], (100.0, 0.0))

    def test_circle(self):
        s = CO.sides_of([circle((0, 0), 10)])
        self.assertEqual(len(s), 4)
        total = sum(CO._length(p) for p in s)
        self.assertAlmostEqual(total, 2 * np.pi * 10, places=1)
        self.assertLess(abs(CO._length(s[0]) - CO._length(s[1])), 0.5)

    def test_rounded_rectangle(self):
        s = CO.sides_of([rect(0, 0, 100, 20, 3)])
        self.assertGreater(CO._length(s[0]), 80)
        self.assertLess(CO._length(s[1]), 25)

    def test_curved_side_kept(self):
        a, b, c, d = box_lines()
        curved = Contour([Cubic((0, 0), (30, -20), (70, -20), (100, 0))], False)
        s = CO.sides_of([curved, b, c, d])
        self.assertAlmostEqual(float(s[0][:, 1].min()), -15.0, places=1)


class PatchMap(unittest.TestCase):
    def test_reaches_the_four_sides(self):
        a, b, c, d = box_lines()
        curved = Contour([Cubic((0, 0), (30, -20), (70, -20), (100, 0))], False)
        p = CO.Patch(CO.sides_of([curved, b, c, d]))
        self.assertAlmostEqual(p.point(0.5, 0.0)[1], -15.0, places=2)
        self.assertAlmostEqual(p.point(0.5, 1.0)[1], 20.0, places=6)
        self.assertAlmostEqual(p.point(0.0, 0.5)[0], 0.0, places=6)
        self.assertAlmostEqual(p.point(1.0, 0.5)[0], 100.0, places=6)

    def test_flat_box_is_identity(self):
        p = CO.Patch(CO.sides_of(box_lines()))
        x, y = p.point(0.25, 0.75)
        self.assertAlmostEqual(x, 25.0)
        self.assertAlmostEqual(y, 15.0)

    def test_grid_matches_point(self):
        a, b, c, d = box_lines()
        curved = Contour([Cubic((0, 0), (30, -20), (70, -20), (100, 0))], False)
        p = CO.Patch(CO.sides_of([curved, b, c, d]))
        X, Y = p.grid(np.array([0.1, 0.6]), np.array([0.2, 0.9]))
        self.assertEqual(X.shape, (2, 2))
        self.assertAlmostEqual(X[1, 0], p.point(0.1, 0.9)[0], places=9)
        self.assertAlmostEqual(Y[0, 1], p.point(0.6, 0.2)[1], places=9)

    def test_turn(self):
        s = CO.sides_of(box_lines())
        x, y = CO.Patch(s, 1).point(0.0, 0.0)
        self.assertEqual((round(x, 6), round(y, 6)), (100.0, 0.0))
        self.assertEqual(tuple(round(v, 6) for v in CO.Patch(s, 2).point(0.0, 0.0)), (100.0, 20.0))
        self.assertEqual(tuple(round(v, 6) for v in CO.Patch(s, 4).point(0.0, 0.0)), (0.0, 0.0))

    def test_continues_past_the_box(self):
        p = CO.Patch(CO.sides_of(box_lines()))
        self.assertAlmostEqual(p.point(-0.1, 0.5)[0], -10.0, places=6)
        self.assertAlmostEqual(p.point(1.1, 0.5)[0], 110.0, places=6)


class Vector(unittest.TestCase):
    def _object(self):
        return Shape(path=Path([rect(0, 0, 10, 10)]), tool=2)

    def test_group_and_source(self):
        g = EN.build_in_curves([self._object()], CO.sides_of(box_lines(200, 100)))
        self.assertEqual(g.extra['envelope']['kind'], 'courbes')
        b = g.bbox()
        for v, want in zip(b, (200, 100, 300, 120)):
            self.assertAlmostEqual(v, want, places=4)
        self.assertEqual(sum(1 for c in g.children if c.extra.get('envelope_source')), 1)

    def test_curved_envelope(self):
        a, b, c, d = box_lines()
        curved = Contour([Cubic((0, 0), (30, -20), (70, -20), (100, 0))], False)
        g = EN.build_in_curves([self._object()], CO.sides_of([curved, b, c, d]))
        self.assertAlmostEqual(g.bbox()[1], -15.0, places=1)

    def test_nothing_to_warp(self):
        self.assertIsNone(EN.build_in_curves([], CO.sides_of(box_lines())))

    def test_rebuild_with_turn(self):
        g = EN.build_in_curves([self._object()], CO.sides_of(box_lines(200, 100)))
        spec = EN.EnvelopeSpec.from_dict(g.extra['envelope'])
        spec.turn = 1
        new = EN.rebuild(g, spec)
        self.assertAlmostEqual(new.bbox()[2] - new.bbox()[0], 100.0, places=4)
        self.assertEqual(new.extra['envelope']['turn'], 1)

    def test_rebuild_after_moving_follows_the_group(self):
        from vectordrive.core.geom import Affine
        g = EN.build_in_curves([self._object()], CO.sides_of(box_lines(200, 100)))
        moved = g.transformed(Affine.translation(1000, 0))
        again = EN.rebuild(moved, EN.EnvelopeSpec.from_dict(moved.extra['envelope']))
        self.assertAlmostEqual(again.bbox()[0], 1200.0, places=4)

    def test_settings_survive_a_save(self):
        import json
        g = EN.build_in_curves([self._object()], CO.sides_of(box_lines()))
        back = EN.EnvelopeSpec.from_dict(json.loads(json.dumps(g.extra['envelope'])))
        self.assertEqual(back.kind, 'courbes')
        self.assertEqual(len(back.sides), 4)

    def test_other_envelopes_unchanged(self):
        spec = EN.EnvelopeSpec(kind='arc', amount=50)
        self.assertEqual(spec.sides, None)
        g = EN.build([self._object()], spec)
        self.assertEqual(g.extra['envelope']['kind'], 'arc')


class Pick(unittest.TestCase):
    def _lines(self):
        return [Shape(path=Path([c])) for c in box_lines()]

    def test_four_curves_last(self):
        o = Shape(path=Path([rect(0, 0, 5, 5)]))
        objs, curves, sides = CO.pick([o] + self._lines())
        self.assertEqual(objs, [o])
        self.assertEqual(len(curves), 4)
        self.assertEqual(len(sides), 4)

    def test_closed_contour_last(self):
        o = Shape(path=Path([rect(0, 0, 5, 5)]))
        env = Shape(path=Path([rect(0, 0, 50, 5)]))
        objs, curves, _s = CO.pick([o, env])
        self.assertEqual(objs, [o])
        self.assertEqual(curves, [env])

    def test_combined_curves_as_one_object(self):
        o = Shape(path=Path([rect(0, 0, 5, 5)]))
        env = Shape(path=Path(box_lines()))
        objs, curves, _s = CO.pick([o, env])
        self.assertEqual(curves, [env])

    def test_open_objects_are_not_taken_for_the_envelope(self):
        strokes = [Shape(path=Path([line((i, 50), (i, 60))])) for i in range(5)]
        env = Shape(path=Path([rect(0, 0, 50, 5)]))
        objs, curves, _s = CO.pick(strokes + [env])
        self.assertEqual(curves, [env])
        self.assertEqual(len(objs), 5)

    def test_nothing(self):
        self.assertIsNone(CO.pick([]))
        self.assertIsNone(CO.pick([Shape(path=Path([line((0, 0), (1, 1))]))]))


def pyramid(n=40, top=3.0):
    y, x = np.mgrid[0:n, 0:n]
    d = np.maximum(np.abs(x - (n - 1) / 2), np.abs(y - (n - 1) / 2)) / ((n - 1) / 2)
    return (1 - d) * top


class Warp(unittest.TestCase):
    def test_same_box_keeps_the_relief(self):
        H = pyramid()
        out, x0, y1, res = CO.warp_heights(H, CO.sides_of(box_lines(0, 0, 20, 20)), 0, 0.5)
        self.assertEqual(out.shape, H.shape)
        self.assertLess(float(np.abs(out - H).max()), 0.25)
        self.assertAlmostEqual(float(out.max()), float(H.max()), delta=0.2)

    def test_box_in_the_output(self):
        out, x0, y1, res = CO.warp_heights(pyramid(), CO.sides_of(box_lines(30, 40, 100, 20)), 0, 0.5)
        self.assertAlmostEqual(x0, 30.0, delta=1.0)
        self.assertAlmostEqual(y1, 60.0, delta=1.0)
        self.assertEqual(out.shape, (40, 200))

    def test_z_does_not_change(self):
        H = pyramid(top=5.0)
        out, *_ = CO.warp_heights(H, CO.sides_of(box_lines(0, 0, 200, 20)), 0, 0.25)
        self.assertAlmostEqual(float(out.max()), 5.0, delta=0.3)
        self.assertGreaterEqual(float(out.min()), -1e-9)

    def test_top_moves_with_the_envelope(self):
        out, x0, y1, res = CO.warp_heights(pyramid(), CO.sides_of(box_lines(0, 0, 100, 20)), 0, 0.5)
        j, i = np.unravel_index(int(np.argmax(out)), out.shape)
        self.assertAlmostEqual(x0 + (i + 0.5) * res, 50.0, delta=2.0)
        self.assertAlmostEqual(y1 - (j + 0.5) * res, 10.0, delta=2.0)

    def test_arc_envelope_bends_the_relief(self):
        a = Contour([Cubic((0, 0), (30, 40), (70, 40), (100, 0))], False)
        t = Contour([Cubic((100, 20), (70, 60), (30, 60), (0, 20))], False)
        sides = CO.sides_of([a, line((100, 0), (100, 20)), t, line((0, 20), (0, 0))])
        H = np.ones((20, 100))
        out, x0, y1, res = CO.warp_heights(H, sides, 0, 0.5)
        col = int(round((50 - x0) / res))
        row_of = lambda y: int(round((y1 - y) / res))
        self.assertEqual(float(out[row_of(5), col]), 0.0)      # sous l'arc, au milieu
        self.assertAlmostEqual(float(out[row_of(40), col]), 1.0, places=6)
        self.assertEqual(float(out[row_of(5), 2]), 1.0)        # dans l'arc, à gauche

    def test_outside_is_zero(self):
        out, *_ = CO.warp_heights(np.ones((10, 10)), CO.sides_of([circle((0, 0), 10)]), 0, 0.25)
        self.assertEqual(float(out[0, 0]), 0.0)
        self.assertAlmostEqual(float(out[out.shape[0] // 2, out.shape[1] // 2]), 1.0, places=6)

    def test_no_hole_in_a_stretched_patch(self):
        pts = [(0, 0), (10, 0), (100, 100), (0, 10)]
        out, x0, y1, res = CO.warp_heights(np.ones((10, 10)), CO.sides_of([polyline(pts, True)]), 0, 0.5)
        row = int((y1 - 30) / res)
        col = int((30 - x0) / res)
        self.assertEqual(float(out[row, col]), 1.0)

    def test_one_pixel_relief(self):
        out, *_ = CO.warp_heights(np.full((1, 1), 2.0), CO.sides_of(box_lines(0, 0, 10, 10)), 0, 1.0)
        self.assertEqual(float(out.max()), 2.0)

    def test_turn_rotates_the_relief(self):
        H = np.zeros((10, 10))
        H[9, 0] = 1.0                                   # en bas à gauche
        sides = CO.sides_of(box_lines(0, 0, 10, 10))
        plain, x0, y1, res = CO.warp_heights(H, sides, 0, 0.25)
        turned, *_ = CO.warp_heights(H, sides, 2, 0.25)
        n = plain.shape[0]
        self.assertGreater(float(plain[n - 1, 0]), 0.5)
        self.assertGreater(float(turned[0, n - 1]), 0.5)

    def test_big_relief_is_capped(self):
        with mock.patch.object(CO, 'MAX_SAMPLES', 10000):
            out, *_ = CO.warp_heights(np.ones((10, 10)), CO.sides_of(box_lines(0, 0, 100, 100)), 0, 0.5)
        self.assertEqual(out.shape, (200, 200))
        self.assertGreater(float(out.mean()), 0.0)

    def test_image(self):
        img = GB.encode(pyramid(), 0.0, 20.0, 0.5, GB.GalbeSpec(z_max=3.0), 4, 'Motif')
        new = CO.warp_image(img, CO.sides_of(box_lines(0, 0, 100, 20)), 0, 0.5)
        self.assertEqual(new.tool, 4)
        self.assertEqual(new.name, 'Motif')
        self.assertAlmostEqual(new.extra['galbe']['top'], 3.0, delta=0.2)
        self.assertEqual(new.bbox()[2] - new.bbox()[0], 100.0)
        self.assertIsNotNone(GB.decode(new))

    def test_tilted_image_refused(self):
        from vectordrive.core.geom import Affine
        img = GB.encode(pyramid(), 0.0, 20.0, 0.5, GB.GalbeSpec(z_max=3.0))
        self.assertIsNone(CO.warp_image(img.transformed(Affine.rotation(30)), CO.sides_of(box_lines()), 0, 0.5))


class Commands(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.close()

    def setUp(self):
        doc = self.win.canvas.doc
        doc.layers = [Layer(name='Plan 1')]
        doc.active = doc.layers[0].id

    @property
    def items(self):
        return self.win.canvas.doc.layers[0].items

    def _put(self, *items):
        self.items.extend(items)
        self.win.canvas.select(list(items))

    def test_ribbon_once(self):
        for k in ('envelope_curves', 'relief_warp'):
            found = [b for i in range(self.win.ribbon.count()) for g in self.win.ribbon.page(i).groups() for b in g.buttons()
                     if b.defaultAction() is self.win.A[k]]
            self.assertEqual(len(found), 1, k)

    def test_te_links(self):
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual(TE_ACTIONS['ID_WARPING_GRID'], 'relief_warp')
        self.assertEqual(TE_ACTIONS['ID_GALBE_MAPPING'], 'relief_photo')

    def test_objects_into_four_curves(self):
        o = Shape(path=Path([rect(0, 0, 10, 10)]))
        curves = [Shape(path=Path([c])) for c in box_lines(200, 100)]
        self._put(o, *curves)
        out = self.win.envelope_curves(turn=0, keep=True)
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out[0].bbox()[2], 300.0, places=4)
        self.assertEqual(len(self.items), 5)
        self.assertNotIn(o, self.items)

    def test_curves_can_go_away(self):
        o = Shape(path=Path([rect(0, 0, 10, 10)]))
        env = Shape(path=Path([rect(200, 100, 100, 20)]))
        self._put(o, env)
        self.win.envelope_curves(turn=0, keep=False)
        self.assertEqual(len(self.items), 1)
        self.assertIsInstance(self.items[0], Group)

    def test_undo(self):
        o = Shape(path=Path([rect(0, 0, 10, 10)]))
        env = Shape(path=Path([rect(200, 100, 100, 20)]))
        self._put(o, env)
        self.win.envelope_curves(turn=0, keep=False)
        self.win.undo()
        self.assertEqual(len(self.items), 2)
        self.assertEqual(self.items[0].bbox(), (0.0, 0.0, 10.0, 10.0))

    def test_text_goes_in(self):
        t = Text(text='ABC', font='VD Trait', size=5.0)
        env = Shape(path=Path([rect(200, 100, 100, 20)]))
        self._put(t, env)
        out = self.win.envelope_curves(turn=0, keep=True)
        self.assertAlmostEqual(out[0].bbox()[0], 200.0, delta=1.0)
        self.assertAlmostEqual(out[0].bbox()[2], 300.0, delta=1.0)

    def test_refused_without_envelope(self):
        o = Shape(path=Path([line((0, 0), (10, 0))]))
        self._put(o)
        with mock.patch.object(QMessageBox, 'information') as info:
            self.assertEqual(self.win.envelope_curves(turn=0, keep=True), [])
        info.assert_called_once()

    def test_refused_without_objects(self):
        env = Shape(path=Path([rect(200, 100, 100, 20)]))
        self._put(env)
        with mock.patch.object(QMessageBox, 'information') as info:
            self.assertEqual(self.win.envelope_curves(turn=0, keep=True), [])
        info.assert_called_once()

    def test_double_click_settings(self):
        o = Shape(path=Path([rect(0, 0, 10, 10)]))
        env = Shape(path=Path([rect(200, 100, 100, 20)]))
        self._put(o, env)
        g = self.win.envelope_curves(turn=0, keep=True)[0]
        with mock.patch.object(self.win, '_curves_dialog') as dialog:
            spec = EN.EnvelopeSpec.from_dict(g.extra['envelope'])
            spec.turn = 2
            dialog.return_value = (spec, True)
            self.win.edit_envelope(g)
        dialog.assert_called_once()
        self.assertEqual(self.win.canvas.selection[0].extra['envelope']['turn'], 2)

    def test_dialog_builds(self):
        from PySide6.QtWidgets import QDialog
        spec = EN.EnvelopeSpec(kind='courbes')
        with mock.patch.object(QDialog, 'exec', return_value=1):
            got, keep = self.win._curves_dialog(spec, keep=False)
        self.assertEqual(got.turn, 0)
        self.assertFalse(keep)

    def test_relief_warp(self):
        img = GB.encode(pyramid(), 0.0, 20.0, 0.5, GB.GalbeSpec(z_max=3.0), 0, 'Motif')
        env = Shape(path=Path([rect(100, 100, 200, 20)]))
        self._put(img, env)
        with mock.patch('vectordrive.ui.progress.run', side_effect=lambda _p, _t, f, *a: f(*a)):
            new = self.win.relief_warp({'resolution': 0.5, 'turn': 0})
        self.assertEqual(new.bbox()[0], 100.0)
        self.assertIn(new, self.items)
        self.assertNotIn(img, self.items)
        self.assertIn(env, self.items)

    def test_relief_warp_needs_both(self):
        img = GB.encode(pyramid(), 0.0, 20.0, 0.5, GB.GalbeSpec(z_max=3.0))
        self._put(img)
        self.assertIsNone(self.win.relief_warp({'resolution': 0.5, 'turn': 0}))

    def test_relief_warp_bad_curves(self):
        img = GB.encode(pyramid(), 0.0, 20.0, 0.5, GB.GalbeSpec(z_max=3.0))
        self._put(img, Shape(path=Path([line((0, 0), (5, 5))])))
        self.assertIsNone(self.win.relief_warp({'resolution': 0.5, 'turn': 0}))

    def test_refusal_messages(self):
        for key in ('join', 'corners', 'area', 'count'):
            self.assertNotEqual(self.win._envelope_why(CO.EnvelopeError(key)), key)


if __name__ == '__main__':
    unittest.main()
