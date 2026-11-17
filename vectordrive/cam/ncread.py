"""Lecture d'un programme ISO (G-code) en parcours, pour le voir et le
simuler (TypeEdit : Simulations NC) — le programme d'une autre machine ou
d'un autre logiciel vérifié avant de le lancer.

Lu : G0 (rapide), G1 (avance ; descente seule en Z : plongée), G2 / G3
(arcs horaire / anti-horaire, centre par I J ou par R — I J relatifs au
départ, ou absolus comme les écrit la Cielle (fiche TypeEdit Ijki=0) : G90.1
/ G91.1 s'ils sont écrits, sinon celui des deux qui met le départ et
l'arrivée à la même distance du centre), G90 / G91
(absolu / relatif), G20 / G21 (pouces / mm), G17 (plan XY, seul plan suivi :
les arcs G18 / G19 sont lus en ligne droite et signalés), mots modaux,
numéros de ligne N, commentaires ( … ) et ; … . Le reste (F, S, T, M) est
ignoré. Cycles de perçage G81–G89 (modaux, G80 ou un G0–G3 les arrêtent) :
à chaque position, descente rapide au plan R, avance jusqu'au fond Z, retour
au plan R (G99) ou à la cote de départ (G98, par défaut) — débourrages Q et
temporisations non détaillés. Arcs G18 (XZ) et G19 (YZ) : découpés en petits
segments (vus en 3D).

Aussi : Heidenhain en dialogue texte clair (BEGIN PGM… : L, CC, C, CR,
FMAX, cotes incrémentales IX…), et les langages des plugins
(`Api.add_nc_reader` : SimPL…), reconnus au contenu ou à l'extension.
"""
from __future__ import annotations

import math
import re

from .model import Move, Toolpath

_WORD = re.compile(r'([A-Z])\s*([-+]?(?:\d+\.?\d*|\.\d+))')


def _clean(line: str) -> str:
    line = re.sub(r'\([^)]*\)', ' ', line)
    line = line.split(';', 1)[0]
    return line.upper()


def dialect(text: str, name: str = '') -> str:
    """Langage du programme : libellé d'un lecteur de plugin, 'heidenhain' ou 'iso'."""
    from ..plugins import REGISTRY
    ext = ('.' + name.rsplit('.', 1)[-1].lower()) if '.' in name else ''
    for label, exts, _read, sniff in REGISTRY.nc_readers:
        try:
            if (sniff is not None and sniff(text)) or (ext and ext in exts):
                return label
        except Exception:                              # reconnaissance d'un plugin en défaut : suivante
            continue
    head = text[:4000].upper()
    if 'BEGIN PGM' in head or re.search(r'^\s*\d*\s*L\s+[XYZ][+-]?\d', head, re.M) and 'G0' not in head:
        return 'heidenhain'
    return 'iso'


def read(text: str, name: str = 'Programme ISO', path: str | None = None) -> Toolpath:
    """Parcours du programme `text`, quel que soit son langage (voir `dialect`).
    Plusieurs outils : `tp.parts`, un parcours par outil (voir `split_tools`).
    `path` : le fichier, passé aux lecteurs des plugins qui le demandent
    (fichiers joints par la machine : durée calculée, brut…)."""
    from ..plugins import REGISTRY
    d = dialect(text, name)
    if d == 'heidenhain':
        tp = read_heidenhain(text, name)
    else:
        tp = None
        for label, _exts, fn, _sniff in REGISTRY.nc_readers:
            if label == d:
                try:
                    tp = fn(text, name, path=path) if path else fn(text, name)
                except TypeError:                          # lecteur d'avant : (texte, nom)
                    tp = fn(text, name)
                tp.source = 'nc'
                break
        if tp is None:
            tp = read_iso(text, name)
    if not getattr(tp, 'parts', None):
        tp.parts = split_tools(tp, getattr(tp, 'tool_changes', None) or [])
    libs = aliases = None
    infos = dict(getattr(tp, 'tool_infos', None) or {})
    changes = getattr(tp, 'tool_changes', None) or []
    spindles = list(getattr(tp, 'spindles', None) or [])
    for part in [tp] + list(tp.parts or []):
        lab = str(changes[0][1]) if part is tp and changes else str(getattr(part, 'tool_label', '') or '')
        part.tool_info = complete_info(infos.get(lab) or {}, lab, part)
        sp = spindle_of(part, spindles)
        if sp:                                             # la broche de ce passage (un outil repris plus loin)
            part.tool_info['spindle'] = sp
        if getattr(part, 'tool_guess', None) is None:
            if libs is None:
                libs, aliases = libraries(), load_aliases()
            label = part.name
            if part is tp:                                 # programme d'un seul outil : son libellé de changement
                label = ' '.join([tp.name] + [str(x) for _i, x in changes[:1]])
            hit, src = resolve(alias_of(part.tool_info, aliases), libs)     # un outil choisi à sa place : d'abord
            part.tool_alias = hit is not None
            if hit is None:
                hit, src = match_tool(part.tool_info, label, libs)
            part.tool_guess = hit if hit is not None else proposal(part.tool_info, label)
            part.tool_source = src
    return tp


#: dossier de Mes outils où vont les outils créés d'après un programme
PROGRAM_FOLDER = 'Outils des programmes'
#: associations retenues (« Choisir un outil existant », case « Retenir ce choix ») : à côté de Mes outils
ALIAS_FILE = 'associations_programmes.json'


def alias_path():
    from . import toollib
    return toollib.default_path().with_name(ALIAS_FILE)


