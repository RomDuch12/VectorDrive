"""Paramètres d'un poste à l'autre : un fichier `.vdparam` (zip) qui porte
les réglages (options, thème, raccourcis, ruban, plaques…), « Mes outils »,
les modèles d'usinage, les modèles de dessin et les thèmes personnels.

À l'import, on choisit ce qu'on reprend ; les outils sont AJOUTÉS à « Mes
outils » (un outil déjà présent n'est pas doublé) ; un fichier de modèle ou
de thème de même nom est remplacé, mais tout ce qui est remplacé (réglages,
bibliothèque d'outils, fichiers) part d'abord dans un dossier de sauvegarde.
Un ancien export de réglages `.ini` s'importe aussi.

Les réglages propres au poste (fichiers récents, dossiers, session, place
de la fenêtre : `local_keys`) ne sont jamais exportés ni importés, pas plus
qu'un secret : un réglage connu (`SECRET_KEYS` : le jeton du serveur MCP
`agent/jeton`) ou dont un segment de clé est un mot de secret entier
(`secret_key`), un fichier de l'assistant ou d'un plugin dont un mot du nom
en est un (`_secret_name`) — jamais une sous-chaîne quelconque, et jamais
pour la bibliothèque, les polices, les modèles ou les thèmes (« Jeton
caddie.svg » est un symbole). Chacun est dit dans `last_errors`. Les clés
d'API de l'assistant sont dans le gestionnaire d'identifiants de Windows,
jamais dans les réglages.

Demandes du 27/11 (« ajouter boutons exports/imports configuration/réglages »,
« param onglets épinglés + labels ») : une configuration complète porte aussi
la bibliothèque interne, les polices ajoutées par l'utilisateur (ses fichiers
SVG, TrueType, OpenType : jamais une police du système ni d'un autre format),
ses scripts, les données de l'assistant (sans ses copies de fichiers), les
onglets épinglés de la fenêtre (leur nom donné, leur fichier ; un dessin
jamais enregistré est emporté, comme dans la session — un dessin modifié
d'un fichier ne l'est pas : son fichier tel qu'enregistré est rouvert) et les
données que les plugins déclarent (`Api.add_config_data` : une catégorie
« plugin:<clé> » chacune, rangée sous `donnees/`). À l'import, un fichier de
bibliothèque ou une police déjà là n'est jamais remplacé ; une catégorie de
plugin absent de ce poste est proposée quand même (ses fichiers sont gardés
pour le jour où il le sera) ; aucune, plugin chargé ou non, n'est emportée
ni écrite dans un dossier du cœur (`CORE_DATA_DIRS`). Un fichier verrouillé
est laissé et dit, à l'export comme à l'import, qui continuent (jamais de
fichier provisoire laissé). Un fichier d'avant, sans ces catégories, se lit
toujours ; les noms d'archive hors de leur dossier (« .. », chemin absolu,
lecteur) ne sont jamais écrits.

Demande du 27/11 (« maj garder le carnet client ») : la catégorie « Carnet de clients » porte le carnet du BAT
(`clients.json` et ses logos, du dossier qu'emploie ce poste : `io.clients.folder`) ; à l'import, il est fusionné
dans celui du poste (`io.clients.merge`) : un client déjà là est gardé tel quel, les autres sont ajoutés avec leur
logo, aucun fichier n'est écrasé, le `clients.json` d'avant part dans la sauvegarde.
"""
from __future__ import annotations

import datetime
import json
import os
import pathlib
import shutil
import tempfile
import zipfile
import zlib

FORMAT = 'vectordrive-parametres'
VERSION = 1
EXT = '.vdparam'
MANIFEST = 'manifeste.json'
SETTINGS_INI = 'reglages.ini'
TOOLS_JSON = 'outils/tools.json'
PINNED = 'onglets_epingles'
PINNED_INDEX = PINNED + '/onglets.json'
#: les fichiers des plugins, rangés sous ce préfixe au chemin relatif aux données de VectorDrive
DATA_PREFIX = 'donnees/'
PLUGIN_PREFIX = 'plugin:'
#: le carnet de clients du BAT : `clients/clients.json` et `clients/logos/…` dans l'archive
BOOK = 'clients'

