"""Imbrication selon la vraie forme : les objets s'emboîtent au lieu de ranger leurs rectangles.

Chaque objet, à chaque angle essayé, devient une grille de cases : toute case touchée par son tracé est marquée, et le
dedans est rempli. La plaque est une grille aussi. La première place libre, en partant du coin haut gauche, se lit sur la
corrélation des deux grilles (FFT). Un objet posé marque la plaque de son tracé élargi de l'écart.

Le tracé tient toujours dans ses cases, l'élargissement compte la diagonale d'une case : deux objets ne sont jamais plus
près que l'écart, quelle que soit la précision. Une précision plus grossière ne perd que de la place, et `nesting_tight`
reprend à la fin le jeu qui reste entre les objets.
"""
from __future__ import annotations

import math

import numpy as np

from . import progress
from .nesting import MIN_PRECISION
from .document import Group, Item, Plate, Shape, Text
from .geom import Affine

#: au plus tant de cases sur le grand côté de la plaque : la précision demandée est relâchée au-delà
MAX_CELLS = 2000
#: au plus tant de copies en remplissage
FILL_MAX = 5000
#: élargissement, en cases : la diagonale d'une case, et de quoi couvrir l'échantillonnage du tracé (cell / 8 de chaque côté)
_DIAGONAL = 1.55


def _next_size(n: int) -> int:
    """Taille de FFT rapide (2, 3, 5 seuls) au moins égale à n."""
    while True:
        m = n
        for p in (2, 3, 5):
            while m % p == 0:
                m //= p
        if m == 1:
            return n
        n += 1


def _leaf_contours(it: Item, tol: float) -> list[list[tuple[np.ndarray, bool]]]:
    """Par objet feuille : ses contours en points (tableau N×2, fermé ou non). Sans tracé : son rectangle."""
    if isinstance(it, Group):
        return [leaf for ch in it.children for leaf in _leaf_contours(ch, tol)]
    path = it.path if isinstance(it, Shape) else (it.outline if isinstance(it, Text) else None)
    out = []
    if path is not None:
        for c in path.contours:
            if not c.segments:
                continue
            pts = [c.segments[0].start]
            for s in c.segments:
                pts.extend(s.flatten(tol))
            arr = np.array(pts, dtype=float)
            if len(arr) >= 2 and np.isfinite(arr).all():
                out.append((arr, bool(c.closed)))
    if not out:
        bb = it.bbox()
        if not bb:
            return []
        out.append((np.array([(bb[0], bb[1]), (bb[2], bb[1]), (bb[2], bb[3]), (bb[0], bb[3]), (bb[0], bb[1])], float), True))
    return [out]


def _fill(pts: np.ndarray, x0: float, y1: float, cell: float, shape: tuple) -> np.ndarray:
    """Le dedans d'un contour fermé (pair-impair), sur toute la grille de l'objet."""
    mh, mw = shape
    p = np.vstack((pts, pts[:1])) if (pts[0] != pts[-1]).any() else pts
    rows = (y1 - p[:, 1]) / cell - 0.5                   # ligne de chaque point, les centres des cases tombant sur les entiers
    cols = (p[:, 0] - x0) / cell - 0.5
    r0, r1 = rows[:-1], rows[1:]
    lo = np.ceil(np.minimum(r0, r1)).astype(int)
    hi = np.ceil(np.maximum(r0, r1)).astype(int)         # moitié ouverte : un sommet n'est compté qu'une fois
    acc = np.zeros((mh, mw + 1), dtype=np.int32)
    for k in np.nonzero(hi > lo)[0]:
        rr = np.arange(max(lo[k], 0), min(hi[k], mh))
        if not len(rr):
            continue
        t = (rr - r0[k]) / (r1[k] - r0[k])
        cc = np.ceil(cols[k] + t * (cols[k + 1] - cols[k])).astype(int)
        np.add.at(acc, (rr, np.clip(cc, 0, mw)), 1)
    return (np.cumsum(acc, axis=1)[:, :mw] & 1).astype(bool)


def _mark(mask: np.ndarray, pts: np.ndarray, x0: float, y1: float, cell: float) -> None:
    """Les cases que touche le tracé. Ainsi un trait ouvert ou très fin compte, et le tracé reste dans ses cases."""
    mh, mw = mask.shape
    d = np.diff(pts, axis=0)
    n = np.maximum(np.ceil(np.hypot(d[:, 0], d[:, 1]) / (cell / 8.0)).astype(int), 1)
    idx = np.repeat(np.arange(len(d)), n)
    t = (np.arange(len(idx)) - np.repeat(np.cumsum(n) - n, n)) / np.repeat(n, n)
    all_pts = np.vstack((pts[idx] + d[idx] * t[:, None], pts[-1:]))
    r = np.clip(((y1 - all_pts[:, 1]) / cell).astype(int), 0, mh - 1)
    c = np.clip(((all_pts[:, 0] - x0) / cell).astype(int), 0, mw - 1)
    mask[r, c] = True


