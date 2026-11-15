"""Rogner : garder ce qui est dans un rectangle (plaque, cadre).

* **Traits** (contours non remplis — le cas de la gravure au fil) : chaque
  segment est coupé exactement là où il traverse un bord (droites,
  Bézier et coniques : racines des équations x(t) = x₀… y(t) = y₁) ; les
  morceaux intérieurs sont gardés et rechaînés. Aucun bord n'est ajouté.
* **Surfaces** (formes remplies) : intersection booléenne exacte avec le
  rectangle (`pathops`), le contour suit alors le bord du rectangle.
"""
from __future__ import annotations

import math

import numpy as np

from .geom import Conic, Contour, Cubic, Line, Path
from .nodes import split_segment


def _roots_in_unit(coefs) -> list[float]:
    """Racines réelles dans ]0, 1[ d'un polynôme (coefficients décroissants)."""
    coefs = np.trim_zeros(np.asarray(coefs, dtype=float), 'f')
    if len(coefs) < 2:
        return []
    out = []
    for r in np.roots(coefs):
        if abs(r.imag) < 1e-9 and 1e-9 < r.real < 1 - 1e-9:
            out.append(float(r.real))
    return out


def crossings(s, box) -> list[float]:
    """Paramètres où le segment traverse une droite du bord du rectangle."""
    x0, y0, x1, y1 = box
    ts = []
    for axis, value in ((0, x0), (0, x1), (1, y0), (1, y1)):
        if isinstance(s, Line):
            a, b = s.p0[axis], s.p1[axis]
            if abs(b - a) > 1e-15:
                t = (value - a) / (b - a)
                if 1e-9 < t < 1 - 1e-9:
                    ts.append(t)
        elif isinstance(s, Cubic):
            p0, p1, p2, p3 = (p[axis] for p in (s.p0, s.p1, s.p2, s.p3))
            # Bernstein → puissances : a t³ + b t² + c t + d
            ts += _roots_in_unit([-p0 + 3 * p1 - 3 * p2 + p3, 3 * p0 - 6 * p1 + 3 * p2,
                                  -3 * p0 + 3 * p1, p0 - value])
        elif isinstance(s, Conic):
            w = s.w
            p0, p1, p2 = (p[axis] for p in (s.p0, s.p1, s.p2))
            # N(t) − value·D(t) = 0, N et D du second degré
            n = (p0 - 2 * w * p1 + p2, 2 * w * p1 - 2 * p0, p0)
            d = (2 - 2 * w, 2 * w - 2, 1.0)
            ts += _roots_in_unit([n[0] - value * d[0], n[1] - value * d[1], n[2] - value * d[2]])
    return sorted(set(round(t, 12) for t in ts))


def _inside(p, box, eps=1e-9) -> bool:
    return box[0] - eps <= p[0] <= box[2] + eps and box[1] - eps <= p[1] <= box[3] + eps


def clip_strokes(path: Path, box) -> Path:
    """Morceaux des contours situés dans `box` (contours ouverts ou fermés)."""
    out: list[Contour] = []
    for c in path.contours:
        segs = list(c.segments)
        if c.closed and segs and math.dist(c.end, c.start) > 1e-9:
            segs.append(Line(c.end, c.start))
        if not segs:
            continue
        b = c.bbox()
        if _inside((b[0], b[1]), box) and _inside((b[2], b[3]), box):
            out.append(c)                            # entièrement dedans
            continue
        pieces = []                                  # (segment, dedans ?)
        for s in segs:
            rest, prev = s, 0.0
            for t in crossings(s, box):
                a, rest = split_segment(rest, (t - prev) / (1 - prev))
                pieces.append(a)
                prev = t
            pieces.append(rest)
        runs, cur = [], []
        for p in pieces:
            if _inside(p.point(0.5), box):
                cur.append(p)
            elif cur:
                runs.append(cur)
                cur = []
        if cur:
            runs.append(cur)
        if c.closed and len(runs) > 1 and _inside(pieces[0].point(0.5), box) and _inside(pieces[-1].point(0.5), box):
            runs[0] = runs.pop() + runs[0]           # le départ du contour fermé était dedans
        out += [Contour(r, False) for r in runs if r]
    return Path(out)


def clip_regions(path: Path, box) -> Path:
    from . import geom, pathops
    rect = Path([geom.rect(box[0], box[1], box[2] - box[0], box[3] - box[1])])
    return pathops.boolean(path, rect, 'intersect')
