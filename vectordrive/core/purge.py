"""Purger (comme PURGER en DAO) : ce qui encombre le dessin sans rien
graver — formes sans contour ou faites de contours vides, textes vides,
groupes vides (une fois leur contenu purgé), calques vides (le calque actif
et le dernier calque restent).
"""
from __future__ import annotations

from .document import Group, Shape, Text


def _empty(it) -> bool:
    if isinstance(it, Shape):
        return not any(c.segments for c in it.path.contours)
    if isinstance(it, Text):
        return not it.text.strip()
    if isinstance(it, Group):
        return not it.children
    return False


def _clean(items: list, counts: dict) -> list:
    out = []
    for it in items:
        if isinstance(it, Group):
            it.children = _clean(it.children, counts)
        if _empty(it):
            key = 'groupes' if isinstance(it, Group) else 'objets'
            counts[key] = counts.get(key, 0) + 1
            continue
        out.append(it)
    return out


def purge(doc) -> dict:
    """Purge le document en place ; rend {'objets', 'groupes', 'calques'}."""
    counts = {'objets': 0, 'groupes': 0, 'calques': 0}
    for L in doc.layers:
        L.items = _clean(L.items, counts)
    active = getattr(doc, 'active_layer', None)
    keep = [L for L in doc.layers if L.items or L is active]
    if not keep and doc.layers:
        keep = [doc.layers[0]]
    counts['calques'] = len(doc.layers) - len(keep)
    doc.layers[:] = keep
    return counts
