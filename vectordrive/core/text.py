"""Mise en page de texte : chaîne + police + hauteur → contours exacts.

Conventions TypeEdit : la **hauteur** d'un texte est celle des capitales
(mm). Le corps (em) s'en déduit par la hauteur de capitales de la police.
Origine = point de base de la première ligne ; Y vers le haut.
"""
from __future__ import annotations

import math

from . import fonts
from .geom import Affine, Path


def em_for_height(font_file: tuple[str, int], height: float) -> float:
    m = fonts.metrics(*font_file)
    return height / (m['cap'] / m['upem'])


def _kern(font_file, left: str, right: str) -> float:
    """Crénage de la paire (unités de la police) : GPOS « kern » si la
    police en a, sinon la table « kern » ; 0 sinon."""
    from . import fontformats, svgfonts
    own = fonts.builtin(font_file[0])
    if own is not None:                              # polices monotrait intégrées : VD Géo a sa table, VD Trait aucune
        kern = getattr(own, 'kerning', None)
        return kern(left, right) if kern is not None else 0.0
    fmt = fontformats.of(font_file[0])
    if fmt is not None:                              # police lue par un plugin
        return fontformats.read_kerning(fmt, font_file[0], left, right)
    if fonts._is_svg(font_file[0]):
        return svgfonts.kerning(font_file[0], left, right)
    f = fonts.load(*font_file)
    cmap = f.getBestCmap() or {}
    a, b = cmap.get(ord(left)), cmap.get(ord(right))
    if a is None or b is None:
        return 0.0
    return fonts.kerning(*font_file)(a, b)


#: petites majuscules : hauteur des capitales réduites (part de la hauteur du texte)
SMALL_CAPS = 0.75


#: ressort (TypeEdit : fonction Ressort) : l'espace libre de la ligne est
#: partagé entre ses ressorts — texte aligné, centré, réparti sans calcul
SPRING = '\u25c6'


#: réglages d'une lettre (`extra['chars']`, position dans le texte -> valeurs) : distances en % de la hauteur du texte, pour
#: suivre son corps ; hauteur et largeur en % ; rotation en degrés. Sur une courbe, dx suit la courbe et dy s'en écarte.
#: kern décale la lettre et ce qui suit ; dx, dy la lettre seule. `font` : sa police, si ce n'est pas celle du texte.
#: `extra['chars_text']` : le texte auquel ils se rapportent.
CHAR_NEUTRAL = {'kern': 0.0, 'dx': 0.0, 'dy': 0.0, 'h': 100.0, 'w': 100.0, 'rot': 0.0}
SUPERSCRIPT = {'h': 60.0, 'dy': 45.0}
SUBSCRIPT = {'h': 60.0, 'dy': -15.0}


def clean_char_fx(fx: dict) -> dict:
    """Sans ce qui ne change rien. Hauteur et largeur restent au-dessus de zéro : une lettre écrasée n'a plus de sens."""
    out = {}
    for i, f in fx.items():
        g = {}
        for k, neutral in CHAR_NEUTRAL.items():
            v = f.get(k, neutral)
            try:
                v = float(v)
            except (TypeError, ValueError):
                continue
            if v != v or v in (float('inf'), float('-inf')):
                continue
            if k in ('h', 'w'):
                v = max(1.0, v)
            if v != neutral:
                g[k] = v
        font = f.get('font')
        if isinstance(font, str) and font.strip():
            g['font'] = font
        if g:
            out[int(i)] = g
    return out


def char_font(f: dict, height: float, ch: str):
    """Le glyphe d'une lettre dans la police que lui donne son réglage : (glyphe, chasse, échelle), ou None : celle du texte."""
    other = fonts.find_font(f['font']) if f.get('font') else None
    if not other:
        return None
    g, adv = fonts.glyph(other[0], other[1], ch)
    return g, adv, em_for_height(other, height) / fonts.metrics(*other)['upem']


def follow_edit(old: str, new: str, fx: dict) -> dict:
    """Les réglages restent sur leurs lettres quand le texte change ; ceux d'une lettre retirée s'en vont avec elle."""
    import difflib
    moved = {}
    for a, b, n in difflib.SequenceMatcher(None, old, new, autojunk=False).get_matching_blocks():
        for j in range(n):
            if a + j in fx:
                moved[b + j] = fx[a + j]
    return moved


def char_fx(t) -> dict:
    """Réglages par lettre d'un texte, {position : valeurs}. Le texte a pu changer depuis : ils suivent ses lettres."""
    raw = t.extra.get('chars')
    if not raw:
        return {}
    try:
        fx = clean_char_fx({int(k): v for k, v in raw.items()})
    except (AttributeError, TypeError, ValueError):
        return {}
    was = t.extra.get('chars_text')
    if isinstance(was, str) and was != t.text:
        fx = follow_edit(was, t.text, fx)
    return {i: f for i, f in fx.items() if 0 <= i < len(t.text)}


def set_char_fx(t, fx: dict) -> None:
    """Pose les réglages par lettre. Dictionnaire neuf : une copie du texte (annulation) peut partager l'ancien."""
    fx = clean_char_fx(fx)
    extra = {k: v for k, v in t.extra.items() if k not in ('chars', 'chars_text')}
    if fx:
        extra['chars'] = {str(i): f for i, f in sorted(fx.items())}
        extra['chars_text'] = t.text
    t.extra = extra


def _letter_fx(rows, text: str, fx: dict, ff, s: float, height: float, small_caps: bool) -> list:
    """Lignes de `_rows` avec les réglages par lettre : le crénage et la taille d'une lettre poussent ce qui la suit.
    Une lettre réglée reçoit un 4ᵉ terme (hauteur, largeur, rotation, dx, dy, avance, rapport d'échelle de sa police)."""
    out = []
    i = 0
    for placed, total, wr in rows:
        moved, shift = [], 0.0
        for g, x, k in placed:
            f = fx.get(i)
            if not f:
                moved.append((g, x + shift, k))
                i += 1
                continue
            shift += f.get('kern', 0.0) / 100.0 * height * wr      # comme les lettres : largeur du texte, ligne resserrée
            if g is None:
                moved.append((g, x + shift, k))
                i += 1
                continue
            h, w = f.get('h', 100.0) / 100.0, f.get('w', 100.0) / 100.0
            gc = _shape(text[i], small_caps)[0]
            adv = adv0 = fonts.glyph(ff[0], ff[1], gc)[1] * s * wr * k
            ratio = 1.0
            other = char_font(f, height, gc)
            if other is not None:
                g, adv, s2 = other
                adv, ratio = adv * s2 * wr * k, s2 / s
            moved.append((g, x + shift, k, (h, w, f.get('rot', 0.0), f.get('dx', 0.0) / 100.0 * height * wr,
                                            f.get('dy', 0.0) / 100.0 * height, adv, ratio)))
            shift += adv * h * w - adv0
            i += 1
        out.append((moved, total + shift, wr))
        i += 1                                           # le saut de ligne
    return out


