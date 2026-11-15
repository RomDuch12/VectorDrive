"""Brut d'un dessin 2D (réponse 20 du 14/11 : « les 2 et aussi au calcul opés ») : la matière d'où une gravure ou un
fraisage sur plaque est usiné, quand elle n'est pas une plaque plate au niveau de Z 0.

- une **surépaisseur** au-dessus de la plaque (`top`, en mm : le dessus du brut est à Z = `top`, Z 0 restant le dessus
  de la plaque finie — un surfaçage la retire) ;
- des **marges** (`side`) autour de la plaque ou du contour ;
- l'emprise : la **plaque du dessin**, ou un **contour dessiné** (une forme fermée du dessin, `item`) ;
- l'épaisseur (`thickness`, 0 : celle de la plaque) : le dessous du brut, Z = −épaisseur.

La simulation part du haut du brut dans son emprise (`cam.simulate.stock_of`). Gardé avec le réglage FAO du dessin
(`CamSetup.stock2d`) ; le brut d'une pièce 3D (`core.stock3d`) reste à part et passe devant quand une pièce 3D est là.

Natures (`kind`) : '' aucun (matière plate à Z 0, comme avant) ; 'plaque' la plaque du dessin agrandie des marges ;
'contour' la forme fermée `item` du dessin agrandie des marges.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field, fields

import numpy as np

from .stock3d import StockBox, _mm

KINDS = {'': 'Aucun (plaque plate à Z 0)', 'plaque': 'Plaque du dessin et marges',
         'contour': 'Contour dessiné et marges'}


@dataclass
class Stock2D:
    kind: str = ''
    top: float = 0.0               # surépaisseur au-dessus de Z 0, le dessus de la plaque finie (mm)
    side: float = 0.0              # marge autour de la plaque ou du contour (mm)
    thickness: float = 0.0         # épaisseur sous Z 0 (mm) ; 0 : celle de la plaque
    item: str = ''                 # contour : l'objet du dessin (forme fermée)
    material: str = ''

    def active(self) -> bool:
        return self.kind in KINDS and self.kind != ''


@dataclass
class StockArea(StockBox):
    """Brut placé d'un dessin 2D : une `StockBox` dont l'emprise peut être un contour quelconque (`poly`, shapely ;
    None : le rectangle). `key` : son empreinte (le cache des simulations compare les bruts par leur texte)."""
    poly: object = field(default=None, repr=False, compare=False)
    key: str = ''

    def footprint(self):
        return self.poly if self.poly is not None else super().footprint()

    def inside(self, xs, ys, extra: float = 0.0):
        if self.poly is None:
            return super().inside(xs, ys, extra)
        import shapely
        xs, ys = np.broadcast_arrays(np.asarray(xs, dtype=np.float64), np.asarray(ys, dtype=np.float64))
        if extra > 0:
            return shapely.intersects_xy(self.poly.buffer(extra), xs, ys)
        # la même grille revient à chaque pas de la simulation pas à pas : son masque est gardé (le dernier)
        k = (xs.shape, xs.flat[0], xs.flat[-1], ys.flat[0], ys.flat[-1]) if xs.size else None
        last = getattr(self, '_mask', None)
        if k is not None and last is not None and last[0] == k:
            return last[1]
        shapely.prepare(self.poly)
        mask = shapely.intersects_xy(self.poly, xs, ys)  # dedans ou sur le bord
        self._mask = (k, mask)
        return mask


def from_dict(d) -> Stock2D:
    if not isinstance(d, dict):
        return Stock2D()
    out = Stock2D()
    for f in fields(Stock2D):
        if f.name not in d:
            continue
        try:
            setattr(out, f.name, str(d[f.name] or '') if f.type in ('str', str) else max(0.0, float(d[f.name] or 0.0)))
        except (TypeError, ValueError):
            pass
    if out.kind not in KINDS:
        out.kind = ''
    return out


def to_dict(s: Stock2D) -> dict:
    return {k: v for k, v in asdict(s).items() if v not in (0.0, '') or k == 'kind'}


def of_setup(setup) -> Stock2D:
    return from_dict(getattr(setup, 'stock2d', None))


def outline(doc, item_id: str):
    """Région shapely de l'objet `item_id` du dessin (ses contours fermés, règle pair-impair) ; None : objet absent
    ou sans contour fermé."""
    if not item_id or doc is None:
        return None
    from ..cam.strategies import item_geometry, region
    it = doc.find(item_id)
    path = item_geometry(it) if it is not None else None
    if path is None:
        return None
    g = region([path], 0.01)
    return None if g is None or g.is_empty else g


def resolve(stock: Stock2D, doc) -> StockArea | None:
    """Brut placé : None sans brut, sans plaque (nature plaque), sans contour fermé (nature contour)."""
    if stock is None or not stock.active() or doc is None:
        return None
    plate = getattr(doc, 'plate', None)
    top = max(0.0, float(stock.top))
    side = max(0.0, float(stock.side))
    t = float(stock.thickness) if stock.thickness > 0 else float(getattr(plate, 'thickness', 0.0) or 0.0)
    if stock.kind == 'plaque':
        if plate is None or plate.width <= 0 or plate.height <= 0:
            return None
        x0, y0, x1, y1 = plate.x - side, plate.y - side, plate.x + plate.width + side, plate.y + plate.height + side
        return StockArea(x0, y0, x1, y1, top, -t, key=f'plaque {x0:g} {y0:g} {x1:g} {y1:g}')
    g = outline(doc, stock.item)
    if g is None:
        return None
    if side > 0:
        g = g.buffer(side)
    x0, y0, x1, y1 = g.bounds
    key = 'contour ' + hashlib.blake2b(g.wkb, digest_size=12).hexdigest()
    return StockArea(x0, y0, x1, y1, top, -t, poly=g, key=key)


def box_for(doc, setup) -> StockArea | None:
    return resolve(of_setup(setup), doc)


def describe(stock: Stock2D, box: StockArea | None) -> str:
    """Le brut en une ligne (fenêtre, fiche de réglage)."""
    from ..i18n import tr
    if box is None or not stock.active():
        return tr('aucun brut : plaque plate à Z 0')
    text = tr('{0} × {1} mm').format(_mm(box.x1 - box.x0), _mm(box.y1 - box.y0))
    if box.poly is not None:
        text = tr('contour de {0}').format(text)
    if box.top > 0:
        text += tr(', {0} mm au-dessus de la plaque (à surfacer)').format(_mm(box.top))
    else:
        text += tr(', sans surépaisseur : la simulation reste celle d\'une plaque plate')
    if box.bottom < 0:
        text += tr(', épaisseur totale {0} mm').format(_mm(box.top - box.bottom))
    if stock.material:
        text += f', {stock.material}'
    return text
