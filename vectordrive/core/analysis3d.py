"""Analyses de surface d'un modèle 3D : dépouille de chaque face vers une
direction de démoulage, faces atteintes le long d'une direction (outil
vertical, démoulage).

D'après SolidCraft (MIT OR Apache-2.0, © 2026 SolidCraft contributors,
utilisé sous MIT) — `crates/render/src/analysis.rs` (AnalysisMode Draft et
Access, leurs couleurs) et `crates/engine/src/cmd/surface_analysis.rs`
(`inspect.draft`).

Les triangles sont des tableaux (n, 3, 3) en mm."""
from __future__ import annotations

import math

import numpy as np

#: dépouille : au moins l'angle vers la direction, entre, au moins l'angle à l'opposé
DRAFT_COLORS = ((0.20, 0.75, 0.30), (0.95, 0.80, 0.15), (0.85, 0.22, 0.20))
#: accessibilité : atteinte, cachée
ACCESS_COLORS = ((0.20, 0.75, 0.30), (0.85, 0.22, 0.20))
DIRECTIONS = {'z+': (0.0, 0.0, 1.0), 'z-': (0.0, 0.0, -1.0), 'x+': (1.0, 0.0, 0.0), 'x-': (-1.0, 0.0, 0.0),
              'y+': (0.0, 1.0, 0.0), 'y-': (0.0, -1.0, 0.0)}


def unit(direction) -> np.ndarray:
    """Direction ('z+', 'x-'… ou vecteur) → vecteur unitaire."""
    v = np.asarray(DIRECTIONS[direction] if isinstance(direction, str) else direction, dtype=float)
    n = float(np.linalg.norm(v))
    if not n > 1e-12:
        raise ValueError('direction nulle')
    return v / n


def normals(tris) -> tuple[np.ndarray, np.ndarray]:
    """(normales unitaires (n, 3), aires (n,)) des triangles."""
    t = np.asarray(tris, dtype=float).reshape(-1, 3, 3)
    n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    a = np.linalg.norm(n, axis=1)
    return n / np.where(a > 0, a, 1.0)[:, None], a / 2


def draft_angles(tris, pull='z+') -> np.ndarray:
    """Dépouille de chaque face (degrés) : 90 tournée vers `pull`, 0 paroi
    parallèle à `pull`, -90 tournée à l'opposé."""
    n, _a = normals(tris)
    return np.degrees(np.arcsin(np.clip(n @ unit(pull), -1.0, 1.0)))


def draft_classes(tris, pull='z+', angle: float = 1.0) -> np.ndarray:
    """0 : dépouille d'au moins `angle` vers `pull` ; 2 : d'au moins `angle`
    à l'opposé (l'autre moitié du moule) ; 1 : entre les deux, trop peu."""
    d, a = draft_angles(tris, pull), abs(float(angle))
    return np.where(d >= a - 1e-9, 0, np.where(d <= -a + 1e-9, 2, 1)).astype(np.int8)


def subdivide(tris, max_edge: float, max_tris: int = 400_000) -> tuple[np.ndarray, np.ndarray]:
    """Triangles coupés en deux par le milieu de leur plus grand côté tant
    qu'il passe `max_edge` (sens de parcours gardé) : (triangles, numéro du
    triangle d'origine de chacun)."""
    t = np.asarray(tris, dtype=float).reshape(-1, 3, 3)
    parent = np.arange(len(t))
    while len(t):
        e = np.linalg.norm(np.roll(t, -1, axis=1) - t, axis=2)          # côtés 0→1, 1→2, 2→0
        k = e.argmax(axis=1)
        big = e[np.arange(len(t)), k] > max_edge
        nb = int(big.sum())
        if not nb or len(t) + nb > max_tris:
            break
        idx = (k[big][:, None] + np.arange(3)) % 3
        b = t[big][np.arange(nb)[:, None], idx]                         # le plus grand côté d'abord
        m = (b[:, 0] + b[:, 1]) / 2
        new = np.concatenate([np.stack([b[:, 0], m, b[:, 2]], 1), np.stack([m, b[:, 1], b[:, 2]], 1)])
        parent = np.concatenate([parent[~big], np.tile(parent[big], 2)])
        t = np.concatenate([t[~big], new])
    return t, parent


def _frame(d: np.ndarray) -> np.ndarray:
    """Rotation (lignes du repère) qui amène `d` sur +Z."""
    h = np.array([1.0, 0.0, 0.0]) if abs(d[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    e1 = h - (h @ d) * d
    e1 /= np.linalg.norm(e1)
    return np.array([e1, np.cross(d, e1), d])


def access_classes(tris, direction='z+', res: float | None = None, max_cells: int = 1_500_000) -> np.ndarray:
    """0 : face atteinte le long de `direction` (tournée vers elle ou
    parallèle, et rien du modèle au-dessus) ; 1 : cachée (tournée à
    l'opposé, ou sous une autre partie). Vue depuis `direction` en carte de
    hauteurs ; chaque face jugée en son centre (recouper les grands
    triangles pour juger plus finement)."""
    from ..cam.advanced import heightmap_from_triangles
    t = np.asarray(tris, dtype=float).reshape(-1, 3, 3)
    if not len(t):
        return np.zeros(0, dtype=np.int8)
    q = t @ _frame(unit(direction)).T
    lo, hi = q.reshape(-1, 3).min(axis=0), q.reshape(-1, 3).max(axis=0)
    w, h = max(hi[0] - lo[0], 1e-3), max(hi[1] - lo[1], 1e-3)
    res = max(res or max(w, h) / 400, math.sqrt(w * h / max_cells))
    x0, y0 = lo[0] - 2 * res, lo[1] - 2 * res
    nx, ny = int(math.ceil(w / res)) + 5, int(math.ceil(h / res)) + 5
    H = heightmap_from_triangles(q, x0, y0, nx, ny, res)
    n, _a = normals(q)
    c = q.mean(axis=1) + n * (1.5 * res)                 # un peu hors de la face : elle ne se cache pas elle-même
    i = np.clip(np.round((c[:, 0] - x0) / res).astype(int), 0, nx - 1)
    j = np.clip(np.round((c[:, 1] - y0) / res).astype(int), 0, ny - 1)
    free = (n[:, 2] > -1e-6) & (c[:, 2] >= H[j, i] - 0.5 * res)
    return np.where(free, 0, 1).astype(np.int8)


def area_shares(tris, classes, k: int) -> list[float]:
    """Part de la surface (0..1) de chacune des `k` classes."""
    _n, a = normals(tris)
    tot = float(a.sum())
    cl = np.asarray(classes)
    return [float(a[cl == i].sum()) / tot if tot > 0 else 0.0 for i in range(k)]
