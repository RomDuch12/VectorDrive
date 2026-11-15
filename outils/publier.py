"""Publie une version de VectorDrive.

    python outils/publier.py [--build] [--dest DOSSIER] [--notes "…"]

1. (--build) empaquette avec PyInstaller puis lance l'autotest de l'exe ;
2. compile l'installateur Inno Setup (installeur/VectorDrive.iss) ;
3. fabrique l'archive portable (dist/portable/VectorDrive-x.y.z-portable.zip :
   le dossier de l'application et un VectorDrive.ini vide qui active le
   mode portable) ;
4. écrit dans dist/maj/ l'installateur, l'archive portable et le manifeste
   `vectordrive-latest.json` (version, empreintes SHA-256, notes) ;
5. (--dest) copie l'installateur et l'archive PUIS le manifeste dans le dossier des
   mises à jour (partage de l'atelier…) : un poste ne voit jamais un
   manifeste qui désigne un installateur pas encore copié.

Édition avec plugin (voir docs/ARCHITECTURE.md) : `--plugin DOSSIER_DU_PAQUET`
(répétable) copie le paquet dans `plugins/` de l'application, `--edition NOM`
nomme les fichiers `VectorDrive-NOM-x.y.z-…`, `--manifest` et `--publisher`
donnent le manifeste suivi par cette édition et l'éditeur de l'installateur.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vectordrive.update import MANIFEST, sha256_file  # noqa: E402

KEEP = 3                                   # versions gardées dans dist/

ISCC_CANDIDATES = [
    pathlib.Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Inno Setup 6' / 'ISCC.exe',
    pathlib.Path('C:/Program Files (x86)/Inno Setup 6/ISCC.exe'),
    pathlib.Path('C:/Program Files/Inno Setup 6/ISCC.exe'),
]


def version() -> str:
    src = (ROOT / 'vectordrive' / '__init__.py').read_text(encoding='utf-8')
    return re.search(r"__version__ = '([^']+)'", src).group(1)


def iscc() -> pathlib.Path:
    for c in ISCC_CANDIDATES:
        if c.exists():
            return c
    found = shutil.which('ISCC')
    if found:
        return pathlib.Path(found)
    raise SystemExit('Inno Setup 6 introuvable (winget install JRSoftware.InnoSetup)')


def _locked(folder: pathlib.Path) -> bool:
    """Dossier verrouillé (VectorDrive lancé depuis lui) : on ne peut ni le
    renommer ni le reconstruire."""
    if not folder.exists():
        return False
    probe = folder.with_name(folder.name + '_essai_verrou')
    try:
        os.rename(folder, probe)
        os.rename(probe, folder)
        return False
    except OSError:
        return True


def run(cmd, **kw) -> None:
    print('>', ' '.join(str(c) for c in cmd))
    subprocess.run(cmd, check=True, **kw)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true', help='PyInstaller + autotest avant l\'installateur')
    ap.add_argument('--dest', help='dossier des mises à jour à alimenter')
    ap.add_argument('--notes', default='', help='notes de version affichées aux utilisateurs')
    ap.add_argument('--plugin', action='append', default=[], help='paquet de plugin à embarquer (dossier)')
    ap.add_argument('--edition', default='', help='nom de l\'édition (fichiers VectorDrive-<édition>-…)')
    ap.add_argument('--manifest', default=MANIFEST, help='nom du manifeste de mise à jour')
    ap.add_argument('--publisher', default='VectorDrive', help='éditeur affiché par l\'installateur')
    args = ap.parse_args(argv)
    v = version()
    ed = f'-{args.edition}' if args.edition else ''
    manifest_name = args.manifest
    # dist/VectorDrive ouvert (VectorDrive lancé depuis lui) : construction à côté
    dist_root = ROOT / 'dist'
    if args.build and _locked(dist_root / 'VectorDrive'):
        dist_root = ROOT / 'dist' / '_stage'
        print('dist/VectorDrive est utilisé : construction dans dist/_stage')
    app = dist_root / 'VectorDrive'
    if not args.build and not app.exists() and (ROOT / 'dist' / '_stage' / 'VectorDrive').exists():
        app = ROOT / 'dist' / '_stage' / 'VectorDrive'
    if args.build:
        run([sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm', '--distpath', str(dist_root),
             'VectorDrive.spec'], cwd=ROOT)
        exe = app / 'VectorDrive.exe'
        report = exe.parent / 'VectorDrive_rapport.txt'
        report.unlink(missing_ok=True)
        r = subprocess.run([str(exe), '--autotest'], cwd=exe.parent)
        if report.exists():
            print(report.read_text(encoding='utf-8'))
        if r.returncode != 0:
            raise SystemExit('autotest de l\'exécutable en échec : publication arrêtée')
        report.unlink(missing_ok=True)
    if not (app / 'VectorDrive.exe').exists():
        raise SystemExit('dist/VectorDrive absent : lancer avec --build')
    plugdir = app / 'plugins'
    if plugdir.exists():
        shutil.rmtree(plugdir)                       # jamais d'un plugin d'une autre édition
    for src in args.plugin:
        src = pathlib.Path(src).resolve()
        shutil.copytree(src, plugdir / src.name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    if args.plugin and args.build:
        # l'exécutable doit charger le plugin et passer ses vérifications
        report = app / 'VectorDrive_rapport.txt'
        report.unlink(missing_ok=True)
        r = subprocess.run([str(app / 'VectorDrive.exe'), '--autotest'], cwd=app)
        if report.exists():
            print(report.read_text(encoding='utf-8'))
        if r.returncode != 0:
            raise SystemExit('autotest de l\'exécutable avec plugin en échec : publication arrêtée')
        report.unlink(missing_ok=True)
    run([str(iscc()), f'/DVersion={v}', f'/DAppSrc={app}', f'/DEdition={ed}', f'/DPublisher={args.publisher}',
         '/Q', str(ROOT / 'installeur' / 'VectorDrive.iss')])
    setup = ROOT / 'dist' / 'installeur' / f'VectorDrive{ed}-{v}-setup.exe'
    from vectordrive.portable import make_archive
    port = make_archive(app, ROOT / 'dist' / 'portable' / f'VectorDrive{ed}-{v}-portable.zip')
    out = ROOT / 'dist' / 'maj'
    out.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(setup, out / setup.name)
    shutil.copyfile(port, out / port.name)
    manifest = {'version': v, 'installer': setup.name, 'sha256': sha256_file(setup),
                'portable': port.name, 'portable_sha256': sha256_file(port),
                'notes': args.notes, 'date': dt.date.today().isoformat(),
                'taille': setup.stat().st_size}
    (out / manifest_name).write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{setup.name} : {setup.stat().st_size / 1e6:.1f} Mo, sha256 {manifest["sha256"][:16]}…')
    print(f'{port.name} : {port.stat().st_size / 1e6:.1f} Mo')
    # sorties locales : on garde les KEEP dernières versions (le dossier --dest n'est jamais nettoyé)
    from vectordrive.update import parse_version
    for folder in (ROOT / 'dist' / 'installeur', ROOT / 'dist' / 'portable', out):
        for suffix in ('-setup.exe', '-portable.zip'):
            olds = sorted((f for f in folder.glob(f'VectorDrive{ed}-*{suffix}')
                           if re.fullmatch(r'\d+\.\d+\.\d+', f.name[len(f'VectorDrive{ed}-'):-len(suffix)])),
                          key=lambda f: parse_version(f.name[len(f'VectorDrive{ed}-'):-len(suffix)]))
            for old in olds[:-KEEP]:
                old.unlink()
    if args.dest:
        dest = pathlib.Path(args.dest)
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(setup, dest / setup.name)
        shutil.copyfile(port, dest / port.name)
        tmp = dest / (manifest_name + '.tmp')
        shutil.copyfile(out / manifest_name, tmp)
        os.replace(tmp, dest / manifest_name)
        print(f'publié dans {dest}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
