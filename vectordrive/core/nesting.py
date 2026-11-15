"""Imbrication : ranger des objets sur la plaque, au plus serré, par leurs
rectangles englobants (algorithme de la « ligne d'horizon », coin haut
gauche d'abord, quart de tour permis). Ce qui ne tient pas sur une plaque
passe sur des plaques suivantes, dessinées à droite : on voit combien il
en faut.

Exemplaires 0 (TypeEdit : copie imbriquée) : la plaque est remplie — les
objets choisis, tour à tour, autant de fois qu'ils tiennent sur une plaque.

L'optimiseur (`tries`, `both_ways`) essaie plusieurs rangements, dans plusieurs ordres et les deux directions, et
garde le meilleur : ce qui ne tient nulle part, puis le nombre de plaques, puis la place prise sur la dernière.

Unités : mm. Le haut de la plaque est en y max (repère TypeEdit).
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field, replace

from .document import Item, Plate
from .geom import Affine
from . import progress

#: écart entre deux plaques suivantes (mm)
PLATE_GAP = 10.0
#: coin de la plaque d'où part le rangement
CORNERS = ('haut_gauche', 'haut_droit', 'bas_gauche', 'bas_droit')
#: forme : case la plus fine (mm)
MIN_PRECISION = 0.05


@dataclass
class NestSpec:
    margin: float = 3.0
    gap: float = 2.0
    allow_rotate: bool = True
    copies: int = 1
    shape: bool = False                                  # selon la vraie forme (`nesting_shape`), sinon les rectangles
    angle_step: float = 90.0                             # forme : pas de rotation (°)
    angles: str = ''                                     # forme : angles permis (« 0;90;180 ») ; vide : d'après le pas
    in_holes: bool = False                               # forme : ranger aussi dans les trous des autres
    allow_mirror: bool = False                           # forme : retourner aussi les objets
    precision: float = 0.5                               # forme : taille des cases (mm)
    counts: list | None = None                           # exemplaires de chaque objet (remplace `copies`)
    corner: str = 'haut_gauche'                          # coin d'où part le rangement (`CORNERS`)
    vertical: bool = False                               # colonne par colonne, sinon rangée par rangée
    tighten: bool = True                                 # forme : reprendre le jeu de la grille à la fin
    region: object = None                                # Path : ranger dans cette forme, pas sur la plaque (selon la forme)
    tries: int = 1                                       # optimiseur : rangements essayés
    both_ways: bool = False                              # optimiseur : les deux directions
    max_seconds: float = 30.0                            # optimiseur : plus d'essai après cette durée
    min_gain: float = 0.0                                # optimiseur : arrêt à ce gain de remplissage sur le 1er (%) ; 0 : tous
    order: int = 0                                       # ordre des objets : 0 les plus grands d'abord, voir `_ordered`


@dataclass
class NestResult:
    placed: list[tuple[Item, Affine]] = field(default_factory=list)
    plates: int = 0
    unplaced: list[Item] = field(default_factory=list)
    rotated: int = 0
    mirrored: int = 0                                    # forme : objets retournés
    usage: float = 0.0                                   # forme : part des plaques couverte
    sheets: list[int] = field(default_factory=list)      # n° de plaque de chaque objet de `placed`
    best: dict = field(default_factory=dict)             # optimiseur : essais faits, direction retenue, remplissage

    def items(self) -> list[Item]:
        return [it.transformed(m) for it, m in self.placed]


class Skyline:
    """Ligne d'horizon d'une bande de largeur W et de hauteur H, remplie
    depuis le haut : segments (x, y, w), y = hauteur déjà occupée."""

    def __init__(self, W: float, H: float):
        self.W, self.H = W, H
        self.segs = [[0.0, 0.0, W]]

    def find(self, w: float, h: float):
        """Meilleure place (y + h, x, i, y) ou None."""
        best = None
        for i, (x, _y, _w) in enumerate(self.segs):
            if x + w > self.W + 1e-9:
                break
            y, rem, j = 0.0, w, i
            while rem > 1e-9 and j < len(self.segs):
                y = max(y, self.segs[j][1])
                rem -= self.segs[j][2]
                j += 1
            if rem > 1e-9 or y + h > self.H + 1e-9:
                continue
            cand = (y + h, x, i, y)
            if best is None or cand[:2] < best[:2]:
                best = cand
        return best

    def place(self, i: int, y: float, w: float, h: float) -> None:
        x = self.segs[i][0]
        new = [x, y + h, w]
        out = self.segs[:i]
        end = x + w
        for s in self.segs[i:]:
            sx, sy, sw = s
            if sx + sw <= end + 1e-9:
                continue                                # recouvert
            if sx < end:
                s = [end, sy, sx + sw - end]            # rogné à gauche
            out.append(s)
        out.insert(i, new)
        merged = []
        for s in out:
            if merged and abs(merged[-1][1] - s[1]) < 1e-9:
                merged[-1][2] += s[2]
            else:
                merged.append(list(s))
        self.segs = merged


def _bb(it: Item):
    return it.bbox()


def _ordered(jobs: list, order: int, size) -> list:
    """Les objets dans l'ordre de cet essai : 0 tel quel (les plus grands d'abord), 1 par aire, 2 par hauteur,
    3 par largeur, ensuite à peu près du plus grand au plus petit, au hasard (le même à chaque fois)."""
    if order <= 0:
        return jobs
    if order == 1:
        return sorted(jobs, key=lambda j: -size(j)[0] * size(j)[1])
    if order == 2:
        return sorted(jobs, key=lambda j: -size(j)[1])
    if order == 3:
        return sorted(jobs, key=lambda j: -size(j)[0])
    rng = random.Random(order)
    spread = max(1.0, len(jobs) / 3.0)
    ranks = [i + rng.uniform(0.0, spread) for i in range(len(jobs))]
    return [j for _r, j in sorted(zip(ranks, jobs), key=lambda x: x[0])]


def _last_sheet_area(res: NestResult) -> float:
    """La place que prennent les objets sur la dernière plaque : le rectangle qui les contient."""
    if not res.sheets:
        return 0.0
    last = max(res.sheets)
    x0 = y0 = float('inf')
    x1 = y1 = float('-inf')
    for (it, m), k in zip(res.placed, res.sheets):
        b = it.bbox() if k == last else None
        if not b:
            continue
        for p in ((b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])):
            x, y = m.apply(p)
            x0, y0, x1, y1 = min(x0, x), min(y0, y), max(x1, x), max(y1, y)
    return (x1 - x0) * (y1 - y0) if x1 >= x0 else 0.0


def _score(res: NestResult) -> tuple:
    """Plus petit : meilleur."""
    return (len(res.unplaced), -len(res.placed), res.plates, _last_sheet_area(res))


def _filled(res: NestResult, plate: Plate) -> float:
    """La part des plaques prise par les rectangles des objets."""
    if not res.plates or plate.width <= 0 or plate.height <= 0:
        return 0.0
    total = 0.0
    for it, _m in res.placed:
        b = it.bbox()
        if b:
            total += (b[2] - b[0]) * (b[3] - b[1])
    return total / (res.plates * plate.width * plate.height)


def _best_of(items: list[Item], plate: Plate, spec: NestSpec) -> NestResult:
    ways = (False, True) if spec.both_ways else (bool(spec.vertical),)
    if spec.both_ways and spec.vertical:
        ways = (True, False)
    wanted = max(int(spec.tries), len(ways))
    start = time.monotonic()
    best, best_score, best_fill, base = None, None, 0.0, 0.0
    done = 0
    for n in range(wanted):
        if done >= len(ways) and time.monotonic() - start >= float(spec.max_seconds):
            break
        trial = replace(spec, tries=1, both_ways=False, vertical=ways[n % len(ways)], order=n // len(ways))
        res = _nest_once(items, plate, trial)
        res.best = {'vertical': trial.vertical, 'order': trial.order}
        done += 1
        score = _score(res)
        fill = _filled(res, plate)
        if n == 0:
            base = fill
        if best is None or score < best_score:
            best, best_score, best_fill = res, score, fill
        if done >= len(ways) and spec.min_gain > 0 and best_fill >= base * (1.0 + float(spec.min_gain) / 100.0):
            break
    best.best.update(tries=done, filled=best_fill, first_filled=base)
    return best


def nest(items: list[Item], plate: Plate, spec: NestSpec) -> NestResult:
    if spec.region is None and (int(spec.tries) > 1 or spec.both_ways):
        return _best_of(items, plate, spec)
    return _nest_once(items, plate, spec)


def parse_angles(text: str) -> list[float]:
    """« 0;90;180 » : les angles, sans doublon, ramenés entre 0 et 360. Ce qui n'est pas un nombre est ignoré."""
    out: list[float] = []
    for part in str(text or '').replace(' ', ';').split(';'):
        try:
            a = float(part.replace(',', '.')) % 360.0
        except ValueError:
            continue
        if a == a and a not in out:                      # NaN écarté
            out.append(a)
    return out


