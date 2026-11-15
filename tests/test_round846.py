"""Round 846 : ce que le détourage promet, il le tient. Une pièce retenue par ses pontets le reste, la rampe respecte son angle,
un contour non usiné se signale, et le tri manuel vaut pour tout le dessin."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Shape


def compute(paths, diameter=2.0, **kw):
    d = Document()
    d.plate = None
    for p in paths:
        d.add(Shape(path=p if isinstance(p, geom.Path) else geom.Path([p]), filled=True, tool=1))
    setup = M.setup_of(d)
    t = M.CamTool(name='F', diameter=diameter)
    setup.tools = [t]
    kw.setdefault('kind', 'contour')
    kw.setdefault('side', 'exterieur')
    kw.setdefault('depth', 5.0)
    kw.setdefault('step_down', 5.0)
    return S.compute(d, setup, M.Operation(tool_id=t.id, **kw))


def feeds(tp):
    return [(a, b) for a, b in zip(tp.moves, tp.moves[1:]) if b.kind == 'feed']


def plunge_points(tp):
    """Le point où l'outil entre dans la matière, à chaque descente depuis le dessus."""
    out = []
    for a, b in zip(tp.moves, tp.moves[1:]):
        if a.z > -1e-6 and b.z < -1e-6:
            out.append((a.x, a.y))
    return out


def square(x, y, w=20.0, h=None):
    return geom.rect(x, y, w, w if h is None else h)


def at_tab(tp, tab_z):
    """Les points parcourus à la hauteur du pontet."""
    return [(b.x, b.y) for a, b in feeds(tp) if abs(b.z - tab_z) < 1e-9 and abs(a.z - tab_z) < 1e-9]


class TestRamp(unittest.TestCase):

    def steepest(self, tp):
        worst = 0.0
        for a, b in feeds(tp):
            run = math.hypot(b.x - a.x, b.y - a.y)
            if b.z < a.z - 1e-9 and run > 1e-9:
                worst = max(worst, (a.z - b.z) / run)
        return worst

    def test_a_short_closed_contour_keeps_the_angle(self):
        """Un petit carré (8 mm de tour) et 1 mm à descendre à 5° : il faut 11,4 mm, donc plus d'un tour."""
        tp = compute([square(0, 0, 2.0)], kind='gravure', side='sur', depth=1.0, step_down=1.0, ramp=True, ramp_angle=5.0)
        self.assertLessEqual(self.steepest(tp), math.tan(math.radians(5.0)) + 1e-6)
        self.assertAlmostEqual(min(m.z for m in tp.moves), -1.0)

    def test_it_ends_with_a_full_turn_at_depth(self):
        tp = compute([square(0, 0, 2.0)], kind='gravure', side='sur', depth=1.0, step_down=1.0, ramp=True, ramp_angle=5.0)
        bottom = [(a, b) for a, b in feeds(tp) if abs(a.z + 1) < 1e-9 and abs(b.z + 1) < 1e-9]
        self.assertGreaterEqual(sum(math.hypot(b.x - a.x, b.y - a.y) for a, b in bottom), 8.0 - 1e-6)

    def test_a_long_contour_still_takes_one_turn(self):
        # un tour, et la partie en pente reprise à la cote (relevé dans TE13)
        tp = compute([square(0, 0, 50.0)], kind='gravure', side='sur', depth=1.0, step_down=1.0, ramp=True, ramp_angle=5.0)
        length = sum(math.hypot(b.x - a.x, b.y - a.y) for a, b in feeds(tp))
        self.assertAlmostEqual(length, 200.0 + 1.0 / math.tan(math.radians(5.0)), places=6)


