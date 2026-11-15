"""Round 673 : pièces STEP en vraies faces (`core.brep` : solides étagés
d'axe Z, plans, cylindres, cônes, sphères) et générateurs (`core.stepgen` :
visserie ISO, rondelles, goupilles, roulements, clavettes, roues dentées,
barres et profilés, plaques percées, entretoises, bagues, éléments de
moule). Chaque fichier écrit est contrôlé sans le lecteur : chaque arête
d'une coque fermée bordée par deux faces en sens opposés, Euler-Poincaré,
et chaque face orientée vers l'extérieur (matière derrière sa normale)."""
import math
import os
import re
import tempfile
import unittest
from collections import defaultdict

from vectordrive.core import brep as B
from vectordrive.core import stepgen as G

ENT = re.compile(r'#(\d+)\s*=\s*([A-Z_0-9]+)\s*\((.*)\)\s*;')


def _entities(text):
    e = {}
    for line in text.splitlines():
        m = ENT.match(line.strip())
        if m:
            e[int(m.group(1))] = (m.group(2), m.group(3))
    return e


def _refs(s):
    return [int(x) for x in re.findall(r'#(\d+)', s)]


def _nums(s):
    return [float(x) for x in re.findall(r'(?<![#\w])-?\d+\.?\d*(?:[eE][-+]?\d+)?', s)]


def topology(text):
    """Par coque : (faces, arêtes, sommets, boucles intérieures, arêtes mal bordées)."""
    e = _entities(text)
    out = []
    for t, a in e.values():
        if t != 'CLOSED_SHELL':
            continue
        use, verts, holes = defaultdict(list), set(), 0
        faces = _refs(a)
        for f in faces:
            for bd in _refs(e[f][1].split(')')[0]):
                tb, ab = e[bd]
                holes += tb == 'FACE_BOUND'
                for oe in _refs(e[_refs(ab)[0]][1]):
                    ec = _refs(e[oe][1])[-1]
                    use[ec].append(e[oe][1].strip().endswith('.T.') == ab.strip().endswith('.T.'))
                    verts.update(_refs(e[ec][1])[:2])
        bad = [ec for ec, u in use.items() if sorted(u) != [False, True]]
        out.append((len(faces), len(use), len(verts), holes, bad))
    return out


def _sub(a, b):
    return [a[i] - b[i] for i in range(3)]


def _dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _unit(a):
    n = math.sqrt(_dot(a, a)) or 1.0
    return [c / n for c in a]


