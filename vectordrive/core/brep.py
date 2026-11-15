"""Pièces en vraies faces (B-rep), écrites en STEP AP214 : solides « étagés »
d'axe Z, que tout logiciel de CAO ouvre avec leurs plans, cylindres, cônes
et sphères (générateurs de `core.stepgen`).

Un corps (`Body`) est une pile de tranches (`Slab`) entre deux cotes ; la
section d'une tranche est faite de boucles fermées — contour extérieur,
trous, îlots — rangées par emboîtement (pair : matière dedans) :

- `Circle` : cercle de centre fixe ; rayon constant (cylindre), qui varie
  linéairement (`r_top` : cône) ou sur une sphère (`sphere=(zc, R)`) ;
- `Poly` : polygone, segments et arcs (`bulges`, comme le DXF : tan(θ/4),
  positif dans le sens direct) ; constant, ou sans arcs mis à l'échelle
  `scale_top` autour de `center` (tronc de pyramide, faces planes).

Les faces horizontales (dessus, dessous, épaulements, fonds de poche) se
calculent d'une tranche à l'autre : la matière d'en dessous sans celle
d'au-dessus regarde vers le haut, l'inverse vers le bas. Les boucles de deux
tranches voisines sont identiques, l'une dans l'autre, ou se touchent sur
des segments droits communs (parois alignées : talon, épaulement, tenon —
les parois y sont coupées aux sommets de l'autre tranche) ; jamais croisées,
ni touchées en un point ; les boucles d'une même tranche ne se coupent pas.

Un corps se place par une matrice 4 × 4 (`matrix`, sans symétrie) : les
générateurs le décrivent debout sur l'axe Z, les assemblages le posent.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

EPS = 1e-6
TWO_PI = 2.0 * math.pi
#: en dessous, un « bulge » est un segment (rayon démesuré, extrémités recalculées trop loin)
BULGE_MIN = 1e-6
#: tolérance des cotes de tranches (mêmes nombres d'une tranche à l'autre)
Z_TOL = 1e-9
GREY = (0.62, 0.64, 0.68)


class BrepError(ValueError):
    pass


# --- sections -------------------------------------------------------------------------------------------
@dataclass
class Circle:
    cx: float
    cy: float
    r: float
    r_top: float | None = None          # rayon en haut de la tranche : cône (None : cylindre)
    sphere: tuple | None = None         # (zc, R) : sur la sphère de centre (cx, cy, zc)

    def radius(self, z: float, z0: float, z1: float) -> float:
        if self.sphere is not None:
            zc, R = self.sphere
            return math.sqrt(max(0.0, R * R - (z - zc) ** 2))
        if self.r_top is None or z1 - z0 < EPS:
            return self.r
        return self.r + (self.r_top - self.r) * (z - z0) / (z1 - z0)

    def varies(self) -> bool:
        return self.sphere is not None or (self.r_top is not None and abs(self.r_top - self.r) > EPS)


@dataclass
class Poly:
    pts: list
    bulges: list | None = None          # par sommet, vers le suivant (0 : segment)
    scale_top: float = 1.0              # en haut de la tranche, mis à l'échelle autour de `center`
    center: tuple = (0.0, 0.0)

    def at(self, z: float, z0: float, z1: float) -> list:
        if abs(self.scale_top - 1.0) < EPS or z1 - z0 < EPS:
            return [(float(x), float(y)) for x, y in self.pts]
        s = 1.0 + (self.scale_top - 1.0) * (z - z0) / (z1 - z0)
        cx, cy = self.center
        return [(cx + (x - cx) * s, cy + (y - cy) * s) for x, y in self.pts]

    def varies(self) -> bool:
        return abs(self.scale_top - 1.0) > EPS


@dataclass
class Slab:
    z0: float
    z1: float
    loops: list


@dataclass
class Body:
    name: str
    slabs: list
    color: tuple = GREY
    matrix: list | None = None          # 4 × 4, lignes ; None : identité

    def bounds(self):
        """(x0, y0, z0, x1, y1, z1) avant placement."""
        xs, ys = [], []
        for s in self.slabs:
            for lp in s.loops:
                for z in (s.z0, s.z1):
                    for p in _level_points(lp, z, s.z0, s.z1):
                        xs.append(p[0])
                        ys.append(p[1])
        return (min(xs), min(ys), min(s.z0 for s in self.slabs), max(xs), max(ys), max(s.z1 for s in self.slabs))


# --- géométrie 2D d'une boucle à une cote ---------------------------------------------------------------
def _bulge_arc(a, b, bulge):
    """(centre, rayon, angle de départ, angle d'arrivée) de l'arc de a à b, sens direct si bulge > 0."""
    th = 4.0 * math.atan(bulge)
    dx, dy = b[0] - a[0], b[1] - a[1]
    c = math.hypot(dx, dy)
    r = c / (2.0 * math.sin(abs(th) / 2.0))
    mx, my = (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0
    h = r * math.cos(abs(th) / 2.0) * (1.0 if abs(th) < math.pi else -1.0)
    nx, ny = -dy / c, dx / c                          # à gauche de a → b
    sgn = 1.0 if bulge > 0 else -1.0
    cx, cy = mx + sgn * nx * h, my + sgn * ny * h
    return (cx, cy), r, math.atan2(a[1] - cy, a[0] - cx), math.atan2(b[1] - cy, b[0] - cx)


def _segments(lp, z, z0, z1) -> list:
    """Segments de la boucle à la cote z : ('line', a, b) ou ('arc', centre, r, a0, a1, sens) avec
    sens +1 (direct) ou -1, dans le sens de parcours de la boucle ; un cercle : deux demi-arcs."""
    if isinstance(lp, Circle):
        r = lp.radius(z, z0, z1)
        c = (lp.cx, lp.cy)
        return [('arc', c, r, 0.0, math.pi, 1), ('arc', c, r, math.pi, TWO_PI, 1)]
    pts = lp.at(z, z0, z1)
    bl = list(lp.bulges or [0.0] * len(pts))
    out = []
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        if abs(bl[i]) < BULGE_MIN:
            out.append(('line', a, b))
        else:
            c, r, a0, a1 = _bulge_arc(a, b, bl[i])
            sens = 1 if bl[i] > 0 else -1
            if sens > 0 and a1 <= a0:
                a1 += TWO_PI
            if sens < 0 and a1 >= a0:
                a1 -= TWO_PI
            out.append(('arc', c, r, a0, a1, sens))
    return out


def _seg_points(sg, n_arc: int = 24) -> list:
    if sg[0] == 'line':
        return [sg[1]]
    _k, c, r, a0, a1, _s = sg
    n = max(2, int(n_arc * abs(a1 - a0) / TWO_PI) + 2)
    return [(c[0] + r * math.cos(a0 + (a1 - a0) * i / n), c[1] + r * math.sin(a0 + (a1 - a0) * i / n))
            for i in range(n)]


def _level_points(lp, z, z0, z1, n_arc: int = 48) -> list:
    pts = []
    for sg in _segments(lp, z, z0, z1):
        pts += _seg_points(sg, n_arc)
    return pts


def _area(pts) -> float:
    return 0.5 * sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
                     for i in range(len(pts)))


def _inside(p, pts) -> bool:
    x, y = p
    ins = False
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            ins = not ins
    return ins


def loop_area(lp, z: float, z0: float, z1: float) -> float:
    """Aire (positive) du disque ou du polygone (arcs compris) à la cote z."""
    if isinstance(lp, Circle):
        return math.pi * lp.radius(z, z0, z1) ** 2
    a = 0.0
    for sg in _segments(lp, z, z0, z1):
        if sg[0] == 'line':
            (x0, y0), (x1, y1) = sg[1], sg[2]
            a += 0.5 * (x0 * y1 - x1 * y0)
        else:
            _k, (cx, cy), r, a0, a1, _s = sg
            a += 0.5 * (r * r * (a1 - a0) + cx * r * (math.sin(a1) - math.sin(a0))
                        - cy * r * (math.cos(a1) - math.cos(a0)))
    return abs(a)


# --- volume exact (essais, propriétés) ---------------------------------------------------------------
def _bbox(pts) -> tuple:
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def _in_box(p, bb) -> bool:
    return bb[0] <= p[0] <= bb[2] and bb[1] <= p[1] <= bb[3]


def _depths(loops, z, z0, z1) -> list:
    polys = [_level_points(lp, z, z0, z1) for lp in loops]
    boxes = [_bbox(p) for p in polys]
    return [sum(1 for j, q in enumerate(polys) if j != i and _in_box(p[0], boxes[j]) and _inside(p[0], q))
            for i, p in enumerate(polys)]


def volume(body: Body, steps: int = 64) -> float:
    """Volume du corps (mm³) : aire de la section intégrée en Z (Simpson ;
    exact pour les cylindres, cônes, sphères et troncs de pyramide)."""
    v = 0.0
    for s in body.slabs:
        h = s.z1 - s.z0
        if h < EPS:
            continue
        depth = _depths(s.loops, (s.z0 + s.z1) / 2.0, s.z0, s.z1)

        def area(z):
            return sum((1 if d % 2 == 0 else -1) * loop_area(lp, z, s.z0, s.z1)
                       for lp, d in zip(s.loops, depth))
        n = 2 if not any(lp.varies() for lp in s.loops) else steps
        acc = area(s.z0) + area(s.z1)
        for i in range(1, n):
            acc += (4 if i % 2 else 2) * area(s.z0 + h * i / n)
        v += acc * h / (3 * n)
    return v


def inverse(m: list) -> list:
    """Inverse d'un placement (rotation + translation)."""
    R = [[m[j][i] for j in range(3)] for i in range(3)]
    t = [-sum(R[i][k] * m[k][3] for k in range(3)) for i in range(3)]
    return [R[0] + [t[0]], R[1] + [t[1]], R[2] + [t[2]], [0.0, 0.0, 0.0, 1.0]]


def contains(body: Body, p) -> bool:
    """Le point (coordonnées placées) est-il dans la matière du corps ?"""
    x, y, z = (float(c) for c in p)
    if body.matrix is not None:
        m = inverse(body.matrix)
        x, y, z = (m[i][0] * x + m[i][1] * y + m[i][2] * z + m[i][3] for i in range(3))
    for s in body.slabs:
        if s.z0 < z < s.z1:
            n = sum(1 for lp in s.loops
                    if (math.hypot(x - lp.cx, y - lp.cy) < lp.radius(z, s.z0, s.z1) if isinstance(lp, Circle)
                        else _inside((x, y), _level_points(lp, z, s.z0, s.z1, 720))))
            return n % 2 == 1
    return False


# --- écriture STEP ----------------------------------------------------------------------------------------
def _f(v: float) -> str:
    v = float(v)
    if abs(v) < 1e-12:
        return '0.'
    s = f'{v:.9f}'.rstrip('0')
    return s


def _ascii(text: str) -> str:
    import unicodedata
    t = unicodedata.normalize('NFKD', str(text))
    return ''.join(ch for ch in t if 32 <= ord(ch) < 127 and ch not in "'\\")


class _Writer:
    """Entités STEP numérotées ; sommets et arêtes partagés par clé."""

    def __init__(self):
        self.lines: list[str] = []
        self.vertices: dict = {}
        self.edges: dict = {}
        self.M = None

    def e(self, text: str) -> str:
        self.lines.append(text)
        return f'#{len(self.lines)}'

    # placement
    def _p(self, p):
        if self.M is None:
            return p
        M = self.M
        return tuple(M[i][0] * p[0] + M[i][1] * p[1] + M[i][2] * p[2] + M[i][3] for i in range(3))

    def _d(self, d):
        if self.M is None:
            return d
        M = self.M
        v = [M[i][0] * d[0] + M[i][1] * d[1] + M[i][2] * d[2] for i in range(3)]
        n = math.sqrt(sum(c * c for c in v)) or 1.0
        return tuple(c / n for c in v)

    def pt(self, p) -> str:
        x, y, z = self._p(p)
        return self.e(f"CARTESIAN_POINT('',({_f(x)},{_f(y)},{_f(z)}))")

    def dr(self, d) -> str:
        x, y, z = self._d(d)
        return self.e(f"DIRECTION('',({_f(x)},{_f(y)},{_f(z)}))")

    def axis(self, p, n, ref) -> str:
        return self.e(f"AXIS2_PLACEMENT_3D('',{self.pt(p)},{self.dr(n)},{self.dr(ref)})")

    def vertex(self, p) -> str:
        k = tuple(round(c, 6) + 0.0 for c in p)
        if k not in self.vertices:
            self.vertices[k] = self.e(f"VERTEX_POINT('',{self.pt(p)})")
        return self.vertices[k]

    def line_edge(self, a, b) -> tuple[str, bool]:
        """(arête, même sens que a → b)."""
        ka, kb = (tuple(round(c, 6) + 0.0 for c in a), tuple(round(c, 6) + 0.0 for c in b))
        key = ('L',) + tuple(sorted((ka, kb)))
        if key not in self.edges:
            d = [b[i] - a[i] for i in range(3)]
            L = math.sqrt(sum(v * v for v in d))
            if L < EPS:
                raise BrepError('arête de longueur nulle')
            vec = self.e(f"VECTOR('',{self.dr(tuple(v / L for v in d))},{_f(L)})")
            ln = self.e(f"LINE('',{self.pt(a)},{vec})")
            self.edges[key] = (self.e(f"EDGE_CURVE('',{self.vertex(a)},{self.vertex(b)},{ln},.T.)"), ka)
        ent, first = self.edges[key]
        return ent, first == ka

    def arc_edge(self, c3, r, a0, a1, normal=(0.0, 0.0, 1.0), ref=(1.0, 0.0, 0.0)) -> tuple[str, bool]:
        """Arc de cercle (centre c3, plan de normale `normal`, repère `ref`), de l'angle a0 à a1 (a1 > a0 :
        sens direct autour de `normal`, sinon indirect) ; rend (arête, même sens que a0 → a1)."""
        vy = (normal[1] * ref[2] - normal[2] * ref[1], normal[2] * ref[0] - normal[0] * ref[2],
              normal[0] * ref[1] - normal[1] * ref[0])

        def at(a):
            return tuple(c3[i] + r * (math.cos(a) * ref[i] + math.sin(a) * vy[i]) for i in range(3))
        lo, hi = (a0, a1) if a1 > a0 else (a1, a0)
        pa, pb = at(lo), at(hi)
        key = ('C', tuple(round(c, 6) + 0.0 for c in c3), round(r, 6), tuple(round(c, 6) + 0.0 for c in normal),
               tuple(round(c, 6) + 0.0 for c in pa), tuple(round(c, 6) + 0.0 for c in pb),
               tuple(round(c, 6) + 0.0 for c in at((lo + hi) / 2)))
        if key not in self.edges:
            circ = self.e(f"CIRCLE('',{self.axis(c3, normal, ref)},{_f(r)})")
            self.edges[key] = (self.e(f"EDGE_CURVE('',{self.vertex(pa)},{self.vertex(pb)},{circ},.T.)"), None)
        return self.edges[key][0], a1 > a0

    def face(self, loops, surf: str, same: bool = True) -> str:
        bounds = []
        for k, oes in enumerate(loops):
            items = [self.e(f"ORIENTED_EDGE('',*,*,{ent},{'.T.' if fwd else '.F.'})") for ent, fwd in oes]
            lp = self.e(f"EDGE_LOOP('',({','.join(items)}))")
            bounds.append(self.e(f"{'FACE_OUTER_BOUND' if k == 0 else 'FACE_BOUND'}('',{lp},.T.)"))
        return self.e(f"ADVANCED_FACE('',({','.join(bounds)}),{surf},{'.T.' if same else '.F.'})")


def _oriented(lp, z, z0, z1, ccw: bool) -> list:
    """Segments de la boucle à la cote z, parcourus dans le sens direct (ccw) ou indirect."""
    segs = _segments(lp, z, z0, z1)
    if (_area(_level_points(lp, z, z0, z1, 24)) > 0) == ccw:
        return segs
    out = []
    for sg in reversed(segs):
        if sg[0] == 'line':
            out.append(('line', sg[2], sg[1]))
        else:
            _k, c, r, a0, a1, s = sg
            out.append(('arc', c, r, a1, a0, -s))
    return out


def _seg_edge(w: _Writer, sg, z) -> tuple[str, bool]:
    if sg[0] == 'line':
        return w.line_edge((sg[1][0], sg[1][1], z), (sg[2][0], sg[2][1], z))
    _k, c, r, a0, a1, _s = sg
    return w.arc_edge((c[0], c[1], z), r, a0, a1)


def _seg_end(sg, which: int):
    if sg[0] == 'line':
        return sg[1] if which == 0 else sg[2]
    _k, c, r, a0, a1, _s = sg
    a = a0 if which == 0 else a1
    return (c[0] + r * math.cos(a), c[1] + r * math.sin(a))


def _wall(w: _Writer, lp, k: int, s: Slab, ccw: bool, bottom=None, top=None, vb=None, vt=None) -> str:
    """Paroi du segment k de la boucle `lp` dans la tranche `s`, parcourue matière à gauche (contour
    extérieur dans le sens direct, trou dans le sens indirect) ; `bottom`, `top` : les segments orientés
    de la boucle aux deux cotes (calculés une fois par boucle) ; `vb`, `vt` : sommets de la tranche voisine
    en bas, en haut (parois alignées) où couper les arêtes droites."""
    b = (bottom or _oriented(lp, s.z0, s.z0, s.z1, ccw))[k]
    t = (top or _oriented(lp, s.z1, s.z0, s.z1, ccw))[k]
    a0, b0 = _seg_end(b, 0), _seg_end(b, 1)
    a1, b1 = _seg_end(t, 0), _seg_end(t, 1)
    P = lambda q, z: (q[0], q[1], z)                      # noqa: E731
    eb, fb = _seg_edge(w, b, s.z0)
    et, ft = _seg_edge(w, t, s.z1)
    if isinstance(lp, Circle) and lp.sphere is not None:
        zc, R = lp.sphere
        c3 = (lp.cx, lp.cy, zc)

        def meridian(q0, q1):
            ang = math.atan2(q0[1] - lp.cy, q0[0] - lp.cx)
            ref = (math.cos(ang), math.sin(ang), 0.0)
            nrm = (math.sin(ang), -math.cos(ang), 0.0)    # plan méridien : x vers l'extérieur, y vers le haut
            u0 = math.atan2(q0[2] - zc, math.hypot(q0[0] - lp.cx, q0[1] - lp.cy))
            u1 = math.atan2(q1[2] - zc, math.hypot(q1[0] - lp.cx, q1[1] - lp.cy))
            return w.arc_edge(c3, R, u0, u1, normal=nrm, ref=ref)
        eup = meridian(P(b0, s.z0), P(b1, s.z1))
        edn = meridian(P(a0, s.z0), P(a1, s.z1))
        surf = w.e(f"SPHERICAL_SURFACE('',{w.axis(c3, (0, 0, 1), (1, 0, 0))},{_f(R)})")
        return w.face([[(eb, fb), eup, (et, not ft), (edn[0], not edn[1])]], surf, b[5] > 0)
    eup = w.line_edge(P(b0, s.z0), P(b1, s.z1))
    edn = w.line_edge(P(a1, s.z1), P(a0, s.z0))
    low = [(eb, fb)] if vb is None else [_seg_edge(w, pc, s.z0) for pc in _split(b, vb)]
    high = [(et, not ft)] if vt is None else [(e, not f) for e, f in reversed([_seg_edge(w, pc, s.z1)
                                                                               for pc in _split(t, vt)])]
    loop = low + [eup] + high + [edn]
    if b[0] == 'line':
        d = (b0[0] - a0[0], b0[1] - a0[1], 0.0)
        up = (a1[0] - a0[0], a1[1] - a0[1], s.z1 - s.z0)
        n = (d[1] * up[2] - d[2] * up[1], d[2] * up[0] - d[0] * up[2], d[0] * up[1] - d[1] * up[0])
        L = math.sqrt(sum(c * c for c in n))
        dl = math.hypot(d[0], d[1])
        surf = w.e(f"PLANE('',{w.axis(P(a0, s.z0), tuple(c / L for c in n), (d[0] / dl, d[1] / dl, 0.0))})")
        return w.face([loop], surf, True)
    _k, c, r0, _a0, _a1, sens = b
    r1 = t[2]
    same = sens > 0                                       # sens direct, matière à gauche : matière dans le cercle
    if abs(r1 - r0) < EPS:
        surf = w.e(f"CYLINDRICAL_SURFACE('',{w.axis((c[0], c[1], s.z0), (0, 0, 1), (1, 0, 0))},{_f(r0)})")
    else:
        h = s.z1 - s.z0
        alpha = math.atan(abs(r1 - r0) / h)
        if r1 > r0:
            ax = w.axis((c[0], c[1], s.z0), (0, 0, 1), (1, 0, 0))
            surf = w.e(f"CONICAL_SURFACE('',{ax},{_f(r0)},{_f(alpha)})")
        else:
            ax = w.axis((c[0], c[1], s.z1), (0, 0, -1), (1, 0, 0))
            surf = w.e(f"CONICAL_SURFACE('',{ax},{_f(r1)},{_f(alpha)})")
    return w.face([loop], surf, same)


class _Level:
    """Boucle d'une tranche à une cote : sa géométrie, de quoi la comparer et la situer."""

    def __init__(self, lp, slab: Slab, z: float, role: str):
        self.lp, self.slab, self.z, self.role = lp, slab, z, role
        self.pts = _level_points(lp, z, slab.z0, slab.z1, 64)
        self.area = abs(_area(self.pts))
        self.bb = _bbox(self.pts)
        segs = _segments(lp, z, slab.z0, slab.z1)
        self.key = frozenset(_seg_key(sg) for sg in segs)


def _seg_key(sg):
    if sg[0] == 'line':
        a, b = (tuple(round(c, 6) + 0.0 for c in sg[1]), tuple(round(c, 6) + 0.0 for c in sg[2]))
        return ('L',) + tuple(sorted((a, b)))
    _k, c, r, a0, a1, _s = sg
    lo, hi = min(a0, a1), max(a0, a1)
    return ('A', round(c[0], 6), round(c[1], 6), round(r, 6), round(math.cos(lo), 6), round(math.sin(lo), 6),
            round(math.cos(hi), 6), round(math.sin(hi), 6), round(math.cos((lo + hi) / 2), 6))


def _region(levels, p) -> bool:
    return sum(1 for lv in levels if _in_box(p, lv.bb) and _inside(p, lv.pts)) % 2 == 1


def _sample_inside(lv: _Level, children: list):
    """Un point juste dans la boucle, hors de ses enfants."""
    pts = lv.pts
    ccw = _area(pts) > 0
    size = math.sqrt(lv.area) if lv.area > 0 else 1.0
    for eps in (size * 1e-3, size * 1e-4):
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            dx, dy = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dy)
            if L < EPS:
                continue
            nx, ny = (-dy / L, dx / L) if ccw else (dy / L, -dx / L)
            p = ((a[0] + b[0]) / 2 + nx * eps, (a[1] + b[1]) / 2 + ny * eps)
            if _inside(p, pts) and not any(_inside(p, c.pts) for c in children):
                return p
    raise BrepError('boucle trop fine')


