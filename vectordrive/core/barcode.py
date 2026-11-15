"""Codes-barres : DataMatrix (ECC200), QR Code, Code 39, EAN-13, Code 128.

Module repris de TauDrive (`Cielle Incicam/atelier/src/engrave/barcode.py`,
même auteur) ; Code 128 ajouté pour VectorDrive.

Encodeurs **en Python pur**, sans dépendance externe : l'application est
distribuée figée sur des postes d'atelier, et une bibliothèque native de
plus serait une bibliothèque de plus à embarquer et à faire vivre.

Chaque encodeur rend une **matrice de booléens**, `True` = module sombre,
première ligne en haut. `engrave.toolpath` la transforme ensuite en
rectangles à graver.

Références : ISO/IEC 16022 (DataMatrix ECC200) et ISO/IEC 18004 (QR Code).
"""
from __future__ import annotations

Matrix = list[list[bool]]


class CodeError(ValueError):
    """Donnée impossible à encoder dans la symbologie demandée."""


# --------------------------------------------------------------------------
# Reed-Solomon sur GF(256)
# --------------------------------------------------------------------------
#
# Les deux symbologies emploient Reed-Solomon, mais **pas le même corps** :
# QR réduit modulo 0x11D, DataMatrix modulo 0x12D. D'où le paramètre.

class _Field:
    """Corps de Galois GF(256) d'une symbologie.

    Deux réglages les distinguent : le polynôme primitif, et **l'exposant
    de la première racine** du polynôme générateur. QR part de alpha^0,
    DataMatrix de alpha^1 — un détail qui ne se voit pas sur la taille du
    symbole mais donne des octets de correction entièrement faux.
    """

    def __init__(self, primitive: int, generator: int = 2,
                 first_root: int = 0) -> None:
        self.first_root = first_root
        self.exp = [0] * 512
        self.log = [0] * 256
        x = 1
        for i in range(255):
            self.exp[i] = x
            self.log[x] = i
            x *= generator
            if x >= 256:
                x ^= primitive
        for i in range(255, 512):
            self.exp[i] = self.exp[i - 255]

    def mul(self, a: int, b: int) -> int:
        if a == 0 or b == 0:
            return 0
        return self.exp[self.log[a] + self.log[b]]

    def generator_poly(self, n: int) -> list[int]:
        poly = [1]
        for i in range(n):
            poly = self._poly_mul(poly, [1, self.exp[i + self.first_root]])
        return poly

    def _poly_mul(self, p: list[int], q: list[int]) -> list[int]:
        out = [0] * (len(p) + len(q) - 1)
        for i, a in enumerate(p):
            if a == 0:
                continue
            for j, b in enumerate(q):
                out[i + j] ^= self.mul(a, b)
        return out

    def remainder(self, data: list[int], n: int) -> list[int]:
        """Les `n` octets de correction d'erreur de `data`."""
        gen = self.generator_poly(n)
        rest = [0] * n
        for byte in data:
            factor = byte ^ rest[0]
            rest = rest[1:] + [0]
            if factor:
                for i, g in enumerate(gen[1:]):
                    rest[i] ^= self.mul(g, factor)
        return rest


_QR_FIELD = _Field(0x11D)
_DM_FIELD = _Field(0x12D, first_root=1)


# --------------------------------------------------------------------------
# DataMatrix ECC200
# --------------------------------------------------------------------------
#
# Chaque entrée décrit un symbole ECC200 :
#   (lignes, colonnes, lignes de région, colonnes de région,
#    régions en Y, régions en X, octets de données, octets de correction,
#    nombre de blocs)
#
# Les symboles **rectangulaires** ne sont pas une curiosité : c'est ce
# qu'on emploie sur une plaque étroite, et c'est ce que porte le DXF de
# production `DataMatrix.dxf` — un 8 x 18 étiré dans une fenêtre de
# 15 x 7 mm.
_DM_SQUARE = (
    (10, 10, 8, 8, 1, 1, 3, 5, 1), (12, 12, 10, 10, 1, 1, 5, 7, 1),
    (14, 14, 12, 12, 1, 1, 8, 10, 1), (16, 16, 14, 14, 1, 1, 12, 12, 1),
    (18, 18, 16, 16, 1, 1, 18, 14, 1), (20, 20, 18, 18, 1, 1, 22, 18, 1),
    (22, 22, 20, 20, 1, 1, 30, 20, 1), (24, 24, 22, 22, 1, 1, 36, 24, 1),
    (26, 26, 24, 24, 1, 1, 44, 28, 1), (32, 32, 14, 14, 2, 2, 62, 36, 1),
    (36, 36, 16, 16, 2, 2, 86, 42, 1), (40, 40, 18, 18, 2, 2, 114, 48, 1),
    (44, 44, 20, 20, 2, 2, 144, 56, 1), (48, 48, 22, 22, 2, 2, 174, 68, 1),
    (52, 52, 24, 24, 2, 2, 204, 42, 2),
)

