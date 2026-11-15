"""Fenêtre des variables (comme TypeEdit : Saisie de variables) : une colonne
par variable, une ligne par état ; ajouter, renommer, supprimer, séries,
import d'un fichier de données, état affiché sur le dessin."""
from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                               QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton,
                               QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout)

from ..core import variables as V
from ..i18n import tr


class SeriesDialog(QDialog):
    """Série (TypeEdit : Séries) : départ, pas, nombre ou valeur finale,
    format, chiffres constants, texte avant et après, aperçu."""

    KINDS = ['numérique', 'alphabétique', 'alphanumérique']

    def __init__(self, parent, names: list):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        self.setWindowTitle(tr('Série'))
        f = QFormLayout(self)
        self.target = QComboBox()
        self.target.setEditable(True)
        self.target.addItems(names or ['VAR1'])
        self.start, self.step, self.count = QSpinBox(), QSpinBox(), QSpinBox()
        for w, v in ((self.start, 1), (self.step, 1), (self.count, 10)):
            w.setRange(-1_000_000, 1_000_000)
            w.setValue(v)
        self.use_end = QCheckBox(tr('Jusqu\'à la valeur finale'))
        self.end = QSpinBox()
        self.end.setRange(-1_000_000, 1_000_000)
        self.end.setValue(10)
        self.kind = QComboBox()
        for k in self.KINDS:
            self.kind.addItem(tr(k.capitalize()), k)
        self.width = QLineEdit()
        self.width.setPlaceholderText('###')
        self.before, self.after = QLineEdit(), QLineEdit()
        self.preview = QLabel()
        self.preview.setWordWrap(True)
        f.addRow(tr('Variable'), self.target)
        f.addRow(tr('Départ'), self.start)
        f.addRow(tr('Pas'), self.step)
        f.addRow(tr('Nombre de valeurs'), self.count)
        f.addRow(self.use_end, self.end)
        f.addRow(tr('Format'), self.kind)
        f.addRow(tr('Chiffres constants (# par chiffre)'), self.width)
        f.addRow(tr('Texte avant'), self.before)
        f.addRow(tr('Texte après'), self.after)
        f.addRow(tr('Aperçu'), self.preview)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)
        for w in (self.start, self.step, self.count, self.end):
            w.valueChanged.connect(lambda _v: self._update())
        for w in (self.width, self.before, self.after):
            w.textChanged.connect(lambda _t: self._update())
        self.use_end.toggled.connect(lambda _on: self._update())
        self.kind.currentIndexChanged.connect(lambda _i: self._update())
        self._update()

    def values(self) -> list[str]:
        return V.series(self.start.value(), self.step.value(), self.count.value(),
                        end=self.end.value() if self.use_end.isChecked() else None,
                        kind=self.kind.currentData(), width=self.width.text(), before=self.before.text(),
                        after=self.after.text())

    def _update(self) -> None:
        self.count.setEnabled(not self.use_end.isChecked())
        self.end.setEnabled(self.use_end.isChecked())
        v = self.values()
        self.preview.setText(', '.join(v[:8]) + (' …' if len(v) > 8 else '') + f'  ({len(v)})')


