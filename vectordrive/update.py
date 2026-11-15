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
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass

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


def check(source: str, current: str = __version__) -> Update | None:
    """Mise à jour plus récente que `current` dans `source`, sinon None."""
    if not source:
        return None
    try:
        data = json.loads(_read(source, manifest_name()).decode('utf-8'))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as ex:
        raise UpdateError(f'manifeste illisible : {ex}') from ex
    for k in ('version', 'installer', 'sha256'):
        if not data.get(k):
            raise UpdateError(f'manifeste incomplet : « {k} » manquant')
    if parse_version(data['version']) <= parse_version(current):
        return None
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
