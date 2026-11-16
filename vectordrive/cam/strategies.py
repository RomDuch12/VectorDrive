"""Calcul des parcours 2D et 2,5D : gravure sur le trait, détourage,
poche, perçage, marquage laser.

Les régions (contours fermés) passent par shapely : décalages au rayon de
l'outil, intérieur / extérieur, liaisons des poches. Les courbes sont
aplaties à la tolérance du réglage FAO.
"""
from __future__ import annotations

import math
import re

from ..core.document import Document, Group, Shape, Text
from ..core.geom import Path
from .model import CamSetup, CamTool, Move, Operation, Toolpath
from ..core import progress
from ..core import surface2d as _S2

#: angle de la rampe d'entrée (°)
RAMP_ANGLE = 5.0


# --- géométrie source ------------------------------------------------------------

def _leaves(items):
    for it in items:
        if not it.visible:
            continue
        if isinstance(it, Group):
            yield from _leaves(it.children)
        else:
            yield it


#: objets retenus pour le calcul en cours (mode sélection, `compute_all(only=…)`) ; None : tous.
#: Variable de contexte : un calcul dans un fil de fond ne restreint pas l'interface.
import contextvars as _cv
_ONLY = _cv.ContextVar('vectordrive_cam_only', default=None)
#: tri des contours manuel (TypeEdit) : les chaînes gardent l'ordre du dessin
_DRAWING_ORDER = _cv.ContextVar('vectordrive_cam_drawing_order', default=False)
_RAMP_LIMIT = _cv.ContextVar('vectordrive_cam_ramp_limit', default=0.0)    # distance maxi de la rampe (TE, page 653)
#: parcours des opérations d'avant, pour une opération « liée au parcours précédent » (sinon None)
_PREVIOUS = _cv.ContextVar('vectordrive_cam_previous', default=None)


def previous_toolpaths() -> list:
    """Parcours déjà calculés des opérations d'avant (opération liée au
    parcours précédent, pendant `compute_all`) ; [] sinon."""
    return _PREVIOUS.get() or []


DRAWN_PATH = 'parcours_dessin'             # trait de « Parcours en dessin » : usiné seulement choisi


def is_drawn_path(it) -> bool:
    """Trait posé par « Parcours en dessin » (trajectoire reprise) ?"""
    return isinstance(getattr(it, 'extra', None), dict) and bool(it.extra.get(DRAWN_PATH))


def source_items(doc: Document, op: Operation, only=None) -> list:
    """Objets du dessin usinés par l'opération, calques visibles seulement :
    les objets choisis (`op.items`, un groupe vaut pour son contenu) s'il y
    en a, sinon ceux des outils (couleurs) choisis. Mode sélection (`only`,
    ou le calcul en cours) : seulement parmi ces objets (un groupe
    sélectionné vaut pour son contenu), chaque opération gardant ses
    couleurs."""
    ids = set(op.items or [])
    wanted = set(op.sources or [])
    only = set(only) if only is not None else _ONLY.get()
    out = []

    def walk(it, in_items: bool, in_only: bool) -> None:
        if not it.visible or _S2.is_outline(it):         # contour d'une surface posée : un guide
            return
        in_items = in_items or it.id in ids
        in_only = in_only or (only is not None and it.id in only)
        if isinstance(it, Group):
            for ch in it.children:
                walk(ch, in_items, in_only)
            return
        if only is not None and not in_only:
            return
        if ids:
            if in_items:
                out.append(it)
        elif (not wanted or it.tool in wanted) and (only is not None or not is_drawn_path(it)):
            out.append(it)                               # trajectoire reprise : choisie seulement

    keep = _S2.layer_filter(doc, op)                    # surfaces posées : chacune dans sa prise
    for L in doc.layers:
        if not L.visible or (keep is not None and not keep(L)) or (L.extra or {}).get('plaque_reprise'):
            continue                                     # plaque de reprise posée (`cam.fixture`) : un repère
        for it in L.items:
            walk(it, False, False)
    return out


def item_geometry(it) -> Path | None:
    if isinstance(it, Shape):
        return it.path
    if isinstance(it, Text):
        return it.outline
    return None


def polylines(paths: list[Path], tol: float) -> list[tuple[list, bool]]:
    """(points, fermé) de chaque contour."""
    out = []
    for p in paths:
        for c in p.contours:
            pts = c.flatten(tol)
            if len(pts) >= 2:
                closed = c.closed and math.dist(pts[0], pts[-1]) < 1e-9
                out.append((pts, closed))
    return out


def _quad_segs(r: float, tol: float) -> int:
    """Segments par quart de cercle pour une erreur de corde < tol."""
    if r <= tol:
        return 2
    return max(2, math.ceil((math.pi / 2) / math.acos(1 - tol / r)))


#: au-delà de ce nombre de parties, retraits et simplifications partie par partie
MANY_PARTS = 32


def _polys(geoms):
    """Polygones non vides d'un tableau de géométries shapely, en une
    région (Polygon, MultiPolygon, ou polygone vide)."""
    import shapely
    from shapely.geometry import Polygon
    parts = shapely.get_parts(geoms)
    parts = parts[(shapely.get_type_id(parts) == 3) & ~shapely.is_empty(parts)]
    if len(parts) == 0:
        return Polygon()
    return parts[0] if len(parts) == 1 else shapely.multipolygons(parts)


def _wall_tree(source, size: int = 32):
    """Arbre des parois de `source`, par tronçons de `size` côtés : presque rien à construire, et une distance n'y parcourt que quelques tronçons
    (avec un anneau d'un seul tenant, tous ses côtés à chaque point : plusieurs secondes par retrait sur un grand dessin). None : pas de paroi."""
    import numpy as np
    import shapely
    walls = shapely.get_parts(source)
    walls = walls[(shapely.get_type_id(walls) == 3) & ~shapely.is_empty(walls)]
    if not len(walls):
        return None
    coords, idx = shapely.get_coordinates(shapely.get_rings(walls), return_index=True)
    n = len(coords)
    same = idx[1:] == idx[:-1]                            # k et k + 1 sont sur le même anneau
    first = np.r_[True, ~same]
    at = np.arange(n)
    pos = at - np.maximum.accumulate(np.where(first, at, 0))
    cut = (pos % size == 0) & ~first & np.r_[same, False]  # ce sommet finit un tronçon et commence le suivant : il compte deux fois
    rep = 1 + cut.astype(int)
    ids = np.repeat(np.cumsum(first | cut) - 1, rep)
    ids[(np.cumsum(rep) - rep)[cut]] -= 1
    return shapely.STRtree(shapely.linestrings(np.repeat(coords, rep, axis=0), indices=ids))


def drop_splinters(res, source, dist: float, quad_segs: int = 8):
    """`res` : le décalage `source.buffer(dist)` (dist < 0 : vers l'intérieur). Retire ce que GEOS y a laissé à tort : une partie d'un retrait, ou un trou d'un
    agrandissement, trop près de la paroi. C'est l'anneau d'une forme qui aurait dû disparaître, retourné : GEOS ne le reconnaît qu'à moins de 10 sommets.
    Relevé sur 39 dessins réels, jusqu'à 26 mm de tour, et jusqu'à 4,9 mm plus près de la paroi que demandé : un parcours y descendait à pleine profondeur,
    dans la paroi. Tout point d'un vrai décalage est à la distance demandée, à la flèche des arcs et à la simplification de GEOS (1 %) près : un sommet
    suffit pour soupçonner, et l'anneau n'est retiré que si tous ses sommets sont trop près."""
    import numpy as np
    import shapely
    from shapely.geometry import Polygon
    d = abs(dist)
    if d <= 1e-6 or res.is_empty:
        return res
    parts = shapely.get_parts(res)
    parts = parts[shapely.get_type_id(parts) == 3]
    if not len(parts):
        return res
    if dist < 0:
        rings = shapely.get_exterior_ring(parts)
        owner = np.arange(len(parts))
    else:
        rings, owner = shapely.get_rings(parts, return_index=True)
        hole = np.r_[False, owner[1:] == owner[:-1]]      # l'extérieur d'abord, puis les trous de la même partie
        rings, owner = rings[hole], owner[hole]
    if not len(rings):
        return res
    tree = _wall_tree(source)
    if tree is None:
        return res
    limit = d - (1.5 * d * (1.0 - math.cos(math.pi / (4 * max(1, quad_segs)))) + 0.015 * d + 1e-3)
    near = np.full(len(rings), np.inf)
    at, dd = tree.query_nearest(shapely.get_point(rings, 0), return_distance=True, all_matches=False)
    near[at[0]] = dd
    bad = np.nonzero(near < limit)[0]
    if not len(bad):
        return res
    coords, idx = shapely.get_coordinates(rings[bad], return_index=True)
    at, dd = tree.query_nearest(shapely.points(coords), return_distance=True, all_matches=False)
    best = np.zeros(len(bad))
    np.maximum.at(best, idx[at[0]], dd)
    bad = bad[best < limit]
    if not len(bad):
        return res
    if dist < 0:
        keep = np.ones(len(parts), dtype=bool)
        keep[owner[bad]] = False
        return _polys(parts[keep])
    gone = {int(i) for i in bad}
    out = list(parts)
    for k in {int(owner[i]) for i in bad}:
        out[k] = Polygon(parts[k].exterior, [rings[int(j)] for j in np.nonzero(owner == k)[0] if int(j) not in gone])
    return _polys(np.array(out, dtype=object))


def buffer_checked(geom, d: float, quad_segs: int = 8, **kw):
    """`geom.buffer(d)` (d < 0 : vers l'intérieur) sans les anneaux faux que GEOS y laisse (`drop_splinters`) : pour tout décalage dont les
    anneaux deviennent un parcours. Relevé : la finition d'un détourage, le chanfrein d'arête et la découpe 3D gardaient l'anneau retourné
    d'une forme trop petite pour l'outil, et l'usinaient à 0,4 mm dans la paroi."""
    return drop_splinters(geom.buffer(d, quad_segs=quad_segs, **kw), geom, d, quad_segs)


def erode(geom, d: float, quad_segs: int = 8):
    """Retrait de `d` (≥ 0) d'une région : `geom.buffer(-d)`. Sur une région
    de nombreuses parties, calculé partie par partie (shapely vectorisé) :
    les parties d'une région valide sont disjointes et un disque ne peut
    tenir à cheval sur deux, le retrait de l'ensemble est donc la réunion
    des retraits — même région, sans un seul gros calcul sur tout le dessin."""
    if d < 0:
        return drop_splinters(geom.buffer(-d, quad_segs=quad_segs), geom, -d, quad_segs)
    import shapely
    parts = shapely.get_parts(geom)
    parts = parts[(shapely.get_type_id(parts) == 3) & ~shapely.is_empty(parts)]
    heavy = d >= HOLES_SPLIT_D and bool((shapely.get_num_interior_rings(parts) >= HOLES_SPLIT).any())
    if not len(parts) or (len(parts) <= MANY_PARTS and not heavy):
        return drop_splinters(geom.buffer(-d, quad_segs=quad_segs), geom, -d, quad_segs)             # petite région : le retrait direct, tel quel
    return drop_splinters(_erode_parts(parts, d, quad_segs), geom, -d, quad_segs)


#: une pièce d'au moins autant de trous est retirée par décomposition au-delà de HOLES_SPLIT_D mm
HOLES_SPLIT = 16
HOLES_SPLIT_D = 1.0


def _erode_one(poly, d: float, qs: int):
    """Retrait d'une pièce. Avec de nombreux trous (fond d'une plaque autour de
    centaines de lettres) et un grand retrait : contour extérieur rétréci,
    moins les trous élargis réunis — même pièce (un disque tient dans la pièce
    s'il tient dans le contour sans toucher un trou), mais le retrait direct
    coûte de plus en plus avec la distance (40 mm : 13 s au lieu de 0,1 s)."""
    import shapely
    from shapely.geometry import Polygon
    holes = list(poly.interiors)
    if len(holes) < HOLES_SPLIT or d < HOLES_SPLIT_D:
        return poly.buffer(-d, quad_segs=qs)
    shell = Polygon(poly.exterior).buffer(-d, quad_segs=qs)
    if shell.is_empty:
        return shell
    grown = shapely.union_all(shapely.buffer(shapely.polygons(holes), d, quad_segs=qs))
    return shell.difference(grown)


def _erode_parts(parts, d: float, qs: int):
    """Retrait de pièces disjointes : les pièces à nombreux trous une par une
    (_erode_one), les autres d'un coup (shapely vectorisé)."""
    import numpy as np
    import shapely
    if len(parts) == 1:
        return _erode_one(parts[0], d, qs)
    heavy = shapely.get_num_interior_rings(parts) >= HOLES_SPLIT if d >= HOLES_SPLIT_D else         np.zeros(len(parts), dtype=bool)
    out = list(shapely.buffer(parts[~heavy], -d, quad_segs=qs)) if (~heavy).any() else []
    out += [_erode_one(p, d, qs) for p in parts[heavy]]
    return _polys(np.array(out, dtype=object)) if out else _polys(parts[:0])


def simplify_parts(geom, tol: float):
    """`geom.simplify(tol)` (topologie gardée), partie par partie sur une
    région de nombreuses parties : chacune reste valide et à moins de `tol`
    du tracé, mais deux parties voisines peuvent se frôler — rendues alors
    en GeometryCollection, pour leurs seuls anneaux (parcours), pas pour
    des opérations de régions."""
    parts = getattr(geom, 'geoms', None)
    if parts is None or len(parts) <= MANY_PARTS:
        return geom.simplify(tol)
    import shapely
    parts = shapely.simplify(shapely.get_parts(geom), tol)
    return shapely.geometrycollections(parts[~shapely.is_empty(parts)])


def within_test(geom):
    """Test répété « ce trajet reste dans la région » (`geom.contains`) :
    géométrie préparée ; sur une région de nombreuses parties, seules les
    parties proches du trajet sont essayées (arbre STRtree) — un trajet
    d'un seul tenant ne tient que dans une partie."""
    import shapely
    parts = getattr(geom, 'geoms', None)
    if parts is None or len(parts) <= MANY_PARTS:
        shapely.prepare(geom)
        return geom.contains
    tree = shapely.STRtree(shapely.get_parts(geom))
    return lambda g: len(tree.query(g, predicate='within')) > 0


def region(paths: list[Path], tol: float):
    """Région shapely (règle pair-impair) des contours fermés."""
    return region_from_lines(polylines(paths, tol))


def region_from_lines(lines: list):
    """`region` à partir des contours déjà aplatis (`polylines`) : pour qui s'en sert aussi, sans aplatir deux fois (2 s sur un gros dessin)."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    rings = []
    for pts, closed in lines:
        if closed and len(pts) >= 4:
            poly = Polygon(pts)
            if not poly.is_valid:
                poly = poly.buffer(0)
            if not poly.is_empty:
                rings.append(poly)
    if len(rings) > 64:
        return _region_grouped(rings)
    geom = None
    for r in sorted(rings, key=lambda g: -g.area):   # pair-impair : XOR successifs
        geom = r if geom is None else geom.symmetric_difference(r)
    return geom if geom is not None else unary_union([])


def _region_grouped(rings: list):
    """Pair-impair de nombreux contours : le XOR n'agit qu'entre contours
    qui se touchent ; on le fait donc par groupe (composantes d'un arbre
    STRtree), puis les groupes, disjoints, sont réunis sans calcul. Même
    région que les XOR successifs, sans leur coût quadratique."""
    from shapely import STRtree
    from shapely.geometry import MultiPolygon
    parent = list(range(len(rings)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    left, right = STRtree(rings).query(rings, predicate='intersects')
    for i, j in zip(left.tolist(), right.tolist()):
        if i != j:
            a, b = find(i), find(j)
            if a != b:
                parent[a] = b
    groups: dict = {}
    for i in range(len(rings)):
        groups.setdefault(find(i), []).append(rings[i])
    polys = []
    for members in groups.values():
        progress.check()
        if len(members) > XOR_MAX:                       # grand groupe : sans XOR successifs (coût quadratique)
            polys += _even_odd(members)
            continue
        geom = None
        for r in sorted(members, key=lambda g: -g.area):
            geom = r if geom is None else geom.symmetric_difference(r)
        if geom is None or geom.is_empty:
            continue
        polys += [g for g in getattr(geom, 'geoms', [geom]) if g.geom_type == 'Polygon' and not g.is_empty]
    polys = _valid_parts(polys)
    if len(polys) == 1:
        return polys[0]
    return MultiPolygon(polys)


def _valid_parts(polys: list) -> list:
    """Les mêmes polygones, ceux que GEOS trouve non valides réparés sur place, et sans les contours d'aire nulle (un trait repassé sur lui-même,
    moins d'un dixième de micron de large) : les uns et les autres font échouer les calculs suivants, et aucun outil n'y entre. Les autres ne sont pas touchés."""
    import numpy as np
    import shapely
    if not polys:
        return polys
    arr = np.empty(len(polys), dtype=object)
    arr[:] = polys
    bad = ~shapely.is_valid(arr)
    if bad.any():
        out = []
        for g, b in zip(polys, bad.tolist()):
            if b:
                fixed = shapely.make_valid(g)
                out += [q for q in shapely.get_parts(fixed).tolist() if q.geom_type == 'Polygon' and not q.is_empty] if fixed.geom_type != 'Polygon' else [fixed]
            else:
                out.append(g)
        polys = out
        arr = np.empty(len(polys), dtype=object)
        arr[:] = polys
    fine = 2 * shapely.area(arr) >= 1e-4 * shapely.length(arr)
    return polys if fine.all() else [g for g, f in zip(polys, fine.tolist()) if f]


#: au-delà, un groupe de contours qui se touchent est traité par `_even_odd`
XOR_MAX = 16


def _even_odd(members: list) -> list:
    """Pair-impair d'un grand groupe, sans XOR successifs (un cadre autour
    de milliers de lettres : 45 s → 0,3 s). Contours imbriqués sans
    croisement (cas courant) : profondeur = nombre de contours englobants,
    une forme par contour de profondeur paire, ses enfants directs pour
    trous. Sinon : faces du réseau des bords (polygonize), gardées si un
    nombre impair de contours les contient. Même région que les XOR."""
    import shapely
    from shapely.geometry import Polygon
    # une partie (contour réparé en plusieurs morceaux) ou un trou compte comme un contour de plus :
    # même pair-impair (parties disjointes ; forme à trous = extérieur XOR trous)
    arr = []
    for m in members:
        for p in getattr(m, 'geoms', [m]):
            if p.geom_type == 'Polygon' and not p.is_empty:
                arr.append(Polygon(p.exterior))
                arr += [Polygon(h) for h in p.interiors]
    n = len(arr)
    tree = shapely.STRtree(arr)
    li, lj = tree.query(arr, predicate='intersects')
    ci, cj = tree.query(arr, predicate='contains_properly')     # arr[ci] contient arr[cj]
    cont = set(zip(ci.tolist(), cj.tolist()))
    progress.check()
    if all(i == j or (i, j) in cont or (j, i) in cont for i, j in zip(li.tolist(), lj.tolist())):
        depth = [0] * n
        for _i, j in cont:
            depth[j] += 1
        parent = [-1] * n
        for i, j in cont:                                     # parent direct : l'englobant le plus profond
            if depth[i] == depth[j] - 1:
                parent[j] = i
        holes: dict = {}
        for j in range(n):
            if depth[j] % 2 == 1 and parent[j] >= 0:
                holes.setdefault(parent[j], []).append(arr[j].exterior)
        return [Polygon(arr[i].exterior, holes.get(i, [])) for i in range(n) if depth[i] % 2 == 0]
    edges = shapely.union_all(shapely.boundary(arr))            # bords noués aux croisements
    progress.check()
    faces = shapely.get_parts(shapely.polygonize(shapely.get_parts(edges)))
    if len(faces) == 0:
        return []
    fi, _rj = tree.query(shapely.point_on_surface(faces), predicate='within')
    counts = [0] * len(faces)
    for k in fi.tolist():
        counts[k] += 1
    keep = [faces[k] for k in range(len(faces)) if counts[k] % 2 == 1]
    if not keep:
        return []
    try:
        u = shapely.coverage_union_all(keep)
    except shapely.errors.GEOSException:                        # des faces qui se chevauchent de quelques microns : la réunion ordinaire, plus lente
        try:
            u = shapely.union_all(keep)
        except shapely.errors.GEOSException:
            u = shapely.union_all(shapely.make_valid(keep), grid_size=1e-6)
    return [g for g in shapely.get_parts(u) if g.geom_type == 'Polygon' and not g.is_empty]


def frames_of(reg):
    """Cadres de la région : les formes qui en englobent d'autres (avec
    des trous) sans être elles-mêmes englobées — le contour fermé qui
    entoure tout, ou chacun s'il y en a plusieurs. None : aucun."""
    import shapely
    from shapely.geometry import Polygon
    polys = [p for p in getattr(reg, 'geoms', [reg]) if p.geom_type == 'Polygon' and not p.is_empty]
    holed = [i for i, p in enumerate(polys) if p.interiors]
    out = []
    if holed:                                            # un point de chaque forme à trous, cherché dans les contours de toutes à la fois
        shells = [Polygon(p.exterior) for p in polys]
        pts = [polys[i].representative_point() for i in holed]
        q, t = shapely.STRtree(shells).query(pts, predicate='within')
        inside = {holed[a] for a, b in zip(q.tolist(), t.tolist()) if holed[a] != b}
        out = [polys[i] for i in holed if i not in inside]
    if not out:
        return None
    from shapely.ops import unary_union
    return unary_union(out)


def keep_exteriors(op, reg):
    """Valeur `exteriors` de rings_of : True (tous les contours), ou les
    cadres à ne pas repasser (« pas de passe sur le cadre », gravure en relief)."""
    if not getattr(op, 'finish_skip_frame', False):
        return True
    frames = frames_of(reg)
    return True if frames is None else frames


def rings_of(geom, region_on_right: bool, *, exteriors=True) -> list[list]:
    """Anneaux d'une région shapely, orientés pour avoir la région à
    droite (sens horaire autour d'un extérieur) ou à gauche ; `exteriors`
    faux : les trous seulement ; une géométrie (keep_exteriors) : sans le
    contour extérieur des formes qui sont dans ce cadre (gravure en relief)."""
    from shapely.geometry import LinearRing
    out = []
    polys = getattr(geom, 'geoms', [geom])
    for poly in polys:
        if poly.is_empty or poly.geom_type != 'Polygon':
            continue
        outer = exteriors if isinstance(exteriors, bool) else not exteriors.covers(poly.representative_point())
        rings = ([(poly.exterior, True)] if outer else []) + [(h, False) for h in poly.interiors]
        for ring, outer in rings:
            ccw = ring.is_ccw if isinstance(ring, LinearRing) else LinearRing(ring.coords).is_ccw
            pts = list(ring.coords)
            # extérieur : région à gauche si anti-horaire ; trou : l'inverse
            left = ccw if outer else not ccw
            if left == region_on_right:
                pts.reverse()
            out.append(pts)
    return out


# --- émission des mouvements ---------------------------------------------------------

class Emitter:
    def __init__(self, op: Operation, tool: CamTool):
        self.moves: list[Move] = []
        self.safe = op.safe_z
        self.clear = op.clear_z
        self.pos = None
        self.fin = False                                 # vrai pendant une passe de finition : avances marquées

    def travel(self, x: float, y: float) -> None:
        """Rejoindre (x, y) au-dessus de la pièce : montée au dégagement,
        déplacement rapide, descente rapide à la hauteur d'approche."""
        if self.pos is not None and self.pos[2] < self.safe:
            self.moves.append(Move('rapid', self.pos[0], self.pos[1], self.safe))
        self.moves.append(Move('rapid', x, y, self.safe))
        self.moves.append(Move('rapid', x, y, self.clear))
        self.pos = (x, y, self.clear)

    def plunge(self, z: float) -> None:
        x, y, z0 = self.pos
        if abs(z - z0) < 1e-12:
            return
        self.moves.append(Move('plunge', x, y, z))
        self.pos = (x, y, z)

    def feed(self, x: float, y: float, z: float) -> None:
        if self.pos is not None and math.dist(self.pos, (x, y, z)) < 1e-9:
            return
        self.moves.append(Move('feed', x, y, z, fin=True) if self.fin else Move('feed', x, y, z))
        self.pos = (x, y, z)

    def retract(self) -> None:
        if self.pos is not None and self.pos[2] < self.safe:
            self.moves.append(Move('rapid', self.pos[0], self.pos[1], self.safe))
            self.pos = (self.pos[0], self.pos[1], self.safe)


def rapid_retracts(moves: list, safe: float) -> int:
    """Toute remontée verticale jusqu'au dégagement se fait en rapide : l'outil sort par où il est entré. Une
    remontée en plusieurs mouvements (jusqu'à l'approche, puis au dégagement) passe en rapide tout entière ; une
    remontée qui s'arrête plus bas (liaison au fond…) reste comme elle est. Rend le nombre de mouvements changés."""
    n, i, count = 0, 0, len(moves)
    prev = None
    while i < count:
        m = moves[i]
        if prev is None or m.is_arc or m.z <= prev.z + 1e-9 or abs(m.x - prev.x) > 1e-9 or abs(m.y - prev.y) > 1e-9:
            prev = m
            i += 1
            continue
        j, z = i, prev.z
        while j < count and not moves[j].is_arc and moves[j].z > z + 1e-9 and \
                abs(moves[j].x - prev.x) <= 1e-9 and abs(moves[j].y - prev.y) <= 1e-9:
            z = moves[j].z
            j += 1
        if z >= safe - 1e-9:
            for k in range(i, j):
                if moves[k].kind != 'rapid':
                    moves[k].kind = 'rapid'
                    n += 1
        prev = moves[j - 1]
        i = j
    return n


def faced_zone(tp, setup, tol: float = 0.01):
    """Zone couverte par un parcours de surfaçage : (surface XY, cote du fond) ; None : rien de surfacé."""
    from shapely import union_all
    from shapely.geometry import LineString, Point
    tool = setup.tool(tp.tool_id)
    cuts = [m for m in tp.moves if m.kind != 'rapid']
    if tool is None or tool.diameter <= 0 or not cuts:
        return None
    floor = min(m.z for m in cuts)
    r = tool.diameter / 2
    parts, run, prev = [], [], None
    for m in tp.moves:
        here = (m.x, m.y)
        if prev is not None and m.kind != 'rapid' and not m.is_arc and abs(m.z - floor) < 1e-6 \
                and abs(prev[2] - floor) < 1e-6:
            if not run:
                run = [prev[:2]]
            if here != run[-1]:
                run.append(here)
        elif run:
            parts.append(LineString(run) if len(run) > 1 else Point(run[0]))
            run = []
        prev = (m.x, m.y, m.z)
    if run:
        parts.append(LineString(run) if len(run) > 1 else Point(run[0]))
    if not parts:
        return None
    return union_all([g.buffer(r, quad_segs=8) for g in parts]), floor


def apply_faced(tp, op, setup, zone, floor: float) -> int:
    """Liaisons de `tp` au-dessus de la zone surfacée : au dégagement bas de l'opération au lieu de son dégagement
    (`op.safe_z`, gardé pour tout ce qui traverse une partie non surfacée). Un outil entier doit rester dans la
    zone, de son départ à son arrivée ; le premier et le dernier mouvement du parcours ne changent pas. Rend le
    nombre de liaisons baissées. À refaire depuis `tp.unfaced` : le surfaçage a pu changer."""
    from shapely.prepared import prep
    from shapely.geometry import LineString
    moves = tp.unfaced if tp.unfaced is not None else tp.moves
    tp.moves, tp.unfaced = moves, None
    low = max(0.0, floor) + float(getattr(op, 'safe_z_faced', 0.0) or 0.0)
    # le dégagement tel qu'il est dans le parcours : un Z de départ le déplace avec tout le reste (une opération qui
    # part du fond d'une poche a ses liaisons plus bas d'autant)
    safe = op.safe_z + float(getattr(op, 'z_start', 0.0) or 0.0)
    tool = setup.tool(tp.tool_id)
    if tool is None or tool.kind == 'laser' or not getattr(op, 'safe_z_faced', 0.0) or low >= safe - 1e-9 \
            or (getattr(op, 'wrap', 'none') or 'none') != 'none' or tp.cycles or tp.source != 'vectordrive':
        return 0
    if any(m.kind != 'rapid' and m.z > low - 1e-9 for m in moves):
        return 0                                         # une coupe au-dessus du dégagement bas : rien à gagner, tout à perdre
    inner = zone.buffer(-tool.diameter / 2)
    if inner.is_empty:
        return 0
    test = prep(inner)
    out, n, i, count = [], 0, 0, len(moves)
    while i < count:
        if moves[i].kind != 'rapid' or i == 0:
            out.append(moves[i])
            i += 1
            continue
        j = i
        while j < count and moves[j].kind == 'rapid':
            j += 1
        run = moves[i:j]
        start, end = moves[i - 1], run[-1]
        moved = abs(end.x - start.x) > 1e-9 or abs(end.y - start.y) > 1e-9
        if j < count and moved and max(m.z for m in run) >= safe - 1e-9 and \
                test.covers(LineString([(start.x, start.y), (end.x, end.y)])):
            if start.z < low - 1e-9:
                out.append(Move('rapid', start.x, start.y, low))
            out.append(Move('rapid', end.x, end.y, low))
            if end.z < low - 1e-9:
                out.append(Move('rapid', end.x, end.y, end.z))
            n += 1
        else:
            out.extend(run)
        i = j
    if n:
        tp.unfaced, tp.moves = moves, out
    return n


#: natures dont le fond plat, une fois fait, laisse les opérations suivantes passer plus bas au-dessus de lui : le
#: surfaçage, et la poche (demande du 15/11 : le dégagement « où tout a été usiné sous le parcours rapide »)
LOW_ZONE_KINDS = ('surfacage', 'poche')
LOW_NOTES = ('dégagement bas sur la zone surfacée', 'dégagement bas sur la zone déjà usinée')


def flat_floor(op, tool) -> bool:
    """Le parcours de `op` laisse-t-il un fond plat, vidé partout où son outil est passé ? Un surfaçage : oui ; une
    poche : à la fraise seulement (un cône ou une boule laissent un fond plus étroit que leur diamètre), et si elle
    vide tout (`clears_all` : ni texture, ni balayage sans tour du contour)."""
    if op.kind == 'surfacage':
        return True
    return op.kind == 'poche' and tool is not None and tool.kind == 'fraise' and clears_all(op, tool)


def low_zone_of(tp, setup):
    """`faced_zone(tp)`, gardée avec le parcours tant que ses mouvements sont les mêmes : la même liste, autant de
    mouvements, la même somme de leurs cotes (un parcours déplacé ou retaillé sur place est refait)."""
    moves = tp.moves
    mark = (len(moves), round(sum(m.x + 2.0 * m.y + 3.0 * m.z for m in moves), 6))
    memo = getattr(tp, '_low_zone', None)
    if memo is None or memo[0] is not moves or memo[1] != mark:
        memo = (moves, mark, faced_zone(tp, setup))
        tp._low_zone = memo
    return memo[2]