class TestTabs(unittest.TestCase):
    TAB_Z = -4.0

    def base(self, **kw):
        return compute([square(0, 0, 40.0)], tabs=2, tab_width=2.0, tab_height=1.0, **kw)

    def test_the_finish_keeps_the_tabs(self):
        """Sans cela, la finition à pleine profondeur traverse les pontets : la pièce part."""
        tp = self.base(stock=0.2, finish=True)
        rough = self.base()
        self.assertGreater(len(at_tab(tp, self.TAB_Z)), len(at_tab(rough, self.TAB_Z)))

    def test_the_finish_tabs_face_the_rough_ones(self):
        """Pontets de l'ébauche et de la finition en vis-à-vis : ailleurs, le mur laissé par l'ébauche ne tient rien."""
        tp = self.base(stock=0.5, finish=True, step_down=5.0)
        outer = [p for p in at_tab(tp, self.TAB_Z) if not (-1.2 <= p[0] <= 41.2 and -1.2 <= p[1] <= 41.2)]
        inner = [p for p in at_tab(tp, self.TAB_Z) if -1.2 <= p[0] <= 41.2 and -1.2 <= p[1] <= 41.2]
        self.assertTrue(outer)
        self.assertTrue(inner)
        for p in inner:
            self.assertLess(min(math.dist(p, q) for q in outer), 6.0)

    def test_leads_keep_the_tabs(self):
        tp = self.base(lead_in=2.0, lead_out=2.0)
        self.assertTrue(at_tab(tp, self.TAB_Z))

    def test_leads_and_finish_keep_the_tabs(self):
        plain = self.base(lead_in=2.0, lead_out=2.0)
        tp = self.base(lead_in=2.0, lead_out=2.0, stock=0.2, finish=True)
        self.assertGreater(len(at_tab(tp, self.TAB_Z)), len(at_tab(plain, self.TAB_Z)))

    def test_an_inside_contour_has_its_tabs(self):
        tp = compute([square(0, 0, 40.0)], side='interieur', tabs=2, tab_width=2.0, tab_height=1.0)
        self.assertTrue(at_tab(tp, self.TAB_Z))

    def test_without_tabs_nothing_changes(self):
        tp = compute([square(0, 0, 40.0)], stock=0.2, finish=True)
        self.assertFalse(at_tab(tp, self.TAB_Z))

    def test_leave_uncut_says_it_drops_the_tabs(self):
        tp = compute([square(0, 0, 40.0)], tabs=2, tab_width=2.0, tab_height=1.0, leave_uncut=5.0)
        self.assertTrue(any('pontets ignorés' in w for w in tp.warnings), tp.warnings)


class TestLostContours(unittest.TestCase):

    def test_inside_a_contour_too_narrow(self):
        tp = compute([square(0, 0, 20.0), square(30, 0, 1.0)], side='interieur')
        self.assertTrue(any('1 contour' in w and 'non usiné' in w for w in tp.warnings), tp.warnings)

    def test_inside_all_is_well(self):
        tp = compute([square(0, 0, 20.0), square(30, 0, 10.0)], side='interieur')
        self.assertFalse(any('non usiné' in w or 'trajectoire' in w for w in tp.warnings), tp.warnings)

    def test_inside_a_neck_splits_the_path(self):
        """Deux carrés reliés par un col plus étroit que l'outil : deux trajectoires pour un contour."""
        pts = [(0, 0), (10, 0), (10, 4.5), (20, 4.5), (20, 0), (30, 0), (30, 10), (20, 10), (20, 5.5), (10, 5.5), (10, 10), (0, 10)]
        tp = compute([geom.polyline(pts, closed=True).close()], side='interieur')
        self.assertTrue(any('2 trajectoire(s)' in w and '1 contour(s)' in w for w in tp.warnings), tp.warnings)

    def test_outside_a_hole_too_small(self):
        tp = compute([geom.Path([square(0, 0, 20.0), geom.circle((10, 10), 0.5)])])
        self.assertTrue(any('1 trajectoire(s)' in w and '2 contour(s)' in w for w in tp.warnings), tp.warnings)

    def test_outside_a_good_hole(self):
        tp = compute([geom.Path([square(0, 0, 20.0), geom.circle((10, 10), 5.0)])])
        self.assertFalse(any('trajectoire' in w for w in tp.warnings), tp.warnings)

    def test_pieces_too_close_keep_their_message(self):
        tp = compute([square(0, 0, 10.0), square(10.5, 0, 10.0)])
        self.assertTrue(any('trop proche' in w for w in tp.warnings), tp.warnings)

    def test_a_pocket_too_narrow(self):
        tp = compute([square(0, 0, 20.0), square(30, 0, 1.0)], kind='poche')
        self.assertTrue(any('1 zone' in w and 'non usinée' in w for w in tp.warnings), tp.warnings)

    def test_a_pocket_all_is_well(self):
        tp = compute([square(0, 0, 20.0), square(30, 0, 10.0)], kind='poche')
        self.assertFalse(any('non usinée' in w for w in tp.warnings), tp.warnings)


