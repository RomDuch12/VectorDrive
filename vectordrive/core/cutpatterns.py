"""Stratégies de découpe (TypeEdit : FAO ▸ Découpe) : géométries de découpe
d'une plaque en pièces — cercles en quinconce, octogones, parts de gâteau,
rectangles, triangles, rondelle. Les traits de partage intérieurs sont des
traits simples (une seule passe entre deux pièces voisines : découpe sur
ligne commune) ; le contour de la plaque est à part.

Mêmes entrées que les scripts de TypeEdit (dimensions de la plaque, nombre
de pièces, rayon, décalage en X et en Y) ; la géométrie est calculée ici.
"""
from __future__ import annotations

import math

from .geom import Contour, Line, Path, circle, polyline, rect

#: motif → libellé
PATTERNS = {
    'cercles': 'Cercles en quinconce', 'octogones': 'Octogones', 'portions': 'Parts de gâteau',
    'rectangles': 'Rectangles', 'triangles': 'Triangles', 'rondelle': 'Rondelle',
}


#: au plus autant de traits (cercles, octogones, traits de partage) : au-delà, `TooMany` — 10 000 000 pièces par
#: côté (les champs le permettent) donnaient 10¹⁴ diagonales, VectorDrive figé puis à court de mémoire
MAX_PIECES = 100_000


class TooMany(ValueError):
    """Trop de pièces : `count` traits demandés, `MAX_PIECES` au plus."""

    def __init__(self, count: float):
        count = math.inf if count > 1e300 else float(count)   # (un entier démesuré ne se formate pas en .0f)
        super().__init__(f'{count:.0f} traits (au plus {MAX_PIECES})')
        self.count = count


def _check(count: float) -> None:
    if not count <= MAX_PIECES:                      # (nan compris)
        raise TooMany(count)


def _seg(a, b) -> Contour:
    return Contour([Line(a, b)], False)


def staggered_circles(length: float, width: float, radius: float, dx: float = 0.0, dy: float = 0.0) -> tuple:
    """Cercles de rayon donné en quinconce dans la plaque (rangées décalées
    d'un rayon, écartées de r√3), seuls ceux qui y tiennent entiers.
    Rend (plaque, cercles)."""
    plate = Path([rect(dx, dy, length, width)])
    out = []
    if radius > 0:
        rows = max(0.0, (width + 1e-9 - 2 * radius) / (radius * math.sqrt(3)) + 1)     # (la tolérance de la
        per = max(0.0, (length + 1e-9) / (2 * radius))                                 # boucle comprise)
        _check((math.floor(rows) if rows < 1e18 else rows) * per)
        row, y = 0, dy + radius
        while y + radius <= dy + width + 1e-9:
            x = dx + radius + (radius if row % 2 else 0.0)
            while x + radius <= dx + length + 1e-9:
                out.append(circle((x, y), radius))
                x += 2 * radius
            row += 1
            y += radius * math.sqrt(3)
    return plate, Path(out)


def octagons(length: float, width: float, per_row: int, dx: float = 0.0, dy: float = 0.0) -> tuple:
    """Octogones réguliers jointifs par leurs côtés, `per_row` sur la longueur,
    autant de rangées que la largeur en contient (pavage octogones-carrés)."""
    plate = Path([rect(dx, dy, length, width)])
    n = max(1, int(per_row))
    w = length / n                                     # largeur d'un octogone (entre deux côtés)
    a = w / (1 + math.sqrt(2))                         # côté
    c = (w - a) / 2                                    # coin coupé
    out = []
    rows = int((width + 1e-9) // w) if w > 0 else 0
    _check(rows * n)
    for j in range(rows):
        for i in range(n):
            x0, y0 = dx + i * w, dy + j * w
            pts = [(x0 + c, y0), (x0 + c + a, y0), (x0 + w, y0 + c), (x0 + w, y0 + c + a),
                   (x0 + c + a, y0 + w), (x0 + c, y0 + w), (x0, y0 + c + a), (x0, y0 + c)]
            out.append(polyline(pts, closed=True))
    return plate, Path(out)


def pie(radius: float, parts: int, dx: float = 0.0, dy: float = 0.0, cut_outer: bool = True) -> tuple:
    """Disque partagé en `parts` parts égales : rayons du centre au bord ;
    le cercle extérieur à part (découpé ou non). Centre en (dx + r, dy + r)."""
    cx, cy = dx + radius, dy + radius
    n = max(1, int(parts))
    _check(n)
    spokes = [_seg((cx, cy), (cx + radius * math.cos(2 * math.pi * k / n), cy + radius * math.sin(2 * math.pi * k / n)))
              for k in range(n)] if n > 1 else []
    outer = Path([circle((cx, cy), radius)]) if cut_outer else Path()
    return outer, Path(spokes)


def rectangles(length: float, width: float, nx: int, ny: int, dx: float = 0.0, dy: float = 0.0) -> tuple:
    """Plaque partagée en nx × ny rectangles : traits de partage (lignes communes)."""
    plate = Path([rect(dx, dy, length, width)])
    nx, ny = max(1, int(nx)), max(1, int(ny))
    _check(nx + ny)
    lines = [_seg((dx + length * i / nx, dy), (dx + length * i / nx, dy + width)) for i in range(1, nx)]
    lines += [_seg((dx, dy + width * j / ny), (dx + length, dy + width * j / ny)) for j in range(1, ny)]
    return plate, Path(lines)


def triangles(length: float, width: float, nx: int, ny: int, dx: float = 0.0, dy: float = 0.0,
              rising: bool = True) -> tuple:
    """Plaque partagée en nx × ny rectangles coupés chacun par sa diagonale
    (montante ou descendante) : 2 × nx × ny triangles."""
    _check(max(1, int(nx)) * max(1, int(ny)) + max(1, int(nx)) + max(1, int(ny)))
    plate, grid = rectangles(length, width, nx, ny, dx, dy)
    nx, ny = max(1, int(nx)), max(1, int(ny))
    w, h = length / nx, width / ny
    diag = []
    for j in range(ny):
        for i in range(nx):
            x0, y0 = dx + i * w, dy + j * h
            diag.append(_seg((x0, y0), (x0 + w, y0 + h)) if rising else _seg((x0, y0 + h), (x0 + w, y0)))
    return plate, Path(grid.contours + diag)


def washer(cx: float, cy: float, outer: float, inner: float) -> tuple:
    """Rondelle : cercle extérieur, cercle intérieur (à découper d'abord)."""
    return Path([circle((cx, cy), outer)]), Path([circle((cx, cy), inner)] if 0 < inner < outer else [])
