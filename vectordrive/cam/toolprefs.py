"""Outils proposés pour chaque type d'opération.

Pour chaque stratégie (gravure, poche, perçage…), une liste ordonnée de
règles dit quels outils proposer, et dans quel ordre :

- ``{'type': 'nature', 'value': 'conique'}`` : les outils de cette nature ;
- ``{'type': 'dossier', 'value': 'Datron/Fraises'}`` : les outils d'un dossier
  de Mes outils (sous-dossiers compris) ;
- ``{'type': 'outil', 'value': <id>, 'name': …, 'diameter': …, 'ref': …}`` :
  un outil précis (retrouvé aussi dans le document, où sa copie a un autre id).

Un outil prend le rang de la première règle qu'il remplit ; dans une même
règle, l'ordre suit ``sort`` (bibliothèque, Ø croissant, Ø décroissant).
``mode`` : 'devant' (les outils adaptés en tête, puis les autres) ou 'seuls'
(seulement les outils adaptés).

Les réglages sont rangés dans le fichier de réglages (clé
``fao/outils_par_operation``, en JSON) ; une stratégie absente garde le
réglage par défaut (DEFAULTS). Qui s'en sert : voir ``USED_BY``.
"""
from __future__ import annotations

import json

from . import toollib

KEY = 'fao/outils_par_operation'
RULE_TYPES = {'nature': 'Nature d\'outil', 'dossier': 'Dossier de Mes outils', 'outil': 'Outil précis'}
SORTS = {'biblio': 'Ordre de la bibliothèque', 'd_asc': 'Ø croissant', 'd_desc': 'Ø décroissant'}
MODES = {'devant': 'Outils adaptés en tête, puis les autres', 'seuls': 'Seulement les outils adaptés'}

#: où le logiciel propose des outils, et sous quelle forme
USED_BY = (
    ('Formulaire d\'une opération (Nouvelle opération, Modifier, parcours de la palette)',
     'liste « Outil » : outils du document dans cet ordre (mode « seulement » : les autres cachés) ; '
     'réglage enregistré : les premiers outils adaptés de Mes outils ensuite, avant « Choisir dans Mes outils… »'),
    ('Fenêtre « Choisir un outil »', 'case « Seulement les outils adaptés » ; réglage enregistré : groupe '
     '« Proposés pour … » en tête ; bouton « Régler les propositions… »'),
    ('Boutons de la palette Parcours', 'outil pris d\'office : le premier proposé (document, puis Mes outils) '
     'quand la stratégie a des réglages enregistrés'),
    ('Bibliothèque d\'outils', 'filtre « Adaptés à » : les outils proposés pour une stratégie, dans leur ordre'),
    ('Relief > Outil (dilatation au profil de l\'outil)', 'liste des outils de Mes outils, dans l\'ordre du relief 3D'),
)


def _n(*kinds: str) -> list[dict]:
    return [{'type': 'nature', 'value': k} for k in kinds]


#: réglages par défaut (ceux qu'appliquait le logiciel avant d'être réglable)
DEFAULTS: dict[str, dict] = {
    'gravure': {'rules': _n('conique', 'fraise', 'boule', 'profil')},
    'contour': {'rules': _n('fraise', 'boule')},
    'poche': {'rules': _n('fraise', 'boule')},
    'percage': {'rules': _n('foret', 'fraise')},
    'vcarve': {'rules': _n('conique')},
    'prismatique': {'rules': _n('conique')},
    'vinyle': {'rules': _n('couteau'), 'mode': 'seuls'},
    'chanfrein_bord': {'rules': _n('conique')},
    'fer_dorer': {'rules': _n('profil', 'conique', 'boule')},
    'decoupe3d': {'rules': _n('conique')},
    'reste': {'rules': _n('fraise', 'boule'), 'sort': 'd_asc'},
    'relief': {'rules': _n('boule', 'conique', 'fraise')},
    'surface3d': {'rules': _n('boule', 'fraise', 'conique')},
    'ebauche3d': {'rules': _n('fraise', 'boule'), 'sort': 'd_desc'},
    'reprise3d': {'rules': _n('fraise', 'boule'), 'sort': 'd_asc'},
    'niveaux3d': {'rules': _n('boule', 'fraise')},
    'finition25d': {'rules': _n('boule', 'conique', 'fraise')},
    'laser': {'rules': _n('laser'), 'mode': 'seuls'},
    'laser_decoupe': {'rules': _n('laser'), 'mode': 'seuls'},
    'laser_gravure': {'rules': _n('laser'), 'mode': 'seuls'},
    'taraudage': {'rules': _n('fraise')},
    'percage_fraise': {'rules': _n('fraise')},
    'chanfrein': {'rules': _n('conique')},
    'surfacage': {'rules': _n('fraise'), 'sort': 'd_desc'},
    'instruction': {'rules': []},
    'texte_machine': {'rules': _n('conique', 'fraise')},
}


