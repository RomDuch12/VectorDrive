"""Bibliothèque d'outils : `tools.json`, et ce qu'on y importe.

Format (JSON, lisible) :

    {"format": "vectordrive-outils", "version": 1,
     "outils": [{"name": "Conique 30° 0,2", "kind": "conique", "diameter": 3.175,
                 "angle": 30, "tip": 0.2, "feed": 500, "spindle": 24000, …,
                 "geometry": {"D1": 0.2, "D2": 3.175, "L1": 38, "L2": 6, "angle": 30},
                 "catalog": {"fournisseur": "DATRON", "reference": "…", "url": "…",
                             "prix": 0, "devise": "EUR"},
                 "drawings": {"dxf": "…", "step": "…"}}]}

Un outil = `cam.model.CamTool` (avances, régimes, passes) + ses cotes de
fabricant (`geometry`), sa fiche de catalogue (`catalog`) et ses dessins
générés (`drawings`, voir `cam.tooldraw`).

Lecture et écriture, **mode de compatibilité** compris :

- `tools.json` de VectorDrive et de NeoDrive (même auteur ; avances
  `feed_finishing`, `feed_plunge`, `rpm`, fiche `geometry` de SimPl) ;
- bases d'outils TypeEdit `.Dbt` (`cam.tooldb`) : à l'export, seuls les
  champs que TypeEdit connaît passent — `compat_report` dit lesquels se
  perdent ;
- CSV (séparateur `;` ou `,`), en-têtes VectorDrive ou symboles ISO 13399 /
  DIN 4000 (DC, DCON, OAL, LU, APMX, NOF, SIG, RE) ;
- fichiers de données des fabricants (GTC / ISO 13399 en XML ou P21,
  archive .zip) : lecture des propriétés usuelles, **expérimentale**.
"""
from __future__ import annotations

import csv
import io
import json
import pathlib
import re
import zipfile
import zlib

from .model import CamTool, new_id

FORMAT = 'vectordrive-outils'
VERSION = 1

#: symboles ISO 13399 / DIN 4000 → (champ de l'outil ou de ses cotes)
ISO = {'DC': 'D1', 'DCON': 'D2', 'DN': 'D3', 'OAL': 'L1', 'LU': 'L3', 'APMX': 'L2', 'LF': 'L1',
       'NOF': 'dents', 'SIG': 'angle', 'RE': 'R', 'PL': 'pointe'}
#: en-têtes CSV de VectorDrive
CSV_FIELDS = ['name', 'kind', 'vendor', 'ref', 'number', 'diameter', 'tip', 'angle', 'flutes', 'cut_length',
              'spindle', 'feed', 'plunge', 'step_down', 'stepover', 'D1', 'D2', 'D3', 'L1', 'L2', 'L3', 'R',
              'prix', 'url', 'notes']
GEOMETRY = ('D1', 'D2', 'D3', 'L1', 'L2', 'L3', 'angle', 'R', 'dents', 'pas', 'famille', 'pointe')


class ToolLibError(ValueError):
    pass


#: fichier choisi dans les options (F10 > FAO) ; vide : celui du dossier des données
CHOSEN_PATH = ''


def default_path() -> pathlib.Path:
    """Bibliothèque de l'utilisateur : `VECTORDRIVE_TOOLS` (essais), sinon le
    fichier choisi dans les options, sinon `outils/tools.json` du dossier des
    données (portable compris)."""
    import os
    if os.environ.get('VECTORDRIVE_TOOLS'):
        return pathlib.Path(os.environ['VECTORDRIVE_TOOLS'])
    if CHOSEN_PATH.strip():
        return pathlib.Path(CHOSEN_PATH.strip())
    from ..portable import data_dir
    return data_dir() / 'outils' / 'tools.json'


# --- tools.json --------------------------------------------------------------------------

def to_json(tools: list[CamTool], folders=()) -> str:
    d = {'format': FORMAT, 'version': VERSION, 'outils': [t.to_dict() for t in tools]}
    if folders:
        d['dossiers'] = list(folders)                    # dossiers créés, même vides
    return json.dumps(d, ensure_ascii=False, indent=1)


def load_folders(path) -> list[str]:
    """Dossiers enregistrés à part dans un tools.json (créés, même vides)."""
    p = pathlib.Path(path)
    try:
        data = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    except (OSError, ValueError):
        return []
    v = data.get('dossiers') if isinstance(data, dict) else None
    return [str(x) for x in v if str(x).strip()] if isinstance(v, list) else []