def _level_faces(w: _Writer, z: float, below: Slab | None, above: Slab | None) -> list:
    B = [_Level(lp, below, z, 'B') for lp in below.loops] if below is not None else []
    A = [_Level(lp, above, z, 'A') for lp in above.loops] if above is not None else []
    keys_b = {lv.key for lv in B}
    keys_a = {lv.key for lv in A}
    rest = [lv for lv in B if lv.key not in keys_a] + [lv for lv in A if lv.key not in keys_b]
    seen, uniq = set(), []
    for lv in rest:
        if lv.key not in seen:
            seen.add(lv.key)
            uniq.append(lv)
    rest = uniq
    children = {}
    for i, lv in enumerate(rest):
        best = None
        for j, other in enumerate(rest):
            if i != j and other.area > lv.area and _in_box(lv.pts[0], other.bb) and _inside(lv.pts[0], other.pts):
                if best is None or other.area < rest[best].area:
                    best = j
        children.setdefault(best, []).append(i)
    faces = []
    for i, lv in enumerate(rest):
        kids = [rest[j] for j in children.get(i, [])]
        p = _sample_inside(lv, kids)
        in_b, in_a = _region(B, p), _region(A, p)
        if in_b == in_a:
            continue
        up = in_b                                         # matière dessous seulement : face vers le haut
        loops = []
        for k, item in enumerate([lv] + kids):
            ccw = (k == 0) == up                          # vu de la normale : extérieur direct, trous indirects
            segs = _oriented(item.lp, z, item.slab.z0, item.slab.z1, ccw)
            loops.append([_seg_edge(w, sg, z) for sg in segs])
        n = (0.0, 0.0, 1.0 if up else -1.0)
        surf = w.e(f"PLANE('',{w.axis((lv.pts[0][0], lv.pts[0][1], z), n, (1, 0, 0))})")
        faces.append(w.face(loops, surf, True))
    return faces