#: (clé, libellé) dans l'ordre des fenêtres
CATEGORIES = (('reglages', 'Réglages : options, thème, raccourcis, ruban, plaques…'),
              ('outils', 'Mes outils (bibliothèque d\'outils)'),
              ('modeles_fao', 'Modèles d\'usinage'),
              ('modeles_dessin', 'Modèles de dessin'),
              ('themes', 'Thèmes personnels'),
              ('bibliotheque', 'Bibliothèque interne : symboles ajoutés, « Logos BAT », « Favoris »'),
              ('polices', 'Polices ajoutées (SVG, TrueType, OpenType)'),
              ('scripts', 'Mes scripts'),
              ('assistant', 'Assistant IA : mémoire, mémoires thématiques (jamais de clé d\'API)'),
              (BOOK, 'Carnet de clients du BAT : noms et logos (fusionné avec celui du poste)'),
              (PINNED, 'Onglets épinglés (leur nom, leur fichier ; un dessin jamais enregistré est emporté)'))
FOLDERS = ('modeles_fao', 'modeles_dessin', 'themes', 'bibliotheque', 'polices', 'scripts', 'assistant')
#: à l'import, un fichier déjà là de ces catégories n'est jamais remplacé (gardé, compté dans « gardes »)
KEEP_PRESENT = ('bibliotheque', 'polices')
#: Assistant : jamais les copies de fichiers qu'il a faites (des dessins de l'utilisateur), ni leur registre
ASSISTANT_SKIP_DIRS = ('copies',)
ASSISTANT_SKIP_FILES = ('copies.json',)
#: réglages secrets connus : jamais exportés ni importés
SECRET_KEYS = ('agent/jeton',)
#: mots de secret : un segment de clé de réglage, ou un mot du nom d'un fichier de l'assistant ou d'un plugin, qui en
#: est un (mot entier, séparé par « _ », « - », « . », espace…) n'est jamais exporté ni importé
SECRET_WORDS = ('jeton', 'jetons', 'token', 'tokens', 'secret', 'secrets', 'password', 'passwords', 'passwd', 'pwd',
                'mdp', 'motdepasse', 'mot_de_passe', 'api_key', 'apikey', 'cle_api', 'credential', 'credentials')
SECRET_EXT = ('.key', '.pem', '.pfx', '.p12')
#: les catégories de fichiers où un nom peut dire un secret (ailleurs : symboles, polices, modèles, thèmes, scripts)
SECRET_CATS = ('assistant',)
#: données des plugins : jamais du code, jamais ces dossiers des données (plugins, sessions, récupération…)
CODE_EXT = ('.py', '.pyc', '.pyo', '.pyd', '.dll', '.so', '.dylib', '.exe', '.bat', '.cmd', '.ps1', '.vbs', '.js',
            '.lnk', '.zip')
DATA_SKIP_DIRS = ('plugins', 'session', 'session_maj', 'recuperation', 'sauvegardes', 'onglets_fermes')
#: données de plugin (chargé ou absent) : jamais emportées ni écrites dans ces dossiers du cœur, sous les données
CORE_DATA_DIRS = DATA_SKIP_DIRS + ('outils', 'modeles_fao', 'modeles_dessin', 'themes', 'polices', 'scripts',
                                   'assistant', 'bibliotheque', 'clients', 'formes_polices', 'cache')
#: une entrée de l'archive qui ne peut être écrite (verrouillée, droits) ou lue (somme fausse, données abîmées) :
#: notée, l'import continue
ENTRY_ERRORS = (OSError, zipfile.BadZipFile, zlib.error)
#: les messages de la dernière exportation ou importation (fichiers refusés, `files()` d'un plugin en erreur…)
last_errors: list = []


def _has_word(text: str) -> bool:
    """`text` contient un mot de secret entier (`SECRET_WORDS`), jamais une sous-chaîne d'un autre mot."""
    import re
    words = [w for w in re.split(r'[^a-z0-9]+', str(text).lower()) if w]
    joined = '_' + '_'.join(words) + '_'
    return any(('_' + w + '_') in joined for w in SECRET_WORDS)


def secret_key(key: str) -> bool:
    """Le réglage `key` est un secret : connu (`SECRET_KEYS`), ou un de ses segments est fait d'un mot de secret
    entier (« agent/jeton », « mistral/api_key », « compte/mdp » ; jamais « dessin/cercle_tangent »)."""
    k = str(key).replace('\\', '/').strip('/')
    if k.lower() in SECRET_KEYS:
        return True
    return any(_has_word(seg) for seg in k.split('/'))


def _secret_name(rel: str) -> bool:
    """Un fichier (de l'assistant ou d'un plugin) dont le chemin dit un secret : un mot de secret entier dans un de ses
    noms, ou une extension de clé."""
    parts = pathlib.PurePosixPath(str(rel).replace('\\', '/')).parts
    return bool(parts) and (any(_has_word(p) for p in parts) or parts[-1].lower().endswith(SECRET_EXT))


def _secret_file(cat: str, rel) -> bool:
    """Le fichier `rel` de la catégorie `cat` est un secret : seulement pour l'assistant et les plugins."""
    return (cat in SECRET_CATS or cat.startswith(PLUGIN_PREFIX)) and _secret_name(str(rel))


