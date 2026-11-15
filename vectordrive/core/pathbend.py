"""Courber le long d'un tracé : le dessin suit une courbe, sa largeur devient
la longueur parcourue, sa hauteur l'écart de part et d'autre du tracé.

Quatre façons de le poser : étiré sur toute la longueur, à sa taille, répété
à la suite, ou répété en remplissant exactement la longueur. Contrairement à
la duplication le long d'une courbe, qui place des copies raides, les objets
sont eux-mêmes déformés.

La déformation n'est pas affine : chaque morceau passe par `envelope.map_segment`
(Bézier d'Hermite coupée tant que l'écart dépasse la tolérance). Dans un coin vif
du tracé, la normale tourne sur une toute petite longueur, pour que le dessin
reste d'un seul tenant ; du côté intérieur du virage il se replie sur lui-même
si le tracé tourne plus serré que sa hauteur (`fold_risk` le signale).

Le résultat est un groupe re-modifiable : objets d'origine et tracé masqués,
objets courbés, réglages dans `extra['path_bend']`.
"""
from __future__ import annotations

import bisect
import math
from dataclasses import asdict, dataclass

from .document import Group, Shape, Text
from .envelope import _deriv, map_segment
from .geom import Conic, Contour, Cubic, Line, Path, bbox_union, dist

MODES = ('etirer', 'garder', 'repeter', 'repeter_etirer')
ALIGNS = ('milieu', 'bas', 'haut')
MAX_COPIES = 1000
CORNER = 0.05                                            # demi-longueur où la normale tourne dans un coin (mm)
CORNER_ANGLE = math.radians(0.5)                         # en dessous, deux morceaux se suivent sans coin
NODE_STEP = 0.25                                         # mm entre deux points de la table sur une courbe
NODES_PER_CURVE = (8, 256)
MIN_TOLERANCE = 1e-5
MIN_HEIGHT = 0.01


@dataclass
class BendSpec:
    mode: str = 'etirer'
    align: str = 'milieu'
    height: float = 100.0                                # % de la hauteur du dessin
    offset: float = 0.0                                  # écart au tracé (mm, + : à gauche du sens)
    start: float = 0.0                                   # départ le long du tracé (mm)
    gap: float = 0.0                                     # entre deux copies (mm)
    flip: bool = False                                   # en miroir, de l'autre côté du tracé
    reverse: bool = False                                # parcourir le tracé dans l'autre sens
    keep_guide: bool = False                             # laisser le tracé dans le dessin
    tolerance: float = 0.005                             # mm

    @classmethod
    def from_dict(cls, d: dict) -> 'BendSpec':
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        return asdict(self)


def _wrap(a: float) -> float:
    """Angle ramené dans ]-π, π]."""
    a = math.fmod(a, 2 * math.pi)
    if a > math.pi:
        a -= 2 * math.pi
    elif a <= -math.pi:
        a += 2 * math.pi
    return a


def _unit(dx: float, dy: float):
    n = math.hypot(dx, dy)
    return (dx / n, dy / n) if n > 1e-12 else None


def _curve_nodes(c: Cubic) -> list:
    """Points et tangentes d'une Bézier, tangente indéfinie (poignée nulle) prise sur la corde voisine."""
    span = dist(c.p0, c.p1) + dist(c.p1, c.p2) + dist(c.p2, c.p3)
    n = max(NODES_PER_CURVE[0], min(NODES_PER_CURVE[1], math.ceil(span / NODE_STEP)))
    pts = [c.point(i / n) for i in range(n + 1)]
    out = []
    for i, p in enumerate(pts):
        t = _unit(*_deriv(c, i / n))
        if t is None:
            a, b = pts[max(0, i - 1)], pts[min(n, i + 1)]
            t = _unit(b[0] - a[0], b[1] - a[1])
        if t is not None:
            out.append((p, t))
    return out


