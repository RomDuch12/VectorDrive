"""Comparer deux dessins (comme COMPARE en DAO, d'après CADCraft) : ce qui
n'est que dans le dessin affiché (ajouté), que dans l'autre (enlevé), ou
dans les deux sous une autre forme (modifié).

Les objets (groupes dépliés) sont appariés d'abord par leur géométrie et
leurs propriétés (outil, plein, calque), le même identifiant préféré ; puis
par identifiant (un .vdz réenregistré garde les siens) : même objet, autre
géométrie ou propriétés ; puis par géométrie seule : propriétés changées.
Le reste n'est que d'un côté. Coordonnées comparées au micron près.

Les différences sont réunies en zones, en ordre de lecture (de haut en
bas, de gauche à droite) : on va de l'une à l'autre.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from .document import Image, Shape, Text

#: écart en dessous duquel deux coordonnées sont égales (mm)
TOL = 1e-3
#: zones de différences : les étendues sont coupées en au plus GRID × GRID cases
GRID = 32


@dataclass
class Comparison:
    other_name: str
    #: objets du dessin affiché seulement
    added: list = field(default_factory=list)
    #: objets de l'autre dessin seulement
    removed: list = field(default_factory=list)
    #: [(objet d'ici, objet de l'autre, [ce qui change])]
    changed: list = field(default_factory=list)
    common: int = 0
    #: zones (x0, y0, x1, y1) qui portent des différences, en ordre de lecture
    regions: list = field(default_factory=list)
    #: zone montrée en dernier (None avant la première)
    at: int | None = None
    #: document comparé (celui qui était affiché)
    doc: object = field(default=None, repr=False, compare=False)

    def differences(self) -> int:
        return len(self.added) + len(self.removed) + len(self.changed)

    def step(self, d: int):
        """Zone suivante (1) ou précédente (-1), en boucle ; None sans zone."""
        if not self.regions:
            return None
        n = len(self.regions)
        self.at = (0 if d > 0 else n - 1) if self.at is None else (self.at + d) % n
        return self.regions[self.at]


def _q(v: float) -> int:
    return round(v / TOL)


def _path_key(path) -> tuple:
    out = []
    for c in path.contours:
        segs = []
        for s in c.segments:
            k = [s.kind]
            for x, y in s.controls():
                k += (_q(x), _q(y))
            if getattr(s, 'w', 1.0) != 1.0:
                k.append(round(s.w * 1e6))
            segs.append(tuple(k))
        out.append((bool(c.closed), tuple(segs)))
    return tuple(out)


def _matrix_key(m) -> tuple:
    return tuple(round(v * 1e6) for v in (m.a, m.b, m.c, m.d)) + (_q(m.e), _q(m.f))


def geometry(it) -> tuple:
    """Empreinte de la géométrie d'un objet feuille (sans ses propriétés)."""
    if isinstance(it, Text):
        from .text import FORMAT_EXTRA
        fx = tuple((k, repr(it.extra[k])) for k in FORMAT_EXTRA if k in it.extra)
        on = it.extra.get('on_path')
        return ('T', it.text, it.font.lower(), _q(it.size), _matrix_key(it.matrix), it.align, _q(it.spacing),
                round(it.line_spacing * 1e4), round(it.width_ratio * 1e4), fx,
                _path_key(on) if on is not None and hasattr(on, 'contours') else None)
    if isinstance(it, Image):
        return ('I', hashlib.sha1(it.data).hexdigest(), _matrix_key(it.matrix))
    if isinstance(it, Shape):
        return ('S', _path_key(it.path))
    return (type(it).__name__, it.id)


#: propriétés comparées : (nom affiché, lecture)
PROPS = (('outil', lambda it, layer: it.tool),
         ('plein', lambda it, layer: bool(getattr(it, 'filled', False))),
         ('calque', lambda it, layer: layer))


def _entries(doc) -> list:
    """[(objet, géométrie, propriétés)] des objets feuilles du document."""
    from .document import Group
    out = []

    def walk(items, layer):
        for it in items:
            if isinstance(it, Group):
                walk(it.children, layer)
            else:
                out.append((it, geometry(it), tuple(f(it, layer) for _n, f in PROPS)))
    for L in doc.layers:
        walk(L.items, L.name)
    return out


def _what(a, b) -> list:
    """Ce qui change d'une entrée à l'autre (géométrie, propriétés)."""
    w = [] if a[1] == b[1] else ['texte' if a[1][0] == 'T' == b[1][0] else 'géométrie']
    return w + [n for (n, _f), x, y in zip(PROPS, a[2], b[2]) if x != y]


