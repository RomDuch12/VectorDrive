"""Icônes dessinées au vol (aucun fichier image, aucune licence tierce).

Chaque icône est une fonction qui dessine sur 64 × 64 px avec un QPainter. Depuis le round 1157, les icônes sont en
aplats de couleur cernés à l'encre : une petite palette (encre, accent, papier, bleu, vert, or, rouge, gris) est tirée
du thème appliqué — claire sur les thèmes sombres, soutenue sur les thèmes clairs — et des aides communes (feuille,
dossier, disquette, loupe, crayon, flèche, pastille + / × / ✓, fraise, poignée…) donnent les mêmes formes aux icônes
d'une même famille. Code des couleurs : bleu = l'objet dessiné, accent = l'action (ce qui bouge, ce qui est choisi),
vert = ajout ou résultat, rouge = retrait, or = dossiers, repères et lumière, gris = métal et second plan.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QTransform

_INK_LIGHT = QColor('#2b3a55')      # encre sur fond clair
_INK_DARK = QColor('#c8d3ea')       # encre sur fond sombre (thème sombre de Windows)
_INK = _INK_LIGHT
_ACCENT = QColor('#d0451b')
_W = 3.6                            # épaisseur du cerne (px sur 64) ; les détails : _FIN
_FIN = 2.6

#: teintes d'office (un thème peut donner les siennes : clés `icon_paper`, `icon_blue`, `icon_green`, `icon_gold`,
#: `icon_red`, `icon_grey` de ses couleurs) — sur fond clair puis sur fond sombre
TEINTES = ('paper', 'blue', 'green', 'gold', 'red', 'grey')
TEINTES_CLAIR = {'paper': '#ffffff', 'blue': '#2f6fd0', 'green': '#2b9a4a', 'gold': '#e2a000', 'red': '#d6332b',
                 'grey': '#7a8698'}
TEINTES_SOMBRE = {'paper': '', 'blue': '#6aa9ff', 'green': '#5fd07d', 'gold': '#f3c24f', 'red': '#ff7b70',
                  'grey': '#98a4b8'}
_PAL: dict[str, QColor] = {}        # palette de l'icône en cours de dessin : nom → couleur
_cache: dict[tuple, QIcon] = {}
ICONS: dict = {}                    # nom → fonction de dessin (rempli famille par famille, plus bas)


def dark_theme() -> bool:
    """Fond de fenêtre sombre (thème sombre du système) ?"""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    return bool(app) and app.palette().window().color().lightness() < 128


def _inks() -> tuple[str, str]:
    """Encre et accent des icônes du thème appliqué."""
    from .theme import current
    c = current().colors
    return c.get('icon') or (_INK_DARK if dark_theme() else _INK_LIGHT).name(), c.get('icon_accent') or '#d0451b'


def _palette() -> tuple[str, ...]:
    """La palette des icônes pour le thème appliqué : encre, accent, fond, puis `TEINTES` — les teintes du thème s'il
    en donne, sinon celles d'office pour un fond clair ou sombre (sombre = l'encre est plus claire que le fond)."""
    from . import themes as T
    from .theme import current
    c = current().colors
    ink, acc = _inks()
    try:
        bg = T.hexa(*T.rgb(str(c.get('ribbon') or c.get('window') or '').split(';')[0]))
        sombre = T.luminance(ink) > T.luminance(bg)
    except (ValueError, TypeError, IndexError):
        sombre = dark_theme()
        bg = '#26292d' if sombre else '#f7f8fa'
    base = TEINTES_SOMBRE if sombre else TEINTES_CLAIR
    out = [ink, acc, bg]
    for k in TEINTES:
        v = c.get('icon_' + k)
        if not (isinstance(v, str) and T.is_color(v)):
            v = base[k] or T.mix(bg, ink, 0.24)            # papier d'un thème sombre : un ton au-dessus du fond
        out.append(v)
    return tuple(out)


def _charge(pal: tuple[str, ...]) -> None:
    """Pose la palette `pal` (voir `_palette`) pour les fonctions de dessin, avec les tons dérivés : `x_f` l'aplat
    doux de la teinte x (vers le blanc sur fond clair, vers le fond sur fond sombre), `shade` le papier ombré."""
    global _INK, _ACCENT
    from . import themes as T
    ink, acc, bg = pal[:3]
    sombre = T.luminance(ink) > T.luminance(bg)
    _PAL.clear()
    _PAL.update(ink=QColor(ink), accent=QColor(acc), bg=QColor(bg))
    for k, v in zip(TEINTES, pal[3:]):
        _PAL[k] = QColor(v)
    for k in ('accent', 'blue', 'green', 'gold', 'red', 'grey'):
        v = _PAL[k].name()
        _PAL[k + '_f'] = QColor(T.mix(v, T.mix(bg, '#000000', 0.25), 0.5) if sombre else T.mix(v, '#ffffff', 0.58))
    _PAL['shade'] = QColor(T.mix(_PAL['paper'].name(), ink, 0.22))
    _INK, _ACCENT = _PAL['ink'], _PAL['accent']


def _icon(draw) -> QIcon:
    _charge(_palette())
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    _st(p)
    draw(p)
    p.end()
    return QIcon(pm)


def icon(name: str) -> QIcon:
    """L'icône `name` aux couleurs du thème appliqué (gardée : refaite si la palette change) ; nom inconnu : la
    feuille blanche."""
    key = (name,) + _palette()
    if key not in _cache:
        _cache[key] = _icon(ICONS.get(name, _new))
    return _cache[key]


# --- plume et aplat ------------------------------------------------------------------------------------------------
def _q(c) -> QColor:
    return c if isinstance(c, QColor) else _PAL[c]


def _plume(p, c='ink', w=_W, dash=None, plat=False):
    """La plume : couleur (nom de la palette), épaisseur, pointillé (en épaisseurs de trait) ; None : sans trait."""
    if c is None:
        p.setPen(Qt.PenStyle.NoPen)
        return
    pen = QPen(_q(c), w)
    pen.setCapStyle(Qt.PenCapStyle.FlatCap if plat else Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    if dash:
        pen.setDashPattern(dash)
    p.setPen(pen)


def _aplat(p, c=None):
    p.setBrush(_q(c) if c else Qt.BrushStyle.NoBrush)


def _st(p, fill=None, c='ink', w=_W, dash=None):
    """Plume et aplat d'un coup : `_st(p, 'blue_f')` = aplat bleu cerné à l'encre."""
    _plume(p, c, w, dash)
    _aplat(p, fill)


# --- formes élémentaires (coordonnées en nombres, sans QPointF) -------------------------------------------------------
def _pts(xy):
    return [QPointF(xy[i], xy[i + 1]) for i in range(0, len(xy), 2)]


def _l(p, *xy):
    """Ligne brisée ouverte x1, y1, x2, y2… (jamais remplie)."""
    p.drawPolyline(_pts(xy))


def _pg(p, *xy):
    """Polygone fermé (rempli de l'aplat courant)."""
    p.drawPolygon(_pts(xy))


def _r(p, x, y, w, h, rad=0.0):
    if rad:
        p.drawRoundedRect(QRectF(x, y, w, h), rad, rad)
    else:
        p.drawRect(QRectF(x, y, w, h))


def _o(p, cx, cy, rx, ry=None):
    p.drawEllipse(QPointF(cx, cy), rx, rx if ry is None else ry)


def _a(p, cx, cy, r, a0, span, ry=None):
    """Arc de centre (cx, cy), de a0 sur `span` degrés (sens trigonométrique à l'écran), sans aplat."""
    ry = r if ry is None else ry
    p.drawArc(QRectF(cx - r, cy - ry, 2 * r, 2 * ry), int(a0 * 16), int(span * 16))


def _ch(*c) -> QPainterPath:
    """Chemin en abrégé : 'M' x y, 'L' x y, 'Q' cx cy x y, 'C' c1x c1y c2x c2y x y, 'A' cx cy rx ry a0 span, 'Z'."""
    path, i = QPainterPath(), 0
    while i < len(c):
        k = c[i]
        if k == 'M':
            path.moveTo(c[i + 1], c[i + 2])
            i += 3
        elif k == 'L':
            path.lineTo(c[i + 1], c[i + 2])
            i += 3
        elif k == 'Q':
            path.quadTo(c[i + 1], c[i + 2], c[i + 3], c[i + 4])
            i += 5
        elif k == 'C':
            path.cubicTo(c[i + 1], c[i + 2], c[i + 3], c[i + 4], c[i + 5], c[i + 6])
            i += 7
        elif k == 'A':
            cx, cy, rx, ry = c[i + 1:i + 5]
            path.arcTo(QRectF(cx - rx, cy - ry, 2 * rx, 2 * ry), c[i + 5], c[i + 6])
            i += 7
        elif k == 'Z':
            path.closeSubpath()
            i += 1
        else:                                               # nombres sans lettre : suite de lignes
            path.lineTo(c[i], c[i + 1])
            i += 2
    return path


def _d(p, *c):
    """Dessine le chemin `_ch(*c)` : rempli seulement s'il est fermé ('Z' à la fin)."""
    if c[-1] == 'Z':
        p.drawPath(_ch(*c))
    else:
        b = p.brush()
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(_ch(*c))
        p.setBrush(b)


def _dot(p, x, y, r=4.0, c='accent'):
    """Pastille pleine sans cerne."""
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_q(c))
    p.drawEllipse(QPointF(x, y), r, r)
    p.restore()


def _perce(p, fn):
    """Efface ce que dessine `fn(p)` (une réserve transparente autour d'un élément posé par-dessus)."""
    p.save()
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
    fn(p)
    p.restore()


# --- aides communes -----------------------------------------------------------------------------------------------
def _pointe(p, x, y, dx, dy, t=11.0, c='accent', k=0.62):
    """Pointe de flèche pleine, sommet en (x, y), tournée vers (dx, dy), longue de t."""
    n = math.hypot(dx, dy) or 1.0
    ux, uy = dx / n, dy / n
    bx, by = x - ux * t, y - uy * t
    p.save()
    _st(p, c, c, 1.6)
    _pg(p, x, y, bx - uy * t * k, by + ux * t * k, bx + uy * t * k, by - ux * t * k)
    p.restore()


def _fleche(p, x1, y1, x2, y2, c='accent', w=4.5, t=None, halo=False, double=False):
    """Flèche droite de (x1, y1) à (x2, y2) : hampe et pointe pleine (aux deux bouts : `double`) ; `halo` : une
    réserve autour, pour la détacher de ce qu'elle recouvre."""
    t = t or w * 2.4
    n = math.hypot(x2 - x1, y2 - y1) or 1.0
    ux, uy = (x2 - x1) / n, (y2 - y1) / n
    bouts = ((x2, y2, 1), (x1, y1, -1))[:2 if double else 1]

    def trace(q, grossi=0.0):
        if grossi:                                          # la silhouette élargie (réserve)
            _st(q, 'ink', 'ink', w + grossi)
            _l(q, x1, y1, x2 - ux * t * 0.5, y2 - uy * t * 0.5)
            _plume(q, 'ink', grossi)
            for ax, ay, s in bouts:
                bx, by = ax - s * ux * t, ay - s * uy * t
                _pg(q, ax, ay, bx - uy * t * 0.62, by + ux * t * 0.62, bx + uy * t * 0.62, by - ux * t * 0.62)
            return
        _plume(q, c, w)
        k = t * 0.6 if double else 0.0
        _l(q, x1 + ux * k, y1 + uy * k, x2 - ux * t * 0.6, y2 - uy * t * 0.6)
        for ax, ay, s in bouts:
            _pointe(q, ax, ay, s * ux, s * uy, t, c)
    p.save()
    if halo:
        _perce(p, lambda q: trace(q, 5.0))
    trace(p)
    p.restore()


def _noeud(p, x, y, c='accent', r=4.6, rond=False, fill='paper', w=2.6):
    """Poignée d'un point de contour : carré (ou rond) clair cerné de la couleur `c`."""
    p.save()
    _st(p, fill, c, w)
    if rond:
        _o(p, x, y, r)
    else:
        _r(p, x - r, y - r, 2 * r, 2 * r, 1.2)
    p.restore()


def _pastille(p, kind='+', cx=47.0, cy=47.0, r=13.0, c=None):
    """Pastille d'état en bas à droite : '+' (vert), 'x' et '-' (rouge), 'ok' (vert), 'i' (bleu), '*' (or) — un
    disque plein détouré d'une réserve, le signe de la couleur du fond."""
    c = c or {'+': 'green', 'ok': 'green', 'x': 'red', '-': 'red', '*': 'gold'}.get(kind, 'blue')
    _perce(p, lambda q: (_st(q, 'ink', 'ink', 1), _o(q, cx, cy, r + 3.2)))
    p.save()
    _st(p, c, c, 1)
    _o(p, cx, cy, r)
    _st(p, None, 'bg', max(3.2, r * 0.3))
    s = r * 0.52
    if kind == '+':
        _l(p, cx - s, cy, cx + s, cy)
        _l(p, cx, cy - s, cx, cy + s)
    elif kind == '-':
        _l(p, cx - s, cy, cx + s, cy)
    elif kind == 'x':
        s *= 0.8
        _l(p, cx - s, cy - s, cx + s, cy + s)
        _l(p, cx - s, cy + s, cx + s, cy - s)
    elif kind == 'ok':
        _l(p, cx - s, cy + s * 0.1, cx - s * 0.2, cy + s * 0.8, cx + s, cy - s * 0.7)
    elif kind == 'i':
        _l(p, cx, cy - s * 0.1, cx, cy + s)
        _dot(p, cx, cy - s * 0.95, r * 0.17, 'bg')
    elif kind == '*':
        for k in range(3):
            a = math.radians(60 * k + 30)
            _l(p, cx - s * math.cos(a), cy - s * math.sin(a), cx + s * math.cos(a), cy + s * math.sin(a))
    p.restore()


def _feuille(p, x=13.0, y=5.0, w=38.0, h=54.0, coin=12.0, fill='paper', lignes=(), c='ink'):
    """Feuille de papier au coin plié ; `lignes` : hauteurs de lignes d'écriture (grises)."""
    p.save()
    _st(p, fill, c)
    _pg(p, x, y, x + w - coin, y, x + w, y + coin, x + w, y + h, x, y + h)
    if coin:
        _st(p, 'shade', c, _FIN)
        _pg(p, x + w - coin, y, x + w - coin, y + coin, x + w, y + coin)
    _plume(p, 'grey', 3)
    for ly in lignes:
        _l(p, x + 7, ly, x + w - 7, ly)
    p.restore()


def _dossier(p, x=5.0, y=10.0, w=54.0, h=44.0, ouvert=False):
    """Dossier or : onglet à gauche ; `ouvert` : le rabat de devant penché."""
    p.save()
    _st(p, 'gold')
    t = w * 0.42
    e = 6 if ouvert else 0
    _d(p, 'M', x, y + h, 'L', x, y + 3, 'Q', x, y, x + 3, y, 'L', x + t - 4, y, 'L', x + t + 3, y + 7,
       'L', x + w - 3 - e, y + 7, 'L', x + w - e, y + 10, 'L', x + w - e, y + h, 'Z')
    _st(p, 'gold_f')
    if ouvert:
        _pg(p, x, y + h, x + 9, y + 19, x + w + 2, y + 19, x + w - 6, y + h)
    else:
        _r(p, x, y + 15, w, h - 15, 2)
    p.restore()


def _disquette(p, x=7.0, y=7.0, s=50.0, c='blue'):
    """Disquette : corps de couleur au coin coupé, volet de métal en haut, étiquette de papier en bas."""
    p.save()
    k = s / 50.0
    _st(p, c + '_f')
    _pg(p, x, y, x + 39 * k, y, x + s, y + 11 * k, x + s, y + s, x, y + s)
    _st(p, 'grey_f', 'ink', _FIN)
    _r(p, x + 11 * k, y, 22 * k, 15 * k)                       # volet
    _st(p, 'ink', 'ink', 1)
    _r(p, x + 24 * k, y + 3.5 * k, 4.5 * k, 8 * k)
    _st(p, 'paper', 'ink', _FIN)
    _r(p, x + 9 * k, y + 27 * k, 32 * k, 23 * k)               # étiquette
    _plume(p, 'grey', 2.6 * k)
    _l(p, x + 15 * k, y + 35 * k, x + 35 * k, y + 35 * k)
    _l(p, x + 15 * k, y + 42 * k, x + 35 * k, y + 42 * k)
    p.restore()