class Guide:
    """Le tracé à suivre, paramétré par la longueur : `point(s)` est dérivable
    (Hermite entre les points de la table), `normal(s)` continue (l'angle
    tourne en ligne droite sur ±CORNER autour des coins vifs). Hors d'un tracé
    ouvert, on continue tout droit ; sur un tracé fermé, on repart du début."""

    def __init__(self, contour: Contour):
        self.closed = bool(contour.closed)
        self.segments = 0
        self.shortest = math.inf
        runs = [[]]                                       # morceaux sans coin : [(s, x, y, tx, ty)]
        s = 0.0
        for seg in contour.segments:
            for piece in (seg.to_cubics(1e-4) if isinstance(seg, Conic) else [seg]):
                if isinstance(piece, Line):
                    t = _unit(piece.p1[0] - piece.p0[0], piece.p1[1] - piece.p0[1])
                    nodes = [(piece.p0, t), (piece.p1, t)] if t is not None else []
                else:
                    nodes = _curve_nodes(piece)
                if len(nodes) < 2:
                    continue
                run = runs[-1]
                if run and abs(_wrap(math.atan2(nodes[0][1][1], nodes[0][1][0]) -
                                     math.atan2(run[-1][4], run[-1][3]))) > CORNER_ANGLE:
                    runs.append([])
                    run = runs[-1]
                length = 0.0
                prev = nodes[0][0]
                for i, (p, t) in enumerate(nodes):
                    length += dist(prev, p)
                    prev = p
                    entry = (s + length, p[0], p[1], t[0], t[1])
                    if i == 0 and run and entry[0] == run[-1][0]:
                        run[-1] = entry                  # raccord sans coin : un seul point
                    else:
                        run.append(entry)
                s += length
                self.segments += 1
                self.shortest = min(self.shortest, length)
        runs = [r for r in runs if r]
        self.length = s
        self.valid = s > 1e-9 and bool(runs)
        if not self.valid:
            return
        self.S, self.X, self.Y, self.TX, self.TY = [], [], [], [], []
        for r in runs:
            for e in r:
                self.S.append(e[0])
                self.X.append(e[1])
                self.Y.append(e[2])
                self.TX.append(e[3])
                self.TY.append(e[4])
        self.corners = len(runs) - 1
        self._angles(runs)
        turning = max(self.A) - min(self.A) if self.A else 0.0
        self.straight = self.corners == 0 and turning < CORNER_ANGLE and not self._seam
        lo, hi = self.length / 2000, self.length / 32
        self.detail = math.inf if self.straight else max(lo, min(hi, self.shortest))

    def _angles(self, runs: list) -> None:
        """Table de l'angle de la normale, coins vifs (couture comprise si fermé) adoucis."""
        n = len(runs)
        spans = [r[-1][0] - r[0][0] for r in runs]
        seam = 0.0
        if self.closed:
            first, last = runs[0][0], runs[-1][-1]
            seam = _wrap(math.atan2(first[4], first[3]) - math.atan2(last[4], last[3]))
        self._seam = self.closed and abs(seam) > CORNER_ANGLE
        half = []                                         # demi-virage après chaque morceau (le dernier : couture)
        for i in range(n):
            nxt = (i + 1) % n
            if i < n - 1 or self._seam:
                half.append(min(CORNER, 0.45 * spans[i], 0.45 * spans[nxt]))
            else:
                half.append(0.0)
        self.SA, self.A = [], []
        offset = 0.0
        for i, r in enumerate(runs):
            ws = half[i - 1] if i > 0 or self._seam else 0.0
            we = half[i]
            raw = [(e[0], math.atan2(e[4], e[3])) for e in r]
            unwrapped = [raw[0]]
            for s_, a in raw[1:]:
                unwrapped.append((s_, unwrapped[-1][1] + _wrap(a - unwrapped[-1][1])))
            S_ = [u[0] for u in unwrapped]
            A_ = [u[1] for u in unwrapped]

            def at(x):
                j = min(len(S_) - 2, max(0, bisect.bisect_right(S_, x) - 1)) if len(S_) > 1 else 0
                if len(S_) < 2 or S_[j + 1] == S_[j]:
                    return A_[j]
                return A_[j] + (A_[j + 1] - A_[j]) * (x - S_[j]) / (S_[j + 1] - S_[j])
            a0, b0 = S_[0] + ws, S_[-1] - we
            nodes = [(a0, at(a0))] + [(x, y) for x, y in zip(S_, A_) if a0 < x < b0] + [(b0, at(b0))]
            if self.SA:
                offset += _wrap(nodes[0][1] + offset - self.A[-1]) - (nodes[0][1] + offset - self.A[-1])
            for x, y in nodes:
                if self.SA and x <= self.SA[-1]:
                    continue
                self.SA.append(x)
                self.A.append(y + offset)
        if self._seam:                                    # les deux moitiés du virage de couture
            w_end, w_start = half[-1], half[-1]
            share = w_end / (w_end + w_start) if w_end + w_start > 0 else 0.5
            delta = _wrap(self.A[0] - self.A[-1])
            self.A.append(self.A[-1] + delta * share)
            self.SA.append(self.length)
            self.A.insert(0, self.A[0] - delta * (1 - share))
            self.SA.insert(0, 0.0)
        if self.SA[0] > 0.0:
            self.SA.insert(0, 0.0)
            self.A.insert(0, self.A[0])
        if self.SA[-1] < self.length:
            self.SA.append(self.length)
            self.A.append(self.A[-1])

    def point(self, s: float) -> tuple[float, float]:
        S = self.S
        if self.closed:
            s = math.fmod(s, self.length)
            if s < 0:
                s += self.length
        elif s <= 0.0:
            return self.X[0] + s * self.TX[0], self.Y[0] + s * self.TY[0]
        elif s >= self.length:
            d = s - self.length
            return self.X[-1] + d * self.TX[-1], self.Y[-1] + d * self.TY[-1]
        i = bisect.bisect_right(S, s) - 1
        i = min(len(S) - 2, max(0, i))
        h = S[i + 1] - S[i]
        if h <= 0:
            return self.X[i], self.Y[i]
        u = (s - S[i]) / h
        u2, u3 = u * u, u * u * u
        a, b, c, d = 2 * u3 - 3 * u2 + 1, (u3 - 2 * u2 + u) * h, 3 * u2 - 2 * u3, (u3 - u2) * h
        return (a * self.X[i] + b * self.TX[i] + c * self.X[i + 1] + d * self.TX[i + 1],
                a * self.Y[i] + b * self.TY[i] + c * self.Y[i + 1] + d * self.TY[i + 1])

    def normal(self, s: float) -> tuple[float, float]:
        """Normale à gauche du sens de parcours."""
        SA, A = self.SA, self.A
        if self.closed:
            s = math.fmod(s, self.length)
            if s < 0:
                s += self.length
        if s <= SA[0]:
            a = A[0]
        elif s >= SA[-1]:
            a = A[-1]
        else:
            j = bisect.bisect_right(SA, s) - 1
            a = A[j] + (A[j + 1] - A[j]) * (s - SA[j]) / (SA[j + 1] - SA[j])
        return -math.sin(a), math.cos(a)

    def min_radius(self) -> float:
        """Plus petit rayon de courbure hors des coins vifs (mm, infini si tout droit)."""
        best = math.inf
        for i in range(len(self.SA) - 1):
            da = abs(self.A[i + 1] - self.A[i])
            ds = self.SA[i + 1] - self.SA[i]
            if da > 1e-9 and ds > 2.5 * CORNER:           # une rampe de coin n'est pas un rayon
                best = min(best, ds / da)
        return best


