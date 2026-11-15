"""Une pièce de la bibliothèque dans un alésage d'une pièce 3D (« Pièce
dans ce trou », onglet Design STEP).

L'alésage est la paroi choisie elle-même (ses demi-faces et tronçons
réunis, `screwfit.Part`) : son axe, son entrée (le bout ouvert ; d'un
alésage débouchant, le haut, ou l'autre bout si on retourne), son fond,
son diamètre et sa profondeur. Un bout prolongé par un trou plus étroit est
un épaulement : fermé, la pièce s'y arrête. La pièce proposée prend le
diamètre de l'alésage et y est posée :

- goupille cylindrique (ISO 2338) : le diamètre de la série qui va (pas plus
  gros que l'alésage, au plus 0,5 mm plus petit), la plus longue dans la
  profondeur, au ras de l'entrée ;
- roulement rigide à billes : la référence de diamètre extérieur qui va
  (même règle ; à diamètre égal, celle qui tient dans la profondeur), au ras
  de l'entrée ;
- bague lisse : diamètre extérieur celui de l'alésage, toute la
  profondeur, au ras de l'entrée ;
- douille de guidage à collerette : diamètre extérieur celui de
  l'alésage, le corps dans toute la profondeur, la collerette sur l'entrée ;
- colonne de guidage à collerette (alésage débouchant) : diamètre guidé
  celui de l'alésage, la collerette contre la sortie, la colonne qui dépasse
  de l'entrée ;
- éjecteur (alésage débouchant) : diamètre de tige celui de l'alésage, le
  bout au ras de l'entrée, la tête juste sous la sortie ;
- bague de centrage : diamètre extérieur celui de l'alésage, posée au
  fond (borgne, elle dépasse pour centrer) ou au ras de l'entrée (débouchant).

Une pièce plus longue qu'un alésage borgne est posée au fond et dépasse de
l'entrée, jamais dans la matière (`outside` dit de combien elle dépasse).
Les cotes « à donner » (alésage d'une bague, collerette, tête) sont
proposées en proportion et se changent ; les coordonnées des pièces posées
sont celles du fichier de la pièce.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import brep as B
from . import screwfit as F
from . import stepgen as G

#: familles proposées, dans l'ordre de la liste
FAMILIES = ('goupille', 'roulement', 'bague', 'douille', 'colonne', 'ejecteur', 'bague_centrage')
#: familles qui traversent la pièce (alésage débouchant)
THROUGH_ONLY = ('colonne', 'ejecteur')
#: jeu (mm) au-delà duquel une goupille ou un roulement de la série ne va pas
FIT_MM = 0.5
#: une goupille ou un roulement plus gros que l'alésage de plus que ceci (mm) ne va pas
OVER_MM = 0.05
#: hauteur d'une bague de centrage proposée (mm)
CENTRING_H = 12.0


@dataclass
class Bore:
    """Un alésage : ses faces, son axe (du fond vers l'entrée), le point de l'axe à l'entrée, son diamètre, sa
    profondeur, débouchant ou non."""
    faces: list
    axis: np.ndarray
    entry: np.ndarray
    diameter: float
    depth: float
    through: bool
    flipped: bool = False

    @property
    def bottom(self) -> np.ndarray:
        return self.entry - self.axis * self.depth


def _shoulder(part: F.Part, g, hi: bool) -> bool:
    """Un trou plus étroit prolonge-t-il `g` au-delà de son bout `hi` (un épaulement) ?"""
    eps = max(part.tol, 1e-3)
    end = g.hi if hi else g.lo
    for h in part.coaxial('holes', g.axis, g.centre, r_max=g.radius - part.tol):
        P = part.points(h.faces)
        if not len(P):
            continue
        s = (P - g.centre) @ g.axis
        if abs((float(s.min()) if hi else float(s.max())) - end) <= eps:
            return True
    return False


def bore(T, face_of, infos, face: int, flip: bool = False, part: F.Part | None = None) -> Bore:
    """L'alésage dont `face` est une paroi (sans passer au trou plus étroit d'un lamage : la paroi choisie)."""
    if not 0 <= face < len(infos):
        raise F.FitError('face inconnue')
    k = infos[face] or {}
    if k.get('genre') != 'cylindre' or not k.get('creux', False):
        raise F.FitError('la face choisie n\'est pas la paroi d\'un trou')
    part = part if part is not None else F.Part(T, face_of, infos)
    g = part.group_of(face)
    if g is None:
        raise F.FitError('la face choisie n\'est pas la paroi d\'un trou')
    opened, _feats = F._ends(part, g)
    opened = {e: opened[e] and not _shoulder(part, g, e) for e in (True, False)}
    if not (opened[True] or opened[False]):
        raise F.FitError('alésage fermé des deux côtés (épaulements)')
    through = opened[True] and opened[False]
    a = g.axis
    head_hi = (a[2] >= -1e-9 if abs(a[2]) > 1e-9 else True) if through else opened[True]
    if flip:
        if not through:
            raise F.FitError('trou borgne : une seule entrée')
        head_hi = not head_hi
    axis = a if head_hi else -a
    entry = g.centre + a * (g.hi if head_hi else g.lo)
    # au micromètre près : le bruit de calcul d'un axe quelconque ne change pas les cotes proposées
    return Bore(list(g.faces), axis, entry, round(2.0 * g.radius, 6), round(g.hi - g.lo, 6), through, bool(flip))


def _half(x: float) -> float:
    """Arrondi au demi-millimètre."""
    return round(2.0 * x) / 2.0


def _fits(d: float, D: float) -> bool:
    """Une pièce de série de diamètre `d` va-t-elle dans l'alésage `D` ?"""
    return d <= D + OVER_MM and D - d <= FIT_MM


