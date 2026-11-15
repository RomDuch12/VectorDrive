"""Recherche de commande (Ctrl+K) : taper quelques lettres du nom ou de la
bulle d'aide d'une commande, Entrée l'exécute — pratique avec les quelque
150 commandes du ruban."""
from __future__ import annotations

import unicodedata

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout

from ..i18n import tr


def fold(s: str) -> str:
    """Minuscules sans accents (« Décaler » ≡ « decaler »)."""
    s = unicodedata.normalize('NFKD', s.replace('&', ''))
    return ''.join(c for c in s if not unicodedata.combining(c)).lower()


def rank(query: str, actions: list[tuple[str, object]]) -> list[tuple[str, object]]:
    """Actions (clé, QAction) correspondant à la requête : tous les mots
    trouvés dans le nom ou la bulle ; nom qui commence par la requête
    d'abord, puis mot du nom, puis bulle."""
    words = fold(query).split()
    scored = []
    for key, act in actions:
        name, tip = fold(act.text()), fold(act.toolTip() or '')
        if not all(w in name or w in tip for w in words):
            continue
        q = ' '.join(words)
        if not words:
            score = 3
        elif name.startswith(q):
            score = 0
        elif any(part.startswith(words[0]) for part in name.split()):
            score = 1
        elif all(w in name for w in words):
            score = 2
        else:
            score = 3
        scored.append((score, name, key, act))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [(k, a) for _s, _n, k, a in scored]


class CommandSearch(QDialog):
    def __init__(self, parent, actions: dict):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        self.setWindowTitle(tr('Chercher une commande'))
        self.actions = [(k, a) for k, a in actions.items() if a.text() and a.isEnabled()]
        lay = QVBoxLayout(self)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(tr('Nom ou action de la commande… (Entrée pour l\'exécuter)'))
        self.list = QListWidget()
        lay.addWidget(self.edit)
        lay.addWidget(self.list)
        self.edit.textChanged.connect(self.refresh)
        self.edit.returnPressed.connect(self.run_current)
        self.list.itemActivated.connect(lambda _it: self.run_current())
        self.chosen = None
        self.resize(520, 420)
        self.refresh('')

    def refresh(self, text: str) -> None:
        self.list.clear()
        for key, act in rank(text, self.actions)[:60]:
            sc = act.shortcut().toString()
            label = act.text().replace('&', '') + (f'    [{sc}]' if sc else '')
            it = QListWidgetItem(act.icon(), label)
            it.setToolTip(act.toolTip())
            it.setData(Qt.ItemDataRole.UserRole, key)
            self.list.addItem(it)
        if self.list.count():
            self.list.setCurrentRow(0)

    def keyPressEvent(self, ev) -> None:
        if ev.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up, Qt.Key.Key_PageDown, Qt.Key.Key_PageUp):
            self.list.keyPressEvent(ev)            # flèches : dans la liste, le curseur reste dans le champ
            return
        super().keyPressEvent(ev)

    def run_current(self) -> None:
        it = self.list.currentItem()
        if it is None:
            return
        self.chosen = it.data(Qt.ItemDataRole.UserRole)
        self.accept()
