"""Cercles tangents à des traits droits ou à des cercles (arcs compris) :
de rayon donné tangent à deux objets (« TTR » en DAO), ou tangent à trois
objets (« TTT »). Parmi les solutions, celle dont les points de contact
tombent le plus près des points cliqués.

D'après CADCraft (`crates/engine/src/cmd/curves.rs` : `ttr`, `ttt`, voir
THIRD_PARTY_NOTICES.md) : rayon donné, centres aux intersections des
parallèles décalées du rayon ; trois objets, méthode de Newton sur chaque
combinaison de côtés (dedans, dehors, englobant).

Un objet est `('line', a, b)` (droite infinie par a et b) ou
`('circle', centre, rayon)`.
"""
from __future__ import annotations

import math

from .geom import Conic, Line, _seg_dist, dist

EPS = 1e-9


# --- objets ------------------------------------------------------------------------------

def _project(a, b, p):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    if L2 < 1e-24:
        return a
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2
    return (a[0] + t * dx, a[1] + t * dy)


def touch(obj, c, r):
    """Point où le cercle (c, r) tangent à l'objet le touche."""
    if obj[0] == 'line':
        return _project(obj[1], obj[2], c)
    k, R = obj[1], obj[2]
    d = dist(c, k)
    ux, uy = ((c[0] - k[0]) / d, (c[1] - k[1]) / d) if d > 1e-15 else (1.0, 0.0)
    p1, p2 = (k[0] + ux * R, k[1] + uy * R), (k[0] - ux * R, k[1] - uy * R)
    return p1 if abs(dist(p1, c) - r) <= abs(dist(p2, c) - r) else p2


def _residual(obj, c, r):
    if obj[0] == 'line':
        return dist(_project(obj[1], obj[2], c), c) - r
    d = dist(c, obj[1])
    return min(abs(d - (obj[2] + r)), abs(d - abs(obj[2] - r)))


def _offsets(obj, r):
    if obj[0] == 'line':
        a, b = obj[1], obj[2]
        L = dist(a, b)
        nx, ny = -(b[1] - a[1]) / L, (b[0] - a[0]) / L
        return [('line', (a[0] + nx * s, a[1] + ny * s), (b[0] + nx * s, b[1] + ny * s)) for s in (r, -r)]
    out = [('circle', obj[1], obj[2] + r)]
    if abs(obj[2] - r) > EPS:
        out.append(('circle', obj[1], abs(obj[2] - r)))
    return out


def _line_line(a, b):
    (p, p2), (q, q2) = (a[1], a[2]), (b[1], b[2])
    rx, ry = p2[0] - p[0], p2[1] - p[1]
    sx, sy = q2[0] - q[0], q2[1] - q[1]
    den = rx * sy - ry * sx
    if abs(den) < 1e-12 * max(1.0, math.hypot(rx, ry) * math.hypot(sx, sy)):
        return []
    t = ((q[0] - p[0]) * sy - (q[1] - p[1]) * sx) / den
    return [(p[0] + t * rx, p[1] + t * ry)]


def _line_circle(ln, ci):
    a, b = ln[1], ln[2]
    k, R = ci[1], ci[2]
    f = _project(a, b, k)
    h = dist(f, k)
    if h > R + 1e-12:
        return []
    L = dist(a, b)
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    s = math.sqrt(max(0.0, R * R - h * h))
    return [(f[0] + ux * s, f[1] + uy * s), (f[0] - ux * s, f[1] - uy * s)]


def _circle_circle(c1, c2):
    (k1, r1), (k2, r2) = (c1[1], c1[2]), (c2[1], c2[2])
    d = dist(k1, k2)
    if d < 1e-15 or d > r1 + r2 + 1e-12 or d < abs(r1 - r2) - 1e-12:
        return []
    a = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
    h = math.sqrt(max(0.0, r1 * r1 - a * a))
    ux, uy = (k2[0] - k1[0]) / d, (k2[1] - k1[1]) / d
    m = (k1[0] + ux * a, k1[1] + uy * a)
    return [(m[0] - uy * h, m[1] + ux * h), (m[0] + uy * h, m[1] - ux * h)]


def _intersect(a, b):
    if a[0] == 'line' and b[0] == 'line':
        return _line_line(a, b)
    if a[0] == 'line':
        return _line_circle(a, b)
    if b[0] == 'line':
        return _line_circle(b, a)
    return _circle_circle(a, b)


def _score(c, r, objs):
    return sum(dist(touch(o, c, r), p) for o, p in objs)


# --- rayon donné --------------------------------------------------------------------------

