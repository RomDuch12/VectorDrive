"""Réunir des textes en un seul texte de plusieurs lignes (comme TXT2MTXT
en DAO, d'après CADCraft) : les textes d'une ligne d'un plan importé
(une ligne de texte par objet) redeviennent un paragraphe modifiable.

Les lignes sont rangées de haut en bas dans le repère du texte le plus
haut (textes tournés compris) ; des textes à la même hauteur forment une
ligne, de gauche à droite, séparés par une espace. Le texte réuni garde la
police, la hauteur et les réglages du texte le plus haut ; son interligne
reprend l'écart médian des lignes. Textes sur courbe, en arc ou dans un
cadre : laissés tels quels.
"""
from __future__ import annotations

import statistics

from .document import Text
from .geom import Affine

#: réglages propres à une forme de texte que la réunion ne garde pas
SKIP = ('on_path', 'arc', 'arc_warp', 'box')


def mergeable(t) -> bool:
    return isinstance(t, Text) and bool(t.text.strip()) and not any(k in t.extra for k in SKIP)


def _em(t) -> float:
    from . import fonts
    from . import text as TX
    ff = fonts.find_font(t.font)
    try:
        return TX.em_for_height(ff, t.size) if ff else t.size / 0.7
    except Exception:                                   # police illisible : corps habituel
        return t.size / 0.7


def merge(texts) -> Text | None:
    """Un texte de plusieurs lignes fait des textes donnés (ceux qui s'y
    prêtent), ou None s'il y en a moins de deux."""
    ts = [t for t in texts if mergeable(t)]
    if len(ts) < 2:
        return None
    first = ts[0]
    m = first.matrix
    sx = (m.a * m.a + m.b * m.b) ** 0.5 or 1.0
    ca, sa = m.a / sx, m.b / sx                         # direction des lignes du premier texte
    ox, oy = m.e, m.f

    def local(t):
        dx, dy = t.matrix.e - ox, t.matrix.f - oy
        return dx * ca + dy * sa, -dx * sa + dy * ca

    items = sorted(((local(t), t) for t in ts), key=lambda it: -it[0][1])
    rows = []                                           # [[(x, y), [textes…]]]
    for (x, y), t in items:
        if rows and abs(rows[-1][0][1] - y) <= 0.3 * max(t.size, rows[-1][1][0].size):
            rows[-1][1].append(t)
            rows[-1][0] = (min(rows[-1][0][0], x), rows[-1][0][1])
        else:
            rows.append([(x, y), [t]])
    lines = []
    for _o, row in rows:
        row.sort(key=lambda t: local(t)[0])
        lines.append(' '.join(t.text.strip() for t in row))
    top = rows[0][1][0]
    out = top.clone()                                   # nouvel identifiant
    out.extra = {k: v for k, v in top.extra.items() if k not in ('fit', 'vnd_obj', 'vnd_moved', 'vnd_shift')}
    out.text = '\n'.join(lines)
    if len(rows) > 1:
        gaps = [rows[i][0][1] - rows[i + 1][0][1] for i in range(len(rows) - 1)]
        out.line_spacing = round(statistics.median(gaps) / _em(top), 4)
    if out.align == 'left':                              # départ : le plus à gauche des débuts de ligne
        x0 = min(o[0] for o, _r in rows)
        y0 = rows[0][0][1]
        e, f = ox + x0 * ca - y0 * sa, oy + x0 * sa + y0 * ca
        out.matrix = Affine(top.matrix.a, top.matrix.b, top.matrix.c, top.matrix.d, e, f)
    out.outline = None
    return out