_DM_RECT = (
    (8, 18, 6, 16, 1, 1, 5, 7, 1), (8, 32, 6, 14, 1, 2, 10, 11, 1),
    (12, 26, 10, 24, 1, 1, 16, 14, 1), (12, 36, 10, 16, 1, 2, 22, 18, 1),
    (16, 36, 14, 16, 1, 2, 32, 24, 1), (16, 48, 14, 22, 1, 2, 49, 28, 1),
)

#: Toutes les tailles, rectangulaires d'abord : à donnée égale, un
#: rectangle occupe moins de hauteur, ce qui est ce qu'on cherche sur une
#: plaque étroite.
_DM_SIZES = _DM_SQUARE

#: Formes proposées dans l'interface.
DM_SHAPES = (('square', 'carré'), ('rect', 'rectangulaire'),
             ('auto', 'au plus juste'))


def _dm_candidates(shape: str):
    if shape == 'rect':
        return _DM_RECT
    if shape == 'auto':
        # à capacité égale on préfère le plus petit nombre de modules
        return tuple(sorted(_DM_SQUARE + _DM_RECT,
                            key=lambda s: (s[6], s[0] * s[1])))
    return _DM_SQUARE


def _dm_encode_ascii(data: bytes) -> list[int]:
    """Encodage ASCII de la norme : paires de chiffres, puis octet à octet."""
    out: list[int] = []
    i = 0
    while i < len(data):
        a = data[i]
        if 48 <= a <= 57 and i + 1 < len(data) and 48 <= data[i + 1] <= 57:
            out.append((a - 48) * 10 + (data[i + 1] - 48) + 130)
            i += 2
        elif a < 128:
            out.append(a + 1)
            i += 1
        else:
            out.append(235)            # bascule vers le haut de la table
            out.append(a - 128 + 1)
            i += 1
    return out


def _dm_pad(words: list[int], capacity: int) -> list[int]:
    """Complète jusqu'à la capacité : un 129, puis un remplissage brouillé.

    Le brouillage est imposé par la norme ; il évite les aplats réguliers
    qui gêneraient la lecture.
    """
    if len(words) > capacity:
        raise CodeError('donnée trop longue')
    words = list(words)
    if len(words) < capacity:
        words.append(129)
        while len(words) < capacity:
            position = len(words) + 1
            pseudo = ((149 * position) % 253) + 1
            value = 129 + pseudo
            words.append(value - 254 if value > 254 else value)
    return words[:capacity]


def _dm_ecc(words: list[int], size) -> list[int]:
    """Ajoute les octets de correction, entrelacés par bloc."""
    ecc_len, blocks = size[7], size[8]
    ecc_all = [0] * (ecc_len * blocks)
    for b in range(blocks):
        block = words[b::blocks] if blocks > 1 else list(words)
        for i, value in enumerate(_DM_FIELD.remainder(block, ecc_len)):
            ecc_all[i * blocks + b] = value
    return list(words) + ecc_all


