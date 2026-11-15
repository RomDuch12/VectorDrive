"""Cadrans : graduations et chiffres autour d'un centre.

Un cadran couvre un secteur (`start`, `sweep` en degrés, sens horaire
positif comme sur une montre ou un manomètre, 0° = en haut) découpé en
`divisions` pas ; une graduation sur `major_every` est longue et porte un
nombre (de `value_from` à `value_to`), une sur `medium_every` est moyenne.
Les graduations sont des traits (à graver au fil) ou des rectangles
d'épaisseur `tick_width` (à graver en remplissage).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from . import geom
from .document import Group, Shape
from .geom import Affine, Path


@dataclass
class DialSpec:
    radius: float = 40.0            # rayon extérieur des graduations, mm
    start: float = -135.0           # angle de la première graduation (0 = haut, horaire +)
    sweep: float = 270.0            # étendue
    divisions: int = 50
    major_every: int = 10
    medium_every: int = 5
    major_len: float = 6.0
    medium_len: float = 4.0
    minor_len: float = 2.5
    tick_width: float = 0.0         # 0 = trait simple
    value_from: float = 0.0
    value_to: float = 100.0
    decimals: int = 0
    text_height: float = 4.0
    text_gap: float = 2.0           # entre les graduations longues et les chiffres
    labels_upright: bool = True     # chiffres droits (sinon : orientés vers le centre)
    font: str = 'Arial'
    circle: bool = True             # cercle de base sous les graduations

    @classmethod
    def from_dict(cls, d: dict) -> 'DialSpec':
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def _dir(angle_deg: float):
    """Vecteur unitaire pour un angle de cadran (0 = haut, horaire +)."""
    a = math.radians(90.0 - angle_deg)
    return math.cos(a), math.sin(a)


def tick_angles(spec: DialSpec) -> list[tuple[float, str]]:
    """(angle, 'major' | 'medium' | 'minor') de chaque graduation."""
    full = abs(abs(spec.sweep) - 360.0) < 1e-9
    n = spec.divisions
    out = []
    for k in range(n if full else n + 1):
        kind = 'minor'
        if spec.major_every and k % spec.major_every == 0:
            kind = 'major'
        elif spec.medium_every and k % spec.medium_every == 0:
            kind = 'medium'
        out.append((spec.start + spec.sweep * k / n, kind))
    return out


def build(spec: DialSpec, center=(0.0, 0.0), tool: int = 0) -> Group:
    cx, cy = center
    lengths = {'major': spec.major_len, 'medium': spec.medium_len, 'minor': spec.minor_len}
    ticks = []
    for ang, kind in tick_angles(spec):
        ux, uy = _dir(ang)
        r1, r0 = spec.radius, spec.radius - lengths[kind]
        a, b = (cx + ux * r0, cy + uy * r0), (cx + ux * r1, cy + uy * r1)
        if spec.tick_width > 0:
            # rectangle centré sur le trait
            w = spec.tick_width / 2
            px, py = -uy * w, ux * w
            ticks.append(geom.polyline([(a[0] + px, a[1] + py), (b[0] + px, b[1] + py),
                                        (b[0] - px, b[1] - py), (a[0] - px, a[1] - py)], closed=True))
        else:
            ticks.append(geom.polyline([a, b]))
    children = [Shape(path=Path(ticks), filled=spec.tick_width > 0, tool=tool, name='graduations')]
    if spec.circle:
        if abs(abs(spec.sweep) - 360) < 1e-9:
            base = geom.circle((cx, cy), spec.radius)
        else:
            # arc trigonométrique équivalent (les angles de cadran vont en sens horaire)
            a0 = 90.0 - spec.start
            base = geom.arc((cx, cy), spec.radius, a0, -spec.sweep)
        children.append(Shape(path=Path([base]), tool=tool, name='cercle'))
    # chiffres sur les graduations longues
    majors = [ang for ang, kind in tick_angles(spec) if kind == 'major']
    if majors and spec.text_height > 0:
        from . import text as T
        n_major = len(majors) - 1 if len(majors) > 1 else 1
        r_txt = spec.radius - spec.major_len - spec.text_gap - spec.text_height / 2
        contours = []
        for i, ang in enumerate(majors):
            v = spec.value_from + (spec.value_to - spec.value_from) * i / n_major
            label = f'{v:.{spec.decimals}f}'
            ux, uy = _dir(ang)
            px, py = cx + ux * r_txt, cy + uy * r_txt
            glyphs = T.layout(label, spec.font, spec.text_height, align='center')
            # centrage vertical : capitales centrées sur le rayon des chiffres
            m = Affine.translation(px, py)
            if not spec.labels_upright:
                m = m @ Affine.rotation(-ang)
            m = m @ Affine.translation(0, -spec.text_height / 2)
            contours += glyphs.transformed(m).contours
        children.append(Shape(path=Path(contours), filled=True, tool=tool, name='chiffres'))
    g = Group(children=children, name='Cadran', tool=tool)
    g.extra['dial'] = asdict(spec) | {'center': [cx, cy]}
    return g
