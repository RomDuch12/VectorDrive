"""Fabrique l'archive .zip d'un plugin, à ajouter par F10 › Plugins › « Ajouter un plugin… » (Windows et macOS).

    python outils/plugin_zip.py DOSSIER_DU_PAQUET [--lib NOM]... [-o ARCHIVE.zip]

- le paquet du plugin (le dossier, dont le __init__.py définit register) à la racine de l'archive, sans
  __pycache__, .pyc ni fichiers cachés ;
- dans _lib, chaque bibliothèque nommée par --lib (un module importable avec ce Python : openpyxl…) et ses
  .dist-info. Une bibliothèque compilée (.pyd, .so…) est propre à un système : refusée, comme la bibliothèque
  standard (déjà dans VectorDrive) ;
- l'archive est relue avant d'être rangée (d'office : NOM_DU_PAQUET.zip dans le dossier courant, ou à côté du paquet
  si la commande est lancée depuis le paquet).

Voir docs/ARCHITECTURE.md (Mécanisme des plugins) et `vectordrive.plugins.build_archive`.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Archive .zip d'un plugin de VectorDrive (Windows et macOS)")
    ap.add_argument('paquet', help='dossier du paquet du plugin')
    ap.add_argument('--lib', action='append', default=[],
                    help='bibliothèque Python pure à mettre dans _lib (répétable)')
    ap.add_argument('-o', '--sortie', help="archive à écrire (d'office : NOM_DU_PAQUET.zip dans le dossier courant)")
    args = ap.parse_args(argv)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from vectordrive import plugins
    pkg = pathlib.Path(args.paquet)
    base = pathlib.Path.cwd()
    if plugins._inside(base / 'x.zip', pkg):                 # lancée depuis le paquet : à côté de lui
        base = pathlib.Path(os.path.abspath(pkg)).parent
    out = pathlib.Path(args.sortie) if args.sortie else base / f'{plugins._true_name(pkg)}.zip'
    try:
        path = plugins.build_archive(pkg, out, args.lib)
    except (ValueError, OSError) as ex:
        print(f'archive non faite : {ex}', file=sys.stderr)
        return 1
    with zipfile.ZipFile(path) as z:
        n = len(z.namelist())
    print(f'{path} : plugin {", ".join(plugins.archive_plugins(path))}, {n} fichiers ; '
          f'bibliothèques : {", ".join(dict.fromkeys(args.lib)) or "aucune"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
