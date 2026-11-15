"""Interpoler entre deux tracés : les formes de passage de l'un à l'autre (TypeEdit : duplication par déformation sur une
courbe ; Inkscape : interpolation entre deux chemins).

Si les deux contours ont la même suite de segments, on interpole leurs points de contrôle : le résultat reste en droites et
en vraies courbes. Sinon, on les rééchantillonne à pas égal et on interpole point par point, en droites.
"""
from __future__ import annotations

import math

import numpy as np

from .geom import Conic, Contour, Cubic, Line, Path, polyline, walker

MIN_POINTS, MAX_POINTS = 64, 720


def _mix(p, q, t: float) -> tuple:
    return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)


def _as_cubic(s):
    if isinstance(s, Cubic):
        return s
    a, b = s.p0, s.p1
    return Cubic(a, _mix(a, b, 1 / 3), _mix(a, b, 2 / 3), b)


def _matches(a: Contour, b: Contour) -> bool:
    if a.closed != b.closed or len(a.segments) != len(b.segments):
        return False
    for x, y in zip(a.segments, b.segments):
        if isinstance(x, Conic) != isinstance(y, Conic):
            return False
    return True


def _center(c: Contour) -> tuple:
    x0, y0, x1, y1 = c.bbox()
    return (x0 + x1) / 2, (y0 + y1) / 2


def _same_way(a: Contour, b: Contour) -> Contour:
    """b parcouru dans le sens de a, pour que la forme de passage ne se retourne pas."""
    if a.closed:
        return b.reversed() if (a.signed_area() > 0) != (b.signed_area() > 0) else b
    ca, cb = _center(a), _center(b)
    keep = math.dist((a.start[0] - ca[0], a.start[1] - ca[1]), (b.start[0] - cb[0], b.start[1] - cb[1]))
    back = math.dist((a.start[0] - ca[0], a.start[1] - ca[1]), (b.end[0] - cb[0], b.end[1] - cb[1]))
    return b.reversed() if back < keep else b


def _best_start(a: Contour, b: Contour) -> Contour:
    """Le contour fermé b, de même nombre de segments que a, débutant au nœud qui évite de le tordre."""
    ca, cb = _center(a), _center(b)
    n = len(a.segments)
    pa = [(s.start[0] - ca[0], s.start[1] - ca[1]) for s in a.segments]
    pb = [(s.start[0] - cb[0], s.start[1] - cb[1]) for s in b.segments]
    k = min(range(n), key=lambda r: sum(math.dist(pa[i], pb[(i + r) % n]) for i in range(n)))
    return Contour(list(b.segments[k:]) + list(b.segments[:k]), True)


def _exact(a: Contour, b: Contour, t: float) -> Contour:
    out = []
    for x, y in zip(a.segments, b.segments):
        if isinstance(x, Line) and isinstance(y, Line):
            out.append(Line(_mix(x.p0, y.p0, t), _mix(x.p1, y.p1, t)))
        elif isinstance(x, Conic):
            out.append(Conic(_mix(x.p0, y.p0, t), _mix(x.p1, y.p1, t), _mix(x.p2, y.p2, t), x.w + (y.w - x.w) * t))
        else:
            u, v = _as_cubic(x), _as_cubic(y)
            out.append(Cubic(_mix(u.p0, v.p0, t), _mix(u.p1, v.p1, t), _mix(u.p2, v.p2, t), _mix(u.p3, v.p3, t)))
    return Contour(out, a.closed)


def _samples(c: Contour, n: int) -> np.ndarray:
    total, at = walker(c)
    count = n if c.closed else n - 1
    return np.array([at(total * i / count)[0] for i in range(n)])


def _resampled(a: Contour, b: Contour, t: float) -> Contour:
    n = max(MIN_POINTS, min(MAX_POINTS, max(len(a.flatten(0.05)), len(b.flatten(0.05)))))
    pa, pb = _samples(a, n), _samples(b, n)
    if a.closed:                                        # le point de b en face du premier de a, au décalage des centres près
        ra, rb = pa - pa.mean(axis=0), pb - pb.mean(axis=0)
        shift = min(range(n), key=lambda k: float(np.hypot(*(ra - np.roll(rb, -k, axis=0)).T).sum()))
        pb = np.roll(pb, -shift, axis=0)
    q = pa + (pb - pa) * t
    return polyline([(float(x), float(y)) for x, y in q], closed=a.closed)


def _contour(a: Contour, b: Contour, t: float) -> Contour:
    a = a.close() if a.closed else a
    b = b.close() if b.closed else b
    if a.closed != b.closed:                            # un fermé et un ouvert : on les traite tous deux comme fermés
        a, b = a.close(), b.close()
    b = _same_way(a, b)
    if _matches(a, b):
        if a.closed:
            b = _best_start(a, b)
            if not _matches(a, b):
                return _resampled(a, b, t)
        return _exact(a, b, t)
    return _resampled(a, b, t)


def interpolate(pa: Path, pb: Path, t: float) -> Path:
    """La forme de passage : t = 0 donne pa, t = 1 donne pb. ValueError si leur nombre de contours diffère."""
    if len(pa.contours) != len(pb.contours) or not pa.contours:
        raise ValueError('nombre de contours différent')
    return Path([_contour(a, b, t) for a, b in zip(pa.contours, pb.contours)])
