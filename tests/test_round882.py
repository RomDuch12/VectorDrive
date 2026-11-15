"""Round 882 : les Lettres prismatiques, relevées dans TE13 sur mes dessins, et le squelette droit."""
import math
import unittest

from shapely.geometry import Polygon, box

from vectordrive.cam import advanced as A
from vectordrive.cam import model as M
from vectordrive.cam import simulate as SIM
from vectordrive.cam import skeleton as SK
from vectordrive.cam import strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape
from vectordrive.ui import cam_panel

TAN = math.tan(math.radians(15))


def P(*pts):
    return geom.polyline(list(pts), closed=True)


def drawing(*shapes):
    doc = Document()
    doc.plate = Plate(width=300.0, height=100.0)
    doc.layers = [Layer(name='A', items=[Shape(path=geom.Path(list(s))) for s in shapes])]
    return doc


def path_of(shapes, *, depth=2.0, step=2.0, tool=None, **kw):
    doc = drawing(*shapes)
    setup = M.setup_of(doc)
    t = tool or M.CamTool(name='c', kind='conique', diameter=8.0, tip=0.2, angle=30.0)
    setup.tools.append(t)
    op = M.Operation(kind='prismatique', tool_id=t.id, depth=depth, step_down=step, climb=kw.pop('climb', True), **kw)
    setup.operations.append(op)
    M.store(doc, setup)
    return S.compute(doc, setup, op, (0.0, 0.0)), setup


def runs(tp):
    """Les morceaux de coupe : le point d'arrivée de la plongée, puis les mouvements."""
    out, cur = [], None
    for m in tp.moves:
        if m.kind == 'plunge':
            cur = [m]
            out.append(cur)
        elif m.kind == 'rapid':
            cur = None
        elif cur is not None:
            cur.append(m)
    return [c for c in out if len(c) > 1]


def flat(tp):
    return [c for c in runs(tp) if max(m.z for m in c) - min(m.z for m in c) < 1e-9]


def walks(tp):
    return [c for c in runs(tp) if max(m.z for m in c) - min(m.z for m in c) >= 1e-9]


def area(c):
    return sum(a.x * b.y - b.x * a.y for a, b in zip(c, c[1:])) / 2


def square(x=220.0, y=15.0, w=30.0):
    return [P((x, y), (x + w, y), (x + w, y + w), (x, y + w))]


STEMS = [(70, 10), (100, 10), (100, 20), (95.4, 20), (95.4, 50), (94.6, 50), (94.6, 20), (75.25, 20), (75.25, 50), (74.75, 50), (74.75, 20), (70, 20)]


