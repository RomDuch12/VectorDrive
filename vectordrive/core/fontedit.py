"""Une police en cours de dessin : ses caractères, leurs chasses et son crénage.

Écrite au format SVG, que VectorDrive relit comme ses autres polices (`svgfonts`). Un caractère garde ses
traits ouverts : on peut dessiner une police monotrait. Tout est en unités de la police, y vers le haut ;
l'éditeur parle en mm, à l'échelle de la hauteur de capitale (100 mm conseillés, comme dans TypeEdit).
"""
from __future__ import annotations

import functools
import os
import pathlib
import re
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from . import fonts
from .geom import Affine, Path

UPEM = 1000.0
#: une capitale de hauteur `cap_mm` mesure ces unités
CAP = 700.0
#: chasse d'un espace dessiné sans tracé, en part de la hauteur de capitale
SPACE_SHARE = 0.3
#: une police reprise s'arrête là : une police asiatique entière ne servirait à rien ici
MAX_CHARS = 5000
SVG_NS = 'http://www.w3.org/2000/svg'
_BAD_FILE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}


def _num(v: float) -> str:
    s = f'{v:.4f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def valid_char(ch: str) -> bool:
    """Un seul caractère, qu'un fichier XML peut porter et qu'on peut taper dans un texte."""
    if len(ch) != 1:
        return False
    code = ord(ch)
    if 0xD800 <= code <= 0xDFFF or code in (0xFFFE, 0xFFFF):
        return False
    return ch.isprintable() or (ch.isspace() and code >= 0x20 and code != 0x85 and code not in (0x2028, 0x2029))


def _d(path: Path) -> str:
    """Le tracé SVG, y vers le haut (`path_d` retourne y : on le retourne d'abord)."""
    from ..io.svg import path_d
    return path_d(path.transformed(Affine(1, 0, 0, -1, 0, 0)), 0.0)


@functools.lru_cache(maxsize=4096)
def _parsed(d: str) -> Path:
    from ..io.svg import parse_path
    return parse_path(d, Affine()) if d.strip() else Path()


def placed(path: Path, on_line: bool, before: float = 0.0) -> Path:
    """Le dessin d'un caractère. `on_line` : son coin bas gauche sur la ligne de base, après l'espace `before` ;
    sinon tel quel par rapport à l'origine du dessin : ce qu'il faut à un g ou à une virgule, qui descendent."""
    box = path.bbox()
    if not on_line or box is None:
        return path
    return path.transformed(Affine.translation(before - box[0], -box[1]))