def program_key(info) -> dict:
    """Ce qui désigne l'outil d'un programme : sa référence, son nom, son numéro (Cielle : T…), ceux qu'il donne."""
    info = info if isinstance(info, dict) else {}
    out = {}
    for k in ('ref', 'name'):
        v = str(info.get(k) or '').strip()
        if v:
            out[k] = v
    try:
        n = int(info.get('number') or 0)
    except (TypeError, ValueError):
        n = 0
    if n > 0:
        out['number'] = n
    return out


def same_program_tool(a, b) -> bool:
    """Les deux descriptions désignent-elles le même outil de programme ? Leurs références quand toutes deux en ont
    (une en commun) ; sinon le nom ; sinon, sans nom ni référence, le numéro."""
    a, b = program_key(a), program_key(b)
    if a and a == b:                                     # la même description, même sans rien de lisible (réf. « / »)
        return True
    ra, rb = ref_tokens(a.get('ref')), ref_tokens(b.get('ref'))
    if ra and rb:
        return bool(ra & rb)
    na, nb = _norm(a.get('name')), _norm(b.get('name'))
    if na or nb:
        return na == nb
    return bool(a.get('number')) and a.get('number') == b.get('number')


def load_aliases(path=None, strict: bool = False) -> list:
    """Les associations retenues [{'programme': …, 'outil': …}] ; fichier absent : aucune ; illisible : aucune, ou
    (`strict`) OSError s'il est inaccessible, ValueError s'il est abîmé. Lu avec ou sans BOM."""
    import json
    p = path or alias_path()
    try:
        text = p.read_text(encoding='utf-8-sig')
    except FileNotFoundError:
        return []
    except OSError:
        if strict:
            raise
        return []
    except ValueError:                                   # un autre codage (ANSI, UTF-16) : abîmé, pas une erreur
        if strict:
            raise
        return []
    try:
        data = json.loads(text)
    except ValueError:
        if strict:
            raise
        return []
    items = data.get('associations') if isinstance(data, dict) else None
    if not isinstance(items, list):
        if strict:
            raise ValueError('associations absentes')
        return []
    return [a for a in items if isinstance(a, dict)
            and isinstance(a.get('outil'), dict) and program_key(a.get('programme'))]


def _aliases_to_rewrite(path=None) -> list:
    """Les associations avant de les réécrire : un fichier abîmé est mis de côté (« .abime.json ») plutôt qu'écrasé ;
    inaccessible (partage réseau absent…) : OSError, rien n'est réécrit."""
    p = path or alias_path()
    try:
        return load_aliases(p, strict=True)
    except ValueError:
        p.replace(p.with_name(p.stem + '.abime' + p.suffix))
        return []


