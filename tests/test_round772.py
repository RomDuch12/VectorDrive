"""Round 772 : courber le dessin le long d'un tracé."""
import math
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())

from shapely.geometry import LinearRing, Point
from PySide6.QtWidgets import QApplication, QMessageBox

from vectordrive.core import pathbend as PB
from vectordrive.core.document import Document, Group, Layer, Shape, Text
from vectordrive.core.geom import Affine, Conic, Contour, Cubic, Line, Path, polyline, rect
from vectordrive.io import vnd, vnd_write as VW


def art(w=20.0, h=4.0, x=0.0, y=0.0):
    return Shape(path=Path([rect(x, y, w, h)]), tool=1)


def line_guide(x0=0.0, y0=0.0, x1=100.0, y1=0.0):
    return Shape(path=Path([Contour([Line((x0, y0), (x1, y1))], False)]), tool=2)


def circle_guide(r=30.0):
    k = 0.5522847498 * r
    segs = [Cubic((r, 0), (r, k), (k, r), (0, r)), Cubic((0, r), (-k, r), (-r, k), (-r, 0)),
            Cubic((-r, 0), (-r, -k), (-k, -r), (0, -r)), Cubic((0, -r), (k, -r), (r, -k), (r, 0))]
    return Shape(path=Path([Contour(segs, True)]))


def half_circle(r=30.0):
    """De (r, 0) à (-r, 0), en passant par le haut."""
    k = 0.5522847498 * r
    return Shape(path=Path([Contour([Cubic((r, 0), (r, k), (k, r), (0, r)), Cubic((0, r), (-k, r), (-r, k), (-r, 0))], False)]))


def shown(g):
    return [c for c in g.children if c.visible]


def points(shape, tol=0.002):
    out = []
    for c in shape.path.contours:
        out += c.flatten(tol)
    return out


def box_of(items):
    boxes = [i.bbox() for i in items]
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


