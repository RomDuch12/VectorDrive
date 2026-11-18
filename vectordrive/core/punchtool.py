"""Emporte-pièce à la souris (demande du 18/11 : « fonction emporte-pièce pour retirer à un contour un segment,
rectangle, cercle (cas d'usage sur une ligne dont on veut retirer à la souris une longueur de x mm) »).

Trois formes :

- **segment** : sur le contour le plus proche du clic, une longueur donnée est retirée, centrée sur le point cliqué
  (mesurée le long du contour : sur une droite, x mm exactement ; sur une courbe, x mm de courbe). Près d'un bout d'un
  trait ouvert, la longueur est gardée entière : elle est décalée pour rester sur le trait. Un contour fermé s'ouvre
  (son côté de fermeture compte comme les autres). La coupe est exacte : les courbes restent des courbes ;
- **rectangle** et **cercle** : tout ce que la forme couvre, posée sur le point cliqué, est retiré — les traits sont
  coupés exactement à son bord ; les surfaces pleines sont évidées par une opération booléenne (leurs courbes sont
  alors retracées).

Un reste plus court que `TINY` n'est pas gardé."""
from __future__ import annotations

import math

from . import geom
from .geom import Contour, Path
from .trim import nearest_param, piece, sub_segment

KINDS = ('segment', 'rectangle', 'cercle')
#: un reste plus court (mm) part avec le morceau retiré
TINY = 1e-3


def _whole(c: Contour) -> Contour:
    """Le contour avec sa fermeture écrite (un contour fermé dont le dernier point n'est pas le premier a un côté de
    plus, implicite)."""
    return c.close() if c.closed else c


def _lengths(c: Contour) -> list:
    return [float(s.length()) for s in c.segments]


def _arc_at(c: Contour, lens: list, g: float) -> float:
    """La longueur parcourue depuis le début du contour jusqu'au paramètre global `g`."""
    i = min(int(math.floor(g)), len(lens) - 1)
    t = min(1.0, g - i)
    if t <= 0:
        return sum(lens[:i])
    return sum(lens[:i]) + float(sub_segment(c.segments[i], 0.0, t).length())


def _param_at(c: Contour, lens: list, s: float) -> float:
    """Le paramètre global du point à la longueur `s` du début (dichotomie dans le segment)."""
    acc = 0.0
    for i, L in enumerate(lens):
        if s <= acc + L or i == len(lens) - 1:
            want = min(max(s - acc, 0.0), L)
            if L <= 1e-12:
                return float(i)
            if type(c.segments[i]).__name__ == 'Line':
                return i + want / L
            lo, hi = 0.0, 1.0
            for _ in range(40):
                mid = (lo + hi) / 2
                if float(sub_segment(c.segments[i], 0.0, mid).length()) < want:
                    lo = mid
                else:
                    hi = mid
            return i + (lo + hi) / 2
        acc += L
    return float(len(lens))


def span(c: Contour, p, length: float) -> tuple | None:
    """(g0, g1, s0, s1, total) du morceau de `length` mm centré sur le point du contour le plus proche de `p` :
    paramètres globaux et longueurs, sur le contour à la fermeture écrite (`_whole`) ; None pour un contour vide ou
    une longueur nulle. Trait ouvert : le morceau est décalé pour rester sur le trait ; un reste de moins de `TINY`
    part avec lui. s0 = 0 et s1 = total : tout le contour."""
    if not c.segments or length <= 0:
        return None
    cc = _whole(c)
    lens = _lengths(cc)
    total = sum(lens)
    if total <= 1e-12:
        return None
    g, _d = nearest_param(cc, p)
    at = _arc_at(cc, lens, g)
    if length >= total - TINY:
        return (0.0, float(len(lens)), 0.0, total, total)
    if cc.closed:
        s0, s1 = (at - length / 2) % total, (at + length / 2) % total
    else:
        s0 = min(max(at - length / 2, 0.0), total - length)
        s1 = s0 + length
        if s0 < TINY:
            s0 = 0.0
        if total - s1 < TINY:
            s1 = total
    return (_param_at(cc, lens, s0), _param_at(cc, lens, s1), s0, s1, total)


