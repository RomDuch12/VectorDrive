"""Filtre de sélection (TypeEdit : F9) : seules les natures d'objets choisies
se sélectionnent — courbes fermées, courbes ouvertes, textes, textes en
colonnes, images, codes à barres, cotations, cadrans et règles.

Un objet spécial (code, cotation, cadran…) a sa nature, même s'il est fait
de courbes ; un groupe ordinaire passe le filtre si tout ce qu'il contient
le passe (comme TypeEdit, un mélange de natures qui n'est pas entièrement
choisi n'est pas pris).
"""
from __future__ import annotations

from .document import Group, Image, Shape, Text

#: nature → libellé (dans l'ordre de la fenêtre)
KINDS = {
    'closed': 'Courbes fermées',
    'open': 'Courbes ouvertes',
    'text': 'Textes',
    'columns': 'Textes en colonnes',
    'image': 'Images',
    'barcode': 'Codes à barres',
    'dimension': 'Cotations',
    'dial': 'Cadrans et règles',
}
_SPECIAL = (('barcode', ('barcode', 'typeedit_barcode')), ('dimension', ('cotation',)),
            ('dial', ('dial', 'typeedit_cadran', 'graduation')))


def kind_of(it) -> str | None:
    """Nature d'un objet qui en a une seule (None : groupe ordinaire)."""
    extra = getattr(it, 'extra', None) or {}
    for kind, keys in _SPECIAL:
        if any(k in extra for k in keys):
            return kind
    if isinstance(it, Image):
        return 'image'
    if isinstance(it, Text):
        return 'columns' if extra.get('box') else 'text'
    if isinstance(it, Shape):
        cs = it.path.contours
        return 'closed' if cs and all(c.closed for c in cs) else 'open'
    return None


def kinds_of(it) -> set:
    """Natures d'un objet ; un groupe ordinaire : celles de son contenu."""
    k = kind_of(it)
    if k is not None:
        return {k}
    if isinstance(it, Group):
        out = set()
        for ch in it.children:
            out |= kinds_of(ch)
        return out
    return set()


def allowed(it, active) -> bool:
    """L'objet se sélectionne-t-il ? `active` : natures choisies, None = pas de filtre."""
    if active is None:
        return True
    ks = kinds_of(it)
    return bool(ks) and ks <= set(active)


def count(items) -> dict:
    """Nombre d'objets de premier niveau par nature (pour la fenêtre)."""
    out = {k: 0 for k in KINDS}
    for it in items:
        for k in kinds_of(it):
            out[k] = out.get(k, 0) + 1
    return out
