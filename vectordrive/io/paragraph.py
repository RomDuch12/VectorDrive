"""Écriture de textes TypeEdit vivants (`CParagraphe`) à
partir d'un `Text` de VectorDrive — validée dans TypeEdit 13 (une et
plusieurs lignes, alignements, rotation, accents : 18/10 et 12/11) ;
écrite d'office à l'enregistrement en VND depuis le round 988, pour les
textes que TypeEdit peut relire (`vnd_write.curves_reason`) ; option des
symboles désactivée par défaut.

Gabarits relevés sur un corpus de 6 094 paragraphes de symboles :
attributs de paragraphe (52 octets), de ligne (68 octets : drapeaux dont
l'alignement dans les 2 bits bas, décalage vertical, 0,75, largeur), de
caractère (204 octets : code, indice de police, hauteur, rapport de
largeur, propriétés ; 4 octets non initialisés mis à zéro), boîte de
chaque caractère (4 coins, float32, m), une ligne de base par ligne en
`courbe1` (avec une seule, TypeEdit 13 n'affiche que la 1ʳᵉ ligne),
`courbe2` vide, origine = point d'ancrage de l'alignement sur la 1re
ligne de base.
"""
from __future__ import annotations

import math
import struct

from ..core import fonts as F
from ..core import text as TX
from ..core.document import Shape, Text
from ..core.geom import Affine, Contour, Line, Path
from .mfc import MfcClass, MfcObject

MM_TO_M = 1 / 1000.0

#: CTxtAttrPara v4 relevé (symbole réel), octets non initialisés à zéro
PARA_TEMPLATE = bytes.fromhex(
    '040000000000000000000000000000000000000000000000000000000000f03f'
    '000000000000f03f000000000088c34000000000')

#: CTxtAttrChar v5 relevé sur 99 136 caractères de TypeEdit 13 (VND de l'atelier)
#: et 21 595 de symboles : code, police, hauteur et rapport remplacés à
#: l'écriture ; les octets 44 à 47 (non initialisés par TypeEdit) à zéro.
#: L'ancien gabarit avait 4 octets de trop avant le réel −0,4 (octet 56) :
#: TypeEdit 13 ne chargeait pas le dessin.
CHAR_TEMPLATE = bytes.fromhex(
    '0500000000000000000000000000000000000000000000000000f03f00000000'
    '0000000000000000000000000000000000000000000000009a9999999999d9bf'
    '000000000000f03f000000000000000000000000000000000000f03f05000000'
    'fca9f1d24d62403f000000000000000000000000000001000c00000000000000'
    '0400000000000000040000000000000000000000000000000000000000000000'
    '0000000000000000000000000000000000000000000000000000000000000000'
    '000000000000000000000000')

#: fin de CTxtAttrLine v4 relevée (8 derniers octets)
LINE_TAIL = bytes.fromhex('000000000000383c')
assert len(PARA_TEMPLATE) == 52, len(PARA_TEMPLATE)
assert len(CHAR_TEMPLATE) == 204, len(CHAR_TEMPLATE)

ALIGN_BITS = {'left': 0, 'right': 1, 'center': 2}


def line_record(align: str, dy_m: float, width_m: float) -> bytes:
    """CTxtAttrLine v4 : version, drapeaux (0x20 | alignement), 5 f64
    (0, décalage vertical, 0, 0,75, largeur), 1,0, 0, fin relevée."""
    return (struct.pack('<II', 4, 0x20 | ALIGN_BITS.get(align, 0))
            + struct.pack('<5d', 0.0, dy_m, 0.0, 0.75, width_m)
            + struct.pack('<d', 1.0) + struct.pack('<I', 0) + LINE_TAIL)


def char_record(code: int, font_index: int, height_m: float, ratio: float) -> bytes:
    b = bytearray(CHAR_TEMPLATE)
    struct.pack_into('<IId', b, 4, code, font_index, height_m)
    struct.pack_into('<d', b, 20, ratio)
    return bytes(b)


def char_layout(t: Text) -> list[tuple]:
    """(caractère, x du stylo, y de la ligne de base, avance, boîte d'encre
    ou None) dans le repère du texte, comme `text.layout` les pose ; les
    fins de ligne donnent ('\\r', x, y, 0, None)."""
    ff = F.find_font(t.font)
    if not ff:
        return []
    m = F.metrics(*ff)
    em = TX.em_for_height(ff, t.size)
    s = em / m['upem']
    out = []
    lines = t.text.split('\n')
    for li, line in enumerate(lines):
        pen, prev, placed = 0.0, None, []
        for ch in line:
            g, adv = F.glyph(ff[0], ff[1], ch)
            if prev is not None:
                pen += TX._kern(ff, prev, ch) * s * t.width_ratio
            placed.append((ch, pen, adv * s * t.width_ratio, g))
            pen += adv * s * t.width_ratio + t.spacing
            prev = ch
        total = pen - t.spacing if line else 0.0
        dx = {'left': 0.0, 'center': -total / 2, 'right': -total}.get(t.align, 0.0)
        y = -li * em * t.line_spacing
        for ch, x, adv, g in placed:
            bb = None
            if g:
                gb = g.bbox()
                if gb:
                    bb = (x + dx + gb[0] * s * t.width_ratio, y + gb[1] * s,
                          x + dx + gb[2] * s * t.width_ratio, y + gb[3] * s)
            out.append((ch, x + dx, y, adv, bb))
        if li < len(lines) - 1:
            out.append(('\r', pen + dx, y, 0.0, None))
    return out


