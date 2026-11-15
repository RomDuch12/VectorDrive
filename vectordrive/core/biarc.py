"""Arcs et segments : Béziers et coniques quelconques → arcs de cercle
tangents (biarcs) et droites, à une tolérance donnée.

Pourquoi : une commande numérique suit un arc (G2/G3, `Arc` SimPl) bien
mieux que des centaines de petites droites, et le programme est plus court.

Méthode : pour un morceau de courbe de P0 à P1, de tangentes T0 et T1, le
biarc « à tangentes égales » passe par un point de jonction J tel que les
deux arcs P0→J et J→P1 soient tangents entre eux et aux extrémités. On
mesure l'écart dans les deux sens (points de la courbe → biarc, points du
biarc → courbe) ; au-delà de la tolérance, la courbe est coupée en deux et
chaque moitié recommence. Les cubiques sont d'abord coupées à leurs points
d'inflexion. Un morceau presque droit devient une droite.
"""
from __future__ import annotations

import math

from .geom import Conic, Contour, Cubic, Line, Path, arc_conics

MAX_DEPTH = 14


def _unit(v):
    n = math.hypot(*v)
    return (v[0] / n, v[1] / n) if n > 1e-15 else None


def _tangents(s):
    """Tangentes unitaires au départ et à l'arrivée d'un segment."""
    if isinstance(s, Cubic):
        p0, p1, p2, p3 = s.p0, s.p1, s.p2, s.p3
        t0 = _unit((p1[0] - p0[0], p1[1] - p0[1])) or _unit((p2[0] - p0[0], p2[1] - p0[1])) \
            or _unit((p3[0] - p0[0], p3[1] - p0[1]))
        t1 = _unit((p3[0] - p2[0], p3[1] - p2[1])) or _unit((p3[0] - p1[0], p3[1] - p1[1])) \
            or _unit((p3[0] - p0[0], p3[1] - p0[1]))
        return t0, t1
    if isinstance(s, Conic):
        p0, p1, p2 = s.p0, s.p1, s.p2
        t0 = _unit((p1[0] - p0[0], p1[1] - p0[1])) or _unit((p2[0] - p0[0], p2[1] - p0[1]))
        t1 = _unit((p2[0] - p1[0], p2[1] - p1[1])) or _unit((p2[0] - p0[0], p2[1] - p0[1]))
        return t0, t1
    d = _unit((s.end[0] - s.start[0], s.end[1] - s.start[1]))
    return d, d


def _arc(p, t, q):
    """Arc de p (tangente t) à q : liste de segments (coniques exactes),
    ou une droite si l'arc dégénère."""
    vx, vy = q[0] - p[0], q[1] - p[1]
    nx, ny = -t[1], t[0]                         # normale à gauche
    den = 2 * (nx * vx + ny * vy)
    if abs(den) < 1e-12 * max(1.0, vx * vx + vy * vy):
        return [Line(p, q)]
    r = (vx * vx + vy * vy) / den                # signé : > 0 centre à gauche
    c = (p[0] + nx * r, p[1] + ny * r)
    a0 = math.degrees(math.atan2(p[1] - c[1], p[0] - c[0]))
    a1 = math.degrees(math.atan2(q[1] - c[1], q[0] - c[0]))
    if r > 0:                                    # trigonométrique
        sweep = (a1 - a0) % 360
    else:
        sweep = -((a0 - a1) % 360)
    if abs(sweep) < 1e-9:
        return [Line(p, q)]
    rr = abs(r)
    segs = arc_conics(c, rr, rr, a0, sweep)
    # extrémités exactes (les angles arrondis ne doivent pas ouvrir le contour)
    if segs:
        segs[0] = Conic(p, segs[0].p1, segs[0].p2, segs[0].w)
        last = segs[-1]
        segs[-1] = Conic(last.p0, last.p1, q, last.w)
    return segs


def biarc(p0, t0, p1, t1):
    """Biarc à tangentes égales : liste de segments de p0 à p1."""
    vx, vy = p1[0] - p0[0], p1[1] - p0[1]
    c = vx * vx + vy * vy
    if c < 1e-24:
        return []
    tx, ty = t0[0] + t1[0], t0[1] + t1[1]
    b = 2 * (vx * tx + vy * ty)
    a = 2 * (1 - (t0[0] * t1[0] + t0[1] * t1[1]))
    if abs(a) < 1e-12:
        vt2 = vx * t1[0] + vy * t1[1]
        if abs(vt2) < 1e-12:
            return [Line(p0, p1)]
        d = c / (4 * vt2)
    else:
        disc = b * b + 4 * a * c
        d = (-b + math.sqrt(max(0.0, disc))) / (2 * a)
    jx = (p0[0] + p1[0] + d * (t0[0] - t1[0])) / 2
    jy = (p0[1] + p1[1] + d * (t0[1] - t1[1])) / 2
    j = (jx, jy)
    first = _arc(p0, t0, j)
    tj = _unit((j[0] - (p0[0] if not first else first[-1].p1[0]),
                j[1] - (p0[1] if not first else first[-1].p1[1])))
    # tangente au point de jonction : celle de la fin du premier arc
    last = first[-1]
    if isinstance(last, Conic):
        tj = _unit((last.p2[0] - last.p1[0], last.p2[1] - last.p1[1])) or tj
    else:
        tj = _unit((j[0] - p0[0], j[1] - p0[1])) or tj
    return first + _arc(j, tj, p1)


