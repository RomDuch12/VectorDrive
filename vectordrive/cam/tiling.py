"""Gravure laser plus grande que le champ, en morceaux (TauDrive : morceaux).

La tête d'un laser à scanner ne se déplace pas : le faisceau balaie un
champ fixe (110 × 110 mm sur la TAU, lentille f-thêta de 160 mm), centré
sur l'origine du travail. Un dessin plus grand se grave en morceaux : on
grave ce qui tient, l'opérateur pousse la pièce d'une cote connue, on grave
la suite.

- **Découpe** : une grille de morceaux égaux, chacun au plus de la taille
  utile du champ (le champ moins une marge de chaque côté, le bord du champ
  étant le moins fidèle) ; des morceaux égaux plutôt que des pleins suivis
  d'une lamelle. Rangées du haut vers le bas, en serpentin.
- **Trajectoires** : chaque segment coupé au bord du morceau (Liang–Barsky)
  puis recentré sur le centre du morceau ; un trait posé exactement sur une
  frontière n'appartient qu'à un morceau (celui de gauche ou du bas) : rien
  n'est gravé deux fois.
- **Consignes** : pour chaque morceau, le déplacement de la pièce depuis le
  précédent (l'opposé de celui du morceau), en clair ; traits de raccord au
  milieu des frontières, au choix, pour contrôler le recalage.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

#: marge de sécurité par défaut au bord du champ (mm)
MARGIN = 2.0
#: tolérance sur une frontière (mm)
EPS = 1e-6


@dataclass
class Tile:
    """Un morceau, dans les coordonnées du dessin."""
    rank: int                       # ordre de gravure, à partir de 1
    col: int                        # colonne, à partir de 1, de gauche à droite
    row: int                        # rangée, à partir de 1, du haut vers le bas
    x1: float
    y1: float
    x2: float
    y2: float
    dx: float = 0.0                 # déplacement de la PIÈCE depuis le morceau précédent
    dy: float = 0.0
    right: bool = False             # voisin à droite (la frontière lui appartient)
    top: bool = False               # voisin en haut (idem)
    left: bool = False
    bottom: bool = False

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1


def useful(field_w: float, field_h: float, margin: float) -> tuple[float, float]:
    """Taille utile du champ, marge retirée de chaque côté."""
    m = max(0.0, float(margin))
    return max(1.0, field_w - 2 * m), max(1.0, field_h - 2 * m)


def needed(bounds, field_w: float, field_h: float, margin: float = MARGIN) -> bool:
    """Vrai si le dessin (x0, y0, x1, y1) est plus grand que le champ utile."""
    if bounds is None:
        return False
    uw, uh = useful(field_w, field_h, margin)
    return bounds[2] - bounds[0] > uw + EPS or bounds[3] - bounds[1] > uh + EPS


def outside(bounds, field_w: float, field_h: float) -> bool:
    """Vrai si le dessin, tel quel, sort du champ centré sur l'origine."""
    if bounds is None:
        return False
    return (bounds[0] < -field_w / 2 - EPS or bounds[2] > field_w / 2 + EPS or
            bounds[1] < -field_h / 2 - EPS or bounds[3] > field_h / 2 + EPS)


def plan(bounds, field_w: float, field_h: float, margin: float = MARGIN) -> list[Tile]:
    """Morceaux qui couvrent le dessin, dans l'ordre de gravure ; un seul,
    le champ centré sur l'origine, si tout tient."""
    if bounds is None:
        return []
    x0, y0, x1, y1 = bounds
    w, h = x1 - x0, y1 - y0
    uw, uh = useful(field_w, field_h, margin)
    nx = max(1, math.ceil((w - EPS) / uw))
    ny = max(1, math.ceil((h - EPS) / uh))
    if nx == 1 and ny == 1:
        return [Tile(1, 1, 1, -field_w / 2, -field_h / 2, field_w / 2, field_h / 2)]
    tw, th = w / nx, h / ny
    tiles = []
    for j in range(ny):
        top = y1 - j * th
        for i in (range(nx) if j % 2 == 0 else range(nx - 1, -1, -1)):
            tiles.append(Tile(len(tiles) + 1, i + 1, j + 1, x0 + i * tw, top - th, x0 + (i + 1) * tw, top,
                              right=i < nx - 1, top=j > 0, left=i > 0, bottom=j < ny - 1))
    for a, b in zip(tiles, tiles[1:]):                 # la pièce va à l'opposé du morceau
        b.dx = _clean(a.cx - b.cx)
        b.dy = _clean(a.cy - b.cy)
    return tiles


def _clean(v: float) -> float:
    return 0.0 if abs(v) < 1e-9 else v


def _clip(p, q, t: Tile):
    """Segment [p, q] coupé au rectangle du morceau (bords compris), ou None."""
    (px, py), (qx, qy) = p[:2], q[:2]
    dx, dy = qx - px, qy - py
    t0, t1 = 0.0, 1.0
    for pk, qk in ((-dx, px - t.x1), (dx, t.x2 - px), (-dy, py - t.y1), (dy, t.y2 - py)):
        if pk == 0.0:
            if qk < 0.0:
                return None
            continue
        r = qk / pk
        if pk < 0.0:
            if r > t1:
                return None
            t0 = max(t0, r)
        else:
            if r < t0:
                return None
            t1 = min(t1, r)
    if t0 > t1:
        return None
    return (px + t0 * dx, py + t0 * dy), (px + t1 * dx, py + t1 * dy)