class GuideTable(unittest.TestCase):
    def test_line(self):
        g = PB.Guide(line_guide().path.contours[0])
        self.assertAlmostEqual(g.length, 100.0)
        self.assertAlmostEqual(g.point(40.0)[0], 40.0, places=9)
        self.assertAlmostEqual(g.point(40.0)[1], 0.0, places=9)
        self.assertAlmostEqual(g.normal(40.0)[1], 1.0)
        self.assertTrue(g.straight)

    def test_past_the_ends_of_an_open_guide_goes_straight_on(self):
        g = PB.Guide(line_guide().path.contours[0])
        self.assertEqual(g.point(-5.0), (-5.0, 0.0))
        self.assertEqual(g.point(105.0), (105.0, 0.0))

    def test_circle_length_and_points(self):
        g = PB.Guide(circle_guide().path.contours[0])
        self.assertAlmostEqual(g.length, 2 * math.pi * 30.0, delta=0.05)
        for k in range(40):
            x, y = g.point(k * g.length / 40)
            self.assertAlmostEqual(math.hypot(x, y), 30.0, delta=0.02)

    def test_closed_guide_wraps(self):
        g = PB.Guide(circle_guide().path.contours[0])
        a, b = g.point(5.0), g.point(5.0 + g.length)
        self.assertAlmostEqual(a[0], b[0], places=6)
        self.assertAlmostEqual(a[1], b[1], places=6)
        a, b = g.point(5.0), g.point(5.0 - 2 * g.length)
        self.assertAlmostEqual(a[0], b[0], places=6)

    def test_circle_normal_points_inward_when_turning_left(self):
        g = PB.Guide(circle_guide().path.contours[0])
        for k in range(1, 12):
            s = k * g.length / 12
            x, y = g.point(s)
            nx, ny = g.normal(s)
            self.assertAlmostEqual(nx, -x / 30.0, delta=0.01)
            self.assertAlmostEqual(ny, -y / 30.0, delta=0.01)

    def test_conic_guide(self):
        c = Conic((10, 0), (10, 10), (0, 10), math.sqrt(2) / 2)
        g = PB.Guide(Contour([c], False))
        self.assertAlmostEqual(g.length, math.pi * 10 / 2, delta=0.01)
        self.assertEqual(g.corners, 0)

    def test_corner_turns_normal_quickly_and_continuously(self):
        g = PB.Guide(polyline([(0, 0), (50, 0), (50, 50)], False).reversed().reversed())
        self.assertEqual(g.corners, 1)
        self.assertAlmostEqual(g.normal(40.0)[1], 1.0, places=6)
        self.assertAlmostEqual(g.normal(60.0)[0], -1.0, places=6)
        prev = g.normal(50.0 - PB.CORNER * 1.5)
        for k in range(1, 31):
            cur = g.normal(50.0 - PB.CORNER * 1.5 + k * PB.CORNER * 0.1)
            self.assertLess(math.dist(prev, cur), 0.2)
            prev = cur

    def test_short_segments_narrow_the_corner(self):
        g = PB.Guide(polyline([(0, 0), (10, 0), (10, 0.02), (20, 0.02)], False))
        self.assertEqual(g.corners, 2)
        self.assertTrue(all(b > a for a, b in zip(g.SA, g.SA[1:])))

    def test_null_segments_skipped(self):
        g = PB.Guide(Contour([Line((0, 0), (0, 0)), Line((0, 0), (10, 0)), Line((10, 0), (10, 0))], False))
        self.assertTrue(g.valid)
        self.assertAlmostEqual(g.length, 10.0)

    def test_empty_guide_not_valid(self):
        self.assertFalse(PB.Guide(Contour([Line((3, 3), (3, 3))], False)).valid)

    def test_degenerate_handles(self):
        g = PB.Guide(Contour([Cubic((0, 0), (0, 0), (10, 0), (10, 0))], False))
        self.assertAlmostEqual(g.length, 10.0, delta=1e-6)
        self.assertAlmostEqual(g.normal(0.0)[1], 1.0, places=6)
        self.assertAlmostEqual(g.normal(10.0)[1], 1.0, places=6)

    def test_reversed_closed_square_seam(self):
        square = rect(0, 0, 10, 10)
        g = PB.Guide(square)
        self.assertTrue(g.closed)
        self.assertTrue(g._seam)
        self.assertGreaterEqual(g.corners, 3)
        for s in (0.0, g.length - 1e-9):
            n = g.normal(s)
            self.assertAlmostEqual(math.hypot(*n), 1.0, places=9)


