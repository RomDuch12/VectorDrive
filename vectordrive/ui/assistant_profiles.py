"""Les profils de l'assistant (demande du 20/11, 21 h 48 : « optimiser parametrage utilisation débutant clé en main
et utilisation avancée de l'assistant IA ») : en mode Avancé, des réglages nommés que l'on retrouve d'un clic —
fournisseur, modèles, adresse, tours, outils permis, consignes, Garder ou Défaire. Jamais une clé d'API (elles
restent dans le gestionnaire d'identifiants de Windows), ni une valeur qui en a l'air ; jamais le plafond des dépenses
(un profil ne le lève pas). Retenus dans les réglages (`assistant/profils`,
JSON)."""
from __future__ import annotations

import json

KEY = 'assistant/profils'
#: au plus tant de profils ; de caractères d'un nom
MAX_PROFILES = 30
NAME_MAX = 40
#: les réglages d'un profil (jamais une clé : `agent.keys`)
PROFILE_KEYS = ('assistant/fournisseur', 'assistant/modele_anthropic', 'assistant/modele_openai',
                'assistant/modele_mistral', 'assistant/adresse_mistral', 'assistant/tours_max',
                'assistant/outils_memoire', 'assistant/outils_scripts', 'assistant/outils_fao',
                'assistant/outils_copies', 'assistant/outils_commandes', 'assistant/consignes',
                'assistant/valider')


def clean_name(name) -> str:
    return ' '.join(str(name or '').split())[:NAME_MAX]


def _plain(v):
    """Une valeur des réglages, telle que JSON la garde (QSettings rend parfois des chaînes, parfois des nombres)."""
    if isinstance(v, (bool, int, float, str)) or v is None:
        return v
    return str(v)


def load(settings) -> list:
    """[{'name', 'values'}] dans l'ordre ; un réglage abîmé : aucun profil."""
    raw = settings.value(KEY, '') if settings is not None else ''
    try:
        data = json.loads(raw) if isinstance(raw, str) and raw.strip() else []
    except (ValueError, RecursionError):
        return []
    out, seen = [], set()
    for d in data if isinstance(data, list) else []:
        if not isinstance(d, dict) or not isinstance(d.get('values'), dict):
            continue
        name = clean_name(d.get('name'))
        if not name or name.casefold() in seen:
            continue
        seen.add(name.casefold())
        out.append({'name': name, 'values': {k: _plain(v) for k, v in d['values'].items()
                                             if k in PROFILE_KEYS and v is not None}})
    return out[:MAX_PROFILES]


def save(settings, profiles) -> None:
    data = [{'name': clean_name(p['name']), 'values': {k: _plain(v) for k, v in p['values'].items()
                                                         if k in PROFILE_KEYS}}
            for p in profiles if clean_name(p.get('name'))][:MAX_PROFILES]
    if data:
        settings.setValue(KEY, json.dumps(data, ensure_ascii=False))
    else:
        settings.remove(KEY)


def _secretish(v, secrets) -> bool:
    """Une valeur qui contient une clé retenue, ou qui a la forme d'une clé (« sk-… ») : jamais dans un profil."""
    import re
    if not isinstance(v, str):
        return False
    return any(s and s in v for s in secrets) or re.search(r'(?<![\w-])sk-[A-Za-z0-9_-]{16,}', v) is not None


def capture(settings) -> dict:
    """Les réglages actuels d'un profil (ceux qui ne sont pas posés : absents, la valeur d'office au retour) ; une
    clé collée par erreur dans un champ (modèle, adresse, consignes) : laissée de côté."""
    secrets = []
    try:
        from ..agent import keys
        from ..agent.chat import PROVIDERS
        secrets = [s for s in (keys.load(p) for p in PROVIDERS) if s and len(s) >= 8]
    except Exception:                                    # noqa: BLE001 — sans le gestionnaire : la forme seule
        pass
    out = {}
    for k in PROFILE_KEYS:
        if settings.contains(k):
            v = _plain(settings.value(k))
            if v is not None and not _secretish(v, secrets):
                out[k] = v
    return out


def apply(settings, values: dict) -> None:
    """Les réglages du profil posés ; ceux qu'il n'a pas : remis à leur valeur d'office."""
    for k in PROFILE_KEYS:
        if k in values:
            settings.setValue(k, values[k])
        else:
            settings.remove(k)


def keep(settings, name: str) -> str | None:
    """Les réglages actuels gardés sous `name` (remplace celui du même nom) ; rend le nom gardé, None si refusé."""
    name = clean_name(name)
    if not name:
        return None
    profiles = load(settings)
    rest = [p for p in profiles if p['name'].casefold() != name.casefold()]
    if len(rest) >= MAX_PROFILES:
        return None
    at = next((i for i, p in enumerate(profiles) if p['name'].casefold() == name.casefold()), len(rest))
    rest.insert(min(at, len(rest)), {'name': name, 'values': capture(settings)})
    save(settings, rest)
    return name


def remove(settings, name: str) -> bool:
    profiles = load(settings)
    rest = [p for p in profiles if p['name'].casefold() != clean_name(name).casefold()]
    if len(rest) == len(profiles):
        return False
    save(settings, rest)
    return True


def find(settings, name: str):
    return next((p for p in load(settings) if p['name'].casefold() == clean_name(name).casefold()), None)
