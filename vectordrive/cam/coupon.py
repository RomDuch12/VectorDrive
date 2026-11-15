"""Coupon d'essai laser, repris de TauDrive (même auteur).

Valider un réglage sur une matière : graver la même case plusieurs fois
en ne changeant qu'un paramètre à la fois, et lire le résultat sur la
chute. Le coupon est une grille : un paramètre varie en X, un autre en Y,
et chaque rangée et chaque colonne portent leurs valeurs gravées — sans
elles, une chute retrouvée trois semaines plus tard ne dit plus rien.

Dans VectorDrive, la puissance et la fréquence sont celles de l'outil
laser, la vitesse, le pas du remplissage et les passages ceux de
l'opération : chaque case reçoit son opération (sur ses seuls objets), et
une copie de l'outil quand la puissance ou la fréquence changent. Les
étiquettes ont la leur : même outil à puissance réduite, un passage.
Les valeurs sont arrondies à un pas de leur ordre de grandeur, pour
qu'elles se recopient telles quelles dans un réglage.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from ..core import geom
from ..core.document import Group, Shape, Text
from ..core.geom import Affine
from .model import CamTool, Operation

#: paramètre → (libellé, unité affichée, facteur réglage → affichage, pas d'arrondi)
AXES = {
    'power': ('Puissance', '%', 1.0, 0.5),
    'feed': ('Vitesse', 'm/min', 0.001, 500.0),
    'frequency': ('Fréquence', 'kHz', 1.0, 1.0),
    'resolution': ('Pas du remplissage', 'mm', 1.0, 0.005),
    'laser_passes': ('Passages', '', 1.0, 0.0),
}
#: réglages de l'outil (les autres sont ceux de l'opération)
TOOL_FIELDS = ('power', 'frequency')
INTEGERS = {'laser_passes'}
#: bornes proposées quand le réglage de départ ne dit rien
FALLBACK = {'power': (20.0, 100.0), 'feed': (1000.0, 4000.0), 'frequency': (20.0, 200.0),
            'resolution': (0.01, 0.08), 'laser_passes': (1, 5)}
#: puissance plafond des étiquettes (%) : elles doivent se lire, pas creuser
LABEL_POWER = 25.0
LABEL_PITCH = 0.05
#: part de la case occupée par un motif (le reste sépare les cases)
MOTIF_FILL = 0.9


def label(f: str) -> str:
    return AXES[f][0] if f in AXES else f


def unit(f: str) -> str:
    return AXES[f][1] if f in AXES else ''


def steps(start: float, stop: float, count: int, f: str) -> list:
    """Valeurs de `start` à `stop`, bornes comprises, arrondies au pas du
    paramètre (sans doublon)."""
    count = max(1, int(count))
    values = [start] if count == 1 else [start + (stop - start) * i / (count - 1) for i in range(count)]
    if f in INTEGERS:
        return sorted({max(1, int(round(v))) for v in values})
    q = AXES.get(f, ('', '', 1.0, 0.0))[3]
    if q:
        out = sorted({round(round(v / q) * q, 6) for v in values})
        if out:
            return out
    return [round(v, 6) for v in values]


def fmt(value, f: str) -> str:
    """Valeur gravée, dans l'unité affichée (vitesse en m/min)."""
    if f in INTEGERS:
        return f'{int(value)}'
    text = f'{float(value) * AXES.get(f, ("", "", 1.0, 0.0))[2]:.6f}'.rstrip('0').rstrip('.')
    return text or '0'


@dataclass
class Spec:
    x_field: str = 'power'
    x_from: float = 20.0
    x_to: float = 100.0
    x_count: int = 5
    y_field: str = 'feed'           # '' : une seule rangée
    y_from: float = 1000.0
    y_to: float = 4000.0
    y_count: int = 4
    cell: float = 8.0               # côté d'une case (mm)
    gap: float = 3.0
    label_size: float = 1.8
    filled: bool = True             # cases remplies (sinon marquées sur le trait)
    labels_filled: bool = False
    x_labels: bool = True
    y_labels: bool = True
    title: bool = True
    font: str = 'Arial'
    center: tuple = (0.0, 0.0)
    #: réglages fixes (ceux qui ne sont sur aucun axe) ; manquants : ceux de l'outil
    fixed: dict = field(default_factory=dict)


@dataclass
class Coupon:
    group: Group
    tools: list
    operations: list
    cells: int = 0


def _axis(spec: Spec, axis: str) -> list:
    f = getattr(spec, f'{axis}_field')
    if not f:
        return [None]
    return steps(getattr(spec, f'{axis}_from'), getattr(spec, f'{axis}_to'), getattr(spec, f'{axis}_count'), f)


def _motif_cell(motif: list, cx: float, cy: float, size: float) -> geom.Path:
    bb = geom.bbox_union(c.bbox() for c in motif)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    k = size * MOTIF_FILL / max(w, h, 1e-9)
    m = Affine.translation(cx, cy) @ Affine.scaling(k, k) @ Affine.translation(-(bb[0] + bb[2]) / 2,
                                                                            -(bb[1] + bb[3]) / 2)
    return geom.Path([c.transformed(m) for c in motif])


