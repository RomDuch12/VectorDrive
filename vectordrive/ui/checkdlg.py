"""Fenêtre « Vérifier le dessin » : liste des problèmes, sélection des
objets concernés, correction quand elle est sûre."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
                               QStyle, QVBoxLayout)

from ..core import check as CK
from ..i18n import tr

_ICONS = {'erreur': QStyle.StandardPixmap.SP_MessageBoxCritical,
          'attention': QStyle.StandardPixmap.SP_MessageBoxWarning,
          'info': QStyle.StandardPixmap.SP_MessageBoxInformation}


class CheckDialog(QDialog):
    vd_keep = True                  # réemployée (gardée par la fenêtre, rafraîchie) : pas libérée à la fermeture

    def __init__(self, win):
        super().__init__(win)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        self.win = win
        self.issues: list[CK.Issue] = []
        self.setWindowTitle(tr('Vérifier le dessin'))
        self.resize(560, 320)
        lay = QVBoxLayout(self)
        self.summary = QLabel()
        lay.addWidget(self.summary)
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._current)
        self.list.itemDoubleClicked.connect(lambda _it: self.select())
        lay.addWidget(self.list)
        row = QHBoxLayout()
        self.b_select = QPushButton(tr('Sélectionner'))
        self.b_select.clicked.connect(self.select)
        self.b_fix = QPushButton(tr('Corriger'))
        self.b_fix.clicked.connect(self.fix)
        b_again = QPushButton(tr('Vérifier à nouveau'))
        b_again.clicked.connect(self.refresh)
        b_close = QPushButton(tr('Fermer'))
        b_close.clicked.connect(self.close)
        for b in (self.b_select, self.b_fix, b_again):
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(b_close)
        lay.addLayout(row)
        self.refresh()

    def refresh(self) -> None:
        from .progress import Cancelled, run
        try:
            self.issues = run(self, tr('Vérification du dessin'), CK.check, self.win.canvas.doc)
        except Cancelled:
            self.issues = getattr(self, 'issues', [])
        self.list.clear()
        st = self.style()
        for i in self.issues:
            it = QListWidgetItem(st.standardIcon(_ICONS[i.severity]), i.text(tr))
            it.setData(Qt.ItemDataRole.UserRole, i.code)
            self.list.addItem(it)
        n_err = sum(1 for i in self.issues if i.severity == 'erreur')
        n_warn = sum(1 for i in self.issues if i.severity == 'attention')
        if not self.issues:
            self.summary.setText(tr('Aucun problème trouvé.'))
        else:
            self.summary.setText(tr('{0} erreur(s), {1} avertissement(s)').format(n_err, n_warn))
        if self.issues:
            self.list.setCurrentRow(0)
        self._current(self.list.currentRow())

    def _issue(self) -> CK.Issue | None:
        r = self.list.currentRow()
        return self.issues[r] if 0 <= r < len(self.issues) else None

    def _current(self, _row: int) -> None:
        i = self._issue()
        self.b_select.setEnabled(bool(i and i.items))
        self.b_fix.setEnabled(bool(i and i.fixable))

    def select(self) -> None:
        i = self._issue()
        if i and i.items:
            self.win.canvas.select(list(i.items))
            self.win.zoom_selection() if hasattr(self.win, 'zoom_selection') else None

    def fix(self) -> None:
        i = self._issue()
        if not i or not i.fixable:
            return
        if i.code == 'doublon':
            self.win.remove_duplicates()
        else:
            w = self.win
            new = {id(it): [x for x in [CK.fix_item(it, i.code, gap=i.params[0], dust=i.params[1])] if x is not None]
                   for it in i.items}
            w.push_undo()
            out = w._replace_in_layers(list(i.items), new)
            w.canvas.invalidate()
            w.canvas.select(out)
            w._on_doc_changed()
        self.refresh()
