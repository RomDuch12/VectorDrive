"""Polices SVG : un fichier SVG avec un élément `<font>`. Le format des polices
monotrait libres (Hershey, EMS…) : des traits ouverts, gravés en un passage.

Hauteur d'em 1, y vers le haut. La hauteur de capitales est mesurée sur le H
s'il existe.
"""
from __future__ import annotations

import functools
import html
import math
import pathlib
import re
import xml.etree.ElementTree as ET

from .geom import Affine, Path

#: on ne lit que le début d'un SVG pour savoir si c'est une police
HEAD_BYTES = 256 * 1024
_FONT_TAG = re.compile(rb'<(?:[\w.-]+:)?font[\s>]')
_FAMILY = re.compile(rb'''font-family\s*=\s*(?:"([^"]+)"|'([^']+)')''')


def _tag(el) -> str:
    return el.tag.rsplit('}', 1)[-1] if isinstance(el.tag, str) else ''


def _number(value, default: float = 0.0) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return v if math.isfinite(v) else default


def font_name(path) -> str | None:
    """Le nom de la police, lu dans le début du fichier ; None si ce SVG n'est pas une police."""
    try:
        with open(path, 'rb') as fh:
            head = fh.read(HEAD_BYTES)
    except OSError:
        return None
    if not _FONT_TAG.search(head):
        return None
    m = _FAMILY.search(head)
    name = html.unescape((m.group(1) or m.group(2)).decode('utf-8', 'replace')).strip() if m else ''
    return name or pathlib.Path(path).stem.strip() or None


def _codes(text: str | None) -> list[int]:
    """Les caractères d'une liste de `hkern` : a,b ou U+0041, U+0041-005A (les ligatures ne comptent pas)."""
    out = []
    for part in (text or '').split(','):
        p = part.strip()
        if p[:2].upper() == 'U+':
            a, _, b = p[2:].partition('-')
            try:
                lo = int(a.replace('?', '0'), 16)
                hi = int(b, 16) if b else int(a.replace('?', 'F'), 16)
            except ValueError:
                continue
            out += list(range(lo, min(hi, lo + 0x10000) + 1))
        elif len(p) == 1:
            out.append(ord(p))
    return out


class SvgFont:
    """Une police SVG : `index`, `glyph(code)`, `kerning(a, b)`."""

    def __init__(self, path: str):
        from ..io.svg import parse_path
        self._parse = parse_path
        root = ET.parse(path).getroot()
        font = next((el for el in root.iter() if _tag(el) == 'font'), None)
        if font is None:
            raise ValueError('pas de police dans ce SVG')
        face = next((el for el in font if _tag(el) == 'font-face'), None)
        get = face.get if face is not None else (lambda _k, _d=None: None)
        self.upem = _number(get('units-per-em'), 1000.0) or 1000.0
        self.name = (get('font-family') or font.get('id') or pathlib.Path(path).stem or '').strip()
        scale = 1.0 / self.upem
        self.ascent = _number(get('ascent'), 0.8 * self.upem) * scale
        self.descent = abs(_number(get('descent'), -0.2 * self.upem)) * scale
        declared = _number(get('cap-height')) * scale
        self.default_adv = _number(font.get('horiz-adv-x'), self.upem / 2) * scale
        self.index: dict[int, tuple] = {}
        self._matrix = Affine.scaling(scale)
        self._missing = None
        names: dict[str, int] = {}
        for el in font:
            kind = _tag(el)
            if kind == 'missing-glyph':
                self._missing = (el.get('d') or '', _number(el.get('horiz-adv-x'), self.default_adv / scale) * scale)
            elif kind == 'glyph':
                code = el.get('unicode') or ''
                if len(code) != 1:                       # ligatures et glyphes sans caractère : pas accessibles au texte
                    continue
                self.index[ord(code)] = (el.get('d') or '', _number(el.get('horiz-adv-x'), self.default_adv / scale) * scale)
                if el.get('glyph-name'):
                    names[el.get('glyph-name')] = ord(code)
        if not self.index:
            raise ValueError('police sans caractère')
        self._kern: dict[tuple[int, int], float] = {}
        for el in font:
            if _tag(el) != 'hkern':
                continue
            left = _codes(el.get('u1')) + [names[n.strip()] for n in (el.get('g1') or '').split(',') if n.strip() in names]
            right = _codes(el.get('u2')) + [names[n.strip()] for n in (el.get('g2') or '').split(',') if n.strip() in names]
            k = -_number(el.get('k')) * scale                  # SVG : on retire k à l'avance
            for a in left:
                for b in right:
                    self._kern[(a, b)] = k
        self.cap = 0.0
        if ord('H') in self.index:
            box = self.glyph(ord('H'))[0].bbox()
            if box:
                self.cap = box[3]
        if self.cap <= 0.0:
            self.cap = declared if declared > 0 else (self.ascent * 0.7 or 0.7)

    def glyph(self, code: int):
        """(tracé, avance) en hauteur d'em 1 ; None si le caractère manque et que la police n'a pas de glyphe de secours."""
        got = self.index.get(code, self._missing)
        if got is None:
            return None
        d, adv = got
        return (self._parse(d, self._matrix) if d.strip() else Path()), adv

    def kerning(self, left: int, right: int) -> float:
        return self._kern.get((left, right), 0.0)


@functools.lru_cache(maxsize=32)
def load(path: str) -> SvgFont:
    return SvgFont(str(path))


@functools.lru_cache(maxsize=8192)
def glyph(path: str, char: str) -> tuple:
    """(tracé, avance) d'un caractère, hauteur d'em 1 ; police abîmée, caractère absent ou valeurs folles : vide, le
    texte reste ; un blanc n'a que son avance."""
    try:
        g = load(path).glyph(ord(char))
    except Exception:
        return Path(), 0.0
    if g is None:
        return Path(), (0.3 if char == ' ' else 0.0)
    path_, adv = g
    if not math.isfinite(adv) or abs(adv) > 1e3:
        adv = 0.0
    if char.isspace():
        return Path(), adv
    for c in path_.contours:
        for seg in c.segments:
            if not all(math.isfinite(v) and abs(v) < 1e3 for pt in (seg.start, seg.end) for v in pt):
                return Path(), adv
    return path_, adv


def metrics(path: str) -> dict:
    """Ses propres mesures ; police abîmée : hauteur 1, boîte 1,25 / 0,75."""
    try:
        f = load(path)
        return {'upem': 1.0, 'ascent': f.ascent, 'descent': f.descent, 'cap': f.cap}
    except Exception:
        return {'upem': 1.0, 'ascent': 1.25, 'descent': 0.75, 'cap': 1.0}


def kerning(path: str, left: str, right: str) -> float:
    try:
        v = load(path).kerning(ord(left), ord(right))
    except Exception:
        return 0.0
    return v if math.isfinite(v) and abs(v) < 10 else 0.0
