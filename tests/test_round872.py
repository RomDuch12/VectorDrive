"""Round 872 : passes connectées en descente angulaire. TE13 ignore ConnectToolpath en plongée angulaire (il remonte à chaque passe) :
VectorDrive le respecte. Sans connexion, les valeurs attendues sont celles que TE13 a calculées sur le même dessin (Ø6, 2 passes de 1 mm, 30°)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from shapely.geometry import LineString, Point, Polygon

from vectordrive.cam import model as M
from vectordrive.cam import strategies as S
from vectordrive.cam import tpp
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape

SQUARE = [(10, 10), (50, 10), (50, 40), (10, 40)]
TRIANGLE = [(70, 15), (90, 15), (80, 40)]
SLOPE_1 = 1.0 / math.tan(math.radians(30.0))
SLOPE_2 = 2.0 / math.tan(math.radians(30.0))
PERIM = 2 * (40 + 30) + 2 * math.pi * 3.0                  # à 3 mm du carré, avec les angles ronds de l'outil


def path_of(shapes=(SQUARE,), **kw):
    doc = Document()
    doc.plate = Plate(width=120.0, height=60.0)
    doc.layers = [Layer(name='A', items=[Shape(path=geom.Path([geom.polyline(s, closed=True)])) for s in shapes])]
    setup = M.setup_of(doc)
    t = M.CamTool(name='F', diameter=6.0)
    setup.tools.append(t)
    base = dict(kind='gravure', side='sur', tool_id=t.id, depth=2.0, step_down=1.0, ramp_angle=30.0)
    base.update(kw)
    op = M.Operation(**base)
    setup.operations.append(op)
    M.store(doc, setup)
    return S.compute(doc, setup, op, (0.0, 0.0))


def contour(shapes=(SQUARE,), **kw):
    kw.setdefault('side', 'exterieur')
    return path_of(shapes, kind='contour', **kw)


def runs(tp):
    """Les morceaux entre deux remontées : [(mouvements)]."""
    out, cur = [], []
    for m in tp.moves:
        if m.kind == 'rapid':
            if cur:
                out.append(cur)
            cur = []
        cur.append(m)
    if cur:
        out.append(cur)
    return [r for r in out if any(m.z < -1e-9 for m in r)]


def lengths(run):
    """(longueur en pente, longueur à plat) d'un morceau."""
    slope = flat = 0.0
    for a, b in zip(run, run[1:]):
        d = math.hypot(b.x - a.x, b.y - a.y)
        if b.z < a.z - 1e-9:
            slope += d
        else:
            flat += d
    return slope, flat


def plan_length(tp):
    return sum(sum(lengths(r)) for r in runs(tp))


def steepest(tp):
    worst = 0.0
    ms = tp.moves
    for a, b in zip(ms, ms[1:]):
        d = math.hypot(b.x - a.x, b.y - a.y)
        if b.kind == 'feed' and b.z < a.z - 1e-9 and d > 1e-9:
            worst = max(worst, (a.z - b.z) / d)
    return worst


class TestNotConnected(unittest.TestCase):
    """Comme TE13, avec ou sans « Total » : à chaque passe, il remonte, et repart de la surface."""

    def test_each_pass_starts_again_from_the_surface(self):
        rs = runs(contour(ramp=True))
        self.assertEqual(len(rs), 2)
        self.assertAlmostEqual(lengths(rs[0])[0], SLOPE_1, places=6)
        self.assertAlmostEqual(lengths(rs[1])[0], SLOPE_2, places=6)

    def test_the_slope_is_cut_again_at_depth(self):
        # relevé dans TE13 : le tour, puis la partie en pente, et l'outil s'arrête au bout
        rs = runs(contour(ramp=True))
        for r, slope in zip(rs, (SLOPE_1, SLOPE_2)):
            self.assertAlmostEqual(lengths(r)[1], PERIM, delta=0.05)
            self.assertLessEqual(math.dist((r[-1].x, r[-1].y), (r[1].x, r[1].y)), slope + 1e-6)

    def test_the_length_is_the_one_of_te(self):
        self.assertAlmostEqual(plan_length(contour(ramp=True)), 2 * PERIM + SLOPE_1 + SLOPE_2, delta=0.1)

    def test_the_global_order_too(self):
        # TE13 : en ordre global, chaque passe repart aussi de la surface
        tp = contour((SQUARE, TRIANGLE), ramp=True, pass_order='global')
        rs = runs(tp)
        self.assertEqual(len(rs), 4)
        self.assertAlmostEqual(lengths(rs[2])[0], SLOPE_2, places=6)


