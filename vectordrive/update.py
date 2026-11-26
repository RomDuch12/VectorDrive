"""Mise à jour automatique.

La source des mises à jour est un **dossier** (partage réseau, dossier
synchronisé…) ou une **URL https** ; elle contient un manifeste
`vectordrive-latest.json` écrit par `outils/publier.py` :

    {"version": "0.2.0", "installer": "VectorDrive-0.2.0-setup.exe",
     "sha256": "…", "notes": "…", "date": "2026-10-16"}

`installer` est relatif au manifeste (ou une URL complète). L'empreinte
SHA-256 est vérifiée avant de lancer l'installateur (intégrité du fichier
copié ou téléchargé). L'installateur Inno Setup tourne en mode silencieux,
ferme VectorDrive puis le relance.

Rien n'est installé sans l'accord de l'utilisateur ; depuis les sources
(non empaqueté), la mise à jour est seulement signalée.

Demande du 26/11 (une version disait « à jour » à côté d'une archive plus
récente déposée seule) : `look` reconnaît aussi, par son seul nom, une archive
portable `VectorDrive{-édition}-1.34.0-portable.zip` de l'édition qui tourne,
déposée dans la source (un dossier) ou dans les dossiers donnés (le dossier où
chercher la dernière version, `maj/dossier_source`). Sans manifeste, elle n'a
pas d'empreinte : elle s'installe par la mise à jour par dossier
(`app_update`, archive vérifiée par `check_archive`), jamais par
l'installateur silencieux. Le manifeste garde la priorité quand il désigne une
version au moins aussi récente.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from . import __version__

MANIFEST = 'vectordrive-latest.json'


def manifest_name() -> str:
    """Manifeste suivi : celui de l'édition (plugin), sinon celui du cœur."""
    from .plugins import REGISTRY
    return REGISTRY.update_manifest or MANIFEST
TIMEOUT = 10


class UpdateError(Exception):
    pass


@dataclass
class Update:
    version: str
    installer: str          # chemin local ou URL
    sha256: str
    notes: str = ''
    date: str = ''
    portable: bool = False   # archive portable (mode portable) plutôt qu'installateur
    folder: str = ''         # archive portable déposée seule, sans manifeste ni empreinte : le dossier où elle a été
    #                          trouvée ; elle s'installe par la mise à jour par dossier (`MainWindow.app_update`)


def parse_version(v: str) -> tuple:
    out = []
    for part in str(v).strip().lstrip('vV').split('.'):
        num = ''.join(ch for ch in part if ch.isdigit())
        out.append(int(num) if num else 0)
    return tuple(out + [0] * (3 - len(out)))


def is_url(source: str) -> bool:
    return urllib.parse.urlparse(source).scheme in ('http', 'https')


def _read(source: str, name: str) -> bytes:
    if is_url(source):
        url = urllib.parse.urljoin(source.rstrip('/') + '/', name)
        if urllib.parse.urlparse(url).scheme != 'https':
            raise UpdateError('les mises à jour par Internet doivent passer par https')
        with urllib.request.urlopen(url, timeout=TIMEOUT) as r:     # noqa: S310 - https vérifié
            return r.read()
    return (pathlib.Path(source) / name).read_bytes()


def _manifest(source: str) -> dict | None:
    """Le manifeste de `source`, vérifié (champs obligatoires) ; None : il n'y en a pas."""
    try:
        data = json.loads(_read(source, manifest_name()).decode('utf-8'))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as ex:
        raise UpdateError(f'manifeste illisible : {ex}') from ex
    for k in ('version', 'installer', 'sha256'):
        if not data.get(k):
            raise UpdateError(f'manifeste incomplet : « {k} » manquant')
    return data


@dataclass
class Lookup:
    """Ce que la vérification a regardé et trouvé (`look`) : `update` (None : rien de plus récent) ; `source` et
    `manifest` (sa version ; '' : pas de manifeste ; None : non lu — pas de source, ou erreur) ; `folders`, les
    dossiers où les archives portables ont été cherchées, et `archive`, la dernière de l'édition qui tourne
    (`app_update.Found`, même pas plus récente ; None : aucune) ; `errors` : manifeste illisible, dossier
    injoignable ; `odd` : les archives `VectorDrive….zip` ignorées pour leur nom (« … (1).zip »)."""
    update: Update | None = None
    source: str = ''
    manifest: str | None = None
    folders: list = field(default_factory=list)
    archive: object = None
    errors: list = field(default_factory=list)
    odd: list = field(default_factory=list)