class Modes(unittest.TestCase):
    def test_stretch_on_a_straight_line_is_a_plain_scale(self):
        g = PB.build([art(20, 4)], line_guide(), PB.BendSpec(mode='etirer', align='bas'))
        res = shown(g)
        self.assertEqual(len(res), 1)
        b = res[0].bbox()
        self.assertAlmostEqual(b[0], 0.0, places=6)
        self.assertAlmostEqual(b[2], 100.0, places=6)
        self.assertAlmostEqual(b[1], 0.0, places=6)
        self.assertAlmostEqual(b[3], 4.0, places=6)

    def test_straight_guide_gives_only_straight_lines(self):
        g = PB.build([art(20, 4)], line_guide(), PB.BendSpec(mode='etirer'))
        c = shown(g)[0].path.contours[0]
        self.assertEqual(len(c.segments), 4)
        self.assertTrue(all(isinstance(s, Line) for s in c.segments))

    def test_keep_size(self):
        g = PB.build([art(20, 4)], line_guide(), PB.BendSpec(mode='garder', align='bas', start=30.0))
        b = shown(g)[0].bbox()
        self.assertAlmostEqual(b[0], 30.0, places=6)
        self.assertAlmostEqual(b[2], 50.0, places=6)

    def test_art_longer_than_guide_runs_past_the_end(self):
        g = PB.build([art(120, 4)], line_guide(), PB.BendSpec(mode='garder', align='bas'))
        self.assertAlmostEqual(shown(g)[0].bbox()[2], 120.0, places=6)

    def test_repeat(self):
        g = PB.build([art(20, 4)], line_guide(), PB.BendSpec(mode='repeter', gap=5.0))
        res = shown(g)
        self.assertEqual(len(res), 4)                     # 20 + 5 + 20 + 5 + 20 + 5 + 20 = 95
        self.assertAlmostEqual(box_of(res)[2], 95.0, places=6)

    def test_repeat_exact_fit_with_gap(self):
        g = PB.build([art(20, 4)], line_guide(x1=95.0), PB.BendSpec(mode='repeter', gap=5.0))
        self.assertEqual(len(shown(g)), 4)

    def test_repeat_stretched_fills_the_length(self):
        g = PB.build([art(20, 4)], line_guide(), PB.BendSpec(mode='repeter_etirer', gap=5.0))
        res = shown(g)
        self.assertEqual(len(res), 4)
        self.assertAlmostEqual(box_of(res)[2], 100.0, places=6)
        widths = [r.bbox()[2] - r.bbox()[0] for r in res]
        self.assertAlmostEqual(widths[0], (100 - 15) / 4, places=6)

    def test_repeat_on_a_closed_guide_counts_the_last_gap(self):
        guide = circle_guide()
        length = PB.Guide(guide.path.contours[0]).length
        g = PB.build([art(10, 2)], guide, PB.BendSpec(mode='repeter', gap=2.0))
        self.assertEqual(len(shown(g)), int(length / 12))

    def test_one_copy_when_the_art_is_longer_than_the_guide(self):
        g = PB.build([art(200, 4)], line_guide(), PB.BendSpec(mode='repeter'))
        self.assertEqual(len(shown(g)), 1)

    def test_too_many_copies_refused(self):
        with self.assertRaises(ValueError) as cm:
            PB.build([art(0.01, 1)], line_guide(), PB.BendSpec(mode='repeter'))
        self.assertEqual(str(cm.exception), 'copies')

    def test_start_past_the_end_refused_for_stretch(self):
        with self.assertRaises(ValueError) as cm:
            PB.build([art()], line_guide(), PB.BendSpec(start=500.0))
        self.assertEqual(str(cm.exception), 'start')

    def test_gap_too_large_refused(self):
        # n = 1 quand l'écart est grand : pas de refus, une seule copie étirée
        g = PB.build([art(10, 2)], line_guide(), PB.BendSpec(mode='repeter_etirer', gap=500.0))
        self.assertEqual(len(shown(g)), 1)

    def test_negative_gap_overlaps(self):
        g = PB.build([art(20, 4)], line_guide(), PB.BendSpec(mode='repeter', gap=-5.0))
        self.assertEqual(len(shown(g)), 6)

    def test_vertical_line_art(self):
        s = Shape(path=Path([Contour([Line((3, 0), (3, 10))], False)]))
        g = PB.build([s], line_guide(), PB.BendSpec(mode='etirer', align='bas', start=7.0))
        b = shown(g)[0].bbox()
        self.assertAlmostEqual(b[0], 7.0, places=6)
        self.assertAlmostEqual(b[3], 10.0, places=6)