def _loupe(p, cx=25.0, cy=25.0, r=17.0, verre='blue_f', manche='accent', bout=56.0):
    """Loupe : verre teinté cerné à l'encre, manche de couleur vers le bas à droite."""
    p.save()
    k = 0.7071
    x0, y0 = cx + r * k, cy + r * k
    _plume(p, 'ink', 9)
    _l(p, x0 + 6, y0 + 6, bout, bout)
    _plume(p, manche, 4.5)
    _l(p, x0 + 6, y0 + 6, bout, bout)
    _plume(p, 'ink', 4.5)
    _l(p, x0, y0, x0 + 4, y0 + 4)
    _st(p, verre, 'ink', 4)
    _o(p, cx, cy, r)
    p.restore()


def _crayon(p, x1, y1, x2, y2, larg=11.0, c='gold'):
    """Crayon dont la mine est en (x1, y1) et le bout en (x2, y2) : fût de couleur, bois clair, gomme rouge."""
    p.save()
    n = math.hypot(x2 - x1, y2 - y1)
    p.translate(x1, y1)
    p.rotate(math.degrees(math.atan2(y2 - y1, x2 - x1)))
    h, t = larg / 2.0, larg * 1.15
    _st(p, c + '_f', 'ink', 3)
    _pg(p, t, -h, n - 7, -h, n - 7, h, t, h)
    _st(p, 'red_f', 'ink', 3)
    _r(p, n - 7, -h, 7, larg, 1.5)
    _st(p, 'paper', 'ink', 3)
    _pg(p, 0, 0, t, -h, t, h)
    _st(p, 'ink', 'ink', 1)
    _pg(p, 0, 0, t * 0.42, -h * 0.42, t * 0.42, h * 0.42)
    p.restore()


def _curseur(p, x=17.0, y=7.0, k=1.0, fill='paper', c='ink'):
    """Pointeur de la souris (flèche), sommet en (x, y)."""
    p.save()
    p.translate(x, y)
    p.scale(k, k)
    _st(p, fill, c)
    _pg(p, 0, 0, 0, 44, 11, 33, 19, 50, 26, 47, 18, 30, 33, 30)
    p.restore()


def _pointille(p, x, y, w, h, c='grey', ep=3.0, rad=0.0, fill=None):
    """Cadre en pointillé (sélection, zone)."""
    p.save()
    _st(p, fill, c, ep, [2.2, 2.2])
    _r(p, x, y, w, h, rad)
    p.restore()


def _lettres(p, s, size=32, rect=(2, 6, 60, 46), c=None, w=None):
    """Lettres au trait (police monotrait intégrée VD Géo), centrées dans `rect`, capitales de 0,68 × `size` px : sans
    police du système (le rendu hors écran n'en a pas), du même trait que les autres icônes."""
    from ..core import text as TX
    from .canvas import to_qpath
    try:
        path = TX.layout(s, 'VD Géo', 1.0)
        x0, y0, x1, y1 = path.bbox()
    except Exception:                                    # police intégrée illisible : l'icône sans ses lettres
        return
    cap = size * 0.68
    x, y, wd, h = rect
    t = QTransform(cap, 0, 0, -cap, x + (wd - (x1 - x0) * cap) / 2 - x0 * cap, y + h / 2 + cap * (y0 + y1) / 2)
    p.save()
    if c is not None or w is not None:
        _plume(p, c or 'ink', w or _W)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(t.map(to_qpath(path)))
    p.restore()


def _fraise(p, x=32.0, y=4.0, larg=16.0, h=50.0, c='accent'):
    """Fraise debout, axe en x, du haut y : queue de métal, goujures de couleur, bout en pointe douce."""
    p.save()
    g = larg / 2.0
    q = h * 0.36                                            # hauteur de la queue
    _st(p, 'grey_f')
    _r(p, x - g * 0.7, y, larg * 0.7, q, 1.5)
    _st(p, c + '_f')
    _d(p, 'M', x - g, y + q, 'L', x + g, y + q, 'L', x + g, y + h - 5, 'L', x, y + h, 'L', x - g, y + h - 5, 'Z')
    _plume(p, 'ink', _FIN)
    pas = (h - q - 5) / 3
    for i in range(3):
        yy = y + q + pas * (i + 0.2)
        _l(p, x - g, yy + pas * 0.75, x + g, yy)
    p.restore()


def _engrenage(p, cx=32.0, cy=32.0, r=20.0, dents=8, fill='grey_f', trou='paper'):
    """Roue dentée."""
    p.save()
    path = QPainterPath()
    r0 = r * 0.74
    d = math.pi / dents
    for i in range(dents):
        a = 2 * math.pi * i / dents
        for j, (rr, aa) in enumerate(((r0, a - d * 0.55), (r, a - d * 0.3), (r, a + d * 0.3), (r0, a + d * 0.55))):
            x, y = cx + rr * math.cos(aa), cy + rr * math.sin(aa)
            if i == 0 and j == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
    path.closeSubpath()
    _st(p, fill)
    p.drawPath(path)
    _st(p, trou, 'ink', 3)
    _o(p, cx, cy, r * 0.3)
    p.restore()


def _oeil(p, cx=32.0, cy=32.0, w=27.0, h=15.0, iris='blue'):
    """Œil : amande claire, iris de couleur."""
    p.save()
    _st(p, 'paper')
    _d(p, 'M', cx - w, cy, 'Q', cx, cy - h * 2, cx + w, cy, 'Q', cx, cy + h * 2, cx - w, cy, 'Z')
    _st(p, iris, 'ink', 3)
    _o(p, cx, cy, h * 0.62)
    _dot(p, cx, cy, h * 0.24, 'ink')
    p.restore()


def _cadenas(p, ouvert=False, c='gold'):
    """Cadenas : corps de couleur, anse de métal (levée d'un côté : ouvert)."""
    p.save()
    anse = ('M', 22, 30, 'L', 22, 18, 'A', 32, 18, 10, 10, 180, -180, 'L', 42, 21) if ouvert else \
        ('M', 22, 30, 'L', 22, 20, 'A', 32, 20, 10, 10, 180, -180, 'L', 42, 30)
    _plume(p, 'ink', 9)
    _d(p, *anse)
    _plume(p, 'grey_f', 3.4)
    _d(p, *anse)
    _st(p, c + '_f')
    _r(p, 12, 29, 40, 28, 4)
    _st(p, 'ink', 'ink', 3)
    _o(p, 32, 40, 3)
    _l(p, 32, 41, 32, 48)
    p.restore()


def _gros(p, c, w, *lignes):
    """Traits épais de couleur cernés à l'encre : chaque ligne est un n-uplet x1, y1, x2, y2…"""
    p.save()
    _plume(p, 'ink', w + 3.4)
    for xy in lignes:
        _l(p, *xy)
    _plume(p, c, w)
    for xy in lignes:
        _l(p, *xy)
    p.restore()


def _regle(p, x, y, w, h, n=6, vertical=False, c='gold_f'):
    """Règle graduée : bande de couleur et ses traits."""
    p.save()
    _st(p, c)
    _r(p, x, y, w, h, 2)
    _plume(p, 'ink', 2.4)
    for i in range(1, n):
        k = 0.55 if i % 2 == 0 else 0.34
        if vertical:
            _l(p, x, y + h * i / n, x + w * k, y + h * i / n)
        else:
            _l(p, x + w * i / n, y, x + w * i / n, y + h * k)
    p.restore()


def _losange(p, cy, fill, cx=32.0, rx=26.0, ry=11.0):
    """Un calque vu en perspective (losange couché)."""
    p.save()
    _st(p, fill)
    _pg(p, cx, cy - ry, cx + rx, cy, cx, cy + ry, cx - rx, cy)
    p.restore()


def _cote(p, x1, y1, x2, y2, c='accent', w=3.4, t=8.0):
    """Ligne de cote : flèche double fine."""
    _fleche(p, x1, y1, x2, y2, c, w, t, double=True)


def _regpoly(cx, cy, r, n, a0=90.0, r2=None):
    """Sommets d'un polygone régulier (ou d'une étoile : rayon r2 un sommet sur deux), en liste x, y…"""
    out = []
    m = n * 2 if r2 else n
    for i in range(m):
        rr = r2 if (r2 and i % 2) else r
        a = math.radians(a0 + 360.0 * i / m)
        out += [cx + rr * math.cos(a), cy - rr * math.sin(a)]
    return out


def _fenetre(p, x=6.0, y=9.0, w=52.0, h=46.0, barre='blue_f', hb=11.0, fill='paper'):
    """Fenêtre ou panneau : cadre clair et barre de titre de couleur."""
    p.save()
    _st(p, fill)
    _r(p, x, y, w, h, 3)
    _st(p, barre)
    _r(p, x, y, w, hb, 3)
    p.restore()


def _tete(p, x, y, dx, dy, t=9.0, c='accent', w=4.0):
    """Pointe de flèche ouverte (chevron), sommet en (x, y), tournée vers (dx, dy)."""
    n = math.hypot(dx, dy) or 1.0
    ux, uy = dx / n, dy / n
    p.save()
    _plume(p, c, w)
    k = t * 0.8
    _l(p, x - ux * t - uy * k, y - uy * t + ux * k, x, y, x - ux * t + uy * k, y - uy * t - ux * k)
    p.restore()


def _lettre_pleine(p, s, size, rect, c='blue_f', w=4.2):
    """Grande lettre « pleine » : le trait de couleur cerné à l'encre."""
    _lettres(p, s, size, rect, 'ink', w + 4.6)
    _lettres(p, s, size, rect, c, w)


# === fichiers ======================================================================================================
def _new(p):
    """Nouveau : la feuille blanche et son + vert."""
    _feuille(p, 10, 5)
    _pastille(p, '+')


def _open(p):
    _dossier(p, ouvert=True)


def _save(p):
    _disquette(p)


def _import(p):
    """Importer : une flèche verte entre dans la feuille."""
    _feuille(p, 20, 5, 38, 54, lignes=(22,))
    _fleche(p, 3, 40, 40, 40, 'green', 7, 17, halo=True)


def _export(p):
    """Exporter : une flèche sort de la feuille."""
    _feuille(p, 5, 5, 38, 54, lignes=(22,))
    _fleche(p, 24, 40, 61, 40, 'accent', 7, 17, halo=True)


def _print(p):
    """Imprimer : imprimante grise, feuille qui sort, voyant vert."""
    _st(p, 'paper')
    _r(p, 18, 5, 28, 18)
    _st(p, 'grey_f')
    _r(p, 6, 20, 52, 26, 5)
    _dot(p, 49, 28, 3, 'green')
    _st(p, 'paper')
    _r(p, 16, 36, 32, 22)
    _plume(p, 'grey', 3)
    _l(p, 22, 44, 42, 44)
    _l(p, 22, 51, 36, 51)


def _pdf(p):
    """BAT / PDF : la feuille au bandeau rouge."""
    _feuille(p, 12, 5, 40, 54)
    _st(p, 'red', 'ink')
    _r(p, 4, 30, 50, 21, 3)
    _lettres(p, 'PDF', 20, (4, 30, 50, 21), 'bg', 3)


def _quit(p):
    """Quitter : la porte ouverte et la flèche rouge qui sort."""
    _st(p, 'grey_f')
    _r(p, 8, 6, 30, 52)
    _st(p, 'gold_f')
    _pg(p, 8, 6, 28, 12, 28, 58, 8, 58)
    _dot(p, 22, 34, 3, 'ink')
    _fleche(p, 34, 32, 61, 32, 'red', 6.5, 15, halo=True)


ICONS.update({'new': _new, 'open': _open, 'save': _save, 'import': _import, 'export': _export, 'print': _print,
              'pdf': _pdf, 'quit': _quit})


# === édition et sélection ============================================================================================
def _undo(p):
    """Annuler : la flèche bleue qui revient."""
    _plume(p, 'blue', 6.5)
    _d(p, 'M', 20, 22, 'L', 38, 22, 'A', 38, 36, 14, 14, 90, -180, 'L', 22, 50)
    _pointe(p, 5, 22, -1, 0, 17, 'blue')


def _redo(p):
    p.translate(64, 0)
    p.scale(-1, 1)
    _undo(p)


def _copy(p):
    _feuille(p, 6, 5, 34, 42, 9, 'shade')
    _feuille(p, 23, 17, 34, 42, 10, lignes=(35, 43, 51))


def _paste(p):
    """Coller : la planchette à pince et sa feuille."""
    _st(p, 'gold_f')
    _r(p, 8, 9, 48, 50, 5)
    _st(p, 'paper', 'ink', _FIN)
    _r(p, 16, 20, 32, 33)
    _plume(p, 'grey', 3)
    _l(p, 22, 29, 42, 29)
    _l(p, 22, 37, 42, 37)
    _l(p, 22, 45, 34, 45)
    _st(p, 'grey_f')
    _r(p, 21, 4, 22, 12, 3)


def _cut(p):
    """Couper : ciseaux aux lames de métal et aux anneaux rouges."""
    _gros(p, 'grey_f', 3.4, (19, 40, 45, 7), (45, 40, 19, 7))
    _st(p, None, 'red', 5)
    _o(p, 15, 48, 8)
    _o(p, 49, 48, 8)
    _dot(p, 32, 24, 2.4, 'ink')


def _delete(p):
    _gros(p, 'red', 7, (15, 15, 49, 49), (49, 15, 15, 49))


def _duplicate(p):
    _st(p, 'grey_f')
    _r(p, 6, 6, 32, 32, 2)
    _st(p, 'blue_f')
    _r(p, 20, 20, 32, 32, 2)
    _pastille(p, '+', 51, 51, 11)


def _arrow(p):
    _curseur(p, 16, 6)


def _select_all(p):
    _pointille(p, 5, 5, 54, 54, 'accent')
    _st(p, 'blue_f')
    _r(p, 13, 14, 18, 15)
    _o(p, 42, 41, 10)


def _invert(p):
    """Inverser la sélection : ce qui était choisi ne l'est plus, et l'inverse."""
    _pointille(p, 5, 5, 54, 54, 'grey')
    _st(p, 'paper')
    _r(p, 13, 14, 18, 15)
    _st(p, 'blue_f')
    _o(p, 42, 41, 10)
    _plume(p, 'accent', 4)
    _l(p, 11, 53, 53, 11)


def _select_filter(p):
    _pointille(p, 5, 5, 54, 54, 'grey')
    _st(p, 'gold_f')
    _pg(p, 13, 15, 51, 15, 37, 32, 37, 49, 27, 44, 27, 32)


def _lasso(p):
    _st(p, 'blue_f', 'ink', 3.4, [2.4, 2.2])
    p.drawPath(_ch('M', 14, 40, 'C', 0, 10, 50, 0, 56, 24, 'C', 60, 44, 30, 50, 22, 42, 'Z'))
    _plume(p, 'accent', 4.5)
    _l(p, 20, 43, 16, 58)
    _noeud(p, 20, 42, rond=True)


def _selection_modes(p):
    _pointille(p, 5, 5, 38, 38, 'accent', fill='blue_f')
    _curseur(p, 33, 25, 0.64)


def _same(kind):
    def d(p):
        _st(p, 'accent_f')
        _r(p, 6, 8, 22, 22, 2)
        if kind == 'tool':                                   # deux formes du même outil (même couleur)
            _o(p, 47, 19, 12)
            _st(p, 'grey_f')
            _pg(p, 20, 57, 44, 57, 32, 37)
        else:                                                # deux fois la même forme
            _st(p, 'blue_f')
            _r(p, 36, 8, 22, 22, 2)
            _st(p, 'grey_f')
            _o(p, 32, 47, 11)
    return d


def _dedupe(p):
    """Doublons : deux objets l'un sur l'autre, l'un en trop."""
    _st(p, 'blue_f')
    _r(p, 6, 6, 34, 34, 2)
    _pointille(p, 15, 15, 34, 34, 'ink', 3)
    _pastille(p, 'x', 50, 50, 11)