# --- parois alignées d'une tranche à l'autre ---------------------------------------------------------
def _slab_segments(slab: Slab, z: float) -> list:
    """Segments orientés matière à gauche de toutes les boucles de la tranche à la cote z."""
    depth = _depths(slab.loops, (slab.z0 + slab.z1) / 2.0, slab.z0, slab.z1)
    out = []
    for lp, d in zip(slab.loops, depth):
        out += _oriented(lp, z, slab.z0, slab.z1, d % 2 == 0)
    return out


def _level_vertices(below: Slab | None, above: Slab | None, z: float):
    """Sommets des boucles des deux tranches à la cote z : tableau (n, 2)."""
    import numpy as np
    pts = [_seg_end(sg, i) for sl in (below, above) if sl is not None for sg in _slab_segments(sl, z)
           for i in (0, 1)]
    return np.asarray(pts, dtype=float).reshape(-1, 2)


def _split(sg, V, tol: float = 1e-7, near: float | None = None) -> list:
    """Le segment coupé aux sommets `V` posés sur lui, dans son sens (un arc reste entier) ; les sommets
    sont repris tels quels pour que les arêtes se partagent. `near` : un sommet plus près que cela sans être
    posé sur le segment (tranches presque alignées) lève BrepError."""
    if sg[0] != 'line' or V is None or not len(V):
        return [sg]
    import numpy as np
    ax, ay = sg[1]
    dx, dy = sg[2][0] - ax, sg[2][1] - ay
    L = math.hypot(dx, dy)
    if L < EPS:
        return [sg]
    t = ((V[:, 0] - ax) * dx + (V[:, 1] - ay) * dy) / (L * L)
    off = np.abs((V[:, 0] - ax) * dy - (V[:, 1] - ay) * dx) / L
    if near is not None and ((off >= tol) & (off < near) & (t * L > tol) & ((1.0 - t) * L > tol)).any():
        raise BrepError(NEAR_MSG)
    idx = np.where((off < tol) & (t * L > tol) & ((1.0 - t) * L > tol))[0]
    if not len(idx):
        return [sg]
    pts = [tuple(sg[1])]
    for i in idx[np.argsort(t[idx])]:
        q = (float(V[i, 0]), float(V[i, 1]))
        if math.hypot(q[0] - pts[-1][0], q[1] - pts[-1][1]) > tol:
            pts.append(q)
    if math.hypot(sg[2][0] - pts[-1][0], sg[2][1] - pts[-1][1]) <= tol:
        pts.pop()
    pts.append(tuple(sg[2]))
    return [('line', a, b) for a, b in zip(pts, pts[1:])]


