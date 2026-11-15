"""Supprimer des faces d'un volume déjà fait, comme le `delete_face` de SolidCraft
(`crates/kernel/src/delete_face.rs`), mais sur un maillage : boucher un perçage, effacer une poche, un
bossage, une rainure, pour simplifier une pièce avant de l'usiner.

Les faces qui entouraient celles qu'on retire doivent pouvoir s'étendre sur le trou qu'elles laissent.
C'est le cas tant que ces voisines sont plates et que leurs bords, plan par plan, se referment : par un
contour entier (le bord d'un perçage sur le dessus de la plaque), ou par un seul raccord droit de chaque
côté (le bord d'une rainure sur une face d'extrémité, ou ses deux bords sur le dessus).

Les triangles restent, un morceau de plan s'ajoute pour chaque plan. Si les morceaux ne se rejoignent pas
exactement, le maillage n'est pas fermé et on passe au second moyen.

Second moyen, pour un chanfrein ou une entaille de coin, où les voisines ne se rejoignent qu'une fois
prolongées : le volume borné par leurs plans, ajouté ou retiré. Ce volume est convexe et serré dans une
boîte autour des faces ; on vérifie avant de s'en servir que ce qu'il change n'est bordé que par ces plans
et par les faces retirées. Sinon il atteindrait autre chose, et l'opération est refusée.
"""
from __future__ import annotations

import numpy as np

from . import draft3d as DR
from . import solids as SO

PLANE_DEG_COS = 0.9999      # deux faces dans le même plan : leurs normales à moins d'un degré environ
PLANE_TOL = 1e-3            # mm
MAX_CHECK = 5000            # triangles du volume à ajouter qui ne sont pas sur un plan voisin : au-delà, on n'essaie pas


def _plane_of(tris: np.ndarray, nrm: np.ndarray) -> tuple | None:
    """(normale, décalage) d'une face plate, ou None."""
    keep = DR._areas(tris) > DR.SLIVER
    if not keep.any():
        return None
    weights = DR._areas(tris[keep])
    n = (nrm[keep] * weights[:, None]).sum(axis=0)
    size = float(np.linalg.norm(n))
    if size < 1e-9:                                      # un cylindre entier : ses normales s'annulent
        return None
    n = n / size
    if float((nrm[keep] @ n).min()) < PLANE_DEG_COS:
        return None
    h = tris[keep].reshape(-1, 3) @ n
    if float(h.max() - h.min()) > PLANE_TOL:
        return None
    return n, float(h.mean())


def _rings(sides: list) -> list:
    """Les contours d'un plan, en indices de sommets : des boucles entières, ou un ou deux morceaux dont le
    raccord droit est implicite (le dernier sommet rejoint le premier suivant)."""
    following: dict = {}
    arriving = set()
    for a, b in sides:
        if a in following:
            raise DR.DraftError('ces faces se touchent en un seul point : retirez-les séparément')
        following[a] = b
        arriving.add(b)
    chains = []
    for start in [a for a in following if a not in arriving]:
        chain = [start]
        while chain[-1] in following:
            chain.append(following.pop(chain[-1]))
        chains.append(chain)
    rings = []
    if len(chains) == 1:
        rings.append(chains[0])
    elif len(chains) == 2:
        rings.append(chains[0] + chains[1])
    elif chains:
        raise DR.DraftError('le contour de ces faces est trop découpé pour se refermer')
    while following:
        start = next(iter(following))
        ring = [start]
        at = following.pop(start)
        while at != start:
            ring.append(at)
            at = following.pop(at)
        rings.append(ring)
    return rings


def _patch(rings: list, v: np.ndarray, n: np.ndarray) -> np.ndarray:
    """Les triangles d'un morceau de plan dont les contours tournent autour de `n`."""
    x = np.cross((1.0, 0.0, 0.0) if abs(n[0]) < 0.7 else (0.0, 1.0, 0.0), n)
    x = x / float(np.linalg.norm(x))
    y = np.cross(n, x)
    flat = [np.column_stack((v[ring] @ x, v[ring] @ y)) for ring in rings]
    area = 0.0
    for q in flat:
        r = np.roll(q, -1, axis=0)
        area += 0.5 * float((q[:, 0] * r[:, 1] - r[:, 0] * q[:, 1]).sum())
    if area <= 0.0:
        raise DR.DraftError('ces faces ne laissent rien pour les remplacer : ajoutez celles qui les prolongent')
    if DR._crossing(flat):
        raise DR.DraftError('le contour de ces faces se recoupe')
    ids = np.array([x0 for ring in rings for x0 in ring], dtype=np.int64)
    return ids[np.asarray(SO._m().triangulate(flat), dtype=np.int64)]