class VariablesDialog(QDialog):
    def __init__(self, parent, table: V.VarTable):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        self.setWindowTitle(tr('Variables'))
        self.setSizeGripEnabled(True)
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel(tr('Afficher l\'état')))
        self.state = QComboBox()
        top.addWidget(self.state, 1)
        lay.addLayout(top)
        self.grid = QTableWidget()
        lay.addWidget(self.grid, 1)
        row = QHBoxLayout()
        for text, slot in ((tr('Ajouter une variable…'), self.add_variable),
                           (tr('Renommer…'), self.rename_variable), (tr('Supprimer la variable'), self.remove_variable),
                           (tr('Ajouter une ligne'), self.add_row), (tr('Supprimer la ligne'), self.remove_row),
                           (tr('Séries…'), self.add_series), (tr('Importer…'), self.import_file)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, s=slot: s())
            row.addWidget(b)
        lay.addLayout(row)
        hint = QLabel(tr('Dans un texte, |Nom| prend la valeur de la variable ; |Date dd/MM/yyyy| et |Heure HH:mm| '
                         'la date et l\'heure de la fabrication.'))
        hint.setWordWrap(True)
        lay.addWidget(hint)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.load(table)
        self.resize(760, 480)

    # --- tableau ↔ grille ------------------------------------------------------------------------
    def load(self, table: V.VarTable) -> None:
        self.grid.clear()
        self.grid.setColumnCount(len(table.names))
        self.grid.setRowCount(len(table.rows))
        self.grid.setHorizontalHeaderLabels(table.names)
        for r, values in enumerate(table.rows):
            for c, v in enumerate(values):
                self.grid.setItem(r, c, QTableWidgetItem(v))
        self._states(table.current)

    def table(self) -> V.VarTable:
        names = [self.grid.horizontalHeaderItem(c).text() for c in range(self.grid.columnCount())]
        rows = [[(self.grid.item(r, c).text() if self.grid.item(r, c) else '') for c in range(len(names))]
                for r in range(self.grid.rowCount())]
        return V.VarTable(names, rows, max(0, self.state.currentIndex()))

    def _states(self, current: int = 0) -> None:
        self.state.clear()
        for r in range(self.grid.rowCount()):
            self.state.addItem(tr('Ligne {0}').format(r + 1))
        if self.grid.rowCount():
            self.state.setCurrentIndex(max(0, min(current, self.grid.rowCount() - 1)))

    # --- commandes ---------------------------------------------------------------------------------
    def add_variable(self, name: str | None = None) -> bool:
        t = self.table()
        if name is None:
            name, ok = QInputDialog.getText(self, tr('Ajouter une variable'), tr('Nom'),
                                            text=f'VAR{len(t.names) + 1}')
            if not ok:
                return False
        try:
            t.add_variable(name)
        except ValueError as e:
            QMessageBox.information(self, tr('Variables'), str(e))
            return False
        self.load(t)
        return True

    def _column(self) -> str | None:
        c = self.grid.currentColumn()
        t = self.table()
        return t.names[c] if 0 <= c < len(t.names) else (t.names[-1] if t.names else None)

    def rename_variable(self, new: str | None = None) -> bool:
        old = self._column()
        if old is None:
            return False
        if new is None:
            new, ok = QInputDialog.getText(self, tr('Renommer'), tr('Nouveau nom'), text=old)
            if not ok:
                return False
        t = self.table()
        try:
            t.rename(old, new)
        except ValueError as e:
            QMessageBox.information(self, tr('Variables'), str(e))
            return False
        self.load(t)
        return True

    def remove_variable(self) -> None:
        name = self._column()
        if name is None:
            return
        t = self.table()
        t.remove_variable(name)
        self.load(t)

    def add_row(self) -> None:
        t = self.table()
        t.rows.append([''] * len(t.names))
        self.load(t)

    def remove_row(self) -> None:
        r = self.grid.currentRow()
        t = self.table()
        if 0 <= r < len(t.rows):
            del t.rows[r]
            self.load(t)

    def fill_column(self, name: str, values: list) -> None:
        """Valeurs d'une colonne (créée si besoin), lignes ajoutées au besoin."""
        t = self.table()
        if name not in t.names:
            t.add_variable(name)
        i = t.names.index(name)
        while len(t.rows) < len(values):
            t.rows.append([''] * len(t.names))
        for r, v in enumerate(values):
            t.rows[r][i] = v
        self.load(t)

    def add_series(self) -> bool:
        dlg = SeriesDialog(self, self.table().names)
        if not dlg.exec():
            return False
        self.fill_column(dlg.target.currentText().strip() or 'VAR1', dlg.values())
        return True

    def import_file(self, path: str | None = None, header: bool | None = None) -> bool:
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, tr('Importer des données'), '',
                                                  tr('Texte (*.txt *.csv);;Tous (*.*)'))
            if not path:
                return False
        import pathlib
        try:
            text = V.decode_text(pathlib.Path(path).read_bytes())
        except OSError as ex:
            QMessageBox.warning(self, tr('Importer des données'), tr('Impossible de lire ce fichier : {0}').format(ex))
            return False
        if header is None:                               # les réglages de l'extraction, avec leur aperçu
            from .variables_import import VariablesImportDialog
            dlg = VariablesImportDialog(self, text)
            self.last_import_dialog = dlg
            if not dlg.exec():
                return False
            self.load(dlg.table())
            return True
        self.load(V.parse_data(text, header=header))
        return True
