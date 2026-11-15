"""Police monotrait intégrée « VD Trait » : des traits ouverts, gravés en
un passage, toujours là (sans police installée sur le poste).

Glyphes de base d'après la police « CADCraft Stroke » de CADCraft
(`crates/fonts/src/stroke.rs`, voir THIRD_PARTY_NOTICES.md), dessinés sur
une petite grille : x de 0 à 6, y de -2 (jambage) à 6 (capitales), ligne
de base à 0, hauteur des minuscules 4. Un glyphe est (largeur, traits) ;
un trait est une suite de points, chacun noté par deux caractères : un
chiffre pour x, une lettre pour y (« a » = -2, « c » = 0, « g » = 4,
« i » = 6). Les traits sont séparés par des espaces.

Ajouts : lettres accentuées composées à la volée (décomposition Unicode :
lettre de base + diacritiques au-dessus ou au-dessous, i et j sans point),
ligatures æ œ, guillemets, tirets, €, ×, ÷, exposants…

Unités rendues comme les polices Gravotech : **hauteur des capitales = 1**,
origine au point de base, y vers le haut, avance = (largeur + chasse) / 6.
"""
from __future__ import annotations

import functools
import unicodedata

from .geom import Contour, Line, Path

NAME = 'VD Trait'
#: pas un fichier : la police est dans le code (repérée par ce chemin)
PATH = '<vectordrive:trait>'
CAP = 6.0                     # hauteur des capitales sur la grille
GAP = 1.6                     # chasse ajoutée à chaque glyphe
SPACE = 2.4                   # largeur d'une espace
ASCENT, DESCENT = 1.3, 0.4    # boîte des caractères, accents des capitales compris

# --- glyphes de base (CADCraft Stroke) -------------------------------------------------

