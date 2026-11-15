"""Géométrie : contours, transformations, hachurage.

Une *polyligne* est une liste de points `(x, y)`. Un *contour* est une
polyligne fermée (le dernier point rejoint le premier implicitement).
"""
from __future__ import annotations

import math

Point = tuple[float, float]
Polyline = list[Point]


# --- transformations -------------------------------------------------------

def rotate(points: Polyline, angle_deg: float,
           cx: float = 0.0, cy: float = 0.0) -> Polyline:
    if not angle_deg:
        return list(points)
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    return [((x - cx) * ca - (y - cy) * sa + cx,
             (x - cx) * sa + (y - cy) * ca + cy) for x, y in points]


def translate(points: Polyline, dx: float, dy: float) -> Polyline:
    return [(x + dx, y + dy) for x, y in points]


def scale(points: Polyline, factor: float) -> Polyline:
    return [(x * factor, y * factor) for x, y in points]


def scale_xy(points: Polyline, fx: float, fy: float) -> Polyline:
    """Mise à l'échelle indépendante sur chaque axe."""
    return [(x * fx, y * fy) for x, y in points]


def bounds(polylines: list[Polyline]) -> tuple[float, float, float, float] | None:
    xs = [x for p in polylines for x, _ in p]
    ys = [y for p in polylines for _, y in p]
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


# --- primitives ------------------------------------------------------------

def rect_contour(width: float, height: float,
                 cx: float = 0.0, cy: float = 0.0) -> Polyline:
    """Rectangle centré sur (cx, cy), sens trigonométrique, fermé."""
    hw, hh = width / 2, height / 2
    return [(cx - hw, cy - hh), (cx + hw, cy - hh), (cx + hw, cy + hh),
            (cx - hw, cy + hh), (cx - hw, cy - hh)]


def circle_contour(radius: float, cx: float = 0.0, cy: float = 0.0,
                   tolerance: float = 0.02) -> Polyline:
    """Cercle discrétisé, fermé.

    Le nombre de segments découle de la tolérance de corde voulue : un
    petit cercle n'a pas besoin d'autant de points qu'un grand.

    Ce nombre est arrondi à un **multiple de quatre** pour que les quatre
    points cardinaux tombent exactement sur le contour : sans cela, un
    cercle de ⌀20 mesurait 19,988 mm sur un axe et 20 sur l'autre — un
    écart invisible à l'écran mais bien réel sur la pièce.
    """
    if radius <= 0:
        return []
    ratio = max(1e-9, min(1.0, tolerance / radius))
    steps = max(12, min(720, int(math.ceil(math.pi / math.acos(1 - ratio)))))
    steps += (-steps) % 4
    pts = [(cx + radius * math.cos(2 * math.pi * i / steps),
            cy + radius * math.sin(2 * math.pi * i / steps))
           for i in range(steps)]
    pts.append(pts[0])
    return pts


def flatten_cubic(p0: Point, p1: Point, p2: Point, p3: Point,
                  tolerance: float = 0.01) -> Polyline:
    """Discrétise une Bézier cubique, hors point de départ.

    Le nombre de segments est déduit d'une borne grossière de la courbure.
    """
    d = (abs(p0[0] - 2 * p1[0] + p2[0]) + abs(p0[1] - 2 * p1[1] + p2[1])
         + abs(p1[0] - 2 * p2[0] + p3[0]) + abs(p1[1] - 2 * p2[1] + p3[1]))
    n = max(2, min(64, int(math.sqrt(d / max(tolerance, 1e-6)) * 2)))
    out: Polyline = []
    for i in range(1, n + 1):
        t = i / n
        u = 1 - t
        out.append((
            u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0],
            u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1],
        ))
    return out


# --- hachurage -------------------------------------------------------------

def hatch(contours: list[Polyline], step: float,
          angle_deg: float = 0.0) -> list[Polyline]:
    """Remplit `contours` de segments parallèles espacés de `step`.

    Règle pair-impair : un point est intérieur si le nombre d'intersections
    à sa gauche est impair — ce qui gère naturellement les contres-formes
    (le trou du « O », l'intérieur du « A »).

    Les segments sont produits en balayage alterné (zigzag) pour limiter
    les déplacements à vide.
    """
    if step <= 0 or not contours:
        return []

    # on travaille dans un repère où les hachures sont horizontales
    work = [rotate(c, -angle_deg) for c in contours]
    b = bounds(work)
    if b is None:
        return []
    x1, y1, x2, y2 = b

    segments: list[Polyline] = []
    n = int((y2 - y1) / step) + 1
    for i in range(n + 1):
        y = y1 + i * step
        if y > y2:
            break
        xs: list[float] = []
        for contour in work:
            pts = contour if contour[0] == contour[-1] else contour + [contour[0]]
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                if ay == by:
                    continue
                lo, hi = (ay, by) if ay < by else (by, ay)
                # borne basse inclusive, borne haute exclusive :
                # évite de compter deux fois un sommet partagé
                if not (lo <= y < hi):
                    continue
                xs.append(ax + (y - ay) * (bx - ax) / (by - ay))
        xs.sort()
        row = [[(xs[k], y), (xs[k + 1], y)] for k in range(0, len(xs) - 1, 2)
               if xs[k + 1] - xs[k] > 1e-9]
        if i % 2:
            row.reverse()
            row = [list(reversed(seg)) for seg in row]
        segments.extend(row)

    return [rotate(s, angle_deg) for s in segments]


