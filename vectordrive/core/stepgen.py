"""Générateurs de pièces STEP : visserie, rondelles, goupilles, roulements,
clavettes, engrenages, barres et profilés, plaques percées, éléments de
moule — en vraies faces (`core.brep`), filets non représentés (comme les
modèles simplifiés des catalogues).

Chaque famille (`FAMILIES`) a ses paramètres (`Param`) et rend des corps
debout sur l'axe Z : vis sous tête en Z = 0, tige vers le bas (vis à tête
fraisée : dessus de la tête en Z = 0) ; écrous, rondelles, bagues, barres
posés sur Z = 0. Les dimensions normalisées sont celles des tables de la
norme citée (valeurs nominales) ; les familles sans norme le disent.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import brep as B

STEEL = (0.62, 0.64, 0.68)
ZINC = (0.78, 0.80, 0.84)
BLACK = (0.22, 0.23, 0.25)
BRASS = (0.80, 0.66, 0.30)
ALU = (0.70, 0.74, 0.80)

#: pas gros (ISO 261)
PITCH = {'M1.6': 0.35, 'M2': 0.4, 'M2.5': 0.45, 'M3': 0.5, 'M4': 0.7, 'M5': 0.8, 'M6': 1.0, 'M8': 1.25,
         'M10': 1.5, 'M12': 1.75, 'M14': 2.0, 'M16': 2.0, 'M20': 2.5, 'M24': 3.0}

#: longueurs préférentielles des normes de vis (mm)
LENGTHS = (3, 4, 5, 6, 8, 10, 12, 16, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 80, 90, 100, 110, 120, 130, 140,
           150, 160, 180, 200)

#: ISO 4762 (CHC) : diamètre de tête dk, hauteur k, six pans s, profondeur t ; longueurs mini, maxi
ISO4762 = {'M2': (3.8, 2, 1.5, 1.0, 3, 20), 'M2.5': (4.5, 2.5, 2, 1.1, 4, 25), 'M3': (5.5, 3, 2.5, 1.3, 5, 30),
           'M4': (7, 4, 3, 2, 6, 40), 'M5': (8.5, 5, 4, 2.5, 8, 50), 'M6': (10, 6, 5, 3, 10, 60),
           'M8': (13, 8, 6, 4, 12, 80), 'M10': (16, 10, 8, 5, 16, 100), 'M12': (18, 12, 10, 6, 20, 120),
           'M14': (21, 14, 12, 7, 25, 140), 'M16': (24, 16, 14, 8, 25, 160), 'M20': (30, 20, 17, 10, 30, 200),
           'M24': (36, 24, 19, 12, 40, 200)}
#: ISO 4017 (H, filetée jusque sous tête) : surplat s, hauteur k
ISO4017 = {'M3': (5.5, 2), 'M4': (7, 2.8), 'M5': (8, 3.5), 'M6': (10, 4), 'M8': (13, 5.3), 'M10': (16, 6.4),
           'M12': (18, 7.5), 'M14': (21, 8.8), 'M16': (24, 10), 'M20': (30, 12.5), 'M24': (36, 15)}
#: ISO 10642 (FHC, tête fraisée 90°) : dk théorique, k, six pans s, profondeur t
ISO10642 = {'M3': (6.72, 1.86, 2, 1.1), 'M4': (8.96, 2.48, 2.5, 1.5), 'M5': (11.2, 3.1, 3, 1.9),
            'M6': (13.44, 3.72, 4, 2.2), 'M8': (17.92, 4.96, 5, 3), 'M10': (22.4, 6.2, 6, 3.6),
            'M12': (26.88, 7.44, 8, 4.3), 'M16': (33.6, 8.8, 10, 4.8), 'M20': (40.32, 10.16, 12, 5.6)}
#: ISO 7380 (BHC, tête bombée) : dk, k, six pans s, profondeur t
ISO7380 = {'M3': (5.7, 1.65, 2, 1.04), 'M4': (7.6, 2.2, 2.5, 1.3), 'M5': (9.5, 2.75, 3, 1.56),
           'M6': (10.5, 3.3, 4, 2.08), 'M8': (14, 4.4, 5, 2.6), 'M10': (17.5, 5.5, 6, 3.12),
           'M12': (21, 6.6, 8, 4.16)}
#: ISO 4026 (STHC bout plat) : six pans s, profondeur t
ISO4026 = {'M3': (1.5, 1.2), 'M4': (2, 1.5), 'M5': (2.5, 2), 'M6': (3, 2), 'M8': (4, 3), 'M10': (5, 4),
           'M12': (6, 4.8), 'M16': (8, 6.4)}
#: ISO 4032 (écrou H) : surplat s, hauteur m
ISO4032 = {'M2': (4, 1.6), 'M2.5': (5, 2), 'M3': (5.5, 2.4), 'M4': (7, 3.2), 'M5': (8, 4.7), 'M6': (10, 5.2),
           'M8': (13, 6.8), 'M10': (16, 8.4), 'M12': (18, 10.8), 'M14': (21, 12.8), 'M16': (24, 14.8),
           'M20': (30, 18), 'M24': (36, 21.5)}
#: ISO 7089 (rondelle plate) : d1, d2, h
ISO7089 = {'M2': (2.2, 5, 0.3), 'M2.5': (2.7, 6, 0.5), 'M3': (3.2, 7, 0.5), 'M4': (4.3, 9, 0.8),
           'M5': (5.3, 10, 1), 'M6': (6.4, 12, 1.6), 'M8': (8.4, 16, 1.6), 'M10': (10.5, 20, 2),
           'M12': (13, 24, 2.5), 'M14': (15, 28, 2.5), 'M16': (17, 30, 3), 'M20': (21, 37, 3), 'M24': (25, 44, 4)}
#: ISO 7093-1 (rondelle large) : d1, d2, h
ISO7093 = {'M3': (3.2, 9, 0.8), 'M4': (4.3, 12, 1), 'M5': (5.3, 15, 1.2), 'M6': (6.4, 18, 1.6),
           'M8': (8.4, 24, 2), 'M10': (10.5, 30, 2.5), 'M12': (13, 37, 3), 'M16': (17, 50, 3), 'M20': (22, 60, 4)}
#: trous de passage ISO 273 (série moyenne) ; lamages pour CHC (diamètre, profondeur = k + 0,5)
CLEARANCE = {'M2': 2.4, 'M2.5': 2.9, 'M3': 3.4, 'M4': 4.5, 'M5': 5.5, 'M6': 6.6, 'M8': 9, 'M10': 11, 'M12': 13.5,
             'M14': 15.5, 'M16': 17.5, 'M20': 22, 'M24': 26}
COUNTERBORE = {'M2': 4.4, 'M2.5': 5.5, 'M3': 6.5, 'M4': 8, 'M5': 10, 'M6': 11, 'M8': 15, 'M10': 18, 'M12': 20,
               'M14': 24, 'M16': 26, 'M20': 33, 'M24': 40}
#: roulements rigides à billes (série 6) : d, D, B, chanfrein r
BEARINGS = {'623': (3, 10, 4, 0.15), '624': (4, 13, 5, 0.2), '625': (5, 16, 5, 0.3), '626': (6, 19, 6, 0.3),
            '608': (8, 22, 7, 0.3), '609': (9, 24, 7, 0.3), '6000': (10, 26, 8, 0.3), '6001': (12, 28, 8, 0.3),
            '6002': (15, 32, 9, 0.3), '6003': (17, 35, 10, 0.3), '6004': (20, 42, 12, 0.6),
            '6005': (25, 47, 12, 0.6), '6200': (10, 30, 9, 0.6), '6201': (12, 32, 10, 0.6),
            '6202': (15, 35, 11, 0.6), '6203': (17, 40, 12, 0.6), '6204': (20, 47, 14, 1.0),
            '6205': (25, 52, 15, 1.0), '6206': (30, 62, 16, 1.0)}
#: DIN 6885 forme A (clavette parallèle) : largeur b, hauteur h
DIN6885 = {'2x2': (2, 2), '3x3': (3, 3), '4x4': (4, 4), '5x5': (5, 5), '6x6': (6, 6), '8x7': (8, 7),
           '10x8': (10, 8), '12x8': (12, 8), '14x9': (14, 9), '16x10': (16, 10), '18x11': (18, 11),
           '20x12': (20, 12)}


@dataclass
class Param:
    key: str
    label: str
    kind: str = 'float'              # 'float', 'int', 'choice'
    default: object = 0.0
    choices: tuple = ()              # 'choice' : valeurs proposées
    lo: float = 0.0
    hi: float = 1e6
    unit: str = 'mm'


@dataclass
class Family:
    key: str
    label: str
    category: str
    standard: str
    params: list
    build: object                    # build(values) -> list[Body]
    name: object                     # name(values) -> str (nom de fichier sans extension)
    note: str = ''
    series: object = None            # series() -> [values…] : toute la gamme (bibliothèque)
    tags: list = field(default_factory=list)


class GenError(ValueError):
    pass


def _num(v) -> str:
    return f'{float(v):g}'


def _need(cond: bool, msg: str) -> None:
    if not cond:
        raise GenError(msg)


def _lengths(lo: float, hi: float) -> list:
    return [L for L in LENGTHS if lo <= L <= hi]


def _size(values, table) -> tuple:
    size = values['size']
    _need(size in table, f'taille inconnue : {size}')
    return size, float(size[1:])


# --- visserie ---------------------------------------------------------------------------------------------
def _shank(d: float, L: float, P: float, top: float = 0.0) -> list:
    """Profil (z, r) d'une tige filetée de diamètre d, de top - L à top, bout chanfreiné."""
    c = min(0.6 * P + 0.05 * d, L / 4.0)
    return [(top - L, d / 2 - c), (top - L + c, d / 2), (top, d / 2)]