def _rigid(m: Affine) -> float | None:
    """Angle (rad) si la matrice est une rotation + translation, sinon None."""
    sx = math.hypot(m.a, m.b)
    sy = math.hypot(m.c, m.d)
    if abs(sx - 1) > 1e-6 or abs(sy - 1) > 1e-6 or abs(m.a * m.c + m.b * m.d) > 1e-6 or m.a * m.d - m.b * m.c < 0:
        return None
    return math.atan2(m.b, m.a)


def build(t: Text, font_index: int) -> MfcObject | None:
    """CParagraphe du texte, ou None s'il ne s'écrit pas ainsi (texte sur
    courbe, en arc, déformé, police introuvable)."""
    from .vnd_write import COURBE_TRAILER, EMPTY_BBOX, _bbox_m, _courbe, _obdao_fields
    if not t.text.strip() or t.extra.get('on_path') is not None or t.extra.get('arc'):
        return None
    ang = _rigid(t.matrix)
    ff = F.find_font(t.font)
    if ang is None or not ff or not t.outline:
        return None
    lay = char_layout(t)
    inks = [e[4] for e in lay if e[4]]
    if not inks:
        return None
    x0 = min(b[0] for b in inks)
    x1 = max(b[2] for b in inks)
    m = F.metrics(*ff)
    s = TX.em_for_height(ff, t.size) / m['upem']
    asc, desc = m['ascent'] * s, m['descent'] * s
    margin = 0.025 * t.size
    M = t.matrix

    def P(x, y):
        return M.apply((x, y))

    boxes = []
    chars = []
    for ch, x, y, adv, bb in lay:
        if ch == '\r':
            chars.append(char_record(13, font_index, t.size * MM_TO_M, t.width_ratio))
            bx0, bx1 = x, x
        else:
            chars.append(char_record(ord(ch), font_index, t.size * MM_TO_M, t.width_ratio))
            bx0, bx1 = ((bb[0] - margin, bb[2] + margin) if bb else (x, x + adv))
        corners = [P(bx0, y - desc), P(bx0, y + asc), P(bx1, y + asc), P(bx1, y - desc)]
        boxes.append(tuple(v * MM_TO_M for c in corners for v in c) + (0,))
    # caractère final (code 0) et sa boîte
    last = lay[-1]
    end = (last[4][2] if last[4] else last[1] + last[3])
    chars.append(char_record(0, font_index, t.size * MM_TO_M, t.width_ratio))
    corners = [P(end, last[2] - desc), P(end, last[2] + asc), P(end, last[2] + asc), P(end, last[2] - desc)]
    boxes.append(tuple(v * MM_TO_M for c in corners for v in c) + (0,))
    # lignes : décalage vertical et largeur d'encre
    em = TX.em_for_height(ff, t.size)
    lines = []
    baselines = []                                    # une ligne de base par ligne (TypeEdit 13 l'exige)
    for li, ln in enumerate(t.text.split('\n')):
        y_li = -li * em * t.line_spacing
        ys = [b for (ch, x, y, adv, b) in lay if b and abs(y - y_li) < 1e-9]
        w = (max(b[2] for b in ys) - min(b[0] for b in ys)) if ys else 0.0
        lines.append(line_record(t.align, y_li * MM_TO_M, w * MM_TO_M))
        if ys:
            baselines.append(Contour([Line(P(min(b[0] for b in ys), y_li), P(max(b[2] for b in ys), y_li))], False))
    anchor = {'left': x0, 'center': (x0 + x1) / 2, 'right': x1}.get(t.align, x0)
    ox, oy = P(anchor, 0.0)
    bb = _bbox_m(t.outline.bbox())
    o = MfcObject(MfcClass('CParagraphe', 6))
    o.fields = _obdao_fields(bb)
    base = _courbe(Shape(path=Path(baselines or [Contour([Line(P(x0, 0.0), P(x1, 0.0))], False)])))
    empty = MfcObject(MfcClass('CCourbe', 1))
    empty.fields = _obdao_fields(EMPTY_BBOX)
    empty.fields['ctn_version'] = 3
    empty.fields['trailer'] = COURBE_TRAILER
    o.fields.update(f8=2, f140=struct.pack('<d', ang), has_para2=0, f160=0,
                    origin=(ox * MM_TO_M, oy * MM_TO_M, 0.0),
                    para1={'para': PARA_TEMPLATE, 'lines': lines, 'chars': chars},
                    f164=0, blob=b'', cube=bb, boxes=boxes, courbe1=base, courbe2=empty, f148=0)
    o.children = [base, empty]
    return o
