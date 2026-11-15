"""Post-processeurs : parcours → programme machine.

Tout programme sort avec un en-tête « à simuler avant usinage » et des
avertissements (cotes sous la profondeur prévue, hors de la machine,
outil sans régime…) : VectorDrive ne connaît ni la pièce bridée ni les
longueurs d'outil réelles.

Un post-processeur rend un ou plusieurs fichiers (`PostResult.files` :
nom, texte) ; `stem` est le nom choisi pour le programme. Celui qui écrit des
arcs le dit (attribut `arcs` de sa fonction) : ses parcours lui arrivent
ajustés en arcs à la tolérance du réglage (`CamSetup.arc_fit`, cam.arcfit).

Le cœur n'en contient aucun : les post-processeurs et les fiches machine
viennent des plugins (`plugins.Api.add_post`, `add_post_provider` pour
ceux qu'on tire des fichiers machine d'un dossier). Sans plugin, les
parcours se calculent, se voient et se simulent, sans programme à écrire.
"""
from __future__ import annotations

import pathlib

from dataclasses import dataclass, field


@dataclass
class PostResult:
    text: str
    warnings: list = field(default_factory=list)
    extension: str = '.nc'
    encoding: str = 'ascii'
    files: list = field(default_factory=list)       # [(nom de fichier, texte)]


def ascii_only(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in s if 32 <= ord(c) < 127)


def check(toolpaths, setup) -> list[str]:
    """Contrôles communs à tous les post-processeurs."""
    out = []
    ops = {o.id: o for o in setup.operations}
    for tp in toolpaths:
        op = ops.get(tp.op_id)
        tool = setup.tool(tp.tool_id)
        if tp.source == 'vectordrive' and op is not None:
            lowest = min((m.z for m in tp.moves), default=0.0)
            if lowest < -abs(op.depth) - 1e-6:
                out.append(f'« {tp.name} » descend à {lowest:.3f} mm, sous la profondeur prévue')
        if tool is not None and tool.kind != 'laser' and not tool.spindle:
            out.append(f'outil « {tool.name} » sans régime de broche')
        out.extend(f'« {tp.name} » : {w}' for w in tp.warnings)
    return out


#: post-processeurs du cœur : aucun (ils viennent des plugins)
BUILTIN: dict = {}


class PostError(ValueError):
    pass


def _plugin_posts() -> dict:
    from ...plugins import REGISTRY
    return REGISTRY.posts


def _providers() -> list:
    from ...plugins import REGISTRY
    return list(REGISTRY.post_providers)


def default_machines_dir() -> str:
    """Dossier de fiches machine livré par un plugin (`default_machines()`
    d'un fournisseur), pour quand l'utilisateur n'en a choisi aucun ; ''
    s'il n'y en a pas."""
    for prov in _providers():
        fn = getattr(prov, 'default_machines', None)
        if fn is None:
            continue
        try:
            d = fn()
        except Exception:                            # plugin en défaut : pas de dossier par défaut
            continue
        if d and pathlib.Path(d).is_dir():
            return str(d)
    return ''


def has_machine_files() -> bool:
    """Un plugin sait-il tirer des post-processeurs de fichiers machine ?"""
    return bool(_providers())


def posts(machines_dir: str = '') -> dict:
    """Post-processeurs disponibles : clé → libellé (ceux des plugins, puis
    ceux qu'ils tirent des fichiers machine du dossier `machines_dir`)."""
    out = dict(BUILTIN)
    out.update({k: v[0] for k, v in _plugin_posts().items()})
    if machines_dir:
        for prov in _providers():
            try:
                out.update(prov.posts(machines_dir))
            except Exception:                        # dossier illisible, fiche abîmée : on passe
                continue
    return out


def rotary(machine) -> bool:
    """Fiche machine qui enroule par l'axe rotatif (TypeEdit : Mset40 ≠ 0,
    bouton Cylindre/Cône du post-processeur)."""
    if machine is None or not hasattr(machine, 'get'):
        return False
    import re
    digits = re.sub(r'[^0-9]', '', str(machine.get('Mset40', '0') or '0').split(',')[0])
    return bool(digits) and int(digits) != 0


