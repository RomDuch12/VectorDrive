"""Multicopie : l'assistant, avec son aperçu."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QGroupBox,
                               QHBoxLayout, QLabel, QSpinBox, QVBoxLayout, QWidget)

from ..core import multicopy as MC
from ..i18n import tr


class _Preview(QWidget):
    """Le premier plan : la plaque, les cellules numérotées dans leur ordre, les lignes de découpe."""

    def __init__(self, box, parent=None):
        super().__init__(parent)
        self.box = box
        self.lay = None
        self.spec = None
        self.setMinimumSize(320, 240)

    def show_layout(self, lay, spec) -> None:
        self.lay, self.spec = lay, spec
        self.update()

    def paintEvent(self, _ev) -> None:
        x0, y0, x1, y1 = self.box
        if x1 <= x0 or y1 <= y0:
            return
        k = min((self.width() - 12) / (x1 - x0), (self.height() - 12) / (y1 - y0))
        ox = (self.width() - (x1 - x0) * k) / 2
        oy = (self.height() - (y1 - y0) * k) / 2

        def at(x, y):
            return QPointF(ox + (x - x0) * k, self.height() - oy - (y - y0) * k)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(QRectF(at(x0, y1), at(x1, y0)), QColor('white'))
        p.setPen(QPen(QColor('#555555'), 1))
        p.drawRect(QRectF(at(x0, y1), at(x1, y0)))
        lay, spec = self.lay, self.spec
        if lay is None or not lay.cells:
            p.end()
            return
        first = [(n, c) for n, c in enumerate(lay.cells) if c.plate == 0]
        font = p.font()
        font.setPixelSize(max(8, min(16, int(min(lay.w, lay.h) * k * 0.5))))
        p.setFont(font)
        for n, c in first:
            r = QRectF(at(c.x, c.y + lay.h), at(c.x + lay.w, c.y))
            p.setPen(QPen(QColor('#1f6fb2'), 1))
            p.setBrush(QColor('#cfe3f5') if n == 0 else QColor('#eef5fb'))
            p.drawRect(r)
            p.setPen(QColor('#123a5c'))
            shown = str(n + 1)
            if c.back and spec.turn_back:
                p.save()
                p.translate(r.center())
                p.rotate(180)
                p.drawText(QRectF(-r.width() / 2, -r.height() / 2, r.width(), r.height()), Qt.AlignmentFlag.AlignCenter, shown)
                p.restore()
            else:
                p.drawText(r, Qt.AlignmentFlag.AlignCenter, shown)
        lines = MC.cut_lines(lay, [(c.col, c.row) for _n, c in first], spec, self.box)
        if lines is not None:
            p.setPen(QPen(QColor('#d0021b'), 1))
            for contour in lines.contours:
                a, b = contour.segments[0].start, contour.segments[-1].end
                p.drawLine(at(*a), at(*b))
        p.end()


class MulticopyDialog(QDialog):
    def __init__(self, parent, bb, box, spec: MC.MultiSpec, tools: list, rows_count: int = 0):
        super().__init__(parent)
        self.setWindowTitle(tr('Multicopie'))
        self.bb, self.box, self.spec0, self.rows_count = bb, box, spec, rows_count
        outer = QHBoxLayout(self)
        col = QVBoxLayout()
        outer.addLayout(col)

        size = QGroupBox(tr('Dimensions et quantité'))
        form = QFormLayout(size)
        self.margin = self._number(spec.margin)
        self.gap_x = self._number(spec.gap_x)
        self.gap_y = self._number(spec.gap_y)
        self.total = self._count(spec.total)
        self.planes = self._count(spec.planes)
        self.limit = self._check(spec.limit_to_rows)
        self.ignore = self._check(spec.ignore_first)
        self.keep = self._check(spec.keep_original)
        form.addRow(tr('Marge au bord de la plaque (mm)'), self.margin)
        form.addRow(tr('Écart horizontal (mm)'), self.gap_x)
        form.addRow(tr('Écart vertical (mm)'), self.gap_y)
        form.addRow(tr('Nombre total, original compris (0 : d’après les plans)'), self.total)
        form.addRow(tr('Nombre de plans (0 : une plaque remplie)'), self.planes)
        if rows_count:
            form.addRow(tr('Limiter aux données de la variable ({0} lignes)').format(rows_count), self.limit)
        form.addRow(tr('Ignorer le premier objet sélectionné (il donne la taille, sans être copié)'), self.ignore)
        form.addRow(tr('Conserver la sélection originale (exemplaires sur de nouveaux plans)'), self.keep)
        col.addWidget(size)

        where = QGroupBox(tr('Position'))
        form = QFormLayout(where)
        self.start = self._choice([('haut_gauche', tr('En haut à gauche')), ('haut_droit', tr('En haut à droite')),
                                   ('bas_gauche', tr('En bas à gauche')), ('bas_droit', tr('En bas à droite'))], spec.start)
        self.place = self._choice([('haut_gauche', tr('En haut à gauche')), ('haut_centre', tr('En haut au centre')),
                                   ('haut_droit', tr('En haut à droite')), ('milieu_gauche', tr('Au milieu à gauche')),
                                   ('centre', tr('Au milieu')), ('milieu_droit', tr('Au milieu à droite')),
                                   ('bas_gauche', tr('En bas à gauche')), ('bas_centre', tr('En bas au centre')),
                                   ('bas_droit', tr('En bas à droite'))], spec.place)
        self.from_sel = self._check(spec.from_selection)
        self.optimised = self._check(spec.optimised)
        self.turn_back = self._check(spec.turn_back)
        self.quarter = self._check(spec.quarter_turn)
        form.addRow(tr('Départ de la duplication'), self.start)
        form.addRow(tr('Position des éléments sur la plaque'), self.place)
        form.addRow(tr('Le premier exemplaire à la position de la sélection'), self.from_sel)
        form.addRow(tr('Optimisé : rangées en aller-retour'), self.optimised)
        form.addRow(tr('Optimisé : rangées du retour tournées d’un demi-tour'), self.turn_back)
        form.addRow(tr('Quart de tour s’il en tient plus'), self.quarter)
        col.addWidget(where)

        cuts = QGroupBox(tr('Lignes de découpe'))
        form = QFormLayout(cuts)
        self.cuts = self._choice([('aucune', tr('Aucune découpe')), ('partielle', tr('Découpe partielle')),
                                  ('totale', tr('Découpe totale'))], spec.cuts)
        self.cut_tool = QComboBox()
        for i, name in tools:
            self.cut_tool.addItem(name, i)
        at = self.cut_tool.findData(spec.cut_tool)
        self.cut_tool.setCurrentIndex(max(at, 0))
        self.cut_tool.currentIndexChanged.connect(self._refresh)
        self.tick = self._number(spec.tick)
        form.addRow(tr('Type'), self.cuts)
        form.addRow(tr('Couleur'), self.cut_tool)
        form.addRow(tr('Découpe partielle : longueur des traits (mm)'), self.tick)
        col.addWidget(cuts)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        col.addWidget(buttons)

        side = QVBoxLayout()
        outer.addLayout(side, 1)
        self.preview = _Preview(box, self)
        side.addWidget(self.preview, 1)
        self.summary = QLabel()
        side.addWidget(self.summary)
        self._refresh()

    def _number(self, value: float) -> QDoubleSpinBox:
        sp = QDoubleSpinBox()
        sp.setRange(0.0, 100000.0)
        sp.setDecimals(3)
        sp.setValue(float(value))
        sp.valueChanged.connect(self._refresh)
        return sp

    def _count(self, value: int) -> QSpinBox:
        sp = QSpinBox()
        sp.setRange(0, MC.MAX_COPIES)
        sp.setValue(int(value))
        sp.valueChanged.connect(self._refresh)
        return sp

    def _check(self, value: bool) -> QCheckBox:
        c = QCheckBox()
        c.setChecked(bool(value))
        c.toggled.connect(self._refresh)
        return c

    def _choice(self, pairs: list, value: str) -> QComboBox:
        c = QComboBox()
        for key, label in pairs:
            c.addItem(label, key)
        c.setCurrentIndex(max(c.findData(value), 0))
        c.currentIndexChanged.connect(self._refresh)
        return c

    def result_spec(self) -> MC.MultiSpec:
        return MC.MultiSpec(margin=self.margin.value(), gap_x=self.gap_x.value(), gap_y=self.gap_y.value(),
                            total=self.total.value(), planes=self.planes.value(), start=str(self.start.currentData()),
                            place=str(self.place.currentData()), from_selection=self.from_sel.isChecked(),
                            optimised=self.optimised.isChecked(), turn_back=self.turn_back.isChecked(),
                            quarter_turn=self.quarter.isChecked(), ignore_first=self.ignore.isChecked(),
                            keep_original=self.keep.isChecked(), limit_to_rows=self.limit.isChecked(),
                            cuts=str(self.cuts.currentData()), cut_tool=int(self.cut_tool.currentData() or 0),
                            tick=self.tick.value())

    def _refresh(self, *_a) -> None:
        if not hasattr(self, 'summary'):
            return
        spec = self.result_spec()
        self.turn_back.setEnabled(spec.optimised)
        self.place.setEnabled(not spec.from_selection)
        self.quarter.setEnabled(not spec.from_selection)
        self.tick.setEnabled(spec.cuts == 'partielle')
        self.cut_tool.setEnabled(spec.cuts != 'aucune')
        count = MC.wanted(spec, self.rows_count)
        lay = MC.layout(self.bb, self.box, spec, count)
        self.preview.show_layout(lay, spec)
        if lay.cells:
            self.summary.setText(tr('{0} exemplaire(s) : {1} × {2} par plan, {3} plan(s)').format(
                len(lay.cells), lay.cols, lay.rows, lay.plates))
        else:
            self.summary.setText(tr('Aucun exemplaire ne tient sur la plaque.'))
