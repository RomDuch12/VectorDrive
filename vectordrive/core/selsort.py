"""Opérateurs et classement de la sélection (TypeEdit : Modes de sélection).

Opérateurs — ce que devient la sélection S quand on clique ou tire un
rectangle sur les objets P :
- standard : S = P (Ctrl : bascule chaque objet de P) ;
- zone : S = P (remplacement, Ctrl sans effet) ;
- ajout : S ∪ P ; désélection : S − P ; garder : S ∩ P.

Classement — l'ordre des objets sélectionnés (celui du dessin, donc de
l'usinage) : en rangées (X dans un sens puis Y) ou en colonnes (Y puis X),
dans un sens ou en zig-zag, depuis le coin haut gauche ou un autre ; ou inversé.
"""
from __future__ import annotations

OPERATORS = {
    'standard': 'Sélection standard (Ctrl : ajouter ou retirer)',
    'zone': 'Sélection par zone (remplace)',
    'ajout': 'Ajout à la sélection',
    'retrait': 'Désélection',
    'garder': 'Garder dans la sélection (intersection)',
}
SORTS = {
    'h': 'Rangées, dans un sens',
    'hz': 'Rangées, en zig-zag',
    'v': 'Colonnes, dans un sens',
    'vz': 'Colonnes, en zig-zag',
    'inverse': 'Inverser l\'ordre',
}


def combine(selection: list, picked: list, op: str = 'standard', ctrl: bool = False) -> list:
    """Nouvelle sélection selon l'opérateur (ordre gardé, sans doublon)."""
    ids = {id(x) for x in selection}
    pids = {id(x) for x in picked}
    if op == 'ajout':
        return selection + [x for x in picked if id(x) not in ids]
    if op == 'retrait':
        return [x for x in selection if id(x) not in pids]
    if op == 'garder':
        return [x for x in selection if id(x) in pids]
    if op == 'standard' and ctrl:                        # bascule
        return [x for x in selection if id(x) not in pids] + [x for x in picked if id(x) not in ids]
    return list(picked)


def _center(it):
    b = it.bbox()
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2, b[2] - b[0], b[3] - b[1]) if b else (0.0, 0.0, 0.0, 0.0)


def _bands(items: list, axis: int) -> list[list]:
    """Rangées (axis = 1 : même Y) ou colonnes (axis = 0 : même X) : deux
    objets sont de la même bande si leurs centres sont plus proches que la
    moitié de la taille médiane."""
    if not items:
        return []
    c = {id(it): _center(it) for it in items}
    sizes = sorted(c[id(it)][3 if axis == 1 else 2] for it in items)
    tol = max(sizes[len(sizes) // 2] / 2, 1e-6)
    # rangées de haut en bas (Y décroissant), colonnes de gauche à droite
    order = sorted(items, key=lambda it: -c[id(it)][1] if axis == 1 else c[id(it)][0])
    bands, ref = [], None
    for it in order:
        v = c[id(it)][axis]
        if ref is None or abs(v - ref) > tol:
            bands.append([it])
            ref = v
        else:
            bands[-1].append(it)
    return bands


def sort(items: list, mode: str, *, from_right: bool = False, from_bottom: bool = False) -> list:
    """Objets dans l'ordre du classement `mode` (SORTS), depuis le coin haut gauche, ou celui que disent `from_right` et
    `from_bottom`."""
    if mode == 'inverse':
        return list(reversed(items))
    if mode not in SORTS:
        return list(items)
    rows = mode in ('h', 'hz')
    bands = _bands(items, 1 if rows else 0)
    if from_bottom if rows else from_right:
        bands.reverse()
    out = []
    for k, band in enumerate(bands):
        # rangée : de gauche à droite ; colonne : de haut en bas, sauf si le coin de départ dit l'autre sens
        back = from_right if rows else from_bottom
        band = sorted(band, key=lambda it: _center(it)[0] if rows else -_center(it)[1], reverse=back)
        if mode in ('hz', 'vz') and k % 2:
            band.reverse()
        out += band
    return out


def apply_order(doc, ordered: list) -> int:
    """Range les objets dans cet ordre, chacun dans son plan, aux places
    qu'occupaient les objets choisis ; rend le nombre d'objets déplacés."""
    moved = 0
    for L in doc.layers:
        ids = {id(it) for it in ordered}
        slots = [i for i, it in enumerate(L.items) if id(it) in ids]
        if not slots:
            continue
        mine = {id(it) for it in L.items}
        seq = [it for it in ordered if id(it) in mine]
        for i, it in zip(slots, seq):
            if L.items[i] is not it:
                moved += 1
            L.items[i] = it
    return moved