def _layout(spec: BendSpec, guide: Guide, width: float) -> tuple[int, float]:
    """(nombre de copies, facteur d'échelle en longueur)."""
    if width < 1e-9:
        return 1, 1.0
    gap = spec.gap
    avail = guide.length if guide.closed else guide.length - max(0.0, spec.start)
    if avail <= 0:
        raise ValueError('start')
    if spec.mode == 'etirer':
        return 1, avail / width
    if spec.mode == 'garder':
        return 1, 1.0
    pitch = max(width + gap, 1e-6)
    n = int((avail if guide.closed else avail + gap) / pitch + 1e-9)
    if n > MAX_COPIES:
        raise ValueError('copies')
    n = max(1, n)
    if spec.mode == 'repeter':
        return n, 1.0
    room = avail - (n if guide.closed else n - 1) * gap
    if room <= 0:
        raise ValueError('gap')
    return n, room / (n * width)


def mapping(guide: Guide, spec: BendSpec, box: tuple, copy: int, sx: float):
    """Fonction (x, y) dessin → (x, y) sur le tracé, pour la copie n° `copy`."""
    x0, y0, x1, y1 = box
    ref = {'bas': y0, 'haut': y1}.get(spec.align, (y0 + y1) / 2)
    hs = max(MIN_HEIGHT, abs(spec.height)) / 100 * (-1 if spec.flip else 1)
    base = spec.start + copy * ((x1 - x0) * sx + spec.gap)
    off = spec.offset
    point, normal = guide.point, guide.normal

    def f(p):
        s = base + (p[0] - x0) * sx
        h = (p[1] - ref) * hs + off
        px, py = point(s)
        nx, ny = normal(s)
        return px + h * nx, py + h * ny
    return f


def _presplit(seg, step: float) -> list:
    """Coupe un morceau assez long pour enjamber un détail du tracé, que les
    trois points de contrôle de `map_segment` pourraient ne pas voir."""
    if isinstance(seg, Conic):
        out = []
        for c in seg.to_cubics(1e-4):
            out += _presplit(c, step)
        return out
    if step == math.inf:
        return [seg]
    if isinstance(seg, Line):
        n = math.ceil(abs(seg.p1[0] - seg.p0[0]) / step)
        if n <= 1:
            return [seg]
        pts = [seg.point(i / n) for i in range(n + 1)]
        pts[0], pts[-1] = seg.p0, seg.p1
        return [Line(a, b) for a, b in zip(pts, pts[1:])]
    xs = (seg.p0[0], seg.p1[0], seg.p2[0], seg.p3[0])
    if max(xs) - min(xs) <= step:
        return [seg]
    a, b = seg.split(0.5)
    return _presplit(a, step) + _presplit(b, step)


