"""Arcs dans les programmes machine : les suites de segments d'un parcours
(avances à Z constant) qui suivent un cercle à `tol` près deviennent des arcs
(G2 / G3, Arc CW / CCW) — programmes bien plus courts, mouvements plus doux,
comme ceux de TypeEdit. Les parcours calculés par VectorDrive sont aplatis ;
seuls les programmes en profitent (l'affichage et la simulation gardent les
segments).

Écart garanti : chaque sommet d'origine est à moins de `tol` de l'arc, et
l'arc à moins de `tol` de chaque segment (flèche) — l'arc et la polyligne ne
s'écartent jamais de plus de `tol`. Un arc suit au moins `MIN_SEGMENTS`
segments, tourne toujours dans le même sens, fait moins d'un tour et son rayon
reste sous `MAX_RADIUS` (au-delà, les segments presque droits restent des
droites). Plongées, rampes (Z qui varie), rapides et arcs déjà présents
(parcours de TypeEdit) sont gardés tels quels."""
from __future__ import annotations

import copy
import math

import numpy as np

from .model import Move

#: un arc remplace au moins ce nombre de segments
MIN_SEGMENTS = 3
#: rayon au-delà duquel les segments restent des droites (mm)
MAX_RADIUS = 500.0
#: angle balayé au plus par un arc (rad) : jamais un tour entier
MAX_SWEEP = 1.9 * math.pi


def _circle(a, m, b):
    """Centre du cercle passant par trois points ; None s'ils sont alignés."""
    ax, ay = a
    bx, by = m
    cx, cy = b
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return None
    a2, b2, c2 = ax * ax + ay * ay, bx * bx + by * by, cx * cx + cy * cy
    ux = (a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / d
    uy = (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / d
    return ux, uy


def arc_of(P: np.ndarray, tol: float):
    """(cx, cy, horaire ?) de l'arc qui suit les points P (k, 2), ou None :
    cercle par le premier, le milieu et le dernier point ; tous les points à
    `tol` de lui, angles qui avancent toujours dans le même sens, moins d'un
    tour, flèche de chaque segment ≤ `tol`."""
    if len(P) < MIN_SEGMENTS + 1:
        return None
    c = _circle(P[0], P[len(P) // 2], P[-1])
    if c is None:
        return None
    d = P - np.asarray(c)
    r = np.hypot(d[:, 0], d[:, 1])
    R = float(r[0])
    if not (4 * tol < R < MAX_RADIUS) or float(np.abs(r - R).max()) > tol:
        return None
    ang = np.arctan2(d[:, 1], d[:, 0])
    da = np.diff(ang)
    da = (da + math.pi) % (2 * math.pi) - math.pi        # pas d'angle dans ]−π, π]
    if not ((da > 1e-12).all() or (da < -1e-12).all()):
        return None
    if abs(float(da.sum())) > MAX_SWEEP:
        return None
    e = np.abs(r - R)                                     # écart des sommets ; flèche de chaque segment
    if float((np.maximum(e[:-1], e[1:]) + R * (1.0 - np.cos(np.abs(da) / 2.0))).max()) > tol:
        return None
    return float(c[0]), float(c[1]), bool(da[0] < 0)


def fit_points(P: np.ndarray, tol: float) -> list:
    """Découpe de la polyligne P (n, 2) : [(j, None) droite jusqu'au point j,
    ou (j, (cx, cy, horaire)) arc jusqu'au point j], du point 0 au dernier.
    Arc le plus long possible depuis chaque point (allongement par doublement
    puis dichotomie : chaque arc gardé est vérifié)."""
    n = len(P)
    out = []
    i = 0
    while i < n - 1:
        j = i + MIN_SEGMENTS
        best = None
        if j < n:
            fit = arc_of(P[i:j + 1], tol)
            if fit is not None:
                best = (j, fit)
                lo, step, hi = j, MIN_SEGMENTS, None
                while lo < n - 1:
                    k = min(n - 1, lo + step)
                    f = arc_of(P[i:k + 1], tol)
                    if f is None:
                        hi = k
                        break
                    lo, best, step = k, (k, f), step * 2
                while hi is not None and hi - lo > 1:
                    mid = (lo + hi) // 2
                    f = arc_of(P[i:mid + 1], tol)
                    if f is None:
                        hi = mid
                    else:
                        lo, best = mid, (mid, f)
        if best is None:
            out.append((i + 1, None))
            i += 1
        else:
            out.append(best)
            i = best[0]
    return out


def _flush(out: list, run: list, start, tol: float) -> None:
    """Suite d'avances à Z constant (depuis `start`) : arcs et droites."""
    if len(run) < MIN_SEGMENTS:
        out.extend(run)
        return
    z = run[0].z
    P = np.array([start[:2]] + [(m.x, m.y) for m in run], dtype=float)
    for j, fit in fit_points(P, tol):
        if fit is None:
            out.append(run[j - 1])
        else:
            cx, cy, cw = fit
            out.append(Move('arc_cw' if cw else 'arc_ccw', float(P[j, 0]), float(P[j, 1]), z, cx, cy,
                            fin=bool(getattr(run[0], 'fin', False))))


def fit_moves(moves: list, tol: float) -> list:
    """Mouvements d'un parcours, les suites d'avances à Z constant ajustées en
    arcs (voir `fit_points`) ; le reste inchangé."""
    out: list = []
    run: list = []
    start = pos = None
    for m in moves:
        if m.kind == 'feed' and pos is not None and abs(m.z - pos[2]) < 1e-9:
            if run and bool(getattr(m, 'fin', False)) != bool(getattr(run[0], 'fin', False)):
                _flush(out, run, start, tol)             # une passe de finition : sa propre suite (son avance)
                run = []
            if not run:
                start = pos
            run.append(m)
        else:
            _flush(out, run, start, tol)
            run = []
            out.append(m)
        pos = (m.x, m.y, m.z)
    _flush(out, run, start, tol)
    return out


def fit_toolpaths(toolpaths: list, tol: float) -> list:
    """Copies des parcours, segments ajustés en arcs à `tol` près (mm) ; les
    mêmes parcours si `tol` ≤ 0."""
    if not tol or tol <= 0:
        return list(toolpaths)
    out = []
    for tp in toolpaths:
        c = copy.copy(tp)                                  # attributs ajoutés en route gardés
        c.moves = fit_moves(tp.moves, tol)
        out.append(c)
    return out
