"""Dépouille : pencher les faces choisies d'un volume vers une direction de démoulage, autour d'un plan
neutre, comme le `draft` de SolidCraft (`crates/kernel/src/polyhedron.rs`), mais sur un maillage.

Les triangles ne changent pas, seuls leurs sommets bougent. Un sommet doit rester sur chaque face qui
l'entoure : sur le plan penché pour une face choisie, sur son plan actuel pour les autres. Trois faces
le fixent, deux lui laissent un chemin le plus court, et les plats restent plats. Une face courbe suit
la normale de ses facettes au sommet : un cylindre devient un cône.

Angle positif : la matière recule à mesure qu'on avance dans le sens du démoulage. Une paroi extérieure
rentre en montant, le bord d'une poche s'évase en montant : les deux se démoulent.
"""
from __future__ import annotations

import math

import numpy as np

from . import faces3d
from . import solids as SO

PULLS = {'z+': (0.0, 0.0, 1.0), 'z-': (0.0, 0.0, -1.0), 'y+': (0.0, 1.0, 0.0), 'y-': (0.0, -1.0, 0.0),
         'x+': (1.0, 0.0, 0.0), 'x-': (-1.0, 0.0, 0.0)}
MAX_ANGLE = 45.0            # degrés
WALL_DEG = 30.0             # une paroi : à moins de cet angle du sens de démoulage
MIN_WALL = 0.5              # sinus : une facette plus à plat que 30° sous le démoulage n'est plus une paroi
SLIVER = 1e-9               # mm² : un triangle sans surface n'a pas de normale
PLANE_TOL = 1e-3            # mm : une face plate reste plate à ça près (les maillages sont en float32)
CONTACT = 1e-4              # mm : un sommet déplacé aussi près d'une autre face la touche
PICK_TOL = 0.5              # mm
PICK_DEG = 25.0
MISFIT = 0.02               # mm : écart admis pour un sommet qui ne peut pas suivre toutes ses faces


class DraftError(SO.SolidError):
    pass


def _areas(tris: np.ndarray) -> np.ndarray:
    return 0.5 * np.linalg.norm(np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]), axis=1)


def _faces(solid) -> tuple:
    """(triangles, face de chaque triangle, normales)."""
    tris = np.asarray(solid.triangles(), dtype=np.float64)
    return tris, faces3d.segment(tris), faces3d.normals(tris)


def pick_of(solid, rank: int, faces: tuple | None = None) -> list:
    """Un point et une normale de la face : de quoi la retrouver après un recalcul."""
    tris, face_of, nrm = faces or _faces(solid)
    which = np.flatnonzero(face_of == rank)
    k = int(which[int(np.argmax(_areas(tris[which])))])
    c = tris[k].mean(axis=0)
    return [float(c[0]), float(c[1]), float(c[2]), float(nrm[k, 0]), float(nrm[k, 1]), float(nrm[k, 2])]


def _distances(q: np.ndarray, t: np.ndarray) -> np.ndarray:
    """La distance de `q` à chaque triangle (k, 3, 3)."""
    a, b, c = t[:, 0], t[:, 1], t[:, 2]
    ab, ac, ap = b - a, c - a, q - a
    n = np.cross(ab, ac)
    nn = np.maximum((n * n).sum(axis=1), 1e-24)
    u = (np.cross(ap, ac) * n).sum(axis=1) / nn
    w = (np.cross(ab, ap) * n).sum(axis=1) / nn
    best = np.full(len(t), np.inf)
    inside = (u >= 0.0) & (w >= 0.0) & (u + w <= 1.0)
    best[inside] = np.abs((ap * n).sum(axis=1))[inside] / np.sqrt(nn[inside])
    for p0, p1 in ((a, b), (b, c), (c, a)):
        d = p1 - p0
        s = np.clip(((q - p0) * d).sum(axis=1) / np.maximum((d * d).sum(axis=1), 1e-18), 0.0, 1.0)
        best = np.minimum(best, np.linalg.norm(q - (p0 + d * s[:, None]), axis=1))
    return best


