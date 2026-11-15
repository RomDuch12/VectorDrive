"""Exporte le dépôt public de VectorDrive à partir du dépôt de travail.

    python outils/exporter_public.py DOSSIER_PUBLIC --interdits FICHIER [--message "…"]

- copie les fichiers suivis par git, sauf les documents de travail privés
  (`PRIVES`) ;
- refuse l'export si un fichier publié contient un des mots du fichier
  `--interdits` (un par ligne : chemins, noms de clients… ; le fichier
  lui-même reste privé) ;
- dans DOSSIER_PUBLIC : dépôt git neuf au premier export, puis un commit
  par export (l'historique du dépôt de travail n'est jamais publié).

Rien n'est poussé vers un serveur : c'est à l'auteur de le faire.
"""
from __future__ import annotations

import argparse
import fnmatch
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: documents de travail qui ne sortent pas (motifs fnmatch, chemins relatifs)
PRIVES = [
    'JOURNAL.md',               # journal de développement (le public : CHANGELOG.md)
    'SPEC.md',                  # spécification d'origine (décisions de l'auteur)
    'docs/formats/*',           # notes d'analyse des formats TypeEdit (interopérabilité)
    '.claude/*',
    'tests/corpus_local.json',
    'tests/_sorties/*',
]
AUTEUR = 'RomDuch <romduch@gmail.com>'
#: programmes machine et parcours (jamais publiés : ce sont des fichiers de production)
PROGRAMMES = re.compile(r'\.(simpl|nc|cnc|iso|tap|ngc|mpf|cljob|plt|hpgl|\d{3})$', re.I)
#: dessins : seulement ceux des ressources de VectorDrive (modèle VND)
DESSINS = re.compile(r'\.(vnd|vdz|gvt)$', re.I)
DESSINS_PERMIS = ('vectordrive/ressources/',)
#: sources de tiers recopiées telles quelles : noms vérifiés, contenu non (noms de paquets Rust…)
TIERS = ('natif/vendor/',)


def publishable() -> list[str]:
    files = subprocess.run(['git', 'ls-files'], cwd=ROOT, capture_output=True, text=True, check=True,
                           encoding='utf-8').stdout.splitlines()
    return [f for f in files if not any(fnmatch.fnmatch(f, p) for p in PRIVES) and (ROOT / f).is_file()]


def production_files(files: list[str]) -> list[str]:
    """Programmes machine, parcours et dessins de clients parmi les fichiers publiés."""
    return [f for f in files if PROGRAMMES.search(f) or (DESSINS.search(f) and not f.startswith(DESSINS_PERMIS))]


def _text(path: pathlib.Path) -> str | None:
    """Contenu d'un fichier texte (quelle que soit son extension), None s'il est binaire."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b'\0' in data[:8192]:
        return None
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        return data.decode('latin-1')


def scan(files: list[str], words: list[str]) -> list[str]:
    """Fichiers (nom ou contenu) où paraît un mot interdit, et fichiers de
    production (programmes, parcours, dessins) qui n'ont rien à publier."""
    pats = [re.compile(re.escape(w), re.I) for w in words if w.strip()]
    hits = [f'{f} : fichier de production (programme, parcours ou dessin)' for f in production_files(files)]
    for f in files:
        for p in pats:
            if p.search(f):
                hits.append(f'{f} : nom ({p.pattern})')
        if f.startswith(TIERS):
            continue
        text = _text(ROOT / f)
        if text is None:
            continue
        for p in pats:
            for m in p.finditer(text):
                line = text.count('\n', 0, m.start()) + 1
                hits.append(f'{f}:{line} : {p.pattern}')
    return hits


def export(dest: pathlib.Path, words: list[str], message: str) -> int:
    files = publishable()
    hits = scan(files, words)
    if hits:
        print('Export refusé — données privées dans des fichiers publiés :')
        print('\n'.join('  ' + h for h in hits[:200]))
        return 1
    dest.mkdir(parents=True, exist_ok=True)
    for old in dest.rglob('*'):                       # repartir propre (sauf .git)
        if '.git' in old.relative_to(dest).parts or not old.is_file():
            continue
        old.unlink()
    for f in files:
        out = dest / f
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / f, out)
    git = lambda *a: subprocess.run(['git', *a], cwd=dest, check=True, capture_output=True, text=True,
                                    encoding='utf-8')
    if not (dest / '.git').exists():
        git('init', '-q')
    git('add', '-A')
    if not git('status', '--porcelain').stdout.strip():
        print('rien de neuf à publier')
        return 0
    name, mail = AUTEUR[:-1].split(' <')
    git('-c', f'user.name={name}', '-c', f'user.email={mail}', 'commit', '-q', '-m', message)
    print(f'{len(files)} fichiers exportés dans {dest} ; dernier commit : '
          + git('log', '--oneline', '-1').stdout.strip())
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('dest')
    ap.add_argument('--interdits', required=True, help='fichier privé des mots interdits (un par ligne)')
    ap.add_argument('--message', default='')
    args = ap.parse_args(argv)
    words = [w.strip() for w in pathlib.Path(args.interdits).read_text(encoding='utf-8').splitlines()
             if w.strip() and not w.startswith('#')]
    sys.path.insert(0, str(ROOT))
    from vectordrive import __version__
    msg = args.message or (f'VectorDrive {__version__}\n\n'
                           'Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>')
    return export(pathlib.Path(args.dest), words, msg)


if __name__ == '__main__':
    sys.exit(main())