def apply_faced_all(setup, toolpaths) -> None:
    """Liaisons basses de chaque parcours sur ce que les surfaçages et les poches d'avant ont vidé ; puis les
    reprises d'usinage, qui coupent le parcours complet.

    Tout est d'abord remis au dégagement haut : une liaison basse ne survit jamais à ce qui l'a permise (poche
    retirée, décochée, déplacée après, refaite au cône). Ne comptent, pour être abaissés comme pour abaisser, que
    les parcours qui vont au programme (opération active, parcours coché), dans l'ordre de la liste, par prise
    (face de la pièce, corps) ; une instruction machine (palpage, repère, retournement, table à vide…) remet à
    zéro : ce qui était usiné avant elle ne l'est plus à coup sûr au même endroit."""
    from shapely import union_all
    from . import restart
    for tp in toolpaths:
        restart.restore(tp)
    ops = {o.id: o for o in setup.operations}
    for tp in toolpaths:
        if tp.unfaced is not None:
            tp.moves, tp.unfaced = tp.unfaced, None
        tp.warnings[:] = [w for w in tp.warnings if not w.startswith(LOW_NOTES)]
    zones: dict = {}                                     # prise → [(zone, cote du fond, d'une poche ?)]
    for tp in toolpaths:
        op = ops.get(tp.op_id)
        if op is None or not op.enabled or not getattr(tp, 'shown', True):
            continue
        if op.kind == 'instruction':                     # (un parcours sans mouvement : vu avant le test suivant)
            zones.clear()
            continue
        if not tp.moves:
            continue
        hold =(getattr(op, 'setup_face', '') or '', getattr(op, 'body3d', -1))
        mine = low_zone_of(tp, setup) if op.kind in LOW_ZONE_KINDS and flat_floor(op, setup.tool(op.tool_id)) \
            else None                                    # (d'après ses mouvements d'origine : avant de les abaisser)
        got = zones.get(hold)
        if got:
            floor = max(f for _z, f, _p in got)
            n = apply_faced(tp, op, setup, got[0][0] if len(got) == 1 else union_all([z for z, _f, _p in got]),
                            floor)
            if n:
                low = max(0.0, floor) + float(op.safe_z_faced or 0.0)
                safe = op.safe_z + float(getattr(op, 'z_start', 0.0) or 0.0)
                note = LOW_NOTES[1] if any(p for _z, _f, p in got) else LOW_NOTES[0]
                tp.warnings.append(f'{note} : {n} liaison(s) à {low:g} mm, {safe:g} mm ailleurs')
        if mine is not None:
            zones.setdefault(hold, []).append((mine[0], mine[1], op.kind != 'surfacage'))
    for tp in toolpaths:
        op = ops.get(tp.op_id)
        if op is not None:
            restart.apply(op, tp)


def levels(depth: float, step: float) -> list[float]:
    """Cotes Z des passes jusqu'à −depth."""
    depth = abs(depth)
    if depth <= 0:
        return [0.0]
    if step <= 0 or step >= depth:
        return [-depth]
    n = math.ceil(depth / step - 5e-3)                    # 2 mm par 0,3333 : 6 passes, pas 7 (un pas arrondi à l'affichage)
    return [-min(depth, (k + 1) * depth / n) for k in range(n)]


def parse_depths(text: str) -> list[float]:
    """« 0,6 0,5 ; 0.4 » → [0.6, 0.5, 0.4] (valeurs positives)."""
    out = []
    for tok in re.split(r'[\s;/]+', (text or '').replace(',', '.').strip()):
        try:
            v = float(tok)
        except ValueError:
            continue
        if v > 0:
            out.append(v)
    return out


def op_levels(op: Operation, tool: CamTool) -> list[float]:
    """Cotes des passes de l'opération : profondeurs successives données
    (`pass_depths`, la dernière répétée jusqu'au fond), sinon passes égales."""
    steps = parse_depths(getattr(op, 'pass_depths', ''))
    depth = abs(op.depth)
    if not steps or depth <= 0:
        return levels(op.depth, op.step_down or tool.step_down)
    out, z, k = [], 0.0, 0
    while z < depth - 1e-9 and len(out) < 10000:
        z = min(depth, round(z + steps[min(k, len(steps) - 1)], 9))
        out.append(-z)
        k += 1
    return out


def _start_nearest(pts: list, closed: bool, here) -> list:
    """Contour fermé : départ au point le plus proche ; ouvert : sens qui
    commence au plus près."""
    if here is None:
        return pts
    if closed:
        ring = pts[:-1]
        i = min(range(len(ring)), key=lambda k: math.dist(ring[k][:2], here[:2]))
        ring = ring[i:] + ring[:i]
        return ring + [ring[0]]
    if math.dist(pts[-1][:2], here[:2]) < math.dist(pts[0][:2], here[:2]):
        return pts[::-1]
    return pts


def start_marks(doc, op, tol: float) -> list:
    """Où les contours fermés doivent commencer (TE, page 693) : les points choisis à la main (Mode Point, Point de départ) puis,
    en « Point de départ du dessin », le début de chaque contour fermé."""
    items = source_items(doc, op)
    marks = [tuple(p[:2]) for it in items for p in (getattr(it, 'extra', {}) or {}).get('start_xy', [])]
    marks += [(m[0], m[1]) for m in lead_marks(doc, op)]
    if getattr(op, 'start_policy', 'proche') == 'dessin':
        geoms = [g for it in items if (g := item_geometry(it))]
        marks += [(pts[0][0], pts[0][1], tuple(pts[-2][:2]), tuple(pts[1][:2]))     # le sommet et ses deux voisins
                  for pts, closed in polylines(geoms, tol) if closed and len(pts) >= 4]
    return marks


def _start_after_corner(ring: list, m, offset: float):
    """Où commence un contour décalé de `offset`, pour un sommet du dessin (x, y, voisin, voisin) : relevé dans TE13, au début du
    côté par lequel l'outil quitte le sommet, donc après l'arrondi de l'angle, et l'entrée y est tangente. Là où le décalage n'a
    pas de tel point (angle rentrant, pas de décalage) : le point du contour le plus près du sommet."""
    if len(m) < 4 or offset <= 0:
        return m
    for other in m[2:4]:
        ex, ey = other[0] - m[0], other[1] - m[1]
        n = math.hypot(ex, ey)
        if n < 1e-9:
            continue
        ex, ey = ex / n, ey / n
        for side in (1.0, -1.0):
            p = (m[0] - side * ey * offset, m[1] + side * ex * offset)
            d, i, q = _closest_on_ring(ring, p)
            if d > 1e-3:
                continue
            # le point peut être la fin de l'arrondi : c'est alors le segment suivant qui part le long du côté
            at_end = math.dist(q[:2], ring[i + 1][:2]) < 1e-3
            for j in (i, (i + 1) % (len(ring) - 1)) if at_end else (i,):
                tx, ty = ring[j + 1][0] - ring[j][0], ring[j + 1][1] - ring[j][1]
                nt = math.hypot(tx, ty)
                if nt > 1e-12 and (tx * ex + ty * ey) / nt > 0.999:
                    return q
    return m


def lead_marks(doc, op) -> list:
    """Entrées et sorties réglées contour par contour, posées sur les formes (TE : Ponts et E/S tangentielles manuels) :
    [(x, y, entrée, sortie)]. Le point est aussi le départ du contour."""
    return [tuple(float(v) for v in p[:4]) for it in source_items(doc, op)
            for p in (getattr(it, 'extra', {}) or {}).get('lead_xy', []) if len(p) >= 4]


def marked_leads(rings: list, marks: list, near: float) -> dict:
    """Chaque marque revient à l'anneau le plus proche, à moins de `near` : {indice de l'anneau : (entrée, sortie)}."""
    won: dict = {}
    for m in marks:
        best, bd = None, near
        for k, pts in enumerate(rings):
            if len(pts) >= 2:
                d = _closest_on_ring(pts, m)[0]
                if d <= bd:
                    best, bd = k, d
        if best is not None:
            won.setdefault(best, (m[2], m[3]))
    return won


def _closest_on_ring(pts: list, m) -> tuple:
    """(distance, indice du côté, point de ce côté) le plus près de `m`, sur un anneau fermé."""
    best = None
    for i in range(len(pts) - 1):
        ax, ay = pts[i][:2]
        bx, by = pts[i + 1][:2]
        ux, uy = bx - ax, by - ay
        uu = ux * ux + uy * uy
        t = 0.0 if uu < 1e-18 else max(0.0, min(1.0, ((m[0] - ax) * ux + (m[1] - ay) * uy) / uu))
        q = (ax + t * ux, ay + t * uy)
        d = math.dist(q, m[:2])
        if best is None or d < best[0] - 1e-12:
            best = (d, i, q)
    return best


def begin_at(pts: list, m) -> list:
    """Le même anneau fermé, qui part du point le plus près de `m` (ajouté s'il tombe au milieu d'un côté)."""
    _d, i, q = _closest_on_ring(pts, m)
    ring = [tuple(p[:2]) for p in pts[:-1]]
    seq = [q] + ring[i + 1:] + ring[:i + 1]
    out = [q]
    for p in seq[1:]:
        if math.dist(p, out[-1]) > 1e-9:
            out.append(p)
    if len(out) > 1 and math.dist(out[-1], q) <= 1e-9:
        out.pop()
    return out + [q]


def apply_starts(chains: list, marks: list, near: float, offset: float = 0.0) -> tuple:
    """Chaque point de départ revient au contour fermé le plus proche, à moins de `near` (le contour usiné est décalé de celui du
    dessin, de `offset`). Rend les chaînes, dans le même ordre, et l'ensemble de leurs nouveaux débuts."""
    fixed: set = set()
    if not marks:
        return chains, fixed
    boxes = {}
    for k, (pts, closed) in enumerate(chains):
        if closed and len(pts) >= 4:
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            boxes[k] = (min(xs) - near, min(ys) - near, max(xs) + near, max(ys) + near)
    won: dict = {}
    for m in marks:
        best, bd = None, near
        for k, (x0, y0, x1, y1) in boxes.items():
            if x0 <= m[0] <= x1 and y0 <= m[1] <= y1:
                d = _closest_on_ring(chains[k][0], m)[0]
                if d <= bd:
                    best, bd = k, d
        if best is not None:
            won.setdefault(best, m)                      # le premier : celui choisi à la main
    out = list(chains)
    for k, m in won.items():
        pts = begin_at(chains[k][0], _start_after_corner(chains[k][0], m, offset))
        out[k] = (pts, True)
        fixed.add(pts[0])
    return out, fixed


def order_chains(chains: list[tuple[list, bool]], here=(0.0, 0.0)) -> list[tuple[list, bool]]:
    """Ordre du plus proche voisin (réduit les rapides) : à chaque pas, la
    chaîne la plus proche (fermée : par n'importe lequel de ses points ;
    ouverte : par un bout ; à égalité, la première). Au-delà de quelques
    dizaines de chaînes, recherche dans une grille (TauDrive) : mêmes
    résultats, sans le coût quadratique. Tri manuel (opération en « ordre
    du dessin ») : les chaînes restent dans l'ordre et le sens du dessin."""
    if _DRAWING_ORDER.get():
        return list(chains)
    if len(chains) > 48:
        return _order_grid(chains, here)
    rest = list(chains)
    out = []
    while rest:
        def d(c):
            pts, closed = c
            if closed:
                return min(math.dist(p[:2], here[:2]) for p in pts)
            return min(math.dist(pts[0][:2], here[:2]), math.dist(pts[-1][:2], here[:2]))
        best = min(rest, key=d)
        rest.remove(best)
        pts = _start_nearest(best[0], best[1], here)
        out.append((pts, best[1]))
        here = pts[-1]
    return out


def _order_grid(chains: list, here) -> list:
    """`order_chains` par grille régulière : points candidats (tous ceux
    d'une chaîne fermée, les bouts d'une ouverte) rangés par case ; recherche
    par anneaux autour du point courant, arrêtée quand l'anneau suivant ne
    peut plus faire mieux."""
    pts_all = []
    for i, (pts, closed) in enumerate(chains):
        cand = pts if closed else ([pts[0], pts[-1]] if pts else [])
        pts_all += [(p[0], p[1], i) for p in cand]
    if not pts_all:
        return list(chains)
    xs = [p[0] for p in pts_all]
    ys = [p[1] for p in pts_all]
    x0, y0 = min(xs), min(ys)
    span = max(max(xs) - x0, max(ys) - y0, 1e-9)
    h = max(span / max(1.0, math.sqrt(len(pts_all))), 1e-9)
    nx, ny = int((max(xs) - x0) / h) + 1, int((max(ys) - y0) / h) + 1
    grid: dict = {}
    for x, y, i in pts_all:
        grid.setdefault((int((x - x0) / h), int((y - y0) / h)), []).append((x, y, i))
    used = [False] * len(chains)
    out = []
    for _ in range(len(chains)):
        qx, qy = here[0], here[1]
        cx = min(max(int((qx - x0) / h), -1), nx)
        cy = min(max(int((qy - y0) / h), -1), ny)
        best = (math.inf, -1)
        # distance du point courant à la grille : les anneaux commencent là
        r = 0
        rmax = max(nx, ny) + abs(cx) + abs(cy) + 2
        while r <= rmax:
            for gx in range(cx - r, cx + r + 1):
                for gy in (range(cy - r, cy + r + 1) if gx in (cx - r, cx + r) else (cy - r, cy + r)):
                    for x, y, i in grid.get((gx, gy), ()):
                        if used[i]:
                            continue
                        d = math.dist((x, y), (qx, qy))
                        if d < best[0] or (d == best[0] and i < best[1]):
                            best = (d, i)
            if best[1] >= 0 and best[0] <= r * h:
                break
            r += 1
        i = best[1]
        if i < 0:
            break
        used[i] = True
        pts = _start_nearest(chains[i][0], chains[i][1], here)
        out.append((pts, chains[i][1]))
        here = pts[-1]
    return out


def _cum(pts) -> list[float]:
    s = [0.0]
    for a, b in zip(pts, pts[1:]):
        s.append(s[-1] + math.dist(a[:2], b[:2]))
    return s


def _point_at(pts, cum, s):
    """Point à l'abscisse curviligne s."""
    for k in range(1, len(pts)):
        if cum[k] >= s - 1e-12:
            a, b = pts[k - 1], pts[k]
            L = cum[k] - cum[k - 1]
            t = 0.0 if L <= 0 else (s - cum[k - 1]) / L
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    return pts[-1][:2]


def _split_at(pts, cuts: list[float]) -> tuple[list, list]:
    """Polyligne avec des sommets ajoutés aux abscisses `cuts` ; rend
    (points, abscisses)."""
    cum = _cum(pts)
    extra = sorted(c for c in cuts if 0 < c < cum[-1])
    out, outs = [pts[0][:2]], [0.0]
    j = 0
    for k in range(1, len(pts)):
        while j < len(extra) and extra[j] < cum[k] - 1e-9:
            if extra[j] > outs[-1] + 1e-9:
                out.append(_point_at(pts, cum, extra[j]))
                outs.append(extra[j])
            j += 1
        out.append(pts[k][:2])
        outs.append(cum[k])
    return out, outs


def ramp_angle_of(op) -> float:
    """Angle de rampe de l'opération (°), 5° par défaut, borné à ]0,5 ; 45]."""
    a = float(getattr(op, 'ramp_angle', 0.0) or 0.0)
    return min(45.0, max(0.5, a)) if a > 0 else RAMP_ANGLE


def _first_stretch(spts: list, limit: float) -> tuple:
    """Le début d'une polyligne, sur `limit` mm : (points, abscisses)."""
    pts, cum = _split_at(spts, [limit])
    n = next(i for i, s in enumerate(cum) if s >= limit - 1e-9)
    return pts[:n + 1], cum[:n + 1]


def _ramp_open(em: Emitter, spts: list, sabs: list[float], z_from: float, z: float, angle: float, *,
               walk: bool = True, limit: float | None = None) -> None:
    """Descente en rampe le long d'un trait ouvert, en zigzag s'il est plus
    court que la rampe, puis retour au départ à la cote et le trait entier
    (`walk` faux : il s'arrête au départ). La distance maxi (`limit`, sinon celle de
    l'opération) borne la longueur du zigzag."""
    whole = spts
    limit = _RAMP_LIMIT.get() if limit is None else limit
    if 0 < limit < sabs[-1] - 1e-9:
        spts, sabs = _first_stretch(spts, limit)
    L = sabs[-1]
    if L <= 1e-9:
        em.plunge(z)
        return
    run = (z_from - z) / math.tan(math.radians(angle))
    em.plunge(z_from)
    done = 0.0
    forward = True
    idx = 0                                        # sommet courant
    while True:
        nxt = idx + 1 if forward else idx - 1
        if not 0 <= nxt < len(spts):
            forward = not forward
            continue
        seg = abs(sabs[nxt] - sabs[idx])
        if seg <= 1e-12:
            idx = nxt
            continue
        if done + seg >= run - 1e-12:
            t = max(0.0, run - done) / seg
            a, b = spts[idx], spts[nxt]
            em.feed(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, z)
            # retour au départ à la cote : vers le début du trait
            back = range(idx, -1, -1) if forward else range(nxt, -1, -1)
            for k in back:
                em.feed(spts[k][0], spts[k][1], z)
            break
        done += seg
        em.feed(spts[nxt][0], spts[nxt][1], z_from + (z - z_from) * done / run)
        idx = nxt
    if walk:
        for p in whole[1:]:
            em.feed(p[0], p[1], z)


