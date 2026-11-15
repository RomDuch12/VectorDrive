"""Texture (TypeEdit : Effets spéciaux ▸ Texture) : une courbe qui remplit
l'espace — Peano, Hilbert, Lebesgue, Sierpinski, Moore — tracée sur le carré
qui couvre la sélection, puis coupée à ses contours fermés (les contours
intérieurs sont exclus, comme les trous d'une lettre). Décor de gravure.
"""
from __future__ import annotations

import math

from .geom import Contour, Line, Path

#: courbe → (libellé, itérations par défaut, itérations au plus)
CURVES = {
    'hilbert': ('Courbe de Hilbert', 4, 8),
    'peano': ('Courbe de Peano', 3, 5),
    'moore': ('Courbe de Moore (fermée)', 4, 7),
    'sierpinski': ('Courbe de Sierpinski (fermée)', 3, 6),
    'lebesgue': ('Courbe de Lebesgue (ordre Z)', 4, 8),
}
#: systèmes de Lindenmayer à angle droit : (axiome, règles)
_LSYS = {
    'hilbert': ('A', {'A': '+BF-AFA-FB+', 'B': '-AF+BFB+FA-'}),
    'peano': ('X', {'X': 'XFYFX+F+YFXFY-F-XFYFX', 'Y': 'YFXFY-F-XFYFX+F+YFXFY'}),
    'moore': ('LFL+F+LFL', {'L': '-RF+LFL+FR-', 'R': '+LF-RFR-FL+'}),
    'sierpinski': ('F+XF+F+XF', {'X': 'XF-F+F-XF+F+XF-F+F-X'}),
}


def _turtle(kind: str, n: int) -> list:
    axiom, rules = _LSYS[kind]
    s = axiom
    for _ in range(n):
        s = ''.join(rules.get(ch, ch) for ch in s)
    x = y = 0
    dx, dy = 1, 0
    pts = [(0, 0)]
    for ch in s:
        if ch == 'F':
            x, y = x + dx, y + dy
            pts.append((x, y))
        elif ch == '+':
            dx, dy = -dy, dx
        elif ch == '-':
            dx, dy = dy, -dx
    return pts


def _lebesgue(n: int) -> list:
    """Ordre Z (Morton) : les centres des cases d'une grille 2ⁿ × 2ⁿ."""
    out = []
    for k in range(4 ** n):
        x = y = 0
        for b in range(n):
            x |= ((k >> (2 * b)) & 1) << b
            y |= ((k >> (2 * b + 1)) & 1) << b
        out.append((x, y))
    return out


def curve_points(kind: str, iterations: int) -> list:
    """Points de la courbe, dans leur repère entier."""
    lo, hi = 1, CURVES.get(kind, ('', 4, 8))[2]
    n = max(lo, min(int(iterations), hi))
    if kind == 'lebesgue':
        return _lebesgue(n)
    pts = _turtle(kind, n)
    if kind == 'sierpinski':                          # tracée en losange : remise d'équerre pour couvrir le carré
        pts = [(x - y, x + y) for x, y in pts]
    return pts


def fit(points: list, box) -> list:
    """Points ramenés dans le carré qui couvre `box` (x0, y0, x1, y1), une
    demi-case de marge pour que la courbe déborde un peu des contours."""
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    span = max(max(xs) - min(xs), max(ys) - min(ys), 1)
    side = max(box[2] - box[0], box[3] - box[1])
    cell = side / span
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    mx, my = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    k = (side + cell) / span
    return [(cx + (x - mx) * k, cy + (y - my) * k) for x, y in points]


def texture(path: Path, kind: str = 'hilbert', iterations: int = 4, border: bool = False) -> Path:
    """La courbe choisie, coupée aux contours fermés de `path` (règle
    pair-impair : un contour intérieur est un trou) ; `border` : les
    contours en plus."""
    from shapely.geometry import LineString
    from . import pathops
    closed = Path([c for c in path.contours if c.closed and c.segments])
    if not closed.contours:
        return Path()
    region = pathops._to_shapely(pathops.normalize(closed))
    if region.is_empty:
        return Path()
    pts = fit(curve_points(kind, iterations), region.bounds)
    cut = LineString(pts).intersection(region)
    out = []
    for g in getattr(cut, 'geoms', [cut]):
        if g.geom_type != 'LineString' or g.is_empty:
            continue
        c = list(g.coords)
        segs = [Line(a, b) for a, b in zip(c, c[1:]) if math.dist(a, b) > 1e-12]
        if segs:
            out.append(Contour(segs, False))
    if border:
        out += closed.contours
    return Path(out)
