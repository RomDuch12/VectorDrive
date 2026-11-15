"""Hachures : traits parallèles qui remplissent des contours fermés (règle
pair-impair : les trous restent vides), pour graver un aplat au laser ou à
la fraise. Angle, pas, hachures croisées, retrait du bord ; les traits
alternent de sens (moins de trajets à vide).

Motifs de DAO (« pat:ANSI31 »…, `core.hatch_patterns`) : familles de
traits du motif, à l'échelle et à l'angle choisis ; ceux d'un fichier .pat
sont gardés dans les réglages (`pat`), le groupe reste modifiable sans lui.

Le résultat est un groupe re-modifiable : les contours d'origine y restent
(masqués si on ne les grave pas) et les réglages dans `extra['hatch']`.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

import numpy as np

from .document import Group, Shape, Text
from .geom import Contour, Line, Path


#: motifs (comme les motifs de hachure des logiciels de DAO) ; le pas en donne l'échelle
PATTERNS = (('lignes', 'Traits parallèles'), ('briques', 'Briques'), ('pointilles', 'Traits pointillés'),
            ('ondules', 'Traits ondulés'), ('nid', "Nid d'abeille"))


@dataclass
class HatchSpec:
    spacing: float = 0.5            # mm entre deux traits
    angle: float = 45.0             # degrés
    cross: bool = False             # seconde série à angle + 90°
    inset: float = 0.0              # retrait du bord (mm)
    outline: bool = True            # graver aussi le contour
    pattern: str = 'lignes'         # PATTERNS, ou « pat:NOM » (motif de DAO)
    scale: float = 1.0              # motif de DAO : échelle (mm du motif ISO × échelle)
    dot: float = 0.2                # motif de DAO : diamètre des points (mm, 0 = aucun)
    pat: list = field(default_factory=list)   # familles d'un motif .pat [[angle, x, y, dx, dy, tirets…]]

    @classmethod
    def from_dict(cls, d: dict) -> 'HatchSpec':
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        return asdict(self)


def closed_path(items) -> Path:
    """Contours fermés des objets (textes compris)."""
    out = []

    def walk(it):
        if isinstance(it, Group):
            for ch in it.children:
                walk(ch)
        elif isinstance(it, Shape):
            out.extend(c for c in it.path.contours if c.closed and c.segments)
        elif isinstance(it, Text):
            if it.outline is None:
                from .text import outline_for
                it.outline = outline_for(it)
            out.extend(c for c in it.outline.contours if c.closed and c.segments)
    for it in items:
        walk(it)
    return Path(out)


def _lines(polys: list[np.ndarray], spacing: float, angle: float) -> list[tuple]:
    """Segments des traits (repère du dessin) pour une série d'angle donné."""
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)
    # repère tourné : les traits deviennent horizontaux
    edges = []
    for P in polys:
        if len(P) < 3:
            continue
        x = P[:, 0] * ca + P[:, 1] * sa
        y = -P[:, 0] * sa + P[:, 1] * ca
        q = np.stack([x, y], 1)
        edges.append(np.concatenate([q, np.roll(q, -1, axis=0)], 1))
    if not edges:
        return []
    E = np.concatenate(edges)                 # (n, 4) : x0 y0 x1 y1
    y0, y1 = E[:, 1], E[:, 3]
    lo, hi = float(min(y0.min(), y1.min())), float(max(y0.max(), y1.max()))
    out = []
    k0 = math.floor(lo / spacing) + 1
    flip = False
    for k in range(k0, int(math.ceil(hi / spacing))):
        y = k * spacing
        m = ((y0 <= y) & (y1 > y)) | ((y1 <= y) & (y0 > y))
        if not m.any():
            continue
        e = E[m]
        t = (y - e[:, 1]) / (e[:, 3] - e[:, 1])
        xs = np.sort(e[:, 0] + t * (e[:, 2] - e[:, 0]))
        segs = [(xs[i], xs[i + 1]) for i in range(0, len(xs) - 1, 2) if xs[i + 1] - xs[i] > 1e-9]
        if flip:
            segs = [(b, a_) for a_, b in reversed(segs)]
        flip = not flip
        for xa, xb in segs:
            out.append(((xa * ca - y * sa, xa * sa + y * ca), (xb * ca - y * sa, xb * sa + y * ca)))
    return out


