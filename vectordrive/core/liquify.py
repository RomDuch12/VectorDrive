"""Liquéfier : un pinceau qui déforme les tracés sur son passage (déformer, tordre,
contracter, dilater, festonner, cristalliser, froisser). Champs de déplacement et rythme des
touches d'après VectorCraft (`crates/tools/src/distort/liquify.rs`, MIT), réécrits en numpy.

Le trait du pinceau se découpe en touches régulières. Pour chaque touche, les segments
que le pinceau atteint sont d'abord redécoupés, là où il passe seulement (un long trait
n'hérite pas de mille points pour un coup de pinceau), puis leurs points et poignées suivent
le champ, pondéré par (1 − r²)² dans le pinceau. Ce qu'il n'atteint pas ne change pas :
un trait reste un trait, un arc reste un arc.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .geom import Conic, Contour, Cubic, Line, Path

KINDS = ('warp', 'twirl', 'pucker', 'bloat', 'scallop', 'crystallize', 'wrinkle')
HOLDS = ('twirl', 'pucker', 'bloat')             # pinceau tenu immobile : une touche de plus, à chaque instant
SIMPLIFIES = ('warp', 'twirl', 'pucker', 'bloat')
NOISY = ('scallop', 'crystallize', 'wrinkle')

MAX_DABS = 20_000
MAX_SEGMENTS = 20_000       # segments par contour : au-delà, on ne redécoupe plus
MIN_SPACING = 0.1           # mm
STRAIGHT = 1e-7             # mm : une courbe si plate est un trait


@dataclass
class Params:
    kind: str = 'warp'
    width: float = 20.0         # mm
    height: float = 20.0        # mm
    angle: float = 0.0          # degrés
    intensity: float = 0.5      # 0 à 1
    detail: float = 2.0         # 1 à 10
    simplify: float = 50.0      # 0 à 100
    simplify_on: bool = True
    rate: float = 40.0          # torsion, degrés
    complexity: float = 1.0     # festonner, cristalliser, froisser : 0 à 15
    horizontal: float = 0.0     # froisser : 0 à 1
    vertical: float = 1.0

    @property
    def radii(self) -> tuple:
        return max(self.width, 1e-3) / 2.0, max(self.height, 1e-3) / 2.0

    def dab_spacing(self) -> float:
        rx, ry = self.radii
        return max(min(rx, ry) * 0.2, MIN_SPACING)

    def detail_spacing(self) -> float:
        rx, ry = self.radii
        extra = 1.0 + self.complexity * 0.5 if self.kind in NOISY else 1.0
        return max(min(rx, ry) * 2.0 / (self.detail * 2.0 + 1.0) / extra, MIN_SPACING)

    def tolerance(self) -> float:
        return self.simplify / 100.0 * self.detail_spacing() * 0.02 if self.kind in SIMPLIFIES and self.simplify_on else 0.0

    def falloff(self, c, q: np.ndarray) -> np.ndarray:
        """Le poids des points `q` (…, 2) pour un pinceau centré en `c` (0 dehors)."""
        rx, ry = self.radii
        a = math.radians(-self.angle)
        co, s = math.cos(a), math.sin(a)
        dx, dy = q[..., 0] - c[0], q[..., 1] - c[1]
        u, v = dx * co - dy * s, dx * s + dy * co
        r2 = (u / rx) ** 2 + (v / ry) ** 2
        return np.where(r2 >= 1.0, 0.0, (1.0 - r2) ** 2)

    def reach(self) -> float:
        return max(self.width, self.height) / 2.0


def params_from(values: dict | None) -> Params:
    """Des réglages enregistrés, ramenés à ce qui a du sens."""
    p = Params()
    for k, v in (values or {}).items():
        if hasattr(p, k):
            setattr(p, k, v)
    p.kind = p.kind if p.kind in KINDS else 'warp'
    p.intensity = min(1.0, max(0.0, float(p.intensity)))
    p.detail = min(10.0, max(1.0, float(p.detail)))
    p.simplify = min(100.0, max(0.0, float(p.simplify)))
    p.complexity = min(15.0, max(0.0, float(p.complexity)))
    p.width, p.height = max(0.05, float(p.width)), max(0.05, float(p.height))
    return p


class Dabber:
    """Découpe un trait qui s'allonge en touches régulières ; la première position en est toujours une."""

    def __init__(self, params: Params):
        self.spacing = params.dab_spacing()
        self.holds = params.kind in HOLDS
        self.last = None
        self.carry = 0.0
        self.dabs = []

    def push(self, p) -> list:
        """Une nouvelle position ; rend les nouvelles touches."""
        p = (float(p[0]), float(p[1]))
        new = []
        if self.last is None:
            new.append(p)
        else:
            d = math.dist(self.last, p)
            if d < 1e-9:
                if self.holds and len(self.dabs) < MAX_DABS:
                    new.append(p)
            else:
                run = self.spacing - self.carry
                while run <= d and len(self.dabs) + len(new) < MAX_DABS:
                    t = run / d
                    new.append((self.last[0] + (p[0] - self.last[0]) * t, self.last[1] + (p[1] - self.last[1]) * t))
                    run += self.spacing
                self.carry = (self.carry + d) % self.spacing
        self.last = p
        self.dabs += new
        return new

    def tail(self) -> list:
        """La dernière position, si le geste s'est arrêté entre deux touches : sans elle,
        un geste plus court que l'espacement ne ferait rien du tout."""
        if self.last is None or (self.dabs and math.dist(self.dabs[-1], self.last) < 1e-9):
            return []
        self.dabs.append(self.last)
        self.carry = 0.0
        return [self.last]


