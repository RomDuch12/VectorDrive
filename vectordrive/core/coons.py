"""Enveloppe par courbes : des objets, ou un relief, déformés entre quatre côtés.

Les côtés sont quatre courbes qui se touchent, dans n'importe quel ordre et n'importe
quel sens, ou un seul contour fermé coupé à ses coins. Ils sont rangés d'après la figure :
bas, droite, haut, gauche, dans le sens direct, en partant du coin en bas à gauche ;
`turn` décale ce rangement d'un quart de tour pour poser le dessin autrement.

Le carreau de Coons reproduit exactement les quatre côtés et se raccorde entre eux :
S(u, v) = (1-v)·B(u) + v·H(u) + (1-u)·G(v) + u·D(v) - (terme bilinéaire des coins).
"""
from __future__ import annotations

import numpy as np

from .document import Shape
from .geom import Contour

#: distance (mm) à laquelle deux bouts de courbes sont considérés comme joints
JOIN_TOL = 0.2
#: changement de direction à partir duquel un point est un coin
CORNER_DEG = 25.0
FLAT_TOL = 0.002
#: nombre de points lus sur le relief ; au-delà, la lecture se fait moins serrée
MAX_SAMPLES = 60_000_000


class EnvelopeError(ValueError):
    """Les courbes ne forment pas une enveloppe : 'join', 'corners', 'area' ou 'count'."""


def _polyline(c: Contour) -> np.ndarray:
    return np.asarray(c.flatten(FLAT_TOL), dtype=float).reshape(-1, 2)


def _length(p: np.ndarray) -> float:
    return float(np.hypot(*np.diff(p, axis=0).T).sum()) if len(p) > 1 else 0.0