class _Pose:
    """Un objet à un angle : sa grille, la même élargie de l'écart, et la boîte de son tracé."""

    def __init__(self, leaves: list, angle: float, center: tuple, cell: float, radius: float, in_holes: bool,
                 flip: tuple = (False, False), mirror: bool = False):
        self.angle = angle
        self.mirror = mirror
        a = math.radians(angle)
        co, si = math.cos(a), math.sin(a)
        cx, cy = center

        def turn(arr):
            x, y = arr[:, 0] - cx, arr[:, 1] - cy
            if mirror:
                x = -x
            return np.column_stack((cx + co * x - si * y, cy + si * x + co * y))
        turned = [[(turn(p), closed) for p, closed in leaf] for leaf in leaves]
        every = np.vstack([p for leaf in turned for p, _c in leaf])
        x0, y0 = every.min(axis=0)
        x1, y1 = every.max(axis=0)
        self.box = (float(x0), float(y0), float(x1), float(y1))
        mw = max(1, math.ceil((x1 - x0) / cell - 1e-9))
        mh = max(1, math.ceil((y1 - y0) / cell - 1e-9))
        mask = np.zeros((mh, mw), dtype=bool)
        for leaf in turned:
            part = np.zeros((mh, mw), dtype=bool)
            for p, closed in leaf:
                if closed:
                    f = _fill(p, x0, y1, cell, (mh, mw))
                    part = part ^ f if in_holes else part | f
            mask |= part
        for leaf in turned:
            for p, closed in leaf:
                _mark(mask, np.vstack((p, p[:1])) if closed else p, x0, y1, cell)
        if flip[0]:                                      # rangement depuis la droite : la plaque vue en miroir
            mask = mask[:, ::-1]
        if flip[1]:                                      # depuis le bas
            mask = mask[::-1, :]
        self.mask = mask
        self.area = int(mask.sum())
        self.radius = radius
        self.reach = math.ceil(radius)
        self.key = (mask.shape, mask.tobytes())
        self._halo = None
        self._spectrum = None

    @property
    def halo(self) -> np.ndarray:
        """La grille élargie de `radius` cases. Rayon non arrondi : une case de plus partout serait de la place perdue."""
        if self._halo is None:
            r = self.reach
            mh, mw = self.mask.shape
            s = (_next_size(mh + 2 * r + 1), _next_size(mw + 2 * r + 1))
            yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
            disc = (xx * xx + yy * yy < self.radius * self.radius).astype(float)
            full = np.fft.irfft2(np.fft.rfft2(self.mask.astype(float), s) * np.fft.rfft2(disc, s), s)
            self._halo = full[:mh + 2 * r, :mw + 2 * r] > 0.5
        return self._halo

    def spectrum(self, s: tuple) -> np.ndarray:
        if self._spectrum is None or self._spectrum[0] != s:
            self._spectrum = (s, np.conj(np.fft.rfft2(self.mask.astype(float), s)))
        return self._spectrum[1]

    def forget(self) -> None:
        self._spectrum = None


class _Sheet:
    """Une plaque en grille : les lignes vont du haut vers le bas."""

    def __init__(self, ny: int, nx: int, vertical: bool = False):
        self.ny, self.nx = ny, nx
        self.vertical = vertical
        self.occupied = np.zeros((ny, nx), dtype=bool)
        self.size = (_next_size(ny), _next_size(nx))
        self.used = 0
        self._spectrum = None

    def find(self, pose: _Pose):
        """La première place libre (ligne, colonne), du haut vers le bas puis de la gauche vers la droite
        (en colonnes : l'inverse) ; None s'il n'y en a pas."""
        mh, mw = pose.mask.shape
        if mh > self.ny or mw > self.nx or pose.area > self.ny * self.nx - self.used:
            return None
        if not self.used:
            return 0, 0
        if self._spectrum is None:
            self._spectrum = np.fft.rfft2(self.occupied.astype(float), self.size)
        hits = np.fft.irfft2(self._spectrum * pose.spectrum(self.size), self.size)[:self.ny - mh + 1, :self.nx - mw + 1]
        free = hits < 0.5
        if self.vertical:
            cols = free.any(axis=0)
            if not cols.any():
                return None
            c = int(cols.argmax())
            return int(free[:, c].argmax()), c
        rows = free.any(axis=1)
        if not rows.any():
            return None
        r = int(rows.argmax())
        return r, int(free[r].argmax())

    def put(self, pose: _Pose, r: int, c: int) -> None:
        h = pose.halo
        k = pose.reach
        y0, x0 = max(r - k, 0), max(c - k, 0)
        y1, x1 = min(r - k + h.shape[0], self.ny), min(c - k + h.shape[1], self.nx)
        self.occupied[y0:y1, x0:x1] |= h[y0 - (r - k):y1 - (r - k), x0 - (c - k):x1 - (c - k)]
        self.used = int(self.occupied.sum())
        self._spectrum = None


