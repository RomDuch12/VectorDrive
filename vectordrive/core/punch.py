"""Poinçonner et rogner à une forme quelconque.

Une forme fermée (le poinçon) coupe les objets :

* **traits** (contours non remplis, polices monotrait…) : chaque contour
  est coupé exactement là où il traverse le bord du poinçon (intersections
  par Newton, découpe au paramètre exact) ; on garde les morceaux dehors
  (poinçonner) ou dedans (rogner). Aucun bord n'est ajouté ;
* **surfaces** (formes remplies, textes) : différence ou intersection
  booléenne exacte.
"""
from __future__ import annotations

import math

import numpy as np

from . import pathops
from .geom import Path
from .trim import cut_params, piece


def _polys(region: Path, tol: float = 1e-4) -> list[np.ndarray]:
    return [np.asarray(c.flatten(tol), float) for c in region.contours if c.closed and c.segments]


def inside(pt, polys) -> bool:
    """Point dans la région (règle pair-impair)."""
    x, y = pt
    n = 0
    for P in polys:
        if len(P) < 3:
            continue
        x0, y0 = P[:, 0], P[:, 1]
        x1, y1 = np.roll(x0, -1), np.roll(y0, -1)
        m = (y0 > y) != (y1 > y)
        with np.errstate(divide='ignore', invalid='ignore'):
            xs = x0[m] + (y - y0[m]) * (x1[m] - x0[m]) / (y1[m] - y0[m])
        n += int(np.count_nonzero(xs > x))
    return n % 2 == 1


def _point_at(contour, g: float):
    n = len(contour.segments)
    i = int(math.floor(g))
    return contour.segments[i % n].point(g - i)


def cut_strokes(path: Path, region: Path, keep_inside: bool) -> Path | None:
    """Traits coupés au bord de `region` ; None si rien ne change."""
    cutters = [s for c in region.contours if c.closed for s in c.close().segments]
    polys = _polys(region)
    out, changed = [], False
    for c in path.contours:
        if not c.segments:
            continue
        if c.closed:
            c = c.close()                               # fermeture implicite → droite explicite
        cuts = cut_params(c, cutters, self_cut=False)
        n = len(c.segments)
        if not cuts:
            if inside(c.segments[0].point(0.5), polys) == keep_inside:
                out.append(c)
            else:
                changed = True
            continue
        changed = True
        if c.closed:
            bounds = cuts + [cuts[0] + n]
        else:
            bounds = [0.0] + cuts + [float(n)]
        spans = list(zip(bounds, bounds[1:]))
        keep = [inside(_point_at(c, (a + b) / 2), polys) == keep_inside for a, b in spans]
        if all(keep):                                   # tangences seulement : rien à couper
            out.append(c)
            continue
        if c.closed and keep[0] and keep[-1]:           # le premier et le dernier se rejoignent
            first = spans.pop(0)
            keep.pop(0)
            spans[-1] = (spans[-1][0], first[1] + n)
        merged = []
        for (a, b), k in zip(spans, keep):
            if not k:
                continue
            if merged and abs(merged[-1][1] - a) < 1e-12:
                merged[-1] = (merged[-1][0], b)
            else:
                merged.append((a, b))
        for a, b in merged:
            pc = piece(c, a, b)
            if pc.segments:
                out.append(pc)
    return Path(out) if changed else None


def cut_regions(path: Path, region: Path, keep_inside: bool) -> Path:
    return pathops.boolean(path, region, 'intersect' if keep_inside else 'difference')


def cut(path: Path, region: Path, filled: bool, keep_inside: bool) -> Path | None:
    """Coupe d'un tracé par la région ; None si inchangé."""
    rb, pb = region.bbox(), path.bbox()
    if not rb or not pb:
        return None
    if pb[2] < rb[0] or pb[0] > rb[2] or pb[3] < rb[1] or pb[1] > rb[3]:
        return Path() if keep_inside else None          # entièrement dehors
    if filled:
        return cut_regions(path, region, keep_inside)
    return cut_strokes(path, region, keep_inside)
