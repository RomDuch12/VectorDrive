"""Round 869 : « Point de départ du dessin » : les points attendus sont ceux que TypeEdit 13 a calculés sur ce même dessin (outil 8 mm)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', os.path.join(tempfile.mkdtemp(), 'session'))
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')

from vectordrive.cam import model as M
from vectordrive.cam import strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape

T_SHAPE = [(10, 10), (50, 10), (50, 20), (35, 20), (35, 40), (25, 40), (25, 20), (10, 20)]
TRIANGLE = [(70, 15), (90, 15), (80, 40)]


def run(shapes, **kw):
    doc = Document()
    doc.plate = Plate(width=120.0, height=60.0)
    doc.layers = [Layer(name='A', items=[Shape(path=geom.Path([geom.polyline(p, closed=True)])) for p in shapes])]
    setup = M.setup_of(doc)
    tool = M.CamTool(name='F', diameter=8.0)
    setup.tools.append(tool)
    op = M.Operation(kind='contour', tool_id=tool.id, depth=6.5, step_down=6.5, side=kw.pop('side', 'exterieur'),
                     start_policy=kw.pop('start_policy', 'dessin'), **kw)
    setup.operations.append(op)
    M.store(doc, setup)
    return S.compute(doc, setup, op, (0.0, 0.0))


def low(tp):
    return [m for m in tp.moves if m.z < -1e-9]


def first_cut(tp):
    m = low(tp)[0]
    return (round(m.x, 3), round(m.y, 3))


class TestLikeTypeEdit(unittest.TestCase):

    def test_outside_after_the_rounded_corner(self):
        self.assertEqual(first_cut(run([T_SHAPE])), (6.0, 10.0))

    def test_outside_the_tool_leaves_along_the_side(self):
        pts = low(run([T_SHAPE]))
        k = next(i for i, m in enumerate(pts) if math.dist((m.x, m.y), (6.0, 20.0)) < 1e-6)
        self.assertTrue(all(abs(m.x - 6.0) < 1e-6 for m in pts[:k + 1]))

    def test_outside_on_a_slanted_side(self):
        self.assertEqual(first_cut(run([TRIANGLE])), (66.286, 16.486))

    def test_inside_on_the_corner_of_the_offset(self):
        self.assertEqual(first_cut(run([T_SHAPE], side='interieur')), (14.0, 14.0))

    def test_the_cut_is_the_same_ring(self):
        a = low(run([T_SHAPE]))
        self.assertAlmostEqual(a[0].x, a[-1].x, places=6)
        self.assertAlmostEqual(a[0].y, a[-1].y, places=6)


class TestDrop(unittest.TestCase):
    """Entrée en goutte, 12 mm de distance, sans rayon de perçage : deux demi-cercles de rayon 6 centrés sur (0, 10)."""

    def setUp(self):
        self.pts = [(m.x, m.y) for m in low(run([T_SHAPE], lead_mode='percage', lead_in=12.0, lead_out=12.0))]

    def test_it_starts_and_ends_at_the_hole(self):
        self.assertAlmostEqual(self.pts[0][0], -6.0, places=6)
        self.assertAlmostEqual(self.pts[0][1], 10.0, places=6)
        self.assertAlmostEqual(self.pts[-1][0], -6.0, places=6)
        self.assertAlmostEqual(self.pts[-1][1], 10.0, places=6)

    def test_the_way_in_passes_under(self):
        k = next(i for i, p in enumerate(self.pts) if math.dist(p, (6.0, 10.0)) < 1e-6)
        way = self.pts[:k + 1]
        self.assertTrue(all(abs(math.dist(p, (0.0, 10.0)) - 6.0) < 1e-3 for p in way))
        self.assertTrue(all(p[1] <= 10.0 + 1e-6 for p in way))

    def test_the_way_out_passes_over(self):
        k = max(i for i, p in enumerate(self.pts) if math.dist(p, (6.0, 10.0)) < 1e-6)
        way = self.pts[k:]
        self.assertTrue(all(abs(math.dist(p, (0.0, 10.0)) - 6.0) < 1e-3 for p in way))
        self.assertTrue(all(p[1] >= 10.0 - 1e-6 for p in way))


class TestOthers(unittest.TestCase):

    def test_a_reflex_corner_keeps_the_nearest_point(self):
        l_shape = [(30, 30), (10, 30), (10, 10), (50, 10), (50, 50), (30, 50)]
        got = first_cut(run([l_shape]))
        self.assertLess(math.dist(got, (30.0, 30.0)), 6.0)

    def test_a_hand_placed_start_is_not_moved(self):
        doc = Document()
        doc.plate = Plate(width=120.0, height=60.0)
        shape = Shape(path=geom.Path([geom.polyline(T_SHAPE, closed=True)]), extra={'start_xy': [[30.0, 6.0]]})
        doc.layers = [Layer(name='A', items=[shape])]
        setup = M.setup_of(doc)
        tool = M.CamTool(name='F', diameter=8.0)
        setup.tools.append(tool)
        op = M.Operation(kind='contour', tool_id=tool.id, depth=6.5, step_down=6.5, side='exterieur')
        setup.operations.append(op)
        M.store(doc, setup)
        self.assertEqual(first_cut(S.compute(doc, setup, op, (0.0, 0.0))), (30.0, 6.0))

    def test_the_nearest_policy_does_not_change(self):
        got = first_cut(run([T_SHAPE], start_policy='proche'))
        self.assertNotEqual(got, (6.0, 10.0))

    def test_the_marks_keep_their_place_first(self):
        chains, fixed = S.apply_starts([([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)], True)], [(5.0, 1.0)], 5.0, 2.0)
        self.assertEqual(chains[0][0][0], (5.0, 0.0))
        self.assertEqual(fixed, {(5.0, 0.0)})

    def test_a_mark_with_no_such_point(self):
        ring = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)]
        self.assertEqual(S._start_after_corner(ring, (5.0, 5.0, (6.0, 5.0), (4.0, 5.0)), 1.0)[:2], (5.0, 5.0))

    def test_no_offset(self):
        ring = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)]
        m = (0.0, 0.0, (10.0, 0.0), (0.0, 10.0))
        self.assertEqual(S._start_after_corner(ring, m, 0.0), m)


if __name__ == '__main__':
    unittest.main()