def double_wrap(toolpaths, setup, machine) -> list[str]:
    """Parcours enroulés pour une machine 3 axes (cam.wrap) alors que la fiche
    machine enroule déjà par l'axe rotatif : refus (ils le seraient deux fois)."""
    if not rotary(machine):
        return []
    ops = {o.id: o for o in setup.operations}
    names = [tp.name or getattr(ops.get(tp.op_id), 'name', '') for tp in toolpaths
             if tp.moves and (getattr(ops.get(tp.op_id), 'wrap', 'none') or 'none') != 'none']
    if not names:
        return []
    return [f'export refusé : {", ".join(f"« {n} »" for n in names[:5])} enroulé(s) pour une machine 3 axes, et la '
            'fiche machine enroule déjà par l\'axe rotatif (Mset40) — choisir l\'un ou l\'autre']


def family(key: str) -> str:
    """La machine désignée par une clé de post-processeur : la clé elle-même,
    ou pour une fiche machine celle du post-processeur qu'elle désigne
    (« mah:…Datron.MAH » → 'datron')."""
    if not key or key in _plugin_posts():
        return key or ''
    fns = {k: v[1] for k, v in _plugin_posts().items()}
    for prov in _providers():
        try:
            got = prov.resolve(key)
        except Exception:                                # fiche illisible : la clé telle quelle
            got = None
        if got:
            target = got[0]
            if isinstance(target, str):
                return target
            return next((k for k, fn in fns.items() if fn is target), key)
    return key


def _accepts(fn, name: str) -> bool:
    import inspect
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False
    return name in params or any(p.kind == p.VAR_KEYWORD for p in params.values())


def _shift_instruction(cy: dict, dx: float, dy: float) -> dict:
    """Instruction machine : ses positions prises sur le dessin (palpages :
    x, y ; mesure d'orientation : x1, y1, x2, y2) décalées comme les
    parcours ; les décalages (incréments) et le reste inchangés."""
    from .. import instructions as INS
    ins = INS.describe(cy.get('name', ''))
    if ins is None or not ins.pick or not isinstance(cy.get('params'), dict):
        return cy
    keys = (('x1', 'y1'), ('x2', 'y2')) if ins.pick == 'two_circles' else (('x', 'y'),)
    p = dict(cy['params'])
    for kx, ky in keys:
        try:
            if kx in p:
                p[kx] = float(p[kx]) - dx
            if ky in p:
                p[ky] = float(p[ky]) - dy
        except (TypeError, ValueError):
            pass
    return dict(cy, params=p)


def shifted(toolpaths, origin) -> list:
    """Copies des parcours (et de leurs cycles de trous, et des positions de
    leurs palpages) dont l'origine `origin` (x, y en mm, celle du dessin)
    devient le zéro ; les mêmes parcours si l'origine est absente ou au zéro."""
    import copy
    from ..model import Move
    try:
        dx, dy = float(origin[0]), float(origin[1])
    except (TypeError, ValueError, IndexError):
        return list(toolpaths)
    if abs(dx) < 1e-12 and abs(dy) < 1e-12:
        return list(toolpaths)
    out = []
    for tp in toolpaths:
        c = copy.copy(tp)                                # attributs ajoutés en route (parts, brut…) gardés
        c.moves = [Move(m.kind, m.x - dx, m.y - dy, m.z, m.cx - dx, m.cy - dy, fin=m.fin) if m.is_arc else
                   Move(m.kind, m.x - dx, m.y - dy, m.z, fin=m.fin) for m in tp.moves]
        c.cycles = [dict(cy, x=float(cy['x']) - dx, y=float(cy['y']) - dy)
                    if isinstance(cy, dict) and 'x' in cy and 'y' in cy else
                    _shift_instruction(cy, dx, dy) if isinstance(cy, dict) and cy.get('kind') == 'instruction'
                    else cy for cy in (tp.cycles or [])]
        out.append(c)
    return out


