"""Une vis pour un trou d'une pièce 3D (« Vis dans ce trou », onglet
Design STEP).

Le trou est lu sur les faces de la pièce telles que le lecteur STEP les
décrit (cylindres creux : axe, centre, rayon), dans n'importe quelle
direction : les faces coaxiales de même rayon sont réunies (deux
demi-cylindres, des tronçons, une gorge entre deux) sauf si de la matière
les sépare (deux trous borgnes face à face) ; un cylindre coaxial plus
large contre une ouverture : un lamage (1,4 fois le diamètre du trou au
moins, sinon un trou étagé) ; un cône contre une ouverture :
une fraisure s'il s'ouvre à 1,5 fois le diamètre du trou au moins, sinon
un chanfrein d'entrée (la vis se pose au-dessus) ; chaque bout ouvert ou
fermé selon la matière juste au-delà du bout, sous le rayon du trou
(débouchant ou borgne). La paroi d'un lamage choisie : le trou dessous.

Genre du trou (d'après son diamètre et sa forme) et vis proposée :
- lamé : vis CHC ISO 4762, le dessous de la tête sur le fond du lamage ;
- fraisé : vis FHC ISO 10642, le dessus de la tête au ras de la surface ;
- de passage (diamètre ISO 273, série fine, moyenne ou large, ou
  nominal) : vis CHC, la tête sur l'ouverture ;
- taraudé (diamètre de perçage d - pas) : vis CHC, la tête sur l'ouverture.
Un lamage moins profond que la moitié du diamètre de la vis est un lamage
de surface : le trou garde le genre de son diamètre (un taraudage lamé
reste taraudé), la tête sur le fond du lamage.

Longueur proposée (parmi celles de la norme) : trou débouchant de passage,
lamé ou fraisé : toute l'épaisseur traversée (lamage, fraisure ou
chanfrein du côté opposé compris) et 1,5 d de filet en prise dessous ;
trou borgne : la plus longue sous la profondeur moins un pas ; trou taraudé
débouchant : la plus courte qui le traverse. Un trou de passage (ou lamé, ou
fraisé) fermé au fond par un trou plus étroit au diamètre de perçage de sa
taille (trou étagé, pièce posée sur une pièce taraudée) : la vis s'y visse,
1,5 d de filet si ce taraudage débouche, sinon jusqu'à un pas de son fond. La vis est posée dans le trou
par `brep.placement` : ses coordonnées sont celles du fichier de la pièce.

`Part` prépare la pièce une fois (faces réunies, triangles rangés par face,
boîtes des triangles pour sonder la matière vite) : à passer à `analyse` et
`same_holes` pour une grande pièce aux nombreux trous.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import brep as B
from . import stepgen as G

#: axes parallèles à 1° près
PARALLEL = math.cos(math.radians(1.0))
#: couverture angulaire minimale d'un trou complet (°)
FULL_DEG = 300.0
#: écart de diamètre (mm) au-delà duquel la taille proposée est dite approchée
CLOSE_MM = 0.3
#: une fraisure s'ouvre à ce rapport du diamètre du trou au moins ; en dessous : un chanfrein d'entrée
COUNTERSINK_RATIO = 1.5
#: un lamage moins profond que cette part du diamètre de la vis : un lamage de surface
SPOTFACE_RATIO = 0.5
#: un lamage s'ouvre à ce rapport du diamètre du trou au moins (la tête y entre) ; en dessous : un trou étagé
#: (passage au-dessus d'un taraudage, deux pièces l'une sur l'autre)
COUNTERBORE_RATIO = 1.4
#: trous de passage ISO 273, séries fine et large (la moyenne : stepgen.CLEARANCE)
CLEARANCE_FINE = {'M2': 2.2, 'M2.5': 2.7, 'M3': 3.2, 'M4': 4.3, 'M5': 5.3, 'M6': 6.4, 'M8': 8.4, 'M10': 10.5,
                  'M12': 13.0, 'M14': 15.0, 'M16': 17.0, 'M20': 21.0, 'M24': 25.0}
CLEARANCE_COARSE = {'M2': 2.6, 'M2.5': 3.1, 'M3': 3.6, 'M4': 4.8, 'M5': 5.8, 'M6': 7.0, 'M8': 10.0, 'M10': 12.0,
                    'M12': 14.5, 'M14': 16.5, 'M16': 18.5, 'M20': 24.0, 'M24': 28.0}
#: direction des rayons du test « dans la matière » : un peu de biais (comme step3d.dans_la_matiere)
_RAY = np.array([0.0127, 0.0071, 1.0]) / np.linalg.norm([0.0127, 0.0071, 1.0])


class FitError(ValueError):
    pass


@dataclass
class HoleFit:
    """Un trou : ses faces, son axe (de l'intérieur vers l'ouverture, côté tête), le point de l'axe où la vis
    se pose, son rayon, l'épaisseur traversée sous l'assise (sous la surface pour une fraisure)."""
    faces: list
    axis: np.ndarray
    seat: np.ndarray
    radius: float
    depth: float
    through: bool
    kind: str                                   # 'lamage', 'fraisure', 'passage', 'taraude'
    counterbore: tuple | None = None            # (rayon, profondeur) du lamage
    flipped: bool = False
    extra: dict = field(default_factory=dict)

    @property
    def diameter(self) -> float:
        return 2.0 * self.radius


def _unit(v) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-12 else v


def _frame(a: np.ndarray):
    """Deux vecteurs unitaires orthogonaux à `a`."""
    u = np.cross(a, (1.0, 0.0, 0.0) if abs(a[0]) < 0.9 else (0.0, 1.0, 0.0))
    u = _unit(u)
    return u, np.cross(a, u)


def _canon(a: np.ndarray) -> np.ndarray:
    """Le sens d'un axe rendu unique (première composante non nulle positive)."""
    for x in a:
        if abs(x) > 1e-9:
            return a if x > 0 else -a
    return a