def _dist_to_segment(p, s) -> float:
    if isinstance(s, Conic):
        cp = s.circle_params()
        if cp:
            (cx, cy), r, a0, sweep = cp
            ang = math.degrees(math.atan2(p[1] - cy, p[0] - cx))
            rel = (ang - a0) % 360 if sweep > 0 else (a0 - ang) % 360
            if rel <= abs(sweep) + 1e-9:
                return abs(math.hypot(p[0] - cx, p[1] - cy) - r)
            return min(math.dist(p, s.start), math.dist(p, s.end))
    # droite (ou repli) : distance au segment
    a, b = s.start, s.end
    ab = (b[0] - a[0], b[1] - a[1])
    L2 = ab[0] ** 2 + ab[1] ** 2
    t = 0.0 if L2 < 1e-24 else max(0.0, min(1.0, ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1]) / L2))
    return math.dist(p, (a[0] + t * ab[0], a[1] + t * ab[1]))


def _deviation(curve, segs, tol: float = 0.01) -> float:
    """Écart maximal entre la courbe et son approximation, dans les deux sens."""
    import numpy as np
    from .cleanup import _dist_to_polyline
    if not segs:
        return math.dist(curve.start, curve.end)
    worst = 0.0
    for k in range(1, 16):
        q = curve.point(k / 16)
        worst = max(worst, min(_dist_to_segment(q, s) for s in segs))
        if worst > tol:
            return worst                              # inutile d'aller plus loin
    poly = np.asarray([curve.start] + curve.flatten(min(max(tol / 50, 1e-5), 5e-4)), dtype=float)
    pts = np.asarray([s.point(t) for s in segs for t in (0.25, 0.5, 0.75)], dtype=float)
    return max(worst, float(_dist_to_polyline(pts, poly).max()))


def _inflections(c: Cubic) -> list[float]:
    """Paramètres des points d'inflexion d'une cubique, dans ]0, 1[."""
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = c.p0, c.p1, c.p2, c.p3
    ax, ay = -x0 + 3 * x1 - 3 * x2 + x3, -y0 + 3 * y1 - 3 * y2 + y3
    bx, by = x0 - 2 * x1 + x2, y0 - 2 * y1 + y2
    cx, cy = x1 - x0, y1 - y0
    # B' × B'' ∝ (a×b) t² + (a×c) t + (b×c)
    A = ax * by - ay * bx
    B = ax * cy - ay * cx
    C = bx * cy - by * cx
    roots = []
    if abs(A) < 1e-15:
        if abs(B) > 1e-15:
            roots = [-C / B]
    else:
        disc = B * B - 4 * A * C
        if disc >= 0:
            sq = math.sqrt(disc)
            roots = [(-B - sq) / (2 * A), (-B + sq) / (2 * A)]
    return sorted(t for t in roots if 1e-6 < t < 1 - 1e-6)


def _split_at(c: Cubic, t: float):
    """Découpe exacte d'une cubique au paramètre t (de Casteljau)."""
    lerp = lambda a, b: (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    p01, p12, p23 = lerp(c.p0, c.p1), lerp(c.p1, c.p2), lerp(c.p2, c.p3)
    p012, p123 = lerp(p01, p12), lerp(p12, p23)
    m = lerp(p012, p123)
    return Cubic(c.p0, p01, p012, m), Cubic(m, p123, p23, c.p3)


def segment_to_arcs(s, tol: float, depth: int = 0) -> list:
    if isinstance(s, Line):
        return [s]
    if isinstance(s, Conic) and s.circle_params():
        return [s]
    if depth == 0 and isinstance(s, Cubic):
        parts, rest = [], s
        prev = 0.0
        for t in _inflections(s):
            a, rest = _split_at(rest, (t - prev) / (1 - prev))
            parts.append(a)
            prev = t
        parts.append(rest)
        if len(parts) > 1:
            return [x for part in parts for x in segment_to_arcs(part, tol, 1)]
    # presque droit : une droite suffit
    line = [Line(s.start, s.end)]
    if math.dist(s.start, s.end) > 1e-12 and _deviation(s, line, tol) <= tol:
        return line
    t0, t1 = _tangents(s)
    if t0 is None or t1 is None:
        return line
    segs = biarc(s.start, t0, s.end, t1)
    if segs and _deviation(s, segs, tol) <= tol:
        return segs
    if depth >= MAX_DEPTH:
        return segs or line
    if isinstance(s, Cubic):
        a, b = _split_at(s, 0.5)
    else:
        a, b = s.split()
    return segment_to_arcs(a, tol, depth + 1) + segment_to_arcs(b, tol, depth + 1)


def to_arcs(path: Path, tol: float = 0.01) -> Path:
    """Chemin équivalent fait uniquement de droites et d'arcs de cercle."""
    out = []
    for c in path.contours:
        segs = [x for s in c.segments for x in segment_to_arcs(s, tol)]
        out.append(Contour(segs, c.closed))
    return Path(out)


def stats(path: Path) -> dict:
    n_line = n_arc = n_other = 0
    for c in path.contours:
        for s in c.segments:
            if isinstance(s, Line):
                n_line += 1
            elif isinstance(s, Conic) and s.circle_params():
                n_arc += 1
            else:
                n_other += 1
    return {'droites': n_line, 'arcs': n_arc, 'autres': n_other}
