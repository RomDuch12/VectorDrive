"""Mécanismes d'une pièce à plusieurs corps (assemblage, moule en
plusieurs parties) : contacts entre corps, liaisons qui en découlent et
mouvement libre de chaque corps — pour les montrer et les animer dans la
vue 3D.

Repérage (réglable, `Settings`) :

- **contact plan** : deux faces planes de corps différents, parallèles (à
  `angle` degrés près), dans le même plan (à `tol` mm près), qui se
  recouvrent d'au moins `min_area` mm² ;
- **contact cylindrique** (STEP : faces cylindriques connues) : deux
  cylindres coaxiaux (à `tol` près) de même rayon (au jeu `clearance` près)
  qui se recouvrent le long de l'axe.

Liaison entre deux corps, d'après leurs contacts :

- cylindre(s) coaxiaux + appui plan perpendiculaire à l'axe : **pivot**
  (rotation autour de l'axe) ; sans appui : **pivot glissant** ;
- cylindres parallèles non coaxiaux (colonnes de guidage) : **glissière**
  le long de leur axe ;
- appuis plans d'une seule direction : **appui plan** — le corps peut s'en
  écarter (démoulage, ouverture) ; deux directions : **glissière** le long
  de leur intersection ; trois et plus : **encastrement**.

Le corps fixe est le plus gros (ou celui choisi) ; chaque autre corps
prend le mouvement de sa liaison avec le corps auquel il est relié, de
proche en proche.

**Collisions** (`collisions`) : les corps fermés en volumes
(core.watertight) sont déplacés pas à pas sur la course ; deux corps qui
prennent un volume commun (plus épais que `MIN_DEPTH`) s'interpénètrent —
au repos, ou dès la position trouvée (affinée par dichotomie) ; la **course libre** d'un corps
(`free_travel`) est celle qu'il parcourt seul avant sa première collision.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

import numpy as np

from . import faces3d

#: libellés des liaisons
JOINTS = {'appui': 'Appui plan', 'glissiere': 'Glissière', 'pivot': 'Pivot', 'pivot_glissant': 'Pivot glissant',
          'encastrement': 'Encastrement', 'aucune': 'Sans contact'}


@dataclass
class Settings:
    tol: float = 0.3              # mm : écart toléré entre deux faces en contact (jeu du plan de joint)
    angle: float = 1.0            # ° : écart toléré entre deux directions
    min_area: float = 1.0         # mm² : recouvrement minimal d'un contact plan
    clearance: float = 0.2        # mm : jeu toléré entre deux cylindres (ajustement)
    fixed: int = -1               # corps fixe ; -1 : le plus gros
    travel: float = 0.0           # mm : course des translations ; 0 : de quoi dégager le corps
    turn: float = 90.0            # ° : rotation des pivots


@dataclass
class Contact:
    a: int
    b: int
    kind: str                     # 'plan' ou 'cylindre'
    direction: tuple              # plan : normale, de a vers b ; cylindre : axe
    point: tuple
    area: float = 0.0
    radius: float = 0.0


@dataclass
class Joint:
    a: int
    b: int
    kind: str                     # clé de JOINTS
    axis: tuple = (0.0, 0.0, 1.0)
    point: tuple = (0.0, 0.0, 0.0)
    contacts: list = field(default_factory=list)


@dataclass
class Motion:
    """Mouvement libre d'un corps (par rapport au corps fixe) : 'translation'
    le long de `axis` de `amount` mm, ou 'rotation' autour de l'axe passant
    par `point` de `amount` degrés ; `parent` : corps dont il suit aussi le
    mouvement."""
    body: int
    kind: str
    axis: tuple
    point: tuple
    amount: float
    parent: int = -1
    joint: str = ''
    inverted: bool = False        # sens retourné par l'utilisateur


# --- faces ---------------------------------------------------------------------------------
def _unit(v):
    v = np.asarray(v, dtype=np.float64)
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def face_planes(model, angle: float = 1.0) -> dict:
    """{face: (normale unitaire vers l'extérieur de la matière, point,
    corps)} des faces planes — normale du STEP (orientée d'après la
    matière), sinon celle des triangles (STL : vers l'extérieur)."""
    tris = np.asarray(model.triangles, dtype=np.float64)
    fo = model.face_ids()
    bo = model.body_ids()
    nrm = faces3d.normals(tris)
    kinds = getattr(model, 'face_kinds', None) or []
    # maillage (STL, volumes) : le signe du volume de chaque corps dit si ses triangles regardent dehors
    vol = np.einsum('ij,ij->i', tris[:, 0], np.cross(tris[:, 1], tris[:, 2]))
    sens = np.where(np.bincount(bo, weights=vol, minlength=int(bo.max()) + 1 if len(bo) else 0) < 0, -1.0, 1.0)
    out = {}
    cos = math.cos(math.radians(angle))
    order = np.argsort(fo, kind='stable')
    starts = np.flatnonzero(np.r_[True, fo[order][1:] != fo[order][:-1]])
    ends = np.r_[starts[1:], len(order)]
    for s, e in zip(starts, ends):
        idx = order[s:e]
        n0 = nrm[idx[0]]
        if (np.abs(nrm[idx] @ n0) < cos).any():
            continue
        f = int(fo[idx[0]])
        k = kinds[f] if f < len(kinds) else {}
        if k.get('genre') == 'plan' and k.get('normale') is not None:
            n0 = _unit(k['normale'])                       # STEP : normale orientée d'après la matière
        else:
            n0 = n0 * sens[int(bo[idx[0]])]
        out[f] = (n0, tris[idx[0], 0], int(bo[idx[0]]))
    return out


def face_cylinders(model) -> dict:
    """{face: (axe unitaire, point de l'axe, rayon, corps)} des faces
    cylindriques connues (STEP)."""
    kinds = getattr(model, 'face_kinds', None) or []
    if not kinds:
        return {}
    fo, bo = model.face_ids(), model.body_ids()
    first = {}
    for i, f in enumerate(fo.tolist()):
        first.setdefault(f, i)
    out = {}
    for f, k in enumerate(kinds):
        if k.get('genre') == 'cylindre' and k.get('axe') is not None and k.get('centre') is not None \
                and k.get('rayon') and f in first:
            out[f] = (_unit(k['axe']), np.asarray(k['centre'], dtype=np.float64), float(k['rayon']),
                      int(bo[first[f]]))
    return out


def _plane_poly(tris, n):
    """Triangles projetés sur le plan de normale n : région shapely."""
    import shapely
    u = _unit(np.cross(n, [1.0, 0, 0] if abs(n[0]) < 0.9 else [0, 1.0, 0]))
    v = np.cross(n, u)
    P = np.stack([tris @ u, tris @ v], axis=-1)            # (k, 3, 2)
    polys = shapely.polygons(P)
    polys = polys[shapely.area(polys) > 1e-12]
    return shapely.union_all(polys) if len(polys) else shapely.Polygon(), u, v


def contacts(model, st: Settings | None = None) -> list[Contact]:
    """Contacts entre corps différents (voir le module)."""
    st = st or Settings()
    tris = np.asarray(model.triangles, dtype=np.float64)
    fo = model.face_ids()
    if model.body_count() < 2:
        return []
    out: list[Contact] = []
    planes = face_planes(model, st.angle)
    cos = math.cos(math.radians(st.angle))
    keys = list(planes)
    if keys:
        N = np.array([planes[k][0] for k in keys])
        P = np.array([planes[k][1] for k in keys])
        B = np.array([planes[k][2] for k in keys])
        D = np.einsum('ij,ij->i', N, P)
        polys = {}
        for i in range(len(keys)):
            dots = N[i + 1:] @ N[i]
            par = dots <= -cos                              # faces en vis-à-vis : normales opposées
            same = np.abs(D[i + 1:] + D[i]) <= st.tol       # même plan, au jeu près
            other = B[i + 1:] != B[i]
            for j in np.flatnonzero(par & same & other) + i + 1:
                fa, fb = keys[i], keys[j]
                if fa not in polys:
                    polys[fa] = _plane_poly(tris[fo == fa], N[i])
                pa, u, v = polys[fa]
                tb = tris[fo == fb]
                import shapely
                pb = shapely.union_all(shapely.polygons(np.stack([tb @ u, tb @ v], axis=-1)))
                area = pa.intersection(pb).area if not pa.is_empty and not pb.is_empty else 0.0
                if area < st.min_area:
                    continue
                a, b = int(B[i]), int(B[j])
                n = N[i].copy()                        # normale extérieure de la face de a : vers b
                c = pa.intersection(pb).centroid
                pt = P[i] + (c.x - P[i] @ u) * u + (c.y - P[i] @ v) * v
                out.append(Contact(a, b, 'plan', tuple(n.tolist()), tuple(pt.tolist()), float(area)))
    cyl = face_cylinders(model)
    ck = list(cyl)
    for i, fa in enumerate(ck):
        aa, ca, ra, ba = cyl[fa]
        for fb in ck[i + 1:]:
            ab, cb, rb, bb = cyl[fb]
            if ba == bb or abs(abs(aa @ ab) - 1) > 1 - cos or abs(ra - rb) > st.clearance + st.tol:
                continue
            d = cb - ca
            off = np.linalg.norm(d - (d @ aa) * aa)
            if off > st.tol + st.clearance:
                continue
            ta = tris[fo == fa].reshape(-1, 3) @ aa
            tb = tris[fo == fb].reshape(-1, 3) @ aa
            if min(ta.max(), tb.max()) - max(ta.min(), tb.min()) <= st.tol:
                continue                                   # pas de recouvrement le long de l'axe
            out.append(Contact(ba, bb, 'cylindre', tuple(aa.tolist()), tuple(ca.tolist()),
                               radius=float(min(ra, rb))))
    return out


# --- liaisons ------------------------------------------------------------------------------
def _independent(dirs, cos: float) -> list:
    """Directions deux à deux non parallèles (au signe près)."""
    out = []
    for d in dirs:
        d = _unit(d)
        if all(abs(d @ e) < cos for e in out):
            out.append(d)
    return out


def free_direction(normals, axes=(), angle: float = 1.0):
    """Direction d dans laquelle un corps peut s'écarter de tous ses appuis
    plans (normales vers lui : n·d ≥ 0 pour toutes, à `angle` près) — et,
    s'il a des contacts cylindriques, le long de leur axe seulement ; la
    plus « dégagée » (min n·d le plus grand). None : bloqué."""
    eps = math.sin(math.radians(max(angle, 0.5)))
    N = [_unit(n) for n in normals]
    if axes:
        a = _unit(axes[0])
        cands = [a, -a]
    else:
        cands = []
        if N:
            s = np.sum(N, axis=0)
            if np.linalg.norm(s) > 1e-9:
                cands.append(_unit(s))
            n0 = N[0]                                  # directions du plan des appuis (pris entre deux plans)
            u = _unit(np.cross(n0, [1.0, 0, 0] if abs(n0[0]) < 0.9 else [0, 1.0, 0]))
            cands += [u, -u, _unit(np.cross(n0, u)), -_unit(np.cross(n0, u))]
        cands += N
        for i in range(len(N)):
            for j in range(i + 1, len(N)):
                c = np.cross(N[i], N[j])
                if np.linalg.norm(c) > 1e-6:
                    cands += [_unit(c), -_unit(c)]
    best, score = None, -2.0
    for d in cands:
        if not np.isfinite(d).all() or np.linalg.norm(d) < 0.5:
            continue
        sc = min((float(n @ d) for n in N), default=1.0)
        # à égalité, la direction qui s'écarte le plus franchement (moyenne des n·d)
        sc2 = sc + 1e-3 * (float(np.mean([n @ d for n in N])) if N else 0.0)
        if sc >= -eps and sc2 > score:
            best, score = d, sc2
    return best


def joints(model, st: Settings | None = None, found: list | None = None) -> list[Joint]:
    """Une liaison par paire de corps en contact (le corps b vu depuis a :
    `axis` est la direction dans laquelle b se dégage ou glisse)."""
    st = st or Settings()
    cos = math.cos(math.radians(max(st.angle, 0.5)))
    eps = math.sin(math.radians(max(st.angle, 0.5)))
    found = contacts(model, st) if found is None else found
    pairs: dict = {}
    for c in found:
        pairs.setdefault((min(c.a, c.b), max(c.a, c.b)), []).append(c)
    out = []
    for (a, b), cs in sorted(pairs.items()):
        cyl = [c for c in cs if c.kind == 'cylindre']
        pl = [c for c in cs if c.kind == 'plan']
        normals = [_unit(np.asarray(c.direction)) * (1 if c.a == a else -1) for c in pl]   # de a vers b
        axes = _independent([c.direction for c in cyl], cos)
        if len(axes) > 1:
            out.append(Joint(a, b, 'encastrement', (0.0, 0.0, 1.0), cs[0].point, cs))
            continue
        if cyl:
            ax = _unit(cyl[0].direction)
            pts = [np.asarray(c.point) for c in cyl]
            coaxial = all(np.linalg.norm((p - pts[0]) - ((p - pts[0]) @ ax) * ax) <= st.tol + st.clearance
                          for p in pts)
            lateral = [n for n in normals if abs(n @ ax) < cos]          # appuis qui ne sont pas des butées
            if coaxial and not lateral:
                stop = [n for n in normals if abs(n @ ax) >= cos]
                d = free_direction(stop, [ax], st.angle) if stop else ax
                kind = 'pivot' if stop else 'pivot_glissant'
                out.append(Joint(a, b, kind, tuple((d if d is not None else ax).tolist()),
                                 tuple(pts[0].tolist()), cs))
                continue
        d = free_direction(normals, [axes[0]] if axes else (), st.angle)
        if d is None:
            out.append(Joint(a, b, 'encastrement', (0.0, 0.0, 1.0), cs[0].point, cs))
            continue
        side = _independent([n for n in normals if abs(n @ d) <= eps], cos)   # appuis le long du mouvement
        kind = 'glissiere' if (len(side) >= 2 or cyl) else 'appui'
        out.append(Joint(a, b, kind, tuple(d.tolist()), cs[0].point, cs))
    return out


def body_sizes(model) -> np.ndarray:
    tris = np.asarray(model.triangles, dtype=np.float64)
    bo = model.body_ids()
    n = model.body_count()
    out = np.zeros(n)
    a = 0.5 * np.linalg.norm(np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]), axis=1)
    np.add.at(out, bo, a)
    return out


