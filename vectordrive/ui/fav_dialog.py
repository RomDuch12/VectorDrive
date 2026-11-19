"""Les favoris dans une fenêtre (demande du 19/11 : « Toolbar d'icones favoris : comment ajouter retirer changer
l'ordre ») : la liste des favoris dans l'ordre de leur barre (glisser une ligne, ou Monter / Descendre ; Retirer), et
toutes les commandes, avec une recherche (double clic, ou « Ajouter ») ; les libellés à côté des icônes. OK retient
(`MainWindow._save_favorites`) ; les favoris d'un plugin absent aujourd'hui sont gardés, au bout."""
from __future__ import annotations

import unicodedata

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QGridLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout)

from ..i18n import tr

KEY = Qt.ItemDataRole.UserRole


def _plain(text: str) -> str:
    """Sans accents ni casse, pour la recherche."""
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if unicodedata.category(c) != 'Mn')


def name(action) -> str:
    return action.text().replace('&', '').strip()


class FavoritesDialog(QDialog):

    def __init__(self, win, parent=None):
        super().__init__(parent or win)
        self.win = win
        self.setWindowTitle(tr('Favoris'))
        self.resize(780, 540)
        lay = QVBoxLayout(self)
        info = QLabel(tr('Les favoris sont la barre de boutons tout en haut (disposition TypeEdit 13 : à la suite de la '
                         'barre d’accès rapide). Ajouter : double clic sur une commande de droite, ou « ← Ajouter ». '
                         'Ranger : glisser une ligne, ou Monter / Descendre. Retirer : double clic sur un favori. Aussi, sans cette fenêtre : clic droit sur '
                         'un bouton du ruban › Ajouter aux favoris (Maj + clic droit pour un outil qui a ses '
                         'réglages) ; clic droit sur un favori › Retirer, ou Agencer les favoris à la souris.'))
        info.setWordWrap(True)
        lay.addWidget(info)
        grid = QGridLayout()
        lay.addLayout(grid, 1)
        grid.addWidget(QLabel(tr('Favoris, dans l’ordre de la barre')), 0, 0)
        grid.addWidget(QLabel(tr('Toutes les commandes')), 0, 2)
        self.favs = QListWidget()
        self.favs.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.favs.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.favs.itemDoubleClicked.connect(lambda _it: self.remove())
        grid.addWidget(self.favs, 1, 0)
        mid = QVBoxLayout()
        self.buttons = {}
        for k, text, slot in (('add', tr('← Ajouter'), lambda: self.add()), ('remove', tr('Retirer'), self.remove),
                              ('up', tr('Monter'), lambda: self.move(-1)), ('down', tr('Descendre'), lambda: self.move(1))):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, s=slot: s())
            mid.addWidget(b)
            self.buttons[k] = b
        mid.addStretch(1)
        grid.addLayout(mid, 1, 1)
        right = QVBoxLayout()
        self.find = QLineEdit()
        self.find.setPlaceholderText(tr('Chercher une commande…'))
        self.find.setClearButtonEnabled(True)
        self.find.textChanged.connect(self._filter)
        right.addWidget(self.find)
        self.all = QListWidget()
        self.all.itemDoubleClicked.connect(lambda it: self.add(it.data(KEY)))
        right.addWidget(self.all, 1)
        grid.addLayout(right, 1, 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(2, 1)
        from . import fav_bar
        self.labels = QCheckBox(tr('Afficher les libellés à côté des icônes'))
        self.labels.setChecked(fav_bar.labels_on(win.settings))
        lay.addWidget(self.labels)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._fill()

    def _row(self, key: str) -> QListWidgetItem:
        a = self.win.A[key]
        it = QListWidgetItem(a.icon(), name(a))
        it.setData(KEY, key)
        tip = (a.toolTip() or '').strip()
        if tip and tip != name(a):
            it.setToolTip(tip)
        return it

    def _fill(self) -> None:
        for k in self.win.favorite_keys():
            self.favs.addItem(self._row(k))
        seen = set()
        rows = []
        for k, a in self.win.A.items():
            if a.isSeparator() or not name(a) or id(a) in seen:
                continue
            seen.add(id(a))
            rows.append((_plain(name(a)), k))
        for _n, k in sorted(rows):
            self.all.addItem(self._row(k))

    def _filter(self, text: str) -> None:
        t = _plain(text.strip())
        for i in range(self.all.count()):
            it = self.all.item(i)
            self.all.setRowHidden(i, bool(t) and t not in _plain(it.text()) and t not in _plain(it.toolTip()))

    def keys(self) -> list:
        return [self.favs.item(i).data(KEY) for i in range(self.favs.count())]

    def add(self, key: str | None = None) -> bool:
        """La commande `key` (sinon celle choisie à droite) au bout des favoris, ou après le favori choisi ; False
        si elle y est déjà."""
        if key is None:
            it = self.all.currentItem()
            key = it.data(KEY) if it is not None and not self.all.isRowHidden(self.all.row(it)) else None
        if not key or key not in self.win.A or self.win.A[key] in {self.win.A[k] for k in self.keys()}:
            return False                                 # la même commande sous une autre clé : déjà là
        at = self.favs.currentRow()
        row = self._row(key)
        if at >= 0:
            self.favs.insertItem(at + 1, row)
        else:
            self.favs.addItem(row)
        self.favs.setCurrentItem(row)
        return True

    def remove(self) -> bool:
        r = self.favs.currentRow()
        if r < 0:
            return False
        self.favs.takeItem(r)
        return True

    def move(self, d: int) -> bool:
        r = self.favs.currentRow()
        if r < 0 or not 0 <= r + d < self.favs.count():
            return False
        it = self.favs.takeItem(r)
        self.favs.insertItem(r + d, it)
        self.favs.setCurrentRow(r + d)
        return True

    def apply(self) -> None:
        """Les favoris retenus (ceux d'un plugin absent aujourd'hui gardés au bout) et les libellés."""
        absent = [k for k in self.win._stored_favorites() if k not in self.win.A]
        self.win._save_favorites(self.keys() + absent)
        self.win.favorite_labels(self.labels.isChecked())
