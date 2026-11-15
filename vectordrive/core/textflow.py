"""Texte dans une forme : le texte coule dans un contour fermé, ligne après ligne,
de part et d'autre de ses trous ou de ses creux.

Chaque ligne cherche les parties libres de sa bande (toute la hauteur réelle des
lettres employées) : rien ne dépasse de la forme. Le résultat est un groupe :
une ligne de texte vivant par morceau, et la forme, masquée, pour le reprendre.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields

from shapely.geometry import Polygon, box

from . import fonts
from . import text as TX
from .document import Group, Shape, Text
from .geom import Affine, Path, polyline

ALIGNS = ('left', 'center', 'right', 'justify')
KEY = 'text_flow'
MIN_SIZE = 0.2
#: justification : au-delà de cet écart entre lettres (× hauteur), la ligne reste alignée à gauche
MAX_GAP = 0.2
FIT_STEPS = 16
#: la première ligne descend par ce pas (× hauteur) jusqu'à trouver la place de son premier mot
SEARCH = 0.1


@dataclass
class FlowSpec:
    size: float = 5.0                                    # hauteur des capitales (mm)
    fit: bool = False                                    # la plus grande hauteur qui fait tout tenir
    line_spacing: float = 1.2
    margin: float = 1.0                                  # marge au bord de la forme (mm)
    align: str = 'center'
    middle: bool = True                                  # bloc centré dans la hauteur de la forme

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> 'FlowSpec':
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (d or {}).items() if k in names})


@dataclass
class FlowLine:
    text: str
    x: float
    y: float                                             # ligne de base
    spacing: float = 0.0


@dataclass
class Flowed:
    lines: list
    size: float
    rest: str = ''                                       # ce qui n'a pas trouvé place


def region_of(path: Path, margin: float = 0.0):
    """La zone utile (shapely) : contours fermés en pair-impair, moins la marge. ValueError si elle est vide."""
    zone = None
    for c in path.contours:
        if not c.closed or not c.segments:
            continue
        pts = c.flatten(0.01)
        if len(pts) < 3:
            continue
        poly = Polygon(pts).buffer(0)
        zone = poly if zone is None else zone.symmetric_difference(poly)
    if zone is None or zone.is_empty or zone.area <= 0:
        raise ValueError('forme')
    if margin > 0:
        zone = zone.buffer(-margin)
    if zone.is_empty or zone.area <= 0:
        raise ValueError('marge')
    return zone


def carve(region: Path, obstacles: list, gap: float = 0.0) -> Path:
    """La forme moins d'autres formes, à `gap` mm autour d'elles : le texte y coule en les contournant
    (l'habillage de VectorCraft et d'Inkscape). Elles peuvent déborder de la forme, ou la couper en plusieurs zones.
    ValueError s'il ne reste rien."""
    from shapely.geometry import MultiPolygon
    zone = region_of(region)
    for path in obstacles:
        try:
            cut = region_of(path)
        except ValueError:
            continue
        zone = zone.difference(cut.buffer(gap) if gap > 0 else cut)
    if zone.is_empty or zone.area <= 0:
        raise ValueError('forme')
    polys = list(zone.geoms) if isinstance(zone, MultiPolygon) else [zone]
    contours = []
    for poly in polys:
        if not isinstance(poly, Polygon) or poly.area <= 0:
            continue
        for ring in (poly.exterior, *poly.interiors):
            contours.append(polyline(list(ring.coords)[:-1], True))
    return Path(contours)


def _free(zone, y0: float, y1: float) -> list[tuple[float, float]]:
    """Les intervalles de x dont le rectangle (x, y0..y1) est tout entier dans la zone, de gauche à droite."""
    x0, _b, x1, _t = zone.bounds
    band = box(x0 - 1.0, y0, x1 + 1.0, y1)
    blocked = band.difference(zone)
    parts = getattr(blocked, 'geoms', [blocked])
    spans = sorted((g.bounds[0], g.bounds[2]) for g in parts if not g.is_empty and g.area > 1e-9)
    out, at = [], x0 - 1.0
    for a, b in spans:
        if a > at:
            out.append((at, a))
        at = max(at, b)
    if at < x1 + 1.0:
        out.append((at, x1 + 1.0))
    return [(a, b) for a, b in out if b - a > 1e-6]


class _Measure:
    def __init__(self, text: str, font: str, size: float, line_spacing: float):
        self.font, self.size = font, size
        self.widths: dict[str, float] = {}
        ff = fonts.find_font(font)
        self.step = TX.em_for_height(ff, size) * line_spacing if ff else 0.0
        chars = ''.join(sorted(set(text) - set(' \n\t')))
        box1 = TX.layout_bbox(chars, font, size) if chars else None
        self.below = max(0.0, -box1[1]) if box1 else 0.0
        self.above = box1[3] if box1 else size

    def width(self, s: str) -> float:
        got = self.widths.get(s)
        if got is None:
            got = TX.line_widths(s, self.font, self.size)[0]
            self.widths[s] = got
        return got


