"""Maillage fermé (étanche) d'un corps triangulé face par face (STEP), pour
en faire un volume du dessin qu'on modifie (booléens, pousser-tirer…) puis
qu'on usine.

Un STEP est maillé face par face : deux faces voisines ne partagent pas
toujours les mêmes points le long de leur arête commune. La réparation :

1. sommets confondus (au µm près), triangles plats retirés ; **languettes**
   posées en double, dos à dos, par deux faces voisines : retirées toutes
   les deux ; doublons retirés ;
2. **jonctions en T** : un sommet d'une face posé sur une arête de bord de
   la face voisine (à `tol` près) coupe cette arête ;
3. **trous** restants (petites fentes) bouchés en éventail — deux trous qui
   se touchent en un sommet, chacun le sien ;
4. triangles orientés de proche en proche (chaque arête parcourue dans les
   deux sens), le volume rendu positif par Manifold ; débris sans volume
   écartés.

`SolidError` si le résultat n'est pas un volume fermé (arêtes partagées par
plus de deux triangles…).
"""
from __future__ import annotations

from collections import deque

import numpy as np

from . import faces3d


def clean(idx: np.ndarray) -> np.ndarray:
    """Triangles (indices) sans triangle plat ni doublon."""
    idx = np.asarray(idx, dtype=np.int64).reshape(-1, 3)
    ok = (idx[:, 0] != idx[:, 1]) & (idx[:, 1] != idx[:, 2]) & (idx[:, 0] != idx[:, 2])
    idx = idx[ok]
    if not len(idx):
        return idx
    _u, first = np.unique(np.sort(idx, axis=1), axis=0, return_index=True)
    return idx[np.sort(first)]


def drop_fins(idx: np.ndarray) -> np.ndarray:
    """Triangles posés deux fois en sens opposés (deux faces voisines qui
    couvrent la même languette, dos à dos) retirés tous les deux : une
    ailette d'épaisseur nulle, dont un seul exemplaire laisserait des arêtes
    à trois triangles. En même sens : un exemplaire gardé (`clean`)."""
    idx = np.asarray(idx, dtype=np.int64).reshape(-1, 3)
    if not len(idx):
        return idx
    _u, inv, cnt = np.unique(np.sort(idx, axis=1), axis=0, return_inverse=True, return_counts=True)
    inv = inv.ravel()
    drop = np.zeros(len(idx), dtype=bool)
    pair = cnt[inv] == 2
    if pair.any():
        rows = np.flatnonzero(pair)
        rows = rows[np.argsort(inv[rows], kind='stable')]
        for a, b in rows.reshape(-1, 2).tolist():
            tb = idx[b].tolist()
            if idx[a].tolist() not in (tb, tb[1:] + tb[:1], tb[2:] + tb[:2]):
                drop[a] = drop[b] = True
    return idx[~drop]


def edge_counts(idx: np.ndarray):
    """(arêtes (e, 2) orientées, nombre de triangles par arête non orientée de chacune)."""
    e = np.concatenate([idx[:, [0, 1]], idx[:, [1, 2]], idx[:, [2, 0]]])
    _u, inv, cnt = np.unique(np.sort(e, axis=1), axis=0, return_inverse=True, return_counts=True)
    return e, cnt[inv.ravel()]


def open_and_bad(idx) -> tuple[int, int]:
    """(arêtes de bord, arêtes partagées par plus de deux triangles)."""
    if not len(idx):
        return 0, 0
    e = np.concatenate([idx[:, [0, 1]], idx[:, [1, 2]], idx[:, [2, 0]]])
    _u, cnt = np.unique(np.sort(e, axis=1), axis=0, return_counts=True)
    return int((cnt == 1).sum()), int((cnt > 2).sum())


