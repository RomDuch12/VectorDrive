"""Brut d'un ensemble : le morceau de matière d'où il sort, pour le BAT.

Un objet ou un groupe (l'ensemble) porte `extra['brut']` : ses quatre coins (bas-gauche, bas-droit, haut-droit,
haut-gauche, dans cet ordre), qui le suivent quand il bouge ; l'épaisseur, un nom, et les cotes à écrire. Le brut n'est
ni gravé, ni usiné, ni exporté : il n'existe que pour le BAT et l'écran.
"""
from __future__ import annotations

import math

from . import geom
from .geom import Path

KEY = 'brut'
#: cotes écrites sur le BAT : celles du brut, celles de l'ensemble
COTES = {'les_deux': 'Brut et ensemble', 'brut': 'Le brut seulement', 'ensemble': 'L\'ensemble seulement',
         'aucune': 'Aucune'}


def of(item) -> dict | None:
    """Le brut de l'objet, s'il en a un de valable."""
    extra = getattr(item, 'extra', None)
    b = extra.get(KEY) if isinstance(extra, dict) else None
    if not isinstance(b, dict):
        return None
    corners = b.get('corners')
    if not isinstance(corners, (list, tuple)) or len(corners) != 4:
        return None
    return b


def make(item, width: float, height: float, *, dx: float = 0.0, dy: float = 0.0, thickness: float = 0.0,
         cotes: str = 'les_deux', name: str = '') -> dict:
    """Pose le brut, centré sur l'objet à (`dx`, `dy`) près. Rend le brut."""
    bb = item.bbox()
    if not bb:
        raise ValueError('objet vide')
    if not (width > 0 and height > 0):
        raise ValueError('dimensions du brut')
    cx, cy = (bb[0] + bb[2]) / 2 + dx, (bb[1] + bb[3]) / 2 + dy
    x0, y0, x1, y1 = cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2
    b = {'corners': [[x0, y0], [x1, y0], [x1, y1], [x0, y1]], 'thickness': float(thickness),
         'cotes': cotes if cotes in COTES else 'les_deux', 'name': str(name or '')}
    item.extra[KEY] = b
    return b


def remove(item) -> bool:
    return item.extra.pop(KEY, None) is not None


def size(b: dict) -> tuple[float, float]:
    c = b['corners']
    return math.dist(c[0], c[1]), math.dist(c[1], c[2])


def center_offset(item, b: dict) -> tuple[float, float]:
    """Décalage du centre du brut sur celui de l'objet."""
    bb = item.bbox()
    c = b['corners']
    if not bb:
        return 0.0, 0.0
    return (c[0][0] + c[2][0]) / 2 - (bb[0] + bb[2]) / 2, (c[0][1] + c[2][1]) / 2 - (bb[1] + bb[3]) / 2


def path(b: dict) -> Path:
    return Path([geom.polyline([tuple(p) for p in b['corners']], closed=True)])


def bbox(b: dict) -> tuple[float, float, float, float]:
    xs = [p[0] for p in b['corners']]
    ys = [p[1] for p in b['corners']]
    return min(xs), min(ys), max(xs), max(ys)


def walk(items, visible_only: bool = True):
    """(objet, brut) de tous les ensembles, à tous les niveaux de groupes."""
    for it in items:
        if visible_only and not getattr(it, 'visible', True):
            continue
        b = of(it)
        if b is not None:
            yield it, b
        kids = getattr(it, 'children', None)
        if kids:
            yield from walk(kids, visible_only)
