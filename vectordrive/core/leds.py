"""LED (TypeEdit : Outils métier ▸ LED) : positions des diodes d'une
enseigne lumineuse — le long des contours (écart entre axes compris entre
un minimum et un maximum, ou un nombre par contour ; diodes aux angles ;
décalage au début et à la fin des contours ouverts) ou à l'intérieur
(remplissage en grille, angle, seulement les diodes entières) ; les diodes
trop proches les unes des autres sont écartées.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .geom import Path, circle


@dataclass
class LedSpec:
    diameter: float = 5.0            # perçage d'une diode (mm)
    layout: str = 'contour'          # 'contour' (sur les tracés) ou 'interieur' (grille)
    spacing_min: float = 20.0        # écart minimum entre axes (mm)
    spacing_max: float = 30.0        # écart maximum entre axes (mm)
    count: int = 0                   # nombre de diodes par contour (0 : selon l'écart)
    corners: bool = False            # une diode à chaque angle
    corner_angle: float = 120.0      # angle (°) au-dessous duquel un sommet est un angle
    offset_start: float = 0.0        # contour ouvert : décalage au début (mm)
    offset_end: float = 0.0          # contour ouvert : décalage à la fin (mm)
    grid_x: float = 20.0             # intérieur : pas en X (mm)
    grid_y: float = 20.0             # intérieur : pas en Y (mm)
    grid_angle: float = 0.0          # intérieur : angle de la grille (°)
    collisions: bool = True          # écarter les diodes qui se touchent


def _count(length: float, spec: LedSpec) -> int:
    if spec.count > 0:
        return int(spec.count)
    lo, hi = max(spec.spacing_min, 1e-6), max(spec.spacing_max, spec.spacing_min, 1e-6)
    n = max(1, math.ceil(length / hi))                 # écart ≤ maximum
    if length / n < lo:                                # sinon écart ≥ minimum
        n = max(1, math.floor(length / lo))
    return n


def _corners(pts: list, closed: bool, limit: float) -> list:
    out = []
    rng = range(len(pts)) if closed else range(1, len(pts) - 1)
    for i in rng:
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
        v1, v2 = (a[0] - b[0], a[1] - b[1]), (c[0] - b[0], c[1] - b[1])
        n1, n2 = math.hypot(*v1), math.hypot(*v2)
        if n1 < 1e-9 or n2 < 1e-9:
            continue
        ang = math.degrees(math.acos(max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))))
        if ang < limit:
            out.append(b)
    return out


def along(contour, spec: LedSpec, tol: float = 0.05) -> list:
    """Positions sur un contour, à intervalles égaux le long du tracé."""
    from .geom import walker
    total, at = walker(contour)
    if total <= 0:
        return []
    closed = contour.closed
    if closed:
        n = _count(total, spec)
        pts = [at(total * k / n)[0] for k in range(n)]
    else:
        s0, s1 = min(spec.offset_start, total), max(spec.offset_start, total - spec.offset_end)
        span = max(0.0, s1 - s0)
        n = _count(span, spec) if span > 0 else 0
        pts = [at(s0 + span * k / n)[0] for k in range(n + 1)] if n else [at(s0)[0]]
    if spec.corners:
        flat = contour.flatten(tol)
        if closed and len(flat) > 1 and math.dist(flat[0], flat[-1]) < 1e-9:
            flat = flat[:-1]
        cs = _corners(flat, closed, spec.corner_angle)
        keep = [p for p in pts if all(math.dist(p, c) >= spec.spacing_min / 2 for c in cs)]
        pts = cs + keep
    return pts


def inside(region, spec: LedSpec) -> list:
    """Grille (pas X, pas Y, angle) dans la région ; seulement les diodes entières."""
    from shapely import affinity
    from shapely.geometry import Point
    room = region.buffer(-spec.diameter / 2)
    if room.is_empty or spec.grid_x <= 0 or spec.grid_y <= 0:
        return []
    c = region.centroid
    rot = affinity.rotate(room, -spec.grid_angle, origin=c)
    x0, y0, x1, y1 = rot.bounds
    a = math.radians(spec.grid_angle)
    out = []
    y = y0
    while y <= y1 + 1e-9:
        x = x0
        while x <= x1 + 1e-9:
            if rot.contains(Point(x, y)):
                dx, dy = x - c.x, y - c.y
                out.append((c.x + dx * math.cos(a) - dy * math.sin(a), c.y + dx * math.sin(a) + dy * math.cos(a)))
            x += spec.grid_x
        y += spec.grid_y
    return out


def drop_collisions(points: list, diameter: float) -> list:
    """Diodes plus proches qu'un diamètre : la première gardée seulement."""
    kept = []
    for p in points:
        if all(math.dist(p, q) >= diameter - 1e-9 for q in kept):
            kept.append(p)
    return kept


def layout(path: Path, spec: LedSpec) -> list:
    """Positions des diodes pour les contours de `path`."""
    if spec.layout == 'interieur':
        from . import pathops
        closed = Path([c for c in path.contours if c.closed and c.segments])
        if not closed.contours:
            return []
        pts = inside(pathops._to_shapely(pathops.normalize(closed)), spec)
    else:
        pts = [p for c in path.contours if c.segments for p in along(c, spec)]
    return drop_collisions(pts, spec.diameter) if spec.collisions else pts


def circles(points: list, diameter: float) -> Path:
    return Path([circle(p, diameter / 2) for p in points])