def _wanted(cat: str, rel) -> bool:
    """Le fichier `rel` (relatif au dossier de la catégorie) fait partie de la catégorie `cat`."""
    parts = pathlib.PurePosixPath(str(rel)).parts
    if not parts:
        return False
    name = parts[-1].lower()
    if name.endswith(('.tmp', '.bak', '.lock', '.vd_copie')) or _secret_file(cat, rel):
        return False
    top = parts[0].lower() if len(parts) > 1 else ''
    if cat == 'polices':                                 # ce que l'utilisateur a ajouté : jamais un autre format
        from ..core.fonts import FONT_EXT
        return pathlib.PurePosixPath(name).suffix in FONT_EXT
    if cat == 'assistant':
        return top not in ASSISTANT_SKIP_DIRS and name not in ASSISTANT_SKIP_FILES
    return True


def _data_ok(rel: str) -> bool:
    """Un fichier de plugin, relatif aux données de VectorDrive, peut être emporté et rendu."""
    p = pathlib.PurePosixPath(rel)
    if not p.parts or p.is_absolute() or '..' in p.parts:
        return False
    name = p.parts[-1].lower()
    return p.parts[0].lower() not in DATA_SKIP_DIRS and p.suffix.lower() not in CODE_EXT \
        and not _secret_name(rel) and not name.endswith(('.tmp', '.lock', '.vd_copie'))


def folder(cat: str) -> pathlib.Path:
    """Dossier de l'utilisateur d'une catégorie de fichiers."""
    if cat == 'modeles_fao':
        from ..cam import templates
        return templates.user_dir()
    if cat == 'modeles_dessin':
        from . import doc_templates
        return doc_templates.user_dir()
    if cat == 'themes':
        from ..ui import themes
        return themes.user_dir()
    if cat == 'bibliotheque':
        from ..ui.symbols import library_root
        return library_root()
    if cat == 'polices':
        from ..core.fonts import user_font_dir
        return user_font_dir()
    if cat == 'scripts':
        from ..core.shapescript import user_dir
        return user_dir()
    if cat == 'assistant':
        from ..agent.tools import assistant_dir
        return assistant_dir()
    raise KeyError(cat)


def _is_link(p) -> bool:
    return os.path.islink(p) or bool(getattr(os.path, 'isjunction', lambda _p: False)(p))


def _files(cat: str, secrets: list | None = None) -> list[pathlib.Path]:
    """Les fichiers d'une catégorie (`_wanted`) ; liens et jonctions jamais suivis, dossiers exclus jamais lus.
    `secrets` : y sont ajoutés les fichiers laissés parce qu'ils disent un secret (`_secret_file`)."""
    d = folder(cat)
    if not d.is_dir():
        return []
    skip = ASSISTANT_SKIP_DIRS if cat == 'assistant' else ()
    out = []
    for here, dirs, names in os.walk(d):
        h = pathlib.Path(here)
        dirs[:] = [x for x in dirs if not _is_link(h / x) and not (h == d and x.lower() in skip)]
        for n in names:
            rel = (h / n).relative_to(d).as_posix()
            if _is_link(h / n):
                continue
            if _wanted(cat, rel):
                out.append(h / n)
            elif secrets is not None and _secret_file(cat, rel):
                secrets.append(h / n)
    return sorted(out)


def _settings_keys(settings, local_keys, secrets: list | None = None) -> list[str]:
    """Les réglages à emporter ; `secrets` : y sont ajoutés ceux laissés parce qu'ils sont secrets."""
    keys = [k for k in settings.allKeys() if not k.startswith(tuple(local_keys))]
    if secrets is not None:
        secrets += [k for k in keys if secret_key(k)]
    return [k for k in keys if not secret_key(k)]


def _tr(text: str) -> str:
    from ..i18n import tr
    return tr(text)


def _secret_note(what) -> str:
    return f'{what} : ' + _tr('secret, jamais emporté')


# --- carnet de clients du BAT ---------------------------------------------------------------
def _book_dir(settings) -> pathlib.Path:
    from . import clients as CL
    return CL.folder(settings)


def _book_entry(rel: str) -> bool:
    """`rel` (relatif au carnet) est un de ses fichiers : `clients.json`, ou un logo de `logos/`."""
    from . import clients as CL
    parts = pathlib.PurePosixPath(rel).parts
    return (parts == (CL.FILE,) or (len(parts) == 2 and parts[0] == CL.LOGOS)) and _wanted(BOOK, rel)


