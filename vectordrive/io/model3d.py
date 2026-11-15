"""Modèle 3D d'un document ouvert depuis un fichier 3D (STEP, STL,
3D XML) : toute la pièce ou tout l'assemblage, pour le plan de travail en
mode 3D — pas seulement la vue de dessus en calques du mode 2D.

STEP : lecteur 3D repris de NeoDrive (`neostep.step3d`, même auteur) —
structure du produit, toutes les surfaces maillées, arêtes, couleurs.
STL / 3D XML : triangles du fichier, arêtes vives calculées.
"""
from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass, field

import numpy as np

from ..core import progress

#: formats de document qui ont un modèle 3D
FORMATS_3D = ('step', 'stl', '3dxml', 'mesh')

#: couleur des pièces sans couleur (aluminium, comme NeoDrive)
ALU = (0.70, 0.74, 0.80)


@dataclass
class Model3D:
    triangles: np.ndarray                     # (n, 3, 3) mm
    colors: np.ndarray                        # (n, 3) 0..1
    segments: np.ndarray                      # (m, 2, 3) mm : arêtes
    name: str = ''
    notes: list = field(default_factory=list)
    parts: int = 1
    faces: int = 0
    #: face de chaque triangle (STEP : celles du fichier) ; None : calculée à la demande (`face_ids`)
    face_of: np.ndarray | None = None
    #: STEP : nature de chaque face ({'genre': 'plan'|'cylindre'…, 'rayon', 'creux'}), sinon vide
    face_kinds: list = field(default_factory=list)
    #: corps (solide) de chaque triangle ; None : morceaux d'un seul tenant, calculés à la demande
    body_of: np.ndarray | None = None
    #: noms des corps (STEP : « Corps1 »… ; sinon « Corps 1 »…)
    body_names: list = field(default_factory=list)
    #: STEP : l'axe du fichier tourné vers le haut ('Z', 'Y', 'X' : pièce redressée à la lecture)
    up_axis: str = 'Z'

    def body_ids(self) -> np.ndarray:
        """Corps de chaque triangle (calcul fait une fois)."""
        if self.body_of is None or len(self.body_of) != len(self.triangles):
            from ..core import faces3d
            self.body_of = faces3d.bodies(self.triangles)
        return self.body_of

    def body_count(self) -> int:
        b = self.body_ids()
        return int(b.max()) + 1 if len(b) else 0

    def body_name(self, k: int) -> str:
        return self.body_names[k] if 0 <= k < len(self.body_names) and self.body_names[k] else f'Corps {k + 1}'

    def segment_bodies(self) -> np.ndarray:
        """Corps de chaque arête (-1 : inconnu), calculé une fois."""
        cached = getattr(self, '_seg_bodies', None)
        if cached is None or len(cached) != len(self.segments):
            from ..core import faces3d
            cached = faces3d.segment_owner(self.triangles, self.body_ids(), self.segments)
            self._seg_bodies = cached
        return cached

    def face_ids(self) -> np.ndarray:
        """Face de chaque triangle : celles du fichier STEP, sinon triangles
        voisins regroupés jusqu'aux arêtes vives (calcul fait une fois)."""
        if self.face_of is None or len(self.face_of) != len(self.triangles):
            from ..core import faces3d
            groups = self.body_of if self.body_of is not None and len(self.body_of) == len(self.triangles) else None
            self.face_of = faces3d.segment(self.triangles, groups=groups)
        return self.face_of

    def face_count(self) -> int:
        f = self.face_ids()
        return int(f.max()) + 1 if len(f) else 0

    def bounds(self) -> tuple:
        pts = [self.triangles.reshape(-1, 3), self.segments.reshape(-1, 3)]
        pts = [p for p in pts if len(p)]
        if not pts:
            return (0.0, 0.0, 0.0, 1.0, 1.0, 1.0)
        a = np.vstack(pts)
        return (*a.min(axis=0).tolist(), *a.max(axis=0).tolist())

    def summary(self) -> str:
        x0, y0, z0, x1, y1, z1 = self.bounds()
        s = f'{len(self.triangles)} triangles, {len(self.segments)} arêtes'
        if self.faces:
            s = f'{self.faces} faces, ' + s
        if self.parts > 1:
            s += f', {self.parts} pièces'
        return s + f' — {x1 - x0:.2f} × {y1 - y0:.2f} × {z1 - z0:.2f} mm'


