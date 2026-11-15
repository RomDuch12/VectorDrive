"""Round 871 : gravure 3D : les valeurs attendues sont celles que TypeEdit 13 a calculées sur le même dessin (cône de 30°, pointe de 0,2 mm, 0,35 de profondeur, 0,1 entre les passes)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from shapely.geometry import MultiPolygon, Point, Polygon

from vectordrive.cam import advanced as A
from vectordrive.cam import model as M
from vectordrive.cam import strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape

T_SHAPE = [(10, 10), (50, 10), (50, 20), (35, 20), (35, 40), (25, 40), (25, 20), (10, 20)]
TRIANGLE = [(70, 15), (90, 15), (80, 40)]
REG = MultiPolygon([Polygon(T_SHAPE), Polygon(TRIANGLE)])
D_FLAT = 0.1 + 0.35 * math.tan(math.radians(15.0))


def path_of(shapes=(T_SHAPE, TRIANGLE), **kw):
    doc = Document()
    doc.plate = Plate(width=120.0, height=60.0)
    doc.layers = [Layer(name='A', items=[Shape(path=geom.Path([geom.polyline(s, closed=True)])) for s in shapes])]
    setup = M.setup_of(doc)
    t = M.CamTool(name='C', diameter=6.0)
    t.kind, t.angle, t.tip = 'conique', 30.0, 0.2
    setup.tools.append(t)
    base = dict(kind='vcarve', tool_id=t.id, depth=0.35, step_down=9.0, resolution=0.1, stepover_mm=0.1)
    base.update(kw)
    op = M.Operation(**base)
    setup.operations.append(op)
    M.store(doc, setup)
    return S.compute(doc, setup, op, (0.0, 0.0))


def cuts(tp):
    return [m for m in tp.moves if m.kind != 'rapid']


def floor(tp):
    return [m for m in cuts(tp) if abs(m.z + 0.35) < 1e-9]


class TestCorners(unittest.TestCase):

    def test_every_corner_is_pulled_up_to_the_surface(self):
        tips = {(round(m.x, 2), round(m.y, 2)) for m in cuts(path_of()) if abs(m.z) < 1e-9}
        # relevé dans TE13 : les 6 angles du T et les 3 du triangle (les 2 angles rentrants du T n'en ont pas)
        for p in ((10.1, 10.1), (49.9, 10.1), (49.9, 19.9), (34.9, 39.9), (25.1, 39.9), (10.1, 19.9), (70.15, 15.1), (89.85, 15.1), (80.0, 39.73)):
            self.assertIn(p, tips)
        self.assertEqual(len(tips), 9)

    def test_nothing_goes_under_the_cone(self):
        tan_h = math.tan(math.radians(15.0))
        for m in cuts(path_of()):
            if m.z < -1e-6:
                self.assertLessEqual(-m.z, (REG.boundary.distance(Point(m.x, m.y)) - 0.1) / tan_h + 1e-3, (m.x, m.y, m.z))

    def test_it_starts_from_the_pass_nearest_the_edge(self):
        chains = A.corner_axis(Polygon(T_SHAPE), D_FLAT, 0.1, math.tan(math.radians(15.0)), 0.35, 135.0)
        self.assertEqual(len(chains), 6)
        first = next(c for c in chains if math.dist(c[1][:2], (10.1, 10.1)) < 1e-6)
        self.assertAlmostEqual(first[0][0], 10.0 + D_FLAT, places=6)
        self.assertAlmostEqual(first[0][1], 10.0 + D_FLAT, places=6)
        self.assertAlmostEqual(first[0][2], -0.35, places=6)

    def test_the_angle_setting(self):
        tan_h = math.tan(math.radians(15.0))
        self.assertEqual(A.corner_axis(Polygon(T_SHAPE), D_FLAT, 0.1, tan_h, 0.35, 0.0), [])
        self.assertEqual(A.corner_axis(Polygon(T_SHAPE), D_FLAT, 0.1, tan_h, 0.35, 80.0), [])          # des angles de 90°
        self.assertEqual(len(A.corner_axis(Polygon(TRIANGLE), D_FLAT, 0.1, tan_h, 0.35, 80.0)), 3)

    def test_none_without_place(self):
        # une forme plus étroite que le premier retrait : la ligne médiane s'en occupe
        narrow = Polygon([(0, 0), (20, 0), (20, 0.3), (0, 0.3)])
        self.assertEqual(A.corner_axis(narrow, D_FLAT, 0.1, math.tan(math.radians(15.0)), 0.35, 135.0), [])

    def test_the_contour_mode_still_has_none(self):
        tp = path_of(vcarve_mode='contour')
        self.assertFalse([m for m in cuts(tp) if abs(m.z) < 1e-9])

    def test_setting_zero_removes_them(self):
        self.assertFalse([m for m in cuts(path_of(corner_pull_angle=0.0)) if abs(m.z) < 1e-9])

    def test_the_finish_keeps_them(self):
        self.assertEqual(len({(round(m.x, 2), round(m.y, 2)) for m in cuts(path_of(vcarve_edges_only=True)) if abs(m.z) < 1e-9}), 9)

    def test_a_skipped_frame_has_none(self):
        frame = [(0, 0), (100, 0), (100, 50), (0, 50)]
        doc = Document()
        doc.plate = Plate(width=120.0, height=60.0)
        doc.layers = [Layer(name='A', items=[Shape(path=geom.Path([geom.polyline(frame, closed=True), geom.polyline(T_SHAPE, closed=True)]))])]
        setup = M.setup_of(doc)
        t = M.CamTool(name='C', diameter=6.0)
        t.kind, t.angle, t.tip = 'conique', 30.0, 0.2
        setup.tools.append(t)
        op = M.Operation(kind='vcarve', tool_id=t.id, depth=0.35, step_down=9.0, resolution=0.1, stepover_mm=5.0, finish_skip_frame=True)
        setup.operations.append(op)
        M.store(doc, setup)
        tips = {(round(m.x, 1), round(m.y, 1)) for m in cuts(S.compute(doc, setup, op, (0.0, 0.0))) if abs(m.z) < 1e-9}
        self.assertNotIn((0.1, 0.1), tips)


class TestFloor(unittest.TestCase):

    def insets(self, tp):
        return sorted({round(REG.boundary.distance(Point(m.x, m.y)), 2) for m in floor(tp)})

    def test_the_distance_between_passes(self):
        got = self.insets(path_of())
        self.assertEqual(got[:6], [0.19, 0.29, 0.39, 0.49, 0.59, 0.69])                    # les mêmes retraits que TE13

    def test_the_length_is_the_one_of_te(self):
        # TE13 : 8 252 mm
        self.assertAlmostEqual(path_of().lengths()[0], 8252.0, delta=8252.0 * 0.02)

    def test_without_a_distance_the_old_step_stays(self):
        got = self.insets(path_of(stepover_mm=0.0))
        self.assertEqual(got[:3], [0.19, 0.4, 0.61])


class TestOrder(unittest.TestCase):

    def test_from_the_centre_to_the_edge_by_default(self):
        ms = floor(path_of([T_SHAPE]))
        d = [Polygon(T_SHAPE).boundary.distance(Point(m.x, m.y)) for m in ms]
        self.assertGreater(d[0], 4.0)
        self.assertLess(d[-1], 0.2)

    def test_the_contour_comes_last_then_the_corners(self):
        tp = path_of([T_SHAPE])
        ms = cuts(tp)
        last_floor = max(i for i, m in enumerate(ms) if abs(m.z + 0.35) < 1e-9 and Polygon(T_SHAPE).boundary.distance(Point(m.x, m.y)) > 0.25)
        first_pull = min(i for i, m in enumerate(ms) if abs(m.z) < 1e-9)
        self.assertLess(last_floor, first_pull)

    def test_from_the_outside_on_demand(self):
        ms = floor(path_of([T_SHAPE], pocket_outside_in=True))
        self.assertLess(Polygon(T_SHAPE).boundary.distance(Point(ms[0].x, ms[0].y)), 0.2)

    def test_the_tool_stays_down_between_passes(self):
        tp = path_of([T_SHAPE])
        ms = tp.moves
        first = next(i for i, m in enumerate(ms) if m.z < -1e-6)
        pull = next(i for i, m in enumerate(ms) if i > first and abs(m.z) < 1e-9)
        rapids = [m for m in ms[first:pull] if m.kind == 'rapid']
        self.assertLessEqual(len(rapids), 3)                  # au plus un dégagement

    def test_a_slope_goes_up_before_it_moves_outward(self):
        # plus d'une passe en pente : en revenant vers le bord, l'outil ne reste pas plus bas que le cône
        tan_h = math.tan(math.radians(15.0))
        tp = path_of([T_SHAPE], depth=2.0, resolution=0.05, stepover_mm=1.0)
        poly = Polygon(T_SHAPE)
        for m in cuts(tp):
            if m.z < -1e-6:
                self.assertLessEqual(-m.z, (poly.boundary.distance(Point(m.x, m.y)) - 0.1) / tan_h + 2e-3, (m.x, m.y, m.z))

    def test_in_layers_each_one_from_the_edge(self):
        tp = path_of([T_SHAPE], vcarve_step=0.117)
        zs = [m.z for m in cuts(tp) if m.z < -1e-6 and abs(m.z) in (0.117, 0.234, 0.35)]
        self.assertEqual(zs, sorted(zs, reverse=True))


class TestRamp(unittest.TestCase):

    def test_the_way_in_is_a_slope(self):
        tp = path_of([T_SHAPE], ramp=True, ramp_angle=30.0)
        ms = [m for m in cuts(tp) if m.z < -1e-9]
        self.assertEqual(ms[0].kind, 'feed')
        self.assertGreater(ms[0].z, -0.35)
        first_pull = next(i for i, m in enumerate(cuts(tp)) if abs(m.z) < 1e-9 and i > 1)
        self.assertFalse([m for m in cuts(tp)[:first_pull] if m.kind == 'plunge' and m.z < -1e-6 and m.z > -0.35])

    def test_the_angle_is_kept(self):
        tp = path_of([T_SHAPE], ramp=True, ramp_angle=30.0)
        q = None
        for m in cuts(tp):
            if q is not None and m.z < q.z - 1e-9:
                self.assertLessEqual(q.z - m.z, math.hypot(m.x - q.x, m.y - q.y) * math.tan(math.radians(30.0)) + 1e-6)
            q = m
            if m.z <= -0.35 + 1e-9:
                break

    def test_no_ramp_by_default(self):
        self.assertTrue([m for m in path_of([T_SHAPE]).moves if m.kind == 'plunge' and m.z < -1e-6])


class TestForm(unittest.TestCase):

    def test_the_form_offers_them(self):
        from vectordrive.ui import cam_panel as P
        for n in ('stepover_mm', 'pocket_outside_in', 'corner_pull_angle', 'ramp', 'ramp_angle'):
            self.assertIn(n, P.KIND_FIELDS['vcarve'])
            self.assertIn(n, P.LABELS)


if __name__ == '__main__':
    unittest.main()
