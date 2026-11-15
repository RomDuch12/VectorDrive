"""Fenêtre du coupon d'essai laser (cam.coupon) : outil de départ, deux
axes (paramètre, de, à, nombre), réglages fixes, cases et étiquettes."""
from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                               QGroupBox, QHBoxLayout, QLabel, QSpinBox, QVBoxLayout)

from ..cam import coupon as CP
from ..cam import model
from ..i18n import tr

#: réglages fixes : (paramètre, libellé, décimales, mini, maxi)
FIXED = (('power', 'Puissance (%)', 1, 0.0, 100.0), ('frequency', 'Fréquence (kHz)', 1, 0.0, 4000.0),
         ('feed', 'Vitesse (mm/min)', 0, 1.0, 1e7), ('resolution', 'Pas du remplissage (mm)', 3, 0.001, 5.0),
         ('laser_passes', 'Passages', 0, 1, 100))


def _spin(decimals, lo, hi, v):
    if decimals == 0 and hi <= 1000:
        w = QSpinBox()
        w.setRange(int(lo), int(hi))
        w.setValue(int(v))
        return w
    w = QDoubleSpinBox()
    w.setDecimals(decimals)
    w.setRange(lo, hi)
    w.setValue(float(v))
    return w


class _Axis(QGroupBox):
    def __init__(self, title: str, field: str, lo: float, hi: float, count: int, allow_none: bool):
        super().__init__(tr(title))
        f = QFormLayout(self)
        self.field = QComboBox()
        if allow_none:
            self.field.addItem(tr('(aucun)'), '')
        for k, (lab, unit, _s, _q) in CP.AXES.items():
            self.field.addItem(tr(lab) + (f' ({unit})' if unit else ''), k)
        self.field.setCurrentIndex(max(0, self.field.findData(field)))
        self.lo, self.hi = QDoubleSpinBox(), QDoubleSpinBox()
        for w, v in ((self.lo, lo), (self.hi, hi)):
            w.setDecimals(3)
            w.setRange(0.0, 1e7)
            w.setValue(v)
        self.count = QSpinBox()
        self.count.setRange(1, 20)
        self.count.setValue(count)
        f.addRow(tr('Paramètre'), self.field)
        f.addRow(tr('De'), self.lo)
        f.addRow(tr('À'), self.hi)
        f.addRow(tr('Nombre de valeurs'), self.count)

    def key(self) -> str:
        return self.field.currentData() or ''

    def suggest(self, base: dict) -> None:
        """Bornes proposées pour le paramètre choisi : autour du réglage de
        départ, sinon celles de cam.coupon.FALLBACK."""
        k = self.key()
        if not k:
            return
        lo, hi = CP.FALLBACK.get(k, (0.0, 1.0))
        v = float(base.get(k) or 0.0)
        if v > 0 and k not in ('power', 'laser_passes'):
            lo, hi = v * 0.5, v * 1.5
        self.lo.setValue(lo)
        self.hi.setValue(hi)


