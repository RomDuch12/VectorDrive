"""Repères : les côtés droits d'un objet changés en repères, des repères répartis sur un rectangle.

Les repères du document : `[['h', y] | ['v', x]]`, et les lignes de construction `[[x, y, angle]]`.
"""
from __future__ import annotations

import math

from .document import Group, Shape
from .geom import Line, dist

MAX_GUIDES = 400
_NEAR = 1e-6


def _straight(path) -> list[tuple]:
    return [(s.p0, s.p1) for c in path.contours for s in c.segments if isinstance(s, Line) and dist(s.p0, s.p1) > 1e-9]


def lines_of(items) -> list[tuple[float, float, float]]:
    """Les droites (x, y, angle) des objets : leurs côtés droits, sinon les quatre côtés de leur boîte."""
    out: list[tuple[float, float, float]] = []

    def walk(it) -> None:
        if not it.visible:
            return
        if isinstance(it, Group):
            for ch in it.children:
                walk(ch)
            return
        edges = _straight(it.path) if isinstance(it, Shape) and it.path else []
        if edges:
            for a, b in edges:
                out.append((a[0], a[1], math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180.0))
            return
        box = it.bbox()
        if box:
            out.extend(((box[0], box[1], 0.0), (box[0], box[3], 0.0), (box[0], box[1], 90.0), (box[2], box[1], 90.0)))
    for it in items:
        walk(it)
    return out


def split(lines) -> tuple[list, list]:
    """Horizontales et verticales en repères ordinaires, les autres en lignes de construction ; sans doublon."""
    guides, obliques, seen = [], [], set()
    for x, y, a in lines:
        a = float(a) % 180.0
        if min(a, 180.0 - a) < _NEAR:
            key = ('h', round(y, 6))
            if key not in seen:
                guides.append(['h', float(y)])
        elif abs(a - 90.0) < _NEAR:
            key = ('v', round(x, 6))
            if key not in seen:
                guides.append(['v', float(x)])
        else:
            t = math.radians(a)
            key = ('o', round(a, 6), round(-x * math.sin(t) + y * math.cos(t), 6))
            if key not in seen:
                obliques.append([float(x), float(y), round(a, 9)])
        seen.add(key)
    return guides, obliques


def new_only(guides: list, obliques: list, have_guides: list, have_obliques: list) -> tuple[list, list]:
    """Ce qui n'existe pas déjà dans le document."""
    def same_guide(g, h):
        return g[0] == h[0] and abs(g[1] - h[1]) < 1e-6

    def normal(o):
        t = math.radians(o[2])
        return o[2] % 180.0, -o[0] * math.sin(t) + o[1] * math.cos(t)

    def same_line(a, b):
        p, q = normal(a), normal(b)
        return abs(p[0] - q[0]) < 1e-6 and abs(p[1] - q[1]) < 1e-6
    return ([g for g in guides if not any(same_guide(g, h) for h in have_guides)],
            [o for o in obliques if not any(same_line(o, h) for h in have_obliques)])


def spread(box, columns: int, rows: int, margin: float = 0.0) -> list:
    """Des repères répartis sur un rectangle : `columns` colonnes et `rows` rangées, dans la marge (bords compris)."""
    x0, y0, x1, y1 = box[0] + margin, box[1] + margin, box[2] - margin, box[3] - margin
    if x1 <= x0 or y1 <= y0:
        return []
    out = []
    if columns > 0:
        out += [['v', x0 + (x1 - x0) * i / columns] for i in range(columns + 1)]
    if rows > 0:
        out += [['h', y0 + (y1 - y0) * i / rows] for i in range(rows + 1)]
    return out