def _islands(path) -> list:
    """Les contours fermés d'un tracé, dans leur ordre, chacun avec ses trous ; une île dans un trou compte à part."""
    from shapely.geometry import Point, Polygon
    from .geom import Path
    rings = []
    for c in path.contours:
        pts = c.flatten(0.05) if c.closed and c.segments else []
        if len(pts) < 3:
            continue
        poly = Polygon(pts).buffer(0)
        if poly.area > 0:
            rings.append((c, poly, Point(pts[0])))
    around = [[j for j, (_c, poly, _p) in enumerate(rings) if j != i and poly.area > rings[i][1].area and poly.contains(pt)]
              for i, (_c0, _p0, pt) in enumerate(rings)]
    zones = {i: [c] for i, (c, _p, _q) in enumerate(rings) if len(around[i]) % 2 == 0}
    for i, (c, _p, _q) in enumerate(rings):
        if i not in zones:
            zones[min((j for j in around[i] if j in zones), key=lambda j: rings[j][1].area)].append(c)
    return [Path(zones[i]) for i in sorted(zones)]


def contours_of(target) -> list:
    """Les zones où ranger, dans l'ordre : chaque objet d'un groupe, chaque contour d'une combinaison."""
    from .document import Group
    from .hatch import closed_path
    if isinstance(target, Group):
        return [z for child in target.children for z in contours_of(child)]
    return _islands(closed_path([target]))