def build_chc(v) -> list:
    size, d = _size(v, ISO4762)
    dk, k, s, t, _lo, _hi = ISO4762[size]
    L = float(v['length'])
    _need(L >= 2, 'longueur trop courte')
    ch = round(0.05 * dk, 2)
    prof = _shank(d, L, PITCH[size]) + [(0.0, dk / 2), (k - ch, dk / 2), (k, dk / 2 - ch)]
    body = B.revolve(prof, f'Vis CHC ISO 4762 {size}x{_num(L)}', BLACK)
    return [B.add_loop(body, k - t, k, B.polygon(6, s, start_deg=30))]


def build_h(v) -> list:
    size, d = _size(v, ISO4017)
    s, k = ISO4017[size]
    L = float(v['length'])
    _need(L >= 2, 'longueur trop courte')
    body = B.revolve(_shank(d, L, PITCH[size]), f'Vis H ISO 4017 {size}x{_num(L)}', ZINC)
    body.slabs.append(B.Slab(0.0, k, [B.polygon(6, s)]))
    return [body]


def build_fhc(v) -> list:
    size, d = _size(v, ISO10642)
    dk, k, s, t = ISO10642[size]
    L = float(v['length'])
    c = min(0.6 * PITCH[size] + 0.05 * d, L / 4.0)              # chanfrein du bout (_shank)
    _need(L - c > k + 0.2, 'longueur trop courte pour la tête')
    prof = _shank(d, L, PITCH[size]) [:2] + [(-k, d / 2), (0.0, dk / 2)]
    body = B.revolve(prof, f'Vis FHC ISO 10642 {size}x{_num(L)}', BLACK)
    return [B.add_loop(body, -t, 0.0, B.polygon(6, s, start_deg=30))]


def build_bhc(v) -> list:
    size, d = _size(v, ISO7380)
    dk, k, s, t = ISO7380[size]
    L = float(v['length'])
    _need(L >= 2, 'longueur trop courte')
    rt = max(0.31 * dk, 0.65 * s)                      # méplat du dessus, où s'ouvre l'empreinte
    r0 = dk / 2
    zc = (rt * rt + k * k - r0 * r0) / (2 * k)         # sphère passant par (r0, 0) et (rt, k)
    R = math.sqrt(r0 * r0 + zc * zc)
    body = B.revolve(_shank(d, L, PITCH[size]), f'Vis BHC ISO 7380 {size}x{_num(L)}', BLACK)
    body.slabs.append(B.Slab(0.0, k, [B.Circle(0.0, 0.0, r0, sphere=(zc, R))]))
    return [B.add_loop(body, k - t, k, B.polygon(6, s, start_deg=30))]


def build_sthc(v) -> list:
    size, d = _size(v, ISO4026)
    s, t = ISO4026[size]
    L = float(v['length'])
    _need(L > t + 0.5, 'longueur plus courte que l\'empreinte')
    c = min(0.6 * PITCH[size], L / 4)
    prof = [(-L, d / 2 - c), (-L + c, d / 2), (-c, d / 2), (0.0, d / 2 - c)]
    body = B.revolve(prof, f'Vis STHC ISO 4026 {size}x{_num(L)}', BLACK)
    return [B.add_loop(body, -t, 0.0, B.polygon(6, s, start_deg=30))]


def build_nut(v) -> list:
    size, d = _size(v, ISO4032)
    s, m = ISO4032[size]
    return [B.Body(f'Ecrou H ISO 4032 {size}', [B.Slab(0.0, m, [B.polygon(6, s), B.Circle(0.0, 0.0, d / 2)])], ZINC)]


def _washer(table, std: str):
    def build(v) -> list:
        size, _d = _size(v, table)
        d1, d2, h = table[size]
        return [B.Body(f'Rondelle {std} {size}', [B.Slab(0.0, h, [B.Circle(0, 0, d2 / 2), B.Circle(0, 0, d1 / 2)])],
                       ZINC)]
    return build


def build_pin(v) -> list:
    d, L = float(v['d']), float(v['length'])
    _need(d > 0 and L > d / 2, 'goupille trop courte')
    c = round(0.12 * d, 2)
    prof = [(0.0, d / 2 - c), (c, d / 2), (L - c, d / 2), (L, d / 2 - c)]
    return [B.revolve(prof, f'Goupille ISO 2338 {_num(d)}x{_num(L)}', STEEL)]


# --- transmission ---------------------------------------------------------------------------------------
def _ring(z_list, r_out, r_in, name, color) -> B.Body:
    """Bague : rayons extérieur et intérieur (fonctions de z, linéaires entre les cotes de `z_list`)."""
    slabs = []
    for za, zb in zip(z_list, z_list[1:]):
        if zb - za < B.EPS:
            continue
        ra, rb, ia, ib = r_out(za, 1), r_out(zb, -1), r_in(za, 1), r_in(zb, -1)
        slabs.append(B.Slab(za, zb, [B.Circle(0, 0, ra, None if abs(rb - ra) < B.EPS else rb),
                                     B.Circle(0, 0, ia, None if abs(ib - ia) < B.EPS else ib)]))
    return B.Body(name, slabs, color)


def build_bearing(v) -> list:
    ref = v['ref']
    _need(ref in BEARINGS, f'roulement inconnu : {ref}')
    d, D, W, r = BEARINGS[ref]
    c = r
    e = min(0.2, c / 2)                                 # retrait des flasques
    zs = [0.0, e, c, W - c, W - e, W]

    def r_out(z, _side):
        if z < c:
            return D / 2 - c + z
        if z > W - c:
            return D / 2 - (z - (W - c))
        return D / 2

    def r_in(z, _side):
        if z < c:
            return d / 2 + c - z
        if z > W - c:
            return d / 2 + (z - (W - c))
        return d / 2
    body = _ring(zs, r_out, r_in, f'Roulement {ref}', STEEL)
    band = (D - d) / 2
    r1, r2 = d / 2 + 0.3 * band, D / 2 - 0.25 * band     # flasque entre les bagues, en retrait
    for z0, z1 in ((0.0, e), (W - e, W)):
        body = B.add_loop(body, z0, z1, B.Circle(0, 0, r2))
        body = B.add_loop(body, z0, z1, B.Circle(0, 0, r1))
    return [body]


def build_key(v) -> list:
    size = v['size']
    _need(size in DIN6885, f'clavette inconnue : {size}')
    b, h = DIN6885[size]
    L = float(v['length'])
    _need(L > b, 'clavette plus courte que sa largeur')
    return [B.Body(f'Clavette DIN 6885 A {size}x{_num(L)}', [B.Slab(0.0, h, [B.slot(0, 0, L, b)])], STEEL)]


def _involute_gear(m: float, z: int, alpha_deg: float = 20.0, n_flank: int = 6) -> list:
    """Contour d'une roue dentée droite (développante, pied en rayon droit) : points dans le sens direct."""
    alpha = math.radians(alpha_deg)
    rp = m * z / 2
    rb = rp * math.cos(alpha)
    ra = rp + m
    rf = max(rp - 1.25 * m, 0.5 * rp)
    inv = lambda a: math.tan(a) - a                       # noqa: E731
    half = math.pi / (2 * z) + inv(alpha)                 # demi-épaisseur angulaire au cercle de base
    r_start = max(rb, rf)
    flank = []
    for i in range(n_flank + 1):
        r = r_start + (ra - r_start) * i / n_flank
        phi = math.acos(min(1.0, rb / r))
        flank.append((r, half - inv(phi)))                # angle polaire depuis l'axe de la dent
    pts = []
    pitch = 2 * math.pi / z
    for k in range(z):
        a0 = k * pitch
        if rf < r_start - 1e-9:
            pts.append((rf * math.cos(a0 - flank[0][1]), rf * math.sin(a0 - flank[0][1])))
        for r, th in flank:                               # flanc montant (côté -)
            pts.append((r * math.cos(a0 - th), r * math.sin(a0 - th)))
        for r, th in reversed(flank):                     # flanc descendant (côté +)
            pts.append((r * math.cos(a0 + th), r * math.sin(a0 + th)))
        if rf < r_start - 1e-9:
            pts.append((rf * math.cos(a0 + flank[0][1]), rf * math.sin(a0 + flank[0][1])))
    out = []
    for p in pts:                                         # points confondus retirés
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 1e-6:
            out.append(p)
    if math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) < 1e-6:
        out.pop()
    return out


