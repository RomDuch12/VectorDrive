"""Une pièce STEP en vraies faces tirée des contours fermés du dessin
(« Pièce du dessin », onglet Design STEP).

Les contours (mm, Y vers le haut, comme le STEP) sont ramenés à des droites
et des arcs de cercle (`biarc.to_arcs`, à `TOL` près) : un arc reste un
arc, sa paroi un vrai cylindre ; un contour fait d'arcs d'un même cercle
est un cercle (`brep.Circle`, un trou rond reconnu par « Vis dans ce trou »).
Le contour le plus extérieur est le bord de la pièce ; dans la matière,
chaque contour intérieur est selon le mode :

- `trous` : un trou débouchant ;
- `poches` : une poche de la profondeur donnée, depuis le dessus ;
- `ronds` : débouchant s'il est rond, une poche sinon (plaque gravée :
  trous de fixation et lumières).

Un contour dans une poche est un îlot (matière) ; un contour dans un îlot,
de nouveau un trou ou une poche. Un îlot dans un trou débouchant serait une
pièce détachée : refusé. Le dessus de la pièce est à Z = épaisseur, le
dessous à Z = 0.
"""
from __future__ import annotations

import math

from . import biarc
from . import brep as B
from .geom import Conic, Line

#: écart (mm) des droites et arcs aux courbes du dessin
TOL = 0.01
MODES = ('trous', 'poches', 'ronds')
#: segment ou écart de fermeture laissé (mm) : le noyau B-rep confond les sommets plus proches
SHORT = 2 * B.EPS


class DrawError(ValueError):
    """Pas de pièce possible (rien de fermé, cotes impossibles, contours qui se coupent)."""


def _arc(s) -> tuple | None:
    """(centre, rayon, départ, balayage en degrés) d'un arc de cercle, sinon None."""
    if isinstance(s, Conic):
        return s.circle_params()
    return None


def _loop(c, tol: float):
    """La boucle du noyau B-rep d'un contour fermé (droites et arcs), None s'il est vide ou plat."""
    pts, bulges, arcs = [], [], []
    for s in c.segments:
        a, b = s.start, s.end
        if math.dist(a, b) < SHORT:                    # plus court que le noyau ne l'écrit : laissé
            continue
        arc = _arc(s)
        if arc is not None:
            pts.append((float(a[0]), float(a[1])))
            bulges.append(math.tan(math.radians(arc[3]) / 4.0))
            arcs.append(arc)
        elif isinstance(s, Line):
            pts.append((float(a[0]), float(a[1])))
            bulges.append(0.0)
        else:                                          # courbe restée : des droites
            flat = [a] + list(s.flatten(tol))
            for p in flat[:-1]:
                pts.append((float(p[0]), float(p[1])))
                bulges.append(0.0)
    if pts and c.segments and math.dist(pts[0], c.segments[-1].end) > SHORT:
        pts.append((float(c.segments[-1].end[0]), float(c.segments[-1].end[1])))     # fermé sans segment
        bulges.append(0.0)
    if arcs and len(arcs) == len(pts):                 # que des arcs d'un même cercle : un cercle
        (cx, cy), r = arcs[0][0], arcs[0][1]
        if all(math.dist(x[0], (cx, cy)) <= tol and abs(x[1] - r) <= tol for x in arcs) \
                and abs(abs(sum(x[3] for x in arcs)) - 360.0) < 1e-3:
            return B.Circle(float(cx), float(cy), float(r))
    if len(pts) < 2 or (len(pts) < 3 and not any(bulges)):
        return None
    return B.Poly(pts, bulges if any(bulges) else None)


def loops(path, tol: float = TOL) -> tuple:
    """(boucles des contours fermés de `path`, nombre de contours ouverts laissés)."""
    P = biarc.to_arcs(path, tol)
    out, left = [], 0
    for c in P.contours:
        if not c.segments:
            continue
        if not c.closed:
            left += 1
            continue
        lp = _loop(c, tol)
        if lp is not None:
            out.append(lp)
    return out, left


#: écart (mm) des cordes aux arcs pour l'imbrication et les contours qui se recoupent
SAG = 1e-3


def _points(lp) -> list:
    """Points de la boucle, les arcs en cordes à SAG près au plus (64 par tour au moins) : un contour près
    d'un bord de grand rayon reste dedans."""
    pts = []
    for sg in B._segments(lp, 0.0, 0.0, 1.0):
        n = 64
        if sg[0] == 'arc' and sg[2] > SAG:
            n = max(n, min(int(math.pi / math.acos(1.0 - SAG / sg[2])) + 1, 200000))
        pts += B._seg_points(sg, n)
    return pts


