"""Restant de plaque : ce que les objets laissent libre, pour une autre imbrication ou un autre usinage.

Trois façons, comme dans TypeEdit :
- simple : le plus grand rectangle libre ;
- standard : la plaque moins les rectangles des objets, une forme simple ;
- optimisé : la plaque moins la vraie forme des objets, plus grande et plus compliquée.

Une partie plus étroite que `min_side` ne compte pas : on ne garde pas une fente entre deux pièces. Seule la plus
grande partie est rendue, avec les trous laissés par les objets qu'elle entoure. Les trous d'un objet ne comptent pas :
ils tombent avec lui.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .geom import Path, polyline, rect
from .nesting_shape import _leaf_contours

MODES = ('simple', 'standard', 'optimise')
TOL = 0.02                                               # écart de corde des courbes (mm)
MAX_CUTS = 800                                           # lignes de la grille du plus grand rectangle, par direction
MAX_LINES = 5000                                         # lignes de découpe de la matière restante, par direction


@dataclass
class RemnantSpec:
    mode: str = 'standard'
    gap: float = 2.0                                     # écart gardé autour des objets (mm)
    min_area: float = 100.0                              # en dessous, pas de restant (mm²)
    min_side: float = 20.0                               # une partie plus étroite ne compte pas (mm)


@dataclass
class Remnant:
    path: Path
    area: float
    share: float                                         # part de la plaque
    others: int = 0                                      # autres parties assez larges, laissées de côté


class NoRemnant(ValueError):
    """Rien qui réponde aux critères."""


def _plate_shape(plate):
    from shapely.geometry import Polygon, box
    if plate.corner_radius > 0:
        c = rect(plate.x, plate.y, plate.width, plate.height, plate.corner_radius)
        return Polygon(c.flatten(TOL)).buffer(0)
    return box(plate.x, plate.y, plate.x + plate.width, plate.y + plate.height)


def _footprint(item, gap: float):
    """La place d'un objet : ses contours pleins, ses traits ouverts, grossis de l'écart."""
    from shapely.geometry import LineString, Polygon
    from shapely.ops import unary_union
    parts = []
    for leaf in _leaf_contours(item, TOL):
        for pts, closed in leaf:
            if closed and len(pts) >= 4:
                poly = Polygon(pts).buffer(0)
                if poly.area > 0:
                    parts.append(poly)
                    continue
            if len(pts) >= 2:
                parts.append(LineString(pts).buffer(0.01))
    if not parts:
        return None
    whole = unary_union(parts)
    return whole.buffer(gap) if gap > 0 else whole


def _box_of(item, gap: float):
    from shapely.geometry import box
    b = item.bbox()
    if not b:
        return None
    return box(b[0] - gap, b[1] - gap, b[2] + gap, b[3] + gap)


def largest_rect(x0: float, y0: float, x1: float, y1: float, boxes: list, min_side: float = 0.0):
    """Le plus grand rectangle libre (x0, y0, x1, y1) entre ces boîtes ; None s'il n'y en a pas d'assez large."""
    arr = np.asarray(boxes, float).reshape(-1, 4)
    xs = np.unique(np.clip(np.concatenate(([x0, x1], arr[:, 0], arr[:, 2])), x0, x1))
    ys = np.unique(np.clip(np.concatenate(([y0, y1], arr[:, 1], arr[:, 3])), y0, y1))
    if len(xs) > MAX_CUTS:                               # plus grossier, mais toujours libre : une case touchée est prise
        xs = np.linspace(x0, x1, MAX_CUTS)
    if len(ys) > MAX_CUTS:
        ys = np.linspace(y0, y1, MAX_CUTS)
    nx, ny = len(xs) - 1, len(ys) - 1
    if nx < 1 or ny < 1:
        return None
    taken = np.zeros((ny, nx), dtype=bool)
    for a, b, c, d in arr:
        i0, i1 = np.searchsorted(xs, a, 'right') - 1, np.searchsorted(xs, c, 'left')
        j0, j1 = np.searchsorted(ys, b, 'right') - 1, np.searchsorted(ys, d, 'left')
        if i1 > max(i0, 0) and j1 > max(j0, 0):
            taken[max(j0, 0):j1, max(i0, 0):i1] = True
    best, found = 0.0, None
    heights = np.zeros(nx)
    for j in range(ny):
        heights = np.where(taken[j], 0.0, heights + (ys[j + 1] - ys[j]))
        stack: list[int] = []
        for i in range(nx + 1):
            h = float(heights[i]) if i < nx else 0.0
            while stack and float(heights[stack[-1]]) >= h:
                top = float(heights[stack.pop()])
                left = stack[-1] + 1 if stack else 0
                wide = float(xs[i] - xs[left])
                if top * wide > best and top >= min_side and wide >= min_side:
                    best = top * wide
                    found = (float(xs[left]), float(ys[j + 1]) - top, float(xs[i]), float(ys[j + 1]))
            stack.append(i)
    return found