def save_aliases(items, path=None) -> None:
    """Écrit les associations : un fichier temporaire à nom unique (deux postes, deux instances), puis remplacé."""
    import json
    import os
    import tempfile
    p = path or alias_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=p.name + '.', suffix='.tmp', dir=str(p.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(json.dumps({'version': 1, 'associations': list(items)}, ensure_ascii=False, indent=1))
        os.replace(tmp, p)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def tool_target(tool) -> dict:
    """Ce qui retrouve l'outil choisi dans les bibliothèques (`toollib.find_match`)."""
    return {'name': str(tool.name or ''), 'ref': str(tool.ref or ''), 'kind': str(tool.kind or 'fraise'),
            'diameter': float(tool.diameter or 0.0), 'angle': float(tool.angle or 0.0), 'tip': float(tool.tip or 0.0)}


def alias_of(info, aliases):
    """L'outil (`tool_target`) choisi à la place de celui du programme, le dernier retenu ; None : aucun."""
    if not program_key(info):
        return None
    return next((a['outil'] for a in reversed(list(aliases or [])) if same_program_tool(a['programme'], info)), None)


def resolve(target, libs) -> tuple:
    """(outil, bibliothèque) d'un outil retenu (`tool_target`), cherché dans les bibliothèques dans l'ordre ;
    (None, '') : aucun."""
    if not isinstance(target, dict) or not (target.get('name') or target.get('ref')):
        return None, ''
    from . import toollib
    from .model import CamTool
    try:
        want = CamTool(name=str(target.get('name') or ''), ref=str(target.get('ref') or ''),
                       kind=str(target.get('kind') or 'fraise'), diameter=float(target.get('diameter') or 0.0),
                       angle=float(target.get('angle') or 0.0), tip=float(target.get('tip') or 0.0))
    except (TypeError, ValueError):
        return None, ''
    for src, tools in libs:
        hit = toollib.find_match(want, tools)
        if hit is not None:
            return hit, src
    return None, ''


def remember(info, tool, path=None) -> bool:
    """Retient `tool` pour l'outil du programme décrit par `info` (l'association d'avant remplacée)."""
    key = program_key(info)
    if not key:
        return False
    items = [a for a in _aliases_to_rewrite(path) if not same_program_tool(a['programme'], key)]
    items.append({'programme': key, 'outil': tool_target(tool)})
    save_aliases(items, path)
    return True


def forget(info, path=None) -> int:
    """Oublie l'association de l'outil du programme ; rend le nombre d'associations retirées."""
    if not program_key(info):
        return 0
    items = _aliases_to_rewrite(path)
    keep = [a for a in items if not same_program_tool(a['programme'], info)]
    if len(keep) != len(items):
        save_aliases(keep, path)
    return len(items) - len(keep)


def spindle_of(part, spindles: list) -> float:
    """Vitesse de broche (S, modale) en vigueur au premier mouvement d'usinage du parcours `part` ; `spindles` =
    [(rang du mouvement suivant, S)] du programme entier ; 0 : inconnue."""
    if not spindles:
        return 0.0
    k = next((i for i, mv in enumerate(part.moves) if mv.kind != 'rapid'), 0)
    at = int(getattr(part, 'first_move', 0) or 0) + k
    before = [s for i, s in spindles if i <= at]
    return float(before[-1]) if before else 0.0


def libraries() -> list:
    """[(nom, outils)] où chercher l'outil d'un programme : Mes outils, puis les bibliothèques des plugins (tools.json
    de l'atelier…), dans l'ordre ; une bibliothèque illisible est sautée."""
    out = []
    try:
        from . import toollib
        out.append(('Mes outils', list(toollib.library())))
    except Exception:                                      # Mes outils illisible : les autres
        pass
    from ..plugins import REGISTRY
    for name, loader in list(REGISTRY.tool_libraries.items()):
        try:
            out.append((name, list(loader() or [])))
        except Exception:                                  # bibliothèque d'un plugin en défaut : suivante
            continue
    return out


def ref_tokens(ref) -> set:
    """Références d'un outil, en minuscules : « 0068443G / 114206 » donne {'0068443g', '114206'}."""
    return {x.strip().casefold() for x in re.split(r'[/,;|]', str(ref or '')) if x.strip()}


def _norm(s) -> str:
    return re.sub(r'[\s_]+', ' ', str(s or '')).strip().casefold()


def same_identity(t, info: dict) -> bool:
    """L'outil `t` est-il celui que décrit `info` (une référence du programme parmi les siennes, sinon même nom et pas
    d'autre référence) ?"""
    refs = ref_tokens(info.get('ref'))
    if refs:
        return bool(refs & ref_tokens(getattr(t, 'ref', '')))
    name = _norm(info.get('name'))
    return bool(name) and _norm(getattr(t, 'name', '')) == name


def other_ref(t, ref) -> bool:
    """`t` a une référence, et aucune n'est `ref` : un autre outil, même s'il porte le même nom."""
    a, b = ref_tokens(ref), ref_tokens(getattr(t, 'ref', ''))
    return bool(a) and bool(b) and not a & b


def match_tool(info: dict, label: str = '', libs=()) -> tuple:
    """(outil, nom de sa bibliothèque) d'un parcours lu, ou (None, '') : d'abord la référence du programme parmi celles
    des outils (Mes outils, puis les bibliothèques des plugins), puis son nom (le même, ou une des références de
    l'outil : un commentaire ISO qui donne la référence), puis une référence d'outil écrite en mot entier dans ce nom.
    Jamais un outil de même nom et d'une autre référence, ni un outil dont le nom est seulement contenu dans celui du
    programme ; le libellé (`label` : nom du fichier compris) n'entre pas en compte."""
    info = info or {}
    ref = info.get('ref')
    for key in ('ref', 'name'):
        if info.get(key):
            for src, tools in libs:
                for t in tools:
                    if same_identity(t, {key: info[key]}) and not other_ref(t, ref):
                        return t, src
    name = str(info.get('name') or '').strip().casefold()
    if not name:
        return None, ''
    for src, tools in libs:                              # le nom donné est une référence de l'outil
        for t in tools:
            if name in ref_tokens(getattr(t, 'ref', '')) and not other_ref(t, ref):
                return t, src
    best, size = (None, ''), 0
    for src, tools in libs:                              # une référence de l'outil, mot entier du nom donné :
        for t in tools:                                  # la plus longue (« ABC 12345 » plutôt que « 12345 »)
            n = max((len(r) for r in ref_tokens(getattr(t, 'ref', '')) if len(r) >= 5 and ref_in(r, name)),
                    default=0)
            if n > size and not other_ref(t, ref):
                best, size = (t, src), n
    return best


def ref_in(ref: str, name: str) -> bool:
    """La référence `ref` est écrite en mot entier dans `name` (tous deux en minuscules) : ni lettre ni chiffre
    collés devant ou derrière (« _ », « - », « . », « , », une espace la séparent : « FR2_0068443G », « D3,0068443G »,
    « (0068443G) », « 0068443G_3 », « 114917_30__0_2 »). Une référence qui finit par un chiffre n'est pas suivie d'une
    décimale (« 12345.6 ») ni d'un suffixe de variante en fin de mot (« 114917-2 », « 114917_2 » : un autre outil).
    Une référence à espace (« ABC 12345 ») compte aussi."""
    tail = r'(?![^\W_])'
    if ref[-1:].isdigit():
        tail += r'(?![.,]\d|[-_]\d{1,2}(?![\w-]|[.,]\d))'
    return re.search(r'(?<![^\W_])' + re.escape(ref) + tail, name) is not None


def complete_info(info: dict, label: str, part) -> dict:
    """Ce que le programme dit de l'outil d'un parcours : nom, référence, fabricant, numéro (T…), broche (tr/min),
    avances de coupe et de plongée (mm/min) — celles des mouvements quand le lecteur n'en donne pas."""
    from collections import Counter
    out = {k: v for k, v in dict(info or {}).items() if v not in (None, '')}
    m = re.match(r'\s*T(\d+)\b', str(label or ''))
    if m and 'number' not in out:
        out['number'] = int(m.group(1))
    moves, feeds = part.moves, list(getattr(part, 'feeds', None) or [])
    if feeds and len(feeds) == len(moves):
        for key, kinds in (('feed', ('feed', 'arc_cw', 'arc_ccw')), ('plunge', ('plunge',))):
            c = Counter(round(f, 3) for mv, f in zip(moves, feeds) if mv.kind in kinds and f > 0)
            if c and not out.get(key):
                out[key] = c.most_common(1)[0][0]
    return out


def cotes_of_name(name: str) -> dict:
    """Cotes lues dans un nom d'outil d'atelier où Ø, ° et la virgule sont devenus « _ » : numéro en tête
    (« 3_… »), Ø (« Fr2 », « _14 »), angle et pointe d'un cône (« 30__0_6 » : 30°, pointe 0,6), dents (« Z2 »),
    longueur utile (« Lg4 », « L4 »)."""
    out: dict = {}
    s = str(name or '').strip()
    m = re.match(r'(\d+)_(.*)$', s)
    if m:
        out['number'] = int(m.group(1))
        s = m.group(2)
    # fin d'une cote : ni chiffre, ni décimale (« _5 », « .5 ») qui suive (« 30__0_6 Balay », « 30__0_6mm »,
    # « Fr2_5 L10 ») ; quatre chiffres ou plus après « _ » sont autre chose : une référence (« FR2_0068443G » : Ø 2)
    end = r'(?!\d|[.,]\d|_\d{1,3}(?!\d))'
    m = re.search(r'(?:^|_|Fr_?)(\d{2,3})__(\d{1,2})(?:_(\d{1,3}))?' + end, s, re.I)
    if m and 5 <= int(m.group(1)) <= 179:                # pointe entière aussi : « 90__1 »
        out.update(kind='conique', angle=float(m.group(1)), tip=float(f'{m.group(2)}.{m.group(3) or 0}'))
    else:
        m = re.search(r'Fr_?(\d{1,3}(?:_\d{1,3})?)' + end, s, re.I) or \
            re.search(r'(?:^|_)_(\d{1,3}(?:_\d{1,3})?)' + end, s)
        if m:
            out['diameter'] = float(m.group(1).replace('_', '.'))
    m = re.search(r'(?:^|_)Z(\d+)(?=_|$)', s, re.I)
    if m:
        out['flutes'] = int(m.group(1))
    m = re.search(r'(?:^|_)Lg?(\d{1,3}(?:_\d{1,3})?)' + end, s, re.I)
    if m:
        out['cut_length'] = float(m.group(1).replace('_', '.'))
    return out


def proposal(info: dict, label: str = ''):
    """L'outil à créer pour un parcours lu dont l'outil n'est dans aucune bibliothèque : nom, référence (ou numéro,
    Cielle), fabricant, broche et avances du programme ; nature et cotes lues du nom ou du libellé (« Fr2 »,
    « 30__0_6 », « Ø2 », « 30° »). None : le programme ne dit rien de l'outil."""
    from .model import CamTool
    info = info or {}
    name = str(info.get('name') or '').strip()
    cotes = cotes_of_name(name) if name else {}
    g = guess_tool(name) if name else None               # le nom du fichier ne dit rien de l'outil
    if g is None and not cotes and not any(info.get(k) for k in ('ref', 'spindle', 'feed')):
        return None
    num = info.get('number') or cotes.get('number')
    t = CamTool(name=name or (f'T{int(num)}' if num else 'Outil du programme'))   # le nom entier : il se retrouve
    if g is not None:
        t.kind, t.diameter, t.angle = g.kind, g.diameter, g.angle
    for k, v in cotes.items():
        setattr(t, k, v)
    if t.kind == 'conique' and 'diameter' not in cotes and g is None:
        t.diameter = max(3.0, t.tip)
    if num:
        t.number = int(num)
    t.ref, t.vendor = str(info.get('ref') or ''), str(info.get('vendor') or '')
    for k, attr in (('spindle', 'spindle'), ('feed', 'feed'), ('plunge', 'plunge'), ('ramp', 'ramp_feed'),
                    ('finish_feed', 'finish_feed')):
        try:
            v = float(info.get(k) or 0.0)
        except (TypeError, ValueError):
            v = 0.0
        if v > 0:
            setattr(t, attr, v)
    return t


def guess_tool(label: str, library=()):
    """Outil d'un parcours lu d'après son libellé : un outil de Mes outils dont
    la référence (ou le nom) y figure, sinon un outil fait des cotes lues
    (« Ø2 », « D2 », « 30° ») ; None : rien de reconnu."""
    from .model import CamTool
    text = str(label or '')
    low = text.lower()
    for t in library or ():
        ref = str(getattr(t, 'ref', '') or '').strip().lower()
        if len(ref) >= 4 and ref in low:
            return t
    for t in library or ():
        name = str(getattr(t, 'name', '') or '').strip().lower()
        if len(name) >= 5 and name in low:
            return t
    m = re.search(r'(?:Ø|\bD)\s*(\d+(?:[.,]\d+)?)', text)
    a = re.search(r'(\d+(?:[.,]\d+)?)\s*°', text)
    if not m and not a:
        return None
    d = float(m.group(1).replace(',', '.')) if m else 3.0
    ang = float(a.group(1).replace(',', '.')) if a else 0.0
    return CamTool(name=text[:40], kind='conique' if ang else 'fraise', diameter=d, angle=ang)


def split_tools(tp: Toolpath, changes: list) -> list:
    """Un parcours par outil : `changes` = [(rang du premier mouvement,
    libellé de l'outil)] ; un seul outil (ou aucun changement) : []."""
    marks = sorted((int(i), str(lab)) for i, lab in changes if 0 <= int(i) <= len(tp.moves))
    if len(marks) < 2 and not (marks and marks[0][0] > 0):
        return []
    if not marks or marks[0][0] > 0:
        marks = [(0, '')] + marks
    out = []
    for k, (i, lab) in enumerate(marks):
        j = marks[k + 1][0] if k + 1 < len(marks) else len(tp.moves)
        if j <= i:
            continue
        part = Toolpath(op_id='', tool_id='', name=f'{tp.name} — {lab}' if lab else tp.name, source='nc')
        part.tool_label = lab                              # libellé du changement d'outil (clé de `tool_infos`)
        part.first_move = i                                # rang de son premier mouvement dans le programme
        part.moves = tp.moves[i:j]
        feeds = getattr(tp, 'feeds', None)
        if feeds and len(feeds) == len(tp.moves):
            part.feeds = feeds[i:j]
        out.append(part)
    return out if len(out) > 1 else []


def _arc_points(p0, p1, c, cw: bool, axes: tuple, tol: float = 0.01) -> list:
    """Points d'un arc dans le plan des axes `axes` (indices de x, y, z),
    l'axe restant interpolé (hélice) ; corde à `tol` près."""
    a, b = axes
    other = 3 - a - b
    r = math.hypot(p0[a] - c[0], p0[b] - c[1])
    a0 = math.atan2(p0[b] - c[1], p0[a] - c[0])
    a1 = math.atan2(p1[b] - c[1], p1[a] - c[0])
    sweep = a1 - a0
    if cw:
        while sweep >= -1e-12:
            sweep -= 2 * math.pi
    else:
        while sweep <= 1e-12:
            sweep += 2 * math.pi
    step = 2 * math.acos(max(-1.0, min(1.0, 1 - tol / max(r, 1e-9)))) if r > tol else math.pi / 8
    n = max(2, int(math.ceil(abs(sweep) / max(step, 1e-3))))
    out = []
    for i in range(1, n + 1):
        t = i / n
        q = [0.0, 0.0, 0.0]
        q[a] = c[0] + r * math.cos(a0 + sweep * t)
        q[b] = c[1] + r * math.sin(a0 + sweep * t)
        q[other] = p0[other] + (p1[other] - p0[other]) * t
        out.append(tuple(q))
    out[-1] = tuple(p1)
    return out


def arc_center(x, y, nx, ny, i, j, ij_abs=None):
    """Centre (cx, cy) d'un arc de (x, y) à (nx, ny) et sa lecture : I J
    relatifs au départ (Fanuc) ou absolus (Cielle) — `ij_abs` imposé, ou
    None : celle qui met le départ et l'arrivée à la même distance du centre,
    l'autre l'étant nettement moins. Rend (cx, cy, absolus ?, tranché ?)."""
    if ij_abs is not None:
        return (i, j, True, True) if ij_abs else (x + i, y + j, False, True)

    def gap(cx, cy):
        r0, r1 = math.hypot(x - cx, y - cy), math.hypot(nx - cx, ny - cy)
        return abs(r0 - r1), max(0.005, 1e-4 * max(r0, r1))
    e_rel, t_rel = gap(x + i, y + j)
    e_abs, t_abs = gap(i, j)
    if e_abs <= t_abs and e_rel > 10 * t_rel:
        return i, j, True, True
    if e_rel <= t_rel and e_abs > 10 * t_abs:
        return x + i, y + j, False, True
    return x + i, y + j, False, False                     # les deux (cercle entier…) ou aucune : relatifs


def ij_gaps(x, y, nx, ny, i, j) -> tuple[float, float]:
    """Écarts (mm) entre les distances du départ et de l'arrivée au centre d'un
    arc lu avec I J absolus, puis relatifs : celle qui convient donne ~0."""
    def gap(cx, cy):
        return abs(math.hypot(x - cx, y - cy) - math.hypot(nx - cx, ny - cy))
    return gap(i, j), gap(x + i, y + j)


def read_iso(text: str, name: str = 'Programme ISO', ij_abs=None) -> Toolpath:
    """Parcours d'un programme ISO (G-code) ; `ij_abs` : centres d'arcs I J
    absolus (True), relatifs (False), ou reconnus arc par arc (None)."""
    tp = Toolpath(op_id='', tool_id='', name=name, source='nc')
    x = y = z = 0.0
    ij_mode = ij_abs                                      # G90.1 / G91.1, ou appris des arcs tranchés
    ij_seen_abs = undecided = False
    gap_abs = gap_rel = 0.0                               # écarts cumulés des arcs non tranchés, dans chaque lecture
    motion = 0
    absolute = True
    scale = 1.0
    plane = 17
    odd_planes = cycles = 0
    cycle = None                                          # cycle de perçage actif : {'r', 'z', 'top'}
    retract_r = False                                     # G99 : retour au plan R (sinon G98 : départ)
    relative_cycles = False
    tp.tool_changes = []
    tp.tool_infos = {}                                    # libellé du changement d'outil → numéro, nom, broche
    tp.spindles = []                                      # [(rang du mouvement suivant, S)]
    tp.feeds = []                                         # avance programmée de chaque mouvement (mm/min)
    feed = 0.0
    label = ''
    for raw in text.splitlines():
        tp.feeds.extend([feed] * (len(tp.moves) - len(tp.feeds)))
        line = _clean(raw)
        if not line.strip() or line.strip().startswith('%'):
            continue
        words = _WORD.findall(line)
        if not words:
            continue
        fw = next((v for letter, v in words if letter == 'F'), None)
        if fw is not None:
            feed = float(fw) * scale
        tw = next((v for letter, v in words if letter == 'T'), None)
        sw = next((v for letter, v in words if letter == 'S'), None)
        if tw is not None:                                # changement d'outil : un parcours par outil
            note = re.findall(r'\(([^)]*)\)', raw)
            label = f'T{int(float(tw))}' + (f' {note[0].strip()}' if note and note[0].strip() else '')
            tp.tool_infos.setdefault(label, {'number': int(float(tw)),
                                             'name': note[0].strip() if note and note[0].strip() else ''})
        if sw is not None and label in tp.tool_infos and float(sw) > 0:
            tp.tool_infos[label].setdefault('spindle', float(sw))
        if sw is not None and float(sw) > 0:
            tp.spindles.append((len(tp.moves), float(sw)))  # broche modale : celle de chaque passage d'outil
        if tw is not None:
            if not tp.tool_changes or tp.tool_changes[-1][1] != label:
                if tp.tool_changes and tp.tool_changes[-1][0] == len(tp.moves):
                    tp.tool_changes[-1] = (len(tp.moves), label)
                else:
                    tp.tool_changes.append((len(tp.moves), label))
        coords = {}
        in_cycle = False
        for letter, val in words:
            v = float(val)
            if letter == 'G':
                g = int(round(v)) if abs(v - round(v)) < 1e-6 else v
                if g in (0, 1, 2, 3):
                    motion = g
                    cycle = None                          # un mouvement ordinaire arrête le cycle
                elif g == 80:
                    cycle = None
                elif g == 98:
                    retract_r = False
                elif g == 99:
                    retract_r = True
                elif g == 90:
                    absolute = True
                elif g == 91:
                    absolute = False
                elif isinstance(g, float) and abs(g - 90.1) < 1e-6:
                    ij_mode = ij_abs = True               # centres d'arcs absolus
                elif isinstance(g, float) and abs(g - 91.1) < 1e-6:
                    ij_mode, ij_abs = False, False
                elif g == 20:
                    scale = 25.4
                elif g == 21:
                    scale = 1.0
                elif g in (17, 18, 19):
                    plane = g
                elif isinstance(g, int) and 81 <= g <= 89:
                    cycles += 1
                    in_cycle = True
            elif letter in 'XYZIJKR':
                coords[letter] = v * scale
        if in_cycle:                                      # G8x : plan R et fond Z (modaux) ; départ = cote actuelle
            if not absolute:
                relative_cycles = True
            prev = cycle or {}
            cycle = {'r': coords.get('R', prev.get('r', z)), 'z': coords.get('Z', prev.get('z', z)),
                     'top': z if not prev else prev.get('top', z)}
        if cycle is not None:
            if in_cycle or 'X' in coords or 'Y' in coords:
                if absolute:
                    nx, ny = coords.get('X', x), coords.get('Y', y)
                else:
                    nx, ny = x + coords.get('X', 0.0), y + coords.get('Y', 0.0)
                if not in_cycle and 'Z' in coords:        # nouveau fond pour les trous suivants
                    cycle['z'] = coords['Z'] if absolute else cycle['z'] + coords['Z']
                top, r, bottom = cycle['top'], cycle['r'], cycle['z']
                tp.moves.append(Move('rapid', nx, ny, max(top, r)))
                tp.moves.append(Move('rapid', nx, ny, r))
                tp.moves.append(Move('plunge', nx, ny, bottom))
                end = r if retract_r else max(top, r)
                tp.moves.append(Move('rapid', nx, ny, end))
                x, y, z = nx, ny, end
            continue
        if not any(k in coords for k in 'XYZ'):
            continue
        if absolute:
            nx, ny, nz = coords.get('X', x), coords.get('Y', y), coords.get('Z', z)
        else:
            nx, ny, nz = x + coords.get('X', 0.0), y + coords.get('Y', 0.0), z + coords.get('Z', 0.0)
        if motion == 0:
            tp.moves.append(Move('rapid', nx, ny, nz))
        elif motion in (2, 3) and plane == 17:
            if 'I' in coords or 'J' in coords:
                cx, cy, is_abs, sure = arc_center(x, y, nx, ny, coords.get('I', 0.0), coords.get('J', 0.0),
                                                  ij_abs)
                if not sure and ij_mode is not None:      # cercle entier : la lecture des arcs d'avant
                    cx, cy, is_abs, _s = arc_center(x, y, nx, ny, coords.get('I', 0.0), coords.get('J', 0.0),
                                                    ij_mode)
                elif not sure:
                    undecided = True
                    ga, gr = ij_gaps(x, y, nx, ny, coords.get('I', 0.0), coords.get('J', 0.0))
                    gap_abs += ga
                    gap_rel += gr
                elif ij_abs is None:
                    ij_mode = is_abs
                ij_seen_abs = ij_seen_abs or is_abs
            elif 'R' in coords:
                cx, cy = _center_from_r(x, y, nx, ny, coords['R'], motion == 2)
            else:
                cx, cy = (x + nx) / 2, (y + ny) / 2
            tp.moves.append(Move('arc_cw' if motion == 2 else 'arc_ccw', nx, ny, nz, cx, cy))
        elif motion in (2, 3):                            # G18 (XZ) / G19 (YZ) : segments, vus en 3D
            axes = (0, 2) if plane == 18 else (1, 2)
            keys = ('I', 'K') if plane == 18 else ('J', 'K')
            p0, p1 = (x, y, z), (nx, ny, nz)
            if (keys[0] in coords or keys[1] in coords) and (ij_abs if ij_abs is not None else bool(ij_mode)):
                c = (coords.get(keys[0], 0.0), coords.get(keys[1], 0.0))        # centres absolus (G90.1)
            elif keys[0] in coords or keys[1] in coords:
                c = (p0[axes[0]] + coords.get(keys[0], 0.0), p0[axes[1]] + coords.get(keys[1], 0.0))
            elif 'R' in coords:
                # G18 : sens vu depuis +Y inversé (repère X, Z) ; le centre suit la même règle
                c = _center_from_r(p0[axes[0]], p0[axes[1]], p1[axes[0]], p1[axes[1]], coords['R'],
                                   (motion == 2) != (plane == 18))
            else:
                c = ((p0[axes[0]] + p1[axes[0]]) / 2, (p0[axes[1]] + p1[axes[1]]) / 2)
            cw = (motion == 2) != (plane == 18)
            for q in _arc_points(p0, p1, c, cw, axes):
                tp.moves.append(Move('feed', *q))
            odd_planes += 1
        else:
            plunge = abs(nx - x) < 1e-9 and abs(ny - y) < 1e-9 and nz < z
            tp.moves.append(Move('plunge' if plunge else 'feed', nx, ny, nz))
        x, y, z = nx, ny, nz
    tp.feeds.extend([feed] * (len(tp.moves) - len(tp.feeds)))
    if ij_abs is None and undecided and ij_seen_abs:      # cercles entiers avant le premier arc tranché
        return read_iso(text, name, ij_abs=True)
    if ij_abs is None and ij_mode is None and undecided and gap_rel > 0.01 and gap_rel > 10.0 * gap_abs:
        return read_iso(text, name, ij_abs=True)          # aucun arc tranché (petits arcs loin de l'origine) :
                                                          # les centres absolus suivent bien mieux l'ensemble
    if ij_seen_abs:
        tp.warnings.append('programme ISO : centres des arcs (I J) en cotes absolues, comme la Cielle')
    if relative_cycles:
        tp.warnings.append(f'programme ISO : {cycles} cycle(s) de perçage en cotes relatives (G91), tracés en '
                           'cotes absolues : à vérifier')
    if not tp.moves:
        tp.warnings.append('programme ISO : aucun mouvement lu')
    return tp


_HH_WORD = re.compile(r'\b(I?)([XYZ])\s*([-+]?\s*(?:\d+\.?\d*|\.\d+))')


def read_heidenhain(text: str, name: str = 'Programme Heidenhain') -> Toolpath:
    """Parcours d'un programme Heidenhain en dialogue texte clair : L (droite,
    FMAX : rapide), CC (centre de cercle), C (arc jusqu'au point, DR- horaire,
    DR+ anti-horaire), CR (arc de rayon R), CT (arc tangent au mouvement
    d'avant) ; cotes incrémentales IX, IY, IZ. Cycles de perçage 200 à 205
    (Q200 distance d'approche, Q201 profondeur, Q203 cote de la surface,
    Q204 saut de bride) tracés à chaque CYCL CALL ou M99 ; les autres cycles
    sont signalés."""
    tp = Toolpath(op_id='', tool_id='', name=name, source='nc')
    x = y = z = 0.0
    cc = (0.0, 0.0)
    skipped = 0
    cycle = None                                         # cycle défini : {'num', Qnnn: valeur}
    heading = None                                       # direction du dernier mouvement (arcs CT)
    tp.tool_changes = []
    tp.feeds = []
    feed = 0.0
    for raw in text.splitlines():
        tp.feeds.extend([feed] * (len(tp.moves) - len(tp.feeds)))
        line = raw.split(';', 1)[0].upper()
        qm = re.match(r'\s*\d*\s*Q(\d+)\s*=\s*([-+]?\s*\d*\.?\d+)', line)
        if qm and cycle is not None:                     # paramètre du cycle en cours de définition
            cycle[int(qm.group(1))] = float(qm.group(2).replace(' ', ''))
            continue
        m = re.match(r'\s*\d*\s*(CC|CR|CT|C|L|BLK|TOOL|BEGIN|END|CYCL)\b(.*)', line)
        if not m:
            continue
        cmd, rest = m.group(1), m.group(2)
        if cmd == 'TOOL':
            tm = re.match(r'\s*CALL\s+(\d+)', rest)
            if tm:
                tp.tool_changes.append((len(tp.moves), f'T{tm.group(1)}'))
            continue
        if cmd == 'BLK':                                # BLK FORM 0.1 (coin bas) et 0.2 (coin haut) : le brut
            bm = re.match(r'\s*FORM\s+0\.([12])\s*Z?\s*(.*)', rest)
            if bm:
                got = {a: float(v.replace(' ', '')) for inc, a, v in _HH_WORD.findall(bm.group(2)) if not inc}
                blk = getattr(tp, '_blk', {})
                blk[bm.group(1)] = got
                tp._blk = blk
                lo, hi = blk.get('1'), blk.get('2')
                if lo and hi and all(a in lo and a in hi for a in 'XYZ'):
                    tp.stock = (min(lo['X'], hi['X']), min(lo['Y'], hi['Y']), min(lo['Z'], hi['Z']),
                                max(lo['X'], hi['X']), max(lo['Y'], hi['Y']), max(lo['Z'], hi['Z']))
            continue
        if cmd in ('BEGIN', 'END'):
            continue
        if cmd == 'CYCL':
            dm = re.match(r'\s*DEF\s+(\d+)', rest)
            if dm:
                num = int(dm.group(1))
                cycle = {'num': num} if 200 <= num <= 205 else None
                if cycle is None:
                    skipped += 1
                continue
            if re.match(r'\s*CALL\b', rest) and cycle is not None:
                x, y, z = _hh_drill(tp, cycle, x, y, z)
            elif re.match(r'\s*CALL\b', rest):
                skipped += 1
            continue
        nx, ny, nz = x, y, z
        for inc, axis, val in _HH_WORD.findall(rest):
            v = float(val.replace(' ', ''))
            ref = {'X': x, 'Y': y, 'Z': z}[axis] if inc else 0.0
            if cmd == 'CC':
                if axis == 'X':
                    cc = ((x if inc else 0.0) + v, cc[1])
                elif axis == 'Y':
                    cc = (cc[0], (y if inc else 0.0) + v)
                continue
            if axis == 'X':
                nx = ref + v
            elif axis == 'Y':
                ny = ref + v
            else:
                nz = ref + v
        if cmd == 'CC':
            continue
        fm = re.search(r'\bF\s*(\d+\.?\d*)', rest)
        if fm:
            feed = float(fm.group(1))
        if cmd == 'L':
            if 'FMAX' in rest:
                tp.moves.append(Move('rapid', nx, ny, nz))
            else:
                plunge = abs(nx - x) < 1e-9 and abs(ny - y) < 1e-9 and nz < z
                tp.moves.append(Move('plunge' if plunge else 'feed', nx, ny, nz))
            if (nx, ny) != (x, y):
                heading = (nx - x, ny - y)
            if re.search(r'\bM99\b', rest) and cycle is not None:     # appel du cycle à ce point
                x, y, z = nx, ny, nz
                x, y, z = _hh_drill(tp, cycle, x, y, z)
                continue
        elif cmd == 'CT':
            arc = _tangent_arc(x, y, nx, ny, heading)
            if arc is None:                              # pas de direction d'avant : droite
                tp.moves.append(Move('feed', nx, ny, nz))
            else:
                cw, center = arc
                tp.moves.append(Move('arc_cw' if cw else 'arc_ccw', nx, ny, nz, *center))
                ex, ey = nx - center[0], ny - center[1]
                heading = (ey, -ex) if cw else (-ey, ex)
        elif cmd in ('C', 'CR'):
            cw = 'DR-' in rest.replace(' ', '')
            if cmd == 'CR':
                rm = re.search(r'\bR\s*([-+]?\s*\d+\.?\d*)', rest)
                r = float(rm.group(1).replace(' ', '')) if rm else 0.0
                center = _center_from_r(x, y, nx, ny, r, cw)
            else:
                center = cc
            tp.moves.append(Move('arc_cw' if cw else 'arc_ccw', nx, ny, nz, *center))
            ex, ey = nx - center[0], ny - center[1]
            heading = (ey, -ex) if cw else (-ey, ex)
        x, y, z = nx, ny, nz
    tp.feeds.extend([feed] * (len(tp.moves) - len(tp.feeds)))
    if skipped:
        tp.warnings.append(f'programme Heidenhain : {skipped} cycle(s) ou arc(s) tangent(s) non suivi(s)')
    if not tp.moves:
        tp.warnings.append('programme Heidenhain : aucun mouvement lu')
    return tp


def _hh_drill(tp: Toolpath, cycle: dict, x: float, y: float, z: float):
    """Un trou du cycle Heidenhain 200–205 au point (x, y) : approche au-dessus
    de la surface (Q203 + Q204, puis + Q200), descente à la profondeur Q201,
    retour ; rend la position finale."""
    surface = cycle.get(203, 0.0)
    approach = abs(cycle.get(200, 2.0))
    clear = surface + max(approach, abs(cycle.get(204, 0.0)))
    bottom = surface - abs(cycle.get(201, 0.0))
    top = max(z, clear)
    tp.moves.append(Move('rapid', x, y, top))
    tp.moves.append(Move('rapid', x, y, surface + approach))
    tp.moves.append(Move('plunge', x, y, bottom))
    tp.moves.append(Move('rapid', x, y, clear))
    return x, y, clear


def _tangent_arc(x0, y0, x1, y1, heading):
    """(horaire ?, centre) de l'arc partant de (x0, y0) tangent à `heading`
    et finissant en (x1, y1) ; None si impossible (droite, pas de direction)."""
    if heading is None:
        return None
    hx, hy = heading
    hn = math.hypot(hx, hy)
    dx, dy = x1 - x0, y1 - y0
    if hn < 1e-12 or math.hypot(dx, dy) < 1e-12:
        return None
    hx, hy = hx / hn, hy / hn
    nx, ny = -hy, hx                                     # normale à gauche de la direction
    dn = dx * nx + dy * ny
    if abs(dn) < 1e-12:
        return None                                      # point dans l'axe : c'est une droite
    r = (dx * dx + dy * dy) / (2 * dn)                   # signé : > 0 centre à gauche (anti-horaire)
    return r < 0, (x0 + nx * r, y0 + ny * r)


def _center_from_r(x0, y0, x1, y1, r, cw: bool):
    """Centre d'un arc donné par son rayon R (R négatif : grand arc)."""
    dx, dy = x1 - x0, y1 - y0
    d = math.hypot(dx, dy)
    if d < 1e-12:
        return x0, y0
    rr = abs(r)
    h = math.sqrt(max(0.0, rr * rr - d * d / 4))
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    ux, uy = -dy / d, dx / d                               # à gauche de la corde
    left = (not cw) == (r > 0)                             # petit arc : centre à gauche si anti-horaire
    s = 1.0 if left else -1.0
    return mx + s * ux * h, my + s * uy * h
