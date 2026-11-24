"""Onglet tenu par l'assistant (demande du 24/11 : « Assistant IA verrouille son onglet pour travailler jusque fin
travail ou annul user, on doit pouvoir travailler sur les autres onglets »).

Pendant une demande, l'onglet de la discussion est à l'assistant : on peut le regarder (molette, bouton du milieu),
pas le modifier — ni à la souris ni au clavier, le ruban et les panneaux grisés, les commandes refusées sauf la vue et
les onglets — jusqu'à la fin de la demande ou « Arrêter ». Les autres onglets restent libres : on y travaille pendant
que l'assistant passe, le temps de chaque outil, dans le sien (`MainWindow.agent_visit`).
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from ..i18n import tr

_MOUSE = (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick)
_OTHER = (QEvent.Type.KeyPress, QEvent.Type.KeyRelease, QEvent.Type.ContextMenu, QEvent.Type.DragEnter,
          QEvent.Type.DragMove, QEvent.Type.Drop, QEvent.Type.TabletPress, QEvent.Type.TouchBegin)


class InputLock(QObject):
    """Filtre posé sur le plan de travail : tant que `active()` est vrai, les clics (gauche, droit), double-clics,
    glissers, touches et dépôts n'y arrivent plus ; la molette (zoom) et le bouton du milieu (déplacer la vue)
    restent. `refused()` : dit pourquoi, au premier clic ou à la première touche."""

    def __init__(self, active, refused=None, parent=None):
        super().__init__(parent)
        self.active, self.refused = active, refused

    def eventFilter(self, obj, ev):                      # noqa: N802 — API Qt
        t = ev.type()
        if t not in _MOUSE and t not in _OTHER and t != QEvent.Type.MouseMove:
            return False
        if not self.active():
            return False
        if t in _MOUSE:
            if ev.button() == Qt.MouseButton.MiddleButton:
                return False
            if t == QEvent.Type.MouseButtonPress and self.refused is not None:
                self.refused()
            return True
        if t == QEvent.Type.MouseMove:                   # un glisser commencé avant : plus rien ne suit
            return bool(ev.buttons() & ~Qt.MouseButton.MiddleButton)
        if t == QEvent.Type.KeyPress and self.refused is not None:
            self.refused()
        return True


class Banner(QWidget):
    """Dans la barre d'état, tant qu'on regarde l'onglet tenu : « L'assistant travaille dans cet onglet » et Arrêter."""

    def __init__(self, stop, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 0, 4, 0)
        self.label = QLabel('🔒 ' + tr('L’assistant travaille dans cet onglet'))
        self.label.setToolTip(tr('Il le rend à la fin de sa demande ; les autres onglets restent libres'))
        lay.addWidget(self.label)
        self.stop = QPushButton(tr('Arrêter l’assistant'))
        self.stop.clicked.connect(lambda _=False: stop())
        lay.addWidget(self.stop)
        self.setVisible(False)
