"""Round 849 : Pointillés, Nettoyer les ponts, ponts sur un Tracé, nombre maximum de ponts ; balayage par zone."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import model as M, strategies as S
from vectordrive.cam.strategies import Emitter
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


def cut_length(tp, z=None):
    return sum(math.hypot(b.x - a.x, b.y - a.y) for a, b in feeds(tp) if z is None or abs(b.z - z) < 1e-9)


def entries(tp):
    return sum(1 for a, b in zip(tp.moves, tp.moves[1:]) if a.z > 1e-9 and b.z <= 1e-9)


SQUARE = geom.rect(0, 0, 40.0, 40.0)


class TestDashes(unittest.TestCase):

    def test_outside_the_tabs(self):
        ring = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        got = S.dashes(ring, [(10.0, 12.0), (30.0, 32.0)])
        self.assertEqual(len(got), 2)
        total = sum(sum(math.dist(p, q) for p, q in zip(d, d[1:])) for d in got)
        self.assertAlmostEqual(total, 36.0)

    def test_the_seam_is_not_a_cut(self):
        """Le départ d'un contour fermé n'est pas une attache : les deux morceaux n'en font qu'un."""
        ring = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        got = S.dashes(ring, [(10.0, 12.0)])
        self.assertEqual(len(got), 1)

    def test_an_open_line_keeps_both_ends(self):
        got = S.dashes([(0, 0), (40, 0)], [(19.0, 21.0)], closed=False)
        self.assertEqual([round(d[-1][0]) for d in got], [19, 40])

    def test_on_the_tabs(self):
        got = S.dashes([(0, 0), (40, 0)], [(19.0, 21.0)], closed=False, on_tabs=True)
        self.assertEqual(len(got), 1)
        self.assertAlmostEqual(math.dist(got[0][0], got[0][-1]), 2.0)


class TestContour(unittest.TestCase):

    def plain(self, **kw):
        return compute([SQUARE], **kw)

    def test_dotted_leaves_the_length_of_each_tab_uncut(self):
        whole = cut_length(self.plain(), -5.0)
        tp = self.plain(tabs=4, tab_width=2.0, tab_mode='pointille')
        self.assertAlmostEqual(cut_length(tp, -5.0), whole - 4 * (2.0 + 2.0), places=6)

    def test_dotted_rises_between_the_pieces(self):
        tp = self.plain(tabs=4, tab_width=2.0, tab_mode='pointille')
        self.assertEqual(entries(tp), 4)
        self.assertFalse([b for a, b in feeds(tp) if -5.0 < b.z < 0])

    def test_dotted_in_every_pass(self):
        tp = self.plain(tabs=2, tab_width=2.0, tab_mode='pointille', step_down=2.5)
        self.assertEqual(entries(tp), 4)

    def test_cleaning_machines_only_the_tabs_at_the_last_pass(self):
        tp = self.plain(tabs=4, tab_width=2.0, tab_mode='nettoyer', step_down=2.5)
        self.assertAlmostEqual(cut_length(tp), 4 * 4.0, places=6)
        self.assertAlmostEqual(min(m.z for m in tp.moves), -5.0)
        self.assertEqual(entries(tp), 4)

    def test_a_tab_stays_a_height_by_default(self):
        tp = self.plain(tabs=2, tab_width=2.0, tab_height=1.0)
        self.assertEqual(entries(tp), 1)
        self.assertTrue([b for a, b in feeds(tp) if abs(b.z + 4.0) < 1e-9])

    def test_dotted_with_leads(self):
        whole = compute([SQUARE], lead_in=2.0, lead_out=2.0)
        tp = compute([SQUARE], lead_in=2.0, lead_out=2.0, tabs=2, tab_width=2.0, tab_mode='pointille')
        self.assertAlmostEqual(cut_length(tp, -5.0), cut_length(whole, -5.0) - 2 * 4.0, places=3)

    def test_dotted_with_finish(self):
        tp = compute([SQUARE], tabs=2, tab_width=2.0, tab_mode='pointille', stock=0.2, finish=True)
        self.assertEqual(entries(tp), 4)

    def test_most_tabs(self):
        op = M.Operation(tab_spacing=10.0, tab_max=3)
        self.assertEqual(S.tab_count(op, [(0, 0), (100, 0)]), 3)
        op = M.Operation(tab_spacing=50.0, tab_max=3)
        self.assertEqual(S.tab_count(op, [(0, 0), (100, 0)]), 2)
        op = M.Operation(tab_spacing=10.0)
        self.assertEqual(S.tab_count(op, [(0, 0), (100, 0)]), 10)


class TestStraightTabs(unittest.TestCase):
    """Un pontet droit monte sur place. Il montait en pente depuis le sommet d'avant : sur ce rectangle, 200 mm restaient à
    moitié coupés au lieu de 20."""

    def tp(self, **kw):
        kw.setdefault('tabs', 2)
        return compute([geom.rect(0, 0, 100, 50)], diameter=6.0, depth=10.0, step_down=10.0, tab_width=4.0, tab_height=2.0, **kw)

    def lengths(self, tp):
        full = high = 0.0
        for a, b in feeds(tp):
            run = math.hypot(b.x - a.x, b.y - a.y)
            if abs(a.z + 10) < 1e-9 and abs(b.z + 10) < 1e-9:
                full += run
            else:
                high += run
        return full, high

    def test_only_the_tabs_are_left(self):
        full, high = self.lengths(self.tp())
        self.assertAlmostEqual(high, 2 * (4.0 + 6.0), places=6)
        whole, _none = self.lengths(self.tp(tabs=0))
        self.assertAlmostEqual(full + high, whole, places=6)

    def test_the_flanks_are_vertical(self):
        tp = self.tp()
        moving = [(a, b) for a, b in feeds(tp) if abs(b.z - a.z) > 1e-9]
        self.assertTrue(moving)
        for a, b in moving:
            self.assertLess(math.hypot(b.x - a.x, b.y - a.y), 1e-9)

    def test_the_way_down_is_a_plunge(self):
        tp = self.tp()
        downs = [b for a, b in zip(tp.moves, tp.moves[1:]) if abs(a.z + 8) < 1e-9 and abs(b.z + 10) < 1e-9]
        self.assertEqual(len(downs), 2)
        self.assertTrue(all(b.kind == 'plunge' for b in downs))

    def test_upper_passes_ignore_the_tabs(self):
        tp = compute([geom.rect(0, 0, 100, 50)], diameter=6.0, depth=10.0, step_down=5.0, tab_width=4.0, tab_height=2.0, tabs=2)
        self.assertFalse([b for a, b in feeds(tp) if abs(a.z + 5) < 1e-9 and abs(b.z + 5) > 1e-9 and b.z > -5])

    def test_curved_tabs_are_unchanged(self):
        tp = self.tp(tab_shape='incurve')
        _full, high = self.lengths(tp)
        self.assertAlmostEqual(high, 2 * (4.0 + 6.0), places=6)


class TestLaser(unittest.TestCase):
    """Le laser n'a pas de hauteur à laisser : ses pontets sont des micro-attaches."""

    def tp(self, **kw):
        return compute([SQUARE], kind='laser_decoupe', depth=0.0, step_down=0.0, diameter=0.2, **kw)

    def test_micro_joints(self):
        whole = cut_length(self.tp())
        got = self.tp(tabs=4, tab_width=0.5)
        self.assertAlmostEqual(cut_length(got), whole - 4 * (0.5 + 0.2), places=6)
        self.assertEqual(entries(got), 4)

    def test_the_beam_never_rises_above_the_sheet_while_cutting(self):
        got = self.tp(tabs=4, tab_width=0.5)
        self.assertTrue(all(abs(b.z) < 1e-9 for _a, b in feeds(got)))

    def test_with_leads(self):
        got = self.tp(tabs=2, tab_width=0.5, lead_in=1.0, lead_out=1.0)
        self.assertEqual(entries(got), 3)                # l'entrée et la sortie ne se rejoignent pas : trois morceaux

    def test_without_tabs_nothing_changes(self):
        self.assertEqual(entries(self.tp()), 1)

    def test_passes_repeat_the_same_joints(self):
        got = compute([SQUARE], kind='laser_decoupe', depth=0.0, step_down=0.0, diameter=0.2, tabs=2, tab_width=0.5, laser_passes=3)
        self.assertEqual(entries(got), 6)