def fixed_body(model, st: Settings) -> int:
    n = model.body_count()
    if 0 <= st.fixed < n:
        return st.fixed
    return int(np.argmax(body_sizes(model))) if n else 0


def _extent(model, b: int, axis) -> float:
    pts = np.asarray(model.triangles, dtype=np.float64)[model.body_ids() == b].reshape(-1, 3)
    if not len(pts):
        return 0.0
    s = pts @ _unit(axis)
    return float(s.max() - s.min())


def motions(model, st: Settings | None = None, found_joints: list | None = None) -> list[Motion]:
    """Mouvement libre de chaque corps, du corps fixe vers les autres
    (parcours des liaisons) ; un corps encastré ou sans contact ne bouge
    pas."""
    st = st or Settings()
    js = joints(model, st) if found_joints is None else found_joints
    ground = fixed_body(model, st)
    by_body: dict = {}
    for j in js:
        by_body.setdefault(j.a, []).append(j)
        by_body.setdefault(j.b, []).append(j)
    seen = {ground}
    todo = [ground]
    out = []
    while todo:
        p = todo.pop(0)
        for j in by_body.get(p, []):
            c = j.b if j.a == p else j.a
            if c in seen:
                continue
            seen.add(c)
            todo.append(c)
            if j.kind in ('encastrement', 'aucune'):
                out.append(Motion(c, 'fixe', (0.0, 0.0, 1.0), j.point, 0.0, p, j.kind))   # suit son parent
                continue
            ax = np.asarray(j.axis, dtype=np.float64)
            if j.a != p:
                ax = -ax                                    # `axis` : b vu de a ; ici l'enfant vu du parent
            if j.kind == 'pivot':
                out.append(Motion(c, 'rotation', tuple(ax.tolist()), j.point, st.turn, p, j.kind))
            else:
                amount = st.travel if st.travel > 0 else round(_extent(model, c, ax) * 1.2 + 1.0, 1)
                out.append(Motion(c, 'translation', tuple(ax.tolist()), j.point, amount, p, j.kind))
    return out


