"""Automatismes d'usinage 3D : une suite d'étapes — ébauche, demi-finition,
finition… — appliquée d'un coup à une pièce 3D (STEP, STL, 3D XML), toute
la pièce ou les faces et contours choisis dans la vue 3D.

Pour chaque étape, l'outil est **proposé** d'après la pièce (taille,
profondeur, plus petit rayon creux) et les outils disponibles (ceux du
document, puis Mes outils), selon la règle de l'étape :

- 'gros'  : le plus gros outil de la nature voulue qui tient dans la pièce
  (ébauche) ;
- 'moyen' : environ la moitié de l'outil de l'étape précédente ;
- 'fin'   : rayon au plus égal au plus petit rayon creux de la pièce
  (finition), sinon environ 1/30 de la pièce ;
- 'outil' : l'outil choisi par l'utilisateur (`tool_id`).

Les réglages en découlent : passe en Z de l'outil (sinon la moitié de son
diamètre), recouvrement, pas de la carte, et pour un outil boule, la
distance entre passes qui laisse une crête d'au plus `crete` mm.

L'utilisateur modifie la suite (étapes, outils, réglages) et l'enregistre
sous un nom : fichiers JSON du dossier `automatismes_3d` des données (à côté
des modèles d'usinage). Les plugins ajoutent les leurs :
`api.add_templates('auto3d', {nom: suite})`.

Une suite :

    {"name": "…", "description": "…", "steps": [
        {"kind": "ebauche3d", "name": "Ébauche", "tool_kind": "fraise", "rule": "gros",
         "tool_id": "", "params": {"stock": 0.3}, "enabled": true}, …]}
"""
from __future__ import annotations

import json
import math
import pathlib
import re
from dataclasses import asdict, dataclass, field

#: genre des suites ajoutées par les plugins (`api.add_templates`)
KIND = 'auto3d'
#: règles de choix de l'outil
RULES = {'gros': 'Le plus gros qui tient (ébauche)', 'moyen': 'Moitié de l\'outil d\'avant',
         'fin': 'Rayon ≤ plus petit rayon creux (finition)', 'outil': 'Outil choisi'}
#: stratégies d'une étape
STEP_KINDS = ('ebauche3d', 'reprise3d', 'surface3d', 'niveaux3d')
#: crête laissée par défaut entre deux passes d'outil boule (mm)
CRETE = 0.01


@dataclass
class Step:
    kind: str = 'surface3d'
    name: str = ''
    tool_kind: str = 'boule'
    rule: str = 'fin'
    tool_id: str = ''                       # règle 'outil' : l'outil choisi (document ou Mes outils)
    params: dict = field(default_factory=dict)   # réglages de l'opération (stock, step_down, raster_dir, crete…)
    enabled: bool = True

    @classmethod
    def from_dict(cls, d: dict) -> 'Step':
        names = set(cls.__dataclass_fields__)
        s = cls(**{k: v for k, v in (d or {}).items() if k in names})
        s.params = dict(s.params or {})
        return s


@dataclass
class Sequence:
    name: str = ''
    description: str = ''
    steps: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {'name': self.name, 'description': self.description,
                'steps': [asdict(s) if isinstance(s, Step) else dict(s) for s in self.steps]}

    @classmethod
    def from_dict(cls, d: dict) -> 'Sequence':
        return cls(str(d.get('name') or ''), str(d.get('description') or ''),
                   [Step.from_dict(s) for s in d.get('steps') or [] if isinstance(s, dict)])


