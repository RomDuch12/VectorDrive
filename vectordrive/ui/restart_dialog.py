"""La fenêtre de la reprise d'usinage : les points du parcours, M pour une entrée dans la matière, L pour un changement de direction."""
from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView, QLabel,
                               QPushButton, QTableView, QVBoxLayout)

from ..cam import restart
from ..i18n import tr


class _Points(QAbstractTableModel):
    """Une table légère : un parcours 3D compte des millions de points."""

    def __init__(self, dialog):
        super().__init__()
        self.dialog = dialog
        self.rows_shown: list = []

    def show(self, rows: list) -> None:
        self.beginResetModel()
        self.rows_shown = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.rows_shown)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else 6

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return ('', tr('N°'), '', 'X', 'Y', 'Z')[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.TextAlignmentRole and index.column() >= 3:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        d = self.dialog
        i = self.rows_shown[index.row()]
        c = index.column()
        if c == 0:
            return '▶' if i == d.start else '■' if i == d.end else ''
        if c == 1:
            return i + 1
        if c == 2:
            return 'M' if i in d.entry_set else 'L'
        m = d.moves[i]
        return f'{(m.x, m.y, m.z)[c - 3]:.3f}'


class RestartDialog(QDialog):
    """`start` et `end` : le point de reprise et le dernier point usiné, en numéros de mouvement."""

    def __init__(self, parent, title: str, moves: list, op=None):
        super().__init__(parent)
        self.setWindowTitle(tr('Reprise d\'usinage : {0}').format(title))
        self.resize(560, 560)
        self.moves = moves
        self.all_rows = restart.rows(moves)
        self.entries = restart.entries(moves)
        self.entry_set = set(self.entries)
        span = restart.current(op, moves) if op is not None else None
        self.start, self.end = span if span else (self.all_rows[0], self.all_rows[-1])
        box = QVBoxLayout(self)
        note = QLabel(tr('Choisissez le point où l\'usinage reprend et le dernier point usiné. M : entrée dans la matière ; '
                         'L : changement de direction. L\'outil descend en plongée au point de reprise.'))
        note.setWordWrap(True)
        box.addWidget(note)
        self.only_entries = QCheckBox(tr('Seulement les entrées dans la matière'))
        self.only_entries.setChecked(bool(self.entries))
        self.only_entries.setEnabled(bool(self.entries))
        self.only_entries.toggled.connect(self._filter)
        box.addWidget(self.only_entries)
        self.model = _Points(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.doubleClicked.connect(lambda _i: self._take('start'))
        box.addWidget(self.table, 1)
        row = QHBoxLayout()
        for text, key in ((tr('Reprendre ici'), 'start'), (tr('Finir ici'), 'end')):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, k=key: self._take(k))
            row.addWidget(b)
        whole = QPushButton(tr('Tout le parcours'))
        whole.clicked.connect(lambda _=False: self.reset())
        row.addWidget(whole)
        row.addStretch(1)
        box.addLayout(row)
        self.summary = QLabel()
        box.addWidget(self.summary)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        box.addWidget(buttons)
        self._filter()

    def _filter(self, *_args) -> None:
        self.model.show(self.entries if self.only_entries.isChecked() else self.all_rows)
        self._say()

    def _say(self) -> None:
        kept = sum(1 for i in self.entries if self.start <= i <= self.end)
        self.summary.setText(tr('Du mouvement {0} au mouvement {1} sur {2} ; {3} entrée(s) dans la matière sur {4}').format(
            self.start + 1, self.end + 1, len(self.moves), kept, len(self.entries)))
        self.model.dataChanged.emit(self.model.index(0, 0), self.model.index(max(0, self.model.rowCount() - 1), 0))

    def _take(self, which: str) -> None:
        at = self.table.currentIndex()
        if at.isValid():
            self.set_point(which, self.model.rows_shown[at.row()])

    def set_point(self, which: str, i: int) -> None:
        """Une reprise après la fin, ou une fin avant la reprise : l'autre borne s'écarte."""
        if which == 'start':
            self.start = i
            if self.end < i:
                self.end = self.all_rows[-1]
        else:
            self.end = i
            if self.start > i:
                self.start = self.all_rows[0]
        self._say()

    def reset(self) -> None:
        self.start, self.end = self.all_rows[0], self.all_rows[-1]
        self._say()