def _ramp_lap(em: Emitter, spts: list, sabs: list, zf, z_from: float, z: float, angle: float, edges: list | None = None,
              clean: bool = True) -> None:
    """Un tour d'anneau fermé qui descend de `z_from` à `z` à l'angle exact (relevé dans TE13) : la pente, en autant de tours qu'il
    faut, puis le reste du tour à la cote. `clean` : on repasse à la cote sur la partie en pente, et l'outil s'arrête au bout de
    celle-ci ; sinon il s'arrête au départ, et la passe suivante, plus basse, enlève ce que la pente a laissé."""
    L = sabs[-1]
    em.plunge(z_from)
    if L <= 1e-9 or z >= z_from:
        em.plunge(z)
        return
    run = (z_from - z) / math.tan(math.radians(angle))
    turns = int((run + 1e-9) // L)
    rest = run - turns * L
    for turn in range(turns):
        for p, s in zip(spts[1:], sabs[1:]):
            em.feed(p[0], p[1], max(z_from + (z - z_from) * min(1.0, (turn * L + s) / run), zf(s)))
    sp, sa = spts, sabs
    k = 0
    if rest > 1e-9:
        sp, sa = _split_at(spts, [rest])
        k = next(i for i, s in enumerate(sa) if s >= rest - 1e-9)
        for p, s in zip(sp[1:k + 1], sa[1:k + 1]):
            em.feed(p[0], p[1], max(z_from + (z - z_from) * min(1.0, (turns * L + s) / run), zf(s)))
        _walk(em, sp[k:], sa[k:], zf, z, edges)
    if clean:
        if turns:
            _walk(em, spts, sabs, zf, z, edges)
        elif k:
            _walk(em, sp[:k + 1], sa[:k + 1], zf, z, edges)


def _ramp_closed(em: Emitter, pts: list, z_from: float, z: float, angle: float) -> None:
    """Descente en rampe le long d'un anneau fermé (en hélice s'il est
    court), puis l'anneau à la cote."""
    spts = [p[:2] for p in pts]
    sabs = _cum(spts)
    L = sabs[-1]
    if 0 < _RAMP_LIMIT.get() < L - 1e-9:                 # distance maxi : en allers-retours sur le début de l'anneau
        _ramp_open(em, spts, sabs, z_from, z, angle)
        return
    _ramp_lap(em, spts, sabs, lambda s: z, z_from, z, angle)


def cut_chain(em: Emitter, pts: list, closed: bool, zs: list[float], *, ramp: bool = False,
              tabs: list | None = None, tab_z: float | None = None, ramp_angle: float = RAMP_ANGLE,
              trace: str = 'simple', tab_shape: str = 'droit', z_start: float = 0.0, lift: str = '') -> None:
    """Usine une polyligne à chaque cote de `zs`. Fermée : on reste en bas
    et on plonge au départ ; ouverte : un sens par passe (pas de remontée) —
    `trace` (`Operation.trace_mode`, relevé dans TE13) : 'ar' (fermée ou ouverte : à chaque
    cote, le trait puis son retour, sans descendre entre les deux), 'dernier' (ce retour à la
    dernière cote seulement ; ouverte : même sens, l'outil remonte et revient au départ),
    'meme_sens' (ouverte : toujours dans le même sens, sans retour).
    `tabs` : intervalles d'abscisse où l'outil remonte à `tab_z` (pontets) ;
    `tab_shape` 'incurve' : montée et descente en quart de sinus sur le
    premier et le dernier tiers du pontet (pontet incurvé).
    `ramp` : descente en rampe (`ramp_angle`) — fermée : le long du contour ;
    ouverte : en zigzag le long du trait. `z_start` : cote d'où l'on descend
    vers la première de `zs` (passes faites une à une, ordre global).
    `lift` (fermée, en rampe) : passes non connectées, relevé dans TE13 : à chaque passe l'outil remonte, revient au départ et
    redescend en rampe, depuis `z_start` ('surface' : la découpe) ou depuis la passe d'avant ('passe' : le tracé). Sinon il reste
    dans la matière et descend de la passe d'avant à la suivante."""
    if not pts:
        return
    if not closed and trace in ('meme_sens', 'dernier'):
        for z in zs:
            if tabs:
                cut_chain(em, pts, False, [z], tabs=tabs, tab_z=tab_z, tab_shape=tab_shape)
                continue
            em.travel(*pts[0][:2])
            em.plunge(z)
            for p in pts[1:]:
                em.feed(p[0], p[1], z)
        if trace == 'dernier' and zs:
            if tabs:
                whole = _cum(pts)[-1]
                cut_chain(em, pts[::-1], False, [zs[-1]], tab_z=tab_z, tab_shape=tab_shape,
                          tabs=sorted((whole - b, whole - a) for a, b in tabs))
                return
            for p in pts[-2::-1]:
                em.feed(p[0], p[1], zs[-1])
        return
    em.travel(*pts[0][:2])
    z_prev = z_start
    seq = pts
    for level, z in enumerate(zs):
        last = level == len(zs) - 1
        go_back = trace == 'ar' or (closed and trace == 'dernier' and last)
        if lift and ramp and closed and level > 0:
            em.travel(*seq[0][:2])
            if lift == 'surface':
                z_prev = z_start
        if not closed and trace != 'ar' and level > 0:
            seq = seq[::-1]
        if tabs and tab_z is not None and z < tab_z:
            curved = tab_shape == 'incurve'
            cuts = [a + (b - a) * i / 24 for a, b in tabs for i in range(25)] if curved else \
                [b for iv in tabs for b in iv]
            spts, sabs = _split_at(seq, cuts)
            edges = None if curved else tabs

            def zf(s, z=z):
                for a, b in tabs:
                    if a - 1e-9 <= s <= b + 1e-9:
                        if not curved or b - a <= 1e-9:
                            return tab_z
                        t = (s - a) / (b - a)
                        phi = max(0.0, min(1.0, t * 3, (1 - t) * 3))
                        return z + (tab_z - z) * (1 - math.cos(math.pi * phi)) / 2
                return z
        else:
            spts, sabs = [p[:2] for p in seq], _cum(seq)
            edges = None

            def zf(s, z=z):
                return z
        if ramp and not closed and z < z_prev and not tabs:
            _ramp_open(em, spts, sabs, z_prev, z, ramp_angle)
        elif ramp and closed and z < z_prev:
            # descente en rampe le long du contour, en autant de tours qu'il faut pour ne pas
            # dépasser l'angle (TypeEdit : « en feuille morte »), puis un tour complet à la cote
            # pour reprendre la partie en pente
            limit = _RAMP_LIMIT.get()
            if limit > 0 and tabs:                       # les allers-retours ne passent pas sur un pontet
                limit = min([limit] + [a for a, _b in tabs])
            if 1e-3 < limit < sabs[-1] - 1e-9:           # distance maxi : en allers-retours sur le début du contour
                _ramp_open(em, spts, sabs, z_prev, z, ramp_angle, walk=False, limit=limit)
                _walk(em, spts, sabs, zf, z, edges)
                if go_back:
                    _walk_back(em, spts, sabs, zf, z, edges)
                z_prev = z
                continue
            _ramp_lap(em, spts, sabs, zf, z_prev, z, ramp_angle, edges, clean=(bool(lift) or last) and not go_back)
        else:
            em.plunge(zf(0.0))
            _walk(em, spts, sabs, zf, z, edges)
        if go_back:
            _walk_back(em, spts, sabs, zf, z, edges)
        z_prev = z


def _walk_back(em: 'Emitter', spts: list, sabs: list, zf, z: float, edges: list | None) -> None:
    """Le retour sur le trait, à la même cote : le même chemin à l'envers, pontets compris."""
    whole = sabs[-1]
    back = [whole - s for s in reversed(sabs)]
    turned = None if edges is None else sorted((whole - b, whole - a) for a, b in edges)
    _walk(em, spts[::-1], back, lambda s: zf(whole - s), z, turned)


def _walk(em: 'Emitter', spts: list, sabs: list, zf, z: float, edges: list | None) -> None:
    """L'outil suit la polyligne à la hauteur `zf`. Pontets droits (`edges`) : il coupe à la cote `z` jusqu'au bord du pontet,
    y monte sur place, et redescend sur place à l'autre bord. Sinon il monterait en pente depuis le sommet d'avant : sur un long
    côté, toute la longueur resterait à moitié coupée."""
    for p, s in zip(spts[1:], sabs[1:]):
        h = zf(s)
        if edges and any(abs(s - a) <= 1e-9 for a, _b in edges):
            em.feed(p[0], p[1], z)
            em.feed(p[0], p[1], h)
        elif edges and any(abs(s - b) <= 1e-9 for _a, b in edges):
            em.feed(p[0], p[1], h)
            em.plunge(z)
        else:
            em.feed(p[0], p[1], h)


def has_tabs(op) -> bool:
    """Pontets demandés : un nombre, ou un écart (TypeEdit : distance entre pontets)."""
    return op.tabs > 0 or float(getattr(op, 'tab_spacing', 0.0) or 0.0) > 0 or float(getattr(op, 'tab_gap', 0.0) or 0.0) > 0


def tab_count(op, pts: list, width: float = 0.0) -> int:
    """Pontets d'un contour : le nombre demandé, au moins un tous les
    `tab_spacing` mm de contour. `tab_gap` : la distance entre ponts de TE13 ; relevé dans ses parcours, leur nombre est la longueur
    du contour sur (distance + `width`, la longueur du pont avec l'outil), arrondi, et au moins un."""
    n = max(0, int(op.tabs))
    spacing = float(getattr(op, 'tab_spacing', 0.0) or 0.0)
    if spacing > 0 and len(pts) > 1:
        n = max(n, int(_cum(pts)[-1] // spacing), 1)
    gap = float(getattr(op, 'tab_gap', 0.0) or 0.0)
    if gap > 0 and len(pts) > 1:
        n = max(n, int(_cum(pts)[-1] / (gap + width) + 0.5), 1)
    most = int(getattr(op, 'tab_max', 0) or 0)
    return min(n, most) if most > 0 else n


def dashes(pts: list, tabs: list, closed: bool = True, on_tabs: bool = False) -> list:
    """Les morceaux d'une polyligne hors de ses pontets (TypeEdit : Pointillés, des ponts sans hauteur) ; `on_tabs` : les
    morceaux sur les pontets (Nettoyer les ponts). Fermée : le dernier et le premier morceau n'en font qu'un."""
    spts, sabs = _split_at(pts, [b for iv in tabs for b in iv])
    out, cur = [], []
    for k in range(len(spts) - 1):
        mid = (sabs[k] + sabs[k + 1]) / 2
        if any(a <= mid <= b for a, b in tabs) == on_tabs:
            cur = cur or [spts[k]]
            cur.append(spts[k + 1])
        elif cur:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    if closed and len(out) > 1 and math.dist(out[-1][-1], out[0][0]) < 1e-9:
        out[0] = out.pop() + out[0][1:]
    return out


def cut_dashes(em: 'Emitter', pts: list, closed: bool, zs: list, tabs: list, mode: str) -> None:
    """'pointille' : à chaque passe, tout sauf les pontets, l'outil relevé entre deux morceaux (le laser éteint) ; 'nettoyer' :
    à la dernière passe, seulement les pontets laissés par un usinage précédent."""
    if mode == 'nettoyer':
        for piece in dashes(pts, tabs, closed, on_tabs=True):
            cut_chain(em, piece, False, zs[-1:])
        return
    pieces = dashes(pts, tabs, closed)
    for z in zs:
        for piece in pieces:
            cut_chain(em, piece, False, [z])


def tab_points(pts: list, tabs: list | None) -> list:
    """Le milieu (x, y) de chaque pontet, pour les retrouver sur un autre parcours du même contour."""
    if not tabs:
        return []
    from shapely.geometry import LineString
    line = LineString([p[:2] for p in pts])
    return [tuple(line.interpolate((a + b) / 2).coords[0])[:2] for a, b in tabs]


def tab_intervals(pts: list, n: int, width: float) -> list[tuple[float, float]]:
    """`n` pontets répartis sur la longueur d'un contour fermé."""
    if n <= 0:
        return []
    L = _cum(pts)[-1]
    if L <= n * width:
        return []
    return [((k + 0.5) * L / n - width / 2, (k + 0.5) * L / n + width / 2) for k in range(n)]


# --- stratégies ------------------------------------------------------------------------

def _feeds(op: Operation, tool: CamTool):
    from .model import op_feed                       # l'avance du cadre actif (ébauche ou finition)
    return (op_feed(op, tool), op.plunge or tool.plunge, op.spindle or tool.spindle)


def _gravure(doc, setup, op, tool, tp: Toolpath, em: Emitter, here) -> None:
    geoms = [g for it in source_items(doc, op) if (g := item_geometry(it))]
    chains = order_chains(polylines(geoms, setup.tolerance), here)
    chains = apply_starts(chains, start_marks(doc, op, setup.tolerance), max(10 * setup.tolerance, 0.01))[0]
    zs = op_levels(op, tool)
    tabbed = has_tabs(op)
    mode = getattr(op, 'tab_mode', 'pont')
    tab_z = -(abs(op.depth) - op.tab_height) if tabbed else None
    for pts, closed in chains:
        tabs = tab_intervals(pts, tab_count(op, pts, op.tab_width + tool.diameter), op.tab_width + tool.diameter) if tabbed else None
        if tabbed and mode != 'pont' and tabs:
            cut_dashes(em, pts, closed, zs, tabs, mode)
        elif not (tabbed and mode == 'nettoyer'):
            connected = bool(getattr(op, 'link_passes', False))
            cut_chain(em, pts, closed, zs, ramp=op.ramp or connected, ramp_angle=ramp_angle_of(op),
                      trace=getattr(op, 'trace_mode', 'simple'), tabs=tabs if mode == 'pont' else None,
                      tab_z=tab_z, tab_shape=getattr(op, 'tab_shape', 'droit'), lift='passe' if op.ramp and not connected else '')
    if not chains:
        tp.warnings.append('aucun trait à graver pour cette opération')


def knife_corners(pts: list, closed: bool, min_angle: float) -> list[int]:
    """Indices des sommets où la direction tourne de plus de `min_angle`°."""
    n = len(pts)
    out = []
    rng = range(n - 1) if closed else range(1, n - 1)
    for i in rng:
        a = pts[i - 1] if i > 0 else pts[-2]
        b, c = pts[i], pts[i + 1]
        d1 = (b[0] - a[0], b[1] - a[1])
        d2 = (c[0] - b[0], c[1] - b[1])
        n1, n2 = math.hypot(*d1), math.hypot(*d2)
        if n1 < 1e-9 or n2 < 1e-9:
            continue
        cosv = max(-1.0, min(1.0, (d1[0] * d2[0] + d1[1] * d2[1]) / (n1 * n2)))
        if math.degrees(math.acos(cosv)) > min_angle:
            out.append(i)
    return out


def corner_loops(pts: list, closed: bool, min_angle: float, max_angle: float = 165.0, length: float = 5.5,
                 radius: float = 2.5, min_side: float = 0.1, accept=None, steps: int = 16,
                 turn_sign: int = 0) -> tuple[list, int]:
    """Boucles aux angles vifs (couteau flottant TypeEdit) : à chaque angle
    tournant de `min_angle` à `max_angle`°, entre deux côtés d'au moins
    `min_side`, l'outil dépasse le sommet de `length`, fait une boucle
    tangente du côté extérieur du virage et revient sur le côté suivant,
    prolongé en arrière de `length` — la lame a pivoté hors de la matière.
    `accept(boucle)` peut refuser une boucle (matière, dessin touché) : elle
    est alors réduite de moitié, deux fois, puis omise. `turn_sign` : virages
    à gauche (1) ou à droite (-1) seulement — angles orientés (découpe : les
    angles extérieurs de la pièce). Rend la polyligne et le nombre de boucles."""
    pts = [tuple(p[:2]) for p in pts]
    if closed and len(pts) > 1 and math.dist(pts[0], pts[-1]) > 1e-9:
        pts = pts + [pts[0]]
    clean = [pts[0]] if pts else []
    for p in pts[1:]:
        if math.dist(p, clean[-1]) > 1e-9:
            clean.append(p)
    pts = clean
    if len(pts) < 3:
        return pts, 0

    def unit(a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1.0
        return dx / L, dy / L
    n = len(pts)
    idx = range(1, n - 1) if not closed else range(1, n)        # fermé : le sommet de départ (= dernier) aussi
    loops = {}
    for i in idx:
        a, b = pts[i - 1], pts[i]
        c = pts[i + 1] if i + 1 < n else pts[1]
        if math.dist(a, b) < min_side or math.dist(b, c) < min_side:
            continue
        u, v = unit(a, b), unit(b, c)
        cross = u[0] * v[1] - u[1] * v[0]
        turn = abs(math.degrees(math.atan2(cross, u[0] * v[0] + u[1] * v[1])))
        if not min_angle < turn < max_angle or (turn_sign and cross * turn_sign <= 0):
            continue
        for f in (1.0, 0.5, 0.25):
            e, k = length * f, 1.5 * radius * f
            A = (b[0] + u[0] * e, b[1] + u[1] * e)
            B = (b[0] - v[0] * e, b[1] - v[1] * e)
            c1 = (A[0] + u[0] * k, A[1] + u[1] * k)
            c2 = (B[0] - v[0] * k, B[1] - v[1] * k)
            loop = [b, A]
            for j in range(1, steps):
                t = j / steps
                s = 1 - t
                loop.append((s ** 3 * A[0] + 3 * s * s * t * c1[0] + 3 * s * t * t * c2[0] + t ** 3 * B[0],
                             s ** 3 * A[1] + 3 * s * s * t * c1[1] + 3 * s * t * t * c2[1] + t ** 3 * B[1]))
            loop += [B, b]
            if accept is None or accept(loop):
                loops[i] = loop
                break
    out = []
    for i, p in enumerate(pts):
        out.append(p)
        if i in loops:
            out += loops[i][1:]
    return out, len(loops)


def drag_knife_path(pts: list, closed: bool, offset: float, min_angle: float, steps_deg: float = 10.0) -> list:
    """Couteau flottant : la lame traîne à `offset` derrière l'axe. L'axe
    passe donc à `offset` en avant de la lame sur chaque segment ; à chaque
    angle vif il pivote autour du sommet (arc de rayon `offset`) pour que la
    lame s'oriente sans couper de travers."""
    if offset <= 0 or len(pts) < 2:
        return list(pts)
    pts = [tuple(p[:2]) for p in pts]
    if closed and math.dist(pts[0], pts[-1]) > 1e-9:
        pts = pts + [pts[0]]
    out = []

    def unit(a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1.0
        return dx / L, dy / L
    segs = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1) if math.dist(pts[i], pts[i + 1]) > 1e-9]
    for k, (a, b) in enumerate(segs):
        u = unit(a, b)
        start = (a[0] + u[0] * offset, a[1] + u[1] * offset)
        end = (b[0] + u[0] * offset, b[1] + u[1] * offset)
        if not out:
            out.append(a)                                   # la lame entre au départ, l'axe la suit
        if math.dist(out[-1], start) > 1e-9:
            out.append(start)
        out.append(end)
        nxt = segs[k + 1] if k + 1 < len(segs) else (segs[0] if closed else None)
        if nxt is None:
            continue
        v = unit(*nxt)
        turn = math.degrees(math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1]))
        if abs(turn) > min_angle:
            a0 = math.atan2(u[1], u[0])
            n = max(1, int(abs(turn) / steps_deg))
            for j in range(1, n + 1):
                t = a0 + math.radians(turn) * j / n
                out.append((b[0] + offset * math.cos(t), b[1] + offset * math.sin(t)))
    return out


def _edge_chamfer(doc, setup, op, tool, tp, em, here) -> None:
    """Chanfrein des bords (TypeEdit : gamme chanfrein) : la pointe de l'outil
    conique longe le bord (décalée de sa demi-troncature, du côté choisi),
    assez bas pour que le cône entame le dessus de la largeur voulue :
    profondeur = largeur / tan(demi-angle). Trous compris (côté intérieur)."""
    if tool.kind != 'conique' or not 0 < tool.angle < 180:
        tp.warnings.append('chanfrein : choisir un outil conique')
        return
    geoms = [g for it in source_items(doc, op) if (g := item_geometry(it))]
    tol = setup.tolerance
    reg = region(geoms, tol)
    if reg.is_empty:
        tp.warnings.append('chanfrein : aucun contour fermé')
        return
    width = max(0.0, getattr(op, 'chamfer_width', 0.3) or 0.3)
    tan_h = math.tan(math.radians(tool.angle) / 2)
    depth = width / tan_h
    if tool.tip / 2 + depth * tan_h > tool.body_diameter() / 2 + 1e-9:
        tp.warnings.append(f'chanfrein : largeur {width:g} mm trop grande pour l\'outil')
        return
    rt = tool.tip / 2
    side = op.side if op.side in ('exterieur', 'interieur') else 'exterieur'
    g = buffer_checked(reg, rt if side == 'exterieur' else -rt, _quad_segs(max(rt, tol), tol)) if rt > 0 else reg
    if g.is_empty:
        tp.warnings.append("chanfrein : forme trop petite pour la pointe de l'outil")
        return
    region_right = op.climb if side == 'exterieur' else not op.climb
    order = holes_first(g, region_right, here)
    for pts, closed in order:
        cut_chain(em, pts, closed, [-depth], ramp=op.ramp, ramp_angle=ramp_angle_of(op))
    tp.warnings.append(f'chanfrein : {width:g} mm à 45° de la face — pointe à {depth:.3f} mm'
                       if abs(tool.angle - 90) < 1e-6 else f'chanfrein : {width:g} mm — pointe à {depth:.3f} mm')


def _vinyl(doc, setup, op, tool, tp, em, here) -> None:
    """Découpe au couteau (TypeEdit : Vinyle) : tracé (le couteau suit le
    contour), asservi (il remonte et se réoriente aux angles vifs), flottant
    (l'axe compense le déport de la lame et pivote aux angles)."""
    geoms = [g for it in source_items(doc, op) if (g := item_geometry(it))]
    chains = order_chains(polylines(geoms, setup.tolerance), here)
    if not chains:
        tp.warnings.append('couteau : aucun trait à découper')
        return
    if tool.kind != 'couteau':
        tp.warnings.append('couteau : choisir un outil de type Couteau (déport de la lame = pointe)')
    zs = [op_levels(op, tool)[-1]]                          # une seule passe, à la profondeur
    mode = getattr(op, 'knife_mode', 'flottant')
    amin = float(getattr(op, 'knife_angle', 30.0) or 30.0)
    amax = float(getattr(op, 'knife_angle_max', 165.0) or 180.0)
    accept = None
    if mode == 'boucles' and getattr(op, 'loop_check', True):
        from shapely.geometry import LineString
        reg = region(geoms, setup.tolerance)
        lines = [LineString(p) for p, _c in chains if len(p) > 1]

        def accept(loop):                                   # ni dans la matière, ni sur le dessin
            body = LineString(loop[1:-1])
            if not reg.is_empty and body.intersects(reg.buffer(-1e-6)):
                return False
            return not any(body.intersects(L) for L in lines)
    nloops = 0
    for pts, closed in chains:
        if mode == 'boucles':
            path, k = corner_loops(pts, closed, amin, amax, float(getattr(op, 'loop_length', 5.5) or 0.0),
                                   float(getattr(op, 'loop_radius', 2.5) or 0.0),
                                   float(getattr(op, 'loop_min_side', 0.1) or 0.0), accept)
            nloops += k
            cut_chain(em, drag_knife_path(path, False, tool.tip, amin), False, zs, trace='meme_sens')
        elif mode == 'flottant':
            cut_chain(em, drag_knife_path(pts, closed, tool.tip, amin), False, zs, trace='meme_sens')
        elif mode == 'asservi':
            ring = list(pts) + ([pts[0]] if closed and math.dist(pts[0], pts[-1]) > 1e-9 else [])
            cuts = [i for i in knife_corners(ring, closed, amin) if i not in knife_corners(ring, closed, amax)]
            bounds = [0] + [i for i in cuts if i > 0] + [len(ring) - 1]
            for i0, i1 in zip(bounds, bounds[1:]):
                if i1 > i0:
                    em.retract()
                    cut_chain(em, ring[i0:i1 + 1], False, zs, trace='meme_sens')
        else:
            cut_chain(em, pts, closed, zs)
    if mode == 'boucles':
        tp.warnings.append(f'couteau : {nloops} boucle(s) aux angles')


def _passes(op) -> int:
    try:
        return max(1, min(100, int(getattr(op, 'laser_passes', 1) or 1)))
    except (TypeError, ValueError):
        return 1


def thicken(chains: list, width: float, step: float) -> list:
    """Trait élargi par passages parallèles (TauDrive) : chaque tracé est
    doublé de part et d'autre, à `step` puis 2 × `step`… jusqu'à la demi-
    épaisseur ; ce qui passe à moins d'un pas d'un passage déjà gardé est
    retiré (deux tracés voisins ne reçoivent pas deux fois l'énergie, ce
    qui brûlerait la matière). Rend [(points, fermé)]."""
    from shapely.geometry import LineString, MultiLineString, Polygon
    from shapely.ops import unary_union
    count = int(width / step / 2 + 1e-9) if width > 0 and step > 0 else 0
    if count <= 0:
        return list(chains)
    out = list(chains)
    kept = [LineString(pts) for pts, _c in chains if len(pts) >= 2]
    zone = unary_union(kept).buffer(step * 0.9, quad_segs=4) if kept else None
    for k in range(1, count + 1):
        added = []
        for pts, closed in chains:
            if len(pts) < 2:
                continue
            offsets = []
            for sign in (1, -1):
                try:
                    if closed and len(pts) >= 4:             # contour fermé : anneaux décalés, fermés
                        g = Polygon(pts).buffer(sign * k * step, join_style='mitre', mitre_limit=4.0)
                        for poly in getattr(g, 'geoms', [g]):
                            if not poly.is_empty:
                                offsets += [LineString(r.coords) for r in [poly.exterior, *poly.interiors]]
                    else:
                        offsets.append(LineString(pts).offset_curve(sign * k * step, join_style='mitre',
                                                                    mitre_limit=4.0))
                except Exception:                        # tracé dégénéré
                    continue
            for off in offsets:
                piece = off if zone is None or not off.intersects(zone) else off.difference(zone)
                for g in getattr(piece, 'geoms', [piece]):
                    if g.geom_type == 'LineString' and not g.is_empty and g.length > step:
                        added.append(g)
        for g in added:
            c = list(g.coords)
            out.append((c, math.dist(c[0], c[-1]) < 1e-9))
        if added:
            zone = unary_union([zone, MultiLineString(added).buffer(step * 0.9, quad_segs=4)]) if zone is not None \
                else MultiLineString(added).buffer(step * 0.9, quad_segs=4)
    return out


def _laser(doc, setup, op, tool, tp, em, here) -> None:
    geoms = [g for it in source_items(doc, op) if (g := item_geometry(it))]
    raw = polylines(geoms, setup.tolerance)
    width = getattr(op, 'line_width', 0.0) or 0.0
    if width > 0:
        step = getattr(op, 'line_step', 0.0) or 0.8 * (tool.diameter or 0.05)
        raw = thicken(raw, width, step)
    chains = order_chains(raw, here)
    chains = apply_starts(chains, start_marks(doc, op, setup.tolerance), max(10 * setup.tolerance, 0.01))[0]
    for _k in range(_passes(op)):                        # chaque passage repart du début du trait
        for pts, closed in chains:
            cut_chain(em, pts, closed, [0.0])


def cut_radius(op: Operation, tool: CamTool) -> float:
    """Rayon de l'outil pour décaler un détourage ou une poche : outil conique
    (ou boule) — rayon du cône au niveau de la matière quand la pointe est au
    fond (contour respecté en surface, par défaut), ou rayon de la pointe
    (contour respecté au fond) ; fraise droite : son rayon."""
    if getattr(op, 'contour_ref', 'surface') == 'fond' and tool.kind in ('conique', 'boule'):
        return tool.radius_at(1e-9) if tool.kind == 'conique' else 0.0
    return tool.radius_at(abs(op.depth)) if op.depth else tool.diameter / 2


def _contour(doc, setup, op, tool, tp, em, here, zs=None) -> None:
    if op.side == 'sur':
        _gravure(doc, setup, op, tool, tp, em, here)
        return
    geoms = [g for it in source_items(doc, op) if (g := item_geometry(it))]
    tol = setup.tolerance
    reg = region(geoms, tol)
    if reg.is_empty:
        tp.warnings.append('détourage : aucun contour fermé')
        return
    open_n = sum(1 for _p, closed in polylines(geoms, tol) if not closed)
    if open_n:
        tp.warnings.append(f'détourage : {open_n} contour(s) ouvert(s) ignoré(s)')
    r = cut_radius(op, tool) + op.stock + float(getattr(op, 'offset_add', 0.0) or 0.0)
    d = r if op.side == 'exterieur' else -r
    ext = op.side == 'exterieur'
    qs = _quad_segs(max(abs(r), tol), tol)
    ra = max(0.0, float(getattr(op, 'corner_round', 0.0) or 0.0))
    loops = bool(getattr(op, 'corner_loops', False)) and op.kind in ('contour', 'laser_decoupe') \
        and not getattr(op, 'common_line', False)
    if ra > 0:                                           # angles de la pièce arrondis en plus de l'outil
        base = reg.buffer(-ra if ext else ra, quad_segs=qs).buffer(ra if ext else -ra, quad_segs=qs)
        if not ext:
            base = keep_small_islands(tp, reg, base, ra, qs)
        path_geom = drop_splinters(base.buffer(d, quad_segs=qs), base, d, qs)
    elif loops:                                          # angles vifs : décalage à onglet, boucles ensuite
        path_geom = drop_splinters(reg.buffer(d, join_style=2, mitre_limit=5.0), reg, d, qs)
    else:
        path_geom = drop_splinters(reg.buffer(d, quad_segs=qs), reg, d, qs)
    if path_geom.is_empty:
        tp.warnings.append('détourage intérieur : outil trop gros pour la forme')
        return
    # avalant (broche horaire) : matière à droite de l'avance
    region_right = op.climb if op.side == 'exterieur' else not op.climb
    rings = [(pts, True) for pts in rings_of(path_geom, region_right)]
    if not getattr(op, 'common_line', False):
        check_contours(op, reg, path_geom, tp)
    order = holes_first(path_geom, region_right, here, getattr(op, 'small_first', False),
                        getattr(op, 'small_first_by', 'aire'), rank=drawing_rank(geoms, tol, abs(r)),
                        all_holes=getattr(op, 'holes_order', 'element') == 'tous')
    starts = start_marks(doc, op, tol)
    near = 3.0 * (abs(r) + ra) + 10 * tol                # le dessin est à un rayon de là, plus dans un angle rentrant
    order, fixed = apply_starts(order, starts, near, abs(r))
    if loops:
        order = _with_corner_loops(op, order, reg, abs(r), ext, region_right, tp)
    if zs is None:
        zs = op_levels(op, tool)
    lead = (getattr(op, 'lead_in', 0.0) or 0.0, getattr(op, 'lead_out', 0.0) or 0.0)
    own_leads = lead_marks(doc, op)                      # réglées contour par contour
    mine = marked_leads([p for p, _c in order], own_leads, near) if own_leads else {}
    leads_of = [mine.get(k, lead) for k in range(len(order))]
    pierce = max(0.0, float(getattr(op, 'lead_pierce', 0.0) or 0.0))
    lead_how = {'mode': getattr(op, 'lead_mode', 'arc'), 'angle_in': getattr(op, 'lead_angle', 45.0),
                'angle_out': getattr(op, 'lead_out_angle', 45.0), 'pierce': pierce,
                'transition': max(0.0, float(getattr(op, 'lead_transition', 0.0) or 0.0))}
    uncut = max(0.0, float(getattr(op, 'leave_uncut', 0.0) or 0.0))
    if uncut > 0:
        if any(a > 0 or b > 0 for a, b in leads_of):
            tp.warnings.append('matière restante : sortie tangente ignorée')
        if has_tabs(op):
            tp.warnings.append('matière restante : pontets ignorés')
        n_short = 0
        for (pts, _closed), (entry, _out) in zip(order, leads_of):
            if entry > 0:
                chain = with_leads(pts, path_geom, op.side == 'exterieur', entry, 0.0, keep_start=pts[0] in fixed, **lead_how)
                pierce_check([chain], reg, (entry, 0.0), pierce, tp)
                short = cut_short(chain, uncut)
            else:
                short = cut_short(pts, uncut)
            if len(short) < 2:
                n_short += 1
                continue
            cut_chain(em, short, False, zs, trace='meme_sens')
        if n_short:
            tp.warnings.append(f'matière restante : {n_short} contour(s) trop court(s), non usiné(s)')
        return
    # pontets posés à la main sur les formes (extra['tabs_xy']) : à leur place, des deux côtés
    manual = [tuple(p[:2]) for it in source_items(doc, op) for p in (getattr(it, 'extra', {}) or {}).get('tabs_xy', [])]
    tab_z = -(abs(op.depth) - op.tab_height) if has_tabs(op) or manual else None
    wtab = op.tab_width + tool.diameter
    tab_shape = getattr(op, 'tab_shape', 'droit')

    # le laser n'a pas de hauteur à laisser : ses pontets sont des micro-attaches
    tab_mode = 'pointille' if op.kind == 'laser_decoupe' else getattr(op, 'tab_mode', 'pont')
    gaps = tab_z is not None and tab_mode != 'pont'

    def cut_gaps(pts, closed, levels, tabs, **kw):
        """Un contour dont les pontets ne sont pas des hauteurs laissées."""
        if tabs:
            cut_dashes(em, pts, closed, levels, tabs, tab_mode)
        elif tab_mode == 'pointille':                    # trop court pour porter un pontet
            cut_chain(em, pts, closed, levels, **kw)

    def ring_tabs(pts):
        if tab_z is None:
            return None
        return manual_tab_intervals(pts, manual, wtab, abs(r) + wtab) if manual else tab_intervals(pts, tab_count(op, pts, wtab), wtab)

    # la finition passe ailleurs et part d'un autre point : ses pontets se calent sur ceux de l'ébauche, sinon rien ne
    # tient plus la pièce (le mur laissé par l'ébauche est détaché là où la finition le coupe)
    finish_near = 2 * (abs(op.stock) + abs(float(getattr(op, 'offset_add', 0.0) or 0.0))) + wtab
    if op.kind in ('laser_decoupe', 'contour') and any(a > 0 or b > 0 for a, b in leads_of):
        # entrée et sortie tangentes dans la chute : dehors pour un détourage
        # extérieur, dedans pour un intérieur (fraisage : sans rampe)
        marks = []
        chains = [with_leads(pts, path_geom, op.side == 'exterieur', *ld, keep_start=pts[0] in fixed or not any(ld), **lead_how)
                  for (pts, _closed), ld in zip(order, leads_of)]
        pierce_check(chains, reg, leads_of, pierce, tp)
        for (pts, _closed), chain in zip(order, chains):
            mine = tab_points(pts, ring_tabs(pts))
            marks += mine
            tabs = manual_tab_intervals(chain, mine, wtab, 1e-3) if mine else None
            if gaps:
                cut_gaps(chain, False, zs or [0.0], tabs)
                continue
            for z in (zs or [0.0]):                      # chaque passage repart de l'entrée
                cut_chain(em, chain, False, [z], tabs=tabs, tab_z=tab_z, tab_shape=tab_shape)
        if op.kind == 'laser_decoupe' or not (op.finish and op.stock > 0):
            return
        em.fin = True                                    # la passe de finition : à l'avance de finition
        fin = buffer_checked(reg, cut_radius(op, tool) if op.side == 'exterieur' else -cut_radius(op, tool),
                             _quad_segs(max(cut_radius(op, tool), tol), tol))
        rings, fixed = apply_starts([(p, True) for p in rings_of(fin, region_right, exteriors=keep_exteriors(op, reg))], starts, near,
                                    abs(cut_radius(op, tool)))
        mine = marked_leads([p for p, _c in rings], own_leads, near) if own_leads else {}
        for k, (pts, _closed) in enumerate(rings):
            ld = mine.get(k, lead)
            chain = with_leads(pts, fin, op.side == 'exterieur', *ld, keep_start=pts[0] in fixed or not any(ld), **lead_how)
            tabs = manual_tab_intervals(chain, marks, wtab, finish_near) if marks else None
            if gaps:
                cut_gaps(chain, False, [zs[-1]], tabs)
            else:
                cut_chain(em, chain, False, [zs[-1]], tabs=tabs, tab_z=tab_z, tab_shape=tab_shape)
        em.fin = False
        return
    tp.cycles = shape_cycles(doc, op, 'contour', abs(op.depth), op.step_down or tool.step_down, 0)
    if getattr(op, 'common_line', False) and op.side == 'exterieur':
        chains, shared = common_line_chains(reg, d, region_right, tol, here)
        if shared > 0:
            tp.warnings.append(f'découpe sur ligne commune : {shared:.1f} mm de bords partagés coupés une fois')
        for pts, closed in chains:
            tabs = (tab_intervals(pts, tab_count(op, pts, op.tab_width + tool.diameter), op.tab_width + tool.diameter)
                    if tab_z is not None and closed else None)
            cut_chain(em, pts, closed, zs, ramp=op.ramp, tabs=tabs, tab_z=tab_z, ramp_angle=ramp_angle_of(op),
                      tab_shape=getattr(op, 'tab_shape', 'droit'))
        return
    marks = []
    if getattr(op, 'trochoidal', False):
        _trochoidal_contour(op, tool, tp, em, reg, r, region_right, here, zs, tol, tab_z)
    elif getattr(op, 'chain_cut', False) and op.side == 'exterieur' and tab_z is None:
        _chain_cut(em, order, reg, abs(r), zs, tp)
    else:
        plan = [(pts, ring_tabs(pts)) for pts, closed in order]
        marks = [m for pts, tabs in plan for m in tab_points(pts, tabs)]
        connected = bool(getattr(op, 'link_passes', False))
        ramp = op.ramp or connected                      # passes connectées : descente en rampe
        lift = 'surface' if ramp and not connected else ''
        if gaps:
            for pts, tabs in plan:
                cut_gaps(pts, True, zs, tabs, ramp=ramp, ramp_angle=ramp_angle_of(op))
        elif getattr(op, 'pass_order', 'poche') == 'global' and len(zs) > 1 and len(plan) > 1:
            for zi, z in enumerate(zs):                  # chaque profondeur sur tous les contours
                for pts, tabs in plan:
                    cut_chain(em, pts, True, [z], ramp=ramp, tabs=tabs, tab_z=tab_z, ramp_angle=ramp_angle_of(op),
                              tab_shape=getattr(op, 'tab_shape', 'droit'), z_start=zs[zi - 1] if zi and not lift else 0.0)
        else:
            for pts, tabs in plan:
                cut_chain(em, pts, True, zs, ramp=ramp, tabs=tabs, tab_z=tab_z, ramp_angle=ramp_angle_of(op),
                          tab_shape=getattr(op, 'tab_shape', 'droit'), lift=lift)
    if op.finish and op.stock > 0:
        em.fin = True                                    # la passe de finition : à l'avance de finition
        fin = buffer_checked(reg, cut_radius(op, tool) if op.side == 'exterieur' else -cut_radius(op, tool),
                             _quad_segs(max(cut_radius(op, tool), tol), tol))
        rings = rings_of(fin, region_right, exteriors=keep_exteriors(op, reg))
        for pts, closed in apply_starts(order_chains([(p, True) for p in rings], em.pos), starts, near, abs(r))[0]:
            tabs = manual_tab_intervals(pts, marks, wtab, finish_near) if marks else None
            if gaps:
                cut_gaps(pts, True, [zs[-1]], tabs, ramp=op.ramp, ramp_angle=ramp_angle_of(op))
            else:
                cut_chain(em, pts, True, [zs[-1]], ramp=op.ramp, ramp_angle=ramp_angle_of(op), tab_z=tab_z, tab_shape=tab_shape,
                          tabs=tabs)
        em.fin = False


def trochoid(pts: list, radius: float, step: float, ccw: bool = True, tol: float = 0.01) -> list:
    """Parcours trochoïdal le long de la polyligne fermée `pts` : le centre
    suit le trait en avançant de `step` par boucle de rayon `radius`
    (anti-horaire si `ccw`). Le pas est ajusté pour un nombre entier de
    boucles : le parcours revient à son départ."""
    L = sum(math.dist(pts[i][:2], pts[i + 1][:2]) for i in range(len(pts) - 1))
    if L <= 1e-9 or radius <= 1e-9 or step <= 1e-9:
        return [tuple(p[:2]) for p in pts]
    loops = max(1, math.ceil(L / step))
    step = L / loops
    per = max(12, math.ceil(2 * math.pi / (2 * math.acos(max(-1.0, 1 - tol / radius)))))
    n = loops * per
    cum = [0.0]
    for i in range(len(pts) - 1):
        cum.append(cum[-1] + math.dist(pts[i][:2], pts[i + 1][:2]))
    sg = 1.0 if ccw else -1.0
    out, j = [], 0
    for k in range(n + 1):
        s = L * k / n
        while j < len(cum) - 2 and cum[j + 1] < s:
            j += 1
        seg = cum[j + 1] - cum[j]
        t = (s - cum[j]) / seg if seg > 1e-12 else 0.0
        a, b = pts[j], pts[j + 1]
        cx, cy = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        th = sg * 2 * math.pi * k / per
        out.append((cx + radius * math.cos(th), cy + radius * math.sin(th)))
    return out


def _trochoidal_contour(op, tool, tp, em, reg, r, region_right, here, zs, tol, tab_z) -> None:
    """Détourage trochoïdal : le centre des boucles suit le décalage à
    r + rayon de boucle, l'outil frôle le contour à chaque boucle — la
    rainure fait `troch_width` de large."""
    D = tool.diameter
    width = op.troch_width if op.troch_width > 0 else 1.5 * D
    rl = (width - D) / 2
    if rl <= tol:
        tp.warnings.append('détourage trochoïdal : rainure pas plus large que l\'outil — détourage simple')
        rl = 0.0
    step = op.troch_step if op.troch_step > 0 else 0.1 * D
    if tab_z is not None:
        tp.warnings.append('détourage trochoïdal : pontets ignorés')
    dd = abs(r) + rl
    qs_c = _quad_segs(max(dd, tol), tol)
    geom_c = drop_splinters(reg.buffer(dd if op.side == 'exterieur' else -dd, quad_segs=qs_c), reg, dd if op.side == 'exterieur' else -dd, qs_c)
    if geom_c.is_empty:
        tp.warnings.append('détourage trochoïdal : rainure trop large pour la forme')
        return
    rings = [(p, True) for p in rings_of(geom_c, region_right)]
    for pts, _closed in order_chains(rings, here):
        # boucles dans le sens de l'avalant : anti-horaire en avalant (broche horaire)
        cut_chain(em, trochoid(pts, rl, step, ccw=op.climb, tol=tol) if rl > 0 else pts, True, zs)


def manual_tab_intervals(pts: list, marks: list, width: float, near: float) -> list | None:
    """Pontets posés à la main : pour chaque repère (x, y) à moins de `near`
    du contour fermé `pts`, l'intervalle d'abscisse de largeur `width`
    centré sur son point le plus proche. None : aucun repère pour ce contour."""
    from shapely.geometry import LineString, Point
    ring = LineString([p[:2] for p in pts])
    L = ring.length
    out = []
    for m in marks:
        P = Point(m)
        if ring.distance(P) > near:
            continue
        s = ring.project(P)
        a, b = max(0.0, s - width / 2), min(L, s + width / 2)
        if b - a > 1e-9:
            out.append((a, b))
    return sorted(out) or None


def cut_short(pts: list, length: float) -> list:
    """Polyligne arrêtée `length` mm avant sa fin (matière restante) ; vide
    si elle n'est pas plus longue."""
    cum = _cum(pts)
    stop = cum[-1] - length
    if stop <= 1e-9:
        return []
    out = [pts[0]]
    for i in range(1, len(pts)):
        if cum[i] < stop - 1e-12:
            out.append(pts[i])
            continue
        a, b = pts[i - 1], pts[i]
        seg = cum[i] - cum[i - 1]
        t = (stop - cum[i - 1]) / seg if seg > 1e-12 else 1.0
        out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        break
    return out


def _ring_split(pts: list, p) -> tuple[list, list]:
    """Anneau fermé coupé au point `p` (sur l'anneau) : chemin du départ à
    `p`, et anneau repartant de `p`."""
    best, k = None, 0
    for i in range(len(pts) - 1):
        a, b = pts[i][:2], pts[i + 1][:2]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 < 1e-18 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
        d = math.dist((a[0] + t * dx, a[1] + t * dy), p)
        if best is None or d < best:
            best, k = d, i
    p = tuple(p[:2])
    return [q[:2] for q in pts[:k + 1]] + [p], [p] + [q[:2] for q in pts[k + 1:]] + [q[:2] for q in pts[1:k + 1]] + [p]


def _chain_cut(em, order, reg, r: float, zs: list, tp) -> None:
    """Découpe en chaîne (TypeEdit) : à chaque passe, l'outil va d'une pièce
    à la suivante en restant dans la matière — après le tour d'une pièce, il
    la longe jusqu'au point le plus proche de la suivante, puis la rejoint
    par un brin de la largeur de l'outil coupé dans la chute. Il ne remonte
    que si ce brin toucherait une pièce (trou vers son pourtour…)."""
    from shapely.geometry import LineString
    from shapely.ops import nearest_points
    keep = buffer_checked(reg, max(0.0, r - 1e-3))
    links = 0
    for z in zs:
        prev = None
        for pts, _closed in order:
            ring = [tuple(q[:2]) for q in pts]
            if len(ring) < 2:
                continue
            if math.dist(ring[0], ring[-1]) > 1e-9:
                ring.append(ring[0])
            linked = False
            if prev is not None and em.pos is not None and abs(em.pos[2] - z) < 1e-9:
                pa, pb = (g.coords[0] for g in nearest_points(LineString(prev), LineString(ring)))
                if math.dist(pa, pb) < 1e-9 or not LineString([pa, pb]).intersects(keep):
                    for q in _ring_split(prev, pa)[0][1:]:    # longe la pièce faite jusqu'au plus près
                        em.feed(q[0], q[1], z)
                    em.feed(pb[0], pb[1], z)                   # brin de liaison, sans remonter
                    ring = _ring_split(ring, pb)[1]
                    links += 1
                    linked = True
            if not linked:
                em.travel(*ring[0])
                em.plunge(z)
            for q in ring[1:]:
                em.feed(q[0], q[1], z)
            prev = ring
    tp.warnings.append(f'découpe en chaîne : {links} liaison(s) coupée(s) sans relever l\'outil')


def _with_corner_loops(op, order, reg, r: float, ext: bool, region_right: bool, tp) -> list:
    """Boucles aux angles extérieurs de la pièce (TypeEdit : Découpe, onglet
    Boucles) : l'outil prolonge l'arête, tourne hors de la pièce et revient
    sur l'arête suivante — l'angle reste vif et la vitesse tenue. Avec
    « Gérer les collisions », chaque boucle qui toucherait une pièce est
    réduite, ou omise."""
    from shapely.geometry import LineString
    keep = buffer_checked(reg, r - 1e-3) if ext else buffer_checked(reg, -(r - 1e-3))

    def accept(loop):
        body = LineString(loop[1:-1])
        return not body.intersects(keep) if ext else keep.contains(body)
    out, n = [], 0
    for pts, closed in order:
        path, k = corner_loops(pts, closed, float(op.loop_angle_min), float(op.loop_angle_max or 180.0),
                               float(op.loop_length or 0.0), float(op.loop_radius or 0.0),
                               float(op.loop_min_side or 0.0), accept if op.loop_check else None,
                               turn_sign=-1 if region_right == ext else 1)   # matière gardée à droite : virages à droite
        out.append((path, closed))
        n += k
    tp.warnings.append(f'découpe : {n} boucle(s) aux angles extérieurs')
    return out


def piece_size(p, by: str = 'aire') -> float:
    """Taille d'une pièce pour le tri des petites pièces (TypeEdit) : aire,
    périmètre extérieur, ou rayon du plus grand cercle inscrit (pièces
    étroites d'abord, même longues)."""
    if by == 'perimetre':
        return p.exterior.length
    if by == 'cercle':
        import shapely
        return shapely.maximum_inscribed_circle(p, max(1e-3, p.length / 2000)).length
    return p.area


def _solid_parts(geom) -> list:
    return [p for p in getattr(geom, 'geoms', [geom]) if p.geom_type == 'Polygon' and not p.is_empty]


def lost_parts(reg, paths) -> int:
    """Surfaces du dessin où le parcours n'a rien trouvé : l'outil n'y entre pas."""
    parts = _solid_parts(reg)
    if paths.is_empty:
        return len(parts)
    import shapely
    shapely.prepare(paths)
    return sum(1 for p in parts if not paths.intersects(p))


def keep_small_islands(tp, reg, base, ra: float, qs: int = 8):
    """Détourage intérieur aux angles arrondis : l'arrondi (fermeture de la région de `ra`) bouche les îles plus petites
    que lui, et l'outil passerait dessus. Elles sont gardées telles quelles (décision de l'utilisateur, round 902) :
    l'outil en fait le tour sans les arrondir. Le parcours `tp` les signale (avertissement et zones à montrer sur le
    dessin). Rend la région à usiner."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    kept = []
    for poly in getattr(reg, 'geoms', [reg]):
        if poly.geom_type != 'Polygon':
            continue
        for ring in poly.interiors:
            hole = Polygon(ring)
            if not hole.is_valid:
                hole = hole.buffer(0)
            if hole.is_empty or not hole.buffer(-ra, quad_segs=qs).is_empty:
                continue                                 # plus grande que l'arrondi : arrondie, pas bouchée
            island = hole.difference(reg)                # la matière de l'île (sans une pièce posée dedans)
            if island.is_empty or base.intersection(island).area < 0.5 * island.area:
                continue
            kept.append(island)
    if not kept:
        return base
    tp.warnings.append(f'détourage intérieur : {len(kept)} île(s) plus petite(s) que l\'arrondi des angles ({ra:g} mm), '
                       'gardée(s) telle(s) quelle(s) — l\'outil en fait le tour sans les arrondir')
    for k in kept:
        for g in getattr(k, 'geoms', [k]):
            if g.geom_type == 'Polygon' and not g.is_empty:
                tp.zones.append({'kind': 'ile', 'pts': [[round(x, 4), round(y, 4)] for x, y in g.exterior.coords]})
    return base.difference(unary_union(kept))


def check_contours(op, reg, paths, tp) -> None:
    """TypeEdit avertit dès que le nombre de trajectoires d'une passe diffère du nombre de contours : un contour ou une
    portion n'a pas pu être découpé, parce que l'outil est trop gros par exemple. Sans cela, il manque au programme un
    morceau du dessin et personne ne le sait."""
    parts, done = _solid_parts(reg), _solid_parts(paths)
    if op.side == 'exterieur':
        if len(done) < len(parts):
            tp.warnings.append(f'détourage : {len(parts) - len(done)} pièce(s) trop proche(s) de leur voisine — '
                               'détourées ensemble, sans couper entre elles (voir « Découpe sur ligne commune »)')
            return
    else:
        lost = lost_parts(reg, paths)
        if lost:
            tp.warnings.append(f'détourage intérieur : {lost} contour(s) plus étroit(s) que l\'outil, non usiné(s)')
            return
    theory, real = (sum(1 + len(p.interiors) for p in g) for g in (parts, done))
    if theory != real:
        tp.warnings.append(f'détourage : {real} trajectoire(s) par passe pour {theory} contour(s) — '
                           'l\'outil ne passe pas partout')


def drawing_rank(geoms: list, tol: float, reach: float = 0.0):
    """Tri manuel (TypeEdit : selon l'ordre de sélection ou de création) : la fonction qui donne à un anneau calculé le
    rang, dans le dessin, du contour dont il vient, celui qui le suit de plus près. None en tri automatique."""
    if not _DRAWING_ORDER.get():
        return None
    import shapely
    from shapely.geometry import LineString
    lines = [LineString([p[:2] for p in pts]) for pts, _closed in polylines(geoms, tol)]
    if not lines:
        return None
    tree = shapely.STRtree(lines)

    def rank(ring) -> int:
        line = LineString([p[:2] for p in ring])
        near = tree.query(line, predicate='dwithin', distance=reach + 10 * tol)
        near = sorted(int(i) for i in near) if len(near) else [int(tree.nearest(line))]
        return min(near, key=lambda i: round(line.hausdorff_distance(lines[i]), 6))
    return rank


def holes_first(geom, region_right: bool, here=(0.0, 0.0), small_first: bool = False, by: str = 'aire',
                *, rank=None, all_holes: bool = False) -> list:
    """Anneaux d'un détourage dans un ordre sûr : pièce par pièce (au plus
    proche, ou les plus petites d'abord), les trous de chaque pièce avant
    son tour — la pièce reste tenue tant que ses trous ne sont pas coupés.
    `rank` (tri manuel, `drawing_rank`) : pièces et trous dans l'ordre du dessin.
    `all_holes` (TypeEdit : tous les contours intérieurs puis les extérieurs) :
    les trous de toutes les pièces, puis les tours de toutes les pièces."""
    parts = _solid_parts(geom)
    if rank is not None:
        parts.sort(key=lambda p: rank(p.exterior.coords))
    elif not small_first:
        parts = _nearest_first(parts, here)
    if small_first:
        parts.sort(key=lambda p: piece_size(p, by))     # tri stable : à taille égale, l'ordre du dessin
    out, pos = [], here
    every_hole, every_outer = [], []
    for p in parts:
        holes = [(pts, True) for pts in rings_of(p, region_right, exteriors=False)]
        outer = [(pts, True) for pts in rings_of(p, region_right) if pts not in [h for h, _c in holes]]
        if rank is not None:
            holes.sort(key=lambda c: rank(c[0]))
        if all_holes:
            every_hole += holes
            every_outer += outer[:1]
            continue
        for pts, c in order_chains(holes, pos) + order_chains(outer[:1], pos):
            out.append((pts, c))
            pos = pts[-1][:2]
    if all_holes:
        if rank is not None:
            every_hole.sort(key=lambda c: rank(c[0]))
        for pts, c in order_chains(every_hole, pos):
            out.append((pts, c))
            pos = pts[-1][:2]
        for pts, c in every_outer if small_first else order_chains(every_outer, pos):
            out.append((pts, c))
            pos = pts[-1][:2]
    return out


def _nearest_first(polys, here=(0.0, 0.0)) -> list:
    """Polygones au plus proche : de `here`, le bord extérieur le plus
    proche, puis du centre de celui-ci, et ainsi de suite. Distances
    calculées d'un coup par shapely (un dessin de 400 pièces : 80 000 points
    créés un à un auparavant)."""
    import numpy as np
    import shapely
    rest, out, pos = list(polys), [], tuple(here[:2])
    rings = [p.exterior for p in rest]
    while rest:
        k = int(np.argmin(shapely.distance(np.asarray(rings, dtype=object), _shp_point(pos))))
        rings.pop(k)
        out.append(rest.pop(k))
        c = out[-1].centroid
        pos = (c.x, c.y)
    return out


def _shp_point(p):
    from shapely.geometry import Point
    return Point(p[0], p[1])


def common_line_chains(reg, d: float, region_right: bool, tol: float, here=(0.0, 0.0)):
    """Découpe sur ligne commune : chaque pièce de la région décalée de `d`
    à part (deux pièces écartées d'un diamètre d'outil gardent leur bord
    commun), pièces prises au plus proche ; un tronçon déjà coupé par une
    pièce voisine n'est pas recoupé — la pièce suivante n'en garde que le
    reste, en morceaux ouverts. Rend ([(points, fermé)], longueur partagée)."""
    from shapely.geometry import LineString
    parts = [p for p in getattr(reg, 'geoms', [reg]) if p.geom_type == 'Polygon' and not p.is_empty]
    rings = []
    for p in parts:
        g = buffer_checked(p, d, _quad_segs(max(abs(d), tol), tol))
        rings += [(pts, True) for pts in rings_of(g, region_right)]
    eps = max(2 * tol, 0.01)
    done = None
    out, shared = [], 0.0
    for pts, _closed in order_chains(rings, here):
        ring = list(pts) + ([pts[0]] if pts[0] != pts[-1] else [])
        line = LineString(ring)
        rest = line if done is None else line.difference(done)
        if rest.is_empty:
            shared += line.length
        elif done is None or rest.length >= line.length - eps:
            out.append((pts, True))
        else:
            shared += line.length - rest.length
            pieces = [list(g.coords) for g in getattr(rest, 'geoms', [rest]) if g.length > eps]
            # un morceau coupé au départ de l'anneau : recollé à celui de la fin
            if len(pieces) > 1 and math.dist(pieces[0][0], ring[0]) < 1e-9 and math.dist(pieces[-1][-1], ring[-1]) < 1e-9:
                pieces[0] = pieces[-1] + pieces[0][1:]
                pieces.pop()
            out += [(pc, False) for pc in pieces]
        bl = line.buffer(eps)
        done = bl if done is None else done.union(bl)
    return out, shared


def helix_entry(em: Emitter, p0, z_from: float, z: float, radius: float, angle: float, inside,
                ccw: bool = True) -> bool:
    """Descente en hélice de rayon `radius` jusqu'à `z`, sur un cercle qui
    passe par `p0` (départ de l'anneau) et reste dans la zone permise
    (`inside`), puis retour à `p0` au fond. False (rien d'émis) si aucun
    cercle ne tient : rampe ou plongée à la place."""
    from shapely.geometry import LineString
    if radius <= 1e-9:
        return False
    for k in range(8):                                   # 8 centres essayés autour du départ
        a = math.pi / 4 * k
        c = (p0[0] + radius * math.cos(a), p0[1] + radius * math.sin(a))
        circle = [(c[0] + radius * math.cos(a + math.pi + t * math.pi / 18),
                   c[1] + radius * math.sin(a + math.pi + t * math.pi / 18)) for t in range(37)]
        if not inside(LineString(circle)):
            continue
        em.travel(p0[0], p0[1])
        em.plunge(z_from)
        pitch = 2 * math.pi * radius * math.tan(math.radians(angle))
        end = _helix(em, c[0], c[1], radius, z_from, z, pitch, ccw, a0=a + math.pi)
        _helix(em, c[0], c[1], radius, z, z, 1.0, ccw, a0=end)       # un tour à plat au fond (pas de cône)
        em.feed(p0[0], p0[1], z)
        return True
    return False


def mill_rings(em: Emitter, order: list, zs: list[float], allowed, ramp_angle: float | None = None,
               inside=None, helix: float = 0.0, only=None, link_angle: float | None = None) -> None:
    """Anneaux de centres d'outil usinés à chaque cote de `zs` ; d'un anneau
    au suivant, liaison au fond si le trajet reste dans `allowed` (le
    centre de l'outil n'y entame pas les bords), sinon par le dégagement —
    puis plongée, ou rampe le long de l'anneau si `ramp_angle`. `inside` :
    test déjà préparé (`within_test(allowed)`), pour des appels répétés.
    `only` : rangs des cotes à faire (ordre global : une cote à la fois) ;
    `link_angle` : passes connectées — d'une cote à la suivante, l'outil
    reste dans la matière et descend en rampe à cet angle."""
    from shapely.geometry import LineString
    inside = inside or within_test(allowed)
    for zi, z in enumerate(zs):
        if only is not None and zi not in only:
            continue
        here_pt = em.pos
        for ri, pts in enumerate(order):
            if ri % 16 == 0:
                progress.step(zi * len(order) + ri, len(zs) * len(order))
            pts = _start_nearest(pts, True, here_pt)
            if em.pos is not None and em.pos[2] <= z + 1e-9 and \
                    inside(LineString([em.pos[:2], pts[0][:2]])):
                em.feed(pts[0][0], pts[0][1], z)               # liaison dans la poche, sans remonter
            elif link_angle and em.pos is not None and em.pos[2] > z + 1e-9 and em.pos[2] < 0.0 and \
                    inside(LineString([em.pos[:2], pts[0][:2]])):
                z_here = em.pos[2]                            # passe connectée : on reste dans la matière
                em.feed(pts[0][0], pts[0][1], z_here)
                _ramp_closed(em, pts, z_here, z, link_angle)
                here_pt = em.pos
                continue
            else:
                if ramp_angle and helix > 0 and helix_entry(em, pts[0], zs[zi - 1] if zi else 0.0, z, helix,
                                                            ramp_angle, inside):
                    for p in pts[1:]:
                        em.feed(p[0], p[1], z)
                    here_pt = em.pos
                    continue
                em.travel(*pts[0][:2])
                if ramp_angle:
                    _ramp_closed(em, pts, zs[zi - 1] if zi else 0.0, z, ramp_angle)
                    here_pt = em.pos
                    continue
                em.plunge(z)
            for p in pts[1:]:
                em.feed(p[0], p[1], z)
            here_pt = em.pos


def corner_spurs(pts: list, step: float, max_angle: float, inside, min_len: float = 0.0) -> tuple[list, int]:
    """Optimisation des angles (TypeEdit) : à chaque coin saillant d'un
    anneau plus fermé que `max_angle`, un aller-retour sur la bissectrice
    vers l'angle de la forme, de longueur pas × (1/sin(θ/2) − 1) — la
    matière qu'un pas large laisse entre deux anneaux dans un angle aigu ;
    raccourci (moitié, quart) tant qu'il sort de la zone permise (`inside`).
    `min_len` : pas de reprise plus courte (les sommets d'un arc aplati)."""
    from shapely.geometry import LineString
    ring = [tuple(p[:2]) for p in pts]
    closed = len(ring) > 3 and math.dist(ring[0], ring[-1]) < 1e-9
    core = ring[:-1] if closed else ring
    n = len(core)
    if n < 3:
        return pts, 0
    area2 = sum(core[i - 1][0] * core[i][1] - core[i][0] * core[i - 1][1] for i in range(n))
    out, k = [], 0
    for i in range(n):
        p = core[i]
        out.append(p)
        a, b = core[i - 1], core[(i + 1) % n]
        u = (p[0] - a[0], p[1] - a[1])
        v = (b[0] - p[0], b[1] - p[1])
        lu, lv = math.hypot(*u), math.hypot(*v)
        if lu < 1e-9 or lv < 1e-9:
            continue
        cross = u[0] * v[1] - u[1] * v[0]
        if cross * area2 <= 0:                               # coin rentrant de l'anneau : rien à chercher
            continue
        theta = math.pi - math.acos(max(-1.0, min(1.0, (u[0] * v[0] + u[1] * v[1]) / (lu * lv))))
        if math.degrees(theta) >= max_angle or theta < 1e-3:
            continue
        back, fwd = (-u[0] / lu, -u[1] / lu), (v[0] / lv, v[1] / lv)
        bx, by = back[0] + fwd[0], back[1] + fwd[1]
        bn = math.hypot(bx, by)
        if bn < 1e-9:
            continue
        out_dir = (-bx / bn, -by / bn)                       # vers la pointe de l'angle
        L = step * (1 / math.sin(theta / 2) - 1)
        if L < min_len:
            continue
        for f in (1.0, 0.5, 0.25):
            q = (p[0] + out_dir[0] * L * f, p[1] + out_dir[1] * L * f)
            if inside(LineString([p, q])):
                out += [q, p]
                k += 1
                break
    if closed:
        out.append(out[0])
    return out, k


def spiral_path(rings: list, maxlen: float) -> list:
    """Anneaux emboîtés successifs (fermés, même sens) changés en une spirale :
    sur chaque tour, le point glisse peu à peu vers l'anneau suivant (au plus
    proche), sans plongée entre deux tours ; le premier et le dernier anneaux
    faits en entier (parti aussitôt vers le suivant, le premier tour laissait
    de la matière : au centre, ou le long du bord en partant du bord)."""
    from shapely.geometry import LineString, Point
    out = []
    for i, ring in enumerate(rings):
        ring = _start_nearest(list(ring), True, out[-1] if out else None)
        if i == len(rings) - 1:
            out += [tuple(p[:2]) for p in ring]
            break
        if i == 0:
            out += [tuple(p[:2]) for p in ring]
        dense = [tuple(ring[0][:2])]
        for p in ring[1:]:
            a = dense[-1]
            n = max(1, int(math.ceil(math.dist(a, p[:2]) / maxlen)))
            dense += [(a[0] + (p[0] - a[0]) * k / n, a[1] + (p[1] - a[1]) * k / n) for k in range(1, n + 1)]
        L = [0.0]
        for a, b in zip(dense, dense[1:]):
            L.append(L[-1] + math.dist(a, b))
        total = L[-1] or 1.0
        nxt = LineString(rings[i + 1])
        for p, s in zip(dense[:-1], L[:-1]):
            f = s / total
            q = nxt.interpolate(nxt.project(Point(p)))
            out.append((p[0] * (1 - f) + q.x * f, p[1] * (1 - f) + q.y * f))
    return out


def spiral_groups(reg, shells: list, region_right: bool, outside_in: bool, step: float, inside) -> list[list]:
    """Par forme de la région : ses passes concentriques, les suites de
    retraits d'un seul contour sans trou changées en spirales (contrôlées
    dans la zone permise `inside`, sinon gardées en anneaux) ; [(points, fermé)]."""
    from shapely.geometry import LineString
    parts = [p for p in getattr(reg, 'geoms', [reg]) if p.geom_type == 'Polygon' and not p.is_empty]
    out = []
    for part in parts:
        seq = []
        for s in shells:
            g = s.intersection(part)
            polys = [p for p in getattr(g, 'geoms', [g]) if p.geom_type == 'Polygon' and not p.is_empty]
            if polys:
                seq.append(polys)
        if not outside_in:
            seq = seq[::-1]
        chains, run = [], []

        def flush():
            if len(run) >= 2:
                sp = spiral_path(run, max(0.05, step / 2))
                if inside(LineString(sp)):
                    chains.append((sp, False))
                    run.clear()
                    return
            chains.extend((r, True) for r in run)
            run.clear()
        for polys in seq:
            if len(polys) == 1 and not polys[0].interiors:
                run.append(rings_of(polys[0], region_right)[0])
            else:
                flush()
                for p in polys:
                    chains.extend((r, True) for r in rings_of(p, region_right))
        flush()
        if chains:
            out.append(chains)
    return out


def _order_chain_groups(groups: list[list], here) -> list[list]:
    if len(groups) <= 1:
        return groups
    marks = [([(g[0][0][0][0], g[0][0][0][1], i)], False) for i, g in enumerate(groups)]
    return [groups[c[0][0][2]] for c in order_chains(marks, here)]


def stay_down_length(op, tool, clear: float, z: float, ramp_angle: float | None = None) -> float:
    """Longueur de liaison jusqu'à laquelle rester au fond va plus vite que remonter : la liaison se fait à l'avance
    de coupe, la remontée coûte une plongée depuis la hauteur d'approche `clear` jusqu'à `z` (les rapides ne sont pas
    comptés) — ou la descente en hélice (`ramp_angle`), plus longue. Jamais moins que le diamètre de l'outil.
    `z` : la cote de la première passe (une limite qui grandirait avec la profondeur laisserait passer plus bas une
    liaison refusée en haut, à travers ce que les passes du dessus n'ont pas ouvert)."""
    feed, plunge, _spindle = _feeds(op, tool)
    hop = (clear - z) * feed / plunge if feed > 0 and plunge > 0 else 0.0
    if ramp_angle and 0.0 < ramp_angle < 90.0:
        hop = max(hop, abs(z) / math.tan(math.radians(ramp_angle)))
    return max(float(tool.diameter or 0.0), hop)


def mill_chains(em: Emitter, chains: list, zs: list[float], inside, ramp_angle: float | None = None,
                helix: float = 0.0, only=None, max_link=None) -> None:
    """Anneaux (fermés) et spirales (ouvertes) usinés à chaque cote, liés au
    fond quand le trajet reste dans la zone permise ; descente en hélice
    (`helix` : rayon, `ramp_angle`) quand il faut redescendre. `only` :
    rangs des cotes à faire (ordre global). `max_link(z)` : longueur de liaison au-delà de laquelle l'outil remonte
    au lieu de rester au fond ; il n'y reste alors que s'il est déjà à la cote de la passe (pas plus bas). Venant
    de la passe du dessus, à moins de cette longueur et sans rampe réglée : il rejoint le départ à sa cote, puis
    descend d'une passe, sans remonter au dégagement."""
    from shapely.geometry import LineString
    for zi, z in enumerate(zs):
        if only is not None and zi not in only:
            continue
        for pts, closed in chains:
            if closed:
                pts = _start_nearest(pts, True, em.pos)
            near = max_link is None or (em.pos is not None and em.pos[2] >= z - 1e-9 and
                                        math.dist(em.pos[:2], pts[0][:2]) <= max_link(z))
            if near and em.pos is not None and em.pos[2] <= z + 1e-9 and \
                    inside(LineString([em.pos[:2], pts[0][:2]])):
                em.feed(pts[0][0], pts[0][1], z)
            elif near and not ramp_angle and max_link is not None and z + 1e-9 < em.pos[2] < -1e-9 and \
                    (math.dist(em.pos[:2], pts[0][:2]) < 1e-9 or inside(LineString([em.pos[:2], pts[0][:2]]))):
                em.feed(pts[0][0], pts[0][1], em.pos[2])       # la passe du dessus, tout près : sans remonter
                em.plunge(z)
            elif ramp_angle and helix > 0 and helix_entry(em, pts[0], zs[zi - 1] if zi else 0.0, z, helix,
                                                          ramp_angle, inside):
                pass
            else:
                em.travel(*pts[0][:2])
                em.plunge(z)
            for p in pts[1:]:
                em.feed(p[0], p[1], z)


def _pass_plan(op, zs: list, groups: list) -> list:
    """Ordre des passes multiples : [(rangs des cotes, rang du groupe,
    groupe)] — poche par poche (chaque poche jusqu'au fond, par défaut) ou
    global (chaque profondeur sur toutes les poches)."""
    if getattr(op, 'pass_order', 'poche') == 'global' and len(zs) > 1 and len(groups) > 1:
        return [([zi], gi, g) for zi in range(len(zs)) for gi, g in enumerate(groups)]
    return [(None, gi, g) for gi, g in enumerate(groups)]


def shape_groups(reg, shells: list, region_right: bool) -> list[list]:
    """Anneaux de retraits successifs (`shells`, du bord vers le centre)
    rangés par forme de la région : pour chaque partie, ses anneaux du
    centre vers le bord. Chaque polygone d'un retrait est rattaché à la
    partie qui contient son premier point (un retrait reste dans sa forme).
    Une seule forme : l'ordre d'avant, à l'identique."""
    parts = [p for p in getattr(reg, 'geoms', [reg]) if p.geom_type == 'Polygon' and not p.is_empty]
    if len(parts) <= 1:
        return [[pts for s in reversed(shells) for pts in rings_of(s, region_right)]]
    import shapely
    tree = shapely.STRtree(parts)
    groups: list[list] = [[] for _ in parts]
    for s in reversed(shells):
        polys = [p for p in getattr(s, 'geoms', [s]) if p.geom_type == 'Polygon' and not p.is_empty]
        if not polys:
            continue
        src, dst = tree.query(shapely.points([p.exterior.coords[0] for p in polys]), predicate='intersects')
        owner: dict = {}
        for i, j in zip(src.tolist(), dst.tolist()):
            owner.setdefault(i, j)
        for i, p in enumerate(polys):
            groups[owner.get(i, 0)].extend(rings_of(p, region_right))
    return [g for g in groups if g]


def part_rings(reg, geoms: list, region_right: bool, exteriors=True) -> list[list]:
    """Anneaux de géométries successives (passes) rangés par forme de la
    région : pour chaque partie, [(indice de la géométrie, anneaux)] dans
    l'ordre des géométries ; chaque polygone rattaché à la partie qui
    contient son premier point. Une seule forme : tout dans un groupe.
    `exteriors` : celui de rings_of, ou une liste (un par géométrie)."""
    parts = [p for p in getattr(reg, 'geoms', [reg]) if p.geom_type == 'Polygon' and not p.is_empty]
    each = exteriors if isinstance(exteriors, list) else [exteriors] * len(geoms)
    if len(parts) <= 1:
        return [[(k, rings_of(g, region_right, exteriors=each[k])) for k, g in enumerate(geoms)]]
    import shapely
    tree = shapely.STRtree(parts)
    groups: list[list] = [[] for _ in parts]
    for k, g in enumerate(geoms):
        polys = [p for p in getattr(g, 'geoms', [g]) if p.geom_type == 'Polygon' and not p.is_empty]
        if not polys:
            continue
        src, dst = tree.query(shapely.points([p.exterior.coords[0] for p in polys]), predicate='intersects')
        owner: dict = {}
        for i, j in zip(src.tolist(), dst.tolist()):
            owner.setdefault(i, j)
        mine: dict = {}
        for i, p in enumerate(polys):
            mine.setdefault(owner.get(i, 0), []).extend(rings_of(p, region_right, exteriors=each[k]))
        for j, rings in mine.items():
            groups[j].append((k, rings))
    return [g for g in groups if g]


def nested_rings(reg, geoms: list, region_right: bool, exteriors=True, here=None) -> list[list]:
    """Comme part_rings, pour des retraits successifs usinés du centre vers le bord, dans l'ordre relevé dans TE13 : chaque polygone après ceux
    qu'il contient, une branche finie avant la suivante. Quatre coins qui restent au-delà de l'axe d'une bande ne sont plus parcourus tour à tour
    à chaque retrait. Rend, pour chaque partie de la région, [(indice de la géométrie, anneaux)] dans l'ordre d'usinage."""
    import numpy as np
    import shapely
    each = exteriors if isinstance(exteriors, list) else [exteriors] * len(geoms)
    levels = [[p for p in getattr(g, 'geoms', [g]) if p.geom_type == 'Polygon' and not p.is_empty] for g in geoms]
    kids: dict = {}
    roots: list = []
    prev_k, prev_tree = None, None
    for k, polys in enumerate(levels):
        if not polys:
            continue
        if prev_tree is None:
            roots += [(k, i) for i in range(len(polys))]
        else:
            src, dst = prev_tree.query(shapely.points([p.exterior.coords[0] for p in polys]), predicate='intersects')
            parent: dict = {}
            for a, b in zip(src.tolist(), dst.tolist()):
                parent.setdefault(a, b)
            for i in range(len(polys)):
                if i in parent:
                    kids.setdefault((prev_k, parent[i]), []).append((k, i))
                else:
                    roots.append((k, i))
        prev_k, prev_tree = k, shapely.STRtree(polys)
    parts = [p for p in getattr(reg, 'geoms', [reg]) if p.geom_type == 'Polygon' and not p.is_empty]
    by_part: dict = {}
    if len(parts) <= 1:
        by_part[0] = roots
    elif roots:
        src, dst = shapely.STRtree(parts).query(shapely.points([levels[k][i].exterior.coords[0] for k, i in roots]), predicate='intersects')
        owner: dict = {}
        for a, b in zip(src.tolist(), dst.tolist()):
            owner.setdefault(a, b)
        for n, node in enumerate(roots):
            by_part.setdefault(owner.get(n, 0), []).append(node)

    def nearest(pts, pos):
        c = np.asarray(pts)[:, :2]
        d = np.sum((c - pos) ** 2, axis=1)
        i = int(np.argmin(d))
        return float(d[i]), c[i]

    groups = []
    for j in sorted(by_part):
        if not by_part[j]:
            continue
        out = []
        pos = np.array(here[:2], dtype=float) if here is not None else np.array(levels[by_part[j][0][0]][by_part[j][0][1]].exterior.coords[0][:2], dtype=float)
        stack = [[(None, None), list(by_part[j])]]
        while stack:
            node, rest = stack[-1]
            if rest:
                pick = 0
                if len(rest) > 1:
                    pick = min(range(len(rest)), key=lambda t: nearest(levels[rest[t][0]][rest[t][1]].exterior.coords, pos)[0])
                child = rest.pop(pick)
                stack.append([child, list(kids.get(child, ()))])
                continue
            stack.pop()
            if node[0] is None:
                continue
            rings = rings_of(levels[node[0]][node[1]], region_right, exteriors=each[node[0]])
            placed = []
            while rings:                                  # dans le polygone : l'anneau le plus près d'abord
                pick = min(range(len(rings)), key=lambda t: nearest(rings[t], pos)[0])
                ring = rings.pop(pick)
                pos = nearest(ring, pos)[1]
                placed.append(ring)
            if placed:
                out.append((node[0], placed))
        groups.append(out)
    return groups


def order_groups(groups: list[list], here) -> list[list]:
    """Groupes d'anneaux pris au plus proche voisin (départ de leur premier
    anneau), depuis `here`."""
    if len(groups) <= 1:
        return groups
    marks = [([(g[0][0][0], g[0][0][1], i)], False) for i, g in enumerate(groups)]
    return [groups[c[0][0][2]] for c in order_chains(marks, here)]


def concentric(geom, step: float, tol: float, limit: int = 10000) -> list:
    """Région de centres d'outil et ses retraits successifs de `step` (chacun
    pris sur la région d'origine), du bord vers le centre."""
    if geom.is_empty:
        return []
    qs = _quad_segs(max(step, tol), tol)
    from ..core import workers
    return workers.pmap(lambda g: simplify_parts(g, tol / 2), erosions(geom, [k * step for k in range(limit)], qs))


def inscribed_radii(geom, tol: float = 0.01):
    """(parties polygonales de la région, rayon du plus grand disque qui
    tient dans chacune, majoré de 2 × `tol`) : un retrait plus grand que le
    rayon d'une partie la fait disparaître. Rayons None si incalculables."""
    import shapely
    parts = shapely.get_parts(geom)
    parts = parts[(shapely.get_type_id(parts) == 3) & ~shapely.is_empty(parts)]
    try:
        radii = shapely.length(shapely.maximum_inscribed_circle(parts, tol)) + 2 * tol if len(parts) else []
    except Exception:                                    # shapely sans cercle inscrit, géométrie exotique
        radii = None
    return parts, radii


def inscribed_radius(geom, tol: float = 0.01) -> float:
    """Rayon du plus grand disque qui tient dans la région (majoré) : tout
    retrait plus grand est vide. Infini si incalculable."""
    _parts, radii = inscribed_radii(geom, tol)
    if radii is None:
        return math.inf
    return float(max(radii)) if len(radii) else 0.0


def erosions(geom, dists, qs: int) -> list:
    """Retraits successifs de `geom` aux distances croissantes `dists`
    (0 : la région elle-même), jusqu'au premier vide exclu ; calculés par
    paquets sur les fils de calcul (core.workers), tous pris sur `geom`.
    Seules les parties assez larges pour un retrait sont retirées (les
    lettres fines d'un grand dessin disparaissent dès les premiers ; un
    retrait au-delà du vide, lent, n'est jamais demandé)."""
    import shapely
    from ..core import workers
    parts, radii = inscribed_radii(geom)
    if radii is None:
        def at(d):
            return erode(geom, d, qs)
        reach = math.inf
    else:
        reach = float(max(radii)) if len(radii) else 0.0

        def at(d):                                       # parties disjointes : retrait de la réunion = réunion des retraits
            alive = parts[radii > d]
            if len(alive) == 0:
                return _polys(alive)
            return _erode_parts(alive, d, qs)
    out = []
    dists = [d for d in dists if d < reach]
    batch = max(1, workers.count())
    for i in range(0, len(dists), batch):
        progress.check()
        part = workers.pmap(lambda d: geom if d <= 0 else at(d), dists[i:i + batch])
        for g in part:
            if g.is_empty:
                return out
            out.append(g)
    return out


def ramp_floor(em: Emitter, rings: list, allowed, z_from: float, z: float, angle: float) -> None:
    """Entrée dans un fond, relevée dans TE13 : en rampe le long de ses anneaux, aller et retour, pour revenir au départ à la cote z. Chemin trop court
    pour que la rampe ait un sens (plus de 16 allers-retours) : rien, l'outil plongera."""
    from shapely.geometry import LineString
    inside = within_test(allowed)
    spts = [tuple(p[:2]) for p in _start_nearest(rings[0], True, em.pos)]
    for pts in rings[1:]:
        pts = _start_nearest(pts, True, spts[-1])
        if not inside(LineString([spts[-1], pts[0][:2]])):
            break
        spts.extend(tuple(p[:2]) for p in pts)
    sabs = _cum(spts)
    if sabs[-1] * 32 < (z_from - z) / math.tan(math.radians(angle)):
        return
    if em.pos is not None and em.pos[2] <= z_from + 1e-9 and inside(LineString([em.pos[:2], spts[0]])):
        em.feed(spts[0][0], spts[0][1], em.pos[2])
    else:
        em.travel(*spts[0])
    _ramp_open(em, spts, sabs, z_from, z, angle, walk=False)


def rings_by_piece(centers, shells: list, region_right: bool) -> list:
    """[(morceau de `centers`, ses anneaux)], les anneaux de `shells` (`concentric`) du bord vers le centre."""
    import shapely
    pieces = [p for p in getattr(centers, 'geoms', [centers]) if p.geom_type == 'Polygon' and not p.is_empty]
    if not pieces:
        return []
    groups: list = [[] for _p in pieces]
    near = shapely.STRtree(pieces)
    for shell in shells:
        polys = [p for p in getattr(shell, 'geoms', [shell]) if p.geom_type == 'Polygon' and not p.is_empty]
        if polys:
            owners = near.nearest(shapely.points([list(p.representative_point().coords)[0] for p in polys]))
            for p, k in zip(polys, owners.tolist()):
                groups[k].extend(rings_of(p, region_right))
    return [(p, g) for p, g in zip(pieces, groups) if g]


def _rest(doc, setup, op, tool, tp, em, here) -> None:
    """Reste matière : ce que l'outil passé avant (`ref_tool_id`, plus gros)
    n'a pas pu enlever — coins, parties étroites — repris avec cet outil."""
    ref = setup.tool(op.ref_tool_id)
    if ref is None or ref.radius_at(abs(op.depth)) <= tool.radius_at(abs(op.depth)):
        tp.warnings.append('reste matière : choisir l\'outil passé avant, plus gros que celui-ci')
        return
    geoms = [g for it in source_items(doc, op) if (g := item_geometry(it))]
    tol = setup.tolerance
    reg = region(geoms, tol)
    if reg.is_empty:
        tp.warnings.append('reste matière : aucun contour fermé')
        return
    depth = abs(op.depth)
    R, r = ref.radius_at(depth), tool.radius_at(depth)
    qs = _quad_segs(max(r, tol), tol)
    done = erode(reg, R + op.stock, qs).buffer(R, quad_segs=qs)      # vidé par l'outil d'avant
    rest = reg.buffer(-op.stock, quad_segs=qs).difference(done).buffer(-0.005).buffer(0.005)
    allowed = erode(reg, r + op.stock, qs)
    centers = allowed.intersection(rest.buffer(r, quad_segs=qs))
    if rest.is_empty or centers.is_empty:
        tp.warnings.append('reste matière : rien à reprendre (ou outil trop gros pour les restes)')
        return
    # la distance entre passes de l'opération (ligne de gamme : Stepover_i de TE), sinon celle de l'outil ; au plus 90 % du
    # diamètre (au-delà, des crêtes resteraient entre les passes)
    step = float(getattr(op, 'stepover_mm', 0.0) or 0.0)
    step = step if step > 0 else (tool.stepover or 0.4) * tool.diameter
    step = max(0.02, min(step, 0.9 * tool.diameter))
    shells = concentric(centers, step, tol)
    region_right = not op.climb
    if getattr(op, 'gamme_rule', 0) >= 885:               # relevé dans TE13 : chaque coin à la suite, l'outil remonte de l'un à l'autre
        groups = rings_by_piece(centers, shells, region_right)
        frames = frames_of(reg) if getattr(op, 'finish_skip_frame', False) else None
        if frames is not None:                            # relevé dans TE13 : les angles du cadre ignoré ne sont pas repris
            import shapely
            rim = shapely.union_all([p.exterior for p in getattr(frames, 'geoms', [frames])]).buffer(R + r + op.stock)
            groups = [g for g in groups if not (frames.covers(g[0]) and rim.covers(g[0]))]
        marks = [([(g[1][0][0][0], g[1][0][0][1], i)], False) for i, g in enumerate(groups)]
        picked = [groups[c[0][0][2]] for c in order_chains(marks, here)]
        zs = levels(depth, op.step_down or tool.step_down)
        angle = ramp_angle_of(op) if op.ramp else None
        # MODE_MULTIPASSE de TE : Global, chaque passe sur tous les coins ; sinon, chaque coin jusqu'au fond
        visits = [(g, k) for k in range(len(zs)) for g in picked] if getattr(op, 'pass_order', 'poche') == 'global' else             [(g, k) for g in picked for k in range(len(zs))]
        for (piece, order), k in visits:
            allowed_here = piece.buffer(1e-6)
            if angle:
                ramp_floor(em, order[::-1], allowed_here, zs[k - 1] if k else 0.0, zs[k], angle)
            mill_rings(em, order[::-1], zs, allowed_here, only={k})
    else:
        order = [pts for s in reversed(shells) for pts in rings_of(s, region_right)]
        mill_rings(em, order, levels(depth, op.step_down or tool.step_down), allowed.buffer(1e-6))
    left = rest.difference(centers.buffer(r)).area
    if left > 0.01:
        tp.warnings.append(f'reste matière : {left:.2f} mm² hors de portée de cet outil (coins à son rayon)')


def _decoupe3d(doc, setup, op, tool, tp, em, here) -> None:
    """Découpe 3D : à chaque passe, décalage du rayon du cône à cette
    profondeur — le bord du dessus suit le contour, le flanc prend l'angle
    de l'outil (chanfrein)."""
    if op.side == 'sur':
        _gravure(doc, setup, op, tool, tp, em, here)
        return
    if tool.kind != 'conique':
        tp.warnings.append('découpe 3D : outil conique attendu (sinon détourage ordinaire)')
    if has_tabs(op):
        tp.warnings.append('découpe 3D : pontets non gérés')
    geoms = [g for it in source_items(doc, op) if (g := item_geometry(it))]
    tol = setup.tolerance
    reg = region(geoms, tol)
    if reg.is_empty:
        tp.warnings.append('découpe 3D : aucun contour fermé')
        return
    region_right = op.climb if op.side == 'exterieur' else not op.climb
    zs = op_levels(op, tool)
    comps = [g for g in getattr(reg, 'geoms', [reg]) if not g.is_empty]
    pos = here
    picker = NearestPicker(comps)
    for ci in range(len(comps)):
        if ci % 16 == 0:
            progress.step(ci, len(comps))
        comp = picker.pop(pos)
        prev_r = None
        for z in zs:
            r = tool.radius_at(-z) + op.stock
            g = buffer_checked(comp, r if op.side == 'exterieur' else -r, _quad_segs(max(r, tol), tol))
            if g.is_empty:
                tp.warnings.append(f'découpe 3D : forme trop petite à {-z:.2f} mm de profondeur')
                break
            for pts in [p for p, _c in order_chains([(p, True) for p in rings_of(g.simplify(tol / 2), region_right)],
                                                    em.pos or pos)]:
                near = em.pos is not None and em.pos[2] < 0 and prev_r is not None and \
                    math.dist(em.pos[:2], pts[0][:2]) <= 3 * abs(r - prev_r) + 0.05
                if near:
                    em.feed(pts[0][0], pts[0][1], em.pos[2])    # petit pas latéral côté chute
                    cut_chain_here(em, pts, z)
                else:
                    cut_chain(em, pts, True, [z], ramp=op.ramp, ramp_angle=ramp_angle_of(op))
            prev_r = r
        if getattr(op, 'corner_pull', False) and tool.kind == 'conique' and 0 < tool.angle < 180 and zs:
            # tirés d'angle : de la cote la plus basse, le long de la bissectrice, jusqu'à ce que le
            # cône touche le sommet de l'angle à la surface
            t = math.tan(math.radians(tool.angle) / 2)
            z_low = zs[-1]
            n_pull = 0
            for v, b, ang in corner_pulls(comp, op.side == 'exterieur', float(op.corner_pull_angle or 135.0)):
                s2 = math.sin(ang / 2)
                r_low = tool.radius_at(-z_low) + op.stock
                d0, d1 = r_low / s2, (tool.tip / 2 + op.stock) / s2
                if d0 - d1 < 1e-3:
                    continue
                em.travel(v[0] + b[0] * d0, v[1] + b[1] * d0)
                em.plunge(z_low)
                steps = max(2, int(math.ceil((d0 - d1) / 0.2)))
                for kk in range(1, steps + 1):
                    d = d0 + (d1 - d0) * kk / steps
                    em.feed(v[0] + b[0] * d, v[1] + b[1] * d, z_low * (d - d1) / (d0 - d1))
                above = min(max(0.0, float(getattr(op, 'corner_pull_z', 0.0) or 0.0)), em.safe)
                if above > 0 and z_low < 0:              # toujours dans la pente, hors de la matière : les copeaux s'évacuent
                    d = d1 + above * (d0 - d1) / z_low
                    em.feed(v[0] + b[0] * d, v[1] + b[1] * d, above)
                em.retract()
                n_pull += 1
            if n_pull:
                tp.warnings.append(f'découpe 3D : {n_pull} tiré(s) d\'angle')
        if getattr(op, 'foot_pull', False) and tool.kind == 'conique' and 0 < tool.angle < 180 and zs:
            # tiré d'angle au pied : à la cote la plus basse, de l'arc du coin jusqu'au sommet du
            # décalage à onglet — le pied du flanc devient vif (poinçons)
            z_low = zs[-1]
            r_low = tool.radius_at(-z_low) + op.stock
            n_foot = 0
            for v, b, ang in corner_pulls(comp, op.side == 'exterieur', float(op.foot_pull_max or 135.0),
                                          min_angle=float(op.foot_pull_min or 0.0), part=True):
                s2 = math.sin(ang / 2)
                d0, d1 = r_low, r_low / s2
                if d1 - d0 < 1e-3:
                    continue
                em.travel(v[0] + b[0] * d0, v[1] + b[1] * d0)
                em.plunge(z_low)
                em.feed(v[0] + b[0] * d1, v[1] + b[1] * d1, z_low)
                em.feed(v[0] + b[0] * d0, v[1] + b[1] * d0, z_low)
                em.retract()
                n_foot += 1
            if n_foot:
                tp.warnings.append(f'découpe 3D : {n_foot} tiré(s) d\'angle au pied')
        if em.pos is not None:
            pos = em.pos


def corner_pulls(comp, exterior: bool, max_angle: float, min_seg: float = 0.05, min_angle: float = 0.0,
                 part: bool = False) -> list:
    """Angles où la découpe 3D doit « tirer » (TypeEdit : tiré d'angle au
    sommet) : sommets du contour où le côté chute fait un angle θ plus
    fermé que `max_angle` — angles rentrants de la pièce (découpe
    extérieure) ou saillants de la forme vidée (découpe intérieure). `part`
    : les angles saillants de la pièce (tiré d'angle au pied), d'au moins
    `min_angle`. Rend [(sommet, bissectrice unitaire vers la chute, θ en
    radians)]."""
    out = []
    rings = [comp.exterior] + list(comp.interiors)
    for k, ring in enumerate(rings):
        pts = list(ring.coords)[:-1]
        n = len(pts)
        if n < 3:
            continue
        area2 = sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1] for i in range(n))
        region_left = (area2 > 0) == (k == 0)              # la pièce (région) à gauche du sens du ring
        for i in range(n):
            a, v, b = pts[i - 1], pts[i], pts[(i + 1) % n]
            e1, e2 = (a[0] - v[0], a[1] - v[1]), (b[0] - v[0], b[1] - v[1])
            l1, l2 = math.hypot(*e1), math.hypot(*e2)
            if l1 < min_seg or l2 < min_seg:
                continue
            u1, u2 = (e1[0] / l1, e1[1] / l1), (e2[0] / l2, e2[1] / l2)
            ang = math.acos(max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1])))   # angle entre les arêtes
            d = (v[0] - a[0], v[1] - a[1])
            cross = d[0] * e2[1] - d[1] * e2[0]                 # virage : > 0 à gauche
            convex_region = (cross > 0) == region_left          # coin saillant de la région
            scrap_convex = (not convex_region) if exterior else convex_region
            wanted = (not scrap_convex) if part else scrap_convex
            if not wanted or not min_angle <= math.degrees(ang) < max_angle:
                continue
            bx, by = u1[0] + u2[0], u1[1] + u2[1]
            bn = math.hypot(bx, by)
            if bn < 1e-9:
                continue
            sg = -1.0 if part else 1.0                          # pièce saillante : la chute est à l'opposé
            out.append((v, (sg * bx / bn, sg * by / bn), ang))
    return out


