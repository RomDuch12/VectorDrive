"""Ligne double (comme Ligne simple/double de TypeEdit, MLIGNE en DAO) : une
polyligne tracée comme deux traits parallèles écartés de `width` — calés
au centre, à gauche ou à droite du trait cliqué ; bouts ouverts, fermés
(un contour fermé) ou arrondis. Angles aigus (à onglet), chanfreinés ou arrondis ;
chaque trait peut avoir son propre espacement à l'axe cliqué.
"""
from __future__ import annotations

from .geom import Path, polyline

JUSTIFY = ('centre', 'gauche', 'droite')
ENDS = ('ouvert', 'ferme', 'arrondi')
LABELS = {'centre': 'Centrée', 'gauche': 'À gauche', 'droite': 'À droite',
          'ouvert': 'Bouts ouverts', 'ferme': 'Bouts fermés', 'arrondi': 'Bouts arrondis'}
MITRE = 5.0
CORNERS = ('aigu', 'chanfrein', 'arrondi')
_JOINS = {'aigu': 2, 'chanfrein': 3, 'arrondi': 1}
QUAD_SEGS = 32                                       # points par quart de tour des coins et des bouts arrondis


def sides_of(o: dict) -> tuple[float, float]:
    """(à gauche, à droite) de l'axe, depuis un réglage qui les donne ou qui donne l'écartement et le calage."""
    if o.get('left') is not None or o.get('right') is not None:
        return max(0.0, float(o.get('left') or 0.0)), max(0.0, float(o.get('right') or 0.0))
    w = abs(float(o.get('width', 2.0)))
    return {'gauche': (w, 0.0), 'droite': (0.0, w)}.get(o.get('justify', 'centre'), (w / 2, w / 2))


def _coords(g) -> list:
    """Polylignes (listes de points) d'une géométrie linéaire shapely."""
    if g.is_empty:
        return []
    if g.geom_type == 'LineString' or g.geom_type == 'LinearRing':
        return [list(g.coords)]
    return [c for p in getattr(g, 'geoms', []) for c in _coords(p)]


def _end_caps(line, left: float, right: float) -> list:
    """Les ronds des deux bouts d'un trait aux côtés inégaux : au milieu des deux traits, leur écart pour diamètre."""
    import math

    from shapely.geometry import Point
    out = []
    co = list(line.coords)
    for a, b in ((co[1], co[0]), (co[-2], co[-1])):
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        nx, ny = -(b[1] - a[1]) / d, (b[0] - a[0]) / d
        if (a, b) == (co[1], co[0]):
            nx, ny = -nx, -ny                        # la gauche se compte dans le sens du tracé
        k = (left - right) / 2
        out.append(Point(b[0] + nx * k, b[1] + ny * k).buffer((left + right) / 2, quad_segs=QUAD_SEGS))
    return out


def double_line(points, width: float, justify: str = 'centre', ends: str = 'ouvert',
                closed: bool = False, corners: str = 'aigu', left: float | None = None,
                right: float | None = None) -> Path:
    """Contours de la ligne double sur les points cliqués (`closed` : la
    polyligne reboucle — deux contours fermés, sans bouts). `left` et `right` :
    l'espacement de chaque trait à l'axe, à la place de `width` et `justify`."""
    from shapely.geometry import LineString, Polygon
    from shapely.ops import unary_union
    pts = []
    for p in points:
        p = (float(p[0]), float(p[1]))
        if not pts or p != pts[-1]:
            pts.append(p)
    if closed and len(pts) > 2 and pts[0] == pts[-1]:
        pts.pop()
    gauche, droite = sides_of({'width': width, 'justify': justify, 'left': left, 'right': right})
    if len(pts) < 2 or gauche + droite <= 1e-9:
        return Path([])
    join = {'join_style': _JOINS.get(corners, 2), 'mitre_limit': MITRE, 'quad_segs': QUAD_SEGS}
    if closed and len(pts) > 2:
        ring = Polygon(pts)
        if not ring.is_valid:
            ring = ring.buffer(0)
        sg = 1.0 if ring.exterior.is_ccw else -1.0       # gauche du parcours cliqué : dedans si anti-horaire
        a = ring.buffer(-sg * gauche, **join)
        b = ring.buffer(sg * droite, **join)
        out = []
        for g in (a, b):
            for poly in getattr(g, 'geoms', [g]):
                if not poly.is_empty:
                    out.append(polyline(list(poly.exterior.coords), closed=True))
        return Path(out)
    line = LineString(pts)
    if ends == 'ouvert':
        sides = [line.offset_curve(gauche, **join) if gauche else line,
                 line.offset_curve(-droite, **join) if droite else line]
        return Path([polyline(c) for g in sides for c in _coords(g) if len(c) >= 2])
    if abs(gauche - droite) < 1e-9:
        g = line.buffer(gauche, cap_style=1 if ends == 'arrondi' else 2, **join)
    else:
        parts = [line.buffer(d, cap_style=2, single_sided=True, **join) for d in (gauche, -droite) if d]
        if ends == 'arrondi':
            parts += _end_caps(line, gauche, droite)
        g = unary_union(parts)
    out = []
    for poly in getattr(g, 'geoms', [g]):
        if poly.is_empty:
            continue
        out.append(polyline(list(poly.exterior.coords), closed=True))
        out += [polyline(list(r.coords), closed=True) for r in poly.interiors]
    return Path(out)
