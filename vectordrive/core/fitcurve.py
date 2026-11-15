"""Approximation et segmentation des contours.

- `approximate` : remplace les suites de petits segments (DXF de DAO,
  vectorisation, courbes surchargées de points) par des courbes de Bézier
  lisses à l'écart voulu — ajustement aux moindres carrés avec
  reparamétrage de Newton et coupe au point le plus éloigné (méthode de
  P. J. Schneider, « An Algorithm for Automatically Fitting Digitized
  Curves », Graphics Gems, 1990). Les angles vifs (au-delà d'un seuil)
  sont gardés, les morceaux droits redeviennent des droites.
- `segment` : l'inverse, les courbes deviennent des segments de droite
  (écart maximal, longueur maximale d'un segment).
"""
from __future__ import annotations

import math

import numpy as np

from .geom import Contour, Cubic, Line, Path


# --- ajustement d'une suite de points ----------------------------------------------

def _unit(v):
    n = float(np.hypot(*v))
    return v / n if n > 1e-15 else v


def _bez(ctrl, u):
    u = u[:, None]
    m = 1 - u
    return (m ** 3) * ctrl[0] + 3 * (m ** 2) * u * ctrl[1] + 3 * m * (u ** 2) * ctrl[2] + (u ** 3) * ctrl[3]


def _bez1(ctrl, u):
    u = u[:, None]
    m = 1 - u
    return 3 * ((m ** 2) * (ctrl[1] - ctrl[0]) + 2 * m * u * (ctrl[2] - ctrl[1]) + (u ** 2) * (ctrl[3] - ctrl[2]))


def _bez2(ctrl, u):
    u = u[:, None]
    return 6 * ((1 - u) * (ctrl[2] - 2 * ctrl[1] + ctrl[0]) + u * (ctrl[3] - 2 * ctrl[2] + ctrl[1]))


def _chord_params(P):
    d = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(P, axis=0).T))])
    return d / d[-1] if d[-1] > 0 else np.linspace(0, 1, len(P))


def _generate(P, u, t0, t1):
    """Contrôles intérieurs aux moindres carrés, tangentes imposées."""
    p0, p3 = P[0], P[-1]
    uu = u[:, None]
    b0, b1, b2, b3 = (1 - uu) ** 3, 3 * (1 - uu) ** 2 * uu, 3 * (1 - uu) * uu ** 2, uu ** 3
    A0, A1 = t0 * b1, t1 * b2
    c00, c01, c11 = (A0 * A0).sum(), (A0 * A1).sum(), (A1 * A1).sum()
    tmp = P - (p0 * (b0 + b1) + p3 * (b2 + b3))
    x0, x1 = (tmp * A0).sum(), (tmp * A1).sum()
    det = c00 * c11 - c01 * c01
    seg = float(np.hypot(*(p3 - p0)))
    al = ar = 0.0
    if abs(det) > 1e-18:
        al, ar = (x0 * c11 - x1 * c01) / det, (c00 * x1 - c01 * x0) / det
    eps = 1e-6 * seg
    if al < eps or ar < eps:
        al = ar = seg / 3
    return np.array([p0, p0 + t0 * al, p3 + t1 * ar, p3])


def _error(P, ctrl, u):
    d = np.hypot(*(_bez(ctrl, u) - P).T)
    if len(P) <= 2:
        return 0.0, len(P) // 2
    k = int(np.argmax(d[1:-1])) + 1
    return float(d[k]), k


def _reparam(P, ctrl, u):
    q, q1, q2 = _bez(ctrl, u) - P, _bez1(ctrl, u), _bez2(ctrl, u)
    num = (q * q1).sum(1)
    den = (q1 * q1).sum(1) + (q * q2).sum(1)
    with np.errstate(divide='ignore', invalid='ignore'):
        step = np.where(np.abs(den) > 1e-15, num / den, 0.0)
    v = np.clip(u - step, 0, 1)
    v[0], v[-1] = 0.0, 1.0
    return np.maximum.accumulate(v)


def fit_points(P: np.ndarray, t0, t1, tol: float, depth: int = 0) -> list[np.ndarray]:
    """Bézier passant à `tol` des points P ; t0 tangente sortante au début,
    t1 tangente entrante (orientée vers l'intérieur) à la fin."""
    n = len(P)
    if n == 2:
        d = float(np.hypot(*(P[1] - P[0]))) / 3
        return [np.array([P[0], P[0] + t0 * d, P[1] + t1 * d, P[1]])]
    u = _chord_params(P)
    ctrl = _generate(P, u, t0, t1)
    err, k = _error(P, ctrl, u)
    if err <= tol:
        return [ctrl]
    if err <= tol * 16:
        for _ in range(12):
            u = _reparam(P, ctrl, u)
            ctrl = _generate(P, u, t0, t1)
            err, k = _error(P, ctrl, u)
            if err <= tol:
                return [ctrl]
    if depth > 40 or n < 3:
        return [np.array([P[0], P[0] + (P[-1] - P[0]) / 3, P[-1] + (P[0] - P[-1]) / 3, P[-1]])]
    tc = _unit(P[k - 1] - P[k + 1])
    if not tc.any():
        tc = _unit(P[k - 1] - P[k])
    return fit_points(P[:k + 1], t0, tc, tol, depth + 1) + fit_points(P[k:], -tc, t1, tol, depth + 1)