def nest_into(items: list[Item], zones: list, spec: NestSpec) -> NestResult:
    """Chaque objet une fois, dans la première zone ; ce qui n'y tient pas passe à la suivante, et ainsi de suite."""
    from . import pathops
    res = NestResult()
    left = list(items)
    matter = room = 0.0
    for k, zone in enumerate(zones):
        if not left:
            break
        got = _nest_once(left, None, replace(spec, region=zone, shape=True, copies=1, counts=None))
        if got.placed:
            area = pathops.area(pathops.normalize(zone))
            room += area
            matter += got.usage * area
            res.placed += got.placed
            res.sheets += [k] * len(got.placed)
            res.rotated += got.rotated
            res.mirrored += got.mirrored
            res.plates += 1
        left = got.unplaced
    res.unplaced = left
    res.usage = matter / room if room > 0 else 0.0
    return res


def _nest_once(items: list[Item], plate: Plate, spec: NestSpec) -> NestResult:
    if spec.shape or spec.region is not None:
        from .nesting_shape import nest_shapes
        return nest_shapes(items, plate, spec)
    res = NestResult()
    W = plate.width - 2 * spec.margin + spec.gap
    H = plate.height - 2 * spec.margin + spec.gap
    if W <= 0 or H <= 0:
        res.unplaced = list(items)
        return res
    if spec.counts is None and int(spec.copies) <= 0:
        return _fill(items, plate, spec, W, H, res)
    SW, SH = (H, W) if spec.vertical else (W, H)
    jobs = []
    for n, it in enumerate(items):
        bb = _bb(it)
        if not bb:
            continue
        for _ in range(count_of(spec, n)):
            jobs.append((it, bb))
    jobs.sort(key=lambda j: (-max(j[1][2] - j[1][0], j[1][3] - j[1][1]),
                             -(j[1][2] - j[1][0]) * (j[1][3] - j[1][1])))
    jobs = _ordered(jobs, int(spec.order), lambda j: (j[1][2] - j[1][0], j[1][3] - j[1][1]))
    sheets: list[Skyline] = []
    for ji, (it, bb) in enumerate(jobs):
        progress.step(ji, len(jobs), 'Imbrication : objet {0} sur {1}')
        w0, h0 = bb[2] - bb[0], bb[3] - bb[1]
        options = [(w0, h0, False)]
        if spec.allow_rotate and abs(w0 - h0) > 1e-9:
            options.append((h0, w0, True))
        options = [o for o in options if o[0] + spec.gap <= W + 1e-9 and o[1] + spec.gap <= H + 1e-9]
        if not options:
            res.unplaced.append(it)
            continue
        # sens d'origine d'abord (textes lisibles, objets TypeEdit gardés) ;
        # quart de tour seulement s'il faut, sur la première plaque où ça tient
        choice = None
        for k, sh in enumerate(sheets + [Skyline(SW, SH)]):
            for w, h, rot in options:
                f = sh.find(*_along(spec, w, h))
                if f is not None:
                    choice = (k, f, w, h, rot)
                    break
            if choice is not None:
                break
        k, (_top, x, i, y), w, h, rot = choice
        if k == len(sheets):
            sheets.append(Skyline(SW, SH))
        sheets[k].place(i, y, *_along(spec, w, h))
        res.placed.append((it, _matrix(plate, spec, k, x, y, bb, w0, h0, rot, res)))
        res.sheets.append(k)
    res.plates = len(sheets)
    return res


