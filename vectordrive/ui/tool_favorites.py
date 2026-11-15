"""Outils favoris (demande du 15/11) : une étoile devant chaque outil des listes d'outils ; les outils étoilés
remontent en tête de liste, dans un groupe « ★ Favoris » qu'on plie et déplie, dans l'ordre qu'on leur donne à la
souris (glisser dans le groupe).

Un favori est retenu par sa clé (`cam.toollib.favorite_key` : sa référence, sinon son nom, sa nature et ses cotes)
dans les réglages (« outils/favoris », en JSON) : il reste favori d'une ouverture à l'autre, quelle que soit la
bibliothèque qui le fournit (Mes outils, un plugin, le document).
"""
from __future__ import annotations

import json

from PySide6.QtCore import QEvent, QRect, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem, QTreeWidget

from ..cam import toollib

#: réglage : les clés des favoris, dans leur ordre (liste JSON)
KEY = 'outils/favoris'
#: réglage : groupe « Favoris » déplié
OPEN_KEY = 'outils/favoris_ouvert'
#: donnée d'une ligne d'outil : vrai (favori), faux (pas favori) ; rien : pas d'étoile (dossier, groupe)
STAR_ROLE = Qt.ItemDataRole.UserRole + 20
#: largeur de l'étoile, en pixels
WIDTH = 18
#: couleur d'une étoile allumée
GOLD = QColor('#e0a800')


def load(settings) -> list[str]:
    """Les clés des favoris, dans leur ordre ([] : aucun, réglages absents ou illisibles)."""
    if settings is None:
        return []
    raw = settings.value(KEY, '')
    try:
        keys = json.loads(raw) if isinstance(raw, str) and raw else []
    except ValueError:
        return []
    return [str(k) for k in keys if str(k)] if isinstance(keys, list) else []


def save(settings, keys) -> None:
    if settings is not None:
        settings.setValue(KEY, json.dumps(list(dict.fromkeys(str(k) for k in keys)), ensure_ascii=False))


def is_open(settings) -> bool:
    """Groupe « Favoris » déplié (d'office : oui)."""
    return settings is None or settings.value(OPEN_KEY, True) not in (False, 'false', '0', 0)


def set_open(settings, on: bool) -> None:
    if settings is not None:
        settings.setValue(OPEN_KEY, bool(on))


def toggle(settings, t) -> bool:
    """L'outil `t` favori (au bout de la liste), ou plus favori ; rend son nouvel état."""
    keys = load(settings)
    k = toollib.favorite_key(t)
    on = k not in keys
    save(settings, keys + [k] if on else [x for x in keys if x != k])
    return on


def rekey(settings, old: str, new: str, keep: bool = False) -> bool:
    """Un favori dont la clé change (outil renommé, sa référence ou ses cotes changées) le reste, à la même place ;
    `keep` : un autre outil a encore l'ancienne clé (l'original d'une copie modifiée), elle reste favorite et la
    nouvelle prend place juste après. Rend vrai si la liste a changé."""
    keys = load(settings)
    if not old or not new or old == new or old not in keys:
        return False
    if keep:
        if new in keys:
            return False
        i = keys.index(old) + 1
        save(settings, keys[:i] + [new] + keys[i:])
    else:
        save(settings, [new if k == old else k for k in keys])
    return True


def ordered(settings, tools) -> list:
    """Les outils favoris parmi `tools`, dans l'ordre des favoris, chacun une fois (le premier de `tools` : un outil
    du document passe devant sa copie dans une bibliothèque)."""
    by: dict = {}
    for t in tools:
        by.setdefault(toollib.favorite_key(t), t)
    return [by[k] for k in load(settings) if k in by]


def reorder(settings, tools_in_order) -> None:
    """Nouvel ordre des favoris montrés (glissés dans le groupe) ; ceux qui ne sont pas montrés (filtrés, d'une
    autre bibliothèque) gardent leur place."""
    shown = list(dict.fromkeys(toollib.favorite_key(t) for t in tools_in_order))
    keys = load(settings)
    seen, have = set(shown), set(keys)
    new = iter([k for k in shown if k in have])        # autant que de places à reprendre dans `keys`
    out = [next(new) if k in seen else k for k in keys]
    save(settings, out + [k for k in shown if k not in out])


class StarDelegate(QStyledItemDelegate):
    """Étoile devant le nom de chaque outil (colonne 0) : ★ favori, ☆ non ; un clic sur l'étoile émet `toggled`
    avec l'index de la ligne (la liste la bascule, puis se refait)."""

    toggled = Signal(object)

    @staticmethod
    def star_rect(rect: QRect) -> QRect:
        return QRect(rect.left(), rect.top(), WIDTH, rect.height())

    def paint(self, painter, option, index) -> None:                  # noqa: D102 — API Qt
        on = index.data(STAR_ROLE)
        if on is None:
            super().paint(painter, option, index)
            return
        r = self.star_rect(option.rect)
        painter.save()
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(r, option.palette.highlight())
        painter.setPen(GOLD if on else option.palette.color(option.palette.ColorRole.Mid))
        painter.setFont(option.font)
        painter.drawText(r, int(Qt.AlignmentFlag.AlignCenter), '★' if on else '☆')
        painter.restore()
        o = QStyleOptionViewItem(option)
        o.rect = option.rect.adjusted(WIDTH, 0, 0, 0)
        super().paint(painter, o, index)

    def sizeHint(self, option, index):                                 # noqa: N802 — API Qt
        s = super().sizeHint(option, index)
        if index.data(STAR_ROLE) is not None:
            s.setWidth(s.width() + WIDTH)
        return s

    def editorEvent(self, event, model, option, index) -> bool:       # noqa: N802 — API Qt
        if index.data(STAR_ROLE) is None or event.type() not in (
                QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick):
            return super().editorEvent(event, model, option, index)
        if event.button() != Qt.MouseButton.LeftButton or \
                not self.star_rect(option.rect).contains(event.position().toPoint()):
            return super().editorEvent(event, model, option, index)
        if event.type() == QEvent.Type.MouseButtonRelease:
            self.toggled.emit(index)
        return True                                    # sur l'étoile : ni choix de l'outil, ni double clic


class FavoriteTree(QTreeWidget):
    """Arbre d'outils où l'on range les favoris à la souris : seules leurs lignes se glissent, seulement dans le
    groupe « Favoris » (voir `lock_drops`) ; `on_moved` est appelé après chaque dépôt."""

    def __init__(self, on_moved, parent=None):
        super().__init__(parent)
        self._on_moved = on_moved
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def dropEvent(self, ev) -> None:                                   # noqa: N802 — API Qt
        super().dropEvent(ev)
        self._on_moved()


def lock_drops(tree, group, rows, draggable: bool = True) -> None:
    """Seules les lignes `rows` (les favoris) se glissent, et seulement dans `group` (le groupe « Favoris ») : les
    autres lignes, les autres groupes et la racine ne reçoivent rien. `draggable` faux (liste triée par une colonne) :
    rien ne se glisse."""
    root = tree.invisibleRootItem()
    root.setFlags(root.flags() & ~Qt.ItemFlag.ItemIsDropEnabled)
    keep = {id(r) for r in rows} if draggable else set()
    stack = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
    while stack:
        it = stack.pop()
        f = it.flags() & ~(Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled)
        if id(it) in keep:
            f |= Qt.ItemFlag.ItemIsDragEnabled
        if it is group and draggable:
            f |= Qt.ItemFlag.ItemIsDropEnabled
        it.setFlags(f)
        stack.extend(it.child(j) for j in range(it.childCount()))