#: deux tranches dont des sommets ou des côtés sont à moins d'un micromètre sans être confondus
NEAR_MSG = 'deux tranches presque alignées (écart sous le micromètre) : arrondir les cotes'
#: refus des parois alignées dits tels quels (les autres : « se croisent »)
PRECISE = (NEAR_MSG, 'arc tangent à un côté de l\'autre tranche', 'deux tranches bord à bord (deux solides)',
           'deux tranches qui se touchent en un point')


def _seg_box(sg, pad: float = 0.0):
    """La boîte exacte du segment (un arc : ses bouts et ses points extrêmes), agrandie de `pad`."""
    if sg[0] == 'line':
        pts = [sg[1], sg[2]]
    else:
        _k, c, r, a0, a1, _s = sg
        lo, hi = min(a0, a1), max(a0, a1)
        q = math.pi / 2.0
        angs = [a0, a1] + [k * q for k in range(math.ceil(lo / q), math.floor(hi / q) + 1)]
        pts = [(c[0] + r * math.cos(a), c[1] + r * math.sin(a)) for a in angs]
    x0, y0, x1, y1 = _bbox(pts)
    return x0 - pad, y0 - pad, x1 + pad, y1 + pad


def _tangent(arc, line) -> bool:
    """L'arc touche-t-il le segment droit en un point qui n'est le bout ni de l'un ni de l'autre ?"""
    _k, c, r, a0, a1, _s = arc
    (x0, y0), (x1, y1) = line[1], line[2]
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy)
    if L < EPS:
        return False
    t = ((c[0] - x0) * dx + (c[1] - y0) * dy) / (L * L)
    if t * L <= EPS or (1.0 - t) * L <= EPS:
        return False
    fx, fy = x0 + t * dx, y0 + t * dy
    if abs(math.hypot(fx - c[0], fy - c[1]) - r) > EPS:
        return False
    lo, hi = min(a0, a1), max(a0, a1)
    a = lo + (math.atan2(fy - c[1], fx - c[0]) - lo) % TWO_PI
    margin = EPS / max(r, EPS)
    return lo + margin < a < hi - margin


def _nest(pts: list) -> list:
    """Boucles (sens direct : contour, indirect : trou) rangées en faces : [(contour, [trous])…]."""
    outer = [i for i, q in enumerate(pts) if _area(q) > 0]
    boxes = {j: _bbox(pts[j]) for j in outer}
    holes = {i: [] for i in outer}
    for i, q in enumerate(pts):
        if i in holes:
            continue
        best = min((j for j in outer if _in_box(q[0], boxes[j]) and _inside(q[0], pts[j])),
                   key=lambda j: abs(_area(pts[j])), default=None)
        if best is None:
            raise BrepError('trou sans contour à une cote')
        holes[best].append(i)
    return [(i, holes[i]) for i in outer]


def _reverse(sg):
    if sg[0] == 'line':
        return ('line', sg[2], sg[1])
    _k, c, r, a0, a1, sens = sg
    return ('arc', c, r, a1, a0, -sens)


def _dkey(sg):
    """Clé du segment avec son sens."""
    if sg[0] == 'line':
        return ('L', tuple(round(c, 6) + 0.0 for c in sg[1]), tuple(round(c, 6) + 0.0 for c in sg[2]))
    return _seg_key(sg) + (sg[5],)


def _mid(sg):
    if sg[0] == 'line':
        return ((sg[1][0] + sg[2][0]) / 2.0, (sg[1][1] + sg[2][1]) / 2.0)
    _k, c, r, a0, a1, _s = sg
    a = (a0 + a1) / 2.0
    return (c[0] + r * math.cos(a), c[1] + r * math.sin(a))


