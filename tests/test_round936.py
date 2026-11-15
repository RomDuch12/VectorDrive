"""Round 936 : Poche, seulement le reste — d'un reste au suivant, l'outil ne reste au fond que si c'est plus court
que de remonter (avance de coupe contre plongée), et seulement à la cote de la passe ; corrections de relecture du
round 935 : passe de finition jamais sautée, passes d'avant plus écartées que le rayon, outil boule, recalcul annulé."""
import math
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r936.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.cam import model, strategies  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Shape  # noqa: E402

W, H = 30.0, 15.0


def rect_doc():
    d = Document()
    d.layers[0].items.append(Shape(path=geom.Path([geom.rect(0, 0, W, H)])))
    return d


def plan(depth=0.5, **finish):
    big = model.CamTool(name='ébauche', diameter=4.0, step_down=1.0)
    small = model.CamTool(name='finition', diameter=1.0, step_down=1.0)
    s = model.CamSetup(tools=[big, small])
    a = model.Operation(name='ébauche', kind='poche', tool_id=big.id, depth=depth)
    b = model.Operation(name='finition', kind='poche', tool_id=small.id, depth=depth, rest_previous=True, **finish)
    s.operations = [a, b]
    return s, a, b


def steps(tp):
    """(mouvement d'avant, mouvement) pour chaque mouvement d'avance dans la matière."""
    out, prev = [], None
    for m in tp.moves:
        if prev is not None and m.kind != 'rapid' and min(prev.z, m.z) < -1e-6:
            out.append((prev, m))
        prev = m
    return out


def longest(tp):
    return max(math.dist((p.x, p.y), (m.x, m.y)) for p, m in steps(tp))


def corners_reached(tp):
    pts = [(m.x, m.y) for _p, m in steps(tp)]
    return [any(math.dist(p, c) < 2.5 for p in pts) for c in ((0, 0), (W, 0), (W, H), (0, H))]


class Links(unittest.TestCase):

    def test_far_rests_are_joined_above_the_part(self):
        s, a, b = plan()
        tp = strategies.compute(rect_doc(), s, b)
        self.assertEqual(corners_reached(tp), [True] * 4)
        self.assertLess(longest(tp), 4.0)                       # avant : 14 et 29 mm au fond, d'un coin à l'autre
        self.assertEqual(len([m for m in tp.moves if m.kind == 'plunge']), 4)     # une descente par coin

    def test_several_passes_never_link_below_the_pass(self):
        s, a, b = plan(depth=1.5)
        small = s.tool(b.tool_id)
        small.step_down = 0.5                                   # trois passes
        tp = strategies.compute(rect_doc(), s, b)
        self.assertEqual(corners_reached(tp), [True] * 4)
        self.assertLess(longest(tp), 4.0)
        rising = [(p, m) for p, m in steps(tp)                  # avant : du fond d'un coin vers la 1re passe du suivant
                  if m.z > p.z + 1e-9 and math.dist((p.x, p.y), (m.x, m.y)) > 1e-6]
        self.assertEqual(rising, [])

    def test_a_short_hop_stays_down(self):
        tool = model.CamTool(name='f', diameter=1.0)
        op = model.Operation(kind='poche', tool_id=tool.id, depth=0.5)
        chains = [([(0.0, 0.0), (1.0, 0.0)], False), ([(2.0, 0.0), (3.0, 0.0)], False),
                  ([(20.0, 0.0), (21.0, 0.0)], False)]
        em = strategies.Emitter(op, tool)
        strategies.mill_chains(em, chains, [-0.5], lambda line: True, max_link=lambda z: 3.0)
        self.assertEqual(len([m for m in em.moves if m.kind == 'plunge']), 2)     # au départ, puis avant le reste éloigné
        self.assertIn(('feed', 2.0, 0.0, -0.5), [(m.kind, m.x, m.y, m.z) for m in em.moves])   # le petit saut, au fond
        em = strategies.Emitter(op, tool)
        strategies.mill_chains(em, chains, [-0.5], lambda line: True)             # sans limite : comme avant
        self.assertEqual(len([m for m in em.moves if m.kind == 'plunge']), 1)

    def test_the_limit_follows_the_feeds(self):
        tool = model.CamTool(name='f', diameter=1.0, feed=600.0, plunge=200.0)
        op = model.Operation(kind='poche', tool_id=tool.id, depth=0.5)
        self.assertAlmostEqual(strategies.stay_down_length(op, tool, 0.5, -0.5), 3.0)     # 1 mm de plongée, 3 fois plus lente
        op.plunge = 600.0
        self.assertAlmostEqual(strategies.stay_down_length(op, tool, 0.5, -0.5), 1.0)
        big = model.CamTool(name='g', diameter=6.0, feed=600.0, plunge=600.0)
        self.assertAlmostEqual(strategies.stay_down_length(op, big, 0.5, -0.5), 6.0)       # jamais moins que le diamètre
        self.assertAlmostEqual(strategies.stay_down_length(op, tool, 0.5, -0.5, 3.0),
                               0.5 / math.tan(math.radians(3.0)))                          # descente en hélice : plus longue


