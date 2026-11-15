"""Faces d'une pièce 3D atteintes par un outil vertical selon la face
tournée vers l'outil (prise) — pour usiner toute la pièce : quelles prises
faut-il, et que reste-t-il hors d'atteinte en 3 axes (contre-dépouilles) ?

Un triangle est atteint d'une prise s'il est, posé ainsi, la plus haute
surface au-dessus de son centre (carte de hauteurs vue de dessus) ; une
paroi verticale l'est si la colonne voisine, d'un côté ou de l'autre, est
libre au-dessus d'elle.
"""
from __future__ import annotations

import numpy as np

from . import faces3d

#: les six prises possibles, dans l'ordre où on les propose
SIDES = ('+Z', '-Z', '+X', '-X', '+Y', '-Y')


def reached(model, face: str, res: float = 0.5, tol: float | None = None) -> np.ndarray:
    """Triangles atteints quand `face` est tournée vers l'outil (booléens)."""
    from ..cam.advanced import heightmap_from_triangles
    from ..io import model3d
    from . import placement3d as P3
    m = model3d.placed(model, P3.Placement(face)) if face != '+Z' else model
    t = np.asarray(m.triangles, dtype=np.float64)
    if not len(t):
        return np.zeros(0, dtype=bool)
    tol = tol if tol is not None else max(0.05, res)
    lo, hi = t.reshape(-1, 3).min(axis=0), t.reshape(-1, 3).max(axis=0)
    x0, y0 = lo[0] - 2 * res, lo[1] - 2 * res
    nx = int(np.ceil((hi[0] - lo[0]) / res)) + 5
    ny = int(np.ceil((hi[1] - lo[1]) / res)) + 5
    H = heightmap_from_triangles(t, x0, y0, nx, ny, res)

    def height_at(x, y):
        i = np.clip(np.round((x - x0) / res).astype(int), 0, nx - 1)
        j = np.clip(np.round((y - y0) / res).astype(int), 0, ny - 1)
        return H[j, i]
    c = t.mean(axis=1)
    n = faces3d.normals(t)
    ok = c[:, 2] >= height_at(c[:, 0], c[:, 1]) - tol
    wall = np.abs(n[:, 2]) < 0.05
    if wall.any():
        nxy = n[wall, :2]
        ln = np.linalg.norm(nxy, axis=1)
        nxy = nxy / np.where(ln > 0, ln, 1.0)[:, None]
        d = 1.5 * res
        cw = c[wall]
        free = np.zeros(len(cw), dtype=bool)
        for s in (1.0, -1.0):                              # le côté libre de la paroi (sens des triangles inconnu)
            h = height_at(cw[:, 0] + s * d * nxy[:, 0], cw[:, 1] + s * d * nxy[:, 1])
            free |= ~np.isfinite(h) | (h <= cw[:, 2] + tol)
        ok[wall] = free
    return ok


def left_out(model, sides, res: float = 0.5, cache: dict | None = None) -> float:
    """Part de la surface qu'aucune des prises `sides` n'atteint ; `cache`
    {face: triangles atteints} garde les calculs d'un appel à l'autre."""
    t = np.asarray(model.triangles, dtype=np.float64)
    if not len(t):
        return 0.0
    area = 0.5 * np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1)
    done = np.zeros(len(t), dtype=bool)
    for s in sides:
        done |= _reached(model, s, res, cache)
    return float(area[~done].sum()) / (float(area.sum()) or 1.0)


def _reached(model, side: str, res: float, cache: dict | None):
    """`reached`, gardé dans `cache` {face: triangles atteints} s'il y en a un."""
    r = cache.get(side) if cache is not None else None
    if r is None:
        r = reached(model, side, res)
        if cache is not None:
            cache[side] = r
    return r


#: poids d'une paroi atteinte (usinée par le flanc de l'outil, souvent long) face à une surface vue de dessus
WALL_WEIGHT = 0.3


def plan_sides(model, res: float = 0.5, sides=SIDES, min_gain: float = 0.005, cache: dict | None = None):
    """Prises à faire, dans l'ordre (gourmand : chaque fois celle qui atteint
    le plus de surface encore non usinée — une paroi comptant pour
    `WALL_WEIGHT`, une surface vue de dessus pour 1) : [(face, part de la
    surface atteinte en plus)], et la part qui reste hors d'atteinte ; `cache`
    comme pour `left_out` (mêmes pièce et résolution)."""
    from . import placement3d as P3
    t = np.asarray(model.triangles, dtype=np.float64)
    if not len(t):
        return [], 0.0
    area = 0.5 * np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1)
    total = float(area.sum()) or 1.0
    reach, weight = {}, {}
    for s in sides:
        reach[s] = _reached(model, s, res, cache)
        R = P3.Placement(s).rotation()
        nz = np.abs(faces3d.normals(t) @ R.T[:, 2])         # composante verticale, pièce posée ainsi
        weight[s] = np.maximum(nz, WALL_WEIGHT)
    done = np.zeros(len(t), dtype=bool)
    out = []
    left = list(sides)
    while left:
        score = {s: float((area * weight[s])[reach[s] & ~done].sum()) for s in left}
        best = max(left, key=lambda s: (score[s], -left.index(s)))
        gain = float(area[reach[best] & ~done].sum()) / total
        if gain < min_gain:
            break
        out.append((best, gain))
        done |= reach[best]
        left.remove(best)
    return out, float(area[~done].sum()) / total
