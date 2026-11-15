"""Braille français (6 points, braille intégral) → points à graver ou à
percer.

Table : alphabet, lettres accentuées françaises, chiffres en notation
Antoine précédés du signe numérique (point 6), signe de majuscule (points
4-6), ponctuation courante. Les caractères Unicode braille (U+2800 à
U+28FF) sont recopiés point pour point : c'est le moyen sûr d'imposer une
transcription faite par un spécialiste.

Cotes par défaut (signalétique) : point Ø 1,5 mm, 2,5 mm entre points
d'une cellule, 6 mm entre cellules, 10 mm entre lignes — toutes réglables.
**Une transcription doit être relue par un lecteur braille** avant
fabrication : la table couvre l'usuel, pas l'abrégé ni les cas
particuliers (mathématiques, informatique…).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from . import geom
from .document import Group, Shape
from .geom import Path

# points numérotés 1-2-3 (colonne gauche, haut en bas) et 4-5-6 (droite)
LETTERS = {
    'a': '1', 'b': '12', 'c': '14', 'd': '145', 'e': '15', 'f': '124', 'g': '1245', 'h': '125',
    'i': '24', 'j': '245', 'k': '13', 'l': '123', 'm': '134', 'n': '1345', 'o': '135',
    'p': '1234', 'q': '12345', 'r': '1235', 's': '234', 't': '2345', 'u': '136', 'v': '1236',
    'w': '2456', 'x': '1346', 'y': '13456', 'z': '1356',
    # lettres accentuées du français
    'ç': '12346', 'é': '123456', 'à': '12356', 'è': '2346', 'ù': '23456', 'â': '16', 'ê': '126',
    'î': '146', 'ô': '1456', 'û': '156', 'ë': '1246', 'ï': '12456', 'ü': '1256', 'œ': '246',
}
#: chiffres, notation Antoine (lettres a à j + point 6), après le signe numérique
DIGITS = {'1': '16', '2': '126', '3': '146', '4': '1456', '5': '156', '6': '1246',
          '7': '12456', '8': '1256', '9': '246', '0': '3456'}
PUNCT = {',': '2', ';': '23', ':': '25', '.': '256', '?': '26', '!': '235', "'": '3', '’': '3',
         '-': '36', '(': '236', ')': '356', '"': '2356', '/': '34', '*': '35'}
#: dans un nombre : virgule décimale (point 2), séparateur de milliers (point 3)
NUMBER_PUNCT = {',': '2', '.': '3'}
NUMBER_SIGN = '6'
CAPITAL_SIGN = '46'


class BrailleError(ValueError):
    pass


def cells(text: str, *, capitals: bool = True) -> list[list[str]]:
    """Lignes de cellules (chaque cellule = chaîne des points, '' = espace).

    Majuscules : signe 4-6 devant la lettre ; mot entièrement en capitales
    (deux lettres ou plus) : signe double 4-6 4-6 une seule fois."""
    import re
    lines = []
    for raw in text.split('\n'):
        out: list[str] = []
        number = False
        caps_word = False
        i = 0
        while i < len(raw):
            ch = raw[i]
            code = ord(ch)
            if 0x2800 <= code <= 0x28FF:                 # braille Unicode tel quel
                bits = code - 0x2800
                out.append(''.join(str(k + 1) for k in range(6) if bits >> k & 1))
                number = caps_word = False
            elif ch == ' ':
                out.append('')
                number = caps_word = False
            elif ch.isdigit():
                if not number:
                    out.append(NUMBER_SIGN)
                    number = True
                out.append(DIGITS[ch])
            elif number and ch in NUMBER_PUNCT and i + 1 < len(raw) and raw[i + 1].isdigit():
                out.append(NUMBER_PUNCT[ch])             # 3,5 ou 1.000 : dans le nombre
            else:
                number = False
                low = ch.lower()
                if low in LETTERS:
                    if ch != low and capitals and not caps_word:
                        word = re.match(r'[^\W\d_]+', raw[i:]).group(0)
                        if len(word) >= 2 and word == word.upper():
                            out += [CAPITAL_SIGN, CAPITAL_SIGN]
                            caps_word = True
                        else:
                            out.append(CAPITAL_SIGN)
                    out.append(LETTERS[low])
                elif ch in PUNCT:
                    out.append(PUNCT[ch])
                    caps_word = False
                else:
                    raise BrailleError(f'caractère sans équivalent braille dans la table : {ch!r}')
            i += 1
        lines.append(out)
    return lines


def unicode_braille(text: str, *, capitals: bool = True) -> str:
    """Transcription en caractères Unicode braille (pour relecture)."""
    def ch(c):
        return chr(0x2800 + sum(1 << (int(d) - 1) for d in c)) if c else ' '
    return '\n'.join(''.join(ch(c) for c in line) for line in cells(text, capitals=capitals))


@dataclass
class BrailleSpec:
    text: str = ''
    dot: float = 1.5            # diamètre du point (mm)
    dot_pitch: float = 2.5      # entre points d'une cellule
    cell_pitch: float = 6.0     # entre cellules
    line_pitch: float = 10.0    # entre lignes
    capitals: bool = True

    @classmethod
    def from_dict(cls, d: dict) -> 'BrailleSpec':
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


#: position (colonne, rang) de chaque point dans la cellule
_POS = {'1': (0, 0), '2': (0, 1), '3': (0, 2), '4': (1, 0), '5': (1, 1), '6': (1, 2)}


def dots(spec: BrailleSpec) -> list[tuple[float, float]]:
    """Centres des points ; origine = point 1 de la première cellule."""
    out = []
    for li, line in enumerate(cells(spec.text, capitals=spec.capitals)):
        for ci, cell in enumerate(line):
            for d in cell:
                col, row = _POS[d]
                out.append((ci * spec.cell_pitch + col * spec.dot_pitch,
                            -li * spec.line_pitch - row * spec.dot_pitch))
    return out


def build(spec: BrailleSpec, tool: int = 0) -> Group:
    r = spec.dot / 2
    shape = Shape(path=Path([geom.circle(c, r) for c in dots(spec)]), filled=True, tool=tool, name='points')
    g = Group(children=[shape], name=f'Braille : {spec.text}', tool=tool)
    g.extra['braille'] = asdict(spec)
    return g