def _oops(p):
    """Rappeler l'effacement : l'objet effacé en tirets, la flèche verte qui le ramène."""
    _pointille(p, 22, 26, 36, 32, 'grey')
    _plume(p, 'green', 5.5)
    _d(p, 'M', 10, 30, 'L', 10, 20, 'A', 25, 20, 15, 13, 180, -180, 'L', 40, 34)
    _pointe(p, 40, 46, 0, 1, 14, 'green')


ICONS.update({'undo': _undo, 'redo': _redo, 'copy': _copy, 'paste': _paste, 'cut': _cut, 'delete': _delete,
              'duplicate': _duplicate, 'select': _arrow, 'select_all': _select_all, 'invert': _invert,
              'select_filter': _select_filter, 'lasso': _lasso, 'selection_modes': _selection_modes,
              'select_same_tool': _same('tool'), 'select_same_shape': _same('shape'), 'dedupe': _dedupe,
              'oops': _oops})


# === vue ============================================================================================================
def _zoom(kind):
    def d(p):
        _loupe(p)
        if kind == 'fit':
            _st(p, 'paper', 'accent', 3.2)
            _r(p, 16, 17, 18, 16, 1.5)
            return
        _plume(p, 'ink', 4.5)
        _l(p, 17, 25, 33, 25)
        if kind == 'in':
            _l(p, 25, 17, 25, 33)
    return d


def _grid(p):
    _st(p, 'paper')
    _r(p, 6, 6, 52, 52, 3)
    _plume(p, 'blue', 2.6)
    for v in (19, 32, 45):
        _l(p, v, 8, v, 56)
        _l(p, 8, v, 56, v)
    _st(p)
    _r(p, 6, 6, 52, 52, 3)


def _measure(p):
    """Mesurer : la règle et la cote au-dessus."""
    _regle(p, 4, 28, 56, 22, 7)
    _cote(p, 5, 15, 59, 15, 'blue')


def _ruler(p):
    p.translate(32, 32)
    p.rotate(-30)
    _regle(p, -29, -10, 58, 20, 7)


def _rulers(p):
    """Règles du plan de travail : en haut et à gauche, le repère du pointeur en pointillé."""
    _regle(p, 5, 5, 54, 14, 6)
    _regle(p, 5, 5, 14, 54, 6, True)
    _st(p, 'gold_f')
    _r(p, 5, 5, 14, 14, 2)
    _plume(p, 'accent', 3, [2, 2])
    _l(p, 41, 24, 41, 58)
    _l(p, 24, 41, 58, 41)


def _guide(p):
    """Guide des commandes : la page et son i."""
    _feuille(p, 9, 5, 40, 54, lignes=(24, 32, 40))
    _pastille(p, 'i', 48, 47, 12)


def _clear_guides(p):
    _plume(p, 'blue', 3.4, [2.4, 2.2])
    _l(p, 20, 5, 20, 59)
    _l(p, 5, 20, 59, 20)
    _pastille(p, 'x', 44, 44, 13)


def _layer_tabs(p):
    """Calques en onglets : un onglet actif, un autre derrière, la page dessous."""
    _st(p, 'grey_f')
    _r(p, 31, 8, 21, 14, 3)
    _st(p, 'accent_f')
    _r(p, 6, 8, 23, 14, 3)
    _st(p, 'paper')
    _r(p, 6, 19, 52, 37, 2)
    _plume(p, 'grey', 3)
    _l(p, 14, 30, 50, 30)
    _l(p, 14, 38, 50, 38)
    _l(p, 14, 46, 36, 46)


def _tab_layers(p):
    _losange(p, 44, 'grey_f')
    _losange(p, 33, 'blue_f')
    _losange(p, 21, 'accent_f')


def _fill(p):
    _st(p, 'blue')
    _o(p, 32, 32, 23)


def _fill_toggle(p):
    """Remplissage ou contour : la moitié pleine, la moitié vide."""
    _st(p, 'paper')
    _r(p, 8, 10, 48, 44, 2)
    _st(p, 'accent')
    _r(p, 8, 10, 24, 44, 2)


def _direction(p):
    """Sens de parcours : le contour et ses pointes."""
    _st(p, 'blue_f')
    _o(p, 32, 32, 22)
    _pointe(p, 54, 39, 0, 1, 14)
    _pointe(p, 10, 25, 0, -1, 14)


def _view_2d(p):
    _st(p, 'paper')
    _r(p, 6, 10, 52, 44, 3)
    _plume(p, 'accent', 4.5)
    _l(p, 14, 44, 26, 26, 36, 38, 50, 20)


def _view_3d(p):
    """Vue 3D : le cube aux trois faces de couleur."""
    _st(p, 'gold_f')
    _pg(p, 32, 6, 56, 18, 32, 30, 8, 18)
    _st(p, 'green_f')
    _pg(p, 8, 18, 32, 30, 32, 58, 8, 46)
    _st(p, 'blue_f')
    _pg(p, 56, 18, 32, 30, 32, 58, 56, 46)


def _view_plane(kind):
    def d(p):
        _l(p, 8, 6, 8, 56, 58, 56)
        _st(p, 'green_f' if kind == 'yz' else 'blue_f')
        _r(p, 18, 34, 32, 16, 2)
        _lettres(p, kind.upper(), 22, (16, 6, 40, 24), 'accent', 3.2)
    return d


def _eye(kind):
    def d(p):
        _oeil(p)
        if kind == 'hide':
            _gros(p, 'red', 4, (10, 54, 54, 10))
    return d


def _freeze(kind):
    def d(p):
        _cadenas(p, kind == 'unfreeze', 'gold' if kind == 'freeze' else 'green')
    return d


def _theme_dark(p):
    """Thème sombre : le croissant de lune et deux étoiles."""
    a, b = QPainterPath(), QPainterPath()
    a.addEllipse(QPointF(28, 34), 23, 23)
    b.addEllipse(QPointF(40, 24), 19, 19)
    _st(p, 'gold_f')
    p.drawPath(a.subtracted(b))
    _dot(p, 46, 14, 3, 'gold')
    _dot(p, 55, 30, 2.4, 'gold')


def _themes(p):
    """Thèmes : la palette du peintre."""
    _st(p, 'paper')
    _d(p, 'M', 32, 8, 'C', 50, 8, 60, 20, 58, 34, 'C', 56, 46, 44, 44, 40, 48, 'C', 37, 52, 42, 58, 32, 58,
       'C', 16, 58, 5, 46, 5, 32, 'C', 5, 18, 16, 8, 32, 8, 'Z')
    for x, y, c in ((18, 28, 'red'), (29, 18, 'gold'), (43, 20, 'green'), (48, 33, 'blue')):
        _st(p, c, 'ink', 2)
        _o(p, x, y, 5)
    _st(p, 'bg', 'ink', 2.6)
    _o(p, 22, 44, 5)


def _ribbon(p):
    """Ruban : la barre en haut de la fenêtre, repliée ou montrée."""
    _st(p, 'blue_f')
    _r(p, 5, 8, 54, 18, 3)
    _plume(p, 'ink', 3)
    _l(p, 13, 17, 23, 17)
    _l(p, 30, 17, 40, 17)
    _fleche(p, 32, 33, 32, 59, 'accent', 5.5, 14)


def _plate(p):
    """La plaque à graver : laiton aux quatre trous."""
    _st(p, 'gold_f')
    _r(p, 5, 13, 54, 38, 7)
    for x in (14, 50):
        for y in (22, 42):
            _dot(p, x, y, 2.6, 'ink')


def _center_plate(p):
    _st(p, 'gold_f')
    _r(p, 5, 11, 54, 42, 6)
    _st(p, 'blue_f')
    _o(p, 32, 32, 11)
    _plume(p, 'accent', 3)
    _l(p, 32, 4, 32, 60)
    _l(p, 2, 32, 62, 32)


def _origin(p):
    """Origine du dessin : X en rouge, Y en vert."""
    _fleche(p, 14, 50, 59, 50, 'red', 4.5, 12)
    _fleche(p, 14, 50, 14, 5, 'green', 4.5, 12)
    _noeud(p, 14, 50, 'ink', 5.5, rond=True, fill='gold')


def _magnet(p):
    """Accrochage : l'aimant rouge aux bouts de métal."""
    u = ('M', 14, 7, 'L', 14, 34, 'A', 32, 34, 18, 18, 180, 180, 'L', 50, 7)
    _plume(p, 'ink', 15.5, plat=True)
    _d(p, *u)
    _plume(p, 'red', 8.5, plat=True)
    _d(p, 'M', 14, 10.5, 'L', 14, 34, 'A', 32, 34, 18, 18, 180, 180, 'L', 50, 10.5)
    _plume(p, 'paper', 8.5, plat=True)
    _l(p, 14, 10.5, 14, 20)
    _l(p, 50, 10.5, 50, 20)
    _plume(p, 'ink', 2.4)
    _l(p, 7, 21, 21, 21)
    _l(p, 43, 21, 57, 21)


ICONS.update({'zoom_fit': _zoom('fit'), 'zoom_in': _zoom('in'), 'zoom_out': _zoom('out'), 'grid': _grid,
              'measure': _measure, 'ruler': _ruler, 'rulers': _rulers, 'guide': _guide,
              'clear_guides': _clear_guides, 'layer_tabs': _layer_tabs, 'tab_layers': _tab_layers, 'fill': _fill,
              'fill_toggle': _fill_toggle, 'direction': _direction, 'view_2d': _view_2d, 'view_3d': _view_3d,
              'view_yz': _view_plane('yz'), 'view_zx': _view_plane('zx'), 'hide': _eye('hide'),
              'show_all': _eye('show'), 'freeze': _freeze('freeze'), 'unfreeze': _freeze('unfreeze'),
              'theme_dark': _theme_dark, 'themes': _themes, 'ribbon': _ribbon, 'plate': _plate,
              'center_plate': _center_plate, 'origin': _origin, 'snap': _magnet})


# === outils de dessin ================================================================================================
def _rect(p):
    _st(p, 'blue_f')
    _r(p, 7, 14, 50, 36, 2)
    _noeud(p, 7, 14)
    _noeud(p, 57, 50)


def _ellipse(p):
    _st(p, 'blue_f')
    _o(p, 32, 32, 26, 19)


def _line(p):
    _plume(p, 'ink', 4.5)
    _l(p, 10, 52, 54, 12)
    _noeud(p, 10, 52)
    _noeud(p, 54, 12)


def _polygon(p):
    _st(p, 'blue_f')
    _pg(p, *_regpoly(32, 34, 25, 5))


def _star(p):
    _st(p, 'gold_f')
    _pg(p, *_regpoly(32, 35, 27, 5, 90, 11.5))


def _spiral(p):
    path = QPainterPath()
    path.moveTo(32, 32)
    for i in range(1, 181):
        th = i / 180 * 3 * 2 * math.pi
        rr = 24 * i / 180
        path.lineTo(32 + rr * math.cos(th), 32 - rr * math.sin(th))
    _st(p, None, 'blue', 4.5)
    p.drawPath(path)
    _noeud(p, 56, 32)
    _dot(p, 32, 32, 3, 'ink')


def _polyline(p):
    xy = (8, 50, 22, 18, 40, 40, 56, 12)
    _plume(p, 'ink', 4.5)
    _l(p, *xy)
    for i in range(0, 8, 2):
        _noeud(p, xy[i], xy[i + 1])


def _bezier(p):
    """Courbe de Bézier : la courbe, ses tangentes et leurs poignées."""
    _plume(p, 'accent', _FIN)
    _l(p, 10, 50, 10, 12)
    _l(p, 54, 14, 54, 52)
    _plume(p, 'ink', 4.5)
    _d(p, 'M', 10, 50, 'C', 10, 6, 54, 58, 54, 14)
    _noeud(p, 10, 12, rond=True, r=4)
    _noeud(p, 54, 52, rond=True, r=4)
    _noeud(p, 10, 50, 'ink')
    _noeud(p, 54, 14, 'ink')


def _arc(p):
    _plume(p, 'ink', 4.5)
    _d(p, 'M', 8, 48, 'Q', 32, -4, 56, 48)
    for x, y in ((8, 48), (32, 22), (56, 48)):
        _noeud(p, x, y)


def _approximate(p):
    """Approcher un contour : la ligne brisée et la courbe lisse qui la remplace."""
    _plume(p, 'grey', 3.4)
    _l(p, 6, 50, 14, 30, 22, 22, 32, 20, 42, 26, 50, 38, 58, 44)
    _plume(p, 'accent', 4.5)
    _d(p, 'M', 6, 50, 'C', 14, 6, 46, 6, 58, 44)


def _segment(p):
    """Segmenter : la courbe et les segments droits qui la remplacent."""
    _plume(p, 'grey', 3.4)
    _d(p, 'M', 6, 50, 'C', 14, 2, 50, 2, 58, 50)
    xy = (6, 50, 13, 28, 32, 15, 51, 28, 58, 50)
    _plume(p, 'accent', 4)
    _l(p, *xy)
    for i in range(0, 10, 2):
        _dot(p, xy[i], xy[i + 1], 3.6, 'ink')


def _arc_center(p):
    """Arc centre, départ, fin : le secteur, ses deux rayons et le centre."""
    _st(p, 'blue_f', None)
    p.drawPath(_ch('M', 32, 46, 'L', 56, 46, 'A', 32, 46, 24, 24, 0, 135, 'Z'))
    _plume(p, 'accent', 3)
    _l(p, 56, 46, 32, 46, 15, 29)
    _plume(p, 'ink', 4.5)
    _a(p, 32, 46, 24, 0, 135)
    _noeud(p, 32, 46, rond=True)


def _circle2(p):
    """Cercle 2 points : le cercle et son diamètre."""
    _st(p, 'blue_f')
    _o(p, 32, 32, 24)
    _plume(p, 'accent', 3)
    _l(p, 15, 49, 49, 15)
    _noeud(p, 15, 49)
    _noeud(p, 49, 15)


def _circle_center(p):
    """Cercle : le cercle, son centre et un rayon."""
    _st(p, 'blue_f')
    _o(p, 32, 32, 24)
    _plume(p, 'accent', 3)
    _l(p, 32, 32, 56, 32)
    _noeud(p, 32, 32, rond=True)
    _noeud(p, 56, 32)


def _rect3(p):
    """Rectangle 3 points : penché, son premier côté en accent."""
    _st(p, 'blue_f')
    _pg(p, 10, 44, 40, 56, 54, 21, 24, 9)
    _plume(p, 'accent', 4)
    _l(p, 10, 44, 40, 56)
    for x, y in ((10, 44), (40, 56), (54, 21)):
        _noeud(p, x, y)


def _ellipse_axis(p):
    p.save()
    p.translate(32, 32)
    p.rotate(-30)
    _st(p, 'blue_f')
    _o(p, 0, 0, 26, 14)
    _plume(p, 'accent', 3)
    _l(p, -26, 0, 26, 0)
    _noeud(p, -26, 0)
    _noeud(p, 26, 0)
    p.restore()


def _polygon_edge(p):
    xy = _regpoly(32, 32, 23, 6, -120)
    _st(p, 'blue_f')
    _pg(p, *xy)
    _plume(p, 'accent', 4)
    _l(p, *xy[:4])
    _noeud(p, xy[0], xy[1])
    _noeud(p, xy[2], xy[3])


def _text(p):
    """Texte : le grand A."""
    _lettre_pleine(p, 'A', 66, (4, 6, 56, 52))


def _tan_circle(p):
    """Cercle tangent à deux traits, points de contact marqués."""
    _plume(p, 'ink', 4)
    _l(p, 40, 6, 4, 54, 60, 54)
    _st(p, 'blue_f')
    _o(p, 32, 40, 14)
    _dot(p, 32, 54, 4.5)
    _dot(p, 20.8, 31.6, 4.5)


def _xline(p):
    """Ligne de construction : un trait qui traverse tout, par un point."""
    _plume(p, 'blue', 4)
    _l(p, 4, 54, 60, 10)
    _tete(p, 4, 54, -56, 44, 8, 'blue', 3.4)
    _tete(p, 60, 10, 56, -44, 8, 'blue', 3.4)
    _noeud(p, 32, 32, rond=True, r=5.5)


