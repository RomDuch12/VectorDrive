"""Duplications : linéaire (pas X / Y), circulaire (autour d'un centre) et
en grille (lignes × colonnes)."""
from __future__ import annotations

import math

from .document import Item
from .geom import Affine


def _copy(it: Item, m: Affine) -> Item:
    c = it.clone()
    return c.transformed(m)


def linear(items: list[Item], count: int, dx: float, dy: float) -> list[Item]:
    """`count` copies supplémentaires, la k-ième décalée de k·(dx, dy)."""
    return [_copy(it, Affine.translation(k * dx, k * dy))
            for k in range(1, count + 1) for it in items]


def grid(items: list[Item], cols: int, rows: int, dx: float, dy: float, ox: float = 0.0, oy: float = 0.0) -> list[Item]:
    """Matrice cols × rows (l'original occupe la case (0, 0)). `ox` décale chaque rangée en X par rapport à la précédente,
    `oy` chaque colonne en Y."""
    return [_copy(it, Affine.translation(i * dx + j * ox, j * dy + i * oy))
            for j in range(rows) for i in range(cols) if (i, j) != (0, 0) for it in items]


def circular(items: list[Item], count: int, center: tuple[float, float], angle: float = 360.0,
             *, rotate: bool = True) -> list[Item]:
    """`count` exemplaires au total (original compris) répartis sur `angle`
    degrés autour de `center`. Sur 360° le pas est 360/count ; sur un arc
    ouvert, les extrémités sont occupées (pas = angle/(count-1)).
    `rotate=False` : les copies sont translatées sans tourner."""
    if count < 2:
        return []
    full = abs(abs(angle) - 360.0) < 1e-9
    step = angle / count if full else angle / (count - 1)
    cx, cy = center
    out = []
    for k in range(1, count):
        a = step * k
        rot = Affine.rotation(a, (cx, cy))
        for it in items:
            if rotate:
                m = rot
            else:
                bb = it.bbox()
                px, py = ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2) if bb else (cx, cy)
                qx, qy = rot.apply((px, py))
                m = Affine.translation(qx - px, qy - py)
            out.append(_copy(it, m))
    return out


def polar_step(radius: float, count: int) -> float:
    """Distance entre deux exemplaires voisins sur un cercle complet."""
    return 2 * radius * math.sin(math.pi / count) if count > 1 else 0.0


#: copies au plus le long d'une courbe (écart trop petit pour sa longueur : refus)
ALONG_MAX = 10000


def _spread(total: float, closed: bool, count: int, spacing: float) -> tuple:
    """(nombre d'exemplaires, pas) sur une courbe de cette longueur. ValueError si l'écart demande trop de copies."""
    if spacing > 0:
        n = (total - 1e-9) / spacing if closed else total / spacing + 1e-9
        if n >= ALONG_MAX:
            raise ValueError(f'écart trop petit : plus de {ALONG_MAX} copies')
        return int(n) + 1, spacing
    if count < 1:
        return 0, 0.0
    return count, total / count if closed else (total / (count - 1) if count > 1 else 0.0)


def following(items: list[Item], contour, count: int, *, rotate: bool = True, spacing: float = 0.0,
              origin: tuple | None = None) -> list[Item]:
    """Selon une courbe (TypeEdit) : les objets gardent leur écart à la courbe et la suivent ; `origin` est le point qui
    va sur la courbe (un marqueur), son départ par défaut. Si ce point est déjà au départ, le premier exemplaire est l'original : il n'est pas recopié."""
    from .geom import dist as geom_dist, walker
    if not items:
        return []
    total, at = walker(contour)
    if total <= 0:
        return []
    count, step = _spread(total, contour.closed, count, spacing)
    p0, a0 = at(0.0)
    ox, oy = origin if origin is not None else p0
    out = []
    for k in range(0 if geom_dist((ox, oy), p0) > 1e-9 else 1, count):
        s = k * step
        (px, py), ang = at(s % total if contour.closed else min(s, total))
        turn = Affine.rotation(math.degrees(ang - a0)) if rotate else Affine.translation(0.0, 0.0)
        m = Affine.translation(px, py) @ turn @ Affine.translation(-ox, -oy)
        out.extend(_copy(it, m) for it in items)
    return out


def morph_along(a: Item, b: Item, contour, count: int, *, rotate: bool = True) -> list[Item]:
    """Par déformation (TypeEdit) : `count` exemplaires le long de la courbe, de la forme de `a` à celle de `b`. Là où un
    exemplaire retombe exactement sur l'objet de départ ou de fin, il n'est pas créé : usiné deux fois, il marquerait."""
    from .geom import walker
    from .morph import interpolate
    total, at = walker(contour)
    if total <= 0 or count < 2:
        return []
    step = total / count if contour.closed else total / (count - 1)
    out = []
    for k in range(count):
        path = interpolate(a.path, b.path, k / (count - 1))
        x0, y0, x1, y1 = path.bbox()
        (px, py), ang = at(k * step if contour.closed else min(k * step, total))
        m = Affine.translation(px, py)
        if rotate:
            m = m @ Affine.rotation(math.degrees(ang))
        path = path.transformed(m @ Affine.translation(-(x0 + x1) / 2, -(y0 + y1) / 2))
        box = path.bbox()
        if any(all(abs(u - v) < 1e-6 for u, v in zip(box, it.path.bbox())) for it in (a, b)):
            continue
        c = a.clone()
        c.path = path
        out.append(c)
    return out


