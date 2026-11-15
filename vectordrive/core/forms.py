"""Formes géométriques paramétrées, éditables après coup (comme les objets
éditables de TypeEdit) : rectangle, ellipse, polygone, étoile, spirale,
flèche, arc par sa corde, oblong, anneau, secteur de couronne.

Une forme garde ses paramètres de construction dans `Shape.extra['forme']`
({type, paramètres…, sig}). On la rouvre (F2 pendant la création,
double-clic, ou l'outil cliqué avec la forme sélectionnée) pour changer un
paramètre : elle est recalculée. Un déplacement, une rotation ou une mise à
l'échelle uniforme (miroir compris) mettent ses paramètres à jour ; toute
autre retouche (nœuds, booléennes, étirement) en fait une courbe ordinaire :
la signature `sig` (nombre de segments, boîte) ne correspond plus.

Les types sont des dataclasses : `FIELDS` (libellés, bornes, choix) sert
au formulaire, `build()` rend le tracé.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, fields, replace

from . import geom
from .geom import Contour, Cubic, Path

KEY = 'forme'


# --- les formes ---------------------------------------------------------------------------------

@dataclass
class Rect:
    kind: str = 'rect'
    cx: float = 0.0
    cy: float = 0.0
    width: float = 40.0
    height: float = 20.0
    corner: str = 'droit'           # droit, arrondi, chanfrein, creux
    radius: float = 3.0             # rayon de l'arrondi / longueur du chanfrein
    angle: float = 0.0

    def build(self) -> Path:
        w, h = abs(self.width), abs(self.height)
        c = geom.rect(self.cx - w / 2, self.cy - h / 2, w, h)
        r = min(abs(self.radius), w / 2 - 1e-6, h / 2 - 1e-6)
        if self.corner != 'droit' and r > 1e-6:
            if self.corner == 'arrondi':
                c = geom.rect(self.cx - w / 2, self.cy - h / 2, w, h, r)
            elif self.corner == 'chanfrein':
                c = geom.corner_contour(c, r, 'chamfer')
            else:                                     # creux : arcs concaves aux coins
                c = _concave_rect(self.cx, self.cy, w, h, r)
        return _rotated(Path([c]), self.angle, (self.cx, self.cy))


@dataclass
class Ellipse:
    kind: str = 'ellipse'
    cx: float = 0.0
    cy: float = 0.0
    width: float = 30.0
    height: float = 20.0
    angle: float = 0.0

    def build(self) -> Path:
        return Path([geom.ellipse((self.cx, self.cy), abs(self.width) / 2, abs(self.height) / 2, self.angle)])


@dataclass
class Polygon:
    kind: str = 'polygon'
    cx: float = 0.0
    cy: float = 0.0
    sides: int = 6
    size: float = 20.0
    size_mode: str = 'sommet'       # sommet (rayon extérieur), cote (rayon intérieur), longueur (d'un côté)
    angle: float = 90.0             # direction du premier sommet
    rounding: float = 0.0           # arrondi des sommets

    def circumradius(self) -> float:
        n = max(3, int(self.sides))
        s = abs(self.size)
        if self.size_mode == 'cote':
            return s / math.cos(math.pi / n)
        if self.size_mode == 'longueur':
            return s / (2 * math.sin(math.pi / n))
        return s

    def build(self) -> Path:
        c = geom.polygon((self.cx, self.cy), self.circumradius(), max(3, int(self.sides)), self.angle)
        if self.rounding > 1e-6:
            c = geom.corner_contour(c, self.rounding, 'fillet')
        return Path([c])


def rect_by_3points(a, b, c, base: Rect | None = None) -> Rect | None:
    """Rectangle dont `a`–`b` est un côté (il donne l'inclinaison) et dont
    l'autre côté va jusqu'à `c`, compté perpendiculairement à `a`–`b` (RECTANG
    incliné, d'après CADCraft) ; posé du côté de `c`. `base` : coins repris
    (arrondi, chanfrein…). None si un côté est nul."""
    w = math.dist(a, b)
    if w < 1e-9:
        return None
    ux, uy = (b[0] - a[0]) / w, (b[1] - a[1]) / w
    h = (c[0] - a[0]) * -uy + (c[1] - a[1]) * ux                 # distance signée, positive à gauche de a→b
    if abs(h) < 1e-9:
        return None
    r = Rect(**{f.name: getattr(base, f.name) for f in fields(Rect)}) if base is not None else Rect()
    r.cx, r.cy = a[0] + ux * w / 2 - uy * h / 2, a[1] + uy * w / 2 + ux * h / 2
    r.width, r.height, r.angle = w, abs(h), math.degrees(math.atan2(uy, ux))
    return r


def ellipse_by_axis(a, b, c) -> Ellipse | None:
    """Ellipse dont `a`–`b` est un axe et dont l'autre demi-axe va du
    centre jusqu'à `c` (ELLIPSE par les bouts d'un axe, d'après CADCraft) ;
    inclinée comme `a`–`b`. None si l'axe ou l'autre demi-axe est nul."""
    w = math.dist(a, b)
    cx, cy = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    h = 2 * math.dist((cx, cy), c)
    if w < 1e-9 or h < 1e-9:
        return None
    return Ellipse(cx=cx, cy=cy, width=w, height=h, angle=math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])))


def polygon_on_edge(a, b, sides: int, right: bool = False, base: Polygon | None = None) -> Polygon | None:
    """Polygone régulier dont `a`–`b` est un côté (POLYGON, option Côté,
    d'après CADCraft `polygon_from_edge`) : posé à gauche du côté parcouru de
    `a` vers `b`, à droite si `right` ; réglé par la longueur du côté, son
    premier sommet en `a`. `base` : réglages repris (arrondi). None si les
    points se confondent."""
    s = math.dist(a, b)
    if s < 1e-9:
        return None
    n = max(3, int(sides))
    ux, uy = (b[0] - a[0]) / s, (b[1] - a[1]) / s
    h = (s / (2 * math.tan(math.pi / n))) * (-1 if right else 1)        # apothème, vers la gauche du côté
    cx, cy = (a[0] + b[0]) / 2 - uy * h, (a[1] + b[1]) / 2 + ux * h
    p = Polygon(**{f.name: getattr(base, f.name) for f in fields(Polygon)}) if base is not None else Polygon()
    p.cx, p.cy, p.sides, p.size, p.size_mode = cx, cy, n, s, 'longueur'
    p.angle = math.degrees(math.atan2(a[1] - cy, a[0] - cx))
    return p


@dataclass
class Star:
    kind: str = 'star'
    cx: float = 0.0
    cy: float = 0.0
    branches: int = 5
    r_out: float = 20.0
    r_in: float = 8.0
    angle: float = 90.0             # direction de la première pointe
    twist: float = 0.0              # décalage des creux (°) : pointes de travers, en hélice
    rounding: float = 0.0           # arrondi des pointes et des creux

    def build(self) -> Path:
        n = max(2, int(self.branches))
        pts = []
        for i in range(2 * n):
            r = abs(self.r_out) if i % 2 == 0 else abs(self.r_in)
            a = math.radians(self.angle + 180.0 * i / n + (self.twist if i % 2 else 0.0))
            pts.append((self.cx + r * math.cos(a), self.cy + r * math.sin(a)))
        c = geom.polyline(pts, closed=True)
        if self.rounding > 1e-6:
            c = geom.corner_contour(c, self.rounding, 'fillet')
        return Path([c])


@dataclass
class Spiral:
    kind: str = 'spiral'
    cx: float = 0.0
    cy: float = 0.0
    turns: float = 3.0
    r_out: float = 20.0
    r_in: float = 0.0
    angle: float = 0.0              # direction du bout extérieur
    clockwise: bool = False
    law: str = 'archimede'          # archimede (pas constant), log (logarithmique)

    def build(self) -> Path:
        if self.law == 'log':
            return Path([_log_spiral((self.cx, self.cy), abs(self.r_out), max(abs(self.r_in), abs(self.r_out) * 0.02),
                                     max(self.turns, 0.05), self.angle, not self.clockwise)])
        return Path([geom.spiral((self.cx, self.cy), abs(self.r_out), max(self.turns, 0.05), self.angle,
                                 min(abs(self.r_in), abs(self.r_out) * 0.99), ccw=not self.clockwise)])


@dataclass
class Arrow:
    kind: str = 'arrow'
    x: float = 0.0                  # point d'ancrage
    y: float = 0.0
    anchor: str = 'depart'          # depart (base de la queue), centre, pointe
    angle: float = 0.0              # direction de la pointe
    style: str = 'standard'         # standard, orthogonale, filaire
    length: float = 40.0
    head_length: float = 12.0
    head_width: float = 16.0
    shaft_width: float = 5.0
    notch: float = 0.0              # retrait de la pointe vers l'avant (0 à 0,9 de sa longueur)
    double: bool = False

    def build(self) -> Path:
        L = max(abs(self.length), 0.1)
        hw = max(abs(self.head_width), 0.01)
        hl = hw / 2 if self.style == 'orthogonale' else abs(self.head_length)
        hl = min(hl, L / (2 if self.double else 1))
        sw = min(max(abs(self.shaft_width), 0.01), hw) / 2
        k = min(max(self.notch, 0.0), 0.9) * hl if self.style == 'standard' else 0.0
        x0 = {'depart': 0.0, 'centre': -L / 2, 'pointe': -L}.get(self.anchor, 0.0)
        x1 = x0 + L
        if self.style == 'filaire':
            cs = [geom.polyline([(x0, 0.0), (x1, 0.0)]),
                  geom.polyline([(x1 - hl, hw / 2), (x1, 0.0), (x1 - hl, -hw / 2)])]
            if self.double:
                cs.append(geom.polyline([(x0 + hl, hw / 2), (x0, 0.0), (x0 + hl, -hw / 2)]))
            p = Path(cs)
        else:
            pts = [(x1, 0.0), (x1 - hl, hw / 2), (x1 - hl + k, sw)]
            if self.double:
                pts += [(x0 + hl - k, sw), (x0 + hl, hw / 2), (x0, 0.0), (x0 + hl, -hw / 2), (x0 + hl - k, -sw)]
            else:
                pts += [(x0, sw), (x0, -sw)]
            pts += [(x1 - hl + k, -sw), (x1 - hl, -hw / 2)]
            p = Path([geom.polyline(pts, closed=True)])
        return p.transformed(_place(self.x, self.y, self.angle))


def arrow_from_clicks(spec: Arrow, pts: list) -> Arrow:
    """La flèche des clics (TypeEdit) : base de la queue, pointe, puis un point qui donne la taille de la pointe (sa distance
    à l'axe, sa position le long de l'axe), puis un point qui donne l'épaisseur de la queue et, pour la flèche standard, la
    forme de la pointe. Tant qu'un clic manque : les proportions habituelles, puis une queue aussi large que la pointe."""
    a, b = pts[0], pts[1]
    length = math.hypot(b[0] - a[0], b[1] - a[1])
    ux, uy = ((b[0] - a[0]) / length, (b[1] - a[1]) / length) if length > 1e-9 else (1.0, 0.0)
    out = replace(spec, x=a[0], y=a[1], anchor='depart', angle=math.degrees(math.atan2(uy, ux)), length=length,
                  head_length=length * 0.3, head_width=length * 0.4, shaft_width=length * 0.15, notch=0.0)

    def axial(q):                                      # (le long de l'axe depuis la base, distance à l'axe)
        vx, vy = q[0] - a[0], q[1] - a[1]
        return vx * ux + vy * uy, abs(-vx * uy + vy * ux)
    if len(pts) >= 3:
        along, off = axial(pts[2])
        out.head_width = max(2.0 * off, 0.01)
        out.head_length = max(length - along, 0.01)
        out.shaft_width = out.head_width
    if len(pts) >= 4:
        along, off = axial(pts[3])
        out.shaft_width = max(2.0 * off, 0.01)
        hl = out.head_width / 2 if out.style == 'orthogonale' else min(out.head_length, length)
        out.notch = max(along - (length - hl), 0.0) / hl if out.style == 'standard' and hl > 0 else 0.0
    return out


@dataclass
class ChordArc:
    kind: str = 'chord_arc'
    x0: float = 0.0                 # extrémités de la corde
    y0: float = 0.0
    x1: float = 40.0
    y1: float = 0.0
    sagitta: float = 10.0           # flèche : écart du milieu de l'arc à la corde (signe : côté)
    closed: bool = False            # fermé par sa corde (segment de disque)

    def build(self) -> Path:
        c = chord_arc((self.x0, self.y0), (self.x1, self.y1), self.sagitta)
        if c is None:
            return Path([geom.polyline([(self.x0, self.y0), (self.x1, self.y1)])])
        if self.closed:
            c = Contour(list(c.segments) + [geom.Line(c.end, c.start)], True)
        return Path([c])


@dataclass
class Marker:
    kind: str = 'marker'
    cx: float = 0.0
    cy: float = 0.0
    look: int = 2                   # aspect (MARKER_LOOKS)
    size: float = 5.0
    angle: float = 0.0

    def build(self) -> Path:
        x, y, s = self.cx, self.cy, abs(self.size)
        h = s / 2
        line = lambda a, b: geom.polyline([a, b])         # noqa: E731
        plus = [line((x - h, y), (x + h, y)), line((x, y - h), (x, y + h))]
        k = h * 0.7071
        cross = [line((x - k, y - k), (x + k, y + k)), line((x - k, y + k), (x + k, y - k))]
        look = int(self.look) % 10
        cs = {0: plus, 1: cross,
              2: plus + [geom.circle((x, y), s * 0.3)],
              3: [geom.circle((x, y), h)],
              4: [geom.circle((x, y), h), geom.circle((x, y), s * 0.06)],
              5: [geom.rect(x - h, y - h, s, s)],
              6: [geom.polyline([(x + h, y), (x, y + h), (x - h, y), (x, y - h)], closed=True)],
              7: plus + [geom.rect(x - h * 0.6, y - h * 0.6, s * 0.6, s * 0.6)],
              8: plus + [geom.circle((x, y), h * 0.45), geom.circle((x, y), h * 0.85)],
              9: [geom.polygon((x, y), h, 3, 90.0)]}[look]
        return _rotated(Path(cs), self.angle, (x, y))


@dataclass
class Slot:
    """Oblong (boutonnière) : deux demi-cercles reliés, longueur hors tout."""
    kind: str = 'slot'
    cx: float = 0.0
    cy: float = 0.0
    length: float = 20.0            # hors tout
    width: float = 6.0
    angle: float = 0.0

    def build(self) -> Path:
        w = max(1e-6, abs(self.width))
        L = max(w, abs(self.length))
        r, d = w / 2, (L - w) / 2
        if d <= 1e-9:
            c = geom.circle((0, 0), r)
        else:
            segs = [geom.Line((-d, -r), (d, -r))] + geom.arc_conics((d, 0), r, r, -90.0, 180.0) + \
                   [geom.Line((d, r), (-d, r))] + geom.arc_conics((-d, 0), r, r, 90.0, 180.0)
            c = Contour(segs, True)
        return Path([c]).transformed(_place(self.cx, self.cy, self.angle))


@dataclass
class Ring:
    """Anneau : deux cercles concentriques (la couronne entre eux)."""
    kind: str = 'ring'
    cx: float = 0.0
    cy: float = 0.0
    r_out: float = 15.0
    r_in: float = 10.0
    angle: float = 0.0

    def build(self) -> Path:
        cs = [geom.circle((self.cx, self.cy), max(1e-6, abs(self.r_out)))]
        if 0 < abs(self.r_in) < abs(self.r_out):
            cs.append(geom.circle((self.cx, self.cy), abs(self.r_in)))
        return Path(cs)


@dataclass
class Sector:
    """Secteur de couronne (r_in = 0 : part de disque), de `start` sur `sweep` degrés."""
    kind: str = 'sector'
    cx: float = 0.0
    cy: float = 0.0
    r_out: float = 20.0
    r_in: float = 10.0
    start: float = 0.0
    sweep: float = 90.0
    angle: float = 0.0

    def build(self) -> Path:
        ro, ri = max(1e-6, abs(self.r_out)), max(0.0, min(abs(self.r_in), abs(self.r_out) - 1e-6))
        sw = max(-360.0, min(360.0, self.sweep))
        a0 = self.start + self.angle
        if abs(abs(sw) - 360.0) < 1e-9:
            return Ring(cx=self.cx, cy=self.cy, r_out=ro, r_in=ri).build()
        c = (self.cx, self.cy)
        outer = geom.arc_conics(c, ro, ro, a0, sw)
        t0, t1 = math.radians(a0), math.radians(a0 + sw)
        p_out_end = (c[0] + ro * math.cos(t1), c[1] + ro * math.sin(t1))
        p_out_start = (c[0] + ro * math.cos(t0), c[1] + ro * math.sin(t0))
        if ri > 1e-9:
            p_in_end = (c[0] + ri * math.cos(t1), c[1] + ri * math.sin(t1))
            p_in_start = (c[0] + ri * math.cos(t0), c[1] + ri * math.sin(t0))
            segs = outer + [geom.Line(p_out_end, p_in_end)] + geom.arc_conics(c, ri, ri, a0 + sw, -sw) + \
                [geom.Line(p_in_start, p_out_start)]
        else:
            segs = outer + [geom.Line(p_out_end, c), geom.Line(c, p_out_start)]
        return Path([Contour(segs, True)])


@dataclass
class Gear:
    """Engrenage droit à denture en développante de cercle : module m,
    z dents, angle de pression ; tête à r + m, pied à r − 1,25 m ;
    alésage central au besoin."""
    kind: str = 'gear'
    cx: float = 0.0
    cy: float = 0.0
    module: float = 2.0
    teeth: int = 20
    pressure: float = 20.0          # angle de pression (°)
    bore: float = 0.0               # Ø de l'alésage (0 : sans)
    angle: float = 0.0

    def build(self) -> Path:
        m, z = max(1e-3, abs(self.module)), max(4, int(self.teeth))
        a = math.radians(max(5.0, min(35.0, self.pressure)))
        r = m * z / 2
        ra, rf, rb = r + m, max(1e-3, r - 1.25 * m), r * math.cos(a)

        def inv(t):
            return math.tan(t) - t
        # demi-épaisseur angulaire de la dent sur le cercle de base
        half_b = math.pi / (2 * z) + inv(a)
        n = 10
        t_max = math.sqrt(max(0.0, (ra / rb) ** 2 - 1))
        r0 = max(rb, rf)
        t_min = math.sqrt(max(0.0, (r0 / rb) ** 2 - 1))
        flank = []                                           # (rayon, angle) du flanc droit, du pied à la tête
        for k in range(n + 1):
            t = t_min + (t_max - t_min) * k / n
            rr = rb * math.hypot(1, t)
            flank.append((rr, half_b - (t - math.atan(t))))
        pts = []
        pitch = 2 * math.pi / z
        for i in range(z):
            c = i * pitch
            if rf < rb:                                      # pied radial sous le cercle de base
                pts.append((rf, c - half_b))
            pts += [(rr, c - th) for rr, th in flank]        # flanc montant (côté −)
            pts += [(rr, c + th) for rr, th in reversed(flank)]
            if rf < rb:
                pts.append((rf, c + half_b))
        rot = math.radians(self.angle)
        xy = [(self.cx + rr * math.cos(th + rot), self.cy + rr * math.sin(th + rot)) for rr, th in pts]
        cs = [geom.polyline(xy, closed=True)]
        if 0 < self.bore < 2 * rf:
            cs.append(geom.circle((self.cx, self.cy), self.bore / 2))
        return Path(cs)


TYPES = {'rect': Rect, 'ellipse': Ellipse, 'polygon': Polygon, 'star': Star, 'spiral': Spiral, 'arrow': Arrow,
         'chord_arc': ChordArc, 'marker': Marker, 'slot': Slot, 'ring': Ring, 'sector': Sector, 'gear': Gear}
TITLES = {'rect': 'Rectangle', 'ellipse': 'Ellipse', 'polygon': 'Polygone', 'star': 'Étoile', 'spiral': 'Spirale',
          'arrow': 'Flèche', 'chord_arc': 'Arc par sa corde', 'marker': 'Marqueur', 'slot': 'Oblong (boutonnière)',
          'ring': 'Anneau', 'sector': 'Secteur de couronne', 'gear': 'Engrenage'}

#: champ → (libellé, minimum, maximum) ; les choix : CHOICES
LABELS = {
    'cx': ('Centre X (mm)', -1e6, 1e6), 'cy': ('Centre Y (mm)', -1e6, 1e6),
    'x': ('Ancrage X (mm)', -1e6, 1e6), 'y': ('Ancrage Y (mm)', -1e6, 1e6),
    'x0': ('Départ X (mm)', -1e6, 1e6), 'y0': ('Départ Y (mm)', -1e6, 1e6),
    'x1': ('Arrivée X (mm)', -1e6, 1e6), 'y1': ('Arrivée Y (mm)', -1e6, 1e6),
    'width': ('Largeur (mm)', 0.001, 1e6), 'height': ('Hauteur (mm)', 0.001, 1e6),
    'corner': ('Coins', None, None), 'radius': ('Rayon / chanfrein (mm)', 0.0, 1e6),
    'angle': ('Angle (°)', -360.0, 360.0), 'sides': ('Nombre de côtés', 3, 1000),
    'size': ('Taille (mm)', 0.001, 1e6), 'size_mode': ('La taille est', None, None),
    'rounding': ('Arrondi des sommets (mm)', 0.0, 1e6), 'branches': ('Nombre de branches', 2, 1000),
    'r_out': ('Rayon extérieur (mm)', 0.001, 1e6), 'r_in': ('Rayon intérieur (mm)', 0.0, 1e6),
    'twist': ('Décalage des creux (°)', -180.0, 180.0), 'turns': ('Nombre de tours', 0.05, 1000.0),
    'clockwise': ('Sens horaire', None, None), 'law': ('Spirale', None, None),
    'anchor': ('Point d\'ancrage', None, None), 'style': ('Type de flèche', None, None),
    'length': ('Longueur totale (mm)', 0.1, 1e6), 'head_length': ('Longueur de la pointe (mm)', 0.0, 1e6),
    'head_width': ('Largeur de la pointe (mm)', 0.01, 1e6), 'shaft_width': ('Épaisseur de la queue (mm)', 0.01, 1e6),
    'notch': ('Pointe en harpon (0 à 0,9)', 0.0, 0.9), 'double': ('Double flèche', None, None),
    'sagitta': ('Flèche de l\'arc (mm)', -1e6, 1e6), 'closed': ('Fermé par la corde', None, None),
    'look': ('Aspect', None, None),
    'start': ('Angle de départ (°)', -360.0, 360.0), 'sweep': ('Ouverture (°)', -360.0, 360.0),
    'module': ('Module (mm)', 0.05, 100.0), 'teeth': ('Nombre de dents', 4, 500),
    'pressure': ('Angle de pression (°)', 5.0, 35.0), 'bore': ('Ø de l\'alésage (mm, 0 : sans)', 0.0, 1e6),
}
CHOICES = {
    'corner': [('droit', 'Droits'), ('arrondi', 'Arrondis'), ('chanfrein', 'Chanfreinés'), ('creux', 'Creux (concaves)')],
    'size_mode': [('sommet', 'Rayon jusqu\'aux sommets'), ('cote', 'Rayon jusqu\'aux côtés'),
                  ('longueur', 'Longueur d\'un côté')],
    'law': [('archimede', 'D\'Archimède (pas constant)'), ('log', 'Logarithmique')],
    'anchor': [('depart', 'Base de la queue'), ('centre', 'Milieu'), ('pointe', 'Pointe')],
    'style': [('standard', 'Standard'), ('orthogonale', 'Orthogonale (pointe à 90°)'), ('filaire', 'Filaire')],
    'look': [(0, '0 — croix droite'), (1, '1 — croix oblique'), (2, '2 — croix et cercle'), (3, '3 — cercle'),
             (4, '4 — cercle et point'), (5, '5 — carré'), (6, '6 — losange'), (7, '7 — croix et carré'),
             (8, '8 — cible'), (9, '9 — triangle')],
}


def field_names(spec) -> list[str]:
    return [f.name for f in fields(spec) if f.name != 'kind']


# --- objet ↔ paramètres ----------------------------------------------------------------------------

def signature(path: Path) -> list:
    bb = path.bbox() or (0, 0, 0, 0)
    return [sum(len(c.segments) for c in path.contours), *[round(v, 4) for v in bb]]


def to_dict(spec) -> dict:
    return asdict(spec)


def from_dict(d: dict):
    cls = TYPES.get((d or {}).get('kind'))
    if cls is None:
        return None
    names = {f.name for f in fields(cls)}
    try:
        return cls(**{k: v for k, v in d.items() if k in names})
    except (TypeError, ValueError):
        return None


def attach(shape, spec) -> None:
    """Tracé recalculé d'après `spec`, paramètres gardés sur l'objet."""
    shape.path = spec.build()
    shape.extra = {**shape.extra, KEY: {**to_dict(spec), 'sig': signature(shape.path)}}


def make(spec, tool: int = 0):
    from .document import Shape
    sh = Shape(path=Path(), tool=tool)
    attach(sh, spec)
    return sh


def spec_of(shape):
    """Paramètres de la forme, s'ils décrivent encore son tracé ; sinon None."""
    d = getattr(shape, 'extra', {}).get(KEY)
    if not isinstance(d, dict) or getattr(shape, 'path', None) is None:
        return None
    if list(d.get('sig') or []) != signature(shape.path):
        return None                                   # retouchée : une courbe ordinaire
    return from_dict(d)


def _similarity(m) -> tuple[float, float, bool] | None:
    """(échelle, rotation en degrés, miroir) d'une similitude ; None sinon."""
    sx, sy = math.hypot(m.a, m.b), math.hypot(m.c, m.d)
    if sx < 1e-12 or abs(sx - sy) > 1e-9 * max(1.0, sx) or abs(m.a * m.c + m.b * m.d) > 1e-9 * sx * sx:
        return None
    det = m.a * m.d - m.b * m.c
    return sx, math.degrees(math.atan2(m.b, m.a)), det < 0


def transformed(d: dict, m, new_path: Path) -> dict | None:
    """Paramètres après la transformation `m` (similitude) ; None : la forme
    devient une courbe (étirement, cisaillement)."""
    sim = _similarity(m)
    spec = from_dict(d)
    if sim is None or spec is None:
        return None
    s, rot, mirror = sim
    if isinstance(spec, ChordArc):
        spec.x0, spec.y0 = m.apply((spec.x0, spec.y0))
        spec.x1, spec.y1 = m.apply((spec.x1, spec.y1))
        spec.sagitta *= -s if mirror else s
    else:
        if hasattr(spec, 'cx'):
            spec.cx, spec.cy = m.apply((spec.cx, spec.cy))
        else:
            spec.x, spec.y = m.apply((spec.x, spec.y))
        spec.angle = (rot - spec.angle) if mirror else (spec.angle + rot)
        spec.angle = (spec.angle + 180.0) % 360.0 - 180.0
        for name in ('width', 'height', 'radius', 'size', 'rounding', 'r_out', 'r_in', 'length', 'module', 'bore',
                     'head_length',
                     'head_width', 'shaft_width'):
            if hasattr(spec, name):
                setattr(spec, name, getattr(spec, name) * s)
        if isinstance(spec, Star) and mirror:
            spec.twist = -spec.twist
        if isinstance(spec, Spiral) and mirror:
            spec.clockwise = not spec.clockwise
        if isinstance(spec, Sector) and mirror:
            spec.start, spec.sweep = -spec.start, -spec.sweep
    out = to_dict(spec)
    out['sig'] = signature(new_path)
    return out


# --- géométrie --------------------------------------------------------------------------------------

def _place(x: float, y: float, angle: float):
    return geom.Affine.translation(x, y) @ geom.Affine.rotation(angle)


def _rotated(p: Path, angle: float, center) -> Path:
    if abs(angle) < 1e-12:
        return p
    return p.transformed(geom.Affine.rotation(angle, center))


def _concave_rect(cx, cy, w, h, r) -> Contour:
    """Rectangle aux coins creusés d'arcs concaves de rayon r (centrés sur
    les coins), parcouru dans le sens trigonométrique."""
    x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    segs = []
    for (px, py), a in (((x0, y0), 90.0), ((x1, y0), 180.0), ((x1, y1), 270.0), ((x0, y1), 0.0)):
        arc = geom.arc_conics((px, py), r, r, a, -90.0)
        if segs:
            segs.append(geom.Line(segs[-1].end, arc[0].start))
        segs += arc
    segs.append(geom.Line(segs[-1].end, segs[0].start))
    return Contour(segs, True)


def chord_arc(p0, p1, sagitta: float) -> Contour | None:
    """Arc de cercle de p0 à p1 dont le milieu est à `sagitta` de la corde
    (positif : à gauche de p0 → p1)."""
    chord = geom.dist(p0, p1)
    if chord < 1e-9 or abs(sagitta) < 1e-9:
        return None
    h = abs(sagitta)
    r = (chord * chord / 4 + h * h) / (2 * h)
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    ux, uy = (p1[0] - p0[0]) / chord, (p1[1] - p0[1]) / chord
    side = 1.0 if sagitta > 0 else -1.0
    d = r - h                                           # du centre au milieu de la corde, côté opposé à l'arc
    c = (mx - side * -uy * d, my - side * ux * d)
    a0 = math.degrees(math.atan2(p0[1] - c[1], p0[0] - c[0]))
    a1 = math.degrees(math.atan2(p1[1] - c[1], p1[0] - c[0]))
    sweep = (a1 - a0) % 360.0
    if side > 0:                                        # arc à gauche : sens horaire de p0 à p1
        sweep = sweep - 360.0
    segs = geom.arc_conics(c, r, r, a0, sweep)
    return Contour(segs, False)


def _log_spiral(center, r_out: float, r_in: float, turns: float, end_deg: float, ccw: bool,
                tol: float = 1e-4) -> Contour:
    """Spirale logarithmique de r_in (au centre) à r_out (à l'extérieur, dans
    la direction end_deg) en `turns` tours ; Bézier raccordées à `tol` près."""
    span = 2 * math.pi * turns
    k = math.log(r_out / r_in) / span
    s = 1.0 if ccw else -1.0
    a_end = math.radians(end_deg)
    cx, cy = center

    def pt(th):
        r, a = r_in * math.exp(k * th), a_end - s * (span - th)
        return (cx + r * math.cos(a), cy + r * math.sin(a))

    def d(th):
        r, a = r_in * math.exp(k * th), a_end - s * (span - th)
        return (k * r * math.cos(a) - s * r * math.sin(a), k * r * math.sin(a) + s * r * math.cos(a))

    segs = []
    n = max(8, math.ceil(turns * 8))
    stack = [(span * (i + 1) / n, span * i / n) for i in reversed(range(n))]
    while stack:
        t1, t0 = stack.pop()
        h = t1 - t0
        p0, p3, d0, d1 = pt(t0), pt(t1), d(t0), d(t1)
        c = Cubic(p0, (p0[0] + d0[0] * h / 3, p0[1] + d0[1] * h / 3), (p3[0] - d1[0] * h / 3, p3[1] - d1[1] * h / 3), p3)
        err = max(geom.dist(c.point(u), pt(t0 + u * h)) for u in (0.25, 0.5, 0.75))
        if err > tol and h > 1e-6:
            m = (t0 + t1) / 2
            stack.append((t1, m))
            stack.append((m, t0))
            continue
        segs.append(c)
    return Contour(segs, False)
