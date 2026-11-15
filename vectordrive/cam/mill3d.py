"""Usinage 3D d'une pièce (STEP, STL, 3D XML), outils de base communs aux
stratégies 3D : la pièce posée comme sur la machine (haut de la pièce à
Z = 0), sa carte de hauteurs, la zone à usiner — toute la pièce, les faces
choisies dans la vue 3D (`Operation.faces3d`) ou l'intérieur de contours
fermés choisis (`Operation.contours3d`) — et le balayage en aller-retour
limité à cette zone.

L'outil évite toujours **toute** la pièce (carte compensée de toutes les
faces) ; la zone dit seulement où il travaille.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass

import numpy as np

from ..core import progress

#: plus grande carte de hauteurs (points)
MAX_POINTS = 6_000_000
#: stratégies qui usinent une pièce 3D (zone : faces ou contours choisis dans la vue 3D)
KINDS = ('surface3d', 'ebauche3d', 'reprise3d', 'niveaux3d')
#: modèles chargés : (fichier, date, placement) → Model3D (les plus récents)
_CACHE: dict = {}
_CACHE_MAX = 3
_RAW: dict = {}                     # pièces telles que lues : à part (les poses ne les chassent pas)
_RAW_MAX = 2


def model_path(doc, op) -> str:
    """Fichier 3D de l'opération : le sien, sinon celui d'où vient le
    dessin (STEP, STL, 3D XML) ; '' sinon."""
    p = getattr(op, 'model_path', '') or ''
    from ..io import model3d
    if p:
        return model3d.resolve(doc, p)                 # déplacé avec la pièce du dessin : elle
    return model3d.source_of(doc) or ''


def _is_source(doc, path) -> bool:
    """`path` est-il la pièce 3D d'où vient le dessin (io.model3d.source_of :
    celle qu'on a ouverte, ou celle que garde le .vdz rouvert) ?"""
    from ..io import model3d
    src = model3d.source_of(doc)
    return bool(src) and bool(path) and \
        os.path.normcase(os.path.abspath(str(src))) == os.path.normcase(os.path.abspath(str(path)))


def raw_model(path: str):
    """Modèle du fichier tel que lu (redressé, sans placement), en mémoire."""
    from ..io import model3d
    key = (os.path.normcase(os.path.abspath(str(path))), os.path.getmtime(path), None)
    m = _RAW.get(key)
    if m is None:
        m = model3d.load(path, None)
        _RAW[key] = m
        while len(_RAW) > _RAW_MAX:
            _RAW.pop(next(iter(_RAW)))
    return m


def cached_raw_model(path: str):
    """Le modèle du fichier s'il est déjà en mémoire (`raw_model`), sinon
    None : rien n'est lu."""
    try:
        key = (os.path.normcase(os.path.abspath(str(path))), os.path.getmtime(path), None)
    except (OSError, TypeError, ValueError):
        return None
    return _RAW.get(key)


def submodel(model, body: int):
    """Le corps `body` seul (mêmes numéros de faces)."""
    from ..io.model3d import Model3D
    sel = model.body_ids() == body
    fo = model.face_ids()[sel]
    segs = np.asarray(model.segments)
    if len(segs):
        segs = segs[model.segment_bodies() == body]
    return Model3D(np.asarray(model.triangles)[sel], np.asarray(model.colors)[sel], segs,
                   f'{model.name} — {model.body_name(body)}', list(model.notes), 1, model.faces, fo,
                   list(model.face_kinds), np.zeros(int(sel.sum()), dtype=np.int64), [model.body_name(body)])


def side_placement(doc, path: str, face: str = '', body: int = -1):
    """Placement de la pièce sur la machine : celui du dessin (pièce du
    dessin) ; `face` : cette face vers l'outil, même rotation et même
    position (centrée sur la plaque, dans le coin…) — la pièce retournée
    pour une seconde prise ; `body` : ce corps seul, posé comme une pièce
    à part. None : coordonnées du fichier."""
    from ..core import placement3d as P3
    from ..io import model3d
    if body >= 0 and body >= raw_model(path).body_count():
        body = -1                                      # corps inconnu : toute la pièce, pas un corps vide
    pl = P3.of(doc) if _is_source(doc, path) else None
    own = P3.body_of(doc, body) if body >= 0 and pl is not None else None
    if own is not None:                                # corps positionné à part : sa pose à lui
        p = P3.Placement(face or own.face, own.rot, own.mode, own.dx, own.dy)
        if p.mode != 'libre':
            turned = model3d.placed(submodel(raw_model(path), body), P3.Placement(p.face, p.rot))
            plate = getattr(doc, 'plate', None)
            box = (plate.x, plate.y, plate.width, plate.height) if plate is not None else None
            P3.resolve(p, turned.bounds(), box)
        return p
    same_face = not face or (pl is not None and face == pl.face) or (pl is None and face == '+Z')
    if same_face and (body < 0 or pl is None or pl.mode in ('libre', 'fichier')):
        return pl
    base = pl or P3.Placement()
    p = P3.Placement(face or base.face, base.rot, base.mode, base.dx, base.dy)
    if p.mode != 'libre':
        raw = raw_model(path)
        if body >= 0:
            raw = submodel(raw, body)
        turned = model3d.placed(raw, P3.Placement(p.face, base.rot))
        plate = getattr(doc, 'plate', None)
        box = (plate.x, plate.y, plate.width, plate.height) if plate is not None else None
        P3.resolve(p, turned.bounds(), box)
    return p


def load_model(doc, path: str, face: str = '', body: int = -1):
    """Modèle 3D du fichier, posé comme sur la machine si c'est la pièce du
    dessin (`core.placement3d`) — `face` : cette face vers l'outil (seconde
    prise), `body` : ce corps seul ; gardé en mémoire (même fichier, même
    date, même placement : pas relu)."""
    from ..core import placement3d as P3
    from ..io import model3d
    pl = side_placement(doc, path, face, body)
    raw = raw_model(path)
    if body >= 0 and body >= raw.body_count():
        body = -1
    if (pl is None or pl.is_identity()) and body < 0:
        return raw
    key = (os.path.normcase(os.path.abspath(str(path))), os.path.getmtime(path),
           tuple(P3.to_dict(pl).values()) if pl is not None else None, body)
    m = _CACHE.get(key)
    if m is None:
        base = submodel(raw, body) if body >= 0 else raw
        m = model3d.placed(base, pl) if pl is not None else base
        _CACHE[key] = m
        while len(_CACHE) > _CACHE_MAX:
            _CACHE.pop(next(iter(_CACHE)))
    return m


def volumes_model(doc, face: str = '', body: int = -1, edges: bool = True):
    """Les volumes du dessin (modélisés dans VectorDrive : extrusions,
    booléens, pousser-tirer…) comme pièce à usiner, un corps par volume ;
    `face` vers l'outil, `body` seul ; `edges` faux : sans arêtes. None :
    aucun volume."""
    from ..core import solids as SO
    from ..core import placement3d as P3
    from ..io import model3d
    if not SO.available():
        return None
    vols = [s for _it, s in SO.doc_solids(doc)]
    if not vols:
        return None
    m = SO.to_model(vols, edges=edges)
    if m is None:
        return None
    if body >= 0 and body < m.body_count():
        m = submodel(m, body)
    if face and face != '+Z':
        m = model3d.placed(m, P3.Placement(face))
    return m


def volume_items(doc) -> list:
    """Objets des volumes du dessin, dans l'ordre des corps de
    `volumes_model` (visibles, non vides)."""
    from ..core import solids as SO
    if not SO.available() or getattr(doc, 'layers', None) is None:
        return []
    return [getattr(it, 'id', '') for it, s in SO.doc_solids(doc) if not s.is_empty()]