def builtin() -> dict[str, Sequence]:
    """Suites livrées avec VectorDrive."""
    rough = Step('ebauche3d', 'Ébauche', 'fraise', 'gros', params={'stock': 0.3, 'ramp': True})
    return {
        'Ébauche et finition': Sequence(
            'Ébauche et finition', 'Fraise : paliers en Z, 0,3 mm laissés ; boule : balayage croisé',
            [rough, Step('surface3d', 'Finition', 'boule', 'fin', params={'raster_dir': 'xy', 'crete': CRETE})]),
        'Ébauche, demi-finition, finition': Sequence(
            'Ébauche, demi-finition, finition',
            'Fraise : 0,5 mm laissés ; boule moyenne : 0,1 mm laissé ; petite boule : balayage croisé',
            [Step('ebauche3d', 'Ébauche', 'fraise', 'gros', params={'stock': 0.5, 'ramp': True}),
             Step('surface3d', 'Demi-finition', 'boule', 'moyen', params={'stock': 0.1, 'crete': 0.05}),
             Step('surface3d', 'Finition', 'boule', 'fin', params={'raster_dir': 'xy', 'crete': CRETE})]),
        'Ébauche, reprise, finition des pentes et des parois': Sequence(
            'Ébauche, reprise, finition des pentes et des parois',
            'Grosse fraise : paliers ; petite fraise : reprise des creux ; boule : balayage des pentes douces '
            '(≤ 50°) puis niveaux constants sur les parois (≥ 40°)',
            [Step('ebauche3d', 'Ébauche', 'fraise', 'gros', params={'stock': 0.3, 'ramp': True}),
             Step('reprise3d', 'Reprise', 'fraise', 'moyen', params={'stock': 0.3}),
             Step('surface3d', 'Finition des pentes', 'boule', 'fin',
                  params={'raster_dir': 'xy', 'crete': CRETE, 'slope_max': 50.0}),
             Step('niveaux3d', 'Finition des parois', 'boule', 'fin', params={'crete': CRETE, 'slope_min': 40.0})]),
        'Ébauche, finition, reprise des angles': Sequence(
            'Ébauche, finition, reprise des angles',
            'Fraise : paliers ; grosse boule : balayage croisé (passes larges) ; petite boule : reprise des '
            'angles et des creux que la grosse n\'atteint pas',
            [rough, Step('surface3d', 'Finition', 'boule', 'gros', params={'raster_dir': 'xy', 'crete': CRETE}),
             Step('reprise3d', 'Reprise des angles', 'boule', 'fin', params={'stock': 0.0, 'crete': CRETE})]),
        'Finition seule': Sequence(
            'Finition seule', 'Petite boule : balayage croisé (matière déjà ébauchée)',
            [Step('surface3d', 'Finition', 'boule', 'fin', params={'raster_dir': 'xy', 'crete': CRETE})]),
        'Ébauche seule': Sequence('Ébauche seule', 'Fraise : paliers en Z, 0,3 mm laissés', [rough]),
    }


# --- suites enregistrées ------------------------------------------------------------------
def user_dir() -> pathlib.Path:
    """Dossier des suites de l'utilisateur : `automatismes_3d`, à côté des
    modèles d'usinage (dossier des essais pendant les essais)."""
    from . import templates
    return templates.user_dir().parent / 'automatismes_3d'


def _file(name: str) -> pathlib.Path:
    stem = re.sub(r'[^\w.-]+', '_', name, flags=re.UNICODE).strip('_') or 'automatisme'
    return user_dir() / f'{stem}.json'


def user_sequences() -> dict[str, Sequence]:
    out = {}
    d = user_dir()
    if d.is_dir():
        for f in sorted(d.glob('*.json')):
            try:
                data = json.loads(f.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            if isinstance(data, dict) and data.get('name') and isinstance(data.get('steps'), list):
                out[str(data['name'])] = Sequence.from_dict(data)
    return out


def plugin_sequences() -> dict[str, Sequence]:
    from ..plugins import REGISTRY
    out = {}
    for name, d in (REGISTRY.templates.get(KIND) or {}).items():
        if isinstance(d, dict):
            d = {**d, 'name': d.get('name') or name}
            out[str(d['name'])] = Sequence.from_dict(d)
    return out


def all_sequences() -> dict[str, tuple[str, Sequence]]:
    """{nom: (origine 'cœur' | 'plugin' | 'utilisateur', suite)} ; une suite
    de l'utilisateur remplace celle du même nom."""
    out = {n: ('cœur', s) for n, s in builtin().items()}
    out.update({n: ('plugin', s) for n, s in plugin_sequences().items()})
    out.update({n: ('utilisateur', s) for n, s in user_sequences().items()})
    return out


def save_user(seq: Sequence) -> pathlib.Path:
    if not seq.name:
        raise ValueError('automatisme sans nom')
    f = _file(seq.name)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(seq.to_dict(), ensure_ascii=False, indent=1), encoding='utf-8')
    return f


def delete_user(name: str) -> bool:
    f = _file(name)
    if f.is_file():
        f.unlink()
        return True
    return False


# --- la pièce ------------------------------------------------------------------------------
@dataclass
class PartInfo:
    """Ce qui guide le choix des outils : taille de la zone (mm), sa
    profondeur sous le haut de la pièce, le plus petit rayon creux connu
    (STEP : trous, congés ; 0 si inconnu), la plus petite largeur de
    passage estimée ; `stock_top` : brut au-dessus du haut de la pièce
    (`core.stock3d`) — l'ébauche part de là ; `floor` : profondeur au plus
    (mm sous le haut de la pièce) pour rester au-dessus des mors de l'étau
    (`core.workspace.jaw_floor`, première prise seulement), 0 : sans limite."""
    size_x: float = 0.0
    size_y: float = 0.0
    depth: float = 0.0
    min_radius: float = 0.0
    min_width: float = 0.0
    stock_top: float = 0.0
    floor: float = 0.0


