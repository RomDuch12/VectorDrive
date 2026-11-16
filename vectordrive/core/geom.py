"""Géométrie exacte : segments, contours, tracés.

Toutes les longueurs sont en **millimètres**, repère mathématique : X vers
la droite, **Y vers le haut** (celui de TypeEdit et des machines).

Trois sortes de segments suffisent à tout représenter sans approximation :

| Segment | Usage |
|---|---|
| `Line`  | droites, polylignes |
| `Cubic` | Bézier cubiques (SVG, PDF, PostScript, polices OTF) |
| `Conic` | coniques rationnelles quadratiques : Bézier quadratiques (w = 1, polices TTF) et **arcs de cercle ou d'ellipse exacts** (w = cos(θ/2)) |

TypeEdit range ses arcs exactement ainsi : des points (x, y, z, w) dont le
poids vaut 0,7071 pour un quart de cercle. Garder la conique, plutôt que
d'aplatir l'arc en segments, conserve la cote d'un perçage et permet de
réécrire le fichier à l'identique. On n'aplatit qu'au moment de dessiner
à l'écran ou d'exporter vers un format qui l'exige.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Iterator, Sequence

Point = tuple[float, float]

#: Tolérance d'aplatissement par défaut (écart corde/courbe), en mm.
TOLERANCE = 0.01
#: En deçà, deux points sont confondus.
EPS = 1e-9


# --- transformations affines -------------------------------------------------

@dataclass(frozen=True)
class Affine:
    """Matrice affine 2D, convention PDF/SVG : (a, b, c, d, e, f).

    x' = a·x + c·y + e
    y' = b·x + d·y + f
    """
    a: float = 1.0
    b: float = 0.0
    c: float = 0.0
    d: float = 1.0
    e: float = 0.0
    f: float = 0.0

    @staticmethod
    def translation(dx: float, dy: float) -> 'Affine':
        return Affine(1, 0, 0, 1, dx, dy)

    @staticmethod
    def scaling(sx: float, sy: float | None = None,
                center: Point = (0.0, 0.0)) -> 'Affine':
        sy = sx if sy is None else sy
        cx, cy = center
        return Affine(sx, 0, 0, sy, cx - sx * cx, cy - sy * cy)

    @staticmethod
    def fit(box, frame, margin: float = 0.0, stretch: bool = False) -> 'Affine':
        """Transformation qui met la boîte `box` (x0, y0, x1, y1) dans le cadre
        `frame` diminué de `margin` de chaque côté, centrée : à l'échelle (le
        plus grand qui tienne, proportions gardées) ou étirée (`stretch`)."""
        fx0, fy0, fx1, fy1 = frame[0] + margin, frame[1] + margin, frame[2] - margin, frame[3] - margin
        bw, bh = box[2] - box[0], box[3] - box[1]
        if fx1 - fx0 <= 0 or fy1 - fy0 <= 0:
            raise ValueError('marge plus grande que le cadre')
        sx = (fx1 - fx0) / bw if bw > 1e-12 else None
        sy = (fy1 - fy0) / bh if bh > 1e-12 else None
        if not stretch or sx is None or sy is None:
            s = min(v for v in (sx, sy) if v is not None) if (sx or sy) else 1.0
            sx = sy = s
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        return Affine(sx, 0, 0, sy, (fx0 + fx1) / 2 - sx * cx, (fy0 + fy1) / 2 - sy * cy)

    @staticmethod
    def rotation(angle_deg: float, center: Point = (0.0, 0.0)) -> 'Affine':
        t = math.radians(angle_deg)
        co, si = math.cos(t), math.sin(t)
        cx, cy = center
        return Affine(co, si, -si, co,
                      cx - co * cx + si * cy, cy - si * cx - co * cy)

    @staticmethod
    def mirror_x(axis_y: float = 0.0) -> 'Affine':
        """Symétrie par rapport à la droite horizontale y = axis_y."""
        return Affine(1, 0, 0, -1, 0, 2 * axis_y)

    @staticmethod
    def mirror_y(axis_x: float = 0.0) -> 'Affine':
        """Symétrie par rapport à la droite verticale x = axis_x."""
        return Affine(-1, 0, 0, 1, 2 * axis_x, 0)

    @staticmethod
    def reflection(p: 'Point', q: 'Point') -> 'Affine':
        """Symétrie par rapport à la droite passant par p et q."""
        dx, dy = q[0] - p[0], q[1] - p[1]
        n = math.hypot(dx, dy)
        if n < 1e-15:
            raise ValueError('axe de symétrie dégénéré')
        ux, uy = dx / n, dy / n
        a, b = ux * ux - uy * uy, 2 * ux * uy
        c, d = b, uy * uy - ux * ux
        return Affine(a, b, c, d, p[0] - (a * p[0] + c * p[1]), p[1] - (b * p[0] + d * p[1]))

    def __matmul__(self, o: 'Affine') -> 'Affine':
        """`self @ o` : applique d'abord `o`, puis `self`."""
        return Affine(
            self.a * o.a + self.c * o.b,
            self.b * o.a + self.d * o.b,
            self.a * o.c + self.c * o.d,
            self.b * o.c + self.d * o.d,
            self.a * o.e + self.c * o.f + self.e,
            self.b * o.e + self.d * o.f + self.f,
        )

    def apply(self, p: Point) -> Point:
        x, y = p
        return (self.a * x + self.c * y + self.e,
                self.b * x + self.d * y + self.f)

    def inverse(self) -> 'Affine':
        det = self.a * self.d - self.b * self.c
        if abs(det) < 1e-300:
            raise ZeroDivisionError('matrice non inversible')
        a, b, c, d = self.d / det, -self.b / det, -self.c / det, self.a / det
        return Affine(a, b, c, d,
                      -(a * self.e + c * self.f), -(b * self.e + d * self.f))

    @property
    def scale_factor(self) -> float:
        """Facteur d'échelle moyen (racine du déterminant)."""
        return math.sqrt(abs(self.a * self.d - self.b * self.c))

    @property
    def is_identity(self) -> bool:
        return self == Affine()

    def to_tuple(self) -> tuple[float, ...]:
        return (self.a, self.b, self.c, self.d, self.e, self.f)


IDENTITY = Affine()


# --- outils ------------------------------------------------------------------

def dist(p: Point, q: Point) -> float:
    return math.hypot(q[0] - p[0], q[1] - p[1])


def lerp(p: Point, q: Point, t: float) -> Point:
    return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)


def _seg_dist(p: Point, a: Point, b: Point) -> float:
    """Distance du point p au segment [a, b]."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dy * dy
    if l2 < EPS * EPS:
        return dist(p, a)
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2))
    return dist(p, (a[0] + t * dx, a[1] + t * dy))


# --- segments ----------------------------------------------------------------

class Segment:
    """Base commune. Un segment est immuable."""
    __slots__ = ()
    kind = '?'

    @property
    def start(self) -> Point:
        raise NotImplementedError

    @property
    def end(self) -> Point:
        raise NotImplementedError

    def controls(self) -> tuple[Point, ...]:
        """Tous les points définissant le segment, départ et arrivée compris."""
        raise NotImplementedError

    def point(self, t: float) -> Point:
        raise NotImplementedError

    def transformed(self, m: Affine) -> 'Segment':
        raise NotImplementedError

    def reversed(self) -> 'Segment':
        raise NotImplementedError

    def flatten(self, tol: float = TOLERANCE) -> list[Point]:
        """Points de l'aplatissement, **sans** le point de départ."""
        raise NotImplementedError

    def length(self, tol: float = TOLERANCE / 10) -> float:
        pts = [self.start] + self.flatten(tol)
        return sum(dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))

    def bbox(self) -> tuple[float, float, float, float]:
        pts = [self.start] + self.flatten(TOLERANCE / 10)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return min(xs), min(ys), max(xs), max(ys)