def _letter_matrix(sx: float, sy: float, x: float, y: float, more: tuple, height: float) -> Affine:
    """Place d'une lettre réglée : mise à sa taille, tournée autour de son centre, puis décalée."""
    h, w, rot, dx, dy, adv, ratio = more
    sx, sy = sx * h * w * ratio, sy * h * ratio
    x, y = x + dx, y + dy
    if not rot:
        return Affine(sx, 0, 0, sy, x, y)
    a = math.radians(rot)
    c, n = math.cos(a), math.sin(a)
    cx, cy = adv * h * w / 2.0, height * h / 2.0         # centre de la lettre, depuis son origine
    return Affine(c * sx, n * sx, -n * sy, c * sy, x + cx - c * cx + n * cy, y + cy - n * cx - c * cy)


def _shape(ch: str, small_caps: bool) -> tuple:
    up = ch.upper()
    if small_caps and ch != up and len(up) == 1:
        return up, SMALL_CAPS
    return ch, 1.0


#: espacement d'un texte : crénage automatique (`typo`) ou non (`prop`), les mêmes sans les espaces de part et d'autre
#: des lettres (`tight_kern`, `tight`), ou chaque lettre dans une case de même largeur (`fixed`)
KERNED = ('typo', 'tight_kern')
TIGHT = ('tight', 'tight_kern')
SPACING_MODES = ('typo', 'prop', 'tight_kern', 'tight', 'fixed')


def _rows(text: str, font: str, height: float, spacing: float, width_ratio: float, kerning: bool,
          fixed: bool = False, small_caps: bool = False, line_ratios: list | None = None, tight: bool = False):
    """Lignes posées depuis leur début : (corps, échelle, [(glyphes [(glyphe,
    x, réduction)], largeur, étirement de la ligne)]), ou None (police ou
    texte absents). `line_ratios` : facteur de largeur de chaque ligne ;
    `tight` : les lettres sans les espaces qui les entourent."""
    ff = fonts.find_font(font)
    if not ff or not text:
        return None
    m = fonts.metrics(*ff)
    em = em_for_height(ff, height)
    s = em / m['upem']

    def shape(ch):
        return _shape(ch, small_caps)
    # chasse fixe : chaque caractère au milieu d'une case de la largeur du plus large du texte
    cell = max((fonts.glyph(ff[0], ff[1], shape(ch)[0])[1] * shape(ch)[1] for ch in set(text) if ch != '\n'),
               default=0.0) * s * width_ratio if fixed else 0.0
    rows = []
    for li, line in enumerate(text.split('\n')):
        f = line_ratios[li] if line_ratios and li < len(line_ratios) else 1.0
        wr, cl = width_ratio * f, cell * f
        pen = 0.0
        placed = []
        prev = None
        for ch in line:
            if ch == SPRING:                             # ressort : sans largeur, marqué (glyphe None, k 0)
                placed.append((None, pen, 0.0))
                continue
            gc, k = shape(ch)
            g, adv = fonts.glyph(ff[0], ff[1], gc)
            if fixed:
                placed.append((g, pen + (cl - adv * s * wr * k) / 2, k))
                pen += cl + spacing
                continue
            if prev is not None and kerning:
                pen += _kern(ff, prev, gc) * s * wr * k
            box = g.bbox() if tight else None
            if box:
                placed.append((g, pen - box[0] * s * wr * k, k))
                pen += (box[2] - box[0]) * s * wr * k + spacing
            else:                                        # un espace garde sa place, serré ou non
                placed.append((g, pen, k))
                pen += adv * s * wr * k + spacing
            prev = gc
        rows.append((placed, pen - spacing if line else 0.0, wr))
    return em, s, rows


def _placed(text: str, font: str, height: float, align: str, spacing: float, line_spacing: float,
            width_ratio: float, kerning: bool, fixed: bool = False, small_caps: bool = False,
            line_ratios: list | None = None, spring_width: float = 0.0, fx: dict | None = None,
            lines: list | None = None, tight: bool = False, chars: list | None = None) -> list:
    """Glyphes posés : [(glyphe, matrice)] — mise en page commune à
    `layout` et `layout_bbox`. `align` 'justify' : chaque ligne étirée à la
    largeur de la plus longue, l'écart réparti entre ses lettres (TypeEdit :
    « aligner le texte en blocs ») ; `small_caps` : minuscules dessinées en
    capitales réduites (SMALL_CAPS) ; `line_ratios` : compression de chaque
    ligne (`compression`) ; une ligne à ressorts (SPRING) est portée à
    `spring_width` (0 : la plus longue ligne), l'écart partagé entre eux ;
    `fx` : réglages par lettre (`char_fx`) ; `lines` reçoit le n° de ligne de
    chaque glyphe rendu, `chars` sa position dans le texte."""
    got = _rows(text, font, height, spacing, width_ratio, kerning, fixed, small_caps, line_ratios, tight)
    if got is None:
        return []
    em, s, rows = got
    if fx:
        rows = _letter_fx(rows, text, fx, fonts.find_font(font), s, height, small_caps)
    widest = max(total for _p, total, _w in rows)
    target = spring_width if spring_width > 0 else widest
    out = []
    next_char = 0
    for li, (placed, total, wr) in enumerate(rows):
        ids = list(range(next_char, next_char + len(placed)))
        next_char += len(placed) + 1                     # le saut de ligne
        n_springs = sum(1 for g, _x, k, *_m in placed if g is None and k == 0.0)
        if n_springs:
            per, shift, moved, kept = max(0.0, target - total) / n_springs, 0.0, [], []
            for pos, (g, x, k, *more) in enumerate(placed):
                if g is None and k == 0.0:
                    shift += per
                else:
                    moved.append((g, x + shift, k, *more))
                    kept.append(ids[pos])
            placed, ids = moved, kept
            dx = 0.0
        elif align == 'justify':
            gap = (widest - total) / (len(placed) - 1) if len(placed) > 1 else 0.0
            placed = [(g, x + i * gap, k, *more) for i, (g, x, k, *more) in enumerate(placed)]
            dx = 0.0
        else:
            dx = {'left': 0.0, 'center': -total / 2, 'right': -total}.get(align, 0.0)
        y = -li * em * line_spacing
        for pos, (g, x, k, *more) in enumerate(placed):
            if g:
                out.append((g, _letter_matrix(s * wr * k, s * k, x + dx, y, more[0], height) if more
                            else Affine(s * wr * k, 0, 0, s * k, x + dx, y)))
                if lines is not None:
                    lines.append(li)
                if chars is not None:
                    chars.append(ids[pos])
    return out


