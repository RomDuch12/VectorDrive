"""Placement d'une pièce 3D (STEP, STL, 3D XML) sur la machine : quelle
face est tournée vers le haut (vers l'outil), quelle rotation autour de Z,
où sur la plaque. Le même placement sert partout : la vue de dessus en 2D
(relue avec cette orientation), le modèle 3D, l'usinage 3D (surface 3D),
les trajectoires montrées sur la pièce.

Gardé dans `Document.extra['placement3d']` : {face, rot, mode, dx, dy}.
La pièce est d'abord redressée comme à la lecture (axe « haut » deviné),
puis tournée pour mettre `face` en haut, tournée de `rot` degrés autour de
Z, puis déplacée de (dx, dy).

`face` : une des six faces des axes ('+Z', '-Z', '+X'…, tournée vers
l'outil), ou 'n:x,y,z' — la pièce **posée sur une face plane** quelconque,
de normale sortante (x, y, z) dans le repère de la pièce redressée : cette
face en bas, le dessus vers l'outil (`rest_faces` propose les faces d'appui
stables, `align_rot` la rotation qui aligne la pièce sur les axes).

Un corps de la pièce peut être positionné à part de l'ensemble pour son
usinage (pièce d'un moule tenue seule) : `Document.extra['placement3d_corps']`
{« n° du corps » : {face, rot, mode, dx, dy}} (`body_of`, `set_body`).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np

KEY = 'placement3d'
#: placements propres des corps positionnés à part : {« n° » : {face, rot, mode, dx, dy}}
KEY_BODIES = 'placement3d_corps'
#: face tournée vers le haut → rotation (3×3) appliquée à la pièce redressée
FACES = {
    '+Z': np.eye(3),
    '-Z': np.array([[1.0, 0, 0], [0, -1.0, 0], [0, 0, -1.0]]),     # retournée (dessous vers l'outil)
    '+X': np.array([[0, 0, -1.0], [0, 1.0, 0], [1.0, 0, 0]]),
    '-X': np.array([[0, 0, 1.0], [0, 1.0, 0], [-1.0, 0, 0]]),
    '+Y': np.array([[1.0, 0, 0], [0, 0, -1.0], [0, 1.0, 0]]),
    '-Y': np.array([[1.0, 0, 0], [0, 0, 1.0], [0, -1.0, 0]]),
}
FACE_LABELS = {'+Z': 'Dessus (comme lue)', '-Z': 'Dessous (pièce retournée)', '+X': 'Côté +X', '-X': 'Côté −X',
               '+Y': 'Côté +Y (arrière)', '-Y': 'Côté −Y (avant)'}
#: face « posée sur une face plane » : 'n:x,y,z' (normale sortante de la face d'appui)
PREFIX = 'n:'
#: écart (°) sous lequel une normale d'appui est celle d'un axe (une des six faces)
AXIS_DEG = 0.5


def normal_of(face: str):
    """Normale d'appui (unitaire) d'une face 'n:x,y,z', sinon None."""
    if not isinstance(face, str) or not face.startswith(PREFIX):
        return None
    try:
        v = np.array([float(c) for c in face[len(PREFIX):].split(',')], dtype=np.float64)
    except ValueError:
        return None
    if v.shape != (3,) or not np.isfinite(v).all() or np.linalg.norm(v) < 1e-9:
        return None
    return v / np.linalg.norm(v)


def rest_matrix(n) -> np.ndarray:
    """Rotation (3×3) qui pose la pièce sur la face de normale sortante
    `n` : n devient (0, 0, −1) — la face d'appui en bas."""
    n = np.asarray(n, dtype=np.float64)
    n = n / np.linalg.norm(n)
    t = np.array([0.0, 0.0, -1.0])
    v = np.cross(n, t)
    c, s = float(n @ t), float(np.linalg.norm(v))
    if s < 1e-12:
        return np.eye(3) if c > 0 else FACES['-Z'].copy()
    K = np.array([[0.0, -v[2], v[1]], [v[2], 0.0, -v[0]], [-v[1], v[0], 0.0]])
    return np.eye(3) + K + K @ K * ((1.0 - c) / (s * s))


