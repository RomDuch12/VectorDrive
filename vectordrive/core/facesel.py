"""Sélection de faces d'une pièce 3D : nature et mesures d'une face, faces
semblables, mesures entre deux faces (onglet Design STEP, groupe
« Sélection 3D »).

Une face est décrite par ce que le lecteur STEP en dit (`face_kinds` du
modèle : plan et sa normale vers l'extérieur, cylindre et son axe, son
centre, son rayon, creux ou bossage, cône…) et par ses triangles (aire,
étendue, cote d'un plan, longueur d'un cylindre le long de son axe). Un
maillage sans description (STL) : une face plate est reconnue à ses
normales, les autres restent « autre ».

Faces semblables à une face choisie : un cylindre, les cylindres de même
rayon, creux ou non comme lui (tous les trous de ce diamètre) ; un plan,
les plans de même normale à la même cote (coplanaires) ; une autre face,
celles de même nature et de même aire (fraisures, congés identiques).

Faces parallèles : un plan, tous les plans de même normale à toute cote (les
fonds tournés vers l'outil d'une prise) ; un cylindre, tous les cylindres
d'axe parallèle, creux ou non comme lui (les trous percés dans ce sens).

Faces coaxiales : un cylindre, un cône, une sphère ou un tore choisi, dans
son corps, toutes les faces de révolution du même axe (sphères centrées
dessus) et les plans perpendiculaires à l'axe bordés seulement par elles (fond
plat, épaulement, fond de lamage) : un trou entier, un arbre entier. Une
sphère choisie prend l'axe d'une face voisine qui passe par son centre (celui
que le fichier lui donne est quelconque).

Faces tangentes : de proche en proche, les faces qui suivent celles choisies
sans arête vive (un bord arrondi : côtés plans et congés des coins, une
chaîne de congés, les deux moitiés d'un trou) ; le pli est mesuré sur les
arêtes communes, par la surface que le lecteur décrit (plan, cylindre) ou
par les facettes. Faces du corps : toutes les faces des corps des faces
choisies (une partie d'un moule). Inverser dans le corps : les faces de ces
corps qui ne sont pas choisies (le reste d'une pièce).

Entre deux faces : deux plans, l'angle entre leurs normales et, parallèles,
leur distance ; deux cylindres, d'axes parallèles l'entraxe, sinon l'angle
des axes et leur plus courte distance ; un plan et un cylindre, l'axe
parallèle au plan : sa distance au plan ; sinon la plus courte distance
entre les sommets des deux faces.
"""
from __future__ import annotations

import math

import numpy as np

#: tolérances : longueur (mm), angle (°)
TOL_MM = 0.01
TOL_DEG = 0.5
#: au-delà, les sommets d'une face sont échantillonnés pour la plus courte distance
SAMPLE = 3000
#: pli (°) sous lequel deux faces se suivent sans arête vive : surfaces décrites des deux côtés, facettes
TANGENT_DEG = 3.0
TANGENT_MESH_DEG = 20.0


def _unit(v) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-12 else v


def _kinds(model) -> list:
    return list(getattr(model, 'face_kinds', None) or [])


def face_triangles(model, face: int) -> np.ndarray:
    """Les triangles (k, 3, 3) de la face `face` du modèle."""
    fo = np.asarray(model.face_ids())
    return np.asarray(model.triangles, dtype=float)[fo == int(face)]