class Squelette(unittest.TestCase):
    def test_un_carre(self):
        arcs = SK.checked_arcs(box(0, 0, 30, 30))
        ends = {(round(a[3], 2), round(a[4], 2), round(a[5], 2)) for a in arcs if a[7] >= 0}
        self.assertEqual(ends, {(15.0, 15.0, 15.0)})

    def test_un_rectangle_a_son_arete(self):
        arcs = SK.checked_arcs(box(0, 0, 30, 10))
        tops = {(round(a[3], 1), round(a[4], 1)) for a in arcs if a[7] >= 0}
        self.assertEqual(tops, {(5.0, 5.0), (25.0, 5.0)})
        self.assertAlmostEqual(max(a[5] for a in arcs), 5.0, 3)

    def test_les_tiges_comme_dans_te13(self):
        # relevé : (95, 19,6) et (95, 49,6) pour la tige de 0,8 ; (75, 19,75) et (75, 49,75) pour celle de 0,5
        tours = SK.roof_tours(SK.checked_arcs(Polygon(STEMS)), 0.536, 22.5)
        pts = {(round(x, 2), round(y, 2), round(t, 2)) for tour in tours for x, y, t in tour}
        for want in ((95.0, 19.6, 0.4), (95.0, 49.6, 0.4), (75.0, 19.75, 0.25), (75.0, 49.75, 0.25)):
            self.assertIn(want, pts)

    def test_une_forme_a_trou(self):
        arcs = SK.checked_arcs(box(10, 10, 60, 60).difference(box(20, 20, 50, 50)))
        self.assertAlmostEqual(max(a[5] for a in arcs), 5.0, 3)
        self.assertEqual(sum(a[7] == 0 for a in arcs), 4)
        self.assertEqual(sum(a[7] == 1 for a in arcs), 4)

    def test_un_contour_dentele_aboutit(self):
        pts = []
        for k in range(1000):
            a = 2 * math.pi * k / 1000
            r = 100 + (5 if k % 2 else 0) + 3 * math.sin(7 * a)
            pts.append((r * math.cos(a), r * math.sin(a)))
        self.assertIsNotNone(SK.checked_arcs(Polygon(pts)))

    def test_un_voile_tres_fin(self):
        # deux carrés reliés par un voile de 0,01 micron : plus fin que le déplacement des points, comme sur un dessin réel
        f = 1e-5
        poly = Polygon([(0, 0), (10, 0), (10, 5), (20, 5), (20, 0), (30, 0), (30, 10), (20, 10), (20, 5 + f), (10, 5 + f), (10, 10), (0, 10)])
        self.assertTrue(poly.is_valid)
        arcs = SK.checked_arcs(poly)
        self.assertIsNotNone(arcs)
        ends = {(round(a[3], 1), round(a[4], 1)) for a in arcs}
        self.assertIn((5.0, 5.0), ends)
        self.assertIn((25.0, 5.0), ends)

    def test_un_coin_rentrant_tres_aigu(self):
        # son sommet avance très vite : le filtre des côtés à portée ne doit pas le perdre
        poly = Polygon([(0, 0), (100, 0), (100, 50), (51, 50), (50, 5), (49, 50), (0, 50)])
        arcs = SK.checked_arcs(poly)
        self.assertIsNotNone(arcs)
        self.assertLessEqual(max(a[5] for a in arcs), 25.01)

    def test_le_sens_des_anneaux(self):
        self.assertEqual(len(SK._clean_ring([(0, 0), (1, 0), (2, 0), (2, 2), (0, 2), (0, 0)], True)), 4)      # sans le sommet aligné
        ring = SK._clean_ring([(0, 0), (0, 2), (2, 2), (2, 0), (0, 0)], True)
        self.assertGreater(sum(ring[i - 1][0] * ring[i][1] - ring[i][0] * ring[i - 1][1] for i in range(4)), 0)

    def test_un_cycle_n_est_pas_repasse(self):
        ring = Polygon([(12 * math.cos(2 * math.pi * k / 80), 12 * math.sin(2 * math.pi * k / 80)) for k in range(80)],
                       [[(8 * math.cos(2 * math.pi * k / 60), 8 * math.sin(2 * math.pi * k / 60)) for k in range(60)]])
        tours = SK.roof_tours(SK.checked_arcs(ring), 20.0, 22.5)
        total = sum(math.dist(a[:2], b[:2]) for t in tours for a, b in zip(t, t[1:]))
        self.assertAlmostEqual(total, 2 * math.pi * 10, delta=3.0)