@dataclass(frozen=True, slots=True)
class Line(Segment):
    p0: Point
    p1: Point
    kind = 'L'

    @property
    def start(self) -> Point:
        return self.p0

    @property
    def end(self) -> Point:
        return self.p1

    def controls(self):
        return (self.p0, self.p1)

    def point(self, t: float) -> Point:
        return lerp(self.p0, self.p1, t)

    def transformed(self, m: Affine) -> 'Line':
        return Line(m.apply(self.p0), m.apply(self.p1))

    def reversed(self) -> 'Line':
        return Line(self.p1, self.p0)

    def flatten(self, tol: float = TOLERANCE) -> list[Point]:
        return [self.p1]

    def length(self, tol: float = 0.0) -> float:
        return dist(self.p0, self.p1)

    def bbox(self):
        (x0, y0), (x1, y1) = self.p0, self.p1
        return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


@dataclass(frozen=True, slots=True)
class Cubic(Segment):
    p0: Point
    p1: Point
    p2: Point
    p3: Point
    kind = 'C'

    @property
    def start(self) -> Point:
        return self.p0

    @property
    def end(self) -> Point:
        return self.p3

    def controls(self):
        return (self.p0, self.p1, self.p2, self.p3)

    def point(self, t: float) -> Point:
        u = 1 - t
        a, b, c, d = u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t
        return (a * self.p0[0] + b * self.p1[0] + c * self.p2[0] + d * self.p3[0],
                a * self.p0[1] + b * self.p1[1] + c * self.p2[1] + d * self.p3[1])

    def split(self, t: float) -> tuple['Cubic', 'Cubic']:
        p01 = lerp(self.p0, self.p1, t)
        p12 = lerp(self.p1, self.p2, t)
        p23 = lerp(self.p2, self.p3, t)
        p012 = lerp(p01, p12, t)
        p123 = lerp(p12, p23, t)
        m = lerp(p012, p123, t)
        return Cubic(self.p0, p01, p012, m), Cubic(m, p123, p23, self.p3)

    def transformed(self, m: Affine) -> 'Cubic':
        return Cubic(*(m.apply(p) for p in self.controls()))

    def length(self, tol: float = 0.0) -> float:
        return _cubic_length(self)

    def reversed(self) -> 'Cubic':
        return Cubic(self.p3, self.p2, self.p1, self.p0)

    def _flat_enough(self, tol: float) -> bool:
        return max(_seg_dist(self.p1, self.p0, self.p3),
                   _seg_dist(self.p2, self.p0, self.p3)) <= tol

    def flatten(self, tol: float = TOLERANCE) -> list[Point]:
        out: list[Point] = []
        pile = [(self, 0)]
        while pile:
            seg, depth = pile.pop()
            if depth >= 16 or seg._flat_enough(tol):
                out.append(seg.p3)
            else:
                a, b = seg.split(0.5)
                pile.append((b, depth + 1))
                pile.append((a, depth + 1))
        return out

    def bbox(self):
        """Encombrement exact : extrema de la dérivée."""
        xs = [self.p0[0], self.p3[0]]
        ys = [self.p0[1], self.p3[1]]
        for i, acc in ((0, xs), (1, ys)):
            a, b, c, d = (self.p0[i], self.p1[i], self.p2[i], self.p3[i])
            # dérivée / 3 : (b-a)(1-t)² + 2(c-b)(1-t)t + (d-c)t²
            qa = -a + 3 * b - 3 * c + d
            qb = 2 * (a - 2 * b + c)
            qc = b - a
            for t in _quad_roots(qa, qb, qc):
                if 0 < t < 1:
                    acc.append(self.point(t)[i])
        return min(xs), min(ys), max(xs), max(ys)


# Gauss-Legendre à 8 points sur [0, 1] : abscisses et poids.
_GL_X = (0.0198550717512319, 0.1016667612931866, 0.2372337950418355, 0.4082826787521751,
         0.5917173212478249, 0.7627662049581645, 0.8983332387068134, 0.9801449282487681)
_GL_W = (0.0506142681451881, 0.1111905172266872, 0.1568533229389436, 0.1813418916891810,
         0.1813418916891810, 0.1568533229389436, 0.1111905172266872, 0.0506142681451881)


def _integrate_speed(speed, pieces: int = 16) -> float:
    """∫₀¹ |P'(t)| dt par Gauss-Legendre composite (erreur ~1e-12 mm sur
    les courbes usuelles)."""
    total = 0.0
    h = 1.0 / pieces
    for k in range(pieces):
        a = k * h
        total += h * sum(w * speed(a + h * x) for x, w in zip(_GL_X, _GL_W))
    return total


def _cubic_length(s: 'Cubic') -> float:
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = s.p0, s.p1, s.p2, s.p3

    def speed(t):
        u = 1 - t
        dx = 3 * (u * u * (x1 - x0) + 2 * u * t * (x2 - x1) + t * t * (x3 - x2))
        dy = 3 * (u * u * (y1 - y0) + 2 * u * t * (y2 - y1) + t * t * (y3 - y2))
        return math.hypot(dx, dy)
    return _integrate_speed(speed)


def batch_lengths(segs) -> list[float]:
    """Longueurs exactes d'une liste de segments, calculées ensemble :
    même Gauss-Legendre composite que `length()`, vectorisé (numpy). Sur un
    gros dessin (75 000 cubiques), 12,8 s → quelques dixièmes."""
    import numpy as np
    out = [0.0] * len(segs)
    cub, cub_i, con, con_i = [], [], [], []
    for i, sg in enumerate(segs):
        if isinstance(sg, Line):
            out[i] = math.dist(sg.p0, sg.p1)
        elif isinstance(sg, Cubic):
            cub_i.append(i)
            cub.append((*sg.p0, *sg.p1, *sg.p2, *sg.p3))
        elif isinstance(sg, Conic):
            arc = sg.circle_params()
            if arc:
                out[i] = arc[1] * math.radians(abs(arc[3]))
            else:
                con_i.append(i)
                con.append((*sg.p0, *sg.p1, *sg.p2, sg.w))
        else:
            out[i] = sg.length()
    if not cub and not con:
        return out
    pieces = 16
    T = np.array([(k + x) / pieces for k in range(pieces) for x in _GL_X])
    W = np.array([w / pieces for _k in range(pieces) for w in _GL_W])
    U = 1 - T
    if cub:
        C = np.array(cub)
        x0, y0, x1, y1, x2, y2, x3, y3 = (C[:, k:k + 1] for k in range(8))
        dx = 3 * (U * U * (x1 - x0) + 2 * U * T * (x2 - x1) + T * T * (x3 - x2))
        dy = 3 * (U * U * (y1 - y0) + 2 * U * T * (y2 - y1) + T * T * (y3 - y2))
        for i, v in zip(cub_i, (np.hypot(dx, dy) * W).sum(1)):
            out[i] = float(v)
    if con:
        C = np.array(con)
        x0, y0, x1, y1, x2, y2, w = (C[:, k:k + 1] for k in range(7))
        b0, b1, b2 = U * U, 2 * U * T * w, T * T
        db0, db1, db2 = -2 * U, 2 * w * (1 - 2 * T), 2 * T
        D = b0 + b1 + b2
        dD = db0 + db1 + db2
        Nx, Ny = b0 * x0 + b1 * x1 + b2 * x2, b0 * y0 + b1 * y1 + b2 * y2
        dNx, dNy = db0 * x0 + db1 * x1 + db2 * x2, db0 * y0 + db1 * y1 + db2 * y2
        sp = np.hypot(dNx * D - Nx * dD, dNy * D - Ny * dD) / (D * D)
        for i, v in zip(con_i, (sp * W).sum(1)):
            out[i] = float(v)
    return out


