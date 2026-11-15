"""Faces d'un modèle 3D, pour les choisir à la souris dans la vue 3D et
les usiner : une face est un morceau de surface d'un seul tenant, bordé
d'arêtes vives.

- STEP : les faces du fichier (le lecteur donne la face de chaque
  triangle) ;
- STL, 3D XML, volumes du dessin (maillages sans topologie) : triangles
  voisins regroupés tant que le pli entre eux reste sous `SHARP` degrés —
  les faces sont alors celles que bordent les arêtes affichées.

Aussi : le triangle visé par un clic (rayon de la caméra), les contours
fermés qui bordent un ensemble de faces, et le résumé d'une sélection.
"""
from __future__ import annotations

import math

import numpy as np

#: pli (°) au-delà duquel deux triangles voisins sont sur deux faces (celui des arêtes vives affichées)
SHARP = 30.0
#: sommets confondus à ce pas près (mm) : les maillages STL répètent leurs sommets
MERGE = 1e-3


def merged_vertices(tris: np.ndarray, step: float = MERGE) -> tuple[np.ndarray, np.ndarray]:
    """(sommets uniques (k, 3), indices (n, 3)) des triangles (n, 3, 3)."""
    t = np.asarray(tris, dtype=np.float64).reshape(-1, 3, 3)
    key = np.round(t.reshape(-1, 3) / step).astype(np.int64)
    uniq, inv = np.unique(key, axis=0, return_inverse=True)
    return uniq * step, inv.reshape(-1, 3)