def save(tools: list[CamTool], path, folders=None) -> pathlib.Path:
    """`folders` : dossiers à garder même vides (None : ceux déjà dans le fichier)."""
    p = pathlib.Path(path)
    if folders is None:
        folders = load_folders(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(to_json(tools, folders), encoding='utf-8')
    tmp.replace(p)
    return p


def from_json(text: str) -> list[CamTool]:
    data = json.loads(text)
    if isinstance(data, dict) and data.get('format') == FORMAT:
        return [CamTool.from_dict(d) for d in data.get('outils', [])]
    if isinstance(data, dict) and isinstance(data.get('tools'), list):          # réglage FAO exporté
        return [CamTool.from_dict(d) for d in data['tools']]
    if isinstance(data, dict) and isinstance(data.get('tools'), dict):          # tools.json de NeoDrive (v3)
        return [from_neodrive(k, v) for k, v in data['tools'].items() if isinstance(v, dict)]
    if isinstance(data, dict) and data and all(isinstance(v, dict) and 'name' in v for v in data.values()):
        return [from_neodrive(k, v) for k, v in data.items()]                   # tools.json de NeoDrive
    if isinstance(data, list):
        return [CamTool.from_dict(d) for d in data if isinstance(d, dict)]
    raise ToolLibError('fichier d\'outils non reconnu')


def load(path) -> list[CamTool]:
    p = pathlib.Path(path)
    if not p.exists():
        return []
    return from_json(p.read_text(encoding='utf-8'))


# --- NeoDrive ---------------------------------------------------------------------------------

def _num(v, d=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def from_neodrive(key: str, d: dict) -> CamTool:
    """Outil d'un tools.json de NeoDrive."""
    g = dict(d.get('geometry') or {})
    name = str(d.get('name') or key)
    low = name.lower()
    angle = _num(g.get('TipAngle'))
    tipd = _num(g.get('TipDiameter'))
    dia = _num(d.get('diameter')) or _num(g.get('Diameter'))
    if low.startswith(('con', 'grav', 'v ')) or (angle and tipd and tipd < dia):
        kind = 'conique'
    elif low.startswith(('boule', 'ball', 'sph')) or _num(g.get('CornerRadius')) >= dia / 2 > 0:
        kind = 'boule'
    elif low.startswith(('foret', 'drill', 'forêt')):
        kind = 'foret'
    else:
        kind = 'fraise'
    dessins = dict(d.get('dessins') or {})
    cotes = dict(dessins.get('cotes') or {})
    geometry = {k: cotes[k] for k in GEOMETRY if k in cotes}
    if dessins.get('famille'):
        geometry.setdefault('famille', dessins['famille'])
    ref = str(d.get('reference') or d.get('article_nr') or '')
    return CamTool(
        name=name, kind=kind, diameter=dia or 1.0, tip=tipd if kind == 'conique' else 0.0,
        angle=angle if kind in ('conique', 'foret') else 0.0, flutes=int(_num(g.get('NumberOfFlutes'), 1) or 1),
        cut_length=_num(g.get('FluteLength')) or _num(d.get('max_depth'), 3.0), ref=ref.split(' / ')[0],
        vendor=str(d.get('vendor') or ''), spindle=_num(d.get('rpm'), 20000.0),
        feed=_num(d.get('feed_finishing')) or _num(d.get('feed_roughing'), 600.0),
        plunge=_num(d.get('feed_plunge'), 200.0), ramp_feed=_num(d.get('feed_ramp')),
        step_down=_num(d.get('max_depth')) and min(_num(d.get('max_depth')), 1.0) or 0.2,
        notes=str(d.get('notes') or ''), geometry=geometry,
        catalog={'fournisseur': str(d.get('vendor') or ''), 'reference': ref, 'cle_neodrive': key},
        drawings={k: dessins[k] for k in ('dxf', 'step') if dessins.get(k)})


def to_neodrive(t: CamTool) -> tuple[str, dict]:
    """(clé, fiche) au format tools.json de NeoDrive."""
    key = re.sub(r'[^a-z0-9]+', '_', f'{t.vendor} {t.name}'.lower()).strip('_') or t.id
    g = {'Diameter': t.diameter, 'TipAngle': t.angle if t.kind in ('conique', 'foret') else 0.0,
         'TipDiameter': t.tip if t.kind == 'conique' else t.diameter, 'NumberOfFlutes': t.flutes,
         'FluteLength': t.cut_length}
    return key, {'name': t.name, 'reference': t.ref, 'rpm': t.spindle, 'feed_finishing': t.feed,
                 'feed_roughing': t.feed, 'feed_plunge': t.plunge, 'feed_ramp': t.ramp_feed or t.plunge,
                 'diameter': t.diameter, 'vendor': t.vendor, 'max_depth': t.cut_length, 'notes': t.notes,
                 'geometry': g}


# --- TypeEdit (.Dbt), mode de compatibilité ------------------------------------------------------

#: ce qu'une base TypeEdit garde d'un outil
DBT_KEEPS = {'name', 'kind', 'number', 'diameter', 'angle', 'tip', 'ref', 'vendor', 'spindle', 'feed', 'plunge',
             'ramp_feed', 'step_down', 'flutes'}


def compat_report(tools: list[CamTool]) -> list[str]:
    """Ce qui ne passe pas dans une base TypeEdit (.Dbt)."""
    out = []
    for t in tools:
        lost = []
        if t.geometry:
            lost.append('cotes du fabricant')
        if t.catalog.get('prix') or t.catalog.get('url'):
            lost.append('fiche de catalogue')
        if t.drawings:
            lost.append('dessins')
        if t.kind == 'boule':
            lost.append('forme boule (écrite en fraise)')
        if t.kind == 'foret':
            lost.append('nature foret (écrite en fraise)')
        if t.cut_length and t.kind != 'laser':
            lost.append('longueur utile')
        if t.power or t.frequency:
            lost.append('réglages laser')
        if lost:
            out.append(f'{t.name} : {", ".join(lost)}')
    return out


def read_dbt(path) -> tuple[list[CamTool], list[str]]:
    from . import tooldb
    entries = tooldb.read(path)
    tools, notes = [], []
    for e in entries:
        t = CamTool.from_dict(e.tool.to_dict())
        t.id = new_id()
        t.catalog = {**t.catalog, 'dossier_typeedit': '/'.join(e.path)}
        tools.append(t)
        notes += e.notes
    return tools, sorted(set(notes))


def write_dbt(tools: list[CamTool], path, folder: str = 'VectorDrive') -> list[str]:
    from . import tooldb
    pathlib.Path(path).write_bytes(tooldb.write_bytes(list(tools), folder))
    return compat_report(tools)


# --- CSV ---------------------------------------------------------------------------------------

def to_csv(tools: list[CamTool]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_FIELDS, delimiter=';', extrasaction='ignore')
    w.writeheader()
    for t in tools:
        row = {k: getattr(t, k) for k in CSV_FIELDS if hasattr(t, k)}
        row.update({k: t.geometry.get(k, '') for k in ('D1', 'D2', 'D3', 'L1', 'L2', 'L3', 'R')})
        row.update(prix=t.catalog.get('prix', ''), url=t.catalog.get('url', ''))
        w.writerow(row)
    return buf.getvalue()


def from_csv(text: str) -> list[CamTool]:
    sample = text[:4096]
    delim = ';' if sample.count(';') >= sample.count(',') else ','
    out = []
    for row in csv.DictReader(io.StringIO(text), delimiter=delim):
        # ligne plus longue que l'en-tête : le surplus (clé None, liste) est ignoré
        row = {k.strip(): (v or '').strip() for k, v in row.items() if isinstance(k, str) and not isinstance(v, list)}
        out.append(_tool_from_props(row))
    return out


def _tool_from_props(props: dict) -> CamTool:
    """Outil d'après des propriétés nommées (en-têtes VectorDrive ou symboles ISO 13399)."""
    up = {k.upper(): v for k, v in props.items()}
    t = CamTool(name=props.get('name') or props.get('nom') or up.get('ORDERING_CODE') or up.get('NAME') or 'Outil')
    for f in ('kind', 'vendor', 'ref', 'notes'):
        if props.get(f):
            setattr(t, f, props[f])
    for f in ('number', 'flutes'):
        if props.get(f):
            setattr(t, f, int(_num(props[f], getattr(t, f))))
    for f in ('diameter', 'tip', 'angle', 'cut_length', 'spindle', 'feed', 'plunge', 'step_down', 'stepover'):
        if props.get(f):
            setattr(t, f, _num(props[f], getattr(t, f)))
    geo = {}
    for k in ('D1', 'D2', 'D3', 'L1', 'L2', 'L3', 'R'):
        if props.get(k):
            geo[k] = _num(props[k])
    for sym, k in ISO.items():
        if up.get(sym) not in (None, ''):
            geo.setdefault(k, _num(up[sym]))
    if geo:
        t.geometry = geo
        if 'D1' in geo and not props.get('diameter'):
            t.diameter = geo['D1']
        if 'L2' in geo and not props.get('cut_length'):
            t.cut_length = geo['L2']
        if 'dents' in geo and not props.get('flutes'):
            t.flutes = int(geo['dents']) or t.flutes
        if 'angle' in geo and not props.get('angle'):
            t.angle = geo['angle']
        if not props.get('kind'):
            r = geo.get('R', 0.0)
            if r and abs(r - t.diameter / 2) < 1e-6:
                t.kind = 'boule'
            elif geo.get('angle') and geo['angle'] < 120 and t.diameter <= 12:
                t.kind = 'conique'
    cat = {k: props[k] for k in ('prix', 'url') if props.get(k)}
    if t.vendor or t.ref:
        cat.update(fournisseur=t.vendor, reference=t.ref)
    t.catalog = cat
    return t


# --- données des fabricants (GTC / ISO 13399), expérimental ------------------------------------------

_P21_PROP = re.compile(r"'(DC|DCON|DN|OAL|LU|APMX|LF|NOF|SIG|RE|PL)'[^;]{0,200}?\(\s*(-?\d+(?:\.\d*)?(?:E[-+]?\d+)?)",
                       re.I)
_XML_PROP = re.compile(r'(?:symbol|name|code|id)\s*=\s*"(DC|DCON|DN|OAL|LU|APMX|LF|NOF|SIG|RE|PL)"[^>]*>'
                       r'(?:\s*<[^>]+>)*\s*(-?\d+(?:[.,]\d+)?)', re.I)
_XML_PAIR = re.compile(r'<(DC|DCON|DN|OAL|LU|APMX|LF|NOF|SIG|RE|PL)>\s*(-?\d+(?:[.,]\d+)?)\s*</', re.I)


def iso13399_props(text: str) -> dict:
    """Symboles ISO 13399 trouvés dans un fichier de données (XML ou P21)."""
    props = {}
    for rx in (_P21_PROP, _XML_PROP, _XML_PAIR):
        for m in rx.finditer(text):
            props.setdefault(m.group(1).upper(), m.group(2).replace(',', '.'))
    m = re.search(r'(?:ORDERING.?CODE|ORDER.?CODE|PRODUCT_ID|ARTICLE)[^A-Za-z0-9]{1,40}([A-Za-z0-9][\w./ -]{2,40})',
                  text, re.I)
    if m:
        props['ref'] = m.group(1).strip()
    return props


def read_manufacturer(path, vendor: str = '') -> list[CamTool]:
    """Outils d'un fichier de fabricant (.xml, .p21, .stp, .zip GTC)."""
    p = pathlib.Path(path)
    texts = []
    if p.suffix.lower() == '.zip':
        try:
            with zipfile.ZipFile(p) as z:
                for n in z.namelist():
                    if n.lower().endswith(('.xml', '.p21', '.stp', '.step')):
                        texts.append((n, z.read(n).decode('utf-8', 'replace')))
        except (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError) as ex:
            raise ToolLibError(f'archive endommagée : {p.name} ({ex})') from ex
    else:
        texts.append((p.name, p.read_text(encoding='utf-8', errors='replace')))
    out = []
    for name, text in texts:
        props = iso13399_props(text)
        if 'DC' not in props:
            continue
        props.setdefault('name', pathlib.Path(name).stem)
        if vendor:
            props['vendor'] = vendor
        out.append(_tool_from_props(props))
    return out


# --- import / export, toutes sortes ------------------------------------------------------------------

IMPORT_FILTER = ('Outils (*.json *.Dbt *.dbt *.csv *.xml *.p21 *.stp *.step *.zip);;'
                 'Bibliothèque VectorDrive ou NeoDrive (*.json);;Base TypeEdit (*.Dbt *.dbt);;CSV (*.csv);;'
                 'Données fabricant GTC / ISO 13399 (*.xml *.p21 *.stp *.step *.zip)')
EXPORT_FILTER = ('Bibliothèque VectorDrive (*.json);;Base TypeEdit, mode de compatibilité (*.Dbt);;'
                 'CSV (*.csv);;tools.json de NeoDrive (*.neodrive.json)')
#: fichiers lus par l'import d'un dossier entier
IMPORT_EXTS = ('.json', '.dbt', '.dbtsav', '.csv', '.xml', '.p21', '.stp', '.step', '.zip')


def import_file(path) -> tuple[list[CamTool], list[str]]:
    """Outils d'un fichier (format d'après l'extension) et remarques."""
    p = pathlib.Path(path)
    ext = p.suffix.lower()
    if ext in ('.dbt', '.dbtsav'):
        return read_dbt(p)
    if ext == '.csv':
        return from_csv(p.read_text(encoding='utf-8-sig', errors='replace')), []
    if ext == '.json':
        return from_json(p.read_text(encoding='utf-8')), []
    if ext in ('.xml', '.p21', '.stp', '.step', '.zip'):
        tools = read_manufacturer(p)
        return tools, ([] if tools else ['aucune propriété ISO 13399 (DC, OAL…) reconnue dans ce fichier'])
    raise ToolLibError(f'format non reconnu : {p.suffix}')


def export_file(tools: list[CamTool], path) -> list[str]:
    """Écrit les outils (format d'après le nom) ; rend les remarques (pertes)."""
    p = pathlib.Path(path)
    name = p.name.lower()
    if name.endswith('.neodrive.json'):
        fiches = {}
        for t in tools:
            key, fiche = to_neodrive(t)
            k, n = key, 2
            while k in fiches:                       # deux outils de même nom : clés distinctes
                k, n = f'{key}_{n}', n + 1
            fiches[k] = fiche
        p.write_text(json.dumps({'version': '3.1', 'tools': fiches},
                                ensure_ascii=False, indent=1),
                     encoding='utf-8')
        return []
    if name.endswith('.dbt'):
        return write_dbt(tools, p)
    if name.endswith('.csv'):
        p.write_text(to_csv(tools), encoding='utf-8-sig')
        return []
    save(tools, p)
    return []


# --- dossiers de « Mes outils » --------------------------------------------------------------
#: dossier des outils qui n'en ont pas
NO_FOLDER = 'Mes outils'


def folder_of(t: CamTool) -> str:
    return (t.folder or '').strip() or NO_FOLDER


def folders(tools: list[CamTool]) -> list[str]:
    """Dossiers, dans l'ordre d'apparition."""
    out: list[str] = []
    for t in tools:
        f = folder_of(t)
        if f not in out:
            out.append(f)
    return out


def unique_folder(name: str, tools: list[CamTool]) -> str:
    """Nom de dossier libre : un import distinct reste un dossier distinct."""
    base = (name or '').strip() or NO_FOLDER
    have = set(folders(tools))
    if base not in have:
        return base
    i = 2
    while f'{base} ({i})' in have:
        i += 1
    return f'{base} ({i})'


def set_folder(tools: list[CamTool], name: str) -> None:
    v = SEP.join(p.strip() for p in (name or '').split(SEP) if p.strip())
    for t in tools:
        t.folder = '' if v == NO_FOLDER else v


#: séparateur des sous-dossiers (« Datron/Fraises »)
SEP = '/'


def folder_parts(name: str) -> list[str]:
    """« Datron / Fraises » → ['Datron', 'Fraises']."""
    return [p.strip() for p in (name or '').split(SEP) if p.strip()]


def join_folder(*parts: str) -> str:
    return SEP.join(p for part in parts for p in folder_parts(part))


def in_folder(t: CamTool, name: str) -> bool:
    """Outil du dossier `name` ou d'un de ses sous-dossiers."""
    f = folder_of(t)
    return f == name or f.startswith(name + SEP)


def rename_folder(tools: list[CamTool], old: str, new: str) -> int:
    """Renomme (ou, vers un dossier existant, fusionne) un dossier et ses
    sous-dossiers ; rend le nombre d'outils déplacés."""
    moved = 0
    for t in tools:
        f = folder_of(t)
        if f == old:
            set_folder([t], new)
            moved += 1
        elif f.startswith(old + SEP):
            set_folder([t], join_folder(new, f[len(old) + 1:]))
            moved += 1
    return moved


merge_folders = rename_folder


def delete_folder(tools: list[CamTool], name: str) -> list[CamTool]:
    """Outils restants, sans ceux du dossier (sous-dossiers compris)."""
    return [t for t in tools if not in_folder(t, name)]


def place(tools: list[CamTool], moving: list[CamTool], folder: str | None = None,
          before: CamTool | None = None) -> None:
    """Outils `moving` rangés dans `folder` (s'il est donné) et placés,
    dans l'ordre, juste avant `before` (sinon après le dernier outil de
    leur dossier) — glisser-déposer, réordonner. En place."""
    ids = {id(t) for t in moving}
    rest = [t for t in tools if id(t) not in ids]
    if folder is not None:
        set_folder(moving, folder)
    if before is not None and id(before) not in ids and before in rest:
        i = rest.index(before)
    else:
        f = folder_of(moving[0]) if moving else NO_FOLDER
        last = [k for k, t in enumerate(rest) if folder_of(t) == f]
        i = last[-1] + 1 if last else len(rest)
    tools[:] = rest[:i] + list(moving) + rest[i:]


def shift(tools: list[CamTool], moving: list[CamTool], d: int) -> bool:
    """Monte (d < 0) ou descend (d > 0) les outils `moving` d'un rang
    parmi les outils de leur dossier ; False si rien ne bouge."""
    ids = {id(t) for t in moving}
    order = list(range(len(tools)))
    seq = order if d < 0 else order[::-1]
    moved = False
    for k in seq:
        t = tools[k]
        if id(t) not in ids:
            continue
        f = folder_of(t)
        nb = range(k - 1, -1, -1) if d < 0 else range(k + 1, len(tools))
        j = next((x for x in nb if folder_of(tools[x]) == f), None)
        if j is None or id(tools[j]) in ids:
            continue
        tools[k], tools[j] = tools[j], tools[k]
        moved = True
    return moved


def import_tree(root, *, prefix: str = '') -> tuple[dict, list[str], list[str]]:
    """Import en lot d'un dossier et de ses sous-dossiers : chaque fichier
    d'outils devient un dossier de Mes outils nommé d'après son chemin
    (« Datron/fraises » pour Datron\\fraises.csv), les dossiers d'une base
    TypeEdit en sous-dossiers. Rend ({dossier: [outils]}, remarques,
    erreurs) ; rien n'est enregistré."""
    root = pathlib.Path(root)
    out: dict[str, list[CamTool]] = {}
    notes: list[str] = []
    errors: list[str] = []
    files = sorted((p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in IMPORT_EXTS),
                   key=lambda p: [s.lower() for s in p.relative_to(root).parts])
    for f in files:
        rel = f.relative_to(root)
        if f.name.startswith(('~', '.')):
            continue                                 # verrous d'Office, fichiers cachés
        try:
            tools, n = import_file(f)
        except Exception as ex:                      # un fichier illisible n'arrête pas le lot
            errors.append(f'{rel} : {ex}')
            continue
        if not tools:
            if n:
                notes += [f'{rel} : {x}' for x in n]
            continue
        base = join_folder(prefix, *rel.parent.parts, f.stem)
        for t in tools:
            sub = str(t.catalog.get('dossier_typeedit') or '') if f.suffix.lower() in ('.dbt', '.dbtsav') else ''
            name = join_folder(base, sub) if sub else base
            t.id = new_id()
            t.folder = name
            out.setdefault(name, []).append(t)
        notes += [f'{rel} : {x}' for x in n]
    return out, notes, errors


def add_folders(lib: list[CamTool], imported: dict, *, replace: bool = False) -> tuple[int, list[str]]:
    """Verse un import en lot dans `lib` (en place) : un dossier déjà présent
    est remplacé (`replace`) ou reçoit un nom libre (« … (2) »). Rend le
    nombre d'outils ajoutés et les dossiers créés ou remplacés."""
    added, names = 0, []
    for name, tools in imported.items():
        if replace:
            lib[:] = [t for t in lib if folder_of(t) != name]
            target = name
        else:
            target = unique_folder(name, lib)
        for t in tools:
            t.folder = target
        lib.extend(tools)
        added += len(tools)
        names.append(target)
    return added, names


def _norm_name(s: str) -> str:
    return re.sub(r'[\s_]+', ' ', str(s or '')).strip().lower()


def same_tool(a: CamTool, b: CamTool) -> bool:
    """Deux fiches du même outil : même référence chez le même fabricant, ou
    même nom, même nature et mêmes cotes (Ø, angle, pointe à 1 µm près)."""
    if a.ref.strip() and b.ref.strip():
        if a.ref.strip().lower() == b.ref.strip().lower() and (
                not a.vendor or not b.vendor or a.vendor.strip().lower() == b.vendor.strip().lower()):
            return True
    return (a.kind == b.kind and abs(a.diameter - b.diameter) < 1e-3 and abs(a.angle - b.angle) < 1e-3
            and abs(a.tip - b.tip) < 1e-3 and _norm_name(a.name) == _norm_name(b.name))


def find_duplicate(t: CamTool, tools: list[CamTool]) -> CamTool | None:
    return next((x for x in tools if x is not t and same_tool(t, x)), None)


def import_files(paths, *, prefix: str = '') -> tuple[dict, list[str], list[str]]:
    """Comme `import_tree`, pour des fichiers choisis : chacun en dossier
    nommé d'après lui, les dossiers d'une base TypeEdit dessous. Rien n'est
    enregistré."""
    out: dict[str, list[CamTool]] = {}
    notes: list[str] = []
    errors: list[str] = []
    for f in map(pathlib.Path, paths):
        try:
            tools, n = import_file(f)
        except Exception as ex:                      # un fichier illisible n'arrête pas le lot
            errors.append(f'{f.name} : {ex}')
            continue
        base = join_folder(prefix, f.stem)
        for t in tools:
            sub = str(t.catalog.get('dossier_typeedit') or '') if f.suffix.lower() in ('.dbt', '.dbtsav') else ''
            name = join_folder(base, sub) if sub else base
            t.id = new_id()
            t.folder = name
            out.setdefault(name, []).append(t)
        notes += [f'{f.name} : {x}' for x in n]
    return out, notes, errors


def library(path=None) -> list[CamTool]:
    """Mes outils (pour le panneau FAO) ; illisible : aucun."""
    try:
        return load(path or default_path())
    except (OSError, ValueError):
        return []


# --- familles (classement des listes d'outils, demande du 15/11) ----------------------------------------------------
#: famille → dossier des listes d'outils, dans leur ordre : Cylindriques (› Cyl 3, Cyl 4…), Coniques (› Con 90,
#: Con 45…), Boules, Chamfer, Thread, Ext-Rad, T-slot, Drill, puis les autres
FAMILIES = (('fraise', 'Cylindriques'), ('conique', 'Coniques'), ('boule', 'Boules'), ('chanfrein', 'Chamfer'),
            ('filetage', 'Thread'), ('rayon', 'Ext-Rad'), ('tslot', 'T-slot'), ('foret', 'Drill'),
            ('torique', 'Toriques'), ('surfacage', 'Surfaçage'), ('laser', 'Laser'), ('couteau', 'Couteaux'),
            ('profil', 'Profils'))
_FAMILY = dict(FAMILIES)
#: sous-dossier d'une famille : « Cyl 3 » (Ø), « Con 90 » (angle)
_SUB = re.compile(r'(Cyl|Con) (\d+(?:\.\d+)?)')


def family(t) -> str:
    """Famille d'un outil : celle de ses cotes ou de sa fiche (« chanfrein », « filetage »…), sinon sa nature."""
    for d in (getattr(t, 'geometry', None), getattr(t, 'catalog', None)):
        f = str((d or {}).get('famille') or '').strip().lower()
        if f in _FAMILY:
            return f
    k = str(getattr(t, 'kind', '') or 'fraise')
    return k if k in _FAMILY else 'fraise'


def _short(v) -> str:
    return f'{round(float(v or 0), 3):g}'


def family_path(t) -> list[str]:
    """Dossiers d'un outil classé par famille : ['Cylindriques', 'Cyl 3'] (par Ø), ['Coniques', 'Con 90'] (par angle),
    ['Boules'], ['Chamfer']… (libellés traduits)."""
    from ..i18n import tr
    f = family(t)
    top = tr(_FAMILY[f])
    if f == 'fraise' and float(getattr(t, 'diameter', 0) or 0) > 0:
        return [top, 'Cyl ' + _short(t.diameter)]
    if f == 'conique' and float(getattr(t, 'angle', 0) or 0) > 0:
        return [top, 'Con ' + _short(t.angle)]
    return [top]


_RANKS: dict = {}


def _family_rank() -> dict:
    """Rang de chaque famille par son libellé traduit, calculé une fois par langue (tri d'une longue liste)."""
    from ..i18n import tr
    lang = tr(FAMILIES[0][1])
    got = _RANKS.get(lang)
    if got is None:
        got = _RANKS[lang] = {tr(label): i for i, (_k, label) in enumerate(FAMILIES)}
    return got


def folder_sort_key(name: str) -> tuple:
    """Clé de tri d'un dossier : les familles dans leur ordre (`FAMILIES`), « Cyl » par Ø croissant, « Con » par angle
    décroissant (Con 90, Con 45, Con 30…), les autres dossiers par nom (sans casse)."""
    rank = _family_rank()
    out = []
    for part in folder_parts(name):
        m = _SUB.fullmatch(part)
        if m:
            v = float(m.group(2))
            out.append((0, -v if m.group(1) == 'Con' else v, ''))
        elif part in rank:
            out.append((0, float(rank[part]), ''))
        else:
            out.append((1, 0.0, part.casefold()))
    return tuple(out)


def favorite_key(t: CamTool) -> str:
    """Clé d'un outil favori (`ui.tool_favorites`) : sa référence, sinon son nom, sa nature et ses cotes — la même pour
    l'outil d'une bibliothèque et ses copies (Mes outils, le document), comme `find_match`."""
    ref = str(t.ref or '').strip().lower()
    if ref:
        return 'ref:' + ref
    return 'outil:{0}|{1}|{2}|{3}|{4}'.format(str(t.name or '').strip().lower(), t.kind, _short(t.diameter),
                                             _short(t.angle), _short(t.tip))


def with_plugins(mine=None, sources: dict | None = None) -> list[CamTool]:
    """« Choisir un outil » : Mes outils (`mine`, sinon `library()`), puis les outils des bibliothèques des plugins (les
    outils DATRON de l'atelier…), dans l'ordre. Un outil déjà vu (même référence, sinon même nom, même nature et mêmes
    cotes : `find_match`) n'y est qu'une fois ; ceux d'un plugin sont des copies, rangées sous le nom de leur
    bibliothèque puis par famille (`family_path` : « Datron/Cylindriques/Cyl 3 »). Une bibliothèque en défaut est
    sautée. `sources` reçoit id → nom de la bibliothèque."""
    from ..plugins import REGISTRY
    out = list(library() if mine is None else mine)
    if sources is not None:
        sources.update({t.id: 'Mes outils' for t in out})
    ids = {t.id for t in out}
    for name, loader in list(REGISTRY.tool_libraries.items()):
        try:
            tools = list(loader() or [])
        except Exception:                                  # bibliothèque d'un plugin en défaut : la suivante
            continue
        for t in tools:
            try:
                if find_match(t, out) is not None:
                    continue
                c = CamTool.from_dict(t.to_dict())
            except Exception:                              # outil illisible : le suivant
                continue
            parts = folder_parts(c.folder)
            if not parts or parts[0].casefold() != str(name).strip().casefold():
                parts = [str(name), *parts]
            c.plugin_folder = join_folder(*parts)        # son dossier dans le plugin : les règles « dossier » d'avant
            c.folder = join_folder(str(name), *family_path(c))     # classés par famille (demande du 15/11)
            if not c.id or c.id in ids:
                c.id = new_id()
            ids.add(c.id)
            out.append(c)
            if sources is not None:
                sources[c.id] = name
    return out


def matches(t: CamTool, text: str = '', kind: str = '', dmin: float = 0.0, dmax: float = 0.0,
            vendor: str = '') -> bool:
    """Filtres du gestionnaire et de « Choisir un outil » : texte (nom,
    référence, fabricant, Ø, n° T, dossier), nature, plage de Ø (0 : sans
    borne), fabricant."""
    q = (text or '').strip().lower()
    if q and q not in f'{t.name} {t.ref} {t.vendor} {t.diameter:g} T{t.number} {folder_of(t)}'.lower():
        return False
    if kind and t.kind != kind:
        return False
    if dmin and t.diameter < dmin - 1e-9:
        return False
    if dmax and t.diameter > dmax + 1e-9:
        return False
    return not vendor or t.vendor.strip().lower() == vendor.strip().lower()


def for_machine(t: CamTool, machine: str) -> bool:
    """L'outil sert-il sur cette machine (clé de post-processeur) ? Un outil
    sans machine désignée sert partout ; pas de machine : tous."""
    ms = [str(m) for m in (getattr(t, 'machines', None) or []) if str(m)]
    return not machine or not ms or machine in ms


def find_match(t: CamTool, library) -> CamTool | None:
    """L'outil de Mes outils qui est `t` : même référence, sinon même nom,
    même nature et mêmes cotes (Ø, angle, pointe) ; None : absent."""
    ref = str(t.ref or '').strip().lower()
    if ref:
        hit = next((x for x in library if str(x.ref or '').strip().lower() == ref), None)
        if hit is not None:
            return hit
    name = str(t.name or '').strip().lower()
    return next((x for x in library if str(x.name or '').strip().lower() == name and x.kind == t.kind
                 and abs(x.diameter - t.diameter) < 0.005 and abs((x.angle or 0) - (t.angle or 0)) < 0.05
                 and abs((x.tip or 0) - (t.tip or 0)) < 0.005), None)


def specs(t: CamTool) -> str:
    """Cotes qui distinguent l'outil : « Ø2 30° pointe 0,2 L4 Z2 »."""
    parts = [f'Ø{t.diameter:g}']
    if t.kind == 'conique' or t.angle:
        if t.angle:
            parts.append(f'{t.angle:g}°')
        if t.tip:
            parts.append(f'pointe {t.tip:g}')
    if t.cut_length:
        parts.append(f'L{t.cut_length:g}')
    if t.flutes and t.flutes > 1:
        parts.append(f'Z{t.flutes}')
    return ' '.join(parts)


def short_label(t: CamTool) -> str:
    """Libellé d'une ligne : « T12 Fraise 2 — Ø2 L4 Z2 »."""
    return f'T{t.number} {t.name} — {specs(t)}'


def summary(t: CamTool, machine_labels: dict | None = None) -> str:
    """Fiche de l'outil en quelques lignes (infobulles, choix d'un outil)."""
    from .model import TOOL_KINDS
    lines = [f'T{t.number}  {t.name}', f'{TOOL_KINDS.get(t.kind, t.kind)} — {specs(t)}']
    if t.vendor or t.ref:
        lines.append(f'{t.vendor} {t.ref}'.strip())
    if t.spindle or t.feed:
        lines.append(f'{t.spindle:g} tr/min — avance {t.feed:g} — plongée {t.plunge:g} mm/min')
    if folder_of(t) and folder_of(t) != 'Mes outils':
        lines.append(f'Dossier : {folder_of(t)}')
    ms = [str(m) for m in (getattr(t, 'machines', None) or []) if str(m)]
    labels = machine_labels or {}
    lines.append('Machines : ' + (', '.join(labels.get(m, m) for m in ms) if ms else 'toutes'))
    if t.notes:
        lines.append(t.notes.strip().splitlines()[0][:80])
    return '\n'.join(lines)


def vendors(tools: list[CamTool]) -> list[str]:
    """Fabricants présents, triés (sans doublon de casse)."""
    seen: dict[str, str] = {}
    for t in tools:
        v = t.vendor.strip()
        if v:
            seen.setdefault(v.lower(), v)
    return sorted(seen.values(), key=str.lower)