def rotation_matrix(axis, deg: float) -> np.ndarray:
    a = _unit(axis)
    t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * (K @ K)


def poses(found: list[Motion], k: float) -> dict:
    """Déplacements des corps à l'avancement k (0 : fermé, 1 : ouvert) :
    {corps: (R, t)} — chaque corps suit aussi le mouvement de son parent."""
    local = {}
    for m in found:
        if m.kind == 'fixe':
            local[m.body] = (np.eye(3), np.zeros(3))
        elif m.kind == 'rotation':
            R = rotation_matrix(m.axis, m.amount * k)
            p = np.asarray(m.point, dtype=np.float64)
            local[m.body] = (R, p - R @ p)
        else:
            local[m.body] = (np.eye(3), np.asarray(m.axis, dtype=np.float64) * m.amount * k)
    parent = {m.body: m.parent for m in found}
    out = {}

    def world(b, depth=0):
        if b in out:
            return out[b]
        R, t = local.get(b, (np.eye(3), np.zeros(3)))
        par = parent.get(b, -1)
        if par in parent and depth < 50:
            Rp, tp = world(par, depth + 1)
            R, t = Rp @ R, Rp @ t + tp
        out[b] = (R, t)
        return out[b]
    for b in local:
        world(b)
    return out


# --- collisions ----------------------------------------------------------------------------
#: épaisseur d'interpénétration tolérée (mm) : les facettes de deux cylindres ajustés se chevauchent un peu
MIN_DEPTH = 0.05