class Placement(unittest.TestCase):
    def test_align(self):
        for align, lo, hi in (('bas', 0.0, 4.0), ('haut', -4.0, 0.0), ('milieu', -2.0, 2.0)):
            g = PB.build([art(20, 4, y=7.0)], line_guide(), PB.BendSpec(mode='garder', align=align))
            b = shown(g)[0].bbox()
            self.assertAlmostEqual(b[1], lo, places=6, msg=align)
            self.assertAlmostEqual(b[3], hi, places=6, msg=align)

    def test_height_offset_and_flip(self):
        g = PB.build([art(20, 4)], line_guide(), PB.BendSpec(mode='garder', align='bas', height=50.0, offset=3.0))
        b = shown(g)[0].bbox()
        self.assertAlmostEqual(b[1], 3.0, places=6)
        self.assertAlmostEqual(b[3], 5.0, places=6)
        g = PB.build([art(20, 4)], line_guide(), PB.BendSpec(mode='garder', align='bas', flip=True))
        b = shown(g)[0].bbox()
        self.assertAlmostEqual(b[1], -4.0, places=6)
        self.assertAlmostEqual(b[3], 0.0, places=6)

    def test_reverse(self):
        g = PB.build([art(20, 4)], line_guide(), PB.BendSpec(mode='garder', align='bas', reverse=True))
        b = shown(g)[0].bbox()
        self.assertAlmostEqual(b[0], 80.0, places=6)
        self.assertAlmostEqual(b[2], 100.0, places=6)
        self.assertAlmostEqual(b[1], -4.0, places=6)              # à gauche du sens, donc dessous

    def test_on_a_half_circle_stays_in_the_band(self):
        g = PB.build([art(50, 4)], half_circle(), PB.BendSpec(mode='etirer', align='bas', tolerance=0.002))
        for x, y in points(shown(g)[0], 0.001):
            r = math.hypot(x, y)
            self.assertGreater(r, 26.0 - 0.01)                    # à gauche du sens : vers le centre
            self.assertLess(r, 30.0 + 0.01)
            self.assertGreater(y, -0.01)

    def test_keep_size_preserves_length_along_the_path(self):
        s = Shape(path=Path([Contour([Line((0, 0), (40, 0))], False)]))
        g = PB.build([s], half_circle(), PB.BendSpec(mode='garder', align='bas'))
        self.assertAlmostEqual(shown(g)[0].path.contours[0].length(), 40.0, delta=0.02)

    def test_tolerance_is_respected(self):
        spec = PB.BendSpec(mode='etirer', align='bas', tolerance=0.005)
        src = art(50, 8)
        g = PB.build([src], half_circle(), spec)
        guide = PB.Guide(half_circle().path.contours[0])
        count, sx = PB._layout(spec, guide, 50.0)
        f = PB.mapping(guide, spec, src.bbox(), 0, sx)
        # chaque point exact du bord du haut (y = 8) est à moins de la tolérance du résultat
        out = shown(g)[0].path.contours[0]
        drawn = LinearRing(out.flatten(0.0005))
        for k in range(101):
            self.assertLess(drawn.distance(Point(f((k / 2, 8.0)))), 0.0055)

    def test_closed_contours_stay_closed_and_touching(self):
        g = PB.build([art(50, 4)], half_circle(), PB.BendSpec(mode='etirer', align='milieu'))
        c = shown(g)[0].path.contours[0]
        self.assertTrue(c.closed)
        self.assertEqual(c.segments[0].start, c.segments[-1].end)
        for a, b in zip(c.segments, c.segments[1:]):
            self.assertEqual(a.end, b.start)

    def test_open_contours_stay_open(self):
        s = Shape(path=Path([Contour([Line((0, 0), (40, 0))], False)]))
        g = PB.build([s], half_circle(), PB.BendSpec())
        self.assertFalse(shown(g)[0].path.contours[0].closed)

    def test_corner_guide_keeps_art_in_one_piece(self):
        guide = Shape(path=Path([polyline([(0, 0), (50, 0), (50, 50)], False)]))
        g = PB.build([art(100, 4)], guide, PB.BendSpec(mode='etirer', align='bas'))
        c = shown(g)[0].path.contours[0]
        for a, b in zip(c.segments, c.segments[1:]):
            self.assertLess(math.dist(a.end, b.start), 1e-9)
        b = shown(g)[0].bbox()
        self.assertAlmostEqual(b[2], 50.0, delta=0.01)
        self.assertAlmostEqual(b[3], 50.0, delta=0.01)

    def test_long_line_follows_fine_zigzag(self):
        """Une longue droite sur un tracé plus fin que les 3 points de contrôle : elle ne le saute pas."""
        pts = [(x * 2.5, 2.0 if x % 2 else 0.0) for x in range(41)]
        guide = Shape(path=Path([polyline(pts, False)]))
        s = Shape(path=Path([Contour([Line((0, 0), (100, 0))], False)]))
        g = PB.build([s], guide, PB.BendSpec(mode='etirer', align='bas'))
        out = shown(g)[0]
        self.assertAlmostEqual(out.bbox()[3], 2.0, delta=0.01)
        self.assertAlmostEqual(out.path.contours[0].length(), PB.Guide(guide.path.contours[0]).length, delta=0.1)

    def test_whole_turn_on_a_circle(self):
        g = PB.build([art(100, 4)], circle_guide(), PB.BendSpec(mode='etirer', align='bas'))
        b = shown(g)[0].bbox()
        for v in b:
            self.assertAlmostEqual(abs(v), 30.0, delta=0.1)    # à gauche du sens : vers l'intérieur

    def test_conic_art(self):
        c = Conic((10, 0), (10, 10), (0, 10), math.sqrt(2) / 2)
        s = Shape(path=Path([Contour([c], False)]))
        g = PB.build([s], line_guide(), PB.BendSpec(mode='garder', align='bas'))
        b = shown(g)[0].bbox()
        self.assertAlmostEqual(b[2] - b[0], 10.0, delta=0.01)