def _text(spec: Spec, text: str, x: float, y: float, name: str) -> Text:
    from ..core import text as TX
    t = Text(text=text, font=spec.font, size=spec.label_size, matrix=Affine.translation(x, y - spec.label_size / 2),
             align='center', name=name)
    try:
        t.outline = TX.outline_for(t)
    except Exception:                                    # police absente : contour calculé plus tard
        t.outline = None
    return t


def build(spec: Spec, tool: CamTool, *, name: str = '', motif: list | None = None) -> Coupon:
    """Grille d'essai : objets (groupés), copies de l'outil et opérations."""
    base = {'power': tool.power, 'frequency': tool.frequency, 'feed': tool.feed,
            'resolution': 0.05, 'laser_passes': 1}
    base.update({k: v for k, v in (spec.fixed or {}).items() if k in AXES and v is not None})
    xs, ys = _axis(spec, 'x'), _axis(spec, 'y')
    pitch = spec.cell + spec.gap
    width, height = len(xs) * pitch - spec.gap, len(ys) * pitch - spec.gap
    longest = max((len(fmt(v, spec.y_field)) for v in ys if v is not None), default=2)
    margin = max(spec.label_size * 0.62 * longest + 2.0, 8.0) if spec.y_labels and spec.y_field else 0.0
    top = spec.label_size + 2.0 if spec.x_labels and spec.x_field else 0.0
    x0 = spec.center[0] - (width + margin) / 2 + margin
    y0 = spec.center[1] + (height + top) / 2 - top
    title = name or tool.name or 'Laser'
    tools: dict = {}

    def tool_for(values: dict) -> CamTool:
        key = tuple(values[k] for k in TOOL_FIELDS)
        if key not in tools:
            t = dataclasses.replace(tool, id=CamTool().id, **{k: values[k] for k in TOOL_FIELDS})
            changed = [f'{label(k)} {fmt(values[k], k)} {unit(k)}'.strip() for k in TOOL_FIELDS
                       if k in (spec.x_field, spec.y_field)]
            t.name = f'{tool.name} — ' + ' · '.join(changed) if changed else tool.name
            tools[key] = t
        return tools[key]

    children, ops = [], []
    for iy, yv in enumerate(ys):
        cy = y0 - iy * pitch - spec.cell / 2
        for ix, xv in enumerate(xs):
            cx = x0 + ix * pitch + spec.cell / 2
            values = dict(base)
            variant = {}
            for f, v in ((spec.x_field, xv), (spec.y_field, yv)):
                if f and v is not None:
                    values[f] = v
                    variant[f] = v
            detail = ' · '.join(f'{label(k)} {fmt(v, k)} {unit(k)}'.strip() for k, v in variant.items())
            path = (_motif_cell(motif, cx, cy, spec.cell) if motif else
                    geom.Path([geom.rect(cx - spec.cell / 2, cy - spec.cell / 2, spec.cell, spec.cell)]))
            cell = Shape(path=path, name=f'case {detail}' if detail else 'case')
            children.append(cell)
            t = tool_for(values)
            ops.append(Operation(name=f'Coupon — {detail}' if detail else 'Coupon',
                                 kind='laser_gravure' if spec.filled else 'laser', tool_id=t.id, items=[cell.id],
                                 feed=float(values['feed']), resolution=float(values['resolution']),
                                 laser_passes=int(values['laser_passes']), depth=0.0))
        if spec.y_labels and spec.y_field and yv is not None:
            children.append(_text(spec, fmt(yv, spec.y_field), x0 - margin / 2, cy, f'étiquette {label(spec.y_field)}'))
    if spec.x_labels and spec.x_field:
        for ix, xv in enumerate(xs):
            children.append(_text(spec, fmt(xv, spec.x_field), x0 + ix * pitch + spec.cell / 2,
                                  y0 + top / 2 + 0.5, f'étiquette {label(spec.x_field)}'))
    if spec.title:
        head = f'{title} · X {label(spec.x_field)} {unit(spec.x_field)}'.strip()
        if spec.y_field:
            head += f' · Y {label(spec.y_field)} {unit(spec.y_field)}'.rstrip()
        children.append(_text(spec, head, spec.center[0], y0 + top + spec.label_size * 1.5, 'titre du coupon'))
    labels = [c for c in children if isinstance(c, Text)]
    out_tools = list(tools.values())
    if labels:
        lt = dataclasses.replace(tool, id=CamTool().id, power=min(base['power'] or LABEL_POWER, LABEL_POWER),
                                 frequency=base['frequency'], name=f'{tool.name} — étiquettes')
        out_tools.append(lt)
        ops.append(Operation(name='Coupon — étiquettes', kind='laser_gravure' if spec.labels_filled else 'laser',
                             tool_id=lt.id, items=[t.id for t in labels], feed=float(base['feed']),
                             resolution=LABEL_PITCH, laser_passes=1, depth=0.0))
    group = Group(name=f'Coupon d\'essai — {title}', children=children)
    return Coupon(group, out_tools, ops, len(xs) * len(ys))