def op_body(doc, op) -> int | None:
    """Corps que l'opération usine seul : `body3d` ; volumes du dessin :
    celui de l'objet gardé (`body3d_ref`, rangs changés par un calque caché
    ou un volume ajouté) — None : ce volume est caché ou supprimé (ou le
    numéro dépasse les volumes)."""
    b = int(getattr(op, 'body3d', -1))
    if b < 0 or model_path(doc, op):
        return b
    items = volume_items(doc)
    item = _ref_item(op, b)
    if item:
        return items.index(item) if item in items else None
    return b if b < len(items) else None


def _ref_item(op, b: int) -> str:
    """Objet volume gardé avec l'opération pour le numéro `b` ('' : aucun,
    ou gardé pour un autre numéro, ou mal écrit)."""
    ref = getattr(op, 'body3d_ref', None)
    if not isinstance(ref, dict) or not isinstance(ref.get('item'), str):
        return ''
    try:
        return ref['item'] if int(ref.get('n', -2)) == b else ''
    except (TypeError, ValueError):
        return ''


def bind_volumes(doc, setup) -> None:
    """Opérations sur un volume du dessin seul : l'objet volume gardé avec
    leur numéro (`body3d_ref`) ; numéro changé depuis (formulaire) : l'objet
    de ce numéro-là."""
    items = None
    for o in setup.operations:
        b = int(getattr(o, 'body3d', -1))
        if o.kind == 'instruction' or b < 0 or model_path(doc, o):
            if getattr(o, 'body3d_ref', None):
                o.body3d_ref = {}
            continue
        if _ref_item(o, b):
            continue                                       # gardé : il suit son objet
        items = volume_items(doc) if items is None else items
        o.body3d_ref = {'item': items[b], 'n': b} if b < len(items) else {}


def zone_frame(doc, path: str) -> dict:
    """Placement de la pièce `path` posée comme le dessin, gardé avec des
    contours de zone qu'on vient d'y choisir (`Operation.contours3d_pl`) : ils
    la suivent quand elle est replacée ou suit la plaque ; {} : volumes du
    dessin, autre fichier (coordonnées qui ne bougent pas)."""
    from ..core import placement3d as P3
    if not path or not _is_source(doc, path):
        return {}
    return P3.to_dict(side_placement(doc, path, '') or P3.Placement())


def zone_op(doc, op):
    """L'opération telle que ses zones s'appliquent à sa prise : contours
    choisis dans la vue 3D (pièce posée comme le dessin, telle qu'elle
    l'était alors : `contours3d_pl`) reportés sur la pièce telle qu'elle est
    posée pour sa prise (tournée vers `setup_face`, corps seul, replacée)."""
    face = getattr(op, 'setup_face', '') or ''
    body = int(getattr(op, 'body3d', -1))
    loops = getattr(op, 'contours3d', None) or []
    if not loops:
        return op
    path = model_path(doc, op)
    from ..core import placement3d as P3
    if not path:                                       # volumes du dessin : posés tels quels, retournés au besoin
        if not face and body < 0:
            return op
        view, side = P3.Placement(), P3.Placement(face or '+Z')
    else:
        view = P3.from_dict(getattr(op, 'contours3d_pl', None)) if _is_source(doc, path) else None
        view = view or side_placement(doc, path, '') or P3.Placement()
        side = side_placement(doc, path, face, body) or P3.Placement()
    if P3.to_dict(view) == P3.to_dict(side):
        return op
    import copy
    R = view.rotation()
    out = []
    for L in loops:
        a = np.asarray(L, dtype=np.float64).reshape(-1, 3).copy()
        a[:, 0] -= view.dx
        a[:, 1] -= view.dy
        out.append(side.apply(a @ R).tolist())             # R orthogonale : inverse = transposée
    c = copy.copy(op)
    c.contours3d = out
    return c


@dataclass
class Grid:
    """Grille de la carte : origine (x0, y0), nx × ny points au pas res."""
    x0: float
    y0: float
    nx: int
    ny: int
    res: float

    @property
    def xs(self):
        return self.x0 + np.arange(self.nx) * self.res

    @property
    def ys(self):
        return self.y0 + np.arange(self.ny) * self.res

    def cell(self, x: float, y: float) -> tuple[int, int]:
        """(ligne, colonne) du point le plus proche, bornées à la grille."""
        i = min(self.nx - 1, max(0, int(round((x - self.x0) / self.res))))
        j = min(self.ny - 1, max(0, int(round((y - self.y0) / self.res))))
        return j, i


class TooBig(ValueError):
    pass


def grid_for(x0: float, y0: float, x1: float, y1: float, margin: float, res: float) -> Grid:
    nx = int(math.ceil((x1 - x0 + 2 * margin) / res)) + 1
    ny = int(math.ceil((y1 - y0 + 2 * margin) / res)) + 1
    if nx * ny > MAX_POINTS:
        raise TooBig(f'carte de {nx} × {ny} points, trop grande — augmenter le pas')
    return Grid(x0 - margin, y0 - margin, nx, ny, res)


def dilate(mask, k: int):
    """Masque élargi de k points (disque approché : k pas de 3 × 3 en
    croix puis en carré alternés)."""
    m = np.asarray(mask, dtype=bool).copy()
    for step in range(max(0, int(k))):
        g = m.copy()
        g[1:] |= m[:-1]
        g[:-1] |= m[1:]
        g[:, 1:] |= m[:, :-1]
        g[:, :-1] |= m[:, 1:]
        if step % 2:
            g[1:, 1:] |= m[:-1, :-1]
            g[:-1, :-1] |= m[1:, 1:]
            g[1:, :-1] |= m[:-1, 1:]
            g[:-1, 1:] |= m[1:, :-1]
        m = g
    return m


def contour_polygons(loops):
    """Contours fermés choisis (listes de points [x, y(, z)]) → région
    shapely (vue de dessus ; un contour dans un autre fait un trou)."""
    import shapely
    polys = []
    for L in loops or []:
        pts = [(float(p[0]), float(p[1])) for p in L]
        if len(pts) >= 3:
            g = shapely.make_valid(shapely.Polygon(pts))
            if not g.is_empty and g.area > 1e-9:
                polys.append(g)
    if not polys:
        return None
    reg = polys[0]
    for g in polys[1:]:                                    # pair-impair : l'îlot d'une poche reste hors zone
        reg = reg.symmetric_difference(g)
    return reg


def has_zone(op) -> bool:
    return bool(getattr(op, 'faces3d', None) or getattr(op, 'contours3d', None))


def _footprint(tris, g: Grid):
    """Points de la grille sous les arêtes des triangles (vue de dessus) —
    une paroi verticale n'a pas d'aire vue de dessus, mais un tracé."""
    m = np.zeros((g.ny, g.nx), dtype=bool)
    t = np.asarray(tris, dtype=np.float64).reshape(-1, 3, 3)
    if not len(t):
        return m
    for a, b in ((0, 1), (1, 2), (2, 0)):
        p, q = t[:, a, :2], t[:, b, :2]
        n = int(max(1, np.ceil(np.linalg.norm(q - p, axis=1).max() / (g.res / 2))))
        for k in range(n + 1):
            x = p + (q - p) * (k / n)
            i = np.clip(np.round((x[:, 0] - g.x0) / g.res).astype(int), 0, g.nx - 1)
            j = np.clip(np.round((x[:, 1] - g.y0) / g.res).astype(int), 0, g.ny - 1)
            m[j, i] = True
    return m


