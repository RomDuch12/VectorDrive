"""Enroulement d'un relief sur un autre (TypeEdit : Enroulement d'objets TypeArt).

Le motif garde ses dimensions le long de la surface du support, pas en vue de dessus :
- parallèle : posé tel quel, sans déformation en X et Y ;
- cylindrique : la distance est mesurée le long de la surface dans un seul sens
  (autour de l'axe Y : le long de X, autour de l'axe X : le long de Y) ;
- sphérique : mesurée le long de la surface sur chaque rayon partant du point de départ.

Le point de départ est un coin ou le centre des deux boîtes, ou deux marqueurs.
Les hauteurs du motif s'ajoutent en Z à celles du support.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from . import galbe as GB
from . import progress

KINDS = (('parallele', 'Projection parallèle'), ('spherique', 'Sphérique'),
         ('cyl_y', 'Cylindrique, autour de l’axe Y'), ('cyl_x', 'Cylindrique, autour de l’axe X'))
ANCHORS = (('centre', 'Centre'), ('haut_gauche', 'Coin supérieur gauche'), ('haut_droite', 'Coin supérieur droit'),
           ('bas_gauche', 'Coin inférieur gauche'), ('bas_droite', 'Coin inférieur droit'), ('marqueurs', 'Marqueurs'))
MODES = (('ajouter', 'Ajouter au support'), ('soustraire', 'Soustraire du support'),
         ('seul', 'Garder seulement le relief enroulé'))
#: pas le long d'un rayon (enroulement sphérique)
RAY_STEPS = 64


@dataclass
class WrapSpec:
    kind: str = 'parallele'
    anchor: str = 'centre'
    mode: str = 'ajouter'
    copies_x: bool = False          # répété côte à côte en X, dans le galbe du support
    copies_y: bool = False
    resolution: float = 0.0         # pas de la carte (0 : celui du support)


def _anchor(box, anchor: str) -> tuple[float, float]:
    x0, y0, x1, y1 = box
    return {'haut_gauche': (x0, y1), 'haut_droite': (x1, y1), 'bas_gauche': (x0, y0),
            'bas_droite': (x1, y0)}.get(anchor, ((x0 + x1) / 2, (y0 + y1) / 2))


def _bilinear(H, x0: float, y1: float, res: float, X, Y):
    """Hauteurs de la carte H (pixels centrés) aux points (X, Y), bornées à la carte."""
    import numpy as np
    fx = np.clip((X - x0) / res - 0.5, 0.0, H.shape[1] - 1.0)
    fy = np.clip((y1 - Y) / res - 0.5, 0.0, H.shape[0] - 1.0)
    i0, j0 = fx.astype(np.int64), fy.astype(np.int64)
    i1, j1 = np.minimum(i0 + 1, H.shape[1] - 1), np.minimum(j0 + 1, H.shape[0] - 1)
    ax, ay = fx - i0, fy - j0
    return (H[j0, i0] * (1 - ax) + H[j0, i1] * ax) * (1 - ay) + (H[j1, i0] * (1 - ax) + H[j1, i1] * ax) * ay


def _along_surface(H, x0: float, y1: float, res: float, X, Y, ax: float, ay: float, kind: str):
    """(u, v) : position de chaque point par rapport au départ, mesurée le long de la surface selon `kind`."""
    import numpy as np
    if kind == 'cyl_y':                                  # le long de X, ligne par ligne
        d = np.diff(H, axis=1)
        s = np.concatenate((np.zeros((H.shape[0], 1)), np.cumsum(np.hypot(res, d), axis=1)), axis=1)
        k = int(np.clip(round((ax - x0) / res - 0.5), 0, H.shape[1] - 1))
        return s - s[:, k:k + 1] + (X[0, k] - ax), Y - ay
    if kind == 'cyl_x':                                  # le long de Y, colonne par colonne (lignes de haut en bas)
        d = np.diff(H, axis=0)
        s = np.concatenate((np.zeros((1, H.shape[1])), np.cumsum(np.hypot(res, d), axis=0)), axis=0)
        k = int(np.clip(round((y1 - ay) / res - 0.5), 0, H.shape[0] - 1))
        return X - ax, s[k:k + 1, :] - s + (Y[k, 0] - ay)
    if kind == 'spherique':
        dx, dy = X - ax, Y - ay
        r = np.hypot(dx, dy)
        length = np.zeros_like(r)
        before = _bilinear(H, x0, y1, res, np.array(float(ax)), np.array(float(ay)))
        for k in range(1, RAY_STEPS + 1):
            if k % 8 == 0:
                progress.check()
            t = k / RAY_STEPS
            h = _bilinear(H, x0, y1, res, ax + dx * t, ay + dy * t)
            length += np.hypot(r / RAY_STEPS, h - before)
            before = h
        with np.errstate(invalid='ignore', divide='ignore'):
            k = np.where(r > 1e-9, length / r, 1.0)
        return dx * k, dy * k
    return X - ax, Y - ay


def wrap_heights(base, box, motif, mbox, spec: WrapSpec, start=None, mstart=None):
    """Le motif enroulé : (hauteurs, x0, y1, pas). `base`, `motif` : (H, x0, y1, pas) de `galbe.decode` ;
    `start`, `mstart` : points de départ imposés sur l'un et l'autre (marqueurs)."""
    import numpy as np
    Hb, bx0, by1, bres = base
    Hm, mx0, my1, mres = motif
    res = spec.resolution if spec.resolution and spec.resolution > 0 else bres
    x0, y1, nx, ny, res = GB._grid(box, res)
    X, Y = np.meshgrid(x0 + (np.arange(nx) + 0.5) * res, y1 - (np.arange(ny) + 0.5) * res)
    H = _bilinear(Hb, bx0, by1, bres, X, Y) if abs(res - bres) > 1e-9 or Hb.shape != (ny, nx) else Hb.copy()
    ax, ay = start if start is not None else _anchor(box, spec.anchor)
    tx, ty = mstart if mstart is not None else _anchor(mbox, spec.anchor)
    u, v = _along_surface(H, x0, y1, res, X, Y, ax, ay, spec.kind)
    w, h = mbox[2] - mbox[0], mbox[3] - mbox[1]
    mu, mv = u + (tx - mbox[0]), v + (ty - mbox[1])              # position dans la boîte du motif
    if spec.copies_x:
        mu = np.mod(mu, w)
    if spec.copies_y:
        mv = np.mod(mv, h)
    inside = (mu >= 0) & (mu <= w) & (mv >= 0) & (mv <= h)
    if (spec.copies_x or spec.copies_y) and float(H.max()) > float(H.min()) + 1e-9:
        inside &= H > float(H.min()) + 1e-9                      # dans le galbe du support, pas toute sa boîte
    M = np.where(inside, _bilinear(Hm, mx0, my1, mres, mbox[0] + mu, mbox[1] + mv), 0.0)
    if spec.mode == 'soustraire':
        out = H - M
    elif spec.mode == 'seul':
        out = np.where(np.abs(M) > 1e-12, H + M, 0.0)
    else:
        out = H + M
    return out, x0, y1, res


def wrap(base_img, motif_img, spec: WrapSpec, markers=None):
    """L'image du support où le motif est enroulé ; None si un relief ne se relit pas (posé de travers).
    `markers` : (départ sur le support, départ sur le motif). ValueError('markers') s'ils manquent."""
    base, motif = GB.decode(base_img), GB.decode(motif_img)
    if base is None or motif is None:
        return None
    start = mstart = None
    if spec.anchor == 'marqueurs':
        if not markers or len(markers) < 2:
            raise ValueError('markers')
        start, mstart = markers[0], markers[1]
    H, x0, y1, res = wrap_heights(base, base_img.bbox(), motif, motif_img.bbox(), spec, start, mstart)
    g = GB.GalbeSpec.from_dict(base_img.extra.get('galbe'))
    g.z_max, g.z_min, g.resolution = float(H.max()), float(H.min()), res
    return GB.encode(H, x0, y1, res, g, base_img.tool, base_img.name or 'Relief')


def sphere_reach(radius: float, along: float) -> float:
    """Distance en vue de dessus d'un point à `along` mm le long d'une sphère de rayon `radius`, depuis son sommet."""
    return radius * math.sin(along / radius)