def _poses(it: Item, spec, cell: float, radius: float) -> list[_Pose]:
    """Les angles permis, retournés ou non, sans ceux qui redonnent la même grille (un carré, un disque)."""
    bb = it.bbox()
    if not bb:
        return []
    leaves = _leaf_contours(it, cell / 4.0)
    if not leaves:
        return []
    center = ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)
    step = float(getattr(spec, 'angle_step', 90.0) or 90.0)
    step = 90.0 if not 1.0 <= step <= 360.0 else step
    angles = [i * step for i in range(max(1, int(360.0 / step)))] if spec.allow_rotate else [0.0]
    if spec.allow_rotate and getattr(spec, 'angles', ''):
        from .nesting import parse_angles
        angles = parse_angles(spec.angles) or angles
    out, seen = [], set()
    corner = str(getattr(spec, 'corner', 'haut_gauche'))
    flip = (corner.endswith('droit'), corner.startswith('bas'))
    for mirror in (False, True) if getattr(spec, 'allow_mirror', False) else (False,):
        for a in angles:
            p = _Pose(leaves, a, center, cell, radius, bool(getattr(spec, 'in_holes', False)), flip, mirror)
            if p.key not in seen:
                seen.add(p.key)
                out.append(p)
            progress.check()
    return out


def _best(sheet: _Sheet, poses: list[_Pose]):
    """La pose qui monte le moins haut sur cette plaque, puis la plus à gauche ; à égalité, celle d'origine."""
    best = None
    for i, p in enumerate(poses):
        got = sheet.find(p)
        if got is not None:
            cand = (got[1] + p.mask.shape[1], got[0], i) if sheet.vertical else (got[0] + p.mask.shape[0], got[1], i)
            if best is None or cand < best[0]:
                best = (cand, p, got)
    return best


def _matrix(it: Item, pose: _Pose, plate: Plate, margin: float, cell: float, k: int, r: int, c: int,
            sheet: _Sheet | None = None, flip: tuple = (False, False)) -> Affine:
    from .nesting import PLATE_GAP
    if flip[0]:
        c = sheet.nx - c - pose.mask.shape[1]
    if flip[1]:
        r = sheet.ny - r - pose.mask.shape[0]
    bb = it.bbox()
    m = Affine.rotation(pose.angle, ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)) if pose.angle else Affine()
    if pose.mirror:
        m = m @ Affine.mirror_y((bb[0] + bb[2]) / 2)
    left = plate.x + k * (plate.width + PLATE_GAP) + margin + c * cell
    top = plate.y + plate.height - margin - r * cell
    return Affine.translation(left - pose.box[0], top - pose.box[3]) @ m


def _outside(region, box: tuple, cell: float, ny: int, nx: int, margin: float) -> np.ndarray:
    """Les cases où rien ne doit aller : hors de la forme (ses trous aussi), sur son bord, et à moins de `margin` de lui."""
    x0, _y0, _x1, y1 = box
    inside = np.zeros((ny, nx), dtype=bool)
    edge = np.zeros((ny, nx), dtype=bool)
    for c in region.contours:
        p = np.asarray(c.flatten(cell / 4.0), dtype=float)
        if len(p) < 2:
            continue
        inside ^= _fill(p, x0, y1, cell, (ny, nx))
        _mark(edge, np.vstack((p, p[:1])), x0, y1, cell)
    blocked = ~inside | edge
    radius = margin / cell + _DIAGONAL
    r = math.ceil(radius)
    s = (_next_size(ny + 2 * r + 1), _next_size(nx + 2 * r + 1))
    yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
    disc = (xx * xx + yy * yy < radius * radius).astype(float)
    grown = np.fft.irfft2(np.fft.rfft2(blocked.astype(float), s) * np.fft.rfft2(disc, s), s)
    return grown[r:r + ny, r:r + nx] > 0.5