def _on_shared_edge(a, b, t: Tile) -> bool:
    """Segment posé sur la frontière de droite ou du haut (celle du voisin)."""
    if t.right and abs(a[0] - t.x2) < EPS and abs(b[0] - t.x2) < EPS:
        return True
    return t.top and abs(a[1] - t.y2) < EPS and abs(b[1] - t.y2) < EPS


def clip_polyline(poly: list, t: Tile) -> list[list]:
    """Tronçons d'une polyligne qui tombent dans le morceau (coordonnées du
    dessin) ; un tronçon continue tant que les segments coupés se suivent."""
    out, cur = [], []
    for a, b in zip(poly, poly[1:]):
        seg = _clip(a, b, t)
        if seg is None or math.dist(*seg) < EPS or _on_shared_edge(seg[0], seg[1], t):
            if seg is None or math.dist(*seg) >= EPS:
                if len(cur) >= 2:
                    out.append(cur)
                cur = []
            continue
        ca, cb = seg
        if cur and math.dist(cur[-1], ca) < EPS:
            cur.append(cb)
        else:
            if len(cur) >= 2:
                out.append(cur)
            cur = [ca, cb]
    if len(cur) >= 2:
        out.append(cur)
    return out


def cut(polys: list, t: Tile) -> list[list]:
    """Polylignes réduites au morceau, recentrées sur son centre."""
    return [[(x - t.cx, y - t.cy) for x, y in piece] for poly in polys for piece in clip_polyline(poly, t)]


def join_marks(t: Tile, length: float = 2.0) -> list[list]:
    """Traits de raccord au milieu de chaque frontière partagée, dans le
    morceau, recentrés : chaque voisin grave le sien de l'autre côté, les
    deux doivent se prolonger en un trait continu."""
    out = []
    if t.right:
        out.append([(t.x2 - length - t.cx, 0.0), (t.x2 - t.cx, 0.0)])
    if t.left:
        out.append([(t.x1 - t.cx, 0.0), (t.x1 + length - t.cx, 0.0)])
    if t.top:
        out.append([(0.0, t.y2 - length - t.cy), (0.0, t.y2 - t.cy)])
    if t.bottom:
        out.append([(0.0, t.y1 - t.cy), (0.0, t.y1 + length - t.cy)])
    return out


def _mm(v: float) -> str:
    return f'{v:+.1f}'.replace('.', ',')


def _move(dx: float, dy: float) -> str:
    parts = []
    if abs(dx) >= 0.05:
        parts.append(f'{abs(dx):.1f} mm vers X{"+" if dx > 0 else "-"} ({"droite" if dx > 0 else "gauche"})')
    if abs(dy) >= 0.05:
        parts.append(f'{abs(dy):.1f} mm vers Y{"+" if dy > 0 else "-"} ({"haut" if dy > 0 else "bas"})')
    return ' et '.join(parts).replace('.', ',') if parts else 'aucun'


def instructions(tiles: list[Tile], bounds, stem: str, field: tuple[float, float], margin: float,
                 marks: bool = False, when: str = '') -> str:
    """Consignes pour l'opérateur (ASCII), écrites à côté des travaux."""
    n = len(tiles)
    nx, ny = max(t.col for t in tiles), max(t.row for t in tiles)

    def v(x: float) -> str:
        return f'{x:.1f}'.replace('.', ',')
    lines = [f'CONSIGNES OPERATEUR - GRAVURE EN {n} MORCEAU{"X" if n > 1 else ""}',
             f'Travail : {stem}' + (f'    Ecrit le {when} par VectorDrive' if when else ''),
             f'Dessin : {v(bounds[2] - bounds[0])} x {v(bounds[3] - bounds[1])} mm - champ de marquage '
             f'{field[0]:g} x {field[1]:g} mm, marge de securite {v(margin)} mm de chaque cote',
             f'Decoupe : {nx} colonne{"s" if nx > 1 else ""} x {ny} rangee{"s" if ny > 1 else ""} - morceaux de '
             f'{v(tiles[0].width)} x {v(tiles[0].height)} mm', '',
             'Repere : X+ vers la droite du plan de travail, Y+ vers le haut, tels qu\'affiches a l\'ecran.',
             'Les deplacements sont ceux de la PIECE sur la table, en millimetres, depuis le morceau precedent.',
             'Entre deux morceaux : meme origine machine, meme Z, meme position du champ. Seule la piece bouge.']
    if marks:
        lines.append('Chaque morceau grave un trait de raccord au milieu de chaque frontiere : apres le dernier '
                     'morceau, ces traits doivent se prolonger exactement. Un decalage se lit et se mesure.')
    lines.append('')
    for t in tiles:
        name = f'{stem}_M{t.rank:02d}'
        lines.append(f'Morceau {t.rank}/{n}  (rangee {t.row}, colonne {t.col}) - travail {name}.CLJOB')
        if t.rank == 1:
            lines.append(f'  Placer la piece de sorte que le point X {_mm(t.cx)} / Y {_mm(t.cy)} du dessin soit au '
                         'centre du champ.')
        else:
            lines.append(f'  Deplacer la piece de {_move(t.dx, t.dy)}.')
        lines.append(f'  Couvre le dessin de X {_mm(t.x1)} a {_mm(t.x2)} et de Y {_mm(t.y1)} a {_mm(t.y2)}.')
        lines.append(f'  Lancer {name}.CLJOB, attendre la fin.')
        lines.append('')
    if n > 1:
        lines.append(f'Controle : au dernier morceau, la piece a ete deplacee en tout de '
                     f'X {_mm(sum(t.dx for t in tiles))} / Y {_mm(sum(t.dy for t in tiles))} par rapport au premier.')
    return '\n'.join(lines) + '\n'