def build_gear(v) -> list:
    m, z, b, bore = float(v['module']), int(v['teeth']), float(v['width']), float(v['bore'])
    _need(m > 0 and z >= 8, 'module positif, 8 dents au moins')
    rf = m * z / 2 - 1.25 * m
    _need(0 <= bore / 2 < rf - m, 'alésage trop grand pour la roue')
    loops = [B.Poly(_involute_gear(m, z))]
    if bore > 0:
        loops.append(B.Circle(0, 0, bore / 2))
    return [B.Body(f'Roue dentee m{_num(m)} z{z}', [B.Slab(0.0, b, loops)], STEEL)]


# --- barres, profilés -------------------------------------------------------------------------------------
def build_bar(v) -> list:
    shape, L = v['shape'], float(v['length'])
    a, e = float(v['a']), float(v['e'])
    bb = float(v['b'])
    _need(L > 0 and a > 0, 'dimensions positives')
    label = {'rond': f'Rond {_num(a)}', 'tube': f'Tube {_num(a)}x{_num(e)}', 'carre': f'Carre {_num(a)}',
             'plat': f'Plat {_num(a)}x{_num(bb)}', 'six_pans': f'Six pans {_num(a)}',
             'tube_carre': f'Tube carre {_num(a)}x{_num(e)}', 'corniere': f'Corniere {_num(a)}x{_num(bb)}x{_num(e)}',
             'u': f'U {_num(a)}x{_num(bb)}x{_num(e)}'}[shape] + f' L{_num(L)}'
    if shape == 'rond':
        loops = [B.Circle(0, 0, a / 2)]
    elif shape == 'tube':
        _need(0 < e < a / 2, 'épaisseur du tube')
        loops = [B.Circle(0, 0, a / 2), B.Circle(0, 0, a / 2 - e)]
    elif shape == 'carre':
        loops = [B.rounded_rect(-a / 2, -a / 2, a / 2, a / 2)]
    elif shape == 'plat':
        _need(bb > 0, 'épaisseur du plat')
        loops = [B.rounded_rect(-a / 2, -bb / 2, a / 2, bb / 2)]
    elif shape == 'six_pans':
        loops = [B.polygon(6, a)]
    elif shape == 'tube_carre':
        _need(0 < e < a / 2, 'épaisseur du tube')
        loops = [B.rounded_rect(-a / 2, -a / 2, a / 2, a / 2, 1.5 * e),
                 B.rounded_rect(-a / 2 + e, -a / 2 + e, a / 2 - e, a / 2 - e, 0.5 * e)]
    elif shape == 'corniere':
        _need(0 < e < min(a, bb), 'épaisseur de la cornière')
        loops = [B.Poly([(0, 0), (a, 0), (a, e), (e, e), (e, bb), (0, bb)])]
    else:
        _need(0 < e < min(a / 2, bb), 'épaisseur du U')
        loops = [B.Poly([(0, 0), (a, 0), (a, bb), (a - e, bb), (a - e, e), (e, e), (e, bb), (0, bb)])]
    return [B.Body(label, [B.Slab(0.0, L, loops)], ALU)]


def _hole_profile(kind: str, size: str, thick: float) -> list:
    """Trou traversant d'axe Z, de 0 à `thick` : [(z0, z1, cercle)…] (lamage, fraisure en haut)."""
    if kind == 'passage':
        r = CLEARANCE[size] / 2
        return [(0.0, thick, B.Circle(0, 0, r))]
    if kind == 'taraude':
        d = float(size[1:])
        return [(0.0, thick, B.Circle(0, 0, (d - PITCH[size]) / 2))]
    if kind == 'lamage':
        dk, k = ISO4762[size][0], ISO4762[size][1]
        depth = min(k + 0.5, thick - 1.0)
        _need(depth > 0, 'plaque trop mince pour le lamage')
        return [(0.0, thick - depth, B.Circle(0, 0, CLEARANCE[size] / 2)),
                (thick - depth, thick, B.Circle(0, 0, COUNTERBORE[size] / 2))]
    if kind == 'fraisure':
        dk = ISO10642[size][0] + 0.5
        rc = CLEARANCE[size] / 2
        depth = dk / 2 - rc                               # 90° : profondeur = différence des rayons
        _need(depth < thick - 0.5, 'plaque trop mince pour la fraisure')
        return [(0.0, thick - depth, B.Circle(0, 0, rc)), (thick - depth, thick, B.Circle(0, 0, rc, dk / 2))]
    raise GenError(f'trou inconnu : {kind}')


def build_plate(v) -> list:
    L, W, e, rc = float(v['length']), float(v['width']), float(v['thickness']), float(v['corner'])
    _need(L > 0 and W > 0 and e > 0, 'dimensions positives')
    pattern, kind, size = v['pattern'], v['hole'], v['size']
    m = float(v['margin'])
    nx, ny = max(1, int(v['nx'])), max(1, int(v['ny']))
    _need(pattern != 'grille' or nx * ny <= 625, 'au plus 625 trous en grille (25 × 25)')
    xs, ys = [], []
    if pattern == 'coins':
        xs, ys = [m, L - m], [m, W - m]
    elif pattern == 'grille':
        xs = [m + (L - 2 * m) * i / (nx - 1) for i in range(nx)] if nx > 1 else [L / 2]
        ys = [m + (W - 2 * m) * j / (ny - 1) for j in range(ny)] if ny > 1 else [W / 2]
    elif pattern == 'centre':
        xs, ys = [L / 2], [W / 2]
    centers = [(x, y) for y in ys for x in xs]
    prof = _hole_profile(kind, size, e) if centers else []
    rmax = max((c.r_top or c.r) for _z0, _z1, c in prof) if prof else 0.0
    gap = 0.2                                                    # matière gardée entre trous et bords
    rc = max(0.0, min(rc, L / 2, W / 2))
    for x, y in centers:
        _need(rmax + gap <= x <= L - rmax - gap and rmax + gap <= y <= W - rmax - gap,
              'trou hors de la plaque (marge trop petite)')
        if (x < rc or x > L - rc) and (y < rc or y > W - rc):  # dans un coin arrondi
            cx, cy = (rc if x < rc else L - rc), (rc if y < rc else W - rc)
            _need(math.hypot(x - cx, y - cy) <= rc - rmax - gap, 'trou qui mord sur un coin arrondi')
    steps = [b - a for t in (xs, ys) for a, b in zip(sorted(t), sorted(t)[1:])]
    _need(not steps or min(steps) > 2 * rmax + gap, 'trous qui se touchent')
    body = B.Body(f'Plaque {_num(L)}x{_num(W)}x{_num(e)}', [B.Slab(0.0, e, [B.rounded_rect(0, 0, L, W, rc)])], ALU)
    body = B.cut(body, *sorted({z for z0, z1, _c in prof for z in (z0, z1)}))
    for sl in body.slabs:                                        # tous les trous d'un coup, tranche par tranche
        for z0, z1, c in prof:
            if sl.z0 >= z0 - B.EPS and sl.z1 <= z1 + B.EPS:
                sl.loops += [B.Circle(x, y, c.radius(sl.z0, z0, z1), None if c.r_top is None
                                      else c.radius(sl.z1, z0, z1)) for x, y in centers]
    return [body]


def build_spacer(v) -> list:
    kind, L = v['shape'], float(v['length'])
    size = v['size']
    _need(size in PITCH, f'taille inconnue : {size}')
    d = float(size[1:])
    hole = B.Circle(0, 0, (d - PITCH[size]) / 2)
    if kind == 'six_pans':
        s = {'M2': 4, 'M2.5': 5, 'M3': 5.5, 'M4': 7, 'M5': 8, 'M6': 10, 'M8': 13}.get(size, 2 * d)
        outer, label = B.polygon(6, s), f'Entretoise six pans {size}x{_num(L)}'
    else:
        D = float(v['D'])
        _need(D > d + 1, 'diamètre extérieur trop petit')
        outer, label = B.Circle(0, 0, D / 2), f'Entretoise ronde {size} D{_num(D)}x{_num(L)}'
    return [B.Body(label, [B.Slab(0.0, L, [outer, hole])], BRASS)]


