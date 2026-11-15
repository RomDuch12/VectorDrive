"""EMF et WMF (dessins de Windows : Word, Excel, PowerPoint, vieux logiciels de gravure) : écrits par Inkscape s'il est
installé sur le poste. VectorDrive écrit un SVG, Inkscape le convertit : rien de lui n'est repris ni fourni."""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import tempfile

from . import inkscape_import, svg
from ..core import progress
from ..core.document import Document

#: Ce qu'Inkscape sait écrire et que VectorDrive n'écrit pas lui-même
EXTENSIONS = ('.emf', '.wmf')


def command(exe: str, src: str, dst: str) -> list[str]:
    kind = pathlib.Path(dst).suffix.lower().lstrip('.')
    return [exe, f'--export-type={kind}', f'--export-filename={dst}', src]


def write(doc: Document, path, settings=None, *, timeout: float = 300) -> None:
    """Le dessin en SVG, converti par Inkscape dans le format de `path`. Sans Inkscape : un message qui dit quoi faire."""
    dst = pathlib.Path(path)
    if dst.suffix.lower() not in EXTENSIONS:
        raise ValueError(f'{dst.name} : format qu\'on ne sait pas écrire (EMF et WMF seulement, par Inkscape)')
    exe = inkscape_import.find(settings)
    if not exe:
        raise ValueError(f'{dst.name} : ce format s\'écrit par Inkscape (gratuit), qui n\'est pas trouvé sur ce poste. '
                         'Installer Inkscape, ou donner son chemin dans F10 > Fichiers ; ou enregistrer le dessin en '
                         'PDF, SVG ou DXF.')
    with tempfile.TemporaryDirectory(prefix='vd_inkscape_') as tmp:
        src = os.path.join(tmp, 'entree.svg')
        out = os.path.join(tmp, 'sortie' + dst.suffix.lower())
        svg.write(doc, src)
        progress.check()
        try:
            r = subprocess.run(command(exe, src, out), capture_output=True, timeout=timeout,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except subprocess.TimeoutExpired as ex:
            raise ValueError(f'{dst.name} : Inkscape ne répond pas après {int(timeout)} s') from ex
        except OSError as ex:
            raise ValueError(f'{dst.name} : Inkscape n\'a pas pu démarrer ({ex})') from ex
        if r.returncode != 0 or not os.path.isfile(out) or os.path.getsize(out) == 0:
            why = (r.stderr or b'').decode('utf-8', 'replace').strip().splitlines()
            raise ValueError(f'{dst.name} : Inkscape n\'a pas su l\'écrire' + (f' ({why[-1][:200]})' if why else ''))
        shutil.copyfile(out, str(dst) + '.tmp')
    os.replace(str(dst) + '.tmp', dst)
    doc.report.append(f'{dst.name} écrit par Inkscape')
