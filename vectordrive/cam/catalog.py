"""Catalogues d'opérations machine : des blocs de programme tout prêts
(commandes d'une documentation de machine, opérations d'un autre logiciel,
programmes d'exemple) que l'on ajoute à la liste des opérations FAO. Les
catalogues viennent des plugins (`Api.add_instruction_catalog`) ; le cœur
n'en contient aucun, il sait seulement prendre un fichier texte comme bloc.

Une entrée devient une instruction machine : un bloc de programme (texte
copié tel quel, {p1} … {p6} remplacés par ses paramètres nommés) ou, si
l'entrée le dit, une instruction connue (palpage, message…) avec ses
réglages.
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Callable

#: taille maximale d'un fichier pris comme bloc (octets)
MAX_FILE = 400_000


@dataclass
class Entry:
    name: str
    text: str | Callable = ''          # lignes du bloc, ou fonction() → lignes (lu à la demande)
    path: str = ''                     # rangement dans le catalogue : « Famille/Sous-famille »
    note: str = ''                     # aide (chapitre, page de la documentation…)
    names: list = field(default_factory=list)      # noms des paramètres {p1} … {p6}
    values: list = field(default_factory=list)     # leurs valeurs par défaut
    instruction: str = 'bloc'          # instruction créée (cam.instructions) ; 'bloc' : texte tel quel
    params: dict = field(default_factory=dict)     # réglages d'une instruction autre que 'bloc'
    catalog: str = ''                  # libellé du catalogue (rempli à la lecture)
    doc: str = ''                      # document du poste (PDF) qui décrit l'opération
    page: int = 0                      # sa page (1 = la première)

    def lines(self) -> str:
        """Texte du bloc (lu à la demande pour un fichier)."""
        t = self.text() if callable(self.text) else self.text
        return str(t or '')


def catalogs() -> list[tuple[str, list[Entry], str]]:
    """[(libellé, entrées, problème)] des catalogues des plugins ; un
    catalogue en défaut est rendu vide avec son problème."""
    from ..plugins import REGISTRY
    out = []
    for label, provider in getattr(REGISTRY, 'instruction_catalogs', []):
        try:
            entries = [e if isinstance(e, Entry) else Entry(**e) for e in (provider() or [])]
            problem = ''
        except Exception as ex:                        # catalogue illisible : les autres restent
            entries, problem = [], f'{type(ex).__name__} : {ex}'
        for e in entries:
            e.catalog = label
        out.append((label, entries, problem))
    return out


def file_entry(path) -> Entry:
    """Un fichier texte (programme machine, extrait) pris comme bloc."""
    p = pathlib.Path(path)
    if p.stat().st_size > MAX_FILE:
        raise ValueError(f'fichier trop grand pour un bloc ({p.stat().st_size // 1000} ko, '
                         f'{MAX_FILE // 1000} ko au plus)')
    raw = p.read_bytes()
    for enc in ('utf-8-sig', 'cp1252', 'latin-1'):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    return Entry(name=p.stem, text=text.replace('\r\n', '\n'), path=str(p.parent.name), note=str(p),
                 catalog='Fichier')


def operation_of(entry: Entry):
    """L'opération (instruction machine) créée pour une entrée."""
    from . import model
    from .instructions import INSTRUCTIONS
    key = entry.instruction if entry.instruction in INSTRUCTIONS else 'bloc'
    if key == 'bloc':
        params = {'texte': entry.lines()}
        names = [str(n) for n in entry.names[:6]]
        if names:
            params['noms'] = ';'.join(names)
        for k, v in enumerate(entry.values[:6], start=1):
            try:
                params[f'p{k}'] = float(v)
            except (TypeError, ValueError):
                continue
    else:
        params = dict(entry.params)
    return model.Operation(name=entry.name, kind='instruction', instruction=key, params=params)