#: le zéro des programmes (TypeEdit : positionnement de la pièce, fenêtre Usinage) : celui qu'attend la machine
#: ('machine' : son post-processeur ou sa fiche le disent, sinon l'origine du dessin), l'origine du dessin, ou un
#: point de la plaque que l'opérateur retrouve sur la machine quand il règle l'origine
ZEROS = ('machine', 'dessin', 'plaque_hg', 'plaque_centre', 'plaque_bg')
#: les points de la plaque
PLATE_ZEROS = ('plaque_hg', 'plaque_centre', 'plaque_bg')


def default_zero(key: str) -> str:
    """Le zéro qu'attend la machine du post-processeur `key`, pris quand le dessin laisse le choix à la machine
    ('machine') : celui que déclare la fonction d'écriture d'un plugin (attribut `program_zero`) ou le fournisseur
    d'une fiche machine (`default_zero(clé)`) — par exemple le coin supérieur gauche de la plaque, pour une machine où
    l'opérateur règle l'origine sur ce coin au lancement ; 'dessin' (l'origine du dessin) sinon, ou pour une réponse
    inconnue."""
    got = ''
    entry = _plugin_posts().get(key) if key else None
    if entry is not None:
        got = getattr(entry[1], 'program_zero', '') or ''
    elif key:
        for prov in _providers():
            fn = getattr(prov, 'default_zero', None)
            if fn is None:
                continue
            try:
                got = fn(key) or ''
            except Exception:                            # fiche illisible, plugin en défaut : aucun zéro demandé
                got = ''
            if got:
                break
    return got if got in ZEROS[1:] else 'dessin'


def effective_zero(zero: str, key: str) -> str:
    """Le zéro du réglage `zero` pour le post-processeur `key` : celui qu'attend la machine pour 'machine' (ou un
    réglage inconnu), sinon le réglage lui-même."""
    return zero if zero in ZEROS[1:] else default_zero(key)


def zero_point(zero: str, plate, origin=None):
    """Le zéro du programme (x, y en mm du dessin) : un point de la plaque `plate` pour 'plaque_hg' (coin supérieur
    gauche ; TE : « Origine-plaque au coin supérieur gauche »), 'plaque_centre' (TE : « Centre-plaque au centre ») ou
    'plaque_bg' (coin inférieur gauche) ; `origin` (l'origine du dessin, None au zéro du dessin) pour 'dessin', pour un
    choix inconnu ou sans plaque."""
    if plate is None or zero not in PLATE_ZEROS:
        return origin
    x0, y0, w, h = float(plate.x), float(plate.y), float(plate.width), float(plate.height)
    if w <= 0 or h <= 0:
        return origin
    return {'plaque_hg': (x0, y0 + h), 'plaque_centre': (x0 + w / 2, y0 + h / 2), 'plaque_bg': (x0, y0)}[zero]


def zero_text(plate, origin) -> tuple:
    """Où tombe le zéro du programme `origin` (x, y en mm du dessin ; None : le zéro du dessin) sur la plaque
    `plate` : (texte, repérable). Un coin ou le centre de la plaque se retrouvent sur la machine quand l'opérateur
    règle l'origine ; un autre point, ou un dessin sans plaque, non."""
    try:
        ox, oy = (float(origin[0]), float(origin[1])) if origin is not None else (0.0, 0.0)
    except (TypeError, ValueError, IndexError):
        ox, oy = 0.0, 0.0
    if plate is None or not (plate.width > 0 and plate.height > 0):
        return 'zéro du dessin, sans plaque : sa place sur la pièce n\'est pas connue', False
    x0, y0, w, h = float(plate.x), float(plate.y), float(plate.width), float(plate.height)
    for (u, v), name in (((0, 1), 'coin supérieur gauche de la plaque'), ((0.5, 0.5), 'centre de la plaque'),
                         ((0, 0), 'coin inférieur gauche de la plaque'), ((1, 1), 'coin supérieur droit de la plaque'),
                         ((1, 0), 'coin inférieur droit de la plaque')):
        if abs(ox - (x0 + u * w)) <= 0.01 and abs(oy - (y0 + v * h)) <= 0.01:
            return name, True
    return (f'X {round(ox - x0, 3):g} ; Y {round(oy - y0, 3):g} mm depuis le coin inférieur gauche de la plaque, '
            'ni un coin ni le centre'), False


