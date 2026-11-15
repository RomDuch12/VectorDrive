"""Round 938 : Poche, seulement le reste, en plusieurs passes — dans un même reste, l'outil descend à la passe suivante
sans remonter au dégagement (sauf rampe ou hélice réglée, ou départ trop loin)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r938.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from vectordrive.cam import model, strategies  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Document, Shape  # noqa: E402

W, H = 30.0, 15.0
CORNERS = ((0, 0), (W, 0), (W, H), (0, H))


def rect_doc():
    d = Document()
    d.layers[0].items.append(Shape(path=geom.Path([geom.rect(0, 0, W, H)])))
    return d


def plan(depth=1.5, **finish):
    big = model.CamTool(name='ébauche', diameter=4.0, step_down=0.5)
    small = model.CamTool(name='finition', diameter=1.0, step_down=0.5)
    s = model.CamSetup(tools=[big, small])
    a = model.Operation(name='ébauche', kind='poche', tool_id=big.id, depth=depth)
    b = model.Operation(name='finition', kind='poche', tool_id=small.id, depth=depth, rest_previous=True, **finish)
    s.operations = [a, b]
    return s, a, b


def retracts(moves, safe):
    """Remontées jusqu'au dégagement."""
    return sum(1 for p, m in zip(moves, moves[1:]) if m.z >= safe - 1e-9 and p.z < safe - 1e-9)


def levels_at(tp, corner):
    return sorted({round(m.z, 3) for m in tp.moves if m.kind != 'rapid' and m.z < -1e-6
                   and math.dist((m.x, m.y), corner) < 2.5})


class Levels(unittest.TestCase):

    def test_the_next_pass_of_a_rest_without_going_up(self):
        s, a, b = plan()
        tp = strategies.compute(rect_doc(), s, b)
        for c in CORNERS:
            self.assertEqual(levels_at(tp, c), [-1.5, -1.0, -0.5], c)        # les trois passes dans chaque coin
        self.assertLessEqual(retracts(tp.moves, b.safe_z), 4)               # avant : 12 (une par passe et par coin)
        down = [(p, m) for p, m in zip(tp.moves, tp.moves[1:]) if m.kind == 'plunge' and p.z < -1e-6]
        self.assertEqual(len(down), 8)                                       # deux descentes d'une passe par coin
        self.assertTrue(all(abs((p.z - m.z) - 0.5) < 1e-9 for p, m in down))
        rising = [(p, m) for p, m in zip(tp.moves, tp.moves[1:])            # et toujours aucune liaison en biais
                  if m.kind != 'rapid' and m.z > p.z + 1e-9 and math.dist((p.x, p.y), (m.x, m.y)) > 1e-6]
        self.assertEqual(rising, [])

    def test_only_near_and_without_a_ramp(self):
        tool = model.CamTool(name='f', diameter=1.0)
        op = model.Operation(kind='poche', tool_id=tool.id, depth=1.0)
        chains = [([(0.0, 0.0), (1.0, 0.0)], False)]
        em = strategies.Emitter(op, tool)
        strategies.mill_chains(em, chains, [-0.5, -1.0], lambda line: True, max_link=lambda z: 3.0)
        kinds = [(m.kind, m.x, m.y, m.z) for m in em.moves]
        self.assertEqual(kinds[-3:], [('feed', 0.0, 0.0, -0.5), ('plunge', 0.0, 0.0, -1.0), ('feed', 1.0, 0.0, -1.0)])
        self.assertEqual(retracts(em.moves, op.safe_z), 0)                   # avant : une remontée entre les deux passes
        em = strategies.Emitter(op, tool)
        strategies.mill_chains(em, chains, [-0.5, -1.0], lambda line: True, max_link=lambda z: 0.5)
        self.assertEqual(retracts(em.moves, op.safe_z), 1)                   # départ plus loin que la limite : remontée
        em = strategies.Emitter(op, tool)
        strategies.mill_chains(em, chains, [-0.5, -1.0], lambda line: True, 3.0, max_link=lambda z: 3.0)
        self.assertEqual(retracts(em.moves, op.safe_z), 1)                   # rampe réglée : l'entrée choisie
        em = strategies.Emitter(op, tool)
        strategies.mill_chains(em, chains, [-0.5, -1.0], lambda line: True)  # la poche entière : comme avant
        self.assertEqual(retracts(em.moves, op.safe_z), 1)

    def test_the_link_limit_is_the_same_at_every_level(self):
        s, a, b = plan(depth=5.0)
        s.tool(a.tool_id).step_down = s.tool(b.tool_id).step_down = 1.0
        a.stock = 0.2                                                        # le reste : une bande le long des bords
        tp = strategies.compute(rect_doc(), s, b)
        per_level = {}
        for p, m in zip(tp.moves, tp.moves[1:]):
            if m.kind == 'plunge':
                per_level[round(m.z, 3)] = per_level.get(round(m.z, 3), 0) + 1
        self.assertEqual(sorted(per_level), [-5.0, -4.0, -3.0, -2.0, -1.0])
        self.assertEqual(len(set(per_level.values())), 1, per_level)        # avant : 4, 4, 4, puis 2 et 2 plus bas


