"""Formes paramétrées : flèches (simple ou double, pointe et corps
réglables), cercle par trois points, cercles reconnus dans des contours,
tangentes à deux cercles et enveloppe (courroie, oblong)."""
from __future__ import annotations

import math
from dataclasses import dataclass

from . import geom
from .geom import Contour, Line, Path


@dataclass
class ArrowSpec:
    length: float = 40.0             # longueur totale (mm)
    shaft_width: float = 6.0         # épaisseur du corps
    head_length: float = 12.0
    head_width: float = 16.0
    double: bool = False             # pointe aux deux bouts
    angle: float = 0.0               # orientation (°, 0 = vers la droite)


def arrow(spec: ArrowSpec, center=(0.0, 0.0)) -> Contour:
    """Contour fermé (sens trigonométrique) d'une flèche centrée sur `center`."""
    L = max(spec.length, 0.1)
    hl = min(max(spec.head_length, 0.0), L / (2 if spec.double else 1))
    hw = max(spec.head_width, spec.shaft_width)
    sw = max(spec.shaft_width, 0.01) / 2
    x0, x1 = -L / 2, L / 2
    pts = [(x1, 0.0), (x1 - hl, hw / 2), (x1 - hl, sw)]
    if spec.double:
        pts += [(x0 + hl, sw), (x0 + hl, hw / 2), (x0, 0.0), (x0 + hl, -hw / 2), (x0 + hl, -sw)]
    else:
        pts += [(x0, sw), (x0, -sw)]
    pts += [(x1 - hl, -sw), (x1 - hl, -hw / 2)]
    a = math.radians(spec.angle)
    ca, sa = math.cos(a), math.sin(a)
    cx, cy = center
    pts = [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in pts]
    return geom.polyline(pts, closed=True)


def circumcircle(a, b, c):
    """(centre, rayon) du cercle passant par trois points ; None s'ils sont alignés."""
    ax, ay = a
    bx, by = b
    cx, cy = c
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return None
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    return (ux, uy), math.hypot(ax - ux, ay - uy)


def circle_3points(a, b, c) -> Contour | None:
    cc = circumcircle(a, b, c)
    return geom.circle(*cc) if cc else None


def circle_2points(a, b) -> Contour | None:
    """Cercle dont `a` et `b` sont les bouts d'un diamètre (CIRCLE 2P,
    d'après CADCraft) ; None si les points se confondent."""
    r = math.dist(a, b) / 2
    return geom.circle(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), r) if r > 1e-9 else None


def arc_center(c, a, b, clockwise: bool = False) -> Contour | None:
    """Arc de centre `c` partant de `a` (qui donne le rayon) jusqu'à la
    direction de `b` (ARC centre, départ, fin, d'après CADCraft) : sens
    trigonométrique, horaire si `clockwise`. None si le rayon est nul, si
    `b` est sur le centre ou dans la direction du départ."""
    r = math.dist(c, a)
    if r < 1e-9 or math.dist(c, b) < 1e-9:
        return None
    a0 = math.degrees(math.atan2(a[1] - c[1], a[0] - c[0]))
    s = (math.degrees(math.atan2(b[1] - c[1], b[0] - c[0])) - a0) % 360.0
    if s < 1e-9 or s > 360.0 - 1e-9:
        return None
    return geom.arc(c, r, a0, s - 360.0 if clockwise else s)


def fit_circle(c: Contour, tol: float = 0.02):
    """(centre, rayon, écart maxi) du cercle des moindres carrés d'un contour
    fermé, s'il en est un au plus à `tol` près ; sinon None."""
    import numpy as np
    if not c.closed or not c.segments:
        return None
    pts = [c.start]
    for s in c.segments:
        pts += s.flatten(tol / 4)
    V = np.array(pts, dtype=float)
    if len(V) < 4:
        return None
    # points le long des côtés aussi : un carré a ses sommets sur un cercle
    t = np.array([0.0, 0.25, 0.5, 0.75])[None, :, None]
    P = (V[:-1, None, :] + (V[1:] - V[:-1])[:, None, :] * t).reshape(-1, 2)
    x, y = P[:, 0], P[:, 1]
    A = np.column_stack([x, y, np.ones_like(x)])
    b = x * x + y * y
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    cx, cy = sol[0] / 2, sol[1] / 2
    r2 = sol[2] + cx * cx + cy * cy
    if r2 <= 0:
        return None
    r = math.sqrt(r2)
    err = float(np.abs(np.hypot(x - cx, y - cy) - r).max())
    # le contour doit faire le tour (pas un arc fermé par une corde)
    ang = np.unwrap(np.arctan2(y - cy, x - cx))
    if abs(ang[-1] - ang[0]) < 2 * math.pi * 0.98 or err > tol:
        return None
    return (float(cx), float(cy)), r, err


def to_circles(path: Path, tol: float = 0.02) -> tuple[Path, int]:
    """Les contours fermés presque circulaires remplacés par des cercles
    exacts (même sens de parcours) ; rend (chemin, nombre de cercles)."""
    out, n = [], 0
    for c in path.contours:
        fit = fit_circle(c, tol)
        if fit is None:
            out.append(c)
            continue
        center, r, _err = fit
        circ = geom.circle(center, r)
        if (circ.signed_area() > 0) != (c.signed_area() > 0):
            circ = circ.reversed()
        out.append(circ)
        n += 1
    return Path(out), n