def _file_part(text: str) -> str:
    """Un morceau de nom de fichier : sans les caractères refusés par Windows."""
    out = ''.join('_' if c in '<>:"/' + chr(92) + '|?*' or ord(c) < 32 else c for c in str(text))
    return out.strip(' .') or 'sans_nom'


def program_groups(toolpaths, how: str, plan_of=None) -> list:
    """Les programmes à écrire (TE : Grouper) : [(suffixe du fichier, parcours)], dans l'ordre de la liste. 'plan' : un par plan
    (`plan_of(parcours)` rend son nom) ; 'parcours' : un par opération, numérotés ; sinon tout dans un fichier, sans suffixe."""
    paths = list(toolpaths)
    if how == 'plan' and plan_of is not None:
        out: dict = {}
        for tp in paths:
            out.setdefault(plan_of(tp) or '', []).append(tp)
        if len(out) > 1:
            return [(_file_part(name), group) for name, group in out.items()]
    elif how == 'parcours':
        out = {}
        for tp in paths:
            out.setdefault(tp.op_id or id(tp), []).append(tp)
        if len(out) > 1:
            return [(f'{i:02d}_{_file_part(group[0].name)}', group) for i, group in enumerate(out.values(), 1)]
    return [('', paths)]


#: orientations de sortie (TE, page 819) : (u, v) dans la plaque de W x H -> position dans la plaque orientée
ORIENTATIONS = {
    'normal': lambda u, v, W, H: (u, v),
    'miroir_y': lambda u, v, W, H: (W - u, v),
    'miroir_x': lambda u, v, W, H: (u, H - v),
    'r180': lambda u, v, W, H: (W - u, H - v),
    'miroir_r90a': lambda u, v, W, H: (H - v, W - u),
    'r90h': lambda u, v, W, H: (v, W - u),
    'r90a': lambda u, v, W, H: (H - v, u),
    'miroir_r90h': lambda u, v, W, H: (v, u),
}
#: celles qui retournent la plaque : les arcs changent de sens, et l'usinage aussi (avalant et opposition)
MIRRORS = frozenset({'miroir_y', 'miroir_x', 'miroir_r90a', 'miroir_r90h'})
#: celles qui échangent la largeur et la hauteur
QUARTERS = frozenset({'miroir_r90a', 'r90h', 'r90a', 'miroir_r90h'})


def _mapped_instruction(cy: dict, fn) -> dict:
    """Instruction machine : ses positions prises sur le dessin (voir `_shift_instruction`) passées par `fn`."""
    from .. import instructions as INS
    ins = INS.describe(cy.get('name', ''))
    if ins is None or not ins.pick or not isinstance(cy.get('params'), dict):
        return cy
    keys = (('x1', 'y1'), ('x2', 'y2')) if ins.pick == 'two_circles' else (('x', 'y'),)
    p = dict(cy['params'])
    for kx, ky in keys:
        try:
            if kx in p and ky in p:
                p[kx], p[ky] = fn(float(p[kx]), float(p[ky]))
        except (TypeError, ValueError):
            pass
    return dict(cy, params=p)


