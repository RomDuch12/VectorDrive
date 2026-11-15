"""Importer un fichier de variables : réglages de l'extraction, avec l'aperçu de ce qu'elle donne."""
from __future__ import annotations

from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox,
                               QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QSpinBox, QTableWidget, QTableWidgetItem,
                               QVBoxLayout)

from ..core import variables as V
from ..i18n import tr

SHOWN_LINES = 200
SHOWN_ROWS = 100


class VariablesImportDialog(QDialog):
    def __init__(self, parent, text: str, header: bool = True):
        super().__init__(parent)
        self.setWindowTitle(tr('Importer un fichier de variables'))
        self.resize(820, 620)
        self.text = text
        col = QVBoxLayout(self)
        row = QHBoxLayout()
        col.addLayout(row)

        box = QGroupBox(tr('Extraction'))
        form = QFormLayout(box)
        self.start = QSpinBox()
        self.start.setRange(0, 10000000)
        self.start.valueChanged.connect(self._refresh)
        self.header = QCheckBox()
        self.header.setChecked(header)
        self.header.toggled.connect(self._refresh)
        self.group = QCheckBox()
        self.group.toggled.connect(self._refresh)
        self.mode = QComboBox()
        self.mode.addItem(tr('Séparateur'), 'sep')
        self.mode.addItem(tr('Largeur constante'), 'fixed')
        self.mode.currentIndexChanged.connect(self._refresh)
        self.col_sep = QComboBox()
        self.col_sep.addItem(tr('Deviné d’après le fichier'), None)
        self.col_sep.addItem(tr('Point-virgule'), ';')
        self.col_sep.addItem(tr('Tabulation'), '\t')
        self.col_sep.addItem(tr('Virgule'), ',')
        self.col_sep.addItem(tr('Espace'), ' ')
        self.col_sep.addItem(tr('Barre verticale'), '|')
        self.col_sep.addItem(tr('Autre'), 'autre')
        self.col_sep.currentIndexChanged.connect(self._refresh)
        self.col_other = QLineEdit()
        self.col_other.textChanged.connect(self._refresh)
        self.line_sep = QComboBox()
        self.line_sep.addItem(tr('Fin de ligne'), None)
        self.line_sep.addItem(tr('Point-virgule'), ';')
        self.line_sep.addItem(tr('Tabulation'), '\t')
        self.line_sep.addItem(tr('Barre verticale'), '|')
        self.line_sep.addItem(tr('Autre'), 'autre')
        self.line_sep.currentIndexChanged.connect(self._refresh)
        self.line_other = QLineEdit()
        self.line_other.textChanged.connect(self._refresh)
        self.widths = QLineEdit()
        self.widths.setPlaceholderText(tr('5,10,3 ; un seul nombre : toutes les colonnes'))
        self.widths.textChanged.connect(self._refresh)
        form.addRow(tr('Commencer à la ligne (0 : au début)'), self.start)
        form.addRow(tr('La première ligne porte les noms des variables'), self.header)
        form.addRow(tr('Regrouper les lignes identiques qui se suivent'), self.group)
        form.addRow(tr('Mode d’extraction'), self.mode)
        form.addRow(tr('Séparateur de colonnes'), self.col_sep)
        form.addRow(tr('Autre séparateur de colonnes'), self.col_other)
        form.addRow(tr('Séparateur de lignes'), self.line_sep)
        form.addRow(tr('Autre séparateur de lignes'), self.line_other)
        form.addRow(tr('Format des colonnes (nombre de caractères)'), self.widths)
        row.addWidget(box)

        self.raw = QPlainTextEdit()
        self.raw.setReadOnly(True)
        self.raw.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        row.addWidget(self.raw, 1)

        col.addWidget(QLabel(tr('Aperçu de l’extraction')))
        self.preview = QTableWidget(0, 0)
        self.preview.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        col.addWidget(self.preview, 1)
        self.summary = QLabel()
        col.addWidget(self.summary)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        col.addWidget(buttons)
        lines = V.split_lines(text)
        self.raw.setPlainText('\n'.join(f'[{i}] {ln}' for i, ln in enumerate(lines[:SHOWN_LINES])))
        self._refresh()

    def _choice(self, combo: QComboBox, other: QLineEdit):
        value = combo.currentData()
        return (other.text() or None) if value == 'autre' else value

    def table(self) -> V.VarTable:
        """Le tableau que donnent les réglages."""
        fixed = self.mode.currentData() == 'fixed'
        widths = V.parse_widths(self.widths.text()) if fixed else None
        return V.parse_data(self.text, sep=None if fixed else self._choice(self.col_sep, self.col_other),
                            header=self.header.isChecked(), start=self.start.value(),
                            line_sep=self._choice(self.line_sep, self.line_other), widths=widths, group=self.group.isChecked())

    def _refresh(self, *_a) -> None:
        if not hasattr(self, 'summary'):
            return
        fixed = self.mode.currentData() == 'fixed'
        self.col_sep.setEnabled(not fixed)
        self.col_other.setEnabled(not fixed and self.col_sep.currentData() == 'autre')
        self.line_other.setEnabled(self.line_sep.currentData() == 'autre')
        self.widths.setEnabled(fixed)
        t = self.table()
        self.preview.setColumnCount(len(t.names))
        self.preview.setHorizontalHeaderLabels(t.names)
        self.preview.setRowCount(min(len(t.rows), SHOWN_ROWS))
        for r, values in enumerate(t.rows[:SHOWN_ROWS]):
            for c, v in enumerate(values):
                self.preview.setItem(r, c, QTableWidgetItem(v))
        self.summary.setText(tr('{0} variable(s), {1} ligne(s)').format(len(t.names), len(t.rows)))
        self.ok.setEnabled(bool(t.names))
