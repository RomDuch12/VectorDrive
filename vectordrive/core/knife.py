"""Couteau (comme celui de TypeEdit) : des formes fermées découpées en
morceaux le long d'un trait — droite, polyligne, courbe, ou le bord d'une
autre forme. Le trait doit traverser la forme de part en part ; une forme
qu'il ne coupe pas reste entière. Les morceaux sont des contours fermés.

Les courbes restent des courbes : `_exact` suit le contour et le trait, et rend
le même découpage que le calcul à plat de shapely, qui garde le dernier mot.
S'ils diffèrent (contours qui se croisent, trait tangent…), on rend le calcul à
plat, aplati à 2 µm près.

`open_along` ne referme rien : il coupe contours ouverts et fermés à chaque
intersection, et rien ne bouge (TypeEdit : Couper un contour).
"""
from __future__ import annotations

from .geom import Conic, Contour, Cubic, Line, Path
from .pathops import FLATTEN, _from_shapely, _to_shapely
from .portion import point_at
from .trim import cut_params, nearest_param, piece


def cut(path: Path, knife: Path) -> list[Path]:
    """Morceaux de `path` (contours fermés, règle pair-impair) coupés par
    les traits de `knife` ; [path] s'il n'est pas coupé."""
    from shapely.geometry import LineString
    from shapely.ops import split, unary_union
    closed = Path([c.close() for c in path.contours if c.closed])
    rest = [c for c in path.contours if not c.closed]
    region = _to_shapely(closed)
    lines = [LineString(pts) for pts in knife.flatten(FLATTEN) if len(pts) >= 2]
    if region.is_empty or not lines:
        return [path]
    parts = split(region, unary_union(lines))
    pieces = [g for g in getattr(parts, 'geoms', [parts]) if not g.is_empty and g.area > 1e-9]
    if len(pieces) <= 1:
        return [path]
    pieces.sort(key=lambda g: (-g.centroid.y, g.centroid.x))      # de haut en bas, de gauche à droite
    out = None
    if len(knife.contours) == 1:
        try:
            out = _exact(closed, knife.contours[0], region, [g.area for g in pieces])
        except (ValueError, ZeroDivisionError, IndexError, KeyError):
            out = None                                  # le calcul à plat reste juste
    out = out or [_from_shapely(g) for g in pieces]
    if rest:                                            # les traits ouverts de la forme ne se perdent pas
        out[0] = Path(list(out[0].contours) + rest)
    return out


def open_along(path: Path, knife: Path) -> tuple:
    """(tracé coupé, nombre de morceaux créés) ; (None, 0) si le trait ne coupe rien. Chaque contour touché est ouvert à
    chaque intersection, et ses morceaux restent dans le même objet, bout à bout."""
    cutters = [s for k in knife.contours for s in k.segments]
    out, made = [], 0
    for c in path.contours:
        c2 = c.close() if c.closed else c
        gs = cut_params(c2, cutters, self_cut=False)
        if not gs:
            out.append(c)
            continue
        if c2.closed:
            parts = [piece(c2, gs[i], gs[(i + 1) % len(gs)]) for i in range(len(gs))]
        else:
            ends = [0.0] + gs + [float(len(c2.segments))]
            parts = [piece(c2, ends[i], ends[i + 1]) for i in range(len(ends) - 1)]
        out.extend(parts)
        made += len(parts)
    return (Path(out), made) if made else (None, 0)


def points_along(path: Path, knife: Path) -> list:
    """Les points où le trait couperait ce tracé."""
    cutters = [s for k in knife.contours for s in k.segments]
    out = []
    for c in path.contours:
        c2 = c.close() if c.closed else c
        out += [point_at(c2, g) for g in cut_params(c2, cutters, self_cut=False)]
    return out


def _ends(segs: list, a: tuple, b: tuple) -> list:
    """Les segments, leurs deux bouts posés exactement sur a et b."""
    def moved(s, start=None, end=None):
        p0 = start if start is not None else s.p0
        if isinstance(s, Line):
            return Line(p0, end if end is not None else s.p1)
        if isinstance(s, Cubic):
            return Cubic(p0, s.p1, s.p2, end if end is not None else s.p3)
        if isinstance(s, Conic):
            return Conic(p0, s.p1, end if end is not None else s.p2, s.w)
        raise ValueError(type(s).__name__)
    if len(segs) == 1:
        return [moved(segs[0], a, b)]
    return [moved(segs[0], start=a)] + segs[1:-1] + [moved(segs[-1], end=b)]


