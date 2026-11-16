"""Relief pour la vue 3D : carte de hauteurs (dessus de la pièce à Z = 0)
de ce que l'usinage creusera.

- d'après les parcours FAO s'il y a des opérations actives (simulation
  d'enlèvement de matière, outils réels) ;
- sinon d'après le dessin : chaque trait gravé à la largeur de son outil
  (table des outils) et à la profondeur de l'opération qui l'usine, ou
  `DEFAULT_DEPTH` ; objets remplis (et, au choix, contours fermés) évidés ;
  reliefs TypeArt (galbes, dômes, balayages…) usinés sommet affleurant, à
  la profondeur du relief (le Viewer TypeArt).

La carte couvre la plaque (sinon le dessin et une marge). Pas de widget :
rasterisation par QPainter sur QImage, utilisable dans un fil de calcul.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..core import progress
from .simulate import SimResult

DEFAULT_DEPTH = 0.3          # mm : profondeur d'un outil sans opération FAO
MIN_WIDTH = 0.1              # mm : trait le plus fin creusé
SOURCES = ('auto', 'dessin', 'fao')


@dataclass
class Relief:
    sim: SimResult
    plate: tuple | None = None           # (x, y, largeur, hauteur, épaisseur affichée)
    toolpaths: list = field(default_factory=list)
    source: str = 'dessin'
    warnings: list = field(default_factory=list)

    @property
    def area(self) -> tuple[float, float, float, float]:
        ny, nx = self.sim.H.shape
        return (self.sim.x0, self.sim.y0, self.sim.x0 + (nx - 1) * self.sim.res,
                self.sim.y0 + (ny - 1) * self.sim.res)


def tool_depths(doc) -> dict[int, float]:
    """Profondeur par outil du dessin d'après les opérations FAO actives
    (la plus profonde ; une opération sans outil désigné vaut pour tous)."""
    from . import model
    out: dict[int, float] = {}
    every = 0.0
    from .strategies import left_on_floor
    for op in model.setup_of(doc).operations:
        depth = op.depth - left_on_floor(op)             # ce qui est usiné : sans la surépaisseur Z laissée au fond
        if not op.enabled or depth <= 0:
            continue
        if not op.sources:
            every = max(every, depth)
        for s in op.sources:
            out[int(s)] = max(out.get(int(s), 0.0), depth)
    if every:
        for t in doc.tools:
            out[t.index] = max(out.get(t.index, 0.0), every)
    return out


def _area(doc, margin: float):
    if doc.plate is not None and doc.plate.visible:
        pl = doc.plate
        return pl.x, pl.y, pl.x + pl.width, pl.y + pl.height
    bb = doc.bbox()
    if not bb:
        return 0.0, 0.0, 100.0, 50.0
    return bb[0] - margin, bb[1] - margin, bb[2] + margin, bb[3] + margin


def _grid(area, max_cells: int, res: float | None):
    x0, y0, x1, y1 = area
    if res is None:
        res = max(math.sqrt(max(1e-6, (x1 - x0) * (y1 - y0)) / max_cells), 0.02)
    nx = int(math.ceil((x1 - x0) / res)) + 1
    ny = int(math.ceil((y1 - y0) / res)) + 1
    return res, nx, ny


def from_drawing(doc, *, depths: dict | None = None, default_depth: float = DEFAULT_DEPTH,
                 fill_closed: bool = False, max_cells: int = 1_000_000, margin: float = 2.0,
                 res: float | None = None) -> SimResult:
    """Carte de hauteurs du dessin gravé (voir le module)."""
    import numpy as np
    from .fixture import without_plates
    doc = without_plates(doc)                            # plaque de reprise posée : un repère, pas gravée
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QTransform
    from ..core.document import Shape, Text
    from ..io.raster import _app
    _app()
    area = _area(doc, margin)
    res, nx, ny = _grid(area, max_cells, res)
    x0, y0 = area[0], area[1]
    y_top = y0 + (ny - 1) * res
    H = np.zeros((ny, nx))
    depths = tool_depths(doc) if depths is None else depths
    by_tool: dict[int, list] = {}
    for leaf in doc.iter_leaves(visible_only=True):
        path = leaf.path if isinstance(leaf, Shape) else (leaf.outline if isinstance(leaf, Text) else None)
        if path and path.contours:
            by_tool.setdefault(leaf.tool, []).append((leaf, path))
    view = QTransform(1 / res, 0, 0, -1 / res, -x0 / res + 0.5, y_top / res + 0.5)
    tools = sorted(by_tool)
    for ti, tool in enumerate(tools):
        progress.step(ti, len(tools), 'Relief : outil {0} sur {1}')
        depth = float(depths.get(tool, default_depth) or default_depth)
        width = max(doc.tool_width(tool), MIN_WIDTH, res)
        img = QImage(nx, ny, QImage.Format.Format_Grayscale8)
        img.fill(0)
        p = QPainter(img)
        try:                                     # le peintre est fermé avant l'image, même si on annule
            p.setTransform(view)
            pen = QPen(QColor(255, 255, 255), width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            for leaf, path in by_tool[tool]:
                progress.check()
                q = QPainterPath()
                q.setFillRule(Qt.FillRule.OddEvenFill)
                any_closed = False
                for c in path.contours:
                    if not c.segments:
                        continue
                    poly = c.flatten(res / 2)
                    q.moveTo(*poly[0])
                    for pt in poly[1:]:
                        q.lineTo(*pt)
                    if c.closed:
                        q.closeSubpath()
                        any_closed = True
                fill = getattr(leaf, 'filled', False) or (fill_closed and any_closed)
                p.setPen(pen)
                p.setBrush(QColor(255, 255, 255) if fill else Qt.BrushStyle.NoBrush)
                p.drawPath(q)
        finally:
            p.end()
        a = np.frombuffer(img.constBits(), np.uint8).reshape(ny, img.bytesPerLine())[:, :nx][::-1]
        np.minimum(H, np.where(a > 127, -depth, 0.0), out=H)
    _typeart(doc, H, x0, y0, res)
    out = SimResult(H, x0, y0, res)
    out.removed = float(-H.sum() * res * res)
    out.deepest = float(H.min()) if H.size else 0.0
    return out


def _typeart(doc, H, x0: float, y0: float, res: float) -> int:
    """Reliefs TypeArt du dessin creusés dans la carte H (lignes de bas en
    haut) : sommet à Z = 0, fond à −profondeur du relief ; rend leur nombre."""
    import numpy as np
    from ..core.document import Image
    from .advanced import _gray
    ny, nx = H.shape
    n = 0
    for leaf in doc.iter_leaves(visible_only=True):
        if not isinstance(leaf, Image) or 'galbe' not in leaf.extra:
            continue
        depth = float(leaf.extra['galbe'].get('relief_depth') or 0.0)
        bx0, by0, bx1, by1 = leaf.bbox()
        i0, i1 = max(0, int(math.ceil((bx0 - x0) / res))), min(nx - 1, int(math.floor((bx1 - x0) / res)))
        j0, j1 = max(0, int(math.ceil((by0 - y0) / res))), min(ny - 1, int(math.floor((by1 - y0) / res)))
        if depth <= 0 or i1 < i0 or j1 < j0:
            continue
        # la carte de l'image, ré-échantillonnée aux nœuds de la grille couverts
        w, h = bx1 - bx0, by1 - by0
        gx = max(2, int(round(w / res)))
        gy = max(2, int(round(h / res)))
        gray = _gray(leaf, gx, gy)
        if gray is None:
            continue
        gray = gray[::-1]                                  # y croissant
        ii = np.clip(((x0 + np.arange(i0, i1 + 1) * res - bx0) / w * gx).astype(int), 0, gx - 1)
        jj = np.clip(((y0 + np.arange(j0, j1 + 1) * res - by0) / h * gy).astype(int), 0, gy - 1)
        Z = (gray[np.ix_(jj, ii)] - 1.0) * depth
        sub = H[j0:j1 + 1, i0:i1 + 1]
        np.minimum(sub, Z, out=sub)
        n += 1
    return n


def pad_to(sim: SimResult, area) -> SimResult:
    """La carte étendue (surface intacte) à toute la zone `area`, même pas."""
    import numpy as np
    res = sim.res
    x0, y0, x1, y1 = area
    nx = int(math.ceil((x1 - x0) / res)) + 1
    ny = int(math.ceil((y1 - y0) / res)) + 1
    from .simulate import initial_heights
    H = initial_heights(getattr(sim, 'stock', None), x0, y0, res, (ny, nx))     # brut : son haut dans son emprise
    i0 = int(round((sim.x0 - x0) / res))
    j0 = int(round((sim.y0 - y0) / res))
    sh, sw = sim.H.shape
    a0, b0 = max(0, j0), max(0, i0)
    a1, b1 = min(ny, j0 + sh), min(nx, i0 + sw)
    if a1 > a0 and b1 > b0:
        H[a0:a1, b0:b1] = sim.H[a0 - j0:a1 - j0, b0 - i0:b1 - i0]
    out = SimResult(H, x0, y0, res, sim.removed, float(H.min()) if H.size else 0.0, list(sim.warnings),
                    stock=getattr(sim, 'stock', None))
    return out


def from_cam(doc, *, max_cells: int = 1_000_000, margin: float = 2.0):
    """(carte simulée sur toute la plaque, parcours) ; None sans opération active."""
    from . import model, simulate, strategies
    setup = model.setup_of(doc)
    if not any(op.enabled for op in setup.operations):
        return None
    with progress.span(0.0, 0.5):
        tps = strategies.compute_all(doc, setup)
    if not any(tp.moves for tp in tps):
        return None
    area = _area(doc, margin)
    res = _grid(area, max_cells, None)[0]
    with progress.span(0.5, 1.0):
        sim = simulate.simulate(tps, setup, res=res, margin=margin, stock=simulate.stock_of(doc, setup, tps))
    return pad_to(sim, (min(area[0], sim.x0), min(area[1], sim.y0),
                        max(area[2], sim.x0 + (sim.H.shape[1] - 1) * res),
                        max(area[3], sim.y0 + (sim.H.shape[0] - 1) * res))), tps


def from_paths(doc, toolpaths, *, cut: bool, max_cells: int = 1_000_000, margin: float = 2.0) -> Relief:
    """Parcours déjà calculés en 3D : `cut` — simulés (matière enlevée) ;
    sinon trajectoires seules, au-dessus de la matière intacte."""
    from . import model, simulate
    setup = model.setup_of(doc)
    tps = [tp for tp in toolpaths if tp.moves]
    area = _area(doc, margin)
    stock = next((s for tp in tps if (s := getattr(tp, 'stock', None))), None)
    if stock:                                            # programme lu : son brut, pas la plaque du dessin
        area = (stock[0], stock[1], stock[3], stock[4])
    for tp in tps:                                       # la zone couvre aussi les trajectoires
        bb = tp.bbox()                                   # (x0, y0, z0, x1, y1, z1)
        if bb:
            area = (min(area[0], bb[0] - margin), min(area[1], bb[1] - margin),
                    max(area[2], bb[3] + margin), max(area[3], bb[4] + margin))
    if cut and tps:
        res = _grid(area, max_cells, None)[0]
        sim = simulate.simulate(tps, setup, res=res, margin=margin, stock=simulate.stock_of(doc, setup, tps))
        sim = pad_to(sim, (min(area[0], sim.x0), min(area[1], sim.y0),
                           max(area[2], sim.x0 + (sim.H.shape[1] - 1) * res),
                           max(area[3], sim.y0 + (sim.H.shape[0] - 1) * res)))
        return Relief(sim, _stock_plate(stock, sim) or _plate(doc, sim), tps, 'simulation', list(sim.warnings))
    import numpy as np
    res, nx, ny = _grid(area, 40_000, None)
    flat = SimResult(np.zeros((ny, nx)), area[0], area[1], res)
    deepest = min((m.z for tp in tps for m in tp.moves), default=0.0)
    flat.deepest = min(0.0, deepest)
    warnings = [] if tps else ['aucun parcours calculé']
    return Relief(flat, _stock_plate(stock, flat) or _plate(doc, flat), tps, 'parcours', warnings)


def build(doc, source: str = 'auto', **kw) -> Relief:
    """Relief du document : `source` = auto (FAO s'il y a des opérations
    actives, sinon dessin), dessin ou fao ; `parcours` (trajectoires seules)
    et `simulation` (enlèvement de matière) des parcours `toolpaths`."""
    if source in ('parcours', 'simulation'):
        return from_paths(doc, kw.get('toolpaths') or [], cut=source == 'simulation',
                          max_cells=kw.get('max_cells', 1_000_000))
    kw.pop('toolpaths', None)
    warnings = []
    if source in ('auto', 'fao'):
        got = from_cam(doc, max_cells=kw.get('max_cells', 1_000_000))
        if got is not None:
            sim, tps = got
            return Relief(sim, _plate(doc, sim), tps, 'fao', list(sim.warnings))
        if source == 'fao':
            warnings.append('aucune opération FAO active : relief tiré du dessin')
    sim = from_drawing(doc, **kw)
    return Relief(sim, _plate(doc, sim), [], 'dessin', warnings)


def _stock_plate(stock, sim: SimResult):
    """Plaque du brut déclaré par un programme (x0, y0, z0, x1, y1, z1), le haut à Z = z1."""
    if not stock:
        return None
    x0, y0, z0, x1, y1, z1 = stock
    deep = -sim.deepest if sim.deepest < 0 else 0.0
    return (x0, y0, x1 - x0, y1 - y0, max(z1 - z0, deep + 0.2))


def _plate(doc, sim: SimResult):
    deep = -sim.deepest if sim.deepest < 0 else 0.0
    if doc.plate is None or not doc.plate.visible:
        return None
    pl = doc.plate
    thick = pl.thickness if pl.thickness > 0 else max(2.0, 3 * deep)
    return (pl.x, pl.y, pl.width, pl.height, max(thick, deep + 0.2))