class TestConnected(unittest.TestCase):

    def test_it_stays_in_the_material(self):
        tp = contour(link_passes=True)
        self.assertEqual(len(runs(tp)), 1)

    def test_it_goes_down_from_pass_to_pass(self):
        r = runs(contour(link_passes=True))[0]
        slope, _flat = lengths(r)
        self.assertAlmostEqual(slope, 2 * SLOPE_1, places=6)            # deux pentes de 1 mm

    def test_one_turn_per_pass_and_the_last_slope_again(self):
        self.assertAlmostEqual(plan_length(contour(link_passes=True)), 2 * PERIM + SLOPE_1, delta=0.1)

    def test_each_contour_is_left_by_the_clearance(self):
        tp = contour((SQUARE, TRIANGLE), link_passes=True)
        self.assertEqual(len(runs(tp)), 2)

    def test_the_angle_is_exact(self):
        self.assertAlmostEqual(steepest(contour(link_passes=True)), math.tan(math.radians(30.0)), places=6)

    def test_the_passes_are_all_cut(self):
        ms = contour(link_passes=True).moves
        for z in (-1.0, -2.0):
            done = sum(math.hypot(b.x - a.x, b.y - a.y) for a, b in zip(ms, ms[1:]) if abs(a.z - z) < 1e-9 and abs(b.z - z) < 1e-9)
            self.assertGreaterEqual(done, PERIM - SLOPE_1 - 0.1)

    def test_nothing_left_on_the_last_slope(self):
        # après la dernière pente, le début du contour est repris à la cote
        ms = contour(link_passes=True).moves
        last = [m for m in ms if abs(m.z + 2.0) < 1e-9]
        bottom = LineString([(m.x, m.y) for m in last])
        cuts = [m for m in ms if m.kind == 'feed']
        slope = [m for m in cuts if -2.0 + 1e-9 < m.z < -1.0 - 1e-9]
        self.assertTrue(slope)
        for m in slope:
            self.assertLess(bottom.distance(Point(m.x, m.y)), 1e-6)

    def test_without_a_ramp_the_tool_still_stays_down(self):
        # comme TE13 avec ConnectToolpath sans plongée angulaire : descente verticale au départ
        tp = contour()
        self.assertEqual(len(runs(tp)), 1)
        self.assertFalse([1 for a, b in zip(tp.moves, tp.moves[1:]) if b.z < a.z - 1e-9 and b.kind == 'feed' and math.hypot(b.x - a.x, b.y - a.y) > 1e-9])


class TestShortContours(unittest.TestCase):
    SMALL = [(0, 0), (7, 0), (7, 7), (0, 7)]                     # dedans au Ø6 : un anneau de 4 mm, pour 11,4 mm de pente

    def test_several_turns_at_the_right_angle(self):
        tp = contour((self.SMALL,), side='interieur', depth=1.0, step_down=1.0, ramp_angle=5.0, link_passes=True)
        self.assertLessEqual(steepest(tp), math.tan(math.radians(5.0)) + 1e-6)
        self.assertAlmostEqual(min(m.z for m in tp.moves), -1.0)

    def test_a_full_turn_ends_it(self):
        tp = contour((self.SMALL,), side='interieur', depth=1.0, step_down=1.0, ramp_angle=5.0, link_passes=True)
        ms = tp.moves
        bottom = sum(math.hypot(b.x - a.x, b.y - a.y) for a, b in zip(ms, ms[1:]) if abs(a.z + 1) < 1e-9 and abs(b.z + 1) < 1e-9)
        self.assertGreaterEqual(bottom, 4.0 - 0.05)


