"""Déplacer des faces d'un volume déjà fait, comme le `offset_faces` de SolidCraft
(`crates/kernel/src/polyhedron.rs`), mais sur un maillage : changer un diamètre, une profondeur de poche,
une épaisseur, ou déplacer un perçage, sans refaire la pièce.

Deux façons :
- le long de la normale : chaque face avance de la même distance, vers l'extérieur de la matière si
  elle est positive. Un trou voit donc son rayon diminuer.
- par un vecteur : les faces choisies se déplacent en bloc. Les faces voisines ne bougent pas de leur
  plan, elles s'allongent ou raccourcissent.

Les sommets obéissent à la même règle que pour la dépouille (core.draft3d) : rester sur toutes les
faces qui les entourent. Les refus aussi : un côté qui se retourne, des contours qui se coupent.
"""
from __future__ import annotations

import numpy as np

from . import draft3d as DR
from . import solids as SO

MODES = ('normal', 'vector')
MAX_MOVE = 100000.0


def _shift_normal(groups: dict, chosen: set, distance: float) -> tuple:
    rows = np.array(list(groups.values()))
    rhs = np.array([distance if f in chosen else 0.0 for f in groups])
    s = np.linalg.lstsq(rows, rhs, rcond=1e-6)[0]
    return s, float(np.abs(rows @ s - rhs).max())


def _shift_vector(groups: dict, chosen: set, vec: np.ndarray) -> tuple:
    """Le sommet suit le vecteur, à ce qu'il faut près pour rester sur les faces qui ne bougent pas. Le plus
    petit écart au vecteur, et non le plus petit déplacement : le bord d'un trou glisse le long de sa
    paroi, sinon le cercle s'écrase."""
    rows = np.array(list(groups.values()))
    rhs = np.array([0.0 if f in chosen else -float(n @ vec) for f, n in groups.items()])
    s = np.linalg.lstsq(rows, rhs, rcond=1e-6)[0]
    return s + vec, float(np.abs(rows @ s - rhs).max())


def apply(solid, values: dict):
    """Le volume aux faces déplacées. `values` : mode (MODES), distance (normale), dx, dy, dz (vecteur),
    picks (de draft3d.pick_of, un par face)."""
    mode = values.get('mode', 'normal')
    if mode not in MODES:
        raise DR.DraftError('façon de déplacer inconnue')
    picks = values.get('picks') or []
    if not picks:
        raise DR.DraftError('aucune face choisie')
    distance = float(values.get('distance', 0.0))
    vec = np.array([float(values.get(k, 0.0)) for k in ('dx', 'dy', 'dz')])
    size = abs(distance) if mode == 'normal' else float(np.linalg.norm(vec))
    if size == 0.0:
        raise DR.DraftError('déplacement nul')
    if size > MAX_MOVE or not np.isfinite(size):
        raise DR.DraftError('déplacement trop grand')
    faces = DR._faces(solid)
    tris, face_of, nrm = faces
    chosen = {DR.find(faces, q) for q in picks}
    t = np.asarray(solid.tris, dtype=np.int64)
    v = np.asarray(solid.verts, dtype=np.float64)
    real = DR._areas(tris) > DR.SLIVER
    out = v.copy()
    worst = 0.0
    for x, groups in DR._around(t, face_of, nrm, real, chosen).items():
        if mode == 'normal':
            s, left = _shift_normal(groups, chosen, distance)
        else:
            s, left = _shift_vector(groups, chosen, vec)
        out[x] = v[x] + s
        worst = max(worst, left)
    return DR.finish(solid, out, worst, face_of, real)
