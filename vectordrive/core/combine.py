"""Combiner, décombiner, englobants / englobés ; répartir.

* **Combiner** : plusieurs formes → une seule (ses contours gardés tels
  quels) ; une lettre « O » importée en deux contours séparés devient une
  forme à trou.
* **Décombiner** : une forme à plusieurs contours → une forme par contour.
* **Englobants / englobés** : chaque contour fermé extérieur reçoit les
  contours qu'il contient directement (trous) ; un îlot dans un trou
  repart comme extérieur. Sens normalisé pour la FAO : extérieurs dans le
  sens trigonométrique, trous dans le sens horaire (types TypeEdit 1 et 2).
* **Répartir** : espacements égaux (entre bords ou entre centres) le long
  de X ou de Y, le premier et le dernier objet restant en place.
"""
from __future__ import annotations


import numpy as np

from .document import Group, Item, Shape, Text
from .geom import Affine, Contour, Path


def _leaf_paths(items):
    for it in items:
        if isinstance(it, Group):
            yield from _leaf_paths(it.children)
        elif isinstance(it, Shape) and it.path:
            yield it, it.path
        elif isinstance(it, Text) and it.outline:
            yield it, it.outline


def combine(items: list[Item]) -> Shape | None:
    pairs = list(_leaf_paths(items))
    if not pairs:
        return None
    first = pairs[0][0]
    return Shape(path=Path([c for _it, p in pairs for c in p.contours]), tool=first.tool,
                 filled=any(getattr(it, 'filled', False) or isinstance(it, Text) for it, _p in pairs))


def uncombine(item: Item) -> list[Shape]:
    out = []
    for it, p in _leaf_paths([item]):
        for c in p.contours:
            if c.segments:
                s = Shape(path=Path([c]), tool=it.tool, filled=getattr(it, 'filled', False) or isinstance(it, Text))
                out.append(s)
    return out


# --- englobants / englobés ---------------------------------------------------------

def _polygon(c: Contour) -> np.ndarray:
    return np.asarray(c.flatten(0.01), dtype=float)


def _inside(pt, poly: np.ndarray) -> bool:
    """Point dans un polygone (règle pair-impair, demi-droite horizontale)."""
    x, y = pt
    xa, ya = poly[:-1, 0], poly[:-1, 1]
    xb, yb = poly[1:, 0], poly[1:, 1]
    cross = (ya > y) != (yb > y)
    with np.errstate(divide='ignore', invalid='ignore'):
        xi = xa + (y - ya) * (xb - xa) / (yb - ya)
    return bool(np.count_nonzero(cross & (x < xi)) % 2)


def _probe(c: Contour, poly: np.ndarray):
    """Point représentatif d'un contour : milieu de son premier segment
    (évite un sommet partagé avec le contour voisin)."""
    if c.segments:
        return c.segments[0].point(0.5)
    return tuple(poly[0])


def nest(contours: list[Contour]) -> list[tuple[Contour, list[Contour]]]:
    """[(extérieur, [trous])] pour des contours fermés ; un contour ouvert
    forme seul son groupe (sans trou)."""
    closed = [c for c in contours if c.closed and c.segments]
    opened = [c for c in contours if not c.closed and c.segments]
    polys = [_polygon(c) for c in closed]
    areas = [abs(c.signed_area()) for c in closed]
    boxes = [c.bbox() for c in closed]
    order = sorted(range(len(closed)), key=lambda i: -areas[i])
    parent = {}
    depth = {}
    for rank, i in enumerate(order):
        pt = _probe(closed[i], polys[i])
        best = None
        for j in order[:rank]:                       # plus grands d'abord
            b = boxes[j]
            bi = boxes[i]
            if not (b[0] <= bi[0] + 1e-9 and b[1] <= bi[1] + 1e-9 and bi[2] <= b[2] + 1e-9 and bi[3] <= b[3] + 1e-9):
                continue
            if _inside(pt, polys[j]) and (best is None or areas[j] < areas[best]):
                best = j
        parent[i] = best
        depth[i] = 0 if best is None else depth[best] + 1
    groups = []
    for i in order:
        if depth[i] % 2 == 0:
            outer = closed[i]
            if outer.signed_area() < 0:
                outer = outer.reversed()
            holes = []
            for k in order:
                if parent.get(k) == i:
                    h = closed[k]
                    holes.append(h.reversed() if h.signed_area() > 0 else h)
            groups.append((outer, holes))
    groups += [(c, []) for c in opened]
    return groups


def combine_nested(items: list[Item]) -> list[Shape]:
    pairs = list(_leaf_paths(items))
    if not pairs:
        return []
    tool = pairs[0][0].tool
    filled = any(getattr(it, 'filled', False) or isinstance(it, Text) for it, _p in pairs)
    contours = [c for _it, p in pairs for c in p.contours]
    return [Shape(path=Path([o] + h), tool=tool, filled=filled) for o, h in nest(contours)]


# --- répartir ------------------------------------------------------------------