def _edge_pairs(idx: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Arêtes des triangles (indices de sommets) : (clés triées (e, 2),
    triangle de chaque arête (e,), début de chaque groupe d'arêtes
    identiques) — l'ordre est celui des clés."""
    n = len(idx)
    e = np.concatenate([idx[:, [0, 1]], idx[:, [1, 2]], idx[:, [2, 0]]])
    tri_of = np.tile(np.arange(n), 3)
    key = np.sort(e, axis=1)
    order = np.lexsort((key[:, 1], key[:, 0]))
    key, tri_of = key[order], tri_of[order]
    starts = np.flatnonzero(np.r_[True, np.any(key[1:] != key[:-1], axis=1)]) if len(key) else np.zeros(0, int)
    return key, tri_of, starts


def normals(tris: np.ndarray) -> np.ndarray:
    t = np.asarray(tris, dtype=np.float64).reshape(-1, 3, 3)
    n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    ln = np.linalg.norm(n, axis=1)
    return n / np.where(ln > 0, ln, 1.0)[:, None]


def _components(n: int, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Composantes connexes du graphe à n sommets et aux liens (a, b) :
    étiquette (la plus petite des sommets de la composante) de chaque
    sommet — union par accrochage des racines et compression des chemins,
    tout en numpy (des centaines de milliers de triangles)."""
    lab = np.arange(n)
    if not len(a):
        return lab
    while True:
        la, lb = lab[a], lab[b]
        diff = la != lb
        if not diff.any():
            break
        lo, hi = np.minimum(la[diff], lb[diff]), np.maximum(la[diff], lb[diff])
        np.minimum.at(lab, hi, lo)
        while True:
            nxt = lab[lab]
            if np.array_equal(nxt, lab):
                break
            lab = nxt
    return lab


def segment(tris: np.ndarray, angle_deg: float = SHARP, groups=None) -> np.ndarray:
    """Face de chaque triangle (0, 1, 2… dans l'ordre de leur premier
    triangle) : triangles voisins dont le pli reste sous `angle_deg` ;
    `groups` (corps de chaque triangle) : jamais deux corps dans une face."""
    t = np.asarray(tris, dtype=np.float64).reshape(-1, 3, 3)
    n = len(t)
    if not n:
        return np.zeros(0, dtype=np.int64)
    v, idx = merged_vertices(t)
    if groups is not None:                                 # sommets propres à chaque corps : un contact entre deux
        idx = idx + np.asarray(groups, dtype=np.int64)[:, None] * len(v)    # corps ne coupe pas leurs faces
    key, tri_of, starts = _edge_pairs(idx)
    sizes = np.diff(np.r_[starts, len(key)])
    pairs = starts[sizes == 2]                             # arêtes partagées par deux triangles exactement
    a, b = tri_of[pairs], tri_of[pairs + 1]
    nrm = normals(t)
    keep = np.einsum('ij,ij->i', nrm[a], nrm[b]) >= math.cos(math.radians(angle_deg))
    lab = _components(n, a[keep], b[keep])
    _u, first, inv = np.unique(lab, return_index=True, return_inverse=True)
    rank = np.empty(len(first), dtype=np.int64)
    rank[np.argsort(first)] = np.arange(len(first))       # numérotées dans l'ordre des triangles
    return rank[inv]


def bodies(tris: np.ndarray) -> np.ndarray:
    """Corps de chaque triangle d'un maillage sans topologie (STL) : les
    morceaux d'un seul tenant (sommets communs), numérotés dans l'ordre de
    leur premier triangle."""
    t = np.asarray(tris, dtype=np.float64).reshape(-1, 3, 3)
    n = len(t)
    if not n:
        return np.zeros(0, dtype=np.int64)
    _v, idx = merged_vertices(t)
    # triangle ↔ sommet : deux triangles qui partagent un sommet sont du même corps
    tri = np.repeat(np.arange(n), 3)
    vert = idx.ravel()
    order = np.argsort(vert, kind='stable')
    vs, ts = vert[order], tri[order]
    same = vs[1:] == vs[:-1]
    lab = _components(n, ts[:-1][same], ts[1:][same])
    _u, first, inv = np.unique(lab, return_index=True, return_inverse=True)
    rank = np.empty(len(first), dtype=np.int64)
    rank[np.argsort(first)] = np.arange(len(first))
    return rank[inv]


def segment_owner(tris: np.ndarray, owner: np.ndarray, segments: np.ndarray) -> np.ndarray:
    """Pour chaque arête (m, 2, 3), le numéro (`owner`, par triangle) du
    triangle qui a un sommet au même endroit que son premier point (au µm
    près) ; -1 sinon."""
    seg = np.asarray(segments, dtype=np.float64).reshape(-1, 2, 3)
    if not len(seg):
        return np.zeros(0, dtype=np.int64)
    t = np.asarray(tris, dtype=np.float64).reshape(-1, 3, 3)
    key = np.round(t.reshape(-1, 3) / MERGE).astype(np.int64)
    own = np.repeat(np.asarray(owner, dtype=np.int64), 3)
    uniq, first = np.unique(key, axis=0, return_index=True)
    q = np.round(seg[:, 0] / MERGE).astype(np.int64)
    # recherche par lignes : clés combinées en un seul entier (coordonnées bornées)
    lo = np.minimum(uniq.min(axis=0), q.min(axis=0))
    span = np.maximum(uniq.max(axis=0), q.max(axis=0)) - lo + 1
    def flat(a):
        a = a - lo
        return (a[:, 0] * span[1] + a[:, 1]) * span[2] + a[:, 2]
    fu, fq = flat(uniq), flat(q)
    pos = np.searchsorted(fu, fq)
    pos = np.minimum(pos, len(fu) - 1)
    ok = fu[pos] == fq
    out = np.full(len(seg), -1, dtype=np.int64)
    out[ok] = own[first[pos[ok]]]
    return out


def ray_hit(tris: np.ndarray, origin, direction) -> tuple[int, float]:
    """Le triangle que le rayon `origin` + t·`direction` (t > 0) touche
    en premier, et t ; (-1, inf) s'il n'en touche aucun (Möller-Trumbore,
    les deux côtés des triangles)."""
    t = np.asarray(tris, dtype=np.float64).reshape(-1, 3, 3)
    if not len(t):
        return -1, math.inf
    o = np.asarray(origin, dtype=np.float64)
    d = np.asarray(direction, dtype=np.float64)
    v0 = t[:, 0]
    e1, e2 = t[:, 1] - v0, t[:, 2] - v0
    p = np.cross(d, e2)
    det = np.einsum('ij,ij->i', e1, p)
    ok = np.abs(det) > 1e-14
    inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
    s = o - v0
    u = np.einsum('ij,ij->i', s, p) * inv
    q = np.cross(s, e1)
    v = (q @ d) * inv
    dist = np.einsum('ij,ij->i', e2, q) * inv
    eps = 1e-9
    hit = ok & (u >= -eps) & (v >= -eps) & (u + v <= 1 + eps) & (dist > 1e-9)
    if not hit.any():
        return -1, math.inf
    dist = np.where(hit, dist, np.inf)
    i = int(np.argmin(dist))
    return i, float(dist[i])


def boundary_loops(tris: np.ndarray, which=None) -> list[np.ndarray]:
    """Contours fermés (polylignes (k, 3), premier point répété à la fin)
    qui bordent les triangles `which` (indices ; tous si None) : arêtes
    qu'un seul de ces triangles emploie, chaînées. Une arête en trop
    (maillage non manifold) interrompt la chaîne : seules les boucles
    fermées sont rendues."""
    t = np.asarray(tris, dtype=np.float64).reshape(-1, 3, 3)
    if which is not None:
        t = t[np.asarray(which, dtype=np.int64)]
    if not len(t):
        return []
    verts, idx = merged_vertices(t)
    e = np.concatenate([idx[:, [0, 1]], idx[:, [1, 2]], idx[:, [2, 0]]])
    key = np.sort(e, axis=1)
    _u, inv, counts = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    border = e[counts[inv.ravel()] == 1]
    nxt: dict[int, list[int]] = {}
    for a, b in border.tolist():
        nxt.setdefault(a, []).append(b)
        nxt.setdefault(b, []).append(a)
    loops = []
    used: set[tuple[int, int]] = set()
    for a0, b0 in border.tolist():
        if (min(a0, b0), max(a0, b0)) in used:
            continue
        chain = [a0, b0]
        used.add((min(a0, b0), max(a0, b0)))
        prev, cur = a0, b0
        while cur != a0:
            cand = [c for c in nxt.get(cur, ()) if c != prev and (min(cur, c), max(cur, c)) not in used]
            if not cand:
                break
            c = cand[0]
            used.add((min(cur, c), max(cur, c)))
            chain.append(c)
            prev, cur = cur, c
        if cur == a0 and len(chain) >= 4:
            loops.append(verts[chain])
    return loops


def face_triangles(face_of: np.ndarray, faces) -> np.ndarray:
    """Indices des triangles des faces `faces`."""
    if face_of is None or not len(face_of):
        return np.zeros(0, dtype=np.int64)
    return np.flatnonzero(np.isin(face_of, np.asarray(list(faces), dtype=np.int64)))


def area(tris: np.ndarray) -> float:
    t = np.asarray(tris, dtype=np.float64).reshape(-1, 3, 3)
    if not len(t):
        return 0.0
    return float(0.5 * np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1).sum())


def describe(tris: np.ndarray) -> dict:
    """Ce qu'il faut savoir d'un morceau de surface pour l'usiner :
    {'aire' mm², 'z_min', 'z_max', 'plat' (horizontal), 'vertical',
    'pente_max' (° depuis l'horizontale)}."""
    t = np.asarray(tris, dtype=np.float64).reshape(-1, 3, 3)
    if not len(t):
        return {'aire': 0.0, 'z_min': 0.0, 'z_max': 0.0, 'plat': False, 'vertical': False, 'pente_max': 0.0}
    nrm = normals(t)
    a = 0.5 * np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1)
    slope = np.degrees(np.arccos(np.clip(np.abs(nrm[:, 2]), 0.0, 1.0)))
    big = a > a.max() * 1e-6
    return {'aire': float(a.sum()), 'z_min': float(t[:, :, 2].min()), 'z_max': float(t[:, :, 2].max()),
            'plat': bool((slope[big] < 0.5).all()),
            'vertical': bool((slope[big] > 89.5).all()),
            'pente_max': float(slope[big].max()) if big.any() else 0.0}