def split_t_junctions(v: np.ndarray, idx: np.ndarray, tol: float, passes: int = 12, perp: float | None = None) -> np.ndarray:
    """Arêtes de bord coupées aux sommets de bord posés dessus : à plus de
    `tol` de ses bouts, à moins de `perp` (10 × `tol`) de l'arête — un point
    de la face voisine posé sur la courbe, pas sur la corde."""
    perp = 10 * tol if perp is None else perp
    idx = np.asarray(idx, dtype=np.int64).copy()
    n_tri = len(idx)
    for _p in range(passes):
        e, cnt = edge_counts(idx)
        tri = np.tile(np.arange(len(idx)), 3)
        which = np.repeat([0, 1, 2], len(idx))
        b = cnt == 1
        E, T, Wh = e[b], tri[b], which[b]
        if not len(E):
            break
        bv = np.unique(E.ravel())
        P = v[bv]
        cell = max(tol * 20, 0.25)
        keys = np.floor(P / cell).astype(np.int64)
        grid: dict = {}
        for i, k in enumerate(map(tuple, keys.tolist())):
            grid.setdefault(k, []).append(i)
        splits: dict = {}
        for (a, c), t, w in zip(E.tolist(), T.tolist(), Wh.tolist()):
            if t in splits:
                continue                                 # une arête par triangle et par passe
            pa, pb = v[a], v[c]
            d = pb - pa
            L = float(np.linalg.norm(d))
            if L < 1e-9:
                continue
            lo = np.floor(np.minimum(pa, pb) / cell).astype(int) - 1
            hi = np.floor(np.maximum(pa, pb) / cell).astype(int) + 1
            if np.prod(hi - lo + 1) > 3000:
                cand = np.arange(len(bv))
            else:
                cand = [i for x in range(lo[0], hi[0] + 1) for y in range(lo[1], hi[1] + 1)
                        for z in range(lo[2], hi[2] + 1) for i in grid.get((x, y, z), ())]
                if not cand:
                    continue
                cand = np.asarray(cand)
            q = P[cand] - pa
            s = q @ d / L
            dist = np.linalg.norm(q - np.outer(s / L, d), axis=1)
            ok = (s > tol) & (s < L - tol) & (dist < perp) & (bv[cand] != a) & (bv[cand] != c)
            if ok.any():
                order = np.argsort(s[ok])
                splits[t] = (w, bv[cand[ok]][order])
        if not splits:
            break
        keep = np.ones(len(idx), dtype=bool)
        new = []
        for t, (w, pts) in splits.items():
            tri3 = idx[t]
            a, c, o = tri3[w], tri3[(w + 1) % 3], tri3[(w + 2) % 3]
            chain = [a, *pts.tolist(), c]
            for p0, p1 in zip(chain[:-1], chain[1:]):
                new.append([p0, p1, o])
            keep[t] = False
        idx = np.concatenate([idx[keep], np.asarray(new, dtype=np.int64)])
        if len(idx) > 20 * n_tri + 1000:                 # garde-fou
            break
    return idx


def border_loops(idx) -> list[list[int]]:
    """Boucles fermées des arêtes de bord (indices de sommets) : le chemin
    suivi d'arête en arête est coupé en cycle à chaque sommet qui y repasse
    — aux sommets où plus de deux arêtes de bord se rejoignent (trous qui se
    touchent, lamelle d'aller-retour) les boucles ne sont plus abandonnées ;
    seul un bout de chemin sans issue l'est."""
    e, cnt = edge_counts(idx)
    border = e[cnt == 1].tolist()
    adj: dict = {}
    for k, (a, b) in enumerate(border):
        adj.setdefault(a, []).append((b, k))
        adj.setdefault(b, []).append((a, k))
    used = [False] * len(border)
    loops = []
    for k0, (a0, b0) in enumerate(border):
        if used[k0]:
            continue
        used[k0] = True
        path, pos, cur = [a0, b0], {a0: 0, b0: 1}, b0
        while True:
            nxt = next(((c, k) for c, k in adj.get(cur, ()) if not used[k]), None)
            if nxt is None:
                break                                      # sans issue : le reste du chemin est laissé
            c, k = nxt
            used[k] = True
            if c in pos:                                   # le chemin repasse par c : un cycle
                i = pos[c]
                if len(path) - i >= 3:
                    loops.append(path[i:])
                for v in path[i + 1:]:
                    del pos[v]
                path = path[:i + 1]
            else:
                pos[c] = len(path)
                path.append(c)
            cur = c
    return loops


def simple_loops(loop: list[int]) -> list[list[int]]:
    """Boucle qui repasse par un sommet (deux trous qui se touchent en un
    point) coupée en boucles simples : bouchée d'un seul éventail, elle
    donnerait une arête à quatre triangles."""
    out, stack, pos = [], [], {}
    for a in loop:
        if a in pos:
            i = pos[a]
            cyc = stack[i:]
            for c in cyc[1:]:
                del pos[c]
            del stack[i + 1:]
            if len(cyc) >= 3:
                out.append(cyc)
        else:
            pos[a] = len(stack)
            stack.append(a)
    if len(stack) >= 3:
        out.append(stack)
    return out


def fill_holes(v: np.ndarray, idx: np.ndarray, max_perimeter: float = 50.0):
    """Trous (boucles de bord, coupées en boucles simples) bouchés en éventail
    autour de leur centre ; rend (sommets, triangles, nombre de trous)."""
    loops = [s for L in border_loops(idx) for s in simple_loops(L)]
    verts = [v]
    new = []
    n = len(v)
    filled = 0
    for L in loops:
        pts = v[L]
        per = float(np.linalg.norm(np.diff(np.vstack([pts, pts[:1]]), axis=0), axis=1).sum())
        if per > max_perimeter:
            continue
        verts.append(pts.mean(axis=0)[None, :])
        for a, b in zip(L, L[1:] + L[:1]):
            new.append([a, b, n])
        n += 1
        filled += 1
    if new:
        idx = np.concatenate([idx, np.asarray(new, dtype=np.int64)])
    return np.vstack(verts), idx, filled


