"""STEP (ISO 10303-21) : vue de dessus d'une pièce 3D, pour la gravure.

Lecteur repris de NeoDrive (`vectordrive/io/neostep`, même auteur) : faces
horizontales tournées vers le haut et leurs contours, un calque par
profondeur (« STEP Pz 5 »), trous verticaux dans le compte rendu,
assemblages placés, pièce couchée redressée. Les arcs restent des courbes.
Les courbes libres d'un « fil de fer » (`step_wire`) : un calque « STEP courbes ».
"""
from __future__ import annotations

import pathlib

from ..core.document import Document, Layer, Shape
from ..core.geom import Contour, Cubic, Line, Path, dist
from .neostep import stepread


def _contour(commandes) -> list[Contour]:
    out, cur = [], []
    pos = start = None
    for c in commandes:
        k = c[0]
        if k == 'M':
            if cur:
                out.append(Contour(cur, False))
            cur = []
            pos = start = (c[1], c[2])
        elif k == 'L':
            p = (c[1], c[2])
            if pos is not None and dist(pos, p) > 1e-12:
                cur.append(Line(pos, p))
            pos = p
        elif k == 'C':
            p = (c[5], c[6])
            cur.append(Cubic(pos, (c[1], c[2]), (c[3], c[4]), p))
            pos = p
        elif k == 'Z':
            if cur and start is not None and dist(pos, start) > 1e-9:
                cur.append(Line(pos, start))
            if cur:
                out.append(Contour(cur, True))
            cur = []
            pos = start
    if cur:
        out.append(Contour(cur, False))
    return out


def read(path, placement=None) -> Document:
    """Vue de dessus du STEP ; `placement` (core.placement3d) : la face
    choisie en haut, tournée et décalée comme sur la machine."""
    from ..core import placement3d as P3
    pl = placement if placement is not None else P3.Placement()
    rot = None if pl.face == '+Z' else P3.face_matrix(pl.face)
    calques, rapport = stepread.lire(str(path), orientation=rot)
    doc = Document(layers=[], source_path=str(path), source_format='step')
    for name, chemins in calques.items():
        items = []
        for ch in chemins:
            cs = _contour(getattr(ch, 'commandes', []) or [])
            if not cs and getattr(ch, 'points', None):
                from ..core.geom import polyline
                cs = [polyline(list(ch.points))]
            if cs:
                p2 = Path(cs)
                if abs(pl.rot) > 1e-12 or abs(pl.dx) > 1e-12 or abs(pl.dy) > 1e-12:
                    p2 = p2.transformed(pl.affine_xy())
                items.append(Shape(path=p2, extra={'step': 1}))     # vue de dessus du STEP (replaçable)
        if items:
            doc.layers.append(Layer(name=name, items=items))
    doc.report = list(getattr(rapport, 'notes', []))
    trous = getattr(rapport, 'trous', None)
    if trous:
        doc.report.append(f'{len(trous)} trou(s) vertical(aux) détecté(s)')
    from . import step_wire
    free, unread = step_wire.contours(path, rot)         # fil de fer : les courbes hors de toute face
    if free:
        moved = abs(pl.rot) > 1e-12 or abs(pl.dx) > 1e-12 or abs(pl.dy) > 1e-12
        items = [Shape(path=Path([c]).transformed(pl.affine_xy()) if moved else Path([c]), extra={'step': 1})
                 for c in free]
        doc.layers.append(Layer(name='STEP courbes', items=items))
        doc.report.append(f'{len(free)} courbe(s) libre(s) (fil de fer), en courbes exactes')
    if unread:
        doc.report.append(f'{unread} courbe(s) libre(s) d’un type non lu')
    if not doc.layers:
        doc.layers.append(Layer(name=pathlib.Path(path).stem))
    if placement is not None and not pl.is_identity():
        doc.extra[P3.KEY] = P3.to_dict(pl)
    return doc
