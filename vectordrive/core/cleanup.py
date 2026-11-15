"""Nettoyage des dessins : contours superposés (doublons), sens des
contours.

Les doublons viennent souvent d'un import (DXF exporté deux fois, symbole
posé deux fois au même endroit) : gravés, ils repassent deux fois au même
endroit. Deux contours sont superposés si chaque point de l'un est à moins
de `tol` de l'autre, dans les deux sens (distance de Hausdorff), quel que
soit leur point de départ ou leur sens de parcours.
"""
from __future__ import annotations

import copy

import numpy as np

from .document import Group, Item, Shape
from .geom import Contour, Path


def _poly(c: Contour, tol: float) -> np.ndarray:
    return np.asarray(c.flatten(tol / 4), dtype=float)


def _dist_to_polyline(p: np.ndarray, poly: np.ndarray) -> np.ndarray:
    """Distance de chaque point de `p` (n, 2) à la polyligne (m, 2)."""
    if len(poly) == 1:
        return np.hypot(*(p - poly[0]).T)
    a, b = poly[:-1], poly[1:]
    ab = b - a
    L2 = (ab ** 2).sum(1)
    L2[L2 == 0] = 1e-30
    d = p[:, None, :] - a[None, :, :]
    t = np.clip((d * ab[None]).sum(2) / L2[None], 0, 1)
    proj = a[None] + t[..., None] * ab[None]
    return np.hypot(*(p[:, None, :] - proj).transpose(2, 0, 1)).min(1)


def _sample(poly: np.ndarray, n: int = 48) -> np.ndarray:
    if len(poly) <= n:
        return poly
    idx = np.linspace(0, len(poly) - 1, n).round().astype(int)
    return poly[idx]


def same_contour(a: Contour, b: Contour, tol: float = 0.01) -> bool:
    if a.closed != b.closed:
        return False
    ba, bb = a.bbox(), b.bbox()
    if max(abs(x - y) for x, y in zip(ba, bb)) > tol:
        return False
    if abs(a.length() - b.length()) > max(tol * 4, 1e-3 * a.length()):
        return False
    pa, pb = _poly(a, tol), _poly(b, tol)
    return bool(_dist_to_polyline(_sample(pa), pb).max() <= tol and
                _dist_to_polyline(_sample(pb), pa).max() <= tol)


def remove_duplicates(items: list[Item], tol: float = 0.01) -> tuple[list[Item], int]:
    """Copie de `items` sans contours superposés (le premier est gardé).
    Une forme vidée disparaît, un groupe vidé aussi."""
    res, n = dedupe(items, tol)
    return [x for x in res if x is not None], n


def dedupe(items: list[Item], tol: float = 0.01) -> tuple[list[Item | None], int]:
    """Comme `remove_duplicates`, mais la liste rendue est alignée sur
    `items` : même objet si inchangé, copie s'il a perdu des contours,
    None s'il n'en reste rien."""
    grid: dict[tuple, list[Contour]] = {}
    cell = max(tol * 50, 1e-6)
    removed = 0

    def is_dup(c: Contour) -> bool:
        bb = c.bbox()
        cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
        gx, gy = int(cx // cell), int(cy // cell)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for other in grid.get((gx + dx, gy + dy), ()):
                    if same_contour(c, other, tol):
                        return True
        grid.setdefault((gx, gy), []).append(c)
        return False

    def walk(it: Item) -> Item | None:
        nonlocal removed
        if isinstance(it, Group):
            ch = [x for x in (walk(c) for c in it.children) if x is not None]
            if not ch:
                return None
            if len(ch) == len(it.children) and all(a is b for a, b in zip(ch, it.children)):
                return it
            g = copy.copy(it)
            g.children = ch
            return g
        if isinstance(it, Shape):
            keep = [c for c in it.path.contours if not c.segments or not is_dup(c)]
            n = len(it.path.contours) - len(keep)
            if not n:
                return it
            removed += n
            if not any(c.segments for c in keep):
                return None
            s = copy.copy(it)
            s.path = Path(keep)
            return s
        return it

    out = [walk(it) for it in items]
    return out, removed


def reverse(path: Path) -> Path:
    return Path([c.reversed() for c in path.contours])


def drop_null_segments(path: Path, tol: float = 1e-6) -> tuple[Path, int]:
    """Segments de longueur nulle (points confondus) retirés ; renvoie le
    chemin et leur nombre. Un contour réduit à rien disparaît."""
    from .geom import dist
    out, n = [], 0
    for c in path.contours:
        keep = []
        for s in c.segments:
            pts = [s.start, s.end] + [getattr(s, a) for a in ('p1', 'p2') if hasattr(s, a)]
            if all(dist(q, s.start) <= tol for q in pts):
                n += 1
                continue
            keep.append(s)
        if keep:
            out.append(Contour(keep, c.closed))
    return Path(out), n
