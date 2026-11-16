"""Plaques de reprise : les bruts vissés sur une plaque percée (demande du 14/11).

Une plaque de reprise est un dessin (symbole de la bibliothèque, DXF…) dont les trous ronds laissent passer les vis ;
les bruts y sont posés sur le dessin, puis vissés par-dessous. Pour chaque brut (contour fermé), les trous de la plaque
qu'il couvre en entier, à une marge de son bord, sont les places de ses vis : on en garde quelques-uns, les plus
écartés (le brut tient sans basculer), et le brut est percé puis taraudé à ces places, au filetage qui passe dans les
trous de la plaque.

Rien ici ne dépend de l'interface : `plate_holes`, `choose`, `layout` rendent des nombres ; `cam_panel` en fait des
trous TypeEdit (`core.holes`) et des opérations de perçage et de taraudage. Unités : mm."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

#: un trou laisse passer la vis dont le Ø nominal ne le dépasse pas de plus que ceci (mm) : ajustement juste — les
#: plaques de reprise sont percées Ø 4,05 pour des CHC M4 (réponse du 15/11), Ø 3,2 pour des M3
FIT = 0.05
#: à partir de ce Ø nominal, le taraudage est prépercé à la fraise (« drillmill si >= M6 », réponse du 16/11) ;
#: en dessous, la fraise à fileter perce elle-même : une seule opération
PREDRILL_FROM = 6.0
#: profondeur taraudée d'après l'épaisseur : au plus `MAX_DEPTH`, en gardant `KEPT` sous l'usinage de la face
MAX_DEPTH, KEPT = 6.0, 0.5
#: deux trous sont « du même diamètre » à ceci près (mm) : 4 et 4,05
SAME = 0.11


def thread_for(diameter: float) -> str:
    """Le plus gros filetage dont la vis passe dans un trou de `diameter` (mm), même juste (M4 dans un Ø 4 ou 4,05) ;
    '' : aucun (trou trop petit)."""
    from .model import THREADS
    best = ''
    for name, (nominal, _pitch, _pre) in THREADS.items():
        if nominal <= diameter + FIT and (not best or nominal > THREADS[best][0]):
            best = name
    return best


def predrilled(thread: str) -> bool:
    """Ce filetage est prépercé à la fraise avant d'être taraudé (à partir de M6) ; sinon la fraise à fileter perce
    elle-même."""
    from .model import THREADS
    return thread in THREADS and THREADS[thread][0] >= PREDRILL_FROM - 1e-9


def depth_for(thickness: float, machined: float = 3.0) -> float:
    """Profondeur taraudée d'après l'épaisseur du brut : ce qui reste sous l'usinage de la face (`machined`), moins
    0,5 mm, 6 mm au plus — 3,5 mm pour 7 mm, 6 mm pour 10 mm (réponse du 15/11). 0 : épaisseur inconnue ou trop
    mince (moins de 1 mm à tarauder)."""
    try:
        d = min(MAX_DEPTH, float(thickness) - float(machined) - KEPT)
    except (TypeError, ValueError):
        return 0.0
    return round(d, 3) if d >= 1.0 else 0.0


def common(holes_: list) -> list:
    """Les trous du diamètre le plus fréquent (à `SAME` près ; à égalité, le plus petit) : sur une plaque de reprise,
    les trous de vis sont les plus nombreux — les autres la fixent sur la table (M6 fraisés tous les 100 mm) ou sont
    des alésages."""
    groups: list = []                                    # [[Ø du premier, trous…]] par Ø croissant
    for h in sorted(holes_, key=lambda h: h.diameter):
        if groups and h.diameter - groups[-1][0] <= SAME:
            groups[-1].append(h)
        else:
            groups.append([h.diameter, h])
    if not groups:
        return []
    best = max(groups, key=lambda g: (len(g), -g[0]))
    keep = {id(h) for h in best[1:]}
    return [h for h in holes_ if id(h) in keep]


def _flag(v, default: bool) -> bool:
    """Une case lue d'un réglage : vrai, faux, ou `default` pour ce qui n'est ni l'un ni l'autre."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str) and v.strip().lower() in ('true', '1', 'yes', 'oui'):
        return True
    if isinstance(v, str) and v.strip().lower() in ('false', '0', 'no', 'non'):
        return False
    return default