def nest_shapes(items: list[Item], plate: Plate, spec):
    """Comme `nesting.nest`, selon la forme des objets. Exemplaires 0 : une plaque remplie.
    Avec `spec.region`, tout va dans cette forme, sur une seule « plaque » : ce qui n'y tient pas reste à part."""
    from .nesting import NestResult, _ordered, count_of
    res = NestResult()
    region = getattr(spec, 'region', None)
    margin = spec.margin
    if region is not None:
        rb = region.bbox()
        if not rb or rb[2] - rb[0] <= 0 or rb[3] - rb[1] <= 0:
            res.unplaced = list(items)
            return res
        plate = Plate(x=rb[0], y=rb[1], width=rb[2] - rb[0], height=rb[3] - rb[1])
        margin = 0.0
    W, H = plate.width - 2 * margin, plate.height - 2 * margin
    if W <= 0 or H <= 0:
        res.unplaced = list(items)
        return res
    cell = max(float(getattr(spec, 'precision', 0.5) or 0.5), MIN_PRECISION, max(W, H) / MAX_CELLS)
    nx, ny = max(1, int(W / cell)), max(1, int(H / cell))
    radius = max(float(spec.gap), 0.0) / cell + _DIAGONAL
    poses = {}
    for i, it in enumerate(items):
        progress.step(i, len(items), 'Imbrication : formes de l\'objet {0} sur {1}')
        got = _poses(it, spec, cell, radius)
        if got:
            poses[id(it)] = got
    usable = [it for it in items if id(it) in poses]
    fill = spec.counts is None and int(spec.copies) <= 0
    vertical = bool(spec.vertical)
    flip = (str(spec.corner).endswith('droit'), str(spec.corner).startswith('bas'))
    blocked = None
    if region is not None:
        blocked = _outside(region, rb, cell, ny, nx, max(float(spec.margin), 0.0))
        if flip[0]:
            blocked = blocked[:, ::-1]
        if flip[1]:
            blocked = blocked[::-1, :]

    def new_sheet() -> _Sheet:
        sh = _Sheet(ny, nx, vertical)
        if blocked is not None:
            sh.occupied = blocked.copy()
            sh.used = int(blocked.sum())
        return sh
    sheets = [new_sheet()] if fill or region is not None else []
    area = 0

    def place(it, sheet, k, found) -> None:
        nonlocal area
        _cand, p, (r, c) = found
        sheet.put(p, r, c)
        res.placed.append((it, _matrix(it, p, plate, margin, cell, k, r, c, sheet, flip)))
        res.sheets.append(k)
        area += p.area
        if p.angle:
            res.rotated += 1
        if p.mirror:
            res.mirrored += 1

    if fill:
        sheet = sheets[0]
        more = True
        while more and len(res.placed) < FILL_MAX:
            more = False
            for it in usable:
                found = _best(sheet, poses[id(it)])
                if found is not None:
                    place(it, sheet, 0, found)
                    more = True
                    progress.step(min(sheet.used, nx * ny - 1), nx * ny, '')
            progress.check()
        res.unplaced = [it for it in items if not any(p is it for p, _m in res.placed)]
    else:
        jobs = sorted((it for n, it in enumerate(items) if id(it) in poses for _ in range(count_of(spec, n))),
                      key=lambda it: -poses[id(it)][0].area)
        boxes = {id(it): it.bbox() for it in usable}
        jobs = _ordered(jobs, int(getattr(spec, 'order', 0)),
                        lambda it: (boxes[id(it)][2] - boxes[id(it)][0], boxes[id(it)][3] - boxes[id(it)][1]))
        last = None
        for ji, it in enumerate(jobs):
            progress.step(ji, len(jobs), 'Imbrication : objet {0} sur {1}')
            if last is not None and last is not it:
                for p in poses[id(last)]:
                    p.forget()                           # gardé pour les exemplaires suivants, pas au-delà : c'est lourd
            last = it
            for k, sheet in enumerate(sheets):
                found = _best(sheet, poses[id(it)])
                if found is not None:
                    place(it, sheet, k, found)
                    break
            else:
                if region is not None:
                    res.unplaced.append(it)
                    continue
                sheet = new_sheet()
                found = _best(sheet, poses[id(it)])
                if found is None:
                    res.unplaced.append(it)
                    continue
                sheets.append(sheet)
                place(it, sheet, len(sheets) - 1, found)
        seen = {id(it) for it, _m in res.placed}
        res.unplaced = list({id(x): x for x in res.unplaced if id(x) not in seen}.values())
    res.unplaced += [it for it in items if id(it) not in poses and not any(x is it for x in res.unplaced)]
    if getattr(spec, 'tighten', True):
        from .nesting_tight import tighten
        tighten(res, plate, spec, margin, cell, region)
    if region is not None:
        from . import pathops
        res.plates = 1 if res.placed else 0
        total = pathops.area(pathops.normalize(region))
        res.usage = area * cell * cell / total if res.placed and total > 0 else 0.0
        return res
    res.plates = sum(1 for s in sheets if s.used)
    res.usage = area * cell * cell / (res.plates * plate.width * plate.height) if res.plates else 0.0
    return res