def _book_files(root) -> list[pathlib.Path]:
    """Le `clients.json` du carnet et ses logos (liens jamais suivis) ; sans `clients.json` : rien."""
    from . import clients as CL
    root = pathlib.Path(root)
    if not (root / CL.FILE).is_file() or _is_link(root) or _is_link(root / CL.FILE):
        return []
    out = [root / CL.FILE]
    logos = root / CL.LOGOS
    if logos.is_dir() and not _is_link(logos):
        out += sorted(f for f in logos.iterdir() if f.is_file() and not _is_link(f)
                      and _book_entry(f'{CL.LOGOS}/{f.name}'))
    return out


# --- onglets épinglés ------------------------------------------------------------------------
def _pinned_tabs(window) -> list:
    return [t for t in getattr(window, 'docs', None) or [] if getattr(t, 'pinned', False)] if window else []


# --- données des plugins (`Api.add_config_data`) ------------------------------------------------
def plugin_specs() -> list:
    """Les catégories déclarées par les plugins chargés : [(clé `plugin:…`, libellé, files)]."""
    from ..plugins import REGISTRY
    return [(c[0], c[1], c[2]) for c in getattr(REGISTRY, 'config_data', [])]


def _data_dir() -> pathlib.Path:
    from ..portable import data_dir
    return data_dir()


def _plugin_files(files, errors: list) -> list[tuple[pathlib.Path, str]]:
    """Les fichiers que rend `files()` d'un plugin : [(chemin, nom dans l'archive)] ; hors des données, lien,
    dossier ou refusé (`_data_ok`) : laissé, et dit dans `errors`. Un fichier absent : rien à emporter."""
    base = os.path.realpath(_data_dir())
    out = []
    for p in files() or []:
        p = pathlib.Path(p)
        try:
            real = os.path.realpath(p)
            inside = os.path.commonpath([base, real]) == base and real != base
        except ValueError:                               # autre lecteur
            inside = False
        rel = pathlib.Path(os.path.relpath(real, base)).as_posix() if inside else ''
        if not inside:
            errors.append(f'{p} : hors des données de VectorDrive')
        elif _is_link(p):
            errors.append(f'{p} : lien, jamais suivi')
        elif p.is_dir():
            errors.append(f'{p} : dossier (seulement des fichiers)')
        elif not _data_ok(rel):
            errors.append(f'{p} : refusé (code, secret ou dossier réservé)')
        elif _core_refused(DATA_PREFIX + rel):           # jamais rendu à l'import : pas emporté, et dit
            errors.append(f'{p} : refusé (dossier du cœur : les données d\'un plugin vont dans le sien)')
        elif p.is_file():
            out.append((p, DATA_PREFIX + rel))
    return out


def categories(labels: dict | None = None) -> list[tuple[str, str]]:
    """Les catégories à montrer : celles du cœur, celles des plugins chargés, puis celles d'un fichier (`labels` :
    {clé : libellé}, `file_labels`) dont le plugin est absent de ce poste — proposées quand même, ses fichiers
    gardés."""
    from ..i18n import tr
    out = list(CATEGORIES) + [(k, tr(lb)) for k, lb, _f in plugin_specs()]   # libellés traduits (en.json du plugin)
    known = {k for k, _l in out}
    for k, lb in (labels or {}).items():
        if k.startswith(PLUGIN_PREFIX) and k not in known:
            out.append((k, f'{tr(lb)} — ' + tr('plugin absent de ce poste : fichiers repris quand même')))
    return out


def available(settings, local_keys=(), window=None) -> dict:
    """Ce que ce poste peut exporter : {catégorie : nombre} ; les onglets épinglés si `window` est donnée ; une
    catégorie de plugin dont `files()` échoue : 0."""
    from ..cam import toollib
    out = {'reglages': len(_settings_keys(settings, local_keys)), 'outils': len(toollib.library())}
    for cat in FOLDERS:
        out[cat] = len(_files(cat))
    from . import clients as CL
    out[BOOK] = len(CL.load(_book_dir(settings)))
    if window is not None:
        out[PINNED] = len(_pinned_tabs(window))
    for key, _label, files in plugin_specs():
        try:
            out[key] = len(_plugin_files(files, []))
        except Exception:                                # noqa: BLE001 — un plugin en erreur n'empêche rien
            out[key] = 0
    return out


