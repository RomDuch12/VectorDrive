"""Assistant Texte en colonnes, réuni en une fenêtre : méthode, position, colonnes, bordures, contenu des cellules."""
from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                               QGroupBox, QHBoxLayout, QHeaderView, QLabel, QRadioButton, QSpinBox, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from ..core import textcolumns as TC
from ..i18n import tr
from .dialogs import FontBox


def _number(value: float, low: float, high: float, decimals: int = 3) -> QDoubleSpinBox:
    w = QDoubleSpinBox()
    w.setRange(low, high)
    w.setDecimals(decimals)
    w.setValue(float(value))
    return w


class TextColumnsDialog(QDialog):
    #: colonnes de la table des réglages
    C_WIDTH, C_ALIGN, C_LEFT, C_TEXT, C_BOTTOM = range(5)

    def __init__(self, parent, spec: TC.TextColumns, tools: list, grid_class):
        super().__init__(parent)
        self.setWindowTitle(tr('Texte en colonnes'))
        spec = TC.clean(spec)
        col = QVBoxLayout(self)
        top = QHBoxLayout()
        col.addLayout(top)

        method = QGroupBox(tr('Méthode'))
        form = QFormLayout(method)
        self.by_line = QRadioButton(tr('Positionner sur la ligne de base'))
        self.by_table = QRadioButton(tr('Positionner dans un tableau'))
        (self.by_table if spec.method == 'table' else self.by_line).setChecked(True)
        form.addRow(self.by_line)
        form.addRow(self.by_table)
        self.height = _number(spec.height, 0.01, 10000.0)
        self.height.setToolTip(tr('Elle prime sur la hauteur de ligne'))
        self.font = FontBox()
        self.font.setCurrentFont(QFont(spec.font))
        form.addRow(tr('Hauteur des caractères (mm)'), self.height)
        form.addRow(tr('Police'), self.font)
        top.addWidget(method)

        place = QGroupBox(tr('Position'))
        form = QFormLayout(place)
        self.x = _number(spec.x, -1e6, 1e6)
        self.y = _number(spec.y, -1e6, 1e6)
        self.point3 = QComboBox()
        for fx, label in ((0.0, tr('Gauche')), (0.5, tr('Milieu')), (1.0, tr('Droite'))):
            self.point3.addItem(label, fx)
        self.point3.setCurrentIndex(max(0, self.point3.findData(float(spec.anchor[0]))))
        self.grid = grid_class(lambda _p: None)
        self.grid.set_point((float(spec.anchor[0]), float(spec.anchor[1])))
        form.addRow(tr('Point de la première ligne de base'), self.point3)
        form.addRow(tr('Point du tableau'), self.grid)
        form.addRow('X', self.x)
        form.addRow('Y', self.y)
        top.addWidget(place)

        size = QGroupBox(tr('Dimensions'))
        form = QFormLayout(size)
        self.rows = QSpinBox()
        self.rows.setRange(1, TC.MAX_ROWS)
        self.rows.setValue(spec.rows)
        self.cols = QSpinBox()
        self.cols.setRange(1, TC.MAX_COLS)
        self.cols.setValue(spec.cols)
        self.line_height = _number(spec.line_height, 0.01, 100000.0)
        self.total_w = _number(spec.total_w, 0.01, 1000000.0)
        self.total_h = _number(spec.total_h, 0.01, 1000000.0)
        self.same = QCheckBox(tr('Même largeur de colonnes'))
        self.same.setChecked(spec.same)
        form.addRow(tr('Nombre de lignes'), self.rows)
        form.addRow(tr('Nombre de colonnes'), self.cols)
        form.addRow(tr('Interligne (mm)'), self.line_height)
        form.addRow(tr('Largeur du tableau (mm)'), self.total_w)
        form.addRow(tr('Hauteur du tableau (mm)'), self.total_h)
        form.addRow(self.same)
        top.addWidget(size)

        col.addWidget(QLabel(tr('Colonnes')))
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([tr('Largeur (mm)'), tr('Alignement'), tr('Marge gauche (%)'),
                                              tr('Largeur du texte (%)'), tr('Marge inférieure (mm)')])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setMaximumHeight(130)
        col.addWidget(self.table)

        row = QHBoxLayout()
        self.borders = QComboBox()
        for k, label in (('all', tr('Tout')), ('frame', tr('Cadre')), ('h', tr('Lignes horizontales')),
                         ('v', tr('Lignes verticales')), ('none', tr('Aucune'))):
            self.borders.addItem(label, k)
        self.borders.setCurrentIndex(max(0, self.borders.findData(spec.borders)))
        self.tool = QComboBox()
        for i, name in tools:
            self.tool.addItem(name, i)
        self.tool.setCurrentIndex(max(0, self.tool.findData(spec.border_tool)))
        self.tool.setToolTip(tr('Elle ne s’applique qu’aux bordures'))
        row.addWidget(QLabel(tr('Bordures')))
        row.addWidget(self.borders)
        row.addWidget(QLabel(tr('Couleur')))
        row.addWidget(self.tool)
        row.addStretch(1)
        col.addLayout(row)

        col.addWidget(QLabel(tr('Contenu : Tab passe à la cellule suivante ; Ctrl+V colle un tableau copié')))
        self.content = QTableWidget(spec.rows, spec.cols)
        self.content.setEditTriggers(QAbstractItemView.EditTrigger.AllEditTriggers)
        self.content.setTabKeyNavigation(True)
        self.content.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.content.installEventFilter(self)
        col.addWidget(self.content, 1)
        for i in range(spec.rows):
            for j in range(spec.cols):
                self.content.setItem(i, j, QTableWidgetItem(TC.cell_text(spec, i, j)))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        col.addWidget(buttons)

        self._columns = [TC.Column(**vars(c)) for c in spec.columns]
        self._fill_columns()
        self.by_line.toggled.connect(lambda _on: self._refresh())
        self.same.toggled.connect(lambda _on: self._refresh())
        self.rows.valueChanged.connect(self.content.setRowCount)
        self.cols.valueChanged.connect(self._cols_changed)
        self._refresh()
        self.resize(820, 640)

    # --- réglages des colonnes ------------------------------------------------------------
    def _fill_columns(self) -> None:
        self.table.setRowCount(len(self._columns))
        self.table.setVerticalHeaderLabels([str(i + 1) for i in range(len(self._columns))])
        for i, c in enumerate(self._columns):
            self.table.setCellWidget(i, self.C_WIDTH, _number(c.width, 0.01, 100000.0))
            box = QComboBox()
            for k, label in (('left', tr('À gauche')), ('center', tr('Centré')), ('right', tr('À droite')),
                             ('justify', tr('Justifié'))):
                box.addItem(label, k)
            box.setCurrentIndex(max(0, box.findData(c.align)))
            self.table.setCellWidget(i, self.C_ALIGN, box)
            self.table.setCellWidget(i, self.C_LEFT, _number(c.left, 0.0, 100.0, 1))
            self.table.setCellWidget(i, self.C_TEXT, _number(c.text_width, 1.0, 100.0, 1))
            self.table.setCellWidget(i, self.C_BOTTOM, _number(c.bottom, -100000.0, 100000.0))

    def columns(self) -> list:
        out = []
        for i in range(self.table.rowCount()):
            cell = self.table.cellWidget
            out.append(TC.Column(width=cell(i, self.C_WIDTH).value(), align=cell(i, self.C_ALIGN).currentData(),
                                 left=cell(i, self.C_LEFT).value(), text_width=cell(i, self.C_TEXT).value(),
                                 bottom=cell(i, self.C_BOTTOM).value()))
        return out

    def _cols_changed(self, n: int) -> None:
        self._columns = self.columns()
        while len(self._columns) < n:
            self._columns.append(TC.Column(**vars(self._columns[-1])))
        del self._columns[n:]
        self._fill_columns()
        self.content.setColumnCount(n)
        self._refresh()

    def _refresh(self) -> None:
        table = self.by_table.isChecked()
        same = self.same.isChecked()
        self.point3.setEnabled(not table)
        self.grid.setEnabled(table)
        self.line_height.setEnabled(not table)
        self.total_w.setEnabled(table and same)          # sinon, la somme des colonnes
        self.total_h.setEnabled(table)
        # un tableau garde ses bordures ; sur la ligne de base, on peut s'en passer
        model = self.borders.model().item(self.borders.findData('none'))
        model.setEnabled(not table)
        if table and self.borders.currentData() == 'none':
            self.borders.setCurrentIndex(self.borders.findData('all'))
        for i in range(self.table.rowCount()):
            on = not same or i == 0
            for j in range(5):
                w = self.table.cellWidget(i, j)
                w.setEnabled(on and not (j == self.C_WIDTH and table and same))

    # --- contenu ----------------------------------------------------------------------------
    def eventFilter(self, obj, ev) -> bool:
        if obj is self.content and ev.type() == QEvent.Type.KeyPress and ev.key() == Qt.Key.Key_V \
                and ev.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.paste(QGuiApplication.clipboard().text())
            return True
        return super().eventFilter(obj, ev)

    def paste(self, text: str) -> None:
        """Un tableau copié (lignes, tabulations), à partir de la cellule courante ; le tableau grandit s'il le faut."""
        rows = [ln.split('\t') for ln in text.replace('\r\n', '\n').rstrip('\n').split('\n')]
        if not rows or not any(any(c for c in r) for r in rows):
            return
        i0, j0 = max(self.content.currentRow(), 0), max(self.content.currentColumn(), 0)
        need_rows = min(i0 + len(rows), TC.MAX_ROWS)
        need_cols = min(j0 + max(len(r) for r in rows), TC.MAX_COLS)
        if need_rows > self.rows.value():
            self.rows.setValue(need_rows)
        if need_cols > self.cols.value():
            self.cols.setValue(need_cols)
        for i, r in enumerate(rows):
            for j, s in enumerate(r):
                if i0 + i < need_rows and j0 + j < need_cols:
                    self.content.setItem(i0 + i, j0 + j, QTableWidgetItem(s))

    def cells(self) -> list:
        out = []
        for i in range(self.content.rowCount()):
            out.append([(self.content.item(i, j).text() if self.content.item(i, j) else '')
                        for j in range(self.content.columnCount())])
        return out

    def spec(self) -> TC.TextColumns:
        table = self.by_table.isChecked()
        anchor = list(self.grid.point()) if table else [self.point3.currentData(), 1.0]
        return TC.clean(TC.TextColumns(
            method='table' if table else 'baseline', height=self.height.value(), font=self.font.currentText(),
            rows=self.rows.value(), cols=self.cols.value(), x=self.x.value(), y=self.y.value(), anchor=anchor,
            line_height=self.line_height.value(), total_w=self.total_w.value(), total_h=self.total_h.value(),
            same=self.same.isChecked(), columns=self.columns(), borders=self.borders.currentData(),
            border_tool=int(self.tool.currentData() or 0), cells=self.cells()))
