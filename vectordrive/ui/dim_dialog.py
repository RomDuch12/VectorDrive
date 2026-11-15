"""Options de cotation : d'une cote posée (double-clic, aperçu en direct)
ou de l'outil Cote (clic droit sur son bouton : les prochaines cotes)."""
from __future__ import annotations

import copy
import json
from dataclasses import fields

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QGroupBox,
                               QLineEdit, QSpinBox, QVBoxLayout)

from ..core import dims as D
from ..i18n import tr

LABELS = {
    'start': 'Symbole au départ', 'end': 'Symbole à l\'arrivée', 'symbol': 'Taille des symboles (mm)',
    'line': 'Ligne de cote', 'outside': 'Longueur à l\'extérieur (mm)', 'ext_lines': 'Lignes d\'attache',
    'ext_beyond': 'Débord au-delà de la ligne de cote (mm)', 'ext_gap': 'Écart à l\'objet coté (mm)',
    'font': 'Police', 'text_height': 'Hauteur du texte (mm)', 'text_offset': 'Écart du texte à la ligne (0 : dans la ligne)',
    'orientation': 'Orientation du texte', 'prefix': 'Préfixe', 'suffix': 'Suffixe', 'unit': 'Unité affichée',
    'decimals': 'Décimales', 'diameter': 'Cote radiale : le diamètre (Ø)',
    'inspect': 'Cote d\'inspection', 'inspect_label': 'Libellé (à gauche de la valeur)',
    'inspect_rate': 'Taux d\'inspection (à droite, ex. 100%)',
}
CHOICES = {'start': D.SYMBOLS, 'end': D.SYMBOLS, 'line': D.LINES, 'orientation': D.ORIENT, 'unit': D.UNITS,
           'inspect': D.INSPECT}
GROUPS = (('Géométrie', ('start', 'end', 'symbol', 'line', 'outside', 'ext_lines', 'ext_beyond', 'ext_gap', 'diameter')),
          ('Texte', ('font', 'text_height', 'text_offset', 'orientation', 'prefix', 'suffix', 'unit', 'decimals')),
          ('Inspection', ('inspect', 'inspect_label', 'inspect_rate')))
#: propres à une cote : ni dans les options des prochaines cotes, ni gardés pour elles
OWN = ('inspect', 'inspect_label', 'inspect_rate')


def default_style(settings, text_height: float | None = None) -> D.DimStyle:
    raw = settings.value('cotes/style', '') if settings is not None else ''
    try:
        d = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        d = {}
    st = D.style_from_dict(d)
    if 'text_height' not in d and text_height:
        st.text_height = float(text_height)
    return st


def save_style(settings, st: D.DimStyle) -> None:
    if settings is not None:
        settings.setValue('cotes/style', json.dumps({k: v for k, v in D.asdict(st).items() if k not in OWN}))