def _segments(polylines) -> np.ndarray:
    """Polylignes (k, 3) → segments (m, 2, 3), en un seul tableau."""
    parts = [np.stack([p[:-1], p[1:]], axis=1) for p in polylines if len(p) >= 2]
    return np.concatenate(parts).astype(np.float32) if parts else np.zeros((0, 2, 3), np.float32)


def sharp_edges(tris: np.ndarray, angle_deg: float = 30.0) -> np.ndarray:
    """Arêtes vives d'un maillage sans topologie (STL) : arêtes partagées
    par deux triangles dont les normales font plus de `angle_deg`, et
    arêtes de bord. Sommets rapprochés au µm près."""
    n = len(tris)
    if not n:
        return np.zeros((0, 2, 3), np.float32)
    v = np.round(tris.reshape(-1, 3) * 1000).astype(np.int64)
    uniq, idx = np.unique(v, axis=0, return_inverse=True)
    idx = idx.reshape(n, 3)
    nrm = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    ln = np.linalg.norm(nrm, axis=1)
    nrm = nrm / np.where(ln > 0, ln, 1)[:, None]
    e = np.concatenate([idx[:, [0, 1]], idx[:, [1, 2]], idx[:, [2, 0]]])
    tri_of = np.tile(np.arange(n), 3)
    key = np.sort(e, axis=1)
    order = np.lexsort((key[:, 1], key[:, 0]))
    key, tri_of, e = key[order], tri_of[order], e[order]
    # groupes d'arêtes identiques (vectorisé : des millions d'arêtes)
    starts = np.flatnonzero(np.r_[True, np.any(key[1:] != key[:-1], axis=1)])
    sizes = np.diff(np.r_[starts, len(key)])
    border = starts[sizes == 1]
    pairs = starts[sizes == 2]
    cos_lim = np.cos(np.radians(angle_deg))
    dots = np.einsum('ij,ij->i', nrm[tri_of[pairs]], nrm[tri_of[pairs + 1]])
    keep = np.concatenate([border, pairs[dots < cos_lim]])
    if not len(keep):
        return np.zeros((0, 2, 3), np.float32)
    return (uniq[e[keep]] / 1000.0).astype(np.float32)


def from_step(path) -> Model3D:
    from .neostep import step3d

    def prog(frac, msg):
        progress.step(int(frac * 1000), 1000, msg)
        return True
    m = step3d.lire_modele(str(path), progress=prog)
    tris = np.asarray(m.triangles, dtype=np.float32).reshape(-1, 3, 3)
    cols = np.asarray(m.couleurs, dtype=np.float32).reshape(-1, 3) if len(m.couleurs) == len(tris) \
        else np.tile(np.array(ALU, np.float32), (len(tris), 1))
    face_of = np.asarray(m.face_de, dtype=np.int64) if len(getattr(m, 'face_de', ())) == len(tris) else None
    kinds = [{k: f.get(k) for k in ('genre', 'rayon', 'creux', 'axe', 'centre', 'normale') if k in f}
             for f in getattr(m, 'faces', [])] if face_of is not None else []
    body_of, names = None, list(getattr(m, 'corps', []) or [])
    if face_of is not None and names and kinds:
        per_face = np.array([int(f.get('corps', -1)) for f in m.faces], dtype=np.int64)
        if len(per_face) and (per_face >= 0).all():
            body_of = per_face[face_of]
    return Model3D(tris, cols, _segments(m.aretes), pathlib.Path(path).name, list(m.notes),
                   max(1, m.n_instances), m.n_faces, face_of, kinds, body_of, names if body_of is not None else [],
                   getattr(m, 'axe_haut', 'Z'))


def from_mesh(path) -> Model3D:
    from . import mesh3d
    ext = pathlib.Path(path).suffix.lower()
    if ext in ('.igs', '.iges'):
        from . import iges
        raw = iges.triangles(path)
        if not len(raw):
            raise ValueError('IGES sans surface')
    else:
        raw = mesh3d.read_3dxml(path) if ext == '.3dxml' else mesh3d.read_stl(path)
    tris = np.asarray(raw, dtype=np.float32).reshape(-1, 3, 3)
    progress.check()
    cols = np.tile(np.array(ALU, np.float32), (len(tris), 1))
    return Model3D(tris, cols, sharp_edges(tris.astype(np.float64)), pathlib.Path(path).name)


#: doc.extra : fichier 3D d'où vient le dessin, gardé dans le .vdz (io.native)
SOURCE_KEY = 'source3d'


_EXTS_3D = ('.stp', '.step', '.stl', '.3dxml', '.igs', '.iges')