class Results(unittest.TestCase):
    def test_group_hides_sources_and_guide(self):
        src, gd = art(), half_circle()
        g = PB.build([src], gd, PB.BendSpec())
        self.assertIn('path_bend', g.extra)
        hidden = [c for c in g.children if not c.visible]
        self.assertEqual(len(hidden), 2)
        self.assertTrue(any(c.extra.get('bend_source') for c in hidden))
        self.assertTrue(any(c.extra.get('bend_guide') for c in hidden))
        self.assertTrue(src.visible)                              # l'objet donné n'est pas touché

    def test_group_box_ignores_what_is_hidden(self):
        g = PB.build([art(50, 4, x=1000.0, y=1000.0)], half_circle(), PB.BendSpec(mode='etirer', align='bas'))
        self.assertLess(g.bbox()[2], 40.0)

    def test_hidden_only_group_keeps_a_box(self):
        s = art()
        s.visible = False
        self.assertEqual(Group(children=[s]).bbox(), s.bbox())

    def test_keeps_tool_and_fill(self):
        s = art()
        s.filled = True
        g = PB.build([s], half_circle(), PB.BendSpec())
        r = shown(g)[0]
        self.assertTrue(r.filled)
        self.assertEqual(r.tool, 1)

    def test_several_objects_share_one_box(self):
        a, b = art(20, 4), art(20, 4, x=30.0)
        g = PB.build([a, b], line_guide(), PB.BendSpec(mode='garder', align='bas'))
        res = shown(g)
        self.assertEqual(len(res), 2)
        self.assertAlmostEqual(res[1].bbox()[0], 30.0, places=6)

    def test_groups_and_hidden_objects(self):
        hide = art(5, 5, x=99.0)
        hide.visible = False
        g = PB.build([Group(children=[art(), hide])], line_guide(), PB.BendSpec(mode='garder', align='bas'))
        self.assertEqual(len(shown(g)), 1)

    def test_text_is_bent(self):
        t = Text(text='ABC', font='Arial', size=10.0)
        g = PB.build([t], half_circle(40.0), PB.BendSpec(mode='garder', align='bas'))
        self.assertIsNotNone(g)
        out = shown(g)
        self.assertEqual(len(out), 1)
        self.assertGreaterEqual(len(out[0].path.contours), 3)

    def test_nothing_to_bend(self):
        self.assertIsNone(PB.build([], half_circle(), PB.BendSpec()))
        self.assertIsNone(PB.build([Shape()], half_circle(), PB.BendSpec()))
        self.assertIsNone(PB.build([art()], Shape(), PB.BendSpec()))
        self.assertIsNone(PB.build([art()], Shape(path=Path([Contour([Line((1, 1), (1, 1))], False)])), PB.BendSpec()))

    def test_rebuild_with_new_settings(self):
        g = PB.build([art(50, 4)], half_circle(), PB.BendSpec(mode='etirer'))
        new = PB.rebuild(g, PB.BendSpec(mode='garder', align='bas'))
        self.assertEqual(new.extra['path_bend']['mode'], 'garder')
        self.assertEqual(sum(1 for c in new.children if c.extra.get('bend_source')), 1)
        self.assertEqual(sum(1 for c in new.children if c.extra.get('bend_guide')), 1)
        self.assertEqual(len(shown(new)), 1)

    def test_rebuild_after_moving_the_group_stays_on_the_moved_guide(self):
        g = PB.build([art(50, 4)], half_circle(), PB.BendSpec(mode='etirer', align='bas'))
        moved = g.transformed(Affine.translation(500.0, 0.0))
        new = PB.rebuild(moved, PB.BendSpec(mode='etirer', align='bas'))
        self.assertAlmostEqual(new.bbox()[0], g.bbox()[0] + 500.0, delta=0.01)

    def test_rebuild_incomplete_group(self):
        self.assertIsNone(PB.rebuild(Group(children=[art()]), PB.BendSpec()))

    def test_spec_round_trip_ignores_unknown(self):
        d = PB.BendSpec(mode='repeter', gap=2.0).to_dict()
        d['autre'] = 1
        self.assertEqual(PB.BendSpec.from_dict(d).gap, 2.0)

    def test_vnd_keeps_only_what_is_visible(self):
        g = PB.build([art(50, 4, x=1000.0, y=1000.0)], half_circle(), PB.BendSpec(mode='etirer', align='bas'))
        doc = Document(layers=[Layer(items=[g])])
        data, _report = VW.write_document(doc)
        path = os.path.join(tempfile.mkdtemp(), 'b.vnd')
        with open(path, 'wb') as fh:
            fh.write(data)
        back = vnd.read(path)
        boxes = [it.bbox() for L in back.layers for it in L.items]
        self.assertTrue(boxes)
        self.assertLess(max(b[2] for b in boxes), 100.0)