def _noise(q: np.ndarray, dab: int, salt: float) -> np.ndarray:
    """Un bruit dans [-1, 1], le même pour un point et sa copie au bout du segment voisin."""
    v = np.sin(q[..., 0] * 12.9898 + q[..., 1] * 78.233 + dab * 37.719 + salt * 3.1) * 43758.5453
    return (v - np.floor(v)) * 2.0 - 1.0


def _anchor_field(p: Params, c, prev, q: np.ndarray, dab: int, salt: float) -> np.ndarray:
    """Où vont les points `q` (…, 2) sous la touche `c`."""
    f = p.falloff(c, q)[..., None]
    i = p.intensity
    cc = np.array(c, dtype=np.float64)
    d = q - cc
    if p.kind == 'warp':
        return q + (cc - np.array(prev, dtype=np.float64)) * (i * f)
    if p.kind == 'twirl':
        a = (math.radians(p.rate) * i * f * 0.25)[..., 0]
        co, s = np.cos(a), np.sin(a)
        return cc + np.stack((d[..., 0] * co - d[..., 1] * s, d[..., 0] * s + d[..., 1] * co), axis=-1)
    if p.kind == 'pucker':
        return q - d * (i * f * 0.2)
    n = np.hypot(d[..., 0], d[..., 1])[..., None]
    unit = np.divide(d, n, out=np.zeros_like(d), where=n > 1e-9)
    r = p.reach()
    if p.kind == 'bloat':
        return q + unit * (i * f * 0.1 * r)
    if p.kind == 'scallop':
        return q - d * (i * f * 0.12)
    if p.kind == 'crystallize':
        return q + unit * (i * f * 0.1 * r * (0.5 + 0.5 * np.abs(_noise(q, dab, salt + 3))[..., None]))
    amp = i * f * 0.06 * r * (1.0 + p.complexity * 0.1)                 # froisser
    wave = np.stack((_noise(q, dab, salt + 11) * p.horizontal, _noise(q, dab, salt + 13) * p.vertical), axis=-1)
    return q + wave * amp


def _handle_field(p: Params, c, prev, h: np.ndarray, old: np.ndarray, new: np.ndarray, dab: int, salt: float) -> np.ndarray:
    """Où vont les poignées `h`, leur point allant de `old` à `new`."""
    if p.kind == 'scallop':                     # elles pivotent et s'allongent : des boucles sur le contour
        f = p.falloff(c, h)
        i = p.intensity
        phi = _noise(h, dab, salt + 7) * (math.pi / 2.0) * i * f * (1.0 + p.complexity * 0.2)
        co, s = np.cos(phi), np.sin(phi)
        v = h - old
        rot = np.stack((v[..., 0] * co - v[..., 1] * s, v[..., 0] * s + v[..., 1] * co), axis=-1)
        return new + rot * (1.0 + 0.6 * i * f)[..., None]
    if p.kind == 'crystallize':                 # elles rentrent : des pointes
        f = p.falloff(c, h)[..., None]
        return new + (h - old) * (1.0 - 0.6 * p.intensity * f)
    return _anchor_field(p, c, prev, h, dab, salt)


def _halves(cp: np.ndarray) -> tuple:
    """Une cubique (4, 2) coupée en son milieu."""
    p01, p12, p23 = (cp[0] + cp[1]) / 2.0, (cp[1] + cp[2]) / 2.0, (cp[2] + cp[3]) / 2.0
    p012, p123 = (p01 + p12) / 2.0, (p12 + p23) / 2.0
    mid = (p012 + p123) / 2.0
    return np.array((cp[0], p01, p012, mid)), np.array((mid, p123, p23, cp[3]))


def _length(cp: np.ndarray) -> float:
    return float(np.hypot(*(cp[1:] - cp[:-1]).T).sum())


def _near(cp: np.ndarray, c, reach: float) -> bool:
    return (cp[:, 0].min() <= c[0] + reach and cp[:, 0].max() >= c[0] - reach and
            cp[:, 1].min() <= c[1] + reach and cp[:, 1].max() >= c[1] - reach)