def summary(counts: dict) -> str:
    from ..i18n import tr
    names = {'reglages': tr('réglages'), 'outils': tr('outils'), 'modeles_fao': tr('modèles d\'usinage'),
             'modeles_dessin': tr('modèles de dessin'), 'themes': tr('thèmes'),
             'bibliotheque': tr('fichiers de bibliothèque'), 'polices': tr('polices'), 'scripts': tr('scripts'),
             'assistant': tr('fichiers de l\'assistant'), PINNED: tr('onglets épinglés'),
             BOOK: tr('clients du carnet'),
             'gardes': tr('fichiers déjà là gardés'), 'introuvables': tr('onglets introuvables')}
    parts = [f'{n} {names[k]}' for k, n in counts.items() if n and k in names]
    plugin = sum(n for k, n in counts.items() if k.startswith(PLUGIN_PREFIX) and isinstance(n, int))
    if plugin:
        parts.append(f'{plugin} ' + tr('fichiers de plugins'))
    return ', '.join(parts) or tr('rien')


# --- export ----------------------------------------------------------------------------------
def export(path, settings, cats=None, *, local_keys=(), window=None) -> dict:
    """Écrit le fichier ; rend {catégorie : nombre écrit}. Les onglets épinglés : seulement avec `window`. Une
    catégorie de plugin dont `files()` échoue n'empêche jamais l'export : 0, et le message dans `last_errors` ; un
    fichier verrouillé non plus (laissé, dit) ; en cas d'erreur, aucun `.tmp` n'est laissé."""
    specs ={k: (lb, f) for k, lb, f in plugin_specs()}
    cats = list(cats or [k for k, _l in CATEGORIES] + list(specs))
    counts = {}
    errors: list[str] = []
    plugins: dict = {}
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    try:
        _export_into(tmp, settings, cats, specs, local_keys, window, counts, errors, plugins)
        tmp.replace(path)
    except BaseException:
        tmp.unlink(missing_ok=True)                      # jamais un .tmp laissé
        raise
    last_errors[:] = errors
    return counts


def _add(z, f, name: str, errors: list) -> bool:
    """Un fichier dans l'archive ; verrouillé ou illisible : dit, l'export continue."""
    try:
        z.write(f, name)
        return True
    except OSError as ex:
        errors.append(f'{f} : {ex.strerror or ex}')
        return False


def _export_into(tmp, settings, cats, specs, local_keys, window, counts, errors, plugins) -> None:
    from PySide6.QtCore import QSettings
    from ..cam import toollib
    with tempfile.TemporaryDirectory() as work, zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        if 'reglages' in cats:
            ini = os.path.join(work, SETTINGS_INI)
            out = QSettings(ini, QSettings.Format.IniFormat)
            secret: list = []
            keys = _settings_keys(settings, local_keys, secret)
            errors += [_secret_note(k) for k in secret]
            for k in keys:
                out.setValue(k, settings.value(k))
            out.sync()
            del out
            if not os.path.exists(ini):                  # aucun réglage : QSettings n'écrit pas de fichier
                pathlib.Path(ini).write_text('', encoding='utf-8')
            z.write(ini, SETTINGS_INI)
            counts['reglages'] = len(keys)
        if 'outils' in cats:
            tools = toollib.library()
            if tools:
                z.writestr(TOOLS_JSON, toollib.to_json(tools))
            counts['outils'] = len(tools)
        for cat in FOLDERS:
            if cat not in cats:
                continue
            root = folder(cat)
            secret = []
            files = _files(cat, secret)
            errors += [_secret_note(f) for f in secret]
            counts[cat] = sum(_add(z, f, f'{cat}/{f.relative_to(root).as_posix()}', errors) for f in files)
        if BOOK in cats:
            from . import clients as CL
            root = _book_dir(settings)
            files = _book_files(root)
            wrote = [f for f in files if _add(z, f, f'{BOOK}/{f.relative_to(root).as_posix()}', errors)]
            counts[BOOK] = len(CL.load(root)) if root / CL.FILE in wrote else 0
        if PINNED in cats and window is not None:
            from . import native
            if hasattr(window, '_store_current'):
                window._store_current()
            entries = []
            for n, t in enumerate(_pinned_tabs(window)):
                e = {'path': t.path or None, 'title': str(getattr(t, 'title', '') or ''), 'file': None,
                     'uid': str(getattr(t, 'uid', '') or '')}   # retrouvé à l'import : jamais rouvert en double
                if not t.path:                           # jamais enregistré : son dessin, emporté
                    name = f'{PINNED}/dessin_{n}.vdz'
                    f = pathlib.Path(work) / f'dessin_{n}.vdz'
                    try:
                        native.write_atomic(native.snapshot(t.doc), f, level=1)
                        z.write(f, name)
                        e['file'] = name
                    except Exception as ex:              # noqa: BLE001 — dit, les autres onglets suivent
                        errors.append(f'{t.name() if hasattr(t, "name") else n} : {ex}')
                        continue
                entries.append(e)
            z.writestr(PINNED_INDEX, json.dumps({'tabs': entries}, ensure_ascii=False, indent=1))
            counts[PINNED] = len(entries)
        for key, (label, files) in specs.items():
            if key not in cats:
                continue
            try:
                found = _plugin_files(files, errors)
            except Exception as ex:                      # noqa: BLE001 — un plugin en erreur n'empêche rien
                errors.append(f'{label} : {ex}')
                counts[key] = 0
                continue
            names = []
            for f, name in found:
                if name not in names and _add(z, f, name, errors):
                    names.append(name)
            plugins[key] = {'label': label, 'files': names}
            counts[key] = len(names)
        from .. import __version__
        man = {'format': FORMAT, 'version': VERSION, 'vectordrive': __version__,
               'date': datetime.datetime.now().isoformat(timespec='seconds'), 'categories': counts}
        if plugins:
            man['plugins'] = plugins
        if errors:
            man['echecs'] = errors
        z.writestr(MANIFEST, json.dumps(man, ensure_ascii=False, indent=1))


