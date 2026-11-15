"""Enveloppe : déformation d'objets (textes surtout) dans une forme — arc,
arche, bombé, pincé, vague, trapèze — comme l'enveloppe de TypeEdit ; et
celles des logiciels de dessin vectoriel : arc inférieur, coquilles,
drapeau, poisson, montée, œil de poisson, gonfler, compresser, torsion.

La déformation n'est pas affine : chaque morceau de courbe est remplacé
par la courbe de Bézier d'Hermite qui a les mêmes extrémités et les mêmes
tangentes que l'image exacte, coupé en deux tant que l'écart dépasse la
tolérance (0,005 mm par défaut). Les droites qui restent droites restent
des droites.

Le résultat est un groupe re-modifiable : objets d'origine masqués +
objets déformés (un par objet, calque conservé), réglages dans
`extra['envelope']`.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from .document import Group, Shape, Text
from .geom import Conic, Contour, Cubic, Line, Path, bbox_union, dist

KINDS = ('arc', 'arche', 'bombe', 'pince', 'vague', 'trapeze', 'arc_bas', 'coquille_bas', 'coquille_haut',
         'drapeau', 'poisson', 'montee', 'oeil', 'gonfler', 'compresser', 'torsion')
NAMES = {'arc': 'Arc', 'arche': 'Arche', 'bombe': 'Bombé', 'pince': 'Pincé', 'vague': 'Vague',
         'trapeze': 'Trapèze (perspective)', 'arc_bas': 'Arc inférieur', 'coquille_bas': 'Coquille vers le bas',
         'coquille_haut': 'Coquille vers le haut', 'drapeau': 'Drapeau', 'poisson': 'Poisson', 'montee': 'Montée',
         'oeil': 'Œil de poisson', 'gonfler': 'Gonfler', 'compresser': 'Compresser', 'torsion': 'Torsion'}


@dataclass
class EnvelopeSpec:
    kind: str = 'arc'
    amount: float = 30.0            # % de la hauteur (trapèze : % de la largeur)
    tolerance: float = 0.005        # mm
    sides: list | None = None       # enveloppe par courbes (kind 'courbes') : côtés rapportés à la boîte des objets
    turn: int = 0                   # … et quarts de tour de leur rangement

    @classmethod
    def from_dict(cls, d: dict) -> 'EnvelopeSpec':
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        return asdict(self)


def mapping(spec: EnvelopeSpec, bbox):
    """Fonction (x, y) → (x', y') de la déformation sur la boîte `bbox`."""
    if spec.kind == 'courbes':
        from .coons import mapping as patch_mapping
        return patch_mapping(spec.sides, spec.turn, bbox)
    x0, y0, x1, y1 = bbox
    w, h = max(x1 - x0, 1e-9), max(y1 - y0, 1e-9)
    k = spec.amount / 100.0
    xc = (x0 + x1) / 2
    kind = spec.kind

    def f(p):
        x, y = p
        u, v = (x - x0) / w, (y - y0) / h
        bump = 1.0 - (2 * u - 1) ** 2            # 0 aux bords, 1 au milieu
        if kind == 'arc':
            return x, y + k * h * bump
        if kind == 'arche':
            return x, y + v * k * h * bump
        if kind == 'bombe':
            return x, y + (2 * v - 1) * k * h * bump
        if kind == 'pince':
            return x, y - (2 * v - 1) * k * h * bump
        if kind == 'vague':
            return x, y + k * h * math.sin(2 * math.pi * u)
        if kind == 'trapeze':
            return xc + (x - xc) * (1 - k * v), y
        if kind == 'arc_bas':                            # le bas s'arrondit, le haut reste droit
            return x, y - (1 - v) * k * h * bump
        if kind == 'coquille_bas':                       # coins du bas tirés vers le bas
            return x, y - (1 - v) * k * h * (1 - bump)
        if kind == 'coquille_haut':                      # coins du haut tirés vers le haut
            return x, y + v * k * h * (1 - bump)
        if kind == 'drapeau':                            # ondule de plus en plus vers la droite
            return x, y + k * h * u * math.sin(2 * math.pi * u)
        if kind == 'poisson':                            # corps renflé, queue pincée
            return x, y + (2 * v - 1) * k * h * 0.5 * math.sin(1.5 * math.pi * u)
        if kind == 'montee':                             # tout monte vers la droite, en douceur
            return x, y + k * h * u * u
        bump_v = 1.0 - (2 * v - 1) ** 2
        side = min(w, h)                                 # les côtés bougent autant que le haut et le bas
        if kind == 'gonfler':
            return x + (2 * u - 1) * k * side * 0.5 * bump_v, y + (2 * v - 1) * k * h * 0.5 * bump
        if kind == 'compresser':
            return x + (2 * u - 1) * k * side * 0.5 * bump_v, y - (2 * v - 1) * k * h * 0.5 * bump
        cx, cy = xc, (y0 + y1) / 2
        dx, dy = (x - cx) / (w / 2), (y - cy) / (h / 2)
        r = min(1.0, math.hypot(dx, dy) / math.sqrt(2))
        rr = min(1.0, math.hypot(x - cx, y - cy) / (side / 2))
        if kind == 'oeil':                               # grossit le centre
            g = 1 + k * (1 - r * r)
            return cx + (x - cx) * g, cy + (y - cy) * g
        if kind == 'torsion':                            # tourne d'autant plus près du centre
            a = k * math.pi * (1 - rr) ** 2
            ca, sa = math.cos(a), math.sin(a)
            return cx + (x - cx) * ca - (y - cy) * sa, cy + (x - cx) * sa + (y - cy) * ca
        return x, y
    return f


def _jac(f, p, eps=1e-6):
    a, b = f((p[0] + eps, p[1])), f((p[0] - eps, p[1]))
    c, d = f((p[0], p[1] + eps)), f((p[0], p[1] - eps))
    return ((a[0] - b[0]) / (2 * eps), (c[0] - d[0]) / (2 * eps),
            (a[1] - b[1]) / (2 * eps), (c[1] - d[1]) / (2 * eps))


def _deriv(seg, t):
    if isinstance(seg, Line):
        return seg.p1[0] - seg.p0[0], seg.p1[1] - seg.p0[1]
    p0, p1, p2, p3 = seg.p0, seg.p1, seg.p2, seg.p3
    u = 1 - t
    return (3 * (u * u * (p1[0] - p0[0]) + 2 * u * t * (p2[0] - p1[0]) + t * t * (p3[0] - p2[0])),
            3 * (u * u * (p1[1] - p0[1]) + 2 * u * t * (p2[1] - p1[1]) + t * t * (p3[1] - p2[1])))


def _split(seg):
    if isinstance(seg, Line):
        m = seg.point(0.5)
        return Line(seg.p0, m), Line(m, seg.p1)
    return seg.split(0.5)


def _hermite(f, seg) -> Cubic:
    a, b = f(seg.start), f(seg.end)
    da, db = _deriv(seg, 0.0), _deriv(seg, 1.0)
    ja, jb = _jac(f, seg.start), _jac(f, seg.end)
    ta = (ja[0] * da[0] + ja[1] * da[1], ja[2] * da[0] + ja[3] * da[1])
    tb = (jb[0] * db[0] + jb[1] * db[1], jb[2] * db[0] + jb[3] * db[1])
    return Cubic(a, (a[0] + ta[0] / 3, a[1] + ta[1] / 3), (b[0] - tb[0] / 3, b[1] - tb[1] / 3), b)


def _straight(c: Cubic, tol: float):
    ab = (c.p3[0] - c.p0[0], c.p3[1] - c.p0[1])
    L = math.hypot(*ab)
    if L < 1e-12:
        return None
    for q in (c.p1, c.p2):
        if abs(ab[0] * (q[1] - c.p0[1]) - ab[1] * (q[0] - c.p0[0])) / L > tol * 0.01:
            return None
        s = (ab[0] * (q[0] - c.p0[0]) + ab[1] * (q[1] - c.p0[1])) / (L * L)
        if not -1e-9 <= s <= 1 + 1e-9:
            return None
    return Line(c.p0, c.p3)


def map_segment(f, seg, tol: float, depth: int = 0) -> list:
    if isinstance(seg, Conic):
        out = []
        for c in seg.to_cubics(tol / 10):
            out += map_segment(f, c, tol, depth)
        return out
    c = _hermite(f, seg)
    err = max(dist(c.point(u), f(seg.point(u))) for u in (0.25, 0.5, 0.75))
    if err > tol and depth < 14:
        s1, s2 = _split(seg)
        return map_segment(f, s1, tol, depth + 1) + map_segment(f, s2, tol, depth + 1)
    return [_straight(c, tol) or c]


def map_path(path: Path, f, tol: float) -> Path:
    out = []
    for c in path.contours:
        segs = []
        for s in c.segments:
            segs += map_segment(f, s, tol)
        out.append(Contour(segs, c.closed))
    return Path(out)


def _shapes(items) -> list[Shape]:
    out = []

    def walk(it):
        if not getattr(it, 'visible', True):
            return
        if isinstance(it, Group):
            for ch in it.children:
                walk(ch)
        elif isinstance(it, Shape) and it.path.contours:
            out.append(Shape(path=it.path, tool=it.tool, name=it.name))
        elif isinstance(it, Text):
            o = it.outline
            if o is None:
                from .text import outline_for
                o = it.outline = outline_for(it)
            if o:
                out.append(Shape(path=o, tool=it.tool, name=it.text[:20]))
    for it in items:
        walk(it)
    return out


def build(items, spec: EnvelopeSpec) -> Group | None:
    src = _shapes(items)
    if not src:
        return None
    bb = bbox_union([s.path.bbox() for s in src])
    f = mapping(spec, bb)
    tol = max(1e-5, spec.tolerance)
    children = []
    for s in src:
        s.visible = False
        s.extra['envelope_source'] = True
        children.append(s)
    for s in src:
        children.append(Shape(path=map_path(s.path, f, tol), tool=s.tool, name=s.name))
    g = Group(children=children, tool=src[0].tool, name='Enveloppe')
    g.extra['envelope'] = spec.to_dict()
    return g


def build_in_curves(items, sides, turn: int = 0, tolerance: float = 0.005) -> Group | None:
    """Les objets déformés entre les côtés (`coons.sides_of`) ; même groupe re-modifiable."""
    from .coons import normalized
    src = _shapes(items)
    if not src:
        return None
    bb = bbox_union([s.path.bbox() for s in src])
    return build(items, EnvelopeSpec(kind='courbes', tolerance=tolerance, sides=normalized(sides, bb), turn=int(turn)))


def rebuild(g: Group, spec: EnvelopeSpec) -> Group:
    src = [Shape(path=c.path, tool=c.tool, name=c.name) for c in g.children if c.extra.get('envelope_source')]
    return build(src, spec)
