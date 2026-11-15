"""Trous de perçage : l'objet « Trou » de TypeEdit (classe CTrou).
Dans VectorDrive, un trou est un cercle au diamètre du foret
qui garde sa profondeur dans `extra['trou']` ; il est réécrit en CTrou
dans les VND tant qu'il reste un cercle (déplacé, copié, redimensionné…).
Unités : mm."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from .document import Item, Shape
from .geom import Path, circle


@dataclass
class HoleSpec:
    diameter: float = 4.0
    depth: float = 10.0

    @classmethod
    def from_dict(cls, d: dict) -> 'HoleSpec':
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        return asdict(self)


def is_hole(item: Item) -> bool:
    return isinstance(item, Shape) and 'trou' in item.extra


def circle_of(item: Item) -> tuple[float, float, float] | None:
    """(x, y, rayon) si l'item est un seul cercle fermé, sinon None."""
    if not isinstance(item, Shape) or len(item.path.contours) != 1 or not item.path.contours[0].closed:
        return None
    bb = item.bbox()
    if not bb:
        return None
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    if w <= 0 or abs(w - h) > 1e-6 * max(w, 1.0):
        return None
    r = w / 2
    if abs(item.path.contours[0].length() - 2 * math.pi * r) > 1e-4 * max(r, 1.0):
        return None                     # carré, polygone… : pas un cercle
    return (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2, r


def rect_of(item: Item) -> tuple[float, float, float, float, float] | None:
    """(x, y, largeur, hauteur, rayon des coins) du centre si l'item est un
    seul rectangle fermé aux côtés horizontaux et verticaux (coins ronds
    compris), sinon None."""
    if not isinstance(item, Shape) or len(item.path.contours) != 1 or not item.path.contours[0].closed:
        return None
    c = item.path.contours[0]
    bb = c.bbox()
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    if w <= 1e-9 or h <= 1e-9:
        return None
    from .geom import Line
    for s in c.segments:
        if isinstance(s, Line) and abs(s.p0[0] - s.p1[0]) > 1e-7 and abs(s.p0[1] - s.p1[1]) > 1e-7:
            return None                                  # côté en biais
    # périmètre 2(w+h) − (8 − 2π) r, aire w·h − (4 − π) r²
    r = max(0.0, (2 * (w + h) - c.length()) / (8 - 2 * math.pi))
    if r > min(w, h) / 2 + 1e-6:
        return None
    area = abs(c.signed_area(min(w, h) * 1e-4))
    if abs(area - (w * h - (4 - math.pi) * r * r)) > 2e-3 * w * h:
        return None
    return (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2, w, h, (round(r, 6) if r > 1e-6 else 0.0)


def make(center: tuple[float, float], spec: HoleSpec, tool: int = 0) -> Shape:
    s = Shape(path=Path([circle(center, spec.diameter / 2)]), tool=tool, name='Trou')
    s.extra['trou'] = {'profondeur': float(spec.depth)}
    return s


def spec_of(item: Item) -> HoleSpec:
    c = circle_of(item)
    depth = float((item.extra.get('trou') or {}).get('profondeur', HoleSpec.depth))
    return HoleSpec(diameter=2 * c[2] if c else HoleSpec.diameter, depth=depth)


def updated(item: Shape, spec: HoleSpec) -> Shape:
    """Trou recalculé au même centre (diamètre et profondeur de `spec`)."""
    c = circle_of(item)
    center = (c[0], c[1]) if c else ((item.bbox()[0] + item.bbox()[2]) / 2, (item.bbox()[1] + item.bbox()[3]) / 2)
    h = make(center, spec, item.tool)
    h.name = item.name or 'Trou'
    info = dict(item.extra.get('trou') or {})
    info['profondeur'] = float(spec.depth)
    h.extra['trou'] = info
    return h


def convert(items: list[Item], spec: HoleSpec, keep_diameter: bool = True) -> dict[int, Shape]:
    """Cercles de `items` changés en trous : {id(ancien): trou}. Les
    autres objets ne sont pas touchés."""
    out = {}
    for it in items:
        c = circle_of(it)
        if c is None:
            continue
        s = HoleSpec(diameter=2 * c[2] if keep_diameter else spec.diameter, depth=spec.depth)
        out[id(it)] = updated(it, s)
    return out


def table(items) -> list[tuple[float, float, int]]:
    """Récapitulatif (diamètre, profondeur, nombre), du plus petit diamètre au plus grand."""
    from collections import Counter
    n = Counter()
    for it in items:
        if is_hole(it):
            s = spec_of(it)
            n[(round(s.diameter, 4), round(s.depth, 4))] += 1
    return [(d, p, k) for (d, p), k in sorted(n.items())]
