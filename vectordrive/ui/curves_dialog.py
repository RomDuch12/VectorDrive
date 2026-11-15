"""Courbe par équation et guilloché : réglages et aperçu."""
from __future__ import annotations

from dataclasses import asdict, fields

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel, QLineEdit,
                               QSpinBox, QVBoxLayout, QWidget)

from ..core import equation as EQ
from ..core.geom import Path
from ..i18n import tr

#: pause de la frappe avant de refaire l'aperçu (ms) ; écart admis de l'aperçu, plus rapide que le tracé définitif (mm)
REFRESH_MS = 150
PREVIEW_TOL = 0.05


class CurvePreview(QWidget):
    """Le tracé, cadré dans le widget ; un message s'il n'y a rien à montrer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 240)
        self.path: Path | None = None

    def set_path(self, path: Path | None) -> None:
        self.path = path
        self.update()

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor('white'))
        bb = self.path.bbox() if self.path else None
        if not bb:
            p.end()
            return
        w, h = max(bb[2] - bb[0], 1e-6), max(bb[3] - bb[1], 1e-6)
        s = min((self.width() - 16) / w, (self.height() - 16) / h)
        ox = (self.width() - w * s) / 2 - bb[0] * s
        oy = (self.height() + h * s) / 2 + bb[1] * s
        q = QPainterPath()
        for c in self.path.contours:
            if not c.segments:
                continue
            a = c.segments[0].start
            q.moveTo(QPointF(ox + a[0] * s, oy - a[1] * s))
            for seg in c.segments:
                for x, y in seg.flatten(0.5 / s):
                    q.lineTo(QPointF(ox + x * s, oy - y * s))
            if c.closed:
                q.closeSubpath()
        p.setPen(QPen(QColor('#1f3a5f'), 1.0))
        p.drawPath(q)
        p.end()


class _CurveDialog(QDialog):
    """Ce que les deux fenêtres partagent : aperçu, message d'erreur, OK seulement sur une courbe valable."""

    def __init__(self, parent, title: str):
        super().__init__(parent)
        self.setWindowTitle(tr(title))
        self.result: Path | None = None
        self.layout_v = QVBoxLayout(self)
        self.form = QFormLayout()
        self.layout_v.addLayout(self.form)
        self.preview = CurvePreview()
        self.layout_v.addWidget(self.preview, 1)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.layout_v.addWidget(self.message)
        self.box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.box.accepted.connect(self.accept)
        self.box.rejected.connect(self.reject)
        self.layout_v.addWidget(self.box)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(REFRESH_MS)
        self._timer.timeout.connect(self.refresh)

    def later(self, *_a) -> None:
        self._timer.start()

    def compute(self, fine: bool) -> Path:
        """Le tracé ; `fine` : le définitif, ajusté en courbes. Sinon l'aperçu, en petits traits droits."""
        raise NotImplementedError

    def refresh(self) -> None:
        self._timer.stop()
        try:
            path = self.compute(False)
            error = '' if path.contours else tr('Aucun point valable sur cet intervalle.')
        except ValueError as ex:
            path, error = None, str(ex)
        self.result = path if path and path.contours else None
        self.preview.set_path(self.result)
        if error:
            self.message.setText(error)
        else:
            bb = path.bbox()
            self.message.setText(tr('{0} × {1} mm, {2} trait(s)').format(
                f'{bb[2] - bb[0]:.1f}', f'{bb[3] - bb[1]:.1f}', len(path.contours)))
        self.box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(self.result is not None)

    def accept(self) -> None:
        self.refresh()
        if self.result is None:
            return
        self.result = self.compute(True)
        super().accept()


class EquationDialog(_CurveDialog):
    KINDS = (('xy', 'x(t) et y(t)'), ('y', 'y = f(x)'), ('polar', 'Polaire : r = f(a)'))

    def __init__(self, parent=None, last: dict | None = None):
        super().__init__(parent, 'Courbe par équation')
        self.preset = QComboBox()
        self.preset.addItem(tr('Libre'), None)
        for row in EQ.PRESETS:
            self.preset.addItem(tr(row[0]), row)
        self.kind = QComboBox()
        for key, label in self.KINDS:
            self.kind.addItem(tr(label), key)
        self.first, self.second = QLineEdit(), QLineEdit()
        self.start, self.end = QLineEdit('0'), QLineEdit('2*pi')
        self.first_label, self.second_label = QLabel(), QLabel()
        self.form.addRow(tr('Courbe toute prête'), self.preset)
        self.form.addRow(tr('Genre'), self.kind)
        self.form.addRow(self.first_label, self.first)
        self.form.addRow(self.second_label, self.second)
        self.form.addRow(tr('De'), self.start)
        self.form.addRow(tr('À'), self.end)
        self.layout_v.insertWidget(1, QLabel(tr('En mm, angles en radians. sin cos tan asin acos atan sqrt abs exp log min max, '
                                                'pi, ^ pour la puissance. rad(90) : degrés en radians.')))
        self.preset.currentIndexChanged.connect(self._use_preset)
        self.kind.currentIndexChanged.connect(self._kind_changed)
        for e in (self.first, self.second, self.start, self.end):
            e.textChanged.connect(self.later)
        last = last if isinstance(last, dict) else {}
        if last.get('first'):
            self.set_values(last)
        else:
            self.preset.setCurrentIndex(1)
        self._kind_changed()
        self.refresh()

    def set_values(self, v: dict) -> None:
        self.kind.setCurrentIndex(max(0, self.kind.findData(v.get('kind', 'xy'))))
        self.first.setText(str(v.get('first', '')))
        self.second.setText(str(v.get('second', '')))
        self.start.setText(str(v.get('start', '0')))
        self.end.setText(str(v.get('end', '2*pi')))

    def values(self) -> dict:
        return {'kind': self.kind.currentData(), 'first': self.first.text(), 'second': self.second.text(),
                'start': self.start.text(), 'end': self.end.text()}

    def _use_preset(self, _i) -> None:
        row = self.preset.currentData()
        if row:
            _name, kind, first, second, start, end = row
            self.set_values({'kind': kind, 'first': first, 'second': second, 'start': start, 'end': end})
            self.refresh()

    def _kind_changed(self, *_a) -> None:
        kind = self.kind.currentData()
        self.first_label.setText({'xy': 'x(t) =', 'y': 'y(x) =', 'polar': 'r(a) ='}[kind])
        self.second_label.setText('y(t) =')
        self.second.setVisible(kind == 'xy')
        self.second_label.setVisible(kind == 'xy')
        self.later()

    def compute(self, fine: bool) -> Path:
        v = self.values()
        return EQ.equation_path(v['kind'], v['first'], v['second'], v['start'], v['end'], EQ.TOL if fine else PREVIEW_TOL, fine)