def _area(loop: list[np.ndarray]) -> float:
    p = np.vstack([s[:-1] for s in loop])
    x, y = p[:, 0], p[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def _chain_four(parts: list[np.ndarray], tol: float) -> list[np.ndarray]:
    """Les quatre courbes bout à bout, chacune dans le bon sens."""
    rest = list(parts[1:])
    loop = [parts[0]]
    for _ in range(3):
        end = loop[-1][-1]
        best = None
        for i, s in enumerate(rest):
            for rev, q in ((False, s[0]), (True, s[-1])):
                d = float(np.hypot(*(q - end)))
                if best is None or d < best[0]:
                    best = (d, i, rev)
        if best is None or best[0] > tol:
            raise EnvelopeError('join')
        s = rest.pop(best[1])
        loop.append(s[::-1] if best[2] else s)
    if float(np.hypot(*(loop[-1][-1] - loop[0][0]))) > tol:
        raise EnvelopeError('join')
    return loop


def _turning(p: np.ndarray) -> np.ndarray:
    """Le changement de direction (degrés) à chaque point d'un contour fermé sans point répété."""
    d = np.roll(p, -1, axis=0) - p
    keep = np.hypot(d[:, 0], d[:, 1]) > 1e-12
    a = np.arctan2(d[:, 1], d[:, 0])
    if not keep.all():                                   # côté nul : garde la direction précédente
        for i in np.flatnonzero(~keep):
            a[i] = a[i - 1]
    t = np.abs((a - np.roll(a, 1) + np.pi) % (2 * np.pi) - np.pi)
    return np.degrees(t)


def _corners(p: np.ndarray) -> list[int]:
    """Les quatre coins d'un contour fermé : ses coins vifs, sinon les points les plus loin en diagonale."""
    turn = _turning(p)
    sharp = np.flatnonzero(turn > CORNER_DEG)
    if len(sharp) == 4:
        return sorted(int(i) for i in sharp)
    centre = (p.min(axis=0) + p.max(axis=0)) / 2
    candidates = sharp if len(sharp) > 4 else np.arange(len(p))
    picked = []
    for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        q = p[candidates] - centre
        picked.append(int(candidates[int(np.argmax(q[:, 0] * dx + q[:, 1] * dy))]))
    if len(set(picked)) == 4:
        return sorted(picked)
    if len(sharp) > 4:                                   # les plus marqués
        return sorted(int(i) for i in sharp[np.argsort(-turn[sharp])[:4]])
    s = np.concatenate(([0.0], np.cumsum(np.hypot(*(np.roll(p, -1, axis=0) - p).T))))
    return sorted({int(np.searchsorted(s, s[-1] * k / 4)) % len(p) for k in range(4)})


def _split_closed(p: np.ndarray) -> list[np.ndarray]:
    if len(p) > 1 and float(np.hypot(*(p[0] - p[-1]))) < 1e-9:
        p = p[:-1]
    if len(p) < 4:
        raise EnvelopeError('corners')
    cut = _corners(p)
    if len(cut) != 4:
        raise EnvelopeError('corners')
    twice = np.vstack((p, p))
    out = []
    for a, b in zip(cut, cut[1:] + [cut[0] + len(p)]):
        out.append(twice[a:b + 1].copy())
    return out


def _ordered(loop: list[np.ndarray]) -> list[np.ndarray]:
    if _area(loop) < 0:
        loop = [s[::-1] for s in reversed(loop)]
    if abs(_area(loop)) < 1e-9:
        raise EnvelopeError('area')
    first = min(range(4), key=lambda i: float(loop[i][0][0] + loop[i][0][1]))
    return loop[first:] + loop[:first]


def sides_of(contours: list[Contour], tol: float = JOIN_TOL) -> list[np.ndarray]:
    """Bas, droite, haut, gauche, dans le sens direct. EnvelopeError si ce n'est pas une enveloppe."""
    parts = [c for c in contours if c.segments]
    if len(parts) == 4:
        lines = [_polyline(c) for c in parts]
        return _ordered(_chain_four(lines, tol))
    if len(parts) == 1:
        p = _polyline(parts[0])
        if parts[0].closed or float(np.hypot(*(p[0] - p[-1]))) <= tol:
            return _ordered(_split_closed(p))
    raise EnvelopeError('count')


def _contours(items) -> list[Contour]:
    return [c for it in items if isinstance(it, Shape) for c in it.path.contours]


def pick(items: list) -> tuple[list, list, list[np.ndarray]] | None:
    """(objets, courbes de l'enveloppe, côtés) d'après la sélection : les quatre derniers tracés
    ouverts s'ils se touchent, sinon le dernier objet. None si aucun des deux ne convient."""
    opened = [it for it in items if isinstance(it, Shape) and it.path.contours
              and not any(c.closed for c in it.path.contours)]
    tries = [opened[-4:]] if len(opened) >= 4 else []
    if items:
        tries.append(items[-1:])
    for curves in tries:
        try:
            sides = sides_of(_contours(curves))
        except EnvelopeError:
            continue
        ids = {id(c) for c in curves}
        return [it for it in items if id(it) not in ids], list(curves), sides
    return None


class _Side:
    """Une courbe parcourue à vitesse constante, de t = 0 à t = 1 ; continue en ligne droite au-delà."""

    def __init__(self, p: np.ndarray):
        s = np.concatenate(([0.0], np.cumsum(np.hypot(*np.diff(p, axis=0).T))))
        keep = np.concatenate(([True], np.diff(s) > 1e-12))
        self.p = p[keep]
        s = s[keep]
        self.total = float(s[-1])
        self.s = s / self.total if self.total > 0 else s

    def __call__(self, t):
        return np.interp(t, self.s, self.p[:, 0]), np.interp(t, self.s, self.p[:, 1])

    def point(self, t: float) -> tuple[float, float]:
        p, s = self.p, self.s
        if len(p) > 1 and t < 0:
            k = t / s[1]
            return float(p[0, 0] + k * (p[1, 0] - p[0, 0])), float(p[0, 1] + k * (p[1, 1] - p[0, 1]))
        if len(p) > 1 and t > 1:
            k = (t - 1) / (1 - s[-2])
            return float(p[-1, 0] + k * (p[-1, 0] - p[-2, 0])), float(p[-1, 1] + k * (p[-1, 1] - p[-2, 1]))
        return float(np.interp(t, s, p[:, 0])), float(np.interp(t, s, p[:, 1]))


class Patch:
    """Le carreau de Coons des quatre côtés (rangés par `sides_of`)."""

    def __init__(self, sides, turn: int = 0):
        sides = [np.asarray(s, dtype=float).reshape(-1, 2) for s in sides]
        k = int(turn) % 4
        low, right, top, left = sides[k:] + sides[:k]
        self.low, self.top = _Side(low), _Side(top[::-1])
        self.left, self.right = _Side(left[::-1]), _Side(right)
        self.outline = np.vstack((low, right, top, left))
        self.c00 = (low[0] + left[-1]) / 2
        self.c10 = (low[-1] + right[0]) / 2
        self.c11 = (right[-1] + top[0]) / 2
        self.c01 = (top[-1] + left[0]) / 2

    def point(self, u: float, v: float) -> tuple[float, float]:
        bx, by = self.low.point(u)
        tx, ty = self.top.point(u)
        lx, ly = self.left.point(v)
        rx, ry = self.right.point(v)
        a, b, c, d = (1 - u) * (1 - v), u * (1 - v), u * v, (1 - u) * v
        x = (1 - v) * bx + v * tx + (1 - u) * lx + u * rx - (a * self.c00[0] + b * self.c10[0] + c * self.c11[0] + d * self.c01[0])
        y = (1 - v) * by + v * ty + (1 - u) * ly + u * ry - (a * self.c00[1] + b * self.c10[1] + c * self.c11[1] + d * self.c01[1])
        return x, y

    def grid(self, us: np.ndarray, vs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """X, Y du carreau : une ligne par valeur de v, une colonne par valeur de u."""
        U, V = us[None, :], vs[:, None]
        bx, by = self.low(us)
        tx, ty = self.top(us)
        lx, ly = self.left(vs)
        rx, ry = self.right(vs)
        a, b, c, d = (1 - U) * (1 - V), U * (1 - V), U * V, (1 - U) * V
        X = ((1 - V) * bx[None, :] + V * tx[None, :] + (1 - U) * lx[:, None] + U * rx[:, None]
             - (a * self.c00[0] + b * self.c10[0] + c * self.c11[0] + d * self.c01[0]))
        Y = ((1 - V) * by[None, :] + V * ty[None, :] + (1 - U) * ly[:, None] + U * ry[:, None]
             - (a * self.c00[1] + b * self.c10[1] + c * self.c11[1] + d * self.c01[1]))
        return X, Y


def normalized(sides: list[np.ndarray], bbox) -> list[list]:
    """Les côtés rapportés à la boîte des objets : ils suivent le groupe qu'on déplace ou agrandit."""
    x0, y0, x1, y1 = bbox
    w, h = max(x1 - x0, 1e-9), max(y1 - y0, 1e-9)
    return [(((np.asarray(s) - (x0, y0)) / (w, h))).tolist() for s in sides]


def mapping(sides, turn: int, bbox):
    """Fonction (x, y) → (x', y') de la boîte `bbox` vers le carreau (côtés rapportés à la boîte)."""
    x0, y0, x1, y1 = bbox
    w, h = max(x1 - x0, 1e-9), max(y1 - y0, 1e-9)
    patch = Patch(sides, turn)

    def f(p):
        X, Y = patch.point((p[0] - x0) / w, (p[1] - y0) / h)
        return x0 + w * X, y0 + h * Y
    return f


def warp_heights(H: np.ndarray, sides, turn: int, res: float, progress=None):
    """Le relief `H` entre les quatre côtés : (hauteurs, x0, y1, pas). Z ne change pas ; zéro autour."""
    from . import galbe as GB
    patch = Patch(sides, turn)
    lo, hi = patch.outline.min(axis=0), patch.outline.max(axis=0)
    x0, y1, nx, ny, res = GB._grid((float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1])), res)
    nu = int(np.ceil(2 * max(patch.low.total, patch.top.total) / res)) + 2
    nv = int(np.ceil(2 * max(patch.left.total, patch.right.total) / res)) + 2
    if nu * nv > MAX_SAMPLES:
        k = (MAX_SAMPLES / (nu * nv)) ** 0.5
        nu, nv = max(2, int(nu * k)), max(2, int(nv * k))
    h, w = H.shape
    us = (np.arange(nu) + 0.5) / nu
    vs = (np.arange(nv) + 0.5) / nv
    fx = np.clip(us * w - 0.5, 0, w - 1)
    i0 = np.minimum(fx.astype(int), w - 2) if w > 1 else np.zeros(nu, dtype=int)
    i1 = i0 + 1 if w > 1 else i0
    ax = fx - i0
    total = np.zeros(nx * ny)
    weight = np.zeros(nx * ny)
    step = 256
    for start in range(0, nv, step):
        part = vs[start:start + step]
        X, Y = patch.grid(us, part)
        fy = np.clip((1 - part) * h - 0.5, 0, h - 1)
        j0 = np.minimum(fy.astype(int), h - 2) if h > 1 else np.zeros(len(part), dtype=int)
        j1 = j0 + 1 if h > 1 else j0
        ay = (fy - j0)[:, None]
        vals = ((H[j0][:, i0] * (1 - ax) + H[j0][:, i1] * ax) * (1 - ay)
                + (H[j1][:, i0] * (1 - ax) + H[j1][:, i1] * ax) * ay)
        col = np.floor((X - x0) / res).astype(np.int64)
        row = np.floor((y1 - Y) / res).astype(np.int64)
        ok = (col >= 0) & (col < nx) & (row >= 0) & (row < ny)
        idx = row[ok] * nx + col[ok]
        total += np.bincount(idx, weights=vals[ok], minlength=nx * ny)
        weight += np.bincount(idx, minlength=nx * ny)
        if progress is not None:
            progress(start / nv)
    seen = weight.reshape(ny, nx) > 0
    out = np.zeros((ny, nx))
    out[seen] = (total / np.maximum(weight, 1)).reshape(ny, nx)[seen]
    return _fill_holes(out, seen), x0, y1, res