def count_of(spec: NestSpec, n: int) -> int:
    """Exemplaires de l'objet n° n."""
    if spec.counts is not None:
        return max(0, int(spec.counts[n])) if n < len(spec.counts) else 0
    return max(1, int(spec.copies))


def _along(spec: NestSpec, w: float, h: float) -> tuple[float, float]:
    """Une boîte dans le repère de la ligne d'horizon : axes échangés pour ranger en colonnes."""
    return (h + spec.gap, w + spec.gap) if spec.vertical else (w + spec.gap, h + spec.gap)


def _matrix(plate, spec, k, x, y, bb, w0, h0, rot, res) -> Affine:
    """Placement d'un objet : quart de tour éventuel, puis son coin au point
    trouvé de la plaque k, compté depuis le coin de départ."""
    if spec.vertical:
        x, y = y, x
    m = Affine()
    if rot:
        cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
        m = Affine.rotation(90, (cx, cy))
        bb = (cx - h0 / 2, cy - w0 / 2, cx + h0 / 2, cy + w0 / 2)
        res.rotated += 1
    w, h = (h0, w0) if rot else (w0, h0)
    corner = spec.corner if spec.corner in CORNERS else CORNERS[0]
    ox = plate.x + k * (plate.width + PLATE_GAP) + (plate.width - spec.margin - x - w if corner.endswith('droit')
                                                    else spec.margin + x)
    top = plate.y + (spec.margin + y + h if corner.startswith('bas') else plate.height - spec.margin - y)
    return Affine.translation(ox - bb[0], top - bb[3]) @ m


#: remplissage : au plus tant de copies (garde-fou)
FILL_MAX = 5000


def _fill(items, plate, spec, W, H, res) -> NestResult:
    """Une plaque remplie : les objets tour à tour tant qu'il en tient un."""
    jobs = [(it, bb) for it in items if (bb := _bb(it))]
    sheet = Skyline(H, W) if spec.vertical else Skyline(W, H)
    more = True
    while more and len(res.placed) < FILL_MAX:
        more = False
        for it, bb in jobs:
            w0, h0 = bb[2] - bb[0], bb[3] - bb[1]
            options = [(w0, h0, False)] + ([(h0, w0, True)] if spec.allow_rotate and abs(w0 - h0) > 1e-9 else [])
            for w, h, rot in options:
                f = sheet.find(*_along(spec, w, h)) if w + spec.gap <= W + 1e-9 and \
                    h + spec.gap <= H + 1e-9 else None
                if f is not None:
                    _top, x, i, y = f
                    sheet.place(i, y, *_along(spec, w, h))
                    res.placed.append((it, _matrix(plate, spec, 0, x, y, bb, w0, h0, rot, res)))
                    res.sheets.append(0)
                    more = True
                    break
            progress.check()
    res.plates = 1 if res.placed else 0
    res.unplaced = [it for it, _bb_ in jobs if not any(p is it for p, _m in res.placed)]
    return res
