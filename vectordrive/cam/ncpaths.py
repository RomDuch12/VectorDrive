"""Programmes appelés par un programme machine (appels externes) : leur fichier sur ce poste.

Un programme écrit pour la machine désigne les programmes qu'il appelle par leur chemin VU DE LA
MACHINE (lecteur réseau de la commande…). Le réglage « fao/chemins_programmes » (F10 › FAO) donne les
correspondances « chemin machine = chemin du poste », séparées par des points-virgules ; un plugin
peut en fournir la valeur par défaut. À défaut, le fichier est cherché tel quel, puis à côté du
programme qui l'appelle."""
from __future__ import annotations

import os
import pathlib

KEY = 'fao/chemins_programmes'
#: recherche d'une copie locale : dossiers parents de l'appelant, fin du chemin machine (dossiers + nom)
ANCESTORS, SUFFIX_PARTS = 4, 4


def mappings(text: str | None = None) -> list[tuple[str, str]]:
    """[(préfixe machine, préfixe du poste)] du réglage (ou de `text`)."""
    if text is None:
        from ..ui.options import value
        from ..portable import settings
        text = value(settings(), KEY)
    out = []
    for part in str(text or '').split(';'):
        if '=' not in part:
            continue
        machine, local = part.split('=', 1)
        machine, local = _norm(machine.strip()), _norm(local.strip())
        if machine:
            out.append((machine, local))
    return out


def _norm(path: str) -> str:
    return path.replace('/', '\\').rstrip('\\')


def candidates(path: str, caller: str | None = None, rules=None) -> list[str]:
    """Fichiers possibles, dans l'ordre : correspondances, chemin tel quel, à côté de l'appelant."""
    raw = _norm(path.strip().strip('"').replace('\\\\', '\\'))
    out = []
    for machine, local in (mappings() if rules is None else rules):
        if raw.lower().startswith(machine.lower()):
            out.append(local + raw[len(machine):])
    out.append(raw)
    if caller:
        name = raw.rsplit('\\', 1)[-1].split(':')[-1]
        here = pathlib.Path(caller).parent
        out.append(str(here / name))
        # copie locale des programmes de la machine : un dossier parent de l'appelant et la fin du
        # chemin machine (« T:\RomDuch\Tranch\Date.simpl » → <parent>\Tranch\Date.simpl)
        parts = [p for p in raw.split('\\') if p and not p.endswith(':')][-SUFFIX_PARTS:]
        for anc in list(here.parents)[:ANCESTORS]:
            for k in range(len(parts), 1, -1):
                out.append(str(anc.joinpath(*parts[-k:])))
        for anc in list(here.parents)[:ANCESTORS]:
            out.append(str(anc / name))
    seen, res = set(), []
    for c in out:
        k = os.path.normcase(c)
        if c and k not in seen:
            seen.add(k)
            res.append(c)
    return res


def to_machine(path: str, rules=None) -> str:
    """Chemin du poste écrit pour la machine (programme appelé) : le préfixe du poste d'une
    correspondance remplacé par celui de la machine (sans casse, « / » ou « \\ ») ; sinon tel quel."""
    raw = _norm(str(path or '').strip().strip('"'))
    for machine, local in (mappings() if rules is None else rules):
        if local and (raw.lower() == local.lower() or raw.lower().startswith(local.lower() + '\\')):
            rest = raw[len(local):].lstrip('\\')
            return machine + '\\' + rest if rest else machine
    return raw


def resolve(path: str, caller: str | None = None, rules=None) -> str | None:
    """Le fichier du programme appelé sur ce poste, ou None s'il est introuvable."""
    import time
    for c in candidates(path, caller, rules):
        server = c[2:].split('\\', 1)[0].lower() if c.startswith('\\\\') else ''
        if server and time.monotonic() - _DOWN.get(server, -1e9) < DOWN_S:
            continue                                     # partage injoignable il y a peu : pas d'attente
        t0 = time.monotonic()
        try:
            if os.path.isfile(c):
                return c
        except (OSError, ValueError):
            pass
        if server and time.monotonic() - t0 > SLOW_S:      # échec lent : serveur hors d'atteinte
            _DOWN[server] = time.monotonic()
    return None


#: serveurs réseau injoignables (atelier hors d'atteinte) : sautés pendant DOWN_S secondes
_DOWN: dict = {}
DOWN_S, SLOW_S = 60.0, 0.5