def _vkey(p):
    return (round(p[0], 6) + 0.0, round(p[1], 6) + 0.0)


def _chain(pieces: list) -> list:
    """Les morceaux orientés enchaînés en boucles fermées (un seul départ par sommet)."""
    nxt = {}
    for pc in pieces:
        k = _vkey(_seg_end(pc, 0))
        if k in nxt:
            raise BrepError('boucles qui se touchent en un point')
        nxt[k] = pc
    loops, used = [], set()
    for k0 in list(nxt):
        if k0 in used:
            continue
        loop, k = [], k0
        while True:
            pc = nxt.get(k)
            if pc is None or k in used:
                raise BrepError('contour ouvert ou mêlé')
            used.add(k)
            loop.append(pc)
            k = _vkey(_seg_end(pc, 1))
            if k == k0:
                break
        loops.append(loop)
    return loops


def _cross_check(Pb: list, Pa: list) -> None:
    """Des morceaux des deux tranches ne se rencontrent qu'à leurs bouts, ou confondus ; un arc tangent à un
    côté de l'autre tranche (le solide s'y pincerait) est refusé."""
    import shapely
    from shapely import STRtree
    from shapely.geometry import LineString

    def geom(pc):
        return LineString(_seg_points(pc, 64) + [_seg_end(pc, 1)])
    ga = [geom(pc) for pc in Pa]
    if not ga:
        return
    tree = STRtree(ga)
    boxes = STRtree([shapely.box(*_seg_box(pc)) for pc in Pa])       # boîtes exactes : un arc tangent ne
    for pb in Pb:                                                     # coupe pas ses cordes échantillonnées
        g = geom(pb)
        for j in boxes.query(shapely.box(*_seg_box(pb, EPS))).tolist():
            pa = Pa[j]
            if {pa[0], pb[0]} == {'arc', 'line'} and (_tangent(pa, pb) if pa[0] == 'arc' else _tangent(pb, pa)):
                raise BrepError('arc tangent à un côté de l\'autre tranche')
        for j in tree.query(g, predicate='intersects').tolist():
            pa = Pa[j]
            if _dkey(pa) in (_dkey(pb), _dkey(_reverse(pb))):
                continue
            inter = g.intersection(ga[j])
            if inter.length > 1e-9:
                raise BrepError('boucles de deux tranches qui se recouvrent en partie')
            ends = [_seg_end(pc, i) for pc in (pa, pb) for i in (0, 1)]
            for q in shapely.get_coordinates(inter):     # points, ou bouts d'un recouvrement infime
                on_a = min(math.hypot(q[0] - e[0], q[1] - e[1]) for e in ends[:2])
                on_b = min(math.hypot(q[0] - e[0], q[1] - e[1]) for e in ends[2:])
                if on_a > 1e-6 or on_b > 1e-6:
                    raise BrepError('boucles de deux tranches qui se croisent')


def _flush_loops(below: Slab | None, above: Slab | None, z: float) -> tuple:
    """Faces horizontales à la cote z quand des boucles des deux tranches se touchent sur des parois
    alignées : (boucles vers le haut, boucles vers le bas), chacune une liste de morceaux orientés région à
    gauche vue de +Z. La matière d'en dessous hors de celle d'au-dessus regarde vers le haut, l'inverse vers
    le bas ; un morceau commun dans le même sens est une paroi qui continue (pas de face), en sens contraire
    deux tranches bord à bord (refusé)."""
    V = _level_vertices(below, above, z)
    groups = [[pc for sg in (_slab_segments(sl, z) if sl is not None else []) for pc in _split(sg, V, near=EPS)]
              for sl in (below, above)]
    if any(pc[0] == 'line' and math.hypot(pc[2][0] - pc[1][0], pc[2][1] - pc[1][1]) < EPS for g in groups for pc in g):
        raise BrepError(NEAR_MSG)
    _cross_check(*groups)
    polys = [[_level_points(lp, z, sl.z0, sl.z1, 64) for lp in sl.loops] if sl is not None else []
             for sl in (below, above)]
    boxes = [[_bbox(q) for q in pl] for pl in polys]
    keys = [{_dkey(pc) for pc in g} for g in groups]
    up, down = [], []
    for k in (0, 1):
        other = 1 - k
        for pc in groups[k]:
            dk = _dkey(pc)
            if dk in keys[other]:
                continue
            if _dkey(_reverse(pc)) in keys[other]:
                raise BrepError('deux tranches bord à bord (deux solides)')
            m = _mid(pc)
            inside = sum(1 for q, b in zip(polys[other], boxes[other]) if _in_box(m, b) and _inside(m, q)) % 2 == 1
            if k == 0:
                (down if inside else up).append(_reverse(pc) if inside else pc)
            else:
                (up if inside else down).append(_reverse(pc) if inside else pc)
    if {_vkey(_seg_end(pc, 0)) for pc in up} & {_vkey(_seg_end(pc, 0)) for pc in down}:
        raise BrepError('deux tranches qui se touchent en un point')      # le solide s'y pincerait
    return _chain(up), _chain(down)


def _flush_faces(w: _Writer, z: float, below: Slab | None, above: Slab | None) -> list:
    faces = []
    for loops, is_up in zip(_flush_loops(below, above, z), (True, False)):
        pts = [[q for pc in lp for q in _seg_points(pc, 64)] for lp in loops]
        for i, hs in _nest(pts):
            ls = [loops[i]] + [loops[j] for j in hs]
            if not is_up:                                  # vue de -Z : boucles retournées
                ls = [[_reverse(pc) for pc in reversed(lp)] for lp in ls]
            n = (0.0, 0.0, 1.0 if is_up else -1.0)
            p0 = _seg_end(loops[i][0], 0)
            surf = w.e(f"PLANE('',{w.axis((p0[0], p0[1], z), n, (1, 0, 0))})")
            faces.append(w.face([[_seg_edge(w, pc, z) for pc in lp] for lp in ls], surf, True))
    return faces


def _neighbours(slabs: list, z: float) -> tuple:
    below = next((sl for sl in slabs if abs(sl.z1 - z) < Z_TOL), None)
    above = next((sl for sl in slabs if abs(sl.z0 - z) < Z_TOL), None)
    return below, above


def check(body: Body) -> set:
    """Lève BrepError si le corps n'est pas décrit comme le module le demande ; rend les cotes (arrondies à
    9 décimales) où deux tranches ont des parois alignées."""
    if not body.slabs:
        raise BrepError(f'{body.name} : aucune tranche')
    for s in body.slabs:
        if s.z1 - s.z0 < EPS:
            raise BrepError(f'{body.name} : tranche d\'épaisseur nulle')
        if not s.loops:
            raise BrepError(f'{body.name} : tranche sans section')
        for lp in s.loops:
            if isinstance(lp, Circle):
                for z in (s.z0, s.z1):
                    if lp.radius(z, s.z0, s.z1) < EPS:
                        raise BrepError(f'{body.name} : cercle de rayon nul')
                if lp.sphere is not None and abs(lp.radius(s.z0, s.z0, s.z1) - lp.r) > EPS:
                    raise BrepError(f'{body.name} : rayon du cercle hors de sa sphère')
            else:
                if len(lp.pts) < 2 or (len(lp.pts) < 3 and not any(lp.bulges or [])):
                    raise BrepError(f'{body.name} : polygone de moins de trois sommets')
                if lp.varies() and any(abs(b) > 1e-12 for b in (lp.bulges or [])):
                    raise BrepError(f'{body.name} : polygone à arcs mis à l\'échelle')
    zs = sorted((s.z0, s.z1) for s in body.slabs)
    for (_a0, a1), (b0, _b1) in zip(zs, zs[1:]):
        if b0 < a1 - Z_TOL:
            raise BrepError(f'{body.name} : tranches qui se chevauchent')
        if b0 > a1 + Z_TOL:
            raise BrepError(f'{body.name} : tranches séparées (deux solides)')
    touch = _check_crossings(body)
    if body.matrix is not None:
        M = body.matrix
        det = (M[0][0] * (M[1][1] * M[2][2] - M[1][2] * M[2][1]) - M[0][1] * (M[1][0] * M[2][2] - M[1][2] * M[2][0])
               + M[0][2] * (M[1][0] * M[2][1] - M[1][1] * M[2][0]))
        if det <= 0:
            raise BrepError(f'{body.name} : placement en miroir')
        for i in range(3):
            for j in range(3):
                d = sum(M[k][i] * M[k][j] for k in range(3))
                if abs(d - (1.0 if i == j else 0.0)) > 1e-6:
                    raise BrepError(f'{body.name} : placement qui n\'est ni rotation ni translation')
    return touch