def _pt(p):
    from shapely.geometry import Point
    return Point(p[0], p[1])


class NearestPicker:
    """Formes prises une à une au plus près d'un point (distance shapely ;
    à égalité, la première de la liste) — le même choix qu'un balayage de
    toutes les formes restantes, sans son coût quadratique : arbre STRtree
    interrogé dans un rayon qui double tant qu'il ne contient pas, avec
    une marge, la plus proche des formes restantes."""

    def __init__(self, geoms: list):
        import shapely
        self.geoms = list(geoms)
        self.used = [False] * len(self.geoms)
        self.left = len(self.geoms)
        self.tree = shapely.STRtree(self.geoms) if self.geoms else None
        if self.geoms:
            b = shapely.total_bounds(self.geoms)
            span = max(float(b[2] - b[0]), float(b[3] - b[1]), 1e-6)
            self.r0 = span / max(1.0, math.sqrt(len(self.geoms)))

    def pop(self, here):
        """La forme restante la plus proche de `here` (retirée)."""
        import shapely
        pt = shapely.Point(here[0], here[1])
        r = self.r0
        while True:
            cand = [i for i in self.tree.query(pt, predicate='dwithin', distance=r).tolist() if not self.used[i]]
            if cand:
                dist = shapely.distance(self.tree.geometries.take(cand), pt).tolist()
                d, i = min(zip(dist, cand))
                if d < r * (1 - 1e-9) - 1e-12 or len(cand) == self.left:     # sûre, ou toutes en lice
                    self.used[i] = True
                    self.left -= 1
                    return self.geoms[i]
            elif self.left == 0:
                raise IndexError('plus de formes')
            r *= 2


