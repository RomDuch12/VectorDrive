"""Trous d'une pièce 3D qu'un outil vertical perce : axe vertical, cercle
(presque) complet — les faces d'un même trou (deux demi-cylindres, un trou
étagé coupé en tronçons de même rayon) sont réunies. Faces cylindriques
creuses connues du STEP ; pour un simple maillage (STL, volumes du dessin
percés ou modifiés), chaque face aux parois verticales dont les sommets
tombent sur un cercle est prise pour un cylindre (`mesh_cylinder`).

Chaque trou : centre (x, y), rayon, cote du haut et du bas, profondeur sous
le haut de la pièce, débouchant ou non — pour en faire des cercles du
dessin et des perçages.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

#: couverture angulaire minimale d'un trou complet (°) ; en deçà : une rainure, un congé
FULL_DEG = 300.0


@dataclass
class Hole:
    x: float
    y: float
    radius: float
    z_top: float
    z_bottom: float
    depth: float                      # sous le haut de la pièce, jusqu'au bas du trou
    through: bool = False             # débouchant (jusqu'au bas de la pièce)
    faces: list = field(default_factory=list)
    coverage: float = 360.0           # couverture angulaire (°)

    @property
    def diameter(self) -> float:
        return 2 * self.radius


def _coverage(pts: np.ndarray, cx: float, cy: float) -> float:
    """Part du tour (°) couverte par des points autour de (cx, cy)."""
    if not len(pts):
        return 0.0
    a = np.sort(np.degrees(np.arctan2(pts[:, 1] - cy, pts[:, 0] - cx)) % 360.0)
    gaps = np.diff(np.r_[a, a[0] + 360.0])
    return float(360.0 - gaps.max())


def mesh_cylinder(T: np.ndarray, tol: float = 0.02, angle: float = 1.0) -> dict | None:
    """Cylindre d'axe vertical d'une face maillée (triangles (n, 3, 3)) :
    parois verticales (à `angle` degrés près), 8 sommets au moins sur un
    cercle (à `tol` près) ; creux si les normales regardent l'axe. Rend une
    description de face comme celles du STEP ({'genre': 'cylindre', 'axe',
    'centre', 'rayon', 'creux'}), ou None."""
    T = np.asarray(T, dtype=np.float64)
    if len(T) < 3:
        return None
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    ln = np.linalg.norm(n, axis=1)
    keep = ln > 1e-12
    if keep.sum() < 3:
        return None
    n = n[keep] / ln[keep, None]
    if np.abs(n[:, 2]).max() > math.sin(math.radians(angle)):
        return None                                    # pas des parois verticales
    P = np.unique(np.round(T[keep].reshape(-1, 3)[:, :2], 9), axis=0)
    if len(P) < 8:
        return None                                    # quatre coins tombent toujours sur un cercle
    A = np.column_stack([P, np.ones(len(P))])
    sol, *_r = np.linalg.lstsq(A, -(P ** 2).sum(axis=1), rcond=None)
    cx, cy = -sol[0] / 2, -sol[1] / 2
    r2 = cx * cx + cy * cy - sol[2]
    if not np.isfinite(r2) or r2 <= 0:
        return None
    r = math.sqrt(r2)
    span = float(np.ptp(P, axis=0).max())
    if r > 2 * span + tol or np.abs(np.hypot(P[:, 0] - cx, P[:, 1] - cy) - r).max() > max(tol, 1e-6 * r):
        return None                                    # pas un cercle (une paroi plane, une courbe libre)
    c = T[keep].mean(axis=1)[:, :2] - [cx, cy]
    inward = float((n[:, 0] * c[:, 0] + n[:, 1] * c[:, 1]).sum()) < 0
    return {'genre': 'cylindre', 'axe': [0.0, 0.0, 1.0], 'centre': [float(cx), float(cy), float(T[:, :, 2].min())],
            'rayon': float(r), 'creux': inward}


def find(model, tol: float = 0.02, angle: float = 1.0) -> list[Hole]:
    """Trous verticaux de la pièce posée (repère du modèle), du plus gros au
    plus petit."""
    if not len(model.triangles):
        return []
    tris = np.asarray(model.triangles, dtype=np.float64)
    fo = model.face_ids()
    kinds = list(getattr(model, 'face_kinds', None) or [])
    known = {f for f, k in enumerate(kinds) if k and k.get('genre')}
    nf = int(fo.max()) + 1 if len(fo) else 0
    if len(known) < nf:                                # faces sans description (maillage) : cylindres ajustés
        kinds += [{}] * (nf - len(kinds))
        order = np.argsort(fo, kind='stable')
        starts = np.flatnonzero(np.r_[True, np.diff(fo[order]) != 0])
        for s, e in zip(starts, np.r_[starts[1:], len(order)]):
            f = int(fo[order[s]])
            if f not in known:
                kinds[f] = mesh_cylinder(tris[order[s:e]], tol, angle) or {}
    top, bottom = float(tris[:, :, 2].max()), float(tris[:, :, 2].min())
    cos = math.cos(math.radians(angle))
    groups: list = []                                  # [(x, y, r, [(face, x, y, r, triangles)])]
    for f, k in enumerate(kinds):
        if k.get('genre') != 'cylindre' or not k.get('creux', False) or k.get('axe') is None \
                or k.get('centre') is None or not k.get('rayon'):
            continue
        a = np.asarray(k['axe'], dtype=float)
        if abs(abs(a[2]) / max(np.linalg.norm(a), 1e-12)) < cos:
            continue                                   # axe pas vertical : pas pour un outil vertical
        sel = fo == f
        if not sel.any():
            continue
        c = np.asarray(k['centre'], dtype=float)
        x, y, r = float(c[0]), float(c[1]), float(k['rayon'])
        part = (f, x, y, r, tris[sel])
        for gx, gy, gr, members in groups:             # même axe, même rayon (à tol près, sans arrondi)
            if math.hypot(gx - x, gy - y) <= tol and abs(gr - r) <= tol:
                members.append(part)
                break
        else:
            groups.append((x, y, r, [part]))
    from . import faces3d
    out = []
    for _gx, _gy, _gr, parts in groups:
        faces = [p[0] for p in parts]
        x = sum(p[1] for p in parts) / len(parts)
        y = sum(p[2] for p in parts) / len(parts)
        r = sum(p[3] for p in parts) / len(parts)
        T = np.concatenate([p[4] for p in parts])
        cov = _coverage(T.reshape(-1, 3), x, y)
        if cov < FULL_DEG:
            continue
        zt, zb = float(T[:, :, 2].max()), float(T[:, :, 2].min())
        i, d = faces3d.ray_hit(tris, (x, y, top + 10.0), (0.0, 0.0, -1.0))
        if i >= 0 and (top + 10.0 - d) > zt + max(tol, 1e-3):
            continue                                   # matière au-dessus : trou ouvert par-dessous (autre prise)
        out.append(Hole(round(x, 4), round(y, 4), round(r, 4), zt, zb, round(top - zb, 4),
                        abs(zb - bottom) < max(tol, 1e-3), faces, round(cov, 1)))
    out.sort(key=lambda h: (-h.radius, h.x, h.y))
    return out