def ttr(o1, p1, o2, p2, r: float):
    """Cercle de rayon `r` tangent aux deux objets, contacts au plus près
    des points cliqués : (centre, rayon) ou None."""
    if not (math.isfinite(r) and r > EPS):
        return None
    objs = [(o1, p1), (o2, p2)]
    best = None
    tol = 1e-6 * max(r, 1.0)
    for a in _offsets(o1, r):
        for b in _offsets(o2, r):
            for c in _intersect(a, b):
                if not all(math.isfinite(v) for v in c):
                    continue
                if abs(_residual(o1, c, r)) > tol or abs(_residual(o2, c, r)) > tol:
                    continue
                sc = _score(c, r, objs)
                if best is None or sc < best[0]:
                    best = (sc, c)
    return (best[1], r) if best else None


# --- trois objets --------------------------------------------------------------------------

def _solve3(m, b):
    def det(m):
        return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
                + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))
    d = det(m)
    if not math.isfinite(d) or abs(d) < 1e-14:
        return None
    out = []
    for k in range(3):
        mk = [list(row) for row in m]
        for row, bv in zip(mk, b):
            row[k] = bv
        out.append(det(mk) / d)
    return out


def _equations(obj):
    """Équations de tangence signées f(x, y, r) = 0 et leur gradient, une
    par côté possible."""
    if obj[0] == 'line':
        a, b = obj[1], obj[2]
        L = dist(a, b)
        nx, ny = -(b[1] - a[1]) / L, (b[0] - a[0]) / L
        c0 = -(nx * a[0] + ny * a[1])

        def line_eq(s):
            return lambda x: (nx * x[0] + ny * x[1] + c0 - s * x[2], [nx, ny, -s])
        return [line_eq(1.0), line_eq(-1.0)]
    k, R = obj[1], obj[2]

    def circle_eq(s, enclose):
        def f(x):
            dx, dy = x[0] - k[0], x[1] - k[1]
            ln = max(math.hypot(dx, dy), 1e-12)
            g = [dx / ln, dy / ln]
            if enclose:
                return ln - (x[2] - R), [g[0], g[1], -1.0]
            return ln - (R + s * x[2]), [g[0], g[1], -s]
        return f
    return [circle_eq(1.0, False), circle_eq(-1.0, False), circle_eq(0.0, True)]


def ttt(objs):
    """Cercle tangent aux trois objets [(objet, point cliqué)] × 3, contacts
    au plus près des clics : (centre, rayon) ou None."""
    from .shapes import circumcircle
    (o1, p1), (o2, p2), (o3, p3) = objs
    cen = ((p1[0] + p2[0] + p3[0]) / 3, (p1[1] + p2[1] + p3[1]) / 3)
    rad = (dist(cen, p1) + dist(cen, p2) + dist(cen, p3)) / 3
    starts = [[cen[0], cen[1], max(rad, 1e-3)]]
    cc = circumcircle(p1, p2, p3)
    if cc:
        starts.append([cc[0][0], cc[0][1], cc[1]])
    scale = max(rad, dist(p1, p2), 1e-6)
    best = None
    for e1 in _equations(o1):
        for e2 in _equations(o2):
            for e3 in _equations(o3):
                for st in starts:
                    x = list(st)
                    ok = False
                    for _i in range(60):
                        (f1, g1), (f2, g2), (f3, g3) = e1(x), e2(x), e3(x)
                        if max(abs(f1), abs(f2), abs(f3)) < 1e-11 * scale:
                            ok = True
                            break
                        dx = _solve3([g1, g2, g3], [-f1, -f2, -f3])
                        if dx is None:
                            break
                        x = [xi + di for xi, di in zip(x, dx)]
                        if not all(math.isfinite(v) for v in x):
                            break
                    if not ok or x[2] <= 1e-9 * scale or x[2] > 1e6 * scale:
                        continue
                    c = (x[0], x[1])
                    sc = _score(c, x[2], objs)
                    if best is None or sc < best[0] - 1e-12:
                        best = (sc, c, x[2])
    return (best[1], best[2]) if best else None


# --- objets d'un dessin ------------------------------------------------------------------------

def object_of(seg):
    """Objet de tangence d'un segment : trait droit → droite ; arc de cercle
    → son cercle ; autre courbe → None."""
    if isinstance(seg, Line):
        return ('line', seg.start, seg.end) if dist(seg.start, seg.end) > EPS else None
    if isinstance(seg, Conic):
        cp = seg.circle_params()
        if cp is not None and cp[1] > EPS:
            return ('circle', cp[0], cp[1])
    return None


def pick(path, p, tol: float = 0.01):
    """Objet de tangence du segment de `path` le plus proche de p (droite ou
    cercle), ou None si ce segment n'est ni droit ni circulaire."""
    best = None
    for c in path.contours:
        for s in c.segments:
            pts = s.flatten(tol)
            d = min((_seg_dist(p, a, b) for a, b in zip(pts, pts[1:])), default=math.inf)
            if best is None or d < best[0]:
                best = (d, s)
    return object_of(best[1]) if best else None