def _dm_place(words: list[int], rows: int, cols: int) -> Matrix:
    """Placement nominal ECC200 (ISO/IEC 16022, annexe F)."""
    grid: list[list[int | None]] = [[None] * cols for _ in range(rows)]

    def put(row: int, col: int, bit: int) -> None:
        if row < 0:
            row += rows
            col += 4 - ((rows + 4) % 8)
        if col < 0:
            col += cols
            row += 4 - ((cols + 4) % 8)
        grid[row][col] = bit

    def utah(row: int, col: int, char: int) -> None:
        b = words[char]
        put(row - 2, col - 2, (b >> 7) & 1)
        put(row - 2, col - 1, (b >> 6) & 1)
        put(row - 1, col - 2, (b >> 5) & 1)
        put(row - 1, col - 1, (b >> 4) & 1)
        put(row - 1, col, (b >> 3) & 1)
        put(row, col - 2, (b >> 2) & 1)
        put(row, col - 1, (b >> 1) & 1)
        put(row, col, b & 1)

    def corner(kind: int, char: int) -> None:
        b = words[char]
        bits = [(b >> (7 - i)) & 1 for i in range(8)]
        spots = {
            1: ((rows - 1, 0), (rows - 1, 1), (rows - 1, 2), (0, cols - 2),
                (0, cols - 1), (1, cols - 1), (2, cols - 1), (3, cols - 1)),
            2: ((rows - 3, 0), (rows - 2, 0), (rows - 1, 0), (0, cols - 4),
                (0, cols - 3), (0, cols - 2), (0, cols - 1), (1, cols - 1)),
            3: ((rows - 3, 0), (rows - 2, 0), (rows - 1, 0), (0, cols - 2),
                (0, cols - 1), (1, cols - 1), (2, cols - 1), (3, cols - 1)),
            4: ((rows - 1, 0), (rows - 1, cols - 1), (0, cols - 3),
                (0, cols - 2), (0, cols - 1), (1, cols - 3), (1, cols - 2),
                (1, cols - 1)),
        }[kind]
        for (r, c), bit in zip(spots, bits):
            grid[r][c] = bit

    char = 0
    row, col = 4, 0
    while True:
        if row == rows and col == 0:
            corner(1, char)
            char += 1
        elif row == rows - 2 and col == 0 and cols % 4:
            corner(2, char)
            char += 1
        elif row == rows - 2 and col == 0 and cols % 8 == 4:
            corner(3, char)
            char += 1
        elif row == rows + 4 and col == 2 and cols % 8 == 0:
            corner(4, char)
            char += 1

        while True:                                  # diagonale montante
            if row < rows and col >= 0 and grid[row][col] is None:
                utah(row, col, char)
                char += 1
            row -= 2
            col += 2
            if not (row >= 0 and col < cols):
                break
        row += 1
        col += 3

        while True:                                  # diagonale descendante
            if row >= 0 and col < cols and grid[row][col] is None:
                utah(row, col, char)
                char += 1
            row += 2
            col -= 2
            if not (row < rows and col >= 0):
                break
        row += 3
        col += 1
        if not (row < rows or col < cols):
            break

    if grid[rows - 1][cols - 1] is None:             # damier de coin
        grid[rows - 1][cols - 1] = 1
        grid[rows - 2][cols - 2] = 1
        grid[rows - 1][cols - 2] = 0
        grid[rows - 2][cols - 1] = 0
    return [[bool(v) for v in line] for line in grid]


def datamatrix(text: str, shape: str = 'square',
               min_side: int = 0) -> Matrix:
    """Matrice d'un DataMatrix ECC200, motifs de repérage compris.

    `shape` vaut `square`, `rect` ou `auto`. `min_side` impose un nombre
    minimal de modules sur le petit côté.
    """
    data = text.encode('latin-1', errors='replace')
    words = _dm_encode_ascii(data)
    candidates = _dm_candidates(shape)
    size = next((s for s in candidates
                 if s[6] >= len(words) and min(s[0], s[1]) >= min_side), None)
    if size is None:
        best = max(s[6] for s in candidates)
        raise CodeError(
            f'{len(words)} octets : au-delà de la capacité des symboles '
            f'gérés ({best} octets)')

    rows, cols, r_rows, r_cols, regions_y, regions_x, data_len = size[:7]
    words = _dm_ecc(_dm_pad(words, data_len), size)
    nominal = _dm_place(words, r_rows * regions_y, r_cols * regions_x)

    # découpage en régions, chacune bordée de son « L » plein et de son
    # bord alterné : c'est ce qui rend le symbole repérable
    out = [[False] * cols for _ in range(rows)]
    for ry in range(regions_y):
        for rx in range(regions_x):
            top = ry * (r_rows + 2)
            left = rx * (r_cols + 2)
            for i in range(r_cols + 2):
                out[top + r_rows + 1][left + i] = True          # « L » bas
                out[top][left + i] = (i % 2 == 0)               # bord haut
            for i in range(r_rows + 2):
                out[top + i][left] = True                       # « L » gauche
                out[top + i][left + r_cols + 1] = (i % 2 == 1)  # bord droit
            for y in range(r_rows):
                for x in range(r_cols):
                    out[top + y + 1][left + x + 1] =                         nominal[ry * r_rows + y][rx * r_cols + x]
    return out


# --------------------------------------------------------------------------
# QR Code — mode octet, versions 1 à 10
# --------------------------------------------------------------------------
#
# Ces dix versions couvrent jusqu'à 271 octets au niveau L : très au-delà
# de ce qu'on marque sur une plaque. Les versions supérieures n'ajoutent
# que de la surface perdue.

