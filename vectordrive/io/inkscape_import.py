"""Fichiers de clients que VectorDrive ne lit pas lui-même (CorelDRAW, EMF, WMF, Visio, WordPerfect) : ouverts par Inkscape
s'il est installé sur le poste. Inkscape écrit un SVG, que VectorDrive lit ensuite : rien de lui n'est repris ni fourni."""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import tempfile

from . import svg
from ..core import progress
from ..core.document import Document

#: Ce qu'Inkscape sait ouvrir et que VectorDrive ne lit pas lui-même
EXTENSIONS = ('.cdr', '.cmx', '.emf', '.wmf', '.vsd', '.vsdx', '.wpg')
#: Réglage F10 : chemin d'inkscape.exe, s'il n'est pas à sa place habituelle
SETTING = 'import/inkscape'


def _usual_places() -> list[str]:
    out = []
    for var in ('ProgramFiles', 'ProgramW6432', 'ProgramFiles(x86)', 'LOCALAPPDATA'):
        root = os.environ.get(var)
        if root:
            out.append(os.path.join(root, 'Inkscape', 'bin', 'inkscape.exe'))
            out.append(os.path.join(root, 'Programs', 'Inkscape', 'bin', 'inkscape.exe'))
    return out


def find(settings=None) -> str:
    """Chemin d'Inkscape : le réglage, puis le chemin du système, puis les dossiers habituels. '' s'il n'y est pas."""
    if settings is None:
        try:
            from ..portable import settings as _s
            settings = _s()
        except Exception:                                # pragma: no cover - réglages illisibles
            settings = None
    chosen = str(settings.value(SETTING, '') or '').strip().strip('"') if settings is not None else ''
    if chosen and os.path.isfile(chosen):
        return chosen
    found = shutil.which('inkscape')
    if found:
        return found
    return next((p for p in _usual_places() if os.path.isfile(p)), '')


def command(exe: str, src: str, dst: str) -> list[str]:
    return [exe, '--export-type=svg', '--export-plain-svg', f'--export-filename={dst}', src]


def read(path, settings=None, *, timeout: float = 300) -> Document:
    """Le fichier, converti en SVG par Inkscape puis lu comme un SVG. Sans Inkscape : un message qui dit quoi faire."""
    src = pathlib.Path(path)
    exe = find(settings)
    if not exe:
        raise ValueError(f'{src.name} : ce format s\'ouvre par Inkscape (gratuit), qui n\'est pas trouvé sur ce poste. '
                         'Installer Inkscape, ou donner son chemin dans F10 > Fichiers ; ou, depuis le logiciel du '
                         'client, enregistrer le dessin en PDF, SVG ou DXF.')
    with tempfile.TemporaryDirectory(prefix='vd_inkscape_') as tmp:
        dst = os.path.join(tmp, 'sortie.svg')
        progress.check()
        try:
            r = subprocess.run(command(exe, str(src), dst), capture_output=True, timeout=timeout,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except subprocess.TimeoutExpired as ex:
            raise ValueError(f'{src.name} : Inkscape ne répond pas après {int(timeout)} s') from ex
        except OSError as ex:
            raise ValueError(f'{src.name} : Inkscape n\'a pas pu démarrer ({ex})') from ex
        if r.returncode != 0 or not os.path.isfile(dst) or os.path.getsize(dst) == 0:
            why = (r.stderr or b'').decode('utf-8', 'replace').strip().splitlines()
            raise ValueError(f'{src.name} : Inkscape n\'a pas su le convertir'
                             + (f' ({why[-1][:200]})' if why else ''))
        doc = svg.read(dst)
    doc.report.append(f'{src.name} ouvert par Inkscape : à comparer avec l\'original du client')
    return doc
