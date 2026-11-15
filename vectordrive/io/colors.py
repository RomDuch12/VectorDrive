"""Couleurs des fichiers lus et écrits (DXF, SVG…) : une couleur = un outil, comme dans TypeEdit.

À la lecture, chaque couleur rencontrée devient un outil du document, dans l'ordre d'apparition
(la première : l'outil 0) ; le blanc (couleur 7 des DAO, blanc sur fond noir) et l'absence de couleur
comptent pour le noir. `KEEP` faux (F10 › Fichiers) : tout à l'outil 0, comme avant."""
from __future__ import annotations

import re

#: couleurs des fichiers lus reprises en outils (réglage import/couleurs)
KEEP = True
#: DXF écrits : le noir porte aussi sa couleur vraie (réglage export/dxf_noir). Seul, le numéro 7 des DAO — « blanc
#: ou noir selon le fond » — est dessiné en blanc par TypeEdit, invisible sur sa page ; avec la couleur vraie il reste noir
DXF_BLACK_TRUE = True
#: DXF écrits : les courbes en arcs de cercle raccordés (réglage export/dxf_courbes), à DXF_ARC_TOL mm près, au lieu
#: de SPLINE exactes — LibreCAD ignore les nœuds d'une SPLINE et déforme une courbe de Bézier à plusieurs morceaux
DXF_ARCS = False
DXF_ARC_TOL = 0.005
#: écart (0…255 par composante) sous lequel deux couleurs font un seul outil ; outils créés au plus
NEAR, MAX_TOOLS = 40, 10                  # 10 : les outils d'un document TypeEdit

#: noms de couleurs CSS courants (SVG)
NAMED = {'black': '#000000', 'white': '#ffffff', 'red': '#ff0000', 'lime': '#00ff00', 'green': '#008000',
         'blue': '#0000ff', 'yellow': '#ffff00', 'cyan': '#00ffff', 'aqua': '#00ffff', 'magenta': '#ff00ff',
         'fuchsia': '#ff00ff', 'gray': '#808080', 'grey': '#808080', 'silver': '#c0c0c0', 'maroon': '#800000',
         'olive': '#808000', 'navy': '#000080', 'purple': '#800080', 'teal': '#008080', 'orange': '#ffa500',
         'brown': '#a52a2a', 'pink': '#ffc0cb', 'gold': '#ffd700', 'darkgreen': '#006400',
         'darkblue': '#00008b', 'darkred': '#8b0000', 'darkgray': '#a9a9a9', 'darkgrey': '#a9a9a9',
         'lightgray': '#d3d3d3', 'lightgrey': '#d3d3d3', 'violet': '#ee82ee', 'indigo': '#4b0082'}
_RGB = re.compile(r'rgba?\(\s*([\d.]+%?)\s*[, ]\s*([\d.]+%?)\s*[, ]\s*([\d.]+%?)')


def hex_of(r: float, g: float, b: float) -> str:
    return '#{:02x}{:02x}{:02x}'.format(*(max(0, min(255, int(round(v)))) for v in (r, g, b)))


def rgb_of(color: str) -> tuple[int, int, int]:
    c = color.lstrip('#')
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)) if len(c) == 6 else (0, 0, 0)


def parse_css(text: str | None) -> str | None:
    """Couleur CSS/SVG (#rgb, #rrggbb, rgb(…), nom) en « #rrggbb » ; None : aucune ou inconnue."""
    if not text:
        return None
    t = text.strip().lower()
    if t in ('none', 'transparent', 'inherit', 'currentcolor') or t.startswith('url('):
        return None
    if t.startswith('#'):
        h = t[1:]
        if len(h) == 3 and all(c in '0123456789abcdef' for c in h):
            return '#' + ''.join(c * 2 for c in h)
        if len(h) >= 6 and all(c in '0123456789abcdef' for c in h[:6]):
            return '#' + h[:6]
        return None
    m = _RGB.match(t)
    if m:
        vals = [float(v[:-1]) * 2.55 if v.endswith('%') else float(v) for v in m.groups()]
        return hex_of(*vals)
    return NAMED.get(t)