@dataclass
class _Group:
    axis: np.ndarray
    centre: np.ndarray
    radius: float
    faces: list
    lo: float = 0.0                             # étendue le long de l'axe, depuis le centre
    hi: float = 0.0


def coaxial_groups(infos, tol: float = 0.02, hollow: bool = True) -> list:
    """Les cylindres (creux seulement si `hollow`) des faces `infos` (descriptions du lecteur), réunis par axe
    et rayon."""
    n = len(infos)
    A, C, R = np.zeros((n, 3)), np.zeros((n, 3)), np.zeros(n)
    groups: list = []
    for f, k in enumerate(infos):
        if not k or k.get('genre') != 'cylindre' or (hollow and not k.get('creux', False)) \
                or k.get('axe') is None or k.get('centre') is None or not k.get('rayon'):
            continue
        a = _canon(_unit(k['axe']))
        c = np.asarray(k['centre'], dtype=float)
        r = float(k['rayon'])
        m = len(groups)
        j = -1
        if m:
            cand = np.flatnonzero((np.abs(A[:m] @ a) >= PARALLEL) & (np.abs(R[:m] - r) <= tol))
            if len(cand):
                d = c - C[cand]
                ax = A[cand]
                off = np.linalg.norm(d - np.einsum('ij,ij->i', d, ax)[:, None] * ax, axis=1)
                hit = cand[off <= tol]
                j = int(hit[0]) if len(hit) else -1
        if j >= 0:
            groups[j].faces.append(f)
        else:
            A[m], C[m], R[m] = a, c, r
            groups.append(_Group(a, c, r, [f]))
    return groups