def analyze(model, faces=(), loops=()) -> PartInfo:
    """Mesures de la pièce (ou de la zone choisie) pour proposer les outils."""
    import numpy as np
    from ..core import faces3d
    tris = np.asarray(model.triangles, dtype=np.float64)
    top = float(tris[:, :, 2].max()) if len(tris) else 0.0
    sel = tris
    faces = list(faces or [])
    if faces:
        idx = faces3d.face_triangles(model.face_ids(), faces)
        if len(idx):
            sel = tris[idx]
    pts = sel.reshape(-1, 3)
    if loops:
        lp = np.concatenate([np.asarray(L, dtype=np.float64).reshape(-1, 3) for L in loops])
        pts = lp if not faces else np.concatenate([pts, lp])
    if not len(pts):
        return PartInfo()
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    info = PartInfo(float(hi[0] - lo[0]), float(hi[1] - lo[1]), max(0.0, top - float(lo[2])))
    radii = []
    kinds = getattr(model, 'face_kinds', None) or []
    wanted = set(faces) if faces else None
    for i, k in enumerate(kinds):
        if wanted is not None and i not in wanted:
            continue
        if k.get('genre') in ('cylindre', 'tore', 'sphere') and k.get('creux', True) and k.get('rayon'):
            r = float(k['rayon'])
            if r > 0.05:
                radii.append(r)
    info.min_radius = min(radii) if radii else 0.0
    info.min_width = min(info.size_x, info.size_y)
    return info


# --- outils proposés ----------------------------------------------------------------------
def _useful(tool) -> float:
    return float(tool.cut_length or 0.0)


def pick_tool(step: Step, tools: list, info: PartInfo, previous=None):
    """Outil proposé pour l'étape parmi `tools` (document d'abord, puis Mes
    outils), ou None (aucun de la nature voulue : à créer)."""
    if step.rule == 'outil' and step.tool_id:
        t = next((t for t in tools if t.id == step.tool_id), None)
        if t is not None:
            return t
    same = [t for t in tools if t.kind == step.tool_kind and t.diameter > 0]
    if not same:
        return None
    size = info.min_width or max(info.size_x, info.size_y) or 50.0
    if step.rule == 'gros':
        fit = [t for t in same if t.diameter <= max(1.0, size / 4)]
        if not fit:                                    # aucun ne tient : le plus petit, pas le plus gros
            return min(same, key=lambda t: (t.diameter, -_useful(t)))
        deep = [t for t in fit if _useful(t) >= info.depth + info.stock_top - 1e-9] or fit
        return max(deep, key=lambda t: (t.diameter, _useful(t)))
    if step.rule == 'moyen':
        want = (previous.diameter / 2) if previous is not None else max(1.0, size / 15)
        return min(same, key=lambda t: (abs(t.diameter - want), -t.diameter))
    # 'fin' (et 'outil' sans outil choisi)
    limit = 2 * info.min_radius if info.min_radius > 0 else min(6.0, max(1.0, size / 30))
    fit = [t for t in same if t.diameter <= limit + 1e-9]
    if fit:
        return max(fit, key=lambda t: t.diameter)
    return min(same, key=lambda t: t.diameter)


def new_tool(step: Step, info: PartInfo, previous=None):
    """Outil à créer quand aucun ne convient : diamètre d'après la règle."""
    from .model import CamTool
    size = info.min_width or max(info.size_x, info.size_y) or 50.0
    if step.rule == 'gros':
        d = min(12.0, max(1.0, size / 4))
    elif step.rule == 'moyen':
        d = previous.diameter / 2 if previous is not None else max(1.0, size / 15)
    else:
        d = 2 * info.min_radius if info.min_radius > 0 else min(6.0, max(1.0, size / 30))
    d = _round_d(d)
    label = {'fraise': 'Fraise Ø{0}', 'boule': 'Fraise boule Ø{0}'}.get(step.tool_kind, 'Outil Ø{0}')
    return CamTool(name=label.format(f'{d:g}'.replace('.', ',')), kind=step.tool_kind, diameter=d,
                   step_down=round(d / 2, 2), cut_length=max(3.0, round(3 * d, 1)), number=0)   # numéro : à l'ajout


def _round_d(d: float) -> float:
    """Diamètre courant le plus proche (au plus d)."""
    common = (0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 16.0, 20.0)
    below = [c for c in common if c <= d + 1e-9]
    return below[-1] if below else common[0]


