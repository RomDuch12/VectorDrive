"""L'affichage d'un arbre d'outils, retenu (demande du 15/11, 23 h 45 : « bibli tools garde le dernier affichage ») :
dossiers ouverts ou fermés, ligne choisie, ligne du haut de la vue. Les lignes sont reconnues par leur chemin (les
textes des dossiers sans leurs comptes, l'identifiant des outils), pas par leur place : l'arbre peut avoir changé
depuis (outils ajoutés, dossiers renommés) ; ce qui n'est plus là est laissé de côté, ce qui est nouveau garde
l'affichage d'office."""
from __future__ import annotations

import json
import re

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QAbstractItemView

#: la clé d'un outil (son identifiant) sur sa ligne, dans les arbres d'outils
ROLE = Qt.ItemDataRole.UserRole
#: « 📁 Cyl 3  (12) » : le compte, qui change avec les filtres
_COUNT = re.compile(r'\s{2}\(\d+\)$')
#: « 📚 Mes outils  —  Proposés pour : Gravure  (4) » : la stratégie choisie dans les filtres
_SUFFIX = re.compile(r'\s{2}—\s{2}.*$')


def _part(it) -> str:
    key = it.data(0, ROLE)
    if key and not it.childCount():
        return '#' + str(key)
    return _COUNT.sub('', _SUFFIX.sub('', it.text(0).strip())).strip()


def key_of(it) -> tuple:
    """Le chemin de la ligne `it` : celui de ses dossiers, puis elle."""
    parts = []
    while it is not None:
        parts.append(_part(it))
        it = it.parent()
    return tuple(reversed(parts))


def items(tree):
    """Toutes les lignes de `tree`, parents avant enfants, dans l'ordre de l'arbre (lignes cachées comprises).
    Jamais par `QTreeWidgetItemIterator` : PySide attache chaque itérateur à son arbre, pour toute la vie de l'arbre ;
    arrêté au milieu (une recherche qui trouve sa ligne), il garde l'adresse d'une ligne que `clear()` détruit sans
    le prévenir, et le `clear()` suivant plante une fois sur vingt (violation d'accès ; essais sous charge du 16/11).
    Une liste d'attente de lignes : rien n'est gardé dans Qt."""
    stack = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount() - 1, -1, -1)]
    while stack:
        it = stack.pop()
        yield it
        stack.extend(it.child(i) for i in range(it.childCount() - 1, -1, -1))


_items = items


def capture(tree) -> dict:
    """L'affichage de `tree` : {'ouverts', 'fermes' : chemins des dossiers, 'choisi', 'haut' : chemin ou None}."""
    opened, closed = [], []
    for node in _items(tree):
        if node.childCount():
            (opened if node.isExpanded() else closed).append(list(key_of(node)))
    cur = tree.currentItem()
    top = tree.itemAt(2, 2)                              # la première ligne en vue (coordonnées de la zone visible)
    return {'ouverts': opened, 'fermes': closed, 'choisi': list(key_of(cur)) if cur is not None else None,
            'haut': list(key_of(top)) if top is not None else None}


def find(tree, key):
    """La ligne de chemin `key` (None : plus là)."""
    if not key:
        return None
    key = tuple(key)
    return next((it for it in _items(tree) if key_of(it) == key), None)


def _scroll(tree, key) -> None:
    """La ligne `key` en haut de la vue, puis la ligne choisie en vue (celle d'une commande faite juste après le
    remplissage, ou l'outil de l'opération, ne sort pas de la vue)."""
    it = find(tree, key)
    if it is not None:
        tree.scrollToItem(it, QAbstractItemView.ScrollHint.PositionAtTop)
    cur = tree.currentItem()
    p = cur.parent() if cur is not None else None
    while p is not None and p.isExpanded():
        p = p.parent()
    if cur is not None and not cur.isHidden() and p is None:   # (dans un dossier fermé : laissé fermé)
        tree.scrollToItem(cur, QAbstractItemView.ScrollHint.EnsureVisible)


def restore(tree, state, *, current: bool = True, reveal: bool = False) -> bool:
    """Remet l'affichage `state` (de `capture`) sur `tree` : la ligne choisie (`current`), les dossiers ouverts ou
    fermés, la ligne du haut ; `reveal` : les dossiers de la ligne choisie ouverts (l'outil d'une opération, en vue).
    Rend False sans affichage retenu."""
    if not isinstance(state, dict) or not state:
        return False
    if current and state.get('choisi'):
        hit = find(tree, state['choisi'])
        if hit is not None:
            tree.setCurrentItem(hit)
    opened = {tuple(k) for k in state.get('ouverts') or [] if isinstance(k, list)}
    closed = {tuple(k) for k in state.get('fermes') or [] if isinstance(k, list)}
    for node in _items(tree):
        if not node.childCount():
            continue
        k = key_of(node)
        if k in opened:
            node.setExpanded(True)
        elif k in closed:
            node.setExpanded(False)
    if reveal and tree.currentItem() is not None:
        p = tree.currentItem().parent()
        while p is not None:
            p.setExpanded(True)
            p = p.parent()
    top = state.get('haut')
    if top:
        _scroll(tree, top)                               # tout de suite, puis une fois la fenêtre montrée et à sa taille
        QTimer.singleShot(0, tree, lambda: _scroll(tree, top))
    return True


def load(settings, key: str):
    """L'affichage retenu sous `key` (None : aucun)."""
    if settings is None:
        return None
    try:
        v = json.loads(str(settings.value(key, '') or '{}'))
    except ValueError:
        return None
    return v if isinstance(v, dict) and v else None


def save(settings, key: str, state) -> None:
    if settings is not None and isinstance(state, dict) and state:
        settings.setValue(key, json.dumps(state, ensure_ascii=False))