class Part:
    """La pièce prête pour l'analyse de ses trous : triangles `T` (n, 3, 3), face de chaque triangle
    `face_of`, descriptions des faces `infos` ; les cylindres réunis par axe et rayon puis coupés là où de la
    matière les sépare, les triangles rangés par face, leurs boîtes vues le long des rayons de sondage."""

    def __init__(self, T, face_of, infos, tol: float = 0.02):
        self.T = np.asarray(T, dtype=float).reshape(-1, 3, 3)
        self.fo = np.asarray(face_of)
        self.infos = infos
        self.tol = tol
        self._order = np.argsort(self.fo, kind='stable')
        self._keys = self.fo[self._order]
        v0 = self.T[:, 0]
        self._v0, self._e1, self._e2 = v0, self.T[:, 1] - v0, self.T[:, 2] - v0
        self._p = np.cross(_RAY, self._e2)
        det = np.einsum('ij,ij->i', self._e1, self._p)
        ok = np.abs(det) > 1e-14
        self._inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        self._uv = _frame(_RAY)
        pu, pv = self.T @ self._uv[0], self.T @ self._uv[1]
        e = 1e-6
        self._box = (pu.min(axis=1) - e, pu.max(axis=1) + e, pv.min(axis=1) - e, pv.max(axis=1) + e)
        self.holes = self._split(coaxial_groups(infos, tol))                     # parois de trous
        self.walls = self._split(coaxial_groups(infos, tol, hollow=False))       # lamages possibles
        self._hole_arr = self._arrays(self.holes)
        self._wall_arr = self._arrays(self.walls)
        self._cones, cen, rad = [], [], []
        for f, k in enumerate(infos):
            if k and k.get('genre') == 'cone':
                Q = self.points([f])
                if len(Q) >= 3:
                    m = Q.mean(axis=0)
                    self._cones.append((f, Q))
                    cen.append(m)
                    rad.append(float(np.linalg.norm(Q - m, axis=1).max()))
        self._cone_c = np.asarray(cen, dtype=float).reshape(-1, 3)
        self._cone_r = np.asarray(rad, dtype=float)

    def points(self, faces) -> np.ndarray:
        """Les sommets des triangles des faces `faces` (m, 3)."""
        idx = [self._order[np.searchsorted(self._keys, f, 'left'):np.searchsorted(self._keys, f, 'right')]
               for f in faces]
        idx = np.concatenate(idx) if idx else np.zeros(0, dtype=np.int64)
        return self.T[idx].reshape(-1, 3)

    def inside(self, pts) -> np.ndarray:
        """Pour chaque point : dans la matière ? (parité des traversées d'un rayon un peu de biais, les seuls
        triangles dont la boîte vue le long du rayon contient le point)."""
        u, v = self._uv
        bu0, bu1, bv0, bv1 = self._box
        out = []
        for o in np.atleast_2d(np.asarray(pts, dtype=float)):
            ou, ov = float(o @ u), float(o @ v)
            k = np.flatnonzero((bu0 <= ou) & (bu1 >= ou) & (bv0 <= ov) & (bv1 >= ov))
            s = o - self._v0[k]
            inv = self._inv[k]
            uu = np.einsum('ij,ij->i', s, self._p[k]) * inv
            q = np.cross(s, self._e1[k])
            vv = (q @ _RAY) * inv
            t = np.einsum('ij,ij->i', self._e2[k], q) * inv
            hit = (inv != 0) & (uu >= 0) & (vv >= 0) & (uu + vv <= 1) & (t > 1e-9)
            out.append(int(hit.sum()) % 2 == 1)
        return np.array(out, dtype=bool)

    def _solid_between(self, g: _Group, s_a: float, s_b: float) -> bool:
        """De la matière entre les abscisses `s_a` et `s_b` de l'axe de `g`, juste sous son rayon ?"""
        u, v = _frame(g.axis)
        rp = g.radius - max(2.0 * self.tol, 0.01 * g.radius)
        mid = g.centre + g.axis * (0.5 * (s_a + s_b))
        pts = [mid + rp * (math.cos(t) * u + math.sin(t) * v) for t in (0.7, 3.9)]
        return bool(self.inside(np.array(pts)).all())

    def _split(self, groups) -> list:
        """Chaque groupe coupé en trous distincts là où de la matière sépare ses faces le long de l'axe."""
        out = []
        for g in groups:
            spans, bare = [], []
            for f in g.faces:
                P = self.points([f])
                if len(P):
                    s = (P - g.centre) @ g.axis
                    spans.append((float(s.min()), float(s.max()), f))
                else:
                    bare.append(f)
            if not spans:
                out.append(g)
                continue
            spans.sort()
            pieces = [[spans[0]]]
            for sp in spans[1:]:
                end = max(x[1] for x in pieces[-1])
                if sp[0] > end + self.tol and self._solid_between(g, end, sp[0]):
                    pieces.append([sp])
                else:
                    pieces[-1].append(sp)
            for i, pc in enumerate(pieces):
                faces = sorted([f for _a, _b, f in pc] + (bare if i == 0 else []))
                out.append(_Group(g.axis, g.centre, g.radius, faces, min(x[0] for x in pc), max(x[1] for x in pc)))
        return out

    @staticmethod
    def _arrays(groups) -> tuple:
        return (np.array([g.axis for g in groups], dtype=float).reshape(-1, 3),
                np.array([g.centre for g in groups], dtype=float).reshape(-1, 3),
                np.array([g.radius for g in groups], dtype=float))

    def coaxial(self, which: str, a, c, r_min: float = -1.0, r_max: float = math.inf) -> list:
        """Les groupes `which` ('holes' ou 'walls') sur l'axe (c, a), de rayon entre `r_min` et `r_max`."""
        groups = self.holes if which == 'holes' else self.walls
        A, C, R = self._hole_arr if which == 'holes' else self._wall_arr
        if not len(groups):
            return []
        cand = np.flatnonzero((R > r_min) & (R < r_max) & (np.abs(A @ a) >= PARALLEL))
        d = C[cand] - c
        off = np.linalg.norm(d - np.outer(d @ a, a), axis=1)
        return [groups[i] for i in cand[off <= self.tol]]

    def cones_near(self, p, reach: float) -> list:
        """Les faces coniques (numéro, sommets) qui passent à moins de `reach` du point `p`."""
        if not len(self._cones):
            return []
        near = np.linalg.norm(self._cone_c - p, axis=1) <= self._cone_r + reach
        return [self._cones[i] for i in np.flatnonzero(near)]

    def group_of(self, face: int):
        return next((g for g in self.holes if face in g.faces), None)