def _center_line(p):
    """Ligne d'axe : un trait mixte entre deux traits."""
    _plume(p, 'ink', 4)
    _l(p, 8, 14, 56, 14)
    _l(p, 8, 50, 56, 50)
    _plume(p, 'accent', 3.4)
    for x0, x1 in ((2, 22), (29, 35), (42, 62)):
        _l(p, x0, 32, x1, 32)


def _double_line(p):
    c = ('M', 6, 40, 'C', 20, 6, 40, 6, 58, 26)
    _plume(p, 'ink', 4.5)
    _d(p, *c)
    p.translate(0, 14)
    _plume(p, 'accent', 4)
    _d(p, *c)


def _dashes(p):
    """Courbe en tirets."""
    _plume(p, 'ink', 4.5, [2.2, 1.6], plat=True)
    _d(p, 'M', 6, 46, 'C', 20, 12, 40, 12, 58, 34)
    _plume(p, 'accent', 4.5, [1.2, 1.6], plat=True)
    _l(p, 8, 56, 56, 56)


def _equation_curve(p):
    """Courbe d'équation : les axes et la sinusoïde."""
    _plume(p, 'ink', 3.4)
    _l(p, 8, 6, 8, 58)
    _l(p, 4, 34, 60, 34)
    _plume(p, 'accent', 4.5)
    _d(p, 'M', 8, 34, 'C', 16, 2, 26, 2, 34, 34, 'C', 42, 66, 52, 66, 60, 34)


def _guilloche(p):
    for k in range(4):
        path = QPainterPath()
        for i in range(121):
            a = i / 120 * math.tau
            rr = 21 + 7 * math.sin(6 * a + k * math.pi / 2)
            q = QPointF(32 + rr * math.cos(a), 32 + rr * math.sin(a))
            if i:
                path.lineTo(q)
            else:
                path.moveTo(q)
        _st(p, None, ('blue', 'ink', 'gold', 'accent')[k], 2.2)
        p.drawPath(path)


def _marker(p):
    """Marqueur : la mire."""
    _st(p, 'paper')
    _o(p, 32, 32, 17)
    _plume(p, 'ink', 3.4)
    _l(p, 4, 32, 60, 32)
    _l(p, 32, 4, 32, 60)
    _st(p, 'accent_f', 'accent', 3.4)
    _o(p, 32, 32, 8)


def _text_path(p):
    """Lettres posées le long d'une courbe."""
    _plume(p, 'accent', 4)
    _d(p, 'M', 4, 60, 'Q', 32, 20, 60, 60)
    _plume(p, 'ink', 3.2)
    for t in (0.18, 0.5, 0.82):
        x = (1 - t) ** 2 * 4 + 2 * t * (1 - t) * 32 + t * t * 60
        y = (1 - t) ** 2 * 60 + 2 * t * (1 - t) * 20 + t * t * 60
        dx, dy = 2 * (1 - t) * 28 + 2 * t * 28, 2 * (1 - t) * -40 + 2 * t * 40
        p.save()
        p.translate(x, y)
        p.rotate(math.degrees(math.atan2(dy, dx)))
        _l(p, -6, -5, 0, -21, 6, -5)
        _l(p, -3.6, -11, 3.6, -11)
        p.restore()


def _text_arc(p):
    """Texte en arc : des lettres sur un arc."""
    _plume(p, 'blue', 4)
    _a(p, 32, 50, 26, 20, 140)
    _plume(p, 'ink', 3.2)
    for ang in (130, 90, 50):
        p.save()
        p.translate(32 + 26 * math.cos(math.radians(ang)), 50 - 26 * math.sin(math.radians(ang)))
        p.rotate(90 - ang)
        _l(p, -6, -5, 0, -20, 6, -5)
        _l(p, -3.6, -10.5, 3.6, -10.5)
        p.restore()


def _text_arcs(p):
    """Arcs de texte : deux arcs de même centre."""
    _plume(p, 'ink', 4.5)
    _a(p, 32, 46, 30, 30, 120)
    _plume(p, 'accent', 4.5)
    _a(p, 32, 46, 18, 30, 120)
    _dot(p, 32, 46, 4, 'blue')


ICONS.update({'rect': _rect, 'ellipse': _ellipse, 'line': _line, 'polygon': _polygon, 'star': _star,
              'spiral': _spiral, 'polyline': _polyline, 'bezier': _bezier, 'arc': _arc, 'approximate': _approximate,
              'segment': _segment, 'arc_center': _arc_center, 'circle2': _circle2, 'circle_center': _circle_center,
              'rect3': _rect3, 'ellipse_axis': _ellipse_axis, 'polygon_edge': _polygon_edge, 'text': _text,
              'tan_circle': _tan_circle, 'xline': _xline, 'center_line': _center_line, 'double_line': _double_line,
              'dashes': _dashes, 'equation_curve': _equation_curve, 'guilloche': _guilloche, 'marker': _marker,
              'text_path': _text_path, 'text_arc': _text_arc, 'text_arcs': _text_arcs})


# === cotes et mesures ================================================================================================
def _measure_radius(p):
    """Cercle, son centre et un rayon fléché."""
    _st(p, 'blue_f')
    _o(p, 30, 34, 22)
    _fleche(p, 30, 34, 46, 18, 'accent', 3.6, 10)
    _noeud(p, 30, 34, rond=True, r=4)


def _dim_arc(p):
    """Cote de longueur d'arc : l'arc, l'arc de cote et le symbole d'arc."""
    _plume(p, 'ink', 4.5)
    _a(p, 32, 46, 20, 15, 150)
    _plume(p, 'accent', 3.4)
    _a(p, 32, 46, 30, 15, 150)
    _plume(p, 'blue', 3.4)
    _a(p, 32, 10, 8, 0, 180, 5)


def _measure_angle(p):
    """Deux côtés et le secteur de leur angle."""
    _st(p, 'gold_f', None)
    p.drawPath(_ch('M', 8, 54, 'L', 36, 54, 'A', 8, 54, 28, 28, 0, 54.5, 'Z'))
    _plume(p, 'accent', 3.4)
    _a(p, 8, 54, 28, 0, 54.5)
    _plume(p, 'ink', 4.5)
    _l(p, 38, 12, 8, 54, 58, 54)


def _dim_jogged(p):
    """Cote radiale à ressaut."""
    _plume(p, 'ink', 4.5)
    _a(p, 10, 56, 50, 30, 60)
    _plume(p, 'accent', 3.6)
    _l(p, 8, 58, 8, 44, 20, 36, 20, 22, 27, 11)
    _pointe(p, 31, 5, 4, -7, 11)


def _dim_jog_line(p):
    """Ressaut de cote : une ligne de cote coupée d'un zigzag."""
    _plume(p, 'ink', 4)
    _l(p, 4, 20, 4, 52)
    _l(p, 60, 20, 60, 52)
    _plume(p, 'accent', 3.6)
    _l(p, 13, 36, 26, 36, 30, 24, 34, 48, 38, 36, 51, 36)
    _pointe(p, 6, 36, -1, 0, 9)
    _pointe(p, 58, 36, 1, 0, 9)


def _dim_inspect(p):
    """Cote d'inspection : la valeur dans un cadre à bouts ronds."""
    _plume(p, 'ink', 4)
    _l(p, 4, 38, 4, 56)
    _l(p, 60, 38, 60, 56)
    _cote(p, 6, 47, 58, 47, 'blue')
    _st(p, 'gold_f', 'ink', 3.2)
    _r(p, 8, 10, 48, 22, 11)
    _plume(p, 'ink', 3)
    _l(p, 38, 10, 38, 32)
    _l(p, 17, 21, 31, 21)
    _l(p, 44, 21, 50, 21)


def _dim_space(p):
    """Espacer les cotes : trois lignes de cote à intervalle égal."""
    _plume(p, 'ink', 4)
    _l(p, 7, 60, 7, 4)
    _l(p, 57, 60, 57, 4)
    for y, c in ((13, 'accent'), (32, 'blue'), (51, 'accent')):
        _cote(p, 10, y, 54, y, c, 3.2, 8)


def _gdt(p):
    """Cadre de tolérancement : trois cases, le symbole de localisation dans la première."""
    _st(p, 'paper')
    _r(p, 2, 19, 60, 26, 2)
    _st(p, 'gold_f')
    _r(p, 2, 19, 22, 26, 2)
    _plume(p, 'ink', 3)
    _l(p, 45, 19, 45, 45)
    _st(p, None, 'accent', 3)
    _o(p, 13, 32, 5)
    _l(p, 5, 32, 21, 32)
    _l(p, 13, 23, 13, 41)
    _plume(p, 'blue', 3.4)
    _l(p, 29, 32, 40, 32)
    _l(p, 49, 40, 53.5, 25, 58, 40)


def _area(p):
    """Surface : la zone teintée et hachurée."""
    xy = (10, 50, 18, 14, 52, 10, 56, 48)
    _st(p, 'accent_f')
    _pg(p, *xy)
    _plume(p, 'accent', 2.6)
    _l(p, 20, 44, 44, 16)
    _l(p, 32, 46, 52, 23)
    _l(p, 15, 34, 29, 17)
    _st(p)
    _pg(p, *xy)


def _dial(p):
    """Cadran : graduations et aiguille."""
    _st(p, 'paper')
    _o(p, 32, 32, 26)
    _plume(p, 'ink', 2.6)
    for k in range(11):
        a = math.radians(225 - 27 * k)
        r0 = 17 if k % 5 == 0 else 20
        _l(p, 32 + 23 * math.cos(a), 32 - 23 * math.sin(a), 32 + r0 * math.cos(a), 32 - r0 * math.sin(a))
    _plume(p, 'red', 4)
    _l(p, 32, 32, 45, 19)
    _dot(p, 32, 32, 4, 'ink')


def _clock(p):
    """Compteur : cadran et aiguilles."""
    _st(p, 'grey_f')
    _r(p, 27, 3, 10, 7, 2)
    _st(p, 'paper')
    _o(p, 32, 35, 23)
    _plume(p, 'accent', 4)
    _l(p, 32, 20, 32, 35, 42, 41)
    _dot(p, 32, 35, 3, 'ink')


ICONS.update({'measure_radius': _measure_radius, 'dim_arc': _dim_arc, 'measure_angle': _measure_angle,
              'dim_jogged': _dim_jogged, 'dim_jog_line': _dim_jog_line, 'dim_inspect': _dim_inspect,
              'dim_space': _dim_space, 'gdt': _gdt, 'area': _area, 'dial': _dial, 'clock': _clock})


# === transformations =================================================================================================
def _mirror_h(p):
    """Miroir : l'objet, l'axe en pointillé et son reflet."""
    _st(p, 'blue_f')
    _pg(p, 26, 12, 6, 52, 26, 52)
    _st(p, 'accent_f')
    _pg(p, 38, 12, 58, 52, 38, 52)
    _plume(p, 'ink', 3, [2, 2])
    _l(p, 32, 4, 32, 60)


def _mirror_v(p):
    p.translate(64, 0)
    p.rotate(90)
    _mirror_h(p)


def _rotate(p):
    """Tourner : l'objet et la flèche qui l'entoure."""
    _st(p, 'blue_f')
    _r(p, 22, 25, 20, 20, 2)
    _plume(p, 'accent', 4.5)
    _a(p, 32, 35, 24, 75, 245)
    _pointe(p, 50, 17.5, 0.87, 0.5, 14)


def _align(kind):
    def d(p):
        if kind in ('left', 'right', 'hcenter'):
            for y, w, c in ((12, 40, 'blue_f'), (38, 26, 'gold_f')):
                _st(p, c)
                _r(p, {'left': 10, 'right': 54 - w, 'hcenter': 32 - w / 2}[kind], y, w, 14, 2)
            x = {'left': 6, 'right': 58, 'hcenter': 32}[kind]
            _plume(p, 'accent', 4)
            _l(p, x, 4, x, 60)
        else:
            for x, h, c in ((12, 40, 'blue_f'), (38, 26, 'gold_f')):
                _st(p, c)
                _r(p, x, {'top': 10, 'bottom': 54 - h, 'vcenter': 32 - h / 2}[kind], 14, h, 2)
            y = {'top': 6, 'bottom': 58, 'vcenter': 32}[kind]
            _plume(p, 'accent', 4)
            _l(p, 4, y, 60, y)
    return d


def _align_center(p):
    """Deux objets centrés l'un sur l'autre, croix du centre."""
    _st(p, 'blue_f')
    _r(p, 8, 13, 48, 38, 2)
    _st(p, 'gold_f')
    _r(p, 21, 23, 22, 18, 2)
    _plume(p, 'accent', 3)
    _l(p, 32, 4, 32, 60)
    _l(p, 3, 32, 61, 32)


def _align_justify(p):
    _plume(p, 'ink', 4)
    for y in (13, 26, 39, 52):
        _l(p, 13, y, 51, y)
    _plume(p, 'accent', 4)
    _l(p, 5, 5, 5, 59)
    _l(p, 59, 5, 59, 59)


def _distribute(kind):
    def d(p):
        horiz = kind in ('h', 'hc')
        if not horiz:                                        # le même dessin, couché
            p.translate(64, 0)
            p.rotate(90)
        centres = kind in ('hc', 'vc')
        for k, (h, c) in enumerate(((30, 'blue_f'), (20, 'gold_f'), (30, 'blue_f'))):
            _st(p, c)
            _r(p, 5 + k * 20.5, (30 - h / 2) if centres else 44 - h, 13, h, 2)
            if centres:
                _plume(p, 'accent', 3)
                _l(p, 11.5 + k * 20.5, 6, 11.5 + k * 20.5, 54)
        _plume(p, 'accent', 4)
        if centres:
            _l(p, 4, 58, 60, 58)
        else:
            _l(p, 4, 52, 60, 52)
            _plume(p, 'accent', 3)
            for x in (22, 42.5):                             # intervalles égaux
                _l(p, x - 2.5, 20, x + 2.5, 20)
    return d


def _same_size(kind):
    def d(p):
        _st(p, 'blue_f')
        _r(p, 5, 14 if kind == 'h' else 20, 22, 36 if kind == 'h' else 24, 2)
        _st(p, 'accent_f', 'accent')
        if kind == 'w':
            _r(p, 35, 26, 22, 12, 2)
        elif kind == 'h':
            _r(p, 39, 14, 16, 36, 2)
        else:
            _r(p, 35, 20, 22, 24, 2)
    return d


def _group(p):
    _pointille(p, 4, 4, 56, 56, 'accent')
    _st(p, 'blue_f')
    _r(p, 10, 10, 26, 22, 2)
    _st(p, 'gold_f')
    _o(p, 41, 41, 14)


def _ungroup(p):
    _pointille(p, 3, 3, 30, 26, 'grey')
    _pointille(p, 30, 30, 31, 31, 'grey')
    _st(p, 'blue_f')
    _r(p, 8, 8, 20, 16, 2)
    _st(p, 'gold_f')
    _o(p, 45.5, 45.5, 10.5)


def _combine(p):
    """Combiner : le contour et son trou."""
    path = QPainterPath()
    path.addRoundedRect(QRectF(7, 11, 50, 42), 2, 2)
    path.addEllipse(QPointF(32, 32), 11, 11)
    path.setFillRule(Qt.FillRule.OddEvenFill)
    _st(p, 'blue_f')
    p.drawPath(path)


def _uncombine(p):
    _st(p, 'blue_f')
    _r(p, 6, 9, 36, 36, 2)
    _st(p, 'gold_f')
    _o(p, 46, 43, 13)


def _bool(kind):
    def d(p):
        a, b = QRectF(6, 9, 33, 33), QRectF(25, 22, 33, 33)
        pa, pb = QPainterPath(), QPainterPath()
        pa.addRect(a)
        pb.addEllipse(b)
        both = QPainterPath(pa)
        both.addPath(pb)                                      # pair-impair : la partie commune reste vide
        res = {'union': pa.united(pb), 'intersect': pa.intersected(pb), 'difference': pa.subtracted(pb),
               'xor': both}[kind]
        if kind in ('intersect', 'difference'):               # ce qui disparaît : en pointillé
            _st(p, None, 'grey', 2.6, [2, 2])
            p.drawRect(a)
            p.drawEllipse(b)
        _st(p, 'blue_f')
        p.drawPath(res)
    return d