def distribute(items: list[Item], axis: str = 'x', mode: str = 'gaps') -> list[Item]:
    """Copies translatées de `items` (même ordre) : espaces égaux entre
    bords (`gaps`) ou entre centres (`centers`) le long de `axis`."""
    if len(items) < 3:
        return list(items)
    k = 0 if axis == 'x' else 1
    boxes = [it.bbox() for it in items]
    lo = lambda b: b[k]
    hi = lambda b: b[k + 2]
    order = sorted(range(len(items)), key=lambda i: (lo(boxes[i]) + hi(boxes[i])) / 2)
    first, last = order[0], order[-1]
    out = list(items)
    if mode == 'centers':
        c0 = (lo(boxes[first]) + hi(boxes[first])) / 2
        c1 = (lo(boxes[last]) + hi(boxes[last])) / 2
        step = (c1 - c0) / (len(items) - 1)
        for n, i in enumerate(order[1:-1], 1):
            c = (lo(boxes[i]) + hi(boxes[i])) / 2
            d = c0 + n * step - c
            out[i] = items[i].transformed(Affine.translation(d, 0) if k == 0 else Affine.translation(0, d))
        return out
    span = hi(boxes[last]) - lo(boxes[first])
    widths = sum(hi(boxes[i]) - lo(boxes[i]) for i in order)
    gap = (span - widths) / (len(items) - 1)
    pos = hi(boxes[first]) + gap
    for i in order[1:-1]:
        d = pos - lo(boxes[i])
        out[i] = items[i].transformed(Affine.translation(d, 0) if k == 0 else Affine.translation(0, d))
        pos += hi(boxes[i]) - lo(boxes[i]) + gap
    return out


def space_fixed(items: list[Item], axis: str = 'x', gap: float = 1.0) -> list[Item]:
    """Copies translatées (même ordre) : les objets se suivent le long de
    `axis` avec un écart imposé entre bords ; le premier (le plus à gauche
    ou le plus bas) reste en place."""
    if len(items) < 2:
        return list(items)
    k = 0 if axis == 'x' else 1
    boxes = [it.bbox() for it in items]
    order = sorted(range(len(items)), key=lambda i: (boxes[i][k] + boxes[i][k + 2]) / 2)
    out = list(items)
    pos = boxes[order[0]][k + 2] + gap
    for i in order[1:]:
        d = pos - boxes[i][k]
        out[i] = items[i].transformed(Affine.translation(d, 0) if k == 0 else Affine.translation(0, d))
        pos += boxes[i][k + 2] - boxes[i][k] + gap
    return out


def same_size(items: list[Item], which: str = 'both', ref: int = -1, keep_ratio: bool = False) -> list[Item]:
    """Copies mises à la largeur (`w`), à la hauteur (`h`) ou aux deux
    (`both`) de l'objet de référence `ref`, chacune autour de son centre ;
    `keep_ratio` : proportions gardées (seule la dimension demandée compte)."""
    rb = items[ref].bbox()
    rw, rh = rb[2] - rb[0], rb[3] - rb[1]
    out = []
    for it in items:
        b = it.bbox()
        w, h = b[2] - b[0], b[3] - b[1]
        sx = rw / w if which in ('w', 'both') and w > 1e-12 else 1.0
        sy = rh / h if which in ('h', 'both') and h > 1e-12 else 1.0
        if keep_ratio and which != 'both':
            sx = sy = sx if which == 'w' else sy
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        m = Affine.translation(cx, cy) @ Affine.scaling(sx, sy) @ Affine.translation(-cx, -cy)
        out.append(it if (abs(sx - 1) < 1e-12 and abs(sy - 1) < 1e-12) else it.transformed(m))
    return out


# --- décomposer, supprimer des contours -------------------------------------------

def contour_depths(contours: list[Contour]) -> list[int]:
    """Profondeur d'emboîtement de chaque contour : 0 = extérieur, 1 = trou,
    2 = île dans un trou… ; −1 pour un contour ouvert ou vide."""
    idx = [i for i, c in enumerate(contours) if c.closed and c.segments]
    polys = {i: _polygon(contours[i]) for i in idx}
    areas = {i: abs(contours[i].signed_area()) for i in idx}
    boxes = {i: contours[i].bbox() for i in idx}
    order = sorted(idx, key=lambda i: -areas[i])
    depth = {}
    for rank, i in enumerate(order):
        pt = _probe(contours[i], polys[i])
        best = None
        bi = boxes[i]
        for j in order[:rank]:
            b = boxes[j]
            if not (b[0] <= bi[0] + 1e-9 and b[1] <= bi[1] + 1e-9 and bi[2] <= b[2] + 1e-9 and bi[3] <= b[3] + 1e-9):
                continue
            if _inside(pt, polys[j]) and (best is None or areas[j] < areas[best]):
                best = j
        depth[i] = 0 if best is None else depth[best] + 1
    return [depth.get(i, -1) for i in range(len(contours))]


def remove_contours(path: Path, mode: str = 'holes', min_size: float = 0.0) -> Path:
    """'holes' : retire les trous (profondeur impaire) ; 'outer' : retire les
    contours extérieurs (garde les trous, devenus pleins) ; 'small' : retire
    les contours dont la plus grande dimension est inférieure à min_size."""
    cs = path.contours
    if mode == 'small':
        keep = []
        for c in cs:
            b = c.bbox()
            if b and max(b[2] - b[0], b[3] - b[1]) >= min_size:
                keep.append(c)
        return Path(keep)
    depth = contour_depths(cs)
    if mode == 'holes':
        return Path([c for c, d in zip(cs, depth) if d % 2 == 0 or d < 0])
    return Path([c for c, d in zip(cs, depth) if d % 2 == 1 or d < 0])


def explode(path: Path) -> list[Path]:
    """Un tracé par segment (traits ouverts d'un seul segment)."""
    out = []
    for c in path.contours:
        for s in (c.close() if c.closed else c).segments:     # fermeture implicite comprise
            out.append(Path([Contour([s], False)]))
    return out