def cut_chain_here(em: Emitter, pts: list, z: float) -> None:
    """Contour fermé depuis la position courante (déjà à son départ)."""
    em.plunge(z)
    for p in pts[1:]:
        em.feed(p[0], p[1], z)


def pierce_check(chains: list, reg, lead: tuple, pierce: float, tp) -> None:
    """Contrôle de perçage (TE, page 661) : un contour du dessin à moins de `pierce` du point d'entrée ou de sortie est signalé.
    `lead` : (entrée, sortie), ou une liste de ces couples, une par chaîne."""
    if pierce <= 0:
        return
    from shapely.geometry import Point
    edge = reg.boundary
    n = 0
    for k, chain in enumerate(chains):
        ld = lead[k] if isinstance(lead, list) else lead
        n += sum(1 for on, p in ((ld[0] > 0, chain[0]), (ld[1] > 0, chain[-1]))
                 if on and Point(p[:2]).distance(edge) < pierce - 1e-6)
    if n:
        tp.warnings.append(f"contrôle de perçage : {n} point(s) à moins de {pierce:g} mm d'un contour")


def with_leads(ring: list, region, scrap_outside: bool, lead_in: float, lead_out: float, steps: int = 12, *,
               keep_start: bool = False, mode: str = 'arc', angle_in: float = 45.0, angle_out: float = 45.0,
               pierce: float = 0.0, transition: float = 0.0) -> list:
    """Anneau fermé précédé d'une entrée et suivi d'une sortie tangentes (quarts
    de cercle) du côté de la chute : hors de `region` si `scrap_outside`,
    dedans sinon. L'entrée part du point de perçage et rejoint le départ de
    l'anneau dans son sens ; la sortie le quitte dans le même sens.
    `keep_start` : le départ a été choisi, il reste là.
    `mode` (TE, page 661) : 'arc' (lead_in et lead_out : rayons), 'ligne' (longueurs ; `angle_in`, `angle_out` : avec le contour),
    'percage' (distances du perçage au contour ; goutte tangente à un cercle de rayon `pierce`, ou cercle de cette distance pour
    diamètre si elle est plus petite que le diamètre de perçage, ou si `pierce` est nul).
    `transition` (mode 'percage', relevé dans TE13 : son rayon de transition R) : la goutte est tangente à un cercle de ce rayon ;
    une distance de moins de 2 x R donne un arc de ce cercle, de cette corde (une demi-volte), sans droite."""
    from shapely.geometry import Point
    if len(ring) < 3:
        return list(ring)
    # départ au milieu du plus long côté : l'arc tient dans la chute (pas d'un coin)
    pts = [tuple(p[:2]) for p in ring]
    closed_ring = math.dist(pts[0], pts[-1]) < 1e-9
    if closed_ring and not keep_start:
        i = max(range(len(pts) - 1), key=lambda j: math.dist(pts[j], pts[j + 1]))
        if math.dist(pts[i], pts[i + 1]) > 1e-9:
            m = ((pts[i][0] + pts[i + 1][0]) / 2, (pts[i][1] + pts[i + 1][1]) / 2)
            ring = [m] + pts[i + 1:-1] + pts[:i + 1] + [m]
    sx, sy = ring[0][:2]
    k = 1
    while k < len(ring) and math.dist(ring[k][:2], (sx, sy)) < 1e-9:
        k += 1
    if k >= len(ring):
        return list(ring)
    tx, ty = ring[k][0] - sx, ring[k][1] - sy
    d = math.hypot(tx, ty)
    tx, ty = tx / d, ty / d
    nx, ny = -ty, tx                                     # normale à gauche du sens de parcours
    eps = 1e-3
    left_inside = region.contains(Point(sx + nx * eps, sy + ny * eps))
    if left_inside == scrap_outside:                     # la chute est à droite
        nx, ny = -nx, -ny

    def quarter(r: float, entering: bool) -> list:
        cx, cy = sx + nx * r, sy + ny * r
        a_s = math.atan2(-ny, -nx)                       # le départ de l'anneau, vu du centre
        a_t = math.atan2(-ty if entering else ty, -tx if entering else tx)
        sweep = (a_s - a_t if entering else a_t - a_s)
        sweep = (sweep + math.pi) % (2 * math.pi) - math.pi
        a0 = a_t if entering else a_s
        return [(cx + r * math.cos(a0 + sweep * i / steps), cy + r * math.sin(a0 + sweep * i / steps))
                for i in range(steps + 1)]

    def straight(r: float, entering: bool) -> list:
        a = math.radians(max(1.0, min(90.0, float(angle_in if entering else angle_out))))
        along, side = r * math.cos(a), r * math.sin(a)
        if entering:
            return [(sx - tx * along + nx * side, sy - ty * along + ny * side), (sx, sy)]
        return [(sx, sy), (sx + tx * along + nx * side, sy + ty * along + ny * side)]

    def drop(r: float, entering: bool) -> list:
        # le cercle est tangent au contour au point de contact ; le perçage est à r de ce point, sur la normale : la droite
        # qui en part est tangente au cercle. r = 2 x rayon : le perçage est sur le cercle, et il n'y a plus de droite.
        rho = transition if transition > 0 else min(pierce, r / 2) if pierce > 0 else r / 2
        sigma = 1.0 if tx * ny - ty * nx > 0 else -1.0
        ox, oy = sx + nx * rho, sy + ny * rho
        an = math.atan2(ny, nx)
        if r < 2 * rho - 1e-9:                           # une demi-volte : un arc de corde r
            span = 2 * math.asin(r / (2 * rho))
            beta = math.pi - span
            hole = None                                  # le bout de l'arc, chacun le sien
        else:
            beta = math.acos(min(1.0, rho / (r - rho)))
            span = math.pi - beta
            hole = (sx + nx * r, sy + ny * r)
        n = 2 * steps
        if entering:
            arc = [(ox + rho * math.cos(an + sigma * (beta + span * i / n)), oy + rho * math.sin(an + sigma * (beta + span * i / n)))
                   for i in range(n)] + [(sx, sy)]
            if hole is None:
                return arc
            return [hole] + (arc if math.dist(hole, arc[0]) > 1e-9 else arc[1:])
        arc = [(sx, sy)] + [(ox + rho * math.cos(an + math.pi + sigma * span * i / n), oy + rho * math.sin(an + math.pi + sigma * span * i / n))
                            for i in range(1, n + 1)]
        return arc + ([hole] if hole is not None and math.dist(hole, arc[-1]) > 1e-9 else [])
    shape = {'ligne': straight, 'percage': drop}.get(mode, quarter)
    from shapely.geometry import LineString
    inner = region.buffer(-1e-3)
    outer = region.buffer(1e-3)

    def fitting(r: float, entering: bool) -> list:
        """L'arc le plus grand (jusqu'à `r`) qui reste dans la chute : un
        jour étroit (entre deux lettres) ne doit pas faire mordre la pièce."""
        while r >= 0.05:
            arc = shape(r, entering)
            ls = LineString(arc)
            if (not ls.intersects(inner)) if scrap_outside else outer.contains(ls):
                return arc
            r *= 0.5
        return []
    out = [tuple(p[:2]) for p in ring]
    if lead_in > 0:
        out = fitting(lead_in, True)[:-1] + out
    if lead_out > 0:
        out = out + fitting(lead_out, False)[1:]
    return out


def _laser_cut(doc, setup, op, tool, tp, em, here) -> None:
    """Découpe laser : contour décalé du demi-faisceau (diamètre de l'outil), une passe."""
    if op.side == 'sur':
        _laser(doc, setup, op, tool, tp, em, here)
        return
    _contour(doc, setup, op, tool, tp, em, here, zs=[0.0] * _passes(op))   # contours fermés : tours répétés


def _laser_fill(doc, setup, op, tool, tp, em, here) -> None:
    """Gravure laser : remplissage par lignes parallèles (pas `resolution`,
    angle `hatch_angle`), en aller-retour ; contour en finition. Comme
    TauDrive : `laser_passes` passages, les lignes tournées de `hatch_step`
    à chacun (sinon les creux du premier guident le second et le fond sort
    strié), seconde nappe à +90° (`hatch_cross`), remplissage rentré de
    `hatch_inset` (le bord gravé tombe sur le contour malgré le demi-spot)."""
    geoms = [g for it in source_items(doc, op) if (g := item_geometry(it))]
    tol = setup.tolerance
    reg = region(geoms, tol)
    if reg.is_empty:
        tp.warnings.append('gravure laser : aucun contour fermé')
        return
    pitch = max(0.005, op.resolution or 0.1)
    zone = reg
    inset = abs(getattr(op, 'hatch_inset', 0.0) or 0.0)
    if inset > 0:
        rentre = erode(reg, inset, _quad_segs(inset, tol))
        zone = rentre if not rentre.is_empty else reg    # forme trop fine : déborder plutôt que rien
    step = getattr(op, 'hatch_step', 0.0) or 0.0
    parts = fill_parts(zone, getattr(op, 'fill_order', 'global'), getattr(op, 'fill_dx', 10.0),
                       getattr(op, 'fill_dy', 10.0), here)
    layers = []
    for k in range(_passes(op)):
        angle = op.hatch_angle + k * step
        layers.append([angle] + ([angle + 90.0] if getattr(op, 'hatch_cross', False) else []))
    auto = bool(getattr(op, 'hatch_auto', False))
    for angles in layers:
        for angle in angles:
            from shapely import affinity
            y_ref = affinity.rotate(zone, -angle, origin=(0, 0)).bounds[1]   # lignes alignées d'une zone à l'autre
            for part in parts:
                if auto:                                 # chaque morceau dans le sens de sa longueur
                    a = angle + long_axis_angle(part)
                    rows = _hatch_rows(part, a, pitch)
                else:
                    rows = _hatch_rows(part, angle, pitch, y_ref)
                if rows is None:
                    tp.warnings.append('gravure laser : pas trop fin pour cette surface')
                    return
                for segs in rows:
                    for c in segs:
                        cut_chain(em, c, False, [0.0])
        if op.finish:
            for pts, _c in order_chains([(p, True) for p in rings_of(reg, op.climb)], em.pos):
                cut_chain(em, pts, True, [0.0])


def long_axis_angle(g) -> float:
    """Angle (°) du grand côté du plus petit rectangle qui enferme `g` : des
    lignes dans ce sens sont moins nombreuses et plus longues."""
    r = g.minimum_rotated_rectangle
    if r.geom_type != 'Polygon':
        return 0.0
    c = list(r.exterior.coords)
    (ax, ay), (bx, by), (qx, qy) = c[0], c[1], c[2]
    if math.hypot(bx - ax, by - ay) >= math.hypot(qx - bx, qy - by):
        return math.degrees(math.atan2(by - ay, bx - ax)) % 180.0
    return math.degrees(math.atan2(qy - by, qx - bx)) % 180.0


def fill_parts(zone, order: str, dx: float, dy: float, here=(0.0, 0.0)) -> list:
    """Morceaux d'un remplissage, dans l'ordre (TypeEdit : Optimisation de
    zone) : 'global' — tout d'un coup ; 'forme' — chaque forme entière, au
    plus proche ; 'zones' — carreaux de dx × dy, en serpentin, rangée par
    rangée (le laser reste dans un petit champ : moins de chauffe, de
    sauts)."""
    import shapely
    polys = [p for p in getattr(zone, 'geoms', [zone]) if not p.is_empty]
    if order == 'forme' and len(polys) > 1:
        return _nearest_first(polys, here)
    if order == 'zones' and dx > 0 and dy > 0:
        x0, y0, x1, y1 = zone.bounds
        nx, ny = max(1, math.ceil((x1 - x0) / dx)), max(1, math.ceil((y1 - y0) / dy))
        if nx * ny > 10000:
            return [zone]
        out = []
        for j in range(ny):
            cols = range(nx) if j % 2 == 0 else range(nx - 1, -1, -1)
            for i in cols:
                cell = shapely.box(x0 + i * dx, y0 + j * dy, x0 + (i + 1) * dx, y0 + (j + 1) * dy)
                g = zone.intersection(cell)
                if not g.is_empty and g.area > 1e-12:
                    out.append(g)
        return out
    return [zone]


def _hatch_rows(reg, angle: float, pitch: float, y_ref: float | None = None):
    """Lignes d'un remplissage à l'angle donné, en aller-retour (rangées de
    segments) ; None si le pas est trop fin pour la surface. Balayage
    pair-impair de toutes les arêtes à la fois (numpy) : une arête coupe
    les rangées comprises entre ses deux bouts (demi-ouvert, un sommet ne
    compte qu'une fois) ; les points de chaque rangée, triés, se prennent
    deux par deux. Mêmes segments que l'intersection ligne par ligne, sans
    son coût sur les gros dessins."""
    import numpy as np
    import shapely
    from shapely import affinity
    rot = affinity.rotate(reg, -angle, origin=(0, 0))
    if rot.is_empty:
        return []
    x0, y0, x1, y1 = rot.bounds
    if y_ref is not None:                                # rangées calées sur celles d'un ensemble plus grand
        y0 = y_ref + math.floor((y0 - y_ref) / pitch + 1e-9) * pitch
    n = int((y1 - y0) / pitch)
    if n > 200000:
        return None
    progress.check()
    ys = []
    for k in range(n + 1):
        y = y0 + (k + 0.5) * pitch
        if y >= y1:
            break
        ys.append(y)
    rows = [[] for _ in ys]
    polys, todo = [], [rot]
    while todo:
        g = todo.pop()
        if g.geom_type == 'Polygon':
            polys.append(g)
        elif hasattr(g, 'geoms'):
            todo += list(g.geoms)
    if polys and ys:
        xy, ring = shapely.get_coordinates(shapely.get_rings(polys), return_index=True)
        same = ring[:-1] == ring[1:]                     # arêtes : points voisins d'un même contour
        ax, ay = xy[:-1, 0][same], xy[:-1, 1][same]
        bx, by = xy[1:, 0][same], xy[1:, 1][same]
        klo = np.ceil((np.minimum(ay, by) - y0) / pitch - 0.5)
        khi = np.ceil((np.maximum(ay, by) - y0) / pitch - 0.5)
        cnt = (khi - klo).astype(np.int64)
        e = np.repeat(np.arange(len(cnt)), cnt)
        k = (klo[e] + (np.arange(len(e)) - (np.cumsum(cnt) - cnt)[e])).astype(np.int64)
        yk = y0 + (k + 0.5) * pitch
        x = ax[e] + (yk - ay[e]) * (bx[e] - ax[e]) / (by[e] - ay[e])
        order = np.lexsort((x, k))
        k, x = k[order], x[order]
        for kk, a, b in zip(k[0::2].tolist(), x[0::2].tolist(), x[1::2].tolist()):
            if b - a <= 1e-12 or kk >= len(ys):
                continue
            row = rows[kk]
            if row and a - row[-1][1][0] <= 1e-12:           # segments qui se touchent : un seul
                row[-1] = [row[-1][0], (b, ys[kk])]
            else:
                row.append([(a, ys[kk]), (b, ys[kk])])
    for kk in range(1, len(rows), 2):
        rows[kk] = [c[::-1] for c in reversed(rows[kk])]
    ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    return [[[(x * ca - y * sa, x * sa + y * ca) for x, y in c] for c in segs] for segs in rows]


def pocket_bottom(op) -> float:
    """Cote du fond d'une poche : son Z de départ moins sa profondeur (celle d'origine si `compute` l'a augmentée de
    la surépaisseur du brut du dessin 2D)."""
    depth = abs(float(op.depth or 0.0))
    left = 0.0 if getattr(op, '_floor_left', False) else min(left_on_floor(op), depth)   # ce qu'elle laisse au fond
    return float(getattr(op, 'z_start', 0.0) or 0.0) - depth + float(getattr(op, '_stock_rise', 0.0) or 0.0) + left


