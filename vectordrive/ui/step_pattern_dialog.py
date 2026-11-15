"""Design STEP : « Répéter des corps » — les corps d'un STEP (tous, ou celui
des faces choisies dans la vue 3D) copiés en ligne, au pas donné en X, Y et Z,
ou en rond autour de la verticale (angle total, centre), dans un nouveau STEP
à géométrie exacte (`io.step_extract.pattern`). Les axes sont ceux de la pièce
redressée, comme dans la vue 3D (un fichier « Y vers le haut » compris).
"""
from __future__ import annotations

import os
import pathlib

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel, QLineEdit,
                               QSpinBox)

from ..i18n import tr
from ..io import step_extract as X
from .step_edit_dialog import ERRORS

#: les façons de répéter, dans l'ordre de la liste
MODE_LABELS = {'ligne': 'En ligne (pas en X, Y, Z)', 'rond': 'En rond (autour de la verticale)'}


def _spin(lo: float, hi: float, value: float, suffix: str = ' mm') -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(3)
    s.setValue(value)
    s.setSuffix(suffix)
    return s


class StepPatternDialog(QDialog):
    """Les corps `picks` (None : tous) du STEP `path` répétés ; `up` : l'axe du fichier tourné vers le haut
    dans la vue 3D (None : lu dans le fichier) ; `written` : le fichier écrit."""

    def __init__(self, parent, path, picks=None, up: str | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr('Répéter des corps'))
        self.path = pathlib.Path(path)
        self.written = None
        self._replace = None                               # fichier existant à remplacer au second clic
        if up is None:
            try:
                from ..io import model3d
                up = model3d.from_step(self.path).up_axis
            except ERRORS:
                up = 'Z'
        self.up = up
        try:
            n = len(X.bodies(self.path))
        except ERRORS:
            n = 0
        self.picks = [k for k in (picks or []) if 0 <= k < n] or None
        lost = bool(picks) and self.picks is None
        form = QFormLayout(self)
        form.addRow(tr('Source :'), QLabel(tr('{0} — {1} corps').format(self.path.name, len(self.picks or range(n)))))
        self.mode = QComboBox()
        for k, label in MODE_LABELS.items():
            self.mode.addItem(tr(label), k)
        form.addRow(tr('Copies :'), self.mode)
        self.count = QSpinBox()
        self.count.setRange(2, 500)
        self.count.setValue(4)
        form.addRow(tr('Nombre (l\'original compris) :'), self.count)
        self.dx, self.dy, self.dz = _spin(-10000, 10000, 50.0), _spin(-10000, 10000, 0.0), _spin(-10000, 10000, 0.0)
        form.addRow(tr('Pas en X :'), self.dx)
        form.addRow(tr('Pas en Y :'), self.dy)
        form.addRow(tr('Pas en Z :'), self.dz)
        self.angle = _spin(-360, 360, 360.0, ' °')
        self.cx, self.cy = _spin(-10000, 10000, 0.0), _spin(-10000, 10000, 0.0)
        form.addRow(tr('Angle total (360 : sur le tour) :'), self.angle)
        form.addRow(tr('Centre X :'), self.cx)
        form.addRow(tr('Centre Y :'), self.cy)
        self.out = QLineEdit(str(self.path.with_name(f'{self.path.stem}_copies.step')))
        form.addRow(tr('Fichier :'), self.out)
        self.info = QLabel(tr('Corps choisi introuvable dans le fichier : tous les corps') if lost else '')
        self.info.setWordWrap(True)
        form.addRow(self.info)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr('Écrire'))
        buttons.accepted.connect(self.write)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.mode.currentIndexChanged.connect(self._modes)
        self._modes()

    def _modes(self) -> None:
        line = self.mode.currentData() == 'ligne'
        for w in (self.dx, self.dy, self.dz):
            w.setEnabled(line)
        for w in (self.angle, self.cx, self.cy):
            w.setEnabled(not line)

    def moves(self) -> list:
        """Les déplacements des copies dans les axes du fichier, d'après la fenêtre (axes de la pièce redressée)."""
        if self.mode.currentData() == 'rond':
            mv = X.pattern_moves(self.count.value(), angle=self.angle.value(), centre=(self.cx.value(), self.cy.value()))
        else:
            mv = X.pattern_moves(self.count.value(), step=(self.dx.value(), self.dy.value(), self.dz.value()))
        return X.file_moves(mv, self.up)

    def target(self) -> pathlib.Path | None:
        """Le fichier à écrire : un nom seul va à côté de la source ; None si vide."""
        out = self.out.text().strip()
        if not out:
            return None
        p = pathlib.Path(out)
        return p if p.is_absolute() else self.path.parent / p

    def write(self) -> str | None:
        """Écrit le STEP des copies et ferme la fenêtre ; un fichier existant n'est remplacé qu'au second clic ;
        sinon dit pourquoi."""
        from ..core.progress import Cancelled
        from . import progress
        out = self.target()
        try:
            if out is None:
                raise X.ExtractError(tr('nom de fichier vide'))
            if out.exists() and (os.path.samefile(out, self.path) or out.resolve() == self.path.resolve()):
                raise X.ExtractError(tr('le fichier source lui-même : choisir un autre nom'))
            if out.exists() and self._replace != out:
                self._replace = out
                self.info.setText(tr('{0} existe déjà : Écrire encore pour le remplacer').format(out.name))
                return None
            self.written = progress.run(self, tr('Répéter des corps'), X.pattern, self.path, self.picks, str(out),
                                        self.moves(), name=out.stem)
        except Cancelled:
            return None
        except ERRORS as ex:
            self.info.setText(tr('Écriture impossible : {0}').format(ex))
            return None
        self.accept()
        return self.written
