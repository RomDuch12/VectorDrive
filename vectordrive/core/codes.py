"""Codes-barres dessinés : matrice (`core.barcode`) → formes à graver.

Styles des codes 2D :

* ``runs``    — modules voisins d'une ligne fusionnés en rectangles
  (5 à 10 fois moins de contours, dessin identique) ;
* ``squares`` — un carré par module ;
* ``outline`` — contour fusionné de toutes les zones sombres (trous compris) ;
* ``dots``    — un point rond par module (micro-percussion, laser point
  par point), diamètre = module × `dot_ratio`.

Les codes linéaires (Code 128, Code 39, EAN-13) sont dessinés en barres de
hauteur `height`, avec la ligne de lecture humaine en option.
L'origine du dessin est le coin bas gauche du code (zone de silence non
dessinée : elle se réserve à la mise en page).

En négatif (`invert`, TypeEdit : Inverser couleur) : c'est le fond qui se
grave — un cadre autour du code (marge de `quiet` modules) moins les
modules ou les barres, qui restent en relief.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from . import barcode as B
from . import geom
from .document import Group, Shape
from .geom import Path


@dataclass
class BarcodeSpec:
    kind: str = 'datamatrix'
    text: str = ''
    module: float = 0.5            # mm
    height: float = 12.0           # mm, codes linéaires
    style: str = 'runs'            # runs | squares | outline | dots
    dot_ratio: float = 0.8
    level: str = 'M'               # QR : L, M, Q, H
    shape: str = 'square'          # DataMatrix : square, rect, auto…
    checksum: bool = False         # Code 39
    human: bool = True             # texte lisible sous un code linéaire
    font: str = 'Arial'
    text_height: float = 2.5
    invert: bool = False           # négatif : graver autour des modules (TypeEdit : Inverser couleur)
    quiet: float = 1.0             # négatif : marge du cadre autour du code (modules)

    @classmethod
    def from_dict(cls, d: dict) -> 'BarcodeSpec':
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


STYLES = (('runs', 'Rangées fusionnées'), ('squares', 'Carrés'), ('outline', 'Contour fusionné'),
          ('dots', 'Points'))


def label(spec: BarcodeSpec) -> str:
    return dict(B.KINDS).get(spec.kind, spec.kind)


def matrix(spec: BarcodeSpec) -> B.Matrix:
    return B.encode(spec.kind, spec.text, level=spec.level, shape=spec.shape, checksum=spec.checksum)


def human_text(spec: BarcodeSpec) -> str:
    if spec.kind == 'ean13':
        d = ''.join(ch for ch in spec.text if ch.isdigit())
        return d + str(B.ean13_key(d)) if len(d) == 12 else d
    return spec.text


def paths(spec: BarcodeSpec) -> tuple[Path, Path | None]:
    """(modules ou barres, texte lisible éventuel), en mm."""
    m = matrix(spec)
    mod = spec.module
    if B.is_linear(spec.kind):
        contours = [geom.rect(x * mod, 0, n * mod, spec.height) for _y, x, n in B.runs(m)]
        bars = _negative(Path(contours), spec, len(m[0]) * mod, spec.height) if spec.invert else Path(contours)
        txt = None
        if spec.human and spec.text_height > 0:
            from . import text as T
            width = len(m[0]) * mod
            t = T.layout(human_text(spec), spec.font, spec.text_height, align='center')
            txt = t.transformed(geom.Affine.translation(width / 2, -spec.text_height * 1.5))
        return bars, txt
    rows = len(m)
    top = lambda r: (rows - 1 - r) * mod
    if spec.style == 'squares':
        contours = [geom.rect(x * mod, top(y), mod, mod)
                    for y, row in enumerate(m) for x, v in enumerate(row) if v]
    elif spec.style == 'dots':
        r = mod * spec.dot_ratio / 2
        contours = [geom.circle(((x + 0.5) * mod, top(y) + 0.5 * mod), r)
                    for y, row in enumerate(m) for x, v in enumerate(row) if v]
    else:
        contours = [geom.rect(x * mod, top(y), n * mod, mod) for y, x, n in B.runs(m)]
    p = Path(contours)
    if spec.invert:
        return _negative(p, spec, len(m[0]) * mod, rows * mod), None
    if spec.style == 'outline':
        from . import pathops
        p = pathops.normalize(p)
    return p, None


def _negative(dark: Path, spec: BarcodeSpec, width: float, height: float) -> Path:
    """Fond à graver : le cadre (code + marge) moins les zones sombres."""
    from . import pathops
    q = max(0.0, spec.quiet) * spec.module
    frame = Path([geom.rect(-q, -q, width + 2 * q, height + 2 * q)])
    return pathops.boolean(frame, pathops.normalize(dark), 'difference')


def build(spec: BarcodeSpec, tool: int = 0) -> Group:
    """Groupe prêt à poser ; ses réglages restent attachés (re-édition)."""
    body, txt = paths(spec)
    children = [Shape(path=body, filled=True, tool=tool, name='modules')]
    if txt is not None and txt.contours:
        children.append(Shape(path=txt, filled=True, tool=tool, name='texte'))
    g = Group(children=children, name=f'{label(spec)} : {spec.text}', tool=tool)
    g.extra['barcode'] = asdict(spec)
    return g