def _opened(zone, r: float):
    """La zone sans ses parties plus étroites que 2·r ; les angles restent vifs."""
    if r <= 0:
        return zone
    return zone.buffer(-r, join_style='mitre').buffer(r, join_style='mitre')


def _pieces(zone) -> list:
    if zone.is_empty:
        return []
    return sorted((p for p in getattr(zone, 'geoms', [zone]) if p.geom_type == 'Polygon' and p.area > 0),
                  key=lambda p: -p.area)


def _to_path(poly) -> Path:
    contours = []
    for ring in (poly.exterior, *poly.interiors):
        contours.append(polyline(list(ring.coords)[:-1], True))
    return Path(contours)


def remnant(plate, items: list, spec: RemnantSpec) -> Remnant:
    """Le restant de la plaque, compte tenu de ces objets. NoRemnant s'il ne répond pas aux critères."""
    from shapely.geometry import box
    from shapely.ops import unary_union
    if spec.mode not in MODES:
        raise ValueError(f'mode inconnu : {spec.mode}')
    gap = max(float(spec.gap), 0.0)
    side = max(float(spec.min_side), 0.0)
    board = _plate_shape(plate)
    full = float(board.area)
    if spec.mode == 'simple':
        boxes = [(b[0] - gap, b[1] - gap, b[2] + gap, b[3] + gap) for b in (it.bbox() for it in items) if b]
        found = largest_rect(plate.x, plate.y, plate.x + plate.width, plate.y + plate.height, boxes, side)
        if found is None:
            raise NoRemnant('critères')
        pieces = _pieces(box(*found).intersection(board))
    else:
        make = _box_of if spec.mode == 'standard' else _footprint
        taken = [g for g in (make(it, gap) for it in items) if g is not None]
        solid = unary_union(taken) if taken else None
        zone = board.difference(solid) if solid is not None else board
        opened = _opened(zone, side / 2.0)
        if solid is not None:
            opened = opened.difference(solid)            # un angle en onglet ne mord ni sur les objets, ni au-dehors
        pieces = _pieces(opened.intersection(board))
        pieces = [p.simplify(0.001) if spec.mode == 'optimise' else p for p in pieces]
    minimum = max(float(spec.min_area), 0.0)
    pieces = [p for p in pieces if p.area >= minimum and p.area > 0]
    if not pieces:
        raise NoRemnant('critères')
    best = pieces[0]
    return Remnant(path=_to_path(best), area=float(best.area), share=float(best.area) / full if full > 0 else 0.0,
                   others=len(pieces) - 1)


def scrap_lines(plate, items, step_x: float, step_y: float, gap: float = 1.0) -> Path:
    """Les lignes qui découpent la matière restante en petits morceaux : une grille depuis le coin bas gauche de la plaque,
    tous les `step_x` et `step_y` mm (0 : pas dans ce sens), coupée à `gap` mm des objets et au bord de la plaque."""
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    zone = _plate_shape(plate)
    parts = [p for p in (_footprint(it, gap) for it in items) if p is not None]
    if parts:
        zone = zone.difference(unary_union(parts))
    contours: list = []
    if zone.is_empty:
        return Path(contours)

    def cut(line) -> None:
        got = line.intersection(zone)
        for piece in getattr(got, 'geoms', [got]):
            if piece.geom_type == 'LineString' and piece.length > 1e-6:
                contours.append(polyline(list(piece.coords), False))
    x0, y0, x1, y1 = plate.x, plate.y, plate.x + plate.width, plate.y + plate.height
    if step_x > 0:
        n = min(int((x1 - x0) / step_x), MAX_LINES)
        for i in range(1, n + 1):
            x = x0 + i * step_x
            if x < x1 - 1e-9:
                cut(LineString([(x, y0), (x, y1)]))
    if step_y > 0:
        n = min(int((y1 - y0) / step_y), MAX_LINES)
        for i in range(1, n + 1):
            y = y0 + i * step_y
            if y < y1 - 1e-9:
                cut(LineString([(x0, y), (x1, y)]))
    return Path(contours)
