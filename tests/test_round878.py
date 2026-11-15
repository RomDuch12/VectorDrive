"""Round 878 : Gravure 3D relevée dans TE13 (cadre ignoré, profondeur au-delà du corps de l'outil) ; Finition sur un gros dessin."""
import math
import unittest

from vectordrive.cam import finish as F
from vectordrive.cam import model as M
from vectordrive.cam import strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape


def P(*pts):
    return geom.polyline(list(pts), closed=True)


FRAME = [P((10, 10), (60, 10), (60, 60), (10, 60)), P((20, 20), (50, 20), (50, 50), (20, 50))]
ISLAND = [P((30, 30), (40, 30), (40, 40), (30, 40))]
U = [P((110, 10), (170, 10), (170, 50), (155, 50), (155, 25), (125, 25), (125, 50), (110, 50))]
T = [P((10, 10), (50, 10), (50, 20), (35, 20), (35, 40), (25, 40), (25, 20), (10, 20))]
TRI = [P((70, 15), (90, 15), (80, 40))]


def drawing(*shapes):
    doc = Document()
    doc.plate = Plate(width=300.0, height=100.0)
    doc.layers = [Layer(name='A', items=[Shape(path=geom.Path(list(s))) for s in shapes])]
    return doc


def path_of(shapes, *, tool=None, **kw):
    doc = drawing(*shapes)
    setup = M.setup_of(doc)
    t = M.CamTool(name='c', kind='conique', diameter=6.0, tip=0.2, angle=30.0)
    for k, v in (tool or {}).items():
        setattr(t, k, v)
    setup.tools.append(t)
    args = dict(kind='vcarve', tool_id=t.id, depth=0.35, step_down=9.0, resolution=0.1, stepover_mm=0.5, vcarve_walls=False)
    args.update(kw)
    op = M.Operation(**args)
    setup.operations.append(op)
    M.store(doc, setup)
    return S.compute(doc, setup, op, (0.0, 0.0))


def deep(tp):
    return [m for m in tp.moves if m.kind != 'rapid' and m.z < -0.3]


def xs(tp, lo, hi):
    return sorted({round(m.x, 3) for m in deep(tp) if lo <= m.x <= hi})


class CadreIgnore(unittest.TestCase):
    def test_le_fond_va_jusqu_au_cadre(self):
        tp = path_of([FRAME], finish_skip_frame=True)
        # relevé dans TE13 : le retrait du fond commence au pas suivant (0,194 + le pas), la passe au pied du bord (0,194) saute
        self.assertAlmostEqual(xs(tp, 0, 15)[0], 10.694, places=2)
        self.assertTrue(any('sans la passe le long de son bord' in w for w in tp.warnings))

    def test_sans_l_option_la_passe_du_bord(self):
        tp = path_of([FRAME])
        self.assertAlmostEqual(xs(tp, 0, 15)[0], 10.194, places=2)
        self.assertFalse(any('cadre englobant' in w for w in tp.warnings))

    def test_le_trou_garde_sa_passe(self):
        tp = path_of([FRAME], finish_skip_frame=True)
        self.assertIn(19.806, xs(tp, 19, 20))

    def test_pas_de_tire_d_angle_sur_le_cadre(self):
        high = [m for m in path_of([FRAME], finish_skip_frame=True).moves if m.kind != 'rapid' and abs(m.z) < 1e-6]
        self.assertFalse([m for m in high if m.x < 10.2 and m.y < 10.2])
        high = [m for m in path_of([FRAME]).moves if m.kind != 'rapid' and abs(m.z) < 1e-6]
        self.assertTrue([m for m in high if m.x < 10.2 and m.y < 10.2])

    def test_une_ile_dans_le_cadre_n_est_pas_un_cadre(self):
        tp = path_of([FRAME, ISLAND], finish_skip_frame=True)
        self.assertIn(30.194, xs(tp, 30, 30.3))

    def test_une_forme_sans_trou_n_est_pas_un_cadre(self):
        # relevé dans TE13 : à la différence de la Finition, la forme sans trou garde tout
        a = path_of([T, TRI], finish_skip_frame=True)
        b = path_of([T, TRI])
        self.assertEqual(len(a.moves), len(b.moves))
        self.assertAlmostEqual(a.lengths()[0], b.lengths()[0], places=6)

    def test_seule_la_forme_percee_perd_sa_passe(self):
        tp = path_of([U, FRAME], finish_skip_frame=True)
        self.assertAlmostEqual(xs(tp, 100, 115)[0], 110.194, places=2)     # U : gardée
        self.assertAlmostEqual(xs(tp, 0, 15)[0], 10.694, places=2)         # le cadre : sans sa passe

    def test_une_operation_enregistree_garde_son_parcours(self):
        d = M.Operation(kind='vcarve', finish_skip_frame=True).to_dict()
        self.assertGreaterEqual(M.Operation.from_dict(d).gravure_rule, 878)
        del d['gravure_rule']
        self.assertEqual(M.Operation.from_dict(d).gravure_rule, 0)
        tp = path_of([FRAME], finish_skip_frame=True, gravure_rule=0)
        self.assertGreater(xs(tp, 0, 30)[0], 14.0)                         # l'ancienne règle : la moitié de la bande

    def test_part_rings_une_valeur_par_passe(self):
        from shapely.geometry import Polygon, box
        reg = Polygon(box(0, 0, 40, 40).exterior, [box(10, 10, 30, 30).exterior.coords])
        keep = S.frames_of(reg)
        a = reg.buffer(-1)
        b = reg.buffer(-2)
        got = S.part_rings(reg, [a, b], True, exteriors=[keep, True])
        self.assertEqual(len(got[0][0][1]), 1)                             # le trou seul
        self.assertEqual(len(got[0][1][1]), 2)