def props(model, face: int, T: np.ndarray | None = None) -> dict:
    """{'face', 'kind' ('plan', 'cylindre', 'cone', 'sphere', 'tore', 'autre'), 'area', 'bounds' (x0, y0, z0,
    x1, y1, z1)} et selon la nature : plan 'normal', 'offset' (cote le long de la normale) ; cylindre
    'radius', 'hollow', 'axis', 'centre' (sur l'axe, au milieu de la face), 'length'."""
    T = face_triangles(model, face) if T is None else T
    k = _kinds(model)
    info = k[face] if 0 <= face < len(k) and k[face] else {}
    P = T.reshape(-1, 3)
    cr = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]) if len(T) else np.zeros((0, 3))
    area = 0.5 * float(np.linalg.norm(cr, axis=1).sum())
    out = {'face': int(face), 'kind': info.get('genre', 'autre'), 'area': area,
           'bounds': tuple(float(x) for x in np.r_[P.min(axis=0), P.max(axis=0)]) if len(P) else (0.0,) * 6}
    if not len(P):
        return out
    if out['kind'] == 'autre' and not info and len(cr):           # sans description : plate si les normales le sont
        n = _unit(cr.sum(axis=0))
        nn = cr / np.maximum(np.linalg.norm(cr, axis=1), 1e-12)[:, None]
        if float(np.linalg.norm(n)) > 0 and float((np.abs(nn @ n)).min()) >= math.cos(math.radians(TOL_DEG)):
            out['kind'] = 'plan'
            info = {'normale': n}
    if out['kind'] == 'plan':
        n = _unit(info.get('normale') if info.get('normale') is not None else cr.sum(axis=0))
        out['normal'] = n
        out['offset'] = float((P @ n).mean())
    elif out['kind'] == 'cylindre' and info.get('rayon'):
        a = _unit(info['axe']) if info.get('axe') is not None else None
        c = np.asarray(info['centre'], dtype=float) if info.get('centre') is not None else None
        out['radius'] = float(info['rayon'])
        out['hollow'] = bool(info.get('creux', False))
        if a is not None and c is not None:
            s = (P - c) @ a
            out['axis'] = a
            out['centre'] = c + a * (0.5 * (float(s.min()) + float(s.max())))
            out['length'] = float(s.max() - s.min())
    return out


def similar(model, faces, tol: float = TOL_MM) -> list:
    """Les faces semblables à chacune des faces `faces` (elles comprises), triées."""
    fo = np.asarray(model.face_ids())
    n = int(fo.max()) + 1 if len(fo) else 0
    T = np.asarray(model.triangles, dtype=float)
    order = np.argsort(fo, kind='stable')
    keys = fo[order]
    cache = {}

    def get(f):
        if f not in cache:
            idx = order[np.searchsorted(keys, f, 'left'):np.searchsorted(keys, f, 'right')]
            cache[f] = props(model, f, T[idx])
        return cache[f]

    kinds = _kinds(model)
    cos = math.cos(math.radians(TOL_DEG))
    out = set()
    for f0 in faces:
        f0 = int(f0)
        if not 0 <= f0 < n:
            continue
        p0 = get(f0)
        out.add(f0)
        for f in range(n):
            if f in out:
                continue
            k = (kinds[f] or {}) if f < len(kinds) else {}
            if k and k.get('genre', 'autre') != p0['kind']:
                continue                                           # tri rapide sur la nature du lecteur
            if p0['kind'] == 'cylindre' and k.get('rayon') is not None \
                    and abs(float(k['rayon']) - p0.get('radius', math.inf)) > tol:
                continue
            p = get(f)
            if p['kind'] != p0['kind']:
                continue
            if p0['kind'] == 'cylindre':
                if 'radius' in p0 and 'radius' in p and abs(p['radius'] - p0['radius']) <= tol \
                        and p['hollow'] == p0['hollow']:
                    out.add(f)
            elif p0['kind'] == 'plan':
                if float(p['normal'] @ p0['normal']) >= cos and abs(p['offset'] - p0['offset']) <= tol:
                    out.add(f)
            elif abs(p['area'] - p0['area']) <= max(tol, 0.005 * p0['area']):
                out.add(f)
    return sorted(out)


def parallel(model, faces, tol_deg: float = TOL_DEG) -> list:
    """Les faces parallèles à chacune des faces `faces` (elles comprises), triées : plans de même normale (même
    sens), cylindres d'axe parallèle et de même genre (creux ou non)."""
    n = int(np.asarray(model.face_ids()).max()) + 1 if len(model.face_ids()) else 0
    is_plan, pn, is_cyl, ca, _cc = _surfaces(model, n)
    kinds = _kinds(model)
    hollow = np.array([f < len(kinds) and bool((kinds[f] or {}).get('creux', False)) for f in range(n)], dtype=bool)
    cos = math.cos(math.radians(tol_deg))
    out = set()
    for f0 in (int(f) for f in faces):
        if not 0 <= f0 < n:
            continue
        out.add(f0)
        if is_plan[f0]:
            out.update(np.flatnonzero(is_plan & (pn @ pn[f0] >= cos)).tolist())
        elif is_cyl[f0]:
            out.update(np.flatnonzero(is_cyl & (np.abs(ca @ ca[f0]) >= cos) & (hollow == hollow[f0])).tolist())
    return sorted(int(f) for f in out)