def outline(it):
    """Tracé qui montre un objet : la forme, le contour du texte (calculé au
    besoin), le cadre de l'image ; None s'il n'y en a pas."""
    try:
        if isinstance(it, Shape):
            return it.path
        if isinstance(it, Text):
            if it.outline is not None:
                return it.outline
            from .text import outline_for
            return outline_for(it)
        if isinstance(it, Image):
            from . import geom
            x0, y0, x1, y1 = it.bbox()
            return geom.Path([geom.rect(x0, y0, x1 - x0, y1 - y0, 0.0)])
    except Exception:
        return None
    return None


def bbox(it):
    p = outline(it)
    try:
        return p.bbox() if p else it.bbox()
    except Exception:
        return None


def compare(doc, other, other_name: str = '') -> Comparison:
    """Comparaison du document `doc` (affiché) avec `other`."""
    here, there = _entries(doc), _entries(other)
    res = Comparison(other_name)
    # 1. géométrie et propriétés égales (même identifiant préféré)
    pool: dict = {}
    for e in there:
        pool.setdefault((e[1], e[2]), []).append(e)
    rest_here = []
    for e in here:
        cand = pool.get((e[1], e[2]))
        if cand:
            k = next((i for i, c in enumerate(cand) if c[0].id == e[0].id), 0)
            cand.pop(k)
            res.common += 1
        else:
            rest_here.append(e)
    rest_there = [e for lst in pool.values() for e in lst]
    # 2. même identifiant : objet modifié
    by_id = {e[0].id: e for e in rest_there}
    left = []
    for e in rest_here:
        o = by_id.pop(e[0].id, None)
        if o is not None:
            res.changed.append((e[0], o[0], _what(e, o)))
        else:
            left.append(e)
    # 3. même géométrie, autres propriétés
    geo: dict = {}
    for e in by_id.values():
        geo.setdefault(e[1], []).append(e)
    used = set()
    for e in left:
        cand = geo.get(e[1])
        if cand:
            o = cand.pop(0)
            used.add(id(o[0]))
            res.changed.append((e[0], o[0], _what(e, o)))
        else:
            res.added.append(e[0])
    order = {id(e[0]): i for i, e in enumerate(there)}
    res.removed = sorted((e[0] for e in by_id.values() if id(e[0]) not in used), key=lambda it: order[id(it)])
    res.regions = regions(res)
    return res


def _union(boxes):
    boxes = [b for b in boxes if b]
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def regions(res: Comparison) -> list:
    """Zones des différences : les encombrements tombent dans une grille d'au
    plus GRID × GRID cases ; des cases voisines marquées forment une zone,
    rendue à l'encombrement de ses différences. Ordre de lecture."""
    boxes = [bbox(it) for it in res.added] + [bbox(it) for it in res.removed] + \
            [_union([bbox(a), bbox(b)]) for a, b, _w in res.changed]
    boxes = [b for b in boxes if b]
    ext = _union(boxes)
    if not ext:
        return []
    w, h = max(ext[2] - ext[0], 1e-9), max(ext[3] - ext[1], 1e-9)
    cw, ch = max(w, h) / GRID, max(w, h) / GRID
    nx, ny = max(1, min(GRID, int(w / cw) + 1)), max(1, min(GRID, int(h / ch) + 1))

    def cell(x, y):
        return min(nx - 1, int((x - ext[0]) / cw)), min(ny - 1, int((y - ext[1]) / ch))
    owner: dict = {}                                 # case → boîtes
    for i, b in enumerate(boxes):
        (i0, j0), (i1, j1) = cell(b[0], b[1]), cell(b[2], b[3])
        for i_ in range(i0, i1 + 1):
            for j_ in range(j0, j1 + 1):
                owner.setdefault((i_, j_), []).append(i)
    seen, out = set(), []
    for start in owner:
        if start in seen:
            continue
        stack, members = [start], set()
        seen.add(start)
        while stack:
            ci, cj = stack.pop()
            members.update(owner[(ci, cj)])
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    nb = (ci + di, cj + dj)
                    if nb in owner and nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
        out.append(_union([boxes[i] for i in members]))
    # zones qui se chevauchent (une grande boîte) : réunies
    merged = True
    while merged:
        merged = False
        for i in range(len(out)):
            for j in range(i + 1, len(out)):
                a, b = out[i], out[j]
                if a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]:
                    out[i] = _union([a, b])
                    del out[j]
                    merged = True
                    break
            if merged:
                break
    rh = max(w, h) / GRID                             # même rangée : hauts à une case près
    return sorted(out, key=lambda r: (-round(r[3] / rh), r[0]))
