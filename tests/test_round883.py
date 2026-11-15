"""Round 883 : un décalage ne garde pas l'anneau retourné d'une forme qui aurait dû disparaître."""
import math
import unittest
from unittest import mock

import numpy as np
import shapely
from shapely.geometry import MultiPolygon, Polygon, box

from vectordrive.cam import finish as F
from vectordrive.cam import model as M
from vectordrive.cam import strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape

#: une forme inventée à 12 sommets, rayon inscrit 1,70 : à 2 mm, GEOS 3.13 rend un anneau retourné
STAR = [(2.048, 0.0), (1.469, 0.848), (0.992, 1.717), (0.0, 2.048), (-0.848, 1.469), (-1.717, 0.992),
        (-2.048, 0.0), (-1.469, -0.848), (-0.992, -1.717), (0.0, -2.048), (0.848, -1.469), (1.717, -0.992)]


def walls_distance(reg, pts):
    return min(r.distance(shapely.Point(pts)) for r in shapely.get_rings(shapely.get_parts(reg)))


def drawing(*shapes):
    doc = Document()
    layer = Layer(name='Plan 1', items=[Shape(path=geom.Path([p])) for p in shapes])
    doc.layers[:] = [layer]
    doc.active = layer.id
    doc.plate = Plate(width=300, height=200)
    return doc


class Retrait(unittest.TestCase):

    def test_l_anneau_retourne_disparait(self):
        p = Polygon(STAR)
        self.assertTrue(S.erode(p, 2.0, 8).is_empty)
        self.assertTrue(S.erode(p, 2.5, 8).is_empty)

    def test_un_retrait_possible_reste_exact(self):
        p = Polygon(STAR)
        for d in (0.3, 1.0, 1.5):
            self.assertAlmostEqual(S.erode(p, d, 8).area, p.buffer(-d, quad_segs=8).area, places=9)

    def test_l_anneau_retourne_d_une_partie_parmi_d_autres(self):
        p = Polygon(STAR)
        big = box(20, 0, 60, 40)
        reg = MultiPolygon([p, big])
        out = S.erode(reg, 2.0, 8)
        self.assertEqual(len(shapely.get_parts(out)), 1)
        self.assertAlmostEqual(out.area, 36.0 * 36.0, places=6)

    def test_avec_de_nombreuses_parties(self):
        shapes = [Polygon([(x + 30 * i, y) for x, y in STAR]) for i in range(40)] + [box(0, 20, 40, 60)]
        out = S.erode(MultiPolygon(shapes), 2.0, 8)
        self.assertEqual(len(shapely.get_parts(out)), 1)

    def test_une_toute_petite_partie_vraie_reste(self):
        reg = box(0, 0, 10, 10)
        out = S.erode(reg, 4.99, 8)
        self.assertFalse(out.is_empty)
        self.assertAlmostEqual(out.area, 0.02 ** 2, places=9)

    def test_un_cercle_presque_entierement_retire_reste(self):
        c = shapely.Point(0, 0).buffer(5.0, quad_segs=32)
        out = S.erode(c, 4.98, 8)
        self.assertFalse(out.is_empty)

    def test_un_grand_retrait_garde_les_arcs(self):
        # autour d'un trou, les sommets de la réunion des disques sont sur des cordes : plus près que le retrait, de la flèche
        holes = [[(x, y), (x + 1, y), (x + 1, y + 1), (x, y + 1)] for x in range(10, 90, 8) for y in (20, 40, 60)]
        reg = Polygon([(0, 0), (100, 0), (100, 80), (0, 80)], holes)
        out = S.erode(reg, 5.0, 3)
        self.assertAlmostEqual(out.area, reg.buffer(-5.0, quad_segs=3).area, delta=1e-6)

    def test_un_seul_sommet_trop_pres_ne_suffit_pas(self):
        reg = box(0, 0, 40, 40)
        fake = Polygon([(0.2, 20), (5, 15), (35, 15), (35, 25), (5, 25)])  # le 1er sommet est trop près, pas les autres
        self.assertTrue(S.drop_splinters(fake, reg, -3.0, 8).equals(fake))

    def test_un_anneau_trop_pres_est_retire(self):
        reg = box(0, 0, 40, 40)
        fake = MultiPolygon([box(3, 3, 37, 37), Polygon([(0.2, 20), (0.3, 20), (0.3, 20.1)])])
        out = S.drop_splinters(fake, reg, -3.0, 8)
        self.assertAlmostEqual(out.area, 34.0 ** 2, places=6)

    def test_la_distance_par_troncons_est_exacte(self):
        pts = [(50 * math.cos(2 * math.pi * k / 500), 50 * math.sin(2 * math.pi * k / 500)) for k in range(500)]
        inner = [(5 * math.cos(2 * math.pi * k / 33) + 3, 5 * math.sin(2 * math.pi * k / 33)) for k in range(33)]
        reg = Polygon(pts, [inner])
        tree = S._wall_tree(reg)
        q = shapely.points(np.array([[0.0, 30.0], [20.0, -7.0], [8.0, 0.0], [-40.0, 10.0], [3.0, 5.5]]))
        at, dd = tree.query_nearest(q, return_distance=True, all_matches=False)
        self.assertEqual(at[0].tolist(), [0, 1, 2, 3, 4])
        for k, v in enumerate(dd):
            self.assertAlmostEqual(v, reg.boundary.distance(q[k]), places=9)

    def test_sans_paroi_rien_ne_change(self):
        self.assertIsNone(S._wall_tree(Polygon()))
        res = box(0, 0, 1, 1)
        self.assertIs(S.drop_splinters(res, Polygon(), -1.0), res)
        self.assertIs(S.drop_splinters(res, box(0, 0, 3, 3), 0.0), res)
        self.assertTrue(S.drop_splinters(Polygon(), box(0, 0, 3, 3), -1.0).is_empty)


