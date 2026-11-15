"""Police monotrait intégrée « VD Géo » : linéale géométrique à gravure en un
passage (ligne médiane), toujours là sans police installée sur le poste.

Dessin **original**, construit à la règle et au compas pour VectorDrive :
cercles, arcs d'ellipse et droites seulement, aucun tracé repris d'une
police existante. Esprit des linéales géométriques des années 1920 : O et o
ronds, a et g à un seul étage, sommets pointus (A M N V W v w), S fait de
deux cercles reliés par leur tangente intérieure, chiffres tabulaires.

Unités comme les polices Gravotech et « VD Trait » : **hauteur des
capitales = 1**, origine sur la ligne de base au début de l'approche
gauche, y vers le haut. Hauteur d'x 0,70 ; ascendantes 1,06 ; jambages
-0,30 ; sommet du t 0,90. Les approches sont comprises dans l'avance.

Les courbes sont des arcs exacts (coniques de `geom.arc_conics`, comme les
arcs TypeEdit), jamais des polylignes ; chaque contour est un trait continu
de l'outil (levées de plume réduites : a, b, d, g, p, q en un trait…).

Description des glyphes : petit langage de commandes, compilé à la demande
en objets `geom` :

* ``M(x, y)`` pose l'outil ; ``L(x, y)`` droite jusqu'à (x, y) ;
* ``A(cx, cy, r, départ, balayage)`` arc de cercle (degrés, balayage
  positif = sens trigonométrique) ; ``E(cx, cy, rx, ry, départ, balayage)``
  arc d'ellipse (angle paramétrique).

Un trait est une liste de commandes ; un glyphe est (approche gauche,
approche droite, traits) — sa largeur vient de l'encombrement du dessin.
Les lettres accentuées sont composées à la volée (décomposition Unicode :
lettre de base + diacritiques au-dessus ou au-dessous, i et j sans point).

Aussi : l'alphabet grec (accents monotoniques composés ; sur les capitales,
le tonos à gauche), des flèches, des signes techniques (≤ ≥ ≠ ≈ ∞ √ ∠ ⊥ ∥
′ ″ № ℃), exposants, indices et fractions.

Crénage : la table `_KERN` (AV, To, LT, P., Vé…), calculée sur le dessin par
`outils/vdgeo_crenage.py` ; deux traits n'y sont jamais rapprochés à moins de
0,15 hauteur de capitale, rien après un chiffre ni une apostrophe.
"""
from __future__ import annotations

import functools
import math
import unicodedata

from .geom import Conic, Contour, Line, Path, arc_conics

NAME = 'VD Géo'
#: pas un fichier : la police est dans le code (repérée par ce chemin)
PATH = '<vectordrive:geo>'

XH, ASC, DSC = 0.70, 1.06, -0.30     # hauteur d'x, ascendantes, jambages
TT = 0.90                            # sommet du t
OV = 0.012                           # débordement optique des rondes
DOT = 0.07                           # point : petit trait vertical (i, j, ponctuation)
IDOT = 0.885                         # pied du point du i
MATH = 0.46                          # axe des signes + − = × ÷ < >
HY = 0.38                            # hauteur du trait d'union et des tirets
SPACE, THIN = 0.32, 0.16             # espace, espace fine
DIGIT = 0.72                         # avance des chiffres (tabulaires)
MISSING = 0.70                       # avance d'un caractère absent
ASCENT, DESCENT = 1.30, 0.35         # boîte des caractères, accents des capitales compris

# approches : fût droit, rond, diagonale, ouvert
SB, SR, SD, SO = 0.11, 0.085, 0.035, 0.06


# --- petit langage de commandes ---------------------------------------------------------

def M(x, y):
    return ('M', x, y)


def L(x, y):
    return ('L', x, y)


def A(cx, cy, r, a0, sweep):
    return ('A', cx, cy, r, a0, sweep)


def E(cx, cy, rx, ry, a0, sweep):
    return ('E', cx, cy, rx, ry, a0, sweep)


def _pt(cx, cy, r, a, ry=None):
    """Point d'angle a (degrés) sur le cercle (ou l'ellipse rx = r, ry)."""
    t = math.radians(a)
    return (cx + r * math.cos(t), cy + (r if ry is None else ry) * math.sin(t))


def _ccw(a, b):
    """Balayage trigonométrique de l'angle a à l'angle b, dans ]0, 360]."""
    return (b - a) % 360.0 or 360.0


def _cw(a, b):
    """Balayage horaire (négatif) de l'angle a à l'angle b."""
    return -((a - b) % 360.0 or 360.0)


def _tan2(c1, r1, ccw1, c2, r2, ccw2):
    """Tangente commune orientée, du cercle 1 parcouru dans le sens ccw1 au
    cercle 2 parcouru dans le sens ccw2 (rayon 0 : un simple point). Le trait
    passe sans angle de l'un à l'autre. Renvoie les angles (degrés) des deux
    points de contact."""
    dx, dy = c2[0] - c1[0], c2[1] - c1[1]
    d = math.hypot(dx, dy)
    ux, uy = dx / d, dy / d
    for e1 in (1, -1):
        for e2 in (1, -1):
            k = (e2 * r2 - e1 * r1) / d
            if abs(k) > 1:
                continue
            s = math.sqrt(1 - k * k)
            for sg in (1, -1):
                nx, ny = k * ux - sg * s * uy, k * uy + sg * s * ux
                t1 = (c1[0] - e1 * r1 * nx, c1[1] - e1 * r1 * ny)
                t2 = (c2[0] - e2 * r2 * nx, c2[1] - e2 * r2 * ny)
                wx, wy = t2[0] - t1[0], t2[1] - t1[1]
                ok = True
                for c, r, ccw, t in ((c1, r1, ccw1, t1), (c2, r2, ccw2, t2)):
                    if r > 0:
                        rx, ry = (t[0] - c[0]) / r, (t[1] - c[1]) / r
                        mx, my = (-ry, rx) if ccw else (ry, -rx)
                        ok = ok and mx * wx + my * wy > 0
                if ok:
                    return (math.degrees(math.atan2(t1[1] - c1[1], t1[0] - c1[0])) if r1 > 0 else 0.0,
                            math.degrees(math.atan2(t2[1] - c2[1], t2[0] - c2[0])) if r2 > 0 else 0.0)
    raise ValueError('pas de tangente commune')


def _xf(strokes, dx=0.0, dy=0.0, sx=1.0, sy=None):
    """Traits mis à l'échelle (sx, sy, symétries comprises) puis déplacés."""
    sy = sx if sy is None else sy
    out = []
    for s in strokes:
        t = []
        for c in s:
            if c[0] in 'ML':
                t.append((c[0], c[1] * sx + dx, c[2] * sy + dy))
                continue
            if c[0] == 'A':
                _, cx, cy, rx, a0, sw = c
                ry = rx
            else:
                _, cx, cy, rx, ry, a0, sw = c
            a = math.radians(a0)
            a1 = math.degrees(math.atan2(math.copysign(1, sy) * math.sin(a), math.copysign(1, sx) * math.cos(a)))
            sw1 = sw * math.copysign(1, sx) * math.copysign(1, sy)
            t.append(('E', cx * sx + dx, cy * sy + dy, rx * abs(sx), ry * abs(sy), a1, sw1))
        out.append(t)
    return out


def _s(cx, y0, y1, ru, rl, k, at=32.0, ab=212.0):
    """S géométrique : deux cercles (haut ru, bas rl) reliés par leur
    tangente intérieure, puis étirés de k en largeur (une affinité garde
    le contact). `at`, `ab` : angles des extrémités haute et basse."""
    cu, cl = (0.0, y1 - ru), (0.0, y0 + rl)
    tu, tl = _tan2(cu, ru, True, cl, rl, False)
    x, y = _pt(0.0, cl[1], rl, tl)
    return [E(cx, cu[1], ru * k, ru, at, _ccw(at, tu)), L(cx + x * k, y),
            E(cx, cl[1], rl * k, rl, tl, _cw(tl, ab))]


def _comma(x, y):
    """Virgule : un point (petit trait) prolongé d'une queue oblique."""
    return [M(x, y + DOT), L(x, y), L(x - 0.05, y - 0.13)]


# --- les glyphes ---------------------------------------------------------------------------