#: (octets de correction par bloc, blocs courts, blocs longs)
_QR_EC = {
    1: {'L': (7, 1, 0), 'M': (10, 1, 0), 'Q': (13, 1, 0), 'H': (17, 1, 0)},
    2: {'L': (10, 1, 0), 'M': (16, 1, 0), 'Q': (22, 1, 0), 'H': (28, 1, 0)},
    3: {'L': (15, 1, 0), 'M': (26, 1, 0), 'Q': (18, 2, 0), 'H': (22, 2, 0)},
    4: {'L': (20, 1, 0), 'M': (18, 2, 0), 'Q': (26, 2, 0), 'H': (16, 4, 0)},
    5: {'L': (26, 1, 0), 'M': (24, 2, 0), 'Q': (18, 2, 2), 'H': (22, 2, 2)},
    6: {'L': (18, 2, 0), 'M': (16, 4, 0), 'Q': (24, 4, 0), 'H': (28, 4, 0)},
    7: {'L': (20, 2, 0), 'M': (18, 4, 0), 'Q': (18, 2, 4), 'H': (26, 4, 1)},
    8: {'L': (24, 2, 0), 'M': (22, 2, 2), 'Q': (22, 4, 2), 'H': (26, 4, 2)},
    9: {'L': (30, 2, 0), 'M': (22, 3, 2), 'Q': (20, 4, 4), 'H': (24, 4, 4)},
    10: {'L': (18, 2, 2), 'M': (26, 4, 1), 'Q': (24, 6, 2), 'H': (28, 6, 2)},
}

#: Nombre total d'octets (données + correction) par version.
_QR_TOTAL = {1: 26, 2: 44, 3: 70, 4: 100, 5: 134, 6: 172, 7: 196, 8: 242,
             9: 292, 10: 346}

#: Positions des motifs d'alignement, versions 2 à 10.
_QR_ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30],
             6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46],
             10: [6, 28, 50]}

_QR_LEVEL_BITS = {'L': 0b01, 'M': 0b00, 'Q': 0b11, 'H': 0b10}

#: Niveaux de correction proposés, du plus économe au plus robuste.
QR_LEVELS = (('L', 'L — 7 %'), ('M', 'M — 15 %'),
             ('Q', 'Q — 25 %'), ('H', 'H — 30 %'))


def _qr_blocks(version: int, level: str) -> tuple[int, list[int]]:
    """Octets de correction par bloc, et taille de chaque bloc de données."""
    ec_len, short, long_ = _QR_EC[version][level]
    blocks = short + long_
    total_data = _QR_TOTAL[version] - ec_len * blocks
    base = total_data // blocks
    sizes = [base] * short + [base + 1] * long_
    if sum(sizes) != total_data:                 # garde-fou sur les tables
        raise CodeError(f'table QR incohérente (version {version}, {level})')
    return ec_len, sizes


def _qr_capacity(version: int, level: str) -> int:
    """Nombre d'octets encodables, en mode octet."""
    _, sizes = _qr_blocks(version, level)
    header = 4 + (8 if version < 10 else 16)     # mode + longueur, en bits
    return (sum(sizes) * 8 - header) // 8


def _qr_bitstream(data: bytes, version: int, level: str) -> list[int]:
    ec_len, sizes = _qr_blocks(version, level)
    bits: list[int] = []

    def push(value: int, width: int) -> None:
        for i in range(width - 1, -1, -1):
            bits.append((value >> i) & 1)

    push(0b0100, 4)                               # mode octet
    push(len(data), 8 if version < 10 else 16)
    for byte in data:
        push(byte, 8)

    capacity_bits = sum(sizes) * 8
    push(0, min(4, capacity_bits - len(bits)))    # terminateur
    while len(bits) % 8:
        bits.append(0)
    filler = (0xEC, 0x11)
    i = 0
    while len(bits) < capacity_bits:
        push(filler[i % 2], 8)
        i += 1

    words = []
    for k in range(0, len(bits), 8):
        value = 0
        for bit in bits[k:k + 8]:
            value = (value << 1) | bit
        words.append(value)

    groups, ecc, offset = [], [], 0
    for length in sizes:
        block = words[offset:offset + length]
        offset += length
        groups.append(block)
        ecc.append(_QR_FIELD.remainder(block, ec_len))

    out: list[int] = []
    for i in range(max(sizes)):                   # entrelacement
        for block in groups:
            if i < len(block):
                out.append(block[i])
    for i in range(ec_len):
        for block in ecc:
            out.append(block[i])

    stream: list[int] = []
    for byte in out:
        for i in range(7, -1, -1):
            stream.append((byte >> i) & 1)
    return stream