def doc_of(*contours):
    d = Document()
    d.layers[0].items.append(Shape(path=geom.Path(list(contours))))
    return d


def cuts(tp):
    return [(m.x, m.y) for _p, m in steps(tp)]


class Finish(unittest.TestCase):

    def test_finish_pass_alone_when_nothing_else_is_left(self):
        d = doc_of(geom.circle((0.0, 0.0), 15.0))
        s, a, b = plan(stock=0.2, finish=True)
        a.stock = 0.2                                           # l'ébauche laisse 0,2 mm, sans passe de finition
        b.tool_id = a.tool_id                                   # le même outil : rien d'autre à reprendre
        tp = strategies.compute(d, s, b)
        pts = cuts(tp)
        self.assertTrue(pts)                                    # avant : rien, « rien à nettoyer »
        self.assertTrue(all(abs(math.hypot(*p) - 13.0) < 0.05 for p in pts))      # le tour, à un rayon du bord
        self.assertGreater(sum(math.dist((p.x, p.y), (m.x, m.y)) for p, m in steps(tp)), 2 * math.pi * 13.0 * 0.95)
        self.assertTrue(any('passe de finition seule' in w for w in tp.warnings))

    def test_finish_pass_in_every_shape(self):
        d = doc_of(geom.rect(0, 0, W, H), geom.circle((60.0, 7.5), 7.0))
        s, a, b = plan(stock=0.2, finish=True)
        a.stock = 0.2
        tp = strategies.compute(d, s, b)
        on_circle = [p for p in cuts(tp) if abs(math.dist(p, (60.0, 7.5)) - 6.5) < 0.05]
        self.assertGreater(len(on_circle), 20)                  # avant : aucune passe sur le cercle (sans coin à reprendre)
        self.assertTrue(any(abs(p.y - 0.5) < 0.05 and abs(m.y - 0.5) < 0.05 and abs(m.x - p.x) > 20
                            for p, m in steps(tp)))             # et le long du rectangle


