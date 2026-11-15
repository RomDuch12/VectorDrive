"""Round 808 : IGES, surfaces 108 (plan), 118 (réglée), 120 (révolution) et 122 (cylindre tabulé).

Tous les fichiers sont écrits à la main : l'aire du maillage se compare à la formule."""
import math
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')

import numpy as np

from tests.test_round777 import Ent, area, build, by_name, line, plane_patch
from vectordrive.io import iges

DEP = '00010000'                                         # dépendante : pas dessinée pour elle-même
PAR = '00010500'                                         # courbe dans (u, v)


def mesh_area(tris):
    return 0.5 * float(np.linalg.norm(np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]), axis=1).sum())


def poly3d(points):
    flat = [c for p in points for c in p]
    return Ent(106, [2, len(points), *flat], form=12, status=DEP)


def poly2d(points):
    flat = [c for p in points for c in p]
    return Ent(106, [1, len(points), 0, *flat], form=11, status=PAR)


def dep_line(a, b):
    return line(a, b, status=DEP)


def arc_xy(r, a0, a1, z=0.0, n=128):
    return [(r * math.cos(a0 + (a1 - a0) * i / n), r * math.sin(a0 + (a1 - a0) * i / n), z) for i in range(n + 1)]


def trimmed(surf, *rings):
    """Une face 144, avec ses courbes : le premier bord à l'extérieur, les suivants en trous."""
    bounds = [Ent(142, [0, surf, b or 0, c or 0, 1], status=DEP) for b, c in rings]
    face = Ent(144, [surf, 1, len(bounds) - 1, bounds[0], *bounds[1:]])
    return [*[c for ring in rings for c in ring if c is not None], *bounds, face]


def faces(surf_ents, *rings):
    return [*surf_ents, *trimmed(surf_ents[-1], *rings)]


def cylinder_parts(r=10.0, h=20.0, sa=0.0, ta=2 * math.pi):
    axis = dep_line((0, 0, 0), (0, 0, 1))
    gen = dep_line((r, 0, 0), (r, 0, h))
    surf = Ent(120, [axis, gen, sa, ta], status=DEP)
    return [axis, gen, surf]


class Tabulated(unittest.TestCase):
    def test_flat_wall(self):
        d = dep_line((0, 0, 0), (20, 0, 0))
        t = iges.triangles(build([d, Ent(122, [d, 0, 0, 10])]))
        self.assertAlmostEqual(mesh_area(t), 200.0, places=6)
        self.assertAlmostEqual(float(t[:, :, 2].max()), 10.0, places=9)

    def test_cylinder(self):
        d = Ent(100, [0, 0, 0, 10, 0, 10, 0], status=DEP)
        t = iges.triangles(build([d, Ent(122, [d, 10, 0, 25])]))
        self.assertAlmostEqual(mesh_area(t), 2 * math.pi * 10 * 25, delta=1.0)

    def test_slanted_generatrix(self):
        d = dep_line((0, 0, 0), (20, 0, 0))
        t = iges.triangles(build([d, Ent(122, [d, 5, 0, 10])]))
        self.assertAlmostEqual(mesh_area(t), 200.0, places=6)
        self.assertAlmostEqual(float(t[:, :, 0].max()), 25.0, places=9)

    def test_matrix(self):
        m = Ent(124, [1, 0, 0, 100, 0, 1, 0, 0, 0, 0, 1, 0])
        d = dep_line((0, 0, 0), (20, 0, 0))
        t = iges.triangles(build([m, d, Ent(122, [d, 0, 0, 10], matrix=m)]))
        self.assertAlmostEqual(float(t[:, :, 0].min()), 100.0, places=9)

    def test_trimmed_in_parameters(self):
        d = dep_line((0, 0, 0), (20, 0, 0))
        surf = Ent(122, [d, 0, 0, 10], status=DEP)
        ring = poly2d([(0, 0), (0.5, 0), (0.5, 1), (0, 1), (0, 0)])
        t = iges.triangles(build(faces([d, surf], (ring, None))))
        self.assertAlmostEqual(mesh_area(t), 100.0, places=6)

    def test_trimmed_in_3d(self):
        d = dep_line((0, 0, 0), (20, 0, 0))
        surf = Ent(122, [d, 0, 0, 10], status=DEP)
        ring = poly3d([(5, 0, 0), (15, 0, 0), (15, 0, 10), (5, 0, 10), (5, 0, 0)])
        t = iges.triangles(build(faces([d, surf], (None, ring))))
        self.assertAlmostEqual(mesh_area(t), 100.0, delta=0.01)

    def test_nurbs_directrix_follows_its_parameter(self):
        # degré 1, nœuds inégaux : u = 0,25 tombe au milieu de la courbe, pas au quart de sa longueur
        d = Ent(126, [2, 1, 1, 0, 0, 0, 0, 0, 0.25, 1, 1, 1, 1, 1, 0, 0, 0, 10, 0, 0, 20, 0, 0, 0, 1, 0, 0, 1],
                status=DEP)
        surf = Ent(122, [d, 0, 0, 10], status=DEP)
        ring = poly2d([(0, 0), (0.25, 0), (0.25, 1), (0, 1), (0, 0)])
        t = iges.triangles(build(faces([d, surf], (ring, None))))
        self.assertAlmostEqual(mesh_area(t), 100.0, places=6)
        self.assertAlmostEqual(float(t[:, :, 0].max()), 10.0, places=9)

    def test_ring_across_the_seam(self):
        d = Ent(100, [0, 0, 0, 10, 0, 10, 0], status=DEP)
        surf = Ent(122, [d, 10, 0, 25], status=DEP)
        pts = arc_xy(10, -math.pi / 4, math.pi / 4) + arc_xy(10, math.pi / 4, -math.pi / 4, z=25)
        ring = poly3d([*pts, pts[0]])
        t = iges.triangles(build(faces([d, surf], (None, ring))))
        self.assertAlmostEqual(mesh_area(t), math.pi / 2 * 10 * 25, delta=1.0)
        self.assertGreater(float(t[:, :, 0].min()), 7.0)