def _revolutions(model, n: int) -> tuple:
    """Par face : (de révolution ?, axe, point de l'axe, sphère ?) d'après le lecteur (cylindre, cône, sphère,
    tore)."""
    rev, ax, pt, sph = np.zeros(n, bool), np.zeros((n, 3)), np.zeros((n, 3)), np.zeros(n, bool)
    for f, k in enumerate(_kinds(model)[:n]):
        k = k or {}
        if k.get('genre') in ('cylindre', 'cone', 'sphere', 'tore') and k.get('axe') is not None \
                and k.get('centre') is not None:
            rev[f], ax[f], pt[f] = True, _unit(k['axe']), np.asarray(k['centre'], dtype=float)
            sph[f] = k['genre'] == 'sphere'
    return rev, ax, pt, sph


def _face_bodies(model, n: int) -> np.ndarray:
    """Le corps de chaque face (0 partout si le modèle n'en dit rien)."""
    fo = np.asarray(model.face_ids())
    out = np.zeros(n, dtype=np.int64)
    bid = getattr(model, 'body_ids', None)
    if bid is not None and len(fo):
        out[fo] = np.asarray(bid())
    return out


def _line_gap(p, c, a) -> float:
    """Distance du point p à la droite (c, a unitaire)."""
    w = np.asarray(p, dtype=float) - c
    return float(np.linalg.norm(w - (w @ a) * a))


def coaxial(model, faces, tol: float = TOL_MM, tol_deg: float = TOL_DEG) -> list:
    """Les faces du même axe que chacune des faces de révolution `faces` (elles comprises), dans son corps,
    triées : cylindres, cônes et tores d'axe confondu, sphères centrées dessus, plans perpendiculaires à l'axe
    bordés seulement par elles (fond plat, épaulement, fond de lamage). Une sphère prend l'axe d'une face de
    révolution voisine qui passe par son centre."""
    n = int(np.asarray(model.face_ids()).max()) + 1 if len(model.face_ids()) else 0
    rev, ax, pt, sph = _revolutions(model, n)
    is_plan, pn, _c, _a, _p = _surfaces(model, n)
    body = _face_bodies(model, n)
    cos = math.cos(math.radians(tol_deg))
    near = None
    out = set()
    for f0 in (int(f) for f in faces):
        if not 0 <= f0 < n:
            continue
        out.add(f0)
        if not rev[f0]:
            continue
        near = neighbours(model) if near is None else near
        a0 = ax[f0]
        if sph[f0]:                                                # l'axe du fichier est quelconque
            a0 = next((ax[g] for g in sorted(near.get(f0, ())) if rev[g] and not sph[g]
                       and _line_gap(pt[f0], pt[g], ax[g]) <= tol), a0)
        w = pt - pt[f0]
        off = np.linalg.norm(w - (w @ a0)[:, None] * a0, axis=1)        # écart à l'axe du point d'axe de chaque face
        same = body == body[f0]
        group = set(np.flatnonzero(rev & same & (off <= tol) & ((np.abs(ax @ a0) >= cos) | sph)).tolist())
        for f in np.flatnonzero(is_plan & same & (np.abs(pn @ a0) >= cos)).tolist():
            if near.get(f) and near[f] <= group:
                group.add(f)
        out |= group
    return sorted(int(f) for f in out)


def _shared_edges(model) -> tuple:
    """Les arêtes communes à deux triangles de faces différentes : (sommets, arêtes (k, 2), triangles a, b)."""
    from .faces3d import _edge_pairs, merged_vertices
    fo = np.asarray(model.face_ids())
    V, idx = merged_vertices(np.asarray(model.triangles, dtype=float).reshape(-1, 3, 3))
    key, tri_of, starts = _edge_pairs(idx)
    sizes = np.diff(np.r_[starts, len(key)])
    pairs = starts[sizes == 2]                                     # arêtes partagées par deux triangles
    a, b = tri_of[pairs], tri_of[pairs + 1]
    cross = fo[a] != fo[b]
    return V, key[pairs][cross], a[cross], b[cross]