def natural_width(t) -> float:
    """La longueur de la plus longue ligne du texte droit, sans sa compression (mm)."""
    mode = t.extra.get('spacing_mode', 'typo')
    got = _rows(shown_text(t), t.font, t.size, t.spacing, t.width_ratio, mode in KERNED, mode == 'fixed',
                bool(t.extra.get('small_caps')), tight=mode in TIGHT)
    if got is None:
        return 0.0
    fx = {} if t.extra.get('rtl') else char_fx(t)
    if fx:
        got = (got[0], got[1], _letter_fx(got[2], t.text, fx, fonts.find_font(t.font), got[1], t.size,
                                          bool(t.extra.get('small_caps'))))
    return max((total for _placed, total, _wr in got[2]), default=0.0)


def compression(t) -> list[float] | None:
    """Facteurs de largeur des lignes d'un texte droit pour tenir dans sa
    longueur maximale (`extra['max_length']` : {'length' (mm), 'by'}) —
    TypeEdit : 'line', chaque ligne trop longue resserrée seule ;
    'paragraph', toutes du facteur de la plus longue (même allure). Les
    lettres se resserrent, l'interlettrage reste ; jamais d'étirement.
    None : pas de limite."""
    ml = t.extra.get('max_length') or {}
    limit = float(ml.get('length', 0.0) or 0.0)
    if limit <= 0:
        return None
    mode = t.extra.get('spacing_mode', 'typo')
    got = _rows(shown_text(t), t.font, t.size, t.spacing, t.width_ratio, mode in KERNED, mode == 'fixed',
                bool(t.extra.get('small_caps')), tight=mode in TIGHT)
    if got is None:
        return None
    fx = {} if t.extra.get('rtl') else char_fx(t)
    if fx:
        got = (got[0], got[1], _letter_fx(got[2], t.text, fx, fonts.find_font(t.font), got[1], t.size,
                                          bool(t.extra.get('small_caps'))))
    out = []
    for placed, total, _wr in got[2]:
        sp = t.spacing * max(0, len(placed) - 1)
        if total <= limit + 1e-9 or total - sp <= 0:
            out.append(1.0)
        else:
            out.append(min(1.0, max(0.05, (limit - sp) / (total - sp))))
    if ml.get('by') == 'paragraph':
        out = [min(out)] * len(out)
    return out


def layout(text: str, font: str, height: float, *, align: str = 'left',
           spacing: float = 0.0, line_spacing: float = 1.2, width_ratio: float = 1.0,
           kerning: bool = True, fixed: bool = False, small_caps: bool = False,
           line_ratios: list | None = None, spring_width: float = 0.0, fx: dict | None = None,
           tight: bool = False) -> Path:
    """Contours du texte, origine au point de base de la 1ʳᵉ ligne.

    `spacing` : interlettrage ajouté (mm) ; `line_spacing` : interligne en
    multiples du corps ; `align` : left, center, right, justify.
    """
    contours = []
    for g, mat in _placed(text, font, height, align, spacing, line_spacing, width_ratio, kerning, fixed,
                          small_caps, line_ratios, spring_width, fx, tight=tight):
        contours.extend(c.transformed(mat) for c in g.contours)
    return Path(contours)


def layout_bbox(text: str, font: str, height: float, *, align: str = 'left',
                spacing: float = 0.0, line_spacing: float = 1.2, width_ratio: float = 1.0,
                kerning: bool = True, small_caps: bool = False):
    """Boîte de `layout(...)` sans en construire les contours : boîtes des
    glyphes (gardées en mémoire par glyphe) passées par leur matrice
    (échelle positive et translation : la boîte suit exactement)."""
    x0 = y0 = float('inf')
    x1 = y1 = float('-inf')
    for g, mat in _placed(text, font, height, align, spacing, line_spacing, width_ratio, kerning,
                          small_caps=small_caps):
        b = g.bbox()
        if not b:
            continue
        ax, ay = mat.apply((b[0], b[1]))
        bx, by = mat.apply((b[2], b[3]))
        x0, y0 = min(x0, ax, bx), min(y0, ay, by)
        x1, y1 = max(x1, ax, bx), max(y1, ay, by)
    return (x0, y0, x1, y1) if x0 <= x1 else None


def advance(text: str, font: str, height: float, spacing: float = 0.0) -> float:
    """Largeur d'avance d'une ligne (mm)."""
    ff = fonts.find_font(font)
    if not ff:
        return 0.0
    s = em_for_height(ff, height) / fonts.metrics(*ff)['upem']
    return sum(fonts.glyph(ff[0], ff[1], ch)[1] * s + spacing for ch in text) - (spacing if text else 0)


def _no_springs(text: str, fx: dict) -> tuple[str, dict]:
    """Le texte sans ses ressorts, les réglages restant sur leurs lettres."""
    if SPRING not in text:
        return text, fx
    out, moved = [], {}
    for i, ch in enumerate(text):
        if ch != SPRING:
            if i in fx:
                moved[len(out)] = fx[i]
            out.append(ch)
    return ''.join(out), moved