def zone_mask(op, model, g: Grid, T=None, stock: float = 0.0, warnings=None, tool=None):
    """Points de la grille où l'outil travaille, ou None (toute la pièce).

    - faces choisies, balayage (cotes de pointe T et outil donnés) : là où
      l'outil touche bien ces faces — sa cote est celle qu'il aurait si
      elles seules existaient (en pente aussi), pas celle où une paroi
      voisine le tient au-dessus ;
    - faces choisies, sans T (ébauche, niveaux constants) : leur vue de
      dessus et le tracé de leurs arêtes (parois verticales comprises) ;
    - contours fermés : leur intérieur.
    `op.extension` (mm) élargit la zone."""
    if isinstance(model, ReliefPiece):                 # un relief : son rectangle
        return model.footprint
    faces = list(getattr(op, 'faces3d', None) or [])
    loops = list(getattr(op, 'contours3d', None) or [])
    if not faces and not loops:
        return None
    from ..core import faces3d
    from .advanced import heightmap_from_triangles
    mask = np.zeros((g.ny, g.nx), dtype=bool)
    if faces:
        idx = faces3d.face_triangles(model.face_ids(), faces)
        sel = np.asarray(model.triangles, dtype=np.float64)[idx]
        top = float(model.bounds()[5])
        Hs = heightmap_from_triangles(sel, g.x0, g.y0, g.nx, g.ny, g.res) - top
        m = np.isfinite(Hs)
        if T is not None and tool is not None:
            from .advanced import with_stock
            Ts = with_stock(np.where(m, Hs, -np.inf), g.res, tool, stock, pad=-np.inf)   # ces faces seules
            m = m & np.isfinite(Ts) & (T <= Ts + max(0.02, g.res * 0.5))   # centre de l'outil au-dessus des faces
        elif T is not None:
            touch = np.zeros_like(m)
            touch[m] = T[m] <= Hs[m] + stock + max(0.02, g.res * 0.5)
            m = touch
        else:
            m |= _footprint(sel - [0.0, 0.0, top], g)
        if not m.any() and warnings is not None and T is not None:
            warnings.append('faces choisies : rien à balayer (parois verticales : stratégie « Niveaux constants »)')
        mask |= m
    if loops:
        import shapely
        reg = contour_polygons(loops)
        if reg is not None:
            X, Y = np.meshgrid(g.xs, g.ys)
            mask |= shapely.contains_xy(reg, X, Y)
    ext = max(0.0, float(getattr(op, 'extension', 0.0) or 0.0))
    if ext > 0:
        mask = dilate(mask, int(math.ceil(ext / g.res)))
    return mask


def zone_bbox(op, model):
    """(x0, y0, x1, y1) de la zone choisie (faces, contours), ou None."""
    from ..core import faces3d
    pts = []
    faces = list(getattr(op, 'faces3d', None) or [])
    if faces:
        idx = faces3d.face_triangles(model.face_ids(), faces)
        if len(idx):
            pts.append(np.asarray(model.triangles, dtype=np.float64)[idx].reshape(-1, 3)[:, :2])
    for L in getattr(op, 'contours3d', None) or []:
        a = np.asarray(L, dtype=np.float64)
        if a.ndim == 2 and len(a):
            pts.append(a[:, :2])
    if not pts:
        return None
    a = np.concatenate(pts)
    return (*a.min(axis=0).tolist(), *a.max(axis=0).tolist())


def useful_levels(levels, T, mask=None) -> list:
    """Cotes de passe utiles : jusqu'à la première sous le point le plus
    bas que l'outil atteint (zone choisie) — les suivantes repasseraient
    sur la surface."""
    vals = T[mask] if mask is not None else T
    vals = vals[np.isfinite(vals)]
    if not len(vals) or not levels:
        return list(levels)
    low = float(vals.min())
    out = []
    for z in levels:
        out.append(z)
        if z <= low + 1e-9:
            break
    return out


def _runs(row) -> list[tuple[int, int]]:
    """Morceaux [début, fin[ des True d'une ligne du masque."""
    r = np.asarray(row, dtype=np.int8)
    d = np.diff(np.r_[0, r, 0])
    return list(zip(np.flatnonzero(d == 1).tolist(), np.flatnonzero(d == -1).tolist()))


def _simplify(pts: list, tol: float) -> list:
    from .advanced import _simplify as simp
    return simp(pts, tol)


def follow(T, g: Grid, a, b, zl: float) -> list:
    """Liaison de a à b en suivant la carte (pas d'un point de grille) :
    l'outil reste sur la surface compensée, jamais dedans."""
    n = max(1, int(math.ceil(math.dist(a[:2], b[:2]) / g.res)))
    out = []
    for k in range(1, n + 1):
        t = k / n
        x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        j, i = g.cell(x, y)
        out.append((x, y, max(float(T[j, i]), zl)))
    out[-1] = tuple(b)
    return out


class SwapXY:
    """Émetteur qui échange X et Y (passes selon Y sur la carte transposée)."""

    def __init__(self, em):
        self.em = em

    @property
    def pos(self):
        p = self.em.pos
        return None if p is None else (p[1], p[0], p[2])

    def travel(self, x, y):
        self.em.travel(y, x)

    def plunge(self, z):
        self.em.plunge(z)

    def feed(self, x, y, z):
        self.em.feed(y, x, z)

    def retract(self):
        self.em.retract()


def transposed(g: Grid) -> Grid:
    return Grid(g.y0, g.x0, g.ny, g.nx, g.res)


def sample(T, g: Grid, xs, ys):
    """Valeurs de la carte en des points quelconques (interpolation bilinéaire, bornée à la grille)."""
    fx = np.clip((np.asarray(xs) - g.x0) / g.res, 0.0, g.nx - 1.0)
    fy = np.clip((np.asarray(ys) - g.y0) / g.res, 0.0, g.ny - 1.0)
    i0 = np.minimum(fx.astype(np.int64), max(0, g.nx - 2))
    j0 = np.minimum(fy.astype(np.int64), max(0, g.ny - 2))
    i1, j1 = np.minimum(i0 + 1, g.nx - 1), np.minimum(j0 + 1, g.ny - 1)
    ax, ay = fx - i0, fy - j0
    return ((T[j0, i0] * (1 - ax) + T[j0, i1] * ax) * (1 - ay)
            + (T[j1, i0] * (1 - ax) + T[j1, i1] * ax) * ay)


class Turned:
    """Émetteur d'un repère tourné de `angle` degrés : (u, v) de la carte tournée → (x, y) du dessin."""

    def __init__(self, em, angle: float):
        self.em = em
        self.c, self.s = math.cos(math.radians(angle)), math.sin(math.radians(angle))

    @property
    def pos(self):
        p = self.em.pos
        return None if p is None else (p[0] * self.c + p[1] * self.s, -p[0] * self.s + p[1] * self.c, p[2])

    def travel(self, u, v):
        self.em.travel(u * self.c - v * self.s, u * self.s + v * self.c)

    def plunge(self, z):
        self.em.plunge(z)

    def feed(self, u, v, z):
        self.em.feed(u * self.c - v * self.s, u * self.s + v * self.c, z)

    def retract(self):
        self.em.retract()


def turned_map(T, g: Grid, mask, angle: float):
    """(T, grille, masque) relus dans le repère tourné ; hors de la carte d'origine : pas de passe."""
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    x = np.array([g.x0, g.x0 + (g.nx - 1) * g.res])
    y = np.array([g.y0, g.y0 + (g.ny - 1) * g.res])
    X, Y = np.meshgrid(x, y)
    U, V = X * c + Y * s, -X * s + Y * c
    nu = int(math.ceil((float(U.max()) - float(U.min())) / g.res)) + 1
    nv = int(math.ceil((float(V.max()) - float(V.min())) / g.res)) + 1
    if nu * nv > MAX_POINTS:
        raise TooBig(f'carte de {nu} × {nv} points, trop grande — augmenter le pas')
    gt = Grid(float(U.min()), float(V.min()), nu, nv, g.res)
    UU, VV = np.meshgrid(gt.xs, gt.ys)
    XX, YY = UU * c - VV * s, UU * s + VV * c
    inside = ((XX >= g.x0 - 1e-9) & (XX <= g.x0 + (g.nx - 1) * g.res + 1e-9)
              & (YY >= g.y0 - 1e-9) & (YY <= g.y0 + (g.ny - 1) * g.res + 1e-9))
    out = sample(T, g, XX, YY)
    if mask is not None:
        i = np.clip(np.round((XX - g.x0) / g.res).astype(np.int64), 0, g.nx - 1)
        j = np.clip(np.round((YY - g.y0) / g.res).astype(np.int64), 0, g.ny - 1)
        inside &= mask[j, i]
    return out, gt, inside


