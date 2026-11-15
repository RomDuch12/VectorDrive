"""Texte dans une forme : le texte, la police, la taille ou le remplissage automatique."""
from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QFormLayout, QPlainTextEdit

from ..core.textflow import FlowSpec
from ..i18n import tr
from .dialogs import FontBox, _buttons, _spin


class TextFlowDialog(QDialog):
    def __init__(self, parent=None, *, text: str = '', font: str = 'Arial', spec: FlowSpec | None = None,
                 gap: float | None = None):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)
        spec = spec or FlowSpec()
        self.setWindowTitle(tr('Texte dans une forme'))
        form = QFormLayout(self)
        self.text = QPlainTextEdit(text)
        self.text.setMinimumHeight(110)
        self.font_box = FontBox()
        self.font_box.setCurrentFont(QFont(font))
        self.fit = QCheckBox(tr('La plus grande taille qui fait tout tenir'))
        self.fit.setChecked(spec.fit)
        self.size = _spin(spec.size, 0.2, 1000.0)
        self.size.setEnabled(not spec.fit)
        self.fit.toggled.connect(lambda on: self.size.setEnabled(not on))
        self.align = QComboBox()
        for k, label in (('left', tr('Gauche')), ('center', tr('Centré')), ('right', tr('Droite')),
                         ('justify', tr('Justifié'))):
            self.align.addItem(label, k)
        self.align.setCurrentIndex(max(0, self.align.findData(spec.align)))
        self.line = _spin(spec.line_spacing, 0.5, 5, suffix=tr(' × corps'), decimals=2)
        self.margin = _spin(spec.margin, 0.0, 1000.0)
        self.middle = QCheckBox(tr('Centrer le bloc dans la hauteur de la forme'))
        self.middle.setChecked(spec.middle)
        form.addRow(tr('Texte'), self.text)
        form.addRow(tr('Police'), self.font_box)
        form.addRow(self.fit)
        form.addRow(tr('Hauteur des capitales'), self.size)
        form.addRow(tr('Alignement'), self.align)
        form.addRow(tr('Interligne'), self.line)
        form.addRow(tr('Marge au bord de la forme'), self.margin)
        form.addRow(self.middle)
        self.gap = None
        if gap is not None:                              # d'autres formes à contourner
            self.gap = _spin(gap, 0.0, 1000.0)
            self.gap.setToolTip(tr('Le texte passe à cette distance des autres formes sélectionnées'))
            form.addRow(tr('Écart autour des autres formes'), self.gap)
        _buttons(self, form)
        self.text.setFocus()

    def values(self) -> dict:
        out = {'text': self.text.toPlainText(), 'font': self.font_box.currentFont().family(),
               'size': self.size.value(), 'fit': self.fit.isChecked(), 'align': self.align.currentData(),
               'line_spacing': self.line.value(), 'margin': self.margin.value(), 'middle': self.middle.isChecked()}
        if self.gap is not None:
            out['gap'] = self.gap.value()
        return out