def on_path(text: str, font: str, height: float, contour, *, start: float = 0.0,
            align: str = 'left', spacing: float = 0.0, side: str = 'left', fx: dict | None = None) -> Path:
    """Texte posé le long d'un contour : chaque glyphe est placé à son
    abscisse curviligne et tourné selon la tangente. `start` : décalage du
    début (mm) ; `side` : 'left' (au-dessus, sens du tracé) ou 'right' ;
    `fx` : réglages par lettre (`char_fx`)."""
    import math
    ff = fonts.find_font(font)
    if not ff or not text or not contour.segments:
        return Path()
    s = em_for_height(ff, height) / fonts.metrics(*ff)['upem']
    total, at = geom_walker(contour)
    fx = fx or {}
    glyphs = []
    for i, ch in enumerate(text):
        own = char_font(fx[i], height, ch) if i in fx else None
        glyphs.append(own if own is not None else (*fonts.glyph(ff[0], ff[1], ch), s))

    def setting(i):
        f = fx.get(i) or {}
        return (f.get('kern', 0.0) / 100.0 * height, f.get('h', 100.0) / 100.0, f.get('w', 100.0) / 100.0,
                f.get('rot', 0.0), f.get('dx', 0.0) / 100.0 * height, f.get('dy', 0.0) / 100.0 * height)
    width = -spacing
    for i, (_g, adv, si) in enumerate(glyphs):
        kern, h, wd, *_more = setting(i)
        width += kern + adv * si * h * wd + spacing
    pos = {'left': start, 'center': start + (total - width) / 2, 'right': start + total - width}.get(align, start)

    flip = side == 'right'
    out = []
    for i, (g, adv, si_) in enumerate(glyphs):
        kern, h, wd, rot, dx, dy = setting(i)
        pos += kern
        w = adv * si_ * h * wd
        # tangente au milieu du glyphe ; sur une courbe fermée, le texte passe le point de départ sans s'y entasser
        (cx, cy), ang = at((pos + dx + w / 2) % total if contour.closed and total > 0 else pos + dx + w / 2)
        if flip:
            ang += math.pi
        co, si = math.cos(ang), math.sin(ang)
        # origine du glyphe : recul d'une demi-chasse le long de la tangente, puis écart à la courbe
        ox, oy = cx - co * w / 2 - si * dy, cy - si * w / 2 + co * dy
        sized = Affine(si_ * h * wd, 0, 0, si_ * h, 0, 0)
        mat = Affine(co, si, -si, co, ox, oy) @ sized
        if rot:
            mat = Affine(co, si, -si, co, ox, oy) @ Affine.rotation(rot, (w / 2, height * h / 2)) @ sized
        out.extend(c.transformed(mat) for c in g.contours)
        pos += w + spacing
    return Path(out)


def curve_abscissa(contour, p) -> float:
    """L'abscisse (mm), le long de la courbe, du point de la courbe le plus proche de p."""
    import math

    from .geom import Line
    from .nodes import nearest_on_segment
    segs = list(contour.segments)
    if contour.closed and segs and contour.closing_gap() > 1e-9:
        segs.append(Line(contour.end, contour.start))
    best, before = None, 0.0
    for sg in segs:
        t, d = nearest_on_segment(sg, p)
        if best is None or d < best[0]:
            pts = [sg.point(t * i / 32) for i in range(33)]
            best = (d, before + sum(math.dist(a, b) for a, b in zip(pts, pts[1:])))
        before += sg.length()
    return best[1] if best else 0.0


def outline_moved_on_curve(t, delta: float) -> Path:
    """Le contour du texte s'il était décalé de `delta` mm sur sa courbe ; le texte ne change pas."""
    keep = t.extra.get('path_offset')
    t.extra['path_offset'] = float(keep or 0.0) + delta
    try:
        return outline_for(t)
    finally:
        if keep is None:
            t.extra.pop('path_offset', None)
        else:
            t.extra['path_offset'] = keep


def geom_walker(contour):
    from .geom import walker
    return walker(contour)


def line_widths(text: str, font: str, height: float, *, spacing: float = 0.0,
                width_ratio: float = 1.0, kerning: bool = True) -> list[float]:
    """Largeur d'avance de chaque ligne, comme `layout` la pose (mm)."""
    ff = fonts.find_font(font)
    if not ff:
        return [0.0 for _ in text.split('\n')]
    s = em_for_height(ff, height) / fonts.metrics(*ff)['upem']
    out = []
    for line in text.split('\n'):
        pen, prev = 0.0, None
        for ch in line:
            _g, adv = fonts.glyph(ff[0], ff[1], ch)
            if prev is not None and kerning:
                pen += _kern(ff, prev, ch) * s * width_ratio
            pen += adv * s * width_ratio + spacing
            prev = ch
        out.append(pen - spacing if line else 0.0)
    return out


def fit_width(text: str, font: str, height: float, width: float, mode: str = 'spacing') -> dict:
    """Réglages pour que la ligne la plus longue mesure `width` mm :
    mode 'spacing' (interlettrage, corps inchangé) ou 'ratio' (étirement
    horizontal des glyphes). Renvoie {'spacing': …, 'width_ratio': …}."""
    lines = text.split('\n')
    base = line_widths(text, font, height)
    i = max(range(len(lines)), key=lambda k: base[k]) if lines else 0
    if not lines or base[i] <= 0 or width <= 0:
        return {'spacing': 0.0, 'width_ratio': 1.0}
    if mode == 'ratio':
        # crénage et chasses s'étirent ensemble : relation linéaire
        return {'spacing': 0.0, 'width_ratio': width / base[i]}
    n = len(lines[i])
    if n < 2:
        return {'spacing': 0.0, 'width_ratio': width / base[i]}
    return {'spacing': (width - base[i]) / (n - 1), 'width_ratio': 1.0}


#: texte en arc : angle du milieu du texte, lu en sens horaire, haut des lettres vers l'extérieur.
#: 'under' est le bas renversé de TypeEdit ; 'bottom', le bas qui se lit de gauche à droite, n'en fait pas partie
ARC_ANGLES = {'top': 90.0, 'right': 0.0, 'under': 270.0, 'left': 180.0}


def arc_sweep(start, end) -> float:
    """Balayage horaire de l'angle `start` à l'angle `end` (°) ; 0 : angles absents ou égaux."""
    if start is None or end is None:
        return 0.0
    return (float(start) - float(end)) % 360.0


def arc_direction(position: str) -> tuple[float, float]:
    """Du centre vers le milieu du texte."""
    import math
    a = math.radians(270.0 if position == 'bottom' else ARC_ANGLES.get(position, 90.0))
    return math.cos(a), math.sin(a)


def radius_from_chord(chord: float, sagitta: float) -> float:
    """Rayon de l'arc de corde `chord` et de flèche `sagitta` (la distance cordale de TypeEdit)."""
    return (chord * chord / 4.0 + sagitta * sagitta) / (2.0 * sagitta)