def removed_piece(c: Contour, p, length: float) -> Contour | None:
    """Le morceau qui serait retiré (pour le montrer sous la souris) ; None : rien."""
    sp = span(c, p, length)
    if sp is None:
        return None
    g0, g1, s0, s1, total = sp
    cc = _whole(c)
    if s0 == 0.0 and s1 == total:
        return Contour(list(cc.segments), False)
    return piece(cc, g0, g1)


def remove_length(c: Contour, p, length: float) -> list | None:
    """Le contour sans le morceau de `length` mm centré près de `p` : la liste des contours restants (0, 1 ou 2) ;
    None si rien n'est retiré."""
    sp = span(c, p, length)
    if sp is None:
        return None
    g0, g1, s0, s1, total = sp
    if s0 == 0.0 and s1 == total:
        return []
    cc = _whole(c)
    n = len(cc.segments)
    if cc.closed:
        rest = piece(cc, g1, g0)                         # du bout du trou à son début, par la fermeture
        return [rest] if rest.segments else []
    out = []
    if s0 > 0.0:
        a = piece(cc, 0.0, g0)
        if a.segments:
            out.append(a)
    if s1 < total:
        b = piece(cc, g1, float(n))
        if b.segments:
            out.append(b)
    return out


def nearest_contour(path: Path, p) -> tuple:
    """(rang du contour le plus proche de `p`, distance) ; (-1, inf) sans contour."""
    best = (-1, math.inf)
    for i, c in enumerate(path.contours):
        if not c.segments:
            continue
        _g, d = nearest_param(_whole(c), p)
        if d < best[1]:
            best = (i, d)
    return best


def punch_length(path: Path, p, length: float) -> Path | None:
    """Le tracé dont le contour le plus proche de `p` perd `length` mm ; None si rien ne change."""
    i, _d = nearest_contour(path, p)
    if i < 0:
        return None
    rest = remove_length(path.contours[i], p, length)
    if rest is None:
        return None
    return Path(list(path.contours[:i]) + rest + list(path.contours[i + 1:]))


def region(kind: str, at, width: float, height: float = 0.0, angle: float = 0.0) -> Path | None:
    """La forme de l'emporte-pièce posée sur `at` : 'cercle' (diamètre `width`) ou 'rectangle' (`width` × `height`,
    tourné de `angle` degrés) ; None pour une taille nulle."""
    x, y = float(at[0]), float(at[1])
    if kind == 'cercle':
        if width <= 0:
            return None
        return Path([geom.circle((x, y), width / 2)])
    if kind == 'rectangle':
        if width <= 0 or height <= 0:
            return None
        c = geom.rect(x - width / 2, y - height / 2, width, height)
        if abs(angle) > 1e-9:
            a = math.radians(angle)
            ca, sa = math.cos(a), math.sin(a)

            def turn(q):
                dx, dy = q[0] - x, q[1] - y
                return (x + dx * ca - dy * sa, y + dx * sa + dy * ca)
            c = geom.polyline([turn(s.start) for s in c.segments], closed=True)
        return Path([c])
    return None


def _boxes_apart(a: Path, b: Path) -> bool:
    ab, bb = a.bbox(), b.bbox()
    return not ab or not bb or ab[2] < bb[0] or ab[0] > bb[2] or ab[3] < bb[1] or ab[1] > bb[3]


def punch_region(path: Path, shape: Path, filled: bool) -> Path | None:
    """Le tracé moins ce que couvre la forme ; None si rien ne change (le tracé n'est alors pas réécrit). Traits :
    coupés au bord ; surfaces : évidées, seulement si la forme en couvre une partie."""
    from . import pathops, punch
    if _boxes_apart(path, shape):
        return None
    if not filled:
        return punch.cut_strokes(path, shape, False)
    common = pathops.boolean(path, shape, 'intersect')   # rien de commun (dans un trou, à côté) : rien à faire
    if not common.contours or _area(common) < 1e-9:
        return None
    return pathops.boolean(path, shape, 'difference')


def _area(path: Path) -> float:
    """L'aire couverte (règle pair-impair approchée : contours extérieurs moins trous, par leur sens)."""
    total = 0.0
    for c in path.contours:
        P = c.flatten(0.01)
        total += sum(P[i][0] * P[(i + 1) % len(P)][1] - P[(i + 1) % len(P)][0] * P[i][1] for i in range(len(P))) / 2
    return abs(total)