def _check_crossings(body: Body) -> set:
    """Boucles d'une tranche qui se coupent ou se touchent, ou boucles de deux tranches voisines qui se
    croisent (autrement que sur des parois alignées) : BrepError (le solide serait faux). Rend les cotes des
    parois alignées."""
    from shapely import STRtree
    from shapely.geometry import LinearRing
    slabs = sorted(body.slabs, key=lambda s: s.z0)
    touch: set = set()

    def rings(s, z):
        out = []
        for lp in s.loops:
            pts = _level_points(lp, z, s.z0, s.z1, 64)
            key = frozenset(_seg_key(sg) for sg in _segments(lp, z, s.z0, s.z1))
            out.append((LinearRing(pts), key))
        return out

    def crossing(group, same_ok: bool = True) -> bool:
        geoms = [g for g, _k in group]
        tree = STRtree(geoms)
        # au bruit de calcul près : un sommet sur un côté sans y être exactement se touche aussi
        a, b = tree.query(geoms, predicate='dwithin', distance=EPS)
        return any(i < j and (not same_ok or group[i][1] != group[j][1]) for i, j in zip(a.tolist(), b.tolist()))
    for k, s in enumerate(slabs):
        for z in (s.z0, s.z1):
            if crossing(rings(s, z), same_ok=False):        # dans une tranche, même deux boucles confondues
                raise BrepError(f'{body.name} : boucles qui se coupent ou se confondent à Z = {z:g}')
        if k and abs(slabs[k - 1].z1 - s.z0) < Z_TOL:
            lo, hi = rings(slabs[k - 1], s.z0), rings(s, s.z0)
            side = {key: d % 2 for (_g, key), d in zip(lo, _depths(slabs[k - 1].loops, (slabs[k - 1].z0 + slabs[k - 1].z1)
                                                                    / 2.0, slabs[k - 1].z0, slabs[k - 1].z1))}
            for (_g, key), d in zip(hi, _depths(s.loops, (s.z0 + s.z1) / 2.0, s.z0, s.z1)):
                if key in side and side[key] != d % 2:          # même boucle, matière de part et d'autre
                    raise BrepError(f'{body.name} : deux tranches bord à bord à Z = {s.z0:g} (deux solides)')
            group = lo + hi
            if crossing(group):
                try:
                    _flush_loops(slabs[k - 1], s, s.z0)        # parois alignées : permises
                except BrepError as ex:
                    why = str(ex) if str(ex) in PRECISE else 'boucles de deux tranches qui se croisent'
                    raise BrepError(f'{body.name} : {why} à Z = {s.z0:g}') from None
                touch.add(round(s.z0, 9))
    return touch


def _body_faces(w: _Writer, body: Body) -> list:
    touch = check(body)
    w.M = body.matrix
    w.vertices, w.edges = {}, {}
    slabs = sorted(body.slabs, key=lambda s: s.z0)
    V = {z: _level_vertices(*_neighbours(slabs, z), z) for z in touch}
    faces = []
    for s in slabs:
        mid = (s.z0 + s.z1) / 2.0
        depth = _depths(s.loops, mid, s.z0, s.z1)
        vb, vt = V.get(round(s.z0, 9)), V.get(round(s.z1, 9))
        for lp, d in zip(s.loops, depth):
            bottom = _oriented(lp, s.z0, s.z0, s.z1, d % 2 == 0)
            top = _oriented(lp, s.z1, s.z0, s.z1, d % 2 == 0)
            for k in range(len(bottom)):
                faces.append(_wall(w, lp, k, s, d % 2 == 0, bottom, top, vb, vt))
    levels = sorted({round(s.z0, 9) for s in slabs} | {round(s.z1, 9) for s in slabs})
    for z in levels:
        below = [s for s in slabs if abs(s.z1 - z) < Z_TOL]
        above = [s for s in slabs if abs(s.z0 - z) < Z_TOL]
        if len(below) > 1 or len(above) > 1:
            raise BrepError(f'{body.name} : tranches qui se chevauchent')
        if round(z, 9) in touch:
            faces += _flush_faces(w, z, below[0] if below else None, above[0] if above else None)
        else:
            faces += _level_faces(w, z, below[0] if below else None, above[0] if above else None)
    w.M = None
    return faces


def step_text(bodies: list, name: str = 'piece', description: str = 'VectorDrive') -> str:
    """Le texte STEP (AP214) des corps : un solide nommé et coloré chacun."""
    w = _Writer()
    nom = _ascii(name) or 'piece'
    ctx = w.e("APPLICATION_CONTEXT('core data for automotive mechanical design processes')")
    w.e(f"APPLICATION_PROTOCOL_DEFINITION('international standard','automotive_design',2000,{ctx})")
    pctx = w.e(f"PRODUCT_CONTEXT('',{ctx},'mechanical')")
    prod = w.e(f"PRODUCT('{nom}','{nom}','',({pctx}))")
    w.e(f"PRODUCT_RELATED_PRODUCT_CATEGORY('part',$,({prod}))")
    pdf = w.e(f"PRODUCT_DEFINITION_FORMATION('','',{prod})")
    pdc = w.e(f"PRODUCT_DEFINITION_CONTEXT('part definition',{ctx},'design')")
    pd = w.e(f"PRODUCT_DEFINITION('design','',{pdf},{pdc})")
    pds = w.e(f"PRODUCT_DEFINITION_SHAPE('','',{pd})")
    lg = w.e("(LENGTH_UNIT()NAMED_UNIT(*)SI_UNIT(.MILLI.,.METRE.))")
    an = w.e("(NAMED_UNIT(*)PLANE_ANGLE_UNIT()SI_UNIT($,.RADIAN.))")
    so = w.e("(NAMED_UNIT(*)SI_UNIT($,.STERADIAN.)SOLID_ANGLE_UNIT())")
    unc = w.e(f"UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-07),{lg},'distance_accuracy_value',"
              f"'confusion accuracy')")
    rctx = w.e(f"(GEOMETRIC_REPRESENTATION_CONTEXT(3)GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT(({unc}))"
               f"GLOBAL_UNIT_ASSIGNED_CONTEXT(({lg},{an},{so}))"
               f"REPRESENTATION_CONTEXT('Context #1','3D Context with UNIT and UNCERTAINTY'))")
    breps, styled = [], []
    for b in bodies:
        faces = _body_faces(w, b)
        shell = w.e(f"CLOSED_SHELL('',({','.join(faces)}))")
        breps.append(w.e(f"MANIFOLD_SOLID_BREP('{_ascii(b.name) or 'corps'}',{shell})"))
        styled += [(f, tuple(b.color or GREY)) for f in faces]
    origin = w.axis((0, 0, 0), (0, 0, 1), (1, 0, 0))
    absr = w.e(f"ADVANCED_BREP_SHAPE_REPRESENTATION('{nom}',({','.join(breps + [origin])}),{rctx})")
    w.e(f"SHAPE_DEFINITION_REPRESENTATION({pds},{absr})")
    items, styles = [], {}
    for item, rgb in styled:
        if rgb not in styles:
            col = w.e(f"COLOUR_RGB('',{_f(rgb[0])},{_f(rgb[1])},{_f(rgb[2])})")
            fsc = w.e(f"FILL_AREA_STYLE_COLOUR('',{col})")
            fas = w.e(f"FILL_AREA_STYLE('',({fsc}))")
            ssfa = w.e(f"SURFACE_STYLE_FILL_AREA({fas})")
            sss = w.e(f"SURFACE_SIDE_STYLE('',({ssfa}))")
            ssu = w.e(f"SURFACE_STYLE_USAGE(.BOTH.,{sss})")
            styles[rgb] = w.e(f"PRESENTATION_STYLE_ASSIGNMENT(({ssu}))")
        items.append(w.e(f"STYLED_ITEM('color',({styles[rgb]}),{item})"))
    if items:
        w.e(f"MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION('',({','.join(items)}),{rctx})")
    date = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    head = ['ISO-10303-21;', 'HEADER;', f"FILE_DESCRIPTION(('{_ascii(description)}'),'2;1');",
            f"FILE_NAME('{nom}.step','{date}',('VectorDrive'),(''),'VectorDrive','VectorDrive','');",
            "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));", 'ENDSEC;', 'DATA;']
    body = [f'#{k + 1}={line};' for k, line in enumerate(w.lines)]
    return '\n'.join(head + body + ['ENDSEC;', 'END-ISO-10303-21;', ''])