# --- tracés qui gardent leurs courbes --------------------------------------

class Chemin:
    """Un tracé qui garde ses COURBES, en plus de sa polyligne.

    Le noyau vectoriel rend des polylignes : c'est ce qu'il faut pour
    usiner, et tout le reste du module raisonne dessus. Mais une courbe
    aplatie ne redevient jamais une courbe : à l'écran elle montre ses
    facettes au zoom, et ressortie en fichier elle pèse mille points là
    où quatre suffisent.

    Un Chemin porte donc les deux : `commandes` — ('M', x, y),
    ('L', x, y), ('C', x1, y1, x2, y2, x3, y3), ('Z',) — et `points`,
    l'aplatissement calculé au fil de la construction.

    Il se comporte comme la liste de ses points : tout ce qui lisait
    des polylignes continue de fonctionner sans rien savoir de lui.
    """

    __slots__ = ('commandes', 'points', 'tolerance')

    def __init__(self, points: Polyline | None = None,
                 tolerance: float = 0.02) -> None:
        self.commandes: list[tuple] = []
        self.points: Polyline = []
        self.tolerance = tolerance
        if points:
            self.depuis_points(points)

    # -- construction -------------------------------------------------------

    def depuis_points(self, points: Polyline) -> 'Chemin':
        """Reprend une polyligne déjà calculée (texte vectorisé,
        primitive sans courbe)."""
        points = list(points)
        if not points:
            return self
        self.moveto(*points[0])
        for x, y in points[1:]:
            self.lineto(x, y)
        return self

    def moveto(self, x: float, y: float) -> None:
        self.commandes.append(('M', x, y))
        self.points.append((x, y))

    def lineto(self, x: float, y: float) -> None:
        if not self.points:
            return self.moveto(x, y)
        self.commandes.append(('L', x, y))
        self.points.append((x, y))

    def cubicto(self, p1: Point, p2: Point, p3: Point) -> None:
        """Bézier cubique : gardée telle quelle ET aplatie."""
        if not self.points:
            return self.moveto(*p3)
        p0 = self.points[-1]
        self.commandes.append(
            ('C', p1[0], p1[1], p2[0], p2[1], p3[0], p3[1]))
        self.points.extend(flatten_cubic(p0, p1, p2, p3, self.tolerance))

    def fermer(self) -> None:
        """Referme le tracé sur son point de départ."""
        if len(self.points) < 2:
            return
        depart = self.points[0]
        if self.points[-1] != depart:
            self.points.append(depart)
        self.commandes.append(('Z',))

    # -- lecture ------------------------------------------------------------

    def est_ferme(self) -> bool:
        return bool(self.commandes) and self.commandes[-1][0] == 'Z'

    def transforme(self, f) -> 'Chemin':
        """Un nouveau chemin dont chaque point passe par `f(x, y)`.

        Les points de contrôle passent par la même fonction que les
        sommets : une Bézier transformée par une matrice affine reste
        la même Bézier, contrôles transformés."""
        autre = Chemin(tolerance=self.tolerance)
        for commande in self.commandes:
            nom = commande[0]
            coords = commande[1:]
            paires = [f(coords[i], coords[i + 1])
                      for i in range(0, len(coords), 2)]
            autre.commandes.append(
                (nom,) + tuple(v for p in paires for v in p))
        autre.points = [f(x, y) for x, y in self.points]
        return autre

    # -- il se lit comme une polyligne --------------------------------------

    def __len__(self) -> int:
        return len(self.points)

    def __iter__(self):
        return iter(self.points)

    def __getitem__(self, index):
        return self.points[index]

    def __repr__(self) -> str:
        courbes = sum(1 for c in self.commandes if c[0] == 'C')
        return (f'<Chemin {len(self.commandes)} commandes '
                f'({courbes} courbes), {len(self.points)} points>')