def arc_contour(center, radius: float, height: float, position: str = 'top',
                side: str = 'outside', start=None, end=None):
    """Support d'un texte en arc, à poser avec `on_path(..., align='center')`.
    `side` : ligne de base sur le cercle de rayon `radius` ('outside') ou haut
    des lettres sur lui ('inside'). `position` : voir `ARC_ANGLES` ; 'bottom' :
    en bas du cercle, lu de gauche à droite. `start`, `end` : l'arc entre ces
    deux angles (°), en sens horaire, à la place de `position`."""
    from .geom import arc
    sweep = arc_sweep(start, end)
    if sweep > 1e-9:
        r = radius if side == 'outside' else max(radius - height, 1e-3)
        return arc(center, r, float(start), -sweep)
    if position == 'bottom':
        r = radius + height if side == 'outside' else radius
        return arc(center, r, 90.0, 360.0)              # trigo, milieu en bas
    r = radius if side == 'outside' else max(radius - height, 1e-3)
    return arc(center, r, ARC_ANGLES.get(position, 90.0) + 180.0, -360.0)      # horaire, milieu à cet angle


#: déformations d'un texte sur arc (TypeEdit : Textes sur arcs multiples)
ARC_MODES = {'simple': 'Simple (lettres non déformées)', 'radial': 'Radial (haut et bas suivent l\'arc)',
             'incline': 'Incliné (côtés vers le centre)'}


def arc_warp(text: str, font: str, height: float, center, radius: float, angle: float = 90.0,
             clockwise: bool = True, mode: str = 'simple', spacing: float = 0.0, tol: float = 0.01,
             fx: dict | None = None) -> 'Path':
    """Une ligne de texte sur l'arc de rayon `radius` (ligne de base) autour
    de `center`, centrée sur l'angle `angle` (°, 90 = en haut). Sens
    horaire : lu de gauche à droite au-dessus du centre, lettres vers
    l'extérieur ; sinon lettres vers le centre. Déformation (TypeEdit) :
    simple — lettres entières, tournées ; radiale — le haut et le bas des
    lettres suivent l'arc, leurs côtés restent parallèles ; inclinée — les
    côtés vont vers le centre de l'arc."""
    import math
    from .geom import Contour, Line, Path as _P
    if radius <= 0 or not text:
        return _P()
    cx, cy = center
    th0 = math.radians(angle)
    sgn = -1.0 if clockwise else 1.0            # sens de l'abscisse le long de l'arc
    up = 1.0 if clockwise else -1.0             # le haut des lettres : vers l'extérieur ou le centre

    def at(x):                                  # angle d'une abscisse sur la ligne de base
        return th0 + sgn * x / radius

    out = []
    for g, mat in _placed(text.split('\n')[0], font, height, 'center', spacing, 1.2, 1.0, True, fx=fx):
        contours = [c.transformed(mat) for c in g.contours]
        pts_all = [c.flatten(tol) for c in contours]
        xs = [x for pts in pts_all for x, _y in pts]
        if not xs:
            continue
        xc = (min(xs) + max(xs)) / 2
        tc = at(xc)
        ux, uy = math.cos(tc) * up, math.sin(tc) * up            # « haut » de la lettre
        for pts, c in zip(pts_all, contours):
            if len(pts) < 2:
                continue
            q = []
            for x, y in pts:
                if mode == 'incline':
                    t, r = at(x), radius + up * y
                    q.append((cx + r * math.cos(t), cy + r * math.sin(t)))
                elif mode == 'radial':
                    t = at(x)
                    q.append((cx + radius * math.cos(t) + y * ux, cy + radius * math.sin(t) + y * uy))
                else:                                            # simple : lettre entière, tournée
                    bx, by = cx + radius * math.cos(tc), cy + radius * math.sin(tc)
                    tx, ty = uy, -ux                             # tangente : sens de lecture
                    q.append((bx + (x - xc) * tx + y * ux, by + (x - xc) * ty + y * uy))
            segs = [Line(a, b) for a, b in zip(q, q[1:]) if math.dist(a, b) > 1e-12]
            if segs:
                out.append(Contour(segs, c.closed))
    return _P(out)


def shown_text(t) -> str:
    """Le texte tel qu'il se pose : de droite à gauche, dans l'ordre d'affichage et avec ses formes liées."""
    if not t.extra.get('rtl'):
        return t.text
    from . import rtl
    chars = fonts.char_set(t.font)
    return rtl.visual(t.text, chars.__contains__ if chars else None)


def line_ratio(t) -> float | None:
    """L'interligne (`line_spacing`, en cadratins) que demande `extra['line_mode']` : `fixed`, en mm d'une ligne de
    base à l'autre quelle que soit la hauteur ; `prop`, un % de la hauteur du texte ajouté à elle ; `typo`, un % de la
    hauteur complète de la police, jambages compris. None : pas de mode, ou police absente."""
    lm = t.extra.get('line_mode')
    ff = fonts.find_font(t.font) if lm else None
    if not ff:
        return None
    em = em_for_height(ff, t.size)
    if em <= 0:
        return None
    value = float(lm.get('value', 0.0) or 0.0)
    if lm.get('mode') == 'fixed':
        pitch = value
    elif lm.get('mode') == 'prop':
        pitch = t.size * (1.0 + value / 100.0)
    elif lm.get('mode') == 'typo':
        m = fonts.metrics(*ff)
        pitch = (m['ascent'] + abs(m['descent'])) / m['upem'] * em * value / 100.0
    else:
        return None
    return max(pitch, 0.0) / em


