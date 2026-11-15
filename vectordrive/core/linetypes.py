"""Types de traits : un contour devient de vrais tirets — pointillés de
découpe, lignes de pliage ou de perforation au laser, au couteau, à la
fraise. Un motif est une suite de longueurs en mm : un tiret (positif), un
espace (négatif), un point (0).

Les tirets suivent les courbes elles-mêmes (droites, Bézier, arcs coupés à
leur paramètre exact) ; un point devient un petit cercle (ou rien). Sur un
contour fermé, le motif peut être ajusté pour tomber juste (un nombre entier
de motifs), et le tiret à cheval sur le départ reste d'un seul morceau.

Bibliothèque standard des types de traits, répartition des tirets et
lecture des fichiers .lin : portage de CADCraft (storytold/cadcraft,
© 2026 ArtCraft Team and the CADCraft contributors, MIT OR Apache-2.0,
utilisé sous MIT) — `crates/doc/src/library.rs` (`standard_linetypes`),
`crates/render/src/linetype.rs` (`ranges`), `crates/doc/src/library/files.rs`
(`parse_lin`). Modifications : longueurs en mm, éléments texte et formes des
.lin laissés de côté, découpe exacte des courbes, ajustement aux contours
fermés."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .geom import Contour, Line, Path, circle

#: longueur d'un pouce (les motifs standard sont définis en pouces, comme dans CADCraft)
INCH = 25.4
#: au plus autant de tirets par contour (un motif minuscule sur un grand contour : laissé continu)
MAX_DASHES = 200_000
#: bornes de lecture d'un fichier .lin (texte de l'utilisateur, jamais sûr)
MAX_LINE_CHARS = 4096
MAX_DEFINITIONS = 4096
MAX_ELEMENTS = 256
MAX_VALUE = 1.0e6


@dataclass
class Linetype:
    name: str
    description: str = ''
    #: longueurs en mm : tiret > 0, espace < 0, point = 0
    pattern: list[float] = field(default_factory=list)

    def length(self) -> float:
        return sum(abs(d) for d in self.pattern)


# CADCraft, crates/doc/src/library.rs : noms d'usage courant, valeurs en pouces
_STANDARD = (
    ('BORDER', 'Border __ __ . __ __ . __ __ .', (0.5, -0.25, 0.5, -0.25, 0.0, -0.25)),
    ('CENTER', 'Center ____ _ ____ _ ____', (1.25, -0.25, 0.25, -0.25)),
    ('CENTER2', 'Center (.5x) ___ _ ___ _', (0.75, -0.125, 0.125, -0.125)),
    ('CENTERX2', 'Center (2x) ________  __  ________', (2.5, -0.5, 0.5, -0.5)),
    ('DASHDOT', 'Dash dot __ . __ . __ .', (0.5, -0.25, 0.0, -0.25)),
    ('DASHDOT2', 'Dash dot (.5x) _._._._.', (0.25, -0.125, 0.0, -0.125)),
    ('DASHED', 'Dashed __ __ __ __', (0.5, -0.25)),
    ('DASHED2', 'Dashed (.5x) _ _ _ _ _', (0.25, -0.125)),
    ('DASHEDX2', 'Dashed (2x) ____  ____  ____', (1.0, -0.5)),
    ('DIVIDE', 'Divide ____ . . ____ . .', (0.5, -0.25, 0.0, -0.25, 0.0, -0.25)),
    ('DOT', 'Dot . . . . . . . .', (0.0, -0.25)),
    ('DOT2', 'Dot (.5x) ........', (0.0, -0.125)),
    ('HIDDEN', 'Hidden __ __ __ __', (0.25, -0.125)),
    ('HIDDEN2', 'Hidden (.5x) _ _ _ _ _', (0.125, -0.0625)),
    ('HIDDENX2', 'Hidden (2x) ____ ____ ____', (0.5, -0.25)),
    ('PHANTOM', 'Phantom ______  __  __  ______', (1.25, -0.25, 0.25, -0.25, 0.25, -0.25)),
    ('PHANTOM2', 'Phantom (.5x) ___ _ _ ___', (0.625, -0.125, 0.125, -0.125, 0.125, -0.125)),
)


def standard() -> list[Linetype]:
    """Types de traits standard, en mm (valeurs en pouces × 25,4, comme les
    définitions ISO des dessins métriques : DASHED = 12,7 mm de tiret,
    6,35 mm d'espace)."""
    return [Linetype(n, d, [round(v * INCH, 6) for v in p]) for n, d, p in _STANDARD]


def parse_pattern(text: str) -> list[float]:
    """« 5, -2.5, 0, -2.5 » (virgules, points-virgules ou espaces ; virgule
    décimale admise avec « ; » ou des espaces) → motif ; ValueError si le
    motif ne trace rien."""
    import re
    t = str(text or '').strip()
    if ';' in t:                                                    # « 5 ; -2,5 »
        parts = [p.replace(',', '.') for p in t.replace(';', ' ').split()]
    elif re.search(r'\d,\d', t) and re.search(r'\s', t) and not re.search(r',[\s+-]', t):
        parts = [p.replace(',', '.') for p in t.split()]            # « 5 -2,5 » : virgule décimale
    else:                                                           # « 5, -2.5 », « 5,-2.5 »
        parts = t.replace(',', ' ').split()
    out = []
    for p in parts[:MAX_ELEMENTS]:
        v = float(p)
        if not math.isfinite(v) or abs(v) > MAX_VALUE:
            raise ValueError(p)
        out.append(v)
    if not out or not any(v >= 0 for v in out) or sum(abs(v) for v in out) <= 1e-9:
        raise ValueError(text)
    return out


def format_pattern(pattern) -> str:
    return ', '.join(f'{v:g}' for v in pattern)


# --- répartition des tirets ------------------------------------------------------------------
def ranges(length: float, pattern, scale: float = 1.0) -> list[tuple[float, float]] | None:
    """Tirets du motif le long d'un trait de longueur `length` : [(début,
    fin)] en abscisse curviligne, un point a début == fin. None : le trait
    reste continu (motif nul, ou qui se répéterait trop souvent)."""
    scale = scale if math.isfinite(scale) and scale > 0 else 1.0
    pat = [float(d) * scale for d in pattern]
    total = sum(abs(d) for d in pat)
    if not (math.isfinite(length) and length > 0) or total <= 1e-12 or length / total * len(pat) > MAX_DASHES:
        return None
    if not any(d >= 0 for d in pat):
        return []
    out = []
    pos, i = 0.0, 0
    while pos < length - 1e-12:
        d = pat[i % len(pat)]
        if d >= 0:
            out.append((pos, min(pos + d, length)))
        pos += abs(d)
        i += 1
    return out


def fitted_scale(length: float, pattern, scale: float = 1.0) -> float:
    """Échelle qui fait tomber le motif juste sur un contour fermé de
    longueur `length` : un nombre entier de motifs, au plus près de `scale`."""
    total = sum(abs(d) for d in pattern) * scale
    if total <= 1e-12 or length <= 0:
        return scale
    n = max(1, round(length / total))
    return length / (n * sum(abs(d) for d in pattern))


# --- découpe exacte ----------------------------------------------------------------------------
def _segments(c: Contour) -> list:
    segs = list(c.segments)
    if c.closed and segs and c.closing_gap() > 1e-9:            # fermeture implicite
        segs.append(Line(c.end, c.start))
    return segs


class _Walker:
    """Abscisse curviligne → (segment, paramètre) sur un contour."""

    SAMPLES = 48

    def __init__(self, segs):
        self.segs = segs
        self.lengths = [s.length() for s in segs]
        self.starts = []
        acc = 0.0
        for L in self.lengths:
            self.starts.append(acc)
            acc += L
        self.total = acc
        self._tables = {}

    def _table(self, i: int):
        tab = self._tables.get(i)
        if tab is None:
            seg = self.segs[i]
            n = self.SAMPLES
            pts = [seg.point(k / n) for k in range(n + 1)]
            cum = [0.0]
            for a, b in zip(pts, pts[1:]):
                cum.append(cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
            k = self.lengths[i] / cum[-1] if cum[-1] > 1e-15 else 1.0
            tab = self._tables[i] = [v * k for v in cum]
        return tab

    def t_at(self, i: int, s: float) -> float:
        """Paramètre du segment `i` à l'abscisse `s` mesurée depuis son début."""
        L = self.lengths[i]
        if L <= 1e-15:
            return 0.0
        s = min(max(s, 0.0), L)
        if isinstance(self.segs[i], Line):
            return s / L
        tab = self._table(i)
        lo, hi = 0, len(tab) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if tab[mid] <= s:
                lo = mid
            else:
                hi = mid
        span = tab[hi] - tab[lo]
        f = (s - tab[lo]) / span if span > 1e-15 else 0.0
        return (lo + f) / (len(tab) - 1)

    def point(self, s: float):
        i = self._index(s)
        return self.segs[i].point(self.t_at(i, s - self.starts[i]))

    def _index(self, s: float) -> int:
        i = 0
        while i + 1 < len(self.segs) and self.starts[i + 1] <= s:
            i += 1
        return i

    def piece(self, s0: float, s1: float) -> Contour | None:
        """Morceau ouvert du contour entre les abscisses s0 < s1."""
        from .trim import sub_segment
        out = []
        for i, seg in enumerate(self.segs):
            a, L = self.starts[i], self.lengths[i]
            lo, hi = max(s0, a), min(s1, a + L)
            if hi - lo <= 1e-9 or L <= 1e-15:
                continue
            t0, t1 = self.t_at(i, lo - a), self.t_at(i, hi - a)
            if t1 - t0 <= 1e-12:
                continue
            out.append(sub_segment(seg, t0, t1))
        return Contour(out, False) if out else None


def dash_contour(c: Contour, pattern, scale: float = 1.0, fit: bool = False) -> tuple[list[Contour], list]:
    """(tirets, points) d'un contour : morceaux ouverts exacts, et centres
    des points du motif. Motif impossible : le contour entier, sans point."""
    segs = _segments(c)
    if not segs:
        return [], []
    w = _Walker(segs)
    if w.total <= 1e-9:
        return [], []
    if fit and c.closed:
        scale = fitted_scale(w.total, pattern, scale)
    rs = ranges(w.total, pattern, scale)
    if rs is None:
        return [Contour(list(c.segments), c.closed)], []
    dashes = [(a, b) for a, b in rs if b - a > 1e-9]
    dots = [w.point(a) for a, b in rs if b - a <= 1e-9]
    # contour fermé : le tiret qui finit au bout et celui qui part du début ne font qu'un
    wrap = c.closed and len(dashes) > 1 and dashes[0][0] <= 1e-9 and dashes[-1][1] >= w.total - 1e-9
    pieces = []
    for k, (a, b) in enumerate(dashes):
        if wrap and k == 0:
            continue
        p = w.piece(a, b)
        if p is None:
            continue
        if wrap and k == len(dashes) - 1:
            first = w.piece(*dashes[0])
            if first is not None:
                p = Contour(p.segments + first.segments, False)
        pieces.append(p)
    if c.closed and len(dashes) == 1 and dashes[0][0] <= 1e-9 and dashes[0][1] >= w.total - 1e-9:
        pieces = [Contour(list(c.segments), True)]               # motif plus long que le contour : continu
    return pieces, dots


def dash_path(path: Path, pattern, scale: float = 1.0, fit: bool = False, dot: float = 0.0) -> Path:
    """Le tracé `path` en tirets ; un point devient un cercle de diamètre
    `dot` (rien si 0)."""
    out = []
    for c in path.contours:
        pieces, dots = dash_contour(c, pattern, scale, fit)
        out.extend(pieces)
        if dot > 0:
            out.extend(circle(p, dot / 2) for p in dots)
    return Path(out)


# --- fichiers .lin -----------------------------------------------------------------------------
def _fields(line: str) -> list[str]:
    """Champs séparés par des virgules hors de […] et de "…"."""
    out, depth, quoted, start = [], 0, False, 0
    for i, ch in enumerate(line):
        if ch == '"':
            quoted = not quoted
        elif ch == '[' and not quoted:
            depth += 1
        elif ch == ']' and not quoted:
            if depth == 0:
                raise ValueError('] sans [')
            depth -= 1
        elif ch == ',' and not quoted and depth == 0:
            out.append(line[start:i].strip())
            start = i + 1
    out.append(line[start:].strip())
    return out


def parse_lin(text: str) -> tuple[list[Linetype], list[str]]:
    """Types de traits d'un fichier .lin (`*NOM,description` puis
    `A,tiret,espace,…`, `;` pour un commentaire) et les remarques (ligne :
    raison). Les éléments texte ou forme ([…]) sont laissés de côté, les
    tirets autour gardés. Longueurs telles qu'écrites (mm pour un fichier
    ISO ; pouces pour les autres : échelle 25,4)."""
    items: list[Linetype] = []
    warnings: list[str] = []

    def warn(no, msg):
        if len(warnings) < 100:
            warnings.append(f'{no} : {msg}')
    pending = None
    for no, raw in enumerate(str(text or '').lstrip('﻿').splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(';'):
            continue
        if len(line) > MAX_LINE_CHARS:
            warn(no, 'ligne trop longue')
            continue
        if line.startswith('*'):
            if pending is not None:
                warn(pending[2], f'{pending[0]} sans motif')
            name, _sep, desc = line[1:].partition(',')
            name = name.strip()
            if not name or any(ord(ch) < 32 for ch in name):
                warn(no, 'définition sans nom')
                pending = None
                continue
            pending = (name[:255], ''.join(ch for ch in desc.strip() if ord(ch) >= 32)[:255], no)
            continue
        if pending is None:
            warn(no, 'motif sans ligne *NOM avant lui')
            continue
        name, desc, _at = pending
        pending = None
        if len(items) >= MAX_DEFINITIONS:
            warn(no, 'trop de types de traits')
            break
        if any(it.name.lower() == name.lower() for it in items):
            warn(no, f'{name} défini deux fois : le premier est gardé')
            continue
        try:
            fs = _fields(line)
        except ValueError as ex:
            warn(no, f'{name} : {ex}')
            continue
        if fs and fs[0].upper() == 'A':
            fs = fs[1:]
        pat, skipped = [], 0
        try:
            for f in fs:
                if not f:
                    continue
                if f.startswith('['):
                    skipped += 1                            # texte ou forme : sans longueur propre
                    continue
                v = float(f)
                if not math.isfinite(v) or abs(v) > MAX_VALUE:
                    raise ValueError(f)
                pat.append(v)
                if len(pat) > MAX_ELEMENTS:
                    raise ValueError('trop d\'éléments')
        except ValueError as ex:
            warn(no, f'{name} : « {ex} » n\'est pas une longueur')
            continue
        if not pat or not any(v >= 0 for v in pat) or sum(abs(v) for v in pat) <= 1e-12:
            warn(no, f'{name} : motif vide')
            continue
        if skipped:
            warn(no, f'{name} : {skipped} élément(s) texte ou forme laissé(s) de côté')
        items.append(Linetype(name, desc, pat))
    if pending is not None:
        warn(pending[2], f'{pending[0]} sans motif')
    return items, warnings