def stepover_for_scallop(radius: float, crest: float) -> float:
    """Distance entre passes d'un outil boule de rayon `radius` qui laisse
    une crête de hauteur `crest` sur un plan : 2·√(2·r·h − h²)."""
    h = max(1e-6, min(crest, radius))
    return 2 * math.sqrt(max(0.0, 2 * radius * h - h * h))


# --- suite → opérations -------------------------------------------------------------------
@dataclass
class Planned:
    """Une étape prête : l'opération, son outil (et s'il est à créer ou à
    copier de Mes outils dans le document)."""
    step: Step
    op: object
    tool: object
    origin: str                              # 'document', 'bibliotheque', 'nouveau'
    limited: float = 0.0                     # profondeur ramenée à la longueur utile de l'outil (mm), 0 : non
    jaws: float = 0.0                        # profondeur ramenée au-dessus des mors de l'étau (mm), 0 : non


#: libellés des prises
SIDE_LABELS = {'': 'comme le dessin', '+Z': 'dessus', '-Z': 'dessous', '+X': 'côté +X', '-X': 'côté −X',
               '+Y': 'côté +Y', '-Y': 'côté −Y'}


def pose_text(who: str, side: str) -> str:
    """Message de l'arrêt avant une prise : « Poser la pièce : dessous vers
    l'outil », « Poser la pièce comme le dessin » (`side` '')."""
    from ..i18n import tr
    if not side:
        return tr('Poser {0} comme le dessin').format(who)
    if side.startswith('n:'):                              # posée sur une face plane (core.placement3d)
        return tr('Poser {0} sur sa face d\'appui choisie').format(who)
    return tr('Poser {0} : {1} vers l\'outil').format(who, tr(SIDE_LABELS.get(side, side)))


def plan_all(seq: Sequence, doc_tools: list, library: list, infos, *, groups, model_path: str = '',
             faces=(), loops=(), depth: float = 0.0, defaults: dict | None = None, body_names=None,
             floors: dict | None = None, home=('',), own_faces: dict | None = None,
             keep_zone: bool = False) -> list:
    """La suite pour chaque prise de chaque corps : `groups` [(corps, [faces
    vers l'outil])] (corps -1 : toute la pièce ; face '' : celle du dessin),
    `infos` {corps: PartInfo}. Entre deux prises, une instruction « poser
    la pièce » à l'opérateur. Une seule prise : la suite telle quelle.
    `floors` {(face, corps): profondeur au plus} : prises tenues dans leur
    propre étau (core.workspace) ; une pièce retournée sans le sien : sans
    limite. `home` : faces qui sont celle du dessin ('' et sa face) — une
    seule prise sur une autre face a aussi son « poser la pièce ».
    `own_faces` {corps: face} : corps positionnés à part (leur face du
    dessin est celle de leur pose). `keep_zone` : faces et contours choisis
    gardés pour un corps aussi (choisis sur ce corps, montré seul)."""
    from .model import Operation
    from ..i18n import tr
    out: list = []
    fresh: list = []
    many = sum(len(sides) for _b, sides in groups) > 1 or \
        any(side not in home for _b, sides in groups for side in sides)
    for body, sides in groups:
        for side in sides:
            name = (body_names or {}).get(body, '') if body >= 0 else ''
            if many:
                said = side or (own_faces or {}).get(body, '')
                text = pose_text(name or tr('la pièce'), said)
                op = Operation(name=text, kind='instruction', instruction='retournement',   # arrêt : broche coupée,
                               params={'message': text, 'park': True, 'setup': [said, body]},  # attente de
                               tool_id='')                                    # l'opérateur ; pose annoncée gardée
                out.append(Planned(None, op, None, 'instruction'))
            info = infos.get(body, infos.get(-1))
            if info is not None and ((side, body) in (floors or {}) or side):
                import dataclasses                               # pièce retournée : l'étau de sa prise, ou aucun
                want = float((floors or {}).get((side, body), 0.0))
                if want != info.floor:
                    info = dataclasses.replace(info, floor=want)
            part = plan(seq, list(doc_tools) + fresh, library, info, model_path=model_path,
                        faces=faces if body < 0 or keep_zone else [], loops=loops if body < 0 or keep_zone
                        else [], depth=depth,
                        defaults=defaults)
            for p in part:
                if p.origin == 'nouveau':
                    fresh.append(p.tool)                   # créé une fois, repris par les prises suivantes
                elif p.tool is not None and any(p.tool is t for t in fresh):
                    p.origin = 'nouveau'
                p.op.setup_face = side
                p.op.body3d = body
                if many:
                    bits = [b for b in (name, tr(SIDE_LABELS.get(side, side)) if side else '') if b]
                    p.op.name = f'{p.op.name} — ' + ', '.join(bits) if bits else p.op.name
            out.extend(part)
    return out