class Relief(unittest.TestCase):
    def test_haut_et_fond_d_un_carre(self):
        # relevé : le contour exact au fond ; le plat s'arrête à H·tan du bord, et la passe à Z = 0 n'enlèverait rien
        tp, _s = path_of([square()])
        rings = flat(tp)
        self.assertEqual(len(rings), 1)
        self.assertAlmostEqual(rings[0][0].z, -2.0)
        xs = [m.x for m in rings[0]]
        self.assertEqual((min(xs), max(xs)), (220.0, 250.0))

    def test_les_niveaux_partent_du_fond(self):
        tp, _s = path_of([square()], depth=2.2, step=1.0)
        zs = sorted({round(c[0].z, 3) for c in flat(tp)}, reverse=True)
        self.assertEqual(zs, [-0.2, -1.2, -2.2])

    def test_le_decalage_de_chaque_niveau(self):
        tp, _s = path_of([square()], step=0.5)
        for c in flat(tp):
            d = (2.0 + c[0].z) * TAN
            self.assertAlmostEqual(min(m.x for m in c), 220.0 + d, 3)
            self.assertAlmostEqual(max(m.x for m in c), 250.0 - d, 3)

    def test_du_haut_vers_le_bas(self):
        tp, _s = path_of([square()], step=0.5)
        self.assertEqual([round(c[0].z, 2) for c in flat(tp)], [-0.5, -1.0, -1.5, -2.0])

    def test_le_sens(self):
        # relevé : en avalant, le sens direct autour d'un extérieur et l'inverse autour d'un trou, en relief comme en creux
        shape = [geom.circle((30, 30), 12), geom.circle((30, 30), 8)]
        for hollow in (False, True):
            tp, _s = path_of([shape], prism_hollow=hollow)
            signs = sorted(area(c) > 0 for c in flat(tp))
            self.assertEqual(signs, [False, True])
            big = max(flat(tp), key=lambda c: abs(area(c)))
            self.assertGreater(area(big), 0)
            tp, _s = path_of([shape], prism_hollow=hollow, climb=False)
            big = max(flat(tp), key=lambda c: abs(area(c)))
            self.assertLess(area(big), 0)

    def test_l_ordre_des_formes(self):
        # relevé : au-dessus du fond, la dernière forme d'abord, l'extérieur avant ce qu'il contient ; au fond, l'inverse
        doc_shapes = [[P((10, 10), (60, 10), (60, 60), (10, 60)), P((20, 20), (50, 20), (50, 50), (20, 50))],
                      [P((30, 30), (40, 30), (40, 40), (30, 40))],
                      square(100, 10, 20)]
        tp, _s = path_of(doc_shapes, step=1.0)
        top = [round(min(m.x for m in c), 0) for c in flat(tp) if abs(c[0].z + 1.0) < 1e-6]
        low = [round(min(m.x for m in c), 0) for c in flat(tp) if abs(c[0].z + 2.0) < 1e-6]
        self.assertEqual(low, [30.0, 20.0, 10.0, 100.0])
        self.assertEqual(len(top), 4)
        self.assertEqual(top[0], 100.0)
        self.assertLess(top[1], top[2])

    def test_le_depart_est_celui_du_dessin(self):
        tp, _s = path_of([[P((250, 15), (250, 45), (220, 45), (220, 15))]])
        c = flat(tp)[0]
        self.assertEqual((c[0].x, c[0].y), (250.0, 15.0))


class Creux(unittest.TestCase):
    def test_le_fond_est_decale(self):
        tp, _s = path_of([square()], prism_hollow=True)
        rings = flat(tp)
        self.assertEqual(len(rings), 1)
        self.assertAlmostEqual(rings[0][0].z, -2.0)
        self.assertAlmostEqual(min(m.x for m in rings[0]), 220 + 2 * TAN, 3)

    def test_les_niveaux_partent_de_la_surface(self):
        tp, _s = path_of([square()], depth=2.2, step=1.0, prism_hollow=True)
        zs = [round(c[0].z, 3) for c in flat(tp)]
        self.assertEqual(zs, [-1.0, -2.0, -2.2])
        for c in flat(tp):
            self.assertAlmostEqual(min(m.x for m in c), 220 - c[0].z * TAN, 3)

    def test_les_aretes_vont_de_la_surface_au_fond(self):
        tp, _s = path_of([square()], prism_hollow=True)
        w = walks(tp)
        self.assertEqual(len(w), 4)
        for c in w:
            self.assertAlmostEqual(c[0].z, -2.0)
            self.assertAlmostEqual(c[1].z, 0.0)
            self.assertIn(round(c[1].x), (220, 250))