def spiral_path(box, step: float, res: float, outward: bool = False, climb: bool = True) -> np.ndarray:
    """Spirale rectangulaire (x, y) dans `box`, passes écartées de `step`. Le sens tient compte du côté
    où reste la matière (à droite de l'outil en avalant)."""
    x0, y0, x1, y1 = box
    step = max(res, step)
    half = min(x1 - x0, y1 - y0) / 2
    turns = max(1, int(math.ceil(half / step)))

    def ring(k: int):
        d = min(k * step, half)
        a, b, c, e = x0 + d, y0 + d, x1 - d, y1 - d
        return np.array(((a, b), (c, b), (c, e), (a, e)))

    parts = []
    for k in range(turns):
        p, q = ring(k), ring(k + 1)
        for side in range(4):
            a, b = side, (side + 1) % 4
            n = max(1, int(math.ceil(float(np.hypot(*(p[b] - p[a]))) / res)))
            t = np.arange(n) / n
            on_p = p[a] + (p[b] - p[a]) * t[:, None]
            on_q = q[a] + (q[b] - q[a]) * t[:, None]
            s = ((side + t) / 4)[:, None]
            parts.append(on_p * (1 - s) + on_q * s)
    last = ring(turns)
    n = max(1, int(math.ceil(float(np.hypot(*(last[1] - last[0]))) / res)))
    parts.append(last[0] + (last[1] - last[0]) * (np.arange(n + 1) / n)[:, None])     # le milieu : un dernier aller
    path = np.vstack(parts)
    # dans ce sens (direct), en partant du bord, la matière est à gauche : c'est de l'opposition
    if climb:
        path = (path - (x0, y0)) * (-1, 1) + (x1, y0)    # miroir : même spirale dans l'autre sens
    return path[::-1] if outward else path


def spiral(em, setup, op, tool, T, g: Grid, levels, mask=None, box=None, skip_done: bool = False) -> None:
    """Passes en spirale à chaque cote de `levels`, dans `box` (par défaut le masque, ou la carte)."""
    if box is None:
        if mask is not None and mask.any():
            rows, cols = np.flatnonzero(mask.any(axis=1)), np.flatnonzero(mask.any(axis=0))
            box = (g.x0 + cols[0] * g.res, g.y0 + rows[0] * g.res, g.x0 + cols[-1] * g.res, g.y0 + rows[-1] * g.res)
        else:
            box = (g.x0, g.y0, g.x0 + (g.nx - 1) * g.res, g.y0 + (g.ny - 1) * g.res)
    path = spiral_path(box, step_over(op, tool, g.res), g.res, bool(getattr(op, 'spiral_outward', False)),
                       bool(getattr(op, 'climb', True)))
    surface = sample(T, g, path[:, 0], path[:, 1])
    alive = np.ones(len(path), dtype=bool)
    if mask is not None:
        j = np.clip(np.round((path[:, 1] - g.y0) / g.res).astype(np.int64), 0, g.ny - 1)
        i = np.clip(np.round((path[:, 0] - g.x0) / g.res).astype(np.int64), 0, g.nx - 1)
        alive = mask[j, i]
    before = math.inf
    for zl in levels:
        progress.check()
        em.retract()
        z = np.maximum(surface, zl)
        run = alive & (surface < before - 1e-6) if skip_done else alive
        last = None
        for a, b in _runs(run):
            if b - a < 2:
                continue
            pts = _simplify([(float(x), float(y), float(h)) for (x, y), h in zip(path[a:b], z[a:b])], setup.tolerance)
            if last is not None and math.dist(last[:2], pts[0][:2]) <= 2 * g.res:
                em.feed(*pts[0])
            else:
                em.travel(pts[0][0], pts[0][1])
                em.plunge(pts[0][2])
            for p in pts[1:]:
                em.feed(*p)
            last = pts[-1]
        before = zl


def finish(em, setup, op, tool, T, g: Grid, levels, mask=None, tp=None) -> None:
    """Passes sur la carte compensée T selon les réglages de l'opération : sens, angle ou spirale ;
    par cotes de Z, l'outil suivant ou non la surface déjà usinée, ou en tranches parallèles au profil."""
    slices = int(getattr(op, 'parallel_slices', 0) or 0)
    skip = not getattr(op, 'follow_profile', True)
    if slices > 0:
        step = float(op.step_down or tool.step_down or tool.diameter / 2)
        if tp is not None:
            tp.warnings.append(f'tranches parallèles : {slices} × {step:g} mm, soit {slices * step:g} mm usinés')
        for k in range(slices - 1, -1, -1):
            _finish_levels(em, setup, op, tool, T + k * step, g, [-1e9], mask, False)
        return
    _finish_levels(em, setup, op, tool, T, g, levels, mask, skip)


def _finish_levels(em, setup, op, tool, T, g: Grid, levels, mask, skip: bool) -> None:
    mode = getattr(op, 'scan_mode', 'passes') or 'passes'
    if mode == 'spirale':
        spiral(em, setup, op, tool, T, g, levels, mask, skip_done=skip)
        return
    if mode == 'angle':
        angle = float(getattr(op, 'raster_angle', 0.0) or 0.0)
        Tt, gt, mt = turned_map(T, g, mask, angle)
        raster(Turned(em, angle), setup, op, tool, Tt, gt, levels, mt, 'x', skip_done=skip)
        turn = float(getattr(op, 'raster_turn', 0.0) or 0.0)
        if turn and levels:                              # la dernière cote reprise en travers
            Tt, gt, mt = turned_map(T, g, mask, angle + turn)
            raster(Turned(em, angle + turn), setup, op, tool, Tt, gt, levels[-1:], mt, 'x')
        return
    raster(em, setup, op, tool, T, g, levels, mask, getattr(op, 'raster_dir', 'x') or 'x', skip_done=skip)


def raster(em, setup, op, tool, T, g: Grid, levels, mask=None, direction: str = 'x', nearest: bool = False,
           min_run: int = 2, skip_done: bool = False) -> None:
    """Balayage en aller-retour de la carte compensée T (cotes de pointe)
    à chaque cote de `levels`, limité au masque : hors zone l'outil remonte,
    une liaison courte suit la surface. `direction` : 'x', 'y' ou 'xy'
    (selon X, puis la dernière cote reprise selon Y). `nearest` : segments
    épars (reprise) enchaînés au plus proche plutôt que ligne après ligne.
    `min_run` : segments plus courts (en points) laissés de côté — 1 : un
    point seul est plongé. `skip_done` : l'outil ne repasse pas où la surface
    est déjà au-dessus de la cote d'avant : il remonte et saute ces zones."""
    if direction == 'y':
        _raster_rows(SwapXY(em), setup, op, tool, T.T, transposed(g), levels,
                     None if mask is None else mask.T, nearest, min_run, skip_done)
        return
    _raster_rows(em, setup, op, tool, T, g, levels, mask, nearest, min_run, skip_done)
    if direction == 'xy' and levels:
        _raster_rows(SwapXY(em), setup, op, tool, T.T, transposed(g), levels[-1:],
                     None if mask is None else mask.T, nearest, min_run)


def step_over(op, tool, res: float) -> float:
    so = float(getattr(op, 'stepover_mm', 0.0) or 0.0) or (tool.stepover or 0.2) * tool.diameter
    return max(res, so)