class FoldRisk(unittest.TestCase):
    def test_gentle_curve_is_fine(self):
        self.assertIsNone(PB.fold_risk([art(50, 4)], half_circle().path.contours[0], PB.BendSpec()))

    def test_tight_curve_warned(self):
        risk = PB.fold_risk([art(50, 40)], half_circle(10.0).path.contours[0], PB.BendSpec())
        self.assertIsNotNone(risk)
        self.assertAlmostEqual(risk[0], 10.0, delta=0.5)
        self.assertAlmostEqual(risk[1], 20.0, delta=0.01)

    def test_corner_counts_as_no_radius(self):
        risk = PB.fold_risk([art(50, 4)], polyline([(0, 0), (50, 0), (50, 50)], False), PB.BendSpec())
        self.assertEqual(risk[0], 0.0)

    def test_straight_guide_never_folds(self):
        self.assertIsNone(PB.fold_risk([art(50, 400)], line_guide().path.contours[0], PB.BendSpec()))


class Command(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.settings.remove('courber')
        cls.win.close()

    def setUp(self):
        self.win.settings.remove('courber')
        doc = self.win.canvas.doc
        for L in doc.layers:
            L.items = []
        self.src = art(50, 4)
        self.guide = half_circle()
        doc.active_layer.items = [self.src, self.guide]
        self.win.canvas.select([self.src, self.guide])

    def _items(self):
        return list(self.win.canvas.doc.active_layer.items)

    def test_action_in_the_ribbon(self):
        self.assertIn('bend_path', self.win.A)
        found = [b for i in range(self.win.ribbon.count()) for gr in self.win.ribbon.page(i).groups() for b in gr.buttons()
                 if b.defaultAction() is self.win.A['bend_path']]
        self.assertEqual(len(found), 1)

    def test_bend_replaces_objects_and_guide(self):
        out = self.win.bend_along_path(PB.BendSpec())
        self.assertEqual(len(out), 1)
        self.assertEqual(self._items(), out)
        self.assertEqual(self.win.canvas.selection, out)

    def test_guide_can_stay(self):
        out = self.win.bend_along_path(PB.BendSpec(keep_guide=True))
        items = self._items()
        self.assertEqual(len(items), 2)
        self.assertIn(self.guide, items)
        self.assertIn(out[0], items)

    def test_undo(self):
        self.win.bend_along_path(PB.BendSpec())
        self.win.undo()
        ids = {type(i).__name__ for i in self._items()}
        self.assertEqual(ids, {'Shape'})
        self.assertEqual(len(self._items()), 2)

    def test_selection_needs_two_objects(self):
        self.win.canvas.select([self.guide])
        with mock.patch.object(QMessageBox, 'information') as info:
            self.assertEqual(self.win.bend_along_path(PB.BendSpec()), [])
        info.assert_called_once()
        self.assertEqual(len(self._items()), 2)

    def test_guide_must_be_a_shape(self):
        t = Text(text='A', font='Arial', size=5.0)
        self.win.canvas.doc.active_layer.items.append(t)
        self.win.canvas.select([self.src, t])
        with mock.patch.object(QMessageBox, 'information') as info:
            self.assertEqual(self.win.bend_along_path(PB.BendSpec()), [])
        info.assert_called_once()

    def test_guide_in_several_pieces_refused(self):
        two = Shape(path=Path([polyline([(0, 0), (9, 0)], False), polyline([(0, 5), (9, 5)], False)]))
        self.win.canvas.doc.active_layer.items.append(two)
        self.win.canvas.select([self.src, two])
        with mock.patch.object(QMessageBox, 'information') as info:
            self.assertEqual(self.win.bend_along_path(PB.BendSpec()), [])
        info.assert_called_once()

    def test_bad_settings_refused_without_change(self):
        with mock.patch.object(QMessageBox, 'information') as info:
            self.assertEqual(self.win.bend_along_path(PB.BendSpec(start=9999.0)), [])
        info.assert_called_once()
        self.assertEqual(len(self._items()), 2)

    def test_dialog_keeps_last_values(self):
        def fake(spec, creating=True):
            spec.mode = 'repeter'
            spec.gap = 3.0
            return spec
        with mock.patch.object(self.win, '_bend_dialog', side_effect=fake):
            self.win.bend_along_path()
        self.assertEqual(str(self.win.settings.value('courber/pose')), 'repeter')
        self.assertEqual(float(self.win.settings.value('courber/entre')), 3.0)

    def test_cancel_changes_nothing(self):
        with mock.patch.object(self.win, '_bend_dialog', return_value=None):
            self.assertEqual(self.win.bend_along_path(), [])
        self.assertEqual(len(self._items()), 2)

    def test_edit(self):
        g = self.win.bend_along_path(PB.BendSpec())[0]
        new = self.win.bend_edit(g, PB.BendSpec(mode='garder', align='bas'))
        self.assertEqual(self._items(), [new])
        self.assertEqual(new.extra['path_bend']['mode'], 'garder')
        self.win.undo()
        self.assertEqual(self._items()[0].extra['path_bend']['mode'], 'etirer')

    def test_double_click_opens_the_settings(self):
        g = self.win.bend_along_path(PB.BendSpec())[0]
        with mock.patch.object(self.win, 'bend_edit') as edit:
            self.win._item_double_clicked(g)
        edit.assert_called_once_with(g)

    def test_fold_warning_in_the_status_bar(self):
        self.src.path = Path([rect(0, 0, 50, 200)])
        self.win.statusBar().clearMessage()
        self.win.bend_along_path(PB.BendSpec())
        self.assertIn('replie', self.win.statusBar().currentMessage())

    def test_real_dialog_gives_settings(self):
        from vectordrive.ui import dialogs
        with mock.patch.object(dialogs.ParamsDialog, 'exec', return_value=1):
            spec = self.win._bend_dialog(PB.BendSpec(mode='garder', height=-50.0, tolerance=0.0))
        self.assertEqual(spec.mode, 'garder')
        self.assertEqual(spec.height, 50.0)
        self.assertEqual(spec.tolerance, PB.MIN_TOLERANCE)


if __name__ == '__main__':
    unittest.main()
