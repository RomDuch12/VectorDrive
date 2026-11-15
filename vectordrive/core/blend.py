"""Raccordement de deux traits ouverts (les « raccordements » de TypeEdit) :
un arc tangent de rayon r relie les deux traits, qui sont coupés ou
prolongés jusqu'à leurs points de tangence ; r = 0 donne un coin vif (les
deux traits prolongés ou coupés jusqu'à leur intersection).

Droites, arcs et Bézier : le centre de l'arc est une intersection des
courbes parallèles exactes à ±r des deux traits (prolongés au besoin par
leur tangente), les points de tangence ses pieds sur chaque trait. Parmi
les centres possibles, on garde le plus proche du coin dont les deux
points de tangence tombent sur les parties gardées (avant l'intersection
des traits).

Raccord en courbe (comme BLEND en DAO, d'après CADCraft — storytold/cadcraft,
© 2026 ArtCraft Team and the CADCraft contributors, MIT OR Apache-2.0,
utilisé sous MIT, `crates/engine/src/cmd/modify2/blend.rs`) : les traits
restent entiers, une courbe relie leurs bouts dans le prolongement de
chacun.
"""
from __future__ import annotations

import math

from .geom import Contour, Cubic, Line, Path, arc_conics, dist
from .parallel import _with_end, _with_start, parallel_raw
from .trim import nearest_param, piece, segment_crossings


def _corner_ends(a: Contour, b: Contour):
    """(a_bout_au_coin, b_bout_au_coin) : True = la fin du contour."""
    best = None
    for ea in (False, True):
        for eb in (False, True):
            d = dist(a.end if ea else a.start, b.end if eb else b.start)
            if best is None or d < best[0]:
                best = (d, ea, eb)
    return best[1], best[2]


def _oriented(c: Contour, corner_at_end: bool) -> Contour:
    """Le contour parcouru du bout gardé vers le coin."""
    return c if corner_at_end else c.reversed()


def _extended(c: Contour, length: float) -> Contour:
    """Prolonge la fin du contour par une droite dans sa tangente."""
    s = c.segments[-1]
    cp = s.controls()
    q = cp[-1]
    for p in reversed(cp[:-1]):
        d = (q[0] - p[0], q[1] - p[1])
        n = math.hypot(*d)
        if n > 1e-12:
            far = (q[0] + d[0] / n * length, q[1] + d[1] / n * length)
            if isinstance(s, Line):                     # une droite s'allonge
                return Contour(c.segments[:-1] + [Line(s.p0, far)], False)
            return Contour(c.segments + [Line(q, far)], False)
    return c


def _crossings(a: Contour, b: Contour) -> list[tuple[float, float]]:
    out = []
    for i, sa in enumerate(a.segments):
        for j, sb in enumerate(b.segments):
            out += [(i + ta, j + tb) for ta, tb in segment_crossings(sa, sb)]
    return out


def _point(c: Contour, g: float):
    n = len(c.segments)
    i = min(int(math.floor(g)), n - 1)
    return c.segments[i].point(g - i)


def blend(a: Contour, b: Contour, r: float) -> Contour | None:
    """Contour ouvert : bout gardé de a → (arc de rayon r) → bout gardé de b.
    None si aucun raccordement n'est possible."""
    if a.closed or b.closed or not a.segments or not b.segments:
        return None
    ea, eb = _corner_ends(a, b)
    A, B = _oriented(a, ea), _oriented(b, eb)          # du bout gardé vers le coin
    reach = 4 * (r + dist(A.end, B.end) + max(A.length(), B.length()))
    Ax, Bx = _extended(A, reach), _extended(B, reach)
    hits = _crossings(Ax, Bx)
    if not hits:
        return None
    # le coin : l'intersection (des traits prolongés) la plus proche des bouts
    gxa, gxb = min(hits, key=lambda h: dist(_point(Ax, h[0]), A.end) + dist(_point(Bx, h[1]), B.end))
    if r <= 1e-12:
        pa, pb = piece(Ax, 0.0, gxa), piece(Bx, 0.0, gxb)
        tail = pb.reversed().segments
        tail[0] = _with_start(tail[0], pa.end)
        return Contour(pa.segments + tail, False)
    corner = _point(Ax, gxa)
    best = None
    for sa in (1, -1):
        oa = parallel_raw(Ax, sa * r)
        for sb in (1, -1):
            ob = parallel_raw(Bx, sb * r)
            for g1, g2 in _crossings(oa, ob):
                c = _point(oa, g1)
                ga, da = nearest_param(Ax, c)
                gb, db = nearest_param(Bx, c)
                if abs(da - r) > 1e-6 * max(1.0, r) or abs(db - r) > 1e-6 * max(1.0, r):
                    continue
                # les points de tangence doivent tomber sur les parties gardées
                if ga > gxa + 1e-9 or gb > gxb + 1e-9 or ga < 1e-9 or gb < 1e-9:
                    continue
                score = dist(c, corner)
                if best is None or score < best[0]:
                    best = (score, c, ga, gb)
    if best is None:
        return None
    _, c, ga, gb = best
    pa, pb = piece(Ax, 0.0, ga), piece(Bx, 0.0, gb)
    ta, tb = pa.end, pb.end
    a0 = math.degrees(math.atan2(ta[1] - c[1], ta[0] - c[0]))
    a1 = math.degrees(math.atan2(tb[1] - c[1], tb[0] - c[0]))
    sweep = (a1 - a0 + 180) % 360 - 180                   # le petit arc
    arc = arc_conics(c, r, r, a0, sweep)
    if arc:
        arc[0] = _with_start(arc[0], ta)
        arc[-1] = _with_end(arc[-1], tb)
    tail = pb.reversed().segments
    return Contour(pa.segments + arc + tail, False)


