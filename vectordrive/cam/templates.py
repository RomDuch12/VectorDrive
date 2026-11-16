"""Modèles d'usinage : un jeu d'outils et d'opérations enregistré sous un
nom, appliqué d'un clic à un autre dessin — une gamme de gravure, une
recette laser, le réglage habituel d'une pièce.

Modèles de l'utilisateur : fichiers JSON du dossier `modeles_fao` des
données (`VECTORDRIVE_CAM_TEMPLATES` pour les essais). Ceux des plugins :
`api.add_templates('fao', {nom: modèle})`.

Un modèle :

    {"name": "…", "description": "…", "tools": [CamTool…],
     "operations": [Operation…], "post": "", "machine": ""}

Ses opérations désignent ses outils par leur `id` ; à l'application, un
outil du modèle est retrouvé dans le réglage du document (même numéro et
même nature, à 0,01 mm près sur le diamètre ; sinon même nom, même nature
et même taille : diamètre, ou angle et pointe d'un cône), ou ajouté.
Version 2 : les reprises de gamme sont liées au parcours précédent ; celles
des modèles d'avant le sont à leur application.
Les opérations reçoivent de nouveaux identifiants ; leurs couleurs
(`sources`) sont celles du modèle, ou celles choisies à l'application.
"""
from __future__ import annotations

import copy
import json
import os
import pathlib
import re

from . import model

KIND = 'fao'
#: version des modèles écrits : 2, reprises de gamme liées au parcours précédent (choix de l'utilisateur gardé)
VERSION = 2


def _version(tpl: dict) -> int:
    try:
        return int(tpl.get('version', 1) or 1)
    except (TypeError, ValueError):
        return 1


def from_setup(setup: model.CamSetup, name: str, description: str = '') -> dict:
    """Modèle tiré d'un réglage (outils utilisés par les opérations seulement)."""
    used = {o.tool_id for o in setup.operations} | {o.ref_tool_id for o in setup.operations}
    tools = [t.to_dict() for t in setup.tools if t.id in used] or [t.to_dict() for t in setup.tools]
    for td in tools:
        td.pop('history', None)                  # historique des vitesses : propre au poste
    ops = []
    from ..core import surface2d
    for o in setup.operations:
        d = surface2d.strip(o.to_dict())         # surface posée d'un dessin : sans objet ailleurs
        d['items'] = []                          # objets d'un dessin : sans objet ailleurs
        d.pop('body3d_ref', None)                # volume d'un dessin : idem
        ops.append(d)
    return {'format': 'vectordrive-modele-fao', 'version': VERSION, 'name': name, 'description': description,
            'tools': tools, 'operations': ops, 'post': setup.post, 'machine': setup.machine}


# --- fichiers ------------------------------------------------------------------------------------
def user_dir() -> pathlib.Path:
    env = os.environ.get('VECTORDRIVE_CAM_TEMPLATES')
    if env:
        return pathlib.Path(env)
    from ..portable import data_dir
    return data_dir() / 'modeles_fao'


def _file(name: str) -> pathlib.Path:
    stem = re.sub(r'[^\w.-]+', '_', name, flags=re.UNICODE).strip('_') or 'modele'
    return user_dir() / f'{stem}.json'


def save_user(tpl: dict) -> pathlib.Path:
    f = _file(tpl['name'])
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(tpl, ensure_ascii=False, indent=1), encoding='utf-8')
    return f


def delete_user(name: str) -> bool:
    f = _file(name)
    if f.is_file():
        f.unlink()
        return True
    return False


