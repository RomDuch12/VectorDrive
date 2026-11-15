"""Contour de zone (comme CONTOUR / BOUNDARY des logiciels de DAO) : un
clic dans une zone fermée par des traits — ouverts ou fermés, de formes
différentes, qui se croisent — donne le contour fermé de cette zone.

Les traits sont aplatis, coupés à leurs croisements, et les faces qu'ils
délimitent reconstruites ; la plus petite qui contient le point est
rendue, ses îlots en trous (ou sans, au choix). Les bouts de traits qui ne
ferment rien sont ignorés.

Tolérance d'écart (comme HPGAPTOL) : une zone presque fermée — des traits
qui ne se touchent pas tout à fait, à moins de `gap` — est fermée quand
même : les traits sont épaissis de gap/2, la zone prise entre eux, puis
regonflée de gap/2 (angles vifs gardés).
"""
from __future__ import annotations

from .geom import Path

#: précision de l'aplatissement des courbes (mm)
FLAT = 0.002


def boundary_at(paths, pt, *, islands: bool = True, tol: float = FLAT, gap: float = 0.0) -> Path | None:
    """Contour de la zone qui contient `pt`, délimitée par les traits de
    `paths` ; None si le point n'est dans aucune zone fermée (à `gap` près)."""
    import shapely
    from shapely.geometry import LineString, Point, Polygon
    from .pathops import _from_shapely
    lines = []
    for p in paths:
        for c in p.contours:
            pts = list(c.flatten(tol))
            if c.closed and len(pts) > 2 and pts[0] != pts[-1]:
                pts.append(pts[0])
            if len(pts) >= 2:
                lines.append(LineString(pts))
    if not lines:
        return None
    noded = shapely.union_all(lines)
    faces = [f for f in shapely.get_parts(shapely.polygonize(shapely.get_parts(noded))) if f.area > 1e-9]
    P = Point(pt)
    inside = [f for f in faces if f.contains(P)]
    if not inside:
        return _with_gap(noded, P, gap) if gap > 0 else None
    f = min(inside, key=lambda g: Polygon(g.exterior).area)
    outer = Polygon(f.exterior)
    if not islands:
        return _from_shapely(outer)
    # îlots : les faces posées dans celle-ci (polygonize ne les retranche pas toujours)
    isl = [Polygon(g.exterior) for g in faces if g is not f and Polygon(g.exterior).within(outer)
           and not Polygon(g.exterior).equals(outer)]
    if isl:
        f = f.difference(shapely.union_all(isl))
    return _from_shapely(f)


def _with_gap(lines, P, gap: float) -> Path | None:
    """Zone presque fermée : les traits épaissis de gap/2 bouchent les
    écarts ; la cavité qui contient P, regonflée de gap/2."""
    import shapely
    from shapely.geometry import Polygon
    from .pathops import _from_shapely
    walls = lines.buffer(gap / 2, cap_style=3, join_style=2, mitre_limit=5.0)   # bouts prolongés : écart bouché
    for poly in shapely.get_parts(walls):
        for ring in poly.interiors:
            hole = Polygon(ring)
            if hole.contains(P):
                out = hole.buffer(gap / 2, join_style=2, mitre_limit=5.0)
                return _from_shapely(out) if not out.is_empty else None
    return None