class WideSteps(unittest.TestCase):

    def plan6(self):
        big = model.CamTool(name='ébauche', diameter=6.0, step_down=1.0)
        small = model.CamTool(name='finition', diameter=1.0, step_down=1.0)
        s = model.CamSetup(tools=[big, small])
        a = model.Operation(name='ébauche', kind='poche', tool_id=big.id, depth=0.5, stepover_mm=5.0)
        b = model.Operation(name='finition', kind='poche', tool_id=small.id, depth=0.5, rest_previous=True)
        s.operations = [a, b]
        return s, a, b

    @staticmethod
    def left_by(tp, reg, radius, margin=0.0):
        """Aire que l'outil atteint (ses centres possibles, élargis de son rayon) et que le parcours ne balaie pas.
        `margin` : bande ignorée le long des parois (une courbe aplatie n'est pas le tracé exact)."""
        import shapely
        lines = [shapely.LineString([(p.x, p.y), (m.x, m.y)]) for p, m in steps(tp)
                 if math.dist((p.x, p.y), (m.x, m.y)) > 1e-9]
        swept = shapely.union_all(lines).buffer(radius, quad_segs=32)
        reach = reg.buffer(-radius - margin, join_style='mitre').buffer(radius, quad_segs=32)
        return reach.difference(swept).area

    def test_the_pocket_takes_the_island_its_wide_passes_would_leave(self):
        import shapely
        box = shapely.box(0, 0, 23.9, 23.9)                     # passes à 3 et 8 mm du bord : un îlot de 1,9 mm au centre
        d = doc_of(geom.rect(0, 0, 23.9, 23.9))
        s, a, b = self.plan6()
        tp = strategies.compute(d, s, a)
        self.assertTrue(any(math.dist(p, (11.95, 11.95)) < 1.5 for p in cuts(tp)))    # avant : rien au centre
        self.assertLess(self.left_by(tp, box, 3.0), 0.05)       # avant : 3,61 mm²
        self.assertTrue(any('1 îlot(s) repris' in w for w in tp.warnings))
        tp = strategies.compute(d, s, b)                        # la finition, seulement le reste : les coins
        self.assertFalse(any(math.dist(p, (11.95, 11.95)) < 3.0 for p in cuts(tp)))
        self.assertFalse(any('non comptée' in w for w in tp.warnings))
        a.pocket_outside_in = True                              # du bord vers le centre : l'îlot après sa passe
        tp = strategies.compute(d, s, a)
        self.assertLess(self.left_by(tp, box, 3.0), 0.05)
        last = cuts(tp)[-1]
        self.assertLess(math.dist(last, (11.95, 11.95)), 1.5)

    def test_corner_slivers_are_taken_where_they_would_stay(self):
        import shapely
        box = shapely.box(0, 0, 40.0, 30.0)
        d = doc_of(geom.rect(0, 0, 40.0, 30.0))
        s, a, b = self.plan6()
        a.stepover_mm = 5.6                                     # plus de 1,7 rayon : des lamelles dans les coins à 90°
        tp = strategies.compute(d, s, a)
        self.assertLess(self.left_by(tp, box, 3.0), 0.05)       # avant : 3 mm², sans « Optimisation des angles »
        self.assertTrue(any('reprise(s) d\'angle, entre des passes' in w for w in tp.warnings))
        a.stepover_mm = 4.2                                     # 1,4 rayon : rien ne reste dans un coin à 90°
        tp = strategies.compute(d, s, a)
        self.assertLess(self.left_by(tp, box, 3.0), 0.05)
        self.assertFalse(any('reprise(s) d\'angle' in w for w in tp.warnings))       # aucune reprise inutile
        a.corner_opt = True                                     # demandée : faite, et dite comme avant
        tp = strategies.compute(d, s, a)
        self.assertTrue(any(w.endswith('reprise(s) d\'angle') for w in tp.warnings))

    def test_what_stays_in_a_narrow_passage_is_taken(self):
        import shapely
        frame, star = geom.rect(-40, -38, 80, 76), geom.star((0.0, 0.0), 30.0, 13.0, 5)
        d = doc_of(frame, star)
        s, a, b = self.plan6()
        a.stepover_mm = 4.2                                     # entre les pointes de l'étoile et le cadre
        tp = strategies.compute(d, s, a)
        reg = strategies.region([g for it in strategies.source_items(d, a) if (g := strategies.item_geometry(it))],
                                s.tolerance)
        self.assertLess(self.left_by(tp, reg, 3.0, margin=0.02), 0.3)                 # avant : 17 mm²
        wall = shapely.union_all([reg.exterior] + list(reg.interiors))
        self.assertGreater(min(wall.distance(shapely.Point(p)) for p in cuts(tp)), 3.0 - 0.02)   # sans entamer les bords

    def test_no_gap_when_the_passes_overlap_the_radius(self):
        import shapely
        d = doc_of(geom.rect(0, 0, 23.9, 23.9))
        s, a, b = self.plan6()
        a.stepover_mm = 3.0                                     # le rayon : rien entre les passes
        box = shapely.box(0, 0, 23.9, 23.9)
        tp = strategies.compute(d, s, a)
        self.assertFalse(any('repris' in w or 'laissés' in w for w in tp.warnings))
        self.assertLess(self.left_by(tp, box, 3.0), 0.05)