# --- lecture ---------------------------------------------------------------------------------
def _is_ini(path) -> bool:
    return pathlib.Path(path).suffix.lower() == '.ini'


def _safe(name: str) -> bool:
    p = pathlib.PurePosixPath(name)
    return not p.is_absolute() and '..' not in p.parts and ':' not in name and '\\' not in name


def _manifest(path) -> tuple[list, dict]:
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            man = json.loads(z.read(MANIFEST).decode('utf-8')) if MANIFEST in names else {}
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError, UnicodeDecodeError) as ex:
        raise ValueError(f'fichier de paramètres illisible : {ex}') from ex
    if not isinstance(man, dict) or man.get('format') != FORMAT:
        raise ValueError('ce n\'est pas un fichier de paramètres VectorDrive')
    return names, man


def _plugin_names(man: dict, names, key: str) -> list[str]:
    """Les fichiers d'une catégorie de plugin d'un fichier : ceux de son manifeste, présents, sûrs."""
    entry = (man.get('plugins') or {}).get(key) if isinstance(man.get('plugins'), dict) else None
    listed = entry.get('files') if isinstance(entry, dict) else None
    have = set(names)
    return [n for n in listed or [] if isinstance(n, str) and n in have and _safe(n) and n.startswith(DATA_PREFIX)
            and _data_ok(n[len(DATA_PREFIX):])]


def _core_refused(name: str) -> bool:
    """Un fichier d'une catégorie de plugin (chargé ou absent de ce poste, 3e relecture du 27/11) qui irait dans un
    dossier du cœur (`CORE_DATA_DIRS`) : refusé."""
    rel = pathlib.PurePosixPath(name[len(DATA_PREFIX):])
    return bool(rel.parts) and rel.parts[0].lower() in CORE_DATA_DIRS


def file_labels(path) -> dict:
    """Les libellés des catégories de plugins d'un fichier ({clé : libellé}) ; {} : aucun, ou un ancien fichier."""
    if _is_ini(path):
        return {}
    _names, man = _manifest(path)
    plugins = man.get('plugins') if isinstance(man.get('plugins'), dict) else {}
    return {k: str(v.get('label') or k) for k, v in plugins.items()
            if isinstance(k, str) and k.startswith(PLUGIN_PREFIX) and isinstance(v, dict)}


def contents(path) -> dict:
    """Ce que porte le fichier : {catégorie : nombre} ; ValueError s'il n'est
    pas un fichier de paramètres."""
    if _is_ini(path):
        from PySide6.QtCore import QSettings
        return {'reglages': len(QSettings(str(path), QSettings.Format.IniFormat).allKeys())}
    names, man = _manifest(path)
    out = {}
    if SETTINGS_INI in names:
        out['reglages'] = (man.get('categories') or {}).get('reglages')
    if TOOLS_JSON in names:
        out['outils'] = (man.get('categories') or {}).get('outils')
    for cat in FOLDERS:
        n = sum(1 for x in names if x.startswith(cat + '/') and not x.endswith('/') and _safe(x)
                and _wanted(cat, x[len(cat) + 1:]))
        if n:
            out[cat] = n
    book = f'{BOOK}/clients.json'
    if book in names:
        try:
            with zipfile.ZipFile(path) as z:
                items = json.loads(z.read(book).decode('utf-8')).get('clients') or []
            n = sum(1 for c in items if isinstance(c, dict) and str(c.get('nom') or '').strip())
            if n:
                out[BOOK] = n
        except (ValueError, AttributeError, KeyError, TypeError, zipfile.BadZipFile):
            pass
    if PINNED_INDEX in names:
        try:
            with zipfile.ZipFile(path) as z:
                tabs = json.loads(z.read(PINNED_INDEX).decode('utf-8')).get('tabs') or []
            out[PINNED] = sum(1 for e in tabs if isinstance(e, dict))
        except (ValueError, AttributeError, KeyError, zipfile.BadZipFile):
            pass
    for key in file_labels(path):
        n = sum(1 for x in _plugin_names(man, names, key) if not _core_refused(x))
        if n:
            out[key] = n
    return out


