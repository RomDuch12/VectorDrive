"""Convertir des courbes (TypeEdit) : le cercle, l'ellipse ou le rectangle le plus proche d'un contour.

Les trois se calent sur le centre de gravité et les moments de la surface du contour : un dessin à main levée tremblé donne
une forme stable, et un vrai cercle, une vraie ellipse ou un vrai rectangle se retrouvent exactement. Le contour garde son
sens de parcours.
"""
from __future__ import annotations

import math

from . import geom
from .geom import Affine, Contour, Path

KINDS = ('cercle', 'ellipse', 'rectangle')
#: un contour plus petit que cette surface (mm²) n'a pas de forme à reconnaître : un trait droit par exemple
MIN_AREA = 1e-6


def moments(c: Contour, tol: float = 0.0005) -> tuple | None:
    """(aire signée, centre X, centre Y, variance X, variance Y, covariance) de la surface du contour ; None si elle est nulle."""
    pts = c.flatten(tol)
    if len(pts) < 3:
        return None
    x0, y0 = pts[0]                                     # près de l'origine : pas de perte de précision loin de 0
    q = [(x - x0, y - y0) for x, y in pts]
    if q[0] != q[-1]:
        q.append(q[0])
    a = sx = sy = xx = yy = xy = 0.0
    for (x1, y1), (x2, y2) in zip(q, q[1:]):
        k = x1 * y2 - x2 * y1
        a += k
        sx += (x1 + x2) * k
        sy += (y1 + y2) * k
        xx += (x1 * x1 + x1 * x2 + x2 * x2) * k
        yy += (y1 * y1 + y1 * y2 + y2 * y2) * k
        xy += (x1 * y2 + 2 * x1 * y1 + 2 * x2 * y2 + x2 * y1) * k
    a /= 2
    if abs(a) < MIN_AREA:
        return None
    cx, cy = sx / (6 * a), sy / (6 * a)
    return (a, cx + x0, cy + y0, xx / (12 * a) - cx * cx, yy / (12 * a) - cy * cy, xy / (24 * a) - cx * cy)


def _same_way(new: Contour, area: float) -> Contour:
    return new if (new.signed_area() > 0) == (area > 0) else new.reversed()


def to_circle(c: Contour) -> Contour | None:
    """Le cercle de même centre de gravité et de même surface."""
    m = moments(c)
    if m is None:
        return None
    return _same_way(geom.circle((m[1], m[2]), math.sqrt(abs(m[0]) / math.pi)), m[0])


def to_ellipse(c: Contour) -> Contour | None:
    """L'ellipse de mêmes moments : pour une surface elliptique, la variance sur un axe vaut le quart de son carré."""
    m = moments(c)
    if m is None:
        return None
    area, cx, cy, vx, vy, cov = m
    mid, half = (vx + vy) / 2, math.hypot((vx - vy) / 2, cov)
    a, b = 2 * math.sqrt(max(mid + half, 0.0)), 2 * math.sqrt(max(mid - half, 0.0))
    if b < 1e-9:
        return None
    angle = math.degrees(math.atan2(2 * cov, vx - vy)) / 2
    place = Affine.translation(cx, cy) @ Affine.rotation(angle) @ Affine.scaling(a, b)
    return _same_way(geom.circle((0.0, 0.0), 1.0).transformed(place), area)


def _direction(c: Contour) -> float:
    """L'angle du plus petit rectangle englobant, que les moments ne donnent pas : un carré n'a pas d'axe principal."""
    from shapely.geometry import Polygon
    box = Polygon(c.flatten(0.0005)).buffer(0).minimum_rotated_rectangle
    (x0, y0), (x1, y1) = list(box.exterior.coords)[:2]
    return math.atan2(y1 - y0, x1 - x0)


def to_rectangle(c: Contour) -> Contour | None:
    """Le rectangle de mêmes moments, dans l'axe du contour : pour un rectangle, la variance sur un côté vaut son carré / 12."""
    m = moments(c)
    if m is None:
        return None
    area, cx, cy, vx, vy, cov = m
    t = _direction(c)
    co, si = math.cos(t), math.sin(t)
    w = math.sqrt(max(12 * (vx * co * co + 2 * cov * si * co + vy * si * si), 0.0))
    h = math.sqrt(max(12 * (vx * si * si - 2 * cov * si * co + vy * co * co), 0.0))
    if w < 1e-9 or h < 1e-9:
        return None
    corners = [(cx + u * w / 2 * co - v * h / 2 * si, cy + u * w / 2 * si + v * h / 2 * co)
               for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    return _same_way(geom.polyline(corners, closed=True).close(), area)


MAKERS = {'cercle': to_circle, 'ellipse': to_ellipse, 'rectangle': to_rectangle}


def convert(path: Path, kind: str) -> tuple:
    """(tracé, nombre de contours convertis). Un contour sans surface reste tel quel."""
    make = MAKERS[kind]
    out, n = [], 0
    for c in path.contours:
        new = make(c)
        out.append(c if new is None else new)
        n += new is not None
    return Path(out), n
