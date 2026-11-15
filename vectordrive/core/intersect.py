"""Points d'intersection du dessin, et manières de les supprimer.

Un croisement qu'on ne voit pas coûte à l'usinage : une gravure doublée, un
outil qui repasse, une poche qui garde un îlot, une découpe qui laisse
tomber une chute au mauvais endroit. `find` les repère tous, au point près
(intersections exactes des segments, pas d'un contour aplati), et les range
par nature :

- **boucle** (`self`) : un contour se recoupe lui-même (reprise de tracé,
  décalage qui se retourne) ; la longueur de la boucle dit si c'est un
  défaut (petite) ou une forme voulue (un 8) ;
- **contours** : deux contours d'un même objet se croisent ;
- **objets** : deux objets se croisent ou se chevauchent.

Méthodes de suppression (`METHODS`), chacune sur une copie :

- `loops` : retirer les petites boucles (plus courtes qu'une limite) — le
  contour garde sa forme, le défaut disparaît ;
- `normalize` : surface pair-impair (ce que montre le remplissage), contours
  simples, recouvrements devenus trous ;
- `nonzero` : surface remplie (règle non nulle) — les recouvrements restent
  pleins ;
- `union` : objets qui se touchent réunis en un seul contour ;
- `outer` : réunion, puis le seul contour extérieur (trous enlevés) ;
- `split` : contours coupés à chaque intersection, en traits ouverts (pour
  graver chaque morceau une fois, ou en supprimer).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .geom import Contour, Path

KINDS = {'self': 'Boucle (contour qui se recoupe)', 'contours': 'Entre contours d\'un objet',
         'objets': 'Entre objets', 'doublon': 'Contours en double (superposés)'}
METHODS = {
    'loops': 'Retirer les petites boucles',
    'normalize': 'Normaliser (pair-impair : recouvrements en trous)',
    'nonzero': 'Surface remplie (recouvrements pleins)',
    'union': 'Réunir les objets qui se croisent',
    'outer': 'Contour extérieur seulement',
    'split': 'Couper aux intersections (traits ouverts)',
    'dedupe': 'Supprimer les contours en double',
}
#: deux contours dont tous les points sont à moins de DUP_TOL (mm) l'un de
#: l'autre sont un doublon (dessin superposé), pas des croisements
DUP_TOL = 0.05
#: boucle « petite » par défaut (mm) : défaut plutôt que forme voulue
LOOP = 2.0
#: au-delà, un contour n'est pas examiné pour ses boucles (trop de segments)
MAX_SEGMENTS = 20000


@dataclass
class Crossing:
    x: float
    y: float
    kind: str                       # 'self', 'contours', 'objets'
    a: object                       # objet (premier niveau)
    b: object = None                # second objet ('objets')
    loop: float = 0.0               # longueur de la boucle ('self')


@dataclass
class Report:
    crossings: list = field(default_factory=list)

    def count(self, kind: str | None = None) -> int:
        return sum(1 for c in self.crossings if kind is None or c.kind == kind)

    def small_loops(self, limit: float = LOOP) -> int:
        return sum(1 for c in self.crossings if c.kind == 'self' and c.loop <= limit)

    def items(self) -> list:
        out = []
        for c in self.crossings:
            for it in (c.a, c.b):
                if it is not None and all(it is not o for o in out):
                    out.append(it)
        return out


def point_at(c: Contour, g: float) -> tuple[float, float]:
    """Point du contour au paramètre global g (indice du segment + t)."""
    n = len(c.segments)
    i = min(int(math.floor(g)), n - 1)
    return c.segments[i % n].point(min(1.0, max(0.0, g - i)))


def _length(c: Contour) -> float:
    return sum(s.length() for s in c.segments)


#: aplatissement des contours pour les intersections entre contours et les
#: longueurs des boucles (mm)
PAIR_FLAT = 0.002


class _Flat:
    """Tracé aplati d'un contour : points, longueur cumulée, début de chaque
    segment dans le tracé, polygone préparé (contour fermé)."""

    def __init__(self, c: Contour):
        pts = [c.segments[0].p0]
        starts = []
        for seg in c.segments:
            starts.append(len(pts) - 1)
            pts.extend(seg.flatten(PAIR_FLAT))
        self.c = c
        self.P = np.asarray(pts, float)
        d = np.hypot(*np.diff(self.P, axis=0).T) if len(self.P) > 1 else np.zeros(0)
        self.S = np.concatenate([[0.0], np.cumsum(d)])
        self.starts = np.asarray(starts + [len(pts) - 1])
        self.total = float(self.S[-1])
        self._poly = False

    def poly(self):
        if self._poly is False:
            self._poly = None
            if self.c.closed and len(self.P) >= 4:
                import shapely
                try:
                    g = shapely.make_valid(shapely.polygons(self.P))
                    shapely.prepare(g)
                    self._poly = g
                except Exception:                       # noqa: BLE001 — contour dégénéré
                    self._poly = None
        return self._poly

    def at(self, g: float) -> float:
        """Abscisse curviligne (approchée par le tracé) du paramètre g."""
        n = len(self.c.segments)
        i = min(int(g), n - 1)
        a, b = self.S[self.starts[i]], self.S[self.starts[i + 1]]
        return float(a + (b - a) * (g - i))

    def near(self, x: float, y: float) -> float:
        """Abscisse curviligne du point du tracé le plus proche de (x, y)."""
        P = self.P
        if len(P) < 2:
            return 0.0
        a, b = P[:-1], P[1:]
        ab = b - a
        L2 = (ab ** 2).sum(1)
        L2[L2 == 0] = 1e-30
        t = np.clip(((x - a[:, 0]) * ab[:, 0] + (y - a[:, 1]) * ab[:, 1]) / L2, 0, 1)
        q = a + t[:, None] * ab
        k = int(np.argmin(np.hypot(q[:, 0] - x, q[:, 1] - y)))
        return float(self.S[k] + t[k] * (self.S[k + 1] - self.S[k]))

    def point(self, s: float) -> tuple[float, float]:
        if self.c.closed and self.total > 0:
            s %= self.total
        s = min(max(s, 0.0), self.total)
        return float(np.interp(s, self.S, self.P[:, 0])), float(np.interp(s, self.S, self.P[:, 1]))


def loop_length(c: Contour, ga: float, gb: float, flat: '_Flat | None' = None) -> float:
    """Longueur de la boucle entre deux paramètres d'un croisement (la plus
    courte des deux parts pour un contour fermé), sur le tracé aplati."""
    f = flat or _Flat(c)
    inner = abs(f.at(gb) - f.at(ga))
    return min(inner, f.total - inner) if c.closed else inner


def _side_change(fa: _Flat, x: float, y: float, fb: _Flat) -> bool:
    """Le contour de `fa` passe-t-il en (x, y) d'un côté à l'autre du contour
    fermé de `fb` (sinon il le touche seulement : sommets communs d'une
    surface normalisée, contact tangent) ? `fb` ouvert : oui."""
    poly = fb.poly()
    if poly is None:
        return True
    import shapely
    s = fa.near(x, y)
    d = min(0.02, max(1e-4, fa.total / 20))
    (x0, y0), (x1, y1) = fa.point(s - d), fa.point(s + d)
    ins = shapely.contains_xy(poly, np.array([x0, x1]), np.array([y0, y1]))
    return bool(ins[0] != ins[1])


def _is_crossing(fa: _Flat, fb: _Flat, x: float, y: float) -> bool:
    """Vrai croisement en (x, y) : pas au bout d'un trait ouvert (jonction de
    traits, T), et passage d'un côté à l'autre d'un contour fermé (pas un
    simple contact). Deux traits ouverts qui se croisent en leur milieu : oui."""
    for f in (fa, fb):
        if not f.c.closed:
            s = f.near(x, y)
            tol = min(1e-3, f.total / 4)
            if s <= tol or s >= f.total - tol:
                return False
    if fb.c.closed:
        return _side_change(fa, x, y, fb)
    if fa.c.closed:
        return _side_change(fb, x, y, fa)
    return True


def _shape_contours(items):
    """[(objet, contour)] des formes (groupes dépliés) ; les textes par leur
    contour."""
    from .document import Group, Shape, Text
    out = []

    def walk(top, it):
        if isinstance(it, Group):
            for ch in it.children:
                walk(top, ch)
        elif isinstance(it, Shape) and it.path:
            out.extend((top, c) for c in it.path.contours if c.segments)
        elif isinstance(it, Text) and getattr(it, 'outline', None):
            out.extend((top, c) for c in it.outline.contours if c.segments)
    for it in items:
        if getattr(it, 'visible', True):
            walk(it, it)
    return out


def find(items, *, progress_cb=None) -> Report:
    """Points d'intersection des objets `items` : boucles exactes (segments
    recoupés), croisements entre contours sur les tracés aplatis à
    PAIR_FLAT près ; dédoublonnés, contacts sans croisement écartés."""
    from . import progress
    from .trim import self_crossings
    cs = _shape_contours(items)
    rep = Report()
    seen = set()

    def add(x, y, kind, a, b=None, loop=0.0):
        key = (round(x, 5), round(y, 5), kind)
        if key in seen:
            return
        seen.add(key)
        rep.crossings.append(Crossing(float(x), float(y), kind, a, b, loop))
    n = len(cs)
    flats = [_Flat(c) for _t, c in cs]
    for k, (top, c) in enumerate(cs):                   # boucles
        progress.step(k, 2 * max(1, n), 'Intersections : contour {0} sur {1}')
        if len(c.segments) > MAX_SEGMENTS:
            continue
        for ga, gb in self_crossings(c):
            x, y = point_at(c, ga)
            add(x, y, 'self', top, None, loop_length(c, ga, gb, flats[k]))
    if n < 2:
        return rep
    progress.step(n, 2 * n, 'Intersections : contour {0} sur {1}')
    for i, j, pts in pair_points(flats):
        ta, tb = cs[i][0], cs[j][0]
        if len(pts) >= 2 and duplicates(flats[i], flats[j]):
            add(pts[0][0], pts[0][1], 'doublon', ta, None if ta is tb else tb)
            continue
        for x, y in pts:
            if not _is_crossing(flats[i], flats[j], x, y):
                continue                                 # contact, jonction de traits
            if ta is tb:
                add(x, y, 'contours', ta)
            else:
                add(x, y, 'objets', ta, tb)
    return rep


def duplicates(fa: _Flat, fb: _Flat, tol: float = DUP_TOL) -> bool:
    """Les deux tracés sont-ils le même, à `tol` près (dessin superposé) ?"""
    if abs(fa.total - fb.total) > max(tol * 4, 0.02 * max(fa.total, fb.total)):
        return False
    import shapely
    la, lb = shapely.linestrings(fa.P), shapely.linestrings(fb.P)
    try:
        return shapely.hausdorff_distance(la, lb, densify=0.25) <= tol
    except Exception:                                   # noqa: BLE001
        return False


def pair_points(flats: list):
    """[(i, j, [(x, y)])], i < j : points où les tracés aplatis de deux
    contours se rencontrent — index spatial et intersections calculés en
    bloc par shapely (en C) ; les bords communs (recouvrements en ligne) ne
    comptent pas, leurs bouts si."""
    import shapely
    lines, idx = [], []
    for k, f in enumerate(flats):
        if len(f.P) < 2:
            continue
        lines.append(shapely.linestrings(f.P))
        idx.append(k)
    if len(lines) < 2:
        return []
    geoms = np.array(lines, dtype=object)
    own = np.array(idx)
    tree = shapely.STRtree(geoms)
    ia, ib = tree.query(geoms, predicate='intersects')
    m = ia < ib
    ia, ib = ia[m], ib[m]
    if not len(ia):
        return []
    inter = shapely.intersection(geoms[ia], geoms[ib])
    out = []
    for a, b, g in zip(own[ia].tolist(), own[ib].tolist(), inter):
        parts = shapely.get_parts(g)
        pts = [(float(shapely.get_x(q)), float(shapely.get_y(q))) for q in parts if shapely.get_type_id(q) == 0]
        if pts:
            out.append((a, b, pts))
    return out


# --- suppression ---------------------------------------------------------------------------------

def _join(a: Contour, b: Contour) -> Contour:
    return Contour(list(a.segments) + list(b.segments), False)


def remove_loops(c: Contour, limit: float = LOOP, max_steps: int = 500) -> Contour:
    """Le contour sans ses boucles plus courtes que `limit` (la plus petite
    d'abord, jusqu'à ce qu'il n'y en ait plus)."""
    from .trim import piece, self_crossings
    for _ in range(max_steps):
        if len(c.segments) < 3 or len(c.segments) > MAX_SEGMENTS:
            return c
        best = None
        f = _Flat(c)
        for ga, gb in self_crossings(c):
            L = loop_length(c, ga, gb, f)
            if L <= limit and (best is None or L < best[0]):
                best = (L, ga, gb)
        if best is None:
            return c
        _L, ga, gb = best
        n = len(c.segments)
        inner = abs(f.at(gb) - f.at(ga))
        if c.closed:
            # la boucle est la plus courte des deux parts : on garde l'autre
            keep = piece(c, gb, ga) if inner <= f.total - inner else piece(c, ga, gb)
            new = Contour(list(keep.segments), True)
        else:
            new = _join(piece(c, 0.0, ga), piece(c, gb, float(n)))
        if not new.segments or len(new.segments) >= n + 2 and _Flat(new).total >= f.total - 1e-9:
            return c
        c = new
    return c


def split(path: Path, cutters: list, boxes=None) -> Path:
    """Contours coupés à chaque intersection (avec eux-mêmes et avec les
    segments `cutters`) : des traits ouverts. `boxes` : cadres des `cutters`
    (tableau n × 4) calculés une fois pour plusieurs tracés."""
    import numpy as np
    from .trim import cut_params, piece
    if boxes is None and cutters:
        boxes = np.array([t.bbox() for t in cutters], dtype=float).reshape(-1, 4)
    out = []
    for c in path.contours:
        if not c.segments:
            continue
        own = {id(t) for t in c.segments}               # ses propres segments : la coupe sur soi est à part
        near = cutters
        if cutters:                                      # seuls les segments qui recouvrent le contour
            x0, y0, x1, y1 = c.bbox()
            m = ((boxes[:, 0] <= x1 + 1e-3) & (boxes[:, 2] >= x0 - 1e-3)
                 & (boxes[:, 1] <= y1 + 1e-3) & (boxes[:, 3] >= y0 - 1e-3))
            near = [cutters[k] for k in np.nonzero(m)[0].tolist()]
        others = [s for s in near if id(s) not in own]
        gs = cut_params(c, others, self_cut=True)
        n = float(len(c.segments))
        if not gs:
            out.append(c)
            continue
        if c.closed:
            for k, g in enumerate(gs):
                out.append(piece(c, g, gs[(k + 1) % len(gs)] if len(gs) > 1 else g + n))
        else:
            bounds = [0.0] + gs + [n]
            out += [piece(c, a, b) for a, b in zip(bounds, bounds[1:]) if b - a > 1e-9]
    return Path([c for c in out if c.segments])


def outer_only(path: Path) -> Path:
    """Contours extérieurs de la surface remplie (trous enlevés)."""
    from shapely.geometry import Point, Polygon
    from . import pathops
    filled = pathops.normalize(path, evenodd=False)
    polys = []
    for c in filled.contours:
        pts = [p for seg in c.segments for p in [seg.p0] + seg.flatten(0.02)]
        polys.append(Polygon(pts).buffer(0) if len(pts) >= 3 else None)
    keep = []
    for i, c in enumerate(filled.contours):
        probe = Point(c.segments[0].p0)
        inside = any(j != i and p is not None and p.buffer(1e-6).contains(probe) and p.area > (polys[i].area if polys[i] else 0)
                     for j, p in enumerate(polys))
        if not inside:
            keep.append(c)
    return Path(keep)


def apply(method: str, shapes: list, *, limit: float = LOOP) -> list:
    """Nouvelles formes (Shape) des formes `shapes` selon `method` (METHODS).
    `union` / `outer` : une forme par groupe d'objets qui se croisent."""
    from . import pathops
    from .document import Shape
    if method == 'loops':
        return [Shape(path=Path([remove_loops(c, limit) for c in s.path.contours]), tool=s.tool) for s in shapes]
    if method in ('normalize', 'nonzero'):
        return [Shape(path=pathops.normalize(s.path, evenodd=method == 'normalize'), tool=s.tool) for s in shapes]
    if method == 'dedupe':
        return dedupe(shapes)
    if method == 'split':
        import numpy as np
        segs = [seg for s in shapes for c in s.path.contours for seg in c.segments]
        boxes = np.array([t.bbox() for t in segs], dtype=float).reshape(-1, 4)     # une fois pour tous
        return [Shape(path=split(s.path, segs, boxes), tool=s.tool) for s in shapes]
    if method in ('union', 'outer'):
        groups = _touching_groups(shapes)
        out = []
        for g in groups:
            p = pathops.union_all([s.path for s in g]) if len(g) > 1 else pathops.normalize(g[0].path, evenodd=False)
            if method == 'outer':
                p = outer_only(p)
            out.append(Shape(path=p, tool=g[0].tool))
        return out
    raise ValueError(method)