def write(path, bodies: list, name: str = '', description: str = 'VectorDrive') -> str:
    """Écrit le STEP ; le texte est fait d'abord, puis écrit à côté et mis en place : un fichier existant
    n'est jamais vidé par une erreur."""
    import os
    import pathlib
    p = pathlib.Path(path)
    text = step_text(bodies, name or p.stem, description)
    tmp = p.with_name(p.name + '.tmp')
    try:
        with open(tmp, 'w', encoding='ascii', newline='\n') as f:
            f.write(text)
        os.replace(tmp, p)
    finally:
        if tmp.exists():
            tmp.unlink()
    return str(p)


# --- maillage (aperçu, volume du dessin) ---------------------------------------------------------------
def _ring(lp, z, slab, ccw: bool, n_arc: int) -> list:
    pts = _level_points(lp, z, slab.z0, slab.z1, n_arc)
    return pts if (_area(pts) > 0) == ccw else pts[::-1]


def _bands(lp, slab, bands: int) -> list:
    """Cotes où échantillonner la paroi : les deux bouts, et des bandes sur une sphère."""
    if isinstance(lp, Circle) and lp.sphere is not None:
        return [slab.z0 + (slab.z1 - slab.z0) * i / bands for i in range(bands + 1)]
    return [slab.z0, slab.z1]


def _zipper(P: list, za: float, Q: list, zb: float) -> list:
    """Triangles entre deux chaînes de points alignés (bas P, haut Q, même sens), comme le quadrilatère
    (p0, p1, q1, q0) qu'elles bordent."""
    def params(C):
        d = [0.0]
        for a, b in zip(C, C[1:]):
            d.append(d[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        return [x / d[-1] if d[-1] > 0 else 0.0 for x in d]
    tp, tq = params(P), params(Q)
    out = []
    i = j = 0
    while i < len(P) - 1 or j < len(Q) - 1:
        if j >= len(Q) - 1 or (i < len(P) - 1 and tp[i + 1] <= tq[j + 1]):
            out.append(((*P[i], za), (*P[i + 1], za), (*Q[j], zb)))
            i += 1
        else:
            out.append(((*P[i], za), (*Q[j + 1], zb), (*Q[j], zb)))
            j += 1
    return [t for t in out if math.hypot(*(
        ((t[1][1] - t[0][1]) * (t[2][2] - t[0][2]) - (t[1][2] - t[0][2]) * (t[2][1] - t[0][1]),
         (t[1][2] - t[0][2]) * (t[2][0] - t[0][0]) - (t[1][0] - t[0][0]) * (t[2][2] - t[0][2]),
         (t[1][0] - t[0][0]) * (t[2][1] - t[0][1]) - (t[1][1] - t[0][1]) * (t[2][0] - t[0][0])))) > 1e-12]


def mesh(body: Body, n_arc: int = 64, bands: int = 8):
    """Triangles (n, 3, 3) du corps placé, fermés et tournés vers l'extérieur (aperçu, volume du dessin) :
    parois en quadrilatères, faces horizontales triangulées sur les points mêmes des parois."""
    import numpy as np
    import shapely
    from shapely.geometry import Polygon
    touch = check(body)
    slabs = sorted(body.slabs, key=lambda s: s.z0)
    n_arc = max(12, min(n_arc, 4096 // max(1, sum(len(s.loops) for s in slabs))))    # grilles : moins fin
    V = {z: _level_vertices(*_neighbours(slabs, z), z) for z in touch}
    tris = []
    flat = []
    for s in slabs:
        depth = _depths(s.loops, (s.z0 + s.z1) / 2.0, s.z0, s.z1)
        for lp, d in zip(s.loops, depth):
            zs = _bands(lp, s, bands)
            rings = [_ring(lp, z, s, d % 2 == 0, n_arc) for z in zs]
            for za, zb, ra, rb in zip(zs, zs[1:], rings, rings[1:]):
                n = len(ra)
                va, vb = V.get(round(za, 9)), V.get(round(zb, 9))
                for i in range(n):
                    j = (i + 1) % n
                    if va is not None or vb is not None:
                        P = _split(('line', ra[i], ra[j]), va)
                        Q = _split(('line', rb[i], rb[j]), vb)
                        if len(P) > 1 or len(Q) > 1:              # paroi alignée : coupée aux sommets voisins
                            tris += _zipper([ra[i]] + [pc[2] for pc in P], za, [rb[i]] + [pc[2] for pc in Q], zb)
                            continue
                    p0, p1 = (*ra[i], za), (*ra[j], za)
                    q0, q1 = (*rb[i], zb), (*rb[j], zb)
                    if math.hypot(p1[0] - p0[0], p1[1] - p0[1]) > 1e-12:
                        tris.append((p0, p1, q1))
                    if math.hypot(q1[0] - q0[0], q1[1] - q0[1]) > 1e-12:
                        tris.append((p0, q1, q0))
    levels = sorted({round(s.z0, 9) for s in slabs} | {round(s.z1, 9) for s in slabs})
    for z in levels:
        below = next((s for s in slabs if abs(s.z1 - z) < 1e-9), None)
        above = next((s for s in slabs if abs(s.z0 - z) < 1e-9), None)
        if z in touch:                                   # parois alignées : les boucles mêmes du STEP
            for loops, up in zip(_flush_loops(below, above, z), (True, False)):
                pts = [[q for pc in lp for q in _seg_points(pc, n_arc)] for lp in loops]
                for i, hs in _nest(pts):
                    flat.append(_cap(Polygon(pts[i], [pts[j] for j in hs]), z, up))
            continue

        def region(slab):
            """Matière de la tranche à la cote z : boucles d'une même profondeur réunies d'un coup (elles ne se
            touchent pas), puis ajoutées (profondeur paire) ou retirées, de l'extérieur vers l'intérieur."""
            if slab is None:
                return Polygon()
            depth = _depths(slab.loops, z, slab.z0, slab.z1)
            reg = Polygon()
            for d in sorted(set(depth)):
                level = shapely.union_all([Polygon(_level_points(lp, z, slab.z0, slab.z1, n_arc))
                                           for lp, dd in zip(slab.loops, depth) if dd == d])
                reg = reg.union(level) if d % 2 == 0 else reg.difference(level)
            return reg
        rb, ra = region(below), region(above)
        for geom, up in ((rb.difference(ra), True), (ra.difference(rb), False)):
            for poly in getattr(geom, 'geoms', [geom]):
                if poly.geom_type != 'Polygon' or poly.area < 1e-12:
                    continue
                flat.append(_cap(poly, z, up))
    T = np.concatenate([np.array(tris, dtype=float).reshape(-1, 3, 3)] + flat)
    if body.matrix is not None:
        M = np.array(body.matrix, dtype=float)
        T = T @ M[:3, :3].T + M[:3, 3]
    return T


def _cap(poly, z: float, up: bool):
    """Triangles (k, 3, 3) du polygone à la cote z, tournés vers le haut (`up`) ou vers le bas."""
    import numpy as np
    import shapely
    c = shapely.get_coordinates(shapely.constrained_delaunay_triangles(poly)).reshape(-1, 4, 2)[:, :3]
    cross = (c[:, 1, 0] - c[:, 0, 0]) * (c[:, 2, 1] - c[:, 0, 1]) - (c[:, 1, 1] - c[:, 0, 1]) * (c[:, 2, 0] - c[:, 0, 0])
    flip = (cross > 0) != up
    c[flip] = c[flip][:, ::-1]
    return np.concatenate([c, np.full((len(c), 3, 1), z)], axis=2)


# --- placements -------------------------------------------------------------------------------------------
def placement(origin=(0.0, 0.0, 0.0), z_axis=(0.0, 0.0, 1.0), x_axis=None) -> list:
    """Matrice qui pose l'axe Z du corps sur `z_axis` en `origin`."""
    zx, zy, zz = z_axis
    n = math.sqrt(zx * zx + zy * zy + zz * zz) or 1.0
    z = (zx / n, zy / n, zz / n)
    if x_axis is None:
        x_axis = (1.0, 0.0, 0.0) if abs(z[0]) < 0.9 else (0.0, 1.0, 0.0)
    d = sum(x_axis[i] * z[i] for i in range(3))
    x = [x_axis[i] - d * z[i] for i in range(3)]
    n = math.sqrt(sum(c * c for c in x)) or 1.0
    x = [c / n for c in x]
    y = (z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0])
    return [[x[0], y[0], z[0], origin[0]], [x[1], y[1], z[1], origin[1]], [x[2], y[2], z[2], origin[2]],
            [0.0, 0.0, 0.0, 1.0]]


def compose(a: list, b: list) -> list:
    """a · b (b appliquée d'abord)."""
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def rotation_z(deg: float) -> list:
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[c, -s, 0.0, 0.0], [s, c, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]


def translation(dx: float, dy: float, dz: float) -> list:
    return [[1.0, 0.0, 0.0, dx], [0.0, 1.0, 0.0, dy], [0.0, 0.0, 1.0, dz], [0.0, 0.0, 0.0, 1.0]]


# --- formes courantes ---------------------------------------------------------------------------------
def polygon(n: int, across_flats: float, cx: float = 0.0, cy: float = 0.0, start_deg: float = 0.0) -> Poly:
    """Polygone régulier de `n` côtés (six pans : surplat `across_flats`), un sommet à `start_deg`."""
    R = across_flats / (2.0 * math.cos(math.pi / n))
    a0 = math.radians(start_deg)
    return Poly([(cx + R * math.cos(a0 + TWO_PI * i / n), cy + R * math.sin(a0 + TWO_PI * i / n))
                 for i in range(n)], center=(cx, cy))


def rounded_rect(x0: float, y0: float, x1: float, y1: float, r: float = 0.0) -> Poly:
    """Rectangle, coins arrondis de rayon r (0 : vifs)."""
    r = max(0.0, min(r, (x1 - x0) / 2.0, (y1 - y0) / 2.0))
    center = ((x0 + x1) / 2, (y0 + y1) / 2)
    if r < EPS:
        return Poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], center=center)
    q = math.pi / 2                                    # un quart de tour par coin
    pts = [(x0 + r, y0), (x1 - r, y0), (x1, y0 + r), (x1, y1 - r), (x1 - r, y1), (x0 + r, y1), (x0, y1 - r),
           (x0, y0 + r)]
    sweep = [0.0, q, 0.0, q, 0.0, q, 0.0, q]           # angle de l'arc qui part de chaque sommet
    out, angles = [], []
    for p, a in zip(pts, sweep):                       # côtés de longueur nulle : leurs deux coins réunis
        if out and math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) < EPS:
            angles[-1] += a
            continue
        out.append(p)
        angles.append(a)
    if len(out) > 1 and math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) < EPS:
        out.pop()
        angles[0] += angles.pop()
    return Poly(out, [math.tan(a / 4.0) for a in angles], center=center)


