"""F2 pendant un tracé : les coordonnées des points déjà posés, à corriger ou à compléter."""
from __future__ import annotations

from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QDoubleSpinBox, QHBoxLayout, QPushButton, QTableWidget, QVBoxLayout)

from ..i18n import tr


class PointsDialog(QDialog):
    def __init__(self, parent, points: list, can_finish: bool = True):
        super().__init__(parent)
        self.setWindowTitle(tr('Coordonnées des points'))
        self.finish = False
        lay = QVBoxLayout(self)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(['X (mm)', 'Y (mm)'])
        self.table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.table)
        row = QHBoxLayout()
        self.b_add = QPushButton(tr('Ajouter'))
        self.b_del = QPushButton(tr('Supprimer'))
        for b, slot in ((self.b_add, self.add_row), (self.b_del, self.remove_row)):
            b.setAutoDefault(False)
            b.clicked.connect(lambda _=False, f=slot: f())
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=self)
        self.b_finish = box.addButton(tr('Terminer le tracé'), QDialogButtonBox.ButtonRole.AcceptRole)
        self.b_finish.clicked.connect(self._mark_finish)
        self.b_finish.setVisible(can_finish)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay.addWidget(box)
        for p in points:
            self._append(p)
        self.resize(340, 320)

    def _mark_finish(self) -> None:
        self.finish = True

    def _append(self, p) -> None:
        i = self.table.rowCount()
        self.table.insertRow(i)
        for j in (0, 1):
            w = QDoubleSpinBox()
            w.setRange(-1e7, 1e7)
            w.setDecimals(3)
            w.setValue(float(p[j]))
            self.table.setCellWidget(i, j, w)
        self.table.setCurrentCell(i, 0)

    def add_row(self) -> None:
        """Un point de plus, à la place du dernier : il reste à le corriger."""
        pts = self.points()
        self._append(pts[-1] if pts else (0.0, 0.0))

    def remove_row(self) -> None:
        i = self.table.currentRow()
        if i < 0:
            i = self.table.rowCount() - 1
        if i >= 0:
            self.table.removeRow(i)

    def points(self) -> list:
        return [(self.table.cellWidget(i, 0).value(), self.table.cellWidget(i, 1).value())
                for i in range(self.table.rowCount())]
