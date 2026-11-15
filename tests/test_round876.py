"""Round 876 : le Balayage relevé dans TE13. Les points attendus viennent des parcours calculés par TE13 sur mes dessins (T et triangle ; U et carré percé), outil Ø6,
3 mm entre passes, sans surépaisseur."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from shapely.geometry import Polygon

from vectordrive.cam import model as M
from vectordrive.cam import strategies as S
from vectordrive.cam import tpp
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape

TEE = [(10, 10), (50, 10), (50, 20), (35, 20), (35, 40), (25, 40), (25, 20), (10, 20)]
TRI = [(70, 15), (90, 15), (80, 40)]
UU = [(10, 10), (70, 10), (70, 50), (55, 50), (55, 25), (25, 25), (25, 50), (10, 50)]
OUT = [(90, 10), (130, 10), (130, 50), (90, 50)]
HOLE = [(105, 25), (105, 35), (115, 35), (115, 25)]


def path_of(items, **kw):
    doc = Document()
    doc.plate = Plate(width=150.0, height=60.0)
    doc.layers = [Layer(name='A', items=items)]
    setup = M.setup_of(doc)
    t = M.CamTool(name='F', diameter=6.0)
    setup.tools.append(t)
    a = dict(kind='poche', pocket_mode='balayage', tool_id=t.id, stepover_mm=3.0, stock=0.0, depth=1.0, step_down=1.0, sweep_contour='sans')
    a.update(kw)
    op = M.Operation(**a)
    setup.operations.append(op)
    M.store(doc, setup)
    return S.compute(doc, setup, op, (0.0, 0.0))


def shape(*contours):
    return Shape(path=geom.Path([geom.polyline(c, closed=True) for c in contours]))


def tee(**kw):
    return path_of([shape(TEE), shape(TRI)], **kw)


def you(**kw):
    return path_of([shape(UU), shape(OUT, HOLE)], **kw)


def cut_points(tp):
    return [(round(m.x, 2), round(m.y, 2)) for m in tp.moves if m.kind != 'rapid' and m.z < -1e-9]


def entries(tp):
    ms = tp.moves
    return [(round(m.x, 2), round(m.y, 2)) for i, m in enumerate(ms) if m.kind == 'rapid' and i + 1 < len(ms) and ms[i + 1].kind != 'rapid']


def flat_length(tp, z):
    out, q = 0.0, None
    for m in tp.moves:
        if q is not None and m.kind != 'rapid' and abs(m.z - z) < 1e-6 and abs(q.z - z) < 1e-6:
            if m.is_arc:
                rr, _a, sw = M.arc_sweep((q.x, q.y, q.z), m)
                out += abs(rr * sw)
            else:
                out += math.hypot(m.x - q.x, m.y - q.y)
        q = m
    return out


class TestRows(unittest.TestCase):

    def test_from_the_bottom_without_the_bottom_itself(self):
        # le T creusé d'un Ø6 : la zone va de 13 à 37 ; rangées 37, 34… 16, pas 13
        tp = tee()
        ys = {y for x, y in cut_points(tp) if x < 60}
        for y in (37.0, 34.0, 31.0, 28.0, 25.0, 22.0, 19.0, 16.0):
            self.assertIn(y, ys)
        self.assertNotIn(13.0, ys)                                        # sans cassé d'angle : ni sur le bas de la zone

    def test_a_row_on_an_edge_crosses_the_shape(self):
        # le U : la rangée de 22 longe le fond de l'échancrure et va d'un bord à l'autre
        rows = S.sweep_rows(Polygon([(13, 13), (67, 13), (67, 47), (58, 47), (58, 22), (22, 22), (22, 47), (13, 47)]), 0.0, 3.0)
        at_22 = [r for r in rows if abs(r[0][0][1] - 22.0) < 1e-3]
        self.assertEqual(len(at_22), 1)
        self.assertEqual(len(at_22[0]), 1)
        self.assertAlmostEqual(abs(at_22[0][0][1][0] - at_22[0][0][0][0]), 54.0, delta=1e-3)


class TestChains(unittest.TestCase):

    def test_the_tee_stays_down(self):
        # TE13, début de la passe : relevé
        got = cut_points(tee())[:10]
        self.assertEqual(got[:9], [(32.0, 37.0), (28.0, 37.0), (28.0, 34.0), (32.0, 34.0), (32.0, 31.0), (28.0, 31.0), (28.0, 28.0), (32.0, 28.0), (32.0, 25.0)])

    def test_links_follow_the_edge(self):
        # de la rangée de 19 à celle de 16, l'outil suit le bord : (25, 17), (13, 17), (13, 16)
        pts = cut_points(tee())
        i = pts.index((13.0, 17.0))
        self.assertIn((25.0, 17.0), pts[i - 3:i])
        self.assertEqual(pts[i + 1:i + 3], [(13.0, 16.0), (47.0, 16.0)])

    def test_lengths(self):
        # longueurs par passe relevées, en mm : T et triangle, sans et avec cassé d'angle
        self.assertAlmostEqual(flat_length(tee(), -1.0), 127.3, delta=0.1)
        self.assertAlmostEqual(flat_length(tee(sweep_contour='apres'), -1.0), 281.9, delta=0.1)
        self.assertAlmostEqual(flat_length(you(), -1.0), 691.9, delta=0.1)
        self.assertAlmostEqual(flat_length(you(sweep_contour='apres'), -1.0), 1110.2, delta=0.1)

    def test_the_u_and_the_square(self):
        # relevé : le bras gauche ; le bras droit et le fond ; le haut du carré et sa gauche ; le bas ; la droite
        self.assertEqual(entries(you())[:5], [(22.0, 46.0), (67.0, 46.0), (127.0, 46.0), (127.0, 22.0), (127.0, 37.0)])


class TestSense(unittest.TestCase):

    def test_conventional_and_climb(self):
        # relevé : chaque rangée dans le même sens, l'outil remonte entre deux
        for sense, first, second in (('opposition', (32.0, 37.0), (28.0, 37.0)), ('avalant', (28.0, 37.0), (32.0, 37.0))):
            pts = cut_points(tee(sweep_direction=sense))
            self.assertEqual(pts[:2], [first, second], sense)
        self.assertAlmostEqual(flat_length(tee(sweep_direction='opposition'), -1.0), 82.9, delta=0.1)

    def test_fixed_sense_follows_its_own_chains(self):
        # relevé : en opposition, le bras gauche continue dans le fond, le bras droit vient après
        got = entries(you(sweep_direction='opposition'))
        self.assertEqual(got[8], (67.0, 22.0))
        self.assertEqual(got[11], (67.0, 46.0))

    def test_jumping_islands(self):
        # relevé : rangée après rangée, le sens alterne, l'outil saute l'échancrure
        got = entries(you(sweep_by_zone=False))
        self.assertEqual(got[:4], [(13.0, 46.0), (58.0, 46.0), (67.0, 43.0), (22.0, 43.0)])

    def test_jumping_islands_stays_in_the_shape(self):
        # relevé : l'outil finit le U avant de passer au carré, à chaque passe
        got = entries(you(sweep_by_zone=False, depth=1.0, step_down=0.5, pass_order='global'))
        xs = [x for x, _y in got]
        changes = sum(1 for a, b in zip(xs, xs[1:]) if (a < 80) != (b < 80))
        self.assertEqual(changes, 3)


class TestOutline(unittest.TestCase):

    def test_after(self):
        # relevé : (13, 13) après la dernière rangée, le premier sommet du dessin
        tp = tee(sweep_contour='apres', start_policy='dessin')
        self.assertEqual(entries(tp)[:2], [(32.0, 37.0), (13.0, 13.0)])

    def test_before(self):
        tp = tee(sweep_contour='avant', start_policy='dessin')
        self.assertEqual(entries(tp)[:2], [(13.0, 13.0), (32.0, 37.0)])

    def test_holes_first(self):
        # relevé : le trou du carré depuis (102, 25), puis son bord depuis (93, 13)
        got = entries(you(sweep_contour='apres', start_policy='dessin'))
        self.assertEqual(got[6:8], [(102.0, 25.0), (93.0, 13.0)])


class TestEntry(unittest.TestCase):

    def test_there_and_back(self):
        # relevé à 20°, 0,5 de passe : aller de 0,687 mm, à mi-profondeur, retour au point de départ
        tp = tee(depth=1.0, step_down=0.5, ramp=True, ramp_angle=20.0, sweep_contour='apres')
        ms = [m for m in tp.moves if m.kind != 'rapid']
        self.assertAlmostEqual(ms[1].x, 31.313, delta=2e-3)
        self.assertAlmostEqual(ms[1].y, 37.0, delta=1e-3)
        self.assertAlmostEqual(ms[1].z, -0.25, delta=1e-6)
        self.assertAlmostEqual(ms[2].x, 32.0, delta=1e-6)
        self.assertAlmostEqual(ms[2].z, -0.5, delta=1e-6)

    def test_from_the_previous_pass(self):
        # à la deuxième passe, l'outil part de -0,5
        tp = tee(depth=1.0, step_down=0.5, ramp=True, ramp_angle=20.0)
        q = None
        seen = []
        for m in tp.moves:
            if q is not None and q.kind == 'plunge' and m.kind != 'rapid' and abs(m.x - q.x) > 1e-6:
                seen.append(round(q.z, 3))
            q = m
        self.assertIn(-0.5, seen)

    def test_total_ramp_length(self):
        self.assertAlmostEqual(self.slopes(tee(depth=1.0, step_down=0.5, ramp=True, ramp_angle=20.0)), 5.5, delta=0.05)
        self.assertAlmostEqual(self.slopes(tee(depth=1.0, step_down=0.5, ramp=True, ramp_angle=20.0, sweep_contour='apres')), 11.0, delta=0.05)

    def slopes(self, tp):
        out, q = 0.0, None
        for m in tp.moves:
            if q is not None and m.kind != 'rapid' and abs(m.z - q.z) > 1e-6:
                out += math.hypot(m.x - q.x, m.y - q.y)
            q = m
        return out

    def test_a_short_row_keeps_the_angle(self):
        em = S.Emitter(M.Operation(), M.CamTool(name='F', diameter=6.0))
        S._sweep_entry(em, [(0.0, 0.0), (0.5, 0.0)], 0.0, -1.0, 20.0)
        self.assertAlmostEqual(em.pos[2], -1.0, delta=1e-9)
        self.assertEqual(em.pos[:2], (0.0, 0.0))
        q = None
        for m in em.moves:
            if q is not None and m.kind != 'rapid' and abs(m.x - q.x) > 1e-9:
                self.assertLessEqual(abs(m.z - q.z) / abs(m.x - q.x), math.tan(math.radians(20.0)) + 1e-6)
                self.assertLessEqual(m.x, 0.5 + 1e-9)
            q = m


class TestOrderAndAngle(unittest.TestCase):

    def test_global(self):
        got = [x for x, _y in entries(tee(depth=1.0, step_down=0.5, pass_order='global'))]
        self.assertEqual([x < 60 for x in got], [True, False, True, False])

    def test_shape_by_shape(self):
        got = [x for x, _y in entries(tee(depth=1.0, step_down=0.5))]
        self.assertEqual([x < 60 for x in got], [True, True, False, False])

    def test_the_best_angle(self):
        # relevé : le T à 0°, le U le long de ses bras, le triangle le long d'un côté, le carré percé à -90°
        inset = lambda pts, *h: Polygon(pts, list(h)).buffer(-3.0, join_style='mitre')
        self.assertEqual(S.sweep_best_angle(inset(TEE)), 0.0)
        self.assertEqual(S.sweep_best_angle(inset(UU)), 90.0)
        self.assertAlmostEqual(S.sweep_best_angle(inset(TRI)), -68.2, delta=0.1)
        self.assertEqual(S.sweep_best_angle(inset(OUT, HOLE)), -90.0)

    def test_the_best_angle_is_used(self):
        pts = cut_points(you(sweep_angle_mode='optimise'))
        self.assertEqual(pts[:3], [(13.0, 47.0), (13.0, 13.0), (16.0, 13.0)])

    def test_a_fixed_angle(self):
        pts = cut_points(you(sweep_angle=45.0))
        self.assertAlmostEqual(pts[0][0], 16.15, delta=0.02)
        self.assertEqual(pts[0][1], 47.0)
        self.assertAlmostEqual(flat_length(you(sweep_angle=45.0), -1.0), 798.0, delta=0.1)

    def test_turning_at_each_pass(self):
        # relevé : 0°, 90°, 180° aux trois passes
        tp = you(depth=1.0, step_down=1.0 / 3, sweep_angle_mode='croise', sweep_angle_incr=90.0)
        got = entries(tp)
        self.assertEqual(got[0], (22.0, 46.0))
        self.assertIn((13.0, 47.0), got)
        self.assertIn((13.0, 14.0), got)
        self.assertAlmostEqual(flat_length(tp, -1.0 / 3) + flat_length(tp, -2.0 / 3) + flat_length(tp, -1.0), 2088.3, delta=0.5)


class TestOldOperations(unittest.TestCase):

    def test_a_saved_operation_keeps_its_rule(self):
        d = M.Operation(kind='poche', pocket_mode='balayage').to_dict()
        d.pop('sweep_rule')
        d.pop('sweep_by_zone')
        op = M.Operation.from_dict(d)
        self.assertEqual(op.sweep_rule, 0)
        self.assertIs(op.sweep_by_zone, False)

    def test_new_ones_are_like_te13(self):
        op = M.Operation.from_dict(M.Operation(kind='poche').to_dict())
        self.assertEqual(op.sweep_rule, 876)
        self.assertIs(op.sweep_by_zone, True)

    def test_the_old_rule_still_runs(self):
        pts = cut_points(tee(sweep_rule=0, sweep_by_zone=False))
        self.assertAlmostEqual(pts[0][1], 14.5, delta=1e-3)                 # au milieu de la première bande


class TestImport(unittest.TestCase):

    def op(self, **sw):
        s = {'AngleMode': '2', 'AngleDecal': '0.', 'AngleIncr': '0.', 'BreakAngleClimb': '1', 'BreakAngleMode': '1', 'Stepover': '3.e-003', 'SweepingMode': '1', 'SweepingType': '1'}
        s.update(sw)
        return tpp.to_template(tpp.Preset(name='b', kind='CP_Sweeping', sections={'SPECIALSWEEPING': s}))['operations'][0]

    def test_the_type(self):
        self.assertIs(self.op()['sweep_by_zone'], True)
        self.assertIs(self.op(SweepingType='2')['sweep_by_zone'], False)
        self.assertEqual(self.op()['sweep_rule'], 876)

    def test_the_turn(self):
        self.assertAlmostEqual(self.op(AngleIncr='1.5707963267949')['sweep_angle_incr'], 90.0, delta=1e-3)

    def test_the_outline_sense(self):
        self.assertIs(self.op(BreakAngleMode='3', BreakAngleClimb='2')['climb'], True)
        self.assertIs(self.op(BreakAngleMode='3', BreakAngleClimb='1')['climb'], False)


class TestForm(unittest.TestCase):

    def test_the_form_offers_it(self):
        from vectordrive.ui import cam_panel as P
        self.assertIn('sweep_angle_incr', P.KIND_FIELDS['poche'])
        self.assertIn('sweep_angle_incr', P.LABELS)


if __name__ == '__main__':
    unittest.main()