def look(source: str, current: str = __version__, folders=(), edition: str | None = None) -> Lookup:
    """La vérification complète (demande du 26/11) : le manifeste de `source`, et les archives portables de
    l'édition `edition` (d'office celle qui tourne : `app_update.current_edition`) déposées, reconnues par leur seul
    nom, dans `source` (si c'est un dossier) et dans `folders` — une édition ne prend jamais l'archive d'une autre.
    Le manifeste l'emporte s'il désigne une version au moins aussi récente que la dernière archive ; sinon l'archive
    (`Update.folder`, sans empreinte). Une erreur (manifeste illisible, dossier injoignable) est gardée dans
    `errors`, sans empêcher le reste. À appeler dans un fil (un partage absent fait attendre)."""
    from . import app_update as AU
    out = Lookup(source=source or '')
    best = None
    if source:
        try:
            data = _manifest(source)
            out.manifest = str(data['version']) if data is not None else ''
            if data is not None and parse_version(data['version']) > parse_version(current):
                best = _from_manifest(source, data)
        except UpdateError as ex:
            out.manifest = None
            out.errors.append(str(ex))
    seen: set = set()
    for d in ([source] if source and not is_url(source) else []) + [str(f) for f in folders or () if f]:
        key = os.path.normcase(os.path.abspath(d))
        if key not in seen:                              # la source et le dossier où chercher : souvent le même
            seen.add(key)
            out.folders.append(d)
    if edition is None:
        from .portable import app_dir
        edition = AU.current_edition(app_dir(), manifest_name())
    found = []
    for d in out.folders:
        try:
            found += [(f, d) for f in AU.scan(d, out.odd)]
        except AU.AppUpdateError as ex:                  # injoignable : dit ; les autres dossiers comptent
            out.errors.append(str(ex))
    top = AU.latest_of([f for f, _d in found], edition)
    out.archive = top
    if top is not None and parse_version(top.version) > parse_version(current) and \
            (best is None or parse_version(top.version) > parse_version(best.version)):
        best = Update(top.version, str(top.path), '', portable=True, folder=next(d for f, d in found if f is top))
    out.update = best
    return out


def check(source: str, current: str = __version__, folders=(), edition: str | None = None) -> Update | None:
    """Mise à jour plus récente que `current`, sinon None : celle du manifeste de `source`, ou une archive portable
    de la même édition déposée seule dans `source` ou dans `folders` (`look`). Rien de plus récent, mais quelque chose
    n'a pas pu être regardé : `UpdateError` — jamais « à jour » sans avoir pu chercher."""
    got = look(source, current, folders, edition)
    if got.update is None and got.errors:
        raise UpdateError(' ; '.join(got.errors))
    return got.update


def _from_manifest(source: str, data: dict) -> Update:
    """La mise à jour que désigne le manifeste : l'installateur, ou l'archive portable (mode portable) ; son
    empreinte."""
    inst, sha, port = data['installer'], data['sha256'], False
    from .portable import is_portable
    if is_portable() and data.get('portable') and data.get('portable_sha256'):
        inst, sha, port = data['portable'], data['portable_sha256'], True
    if is_url(source):
        inst = urllib.parse.urljoin(source.rstrip('/') + '/', inst)
    elif not pathlib.Path(inst).is_absolute():
        inst = str(pathlib.Path(source) / inst)
    return Update(data['version'], inst, sha.lower(), data.get('notes', ''), data.get('date', ''), port)


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def fetch(up: Update, dest_dir=None) -> pathlib.Path:
    """Copie (ou télécharge) l'installateur et vérifie son empreinte."""
    if up.folder or not up.sha256:                       # archive déposée seule : par la mise à jour par dossier
        raise UpdateError(f'{up.installer} : sans empreinte, à installer par « Mettre à jour l’application »')
    dest_dir = pathlib.Path(dest_dir or tempfile.mkdtemp(prefix='vectordrive_maj_'))
    name = pathlib.PurePosixPath(urllib.parse.urlparse(up.installer).path).name if is_url(up.installer) \
        else pathlib.Path(up.installer).name
    dest = dest_dir / name
    if is_url(up.installer):
        if urllib.parse.urlparse(up.installer).scheme != 'https':
            raise UpdateError('les mises à jour par Internet doivent passer par https')
        with urllib.request.urlopen(up.installer, timeout=60) as r, open(dest, 'wb') as f:  # noqa: S310
            shutil.copyfileobj(r, f)
    else:
        shutil.copyfile(up.installer, dest)
    got = sha256_file(dest)
    if got != up.sha256:
        dest.unlink(missing_ok=True)
        raise UpdateError(f'empreinte SHA-256 incorrecte pour {name} : fichier refusé')
    return dest


def can_install() -> bool:
    """Seul l'exécutable empaqueté peut se remplacer par l'installateur."""
    return bool(getattr(sys, 'frozen', False)) and sys.platform == 'win32'


def launch_installer(path) -> None:
    """Lance l'installateur en silencieux ; l'appelant quitte ensuite
    VectorDrive (l'installateur le relance une fois fini)."""
    subprocess.Popen([str(path), '/SILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/CLOSEAPPLICATIONS'],
                     close_fds=True)