def doc_of(*contours):
    d = Document()
    d.layers[0].items.append(Shape(path=geom.Path(list(contours))))
    return d


def cut_steps(tp):
    out, prev = [], None
    for m in tp.moves:
        if prev is not None and m.kind != 'rapid' and min(prev.z, m.z) < -1e-6:
            out.append((prev, m))
        prev = m
    return out


def left_by(tp, reg, radius):
    """Aire que l'outil atteint et que le parcours ne balaie pas."""
    import shapely
    lines = [shapely.LineString([(p.x, p.y), (m.x, m.y)]) for p, m in cut_steps(tp)
             if math.dist((p.x, p.y), (m.x, m.y)) > 1e-9]
    swept = shapely.union_all(lines).buffer(radius, quad_segs=32)
    return reg.buffer(-radius, quad_segs=32).buffer(radius, quad_segs=32).difference(swept).area


class Review(unittest.TestCase):

    def test_finish_in_a_slot_nobody_opened_goes_level_by_level(self):
        d = doc_of(geom.rect(0, 0, 20.0, 1.2))                               # la fraise de 1 n'y entre qu'à la finition
        big = model.CamTool(name='ébauche', diameter=4.0, step_down=0.5)
        small = model.CamTool(name='finition', diameter=1.0, step_down=0.5)
        s = model.CamSetup(tools=[big, small])
        a = model.Operation(name='ébauche', kind='poche', tool_id=big.id, depth=3.0)
        b = model.Operation(name='finition', kind='poche', tool_id=small.id, depth=3.0, rest_previous=True,
                            stock=0.2, finish=True)
        s.operations = [a, b]
        tp = strategies.compute(d, s, b)
        cut = cut_steps(tp)
        self.assertTrue(cut)
        self.assertEqual(sorted({round(m.z, 3) for _p, m in cut}), [-3.0, -2.5, -2.0, -1.5, -1.0, -0.5])
        below = [max(0.0, -m.z) - max(0.0, -p.z) for p, m in zip(tp.moves, tp.moves[1:]) if m.kind == 'plunge']
        self.assertLessEqual(max(below), 0.5 + 1e-9)                         # avant : une plongée de 3 mm en pleine matière
        self.assertTrue(any('à toutes les cotes' in w for w in tp.warnings))

    def test_finish_along_a_stock_only_stays_at_the_bottom(self):
        d = doc_of(geom.circle((0.0, 0.0), 15.0))
        big = model.CamTool(name='ébauche', diameter=4.0, step_down=0.5)
        s = model.CamSetup(tools=[big])
        a = model.Operation(name='ébauche', kind='poche', tool_id=big.id, depth=1.5, stock=0.2)
        b = model.Operation(name='finition', kind='poche', tool_id=big.id, depth=1.5, rest_previous=True,
                            stock=0.2, finish=True)
        s.operations = [a, b]
        tp = strategies.compute(d, s, b)
        self.assertEqual(sorted({round(m.z, 3) for _p, m in cut_steps(tp)}), [-1.5])   # la surépaisseur seule : au fond
        self.assertFalse(any('à toutes les cotes' in w for w in tp.warnings))
        self.assertFalse(hasattr(strategies, 'pocket_gaps'))                # (la simulation retirée avec ce round)

    def test_nothing_left_in_a_t_shape(self):
        import shapely
        t_shape = [(0, 36), (23, 36), (23, 0), (37, 0), (37, 36), (60, 36), (60, 50), (0, 50)]   # barre 60 × 14, pied 14 × 36
        tool = model.CamTool(name='f', diameter=6.0, step_down=1.0)
        s = model.CamSetup(tools=[tool])
        for kw in ({}, {'corner_opt': True}, {'pocket_outside_in': True}):
            op = model.Operation(kind='poche', tool_id=tool.id, depth=0.5, stepover_mm=4.08, **kw)
            s.operations = [op]
            tp = strategies.compute(doc_of(geom.polyline(t_shape, closed=True)), s, op)
            self.assertLess(left_by(tp, shapely.Polygon(t_shape), 3.0), 0.05, kw)   # avant : 20,8 mm² dans le pied

    def test_full_width_step_adds_no_micro_cut(self):
        tool = model.CamTool(name='f', diameter=6.0, step_down=1.0)
        s = model.CamSetup(tools=[tool])
        op = model.Operation(kind='poche', tool_id=tool.id, depth=0.5, stepover_mm=6.0)
        s.operations = [op]
        tp = strategies.compute(doc_of(geom.circle((0.0, 0.0), 20.0)), s, op)
        self.assertFalse(any('reprise(s) d\'angle' in w for w in tp.warnings))        # avant : 256 de 0,002 mm
        short = [1 for p, m in cut_steps(tp) if 1e-9 < math.dist((p.x, p.y), (m.x, m.y)) < 0.01]
        self.assertEqual(short, [])


if __name__ == '__main__':
    unittest.main()
