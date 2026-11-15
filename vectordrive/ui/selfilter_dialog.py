"""Fenêtre du filtre de sélection (F9, comme TypeEdit) : un bouton par
nature d'objet ; tant qu'elle est ouverte, seules les natures enfoncées se
sélectionnent (au clic, au rectangle, avec Tout). À l'ouverture tous les
boutons sont relevés ; à la fermeture le filtre s'arrête et n'est pas gardé."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QGridLayout, QHBoxLayout, QPushButton, QToolButton, QVBoxLayout

from ..core import selfilter as SF
from ..i18n import tr


class SelectionFilterDialog(QDialog):
    vd_keep = True                  # réemployée (gardée par la fenêtre) : pas libérée à la fermeture

    closed = Signal()

    def __init__(self, win):
        super().__init__(win)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        self.win = win
        self.setWindowTitle(tr('Filtre de sélection'))
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setModal(False)
        outer = QVBoxLayout(self)
        grid = QGridLayout()
        self.buttons = {}
        for i, (k, lab) in enumerate(SF.KINDS.items()):
            b = QToolButton()
            b.setCheckable(True)
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            b.setMinimumWidth(170)
            b.setProperty('vd_label', lab)
            b.toggled.connect(lambda _on: self._apply())
            grid.addWidget(b, i // 2, i % 2)
            self.buttons[k] = b
        outer.addLayout(grid)
        row = QHBoxLayout()
        for text, slot in ((tr('Tout'), lambda: self.set_all(True)), (tr('Aucun'), lambda: self.set_all(False)),
                           (tr('Inverser'), self.invert), (tr('Sélectionner'), self.select_matching)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, s=slot: s())
            row.addWidget(b)
        outer.addLayout(row)
        close = QPushButton(tr('Fermer (F9)'))
        close.clicked.connect(lambda _=False: self.close())
        outer.addWidget(close)
        self.refresh_counts()

    def active(self) -> set:
        return {k for k, b in self.buttons.items() if b.isChecked()}

    def _apply(self) -> None:
        self.win.canvas.pick_filter = self.active()      # la sélection en cours reste telle quelle

    def refresh_counts(self) -> None:
        canvas = self.win.canvas
        items = [it for L in canvas.doc.layers if canvas.layer_shown(L) and not L.locked for it in L.items
                 if it.visible and not it.locked]
        n = SF.count(items)
        for k, b in self.buttons.items():
            b.setText(f'{tr(b.property("vd_label"))} ({n.get(k, 0)})')

    def set_all(self, on: bool) -> None:
        for b in self.buttons.values():
            b.blockSignals(True)
            b.setChecked(on)
            b.blockSignals(False)
        self._apply()

    def invert(self) -> None:
        for b in self.buttons.values():
            b.blockSignals(True)
            b.setChecked(not b.isChecked())
            b.blockSignals(False)
        self._apply()

    def select_matching(self) -> None:
        self.win.canvas.select_all()
        self.win.canvas.invalidate()

    def showEvent(self, e) -> None:
        """À chaque ouverture : boutons relevés (rien ne se sélectionne), comptes à jour."""
        super().showEvent(e)
        self.refresh_counts()
        self.set_all(False)

    def hideEvent(self, e) -> None:
        """Fermée (bouton, Échap, F9) : plus de filtre."""
        self.win.canvas.pick_filter = None
        self.closed.emit()
        super().hideEvent(e)
