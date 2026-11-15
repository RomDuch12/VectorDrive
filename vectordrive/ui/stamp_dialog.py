"""Réglages d'un tampon : le format du support (tout prêt ou enregistré), le dessin dedans, la découpe."""
from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QGroupBox,
                               QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout)

from ..core import stamp as SP
from ..i18n import tr


def _number(value: float, lo: float = 0.0, hi: float = 10000.0) -> QDoubleSpinBox:
    sp = QDoubleSpinBox()
    sp.setDecimals(3)
    sp.setRange(lo, hi)
    sp.setValue(value)
    return sp


class StampDialog(QDialog):
    def __init__(self, parent, spec: SP.StampSpec, saved: list | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr('Tampon'))
        self.spec = spec
        self.saved = [tuple(f) for f in (saved or [])]
        col = QVBoxLayout(self)

        box = QGroupBox(tr('Support'))
        form = QFormLayout(box)
        self.kind = QComboBox()
        for key, label in (('auto', tr('Autour des objets')), ('rect', tr('Rectangle')), ('cercle', tr('Cercle')),
                           ('ellipse', tr('Ellipse'))):
            self.kind.addItem(label, key)
        self.kind.setCurrentIndex(max(0, self.kind.findData(spec.support)))
        self.format = QComboBox()
        self.width = _number(spec.width, SP.MIN_SUPPORT)
        self.height = _number(spec.height, SP.MIN_SUPPORT)
        self.fit = QCheckBox()
        self.fit.setChecked(spec.fit)
        row = QHBoxLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText(tr('Nom de ce format'))
        self.save = QPushButton(tr('Enregistrer ce format'))
        row.addWidget(self.name, 1)
        row.addWidget(self.save)
        form.addRow(tr('Forme'), self.kind)
        form.addRow(tr('Format'), self.format)
        form.addRow(tr('Largeur (mm)'), self.width)
        form.addRow(tr('Hauteur (mm)'), self.height)
        form.addRow(tr('Ajuster le dessin au support'), self.fit)
        form.addRow(row)
        col.addWidget(box)

        box = QGroupBox(tr('Gravure'))
        form = QFormLayout(box)
        self.margin = _number(spec.margin)
        self.radius = _number(spec.radius)
        self.border = _number(spec.border)
        self.shoulder = _number(spec.shoulder)
        self.mirror = QCheckBox()
        self.mirror.setChecked(spec.mirror)
        self.negative = QCheckBox()
        self.negative.setChecked(spec.negative)
        self.hatch = _number(spec.hatch)
        form.addRow(tr('Marge autour des objets (mm)'), self.margin)
        form.addRow(tr('Rayon des coins (mm)'), self.radius)
        form.addRow(tr('Bordure en relief (mm, 0 = aucune)'), self.border)
        form.addRow(tr('Épaulement des objets (mm)'), self.shoulder)
        form.addRow(tr('Miroir (le tampon imprime à l\'envers)'), self.mirror)
        form.addRow(tr('Négatif (graver le fond)'), self.negative)
        form.addRow(tr('Hachures du fond, pas (mm, 0 = aucune)'), self.hatch)
        col.addWidget(box)

        box = QGroupBox(tr('Découpe'))
        form = QFormLayout(box)
        self.cut = QComboBox()
        for key, label in (('support', tr('Le support')), ('optimise', tr('Optimisée : autour de la forme des objets')),
                           ('rectangle', tr('Rectangle autour des objets')), ('boites', tr('Boîtes fusionnées : par objet et par ligne'))):
            self.cut.addItem(label, key)
        self.cut.setCurrentIndex(max(0, self.cut.findData(spec.cut)))
        self.cut_offset = _number(spec.cut_offset, -10000.0)
        form.addRow(tr('Forme de la découpe'), self.cut)
        form.addRow(tr('Décalage de la découpe (mm)'), self.cut_offset)
        col.addWidget(box)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        col.addWidget(bb)

        self._fill_formats()
        self.format.activated.connect(self._format_chosen)
        self.kind.currentIndexChanged.connect(self._sync)
        self.width.valueChanged.connect(self._width_changed)
        self.save.clicked.connect(self.save_format)
        self._sync()

    def _fill_formats(self) -> None:
        self.format.clear()
        self.format.addItem(tr('Sur mesure'), None)
        for f in list(SP.SUPPORTS) + self.saved:
            self.format.addItem(f[0], f)

    def _format_chosen(self, index: int) -> None:
        f = self.format.itemData(index)
        if not f:
            return
        self.kind.setCurrentIndex(max(0, self.kind.findData(f[1])))
        self.width.setValue(float(f[2]))
        self.height.setValue(float(f[3]))

    def _width_changed(self, value: float) -> None:
        if self.kind.currentData() == 'cercle':
            self.height.setValue(value)

    def _sync(self, *_a) -> None:
        kind = self.kind.currentData()
        on = kind != 'auto'
        for w in (self.format, self.width, self.fit, self.name, self.save):
            w.setEnabled(on)
        self.height.setEnabled(on and kind != 'cercle')
        self.radius.setEnabled(kind in ('auto', 'rect'))
        if kind == 'cercle':
            self.height.setValue(self.width.value())

    def save_format(self) -> bool:
        """Ajoute ce format aux formats enregistrés, ou remplace celui du même nom."""
        name = self.name.text().strip()
        kind = self.kind.currentData()
        if not name or kind == 'auto':
            return False
        f = (name, kind, self.width.value(), self.height.value())
        self.saved = [s for s in self.saved if s[0] != name] + [f]
        self._fill_formats()
        self.format.setCurrentIndex(self.format.findText(name))
        return True

    def result_params(self) -> SP.StampSpec:
        kind = str(self.kind.currentData())
        width = self.width.value()
        return replace(self.spec, support=kind, width=width, height=width if kind == 'cercle' else self.height.value(),
                       fit=self.fit.isChecked(), margin=self.margin.value(), radius=self.radius.value(),
                       border=self.border.value(), shoulder=self.shoulder.value(), mirror=self.mirror.isChecked(),
                       negative=self.negative.isChecked(), hatch=self.hatch.value(), cut=str(self.cut.currentData()),
                       cut_offset=self.cut_offset.value())