def neighbours(model) -> dict:
    """Pour chaque face, les faces qui ont une arête commune avec elle."""
    fo = np.asarray(model.face_ids())
    if not len(fo):
        return {}
    _V, _ek, a, b = _shared_edges(model)
    out: dict = {}
    for f, g in set(zip(fo[a].tolist(), fo[b].tolist())):
        out.setdefault(f, set()).add(g)
        out.setdefault(g, set()).add(f)
    return out


def _surfaces(model, n: int) -> tuple:
    """Par face : (plan ?, normale, cylindre ?, axe, point de l'axe) d'après le lecteur."""
    is_plan, pn = np.zeros(n, bool), np.zeros((n, 3))
    is_cyl, ca, cc = np.zeros(n, bool), np.zeros((n, 3)), np.zeros((n, 3))
    for f, k in enumerate(_kinds(model)[:n]):
        k = k or {}
        if k.get('genre') == 'plan' and k.get('normale') is not None:
            is_plan[f], pn[f] = True, _unit(k['normale'])
        elif k.get('genre') == 'cylindre' and k.get('axe') is not None and k.get('centre') is not None:
            is_cyl[f], ca[f], cc[f] = True, _unit(k['axe']), np.asarray(k['centre'], dtype=float)
    return is_plan, pn, is_cyl, ca, cc


def tangent_links(model, angle_deg: float = TANGENT_DEG, mesh_deg: float = TANGENT_MESH_DEG) -> dict:
    """Pour chaque face, les faces voisines qui la suivent sans arête vive : sur la plupart de leurs arêtes
    communes, les deux surfaces ont la même normale (au signe près) — celle du plan, du cylindre au milieu de
    l'arête, sinon celle du triangle (`mesh_deg` de tolérance : les facettes)."""
    from .faces3d import normals
    fo = np.asarray(model.face_ids())
    T = np.asarray(model.triangles, dtype=float).reshape(-1, 3, 3)
    if not len(T):
        return {}
    V, ek, a, b = _shared_edges(model)
    if not len(a):
        return {}
    n = int(fo.max()) + 1
    is_plan, pn, is_cyl, ca, cc = _surfaces(model, n)
    mid = 0.5 * (V[ek[:, 0]] + V[ek[:, 1]])
    nt = normals(T)

    def side(t):
        f = fo[t]
        nrm = nt[t].copy()
        p = is_plan[f]
        nrm[p] = pn[f[p]]
        c = is_cyl[f]
        if c.any():
            w = mid[c] - cc[f[c]]
            ax = ca[f[c]]
            r = w - (w * ax).sum(axis=1)[:, None] * ax
            nrm[c] = r / np.maximum(np.linalg.norm(r, axis=1), 1e-12)[:, None]
        return nrm, p | c
    na, ea = side(a)
    nb, eb = side(b)
    dot = np.abs((na * nb).sum(axis=1))
    ok = dot >= np.where(ea & eb, math.cos(math.radians(angle_deg)), math.cos(math.radians(mesh_deg)))
    fa, fb = fo[a], fo[b]
    pk = np.minimum(fa, fb) * n + np.maximum(fa, fb)
    uk, inv = np.unique(pk, return_inverse=True)
    good = np.bincount(inv, weights=ok.astype(float)) >= 0.5 * np.bincount(inv)
    links: dict = {}
    for k in uk[good].tolist():
        f, g = divmod(int(k), n)
        links.setdefault(f, set()).add(g)
        links.setdefault(g, set()).add(f)
    return links


def tangent(model, faces, angle_deg: float = TANGENT_DEG, mesh_deg: float = TANGENT_MESH_DEG) -> list:
    """Les faces choisies et, de proche en proche, celles qui les suivent sans arête vive, triées."""
    links = tangent_links(model, angle_deg, mesh_deg)
    out = {int(f) for f in faces}
    todo = list(out)
    while todo:
        for g in links.get(todo.pop(), ()):
            if g not in out:
                out.add(g)
                todo.append(g)
    return sorted(out)


def body_faces(model, faces) -> list:
    """Toutes les faces des corps des faces choisies, triées."""
    fo = np.asarray(model.face_ids())
    bid = getattr(model, 'body_ids', None)
    if bid is None or not len(fo):
        return sorted({int(f) for f in faces})
    bo = np.asarray(bid())
    bodies = np.unique(bo[np.isin(fo, [int(f) for f in faces])])
    return sorted(int(f) for f in np.unique(fo[np.isin(bo, bodies)]))


