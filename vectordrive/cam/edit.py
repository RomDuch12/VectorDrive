"""Retouches de parcours : inverser, translater."""
from __future__ import annotations

import copy

from .model import Move, Toolpath


def reversed_toolpath(tp: Toolpath) -> Toolpath:
    """Même trajet parcouru à l'envers : chaque mouvement mène au point
    d'où partait le suivant ; un arc garde son centre et change de sens."""
    out = copy.copy(tp)
    out.warnings = list(tp.warnings)
    ms = tp.moves
    if len(ms) < 2:
        out.moves = list(ms)
        return out
    flip = {'arc_cw': 'arc_ccw', 'arc_ccw': 'arc_cw'}
    rev = [Move('rapid', ms[-1].x, ms[-1].y, ms[-1].z)]
    for k in range(len(ms) - 1, 0, -1):
        m, prev = ms[k], ms[k - 1]
        rev.append(Move(flip.get(m.kind, m.kind), prev.x, prev.y, prev.z, m.cx, m.cy, fin=m.fin))
    out.moves = rev
    return out


def translated_toolpath(tp: Toolpath, dx: float, dy: float, dz: float = 0.0) -> Toolpath:
    out = copy.copy(tp)
    out.moves = [Move(m.kind, m.x + dx, m.y + dy, m.z + dz, m.cx + dx, m.cy + dy, fin=m.fin) for m in tp.moves]
    return out