def _motif(bounds, s: float, pattern: str) -> list[list[tuple[float, float]]]:
    """Polylignes du motif (non tourné) couvrant `bounds`, pas `s`."""
    x0, y0, x1, y1 = bounds
    out = []
    rows = int(math.ceil((y1 - y0) / s)) + 2
    if pattern == 'briques':                         # rangées de hauteur s, briques de 2s, joints décalés
        for k in range(rows):
            y = y0 - s + k * s
            out.append([(x0 - 2 * s, y), (x1 + 2 * s, y)])
            off = (k % 2) * s
            x = x0 - 2 * s + off
            while x <= x1 + 2 * s:
                out.append([(x, y), (x, y + s)])
                x += 2 * s
    elif pattern == 'pointilles':                    # tirets de 2s, espaces de s
        for k in range(rows):
            y = y0 - s + k * s
            x = x0 - 3 * s + (k % 2) * 1.5 * s
            while x <= x1 + 3 * s:
                out.append([(x, y), (x + 2 * s, y)])
                x += 3 * s
    elif pattern == 'ondules':                       # sinusoïde d'amplitude s/3, période 4s
        n = max(8, int((x1 - x0) / (s / 4)) + 16)
        for k in range(rows):
            y = y0 - s + k * s
            out.append([(x0 - 2 * s + (x1 - x0 + 4 * s) * j / n,
                         y + s / 3 * math.sin(2 * math.pi * ((x0 - 2 * s + (x1 - x0 + 4 * s) * j / n) / (4 * s))))
                        for j in range(n + 1)])
    elif pattern == 'nid':                           # hexagones de côté s
        h = math.sqrt(3) * s
        cols = int(math.ceil((x1 - x0) / (1.5 * s))) + 3
        rws = int(math.ceil((y1 - y0) / h)) + 3
        for i in range(-1, cols):
            for j in range(-1, rws):
                cx = x0 + i * 1.5 * s
                cy = y0 + j * h + (i % 2) * h / 2
                pts = [(cx + s * math.cos(math.radians(60 * a)), cy + s * math.sin(math.radians(60 * a)))
                       for a in range(4)]
                out.append(pts)                      # trois côtés : les voisins font les autres
    return out


def _pattern_path(region: Path, spec: HatchSpec) -> Path:
    """Motif découpé dans les contours fermés (pair-impair), tourné de `angle`."""
    import shapely
    from shapely.affinity import rotate
    from shapely.geometry import LineString
    from .geom import polyline
    from .pathops import _to_shapely
    reg = _to_shapely(region)
    if reg.is_empty:
        return Path()
    c = reg.centroid
    back = rotate(reg, -spec.angle, origin=c)
    lines = [LineString(p) for p in _motif(back.bounds, spec.spacing, spec.pattern) if len(p) >= 2]
    if not lines:
        return Path()
    cut = shapely.intersection(shapely.union_all(lines), back)
    cut = rotate(cut, spec.angle, origin=c)
    out = []
    for g in shapely.get_parts(shapely.line_merge(cut) if not cut.is_empty else cut):
        if g.geom_type == 'LineString' and g.length > 1e-9:
            out.append(polyline([tuple(xy) for xy in g.coords]))
    return Path(out)


def pattern_lines(spec: HatchSpec) -> list:
    """Familles de traits du motif de DAO des réglages : celles gardées
    (fichier .pat), sinon celles du motif standard de ce nom."""
    from . import hatch_patterns as HP
    if spec.pat:
        out = []
        for v in spec.pat:
            try:
                out.append(HP.PatternLine.from_list(v))
            except (TypeError, ValueError):
                continue
        return out
    p = HP.standard().get(str(spec.pattern)[4:].upper())
    return list(p.lines) if p is not None else []


def _cad_pattern_path(region: Path, spec: HatchSpec) -> Path:
    from . import hatch_patterns as HP
    from .geom import circle
    lines = pattern_lines(spec)
    gaps = [abs(ln.delta[1]) * spec.scale for ln in lines if abs(ln.delta[1]) > 1e-9]
    tol = min(0.01, min(gaps) / 20) if gaps else 0.01
    polys = [np.asarray(c.flatten(tol), float) for c in region.contours if c.closed]
    segs, dots = HP.segments(polys, lines, spec.scale, spec.angle)
    out = [Contour([Line(a, b)], False) for a, b in segs]
    if spec.dot > 0:
        out.extend(circle(p, spec.dot / 2) for p in dots)
    return Path(out)


def hatch_path(source: Path, spec: HatchSpec) -> Path:
    """Traits de hachure d'un ensemble de contours fermés."""
    region = source
    if spec.inset > 0:
        from .parallel import offset_checked
        region = offset_checked(source, -spec.inset)[0]          # exact, contrôlé
    if str(getattr(spec, 'pattern', '')).startswith('pat:'):
        return _cad_pattern_path(region, spec) if region else Path()
    if spec.spacing <= 0 or not region:
        return Path()
    if getattr(spec, 'pattern', 'lignes') not in ('lignes', ''):
        return _pattern_path(region, spec)
    tol = min(0.01, spec.spacing / 20)
    polys = [np.asarray(c.flatten(tol), float) for c in region.contours if c.closed]
    segs = _lines(polys, spec.spacing, spec.angle)
    if spec.cross:
        segs += _lines(polys, spec.spacing, spec.angle + 90)
    return Path([Contour([Line(a, b)], False) for a, b in segs])


def build(items, spec: HatchSpec, tool: int = 0) -> Group | None:
    source = closed_path(items)
    if not source.contours:
        return None
    src = Shape(path=source, tool=tool, name='Contour')
    src.visible = spec.outline
    src.extra['hatch_source'] = True
    lines = Shape(path=hatch_path(source, spec), tool=tool, name='Hachures')
    g = Group(children=[src, lines], tool=tool, name='Hachures')
    g.extra['hatch'] = spec.to_dict()
    return g


def rebuild(g: Group, spec: HatchSpec) -> Group:
    """Mêmes contours (déplacés, tournés… avec le groupe), nouveaux réglages."""
    src = next(c for c in g.children if c.extra.get('hatch_source'))
    return build([Shape(path=src.path, tool=src.tool)], spec, g.tool)
