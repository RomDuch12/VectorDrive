"""Round 870 : fer à dorer gaufrant : les valeurs attendues sont celles que TypeEdit 13 a calculées sur les mêmes dessins, avec les mêmes réglages."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from shapely.geometry import Point, Polygon

from vectordrive.cam import advanced as A
from vectordrive.cam import model as M
from vectordrive.cam import strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape

RECT = [(10, 10), (50, 10), (50, 30), (10, 30)]
RECT_POLY = Polygon(RECT)
HOLED_OUT = [(10, 10), (40, 10), (40, 40), (10, 40)]
HOLED_IN = [(20, 20), (20, 30), (30, 30), (30, 20)]
HOLED_POLY = Polygon(HOLED_OUT, [HOLED_IN])
NECK = [(55, 10), (75, 10), (75, 22), (85, 22), (85, 10), (105, 10), (105, 40), (85, 40), (85, 28), (75, 28), (75, 40), (55, 40)]
NECK_POLY = Polygon(NECK)


def cone(angle=30.0, tip=0.2):
    t = M.CamTool(name='C', diameter=6.0)
    t.kind, t.angle, t.tip = 'conique', angle, tip
    return t


def op_of(**kw):
    base = dict(kind='fer_dorer', depth=1.0, emboss_edge=0.5, emboss_width=2.0, emboss_start_angle=30.0, emboss_end_angle=0.0)
    base.update(kw)
    return M.Operation(**base)


def path_of(shapes, tool=None, **kw):
    doc = Document()
    doc.plate = Plate(width=120.0, height=60.0)
    doc.layers = [Layer(name='A', items=[Shape(path=geom.Path([geom.polyline(c, closed=True) for c in s])) for s in shapes])]
    setup = M.setup_of(doc)
    tool = tool or cone()
    setup.tools.append(tool)
    op = op_of(tool_id=tool.id, resolution=0.5, step_down=5.0, **kw)
    setup.operations.append(op)
    M.store(doc, setup)
    return S.compute(doc, setup, op, (0.0, 0.0)), op, tool


def cuts(tp):
    return [m for m in tp.moves if m.kind != 'rapid' and m.z < -1e-9]


class TestProfile(unittest.TestCase):
    """Cote de l'outil, à la distance de son axe au bord : relevé dans TE13."""

    def check(self, table, r, tol=0.002, tool=None, **kw):
        op = op_of(**kw)
        for axis, z in table:
            self.assertAlmostEqual(-A.emboss_depth(op, axis - r, tool), z, delta=tol, msg=f'axe à {axis}')

    def test_start_30(self):
        self.check([(0.7, -0.156), (0.9, -0.396), (1.1, -0.571), (1.3, -0.702), (1.5, -0.801), (1.7, -0.875), (1.9, -0.928), (2.1, -0.965), (2.3, -0.988)],
                   0.1, tool=cone())

    def test_start_60_no_edge(self):
        self.check([(0.285, -0.152), (0.56, -0.307), (0.835, -0.46), (1.11, -0.608), (1.385, -0.749), (1.66, -0.881), (1.935, -0.986)],
                   0.02, emboss_edge=0.0, emboss_start_angle=60.0)

    def test_an_end_angle(self):
        self.check([(0.775, -0.229), (1.05, -0.387), (1.325, -0.52), (1.6, -0.642), (1.875, -0.755), (2.15, -0.862), (2.425, -0.965)],
                   0.02, tol=0.006, emboss_end_angle=20.0)

    def test_wider_than_the_form(self):
        self.check([(1.11, -0.32), (4.96, -0.633), (9.36, -0.797)], 0.02, emboss_edge=0.0, emboss_width=30.0)

    def test_nothing_on_the_edge(self):
        self.assertEqual(A.emboss_depth(op_of(), 0.5), 0.0)
        self.assertEqual(A.emboss_depth(op_of(), 0.2), 0.0)

    def test_the_whole_depth_after_the_width(self):
        self.assertEqual(A.emboss_depth(op_of(), 2.5), 1.0)
        self.assertEqual(A.emboss_depth(op_of(), 9.0), 1.0)


