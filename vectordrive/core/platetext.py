"""Mise en page du texte sur la plaque (TypeEdit ▸ Surface active ▸ Mise
en page du texte) : n lignes de texte réparties dans la hauteur de la
plaque, marges automatiques.

* **volume du texte** : part de la hauteur (marges de la plaque ôtées)
  occupée par les capitales des lignes ;
* le reste se partage entre les interlignes et les marges du haut et du
  bas, chacune valant `margin_factor` interlignes ;
* **décalage** : une part de la marge retirée en haut et ajoutée en bas (le
  texte remonte) ;
* **marges horizontales** : part de la largeur laissée à gauche et à droite ;
  chaque ligne a pour longueur maximale la largeur qui reste.

Hauteurs de lignes égales, ou proportionnelles à des poids donnés.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlateTextSpec:
    lines: int = 3
    volume: float = 55.0            # % de la hauteur pour les capitales
    margin_factor: float = 1.0      # marge du haut ou du bas = n interlignes
    offset: float = 0.0             # % de la marge : retiré en haut, ajouté en bas
    h_margin: float = 6.0           # % de la largeur, de chaque côté
    weights: str = ''               # poids des lignes (« 2 1 1 » : la première deux fois plus haute)
    font: str = 'Arial'


def layout(plate, spec: PlateTextSpec) -> list[tuple[float, float, float, float]]:
    """[(x du centre, y de la ligne de base, hauteur des capitales, longueur
    maximale)] du haut vers le bas."""
    n = max(1, int(spec.lines))
    x0, y0, x1, y1 = plate.usable() if hasattr(plate, 'usable') else (
        plate.x, plate.y, plate.x + plate.width, plate.y + plate.height)
    H, Wd = y1 - y0, x1 - x0
    try:
        w = [float(v) for v in spec.weights.replace(',', '.').split()][:n]
    except ValueError:
        w = []
    w = (w + [1.0] * n)[:n] if w else [1.0] * n
    total_caps = max(0.0, min(100.0, spec.volume)) / 100.0 * H
    caps = [total_caps * k / sum(w) for k in w]
    rest = max(0.0, H - total_caps)
    gap = rest / (2 * max(0.0, spec.margin_factor) + n - 1) if (2 * spec.margin_factor + n - 1) > 0 else 0.0
    margin = spec.margin_factor * gap
    shift = spec.offset / 100.0 * margin / 2
    top = margin - shift
    xc = (x0 + x1) / 2
    length = Wd * (1 - 2 * max(0.0, min(49.0, spec.h_margin)) / 100.0)
    out, y = [], y1 - top
    for h in caps:
        out.append((xc, y - h, h, length))
        y -= h + gap
    return out
