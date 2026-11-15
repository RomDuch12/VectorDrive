"""Round 881 : l'Intaille et l'axe médian sans branches parasites, relevés dans TE13 sur mes dessins."""
import math
import unittest

from shapely.geometry import LineString, Point, box

from vectordrive.cam import advanced as A
from vectordrive.cam import model as M
from vectordrive.cam import strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Document, Layer, Plate, Shape


def P(*pts):
    return geom.polyline(list(pts), closed=True)


def stadium(x0, y0, x1, r):
    pts = []
    for k in range(0, 41):
        a = -math.pi / 2 + math.pi * k / 40
        pts.append((x1 + r * math.cos(a), y0 + r * math.sin(a)))
    for k in range(0, 41):
        a = math.pi / 2 + math.pi * k / 40
        pts.append((x0 + r * math.cos(a), y0 + r * math.sin(a)))
    return geom.polyline(pts, closed=True)


def drawing(*shapes):
    doc = Document()
    doc.plate = Plate(width=300.0, height=100.0)
    doc.layers = [Layer(name='A', items=[Shape(path=geom.Path(list(s))) for s in shapes])]
    return doc


def path_of(shapes, *, depth=2.0, **kw):
    doc = drawing(*shapes)
    setup = M.setup_of(doc)
    t = M.CamTool(name='c', kind='conique', diameter=6.0, tip=0.2, angle=30.0)
    setup.tools.append(t)
    op = M.Operation(kind='vcarve', tool_id=t.id, depth=depth, step_down=9.0, resolution=0.05, vcarve_mode='axe', **kw)
    setup.operations.append(op)
    M.store(doc, setup)
    return S.compute(doc, setup, op, (0.0, 0.0))


def cut(tp, z=-1e-6):
    """Longueur au-dessous de la surface, sans les plongées."""
    total, prev = 0.0, None
    for m in tp.moves:
        if prev is not None and m.kind == 'feed' and m.z < z and prev.z < z:
            total += math.dist((prev.x, prev.y), (m.x, m.y))
        prev = m
    return total


class Formes(unittest.TestCase):
    def test_un_cercle_ne_donne_rien(self):
        tp = path_of([[geom.circle((30, 30), 15)]])
        self.assertLess(cut(tp), 0.5)
        self.assertTrue(any('pas d\'axe' in w for w in tp.warnings), tp.warnings)

    def test_un_anneau_son_cercle_moyen(self):
        tp = path_of([[geom.circle((20, 30), 12), geom.circle((20, 30), 8)]])
        self.assertAlmostEqual(cut(tp), 2 * math.pi * 10, delta=2.0)     # TE13 : 62,85
        for m in tp.moves:
            if m.kind == 'feed' and m.z < -0.1:
                self.assertAlmostEqual(math.hypot(m.x - 20, m.y - 30), 10.0, delta=0.05)

    def test_un_oblong_son_axe(self):
        tp = path_of([[stadium(50, 30, 80, 6)]])
        self.assertAlmostEqual(cut(tp), 30.0, delta=1.0)                 # TE13 : 30
        for m in tp.moves:
            if m.kind == 'feed' and m.z < -0.1:
                self.assertAlmostEqual(m.y, 30.0, delta=0.05)

    def test_une_ellipse_le_segment_des_centres_de_courbure(self):
        tp = path_of([[geom.ellipse((125, 30), 25, 8)]])
        self.assertAlmostEqual(cut(tp), 44.87, delta=2.0)                # TE13 : 44,87
        xs = [m.x for m in tp.moves if m.kind == 'feed' and m.z < -0.1]
        self.assertAlmostEqual(max(xs), 147.43, delta=1.5)
        self.assertAlmostEqual(min(xs), 102.57, delta=1.5)

    def test_un_carre_ses_diagonales(self):
        tp = path_of([[P((220, 15), (250, 15), (250, 45), (220, 45))]], depth=0.5)
        self.assertAlmostEqual(cut(tp), 4 * math.dist((220.234, 15.234), (235, 30)), delta=1.0)

    def test_le_120_garde_sa_branche_le_150_non(self):
        # relevé dans TE13 : même limite que les tirés d'angle de la Finition (135°)
        def with_corner(angle):
            # un coin d'ouverture `angle` en (0, 0), fermé loin de là
            a = math.radians(angle)
            return [[P((0, 0), (40, 0), (40, 40 * math.tan(a) if angle < 90 else 40), (40 * math.cos(a) if angle > 90 else 40 / math.tan(a), 40 * math.sin(a) if angle > 90 else 40))]]
        near = lambda tp: [m for m in tp.moves if m.kind == 'feed' and m.z <= 0 and math.hypot(m.x, m.y) < 2.0]
        self.assertTrue(near(path_of(with_corner(120))))
        self.assertFalse(near(path_of(with_corner(150))))


