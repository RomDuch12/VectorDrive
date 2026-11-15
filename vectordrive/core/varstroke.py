"""Trait à largeur variable (comme le profil de largeur des logiciels de
dessin vectoriel) : un trait devient le contour fermé d'une bande dont la
largeur suit un profil le long du trait — de la largeur de départ à celle
d'arrivée, effilé aux deux bouts, ou ondulé. Pour graver des pleins et des
déliés, des feuilles, des pointes.
"""
from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass, field

from .geom import Path

PROFILES = (('lineaire', "De la largeur de départ à celle d'arrivée"), ('effile', 'Effilé aux deux bouts'),
            ('ondule', 'Ondulé'))

#: profils tout faits, d'après VectorCraft (crates/doc/src/appearance.rs) : (abscisse, part de la largeur)
PRESETS = {
    'pointe_debut': ((0.0, 0.0), (1.0, 1.0)),
    'pointe_fin': ((0.0, 1.0), (1.0, 0.0)),
    'pincement': ((0.0, 1.0), (0.5, 0.25), (1.0, 1.0)),
    'goutte': ((0.0, 0.0), (0.2, 1.0), (1.0, 0.0)),
    'vague': ((0.0, 0.3), (0.25, 1.0), (0.5, 0.3), (0.75, 1.0), (1.0, 0.3)),
}


@dataclass
class VarStrokeSpec:
    profile: str = 'effile'
    w_start: float = 0.0            # largeur au départ (mm) — effilé : largeur au milieu = w_end
    w_end: float = 2.0              # largeur à l'arrivée (mm)
    waves: int = 4                  # ondulé : nombre d'ondes
    tolerance: float = 0.01         # aplatissement des courbes (mm)
    knots: list = field(default_factory=list)            # profil 'points' : (abscisse, à gauche, à droite) en mm


def width_at(spec: VarStrokeSpec, t: float) -> float:
    """Largeur à l'abscisse relative t (0 au départ, 1 à l'arrivée)."""
    a, b = max(0.0, spec.w_start), max(0.0, spec.w_end)
    if spec.profile == 'effile':
        return max(a, b) * math.sin(math.pi * min(1.0, max(0.0, t)))
    if spec.profile == 'ondule':
        k = 0.5 - 0.5 * math.cos(2 * math.pi * max(1, int(spec.waves)) * t)
        return a + (b - a) * k
    if spec.profile in PRESETS:
        k = _interpolate(PRESETS[spec.profile], t)
        return b * k
    return a + (b - a) * t


def _interpolate(points, t: float) -> float:
    """La valeur à t, entre des points (abscisse, valeur) rangés par abscisse. La courbe passe par eux sans cassure
    et sans jamais les dépasser (cubique monotone de Fritsch et Carlson) : un point de largeur ne fait pas de coude visible
    sur le contour gravé, et aucune largeur n'apparaît au-delà de celles qu'on a données."""
    if t <= points[0][0]:
        return points[0][1]
    if t >= points[-1][0]:
        return points[-1][1]
    i = bisect_right([p[0] for p in points], t)
    (t0, v0), (t1, v1) = points[i - 1], points[i]
    h = t1 - t0
    if h <= 0.0:
        return v1

    def rise(k):
        return (points[k + 1][1] - points[k][1]) / (points[k + 1][0] - points[k][0]) if points[k + 1][0] > points[k][0] else 0.0

    def slope(k):
        if k <= 0:
            return rise(0)
        if k >= len(points) - 1:
            return rise(len(points) - 2)
        a, b = rise(k - 1), rise(k)
        if a * b <= 0.0:
            return 0.0
        return 2.0 * a * b / (a + b)
    u = (t - t0) / h
    m0, m1 = slope(i - 1) * h, slope(i) * h
    return (v0 * (1 + 2 * u) * (1 - u) ** 2 + m0 * u * (1 - u) ** 2 + v1 * u * u * (3 - 2 * u) + m1 * u * u * (u - 1))


def sides_at(spec: VarStrokeSpec, t: float) -> tuple[float, float]:
    """Ce que la bande prend à gauche et à droite du trait, à l'abscisse relative t."""
    if spec.profile == 'points':
        if not spec.knots:
            return 0.0, 0.0
        knots = sorted(spec.knots, key=lambda k: k[0])
        return (max(0.0, _interpolate([(k[0], k[1]) for k in knots], t)),
                max(0.0, _interpolate([(k[0], k[2]) for k in knots], t)))
    h = width_at(spec, t) / 2.0
    return h, h


