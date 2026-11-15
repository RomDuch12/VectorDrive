"""Texte en colonnes (TypeEdit) : des rangées et des colonnes de texte, posées par leur première ligne de base ou comme un
tableau, avec une largeur, un alignement et des marges par colonne, et des bordures au choix.

Le groupe construit garde son réglage (`extra['text_columns']`) : un double-clic le rouvre sans perdre le texte.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .document import Group, Shape, Text
from .geom import Affine, Path, polyline, rect

#: au-delà, un tableau de texte n'a plus de sens et la fenêtre deviendrait inutilisable
MAX_ROWS = 500
MAX_COLS = 50


@dataclass
class Column:
    width: float = 40.0              # mm
    align: str = 'left'
    left: float = 3.0                # marge gauche, en % de la largeur de la cellule
    text_width: float = 94.0         # largeur du texte, en % de la largeur de la cellule
    bottom: float = 1.5              # du bas de la cellule à la ligne de base (mm)


@dataclass
class TextColumns:
    method: str = 'baseline'
    height: float = 5.0              # hauteur des capitales : elle prime sur la hauteur de ligne
    font: str = 'Arial'
    rows: int = 3
    cols: int = 2
    x: float = 0.0
    y: float = 0.0
    anchor: list = field(default_factory=lambda: [0.0, 1.0])  # le point du tableau que donnent x et y, en fractions
    line_height: float = 8.0         # sur la ligne de base : l'interligne
    total_w: float = 80.0            # dans un tableau : ses dimensions
    total_h: float = 24.0
    same: bool = True                # toutes les colonnes comme la première
    columns: list = field(default_factory=lambda: [Column()])
    borders: str = 'all'
    border_tool: int = 0
    cells: list = field(default_factory=list)        # rangées de textes

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> 'TextColumns':
        known = {k: v for k, v in d.items() if k in TextColumns.__dataclass_fields__}
        known['columns'] = [Column(**{k: v for k, v in c.items() if k in Column.__dataclass_fields__}) for c in d.get('columns') or []]
        return TextColumns(**known)


def clean(spec: TextColumns) -> TextColumns:
    """Le réglage ramené à ce qui se construit : bornes, autant de réglages de colonne que de colonnes, tableau toujours bordé."""
    spec.rows = max(1, min(int(spec.rows), MAX_ROWS))
    spec.cols = max(1, min(int(spec.cols), MAX_COLS))
    spec.height = max(0.01, float(spec.height))
    spec.line_height = max(0.01, float(spec.line_height))
    spec.total_w = max(0.01, float(spec.total_w))
    spec.total_h = max(0.01, float(spec.total_h))
    cols = list(spec.columns) or [Column()]
    while len(cols) < spec.cols:
        cols.append(Column(**asdict(cols[-1])))
    spec.columns = cols[:spec.cols]
    for c in spec.columns:
        c.width = max(0.01, float(c.width))
        c.left = max(0.0, min(float(c.left), 100.0))
        c.text_width = max(1.0, min(float(c.text_width), 100.0 - c.left))
    if spec.method == 'table' and spec.borders == 'none':
        spec.borders = 'all'                         # le manuel : un tableau garde ses bordures
    return spec


def widths(spec: TextColumns) -> list[float]:
    """La largeur de chaque colonne."""
    if spec.method == 'table' and spec.same:
        return [spec.total_w / spec.cols] * spec.cols
    if spec.same:
        return [spec.columns[0].width] * spec.cols
    return [c.width for c in spec.columns]


def row_height(spec: TextColumns) -> float:
    return spec.total_h / spec.rows if spec.method == 'table' else spec.line_height


def corner(spec: TextColumns) -> tuple[float, float, float, float]:
    """Le tableau : (gauche, haut, largeur, hauteur)."""
    w, h = sum(widths(spec)), row_height(spec) * spec.rows
    fx = float(spec.anchor[0]) if spec.anchor else 0.0
    if spec.method == 'table':
        fy = float(spec.anchor[1]) if len(spec.anchor) > 1 else 1.0
        return spec.x - fx * w, spec.y - fy * h + h, w, h
    # x et y : un point de la première ligne de base ; le bas de la première rangée est sous lui
    first = column_of(spec, 0)
    return spec.x - fx * w, spec.y - first.bottom + row_height(spec), w, h


def column_of(spec: TextColumns, j: int) -> Column:
    return spec.columns[0] if spec.same else spec.columns[j]


def lines_of(spec: TextColumns) -> Path:
    """Les bordures."""
    x0, top, w, h = corner(spec)
    rh = row_height(spec)
    bottom = top - h
    out = []
    if spec.borders in ('all', 'frame'):
        out.append(rect(x0, bottom, w, h))
    if spec.borders in ('all', 'h'):
        first, last = (1, spec.rows) if spec.borders == 'all' else (0, spec.rows + 1)
        for i in range(first, last):
            y = top - i * rh
            out.append(polyline([(x0, y), (x0 + w, y)]))
    if spec.borders in ('all', 'v'):
        xs = [x0]
        for v in widths(spec):
            xs.append(xs[-1] + v)
        inner = xs[1:-1] if spec.borders == 'all' else xs
        for x in inner:
            out.append(polyline([(x, top), (x, bottom)]))
    return Path(out)


def cell_text(spec: TextColumns, i: int, j: int) -> str:
    return str(spec.cells[i][j]) if i < len(spec.cells) and j < len(spec.cells[i]) else ''


def build(spec: TextColumns, tool: int = 0, name: str = 'Texte en colonnes') -> Group:
    """Le groupe : les bordures, puis un texte par cellule remplie, ajusté à la largeur de sa cellule."""
    from . import text as TX
    spec = clean(spec)
    x0, top, _w, _h = corner(spec)
    rh = row_height(spec)
    ws = widths(spec)
    children = []
    path = lines_of(spec)
    if path.contours:
        children.append(Shape(path=path, tool=spec.border_tool))
    for i in range(spec.rows):
        x = x0
        low = top - (i + 1) * rh
        for j, w in enumerate(ws):
            s = cell_text(spec, i, j)
            if s.strip():
                c = column_of(spec, j)
                room = w * c.text_width / 100.0
                xa = x + w * c.left / 100.0
                at = {'center': xa + room / 2, 'right': xa + room}.get(c.align, xa)
                t = Text(text=s, font=spec.font, size=spec.height, matrix=Affine.translation(at, low + c.bottom),
                         align='left' if c.align == 'justify' else c.align, tool=tool)
                if c.align == 'justify':
                    t.extra['fit'] = {'width': room, 'mode': 'spacing'}
                else:
                    t.extra['max_length'] = {'length': room, 'by': 'line'}
                t.outline = TX.outline_for(t)
                children.append(t)
            x += w
    g = Group(children=children, tool=tool, name=name)
    g.extra['text_columns'] = spec.to_dict()
    return g


def seed_from_lines(spec: TextColumns, lines: list[str]) -> TextColumns:
    """Les lignes d'un texte dans la première colonne, comme chez TypeEdit : la première colonne se remplit d'abord."""
    spec.rows = max(spec.rows, min(len(lines), MAX_ROWS))
    spec.cells = [[s] for s in lines[:MAX_ROWS]]
    return spec