class TestTrace(unittest.TestCase):
    """Page 788 : les ponts valent aussi sur un parcours de Tracé."""

    def line(self, **kw):
        return compute([geom.polyline([(0, 0), (40, 0)])], kind='gravure', side='sur', diameter=1.0, **kw)

    def test_no_tabs_by_default(self):
        tp = self.line()
        self.assertFalse([b for _a, b in feeds(tp) if -5.0 < b.z < 0])

    def test_a_height_on_a_line(self):
        tp = self.line(tabs=1, tab_width=2.0, tab_height=1.0)
        self.assertAlmostEqual(cut_length(tp, -4.0), 3.0, places=6)

    def test_dotted_on_a_line(self):
        tp = self.line(tabs=1, tab_width=2.0, tab_mode='pointille')
        self.assertAlmostEqual(cut_length(tp, -5.0), 37.0, places=6)
        self.assertEqual(entries(tp), 2)

    def test_cleaning_on_a_line(self):
        tp = self.line(tabs=1, tab_width=2.0, tab_mode='nettoyer')
        self.assertAlmostEqual(cut_length(tp, -5.0), 3.0, places=6)

    def test_a_line_with_one_way_passes(self):
        tp = self.line(tabs=1, tab_width=2.0, tab_height=1.0, trace_mode='aller_simple', step_down=2.5)
        self.assertAlmostEqual(cut_length(tp, -4.0), 3.0, places=6)

    def test_a_line_with_a_last_return(self):
        tp = self.line(tabs=1, tab_width=2.0, tab_height=1.0, trace_mode='dernier_ar')
        self.assertAlmostEqual(cut_length(tp, -4.0), 6.0, places=6)
        self.assertAlmostEqual(cut_length(tp, -5.0), 74.0, places=6)

    def test_a_closed_contour_on_the_line(self):
        tp = compute([SQUARE], kind='gravure', side='sur', diameter=1.0, tabs=2, tab_width=2.0, tab_mode='pointille')
        self.assertEqual(entries(tp), 2)
        self.assertAlmostEqual(cut_length(tp, -5.0), 160.0 - 2 * 3.0, places=6)