@functools.cache
def _table() -> dict:
    """{caractère: (approche gauche, approche droite, traits)} ; approche
    gauche None : chiffre tabulaire, centré dans l'avance DIGIT."""
    G = {}

    def g(ch, lsb, rsb, *strokes):
        G[ch] = (lsb, rsb, tuple(tuple(s) for s in strokes if s))

    # capitales -------------------------------------------------------------------------
    r = 0.5 + OV                                   # O : cercle de diamètre 1 + débordements
    g('A', SD, SD, [M(0, 0), L(.40, 1), L(.80, 0)], [M(.12, .30), L(.68, .30)])
    ym, ru, rl, xu, xl = .53, .235, .265, .29, .31
    g('B', SB, SR, [M(0, ym), L(0, 0), L(xl, 0), A(xl, rl, rl, -90, 180), L(xu, ym),
                    A(xu, ym + ru, ru, -90, 180), L(0, 1), L(0, ym), L(xu, ym)])
    g('C', SR, .05, [A(r, .5, r, 48, 264)])
    g('D', SB, SR, [M(0, 0), L(0, 1), L(.24, 1), A(.24, .5, .5, 90, -180), L(0, 0)])
    g('E', SB, .07, [M(.50, 1), L(0, 1), L(0, 0), L(.52, 0)], [M(0, .52), L(.44, .52)])
    g('F', SB, .06, [M(.50, 1), L(0, 1), L(0, 0)], [M(0, .52), L(.42, .52)])
    g('G', SR, SR, [A(r, .5, r, 48, 312), L(2 * r - .30, .5)])
    g('H', SB, SB, [M(0, 1), L(0, 0)], [M(.68, 1), L(.68, 0)], [M(0, .52), L(.68, .52)])
    g('I', SB, SB, [M(0, 1), L(0, 0)])
    g('J', .05, SB, [M(.46, 1), L(.46, .23 - OV), A(.23, .23 - OV, .23, 0, -165)])
    g('K', SB, SD, [M(0, 1), L(0, 0)], [M(.62, 1), L(0, .34)], [M(.20, .34 + .66 * .20 / .62), L(.64, 0)])
    g('L', SB, .04, [M(0, 1), L(0, 0), L(.48, 0)])
    g('M', .06, .06, [M(0, 0), L(.10, 1), L(.45, 0), L(.80, 1), L(.90, 0)])
    g('N', SB, SB, [M(0, 0), L(0, 1), L(.70, 0), L(.70, 1)])
    g('O', SR, SR, [A(r, .5, r, 90, 360)])
    bowl = [M(0, 0), L(0, 1), L(.30, 1), A(.30, .735, .265, 90, -180), L(0, .47)]
    g('P', SB, .06, bowl)
    g('Q', SR, SR, [A(r, .5, r, 90, 360)], [M(.66, .26), L(1.0, -.06)])
    g('R', SB, .04, bowl, [M(.30, .47), L(.60, 0)])
    g('S', .07, .07, _s(0, -OV, 1 + OV, .225, .245, 1.18))
    g('T', .03, .03, [M(0, 1), L(.62, 1)], [M(.31, 1), L(.31, 0)])
    g('U', .10, .10, [M(0, 1), L(0, .33 - OV), A(.33, .33 - OV, .33, 180, 180), L(.66, 1)])
    g('V', SD, SD, [M(0, 1), L(.37, 0), L(.74, 1)])
    g('W', SD, SD, [M(0, 1), L(.26, 0), L(.52, 1), L(.78, 0), L(1.04, 1)])
    g('X', SD, SD, [M(0, 1), L(.64, 0)], [M(0, 0), L(.64, 1)])
    g('Y', SD, SD, [M(0, 1), L(.35, .46), L(.70, 1)], [M(.35, .46), L(.35, 0)])
    g('Z', .05, .05, [M(0, 1), L(.62, 1), L(0, 0), L(.62, 0)])

    # minuscules ------------------------------------------------------------------------
    ro, cy = .36, .35                              # panse : cercle de la hauteur d'x
    rn = .27                                       # n, m, r, u : le fût, puis l'arche (rien n'est repassé)
    nc = XH + OV - rn                              # du fût (0,27 au plus) ; centre de l'arche du n
    g('a', SR, SB, [M(2 * ro, XH), L(2 * ro, cy), A(ro, cy, ro, 0, -360), L(2 * ro, 0)])
    g('b', SB, SR, [M(0, ASC), L(0, cy), A(ro, cy, ro, 180, 360), L(0, 0)])
    g('c', SR, .05, [A(ro, cy, ro, 45, 270)])
    g('d', SR, SB, [M(2 * ro, ASC), L(2 * ro, cy), A(ro, cy, ro, 0, -360), L(2 * ro, 0)])
    g('e', SR, .07, [M(0, cy), L(2 * ro, cy), A(ro, cy, ro, 0, 320)])
    rf = .20
    fhook = [M(.16, 0), L(.16, ASC - rf), A(.16 + rf, ASC - rf, rf, 180, -135)]
    g('f', .04, .02, fhook, [M(0, XH), L(.40, XH)])
    # ƒ (florin) : le f, son fût descendu sous la ligne et terminé par le même crochet, retourné ; d'un seul trait
    g('ƒ', .04, .02, [A(.16 - rf, DSC - OV + rf, rf, 225, 135), L(.16, ASC - rf),
                      A(.16 + rf, ASC - rf, rf, 180, -135)], [M(0, XH), L(.40, XH)])
    rgx, rgy = .30, .25
    g('g', SR, SB, [M(2 * ro, XH), L(2 * ro, cy), A(ro, cy, ro, 0, -360), L(2 * ro, DSC - OV + rgy),
                    E(2 * ro - rgx, DSC - OV + rgy, rgx, rgy, 0, -165)])
    g('h', SB, SB, [M(0, ASC), L(0, 0)], [M(0, nc), A(rn, nc, rn, 180, -180), L(2 * rn, 0)])
    g('i', SB, SB, [M(0, 0), L(0, XH)], [M(0, IDOT), L(0, IDOT + DOT)])
    rj = .16
    jtail = [M(0, XH), L(0, DSC - OV + rj), A(-rj, DSC - OV + rj, rj, 0, -150)]
    g('j', .02, SB, jtail, [M(0, IDOT), L(0, IDOT + DOT)])
    karm = ([M(.46, XH), L(0, .24)], [M(.16, .40), L(.48, 0)])
    g('k', SB, SD, [M(0, ASC), L(0, 0)], *karm)
    g('l', SB, SB, [M(0, ASC), L(0, 0)])
    rm = .22
    mc = XH + OV - rm
    g('m', SB, SB, [M(0, XH), L(0, 0)], [M(0, mc), A(rm, mc, rm, 180, -180), A(3 * rm, mc, rm, 180, -180),
                                         L(4 * rm, 0)], [M(2 * rm, mc), L(2 * rm, 0)])
    nstem, narch = [M(0, XH), L(0, 0)], [M(0, nc), A(rn, nc, rn, 180, -180)]
    g('n', SB, SB, nstem, narch + [L(2 * rn, 0)])
    g('o', SR, SR, [A(ro, cy, ro, 90, 360)])
    g('p', SB, SR, [M(0, XH), L(0, cy), A(ro, cy, ro, 180, 360), L(0, DSC)])
    g('q', SR, SB, [M(2 * ro, XH), L(2 * ro, cy), A(ro, cy, ro, 0, -360), L(2 * ro, DSC)])
    rr = .25
    g('r', SB, .02, [M(0, XH), L(0, 0)], [M(0, XH + OV - rr), A(rr, XH + OV - rr, rr, 180, -125)])
    g('s', .07, .07, _s(0, -OV, XH + OV, .165, .175, 1.32))
    g('t', .04, .04, [M(.16, TT), L(.16, 0)], [M(0, XH), L(.36, XH)])
    ubowl = [M(0, XH), L(0, rn - OV), A(rn, rn - OV, rn, 180, 180)]
    g('u', SB, SB, ubowl, [M(2 * rn, XH), L(2 * rn, 0)])
    g('v', SD, SD, [M(0, XH), L(.28, 0), L(.56, XH)])
    g('w', SD, SD, [M(0, XH), L(.20, 0), L(.40, XH), L(.60, 0), L(.80, XH)])
    g('x', SD, SD, [M(0, XH), L(.52, 0)], [M(0, 0), L(.52, XH)])
    g('y', SD, SD, [M(0, XH), L(.28, 0)], [M(.56, XH), L(.16, DSC)])
    g('z', .05, .05, [M(0, XH), L(.50, XH), L(0, 0), L(.50, 0)])

    # chiffres (tabulaires) --------------------------------------------------------------
    D = None
    g('0', D, D, [E(.27, .5, .27, .5 + OV, 90, 360)])
    g('1', D, D, [M(0, .80), L(.20, 1), L(.20, 0)])
    c2, r2 = (.27, 1 + OV - .27), .27
    a2 = _tan2(c2, r2, False, (0, 0), 0, None)[0]
    g('2', D, D, [A(*c2, r2, 155, _cw(155, a2)), L(0, 0), L(.55, 0)])
    g('3', D, D, [A(.27, 1 + OV - .235, .235, 150, -240), A(.27, .266, .276, 90, -240)])
    g('4', D, D, [M(.40, 0), L(.40, 1), L(0, .30), L(.56, .30)])
    c5, r5 = (.27, .30), .31
    j5 = _pt(*c5, r5, 140)
    g('5', D, D, [M(.52, 1), L(.07, 1), L(*j5), A(*c5, r5, 140, -280)])
    c6, r6, p6 = (.28, .28), .29, (.47, 1.0)
    a6 = _tan2(p6, 0, None, c6, r6, True)[1]
    six = [[M(*p6), L(*_pt(*c6, r6, a6)), A(*c6, r6, a6, 360)]]
    g('6', D, D, *six)
    g('7', D, D, [M(0, 1), L(.54, 1), L(.16, 0)])
    yj = .55                                       # 8 : deux cercles tangents en yj
    r8u, r8l = (1 + OV - yj) / 2, (yj + OV) / 2
    g('8', D, D, [A(.27, yj + r8u, r8u, 270, 360), A(.27, yj - r8l, r8l, 90, -360)])
    g('9', D, D, *_xf(six, .56, 1.0, -1))

    # ponctuation, signes ASCII -----------------------------------------------------------
    g(' ', 0, SPACE, [])
    g('!', SB, SB, [M(0, 1), L(0, .26)], [M(0, 0), L(0, DOT)])
    g('"', .08, .08, [M(0, 1), L(0, .74)], [M(.16, 1), L(.16, .74)])
    g('#', .05, .05, [M(.16, .04), L(.30, .96)], [M(.40, .04), L(.54, .96)],
      [M(.02, .34), L(.66, .34)], [M(.04, .66), L(.68, .66)])
    g('$', .07, .07, _s(.29, -OV, 1 + OV, .225, .245, 1.18), [M(.29, 1.12), L(.29, -.12)])
    g('%', .05, .05, [A(.14, .84, .14, 90, 360)], [M(.04, 0), L(.70, 1)], [A(.60, .16, .14, 90, 360)])
    ct, rt, cb, rb, pa = (.30, .79), .20, (.31, .27), .28, (.80, 0)
    a1 = _tan2(pa, 0, None, ct, rt, False)[1]
    a2_, a3 = _tan2(ct, rt, False, cb, rb, True)
    a4 = -35.0
    q4 = _pt(*cb, rb, a4)
    dx4, dy4 = -math.sin(math.radians(a4)), math.cos(math.radians(a4))
    t4 = (.44 - q4[1]) / dy4
    g('&', .06, .04, [M(*pa), L(*_pt(*ct, rt, a1)), A(*ct, rt, a1, _cw(a1, a2_)), L(*_pt(*cb, rb, a3)),
                      A(*cb, rb, a3, _ccw(a3, a4)), L(q4[0] + dx4 * t4, .44)])
    g("'", .08, .08, [M(0, 1), L(0, .74)])
    pr, ph = .85, .62                              # parenthèses : arcs d'un grand cercle
    pa_ = math.degrees(math.asin(ph / pr))
    g('(', .08, .05, [A(pr, .44, pr, 180 - pa_, 2 * pa_)])
    g(')', .05, .08, [A(0, .44, pr, -pa_, 2 * pa_)])
    g('*', .06, .06, [M(0, .62), L(0, .94)], [M(-.1386, .70), L(.1386, .86)], [M(-.1386, .86), L(.1386, .70)])
    g('+', .07, .07, [M(0, MATH), L(.56, MATH)], [M(.28, MATH - .28), L(.28, MATH + .28)])
    g(',', .10, .10, _comma(0, 0))
    g('-', .07, .07, [M(0, HY), L(.30, HY)])
    g('­', .07, .07, [M(0, HY), L(.30, HY)])
    g('.', .10, .10, [M(0, 0), L(0, DOT)])
    g('/', .03, .03, [M(0, -.12), L(.44, 1.04)])
    g(':', .10, .10, [M(0, 0), L(0, DOT)], [M(0, XH - DOT), L(0, XH)])
    g(';', .10, .10, _comma(0, 0), [M(0, XH - DOT), L(0, XH)])
    g('<', .07, .07, [M(.50, MATH + .28), L(0, MATH), L(.50, MATH - .28)])
    g('=', .07, .07, [M(0, MATH + .12), L(.56, MATH + .12)], [M(0, MATH - .12), L(.56, MATH - .12)])
    g('>', .07, .07, [M(0, MATH + .28), L(.50, MATH), L(0, MATH - .28)])
    g('?', .07, .07, [A(.25, 1 + OV - .25, .25, 160, -250), L(.25, .26)], [M(.25, 0), L(.25, DOT)])
    co, ri, ro_, cs = (.52, .42), .20, .48, .14   # @ : un a dans un grand cercle
    g('@', .06, .06, [M(co[0] + ri, .62), L(co[0] + ri, co[1]), A(*co, ri, 0, -360),
                      A(co[0] + ri + cs, co[1], cs, 180, 180), A(*co, ro_, 0, 320)])
    g('[', .10, .05, [M(.20, ASC), L(0, ASC), L(0, -.18), L(.20, -.18)])
    g('\\', .03, .03, [M(0, 1.04), L(.44, -.12)])
    g(']', .05, .10, [M(0, ASC), L(.20, ASC), L(.20, -.18), L(0, -.18)])
    g('^', .06, .06, [M(0, .62), L(.24, 1), L(.48, .62)])
    g('_', .02, .02, [M(0, -.20), L(.60, -.20)])
    g('`', .08, .08, [M(.15, XH + .12), L(0, XH + .29)])
    rb_ = .10
    g('{', .08, .06, [M(.26, ASC), A(.26, ASC - rb_, rb_, 90, 90), L(.16, .54), A(.06, .54, rb_, 0, -90),
                      A(.06, .34, rb_, 90, -90), L(.16, -.08), A(.26, -.08, rb_, 180, 90)])
    g('|', SB, SB, [M(0, ASC), L(0, DSC)])
    g('}', .06, .08, *_xf([G['{'][2][0]], .26, 0, -1, 1))
    g('~', .06, .06, [E(.13, MATH, .13, .08, 180, -180), E(.39, MATH, .13, .08, 180, 180)])

    # Latin-1 : signes ------------------------------------------------------------------
    g(' ', 0, SPACE, [])
    g('¢', SR, .05, [A(.38, .45, .38, 45, 270)], [M(.38, .95), L(.38, -.05)])
    g('£', .05, .05, [A(.40, .78, .22, 30, 150), L(.18, 0)], [M(0, 0), L(.62, 0)], [M(0, .44), L(.42, .44)])
    cc = (.32, MATH)
    g('¤', .05, .05, [A(*cc, .20, 90, 360)],
      *[[M(*_pt(*cc, .20, a)), L(*_pt(*cc, .31, a))] for a in (45, 135, 225, 315)])
    g('¥', SD, SD, [M(0, 1), L(.35, .50), L(.70, 1)], [M(.35, .50), L(.35, 0)],
      [M(.13, .36), L(.57, .36)], [M(.13, .20), L(.57, .20)])
    g('¦', SB, SB, [M(0, ASC), L(0, .50)], [M(0, .26), L(0, DSC)])
    g('§', .07, .07, _s(.22, .22, 1 + OV, .175, .175, 1.26), _s(.22, -.08, .71, .175, .175, 1.26))
    g('©', .06, .06, [A(.53, .5, .53, 90, 360)], [A(.53, .5, .25, 45, 270)])
    g('«', .05, .05, [M(.20, .60), L(0, .36), L(.20, .12)], [M(.40, .60), L(.20, .36), L(.40, .12)])
    g('¬', .07, .07, [M(0, .52), L(.56, .52), L(.56, .30)])
    g('®', .06, .06, [A(.53, .5, .53, 90, 360)],
      [M(.38, .24), L(.38, .76), L(.52, .76), A(.52, .64, .12, 90, -180), L(.38, .52)], [M(.52, .52), L(.68, .24)])
    g('°', .06, .06, [A(.13, .87, .13, 90, 360)])
    re_ = .42                                      # ℮ (signe estimé des préemballages) : un e rond, plus grand
    g('℮', SR, .07, [M(0, re_), L(2 * re_, re_), A(re_, re_, re_, 0, 320)])
    g('±', .07, .07, [M(0, .58), L(.56, .58)], [M(.28, .32), L(.28, .84)], [M(0, .08), L(.56, .08)])
    g('µ', SB, SB, [M(0, XH), L(0, DSC)], [M(0, rn - OV), A(rn, rn - OV, rn, 180, 180)], [M(2 * rn, XH), L(2 * rn, 0)])
    g('¶', .05, SB, [M(.30, -.10), L(.30, 1), L(.48, 1), L(.48, -.10)], [M(.30, 1), A(.30, .75, .25, 90, 180)])
    g('·', SB, SB, [M(0, .36), L(0, .36 + DOT)])
    g('»', .05, .05, [M(0, .60), L(.20, .36), L(0, .12)], [M(.20, .60), L(.40, .36), L(.20, .12)])
    g('×', .08, .08, [M(0, MATH - .20), L(.40, MATH + .20)], [M(0, MATH + .20), L(.40, MATH - .20)])
    g('÷', .07, .07, [M(0, MATH), L(.56, MATH)], [M(.28, MATH + .18), L(.28, MATH + .18 + DOT)],
      [M(.28, MATH - .18 - DOT), L(.28, MATH - .18)])

    # Latin-1 et Latin étendu A : lettres dessinées -----------------------------------------
    g('Æ', SD, .07, [M(0, 0), L(.50, 1), L(.98, 1)], [M(.50, 1), L(.50, 0), L(1.0, 0)],
      [M(.50, .52), L(.92, .52)], [M(.16, .32), L(.50, .32)])
    dshape = [M(.10, 0), L(.10, 1), L(.34, 1), A(.34, .5, .5, 90, -180), L(.10, 0)]
    g('Ð', .04, SR, dshape, [M(0, .5), L(.30, .5)])
    g('Đ', .04, SR, dshape, [M(0, .5), L(.30, .5)])
    g('Ø', SR, SR, [A(r, .5, r, 90, 360)], [M(r - .45, -.04), L(r + .45, 1.04)])
    g('Þ', SB, .06, [M(0, 1), L(0, 0)], [M(0, .80), L(.28, .80), A(.28, .535, .265, 90, -180), L(0, .27)])
    g('ß', SB, .06, [M(0, 0), L(0, ASC - .24), A(.24, ASC - .24, .24, 180, -270),
                     A(.24, ASC - .48 - .295, .295, 90, -215)])
    g('æ', SR, .07, G['a'][2][0], [M(2 * ro, cy), L(4 * ro, cy), A(3 * ro, cy, ro, 0, 320)])
    pd = (.20, 1.02)
    ad = _tan2(pd, 0, None, (ro, cy), ro, False)[1]
    g('ð', SR, SR, [M(*pd), L(*_pt(ro, cy, ro, ad)), A(ro, cy, ro, ad, -360)], [M(.22, .80), L(.50, .94)])
    g('ø', SR, SR, [A(ro, cy, ro, 90, 360)], [M(.02, -.03), L(.70, .73)])
    g('þ', SB, SR, [M(0, ASC), L(0, cy), A(ro, cy, ro, 180, 360), L(0, DSC)])
    g('Œ', SR, .07, [M(1.02, 1), L(.50, 1), A(.50, .5, .5, 90, 180), L(1.02, 0)],
      [M(.50, 1), L(.50, 0)], [M(.50, .52), L(.96, .52)])
    g('œ', SR, .07, [A(ro, cy, ro, 0, 360), L(4 * ro, cy), A(3 * ro, cy, ro, 0, 320)])
    g('Ł', .02, .04, [M(.12, 1), L(.12, 0), L(.60, 0)], [M(0, .38), L(.26, .60)])
    g('ł', .04, .04, [M(.12, ASC), L(.12, 0)], [M(0, .44), L(.24, .66)])
    g('đ', SR, .05, G['d'][2][0], [M(.56, .92), L(.88, .92)])
    g('Ħ', .04, .04, [M(.08, 1), L(.08, 0)], [M(.76, 1), L(.76, 0)], [M(.08, .52), L(.76, .52)],
      [M(0, .78), L(.84, .78)])
    g('ħ', .04, SB, [M(.08, ASC), L(.08, 0)], _xf([G['h'][2][1]], .08)[0], [M(0, .90), L(.30, .90)])
    g('ı', SB, SB, [M(0, 0), L(0, XH)])
    g('ȷ', .02, SB, jtail)
    g('Ĳ', SB, SB, [M(0, 1), L(0, 0)], *_xf(G['J'][2], .24))
    g('ĳ', SB, SB, [M(0, 0), L(0, XH)], [M(0, IDOT), L(0, IDOT + DOT)], *_xf(G['j'][2], .34))
    g('ĸ', SB, SD, [M(0, XH), L(0, 0)], *karm)
    g('Ŀ', SB, .04, [M(0, 1), L(0, 0), L(.48, 0)], [M(.26, .47), L(.26, .47 + DOT)])
    g('ŀ', SB, SB, [M(0, ASC), L(0, 0)], [M(.18, .50), L(.18, .50 + DOT)])
    g('ŉ', .06, SB, _comma(0, 1 - DOT), *_xf(G['n'][2], .16))
    g('Ŋ', SB, SB, [M(0, 0), L(0, 1), L(.70, 0)], [M(.70, 1), L(.70, -.06), A(.52, -.06, .18, 0, -160)])
    g('ŋ', SB, SB, nstem, narch + [L(2 * rn, DSC - OV + rj), A(2 * rn - rj, DSC - OV + rj, rj, 0, -150)])
    g('Ŧ', .03, .03, [M(0, 1), L(.62, 1)], [M(.31, 1), L(.31, 0)], [M(.15, .52), L(.47, .52)])
    g('ŧ', .04, .04, [M(.16, TT), L(.16, 0)], [M(0, XH), L(.36, XH)], [M(.04, .42), L(.30, .42)])
    g('ſ', .04, .02, fhook)

    # ponctuation et signes divers ------------------------------------------------------
    g('€', .02, .05, [A(.58, .5, r, 48, 264)], [M(0, .60), L(.58, .60)], [M(0, .40), L(.58, .40)])
    g('’', .08, .08, _comma(.05, 1 - DOT))
    g('‘', .08, .08, *_xf([_comma(.05, 1 - DOT)], .05, 1.80, -1))
    g('‚', .10, .10, _comma(0, 0))
    g('”', .08, .08, _comma(.05, 1 - DOT), _comma(.21, 1 - DOT))
    g('“', .08, .08, *_xf([_comma(.05, 1 - DOT), _comma(.21, 1 - DOT)], .26, 1.80, -1))
    g('„', .10, .10, _comma(0, 0), _comma(.16, 0))
    g('†', .06, .06, [M(.24, 1), L(.24, -.20)], [M(0, .70), L(.48, .70)])
    g('‡', .06, .06, [M(.24, 1), L(.24, -.20)], [M(0, .74), L(.48, .74)], [M(0, .18), L(.48, .18)])
    g('•', .08, .08, [A(0, .42, .14, 90, 360)], [A(0, .42, .07, 90, 360)])
    g('…', .10, .10, [M(0, 0), L(0, DOT)], [M(.26, 0), L(.26, DOT)], [M(.52, 0), L(.52, DOT)])
    g('‰', .05, .05, *G['%'][2], [A(.94, .16, .14, 90, 360)])
    g('‹', .05, .05, [M(.20, .60), L(0, .36), L(.20, .12)])
    g('›', .05, .05, [M(0, .60), L(.20, .36), L(0, .12)])
    g('−', .07, .07, [M(0, MATH), L(.56, MATH)])
    g('–', .04, .04, [M(0, HY), L(.56, HY)])
    g('—', .04, .04, [M(0, HY), L(1.10, HY)])
    g('™', .06, .06, [M(0, 1), L(.30, 1)], [M(.15, 1), L(.15, .62)],
      [M(.40, .62), L(.44, 1), L(.56, .62), L(.68, 1), L(.72, .62)])
    g('⌀', .04, .04, [A(.45, .5, .40, 90, 360)], [M(0, 0), L(.90, 1)])
    g(' ', 0, THIN, [])
    g(' ', 0, THIN, [])

    # dérivés : exposants, ordinaux, fractions, glyphes retournés ----------------------------
    for ch, base in (('¹', '1'), ('²', '2'), ('³', '3')):
        g(ch, .05, .05, *_xf(G[base][2], 0, .44, .56))
    g('ª', .05, .05, *_xf(G['a'][2], 0, .56, .6), [M(0, .44), L(.43, .44)])
    g('º', .05, .05, *_xf(G['o'][2], 0, .56, .6), [M(0, .44), L(.43, .44)])
    for ch, num, den in (('¼', '1', '4'), ('½', '1', '2'), ('¾', '3', '4')):
        g(ch, .05, .05, *_xf(G[num][2], .02 if num == '1' else 0, .52, .48), [M(.12, 0), L(.70, 1)],
          *_xf(G[den][2], .50, 0, .48))
    for ch, base in (('¡', '!'), ('¿', '?')):
        lsb, rsb, strokes = G[base]
        g(ch, rsb, lsb, *_xf(strokes, 0, XH, -1))

    # grec : alphabet monotonique (les accents sont composés) --------------------------------
    for gr, la in zip('ΑΒΕΖΗΙΚΜΝΟΡΤΥΧ',
                      'ABEZHIKMNOPTYX'):
        G[gr] = G[la]                              # Α Β Ε Ζ Η Ι Κ Μ Ν Ο Ρ Τ Υ Χ : les capitales latines
    g('Γ', SB, .05, [M(.48, 1), L(0, 1), L(0, 0)])
    g('Δ', SD, SD, [M(0, 0), L(.40, 1), L(.80, 0), L(0, 0)])
    g('Θ', SR, SR, [A(r, .5, r, 90, 360)], [M(r - .22, .5), L(r + .22, .5)])
    g('Λ', SD, SD, [M(0, 0), L(.40, 1), L(.80, 0)])
    g('Ξ', .05, .05, [M(0, 1), L(.62, 1)], [M(.08, .52), L(.54, .52)], [M(0, 0), L(.62, 0)])
    g('Π', SB, SB, [M(0, 0), L(0, 1), L(.68, 1), L(.68, 0)])
    g('Σ', .05, .05, [M(.60, 1), L(0, 1), L(.32, .5), L(0, 0), L(.62, 0)])
    g('Φ', .05, .05, [E(.42, .5, .42, .27, 90, 360)], [M(.42, 1), L(.42, 0)])
    g('Ψ', .05, .05, [M(0, 1), L(0, .64), A(.36, .64, .36, 180, 180), L(.72, 1)], [M(.36, 1), L(.36, 0)])
    oc, orad, of1, of2 = (.45, .575), .43, (.24, 0.0), (.66, 0.0)     # Ω : bol ouvert, jambes tangentes, pieds
    oa1 = _tan2(of1, 0, None, oc, orad, False)[1]
    oa2 = _tan2(oc, orad, False, of2, 0, None)[0]
    g('Ω', .04, .04, [M(0, 0), L(*of1), L(*_pt(*oc, orad, oa1)), A(*oc, orad, oa1, _cw(oa1, oa2)), L(*of2),
                      L(.90, 0)])
    g('α', SR, .03, [M(2 * ro + .07, XH), L(2 * ro, cy), A(ro, cy, ro, 0, 360), L(2 * ro + .09, 0)])
    g('β', SB, SR, [M(0, DSC), L(0, .80), A(.22, .80, .22, 180, -270), E(.22, .29, .29, .29, 90, -180), L(0, 0)])
    g('γ', SD, SD, [M(0, XH), L(.28, 0), L(.28, DSC)], [M(.56, XH), L(.28, 0)])
    g('δ', SR, SR, [M(.58, ASC), L(.16, ASC), L(ro, cy + ro), A(ro, cy, ro, 90, 360)])
    g('ε', SR, .05, [A(.26, .535, .165, 40, 230), E(.26, .185, .20, .185, 90, 230)])
    g('ζ', .04, .04, [M(.10, ASC), L(.50, ASC), L(.04, .25), E(.24, .25, .20, .25, 180, 90), L(.36, 0),
                      A(.36, -.15, .15, 90, -150)])
    g('η', SB, SB, nstem, narch + [L(2 * rn, DSC)])
    g('θ', SR, SR, [E(.27, .53, .27, .53, 90, 360)], [M(0, .53), L(.54, .53)])
    g('ι', SB, .04, [M(0, XH), L(0, .12), A(.12, .12, .12, 180, 90)])
    G['κ'] = G['ĸ']                           # κ : le kra
    g('λ', .03, .03, [M(.04, ASC), L(.62, 0)], [M(.04 + .58 * (ASC - .50) / ASC, .50), L(0, 0)])
    G['μ'] = G['µ']                      # μ : le micro
    G['ν'] = G['v']                           # ν
    g('ξ', .05, .04, [A(.27, .87, .19, 60, 210), E(.27, .34, .27, .34, 90, 180), L(.36, 0),
                      A(.36, -.14, .14, 90, -150)])
    G['ο'] = G['o']                           # ο
    g('π', .04, .04, [M(0, XH), L(.64, XH)], [M(.14, XH), L(.14, 0)], [M(.50, XH), L(.50, .12),
                                                                      A(.62, .12, .12, 180, 90)])
    g('ρ', SB, SR, [M(0, DSC), L(0, cy), A(ro, cy, ro, 180, -360)])
    g('ς', SR, .04, [A(ro, cy, ro, 50, 220), A(ro, cy - ro - .13, .13, 90, -150)])
    g('σ', SR, .03, [M(2 * ro + .16, cy + ro), L(ro, cy + ro), A(ro, cy, ro, 90, 360)])
    g('τ', .03, .04, [M(0, XH), L(.50, XH)], [M(.25, XH), L(.25, .12), A(.37, .12, .12, 180, 90)])
    g('υ', SB, SB, [M(0, XH), L(0, .30), A(.30, .30, .30, 180, 180), L(.60, XH)])
    g('φ', SR, SR, [A(ro, cy, ro, 90, 360)], [M(ro, .92), L(ro, DSC)])
    g('χ', SD, SD, [M(0, XH), L(.52, DSC)], [M(0, DSC), L(.52, XH)])
    g('ψ', SB, SB, [M(0, XH), L(0, .36), A(.30, .36, .30, 180, 180), L(.60, XH)], [M(.30, .92), L(.30, DSC)])
    g('ω', SR, SR, [E(.22, .37, .22, .38, 120, 240), E(.66, .37, .22, .38, 180, 240)])

    # flèches ------------------------------------------------------------------------------
    hd, ax = .17, .84                              # pointe, longueur
    right = [[M(0, MATH), L(ax, MATH)], [M(ax - hd, MATH + hd), L(ax, MATH), L(ax - hd, MATH - hd)]]
    g('→', .06, .06, *right)
    g('←', .06, .06, *_xf(right, ax, 0, -1, 1))
    g('↔', .06, .06, [M(0, MATH), L(ax + .14, MATH)], [M(hd, MATH + hd), L(0, MATH), L(hd, MATH - hd)],
      [M(ax + .14 - hd, MATH + hd), L(ax + .14, MATH), L(ax + .14 - hd, MATH - hd)])
    up = [[M(hd, 0), L(hd, 1)], [M(0, 1 - hd), L(hd, 1), L(2 * hd, 1 - hd)]]
    g('↑', .06, .06, *up)
    g('↓', .06, .06, *_xf(up, 0, 1, 1, -1))
    g('↕', .06, .06, *up, [M(0, hd), L(hd, 0), L(2 * hd, hd)])
    ne = [[M(0, .06), L(.70, .76)], [M(.46, .76), L(.70, .76), L(.70, .52)]]
    g('↗', .05, .05, *ne)
    g('↖', .05, .05, *_xf(ne, .70, 0, -1, 1))
    g('↘', .05, .05, *_xf(ne, 0, .82, 1, -1))
    g('↙', .05, .05, *_xf(ne, .70, .82, -1, -1))
    xj = .56 + .28 * (.26 - .09) / .26             # ⇒ : les deux traits s'arrêtent sur la pointe
    dbl = [[M(0, MATH + .09), L(xj, MATH + .09)], [M(0, MATH - .09), L(xj, MATH - .09)],
           [M(.56, MATH + .26), L(.84, MATH), L(.56, MATH - .26)]]
    g('⇒', .06, .06, *dbl)
    g('⇐', .06, .06, *_xf(dbl, .84, 0, -1, 1))

    # signes techniques ----------------------------------------------------------------------
    g('≤', .07, .07, [M(.50, .80), L(0, .56), L(.50, .32)], [M(0, .14), L(.50, .14)])
    g('≥', .07, .07, [M(0, .80), L(.50, .56), L(0, .32)], [M(0, .14), L(.50, .14)])
    g('≠', .07, .07, *G['='][2], [M(.12, MATH - .30), L(.44, MATH + .30)])
    g('≈', .06, .06, [E(.13, MATH + .10, .13, .07, 180, -180), E(.39, MATH + .10, .13, .07, 180, 180)],
      [E(.13, MATH - .10, .13, .07, 180, -180), E(.39, MATH - .10, .13, .07, 180, 180)])
    g('∞', .06, .06, [A(.18, MATH, .16, 0, 360), A(.50, MATH, .16, 180, -360)])
    g('√', .03, .03, [M(0, .44), L(.10, .50), L(.30, 0), L(.58, ASC), L(.90, ASC)])
    g('∠', .05, .05, [M(.70, .78), L(0, 0), L(.80, 0)])
    g('⊥', .05, .05, [M(.40, .90), L(.40, 0)], [M(0, 0), L(.80, 0)])
    g('∥', SB, SB, [M(0, ASC), L(0, DSC)], [M(.20, ASC), L(.20, DSC)])
    g('′', .06, .06, [M(.10, 1), L(.02, .70)])
    g('″', .06, .06, [M(.10, 1), L(.02, .70)], [M(.26, 1), L(.18, .70)])
    g('№', SB, .06, *G['N'][2], *_xf(G['o'][2], .86, .40, .5), [M(.86, .28), L(1.22, .28)])
    g('℃', .06, .05, *G['°'][2], *_xf(G['C'][2], .34))
    g('℉', .06, .06, *G['°'][2], *_xf(G['F'][2], .40))
    g('✓', .05, .05, [M(0, .42), L(.24, .10), L(.72, .92)])
    g('✗', .05, .05, [M(.04, .10), L(.62, .92)], [M(.08, .84), L(.58, .06)])
    g('‒', .04, .04, [M(0, HY), L(.64, HY)])          # tiret numérique (largeur d'un chiffre)
    g('⁄', 0, 0, [M(0, 0), L(.50, 1)])                # barre de fraction
    for alias, ch in (('Ω', 'Ω'), ('∆', 'Δ'), ('∑', 'Σ'), ('∅', '⌀'), ('‐', '-'),
                      ('‑', '-'), ('―', '—')):
        G[alias] = G[ch]                           # ohm, incrément, somme, ensemble vide, tirets

    # exposants, indices, fractions ----------------------------------------------------------
    for ch, base in zip('⁰⁴⁵⁶⁷⁸⁹', '0456789'):
        g(ch, .05, .05, *_xf(G[base][2], 0, .44, .56))
    for i in range(10):
        g(chr(0x2080 + i), .05, .05, *_xf(G[str(i)][2], 0, -.16, .56))
    for ch, num, den in (('⅓', '1', '3'), ('⅔', '2', '3'), ('⅛', '1', '8'), ('⅜', '3', '8'), ('⅝', '5', '8'),
                         ('⅞', '7', '8')):
        g(ch, .05, .05, *_xf(G[num][2], .02 if num == '1' else 0, .52, .48), [M(.12, 0), L(.70, 1)],
          *_xf(G[den][2], .50, 0, .48))
    return G


