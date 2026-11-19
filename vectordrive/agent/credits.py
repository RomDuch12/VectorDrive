"""Les crédits de l'assistant IA (demande du 19/11 midi : « un système de gestion des crédits par session,
onglet_fichier, retenu dans .vdz si dépenses >0 ») : ce que coûtent les demandes, en jetons et en argent.

- Chaque tour du modèle rend ses jetons (`agent.chat`, `on_usage`) : entrée, sortie, entrée lue en cache, entrée
  écrite en cache.
- Le prix d'un modèle : par million de jetons (entrée, sortie, entrée lue en cache), d'office les prix publics
  (`PRICES`, à vérifier sur la page du fournisseur), modifiables dans les options (`assistant/prix`) ; un modèle sans
  prix compte ses jetons seulement.
- Les totaux : un dictionnaire (`add` en rend un neuf, jamais modifié en place : un enregistrement en fond peut
  lire l'ancien) — celui de la session (le panneau), celui du dessin (`doc.extra[KEY]`, posé à la première dépense,
  donc retenu dans le .vdz seulement s'il y en a eu).

    t = add(None, 'mistral', 'mistral-large-latest', {'in': 1200, 'out': 300}, prices(settings))
    t['cout'], t['entree'], t['par_modele']['mistral:mistral-large-latest']['tours']
"""
from __future__ import annotations

import json

#: clé de `doc.extra` : les dépenses du dessin
KEY = 'ia_credits'
#: réglages : les prix (JSON {"fournisseur:modèle": [entrée, sortie, cache]}), leur devise, le plafond par session
KEY_PRICES = 'assistant/prix'
KEY_CURRENCY = 'assistant/devise'
KEY_CAP = 'assistant/plafond_session'
#: prix d'office, par million de jetons : (entrée, sortie, entrée lue en cache) — prix publics relevés le 19/11/2026,
#: en dollars, à vérifier sur la page du fournisseur (docs.mistral.ai/platform/pricing pour Mistral : les sources
#: diffèrent, le plus haut est pris) ; ChatGPT : pas de prix sûr, à remplir
PRICES = {
    'mistral:mistral-large-latest': (2.0, 6.0, 2.0),
    'mistral:mistral-medium-latest': (1.5, 7.5, 1.5),
    'mistral:mistral-small-latest': (0.2, 0.6, 0.2),
    'anthropic:claude-opus-5-5': (4.0, 20.0, 0.20),
    'anthropic:claude-sonnet-5-5': (2.0, 10.0, 0.10),
    'anthropic:claude-haiku-5-5': (0.10, 0.50, 0.01),
}
#: l'écriture en cache (Claude) : 1,25 × le prix d'entrée (cache de 5 minutes)
CACHE_WRITE = {'anthropic': 1.25}
#: les compteurs d'un total
FIELDS = ('entree', 'sortie', 'cache', 'ecrit', 'tours')


def model_key(provider: str, model: str) -> str:
    return f'{provider}:{(model or "").strip()}'


def prices(settings=None) -> dict:
    """Les prix : ceux des réglages (s'ils y sont, même vides : l'utilisateur a pu en retirer), sinon `PRICES`."""
    raw = settings.value(KEY_PRICES, '') if settings is not None else ''
    if not raw:
        return dict(PRICES)
    try:
        got = json.loads(str(raw))
    except ValueError:
        return dict(PRICES)
    out = {}
    if isinstance(got, dict):
        for k, v in got.items():
            try:
                p = tuple(max(0.0, float(x)) for x in list(v)[:3])
            except (TypeError, ValueError):
                continue
            if len(p) == 2:
                p = p + (p[0],)
            if len(p) == 3 and ':' in str(k):
                out[str(k)] = p
    return out


def save_prices(settings, table: dict) -> None:
    settings.setValue(KEY_PRICES, json.dumps({k: list(v) for k, v in table.items()}, ensure_ascii=False))


def currency(settings=None) -> str:
    return str((settings.value(KEY_CURRENCY, '$') if settings is not None else '$') or '$').strip() or '$'


def cap(settings=None) -> float:
    try:
        return max(0.0, float(settings.value(KEY_CAP, 0.0) or 0.0)) if settings is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def normal(usage: dict) -> dict:
    """Les jetons d'un tour : 'in' (entrée hors cache), 'out', 'cache' (lue en cache), 'write' (écrite en cache)."""
    def n(k):
        try:
            return max(0, int(usage.get(k) or 0))
        except (TypeError, ValueError):
            return 0
    return {k: n(k) for k in ('in', 'out', 'cache', 'write')}


def cost(provider: str, model: str, usage: dict, table: dict) -> float | None:
    """Le prix d'un tour ; None si le modèle n'a pas de prix."""
    p = table.get(model_key(provider, model))
    if p is None:
        return None
    u = normal(usage)
    write = CACHE_WRITE.get(provider, 1.0)
    return (u['in'] * p[0] + u['out'] * p[1] + u['cache'] * p[2] + u['write'] * p[0] * write) / 1e6


def _blank() -> dict:
    return {**{k: 0 for k in FIELDS}, 'cout': 0.0}


def _clean(d) -> dict:
    out = _blank()
    if isinstance(d, dict):
        for k in FIELDS:
            try:
                out[k] = max(0, int(d.get(k) or 0))
            except (TypeError, ValueError):
                pass
        try:
            out['cout'] = max(0.0, float(d.get('cout') or 0.0))
        except (TypeError, ValueError):
            pass
    return out


def add(total, provider: str, model: str, usage: dict, table: dict, money: str = '$') -> dict:
    """Un tour ajouté au total `total` (None : le premier) ; rend un total neuf : compteurs, coût, devise, les modèles
    sans prix, et le détail par modèle."""
    u = normal(usage)
    c = cost(provider, model, u, table)
    out = _clean(total)
    by = {k: _clean(v) for k, v in ((total or {}).get('par_modele') or {}).items()} if isinstance(total, dict) else {}
    key = model_key(provider, model)
    one = by.get(key, _blank())
    for t in (out, one):
        t['entree'] += u['in']
        t['sortie'] += u['out']
        t['cache'] += u['cache']
        t['ecrit'] += u['write']
        t['tours'] += 1
        t['cout'] += c or 0.0
    by[key] = one
    out['par_modele'] = by
    out['devise'] = money
    unpriced = set((total or {}).get('sans_prix') or ()) if isinstance(total, dict) else set()
    if c is None:
        unpriced.add(key)
    if unpriced:
        out['sans_prix'] = sorted(unpriced)
    return out


def tokens(total) -> int:
    t = _clean(total)
    return t['entree'] + t['sortie'] + t['cache'] + t['ecrit']


def spent(total) -> bool:
    """Y a-t-il eu une dépense (des jetons) ?"""
    return tokens(total) > 0


def money_text(value: float, money: str, sep: str = ',') -> str:
    """0,0123 $ : quatre chiffres après la virgule sous un centime, deux au-delà."""
    s = f'{value:.4f}' if value < 0.01 else f'{value:.2f}'
    return f'{s.replace(".", sep)} {money}'


def tokens_text(n: int) -> str:
    return f'{n:,}'.replace(',', ' ')