def orient(idx: np.ndarray, v: np.ndarray | None = None) -> np.ndarray:
    """Triangles orientés de proche en proche : deux triangles voisins
    parcourent leur arête commune en sens opposés ; `v` (sommets) donné :
    chaque coque reçoit aussi le bon sens — vers l'extérieur, vers l'intérieur
    pour une cavité (coque dans la boîte d'une autre)."""
    n = len(idx)
    e = np.concatenate([idx[:, [0, 1]], idx[:, [1, 2]], idx[:, [2, 0]]])
    tri = np.tile(np.arange(n), 3)
    key = np.sort(e, axis=1)
    order = np.lexsort((key[:, 1], key[:, 0]))
    key, tri, e = key[order], tri[order], e[order]
    starts = np.flatnonzero(np.r_[True, np.any(key[1:] != key[:-1], axis=1)])
    sizes = np.diff(np.r_[starts, len(key)])
    adj: list = [[] for _ in range(n)]
    for s in starts[sizes == 2].tolist():
        t1, t2 = int(tri[s]), int(tri[s + 1])
        same = bool(e[s, 0] == e[s + 1, 0])              # même sens : l'un des deux doit être retourné
        adj[t1].append((t2, same))
        adj[t2].append((t1, same))
    flip = np.zeros(n, dtype=bool)
    seen = np.zeros(n, dtype=bool)
    comp = np.full(n, -1, dtype=np.int64)
    nc = 0
    for s0 in range(n):
        if seen[s0]:
            continue
        seen[s0] = True
        comp[s0] = nc
        q = deque([s0])
        while q:
            t = q.popleft()
            for u, same in adj[t]:
                if not seen[u]:
                    flip[u] = flip[t] ^ same
                    seen[u] = True
                    comp[u] = nc
                    q.append(u)
        nc += 1
    out = idx.copy()
    out[flip] = out[flip][:, ::-1]
    if v is not None and nc > 1:
        P = np.asarray(v, dtype=np.float64)[out]
        vol = np.einsum('ij,ij->i', P[:, 0], np.cross(P[:, 1], P[:, 2])) / 6.0
        vols = np.bincount(comp, weights=vol, minlength=nc)
        lo = np.array([P[comp == c].reshape(-1, 3).min(axis=0) for c in range(nc)])
        hi = np.array([P[comp == c].reshape(-1, 3).max(axis=0) for c in range(nc)])
        for c in range(nc):
            inside = any(d != c and (lo[d] <= lo[c] + 1e-9).all() and (hi[c] <= hi[d] + 1e-9).all()
                         and (hi[d] - lo[d]).prod() > (hi[c] - lo[c]).prod() for d in range(nc))
            want = -1.0 if inside else 1.0
            if vols[c] * want < 0:
                sel = comp == c
                out[sel] = out[sel][:, ::-1]
    return out


def repair(tris, tol: float = 0.01) -> tuple[np.ndarray, np.ndarray, dict]:
    """Triangles (n, 3, 3) → (sommets, triangles orientés, compte rendu
    {'ailettes', 'jonctions', 'trous', 'bords', 'mauvaises'}) ; ne contrôle
    pas encore la fermeture (voir `to_solid`)."""
    v, idx = faces3d.merged_vertices(np.asarray(tris, dtype=np.float64), 1e-5)
    idx = idx[(idx[:, 0] != idx[:, 1]) & (idx[:, 1] != idx[:, 2]) & (idx[:, 0] != idx[:, 2])]
    n0 = len(idx)
    idx = drop_fins(idx)                                 # avant `clean`, qui en garderait un exemplaire
    fins = (n0 - len(idx)) // 2
    idx = clean(idx)
    before = len(idx)
    idx = clean(split_t_junctions(v, idx, max(tol, 1e-4)))
    v, idx, holes = fill_holes(v, idx)
    idx = clean(orient(clean(idx), v))
    b, bad = open_and_bad(idx)
    return v, idx, {'ailettes': fins, 'jonctions': max(0, len(idx) - before), 'trous': holes, 'bords': b,
                    'mauvaises': bad}


def to_solid(tris, name: str = 'Volume', tol: float = 0.01, color=None):
    """Volume (core.solids.Solid) d'un corps triangulé, après réparation ;
    SolidError s'il ne ferme pas."""
    from . import solids as SO
    v, idx, rep = repair(tris, tol)
    s = SO.Solid(v, idx, name) if color is None else SO.Solid(v, idx, name, tuple(color))
    try:
        man = s.manifold()
    except SO.SolidError:
        raise SO.SolidError(f'maillage non fermé après réparation : {rep["bords"]} arête(s) de bord, '
                            f'{rep["mauvaises"]} arête(s) partagée(s) par plus de deux faces') from None
    if man.volume() < 0:
        s.tris = s.tris[:, ::-1].copy()
        man = s.manifold()
    parts = man.decompose()
    if len(parts) > 1:                                   # débris sans volume laissés par les bouchages
        keep = [p for p in parts if abs(p.volume()) > 1e-6 * abs(man.volume())]
        if keep and len(keep) < len(parts):
            man = type(man).compose(keep)
    return SO.Solid.from_manifold(man, name, s.color)