def _hits(cp: np.ndarray, p: Params, c) -> bool:
    """Le pinceau atteint-il ce morceau de courbe ? Il peut le traverser sans toucher ses bouts :
    on recoupe tant que le morceau passe près et reste long devant le pinceau."""
    reach = p.reach()
    smallest = min(p.radii) * 0.25
    stack = [cp]
    while stack:
        k = stack.pop()
        if not _near(k, c, reach):
            continue
        if np.any(p.falloff(c, k[[0, 3]]) > 0.0):
            return True
        if _length(k) > smallest:
            stack.extend(_halves(k))
    return False


def _refine(cp: np.ndarray, p: Params, c, spacing: float, room: int) -> list:
    """Une cubique, en morceaux plus courts que `spacing` là où le pinceau passe, et entière ailleurs."""
    reach = p.reach()
    out, stack = [], [cp]
    while stack:
        k = stack.pop()
        if len(out) + len(stack) < room and _near(k, c, reach) and _length(k) > spacing:
            a, b = _halves(k)
            stack += [b, a]
        else:
            out.append(k)
    return out


def _boxes(cps: np.ndarray) -> np.ndarray:
    return np.concatenate((cps.min(axis=1), cps.max(axis=1)), axis=1)


def _cubics_of(seg) -> list:
    """Le segment en cubiques (4, 2)."""
    if isinstance(seg, Line):
        a, b = np.array(seg.p0, dtype=np.float64), np.array(seg.p1, dtype=np.float64)
        return [np.array((a, a + (b - a) / 3.0, a + (b - a) * 2.0 / 3.0, b))]
    if isinstance(seg, Cubic):
        return [np.array((seg.p0, seg.p1, seg.p2, seg.p3), dtype=np.float64)]
    if isinstance(seg, Conic):
        return [np.array((s.p0, s.p1, s.p2, s.p3), dtype=np.float64) for s in seg.to_cubics()]
    raise TypeError(type(seg))


def _box_of(seg) -> tuple:
    if isinstance(seg, np.ndarray):
        return seg[:, 0].min(), seg[:, 1].min(), seg[:, 0].max(), seg[:, 1].max()
    pts = seg.controls()
    xs, ys = [q[0] for q in pts], [q[1] for q in pts]
    return min(xs), min(ys), max(xs), max(ys)


class ContourStroke:
    """Un contour sous le pinceau : ses segments d'origine, tant que le pinceau ne les atteint pas,
    et des cubiques (tableaux) dès qu'il les a atteints."""

    def __init__(self, contour: Contour):
        self.closed = contour.closed
        self.items = list(contour.segments)
        self.boxes = np.array([_box_of(s) for s in self.items], dtype=np.float64).reshape(-1, 4)
        self.changed = False

    def _touched(self, c, r: float) -> np.ndarray:
        b = self.boxes
        return np.nonzero((b[:, 0] <= c[0] + r) & (b[:, 2] >= c[0] - r) & (b[:, 1] <= c[1] + r) & (b[:, 3] >= c[1] - r))[0]

    def _subdivide(self, p: Params, c, spacing: float) -> None:
        idx = self._touched(c, p.reach()).tolist()
        if not idx:
            return
        arrays = [i for i in idx if isinstance(self.items[i], np.ndarray)]
        todo = [i for i in idx if not isinstance(self.items[i], np.ndarray)]
        if arrays:
            cps = np.array([self.items[i] for i in arrays])
            lengths = np.hypot(*(cps[:, 1:] - cps[:, :-1]).transpose(2, 0, 1)).sum(axis=1)
            todo += [i for i, n in zip(arrays, lengths) if n > spacing]
            todo.sort()
        items, boxes, last = [], [], 0
        for i in todo:
            seg = self.items[i]
            parts = [seg] if isinstance(seg, np.ndarray) else _cubics_of(seg)
            if not isinstance(seg, np.ndarray) and not any(_hits(cp, p, c) for cp in parts):
                continue
            room = MAX_SEGMENTS - len(self.items) - len(items)
            cut = [piece for cp in parts for piece in _refine(cp, p, c, spacing, room)]
            items.extend(self.items[last:i])
            boxes.append(self.boxes[last:i])
            items.extend(cut)
            boxes.append(_boxes(np.array(cut)))
            last = i + 1
        if boxes:
            items.extend(self.items[last:])
            boxes.append(self.boxes[last:])
            self.items = items
            self.boxes = np.concatenate(boxes, axis=0)

    def dab(self, p: Params, c, prev, rank: int, salt: float) -> None:
        self._subdivide(p, c, p.detail_spacing())
        idx = [i for i in self._touched(c, p.reach()).tolist() if isinstance(self.items[i], np.ndarray)]
        if not idx:
            return
        cps = np.array([self.items[i] for i in idx])
        a0, h0, h1, a1 = cps[:, 0], cps[:, 1], cps[:, 2], cps[:, 3]
        n0 = _anchor_field(p, c, prev, a0, rank, salt)
        n1 = _anchor_field(p, c, prev, a1, rank, salt)
        m0 = _handle_field(p, c, prev, h0, a0, n0, rank, salt + 1)
        m1 = _handle_field(p, c, prev, h1, a1, n1, rank, salt + 2)
        out = np.stack((n0, m0, m1, n1), axis=1)
        # Un même point, au bout de deux segments : les fichiers importés laissent de tout petits écarts,
        # et le bruit, qui dépend de la position, séparerait franchement les deux copies.
        ids = np.array(idx)
        follows = np.nonzero(ids[1:] == ids[:-1] + 1)[0]
        out[follows + 1, 0] = out[follows, 3]
        if self.closed and ids[0] == 0 and ids[-1] == len(self.items) - 1:
            out[0, 0] = out[-1, 3]
        if not np.array_equal(out, cps):
            self.changed = True
        self.boxes[ids] = _boxes(out)
        for k, i in enumerate(idx):
            self.items[i] = out[k]

    def _simplified(self, tol: float) -> list:
        """Sans les points posés à plat entre leurs voisins (tous deux déjà touchés)."""
        items = list(self.items)
        if tol <= 0.0:
            return items
        i = 0
        while i + 1 < len(items):
            a, b = items[i], items[i + 1]
            if isinstance(a, np.ndarray) and isinstance(b, np.ndarray) and _flat(a, b, tol):
                lab = np.hypot(*(b[3] - a[0]))
                lak, lkb = max(np.hypot(*(a[3] - a[0])), 1e-9), max(np.hypot(*(b[3] - a[3])), 1e-9)
                items[i] = np.array((a[0], a[0] + (a[1] - a[0]) * (lab / lak), b[3] + (b[2] - b[3]) * (lab / lkb), b[3]))
                del items[i + 1]
            else:
                i += 1
        return items

    def contour(self, tol: float = 0.0) -> Contour:
        return Contour([_segment(s) if isinstance(s, np.ndarray) else s for s in self._simplified(tol)], self.closed)