# --- diacritiques ------------------------------------------------------------------------

_OGX, _OGY, _OGA = .075, .09, 135.0           # ogonek : ellipse passant par l'attache
#: diacritiques combinants, centrés sur x = 0 et posés sur y = 0 (au-dessus :
#: vers le haut ; cédille, ogonek, virgule souscrite : vers le bas)
_MARKS = {
    0x300: [[M(.07, 0), L(-.08, .17)]],                                    # grave
    0x301: [[M(-.07, 0), L(.08, .17)]],                                    # aigu
    0x302: [[M(-.14, 0), L(0, .15), L(.14, 0)]],                           # circonflexe
    0x303: [[E(-.075, .06, .075, .06, 180, -180), E(.075, .06, .075, .06, 180, 180)]],   # tilde
    0x304: [[M(-.14, .06), L(.14, .06)]],                                  # macron
    0x306: [[E(0, .12, .13, .12, 180, 180)]],                              # brève
    0x307: [[M(0, 0), L(0, DOT)]],                                         # point
    0x308: [[M(-.11, 0), L(-.11, DOT)], [M(.11, 0), L(.11, DOT)]],         # tréma
    0x30A: [[A(0, .075, .075, 270, 360)]],                                 # rond
    0x30B: [[M(-.12, 0), L(-.03, .17)], [M(.05, 0), L(.14, .17)]],         # double aigu
    0x30C: [[M(-.14, .15), L(0, 0), L(.14, .15)]],                         # caron
    0x327: [[M(0, 0), L(0, -.06), E(0, -.125, .07, .065, 90, -230)]],      # cédille
    0x328: [[E(-_OGX * math.cos(math.radians(_OGA)), -_OGY * math.sin(math.radians(_OGA)),     # ogonek
               _OGX, _OGY, _OGA, 165)]],
    0x323: [[M(0, -.09), L(0, -.09 - DOT)]],                               # point souscrit
    0x326: [[M(.025, -.07), L(-.025, -.20)]],                              # virgule souscrite (Ș Ț)
    'comma': [[M(.025, -.07), L(-.025, -.20)]],                            # virgule souscrite
    'turned': [[M(-.02, 0), L(.025, .14)]],                                # virgule culbutée (ģ)
}
_BELOW = {0x323, 0x326, 0x327, 0x328, 'comma'}
#: lettres lettones et assimilées : virgule souscrite plutôt que cédille
_COMMA_BELOW = set('GKLNRgklnr')
#: caron en apostrophe, à droite des lettres hautes (ď ľ ť Ľ)
_CARON_APOS = set('dltL')
#: signes d'accent isolés (Latin-1), dessinés au-dessus de la hauteur d'x
_SPACING = {'´': 0x301, '¨': 0x308, '¯': 0x304, '¸': 0x327, 'ˆ': 0x302, '˜': 0x303, '˘': 0x306, '˙': 0x307,
            '˚': 0x30A, '˝': 0x30B, 'ˇ': 0x30C, '˛': 0x328}