def dedupe(shapes: list, tol: float = DUP_TOL) -> list:
    """Les formes sans leurs contours en double (le premier est gardé) ;
    une forme dont tous les contours sont des doubles disparaît."""
    import shapely
    from .document import Shape
    flats = [(si, ci, _Flat(c)) for si, s in enumerate(shapes) for ci, c in enumerate(s.path.contours)
             if c.segments]
    drop = set()
    if len(flats) > 1:
        boxes = shapely.box(*np.array([[f.P[:, 0].min(), f.P[:, 1].min(), f.P[:, 0].max(), f.P[:, 1].max()]
                                       for _s, _c, f in flats]).T)
        tree = shapely.STRtree(boxes)
        ia, ib = tree.query(shapely.buffer(boxes, tol), predicate='intersects')
        for a, b in sorted(zip(ia.tolist(), ib.tolist())):
            if a < b and a not in drop and b not in drop and duplicates(flats[a][2], flats[b][2], tol):
                drop.add(b)
    gone = {(flats[k][0], flats[k][1]) for k in drop}
    out = []
    for si, s in enumerate(shapes):
        keep = [c for ci, c in enumerate(s.path.contours) if (si, ci) not in gone]
        if keep:
            out.append(Shape(path=Path(keep), tool=s.tool))
    return out


def _touching_groups(shapes: list) -> list[list]:
    """Formes regroupées quand elles se croisent ou se chevauchent (boîtes,
    puis surfaces)."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    geo = []
    for s in shapes:
        polys = [Polygon(p).buffer(0) for p in s.path.flatten(0.05) if len(p) >= 4]
        geo.append(unary_union(polys) if polys else None)
    parent = list(range(len(shapes)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    # paires qui se touchent par un arbre (STRtree) : la double boucle testait toutes les paires
    # (10 000 objets : 50 millions de tests, deux minutes)
    import shapely
    idx = [i for i, g in enumerate(geo) if g is not None and not g.is_empty]
    if len(idx) > 1:
        arr = [geo[i] for i in idx]
        left, right = shapely.STRtree(arr).query(arr, predicate='intersects')
        for a, b in zip(left.tolist(), right.tolist()):
            if a < b:
                i, j = idx[a], idx[b]
                ri, rj = root(i), root(j)
                if ri != rj:
                    parent[max(ri, rj)] = min(ri, rj)
    groups: dict = {}
    for i, s in enumerate(shapes):
        groups.setdefault(root(i), []).append(s)
    return list(groups.values())