def _memo(obj, name: str, key, fn):
    """Résultat mis en cache sur l'objet tant que `key` ne change pas
    (les chemins ne sont jamais modifiés en place : toute transformation
    en crée de nouveaux)."""
    cache = obj.__dict__.setdefault('_memo', {})
    hit = cache.get(name)
    if hit is not None and hit[0] == key:
        return hit[1]
    v = fn()
    cache[name] = (key, v)
    return v


def _state_without_memo(obj) -> dict:
    """État d'un objet pour pickle, sans ses résultats mis en cache : deux
    chemins égaux ont la même empreinte (mémoire des parcours FAO), et les
    clés du cache (identités d'objets) n'auraient pas de sens ailleurs."""
    d = dict(obj.__dict__)
    d.pop('_memo', None)
    return d


def _conic_length(s: 'Conic') -> float:
    arc = s.circle_params()
    if arc:
        return arc[1] * math.radians(abs(arc[3]))
    (x0, y0), (x1, y1), (x2, y2), w = s.p0, s.p1, s.p2, s.w

    def speed(t):
        u = 1 - t
        b0, b1, b2 = u * u, 2 * u * t * w, t * t
        db0, db1, db2 = -2 * u, 2 * w * (1 - 2 * t), 2 * t
        D = b0 + b1 + b2
        dD = db0 + db1 + db2
        Nx = b0 * x0 + b1 * x1 + b2 * x2
        Ny = b0 * y0 + b1 * y1 + b2 * y2
        dNx = db0 * x0 + db1 * x1 + db2 * x2
        dNy = db0 * y0 + db1 * y1 + db2 * y2
        return math.hypot(dNx * D - Nx * dD, dNy * D - Ny * dD) / (D * D)
    return _integrate_speed(speed)


def _quad_roots(a: float, b: float, c: float) -> list[float]:
    if abs(a) < 1e-12:
        return [] if abs(b) < 1e-12 else [-c / b]
    disc = b * b - 4 * a * c
    if disc < 0:
        return []
    r = math.sqrt(disc)
    return [(-b + r) / (2 * a), (-b - r) / (2 * a)]


@dataclass(frozen=True, slots=True)
class Conic(Segment):
    """Bézier rationnelle quadratique : P(t) = Σ wᵢBᵢ(t)Pᵢ / Σ wᵢBᵢ(t),
    avec w₀ = w₂ = 1 et w₁ = w.

    * w = 1 : Bézier quadratique ordinaire (TrueType) ;
    * w < 1 : arc d'ellipse — arc de cercle d'angle θ si le contrôle est
      à l'intersection des tangentes et w = cos(θ/2) ;
    * w > 1 : arc d'hyperbole (rare, jamais produit par nous).

    Une transformation affine conserve w : un arc reste exact sous
    rotation, échelle ou cisaillement (il devient arc d'ellipse).
    """
    p0: Point
    p1: Point
    p2: Point
    w: float = 1.0
    kind = 'Q'

    @property
    def start(self) -> Point:
        return self.p0

    @property
    def end(self) -> Point:
        return self.p2

    def controls(self):
        return (self.p0, self.p1, self.p2)

    def point(self, t: float) -> Point:
        u = 1 - t
        b0, b1, b2 = u * u, 2 * u * t * self.w, t * t
        s = b0 + b1 + b2
        return ((b0 * self.p0[0] + b1 * self.p1[0] + b2 * self.p2[0]) / s,
                (b0 * self.p0[1] + b1 * self.p1[1] + b2 * self.p2[1]) / s)

    def split(self) -> tuple['Conic', 'Conic']:
        """Coupe au paramètre milieu (subdivision exacte des coniques)."""
        w = self.w
        x0, y0 = self.p0
        x1, y1 = self.p1
        x2, y2 = self.p2
        # coordonnées homogènes
        a = ((x0 + w * x1) / (1 + w), (y0 + w * y1) / (1 + w))
        b = ((w * x1 + x2) / (1 + w), (w * y1 + y2) / (1 + w))
        m = ((x0 + 2 * w * x1 + x2) / (2 + 2 * w),
             (y0 + 2 * w * y1 + y2) / (2 + 2 * w))
        nw = math.sqrt((1 + w) / 2)
        return Conic(self.p0, a, m, nw), Conic(m, b, self.p2, nw)

    def transformed(self, m: Affine) -> 'Conic':
        return Conic(m.apply(self.p0), m.apply(self.p1), m.apply(self.p2), self.w)

    def reversed(self) -> 'Conic':
        return Conic(self.p2, self.p1, self.p0, self.w)

    def length(self, tol: float = 0.0) -> float:
        return _conic_length(self)

    def bbox(self):
        """Encombrement exact. Coordonnée x(t) = N(t)/D(t) avec N, D du
        second degré : x'(t) = 0 ⇔ N'D − ND' = 0, polynôme du second degré
        (les termes en t³ s'annulent), résolu analytiquement."""
        (x0, y0), (x2, y2) = self.p0, self.p2
        w = self.w
        xs, ys = [x0, x2], [y0, y2]
        d0, d1, d2 = 1.0, 2 * w - 2, 2 - 2 * w
        for i, acc in ((0, xs), (1, ys)):
            a0, a1, a2 = self.p0[i], self.p1[i], self.p2[i]
            n0, n1, n2 = a0, 2 * w * a1 - 2 * a0, a0 - 2 * w * a1 + a2
            A = n2 * d1 - n1 * d2
            B = 2 * (n2 * d0 - n0 * d2)
            C = n1 * d0 - n0 * d1
            scale = max(abs(A), abs(B), abs(C), 1e-300)
            if abs(A) <= 1e-14 * scale:
                roots = [-C / B] if abs(B) > 1e-14 * scale else []
            else:
                disc = B * B - 4 * A * C
                if disc < 0:
                    roots = []
                else:
                    sq = math.sqrt(disc)
                    q = -0.5 * (B + math.copysign(sq, B))
                    roots = [q / A] + ([C / q] if q != 0 else [])
            for t in roots:
                if 0 < t < 1:
                    acc.append(self.point(t)[i])
        return min(xs), min(ys), max(xs), max(ys)

    def flatten(self, tol: float = TOLERANCE) -> list[Point]:
        out: list[Point] = []
        pile = [(self, 0)]
        while pile:
            seg, depth = pile.pop()
            m = seg.point(0.5)
            if depth >= 16 or _seg_dist(m, seg.p0, seg.p2) <= tol and \
                    _seg_dist(seg.point(0.25), seg.p0, seg.p2) <= tol:
                out.append(seg.p2)
            else:
                a, b = seg.split()
                pile.append((b, depth + 1))
                pile.append((a, depth + 1))
        return out

    def to_cubics(self, tol: float = 1e-4) -> list[Cubic]:
        """Approximation par cubiques, pour les formats qui n'ont pas de
        coniques (SVG, PDF). Exacte si w = 1 ; sinon subdivisée jusqu'à
        un écart < tol (0,1 µm par défaut)."""
        if abs(self.w - 1.0) < 1e-12:
            p0, p1, p2 = self.p0, self.p1, self.p2
            return [Cubic(p0, lerp(p0, p1, 2 / 3), lerp(p2, p1, 2 / 3), p2)]
        out: list[Cubic] = []
        pile = [(self, 0)]
        while pile:
            seg, depth = pile.pop()
            c = seg._cubic_guess()
            ok = depth >= 12 or all(
                dist(c.point(t), seg.point(t)) <= tol for t in (0.25, 0.5, 0.75))
            if ok:
                out.append(c)
            else:
                a, b = seg.split()
                pile.append((b, depth + 1))
                pile.append((a, depth + 1))
        return out

    def _cubic_guess(self) -> Cubic:
        # tangentes conservées ; longueur des poignées k = 4w / (3(1+w))
        k = 4 * self.w / (3 * (1 + self.w))
        return Cubic(self.p0, lerp(self.p0, self.p1, k),
                     lerp(self.p2, self.p1, k), self.p2)

    def circle_params(self, tol: float = 1e-7) -> tuple[Point, float, float, float] | None:
        """Si le segment est un arc de cercle : (centre, rayon, angle de
        départ en degrés, balayage signé en degrés). Sinon None."""
        if not 0 < self.w < 1:
            return None
        p0, p1, p2 = self.p0, self.p1, self.p2
        d0, d2 = dist(p0, p1), dist(p2, p1)
        if abs(d0 - d2) > tol * max(1.0, d0):
            return None
        chord = dist(p0, p2)
        if chord < EPS:
            return None
        half = math.acos(max(-1.0, min(1.0, self.w)))      # θ/2
        r = chord / 2 / math.sin(half)
        # centre : le long de la bissectrice, du côté opposé au contrôle
        mx, my = (p0[0] + p2[0]) / 2, (p0[1] + p2[1]) / 2
        vx, vy = mx - p1[0], my - p1[1]
        nv = math.hypot(vx, vy)
        if nv < EPS:
            return None
        h = r * math.cos(half)
        c = (mx + vx / nv * h, my + vy / nv * h)
        if abs(dist(c, p0) - r) > tol * max(1.0, r) or \
                abs(dist(c, p2) - r) > tol * max(1.0, r):
            return None
        a0 = math.degrees(math.atan2(p0[1] - c[1], p0[0] - c[0]))
        cross = (p1[0] - p0[0]) * (p2[1] - p1[1]) - (p1[1] - p0[1]) * (p2[0] - p1[0])
        sweep = math.degrees(2 * half) * (1 if cross > 0 else -1)
        return c, r, a0, sweep