@dataclass
class Clash:
    """Deux corps qui s'interpénètrent à l'avancement `k` (volume commun en
    mm³ à la position contrôlée) ; `free` : dernier avancement trouvé libre."""
    a: int
    b: int
    k: float
    volume: float
    free: float = 0.0


def body_manifolds(model) -> tuple[dict, dict]:
    """Volumes fermés des corps (core.watertight), pour les contrôles de
    collision : ({corps: Manifold}, {corps: raison} de ceux dont le maillage
    ne ferme pas — ou ne renferme aucun volume, une surface ouverte)."""
    from . import solids as SO
    from . import watertight as WT
    ids = model.body_ids()
    T = np.asarray(model.triangles, dtype=np.float64)
    out, failed = {}, {}
    for b in range(model.body_count()):
        try:
            man = WT.to_solid(T[ids == b]).manifold()
        except SO.SolidError as ex:
            failed[b] = str(ex)
            continue
        if abs(float(man.volume())) <= 1e-9:
            failed[b] = 'aucun volume (surface ouverte)'
            continue
        out[b] = man
    return out, failed


def _moved(man, pose):
    R, t = pose
    if np.allclose(R, np.eye(3)) and not np.any(t):
        return man
    return man.transform(np.hstack([R, np.asarray(t, dtype=np.float64)[:, None]]))