class Ruled(unittest.TestCase):
    def test_two_lines(self):
        a, b = dep_line((0, 0, 0), (10, 0, 0)), dep_line((0, 0, 5), (10, 0, 5))
        t = iges.triangles(build([a, b, Ent(118, [a, b, 0, 1], form=1)]))
        self.assertAlmostEqual(mesh_area(t), 50.0, places=6)

    def test_first_to_last(self):
        a, b = dep_line((0, 0, 0), (10, 0, 0)), dep_line((0, 0, 5), (10, 0, 5))
        path = build([a, b, Ent(118, [a, b, 1, 0], form=1)])
        r = iges._Reader(path)
        surf, _m = r._nurbs(5)
        np.testing.assert_allclose(surf.eval([0.0], [1.0])[0], (10, 0, 5))
        np.testing.assert_allclose(surf.eval([1.0], [1.0])[0], (0, 0, 5))
        np.testing.assert_allclose(surf.eval([0.5], [0.5])[0], (5, 0, 2.5))

    def test_equal_parameter_and_equal_length(self):
        def nurbs():
            return Ent(126, [2, 1, 1, 0, 0, 0, 0, 0, 0.25, 1, 1, 1, 1, 1, 0, 0, 0, 10, 0, 0, 20, 0, 0, 0, 1, 0, 0, 1],
                       status=DEP)
        for form, x in ((1, 10.0), (0, 5.0)):
            a, b = nurbs(), dep_line((0, 5, 0), (20, 5, 0))
            r = iges._Reader(build([a, b, Ent(118, [a, b, 0, 0], form=form)]))
            surf, _m = r._nurbs(5)
            self.assertAlmostEqual(float(surf.eval([0.25], [0.0])[0, 0]), x, places=6)

    def test_frustum_between_two_circles(self):
        a = Ent(100, [0, 0, 0, 10, 0, 10, 0], status=DEP)
        b = Ent(100, [8, 0, 0, 5, 0, 5, 0], status=DEP)
        t = iges.triangles(build([a, b, Ent(118, [a, b, 0, 0], form=1)]))
        slant = math.hypot(5, 8)
        self.assertAlmostEqual(mesh_area(t), math.pi * (10 + 5) * slant, delta=1.0)

    def test_trimmed_in_3d(self):
        a, b = dep_line((0, 0, 0), (10, 0, 0)), dep_line((0, 0, 5), (10, 0, 5))
        surf = Ent(118, [a, b, 0, 1], form=1, status=DEP)
        ring = poly3d([(2, 0, 0), (8, 0, 0), (8, 0, 5), (2, 0, 5), (2, 0, 0)])
        t = iges.triangles(build(faces([a, b, surf], (None, ring))))
        self.assertAlmostEqual(mesh_area(t), 30.0, delta=0.01)