class TestAngleLimits(unittest.TestCase):

    def test_not_steeper_than_the_tool(self):
        a, b = op_of(emboss_start_angle=5.0), op_of(emboss_start_angle=15.0)
        for d in (0.6, 0.9, 1.5, 2.2):
            self.assertAlmostEqual(A.emboss_depth(a, d, cone()), A.emboss_depth(b, d, cone()), places=9)

    def test_a_steep_angle_with_a_straight_tool(self):
        self.assertGreater(A.emboss_depth(op_of(emboss_start_angle=0.0), 0.6), A.emboss_depth(op_of(emboss_start_angle=30.0), 0.6))

    def test_too_flat_is_the_straight_line(self):
        # TE : 70° demandés deviennent 63,435°, et le profil est la droite du bord au fond
        op = op_of(emboss_start_angle=70.0)
        for axis, z in ((0.7, -0.05), (1.5, -0.45), (2.3, -0.85)):
            self.assertAlmostEqual(-A.emboss_depth(op, axis - 0.1), z, delta=0.002)

    def test_the_old_default_means_no_limit(self):
        self.assertEqual(A.emboss_depth(op_of(emboss_start_angle=90.0), 0.9), A.emboss_depth(op_of(emboss_start_angle=0.0), 0.9))

    def test_no_depth(self):
        self.assertEqual(A.emboss_depth(op_of(depth=0.0), 1.0), 0.0)


class TestPasses(unittest.TestCase):

    def test_from_the_edge_to_the_centre(self):
        tp, op, tool = path_of([[RECT]])
        insets = [round(RECT_POLY.boundary.distance(Point(m.x, m.y)), 3) for m in cuts(tp)]
        self.assertEqual(insets, sorted(insets))
        self.assertEqual(insets[0], 1.0)                   # 0,5 + 0,5 : à 0,5, TE passe en surface sans rien couper
        self.assertEqual(insets[-1], 9.5)

    def test_the_passes_follow_each_other_without_going_up(self):
        tp, op, tool = path_of([[RECT]])
        self.assertEqual(sum(1 for m in tp.moves if m.kind == 'rapid' and m.z <= 0.0), 0)
        first = next(i for i, m in enumerate(tp.moves) if m.kind == 'plunge')
        last = max(i for i, m in enumerate(tp.moves) if m.z < 0)
        self.assertFalse([m for m in tp.moves[first:last] if m.kind == 'rapid'])

    def test_it_goes_down_on_the_next_pass(self):
        tp, op, tool = path_of([[RECT]])
        ms = tp.moves
        k = next(i for i, m in enumerate(ms) if m.kind == 'plunge' and i > next(j for j, n in enumerate(ms) if n.kind == 'plunge'))
        self.assertEqual((ms[k - 1].x, ms[k - 1].y), (ms[k].x, ms[k].y))
        self.assertGreater(ms[k - 1].z, ms[k].z)

    def test_clockwise_like_te(self):
        tp, op, tool = path_of([[RECT]])
        ms = cuts(tp)
        z0 = ms[0].z
        ring = [(m.x, m.y) for m in ms if m.z == z0]
        area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:]))
        self.assertLess(area, 0.0)

    def test_the_floor_is_the_whole_depth(self):
        tp, op, tool = path_of([[RECT]])
        self.assertEqual(min(m.z for m in tp.moves), -1.0)
        self.assertEqual(cuts(tp)[-1].z, -1.0)

    def test_inside_is_the_default(self):
        self.assertEqual(M.Operation().emboss_side, 'dedans')
        self.assertEqual(M.Operation().emboss_start_angle, 0.0)

    def test_an_old_document_stays_around(self):
        self.assertEqual(M.Operation.from_dict({'kind': 'fer_dorer'}).emboss_side, 'autour')
        self.assertEqual(M.Operation.from_dict({'kind': 'fer_dorer', 'emboss_side': 'dedans'}).emboss_side, 'dedans')
        self.assertEqual(M.Operation.from_dict({'kind': 'gravure'}).emboss_side, 'dedans')