_GLYPHS = {
    ' ': (2.4, ''),
    'A': (4.0, '0c2i4c 1f3f'),
    'B': (4.0, '0c0i3i4h4g3f0f 3f4e4d3c0c'),
    'C': (4.0, '4h3i1i0h0d1c3c4d'),
    'D': (4.0, '0c0i3i4h4d3c0c'),
    'E': (4.0, '4i0i0c4c 0f3f'),
    'F': (4.0, '4i0i0c 0f3f'),
    'G': (4.0, '4h3i1i0h0d1c3c4d4f2f'),
    'H': (4.0, '0c0i 4c4i 0f4f'),
    'I': (2.0, '0i2i 1i1c 0c2c'),
    'J': (4.0, '4i4d3c1c0d0e'),
    'K': (4.0, '0c0i 4i0e 1f4c'),
    'L': (4.0, '0i0c4c'),
    'M': (4.0, '0c0i2f4i4c'),
    'N': (4.0, '0c0i4c4i'),
    'O': (4.0, '1c0d0h1i3i4h4d3c1c'),
    'P': (4.0, '0c0i3i4h4g3f0f'),
    'Q': (4.0, '1c0d0h1i3i4h4d3c1c 2e4b'),
    'R': (4.0, '0c0i3i4h4g3f0f 2f4c'),
    'S': (4.0, '4h3i1i0h0g1f3f4e4d3c1c0d'),
    'T': (4.0, '0i4i 2i2c'),
    'U': (4.0, '0i0d1c3c4d4i'),
    'V': (4.0, '0i2c4i'),
    'W': (4.0, '0i1c2f3c4i'),
    'X': (4.0, '0i4c 0c4i'),
    'Y': (4.0, '0i2f4i 2f2c'),
    'Z': (4.0, '0i4i0c4c'),
    '0': (4.0, '1c0d0h1i3i4h4d3c1c'),
    '1': (4.0, '1h2i2c 1c3c'),
    '2': (4.0, '0h1i3i4h4g0c4c'),
    '3': (4.0, '0h1i3i4h4g3f2f 3f4e4d3c1c0d'),
    '4': (4.0, '3c3i0e4e'),
    '5': (4.0, '4i0i0f3f4e4d3c1c0d'),
    '6': (4.0, '4h3i1i0h0d1c3c4d4e3f1f0e'),
    '7': (4.0, '0i4i1c'),
    '8': (4.0, '1f0g0h1i3i4h4g3f1f0e0d1c3c4d4e3f'),
    '9': (4.0, '4f1f0g0h1i3i4h4d3c1c0d'),
    'a': (4.0, '4g4c 4f3g1g0f0d1c3c4d'),
    'b': (4.0, '0i0c 0d1c3c4d4f3g1g0f'),
    'c': (4.0, '4f3g1g0f0d1c3c4d'),
    'd': (4.0, '4i4c 4d3c1c0d0f1g3g4f'),
    'e': (4.0, '0e4e4f3g1g0f0d1c3c4d'),
    'f': (3.0, '3i2i1h1c 0g3g'),
    'g': (4.0, '4g4b3a1a0b 4f3g1g0f0d1c3c4d'),
    'h': (4.0, '0i0c 0f1g3g4f4c'),
    'i': (1.0, '0c0g 0h0i'),
    'j': (2.0, '2g2b1a0a 2h2i'),
    'k': (4.0, '0i0c 3g0d 1e3c'),
    'l': (2.0, '1i1d2c'),
    'm': (4.0, '0c0g 0f1g2f2c 2f3g4f4c'),
    'n': (4.0, '0c0g 0f1g3g4f4c'),
    'o': (4.0, '1c0d0f1g3g4f4d3c1c'),
    'p': (4.0, '0g0a 0f1g3g4f4d3c1c0d'),
    'q': (4.0, '4g4a 4f3g1g0f0d1c3c4d'),
    'r': (3.0, '0c0g 0e2g3g'),
    's': (4.0, '4f3g1g0f1e3e4d3c1c0d'),
    't': (3.0, '1i1d2c3c 0g3g'),
    'u': (4.0, '0g0d1c3c4d 4g4c'),
    'v': (4.0, '0g2c4g'),
    'w': (4.0, '0g1c2f3c4g'),
    'x': (4.0, '0g4c 0c4g'),
    'y': (4.0, '0g2c 4g1a0a'),
    'z': (4.0, '0g4g0c4c'),
    '!': (1.0, '0i0e 0d0c'),
    '"': (2.0, '0i0g 2i2g'),
    '#': (4.0, '1c1i 3c3i 0e4e 0g4g'),
    '$': (4.0, '4h3i1i0h0g1f3f4e4d3c1c0d 2i2c'),
    '%': (4.0, '0c4i 0i0h1h1i0i 3c3d4d4c3c'),
    '&': (4.0, '4c1h1i2i3h0e0d1c2c4e'),
    "'": (1.0, '0i0g'),
    '(': (2.0, '2i1h0f0e1d2c'),
    ')': (2.0, '0i1h2f2e1d0c'),
    '*': (4.0, '2h2d 0g4e 0e4g'),
    '+': (4.0, '2d2h 0f4f'),
    ',': (1.0, '1d1c0b'),
    '-': (4.0, '0f4f'),
    '.': (1.0, '0c0d'),
    '/': (4.0, '0c4i'),
    ':': (1.0, '0c0d 0g0h'),
    ';': (1.0, '1d1c0b 1g1h'),
    '<': (4.0, '4h0f4d'),
    '=': (4.0, '0e4e 0g4g'),
    '>': (4.0, '0h4f0d'),
    '?': (4.0, '0h1i3i4h4g2f2e 2d2c'),
    '@': (4.0, '3e3g1g1e3e4f4h3i1i0h0d1c4c'),
    '[': (2.0, '2i0i0c2c'),
    '\\': (4.0, '0i4c'),
    ']': (2.0, '0i2i2c0c'),
    '^': (4.0, '0g2i4g'),
    '_': (4.0, '0b4b'),
    '`': (1.0, '0i1h'),
    '{': (2.0, '2i1h1g0f1e1d2c'),
    '|': (1.0, '0i0a'),
    '}': (2.0, '0i1h1g2f1e1d0c'),
    '~': (4.0, '0g1h3f4g'),
    '°': (2.0, '1i0h1g2h1i'),
    '±': (4.0, '2e2i 0g4g 0d4d'),
    'Ø': (4.0, '1c0d0h1i3i4h4d3c1c 0c4i'),
    'ø': (4.0, '1c0d0h1i3i4h4d3c1c 0c4i'),
    '⌀': (4.0, '1c0d0h1i3i4h4d3c1c 0c4i'),
    '•': (2.0, '1d0e1f2e1d 0e2e 1d1f'),
}

# --- ajouts ------------------------------------------------------------------------------