class Spiral(unittest.TestCase):

    def pocket(self, contour, **kw):
        tool = model.CamTool(name='f', diameter=6.0, step_down=1.0)
        s = model.CamSetup(tools=[tool])
        op = model.Operation(kind='poche', tool_id=tool.id, depth=0.5, pocket_spiral=True, **kw)
        s.operations = [op]
        return strategies.compute(doc_of(contour), s, op)

    def test_the_spiral_leaves_nothing_in_the_middle(self):
        import shapely
        tp = self.pocket(geom.rect(0, 0, 40, 30))               # pas de 40 % : le réglage d'origine
        self.assertTrue(any('1 spirale(s)' in w for w in tp.warnings))
        self.assertLess(WideSteps.left_by(tp, shapely.box(0, 0, 40, 30), 3.0), 0.05)     # avant : 15 mm² au centre

    def test_the_spiral_from_the_edge_leaves_nothing_along_the_walls(self):
        import shapely
        tp = self.pocket(geom.circle((0.0, 0.0), 20.0), pocket_outside_in=True)
        self.assertTrue(any('1 spirale(s)' in w for w in tp.warnings))
        disc = shapely.Point(0.0, 0.0).buffer(20.0, quad_segs=64)
        self.assertLess(WideSteps.left_by(tp, disc, 3.0, margin=0.05), 0.5)              # avant : plus de 100 mm²

    def test_what_the_spiral_misses_in_an_arm_is_taken(self):
        import shapely
        pts = [(0, 0), (50, 0), (50, 18), (20, 18), (20, 45), (0, 45)]         # un L : l'anneau du milieu n'existe que
        reg = shapely.Polygon(pts)                                              # dans un bras
        for outside_in in (False, True):
            tp = self.pocket(geom.polyline(pts, closed=True), stepover_mm=3.0, pocket_outside_in=outside_in)
            self.assertTrue(any('1 spirale(s)' in w for w in tp.warnings))
            self.assertTrue(any('repris' in w for w in tp.warnings))
            self.assertLess(WideSteps.left_by(tp, reg, 3.0), 0.05, outside_in)  # avant : 65 mm² (278 en partant du bord)
            wall = reg.exterior
            self.assertGreater(min(wall.distance(shapely.Point(p)) for p in cuts(tp)), 3.0 - 0.02)   # sans entamer le bord

    def test_wide_passes_are_rings_not_a_spiral(self):
        import shapely
        tp = self.pocket(geom.rect(0, 0, 23.9, 23.9), stepover_mm=5.0)
        self.assertTrue(any('en anneaux' in w for w in tp.warnings))                    # avant : une spirale, 39 mm² laissés
        self.assertFalse(any('spirale(s)' in w for w in tp.warnings))
        self.assertLess(WideSteps.left_by(tp, shapely.box(0, 0, 23.9, 23.9), 3.0), 0.05)

    def test_ball_with_wide_passes_is_not_counted(self):
        ball = model.CamTool(name='boule', kind='boule', diameter=4.0, step_down=1.0, stepover=0.8)
        op = model.Operation(kind='poche', tool_id=ball.id, depth=2.0)
        self.assertFalse(strategies.clears_all(op, ball))       # avant : comptée, crêtes sur toute la hauteur
        ball.stepover = 0.4
        self.assertTrue(strategies.clears_all(op, ball))


class Panel(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.cp = self.w.cam_panel
        sh = Shape(path=geom.Path([geom.rect(0, 0, W, H)]))
        self.w.canvas.doc.active_layer.items.append(sh)
        s = self.cp.setup()
        big = model.CamTool(name='ébauche 936', diameter=4.0, step_down=1.0)
        small = model.CamTool(name='finition 936', diameter=1.0, step_down=1.0)
        s.tools = [big, small]
        s.operations = [model.Operation(name='A', kind='poche', tool_id=big.id, items=[sh.id], depth=0.5),
                        model.Operation(name='B', kind='poche', tool_id=small.id, items=[sh.id], depth=0.5,
                                        rest_previous=True)]
        self.cp.save(s)

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_a_cancelled_recompute_is_not_up_to_date(self):
        from vectordrive.ui import progress
        s = self.cp.setup()
        for op in s.operations:
            self.cp.compute_op(op)
        self.assertTrue(self.cp.inputs_current())
        s = self.cp.setup()
        s.operations[0].stock = 0.2
        self.cp.save(s)
        calls = []

        def run(_win, _title, fn, *args):
            calls.append(fn)
            if len(calls) == 2:                                 # le recalcul de B : annulé
                raise progress.Cancelled()
            return fn(*args)
        with mock.patch.object(progress, 'run', side_effect=run):
            self.cp.compute_op(s.operations[0])
        self.assertEqual(len(calls), 2)
        self.assertFalse(self.cp.inputs_current())              # avant : B donnée pour à jour, avec son ancien parcours
        self.cp.compute_op(self.cp.setup().operations[1])       # refaite : tout est à jour
        self.assertTrue(self.cp.inputs_current())


if __name__ == '__main__':
    unittest.main()