@dataclass
class Hole:
    x: float
    y: float
    diameter: float


@dataclass
class Spec:
    """Réglage : les trous de la plaque retenus (diamètres), les vis par brut, la marge au bord du brut, le brut
    retourné pour son taraudage (miroir autour de son centre : '' aucun, 'x' gauche-droite, 'y' haut-bas)."""
    min_diameter: float = 2.5
    max_diameter: float = 9.0
    per_blank: int = 4              # 0 : tous les trous couverts
    margin: float = 3.0
    mirror: str = ''
    thread: str = ''                # '' : d'après le diamètre des trous de la plaque
    depth: float = 6.0              # profondeur taraudée
    extra_drill: float = 2.0        # le perçage (à partir de M6) descend plus bas que le taraudage
    common_only: bool = True        # seulement les trous du Ø le plus fréquent (`common`)
    auto_depth: bool = True         # profondeur d'après l'épaisseur du brut (`depth_for`)
    machined: float = 3.0           # ce que l'usinage de la face enlève (pour `auto_depth`)

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}

    def by_thickness(self, thickness) -> bool:
        """La profondeur se calcule d'après cette épaisseur : la case est cochée et l'épaisseur connue."""
        try:
            return bool(self.auto_depth) and float(thickness or 0.0) > 0
        except (TypeError, ValueError):
            return False

    def depth_on(self, thickness) -> float:
        """La profondeur taraudée pour un brut de cette épaisseur : d'après elle si c'est demandé et qu'elle est
        connue — 0 : brut trop mince pour être taraudé ; sinon la profondeur réglée."""
        if self.by_thickness(thickness):
            return depth_for(thickness, self.machined)
        return round(float(self.depth), 3)

    def drill_on(self, thickness) -> float:
        """La profondeur du perçage à la fraise (à partir de M6) : `extra_drill` sous le taraudage — sans entrer,
        quand l'épaisseur est connue, dans ce que l'usinage de la face enlèvera (0,5 mm gardés). 0 : trop mince."""
        depth = self.depth_on(thickness)
        if depth <= 0:
            return 0.0
        deep = depth + max(0.0, float(self.extra_drill))
        if self.by_thickness(thickness):
            deep = min(deep, max(depth, float(thickness) - float(self.machined) - KEPT))
        return round(deep, 3)

    @classmethod
    def from_dict(cls, d) -> 'Spec':
        out = cls()
        for k, v in dict(d or {}).items():
            if k in cls.__dataclass_fields__:
                try:
                    was = getattr(out, k)
                    setattr(out, k, _flag(v, was) if isinstance(was, bool) else type(was)(v))
                except (TypeError, ValueError):
                    pass
        out.per_blank = max(0, out.per_blank)
        out.mirror = out.mirror if out.mirror in ('', 'x', 'y') else ''
        from .model import THREADS
        out.thread = out.thread if out.thread in THREADS else ''
        return out


def _leaves(items):
    """Les objets feuilles, groupes dépliés ; ceux d'un groupe caché ne comptent pas."""
    from ..core.document import Group
    for it in items:
        if not getattr(it, 'visible', True):
            continue
        if isinstance(it, Group):
            yield from _leaves(it.children)
        else:
            yield it


def plate_holes(items, min_diameter: float = 0.0, max_diameter: float = math.inf, skip=()) -> list[Hole]:
    """Les trous ronds (cercles fermés) de la plaque, groupes dépliés, entre les deux diamètres ; un trou dessiné deux
    fois n'est compté qu'une fois. `skip` : identifiants d'objets à laisser (les cercles des bruts choisis)."""
    from ..core import holes
    skip = set(skip)
    out: list[Hole] = []
    seen = set()
    for it in _leaves(items):
        if it.id in skip:
            continue
        c = holes.circle_of(it)
        if c is None:
            continue
        x, y, r = c
        d = 2 * r
        if not min_diameter - 1e-6 <= d <= max_diameter + 1e-6:
            continue
        key = (round(x, 2), round(y, 2))
        if key in seen:
            continue
        seen.add(key)
        out.append(Hole(x, y, round(d, 3)))
    return out


