"""Repères… : la liste des repères du dessin, modifiable, et leur répartition sur la plaque."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QPushButton, QSpinBox,
                               QTableWidget, QTableWidgetItem, QVBoxLayout)

from ..core import guides as GD
from ..i18n import tr
from .dialogs import _spin


def _text(v: float) -> str:
    return f'{v:.6f}'.rstrip('0').rstrip('.') or '0'


class GuidesDialog(QDialog):
    def __init__(self, parent=None, guides=(), obliques=(), box=(0.0, 0.0, 100.0, 100.0)):
        super().__init__(parent)
        from .fit import release
        release(self)                                    # fermée : détruite, pas gardée par son parent
        self.setWindowTitle(tr('Repères'))
        self.box = box
        self.resize(520, 480)
        lay = QVBoxLayout(self)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([tr('Type'), tr('X (mm)'), tr('Y (mm)'), tr('Angle (°)')])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        lay.addWidget(self.table)
        row = QHBoxLayout()
        for label, slot in ((tr('Ajouter'), self.add_row), (tr('Supprimer'), self.remove_row), (tr('Tout effacer'), self.clear)):
            b = QPushButton(label)
            b.setAutoDefault(False)
            b.clicked.connect(lambda _=False, f=slot: f())
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        form = QFormLayout()
        self.columns = QSpinBox()
        self.columns.setRange(0, 100)
        self.columns.setValue(2)
        self.rows = QSpinBox()
        self.rows.setRange(0, 100)
        self.rows.setValue(2)
        self.margin = _spin(0.0, 0.0, 100000.0)
        form.addRow(tr('Colonnes'), self.columns)
        form.addRow(tr('Rangées'), self.rows)
        form.addRow(tr('Marge'), self.margin)
        spread = QPushButton(tr('Répartir sur la plaque'))
        spread.setAutoDefault(False)
        spread.clicked.connect(lambda _=False: self.spread())
        form.addRow(spread)
        lay.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        for axis, v in guides:
            self.add_row('h' if axis == 'h' else 'v', v if axis == 'v' else 0.0, v if axis == 'h' else 0.0)
        for x, y, a in obliques:
            self.add_row('o', x, y, a)

    def add_row(self, kind: str = 'h', x: float = 0.0, y: float = 0.0, angle: float = 45.0) -> None:
        r = self.table.rowCount()
        self.table.insertRow(r)
        combo = QComboBox()
        for k, label in (('h', tr('Horizontal')), ('v', tr('Vertical')), ('o', tr('Oblique'))):
            combo.addItem(label, k)
        combo.setCurrentIndex(max(0, combo.findData(kind)))
        self.table.setCellWidget(r, 0, combo)
        for col, v in ((1, x), (2, y), (3, angle)):
            self.table.setItem(r, col, QTableWidgetItem(_text(v)))
        combo.currentIndexChanged.connect(lambda _i, c=combo: self._refresh(c))
        self._refresh(combo)

    def _refresh(self, combo: QComboBox) -> None:
        """Seules les valeurs utiles au type se modifient."""
        r = next((i for i in range(self.table.rowCount()) if self.table.cellWidget(i, 0) is combo), -1)
        if r < 0:
            return
        k = combo.currentData()
        live = {'h': (2,), 'v': (1,), 'o': (1, 2, 3)}[k]
        for col in (1, 2, 3):
            it = self.table.item(r, col)
            editable = Qt.ItemFlag.ItemIsEditable
            it.setFlags(it.flags() | editable if col in live else it.flags() & ~editable)

    def remove_row(self) -> None:
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)

    def clear(self) -> None:
        self.table.setRowCount(0)

    def spread(self) -> None:
        for axis, v in GD.spread(self.box, self.columns.value(), self.rows.value(), self.margin.value()):
            self.add_row(axis, v if axis == 'v' else 0.0, v if axis == 'h' else 0.0)

    def _value(self, r: int, col: int) -> float:
        try:
            return float(self.table.item(r, col).text().replace(',', '.'))
        except ValueError:                               # saisie illisible : zéro, visible à la réouverture
            return 0.0

    def values(self) -> tuple[list, list]:
        lines = []
        for r in range(self.table.rowCount()):
            k = self.table.cellWidget(r, 0).currentData()
            x, y, a = self._value(r, 1), self._value(r, 2), self._value(r, 3)
            lines.append((x, y, 0.0 if k == 'h' else (90.0 if k == 'v' else a)))
        return GD.split(lines)