def merge_collinear(path: Path, tol: float = 0.001) -> tuple[Path, int]:
    """Points alignés retirés : droites consécutives sur une même droite (à
    `tol` près) fusionnées ; rend (chemin, points retirés)."""
    out, removed = [], 0
    for c in path.contours:
        segs = list(c.segments)
        merged: list = []
        for s in segs:
            if merged and isinstance(s, Line) and isinstance(merged[-1], Line):
                p = merged[-1]
                if _collinear(p.p0, p.p1, s.p1, tol) and _same_direction(p, s):
                    merged[-1] = Line(p.p0, s.p1)
                    removed += 1
                    continue
            merged.append(s)
        if c.closed and len(merged) > 2 and isinstance(merged[0], Line) and isinstance(merged[-1], Line):
            last, first = merged[-1], merged[0]
            if _collinear(last.p0, last.p1, first.p1, tol) and _same_direction(last, first):
                merged = [Line(last.p0, first.p1)] + merged[1:-1]
                removed += 1
        out.append(Contour(merged, c.closed))
    return Path(out), removed


def _collinear(a, b, c, tol: float) -> bool:
    (ax, ay), (bx, by), (cx, cy) = a, b, c
    L = math.hypot(cx - ax, cy - ay)
    if L < 1e-12:
        return False
    return abs((bx - ax) * (cy - ay) - (by - ay) * (cx - ax)) / L <= tol


def _same_direction(p: Line, s: Line) -> bool:
    return (p.p1[0] - p.p0[0]) * (s.p1[0] - s.p0[0]) + (p.p1[1] - p.p0[1]) * (s.p1[1] - s.p0[1]) > 0


def circle_tangents(c1, r1: float, c2, r2: float, kind: str = 'externes') -> list[Contour]:
    """Droites tangentes à deux cercles : externes (ne se croisent pas entre
    les cercles), internes (se croisent), ou toutes. Liste vide si les cercles
    ne le permettent pas (l'un dans l'autre ; internes : cercles sécants)."""
    (x1, y1), (x2, y2) = c1, c2
    d = math.hypot(x2 - x1, y2 - y1)
    th = math.atan2(y2 - y1, x2 - x1)
    out = []

    def pt(c, r, a):
        return (c[0] + r * math.cos(a), c[1] + r * math.sin(a))
    if kind in ('externes', 'toutes') and d > abs(r1 - r2) + 1e-9:
        a = math.acos((r1 - r2) / d)
        for s in (1, -1):
            out.append(geom.polyline([pt(c1, r1, th + s * a), pt(c2, r2, th + s * a)]))
    if kind in ('internes', 'toutes') and d > r1 + r2 + 1e-9:
        a = math.acos((r1 + r2) / d)
        for s in (1, -1):
            out.append(geom.polyline([pt(c1, r1, th + s * a), pt(c2, r2, th + s * a + math.pi)]))
    return out


def _circle_meet(c1, rho1: float, c2, rho2: float) -> list:
    """Points communs de deux cercles (0, 1 ou 2)."""
    (x1, y1), (x2, y2) = c1, c2
    d = math.hypot(x2 - x1, y2 - y1)
    if d < 1e-12 or rho1 < 0 or rho2 < 0:
        return []
    a = (rho1 * rho1 - rho2 * rho2 + d * d) / (2 * d)
    h2 = rho1 * rho1 - a * a
    if h2 < -1e-12:
        return []
    h = math.sqrt(max(h2, 0.0))
    ex, ey = (x2 - x1) / d, (y2 - y1) / d
    mx, my = x1 + a * ex, y1 + a * ey
    if h < 1e-9:
        return [(mx, my)]
    return [(mx - h * ey, my + h * ex), (mx + h * ey, my - h * ex)]


def tangent_arcs(c1, r1: float, c2, r2: float, radius: float, enclosing: bool = False) -> list[Contour]:
    """Arcs de raccord de rayon `radius` tangents aux deux cercles (TypeEdit :
    « Arc tangent ») : à l'extérieur des deux (congé), ou les englobant
    (`enclosing`, rayon plus grand que chacun). Chaque arc va d'un point de
    contact à l'autre par le plus court ; deux solutions au plus, aucune si
    le rayon ne permet pas d'atteindre les deux cercles."""
    if radius <= 0:
        return []
    if enclosing:
        if radius <= max(r1, r2):
            return []
        centers = _circle_meet(c1, radius - r1, c2, radius - r2)
    else:
        centers = _circle_meet(c1, r1 + radius, c2, r2 + radius)
    out = []
    for px, py in centers:
        a1 = math.degrees(math.atan2(c1[1] - py, c1[0] - px))
        a2 = math.degrees(math.atan2(c2[1] - py, c2[0] - px))
        sweep = (a2 - a1 + 180.0) % 360.0 - 180.0
        if abs(sweep) < 1e-9:
            continue
        out.append(geom.arc((px, py), radius, a1, sweep))
    return out


def belt(c1, r1: float, c2, r2: float) -> Contour | None:
    """Enveloppe de deux cercles (courroie, oblong) : arcs extérieurs reliés
    par les tangentes externes, sens trigonométrique. None si un cercle
    contient l'autre."""
    (x1, y1), (x2, y2) = c1, c2
    d = math.hypot(x2 - x1, y2 - y1)
    if d <= abs(r1 - r2) + 1e-9:
        return None
    th = math.degrees(math.atan2(y2 - y1, x2 - x1))
    a = math.degrees(math.acos((r1 - r2) / d))

    def pt(c, r, deg):
        return (c[0] + r * math.cos(math.radians(deg)), c[1] + r * math.sin(math.radians(deg)))
    segs = []
    segs += geom.arc(c2, r2, th - a, 2 * a).segments                     # côté extérieur du 2e cercle
    segs.append(Line(pt(c2, r2, th + a), pt(c1, r1, th + a)))
    segs += geom.arc(c1, r1, th + a, 360 - 2 * a).segments               # côté extérieur du 1er
    segs.append(Line(pt(c1, r1, th - a), pt(c2, r2, th - a)))
    return Contour(segs, True)
