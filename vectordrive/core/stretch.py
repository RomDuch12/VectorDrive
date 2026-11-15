"""Étirer (comme ÉTIRER des logiciels de DAO) : les nœuds pris dans une
fenêtre se déplacent, les autres restent ; les segments entre les deux
s'allongent ou se raccourcissent.

Règles par segment : une extrémité bouge si elle est dans la fenêtre ; une
poignée de Bézier suit l'extrémité à laquelle elle est attachée ; le point
de contrôle d'un arc (conique) ne bouge que si les deux extrémités bougent
(l'arc reste un arc) — sinon l'arc devient une conique qui rejoint ses
nouveaux bouts.
"""
from __future__ import annotations

from dataclasses import replace

from .geom import Conic, Contour, Cubic, Line, Path


def _in(p, rect) -> bool:
    x0, y0, x1, y1 = rect
    return min(x0, x1) <= p[0] <= max(x0, x1) and min(y0, y1) <= p[1] <= max(y0, y1)


def stretch_contour(c: Contour, rect, dx: float, dy: float) -> tuple[Contour, int]:
    """Contour étiré, et le nombre de nœuds déplacés."""
    def mv(p):
        return (p[0] + dx, p[1] + dy)
    out, n = [], 0
    for s in c.segments:
        a, b = _in(s.start, rect), _in(s.end, rect)
        n += a
        if isinstance(s, Line):
            out.append(Line(mv(s.p0) if a else s.p0, mv(s.p1) if b else s.p1))
        elif isinstance(s, Cubic):
            out.append(Cubic(mv(s.p0) if a else s.p0, mv(s.p1) if a else s.p1,
                             mv(s.p2) if b else s.p2, mv(s.p3) if b else s.p3))
        elif isinstance(s, Conic):
            out.append(replace(s, p0=mv(s.p0) if a else s.p0, p1=mv(s.p1) if a and b else s.p1,
                               p2=mv(s.p2) if b else s.p2))
        else:
            out.append(s)
    if not c.closed and c.segments and _in(c.segments[-1].end, rect):
        n += 1
    return Contour(out, c.closed), n


def stretch_path(path: Path, rect, dx: float, dy: float) -> tuple[Path, int]:
    """Tracé étiré (contours ouverts et fermés) ; nombre de nœuds déplacés."""
    cs, n = [], 0
    for c in path.contours:
        nc, k = stretch_contour(c, rect, dx, dy)
        cs.append(nc)
        n += k
    return Path(cs), n