def oriented(toolpaths, how: str, rect, origin=None, box_mm=None) -> tuple:
    """Les parcours quand la plaque `rect` (x0, y0, x1, y1) est orientée par `how` : elle garde son coin inférieur gauche, le
    zéro du programme garde sa place relative sur elle (centre, coin…). Rend (parcours, origine, boîte) ; les mêmes si
    l'orientation est normale, inconnue, ou s'il n'y a pas de plaque."""
    fn = ORIENTATIONS.get(how)
    if fn is None or how == 'normal' or rect is None:
        return list(toolpaths), origin, box_mm
    import copy
    from ..model import Move
    x0, y0, x1, y1 = [float(v) for v in rect]
    W, H = x1 - x0, y1 - y0
    if W <= 0 or H <= 0:
        return list(toolpaths), origin, box_mm
    W2, H2 = (H, W) if how in QUARTERS else (W, H)
    swap = {'arc_cw': 'arc_ccw', 'arc_ccw': 'arc_cw'} if how in MIRRORS else {}

    def at(x: float, y: float) -> tuple:
        u, v = fn(x - x0, y - y0, W, H)
        return x0 + u, y0 + v
    out = []
    for tp in toolpaths:
        c = copy.copy(tp)
        moves = []
        for m in tp.moves:
            x, y = at(m.x, m.y)
            if m.is_arc:
                cx, cy = at(m.cx, m.cy)
                moves.append(Move(swap.get(m.kind, m.kind), x, y, m.z, cx, cy, fin=m.fin))
            else:
                moves.append(Move(m.kind, x, y, m.z, fin=m.fin))
        c.moves = moves
        cycles = []
        for cy in tp.cycles or []:
            if isinstance(cy, dict) and 'x' in cy and 'y' in cy:
                nx, ny = at(float(cy['x']), float(cy['y']))
                cycles.append(dict(cy, x=nx, y=ny))
            elif isinstance(cy, dict) and cy.get('kind') == 'instruction':
                cycles.append(_mapped_instruction(cy, at))
            else:
                cycles.append(cy)
        c.cycles = cycles
        out.append(c)
    ox, oy = (float(origin[0]), float(origin[1])) if origin is not None else (0.0, 0.0)
    new_origin = (x0 + (ox - x0) / W * W2, y0 + (oy - y0) / H * H2)
    box = None if box_mm is None else (x0, y0, box_mm[2], x0 + W2, y0 + H2, box_mm[5])
    return out, new_origin, box


def run(key: str, toolpaths, setup, *, title: str = '', machine=None, stem: str = 'programme',
        box_mm=None, out_dir: str = '', origin=None) -> PostResult:
    """Programme machine des parcours par le post-processeur `key` (d'un
    plugin, ou tiré d'une fiche machine par le plugin qui sait la lire) ;
    `out_dir` : dossier où les fichiers seront écrits — un post-processeur
    qui le demande (`machine_dir`) reçoit ce dossier tel que la machine le
    voit (F10 › FAO › chemins des programmes) ; `origin` : l'origine du
    dessin (x, y), zéro du programme comme dans TypeEdit (parcours et brut
    décalés)."""
    fns = {k: v[1] for k, v in _plugin_posts().items()}
    fn = fns.get(key)
    if fn is None:                                     # fiche machine : son plugin dit quel post et quelle fiche
        for prov in _providers():
            got = prov.resolve(key)
            if got:
                target, found = got[0], got[1]
                machine = found if machine is None else machine
                fn = target if callable(target) else fns.get(target)
                break
    if fn is None:
        raise PostError(f'post-processeur « {key} » absent (il est apporté par un plugin)')
    if origin is not None:                             # origine du dessin : zéro du programme
        toolpaths = shifted(toolpaths, origin)
        try:
            dx, dy = float(origin[0]), float(origin[1])
        except (TypeError, ValueError, IndexError):
            dx = dy = 0.0
        if box_mm is not None:
            box_mm = (box_mm[0] - dx, box_mm[1] - dy, box_mm[2], box_mm[3] - dx, box_mm[4] - dy, box_mm[5])
    tol = float(getattr(setup, 'arc_fit', 0.0) or 0.0)
    if tol > 0 and getattr(fn, 'arcs', False) and not rotary(machine):   # axe rotatif : segments
        from ..arcfit import fit_toolpaths
        toolpaths = fit_toolpaths(toolpaths, tol)
    refused = double_wrap(toolpaths, setup, machine)
    if refused:                                        # rien n'est écrit
        return PostResult('', refused, '.nc')
    extra = {}
    if out_dir and _accepts(fn, 'machine_dir'):
        from .. import ncpaths
        seen = ncpaths.to_machine(str(out_dir))
        if seen and seen.lower() != str(pathlib.Path(out_dir)).replace('/', '\\').lower():
            extra['machine_dir'] = seen                  # sinon : noms seuls, à côté du travail
    res = fn(toolpaths, setup, title=title, machine=machine, stem=stem, box_mm=box_mm, **extra)
    if not res.files and res.text:                     # texte vide : export refusé ou rien à écrire
        res.files = [(stem + res.extension, res.text)]
    res.warnings = check(toolpaths, setup) + res.warnings
    return res