def _closed(solid, tris, t, v, face_of, gone, planes):
    """Le premier moyen : un morceau par plan, d'après leurs contours."""
    patches = [_patch(_rings(sides), v, n) for n, _h, sides in planes]
    kept = t[~gone]
    new = np.vstack((kept, *patches))
    face2 = np.concatenate((face_of[~gone], *(np.full(len(q), -1 - i) for i, q in enumerate(patches))))
    moved = np.zeros(new.shape, dtype=bool)
    moved[len(kept):] = True
    real = np.ones(len(new), dtype=bool)
    real[:len(kept)] = DR._areas(tris[~gone]) > DR.SLIVER
    if DR.self_crossing(v, new, moved, real, face2):
        raise DR.DraftError('la face qui les remplace traverserait le reste de la pièce')
    used, new = np.unique(new, return_inverse=True)
    try:
        return SO.Solid(v[used], new.reshape(-1, 3), solid.name, solid.color).manifold()
    except SO.SolidError:
        raise DR.DraftError('ces faces ne se referment pas avec des plans : les voisines ne se rejoignent pas') from None


def _beyond(solid, gone_tris: np.ndarray, planes: list):
    """Le volume aux voisines prolongées (`planes` : [normale, décalage, ...]), ou None."""
    pts = gone_tris.reshape(-1, 3)
    cuts = []
    for n, h, *_rest in planes:                          # chaque voisine garde le côté où sont les faces retirées
        d = pts @ n - h
        if float(d.max()) > PLANE_TOL and float(d.min()) < -PLANE_TOL:
            return None
        cuts.append(([float(-n[0]), float(-n[1]), float(-n[2])], -h) if float(d.max()) <= PLANE_TOL
                    else ([float(n[0]), float(n[1]), float(n[2])], h))
    lo0, hi0 = pts.min(axis=0), pts.max(axis=0)
    man = solid.manifold()
    for room in (0.0, 0.25 * float((hi0 - lo0).max())):
        lo, size = lo0 - room, np.maximum(hi0 - lo0 + 2.0 * room, 1e-6)
        region = SO.box(lo[0], lo[1], lo[2], size[0], size[1], size[2]).manifold()
        for normal, offset in cuts:
            region = region.trim_by_plane(normal, offset)
        if region.is_empty():
            continue
        for fill in (True, False):
            gap = region - man if fill else region ^ man
            if gap.is_empty():
                continue
            bb = gap.bounding_box()
            if min(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2]) <= 10.0 * PLANE_TOL:
                continue
            got = SO._solid(gap, 'trou').triangles()
            centres = got[DR._areas(got) > DR.SLIVER].mean(axis=1)
            on_plane = np.zeros(len(centres), dtype=bool)
            for n, h, *_rest in planes:
                on_plane |= np.abs(centres @ n - h) <= PLANE_TOL
            far = np.flatnonzero(~on_plane)
            if len(far) <= MAX_CHECK and all(float(DR._distances(centres[i], gone_tris).min()) <= PLANE_TOL for i in far):
                return man + region if fill else man - region
    return None


def apply(solid, values: dict):
    """Le volume sans les faces de `values['picks']` (de draft3d.pick_of, un par face)."""
    picks = values.get('picks') or []
    if not picks:
        raise DR.DraftError('aucune face choisie')
    faces = DR._faces(solid)
    tris, face_of, nrm = faces
    chosen = {DR.find(faces, q) for q in picks}
    if len(chosen) >= len(np.unique(face_of)):
        raise DR.DraftError('il ne resterait rien du volume')
    t = np.asarray(solid.tris, dtype=np.int64)
    v = np.asarray(solid.verts, dtype=np.float64)
    gone = np.isin(face_of, list(chosen))
    # Le bord de ce qu'on retire : un côté d'un triangle gardé dont le jumeau part
    leaving = {}
    for a, b, c in t[gone].tolist():
        leaving[(a, b)] = True
        leaving[(b, c)] = True
        leaving[(c, a)] = True
    by_face: dict = {}
    for k in np.flatnonzero(~gone):
        a, b, c = t[k].tolist()
        for u, w in ((a, b), (b, c), (c, a)):
            if (w, u) in leaving:
                by_face.setdefault(int(face_of[k]), []).append((w, u))
    if not by_face:
        raise DR.DraftError('ces faces ne touchent rien d’autre')
    # Un plan, avec tous les bords qui y sont
    planes: list = []
    for f, sides in by_face.items():
        which = face_of == f
        plane = _plane_of(tris[which], nrm[which])
        if plane is None:
            raise DR.DraftError('une face voisine est courbe : elle ne peut pas s’étendre sur le vide')
        for known in planes:
            if float(known[0] @ plane[0]) >= PLANE_DEG_COS and abs(known[1] - plane[1]) <= PLANE_TOL:
                known[2].extend(sides)
                break
        else:
            planes.append([plane[0], plane[1], list(sides)])
    try:
        man = _closed(solid, tris, t, v, face_of, gone, planes)
    except DR.DraftError as first:
        man = _beyond(solid, tris[gone], planes)
        if man is None:
            raise first from None
    if man.is_empty() or man.volume() <= 0.0:
        raise DR.DraftError('il ne resterait rien du volume')
    out = SO._solid(man, solid.name)
    out.color = solid.color
    return out
