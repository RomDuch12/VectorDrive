"""Rapport d'imbrication : les chiffres de chaque plan rempli, d'après le manuel de TypeEdit."""
from __future__ import annotations

from dataclasses import dataclass

from . import pathops
from .hatch import closed_path
from .remnant import _footprint

#: réglages d'une imbrication gardés dans le document (`doc.extra['imbrication']`)
KEEP = ('margin', 'gap', 'allow_rotate', 'shape', 'angle_step', 'angles', 'in_holes', 'allow_mirror', 'precision',
        'corner', 'vertical')


def remember(doc, spec, res) -> None:
    """Garde les réglages de la dernière imbrication : le rapport peut venir plus tard, ou après réouverture."""
    kept = {k: getattr(spec, k) for k in KEEP}
    kept['plates'] = int(res.plates)
    kept['placed'] = len(res.placed)
    kept['unplaced'] = len(res.unplaced)
    kept['usage'] = float(res.usage)
    if res.best:
        kept.update(tries=int(res.best['tries']), best_vertical=bool(res.best['vertical']),
                    filled=float(res.best['filled']), first_filled=float(res.best['first_filled']))
    doc.extra['imbrication'] = kept


@dataclass
class PlaneRow:
    name: str
    width: float                                         # la plaque
    height: float
    thickness: float
    surface: float
    pieces: int
    pieces_area: float                                   # la matière des pièces, trous déduits
    cut_area: float                                      # ce qui tombe : pièces pleines, grossies de la moitié de l'écart
    cut_width: float
    cut_height: float
    filled: float                                        # part de la plaque qui tombe


def plane_rows(doc, gap: float = 0.0) -> list[PlaneRow]:
    """Un rang par plan visible qui contient quelque chose."""
    from shapely.ops import unary_union
    plate = doc.plate
    width, height = (plate.width, plate.height) if plate is not None else (0.0, 0.0)
    surface = width * height
    thickness = float(plate.thickness) if plate is not None else 0.0
    rows = []
    half = max(float(gap), 0.0) / 2.0
    for layer in doc.layers:
        if not layer.visible or not layer.items:
            continue
        matter = 0.0
        parts = []
        for it in layer.items:
            closed = closed_path([it])
            if closed.contours:
                matter += abs(pathops.area(pathops.normalize(closed)))
            print_ = _footprint(it, half)
            if print_ is not None:
                parts.append(print_)
        whole = unary_union(parts) if parts else None
        area, cut_w, cut_h = 0.0, 0.0, 0.0
        if whole is not None and not whole.is_empty:
            area = float(whole.area)
            b = whole.bounds
            cut_w, cut_h = b[2] - b[0], b[3] - b[1]
        rows.append(PlaneRow(name=layer.name, width=width, height=height, thickness=thickness, surface=surface,
                             pieces=len(layer.items), pieces_area=matter, cut_area=area, cut_width=cut_w,
                             cut_height=cut_h, filled=area / surface if surface > 0 else 0.0))
    return rows