#: (largeur, traits sur la grille, traits en nombres [[(x, y)…]…])
_EXTRA = {
    'ı': (1.0, '0c0g', []),
    'ȷ': (2.0, '2g2b1a0a', []),
    'ß': (4.0, '0c0h1i3i4h4g3f2f 3f4e4d3c1c', []),
    'æ': (8.0, '4g4c 4f3g1g0f0d1c3c4d 4e8e8f7g5g4f 4d5c7c8d', []),
    'Æ': (8.0, '0c4i8i 4i4c8c 2f7f', []),
    'œ': (8.0, '1c0d0f1g3g4f4d3c1c 4e8e8f7g5g4f 4d5c7c8d', []),
    'Œ': (8.0, '8i1i0h0d1c8c 4i4c 4f7f', []),
    'Ł': (4.0, '0i0c4c', [[(-1.0, 2.4), (1.4, 4.0)]]),
    'ł': (2.0, '1i1d2c', [[(0.0, 2.6), (2.0, 4.4)]]),
    '£': (4.0, '4h3i2i1h1d0c4c 0f3f', []),
    '€': (4.0, '4h3i1i0h0d1c3c4d', [[(-0.6, 2.4), (2.6, 2.4)], [(-0.6, 3.6), (2.6, 3.6)]]),
    '«': (3.5, '', [[(1.5, 3.5), (0.0, 2.0), (1.5, 0.5)], [(3.5, 3.5), (2.0, 2.0), (3.5, 0.5)]]),
    '»': (3.5, '', [[(0.0, 3.5), (1.5, 2.0), (0.0, 0.5)], [(2.0, 3.5), (3.5, 2.0), (2.0, 0.5)]]),
    '‹': (1.5, '', [[(1.5, 3.5), (0.0, 2.0), (1.5, 0.5)]]),
    '›': (1.5, '', [[(0.0, 3.5), (1.5, 2.0), (0.0, 0.5)]]),
    '‘': (1.0, '0g0h1i', []),
    '’': (1.0, '1i1h0g', []),
    '‚': (1.0, '1d1c0b', []),
    '“': (3.0, '0g0h1i 2g2h3i', []),
    '”': (3.0, '1i1h0g 3i3h2g', []),
    '„': (3.0, '1d1c0b 3d3c2b', []),
    '–': (4.0, '0f4f', []),
    '—': (8.0, '0f8f', []),
    '…': (5.0, '0c0d 2c2d 4c4d', []),
    '·': (1.0, '0e0f', []),
    '×': (4.0, '', [[(0.6, 1.6), (3.4, 4.4)], [(0.6, 4.4), (3.4, 1.6)]]),
    '÷': (4.0, '0f4f', [[(2.0, 0.8), (2.0, 1.8)], [(2.0, 4.2), (2.0, 5.2)]]),
    'µ': (4.0, '0g0a 0d1c3c4d 4g4c', []),
    '©': (6.0, '2c0e0g2i4i6g6e4c2c', [[(4.0, 3.8), (3.5, 4.3), (2.5, 4.3), (2.0, 3.8), (2.0, 2.2), (2.5, 1.7),
                                        (3.5, 1.7), (4.0, 2.2)]]),
    '®': (6.0, '2c0e0g2i4i6g6e4c2c', [[(2.2, 1.5), (2.2, 4.5), (3.4, 4.5), (4.0, 4.0), (4.0, 3.5), (3.4, 3.0),
                                        (2.2, 3.0)], [(3.0, 3.0), (4.0, 1.5)]]),
    ' ': (1.2, '', []),          # espace fine
    ' ': (1.2, '', []),          # espace fine insécable (avant « ; : ! ? » en français)
}

#: exposants : (glyphe, réduction, montée)
_SMALL = {'¹': ('1', 0.5, 3.5), '²': ('2', 0.5, 3.5), '³': ('3', 0.5, 3.5),
          'ª': ('a', 0.6, 3.2), 'º': ('o', 0.6, 3.2)}
#: glyphes tournés d'un demi-tour : ¡ ¿
_TURNED = {'¡': '!', '¿': '?'}

#: diacritiques combinants : traits centrés sur x = 0, posés sur y = 0
#: (au-dessus : vers le haut ; cédille, ogonek : vers le bas)
_MARKS = {
    0x300: [[(-0.5, 1.2), (0.5, 0.0)]],                                        # grave
    0x301: [[(-0.5, 0.0), (0.5, 1.2)]],                                        # aigu
    0x302: [[(-1.0, 0.0), (0.0, 1.0), (1.0, 0.0)]],                            # circonflexe
    0x303: [[(-1.2, 0.2), (-0.5, 0.9), (0.5, 0.2), (1.2, 0.9)]],               # tilde
    0x304: [[(-1.0, 0.5), (1.0, 0.5)]],                                        # macron
    0x306: [[(-1.0, 1.0), (-0.6, 0.2), (0.0, 0.0), (0.6, 0.2), (1.0, 1.0)]],   # brève
    0x307: [[(0.0, 0.0), (0.0, 1.0)]],                                         # point
    0x308: [[(-0.8, 0.0), (-0.8, 1.0)], [(0.8, 0.0), (0.8, 1.0)]],             # tréma
    0x30A: [[(0.0, 0.0), (-0.6, 0.6), (0.0, 1.2), (0.6, 0.6), (0.0, 0.0)]],    # rond
    0x30B: [[(-1.0, 0.0), (-0.2, 1.2)], [(0.2, 0.0), (1.0, 1.2)]],             # double aigu
    0x30C: [[(-1.0, 1.0), (0.0, 0.0), (1.0, 1.0)]],                            # caron
    0x327: [[(0.0, 0.0), (0.0, -0.6), (0.7, -1.0), (0.0, -1.6)]],              # cédille
    0x328: [[(0.0, 0.0), (-0.6, -0.8), (0.0, -1.6), (0.6, -1.4)]],             # ogonek
}
_BELOW = {0x327, 0x328}


