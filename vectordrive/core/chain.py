"""Raccord automatique des contours ouverts dont les extrémités se
touchent (à `tol` près) : droites et arcs séparés d'un DXF, morceaux d'un
contour coupé… Les chaînes qui reviennent à leur point de départ sont
fermées. Les extrémités qui ne coïncident pas tout à fait sont recalées
(l'écart, au plus `tol`, est absorbé par le segment suivant).
"""
from __future__ import annotations

import dataclasses
import math
from collections import defaultdict

from .geom import Conic, Contour, Cubic, Line, Segment


def _with_start(s: Segment, p) -> Segment:
    if s.start == p:
        return s
    if isinstance(s, Cubic):
        d = (p[0] - s.p0[0], p[1] - s.p0[1])
        return dataclasses.replace(s, p0=p, p1=(s.p1[0] + d[0], s.p1[1] + d[1]))
    return dataclasses.replace(s, p0=p)


def _with_end(s: Segment, p) -> Segment:
    if s.end == p:
        return s
    if isinstance(s, Cubic):
        d = (p[0] - s.p3[0], p[1] - s.p3[1])
        return dataclasses.replace(s, p3=p, p2=(s.p2[0] + d[0], s.p2[1] + d[1]))
    if isinstance(s, (Line, Conic)):
        return dataclasses.replace(s, p1=p) if isinstance(s, Line) else dataclasses.replace(s, p2=p)
    return s


def chain_layers(layers, tol: float = 0.01, only: set | None = None, link: float = 0.0,
                 separately: bool = False) -> tuple[int, int, list]:
    """Raccorde, calque par calque, les contours ouverts des formes de
    premier niveau (toutes, ou celles dont l'id est dans `only`) des
    calques visibles et non verrouillés. Une forme par chaîne ; les
    contours fermés restent dans leur forme. Rend (raccords, fermetures,
    formes nouvelles ou modifiées). Les calques sont modifiés en place.
    `link` : voir `chain`. `separately` : chaque contour ne se ferme que
    sur lui-même, aucun n'est relié à un autre, et les formes restent."""
    import copy
    from .document import Shape
    from .geom import Path
    total_j = total_c = 0
    touched = []
    for L in layers:
        if not L.visible or L.locked:
            continue
        shapes = [it for it in L.items if isinstance(it, Shape) and (only is None or id(it) in only)
                  and any(not c.closed for c in it.path.contours)]
        opens = [c for s in shapes for c in s.path.contours if not c.closed and c.segments]
        if not opens:
            continue
        if separately:
            total_c += _close_each(L, shapes, tol, link, touched)
            continue
        chained, j, c = chain(opens, tol, link)
        if not j and not c:
            continue
        total_j += j
        total_c += c
        tool = shapes[0].tool
        ids = {id(s) for s in shapes}
        items = []
        for it in L.items:
            if id(it) in ids:
                rest = [k for k in it.path.contours if k.closed]
                if rest:
                    keep = copy.copy(it)
                    keep.path = Path(rest)
                    items.append(keep)
                    touched.append(keep)
            else:
                items.append(it)
        for k in chained:
            sh = Shape(path=Path([k]), tool=tool)
            items.append(sh)
            touched.append(sh)
        L.items = items
    return total_j, total_c, touched


def _close_each(layer, shapes: list, tol: float, link: float, touched: list) -> int:
    """Chaque contour ouvert de ces formes fermé sur lui-même ; rend le nombre de fermetures."""
    import copy
    from .geom import Path
    closings = 0
    for s in shapes:
        out, n = [], 0
        for k in s.path.contours:
            got, _j, c = chain([k], tol, link) if not k.closed and k.segments else ([k], 0, 0)
            out += got
            n += c
        if n:
            new = copy.copy(s)
            new.path = Path(out)
            layer.items[next(i for i, x in enumerate(layer.items) if x is s)] = new
            touched.append(new)
            closings += n
    return closings


