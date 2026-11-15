"""Contrôle du programme écrit : chaque fichier du post-processeur est relu
(cam.ncread : ISO, SimPL et les autres lecteurs) et ses mouvements de coupe
comparés aux parcours dont il vient, dans les deux sens — le programme ne
coupe pas là où aucun parcours ne passe, aucun parcours ne manque au
programme. Un écart au-delà de `TOL` est signalé avec sa position : arc
écrit dans le mauvais sens, centre mal placé, mouvement perdu, cote mal
formatée… Ce que la relecture ne peut pas reproduire exactement est laissé
de côté (contrôle sauté et dit) : cycles de la machine (trous, texte,
instructions), axe rotatif, laser en morceaux."""
from __future__ import annotations

import math

import numpy as np

from .model import arc_points

#: écart toléré entre le programme relu et les parcours (mm) : arcs ajustés (0,01), arrondis des cotes
TOL = 0.05
#: pas d'échantillonnage le long des mouvements de coupe (mm)
STEP = 0.5
#: au-delà, les points sont pris un sur k (le contrôle reste rapide sur les très gros programmes)
MAX_POINTS = 300_000


def cut_segments(toolpaths) -> tuple[np.ndarray, np.ndarray]:
    """(départs, arrivées) des segments de coupe (avances, plongées, arcs aplatis)."""
    a, b = [], []
    for tp in toolpaths:
        prev = None
        for m in tp.moves:
            p = (m.x, m.y, m.z)
            if prev is not None and m.kind != 'rapid':
                pts = [prev] + (list(arc_points(prev, m, 0.005)) if m.is_arc else [p])
                for q0, q1 in zip(pts, pts[1:]):
                    a.append(q0)
                    b.append(q1)
            prev = p
    if not a:
        return np.zeros((0, 3)), np.zeros((0, 3))
    return np.asarray(a, dtype=float), np.asarray(b, dtype=float)


def samples(A: np.ndarray, B: np.ndarray, step: float = STEP) -> np.ndarray:
    """Points tous les `step` mm le long des segments (bouts compris)."""
    if not len(A):
        return np.zeros((0, 3))
    L = np.linalg.norm(B - A, axis=1)
    n = np.maximum(1, np.ceil(L / step).astype(int))
    idx = np.repeat(np.arange(len(A)), n + 1)
    t = np.concatenate([np.linspace(0.0, 1.0, k + 1) for k in n])
    P = A[idx] + (B[idx] - A[idx]) * t[:, None]
    if len(P) > MAX_POINTS:
        P = P[::int(math.ceil(len(P) / MAX_POINTS))]
    return P


def deviation(P: np.ndarray, A: np.ndarray, B: np.ndarray, r: float) -> tuple[float, np.ndarray | None]:
    """(plus grand écart 3D des points P aux segments, point le plus loin) ;
    un point à plus de `r` de tout segment en XY compte pour l'infini."""
    import shapely
    if not len(P):
        return 0.0, None
    if not len(A):
        return math.inf, P[0]
    tree = shapely.STRtree(shapely.linestrings(np.stack([A[:, :2], B[:, :2]], axis=1)))
    pi, si = tree.query(shapely.points(P[:, :2]), predicate='dwithin', distance=r)
    best = np.full(len(P), math.inf)
    if len(pi):
        a, b, p = A[si], B[si], P[pi]
        d = b - a
        L2 = (d * d).sum(axis=1)
        t = np.clip(((p - a) * d).sum(axis=1) / np.where(L2 > 0, L2, 1.0), 0.0, 1.0)
        dist = np.linalg.norm(p - (a + t[:, None] * d), axis=1)
        np.minimum.at(best, pi, dist)
    k = int(np.argmax(best))
    return float(best[k]), P[k]


#: extensions des programmes relus (ISO, Heidenhain…) ; s'y ajoutent celles des lecteurs des plugins (SimPL)
PROGRAM_EXT = ('.nc', '.iso', '.tap', '.ngc', '.gcode', '.gc', '.cnc', '.mpf', '.spf', '.eia', '.din', '.ptp', '.h')


