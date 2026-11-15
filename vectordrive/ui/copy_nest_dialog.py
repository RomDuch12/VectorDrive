"""Copie imbriquée : combien d'exemplaires de chaque objet, et comment les ranger."""
from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QLineEdit,
                               QFormLayout, QGroupBox, QHeaderView, QHBoxLayout, QLabel, QSpinBox, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from ..core import nesting as N
from ..core.document import Text
from ..i18n import tr

MAX_COUNT = 5000


def _name_of(item, index: int) -> str:
    if item.name:
        return item.name
    if isinstance(item, Text) and item.text.strip():
        return item.text.strip().splitlines()[0][:40]
    return tr('Objet {0}').format(index + 1)


class CopyNestDialog(QDialog):
    def __init__(self, parent, items: list, spec: N.NestSpec, per_plane: bool = True, count: int = 1):
        super().__init__(parent)
        self.setWindowTitle(tr('Copie imbriquée'))
        self.items = list(items)
        self.spec = spec
        col = QVBoxLayout(self)
        row = QHBoxLayout()
        self.same = QCheckBox(tr('Même nombre pour chaque objet'))
        self.same.setChecked(True)
        self.same_count = QSpinBox()
        self.same_count.setRange(1, MAX_COUNT)
        self.same_count.setValue(max(1, count))
        row.addWidget(self.same)
        row.addWidget(self.same_count)
        row.addStretch(1)
        col.addLayout(row)
        self.table = QTableWidget(len(self.items), 2)
        self.table.setHorizontalHeaderLabels([tr('Objet à dupliquer'), tr('Exemplaires')])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.spins = []
        for i, it in enumerate(self.items):
            cell = QTableWidgetItem(_name_of(it, i))
            cell.setFlags(cell.flags() | Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 0, cell)
            sp = QSpinBox()
            sp.setRange(0, MAX_COUNT)
            sp.setValue(max(1, count))
            self.table.setCellWidget(i, 1, sp)
            self.spins.append(sp)
        col.addWidget(self.table)
        box = QGroupBox(tr('Imbrication'))
        form = QFormLayout(box)
        self.margin = self._number(spec.margin, 0.0, 10000.0)
        self.gap = self._number(spec.gap, 0.0, 10000.0)
        self.rotate = QCheckBox()
        self.rotate.setChecked(spec.allow_rotate)
        self.shape = QCheckBox()
        self.shape.setChecked(spec.shape)
        self.angle = self._number(spec.angle_step, 1.0, 360.0)
        self.angles = QLineEdit(spec.angles)
        self.holes = QCheckBox()
        self.holes.setChecked(spec.in_holes)
        self.mirror = QCheckBox()
        self.mirror.setChecked(spec.allow_mirror)
        self.precision = self._number(spec.precision, N.MIN_PRECISION, 100.0)
        self.corner = QComboBox()
        for key, label in ((N.CORNERS[0], tr('En haut à gauche')), (N.CORNERS[1], tr('En haut à droite')),
                           (N.CORNERS[2], tr('En bas à gauche')), (N.CORNERS[3], tr('En bas à droite'))):
            self.corner.addItem(label, key)
        self.corner.setCurrentIndex(max(0, self.corner.findData(spec.corner)))
        self.direction = QComboBox()
        self.direction.addItem(tr('Horizontale'), False)
        self.direction.addItem(tr('Verticale'), True)
        self.direction.setCurrentIndex(1 if spec.vertical else 0)
        self.planes = QCheckBox()
        self.planes.setChecked(per_plane)
        self.tries = QSpinBox()
        self.tries.setRange(1, 1000)
        self.tries.setValue(max(1, int(spec.tries)))
        self.both_ways = QCheckBox()
        self.both_ways.setChecked(bool(spec.both_ways))
        self.seconds = self._number(spec.max_seconds, 0.0, 86400.0)
        self.gain = self._number(spec.min_gain, 0.0, 1000.0)
        form.addRow(tr('Marge au bord de la plaque (mm)'), self.margin)
        form.addRow(tr('Écart entre objets (mm)'), self.gap)
        form.addRow(tr('Quart de tour permis'), self.rotate)
        form.addRow(tr('Selon la vraie forme des objets (sinon : leurs rectangles)'), self.shape)
        form.addRow(tr('Forme : pas de rotation (°, 90 : quarts de tour)'), self.angle)
        form.addRow(tr('Forme : angles permis (°, ex. 0;90;180 ; vide : d’après le pas)'), self.angles)
        form.addRow(tr('Forme : ranger aussi dans les trous des autres'), self.holes)
        form.addRow(tr('Forme : retournement permis (miroir)'), self.mirror)
        form.addRow(tr('Forme : précision (mm ; plus fin : plus serré, plus long)'), self.precision)
        form.addRow(tr('Point de départ'), self.corner)
        form.addRow(tr('Direction'), self.direction)
        form.addRow(tr('Un plan par plaque (sinon : plaques suivantes à droite)'), self.planes)
        form.addRow(tr('Optimiseur : nombre d’essais (1 : un seul rangement)'), self.tries)
        form.addRow(tr('Optimiseur : essayer les deux directions'), self.both_ways)
        form.addRow(tr('Optimiseur : durée maximale (s)'), self.seconds)
        form.addRow(tr('Optimiseur : s’arrêter à ce gain de remplissage (%, 0 : faire tous les essais)'), self.gain)
        col.addWidget(box)
        self.summary = QLabel()
        col.addWidget(self.summary)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        col.addWidget(bb)
        self.same.toggled.connect(self._sync)
        self.same_count.valueChanged.connect(self._sync)
        self.shape.toggled.connect(self._sync)
        for sp in self.spins:
            sp.valueChanged.connect(self._sync)
        self._sync()

    @staticmethod
    def _number(value: float, lo: float, hi: float) -> QDoubleSpinBox:
        sp = QDoubleSpinBox()
        sp.setDecimals(3)
        sp.setRange(lo, hi)
        sp.setValue(value)
        return sp

    def _sync(self, *_a) -> None:
        same = self.same.isChecked()
        self.same_count.setEnabled(same)
        for sp in self.spins:
            sp.setEnabled(not same)
        for w in (self.angle, self.angles, self.holes, self.mirror, self.precision):
            w.setEnabled(self.shape.isChecked())
        self.summary.setText(tr('{0} exemplaire(s) à ranger').format(sum(self.counts())))

    def counts(self) -> list[int]:
        if self.same.isChecked():
            return [self.same_count.value()] * len(self.items)
        return [sp.value() for sp in self.spins]

    def names(self) -> list[str]:
        return [self.table.item(i, 0).text().strip() for i in range(len(self.items))]

    def result_params(self) -> dict:
        names = {}
        for i, (it, name) in enumerate(zip(self.items, self.names())):
            if name and name != _name_of(it, i):
                names[id(it)] = name
        spec = replace(self.spec, margin=self.margin.value(), gap=self.gap.value(), allow_rotate=self.rotate.isChecked(),
                       shape=self.shape.isChecked(), angle_step=self.angle.value(), angles=self.angles.text().strip(),
                       in_holes=self.holes.isChecked(),
                       allow_mirror=self.mirror.isChecked(), precision=self.precision.value(), corner=str(self.corner.currentData()),
                       vertical=bool(self.direction.currentData()), counts=self.counts(), tries=self.tries.value(),
                       both_ways=self.both_ways.isChecked(), max_seconds=self.seconds.value(), min_gain=self.gain.value())
        return {'spec': spec, 'per_plane': self.planes.isChecked(), 'names': names, 'same': self.same.isChecked(),
                'count': self.same_count.value()}