def build_flange(v) -> list:
    """Bride ronde : disque percé de trous sur un cercle (passage, lamés, fraisés ou taraudés, comme la plaque
    percée), alésage au centre au besoin, centrage en saillie dessus au besoin ; dessous à Z = 0, axe Z."""
    D, T, d = float(v['D']), float(v['thickness']), float(v['bore'])
    n, pcd, a0 = int(v['n']), float(v['pcd']), float(v['start'])
    ds, hs = float(v['spigot']), float(v['spigot_height'])
    _need(D > 0 and T > 0, 'dimensions positives')
    _need(0 <= d < D, 'alésage plus petit que la bride')
    spigot = ds > 0 and hs > 0
    _need(not spigot or d < ds < D, 'centrage entre l\'alésage et le bord')
    prof = _hole_profile(v['hole'], v['size'], T) if n > 0 else []
    rmax = max((c.r_top or c.r) for _z0, _z1, c in prof) if prof else 0.0
    gap = 0.5                                                    # matière gardée autour des trous
    if n > 0:
        inner = max(d / 2, ds / 2 if spigot else 0.0)
        _need(pcd / 2 - rmax >= inner + gap, 'trous sur l\'alésage ou sous le centrage (cercle trop petit)')
        _need(pcd / 2 + rmax <= D / 2 - gap, 'trous hors de la bride (cercle trop grand)')
        _need(n == 1 or pcd * math.sin(math.pi / n) > 2 * rmax + gap, 'trous qui se touchent')
    centers = [(pcd / 2 * math.cos(math.radians(a0 + 360.0 * i / n)), pcd / 2 * math.sin(math.radians(a0 + 360.0 * i / n)))
               for i in range(n)]
    bore = [B.Circle(0.0, 0.0, d / 2)] if d > 0 else []
    body = B.Body(f'Bride ronde {_num(D)}x{_num(T)}', [B.Slab(0.0, T, [B.Circle(0.0, 0.0, D / 2)] + bore)], STEEL)
    body = B.cut(body, *sorted({z for z0, z1, _c in prof for z in (z0, z1)}))
    for sl in body.slabs:
        for z0, z1, c in prof:
            if sl.z0 >= z0 - B.EPS and sl.z1 <= z1 + B.EPS:
                sl.loops += [B.Circle(x, y, c.radius(sl.z0, z0, z1), None if c.r_top is None
                                      else c.radius(sl.z1, z0, z1)) for x, y in centers]
    if spigot:
        body.slabs.append(B.Slab(T, T + hs, [B.Circle(0.0, 0.0, ds / 2)] + bore))
    return [body]


def build_bush(v) -> list:
    d, D, L = float(v['d']), float(v['D']), float(v['length'])
    _need(0 < d < D and L > 0, 'diamètres et longueur')
    c = min(float(v['chamfer']), 0.95 * (D - d) / 4, L / 4)     # chanfreins qui laissent une couronne
    zs = [0.0, c, L - c, L] if c > 0 else [0.0, L]

    def r_out(z, _s):
        return D / 2 - max(0.0, c - z, z - (L - c)) if c > 0 else D / 2

    def r_in(z, _s):
        return d / 2 + max(0.0, c - z, z - (L - c)) if c > 0 else d / 2
    return [_ring(zs, r_out, r_in, f'Bague {_num(d)}x{_num(D)}x{_num(L)}', BRASS)]


# --- moule (sans norme : dimensions à donner) -----------------------------------------------------------
def build_ejector(v) -> list:
    d1, L, d2, k = float(v['d1']), float(v['length']), float(v['d2']), float(v['k'])
    _need(0 < d1 < d2 and L > k > 0, 'diamètres et longueurs')
    prof = [(0.0, d1 / 2), (L - k, d1 / 2), (L - k, d2 / 2), (L, d2 / 2)]
    return [B.revolve(prof, f'Ejecteur {_num(d1)}x{_num(L)}', STEEL)]


def build_pillar(v) -> list:
    d, L, D, h = float(v['d']), float(v['length']), float(v['D']), float(v['h'])
    _need(0 < d < D and L > h > 0, 'diamètres et longueurs')
    c = min(0.1 * d, 1.0)
    prof = [(0.0, D / 2), (h, D / 2), (h, d / 2), (L - c, d / 2), (L, d / 2 - c)]
    return [B.revolve(prof, f'Colonne de guidage {_num(d)}x{_num(L)}', STEEL)]


def build_guide_bush(v) -> list:
    d, D, L, D2, h = float(v['d']), float(v['D']), float(v['length']), float(v['D2']), float(v['h'])
    _need(0 < d < D < D2 and L > h > 0, 'diamètres et longueurs')
    slabs = [B.Slab(0.0, L - h, [B.Circle(0, 0, D / 2), B.Circle(0, 0, d / 2)]),
             B.Slab(L - h, L, [B.Circle(0, 0, D2 / 2), B.Circle(0, 0, d / 2)])]
    return [B.Body(f'Douille de guidage {_num(d)}x{_num(L)}', slabs, BRASS)]


def build_locating_ring(v) -> list:
    D, d, h = float(v['D']), float(v['d']), float(v['h'])
    _need(0 < d < D and h > 0, 'diamètres et hauteur')
    c = min(1.0, h / 4, (D - d) / 8)
    zs = [0.0, h - c, h]

    def r_out(z, _s):
        return D / 2 - max(0.0, z - (h - c))

    def r_in(z, _s):
        return d / 2 + max(0.0, z - (h - c))
    return [_ring(zs, r_out, r_in, f'Bague de centrage D{_num(D)}', STEEL)]


# --- bridage (sans norme : dimensions à donner) ----------------------------------------------------------
def build_strap_clamp(v) -> list:
    """Bride de serrage : longueur en X, lumière oblongue au milieu pour la vis (largeur de passage) ; talon
    dessous au bout X = longueur, sur toute la largeur (hauteur 0 : bride plate)."""
    L, W, e, size, ls = float(v['length']), float(v['width']), float(v['thickness']), v['size'], float(v['slot'])
    h, lh = float(v['heel']), float(v['heel_length'])
    _need(size in CLEARANCE, f'taille inconnue : {size}')
    w = CLEARANCE[size]
    _need(L > 0 and W > 0 and e > 0, 'dimensions positives')
    _need(W >= w + 4.0, 'bride trop étroite pour la vis')
    _need(w <= ls <= L - 6.0, 'lumière plus courte que la vis ou plus longue que la bride')
    top = [B.rounded_rect(0, -W / 2, L, W / 2), B.slot(L / 2, 0, ls, w)]
    name = f'Bride {_num(L)}x{_num(W)}x{_num(e)} {size}'
    if h <= 0:
        return [B.Body(name, [B.Slab(0.0, e, top)], BLACK)]
    _need(0 < lh < L and L - lh >= L / 2 + ls / 2 + 2.0, 'talon sous la lumière : talon plus court')
    return [B.Body(f'{name} talon {_num(h)}', [B.Slab(0.0, h, [B.rounded_rect(L - lh, -W / 2, L, W / 2)]),
                                               B.Slab(h, h + e, top)], BLACK)]


def build_step_block(v) -> list:
    """Cale étagée : profil des marches (X, Z) extrudé sur la largeur en Y, la plus haute marche au bord
    X = 0 ; posée par sa matrice (profil dans le plan local XY, extrusion en Z local)."""
    n, h, s, W = int(v['steps']), float(v['step_height']), float(v['step_depth']), float(v['width'])
    _need(n >= 1 and h > 0 and s > 0 and W > 0, 'dimensions positives')
    L = n * s
    pts = [(0.0, 0.0), (L, 0.0)]
    for i in range(1, n + 1):
        pts += [(L - (i - 1) * s, i * h), (L - i * s, i * h)]
    pts = [q for k, q in enumerate(pts) if k == 0 or q != pts[k - 1]]
    if pts[-1] == pts[0]:
        pts.pop()
    body = B.Body(f'Cale etagee {n}x{_num(h)}x{_num(s)} W{_num(W)}', [B.Slab(0.0, W, [B.Poly(pts)])], BLACK)
    body.matrix = B.placement((0.0, W, 0.0), (0.0, -1.0, 0.0), (1.0, 0.0, 0.0))   # y local → Z, z local → -Y
    return [body]


def build_soft_jaw(v) -> list:
    """Mors doux couché : X = longueur, Y = hauteur, Z = épaisseur (dos contre le mors de l'étau en Z = 0,
    face de serrage en haut) ; deux trous lamés côté serrage ; épaulement au bord haut de la face de serrage
    (profondeur et hauteur ; 0 : sans)."""
    L, H, e, size = float(v['length']), float(v['height']), float(v['thickness']), v['size']
    sp, hy = float(v['spacing']), float(v['hole_y'])
    p, q = float(v['step_depth']), float(v['step_height'])
    _need(L > 0 and H > 0 and e > 0, 'dimensions positives')
    _need(size in COUNTERBORE, f'taille inconnue : {size}')
    _need((p > 0) == (q > 0), 'épaulement : profondeur et hauteur, ou aucune')
    _need(p < e and q < H, 'épaulement plus grand que le mors')
    prof = _hole_profile('lamage', size, e)
    rmax = max(c.r for _z0, _z1, c in prof)
    xs = [L / 2 - sp / 2, L / 2 + sp / 2]
    _need(sp > 2 * rmax + 0.2, 'trous qui se touchent (entraxe)')
    _need(xs[0] - rmax >= 0.2, 'entraxe plus grand que le mors')
    for z0, z1, c in prof:                                       # chaque trou dans la matière de sa tranche
        top = H - q if p > 0 and z1 > e - p + B.EPS else H
        _need(c.r + 0.2 <= hy <= top - c.r - 0.2, 'trous hors du mors (hauteur des trous)')
    name = f'Mors doux {_num(L)}x{_num(H)}x{_num(e)} {size} entraxe {_num(sp)}'
    if p > 0:
        name += f' epaulement {_num(p)}x{_num(q)}'
        slabs = [B.Slab(0.0, e - p, [B.rounded_rect(0, 0, L, H)]), B.Slab(e - p, e, [B.rounded_rect(0, 0, L, H - q)])]
    else:
        slabs = [B.Slab(0.0, e, [B.rounded_rect(0, 0, L, H)])]
    body = B.cut(B.Body(name, slabs, ALU), *sorted({z for z0, z1, _c in prof for z in (z0, z1)}))
    for sl in body.slabs:
        for z0, z1, c in prof:
            if sl.z0 >= z0 - B.EPS and sl.z1 <= z1 + B.EPS:
                sl.loops += [B.Circle(x, hy, c.r) for x in xs]
    return [body]