def through_points(pts, closed: bool = False, tension: float = 0.5) -> 'Contour':
    """Courbe lisse qui passe par tous les points (Catmull-Rom centripète,
    en Bézier cubiques) — comme une SPLINE par points de lissage. Fermée :
    elle reboucle sans angle. `tension` 0,5 : tangentes au demi-écart."""
    P = [tuple(p[:2]) for p in pts]
    clean = [P[0]] if P else []
    for p in P[1:]:
        if dist(p, clean[-1]) > 1e-9:
            clean.append(p)
    P = clean
    if closed and len(P) > 2 and dist(P[0], P[-1]) < 1e-9:
        P = P[:-1]
    n = len(P)
    if n < 2:
        return Contour([], closed)
    if n == 2:
        return Contour([Line(P[0], P[1])], False)

    def tangent(i):
        if closed:
            a, b = P[(i - 1) % n], P[(i + 1) % n]
        else:
            a, b = P[max(0, i - 1)], P[min(n - 1, i + 1)]
        return ((b[0] - a[0]) * tension, (b[1] - a[1]) * tension)
    segs = []
    count = n if closed else n - 1
    for i in range(count):
        p0, p1 = P[i], P[(i + 1) % n]
        t0, t1 = tangent(i), tangent((i + 1) % n)
        if not closed and i == 0:                      # bouts libres : tangente vers le point suivant
            t0 = ((p1[0] - p0[0]) * tension, (p1[1] - p0[1]) * tension)
        if not closed and i == count - 1:
            t1 = ((p1[0] - p0[0]) * tension, (p1[1] - p0[1]) * tension)
        segs.append(Cubic(p0, (p0[0] + t0[0] / 1.5, p0[1] + t0[1] / 1.5),
                          (p1[0] - t1[0] / 1.5, p1[1] - t1[1] / 1.5), p1))
    return Contour(segs, closed)


def arc_conics(center: Point, rx: float, ry: float, start_deg: float,
               sweep_deg: float, rotation_deg: float = 0.0) -> list[Conic]:
    """Arc d'ellipse exact en coniques de 90° au plus.

    Balayage positif = sens trigonométrique (anti-horaire, Y vers le haut).
    """
    if abs(sweep_deg) < 1e-12:
        return []
    n = max(1, math.ceil(abs(sweep_deg) / 90.0 - 1e-9))
    step = math.radians(sweep_deg) / n
    w = math.cos(step / 2)
    t = math.radians(start_deg)
    out = []
    # arcs sur le cercle unité, puis transformation affine
    m = Affine.translation(*center) @ Affine.rotation(rotation_deg) @ Affine.scaling(rx, ry)
    for _ in range(n):
        a0, a1 = t, t + step
        p0 = (math.cos(a0), math.sin(a0))
        p2 = (math.cos(a1), math.sin(a1))
        k = 1 / math.cos(step / 2)
        mid = a0 + step / 2
        p1 = (math.cos(mid) * k, math.sin(mid) * k)
        out.append(Conic(m.apply(p0), m.apply(p1), m.apply(p2), w))
        t = a1
    return out


# --- contours et tracés --------------------------------------------------------