def _merge_lines(segs: list, tol: float) -> list:
    """Réunit les droites qui se suivent dans le même alignement."""
    out = []
    for s in segs:
        if out and isinstance(s, Line) and isinstance(out[-1], Line):
            a, m, b = out[-1].p0, out[-1].p1, s.p1
            ab = (b[0] - a[0], b[1] - a[1])
            L = math.hypot(*ab)
            if L > 1e-12:
                d = abs(ab[0] * (m[1] - a[1]) - ab[1] * (m[0] - a[0])) / L
                along = (ab[0] * (m[0] - a[0]) + ab[1] * (m[1] - a[1])) / (L * L)
                if d <= tol * 0.01 and 0.0 <= along <= 1.0:
                    out[-1] = Line(a, b)
                    continue
        out.append(s)
    return out


def bend_path(path: Path, f, step: float, tol: float) -> Path:
    out = []
    for c in path.contours:
        segs = []
        for s in c.segments:
            for piece in _presplit(s, step):
                segs += map_segment(f, piece, tol)
        out.append(Contour(_merge_lines(segs, tol), c.closed))
    return Path(out)


def _sources(items) -> list[Shape]:
    """Les objets à courber (textes en contours), sans ce qui est masqué."""
    out = []

    def walk(it):
        if not getattr(it, 'visible', True):
            return
        if isinstance(it, Group):
            for ch in it.children:
                walk(ch)
        elif isinstance(it, Shape) and it.path.contours:
            out.append(Shape(path=it.path, tool=it.tool, name=it.name, filled=it.filled))
        elif isinstance(it, Text):
            o = it.outline
            if o is None:
                from .text import outline_for
                o = it.outline = outline_for(it)
            if o and o.contours:
                out.append(Shape(path=o, tool=it.tool, name=it.text[:20]))
    for it in items:
        walk(it)
    return out


def _oriented(contour: Contour, spec: BendSpec) -> Contour:
    return contour.reversed() if spec.reverse else contour


def fold_risk(items, contour: Contour, spec: BendSpec) -> tuple[float, float] | None:
    """(rayon le plus petit, plus grand écart au tracé) si le dessin risque de se
    replier dans un virage, sinon None. Un coin vif compte pour un rayon nul."""
    src = _sources(items)
    if not src:
        return None
    box = bbox_union([s.path.bbox() for s in src])
    guide = Guide(_oriented(contour, spec))
    if not guide.valid or guide.straight:
        return None
    ref = {'bas': box[1], 'haut': box[3]}.get(spec.align, (box[1] + box[3]) / 2)
    hs = max(MIN_HEIGHT, abs(spec.height)) / 100
    reach = max(abs((box[1] - ref) * hs + spec.offset), abs((box[3] - ref) * hs + spec.offset))
    radius = 0.0 if guide.corners or guide._seam else guide.min_radius()
    return (radius, reach) if reach > radius else None


def build(items, guide_item: Shape, spec: BendSpec) -> Group | None:
    """Groupe du dessin courbé, None s'il n'y a rien à courber. ValueError si les
    réglages ne tiennent pas sur le tracé (départ, écart, trop de copies)."""
    src = _sources(items)
    if not src or not guide_item.path.contours:
        return None
    guide = Guide(_oriented(guide_item.path.contours[0], spec))
    if not guide.valid:
        return None
    box = bbox_union([s.path.bbox() for s in src])
    count, sx = _layout(spec, guide, box[2] - box[0])
    tol = max(MIN_TOLERANCE, spec.tolerance)
    step = guide.detail / max(sx, 1e-9)
    children = []
    for s in src:
        s.visible = False
        s.extra['bend_source'] = True
        children.append(s)
    hidden = Shape(path=Path([guide_item.path.contours[0]]), tool=guide_item.tool, name=guide_item.name, visible=False)
    hidden.extra['bend_guide'] = True
    children.append(hidden)
    for k in range(count):
        f = mapping(guide, spec, box, k, sx)
        for s in src:
            children.append(Shape(path=bend_path(s.path, f, step, tol), tool=s.tool, name=s.name, filled=s.filled))
    g = Group(children=children, tool=src[0].tool, name='Courbé le long du tracé')
    g.extra['path_bend'] = spec.to_dict()
    return g


def rebuild(g: Group, spec: BendSpec) -> Group | None:
    src = [Shape(path=c.path, tool=c.tool, name=c.name, filled=c.filled) for c in g.children if c.extra.get('bend_source')]
    guides = [c for c in g.children if c.extra.get('bend_guide')]
    if not src or not guides:
        return None
    return build(src, guides[0], spec)
