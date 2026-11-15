"""Round 877 : la Finition relevée dans TE13. Un trajet par contour : l'anneau décalé, les tirés d'angle jusqu'au sommet, l'axe des parties
étroites. Les valeurs attendues sont celles que TE13 a calculées sur ces mêmes dessins, avec un cône Ø4 à 30°, pointe 0,2."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.cam import finish as F
from vectordrive.cam import model as M
from vectordrive.cam import strategies as S
from vectordrive.cam import tpp
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape


def P(*pts):
    return geom.polyline(list(pts), closed=True)


U = P((10, 10), (70, 10), (70, 50), (55, 50), (55, 25), (25, 25), (25, 50), (10, 50))
SQUARE = [P((90, 10), (130, 10), (130, 50), (90, 50)), P((105, 25), (105, 35), (115, 35), (115, 25))]
FRAME = [P((10, 10), (60, 10), (60, 60), (10, 60)), P((20, 20), (50, 20), (50, 50), (20, 50)),
         P((30, 30), (40, 30), (40, 40), (30, 40)), P((33, 33), (37, 33), (37, 37), (33, 37))]
STEMS = P((70, 10), (100, 10), (100, 20), (95.4, 20), (95.4, 50), (94.6, 50), (94.6, 20),
          (75.25, 20), (75.25, 50), (74.75, 50), (74.75, 20), (70, 20))
BAR = P((10, 10), (10.5, 10), (10.5, 40), (10, 40))
NECK = P((90, 10), (110, 10), (110, 19.7), (120, 19.7), (120, 10), (140, 10), (140, 30), (120, 30), (120, 20.3), (110, 20.3), (110, 30), (90, 30))
THIN_RING = [P((50, 10), (80, 10), (80, 40), (50, 40)), P((50.5, 10.5), (50.5, 39.5), (79.5, 39.5), (79.5, 10.5))]
OBTUSE = P((150, 10), (170, 10), (178.66, 15), (178.66, 35), (150, 35))


def drawing(*shapes):
    doc = Document()
    doc.plate = Plate(width=240.0, height=70.0)
    items = [Shape(path=geom.Path(s if isinstance(s, list) else [s])) for s in shapes]
    doc.layers = [Layer(name='A', items=items)]
    return doc


def path_of(shapes, nb=2, depth=1.5, **kw):
    doc = drawing(*shapes)
    setup = M.setup_of(doc)
    tool = M.CamTool(name='c', kind='conique', diameter=4.0, tip=0.2, angle=30.0)
    setup.tools.append(tool)
    opts = dict(ramp=True, ramp_angle=15.0, pass_order='global', start_policy='dessin', climb=True)
    opts.update(kw)
    op = M.Operation(kind='vcarve', tool_id=tool.id, depth=depth, step_down=depth / nb, vcarve_edges_only=True, vcarve_step=depth / nb, **opts)
    setup.operations.append(op)
    M.store(doc, setup)
    return S.compute(doc, setup, op, (0.0, 0.0))


def chains(tp):
    """Les chaînes de coupe, sans la descente rapide : [(x, y, z)…]."""
    out, cur = [], None
    for m in tp.moves:
        if m.kind == 'rapid':
            if cur and len(cur) > 1:
                out.append(cur)
            cur = [(m.x, m.y, m.z)]
        elif cur is not None:
            cur.append((m.x, m.y, m.z))
    if cur and len(cur) > 1:
        out.append(cur)
    return out


def length(c):
    return sum(math.dist(a, b) for a, b in zip(c, c[1:]))


def rounded(c, n=3):
    return [tuple(round(v, n) for v in p) for p in c]


class Trajet(unittest.TestCase):
    def test_un_trajet_avec_les_tires_dans_le_contour(self):
        c = chains(path_of([U, SQUARE]))[0]
        want = [(10.0, 10.0, 1.123), (10.301, 10.301, -0.114), (11.275, 10.301, -0.375), (10.301, 10.301, -0.636), (10.0, 10.0, 0.373),
                (10.301, 10.301, -0.75), (69.699, 10.301, -0.75), (70.0, 10.0, 0.373), (69.699, 10.301, -0.75), (69.699, 49.699, -0.75),
                (70.0, 50.0, 0.373), (69.699, 49.699, -0.75), (55.301, 49.699, -0.75), (55.0, 50.0, 0.373), (55.301, 49.699, -0.75), (55.301, 25.0, -0.75)]
        self.assertEqual(rounded(c[:len(want)]), want)
        self.assertEqual(rounded(c[-1:]), [(10.0, 10.0, 0.373)])     # et il finit au sommet du départ

    def test_les_formes_et_les_passes(self):
        tp = path_of([U, SQUARE])
        c = chains(tp)
        self.assertEqual(len(c), 6)                                  # U, trou, carré, deux fois
        self.assertEqual([rounded(x[:1], 3)[0][:2] for x in c[:3]], [(10.0, 10.0), (104.699, 25.0), (90.0, 10.0)])
        self.assertEqual(rounded(c[3][:2]), [(10.0, 10.0, 1.123), (10.502, 10.502, -0.94)])
        self.assertAlmostEqual(tp.lengths()[0], 981.1, delta=2.0)    # TE13 ; VD descend en plus de la hauteur d'approche
        self.assertEqual(round(min(m.z for m in tp.moves), 3), -1.5)

    def test_une_passe(self):
        c = chains(path_of([U, SQUARE], nb=1))[0]
        self.assertEqual(rounded(c[:4]), [(10.0, 10.0, 1.873), (10.502, 10.502, -0.19), (12.591, 10.502, -0.75), (10.502, 10.502, -1.31)])

    def test_le_trou_sans_tire_part_apres_l_arrondi(self):
        c = chains(path_of([SQUARE], nb=1, depth=0.75))[1]            # seul, le carré passe d'abord, puis son trou
        self.assertEqual(rounded(c[1:4]), [(104.699, 25.0, 0.0), (104.699, 26.4, -0.375), (104.699, 25.0, -0.75)])

    def test_en_opposition(self):
        c = chains(path_of([SQUARE], nb=1, depth=0.75, climb=False))
        self.assertEqual(rounded(c[1][1:4]), [(105.0, 24.699, 0.0), (106.4, 24.699, -0.375), (105.0, 24.699, -0.75)])
        self.assertEqual(rounded(c[0][1:3]), [(90.301, 10.301, -0.114), (90.301, 11.275, -0.375)])

    def test_surepaisseur_les_arrondis_restent_centres_sur_le_dessin(self):
        c = chains(path_of([SQUARE], nb=1, depth=0.75, stock=0.1))
        self.assertEqual(rounded(c[1][1:2]), [(104.599, 25.0, 0.0)])
        top = [p for p in c[1] if abs(p[1] - 35.401) < 1e-3]
        self.assertTrue(top)                                         # l'arrondi : 0,301 + 0,1 autour de (105, 35)
        self.assertEqual(rounded(c[0][:2]), [(90.1, 10.1, 1.123), (90.401, 10.401, -0.114)])

    def test_sans_plongee_jusqu_a_la_surface(self):
        c = chains(path_of([U], nb=1, depth=0.75, ramp=False))[0]
        self.assertEqual(rounded(c[:4]), [(10.1, 10.1, 0.5), (10.1, 10.1, 0.0), (10.301, 10.301, -0.75), (69.699, 10.301, -0.75)])
        self.assertLessEqual(max(p[2] for p in c[1:]), 0.0)
        self.assertEqual(rounded(c[4:5]), [(69.9, 10.1, 0.0)])

    def test_angle_de_plongee(self):
        c = chains(path_of([U], nb=1, depth=0.75, ramp_angle=30.0))[0]
        h = 0.75 / math.tan(math.radians(30)) / 2
        self.assertAlmostEqual(c[2][0], 10.0 + 0.301 + h - 0.301 * math.sqrt(2), delta=2e-3)

    def test_un_angle_ouvert_n_a_pas_de_tire(self):
        c = rounded(chains(path_of([OBTUSE], nb=1, depth=0.75))[0])
        self.assertNotIn((170.0, 10.0, 0.373), c)
        self.assertIn((178.66, 15.0, 0.373), c)

    def test_angle_aigu(self):
        c = rounded(chains(path_of([P((110, 10), (140, 10), (125, 50))], nb=1, depth=0.75))[0])
        self.assertIn((125.0, 50.0, 0.373), c)
        self.assertIn((125.0, 49.143, -0.75), c)


class PartiesEtroites(unittest.TestCase):
    def test_branche_etroite_a_l_axe_et_retour(self):
        tp = path_of([STEMS])
        c = chains(tp)
        self.assertEqual(len(c), 2)                                  # le tout en un trajet, une fois par passe
        r = rounded(c[0])
        i = r.index((75.25, 50.0, 0.373))                            # l'axe de 0,5 de large : à 0,56 ; le premier tiré de la paroi de droite
        self.assertEqual(r[i - 1], (75.0, 49.75, -0.56))
        self.assertEqual(r[i + 1], (75.0, 49.75, -0.56))
        self.assertEqual(r[i + 2], (74.75, 50.0, 0.373))
        self.assertAlmostEqual(length(c[0]), 220.65, delta=0.4)      # TE13 : 220,15 ; VD descend en plus de 0,5
        self.assertAlmostEqual(length(c[1]), 229.75, delta=0.4)
        self.assertTrue(any(abs(p[0] - 95.0) < 2e-3 and abs(p[1] - 49.6) < 2e-3 and abs(p[2] + 1.12) < 2e-3 for p in c[1]))   # à la 2e passe, la branche de 0,8 passe à l'axe

    def test_forme_fine_une_seule_fois(self):
        c = chains(path_of([BAR]))
        self.assertEqual(len(c), 1)                                  # rien de plus bas à la 2e passe
        r = rounded(c[0])
        self.assertEqual(r[:3], [(10.0, 10.0, 1.123), (10.25, 10.25, 0.095), (10.5, 10.0, 0.934)])
        self.assertEqual(r[-1], (10.25, 10.25, -0.56))               # TE13 ne remonte pas à la fin, le pied est sur l'axe
        self.assertAlmostEqual(length(c[0]), 72.68, delta=0.05)

    def test_goulot_les_deux_parties_en_un_trajet(self):
        c = chains(path_of([NECK]))
        self.assertEqual(len(c), 2)
        self.assertAlmostEqual(length(c[0]), 199.35, delta=0.3)
        self.assertAlmostEqual(length(c[1]), 213.03, delta=0.3)

    def test_cadre_fin_un_trajet_par_contour(self):
        c = chains(path_of(THIN_RING))
        self.assertEqual(len(c), 2)                                  # le bord, puis le trou : l'un et l'autre sur l'axe
        self.assertEqual(rounded(c[1][:1], 2), [(50.25, 10.5, 0.5)])
        self.assertAlmostEqual(length(c[0]), 130.86, delta=0.2)      # le bord, avec ses tirés d'angle


class Cadre(unittest.TestCase):
    def test_sans_trou_il_ne_reste_rien(self):
        tp = path_of([U, P((110, 10), (140, 10), (125, 50))], finish_skip_frame=True)
        self.assertFalse(chains(tp))
        self.assertTrue(any('cadre' in w for w in tp.warnings))

    def test_le_trou_reste(self):
        c = chains(path_of([U, SQUARE], finish_skip_frame=True))
        self.assertEqual(len(c), 2)
        self.assertEqual(rounded(c[0][1:2]), [(104.699, 25.0, 0.0)])

    def test_tous_les_contours_interieurs_restent(self):
        c = chains(path_of([FRAME, STEMS], finish_skip_frame=True))
        self.assertEqual(len(c), 6)                                  # l'îlot, la poche et son îlot, à deux passes
        self.assertEqual([round(x[0][0], 1) for x in c[:3]], [19.7, 30.0, 32.7])


class Ordre(unittest.TestCase):
    def test_ordre_releve(self):
        c = chains(path_of([STEMS, FRAME, OBTUSE], nb=1, depth=0.75))
        self.assertEqual([round(x[0][0], 1) for x in c], [10.0, 19.7, 30.0, 32.7, 150.0, 70.0])

    def test_poche_par_poche(self):
        c = chains(path_of([U, SQUARE], pass_order='poche'))
        self.assertEqual([round(x[0][0], 1) for x in c], [10.0, 10.0, 104.7, 104.5, 90.0, 90.0])

    def test_poche_par_poche_dans_l_ordre_du_dessin(self):
        c = chains(path_of([STEMS, FRAME, OBTUSE], nb=1, depth=0.75, pass_order='poche', order_mode='dessin'))
        self.assertEqual([round(x[0][0], 1) for x in c], [10.0, 70.0, 150.0, 32.7, 30.0, 19.7])


class TroisDUniquement(unittest.TestCase):
    OUTIL = dict(nb=3, finish_3d_only=True, finish_skip_frame=True, stock=0.1)

    def path(self, shapes):
        doc = drawing(*shapes)
        setup = M.setup_of(doc)
        tool = M.CamTool(name='c', kind='conique', diameter=6.0, tip=0.6, angle=30.0)
        setup.tools.append(tool)
        op = M.Operation(kind='vcarve', tool_id=tool.id, depth=1.5, step_down=0.5, vcarve_edges_only=True, vcarve_step=0.5, ramp=True, ramp_angle=15.0,
                         pass_order='global', start_policy='dessin', climb=True, finish_3d_only=True, finish_skip_frame=True, stock=0.1)
        setup.operations.append(op)
        M.store(doc, setup)
        return S.compute(doc, setup, op, (0.0, 0.0))

    def test_rien_que_les_tires_d_angle(self):
        c = chains(self.path([FRAME]))
        self.assertEqual(len(c), 12)                                 # les 4 angles de la poche, 3 passes (TE13 refait le premier à chaque passe)
        self.assertEqual(rounded(c[0][1:8]), [(30.534, 30.534, 0.0), (30.1, 30.1, 1.455), (30.326, 30.326, 0.527), (30.1, 30.1, 1.284),
                                              (30.534, 30.534, -0.5), (30.1, 30.1, 1.12), (30.534, 30.534, -0.5)])
        self.assertEqual(rounded(c[1][1:2]), [(39.466, 30.534, 0.0)])

    def test_un_trou_sans_angle_saillant_ne_donne_rien(self):
        self.assertFalse(chains(self.path([U, SQUARE])))


class Robustesse(unittest.TestCase):
    def test_une_geometrie_refusee_par_geos_est_reparee(self):
        import shapely
        from shapely.geometry import box

        class Refuse:
            def __init__(self, g):
                self.g = g

            def difference(self, other):
                raise shapely.errors.GEOSException('side location conflict')

        a = box(0, 0, 4, 4)
        orig = shapely.make_valid
        calls = []

        def valid(g):
            calls.append(g)
            return orig(g.g if isinstance(g, Refuse) else g)
        shapely.make_valid = valid
        try:
            r = F._overlay('difference', Refuse(a), box(2, 0, 4, 4))
        finally:
            shapely.make_valid = orig
        self.assertEqual(len(calls), 2)
        self.assertAlmostEqual(r.area, 8.0, places=5)

    def test_sans_erreur_le_calcul_normal(self):
        from shapely.geometry import box
        self.assertAlmostEqual(F._overlay('intersection', box(0, 0, 4, 4), box(2, 0, 6, 4)).area, 8.0, places=9)


class Reglages(unittest.TestCase):
    def test_import(self):
        p = tpp.Preset(name='f', kind='CP_Finishing', sections={'PROFONDEUR': {'ZBOTTOM': '1.5e-003', 'NBSLICES': '3'},
                                                                'SPECIALFINITION': {'SkipExternal': '1', 'Allowance': '1.e-004', 'climbMilling': '2'}})
        o = tpp.to_template(p)['operations'][0]
        self.assertTrue(o['vcarve_edges_only'])
        self.assertAlmostEqual(o['vcarve_step'], 0.5)
        self.assertEqual(o['finish_rule'], 877)
        self.assertTrue(o['finish_skip_frame'])
        self.assertFalse(o['finish_3d_only'])
        p.sections['SPECIALFINITION']['Mode3DOnly'] = '1'
        self.assertTrue(tpp.to_template(p)['operations'][0]['finish_3d_only'])

    def test_les_operations_enregistrees_ne_changent_pas(self):
        d = M.Operation(kind='vcarve', vcarve_edges_only=True).to_dict()
        d.pop('finish_rule')
        self.assertEqual(M.Operation.from_dict(d).finish_rule, 0)
        self.assertEqual(M.Operation().finish_rule, 877)

    def test_l_ancienne_regle_reste_calculable(self):
        tp = path_of([U], nb=1, depth=0.75, finish_rule=0)
        self.assertTrue(tp.moves)
        self.assertLessEqual(max(m.z for m in tp.moves if m.kind == 'feed'), 0.0)

    def test_le_corps_de_l_outil_est_signale(self):
        tp = path_of([U], nb=1, depth=8.0)
        self.assertTrue(any('corps' in w for w in tp.warnings))
        self.assertEqual(round(min(m.z for m in tp.moves), 3), -8.0)  # TE13 va à la profondeur demandée


class Graphe(unittest.TestCase):
    def test_allegement(self):
        pts = [(0.0, i * 0.1, -1.0) for i in range(100)]
        self.assertEqual(F._rdp3(pts, 0.001), [pts[0], pts[-1]])
        loop = [(math.cos(i / 40 * 6.2831853), math.sin(i / 40 * 6.2831853), 0.0) for i in range(41)]
        out = F._rdp3(loop, 0.02)
        self.assertLess(len(out), 40)
        self.assertEqual(out[0], loop[0])
        self.assertEqual(out[-1], loop[-1])

    def test_ordre_des_contours(self):
        from shapely.geometry import Polygon
        pts = [[(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)], [(5, 0), (6, 0), (6, 1), (5, 1), (5, 0)], [(3, 0), (4, 0), (4, 1), (3, 1), (3, 0)]]
        order, tops = F.finish_order(pts, [Polygon(p) for p in pts])
        self.assertEqual(order, [0, 1, 2])
        self.assertEqual(tops, {0, 1, 2})
        self.assertEqual(F.finish_order(pts, [Polygon(p) for p in pts], True)[0], [0, 2, 1])

    def test_ordre_avec_des_contours_englobes(self):
        from shapely.geometry import Polygon

        def sq(x, y, w, h):
            return [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
        pts = [sq(0, 0, 100, 100), sq(5, 5, 90, 90), sq(10, 10, 5, 5), sq(50, 10, 5, 5), sq(30, 10, 5, 5)]
        order, tops = F.finish_order(pts, [Polygon(p) for p in pts])
        self.assertEqual(order, [0, 1, 3, 4, 2])                     # relevé dans TE13 : le cadre, l'îlot, puis de droite à gauche
        self.assertEqual(tops, {0})


if __name__ == '__main__':
    unittest.main()