class TestZones(unittest.TestCase):

    def order(self, **kw):
        """La zone (0 ou 1) de chaque avance à fond, dans l'ordre."""
        tp = compute([geom.rect(0, 0, 20, 20), geom.rect(100, 0, 20, 20)], kind='poche', pocket_mode='balayage', depth=1.0,
                     step_down=1.0, sweep_angle=0.0, **kw)
        return [0 if b.x < 60 else 1 for a, b in feeds(tp) if abs(b.z + 1) < 1e-9]

    def changes(self, seq):
        return sum(1 for a, b in zip(seq, seq[1:]) if a != b)

    def test_jumping_over_islands_goes_back_and_forth(self):
        self.assertGreater(self.changes(self.order(sweep_by_zone=False, sweep_rule=0)), 3)   # l'ancienne règle ; TE13 reste forme par forme

    def test_zone_by_zone_finishes_one_first(self):
        self.assertEqual(self.changes(self.order(sweep_by_zone=True)), 1)

    def test_every_zone_is_fully_cut(self):
        a = compute([geom.rect(0, 0, 20, 20), geom.rect(100, 0, 20, 20)], kind='poche', pocket_mode='balayage', depth=1.0,
                    step_down=1.0, sweep_angle=0.0)
        b = compute([geom.rect(0, 0, 20, 20), geom.rect(100, 0, 20, 20)], kind='poche', pocket_mode='balayage', depth=1.0,
                    step_down=1.0, sweep_angle=0.0, sweep_by_zone=True)
        self.assertAlmostEqual(cut_length(a), cut_length(b), delta=cut_length(a) * 0.05)

    def test_one_zone_is_the_same(self):
        kw = dict(kind='poche', pocket_mode='balayage', depth=1.0, step_down=1.0, sweep_angle=0.0)
        a = compute([geom.rect(0, 0, 20, 20)], **kw)
        b = compute([geom.rect(0, 0, 20, 20)], sweep_by_zone=True, **kw)
        self.assertEqual(a.moves, b.moves)

    def test_the_outline_belongs_to_its_zone(self):
        tp = compute([geom.rect(0, 0, 20, 20), geom.rect(100, 0, 20, 20)], kind='poche', pocket_mode='balayage', depth=1.0,
                     step_down=1.0, sweep_angle=0.0, sweep_by_zone=True, sweep_contour='avant')
        seq = [0 if b.x < 60 else 1 for _a, b in feeds(tp) if abs(b.z + 1) < 1e-9]
        self.assertEqual(self.changes(seq), 1)


class TestPanel(unittest.TestCase):

    def test_the_fields_are_offered(self):
        from vectordrive.ui import cam_panel as P
        for name in ('tab_max', 'tab_mode', 'sweep_by_zone'):
            self.assertIn(name, P.LABELS)
        for name in ('tab_max', 'tab_mode'):
            self.assertIn(name, P.KIND_FIELDS['contour'])
            self.assertIn(name, P.KIND_FIELDS['gravure'])
        self.assertIn('tabs', P.KIND_FIELDS['laser_decoupe'])
        self.assertNotIn('tab_mode', P.KIND_FIELDS['laser_decoupe'])


if __name__ == '__main__':
    unittest.main()
