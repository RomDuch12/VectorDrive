"""Gomme (comme l'outil Gomme des logiciels de dessin vectoriel) : le
passage d'une gomme ronde de rayon r efface ce qu'il couvre — les formes
fermées perdent la surface balayée (elles peuvent se couper en morceaux),
les traits ouverts sont coupés et leurs morceaux sous la gomme retirés.
Les courbes touchées sont aplaties (Approximation pour les relisser).
"""
from __future__ import annotations

from .geom import Path, polyline

FLAT = 0.005


def eraser_region(points, radius: float):
    from shapely.geometry import LineString, Point
    pts = [tuple(p[:2]) for p in points]
    if len(pts) == 1 or all(p == pts[0] for p in pts):
        return Point(pts[0]).buffer(radius)
    return LineString(pts).buffer(radius)


def paint(paths: list[Path], region) -> Path:
    """Pinceau à aplat : la zone peinte réunie aux tracés fermés donnés (ceux
    qu'elle touche) — une seule surface."""
    import shapely
    from .pathops import _from_shapely, _to_shapely
    geoms = [region] + [_to_shapely(Path([c for c in p.contours if c.closed and c.segments])) for p in paths]
    return _from_shapely(shapely.union_all([g for g in geoms if not g.is_empty]))


def erase(path: Path, region) -> Path | None:
    """Le tracé moins la zone gommée ; None s'il n'est pas touché (rendu tel
    quel par l'appelant), Path() s'il disparaît."""
    import shapely
    from shapely.geometry import LineString
    from .pathops import _from_shapely, _to_shapely
    b = path.bbox()
    if not b:
        return None
    bx = shapely.box(*b)
    if not bx.buffer(1e-9).intersects(region):
        return None
    closed = Path([c for c in path.contours if c.closed and c.segments])
    opened = [c for c in path.contours if not c.closed and c.segments]
    touched = False
    out = []
    if closed.contours:
        g = _to_shapely(closed)
        if g.intersects(region):
            touched = True
            out += _from_shapely(g.difference(region)).contours
        else:
            out += closed.contours
    for c in opened:
        ls = LineString(c.flatten(FLAT))
        if not ls.intersects(region):
            out.append(c)
            continue
        touched = True
        rest = ls.difference(region)
        for part in shapely.get_parts(rest):
            coords = [tuple(xy) for xy in part.coords]
            if len(coords) >= 2:
                out.append(polyline(coords))
    return Path(out) if touched else None