def plan(seq: Sequence, doc_tools: list, library: list, info: PartInfo, *, model_path: str = '',
         faces=(), loops=(), depth: float = 0.0, defaults: dict | None = None) -> list[Planned]:
    """Étapes actives de la suite → opérations (dans l'ordre), outils
    proposés et réglages déduits. Rien n'est ajouté au document ici."""
    from .model import Operation
    out: list[Planned] = []
    previous = None
    ids = {t.id for t in doc_tools}
    created: list = []                                   # outils à créer : repris par les étapes suivantes
    for step in seq.steps:
        if not step.enabled:
            continue
        pool = list(doc_tools) + [t for t in library if t.id not in ids]
        tool = pick_tool(step, pool, info, previous)
        if tool is None:
            want = new_tool(step, info, previous)
            tool = next((t for t in created if t.kind == want.kind and abs(t.diameter - want.diameter) < 1e-9), None)
            if tool is None:
                tool = want
                created.append(tool)
            origin = 'nouveau'
        else:
            origin = 'document' if tool.id in ids else 'bibliotheque'
        p = dict(step.params or {})
        crest = p.pop('crete', None)
        op = Operation(name=step.name or step.kind, kind=step.kind, tool_id=tool.id, depth=round(float(depth), 3),
                       model_path=model_path, faces3d=sorted(int(f) for f in faces),
                       contours3d=[[[round(float(c), 4) for c in pt] for pt in L] for L in loops],
                       **(defaults or {}))
        for k, v in p.items():
            if hasattr(op, k):
                setattr(op, k, v)
        if step.kind == 'reprise3d' and previous is not None:
            op.ref_tool_id = previous.id                 # l'outil d'avant : son reste est repris
        if step.kind == 'niveaux3d':
            if not p.get('step_down'):
                op.step_down = round(stepover_for_scallop(tool.diameter / 2, float(crest or CRETE)), 3) \
                    if tool.kind == 'boule' else (tool.step_down or round(tool.diameter / 4, 2))
            if not p.get('resolution'):
                op.resolution = round(min(0.1, max(0.02, tool.diameter / 40)), 3)
        elif step.kind in ('ebauche3d', 'reprise3d'):
            if step.kind == 'reprise3d' and tool.kind == 'boule' and not p.get('stepover_mm'):
                op.stepover_mm = round(stepover_for_scallop(tool.diameter / 2, float(crest or CRETE)), 3)   # finition
            if not p.get('step_down'):
                op.step_down = tool.step_down if tool.step_down and tool.step_down < tool.diameter else \
                    round(tool.diameter / 2, 2)
            if not p.get('resolution'):
                op.resolution = round(min(0.3, max(0.1, tool.diameter / 40)), 2)
        else:
            if tool.kind == 'boule' and not p.get('stepover_mm'):
                op.stepover_mm = round(stepover_for_scallop(tool.diameter / 2, float(crest or CRETE)), 3)
            if not p.get('step_down'):
                # finition : la surface d'une passe (la matière est déjà ébauchée) ; seule, à la passe de l'outil
                op.step_down = 0.0 if not out else max(round(float(depth or 0.0), 3), 1000.0)
            if not p.get('resolution'):
                so = op.stepover_mm or (tool.stepover or 0.2) * tool.diameter
                op.resolution = round(min(0.1, max(0.02, so / 2)), 3)
        limited = 0.0
        reach = float(getattr(tool, 'cut_length', 0.0) or 0.0)
        want = op.depth if op.depth > 0 else float(info.depth or 0.0)
        above = float(info.stock_top or 0.0) if step.kind == 'ebauche3d' else 0.0   # l'ébauche part du haut du brut
        if reach > 0 and want + above > reach + 1e-6:    # plus bas, le porte-outil toucherait la pièce
            op.depth = limited = round(max(0.01, reach - above), 3)
        jaws = 0.0
        floor = float(getattr(info, 'floor', 0.0) or 0.0)
        if floor > 0 and (op.depth if op.depth > 0 else float(info.depth or 0.0)) > floor + 1e-6:
            op.depth = jaws = round(floor, 3)              # plus bas, l'outil irait dans les mors
        out.append(Planned(step, op, tool, origin, limited, jaws))
        previous = tool
    return out