def slot(cx: float, cy: float, length: float, width: float, angle_deg: float = 0.0) -> Poly:
    """Oblong (clavette, lumière) : longueur hors tout, largeur, axe à `angle_deg`."""
    r = width / 2.0
    h = max(EPS, length / 2.0 - r)
    c, s = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    loc = [(-h, -r), (h, -r), (h, r), (-h, r)]
    pts = [(cx + x * c - y * s, cy + x * s + y * c) for x, y in loc]
    return Poly(pts, [0.0, 1.0, 0.0, 1.0], center=(cx, cy))


def revolve(profile: list, name: str, color=GREY, cx: float = 0.0, cy: float = 0.0, holes=None) -> Body:
    """Corps de révolution d'axe Z depuis un profil [(z, r)…] lu de bas en haut : une tranche par pas,
    cylindre ou cône ; `holes` : [(z0, z1, loop)…] ajoutés aux tranches de ces cotes (empreintes)."""
    slabs = []
    for (za, ra), (zb, rb) in zip(profile, profile[1:]):
        if zb - za < EPS:
            continue
        slabs.append(Slab(za, zb, [Circle(cx, cy, ra, None if abs(rb - ra) < EPS else rb)]))
    for z0, z1, lp in holes or []:
        slabs = _cut_slabs(slabs, z0, z1)
        for s in slabs:
            if s.z0 >= z0 - EPS and s.z1 <= z1 + EPS:
                s.loops.append(lp)
    return Body(name, slabs, color)


def _cut_slabs(slabs: list, *zs) -> list:
    """Tranches recoupées aux cotes `zs` (cônes et sphères recalculés)."""
    out = []
    for s in slabs:
        cuts = sorted(z for z in zs if s.z0 + EPS < z < s.z1 - EPS)
        bounds = [s.z0] + cuts + [s.z1]
        for za, zb in zip(bounds, bounds[1:]):
            loops = []
            for lp in s.loops:
                if isinstance(lp, Circle):
                    if lp.sphere is not None:
                        loops.append(Circle(lp.cx, lp.cy, lp.radius(za, s.z0, s.z1), sphere=lp.sphere))
                    elif lp.varies():
                        loops.append(Circle(lp.cx, lp.cy, lp.radius(za, s.z0, s.z1), lp.radius(zb, s.z0, s.z1)))
                    else:
                        loops.append(Circle(lp.cx, lp.cy, lp.r))
                elif lp.varies():
                    h = s.z1 - s.z0
                    sa = 1.0 + (lp.scale_top - 1.0) * (za - s.z0) / h
                    sb = 1.0 + (lp.scale_top - 1.0) * (zb - s.z0) / h
                    loops.append(Poly(lp.at(za, s.z0, s.z1), None, sb / sa if sa > EPS else 1.0, lp.center))
                else:
                    loops.append(Poly(list(lp.pts), list(lp.bulges) if lp.bulges else None, 1.0, lp.center))
            out.append(Slab(za, zb, loops))
    return out


def cut(body: Body, *zs) -> Body:
    """Le corps aux tranches recoupées aux cotes `zs`."""
    return Body(body.name, _cut_slabs(body.slabs, *zs), body.color, body.matrix)


def add_loop(body: Body, z0: float, z1: float, lp) -> Body:
    """Une boucle (trou, empreinte, îlot) ajoutée aux tranches entre z0 et z1 (recoupées au besoin)."""
    b = cut(body, z0, z1)
    for s in b.slabs:
        if s.z0 >= z0 - EPS and s.z1 <= z1 + EPS:
            s.loops.append(lp)
    return b