def _raster_rows(em, setup, op, tool, T, g: Grid, levels, mask, nearest: bool = False, min_run: int = 2,
                 skip_done: bool = False) -> None:
    ny, nx = T.shape
    so = step_over(op, tool, g.res)
    rows = np.arange(0, ny, max(1, int(round(so / g.res))))
    if rows[-1] != ny - 1:
        rows = np.append(rows, ny - 1)
    xs = g.xs
    link_max = 1.5 * so + g.res
    last = None

    def emit(pts, zl):
        nonlocal last
        if last is not None and math.dist(last[:2], pts[0][:2]) <= link_max:
            for p in follow(T, g, last, pts[0], zl):
                em.feed(*p)
        else:
            em.travel(pts[0][0], pts[0][1])
            em.plunge(pts[0][2])
        for p in pts[1:]:
            em.feed(*p)
        last = pts[-1]

    before = math.inf
    for zl in levels:
        em.retract()
        last = None
        forward = True
        segs = []
        for j, row in enumerate(rows):
            if j % 8 == 0:
                progress.check()
            y = float(g.y0 + row * g.res)
            zrow = np.maximum(T[row], zl)
            if skip_done:
                keep = T[row] < before - 1e-6
                runs = _runs(keep & mask[row] if mask is not None else keep)
            else:
                runs = _runs(mask[row]) if mask is not None else [(0, nx)]
            if not forward:
                runs = runs[::-1]
            for a, b in runs:
                if b - a < min_run:
                    continue
                idx = range(a, b) if forward else range(b - 1, a - 1, -1)
                pts = _simplify([(float(xs[i]), y, float(zrow[i])) for i in idx], setup.tolerance)
                if nearest:
                    segs.append(pts)
                else:
                    emit(pts, zl)
            forward = not forward
        before = zl
        if segs:                                         # segments épars (reprise) : enchaînés au plus proche
            S = np.array([s[0][:2] for s in segs])
            E = np.array([s[-1][:2] for s in segs])
            left = np.ones(len(segs), dtype=bool)
            here = S[0]
            for _n in range(len(segs)):
                ds = np.where(left, np.hypot(S[:, 0] - here[0], S[:, 1] - here[1]), np.inf)
                de = np.where(left, np.hypot(E[:, 0] - here[0], E[:, 1] - here[1]), np.inf)
                i, k = int(ds.argmin()), int(de.argmin())
                rev = de[k] < ds[i]
                left[k if rev else i] = False
                emit(segs[k][::-1] if rev else segs[i], zl)
                here = np.array(last[:2])


class ReliefPiece:
    """Des reliefs TypeArt vus comme une pièce : leurs rectangles sont la zone usinée."""
    notes = ()
    triangles = ()

    def __init__(self, footprint):
        self.footprint = footprint


def relief_images(doc, op) -> list:
    """Les reliefs que l'opération usine comme une pièce : ceux qu'elle désigne (objets choisis) ;
    ceux de ses outils s'il n'y a pas d'autre pièce. Son propre fichier 3D passe avant."""
    if getattr(op, 'model_path', '') or not hasattr(doc, 'layers'):
        return []
    from ..core.document import Image
    from . import strategies as S
    found = [it for it in S.source_items(doc, op) if isinstance(it, Image) and 'galbe' in it.extra]
    if found and (getattr(op, 'items', None) or not (model_path(doc, op) or volume_items(doc))):
        return found
    return []


def _relief_piece(images, op, tool, tp, res: float, label: str, margin_tool=None):
    """Comme `piece_heights`, depuis des reliefs : le sommet à Z = 0 (affleurant), la plaque autour à la
    même hauteur : l'outil reste dans le rectangle de chaque relief."""
    from ..core import galbe as GB
    maps = []
    for img in images:
        got = GB.decode(img)
        if got is None:
            tp.warnings.append(f'{label} : relief « {img.name} » tourné ou illisible — il doit être posé droit')
            continue
        maps.append((got, img.bbox()))
    if not maps:
        return None
    x0 = min(m[1][0] for m in maps)
    y0 = min(m[1][1] for m in maps)
    x1 = max(m[1][2] for m in maps)
    y1 = max(m[1][3] for m in maps)
    try:
        d = max(tool.diameter, float(getattr(margin_tool, 'diameter', 0.0) or 0.0))
        g = grid_for(x0, y0, x1, y1, d + max(0.0, float(op.stock or 0.0)) + 2 * res, res)
    except TooBig as ex:
        tp.warnings.append(f'{label} : {ex}')
        return None
    H = np.full((g.ny, g.nx), -np.inf)
    X, Y = np.meshgrid(g.xs, g.ys)
    for (A, ax0, ay1, ares), box in maps:
        inside = (X >= box[0]) & (X <= box[2]) & (Y >= box[1]) & (Y <= box[3])
        fx = np.clip((X[inside] - ax0) / ares - 0.5, 0.0, A.shape[1] - 1.0)
        fy = np.clip((ay1 - Y[inside]) / ares - 0.5, 0.0, A.shape[0] - 1.0)
        i0, j0 = fx.astype(np.int64), fy.astype(np.int64)
        i1, j1 = np.minimum(i0 + 1, A.shape[1] - 1), np.minimum(j0 + 1, A.shape[0] - 1)
        kx, ky = fx - i0, fy - j0
        h = (A[j0, i0] * (1 - kx) + A[j0, i1] * kx) * (1 - ky) + (A[j1, i0] * (1 - kx) + A[j1, i1] * kx) * ky
        H[inside] = np.maximum(H[inside], h)
    inside = np.isfinite(H)
    if not inside.any():
        tp.warnings.append(f'{label} : relief trop petit pour ce pas')
        return None
    top = float(H[inside].max())
    H[inside] -= top
    depth = abs(op.depth) if op.depth > 0 else -float(H[inside].min())
    H[~inside] = 0.0
    return ReliefPiece(inside), g, H, depth


def op_model(doc, op):
    """Pièce de l'opération posée comme sur la machine (prise, corps), ou
    None (absente, illisible, volume caché : `piece_heights` le dit)."""
    if relief_images(doc, op):
        return None
    path = model_path(doc, op)
    face, body = getattr(op, 'setup_face', '') or '', op_body(doc, op)
    if body is None:
        return None
    try:
        return load_model(doc, path, face, body) if path else volumes_model(doc, face, body)
    except progress.Cancelled:
        raise
    except Exception:                                      # noqa: BLE001 — fichier tiers
        return None


def levels_above(top: float, step: float) -> list[float]:
    """Paliers dans le brut au-dessus du haut de la pièce : passes égales
    de `top` jusqu'à Z 0 compris."""
    if top <= 1e-6:
        return []
    n = max(1, math.ceil(top / step - 1e-9)) if step > 0 else 1
    return [top * (1 - (k + 1) / n) for k in range(n)]


