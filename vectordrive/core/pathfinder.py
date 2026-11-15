"""Pathfinder (comme les commandes de même nom des logiciels de dessin
vectoriel) sur des formes empilées, de la plus basse à la plus haute :

* **diviser** : toutes les pièces délimitées par les contours qui se
  croisent, chacune prenant l'outil de la forme visible au-dessus d'elle ;
* **détourer** : chaque forme privée de ce que cachent celles du dessus
  (parties cachées supprimées) ;
* **fusionner** : comme détourer, puis les pièces voisines du même outil
  réunies ;
* **recadrer** : la forme du dessus sert de cadre — les autres sont
  coupées à son contour et elle disparaît ;
* **soustraire l'arrière** : la forme du dessus privée de toutes les autres.

Les fonctions prennent [(Path, outil)] (du bas vers le haut) et rendent
[(Path, outil)].
"""
from __future__ import annotations

from .geom import Path
from .pathops import _from_shapely, _to_shapely

OPS = (('divide', 'Diviser'), ('trim', 'Détourer'), ('merge', 'Fusionner'), ('crop', 'Recadrer'),
       ('minus_back', "Soustraire l'arrière"))


def _regions(items):
    return [(_to_shapely(p), t) for p, t in items]


def _out(geoms_tools) -> list[tuple[Path, int]]:
    out = []
    for g, t in geoms_tools:
        if g is None or g.is_empty or g.area < 1e-9:
            continue
        p = _from_shapely(g)
        if p.contours:
            out.append((p, t))
    return out


def _faces(items) -> list:
    """[(polygone, outil)] : pièces de l'arrangement des contours, chacune à
    l'outil de la forme la plus haute qui la couvre."""
    import shapely
    regs = _regions(items)
    lines = shapely.union_all([shapely.boundary(g) for g, _t in regs if not g.is_empty])
    faces = shapely.get_parts(shapely.polygonize(shapely.get_parts(lines)))
    out = []
    for f in faces:
        if f.area < 1e-9:
            continue
        pt = f.representative_point()
        owner = None
        for g, t in reversed(regs):                         # la plus haute d'abord
            if g.contains(pt):
                owner = t
                break
        if owner is not None:
            out.append((f, owner))
    return out


def divide(items) -> list[tuple[Path, int]]:
    """Pièces de l'arrangement des contours, chacune à l'outil de la forme la
    plus haute qui la couvre ; une pièce par polygone."""
    return _out(_faces(items))


def build(items, stroke, delete: bool = False) -> tuple[list[tuple[Path, int]], int]:
    """Concepteur de formes : les pièces de l'arrangement que touche le tracé
    `stroke` (points ; un seul point : un clic) sont réunies en une forme (à
    l'outil de la première touchée), ou supprimées si `delete` ; les autres
    pièces restent séparées. Rend les formes et le nombre de pièces touchées."""
    import shapely
    from shapely.geometry import LineString, Point
    faces = _faces(items)
    probe = Point(stroke[0]) if len(stroke) < 2 else LineString(stroke)
    hit = [i for i, (f, _t) in enumerate(faces) if f.intersects(probe)]
    if len(stroke) >= 2:                     # ordre de passage : outil de la première traversée
        hit.sort(key=lambda i: probe.project(faces[i][0].representative_point()))
    rest = [ft for i, ft in enumerate(faces) if i not in set(hit)]
    if not hit:
        return _out(faces), 0
    if delete:
        return _out(rest), len(hit)
    merged = shapely.union_all([faces[i][0] for i in hit]).buffer(0)
    return _out([(merged, faces[hit[0]][1])] + rest), len(hit)


def trim(items) -> list[tuple[Path, int]]:
    """Chaque forme moins ce que couvrent les formes posées au-dessus."""
    import shapely
    regs = _regions(items)
    out = []
    above = None
    for g, t in reversed(regs):
        vis = g if above is None else shapely.difference(g, above)
        out.append((vis, t))
        above = g if above is None else shapely.union(above, g)
    return _out(reversed(out))


def merge(items) -> list[tuple[Path, int]]:
    """Détourer, puis réunir les pièces visibles d'un même outil."""
    import shapely
    pieces = trim(items)
    by_tool: dict = {}
    for p, t in pieces:
        by_tool.setdefault(t, []).append(_to_shapely(p))
    return _out((shapely.union_all(gs), t) for t, gs in by_tool.items())


def crop(items) -> list[tuple[Path, int]]:
    """La forme du dessus comme cadre : les autres (détourées entre elles)
    coupées à son contour ; le cadre disparaît."""
    import shapely
    if len(items) < 2:
        return list(items)
    frame = _to_shapely(items[-1][0])
    return _out((shapely.intersection(_to_shapely(p), frame), t) for p, t in trim(items[:-1]))


def minus_back(items) -> list[tuple[Path, int]]:
    """La forme du dessus moins toutes celles de dessous."""
    import shapely
    if len(items) < 2:
        return list(items)
    top, t = items[-1]
    below = shapely.union_all([_to_shapely(p) for p, _t in items[:-1]])
    return _out([(shapely.difference(_to_shapely(top), below), t)])


def apply(op: str, items) -> list[tuple[Path, int]]:
    return {'divide': divide, 'trim': trim, 'merge': merge, 'crop': crop, 'minus_back': minus_back}[op](items)