def along(items: list[Item], contour, count: int, *, rotate: bool = True,
          start: float = 0.0, spacing: float = 0.0) -> list[Item]:
    """`count` exemplaires posés à intervalles réguliers le long de
    `contour` (abscisse curviligne) : courbe fermée → pas = longueur/count,
    ouverte → extrémités occupées. `spacing` > 0 (d'après ARRAYPATH de
    CADCraft) : un exemplaire tous les `spacing` mm depuis le départ, autant
    que la courbe en porte (`count` ignoré) ; ValueError au-delà de
    ALONG_MAX. Le centre de l'encombrement de la sélection est posé sur la
    courbe ; `rotate` : orientés selon la tangente (l'objet d'origine
    correspond à une tangente horizontale)."""
    from .geom import bbox_union, walker
    if not items:
        return []
    total, at = walker(contour)
    if total <= 0:
        return []
    closed = contour.closed
    count, step = _spread(total, closed, count, spacing)
    if count < 1:
        return []
    bb = bbox_union(it.bbox() for it in items)
    rx, ry = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
    out = []
    for k in range(count):
        (px, py), ang = at((start + k * step) % total if closed else start + k * step)
        m = Affine.translation(px, py)
        if rotate:
            m = m @ Affine.rotation(math.degrees(ang))
        m = m @ Affine.translation(-rx, -ry)
        out.extend(_copy(it, m) for it in items)
    return out



def _size(it) -> float:
    bb = it.bbox()
    return max(bb[2] - bb[0], bb[3] - bb[1]) if bb else 0.0


def scaled_along(start: Item, end: Item, contour, count: int, *, rotate: bool = True,
                 equidistant: bool = False) -> list[Item]:
    """Duplication homothétique sur une courbe (TypeEdit) : `count` copies
    de `start`, de sa taille à celle de `end` (même forme, autre taille),
    la première centrée au départ de la courbe (attention à son sens), la
    dernière à son arrivée (courbe fermée : à intervalles réguliers).
    `equidistant` : c'est l'écart entre deux copies qui est constant, pas
    la distance entre leurs centres (trop de copies : les dernières se
    chevauchent). `rotate` : orientées selon la tangente."""
    from .geom import walker
    a, b = _size(start), _size(end)
    if count < 1 or a <= 0:
        return []
    total, at = walker(contour)
    if total <= 0:
        return []
    k_end = b / a if b > 0 else 1.0
    n = count
    ks = [1.0 + (k_end - 1.0) * (i / (n - 1) if n > 1 else 0.0) for i in range(n)]
    bb = start.bbox()
    cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
    closed = contour.closed
    if equidistant and n > 1:
        w = [(bb[2] - bb[0]) * k for k in ks]                # étendue le long de la tangente
        pairs = [(w[i] + w[i + 1]) / 2 for i in range(n - 1)] + ([(w[-1] + w[0]) / 2] if closed else [])
        gap = (total - sum(pairs)) / len(pairs)
        pos = [0.0]
        for d in pairs[:n - 1]:
            pos.append(pos[-1] + d + gap)
    else:
        step = total / n if closed else (total / (n - 1) if n > 1 else 0.0)
        pos = [i * step for i in range(n)]
    out = []
    for s, k in zip(pos, ks):
        (px, py), ang = at(min(max(s, 0.0), total) if not closed else s % total)
        m = Affine.translation(px, py)
        if rotate:
            m = m @ Affine.rotation(math.degrees(ang))
        m = m @ Affine.scaling(k, k) @ Affine.translation(-cx, -cy)
        out.append(_copy(start, m))
    return out


def fill_layout(item_w: float, item_h: float, box, gap_x: float, gap_y: float, margin: float,
                allow_rotate: bool = False) -> dict:
    """Disposition en grille du plus grand nombre d'exemplaires dans `box`
    (x0, y0, x1, y1) : {'cols', 'rows', 'rotated', 'origin', 'w', 'h'} ;
    le bloc est centré dans la zone utile (box moins la marge)."""
    W = box[2] - box[0] - 2 * margin
    H = box[3] - box[1] - 2 * margin

    def count(w, h):
        if w <= 0 or h <= 0 or W < w or H < h:
            return 0, 0
        return int((W + gap_x + 1e-9) // (w + gap_x)), int((H + gap_y + 1e-9) // (h + gap_y))
    c, r = count(item_w, item_h)
    best = {'cols': c, 'rows': r, 'rotated': False, 'w': item_w, 'h': item_h}
    if allow_rotate:
        c2, r2 = count(item_h, item_w)
        if c2 * r2 > c * r:
            best = {'cols': c2, 'rows': r2, 'rotated': True, 'w': item_h, 'h': item_w}
    bw = best['cols'] * best['w'] + max(0, best['cols'] - 1) * gap_x
    bh = best['rows'] * best['h'] + max(0, best['rows'] - 1) * gap_y
    best['origin'] = (box[0] + margin + (W - bw) / 2, box[1] + margin + (H - bh) / 2)
    return best


def fill(items: list[Item], box, gap_x: float = 2.0, gap_y: float = 2.0, margin: float = 3.0,
         allow_rotate: bool = False) -> tuple[list[Item], dict]:
    """Exemplaires de `items` (pris comme un bloc) remplissant `box`."""
    from .geom import bbox_union
    bb = bbox_union(it.bbox() for it in items)
    if not bb:
        return [], {}
    lay = fill_layout(bb[2] - bb[0], bb[3] - bb[1], box, gap_x, gap_y, margin, allow_rotate)
    base = Affine.translation(-bb[0], -bb[1])
    if lay['rotated']:
        # quart de tour, puis retour dans le premier quadrant
        base = Affine.translation(bb[3] - bb[1], 0) @ Affine.rotation(90) @ base
    ox, oy = lay['origin']
    out = []
    for j in range(lay['rows']):
        for i in range(lay['cols']):
            m = Affine.translation(ox + i * (lay['w'] + gap_x), oy + j * (lay['h'] + gap_y)) @ base
            out.extend(_copy(it, m) for it in items)
    return out, lay