def normalized(p: dict | None) -> dict:
    p = dict(p or {})
    rules = [dict(r) for r in p.get('rules') or [] if isinstance(r, dict) and r.get('type') in RULE_TYPES]
    return {'rules': rules, 'mode': p.get('mode') if p.get('mode') in MODES else 'devant',
            'sort': p.get('sort') if p.get('sort') in SORTS else 'biblio'}


def default_for(kind: str) -> dict:
    return normalized(DEFAULTS.get(kind, {'rules': []}))


def load(settings) -> dict[str, dict]:
    """Réglages enregistrés {stratégie: réglage} (sans les défauts)."""
    if settings is None:
        return {}
    raw = settings.value(KEY, '')
    try:
        data = json.loads(raw) if isinstance(raw, str) and raw else (raw if isinstance(raw, dict) else {})
    except ValueError:
        return {}
    return {k: normalized(v) for k, v in data.items() if isinstance(v, dict)}


def save(settings, prefs: dict[str, dict]) -> None:
    """Enregistre les réglages qui diffèrent des défauts."""
    keep = {k: normalized(v) for k, v in prefs.items() if normalized(v) != default_for(k)}
    settings.setValue(KEY, json.dumps(keep, ensure_ascii=False))


def pref_for(kind: str, prefs: dict | None = None) -> dict:
    p = (prefs or {}).get(kind)
    return normalized(p) if p is not None else default_for(kind)


def customized(kind: str, prefs: dict | None) -> bool:
    return bool(prefs) and kind in prefs and normalized(prefs[kind]) != default_for(kind)


def tool_rule(t) -> dict:
    """Règle « outil précis » pour `t`."""
    return {'type': 'outil', 'value': t.id, 'name': t.name, 'diameter': float(t.diameter), 'ref': t.ref,
            'kind': t.kind}


def matches(rule: dict, t) -> bool:
    typ, v = rule.get('type'), rule.get('value')
    if typ == 'nature':
        return t.kind == v
    if typ == 'dossier':
        return bool(getattr(t, 'folder', '')) and toollib.in_folder(t, str(v))
    if typ == 'outil':
        if t.id == v:
            return True
        ref = str(rule.get('ref') or '').strip().lower()
        if ref and t.ref.strip().lower() == ref:
            return True
        return (str(rule.get('name') or '').strip().lower() == t.name.strip().lower()
                and abs(float(rule.get('diameter') or 0) - t.diameter) < 1e-3)
    return False


def rank_of(t, pref: dict) -> int | None:
    """Rang de la première règle remplie par `t` (None : aucune)."""
    return next((i for i, r in enumerate(pref['rules']) if matches(r, t)), None)


def ordered(tools, kind: str, prefs: dict | None = None, *, only: bool | None = None) -> list:
    """Outils dans l'ordre proposé pour la stratégie `kind` ; `only` (par
    défaut : le mode du réglage) ne garde que les outils adaptés. Sans
    règle, tous les outils sont adaptés, dans leur ordre."""
    pref = pref_for(kind, prefs)
    tools = list(tools)
    if not pref['rules']:
        return tools
    if only is None:
        only = pref['mode'] == 'seuls'
    pos = {id(t): i for i, t in enumerate(tools)}

    def within(t):
        if pref['sort'] == 'd_asc':
            return t.diameter
        if pref['sort'] == 'd_desc':
            return -t.diameter
        return 0.0
    ranked = [(rank_of(t, pref), t) for t in tools]
    good = sorted(((r, t) for r, t in ranked if r is not None), key=lambda rt: (rt[0], within(rt[1]), pos[id(rt[1])]))
    out = [t for _r, t in good]
    if not only:
        out += [t for r, t in ranked if r is None]
    return out


def suits(t, kind: str, prefs: dict | None = None) -> bool:
    pref = pref_for(kind, prefs)
    return not pref['rules'] or rank_of(t, pref) is not None


def best(tools, kind: str, prefs: dict | None = None):
    """Premier outil adapté (None : aucun)."""
    return next(iter(ordered(tools, kind, prefs, only=True)), None)


#: outils de Mes outils ajoutés directement à la liste du formulaire (réglage enregistré)
LIST_PROPOSALS = 8


def describe(rule: dict, tr=lambda s: s) -> str:
    """Libellé d'une règle pour les listes."""
    from .model import TOOL_KINDS
    typ, v = rule.get('type'), rule.get('value')
    if typ == 'nature':
        return tr('Nature : {0}').format(tr(TOOL_KINDS.get(v, v)))
    if typ == 'dossier':
        return tr('Dossier : {0}').format(v)
    d = rule.get('diameter')
    return tr('Outil : {0}').format(f'{rule.get("name") or v}' + (f' — Ø {float(d):g}' if d else ''))