def is_stroke(path) -> bool:
    return str(path) == PATH


# --- compilation -----------------------------------------------------------------------

def _contours(strokes, gaps=None) -> list:
    """Traits → contours `geom` continus. Un arc qui ne part pas du point
    courant est rattaché par une droite (noté dans `gaps` : erreur de dessin)."""
    out = []
    for s in strokes:
        segs, pen = [], None
        for c in s:
            op = c[0]
            if op == 'M':
                pen = (c[1], c[2])
                continue
            if op == 'L':
                p = (c[1], c[2])
                if pen is not None and math.dist(pen, p) > 1e-6:
                    segs.append(Line(pen, p))
                    pen = p
                elif pen is None:
                    pen = p
                continue
            if op == 'A':
                _, cx, cy, rx, a0, sw = c
                ry = rx
            else:
                _, cx, cy, rx, ry, a0, sw = c
            arcs = arc_conics((cx, cy), rx, ry, a0, sw)
            if pen is not None:
                if math.dist(pen, arcs[0].p0) <= 1e-6:
                    arcs[0] = Conic(pen, arcs[0].p1, arcs[0].p2, arcs[0].w)
                else:
                    if gaps is not None:
                        gaps.append((pen, arcs[0].p0))
                    segs.append(Line(pen, arcs[0].p0))
            segs.extend(arcs)
            pen = arcs[-1].p2
        if not segs:
            continue
        closed = len(segs) > 1 and math.dist(segs[0].start, segs[-1].end) <= 1e-6
        if closed:                                 # referme exactement
            last = segs[-1]
            p0 = segs[0].start
            segs[-1] = Line(last.p0, p0) if isinstance(last, Line) else Conic(last.p0, last.p1, p0, last.w)
        out.append(Contour(segs, closed))
    return out