class Laterales(unittest.TestCase):
    def test_en_relief(self):
        # relevé : à chaque niveau, tous les décalages entre le flanc et le bord, du flanc vers le bord
        tp, _s = path_of([square()], step=0.5, prism_lateral=True)
        lv = {}
        for c in flat(tp):
            lv.setdefault(round(c[0].z, 2), []).append(round((min(m.x for m in c) - 220.0) / TAN, 2))
        self.assertEqual(lv[-0.5], [1.5, 1.0, 0.5, 0.0])
        self.assertEqual(lv[-1.0], [1.0, 0.5, 0.0])
        self.assertEqual(lv[-2.0], [0.0])

    def test_en_creux_jusqu_au_centre(self):
        tp, _s = path_of([square(w=4.0)], step=0.5, prism_hollow=True, prism_lateral=True)
        at_z = [c for c in flat(tp) if abs(c[0].z + 1.0) < 1e-6]
        # de 1,0·tan à 2 mm (le centre), de 0,5·tan en 0,5·tan
        self.assertEqual(len(at_z), int((2.0 - 1.0 * TAN) / (0.5 * TAN)) + 1)
        self.assertAlmostEqual(min(m.x for m in at_z[0]), 220 + TAN, 3)


class Aretes(unittest.TestCase):
    def test_un_aller_retour_par_coin(self):
        # relevé : (249,464, 15,536, 0) → (250, 15, −2) → retour ; 4,28 mm
        tp, _s = path_of([square()])
        w = walks(tp)
        self.assertEqual(len(w), 4)
        for c in w:
            self.assertEqual(len(c), 3)
            self.assertAlmostEqual(c[0].z, 0.0)
            self.assertAlmostEqual(c[1].z, -2.0)
            self.assertAlmostEqual(math.dist((c[0].x, c[0].y, c[0].z), (c[1].x, c[1].y, c[1].z)) * 2, 4.28, 2)

    def test_le_seuil_de_tournant(self):
        # relevé : 20° pas d'arête, 25° une arête
        def bend(turn):
            h = math.radians(turn)
            return [P((0, 0), (40, 0), (40 + 40 * math.cos(h), 40 * math.sin(h)), (40 + 40 * math.cos(h), 90), (0, 90))]
        def count(turn):
            tp, _s = path_of([bend(turn)], depth=0.5, step=0.5)
            return sum(1 for c in walks(tp) if any(abs(m.x - 40) < 0.2 and m.y < 1 and m.z < -0.4 for m in c))
        self.assertEqual(count(20), 0)
        self.assertEqual(count(25), 1)

    def test_les_coins_rentrants_aussi(self):
        tp, _s = path_of([[P(*STEMS)]])
        lows = {(round(m.x, 2), round(m.y, 2)) for c in walks(tp) for m in c if m.z < -1.99}
        self.assertLessEqual({(95.4, 20.0), (94.6, 20.0), (75.25, 20.0), (74.75, 20.0)}, lows)

    def test_la_tige_etroite_suit_son_arete(self):
        # relevé : z = −2 + 0,4 / tan 15° = −0,507 le long de la tige de 0,8
        tp, _s = path_of([[P(*STEMS)]])
        pts = {(round(m.x, 2), round(m.y, 2), round(m.z, 2)) for c in walks(tp) for m in c}
        self.assertIn((95.0, 49.6, -0.51), pts)
        self.assertIn((75.0, 49.75, -1.07), pts)

    def test_un_contour_courbe_a_une_couture(self):
        tp, _s = path_of([[geom.circle((30, 30), 15)]])
        w = walks(tp)
        self.assertEqual(len(w), 1)
        self.assertEqual(len(w[0]), 2)
        self.assertAlmostEqual(math.dist((w[0][0].x, w[0][0].y), (w[0][1].x, w[0][1].y)), 2 * TAN, 2)

    def test_jamais_au_dessus_de_la_surface(self):
        tp, _s = path_of([[P(*STEMS)], square()], depth=5.0, step=1.0)
        self.assertLessEqual(max(m.z for c in runs(tp) for m in c), 1e-9)