class TestShapes(unittest.TestCase):

    def no_mark(self, tp, poly, op, tool):
        """Aucun mouvement ne passe sous le galbe : ni les passes, ni leurs liaisons."""
        for m in cuts(tp):
            d = poly.boundary.distance(Point(m.x, m.y))
            self.assertTrue(poly.buffer(1e-6).contains(Point(m.x, m.y)), (m.x, m.y))
            self.assertLessEqual(-m.z, A.emboss_depth(op, d - tool.tip / 2, tool) + 0.002, (m.x, m.y, m.z))     # les arcs sont des cordes

    def test_a_hole(self):
        tp, op, tool = path_of([[HOLED_OUT, HOLED_IN]])
        self.no_mark(tp, HOLED_POLY, op, tool)
        self.assertEqual(sum(1 for m in tp.moves if m.kind == 'plunge' and m.z < -1e-9 and tp.moves[tp.moves.index(m) - 1].kind == 'rapid'), 1)

    def test_a_neck_is_finished_on_one_side_first(self):
        tp, op, tool = path_of([[NECK]])
        self.no_mark(tp, NECK_POLY, op, tool)
        ms = [m for m in cuts(tp) if NECK_POLY.boundary.distance(Point(m.x, m.y)) > 3.2]
        sides = [m.x < 80 for m in ms]
        self.assertEqual(sum(1 for a, b in zip(sides, sides[1:]) if a != b), 1)

    def test_two_shapes_one_after_the_other(self):
        tp, op, tool = path_of([[HOLED_OUT, HOLED_IN], [NECK]])
        ms = cuts(tp)
        sides = [m.x < 50 for m in ms]
        self.assertEqual(sum(1 for a, b in zip(sides, sides[1:]) if a != b), 1)

    def test_too_small(self):
        tp, op, tool = path_of([[[(10, 10), (10.4, 10), (10.4, 10.4), (10, 10.4)]]])
        self.assertEqual(cuts(tp), [])


class TestAround(unittest.TestCase):

    def test_the_form_stays(self):
        tp, op, tool = path_of([[RECT]], emboss_side='autour')
        self.assertTrue(cuts(tp))
        for m in cuts(tp):
            self.assertFalse(RECT_POLY.contains(Point(m.x, m.y)))

    def test_it_ends_at_the_width(self):
        tp, op, tool = path_of([[RECT]], emboss_side='autour')
        far = max(RECT_POLY.distance(Point(m.x, m.y)) for m in cuts(tp))
        self.assertAlmostEqual(far, 0.5 + 2.0 + 0.1, delta=0.2)
        self.assertEqual(min(m.z for m in tp.moves), -1.0)

    def test_from_the_form_outwards(self):
        tp, op, tool = path_of([[RECT]], emboss_side='autour')
        d = [round(RECT_POLY.distance(Point(m.x, m.y)), 2) for m in cuts(tp)]
        self.assertEqual(d[0], 1.0)
        self.assertGreater(d[-1], d[0])


class TestIntaglio(unittest.TestCase):

    def test_the_centre_line_follows_the_profile(self):
        tp, op, tool = path_of([[RECT]], tool=cone(), emboss_passes='intaille')
        self.assertTrue(cuts(tp))
        for m in cuts(tp):
            d = RECT_POLY.boundary.distance(Point(m.x, m.y))
            self.assertAlmostEqual(-m.z, A.emboss_depth(op, d - 0.1, tool), delta=0.05, msg=(m.x, m.y))

    def test_it_goes_into_the_corners(self):
        tp, op, tool = path_of([[RECT]], tool=cone(), emboss_passes='intaille')
        self.assertLess(min(m.x for m in cuts(tp)), 11.0)
        self.assertEqual(min(m.z for m in cuts(tp)), -1.0)

    def test_no_warning_about_wide_zones(self):
        tp, op, tool = path_of([[RECT]], tool=cone(), emboss_passes='intaille')
        self.assertFalse([w for w in tp.warnings if 'plus larges' in w], tp.warnings)

    def test_after_the_standard_passes(self):
        std = path_of([[RECT]], tool=cone())[0]
        both = path_of([[RECT]], tool=cone(), emboss_passes='les_deux')[0]
        self.assertEqual([(m.x, m.y, m.z) for m in cuts(both)][:len(cuts(std))], [(m.x, m.y, m.z) for m in cuts(std)])
        self.assertGreater(len(cuts(both)), len(cuts(std)))


if __name__ == '__main__':
    unittest.main()