def from_operands(vals) -> str | None:
    """Couleur d'opérandes PDF / PostScript : 1 = gris, 3 = RVB, 4 = CMJN (0…1)."""
    try:
        v = [float(x) for x in vals]
    except (TypeError, ValueError):
        return None
    if len(v) == 1:
        return hex_of(v[0] * 255, v[0] * 255, v[0] * 255)
    if len(v) == 3:
        return hex_of(v[0] * 255, v[1] * 255, v[2] * 255)
    if len(v) == 4:
        c, m, y, k = v
        return hex_of(255 * (1 - c) * (1 - k), 255 * (1 - m) * (1 - k), 255 * (1 - y) * (1 - k))
    return None


class ToolColors:
    """Couleurs rencontrées dans un fichier lu → outils de `doc` (ordre d'apparition)."""

    def __init__(self, doc):
        self.doc = doc
        self.map: dict[str, int] = {}
        self.made: dict[int, tuple] = {}                 # outils créés : leur couleur (r, v, b)

    def tool(self, color: str | None) -> int:
        if not KEEP:
            return 0
        c = (color or '#000000').lower()
        if c == '#ffffff':
            c = '#000000'                                # blanc des DAO (fond noir) : noir
        idx = self.map.get(c)
        if idx is None and self.made:
            # teintes voisines (PDF d'impression : #000000, #020203, #1e1e1c…) : un seul outil ;
            # au-delà de MAX_TOOLS couleurs, la plus proche
            rgb = rgb_of(c)
            gap, near = min((max(abs(a - b) for a, b in zip(v, rgb)), k) for k, v in self.made.items())
            if gap <= NEAR or len(self.made) >= MAX_TOOLS:
                idx = self.map[c] = near
        if idx is None:
            from ..core.document import Tool
            idx = self.map[c] = len(self.made)
            self.made[idx] = rgb_of(c)
            old = next((t for t in self.doc.tools if t.index == idx), None)
            self.doc.tools = [t for t in self.doc.tools if t.index != idx] + \
                [Tool(idx, c, old.name if old else f'Outil {idx + 1}', old.width if old else 0.0)]
            self.doc.tools.sort(key=lambda t: t.index)
        return idx


def black_first(doc, colors: 'ToolColors') -> None:
    """Fin de lecture : le noir (et le blanc des DAO), s'il est employé, prend l'outil 1 (index 0) — celui
    que les modèles de FAO usinent d'office — en échangeant avec la couleur qui l'avait."""
    b = colors.map.get('#000000')
    if not b:
        return
    swap = {0: b, b: 0}
    for L in doc.layers:
        for it in L.items:
            for leaf in [it] + list(_descendants(it)):
                t = int(getattr(leaf, 'tool', 0) or 0)
                if t in swap:
                    leaf.tool = swap[t]
    cols = {t.index: t for t in doc.tools}
    t0, tb = cols.get(0), cols.get(b)
    if t0 is not None and tb is not None:
        t0.color, tb.color = tb.color, t0.color
    colors.map = {k: swap.get(v, v) for k, v in colors.map.items()}
    colors.made = {swap.get(k, k): v for k, v in colors.made.items()}


def _descendants(item):
    for ch in getattr(item, 'children', ()) or ():
        yield ch
        yield from _descendants(ch)


def nearest_aci(color: str) -> int:
    """Couleur indexée des DAO (1…255) la plus proche ; 7 pour le noir (noir ou blanc selon le fond)."""
    from ezdxf.colors import aci2rgb
    r, g, b = rgb_of(color)
    if (r, g, b) == (0, 0, 0):
        return 7
    best, bd = 7, None
    for i in range(1, 256):
        c = aci2rgb(i)
        d = (c.r - r) ** 2 + (c.g - g) ** 2 + (c.b - b) ** 2
        if bd is None or d < bd:
            best, bd = i, d
    return best