def blank_polygon(item, tol: float = 0.01):
    """Le brut en polygone shapely (contours fermés, règle pair-impair) ; None : pas de contour fermé."""
    from . import strategies as S
    path = S.item_geometry(item)
    if path is None:
        return None
    reg = S.region([path], tol)
    return None if reg.is_empty else reg


def leaf_ids(items) -> set:
    """Les identifiants des objets feuilles de `items` (groupes dépliés)."""
    return {it.id for it in _leaves(items)}


def plate_parts(items, min_diameter: float = 0.0, max_diameter: float = math.inf) -> set:
    """Les objets du dessin de la plaque (un symbole posé) : le groupe de premier niveau qui a le plus de trous, s'il en
    a au moins trois et la moitié de ceux du calque — pas le groupe d'un brut et de ses quelques perçages."""
    from ..core.document import Group
    total = len(plate_holes(items, min_diameter, max_diameter))
    best, best_n = None, 0
    for it in items:
        if isinstance(it, Group):
            n = len(plate_holes([it], min_diameter, max_diameter))
            if n > best_n:
                best, best_n = it, n
    if best is None or best_n < 3 or 2 * best_n < total:
        return set()
    return leaf_ids([best])


def skip_for(selection, blanks) -> set:
    """Les cercles qui appartiennent aux bruts (un alésage dessiné dans le groupe d'un brut) : pas des trous de la
    plaque, même posés sur son calque."""
    from ..core import holes
    from ..core.document import Group
    want = {b.id for b in blanks}
    out = set()

    def walk(it):
        if isinstance(it, Group):
            leaves = list(_leaves(it.children))
            if any(x.id in want for x in leaves):
                out.update(x.id for x in leaves if holes.circle_of(x) is not None)
            else:
                for ch in it.children:
                    walk(ch)
    for it in selection or ():
        walk(it)
    return out


def blanks_of(items, min_area: float = 1.0, max_hole: float = 9.0, frame=None, exclude=(), holes_=None) -> list:
    """Les bruts parmi `items` (groupes dépliés) : les formes fermées d'au moins `min_area` mm², ni cercles de Ø
    `max_hole` au plus (des trous), ni dans une autre (une gravure tracée sur le brut), ni parmi `exclude` (le dessin
    de la plaque, `plate_parts`). `frame` (x0, y0, x1, y1) : le cadre des trous de la plaque — une forme qui le couvre
    et en contient d'autres (le contour de la plaque, un cadre) n'est pas un brut ; seule, c'est un grand brut.
    `holes_` (les trous de la plaque, qui donnent aussi le cadre) : la forme n'est un cadre que si une de celles
    qu'elle contient couvre un trou — un grand brut et le logo gravé dedans restent un brut."""
    if holes_ is not None:
        frame = frame_of(holes_)
    from ..core import holes
    from ..core.document import Shape
    exclude = set(exclude)
    cand = []
    for it in _leaves(items):
        if not isinstance(it, Shape) or it.id in exclude:
            continue
        c = holes.circle_of(it)
        if c is not None and 2 * c[2] <= max_hole + 1e-6:
            continue
        if not it.path.contours or not all(k.closed for k in it.path.contours):
            continue
        poly = blank_polygon(it)
        if poly is None or poly.area < min_area:
            continue
        cand.append((it, poly, poly.bounds))
    cand.sort(key=lambda c: c[1].area)
    grown: dict = {}                                     # chaque forme élargie une fois (contient : bord compris)
    parents: dict = {}                                   # les formes plus grandes qui contiennent chacune
    for k, (it, poly, b) in enumerate(cand):
        parents[id(it)] = []
        for o, o_poly, ob in cand[k + 1:]:              # les plus grandes seulement, d'abord par leur cadre
            if ob[0] <= b[0] and ob[1] <= b[1] and ob[2] >= b[2] and ob[3] >= b[3] and o_poly.area > poly.area:
                if id(o) not in grown:
                    grown[id(o)] = o_poly.buffer(1e-6)
                if grown[id(o)].contains(poly):
                    parents[id(it)].append(id(o))
    holders = {p for ps in parents.values() for p in ps}

    def over_holes(poly) -> bool:
        from shapely.geometry import Point
        x0, y0, x1, y1 = poly.bounds
        return any(x0 < h.x < x1 and y0 < h.y < y1 and poly.contains(Point(h.x, h.y)) for h in holes_)

    def is_frame(it, b) -> bool:
        if frame is None or id(it) not in holders or not (b[0] <= frame[0] and b[1] <= frame[1]
                                                          and b[2] >= frame[2] and b[3] >= frame[3]):
            return False
        if holes_ is None:
            return True
        return any(id(it) in parents[id(c)] and over_holes(c_poly) for c, c_poly, _cb in cand)
    frames = {id(it) for it, _poly, b in cand if is_frame(it, b)}
    out = [it for it, _poly, _b in cand if id(it) not in frames and all(p in frames for p in parents[id(it)])]
    order = {id(it): i for i, it in enumerate(_leaves(items))}
    return sorted(out, key=lambda it: order.get(id(it), 0))


