"""Règles graduées et verniers (comme le générateur de verniers de
TypeEdit) : une échelle droite de `divisions` pas, un grand trait tous les
`major_every` pas (numéroté), un moyen tous les `medium_every` ; au choix un
vernier dessous — `vernier` divisions couvrant `vernier` − 1 pas de la
règle, lecture au 1/`vernier` de pas.

Traits simples (à graver au fil) ou rectangles d'épaisseur `tick_width` (en
remplissage). Le groupe garde ses réglages : double-clic pour le modifier.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from . import geom
from .document import Group, Shape
from .geom import Affine, Path


@dataclass
class GraduationSpec:
    divisions: int = 100             # nombre de pas de la règle
    step: float = 1.0                # pas (mm)
    major_every: int = 10
    medium_every: int = 5
    major_len: float = 6.0
    medium_len: float = 4.5
    minor_len: float = 3.0
    tick_width: float = 0.0          # 0 = trait simple
    baseline: bool = True            # trait de base sous les graduations
    numbers: bool = True
    value_from: float = 0.0          # valeur du premier grand trait
    value_step: float = 10.0         # écart de valeur entre deux grands traits
    decimals: int = 0
    text_height: float = 2.5
    text_gap: float = 1.0
    font: str = 'Arial'
    vernier: int = 0                 # 0 = sans vernier ; sinon nombre de divisions du vernier
    vernier_gap: float = 0.0         # écart entre la règle et le vernier (mm)
    label_angle: float = 0.0         # chiffres inclinés de… (°, 90 : perpendiculaires aux traits, lus de bas en haut)
    labels_below: bool = False       # chiffres sous le trait de base (sinon au-dessus des grands traits)

    @classmethod
    def from_dict(cls, d: dict) -> 'GraduationSpec':
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def _kind(k: int, major: int, medium: int) -> str:
    if major and k % major == 0:
        return 'major'
    if medium and k % medium == 0:
        return 'medium'
    return 'minor'


def _tick(x: float, y0: float, y1: float, w: float):
    if w > 0:
        h = w / 2
        return geom.polyline([(x - h, y0), (x + h, y0), (x + h, y1), (x - h, y1)], closed=True)
    return geom.polyline([(x, y0), (x, y1)])


def _labels(items, font: str, height: float, angle: float = 0.0, below: bool = False):
    """Contours des nombres : [(texte, x centre, y bas)] ; `angle` : chaque
    nombre tourné autour de son point d'attache (il part alors du trait au
    lieu d'être centré) ; `below` : sous le point d'attache."""
    from . import text as T
    contours = []
    for label, x, y in items:
        if abs(angle) < 1e-9:
            glyphs = T.layout(label, font, height, align='center')
            dy = -height if below else 0.0
            contours += glyphs.transformed(Affine.translation(x, y + dy)).contours
            continue
        glyphs = T.layout(label, font, height, align='right' if below else 'left')
        glyphs = glyphs.transformed(Affine.translation(0.0, -height / 2))     # centré sur l'axe du trait
        contours += glyphs.transformed(Affine.translation(x, y) @ Affine.rotation(angle, (0.0, 0.0))).contours
    return contours


def ticks(spec: GraduationSpec) -> list[tuple[float, str]]:
    """(abscisse, nature) des traits de la règle."""
    return [(k * spec.step, _kind(k, spec.major_every, spec.medium_every)) for k in range(spec.divisions + 1)]


def vernier_ticks(spec: GraduationSpec) -> list[tuple[float, str]]:
    """(abscisse, nature) des traits du vernier : n divisions sur n − 1 pas."""
    n = int(spec.vernier)
    if n < 2:
        return []
    d = spec.step * (n - 1) / n
    half = n // 2 if n % 2 == 0 else 0
    return [(k * d, 'major' if k in (0, n) else ('medium' if half and k == half else 'minor')) for k in range(n + 1)]


def build(spec: GraduationSpec, origin=(0.0, 0.0), tool: int = 0) -> Group:
    """Groupe : graduations, trait de base, nombres, vernier. `origin` =
    premier trait, sur le trait de base ; les traits montent."""
    ox, oy = origin
    lengths = {'major': spec.major_len, 'medium': spec.medium_len, 'minor': spec.minor_len}
    w = max(0.0, spec.tick_width)
    tk = [_tick(ox + x, oy, oy + lengths[kind], w) for x, kind in ticks(spec)]
    children = [Shape(path=Path(tk), filled=w > 0, tool=tool, name='graduations')]
    length = spec.divisions * spec.step
    if spec.baseline:
        children.append(Shape(path=Path([geom.polyline([(ox, oy), (ox + length, oy)])]), tool=tool, name='base'))
    if spec.numbers and spec.text_height > 0:
        items, n = [], 0
        for x, kind in ticks(spec):
            if kind == 'major':
                v = spec.value_from + spec.value_step * n
                y = oy - spec.text_gap if spec.labels_below else oy + spec.major_len + spec.text_gap
                items.append((f'{v:.{spec.decimals}f}', ox + x, y))
                n += 1
        if items:
            children.append(Shape(path=Path(_labels(items, spec.font, spec.text_height, spec.label_angle,
                                                    spec.labels_below)), filled=True, tool=tool, name='nombres'))
    vt = vernier_ticks(spec)
    if vt:
        vy = oy - spec.vernier_gap
        vk = [_tick(ox + x, vy, vy - lengths[kind], w) for x, kind in vt]
        children.append(Shape(path=Path(vk), filled=w > 0, tool=tool, name='vernier'))
        if spec.baseline and spec.vernier_gap > 0:
            vlen = vt[-1][0]
            children.append(Shape(path=Path([geom.polyline([(ox, vy), (ox + vlen, vy)])]), tool=tool,
                                  name='base du vernier'))
        if spec.numbers and spec.text_height > 0:
            n = int(spec.vernier)
            marks = [(str(k), ox + x, vy - spec.major_len - spec.text_gap - spec.text_height)
                     for k, (x, kind) in enumerate(vt) if kind != 'minor' or k == n]
            children.append(Shape(path=Path(_labels(marks, spec.font, spec.text_height * 0.8)), filled=True,
                                  tool=tool, name='nombres du vernier'))
    g = Group(children=children, name='Règle graduée' if not vt else 'Règle et vernier', tool=tool)
    g.extra['graduation'] = asdict(spec) | {'origin': [ox, oy]}
    return g
