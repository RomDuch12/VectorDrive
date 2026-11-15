"""Une portion de contour entre deux points quelconques : la retirer ou la remplacer.

Couper-supprimer, Transformer en segment, en arc, en courbe, en angle. Les points sont donnés par leur paramètre global
le long du contour (`trim.nearest_param`) : ils n'ont pas besoin d'être des nœuds, et le reste du contour ne change pas.
"""
from __future__ import annotations

import math

from .geom import Contour, Cubic, Line, arc_3points
from .trim import piece

KINDS = ('delete', 'segment', 'arc', 'curve', 'angle')
#: les transformations qui se règlent à la souris après le second point
SHAPED = ('arc', 'curve', 'angle')


def point_at(contour: Contour, g: float) -> tuple:
    segs = contour.segments
    i = int(math.floor(g + 1e-12))
    return segs[i % len(segs)].point(max(0.0, min(1.0, g - i)))


def span(contour: Contour, a: float, b: float, clockwise: bool = True) -> tuple:
    """Les paramètres (g0, g1) de la portion entre a et b, dans le sens du contour. Contour fermé : celle qu'on parcourt
    de a à b dans le sens horaire, ou, si `clockwise` est faux, dans l'autre sens."""
    if not contour.closed:
        return (a, b) if a <= b else (b, a)
    return (a, b) if (contour.signed_area() < 0) == clockwise else (b, a)


def portion(contour: Contour, g0: float, g1: float) -> Contour:
    return piece(contour, g0, g1)


def delete(contour: Contour, g0: float, g1: float) -> list:
    """Ce qui reste du contour sans la portion : un contour fermé s'ouvre, un contour ouvert donne jusqu'à deux morceaux."""
    if contour.closed:
        rest = piece(contour, g1, g0)
        return [rest] if rest.segments else []
    out = []
    if g0 > 1e-9:
        out.append(piece(contour, 0.0, g0))
    if g1 < len(contour.segments) - 1e-9:
        out.append(piece(contour, g1, float(len(contour.segments))))
    return out


def replace(contour: Contour, g0: float, g1: float, segments: list) -> Contour:
    """Le contour, sa portion remplacée par ces segments, qui vont du point g0 au point g1."""
    if contour.closed:
        return Contour(list(piece(contour, g1, g0).segments) + list(segments), True)
    head = list(piece(contour, 0.0, g0).segments) if g0 > 1e-9 else []
    tail = list(piece(contour, g1, float(len(contour.segments))).segments) if g1 < len(contour.segments) - 1e-9 else []
    return Contour(head + list(segments) + tail, False)


def new_segments(kind: str, a: tuple, b: tuple, h: tuple | None = None) -> list:
    """Ce qui remplace la portion, de a à b : `h` règle l'arc (il y passe), la courbe (en son milieu) ou l'angle (son sommet)."""
    if kind == 'angle' and h is not None:
        return [Line(a, h), Line(h, b)]
    if kind == 'arc' and h is not None:
        c = arc_3points(a, h, b)
        if c is not None:
            return list(c.segments)
    if kind == 'curve' and h is not None:
        qx, qy = 2 * h[0] - (a[0] + b[0]) / 2, 2 * h[1] - (a[1] + b[1]) / 2
        return [Cubic(a, (a[0] + 2 * (qx - a[0]) / 3, a[1] + 2 * (qy - a[1]) / 3),
                      (b[0] + 2 * (qx - b[0]) / 3, b[1] + 2 * (qy - b[1]) / 3), b)]
    return [Line(a, b)]