@dataclass
class Contour:
    """Suite de segments chaînés. `closed` : le dernier point rejoint le
    premier (par un segment explicite ou implicite)."""
    segments: list[Segment] = field(default_factory=list)
    closed: bool = False

    __getstate__ = _state_without_memo

    def __bool__(self) -> bool:
        return bool(self.segments)

    @property
    def start(self) -> Point:
        return self.segments[0].start

    @property
    def end(self) -> Point:
        return self.segments[-1].end

    def closing_gap(self) -> float:
        return dist(self.start, self.end) if self.segments else 0.0

    def nodes(self) -> list[Point]:
        """Nœuds sur la courbe (extrémités des segments)."""
        if not self.segments:
            return []
        pts = [self.segments[0].start] + [s.end for s in self.segments]
        if self.closed and dist(pts[0], pts[-1]) < 1e-9:
            pts.pop()
        return pts

    def flatten(self, tol: float = TOLERANCE) -> list[Point]:
        if not self.segments:
            return []
        pts = [self.segments[0].start]
        for s in self.segments:
            pts.extend(s.flatten(tol))
        if self.closed and dist(pts[0], pts[-1]) > 1e-9:
            pts.append(pts[0])
        return pts

    def length(self) -> float:
        def compute():
            n = sum(batch_lengths(self.segments)) if len(self.segments) > 16 else \
                sum(s.length() for s in self.segments)
            return n + (self.closing_gap() if self.closed else 0.0)
        return _memo(self, 'length', (id(self.segments), len(self.segments), self.closed), compute)

    def digest(self) -> bytes:
        """Empreinte du contour (segments, fermeture), mise en cache comme
        sa longueur : deux contours égaux ont la même."""
        def compute():
            import hashlib
            import pickle
            return hashlib.blake2b(pickle.dumps((self.segments, self.closed), protocol=pickle.HIGHEST_PROTOCOL),
                                   digest_size=16).digest()
        return _memo(self, 'digest', (id(self.segments), len(self.segments), self.closed), compute)

    def signed_area(self, tol: float = TOLERANCE / 10) -> float:
        """Aire signée (positive si anti-horaire), contour supposé fermé."""
        pts = self.flatten(tol)
        s = 0.0
        for i in range(len(pts) - 1):
            s += pts[i][0] * pts[i + 1][1] - pts[i + 1][0] * pts[i][1]
        if pts and pts[0] != pts[-1]:
            s += pts[-1][0] * pts[0][1] - pts[0][0] * pts[-1][1]
        return s / 2

    def bbox(self):
        """Encombrement exact, mis en cache (comme la longueur : les contours
        ne sont jamais modifiés en place)."""
        def compute():
            x0s, y0s, x1s, y1s = zip(*[s.bbox() for s in self.segments])
            return min(x0s), min(y0s), max(x1s), max(y1s)
        if not self.segments:
            raise ValueError('contour vide')
        return _memo(self, 'bbox', (id(self.segments), len(self.segments)), compute)

    def transformed(self, m: Affine) -> 'Contour':
        # calcul en ligne (sans appel de méthode par point) : les gros
        # dessins comptent des centaines de milliers de segments
        a, b, c, d, e, f = m.a, m.b, m.c, m.d, m.e, m.f
        out = []
        add = out.append
        for s in self.segments:
            t = type(s)
            if t is Line:
                (x0, y0), (x1, y1) = s.p0, s.p1
                add(Line((a * x0 + c * y0 + e, b * x0 + d * y0 + f), (a * x1 + c * y1 + e, b * x1 + d * y1 + f)))
            elif t is Cubic:
                (x0, y0), (x1, y1), (x2, y2), (x3, y3) = s.p0, s.p1, s.p2, s.p3
                add(Cubic((a * x0 + c * y0 + e, b * x0 + d * y0 + f), (a * x1 + c * y1 + e, b * x1 + d * y1 + f),
                          (a * x2 + c * y2 + e, b * x2 + d * y2 + f), (a * x3 + c * y3 + e, b * x3 + d * y3 + f)))
            elif t is Conic:
                (x0, y0), (x1, y1), (x2, y2) = s.p0, s.p1, s.p2
                add(Conic((a * x0 + c * y0 + e, b * x0 + d * y0 + f), (a * x1 + c * y1 + e, b * x1 + d * y1 + f),
                          (a * x2 + c * y2 + e, b * x2 + d * y2 + f), s.w))
            else:
                add(s.transformed(m))
        return Contour(out, self.closed)

    def reversed(self) -> 'Contour':
        return Contour([s.reversed() for s in reversed(self.segments)], self.closed)

    def close(self, tol: float = 1e-6) -> 'Contour':
        """Ferme le contour, en ajoutant une droite si le trou dépasse tol."""
        segs = list(self.segments)
        if segs and dist(self.end, self.start) > tol:
            segs.append(Line(self.end, self.start))
        return Contour(segs, True)

    def opened(self) -> 'Contour':
        return Contour(list(self.segments), False)


@dataclass
class Path:
    """Ensemble de contours (un caractère « o » = deux contours)."""
    contours: list[Contour] = field(default_factory=list)

    __getstate__ = _state_without_memo

    def __bool__(self) -> bool:
        return any(self.contours)

    def _key(self):
        return (id(self.contours), len(self.contours))

    def digest(self) -> bytes:
        """Empreinte du tracé : celles de ses contours (gardées avec eux)."""
        import hashlib
        h = hashlib.blake2b(digest_size=16)
        for c in self.contours:
            h.update(c.digest())
        return h.digest()

    def bbox(self) -> tuple[float, float, float, float] | None:
        def compute():
            bs = [c.bbox() for c in self.contours if c]
            if not bs:
                return None
            return (min(b[0] for b in bs), min(b[1] for b in bs),
                    max(b[2] for b in bs), max(b[3] for b in bs))
        return _memo(self, 'bbox', self._key(), compute)

    def transformed(self, m: Affine) -> 'Path':
        out = Path([c.transformed(m) for c in self.contours])
        memo = self.__dict__.get('_memo', {})
        key, okey = out._key(), self._key()
        new = {}
        hit = memo.get('length')
        if hit is not None and hit[0] == okey:
            # similitude (rotation, symétrie, échelle uniforme) : longueur × k
            n1, n2 = m.a * m.a + m.b * m.b, m.c * m.c + m.d * m.d
            if abs(n1 - n2) <= 1e-12 * max(1.0, n1) and abs(m.a * m.c + m.b * m.d) <= 1e-12 * max(1.0, n1):
                new['length'] = (key, hit[1] * math.sqrt(n1))
        both = memo.get('lengths')
        if both is not None and both[0] == okey:         # (fermés, ouverts) : suivent une similitude de même
            n1, n2 = m.a * m.a + m.b * m.b, m.c * m.c + m.d * m.d
            if abs(n1 - n2) <= 1e-12 * max(1.0, n1) and abs(m.a * m.c + m.b * m.d) <= 1e-12 * max(1.0, n1):
                scale = math.sqrt(n1)
                new['lengths'] = (key, (both[1][0] * scale, both[1][1] * scale))
        hit = memo.get('bbox')
        if hit is not None and hit[0] == okey and hit[1] is not None and m.b == 0 and m.c == 0:
            x0, y0, x1, y1 = hit[1]
            xa, ya = m.apply((x0, y0))
            xb, yb = m.apply((x1, y1))
            new['bbox'] = (key, (min(xa, xb), min(ya, yb), max(xa, xb), max(ya, yb)))
        if new:
            out.__dict__['_memo'] = new
        return out

    def length(self) -> float:
        def compute():
            segs = [sg for c in self.contours for sg in c.segments]
            gaps = sum(c.closing_gap() for c in self.contours if c.closed)
            return sum(batch_lengths(segs)) + gaps
        return _memo(self, 'length', self._key(), compute)

    def lengths(self) -> tuple:
        """(longueur des contours fermés — leur périmètre —, longueur des contours ouverts), gardées avec le tracé.
        Tous les segments calculés ensemble (`batch_lengths`) : des milliers de petits contours — un texte en
        courbes — ne se calculent pas un à un."""
        def compute():
            segs, shut = [], []
            for c in self.contours:
                segs.extend(c.segments)
                shut.extend([bool(c.closed)] * len(c.segments))
            closed = sum(c.closing_gap() for c in self.contours if c.closed)
            opened = 0.0
            for length, is_closed in zip(batch_lengths(segs), shut):
                if is_closed:
                    closed += length
                else:
                    opened += length
            return closed, opened
        return _memo(self, 'lengths', self._key(), compute)

    def segment_count(self) -> int:
        return sum(len(c.segments) for c in self.contours)

    def flatten(self, tol: float = TOLERANCE) -> list[list[Point]]:
        return [c.flatten(tol) for c in self.contours if c]