def _exact(closed: Path, blade: Contour, region, areas: list) -> list | None:
    """Le découpage en suivant les segments d'origine ; None s'il ne rend pas exactement les aires de `areas`."""
    from shapely.geometry import Point, Polygon

    def poly(c):
        return Polygon(c.flatten(FLATTEN)).buffer(0)
    shapes = [poly(c) for c in closed.contours]
    oriented = []                                       # l'intérieur à gauche de chaque contour
    depths = []
    for i, c in enumerate(closed.contours):
        q = Point(c.start)
        depth = sum(1 for j, sh in enumerate(shapes) if j != i and sh.contains(q))
        depths.append(depth)
        oriented.append(c if (c.signed_area() > 0) == (depth % 2 == 0) else c.reversed())
    cross = []                                          # (paramètre sur le trait, contour, paramètre sur le contour)
    for i, c in enumerate(oriented):
        for g in cut_params(c, list(blade.segments), self_cut=False):
            cross.append((nearest_param(blade, point_at(c, g))[0], i, g))
    if not cross:
        return None
    cross.sort()
    n = len(cross)
    points = [point_at(oriented[i], g) for _t, i, g in cross]
    partner, chord = {}, {}
    pairs = [(k, k + 1) for k in range(n - 1)]
    if blade.closed and n > 1:
        pairs.append((n - 1, 0))
    for x, y in pairs:
        if abs(cross[x][0] - cross[y][0]) < 1e-9:
            return None                                 # deux contours coupés au même point
        seg = piece(blade, cross[x][0], cross[y][0])
        if not region.contains(Point(point_at(seg, len(seg.segments) / 2))):
            continue
        if x in partner or y in partner:
            return None
        partner[x], partner[y] = y, x
        chord[x, y] = _ends(list(seg.segments), points[x], points[y])
        chord[y, x] = _ends(list(seg.reversed().segments), points[y], points[x])
    if not partner:
        return None
    following, arc = {}, {}                             # d'un point de coupe au suivant, le long de son contour
    for i, c in enumerate(oriented):
        here = sorted((k for k in range(n) if cross[k][1] == i), key=lambda k: cross[k][2])
        for a, k in enumerate(here):
            nxt = here[(a + 1) % len(here)]
            following[k] = nxt
            arc[k] = _ends(list(piece(c, cross[k][2], cross[nxt][2]).segments), points[k], points[nxt])
    used, loops = set(), []
    for first in range(n):
        if first in used:
            continue
        segs, cur = [], first
        while True:
            used.add(cur)
            segs += arc[cur]
            end = following[cur]
            if end in partner:
                segs += chord[end, partner[end]]
                end = partner[end]
            if end == first:
                break
            if end in used:
                return None
            cur = end
        loops.append(Contour(segs, True))
    uncut = [i for i in range(len(oriented)) if not any(cross[k][1] == i for k in range(n))]
    outers = [c for c in loops if c.signed_area() > 0] + [oriented[i] for i in uncut if depths[i] % 2 == 0]
    holes = [c for c in loops if c.signed_area() <= 0] + [oriented[i] for i in uncut if depths[i] % 2 == 1]
    out = [[c] for c in outers]
    outer_shapes = [poly(c) for c in outers]
    for h in holes:
        q = Point(point_at(h, 0.5))
        hit = [k for k, sh in enumerate(outer_shapes) if sh.contains(q)]
        if not hit:
            return None
        out[min(hit, key=lambda k: outer_shapes[k].area)].append(h)
    got = [(_to_shapely(Path(cs)), Path(cs)) for cs in out]
    if len(got) != len(areas):
        return None
    for mine, ref in zip(sorted(g.area for g, _p in got), sorted(areas)):
        if abs(mine - ref) > max(1e-3, ref * 1e-3):
            return None
    got.sort(key=lambda x: (-x[0].centroid.y, x[0].centroid.x))
    return [p for _g, p in got]