class _Step:
    """Lecture des entités écrites par core.brep : points, repères, arêtes, surfaces."""

    def __init__(self, text):
        self.e = _entities(text)

    def point(self, r):
        return _nums(self.e[r][1])[:3]

    def vertex(self, r):
        return self.point(_refs(self.e[r][1])[0])

    def axis(self, r):
        p, n, x = _refs(self.e[r][1])
        return self.point(p), _nums(self.e[n][1])[:3], _nums(self.e[x][1])[:3]

    def edge(self, oe):
        """(début, fin, points de l'arête dans le sens du parcours, tangente au milieu) d'un ORIENTED_EDGE."""
        e = self.e
        fwd = e[oe][1].strip().endswith('.T.')
        ec = _refs(e[oe][1])[-1]
        v1, v2, cu = _refs(e[ec][1])[:3]
        p1, p2 = self.vertex(v1), self.vertex(v2)
        if e[cu][0] == 'LINE':
            lp = self.point(_refs(e[cu][1])[0])
            d = _unit(_nums(e[_refs(e[_refs(e[cu][1])[1]][1])[0]][1])[:3])
            off = max(math.sqrt(_dot(_cross(_sub(p, lp), d), _cross(_sub(p, lp), d))) for p in (p1, p2))
            pts = [p1, [(p1[i] + p2[i]) / 2 for i in range(3)], p2]
            tg = _unit(_sub(p2, p1))
        else:
            c, n, x = self.axis(_refs(e[cu][1])[0])
            r = _nums(e[cu][1].split(',', 1)[1])[-1]
            y = _cross(n, x)
            off = max(max(abs(math.sqrt(_dot(_sub(p, c), _sub(p, c))) - r), abs(_dot(_sub(p, c), n))) for p in (p1, p2))
            t1 = math.atan2(_dot(_sub(p1, c), y), _dot(_sub(p1, c), x))
            t2 = math.atan2(_dot(_sub(p2, c), y), _dot(_sub(p2, c), x))
            span = (t2 - t1) % (2 * math.pi) or 2 * math.pi
            pts = [[c[i] + r * (math.cos(t1 + span * k / 4) * x[i] + math.sin(t1 + span * k / 4) * y[i]) for i in range(3)]
                   for k in range(5)]
            tm = t1 + span / 2
            tg = [-math.sin(tm) * x[i] + math.cos(tm) * y[i] for i in range(3)]
        if not fwd:
            v1, v2, pts, tg = v2, v1, pts[::-1], [-v for v in tg]
        return v1, v2, pts, tg, off

    def surface(self, face):
        """(distance d'un point à la surface, normale de la face en un point) de l'ADVANCED_FACE."""
        a = self.e[face][1]
        st, sa = self.e[_refs(a.split(')')[1])[0]]
        c, ax, _x = self.axis(_refs(sa)[0])
        parts = sa.split(',', 2)                                         # nom, repère, rayon (, angle)
        nums = _nums(parts[2]) if len(parts) > 2 else []
        same = a.strip().endswith('.T.')

        def dist(p):
            d = _sub(p, c)
            h = _dot(d, ax)
            rho = math.sqrt(max(0.0, _dot(d, d) - h * h))
            if st == 'PLANE':
                return abs(h)
            if st == 'CYLINDRICAL_SURFACE':
                return abs(rho - nums[0])
            if st == 'CONICAL_SURFACE':
                return abs(rho - (nums[0] + h * math.tan(nums[1]))) * math.cos(nums[1])
            return abs(math.sqrt(_dot(d, d)) - nums[0])

        def normal(p):
            d = _sub(p, c)
            if st == 'PLANE':
                n = ax
            elif st == 'SPHERICAL_SURFACE':
                n = _unit(d)
            else:
                rho = _unit([d[i] - _dot(d, ax) * ax[i] for i in range(3)])
                n = rho if st == 'CYLINDRICAL_SURFACE' else \
                    [rho[i] * math.cos(nums[1]) - ax[i] * math.sin(nums[1]) for i in range(3)]
            return _unit(n if same else [-v for v in n])
        return st, dist, normal

    def loops(self, face):
        return [(self.e[b][0], [oe for oe in _refs(self.e[_refs(self.e[b][1])[0]][1])])
                for b in _refs(self.e[face][1].split(')')[0])]

    def faces(self):
        return [k for k, (t, _a) in self.e.items() if t == 'ADVANCED_FACE']


def geometry_errors(text, tol=1e-6):
    """Sommets hors de leur courbe, arêtes hors de la surface de leur face, boucles mal enchaînées."""
    S = _Step(text)
    bad = []
    for f in S.faces():
        st, dist, _n = S.surface(f)
        for _kind, oes in S.loops(f):
            ends = []
            for oe in oes:
                v1, v2, pts, _tg, off = S.edge(oe)
                if off > tol:
                    bad.append((f, st, 'sommet hors de sa courbe'))
                if max(dist(p) for p in pts) > tol:
                    bad.append((f, st, 'arête hors de la surface'))
                ends.append((v1, v2))
            for (a1, b1), (a2, b2) in zip(ends, ends[1:] + ends[:1]):
                if b1 != a2:
                    bad.append((f, st, 'boucle mal enchaînée'))
    return bad


