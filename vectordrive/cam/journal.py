"""Journal des exports, repris de TauDrive (même auteur).

Un même travail est rarement écrit une seule fois : on corrige une
avance, on ajoute une passe, on relance — et trois pièces plus tard,
personne ne sait plus laquelle a été usinée avec quoi. À chaque écriture
d'un programme, une entrée s'ajoute à `<programme>-journal.txt`, à côté :
l'heure, les fichiers, les opérations avec leurs réglages, et surtout ce
qui a changé depuis l'écriture précédente. Texte simple, ASCII, lisible
depuis n'importe quel poste.
"""
from __future__ import annotations

import datetime as dt
import pathlib
import unicodedata

SUFFIX = '-journal.txt'
#: réglages suivis : (attribut, libellé, objet) — objet 'op' (opération) ou 'tool' (outil)
TRACKED = (
    ('kind', 'strategie', 'op'), ('number', 'outil', 'tool'), ('name', 'nom outil', 'tool'),
    ('diameter', 'diametre', 'tool'), ('depth', 'profondeur', 'op'), ('step_down', 'passe', 'op'),
    ('feed', 'avance', 'op'), ('plunge', 'plongee', 'op'), ('spindle', 'broche', 'op'),
    ('power', 'puissance', 'tool'), ('frequency', 'frequence', 'tool'), ('resolution', 'pas', 'op'),
    ('laser_passes', 'passages', 'op'), ('hatch_angle', 'angle', 'op'), ('wobble', 'oscillation', 'op'),
    ('enabled', 'active', 'op'),
)


def ascii_only(s: str) -> str:
    s = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in s if c in '\n\t' or 32 <= ord(c) < 127)


def _fmt(v) -> str:
    if isinstance(v, bool):
        return 'oui' if v else 'non'
    if isinstance(v, float):
        return f'{v:g}'
    return str(v)


def state(setup, toolpaths=(), post: str = '') -> dict:
    """Réglages suivis de chaque opération (outil compris)."""
    ops = {}
    for i, op in enumerate(setup.operations, start=1):
        tool = setup.tool(op.tool_id)
        vals = {}
        for attr, label, where in TRACKED:
            obj = op if where == 'op' else tool
            if obj is None or not hasattr(obj, attr):
                continue
            v = getattr(obj, attr)
            if attr == 'number':
                v = f'T{v}'
            vals[label] = _fmt(v)
        ops[f'{i}. {op.name or op.kind}'] = vals
    return {'post': post, 'operations': ops, 'parcours': sum(1 for tp in toolpaths if tp.moves or tp.cycles)}


def differences(before: dict | None, after: dict) -> list[str]:
    """Ce qui a changé entre deux écritures, en clair."""
    if not before:
        return []
    out = []
    if before.get('post') != after.get('post'):
        out.append(f'post-processeur : {before.get("post")} -> {after.get("post")}')
    a, b = before.get('operations', {}), after.get('operations', {})
    for name in [n for n in b if n not in a]:
        out.append(f'operation ajoutee : {name}')
    for name in [n for n in a if n not in b]:
        out.append(f'operation retiree : {name}')
    for name in [n for n in b if n in a]:
        for label in b[name]:
            if a[name].get(label) != b[name][label]:
                out.append(f'{name} - {label} : {a[name].get(label, "-")} -> {b[name][label]}')
    return out


def path_for(folder, stem: str) -> pathlib.Path:
    return pathlib.Path(folder) / f'{stem}{SUFFIX}'


def next_rank(folder, stem: str) -> int:
    p = path_for(folder, stem)
    try:
        return sum(1 for line in p.read_text(encoding='ascii', errors='replace').splitlines()
                   if line.startswith('Export n')) + 1
    except OSError:
        return 1


def render(st: dict, changes: list[str], *, rank: int, folder: str, files: list[str],
           when: dt.datetime | None = None) -> str:
    """Une entrée du journal."""
    moment = (when or dt.datetime.now()).strftime('%Y-%m-%d %H:%M:%S')
    lines = ['=' * 72, f'Export n{rank}   {moment}', f'  dossier  : {folder}',
             f'  fichiers : {", ".join(files)}', f'  post     : {st.get("post", "")}',
             f'  parcours : {st.get("parcours", 0)}', '  operations :']
    for name, vals in st.get('operations', {}).items():
        lines.append(f'    - {name} : ' + ', '.join(f'{k} {v}' for k, v in vals.items()))
    if changes:
        lines.append('  MODIFICATIONS depuis l\'export precedent :')
        lines += [f'    * {c}' for c in changes]
    elif rank > 1:
        lines.append('  aucun reglage modifie depuis l\'export precedent')
    return ascii_only('\n'.join(lines)) + '\n'


def append(folder, stem: str, entry: str) -> pathlib.Path | None:
    """Ajoute l'entrée ; ne lève jamais (les fichiers sont déjà écrits :
    un journal qui ferait échouer l'écriture serait pire que pas de journal)."""
    target = path_for(folder, stem)
    try:
        with target.open('a', encoding='ascii', errors='replace', newline='\r\n') as f:
            f.write(entry)
    except OSError:
        return None
    return target