def find(faces: tuple, pick) -> int:
    """La face d'un point noté : la plus proche, tournée à peu près pareil."""
    tris, face_of, nrm = faces
    q, n = np.asarray(pick[:3], dtype=np.float64), np.asarray(pick[3:6], dtype=np.float64)
    keep = np.flatnonzero(nrm @ n >= math.cos(math.radians(PICK_DEG)))
    if len(keep):
        d = _distances(q, tris[keep])
        j = int(np.argmin(d))
        if d[j] <= PICK_TOL:
            return int(face_of[keep[j]])
    raise DraftError(f'face introuvable près de ({pick[0]:g} ; {pick[1]:g} ; {pick[2]:g})')


def walls(faces: tuple, pull: str = 'z+', within: float = WALL_DEG) -> list:
    """Les faces à peu près parallèles au démoulage."""
    tris, face_of, nrm = faces
    p = np.array(PULLS[pull])
    real = _areas(tris) > SLIVER
    out = []
    limit = math.sin(math.radians(within))
    for f in np.unique(face_of):
        which = (face_of == f) & real
        if which.any() and float(np.abs(nrm[which] @ p).max()) <= limit:
            out.append(int(f))
    return out


def _span(solid, pull: str) -> tuple:
    h = np.asarray(solid.verts, dtype=np.float64) @ np.array(PULLS[pull])
    return float(h.min()), float(h.max())


def neutral_default(solid, pull: str = 'z+') -> float:
    """Le plan neutre par défaut : le début de la pièce dans le sens du démoulage."""
    return _span(solid, pull)[0]


def _shift(x: np.ndarray, groups: dict, chosen: set, p: np.ndarray, tilt: tuple, neutral: float) -> tuple:
    """(déplacement du sommet, écart restant)."""
    co, si = tilt
    rows, rhs = [], []
    for f, n in groups.items():
        if f in chosen:
            axis = np.cross(p, n)
            size = float(np.linalg.norm(axis))
            if size >= MIN_WALL / 2.0:                  # une moyenne de facettes qui sont toutes des parois
                u = axis / size
                m = np.cross(u, n)                      # dans le plan de la normale, vers le démoulage
                if float(m @ p) < 0.0:
                    m = -m
                n2 = n * co + m * si
                w = np.cross(n, u)                      # le long de la face, en quittant le plan neutre
                t = (neutral - float(x @ p)) / float(w @ p)
                rows.append(n2)
                rhs.append(float(n2 @ (w * t)))
                continue
        rows.append(n)
        rhs.append(0.0)
    A, b = np.array(rows), np.array(rhs)
    s = np.linalg.lstsq(A, b, rcond=1e-6)[0]
    return s, float(np.abs(A @ s - b).max())


def _side_turned_over(v: np.ndarray, out: np.ndarray, t: np.ndarray, face_of: np.ndarray) -> bool:
    """Un côté entre deux faces a changé de sens : il est passé par une longueur nulle, une face s'est refermée."""
    e = np.vstack((t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]))
    own = np.tile(face_of, 3)
    lo, hi = e.min(axis=1), e.max(axis=1)
    order = np.lexsort((hi, lo))
    lo, hi, own, e = lo[order], hi[order], own[order], e[order]
    border = (lo[1:] == lo[:-1]) & (hi[1:] == hi[:-1]) & (own[1:] != own[:-1])
    a, b = e[:-1][border].T
    d0, d1 = v[b] - v[a], out[b] - out[a]
    big = (d0 * d0).sum(axis=1) > 1e-10
    return bool(((d0 * d1).sum(axis=1)[big] <= 0.0).any())


def _loops(tri: np.ndarray) -> list:
    """Les contours d'un groupe de triangles, en indices de sommets, dans le sens des triangles."""
    sides = {}
    for a, b, c in tri.tolist():
        for u, w in ((a, b), (b, c), (c, a)):
            if (w, u) in sides:
                del sides[(w, u)]
            else:
                sides[(u, w)] = True
    following: dict = {}
    for u, w in sides:
        following.setdefault(u, []).append(w)
    loops = []
    while following:
        start = next(iter(following))
        ring, at = [], start
        while True:
            ring.append(at)
            nexts = following[at]
            to = nexts.pop()
            if not nexts:
                del following[at]
            at = to
            if at == start:
                break
            if at not in following:
                raise DraftError('une face plate a un bord ouvert')
        loops.append(ring)
    return loops