def _inside(root: pathlib.Path, dst: pathlib.Path) -> bool:
    """`dst` reste dans `root` une fois les chemins résolus (ni « .. », ni lien, ni lecteur ne le font sortir)."""
    try:
        r = os.path.realpath(root)
        return os.path.commonpath([r, os.path.realpath(dst)]) == r
    except ValueError:                                   # autre lecteur
        return False


# --- import ----------------------------------------------------------------------------------
def default_backup_dir() -> pathlib.Path:
    from ..portable import data_dir
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    return data_dir() / 'sauvegardes' / f'avant-import-{stamp}'


def _reopen_pinned(window, z, work: pathlib.Path, errors: list) -> tuple[int, int]:
    """Les onglets épinglés d'un fichier rouverts dans `window`, épinglés, avec leur nom donné : un onglet déjà ouvert
    (même identifiant `uid`, ou même fichier) est épinglé et renommé sur place (jamais doublé, même au 2e import) ;
    un dessin emporté revient non enregistré, sous son identifiant ; un fichier introuvable est dit. Rend (rouverts
    ou retrouvés, introuvables)."""
    from ..ui.doctabs import same_file
    from . import registry
    try:
        tabs = json.loads(z.read(PINNED_INDEX).decode('utf-8')).get('tabs') or []
    except (ValueError, AttributeError, KeyError):
        return 0, 0
    n = missing = 0
    for e in tabs:
        if not isinstance(e, dict):
            continue
        path, inner = e.get('path'), e.get('file')
        title = ' '.join(str(e.get('title') or '').split())[:120]
        uid = e.get('uid') if isinstance(e.get('uid'), str) and e.get('uid') else None
        at = next((k for k, t in enumerate(window.docs) if uid and getattr(t, 'uid', None) == uid), None)
        try:
            if at is not None:
                pass                                     # déjà là (même onglet) : épinglé, renommé sur place
            elif isinstance(path, str) and path:
                at = next((k for k, t in enumerate(window.docs) if same_file(t.path, path)), None)
                if at is None and pathlib.Path(path).is_file():
                    if window.open_path(path):
                        at = window.doc_index
                if at is None:
                    missing += 1
                    errors.append(f'{path} : introuvable')
                    continue
            elif isinstance(inner, str) and _safe(inner) and inner.startswith(PINNED + '/'):
                f = work / ('onglet_' + pathlib.PurePosixPath(inner).name)
                f.write_bytes(z.read(inner))
                doc = registry.open_document(str(f))
                doc.source_path = ''
                at = window._open_in_tab(doc, None, modified=True, uid=uid)
            else:
                continue
        except Exception as ex:                          # noqa: BLE001 — un onglet abîmé n'empêche pas les autres
            errors.append(f'{path or inner} : {ex}')
            continue
        tab = window.docs[at]
        tab.pinned = True
        if title:
            tab.title = title
        n += 1
    if n:
        window._rank_pinned()
        window._sync_tabs()
        window._title()
    return n, missing