@dataclass
class Draft:
    name: str = ''
    upem: float = UPEM
    ascent: float = 800.0
    descent: float = 200.0
    cap: float = CAP
    default_adv: float = 500.0
    #: code → (tracé SVG, chasse) ; un tracé relu d'un fichier reste tel quel, sans perte
    glyphs: dict = field(default_factory=dict)
    #: (code, code) → ajouté à la chasse du premier, comme `SvgFont.kerning`
    kern: dict = field(default_factory=dict)
    missing: tuple | None = None

    def units(self, cap_mm: float) -> float:
        """Unités par mm pour cette hauteur de capitale."""
        return self.cap / cap_mm

    def put(self, code: int, path: Path, adv_mm: float, cap_mm: float) -> None:
        k = self.units(cap_mm)
        self.glyphs[code] = (_d(path.transformed(Affine.scaling(k))), adv_mm * k)

    def remove(self, code: int) -> None:
        self.glyphs.pop(code, None)
        self.kern = {p: v for p, v in self.kern.items() if code not in p}

    def set_adv(self, code: int, adv_mm: float, cap_mm: float) -> None:
        self.glyphs[code] = (self.glyphs[code][0], adv_mm * self.units(cap_mm))

    def adv_mm(self, code: int, cap_mm: float) -> float:
        return self.glyphs[code][1] / self.units(cap_mm)

    def set_kern(self, left: int, right: int, mm: float, cap_mm: float) -> None:
        """Négatif : rapproche la paire. Zéro : retire la paire."""
        if mm:
            self.kern[(left, right)] = mm * self.units(cap_mm)
        else:
            self.kern.pop((left, right), None)

    def kern_mm(self, left: int, right: int, cap_mm: float) -> float:
        return self.kern.get((left, right), 0.0) / self.units(cap_mm)

    def glyph_units(self, code: int) -> Path:
        return _parsed(self.glyphs[code][0])

    def glyph_mm(self, code: int, cap_mm: float) -> Path:
        return self.glyph_units(code).transformed(Affine.scaling(1.0 / self.units(cap_mm)))

    def text_units(self, text: str) -> Path:
        """Le texte d'essai, comme il sera posé : chasses et crénage ; un caractère absent ne prend pas de place."""
        x, prev, out = 0.0, None, []
        for ch in text:
            code = ord(ch)
            if prev is not None:
                x += self.kern.get((prev, code), 0.0)
            got = self.glyphs.get(code, self.missing)
            if got is not None:
                out += _parsed(got[0]).transformed(Affine.translation(x, 0)).contours
                x += got[1]
            prev = code
        return Path(out)

    def to_svg(self) -> str:
        root = ET.Element('svg', {'xmlns': SVG_NS, 'version': '1.1'})
        defs = ET.SubElement(root, 'defs')
        font = ET.SubElement(defs, 'font', {'id': 'police', 'horiz-adv-x': _num(self.default_adv)})
        ET.SubElement(font, 'font-face', {'font-family': self.name, 'units-per-em': _num(self.upem),
                                          'ascent': _num(self.ascent), 'descent': _num(-self.descent),
                                          'cap-height': _num(self.cap)})
        if self.missing is not None:
            ET.SubElement(font, 'missing-glyph', {'d': self.missing[0], 'horiz-adv-x': _num(self.missing[1])})
        for code in sorted(self.glyphs):
            d, adv = self.glyphs[code]
            attrs = {'unicode': chr(code), 'horiz-adv-x': _num(adv)}
            if d:
                attrs['d'] = d
            ET.SubElement(font, 'glyph', attrs)
        for (a, b) in sorted(self.kern):                 # en U+ : une virgule compterait comme séparateur
            ET.SubElement(font, 'hkern', {'u1': f'U+{a:04X}', 'u2': f'U+{b:04X}', 'k': _num(-self.kern[(a, b)])})
        ET.indent(root)
        return ET.tostring(root, encoding='unicode') + '\n'

    def save(self, path) -> None:
        """Tout ou rien : un fichier déjà là reste entier si l'écriture échoue."""
        path = pathlib.Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(suffix='.tmp', dir=path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as fh:
                fh.write(self.to_svg())
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise


def load(path) -> Draft:
    """Lève OSError, ValueError ou ET.ParseError si le fichier n'est pas une police lisible.
    Les ligatures et les glyphes sans caractère ne sont pas repris : le texte ne s'en sert pas."""
    from .svgfonts import SvgFont
    f = SvgFont(str(path))
    k = f.upem
    return Draft(name=f.name, upem=k, ascent=f.ascent * k, descent=f.descent * k, cap=f.cap * k,
                 default_adv=f.default_adv * k,
                 glyphs={code: (d, adv * k) for code, (d, adv) in f.index.items()},
                 kern={p: v * k for p, v in f._kern.items()},
                 missing=(f._missing[0], f._missing[1] * k) if f._missing else None)


def can_clone(name: str) -> bool:
    """Polices TrueType, OpenType et SVG, comme TypeEdit ; pas celles que lit un plugin, sauf si son format le permet."""
    from . import fontformats
    ff = fonts.find_font(name) if fonts.is_available(name) else None
    fmt = fontformats.of(ff[0]) if ff else None
    return bool(ff) and (fmt is None or fmt.clonable)


def clone(name: str, new_name: str, chars=None) -> Draft:
    """Un brouillon qui part d'une police de la machine. Son crénage n'est pas repris.
    `chars` : les caractères voulus, parmi les siens ; sinon tous, dans la limite de `MAX_CHARS`."""
    ff = fonts.find_font(name)
    m = fonts.metrics(*ff)
    k = UPEM / m['upem']
    scale = Affine.scaling(k)
    has = fonts.characters(name)
    picked = [c for c in chars if c in set(has)] if chars is not None else list(has)
    draft = Draft(name=new_name, ascent=m['ascent'] * k, descent=abs(m['descent']) * k, cap=m['cap'] * k)
    for ch in picked[:MAX_CHARS]:
        g, adv = fonts.glyph(ff[0], ff[1], ch)
        draft.glyphs[ord(ch)] = (_d(g.transformed(scale)) if g else '', adv * k)
    return draft


def same_file(a, b) -> bool:
    try:
        return pathlib.Path(a).resolve() == pathlib.Path(b).resolve()
    except OSError:
        return False


def name_taken(name: str, mine=None) -> bool:
    """Une autre police porte ce nom : les textes ne sauraient plus laquelle prendre (chaque nom doit être unique)."""
    if not fonts.is_available(name):
        return False
    got = fonts.find_font(name)
    return not (got and mine and same_file(got[0], mine))


def file_for(name: str, folder) -> pathlib.Path:
    """Un fichier neuf pour ce nom, sans écraser celui d'une autre police."""
    folder = pathlib.Path(folder)
    stem = _BAD_FILE.sub('_', name).strip(' .')[:100].strip(' .') or 'police'
    if stem.upper() in _RESERVED:
        stem = '_' + stem
    path = folder / f'{stem}.svg'
    n = 2
    while path.exists():
        path = folder / f'{stem} {n}.svg'
        n += 1
    return path


def inside(path, folder) -> bool:
    try:
        return pathlib.Path(path).resolve().is_relative_to(pathlib.Path(folder).resolve())
    except OSError:
        return False