def _flat(strokes) -> list:
    return [p for c in _contours(strokes) for p in c.flatten(0.002)]


def _bbox(strokes):
    path = Path(_contours(strokes))
    return path.bbox()


def _anchor(strokes, top: bool, pure: bool = False) -> float:
    """Abscisse où poser un accent : au-dessus, entre le point le plus haut
    et le milieu de l'encombrement (`pure` : le point le plus haut seul) ;
    au-dessous, au milieu des points bas."""
    pts = _flat(strokes)
    ys = [p[1] for p in pts]
    lim = max(ys) if top else min(ys)
    xs = [p[0] for p in pts if abs(p[1] - lim) <= 0.006]
    x_ext = (min(xs) + max(xs)) / 2
    if not top or pure:
        return x_ext
    allx = [p[0] for p in pts]
    return (x_ext + (min(allx) + max(allx)) / 2) / 2


@functools.lru_cache(maxsize=2048)
def _layout(ch: str):
    """(traits en place, avance) d'un caractère, ou None (absent)."""
    tab = _table()
    if ch in tab:
        lsb, rsb, strokes = tab[ch]
        if not strokes:
            return (), rsb
        x0, _y0, x1, _y1 = _bbox(strokes)
        if lsb is None:                            # chiffre : centré dans l'avance commune
            shift = (DIGIT - (x1 - x0)) / 2 - x0 - (0.03 if ch == '1' else 0.0)
            return tuple(map(tuple, _xf(strokes, shift))), DIGIT
        return tuple(map(tuple, _xf(strokes, lsb - x0))), lsb + (x1 - x0) + rsb
    if ch in _SPACING:                             # accent isolé : sur une lettre absente
        mark = _MARKS[_SPACING[ch]]
        y = 0.0 if _SPACING[ch] in _BELOW else XH + 0.12
        moved = _xf(mark, 0, y)
        x0, _y0, x1, _y1 = _bbox(moved)
        return tuple(map(tuple, _xf(moved, 0.08 - x0))), x1 - x0 + 0.16
    if ch.isspace():
        return (), SPACE
    d = unicodedata.normalize('NFD', ch)
    if len(d) == 1 and d != ch:                    # équivalent canonique : Ω de l'ohm, Å de l'angström, ; grec
        return _layout(d)
    if len(d) < 2 or any(ord(m) not in _MARKS for m in d[1:]):
        return None
    base = d[0]
    got = _layout({'i': 'ı', 'j': 'ȷ'}.get(base, base))
    if got is None or not got[0]:
        return None
    strokes, adv = got
    out = [list(s) for s in strokes]
    x0, y0, x1, y1 = _bbox(strokes)
    top = y1
    gap = None
    for m in d[1:]:
        cp = ord(m)
        if cp == 0x30C and base in _CARON_APOS:    # ď ľ ť Ľ : apostrophe à droite
            if base == 't':
                xa, ya = x0 + .30, 1.0 - DOT
            elif base == 'L':
                xa, ya = x0 + .20, 1.0 - DOT
            else:
                xa, ya = x1 + .12, ASC - DOT
                adv += .10
            out.append(_comma(xa, ya))
            continue
        if cp == 0x301 and 0x391 <= ord(base) <= 0x3A9:   # tonos des capitales grecques : à gauche
            out += _xf(_MARKS[cp], x0 - .11, .85, .9)
            continue
        if cp == 0x327 and base in _COMMA_BELOW:
            cp = 'comma' if base != 'g' else 'turned'
        if cp in _BELOW:
            if cp == 0x328:                        # ogonek : au pied droit
                if base in 'Aau':
                    xo, yo = x1, 0.0
                elif base == 'E':
                    xo, yo = x1 - .10, 0.0
                elif base in 'Ii':
                    xo, yo = x0, 0.0
                else:
                    xo, yo = _anchor(strokes, False) + .05, y0
                out += _xf(_MARKS[cp], xo, yo)
            else:
                xb = _anchor(strokes, False)
                out += _xf(_MARKS[cp], xb, y0 if y0 > -0.05 else 0.0)
            continue
        tall = top > 0.85                          # capitales, ascendantes : accents réduits
        k = 0.80 if tall else 1.0
        if gap is None:
            gap = 0.09 if tall else 0.12
        xc = _anchor(strokes, True, base in 'ij')
        mark = _MARKS[cp]
        y = top + gap
        out += _xf(mark, xc, y, k)
        top = y + max(p[1] for p in _flat(mark)) * k
        gap = 0.05
    bx0, _by0, bx1, _by1 = _bbox(out)             # accent plus large que la lettre : on élargit
    shift = max(0.0, 0.02 - bx0)
    adv = max(adv + shift, bx1 + shift + 0.02)
    return tuple(map(tuple, _xf(out, shift))), adv