def _qr_skeleton(version: int) -> tuple[Matrix, list[list[bool]]]:
    """Motifs fixes du symbole, et masque des positions réservées."""
    size = version * 4 + 17
    grid = [[False] * size for _ in range(size)]
    fixed = [[False] * size for _ in range(size)]

    def finder(top: int, left: int) -> None:
        for y in range(-1, 8):
            for x in range(-1, 8):
                r, c = top + y, left + x
                if not (0 <= r < size and 0 <= c < size):
                    continue
                grid[r][c] = ((0 <= y <= 6 and x in (0, 6))
                              or (0 <= x <= 6 and y in (0, 6))
                              or (2 <= x <= 4 and 2 <= y <= 4))
                fixed[r][c] = True

    finder(0, 0)
    finder(0, size - 7)
    finder(size - 7, 0)

    for i in range(8, size - 8):                  # lignes de synchronisation
        grid[6][i] = grid[i][6] = (i % 2 == 0)
        fixed[6][i] = fixed[i][6] = True

    centres = _QR_ALIGN[version]
    for cy in centres:
        for cx in centres:
            if (cy, cx) in ((6, 6), (6, size - 7), (size - 7, 6)):
                continue
            for y in range(-2, 3):
                for x in range(-2, 3):
                    grid[cy + y][cx + x] = max(abs(x), abs(y)) != 1
                    fixed[cy + y][cx + x] = True

    for i in range(9):                            # zones d'information
        fixed[8][i] = True
        fixed[i][8] = True
    for i in range(8):
        fixed[8][size - 1 - i] = True
        fixed[size - 1 - i][8] = True
    grid[size - 8][8] = True                      # module toujours sombre
    fixed[size - 8][8] = True

    if version >= 7:
        for i in range(6):
            for j in range(3):
                fixed[size - 11 + j][i] = True
                fixed[i][size - 11 + j] = True
    return grid, fixed


