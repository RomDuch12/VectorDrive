"""Brut d'une pièce 3D (STEP, STL, 3D XML) : le bloc, la plaque ou la barre
ronde d'où elle est usinée — donné par l'utilisateur pour que l'usinage
parte de la vraie matière :

- l'ébauche 3D commence au haut du brut (surépaisseur au-dessus de la
  pièce : paliers au-dessus de Z 0) et vide tout le brut autour de la pièce,
  pas seulement une largeur d'outil ; rien n'est usiné hors du brut ;
- contrôles : pièce qui dépasse du brut, brut moins épais que la pièce ;
- usinage automatique : profondeur et longueur d'outil comptées depuis le
  haut du brut.

Repère : celui de l'usinage 3D — haut de la pièce posée à Z = 0, X et Y du
dessin. Gardé avec le réglage FAO du dessin (`CamSetup.stock3d`).

Natures (`kind`) :

- ''       : aucun brut donné (comme avant : la matière est supposée au
  niveau du haut de la pièce, autour d'elle) ;
- 'marges' : la boîte de la pièce agrandie de `side` mm de chaque côté,
  `top` mm au-dessus et `bottom` mm dessous ;
- 'bloc'   : bloc `sx` × `sy` × `sz` centré sur la pièce (décalé de dx, dy),
  son haut `top` mm au-dessus de la pièce ;
- 'rond'   : barre ronde Ø `diameter`, hauteur `sz`, axe vertical, centrée
  sur la pièce (décalée de dx, dy), son haut `top` mm au-dessus ;
- 'plaque' : la plaque du dessin (position, largeur, hauteur), épaisseur
  `sz` ou, à 0, celle de la plaque ; son haut `top` mm au-dessus.

Hauteur `sz` à 0 (bloc, rond) : la pièce et la surépaisseur du dessus.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, fields

import numpy as np

KINDS = {'': 'Aucun (matière au haut de la pièce)', 'marges': 'Boîte de la pièce + marges',
         'bloc': 'Bloc (longueur × largeur × hauteur)', 'rond': 'Barre ronde (Ø × hauteur)',
         'plaque': 'Plaque du dessin'}
#: écart toléré entre la pièce et le bord du brut (mm)
TOL = 0.01


@dataclass
class Stock3D:
    kind: str = ''
    sx: float = 0.0
    sy: float = 0.0
    sz: float = 0.0
    diameter: float = 0.0
    top: float = 0.0               # surépaisseur au-dessus de la pièce (mm)
    side: float = 0.0              # marges : de chaque côté (mm)
    bottom: float = 0.0            # marges : dessous (mm)
    dx: float = 0.0
    dy: float = 0.0
    material: str = ''

    def active(self) -> bool:
        return self.kind in KINDS and self.kind != ''


@dataclass
class StockBox:
    """Brut placé : emprise (x0, y0, x1, y1), haut et bas (Z, haut de la
    pièce à 0) ; `round` : cylindre inscrit dans l'emprise."""
    x0: float
    y0: float
    x1: float
    y1: float
    top: float
    bottom: float
    round: bool = False

    @property
    def center(self) -> tuple[float, float]:
        return (self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2

    @property
    def height(self) -> float:
        return self.top - self.bottom

    def footprint(self):
        """Emprise vue de dessus (shapely)."""
        from shapely.geometry import Point, box
        if self.round:
            cx, cy = self.center
            return Point(cx, cy).buffer((self.x1 - self.x0) / 2, quad_segs=32)
        return box(self.x0, self.y0, self.x1, self.y1)

    def inside(self, xs, ys, extra: float = 0.0):
        """Points (tableaux) dans l'emprise agrandie de `extra` mm."""
        xs, ys = np.asarray(xs, dtype=np.float64), np.asarray(ys, dtype=np.float64)
        if self.round:
            cx, cy = self.center
            r = (self.x1 - self.x0) / 2 + extra
            return (xs - cx) ** 2 + (ys - cy) ** 2 <= r * r
        if extra <= 0:
            return (xs >= self.x0 - extra) & (xs <= self.x1 + extra) & (ys >= self.y0 - extra) & (ys <= self.y1 + extra)
        dx = np.maximum(np.maximum(self.x0 - xs, xs - self.x1), 0.0)       # coins arrondis : comme l'outil
        dy = np.maximum(np.maximum(self.y0 - ys, ys - self.y1), 0.0)
        return dx * dx + dy * dy <= extra * extra


def from_dict(d) -> Stock3D:
    if not isinstance(d, dict):
        return Stock3D()
    out = Stock3D()
    for f in fields(Stock3D):
        if f.name not in d:
            continue
        try:
            setattr(out, f.name, str(d[f.name]) if f.type in ('str', str) else float(d[f.name] or 0.0))
        except (TypeError, ValueError):
            pass
    if out.kind not in KINDS:
        out.kind = ''
    return out


def to_dict(s: Stock3D) -> dict:
    return {k: v for k, v in asdict(s).items() if v not in (0.0, '') or k == 'kind'}


def resolve(stock: Stock3D, part_bounds, plate=None) -> StockBox | None:
    """Brut placé autour de la pièce : `part_bounds` (x0, y0, z0, x1, y1, z1)
    de la pièce posée (son haut sera Z 0) ; `plate` : la plaque du dessin.
    None : pas de brut (ou nature inconnue, plaque absente)."""
    if stock is None or not stock.active():
        return None
    x0, y0, z0, x1, y1, z1 = (float(v) for v in part_bounds)
    h = max(0.0, z1 - z0)
    top = max(0.0, float(stock.top))
    cx, cy = (x0 + x1) / 2 + stock.dx, (y0 + y1) / 2 + stock.dy
    height = float(stock.sz) if stock.sz > 0 else h + top
    if stock.kind == 'marges':
        s = max(0.0, float(stock.side))
        return StockBox(x0 - s, y0 - s, x1 + s, y1 + s, top, -h - max(0.0, float(stock.bottom)))
    if stock.kind == 'bloc':
        if stock.sx <= 0 or stock.sy <= 0:
            return None
        return StockBox(cx - stock.sx / 2, cy - stock.sy / 2, cx + stock.sx / 2, cy + stock.sy / 2, top, top - height)
    if stock.kind == 'rond':
        if stock.diameter <= 0:
            return None
        r = stock.diameter / 2
        return StockBox(cx - r, cy - r, cx + r, cy + r, top, top - height, True)
    if stock.kind == 'plaque':
        if plate is None or plate.width <= 0 or plate.height <= 0:
            return None
        t = float(stock.sz) if stock.sz > 0 else float(getattr(plate, 'thickness', 0.0) or 0.0) or h + top
        return StockBox(plate.x, plate.y, plate.x + plate.width, plate.y + plate.height, top, top - t)
    return None


def check(box: StockBox | None, part_bounds) -> list[str]:
    """Contrôles du brut : la pièce doit tenir dedans."""
    if box is None:
        return []
    from ..i18n import tr
    x0, y0, z0, x1, y1, z1 = (float(v) for v in part_bounds)
    out = []
    if box.round:
        cx, cy = box.center
        far = max(math.hypot(x - cx, y - cy) for x in (x0, x1) for y in (y0, y1))
        over = far - (box.x1 - box.x0) / 2
    else:
        over = max(box.x0 - x0, x1 - box.x1, box.y0 - y0, y1 - box.y1)
    if over > TOL:
        out.append(tr('brut : la pièce dépasse du brut de {0} mm (vue de dessus)').format(_mm(over)))
    short = box.bottom - (z0 - z1)
    if short > TOL:
        out.append(tr('brut : moins épais que la pièce et sa surépaisseur — il manque {0} mm').format(_mm(short)))
    return out


def describe(stock: Stock3D, box: StockBox | None = None) -> str:
    """Le brut en une ligne (fiche de réglage, boîte de dialogue)."""
    from ..i18n import tr
    if box is None or not stock.active():
        return tr('aucun brut donné')
    if box.round:
        text = tr('barre ronde Ø {0} × {1} mm').format(_mm(box.x1 - box.x0), _mm(box.height))
    else:
        text = tr('{0} × {1} × {2} mm').format(_mm(box.x1 - box.x0), _mm(box.y1 - box.y0), _mm(box.height))
    if box.top > TOL:
        text += tr(', {0} mm au-dessus de la pièce').format(_mm(box.top))
    if stock.material:
        text += f', {stock.material}'
    return text


def _mm(v: float) -> str:
    from ..i18n import decimal_sep
    return f'{v:.2f}'.rstrip('0').rstrip('.').replace('.', decimal_sep())


def of_setup(setup) -> Stock3D:
    return from_dict(getattr(setup, 'stock3d', None))


def box_for(doc, setup, model) -> StockBox | None:
    """Brut du réglage FAO placé autour de `model` (la pièce posée)."""
    st = of_setup(setup)
    if not st.active() or model is None:
        return None
    t = np.asarray(model.triangles, dtype=np.float64)
    if not len(t):
        return None
    lo, hi = t.reshape(-1, 3).min(axis=0), t.reshape(-1, 3).max(axis=0)
    return resolve(st, (lo[0], lo[1], lo[2], hi[0], hi[1], hi[2]), getattr(doc, 'plate', None))