def has(ch: str) -> bool:
    return _layout(ch) is not None


@functools.lru_cache(maxsize=4096)
def glyph(char: str) -> tuple[Path, float]:
    """(contours en hauteur de capitales 1, avance) ; caractère absent :
    rien, avec la place d'une lettre moyenne."""
    got = _layout(char)
    if got is None:
        return Path(), MISSING
    strokes, adv = got
    return Path(_contours(strokes)), adv


def metrics() -> dict:
    """Hauteur des capitales 1, comme les polices Gravotech."""
    return {'upem': 1.0, 'ascent': ASCENT, 'descent': DESCENT, 'cap': 1.0}


#: blocs où chercher les caractères composés : latins (Latin-1, étendus A et B, additionnel), grec, symboles
_COMPOSED = ((0xC0, 0x250), (0x370, 0x3D0), (0x1E00, 0x1F00), (0x2100, 0x2150))


def _fits(ch: str) -> bool:
    """Caractère composé que la police sait faire, dans la boîte des caractères
    (trois accents empilés sur une capitale en sortiraient : pas proposé)."""
    got = _layout(ch)
    if got is None or not got[0]:
        return False
    _x0, y0, _x1, y1 = _bbox(got[0])
    return y0 >= -DESCENT - 1e-9 and y1 <= ASCENT + 1e-9


@functools.cache
def characters() -> tuple:
    """Caractères dessinés : la table, les signes d'accent et les caractères
    que la composition sait faire (lettres latines et grecques accentuées,
    équivalents canoniques), dans la boîte des caractères."""
    pool = set(_table()) | set(_SPACING)
    for lo, hi in _COMPOSED:
        pool |= {chr(c) for c in range(lo, hi) if _fits(chr(c))}
    return tuple(sorted(c for c in pool if c >= ' ' and not c.isspace() or c == ' '))


# --- crénage ---------------------------------------------------------------------------------