def _polygon(lp):
    from shapely.geometry import Polygon
    return Polygon(_points(lp))


def _simple(lp) -> bool:
    """La boucle ne se recoupe ni ne se touche, et a une surface."""
    from shapely.geometry import LinearRing
    pts = _points(lp)
    return len(pts) >= 3 and abs(B._area(pts)) > B.EPS and LinearRing(pts).is_simple


def nesting(lps: list) -> list:
    """Pour chaque boucle, (profondeur, boucle qui la contient directement ou None) : 0 pour le bord."""
    from shapely.geometry import Point
    from shapely.prepared import prep
    polys = [_polygon(lp) for lp in lps]
    pp = [prep(p) for p in polys]
    out = []
    for i, p in enumerate(polys):
        pt = Point(p.exterior.coords[0])                # un point du contour, dans ceux qui le contiennent
        holders = [j for j in range(len(polys)) if j != i and pp[j].contains(pt)]
        parent = min(holders, key=lambda j: polys[j].area) if holders else None
        out.append((len(holders), parent))
    return out


def bodies(path, thickness: float, mode: str = 'trous', pocket: float = 0.0, name: str = 'piece',
           tol: float = TOL) -> list:
    """Les pièces : une par bord (contour le plus extérieur) des contours fermés de `path`, sur `thickness` de
    haut, contours intérieurs selon `mode` (poches de `pocket` de profondeur) ; DrawError si impossible."""
    if mode not in MODES:
        raise DrawError(f'mode inconnu : {mode}')
    if not thickness > 0:
        raise DrawError('épaisseur nulle')
    lps, _left = loops(path, tol)
    if not lps:
        raise DrawError('aucun contour fermé')
    if not all(_simple(lp) for lp in lps):
        raise DrawError('contour qui se recoupe ou sans surface (en huit, en étoile croisée, aplati)')
    try:                                               # d'abord : contours qui se coupent ou se touchent
        B.check(B.Body(name, [B.Slab(0.0, float(thickness), lps)]))
    except B.BrepError as ex:
        raise DrawError(str(ex).split(' : ', 1)[-1]) from None
    nest = nesting(lps)
    through = [mode == 'trous' or (mode == 'ronds' and isinstance(lp, B.Circle)) for lp in lps]
    for d, parent in nest:
        if d and d % 2 == 0 and through[parent]:
            raise DrawError('îlot dans un trou débouchant : une pièce détachée (le mettre en poche, ou le relier)')

    def edge(i):                                       # le bord qui contient la boucle i
        while nest[i][1] is not None:
            i = nest[i][1]
        return i
    groups: dict = {}
    for i in range(len(lps)):
        groups.setdefault(edge(i), []).append(i)
    out = []
    for n, (top, members) in enumerate(sorted(groups.items(), key=lambda kv: _polygon(lps[kv[0]]).bounds[:2])):
        label = name if len(groups) == 1 else f'{name}_{n + 1}'
        own = [lps[i] for i in members]
        if not any(nest[i][0] % 2 == 1 and not through[i] for i in members):
            slabs = [B.Slab(0.0, float(thickness), own)]
        else:
            if not 0 < pocket < thickness:
                raise DrawError(f'profondeur de poche hors de ]0, {thickness:g}[')
            below = [lps[i] for i in members if nest[i][0] == 0 or (nest[i][0] % 2 == 1 and through[i])]
            floor = float(thickness - pocket)              # bord et trous débouchants (jusque dans un îlot)
            slabs = [B.Slab(0.0, floor, below), B.Slab(floor, float(thickness), own)]
        b = B.Body(label, slabs)
        try:
            B.check(b)
        except B.BrepError as ex:
            raise DrawError(str(ex).split(' : ', 1)[-1]) from None
        out.append(b)
    return out


def summary(path, tol: float = TOL) -> dict:
    """Ce que donnent les contours : fermés, ouverts laissés, ronds, encombrement (x0, y0, x1, y1)."""
    lps, left = loops(path, tol)
    box = None
    if lps:
        bs = [B.Body('', [B.Slab(0.0, 1.0, [lp])]).bounds() for lp in lps]
        box = (min(b[0] for b in bs), min(b[1] for b in bs), max(b[3] for b in bs), max(b[4] for b in bs))
    return {'closed': len(lps), 'open': left, 'circles': sum(isinstance(lp, B.Circle) for lp in lps), 'bounds': box}
