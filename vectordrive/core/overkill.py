"""Nettoyer les superpositions (comme NETTOYER / OVERKILL en DAO) : des
traits droits qui se recouvrent en partie (le même bord dessiné deux fois,
deux rectangles accolés) seraient gravés deux fois. Les morceaux communs
sont fusionnés : il ne reste qu'un trait par endroit, les traits qui se
prolongent sont joints, et un tracé qui se referme redevient fermé.

Seuls les traits faits de segments droits sont traités (les courbes
restent telles quelles) ; un outil (couleur) à la fois.
"""
from __future__ import annotations

from .geom import Line, Path, polyline


def straight_only(path: Path) -> bool:
    return bool(path.contours) and all(isinstance(s, Line) for c in path.contours for s in c.segments)


def _length(path: Path) -> float:
    return sum(c.length() for c in path.contours)


def overkill(paths: list[Path], tol: float = 1e-6) -> tuple[Path, float]:
    """Les tracés (droits) fusionnés sans superposition : (tracé, longueur
    retirée en mm)."""
    import shapely
    from shapely.geometry import LineString
    lines = []
    for p in paths:
        for c in p.contours:
            pts = [c.segments[0].start] + [s.end for s in c.segments] if c.segments else []
            if c.closed and pts and pts[0] != pts[-1]:
                pts.append(pts[0])
            if len(pts) >= 2:
                lines.append(LineString(pts))
    if not lines:
        return Path(), 0.0
    merged = shapely.line_merge(shapely.union_all(lines, grid_size=tol))
    out = []
    for g in shapely.get_parts(merged):
        coords = [tuple(xy) for xy in g.coords]
        clean = [coords[0]]
        for q in coords[1:]:
            if q != clean[-1]:
                clean.append(q)
        if len(clean) < 2:
            continue
        closed = len(clean) > 3 and clean[0] == clean[-1]
        out.append(polyline(clean[:-1] if closed else clean, closed=closed))
    new = Path(out)
    return new, max(0.0, sum(_length(p) for p in paths) - _length(new))