class TestTabs(unittest.TestCase):

    def test_the_tabs_stay(self):
        tp = contour(link_passes=True, tabs=2, tab_width=2.0, tab_height=1.0)
        at_bottom = [m for m in tp.moves if abs(m.z + 1.0) < 1e-9]
        self.assertTrue(at_bottom)                                       # les pontets à 1 mm du fond
        self.assertAlmostEqual(min(m.z for m in tp.moves), -2.0)


class TestPocketRing(unittest.TestCase):
    """La rampe le long d'un anneau suit l'anneau : elle ne coupe pas en ligne droite vers son second point."""

    def test_it_follows_the_ring(self):
        ring = [(0, 0), (30, 0), (30, 3), (3, 3), (3, 30), (0, 30), (0, 0)]
        tp = M.CamTool(name='F', diameter=1.0)
        em = S.Emitter(M.Operation(kind='poche', depth=1.0), tp)
        em.travel(0.0, 0.0)
        S._ramp_closed(em, ring, 0.0, -2.0, 5.0)                         # 22,9 mm de pente : au-delà du premier côté
        line = LineString(ring)
        for m in em.moves:
            self.assertLess(line.distance(Point(m.x, m.y)), 1e-6, (m.x, m.y))


class TestPlotting(unittest.TestCase):
    """Le tracé dans TE13 (cône, 2 passes de 0,15 à 10°, le T de 140 mm de tour) : à chaque passe l'outil remonte, redescend à la
    passe d'avant et repart en pente de là, sur 0,85 mm ; puis le tour, et la partie en pente reprise à la cote."""
    T_SHAPE = [(10, 10), (50, 10), (50, 20), (35, 20), (35, 40), (25, 40), (25, 20), (10, 20)]
    KW = dict(kind='gravure', side='sur', depth=0.3, step_down=0.15, ramp_angle=10.0)
    SLOPE = 0.15 / math.tan(math.radians(10.0))

    def test_each_pass_starts_from_the_one_before(self):
        rs = runs(path_of((self.T_SHAPE,), ramp=True, **self.KW))
        self.assertEqual(len(rs), 2)
        for r in rs:
            self.assertAlmostEqual(lengths(r)[0], self.SLOPE, places=6)
            self.assertAlmostEqual(lengths(r)[1], 140.0, places=6)
        first = [m for m in rs[1] if m.kind == 'feed'][0]
        self.assertAlmostEqual(first.z, -0.3, places=6)                  # une seule pente, de -0,15 à -0,3
        self.assertAlmostEqual(math.hypot(first.x - rs[1][0].x, first.y - rs[1][0].y), self.SLOPE, places=6)

    def test_connected_it_stays_down(self):
        tp = path_of((self.T_SHAPE,), link_passes=True, **self.KW)
        rs = runs(tp)
        self.assertEqual(len(rs), 1)
        self.assertAlmostEqual(lengths(rs[0])[0], 2 * self.SLOPE, places=6)
        self.assertAlmostEqual(lengths(rs[0])[1], 280.0 - self.SLOPE, places=6)

    def test_without_a_ramp_it_stays_down_too(self):
        # TE13 sans plongée angulaire : descente verticale au départ
        self.assertEqual(len(runs(path_of((self.T_SHAPE,), **self.KW))), 1)

    def test_there_and_back(self):
        # l'aller-retour reprend la pente en revenant
        rs = runs(path_of((self.T_SHAPE,), link_passes=True, trace_mode='ar', **self.KW))
        self.assertEqual(len(rs), 1)
        self.assertAlmostEqual(lengths(rs[0])[0], 2 * self.SLOPE, places=6)
        self.assertAlmostEqual(lengths(rs[0])[1], 4 * 140.0 - 2 * self.SLOPE, places=6)

    def test_the_form_offers_it(self):
        from vectordrive.ui import cam_panel as P
        self.assertIn('link_passes', P.KIND_FIELDS['gravure'])