class GuillocheDialog(_CurveDialog):
    KINDS = (('rosette', 'Rosette'), ('band', 'Bande'), ('spiro', 'Spirographe'))
    #: champ, libellé, mini, maxi, motifs où il compte
    FIELDS = (('lines', 'Traits', 1, EQ.MAX_LINES, 'rosette band spiro'),
              ('radius', 'Rayon (mm)', 0.1, 5000.0, 'rosette'),
              ('length', 'Longueur (mm)', 0.1, 5000.0, 'band'),
              ('amplitude', 'Hauteur de la vague (mm)', 0.0, 5000.0, 'rosette band'),
              ('lobes', 'Vagues sur un tour', 1, EQ.MAX_LOBES, 'rosette'),
              ('wavelength', 'Longueur d\'une vague (mm)', 0.1, 5000.0, 'band'),
              ('amplitude2', 'Seconde vague : hauteur (mm)', 0.0, 5000.0, 'rosette band'),
              ('lobes2', 'Seconde vague : nombre sur un tour', 0, EQ.MAX_LOBES, 'rosette'),
              ('wavelength2', 'Seconde vague : longueur (mm)', 0.0, 5000.0, 'band'),
              ('big', 'Cercle fixe : rayon (mm)', 0.1, 5000.0, 'spiro'),
              ('small', 'Cercle qui roule : rayon (mm)', 0.1, 5000.0, 'spiro'),
              ('pen', 'Stylo : distance au centre (mm)', 0.0, 5000.0, 'spiro'))

    def __init__(self, parent=None, last: dict | None = None):
        super().__init__(parent, 'Guilloché')
        spec = EQ.GuillocheSpec()
        names = {f.name for f in fields(EQ.GuillocheSpec)}
        for k, v in (last if isinstance(last, dict) else {}).items():
            if k in names:
                try:
                    setattr(spec, k, type(getattr(spec, k))(v))
                except (TypeError, ValueError):
                    pass
        self.kind = QComboBox()
        for key, label in self.KINDS:
            self.kind.addItem(tr(label), key)
        self.kind.setCurrentIndex(max(0, self.kind.findData(spec.kind)))
        self.form.addRow(tr('Motif'), self.kind)
        self.fields = {}
        self.labels = {}
        for name, label, lo, hi, _kinds in self.FIELDS:
            if isinstance(lo, int):
                b = QSpinBox()
            else:
                b = QDoubleSpinBox()
                b.setDecimals(2)
            b.setRange(lo, hi)
            b.setValue(getattr(spec, name))
            b.valueChanged.connect(self.later)
            self.labels[name] = QLabel(tr(label))
            self.form.addRow(self.labels[name], b)
            self.fields[name] = b
        self.outside = QCheckBox(tr('Le cercle roule au-dehors'))
        self.outside.setChecked(spec.outside)
        self.outside.toggled.connect(self.later)
        self.form.addRow('', self.outside)
        self.kind.currentIndexChanged.connect(self._kind_changed)
        self._kind_changed()
        self.refresh()

    def _kind_changed(self, *_a) -> None:
        kind = self.kind.currentData()
        for name, _label, _lo, _hi, kinds in self.FIELDS:
            on = kind in kinds.split()
            self.fields[name].setVisible(on)
            self.labels[name].setVisible(on)
        self.outside.setVisible(kind == 'spiro')
        self.later()

    def spec(self) -> EQ.GuillocheSpec:
        return EQ.GuillocheSpec(kind=self.kind.currentData(), outside=self.outside.isChecked(),
                                **{k: b.value() for k, b in self.fields.items()})

    def values(self) -> dict:
        return asdict(self.spec())

    def compute(self, fine: bool) -> Path:
        return EQ.guilloche(self.spec(), EQ.TOL if fine else PREVIEW_TOL, fine)
