"""Traits de coupe et hirondelles de repérage (comme les Crop Marks des
logiciels de dessin, les hirondelles de TypeEdit pour la découpe) autour
d'un cadre : aux quatre coins, deux traits dans le prolongement des bords,
écartés du cadre ; au milieu de chaque côté, une cible (cercle et croix)
pour recaler une découpe sur une impression.

Dessin original (aucun symbole repris).
"""
from __future__ import annotations

from dataclasses import dataclass

from .geom import Path, circle, polyline

KINDS = (('coins', 'Traits de coupe aux coins'), ('cibles', 'Cibles au milieu des côtés'),
         ('les_deux', 'Traits de coupe et cibles'))


@dataclass
class CropMarksSpec:
    kind: str = 'coins'
    length: float = 5.0             # longueur des traits (mm)
    gap: float = 2.0                # écart entre le cadre et les traits (mm)
    target: float = 4.0             # diamètre des cibles (mm)
    margin: float = 0.0             # cadre agrandi de… autour des objets (mm, fond perdu)


def marks(bbox, spec: CropMarksSpec) -> Path:
    """Traits ouverts (et cercles des cibles) autour de `bbox` (x0, y0, x1, y1)."""
    m = max(0.0, spec.margin)
    x0, y0, x1, y1 = bbox[0] - m, bbox[1] - m, bbox[2] + m, bbox[3] + m
    g, L = max(0.0, spec.gap), max(0.0, spec.length)
    out = []
    if spec.kind in ('coins', 'les_deux') and L > 0:
        for cx, sx in ((x0, -1), (x1, 1)):
            for cy, sy in ((y0, -1), (y1, 1)):
                out.append(polyline([(cx + sx * g, cy), (cx + sx * (g + L), cy)]))      # dans le prolongement du bord
                out.append(polyline([(cx, cy + sy * g), (cx, cy + sy * (g + L))]))
    if spec.kind in ('cibles', 'les_deux') and spec.target > 0:
        r = spec.target / 2
        d = g + max(L, spec.target) / 2
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        for px, py in ((mx, y0 - d), (mx, y1 + d), (x0 - d, my), (x1 + d, my)):
            out.append(circle((px, py), r))
            out.append(polyline([(px - r * 1.4, py), (px + r * 1.4, py)]))
            out.append(polyline([(px, py - r * 1.4), (px, py + r * 1.4)]))
    return Path(out)
