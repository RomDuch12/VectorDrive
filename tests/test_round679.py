"""Round 679 : parois alignées d'une tranche à l'autre dans le noyau B-rep (core.brep) — marches, talon,
tenon, épaulement, équerre, poche ouverte sur le bord : solides fermés, arêtes partagées, faces tournées
vers l'extérieur, volume exact, maillage fermé ; croisements, contact en un point, tranches bord à bord,
cercle tangent toujours refusés ; pièces d'avant inchangées. Générateurs : bride à talon, mors doux à
épaulement, écrou pour rainure en T."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np

from vectordrive.core import brep as B
from vectordrive.core import stepgen as G
from tests.test_round673 import geometry_errors, misoriented, topology

R = B.rounded_rect


def mesh_volume(b):
    from vectordrive.core import solids as SO
    return SO.from_triangles(B.mesh(b, n_arc=256), b.name).volume()      # fermé, orienté : sinon SolidError


def placed_bounds(b):
    P = B.mesh(b).reshape(-1, 3)
    return [round(float(x), 6) + 0.0 for x in list(P.min(axis=0)) + list(P.max(axis=0))]


class TestFlush(unittest.TestCase):
    def assertValid(self, b, volume=None):
        text = B.step_text([b], b.name)
        top = topology(text)
        self.assertEqual(len(top), 1, b.name)                             # une coque
        self.assertFalse(top[0][-1], b.name)                              # chaque arête bordée deux fois
        self.assertEqual(geometry_errors(text), [], b.name)
        self.assertEqual(misoriented(text, lambda q: B.contains(b, q)), [], b.name)
        v = B.volume(b)
        self.assertAlmostEqual(mesh_volume(b) / v, 1.0, delta=1e-4, msg=b.name)
        if volume is not None:
            self.assertAlmostEqual(v, volume, 3, b.name)
        return text

    def test_flush_shapes(self):
        stairs = B.Body('marches', [B.Slab(i * 8, (i + 1) * 8, [R(0, 0, 48 - 12 * i, 30)]) for i in range(4)])
        self.assertValid(stairs, sum((48 - 12 * i) * 30 * 8 for i in range(4)))
        heel = B.Body('talon', [B.Slab(0, 15, [R(85, -15, 100, 15)]),
                                B.Slab(15, 30, [R(0, -15, 100, 15), B.slot(50, 0, 40, 11)])])
        self.assertValid(heel)
        nut = B.Body('ecrou', [B.Slab(0, 8, [R(-11, -11, 11, 11), B.Circle(0, 0, 5.5)]),
                               B.Slab(8, 16, [R(-11, -7, 11, 7), B.Circle(0, 0, 5.5)])])
        self.assertValid(nut, 22 * (22 * 8 + 14 * 8) - math.pi * 5.5 ** 2 * 16)
        angle = B.Body('equerre', [B.Slab(0, 5, [R(0, 0, 50, 50)]),
                                   B.Slab(5, 40, [B.Poly([(0, 0), (50, 0), (50, 5), (5, 5), (5, 50), (0, 50)])])])
        self.assertValid(angle, 50 * 50 * 5 + 35 * (50 * 5 + 45 * 5))
        pocket = B.Body('poche', [B.Slab(0, 5, [R(0, 0, 40, 40)]),
                                  B.Slab(5, 10, [B.Poly([(0, 0), (40, 0), (40, 40), (0, 40), (0, 30), (20, 30),
                                                         (20, 10), (0, 10)])])])
        self.assertValid(pocket, 40 * 40 * 10 - 20 * 20 * 5)              # poche ouverte sur le bord X = 0
        over = B.Body('dessus', [B.Slab(0, 5, [R(0, 0, 30, 40)]), B.Slab(5, 10, [R(0, 0, 50, 40)])])
        self.assertValid(over, 30 * 40 * 5 + 50 * 40 * 5)                 # porte-à-faux : face vers le bas
        tilted = B.Body('placee', [B.Slab(0, 8, [R(-11, -11, 11, 11)]), B.Slab(8, 16, [R(-11, -7, 11, 7)])],
                        matrix=B.compose(B.translation(5, 6, 7), B.rotation_z(30)))
        self.assertValid(tilted)

    def test_shared_edges_split(self):
        b = B.Body('marche', [B.Slab(0, 8, [R(0, 0, 48, 30)]), B.Slab(8, 16, [R(0, 0, 36, 30)])])
        text = B.step_text([b], 'marche')
        self.assertIn("CARTESIAN_POINT('',(36.,0.,8.))", text)            # le sommet de la marche, partagé
        faces = text.count('ADVANCED_FACE(')
        self.assertEqual(faces, 2 + 4 + 4 + 1)                            # dessous, dessus, 2 × 4 parois, marche

    def test_refusals(self):
        bad = {
            'croisees': [B.Slab(0, 5, [R(0, 0, 40, 40)]), B.Slab(5, 10, [R(20, 20, 60, 60)])],
            'point': [B.Slab(0, 5, [R(0, 0, 40, 40)]), B.Slab(5, 10, [R(40, 40, 60, 60)])],
            'bord_a_bord': [B.Slab(0, 5, [R(0, 0, 40, 40)]), B.Slab(5, 10, [R(40, 0, 60, 40)])],
            'coin_dedans': [B.Slab(0, 5, [R(0, 0, 40, 40)]), B.Slab(5, 10, [B.Poly([(20, 0), (30, 20), (10, 20)])])],
            'tangent': [B.Slab(0, 5, [R(0, 0, 40, 40)]), B.Slab(5, 10, [B.Circle(20, 10, 10)])],
            'cercles': [B.Slab(0, 1, [B.Circle(0, 0, 5)]), B.Slab(1, 2, [B.Circle(3, 0, 5)])],
        }
        for name, slabs in bad.items():
            with self.assertRaises(B.BrepError, msg=name):
                B.step_text([B.Body(name, slabs)], name)
            with self.assertRaises(B.BrepError, msg=name):
                B.mesh(B.Body(name, slabs))

    def test_float_noise(self):
        """Des cotes au bruit de calcul près : acceptées, STEP juste et maillage fermé."""
        c, sn = math.cos(math.radians(30)), math.sin(math.radians(30))
        rot = lambda pts: [(x * c - y * sn, x * sn + y * c) for x, y in pts]       # noqa: E731
        cases = {
            'somme': [B.Slab(0, 5, [R(0, 0.3, 40, 30)]), B.Slab(5, 10, [R(0, 0.1 + 0.2, 20, 30)])],
            'tournee': [B.Slab(0, 5, [B.Poly(rot([(0, 0), (40, 0), (40, 30), (0, 30)]))]),
                        B.Slab(5, 10, [B.Poly(rot([(0, 0), (20, 0), (20, 30), (0, 30)]))])],
            'decalee': [B.Slab(0, 5, [R(0, 0, 40, 30)]), B.Slab(5, 10, [R(0, 1e-9, 20, 30)])],
            'recouvrement': [B.Slab(0, 5, [B.Poly([(0, 0), (20, 0), (40, 0), (40, 30), (0, 30)])]),
                             B.Slab(5, 10, [R(20 - 4e-15, 0, 40, 30)])],
        }
        # essai au hasard : un sommet du carré du dessus à 1e-15 d'un côté du polygone du dessous, sans le
        # croiser exactement (accepté sans paroi alignée avant : face du dessus mal découpée, maillage ouvert)
        poly = [(-4.694773936166932, 82.32836144177952), (13.147718508500228, 25.04271347161167),
                (-5.94749748155572, 19.095215990055948), (-2.97374874077786, 9.547607995027974),
                (16.12146724927809, 15.495105476583696), (19.095215990055948, 5.94749748155572),
                (38.190431980111896, 11.89499496311144), (26.295437017000456, 50.08542694322334),
                (14.400442053889018, 88.27585892333524)]
        square = [(19.721577762750343, 37.5640702074175), (16.747829021972482, 47.111678202445475),
                  (7.200221026944509, 44.13792946166762), (10.173969767722369, 34.590321466639644)]
        cases['hasard'] = [B.Slab(0, 5, [B.Poly(poly)]), B.Slab(5, 10, [B.Poly(square)])]
        for name, slabs in cases.items():
            self.assertValid(B.Body(name, slabs))
        self.assertEqual(B.check(B.Body('hasard', cases['hasard'])), {5.0})
        # un sommet d'un losange sur un côté de la tranche du dessous, au bruit de calcul près (à 2e-15 sans
        # s'y croiser, ou dessus) : refusé ou juste selon le côté du bruit, jamais un maillage ouvert
        refused = 0
        for deg in (30.0, 17.3, 41.7, 23.0):
            ca, sa = math.cos(math.radians(deg)), math.sin(math.radians(deg))
            for y0 in (7, 10, 15, 21):
                turn = [(x * ca - y * sa, x * sa + y * ca) for x, y in ((0, 0), (40, 0), (40, 30), (0, 30))]
                diamond = [(x * ca - y * sa, x * sa + y * ca) for x, y in ((0, y0), (6, y0 - 6), (12, y0), (6, y0 + 6))]
                for upper in (False, True):        # losange au-dessus, ou plaque au-dessus du losange
                    lo, hi = (turn, diamond) if not upper else (diamond, turn)
                    b = B.Body(f'pointe_{deg:g}_{y0}_{int(upper)}', [B.Slab(0, 5, [B.Poly(lo)]), B.Slab(5, 10, [B.Poly(hi)])])
                    try:
                        B.check(b)
                    except B.BrepError:
                        refused += 1
                        with self.assertRaises(B.BrepError, msg=b.name):
                            B.mesh(b)
                        continue
                    self.assertValid(b)
        self.assertGreater(refused, 0)

    def test_review_refusals(self):
        bl = math.tan(0.085)
        bad = {
            'presque': [B.Slab(0, 5, [R(0, 0, 40, 30)]), B.Slab(5, 10, [R(5e-7, 0, 20, 30)])],
            'tenon': [B.Slab(0, 8, [R(-11, -11, 11, 11)]), B.Slab(8, 16, [R(-11, -(11 - 6e-7), 11, 11 - 6e-7)])],
            'bouchon': [B.Slab(0, 5, [R(0, 0, 40, 40), R(10, 10, 30, 30)]), B.Slab(5, 10, [R(10, 10, 30, 30)])],
            'bouchon_rond': [B.Slab(0, 5, [B.Circle(0, 0, 10), B.Circle(0, 0, 5)]), B.Slab(5, 10, [B.Circle(0, 0, 5)])],
            'cadre': [B.Slab(0, 5, [R(-10, -10, 50, 50), R(0, 0, 40, 40)]), B.Slab(5, 10, [R(0, 0, 40, 40)])],
            'arc_tangent': [B.Slab(0, 5, [R(0, 0, 40, 40)]),
                            B.Slab(5, 10, [B.Poly([(0, 20), (0, 10 * bl), (10, 10 * bl), (30, 10 * bl), (30, 20)],
                                                  [0, 0, bl, 0, 0])])],
        }
        for name, slabs in bad.items():
            with self.assertRaises(B.BrepError, msg=name):
                B.step_text([B.Body(name, slabs)], name)
            with self.assertRaises(B.BrepError, msg=name):
                B.mesh(B.Body(name, slabs))
        with self.assertRaises(B.BrepError) as cm:
            B.check(B.Body('presque', bad['presque']))
        self.assertIn('presque alignées', str(cm.exception))

    def test_earlier_parts_unchanged(self):
        b = G.build('plaque', G.values('plaque', hole='lamage'))[0]
        self.assertEqual(B.check(b), set())                               # pas de paroi alignée : rien ne change
        gear = G.build('engrenage', G.values('engrenage'))[0]
        self.assertEqual(B.check(gear), set())


class TestGenerators(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmp.cleanup()

    def written(self, key, v):
        bodies = G.build(key, v)
        p = os.path.join(self._tmp.name, f'{key}.step')
        G.write(key, v, p)
        with open(p, encoding='latin-1') as f:
            text = f.read()
        self.assertEqual(len(topology(text)), 1, key)
        self.assertEqual(geometry_errors(text), [], key)
        self.assertEqual(misoriented(text, lambda q: B.contains(bodies[0], q)), [], key)
        return bodies[0]

    def test_heel_clamp(self):
        v = G.values('bride', heel=15.0)
        b = self.written('bride', v)
        self.assertEqual(b.name, 'Bride 100x30x15 M10 talon 15')
        self.assertEqual(placed_bounds(b), [0, -15, 0, 100, 15, 30])
        w = G.CLEARANCE['M10']
        slot = (40 - w) * w + math.pi * (w / 2) ** 2
        self.assertAlmostEqual(mesh_volume(b) / ((100 * 30 - slot) * 15 + 15 * 30 * 15), 1.0, delta=0.002)
        self.assertIn('_talon15x15', G.file_name('bride', v))
        self.assertNotIn('talon', G.file_name('bride', G.values('bride')))  # bride plate : nom d'avant
        with self.assertRaises(G.GenError):
            G.build('bride', G.values('bride', heel=15.0, heel_length=40.0))   # sous la lumière

    def test_stepped_jaw(self):
        v = G.values('mors_doux', step_depth=5.0, step_height=8.0)
        b = self.written('mors_doux', v)
        self.assertEqual(placed_bounds(b), [0, 0, 0, 150, 40, 20])
        prof = G._hole_profile('lamage', 'M8', 20.0)
        holes = 2 * sum(math.pi * c.r ** 2 * (z1 - z0) for z0, z1, c in prof)
        self.assertAlmostEqual(mesh_volume(b) / (150 * 40 * 20 - 150 * 8 * 5 - holes), 1.0, delta=0.002)
        for over in ({'step_depth': 5.0}, {'step_depth': 5.0, 'step_height': 8.0, 'hole_y': 30.0},
                     {'step_depth': 25.0, 'step_height': 5.0}):
            with self.assertRaises(G.GenError, msg=over):
                G.build('mors_doux', G.values('mors_doux', **over))
        from vectordrive.core import screwfit as F
        from vectordrive.io.neostep import step3d
        p = os.path.join(self._tmp.name, 'mors.step')
        G.write('mors_doux', v, p)
        m = step3d.lire_modele(p, axe_haut='Z')
        T, fo, infos = np.asarray(m.triangles, float).reshape(-1, 3, 3), np.asarray(m.face_de), list(m.faces)
        face = next(f for f, k in enumerate(infos) if k.get('genre') == 'cylindre' and k.get('creux')
                    and abs(k['rayon'] - G.CLEARANCE['M8'] / 2) < 1e-6)
        self.assertEqual(F.analyse(T, fo, infos, face).kind, 'lamage')    # toujours lamés malgré l'épaulement

    def test_t_nut(self):
        b = self.written('ecrou_t', G.values('ecrou_t'))
        self.assertEqual(b.name, 'Ecrou T 14 M12')
        self.assertEqual(placed_bounds(b), [-11, -11, 0, 11, 11, 16])
        r = (12 - G.PITCH['M12']) / 2
        self.assertAlmostEqual(mesh_volume(b) / (22 * (22 * 8 + 14 * 8) - math.pi * r * r * 16), 1.0, delta=0.002)
        for over in ({'size': 'M20'}, {'a': 22.0}, {'k': 16.0}):
            with self.assertRaises(G.GenError, msg=over):
                G.build('ecrou_t', G.values('ecrou_t', **over))
        self.assertEqual([k for k, f in G.FAMILIES.items() if f.category == 'Bridage'][:5],
                         ['bride', 'cale_etagee', 'mors_doux', 'goujon', 'ecrou_t'])


if __name__ == '__main__':
    unittest.main()
