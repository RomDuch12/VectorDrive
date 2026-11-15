"""Crayon et reconnaissance de formes (comme l'outil Shaper des logiciels
de dessin vectoriel) : un tracé à main levée devient la forme qu'il
esquisse — trait droit, rectangle (droit ou tourné de 45°), ellipse ou
cercle, triangle — sinon une courbe lissée (approximation en Bézier).
"""
from __future__ import annotations

import math

from .geom import Affine, Path, circle, polyline, rect

#: écarts tolérés, en part de la taille du tracé
LINE_TOL = 0.04
CLOSE_TOL = 0.18
SHAPE_TOL = 0.09


def _size(pts) -> float:
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return max(max(xs) - min(xs), max(ys) - min(ys), 1e-9)


def _dist_to_segment(p, a, b) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 < 1e-18 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


def _poly_error(pts, poly) -> float:
    ring = list(poly) + [poly[0]]
    return max(min(_dist_to_segment(p, a, b) for a, b in zip(ring, ring[1:])) for p in pts)


def recognize(pts) -> tuple[str, Path]:
    """(nature, tracé) du geste : 'trait', 'rectangle', 'ellipse',
    'triangle' ou 'courbe'."""
    from shapely.geometry import MultiPoint, Polygon
    from .fitcurve import approximate
    pts = [tuple(p[:2]) for p in pts]
    if len(pts) < 2:
        return 'courbe', Path()
    size = _size(pts)
    a, b = pts[0], pts[-1]
    if max(_dist_to_segment(p, a, b) for p in pts) <= LINE_TOL * max(math.dist(a, b), 1e-9) and math.dist(a, b) > 0.3 * size:
        return 'trait', Path([polyline([a, b])])
    closed = math.dist(a, b) <= CLOSE_TOL * size and len(pts) >= 8
    if closed:
        hull = MultiPoint(pts).convex_hull
        tol = SHAPE_TOL * size
        # rectangle : le plus petit rectangle tourné, angle ramené au pas de 45°
        mrr = hull.minimum_rotated_rectangle
        c = list(mrr.exterior.coords)[:4]
        e = max(((c[0], c[1]), (c[1], c[2])), key=lambda s: math.dist(*s))
        ang = math.degrees(math.atan2(e[1][1] - e[0][1], e[1][0] - e[0][0]))
        ang45 = round(ang / 45.0) * 45.0
        w, h = math.dist(c[0], c[1]), math.dist(c[1], c[2])
        cx, cy = mrr.centroid.x, mrr.centroid.y
        # côtés : la position moyenne du trait près de chaque bord (pas l'extrême, que le tremblé élargit)
        t = math.radians(ang45)
        ca, sa = math.cos(t), math.sin(t)
        us = sorted((p[0] - cx) * ca + (p[1] - cy) * sa for p in pts)
        vs = sorted(-(p[0] - cx) * sa + (p[1] - cy) * ca for p in pts)
        q = max(1, len(pts) // 8)
        u0, u1 = sum(us[:q]) / q, sum(us[-q:]) / q
        v0, v1 = sum(vs[:q]) / q, sum(vs[-q:]) / q
        cx, cy = cx + ca * (u0 + u1) / 2 - sa * (v0 + v1) / 2, cy + sa * (u0 + u1) / 2 + ca * (v0 + v1) / 2
        L, S = u1 - u0, v1 - v0
        box = rect(-L / 2, -S / 2, L, S).transformed(Affine.translation(cx, cy) @ Affine.rotation(ang45))
        box_pts = [s.start for s in box.segments]
        rect_err = _poly_error(pts, box_pts)
        # ellipse : centre = moyenne des points, demi-axes = √2 × moyenne quadratique le long des axes
        n = len(pts)
        ex, ey = sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n
        eu = [(p[0] - ex) * ca + (p[1] - ey) * sa for p in pts]
        ev = [-(p[0] - ex) * sa + (p[1] - ey) * ca for p in pts]
        ea = math.sqrt(2 * sum(u * u for u in eu) / n)
        eb = math.sqrt(2 * sum(v * v for v in ev) / n)
        ell_err = math.inf
        if ea > 1e-9 and eb > 1e-9:
            ell_err = max(abs(math.hypot(u / ea, v / eb) - 1.0) * min(ea, eb) for u, v in zip(eu, ev))
        # triangle : enveloppe simplifiée à trois sommets
        tri = hull.simplify(tol, preserve_topology=False)
        tri_pts = list(tri.exterior.coords)[:-1] if isinstance(tri, Polygon) else []
        tri_err = _poly_error(pts, tri_pts) if len(tri_pts) == 3 else math.inf
        best = min((rect_err, 'rectangle'), (ell_err, 'ellipse'), (tri_err, 'triangle'))
        if best[0] <= tol:
            if best[1] == 'rectangle':
                return 'rectangle', Path([box])
            if best[1] == 'ellipse':
                if abs(ea - eb) <= 0.08 * max(ea, eb):
                    return 'ellipse', Path([circle((ex, ey), (ea + eb) / 2)])
                e = circle((0, 0), 1).transformed(Affine.translation(ex, ey) @ Affine.rotation(ang45) @
                                                 Affine(ea, 0, 0, eb, 0, 0))
                return 'ellipse', Path([e])
            return 'triangle', Path([polyline(tri_pts, closed=True)])
    p = Path([polyline(pts + ([pts[0]] if closed else []), closed=closed)])
    return 'courbe', approximate(p, tol=max(0.02, 0.01 * size))