def outline_for(t) -> 'Path':
    """Contour d'un `Text` selon ses réglages : largeur imposée
    (extra['fit']), arc (extra['arc']), courbe (extra['on_path']) ou ligne
    droite (matrix)."""
    from .geom import Path as _P
    ratio = line_ratio(t)
    if ratio is not None:
        t.line_spacing = ratio
    box = t.extra.get('box')
    if box:
        f = fit_box(shown_text(t), t.font, box['x1'] - box['x0'], box['y1'] - box['y0'],
                    line_spacing=t.line_spacing, stretch=box.get('stretch', False), compress=box.get('compress', False))
        if f['size'] > 0:
            t.size, t.width_ratio, t.spacing = f['size'], f['width_ratio'], 0.0
            t.matrix = box_matrix(box, t.size, t.align)
            if box.get('middle'):                        # centré aussi en hauteur
                from .geom import Affine
                t.matrix = Affine.translation(0.0, ((box['y0'] - box['y1']) + f['used']) / 2.0) @ t.matrix
    fit = t.extra.get('fit') or {}
    springs = SPRING in t.text                           # ressorts : la largeur imposée est celle des lignes
    if fit.get('width', 0) > 0 and t.extra.get('on_path') is None and not box and not springs:
        f = fit_width(shown_text(t), t.font, t.size, fit['width'], fit.get('mode', 'spacing'))
        t.spacing, t.width_ratio = f['spacing'], f['width_ratio']
    fx = {} if t.extra.get('rtl') else char_fx(t)                # par lettre : les lettres ne sont plus dans le même ordre
    shown = shown_text(t)
    if t.extra.get('chars') and t.extra.get('chars_text') != t.text:
        set_char_fx(t, fx)                               # le texte a changé : ils se rapportent maintenant à lui
    warp = t.extra.get('arc_warp')
    if warp:
        plain, kept = _no_springs(shown, fx)
        first = len(plain.split('\n')[0])
        return arc_warp(plain, t.font, t.size, tuple(warp['center']), warp['radius'],
                        warp.get('angle', 90.0),
                        warp.get('clockwise', True), warp.get('mode', 'simple'), t.spacing,
                        fx={i: f for i, f in kept.items() if i < first})
    arc = t.extra.get('arc')
    if arc:
        t.extra['on_path'] = arc_contour(tuple(arc['center']), arc['radius'], t.size, arc.get('position', 'top'),
                                         arc.get('side', 'outside'), arc.get('start'), arc.get('end'))
        sweep = arc_sweep(arc.get('start'), arc.get('end'))
        if sweep > 1e-9:                                 # entre deux angles : l'interlettrage remplit l'arc
            import math
            r = arc['radius'] if arc.get('side', 'outside') == 'outside' else max(arc['radius'] - t.size, 1e-3)
            t.spacing = fit_width(_no_springs(shown, fx)[0], t.font, t.size, math.radians(sweep) * r)['spacing']
    if t.extra.get('on_path') is not None:
        plain, kept = _no_springs(shown, fx)
        return on_path(plain, t.font, t.size, t.extra['on_path'], align=t.align,
                       spacing=t.spacing,
                       start=float(t.extra.get('path_offset', 0.0) or 0.0), fx=kept)
    mode = t.extra.get('spacing_mode', 'typo')
    p = layout(shown, t.font, t.size, align=t.align, spacing=t.spacing,
               line_spacing=t.line_spacing, width_ratio=t.width_ratio, kerning=mode in KERNED,
               fixed=mode == 'fixed', small_caps=bool(t.extra.get('small_caps')), line_ratios=compression(t),
               spring_width=(float(fit.get('width', 0) or 0) or (box['x1'] - box['x0'] if box else 0.0)) if springs else 0.0,
               fx=fx, tight=mode in TIGHT)
    if p and t.extra.get('underline'):
        p = _P(p.contours + underlines(t, mode))
    if p and t.extra.get('italic'):
        import math
        from .geom import Affine
        p = p.transformed(Affine(1.0, 0.0, math.tan(math.radians(float(t.extra['italic']))), 1.0, 0.0, 0.0))
    if p and t.extra.get('baseline'):
        from .geom import Affine
        p = p.transformed(Affine(1.0, 0.0, 0.0, 1.0, 0.0, baseline_shift(t)))
    return p.transformed(t.matrix) if p else _P()


def straight(t) -> bool:
    """Un texte posé en ligne droite, lettres dans leur ordre : on peut le prendre lettre par lettre."""
    x = t.extra
    return not (x.get('rtl') or x.get('arc') or x.get('arc_warp') or x.get('on_path') is not None)


def text_matrix(t):
    """De la mise en page au dessin, comme `outline_for` : italique, ligne de base, matrice du texte."""
    import math
    from .geom import Affine
    m = t.matrix
    if t.extra.get('baseline'):
        m = m @ Affine(1.0, 0.0, 0.0, 1.0, 0.0, baseline_shift(t))
    if t.extra.get('italic'):
        m = m @ Affine(1.0, 0.0, math.tan(math.radians(float(t.extra['italic']))), 1.0, 0.0, 0.0)
    return m


def letter_outlines(t) -> list:
    """[(position dans le texte, contours sur le dessin)] des lettres d'un texte droit ; sans les espaces."""
    from .geom import Path as _P
    if not straight(t):
        return []
    fit = t.extra.get('fit') or {}
    springs = SPRING in t.text
    mode = t.extra.get('spacing_mode', 'typo')
    chars = []
    placed = _placed(t.text, t.font, t.size, t.align, t.spacing, t.line_spacing, t.width_ratio, mode in KERNED,
                     mode == 'fixed', bool(t.extra.get('small_caps')), compression(t),
                     float(fit.get('width', 0) or 0) if springs else 0.0, char_fx(t), tight=mode in TIGHT, chars=chars)
    whole = text_matrix(t)
    return [(i, _P([c.transformed(whole @ mat) for c in g.contours])) for i, (g, mat) in zip(chars, placed)]


def caret_points(t) -> list:
    """Le curseur de saisie d'un texte droit : pour chaque position 0…len(t.text), son point sur la ligne de base,
    dans le dessin — là où `outline_for` pose les lettres (alignement, ressorts, justification, compression,
    réglages par lettre, italique). Texte vide ou police absente : l'origine du texte à chaque position ; texte
    courbe ou de droite à gauche : []."""
    if not straight(t):
        return []
    whole = text_matrix(t)
    text = t.text
    mode = t.extra.get('spacing_mode', 'typo')
    got = _rows(text, t.font, t.size, t.spacing, t.width_ratio, mode in KERNED, mode == 'fixed',
                bool(t.extra.get('small_caps')), compression(t), tight=mode in TIGHT)
    if got is None:
        return [whole.apply((0.0, 0.0))] * (len(text) + 1)
    em, s, rows = got
    fx = char_fx(t)
    if fx:
        rows = _letter_fx(rows, text, fx, fonts.find_font(t.font), s, t.size, bool(t.extra.get('small_caps')))
    fit, box = t.extra.get('fit') or {}, t.extra.get('box')
    target = 0.0
    if SPRING in text:
        target = float(fit.get('width', 0) or 0) or (box['x1'] - box['x0'] if box else 0.0)
    widest = max(total for _p, total, _w in rows)
    target = target if target > 0 else widest
    out = []
    for li, (placed, total, _wr) in enumerate(rows):
        xs = [x for _g, x, *_m in placed]
        end, dx = total, 0.0
        springs = [g is None and k == 0.0 for g, _x, k, *_m in placed]
        if any(springs):                                 # l'écart partagé entre les ressorts, comme `_placed`
            per, shift = max(0.0, target - total) / sum(springs), 0.0
            for i, spring in enumerate(springs):
                xs[i] += shift
                if spring:
                    shift += per
            end = total + shift
        elif t.align == 'justify':
            gap = (widest - total) / (len(placed) - 1) if len(placed) > 1 else 0.0
            xs = [x + i * gap for i, x in enumerate(xs)]
            end = total + max(0, len(placed) - 1) * gap
        else:
            dx = {'left': 0.0, 'center': -total / 2, 'right': -total}.get(t.align, 0.0)
        y = -li * em * t.line_spacing
        out.extend(whole.apply((x + dx, y)) for x in xs)
        out.append(whole.apply((end + dx, y)))
    return out


