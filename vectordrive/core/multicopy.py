"""Multicopie : des exemplaires en grille sur la plaque, sur autant de plans qu'il en faut, d'après le manuel de TypeEdit.

Le point de départ et le rangement « optimisé » (aller-retour) fixent l'ordre des exemplaires, donc celui de l'usinage et
de leurs numéros. Une cellule est l'exemplaire avec la moitié de l'écart autour : deux cellules voisines partagent leur
bord, et c'est là que passent les lignes de découpe.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .duplicate import _copy
from .geom import Affine, Path, bbox_union, polyline

STARTS = ('haut_gauche', 'haut_droit', 'bas_gauche', 'bas_droit')
PLACES = ('haut_gauche', 'haut_centre', 'haut_droit', 'milieu_gauche', 'centre', 'milieu_droit',
          'bas_gauche', 'bas_centre', 'bas_droit')
CUTS = ('aucune', 'partielle', 'totale')
MAX_COPIES = 20000


@dataclass
class MultiSpec:
    margin: float = 3.0                                  # au bord de la plaque
    gap_x: float = 2.0
    gap_y: float = 2.0
    total: int = 0                                       # exemplaires, original compris ; 0 : voir `planes`
    planes: int = 0                                      # plans remplis ; 0 avec total 0 : une plaque remplie
    start: str = 'haut_gauche'                           # le premier exemplaire
    place: str = 'centre'                                # où va le bloc dans la zone utile
    from_selection: bool = False                         # le premier exemplaire reste à la place de la sélection
    optimised: bool = False                              # aller-retour : moins de déplacements de l'outil
    turn_back: bool = False                              # optimisé : les rangées du retour tournées d'un demi-tour
    quarter_turn: bool = False                           # un quart de tour s'il en tient plus
    ignore_first: bool = False                           # le premier objet donne sa taille à la cellule, sans être copié
    keep_original: bool = False                          # l'original reste, les exemplaires vont sur de nouveaux plans
    limit_to_rows: bool = True                           # variables : autant d'exemplaires que de lignes du tableau
    cuts: str = 'aucune'
    cut_tool: int = 0
    tick: float = 3.0                                    # découpe partielle : longueur des traits (mm)


@dataclass
class Cell:
    plate: int
    col: int                                             # de gauche à droite
    row: int                                             # de bas en haut
    x: float
    y: float
    back: bool = False                                   # sur une rangée du retour


@dataclass
class Layout:
    cols: int = 0
    rows: int = 0
    w: float = 0.0
    h: float = 0.0
    turned: bool = False
    ox: float = 0.0
    oy: float = 0.0
    cells: list[Cell] = field(default_factory=list)

    @property
    def per_plate(self) -> int:
        return self.cols * self.rows

    @property
    def plates(self) -> int:
        return max((c.plate for c in self.cells), default=-1) + 1


@dataclass
class MultiResult:
    layout: Layout
    planes: list[list] = field(default_factory=list)     # les exemplaires de chaque plan
    cuts: list = field(default_factory=list)             # le tracé des lignes de découpe de chaque plan, ou None
    count: int = 0


def wanted(spec: MultiSpec, rows: int = 0) -> int | None:
    """Combien d'exemplaires, si les lignes d'un tableau de variables en décident ; None : d'après `spec`."""
    if rows <= 0 or not spec.limit_to_rows:
        return None
    return min(spec.total, rows) if spec.total > 0 else rows