def _fill_holes(H: np.ndarray, seen: np.ndarray) -> np.ndarray:
    """Une zone très étirée peut laisser un point sans lecture : il prend la moyenne de ses voisins."""
    for _ in range(2):
        if seen.all():
            break
        V, S = np.pad(H * seen, 1), np.pad(seen.astype(float), 1)
        ny, nx = H.shape
        count = np.zeros((ny, nx))
        total = np.zeros((ny, nx))
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx or dy:
                    count += S[1 + dy:1 + dy + ny, 1 + dx:1 + dx + nx]
                    total += V[1 + dy:1 + dy + ny, 1 + dx:1 + dx + nx]
        hole = ~seen & (count >= 5)
        if not hole.any():
            break
        H = H.copy()
        H[hole] = total[hole] / count[hole]
        seen = seen | hole
    return H


def warp_image(img, sides, turn: int, res: float, progress=None):
    """L'image de relief `img`, déformée. None si son relief ne se relit pas (posé de travers)."""
    from . import galbe as GB
    got = GB.decode(img)
    if got is None:
        return None
    H, _x0, _y1, _res = got
    new, x0, y1, step = warp_heights(H, sides, turn, res, progress)
    spec = GB.GalbeSpec.from_dict(img.extra.get('galbe'))
    spec.z_max, spec.z_min, spec.resolution, spec.margin = float(new.max()), float(new.min()), step, 0.0
    return GB.encode(new, x0, y1, step, spec, img.tool, img.name)
