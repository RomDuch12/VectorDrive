"""Round 879 : le fond de la Gravure 3D par branches, comme TE13."""
import math
import unittest

from shapely.geometry import Polygon, box

from vectordrive.cam import model as M
from vectordrive.cam import strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape


def P(*pts):
    return geom.polyline(list(pts), closed=True)


FRAME = [P((10, 10), (60, 10), (60, 60), (10, 60)), P((20, 20), (50, 20), (50, 50), (20, 50))]
ISLAND = [P((80, 10), (120, 10), (120, 50), (80, 50))]


def path_of(shapes, **kw):
    doc = Document()
    doc.plate = Plate(width=300.0, height=100.0)
    doc.layers = [Layer(name='A', items=[Shape(path=geom.Path(list(s))) for s in shapes])]
    setup = M.setup_of(doc)
    t = M.CamTool(name='c', kind='conique', diameter=6.0, tip=0.2, angle=30.0)
    setup.tools.append(t)
    args = dict(kind='vcarve', tool_id=t.id, depth=0.35, step_down=9.0, resolution=0.1, stepover_mm=0.2, vcarve_walls=False)
    args.update(kw)
    op = M.Operation(**args)
    setup.operations.append(op)
    M.store(doc, setup)
    return S.compute(doc, setup, op, (0.0, 0.0))


def cuts(tp):
    out, prev = [], None
    for m in tp.moves:
        if prev is not None and m.kind != 'rapid':
            out.append((prev, m))
        prev = m
    return out


def long_diagonals(tp, n=5.0):
    return [(a, b) for a, b in cuts(tp) if a.z < -0.3 and b.z < -0.3 and math.dist((a.x, a.y), (b.x, b.y)) > n and
            abs(a.x - b.x) > 1e-3 and abs(a.y - b.y) > 1e-3]


class Anneaux(unittest.TestCase):
    def setUp(self):
        self.reg = Polygon(box(0, 0, 40, 40).exterior, [box(10, 10, 30, 30).exterior.coords])
        self.geoms = [self.reg.buffer(-0.5 * k) for k in range(1, 14)]        # au-delà de 5 : les quatre coins seuls

    def test_chaque_polygone_apres_ceux_qu_il_contient(self):
        g = S.nested_rings(self.reg, self.geoms, True, here=(0.0, 0.0))
        self.assertEqual(len(g), 1)
        ks = [k for k, _r in g[0]]
        self.assertEqual(ks[-1], 0)                                     # le bord en dernier
        self.assertEqual(ks[0], max(ks))                                # le centre d'abord
        for i, (k, rings) in enumerate(g[0]):                           # plus aucune passe plus profonde dans le même polygone ensuite
            poly = Polygon(rings[0])
            for k2, rings2 in g[0][i + 1:]:
                if k2 > k:
                    self.assertFalse(poly.contains(Polygon(rings2[0]).representative_point()))

    def test_rien_de_perdu(self):
        g = S.nested_rings(self.reg, self.geoms, True, here=(0.0, 0.0))
        a = sorted(len(r) for _k, rings in g[0] for r in rings)
        b = sorted(len(r) for _k, rings in S.part_rings(self.reg, self.geoms, True)[0] for r in rings)
        self.assertEqual(a, b)

    def test_le_cote_de_depart_est_le_plus_proche(self):
        g = S.nested_rings(self.reg, self.geoms, True, here=(40.0, 40.0))
        first = Polygon(g[0][0][1][0]).centroid
        self.assertGreater(first.x, 20)
        self.assertGreater(first.y, 20)

    def test_une_valeur_par_passe(self):
        keep = S.frames_of(self.reg)
        each = [keep] + [True] * (len(self.geoms) - 1)
        g = S.nested_rings(self.reg, self.geoms, True, exteriors=each, here=(0.0, 0.0))
        self.assertEqual(g[0][-1][0], 0)
        self.assertEqual(len(g[0][-1][1]), 1)                           # le trou seul

    def test_plusieurs_parties(self):
        reg = box(0, 0, 10, 10).union(box(20, 0, 30, 10))
        geoms = [reg.buffer(-1), reg.buffer(-2)]
        g = S.nested_rings(reg, geoms, True, here=(0.0, 0.0))
        self.assertEqual(len(g), 2)
        self.assertEqual([k for k, _r in g[0]], [1, 0])
        self.assertEqual([k for k, _r in g[1]], [1, 0])

    def test_vide(self):
        self.assertEqual(S.nested_rings(box(0, 0, 1, 1), [], True), [])


class Parcours(unittest.TestCase):
    def test_plus_court_et_sans_longs_trajets_d_un_coin_a_l_autre(self):
        new = path_of([FRAME])
        old = path_of([FRAME], gravure_rule=878)
        self.assertLess(new.lengths()[0], old.lengths()[0] * 0.97)
        self.assertLessEqual(len(long_diagonals(new, 15.0)), 3)          # 4 coins, une fois chacun
        self.assertGreater(len(long_diagonals(old, 15.0)), 12)

    def test_tout_le_fond_reste_grave(self):
        new = path_of([FRAME])
        old = path_of([FRAME], gravure_rule=878)
        depth = {round(m.x, 2) for m in new.moves if m.kind != 'rapid' and m.z < -0.3}
        before = {round(m.x, 2) for m in old.moves if m.kind != 'rapid' and m.z < -0.3}
        self.assertTrue(before <= depth | {round(v + d, 2) for v in depth for d in (-0.01, 0.01)})

    def test_une_operation_d_avant_garde_son_ordre(self):
        d = M.Operation(kind='vcarve').to_dict()
        self.assertGreaterEqual(M.Operation.from_dict(d).gravure_rule, 879)
        del d['gravure_rule']
        self.assertEqual(M.Operation.from_dict(d).gravure_rule, 0)

    def test_en_partant_de_l_exterieur_inchange(self):
        a = path_of([FRAME], pocket_outside_in=True)
        b = path_of([FRAME], pocket_outside_in=True, gravure_rule=878)
        self.assertEqual(len(a.moves), len(b.moves))

    def test_avec_le_cadre_ignore(self):
        tp = path_of([FRAME], finish_skip_frame=True)
        self.assertAlmostEqual(min(m.x for m in tp.moves if m.kind != 'rapid' and m.z < -0.3), 10.394, places=2)

    def test_les_formes_separees_une_a_une(self):
        tp = path_of([ISLAND, FRAME])
        seq = []
        for m in tp.moves:
            if m.kind != 'rapid' and m.z < -0.3:
                w = 0 if m.x < 70 else 1
                if not seq or seq[-1] != w:
                    seq.append(w)
        self.assertEqual(seq, [0, 1])

    def test_les_liaisons_restent_dans_la_zone(self):
        # aucune liaison au fond ne touche la paroi (le cône à la profondeur finale tient à 0,194 du bord)
        reg = Polygon(box(10, 10, 60, 60).exterior, [box(20, 20, 50, 50).exterior.coords])
        tp = path_of([FRAME])
        d = 0.1 + 0.35 * math.tan(math.radians(15))
        from shapely.geometry import Point
        for a, b in cuts(tp):
            if a.z < -0.3 and b.z < -0.3:
                self.assertGreater(reg.boundary.distance(Point(b.x, b.y)), d - 0.01)


if __name__ == '__main__':
    unittest.main()
