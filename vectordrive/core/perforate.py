"""Perforation : trous ronds en quinconce (rangées à 60°, une sur deux
décalée d'un demi-pas) ou en grille carrée dans les contours fermés d'un
tracé (règle pair-impair : les découpes restent pleines de vide), gardés à
une marge des bords, des découpes et de traits ouverts donnés (axes de
pli d'un développé).

Porté de SolidCraft (MIT OR Apache-2.0, © 2026 SolidCraft contributors,
utilisé sous MIT) — `crates/doc/src/sheet.rs` (`perforation_holes`,
SheetPerforate) : rangées depuis le coin bas gauche de l'encombrement plus
marge et rayon, trou gardé s'il est à marge + rayon de chaque bord ;
ajouté : grille centrée dans l'encombrement (marges égales).
"""
from __future__ import annotations

import math

import numpy as np

#: dispositions des trous
PATTERNS = {'quinconce': 'Quinconce (60°)', 'carre': 'Grille carrée'}

#: départ des rangées : champ centré (marges égales), ou depuis le coin bas gauche (comme SolidCraft) ou bas droit
ALIGNS = {'centre': 'Centrées', 'gauche': 'Depuis la gauche', 'droite': 'Depuis la droite'}

#: au-delà, refus (un pas trop fin pour la surface)
MAX_HOLES = 200_000


def _segments(contours, tol: float) -> np.ndarray:
    """Segments (M × 2 × 2) des contours aplatis, fermés bouclés."""
    out = []
    for c in contours:
        pts = np.asarray(c.flatten(tol), dtype=float)
        if c.closed and len(pts) > 1 and not np.allclose(pts[0], pts[-1]):
            pts = np.vstack([pts, pts[:1]])
        if len(pts) >= 2:
            out.append(np.stack([pts[:-1], pts[1:]], axis=1))
    return np.concatenate(out) if out else np.zeros((0, 2, 2))


def _inside(P: np.ndarray, edges: np.ndarray, chunk: int = 4096) -> np.ndarray:
    """Points dans la matière : croisements pair-impair d'une demi-droite +X."""
    a, b = edges[:, 0], edges[:, 1]
    out = np.zeros(len(P), dtype=bool)
    for i in range(0, len(P), chunk):
        x, y = P[i:i + chunk, :1], P[i:i + chunk, 1:]
        cross = (a[:, 1] > y) != (b[:, 1] > y)
        with np.errstate(divide='ignore', invalid='ignore'):
            xi = a[:, 0] + (y - a[:, 1]) * (b[:, 0] - a[:, 0]) / (b[:, 1] - a[:, 1])
        out[i:i + chunk] = (cross & (x < xi)).sum(axis=1) % 2 == 1
    return out


def _clearance(P: np.ndarray, segs: np.ndarray, chunk: int = 2048) -> np.ndarray:
    """Distance de chaque point au segment le plus proche."""
    out = np.full(len(P), np.inf)
    if not len(segs):
        return out
    a, d = segs[:, 0], segs[:, 1] - segs[:, 0]
    ll = np.maximum((d * d).sum(axis=1), 1e-300)
    for i in range(0, len(P), chunk):
        q = P[i:i + chunk, None, :]
        t = np.clip(((q - a) * d).sum(axis=2) / ll, 0.0, 1.0)
        out[i:i + chunk] = np.linalg.norm(q - (a + d * t[..., None]), axis=2).min(axis=1)
    return out


def holes(path, diameter: float, pitch: float, margin: float | None = None, square: bool = False, keep_clear=(),
          align: str = 'centre', tol: float = 0.02) -> np.ndarray:
    """Centres (N × 2) des trous de `diameter` au pas `pitch` (entre axes)
    dans les contours fermés de `path`, à `margin` (défaut : le diamètre)
    de leurs bords et des contours ouverts `keep_clear`. `align` (ALIGNS) :
    grille centrée dans l'encombrement, ou rangées depuis le bas et la
    gauche ou la droite."""
    d, p = float(diameter), float(pitch)
    if not (d > 0 and p > d):
        raise ValueError('perforation : diamètre positif, pas plus grand que le diamètre')
    m = d if margin is None else float(margin)
    if m < 0:
        raise ValueError('perforation : marge négative')
    if align not in ALIGNS:
        raise ValueError(f'perforation : départ inconnu {align}')
    edges = _segments([c for c in path.contours if c.closed and c.segments], tol)
    if not len(edges):
        raise ValueError('perforation : aucun contour fermé')
    obstacles = np.concatenate([edges, _segments([c for c in keep_clear if c.segments], tol)])
    clear = d / 2 + m
    lo, hi = edges.reshape(-1, 2).min(axis=0), edges.reshape(-1, 2).max(axis=0)
    dy = p if square else p * math.sqrt(3) / 2
    rows = int(math.floor((hi[1] - lo[1] - 2 * clear) / dy + 1e-9)) + 1
    cols = int(math.floor((hi[0] - lo[0] - 2 * clear) / p + 1e-9)) + 1
    if rows <= 0 or cols <= 0:
        return np.zeros((0, 2))
    if rows * cols > MAX_HOLES:
        raise ValueError(f'perforation : plus de {MAX_HOLES} trous, pas trop fin')
    span = hi - lo - 2 * clear
    ox, oy = ((span[0] - (cols - 1) * p) / 2, (span[1] - (rows - 1) * dy) / 2) if align == 'centre' else (0.0, 0.0)
    pts = []
    for r in range(rows):
        y = lo[1] + clear + oy + r * dy
        shift = ox + (p / 2 if not square and r % 2 else 0.0)
        n = int(math.floor((span[0] - shift) / p + 1e-9)) + 1
        steps = shift + p * np.arange(max(n, 0))
        xs = hi[0] - clear - steps if align == 'droite' else lo[0] + clear + steps
        pts.append(np.column_stack([xs, np.full(len(xs), y)]))
    P = np.concatenate(pts) if pts else np.zeros((0, 2))
    if not len(P):
        return P
    P = P[_inside(P, edges)]
    return P[_clearance(P, obstacles) >= clear - 1e-9]


def region_area(path, tol: float = 0.02) -> float:
    """Aire de la matière des contours fermés (pair-impair)."""
    rings = [np.asarray(c.flatten(tol), dtype=float) for c in path.contours if c.closed and c.segments]
    rings = [r for r in rings if len(r) >= 3]
    total = 0.0
    for i, r in enumerate(rings):
        x, y = r[:, 0], r[:, 1]
        a = abs(0.5 * float((x * np.roll(y, -1) - np.roll(x, -1) * y).sum()))
        others = [o for j, o in enumerate(rings) if j != i]
        depth = sum(bool(_inside(r[:1], _segments_from(o))[0]) for o in others)
        total += -a if depth % 2 else a
    return total


def _segments_from(ring: np.ndarray) -> np.ndarray:
    pts = np.vstack([ring, ring[:1]])
    return np.stack([pts[:-1], pts[1:]], axis=1)


def perforate(path, diameter: float, pitch: float, margin: float | None = None, square: bool = False,
              keep_clear=(), align: str = 'centre', tol: float = 0.02):
    """(tracé des trous, nombre, part ajourée de la matière) — voir holes."""
    from .geom import Path, circle
    P = holes(path, diameter, pitch, margin, square, keep_clear, align, tol)
    r = float(diameter) / 2
    area = region_area(path, tol)
    ratio = len(P) * math.pi * r * r / area if area > 0 else 0.0
    return Path([circle((float(x), float(y)), r) for x, y in P]), len(P), ratio