def _coverage(P: np.ndarray, c: np.ndarray, a: np.ndarray) -> float:
    """Part du tour (°) que couvrent les points `P` autour de l'axe (c, a)."""
    u, v = _frame(a)
    q = P - c
    ang = np.sort(np.degrees(np.arctan2(q @ v, q @ u)) % 360.0)
    if not len(ang):
        return 0.0
    gaps = np.diff(np.r_[ang, ang[0] + 360.0])
    return float(360.0 - gaps.max())


def _open(part: Part, c, a, s_end, r, sign) -> bool:
    """Le bout du trou à l'abscisse `s_end` (au-delà : vers `sign`) est-il ouvert ? Des points juste au-delà,
    sous le rayon du trou (le cône d'un foret, plus court, n'y est pas) : vides en majorité."""
    u, v = _frame(a)
    e = max(0.2 * r, 0.05)
    pts = [c + a * (s_end + sign * e) + 0.9 * r * (math.cos(t) * u + math.sin(t) * v)
           for t in (0.3, 1.9, 3.5, 5.1)]
    return int((~part.inside(np.array(pts))).sum()) >= 3


def _match(d_hole: float, sizes, diam) -> tuple:
    """(taille, écart) dont `diam(taille)` est le plus près de `d_hole`."""
    best = min(sizes, key=lambda s: abs(diam(s) - d_hole))
    return best, abs(diam(best) - d_hole)


def _tap_drill(size: str) -> float:
    return float(size[1:]) - G.PITCH[size]


def _iso273(size: str) -> list:
    return [t[size] for t in (CLEARANCE_FINE, G.CLEARANCE, CLEARANCE_COARSE) if size in t]


def _clear(size: str, d_hole: float) -> float:
    """Le diamètre d'un trou de passage de cette taille le plus près de `d_hole` : ISO 273 (série fine, moyenne
    ou large) ou nominal (ajusté) ; à égalité, ISO 273."""
    return min([(abs(x - d_hole), x) for x in _iso273(size)] + [(abs(float(size[1:]) - d_hole) + 1e-6,
                                                                  float(size[1:]))])[1]


def _clear_match(d_hole: float, sizes) -> tuple:
    """(taille, écart) du trou de passage le plus près de `d_hole` ; à égalité, une valeur ISO 273 avant un
    nominal (Ø10 : M8 série large, pas M10 ajusté)."""
    def err(s):
        x = _clear(s, d_hole)
        return abs(x - d_hole) + (1e-6 if x == float(s[1:]) else 0.0)
    best = min(sizes, key=err)
    return best, abs(_clear(best, d_hole) - d_hole)


