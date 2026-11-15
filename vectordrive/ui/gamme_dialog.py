"""Fenêtre de la gamme à plusieurs outils (manuel de TE, pages 619 à 621) : une ligne par outil, et les réglages de toute la gamme."""
from __future__ import annotations

from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                               QHBoxLayout, QHeaderView, QMessageBox, QPushButton, QTableWidget, QVBoxLayout)

from ..cam import gamme
from ..i18n import tr


def _spin(value: float, top: float, suffix: str = ' mm', low: float = 0.0, decimals: int = 3) -> QDoubleSpinBox:
    sp = QDoubleSpinBox()
    sp.setRange(low, top)
    sp.setDecimals(decimals)
    sp.setSuffix(suffix)
    sp.setValue(value)
    return sp


class GammeDialog(QDialog):
    """`setup` : les outils du document. `steps` : les lignes de départ. Après OK : `steps()`, `depth`, `stock`, `contour_ref`,
    `skip_frame`, `z_start`. Les outils sont classés à la validation."""
    COLUMNS = ('Outil', 'Usinage', 'Distance entre passes', 'Profondeur', 'Profondeur de passe', 'Finition 3D', 'Angle')

    def __init__(self, parent, setup, steps: list, depth: float = 0.5):
        super().__init__(parent)
        self.setup_doc = setup
        self.tools = [t for t in setup.tools if t.kind != 'laser']
        self.setWindowTitle(tr('Gamme multi-outils'))
        lay = QVBoxLayout(self)
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels([tr(c) for c in self.COLUMNS])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.table, 1)
        row = QHBoxLayout()
        self.add_btn = QPushButton(tr('Ajouter un outil'))
        self.add_btn.clicked.connect(lambda: self.add_step())
        self.del_btn = QPushButton(tr('Retirer'))
        self.del_btn.clicked.connect(self.remove_step)
        row.addWidget(self.add_btn)
        row.addWidget(self.del_btn)
        row.addStretch(1)
        lay.addLayout(row)
        form = QFormLayout()
        self.w_z = _spin(0.0, 1000.0, low=-1000.0)
        self.w_depth = _spin(depth, 1000.0)
        self.w_ref = QComboBox()
        self.w_ref.addItem(tr('En surface'), 'surface')
        self.w_ref.addItem(tr('En fond de gravure'), 'fond')
        self.w_stock = _spin(0.0, 100.0)
        self.w_frame = QCheckBox(tr('Ignorer le cadre englobant'))
        form.addRow(tr('Z de départ'), self.w_z)
        form.addRow(tr('Profondeur totale'), self.w_depth)
        form.addRow(tr('Respect du contour'), self.w_ref)
        form.addRow(tr('Surépaisseur XY laissée pour la finition'), self.w_stock)
        form.addRow('', self.w_frame)
        lay.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        for s in steps:
            self.add_step(s)
        self.resize(760, 420)

    def add_step(self, step=None) -> None:
        """Une ligne de plus : l'outil suivant de la liste, par défaut."""
        r = self.table.rowCount()
        step = step or gamme.Step(self.tools[min(r, len(self.tools) - 1)].id if self.tools else '')
        self.table.insertRow(r)
        tool = QComboBox()
        for t in self.tools:
            tool.addItem(f'T{t.number} {t.name}', t.id)
        tool.setCurrentIndex(max(0, tool.findData(step.tool_id)))
        mode = QComboBox()
        mode.addItem(tr('Balayage'), 'balayage')
        mode.addItem(tr('Contournage'), 'contournage')
        mode.setCurrentIndex(max(0, mode.findData(step.mode)))
        finish = QCheckBox()
        finish.setChecked(step.finish3d)
        for col, w in enumerate((tool, mode, _spin(step.stepover, 100.0), _spin(step.depth, 1000.0), _spin(step.step_down, 1000.0), finish,
                                 _spin(step.sweep_angle, 360.0, ' °', -360.0, 2))):
            self.table.setCellWidget(r, col, w)

    def remove_step(self) -> None:
        r = self.table.currentRow()
        self.table.removeRow(r if r >= 0 else self.table.rowCount() - 1)

    def steps(self) -> list:
        cell = self.table.cellWidget
        return [gamme.Step(cell(r, 0).currentData(), cell(r, 1).currentData(), cell(r, 2).value(), cell(r, 3).value(),
                           cell(r, 5).isChecked(), cell(r, 6).value(), cell(r, 4).value()) for r in range(self.table.rowCount())]

    @property
    def depth(self) -> float:
        return self.w_depth.value()

    @property
    def stock(self) -> float:
        return self.w_stock.value()

    @property
    def contour_ref(self) -> str:
        return self.w_ref.currentData()

    @property
    def skip_frame(self) -> bool:
        return self.w_frame.isChecked()

    @property
    def z_start(self) -> float:
        return self.w_z.value()

    def accept(self) -> None:
        why = gamme.problem(self.setup_doc, self.steps(), self.depth)
        if why:
            QMessageBox.warning(self, tr('Gamme multi-outils'), tr(why))
            return
        super().accept()