def build_t_nut(v) -> list:
    """Écrou pour rainure en T : tête large en bas (dans la rainure), tenon à la largeur de la rainure dessus,
    même longueur (X), taraudage traversant au diamètre de perçage."""
    a, e, k, h, L, size = (float(v['a']), float(v['e']), float(v['k']), float(v['h']), float(v['length']),
                           v['size'])
    _need(size in PITCH, f'taille inconnue : {size}')
    _need(0 < a < e and 0 < k < h and L > 0, 'largeurs et hauteurs')
    r = (float(size[1:]) - PITCH[size]) / 2
    _need(r + 0.5 <= a / 2 and 2 * r + 1.0 <= L, 'taraudage plus large que le tenon')
    hole = B.Circle(0, 0, r)
    slabs = [B.Slab(0.0, k, [B.rounded_rect(-L / 2, -e / 2, L / 2, e / 2), hole]),
             B.Slab(k, h, [B.rounded_rect(-L / 2, -a / 2, L / 2, a / 2), hole])]
    return [B.Body(f'Ecrou T {_num(a)} {size}', slabs, STEEL)]


def build_stud(v) -> list:
    """Goujon de bridage : tige au diamètre nominal, chanfreinée aux deux bouts (filets non représentés),
    debout sur Z."""
    size, L = v['size'], float(v['length'])
    _need(size in PITCH, f'taille inconnue : {size}')
    d = float(size[1:])
    _need(L >= 2 * d, 'goujon plus court que deux diamètres')
    c = min(PITCH[size], L / 4)
    prof = [(0.0, d / 2 - c), (c, d / 2), (L - c, d / 2), (L, d / 2 - c)]
    return [B.revolve(prof, f'Goujon {size}x{_num(L)}', STEEL)]


def build_v_block(v) -> list:
    """Vé de bridage : bloc de profil constant, le vé ouvert en haut sur toute la longueur (Y), une gorge
    au fond du vé au besoin ; dessous à Z = 0, centré en X et Y."""
    L, W, H = float(v['length']), float(v['width']), float(v['height'])
    angle, b, g, gd = float(v['angle']), float(v['opening']), float(v['relief']), float(v['relief_depth'])
    _need(L > 0 and W > 0 and H > 0, 'dimensions positives')
    _need(0 < b <= W - 4.0, 'ouverture du vé : au moins 2 mm de bord de chaque côté')
    t = math.tan(math.radians(angle / 2.0))
    depth = b / 2.0 / t                                          # profondeur du vé jusqu'à sa pointe
    _need(0 <= g < b, 'gorge plus large que le vé')
    y_g = H - depth + g / 2.0 / t                                # le vé rencontre la gorge
    bottom = H - depth - (gd if g > 0 else 0.0)
    _need(bottom >= 3.0, 'vé trop profond : au moins 3 mm de matière dessous')
    pts = [(-W / 2, 0.0), (W / 2, 0.0), (W / 2, H), (b / 2, H)]
    if g > 0:
        _need(gd > 0, 'profondeur de gorge')
        pts += [(g / 2, y_g), (g / 2, bottom), (-g / 2, bottom), (-g / 2, y_g)]
    else:
        pts += [(0.0, H - depth)]
    pts += [(-b / 2, H), (-W / 2, H)]
    body = B.Body(f'Ve {_num(angle)} {_num(L)}x{_num(W)}x{_num(H)}', [B.Slab(0.0, L, [B.Poly(pts)])], STEEL)
    body.matrix = B.placement((0.0, -L / 2, 0.0), (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0))   # profil X-Z, long de Y
    return [body]


def build_t_slot_plate(v) -> list:
    """Plateau à rainures en T (ISO 299) : bloc de profil constant, n rainures ouvertes dessus sur toute la
    longueur (Y), à l'entraxe donné et centrées en X ; dessous à Z = 0, centré en X et Y."""
    L, W, H = float(v['length']), float(v['width']), float(v['height'])
    n, p = int(v['n']), float(v['pitch'])
    a, b, c, h = float(v['a']), float(v['b']), float(v['c']), float(v['h'])
    _need(L > 0 and W > 0 and H > 0 and a > 0 and c > 0, 'dimensions positives')
    _need(n >= 1, 'au moins une rainure')
    _need(b > a, 'tête plus large que la rainure')
    _need(c < h, 'tête moins haute que la rainure')
    _need(h <= H - 5.0, 'rainure trop profonde : au moins 5 mm de matière dessous')
    _need(n == 1 or p >= b + 5.0, 'rainures qui se touchent : entraxe d\'au moins la tête + 5 mm')
    _need((n - 1) * p / 2.0 + b / 2.0 + 5.0 <= W / 2.0, 'plateau trop étroit pour les rainures (5 mm de bord)')
    pts = [(-W / 2, 0.0), (W / 2, 0.0), (W / 2, H)]
    neck, foot = H - (h - c), H - h
    for i in reversed(range(n)):                                 # le dessus, de droite à gauche
        x = (i - (n - 1) / 2.0) * p
        pts += [(x + a / 2, H), (x + a / 2, neck), (x + b / 2, neck), (x + b / 2, foot),
                (x - b / 2, foot), (x - b / 2, neck), (x - a / 2, neck), (x - a / 2, H)]
    pts += [(-W / 2, H)]
    body = B.Body(f'Plateau rainures {n}x{_num(a)} {_num(L)}x{_num(W)}x{_num(H)}', [B.Slab(0.0, L, [B.Poly(pts)])],
                  STEEL)
    body.matrix = B.placement((0.0, -L / 2, 0.0), (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0))   # profil X-Z, long de Y
    return [body]


def build_taper_wedge(v) -> list:
    """Cale pentée : bloc de profil constant, le dessus en pente de la hauteur h1 (bord X bas) à h2 (bord X
    haut), long de Y ; dessous à Z = 0, centré en X et Y."""
    L, W, h1, h2 = float(v['length']), float(v['width']), float(v['h1']), float(v['h2'])
    _need(L > 0 and W > 0, 'dimensions positives')
    _need(h1 >= 0.5, 'bout mince : 0,5 mm au moins')
    _need(h2 > h1, 'bout épais plus haut que le bout mince')
    pts = [(-W / 2, 0.0), (W / 2, 0.0), (W / 2, h1), (-W / 2, h2)]          # X du profil : -X de la pièce
    body = B.Body(f'Cale pentee {_num(L)}x{_num(W)} {_num(h1)}-{_num(h2)}', [B.Slab(0.0, L, [B.Poly(pts)])], STEEL)
    body.matrix = B.placement((0.0, -L / 2, 0.0), (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0))   # profil X-Z, long de Y
    return [body]


def _taper_name(v) -> str:
    angle = math.degrees(math.atan2(float(v['h2']) - float(v['h1']), float(v['width'])))
    return f'Cale_pentee_{_num(v["length"])}x{_num(v["width"])}_h{_num(v["h1"])}-{_num(v["h2"])}_{_num(round(angle, 2))}deg'


def _rect_gap(cx: float, cy: float, x0: float, y0: float, x1: float, y1: float) -> float:
    """Distance du point au rectangle (0 dedans)."""
    return math.hypot(max(x0 - cx, 0.0, cx - x1), max(y0 - cy, 0.0, cy - y1))


def build_mould_plate(v) -> list:
    """Plaque de moule : quatre alésages de guidage aux coins (un décalé en X : un seul sens de montage),
    lamés dessus pour les collerettes au besoin, une empreinte en poche au milieu au besoin ; dessous à Z = 0,
    coin à l'origine."""
    L, W, T = float(v['length']), float(v['width']), float(v['thickness'])
    D, m, off = float(v['bore']), float(v['inset']), float(v['offset'])
    D2, h = float(v['counterbore']), float(v['counterbore_depth'])
    cl, cw, cd, rc = float(v['cavity_length']), float(v['cavity_width']), float(v['cavity_depth']), float(v['cavity_corner'])
    _need(L > 0 and W > 0 and T > 0 and D > 0, 'dimensions positives')
    lamage = D2 > 0
    cavity = cl > 0 and cw > 0 and cd > 0
    _need(not lamage or (D2 > D and 0 < h < T), 'lamage plus large que l\'alésage, moins profond que la plaque')
    _need(not cavity or cd < T, 'empreinte moins profonde que la plaque')
    r = (D2 if lamage else D) / 2.0
    gap = 1.0                                                    # matière gardée autour des alésages
    centres = [(m, m), (L - m, m), (L - m, W - m), (m + off, W - m)]
    for x, y in centres:
        _need(r + gap <= x <= L - r - gap and r + gap <= y <= W - r - gap, 'alésage trop près du bord')
    _need(min(math.dist(a, b) for i, a in enumerate(centres) for b in centres[i + 1:]) > 2 * r + gap,
          'alésages qui se touchent')
    box = ((L - cl) / 2, (W - cw) / 2, (L + cl) / 2, (W + cw) / 2)
    if cavity:
        _need(cl < L - 2 * gap and cw < W - 2 * gap, 'empreinte plus grande que la plaque')
        _need(all(_rect_gap(x, y, *box) >= r + gap for x, y in centres), 'empreinte qui touche un alésage')
    outer = B.rounded_rect(0, 0, L, W)
    levels = sorted({0.0, T} | ({T - h} if lamage else set()) | ({T - cd} if cavity else set()))
    slabs = []
    for z0, z1 in zip(levels, levels[1:]):
        loops = [outer]
        wide = lamage and z0 >= T - h - B.EPS
        loops += [B.Circle(x, y, (D2 if wide else D) / 2.0) for x, y in centres]
        if cavity and z0 >= T - cd - B.EPS:
            loops.append(B.rounded_rect(*box, max(0.0, min(rc, cl / 2 - B.EPS, cw / 2 - B.EPS))))
        slabs.append(B.Slab(z0, z1, loops))
    return [B.Body(f'Plaque de moule {_num(L)}x{_num(W)}x{_num(T)}', slabs, STEEL)]


