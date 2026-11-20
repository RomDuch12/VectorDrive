"""Rechercher / remplacer : le texte, la taille, la police, la compression, sur la sélection, le plan actif ou tous les plans."""
from __future__ import annotations

from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QRadioButton, QVBoxLayout)

from ..core import textops as TO
from ..i18n import tr
from .dialogs import FontBox


class FindReplaceDialog(QDialog):
    def __init__(self, parent, texts_of, has_selection: bool, last_find: str = ''):
        """`texts_of(portée)` : les textes de 'selection', 'layer' ou 'all'."""
        super().__init__(parent)
        from .fit import release
        release(self)                                    # fermée : détruite, pas gardée par son parent
        self.setWindowTitle(tr('Rechercher / remplacer'))
        self.texts_of = texts_of
        col = QVBoxLayout(self)

        scope = QGroupBox(tr('Appliquer sur'))
        row = QHBoxLayout(scope)
        self.scopes = {'selection': QRadioButton(tr('Sélection')), 'layer': QRadioButton(tr('Plan actif')),
                       'all': QRadioButton(tr('Tous les plans'))}
        group = QButtonGroup(self)
        for w in self.scopes.values():
            group.addButton(w)
            row.addWidget(w)
            w.toggled.connect(self._refresh_lists)
        self.scopes['selection'].setEnabled(has_selection)
        col.addWidget(scope)

        self.text_box = QGroupBox(tr('Rechercher et remplacer du texte'))
        self.text_box.setCheckable(True)
        self.text_box.setChecked(True)
        form = QFormLayout(self.text_box)
        self.find = QLineEdit(last_find)
        self.repl = QLineEdit()
        self.case = QCheckBox(tr('Respecter la casse'))
        self.whole = QCheckBox(tr('Mots entiers'))
        form.addRow(tr('Rechercher'), self.find)
        form.addRow(tr('Remplacer par'), self.repl)
        form.addRow(self.case)
        form.addRow(self.whole)
        col.addWidget(self.text_box)

        self.size_box = QGroupBox(tr('Rechercher et remplacer la taille du texte'))
        self.size_box.setCheckable(True)
        self.size_box.setChecked(False)
        form = QFormLayout(self.size_box)
        self.old_size = QComboBox()
        self.new_size = QDoubleSpinBox()
        self.new_size.setRange(0.001, 100000.0)
        self.new_size.setDecimals(3)
        self.new_size.setValue(10.0)
        self.all_sizes = QCheckBox(tr('Remplacer toutes les tailles de texte'))
        self.all_sizes.toggled.connect(lambda on: self.old_size.setEnabled(not on))
        form.addRow(tr('Ancienne taille de texte (mm)'), self.old_size)
        form.addRow(tr('Nouvelle taille de texte (mm)'), self.new_size)
        form.addRow(self.all_sizes)
        col.addWidget(self.size_box)

        self.font_box = QGroupBox(tr('Rechercher et remplacer une police'))
        self.font_box.setCheckable(True)
        self.font_box.setChecked(False)
        form = QFormLayout(self.font_box)
        self.old_font = QComboBox()
        self.new_font = FontBox()
        self.all_fonts = QCheckBox(tr('Remplacer toutes les polices'))
        self.all_fonts.toggled.connect(lambda on: self.old_font.setEnabled(not on))
        form.addRow(tr('Police à rechercher'), self.old_font)
        form.addRow(tr('Remplacer par la police'), self.new_font)
        form.addRow(self.all_fonts)
        col.addWidget(self.font_box)

        self.comp_box = QGroupBox(tr('Compression identique'))
        self.comp_box.setCheckable(True)
        self.comp_box.setChecked(False)
        row = QHBoxLayout(self.comp_box)
        self.ratio = QDoubleSpinBox()
        self.ratio.setRange(1.0, 1000.0)
        self.ratio.setDecimals(1)
        self.ratio.setSuffix(' %')
        self.ratio.setValue(100.0)
        strongest = QPushButton(tr('La plus forte'))
        strongest.setToolTip(tr('Reprend la plus forte compression trouvée parmi ces textes'))
        strongest.clicked.connect(self._strongest)
        row.addWidget(QLabel(tr('Largeur des caractères')))
        row.addWidget(self.ratio)
        row.addWidget(strongest)
        row.addStretch(1)
        col.addWidget(self.comp_box)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        col.addWidget(buttons)
        self.scopes['selection' if has_selection else 'all'].setChecked(True)
        self._refresh_lists()

    def scope(self) -> str:
        return next((k for k, w in self.scopes.items() if w.isChecked()), 'all')

    def _refresh_lists(self, *_a) -> None:
        """Les tailles et les polices trouvées dans la portée, dans leur ordre : la première trouvée est proposée."""
        if not hasattr(self, 'ratio'):
            return
        texts = self.texts_of(self.scope())
        self.old_size.clear()
        for v in TO.sizes_of(texts):
            self.old_size.addItem(f'{v:.3f}', v)
        self.old_font.clear()
        fonts = TO.fonts_of(texts)
        self.old_font.addItems(fonts)
        if fonts:
            self.new_font.setCurrentFont(fonts[0])

    def _strongest(self) -> None:
        got = [t.width_ratio for t in self.texts_of(self.scope())]
        if got:
            self.ratio.setValue(min(got) * 100.0)

    def values(self) -> dict:
        return {'scope': self.scope(), 'text': self.text_box.isChecked(), 'find': self.find.text(), 'repl': self.repl.text(),
                'case': self.case.isChecked(), 'whole': self.whole.isChecked(),
                'size': self.size_box.isChecked(), 'old_size': self.old_size.currentData(), 'new_size': self.new_size.value(),
                'all_sizes': self.all_sizes.isChecked(),
                'font': self.font_box.isChecked(), 'old_font': self.old_font.currentText(),
                'new_font': self.new_font.currentText(), 'all_fonts': self.all_fonts.isChecked(),
                'comp': self.comp_box.isChecked(), 'ratio': self.ratio.value()}