def _segment(cp: np.ndarray):
    """Un morceau resté droit redevient un trait."""
    a, b = (float(cp[0][0]), float(cp[0][1])), (float(cp[3][0]), float(cp[3][1]))
    if a != b and np.all(_dist_seg(cp[1:3], cp[0], cp[3]) <= STRAIGHT):
        return Line(a, b)
    return Cubic(a, (float(cp[1][0]), float(cp[1][1])), (float(cp[2][0]), float(cp[2][1])), b)


def _dist_seg(q: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    ab = b - a
    l2 = float(ab @ ab)
    if l2 < 1e-18:
        return np.hypot(*(q - a).T)
    t = np.clip(((q - a) @ ab) / l2, 0.0, 1.0)[:, None]
    return np.hypot(*(q - (a + ab * t)).T)


def _flat(a: np.ndarray, b: np.ndarray, tol: float) -> bool:
    if float((a[3] - a[0]) @ (b[3] - b[0])) <= 0.0:
        return False
    q = np.array((a[1], a[2], a[3], b[1], b[2]))
    return bool(np.all(_dist_seg(q, a[0], b[3]) <= tol))


class PathStroke:
    """Un tracé sous le pinceau : ses contours se déforment au fil des touches."""

    def __init__(self, path: Path, params: Params, salt: float = 0.0):
        self.params = params
        self.salt = salt
        self.contours = [ContourStroke(c) for c in path.contours]
        self.source = path
        self.count = 0
        self.prev = None

    def dab(self, c) -> None:
        prev = self.prev if self.prev is not None else c
        for k, cs in enumerate(self.contours):
            if cs.items:
                cs.dab(self.params, c, prev, self.count, self.salt + k)
        self.prev = c
        self.count += 1

    @property
    def changed(self) -> bool:
        return any(c.changed for c in self.contours)

    def path(self, final: bool = False) -> Path:
        if not self.changed:
            return self.source
        tol = self.params.tolerance() if final else 0.0
        return Path([c.contour(tol) if c.changed else s for c, s in zip(self.contours, self.source.contours)])


def apply(path: Path, points, params: Params, salt: float = 0.0) -> Path:
    """Un trait du pinceau, le long de `points`, sur un tracé."""
    d = Dabber(params)
    stroke = PathStroke(path, params, salt)
    for q in points:
        for c in d.push(q):
            stroke.dab(c)
    for c in d.tail():
        stroke.dab(c)
    return stroke.path(final=True)