class Lie(unittest.TestCase):
    def test_lie_au_parcours_precedent(self):
        from vectordrive.cam import strategies
        doc = drawing([P((-10, -7), (10, -7), (10, 7), (-10, 7)), P((-5, -3), (5, -3), (5, 3), (-5, 3))])
        setup = M.setup_of(doc)
        cyl = M.CamTool(name='Cyl 5', diameter=5.0, number=1, cut_length=7, step_down=1.0)    # trop large pour la bande
        cone = M.CamTool(name='V', kind='conique', diameter=6.0, tip=0.2, angle=30.0, number=2, cut_length=15)
        setup.tools += [cyl, cone]
        pocket = M.Operation(name='a', kind='poche', tool_id=cyl.id, depth=1.0, step_down=1.0)
        carve = M.Operation(name='b', kind='vcarve', tool_id=cone.id, depth=1.0, finish_skip_frame=True, link_previous=True)
        setup.operations += [pocket, carve]
        M.store(doc, setup)
        tp = strategies.compute_all(doc, setup)[1]
        self.assertTrue(tp.moves)
        # le bord du cadre n'est pas repassé : aucune passe au pied du bord (0,368 du cadre), à fond
        foot = 0.1 + 1.0 * math.tan(math.radians(15))
        self.assertFalse([m for m in tp.moves if m.kind != 'rapid' and m.z < -0.9 and abs(abs(m.y) - (7 - foot)) < 0.01 and abs(m.x) < 5])


class Profondeur(unittest.TestCase):
    TOOL = dict(diameter=6.0, tip=0.1, angle=90.0)

    def test_la_profondeur_demandee_comme_te13(self):
        tp = path_of([T], tool=self.TOOL, depth=3.5, stepover_mm=1.0)
        self.assertAlmostEqual(min(m.z for m in tp.moves), -3.5, places=6)
        self.assertTrue(any('retrait de 0.550 mm' in w for w in tp.warnings), tp.warnings)

    def test_le_premier_retrait_reste_celui_du_cone(self):
        tp = path_of([[P((0, 0), (40, 0), (40, 40), (0, 40))]], tool=self.TOOL, depth=3.5, stepover_mm=1.0)
        self.assertAlmostEqual(min(m.x for m in tp.moves if m.z < -3.4), 3.55, places=2)

    def test_l_ancienne_regle_limite_encore(self):
        tp = path_of([T], tool=self.TOOL, depth=3.5, stepover_mm=1.0, gravure_rule=0)
        self.assertAlmostEqual(min(m.z for m in tp.moves), -2.95, places=6)
        self.assertTrue(any('profondeur limitée' in w for w in tp.warnings))

    def test_sans_probleme_pas_d_avertissement(self):
        tp = path_of([T], depth=0.35)
        self.assertFalse(any('retrait' in w for w in tp.warnings))


class GrosDessin(unittest.TestCase):
    def test_l_index_des_parois(self):
        import shapely
        from shapely.geometry import MultiPolygon, box
        reg = MultiPolygon([box(0, 0, 10, 10), box(20, 0, 30, 10)])
        tree = F._walls_index(reg)
        d = tree.query_nearest(shapely.points(15.0, 5.0), return_distance=True, all_matches=False)[1][0]
        self.assertAlmostEqual(d, 5.0, places=9)

    def test_un_axe_par_forme_et_rien_de_perdu(self):
        # beaucoup de petites formes : chaque trait fin garde son axe
        bars = [[P((i * 3.0, 0), (i * 3.0 + 0.5, 0), (i * 3.0 + 0.5, 10), (i * 3.0, 10))] for i in range(40)]
        doc = drawing(*bars)
        setup = M.setup_of(doc)
        t = M.CamTool(name='c', kind='conique', diameter=4.0, tip=0.2, angle=30.0)
        setup.tools.append(t)
        op = M.Operation(kind='vcarve', tool_id=t.id, depth=1.5, step_down=1.5, vcarve_edges_only=True, vcarve_step=1.5, ramp=False, resolution=0.1)
        setup.operations.append(op)
        M.store(doc, setup)
        tp = S.compute(doc, setup, op, (0.0, 0.0))
        for i in range(40):
            self.assertTrue([m for m in tp.moves if m.kind != 'rapid' and m.z < -0.1 and abs(m.x - (i * 3.0 + 0.25)) < 0.02], i)

    def test_une_forme_a_nombreux_trous(self):
        import shapely
        from shapely.geometry import Polygon, box
        holes = [box(5 + 6 * i, 5, 8 + 6 * i, 12).exterior.coords for i in range(20)]
        plate = Polygon(box(0, 0, 130, 20).exterior, holes)
        self.assertGreaterEqual(len(plate.interiors), S.HOLES_SPLIT)
        chains = F._axis_chains(plate, 2.5, 0.1, math.tan(math.radians(15)), 8.0, 0.1, 8, [])
        self.assertTrue(chains)                                    # les ponts de 3 mm entre les trous n'ont pas la place de l'anneau
        self.assertTrue(all(0 < p[1] < 20 for c in chains for p in c))

    def test_une_forme_seule_comme_avant(self):
        from shapely.geometry import box
        chains = F._axis_chains(box(0, 0, 0.5, 10), 0.5, 0.1, math.tan(math.radians(15)), 1.5, 0.1, 8, [])
        self.assertTrue(chains)
        self.assertGreater(sum(1 for c in chains for p in c if abs(p[0] - 0.25) < 0.01), 20)   # l'axe du trait, sans compter les fourches des bouts


if __name__ == '__main__':
    unittest.main()