class TestOrder(unittest.TestCase):

    def xs(self, tp):
        return [round(x, 0) for x, _y in plunge_points(tp)]

    def rows(self, tp, width=100.0):
        """La pièce de chaque plongée, d'après son abscisse : les pièces sont tous les 100 mm, le parcours déborde un peu."""
        return [round(x / width) for x, _y in plunge_points(tp)]

    def test_automatic_takes_the_nearest(self):
        tp = compute([square(200, 0), square(0, 0), square(100, 0)])
        self.assertEqual(self.rows(tp, 100.0), [0, 1, 2])

    def test_manual_follows_the_drawing(self):
        tp = compute([square(200, 0), square(0, 0), square(100, 0)], order_mode='dessin')
        self.assertEqual(self.rows(tp, 100.0), [2, 0, 1])

    def test_manual_small_first_is_still_small_first(self):
        tp = compute([square(200, 0, 30.0), square(0, 0, 30.0), square(100, 0, 10.0)], order_mode='dessin', small_first=True)
        self.assertEqual(self.rows(tp, 100.0), [1, 2, 0])

    def test_manual_holes_in_the_drawing_order_and_before_the_outside(self):
        plate = geom.Path([square(0, 0, 100.0), geom.circle((80, 50), 5.0), geom.circle((20, 50), 5.0), geom.circle((50, 50), 5.0)])
        tp = compute([plate], order_mode='dessin')
        pts = plunge_points(tp)
        self.assertEqual(len(pts), 4)
        self.assertEqual([round(x / 30) for x, _y in pts[:3]], [round(80 / 30), round(20 / 30), round(50 / 30)])

    def test_manual_pocket(self):
        tp = compute([square(200, 0), square(0, 0), square(100, 0)], kind='poche', order_mode='dessin')
        seen = []
        for k in self.rows(tp, 100.0):
            if k not in seen:
                seen.append(k)
        self.assertEqual(seen, [2, 0, 1])

    def plates(self, **kw):
        return compute([geom.Path([square(x, 0, 40.0), geom.circle((x + 20, 20), 5.0)]) for x in (0.0, 100.0)], **kw)

    def kinds(self, tp):
        """Pour chaque plongée : 't' si elle est sur un trou (près de son centre), 'e' sinon."""
        out = []
        for x, y in plunge_points(tp):
            cx = 20.0 if x < 60 else 120.0
            out.append('t' if math.hypot(x - cx, y - 20.0) < 10 else 'e')
        return ''.join(out)

    def test_element_by_element_by_default(self):
        self.assertEqual(self.kinds(self.plates()), 'tete')

    def test_all_the_holes_then_all_the_outsides(self):
        self.assertEqual(self.kinds(self.plates(holes_order='tous')), 'ttee')

    def test_all_the_holes_manual_order(self):
        tp = compute([geom.Path([square(x, 0, 40.0), geom.circle((x + 20, 20), 5.0)]) for x in (100.0, 0.0)],
                     holes_order='tous', order_mode='dessin')
        self.assertEqual(self.kinds(tp), 'ttee')
        self.assertEqual([0 if x < 60 else 1 for x, _y in plunge_points(tp)], [1, 0, 1, 0])


class TestPanel(unittest.TestCase):

    def test_the_option_is_offered(self):
        from vectordrive.ui import cam_panel as P
        self.assertIn('holes_order', P.LABELS)
        self.assertIn('holes_order', P.KIND_FIELDS['contour'])
        self.assertIn('holes_order', P.KIND_FIELDS['laser_decoupe'])


if __name__ == '__main__':
    unittest.main()