def _crossing(rings: list) -> bool:
    """Deux côtés se coupent-ils franchement ? Les contours viennent d'un maillage : les bouts communs ne comptent pas."""
    a = np.vstack(rings)
    b = np.vstack([np.roll(r, -1, axis=0) for r in rings])
    lo, hi = np.minimum(a, b), np.maximum(a, b)
    d = b - a

    def side(i, others):
        return d[i, 0] * (others[:, 1] - a[i, 1]) - d[i, 1] * (others[:, 0] - a[i, 0])

    for i in range(len(a) - 1):
        j = i + 1 + np.flatnonzero((lo[i + 1:] <= hi[i]).all(axis=1) & (hi[i + 1:] >= lo[i]).all(axis=1))
        if not len(j):
            continue
        c, e = a[j], b[j]
        first = side(i, c) * side(i, e) < 0.0
        q = a[i] - c
        one = d[j, 0] * q[:, 1] - d[j, 1] * q[:, 0]
        r = b[i] - c
        two = d[j, 0] * r[:, 1] - d[j, 1] * r[:, 0]
        if (first & (one * two < 0.0)).any():
            return True
    return False


def _rebuilt(tri: np.ndarray, out: np.ndarray, normal: np.ndarray) -> np.ndarray:
    """Une face plate retriangulée d'après ses contours.

    Ses contours peuvent être bons alors qu'un de ses triangles s'est retourné : un triangle très fin,
    entre le bord d'une poche ronde et un point lointain, n'a pas besoin de grand-chose. Le découpage
    de la face n'était valable que pour la forme d'avant."""
    loops = _loops(tri)
    ids = np.array([x for ring in loops for x in ring], dtype=np.int64)
    n = np.zeros(3)
    for ring in loops:
        q = out[ring]
        n += np.cross(q, np.roll(q, -1, axis=0)).sum(axis=0)
    size = float(np.linalg.norm(n))
    if size < 1e-9 or float(n @ normal) <= 0.0:
        raise DraftError('trop loin pour cette pièce : des faces se croisent')
    n = n / size
    c = out[ids].mean(axis=0)
    if float(np.abs((out[ids] - c) @ n).max()) > PLANE_TOL:
        raise DraftError('trop loin pour cette pièce : des faces se croisent')
    x = np.cross((1.0, 0.0, 0.0) if abs(n[0]) < 0.7 else (0.0, 1.0, 0.0), n)
    x = x / float(np.linalg.norm(x))
    y = np.cross(n, x)
    rings = [np.column_stack(((out[ring] - c) @ x, (out[ring] - c) @ y)) for ring in loops]
    if _crossing(rings):
        raise DraftError('trop loin pour cette pièce : des faces se croisent')
    return ids[np.asarray(SO._m().triangulate(rings), dtype=np.int64)]


def _around(t: np.ndarray, face_of: np.ndarray, nrm: np.ndarray, real: np.ndarray, chosen: set) -> dict:
    """Pour chaque sommet des faces choisies : la normale de chaque face autour de lui."""
    touched = np.unique(t[np.isin(face_of, list(chosen))])
    around: dict = {int(x): {} for x in touched}
    keep = np.isin(t, touched).any(axis=1)
    for k in np.flatnonzero(keep & real):
        f = int(face_of[k])
        for x in t[k]:
            x = int(x)
            if x in around:
                around[x][f] = around[x].get(f, 0.0) + nrm[k]
    return {x: {f: n / max(float(np.linalg.norm(n)), 1e-12) for f, n in groups.items()} for x, groups in around.items()}


