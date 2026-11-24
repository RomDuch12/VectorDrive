"""Paramètres de construction d'une forme (core.forms) : création
numérique (F2 avec l'outil), modification d'une forme posée (double-clic,
F2, clic droit sur le bouton de l'outil), ou réglages par défaut de l'outil
(clic droit sur son bouton, rien de sélectionné). L'aperçu suit chaque
changement ; Annuler remet tout comme avant."""
from __future__ import annotations

import copy
import json

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel,
                               QSpinBox)

from ..core import forms as F
from ..i18n import tr

#: action d'outil → type de forme
TOOL_KINDS = {'tool_rect': 'rect', 'tool_circle': 'circle', 'tool_ellipse': 'ellipse', 'tool_polygon': 'polygon', 'tool_star': 'star',
              'tool_spiral': 'spiral', 'arrow': 'arrow', 'chord_arc': 'chord_arc', 'tool_marker': 'marker',
              'form_slot': 'slot', 'form_ring': 'ring', 'form_sector': 'sector', 'form_gear': 'gear'}
#: champs de placement (pas dans les réglages par défaut d'un outil)
PLACEMENT = ('cx', 'cy', 'x', 'y', 'x0', 'y0', 'x1', 'y1')


def defaults(settings, kind: str):
    """Réglages par défaut de l'outil (ceux de la dernière forme réglée)."""
    spec = F.TYPES[kind]()
    raw = settings.value(f'formes/{kind}', '') if settings is not None else ''
    try:
        d = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        d = {}
    got = F.from_dict({**F.to_dict(spec), **{k: v for k, v in d.items() if k not in PLACEMENT}})
    return got or spec


def save_defaults(settings, spec) -> None:
    if settings is None:
        return
    d = {k: v for k, v in F.to_dict(spec).items() if k not in PLACEMENT}
    settings.setValue(f'formes/{spec.kind}', json.dumps(d))


class FormDialog(QDialog):
    def __init__(self, parent, spec, *, title: str = '', on_change=None, placement: bool = True):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)
        self.spec = copy.deepcopy(spec)
        self.on_change = on_change
        self.setWindowTitle(title or tr(F.TITLES.get(spec.kind, spec.kind)))
        form = QFormLayout(self)
        if not placement:
            note = QLabel(tr('Réglages des prochaines formes de cet outil'))
            note.setStyleSheet('color: #868e96;')
            form.addRow(note)
        self.widgets = {}
        for name in F.field_names(spec):
            if not placement and name in PLACEMENT:
                continue
            label, lo, hi = F.LABELS.get(name, (name, None, None))
            v = getattr(spec, name)
            if name in F.CHOICES:
                w = QComboBox()
                for value, text in F.CHOICES[name]:
                    w.addItem(tr(text), value)
                w.setCurrentIndex(max(0, w.findData(v)))
                w.currentIndexChanged.connect(lambda _i: self._changed())
            elif isinstance(v, bool):
                w = QCheckBox()
                w.setChecked(v)
                w.toggled.connect(lambda _b: self._changed())
            elif isinstance(v, int):
                w = QSpinBox()
                w.setRange(int(lo if lo is not None else -10**6), int(hi if hi is not None else 10**6))
                w.setValue(int(v))
                w.valueChanged.connect(lambda _v: self._changed())
            else:
                w = QDoubleSpinBox()
                w.setDecimals(3 if name not in ('notch',) else 2)
                w.setRange(float(lo if lo is not None else -1e6), float(hi if hi is not None else 1e6))
                w.setSingleStep(0.05 if name == 'notch' else 1.0)
                w.setValue(float(v))
                w.valueChanged.connect(lambda _v: self._changed())
            form.addRow(tr(label), w)
            self.widgets[name] = w
        self._sync_enabled()
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def value(self):
        """Forme d'après le formulaire."""
        s = copy.deepcopy(self.spec)
        for name, w in self.widgets.items():
            if isinstance(w, QComboBox):
                setattr(s, name, w.currentData())
            elif isinstance(w, QCheckBox):
                setattr(s, name, w.isChecked())
            else:
                setattr(s, name, type(getattr(s, name))(w.value()))
        return s

    def set_field(self, name: str, v) -> None:
        w = self.widgets[name]
        if isinstance(w, QComboBox):
            w.setCurrentIndex(max(0, w.findData(v)))
        elif isinstance(w, QCheckBox):
            w.setChecked(bool(v))
        else:
            w.setValue(v)

    def _sync_enabled(self) -> None:
        """Champs sans effet grisés (rayon des coins droits, pointe d'une
        flèche orthogonale…)."""
        s = self.value()
        rules = {'radius': getattr(s, 'corner', '') != 'droit',
                 'head_length': getattr(s, 'style', '') != 'orthogonale',
                 'notch': getattr(s, 'style', '') == 'standard',
                 'shaft_width': getattr(s, 'style', '') != 'filaire'}
        for name, on in rules.items():
            if name in self.widgets:
                self.widgets[name].setEnabled(on)

    def _changed(self) -> None:
        self._sync_enabled()
        if self.on_change is not None:
            try:
                self.on_change(self.value())
            except (ValueError, ZeroDivisionError):
                pass