class Hauteurs(unittest.TestCase):
    def test_sans_la_troncature(self):
        # relevé : le bouton Calculer de TE13 donne 55,98 pour un carré de 30 et 7,47 pour un trait de 4
        reg = S.region([geom.Path(square()), geom.Path([P((0, 0), (40, 0), (40, 4), (0, 4))])], 0.01)
        t = M.CamTool(name='c', kind='conique', diameter=8.0, tip=0.2, angle=30.0)
        top, low = A.prismatic_heights(reg, t, te=True)
        self.assertAlmostEqual(top, 15 / TAN, 1)
        self.assertAlmostEqual(low, 2 / TAN, 1)

    def test_calculee_elle_reste_dans_le_cone(self):
        tp, _s = path_of([square()], depth=0.0, step=5.0)
        self.assertTrue(any('profondeur limitée' in w for w in tp.warnings), tp.warnings)
        want = (4.0 - 0.1) / TAN
        self.assertAlmostEqual(min(m.z for m in tp.moves), -want, 2)

    def test_demandee_on_la_fait_en_prevenant(self):
        tp, _s = path_of([square()], depth=20.0, step=20.0)
        self.assertAlmostEqual(min(m.z for m in tp.moves), -20.0, 3)
        self.assertTrue(any('son corps touchera' in w for w in tp.warnings), tp.warnings)


class Matiere(unittest.TestCase):
    def test_le_profil_d_une_barre(self):
        t = M.CamTool(name='c', kind='conique', diameter=8.0, tip=0.2, angle=90.0)
        tp, setup = path_of([[P((0, 0), (30, 0), (30, 10), (0, 10))]], depth=3.0, step=0.5, tool=t)
        sim = SIM.simulate([tp], setup, res=0.05)

        def z(x, y):
            return float(sim.H[int(round((y - sim.y0) / sim.res)), int(round((x - sim.x0) / sim.res))])
        self.assertAlmostEqual(z(15, 0), -3.0, 1)                        # le fond, sous le contour
        self.assertAlmostEqual(z(15, 2), -3.0 + (2 - 0.1), 1)            # le flanc à 45° : décalé de la troncature
        self.assertAlmostEqual(z(15, 5), 0.0, 1)                         # le plat du dessus


class Ancien(unittest.TestCase):
    def test_une_operation_d_avant_ne_change_pas(self):
        d = M.Operation(kind='prismatique').to_dict()
        self.assertEqual(M.Operation.from_dict(d).prism_rule, 882)
        del d['prism_rule']
        self.assertEqual(M.Operation.from_dict(d).prism_rule, 0)
        tp, _s = path_of([square()], step=2.0, prism_rule=0)
        self.assertEqual(walks(tp), [])
        self.assertAlmostEqual(min(m.x for m in flat(tp)[0]), 219.9, 3)  # le contour décalé de la troncature, vers l'extérieur

    def test_le_debordement_reste(self):
        tp, _s = path_of([square()], extension=1.0)
        self.assertLess(min(m.x for m in tp.moves if m.kind == 'feed'), 219.5)
        self.assertLessEqual(max(m.z for c in runs(tp) for m in c), 1e-9)


class Formulaire(unittest.TestCase):
    def test_les_cases(self):
        self.assertLessEqual({'prism_hollow', 'prism_lateral'}, cam_panel.KIND_FIELDS['prismatique'])
        for f in ('prism_hollow', 'prism_lateral'):
            self.assertIn(f, cam_panel.LABELS)
            self.assertTrue(any(f in fields for _n, fields in cam_panel.OP_SECTIONS))


if __name__ == '__main__':
    unittest.main()
