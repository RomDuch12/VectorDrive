"""Opérations d'un plugin dans la liste des opérations FAO (réponse du 17/11 à la question 48 : une liste unique).

Un plugin déclare un fournisseur (`plugins.Api.add_operation_provider`) ; chacune de ses lignes devient ici une
opération machine sans outil — `Operation(kind='instruction', instruction=EXTERNAL)` — qui tient sa place parmi les
opérations, donc dans le programme : ↑ / ↓, la case, l'œil marchent comme pour les autres. Ses réglages restent au
plugin ; l'opération ne garde que de quoi la retrouver et la montrer (`params` : 'provider', 'ref', 'label', 'tool',
'tip'). Son parcours porte un cycle `{'kind': 'instruction', 'name': EXTERNAL, 'params': …}` que le post-processeur du
plugin écrit à son rang ; pour une autre machine, ou sans le plugin, il est vide (et le compte rendu le dit)."""
from __future__ import annotations

#: nom de l'instruction des opérations de plugin
EXTERNAL = 'externe'


def is_external(op) -> bool:
    return getattr(op, 'kind', '') == 'instruction' and getattr(op, 'instruction', '') == EXTERNAL


def ref_of(op) -> str:
    return str((getattr(op, 'params', None) or {}).get('ref', ''))


def providers() -> dict:
    """{clé : fournisseur} des plugins chargés."""
    from .. import plugins
    return dict(getattr(plugins.REGISTRY, 'op_providers', {}) or {})


def provider_of(op):
    return providers().get(str((getattr(op, 'params', None) or {}).get('provider', '')))


def can_rename(op, doc) -> bool:
    """Son plugin renomme-t-il cette opération (`rename`, et `renamable(dessin, ref)` s'il le dit) ?"""
    p = provider_of(op)
    if p is None or not callable(getattr(p, 'rename', None)):
        return False
    if not callable(getattr(p, 'renamable', None)):
        return True
    return bool(call(op, 'renamable', doc, ref_of(op), default=False))


def undo_keys(op) -> tuple:
    """Les réglages du dessin (`doc.extra`) où son plugin garde ses opérations : Ctrl+Z les rend."""
    keys = getattr(provider_of(op), 'undo_keys', ()) or ()
    return tuple(str(k) for k in keys) if isinstance(keys, (tuple, list)) else ()


#: (fournisseur, ses post-processeurs, post-processeur du dessin) → s'il écrit avec lui : une fiche machine se
#: résout en lisant des fichiers, et la liste des opérations se refait souvent
_MATCHES: dict = {}


def post_matches(provider, post_key: str) -> bool:
    """Le fournisseur écrit-il ses opérations avec ce post-processeur (`provider.posts`, vide : avec tous) ? Une
    fiche machine compte pour le post-processeur qu'elle désigne."""
    posts = tuple(getattr(provider, 'posts', ()) or ())
    key = (id(provider), posts, post_key)
    if key not in _MATCHES:
        if len(_MATCHES) > 200:
            _MATCHES.clear()
        _MATCHES[key] = _post_matches(posts, post_key)
    return _MATCHES[key]


def _post_matches(posts: tuple, post_key: str) -> bool:
    if not posts:
        return True
    if not post_key:
        return False
    if post_key in posts:
        return True
    from . import post
    try:
        fn, _machine = post._resolve(post_key)
        table = post._plugin_posts()
    except Exception:                                  # noqa: BLE001 — un plugin en défaut : pas pour cette machine
        return False
    return fn is not None and any((table.get(k) or (None, None))[1] is fn for k in posts)


def active(op, post_key: str) -> bool:
    """L'opération de plugin s'écrit-elle avec ce post-processeur (son plugin chargé, sa machine) ?"""
    p = provider_of(op)
    return p is not None and post_matches(p, post_key)


