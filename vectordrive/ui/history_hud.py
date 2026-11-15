"""La liste des modifications par-dessus le plan de travail (demande du 14/11 : « ctrlZ ctrlE affichent liste d'opé et
navigation étapes »).

« Défaire » et « Refaire » montrent quelques secondes la suite des modifications du dessin, celle où l'on est mise en
avant, les modifications défaites en grisé. Un clic sur une ligne revient à l'état d'après cette modification (« Début
de l'historique » : avant la plus ancienne gardée). La liste ne prend pas le clavier : Défaire et Refaire continuent
d'y monter et descendre. Elle suit les piles d'annulation tant qu'elle est à l'écran, et s'efface seule, sauf tant que
la souris est dessus. Elle est posée sur le plan de travail montré (dessin ou vue 3D).
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtWidgets import QFrame, QLabel, QListWidget, QListWidgetItem, QVBoxLayout

from ..i18n import tr

#: durée d'affichage après le dernier Défaire / Refaire (ms)
SHOWN_MS = 3000
#: lignes montrées au plus, autour de l'état courant
ROWS = 12
#: lignes au moins, même sur un tout petit plan de travail
MIN_ROWS = 3
WIDTH = 300
MARGIN = 12


class HistoryHud(QFrame):
    """`win` : la fenêtre principale (`history_timeline`, `history_go`, `history_signature`, `finish_typing`)."""

    def __init__(self, win):
        super().__init__(getattr(win, 'stage', None) or win.canvas)
        self.win = win
        self.setObjectName('historyHud')
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_NoMousePropagation)     # ni appui ni relâchement ne vont au dessin
        self.setCursor(Qt.CursorShape.ArrowCursor)                      # pas la croix de l'outil de dessin
        self.setAutoFillBackground(True)
        self.setStyleSheet('QFrame#historyHud { background: palette(window); border: 1px solid palette(mid); '
                           'border-radius: 6px; }')
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)
        self.title = QLabel(tr('Historique — un clic revient à l’étape'))
        lay.addWidget(self.title)
        self.list = QListWidget()
        self.list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setUniformItemSizes(True)
        self.list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.list.itemClicked.connect(self._clicked)
        lay.addWidget(self.list)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(SHOWN_MS)
        self.timer.timeout.connect(self._timeout)
        self.current = 0                     # nombre de modifications faites, à l'affichage
        self.signature = None
        self.hide()

    def _room(self) -> tuple:
        """(lignes au plus, largeur, hauteur d'une ligne) d'après la place du plan de travail."""
        parent = self.parentWidget()
        row_h = max(18, self.list.sizeHintForRow(0) if self.list.count() else self.list.fontMetrics().height() + 4)
        free = parent.height() - 2 * MARGIN - self.title.sizeHint().height() - 28
        return max(MIN_ROWS, min(ROWS, free // row_h)), max(120, min(WIDTH, parent.width() - 2 * MARGIN)), row_h

    def refresh(self) -> None:
        """La liste d'après l'état du dessin : `ROWS` lignes au plus (moins si la place manque), autour de l'état
        courant."""
        labels, done = self.win.history_timeline()
        self.current, self.signature = done, self.win.history_signature()
        total = len(labels) + 1              # avec le début de l'historique
        most, width, row_h = self._room()
        first = max(0, min(done - most // 2, total - most))
        self.list.clear()
        for k in range(first, min(total, first + most)):
            text = tr('Début de l’historique') if k == 0 else f'{k}. {labels[k - 1]}'
            it = QListWidgetItem(('▶ ' if k == done else '    ') + text)
            it.setData(Qt.ItemDataRole.UserRole, k)
            if k == done:
                f = it.font()
                f.setBold(True)
                it.setFont(f)
            elif k > done:                   # défaite : en grisé
                it.setForeground(self.palette().placeholderText())
            self.list.addItem(it)
        rows = self.list.count()
        row_h = max(row_h, self.list.sizeHintForRow(0)) if rows else row_h
        self.list.setFixedHeight(rows * row_h + 2 * self.list.frameWidth() + 8)
        self.setFixedWidth(width)
        self.adjustSize()
        parent, canvas = self.parentWidget(), self.win.canvas
        at = QPoint(MARGIN, MARGIN)
        if canvas is not parent and parent.isAncestorOf(canvas) and canvas.isVisibleTo(parent):
            at = canvas.mapTo(parent, at)    # dans le dessin, pas sur ses règles
        self.move(at)

    def rows(self) -> list:
        """Les lignes montrées : (rang de l'état, texte)."""
        return [(self.list.item(i).data(Qt.ItemDataRole.UserRole), self.list.item(i).text())
                for i in range(self.list.count())]

    def show_now(self) -> None:
        """Montre la liste à jour, pour `SHOWN_MS`."""
        self.refresh()
        self.show()
        self.raise_()
        self.timer.start()

    def stacks_changed(self) -> None:
        """Les piles d'annulation ont changé (autre modification, autre dessin) : à l'écran, la liste suit."""
        if not self.isHidden():
            self.refresh()

    def go(self, done: int) -> bool:
        """Revient à l'état où `done` modifications sont faites. Une liste qui n'est plus à jour (le dessin a changé
        depuis, une saisie de texte s'est terminée) est refaite, sans rien défaire : faux."""
        self.win.finish_typing()             # la saisie en cours est un pas : posé avant de compter
        if self.signature != self.win.history_signature():
            self.refresh()
            self.timer.start()
            return False
        self.win.history_go(done)
        self.refresh()
        self.timer.start()
        return True

    def _clicked(self, item) -> None:
        self.go(int(item.data(Qt.ItemDataRole.UserRole)))

    def _timeout(self) -> None:
        if self.underMouse():                # on y lit, on y clique : elle reste
            self.timer.start()
        else:
            self.hide()

    def mousePressEvent(self, ev) -> None:   # noqa: N802 (API Qt) — un clic sur le cadre ne va pas au dessin
        ev.accept()

    def mouseReleaseEvent(self, ev) -> None:   # noqa: N802 (API Qt)
        ev.accept()

    def wheelEvent(self, ev) -> None:        # noqa: N802 (API Qt) — la molette non plus
        ev.accept()