def _pierced(p: np.ndarray, q: np.ndarray, tri: np.ndarray) -> np.ndarray:
    """Le segment p-q traverse-t-il franchement le triangle ? (k, 3), (k, 3), (k, 3, 3)."""
    a = tri[:, 0]
    ab, ac = tri[:, 1] - a, tri[:, 2] - a
    n = np.cross(ab, ac)
    n = n / np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]
    d0, d1 = ((p - a) * n).sum(axis=1), ((q - a) * n).sum(axis=1)
    apart = ((d0 > 1e-7) & (d1 < -1e-7)) | ((d0 < -1e-7) & (d1 > 1e-7))
    out = np.zeros(len(p), dtype=bool)
    if apart.any():
        k = np.flatnonzero(apart)
        x = p[k] + (q[k] - p[k]) * (d0[k] / (d0[k] - d1[k]))[:, None] - a[k]
        n2 = np.cross(ab[k], ac[k])
        nn = np.maximum((n2 * n2).sum(axis=1), 1e-24)
        u = (np.cross(x, ac[k]) * n2).sum(axis=1) / nn
        w = (np.cross(ab[k], x) * n2).sum(axis=1) / nn
        out[k] = (u >= 0.0) & (w >= 0.0) & (u + w <= 1.0)
    return out


def self_crossing(out: np.ndarray, t: np.ndarray, moved: np.ndarray, real: np.ndarray, face: np.ndarray) -> bool:
    """Un triangle touché par le déplacement en traverse-t-il un autre, ou un sommet déplacé en touche-t-il un ?
    Pas dans sa propre face : les triangles retournés y répondent déjà, et un sommet y frôle sans mal un
    voisin très fin. Le contraire ferait refuser à tort."""
    tri = out[t]
    lo, hi = tri.min(axis=1), tri.max(axis=1)
    order = np.argsort(lo[:, 0])
    lo_s, hi_s = lo[order], hi[order]
    t_s, tri_s, real_s, face_s = t[order], tri[order], real[order], face[order]
    reach = np.maximum.accumulate(hi_s[:, 0])
    mine, theirs = [], []
    for i in np.flatnonzero(moved.any(axis=1) & real):
        start = int(np.searchsorted(reach, lo[i, 0], side='left'))
        stop = int(np.searchsorted(lo_s[:, 0], hi[i, 0], side='right'))
        if start >= stop:
            continue
        box = ((lo_s[start:stop] <= hi[i]) & (hi_s[start:stop] >= lo[i])).all(axis=1) & real_s[start:stop]
        j = start + np.flatnonzero(box)
        if not len(j):
            continue
        c = t_s[j]
        x0, x1, x2 = t[i]                                       # un sommet commun : elles se rejoignent
        shared = ((c == x0) | (c == x1) | (c == x2)).any(axis=1)
        j = j[~shared & (face_s[j] != face[i])]
        if len(j):
            mine.append(np.full(len(j), i))
            theirs.append(j)
    if mine:
        mine, theirs = np.concatenate(mine), np.concatenate(theirs)
        for at in range(0, len(mine), 200000):
            one, two = tri[mine[at:at + 200000]], tri_s[theirs[at:at + 200000]]
            for u, w in ((0, 1), (1, 2), (2, 0)):
                if _pierced(one[:, u], one[:, w], two).any() or _pierced(two[:, u], two[:, w], one).any():
                    return True
    # Un sommet déplacé sur une face dont il n'est pas : une épaisseur nulle, qu'aucune traversée ne montre
    own: dict = {}
    for x, f in zip(t.ravel().tolist(), np.repeat(face, 3).tolist()):
        own.setdefault(x, set()).add(f)
    for x in np.unique(t[moved & real[:, None]]).tolist():
        q = out[x]
        start = int(np.searchsorted(reach, q[0] - CONTACT, side='left'))
        stop = int(np.searchsorted(lo_s[:, 0], q[0] + CONTACT, side='right'))
        if start >= stop:
            continue
        box = ((lo_s[start:stop] <= q + CONTACT) & (hi_s[start:stop] >= q - CONTACT)).all(axis=1) & real_s[start:stop]
        j = start + np.flatnonzero(box)
        j = j[~np.isin(face_s[j], list(own[x]))]
        if len(j) and (_distances(q, tri_s[j]) <= CONTACT).any():
            return True
    return False