def call(op, name: str, *args, default=None):
    """`provider.<name>(*args)` du fournisseur de `op` ; `default` s'il n'a pas cette fonction ou s'il est en défaut
    (noté au journal)."""
    p = provider_of(op)
    fn = getattr(p, name, None) if p is not None else None
    if not callable(fn):
        return default
    try:
        return fn(*args)
    except Exception as ex:                            # noqa: BLE001 — un plugin en défaut ne casse pas le panneau
        from .. import journal
        journal.record(type(ex), ex, ex.__traceback__, where=f'opération de plugin : {name}')
        return default


def _rows(provider, doc):
    """Les lignes du fournisseur pour `doc` (chacune un dict avec 'ref') ; None s'il est en défaut (ses opérations
    restent alors comme elles sont)."""
    try:
        rows = list(provider.rows(doc) or [])
    except Exception as ex:                            # noqa: BLE001
        from .. import journal
        journal.record(type(ex), ex, ex.__traceback__, where='opération de plugin : rows')
        return None
    return [r for r in rows if isinstance(r, dict) and str(r.get('ref', '') or '')]


def sync(setup, doc, post_key: str) -> tuple:
    """Les opérations des plugins à jour dans `setup.operations` : une par ligne de chaque fournisseur qui écrit avec
    ce post-processeur — une ligne neuve s'ajoute à la fin (après les opérations du dessin : là où le plugin les
    écrivait jusqu'ici), dans l'ordre du fournisseur, ou à la place de la première ligne du même fournisseur qui
    disparaît en même temps (des lignes remplacées par une autre : la place choisie gardée) ; libellé, outil et bulle suivent la ligne, la case aussi quand le
    plugin la change (`params['on']` : son dernier état vu ; décochée ici, elle le reste) ; une opération
    dont la ligne a disparu (ou en double) est retirée. Celles d'un plugin absent ou d'une autre machine restent (leur
    place revient avec lui) ; elles ne s'écrivent pas. Rend (changé ?, identifiants des opérations retirées)."""
    from . import model
    changed, gone = False, []
    for key, p in providers().items():
        if not post_matches(p, post_key):
            continue
        rows = _rows(p, doc)
        if rows is None:
            continue
        refs = {str(r['ref']) for r in rows}
        seen, keep, slot = set(), [], None
        for o in setup.operations:
            if is_external(o) and str(o.params.get('provider', '')) == key:
                ref = ref_of(o)
                if ref not in refs or ref in seen:
                    gone.append(o.id)
                    changed = True
                    if slot is None and ref not in refs:
                        slot = len(keep)
                    continue
                seen.add(ref)
            keep.append(o)
        setup.operations[:] = keep
        have = {ref_of(o): o for o in setup.operations if is_external(o) and str(o.params.get('provider', '')) == key}
        for r in rows:
            ref = str(r['ref'])
            label = str(r.get('label') or ref)
            on = bool(r.get('enabled', True))
            info = {'provider': key, 'ref': ref, 'label': label, 'tool': str(r.get('tool') or ''),
                    'tip': str(r.get('tip') or ''), 'on': on}
            o = have.get(ref)
            if o is None:
                new = model.Operation(kind='instruction', instruction=EXTERNAL, name=label, params=info, enabled=on)
                if slot is None:
                    setup.operations.append(new)
                else:
                    setup.operations.insert(slot, new)
                    slot += 1
                changed = True
            elif o.params != info or o.name != label:
                if o.params.get('on') != on:             # changée chez le plugin : suivie
                    o.enabled = on
                o.params, o.name = info, label
                changed = True
    return changed, gone


def cycle_of(op, post_key: str):
    """Le cycle du parcours de l'opération de plugin ; None si elle ne s'écrit pas avec ce post-processeur."""
    if not active(op, post_key):
        return None
    return {'kind': 'instruction', 'name': EXTERNAL, 'params': dict(op.params)}


def columns(op) -> tuple:
    """(stratégie, outil, profondeur) montrés dans la liste des opérations : le libellé du fournisseur, l'outil dit
    par lui."""
    p = provider_of(op)
    kind = str(getattr(p, 'label', '') or '') if p is not None else ''
    return kind or 'Plugin', str(op.params.get('tool', '') or '') or '—', '—'
