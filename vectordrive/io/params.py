"""Paramètres d'un poste à l'autre : un fichier `.vdparam` (zip) qui porte
les réglages (options, thème, raccourcis, ruban, plaques…), « Mes outils »,
les modèles d'usinage, les modèles de dessin et les thèmes personnels.

À l'import, on choisit ce qu'on reprend ; les outils sont AJOUTÉS à « Mes
outils » (un outil déjà présent n'est pas doublé) ; un fichier de modèle ou
de thème de même nom est remplacé, mais tout ce qui est remplacé (réglages,
bibliothèque d'outils, fichiers) part d'abord dans un dossier de sauvegarde.
Un ancien export de réglages `.ini` s'importe aussi.

Les réglages propres au poste (fichiers récents, dossiers, session, place
de la fenêtre : `local_keys`) ne sont jamais exportés ni importés.
"""
from __future__ import annotations

import datetime
import json
import os
import pathlib
import shutil
import tempfile
import zipfile

FORMAT = 'vectordrive-parametres'
VERSION = 1
EXT = '.vdparam'
MANIFEST = 'manifeste.json'
SETTINGS_INI = 'reglages.ini'
TOOLS_JSON = 'outils/tools.json'

#: (clé, libellé) dans l'ordre des fenêtres
CATEGORIES = (('reglages', 'Réglages : options, thème, raccourcis, ruban, plaques…'),
              ('outils', 'Mes outils (bibliothèque d\'outils)'),
              ('modeles_fao', 'Modèles d\'usinage'),
              ('modeles_dessin', 'Modèles de dessin'),
              ('themes', 'Thèmes personnels'))
FOLDERS = ('modeles_fao', 'modeles_dessin', 'themes')


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
    raise KeyError(cat)


def _files(cat: str) -> list[pathlib.Path]:
    d = folder(cat)
    if not d.is_dir():
        return []
    return sorted(f for f in d.rglob('*') if f.is_file() and not f.name.endswith(('.tmp', '.bak')))


def _settings_keys(settings, local_keys) -> list[str]:
    return [k for k in settings.allKeys() if not k.startswith(tuple(local_keys))]


def available(settings, local_keys=()) -> dict:
    """Ce que ce poste peut exporter : {catégorie : nombre}."""
    from ..cam import toollib
    out = {'reglages': len(_settings_keys(settings, local_keys)), 'outils': len(toollib.library())}
    for cat in FOLDERS:
        out[cat] = len(_files(cat))
    return out


def summary(counts: dict) -> str:
    from ..i18n import tr
    names = {'reglages': tr('réglages'), 'outils': tr('outils'), 'modeles_fao': tr('modèles d\'usinage'),
             'modeles_dessin': tr('modèles de dessin'), 'themes': tr('thèmes')}
    parts = [f'{n} {names[k]}' for k, n in counts.items() if n and k in names]
    return ', '.join(parts) or tr('rien')


# --- export ----------------------------------------------------------------------------------
def export(path, settings, cats=None, *, local_keys=()) -> dict:
    """Écrit le fichier ; rend {catégorie : nombre écrit}."""
    from PySide6.QtCore import QSettings
    from ..cam import toollib
    cats = list(cats or [k for k, _l in CATEGORIES])
    counts = {}
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    with tempfile.TemporaryDirectory() as work, zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        if 'reglages' in cats:
            ini = os.path.join(work, SETTINGS_INI)
            out = QSettings(ini, QSettings.Format.IniFormat)
            keys = _settings_keys(settings, local_keys)
            for k in keys:
                out.setValue(k, settings.value(k))
            out.sync()
            del out
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
            files = _files(cat)
            for f in files:
                z.write(f, f'{cat}/{f.relative_to(root).as_posix()}')
            counts[cat] = len(files)
        from .. import __version__
        z.writestr(MANIFEST, json.dumps({'format': FORMAT, 'version': VERSION, 'vectordrive': __version__,
                                         'date': datetime.datetime.now().isoformat(timespec='seconds'),
                                         'categories': counts}, ensure_ascii=False, indent=1))
    tmp.replace(path)
    return counts


# --- lecture ---------------------------------------------------------------------------------
def _is_ini(path) -> bool:
    return pathlib.Path(path).suffix.lower() == '.ini'


def _safe(name: str) -> bool:
    p = pathlib.PurePosixPath(name)
    return not p.is_absolute() and '..' not in p.parts and ':' not in name and '\\' not in name


def contents(path) -> dict:
    """Ce que porte le fichier : {catégorie : nombre} ; ValueError s'il n'est
    pas un fichier de paramètres."""
    if _is_ini(path):
        from PySide6.QtCore import QSettings
        return {'reglages': len(QSettings(str(path), QSettings.Format.IniFormat).allKeys())}
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            man = json.loads(z.read(MANIFEST).decode('utf-8')) if MANIFEST in names else {}
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as ex:
        raise ValueError(f'fichier de paramètres illisible : {ex}') from ex
    if man.get('format') != FORMAT:
        raise ValueError('ce n\'est pas un fichier de paramètres VectorDrive')
    out = {}
    if SETTINGS_INI in names:
        out['reglages'] = (man.get('categories') or {}).get('reglages')
    if TOOLS_JSON in names:
        out['outils'] = (man.get('categories') or {}).get('outils')
    for cat in FOLDERS:
        n = sum(1 for x in names if x.startswith(cat + '/') and not x.endswith('/'))
        if n:
            out[cat] = n
    return out


# --- import ----------------------------------------------------------------------------------
def default_backup_dir() -> pathlib.Path:
    from ..portable import data_dir
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    return data_dir() / 'sauvegardes' / f'avant-import-{stamp}'


def import_(path, settings, cats=None, *, local_keys=(), backup_dir=None) -> tuple[dict, pathlib.Path | None]:
    """Reprend les catégories `cats` (toutes par défaut) ; rend ({catégorie :
    nombre repris}, dossier de sauvegarde ou None si rien n'a été remplacé)."""
    from PySide6.QtCore import QSettings
    from ..cam import toollib
    found = contents(path)
    cats = [c for c in (cats or list(found)) if c in found]
    backup = pathlib.Path(backup_dir) if backup_dir else default_backup_dir()
    used = False
    counts = {}

    def save_copy(src: pathlib.Path, rel: str) -> None:
        nonlocal used
        dst = backup / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        used = True

    def apply_settings(src) -> int:
        nonlocal used
        keys = [k for k in src.allKeys() if not k.startswith(tuple(local_keys))]
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

    if _is_ini(path):
        if 'reglages' in cats:
            counts['reglages'] = apply_settings(QSettings(str(path), QSettings.Format.IniFormat))
        return counts, (backup if used else None)
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
            for name in z.namelist():
                if not name.startswith(cat + '/') or name.endswith('/') or not _safe(name):
                    continue
                rel = name[len(cat) + 1:]
                dst = root / rel
                if dst.is_file():
                    if dst.read_bytes() == z.read(name):
                        continue                         # déjà là, identique
                    save_copy(dst, f'{cat}/{rel}')
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(z.read(name))
                n += 1
            counts[cat] = n
    return counts, (backup if used else None)