def _entry(part: Part, g: _Group, end: float, sgn: float) -> dict:
    """Ce qui s'ouvre au bout `end` (abscisse le long de l'axe de `g`, dehors vers `sgn`) : 'chamfer' (hauteur
    d'un chanfrein d'entrée), 'countersink' ((hauteur, rayon) d'une fraisure), 'counterbore' ((rayon,
    profondeur) d'un lamage, au-dessus du chanfrein)."""
    a, c, r, tol = g.axis, g.centre, g.radius, part.tol
    eps = max(tol, 1e-3)
    out = {'chamfer': 0.0, 'countersink': None, 'counterbore': None}
    cones = []                                    # faces coniques contre le bout, qui s'évasent vers dehors
    for _f, Q in part.cones_near(c + a * end, 4.0 * r + eps):
        q = sgn * ((Q - c) @ a - end)
        w = Q - c
        rad = np.linalg.norm(w - np.outer(w @ a, a), axis=1)
        if abs(float(q.min())) <= eps and float(q.max()) > tol \
                and float(rad.min()) >= r - eps and float(rad.max()) <= 4.0 * r \
                and np.ptp(rad) > tol and np.corrcoef(q, rad)[0, 1] > 0.9:
            cones.append((Q, float(q.max()), float(rad.max())))
    if cones and _coverage(np.concatenate([Q for Q, _h, _R in cones]), c, a) >= FULL_DEG:
        h, R = max(x[1] for x in cones), max(x[2] for x in cones)
        if R >= COUNTERSINK_RATIO * r:
            out['countersink'] = (h, R)
        else:
            out['chamfer'] = h
    base = end + sgn * out['chamfer']
    for w in part.coaxial('walls', a, c, r_min=COUNTERBORE_RATIO * r - tol):
        Q = part.points(w.faces)
        if not len(Q):
            continue
        q = sgn * ((Q - c) @ a - base)
        if abs(float(q.min())) <= eps and float(q.max()) > tol:
            if out['counterbore'] is None or w.radius < out['counterbore'][0]:
                out['counterbore'] = (w.radius, float(q.max()))
    return out


def _height(feat) -> float:
    """La hauteur de ce qui s'ouvre à un bout (fraisure, ou chanfrein et lamage)."""
    if feat is None:
        return 0.0
    if feat['countersink'] is not None:
        return feat['countersink'][0]
    return feat['chamfer'] + (feat['counterbore'][1] if feat['counterbore'] is not None else 0.0)


def _inner(part: Part, g: _Group):
    """Le trou plus étroit au fond de `g` si `g` est la paroi d'un lamage (contre un de ses bouts), sinon None."""
    eps = max(part.tol, 1e-3)
    best = None
    for h in part.coaxial('holes', g.axis, g.centre, r_max=g.radius / COUNTERBORE_RATIO + part.tol):
        P = part.points(h.faces)
        if not len(P):
            continue
        s = (P - g.centre) @ g.axis
        if (abs(float(s.max()) - g.lo) <= eps or abs(float(s.min()) - g.hi) <= eps) \
                and (best is None or h.radius > best.radius):
            best = h
    return best


def _thread(part: Part, g: _Group, head_hi: bool):
    """(diamètre, longueur, débouchant ?) du trou plus étroit qui continue `g` sous son fond fermé (à l'opposé
    de la tête), ou None."""
    eps = max(part.tol, 1e-3)
    end = g.lo if head_hi else g.hi
    for h in part.coaxial('holes', g.axis, g.centre, r_max=g.radius - part.tol):
        P = part.points(h.faces)
        if not len(P):
            continue
        s = (P - g.centre) @ g.axis
        lo, hi = float(s.min()), float(s.max())
        if abs((hi if head_hi else lo) - end) <= eps and _coverage(P, g.centre, g.axis) >= FULL_DEG:
            out = _open(part, g.centre, g.axis, lo if head_hi else hi, h.radius, -1.0 if head_hi else 1.0)
            return 2.0 * h.radius, hi - lo, bool(out)
    return None


