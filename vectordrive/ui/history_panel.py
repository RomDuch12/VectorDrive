"""Panneau « Défaire / Refaire » (demande du 15/11, 20 h 02 : « fenetre apposable en colonne : accrochage […]
couleur Défaire/refaire (gauche par défaut) ») : toute la suite des modifications du dessin, celle où l'on est mise
en avant, les modifications défaites en grisé. Un clic sur une ligne revient à l'état d'après cette modification
(« Début de l'historique » : avant la plus ancienne gardée).

C'est la liste que Défaire et Refaire montrent quelques secondes sur le plan de travail (`ui.history_hud`), à demeure
et entière : un panneau de colonne comme les autres (à gauche d'office, masqué tant qu'on ne le demande pas). Elle ne
prend pas le clavier : Ctrl+Z et Ctrl+Y restent au dessin."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from ..i18n import tr


class HistoryPanel(QWidget):
    """`win` : la fenêtre principale (`history_timeline`, `history_go`, `history_signature`)."""

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.signature = None
        self.current = 0
        self._going = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        self.list = QListWidget()
        self.list.setFocusPolicy(Qt.FocusPolicy.NoFocus)             # le clavier reste au dessin
        self.list.setToolTip(tr('Un clic sur une ligne revient à l’état d’après cette modification'))
        self.list.itemClicked.connect(self._clicked)
        lay.addWidget(self.list)

    def refresh(self) -> None:
        """La liste d'après l'état du dessin, l'état courant en vue."""
        labels, done = self.win.history_timeline()
        self.current, self.signature = done, self.win.history_signature()
        self.list.clear()
        for k in range(len(labels) + 1):                 # avec le début de l'historique
            text = tr('Début de l’historique') if k == 0 else f'{k}. {labels[k - 1]}'
            it = QListWidgetItem(('▶ ' if k == done else '    ') + text)
            it.setData(Qt.ItemDataRole.UserRole, k)
            if k == done:
                f = it.font()
                f.setBold(True)
                it.setFont(f)
            elif k > done:                               # défaite : en grisé
                it.setForeground(self.palette().placeholderText())
            self.list.addItem(it)
        here = self.list.item(done)
        if here is not None:
            self.list.scrollToItem(here)

    def rows(self) -> list:
        """Les lignes : (rang de l'état, texte)."""
        return [(self.list.item(i).data(Qt.ItemDataRole.UserRole), self.list.item(i).text())
                for i in range(self.list.count())]

    def stacks_changed(self) -> None:
        """Les piles d'annulation ont changé (autre modification, autre dessin) : à l'écran, le panneau suit ; caché
        ou derrière un autre onglet, il se refera en reparaissant. Pas pendant un saut de plusieurs pas (`go`) : une
        seule fois à l'arrivée."""
        if self._going or self.visibleRegion().isEmpty():
            return
        if self.win.history_signature() != self.signature:
            self.refresh()

    def go(self, done: int) -> int:
        """Revient à l'état où `done` modifications sont faites ; rend le nombre de modifications faites. Si le
        dessin a changé depuis que la liste est faite (certaines commandes ne préviennent pas), la liste est refaite
        et rien n'est défait : la ligne cliquée ne disait plus ce qu'elle montrait."""
        self.win.finish_typing()                         # la saisie en cours est un pas : elle change les piles
        if self.win.history_signature() != self.signature:
            self.refresh()
            return self.current
        self._going = True
        try:
            got = self.win.history_go(int(done))
        finally:
            self._going = False
        self.refresh()
        return got

    def _clicked(self, item) -> None:
        self.go(item.data(Qt.ItemDataRole.UserRole))

    def showEvent(self, ev) -> None:                     # noqa: N802 (API Qt)
        super().showEvent(ev)
        self.refresh()

    def enterEvent(self, ev) -> None:                    # noqa: N802 (API Qt)
        """La souris arrive sur la liste : remise à jour si une commande a changé le dessin sans prévenir."""
        super().enterEvent(ev)
        if self.win.history_signature() != self.signature:
            self.refresh()