def chain(contours: list[Contour], tol: float = 0.01, link: float = 0.0) -> tuple[list[Contour], int, int]:
    """Contours raccordés : (contours, nombre de raccords, nombre de
    contours fermés par le raccord). Les contours déjà fermés sont rendus
    tels quels, en tête. Deux bouts à moins de `tol` sont fusionnés (la forme
    bouge un peu) ; entre `tol` et `link`, ils sont reliés par un segment
    (la forme ne bouge pas)."""
    out, _tags, joins, closings = chain_tagged(contours, [None] * len(contours), tol, link)
    return out, joins, closings


def chain_tagged(contours: list[Contour], tags: list, tol: float = 0.01,
                 link: float = 0.0) -> tuple[list[Contour], list, int, int]:
    """Comme `chain`, chaque contour portant une étiquette (sa couleur…) : rend (contours, étiquettes, raccords,
    fermetures). Une chaîne garde l'étiquette du morceau dont elle part (le premier dans l'ordre donné)."""
    done = [c for c in contours if c.closed or not c.segments]
    done_tags = [t for c, t in zip(contours, tags) if c.closed or not c.segments]
    opens = [c for c in contours if not c.closed and c.segments]
    open_tags = [t for c, t in zip(contours, tags) if not c.closed and c.segments]
    reach = max(tol, link)
    cell = max(reach, 1e-9) * 2
    grid: dict[tuple, list] = defaultdict(list)

    def key(p):
        return (math.floor(p[0] / cell), math.floor(p[1] / cell))

    for i, c in enumerate(opens):
        grid[key(c.start)].append((i, 0))
        grid[key(c.end)].append((i, 1))
    used = [False] * len(opens)

    def near(p):
        kx, ky = key(p)
        best = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for i, which in grid.get((kx + dx, ky + dy), ()):
                    if used[i]:
                        continue
                    q = opens[i].start if which == 0 else opens[i].end
                    d = math.dist(p, q)
                    if d <= reach and (best is None or d < best[0]):
                        best = (d, i, which)
        return best

    def own_end_first(segs, hit) -> bool:
        """Son autre bout est plus près que le contour voisin : il se fermera."""
        return (len(segs) > 1 or not isinstance(segs[0], Line)) and math.dist(segs[-1].end, segs[0].start) < hit[0]

    joins = closings = 0
    out, out_tags = [], []
    for i, c0 in enumerate(opens):
        if used[i]:
            continue
        used[i] = True
        segs = list(c0.segments)
        while True:                                    # vers l'avant
            hit = near(segs[-1].end)
            if hit is None or own_end_first(segs, hit):
                break
            d, j, which = hit
            used[j] = True
            nxt = list((opens[j] if which == 0 else opens[j].reversed()).segments)
            if d <= tol:
                nxt[0] = _with_start(nxt[0], segs[-1].end)
            else:
                segs.append(Line(segs[-1].end, nxt[0].start))
            segs += nxt
            joins += 1
        while True:                                    # vers l'arrière
            hit = near(segs[0].start)
            if hit is None or own_end_first(segs, hit):
                break
            d, j, which = hit
            used[j] = True
            prev = list((opens[j] if which == 1 else opens[j].reversed()).segments)
            if d <= tol:
                prev[-1] = _with_end(prev[-1], segs[0].start)
            else:
                prev.append(Line(prev[-1].end, segs[0].start))
            segs = prev + segs
            joins += 1
        gap = math.dist(segs[-1].end, segs[0].start)
        closed = gap <= reach and (len(segs) > 1 or not isinstance(segs[0], Line))
        if closed:
            if gap <= tol:
                segs[-1] = _with_end(segs[-1], segs[0].start)
            else:
                segs.append(Line(segs[-1].end, segs[0].start))
            closings += 1
        out.append(Contour(segs, closed))
        out_tags.append(open_tags[i])
    return done + out, done_tags + out_tags, joins, closings