def _hole(part: Part, face: int) -> tuple:
    """(groupe, bouts ouverts {True : haut, False : bas}, ce qui s'ouvre à chaque bout ouvert) du trou dont
    `face` est une paroi."""
    k = part.infos[face] or {}
    if k.get('genre') != 'cylindre' or not k.get('creux', False):
        raise FitError('la face choisie n\'est pas la paroi d\'un trou')
    g = part.group_of(face)
    if g is None:
        raise FitError('la face choisie n\'est pas la paroi d\'un trou')
    g = _inner(part, g) or g
    return (g,) + _ends(part, g)


def _ends(part: Part, g: _Group) -> tuple:
    a, c, r = g.axis, g.centre, g.radius
    P = part.points(g.faces)
    if not len(P) or _coverage(P, c, a) < FULL_DEG:
        raise FitError('pas un trou complet (rainure, congé ?)')
    opened = {True: _open(part, c, a, g.hi, r, 1.0), False: _open(part, c, a, g.lo, r, -1.0)}
    if not (opened[True] or opened[False]):
        raise FitError('trou fermé des deux côtés')
    feats = {hi: _entry(part, g, g.hi if hi else g.lo, 1.0 if hi else -1.0) if opened[hi] else None
             for hi in (True, False)}
    return opened, feats


def _fit(part: Part, g: _Group, opened: dict, feats: dict, flip: bool) -> HoleFit:
    a, c, r = g.axis, g.centre, g.radius
    s0, s1 = g.lo, g.hi
    through = opened[True] and opened[False]
    if through:
        marked = [hi for hi in (True, False)
                  if feats[hi]['counterbore'] is not None or feats[hi]['countersink'] is not None]
        head_hi = marked[0] if len(marked) == 1 else (a[2] >= -1e-9 if abs(a[2]) > 1e-9 else True)
    else:
        head_hi = opened[True]
    if flip:
        if not through:
            raise FitError('trou borgne : la vis n\'entre que d\'un côté')
        head_hi = not head_hi
    axis = a if head_hi else -a
    end, far = (s1, s0) if head_hi else (-s0, -s1)       # abscisses le long de `axis`
    feat = feats[head_hi]
    far -= _height(feats[not head_hi])                     # l'épaisseur traversée, jusqu'à la face opposée
    d_hole = 2.0 * r
    tap, tap_err = _match(d_hole, list(G.ISO4762), _tap_drill)
    clr, clr_err = _clear_match(d_hole, list(G.ISO4762))
    plain, size = ('taraude', tap) if tap_err <= clr_err + 1e-9 else ('passage', clr)
    cb, cs = feat['counterbore'], feat['countersink']
    if cb is not None and cb[1] >= SPOTFACE_RATIO * float(size[1:]):
        kind, seat_s = 'lamage', end + feat['chamfer']
    elif cs is not None:
        kind, seat_s = 'fraisure', end + cs[0]
    else:                                                 # chanfrein ou lamage de surface : au-dessus
        kind, seat_s = plain, end + feat['chamfer']
    seat = c + a * (seat_s if head_hi else -seat_s)
    extra = {'tap': (tap, tap_err), 'clear': (clr, clr_err), 'countersink': cs, 'chamfer': feat['chamfer'],
             'length': s1 - s0}
    if not through:
        extra['thread'] = _thread(part, g, head_hi)
    return HoleFit(list(g.faces), axis, seat, r, seat_s - far, through, kind, cb, bool(flip), extra)


def analyse(T, face_of, infos, face: int, flip: bool = False, tol: float = 0.02, part: Part | None = None) -> HoleFit:
    """Le trou dont `face` est une paroi : triangles `T` (n, 3, 3) de la pièce, `face_of` (face de chaque
    triangle), `infos` (description de chaque face) ; `flip` : la tête de l'autre côté ; `part` : la pièce
    déjà préparée (`Part`), sinon préparée ici."""
    if not 0 <= face < len(infos):
        raise FitError('face inconnue')
    k = infos[face] or {}
    if k.get('genre') != 'cylindre' or not k.get('creux', False):
        raise FitError('la face choisie n\'est pas la paroi d\'un trou')
    part = part if part is not None else Part(T, face_of, infos, tol)
    g, opened, feats = _hole(part, face)
    return _fit(part, g, opened, feats, flip)


def lengths(family: str, size: str) -> list:
    """Les longueurs de la norme pour cette taille (gamme de la famille)."""
    f = G.FAMILIES[family]
    return sorted({float(v['length']) for v in f.series() if v['size'] == size})