def is_stroke(path) -> bool:
    return str(path) == PATH


def _decode(spec: str) -> list:
    """Traits notés sur la grille → [[(x, y)…]…]."""
    out = []
    for run in spec.split():
        pts = [(float(ord(run[i]) - 48), float(ord(run[i + 1]) - 97 - 2)) for i in range(0, len(run) - 1, 2)]
        if pts:
            out.append(pts)
    return out


@functools.lru_cache(maxsize=1024)
def _strokes(ch: str):
    """(largeur, traits) d'un caractère sur la grille, ou None (absent)."""
    if ch in _GLYPHS:
        w, spec = _GLYPHS[ch]
        return w, tuple(tuple(s) for s in _decode(spec))
    if ch in _EXTRA:
        w, spec, more = _EXTRA[ch]
        return w, tuple(tuple(s) for s in _decode(spec) + [list(m) for m in more])
    if ch in _SMALL:
        base, k, dy = _SMALL[ch]
        w, runs = _strokes(base)
        return w * k, tuple(tuple((x * k, y * k + dy) for x, y in s) for s in runs)
    if ch in _TURNED:
        w, runs = _strokes(_TURNED[ch])
        xs = [x for s in runs for x, _y in s]
        sx = min(xs) + max(xs)
        return w, tuple(tuple((sx - x, 4.0 - y) for x, y in s) for s in runs)
    if ch.isspace():
        return SPACE, ()
    d = unicodedata.normalize('NFD', ch)
    if len(d) < 2 or any(ord(m) not in _MARKS for m in d[1:]):
        return None
    got = _strokes({'i': 'ı', 'j': 'ȷ'}.get(d[0], d[0]))
    if got is None or not got[1]:
        return None
    w, runs = got
    pts = [p for s in runs for p in s]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    cx = (min(xs) + max(xs)) / 2
    if d[0] in 'ij':                                   # sur la hampe
        cx = max(runs[0], key=lambda p: p[1])[0]
    top = max(ys)
    tall = top > 4.5                                   # capitales, ascendantes : accents serrés
    k, gap = (0.75, 0.7) if tall else (1.0, 1.0)
    out = list(runs)
    for m in d[1:]:
        cp = ord(m)
        if cp in _BELOW:
            x0 = max(xs) - 0.6 if cp == 0x328 else cx
            out += [tuple((x0 + x, y) for x, y in s) for s in _MARKS[cp]]
            continue
        y0 = top + gap
        out += [tuple((cx + x, y0 + y * k) for x, y in s) for s in _MARKS[cp]]
        top = y0 + max(y for s in _MARKS[cp] for _x, y in s) * k
        gap = 0.4
    return w, tuple(out)


def has(ch: str) -> bool:
    return _strokes(ch) is not None


@functools.lru_cache(maxsize=4096)
def glyph(char: str) -> tuple[Path, float]:
    """(contours en hauteur de capitales 1, avance) ; caractère absent :
    rien, avec la place d'une lettre moyenne."""
    got = _strokes(char)
    if got is None:
        return Path(), (4.0 + GAP) / CAP
    w, runs = got
    contours = []
    for s in runs:
        pts = [(x / CAP, y / CAP) for x, y in s]
        segs = [Line(a, b) for a, b in zip(pts, pts[1:]) if a != b]
        if segs:
            contours.append(Contour(segs, len(segs) > 1 and pts[0] == pts[-1]))
    return Path(contours), (w + GAP) / CAP


def metrics() -> dict:
    """Hauteur des capitales 1, comme les polices Gravotech."""
    return {'upem': 1.0, 'ascent': ASCENT, 'descent': DESCENT, 'cap': 1.0}


def characters() -> tuple:
    """Caractères dessinés : la table, les ajouts et les lettres latines
    accentuées que la composition sait faire (Latin-1 et Latin étendu A)."""
    pool = set(_GLYPHS) | set(_EXTRA) | set(_SMALL) | set(_TURNED)
    pool |= {chr(c) for c in range(0xC0, 0x180) if _strokes(chr(c)) is not None}
    return tuple(sorted(c for c in pool if c >= ' ' and not c.isspace() or c == ' '))
