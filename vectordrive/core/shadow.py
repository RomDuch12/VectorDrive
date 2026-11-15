"""Ombrage : ombre d'un objet dans une direction, pour donner du relief à
un texte ou un logo gravé.

- *pleine* (extrusion) : tout ce que balaie l'objet en glissant de la
  distance voulue, moins l'objet ; calculée exactement sur les courbes
  (somme de Minkowski avec un segment : objet, objet décalé et « rubans »
  balayés par chaque morceau de contour, coupé là où sa tangente est
  parallèle à la direction) ;
- *portée* : copie décalée de l'objet, moins l'objet ;
- *éclairage* (TypeEdit : Effet ombrage) : les parties éclairées, dans
  l'objet — le liseré du côté de la lumière (opposé à l'ombre), l'objet
  moins sa copie décalée ; l'écart les rentre dans l'objet.

Un écart laisse un liseré vide entre l'objet et son ombre. Le résultat est
un groupe re-modifiable (objet d'origine + ombre, réglages dans
`extra['shadow']`), comme les hachures.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from . import pathops
from .document import Group, Shape
from .geom import Affine, Conic, Contour, Line, Path

KINDS = ('pleine', 'portee', 'eclairage')


@dataclass
class ShadowSpec:
    kind: str = 'pleine'            # 'pleine' (extrusion), 'portee' (copie décalée), 'eclairage' (liseré éclairé)
    angle: float = -45.0            # direction de l'ombre (°, 0 = vers la droite)
    distance: float = 1.0           # mm
    gap: float = 0.0                # écart entre l'objet et l'ombre (mm)
    keep: bool = True               # garder l'objet avec son ombre

    @classmethod
    def from_dict(cls, d: dict) -> 'ShadowSpec':
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        return asdict(self)

    def vector(self) -> tuple[float, float]:
        a = math.radians(self.angle)
        return round(self.distance * math.cos(a), 12), round(self.distance * math.sin(a), 12)   # 90° : pas de 1e-16


def _cross(a, b) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _monotone_pieces(seg, v) -> list:
    """Morceaux d'un segment dont la tangente ne devient jamais parallèle à v."""
    if isinstance(seg, Line):
        return [seg]
    if isinstance(seg, Conic):
        out = []
        for c in seg.to_cubics(1e-5):
            out.extend(_monotone_pieces(c, v))
        return out
    p0, p1, p2, p3 = seg.p0, seg.p1, seg.p2, seg.p3
    al = _cross((p1[0] - p0[0], p1[1] - p0[1]), v)
    be = _cross((p2[0] - p1[0], p2[1] - p1[1]), v)
    ga = _cross((p3[0] - p2[0], p3[1] - p2[1]), v)
    A, B, C = al - 2 * be + ga, 2 * (be - al), al
    ts = []
    if abs(A) > 1e-12:
        d = B * B - 4 * A * C
        if d >= 0:
            r = math.sqrt(d)
            ts = [(-B - r) / (2 * A), (-B + r) / (2 * A)]
    elif abs(B) > 1e-12:
        ts = [-C / B]
    ts = sorted(t for t in ts if 1e-9 < t < 1 - 1e-9)
    out, cur, done = [], seg, 0.0
    for t in ts:
        a, cur = cur.split((t - done) / (1 - done))
        out.append(a)
        done = t
    out.append(cur)
    return out


def _ribbon(seg, v) -> Contour | None:
    a, b = seg.start, seg.end
    if isinstance(seg, Line) and abs(_cross((b[0] - a[0], b[1] - a[1]), v)) < 1e-12:
        return None                                  # trait parallèle : surface nulle
    m = Affine.translation(*v)
    back = seg.transformed(m).reversed()
    av, bv = m.apply(a), m.apply(b)
    return Contour([seg, Line(b, bv), back, Line(av, a)], True)


def _union_tree(paths: list[Path]) -> Path:
    paths = [p for p in paths if p]
    while len(paths) > 1:
        nxt = [pathops.boolean(paths[i], paths[i + 1], 'union') for i in range(0, len(paths) - 1, 2)]
        if len(paths) % 2:
            nxt.append(paths[-1])
        paths = nxt
    return paths[0] if paths else Path()


def sweep(path: Path, v) -> Path:
    """Région balayée par les contours fermés de `path` glissant de 0 à v."""
    closed = Path([c for c in path.contours if c.closed and c.segments])
    if not closed:
        return Path()
    if math.hypot(*v) < 1e-12:
        return pathops.normalize(closed)
    pieces = [closed, closed.transformed(Affine.translation(*v))]
    ribbons = []
    for c in closed.contours:
        for s in c.segments:
            for piece in _monotone_pieces(s, v):
                r = _ribbon(piece, v)
                if r is not None:
                    ribbons.append(r)
    # rubans orientés dans le même sens puis réunis en un seul appel (règle
    # non nulle) — des milliers d'opérations booléennes en moins
    if ribbons:
        # aire balayée d'un morceau monotone = (fin − début) × v : son signe
        # donne l'orientation du ruban, sans aplatir
        def positive(r):
            a, b = r.segments[0].start, r.segments[0].end
            return (b[0] - a[0]) * v[1] - (b[1] - a[1]) * v[0] >= 0
        oriented = [r if positive(r) else r.reversed() for r in ribbons]
        pieces.append(pathops.normalize(Path(oriented), evenodd=False))
    return _union_tree(pieces)


def shadow_path(source: Path, spec: ShadowSpec) -> Path:
    closed = Path([c for c in source.contours if c.closed and c.segments])
    if not closed or spec.distance <= 0:
        return Path()
    v = spec.vector()
    from .parallel import offset_checked
    if spec.kind == 'eclairage':                     # côté de la lumière : l'objet moins sa copie vers l'ombre
        lit = pathops.boolean(closed, closed.transformed(Affine.translation(*v)), 'difference')
        if spec.gap > 0 and lit.contours:
            inner = offset_checked(closed, -spec.gap)[0]
            lit = pathops.boolean(lit, inner, 'intersect') if inner else Path()
        return lit
    if spec.kind == 'portee':
        region = closed.transformed(Affine.translation(*v))
    else:
        region = sweep(closed, v)
    hole = offset_checked(closed, spec.gap)[0] if spec.gap > 0 else closed     # exact, contrôlé
    return pathops.boolean(region, hole, 'difference')


def build(items, spec: ShadowSpec, tool: int = 0) -> Group | None:
    from .hatch import closed_path
    source = closed_path(items)
    if not source.contours:
        return None
    src = Shape(path=source, tool=tool, name='Objet')
    src.visible = spec.keep
    src.extra['shadow_source'] = True
    sh = Shape(path=shadow_path(source, spec), tool=tool, name='Éclairage' if spec.kind == 'eclairage' else 'Ombre')
    g = Group(children=[src, sh], tool=tool, name='Ombrage')
    g.extra['shadow'] = spec.to_dict()
    return g


def rebuild(g: Group, spec: ShadowSpec) -> Group:
    src = next(c for c in g.children if c.extra.get('shadow_source'))
    return build([Shape(path=src.path, tool=src.tool)], spec, g.tool)