def _is_3d(path, fmt=None) -> bool:
    if not path:
        return False
    p = pathlib.Path(path)
    return (fmt == 'step' or p.suffix.lower() in _EXTS_3D) and p.is_file()    # le nom d'abord : un .vdz sans disque


def _same(a, b) -> bool:
    return os.path.normcase(os.path.abspath(str(a))) == os.path.normcase(os.path.abspath(str(b)))


def _kept(doc) -> str | None:
    extra = getattr(doc, 'extra', None)
    alt = extra.get(SOURCE_KEY) if isinstance(extra, dict) else None
    return alt if isinstance(alt, str) and alt else None


def _near(src, alt) -> str | None:
    """Pièce du nom de `alt` à côté du dessin `src`, si elle existe."""
    if not src:
        return None
    near = pathlib.Path(src).parent / pathlib.Path(alt).name
    return str(near) if _is_3d(near) else None


def source_of(doc) -> str | None:
    """Fichier 3D d'où vient le document, ou None : celui qu'on a ouvert,
    sinon celui que garde le dessin enregistré (`SOURCE_KEY`) — du même nom
    à côté du dessin d'abord (dossier de travail copié ou déplacé avec sa
    pièce : la sienne, `twin_note` le signale), sinon à son chemin."""
    src = getattr(doc, 'source_path', None)
    if _is_3d(src, getattr(doc, 'source_format', None)):
        return src
    alt = _kept(doc)
    if alt is None:
        return None
    near = _near(src, alt)
    if near is not None:
        return near
    return alt if _is_3d(alt) else None


def twin_note(doc) -> str | None:
    """Texte à montrer quand deux pièces portent le nom de celle du
    dessin — celle qu'il garde et celle d'à côté, prise (`source_of`) —, ou
    None."""
    src = getattr(doc, 'source_path', None)
    if _is_3d(src, getattr(doc, 'source_format', None)):
        return None
    alt = _kept(doc)
    if alt is None:
        return None
    near = _near(src, alt)
    if near is None or _same(near, alt) or not _is_3d(alt):
        return None
    return (f'Deux pièces 3D nommées « {pathlib.Path(alt).name} » : celle à côté du dessin est prise ({near}) ; '
            f'le dessin a été fait avec {alt}. Vérifier que c\'est la bonne (révision, placement, prises).')


def resolve(doc, path):
    """Fichier 3D `path` d'une opération : la pièce du dessin
    (`source_of`) s'il désigne celle que gardait le dessin (pièce d'à côté
    prise) ; lui sinon — une opération posée sur un autre fichier du même
    nom, même absent, n'usine pas la pièce du dessin en douce."""
    if not path:
        return path
    src = source_of(doc)
    if not src or _same(src, path):
        return path
    kept = _kept(doc)
    if kept is not None and _same(kept, path):
        return src
    return path


def same_name(a, b) -> bool:
    """Même nom de fichier (chemins Windows ou non, casse ignorée)."""
    name = lambda p: str(p).replace('\\', '/').rsplit('/', 1)[-1].lower()     # noqa: E731
    return bool(a) and bool(b) and name(a) == name(b)


def load(path, placement=None) -> Model3D:
    """Modèle 3D du fichier ; `placement` (core.placement3d) : posé comme
    sur la machine (face en haut, rotation, décalage)."""
    ext = pathlib.Path(path).suffix.lower()
    m = from_step(path) if ext in ('.stp', '.step') else from_mesh(path)
    return placed(m, placement)


def placed(m: Model3D, placement) -> Model3D:
    if placement is None or placement.is_identity():
        return m
    tris = placement.apply(m.triangles).astype(np.float32)
    segs = placement.apply(m.segments).astype(np.float32) if len(m.segments) else m.segments
    kinds = [_placed_kind(k, placement) for k in m.face_kinds]
    return Model3D(tris, m.colors, segs, m.name, list(m.notes), m.parts, m.faces, m.face_of, kinds,
                   m.body_of, list(m.body_names), m.up_axis)


def _placed_kind(k: dict, placement) -> dict:
    """Nature d'une face, axes et points posés comme la pièce."""
    out = dict(k)
    R = placement.rotation() if hasattr(placement, 'rotation') else None
    for key in ('axe', 'normale'):
        if key in out and out[key] is not None and R is not None:
            out[key] = (np.asarray(R) @ np.asarray(out[key], dtype=float)).tolist()
    if 'centre' in out and out['centre'] is not None:
        out['centre'] = placement.apply(np.asarray(out['centre'], dtype=float).reshape(1, 3))[0].tolist()
    return out
