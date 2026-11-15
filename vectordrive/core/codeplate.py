"""Plaque codée : un code (DataMatrix, QR, Code 128…) et son texte lisible,
chacun ajusté à sa fenêtre (TauDrive : plaque codée, à la façon des plaques
de production).

On part des fenêtres disponibles — deux cadres de la plaque type, l'un pour
le symbole, l'autre pour le texte — et le contenu s'y ajuste : le plus
grand code qui tienne (forme du DataMatrix, carrée ou rectangulaire,
choisie pour cela), centré, et le texte au plus grand dans son cadre.
L'inverse — choisir un module ou une police puis espérer que ça rentre —
donne les marquages qui débordent.

Le texte suit toujours le code : une nouvelle donnée refait les deux
(`rebuild`), à la place où la plaque a été déplacée.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from . import barcode as B
from . import codes
from .document import Group, Text
from .geom import Affine


@dataclass
class PlateSpec:
    data: str = ''
    kind: str = 'datamatrix'
    style: str = 'runs'
    font: str = 'Arial'
    code_frame: list = field(default_factory=list)   # [x0, y0, x1, y1] du cadre du code
    text_frame: list = field(default_factory=list)   # idem pour le texte ; vide : pas de texte
    quiet: float = 0.0                               # marge laissée dans le cadre du code (mm)

    @classmethod
    def from_dict(cls, d: dict) -> 'PlateSpec':
        return cls(**{k: v for k, v in (d or {}).items() if k in cls.__dataclass_fields__})


@dataclass
class Preset:
    """Préréglage de plaque codée : la plaque type, sans sa position —
    symbologie, police, fenêtre du code (largeur × hauteur), fenêtre du
    texte et son décalage depuis le centre du code, cadre tracé autour."""
    name: str = ''
    kind: str = 'datamatrix'
    font: str = 'Arial'
    code_w: float = 15.0
    code_h: float = 7.0
    text_w: float = 8.0
    text_h: float = 1.5
    text_dx: float = 0.0
    text_dy: float = -5.0
    frames: bool = True                               # cadres de la plaque type tracés (sinon gardés invisibles)

    @classmethod
    def from_dict(cls, d: dict) -> 'Preset':
        return cls(**{k: v for k, v in (d or {}).items() if k in cls.__dataclass_fields__})


#: préréglages livrés (exemples, à adapter)
FACTORY = (Preset('DataMatrix rectangulaire 15 × 7, texte dessous', 'datamatrix', 'Arial', 15.0, 7.0, 12.0, 2.0,
                  0.0, -5.5),
           Preset('Code carré 10 × 10, texte dessous', 'datamatrix', 'Arial', 10.0, 10.0, 10.0, 2.0, 0.0, -7.0),
           Preset('QR 20 × 20, texte dessous', 'qr', 'Arial', 20.0, 20.0, 18.0, 3.0, 0.0, -12.5))


def preset_frames(p: Preset, cx: float, cy: float) -> tuple[list, list]:
    """Fenêtres du code et du texte d'un préréglage, le code centré en (cx, cy)."""
    code = [cx - p.code_w / 2, cy - p.code_h / 2, cx + p.code_w / 2, cy + p.code_h / 2]
    tx, ty = cx + p.text_dx, cy + p.text_dy
    text = [tx - p.text_w / 2, ty - p.text_h / 2, tx + p.text_w / 2, ty + p.text_h / 2] if p.text_w > 0 else []
    return code, text


def preset_from_frames(name: str, code: list, text: list, kind: str = 'datamatrix', font: str = 'Arial') -> Preset:
    """Préréglage relevé sur deux cadres (fenêtres du code et du texte)."""
    cx, cy = (code[0] + code[2]) / 2, (code[1] + code[3]) / 2
    p = Preset(name, kind, font, round(code[2] - code[0], 4), round(code[3] - code[1], 4))
    if text:
        p.text_w, p.text_h = round(text[2] - text[0], 4), round(text[3] - text[1], 4)
        p.text_dx, p.text_dy = round((text[0] + text[2]) / 2 - cx, 4), round((text[1] + text[3]) / 2 - cy, 4)
    else:
        p.text_w = p.text_h = 0.0
    return p


def build_from_preset(p: Preset, data: str, cx: float, cy: float, tool: int = 0):
    """Plaque codée complète d'un préréglage : cadres (si `p.frames`), code
    et texte ajustés ; rend le groupe."""
    from . import geom
    from .document import Shape
    code_f, text_f = preset_frames(p, cx, cy)
    g = build(PlateSpec(data=data, kind=p.kind, font=p.font, code_frame=code_f, text_frame=text_f), tool)
    if p.frames:
        for f in (code_f, text_f):
            if f:
                g.children.append(Shape(path=geom.Path([geom.rect(f[0], f[1], f[2] - f[0], f[3] - f[1])]), tool=tool,
                                        name='cadre'))
    g.extra.setdefault('codeplate', {})['preset'] = p.name
    return g