def _offset(p):
    """Décalage : le contour et son parallèle."""
    _st(p, 'paper', 'accent', 3.6)
    _r(p, 6, 6, 52, 52, 13)
    _st(p, 'blue_f')
    _r(p, 19, 19, 26, 26, 2)


def _fillet(p):
    """Arrondi : l'angle vif en pointillé, l'arrondi en couleur."""
    _plume(p, 'grey', 3, [2, 2])
    _l(p, 8, 32, 8, 8, 32, 8)
    _plume(p, 'ink', 5)
    _l(p, 8, 58, 8, 32)
    _l(p, 32, 8, 58, 8)
    _plume(p, 'accent', 5)
    _d(p, 'M', 8, 32, 'Q', 8, 8, 32, 8)


def _chamfer(p):
    _plume(p, 'grey', 3, [2, 2])
    _l(p, 8, 30, 8, 8, 30, 8)
    _plume(p, 'ink', 5)
    _l(p, 8, 58, 8, 30)
    _l(p, 30, 8, 58, 8)
    _plume(p, 'accent', 5)
    _l(p, 8, 30, 30, 8)
    _noeud(p, 8, 30)
    _noeud(p, 30, 8)


def _fleche_arc(p, x1, x2, y, h=20.0, c='accent', w=4.0):
    """Flèche en arche de (x1, y) à (x2, y), montant de h."""
    p.save()
    _plume(p, c, w)
    _d(p, 'M', x1, y, 'C', x1 + 3, y - h, x2 - 4, y - h, x2 - 1, y - 6)
    _pointe(p, x2, y + 2, 0.25, 1, 11, c)
    p.restore()


def _transform_again(p):
    _st(p, 'blue_f')
    _r(p, 7, 34, 22, 22, 2)
    _fleche_arc(p, 18, 48, 28)


def _transform_again_copy(p):
    _st(p, 'blue_f')
    _r(p, 5, 34, 22, 22, 2)
    _pointille(p, 37, 34, 22, 22, 'ink', 3, fill='accent_f')
    _fleche_arc(p, 16, 48, 28)


def _transform_each(p):
    for x, y in ((7, 7), (36, 7), (7, 36), (36, 36)):
        _st(p, 'blue_f')
        _r(p, x, y, 21, 21, 2)
        _dot(p, x + 10.5, y + 10.5, 3.6)


def _duplicate_scaled(p):
    _plume(p, 'ink', 3.4)
    _d(p, 'M', 6, 54, 'C', 20, 10, 44, 10, 58, 30)
    for x, y, rr in ((11, 46, 5), (27, 25, 8), (47, 21, 11)):
        _st(p, 'blue_f', 'ink', 3)
        _o(p, x, y, rr)


def _order(kind):
    def d(p):
        dessus = kind in ('front', 'forward')
        for c in (('grey_f', 'accent_f') if dessus else ('accent_f', 'grey_f')):
            _st(p, c)
            if c == 'grey_f':
                _r(p, 8, 6, 30, 30, 2)
            else:
                _r(p, 26, 24, 30, 30, 2)
        if kind == 'forward':
            _fleche(p, 11, 60, 11, 42, 'green', 4.5, 11)
        elif kind == 'backward':
            _fleche(p, 11, 42, 11, 60, 'red', 4.5, 11)
    return d


def _mirror_axis(p):
    _st(p, 'blue_f')
    _pg(p, 8, 50, 24, 14, 28, 44)
    _st(p, 'accent_f')
    _pg(p, 60, 50, 44, 14, 40, 44)
    _plume(p, 'accent', 3, [2, 2])
    _l(p, 34, 4, 34, 60)


def _axis_align(kind):
    """Pièce penchée redressée autour d'un pivot, axe en pointillé."""
    def d(p):
        _st(p, None, 'grey', 3, [2, 2])
        _pg(p, 16, 50, 44, 40, 36, 18, 8, 28)
        _st(p, 'blue_f')
        if kind == 'v':
            _r(p, 16, 14, 22, 36, 1)
        else:
            _r(p, 16, 28, 36, 22, 1)
        _plume(p, 'accent', 3, [2, 2])
        if kind == 'v':
            _l(p, 16, 3, 16, 61)
        else:
            _l(p, 3, 50, 61, 50)
        _noeud(p, 16, 50, 'ink', 4.5, rond=True, fill='red')
    return d


def _contour_move(p):
    """Objet à deux contours, le petit déplacé (flèche)."""
    _st(p, 'blue_f')
    _r(p, 5, 9, 42, 46, 2)
    _st(p, None, 'ink', 2.6, [2, 2])
    _o(p, 18, 28, 8)
    _st(p, 'paper', 'accent', 3.4)
    _o(p, 46, 28, 9)
    _fleche(p, 16, 46, 44, 46, 'accent', 4, 10)


def _mirror_path(path):
    return QTransform(-1, 0, 0, 1, 64, 0).map(path)


def _sym_mark(p, h=False, v=False):
    _plume(p, 'blue', 2.6, [2.4, 2])
    if h:
        _l(p, 3, 32, 61, 32)
    if v:
        _l(p, 32, 3, 32, 61)


def _sym_draw(p):
    """Dessin symétrique : la moitié tracée, l'autre en reflet."""
    path = _ch('M', 32, 56, 'C', 50, 56, 56, 40, 46, 30, 'C', 38, 22, 52, 12, 32, 8)
    _st(p, 'blue_f', None)
    p.drawPath(path.united(_mirror_path(path)))
    _st(p, None, 'ink', 4)
    p.drawPath(path)
    _plume(p, 'accent', 4)
    p.drawPath(_mirror_path(path))
    _sym_mark(p, v=True)


def _sym_ox(p):
    path = _ch('M', 10, 32, 'C', 12, 8, 52, 8, 54, 32)
    _sym_mark(p, h=True)
    _st(p, None, 'ink', 4.5)
    p.drawPath(path)
    _plume(p, 'accent', 4.5)
    p.drawPath(QTransform(1, 0, 0, -1, 0, 64).map(path))


def _sym_oy(p):
    path = _ch('M', 32, 10, 'C', 8, 12, 8, 52, 32, 54)
    _sym_mark(p, v=True)
    _st(p, None, 'ink', 4.5)
    p.drawPath(path)
    _plume(p, 'accent', 4.5)
    p.drawPath(_mirror_path(path))


def _sym_both(p):
    path = _ch('M', 32, 10, 'C', 46, 10, 54, 18, 54, 32)
    _sym_mark(p, h=True, v=True)
    _st(p, None, 'accent', 4.5)
    for t in (QTransform(-1, 0, 0, 1, 64, 0), QTransform(1, 0, 0, -1, 0, 64), QTransform(-1, 0, 0, -1, 64, 64)):
        p.drawPath(t.map(path))
    _plume(p, 'ink', 4.5)
    p.drawPath(path)


def _sym_origin(p):
    path = _ch('M', 14, 44, 'C', 14, 26, 34, 14, 50, 26, 'C', 58, 32, 48, 48, 32, 32)
    _st(p, None, 'ink', 4.5)
    p.drawPath(path)
    _plume(p, 'accent', 4.5)
    p.drawPath(QTransform(-1, 0, 0, -1, 64, 64).map(path))
    _noeud(p, 32, 32, 'blue', 4, rond=True)


def _nest(p):
    """Englobants : les formes l'une dans l'autre."""
    _st(p, 'blue_f')
    _r(p, 5, 5, 54, 54, 2)
    _st(p, 'gold_f')
    _r(p, 16, 16, 32, 32, 2)
    _st(p, 'accent_f')
    _o(p, 32, 32, 8)


def _nesting(p):
    """Imbriquer : les pièces serrées sur la plaque."""
    _st(p, 'paper')
    _r(p, 4, 5, 56, 54, 2)
    for x, y, w, h, c in ((9, 10, 22, 15, 'blue_f'), (34, 10, 21, 25, 'gold_f'), (9, 28, 13, 26, 'green_f'),
                          (25, 38, 30, 16, 'accent_f')):
        _st(p, c, 'ink', _FIN)
        _r(p, x, y, w, h, 1)


def _fill_plate(p):
    """Multicopie : la plaque remplie de copies."""
    _st(p, 'gold_f')
    _r(p, 4, 7, 56, 50, 3)
    _st(p, 'blue_f', 'ink', 2.2)
    for i in range(3):
        for j in range(3):
            _r(p, 9.5 + i * 16.5, 12.5 + j * 14.5, 12, 10, 1)


def _bbox_frame(p):
    """Cadre englobant autour du texte."""
    _st(p, 'paper', 'accent', 3.6)
    _r(p, 5, 11, 54, 42, 7)
    _plume(p, 'ink', 4)
    _l(p, 15, 25, 49, 25)
    _l(p, 15, 39, 40, 39)


def _clip(p):
    """Rogner : ce qui reste dans le cercle."""
    a, b = QPainterPath(), QPainterPath()
    a.addRect(QRectF(5, 20, 40, 38))
    b.addEllipse(QPointF(42, 24), 19, 19)
    _st(p, None, 'grey', 2.6, [2, 2])
    p.drawPath(a)
    _st(p, 'blue_f')
    p.drawPath(a.intersected(b))
    _st(p, None, 'accent', 3.4)
    p.drawPath(b)


def _punch(p):
    """Emporte-pièce : la forme mordue par le poinçon."""
    a, b = QPainterPath(), QPainterPath()
    a.addRoundedRect(QRectF(5, 15, 42, 40), 2, 2)
    b.addEllipse(QPointF(43, 20), 15, 15)
    _st(p, 'blue_f')
    p.drawPath(a.subtracted(b))
    _st(p, 'accent_f', 'accent', 3.4)
    _o(p, 43, 20, 10)


def _trim(p):
    """Ajuster : le morceau entre les deux limites est retiré."""
    _plume(p, 'ink', 4.5)
    _l(p, 20, 5, 20, 59)
    _l(p, 44, 5, 44, 59)
    _plume(p, 'blue', 4.5)
    _l(p, 5, 32, 20, 32)
    _l(p, 44, 32, 59, 32)
    _plume(p, 'red', 3.4, [1.6, 1.8])
    _l(p, 24, 32, 41, 32)


def _extend(p):
    """Prolonger jusqu'à la limite."""
    _plume(p, 'ink', 4.5)
    _l(p, 52, 5, 52, 59)
    _plume(p, 'blue', 4.5)
    _l(p, 5, 32, 24, 32)
    _fleche(p, 28, 32, 50, 32, 'green', 4.5, 12)


def _envelope(p):
    """Enveloppe : la forme étirée entre deux courbes."""
    _st(p, 'blue_f')
    _d(p, 'M', 7, 46, 'Q', 32, 30, 57, 46, 'L', 57, 22, 'Q', 32, 2, 7, 22, 'Z')
    _plume(p, 'accent', 3)
    for k in range(1, 4):
        x = 7 + 12.5 * k
        t = (x - 7) / 50
        top = (1 - t) ** 2 * 22 + 2 * (1 - t) * t * 2 + t * t * 22
        bot = (1 - t) ** 2 * 46 + 2 * (1 - t) * t * 30 + t * t * 46
        _l(p, x, top + 4, x, bot - 4)


def _bend_path(p):
    _plume(p, 'accent', 3.4)
    for k in range(5):
        t = (k + 0.5) / 5
        u = 1 - t
        x = u ** 3 * 6 + 3 * u * u * t * 20 + 3 * u * t * t * 44 + t ** 3 * 58
        y = u ** 3 * 46 + 3 * u * u * t * 10 + 3 * u * t * t * 10 + t ** 3 * 46
        dx = 3 * u * u * 14 + 6 * u * t * 24 + 3 * t * t * 14
        dy = 3 * u * u * -36 + 3 * t * t * 36
        n = (dx * dx + dy * dy) ** 0.5 or 1.0
        _l(p, x, y, x + dy / n * 12, y - dx / n * 12)
    _plume(p, 'ink', 4.5)
    _d(p, 'M', 6, 46, 'C', 20, 10, 44, 10, 58, 46)


def _shadow(p):
    """Ombrage : la lettre et son ombre portée."""
    _lettres(p, 'S', 62, (11, 12, 50, 50), 'accent', 8)
    _lettres(p, 'S', 62, (3, 4, 50, 50), 'ink', 10)
    _lettres(p, 'S', 62, (3, 4, 50, 50), 'paper', 4.4)


def _normalize(p):
    """Intersections : le contour qui se croise, son nœud."""
    _st(p, 'blue_f')
    _pg(p, 8, 48, 56, 16, 56, 48, 8, 16)
    _noeud(p, 32, 32, r=5.5)


def _stroke(p):
    """Contour du trait : le trait épaissi autour de son axe."""
    _plume(p, 'ink', 19)
    _l(p, 15, 47, 49, 17)
    _plume(p, 'blue_f', 12.5)
    _l(p, 15, 47, 49, 17)
    _plume(p, 'accent', 3, [2, 2])
    _l(p, 15, 47, 49, 17)


def _stamp(p):
    """Tampon : poignée de bois, semelle, l'empreinte dessous."""
    _st(p, 'gold_f')
    _r(p, 27, 22, 10, 16)
    _r(p, 21, 4, 22, 22, 9)
    _st(p, 'grey_f')
    _r(p, 9, 36, 46, 13, 3)
    _plume(p, 'red', 4.5)
    _l(p, 12, 57, 52, 57)


def _explode(p):
    """Éclater : les côtés du contour, séparés."""
    _plume(p, 'ink', 4.5)
    for a in ((10, 50, 22, 14), (28, 10, 52, 10), (56, 16, 44, 52), (38, 56, 14, 56)):
        _l(p, *a)
    for x, y in ((25, 12), (54, 13), (41, 54), (12, 53)):
        _dot(p, x, y, 4.2)


def _remove_contours(p):
    _st(p, 'blue_f')
    _r(p, 5, 7, 48, 48, 2)
    _st(p, 'paper', 'ink', 2.6, [2, 2])
    _o(p, 27, 29, 12)
    _pastille(p, 'x', 50, 50, 11)


def _blend(p):
    """Raccord : deux traits reliés par un arc."""
    _plume(p, 'ink', 4.5)
    _l(p, 6, 52, 28, 52)
    _l(p, 52, 28, 52, 6)
    _plume(p, 'accent', 4.5)
    _d(p, 'M', 28, 52, 'Q', 52, 52, 52, 28)
    _noeud(p, 28, 52, r=4)
    _noeud(p, 52, 28, r=4)


def _blend_curve(p):
    """Raccord en courbe : deux traits reliés dans leur prolongement."""
    _plume(p, 'ink', 4.5)
    _l(p, 4, 46, 22, 46)
    _l(p, 42, 18, 60, 18)
    _plume(p, 'accent', 4.5)
    _d(p, 'M', 22, 46, 'C', 36, 46, 28, 18, 42, 18)
    _noeud(p, 22, 46, r=4)
    _noeud(p, 42, 18, r=4)


def _cells(p):
    """Cellules : deux volumes qui se recouvrent, leur partie commune en couleur."""
    a, b = QPainterPath(), QPainterPath()
    a.addEllipse(QPointF(22, 32), 18, 18)
    b.addEllipse(QPointF(42, 32), 18, 18)
    _st(p, 'blue_f')
    p.drawPath(a)
    p.drawPath(b)
    _st(p, 'accent')
    p.drawPath(a.intersected(b))


