"""Motifs de hachure de DAO : chaque motif est une suite de familles de
traits parallèles — angle, origine, décalage (le long du trait d'un trait au
suivant, et entre deux traits), tirets (positif), espaces (négatif), points
(0). ANSI31 à ANSI38, NET, BRICK, HONEY, EARTH, GRASS, AR-CONC… et les
fichiers .pat de l'utilisateur.

Bibliothèque standard, balayage des familles et lecture des .pat : portage
de CADCraft (storytold/cadcraft, © 2026 ArtCraft Team and the CADCraft
contributors, MIT OR Apache-2.0, utilisé sous MIT) — `crates/doc/src/library.rs`
(`standard_patterns`), `crates/render/src/hatch.rs` (`Family::sweep`,
`Family::dash`, `crossings`), `crates/doc/src/library/files.rs` (`parse_pat`).
Modifications : longueurs en mm, intersections en numpy, traits alternés
(moins de trajets à vide), points rendus à part."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

INCH = 25.4
#: bornes : traits par famille, morceaux en tout (un motif minuscule sur une grande surface)
MAX_FAMILY_LINES = 20_000
MAX_RUNS = 1_000_000
#: bornes de lecture d'un fichier .pat (texte de l'utilisateur, jamais sûr)
MAX_LINE_CHARS = 4096
MAX_DEFINITIONS = 4096
MAX_FAMILIES = 1024
MAX_DASHES = 256
MAX_VALUE = 1.0e6


@dataclass
class PatternLine:
    angle: float
    origin: tuple = (0.0, 0.0)
    #: (décalage le long du trait d'un trait au suivant, écart entre deux traits)
    delta: tuple = (0.0, 1.0)
    dashes: list = field(default_factory=list)

    def to_list(self) -> list:
        return [self.angle, self.origin[0], self.origin[1], self.delta[0], self.delta[1], *self.dashes]

    @classmethod
    def from_list(cls, v) -> 'PatternLine':
        v = [float(x) for x in v]
        if len(v) < 5 or not all(math.isfinite(x) and abs(x) <= MAX_VALUE for x in v) or abs(v[4]) < 1e-9:
            raise ValueError(v)
        return cls(v[0], (v[1], v[2]), (v[3], v[4]), v[5:5 + MAX_DASHES])

    def scaled(self, k: float) -> 'PatternLine':
        return PatternLine(self.angle, (self.origin[0] * k, self.origin[1] * k), (self.delta[0] * k, self.delta[1] * k),
                           [d * k for d in self.dashes])


@dataclass
class HatchPattern:
    name: str
    description: str = ''
    lines: list = field(default_factory=list)


def _pl(angle, origin, delta, dashes=()):
    return PatternLine(angle, origin, delta, list(dashes))


_R2 = 1 / math.sqrt(2)
# CADCraft, crates/doc/src/library.rs : noms d'usage courant, valeurs en pouces (libellés traduits)
_STANDARD = (
    ('ANSI31', 'Fonte, brique, maçonnerie', [_pl(45, (0, 0), (0, 0.125))]),
    ('ANSI32', 'Acier', [_pl(45, (0, 0), (0, 0.375)), _pl(45, (0.176777, 0), (0, 0.375))]),
    ('ANSI33', 'Bronze, laiton, cuivre', [_pl(45, (0, 0), (0, 0.25)), _pl(45, (0.176777, 0), (0, 0.25), (0.125, -0.0625))]),
    ('ANSI34', 'Plastique, caoutchouc', [_pl(45, (0.176777 * i / 2, 0), (0, 0.75)) for i in range(4)]),
    ('ANSI35', 'Brique réfractaire', [_pl(45, (0, 0), (0, 0.25)),
                                      _pl(45, (0.176777, 0), (0, 0.25), (0.3125, -0.0625, 0, -0.0625))]),
    ('ANSI36', 'Marbre, ardoise, verre', [_pl(45, (0, 0), (0.21875, 0.125), (0.3125, -0.0625, 0, -0.0625))]),
    ('ANSI37', 'Plomb, zinc, magnésium', [_pl(45, (0, 0), (0, 0.125)), _pl(135, (0, 0), (0, 0.125))]),
    ('ANSI38', 'Aluminium', [_pl(45, (0, 0), (0, 0.125)), _pl(135, (0, 0), (0.25, 0.125), (0.3125, -0.1875))]),
    ('LINE', 'Traits horizontaux parallèles', [_pl(0, (0, 0), (0, 0.125))]),
    ('NET', 'Quadrillage horizontal et vertical', [_pl(0, (0, 0), (0, 0.125)), _pl(90, (0, 0), (0, 0.125))]),
    ('NET3', 'Réseau à 0°, 60° et 120°', [_pl(0, (0, 0), (0, 0.125)), _pl(60, (0, 0), (0, 0.125)),
                                          _pl(120, (0, 0), (0, 0.125))]),
    ('DOTS', 'Points', [_pl(0, (0, 0), (0.03125, 0.0625), (0, -0.0625))]),
    ('DASH', 'Traits interrompus', [_pl(0, (0, 0), (0.125, 0.125), (0.125, -0.125))]),
    ('BRICK', 'Briques', [_pl(0, (0, 0), (0, 0.25)), _pl(90, (0, 0), (0, 0.5), (0.25, -0.25)),
                          _pl(90, (0.25, 0), (0, 0.5), (-0.25, 0.25))]),
    ('SQUARE', 'Petits carrés alignés', [_pl(0, (0, 0), (0, 0.125), (0.125, -0.125)),
                                         _pl(90, (0, 0), (0, 0.125), (0.125, -0.125))]),
    ('CROSS', 'Croix', [_pl(0, (0, 0), (0.25, 0.25), (0.125, -0.375)),
                        _pl(90, (0.0625, -0.0625), (0.25, 0.25), (0.125, -0.375))]),
    ('EARTH', 'Terre', [_pl(0, (0, 0), (0.25, 0.25), (0.25, -0.25)), _pl(0, (0, 0.09375), (0.25, 0.25), (0.25, -0.25)),
                        _pl(0, (0, 0.1875), (0.25, 0.25), (0.25, -0.25)),
                        _pl(90, (0.03125, 0.21875), (0.25, 0.25), (0.25, -0.25)),
                        _pl(90, (0.125, 0.21875), (0.25, 0.25), (0.25, -0.25)),
                        _pl(90, (0.21875, 0.21875), (0.25, 0.25), (0.25, -0.25))]),
    ('GRASS', 'Herbe', [_pl(90, (0, 0), (_R2, _R2), (0.1875, -1.226)), _pl(45, (0, 0), (0, 1), (0.1875, -0.8125)),
                        _pl(135, (0, 0), (0, 1), (0.1875, -0.8125))]),
    ('HONEY', "Nid d'abeille", [_pl(0, (0, 0), (0.1875, 0.108253), (0.125, -0.25)),
                                _pl(120, (0, 0), (0.1875, 0.108253), (0.125, -0.25)),
                                _pl(60, (0.125, 0), (0.1875, 0.108253), (0.125, -0.25))]),
    ('ZIGZAG', 'Escalier', [_pl(0, (0, 0), (0.125, 0.125), (0.125, -0.125)),
                            _pl(90, (0.125, 0), (0.125, 0.125), (0.125, -0.125))]),
    # dessinés à l'échelle des motifs du même nom des logiciels de DAO (× 16, comme CADCraft)
    ('AR-CONC', 'Béton : points et cailloux', [p.scaled(16) for p in (
        _pl(50, (0, 0), (0.4, 0.25), (0.15, -0.6)), _pl(355, (0, 0), (0.27, 0.3), (0.12, -0.5)),
        _pl(100, (0.12, 0.05), (0.35, 0.33), (0.1, -0.55)), _pl(0, (0.07, 0.02), (0.21, 0.17), (0, -0.4)))]),
    ('AR-SAND', 'Sable : points', [p.scaled(16) for p in (
        _pl(37.5, (0, 0), (0.112, 0.0912), (0, -0.22, 0, -0.14)), _pl(7.5, (0, 0), (0.157, 0.0724), (0, -0.19, 0, -0.31)),
        _pl(-32.5, (0, 0), (0.091, 0.1312), (0, -0.27, 0, -0.11)))]),
)


def standard() -> dict[str, HatchPattern]:
    """Motifs standard, en mm (valeurs en pouces × 25,4, comme les définitions
    ISO des dessins métriques : ANSI31 = traits à 45° espacés de 3,175 mm)."""
    return {n: HatchPattern(n, d, [p.scaled(INCH) for p in lines]) for n, d, lines in _STANDARD}


# --- balayage ----------------------------------------------------------------------------------
def _rot(x, y, a):
    c, s = math.cos(a), math.sin(a)
    return x * c - y * s, x * s + y * c


def segments(polys, lines, scale: float = 1.0, angle: float = 0.0, origin=(0.0, 0.0)):
    """(traits [(a, b)], points [p]) des familles `lines` dans les contours
    fermés `polys` (tableaux numpy de points, règle pair-impair) ; `scale`,
    `angle` (degrés) et `origin` placent le motif."""
    scale = scale if math.isfinite(scale) and scale > 0 else 1.0
    segs, dots = [], []
    polys = [np.asarray(P, float) for P in polys if len(P) >= 3]
    if not polys:
        return segs, dots
    rot = math.radians(angle)
    for fam in lines:
        if fam.dashes and not any(d >= 0 for d in fam.dashes):
            continue                                   # que des espaces : rien à tracer
        ang = math.radians(fam.angle) + rot
        ox, oy = _rot(fam.origin[0] * scale, fam.origin[1] * scale, rot)
        ox, oy = origin[0] + ox, origin[1] + oy
        spacing = abs(fam.delta[1] * scale)
        if not math.isfinite(spacing) or spacing < 1e-9:
            continue
        shift = fam.delta[0] * scale
        dashes = [d * scale for d in fam.dashes]
        pat_len = sum(abs(d) for d in dashes)
        ca, sa = math.cos(ang), math.sin(ang)
        edges = []
        for P in polys:
            x = (P[:, 0] - ox) * ca + (P[:, 1] - oy) * sa
            y = -(P[:, 0] - ox) * sa + (P[:, 1] - oy) * ca
            q = np.stack([x, y], 1)
            edges.append(np.concatenate([q, np.roll(q, -1, axis=0)], 1))
        E = np.concatenate(edges)
        y0, y1 = E[:, 1], E[:, 3]
        k0 = math.floor(float(min(y0.min(), y1.min())) / spacing)
        k1 = math.ceil(float(max(y0.max(), y1.max())) / spacing)
        if k1 - k0 > MAX_FAMILY_LINES:
            continue

        def world(x, y):
            return (ox + x * ca - y * sa, oy + x * sa + y * ca)
        flip = False
        for k in range(k0, k1 + 1):
            if len(segs) + len(dots) >= MAX_RUNS:
                return segs, dots
            y = k * spacing
            m = (y0 > y) != (y1 > y)
            if not m.any():
                continue
            e = E[m]
            xs = np.sort(e[:, 0] + (e[:, 2] - e[:, 0]) * (y - e[:, 1]) / (e[:, 3] - e[:, 1]))
            spans = [(float(xs[i]), float(xs[i + 1])) for i in range(0, len(xs) - 1, 2) if xs[i + 1] - xs[i] > 1e-9]
            if not dashes or pat_len < 1e-12:
                line = [(world(a, y), world(b, y)) for a, b in spans]
                if flip:                                # traits alternés : moins de trajets à vide
                    line = [(b, a) for a, b in reversed(line)]
                flip = not flip
                segs.extend(line)
                continue
            offset = shift * k
            for x0, x1 in spans:
                x = offset + math.floor((x0 - offset) / pat_len) * pat_len
                guard = 0
                while x < x1 and guard < 100_000:
                    for d in dashes:
                        guard += 1
                        L = abs(d)
                        if d > 0:
                            a, b = max(x, x0), min(x + L, x1)
                            if b > a:
                                segs.append((world(a, y), world(b, y)))
                        elif d == 0 and x0 <= x <= x1:
                            dots.append(world(x, y))
                        x += L
                        if x >= x1:
                            break
    return segs, dots


# --- fichiers .pat -----------------------------------------------------------------------------
def parse_pat(text: str) -> tuple[list[HatchPattern], list[str]]:
    """Motifs d'un fichier .pat (`*NOM,description` puis une famille par
    ligne : `angle, x, y, dx, dy[, tirets…]` ; `;` commente la fin de la
    ligne) et les remarques. Longueurs telles qu'écrites (mm pour un fichier
    ISO ; pouces pour les autres : échelle 25,4)."""
    items: list[HatchPattern] = []
    warnings: list[str] = []

    def warn(no, msg):
        if len(warnings) < 100:
            warnings.append(f'{no} : {msg}')
    cur = None                                          # [motif, ligne, en échec]

    def finish():
        if cur is None or cur[2]:
            return
        p, at = cur[0], cur[1]
        if not p.lines:
            warn(at, f'{p.name} sans famille de traits')
        elif len(items) >= MAX_DEFINITIONS:
            warn(at, f'trop de motifs : {p.name} laissé')
        elif any(q.name.lower() == p.name.lower() for q in items):
            warn(at, f'{p.name} défini deux fois : le premier est gardé')
        else:
            items.append(p)
    for no, raw in enumerate(str(text or '').lstrip('﻿').splitlines(), 1):
        line = raw.split(';', 1)[0].strip()
        if not line:
            continue
        if len(line) > MAX_LINE_CHARS:
            warn(no, 'ligne trop longue')
            continue
        if line.startswith('*'):
            finish()
            name, _sep, desc = line[1:].partition(',')
            name = name.strip()
            if not name or any(ord(ch) < 32 for ch in name):
                warn(no, 'définition sans nom')
                cur = None
                continue
            cur = [HatchPattern(name[:255].upper(), ''.join(ch for ch in desc.strip() if ord(ch) >= 32)[:255]), no,
                   False]
            continue
        if cur is None:
            warn(no, 'famille de traits sans ligne *NOM avant elle')
            continue
        if cur[2]:
            continue
        if len(cur[0].lines) >= MAX_FAMILIES:
            warn(no, f'{cur[0].name} : trop de familles de traits')
            cur[2] = True
            continue
        try:
            vals = [f.strip() for f in line.split(',')]
            vals = vals[:5] + [v for v in vals[5:] if v]
            cur[0].lines.append(PatternLine.from_list(vals))
        except ValueError:
            warn(no, f'{cur[0].name} : famille illisible (angle, x, y, dx, dy, tirets ; dy non nul)')
            cur[2] = True
    finish()
    return items, warnings