def frames_of(items) -> tuple[list, list]:
    """Fenêtres d'une sélection (boîtes) : la plus grande pour le code, la
    suivante pour le texte — un code demande bien plus de surface qu'une
    ligne de caractères."""
    boxes = sorted((b for b in (it.bbox() for it in items) if b), key=lambda b: -(b[2] - b[0]) * (b[3] - b[1]))
    if not boxes:
        return [], []
    return list(boxes[0]), (list(boxes[1]) if len(boxes) > 1 else [])


def fit_code(kind: str, data: str, frame, quiet: float = 0.0):
    """(forme, module, largeur, hauteur) du plus grand code qui tienne dans
    le cadre, ou None (donnée impossible). Codes linéaires : barres de la
    hauteur du cadre."""
    w = frame[2] - frame[0] - 2 * quiet
    h = frame[3] - frame[1] - 2 * quiet
    if w <= 0 or h <= 0:
        return None
    best = None
    for shape in (('square', 'rect') if kind == 'datamatrix' else ('square',)):
        try:
            m = B.encode(kind, data, shape=shape)
        except B.CodeError:
            continue
        rows, cols = len(m), len(m[0])
        if B.is_linear(kind):
            mod = w / cols
            size = (cols * mod, h)
        else:
            mod = min(w / cols, h / rows)
            size = (cols * mod, rows * mod)
        if best is None or mod > best[1] + 1e-12:
            best = (shape, mod, size[0], size[1])
    return best


def build(spec: PlateSpec, tool: int = 0) -> Group:
    """Groupe « Plaque codée » : le code centré dans son cadre, le texte
    (vivant, dans son cadre) ; réglages dans `extra['codeplate']`."""
    from . import text as TX
    fit = fit_code(spec.kind, spec.data, spec.code_frame, spec.quiet)
    if fit is None:
        raise ValueError('donnée impossible à coder dans ce cadre')
    shape, mod, _w, h = fit
    bs = codes.BarcodeSpec(kind=spec.kind, text=spec.data, module=mod, style=spec.style, shape=shape,
                           human=False, height=h if B.is_linear(spec.kind) else 12.0)
    code = codes.build(bs, tool)
    bb = code.bbox()
    x0, y0, x1, y1 = spec.code_frame
    code = code.transformed(Affine.translation((x0 + x1) / 2 - (bb[0] + bb[2]) / 2, (y0 + y1) / 2 - (bb[1] + bb[3]) / 2))
    code.name = 'code'
    children = [code]
    if spec.text_frame:
        tx0, ty0, tx1, ty1 = spec.text_frame
        t = Text(text=spec.data, font=spec.font, size=1.0, align='center', tool=tool, name='texte')
        t.extra['box'] = {'x0': tx0, 'y0': ty0, 'x1': tx1, 'y1': ty1}
        t.outline = TX.outline_for(t)
        children.append(t)
    g = Group(children=children, name=f'Plaque codée : {spec.data}', tool=tool)
    cb = code.bbox()
    g.extra['codeplate'] = dict(asdict(spec), placed=[(cb[0] + cb[2]) / 2, (cb[1] + cb[3]) / 2])
    return g


def spec_of(g: Group) -> PlateSpec:
    """Réglages d'une plaque, cadres replacés là où elle a été déplacée."""
    d = dict(g.extra.get('codeplate') or {})
    spec = PlateSpec.from_dict(d)
    code = next((c for c in g.children if c.name == 'code'), None)
    if code is not None and d.get('placed') and spec.code_frame:
        cb = code.bbox()
        dx = (cb[0] + cb[2]) / 2 - d['placed'][0]
        dy = (cb[1] + cb[3]) / 2 - d['placed'][1]
        spec.code_frame = [spec.code_frame[0] + dx, spec.code_frame[1] + dy,
                           spec.code_frame[2] + dx, spec.code_frame[3] + dy]
    text = next((c for c in g.children if isinstance(c, Text)), None)
    if text is not None and 'box' in text.extra:
        b = text.extra['box']
        spec.text_frame = [b['x0'], b['y0'], b['x1'], b['y1']]
        spec.font = text.font
    return spec


def rebuild(g: Group, data: str | None = None, **changes) -> Group:
    """La plaque refaite (nouvelle donnée, ou autre réglage) : code et texte
    toujours d'accord."""
    spec = spec_of(g)
    if data is not None:
        spec.data = data
    for k, v in changes.items():
        setattr(spec, k, v)
    return build(spec, g.tool)