ICONS.update({'mirror_h': _mirror_h, 'mirror_v': _mirror_v, 'rotate': _rotate, 'align_left': _align('left'),
              'align_right': _align('right'), 'align_hcenter': _align('hcenter'), 'align_top': _align('top'),
              'align_bottom': _align('bottom'), 'align_vcenter': _align('vcenter'), 'align_center': _align_center,
              'align_justify': _align_justify, 'distribute_h': _distribute('h'), 'distribute_v': _distribute('v'),
              'distribute_hc': _distribute('hc'), 'distribute_vc': _distribute('vc'), 'same_w': _same_size('w'),
              'same_h': _same_size('h'), 'same_both': _same_size('both'), 'group': _group, 'ungroup': _ungroup,
              'combine': _combine, 'uncombine': _uncombine, 'union': _bool('union'),
              'intersect': _bool('intersect'), 'difference': _bool('difference'), 'xor': _bool('xor'),
              'offset': _offset, 'fillet': _fillet, 'chamfer': _chamfer, 'transform_again': _transform_again,
              'transform_again_copy': _transform_again_copy, 'transform_each': _transform_each,
              'duplicate_scaled': _duplicate_scaled, 'order_front': _order('front'), 'order_back': _order('back'),
              'order_forward': _order('forward'), 'order_backward': _order('backward'),
              'mirror_axis': _mirror_axis, 'axis_v': _axis_align('v'), 'axis_h': _axis_align('h'),
              'contour_move': _contour_move, 'sym_draw': _sym_draw, 'sym_ox': _sym_ox, 'sym_oy': _sym_oy,
              'sym_both': _sym_both, 'sym_origin': _sym_origin, 'nest': _nest, 'nesting': _nesting,
              'fill_plate': _fill_plate, 'bbox_frame': _bbox_frame, 'clip': _clip, 'punch': _punch, 'trim': _trim,
              'extend': _extend, 'envelope': _envelope, 'bend_path': _bend_path, 'shadow': _shadow,
              'normalize': _normalize, 'stroke': _stroke, 'stamp': _stamp, 'explode': _explode,
              'remove_contours': _remove_contours, 'blend': _blend, 'blend_curve': _blend_curve, 'cells': _cells})


# === points et contours ==============================================================================================
_ARCHE = ('M', 6, 50, 'C', 20, 6, 44, 6, 58, 50)


def _node(p):
    _plume(p, 'ink', 4.5)
    _d(p, *_ARCHE)
    for x, y in ((6, 50), (32, 17), (58, 50)):
        _noeud(p, x, y, r=5)


def _node_delete(p):
    _plume(p, 'ink', 4.5)
    _d(p, *_ARCHE)
    _noeud(p, 6, 50, r=5)
    _noeud(p, 58, 50, r=5)
    _gros(p, 'red', 4.5, (24, 8, 40, 26), (40, 8, 24, 26))


def _break(p):
    """Couper le contour en un point."""
    _plume(p, 'ink', 4.5)
    _l(p, 5, 32, 24, 32)
    _l(p, 40, 32, 59, 32)
    _noeud(p, 24, 32, r=4.4)
    _noeud(p, 40, 32, r=4.4)
    _plume(p, 'red', 4.5)
    _l(p, 28, 14, 36, 50)


def _join(p):
    """Joindre deux contours : le trait vert qui les relie."""
    _plume(p, 'ink', 4.5)
    _l(p, 6, 44, 24, 24)
    _l(p, 40, 24, 58, 44)
    _plume(p, 'green', 4.5)
    _l(p, 24, 24, 40, 24)
    _noeud(p, 24, 24, 'green', 4.4)
    _noeud(p, 40, 24, 'green', 4.4)


def _to_curves(p):
    """Convertir en courbes : la lettre et ses points."""
    _lettre_pleine(p, 'A', 66, (4, 6, 56, 52))
    for x, y in ((13, 53), (32, 9), (51, 53)):
        _noeud(p, x, y, r=4.2)


def _node_icon(kind):
    def d(p):
        if kind in ('node_line', 'node_curve'):
            droit = kind == 'node_line'
            _plume(p, 'grey', 3.4, [1.4, 1.8])
            if droit:
                _d(p, 'M', 8, 48, 'C', 20, 8, 44, 8, 56, 48)
            else:
                _l(p, 8, 48, 56, 48)
            _plume(p, 'accent', 4.5)
            if droit:
                _l(p, 8, 48, 56, 48)
            else:
                _d(p, 'M', 8, 48, 'C', 20, 8, 44, 8, 56, 48)
            _noeud(p, 8, 48, 'ink')
            _noeud(p, 56, 48, 'ink')
        elif kind in ('node_smooth', 'node_symmetric'):
            _plume(p, 'ink', 4.5)
            _d(p, 'M', 6, 52, 'C', 14, 22, 24, 22, 32, 22, 'C', 40, 22, 50, 22, 58, 52)
            a = 20 if kind == 'node_symmetric' else 10
            _plume(p, 'accent', 3)
            _l(p, 32 - a, 22, 52, 22)
            _noeud(p, 32 - a, 22, rond=True, r=3.8)
            _noeud(p, 52, 22, rond=True, r=3.8)
            _noeud(p, 32, 22, 'ink', 5)
        else:
            horiz = kind == 'node_align_h'
            _plume(p, 'accent', 3.4)
            if horiz:
                _l(p, 3, 32, 61, 32)
            else:
                _l(p, 32, 3, 32, 61)
            for t in (12, 32, 52):
                _noeud(p, t if horiz else 32, 32 if horiz else t, 'ink', 5.5)
    return d


def _node_refine(p):
    """Affiner : des points ajoutés (verts) entre les points du contour."""
    _plume(p, 'ink', 4.5)
    _d(p, 'M', 6, 48, 'C', 18, 10, 46, 10, 58, 48)
    for x, y in ((6, 48), (32, 20), (58, 48)):
        _noeud(p, x, y, 'ink')
    for x, y in ((15, 29), (49, 29)):
        _noeud(p, x, y, 'green', fill='green_f')


def _node_portion(kind):
    def d(p):
        _plume(p, 'grey', 3.4, [1.4, 1.8])
        _d(p, 'M', 6, 50, 'C', 14, 14, 50, 14, 58, 50)
        _plume(p, 'accent', 4.5)
        if kind == 'segment':
            _l(p, 6, 50, 58, 50)
        else:
            _l(p, 6, 50, 32, 12, 58, 50)
        _noeud(p, 6, 50, 'ink')
        _noeud(p, 58, 50, 'ink')
    return d


def _node_project(kind):
    """Point projeté sur un repère (trait), flèche de projection."""
    def d(p):
        _plume(p, 'blue', 4.5)
        if kind == 'perp':
            _l(p, 4, 48, 60, 20)
        else:
            _l(p, 4, 50, 60, 50)
        sx, sy = (10, 30) if kind == 'h' else (22, 12)
        if kind == 'v':
            dx, dy = 22, 50
        elif kind == 'h':
            _l(p, 50, 6, 50, 58)
            dx, dy = 50, 30
        else:
            dx, dy = 32.3, 34.9
        _fleche(p, sx, sy, dx, dy, 'accent', 3.6, 10)
        _noeud(p, sx, sy, 'ink')
    return d


def _chain(p):
    """Raccorder : les bouts voisins reliés."""
    _plume(p, 'ink', 4.5)
    _l(p, 7, 46, 24, 20)
    _l(p, 40, 20, 57, 46)
    _plume(p, 'green', 4.5)
    _l(p, 24, 20, 40, 20)
    _noeud(p, 24, 20, 'green', 4.4, rond=True)
    _noeud(p, 40, 20, 'green', 4.4, rond=True)


def _remove_loops(p):
    """Retirer les boucles."""
    _plume(p, 'ink', 4.5)
    _d(p, 'M', 5, 46, 'L', 30, 46, 'C', 52, 46, 44, 16, 32, 24, 'C', 24, 30, 30, 46, 59, 46)
    _gros(p, 'red', 4, (42, 6, 56, 20), (56, 6, 42, 20))


def _to_arcs(p):
    """Convertir en arcs : la courbe en pointillé, les arcs qui la remplacent."""
    _plume(p, 'grey', 3, [2, 2])
    _d(p, 'M', 6, 46, 'C', 22, 2, 42, 62, 58, 18)
    _plume(p, 'accent', 4.5)
    _d(p, 'M', 6, 46, 'Q', 14, 14, 32, 32, 'Q', 50, 50, 58, 18)
    for x, y in ((6, 46), (32, 32), (58, 18)):
        _noeud(p, x, y, 'ink', 4.2)


def _trace(p):
    """Vectoriser : l'image en gris, le contour retrouvé."""
    _pointille(p, 5, 5, 54, 54, 'grey', 3, fill='grey_f')
    _st(p, 'blue_f', 'accent', 4)
    _d(p, 'M', 16, 46, 'C', 10, 20, 30, 8, 44, 18, 'C', 56, 28, 44, 52, 16, 46, 'Z')
    for x, y in ((16, 46), (44, 18)):
        _noeud(p, x, y, 'ink', 4)


def _change_point(p):
    """Changer par un point : les traits et le cercle tirés vers le point cliqué."""
    _st(p, 'blue_f')
    _o(p, 40, 24, 18)
    _plume(p, 'ink', 4)
    _l(p, 5, 56, 40, 24, 5, 32)
    _plume(p, 'accent', 3.6)
    _l(p, 32, 24, 48, 24)
    _l(p, 40, 16, 40, 32)


def _snap_kind(kind):
    """Accrochage : le trait de l'objet (bleu) et la marque du point accroché."""
    def d(p):
        _plume(p, 'blue', 4.5)
        _l(p, 7, 51, 57, 13)
        _st(p, 'paper', 'accent', 3.6)
        if kind == 'node':
            _r(p, 22, 22, 20, 20, 1.5)
        elif kind == 'middle':
            _pg(p, 32, 18, 45, 42, 19, 42)
        elif kind == 'center':
            _o(p, 32, 32, 11)
            _dot(p, 32, 32, 3)
        elif kind == 'perpendicular':
            _aplat(p)
            _l(p, 32, 18, 32, 44, 46, 44)
            _l(p, 32, 37, 39, 37, 39, 44)
        elif kind == 'parallel':
            _plume(p, 'accent', 4)
            _l(p, 22, 56, 60, 27)
        elif kind == 'extension':
            _plume(p, 'accent', 3.6, [1.6, 1.8])
            _l(p, 32, 32, 57, 13)
            _noeud(p, 32, 32, r=5)
        elif kind == 'tangent':
            _o(p, 32, 37, 11)
            _plume(p, 'accent', 3.6)
            _l(p, 14, 26, 50, 26)
        elif kind == 'centroid':
            _o(p, 32, 32, 11)
            _l(p, 32, 15, 32, 49)
            _l(p, 15, 32, 49, 32)
        elif kind == 'intersection':
            _plume(p, 'blue', 4.5)
            _l(p, 8, 14, 56, 50)
            _gros(p, 'accent', 3.6, (24, 24, 40, 40), (40, 24, 24, 40))
        elif kind == 'guide':
            _plume(p, 'accent', 3.6, [1.8, 1.8])
            _l(p, 32, 4, 32, 60)
            _st(p, 'paper', 'accent', 3.6)
            _o(p, 32, 32, 7)
        elif kind == 'nearest':
            _pg(p, 21, 22, 43, 22, 21, 42, 43, 42)
        else:                                                # grille
            for x in (14, 32, 50):
                for y in (14, 32, 50):
                    _dot(p, x, y, 2.6, 'grey')
            _gros(p, 'accent', 3.4, (25, 25, 39, 39), (39, 25, 25, 39))
    return d


def _fx_scallop(p):
    """Bord en festons."""
    path = QPainterPath()
    path.moveTo(8, 14)
    for i in range(3):
        path.arcTo(QRectF(8 + 16 * i, 6, 16, 16), 180, -180)
    for j in range(2):
        path.arcTo(QRectF(48, 14 + 18 * j, 12, 18), 90, -180)
    for i in (2, 1, 0):
        path.arcTo(QRectF(8 + 16 * i, 42, 16, 16), 0, -180)
    for j in (1, 0):
        path.arcTo(QRectF(4, 14 + 18 * j, 12, 18), 270, -180)
    path.closeSubpath()
    _st(p, 'gold_f')
    p.drawPath(path)


def _match_props(p):
    """Reproduire les propriétés : le pinceau et sa trace."""
    _gros(p, 'gold', 5, (52, 6, 38, 26))
    _st(p, 'accent_f')
    _d(p, 'M', 24, 35, 'C', 16, 40, 12, 48, 8, 58, 'C', 20, 56, 30, 50, 34, 42, 'Z')
    _st(p, 'grey_f')
    _pg(p, 30, 26, 40, 33, 34, 42, 24, 35)
    _plume(p, 'accent', 4.5)
    _l(p, 40, 58, 59, 58)


ICONS.update({'node': _node, 'node_delete': _node_delete, 'break': _break, 'join': _join, 'to_curves': _to_curves,
              **{k: _node_icon(k) for k in ('node_line', 'node_curve', 'node_smooth', 'node_symmetric',
                                            'node_align_h', 'node_align_v')},
              'node_refine': _node_refine, 'node_segment': _node_portion('segment'),
              'node_angle': _node_portion('angle'), 'node_project_v': _node_project('v'),
              'node_project_h': _node_project('h'), 'node_project_perp': _node_project('perp'), 'chain': _chain,
              'remove_loops': _remove_loops, 'to_arcs': _to_arcs, 'trace': _trace, 'change_point': _change_point,
              'snap_node': _snap_kind('node'), 'snap_middle': _snap_kind('middle'),
              'snap_center': _snap_kind('center'), 'snap_grid': _snap_kind('grid'),
              'snap_centroid': _snap_kind('centroid'), 'snap_perpendicular': _snap_kind('perpendicular'),
              'snap_tangent': _snap_kind('tangent'), 'snap_extension': _snap_kind('extension'),
              'snap_parallel': _snap_kind('parallel'), 'snap_intersection': _snap_kind('intersection'),
              'snap_nearest': _snap_kind('nearest'), 'snap_guide': _snap_kind('guide'),
              'fx_scallop': _fx_scallop, 'match_props': _match_props})


# === FAO =============================================================================================================
def _cam(p):
    """FAO : la fraise."""
    _fraise(p, 32, 3, 22, 58)


def _cam_compute(p):
    """Calculer les parcours : l'aller-retour dans la poche, du départ (vert) à l'arrivée."""
    _st(p, 'paper')
    _r(p, 5, 5, 54, 54, 3)
    _plume(p, 'accent', 3.8)
    _l(p, 14, 15, 50, 15, 50, 26, 14, 26, 14, 37, 50, 37, 50, 48, 24, 48)
    _pointe(p, 14, 48, -1, 0, 10)
    _dot(p, 14, 15, 4.4, 'green')


def _cam_post(p):
    """Post-traiter : la feuille du programme machine."""
    _feuille(p, 9, 5, 42, 54)
    _lettres(p, 'G1', 19, (11, 9, 26, 16), 'blue', 3.2)
    for y, x1, c in ((32, 44, 'ink'), (40, 38, 'accent'), (48, 44, 'ink')):
        _plume(p, c, 3.2)
        _l(p, 16, y, x1, y)


def _cam_import(p):
    """Importer des parcours : la flèche verte vers le trajet."""
    _plume(p, 'blue', 4.5)
    _l(p, 6, 54, 22, 36, 40, 50, 58, 26)
    _fleche(p, 30, 4, 30, 30, 'green', 5, 13)


def _quote(p):
    """Devis : la feuille et la pièce en euro."""
    _feuille(p, 6, 5, 38, 54, lignes=(22, 30))
    _perce(p, lambda q: (_st(q, 'ink', 'ink', 1), _o(q, 43, 43, 17.5)))
    _st(p, 'gold_f')
    _o(p, 43, 43, 14.5)
    _plume(p, 'ink', 3.2)
    _a(p, 45, 43, 7.5, 55, 250)
    _l(p, 34, 40.5, 44, 40.5)
    _l(p, 34, 45.5, 43, 45.5)


def _tools(p):
    """Outils : la liste et les couleurs des outils."""
    for i, c in enumerate(('red', 'green', 'blue', 'gold')):
        _st(p, c, 'ink', 2.4)
        _r(p, 7, 6.5 + i * 13.5, 14, 10, 2)
        _plume(p, 'ink', 4)
        _l(p, 29, 11.5 + i * 13.5, 56, 11.5 + i * 13.5)


def _engrave_preview(p):
    """Aperçu de la gravure : la largeur réellement gravée autour du trait."""
    c = ('M', 9, 47, 'C', 20, 4, 40, 4, 55, 40)
    _plume(p, 'ink', 19)
    _d(p, *c)
    _plume(p, 'accent_f', 13)
    _d(p, *c)
    _plume(p, 'ink', 2.6, [2, 2])
    _d(p, *c)