def invert(model, faces) -> list:
    """Les faces des corps des faces choisies qui ne le sont pas, triées."""
    chosen = {int(f) for f in faces}
    return [f for f in body_faces(model, faces) if f not in chosen] if chosen else []


def _axis_distance(c1, a1, c2, a2) -> float:
    """Plus courte distance entre deux droites (c, a)."""
    w = c2 - c1
    n = np.cross(a1, a2)
    if float(np.linalg.norm(n)) < 1e-9:
        return float(np.linalg.norm(w - (w @ a1) * a1))
    return abs(float(w @ _unit(n)))


def _angle(u, v) -> float:
    return math.degrees(math.acos(max(-1.0, min(1.0, float(_unit(u) @ _unit(v))))))


def _min_distance(P: np.ndarray, Q: np.ndarray) -> float:
    rng = np.random.default_rng(0)
    if len(P) > SAMPLE:
        P = P[rng.choice(len(P), SAMPLE, replace=False)]
    if len(Q) > SAMPLE:
        Q = Q[rng.choice(len(Q), SAMPLE, replace=False)]
    best = math.inf
    for i in range(0, len(P), 500):
        d = np.linalg.norm(P[i:i + 500, None, :] - Q[None, :, :], axis=2)
        best = min(best, float(d.min()))
    return best


def between(p: dict, q: dict, P: np.ndarray, Q: np.ndarray) -> dict:
    """Mesures entre deux faces décrites par `props` (sommets `P`, `Q`) : {'angle', 'distance', 'what'}, ce qui
    a un sens ; 'what' : 'parallel_planes', 'planes', 'parallel_axes', 'axes', 'axis_plane',
    'axis_normal_to_plane', 'plane_axis', 'nearest'."""
    kinds = (p['kind'], q['kind'])
    if kinds == ('plan', 'plan'):
        ang = _angle(p['normal'], q['normal'])
        if ang <= TOL_DEG or ang >= 180.0 - TOL_DEG:
            d = abs(float((Q @ p['normal']).mean()) - p['offset'])
            return {'what': 'parallel_planes', 'angle': ang, 'distance': d}
        return {'what': 'planes', 'angle': ang}
    if 'axis' in p and 'axis' in q:
        ang = _angle(p['axis'], q['axis'])
        ang = min(ang, 180.0 - ang)
        d = _axis_distance(p['centre'], p['axis'], q['centre'], q['axis'])
        return {'what': 'parallel_axes' if ang <= TOL_DEG else 'axes', 'angle': ang, 'distance': d}
    if 'axis' in p and q['kind'] == 'plan' or 'axis' in q and p['kind'] == 'plan':
        cyl, pl = (p, q) if 'axis' in p else (q, p)
        ang = _angle(cyl['axis'], pl['normal'])
        ang = min(ang, 180.0 - ang)
        if ang >= 90.0 - TOL_DEG:
            return {'what': 'axis_plane', 'angle': 90.0 - ang,
                    'distance': abs(float(cyl['centre'] @ pl['normal']) - pl['offset'])}
        if ang <= TOL_DEG:
            return {'what': 'axis_normal_to_plane', 'angle': 90.0 - ang}
        return {'what': 'plane_axis', 'angle': 90.0 - ang}
    return {'what': 'nearest', 'distance': _min_distance(P, Q)}


def measure(model, faces) -> dict:
    """{'faces' : [props…], 'between' : mesures entre les deux faces s'il y en a deux, 'area', 'bounds'} pour
    les faces `faces` du modèle."""
    fo = np.asarray(model.face_ids())
    T = np.asarray(model.triangles, dtype=float)
    faces = [int(f) for f in faces]
    tris = {f: T[fo == f] for f in faces}
    ps = [props(model, f, tris[f]) for f in faces]
    out = {'faces': ps, 'area': sum(p['area'] for p in ps)}
    pts = [tris[f].reshape(-1, 3) for f in faces if len(tris[f])]
    if pts:
        A = np.concatenate(pts)
        out['bounds'] = tuple(float(x) for x in np.r_[A.min(axis=0), A.max(axis=0)])
    if len(faces) == 2 and all(len(tris[f]) for f in faces):
        out['between'] = between(ps[0], ps[1], tris[faces[0]].reshape(-1, 3), tris[faces[1]].reshape(-1, 3))
    return out