def propose(b: Bore, family: str) -> dict:
    """Les valeurs du générateur `family` pour l'alésage `b` (FitError si la famille n'y va pas, ni hors des
    cotes du générateur)."""
    try:
        return _propose(b, family)
    except G.GenError as ex:
        raise F.FitError(str(ex)) from None


def _propose(b: Bore, family: str) -> dict:
    D, h = b.diameter, b.depth
    if family in THROUGH_ONLY and not b.through:
        raise F.FitError('alésage borgne : la pièce le traverse')
    if family == 'goupille':
        sizes = [float(x) for x in G.FAMILIES['goupille'].params[0].choices if _fits(float(x), D)]
        if not sizes:
            raise F.FitError(f'pas de goupille de la série au Ø{D:g}')
        d = max(sizes)
        lens = G._lengths(2 * d, 10 * d)
        L = max((x for x in lens if x <= h + 1e-6), default=lens[0])
        return G.values('goupille', d=d, length=float(L))
    if family == 'roulement':
        refs = [r for r in G.FAMILIES['roulement'].params[0].choices
                if r in G.BEARINGS and _fits(G.BEARINGS[r][1], D)]
        if not refs:
            raise F.FitError(f'pas de roulement de la série au Ø{D:g}')
        OD = max(G.BEARINGS[r][1] for r in refs)
        same = [r for r in refs if G.BEARINGS[r][1] == OD]
        fit = [r for r in same if G.BEARINGS[r][2] <= h + 1e-6]
        ref = max(fit, key=lambda r: G.BEARINGS[r][2]) if fit else min(same, key=lambda r: G.BEARINGS[r][2])
        return G.values('roulement', ref=ref)
    if family == 'bague':
        return G.values('bague', D=D, d=max(_half(0.625 * D), 0.5), length=h, chamfer=0.5 if D >= 10 else 0.2)
    if family == 'douille':
        return G.values('douille', D=D, d=max(_half(0.64 * D), 0.5), length=h + 5.0, D2=D + 5.0, h=5.0)
    if family == 'colonne':
        return G.values('colonne', d=D, D=D + 8.0, h=6.0, length=float(math.ceil(h + 6.0 + 2.0 * D - 1e-6)))
    if family == 'ejecteur':
        k = 3.0 if D <= 4 else (5.0 if D <= 10 else 7.0)
        return G.values('ejecteur', d1=D, d2=_half(D + max(4.0, 0.6 * D)), k=k, length=float(math.ceil(h - 1e-6) + k))
    if family == 'bague_centrage':
        return G.values('bague_centrage', D=D, d=max(_half(0.36 * D), 0.5),
                        h=min(CENTRING_H, h) if b.through else max(h, CENTRING_H))
    raise F.FitError(f'famille inconnue : {family}')