def band(points, spec: VarStrokeSpec, closed: bool = False):
    """Polygone (shapely) de la bande autour de la polyligne `points`."""
    import shapely
    from shapely.geometry import Polygon
    pts = [tuple(p[:2]) for p in points]
    clean = [pts[0]] if pts else []
    for p in pts[1:]:
        if math.dist(p, clean[-1]) > 1e-9:
            clean.append(p)
    pts = clean
    if len(pts) < 2:
        return Polygon()
    if closed and math.dist(pts[0], pts[-1]) > 1e-9:
        pts.append(pts[0])
    # largeur qui varie : assez de points le long des segments droits
    total = sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
    step = max(0.02, total / 400)
    dense = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        k = max(1, int(math.ceil(math.dist(a, b) / step)))
        dense += [(a[0] + (b[0] - a[0]) * j / k, a[1] + (b[1] - a[1]) * j / k) for j in range(1, k + 1)]
    pts = dense
    if closed and spec.profile == 'points' and spec.knots:               # le raccord du tour ne fait pas de marche
        knots = sorted(spec.knots, key=lambda k: k[0])
        span = 1.0 - knots[-1][0] + knots[0][0]
        if span > 0:
            f = (1.0 - knots[-1][0]) / span
            seam = tuple(knots[-1][j] + (knots[0][j] - knots[-1][j]) * f for j in (1, 2))
            spec = VarStrokeSpec(profile='points', knots=[(0.0, *seam)] + knots + [(1.0, *seam)])
    L = [0.0]
    for a, b in zip(pts, pts[1:]):
        L.append(L[-1] + math.dist(a, b))
    total = L[-1] or 1.0
    left, right = [], []
    n = len(pts)
    for i, p in enumerate(pts):
        if closed and (i == 0 or i == n - 1):
            a, b = pts[-2], pts[1]
        else:
            a, b = pts[max(0, i - 1)], pts[min(n - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        d = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / d, dx / d
        hl, hr = sides_at(spec, L[i] / total)
        left.append((p[0] + nx * hl, p[1] + ny * hl))
        right.append((p[0] - nx * hr, p[1] - ny * hr))
    if closed:
        outer, inner = Polygon(left), Polygon(right)
        if outer.is_valid and inner.is_valid:
            return outer.symmetric_difference(inner).buffer(0)
    else:
        whole = Polygon(left + right[::-1])
        if whole.is_valid:
            return whole
    # un virage plus serré que la largeur, ou un trait qui se croise : tranche par tranche, rien ne se perd
    slices = [Polygon([left[i], left[i + 1], right[i + 1], right[i]]).buffer(0) for i in range(n - 1)]
    return shapely.union_all([s for s in slices if not s.is_empty])


def nib(width: float, angle: float, ratio: float = 0.1, sides: int = 24):
    """La plume : une ellipse de grand axe `width`, penchée de `angle` degrés, d'épaisseur `ratio` × `width`. Points autour."""
    a, b = max(width, 0.0) / 2.0, max(min(ratio, 1.0), 0.0) * max(width, 0.0) / 2.0
    co, si = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    out = []
    for i in range(sides):
        u = 2.0 * math.pi * i / sides
        x, y = a * math.cos(u), b * math.sin(u)
        out.append((x * co - y * si, x * si + y * co))
    return out


def nib_stroke(path: Path, width: float, angle: float = 30.0, ratio: float = 0.1, tolerance: float = 0.02) -> Path:
    """Le trait tel que le trace une plume qui ne tourne pas : large en travers de la plume, fin dans son sens. Chaque
    morceau du trait balaie l'enveloppe convexe de la plume à ses deux bouts ; la réunion est exacte pour une plume convexe."""
    import shapely
    from shapely.geometry import MultiPoint
    from .pathops import _from_shapely
    pen = nib(width, angle, ratio)
    parts = []
    for c in path.contours:
        if not c.segments:
            continue
        pts = [tuple(p[:2]) for p in c.flatten(tolerance)]
        if c.closed and pts and math.dist(pts[0], pts[-1]) > 1e-9:
            pts.append(pts[0])
        for a, b in zip(pts, pts[1:]):
            hull = MultiPoint([(a[0] + x, a[1] + y) for x, y in pen] + [(b[0] + x, b[1] + y) for x, y in pen]).convex_hull
            if hull.geom_type == 'Polygon' and hull.area > 0:
                parts.append(hull)
    if not parts:
        return Path()
    return _from_shapely(shapely.union_all(parts))


def var_stroke(path: Path, spec: VarStrokeSpec) -> Path:
    """Contours fermés des bandes de chaque trait du tracé."""
    import shapely
    from .pathops import _from_shapely
    polys = []
    for c in path.contours:
        if c.segments:
            g = band(c.flatten(spec.tolerance), spec, c.closed)
            if not g.is_empty:
                polys.append(g)
    if not polys:
        return Path()
    return _from_shapely(shapely.union_all(polys))