def _place(words: list, zone, m: _Measure, start: float) -> tuple[list, list, list]:
    """Pose les mots à partir de la ligne de base `start` : (morceaux [(texte, x0, x1, y, dernier)], reste, bornes)."""
    bottom = zone.bounds[1]
    y = start
    done, i, started = [], 0, False
    n = len(words)
    while i < n and y - m.below >= bottom - 1e-9:
        spans = _free(zone, y - m.below, y + m.above)
        forced = False
        for a, b in spans:
            if i >= n or forced:
                break
            line: list[str] = []
            last = False
            while i < n:
                w = words[i]
                if w is None:                            # fin de paragraphe
                    i += 1
                    last = True
                    forced = True
                    break
                test = ' '.join([*line, w])
                if m.width(test) <= b - a:
                    line.append(w)
                    i += 1
                else:
                    break
            if i >= n:
                last = True
            if line:
                done.append((' '.join(line), a, b, y, last))
                started = True
        if not started:                                  # pas encore de place pour le premier mot : descendre un peu
            y -= m.size * SEARCH
        elif forced and not done:
            y -= m.step
        else:
            y -= m.step
    rest = [w for w in words[i:]]
    return done, rest, [start]


def _words(text: str) -> list:
    out: list = []
    for para in text.split('\n'):
        out.extend(para.split())
        out.append(None)
    while out and out[-1] is None:
        out.pop()
    return out


def _rest_text(rest: list) -> str:
    parts, cur = [], []
    for w in rest:
        if w is None:
            parts.append(' '.join(cur))
            cur = []
        else:
            cur.append(w)
    parts.append(' '.join(cur))
    return '\n'.join(parts).strip('\n')


def _lines(pieces: list, align: str, m: _Measure) -> list[FlowLine]:
    out = []
    for text, a, b, y, last in pieces:
        w = m.width(text)
        x, gap = a, 0.0
        if align == 'center':
            x = a + (b - a - w) / 2
        elif align == 'right':
            x = b - w
        elif align == 'justify' and not last and len(text) > 1:
            g = (b - a - w) / (len(text) - 1)
            if g <= m.size * MAX_GAP:
                gap = g
        out.append(FlowLine(text, x, y, gap))
    return out


def _attempt(words: list, zone, text: str, font: str, size: float, spec: FlowSpec) -> tuple[list, list, _Measure]:
    m = _Measure(text, font, size, spec.line_spacing)
    top = zone.bounds[3] - m.above
    pieces, rest, _ = _place(words, zone, m, top)
    if spec.middle and pieces and not rest:
        for _ in range(3):                               # l'espace libre partagé entre le haut et le bas
            high = zone.bounds[3] - (pieces[0][3] + m.above)
            low = pieces[-1][3] - m.below - zone.bounds[1]
            shift = (low - high) / 2
            if shift <= 1e-3:
                break
            again, left, _ = _place(words, zone, m, pieces[0][3] - shift)
            if left:
                break
            pieces = again
    return pieces, rest, m


def flow(text: str, font: str, region: Path, spec: FlowSpec) -> Flowed:
    """Les lignes du texte dans la forme. ValueError : forme ouverte ou mangée par la marge."""
    zone = region_of(region, max(0.0, spec.margin))
    align = spec.align if spec.align in ALIGNS else 'left'
    words = _words(text)
    if not words or not fonts.find_font(font):
        return Flowed([], spec.size, text.strip())
    size = max(MIN_SIZE, spec.size)
    if spec.fit:
        lo, hi = MIN_SIZE, max(MIN_SIZE * 2, zone.bounds[3] - zone.bounds[1])
        best = None
        for _ in range(FIT_STEPS):
            mid = (lo + hi) / 2
            pieces, rest, m = _attempt(words, zone, text, font, mid, spec)
            if rest or not pieces:
                hi = mid
            else:
                lo = mid
                best = (pieces, m, mid)
        if best is not None:
            pieces, m, size = best
            return Flowed(_lines(pieces, align, m), size)
        size = MIN_SIZE
    pieces, rest, m = _attempt(words, zone, text, font, size, spec)
    return Flowed(_lines(pieces, align, m), size, _rest_text(rest))


def build(text: str, font: str, region: Path, spec: FlowSpec, *, tool: int = 0) -> tuple[Group | None, Flowed]:
    """Le groupe : la forme masquée, puis une ligne de texte par morceau. None si rien n'a trouvé place."""
    got = flow(text, font, region, spec)
    if not got.lines:
        return None, got
    kids: list = [Shape(path=region, tool=tool, visible=False, extra={'flow_region': 1})]
    for ln in got.lines:
        t = Text(text=ln.text, font=font, size=got.size, matrix=Affine.translation(ln.x, ln.y), align='left',
                 spacing=ln.spacing, line_spacing=spec.line_spacing, tool=tool)
        t.outline = TX.outline_for(t)
        kids.append(t)
    g = Group(children=kids, tool=tool)
    g.extra[KEY] = {**spec.to_dict(), 'text': text, 'font': font, 'used_size': got.size}
    return g, got


def region_child(g: Group):
    return next((c for c in g.children if isinstance(c, Shape) and c.extra.get('flow_region')), None)


def rebuild(g: Group, text: str, font: str, spec: FlowSpec) -> tuple[Group | None, Flowed]:
    """De nouveaux réglages pour un groupe : la forme, éventuellement déplacée avec lui, reste celle de départ."""
    shape = region_child(g)
    if shape is None:
        raise ValueError('forme')
    return build(text, font, shape.path, spec, tool=g.tool)