def is_program(name: str) -> bool:
    """Fichier de mouvements à relire (pas le .CLJOB, XML, ni les consignes)."""
    import pathlib
    import re
    ext = pathlib.Path(name).suffix.lower()
    if ext in PROGRAM_EXT or re.fullmatch(r'\.u\d\d', ext):
        return True
    try:
        from ..plugins import REGISTRY
        return any(ext in [e.lower() for e in exts or ()] for _l, exts, _r, _s in REGISTRY.nc_readers)
    except Exception:                                    # registre des plugins indisponible
        return False


#: cycles que la machine exécute elle-même (programme SimPL) : la relecture n'en donne qu'une approximation
CYCLES = ('Thread', 'DrillMilling', 'Drill ', 'CircleCavity', 'RectangleCavity', 'CircleFromMid', 'RectFromMid',
          'RectangleFace', 'CircleFace', 'Engrave', 'Pattern::', 'G81', 'G82', 'G83', 'G84', 'G85', 'G86', 'G87',
          'G88', 'G89', 'CYCL DEF')


def skip_reason(toolpaths, setup, texts) -> str:
    """Pourquoi la relecture ne peut pas être comparée exactement ('' : comparable)."""
    import re
    if getattr(setup, 'laser_tiles', False):
        return 'laser en morceaux (pièce recentrée pour chaque morceau)'
    if any(re.search(r'(?m)(?:^|\s)A[=\s]?[-+]?\d', t) for t in texts):
        return 'axe rotatif'
    if any(c in t for t in texts for c in CYCLES):
        return 'cycles exécutés par la machine (trous, poches, texte) écrits tels quels'
    return ''


def verify(files, toolpaths, setup, origin=None, tol: float = TOL) -> list[str]:
    """Avertissements du contrôle du programme écrit : fichiers `files`
    [(nom, texte)] du post-processeur, parcours d'origine (avant le décalage
    de l'origine `origin`, que le contrôle refait)."""
    from . import ncread
    from .post import shifted
    tps = [tp for tp in toolpaths if tp.moves]
    files = [(n, t) for n, t in files if is_program(n)]
    if not tps or not files:
        return []
    why = skip_reason(tps, setup, [t for _n, t in files])
    if why:
        return [f'programme écrit : contrôle par relecture sauté ({why})']
    read = []
    for name, text in files:
        try:
            tp = ncread.read(text, name)
        except Exception as ex:                          # noqa: BLE001 — un lecteur en défaut ne bloque rien
            return [f'programme écrit : relecture impossible de {name} ({ex})']
        if any(m.kind != 'rapid' for m in tp.moves):
            read.append(tp)
    if not read:
        return [f'programme écrit : aucun mouvement de coupe relu dans {", ".join(n for n, _t in files)}']
    src = shifted(tps, origin) if origin is not None else tps
    A, B = cut_segments(src)
    C, D = cut_segments(read)
    out = []
    d1, p1 = deviation(_in_material(samples(C, D)), A, B, max(tol, 1.0))
    if d1 > tol:
        out.append(_message('le programme coupe à', d1, p1, 'des parcours'))
    d2, p2 = deviation(_in_material(samples(A, B)), C, D, max(tol, 1.0))
    if d2 > tol:
        out.append(_message('un parcours passe à', d2, p2, 'du programme relu (mouvement absent ?)'))
    return out


def _in_material(P: np.ndarray) -> np.ndarray:
    """Les points au niveau de la matière ou dessous (Z ≤ 0) : une descente en l'air ne coupe rien
    (le laser n'écrit que ses traits à Z = 0)."""
    return P[P[:, 2] <= 1e-6] if len(P) else P


def _message(what: str, d: float, p, other: str) -> str:
    dist = 'plus de 1 mm' if not math.isfinite(d) else f'{d:.3f} mm'.replace('.', ',')
    where = '' if p is None else f' (X {p[0]:.3f} Y {p[1]:.3f} Z {p[2]:.3f})'.replace('.', ',')
    return f'programme écrit, CONTRÔLE : {what} {dist} {other}{where} — vérifier le post-processeur'