def face_for_rest(n) -> str:
    """Face du placement qui pose la pièce sur la face de normale sortante
    `n` : une des six si n suit un axe (à `AXIS_DEG` près), sinon 'n:x,y,z'."""
    n = np.asarray(n, dtype=np.float64)
    n = n / np.linalg.norm(n)
    lim = math.cos(math.radians(AXIS_DEG))
    for key, R in FACES.items():
        if -float((R @ n)[2]) >= lim:
            return key
    return PREFIX + ','.join(f'{c:.6f}' for c in n)


def face_matrix(face: str) -> np.ndarray:
    """Rotation de la face du placement (une des six, ou posée sur une face plane)."""
    if face in FACES:
        return FACES[face]
    n = normal_of(face)
    return rest_matrix(n) if n is not None else FACES['+Z']


def face_label(face: str) -> str:
    return FACE_LABELS.get(face, 'Posée sur une face plane')


def align_rot(points) -> float:
    """Rotation autour de Z (°, dans ]−90, 90]) qui rend le plus petit
    rectangle englobant des points (vue de dessus) parallèle aux axes, son
    grand côté suivant X."""
    from shapely.geometry import MultiPoint
    a = np.asarray(points, dtype=np.float64).reshape(-1, np.shape(points)[-1])[:, :2]
    if len(a) < 3:
        return 0.0
    rect = MultiPoint([tuple(p) for p in a]).minimum_rotated_rectangle
    if rect.geom_type != 'Polygon':
        return 0.0
    c = list(rect.exterior.coords)[:3]
    e1 = (c[1][0] - c[0][0], c[1][1] - c[0][1])
    e2 = (c[2][0] - c[1][0], c[2][1] - c[1][1])
    e = e1 if math.hypot(*e1) >= math.hypot(*e2) - 1e-9 else e2
    rot = -math.degrees(math.atan2(e[1], e[0]))
    while rot <= -90.0 + 1e-9:
        rot += 180.0
    while rot > 90.0 + 1e-9:
        rot -= 180.0
    return 0.0 if abs(rot) < 1e-6 else round(rot, 4)


def rest_faces(model, count: int = 8, min_frac: float = 0.002) -> list:
    """Faces planes sur lesquelles la pièce tient posée (toute la pièce
    d'un même côté de leur plan), dans le repère de la pièce redressée :
    [(face du placement, aire mm², numéro de face)], de la plus grande à la
    plus petite ; faces coplanaires réunies."""
    t = np.asarray(model.triangles, dtype=np.float64).reshape(-1, 3, 3)
    if not len(t):
        return []
    fid = np.asarray(model.face_ids(), dtype=np.int64)
    cr = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    A = 0.5 * np.linalg.norm(cr, axis=1)
    nf = int(fid.max()) + 1
    area = np.bincount(fid, weights=A, minlength=nf)
    nsum = np.stack([np.bincount(fid, weights=0.5 * cr[:, k], minlength=nf) for k in range(3)], axis=1)
    ln = np.linalg.norm(nsum, axis=1)
    planar = (area > max(1e-9, min_frac * A.sum())) & (ln >= area * math.cos(math.radians(1.0)))
    cand = np.flatnonzero(planar)
    cand = cand[np.argsort(-area[cand])][:60]
    pts = np.unique(np.round(t.reshape(-1, 3), 5), axis=0)
    tol = max(0.01, 1e-4 * float(np.linalg.norm(pts.max(axis=0) - pts.min(axis=0))))
    seen: dict = {}
    for f in cand:
        n = nsum[f] / ln[f]
        d = float((t[fid == f].reshape(-1, 3) @ n).mean())
        proj = pts @ n
        if proj.max() <= d + tol:
            out = n                                        # normale sortante : toute la pièce derrière
        elif proj.min() >= d - tol:
            out, d = -n, -d                                # maillage retourné
        else:
            continue                                       # de la matière des deux côtés : pas d'appui
        key = face_for_rest(out)
        k2 = (key, round(d, 2))
        if k2 in seen:
            seen[k2][1] += float(area[f])
        else:
            seen[k2] = [key, float(area[f]), int(f)]
    return sorted((tuple(v) for v in seen.values()), key=lambda r: -r[1])[:count]