def blend_paths(pa: Path, pb: Path, r: float) -> Path | None:
    """Raccordement de deux objets d'un seul contour ouvert chacun."""
    if len(pa.contours) != 1 or len(pb.contours) != 1:
        return None
    c = blend(pa.contours[0], pb.contours[0], r)
    return Path([c]) if c is not None else None


def curve_bridge(p1, t1, p2, t2, smooth: bool = False) -> Contour | None:
    """Courbe de p1 à p2 qui part de p1 dans la direction t1 et arrive en p2
    depuis la direction t2 (t1, t2 : directions sortantes des traits, comme
    `blend_spline` de CADCraft) ; tangente : une Bézier, poignées au tiers de
    l'écart ; lisse : la courbe de degré 5 de CADCraft (poignées à 1/5 et
    2/5 de l'écart, courbure nulle aux deux bouts : raccord sans à-coup sur un
    trait droit), en morceaux de Bézier de mêmes bouts et mêmes dérivées
    qu'elle (à 5 µm + 0,01 % de l'écart près). None : bouts confondus."""
    d = dist(p1, p2)
    n1, n2 = math.hypot(*t1), math.hypot(*t2)
    if d < 1e-9 or n1 < 1e-12 or n2 < 1e-12:
        return None
    u1, u2 = (t1[0] / n1, t1[1] / n1), (t2[0] / n2, t2[1] / n2)

    def at(p, u, k):
        return (p[0] + u[0] * k, p[1] + u[1] * k)

    if not smooth:
        return Contour([Cubic(p1, at(p1, u1, d / 3), at(p2, u2, d / 3), p2)], False)
    C = [p1, at(p1, u1, d / 5), at(p1, u1, 2 * d / 5), at(p2, u2, 2 * d / 5), at(p2, u2, d / 5), p2]

    def q(t):                                               # point et dérivée de la courbe de degré 5
        x = y = dx = dy = 0.0
        for i in range(6):
            b = math.comb(5, i) * t ** i * (1 - t) ** (5 - i)
            x, y = x + b * C[i][0], y + b * C[i][1]
        for i in range(5):
            b = 5 * math.comb(4, i) * t ** i * (1 - t) ** (4 - i)
            dx, dy = dx + b * (C[i + 1][0] - C[i][0]), dy + b * (C[i + 1][1] - C[i][1])
        return (x, y), (dx, dy)

    tol = 0.005 + d * 1e-4
    for n in (2, 4, 6, 8, 12, 16, 24, 32):
        segs, err = [], 0.0
        for j in range(n):
            ta, tb = j / n, (j + 1) / n
            (a, da), (b, db) = q(ta), q(tb)
            h = (tb - ta) / 3
            s = Cubic(p1 if j == 0 else a, (a[0] + da[0] * h, a[1] + da[1] * h), (b[0] - db[0] * h, b[1] - db[1] * h),
                      p2 if j == n - 1 else b)
            segs.append(s)
            err = max([err] + [dist(s.point(k / 4), q(ta + (tb - ta) * k / 4)[0]) for k in (1, 2, 3)])
        if err <= tol:
            break
    return Contour(segs, False)


def bridge(a: Contour, b: Contour | None = None, smooth: bool = False) -> tuple[Contour, Contour | None] | None:
    """Raccord en courbe entre les bouts les plus proches de deux contours
    ouverts (b None : entre les deux bouts de a) ; rend (courbe, contour
    joint — fermé pour un seul contour) ou None (contour fermé, bouts qui se
    touchent déjà, trait droit seul : la courbe reviendrait sur lui)."""
    from .trim import _end_direction
    if a.closed or not a.segments or b is not None and (b.closed or not b.segments):
        return None
    if b is None:
        x, y = a, a
    else:
        ea, eb = _corner_ends(a, b)
        x, y = _oriented(a, ea), _oriented(b, eb).reversed()   # x finit au coin, y en part
    c = curve_bridge(x.end, _end_direction(x.segments[-1], True), y.start,
                     _end_direction(y.segments[0], False), smooth)
    if c is None:
        return None
    if b is None:
        j = Contour(list(a.segments) + list(c.segments), True)
        return (c, j) if abs(j.signed_area()) > 1e-9 * dist(a.start, a.end) ** 2 else None
    return c, Contour(list(x.segments) + list(c.segments) + list(y.segments), False)
