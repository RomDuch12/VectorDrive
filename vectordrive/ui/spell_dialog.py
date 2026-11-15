"""Orthographe : les mots à revoir des textes du dessin, un par un."""
from __future__ import annotations

import html

from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QPushButton, QVBoxLayout)

from ..core import spell as SP
from ..i18n import tr


class SpellSession:
    """Parcourt les textes, sans fenêtre : `current` donne (texte, mot à revoir). `apply(texte, chaîne)` modifie le dessin."""

    def __init__(self, texts: list, checker, apply, ignored: set | None = None, on_add=None):
        self.texts = list(texts)
        self.checker = checker
        self.apply = apply
        self.ignored = set(ignored or ())
        self.on_add = on_add                             # le mot ajouté au dictionnaire : à garder
        self.index = 0
        self.done_in_text: set = set()                   # (position, mot) déjà écartés dans le texte en cours
        self.replacements = 0
        self.current_fault = None
        self.advance()

    @property
    def text(self):
        return self.texts[self.index] if self.index < len(self.texts) else None

    def advance(self) -> None:
        """Mot suivant : dans le texte en cours, puis dans les suivants."""
        self.current_fault = None
        while self.index < len(self.texts):
            for f in SP.faults_of(self.checker, self.texts[self.index].text, ignore=self.ignored):
                if (f.start, f.word) not in self.done_in_text:
                    self.current_fault = f
                    return
            self.index += 1
            self.done_in_text = set()

    def finished(self) -> bool:
        return self.current_fault is None

    def replace(self, by: str) -> None:
        t, f = self.text, self.current_fault
        if t is None or f is None:
            return
        new = SP.replaced(t.text, f, by)
        if new == t.text:                                # rien de changé : ne pas reposer la même question
            self.done_in_text.add((f.start, f.word))
        else:                                            # une correction encore fausse sera revue
            delta = len(new) - len(t.text)
            self.apply(t, new)
            self.replacements += 1
            self.done_in_text = {(s + delta if s > f.start else s, w) for s, w in self.done_in_text}
        self.advance()

    def ignore(self) -> None:
        if self.current_fault is not None:
            self.done_in_text.add((self.current_fault.start, self.current_fault.word))
        self.advance()

    def ignore_all(self) -> None:
        if self.current_fault is not None:
            self.ignored.add(self.current_fault.word.casefold())
        self.advance()

    def add_word(self) -> None:
        """Le mot en cours va au dictionnaire : il n'est plus signalé, ni ici ni les fois suivantes."""
        if self.current_fault is not None and self.on_add is not None:
            self.on_add(self.current_fault.word)
        self.ignore_all()


class SpellDialog(QDialog):
    def __init__(self, parent, session: SpellSession, show_text=None):
        super().__init__(parent)
        self.session = session
        self.show_text = show_text                       # montre le texte en cours dans le plan de travail
        self.setWindowTitle(tr('Orthographe'))
        v = QVBoxLayout(self)
        self.context = QLabel()
        self.context.setWordWrap(True)
        v.addWidget(self.context)
        v.addWidget(QLabel(tr('Remplacer par')))
        self.edit = QLineEdit()
        v.addWidget(self.edit)
        self.list = QListWidget()
        self.list.currentTextChanged.connect(self._picked)
        self.list.itemDoubleClicked.connect(lambda _it: self.do_replace())
        v.addWidget(self.list)
        row = QHBoxLayout()
        self.b_replace = QPushButton(tr('Remplacer'))
        self.b_ignore = QPushButton(tr('Ignorer'))
        self.b_all = QPushButton(tr('Ignorer partout'))
        self.b_add = QPushButton(tr('Ajouter'))
        self.b_add.setToolTip(tr('Ajouter le mot au dictionnaire de VectorDrive : il ne sera plus signalé'))
        self.b_close = QPushButton(tr('Fermer'))
        for b in (self.b_replace, self.b_ignore, self.b_all, self.b_add, self.b_close):
            b.setAutoDefault(False)
            row.addWidget(b)
        self.b_replace.setDefault(True)
        self.b_replace.clicked.connect(self.do_replace)
        self.b_ignore.clicked.connect(self.do_ignore)
        self.b_all.clicked.connect(self.do_ignore_all)
        self.b_add.clicked.connect(self.do_add)
        self.b_close.clicked.connect(self.accept)
        v.addLayout(row)
        self.resize(420, 300)
        self.refresh()

    def _picked(self, s: str) -> None:
        if s:
            self.edit.setText(s)

    def refresh(self) -> None:
        s = self.session
        if s.finished():
            self.accept()
            return
        t, f = s.text, s.current_fault
        a, w, b = t.text[:f.start], t.text[f.start:f.start + f.length], t.text[f.start + f.length:]
        self.context.setText(f'{html.escape(a)}<b style="color:#c00000"><u>{html.escape(w)}</u></b>{html.escape(b)}'
                             .replace('\n', '<br>'))
        self.list.clear()
        shown = [x if x else tr('(retirer le mot répété)') for x in f.suggestions]
        self.list.addItems(shown)
        self._removal = [x for x in f.suggestions if not x] != []
        first = f.suggestions[0] if f.suggestions else w
        self.edit.setText(first)
        if f.suggestions:
            self.list.setCurrentRow(0)
            self.edit.setText(first)
        if self.show_text:
            self.show_text(t)

    def do_replace(self) -> None:
        self.session.replace(self.edit.text())
        self.refresh()

    def do_ignore(self) -> None:
        self.session.ignore()
        self.refresh()

    def do_ignore_all(self) -> None:
        self.session.ignore_all()
        self.refresh()

    def do_add(self) -> None:
        self.session.add_word()
        self.refresh()