def _hatch(p):
    """Hachures."""
    disque = QPainterPath()
    disque.addEllipse(QPointF(32, 32), 25, 25)
    _st(p, 'paper')
    p.drawPath(disque)
    p.save()
    p.setClipPath(disque)
    _plume(p, 'accent', 3)
    for k in range(-5, 6):
        _l(p, 6 + k * 9, 58, 58 + k * 9, 6)
    p.restore()
    _st(p)
    p.drawPath(disque)


def _holes(p):
    """Trous : la plaque et ses perçages pointés."""
    _st(p, 'grey_f')
    _r(p, 4, 4, 56, 56, 5)
    for cx in (19, 45):
        for cy in (19, 45):
            _st(p, 'bg', 'ink', 3)
            _o(p, cx, cy, 8.5)
            _plume(p, 'accent', 2.6)
            _l(p, cx - 5, cy, cx + 5, cy)
            _l(p, cx, cy - 5, cx, cy + 5)


def _perforate(p):
    """Perforer : une tôle percée de trous en quinconce."""
    _st(p, 'grey_f')
    _r(p, 4, 7, 56, 50, 3)
    _st(p, 'bg', 'ink', 2.4)
    for j, y in enumerate((18, 32, 46)):
        for x in ((16, 30, 44) if j % 2 == 0 else (23, 37, 51)):
            _o(p, x, y, 4.2)


def _coil(p):
    """Ressort : les spires, le devant en couleur."""
    _plume(p, 'grey', 4.5)
    for i in range(4):
        _l(p, 52, 51 - i * 11.5, 12, 45.2 - i * 11.5)
    _plume(p, 'accent', 5)
    for i in range(4):
        _l(p, 12, 56.8 - i * 11.5, 52, 51 - i * 11.5)


def _thread(p):
    """Filetage : la tige et ses filets."""
    _st(p, 'grey_f')
    _r(p, 20, 4, 24, 56, 2)
    _plume(p, 'accent', 3.6)
    for i in range(6):
        _l(p, 15, 16 + i * 8, 49, 10 + i * 8)


def _hole3d(p):
    """Perçage 3D : le bloc coupé, le trou lamé fini en pointe."""
    _st(p, 'grey_f')
    _pg(p, 5, 13, 18, 13, 18, 26, 26, 26, 26, 46, 32, 54, 38, 46, 38, 26, 46, 26, 46, 13, 59, 13, 59, 59, 5, 59)
    _plume(p, 'accent', 3, [3, 1.4, 1, 1.4])
    _l(p, 32, 3, 32, 61)


def _pipe(p):
    """Tube coudé, l'intérieur visible aux bouts."""
    _st(p, 'grey_f')
    _pg(p, 6, 18, 40, 18, 52, 30, 52, 58, 36, 58, 36, 38, 32, 34, 6, 34)
    _st(p, 'paper', 'ink', 3)
    _o(p, 6, 26, 3.6, 8)
    _st(p, 'accent_f', 'ink', 3)
    _o(p, 44, 58, 8, 3.2)


def _bounding(p):
    """Volume englobant : la pièce et le pavé en pointillé."""
    _st(p, 'blue_f')
    _o(p, 32, 37, 14)
    _r(p, 26, 12, 12, 13, 1)
    _pointille(p, 7, 5, 50, 54, 'accent')


def _rib(p):
    """Nervure : la coque en coupe, le mur ajouté."""
    _st(p, 'grey_f')
    _pg(p, 5, 9, 12, 9, 12, 48, 52, 48, 52, 9, 59, 9, 59, 55, 5, 55)
    _st(p, 'accent_f')
    _r(p, 28, 21, 8, 27)


def _boss(p):
    """Bossage : le fût percé et ses nervures."""
    _st(p, 'gold_f')
    _pg(p, 9, 55, 25, 32, 25, 55)
    _pg(p, 55, 55, 39, 32, 39, 55)
    _st(p, 'accent_f')
    _pg(p, 24, 55, 26, 13, 38, 13, 40, 55)
    _plume(p, 'ink', 2.6, [2, 1.6])
    _l(p, 32, 13, 32, 38)
    _plume(p, 'ink', 4)
    _l(p, 3, 56, 61, 56)


def _cylindre(p, cone=False, fill='grey_f'):
    """Pièce de révolution couchée : cylindre (ou cône)."""
    y0 = 10 if cone else 16
    hg, hd = (10, 22) if cone else (16, 16)
    _st(p, fill)
    _d(p, 'M', 10, 32 - hg, 'L', 52, y0, 'A', 52, 32, 6, hd, 90, -180, 'L', 10, 32 + hg, 'Z')
    _st(p, 'paper')
    _o(p, 10, 32, 5, hg)


def _wrap_cylinder(p):
    _cylindre(p)
    _plume(p, 'accent', 3.4)
    for x in (26, 36, 46):
        _d(p, 'M', x - 4, 21, 'Q', x + 3, 32, x - 4, 43)


def _wrap_cone(p):
    _cylindre(p, True)
    _plume(p, 'accent', 3.4)
    for x, h in ((26, 9), (36, 12), (46, 15)):
        _d(p, 'M', x - 4, 32 - h, 'Q', x + 3, 32, x - 4, 32 + h)


def _wrap_emboss(p):
    """Relief sur cylindre : la lettre posée sur son pourtour."""
    _cylindre(p)
    _plume(p, 'accent', 4.5)
    _l(p, 26, 43, 35, 21, 44, 43)
    _l(p, 30, 36, 40, 36)


def _frame(p):
    """Profilé : la poutrelle en I vue en bout, sa longueur en fuite."""
    _st(p, 'grey_f')
    _pg(p, 6, 10, 26, 4, 58, 4, 58, 48, 38, 54)
    _st(p, 'accent_f')
    _pg(p, 6, 10, 38, 10, 38, 17, 26, 17, 26, 47, 38, 47, 38, 54, 6, 54, 6, 47, 18, 47, 18, 17, 6, 17)


def _lip(p):
    """Lèvre levée sur le bord d'une coque (coupe)."""
    _gros(p, 'grey_f', 5, (9, 58, 9, 30, 26, 30), (36, 30, 36, 50, 58, 50))
    _st(p, 'accent_f')
    _r(p, 25, 10, 12, 22, 1)


def _snap_fit(p):
    """Clip : le bras et son crochet."""
    _st(p, 'accent_f')
    _pg(p, 23, 56, 23, 7, 32, 7, 45, 24, 33, 24, 33, 56)
    _plume(p, 'ink', 4)
    _l(p, 3, 57, 61, 57)


def _rest_pad(p):
    """Appui : le plot posé sur la plaque."""
    _st(p, 'accent_f')
    _pg(p, 15, 40, 21, 24, 43, 24, 49, 40)
    _st(p, 'grey_f')
    _r(p, 4, 40, 56, 17, 2)


def _bent_sheet(p):
    """Tôle pliée : le profil en U, son flan à plat dessous."""
    _plume(p, 'ink', 9)
    u = ('M', 9, 6, 'L', 9, 28, 'Q', 9, 35, 16, 35, 'L', 48, 35, 'Q', 55, 35, 55, 28, 'L', 55, 6)
    _d(p, *u)
    _plume(p, 'grey_f', 3.6)
    _d(p, *u)
    _st(p, 'gold_f')
    _r(p, 4, 46, 56, 12, 1)
    _plume(p, 'ink', 2.4, [2, 1.6])
    _l(p, 22, 46, 22, 58)
    _l(p, 42, 46, 42, 58)


def _sheet_tray(p):
    """Bac en tôle : le développé en croix, les plis en pointillé."""
    _st(p, 'grey_f')
    _pg(p, 20, 4, 44, 4, 44, 20, 60, 20, 60, 44, 44, 44, 44, 60, 20, 60, 20, 44, 4, 44, 4, 20, 20, 20)
    _pointille(p, 20, 20, 24, 24, 'accent', 3, fill='gold_f')


def _sheet_fold(p):
    """Plier la tôle : le rabat relevé."""
    _st(p, 'grey_f')
    _pg(p, 4, 57, 36, 57, 44, 41, 12, 41)
    _st(p, 'accent_f')
    _pg(p, 36, 57, 44, 41, 44, 7, 36, 23)
    _plume(p, 'blue', 3.6)
    _a(p, 50, 30, 8, 80, -150, 13)
    _pointe(p, 50, 45, -1, 0.3, 9, 'blue')


def _draft_analysis(p):
    """Analyse de dépouille : dessus vert, flancs or, dessous rouge."""
    _st(p, 'grey_f', None)
    _pg(p, 18, 34, 46, 34, 56, 57, 8, 57)
    for a, c in (((8, 57, 56, 57), 'red'), ((18, 34, 8, 57), 'gold'), ((46, 34, 56, 57), 'gold'),
                 ((18, 34, 46, 34), 'green')):
        _plume(p, c, 5.5)
        _l(p, *a)
    _fleche(p, 32, 27, 32, 3, 'blue', 4.5, 12)


def _cube(p, x, y, s, d, fill):
    _st(p, fill)
    _r(p, x, y, s, s)
    _pg(p, x, y, x + d, y - d, x + s + d, y - d, x + s, y)
    _pg(p, x + s, y, x + s + d, y - d, x + s + d, y + s - d, x + s, y + s)


def _scale3d(p):
    """Échelle 3D : le petit cube et le même agrandi."""
    _cube(p, 24, 20, 28, 9, 'accent_f')
    _cube(p, 4, 38, 17, 6, 'blue_f')


def _sheets(p):
    """Deux versions à comparer : deux feuilles décalées."""
    _st(p, 'blue_f')
    _r(p, 5, 5, 31, 41, 2)
    _st(p, 'paper')
    _r(p, 27, 17, 32, 42, 2)


def _compare(p):
    """Comparer : deux feuilles, ce qui s'ajoute et ce qui s'en va."""
    _sheets(p)
    _plume(p, 'green', 4.5)
    _l(p, 35, 29, 51, 29)
    _l(p, 43, 21, 43, 37)
    _plume(p, 'red', 4.5)
    _l(p, 35, 48, 51, 48)


def _compare_next(p):
    _sheets(p)
    _pointe(p, 53, 38, 1, 0, 17, 'accent', 0.75)


def _compare_prev(p):
    _sheets(p)
    _pointe(p, 33, 38, -1, 0, 17, 'accent', 0.75)


def _compare_close(p):
    _sheets(p)
    _gros(p, 'red', 4.5, (35, 30, 51, 46), (51, 30, 35, 46))


def _tab_paths(p):
    """FAO, les parcours : la fraise au-dessus de son trait."""
    _fraise(p, 32, 3, 18, 42)
    _plume(p, 'blue', 4.5)
    _l(p, 6, 56, 58, 56)


def _tab_ops(p):
    """FAO, les opérations : la liste et ses puces."""
    for y, c in ((14, 'accent'), (32, 'blue'), (50, 'green')):
        _dot(p, 11, y, 5.2, c)
        _plume(p, 'ink', 4.5)
        _l(p, 25, y, 56, y)


def _tab_program(p):
    """Programme machine : des lignes de code, en retrait."""
    for x0, x1, y, c in ((8, 38, 12, 'blue'), (20, 56, 25, 'ink'), (20, 46, 38, 'ink'), (8, 34, 51, 'accent')):
        _plume(p, c, 4.5)
        _l(p, x0, y, x1, y)


def _tab_dims(p):
    """Dimensions : la cote entre deux traits d'attache."""
    _plume(p, 'ink', 4.5)
    _l(p, 9, 10, 9, 54)
    _l(p, 55, 10, 55, 54)
    _fleche(p, 13, 32, 51, 32, 'accent', 4.5, 11, double=True)


def _tab_library(p):
    """Bibliothèque : quatre cases."""
    for x, y, c in ((7, 7, 'blue_f'), (35, 7, 'gold_f'), (7, 35, 'green_f'), (35, 35, 'accent_f')):
        _st(p, c)
        _r(p, x, y, 22, 22, 2)


def _tab_fonts(p):
    """Polices : le A."""
    _lettre_pleine(p, 'A', 66, (4, 6, 56, 52), 'accent_f')


def _tab_panel(p):
    """Un panneau sans icône à lui (celui d'un plugin) : une fenêtre et sa barre."""
    _fenetre(p, 7, 9, 50, 46, 'accent_f', 12)


ICONS.update({'cam': _cam, 'cam_compute': _cam_compute, 'cam_post': _cam_post, 'cam_import': _cam_import,
              'quote': _quote, 'tools': _tools, 'engrave_preview': _engrave_preview, 'hatch': _hatch,
              'holes': _holes, 'perforate': _perforate, 'coil': _coil, 'thread': _thread, 'hole3d': _hole3d,
              'pipe': _pipe, 'bounding': _bounding, 'rib': _rib, 'boss': _boss, 'wrap_cylinder': _wrap_cylinder,
              'wrap_cone': _wrap_cone, 'wrap_emboss': _wrap_emboss, 'frame': _frame, 'lip': _lip,
              'snap_fit': _snap_fit, 'rest_pad': _rest_pad, 'bent_sheet': _bent_sheet, 'sheet_tray': _sheet_tray,
              'sheet_fold': _sheet_fold, 'draft_analysis': _draft_analysis, 'scale3d': _scale3d,
              'compare': _compare, 'compare_next': _compare_next, 'compare_prev': _compare_prev,
              'compare_close': _compare_close, 'tab_paths': _tab_paths, 'tab_ops': _tab_ops,
              'tab_program': _tab_program, 'tab_dims': _tab_dims, 'tab_library': _tab_library,
              'tab_fonts': _tab_fonts, 'tab_panel': _tab_panel})


# === texte ===========================================================================================================
def _text_horizontal(p):
    """Texte : des lettres sur une ligne, la flèche de l'écriture."""
    _lettres(p, 'Ab', 40, (2, 2, 60, 38), 'ink', 4.5)
    _fleche(p, 8, 51, 56, 51, 'accent', 4.5, 12)


def _text_vertical(p):
    """Texte vertical : les lettres l'une sous l'autre, la flèche vers le bas."""
    _lettres(p, 'A', 34, (4, 2, 34, 30), 'ink', 4.5)
    _lettres(p, 'b', 34, (4, 30, 34, 30), 'ink', 4.5)
    _fleche(p, 50, 6, 50, 58, 'accent', 4.5, 12)


def _text_box(p):
    """Bloc de texte : le cadre et ses lettres."""
    _pointille(p, 4, 12, 56, 40, 'accent', 3, fill='paper')
    _lettres(p, 'Ab', 32, (4, 12, 56, 40), 'ink', 4.2)


def _case_upper(p):
    """MAJUSCULES."""
    _lettres(p, 'AB', 40, (2, 2, 60, 46), 'ink', 4.5)
    _plume(p, 'accent', 4.5)
    _l(p, 8, 56, 56, 56)


def _case_lower(p):
    """minuscules."""
    _lettres(p, 'ab', 40, (2, 2, 60, 46), 'ink', 4.5)
    _plume(p, 'blue', 4.5)
    _l(p, 8, 56, 56, 56)


def _case_words(p):
    """Majuscule Aux Mots : la capitale soulignée."""
    _lettres(p, 'Ab', 40, (2, 2, 60, 46), 'ink', 4.5)
    _plume(p, 'accent', 4.5)
    _l(p, 10, 56, 30, 56)


def _case_small(p):
    """Petites majuscules : une capitale, une petite capitale."""
    _lettres(p, 'A', 46, (0, 4, 36, 48), 'ink', 4.5)
    _lettres(p, 'A', 28, (32, 18, 30, 34), 'accent', 4)
    _plume(p, 'ink', 3)
    _l(p, 4, 57, 60, 57)


def _case_initial(p):
    """Casse initiale : « Aa » et la flèche du retour."""
    _lettres(p, 'Aa', 32, (2, 0, 60, 36), 'ink', 4.5)
    _plume(p, 'accent', 4.5)
    _a(p, 34, 42, 15, 0, -165, 11)
    _pointe(p, 17, 36, -0.3, -1, 12)


def _text_rtl(p):
    """De droite à gauche : la lettre, la flèche vers la gauche."""
    _lettres(p, 'A', 36, (22, 2, 38, 36), 'ink', 4.5)
    _fleche(p, 58, 50, 6, 50, 'accent', 4.5, 12)