class Agrandissement(unittest.TestCase):

    def test_un_trou_retourne_disparait(self):
        reg = Polygon([(-30, -30), (30, -30), (30, 30), (-30, 30)], [STAR])
        g = reg.buffer(2.0, quad_segs=8)
        out = S.drop_splinters(g, reg, 2.0, 8)
        self.assertEqual(len(out.interiors), 0)
        self.assertTrue(S.erode(reg, -2.0, 8).equals(out))

    def test_un_trou_vrai_reste(self):
        reg = Polygon([(-30, -30), (30, -30), (30, 30), (-30, 30)], [[(-5, -5), (5, -5), (5, 5), (-5, 5)]])
        g = reg.buffer(4.99, quad_segs=8)
        self.assertEqual(len(g.interiors), 1)
        self.assertEqual(len(S.drop_splinters(g, reg, 4.99, 8).interiors), 1)

    def test_seul_le_trou_faux_part(self):
        hole = [(-5, -5), (5, -5), (5, 5), (-5, 5)]
        reg = box(-40, -40, 40, 40)
        grown = Polygon(reg.buffer(1.0, join_style='mitre').exterior, [hole, [(39.8, 0), (39.9, 0), (39.9, 0.1)]])
        out = S.drop_splinters(grown, Polygon(reg.exterior, [hole]).buffer(0), 1.0, 8)
        self.assertLessEqual(len(out.interiors), 1)
        self.assertFalse(any(max(c[0] for c in r.coords) > 39 for r in out.interiors))


def star_path(dx=0.0, dy=0.0):
    return geom.polyline([(x + dx, y + dy) for x, y in STAR], closed=True)


