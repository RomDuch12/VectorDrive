"""Fenêtre des modes de sélection (TypeEdit) : opérateur de sélection et
classement de la sélection (ordre du dessin et de l'usinage)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QButtonGroup, QDialog, QGroupBox, QPushButton, QRadioButton, QVBoxLayout

from ..core import selsort as SS
from ..i18n import tr


class SelectionModesDialog(QDialog):
    vd_keep = True                  # réemployée (gardée par la fenêtre) : pas libérée à la fermeture

    def __init__(self, win):
        super().__init__(win)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        self.win = win
        self.setWindowTitle(tr('Modes de sélection'))
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setModal(False)
        lay = QVBoxLayout(self)
        ops = QGroupBox(tr('Opérateur'))
        ol = QVBoxLayout(ops)
        self.group = QButtonGroup(self)
        self.radios = {}
        for k, lab in SS.OPERATORS.items():
            r = QRadioButton(tr(lab))
            r.setProperty('vd_op', k)
            self.group.addButton(r)
            ol.addWidget(r)
            self.radios[k] = r
        self.radios[getattr(win.canvas, 'select_op', 'standard')].setChecked(True)
        self.group.buttonToggled.connect(lambda b, on: on and self.set_operator(b.property('vd_op')))
        lay.addWidget(ops)
        lasso = QPushButton(tr('Lasso (polygonal ou à main levée)'))
        lasso.clicked.connect(lambda _=False: self.win.set_tool('lasso'))
        lay.addWidget(lasso)
        sorts = QGroupBox(tr('Classement de la sélection (ordre d\'usinage)'))
        sl = QVBoxLayout(sorts)
        for k, lab in SS.SORTS.items():
            b = QPushButton(tr(lab))
            b.clicked.connect(lambda _=False, kk=k: self.win.sort_selection(kk))
            sl.addWidget(b)
        lay.addWidget(sorts)
        close = QPushButton(tr('Fermer'))
        close.clicked.connect(lambda _=False: self.close())
        lay.addWidget(close)

    def set_operator(self, op: str) -> None:
        self.win.canvas.select_op = op

    def hideEvent(self, e) -> None:
        """Fermée : retour à la sélection standard, comme TypeEdit."""
        self.win.canvas.select_op = 'standard'
        self.radios['standard'].setChecked(True)
        if 'selection_modes' in getattr(self.win, 'A', {}):
            self.win._check_quietly('selection_modes', False)
        super().hideEvent(e)