def _to_segment(ctrl, tol: float):
    p0, p1, p2, p3 = (tuple(map(float, q)) for q in ctrl)
    ab = ctrl[3] - ctrl[0]
    L = float(np.hypot(*ab))
    if L > 1e-12:
        dev = max(abs(ab[0] * (q[1] - ctrl[0][1]) - ab[1] * (q[0] - ctrl[0][0])) / L for q in ctrl[1:3])
        along = [float(np.dot(q - ctrl[0], ab)) / (L * L) for q in ctrl[1:3]]
        if dev <= tol * 0.25 and all(-1e-9 <= a <= 1 + 1e-9 for a in along):
            return Line(p0, p3)
    return Cubic(p0, p1, p2, p3)


# --- contours ---------------------------------------------------------------------

def _clean(pts):
    out = [pts[0]]
    for q in pts[1:]:
        if math.hypot(q[0] - out[-1][0], q[1] - out[-1][1]) > 1e-9:
            out.append(q)
    return out


def _turn(a, b, c) -> float:
    v1 = (b[0] - a[0], b[1] - a[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    n = math.hypot(*v1) * math.hypot(*v2)
    if n < 1e-24:
        return 0.0
    cos = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / n))
    return math.degrees(math.acos(cos))


def _fit_run(pts, tol, t0=None, t1=None) -> list:
    P = np.asarray(pts, float)
    if len(P) < 2:
        return []
    t0 = _unit(P[1] - P[0]) if t0 is None else t0
    t1 = _unit(P[-2] - P[-1]) if t1 is None else t1
    return [_to_segment(c, tol) for c in fit_points(P, t0, t1, tol)]


def approximate_contour(c: Contour, tol: float, corner: float = 35.0, curves: bool = True) -> Contour:
    """`curves` : ré-ajuster aussi les courbes existantes (sinon seules les
    suites de droites sont approximées, les courbes restent telles quelles)."""
    if not c.segments:
        return c
    if not curves:
        return _approximate_lines_only(c, tol, corner)
    pts = [c.segments[0].start]
    for s in c.segments:
        pts.extend(s.flatten(tol / 8))                   # sans le départ : c'est l'arrivée du précédent
    if c.closed and math.hypot(pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1]) > 1e-9:
        pts.append(pts[0])
    pts = _clean(pts)
    return Contour(_fit_polyline(pts, tol, corner, c.closed), c.closed)


def _fit_polyline(pts, tol, corner, closed) -> list:
    n = len(pts)
    if n < 2:
        return []
    if closed:
        ring = pts[:-1]
        m = len(ring)
        if m < 3:
            return [Line(pts[i], pts[i + 1]) for i in range(n - 1)]
        corners = [i for i in range(m) if _turn(ring[i - 1], ring[i], ring[(i + 1) % m]) > corner]
        if not corners:
            tc = _unit(np.subtract(ring[1], ring[-1]).astype(float))
            return _fit_run(pts, tol, tc, -tc)
        s = corners[0]
        ring = ring[s:] + ring[:s]
        cuts = [(i - s) % m for i in corners] + [m]
        ring = ring + [ring[0]]
        out = []
        for a, b in zip(cuts, cuts[1:]):
            out += _fit_run(ring[a:b + 1], tol)
        return out
    cuts = [0] + [i for i in range(1, n - 1) if _turn(pts[i - 1], pts[i], pts[i + 1]) > corner] + [n - 1]
    out = []
    for a, b in zip(cuts, cuts[1:]):
        out += _fit_run(pts[a:b + 1], tol)
    return out


def _approximate_lines_only(c: Contour, tol: float, corner: float) -> Contour:
    out, run = [], []

    def flush():
        if run:
            out.extend(_fit_polyline(_clean([run[0].start] + [s.end for s in run]), tol, corner, False))
            run.clear()
    segs = list(c.segments)
    if c.closed and all(isinstance(s, Line) for s in segs):
        pts = _clean([segs[0].start] + [s.end for s in segs])
        return Contour(_fit_polyline(pts, tol, corner, True), True)
    for s in segs:
        if isinstance(s, Line):
            run.append(s)
        else:
            flush()
            out.append(s)
    flush()
    return Contour(out, c.closed)


def approximate(path: Path, tol: float = 0.01, corner: float = 35.0, curves: bool = True) -> Path:
    return Path([approximate_contour(c, tol, corner, curves) for c in path.contours])


# --- segmentation -----------------------------------------------------------------

def segment(path: Path, tol: float = 0.01, max_len: float = 0.0, lines_too: bool = False) -> Path:
    """Courbes → droites à `tol` près ; `max_len` > 0 : aucun segment plus
    long (les droites d'origine aussi si `lines_too`)."""
    out = []
    for c in path.contours:
        segs = []
        for s in c.segments:
            if isinstance(s, Line):
                pts = [s.start, s.end]
                cut = lines_too
            else:
                pts = s.flatten(tol)
                cut = True
            for a, b in zip(pts, pts[1:]):
                L = math.hypot(b[0] - a[0], b[1] - a[1])
                k = max(1, math.ceil(L / max_len - 1e-9)) if (cut and max_len > 0) else 1
                prev = a
                for i in range(1, k + 1):
                    q = b if i == k else (a[0] + (b[0] - a[0]) * i / k, a[1] + (b[1] - a[1]) * i / k)
                    segs.append(Line(prev, q))
                    prev = q
        out.append(Contour(segs, c.closed))
    return Path(out)