class CouponDialog(QDialog):
    def __init__(self, parent, lasers: list, motif_ok: bool = False, font: str = 'Arial'):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        self.setWindowTitle(tr('Coupon d\'essai laser'))
        self.setSizeGripEnabled(True)
        self.lasers = list(lasers) or [model.CamTool(name='Laser', kind='laser', diameter=0.05, power=50.0,
                                                     frequency=20.0, feed=1000.0, spindle=0.0, cut_length=0.0)]
        self.font = font
        outer = QVBoxLayout(self)
        top = QFormLayout()
        self.tool = QComboBox()
        self.tool.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.tool.setMinimumContentsLength(40)
        for t in self.lasers:
            self.tool.addItem(f'{t.name} — {t.power:g} % · {t.frequency:g} kHz · {t.feed:g} mm/min', t.id)
        top.addRow(tr('Outil laser de départ'), self.tool)
        outer.addLayout(top)
        cols = QHBoxLayout()
        self.x = _Axis('Axe X (colonnes)', 'power', 20.0, 100.0, 5, False)
        self.y = _Axis('Axe Y (rangées)', 'feed', 1000.0, 4000.0, 4, True)
        cols.addWidget(self.x)
        cols.addWidget(self.y)
        fixed = QGroupBox(tr('Réglages fixes (hors des axes)'))
        ff = QFormLayout(fixed)
        self.fixed = {}
        for k, lab, dec, lo, hi in FIXED:
            w = _spin(dec, lo, hi, lo)
            ff.addRow(tr(lab), w)
            self.fixed[k] = w
        cols.addWidget(fixed)
        outer.addLayout(cols)
        opts = QGroupBox(tr('Cases et étiquettes'))
        of = QFormLayout(opts)
        self.cell, self.gap, self.label = (_spin(2, 1.0, 100.0, 8.0), _spin(2, 0.0, 50.0, 3.0),
                                           _spin(2, 0.3, 20.0, 1.8))
        of.addRow(tr('Côté d\'une case (mm)'), self.cell)
        of.addRow(tr('Écart entre les cases (mm)'), self.gap)
        of.addRow(tr('Hauteur des étiquettes (mm)'), self.label)
        self.filled = QCheckBox(tr('Cases remplies (sinon marquées sur le trait)'))
        self.filled.setChecked(True)
        self.labels_filled = QCheckBox(tr('Étiquettes remplies'))
        self.x_labels = QCheckBox(tr('Valeurs des colonnes'))
        self.y_labels = QCheckBox(tr('Valeurs des rangées'))
        self.title = QCheckBox(tr('Titre du coupon'))
        for w in (self.x_labels, self.y_labels, self.title):
            w.setChecked(True)
        self.motif = QCheckBox(tr('Le dessin sélectionné dans chaque case'))
        self.motif.setEnabled(motif_ok)
        self.motif.setToolTip(tr('Juger le rendu du dessin réel plutôt que celui d\'un carré plein'))
        for w in (self.filled, self.labels_filled, self.x_labels, self.y_labels, self.title, self.motif):
            of.addRow(w)
        outer.addWidget(opts)
        self.note = QLabel()
        self.note.setWordWrap(True)
        outer.addWidget(self.note)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        outer.addWidget(bb)
        self.tool.currentIndexChanged.connect(lambda _i: self._tool_changed())
        for axis in (self.x, self.y):
            axis.field.currentIndexChanged.connect(lambda _i, a=axis: self._axis_changed(a))
            for w in (axis.lo, axis.hi, axis.count):
                w.valueChanged.connect(lambda _v: self._update())
        self._tool_changed()
        hint = self.sizeHint()
        self.resize(min(hint.width(), 1000), hint.height())

    def base_tool(self) -> model.CamTool:
        return self.lasers[max(0, self.tool.currentIndex())]

    def _base(self) -> dict:
        t = self.base_tool()
        return {'power': t.power, 'frequency': t.frequency, 'feed': t.feed, 'resolution': 0.05, 'laser_passes': 1}

    def _tool_changed(self) -> None:
        for k, v in self._base().items():
            self.fixed[k].setValue(v)
        self._update()

    def _axis_changed(self, axis: _Axis) -> None:
        axis.suggest(self._base())
        self._update()

    def spec(self) -> CP.Spec:
        return CP.Spec(x_field=self.x.key(), x_from=self.x.lo.value(), x_to=self.x.hi.value(),
                       x_count=self.x.count.value(), y_field=self.y.key(), y_from=self.y.lo.value(),
                       y_to=self.y.hi.value(), y_count=self.y.count.value(), cell=self.cell.value(),
                       gap=self.gap.value(), label_size=self.label.value(), filled=self.filled.isChecked(),
                       labels_filled=self.labels_filled.isChecked(), x_labels=self.x_labels.isChecked(),
                       y_labels=self.y_labels.isChecked(), title=self.title.isChecked(), font=self.font,
                       fixed={k: w.value() for k, w in self.fixed.items()})

    def use_motif(self) -> bool:
        return self.motif.isEnabled() and self.motif.isChecked()

    def _update(self) -> None:
        same = bool(self.x.key()) and self.x.key() == self.y.key()
        for k, w in self.fixed.items():
            w.setEnabled(k not in (self.x.key(), self.y.key()))
        s = self.spec()
        nx = len(CP.steps(s.x_from, s.x_to, s.x_count, s.x_field)) if s.x_field else 1
        ny = len(CP.steps(s.y_from, s.y_to, s.y_count, s.y_field)) if s.y_field else 1
        pitch = s.cell + s.gap
        text = tr('{0} cases ({1} × {2}), environ {3:.0f} × {4:.0f} mm ; une opération par case, plus les '
                  'étiquettes.').format(nx * ny, nx, ny, nx * pitch, ny * pitch)
        if same:
            text = tr('Les deux axes portent le même paramètre : choisir un autre paramètre en Y.')
        self.note.setText(text)
        ok = self.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok) \
            if self.findChild(QDialogButtonBox) else None
        if ok is not None:
            ok.setEnabled(not same)