def caret_index(t, point) -> int:
    """La position du texte droit dont le curseur passe au plus près de `point` (dessin) ; texte courbe : la fin."""
    pts = caret_points(t)
    if not pts:
        return len(t.text)
    whole = text_matrix(t)
    o, u = whole.apply((0.0, 0.0)), whole.apply((0.0, t.size / 2.0))
    ux, uy = u[0] - o[0], u[1] - o[1]                    # du pied du curseur à sa mi-hauteur
    return min(range(len(pts)), key=lambda i: (pts[i][0] + ux - point[0]) ** 2 + (pts[i][1] + uy - point[1]) ** 2)


def _char_class(ch: str) -> int:
    """0 : lettre, chiffre, souligné (un mot) ; 1 : espace, ressort ; 2 : le reste (ponctuation)."""
    if ch.isalnum() or ch == '_':
        return 0
    return 1 if ch.isspace() or ch == SPRING else 2


def line_span(src: str, c: int) -> tuple:
    """(début, fin) de la ligne du texte `src` où se trouve la position `c` (sans son saut de ligne)."""
    c = max(0, min(len(src), int(c)))
    start = src.rfind('\n', 0, c) + 1
    end = src.find('\n', c)
    return start, (len(src) if end < 0 else end)


def char_span(src: str, i: int) -> tuple:
    """(début, fin) du mot — ou de la suite d'espaces, de ponctuation — dont fait partie le caractère de rang `i`
    (double clic sur ce caractère) ; au-delà de la ligne : son dernier caractère ; ligne vide : rien."""
    i = max(0, min(len(src), int(i)))
    start, end = line_span(src, i)
    if start == end:
        return i, i
    i = max(start, min(i, end - 1))
    kind = _char_class(src[i])
    a, b = i, i + 1
    while a > start and _char_class(src[a - 1]) == kind:
        a -= 1
    while b < end and _char_class(src[b]) == kind:
        b += 1
    return a, b


def word_span(src: str, c: int) -> tuple:
    """(début, fin) du mot de `src` à la position `c` du curseur : le mot qui touche `c` — celui d'après d'abord —
    sinon la suite d'espaces ou de ponctuation ; jamais au-delà de la ligne."""
    c = max(0, min(len(src), int(c)))
    start, end = line_span(src, c)
    if start == end:
        return c, c
    if c < end and _char_class(src[c]) == 0:
        return char_span(src, c)
    if c > start and _char_class(src[c - 1]) == 0:
        return char_span(src, c - 1)
    return char_span(src, c if c < end else c - 1)


def ensure_outlines(doc) -> int:
    """Contour de chaque texte vivant qui n'en a pas encore (jamais affiché :
    dessin importé puis exporté, conversion en ligne de commande, lot) —
    sans lui, les écrivains DXF, SVG, PDF, EPS et VND sautaient le texte.
    Rend le nombre de contours calculés ; un texte dont la police manque
    reste sans contour (il est signalé ailleurs)."""
    n = 0
    for it in doc.iter_leaves():
        if getattr(it, 'outline', None) is None and hasattr(it, 'font') and hasattr(it, 'text'):
            try:
                it.outline = outline_for(it)
                n += 1
            except Exception:
                continue
    return n


#: mise en forme reproduite d'un texte à l'autre (TypeEdit : Reproduire la mise en forme)
FORMAT_ATTRS = ('font', 'size', 'width_ratio', 'spacing', 'line_spacing', 'align')
FORMAT_EXTRA = ('italic', 'underline', 'small_caps', 'baseline', 'spacing_mode', 'max_length', 'line_mode', 'rtl')


def text_format(t) -> dict:
    """Mise en forme d'un texte (police, hauteur, largeur, espacements,
    alignement, styles), sans son contenu ni sa place."""
    import copy
    return {'attrs': {k: getattr(t, k) for k in FORMAT_ATTRS},
            'extra': {k: copy.deepcopy(t.extra[k]) for k in FORMAT_EXTRA if k in t.extra}}


def formatted(t, fmt: dict) -> dict:
    """La mise en forme qu'aurait le texte après `apply_format(t, fmt)`, sans le changer."""
    import copy
    out = text_format(t)
    for k, v in (fmt.get('attrs') or {}).items():
        if k in FORMAT_ATTRS and not (k == 'size' and 'box' in t.extra):
            out['attrs'][k] = v
    extra = fmt.get('extra') or {}
    out['extra'] = {k: copy.deepcopy(extra[k]) for k in FORMAT_EXTRA if k in extra}
    return out


def apply_format(t, fmt: dict) -> bool:
    """Pose la mise en forme `fmt` sur le texte (contour recalculé ; seuls les champs de mise en forme) ; rend
    vrai s'il a changé."""
    import copy
    before = text_format(t)
    for k, v in fmt['attrs'].items():
        if k not in FORMAT_ATTRS or (k == 'size' and 'box' in t.extra):
            continue                                     # texte dans un cadre : sa hauteur suit le cadre
        setattr(t, k, v)
    for k in FORMAT_EXTRA:
        if k in fmt['extra']:
            t.extra[k] = copy.deepcopy(fmt['extra'][k])
        else:
            t.extra.pop(k, None)
    if text_format(t) == before:
        return False
    t.extra.pop('fit', None)                             # une largeur imposée reprendrait la main
    t.outline = outline_for(t)
    return True