class TestPocket(unittest.TestCase):
    """Le balayage dans TE13 : d'une passe à l'autre, l'outil remonte et repart en pente de la passe d'avant, à 30° sur 1,73 mm."""

    def test_each_pass_slopes_from_the_one_before(self):
        tp = path_of(kind='poche', side='sur', ramp=True)
        ms = tp.moves
        slopes = [(a, b) for a, b in zip(ms, ms[1:]) if b.kind == 'feed' and b.z < a.z - 1e-9]
        self.assertTrue(slopes)
        self.assertAlmostEqual(steepest(tp), math.tan(math.radians(30.0)), places=6)
        self.assertAlmostEqual(sum(math.hypot(b.x - a.x, b.y - a.y) for a, b in slopes), 2 * SLOPE_1, places=6)

    def test_connected_it_stays_down(self):
        plain = path_of(kind='poche', side='sur', ramp=True)
        linked = path_of(kind='poche', side='sur', link_passes=True)
        self.assertLess(sum(m.kind == 'rapid' for m in linked.moves), sum(m.kind == 'rapid' for m in plain.moves))


class TestOldOperations(unittest.TestCase):

    def test_they_stay_in_the_material(self):
        d = M.Operation(kind='contour', ramp=True).to_dict()
        del d['link_rule']
        self.assertTrue(M.Operation.from_dict(d).link_passes)

    def test_the_plotting_too(self):
        d = M.Operation(kind='gravure', ramp=True).to_dict()
        del d['link_rule']
        self.assertTrue(M.Operation.from_dict(d).link_passes)

    def test_a_pocket_keeps_its_way(self):
        # le balayage remontait déjà entre deux passes
        d = M.Operation(kind='poche', ramp=True).to_dict()
        del d['link_rule']
        self.assertFalse(M.Operation.from_dict(d).link_passes)

    def test_without_a_ramp_nothing_changes(self):
        d = M.Operation(kind='contour').to_dict()
        del d['link_rule']
        self.assertFalse(M.Operation.from_dict(d).link_passes)

    def test_a_new_one_keeps_the_choice(self):
        o = M.Operation.from_dict(M.Operation(kind='contour', ramp=True).to_dict())
        self.assertFalse(o.link_passes)


class TestPresets(unittest.TestCase):

    def op(self, connect, ramp, kind='CP_Cutting_3D'):
        p = tpp.Preset(name='essai', kind=kind, sections={
            'PROFONDEUR': {'ZBOTTOM': '2.e-003', 'NBSLICES': '2'},
            'FAO_NEWPARAMGLOB': {'PLONGEEANGULAIRE_ATIVE': ramp, 'PLONGEEANGULAIRE_ANGLE': str(math.radians(30))},
            'Properties': {'ConnectToolpath': connect}})
        return tpp.to_template(p)['operations'][0]

    def test_connect_with_a_ramp(self):
        o = self.op('1', '1')
        self.assertTrue(o['ramp'])
        self.assertTrue(o['link_passes'])

    def test_no_connect_with_a_ramp(self):
        o = self.op('0', '1')
        self.assertTrue(o['ramp'])
        self.assertFalse(o['link_passes'])

    def test_the_plotting(self):
        self.assertTrue(self.op('1', '1', 'CP_Plotting')['link_passes'])
        self.assertFalse(self.op('0', '1', 'CP_Plotting')['link_passes'])

    def test_connect_without_a_ramp(self):
        # sans rampe, le détourage reste déjà en bas : « Connecter » y ajouterait une rampe que TE ne fait pas
        o = self.op('1', '0')
        self.assertFalse(o['ramp'])
        self.assertFalse(o['link_passes'])


class TestForm(unittest.TestCase):

    def test_the_form_offers_it(self):
        from vectordrive.ui import cam_panel as P
        self.assertIn('link_passes', P.KIND_FIELDS['contour'])
        self.assertIn('link_passes', P.LABELS)


if __name__ == '__main__':
    unittest.main()