class Parcours(unittest.TestCase):

    def test_la_finition_ne_descend_pas_dans_la_paroi(self):
        doc = drawing(star_path(30, 30))
        t = M.CamTool(name='c', kind='conique', diameter=8.0, tip=0.2, angle=60.0)
        setup = M.CamSetup(tools=[t])
        depth = 3.3
        op = M.Operation(kind='vcarve', tool_id=t.id, depth=depth, step_down=depth, climb=True, vcarve_edges_only=True, vcarve_step=depth)
        setup.operations = [op]
        tp = S.compute(doc, setup, op, (0.0, 0.0))
        tan_h = math.tan(math.radians(30))
        reg = S.region([S.item_geometry(doc.layers[0].items[0])], setup.tolerance)
        over = [t.tip / 2 - m.z * tan_h - walls_distance(reg, (m.x, m.y)) for m in tp.moves if m.kind != 'rapid' and m.z < -1e-6]
        self.assertTrue(over)
        self.assertLess(max(over), 0.02)

    def test_la_decoupe_interieure_ne_garde_pas_l_anneau(self):
        doc = drawing(star_path(30, 30))
        t = M.CamTool(name='f', kind='fraise', diameter=4.0)
        setup = M.CamSetup(tools=[t])
        op = M.Operation(kind='contour', tool_id=t.id, depth=1.0, step_down=1.0, side='interieur')
        setup.operations = [op]
        tp = S.compute(doc, setup, op, (0.0, 0.0))
        self.assertFalse([m for m in tp.moves if m.kind != 'rapid'])

    def test_la_poche_ne_garde_pas_l_anneau(self):
        doc = drawing(star_path(30, 30))
        t = M.CamTool(name='f', kind='fraise', diameter=4.0)
        setup = M.CamSetup(tools=[t])
        op = M.Operation(kind='poche', tool_id=t.id, depth=1.0, step_down=1.0)
        setup.operations = [op]
        tp = S.compute(doc, setup, op, (0.0, 0.0))
        self.assertFalse([m for m in tp.moves if m.kind != 'rapid'])

    def test_les_lettres_prismatiques_non_plus(self):
        doc = drawing(star_path(30, 30))
        t = M.CamTool(name='c', kind='conique', diameter=6.0, tip=0.2, angle=30.0)
        setup = M.CamSetup(tools=[t])
        # un retrait de 2 mm, au-delà du rayon inscrit, aux niveaux hauts du relief
        op = M.Operation(kind='prismatique', tool_id=t.id, depth=7.5, step_down=7.5, climb=True)
        setup.operations = [op]
        tp = S.compute(doc, setup, op, (0.0, 0.0))
        tan_h = math.tan(math.radians(15))
        reg = S.region([S.item_geometry(doc.layers[0].items[0])], setup.tolerance)
        for m in tp.moves:
            if m.kind != 'rapid' and -7.4 < m.z < -1e-6:
                self.assertTrue(reg.buffer(1e-3).contains(shapely.Point(m.x, m.y)))


class Entree(unittest.TestCase):

    def run_entry(self, length):
        em = S.Emitter(M.Operation(kind='vcarve', depth=1.0), M.CamTool(name='c', kind='conique', diameter=4.0, tip=0.2, angle=30.0))
        em.pos = (0.0, 0.0, 0.0)
        path = [(0.0, 0.0, -1.0), (length, 0.0, -1.0), (length, length, -1.0), (0.0, 0.0, -1.0)]
        F._v_entry(em, path, 1.0, 15.0)
        return em.moves

    def test_sur_quelques_microns_pas_d_allers_retours(self):
        self.assertEqual(self.run_entry(0.001), [])

    def test_sur_un_vrai_chemin_la_pente_reste(self):
        moves = self.run_entry(1.0)
        self.assertGreater(len(moves), 2)
        self.assertLess(len(moves), 40)


class Appels(unittest.TestCase):

    def test_le_retrait_passe_par_le_controle(self):
        with mock.patch.object(S, 'drop_splinters', wraps=S.drop_splinters) as m:
            S.erode(box(0, 0, 10, 10), 1.0, 8)
        self.assertEqual(m.call_count, 1)
        self.assertLess(m.call_args.args[2], 0)

    def test_la_decoupe_exterieure_passe_par_le_controle(self):
        doc = drawing(geom.polyline([(10, 10), (40, 10), (40, 40), (10, 40)], closed=True))
        t = M.CamTool(name='f', kind='fraise', diameter=4.0)
        setup = M.CamSetup(tools=[t])
        op = M.Operation(kind='contour', tool_id=t.id, depth=1.0, step_down=1.0, side='exterieur')
        setup.operations = [op]
        with mock.patch.object(S, 'drop_splinters', wraps=S.drop_splinters) as m:
            S.compute(doc, setup, op, (0.0, 0.0))
        self.assertTrue(any(c.args[2] > 0 for c in m.call_args_list))


if __name__ == '__main__':
    unittest.main()