# --- familles ---------------------------------------------------------------------------------------------
def _plate_name(v) -> str:
    n = f'Plaque_{_num(v["length"])}x{_num(v["width"])}x{_num(v["thickness"])}_r{_num(v["corner"])}_{v["pattern"]}'
    if v['pattern'] != 'aucun':
        n += f'_{v["hole"]}_{v["size"]}_m{_num(v["margin"])}'
    if v['pattern'] == 'grille':
        n += f'_{int(v["nx"])}x{int(v["ny"])}'
    return n


def _sizes(table) -> tuple:
    return tuple(table)


def _screw_family(key, label, std, table, build, lo_hi, default='M6', note=''):
    def name(v):
        return f'{label.split(" (")[0].replace(" ", "_")}_{std.replace(" ", "")}_{v["size"]}x{_num(v["length"])}'

    def series():
        return [{'size': s, 'length': L} for s in table for L in _lengths(*lo_hi(s))]
    return Family(key, label, 'Visserie', std, [Param('size', 'Taille', 'choice', default, _sizes(table)),
                                                 Param('length', 'Longueur', 'float', 20.0, (), 2.0, 300.0)],
                  build, name, note, series)


def _lo_hi_4762(s):
    return ISO4762[s][4], ISO4762[s][5]


def _lo_hi_generic(s):
    d = float(s[1:])
    return max(4, d), min(200, 12 * d)


FAMILIES: dict = {}


def _add(f: Family) -> None:
    FAMILIES[f.key] = f


_add(_screw_family('chc', 'Vis CHC (tête cylindrique six pans creux)', 'ISO 4762', ISO4762, build_chc, _lo_hi_4762))
_add(_screw_family('h', 'Vis H (tête hexagonale)', 'ISO 4017', ISO4017, build_h, _lo_hi_generic))
_add(_screw_family('fhc', 'Vis FHC (tête fraisée six pans creux)', 'ISO 10642', ISO10642, build_fhc,
                   lambda s: (max(6, float(s[1:]) * 1.5), min(100, 10 * float(s[1:]))),
                   note='Longueur hors tout, tête comprise ; dessus de la tête en Z = 0'))
_add(_screw_family('bhc', 'Vis BHC (tête bombée six pans creux)', 'ISO 7380', ISO7380, build_bhc,
                   lambda s: (max(4, float(s[1:])), min(60, 6 * float(s[1:])))))
_add(_screw_family('sthc', 'Vis STHC (sans tête, bout plat)', 'ISO 4026', ISO4026, build_sthc,
                   lambda s: (max(3, float(s[1:])), min(40, 4 * float(s[1:]))),
                   note='Dessus en Z = 0'))
_add(Family('ecrou', 'Écrou H', 'Visserie', 'ISO 4032', [Param('size', 'Taille', 'choice', 'M6', _sizes(ISO4032))],
            build_nut, lambda v: f'Ecrou_H_ISO4032_{v["size"]}', 'Trou au diamètre nominal (filet non représenté)',
            lambda: [{'size': s} for s in ISO4032]))
_add(Family('rondelle', 'Rondelle plate', 'Visserie', 'ISO 7089',
            [Param('size', 'Taille', 'choice', 'M6', _sizes(ISO7089))], _washer(ISO7089, 'ISO 7089'),
            lambda v: f'Rondelle_ISO7089_{v["size"]}', '', lambda: [{'size': s} for s in ISO7089]))
_add(Family('rondelle_large', 'Rondelle large', 'Visserie', 'ISO 7093-1',
            [Param('size', 'Taille', 'choice', 'M6', _sizes(ISO7093))], _washer(ISO7093, 'ISO 7093'),
            lambda v: f'Rondelle_large_ISO7093_{v["size"]}', '', lambda: [{'size': s} for s in ISO7093]))
_add(Family('goupille', 'Goupille cylindrique', 'Visserie', 'ISO 2338',
            [Param('d', 'Diamètre', 'choice', 6.0, (1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 16.0, 20.0)),
             Param('length', 'Longueur', 'float', 20.0, (), 2.0, 200.0)],
            build_pin, lambda v: f'Goupille_ISO2338_{_num(v["d"])}x{_num(v["length"])}', 'Chanfreins 0,12 d',
            lambda: [{'d': d, 'length': L} for d in (2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0)
                     for L in _lengths(2 * d, 10 * d)]))
_add(Family('roulement', 'Roulement rigide à billes', 'Transmission', 'ISO 15 (série 6)',
            [Param('ref', 'Référence', 'choice', '608', tuple(BEARINGS))], build_bearing,
            lambda v: f'Roulement_{v["ref"]}', 'Une seule pièce : bagues et flasques', lambda: [{'ref': r} for r in BEARINGS]))
_add(Family('clavette', 'Clavette parallèle forme A', 'Transmission', 'DIN 6885',
            [Param('size', 'b x h', 'choice', '6x6', tuple(DIN6885)), Param('length', 'Longueur', 'float', 25.0, (), 3, 400)],
            build_key, lambda v: f'Clavette_DIN6885A_{v["size"]}x{_num(v["length"])}'))
_add(Family('engrenage', 'Roue dentée droite', 'Transmission', 'développante 20°',
            [Param('module', 'Module', 'choice', 1.0, (0.5, 0.8, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0)),
             Param('teeth', 'Dents', 'int', 30, (), 8, 200, ''), Param('width', 'Largeur', 'float', 10.0, (), 1, 200),
             Param('bore', 'Alésage', 'float', 8.0, (), 0, 400)],
            build_gear, lambda v: f'Roue_m{_num(v["module"])}_z{int(v["teeth"])}_b{_num(v["width"])}_al{_num(v["bore"])}',
            'Flancs en facettes (développante), pied en rayon droit'))
_add(Family('barre', 'Barre, tube, profilé', 'Brut', '',
            [Param('shape', 'Forme', 'choice', 'rond', ('rond', 'tube', 'carre', 'plat', 'six_pans', 'tube_carre',
                                                         'corniere', 'u')),
             Param('a', 'Diamètre ou côté a', 'float', 20.0, (), 0.5, 1000),
             Param('b', 'Côté b', 'float', 10.0, (), 0.0, 1000), Param('e', 'Épaisseur', 'float', 2.0, (), 0.0, 100),
             Param('length', 'Longueur', 'float', 100.0, (), 0.5, 6000)],
            build_bar, lambda v: build_bar(v)[0].name.replace(' ', '_'), 'Debout sur Z (longueur en hauteur)'))
_add(Family('plaque', 'Plaque percée', 'Brut', '',
            [Param('length', 'Longueur', 'float', 100.0, (), 1, 3000), Param('width', 'Largeur', 'float', 60.0, (), 1, 3000),
             Param('thickness', 'Épaisseur', 'float', 10.0, (), 0.5, 500),
             Param('corner', 'Rayon des coins', 'float', 0.0, (), 0, 500),
             Param('pattern', 'Trous', 'choice', 'coins', ('aucun', 'coins', 'grille', 'centre')),
             Param('hole', 'Type de trou', 'choice', 'lamage', ('passage', 'lamage', 'fraisure', 'taraude')),
             Param('size', 'Vis', 'choice', 'M6', tuple(k for k in ISO10642 if k in COUNTERBORE)),
             Param('margin', 'Marge des trous', 'float', 10.0, (), 0, 1000),
             Param('nx', 'Trous en X (grille)', 'int', 3, (), 1, 50, ''), Param('ny', 'Trous en Y (grille)', 'int', 2, (), 1, 50, '')],
            build_plate, _plate_name,
            'Lamage pour vis CHC, fraisure 90° pour vis FHC, taraudage au diamètre de perçage'))