def _boxes_touch(ma, mb) -> bool:
    a, b = np.asarray(ma.bounding_box()), np.asarray(mb.bounding_box())
    return not (np.any(a[:3] > b[3:]) or np.any(b[:3] > a[3:]))


def _penetration(inter, min_volume: float, min_depth: float) -> float:
    """Volume d'une interpénétration (0 si elle est tolérée : moins de
    `min_volume` mm³, ou plus mince que `min_depth` mm — épaisseur estimée
    2 × volume / surface, celle d'une lame)."""
    v = float(inter.volume())
    if v <= min_volume:
        return 0.0
    s = float(inter.surface_area())
    return v if s > 0 and 2.0 * v / s > min_depth else 0.0


def collisions(mans: dict, found: list[Motion], steps: int = 24, min_volume: float | None = None,
               min_depth: float = MIN_DEPTH, refine: int = 12) -> list[Clash]:
    """Interpénétrations des corps pendant le mouvement : au repos (k = 0)
    entre tous les corps, puis de k = 1/`steps` à 1 entre les corps qui
    bougent l'un par rapport à l'autre ; pour chaque paire, la première
    position en collision, affinée par dichotomie (`refine` pas) depuis la
    dernière position libre. Tolérées : moins de `min_volume` mm³ (par
    défaut 1e-7 du plus petit des deux corps, au moins 0,001 mm³), ou plus
    mince que `min_depth` (facettes de deux cylindres ajustés) ; deux faces
    en contact n'ont pas de volume commun. Une paire qui s'interpénètre déjà
    au repos est encore contrôlée pendant le mouvement, sur ce qui s'ajoute
    à son volume commun de départ. Un obstacle plus mince qu'un pas peut
    passer entre deux positions."""
    ident = (np.eye(3), np.zeros(3))
    size = {b: abs(float(m.volume())) for b, m in mans.items()}
    keys = sorted(mans)
    pairs = [(a, b) for i, a in enumerate(keys) for b in keys[i + 1:]]

    def tol(a, b):
        return min_volume if min_volume is not None else max(1e-3, 1e-7 * min(size[a], size[b]))

    base = {}                                            # volume commun au repos, retranché pendant le mouvement
    out, done = [], set()
    for a, b in pairs:
        if not _boxes_touch(mans[a], mans[b]):
            continue
        inter = mans[a] ^ mans[b]
        if float(inter.volume()) > 0:
            base[(a, b)] = inter
            v = _penetration(inter, tol(a, b), min_depth)
            if v:
                out.append(Clash(a, b, 0.0, v, 0.0))

    def common(P, a, b):
        """Volume commun ajouté depuis le repos (Manifold), ou None."""
        ma, mb = _moved(mans[a], P.get(a, ident)), _moved(mans[b], P.get(b, ident))
        if not _boxes_touch(ma, mb):
            return None
        inter = ma ^ mb
        return inter - base[(a, b)] if (a, b) in base else inter

    def hit(P, a, b):
        inter = common(P, a, b)
        return 0.0 if inter is None else _penetration(inter, tol(a, b), min_depth)

    def volume(k, a, b):
        inter = common(poses(found, k), a, b)
        return 0.0 if inter is None else float(inter.volume())

    prev = 0.0
    n = max(1, steps)
    for i in range(1, n + 1):
        k = i / n
        P = poses(found, k)
        for a, b in pairs:
            if (a, b) in done:
                continue
            (Ra, ta), (Rb, tb) = P.get(a, ident), P.get(b, ident)
            if np.allclose(Ra, Rb) and np.allclose(ta, tb):
                continue                                 # pas de mouvement l'un par rapport à l'autre
            v = hit(P, a, b)
            if not v:
                continue
            lo, hi = prev, k
            for _r in range(refine):                     # où l'interpénétration dépasse l'épaisseur tolérée
                mid = (lo + hi) / 2
                if hit(poses(found, mid), a, b):
                    hi = mid
                else:
                    lo = mid
            noise = volume(prev, a, b) + tol(a, b)       # puis où le volume commun se met à croître
            lo = prev
            for _r in range(refine):
                mid = (lo + hi) / 2
                if volume(mid, a, b) > noise:
                    hi = mid
                else:
                    lo = mid
            out.append(Clash(a, b, hi, v, lo))
            done.add((a, b))
        prev = k
    return sorted(out, key=lambda c: (c.k, c.a, c.b))


def free_travel(mans: dict, found: list[Motion], body: int, steps: int = 48) -> float | None:
    """Course libre du corps `body`, les autres mouvements arrêtés (ses
    enfants le suivent, animés ou non) : ce qu'il parcourt de sa course
    réglée (mm ou degrés) avant sa première collision, arrondi par défaut au
    millième ; 0 s'il est bloqué dès le départ ; None s'il est libre sur
    toute la course (ou sans mouvement)."""
    m = next((x for x in found if x.body == body and x.kind != 'fixe'), None)
    if m is None or m.amount <= 0:
        return None
    solo = [x if x.body == body or x.kind == 'fixe' else replace(x, amount=0.0) for x in found]
    hits = [c for c in collisions(mans, solo, steps) if c.k > 0]
    return math.floor(m.amount * hits[0].free * 1000.0) / 1000.0 if hits else None