def import_(path, settings, cats=None, *, local_keys=(), backup_dir=None,
            window=None) -> tuple[dict, pathlib.Path | None]:
    """Reprend les catégories `cats` (toutes par défaut) ; rend ({catégorie :
    nombre repris}, dossier de sauvegarde ou None si rien n'a été remplacé).
    Les onglets épinglés : seulement avec `window`. Messages : `last_errors`."""
    from PySide6.QtCore import QSettings
    from ..cam import toollib
    found = contents(path)
    cats = [c for c in (cats or list(found)) if c in found]
    backup = pathlib.Path(backup_dir) if backup_dir else default_backup_dir()
    used = False
    counts = {}
    errors: list[str] = []

    def save_copy(src: pathlib.Path, rel: str) -> None:
        nonlocal used
        dst = backup / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        used = True

    def apply_settings(src) -> int:
        nonlocal used
        secret: list = []
        keys = _settings_keys(src, local_keys, secret)
        errors.extend(_secret_note(k) for k in secret)
        if keys:
            backup.mkdir(parents=True, exist_ok=True)
            old = QSettings(str(backup / SETTINGS_INI), QSettings.Format.IniFormat)
            for k in _settings_keys(settings, local_keys):
                old.setValue(k, settings.value(k))
            old.sync()
            used = True
        for k in keys:
            settings.setValue(k, src.value(k))
        settings.sync()
        return len(keys)

    def put(z, name: str, root: pathlib.Path, rel: str, cat: str) -> bool:
        """Un fichier de l'archive écrit à sa place ; vrai s'il l'a été."""
        dst = root / rel
        if not _inside(root, dst) or dst.is_dir():
            errors.append(f'{name} : refusé (hors de son dossier)')
            return False
        data = z.read(name)
        if dst.is_file():
            if dst.read_bytes() == data:
                return False                             # déjà là, identique
            if cat in KEEP_PRESENT:                      # bibliothèque, polices : le fichier déjà là est gardé
                counts['gardes'] = counts.get('gardes', 0) + 1
                return False
            save_copy(dst, name)
        dst.parent.mkdir(parents=True, exist_ok=True)
        part = dst.with_name(dst.name + '.vd_copie')
        try:
            part.write_bytes(data)
            os.replace(part, dst)
        except OSError:                                  # fichier verrouillé : dit par l'appelant, jamais de reste
            try:
                part.unlink()
            except OSError:
                pass
            raise
        return True

    if _is_ini(path):
        if 'reglages' in cats:
            counts['reglages'] = apply_settings(QSettings(str(path), QSettings.Format.IniFormat))
        last_errors[:] = errors
        return counts, (backup if used else None)
    names, man = _manifest(path)
    with zipfile.ZipFile(path) as z, tempfile.TemporaryDirectory() as work:
        if 'reglages' in cats:
            ini = pathlib.Path(work) / SETTINGS_INI
            ini.write_bytes(z.read(SETTINGS_INI))
            src = QSettings(str(ini), QSettings.Format.IniFormat)
            counts['reglages'] = apply_settings(src)
            del src
        if 'outils' in cats:
            new = toollib.from_json(z.read(TOOLS_JSON).decode('utf-8'))
            lib = toollib.library()
            added = [t for t in new if toollib.find_duplicate(t, lib) is None]
            if added:
                target = toollib.default_path()
                if target.is_file():
                    save_copy(target, 'outils/' + target.name)
                toollib.save(lib + added, target)
            counts['outils'] = len(added)
        for cat in FOLDERS:
            if cat not in cats:
                continue
            root = folder(cat)
            n = 0
            for name in names:
                if not name.startswith(cat + '/') or name.endswith('/') or not _safe(name):
                    continue
                if not _wanted(cat, name[len(cat) + 1:]):
                    if _secret_file(cat, name[len(cat) + 1:]):
                        errors.append(_secret_note(name))
                    continue
                try:
                    n += put(z, name, root, name[len(cat) + 1:], cat)
                except ENTRY_ERRORS as ex:                # verrouillé, droits, entrée abîmée : noté, on continue
                    errors.append(f'{name} : {getattr(ex, "strerror", None) or ex}')
            counts[cat] = n
        for key in [c for c in cats if c.startswith(PLUGIN_PREFIX)]:
            base = _data_dir()
            n = 0
            for name in _plugin_names(man, names, key):
                if _core_refused(name):
                    errors.append(f'{name} : ' + _tr('refusé (données de plugin : jamais dans un dossier du '
                                                     'cœur)'))
                    continue
                try:
                    n += put(z, name, base, name[len(DATA_PREFIX):], key)
                except ENTRY_ERRORS as ex:
                    errors.append(f'{name} : {getattr(ex, "strerror", None) or ex}')
            counts[key] = n
        if BOOK in cats:                                 # fusionné : rien d'ici n'est écrasé
            from . import clients as CL
            carnet = pathlib.Path(work) / 'carnet'
            for name in names:
                rel = name[len(BOOK) + 1:]
                if not name.startswith(BOOK + '/') or not _safe(name) or not _book_entry(rel):
                    continue
                try:
                    f = carnet / rel
                    f.parent.mkdir(parents=True, exist_ok=True)
                    f.write_bytes(z.read(name))
                except ENTRY_ERRORS as ex:
                    errors.append(f'{name} : {getattr(ex, "strerror", None) or ex}')

            def keep_copy(f: pathlib.Path) -> str:
                save_copy(f, f'{BOOK}/{CL.FILE}')
                return f'{f} → {backup / BOOK / CL.FILE}'
            try:
                merged = CL.merge(carnet, _book_dir(settings), backup=keep_copy)
                added, bad = merged.added, merged.failed
            except OSError as ex:
                added, bad = [], [f'{_book_dir(settings)} : {ex.strerror or ex}']
            errors += bad
            counts[BOOK] = len(added)
        if PINNED in cats and window is not None:
            counts[PINNED], lost = _reopen_pinned(window, z, pathlib.Path(work), errors)
            if lost:
                counts['introuvables'] = lost
    last_errors[:] = errors
    return counts, (backup if used else None)