def _text_on_baseline(p):
    """Sur la ligne de base : la lettre posée sur la ligne."""
    _lettres(p, 'A', 46, (4, 0, 56, 48), 'ink', 4.8)
    _plume(p, 'accent', 4.5)
    _l(p, 4, 53, 60, 53)


def _text_under_baseline(p):
    """Sous la ligne de base : la ligne au haut des capitales."""
    _plume(p, 'accent', 4.5)
    _l(p, 4, 10, 60, 10)
    _lettres(p, 'A', 46, (4, 14, 56, 48), 'ink', 4.8)


def _lines(p, x0=24, x1=58):
    _plume(p, 'ink', 4.5)
    for y in (14, 32, 50):
        _l(p, x0, y, x1, y)


def _line_fixed(p):
    """Interligne fixe : trois lignes, deux écarts égaux cotés."""
    _lines(p)
    _plume(p, 'accent', 3.6)
    _l(p, 10, 14, 10, 50)
    for y in (14, 32, 50):
        _l(p, 4, y, 16, y)


def _line_prop(p):
    """Interligne proportionnel : trois lignes et le pour-cent."""
    _lines(p, 28)
    _lettres(p, '%', 36, (0, 14, 24, 36), 'accent', 3.8)


def _line_typo(p):
    """Interligne typographique : « Ag », jambages compris entre les deux lignes."""
    _lettres(p, 'Ag', 36, (2, 6, 60, 46), 'ink', 4.5)
    _plume(p, 'accent', 3.6)
    _l(p, 4, 7, 60, 7)
    _l(p, 4, 58, 60, 58)


def _squeeze(p, y, c='accent'):
    _fleche(p, 1, y, 15, y, c, 4, 10)
    _fleche(p, 63, y, 49, y, c, 4, 10)


def _text_compress_line(p):
    """Compression ligne : une ligne serrée par les deux bouts."""
    _plume(p, 'ink', 7.5)
    _l(p, 23, 32, 41, 32)
    _squeeze(p, 32)


def _text_compress_para(p):
    """Compression paragraphe : toutes les lignes serrées ensemble."""
    _plume(p, 'ink', 5.5)
    for y, x1 in ((15, 42), (32, 38), (49, 42)):
        _l(p, 22, y, x1, y)
    _squeeze(p, 32)


def _text_compress_global(p):
    """Compression globale : les lignes à un pourcentage de la plus longue."""
    _plume(p, 'ink', 5.5)
    for y, x1 in ((15, 36), (32, 28), (49, 33)):
        _l(p, 6, y, x1, y)
    _lettres(p, '%', 36, (38, 14, 26, 36), 'accent', 3.8)


def _text_merge(p):
    """Lignes éparses réunies en un paragraphe."""
    _plume(p, 'grey', 4.5)
    for x0, x1, y in ((4, 20, 15), (10, 26, 32), (2, 18, 49)):
        _l(p, x0, y, x1, y)
    _fleche(p, 28, 32, 43, 32, 'green', 4, 10)
    _plume(p, 'ink', 4.5)
    for y in (17, 32, 47):
        _l(p, 48, y, 60, y)


def _text_columns(p):
    _plume(p, 'ink', 4)
    for x in (6, 37):
        for k in range(5):
            _l(p, x, 12 + k * 10, x + (21 if k % 2 == 0 else 15), 12 + k * 10)
    _plume(p, 'accent', 3, [2, 2])
    _l(p, 32, 5, 32, 59)


def _text_spring(p):
    """Ressort du texte : entre les bords de la ligne, un ressort qui pousse."""
    _plume(p, 'ink', 4.5)
    _l(p, 5, 12, 5, 52)
    _l(p, 59, 12, 59, 52)
    _plume(p, 'accent', 4)
    _l(p, 5, 32, 13, 32, 18, 21, 24, 43, 30, 21, 36, 43, 42, 21, 47, 32, 59, 32)


def _text_letters(p):
    """Lettres et exposants."""
    _lettres(p, 'A', 46, (0, 12, 40, 46), 'ink', 4.8)
    _lettres(p, '2', 26, (38, 2, 24, 26), 'accent', 4)


def _spell_check(p):
    """Orthographe : le mot et sa coche verte."""
    _lettres(p, 'Abc', 30, (2, 2, 60, 30), 'ink', 4)
    _gros(p, 'green', 4.5, (15, 45, 26, 56, 49, 35))


def _replace_font(p):
    """Remplacer la police : d'une lettre à l'autre."""
    _lettres(p, 'A', 38, (0, 2, 30, 34), 'ink', 4.5)
    _lettres(p, 'a', 40, (32, 26, 30, 34), 'blue', 4.5)
    _fleche(p, 10, 48, 30, 48, 'accent', 4, 10)


def _font_recognize(p):
    """Reconnaître la police : la lettre sous la loupe."""
    _lettres(p, 'A', 44, (0, 2, 38, 44), 'ink', 4.8)
    _loupe(p, 39, 39, 11, bout=60)


def _find_replace(p):
    """Rechercher / remplacer : la loupe sur une lettre."""
    _loupe(p)
    _lettres(p, 'A', 24, (12, 12, 26, 26), 'ink', 3.6)


def _text_copy_format(p):
    """Reproduire la mise en forme : le rouleau du peintre."""
    _plume(p, 'ink', 3.6)
    _l(p, 50, 15, 57, 15, 57, 30, 32, 30, 32, 38)
    _st(p, 'accent_f')
    _r(p, 8, 5, 42, 20, 5)
    _st(p, 'gold_f')
    _r(p, 27, 37, 10, 22, 3)


def _text_styles(p):
    """Préréglages de texte : des fiches empilées, la lettre devant."""
    _st(p, 'grey_f')
    _r(p, 22, 4, 37, 31, 2)
    _st(p, 'blue_f')
    _r(p, 14, 12, 37, 31, 2)
    _st(p, 'paper')
    _r(p, 5, 21, 38, 37, 2)
    _lettres(p, 'A', 30, (5, 21, 38, 37), 'accent', 4.2)


def _text_preset_save(p):
    """Enregistrer le préréglage : la disquette, la lettre sur l'étiquette."""
    _disquette(p)
    _st(p, 'paper', 'ink', _FIN)
    _r(p, 16, 34, 32, 23)
    _lettres(p, 'A', 20, (16, 34, 32, 23), 'accent', 3.6)


def _char_map(p):
    """Table des caractères : la grille, une case choisie."""
    _st(p, 'paper')
    _r(p, 5, 5, 54, 54, 2)
    _st(p, 'accent_f', None)
    _r(p, 23, 23, 18, 18)
    _plume(p, 'ink', _FIN)
    for v in (23, 41):
        _l(p, v, 5, v, 59)
        _l(p, 5, v, 59, v)
    _lettres(p, 'A', 16, (23, 23, 18, 18), 'ink', 2.8)


def _insert_variable(p):
    """Insérer une variable : la lettre entre ses accolades."""
    _lettres(p, 'A', 40, (14, 8, 36, 48), 'ink', 4.5)
    _plume(p, 'accent', 4.5)
    _l(p, 15, 8, 8, 8, 8, 56, 15, 56)
    _l(p, 49, 8, 56, 8, 56, 56, 49, 56)


def _variables(p):
    """Variables : le tableau et sa ligne de titres."""
    _st(p, 'paper')
    _r(p, 5, 8, 54, 48, 2)
    _st(p, 'blue_f')
    _r(p, 5, 8, 54, 15, 2)
    _plume(p, 'ink', _FIN)
    _l(p, 5, 39, 59, 39)
    _l(p, 27, 8, 27, 56)
    _dot(p, 43, 31, 3.4)


def _variables_produce(p):
    """Produire les variables : la série de plaques qui sort."""
    for i, c in enumerate(('grey_f', 'blue_f', 'paper')):
        _st(p, c)
        _r(p, 5 + i * 6, 5 + i * 6, 36, 27, 2)
    _fleche(p, 28, 52, 59, 52, 'green', 5, 13)


def _braille(p):
    """Braille : deux cellules de points."""
    for cx, dots in ((7, (0, 1, 3)), (36, (0, 2, 4, 5))):
        _st(p, 'paper', 'ink', 3)
        _r(p, cx, 5, 21, 54, 5)
        for k in range(6):
            _dot(p, cx + 6 + (k // 3) * 9, 15 + (k % 3) * 17, 3.4 if k in dots else 1.4, 'ink' if k in dots else 'grey')


def _barcode(p):
    """Code-barres : l'étiquette et le trait rouge du lecteur."""
    _st(p, 'paper')
    _r(p, 4, 8, 56, 48, 3)
    _st(p, 'ink', None)
    x = 10.0
    for i, w in enumerate((3, 1, 2, 1, 4, 1, 1, 3, 2, 1, 3, 1, 2, 1, 2)):
        if i % 2 == 0:
            _r(p, x, 14, w * 1.7, 36)
        x += w * 1.7
    _plume(p, 'red', 3)
    _l(p, 1, 32, 63, 32)


ICONS.update({'text_horizontal': _text_horizontal, 'text_vertical': _text_vertical, 'text_box': _text_box,
              'case_upper': _case_upper, 'case_lower': _case_lower, 'case_words': _case_words,
              'case_small': _case_small, 'case_initial': _case_initial, 'text_rtl': _text_rtl,
              'text_on_baseline': _text_on_baseline, 'text_under_baseline': _text_under_baseline,
              'line_fixed': _line_fixed, 'line_prop': _line_prop, 'line_typo': _line_typo,
              'text_compress_line': _text_compress_line, 'text_compress_para': _text_compress_para,
              'text_compress_global': _text_compress_global, 'text_merge': _text_merge,
              'text_columns': _text_columns, 'text_spring': _text_spring, 'text_letters': _text_letters,
              'spell_check': _spell_check, 'replace_font': _replace_font, 'font_recognize': _font_recognize,
              'find_replace': _find_replace, 'text_copy_format': _text_copy_format, 'text_styles': _text_styles,
              'text_preset_save': _text_preset_save, 'char_map': _char_map, 'insert_variable': _insert_variable,
              'variables': _variables, 'variables_produce': _variables_produce, 'braille': _braille,
              'barcode': _barcode})


# === effets, bibliothèque, assistant, options et aide ===============================================================
def _library(p):
    """Bibliothèque : des livres debout sur une étagère, un penché."""
    for x, y, c in ((7, 17, 'blue_f'), (19, 8, 'green_f'), (31, 15, 'accent_f')):
        _st(p, c)
        _r(p, x, y, 11, 57 - y, 1.5)
        _plume(p, 'ink', _FIN)
        _l(p, x + 3, y + 8, x + 8, y + 8)
    _st(p, 'gold_f')
    _pg(p, 44, 57, 51, 20, 60, 22, 54, 57)
    _plume(p, 'ink', 4)
    _l(p, 3, 58, 61, 58)


def _keyboard(p):
    """Raccourcis clavier : un clavier, une touche en couleur."""
    _st(p, 'grey_f')
    _r(p, 3, 14, 58, 37, 5)
    _st(p, 'paper', 'ink', 2)
    for y in (20, 30):
        for x in (8, 18, 28, 38, 48):
            _r(p, x, y, 7.5, 7, 1.5)
    _r(p, 16, 40, 26, 6, 1.5)
    _st(p, 'accent', 'ink', 2)
    _r(p, 46, 40, 10, 6, 1.5)


def _save_symbol(p):
    """Enregistrer dans la bibliothèque : l'objet et son + vert."""
    _st(p, 'blue_f')
    _r(p, 5, 5, 40, 40, 2)
    _st(p, 'gold_f')
    _o(p, 25, 25, 11)
    _pastille(p, '+', 49, 49, 12)


def _shape_script(p):
    """Script de forme : une page de lignes qui dessine."""
    _feuille(p, 5, 5, 36, 54, 10, lignes=(21, 29, 37))
    _st(p, 'accent_f')
    _pg(p, *_regpoly(46, 43, 14, 6, 0))


def _marquetry(p):
    """Marqueterie : la pièce incrustée dans son fond."""
    _st(p, 'gold_f')
    _r(p, 5, 9, 54, 46, 8)
    _st(p, 'accent_f')
    _r(p, 17, 21, 30, 22, 6)


def _leds(p):
    """LED : le boîtier et ses voyants."""
    _st(p, 'grey_f')
    _r(p, 4, 14, 56, 36, 7)
    for x, c in ((16, 'red'), (32, 'gold'), (48, 'green')):
        _st(p, c, 'ink', 2.4)
        _o(p, x, 32, 5.5)


def _cut_pattern(p):
    """Découpe en éléments : la pièce et ses traits de coupe."""
    _st(p, 'blue_f')
    _r(p, 5, 9, 54, 46, 2)
    _plume(p, 'accent', 3.6)
    _l(p, 24, 9, 24, 55)
    _l(p, 41, 9, 41, 55)
    _l(p, 5, 32, 59, 32)


def _texture(p):
    """Texture : une courbe qui remplit la surface."""
    from ..core.texture import curve_points, fit
    _st(p, 'paper')
    _r(p, 4, 4, 56, 56, 4)
    _plume(p, 'accent', 3.4)
    pts = fit(curve_points('hilbert', 2), (11, 11, 53, 53))
    _l(p, *[v for q in pts for v in q])


def _halftone(p):
    """Photo en trame : des points de plus en plus gros."""
    for i in range(6):
        for j in range(6):
            _dot(p, 7 + i * 10, 7 + j * 10, 0.7 + 4.2 * (i + j) / 10, 'blue' if i + j > 6 else 'ink')


def _check(p):
    """Vérifier : la liste et sa coche verte."""
    _feuille(p, 7, 5, 40, 54, lignes=(21, 30, 39))
    _pastille(p, 'ok', 47, 46, 13)


def _news(p):
    """Nouveautés : la page et son étoile."""
    _st(p, 'paper')
    _r(p, 8, 9, 42, 49, 4)
    _plume(p, 'grey', 3)
    for y in (26, 35, 44):
        _l(p, 16, y, 42, y)
    _st(p, 'gold', 'ink', _FIN)
    _pg(p, *_regpoly(47, 15, 13, 5, 90, 5.6))


def _command_search(p):
    """Chercher une commande : la loupe et l'invite."""
    _loupe(p)
    _plume(p, 'ink', 4)
    _l(p, 19, 18, 27, 25, 19, 32)


def _options(p):
    """Options : la roue dentée."""
    _engrenage(p, 32, 32, 27, 8, 'grey_f', 'accent_f')


def _about(p):
    """À propos : le i dans son disque bleu."""
    _st(p, 'blue')
    _o(p, 32, 32, 26)
    _plume(p, 'bg', 6.5)
    _l(p, 32, 29, 32, 46)
    _dot(p, 32, 18, 4.2, 'bg')


def _update(p):
    """Mise à jour : la flèche verte qui descend dans le cercle."""
    _st(p, 'paper')
    _o(p, 32, 32, 26)
    _fleche(p, 32, 14, 32, 48, 'green', 6.5, 16)


def _assistant(p):
    """Assistant IA : une bulle de discussion, une étincelle dedans."""
    _st(p, 'blue_f')
    _d(p, 'M', 16, 7, 'L', 48, 7, 'Q', 59, 7, 59, 18, 'L', 59, 34, 'Q', 59, 45, 48, 45, 'L', 29, 45, 'L', 14, 58,
       'L', 17, 45, 'L', 16, 45, 'Q', 5, 45, 5, 34, 'L', 5, 18, 'Q', 5, 7, 16, 7, 'Z')
    _st(p, 'gold', 'ink', 2.2)
    e = []
    for i in range(8):                                       # étincelle à quatre branches
        a = math.radians(90 + 45 * i)
        rr = 14 if i % 2 == 0 else 4.6
        e += [32 + rr * math.cos(a), 26 - rr * math.sin(a)]
    _pg(p, *e)


ICONS.update({'library': _library, 'keyboard': _keyboard, 'save_symbol': _save_symbol,
              'shape_script': _shape_script, 'marquetry': _marquetry, 'leds': _leds, 'cut_pattern': _cut_pattern,
              'texture': _texture, 'halftone': _halftone, 'check': _check, 'news': _news,
              'command_search': _command_search, 'options': _options, 'about': _about, 'update': _update,
              'assistant_ia': _assistant, 'tab_assistant': _assistant})
