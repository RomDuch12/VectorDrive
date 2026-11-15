"""Mesures sur le dessin (comme MESUREGEOM en DAO) : rayon d'un cercle ou
d'un arc (arc entier, même en plusieurs morceaux), rayon de courbure d'une
courbe au point cliqué, angle entre deux traits droits ou en trois points.
"""
from __future__ import annotations

import math

from .geom import Conic, Line, dist
from .nodes import nearest_on_segment

TOL = 1e-6


def segment_at(path, p):
    """(contour, indice, t, distance) du segment de `path` le plus proche de
    p, ou None (tracé vide)."""
    best = None
    for c in path.contours:
        for i, s in enumerate(c.segments):
            x0, y0, x1, y1 = _bbox(s)
            far = math.hypot(max(x0 - p[0], 0.0, p[0] - x1), max(y0 - p[1], 0.0, p[1] - y1))
            if best is not None and far >= best[3]:
                continue
            t, d = nearest_on_segment(s, p)
            if best is None or d < best[3]:
                best = (c, i, t, d)
    return best


def _bbox(s):
    pts = s.controls()
    xs, ys = [q[0] for q in pts], [q[1] for q in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _circle(s):
    if isinstance(s, Conic):
        cp = s.circle_params()
        if cp is not None and cp[1] > TOL:
            return cp[0], cp[1]
    return None


def _same(a, b):
    return a is not None and b is not None and dist(a[0], b[0]) <= TOL * max(1.0, a[1]) and \
        abs(a[1] - b[1]) <= TOL * max(1.0, a[1])


def _sweep(s, center):
    """Angle balayé par un arc de cercle (degrés, valeur absolue)."""
    tot, prev = 0.0, None
    for k in range(9):
        q = s.point(k / 8)
        a = math.atan2(q[1] - center[1], q[0] - center[0])
        if prev is not None:
            tot += (a - prev + math.pi) % (2 * math.pi) - math.pi
        prev = a
    return abs(math.degrees(tot))


def curvature(s, t: float):
    """(rayon de courbure, centre de courbure) au paramètre t, ou None
    (trait droit, point d'inflexion)."""
    h = 1e-4
    t0, t1 = max(0.0, t - h), min(1.0, t + h)
    tm = (t0 + t1) / 2
    hh = (t1 - t0) / 2
    p0, pm, p1 = s.point(t0), s.point(tm), s.point(t1)
    dx, dy = (p1[0] - p0[0]) / (2 * hh), (p1[1] - p0[1]) / (2 * hh)
    ddx, ddy = (p1[0] - 2 * pm[0] + p0[0]) / (hh * hh), (p1[1] - 2 * pm[1] + p0[1]) / (hh * hh)
    sp = math.hypot(dx, dy)
    cross = dx * ddy - dy * ddx
    if sp < 1e-12 or abs(cross) < 1e-12 * sp ** 3:
        return None
    r = sp ** 3 / abs(cross)
    nx, ny = -dy / sp, dx / sp
    if cross < 0:
        nx, ny = -nx, -ny
    q = s.point(t)
    return r, (q[0] + nx * r, q[1] + ny * r)


def radius_info(path, p) -> dict | None:
    """Ce que vaut le trait le plus proche de p :
    {'kind': 'circle', 'center', 'r'} (cercle entier),
    {'kind': 'arc', 'center', 'r', 'sweep', 'length', 'start', 'end'},
    {'kind': 'line', 'length', 'angle', 'start', 'end'},
    {'kind': 'curve', 'r', 'center', 'point'} (rayon de courbure en p) ou
    {'kind': 'flat', 'point'} (courbe droite à cet endroit) ; None : rien."""
    got = segment_at(path, p)
    if got is None:
        return None
    c, i, t, _d = got
    s = c.segments[i]
    if isinstance(s, Line):
        return {'kind': 'line', 'length': dist(s.start, s.end), 'start': s.start, 'end': s.end,
                'angle': math.degrees(math.atan2(s.end[1] - s.start[1], s.end[0] - s.start[0]))}
    ci = _circle(s)
    if ci is not None:
        n = len(c.segments)
        lo = hi = i                                  # morceaux voisins du même cercle : un seul arc
        while hi - lo + 1 < n:
            j = hi + 1
            if j >= n and not c.closed or not _same(_circle(c.segments[j % n]), ci):
                break
            hi = j
        while hi - lo + 1 < n:
            j = lo - 1
            if j < 0 and not c.closed or not _same(_circle(c.segments[j % n]), ci):
                break
            lo = j
        parts = [c.segments[k % n] for k in range(lo, hi + 1)]
        sweep = sum(_sweep(q, ci[0]) for q in parts)
        if c.closed and len(parts) == n and abs(sweep - 360.0) < 1e-3:
            return {'kind': 'circle', 'center': ci[0], 'r': ci[1]}
        return {'kind': 'arc', 'center': ci[0], 'r': ci[1], 'sweep': sweep,
                'length': math.radians(sweep) * ci[1], 'start': parts[0].start, 'end': parts[-1].end}
    k = curvature(s, t)
    if k is None:
        return {'kind': 'flat', 'point': s.point(t)}
    return {'kind': 'curve', 'r': k[0], 'center': k[1], 'point': s.point(t)}


def line_at(path, p, tol: float):
    """Trait droit de `path` à moins de `tol` de p : (a, b) ou None."""
    got = segment_at(path, p)
    if got is None or got[3] > tol:
        return None
    s = got[0].segments[got[1]]
    return (s.start, s.end) if isinstance(s, Line) and dist(s.start, s.end) > TOL else None


def angle_3points(v, a, b) -> float | None:
    """Angle en v entre va et vb, de 0 à 180°, ou None (point confondu)."""
    ux, uy, wx, wy = a[0] - v[0], a[1] - v[1], b[0] - v[0], b[1] - v[1]
    if math.hypot(ux, uy) < TOL or math.hypot(wx, wy) < TOL:
        return None
    return abs(math.degrees(math.atan2(ux * wy - uy * wx, ux * wx + uy * wy)))


def lines_angle(l1, l2, p1=None, p2=None) -> dict:
    """Angle entre deux traits droits : {'angle' (0–180°), 'vertex' (point de
    rencontre des droites, ou None si parallèles), 'gap' (écart des
    parallèles)}. Avec les points cliqués p1, p2 : l'angle du secteur où ils
    sont (côté de chaque trait où l'on a cliqué)."""
    (a, b), (c, d) = l1, l2
    rx, ry, sx, sy = b[0] - a[0], b[1] - a[1], d[0] - c[0], d[1] - c[1]
    den = rx * sy - ry * sx
    if abs(den) < 1e-12 * math.hypot(rx, ry) * math.hypot(sx, sy):
        L = math.hypot(rx, ry)
        gap = abs(rx * (c[1] - a[1]) - ry * (c[0] - a[0])) / L
        return {'angle': 0.0, 'vertex': None, 'gap': gap}
    t = ((c[0] - a[0]) * sy - (c[1] - a[1]) * sx) / den
    v = (a[0] + t * rx, a[1] + t * ry)

    def ray(seg, d, p):                              # demi-droite du côté du clic (sinon du bout le plus loin)
        if p is None:
            p = seg[0] if dist(seg[0], v) > dist(seg[1], v) else seg[1]
        return d if (p[0] - v[0]) * d[0] + (p[1] - v[1]) * d[1] >= 0 else (-d[0], -d[1])
    u, w = ray(l1, (rx, ry), p1), ray(l2, (sx, sy), p2)
    ang = angle_3points(v, (v[0] + u[0], v[1] + u[1]), (v[0] + w[0], v[1] + w[1]))
    return {'angle': ang, 'vertex': v, 'gap': 0.0, 'dirs': (u, w)}