_add(Family('entretoise', 'Entretoise taraudée', 'Brut', '',
            [Param('shape', 'Forme', 'choice', 'six_pans', ('six_pans', 'ronde')),
             Param('size', 'Taraudage', 'choice', 'M4', ('M2', 'M2.5', 'M3', 'M4', 'M5', 'M6', 'M8')),
             Param('D', 'Diamètre (ronde)', 'float', 8.0, (), 1, 100), Param('length', 'Longueur', 'float', 20.0, (), 1, 300)],
            build_spacer, lambda v: build_spacer(v)[0].name.replace(' ', '_'), 'Traversante, au diamètre de perçage'))
_add(Family('bague', 'Bague lisse', 'Brut', '',
            [Param('d', 'Alésage', 'float', 10.0, (), 0.5, 1000), Param('D', 'Diamètre extérieur', 'float', 16.0, (), 1, 1000),
             Param('length', 'Longueur', 'float', 12.0, (), 0.5, 1000), Param('chamfer', 'Chanfrein', 'float', 0.5, (), 0, 20)],
            build_bush, lambda v: f'Bague_{_num(v["d"])}x{_num(v["D"])}x{_num(v["length"])}_ch{_num(v["chamfer"])}'))
_add(Family('bride_ronde', 'Bride ronde', 'Brut', '',
            [Param('D', 'Diamètre extérieur', 'float', 120.0, (), 5, 2000), Param('thickness', 'Épaisseur', 'float', 15.0, (), 0.5, 500),
             Param('bore', 'Alésage (0 : sans)', 'float', 40.0, (), 0, 2000),
             Param('n', 'Nombre de trous', 'int', 6, (), 0, 72, ''),
             Param('pcd', 'Cercle des trous (Ø)', 'float', 90.0, (), 1, 2000),
             Param('hole', 'Type de trou', 'choice', 'passage', ('passage', 'lamage', 'fraisure', 'taraude')),
             Param('size', 'Vis', 'choice', 'M8', tuple(k for k in ISO10642 if k in COUNTERBORE)),
             Param('start', 'Angle du premier trou', 'float', 0.0, (), -360, 360, '°'),
             Param('spigot', 'Centrage : Ø (0 : sans)', 'float', 0.0, (), 0, 2000),
             Param('spigot_height', 'Centrage : hauteur', 'float', 3.0, (), 0, 200)],
            build_flange, lambda v: (f'Bride_ronde_D{_num(v["D"])}x{_num(v["thickness"])}_a{_num(v["bore"])}'
                                     f'_{int(v["n"])}x{v["hole"]}_{v["size"]}_c{_num(v["pcd"])}_{_num(v["start"])}deg'
                                     + (f'_centrage{_num(v["spigot"])}x{_num(v["spigot_height"])}'
                                        if float(v["spigot"]) > 0 and float(v["spigot_height"]) > 0 else '')),
            'Trous sur un cercle, le premier à l\'angle donné depuis +X ; lamage ou fraisure côté dessus, centrage '
            'en saillie dessus'))
_add(Family('ejecteur', 'Éjecteur à tête cylindrique', 'Moule', 'dimensions à donner',
            [Param('d1', 'Diamètre de tige', 'float', 4.0, (), 0.5, 40), Param('length', 'Longueur', 'float', 100.0, (), 5, 1000),
             Param('d2', 'Diamètre de tête', 'float', 8.0, (), 1, 60), Param('k', 'Hauteur de tête', 'float', 3.0, (), 0.5, 20)],
            build_ejector, lambda v: f'Ejecteur_{_num(v["d1"])}x{_num(v["length"])}_tete{_num(v["d2"])}x{_num(v["k"])}',
            'Tête en haut (Z = longueur)'))
_add(Family('colonne', 'Colonne de guidage à collerette', 'Moule', 'dimensions à donner',
            [Param('d', 'Diamètre guidé', 'float', 16.0, (), 2, 200), Param('length', 'Longueur', 'float', 80.0, (), 5, 1000),
             Param('D', 'Diamètre de collerette', 'float', 24.0, (), 3, 300),
             Param('h', 'Hauteur de collerette', 'float', 6.0, (), 0.5, 100)],
            build_pillar, lambda v: f'Colonne_{_num(v["d"])}x{_num(v["length"])}_collerette{_num(v["D"])}x{_num(v["h"])}'))
_add(Family('douille', 'Douille de guidage à collerette', 'Moule', 'dimensions à donner',
            [Param('d', 'Alésage', 'float', 16.0, (), 2, 200), Param('D', 'Diamètre extérieur', 'float', 25.0, (), 3, 300),
             Param('length', 'Longueur', 'float', 40.0, (), 3, 500), Param('D2', 'Diamètre de collerette', 'float', 30.0, (), 4, 400),
             Param('h', 'Hauteur de collerette', 'float', 5.0, (), 0.5, 100)],
            build_guide_bush, lambda v: (f'Douille_{_num(v["d"])}x{_num(v["D"])}x{_num(v["length"])}'
                                         f'_collerette{_num(v["D2"])}x{_num(v["h"])}')))
_add(Family('bague_centrage', 'Bague de centrage', 'Moule', 'dimensions à donner',
            [Param('D', 'Diamètre extérieur', 'float', 100.0, (), 10, 500), Param('d', 'Alésage', 'float', 36.0, (), 2, 400),
             Param('h', 'Hauteur', 'float', 12.0, (), 2, 100)],
            build_locating_ring, lambda v: f'Bague_centrage_D{_num(v["D"])}_d{_num(v["d"])}_h{_num(v["h"])}'))
_add(Family('plaque_moule', 'Plaque de moule', 'Moule', 'dimensions à donner',
            [Param('length', 'Longueur', 'float', 196.0, (), 20, 2000), Param('width', 'Largeur', 'float', 196.0, (), 20, 2000),
             Param('thickness', 'Épaisseur', 'float', 36.0, (), 3, 500),
             Param('bore', 'Alésage de guidage', 'float', 20.0, (), 2, 200),
             Param('inset', 'Entraxe au bord', 'float', 22.0, (), 2, 500),
             Param('offset', 'Décalage d\'un alésage', 'float', 2.0, (), -100, 100),
             Param('counterbore', 'Lamage (0 : sans)', 'float', 26.0, (), 0, 300),
             Param('counterbore_depth', 'Profondeur du lamage', 'float', 5.0, (), 0, 500),
             Param('cavity_length', 'Empreinte : longueur (0 : sans)', 'float', 80.0, (), 0, 2000),
             Param('cavity_width', 'Empreinte : largeur', 'float', 60.0, (), 0, 2000),
             Param('cavity_depth', 'Empreinte : profondeur', 'float', 15.0, (), 0, 500),
             Param('cavity_corner', 'Empreinte : rayon des coins', 'float', 5.0, (), 0, 500)],
            build_mould_plate, lambda v: (f'Plaque_moule_{_num(v["length"])}x{_num(v["width"])}x{_num(v["thickness"])}'
                                          f'_D{_num(v["bore"])}_m{_num(v["inset"])}'),
            'Coin à l\'origine ; un alésage décalé en X (un seul sens de montage) ; alésages pour douilles ou '
            'colonnes (Pièce dans ce trou)'))


_add(Family('bride', 'Bride de serrage', 'Bridage', 'dimensions à donner',
            [Param('length', 'Longueur', 'float', 100.0, (), 10, 1000), Param('width', 'Largeur', 'float', 30.0, (), 5, 300),
             Param('thickness', 'Épaisseur', 'float', 15.0, (), 2, 200),
             Param('size', 'Vis', 'choice', 'M10', ('M6', 'M8', 'M10', 'M12', 'M16')),
             Param('slot', 'Longueur de la lumière', 'float', 40.0, (), 2, 1000),
             Param('heel', 'Hauteur du talon', 'float', 0.0, (), 0, 300),
             Param('heel_length', 'Longueur du talon', 'float', 15.0, (), 0, 500)],
            build_strap_clamp, lambda v: (f'Bride_{_num(v["length"])}x{_num(v["width"])}x{_num(v["thickness"])}_'
                                          f'{v["size"]}_lumiere{_num(v["slot"])}'
                                          + (f'_talon{_num(v["heel"])}x{_num(v["heel_length"])}'
                                             if float(v['heel']) > 0 else '')),
            'Lumière au milieu ; talon dessous au bout (hauteur 0 : bride plate, avec une cale étagée)'))
_add(Family('cale_etagee', 'Cale étagée', 'Bridage', 'dimensions à donner',
            [Param('steps', 'Marches', 'int', 3, (), 1, 20, ''), Param('step_height', 'Hauteur de marche', 'float', 10.0, (), 1, 200),
             Param('step_depth', 'Profondeur de marche', 'float', 15.0, (), 1, 200),
             Param('width', 'Largeur', 'float', 40.0, (), 2, 500)],
            build_step_block, lambda v: build_step_block(v)[0].name.replace(' ', '_'), 'La plus haute marche en X = 0'))