MODES = {'fichier': 'Coordonnées du fichier', 'centre': 'Centrée sur la plaque',
         'coin': 'Dans le coin bas-gauche de la plaque', 'origine': 'Centrée sur l\'origine', 'libre': 'Décalage libre'}


@dataclass
class Placement:
    face: str = '+Z'
    rot: float = 0.0
    mode: str = 'fichier'
    dx: float = 0.0
    dy: float = 0.0

    def is_identity(self) -> bool:
        return self.face == '+Z' and abs(self.rot) < 1e-12 and abs(self.dx) < 1e-12 and abs(self.dy) < 1e-12

    def rotation(self) -> np.ndarray:
        """3×3 : face vers le haut, puis rotation autour de Z."""
        t = math.radians(self.rot)
        rz = np.array([[math.cos(t), -math.sin(t), 0], [math.sin(t), math.cos(t), 0], [0, 0, 1.0]])
        return rz @ face_matrix(self.face)

    def apply(self, pts) -> np.ndarray:
        """Points (…, 3) placés."""
        a = np.asarray(pts, dtype=np.float64)
        out = a.reshape(-1, 3) @ self.rotation().T
        out[:, 0] += self.dx
        out[:, 1] += self.dy
        return out.reshape(a.shape)

    def affine_xy(self):
        """Partie plane (rotation autour de Z puis décalage) : pour le dessin
        2D relu avec la face choisie déjà en haut."""
        from .geom import Affine
        return Affine.translation(self.dx, self.dy) @ Affine.rotation(self.rot)


def of(doc) -> Placement:
    d = (getattr(doc, 'extra', {}) or {}).get(KEY)
    if not isinstance(d, dict):
        return Placement()
    try:
        return Placement(**{k: d[k] for k in ('face', 'rot', 'mode', 'dx', 'dy') if k in d})
    except TypeError:
        return Placement()


def to_dict(p: Placement) -> dict:
    return asdict(p)


def from_dict(d) -> Placement | None:
    """Placement gardé (`to_dict`), ou None (vide, illisible)."""
    if not isinstance(d, dict) or not d:
        return None
    try:
        return Placement(**{k: d[k] for k in ('face', 'rot', 'mode', 'dx', 'dy') if k in d})
    except TypeError:
        return None


def body_of(doc, body: int) -> Placement | None:
    """Placement propre du corps `body` (positionné à part de l'ensemble pour
    son usinage) ; None : posé comme l'ensemble."""
    if body is None or int(body) < 0:
        return None
    d = ((getattr(doc, 'extra', {}) or {}).get(KEY_BODIES) or {}).get(str(int(body)))
    if not isinstance(d, dict):
        return None
    try:
        return Placement(**{k: d[k] for k in ('face', 'rot', 'mode', 'dx', 'dy') if k in d})
    except TypeError:
        return None


def set_body(doc, body: int, p: Placement | None) -> None:
    """Placement propre du corps `body` gardé (None : de nouveau comme l'ensemble)."""
    allp = dict(doc.extra.get(KEY_BODIES) or {})
    if p is None:
        allp.pop(str(int(body)), None)
    else:
        allp[str(int(body))] = to_dict(p)
    if allp:
        doc.extra[KEY_BODIES] = allp
    else:
        doc.extra.pop(KEY_BODIES, None)


def resolve(p: Placement, bounds, plate=None, margin: float = 5.0) -> Placement:
    """Décalage (dx, dy) d'après le mode : `bounds` (x0, y0, z0, x1, y1, z1)
    de la pièce orientée et tournée, sans décalage ; `plate` (x, y, l, h)."""
    x0, y0, _z0, x1, y1, _z1 = bounds
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if p.mode == 'fichier':
        p.dx = p.dy = 0.0
    elif p.mode == 'origine':
        p.dx, p.dy = -cx, -cy
    elif p.mode == 'centre' and plate is not None:
        px, py, pw, ph = plate
        p.dx, p.dy = px + pw / 2 - cx, py + ph / 2 - cy
    elif p.mode == 'coin' and plate is not None:
        px, py, _pw, _ph = plate
        p.dx, p.dy = px + margin - x0, py + margin - y0
    return p