def clears_all(op, tool) -> bool:
    """La poche `op` vide-t-elle tout ce que son outil atteint ? Non : balayage sans tour du contour (festons le long
    des parois) ou texturé (des traits), pas plus large que l'outil (crêtes), outil conique au pas imposé plus large
    que sa pointe (crêtes au fond), outil boule au pas plus large que la moitié de sa largeur (crêtes hautes). Fraise
    au pas plus grand que son rayon : oui — elle reprend elle-même ce qui resterait entre ses passes (reprises
    d'angle, tour de ce qui reste : `spiral_leftover`)."""
    if getattr(op, 'pocket_mode', 'concentrique') == 'balayage' and \
            (getattr(op, 'sweep_contour', 'apres') == 'sans' or getattr(op, 'sweep_texture', False)):
        return False
    step = float(getattr(op, 'stepover_mm', 0.0) or 0.0)
    if tool.kind == 'conique':                           # sans pas imposé : resserré (crêtes d'au plus 0,02 mm)
        return not step or step <= 2 * floor_radius(op, tool) + 0.05
    r = cut_radius(op, tool)
    if tool.kind == 'boule' and r > 0:
        return (step or (tool.stepover or 0.4) * 2 * r) <= r + 1e-6
    return (step or (tool.stepover or 0.4) * tool.diameter) <= tool.diameter + 1e-6


def previous_pockets(setup, op) -> list:
    """Poche, seulement le reste : les opérations Poche actives placées avant `op`, au fond au moins aussi bas (Z de
    départ compris), avec un outil d'usinage — ce qu'elles ont vidé n'est pas repassé."""
    ops = list(getattr(setup, 'operations', None) or [])
    at = next((i for i, o in enumerate(ops) if o is op), None)
    if at is None:
        at = next((i for i, o in enumerate(ops) if o.id == op.id), None)
    if at is None:
        return []
    out = []
    for o in ops[:at]:
        t = setup.tool(o.tool_id)
        if o.enabled and o.kind == 'poche' and t is not None and t.kind != 'laser' and \
                pocket_bottom(o) <= pocket_bottom(op) + 1e-6:
            out.append(o)
    return out


def floor_left_before(setup, op) -> list:
    """Les poches actives placées avant `op` qui seraient descendues assez bas, mais ont laissé une surépaisseur Z
    au fond : leur fond reste à faire partout (`previous_pockets` ne les compte pas)."""
    ops = list(getattr(setup, 'operations', None) or [])
    at = next((i for i, o in enumerate(ops) if o is op or o.id == op.id), None)
    out = []
    for o in ops[:at] if at is not None else []:
        t = setup.tool(o.tool_id)
        left = left_on_floor(o)
        if o.enabled and o.kind == 'poche' and t is not None and t.kind != 'laser' and left > 0 and \
                pocket_bottom(o) > pocket_bottom(op) + 1e-6 >= pocket_bottom(o) - left:
            out.append(o)
    return out


def floor_radius(op, tool) -> float:
    """Rayon de ce que l'outil vide au fond : la pointe d'un outil conique, sinon son rayon de décalage."""
    if tool.kind == 'conique':
        return max(0.0, tool.radius_at(1e-9))
    return cut_radius(op, tool)


def spiral_leftover(groups: list, centers, R: float, region_right: bool, qs: int, tol: float) -> list:
    """Ce que des spirales, ou des anneaux plus écartés que le rayon, laissent, par groupe : les tours (fermés) le
    long du bord de chaque reste. Spirales : là où un anneau intérieur ne longe pas tout l'anneau suivant (le bras
    d'une forme où il a disparu), le tour qui glisse de l'un à l'autre n'y passe pas. Anneaux écartés de plus que
    `R` (et d'au plus 2R) : un îlot au centre ou là où la forme se resserre, une lamelle qu'une reprise d'angle n'a
    pas atteinte. Le reste, entre deux tours écartés d'au plus 2R, est plus étroit que 2R : un tour le long de son
    bord l'enlève. Mesuré sur le parcours même (`groups` : [(points, fermé)], reprises d'angle comprises) : les
    centres permis (`centers`) élargis de `R`, moins ce que les tours balaient."""
    import shapely
    out: list = [[] for _g in groups]
    lines = [shapely.LineString([p[:2] for p in pts]) for g in groups for pts, _closed in g if len(pts) >= 2]
    if not lines:
        return out
    thin = max(0.01, 2 * tol)
    # chaque tour élargi puis réunis (élargir d'un coup la réunion des lignes est cent fois plus long quand les tours
    # se touchent, au pas de 2R) ; élargi de `thin` en plus, et le reste regonflé d'autant : sans les lamelles
    swept = shapely.union_all(shapely.buffer(lines, R + thin, quad_segs=qs))
    left = centers.buffer(R, quad_segs=qs).difference(swept)
    left = left.buffer(thin, quad_segs=qs).intersection(centers)
    loops = [pts for pts in rings_of(simplify_parts(left, tol / 2), region_right) if len(pts) >= 3]
    if not loops:
        return out
    owner = [shapely.union_all([shapely.LineString([p[:2] for p in pts]) for pts, _c in g if len(pts) >= 2])
             for g in groups]
    for pts in loops:
        at = shapely.Point(pts[0][:2])
        out[min(range(len(groups)), key=lambda i: owner[i].distance(at))].append(pts)
    for i, (g, more) in enumerate(zip(groups, out)):     # au plus proche, depuis la fin du dernier tour du groupe
        if len(more) > 1 and g:
            last = g[-1][0]
            out[i] = [p for p, _closed in order_chains([(p, True) for p in more], last[-1] if last else (0.0, 0.0))]
    return out


def cleared_by(doc, op, tool, tol: float):
    """Ce qu'une poche vide au fond (shapely) : ses centres d'outil, décalés de son rayon et de sa surépaisseur XY,
    élargis du rayon qui vide au fond (une passe de finition enlève la surépaisseur ; outil boule : le pied des parois,
    arrondi, reste). None : rien."""
    geoms = [g for it in source_items(doc, op) if (g := item_geometry(it))]
    reg = region(geoms, tol) if geoms else None
    if reg is None or reg.is_empty:
        return None
    R = cut_radius(op, tool)
    qs = _quad_segs(max(R, tol), tol)
    stock = 0.0 if (op.finish and op.stock > 0) else max(0.0, float(op.stock or 0.0))
    centers = erode(reg, R + stock, qs)
    fr = 0.0 if tool.kind == 'boule' else floor_radius(op, tool)
    return None if centers.is_empty else centers.buffer(max(fr, 1e-3), quad_segs=qs)


def thick_radius(r: float, stock: float) -> float:
    """Rayon du disque qui dit « épais » de la matière qu'une passe de finition rencontre : un peu plus que celui
    du disque inscrit dans ce que les passes à r + surépaisseur laissent dans un coin droit (toute poche finit ce
    coin au fond d'un coup) ; jamais plus de 0,94 r (une rainure de la largeur de l'outil est toujours épaisse)."""
    corner = ((math.sqrt(2.0) - 1.0) * r + math.sqrt(2.0) * max(0.0, stock)) / (1.0 + math.sqrt(2.0))
    return min(corner + 0.02, 0.94 * r)


def clip_chains(pts: list, keep, seg: float) -> list:
    """Morceaux de l'anneau fermé `pts` dont les points sont dans `keep` (shapely), dans son sens : [(points, fermé)].
    L'anneau est recoupé tous les `seg` mm ; chaque morceau garde un point de plus de part et d'autre (le bord de `keep`
    n'est pas manqué). Tout dedans : l'anneau lui-même, fermé."""
    import numpy as np
    import shapely
    ring = [tuple(p[:2]) for p in pts]
    if len(ring) < 3:
        return []
    if math.dist(ring[0], ring[-1]) > 1e-9:
        ring.append(ring[0])
    dense = [tuple(c) for c in shapely.segmentize(shapely.linestrings(ring), seg).coords][:-1]
    n = len(dense)
    if n < 2:
        return []
    xy = np.array(dense)
    inside = np.asarray(shapely.intersects_xy(keep, xy[:, 0], xy[:, 1]), dtype=bool)
    if not inside.any():
        return []
    grow = inside | np.roll(inside, 1) | np.roll(inside, -1)
    if grow.all():
        return [(ring, True)]
    start = int(np.argmin(grow))                         # un point dehors : les morceaux commencent après lui
    out, cur = [], []
    for k in range(1, n + 1):
        i = (start + k) % n
        if grow[i]:
            cur.append(dense[i])
        elif cur:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    chains = []
    for c in out:
        if len(c) >= 2:
            c = [tuple(q) for q in shapely.linestrings(c).simplify(1e-4).coords]
            chains.append((c, False))
    return chains


def split_shut(fin: list, shut, reg, reach: float, stock: float, seg: float, qs: int) -> tuple[list, list]:
    """Partage les morceaux de finition `fin` ([(points, fermé)]) : ceux qui longent de la matière jamais ouverte
    (`shut`, shapely : ce qu'aucune passe n'a ouvert) — à faire à toutes les cotes, comme un contour, le tronçon
    seulement pour un tour fermé — et les autres, au fond seulement. Jamais ouverte : ce qui, dans `shut`, est plus
    épais que ce qu'un coin droit garde (`thick_radius`) et que la finition balaie (`reach` : son rayon) ; une
    surépaisseur seule ne l'est pas tant qu'elle reste sous 1,3 fois le rayon. Rend (à toutes les cotes, au fond)."""
    import shapely
    if not fin or shut is None or shut.is_empty:
        return [], list(fin)
    lines = [shapely.LineString([p[:2] for p in pts]) for pts, _closed in fin]
    thick = thick_radius(reach, stock)                   # ce que la finition rencontre d'épais : ce disque y tient
    core = shut.buffer(-thick, quad_segs=qs)
    if core.is_empty:                                    # rien d'épais nulle part (le cas courant) : rien à chercher
        return [], list(fin)
    shut = shut.intersection(core.buffer(thick, quad_segs=qs))   # seul ce qui est épais peut l'être dans le balayage
    shut = shut.intersection(shapely.union_all(shapely.buffer(lines, reach, quad_segs=qs)))
    shut = shut.buffer(-thick, quad_segs=qs).buffer(thick, quad_segs=qs)
    if shut.is_empty:
        return [], list(fin)
    near = shut.buffer(reach + 2 * seg, quad_segs=qs)    # là, l'outil touche cette matière
    away = reg.buffer(reach, quad_segs=qs).difference(near)
    shapely.prepare(near)
    shapely.prepare(away)
    deep, flat = [], []
    for (pts, closed), line in zip(fin, lines):
        if not line.intersects(near):
            flat.append((pts, closed))
        elif not closed:
            deep.append((pts, False))
        else:                                            # un tour fermé : le tronçon qui la longe seulement
            parts = clip_chains(pts, near, seg)
            if len(parts) == 1 and parts[0][1]:
                deep.append((pts, True))
            else:
                deep += parts
                flat += clip_chains(pts, away, seg)
    return deep, flat


def cut_deep(em, deep: list, levels: list, here, **kw) -> None:
    """Les morceaux de finition `deep` ([(points, fermé)]) à toutes les cotes `levels`, au plus proche voisin. Un
    morceau ouvert est parcouru en aller-retour : il est remis dans le sens de sa source (`order_chains` le retourne
    pour partir du bout le plus proche), puis retourné si le nombre de cotes est pair — la dernière cote, celle qui se
    voit, dans le sens demandé (avalant ou en opposition). `kw` : pour `cut_chain`."""
    src = {(tuple(p[0][:2]), tuple(p[-1][:2])) for p, closed in deep if not closed}
    for pts, closed in order_chains(deep, here):
        if not closed:
            ends = (tuple(pts[0][:2]), tuple(pts[-1][:2]))
            if ends not in src and ends[::-1] in src:
                pts = pts[::-1]                          # retourné par order_chains : remis dans son sens
            if len(levels) % 2 == 0:
                pts = pts[::-1]
        cut_chain(em, pts, closed, levels, **kw)


def opened_by(moves: list, z: float, r: float, qs: int):
    """Ce que les avances à la cote `z` ont ouvert (shapely) : leurs segments élargis du rayon `r` ; None : rien.
    D'après les mouvements mêmes : un balayage sans tour du contour, une spirale, une reprise d'angle comptent pour
    ce qu'ils enlèvent vraiment."""
    import shapely
    runs, cur, prev = [], [], None
    for m in moves:
        if prev is not None and m.kind != 'rapid' and prev.kind != 'rapid' and abs(m.z - z) < 1e-6 \
                and abs(prev.z - z) < 1e-6:                  # un segment au fond (après la plongée, entre avances)
            if not cur:
                cur = [(prev.x, prev.y)]
            if math.dist(cur[-1], (m.x, m.y)) > 1e-9:
                cur.append((m.x, m.y))
        else:
            if len(cur) >= 2:
                runs.append(cur)
            cur = []
        prev = m
    if len(cur) >= 2:
        runs.append(cur)
    if not runs:
        return None
    return shapely.union_all(shapely.buffer([shapely.LineString(c) for c in runs], r, quad_segs=qs))


def finish_pass(em, op, tool, tp, reg, region_right: bool, zs: list, qs: int, ramp: bool = False) -> None:
    """Passe de finition d'une poche entière (concentrique ou balayage) : le tour au rayon de l'outil, au fond. Avec
    `op.finish_shut_levels` (réponse 7 du 14/11, en option), la règle de « seulement le reste » : les tronçons qui
    longent de la matière que l'ébauche n'a pas ouverte — une zone plus étroite que l'outil et deux surépaisseurs, où
    seule la finition entre, la pointe d'un coin aigu, les dents qu'un balayage sans tour du contour laisse le long
    d'un bord — sont faits à toutes les cotes ; le reste au fond. Ce qui est ouvert : les avances de l'ébauche au fond,
    élargies du rayon (`opened_by`). Outil conique ou boule : au fond seulement (le flanc ouvre la matière à chaque
    passe). `ramp` : l'entrée en rampe de l'opération (poche concentrique)."""
    r = cut_radius(op, tool)
    fin = [(p, True) for p in rings_of(erode(reg, r, qs), region_right, exteriors=keep_exteriors(op, reg))]
    deep, flat = [], fin
    if getattr(op, 'finish_shut_levels', False) and len(zs) > 1 and fin and tool.kind not in ('conique', 'boule'):
        opened = opened_by(em.moves, zs[-1], r, qs)
        shut = reg.difference(opened) if opened is not None else reg
        seg = max(0.02, min(0.2, max(r, 1e-3) / 2))
        deep, flat = split_shut(fin, shut, reg, r, op.stock, seg, qs)
    kw = {'ramp': op.ramp, 'ramp_angle': ramp_angle_of(op)} if ramp else {}
    was, em.fin = em.fin, True                           # la passe de finition : à l'avance de finition
    try:
        cut_deep(em, deep, zs, em.pos if em.pos is not None else (0.0, 0.0), **kw)
        for pts, closed in order_chains(flat, em.pos if em.pos is not None else (0.0, 0.0)):
            cut_chain(em, pts, closed, [zs[-1]], **kw)
    finally:
        em.fin = was
    if deep:
        tp.warnings.append(f'poche : passe de finition à toutes les cotes sur {len(deep)} morceau(x), le long de '
                           'matière que l\'ébauche n\'a pas ouverte')


def _pocket_rest(doc, setup, op, tool, tp, em, here, reg, r, step, qs, tol) -> bool:
    """Poche, seulement le reste (ébauche puis finition, la gravure en deux outils) : les passes de la poche entière,
    gardées là seulement où leur outil enlève ce que les poches d'avant ont laissé — coins plus fins que leur outil,
    surépaisseur XY qu'elles ont laissée le long des bords. Ce qu'un outil au moins aussi gros (surépaisseur XY
    comprise) a déjà vidé n'est pas repassé : une passe n'est gardée que là où la pointe de l'outil (le flanc, pour la
    passe du bord) touche ce reste. Faux : aucune poche avant celle-ci, la poche entière est faite."""
    import shapely
    if tool.kind in ('conique', 'boule') and getattr(op, 'contour_ref', 'surface') == 'fond':
        tp.warnings.append('poche, seulement le reste : contour respecté au fond, le flanc de l\'outil taille hors du '
                           'contour ; poche entière')
        return False
    prevs = previous_pockets(setup, op)
    if not prevs:
        shy = floor_left_before(setup, op)
        if shy:                                          # vidée, mais du fond laissé : il est à faire partout
            tp.warnings.append(f'poche, seulement le reste : « {shy[-1].name or shy[-1].kind} » a laissé '
                               f'{left_on_floor(shy[-1]):g} mm au fond (surépaisseur Z), le fond est à faire '
                               'partout — poche entière')
        else:
            tp.warnings.append('poche, seulement le reste : aucune poche active avant celle-ci, poche entière')
        return False
    loose = [o for o in prevs if not clears_all(o, setup.tool(o.tool_id))]
    for o in loose:
        tp.warnings.append(f'poche, seulement le reste : « {o.name or o.kind} » non comptée (balayage sans tour du '
                           'contour ou texturé, ou passes plus écartées que l\'outil)')
    prevs = [o for o in prevs if all(o is not x for x in loose)]
    if not prevs:
        tp.warnings.append('poche, seulement le reste : aucune poche avant celle-ci qui vide tout, poche entière')
        return False
    done = [g for o in prevs if (g := cleared_by(doc, o, setup.tool(o.tool_id), tol)) is not None]
    done = shapely.union_all(done) if done else None
    stock = max(0.0, float(op.stock or 0.0))
    target = reg.buffer(-stock, quad_segs=qs) if stock > 0 else reg
    rest = target.difference(done) if done is not None else target
    rest = rest.buffer(-0.005, quad_segs=qs).buffer(0.005, quad_segs=qs)
    rf = max(floor_radius(op, tool), 1e-3)
    seg = max(0.02, min(0.2, rf / 2))
    m = max(1e-4, min(2 * tol, 0.05))                    # l'outil qui frôle le reste (arcs aplatis compris) : inutile

    def finish_walls(cut=None) -> int:
        """Passe de finition là où les poches d'avant n'ont pas fait la paroi, dans toutes les formes (même celles
        où rien d'autre ne reste). `cut` : ce que les passes de cette poche viennent d'ouvrir. Ce qui longe de la
        matière que personne n'a ouverte (une rainure où l'outil n'entre qu'à la finition, la pointe d'un coin
        aigu) est fait à toutes les cotes, comme un contour — le tronçon seulement, pour un tour fermé ; le reste,
        au fond seulement. Jamais ouverte : ce qui reste, hors de `cut`, dans ce que la finition balaie, là où
        c'est plus épais que ce qu'un coin droit garde (`thick_radius`) ; une surépaisseur seule ne l'est pas tant
        qu'elle reste sous 1,3 fois le rayon de l'outil (au-delà, les coins puis le tour entier le deviennent).
        Outil conique ou boule : au fond seulement (le flanc ouvre la matière à chaque passe). Rend le nombre de
        morceaux usinés."""
        if not (op.finish and op.stock > 0):
            return 0
        left = reg.difference(done) if done is not None else reg
        left = left.buffer(-0.005, quad_segs=qs).buffer(0.005, quad_segs=qs)     # sans les lamelles des arcs
        if left.is_empty:
            return 0
        keep = left.buffer(max(max(r, rf) - m, rf / 2), quad_segs=qs)
        shapely.prepare(keep)
        fin = [ch for pts in rings_of(erode(reg, r, qs), not op.climb, exteriors=keep_exteriors(op, reg))
               for ch in clip_chains(pts, keep, seg)]
        levels = op_levels(op, tool)
        reach = max(r, rf)
        deep, flat = [], list(fin)
        if len(levels) > 1 and fin and tool.kind not in ('conique', 'boule'):
            deep, flat = split_shut(fin, left if cut is None else left.difference(cut), reg, reach, op.stock, seg, qs)
        was, em.fin = em.fin, True                       # la passe de finition : à l'avance de finition
        try:
            cut_deep(em, deep, levels, em.pos if em.pos is not None else here, ramp=op.ramp,
                     ramp_angle=ramp_angle_of(op))
            for pts, closed in order_chains(flat, em.pos if em.pos is not None else here):
                cut_chain(em, pts, closed, [levels[-1]], ramp=op.ramp, ramp_angle=ramp_angle_of(op))
        finally:
            em.fin = was
        if deep:
            tp.warnings.append(f'poche, seulement le reste : passe de finition à toutes les cotes sur {len(deep)} '
                               'morceau(x), le long de matière jamais ouverte')
        return len(fin)
    if rest.is_empty:
        tp.warnings.append('poche, seulement le reste : rien à nettoyer au fond, passe de finition seule'
                           if finish_walls() else
                           'poche, seulement le reste : rien à nettoyer, les poches d\'avant ont tout vidé')
        return True
    tp.warnings.append(f'poche, seulement le reste : {rest.area:.2f} mm² laissés par les poches d\'avant')
    parts = [p for p in shapely.get_parts(reg) if p.geom_type == 'Polygon' and p.intersects(rest)]
    work = shapely.union_all(parts) if parts else reg     # seules les formes où il reste de la matière
    near_wall = rest.buffer(max(max(r, rf) - m, rf / 2), quad_segs=qs)   # passe du bord : son flanc touche le reste
    near_floor = rest.buffer(max(rf - m, rf / 2), quad_segs=qs)          # les autres : leur pointe (le fond) le touche
    shapely.prepare(near_wall)
    shapely.prepare(near_floor)
    region_right = not op.climb
    d0 = r + stock
    chains, first, last_d, emptied = [], None, None, False
    for k in range(10000):
        progress.check()
        d = d0 + k * step
        shell = erode(work, d, qs)
        if shell.is_empty:
            emptied = True
            break
        if k == 0:
            first = shell
        keep = near_wall if k == 0 else near_floor
        if not shell.intersects(keep):                   # les retraits suivants, plus petits, non plus
            break
        for pts in rings_of(simplify_parts(shell, tol / 2), region_right):
            chains += [(k, c, closed) for c, closed in clip_chains(pts, keep, seg)]
        last_d = d
    if emptied and last_d is not None and tool.kind == 'conique':
        # comme la poche : seule la pointe creuse le fond, passes intermédiaires jusqu'au milieu
        for j in (1, 2, 3):
            g = erode(work, last_d + j * step / 4, qs)
            if g.is_empty:
                break
            for pts in rings_of(simplify_parts(g, tol / 2), region_right):
                chains += [(k + j / 4, c, closed) for c, closed in clip_chains(pts, near_floor, seg)]
    if first is None or not chains:
        tp.warnings.append('poche, seulement le reste : rien que cet outil atteigne')
        finish_walls()
        return True
    zone = rest.buffer(max(r, rf) + step, quad_segs=qs)
    pieces = [p for p in shapely.get_parts(zone) if not p.is_empty]
    owners = shapely.STRtree(pieces).nearest(shapely.points([c[1][0][:2] for c in chains])).tolist()
    groups: list = [[] for _p in pieces]
    for ch, w in zip(chains, owners):
        groups[w].append(ch)
    outside_in = bool(getattr(op, 'pocket_outside_in', False))
    groups = [[(c, closed) for _k, c, closed in sorted(g, key=lambda x: x[0] if outside_in else -x[0])]
              for g in groups if g]                      # du centre vers le bord, comme la poche (sauf réglage)
    groups = _order_chain_groups(groups, here)
    zs = op_levels(op, tool)
    inside = within_test(erode(work, d0 - 1e-6, qs))
    angle = ramp_angle_of(op) if op.ramp else None
    helix = float(getattr(op, 'ramp_helix', 0.0) or 0.0)
    link_max = stay_down_length(op, tool, em.clear, zs[0], angle if helix > 0 else None)

    def max_link(_z):                                    # d'un reste au suivant : au fond seulement si c'est plus court ;
        return link_max                                  # la même limite à toutes les cotes
    for zi, gi, g in _pass_plan(op, zs, groups):
        with progress.span(gi / len(groups), (gi + 1) / len(groups)):
            mill_chains(em, g, zs, inside, angle, helix, only=zi, max_link=max_link)
    left = rest.difference(first.buffer(max(r, rf), quad_segs=qs)).area
    if left > 0.01:
        tp.warnings.append(f'poche, seulement le reste : {left:.2f} mm² hors de portée de cet outil '
                           '(coins plus fins que son rayon)')
    swept = [shapely.LineString([p[:2] for p in c]) for _k, c, _closed in chains if len(c) >= 2]
    finish_walls(shapely.union_all(swept).buffer(rf, quad_segs=qs) if swept else None)
    return True


def _pocket(doc, setup, op, tool, tp, em, here) -> None:
    geoms = [g for it in source_items(doc, op) if (g := item_geometry(it))]
    tol = setup.tolerance
    reg = region(geoms, tol)
    if reg.is_empty:
        tp.warnings.append('poche : aucun contour fermé')
        return
    r = cut_radius(op, tool)
    width = 2 * r if tool.kind in ('conique', 'boule') and r > 0 else tool.diameter   # largeur qui coupe vraiment
    step = max(0.05, (getattr(op, 'stepover_mm', 0.0) or 0.0) or (tool.stepover or 0.4) * width)
    if tool.kind == 'conique' and 0 < tool.angle < 180 and not getattr(op, 'stepover_mm', 0.0):
        # seule la pointe touche le fond : pas assez serré pour des crêtes d'au plus 0,02 mm
        step = min(step, max(0.01, 2 * (tool.tip / 2 + 0.02 * math.tan(math.radians(tool.angle) / 2))))
    qs = _quad_segs(max(r, tol), tol)
    if getattr(op, 'rest_previous', False) and _pocket_rest(doc, setup, op, tool, tp, em, here, reg, r, step, qs, tol):
        return
    from ..core import workers
    # premier anneau et zone permise au centre de l'outil : en même temps (fils de calcul). La surépaisseur en est exclue : une liaison au fond ne l'entame pas
    first, allowed = workers.pmap(lambda d: erode(reg, d, qs), [r + op.stock, r + op.stock - 1e-6])
    if first.is_empty:
        tp.warnings.append('poche : outil trop gros pour la forme')
        return
    lost = lost_parts(reg, first)
    if lost:
        tp.warnings.append(f'poche : {lost} zone(s) plus étroite(s) que l\'outil, non usinée(s)')
    rank = drawing_rank(geoms, tol, r + op.stock)
    if getattr(op, 'pocket_mode', 'concentrique') == 'balayage':
        if getattr(op, 'sweep_rule', 0) >= 876 and not getattr(op, 'sweep_texture', False):
            _sweep_te(doc, setup, op, tool, tp, em, here, reg, first, step, tol, qs)
        else:
            _sweep_pocket(op, tool, tp, em, here, reg, first, allowed, step, tol, qs)
        return
    # anneaux concentriques, du bord vers le centre ; chacun décalé depuis
    # la région d'origine (décaler un décalage accumule les sommets)
    raw = [first] + erosions(reg, [r + op.stock + k * step for k in range(1, 10000)], qs)
    shells = workers.pmap(lambda g: simplify_parts(g, tol / 2), raw)
    if tool.kind == 'conique' and shells:
        # outil conique : seule la pointe creuse le fond ; le milieu, entre la
        # dernière passe et le décalage suivant (vide), garde une crête — passes
        # intermédiaires jusqu'au milieu
        last = r + op.stock + (len(shells) - 1) * step
        for k in (1, 2, 3):
            g = erode(reg, last + k * step / 4, qs)
            if g.is_empty:
                break
            shells.append(simplify_parts(g, tol / 2))
    region_right = not op.climb                           # matière à garder autour : à gauche si avalant
    zs = op_levels(op, tool)
    # forme par forme (toutes ses passes, du centre vers le bord), au plus proche
    outside_in = bool(getattr(op, 'pocket_outside_in', False))
    inside = within_test(allowed)
    spiral = bool(getattr(op, 'pocket_spiral', False))
    spur_angle = float(op.corner_opt_angle or 135.0) if getattr(op, 'corner_opt', False) else 0.0
    wide, auto_spurs = False, False
    if tool.kind not in ('conique', 'boule') and r + 1e-6 < step <= 2 * r + 1e-6:
        # passes plus écartées que le rayon : entre elles resterait une lamelle dans les coins vifs (reprise d'angle)
        # et un îlot au centre ou là où la forme se resserre (un tour le long de son bord, mesuré sur le parcours)
        wide = True
        if spiral:                                       # une spirale en laisserait davantage, entre ses tours
            spiral = False
            tp.warnings.append('poche : pas plus large que le rayon de l\'outil, passes en anneaux plutôt qu\'en '
                               'spirale (elle laisserait de la matière entre ses tours)')
        if not spur_angle:                               # d'office, aux seuls coins qui laisseraient une lamelle :
            auto_spurs = True                            # pas > R (1 + sin(angle / 2))
            spur_angle = math.degrees(2 * math.asin(min(1.0, step / r - 1.0)))
    if spiral:
        groups = spiral_groups(reg, shells, region_right, outside_in, step, inside)
        missed = spiral_leftover(groups, first, r, region_right, qs, tol)
        if any(missed):                                  # un tour le long de chaque reste, après les spirales
            groups = [g + [(pts, True) for pts in more] for g, more in zip(groups, missed)]
            tp.warnings.append(f'poche : {sum(len(m) for m in missed)} reste(s) entre les tours des spirales, '
                               'repris')
        groups = sorted(groups, key=lambda g: rank(g[0][0])) if rank is not None else _order_chain_groups(groups, here)
        nsp = sum(1 for g in groups for _c, closed in g if not closed)
        tp.warnings.append(f'poche : {nsp} spirale(s)')
        for zi, gi, chains in _pass_plan(op, zs, groups):
            with progress.span(gi / len(groups), (gi + 1) / len(groups)):
                mill_chains(em, chains, zs, inside, ramp_angle_of(op) if op.ramp else None,
                            float(getattr(op, 'ramp_helix', 0.0) or 0.0), only=zi)
    else:
        groups = shape_groups(reg, shells, region_right)
        groups = sorted(groups, key=lambda g: rank(g[0])) if rank is not None else order_groups(groups, here)
        if outside_in:
            groups = [g[::-1] for g in groups]
        if spur_angle > 0:
            nspur = 0
            new_groups = []
            for g in groups:
                rings = []
                for pts in g:                            # d'office : pas de reprise de quelques microns (arcs)
                    q, k = corner_spurs(pts, step, spur_angle, inside, 0.05 if auto_spurs else 0.0)
                    rings.append(q)
                    nspur += k
                new_groups.append(rings)
            groups = new_groups
            if not auto_spurs:
                tp.warnings.append(f'poche : {nspur} reprise(s) d\'angle')
            elif nspur:
                tp.warnings.append(f'poche : {nspur} reprise(s) d\'angle, entre des passes plus écartées que le rayon '
                                   'de l\'outil')
        if wide:                                         # ce qui reste encore, mesuré sur ces anneaux et ces reprises :
            missed = spiral_leftover([[(pts, True) for pts in g] for g in groups], first, r, region_right, qs, tol)
            if any(missed):                              # un tour le long de son bord, à la fin de chaque cote
                groups = [g + more for g, more in zip(groups, missed)]
                tp.warnings.append(f'poche : {sum(len(m) for m in missed)} îlot(s) repris entre des passes plus '
                                   'écartées que le rayon de l\'outil')
        link = ramp_angle_of(op) if getattr(op, 'link_passes', False) else None
        for zi, gi, order in _pass_plan(op, zs, groups):
            with progress.span(gi / len(groups), (gi + 1) / len(groups)):
                mill_rings(em, order, zs, allowed, ramp_angle_of(op) if op.ramp else None, inside=inside,
                           helix=float(getattr(op, 'ramp_helix', 0.0) or 0.0), only=zi, link_angle=link)
    tp.cycles = shape_cycles(doc, op, 'poche', abs(op.depth), op.step_down or tool.step_down,
                             int(round((tool.stepover or 0.4) * 100)))
    if op.finish and op.stock > 0:
        finish_pass(em, op, tool, tp, reg, region_right, zs, qs, ramp=True)