def propose(fit: HoleFit) -> dict:
    """{'family', 'size', 'length', 'exact', 'note'} : la vis du trou."""
    family = 'fhc' if fit.kind == 'fraisure' else 'chc'
    table = G.ISO10642 if family == 'fhc' else G.ISO4762
    sizes = list(table)
    d_hole = fit.diameter
    if fit.kind == 'taraude':
        size, err = _match(d_hole, sizes, _tap_drill)
        note = f'taraudé {size} (perçage {_tap_drill(size):g})'
    else:
        size, err = _clear_match(d_hole, sizes)
        note = {'lamage': 'lamé', 'fraisure': 'fraisé', 'passage': 'de passage'}[fit.kind] + f' {size}'
    d, P = float(size[1:]), G.PITCH[size]
    lens = lengths(family, size)
    th = fit.extra.get('thread')
    if not fit.through and fit.kind != 'taraude' and th is not None and abs(th[0] - _tap_drill(size)) <= CLOSE_MM:
        note += ' ; vissée dans le taraudage dessous'
        if th[2]:
            want = fit.depth + 1.5 * d
            L = next((x for x in lens if x >= want - 1e-6), lens[-1])
        else:
            L = max((x for x in lens if x <= fit.depth + th[1] - P + 1e-6), default=lens[0])
    elif fit.through:
        want = fit.depth + 1.5 * d if fit.kind != 'taraude' else fit.depth
        L = next((x for x in lens if x >= want - 1e-6), None)
        if L is None:
            L = lens[-1]
            note += f' ; plus long que la plus longue de la norme ({L:g})'
    else:
        L = max((x for x in lens if x <= fit.depth - P + 1e-6), default=None)
        if L is None:
            L = lens[0]
            note += f' ; trou trop court pour la plus courte de la norme ({L:g})'
    return {'family': family, 'size': size, 'length': L, 'exact': err <= CLOSE_MM, 'note': note}


def placement(fit: HoleFit) -> list:
    """La matrice qui pose une vis du générateur (axe Z, tête vers +Z, assise en Z = 0) dans le trou."""
    return B.placement(tuple(float(x) for x in fit.seat), tuple(float(x) for x in fit.axis))


def screw(fit: HoleFit, family: str, size: str, length: float) -> list:
    """Les corps de la vis `family` `size` × `length`, posée dans le trou."""
    M = placement(fit)
    bodies = G.build(family, G.values(family, size=size, length=length))
    for b in bodies:
        b.matrix = B.compose(M, b.matrix) if b.matrix is not None else M
    return bodies


def _same_feature(x, y, tol: float) -> bool:
    if (x is None) != (y is None):
        return False
    return x is None or all(abs(p - q) <= max(tol, 0.05) for p, q in zip(x, y))


def same_holes(T, face_of, infos, fit: HoleFit, tol: float = 0.02, part: Part | None = None) -> list:
    """Les trous comme `fit` (même rayon, genre, épaisseur, lamage, fraisure, axe dans le même sens), `fit`
    d'abord ; `part` : la pièce déjà préparée."""
    part = part if part is not None else Part(T, face_of, infos, tol)
    out = [fit]
    length = fit.extra.get('length')
    for g in part.holes:
        if set(g.faces) & set(fit.faces) or abs(g.radius - fit.radius) > tol:
            continue
        if length is not None and abs((g.hi - g.lo) - length) > max(5 * tol, 0.05):
            continue                                      # pas la même longueur de perçage : pas besoin de sonder
        try:
            opened, feats = _ends(part, g)
        except FitError:
            continue
        for flip in (False, True):
            try:
                h = _fit(part, g, opened, feats, flip)
            except FitError:
                continue
            if float(h.axis @ fit.axis) >= PARALLEL:
                break
        else:
            continue
        if h.kind != fit.kind or h.through != fit.through or abs(h.depth - fit.depth) > max(5 * tol, 0.05):
            continue
        if not _same_feature(h.counterbore, fit.counterbore, tol) \
                or not _same_feature(h.extra.get('countersink'), fit.extra.get('countersink'), tol):
            continue
        out.append(h)
    return out