def misoriented(text, contains, delta=0.02, eps=0.01):
    """Faces dont la normale ne regarde pas le vide : au milieu de chaque arête du contour extérieur, un point
    juste dans la face (à gauche de l'arête vue de la normale) ; une sonde au moins doit trouver la matière
    derrière la normale et le vide devant (les autres peuvent sortir par une face voisine)."""
    S = _Step(text)
    bad = []
    for f in S.faces():
        st, _dist, normal = S.surface(f)
        outer = next(oes for kind, oes in S.loops(f) if kind == 'FACE_OUTER_BOUND')
        ok = False
        for oe in outer:
            _v1, _v2, pts, tg, _off = S.edge(oe)
            m = pts[len(pts) // 2]
            nrm = normal(m)
            q = [m[i] + delta * _cross(nrm, tg)[i] for i in range(3)]
            if not contains([q[i] + eps * nrm[i] for i in range(3)]) and contains([q[i] - eps * nrm[i] for i in range(3)]):
                ok = True
                break
        if not ok:
            bad.append((f, st))
    return bad


class SolidCase(unittest.TestCase):
    def assertSolid(self, bodies, msg=''):
        """Coques fermées, Euler juste (genre donné par les trous traversants), faces vers l'extérieur."""
        text = B.step_text(bodies, 'essai')
        shells = topology(text)
        self.assertEqual(len(shells), len(bodies), msg)
        for (f, ed, v, h, bad) in shells:
            self.assertEqual(bad, [], msg)
            self.assertEqual((v - ed + f - h) % 2, 0, msg)             # 2 (1 - genre)
            self.assertLessEqual(v - ed + f - h, 2, msg)
        self.assertEqual(geometry_errors(text), [], msg)
        self.assertEqual(misoriented(text, lambda p: any(B.contains(b, p) for b in bodies)), [], msg)
        return text


CASES = {
    'cylindre': B.Body('cyl', [B.Slab(0, 10, [B.Circle(0, 0, 5)])]),
    'cone': B.Body('cone', [B.Slab(0, 10, [B.Circle(0, 0, 5, 2)])]),
    'cone_inv': B.Body('cone2', [B.Slab(0, 10, [B.Circle(0, 0, 2, 5)])]),
    'bague': B.Body('bague', [B.Slab(0, 8, [B.Circle(0, 0, 10), B.Circle(0, 0, 4)])]),
    'ecrou': B.Body('ecrou', [B.Slab(0, 5, [B.polygon(6, 10), B.Circle(0, 0, 3)])]),
    'chanfrein': B.revolve([(0, 2.5), (0.5, 3), (10, 3), (10, 5), (13.5, 5), (14, 4.5)], 'ch'),
    'empreinte': B.add_loop(B.revolve([(0, 5), (6, 5)], 'chc'), 3, 6, B.polygon(6, 5)),
    'dome': B.Body('dome', [B.Slab(0, 3, [B.Circle(0, 0, 5, sphere=(-1, math.sqrt(26)))])]),
    'pyramide': B.Body('pyr', [B.Slab(0, 4, [B.Poly([(-5, -5), (5, -5), (5, 5), (-5, 5)], scale_top=0.5)])]),
    'plaque': B.Body('plaque', [B.Slab(0, 6, [B.rounded_rect(0, 0, 60, 40, 5), B.Circle(10, 10, 3), B.Circle(50, 30, 3)]),
                                B.Slab(6, 10, [B.rounded_rect(0, 0, 60, 40, 5), B.Circle(10, 10, 5.5),
                                               B.Circle(50, 30, 3, 5)])]),
    'oblong': B.Body('cl', [B.Slab(0, 5, [B.slot(0, 0, 30, 8, 30)])]),
    'ilot': B.Body('ilot', [B.Slab(0, 4, [B.rounded_rect(0, 0, 40, 40, 3), B.rounded_rect(5, 5, 35, 35, 2),
                                          B.Circle(20, 20, 6)])]),
    'place': B.Body('pl', [B.Slab(0, 10, [B.Circle(0, 0, 5)])],
                    matrix=B.compose(B.translation(10, 20, 30), B.placement((0, 0, 0), (1, 1, 0)))),
}


class TestBrep(SolidCase):
    def test_closed_and_outward(self):
        for k, b in CASES.items():
            self.assertSolid([b], k)

    def test_euler_genus(self):
        f, ed, v, h, _bad = topology(B.step_text([CASES['plaque']], 'p'))[0]
        self.assertEqual(v - ed + f - h, -2)                            # deux trous traversants : genre 2
        f, ed, v, h, _bad = topology(B.step_text([CASES['cylindre']], 'c'))[0]
        self.assertEqual((f, ed, v, h), (4, 6, 4, 0))                   # cercles en deux demi-arcs, couture

    def test_checker_sees_a_flipped_face(self):
        text = B.step_text([CASES['bague']], 'b')
        lines = text.split('\n')
        i = next(i for i, ln in enumerate(lines) if 'ADVANCED_FACE' in ln)
        lines[i] = lines[i].replace(',.T.);', ',.F.);') if lines[i].endswith(',.T.);') else lines[i].replace(',.F.);', ',.T.);')
        self.assertTrue(misoriented('\n'.join(lines), lambda p: B.contains(CASES['bague'], p)))

    def test_checker_sees_wrong_surfaces(self):
        for case, old in (('cylindre', 'CYLINDRICAL_SURFACE'), ('cone', 'CONICAL_SURFACE')):
            text = B.step_text([CASES[case]], case)
            lines = text.split('\n')
            i = next(i for i, ln in enumerate(lines) if old in ln)
            if old == 'CYLINDRICAL_SURFACE':                              # rayon 5 → 50
                lines[i] = lines[i].replace(',5.)', ',50.)')
            else:                                                         # rayon de départ du cône faussé
                parts = lines[i].split(',')
                parts[-2] = '7.'
                lines[i] = ','.join(parts)
            self.assertNotEqual(lines[i], text.split('\n')[i])
            self.assertTrue(geometry_errors('\n'.join(lines)), case)

    def test_bowl_probe(self):
        b = B.Body('bol', [B.Slab(0, 4, [B.rounded_rect(-10, -10, 10, 10, 2), B.Circle(1, 1, 3, sphere=(4.5, 5))])])
        b.slabs[0].loops[1] = B.Circle(1, 1, b.slabs[0].loops[1].radius(0, 0, 4), sphere=(4.5, 5))
        self.assertSolid([b])                                             # sondes prises sur chaque arête

    def test_volumes(self):
        V = B.volume
        self.assertAlmostEqual(V(CASES['cylindre']), math.pi * 250, 6)
        self.assertAlmostEqual(V(CASES['cone']), math.pi * 10 * (25 + 10 + 4) / 3, 6)
        self.assertAlmostEqual(V(CASES['bague']), math.pi * (100 - 16) * 8, 6)
        self.assertAlmostEqual(V(CASES['pyramide']), 4 * (100 + 50 + 25) / 3, 6)
        self.assertAlmostEqual(V(CASES['dome']), math.pi * (26 * 3 - (4 ** 3 - 1) / 3), 6)   # ∫ π (R² - (z + 1)²)
        self.assertAlmostEqual(V(CASES['oblong']), 5 * (22 * 8 + math.pi * 16), 6)

    def test_contains_placed(self):
        b = CASES['place']
        self.assertTrue(B.contains(b, (10, 20, 30)) is False)          # sur la face du bas : hors de la matière
        d = 1 / math.sqrt(2)
        self.assertTrue(B.contains(b, (10 + 5 * d, 20 + 5 * d, 30)))  # 5 mm le long de l'axe (1, 1, 0)
        self.assertFalse(B.contains(b, (10, 20, 35)))
        M = B.compose(B.translation(1, 2, 3), B.rotation_z(30))
        P = B.compose(B.inverse(M), M)
        for i in range(4):
            for j in range(4):
                self.assertAlmostEqual(P[i][j], 1.0 if i == j else 0.0, 9)

    def test_check_refuses(self):
        bad = [B.Body('a', []), B.Body('b', [B.Slab(0, 0, [B.Circle(0, 0, 1)])]),
               B.Body('c', [B.Slab(0, 1, [B.Circle(0, 0, 1, 0)])]),
               B.Body('d', [B.Slab(0, 1, [B.Poly([(0, 0), (1, 0), (1, 1)], [0.5, 0, 0], 0.5)])]),
               B.Body('e', [B.Slab(0, 1, [B.Circle(0, 0, 1)])], matrix=[[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]]),
               B.Body('f', [B.Slab(0, 2, [B.Circle(0, 0, 1)]), B.Slab(1, 3, [B.Circle(0, 0, 1)])]),
               B.Body('g', [B.Slab(0, 1, [B.Circle(0, 0, 1)]), B.Slab(2, 3, [B.Circle(0, 0, 1)])]),
               B.Body('h', [B.Slab(0, 1, [B.Circle(0, 0, 5), B.Circle(4, 0, 2)])]),                 # trou qui coupe le bord
               B.Body('i', [B.Slab(0, 1, [B.Circle(0, 0, 5), B.Circle(5, 0, 2)])]),
               B.Body('j', [B.Slab(0, 1, [B.Circle(0, 0, 5)]), B.Slab(1, 2, [B.Circle(3, 0, 5)])]),  # tranches croisées
               B.Body('k', [B.Slab(0, 1, [B.Circle(0, 0, 3, sphere=(5, 5))])]),                    # rayon hors sphère
               B.Body('l', [B.Slab(0, 1, [B.Circle(0, 0, 1)])], matrix=[[2, 0, 0, 0], [0, 2, 0, 0], [0, 0, 2, 0],
                                                                       [0, 0, 0, 1]]),
               B.Body('m', [B.Slab(5, 6, [B.Circle(0, 0, 1)]), B.Slab(6 + 4e-7, 7, [B.Circle(0, 0, 1)])])]
        for b in bad:
            with self.assertRaises(B.BrepError, msg=b.name):
                B.step_text([b], 'x')

    def test_review_cases(self):
        tri = B.Body('tri', [B.Slab(0, 10, [B.Poly([(0, 0), (10, 0), (0, 10)], scale_top=0.5, center=(0, 0))])])
        v = B.volume(tri)
        cut = B.cut(tri, 5)
        self.assertAlmostEqual(B.volume(cut), v, 6)                       # tronc recoupé : même volume
        self.assertSolid([cut])
        flat = B.Body('plat', [B.Slab(0, 2, [B.Poly([(0, 0), (10, 0), (10, 10), (0, 10)], [1e-10, 0, 0, 0])])])
        self.assertSolid([flat])                                          # arc presque plat : un segment
        for x1, y1, n in ((40, 20, 6), (20, 20, 4)):                      # coins jusqu'à la demi-largeur
            lp = B.rounded_rect(0, 0, x1, y1, 50)
            self.assertEqual(len(lp.pts), n)                              # côtés nuls retirés
            self.assertAlmostEqual(B.loop_area(lp, 0, 0, 1), (x1 - y1) * y1 + math.pi * (y1 / 2) ** 2, 6)
            self.assertSolid([B.Body('o', [B.Slab(0, 3, [lp])])])
        import time
        t0 = time.perf_counter()
        B.step_text(G.build('engrenage', G.values('engrenage', teeth=120)), 'r')
        B.step_text(G.build('plaque', G.values('plaque', pattern='grille', length=400, width=400, nx=25, ny=25,
                                               size='M3', hole='passage')), 'p')
        self.assertLess(time.perf_counter() - t0, 20)                     # sans coût quadratique

    def test_several_bodies_named_and_coloured(self):
        a = B.Body('Axe', [B.Slab(0, 10, [B.Circle(0, 0, 2)])], (1.0, 0.0, 0.0))
        b = B.Body('Bague', [B.Slab(0, 4, [B.Circle(0, 0, 5), B.Circle(0, 0, 2.5)])], (0.0, 0.0, 1.0))
        text = self.assertSolid([a, b])
        self.assertIn("MANIFOLD_SOLID_BREP('Axe'", text)
        self.assertIn("MANIFOLD_SOLID_BREP('Bague'", text)
        self.assertEqual(text.count('COLOUR_RGB'), 2)
        self.assertEqual(text.count("STYLED_ITEM('color'"), text.count('ADVANCED_FACE'))

    def test_read_back(self):
        from vectordrive.io import model3d
        b = CASES['plaque']
        p = os.path.join(tempfile.mkdtemp(), 'plaque.step')
        B.write(p, [b], 'plaque')
        m = model3d.from_step(p)
        self.assertEqual(m.body_names, ['plaque'])
        with open(p, encoding='ascii') as f:
            self.assertEqual(len(m.face_kinds), f.read().count('ADVANCED_FACE'))
        holes = [f for f in m.face_kinds if f.get('genre') == 'cylindre' and f.get('creux')]
        self.assertEqual(sorted(round(f['rayon'], 3) for f in holes), [3.0, 3.0, 3.0, 3.0, 5.5, 5.5])
        lo, hi = m.triangles.reshape(-1, 3).min(axis=0), m.triangles.reshape(-1, 3).max(axis=0)
        self.assertEqual([round(float(x), 3) for x in lo], [0, 0, 0])
        self.assertEqual([round(float(x), 3) for x in hi], [60, 40, 10])


class TestStepgen(SolidCase):
    def test_every_family(self):
        self.assertEqual(set(f.category for f in G.FAMILIES.values()), set(G.CATEGORIES))
        for key, f in G.FAMILIES.items():
            v = G.values(key)
            bodies = G.build(key, v)
            self.assertSolid(bodies, key)
            self.assertGreater(B.volume(bodies[0]), 0, key)
            name = G.file_name(key, v)
            self.assertRegex(name, r'^[A-Za-z0-9_.x-]+$', key)

    def test_series_ends(self):
        for key, f in G.FAMILIES.items():
            if f.series is None:
                continue
            items = f.series()
            self.assertTrue(items, key)
            names = set()
            for over in (items[0], items[len(items) // 2], items[-1]):
                v = G.values(key, **over)
                self.assertSolid(G.build(key, v), f'{key} {over}')
            for over in items:
                names.add(G.file_name(key, G.values(key, **over)))
            self.assertEqual(len(names), len(items), key)                # un fichier par pièce

    def test_variants(self):
        for shape in ('rond', 'tube', 'carre', 'plat', 'six_pans', 'tube_carre', 'corniere', 'u'):
            self.assertSolid(G.build('barre', G.values('barre', shape=shape, a=20, b=8, e=2)), shape)
        for pattern in ('aucun', 'coins', 'grille', 'centre'):
            for hole in ('passage', 'lamage', 'fraisure', 'taraude'):
                v = G.values('plaque', pattern=pattern, hole=hole, size='M5', corner=4)
                self.assertSolid(G.build('plaque', v), f'{pattern} {hole}')
        self.assertSolid(G.build('entretoise', G.values('entretoise', shape='ronde', size='M5', D=9)))
        self.assertSolid(G.build('engrenage', G.values('engrenage', module=2.0, teeth=12, bore=0)))
        self.assertSolid(G.build('bague', G.values('bague', chamfer=0)))

    def test_dimensions(self):
        def bounds(key, **over):
            b = G.build(key, G.values(key, **over))[0]
            return tuple(round(x, 3) for x in b.bounds())
        self.assertEqual(bounds('chc', size='M6', length=20), (-5, -5, -20, 5, 5, 6))    # sous tête en Z = 0
        x0, y0, z0, x1, y1, z1 = bounds('fhc', size='M6', length=20)
        self.assertEqual((z0, z1, x1), (-20, 0, 6.72))                                  # dessus de la tête en 0
        self.assertEqual(bounds('ecrou', size='M8')[5], 6.8)
        self.assertEqual(bounds('roulement', ref='608'), (-11, -11, 0, 11, 11, 7))
        self.assertAlmostEqual(B.volume(G.build('rondelle', G.values('rondelle', size='M6'))[0]),
                               math.pi * (36 - 3.2 ** 2) * 1.6, 6)
        x0, y0, z0, x1, y1, z1 = bounds('engrenage', module=1.0, teeth=30, width=10, bore=8)
        self.assertAlmostEqual(max(x1, y1), 16.0, 2)                                    # tête : m (z + 2) / 2

    def test_values_checked(self):
        with self.assertRaises(G.GenError):
            G.values('chc', size='M7')
        with self.assertRaises(G.GenError):
            G.values('chc', length=1000)
        self.assertEqual(G.values('engrenage', teeth='24')['teeth'], 24)
        with self.assertRaises(G.GenError):
            G.build('plaque', G.values('plaque', pattern='grille', nx=20, size='M10', hole='lamage'))   # trous qui se touchent
        with self.assertRaises(G.GenError):
            G.build('engrenage', G.values('engrenage', teeth=10, bore=10))
        for over in ({'teeth': 'abc'}, {'teeth': 8.9}, {'tooth': 99}):
            with self.assertRaises(G.GenError, msg=over):
                G.values('engrenage', **over)
        with self.assertRaisesRegex(G.GenError, 'coin arrondi'):           # trou lamé dans un coin de 25
            G.build('plaque', G.values('plaque', corner=25))
        self.assertSolid(G.build('plaque', G.values('plaque', corner=12)))
        with self.assertRaisesRegex(G.GenError, 'trop courte'):
            G.build('fhc', G.values('fhc', size='M20', length=12))
        names = {G.file_name('engrenage', G.values('engrenage', bore=b)) for b in (8, 12)}
        self.assertEqual(len(names), 2)                                    # l'alésage dans le nom

    def test_write_and_series(self):
        from vectordrive.io import model3d
        d = tempfile.mkdtemp()
        p = G.write('chc', G.values('chc', size='M4', length=12), os.path.join(d, 'vis.step'))
        m = model3d.from_step(p)
        self.assertEqual(m.body_names, ['Vis CHC ISO 4762 M4x12'])
        with open(p, encoding='ascii') as f:
            text = f.read()
        self.assertIn("FILE_DESCRIPTION(('Vis CHC (tete cylindrique six pans creux) ISO 4762')", text)
        files = G.write_series('ecrou', os.path.join(d, 'ecrous'))
        self.assertEqual(len(files), len(G.ISO4032))
        self.assertTrue(all(os.path.getsize(f) > 0 for f in files))
        seen = []
        files = G.write_series('rondelle', os.path.join(d, 'r'), progress=lambda i, n: seen.append((i, n)) or i < 2)
        self.assertEqual(len(files), 2)                                   # arrêtée par la progression
        self.assertEqual(seen[-1], (2, len(G.ISO7089)))
        with self.assertRaises(G.GenError):
            G.write_series('plaque', d)                                    # pas de gamme


if __name__ == '__main__':
    unittest.main()