_QR_MASKS = (
    lambda r, c: (r + c) % 2 == 0,
    lambda r, c: r % 2 == 0,
    lambda r, c: c % 3 == 0,
    lambda r, c: (r + c) % 3 == 0,
    lambda r, c: (r // 2 + c // 3) % 2 == 0,
    lambda r, c: (r * c) % 2 + (r * c) % 3 == 0,
    lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0,
    lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0,
)


def _qr_format_bits(level: str, mask: int) -> list[int]:
    value = (_QR_LEVEL_BITS[level] << 3) | mask
    rest = value << 10
    for i in range(4, -1, -1):
        if rest & (1 << (i + 10)):
            rest ^= 0b10100110111 << i
    bits = ((value << 10) | rest) ^ 0b101010000010010
    return [(bits >> (14 - i)) & 1 for i in range(15)]


def _qr_version_bits(version: int) -> list[int]:
    rest = version << 12
    for i in range(5, -1, -1):
        if rest & (1 << (i + 12)):
            rest ^= 0b1111100100101 << i
    bits = (version << 12) | rest
    return [(bits >> (17 - i)) & 1 for i in range(18)]


def _qr_penalty(grid: Matrix) -> int:
    """Score de pénalité de la norme : plus il est bas, mieux c'est."""
    size = len(grid)
    score = 0
    columns = [list(col) for col in zip(*grid)]

    for lines in (grid, columns):
        for row in lines:
            run, previous = 1, row[0]
            for value in row[1:]:
                if value == previous:
                    run += 1
                else:
                    if run >= 5:
                        score += 3 + (run - 5)
                    run, previous = 1, value
            if run >= 5:
                score += 3 + (run - 5)

    for r in range(size - 1):                     # blocs 2x2
        for c in range(size - 1):
            if (grid[r][c] == grid[r][c + 1] == grid[r + 1][c]
                    == grid[r + 1][c + 1]):
                score += 3

    finder = [True, False, True, True, True, False, True]
    for lines in (grid, columns):
        for row in lines:
            for i in range(size - 6):
                if row[i:i + 7] != finder:
                    continue
                if i >= 4 and not any(row[i - 4:i]):
                    score += 40
                if i + 11 <= size and not any(row[i + 7:i + 11]):
                    score += 40

    dark = sum(1 for row in grid for v in row if v)
    percent = dark * 100 / (size * size)
    score += 10 * int(abs(percent - 50) / 5)
    return score


def _qr_write_format(grid: Matrix, level: str, mask: int,
                     version: int) -> None:
    size = len(grid)
    bits = _qr_format_bits(level, mask)
    for i in range(6):
        grid[8][i] = bool(bits[i])
        grid[size - 1 - i][8] = bool(bits[i])
    grid[8][7] = bool(bits[6])
    grid[8][8] = bool(bits[7])
    grid[7][8] = bool(bits[8])
    for i in range(9, 15):
        grid[14 - i][8] = bool(bits[i])
        grid[8][size - 15 + i] = bool(bits[i])
    grid[size - 8][8] = True

    if version >= 7:
        vbits = _qr_version_bits(version)
        for i in range(18):
            r, c = i // 3, i % 3
            grid[size - 11 + c][r] = bool(vbits[17 - i])
            grid[r][size - 11 + c] = bool(vbits[17 - i])


def qrcode(text: str, level: str = 'M', min_version: int = 1) -> Matrix:
    """Matrice d'un QR Code, mode octet, versions 1 à 10.

    `level` est le niveau de correction : `L`, `M`, `Q` ou `H`.
    """
    level = level.upper()
    if level not in _QR_LEVEL_BITS:
        raise CodeError(f'niveau de correction inconnu : {level!r}')
    data = text.encode('utf-8')

    version = next((v for v in range(max(1, min_version), 11)
                    if _qr_capacity(v, level) >= len(data)), None)
    if version is None:
        raise CodeError(
            f'{len(data)} octets : au-delà de la capacité de la version 10 '
            f'au niveau {level} ({_qr_capacity(10, level)} octets)')

    stream = _qr_bitstream(data, version, level)
    grid, fixed = _qr_skeleton(version)
    size = len(grid)

    # remplissage en colonnes doubles, de droite à gauche
    index = 0
    col = size - 1
    upward = True
    while col > 0:
        if col == 6:                              # la colonne de synchro
            col -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for row in rows:
            for c in (col, col - 1):
                if fixed[row][c]:
                    continue
                grid[row][c] = bool(stream[index]) if index < len(stream) \
                    else False
                index += 1
        upward = not upward
        col -= 2

    best, best_score = None, None
    for mask in range(8):
        candidate = [row[:] for row in grid]
        rule = _QR_MASKS[mask]
        for r in range(size):
            for c in range(size):
                if not fixed[r][c] and rule(r, c):
                    candidate[r][c] = not candidate[r][c]
        _qr_write_format(candidate, level, mask, version)
        score = _qr_penalty(candidate)
        if best_score is None or score < best_score:
            best, best_score = candidate, score
    return best


# --------------------------------------------------------------------------
# Codes-barres linéaires
# --------------------------------------------------------------------------
#
# Rendus comme les codes 2D : une matrice de booléens, mais d'**une seule
# ligne**. La hauteur des barres est une affaire de gravure, pas
# d'encodage — c'est `engrave.toolpath` qui l'applique.

#: Code 39 : neuf éléments par caractère (cinq barres, quatre espaces),
#: dont exactement trois larges. 1 = élément large.
_C39 = {
    '0': '000110100', '1': '100100001', '2': '001100001', '3': '101100000',
    '4': '000110001', '5': '100110000', '6': '001110000', '7': '000100101',
    '8': '100100100', '9': '001100100', 'A': '100001001', 'B': '001001001',
    'C': '101001000', 'D': '000011001', 'E': '100011000', 'F': '001011000',
    'G': '000001101', 'H': '100001100', 'I': '001001100', 'J': '000011100',
    'K': '100000011', 'L': '001000011', 'M': '101000010', 'N': '000010011',
    'O': '100010010', 'P': '001010010', 'Q': '000000111', 'R': '100000110',
    'S': '001000110', 'T': '000010110', 'U': '110000001', 'V': '011000001',
    'W': '111000000', 'X': '010010001', 'Y': '110010000', 'Z': '011010000',
    '-': '010000101', '.': '110000100', ' ': '011000100', '$': '010101000',
    '/': '010100010', '+': '010001010', '%': '000101010', '*': '010010100',
}

#: Motifs de gauche d'un EAN, parité impaire. 1 = module sombre.
_EAN_L = ('0001101', '0011001', '0010011', '0111101', '0100011',
          '0110001', '0101111', '0111011', '0110111', '0001011')

#: Parité des six chiffres de gauche, choisie par le premier chiffre.
_EAN_PARITY = ('LLLLLL', 'LLGLGG', 'LLGGLG', 'LLGGGL', 'LGLLGG',
               'LGGLLG', 'LGGGLL', 'LGLGLG', 'LGLGGL', 'LGGLGL')


def _ean_right(digit: int) -> str:
    """Motif de droite : le complément du motif de gauche."""
    return ''.join('1' if c == '0' else '0' for c in _EAN_L[digit])


def _ean_g(digit: int) -> str:
    """Motif de gauche à parité paire : le motif de droite, à l'envers."""
    return _ean_right(digit)[::-1]


def code39(text: str, checksum: bool = False) -> Matrix:
    """Code 39, avec ses délimiteurs `*`.

    Symbologie **auto-vérifiante** : chaque caractère porte sa propre
    contrainte de trois éléments larges sur neuf, ce qui suffit à écarter
    la plupart des lectures fautives. La clé modulo 43 reste proposée pour
    les donneurs d'ordre qui l'exigent.
    """
    text = text.upper()
    unknown = sorted({c for c in text if c not in _C39 or c == '*'})
    if unknown:
        raise CodeError('caractère(s) hors Code 39 : ' + ', '.join(unknown))

    body = text
    if checksum:
        alphabet = ''.join(k for k in _C39 if k != '*')
        total = sum(alphabet.index(c) for c in text) % 43
        body += alphabet[total]

    bits: list[bool] = []
    for i, char in enumerate('*' + body + '*'):
        if i:
            bits.append(False)                    # séparateur inter-caractère
        for j, wide in enumerate(_C39[char]):
            width = 3 if wide == '1' else 1
            bits.extend([j % 2 == 0] * width)     # éléments pairs = barres
    return [bits]


def ean13(digits: str) -> Matrix:
    """EAN-13. Accepte 12 chiffres — la clé est calculée — ou 13."""
    digits = ''.join(c for c in digits if not c.isspace())
    if not digits.isdigit() or len(digits) not in (12, 13):
        raise CodeError('EAN-13 : 12 ou 13 chiffres attendus, '
                        f'reçu {len(digits)} caractère(s)')
    values = [int(c) for c in digits[:12]]
    key = (10 - sum(v * (3 if i % 2 else 1)
                    for i, v in enumerate(values)) % 10) % 10
    if len(digits) == 13 and int(digits[12]) != key:
        raise CodeError(f'clé de contrôle incorrecte : {digits[12]} '
                        f'au lieu de {key}')
    values.append(key)

    bits = [True, False, True]                    # garde de départ
    for parity, digit in zip(_EAN_PARITY[values[0]], values[1:7]):
        pattern = _EAN_L[digit] if parity == 'L' else _ean_g(digit)
        bits.extend(c == '1' for c in pattern)
    bits.extend([False, True, False, True, False])  # garde centrale
    for digit in values[7:]:
        bits.extend(c == '1' for c in _ean_right(digit))
    bits.extend([True, False, True])              # garde de fin
    return [bits]


def ean13_key(digits: str) -> int:
    """Clé de contrôle des douze premiers chiffres."""
    values = [int(c) for c in digits[:12]]
    return (10 - sum(v * (3 if i % 2 else 1)
                     for i, v in enumerate(values)) % 10) % 10


#: Symbologies proposées dans l'interface.
# --------------------------------------------------------------------------
# Code 128 (ISO/IEC 15417) : sous-ensembles B (ASCII 32-127) et C (paires
# de chiffres), passage automatique en C pour les suites de chiffres.
# --------------------------------------------------------------------------

#: Largeurs barre/espace des 107 symboles (valeur 0 à 106 ; 106 = arrêt).
_C128 = (
    '212222', '222122', '222221', '121223', '121322', '131222', '122213', '122312', '132212', '221213',
    '221312', '231212', '112232', '122132', '122231', '113222', '123122', '123221', '223211', '221132',
    '221231', '213212', '223112', '312131', '311222', '321122', '321221', '312212', '322112', '322211',
    '212123', '212321', '232121', '111323', '131123', '131321', '112313', '132113', '132311', '211313',
    '231113', '231311', '112133', '112331', '132131', '113123', '113321', '133121', '313121', '211331',
    '231131', '213113', '213311', '213131', '311123', '311321', '331121', '312113', '312311', '332111',
    '314111', '221411', '431111', '111224', '111422', '121124', '121421', '141122', '141221', '112214',
    '112412', '122114', '122411', '142112', '142211', '241211', '221114', '413111', '241112', '134111',
    '111242', '121142', '121241', '114212', '124112', '124211', '411212', '421112', '421211', '212141',
    '214121', '412121', '111143', '111341', '131141', '114113', '114311', '411113', '411311', '113141',
    '114131', '311141', '411131', '211412', '211214', '211232', '2331112',
)
_C128_START_B, _C128_START_C, _C128_TO_B, _C128_TO_C, _C128_STOP = 104, 105, 100, 99, 106


def _digits_run(text: str, i: int) -> int:
    n = 0
    while i + n < len(text) and text[i + n].isdigit():
        n += 1
    return n


def code128_values(text: str) -> list[int]:
    """Valeurs des symboles (départ, données, contrôle, arrêt)."""
    if not text:
        raise CodeError('Code 128 : texte vide')
    bad = [c for c in text if not 32 <= ord(c) <= 126]
    if bad:
        raise CodeError(f'Code 128 : caractère non pris en charge {bad[0]!r} (ASCII 32 à 126)')
    out: list[int] = []
    i = 0
    run = _digits_run(text, 0)
    mode = 'C' if run >= 4 or (run == len(text) >= 2 and run % 2 == 0) else 'B'
    out.append(_C128_START_C if mode == 'C' else _C128_START_B)
    while i < len(text):
        run = _digits_run(text, i)
        if mode == 'C':
            if run >= 2:
                out.append(int(text[i:i + 2]))
                i += 2
                continue
            mode = 'B'
            out.append(_C128_TO_B)
            continue
        # sous-ensemble B : passage en C si la suite de chiffres le vaut
        at_end = i + run == len(text)
        if run >= 6 or (at_end and run >= 4):
            if run % 2:
                out.append(ord(text[i]) - 32)       # un chiffre en B, le reste en paires
                i += 1
            out.append(_C128_TO_C)
            mode = 'C'
            continue
        out.append(ord(text[i]) - 32)
        i += 1
    check = (out[0] + sum(k * v for k, v in enumerate(out[1:], 1))) % 103
    return out + [check, _C128_STOP]


def code128(text: str) -> Matrix:
    row: list[bool] = []
    for v in code128_values(text):
        for k, w in enumerate(_C128[v]):
            row.extend([k % 2 == 0] * int(w))
    return [row]


KINDS = (
    ('datamatrix', 'DataMatrix (ECC200)'),
    ('qr', 'QR Code'),
    ('code128', 'Code 128'),
    ('code39', 'Code 39'),
    ('ean13', 'EAN-13'),
)

#: Symbologies à une dimension : une seule ligne de modules, dont la
#: hauteur des barres est un réglage de gravure.
LINEAR = ('code39', 'ean13', 'code128')


def is_linear(kind: str) -> bool:
    return kind in LINEAR


def encode(kind: str, text: str, *, level: str = 'M',
           shape: str = 'square', checksum: bool = False,
           quiet_modules: int = 0) -> Matrix:
    """Matrice d'un code, zone de silence éventuelle comprise.

    La zone de silence n'est pas gravée — c'est du vide — mais elle compte
    dans l'encombrement : c'est elle qui garantit la lecture sur une pièce
    dont le fond n'est pas neutre.
    """
    if kind == 'datamatrix':
        matrix = datamatrix(text, shape)
    elif kind == 'qr':
        matrix = qrcode(text, level)
    elif kind == 'code39':
        matrix = code39(text, checksum)
    elif kind == 'ean13':
        matrix = ean13(text)
    elif kind == 'code128':
        matrix = code128(text)
    else:
        raise CodeError(f'symbologie inconnue : {kind!r}')
    if quiet_modules <= 0:
        return matrix
    if is_linear(kind):
        # sur un code linéaire la zone de silence n'a de sens qu'à gauche
        # et à droite : au-dessus et au-dessous, ce sont les barres
        # elles-mêmes qui débordent
        return [[False] * quiet_modules + row + [False] * quiet_modules
                for row in matrix]
    width = len(matrix[0]) + 2 * quiet_modules
    blank = [[False] * width for _ in range(quiet_modules)]
    body = [[False] * quiet_modules + row + [False] * quiet_modules
            for row in matrix]
    return blank + body + [[False] * width for _ in range(quiet_modules)]


def runs(matrix: Matrix) -> list[tuple[int, int, int]]:
    """Modules sombres fusionnés par ligne : (ligne, début, longueur).

    Fusionner les modules voisins d'une même ligne divise par cinq à dix le
    nombre de contours à graver, sans rien changer au dessin.
    """
    out = []
    for y, row in enumerate(matrix):
        x = 0
        while x < len(row):
            if not row[x]:
                x += 1
                continue
            start = x
            while x < len(row) and row[x]:
                x += 1
            out.append((y, start, x - start))
    return out
