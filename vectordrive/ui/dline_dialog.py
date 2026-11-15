"""Réglages de l'outil Ligne double : type de coins, espacement de chaque trait à l'axe médian, départ et fin de ligne."""
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout

from ..core.doubleline import sides_of
from ..i18n import tr


class DoubleLineDialog(QDialog):
    def __init__(self, parent, cur: dict):
        super().__init__(parent)
        self.setWindowTitle(tr('Ligne double'))
        form = QFormLayout(self)
        self.corners = QComboBox(self)
        for k, label in (('aigu', tr('Aigu')), ('chanfrein', tr('Chanfreiné')), ('arrondi', tr('Arrondi'))):
            self.corners.addItem(label, k)
        self.corners.setCurrentIndex(max(0, self.corners.findData(cur.get('corners', 'aigu'))))
        form.addRow(tr('Type de coins'), self.corners)
        left, right = sides_of(cur)
        self.left = self._side(left)
        self.right = self._side(right)
        form.addRow(tr('Espacement à gauche de l\'axe'), self.left)
        form.addRow(tr('Espacement à droite de l\'axe'), self.right)
        self.ends = QComboBox(self)
        for k, label in (('ouvert', tr('Ouvert')), ('ferme', tr('Plat')), ('arrondi', tr('Arrondi'))):
            self.ends.addItem(label, k)
        self.ends.setCurrentIndex(max(0, self.ends.findData(cur.get('ends', 'ouvert'))))
        form.addRow(tr('Départ et fin de ligne'), self.ends)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.left.valueChanged.connect(self._refresh)
        self.right.valueChanged.connect(self._refresh)
        self._refresh()

    def _side(self, value: float) -> QDoubleSpinBox:
        w = QDoubleSpinBox(self)
        w.setRange(0.0, 10000.0)
        w.setDecimals(3)
        w.setSuffix(' mm')
        w.setValue(float(value))
        return w

    def _refresh(self) -> None:
        self.ok.setEnabled(self.left.value() + self.right.value() > 0.0)      # deux traits confondus : rien à tracer

    def values(self) -> dict:
        return {'left': self.left.value(), 'right': self.right.value(), 'corners': self.corners.currentData(),
                'ends': self.ends.currentData()}
