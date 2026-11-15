"""Tampon : prépare la gravure d'un tampon encreur (caoutchouc au laser)
à partir de la sélection — l'outil « tampon » des métiers de TypeEdit.

- cadre autour des objets (marge, coins arrondis), bordure en relief de
  l'épaisseur voulue (0 = aucune) ;
- épaulement : les lettres sont élargies à leur pied (décalage) pour
  qu'elles tiennent ;
- miroir (un tampon imprime à l'envers) ;
- négatif : la zone à graver est le fond (cadre − objets − bordure),
  éventuellement rempli de hachures pour une machine à fraise ou un laser
  vectoriel ;
- le contour extérieur du cadre est donné à part (découpe).

Le support peut aussi être imposé : rectangle, cercle ou ellipse à un format
donné, le dessin y est centré et, au choix, mis à l'échelle pour y tenir. La
découpe peut suivre le support, la forme des objets, leur rectangle, ou leurs
boîtes (par ligne) fusionnées.

Le résultat est un groupe re-modifiable : objets d'origine masqués (non
retournés), zone à graver, hachures ; réglages dans `extra['stamp']`.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from . import pathops
from .document import Group, Shape
from .geom import Affine, Path, circle, ellipse, rect

SUPPORT_KINDS = ('auto', 'rect', 'cercle', 'ellipse')
CUT_KINDS = ('support', 'optimise', 'rectangle', 'boites')
MIN_SUPPORT = 0.1
#: formats courants (nom, forme, largeur, hauteur en mm)
SUPPORTS = (('20 × 10', 'rect', 20.0, 10.0), ('38 × 14', 'rect', 38.0, 14.0), ('47 × 18', 'rect', 47.0, 18.0),
            ('58 × 22', 'rect', 58.0, 22.0), ('68 × 24', 'rect', 68.0, 24.0), ('70 × 10', 'rect', 70.0, 10.0),
            ('60 × 40', 'rect', 60.0, 40.0), ('75 × 38', 'rect', 75.0, 38.0), ('ø 30', 'cercle', 30.0, 30.0),
            ('ø 40', 'cercle', 40.0, 40.0), ('ø 50', 'cercle', 50.0, 50.0), ('ø 75', 'cercle', 75.0, 75.0),
            ('75 × 50', 'ellipse', 75.0, 50.0))


@dataclass
class StampSpec:
    margin: float = 2.0             # mm entre les objets et le bord du cadre
    radius: float = 1.0             # rayon des coins du cadre
    border: float = 0.8             # épaisseur de la bordure en relief (0 = aucune)
    shoulder: float = 0.0           # épaulement des objets (mm)
    mirror: bool = True
    negative: bool = True           # graver le fond (sinon : les objets)
    hatch: float = 0.0              # pas des hachures du fond (0 = aucune)
    support: str = 'auto'           # autour des objets, ou format imposé (`SUPPORT_KINDS`)
    width: float = 60.0             # format imposé (mm) ; cercle : le diamètre
    height: float = 40.0
    fit: bool = True                # mettre le dessin à l'échelle du support, marge comprise
    cut: str = 'support'            # forme de la découpe (`CUT_KINDS`)
    cut_offset: float = 0.0         # décalage de la découpe (mm)

    @classmethod
    def from_dict(cls, d: dict) -> 'StampSpec':
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        return asdict(self)


def _closed(items) -> Path:
    from .hatch import closed_path
    return closed_path(items)


def _support_size(spec: StampSpec) -> tuple[float, float]:
    w = max(MIN_SUPPORT, spec.width)
    return (w, w) if spec.support == 'cercle' else (w, max(MIN_SUPPORT, spec.height))


def fit_scale(source: Path, spec: StampSpec) -> float:
    """Échelle qui fait tenir le dessin dans le support, marge comprise (un cercle ou
    une ellipse se juge sur le tracé lui-même, pas sur sa boîte)."""
    x0, y0, x1, y1 = source.bbox()
    w, h = _support_size(spec)
    a, b = w / 2 - spec.margin, h / 2 - spec.margin
    if a <= 0 or b <= 0:
        return 1.0
    if spec.support == 'rect':
        sw, sh = x1 - x0, y1 - y0
        return min(2 * a / sw if sw > 1e-9 else float('inf'), 2 * b / sh if sh > 1e-9 else float('inf'))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    far = 0.0
    for c in source.contours:
        for px, py in c.flatten(0.01):
            far = max(far, ((px - cx) / a) ** 2 + ((py - cy) / b) ** 2)
    return 1.0 / far ** 0.5 if far > 0 else 1.0


def placed_source(source: Path, spec: StampSpec) -> Path:
    """Le dessin tel qu'il va sur le support : à l'échelle si `fit`. Son centre ne bouge pas."""
    if spec.support == 'auto' or not spec.fit:
        return source
    k = fit_scale(source, spec)
    if k == float('inf') or abs(k - 1.0) < 1e-12:
        return source
    x0, y0, x1, y1 = source.bbox()
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return source.transformed(Affine.translation(cx, cy) @ Affine.scaling(k) @ Affine.translation(-cx, -cy))


def overflows(source: Path, spec: StampSpec) -> bool:
    """Le dessin dépasse-t-il du support, marge comprise ?"""
    return spec.support != 'auto' and fit_scale(placed_source(source, spec), spec) < 1.0 - 1e-6


def frame_of(source: Path, spec: StampSpec) -> Path:
    x0, y0, x1, y1 = source.bbox()
    if spec.support != 'auto':
        w, h = _support_size(spec)
        c = ((x0 + x1) / 2, (y0 + y1) / 2)
        if spec.support == 'cercle':
            return Path([circle(c, w / 2)])
        if spec.support == 'ellipse':
            return Path([ellipse(c, w / 2, h / 2)])
        return Path([rect(c[0] - w / 2, c[1] - h / 2, w, h, max(0.0, min(spec.radius, w / 2, h / 2)))])
    m = spec.margin
    w, h = x1 - x0 + 2 * m, y1 - y0 + 2 * m
    r = max(0.0, min(spec.radius, w / 2, h / 2))
    return Path([rect(x0 - m, y0 - m, w, h, r)])


def region(source: Path, spec: StampSpec) -> Path:
    """Zone à graver (avant miroir)."""
    frame = frame_of(source, spec)
    objs = pathops.normalize(source)
    if spec.shoulder > 0:
        from .parallel import offset_checked
        objs = offset_checked(objs, spec.shoulder)[0]             # exact, contrôlé
    if not spec.negative:
        out = objs
        if spec.border > 0:
            ring = pathops.boolean(frame, pathops.offset(frame, -spec.border, 'miter'), 'difference')
            out = pathops.boolean(out, ring, 'union')
        return out
    inner = pathops.offset(frame, -spec.border, 'miter') if spec.border > 0 else frame
    return pathops.boolean(inner, objs, 'difference')


def _line_boxes(source: Path) -> list[tuple]:
    """Une boîte par ligne : les contours dont les hauteurs se recouvrent vont ensemble."""
    boxes = sorted((c.bbox() for c in source.contours), key=lambda b: b[1])
    lines: list[list] = []
    for b in boxes:
        if lines and b[1] <= lines[-1][3]:
            last = lines[-1]
            last[0], last[2], last[3] = min(last[0], b[0]), max(last[2], b[2]), max(last[3], b[3])
        else:
            lines.append(list(b))
    return [tuple(x) for x in lines]


def cut_path(source: Path, frame: Path, spec: StampSpec) -> Path:
    """Le contour de découpe (avant miroir)."""
    off = spec.cut_offset
    if spec.cut == 'rectangle':
        x0, y0, x1, y1 = source.bbox()
        return Path([rect(x0 - off, y0 - off, max(1e-3, x1 - x0 + 2 * off), max(1e-3, y1 - y0 + 2 * off))])
    if spec.cut == 'optimise':
        from .intersect import outer_only
        return outer_only(pathops.offset(pathops.normalize(source), off, 'round') if off else pathops.normalize(source))
    if spec.cut == 'boites':
        rects = [Path([rect(b[0] - off, b[1] - off, max(1e-3, b[2] - b[0] + 2 * off), max(1e-3, b[3] - b[1] + 2 * off))])
                 for b in _line_boxes(source)]
        return pathops.union_all(rects)
    return pathops.offset(frame, off, 'miter') if off else frame


def build(items, spec: StampSpec, tool: int = 0) -> Group | None:
    source = _closed(items)
    if not source.contours:
        return None
    laid = placed_source(source, spec)
    zone = region(laid, spec)
    frame = frame_of(laid, spec)
    m = Affine()
    if spec.mirror:
        x0, _, x1, _ = frame.bbox()
        m = Affine.mirror_y((x0 + x1) / 2)
    children = []
    src = Shape(path=source, tool=tool, name='Objets')
    src.visible = False
    src.extra['stamp_source'] = True
    children.append(src)
    children.append(Shape(path=zone.transformed(m), tool=tool, name='Zone à graver'))
    children.append(Shape(path=cut_path(laid, frame, spec).transformed(m), tool=tool, name='Découpe'))     # à découper
    if spec.hatch > 0:
        from .hatch import HatchSpec, hatch_path
        lines = hatch_path(zone, HatchSpec(spacing=spec.hatch, angle=0.0, outline=False))
        children.append(Shape(path=lines.transformed(m), tool=tool, name='Hachures'))
    g = Group(children=children, tool=tool, name='Tampon')
    g.extra['stamp'] = spec.to_dict()
    return g


def rebuild(g: Group, spec: StampSpec) -> Group:
    src = next(c for c in g.children if c.extra.get('stamp_source'))
    return build([Shape(path=src.path, tool=src.tool)], spec, g.tool)
