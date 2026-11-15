"""Le contour d'un trait, avec ses coins et ses bouts, et l'enveloppe d'un dessin (TypeEdit : Couteaux).

L'enveloppe prépare un parcours de gravure ou de balayage : rectangle, cercle, convexe ou concave, avec une marge. La
concave colle au dessin pour économiser la matière et le temps d'usinage : c'est sa fermeture morphologique (grossie puis
amincie), la plus petite distance qui rende une seule pièce.
"""
from __future__ import annotations

from . import geom
from .geom import Path
from .pathops import FLATTEN, _from_shapely
from .parallel import stroke_checked

CORNERS = {'aigu': 'mitre', 'chanfrein': 'bevel', 'arrondi': 'round'}
ENDS = {'plat': 'flat', 'arrondi': 'round'}
ENVELOPES = ('rectangle', 'cercle', 'convexe', 'concave')
#: un coin aigu s'arrête au-delà de ce multiple du rayon, sinon un angle très fermé part très loin
MITRE_LIMIT = 8.0


def stroke(path: Path, radius: float, corner: str = 'arrondi', end: str = 'arrondi') -> Path:
    """Le contour fermé d'un trait de ce rayon (la moitié de l'épaisseur). Coins et bouts arrondis : exact, les courbes
    restent des arcs ; sinon les courbes d'origine sont suivies à 2 µm près."""
    if corner not in CORNERS or end not in ENDS:
        raise ValueError((corner, end))
    r = abs(radius)
    if r < 1e-9:
        raise ValueError('rayon nul')
    if corner == 'arrondi' and end == 'arrondi':
        return stroke_checked(path, 2 * r)[0]
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    lines = [LineString(p) for p in path.flatten(FLATTEN) if len(p) > 1]
    return _from_shapely(unary_union([ln.buffer(r, quad_segs=32, cap_style=ENDS[end], join_style=CORNERS[corner],
                                                mitre_limit=MITRE_LIMIT) for ln in lines]))


def _points(path: Path) -> list:
    return [q for pts in path.flatten(FLATTEN) for q in pts]


def _rings(g) -> Path:
    """Les seuls contours extérieurs : une enveloppe n'a pas de trou."""
    polys = list(getattr(g, 'geoms', [g]))
    return Path([geom.polyline(list(p.exterior.coords)[:-1], closed=True).close() for p in polys if not p.is_empty])


def concave(path: Path) -> object:
    """La fermeture du dessin : la plus petite qui donne une seule pièce, au pire son enveloppe convexe."""
    from shapely.geometry import LineString, MultiPoint, Polygon
    from shapely.ops import unary_union
    flat = [p for p in path.flatten(FLATTEN) if len(p) > 1]
    ink = unary_union([Polygon(p).buffer(0) if len(p) >= 4 and geom.dist(p[0], p[-1]) < 1e-9 else LineString(p) for p in flat])
    x0, y0, x1, y1 = ink.bounds
    size = max(x1 - x0, y1 - y0, 1e-6)
    d = size / 64
    while d <= size:
        g = ink.buffer(d, quad_segs=8).buffer(-d, quad_segs=8).union(ink)
        if g.geom_type == 'Polygon' and not g.is_empty:
            return g
        d *= 2
    return MultiPoint([q for p in flat for q in p]).convex_hull


def envelope(path: Path, kind: str, margin: float = 0.0) -> Path:
    """L'enveloppe du dessin, à `margin` de lui, en un contour fermé."""
    from shapely.geometry import MultiPoint
    pts = _points(path)
    if not pts:
        return Path()
    m = max(0.0, margin)
    if kind == 'rectangle':
        x0, y0, x1, y1 = path.bbox()
        return Path([geom.rect(x0 - m, y0 - m, x1 - x0 + 2 * m, y1 - y0 + 2 * m)])
    if kind == 'cercle':
        import shapely
        hull = MultiPoint(pts)
        disc = shapely.minimum_bounding_circle(hull)
        c = disc.centroid
        return Path([geom.circle((c.x, c.y), float(shapely.minimum_bounding_radius(hull)) + m)])
    if kind == 'convexe':
        g = MultiPoint(pts).convex_hull
    elif kind == 'concave':
        g = concave(path)
    else:
        raise ValueError(kind)
    if m > 0:
        g = g.buffer(m, quad_segs=16)
    elif g.geom_type != 'Polygon':                      # dessin aligné : la marge nulle ne donne pas de surface
        g = g.buffer(1e-6)
    return _rings(g)