def placement(b: Bore, family: str, v: dict) -> list:
    """La matrice qui pose la pièce du générateur (sur l'axe Z, de Z = 0 au bas) dans l'alésage."""
    def at(z_local_at_entry: float, down: bool = False):
        if down:                                           # Z de la pièce vers le fond
            return B.placement(tuple(float(x) for x in b.entry + b.axis * z_local_at_entry),
                               tuple(float(x) for x in -b.axis))
        return B.placement(tuple(float(x) for x in b.entry - b.axis * z_local_at_entry),
                           tuple(float(x) for x in b.axis))

    def flush(length: float):                              # au ras de l'entrée ; plus longue qu'un borgne : au fond
        return at(length if b.through or length <= b.depth + 1e-6 else b.depth)
    if family == 'goupille':
        return flush(float(v['length']))
    if family == 'roulement':
        return flush(float(G.BEARINGS[v['ref']][2]))
    if family == 'bague':
        return flush(float(v['length']))
    if family == 'douille':
        body = float(v['length']) - float(v['h'])
        return at(body if b.through else min(body, b.depth))
    if family == 'colonne':
        return at(b.depth + float(v['h']))
    if family == 'ejecteur':
        return at(0.0, down=True)
    if family == 'bague_centrage':
        return at(float(v['h']) if b.through else b.depth)
    raise F.FitError(f'famille inconnue : {family}')


def parts(b: Bore, family: str, v: dict) -> list:
    """Les corps de la pièce `family` aux valeurs `v`, posée dans l'alésage."""
    M = placement(b, family, v)
    bodies = G.build(family, v)
    for body in bodies:
        body.matrix = B.compose(M, body.matrix) if body.matrix is not None else M
    return bodies


def outside(b: Bore, bodies: list) -> tuple:
    """(dépassement de l'entrée, dépassement de la sortie ou du fond) des corps posés, mm le long de l'axe (0 :
    dans l'alésage)."""
    P = np.concatenate([B.mesh(x).reshape(-1, 3) for x in bodies]) if bodies else np.zeros((0, 3))
    if not len(P):
        return 0.0, 0.0
    t = (P - b.entry) @ b.axis
    return round(max(float(t.max()), 0.0), 3), round(max(-float(t.min()) - b.depth, 0.0), 3)


def same_bores(T, face_of, infos, b: Bore, part: F.Part | None = None) -> list:
    """Les alésages comme `b` (même diamètre, même profondeur, débouchants ou non pareil, entrée du même côté),
    `b` d'abord."""
    part = part if part is not None else F.Part(T, face_of, infos)
    out = [b]
    for g in part.holes:
        if set(g.faces) & set(b.faces) or abs(2.0 * g.radius - b.diameter) > 2 * part.tol \
                or abs((g.hi - g.lo) - b.depth) > max(5 * part.tol, 0.05):
            continue
        for flip in (False, True):
            try:
                c = bore(T, face_of, infos, g.faces[0], flip, part)
            except F.FitError:
                continue
            if float(c.axis @ b.axis) >= F.PARALLEL:
                break
        else:
            continue
        if c.through == b.through:
            out.append(c)
    return out