class Revolution(unittest.TestCase):
    def whole(self, gen, axis=((0, 0, 0), (0, 0, 1)), sa=0.0, ta=2 * math.pi):
        ax = dep_line(*axis)
        return iges.triangles(build([ax, gen, Ent(120, [ax, gen, sa, ta])]))

    def test_cylinder(self):
        t = self.whole(dep_line((10, 0, 0), (10, 0, 20)))
        self.assertAlmostEqual(mesh_area(t), 2 * math.pi * 10 * 20, delta=1.0)
        self.assertLess(abs(float(np.hypot(t[:, :, 0], t[:, :, 1]).max()) - 10.0), 1e-9)

    def test_frustum(self):
        t = self.whole(dep_line((10, 0, 0), (5, 0, 8)))
        self.assertAlmostEqual(mesh_area(t), math.pi * 15 * math.hypot(5, 8), delta=1.0)

    def test_disc(self):
        t = self.whole(dep_line((0, 0, 4), (10, 0, 4)))
        self.assertAlmostEqual(mesh_area(t), math.pi * 100, delta=0.5)

    def test_sphere(self):
        gen = Ent(100, [0, 0, 0, 0, -10, 0, 10], status=DEP)
        t = self.whole(gen, axis=((0, -1, 0), (0, 1, 0)))
        self.assertAlmostEqual(mesh_area(t), 4 * math.pi * 100, delta=2.0)

    def test_partial_turn_and_its_sense(self):
        t = self.whole(dep_line((10, 0, 0), (10, 0, 20)), ta=math.pi / 2)
        self.assertAlmostEqual(mesh_area(t), math.pi / 2 * 10 * 20, delta=0.5)
        self.assertGreater(float(t[:, :, 1].min()), -1e-9)       # autour de +Z, de +X vers +Y
        self.assertGreater(float(t[:, :, 0].min()), -1e-9)

    def test_axis_elsewhere_and_tilted(self):
        o = np.array((3.0, -4.0, 7.0))
        k = np.array((1.0, 1.0, 0.0)) / math.sqrt(2)
        n = np.array((0.0, 0.0, 1.0))
        a, b = o + n * 10, o + n * 10 + k * 30
        t = self.whole(dep_line(a, b), axis=(tuple(o), tuple(o + k)))
        self.assertAlmostEqual(mesh_area(t), 2 * math.pi * 10 * 30, delta=1.5)
        q = t.reshape(-1, 3) - o
        d = np.linalg.norm(q - (q @ k)[:, None] * k, axis=1)
        self.assertLess(float(np.abs(d - 10).max()), 1e-6)

    def test_silhouette_of_a_cone_is_a_circle(self):
        ax, gen = dep_line((0, 0, 0), (0, 0, 1)), dep_line((0, 0, 10), (10, 0, 0))
        doc = iges.read(build([ax, gen, Ent(120, [ax, gen, 0, 2 * math.pi])]))
        c = by_name(doc, 'Silhouette')[0].items[0].path.contours[0]
        self.assertAlmostEqual(area(c), math.pi * 100, delta=1.0)
        self.assertFalse(any('120' in r for r in doc.report))

    def test_inches_give_the_same_tolerance(self):
        ax, gen = dep_line((0, 0, 0), (0, 0, 1)), dep_line((1, 0, 0), (1, 0, 1))
        t = iges.triangles(build([ax, gen, Ent(120, [ax, gen, 0, 2 * math.pi])], unit=1, unit_name='2HIN'))
        self.assertAlmostEqual(mesh_area(t), 2 * math.pi * 25.4 * 25.4, delta=2.0)
        mid = t.mean(axis=1)
        self.assertGreater(float(np.hypot(mid[:, 0], mid[:, 1]).min()), 25.4 - 0.02)