def choose(poly, candidates: list[Hole], count: int, margin: float) -> list[Hole]:
    """Les trous de `candidates` couverts en entier par le brut `poly`, à `margin` de son bord ; `count` d'entre eux
    (0 : tous), les plus écartés : le premier le plus loin du centre du brut, puis chaque fois celui qui est le plus
    loin des trous déjà pris. L'ordre rendu est celui du dessin (bas en haut, puis gauche à droite)."""
    from shapely.geometry import Point
    x0, y0, x1, y1 = poly.bounds
    shrunk: dict = {}                                    # brut rétréci, un par diamètre de trou

    def fits(h: Hole) -> bool:
        if not (x0 < h.x < x1 and y0 < h.y < y1):
            return False
        if h.diameter not in shrunk:
            shrunk[h.diameter] = poly.buffer(-(max(margin, 0.0) + h.diameter / 2))
        return shrunk[h.diameter].contains(Point(h.x, h.y))
    inside = [h for h in candidates if fits(h)]
    inside.sort(key=lambda h: (round(h.y, 3), round(h.x, 3)))
    if count <= 0 or len(inside) <= count:
        return inside
    c = poly.centroid
    pick = [max(inside, key=lambda h: (round(math.hypot(h.x - c.x, h.y - c.y), 6), -h.y, -h.x))]
    while len(pick) < count:
        rest = [h for h in inside if h not in pick]

        def spread(h: Hole):
            d = [math.hypot(h.x - p.x, h.y - p.y) for p in pick]
            return round(min(d), 6), round(sum(d), 6), -h.y, -h.x   # à égalité : le plus loin de tous, puis en bas
        pick.append(max(rest, key=spread))
    return sorted(pick, key=lambda h: (round(h.y, 3), round(h.x, 3)))


def mirrored(holes_: list[Hole], poly, axis: str) -> list[Hole]:
    """Les trous retournés avec le brut (miroir autour du centre de son cadre) : la face vissée est celle de dessous,
    le taraudage se fait brut retourné."""
    if axis not in ('x', 'y'):
        return list(holes_)
    x0, y0, x1, y1 = poly.bounds
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if axis == 'x':
        return [Hole(2 * cx - h.x, h.y, h.diameter) for h in holes_]
    return [Hole(h.x, 2 * cy - h.y, h.diameter) for h in holes_]


@dataclass
class Placement:
    """Ce que donne la plaque pour chaque brut : ses trous de vis (déjà retournés s'il le faut)."""
    blanks: list = field(default_factory=list)       # [(objet brut, [Hole…])] dans l'ordre des bruts
    thread: str = ''

    def count(self) -> int:
        return sum(len(h) for _b, h in self.blanks)

    def empty(self) -> list:
        """Les bruts sans aucun trou de vis (trop petits, ou posés hors des trous de la plaque)."""
        return [b for b, h in self.blanks if not h]


#: marque du calque de trous de fixation ajouté (`Layer.extra`) : jamais pris pour la plaque
MADE_KEY = 'fixation_bruts'
#: marque du calque d'une plaque de reprise posée (`Layer.extra`, {'fichier': chemin}) : un repère, jamais usiné
PLATE_LAYER = 'plaque_reprise'
#: fichiers proposés comme plaques : symboles TypeEdit, dessins
PLATE_EXTS = ('.smb', '.dxf', '.vdz', '.svg')
#: réglage : le dernier dossier de plaques choisi
FOLDER_KEY = 'fao/plaques_dossier'


