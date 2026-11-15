"""Trajectoires 3D recomposées : celles de chaque prise (pièce retournée,
face vers l'outil `setup_face`) et de chaque corps usiné seul (`body3d`)
ramenées sur la pièce posée comme le dessin — toutes ensemble, pour voir
que chaque face de chaque pièce est usinée et d'où vient l'outil.

Une prise usine la pièce posée par `mill3d.side_placement` (rotation R,
décalage d), le haut de la pièce posée à Z 0 : un point p de ses
trajectoires est, dans le fichier, Rᵀ·(p + (0, 0, haut) − d). Le même
point dans la prise du dessin (R₀, d₀, haut₀) : R₀·… + d₀ − (0, 0, haut₀).
Les arcs sont aplatis (une prise retournée les sortirait de leur plan)."""
from __future__ import annotations

import copy

import numpy as np

from . import mill3d
from .model import Move, arc_points


def frame(doc, path: str, face: str = '', body: int = -1):
    """(R, d, haut) de la prise (`face`, `body`) de la pièce `path` (vide :
    les volumes du dessin) ; None : pièce absente ou illisible."""
    from ..core import placement3d as P3
    try:
        if path:
            pl = mill3d.side_placement(doc, path, face, body)
            m = mill3d.load_model(doc, path, face, body)
        else:
            pl = P3.Placement(face) if face and face != '+Z' else None
            m = mill3d.volumes_model(doc, face, body, edges=False)   # le haut seulement
    except Exception:                                      # noqa: BLE001 — fichier tiers
        return None
    if m is None or not len(getattr(m, 'triangles', ())):
        return None
    R = pl.rotation() if pl is not None else np.eye(3)
    d = np.array([pl.dx, pl.dy, 0.0]) if pl is not None else np.zeros(3)
    return np.asarray(R, dtype=np.float64), d, float(m.bounds()[5])


def transform(doc, op, frames: dict | None = None) -> tuple[np.ndarray, np.ndarray] | None:
    """(A 3×3, b 3) : point des trajectoires de la prise de `op` → point des
    trajectoires de la prise du dessin (même pièce) ; None : sa prise est
    celle du dessin, ou la pièce est illisible. `frames` : prises déjà
    calculées (gardées d'un appel à l'autre)."""
    face, body = getattr(op, 'setup_face', '') or '', int(getattr(op, 'body3d', -1))
    if (face, body) == ('', -1):
        return None
    path = mill3d.model_path(doc, op)
    body = mill3d.op_body(doc, op)                         # volume du dessin : celui de l'objet gardé
    if body is None:
        return None
    frames = {} if frames is None else frames
    for k in ((face, body), ('', -1)):
        if (path, *k) not in frames:
            frames[(path, *k)] = frame(doc, path, *k)
    src, ref = frames[(path, face, body)], frames[(path, '', -1)]
    if src is None or ref is None:
        return None
    (R, d, top), (R0, d0, top0) = src, ref
    A = R0 @ R.T
    b = R0 @ (R.T @ (np.array([0.0, 0.0, top]) - d)) + d0 - np.array([0.0, 0.0, top0])
    return A, b


def flatten(moves) -> list[tuple[str, float, float, float]]:
    """Mouvements → (nature, x, y, z) en lignes droites (arcs aplatis, 0,01 mm)."""
    out, prev = [], None
    for m in moves:
        if m.is_arc and prev is not None:
            out += [('feed', *p) for p in arc_points(prev, m, 0.01)]
        else:
            out.append((m.kind, m.x, m.y, m.z))
        prev = (m.x, m.y, m.z)
    return out


def reassemble(doc, toolpaths, operations) -> list:
    """Les trajectoires `toolpaths`, celles d'une autre prise ou d'un corps
    seul ramenées sur la pièce posée comme le dessin (copies, arcs
    aplatis) ; les autres telles quelles. Une prise illisible : ses
    trajectoires sont laissées de côté (rien de faux à l'écran)."""
    ops = {o.id: o for o in operations}
    cache: dict = {}
    frames: dict = {}                                      # prise du dessin calculée une fois
    out = []
    for tp in toolpaths:
        op = ops.get(tp.op_id)
        if op is None or ((getattr(op, 'setup_face', '') or ''), int(getattr(op, 'body3d', -1))) == ('', -1):
            out.append(tp)
            continue
        key = (mill3d.model_path(doc, op), op.setup_face or '', int(op.body3d), str(op.body3d_ref))
        if key not in cache:
            cache[key] = transform(doc, op, frames)
        T = cache[key]
        if T is None:
            continue
        A, b = T
        flat = flatten(tp.moves)
        if not flat:
            continue
        P = np.asarray([f[1:] for f in flat], dtype=np.float64) @ A.T + b
        c = copy.copy(tp)
        c.moves = [Move(k, float(p[0]), float(p[1]), float(p[2])) for (k, *_xyz), p in zip(flat, P)]
        c.cycles = []
        out.append(c)
    return out