class RevolutionTrimmed(unittest.TestCase):
    def test_in_parameters(self):
        parts = cylinder_parts()
        ring = poly2d([(0, 0), (1, 0), (1, math.pi / 2), (0, math.pi / 2), (0, 0)])
        t = iges.triangles(build(faces(parts, (ring, None))))
        self.assertAlmostEqual(mesh_area(t), math.pi / 2 * 10 * 20, delta=0.5)
        self.assertGreater(float(t[:, :, 1].min()), -1e-9)

    def test_arc_generatrix_in_parameters(self):
        # le paramètre d'un arc est son angle : ici la moitié haute d'une sphère
        ax = dep_line((0, -1, 0), (0, 1, 0))
        gen = Ent(100, [0, 0, 0, 0, -10, 0, 10], status=DEP)
        surf = Ent(120, [ax, gen, 0, 2 * math.pi], status=DEP)
        ring = poly2d([(0, 0), (math.pi / 2, 0), (math.pi / 2, 2 * math.pi), (0, 2 * math.pi), (0, 0)])
        t = iges.triangles(build(faces([ax, gen, surf], (ring, None))))
        self.assertAlmostEqual(mesh_area(t), 2 * math.pi * 100, delta=2.0)
        self.assertGreater(float(t[:, :, 1].min()), -1e-6)

    def test_in_3d(self):
        parts = cylinder_parts()
        pts = arc_xy(10, 0, math.pi / 2) + arc_xy(10, math.pi / 2, 0, z=20)
        t = iges.triangles(build(faces(parts, (None, poly3d([*pts, pts[0]])))))
        self.assertAlmostEqual(mesh_area(t), math.pi / 2 * 10 * 20, delta=0.5)

    def test_3d_wins_over_parameters(self):
        parts = cylinder_parts()
        pts = arc_xy(10, 0, math.pi / 2) + arc_xy(10, math.pi / 2, 0, z=20)
        wrong = poly2d([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
        t = iges.triangles(build(faces(parts, (wrong, poly3d([*pts, pts[0]])))))
        self.assertAlmostEqual(mesh_area(t), math.pi / 2 * 10 * 20, delta=0.5)

    def test_across_the_seam(self):
        parts = cylinder_parts()
        pts = arc_xy(10, -math.pi / 4, math.pi / 4) + arc_xy(10, math.pi / 4, -math.pi / 4, z=20)
        t = iges.triangles(build(faces(parts, (None, poly3d([*pts, pts[0]])))))
        self.assertAlmostEqual(mesh_area(t), math.pi / 2 * 10 * 20, delta=0.5)
        self.assertGreater(float(t[:, :, 0].min()), 7.0)         # le bon côté de la couture

    def test_full_turn_with_its_seam(self):
        parts = cylinder_parts()
        pts = arc_xy(10, 0, 2 * math.pi) + arc_xy(10, 2 * math.pi, 0, z=20)
        t = iges.triangles(build(faces(parts, (None, poly3d([*pts, pts[0]])))))
        self.assertAlmostEqual(mesh_area(t), 2 * math.pi * 10 * 20, delta=1.0)

    def test_clockwise_ring(self):
        parts = cylinder_parts()
        pts = arc_xy(10, math.pi / 2, 0) + arc_xy(10, 0, math.pi / 2, z=20)
        t = iges.triangles(build(faces(parts, (None, poly3d([*pts, pts[0]])))))
        self.assertAlmostEqual(mesh_area(t), math.pi / 2 * 10 * 20, delta=0.5)

    def test_ring_through_the_apex_of_a_cone(self):
        ax, gen = dep_line((0, 0, 0), (0, 0, 1)), dep_line((0, 0, 10), (10, 0, 0))
        surf = Ent(120, [ax, gen, 0, 2 * math.pi], status=DEP)
        pts = arc_xy(10, 0, math.pi / 2)
        ring = poly3d([*pts, (0, 0, 10), pts[0]])
        t = iges.triangles(build(faces([ax, gen, surf], (None, ring))))
        self.assertAlmostEqual(mesh_area(t), math.pi * 10 * math.hypot(10, 10) / 4, delta=0.5)

    def test_straight_edges_on_a_disc(self):
        ax, gen = dep_line((0, 0, 0), (0, 0, 1)), dep_line((0, 0, 4), (10, 0, 4))
        surf = Ent(120, [ax, gen, 0, 2 * math.pi], status=DEP)
        ring = poly3d([(5, 1, 4), (8, 1, 4), (8, 5, 4), (5, 5, 4), (5, 1, 4)])
        t = iges.triangles(build(faces([ax, gen, surf], (None, ring))))
        self.assertAlmostEqual(mesh_area(t), 12.0, delta=0.05)
        self.assertLess(float(t[:, :, 0].max()), 8.01)

    def test_a_hole(self):
        parts = cylinder_parts()
        pts = arc_xy(10, 0, math.pi / 2) + arc_xy(10, math.pi / 2, 0, z=20)
        n = 40
        rim = []
        for i in range(n + 1):
            a = 2 * math.pi * i / n
            th = math.pi / 4 + 0.2 * math.cos(a)
            rim.append((10 * math.cos(th), 10 * math.sin(th), 10 + 2 * math.sin(a)))
        t = iges.triangles(build(faces(parts, (None, poly3d([*pts, pts[0]])), (None, poly3d(rim)))))
        self.assertAlmostEqual(mesh_area(t), math.pi / 2 * 10 * 20 - math.pi * 2 * 2, delta=0.7)

    def test_bounded_143(self):
        parts = cylinder_parts()
        pts = arc_xy(10, 0, math.pi / 2) + arc_xy(10, math.pi / 2, 0, z=20)
        ring = poly3d([*pts, pts[0]])
        bound = Ent(141, [0, 0, parts[-1], 1, ring, 1, 0], status=DEP)
        t = iges.triangles(build([*parts, ring, bound, Ent(143, [0, parts[-1], 1, bound])]))
        self.assertAlmostEqual(mesh_area(t), math.pi / 2 * 10 * 20, delta=0.5)

    def test_solid_face_510(self):
        parts = cylinder_parts()
        pts = arc_xy(10, 0, math.pi / 2) + arc_xy(10, math.pi / 2, 0, z=20)
        ring = poly3d([*pts, pts[0]])
        verts = Ent(502, [1, *pts[0]], form=1, status=DEP)
        edges = Ent(504, [1, ring, verts, 1, verts, 1], form=1, status=DEP)
        loop = Ent(508, [1, 0, edges, 1, 1, 0], form=1, status=DEP)
        face = Ent(510, [parts[-1], 1, 1, loop], form=1)
        t = iges.triangles(build([*parts, ring, verts, edges, loop, face]))
        self.assertAlmostEqual(mesh_area(t), math.pi / 2 * 10 * 20, delta=0.5)


class Plane(unittest.TestCase):
    def test_trimmed_with_a_hole(self):
        surf = Ent(108, [0, 0, 1, 5, 0, 0, 0, 0, 0], status=DEP)
        outer = poly3d([(0, 0, 5), (40, 0, 5), (40, 30, 5), (0, 30, 5), (0, 0, 5)])
        hole = Ent(100, [5, 20, 15, 25, 15, 25, 15], status=DEP)
        doc = iges.read(build(faces([surf], (None, outer), (None, hole))))
        self.assertTrue(by_name(doc, 'Pz 5'))
        c = by_name(doc, 'Silhouette')[0].items[0].path.contours
        self.assertAlmostEqual(max(abs(area(x)) for x in c), 1200.0, delta=0.5)
        t = iges.triangles(build(faces([surf], (None, outer), (None, hole))))
        self.assertAlmostEqual(mesh_area(t), 1200 - math.pi * 25, delta=0.2)

    def test_exact_outline_needs_few_triangles(self):
        surf = Ent(108, [0, 0, 1, 0, 0, 0, 0, 0, 0], status=DEP)
        outer = poly3d([(0, 0, 0), (40, 0, 0), (40, 30, 0), (0, 30, 0), (0, 0, 0)])
        t = iges.triangles(build(faces([surf], (None, outer))))
        self.assertAlmostEqual(mesh_area(t), 1200.0, places=6)
        self.assertLess(len(t), 8)

    def test_horizontal_plane_in_parameters(self):
        surf = Ent(108, [0, 0, 1, 7, 0, 0, 0, 0, 0], status=DEP)
        ring = poly2d([(10, 10), (30, 10), (30, 20), (10, 20), (10, 10)])
        t = iges.triangles(build(faces([surf], (ring, None))))
        self.assertAlmostEqual(mesh_area(t), 200.0, places=6)
        self.assertAlmostEqual(float(t[:, :, 2].min()), 7.0, places=9)
        self.assertAlmostEqual(float(t[:, :, 0].min()), 10.0, places=9)

    def test_tilted_plane(self):
        n = (1.0, 0.0, 1.0)
        surf = Ent(108, [*n, 10.0, 0, 0, 0, 0, 0], status=DEP)
        ring = poly3d([(10, 0, 0), (10, 20, 0), (0, 20, 10), (0, 0, 10), (10, 0, 0)])
        t = iges.triangles(build(faces([surf], (None, ring))))
        self.assertAlmostEqual(mesh_area(t), 20 * math.hypot(10, 10), places=6)
        np.testing.assert_allclose(t[:, :, 0] + t[:, :, 2], 10.0, atol=1e-9)

    def test_tilted_plane_without_3d_edge_is_reported(self):
        surf = Ent(108, [1, 0, 1, 10, 0, 0, 0, 0, 0], status=DEP)
        ring = poly2d([(0, 0), (1, 0), (1, 1), (0, 0)])
        doc = iges.read(build(faces([surf], (ring, None))))
        self.assertTrue(any('144' in r for r in doc.report))

    def test_bounded_plane_on_its_own(self):
        rim = Ent(100, [3, 0, 0, 10, 0, 10, 0], status=DEP)
        surf = Ent(108, [0, 0, 1, 3, rim, 0, 0, 0, 0], form=1)
        doc = iges.read(build([rim, surf]))
        self.assertTrue(by_name(doc, 'Pz 3'))
        t = iges.triangles(build([rim, surf]))
        self.assertAlmostEqual(mesh_area(t), math.pi * 100, delta=0.2)

    def test_bounded_plane_under_a_matrix(self):
        m = Ent(124, [1, 0, 0, 100, 0, 1, 0, 0, 0, 0, 1, 0])
        rim = Ent(100, [3, 0, 0, 10, 0, 10, 0], status=DEP)
        surf = Ent(108, [0, 0, 1, 3, rim, 0, 0, 0, 0], form=1, matrix=m)
        t = iges.triangles(build([m, rim, surf]))
        self.assertAlmostEqual(float(t[:, :, 0].min()), 90.0, delta=0.01)
        self.assertAlmostEqual(mesh_area(t), math.pi * 100, delta=0.2)

    def test_endless_plane_is_reported(self):
        doc = iges.read(build([Ent(108, [0, 0, 1, 3, 0, 0, 0, 0, 0])]))
        self.assertTrue(any('108' in r for r in doc.report))
        self.assertEqual(len(iges.triangles(build([Ent(108, [0, 0, 1, 3, 0, 0, 0, 0, 0])]))), 0)

    def test_hole_plane_is_not_a_face(self):
        rim = Ent(100, [3, 0, 0, 10, 0, 10, 0], status=DEP)
        doc = iges.read(build([rim, Ent(108, [0, 0, 1, 3, rim, 0, 0, 0, 0], form=-1)]))
        self.assertTrue(any('108' in r for r in doc.report))

    def test_no_normal_is_reported(self):
        doc = iges.read(build([Ent(108, [0, 0, 0, 3, 0, 0, 0, 0, 0])]))
        self.assertTrue(any('108' in r for r in doc.report))


class Together(unittest.TestCase):
    def test_a_turned_part(self):
        """Un plot : sa paroi (révolution) et son dessus (plan), posés sur une plaque (NURBS)."""
        parts = cylinder_parts(r=10.0, h=8.0)
        rim = Ent(100, [8, 0, 0, 10, 0, 10, 0], status=DEP)
        top = Ent(108, [0, 0, 1, 8, rim, 0, 0, 0, 0], form=1)
        wall = Ent(120, parts[-1].params)
        plate = plane_patch(-30, -30, 30, 30)
        plate.status = '00000000'
        doc = iges.read(build([*parts[:2], wall, rim, top, plate]))
        self.assertTrue(by_name(doc, 'Pz 8'))
        self.assertTrue(by_name(doc, 'Pz 0'))
        c = by_name(doc, 'Pz 8')[0].items[0].path.contours[0]
        self.assertAlmostEqual(abs(area(c)), math.pi * 100, delta=1.0)
        self.assertFalse(any('non lus' in r for r in doc.report))

    def test_a_shared_surface_keeps_its_faces_apart(self):
        parts = cylinder_parts()
        one = arc_xy(10, 0, math.pi / 2) + arc_xy(10, math.pi / 2, 0, z=20)
        two = arc_xy(10, math.pi, 3 * math.pi / 2) + arc_xy(10, 3 * math.pi / 2, math.pi, z=20)
        ents = [*parts, *trimmed(parts[-1], (None, poly3d([*one, one[0]]))),
                *trimmed(parts[-1], (None, poly3d([*two, two[0]])))]
        t = iges.triangles(build(ents))
        self.assertAlmostEqual(mesh_area(t), math.pi * 10 * 20, delta=1.0)
        self.assertFalse(((t[:, :, 0] < -0.01).any(axis=1) & (t[:, :, 1] > 0.01).any(axis=1)).any())


class Broken(unittest.TestCase):
    def test_missing_generatrix(self):
        ax = dep_line((0, 0, 0), (0, 0, 1))
        doc = iges.read(build([ax, Ent(120, [ax, 999, 0, 6.28])]))
        self.assertTrue(any('120' in r for r in doc.report))

    def test_null_axis(self):
        ax, gen = dep_line((0, 0, 0), (0, 0, 0)), dep_line((10, 0, 0), (10, 0, 5))
        doc = iges.read(build([ax, gen, Ent(120, [ax, gen, 0, 6.28])]))
        self.assertTrue(any('120' in r for r in doc.report))

    def test_generatrix_on_the_axis(self):
        ax, gen = dep_line((0, 0, 0), (0, 0, 1)), dep_line((0, 0, 2), (0, 0, 5))
        doc = iges.read(build([ax, gen, Ent(120, [ax, gen, 0, 6.28])]))
        self.assertTrue(any('120' in r for r in doc.report))

    def test_no_height(self):
        d = dep_line((0, 0, 0), (20, 0, 0))
        doc = iges.read(build([d, Ent(122, [d, 0, 0, 0])]))
        self.assertTrue(any('122' in r for r in doc.report))

    def test_counted_once(self):
        doc = iges.read(build([Ent(122, [999, 0, 0, 1])]))
        line_ = next(r for r in doc.report if '122' in r)
        self.assertIn('× 1', line_)

    def test_ruled_with_a_point(self):
        p = Ent(116, [0, 0, 0, 0], status=DEP)
        a = dep_line((0, 0, 0), (10, 0, 0))
        doc = iges.read(build([p, a, Ent(118, [a, p, 0, 0], form=1)]))
        self.assertTrue(any('118' in r for r in doc.report))

    def test_other_surfaces_are_still_reported(self):
        doc = iges.read(build([Ent(192, [0, 0, 5])]))
        self.assertTrue(any('192' in r for r in doc.report))


class Units(unittest.TestCase):
    def test_announced_unit_too_large_applies_to_swept_surfaces(self):
        d = dep_line((0, 0, 0), (100, 0, 0))
        doc = iges.read(build([d, Ent(122, [d, 0, 0, 10])], unit=6, unit_name='1HM'))
        self.assertTrue(any('unité' in r for r in doc.report))
        t = iges.triangles(build([d, Ent(122, [d, 0, 0, 10])], unit=6, unit_name='1HM'))
        self.assertAlmostEqual(mesh_area(t), 1000.0, places=6)


if __name__ == '__main__':
    unittest.main()