def user_templates() -> dict[str, dict]:
    out = {}
    d = user_dir()
    if d.is_dir():
        for f in sorted(d.glob('*.json')):
            try:
                t = json.loads(f.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            if isinstance(t, dict) and t.get('name') and isinstance(t.get('operations'), list):
                out[str(t['name'])] = t
    return out


def plugin_templates() -> dict[str, dict]:
    from ..plugins import REGISTRY
    out = {}
    for name, t in (REGISTRY.templates.get(KIND) or {}).items():
        if isinstance(t, dict):
            t = dict(t)
            t.setdefault('name', name)
            out[name] = t
    return out


def all_templates() -> dict[str, tuple[str, dict]]:
    """{nom: (origine, modèle)} : ceux des plugins, puis ceux de
    l'utilisateur (qui l'emportent à nom égal)."""
    out = {n: ('plugin', t) for n, t in plugin_templates().items()}
    out.update({n: ('utilisateur', t) for n, t in user_templates().items()})
    return out


# --- dossiers des modèles de l'utilisateur ---------------------------------------------------------
def label_of(tpl: dict) -> str:
    """Nom du modèle sans son dossier."""
    name, folder = str(tpl.get('name') or ''), str(tpl.get('dossier') or '')
    return name[len(folder) + 3:] if folder and name.startswith(folder + ' / ') else name


def folder_parts(folder: str) -> list[str]:
    return [p.strip() for p in str(folder or '').replace(' / ', '/').split('/') if p.strip()]


def _empty_file() -> pathlib.Path:
    return user_dir() / '.dossiers'


def empty_folders() -> list[str]:
    """Dossiers créés par l'utilisateur, gardés même vides."""
    try:
        v = json.loads(_empty_file().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    return ['/'.join(folder_parts(f)) for f in v if isinstance(f, str) and folder_parts(f)] \
        if isinstance(v, list) else []


def _save_empty(folders) -> None:
    f = _empty_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(sorted(set(folders), key=str.lower), ensure_ascii=False), encoding='utf-8')


def add_folder(folder: str) -> str:
    """Nouveau dossier (vide) ; rend son chemin normalisé."""
    folder = '/'.join(folder_parts(folder))
    if folder and folder not in empty_folders():
        _save_empty(empty_folders() + [folder])
    return folder


def user_folders() -> list[str]:
    """Dossiers (et dossiers parents) des modèles de l'utilisateur, et
    ceux qu'il a créés (même vides)."""
    out = set()
    for f in [t.get('dossier') for t in user_templates().values()] + empty_folders():
        parts = folder_parts(f)
        for i in range(1, len(parts) + 1):
            out.add('/'.join(parts[:i]))
    return sorted(out, key=str.lower)


def rename_template(name: str, label: str) -> str | None:
    """Renomme un modèle (dans son dossier) ; rend son nouveau nom, None
    s'il n'existe pas ou si le nom est déjà pris."""
    tpl = user_templates().get(name)
    label = str(label or '').replace(' / ', ' - ').strip()
    if tpl is None or not label:
        return None
    folder = '/'.join(folder_parts(tpl.get('dossier')))
    new = f'{folder} / {label}' if folder else label
    if new == name:
        return name
    if new in user_templates():
        return None
    delete_user(name)
    save_user(dict(tpl, name=new))
    return new


def set_folder(name: str, folder: str, extra: dict | None = None) -> str | None:
    """Range le modèle `name` dans `folder` (vide : hors dossier), avec les clés
    `extra` ; rend son nouveau nom, ou None s'il n'existe pas ou qu'un autre
    modèle porte déjà ce nom dans `folder` (il n'est jamais écrasé : les
    dossiers des process et des modèles sont montrés à part)."""
    tpl = user_templates().get(name)
    if tpl is None:
        return None
    label = label_of(tpl)
    folder = '/'.join(folder_parts(folder))
    new = f'{folder} / {label}' if folder else label
    if new == name and not extra:
        return name
    if new != name and new in user_templates():
        return None
    delete_user(name)
    tpl = dict(tpl, name=new, dossier=folder, **(extra or {}))
    save_user(tpl)
    return new


def _in(folder: str, root: str) -> bool:
    f, r = '/'.join(folder_parts(folder)), '/'.join(folder_parts(root))
    return f == r or f.startswith(r + '/')


#: le dossier d'import d'un modèle repris de TypeEdit (« TypeEdit 13 — Meca3 »), suivi quand l'utilisateur le renomme
#: ou le déplace ; le nom d'origine de ce dossier (celui du fichier importé), pour refaire l'import au même endroit
ROOT_KEY, SOURCE_KEY = 'racine_import', 'source_import'


def imported(t: dict) -> bool:
    """Modèle repris de TypeEdit : paramètres de parcours (TPP) ou fichier .ttpl."""
    return t.get('origine') == 'typeedit' or isinstance(t.get('typeedit'), dict)


def _root_path(t: dict) -> str:
    """Le chemin du dossier d'import d'un modèle repris de TypeEdit ('' : aucun). Importé avant le 15/11 (sans
    `ROOT_KEY`) : son premier dossier, si son nom commence par « TypeEdit »."""
    if not imported(t):
        return ''
    if ROOT_KEY in t:
        return '/'.join(folder_parts(t.get(ROOT_KEY)))
    parts = folder_parts(t.get('dossier'))
    return parts[0] if parts and parts[0].startswith('TypeEdit') else ''


def import_root(t: dict) -> str | None:
    """Le dossier d'import (premier dossier) d'un modèle repris de TypeEdit et resté dedans, même renommé ; None :
    modèle non importé, ou rangé ailleurs par l'utilisateur (son dossier d'import aussi, mis dans un autre dossier)."""
    root = _root_path(t)
    parts = folder_parts(t.get('dossier'))
    return root if root and '/' not in root and parts and parts[0] == root else None


def root_of_source(source: str) -> str:
    """Le dossier d'import actuel du fichier `source` (« TypeEdit 13 — Meca3 », peut-être renommé depuis) : un
    nouvel import s'y refait."""
    for t in user_templates().values():
        if t.get(SOURCE_KEY) == source:
            root = import_root(t)
            if root:
                return root
    return source


def rename_folder(old: str, new: str, which=None) -> int:
    """Renomme (ou déplace, ou fusionne dans un existant) un dossier et ses
    sous-dossiers ; rend le nombre de modèles déplacés. Un dossier d'import de
    TypeEdit renommé le reste (`ROOT_KEY`). `which(modèle)` : ces modèles
    seulement (les process de la palette ont leurs dossiers à part)."""
    old_p, new_p = '/'.join(folder_parts(old)), '/'.join(folder_parts(new))
    n = 0
    for name, t in list(user_templates().items()):
        f = '/'.join(folder_parts(t.get('dossier')))
        if _in(f, old_p) and (which is None or which(t)):
            extra = {}
            root = _root_path(t)
            if root and _in(root, old_p):
                if ROOT_KEY not in t and SOURCE_KEY not in t and t.get('origine') == 'typeedit':
                    extra[SOURCE_KEY] = root             # importé avant : le dossier porte le nom de son fichier
                extra[ROOT_KEY] = (new_p + root[len(old_p):]).strip('/')
            n += set_folder(name, (new_p + f[len(old_p):]).strip('/'), extra) is not None
    empty = empty_folders()
    if any(_in(f, old_p) for f in empty):
        _save_empty([(new_p + f[len(old_p):]).strip('/') if _in(f, old_p) else f for f in empty])
    return n


def delete_folder(folder: str, which=None) -> int:
    """Supprime les modèles du dossier (sous-dossiers compris) ; rend leur nombre.
    `which(modèle)` : ces modèles seulement."""
    n = 0
    for name, t in list(user_templates().items()):
        if _in(t.get('dossier'), folder) and (which is None or which(t)):
            n += delete_user(name)
    empty = empty_folders()
    if any(_in(f, folder) for f in empty):
        _save_empty([f for f in empty if not _in(f, folder)])
    return n


def delete_imported(root: str) -> int:
    """Supprime les modèles importés de TypeEdit rangés sous `root` (avant
    un nouvel import du même fichier : l'arborescence est refaite) ; ceux
    que l'utilisateur a déplacés ailleurs restent."""
    n = 0
    for name, t in list(user_templates().items()):
        if t.get('origine') == 'typeedit' and _in(t.get('dossier'), root):
            n += delete_user(name)
    return n


# --- application -------------------------------------------------------------------------------------
def _match(setup: model.CamSetup, t: model.CamTool) -> model.CamTool | None:
    for s in setup.tools:
        if s.number == t.number and s.kind == t.kind and abs(s.diameter - t.diameter) <= 0.01 \
                and (s.kind != 'conique' or abs(s.angle - t.angle) <= 0.01):
            return s
    for s in setup.tools:                       # même nom : aussi la même sorte et la même taille (deux fiches TypeEdit
        if t.name and s.name == t.name and s.kind == t.kind and _same_size(s, t):     # peuvent porter le même nom)
            return s
    return None


def _same_size(a: model.CamTool, b: model.CamTool) -> bool:
    """Même taille : le diamètre ; pour un cône, l'angle et la pointe (son corps peut manquer à une fiche)."""
    if a.kind == 'conique':
        return abs(a.angle - b.angle) <= 0.01 and abs((a.tip or 0.0) - (b.tip or 0.0)) <= 0.01
    return abs(a.diameter - b.diameter) <= 0.01


def from_operation(setup: model.CamSetup, op: model.Operation, name: str, description: str = '') -> dict:
    """Modèle d'une seule opération (le formulaire rempli) et de ses outils,
    à réappliquer sur d'autres formes."""
    one = model.CamSetup.from_dict(setup.to_dict())
    keep = {op.tool_id, op.ref_tool_id} - {''}
    one.tools = [t for t in one.tools if t.id in keep]
    one.operations = [o for o in one.operations if o.id == op.id]
    tpl = from_setup(one, name, description)
    tpl['post'] = tpl['machine'] = ''
    return tpl


def single(op: model.Operation, tool: model.CamTool | None, name: str, preset: str = '',
           description: str = '') -> dict:
    """Modèle d'un formulaire de parcours (une opération et son outil), à
    retrouver sous ce parcours (`preset` : bouton de la palette)."""
    from ..core import surface2d
    d = surface2d.strip(op.to_dict())
    d['items'], d['sources'] = [], []
    d.pop('body3d_ref', None)                    # volume d'un dessin : sans objet ailleurs
    tools = []
    if tool is not None:
        td = tool.to_dict()
        td['folder'] = ''
        td.pop('history', None)                  # historique des vitesses : propre au poste
        tools = [td]
        d['tool_id'] = td['id']
    return {'format': 'vectordrive-modele-fao', 'version': VERSION, 'name': name, 'description': description,
            'tools': tools, 'operations': [d], 'post': '', 'machine': '', 'preset': preset}


def apply(setup: model.CamSetup, tpl: dict, *, sources: list | None = None,
          replace: bool = False, items: list | None = None) -> tuple[model.CamSetup, list[str]]:
    """Le réglage avec le modèle appliqué (copie) et un compte rendu ;
    `items` : objets du dessin à usiner (les formes choisies) au lieu des
    couleurs."""
    s = copy.deepcopy(setup)
    report = []
    if replace:
        s.operations = []
    ids = {}
    taken = {t.number for t in s.tools}
    for d in tpl.get('tools') or []:
        t = model.CamTool.from_dict(d)
        found = _match(s, t)
        if found is not None:
            ids[t.id] = found.id
            continue
        new = copy.deepcopy(t)
        new.id = model.new_id()
        if new.number in taken:
            new.number = max(taken | {0}) + 1
        taken.add(new.number)
        s.tools.append(new)
        ids[t.id] = new.id
        report.append(f'outil ajouté : T{new.number} {new.name}')
    n = 0
    old = _version(tpl) < VERSION                # avant la version 2 : reprises de gamme non liées d'office
    for d in tpl.get('operations') or []:
        o = model.Operation.from_dict(d)
        o.id = model.new_id()
        o.tool_id = ids.get(o.tool_id, o.tool_id)
        o.ref_tool_id = ids.get(o.ref_tool_id, o.ref_tool_id) if o.ref_tool_id else ''
        o.items = list(items) if items else []
        o.body3d_ref = {}                        # volume d'un autre dessin : le numéro seul
        if old and o.kind == 'reste' and getattr(o, 'gamme_rule', 0) >= 885:   # reprise de gamme d'un modèle d'avant
            o.link_previous = True               # la version 2 : seulement ce que les lignes d'avant ont laissé
        if sources is not None:
            o.sources = list(sources)
        s.operations.append(o)
        n += 1
    if tpl.get('post') and (replace or not setup.operations):
        s.post = tpl['post']
    if tpl.get('machine') and (replace or not setup.machine):
        s.machine = tpl['machine']
    report.insert(0, f'{n} opération(s) ajoutée(s)')
    return s, report