def sweep_best_angle(zone) -> float:
    """Angle « Optimisé », relevé dans TE13 : le long des côtés de la forme qui font ensemble le plus de longueur (un U : le long de ses
    bras, même s'il est plus large que haut). Entre ]-90 ; 90] ; à égalité, comme TE : l'angle le plus grand, en négatif."""
    totals: dict = {}
    for ring in [zone.exterior, *zone.interiors]:
        c = list(ring.coords)
        for a, b in zip(c, c[1:]):
            n = math.dist(a[:2], b[:2])
            if n > 1e-9:
                d = round(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180.0, 1)
                totals[d] = totals.get(d, 0.0) + n
    if not totals:
        return 0.0
    top = max(totals.values())
    best = [a - 180.0 if a > 90.0 else a for a, v in totals.items() if v >= top - 1e-3]
    return best[0] if len(best) == 1 else -max(abs(a) for a in best)


def sweep_rows(zone, angle: float, step: float):
    """Rangées d'une zone, relevées dans TE13 : à l'angle donné, tous les `step` depuis le bas de la zone, la rangée sur le bas lui-même exclue (celle
    du haut comprise si elle tombe sur le bord). Du haut vers le bas ; chaque segment [début, fin] va vers les x croissants du repère de l'angle. None
    si le pas est trop fin. Calculées un rien sous leur cote : une rangée posée sur un bord de la forme la traverse entièrement, comme dans TE."""
    from shapely import affinity
    rot = affinity.rotate(zone, -angle, origin=(0, 0))
    if rot.is_empty:
        return []
    rows = _hatch_rows(zone, angle, step, rot.bounds[1] - step / 2 - 1e-7)
    if rows is None:
        return None
    out = []
    for k, row in enumerate(rows):
        if k % 2:                                        # _hatch_rows les rend en aller-retour
            row = [c[::-1] for c in reversed(row)]
        if row:
            out.append(row)
    return out[::-1]


class _ZoneEdges:
    """Bords d'une zone et bouts des rangées posés dessus : qui est voisin de qui en suivant le bord, et le chemin de l'un à l'autre."""

    def __init__(self, zone, rows):
        import numpy as np
        import shapely
        self.rings = [list(r.coords) for r in [zone.exterior, *zone.interiors]]
        self.cums = [_cum(c) for c in self.rings]
        keys = [(k, j, e) for k, row in enumerate(rows) for j in range(len(row)) for e in (0, 1)]
        self.at: dict = {}
        self.turns: list = [[] for _ in self.rings]
        if not keys:
            return
        points = shapely.points([rows[k][j][e][:2] for k, j, e in keys])
        lines = [shapely.linestrings(c) for c in self.rings]
        dist = np.array([shapely.distance(points, r) for r in lines])
        which = dist.argmin(axis=0)
        for ri, line in enumerate(lines):
            idx = np.nonzero(which == ri)[0]
            if not len(idx):
                continue
            pos = shapely.line_locate_point(line, points[idx])
            for i in np.argsort(pos, kind='stable').tolist():
                key = keys[int(idx[i])]
                self.at[key] = (ri, len(self.turns[ri]), float(pos[i]))
                self.turns[ri].append(key)

    def neighbours(self, key) -> list:
        """Les bouts voisins sur le bord : [(bout, sens)], sens +1 dans le sens du bord, -1 à l'inverse."""
        if key not in self.at:
            return []
        ri, i, _s = self.at[key]
        turn = self.turns[ri]
        return [] if len(turn) < 2 else [(turn[(i + 1) % len(turn)], 1), (turn[(i - 1) % len(turn)], -1)]

    def path(self, a, b, sense: int) -> list:
        """Points du bord entre les bouts a et b, les deux exclus."""
        from bisect import bisect_left, bisect_right
        ri, _i, sa = self.at[a]
        ring, cum = self.rings[ri], self.cums[ri]
        n, L = len(ring) - 1, cum[-1]                     # le dernier point répète le premier
        span = self.length(a, b, sense)
        i = bisect_right(cum, sa + 1e-7) if sense > 0 else bisect_left(cum, sa - 1e-7) - 1
        out = []
        for _k in range(n):
            i %= n
            d = (cum[i] - sa) % L if sense > 0 else (sa - cum[i]) % L
            if d >= span - 1e-7:
                break
            out.append(ring[i])
            i += sense
        return out

    def length(self, a, b, sense: int) -> float:
        L = self.cums[self.at[a][0]][-1]
        sa, sb = self.at[a][2], self.at[b][2]
        return (sb - sa) % L if sense > 0 else (sa - sb) % L


def sweep_chains(zone, rows, direction: str = 'aller_retour') -> list:
    """Passes d'une zone, comme TE13 : chaque chaîne commence par une rangée parcourue vers les x décroissants du repère (« en avalant » : croissants), puis passe à la
    rangée du dessous si son bout est le voisin immédiat sur le bord (aucun autre bout de rangée entre les deux), sinon s'arrête. Dans le même sens (opposition, avalant),
    la rangée suivante repart du même côté. Rend [chaîne], chaîne : liste de morceaux [(segment, liaison)] ; `liaison` : points du bord avant le segment, [] pour le premier."""
    edges = _ZoneEdges(zone, rows)
    used: set = set()
    chains = []
    start_end = 1 if direction == 'avalant' else 0        # le bout atteint à la fin de la première rangée : 0, le x le plus bas
    for k0, row in enumerate(rows):
        for j0 in range(len(row)):
            if (k0, j0) in used:
                continue
            used.add((k0, j0))
            chain = [(row[j0] if start_end else row[j0][::-1], [])]
            k, j, end = k0, j0, start_end
            while k + 1 < len(rows):
                best = None
                for other, sense in edges.neighbours((k, j, end)):
                    if other[0] == k + 1 and (other[0], other[1]) not in used and (direction == 'aller_retour' or other[2] == end):
                        n = edges.length((k, j, end), other, sense)
                        if best is None or n < best[0]:
                            best = (n, other, sense)
                if best is None:
                    break
                _n, other, sense = best
                link = edges.path((k, j, end), other, sense)
                k, j = other[0], other[1]
                used.add((k, j))
                if direction == 'aller_retour':
                    seg = rows[k][j] if other[2] == 0 else rows[k][j][::-1]
                    end = 1 - other[2]
                else:
                    seg = rows[k][j] if start_end else rows[k][j][::-1]
                chain.append((seg, link))
            chains.append(chain)
    return chains


def _order_sweep_chains(chains: list) -> list:
    """TE13 : la première, puis au plus proche du départ de chacune."""
    if not chains:
        return []
    rest, out = list(chains[1:]), [chains[0]]
    while rest:
        pos = out[-1][-1][0][-1]
        i = min(range(len(rest)), key=lambda n: math.dist(rest[n][0][0][0][:2], pos[:2]))
        out.append(rest.pop(i))
    return out


def _sweep_entry(em, pts: list, z_from: float, z: float, angle) -> None:
    """Entrée d'une passe de balayage. En plongée angulaire, relevé dans TE13 : l'outil part de la passe d'avant le long de son trajet, puis revient au point de
    départ en continuant de descendre. Trajet trop court : autant d'allers et retours qu'il faut pour tenir l'angle."""
    em.travel(*pts[0][:2])
    if angle is None or z >= z_from:
        em.plunge(z)
        return
    em.plunge(z_from)
    cum = _cum(pts)
    half = (z_from - z) / math.tan(math.radians(angle)) / 2
    turns = max(1, int(math.ceil(half / cum[-1] - 1e-9))) if cum[-1] > 1e-9 else 0
    if not turns:
        em.plunge(z)
        return
    half = min(half, cum[-1])
    dz = (z_from - z) / (2 * turns)
    tip = _point_at(pts, cum, half)
    between = [(p, s) for p, s in zip(pts, cum) if 1e-9 < s < half - 1e-9]
    zz = z_from
    for _k in range(turns):
        for p, s in between:
            em.feed(p[0], p[1], zz - dz * s / half)
        zz -= dz
        em.feed(tip[0], tip[1], zz)
        for p, s in between[::-1]:
            em.feed(p[0], p[1], zz - dz * (1.0 - s / half))
        zz -= dz
        em.feed(pts[0][0], pts[0][1], zz)


def _sweep_zone_level(op, em, zone, angle, step, tp, z, z_from, ramp, contour, memo: dict) -> None:
    """Une passe sur une zone : cassé d'angle avant ou après, rangées en chaînes, comme TE13."""
    when = getattr(op, 'sweep_contour', 'apres')
    direction = getattr(op, 'sweep_direction', 'aller_retour')

    def ring_pass():
        for pts, _c in contour:
            _sweep_entry(em, pts, z_from, z, ramp)
            for p in pts[1:]:
                em.feed(p[0], p[1], z)

    key = (id(zone), round(angle, 6))
    if key not in memo:                                   # les mêmes rangées à chaque passe
        rows = sweep_rows(zone, angle, step)
        if rows is None:
            tp.warnings.append('balayage : pas trop fin pour cette surface')
            rows = []
        by_zone = getattr(op, 'sweep_by_zone', True)
        memo[key] = (rows, _order_sweep_chains(sweep_chains(zone, rows, direction)) if by_zone else [])
    rows, chains = memo[key]
    if when == 'avant':
        ring_pass()
    if getattr(op, 'sweep_by_zone', True):
        for chain in chains:
            if direction == 'aller_retour':
                first = chain[0][0]
                _sweep_entry(em, first, z_from, z, ramp)
                for seg, link in chain:
                    for p in link:
                        em.feed(p[0], p[1], z)
                    for p in seg:
                        em.feed(p[0], p[1], z)
            else:
                # chaque rangée dans le même sens : l'outil remonte entre deux
                for seg, _link in chain:
                    _sweep_entry(em, list(seg), z_from, z, ramp)
                    em.feed(seg[-1][0], seg[-1][1], z)
    else:
        # avec sauts d'îlots, relevé dans TE13 : rangée après rangée, en sautant ce qui n'est pas à usiner ; la rangée du bas va vers les x croissants
        count = len(rows)
        for k, row in enumerate(rows):
            segs = row if (count - 1 - k) % 2 == 0 else [c[::-1] for c in reversed(row)]
            for seg in segs:
                if direction != 'aller_retour':
                    down = direction == 'opposition'
                    seg = sorted(seg, key=lambda p: _along(p, angle), reverse=down)
                _sweep_entry(em, list(seg), z_from, z, ramp)
                for p in seg[1:]:
                    em.feed(p[0], p[1], z)
    if when == 'apres':
        ring_pass()


def _ring_area(pts: list) -> float:
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:])) / 2


def _along(p, angle: float) -> float:
    a = math.radians(angle)
    return p[0] * math.cos(a) + p[1] * math.sin(a)


def _sweep_te(doc, setup, op, tool, tp, em, here, reg, first, step, tol, qs) -> None:
    """Balayage relevé dans TE13 : forme par forme (passe par passe sur tout le dessin en ordre global, sinon chaque forme jusqu'au fond)."""
    from shapely.geometry import LineString
    zones = _nearest_first(_solid_parts(first), em.pos[:2] if em.pos is not None else here)
    zs = op_levels(op, tool)
    region_right = not op.climb
    ramp = ramp_angle_of(op) if op.ramp else None
    cs = float(getattr(op, 'sweep_contour_stock', -1.0))
    ring = first
    if 0 <= cs < op.stock:                                # cassé d'angle plus près du bord que les hachures
        ring = erode(reg, cut_radius(op, tool) + cs, qs)
        tp.warnings.append(f'balayage : surépaisseur {op.stock:g} mm sur les hachures, {cs:g} mm au cassé d\'angle')
    starts = start_marks(doc, op, tol)
    near = 3.0 * (cut_radius(op, tool) + op.stock) + 10 * tol
    plan = {}
    mode = getattr(op, 'sweep_angle_mode', 'fixe')
    start = float(getattr(op, 'sweep_angle', 0.0) or 0.0)
    incr = float(getattr(op, 'sweep_angle_incr', 90.0) or 0.0)
    for zi, zone in enumerate(zones):
        near_zone = zone.buffer(abs(op.stock - max(cs, 0.0)) + op.stock + 1e-3)
        rings = [pts for pts in rings_of(ring, region_right) if near_zone.intersects(LineString([p[:2] for p in pts]))]
        if len(rings) > 1:                                # relevé dans TE13 : les trous d'abord, le bord extérieur ensuite
            rings.sort(key=lambda pts: abs(_ring_area(pts)))
        chains = apply_starts([(p, True) for p in rings], starts, near, cut_radius(op, tool) + op.stock)[0] if starts else [(p, True) for p in rings]
        plan[zi] = (zone, sweep_best_angle(zone) if mode == 'optimise' else start, chains)
    if getattr(op, 'sweep_contour', 'apres') == 'sans':
        plan = {zi: (z, a, []) for zi, (z, a, _c) in plan.items()}

    memo: dict = {}

    def level(zi, li):
        zone, base, contour = plan[zi]
        angle = base + li * incr if mode == 'croise' else base
        _sweep_zone_level(op, em, zone, angle, step, tp, zs[li], zs[li - 1] if li else 0.0, ramp, contour, memo)

    if getattr(op, 'pass_order', 'poche') == 'global':
        for li in range(len(zs)):
            for zi in plan:
                level(zi, li)
    else:
        for zi in plan:
            for li in range(len(zs)):
                level(zi, li)
    if op.finish and op.stock > 0:
        finish_pass(em, op, tool, tp, reg, region_right, zs, qs)


def sweep_angles(op, zone) -> list[float]:
    """Angles des passes d'un balayage : fixe ; optimisé (le long du grand côté
    du plus petit rectangle qui contient la zone : moins de remontées) ;
    croisé (X et Y : l'angle puis +90°)."""
    mode = getattr(op, 'sweep_angle_mode', 'fixe')
    a = float(getattr(op, 'sweep_angle', 0.0) or 0.0)
    if mode == 'optimise' and not zone.is_empty:
        rect = zone.minimum_rotated_rectangle
        c = list(rect.exterior.coords) if rect.geom_type == 'Polygon' else []
        if len(c) >= 3:
            e = max(((c[0], c[1]), (c[1], c[2])), key=lambda s: math.dist(*s))
            a = math.degrees(math.atan2(e[1][1] - e[0][1], e[1][0] - e[0][0]))
    return [a, a + 90.0] if mode == 'croise' else [a]


def _sweep_pocket(op, tool, tp, em, here, reg, first, allowed, step, tol, qs, finish: bool = True) -> None:
    """Balayage (TypeEdit) : évidage par passes parallèles à l'angle choisi,
    en aller-retour sans remonter tant que la liaison reste dans la poche,
    ou toutes dans le même sens (en opposition / en avalant) ; tour du
    contour (cassé d'angle) avant ou après."""
    from shapely.geometry import LineString
    by_zone = bool(getattr(op, 'sweep_by_zone', False))
    zones = _solid_parts(first) if by_zone else []
    if len(zones) > 1:                                   # TypeEdit : une zone entière, avant de commencer la suivante
        for zone in _nearest_first(zones, em.pos[:2] if em.pos is not None else here):
            _sweep_pocket(op, tool, tp, em, here, reg, zone, allowed, step, tol, qs, finish=False)
        if finish and op.finish and op.stock > 0:        # la finition une fois, après toutes les zones
            finish_pass(em, op, tool, tp, reg, not op.climb, op_levels(op, tool), qs)
        return
    inside = within_test(allowed)
    region_right = not op.climb
    cs = float(getattr(op, 'sweep_contour_stock', -1.0))
    ring = first
    if 0 <= cs < op.stock:                               # cassé d'angle plus près du bord que les hachures
        ring = erode(reg, cut_radius(op, tool) + cs, qs)
        note = f'balayage : surépaisseur {op.stock:g} mm sur les hachures, {cs:g} mm au cassé d\'angle'
        if note not in tp.warnings:
            tp.warnings.append(note)
    contour = [pts for pts in rings_of(ring, region_right)]
    if by_zone:                                          # le cassé d'angle de cette zone seulement
        near = first.buffer(op.stock + 1e-3)
        contour = [pts for pts in contour if near.intersects(LineString([p[:2] for p in pts]))]
    direction = getattr(op, 'sweep_direction', 'aller_retour')
    when = getattr(op, 'sweep_contour', 'apres')
    nets = []
    for a in sweep_angles(op, first):
        rows = _hatch_rows(first, a, step)
        if rows is None:
            tp.warnings.append('balayage : pas trop fin pour cette surface')
            return
        segs = [c for row in rows for c in row]
        if direction != 'aller_retour':
            ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
            want = 1.0 if direction == 'avalant' else -1.0
            segs = [c if ((c[-1][0] - c[0][0]) * ca + (c[-1][1] - c[0][1]) * sa) * want >= 0 else c[::-1]
                    for c in segs]
        nets.append(segs)
    zs = op_levels(op, tool)
    if getattr(op, 'sweep_texture', False):
        _texture_strokes(op, em, nets)
        return

    def contour_pass(z):
        for pts, _c in order_chains([(p, True) for p in contour], em.pos or here):
            cut_chain(em, pts, True, [z])
    for z in zs:
        if when == 'avant':
            contour_pass(z)
        for segs in nets:
            for c in segs:
                if em.pos is not None and em.pos[2] <= z + 1e-9 and \
                        inside(LineString([em.pos[:2], c[0][:2]])):
                    em.feed(c[0][0], c[0][1], z)             # liaison dans la poche, sans remonter
                else:
                    em.travel(*c[0][:2])
                    em.plunge(z)
                for p in c[1:]:
                    em.feed(p[0], p[1], z)
        if when == 'apres':
            contour_pass(z)
    if finish and op.finish and op.stock > 0:
        finish_pass(em, op, tool, tp, reg, region_right, zs, qs)


def texture_strokes(segs: list, op, rnd) -> list[list[tuple[float, float, float]]]:
    """Coups de gouge le long des passes : longueur au hasard entre
    tex_len_min et tex_len_max, profondeur entre tex_depth_min et
    tex_depth_max (creux au milieu du coup, à fleur aux bouts), chaque coup
    reprenant le précédent de `tex_overlap` %."""
    lo_l, hi_l = sorted((max(0.05, op.tex_len_min), max(0.05, op.tex_len_max)))
    lo_d, hi_d = sorted((abs(op.tex_depth_min), abs(op.tex_depth_max)))
    ov = min(0.9, max(0.0, op.tex_overlap / 100.0))
    out = []
    for c in segs:
        cum = _cum(c)
        L = cum[-1]
        s = 0.0
        while s < L - 1e-6:
            ln = rnd.uniform(lo_l, hi_l)
            e = min(L, s + ln)
            depth = rnd.uniform(lo_d, hi_d)
            n = max(4, int((e - s) / 0.2))
            n += n % 2                                     # nombre pair : le creux du coup est atteint
            pts = []
            for k in range(n + 1):
                t = s + (e - s) * k / n
                x, y = _point_at(c, cum, t)[:2]
                pts.append((x, y, -depth * math.sin(math.pi * k / n)))
            out.append(pts)
            if e >= L - 1e-6:
                break
            s = e - (e - s) * ov
    return out


def _texture_strokes(op, em, nets) -> None:
    """Balayage texturé : chaque coup est une descente en arc jusqu'à sa
    profondeur puis une remontée, l'outil restant à l'approche entre deux."""
    import random
    rnd = random.Random(int(getattr(op, 'tex_seed', 1)))
    for segs in nets:
        for pts in texture_strokes(segs, op, rnd):
            em.travel(pts[0][0], pts[0][1])
            em.plunge(pts[0][2])
            for x, y, z in pts[1:]:
                em.feed(x, y, z)


#: perçage : points percés parmi les objets choisis (TypeEdit : filtre de sélection)
DRILL_POINTS = {'cercles': 'Centres des cercles et marqueurs', 'marqueurs': 'Marqueurs seulement',
                'depart': 'Point de départ des traits ouverts', 'arrivee': "Point d'arrivée des traits ouverts",
                'depart_arrivee': 'Départ et arrivée (contours fermés : départ)',
                'centres': 'Centre des contours fermés (braille)'}
DRILL_MODES = {'debourrage': 'En passes, remontée au dégagement', 'brise_copeau': 'En passes, petit recul (brise-copeau)',
               'simple': 'Une seule passe'}
#: recul du brise-copeau (mm)
CHIP_BREAK = 0.3


def hole_centers(doc, op) -> list[tuple[float, float, float]]:
    """(x, y, rayon) des trous à percer, selon `op.drill_points` (rayon 0 : un point)."""
    from ..core import forms as F
    from ..core.holes import circle_of
    mode = getattr(op, 'drill_points', 'cercles') or 'cercles'
    out = []
    for it in source_items(doc, op):
        sp = F.spec_of(it) if isinstance(it, Shape) else None
        if sp is not None and getattr(sp, 'kind', '') == 'marker':
            if mode in ('cercles', 'marqueurs'):
                out.append((float(sp.cx), float(sp.cy), 0.0))
            continue
        if mode == 'cercles':
            c = circle_of(it)
            if c is not None:
                out.append(c)
        elif mode in ('depart', 'arrivee', 'depart_arrivee', 'centres') and isinstance(it, Shape):
            for c in it.path.contours:
                if not c.segments:
                    continue
                if mode == 'centres':
                    if c.closed:
                        from ..core.cadtools import mass_properties
                        g = mass_properties(Path([c]))
                        if g and g.get('area', 0) > 1e-12:
                            out.append((*g['centroid'], 0.0))
                    continue
                if mode in ('depart', 'depart_arrivee') and (not c.closed or mode == 'depart_arrivee'):
                    out.append((*c.start, 0.0))
                if not c.closed and mode in ('arrivee', 'depart_arrivee'):
                    out.append((*c.segments[-1].end, 0.0))
    return out


def _drill(doc, setup, op, tool, tp, em, here) -> None:
    holes = hole_centers(doc, op)
    if not holes:
        tp.warnings.append('perçage : aucun cercle parmi les objets choisis'
                           if getattr(op, 'drill_points', 'cercles') == 'cercles' else
                           'perçage : aucun point à percer parmi les objets choisis (voir « Points percés »)')
        return
    mode = getattr(op, 'drill_mode', 'debourrage')
    slow = bool(getattr(op, 'drill_feed_retract', False))

    def up(x, y, z):                                     # remontée : rapide, ou en vitesse de travail
        em.moves.append(Move('feed' if slow else 'rapid', x, y, z))
        em.pos = (x, y, z)
    big = [h for h in holes if h[2] > tool.diameter / 2 + 0.01]
    if big:
        tp.warnings.append(f'perçage : {len(big)} cercle(s) plus grand(s) que le foret '
                           '(percés au centre ; utiliser une poche pour les agrandir)')
    rest = list(holes)
    pos = here
    depth = abs(op.depth)
    while rest:
        h = min(rest, key=lambda c: math.dist(c[:2], pos[:2]))
        rest.remove(h)
        em.travel(h[0], h[1])
        if op.peck > 0 and op.peck < depth and mode != 'simple':
            z = 0.0
            while z > -depth + 1e-9:
                z = max(-depth, z - op.peck)
                em.plunge(z)
                if z > -depth + 1e-9:
                    if mode == 'brise_copeau':               # petit recul, sans sortir du trou
                        up(h[0], h[1], z + CHIP_BREAK)
                    else:
                        up(h[0], h[1], op.clear_z)
                        em.moves.append(Move('rapid', h[0], h[1], z + 0.1))
                        em.pos = (h[0], h[1], z + 0.1)
        else:
            em.plunge(-depth)
        up(h[0], h[1], op.clear_z)
        pos = h


# --- trous : taraudage, perçage à la fraise, ébavurage (opérations de NeoDrive) ---------------
def _helix(em: Emitter, cx: float, cy: float, r: float, z_from: float, z_to: float, pitch: float,
           ccw: bool, step_deg: float = 10.0, a0: float = 0.0) -> float:
    """Hélice de rayon r autour de (cx, cy), de z_from à z_to, `pitch` par
    tour, depuis l'angle `a0` (radians ; 0 : le point (cx + r, cy)) ;
    aplatie tous les `step_deg`. Rend l'angle d'arrivée."""
    turns = abs(z_to - z_from) / max(pitch, 1e-6)
    n = max(1, int(math.ceil(turns * 360.0 / step_deg)))
    sign = 1.0 if ccw else -1.0
    a = a0
    for k in range(1, n + 1):
        t = k / n
        a = a0 + sign * math.radians(turns * 360.0 * t)
        em.feed(cx + r * math.cos(a), cy + r * math.sin(a), z_from + (z_to - z_from) * t)
    return a


def tangent_arc(p, tangent, center, sweep_deg: float, arrive: bool, step_deg: float = 10.0) -> list:
    """Arc de cercle de centre `center` passant par `p` avec la tangente
    `tangent` en p : `arrive` — l'arc de `sweep_deg` qui finit en p ; sinon
    celui qui en part. Points (sans p à l'arrivée, sans p au départ)."""
    R = math.dist(p, center)
    th = math.atan2(p[1] - center[1], p[0] - center[0])
    sgn = 1.0 if (-math.sin(th) * tangent[0] + math.cos(th) * tangent[1]) >= 0 else -1.0
    sw = math.radians(sweep_deg)
    n = max(2, int(math.ceil(sweep_deg / step_deg)))
    if arrive:
        angs = [th - sgn * sw * (1 - k / n) for k in range(n)]
    else:
        angs = [th + sgn * sw * k / n for k in range(1, n + 1)]
    return [(center[0] + R * math.cos(a), center[1] + R * math.sin(a)) for a in angs]


def _circle_at(em: Emitter, cx: float, cy: float, r: float, z: float, ccw: bool, step_deg: float = 10.0) -> None:
    """Un tour complet à la cote z, depuis la position courante sur le cercle."""
    a0 = math.atan2(em.pos[1] - cy, em.pos[0] - cx)
    n = int(math.ceil(360.0 / step_deg))
    sign = 1.0 if ccw else -1.0
    for k in range(1, n + 1):
        a = a0 + sign * 2 * math.pi * k / n
        em.feed(cx + r * math.cos(a), cy + r * math.sin(a), z)


def _near_order(holes, here):
    rest, pos = list(holes), here
    while rest:
        h = min(rest, key=lambda c: math.dist(c[:2], pos[:2]))
        rest.remove(h)
        yield h
        pos = h


def _thread(doc, setup, op, tool, tp, em, here) -> None:
    """Taraudage à la fraise à fileter : au centre de chaque cercle, hélice
    du filetage (Ø nominal, pas ISO ou choisi) — avalant : du fond vers le
    haut ; en opposition : du haut vers le fond."""
    from .model import THREADS
    holes = hole_centers(doc, op)
    if not holes:
        tp.warnings.append('taraudage : aucun cercle parmi les objets choisis')
        return
    name = op.thread if op.thread in THREADS else 'M4'
    nominal, iso_pitch, pre = THREADS[name]
    pitch = op.pitch or iso_pitch
    ext = bool(getattr(op, 'thread_external', False))
    r = nominal / 2 + tool.diameter / 2 if ext else nominal / 2 - tool.diameter / 2
    if r <= 0.02:
        tp.warnings.append(f'taraudage : fraise trop grosse pour {name} (Ø {tool.diameter:g} mm)')
        return
    depth = abs(op.depth)
    # filet à droite : sens trigonométrique en remontant (avalant), horaire en descendant ;
    # filetage (dehors) : sens inverse pour le même filet en avalant
    up = op.climb
    ccw = (not op.thread_left) if up else op.thread_left
    if ext:
        ccw = not ccw
    a0 = math.radians(float(getattr(op, 'thread_start_angle', 0.0) or 0.0))
    arc = getattr(op, 'thread_lead', 'droit') == 'arc'
    d = max(0.05, float(getattr(op, 'thread_lead_dist', 1.0) or 1.0))
    for cx, cy, rc in _near_order(holes, here):
        if not ext and abs(2 * rc - pre) > 0.3 and abs(2 * rc - nominal) > 0.3:
            tp.warnings.append(f'taraudage {name} : cercle de Ø {2 * rc:.2f} mm (avant-trou attendu Ø {pre:g})')
        z_from, z_to = (-depth, 0.0) if up else (0.0, -depth)
        u = (math.cos(a0), math.sin(a0))
        S = (cx + r * u[0], cy + r * u[1])
        t = (-u[1], u[0]) if ccw else (u[1], -u[0])
        if ext:                                          # dehors : de la distance d'entrée vers le filet
            start = (S[0] + d * u[0], S[1] + d * u[1])
            lead = tangent_arc(S, t, start, 90.0, True) if arc else []
            em.travel(*(lead[0] if lead else start))
        else:                                            # dedans : du centre du trou
            lead = tangent_arc(S, t, (cx + r / 2 * u[0], cy + r / 2 * u[1]), 180.0, True) if arc else []
            em.travel(cx, cy)
        em.plunge(z_from)
        for q in lead[1:] if ext else lead:
            em.feed(q[0], q[1], z_from)
        em.feed(S[0], S[1], z_from)                      # sur le filet
        ae = _helix(em, cx, cy, r, z_from, z_to, pitch, ccw, a0=a0)
        ue = (math.cos(ae), math.sin(ae))
        E = (cx + r * ue[0], cy + r * ue[1])
        te = (-ue[1], ue[0]) if ccw else (ue[1], -ue[0])
        if arc:                                          # sortie tangente
            c_out = (E[0] + d * ue[0], E[1] + d * ue[1]) if ext else (cx + r / 2 * ue[0], cy + r / 2 * ue[1])
            for q in tangent_arc(E, te, c_out, 90.0 if ext else 180.0, False):
                em.feed(q[0], q[1], em.pos[2])
        elif ext:
            em.feed(E[0] + d * ue[0], E[1] + d * ue[1], em.pos[2])
        else:
            em.feed(cx, cy, em.pos[2])                   # dégagement au centre
        em.retract()
        tp.cycles.append({'kind': 'taraudage', 'x': cx, 'y': cy, 'depth': depth, 'thread': name,
                          'pitch': pitch, 'left': op.thread_left, 'climb': op.climb})


def _helix_bore(doc, setup, op, tool, tp, em, here) -> None:
    """Perçage à la fraise : hélice descendante au Ø du trou (passe en Z
    par tour), un tour au fond, retour au centre."""
    holes = hole_centers(doc, op)
    if not holes:
        tp.warnings.append('perçage à la fraise : aucun cercle parmi les objets choisis')
        return
    depth = abs(op.depth)
    step = op.step_down or tool.step_down or 0.2
    rt = tool.diameter / 2
    ccw = op.climb                                       # trou : matière dehors, avalant = sens trigo
    for cx, cy, rc in _near_order(holes, here):
        rh = op.hole_diameter / 2 if op.hole_diameter > 0 else rc
        r = rh - rt
        if r < -1e-6:
            tp.warnings.append(f'perçage à la fraise : trou Ø {2 * rh:.2f} plus petit que la fraise')
            continue
        em.travel(cx + max(r, 0.0), cy)
        if r < 0.005:                                    # fraise au Ø du trou : plongée
            em.plunge(-depth)
        else:
            em.plunge(0.0)
            _helix(em, cx, cy, r, 0.0, -depth, step, ccw)
            _circle_at(em, cx, cy, r, -depth, ccw)
            em.feed(cx, cy, -depth)
        em.retract()
        tp.cycles.append({'kind': 'percage_fraise', 'x': cx, 'y': cy, 'depth': depth, 'diameter': 2 * rh,
                          'infeed': step})