def bbox_union(boxes: Iterable[tuple[float, float, float, float] | None]):
    boxes = [b for b in boxes if b]
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


# --- fabriques de formes -------------------------------------------------------

def each_matrix(bb, dx: float, dy: float, sx: float, sy: float, angle: float, fx: float = 0.5,
                fy: float = 0.5) -> 'Affine':
    """Transformation d'un objet de cadre `bb` autour de son propre point (fx, fy du cadre) : échelle, rotation, puis
    déplacement."""
    px, py = bb[0] + fx * (bb[2] - bb[0]), bb[1] + fy * (bb[3] - bb[1])
    return (Affine.translation(dx, dy) @ Affine.translation(px, py) @ Affine.rotation(angle)
            @ Affine.scaling(sx, sy) @ Affine.translation(-px, -py))


class PathBuilder:
    """Construit un `Path` au fil de commandes moveTo / lineTo / curveTo,
    comme le font les lecteurs SVG, PDF et PostScript."""

    def __init__(self, matrix: Affine = IDENTITY):
        self.matrix = matrix
        self.contours: list[Contour] = []
        self._cur: list[Segment] = []
        self._start: Point | None = None
        self._pos: Point | None = None

    @property
    def position(self) -> Point | None:
        return self._pos

    def _flush(self, closed: bool = False) -> None:
        if self._cur:
            self.contours.append(Contour(self._cur, closed))
        self._cur = []

    def move_to(self, p: Point) -> None:
        self._flush()
        self._start = self._pos = p

    def line_to(self, p: Point) -> None:
        if self._pos is None:
            self.move_to(p)
            return
        if dist(self._pos, p) > EPS:
            m = self.matrix
            self._cur.append(Line(m.apply(self._pos), m.apply(p)))
        self._pos = p

    def cubic_to(self, c1: Point, c2: Point, p: Point) -> None:
        if self._pos is None:
            self.move_to(c1)
        m = self.matrix
        self._cur.append(Cubic(m.apply(self._pos), m.apply(c1), m.apply(c2), m.apply(p)))
        self._pos = p

    def quad_to(self, c: Point, p: Point, w: float = 1.0) -> None:
        if self._pos is None:
            self.move_to(c)
        m = self.matrix
        self._cur.append(Conic(m.apply(self._pos), m.apply(c), m.apply(p), w))
        self._pos = p

    def add_segment(self, seg: Segment) -> None:
        """Ajoute un segment déjà en coordonnées finales."""
        self._cur.append(seg)

    def close(self) -> None:
        if self._cur and self._start is not None and self._pos is not None:
            if dist(self._pos, self._start) > EPS:
                m = self.matrix
                self._cur.append(Line(m.apply(self._pos), m.apply(self._start)))
            self._flush(closed=True)
        self._pos = self._start

    def path(self) -> Path:
        self._flush()
        return Path(self.contours)


def close_returning(p: Path, tol: float = 1e-9) -> Path:
    """Les contours ouverts de `p` qui reviennent à leur point de départ, fermés : le tour d'une forme tiré sans que
    le logiciel écrive la fermeture. Un aller-retour de deux traits droits reste ouvert."""
    def returns(c: Contour) -> bool:
        n = len(c.segments)
        return (not c.closed and n >= 2 and dist(c.end, c.start) <= tol
                and (n >= 3 or not all(isinstance(s, Line) for s in c.segments)))
    if not any(returns(c) for c in p.contours):
        return p
    return Path([Contour(list(c.segments), True) if returns(c) else c for c in p.contours])


def rect(x: float, y: float, w: float, h: float, r: float = 0.0) -> Contour:
    """Rectangle de coin bas-gauche (x, y), coins arrondis de rayon r."""
    r = max(0.0, min(r, abs(w) / 2, abs(h) / 2))
    if r <= EPS:
        pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        return Contour([Line(pts[i], pts[(i + 1) % 4]) for i in range(4)], True)
    segs: list[Segment] = []
    x0, y0, x1, y1 = x, y, x + w, y + h
    segs.append(Line((x0 + r, y0), (x1 - r, y0)))
    segs += arc_conics((x1 - r, y0 + r), r, r, -90, 90)
    segs.append(Line((x1, y0 + r), (x1, y1 - r)))
    segs += arc_conics((x1 - r, y1 - r), r, r, 0, 90)
    segs.append(Line((x1 - r, y1), (x0 + r, y1)))
    segs += arc_conics((x0 + r, y1 - r), r, r, 90, 90)
    segs.append(Line((x0, y1 - r), (x0, y0 + r)))
    segs += arc_conics((x0 + r, y0 + r), r, r, 180, 90)
    return Contour(segs, True)


def ellipse(center: Point, rx: float, ry: float, rotation_deg: float = 0.0) -> Contour:
    return Contour(arc_conics(center, rx, ry, 0, 360, rotation_deg), True)


def circle(center: Point, r: float) -> Contour:
    return ellipse(center, r, r)


circle_ = circle                    # pour les fonctions dont un paramètre s'appelle « circle »


def polygon(center: Point, radius: float, sides: int, start_deg: float = 90.0) -> Contour:
    pts = [(center[0] + radius * math.cos(math.radians(start_deg + 360 * i / sides)),
            center[1] + radius * math.sin(math.radians(start_deg + 360 * i / sides)))
           for i in range(sides)]
    return polyline(pts, closed=True)


def polyline(points: Sequence[Point], closed: bool = False) -> Contour:
    segs = [Line(points[i], points[i + 1]) for i in range(len(points) - 1)
            if dist(points[i], points[i + 1]) > EPS]
    if closed and len(points) > 2 and dist(points[-1], points[0]) > EPS:
        segs.append(Line(points[-1], points[0]))
    return Contour(segs, closed)