def piece_heights(doc, op, tool, tp, res: float, label: str, margin_tool=None, cover=None, model=None):
    """(modèle, grille, H : hauteurs de la pièce (haut à Z = 0, -inf autour),
    profondeur) de l'opération, ou None (avertissement dans tp) ; `cover` :
    brut (`core.stock3d.StockBox`) que la carte couvre en entier ; `model` :
    la pièce déjà lue. Des reliefs TypeArt choisis tiennent lieu de pièce."""
    from .advanced import heightmap_from_triangles
    if model is None:
        images = relief_images(doc, op)
        if images:
            return _relief_piece(images, op, tool, tp, res, label, margin_tool)
    path = model_path(doc, op)
    face, body = getattr(op, 'setup_face', '') or '', op_body(doc, op)
    if body is None and model is None:
        tp.warnings.append(f'{label} : le volume du dessin usiné seul (corps n° {int(op.body3d) + 1}) est caché ou '
                           'supprimé — le montrer, ou choisir un autre corps : rien d\'usiné')
        return None
    try:
        if model is None:
            model = load_model(doc, path, face, body) if path else volumes_model(doc, face, body)
    except progress.Cancelled:
        raise
    except Exception as ex:                                # noqa: BLE001 — fichier tiers
        tp.warnings.append(f'{label} : pièce 3D illisible ({ex})')
        return None
    if model is None:
        tp.warnings.append(f'{label} : choisir le fichier 3D de la pièce (STEP, STL, 3D XML), modéliser des '
                           'volumes dans le dessin, ou choisir un relief')
        return None
    tris = np.asarray(model.triangles, dtype=np.float64)
    if not len(tris):
        tp.warnings.append(f'{label} : aucune face maillée dans la pièce')
        return None
    lo, hi = tris.reshape(-1, 3).min(axis=0), tris.reshape(-1, 3).max(axis=0)
    box = (float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1]))
    zb = zone_bbox(op, model)
    if zb is not None:                                     # zone choisie : la carte autour d'elle seulement
        ext = max(0.0, float(getattr(op, 'extension', 0.0) or 0.0))
        box = (max(box[0], zb[0] - ext), max(box[1], zb[1] - ext), min(box[2], zb[2] + ext), min(box[3], zb[3] + ext))
        if box[2] < box[0] or box[3] < box[1]:
            tp.warnings.append(f'{label} : la zone choisie est hors de la pièce')
            return None
    elif cover is not None:                                # brut donné : la carte le couvre en entier
        box = (min(box[0], cover.x0), min(box[1], cover.y0), max(box[2], cover.x1), max(box[3], cover.y1))
    try:
        # marge : l'outil passe tout autour (son centre à un rayon du bord), et un rayon de plus où la
        # carte compensée reste juste (au-delà de la carte, la matière est supposée à Z 0)
        d = max(tool.diameter, float(getattr(margin_tool, 'diameter', 0.0) or 0.0))
        g = grid_for(*box, d + max(0.0, float(op.stock or 0.0)) + 2 * res, res)
    except TooBig as ex:
        tp.warnings.append(f'{label} : {ex}')
        return None
    depth = abs(op.depth) if op.depth > 0 else float(hi[2] - lo[2])
    H = heightmap_from_triangles(tris, g.x0, g.y0, g.nx, g.ny, g.res) - hi[2]
    for n in (model.notes or [])[:3]:
        tp.warnings.append(f'pièce 3D : {n}')
    return model, g, H, depth


# --- courbes de niveau de la carte (carrés marchants) ------------------------------------
#: segments de chaque cas (coins dedans : bas-gauche 1, bas-droite 2, haut-droite 4, haut-gauche 8) entre
#: les bords 0 (bas), 1 (droite), 2 (haut), 3 (gauche) ; 5 et 10 : selon le centre (dedans, dehors)
_CASES = {1: [(3, 0)], 2: [(0, 1)], 3: [(3, 1)], 4: [(1, 2)], 6: [(0, 2)], 7: [(3, 2)], 8: [(2, 3)],
          9: [(0, 2)], 11: [(1, 2)], 12: [(3, 1)], 13: [(0, 1)], 14: [(3, 0)]}
_SADDLE = {5: ([(0, 1), (2, 3)], [(3, 0), (1, 2)]), 10: ([(3, 0), (1, 2)], [(0, 1), (2, 3)])}


def iso_segments(F, g: Grid) -> np.ndarray:
    """Segments (m, 2, 2) de la courbe F = 0 (F ≤ 0 : dedans), bords
    interpolés ; la carte est bordée de « dehors » : les courbes se
    ferment. Deux cases voisines calculent le même point sur leur bord
    commun (mêmes valeurs, même formule) : les segments se raccordent."""
    ny, nx = F.shape
    P = np.ones((ny + 2, nx + 2))
    P[1:-1, 1:-1] = np.where(np.isfinite(F), F, 1.0)
    P[P == 0] = -1e-12                                    # pas de valeur nulle : bords jamais sur un coin
    a, b, c, d = P[:-1, :-1], P[:-1, 1:], P[1:, 1:], P[1:, :-1]
    case = (a <= 0) * 1 + (b <= 0) * 2 + (c <= 0) * 4 + (d <= 0) * 8
    J, I = np.mgrid[0:ny + 1, 0:nx + 1]
    # coins pris des indices entiers : le bord droit d'une case et le bord gauche de sa voisine
    # tombent sur les mêmes nombres
    X0, X1 = g.x0 + (I - 1) * g.res, g.x0 + I * g.res
    Y0, Y1 = g.y0 + (J - 1) * g.res, g.y0 + J * g.res
    with np.errstate(divide='ignore', invalid='ignore'):
        edges = (
            (X0 + g.res * (a / (a - b)), Y0),                     # 0 : bas (a → b)
            (X1, Y0 + g.res * (b / (b - c))),                     # 1 : droite (b → c)
            (X0 + g.res * (d / (d - c)), Y1),                     # 2 : haut (d → c)
            (X0, Y0 + g.res * (a / (a - d))),                     # 3 : gauche (a → d)
        )
    segs = []

    def add(sel, pairs):
        for e1, e2 in pairs:
            p = np.stack([edges[e1][0][sel], edges[e1][1][sel]], axis=1)
            q = np.stack([edges[e2][0][sel], edges[e2][1][sel]], axis=1)
            segs.append(np.stack([p, q], axis=1))
    for k, pairs in _CASES.items():
        sel = case == k
        if sel.any():
            add(sel, pairs)
    centre = (a + b + c + d) / 4
    for k, (inside, outside) in _SADDLE.items():
        sel = case == k
        if sel.any():
            add(sel & (centre <= 0), inside)
            add(sel & (centre > 0), outside)
    return np.concatenate(segs) if segs else np.zeros((0, 2, 2))


def iso_region(F, g: Grid, tol: float = 0.0):
    """Région shapely {F ≤ 0} : courbes de niveau fermées, remplies en
    pair-impair (un îlot dans un trou dans une forme…). `tol` : tracé
    simplifié à moins de `tol`."""
    import shapely
    segs = iso_segments(F, g)
    if not len(segs):
        return shapely.Polygon()
    lines = shapely.line_merge(shapely.multilinestrings(segs))
    rings = [ln for ln in getattr(lines, 'geoms', [lines]) if ln.is_ring and len(ln.coords) >= 4]
    polys = [shapely.Polygon(r.coords) for r in rings]
    polys = [p if p.is_valid else shapely.make_valid(p) for p in polys]
    polys = [p for p in polys if not p.is_empty and p.area > 1e-12]
    if not polys:
        return shapely.Polygon()
    polys.sort(key=lambda p: -p.area)
    tree = shapely.STRtree(polys)
    pts = shapely.point_on_surface(polys)
    src, dst = tree.query(pts, predicate='within')
    depth = np.zeros(len(polys), dtype=int)
    for i, j in zip(src.tolist(), dst.tolist()):
        if i != j and polys[j].area > polys[i].area:
            depth[i] += 1
    out = shapely.Polygon()
    for dpt in sorted(set(depth.tolist())):
        layer = shapely.union_all([polys[i] for i in np.flatnonzero(depth == dpt)])
        out = out.union(layer) if dpt % 2 == 0 else out.difference(layer)
    if tol > 0:
        out = out.simplify(tol)
    return out