def _chamfer(doc, setup, op, tool, tp, em, here) -> None:
    """Ébavurage des trous : l'outil conique plonge au centre jusqu'à ce que
    son cône dépasse le bord du trou de la largeur voulue (surépaisseur,
    0,2 mm par défaut)."""
    holes = hole_centers(doc, op)
    if not holes:
        tp.warnings.append('ébavurage : aucun cercle parmi les objets choisis')
        return
    if tool.kind != 'conique' or not tool.angle:
        tp.warnings.append('ébavurage : outil conique attendu')
        return
    half = math.radians(tool.angle / 2)
    width = op.stock if op.stock > 0 else 0.2
    for cx, cy, rc in _near_order(holes, here):
        target = rc + width
        if target > tool.diameter / 2 + 1e-9:
            tp.warnings.append(f'ébavurage : trou Ø {2 * rc:.2f} trop grand pour l\'outil (Ø {tool.diameter:g})')
            continue
        depth = max(0.0, (target - tool.tip / 2) / math.tan(half))
        em.travel(cx, cy)
        em.plunge(-depth)
        em.retract()
        tp.cycles.append({'kind': 'chanfrein', 'x': cx, 'y': cy, 'depth': depth})


# --- formes simples : cycles des machines (cercles, rectangles) --------------------------------
def shape_cycles(doc, op, kind: str, depth: float, infeed: float, stepover: float) -> list:
    """Cycles équivalents d'une poche (`kind` 'poche') ou d'un détourage
    ('contour') si chaque forme est un cercle ou un rectangle droit, toutes
    disjointes ; sinon [] (la machine reçoit les mouvements)."""
    from ..core.holes import circle_of, rect_of
    items = [it for it in source_items(doc, op) if item_geometry(it)]
    if not items or (kind == 'contour' and has_tabs(op)):
        return []
    out = []
    side = {'interieur': 'Inside', 'exterieur': 'Outside', 'sur': 'Over'}.get(op.side, 'Outside')
    for it in items:
        c = circle_of(it)
        if c is not None:
            if kind == 'poche':
                out.append({'kind': 'poche_cercle', 'x': c[0], 'y': c[1], 'diameter': 2 * c[2], 'depth': depth,
                            'infeed': infeed, 'stock': op.stock, 'stepover': stepover})
            else:
                out.append({'kind': 'decoupe_cercle', 'x': c[0], 'y': c[1], 'diameter': 2 * c[2], 'depth': depth,
                            'infeed': infeed, 'side': side})
            continue
        r = rect_of(it)
        if r is None:
            return []
        base = {'x': r[0], 'y': r[1], 'width': r[2], 'height': r[3], 'corner': r[4], 'depth': depth,
                'infeed': infeed}
        if kind == 'poche':
            out.append({'kind': 'poche_rectangle', **base, 'stock': op.stock, 'stepover': stepover})
        else:
            out.append({'kind': 'decoupe_rectangle', **base, 'side': side})
    # formes disjointes seulement (une lettre dans un cadre n'est pas une poche simple)
    boxes = [it.bbox() for it in items]
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                return []
    return out


def _facing(doc, setup, op, tool, tp, em, here) -> None:
    """Surfaçage : passes parallèles sur l'encombrement des objets choisis
    (sinon la plaque), débordement compris, à chaque passe en Z ; angle des
    passes réglable. Sens des passes (`face_direction`) : aller-retour, ou
    toutes en avalant (la matière pas encore surfacée à droite de l'outil,
    broche en sens horaire), ou toutes en opposition (à gauche) ; alors chaque
    passe part du même côté, après une remontée hors de la pièce."""
    from ..core.geom import bbox_union
    from ..core.holes import circle_of
    items = [it for it in source_items(doc, op) if item_geometry(it)]
    bb = bbox_union(it.bbox() for it in items) if items else None
    whole = False
    if not op.items and not op.sources and _ONLY.get() is None:   # ni objet ni couleur choisis, brut du dessin 2D
        from ..core import stock2d                        # (réponse 20 du 14/11) : toute son emprise
        box = stock2d.box_for(doc, setup)
        if box is not None:
            bb, whole = (box.x0, box.y0, box.x1, box.y1), True
    if bb is None and doc.plate is not None:
        pl = doc.plate
        bb = (pl.x, pl.y, pl.x + pl.width, pl.y + pl.height)
    if bb is None:
        tp.warnings.append('surfaçage : ni objet ni plaque')
        return
    r = tool.diameter / 2
    ext = op.extension + r
    x0, y0, x1, y1 = bb[0] - ext, bb[1] - ext, bb[2] + ext, bb[3] + ext
    step = max(0.05, (tool.stepover or 0.4) * tool.diameter)
    a = math.radians(op.face_angle)
    ca, sa = math.cos(a), math.sin(a)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    # passes dans le repère tourné : boîte englobante de la zone tournée
    corners = [((x - cx) * ca + (y - cy) * sa, -(x - cx) * sa + (y - cy) * ca) for x, y in
               ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    u0, u1 = min(p[0] for p in corners), max(p[0] for p in corners)
    v0, v1 = min(p[1] for p in corners), max(p[1] for p in corners)
    n = max(1, int(math.ceil((v1 - v0) / step)))
    rows = [v0 + (v1 - v0) * k / n for k in range(n + 1)]

    def world(u, v):
        return cx + u * ca - v * sa, cy + u * sa + v * ca
    # les passes avancent vers +v : la matière restante est à gauche d'une passe vers +u, à droite d'une passe vers -u
    direction = getattr(op, 'face_direction', 'aller_retour')
    one_way = direction in ('avalant', 'opposition')
    for z in op_levels(op, tool):
        for k, v in enumerate(rows):
            if direction == 'avalant':
                pa, pb = world(u1, v), world(u0, v)
            elif direction == 'opposition':
                pa, pb = world(u0, v), world(u1, v)
            else:
                pa, pb = (world(u0, v), world(u1, v)) if k % 2 == 0 else (world(u1, v), world(u0, v))
            if k == 0 or one_way:                        # sens unique : remonter, revenir au départ, replonger
                em.travel(*pa)
                em.plunge(z)
            else:
                em.feed(pa[0], pa[1], z)
            em.feed(pb[0], pb[1], z)
        em.retract()
    if one_way:                                          # les cycles des machines (RectangleFace … BothWays, CircleFace)
        return                                           # vont et viennent : les mouvements, eux, gardent le sens
    depth = abs(op.depth)
    infeed = op.step_down or tool.step_down
    pct = int(round((tool.stepover or 0.4) * 100))
    one = items[0] if len(items) == 1 and not whole else None
    c = circle_of(one) if one is not None else None
    if c is not None:
        tp.cycles.append({'kind': 'surfacage_cercle', 'x': c[0], 'y': c[1], 'diameter': 2 * c[2],
                          'extension': 2 * op.extension, 'depth': depth, 'infeed': infeed, 'stepover': pct})
    else:
        tp.cycles.append({'kind': 'surfacage_rectangle', 'x': (bb[0] + bb[2]) / 2, 'y': (bb[1] + bb[3]) / 2,
                          'width': bb[2] - bb[0], 'height': bb[3] - bb[1], 'extension': op.extension,
                          'depth': depth, 'infeed': infeed, 'stepover': pct, 'angle': op.face_angle})


def _machine_text(doc, setup, op, tool, tp, em, here) -> None:
    """Texte machine : gravé par la commande numérique avec sa police, au
    moment de l'usinage — noté en cycle pour les post-processeurs qui le
    connaissent ; le parcours se limite à rejoindre le centre du texte."""
    from .instructions import params_of
    p = params_of('texte_machine', op.params)
    if not (p['text'].strip() or p['variable'].strip() or p['date']):
        tp.warnings.append('texte machine : rien à graver')
        return
    em.travel(p['x'], p['y'])
    tp.cycles = [{'kind': 'texte_machine', 'x': p['x'], 'y': p['y'], 'text': p['text'], 'variable': p['variable'],
                  'date': p['date'], 'height': p['height'], 'rotation': p['rotation'], 'depth': abs(op.depth),
                  'double': p['double'], 'depth1': min(abs(p['depth1']), abs(op.depth))}]
    tp.warnings.append('texte machine : gravé par la commande (police de la machine) ; seuls les '
                       'post-processeurs qui le connaissent l\'écrivent (Datron)')


STRATEGIES = {
    'vinyle': _vinyl,
    'chanfrein_bord': _edge_chamfer,
    'texte_machine': _machine_text,
    'surfacage': _facing,
    'gravure': _gravure,
    'taraudage': _thread,
    'percage_fraise': _helix_bore,
    'chanfrein': _chamfer,
    'contour': _contour,
    'poche': _pocket,
    'percage': _drill,
    'laser': _laser,
    'decoupe3d': _decoupe3d,
    'reste': _rest,
    'laser_decoupe': _laser_cut,
    'laser_gravure': _laser_fill,
}


#: natures dont la première passe part du haut du brut du dessin 2D (réponse 20 du 14/11) ; les autres (gravure 2,5D,
#: chanfreins, taraudage…) gardent Z 0 — leur profondeur se lit sur le dessus de la plaque — dégagements relevés
RISE_KINDS = ('surfacage', 'gravure', 'contour', 'poche', 'percage', 'percage_fraise', 'reste')
#: natures qui peuvent laisser une surépaisseur Z au fond (`Operation.stock_z`, réponse du 15/11 à la question 28),
#: distincte de celle des flancs : le fond reste à une finition
STOCK_Z_KINDS = ('contour', 'poche', 'reste')


def left_on_floor(op) -> float:
    """Ce que l'opération laisse au fond (mm) : sa surépaisseur Z, pour les natures qui en ont une ; 0 sinon."""
    if getattr(op, 'kind', '') not in STOCK_Z_KINDS:
        return 0.0
    try:
        return max(0.0, float(getattr(op, 'stock_z', 0.0) or 0.0))
    except (TypeError, ValueError):
        return 0.0


def stock_top(doc, setup, op) -> float:
    """Surépaisseur du brut du dessin 2D (`core.stock2d`) au-dessus de Z 0 au début de l'opération. 0 : pas de brut
    (ou sans surépaisseur), un surfaçage actif de toute l'emprise du brut (ni objet ni couleur choisis) placé avant
    elle — le dessus est alors à Z 0 —, une autre prise (pièce retournée, face, corps 3D) ou un brut 3D, un Z de
    départ, une opération enroulée ou projetée, le laser."""
    if doc is None or op.kind.startswith('laser'):
        return 0.0
    if float(getattr(op, 'z_start', 0.0) or 0.0) or (getattr(op, 'wrap', 'none') or 'none') != 'none':
        return 0.0
    tool = setup.tool(op.tool_id)
    if tool is not None and tool.kind == 'laser':
        return 0.0
    from ..core import stock2d, stock3d
    st = stock2d.of_setup(setup)
    if not st.active() or st.top <= 0 or stock3d.of_setup(setup).active():
        return 0.0
    from ..core import workspace as WS
    if WS.op_setup(op, doc) != ('', -1):
        return 0.0
    for o in setup.operations:
        if o is op or o.id == op.id:
            break
        if o.enabled and o.kind == 'surfacage' and not o.items and not o.sources:
            return 0.0
    return float(st.top) if stock2d.box_for(doc, setup) is not None else 0.0


def stock_rise(doc, setup, op) -> float:
    """La surépaisseur `stock_top` si l'opération la traverse (`RISE_KINDS`) : sa première passe part du haut du
    brut ; sinon 0."""
    return stock_top(doc, setup, op) if op.kind in RISE_KINDS else 0.0


def compute(doc: Document, setup: CamSetup, op: Operation, here=(0.0, 0.0)) -> Toolpath:
    """Parcours d'une opération."""
    tool = setup.tool(op.tool_id)
    tp = Toolpath(op_id=op.id, tool_id=op.tool_id, name=op.name)
    if op.kind == 'instruction':                        # sans outil ni parcours
        from .instructions import INSTRUCTIONS, params_of
        if op.instruction not in INSTRUCTIONS:
            tp.warnings.append(f'instruction « {op.instruction} » inconnue')
            return tp
        tp.cycles = [{'kind': 'instruction', 'name': op.instruction,
                      'params': params_of(op.instruction, op.params)}]
        if op.instruction == 'appel_programme' and not tp.cycles[0]['params']['path'].strip():
            tp.warnings.append('appel de programme : fichier non indiqué')
        if op.instruction == 'saisie_operateur':
            from .instructions import input_fields
            fields, problems = input_fields(tp.cycles[0]['params']['champs'])
            tp.warnings += [f'saisie de l\'opérateur : {p}' for p in problems]
            if not fields:
                tp.warnings.append('saisie de l\'opérateur : aucun champ')
        return tp
    if tool is None:
        tp.warnings.append('aucun outil choisi')
        return tp
    if op.kind == 'gamme':
        # opération « gamme » d'un modèle importé avant la v0.268 : calculée en
        # finition 2,5D ; l'ébauche est une opération à part (réimporter le modèle)
        tp.warnings.append('gamme : seule la finition est calculée — réimporter le modèle TypeEdit pour avoir '
                           'aussi l\'ébauche')
        import copy
        op = copy.copy(op)
        op.kind = 'vcarve'
    if op.kind not in STRATEGIES:
        from ..plugins import REGISTRY
        from . import advanced
        fn = advanced.STRATEGIES.get(op.kind) or (REGISTRY.strategies.get(op.kind) or (None, None))[1]
        if fn is None:
            tp.warnings.append(f'stratégie « {op.kind} » inconnue')
            return tp
    else:
        fn = STRATEGIES[op.kind]
    if tool.kind == 'laser' and not op.kind.startswith('laser'):
        tp.warnings.append('outil laser : utiliser une opération laser (marquage, découpe, gravure)')
    if op.kind.startswith('laser') and tool.kind != 'laser':
        tp.warnings.append('opération laser avec un outil d\'usinage : vérifier le choix de l\'outil')
    leave = left_on_floor(op)
    if leave > 0:                                        # surépaisseur Z : le fond reste à une finition
        if leave >= abs(op.depth) - 1e-9:
            tp.warnings.append(f'surépaisseur Z {leave:g} mm : pas moins que la profondeur ({abs(op.depth):g} mm), '
                               'rien n’est usiné')
            return tp
        import copy
        op = copy.copy(op)
        op.depth = abs(op.depth) - leave                 # passes, pattes, cycles : tout s’arrête au-dessus du fond
        op._floor_left = True
    top = stock_top(doc, setup, op)
    rise = top if op.kind in RISE_KINDS else 0.0
    if top > 0:                                          # brut du dessin 2D plus haut que la plaque
        import copy
        op = copy.copy(op)
        if rise:                                         # passes depuis son haut, fond inchangé
            op.depth = op.depth + rise
            op._stock_rise = rise
        else:                                            # profondeur lue depuis Z 0, dégagements au-dessus du brut
            op.safe_z = op.safe_z + top
            op.clear_z = op.clear_z + top
            tp.warnings.append(f'brut du dessin {top:g} mm au-dessus de la plaque : profondeur lue depuis Z 0, '
                               'dégagements relevés')
    if op.depth > tool.cut_length > 0 and tool.kind != 'laser':
        tp.warnings.append(f'profondeur {op.depth:g} mm > longueur utile de l\'outil ({tool.cut_length:g} mm)')
    em = Emitter(op, tool)
    token = _DRAWING_ORDER.set(getattr(op, 'order_mode', 'auto') == 'dessin')
    ramp_token = _RAMP_LIMIT.set(max(0.0, float(getattr(op, 'ramp_max', 0.0) or 0.0)))
    try:
        fn(doc, setup, op, tool, tp, em, here)
    finally:
        _RAMP_LIMIT.reset(ramp_token)
        _DRAWING_ORDER.reset(token)
    em.retract()
    tp.moves = em.moves
    if op.kind.startswith('laser') and tool.kind == 'laser':
        _wobble(op, tool, tp)
    if (getattr(op, 'wrap', 'none') or 'none') != 'none':
        _wrap(op, setup, tool, tp)
    _multicopy(doc, op, tp, em.safe)
    if not getattr(op, 'drill_feed_retract', False):     # sauf remontée demandée en vitesse de travail (alésage)
        rapid_retracts(tp.moves, op.safe_z)
    z0 = float(getattr(op, 'z_start', 0.0) or 0.0)
    if z0:                                               # Z de départ : tout le parcours suit le dessus de la matière
        for m in tp.moves:
            m.z += z0
        if tp.cycles:                                    # les cycles machine partiraient de Z 0 : les mouvements font foi
            tp.cycles = []
            tp.warnings.append(f'Z de départ {z0:g} mm : cycles machine remplacés par les mouvements')
    if rise > 0:                                         # relevé de la surépaisseur : le fond revient à −profondeur
        for m in tp.moves:
            m.z += rise
        if tp.cycles:
            tp.cycles = []
            tp.warnings.append(f'brut du dessin {rise:g} mm au-dessus de la plaque : cycles machine remplacés par '
                               'les mouvements')
    return tp


def copies_pitch(doc, op) -> tuple[float, float]:
    """Pas de la multicopie : donné, sinon taille des objets usinés + écart."""
    dx, dy = float(getattr(op, 'copies_dx', 0.0) or 0.0), float(getattr(op, 'copies_dy', 0.0) or 0.0)
    if dx and dy:
        return dx, dy
    boxes = [it.bbox() for it in source_items(doc, op)]
    boxes = [b for b in boxes if b]
    gap = float(getattr(op, 'copies_gap', 5.0) or 0.0)
    w = (max(b[2] for b in boxes) - min(b[0] for b in boxes)) if boxes else 0.0
    h = (max(b[3] for b in boxes) - min(b[1] for b in boxes)) if boxes else 0.0
    return (dx or w + gap), (dy or h + gap)


def _multicopy(doc, op, tp, safe: float) -> None:
    """Multicopie du parcours (TypeEdit) : colonnes × rangées, en serpentin,
    l'outil remontant au dégagement entre deux copies ; cycles décalés aussi."""
    import copy as _copy
    nx, ny = max(1, int(getattr(op, 'copies_x', 1) or 1)), max(1, int(getattr(op, 'copies_y', 1) or 1))
    if nx * ny <= 1 or not tp.moves:
        return
    dx, dy = copies_pitch(doc, op)
    base, cycles = list(tp.moves), list(tp.cycles)
    out, cyc = list(base), list(cycles)
    order = [(i if j % 2 == 0 else nx - 1 - i, j) for j in range(ny) for i in range(nx)][1:]
    for i, j in order:
        ox, oy = i * dx, j * dy
        last = out[-1]
        out.append(Move('rapid', last.x, last.y, safe))
        first = base[0]
        out.append(Move('rapid', first.x + ox, first.y + oy, safe))
        for m in base:
            c = _copy.copy(m)
            c.x += ox
            c.y += oy
            if m.is_arc:
                c.cx += ox
                c.cy += oy
            out.append(c)
        for cy_ in cycles:
            d = dict(cy_)
            if 'x' in d and 'y' in d:
                d['x'] += ox
                d['y'] += oy
            cyc.append(d)
    tp.moves, tp.cycles = out, cyc
    tp.warnings.append(f'multicopie : {nx} × {ny} copies, pas {dx:g} × {dy:g} mm')


def _wrap(op, setup, tool, tp) -> None:
    """Parcours enroulé sur la pièce cylindrique ou conique (cam.wrap) ; les
    cycles machine, qui décriraient la forme à plat, sont écartés. Refusé
    (rien d'écrit) au laser ou sans mouvements à enrouler."""
    from . import wrap as WR
    w = WR.Wrap.of(op)
    if w is None:
        return
    if tool.kind == 'laser':
        tp.moves, tp.cycles = [], []
        tp.warnings.append('enroulement : non pris en charge au laser — rien d\'écrit')
        return
    if tp.cycles and not tp.moves:
        tp.cycles = []
        tp.warnings.append('enroulement : cycles machine seuls (texte machine…), impossibles à enrouler — '
                           'rien d\'écrit')
        return
    if w.mode == 'surface':
        moves, warnings = _project(op, setup, tp)
    elif w.mode == 'locale':
        moves, warnings = _project_local(op, setup, tp)
    else:
        moves, warnings = WR.apply(tp.moves, w, op.safe_z, setup.tolerance)
    tp.warnings += warnings
    if tp.cycles and moves:
        tp.warnings.append('enroulement : cycles machine remplacés par les mouvements enroulés')
    tp.cycles = []
    tp.moves = moves
    if moves:
        tp.warnings.append(WR.describe(w))


def _project(op, setup, tp) -> tuple[list, list]:
    """Projection parallèle sur la pièce STEP de l'opération (cam.wrap)."""
    from . import wrap as WR
    path = getattr(op, 'wrap_model', '') or ''
    if not path:
        return [], ['projection : choisir le fichier STEP de la pièce (« Pièce STEP » de l\'enroulement)']
    try:
        from ..io.neostep import step3d
        mod = step3d.lire_modele(path)
    except Exception as ex:                               # noqa: BLE001 — fichier tiers
        return [], [f'projection : STEP illisible ({ex})']
    if not len(mod.triangles):
        return [], ['projection : aucune face maillée dans le STEP']
    xs = [m.x for m in tp.moves]
    ys = [m.y for m in tp.moves]
    smap = WR.SurfaceMap(mod.triangles, (min(xs), min(ys), max(xs), max(ys)), max(0.02, setup.tolerance * 5))
    return WR.project(tp.moves, smap, op.safe_z, smap.res)


def _project_local(op, setup, tp) -> tuple[list, list]:
    """Projection locale le long de la courbe guide de l'opération (cam.wrap)."""
    from . import wrap as WR
    path = getattr(op, 'wrap_model', '') or ''
    if not path:
        return [], ['projection locale : choisir la pièce (STEP, STL)']
    try:
        from ..io import model3d as M3
        tris = M3.load(path).triangles
    except Exception as ex:                               # noqa: BLE001 — fichier tiers
        return [], [f'projection locale : pièce illisible ({ex})']
    if not len(tris):
        return [], ['projection locale : aucune face maillée']
    guide = getattr(op, 'wrap_guide', None) or []
    low = [m for m in tp.moves if m.z < op.safe_z - 1e-9]
    if not guide:
        return WR.local_project(tp.moves, None, guide, op.safe_z, 0.1)          # message : pas de guide
    if not low:
        return tp.moves, []
    span = max(max(m.y for m in low) - min(m.y for m in low), 1.0) + 2.0
    gx = [p[0] for p in guide]
    gy = [p[1] for p in guide]
    smap = WR.SurfaceMap(tris, (min(gx) - span, min(gy) - span, max(gx) + span, max(gy) + span),
                         max(0.02, setup.tolerance * 5))
    return WR.local_project(tp.moves, smap, guide, op.safe_z, smap.res)


def _wobble(op, tool, tp) -> None:
    """Oscillation du faisceau superposée au parcours laser, cadence du
    scanner vérifiée (cam.wobble)."""
    from . import wobble as W
    shape = getattr(op, 'wobble', 'none') or 'none'
    a, p = getattr(op, 'wobble_amplitude', 0.0) or 0.0, getattr(op, 'wobble_pitch', 0.0) or 0.0
    if not W.active(shape, a, p):
        return
    from .model import op_feed
    for level, text in W.check(op_feed(op, tool), p, a, shape):
        tp.warnings.append(('BLOQUANT : ' if level == 'bloquant' else '') + text)
    tp.moves = W.apply_moves(tp.moves, a, p, shape)


def compute_linked(doc: Document, setup: CamSetup, op: Operation, previous, here=(0.0, 0.0)) -> Toolpath:
    """Parcours de `op` lié au parcours précédent (gamme) : seulement la
    matière laissée par les parcours d'avant `previous`."""
    token_prev = _PREVIOUS.set(list(previous))
    try:
        tp = compute(doc, setup, op, here)
    finally:
        _PREVIOUS.reset(token_prev)
    if tp.moves:
        from . import linkprev
        rise = stock_rise(doc, setup, op)
        if rise > 0:                                     # brut du dessin 2D : trié dans le repère de son haut, comme
            import copy                                  # un Z de départ (dégagements compris)
            lifted = copy.copy(op)
            lifted.z_start = rise
            tp = linkprev.remaining_only(tp, list(previous), setup, lifted)
        else:
            tp = linkprev.remaining_only(tp, list(previous), setup, op)
        later = linkprev.later_bigger(setup, op)
        if later:
            tp.warnings.append(f'lier au parcours précédent : « {later} », avec un outil plus gros, '
                               'est usiné après — placer les gros outils avant (gamme du plus gros '
                               'au plus fin)')
    return tp


def compute_all(doc: Document, setup: CamSetup, only=None) -> list[Toolpath]:
    """Parcours des opérations actives ; `only` : identifiants d'objets
    (mode sélection) — seuls eux sont usinés."""
    from ..core.text import ensure_outlines
    ensure_outlines(doc)                             # textes jamais affichés : contours à usiner
    token = _ONLY.set(set(only) if only is not None else None)
    try:
        out = []
        here = (0.0, 0.0)
        ops = [op for op in setup.operations if op.enabled]
        doc_key = _doc_signature(doc)                    # None : pas de mémoire des parcours
        LAST_RUN.update(reused=0, computed=0)
        setup_key = _setup_signature(setup) if doc_key else None
        prev_keys = []
        for i, op in enumerate(ops):
            progress.step(i, len(ops), 'Parcours {0} sur {1}')
            key = _op_key(doc_key, setup_key, op, here, only) if setup_key else None
            if key is not None:                          # brut du dessin 2D : traversé ou non (surfaçage avant elle)
                key = key + (('brut2d', stock_top(doc, setup, op)),)
            linked = bool(getattr(op, 'link_previous', False))
            after = linked or bool(getattr(op, 'rest_previous', False))     # poche, seulement le reste : aussi
            if after and key is not None:                # le résultat dépend aussi des parcours d'avant
                key = key + (tuple(prev_keys),) if all(k is not None for k in prev_keys) else None
            hit = _TP_CACHE.get(key) if key else None
            if hit is not None:                          # rien n'a changé pour elle : le parcours d'avant
                _TP_CACHE.move_to_end(key)
                tp = _copy_tp(hit)
                LAST_RUN['reused'] += 1
            else:
                with progress.span(i / len(ops), (i + 1) / len(ops)):
                    if linked:                           # gamme : seulement la matière laissée par les parcours d'avant
                        tp = compute_linked(doc, setup, op, out, here)
                    else:
                        token_prev = _PREVIOUS.set(None)
                        try:
                            tp = compute(doc, setup, op, here)
                        finally:
                            _PREVIOUS.reset(token_prev)
                LAST_RUN['computed'] += 1
                if key and len(tp.moves) <= TP_CACHE_MOVES:
                    _TP_CACHE[key] = _copy_tp(tp)
                    while len(_TP_CACHE) > TP_CACHE_MAX or \
                            sum(len(t.moves) for t in _TP_CACHE.values()) > TP_CACHE_MOVES:
                        _TP_CACHE.popitem(last=False)
            out.append(tp)
            prev_keys.append(key if key is not None or tp.moves else 'vide')
            if tp.moves:
                here = (tp.moves[-1].x, tp.moves[-1].y)
        apply_faced_all(setup, out)
        return out
    finally:
        _ONLY.reset(token)


# --- mémoire des parcours : une opération dont rien n'a changé n'est pas recalculée -----------------
from collections import OrderedDict as _OrderedDict

#: (dessin, réglage, opération, départ, sélection) → parcours ; les plus anciens partent d'abord
_TP_CACHE: _OrderedDict = _OrderedDict()
TP_CACHE_MAX = 32
#: mouvements gardés au plus, tous parcours confondus (≈ 100 octets chacun : 4 millions ≈ 400 Mo)
TP_CACHE_MOVES = 4_000_000
#: dernier calcul : parcours repris de la mémoire et parcours calculés (compte rendu du panneau FAO)
LAST_RUN = {'reused': 0, 'computed': 0}
#: opérations jamais gardées : dépendent de l'heure, d'un compteur, d'un fichier sur le disque (modèle
#: STEP de la surface 3D) — les stratégies des plugins non plus
NO_CACHE_KINDS = ('texte_machine', 'instruction', 'surface3d', 'ebauche3d', 'reprise3d', 'niveaux3d')
#: données du dessin hors clé : la description FAO elle-même (une opération changée ne doit pas
#: invalider les autres) et son journal
_EXTRA_SKIP = ('fao', 'fao_journal', 'work_time', 'guides', 'guides_obliques', 'notes', 'prises3d')   # le calcul ne les lit pas


def _digest(obj) -> str | None:
    import hashlib
    import io
    import pickle
    try:
        buf = io.BytesIO()
        _Pickler(buf, protocol=pickle.HIGHEST_PROTOCOL).dump(obj)
        return hashlib.blake2b(buf.getvalue(), digest_size=20).hexdigest()
    except Exception:                                    # objet non sérialisable : pas de mémoire
        return None


def _path_ref(digest: bytes):
    """Tracé dans une empreinte (`_Pickler`) : jamais relu."""
    raise TypeError('empreinte seulement')


import pickle as _pickle


class _Pickler(_pickle.Pickler):
    """Pickle d'empreinte : un tracé y entre par celles de ses contours
    (gardées avec eux), pas segment par segment."""
    def reducer_override(self, obj):
        if type(obj) is Path:
            return _path_ref, (obj.digest(),)
        return NotImplemented


def _doc_signature(doc: Document) -> str | None:
    """Empreinte de tout ce que lit le calcul : calques (nom, visibilité,
    objets), plaque, table des outils, données du dessin (hors FAO)."""
    extra = {k: v for k, v in (doc.extra or {}).items() if k not in _EXTRA_SKIP} if isinstance(doc.extra, dict) else None
    from ..core import surface2d                         # surface posée : rattachements, contenu à suivre
    return _digest(([(L.id, L.name, L.visible, surface2d.of_layer(L), L.items) for L in doc.layers],
                    doc.plate, doc.tools, extra))


def _setup_signature(setup: CamSetup) -> str | None:
    """Empreinte du réglage FAO sans ses opérations (outils, machine, tolérance…)."""
    import copy
    bare = copy.copy(setup)
    bare.operations = []
    return _digest(bare)


def _op_key(doc_key, setup_key, op: Operation, here, only):
    from ..plugins import REGISTRY
    if op.kind in NO_CACHE_KINDS or op.kind in REGISTRY.strategies:
        return None
    import dataclasses
    d = _digest(dataclasses.replace(op, restart_from=0, restart_to=0, restart_sig=''))   # le calcul ne les lit pas
    if d is None:
        return None
    return (doc_key, setup_key, d, (round(here[0], 9), round(here[1], 9)),
            frozenset(only) if only is not None else None, bool(_DRAWING_ORDER.get()))


def _copy_tp(tp: Toolpath) -> Toolpath:
    """Copie légère : mouvements partagés (jamais modifiés en place), listes
    de messages et de cycles propres à chaque copie."""
    import copy
    c = copy.copy(tp)
    c.warnings = list(tp.warnings)
    c.cycles = [dict(x) if isinstance(x, dict) else x for x in tp.cycles]
    return c


def clear_toolpath_cache() -> None:
    _TP_CACHE.clear()


def rest_zones(reg, tool, depth: float = 0.0, stock: float = 0.0, tol: float = 0.01):
    """Aperçu du reste de matière (TypeEdit) : ce que l'outil ne peut pas
    vider dans la région `reg` (shapely) — angles rentrants, passages trop
    étroits : la région moins son ouverture par le disque de l'outil (rayon
    au niveau de `depth` pour un outil conique), surépaisseur `stock`
    comprise. Rend (reste, rayon)."""
    op = Operation(depth=depth)
    r = cut_radius(op, tool) + max(0.0, stock)
    if r <= 0 or reg.is_empty:
        return reg.buffer(0).difference(reg), r
    qs = _quad_segs(max(r, tol), tol)
    reach = erode(reg, r, qs).buffer(r, quad_segs=qs)
    rest = reg.difference(reach)
    return rest.buffer(-tol / 4).buffer(tol / 4), r                 # liserés numériques ôtés