def tangent_arc(p0: Point, direction: Point, p1: Point):
    """L'arc parti de p0 dans la direction (unitaire) donnée et qui arrive en p1 : (segments, direction à l'arrivée).
    p1 droit devant : un segment. p1 confondu avec p0 ou droit derrière : aucun arc possible, None."""
    tx, ty = direction
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    length2 = dx * dx + dy * dy
    if length2 < EPS * EPS:
        return None
    height = dx * -ty + dy * tx                          # p1 à gauche de la tangente : positif
    if abs(height) < 1e-9 * math.sqrt(length2):
        if dx * tx + dy * ty <= 0:
            return None
        return [Line(p0, p1)], direction
    r = length2 / (2.0 * height)                         # signé : positif, le centre est à gauche, sens direct
    cx, cy = p0[0] - ty * r, p0[1] + tx * r
    a0 = math.atan2(p0[1] - cy, p0[0] - cx)
    a1 = math.atan2(p1[1] - cy, p1[0] - cx)
    sweep = (a1 - a0) % (2 * math.pi) if r > 0 else -((a0 - a1) % (2 * math.pi))
    arcs = arc_conics((cx, cy), abs(r), abs(r), math.degrees(a0), math.degrees(sweep))
    if not arcs:
        return None
    first = arcs[0]                                      # bouts exacts : le suivant repart de p1
    arcs[0] = Conic(p0, first.p1, first.p2, first.w)
    last = arcs[-1]
    arcs[-1] = Conic(last.p0, last.p1, p1, last.w)
    ex, ey = p1[0] - cx, p1[1] - cy
    k = (1.0 if r > 0 else -1.0) / math.hypot(ex, ey)
    return arcs, (-ey * k, ex * k)


def bulge_segment(p0: Point, p1: Point, bulge: float) -> list[Segment]:
    """Segment de polyligne DXF : bulge = tan(θ/4), positif = anti-horaire."""
    if abs(bulge) < 1e-12:
        return [Line(p0, p1)]
    theta = 4 * math.atan(bulge)
    chord = dist(p0, p1)
    r = chord / (2 * math.sin(abs(theta) / 2))
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    # distance du centre au milieu de la corde, signée
    h = r * math.cos(theta / 2) * (1 if bulge > 0 else -1)
    ux, uy = (p1[0] - p0[0]) / chord, (p1[1] - p0[1]) / chord
    c = (mx - uy * h, my + ux * h)
    a0 = math.degrees(math.atan2(p0[1] - c[1], p0[0] - c[0]))
    segs = arc_conics(c, r, r, a0, math.degrees(theta))
    # recoller exactement les extrémités (erreurs d'arrondi)
    if segs:
        f = segs[0]
        segs[0] = Conic(p0, f.p1, f.p2, f.w)
        l = segs[-1]
        segs[-1] = Conic(l.p0, l.p1, p1, l.w)
    return segs


def iter_segments(paths: Iterable[Path]) -> Iterator[Segment]:
    for p in paths:
        for c in p.contours:
            yield from c.segments


def star(center: Point, r_out: float, r_in: float, branches: int, start_deg: float = 90.0) -> Contour:
    pts = []
    for i in range(2 * branches):
        r = r_out if i % 2 == 0 else r_in
        a = math.radians(start_deg + 180.0 * i / branches)
        pts.append((center[0] + r * math.cos(a), center[1] + r * math.sin(a)))
    return polyline(pts, closed=True)


def spiral(center: Point, r_out: float, turns: float, start_deg: float = 0.0, r_in: float = 0.0,
           ccw: bool = True, tol: float = 1e-4) -> Contour:
    """Spirale d'Archimède de `r_in` (au centre) à `r_out` (à l'extérieur,
    dans la direction `start_deg`) en `turns` tours ; courbes de Bézier
    raccordées en tangence, à `tol` mm de la courbe exacte."""
    span = 2 * math.pi * max(turns, 1e-6)
    b = (r_out - r_in) / span                 # r = r_in + b·θ, θ de 0 à span
    s = 1.0 if ccw else -1.0
    a_end = math.radians(start_deg)
    cx, cy = center

    def pt(th):
        r, a = r_in + b * th, a_end - s * (span - th)
        return (cx + r * math.cos(a), cy + r * math.sin(a))

    def d(th):                                # dérivée par rapport à θ
        r, a = r_in + b * th, a_end - s * (span - th)
        return (b * math.cos(a) - s * r * math.sin(a), b * math.sin(a) + s * r * math.cos(a))

    def hermite(t0, t1):
        h = t1 - t0
        p0, p3, d0, d1 = pt(t0), pt(t1), d(t0), d(t1)
        return Cubic(p0, (p0[0] + d0[0] * h / 3, p0[1] + d0[1] * h / 3),
                     (p3[0] - d1[0] * h / 3, p3[1] - d1[1] * h / 3), p3)

    segs: list[Segment] = []
    stack = [(span * (k + 1) / max(4, math.ceil(turns * 4)), span * k / max(4, math.ceil(turns * 4)))
             for k in reversed(range(max(4, math.ceil(turns * 4))))]
    while stack:
        t1, t0 = stack.pop()
        c = hermite(t0, t1)
        err = max(dist(c.point(u), pt(t0 + u * (t1 - t0))) for u in (0.1, 0.25, 0.4, 0.5, 0.6, 0.75, 0.9))
        if err > tol and t1 - t0 > 1e-6:
            m = (t0 + t1) / 2
            stack.append((t1, m))
            stack.append((m, t0))
        else:
            segs.append(c)
    return Contour(segs, False)


def marker(center: Point, size: float, circle: bool = True) -> list[Contour]:
    """Repère de calage : croix de `size` mm (deux traits ouverts) et, si
    `circle`, cercle de rayon size × 0,3 au centre."""
    x, y = center
    h = size / 2
    out = [Contour([Line((x - h, y), (x + h, y))], False), Contour([Line((x, y - h), (x, y + h))], False)]
    if circle:
        out.append(circle_(center, size * 0.3))
    return out


def walker(contour: Contour, samples: int = 64):
    """Parcours d'une courbe à l'abscisse curviligne : renvoie (longueur,
    at) où at(d) → (point, angle de la tangente en radians), d borné à
    [0, longueur].

    Le point est pris **sur la courbe exacte** (`segment.point(t)`) et la
    tangente vient de la dérivée ; seule la correspondance t ↔ longueur est
    tabulée (`samples` pas par segment courbe, recalés sur la longueur
    exacte du segment). Un contour fermé inclut son segment de fermeture.
    """
    segs = list(contour.segments)
    if contour.closed and segs and contour.closing_gap() > 1e-9:
        segs.append(Line(contour.end, contour.start))
    tables = []                      # (abscisse de départ, ts, longueurs cumulées, segment)
    total = 0.0
    for sg in segs:
        n = 1 if isinstance(sg, Line) else samples
        ts = [i / n for i in range(n + 1)]
        pts = [sg.point(t) for t in ts]
        cum = [0.0]
        for i in range(1, len(pts)):
            cum.append(cum[-1] + math.dist(pts[i - 1], pts[i]))
        if cum[-1] <= 0:
            continue
        k = sg.length() / cum[-1]
        cum = [c * k for c in cum]
        tables.append((total, ts, cum, sg))
        total += cum[-1]
    starts = [t[0] for t in tables]

    def at(d: float):
        if not tables:
            return (contour.start if contour.segments else (0.0, 0.0)), 0.0
        import bisect
        d = max(0.0, min(total, d))
        i = max(0, bisect.bisect_right(starts, d) - 1)
        s0, ts, cum, sg = tables[i]
        dd = d - s0
        j = max(0, min(len(cum) - 2, bisect.bisect_right(cum, dd) - 1))
        span = max(cum[j + 1] - cum[j], 1e-15)
        t = ts[j] + (ts[j + 1] - ts[j]) * (dd - cum[j]) / span
        t = max(0.0, min(1.0, t))
        h = 1e-6
        a_, b_ = sg.point(max(0.0, t - h)), sg.point(min(1.0, t + h))
        return sg.point(t), math.atan2(b_[1] - a_[1], b_[0] - a_[0])
    return total, at