#: au plus tant de plaques listées (un dossier retenu trop vaste ne ralentit pas la fenêtre)
MAX_FILES = 300


def is_plate_layer(layer) -> bool:
    return bool((getattr(layer, 'extra', None) or {}).get(PLATE_LAYER))


def without_plates(doc):
    """Le dessin sans ses plaques de reprise posées (copie superficielle), ou lui-même s'il n'en a pas : ce qui est
    tracé ou gravé (HPGL, relief tiré du dessin) ne reprend pas ce repère."""
    if not any(is_plate_layer(L) for L in doc.layers):
        return doc
    import dataclasses
    return dataclasses.replace(doc, layers=[L for L in doc.layers if not is_plate_layer(L)])


def plate_folders(settings=None) -> list:
    """Les dossiers de plaques : le dernier choisi (réglage `FOLDER_KEY`), puis ceux d'un plugin
    (`api.set_defaults('plaques', {'dossiers': [...]})`) ; ceux qui existent, chacun une fois."""
    import pathlib
    from ..plugins import default
    out, seen = [], set()
    first = str(settings.value(FOLDER_KEY, '') or '') if settings is not None else ''
    for d in [first] + [str(x) for x in (default('plaques', 'dossiers', []) or [])]:
        if not d:
            continue
        p = pathlib.Path(d)
        key = str(p).lower()
        if key not in seen and p.is_dir():
            seen.add(key)
            out.append(p)
    return out


def plate_files(folders) -> list:
    """Les plaques des dossiers (et de leurs sous-dossiers directs) : [(nom, chemin)] triés par nom, chacune une fois,
    au plus `MAX_FILES`."""
    out, seen = [], set()
    for d in folders:
        try:
            entries = sorted(d.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            continue
        for p in entries:
            if len(out) >= MAX_FILES:
                break
            subs = []
            if p.is_dir():
                try:
                    subs = sorted(p.iterdir(), key=lambda q: q.name.lower())
                except OSError:
                    subs = []
            for f in ([p] if p.is_file() else subs):
                if len(out) >= MAX_FILES:
                    break
                if f.is_file() and f.suffix.lower() in PLATE_EXTS and str(f).lower() not in seen:
                    seen.add(str(f).lower())
                    out.append((f.stem if f.parent == d else f'{f.parent.name} / {f.stem}', f))
    return sorted(out, key=lambda e: e[0].lower())


def find_blanks(items, plate_items, min_diameter: float = 0.0, max_diameter: float = math.inf) -> list:
    """Les bruts parmi `items`, la plaque `plate_items` connue : ni le dessin de la plaque (`plate_parts`), ni une forme
    qui couvre le cadre de ses trous et en contient d'autres (`blanks_of`)."""
    found = plate_holes(plate_items, min_diameter, max_diameter)
    return blanks_of(items, max_hole=max_diameter, holes_=found,
                     exclude=plate_parts(plate_items, min_diameter, max_diameter))


def frame_of(holes_: list[Hole]):
    """Le cadre (x0, y0, x1, y1) des trous ; None sans trou."""
    if not holes_:
        return None
    return (min(h.x for h in holes_), min(h.y for h in holes_), max(h.x for h in holes_), max(h.y for h in holes_))


def layout(blanks, plate_items, spec: Spec, skip=()) -> Placement:
    """Pour chaque brut (contour fermé) : ses trous de vis sur la plaque `plate_items`, d'après le réglage `spec`.
    Une forme faite de plusieurs contours séparés compte pour autant de bruts. `skip` : objets de la plaque à laisser
    (les cercles des bruts choisis, quand ils sont sur le calque de la plaque)."""
    cand = plate_holes(plate_items, spec.min_diameter, spec.max_diameter, skip)
    if spec.common_only:                                 # les trous de vis : les plus nombreux
        cand = common(cand)
    out = Placement()
    used = []
    for b in blanks:
        poly = blank_polygon(b)
        if poly is None:
            continue
        for part in getattr(poly, 'geoms', [poly]):     # plusieurs contours séparés : un brut chacun
            got = choose(part, cand, spec.per_blank, spec.margin)
            used += got
            out.blanks.append((b, mirrored(got, part, spec.mirror)))
    out.thread = spec.thread or (thread_for(min(h.diameter for h in used)) if used else '')
    return out