class DimDialog(QDialog):
    def __init__(self, parent, style: D.DimStyle, *, dim: D.Dim | None = None, on_change=None):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)
        self.setWindowTitle(tr('Options de cotation') if dim is None else tr(D.KINDS.get(dim.kind, 'Cote')))
        self.dim = copy.deepcopy(dim)
        self.style0 = copy.deepcopy(style)
        self.on_change = on_change
        lay = QVBoxLayout(self)
        self.widgets = {}
        if dim is not None:
            g = QGroupBox(tr('Cote'))
            f = QFormLayout(g)
            if dim.kind in ('libre', 'horizontale', 'verticale'):
                k = QComboBox()
                for key in ('libre', 'horizontale', 'verticale'):
                    k.addItem(tr(D.KINDS[key]), key)
                k.setCurrentIndex(max(0, k.findData(dim.kind)))
                k.currentIndexChanged.connect(lambda _i: self._changed())
                f.addRow(tr('Type'), k)
                self.widgets['kind'] = k
            o = QDoubleSpinBox()
            o.setRange(-1e5, 1e5)
            o.setDecimals(3)
            o.setValue(dim.offset)
            o.valueChanged.connect(lambda _v: self._changed())
            f.addRow(tr('Rayon de l\'arc (mm)') if dim.kind in ('angulaire', 'arc') else
                     tr('Débord de la ligne (mm)') if dim.kind == 'radiale' else tr('Position de la ligne de cote (mm)'), o)
            self.widgets['offset'] = o
            lay.addWidget(g)
        for title, names in GROUPS:
            if title == 'Inspection' and (dim is None or dim.kind not in D.INSPECTED):
                continue
            g = QGroupBox(tr(title))
            f = QFormLayout(g)
            for name in names:
                v = getattr(style, name)
                if name in CHOICES:
                    w = QComboBox()
                    for key, text in CHOICES[name].items():
                        w.addItem(tr(text), key)
                    w.setCurrentIndex(max(0, w.findData(v)))
                    w.currentIndexChanged.connect(lambda _i: self._changed())
                elif name == 'font':
                    from PySide6.QtWidgets import QFontComboBox
                    from PySide6.QtGui import QFont
                    w = QFontComboBox()
                    w.setCurrentFont(QFont(v))
                    w.currentFontChanged.connect(lambda _f: self._changed())
                elif isinstance(v, bool):
                    w = QCheckBox()
                    w.setChecked(v)
                    w.toggled.connect(lambda _b: self._changed())
                elif isinstance(v, int):
                    w = QSpinBox()
                    w.setRange(0, 6)
                    w.setValue(v)
                    w.valueChanged.connect(lambda _v: self._changed())
                elif isinstance(v, float):
                    w = QDoubleSpinBox()
                    w.setRange(0.0, 1000.0)
                    w.setDecimals(3)
                    w.setValue(v)
                    w.valueChanged.connect(lambda _v: self._changed())
                else:
                    w = QLineEdit(str(v))
                    w.textChanged.connect(lambda _t: self._changed())
                f.addRow(tr(LABELS[name]), w)
                self.widgets[name] = w
            lay.addWidget(g)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._sync()

    def style(self) -> D.DimStyle:
        st = copy.deepcopy(self.style0)
        for f in fields(D.DimStyle):
            w = self.widgets.get(f.name)
            if w is None:
                continue
            if isinstance(w, QComboBox) and f.name != 'font':
                setattr(st, f.name, w.currentData())
            elif f.name == 'font':
                setattr(st, f.name, w.currentFont().family())
            elif isinstance(w, QCheckBox):
                setattr(st, f.name, w.isChecked())
            elif isinstance(w, QLineEdit):
                setattr(st, f.name, w.text())
            else:
                setattr(st, f.name, type(getattr(st, f.name))(w.value()))
        return st

    def value(self) -> D.Dim | None:
        if self.dim is None:
            return None
        d = copy.deepcopy(self.dim)
        d.style = self.style()
        if 'kind' in self.widgets:
            d.kind = self.widgets['kind'].currentData()
        d.offset = self.widgets['offset'].value()
        return d

    def set_field(self, name: str, v) -> None:
        w = self.widgets[name]
        if isinstance(w, QComboBox) and name != 'font':
            w.setCurrentIndex(max(0, w.findData(v)))
        elif isinstance(w, QCheckBox):
            w.setChecked(bool(v))
        elif isinstance(w, QLineEdit):
            w.setText(str(v))
        else:
            w.setValue(v)

    def _sync(self) -> None:
        st = self.style()
        if 'outside' in self.widgets:
            self.widgets['outside'].setEnabled(st.line == 'exterieure')
        for n in ('ext_beyond', 'ext_gap'):
            self.widgets[n].setEnabled(st.ext_lines)
        for n in ('inspect_label', 'inspect_rate'):
            if n in self.widgets:
                self.widgets[n].setEnabled(bool(st.inspect))

    def _changed(self) -> None:
        self._sync()
        if self.on_change is not None and self.dim is not None:
            try:
                self.on_change(self.value())
            except (ValueError, ZeroDivisionError):
                pass