def arc(center: Point, r: float, start_deg: float, sweep_deg: float) -> Contour:
    return Contour(arc_conics(center, r, r, start_deg, sweep_deg), False)


def arc_3points(a: Point, b: Point, c: Point) -> Contour | None:
    """Arc passant par trois points (a → b → c). None si alignés."""
    ax, ay = a
    bx, by = b
    cx, cy = c
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return None
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    t0 = math.degrees(math.atan2(ay - uy, ax - ux))
    t1 = math.degrees(math.atan2(by - uy, bx - ux))
    t2 = math.degrees(math.atan2(cy - uy, cx - ux))
    ccw = ((t1 - t0) % 360) < ((t2 - t0) % 360)
    sweep = (t2 - t0) % 360 if ccw else -((t0 - t2) % 360)
    segs = arc_conics((ux, uy), r, r, t0, sweep)
    if segs:
        segs[0] = Conic(a, segs[0].p1, segs[0].p2, segs[0].w)
        l = segs[-1]
        segs[-1] = Conic(l.p0, l.p1, c, l.w)
    return Contour(segs, False)


def _corner_ok(s0: Segment, s1: Segment) -> bool:
    return isinstance(s0, Line) and isinstance(s1, Line)


def _unit(p: Point, q: Point) -> tuple[Point, float]:
    d = dist(p, q)
    return ((q[0] - p[0]) / d, (q[1] - p[1]) / d), d


def corner_contour(c: Contour, size: float, kind: str = 'fillet',
                   only: set[int] | None = None) -> Contour:
    """Congés (`fillet`, rayon `size`) ou chanfreins (`chamfer`, recul
    `size` sur chaque côté) aux coins entre deux droites.

    `only` : indices des nœuds à traiter (nœud i = fin du segment i) ;
    None = tous. Les coins trop petits pour le rayon sont laissés tels
    quels. Le congé est un arc exact (conique au contrôle sur le coin).
    Congé de rayon négatif (TypeEdit : angle arrondi vers l'intérieur) :
    l'arc est centré sur le coin, de rayon |size| — le coin est creusé.
    """
    segs = list(c.segments)
    n = len(segs)
    notch = kind == 'fillet' and size < 0
    size = abs(size) if notch else size
    if n < 2 or size <= 0:
        return Contour(segs, c.closed)
    corners = range(n) if c.closed else range(n - 1)
    cut: dict[int, tuple] = {}
    for i in corners:
        if only is not None and i not in only:
            continue
        s0, s1 = segs[i], segs[(i + 1) % n]
        if not _corner_ok(s0, s1):
            continue
        v = s0.p1
        (d0, L0) = _unit(v, s0.p0)
        (d1, L1) = _unit(v, s1.p1)
        cosang = max(-1.0, min(1.0, d0[0] * d1[0] + d0[1] * d1[1]))
        alpha = math.acos(cosang)                 # angle intérieur du coin
        if alpha < 1e-6 or abs(alpha - math.pi) < 1e-6:
            continue
        t = size if notch or kind != 'fillet' else size / math.tan(alpha / 2)
        if t >= L0 - 1e-9 or t >= L1 - 1e-9:
            continue
        p0 = (v[0] + d0[0] * t, v[1] + d0[1] * t)
        p1 = (v[0] + d1[0] * t, v[1] + d1[1] * t)
        if notch:                                  # arc centré sur le coin : contrôle sur la bissectrice
            bx, by = d0[0] + d1[0], d0[1] + d1[1]
            bl = math.hypot(bx, by)
            ca = math.cos(alpha / 2)
            if bl < 1e-12 or ca < 1e-6:
                continue
            ctrl = (v[0] + bx / bl * size / ca, v[1] + by / bl * size / ca)
            cut[i] = (p0, ctrl, p1, ca)
            continue
        cut[i] = (p0, v, p1, math.sin(alpha / 2))
    if not cut:
        return Contour(segs, c.closed)
    out: list[Segment] = []
    for i, s in enumerate(segs):
        a = s.start
        b = s.end
        prev = (i - 1) % n
        if prev in cut and (c.closed or i > 0):
            a = cut[prev][2]
        if i in cut:
            b = cut[i][0]
        if dist(a, b) > 1e-12:
            out.append(Line(a, b))
        if i in cut:
            p0, v, p1, w = cut[i]
            out.append(Conic(p0, v, p1, w) if kind == 'fillet' else Line(p0, p1))
    if c.closed and (n - 1) in cut and out:
        pass                                       # le premier segment a déjà été raccourci
    return Contour(out, c.closed)


def dimension(p1: Point, p2: Point, offset: float, text_height: float = 3.5,
              arrow: float = 2.5, decimals: int = 2, font: str = 'Arial') -> list[Path]:
    """Cote linéaire alignée (géométrie gravable) : lignes d'attache, ligne
    de cote, flèches pleines, valeur. `offset` : distance signée de la ligne
    de cote à la mesure. Retourne [traits, flèches, texte]."""
    from . import text as _text
    L = dist(p1, p2)
    if L < 1e-9:
        return []
    ux, uy = (p2[0] - p1[0]) / L, (p2[1] - p1[1]) / L
    nx, ny = -uy, ux
    a = (p1[0] + nx * offset, p1[1] + ny * offset)
    b = (p2[0] + nx * offset, p2[1] + ny * offset)
    ext = 1.5 * (1 if offset >= 0 else -1)
    gap = 1.0 * (1 if offset >= 0 else -1)
    lines = [polyline([(p1[0] + nx * gap, p1[1] + ny * gap), (a[0] + nx * ext, a[1] + ny * ext)]),
             polyline([(p2[0] + nx * gap, p2[1] + ny * gap), (b[0] + nx * ext, b[1] + ny * ext)]),
             polyline([a, b])]
    hw = arrow * 0.18

    def head(tip, d):
        bx, by = tip[0] + d[0] * arrow, tip[1] + d[1] * arrow
        return polyline([tip, (bx + nx * hw, by + ny * hw), (bx - nx * hw, by - ny * hw)], closed=True)
    heads = [head(a, (ux, uy)), head(b, (-ux, -uy))]
    label = f'{L:.{decimals}f}'.rstrip('0').rstrip('.') if decimals else f'{L:.0f}'
    t = _text.layout(label, font, text_height, align='center')
    ang = math.degrees(math.atan2(uy, ux))
    if ang > 90.0001 or ang < -89.9999:          # texte toujours lisible
        ang -= 180
    mid = ((a[0] + b[0]) / 2 + nx * 1.0 * (1 if offset >= 0 else -1),
           (a[1] + b[1]) / 2 + ny * 1.0 * (1 if offset >= 0 else -1))
    if offset < 0:
        mid = (mid[0] - nx * text_height, mid[1] - ny * text_height)
    m = Affine.translation(*mid) @ Affine.rotation(ang)
    return [Path(lines), Path(heads), t.transformed(m)]