#: paires crénées (hauteur des capitales = 1 ; négatif : rapprochées), calculées sur le dessin par
#: outils/vdgeo_crenage.py — à relancer après une retouche des glyphes
_KERN = {
    'AC': -0.11, 'AG': -0.11, 'AO': -0.11, 'AQ': -0.11, 'AT': -0.15, 'AU': -0.07, 'AV': -0.15, 'AW': -0.15,
    'AY': -0.15, 'Aa': -0.06, 'Ac': -0.06, 'Ad': -0.07, 'Ae': -0.06, 'Ag': -0.06, 'Ao': -0.06, 'Aq': -0.06,
    'Au': -0.05, 'Av': -0.1, 'Aw': -0.06, 'Ay': -0.1, 'Aæ': -0.06, 'Aœ': -0.06, "A'": -0.1, 'A"': -0.1, 'A’': -0.1,
    'A‘': -0.1, 'A”': -0.1, 'A“': -0.1, 'Aà': -0.07, 'Aâ': -0.07, 'Aä': -0.07, 'Aé': -0.07, 'Aè': -0.07, 'Aê': -0.07,
    'Aë': -0.07, 'Aô': -0.07, 'Aö': -0.07, 'Aù': -0.06, 'Aû': -0.06, 'Aü': -0.06, 'Aç': -0.06, 'AÇ': -0.11,
    'AÔ': -0.11, 'AÖ': -0.11, 'AÙ': -0.07, 'AÛ': -0.07, 'AÜ': -0.07, 'AŒ': -0.11, 'FA': -0.15, 'FC': -0.07,
    'FG': -0.07, 'FJ': -0.15, 'FO': -0.07, 'FQ': -0.07, 'Fa': -0.1, 'Fc': -0.1, 'Fd': -0.1, 'Fe': -0.1, 'Fg': -0.1,
    'Fo': -0.1, 'Fq': -0.1, 'Fs': -0.06, 'Fu': -0.1, 'Fv': -0.08, 'Fw': -0.07, 'Fx': -0.12, 'Fy': -0.08, 'Fæ': -0.1,
    'Fœ': -0.1, 'F’': -0.03, 'F”': -0.03, 'F.': -0.1, 'F,': -0.1, 'F-': -0.1, 'Fà': -0.1, 'Fâ': -0.1, 'Fä': -0.1,
    'Fé': -0.1, 'Fè': -0.1, 'Fê': -0.1, 'Fë': -0.1, 'Fô': -0.1, 'Fö': -0.1, 'Fù': -0.1, 'Fû': -0.1, 'Fü': -0.1,
    'Fç': -0.1, 'FÀ': -0.15, 'FÂ': -0.15, 'FÄ': -0.15, 'FÇ': -0.07, 'FÔ': -0.07, 'FÖ': -0.07, 'FŒ': -0.07,
    'KC': -0.15, 'KG': -0.15, 'KO': -0.15, 'KQ': -0.15, 'Ka': -0.1, 'Kc': -0.1, 'Kd': -0.1, 'Ke': -0.1, 'Kg': -0.1,
    'Ko': -0.1, 'Kq': -0.1, 'Ku': -0.08, 'Kv': -0.15, 'Kw': -0.11, 'Ky': -0.15, 'Kæ': -0.1, 'Kœ': -0.1, 'K-': -0.1,
    'Kà': -0.1, 'Kâ': -0.1, 'Kä': -0.1, 'Ké': -0.1, 'Kè': -0.1, 'Kê': -0.1, 'Kë': -0.1, 'Kô': -0.1, 'Kö': -0.1,
    'Kù': -0.08, 'Kû': -0.08, 'Kü': -0.08, 'Kç': -0.1, 'KÇ': -0.15, 'KÔ': -0.15, 'KÖ': -0.15, 'KŒ': -0.15,
    'LC': -0.15, 'LG': -0.15, 'LO': -0.15, 'LQ': -0.15, 'LT': -0.15, 'LU': -0.11, 'LV': -0.15, 'LW': -0.15,
    'LY': -0.15, 'La': -0.11, 'Lc': -0.11, 'Ld': -0.11, 'Le': -0.11, 'Lg': -0.11, 'Lo': -0.11, 'Lq': -0.11,
    'Lu': -0.09, 'Lv': -0.15, 'Lw': -0.11, 'Ly': -0.15, 'Læ': -0.11, 'Lœ': -0.11, "L'": -0.1, 'L"': -0.1, 'L’': -0.1,
    'L‘': -0.1, 'L”': -0.1, 'L“': -0.1, 'L-': -0.1, 'Là': -0.11, 'Lâ': -0.11, 'Lä': -0.11, 'Lé': -0.11, 'Lè': -0.11,
    'Lê': -0.11, 'Lë': -0.11, 'Lô': -0.11, 'Lö': -0.11, 'Lù': -0.09, 'Lû': -0.09, 'Lü': -0.09, 'Lç': -0.11,
    'LÇ': -0.15, 'LÔ': -0.15, 'LÖ': -0.15, 'LÙ': -0.11, 'LÛ': -0.11, 'LÜ': -0.11, 'LŒ': -0.15, 'PA': -0.15,
    'PJ': -0.15, 'PT': -0.03, 'PX': -0.03, 'PY': -0.03, 'Pa': -0.1, 'Pc': -0.1, 'Pd': -0.1, 'Pe': -0.09, 'Pg': -0.1,
    'Po': -0.1, 'Pq': -0.1, 'Pæ': -0.1, 'Pœ': -0.1, 'P.': -0.1, 'P,': -0.1, 'P-': -0.1, 'Pà': -0.1, 'Pâ': -0.1,
    'Pä': -0.1, 'Pé': -0.09, 'Pè': -0.09, 'Pê': -0.09, 'Pë': -0.09, 'Pô': -0.1, 'Pö': -0.1, 'Pç': -0.1, 'PÀ': -0.15,
    'PÂ': -0.15, 'PÄ': -0.15, 'RC': -0.04, 'RG': -0.04, 'RO': -0.04, 'RQ': -0.04, 'RT': -0.05, 'RV': -0.03,
    'RY': -0.05, 'Ra': -0.07, 'Rc': -0.07, 'Rd': -0.1, 'Re': -0.07, 'Rg': -0.07, 'Ro': -0.07, 'Rq': -0.07,
    'Ru': -0.03, 'Ræ': -0.07, 'Rœ': -0.07, 'R-': -0.1, 'Rà': -0.1, 'Râ': -0.1, 'Rä': -0.09, 'Ré': -0.1, 'Rè': -0.1,
    'Rê': -0.1, 'Rë': -0.09, 'Rô': -0.1, 'Rö': -0.09, 'Rù': -0.03, 'Rû': -0.03, 'Rü': -0.03, 'Rç': -0.07, 'RÇ': -0.04,
    'RÔ': -0.04, 'RÖ': -0.04, 'RŒ': -0.04, 'TA': -0.15, 'TC': -0.15, 'TG': -0.15, 'TJ': -0.15, 'TO': -0.15,
    'TQ': -0.15, 'Ta': -0.15, 'Tc': -0.15, 'Td': -0.15, 'Te': -0.15, 'Tg': -0.15, 'To': -0.15, 'Tq': -0.15,
    'Ts': -0.15, 'Tu': -0.15, 'Tv': -0.15, 'Tw': -0.15, 'Tx': -0.15, 'Ty': -0.15, 'Tæ': -0.15, 'Tœ': -0.15,
    'T.': -0.1, 'T,': -0.1, 'T-': -0.1, 'Tà': -0.15, 'Tâ': -0.15, 'Tä': -0.15, 'Té': -0.15, 'Tè': -0.15, 'Tê': -0.15,
    'Të': -0.15, 'Tô': -0.15, 'Tö': -0.15, 'Tù': -0.15, 'Tû': -0.15, 'Tü': -0.15, 'Tç': -0.15, 'TÀ': -0.15,
    'TÂ': -0.15, 'TÄ': -0.15, 'TÇ': -0.15, 'TÔ': -0.15, 'TÖ': -0.15, 'TŒ': -0.15, 'VA': -0.15, 'VC': -0.11,
    'VG': -0.11, 'VJ': -0.15, 'VO': -0.11, 'VQ': -0.11, 'Va': -0.15, 'Vc': -0.15, 'Vd': -0.15, 'Ve': -0.15,
    'Vg': -0.15, 'Vo': -0.15, 'Vq': -0.15, 'Vs': -0.1, 'Vu': -0.09, 'Væ': -0.15, 'Vœ': -0.15, 'V.': -0.1, 'V,': -0.1,
    'V-': -0.08, 'Và': -0.15, 'Vâ': -0.15, 'Vä': -0.15, 'Vé': -0.15, 'Vè': -0.15, 'Vê': -0.15, 'Vë': -0.15,
    'Vô': -0.15, 'Vö': -0.15, 'Vù': -0.09, 'Vû': -0.09, 'Vü': -0.09, 'Vç': -0.15, 'VÀ': -0.15, 'VÂ': -0.15,
    'VÄ': -0.15, 'VÇ': -0.11, 'VÔ': -0.11, 'VÖ': -0.11, 'VŒ': -0.11, 'WA': -0.15, 'WC': -0.07, 'WG': -0.07,
    'WJ': -0.14, 'WO': -0.07, 'WQ': -0.07, 'Wa': -0.1, 'Wc': -0.1, 'Wd': -0.12, 'We': -0.1, 'Wg': -0.1, 'Wo': -0.1,
    'Wq': -0.1, 'Ws': -0.06, 'Wu': -0.06, 'Wæ': -0.1, 'Wœ': -0.1, 'W.': -0.1, 'W,': -0.1, 'Wà': -0.12, 'Wâ': -0.11,
    'Wä': -0.11, 'Wé': -0.12, 'Wè': -0.12, 'Wê': -0.12, 'Wë': -0.11, 'Wô': -0.11, 'Wö': -0.11, 'Wù': -0.06,
    'Wû': -0.06, 'Wü': -0.06, 'Wç': -0.1, 'WÀ': -0.15, 'WÂ': -0.15, 'WÄ': -0.15, 'WÇ': -0.07, 'WÔ': -0.07,
    'WÖ': -0.07, 'WŒ': -0.07, 'XC': -0.13, 'XG': -0.13, 'XO': -0.12, 'XQ': -0.12, 'Xa': -0.09, 'Xc': -0.09,
    'Xd': -0.09, 'Xe': -0.09, 'Xg': -0.09, 'Xo': -0.09, 'Xq': -0.09, 'Xu': -0.08, 'Xv': -0.08, 'Xw': -0.08,
    'Xy': -0.08, 'Xæ': -0.09, 'Xœ': -0.09, 'X-': -0.09, 'Xà': -0.09, 'Xâ': -0.09, 'Xä': -0.09, 'Xé': -0.09,
    'Xè': -0.09, 'Xê': -0.09, 'Xë': -0.09, 'Xô': -0.09, 'Xö': -0.09, 'Xù': -0.08, 'Xû': -0.08, 'Xü': -0.08,
    'Xç': -0.09, 'XÇ': -0.13, 'XÔ': -0.12, 'XÖ': -0.12, 'XŒ': -0.13, 'YA': -0.15, 'YC': -0.15, 'YG': -0.15,
    'YJ': -0.15, 'YO': -0.15, 'YQ': -0.15, 'Ya': -0.15, 'Yc': -0.15, 'Yd': -0.15, 'Ye': -0.15, 'Yg': -0.15,
    'Yo': -0.15, 'Yq': -0.15, 'Ys': -0.15, 'Yu': -0.15, 'Yv': -0.08, 'Yw': -0.08, 'Yx': -0.08, 'Yy': -0.08,
    'Yæ': -0.15, 'Yœ': -0.15, 'Y.': -0.1, 'Y,': -0.1, 'Y-': -0.1, 'Yà': -0.15, 'Yâ': -0.15, 'Yä': -0.15, 'Yé': -0.15,
    'Yè': -0.15, 'Yê': -0.15, 'Yë': -0.15, 'Yô': -0.15, 'Yö': -0.15, 'Yù': -0.15, 'Yû': -0.15, 'Yü': -0.15,
    'Yç': -0.15, 'YÀ': -0.15, 'YÂ': -0.15, 'YÄ': -0.15, 'YÇ': -0.15, 'YÔ': -0.15, 'YÖ': -0.15, 'YŒ': -0.15,
    'ΓA': -0.15, 'ΓC': -0.15, 'ΓG': -0.15, 'ΓJ': -0.15, 'ΓO': -0.15, 'ΓQ': -0.15, 'Γa': -0.15, 'Γc': -0.15,
    'Γd': -0.15, 'Γe': -0.15, 'Γg': -0.15, 'Γo': -0.15, 'Γq': -0.15, 'Γs': -0.15, 'Γu': -0.15, 'Γv': -0.15,
    'Γw': -0.15, 'Γx': -0.15, 'Γy': -0.15, 'Γæ': -0.15, 'Γœ': -0.15, 'Γ’': -0.03, 'Γ”': -0.03, 'Γ.': -0.1, 'Γ,': -0.1,
    'Γ-': -0.1, 'Γà': -0.15, 'Γâ': -0.15, 'Γä': -0.15, 'Γé': -0.15, 'Γè': -0.15, 'Γê': -0.15, 'Γë': -0.15,
    'Γô': -0.15, 'Γö': -0.15, 'Γù': -0.15, 'Γû': -0.15, 'Γü': -0.15, 'Γç': -0.15, 'ΓÀ': -0.15, 'ΓÂ': -0.15,
    'ΓÄ': -0.15, 'ΓÇ': -0.15, 'ΓÔ': -0.15, 'ΓÖ': -0.15, 'ΓŒ': -0.15, 'ΛC': -0.11, 'ΛG': -0.11, 'ΛO': -0.11,
    'ΛQ': -0.11, 'ΛT': -0.15, 'ΛU': -0.07, 'ΛV': -0.15, 'ΛW': -0.15, 'ΛY': -0.15, 'Λa': -0.06, 'Λc': -0.06,
    'Λd': -0.07, 'Λe': -0.06, 'Λg': -0.06, 'Λo': -0.06, 'Λq': -0.06, 'Λu': -0.05, 'Λv': -0.1, 'Λw': -0.06, 'Λy': -0.1,
    'Λæ': -0.06, 'Λœ': -0.06, "Λ'": -0.1, 'Λ"': -0.1, 'Λ’': -0.1, 'Λ‘': -0.1, 'Λ”': -0.1, 'Λ“': -0.1, 'Λà': -0.07,
    'Λâ': -0.07, 'Λä': -0.07, 'Λé': -0.07, 'Λè': -0.07, 'Λê': -0.07, 'Λë': -0.07, 'Λô': -0.07, 'Λö': -0.07,
    'Λù': -0.06, 'Λû': -0.06, 'Λü': -0.06, 'Λç': -0.06, 'ΛÇ': -0.11, 'ΛÔ': -0.11, 'ΛÖ': -0.11, 'ΛÙ': -0.07,
    'ΛÛ': -0.07, 'ΛÜ': -0.07, 'ΛŒ': -0.11, 'fA': -0.15, 'fC': -0.08, 'fG': -0.08, 'fJ': -0.15, 'fO': -0.08,
    'fQ': -0.08, 'fa': -0.15, 'fc': -0.15, 'fd': -0.15, 'fe': -0.15, 'fg': -0.15, 'fo': -0.15, 'fq': -0.15,
    'fs': -0.08, 'fu': -0.08, 'fæ': -0.15, 'fœ': -0.15, 'f.': -0.1, 'f,': -0.1, 'f-': -0.1, 'fà': -0.15, 'fâ': -0.15,
    'fä': -0.15, 'fé': -0.15, 'fè': -0.15, 'fê': -0.15, 'fë': -0.15, 'fô': -0.15, 'fö': -0.15, 'fù': -0.08,
    'fû': -0.08, 'fü': -0.08, 'fç': -0.15, 'fÀ': -0.15, 'fÂ': -0.15, 'fÄ': -0.15, 'fÇ': -0.08, 'fÔ': -0.08,
    'fÖ': -0.08, 'fŒ': -0.08, 'kT': -0.15, 'kV': -0.04, 'kY': -0.1, 'ka': -0.1, 'kc': -0.1, 'kd': -0.1, 'ke': -0.1,
    'kg': -0.1, 'ko': -0.1, 'kq': -0.1, 'kæ': -0.1, 'kœ': -0.1, 'k-': -0.1, 'kà': -0.1, 'kâ': -0.1, 'kä': -0.1,
    'ké': -0.1, 'kè': -0.1, 'kê': -0.1, 'kë': -0.1, 'kô': -0.1, 'kö': -0.1, 'kç': -0.1, 'rA': -0.15, 'rJ': -0.15,
    'rT': -0.15, 'rX': -0.09, 'rY': -0.09, 'ra': -0.06, 'rc': -0.06, 'rd': -0.06, 're': -0.06, 'rg': -0.06,
    'ro': -0.06, 'rq': -0.06, 'ræ': -0.06, 'rœ': -0.06, 'r.': -0.1, 'r,': -0.1, 'r-': -0.1, 'rà': -0.06, 'râ': -0.06,
    'rä': -0.06, 'ré': -0.06, 'rè': -0.06, 'rê': -0.06, 'rë': -0.06, 'rô': -0.06, 'rö': -0.06, 'rç': -0.06,
    'rÀ': -0.15, 'rÂ': -0.15, 'rÄ': -0.15, 'vA': -0.1, 'vJ': -0.14, 'vT': -0.15, 'vX': -0.08, 'vY': -0.08,
    'va': -0.06, 'vc': -0.06, 'vd': -0.06, 've': -0.06, 'vg': -0.06, 'vo': -0.06, 'vq': -0.06, 'væ': -0.06,
    'vœ': -0.06, 'v.': -0.1, 'v,': -0.1, 'và': -0.06, 'vâ': -0.06, 'vä': -0.06, 'vé': -0.06, 'vè': -0.06, 'vê': -0.06,
    'vë': -0.06, 'vô': -0.06, 'vö': -0.06, 'vç': -0.06, 'vÀ': -0.1, 'vÂ': -0.1, 'vÄ': -0.1, 'wA': -0.06, 'wJ': -0.08,
    'wT': -0.15, 'wX': -0.08, 'wY': -0.08, 'wa': -0.03, 'wc': -0.03, 'wd': -0.03, 'we': -0.03, 'wg': -0.03,
    'wo': -0.03, 'wq': -0.03, 'wæ': -0.03, 'wœ': -0.03, 'w.': -0.07, 'w,': -0.1, 'wà': -0.03, 'wâ': -0.03,
    'wä': -0.03, 'wé': -0.03, 'wè': -0.03, 'wê': -0.03, 'wë': -0.03, 'wô': -0.03, 'wö': -0.03, 'wç': -0.03,
    'wÀ': -0.06, 'wÂ': -0.06, 'wÄ': -0.06, 'xT': -0.15, 'xY': -0.08, 'xa': -0.06, 'xc': -0.06, 'xd': -0.06,
    'xe': -0.06, 'xg': -0.06, 'xo': -0.06, 'xq': -0.06, 'xæ': -0.06, 'xœ': -0.06, 'x-': -0.09, 'xà': -0.06,
    'xâ': -0.06, 'xä': -0.06, 'xé': -0.06, 'xè': -0.06, 'xê': -0.06, 'xë': -0.06, 'xô': -0.06, 'xö': -0.06,
    'xç': -0.06, 'yA': -0.1, 'yJ': -0.14, 'yT': -0.15, 'yX': -0.08, 'yY': -0.08, 'ya': -0.06, 'yc': -0.06,
    'yd': -0.06, 'ye': -0.06, 'yg': -0.07, 'yo': -0.06, 'yq': -0.07, 'yæ': -0.06, 'yœ': -0.06, 'y.': -0.1, 'y,': -0.1,
    'yà': -0.06, 'yâ': -0.06, 'yä': -0.06, 'yé': -0.06, 'yè': -0.06, 'yê': -0.06, 'yë': -0.06, 'yô': -0.06,
    'yö': -0.06, 'yç': -0.07, 'yÀ': -0.1, 'yÂ': -0.1, 'yÄ': -0.1,
}


def kerning(left: str, right: str) -> float:
    """Crénage de la paire, en hauteur des capitales ; une lettre accentuée par-dessus, à gauche, se crène comme
    sa lettre de base (À, Ÿ, ý) ; 0 hors de la table."""
    k = _KERN.get(left + right)
    if k is None and len(left) == 1 and not left.isascii():
        d = unicodedata.normalize('NFD', left)
        if len(d) > 1 and all(0x300 <= ord(m) <= 0x30C for m in d[1:]):
            k = _KERN.get(d[0] + right)
    return k if k is not None else 0.0


def _audit() -> list:
    """Caractères dont un trait n'est pas continu (arc mal raccordé) : vide."""
    bad = []
    for ch in characters():
        gaps = []
        _contours(_layout(ch)[0], gaps)
        if gaps:
            bad.append(ch)
    return bad