def _fit(room: float, size: float, gap: float) -> int:
    if size <= 0 or room < size - 1e-9:
        return 0
    return int((room + gap + 1e-9) // (size + gap))


def layout(bb, box, spec: MultiSpec, count: int | None = None) -> Layout:
    """La grille d'un bloc de boîte `bb` sur la plaque `box` ; `count` : exemplaires demandés, sinon d'après `spec`."""
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    gx, gy = max(spec.gap_x, 0.0), max(spec.gap_y, 0.0)
    x0, y0 = box[0] + spec.margin, box[1] + spec.margin
    x1, y1 = box[2] - spec.margin, box[3] - spec.margin
    left, top = not spec.start.endswith('droit'), spec.start.startswith('haut')
    turned = False
    if spec.from_selection:
        room_x = x1 - bb[0] if left else bb[2] - x0
        room_y = bb[3] - y0 if top else y1 - bb[1]
        cols, rows = max(1, _fit(room_x, w, gx)), max(1, _fit(room_y, h, gy))
        if bb[0] < box[0] or bb[2] > box[2] or bb[1] < box[1] or bb[3] > box[3]:     # hors de la plaque : elle seule
            cols, rows = 1, 1
    else:
        cols, rows = _fit(x1 - x0, w, gx), _fit(y1 - y0, h, gy)
        if spec.quarter_turn:
            c2, r2 = _fit(x1 - x0, h, gx), _fit(y1 - y0, w, gy)
            if c2 * r2 > cols * rows:
                cols, rows, w, h, turned = c2, r2, h, w, True
    out = Layout(cols=cols, rows=rows, w=w, h=h, turned=turned)
    per = cols * rows
    if per <= 0:
        return out
    bw, bh = cols * w + (cols - 1) * gx, rows * h + (rows - 1) * gy
    if spec.from_selection:
        out.ox = bb[0] if left else bb[2] - bw
        out.oy = bb[3] - bh if top else bb[1]
    else:
        out.ox = x0 + (x1 - x0 - bw) * (0.0 if spec.place.endswith('gauche') else 1.0 if spec.place.endswith('droit') else 0.5)
        out.oy = y0 + (y1 - y0 - bh) * (1.0 if spec.place.startswith('haut') else 0.0 if spec.place.startswith('bas') else 0.5)
    if count is None:
        count = spec.total if spec.total > 0 else (spec.planes * per if spec.planes > 0 else per)
    for n in range(min(max(count, 0), MAX_COPIES)):
        plate, rest = divmod(n, per)
        j, i = divmod(rest, cols)
        back = spec.optimised and j % 2 == 1
        col = cols - 1 - i if back else i
        col = col if left else cols - 1 - col
        row = rows - 1 - j if top else j
        out.cells.append(Cell(plate, col, row, out.ox + col * (w + gx), out.oy + row * (h + gy), back))
    return out


def matrices(bb, lay: Layout, spec: MultiSpec) -> list[Affine]:
    """De l'original à chaque cellule."""
    base = Affine.translation(-bb[0], -bb[1])
    if lay.turned:
        base = Affine.translation(bb[3] - bb[1], 0) @ Affine.rotation(90) @ base
    out = []
    for c in lay.cells:
        m = Affine.translation(c.x, c.y) @ base
        if c.back and spec.turn_back:
            m = Affine.rotation(180, (c.x + lay.w / 2, c.y + lay.h / 2)) @ m
        out.append(m)
    return out


def _edges(cells) -> tuple[set, set]:
    """Les bords des cellules : (colonne, ligne) à l'horizontale, (ligne de colonne, rangée) à la verticale."""
    across, down = set(), set()
    for c, r in cells:
        across |= {(c, r), (c, r + 1)}
        down |= {(c, r), (c + 1, r)}
    return across, down


def cut_lines(lay: Layout, cells, spec: MultiSpec, box) -> Path | None:
    """Les lignes de découpe autour de ces cellules (colonne, rangée) d'une plaque : bords entiers (`totale`), ou trait
    à chaque croisement (`partielle`). Rien autour d'une cellule vide. Elles restent sur la plaque."""
    cells = set(cells)
    if spec.cuts not in ('partielle', 'totale') or not cells:
        return None
    gx, gy = max(spec.gap_x, 0.0), max(spec.gap_y, 0.0)

    def X(c):
        return min(max(lay.ox + c * (lay.w + gx) - gx / 2, box[0]), box[2])

    def Y(r):
        return min(max(lay.oy + r * (lay.h + gy) - gy / 2, box[1]), box[3])
    across, down = _edges(cells)
    contours = []
    if spec.cuts == 'totale':
        for r in sorted({r for _c, r in across}):
            cols = sorted(c for c, rr in across if rr == r)
            start = prev = cols[0]
            for c in cols[1:] + [None]:
                if c is None or c != prev + 1:
                    contours.append(polyline([(X(start), Y(r)), (X(prev + 1), Y(r))], closed=False))
                    start = c
                prev = c
        for c in sorted({c for c, _r in down}):
            rows = sorted(r for cc, r in down if cc == c)
            start = prev = rows[0]
            for r in rows[1:] + [None]:
                if r is None or r != prev + 1:
                    contours.append(polyline([(X(c), Y(start)), (X(c), Y(prev + 1))], closed=False))
                    start = r
                prev = r
        return Path(contours)
    tick = max(spec.tick, 0.01)
    nodes = {(c, r) for c, r in across} | {(c + 1, r) for c, r in across} | {(c, r) for c, r in down} | {(c, r + 1) for c, r in down}
    for c, r in sorted(nodes):
        x, y = X(c), Y(r)
        a = min(tick, (x - X(c - 1)) / 2) if (c - 1, r) in across else 0.0
        b = min(tick, (X(c + 1) - x) / 2) if (c, r) in across else 0.0
        if a + b > 0:
            contours.append(polyline([(x - a, y), (x + b, y)], closed=False))
        a = min(tick, (y - Y(r - 1)) / 2) if (c, r - 1) in down else 0.0
        b = min(tick, (Y(r + 1) - y) / 2) if (c, r) in down else 0.0
        if a + b > 0:
            contours.append(polyline([(x, y - a), (x, y + b)], closed=False))
    return Path(contours)


def build(items: list, box, spec: MultiSpec, count: int | None = None, dress=None) -> MultiResult:
    """Les exemplaires. `dress(copies, n)` peut les remplir (variables) et dit si l'exemplaire n'est pas vide."""
    bb = bbox_union(it.bbox() for it in items)
    if not bb:
        return MultiResult(Layout())
    lay = layout(bb, box, spec, count)
    res = MultiResult(lay)
    if not lay.cells:
        return res
    copied = items[1:] if spec.ignore_first else items
    res.planes = [[] for _ in range(lay.plates)]
    full: list[set] = [set() for _ in range(lay.plates)]
    for n, (cell, m) in enumerate(zip(lay.cells, matrices(bb, lay, spec))):
        copies = [_copy(it, m) for it in copied]
        if dress is None or dress(copies, n):
            full[cell.plate].add((cell.col, cell.row))
        res.planes[cell.plate].extend(copies)
        res.count += 1
    res.cuts = [cut_lines(lay, cells, spec, box) for cells in full]
    return res