def finish(solid, out: np.ndarray, worst: float, face_of: np.ndarray, real: np.ndarray):
    """Le volume aux sommets déplacés, ou un refus.

    Le maillage reste fermé et le volume plausible même si des parois se croisent : Manifold ne dirait
    rien. Un côté retourné, ou un triangle retourné sur une face qu'on ne peut pas redécouper, c'est non."""
    if worst > MISFIT:
        raise DraftError('une face voisine ne peut pas suivre : un sommet resterait hors de ses faces '
                         f'(écart de {worst:.2f} mm)')
    v = np.asarray(solid.verts, dtype=np.float64)
    t = np.asarray(solid.tris, dtype=np.int64)
    if _side_turned_over(v, out, t, face_of):
        raise DraftError('trop loin pour cette pièce : des faces se croisent')
    before = np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]])
    after = np.cross(out[t[:, 1]] - out[t[:, 0]], out[t[:, 2]] - out[t[:, 0]])
    flipped = real & ((before * after).sum(axis=1) <= 0.0)
    shifted = np.linalg.norm(out - v, axis=1) > 1e-9
    if flipped.any():
        again = np.unique(face_of[flipped])
        parts = [t[~np.isin(face_of, again)]]
        for f in again:
            which = face_of == f
            parts.append(_rebuilt(t[which], out, before[which].sum(axis=0)))
        stay = ~np.isin(face_of, again)
        real = np.concatenate((real[stay], np.ones(sum(len(q) for q in parts[1:]), dtype=bool)))
        face_of = np.concatenate((face_of[stay], *(np.full(len(q), f) for q, f in zip(parts[1:], again))))
        t = np.vstack(parts)
    if self_crossing(out, t, shifted[t], real, face_of):
        raise DraftError('trop loin pour cette pièce : des faces se croisent')
    used, t = np.unique(t, return_inverse=True)
    t = t.reshape(-1, 3)
    out = out[used]
    moved = SO.Solid(out, t.copy(), solid.name, solid.color)
    try:
        man = moved.manifold()
    except SO.SolidError:
        raise DraftError('trop loin pour cette pièce : le volume se recoupe') from None
    if man.is_empty() or man.volume() <= 0.0:
        raise DraftError('trop loin pour cette pièce : le volume se retourne')
    result = SO._solid(man, solid.name)
    result.color = solid.color
    return result


def apply(solid, values: dict):
    """Le volume aux faces penchées. `values` : angle (degrés), neutral (hauteur du plan neutre le long du
    démoulage), pull (une clé de PULLS), picks (de pick_of, un par face)."""
    angle = float(values.get('angle', 3.0))
    if abs(angle) > MAX_ANGLE:
        raise DraftError(f'angle trop grand : {MAX_ANGLE:g}° au plus')
    if angle == 0.0:
        raise DraftError('angle nul')
    pull = values.get('pull', 'z+')
    if pull not in PULLS:
        raise DraftError('sens de démoulage inconnu')
    picks = values.get('picks') or []
    if not picks:
        raise DraftError('aucune face choisie')
    neutral = values.get('neutral')
    neutral = neutral_default(solid, pull) if neutral is None else float(neutral)
    faces = _faces(solid)
    tris, face_of, nrm = faces
    chosen = {find(faces, q) for q in picks}
    p = np.array(PULLS[pull])
    t = np.asarray(solid.tris, dtype=np.int64)
    v = np.asarray(solid.verts, dtype=np.float64)
    real = _areas(tris) > SLIVER
    for f in chosen:
        size = np.linalg.norm(np.cross(nrm[(face_of == f) & real], p), axis=1)
        if size.max() < MIN_WALL:
            raise DraftError('une face à plat sous le démoulage ne peut pas pencher : choisissez les parois')
        if size.min() < MIN_WALL:
            raise DraftError('cette face se prolonge sans arête jusqu’à une partie à plat, par un congé sans doute : '
                             'dépouillez avant d’arrondir')
    around = _around(t, face_of, nrm, real, chosen)
    a = math.radians(angle)
    tilt = (math.cos(a), math.sin(a))
    out = v.copy()
    worst = 0.0
    for x, groups in around.items():
        s, left = _shift(v[x], groups, chosen, p, tilt, neutral)
        out[x] = v[x] + s
        worst = max(worst, left)
    return finish(solid, out, worst, face_of, real)
