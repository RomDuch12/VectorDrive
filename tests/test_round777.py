"""Round 777 : lecture des fichiers IGES."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')

import numpy as np
from shapely.geometry import Polygon

from vectordrive.core.geom import Conic, Cubic, Line
from vectordrive.io import iges, mesh3d, model3d, registry


class Ent:
    """Une entité à écrire ; `de` est connu après `build`."""

    def __init__(self, kind, params, form=0, matrix=None, status='00000000', level=0):
        self.kind, self.params, self.form = kind, params, form
        self.matrix, self.status, self.level = matrix, status, level
        self.de = 0


def _line(text, section, seq):
    return f'{text:<72}{section}{seq:>7}'


def build(ents, unit=2, unit_name='2HMM', head=None, folder=None, name='essai.igs'):
    for i, e in enumerate(ents):
        e.de = 2 * i + 1
    d_lines, p_lines = [], []
    for e in ents:
        vals = [v.de if isinstance(v, Ent) else v for v in e.params]
        text = ','.join([str(e.kind), *[str(v) for v in vals]]) + ';'
        chunks = [text[i:i + 64] for i in range(0, len(text), 64)] or ['']
        ptr = len(p_lines) + 1
        for c in chunks:
            p_lines.append(f'{c:<64}{e.de:>8}P{len(p_lines) + 1:>7}')
        m = e.matrix.de if e.matrix else 0
        first = f'{e.kind:>8}{ptr:>8}{0:>8}{0:>8}{e.level:>8}{0:>8}{m:>8}{0:>8}{e.status:>8}'
        second = f'{e.kind:>8}{0:>8}{0:>8}{len(chunks):>8}{e.form:>8}{0:>8}{0:>8}{"":>8}{0:>8}'
        d_lines.append(_line(first, 'D', e.de))
        d_lines.append(_line(second, 'D', e.de + 1))
    g = head or (f'1H,,1H;,3Hsrc,5Ha.igs,1Hx,1Hy,32,38,6,308,15,,1.,{unit},{unit_name},1,1.,'
                 '15H20260101.000000,0.001,100.,1Ha,1Hb,11,0,15H20260101.000000;')
    g_lines = [_line(g[i:i + 72], 'G', i // 72 + 1) for i in range(0, len(g), 72)]
    out = [_line('essai', 'S', 1)] + g_lines + d_lines + p_lines
    out.append(_line(f'S{1:>7}G{len(g_lines):>7}D{len(d_lines):>7}P{len(p_lines):>7}', 'T', 1))
    path = os.path.join(folder or tempfile.mkdtemp(), name)
    with open(path, 'w', encoding='latin-1', newline='\n') as fh:
        fh.write('\n'.join(out) + '\n')
    return path


def line(a, b, **kw):
    return Ent(110, [*a, *b], **kw)


def contours(doc):
    return [c for L in doc.layers for it in L.items for c in it.path.contours]


def area(c, tol=0.001):
    return Polygon(c.flatten(tol)).area


def plane_patch(x0, y0, x1, y1, z=0.0):
    """Surface 128 de degrés 1 × 1, de paramètres (0..1)²."""
    return Ent(128, [1, 1, 1, 1, 0, 0, 1, 0, 0, 0, 0, 1, 1, 0, 0, 1, 1, 1, 1, 1, 1,
                     x0, y0, z, x1, y0, z, x0, y1, z, x1, y1, z, 0, 1, 0, 1], status='00010000')


def by_name(doc, text):
    return [L for L in doc.layers if text in L.name]


class Curves(unittest.TestCase):
    def test_line(self):
        doc = iges.read(build([line((1, 2, 3), (11, 2, 3))]))
        cs = contours(doc)
        self.assertEqual(len(cs), 1)
        self.assertIsInstance(cs[0].segments[0], Line)
        self.assertEqual(doc.bbox(include_plate=False), (1.0, 2.0, 11.0, 2.0))
        self.assertEqual(doc.layers[0].name, 'IGES')
        self.assertEqual(doc.source_format, 'iges')

    def test_quarter_arc_stays_a_curve(self):
        doc = iges.read(build([Ent(100, [0, 0, 0, 10, 0, 0, 10])]))
        s = contours(doc)[0].segments
        self.assertEqual(len(s), 1)
        self.assertIsInstance(s[0], Conic)
        mid = s[0].flatten(0.001)[len(s[0].flatten(0.001)) // 2]
        self.assertAlmostEqual(math.hypot(*mid), 10.0, delta=0.001)

    def test_full_circle(self):
        c = contours(iges.read(build([Ent(100, [5, 0, 0, 10, 0, 10, 0])])))[0]
        self.assertTrue(c.closed)
        self.assertAlmostEqual(area(c), math.pi * 100, delta=0.05)

    def test_clockwise_definition_stays_counterclockwise(self):
        c = contours(iges.read(build([Ent(100, [0, 0, 0, 0, 10, 10, 0])])))[0]
        pts = c.flatten(0.01)                            # de (0, 10) à (10, 0) dans le sens direct : 270 °
        self.assertLess(min(x for x, _y in pts), -9.9)
        self.assertLess(min(y for _x, y in pts), -9.9)
        self.assertLess(max(x for x, _y in pts), 10.01)

    def test_composite_is_one_contour(self):
        a = line((0, 0, 0), (10, 0, 0), status='00010000')
        b = line((10, 0, 0), (10, 10, 0), status='00010000')
        k = line((10, 10, 0), (0, 0, 0), status='00010000')
        comp = Ent(102, [3, a, b, k])
        doc = iges.read(build([a, b, k, comp]))
        cs = contours(doc)
        self.assertEqual(len(cs), 1)
        self.assertTrue(cs[0].closed)
        self.assertAlmostEqual(area(cs[0]), 50.0)

    def test_composite_with_a_jump_is_two_contours(self):
        a = line((0, 0, 0), (10, 0, 0), status='00010000')
        b = line((50, 50, 0), (60, 50, 0), status='00010000')
        self.assertEqual(len(contours(iges.read(build([a, b, Ent(102, [2, a, b])])))), 2)

    def test_ellipse(self):
        # x²/25 + y²/4 = 1
        c = contours(iges.read(build([Ent(104, [4, 0, 25, 0, 0, -100, 0, 5, 0, 5, 0], form=1)])))[0]
        self.assertTrue(c.closed)
        self.assertAlmostEqual(area(c), math.pi * 10, delta=0.05)

    def test_rotated_ellipse_passes_through_its_ends(self):
        s = (3 * math.sqrt(0.5), 3 * math.sqrt(0.5))
        # x²/9 + y²/1 tournée de 45 ° : 5x² - 8xy + 5y² = 9
        c = contours(iges.read(build([Ent(104, [5, -8, 5, 0, 0, -9, 0, *s, *s], form=1)])))[0]
        box = c.bbox()
        self.assertAlmostEqual(area(c), math.pi * 3, delta=0.05)
        self.assertAlmostEqual(box[2], math.sqrt(5), delta=0.01)

    def test_parabola(self):
        # y = x² entre -1 et 1 : x² - y = 0
        c = contours(iges.read(build([Ent(104, [1, 0, 0, 0, -1, 0, 0, -1, 1, 1, 1], form=3)])))[0]
        pts = c.flatten(0.001)
        for x, y in pts:
            self.assertAlmostEqual(y, x * x, delta=0.002)
        self.assertLess(min(y for _x, y in pts), 0.01)

    def test_polyline_forms(self):
        doc = iges.read(build([Ent(106, [2, 3, 0, 0, 5, 10, 0, 5, 10, 10, 5], form=12)]))
        self.assertEqual(len(contours(doc)[0].segments), 2)
        doc = iges.read(build([Ent(106, [1, 3, 7, 0, 0, 10, 0, 10, 10], form=63)]))
        self.assertTrue(contours(doc)[0].closed)

    def test_point_cloud_is_reported(self):
        doc = iges.read(build([Ent(106, [1, 2, 0, 0, 0, 5, 5], form=1), line((0, 0, 0), (1, 0, 0))]))
        self.assertEqual(len(contours(doc)), 1)
        self.assertTrue(any('106' in r for r in doc.report))

    def test_parametric_spline(self):
        # x = t, y = t² entre 0 et 2
        params = [3, 2, 3, 1, 0, 2, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0] + [2, 1, 0, 0, 4, 4, 1, 0, 0, 0, 0, 0]
        c = contours(iges.read(build([Ent(112, params)])))[0]
        self.assertIsInstance(c.segments[0], Cubic)
        for x, y in c.flatten(0.001):
            self.assertAlmostEqual(y, x * x, delta=0.002)
        self.assertAlmostEqual(c.bbox()[3], 4.0)

    def test_nurbs_degree_1(self):
        p = [2, 1, 0, 0, 1, 0, 0, 0, 1, 2, 2, 1, 1, 1, 0, 0, 0, 5, 0, 0, 5, 5, 0, 0, 2, 0, 0, 1]
        c = contours(iges.read(build([Ent(126, p)])))[0]
        self.assertEqual(len(c.segments), 2)
        self.assertIsInstance(c.segments[0], Line)

    def test_nurbs_rational_arc_is_exact(self):
        w = math.sqrt(0.5)
        p = [2, 2, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, w, 1, 10, 0, 0, 10, 10, 0, 0, 10, 0, 0, 1, 0, 0, 1]
        c = contours(iges.read(build([Ent(126, p)])))[0]
        self.assertIsInstance(c.segments[0], Conic)
        self.assertAlmostEqual(c.segments[0].w, w)
        for x, y in c.flatten(0.0005):
            self.assertAlmostEqual(math.hypot(x, y), 10.0, delta=1e-6)

    def test_nurbs_cubic_gives_cubics(self):
        knots = [0, 0, 0, 0, 1, 2, 2, 2, 2]
        ctrl = [0, 0, 0, 1, 2, 0, 2, 3, 0, 4, 3, 0, 5, 1, 0]
        p = [4, 3, 0, 0, 1, 0, *knots, 1, 1, 1, 1, 1, *ctrl, 0, 2, 0, 0, 1]
        c = contours(iges.read(build([Ent(126, p)])))[0]
        self.assertEqual([type(s) for s in c.segments], [Cubic, Cubic])
        self.assertEqual(c.start, (0.0, 0.0))
        self.assertAlmostEqual(c.segments[-1].p3[0], 5.0)

    def test_nurbs_matches_de_boor(self):
        knots = np.array([0, 0, 0, 0, 1, 2, 3, 3, 3, 3], dtype=float)
        ctrl = np.array([[0, 0, 0], [1, 3, 0], [3, 3, 0], [4, 0, 0], [6, 1, 0], [7, 4, 0]], dtype=float)
        pieces = iges._bezier_pieces(3, knots, ctrl, np.ones(6), 0.0, 3.0)
        self.assertEqual(len(pieces), 3)
        surf_u, surf_n = iges._Nurbs._basis(knots, 3, 5, np.array([0.5]))
        expected = (surf_n[0][:, None] * ctrl[surf_u[0] - 3:surf_u[0] + 1]).sum(axis=0)
        got = pieces[0].points(2)[1]
        self.assertAlmostEqual(float(np.linalg.norm(got - expected)), 0.0, places=9)

    def test_nurbs_range_is_followed(self):
        p = [1, 1, 1, 0, 1, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 10, 0, 0, 0.2, 0.7, 0, 0, 1]
        c = contours(iges.read(build([Ent(126, p)])))[0]
        box = c.bbox()
        self.assertAlmostEqual(box[0], 2.0)
        self.assertAlmostEqual(box[2], 7.0)

    def test_unclamped_nurbs(self):
        p = [3, 2, 0, 0, 1, 0, 0, 1, 2, 3, 4, 5, 6, 1, 1, 1, 1, 0, 0, 0, 2, 3, 0, 4, 3, 0, 6, 0, 0, 2, 4, 0, 0, 1]
        c = contours(iges.read(build([Ent(126, p)])))[0]
        self.assertAlmostEqual(c.start[0], 1.0)
        self.assertAlmostEqual(c.start[1], 1.5)


class Structure(unittest.TestCase):
    def test_matrix(self):
        m = Ent(124, [0, -1, 0, 100, 1, 0, 0, 0, 0, 0, 1, 0])
        doc = iges.read(build([m, line((0, 0, 0), (10, 0, 0), matrix=m)]))
        box = doc.bbox(include_plate=False)
        self.assertAlmostEqual(box[0], 100.0)
        self.assertAlmostEqual(box[3], 10.0)

    def test_matrix_of_a_matrix(self):
        outer = Ent(124, [1, 0, 0, 5, 0, 1, 0, 0, 0, 0, 1, 0])
        inner = Ent(124, [1, 0, 0, 0, 0, 1, 0, 7, 0, 0, 1, 0], matrix=outer)
        doc = iges.read(build([outer, inner, line((0, 0, 0), (1, 0, 0), matrix=inner)]))
        box = doc.bbox(include_plate=False)
        self.assertAlmostEqual(box[0], 5.0)
        self.assertAlmostEqual(box[1], 7.0)

    def test_blanked_and_dependent_stay_out(self):
        ents = [line((0, 0, 0), (1, 0, 0), status='01000000'), line((0, 0, 0), (2, 0, 0), status='00010000'),
                line((0, 0, 0), (3, 0, 0), status='00000500'), line((0, 0, 0), (4, 0, 0))]
        self.assertEqual(iges.read(build(ents)).bbox(include_plate=False)[2], 4.0)

    def test_levels_become_layers(self):
        doc = iges.read(build([line((0, 0, 0), (1, 0, 0), level=3), line((0, 5, 0), (1, 5, 0), level=8)]))
        self.assertEqual([L.name for L in doc.layers], ['IGES niveau 3', 'IGES niveau 8'])

    def test_touching_curves_are_joined(self):
        doc = iges.read(build([line((0, 0, 0), (10, 0, 0)), line((10, 0, 0), (10, 10, 0)), line((10, 10, 0), (0, 0, 0))]))
        cs = contours(doc)
        self.assertEqual(len(cs), 1)
        self.assertTrue(cs[0].closed)
        self.assertTrue(any('raccord' in r for r in doc.report))

    def test_subfigure(self):
        a = line((0, 0, 0), (10, 0, 0), status='00000200')
        fig = Ent(308, [0, '1Hf', 1, a], status='00000200')
        inst = Ent(408, [fig, 100, 50, 0, 2.0])
        doc = iges.read(build([a, fig, inst]))
        self.assertEqual(doc.bbox(include_plate=False), (100.0, 50.0, 120.0, 50.0))

    def test_nested_subfigure(self):
        a = line((0, 0, 0), (1, 0, 0), status='00000200')
        low = Ent(308, [0, '1Hf', 1, a], status='00000200')
        mid = Ent(408, [low, 10, 0, 0, 1.0], status='00000200')
        top = Ent(308, [1, '1Hg', 1, mid], status='00000200')
        doc = iges.read(build([a, low, mid, top, Ent(408, [top, 0, 20, 0, 1.0])]))
        self.assertEqual(doc.bbox(include_plate=False), (10.0, 20.0, 11.0, 20.0))

    def test_cycle_does_not_hang(self):
        comp = Ent(102, [1, 1])                          # se désigne elle-même
        iges.read(build([comp]))

    def test_fortran_exponents_and_strings(self):
        self.assertEqual(iges._num('1.5D+01'), 15.0)
        self.assertEqual(iges._fields('2Ha,,3.,5Hb;c,d;x', ',', ';'), ['a,', '3.', 'b;c,d'])

    def test_other_delimiters(self):
        head = "1H||1H!|3Hsrc|5Ha.igs|1Hx|1Hy|32|38|6|308|15||1.|1|2HIN|1|1.|15H20260101.000000|0.001|100.|1Ha|1Hb|11|0|15H20260101.000000!"
        path = build([line((0, 0, 0), (1, 0, 0))], head=head)
        self.assertAlmostEqual(iges._Reader(path).unit, 25.4)

    def test_broken_entity_is_reported(self):
        doc = iges.read(build([Ent(126, [2, 2]), line((0, 0, 0), (1, 0, 0))]))
        self.assertEqual(len(contours(doc)), 1)
        self.assertTrue(any('126' in r for r in doc.report))

    def test_empty_file_refused(self):
        p = os.path.join(tempfile.mkdtemp(), 'v.igs')
        with open(p, 'w', encoding='latin-1') as fh:
            fh.write('rien du tout\n')
        with self.assertRaises(ValueError):
            iges.read(p)

    def test_file_without_geometry_keeps_a_layer(self):
        doc = iges.read(build([Ent(124, [1, 0, 0, 5, 0, 1, 0, 0, 0, 0, 1, 0])]))
        self.assertEqual(len(doc.layers), 1)


class Units(unittest.TestCase):
    def test_inches(self):
        box = iges.read(build([line((0, 0, 0), (1, 0, 0))], unit=1, unit_name='2HIN')).bbox(include_plate=False)
        self.assertAlmostEqual(box[2], 25.4)

    def test_centimetres(self):
        box = iges.read(build([line((0, 0, 0), (3, 0, 0))], unit=10, unit_name='2HCM')).bbox(include_plate=False)
        self.assertAlmostEqual(box[2], 30.0)

    def test_named_unit(self):
        box = iges.read(build([line((0, 0, 0), (1, 0, 0))], unit=3, unit_name='2HFT')).bbox(include_plate=False)
        self.assertAlmostEqual(box[2], 304.8)

    def test_real_metres(self):
        box = iges.read(build([line((0, 0, 0), (0.5, 0, 0))], unit=6, unit_name='1HM')).bbox(include_plate=False)
        self.assertAlmostEqual(box[2], 500.0)

    def test_absurd_size_read_as_millimetres(self):
        doc = iges.read(build([line((0, 0, 0), (280, 0, 0))], unit=6, unit_name='1HM'))
        self.assertAlmostEqual(doc.bbox(include_plate=False)[2], 280.0)
        self.assertTrue(any('millim' in r for r in doc.report))

    def test_surface_uses_the_same_rule(self):
        surf = plane_patch(0, 0, 1, 1)
        surf.status = '00000000'
        box = iges.read(build([surf], unit=1, unit_name='2HIN')).bbox(include_plate=False)
        self.assertAlmostEqual(box[2], 25.4, delta=0.001)


class Surfaces(unittest.TestCase):
    def _trim(self, surf, outer=None, holes=()):
        n1 = 1 if outer else 0
        return Ent(144, [surf, n1, len(holes), outer or 0, *holes])

    def _boundary(self, surf, pcurve=None, model=None):
        return Ent(142, [0, surf, pcurve or 0, model or 0, 1], status='00010000')

    def test_whole_patch(self):
        surf = plane_patch(0, 0, 20, 10, z=5.0)
        surf.status = '00000000'
        doc = iges.read(build([surf]))
        self.assertTrue(by_name(doc, 'Pz 5'))
        c = by_name(doc, 'Silhouette')[0].items[0].path.contours[0]
        self.assertAlmostEqual(area(c), 200.0, delta=0.5)

    def test_level_needs_a_flat_face(self):
        # surface de degré 2 : bombée, une partie de ses triangles presque à plat au sommet
        k = [0, 0, 0, 1, 1, 1]
        w = [1] * 9
        p = []
        for j, y in enumerate((0, 10, 20)):
            for i, x in enumerate((0, 10, 20)):
                p += [x, y, 6.0 if (i == 1 and j == 1) else 0.0]
        surf = Ent(128, [2, 2, 2, 2, 0, 0, 1, 0, 0, *k, *k, *w, *p, 0, 1, 0, 1])
        doc = iges.read(build([surf]))
        self.assertFalse(by_name(doc, 'Pz'))
        self.assertTrue(by_name(doc, 'Silhouette'))

    def test_trimmed_with_a_hole(self):
        surf = plane_patch(0, 0, 100, 100)
        hole = Ent(100, [0, 0.5, 0.5, 0.75, 0.5, 0.75, 0.5], status='00010500')
        bound = self._boundary(surf, hole)
        doc = iges.read(build([surf, hole, bound, self._trim(surf, holes=[bound])]))
        polys = by_name(doc, 'Silhouette')[0].items[0].path.contours
        self.assertEqual(len(polys), 2)
        total = sum(sorted(area(c) for c in polys)[i] * s for i, s in ((1, 1), (0, -1)))
        self.assertAlmostEqual(total, 10000 - math.pi * 625, delta=20.0)

    def test_trimmed_outside(self):
        surf = plane_patch(0, 0, 100, 100)
        ring = Ent(106, [1, 5, 0, 0.25, 0.25, 0.75, 0.25, 0.75, 0.75, 0.25, 0.75, 0.25, 0.25], form=11, status='00010500')
        bound = self._boundary(surf, ring)
        doc = iges.read(build([surf, ring, bound, self._trim(surf, outer=bound)]))
        box = doc.bbox(include_plate=False)
        self.assertAlmostEqual(box[0], 25.0, delta=0.1)
        self.assertAlmostEqual(box[2], 75.0, delta=0.1)

    def test_boundary_given_only_in_3d(self):
        surf = plane_patch(0, 0, 100, 100)
        ring = Ent(106, [2, 5, 20, 20, 0, 60, 20, 0, 60, 60, 0, 20, 60, 0, 20, 20, 0], form=12, status='00010000')
        bound = self._boundary(surf, None, ring)
        doc = iges.read(build([surf, ring, bound, self._trim(surf, outer=bound)]))
        c = by_name(doc, 'Silhouette')[0].items[0].path.contours[0]
        self.assertAlmostEqual(area(c), 1600.0, delta=4.0)

    def test_surface_under_a_matrix(self):
        m = Ent(124, [1, 0, 0, 1000, 0, 1, 0, 0, 0, 0, 1, 0])
        surf = plane_patch(0, 0, 10, 10)
        surf.matrix = m
        surf.status = '00000000'
        self.assertAlmostEqual(iges.read(build([m, surf])).bbox(include_plate=False)[0], 1000.0, delta=0.01)

    def test_rational_cylinder_is_accurate(self):
        w = math.sqrt(0.5)
        k = [0, 0, 0, 1, 1, 1]
        kv = [0, 0, 1, 1]
        wts = [1, w, 1, 1, w, 1]
        ctrl = [10, 0, 0, 10, 10, 0, 0, 10, 0, 10, 0, 30, 10, 10, 30, 0, 10, 30]
        surf = Ent(128, [2, 1, 2, 1, 0, 0, 0, 0, 0, *k, *kv, *wts, *ctrl, 0, 1, 0, 1])
        tris = iges.triangles(build([surf]))
        self.assertGreater(len(tris), 8)
        for x, y, _z in tris.reshape(-1, 3):
            self.assertAlmostEqual(math.hypot(x, y), 10.0, delta=1e-6)

    def test_mesh_is_close_to_the_surface(self):
        # un quart de cylindre de rayon 10 : la flèche du maillage reste sous la tolérance demandée
        w = math.sqrt(0.5)
        k = [0, 0, 0, 1, 1, 1]
        kv = [0, 0, 1, 1]
        wts = [1, w, 1, 1, w, 1]
        ctrl = [10, 0, 0, 10, 10, 0, 0, 10, 0, 10, 0, 30, 10, 10, 30, 0, 10, 30]
        surf = Ent(128, [2, 1, 2, 1, 0, 0, 0, 0, 0, *k, *kv, *wts, *ctrl, 0, 1, 0, 1])
        tris = iges.triangles(build([surf]))
        mids = tris[:, [0, 1, 2]].mean(axis=1)
        self.assertGreater(float(np.hypot(mids[:, 0], mids[:, 1]).min()), 10.0 - 0.05)

    def test_solid_face_with_3d_edges(self):
        surf = plane_patch(0, 0, 100, 100, z=3.0)
        c1 = line((10, 10, 3), (50, 10, 3), status='00010000')
        c2 = line((50, 10, 3), (50, 50, 3), status='00010000')
        c3 = line((50, 50, 3), (10, 50, 3), status='00010000')
        c4 = line((10, 50, 3), (10, 10, 3), status='00010000')
        verts = Ent(502, [4, 10, 10, 3, 50, 10, 3, 50, 50, 3, 10, 50, 3], form=1, status='00010000')
        edges = Ent(504, [4, c1, verts, 1, verts, 2, c2, verts, 2, verts, 3, c3, verts, 3, verts, 4, c4, verts, 4, verts, 1],
                    form=1, status='00010000')
        loop = Ent(508, [4, 0, edges, 1, 1, 0, 0, edges, 2, 1, 0, 0, edges, 3, 1, 0, 0, edges, 4, 1, 0], form=1, status='00010000')
        face = Ent(510, [surf, 1, 1, loop], form=1, status='00010000')
        shell = Ent(514, [1, face, 1], form=1, status='00010000')
        solid = Ent(186, [shell, 1, 0])
        doc = iges.read(build([surf, c1, c2, c3, c4, verts, edges, loop, face, shell, solid]))
        c = by_name(doc, 'Silhouette')[0].items[0].path.contours[0]
        self.assertAlmostEqual(area(c), 1600.0, delta=4.0)
        self.assertTrue(by_name(doc, 'Pz 3'))

    def test_solid_face_with_parameter_curves(self):
        surf = plane_patch(0, 0, 100, 100)
        ring = Ent(106, [1, 5, 0, 0.1, 0.1, 0.5, 0.1, 0.5, 0.5, 0.1, 0.5, 0.1, 0.1], form=11, status='00010500')
        c = line((0, 0, 0), (1, 0, 0), status='00010000')
        verts = Ent(502, [1, 0, 0, 0], form=1, status='00010000')
        edges = Ent(504, [1, c, verts, 1, verts, 1], form=1, status='00010000')
        loop = Ent(508, [1, 0, edges, 1, 1, 1, 0, ring], form=1, status='00010000')
        face = Ent(510, [surf, 1, 1, loop], form=1)
        doc = iges.read(build([surf, ring, c, verts, edges, loop, face]))
        box = doc.bbox(include_plate=False)
        self.assertAlmostEqual(box[0], 10.0, delta=0.1)
        self.assertAlmostEqual(box[2], 50.0, delta=0.1)

    def test_downward_solid_face_gives_no_level(self):
        surf = plane_patch(0, 0, 10, 10, z=2.0)
        verts = Ent(502, [1, 0, 0, 0], form=1, status='00010000')
        c = line((0, 0, 2), (1, 0, 2), status='00010000')
        edges = Ent(504, [1, c, verts, 1, verts, 1], form=1, status='00010000')
        face_same = Ent(510, [surf, 0, 0], form=1, status='00010000')
        shell = Ent(514, [1, face_same, 0], form=1, status='00010000')
        doc = iges.read(build([surf, verts, c, edges, face_same, shell, Ent(186, [shell, 1, 0])]))
        self.assertFalse(by_name(doc, 'Pz'))
        self.assertTrue(by_name(doc, 'Silhouette'))

    def test_unread_surface_type_is_reported(self):
        doc = iges.read(build([Ent(120, [0, 0, 0, 0, 0, 1, 0, 3.14])]))
        self.assertTrue(any('120' in r for r in doc.report))

    def test_trimmed_unread_surface_is_reported(self):
        other = Ent(122, [0, 0, 0, 1], status='00010000')
        doc = iges.read(build([other, Ent(144, [other, 0, 0, 0])]))
        self.assertTrue(any('122' in r for r in doc.report))

    def test_broken_surface_is_reported(self):
        doc = iges.read(build([Ent(128, [1, 1, 1, 1, 0, 0, 1, 0, 0, 0, 0])]))
        self.assertTrue(any('128' in r for r in doc.report))

    def test_curves_and_surfaces_together(self):
        surf = plane_patch(0, 0, 10, 10)
        surf.status = '00000000'
        doc = iges.read(build([surf, line((0, 0, 0), (20, 20, 0))]))
        self.assertEqual(doc.layers[0].name, 'IGES')
        self.assertTrue(by_name(doc, 'Silhouette'))


class Wiring(unittest.TestCase):
    def test_registry(self):
        self.assertIs(registry.by_extension('a.igs'), registry.by_extension('a.IGES'))
        self.assertIsNotNone(registry.by_extension('piece.igs'))
        self.assertIsNotNone(registry.by_extension('piece.igs').writer)     # round 947 : l'IGES s'écrit aussi
        self.assertIn('*.igs', registry.filter_string())

    def test_open_through_the_registry(self):
        doc = registry.open_document(build([line((0, 0, 0), (1, 0, 0))]))
        self.assertEqual(len(contours(doc)), 1)

    def test_3d_model(self):
        surf = plane_patch(0, 0, 10, 10)
        surf.status = '00000000'
        m = model3d.load(build([surf]))
        self.assertGreaterEqual(len(m.triangles), 2)
        self.assertTrue(model3d._is_3d(build([surf])))

    def test_3d_model_without_surface_refused(self):
        with self.assertRaises(ValueError):
            model3d.load(build([line((0, 0, 0), (1, 0, 0))]))

    def test_top_view_defaults_unchanged(self):
        t = np.array([[[0, 0, 1], [1, 0, 1], [1, 1, 1]], [[0, 0, 1], [1, 1, 1], [0, 1, 1]]], dtype=float)
        doc = mesh3d.top_view(t)
        self.assertEqual([L.name for L in doc.layers], ['Pz 1', 'Silhouette'])
        doc = mesh3d.top_view(t, flat=np.array([False, False]))
        self.assertEqual([L.name for L in doc.layers], ['Silhouette'])

    def test_close_fills_a_crack(self):
        a = [[0, 0, 0], [1, 0, 0], [1, 1, 0]]
        b = [[1.01, 0, 0], [2, 0, 0], [2, 1, 0]]
        c = [[1.01, 0, 0], [2, 1, 0], [1.01, 1, 0]]
        d = [[0, 0, 0], [1, 1, 0], [0, 1, 0]]
        t = np.array([a, d, b, c], dtype=float)
        apart = mesh3d.top_view(t, flat=np.zeros(4, dtype=bool))
        joined = mesh3d.top_view(t, flat=np.zeros(4, dtype=bool), close=0.02)
        self.assertEqual(len(apart.layers[0].items[0].path.contours), 2)
        self.assertEqual(len(joined.layers[0].items[0].path.contours), 1)


if __name__ == '__main__':
    unittest.main()
