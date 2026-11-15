"""Resserrer une imbrication selon la forme : la grille laisse du jeu, la géométrie exacte le reprend.

La grille de `nesting_shape` ne met jamais deux objets plus près que l'écart, mais elle les laisse plus loin : jusqu'à
deux ou trois cases de trop. Ici chaque objet, en partant du coin de rangement, glisse vers ce coin tant que sa distance
exacte aux autres reste au moins l'écart. Le rangement ne change pas, seul le jeu disparaît.
"""
from __future__ import annotations

import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import LineString, Polygon

from . import progress
from .geom import Affine

#: au-delà, on garde le rangement de la grille : le gain ne vaut pas l'attente
MAX_PIECES = 500
#: nombre d'essais de position au plus, pour toute l'imbrication
MAX_TESTS = 25000
#: finesse des contours (mm) ; comptée dans la distance pour que la vraie courbe reste à l'écart
TOL = 0.01
#: glissement essayé d'un coup, en cases
REACH_CELLS = 1.0
SPLITS = 6


def _piece(it, in_holes: bool):
    """La forme d'un objet : ses contours fermés remplis (trous gardés si on range dedans), ses traits ouverts."""
    from .nesting_shape import _leaf_contours
    parts = []
    for leaf in _leaf_contours(it, TOL):
        filled = None
        for pts, closed in leaf:
            if closed and len(pts) >= 3:
                poly = shapely.make_valid(Polygon(pts))
                if filled is None:
                    filled = poly
                elif in_holes:
                    filled = filled.symmetric_difference(poly)
                else:
                    filled = filled.union(poly)
            elif len(pts) >= 2:
                parts.append(LineString(pts))
        if filled is not None:
            parts.append(filled)
    return shapely.union_all(parts) if parts else None


def _region(path):
    """La forme où l'on range, pair-impair."""
    out = None
    for c in path.contours:
        pts = c.flatten(TOL)
        if len(pts) < 3:
            continue
        poly = shapely.make_valid(Polygon(pts))
        out = poly if out is None else out.symmetric_difference(poly)
    return out


class _Budget:
    def __init__(self, tests: int):
        self.left = tests

    def spend(self) -> bool:
        self.left -= 1
        if self.left % 256 == 0:
            progress.check()
        return self.left > 0


def _sheet(geoms: list, rect: tuple, vx: float, vy: float, vertical: bool, gap: float, reach: float, budget: _Budget,
           region=None, border: float = 0.0) -> list[tuple[float, float]]:
    """Les déplacements (dx, dy) de chaque objet d'une plaque, vers le coin (vx, vy)."""
    boxes = np.array([g.bounds for g in geoms], dtype=float)
    moved = [(0.0, 0.0)] * len(geoms)
    need = gap + 2 * TOL
    limit = None if region is None else (region, region.boundary)

    def allowed(i: int, dx: float, dy: float) -> bool:
        if not budget.spend():
            return False
        b = boxes[i]
        x0, y0, x1, y1 = b[0] + dx, b[1] + dy, b[2] + dx, b[3] + dy
        if x0 < rect[0] - 1e-9 or y0 < rect[1] - 1e-9 or x1 > rect[2] + 1e-9 or y1 > rect[3] + 1e-9:
            return False
        g = affinity.translate(geoms[i], dx, dy)
        near = (boxes[:, 0] - need < x1) & (boxes[:, 2] + need > x0) & (boxes[:, 1] - need < y1) & (boxes[:, 3] + need > y0)
        near[i] = False
        for j in np.nonzero(near)[0]:
            if g.distance(geoms[j]) < need:
                return False
        if limit is not None and (not limit[0].contains(g) or (border > 0 and limit[1].distance(g) < border + 2 * TOL)):
            return False
        return True

    def slide(i: int, ax: float, ay: float) -> float:
        """Jusqu'où l'objet avance selon (ax, ay) : par pas tant que c'est libre, puis par moitiés."""
        done = 0.0
        while allowed(i, ax * (done + reach), ay * (done + reach)):
            done += reach
        lo, hi = done, done + reach
        for _ in range(SPLITS):
            mid = (lo + hi) / 2
            if allowed(i, ax * mid, ay * mid):
                lo = mid
            else:
                hi = mid
        return lo

    def commit(i: int, dx: float, dy: float) -> None:
        geoms[i] = affinity.translate(geoms[i], dx, dy)
        boxes[i] += (dx, dy, dx, dy)
        moved[i] = (moved[i][0] + dx, moved[i][1] + dy)

    for _round in range(2):
        any_move = 0.0
        # les plus près du coin d'abord : ils libèrent la place des suivants
        along = boxes[:, 0] * -vx + boxes[:, 2] * 0 if vertical else boxes[:, 1] * -vy
        other = boxes[:, 1] * -vy if vertical else boxes[:, 0] * -vx
        for i in np.lexsort((other, along)):
            i = int(i)
            for ax, ay in (((vx, 0.0), (0.0, vy)) if vertical else ((0.0, vy), (vx, 0.0))):
                d = slide(i, ax, ay)
                if d > 0:
                    commit(i, ax * d, ay * d)
                    any_move += d
            if budget.left <= 0:
                return moved
        if any_move < reach:
            break
    return moved


def tighten(res, plate, spec, margin: float, cell: float, region=None) -> None:
    """Reprend le jeu de `res` (`NestResult` d'une imbrication selon la forme) : ses matrices sont mises à jour."""
    from .nesting import PLATE_GAP
    if not res.placed or len(res.placed) > MAX_PIECES:
        return
    try:
        base = {}
        for it, _m in res.placed:
            if id(it) not in base:
                base[id(it)] = _piece(it, bool(getattr(spec, 'in_holes', False)))
        where = _region(region) if region is not None else None
        if region is not None and where is None:
            return
        corner = str(getattr(spec, 'corner', 'haut_gauche'))
        vx = 1.0 if corner.endswith('droit') else -1.0
        vy = -1.0 if corner.startswith('bas') else 1.0
        by_sheet: dict[int, list[int]] = {}
        for n, k in enumerate(res.sheets):
            by_sheet.setdefault(k, []).append(n)
        budget = _Budget(MAX_TESTS)
        reach = max(cell * REACH_CELLS, 0.05)
        for k, members in by_sheet.items():
            kept = [n for n in members if base[id(res.placed[n][0])] is not None]
            geoms = []
            for n in kept:
                it, m = res.placed[n]
                geoms.append(affinity.affine_transform(base[id(it)], [m.a, m.c, m.b, m.d, m.e, m.f]))
            left = plate.x + k * (plate.width + PLATE_GAP) + margin
            rect = (left, plate.y + margin, left + plate.width - 2 * margin, plate.y + plate.height - margin)
            moves = _sheet(geoms, rect, vx, vy, bool(getattr(spec, 'vertical', False)), max(float(spec.gap), 0.0), reach,
                           budget, where, max(float(getattr(spec, 'margin', 0.0)), 0.0) if region is not None else 0.0)
            for n, (dx, dy) in zip(kept, moves):
                if dx or dy:
                    it, m = res.placed[n]
                    res.placed[n] = (it, Affine.translation(dx, dy) @ m)
    except shapely.errors.GEOSException:
        return                                           # une forme que la géométrie refuse : le rangement de la grille reste bon