class Ancien(unittest.TestCase):
    def test_une_operation_d_avant_garde_ses_branches(self):
        d = M.Operation(kind='vcarve', vcarve_mode='axe').to_dict()
        self.assertEqual(M.Operation.from_dict(d).gravure_rule, 881)
        del d['gravure_rule']
        self.assertEqual(M.Operation.from_dict(d).gravure_rule, 0)
        tp = path_of([[geom.circle((30, 30), 15)]], gravure_rule=880)
        self.assertGreater(cut(tp), 100.0)                               # l'étoile d'avant


class Liaisons(unittest.TestCase):
    def test_on_reste_au_fond_d_une_branche_a_la_suivante(self):
        new = path_of([[P((220, 15), (250, 15), (250, 45), (220, 45))]], depth=0.5)
        old = path_of([[P((220, 15), (250, 15), (250, 45), (220, 45))]], depth=0.5, gravure_rule=880)
        self.assertLess(sum(m.kind == 'rapid' for m in new.moves), sum(m.kind == 'rapid' for m in old.moves))


class Elagage(unittest.TestCase):
    def setUp(self):
        self.reg = box(0, 0, 100, 40)

    def test_vide(self):
        self.assertEqual(A.prune_hairs([], self.reg), [])

    def test_une_branche_vers_un_coin_vif_reste(self):
        c = [[(10.0, 10.0), (20.0, 20.0)], [(20.0, 20.0), (80.0, 20.0)]]
        self.assertEqual(len(A.prune_hairs(c, self.reg)), 2)            # 90° : la distance baisse de 0,71 par mm

    def test_un_poil_disparait(self):
        c = [[(20.0, 20.0), (80.0, 20.0)], [(50.0, 20.0), (50.0, 1.0)]]   # droit vers le bord : la distance baisse de 1 par mm
        got = A.prune_hairs(c, self.reg)
        self.assertEqual(got, [c[0]])

    def test_un_axe_de_largeur_constante_reste(self):
        c = [[(20.0, 20.0), (80.0, 20.0)]]
        self.assertEqual(A.prune_hairs(c, self.reg), c)

    def test_un_morceau_isole_tres_court(self):
        c = [[(50.0, 20.0), (50.1, 20.0)]]
        self.assertEqual(A.prune_hairs(c, self.reg, tiny=1.0), [])
        self.assertEqual(A.prune_hairs(c, self.reg), c)

    def test_les_poils_sur_une_branche(self):
        # après avoir retiré les poils, ce qui devient un bout est jugé à son tour
        c = [[(50.0, 20.0), (50.0, 10.0)], [(50.0, 10.0), (50.0, 1.0)], [(50.0, 10.0), (41.0, 10.0)]]
        got = A.prune_hairs(c, self.reg, 135.0)
        self.assertNotIn(c[1], got)


class FinitionCourbe(unittest.TestCase):
    def test_un_trait_courbe_sans_poils(self):
        # un anneau étroit : l'axe d'une Finition profonde ne fait que le tour
        doc = drawing([geom.circle((30, 30), 12), geom.circle((30, 30), 10.6)])
        setup = M.setup_of(doc)
        t = M.CamTool(name='c', kind='conique', diameter=6.0, tip=0.2, angle=30.0)
        setup.tools.append(t)
        op = M.Operation(kind='vcarve', tool_id=t.id, depth=3.0, step_down=3.0, vcarve_edges_only=True, vcarve_step=3.0, ramp=False, resolution=0.1)
        setup.operations.append(op)
        M.store(doc, setup)
        tp = S.compute(doc, setup, op, (0.0, 0.0))
        for m in tp.moves:
            if m.kind == 'feed' and m.z < -0.1:
                self.assertAlmostEqual(math.hypot(m.x - 30, m.y - 30), 11.3, delta=0.1)


if __name__ == '__main__':
    unittest.main()