_add(Family('mors_doux', 'Mors doux', 'Bridage', 'dimensions à donner',
            [Param('length', 'Longueur', 'float', 150.0, (), 20, 1000), Param('height', 'Hauteur', 'float', 40.0, (), 5, 300),
             Param('thickness', 'Épaisseur', 'float', 20.0, (), 3, 200),
             Param('size', 'Vis', 'choice', 'M8', tuple(k for k in ('M4', 'M5', 'M6', 'M8', 'M10', 'M12') if k in COUNTERBORE)),
             Param('spacing', 'Entraxe des trous', 'float', 100.0, (), 1, 1000),
             Param('hole_y', 'Hauteur des trous', 'float', 20.0, (), 1, 300),
             Param('step_depth', 'Profondeur de l\'épaulement', 'float', 0.0, (), 0, 200),
             Param('step_height', 'Hauteur de l\'épaulement', 'float', 0.0, (), 0, 300)],
            build_soft_jaw, lambda v: (build_soft_jaw(v)[0].name.replace(' ', '_') + f'_y{_num(v["hole_y"])}'),
            'Couché : dos en Z = 0, face de serrage en haut, lamages côté serrage ; épaulement au bord haut'))
_add(Family('goujon', 'Goujon de bridage', 'Bridage', 'dimensions à donner',
            [Param('size', 'Taille', 'choice', 'M12', ('M6', 'M8', 'M10', 'M12', 'M16', 'M20')),
             Param('length', 'Longueur', 'float', 80.0, (), 10, 500)],
            build_stud, lambda v: f'Goujon_{v["size"]}x{_num(v["length"])}',
            'Au diamètre nominal, filets non représentés'))
_add(Family('ecrou_t', 'Écrou pour rainure en T', 'Bridage', 'dimensions à donner',
            [Param('a', 'Largeur de rainure', 'float', 14.0, (), 4, 60), Param('e', 'Largeur de tête', 'float', 22.0, (), 5, 100),
             Param('k', 'Hauteur de tête', 'float', 8.0, (), 1, 60), Param('h', 'Hauteur totale', 'float', 16.0, (), 2, 100),
             Param('length', 'Longueur', 'float', 22.0, (), 3, 200),
             Param('size', 'Taraudage', 'choice', 'M12', ('M4', 'M5', 'M6', 'M8', 'M10', 'M12', 'M16', 'M20'))],
            build_t_nut, lambda v: (f'Ecrou_T_a{_num(v["a"])}_{v["size"]}_e{_num(v["e"])}_k{_num(v["k"])}'
                                    f'_h{_num(v["h"])}_L{_num(v["length"])}'),
            'Tête dans la rainure (en bas), taraudage au diamètre de perçage'))
_add(Family('ve', 'Vé de bridage', 'Bridage', 'dimensions à donner',
            [Param('length', 'Longueur', 'float', 60.0, (), 5, 1000), Param('width', 'Largeur', 'float', 60.0, (), 10, 500),
             Param('height', 'Hauteur', 'float', 40.0, (), 5, 500),
             Param('angle', 'Angle du vé', 'choice', 90.0, (90.0, 120.0)),
             Param('opening', 'Ouverture du vé', 'float', 40.0, (), 2, 500),
             Param('relief', 'Largeur de gorge (0 : sans)', 'float', 4.0, (), 0, 100),
             Param('relief_depth', 'Profondeur de gorge', 'float', 3.0, (), 0, 100)],
            build_v_block, lambda v: (f'Ve_{_num(v["angle"])}_{_num(v["length"])}x{_num(v["width"])}x{_num(v["height"])}'
                                      f'_o{_num(v["opening"])}'),
            'Vé ouvert en haut, sur toute la longueur ; gorge au fond pour les arêtes vives'))
_add(Family('plateau_rainures', 'Plateau à rainures en T', 'Bridage', 'rainures ISO 299',
            [Param('length', 'Longueur', 'float', 300.0, (), 10, 3000), Param('width', 'Largeur', 'float', 200.0, (), 10, 2000),
             Param('height', 'Hauteur', 'float', 50.0, (), 5, 500),
             Param('n', 'Nombre de rainures', 'int', 3, (), 1, 30, ''),
             Param('pitch', 'Entraxe des rainures', 'float', 63.0, (), 5, 1000),
             Param('a', 'Largeur de rainure', 'float', 14.0, (), 4, 60), Param('b', 'Largeur de tête', 'float', 23.0, (), 5, 100),
             Param('c', 'Hauteur de tête', 'float', 9.0, (), 1, 60), Param('h', 'Profondeur totale', 'float', 23.0, (), 2, 200)],
            build_t_slot_plate, lambda v: (f'Plateau_rainures_{int(v["n"])}x{_num(v["a"])}_p{_num(v["pitch"])}'
                                           f'_{_num(v["length"])}x{_num(v["width"])}x{_num(v["height"])}'
                                           f'_b{_num(v["b"])}_c{_num(v["c"])}_h{_num(v["h"])}'),
            'Rainures ouvertes dessus sur toute la longueur, centrées ; l\'écrou en T par défaut y entre'))
_add(Family('cale_pentee', 'Cale pentée', 'Bridage', 'dimensions à donner',
            [Param('length', 'Longueur', 'float', 100.0, (), 2, 2000), Param('width', 'Largeur', 'float', 50.0, (), 2, 1000),
             Param('h1', 'Hauteur au bout mince', 'float', 5.0, (), 0.5, 500),
             Param('h2', 'Hauteur au bout épais', 'float', 15.0, (), 0.5, 500)],
            build_taper_wedge, _taper_name,
            'Pente le long de la largeur (X), du bout mince au bout épais ; l\'angle est dans le nom'))


CATEGORIES = ('Visserie', 'Transmission', 'Brut', 'Moule', 'Bridage')
#: libellés des choix (clé → texte montré)
CHOICE_LABELS = {'rond': 'Rond', 'tube': 'Tube', 'carre': 'Carré', 'plat': 'Plat', 'six_pans': 'Six pans',
                 'tube_carre': 'Tube carré', 'corniere': 'Cornière', 'u': 'U', 'ronde': 'Ronde', 'aucun': 'Aucun',
                 'coins': 'Aux quatre coins', 'grille': 'En grille', 'centre': 'Au centre', 'passage': 'Passage',
                 'lamage': 'Lamé (vis CHC)', 'fraisure': 'Fraisé 90° (vis FHC)', 'taraude': 'Taraudé'}


def defaults(key: str) -> dict:
    return {p.key: p.default for p in FAMILIES[key].params}


def values(key: str, **over) -> dict:
    """Valeurs par défaut de la famille, remplacées par `over` ; contrôlées."""
    f = FAMILIES[key]
    v = defaults(key)
    unknown = set(over) - set(v)
    if unknown:
        raise GenError(f'{f.label} : paramètre inconnu {", ".join(sorted(unknown))}')
    v.update(over)
    for p in f.params:
        x = v[p.key]
        if p.kind == 'choice':
            if x not in p.choices:
                raise GenError(f'{p.label} : {x} hors de la liste')
            continue
        try:
            n = float(x)
        except (TypeError, ValueError):
            raise GenError(f'{p.label} : {x} n\'est pas un nombre') from None
        if p.kind == 'int':
            if n != int(n):
                raise GenError(f'{p.label} : {x} n\'est pas un nombre entier')
            n = int(n)
        if not p.lo <= n <= p.hi:
            raise GenError(f'{p.label} : {x} hors de [{p.lo:g}, {p.hi:g}]')
        v[p.key] = n
    return v


def build(key: str, v: dict) -> list:
    """Les corps de la pièce (GenError si les valeurs ne vont pas)."""
    bodies = FAMILIES[key].build(v)
    for b in bodies:
        try:
            B.check(b)
        except B.BrepError as ex:
            raise GenError(str(ex)) from ex
    return bodies


def file_name(key: str, v: dict) -> str:
    return B._ascii(FAMILIES[key].name(v)).replace('/', '-').replace(' ', '_') or key


def folder_name(key: str) -> str:
    """Sous-dossier d'une gamme : « Vis_CHC_ISO4762 », « Roulement_rigide_a_billes_ISO15 »…"""
    f = FAMILIES[key]
    std = f.standard.split(' (')[0].replace(' ', '') if f.standard and f.standard[0].isupper() else ''
    return B._ascii(f'{f.label.split(" (")[0]} {std}'.strip()).replace(' ', '_').replace('/', '-') or key


def write(key: str, v: dict, path) -> str:
    """Le STEP de la pièce dans `path` (fichier)."""
    f = FAMILIES[key]
    return B.write(path, build(key, v), file_name(key, v), f'{f.label} {f.standard}'.strip())


def write_series(key: str, folder, progress=None) -> list:
    """Toute la gamme de la famille (tailles × longueurs courantes) dans `folder` ; rend les fichiers."""
    import pathlib

    from . import progress as PR
    f = FAMILIES[key]
    if f.series is None:
        raise GenError(f'{f.label} : pas de gamme')
    out = pathlib.Path(folder)
    out.mkdir(parents=True, exist_ok=True)
    done = []
    items = f.series()
    for i, over in enumerate(items):
        PR.step(i, len(items), 'Pièce {0} sur {1}')
        v = values(key, **over)
        done.append(write(key, v, out / f'{file_name(key, v)}.step'))
        if progress is not None and progress(i + 1, len(items)) is False:
            break
    return done