def flat_heights(H, res: float, min_area: float, min_width: float = 0.0) -> list[float]:
    """Hauteurs des fonds plats de la carte (au µm près) d'au moins
    `min_area` mm² et assez larges : la région à cette hauteur garde des
    points une fois rétrécie de `min_width` / 2 (un plan incliné aligné sur
    la grille a des colonnes de même hauteur, sans largeur). De la plus
    haute à la plus basse."""
    v = H[np.isfinite(H)]
    if not len(v):
        return []
    R = np.where(np.isfinite(H), np.round(H, 3), np.nan)
    q, counts = np.unique(np.round(v, 3), return_counts=True)
    k = max(1, int(round(min_width / 2 / res))) if min_width > 0 else 0
    keep = []
    for h in q[counts * res * res >= min_area].tolist():
        if k:
            m = R == h
            rows, cols = np.flatnonzero(m.any(axis=1)), np.flatnonzero(m.any(axis=0))
            if len(rows) <= 2 * k or len(cols) <= 2 * k:
                continue
            sub = m[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
            for _s in range(k):                       # rétrécie d'un point par pas (croix)
                e = sub.copy()
                e[1:] &= sub[:-1]
                e[:-1] &= sub[1:]
                e[:, 1:] &= sub[:, :-1]
                e[:, :-1] &= sub[:, 1:]
                e[0, :] = e[-1, :] = False
                e[:, 0] = e[:, -1] = False
                sub = e
                if not sub.any():
                    break
            if not sub.any():
                continue
        keep.append(h)
    return sorted(keep, reverse=True)


def rough_levels(op, tool, depth: float, H=None, res: float = 0.1) -> list[float]:
    """Paliers d'ébauche : passes égales jusqu'à −depth, plus un palier
    juste au-dessus de chaque fond plat (surépaisseur et demi-pas de la
    carte laissés) — sinon un
    fond entre deux paliers garderait jusqu'à une passe de matière."""
    from . import strategies as S
    zs = S.levels(depth, op.step_down or tool.step_down)
    if H is not None:
        stock = max(0.0, float(op.stock or 0.0))
        r = tool.diameter / 2
        for h in flat_heights(H, res, max(res * res * 4, math.pi * r * r), 2 * r):   # où l'outil se pose en entier
            z = h + stock + res / 2                       # comme la carte de l'ébauche (demi-pas)
            if -depth - 1e-9 <= z < -1e-6:
                zs.append(z)
    out = []
    for z in sorted(zs, reverse=True):
        if not out or out[-1] - z > 0.01:
            out.append(z)
        else:
            out[-1] = min(out[-1], z)
    return out


def zlevel_rough(em, setup, op, tool, tp, T, g: Grid, levels, mask=None, here=(0.0, 0.0), start: float = 0.0) -> int:
    """Ébauche par paliers : à chaque cote z, la région où la pointe de
    l'outil peut descendre à z sans entamer la pièce (surépaisseur
    comprise, carte T) — dans la zone — vidée en anneaux concentriques
    depuis son bord ; `start` : haut de la matière (brut au-dessus de la
    pièce), d'où part la rampe du premier palier. Rend le nombre de paliers
    usinés."""
    from . import strategies as S
    tol = setup.tolerance
    width = tool.diameter if tool.kind not in ('conique',) else max(tool.tip, 0.1)
    step = max(0.05, float(getattr(op, 'stepover_mm', 0.0) or 0.0) or (tool.stepover or 0.4) * width)
    region_right = not op.climb
    ramp = S.ramp_angle_of(op) if op.ramp else None
    done = 0
    for zi, z in enumerate(levels):
        progress.step(zi, len(levels), 'Ébauche 3D : palier {0} sur {1}')
        # dedans / dehors seulement : la carte compensée saute d'un coup au pied d'une paroi (fraise
        # plate), une interpolation y placerait le bord trop près ; bord à mi-chemin, puis retiré d'un
        # demi-pas : l'outil ne va pas plus loin que le dernier point permis
        ok = T <= z + 1e-6
        if mask is not None:
            ok &= mask
        rows, cols = np.flatnonzero(ok.any(axis=1)), np.flatnonzero(ok.any(axis=0))
        if not len(rows):
            continue
        j0, j1, i0, i1 = rows[0], rows[-1] + 1, cols[0], cols[-1] + 1     # la carte rognée à la région
        sub = Grid(g.x0 + i0 * g.res, g.y0 + j0 * g.res, int(i1 - i0), int(j1 - j0), g.res)
        allowed = iso_region(np.where(ok[j0:j1, i0:i1], -1.0, 1.0), sub)
        if allowed.is_empty:
            continue
        allowed = allowed.buffer(-g.res / 2, quad_segs=2).simplify(tol / 2)
        if allowed.is_empty:
            continue
        shells = S.concentric(allowed, step, tol)
        if not shells:
            continue
        groups = S.order_groups(S.shape_groups(allowed, shells, region_right), em.pos or here)
        inside = S.within_test(allowed.buffer(1e-6))
        z_prev = levels[zi - 1] if zi else start
        for order in groups:                               # rampe depuis le palier d'avant, pas depuis le dessus
            S.mill_rings(em, order, [z_prev, z], allowed, ramp, inside=inside, only={1})
        done += 1
    return done


# --- pentes, reprise, niveaux constants --------------------------------------------------
def slopes(T, res: float):
    """Pente (°, 0 à plat, 90 à la verticale) de la surface que suit
    l'outil, en chaque point (gradient de la carte compensée)."""
    gy, gx = np.gradient(np.where(np.isfinite(T), T, np.nan), res)
    s = np.degrees(np.arctan(np.hypot(gx, gy)))
    return np.where(np.isfinite(s), s, 0.0)


def slope_mask(T, res: float, lo: float = 0.0, hi: float = 90.0):
    """Points où la pente est entre `lo` et `hi` degrés (None : tous)."""
    lo, hi = max(0.0, float(lo or 0.0)), min(90.0, float(hi if hi is not None else 90.0) or 90.0)
    if lo <= 0.0 and hi >= 90.0:
        return None
    s = slopes(T, res)
    return (s >= lo - 1e-9) & (s <= hi + 1e-9)


def combine(*masks):
    """Intersection des masques (None : sans limite)."""
    out = None
    for m in masks:
        if m is None:
            continue
        out = m.copy() if out is None else (out & m)
    return out


def rest_raster(em, setup, op, tool, T, Tprev, g: Grid, step: float, mask=None, min_rest: float = 0.02,
                direction: str = 'x', Eprev=None, Ecur=None) -> int:
    """Reprise : là où l'outil d'avant a laissé plus de `min_rest` mm de
    matière que l'outil courant (cotes de pointe T) peut enlever, balayage
    par paliers de `step` depuis le haut de ce reste. `Eprev`, `Ecur` : les
    surfaces laissées par les deux outils (advanced.envelope) — chaque palier
    limité aux positions de l'outil sous lesquelles il reste de la matière
    au-dessus de lui, puis le tour des parois de la zone ; sans elles, les cotes de pointe Tprev et T (le reste
    déborde alors le long des parois). Un point n'est repris à un palier
    que si la pointe y descend plus bas qu'au palier d'avant (sous sa cote
    de surface, chaque palier repassait le même trajet). Rend le nombre de
    paliers."""
    if Eprev is not None and Ecur is not None:
        return _rest_envelopes(em, setup, op, tool, T, g, step, mask, min_rest, direction, Eprev, Ecur)
    rest = (Tprev - T) > min_rest
    if mask is not None:
        rest &= mask
    if not rest.any():
        return 0
    rest = dilate(rest, 1)
    top, low = float(Tprev[rest].max()), float(T[rest].min())
    n = max(1, int(math.ceil((top - low) / max(step, 1e-3) - 1e-9)))
    done = 0
    reached = np.full(T.shape, np.inf)                   # pointe la plus basse déjà passée en chaque point
    for k in range(1, n + 1):
        zl = top - (top - low) * k / n
        tip = np.maximum(T, zl)
        m = rest & (Tprev > tip + min_rest / 2) & (tip < reached - 1e-6)
        if m.any():
            raster(em, setup, op, tool, T, g, [zl], m, direction)
            reached[m] = tip[m]
            done += 1
    return done


def label(mask) -> tuple[np.ndarray, int]:
    """Zones d'un seul tenant d'un masque (voisins en croix) : (numéro de
    zone de chaque point, 0 hors du masque ; nombre de zones), numérotées
    dans l'ordre de leur premier point. Réunion par segments de ligne (bien
    moins nombreux que les points)."""
    m = np.asarray(mask, dtype=bool)
    ny, nx = m.shape
    lab = np.zeros(m.shape, dtype=np.int64)
    if not m.any():
        return lab, 0
    pad = np.zeros((ny, nx + 2), dtype=np.int8)
    pad[:, 1:-1] = m
    d = np.diff(pad, axis=1)
    rows, c0 = np.nonzero(d == 1)                        # débuts des segments (ligne après ligne)
    _r, c1 = np.nonzero(d == -1)                         # fins (exclues), dans le même ordre
    parent = np.arange(len(rows))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    first = np.searchsorted(rows, np.arange(ny + 1))     # premier segment de chaque ligne
    for y in range(1, ny):
        i, i1, j, j1 = first[y - 1], first[y], first[y], first[y + 1]
        while i < i1 and j < j1:                         # segments des deux lignes qui se chevauchent
            if c0[i] < c1[j] and c0[j] < c1[i]:
                a, b = find(i), find(j)
                if a != b:
                    parent[max(a, b)] = min(a, b)
            if c1[i] <= c1[j]:
                i += 1
            else:
                j += 1
    roots = np.array([find(k) for k in range(len(rows))])
    _u, comp = np.unique(roots, return_inverse=True)
    for k in range(len(rows)):
        lab[rows[k], c0[k]:c1[k]] = comp[k] + 1
    return lab, int(comp.max()) + 1


def _rest_contours(em, setup, op, tool, T, g: Grid, zl: float, m) -> int:
    """Le tour des parois d'une zone de reprise à la cote zl (les lignes de
    balayage, posées sur la grille, ne passent pas au ras des parois qui leur
    sont parallèles) — calculé sur la zone seule."""
    ys, xs = np.nonzero(m)
    if not len(ys):
        return 0
    k = int(math.ceil(tool.diameter / 2 / g.res)) + 3
    r0, r1 = max(0, ys.min() - k), min(T.shape[0], ys.max() + k + 1)
    c0, c1 = max(0, xs.min() - k), min(T.shape[1], xs.max() + k + 1)
    gc = Grid(g.x0 + c0 * g.res, g.y0 + r0 * g.res, c1 - c0, r1 - r0, g.res)
    Tc = T[r0:r1, c0:c1]
    z = max(zl, float(Tc[m[r0:r1, c0:c1]].min()) + 0.005)   # au fond : un rien au-dessus (sinon pas de courbe)
    allow = dilate(m[r0:r1, c0:c1], 3)                 # la courbe longe le bord de la zone : pas hachée par lui
    return waterline(em, setup, op, tool, Tc, gc, [z], allow)


def _rest_envelopes(em, setup, op, tool, T, g, step, mask, min_rest, direction, Eprev, Ecur) -> int:
    # Les déplacements rapides restent ceux de toujours (dégagement, hauteur d'approche, plongée) : la matière
    # laissée par l'outil d'avant n'est connue qu'à peu près (marches d'une ébauche par paliers, autre
    # surépaisseur, autre zone, autre profondeur) — descendre ou sauter « au ras » y entrerait.
    import dataclasses
    from .advanced import compensate
    rest = (Eprev - Ecur) > min_rest                     # matière que l'outil d'avant a laissée et que celui-ci prend
    if mask is not None:
        rest &= mask
    if not rest.any():
        return 0
    flat = dataclasses.replace(tool, kind='fraise')
    above = compensate(np.where(rest, Eprev, -np.inf), g.res, flat, pad=-np.inf)   # plus haut reste sous l'outil
    centers = np.isfinite(above)
    if mask is not None:
        centers &= mask                                  # le centre de l'outil reste dans la zone choisie
    lab, nz = label(centers)
    if not nz:
        return 0
    idx = np.flatnonzero(lab)
    zid = lab.ravel()[idx]
    rows, cols = idx // lab.shape[1], idx % lab.shape[1]
    big = np.iinfo(np.int64).max
    r0, c0 = np.full(nz + 1, big), np.full(nz + 1, big)
    r1, c1 = np.full(nz + 1, -1), np.full(nz + 1, -1)
    np.minimum.at(r0, zid, rows)
    np.minimum.at(c0, zid, cols)
    np.maximum.at(r1, zid, rows)
    np.maximum.at(c1, zid, cols)
    cnt = np.maximum(np.bincount(zid, minlength=nz + 1), 1)
    cen = np.column_stack([np.bincount(zid, cols, nz + 1) / cnt, np.bincount(zid, rows, nz + 1) / cnt])
    order, left, cur = [], set(range(1, nz + 1)), np.array([0.0, 0.0])
    while left:                                          # zones d'un seul tenant, de proche en proche
        z = min(left, key=lambda i: float(np.hypot(*(cen[i] - cur))))
        order.append(z)
        left.discard(z)
        cur = cen[z]
    k = int(math.ceil(tool.diameter / 2 / g.res)) + 2
    done = 0
    reached = np.full(T.shape, np.inf)                   # pointe la plus basse déjà passée en chaque point
    for zone in order:                                   # toute la profondeur d'une zone, puis la suivante
        rs = slice(max(0, r0[zone] - k), min(T.shape[0], r1[zone] + k + 1))
        cs = slice(max(0, c0[zone] - k), min(T.shape[1], c1[zone] + k + 1))
        gc = Grid(g.x0 + cs.start * g.res, g.y0 + rs.start * g.res, cs.stop - cs.start, rs.stop - rs.start, g.res)
        here, Tc, ac, rc = lab[rs, cs] == zone, T[rs, cs], above[rs, cs], reached[rs, cs]   # rc : vue, mise à jour
        top, low = float(ac[here].max()), float(Tc[here].min())
        n = max(1, int(math.ceil((top - low) / max(step, 1e-3) - 1e-9)))
        for lv in range(1, n + 1):
            zl = top - (top - low) * lv / n
            tip = np.maximum(Tc, zl)
            m = here & (ac > tip + min_rest / 2) & (tip < rc - 1e-6)
            if m.any():
                raster(em, setup, op, tool, Tc, gc, [zl], m, direction, nearest=True, min_run=1)
                _rest_contours(em, setup, op, tool, Tc, gc, zl, m)
                rc[m] = tip[m]
                done += 1
    return done


def waterline(em, setup, op, tool, T, g: Grid, levels, mask=None) -> int:
    """Niveaux constants : à chaque cote z, le centre de l'outil suit la
    courbe de niveau T = z (l'outil touche la pièce sur tout son tour) —
    finition des parois raides ; limitée au masque (zone, pentes). Rend le
    nombre de courbes usinées."""
    import shapely
    from . import strategies as S
    tol = setup.tolerance
    allow = None
    if mask is not None:
        allow = iso_region(np.where(dilate(mask, 1), -1.0, 1.0), g)
    n = 0
    for zi, z in enumerate(levels):
        progress.step(zi, len(levels), 'Niveaux constants : cote {0} sur {1}')
        reg = iso_region(T - z, g, tol / 4)
        if reg.is_empty:
            continue
        lines = shapely.boundary(reg)
        if allow is not None:
            lines = lines.intersection(allow)
        chains = []
        for ln in getattr(lines, 'geoms', [lines]):
            if ln.is_empty or ln.geom_type not in ('LineString', 'LinearRing') or ln.length < 2 * g.res:
                continue
            pts = [(float(x), float(y)) for x, y in ln.coords]
            closed = math.dist(pts[0], pts[-1]) < 1e-9
            chains.append((pts, closed))
        # au-delà de la carte la matière est supposée à Z 0 : l'outil y est tenu à un rayon du bord —
        # une courbe tout entière dans cette bande longe le bord de la carte, pas une paroi
        e = tool.diameter / 2
        bx = g.x0 + e, g.y0 + e, g.x0 + (g.nx - 1) * g.res - e, g.y0 + (g.ny - 1) * g.res - e
        for pts, closed in S.order_chains(chains, em.pos or (0.0, 0.0)):
            if all(not (bx[0] < x < bx[2] and bx[1] < y < bx[3]) for x, y in pts):
                continue
            S.cut_chain(em, pts, closed, [z])
            n += 1
    return n


def scallop_step(radius: float, crest: float) -> float:
    """Pas (mm) entre deux passes d'une boule de rayon `radius` qui laisse
    une crête de `crest` mm sur une surface perpendiculaire au pas."""
    h = max(1e-6, min(crest, radius))
    return 2 * math.sqrt(max(0.0, 2 * radius * h - h * h))