def baseline_shift(t) -> float:
    """Décalage vertical d'un texte droit par rapport à sa ligne de base
    (TypeEdit : Sur / Sous la ligne de base, écart en % de la hauteur) :
    sous la ligne, le haut des capitales vient sur elle."""
    b = t.extra.get('baseline') or {}
    off = float(b.get('offset', 0.0) or 0.0) / 100.0 * t.size
    return -(t.size + off) if b.get('side') == 'under' else off


#: souligné par défaut, en % de la hauteur du texte : distance sous la ligne de base, épaisseur
UNDERLINE_POS, UNDERLINE_THICK = 15.0, 7.0
ITALIC_DEFAULT, ITALIC_MAX = 12.0, 75.0


def underline_style(t) -> tuple:
    """(position, épaisseur) du souligné, en % de la hauteur. `extra['underline']` : True (par défaut) ou {'pos', 'thick'}."""
    u = t.extra.get('underline')
    if not isinstance(u, dict):
        return UNDERLINE_POS, UNDERLINE_THICK
    try:
        pos, thick = float(u.get('pos', UNDERLINE_POS)), float(u.get('thick', UNDERLINE_THICK))
    except (TypeError, ValueError):
        return UNDERLINE_POS, UNDERLINE_THICK
    if pos != pos or thick != thick or abs(pos) == float('inf') or thick <= 0 or thick == float('inf'):
        return UNDERLINE_POS, UNDERLINE_THICK
    return pos, thick


def underlines(t, mode: str = 'typo') -> list:
    """Soulignés d'un texte droit (repère du texte) : une barre fermée sous
    chaque ligne, à la distance et de l'épaisseur de `underline_style`."""
    from .geom import rect
    lines: dict = {}
    fx = {} if t.extra.get('rtl') else char_fx(t)
    ff = fonts.find_font(t.font)
    pitch = em_for_height(ff, t.size) * t.line_spacing if ff else 0.0
    numbers: list = []
    placed = _placed(shown_text(t), t.font, t.size, t.align, t.spacing, t.line_spacing, t.width_ratio,
                     mode in KERNED, mode == 'fixed', bool(t.extra.get('small_caps')), compression(t), 0.0, fx, numbers,
                     tight=mode in TIGHT)
    for (g, mat), li in zip(placed, numbers):
        b = g.bbox()
        if not b:
            continue
        xs = [mat.apply(c)[0] for c in ((b[0], b[1]), (b[2], b[1]), (b[0], b[3]), (b[2], b[3]))]   # une lettre peut être tournée
        x0, x1 = min(xs), max(xs)
        y = round(-li * pitch, 9)                        # la ligne, pas la lettre : un exposant reste souligné avec elle
        lo, hi = lines.get(y, (x0, x1))
        lines[y] = (min(lo, x0), max(hi, x1))
    pos, thick = underline_style(t)
    th = thick / 100.0 * t.size
    return [rect(x0, y - pos / 100.0 * t.size - th, x1 - x0, th) for y, (x0, x1) in lines.items() if x1 > x0]


def fit_box(text: str, font: str, width: float, height: float, *, line_spacing: float = 1.2,
            stretch: bool = False, compress: bool = False) -> dict:
    """Plus grande hauteur de capitales telle que le texte (toutes ses
    lignes) tienne dans width × height mm, jambages compris ; `stretch` :
    étirement horizontal pour remplir aussi la largeur ; `compress` : la
    hauteur du cadre d'abord, les lettres comprimées si la largeur manque.
    Renvoie {'size', 'width_ratio', 'em', 'used'} (em : corps, pour
    l'interligne ; used : hauteur occupée)."""
    ff = fonts.find_font(font)
    if not ff or not text or width <= 0 or height <= 0:
        return {'size': 0.0, 'width_ratio': 1.0, 'em': 0.0, 'used': 0.0}
    m = fonts.metrics(*ff)
    em1 = em_for_height(ff, 1.0)                     # corps pour une capitale de 1 mm
    desc1 = m['descent'] / m['upem'] * em1           # jambage pour une capitale de 1 mm
    n = len(text.split('\n'))
    w1 = max(line_widths(text, font, 1.0)) or 1e-9
    h1 = 1.0 + (n - 1) * em1 * line_spacing + desc1
    size = height / h1 if compress else min(width / w1, height / h1)
    ratio = 1.0
    if compress:
        ratio = min(1.0, width / (w1 * size))
    elif stretch:
        ratio = max(1.0, width / (w1 * size))
    return {'size': size, 'width_ratio': ratio, 'em': em1 * size, 'used': size * h1}


def box_matrix(box: dict, size: float, align: str):
    """Origine du texte dans le cadre : 1ʳᵉ ligne de base sous le bord
    haut, x selon l'alignement."""
    from .geom import Affine
    x0, x1, y1 = box['x0'], box['x1'], box['y1']
    x = {'left': x0, 'center': (x0 + x1) / 2, 'right': x1}.get(align, x0)
    return Affine.translation(x, y1 - size)


def split_columns(lines: list[str], n: int) -> list[list[str]]:
    """Lignes réparties dans n colonnes, dans l'ordre, la première la plus
    remplie (comme un journal)."""
    n = max(1, min(n, len(lines)))
    per = -(-len(lines) // n)
    return [lines[i:i + per] for i in range(0, len(lines), per)]


def columns(t, n: int, gutter: float) -> list:
    """Texte en colonnes : copies de `t` portant chacune une part des lignes,
    côte à côte (écart `gutter` entre colonnes), premières lignes de base
    alignées sur celle de `t`."""
    import copy as _copy
    from .document import drop_source_object
    from .geom import Affine
    parts = split_columns(t.text.split('\n'), n)
    out = []
    x_next = None
    for k, lines in enumerate(parts):
        c = _copy.copy(t)
        c.extra = {key: v for key, v in t.extra.items() if key not in ('columns',)}
        drop_source_object(c)
        c.text = '\n'.join(lines)
        c.outline = outline_for(c)
        if k and x_next is not None and c.outline:
            bb = c.outline.bbox()
            c = c.transformed(Affine.translation(x_next - bb[0], 0.0))
        bb = c.outline.bbox() if c.outline else None
        if bb:
            x_next = bb[2] + gutter
        out.append(c)
    return out
