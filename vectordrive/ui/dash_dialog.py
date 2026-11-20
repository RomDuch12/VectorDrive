"""Pointillés : choix du type de trait (standard, d'un fichier .lin ou motif
à soi), de l'échelle, de l'ajustement aux contours fermés et des points ;
aperçu du motif. Les traits sélectionnés deviennent de vrais tirets
(`core.linetypes`)."""
from __future__ import annotations

import json

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout)

from ..core import linetypes as LT
from ..i18n import tr

#: réglages (dernières valeurs)
KEY = 'pointilles/'
#: largeur de l'aperçu (pixels)
PREVIEW_W, PREVIEW_H = 380, 26


def _bool(v, default: bool) -> bool:
    if v is None:
        return default
    return v in (True, 'true', '1', 1)


class DashDialog(QDialog):
    def __init__(self, parent, settings):
        super().__init__(parent)
        from .fit import release
        release(self)                                    # fermée : détruite, pas gardée par son parent
        self.settings = settings
        self.setWindowTitle(tr('Pointillés'))
        self.types = LT.standard() + self._imported()
        lay = QVBoxLayout(self)
        intro = QLabel(tr('Les traits sélectionnés deviennent de vrais tirets (découpe en pointillés, pliage, '
                          'perforation). Motif en mm : un tiret (positif), un espace (négatif), un point (0).'))
        intro.setWordWrap(True)
        lay.addWidget(intro)
        form = QFormLayout()
        lay.addLayout(form)
        row = QHBoxLayout()
        self.kind = QComboBox()
        self.kind.addItem(tr('Motif à soi'), '')
        for t in self.types:
            self.kind.addItem(f'{t.name} — {t.description}' if t.description else t.name, t.name)
        row.addWidget(self.kind, 1)
        imp = QPushButton(tr('Fichier .lin…'))
        imp.setToolTip(tr('Lire les types de traits d\'un fichier .lin (gardés pour la prochaine fois)'))
        imp.clicked.connect(lambda: self.import_lin())
        row.addWidget(imp)
        form.addRow(tr('Type de trait'), row)
        self.pattern = QLineEdit()
        self.pattern.setPlaceholderText('5, -2.5, 0, -2.5')
        self.pattern.setToolTip(tr('Longueurs en mm séparées par des virgules : 5, -2.5 (tiret de 5, espace de '
                                   '2,5) ; 0 : un point'))
        form.addRow(tr('Motif (mm)'), self.pattern)
        self.scale = QDoubleSpinBox()
        self.scale.setRange(0.01, 1000.0)
        self.scale.setDecimals(3)
        self.scale.setSingleStep(0.1)
        self.scale.setToolTip(tr('Multiplie toutes les longueurs du motif (25,4 pour un fichier .lin en pouces)'))
        form.addRow(tr('Échelle'), self.scale)
        self.fit = QCheckBox(tr('Contours fermés : motif ajusté pour tomber juste'))
        self.fit.setToolTip(tr('Un nombre entier de motifs sur chaque contour fermé : pas de tiret raccourci au '
                               'départ'))
        form.addRow('', self.fit)
        self.dot = QDoubleSpinBox()
        self.dot.setRange(0.0, 50.0)
        self.dot.setDecimals(2)
        self.dot.setSuffix(' mm')
        self.dot.setToolTip(tr('Un point du motif devient un cercle de ce diamètre (0 : rien)'))
        form.addRow(tr('Points : cercles de Ø'), self.dot)
        self.keep = QCheckBox(tr('Garder les traits d\'origine'))
        form.addRow('', self.keep)
        self.preview = QLabel()
        self.preview.setMinimumSize(PREVIEW_W, PREVIEW_H)
        lay.addWidget(self.preview)
        self.error = QLabel()
        self.error.setStyleSheet('color: #e03131;')
        lay.addWidget(self.error)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.ok = bb.button(QDialogButtonBox.StandardButton.Ok)
        lay.addWidget(bb)
        s = settings
        self.pattern.setText(str(s.value(KEY + 'motif', '') or '') or LT.format_pattern(self.types[6].pattern))
        self.scale.setValue(float(s.value(KEY + 'echelle', 0.25) or 0.25))
        self.fit.setChecked(_bool(s.value(KEY + 'ajuster'), True))
        self.dot.setValue(float(s.value(KEY + 'point', 0.5) or 0.0))
        self.keep.setChecked(_bool(s.value(KEY + 'garder'), False))
        self.kind.setCurrentIndex(max(0, self.kind.findData(str(s.value(KEY + 'type', 'DASHED') or ''))))
        self._sync_kind()
        self.kind.currentIndexChanged.connect(lambda _i: self._kind_changed())
        self.pattern.textEdited.connect(lambda _t: self._pattern_edited())
        self.scale.valueChanged.connect(lambda _v: self._update())
        self.dot.valueChanged.connect(lambda _v: self._update())
        self._update()

    # --- types de traits ---------------------------------------------------------------------
    def _imported(self) -> list:
        try:
            raw = json.loads(str(self.settings.value(KEY + 'types_lin', '') or '') or '[]')
        except ValueError:
            return []
        out = []
        for d in raw if isinstance(raw, list) else []:
            try:
                out.append(LT.Linetype(str(d['name']), str(d.get('description', '')),
                                       LT.parse_pattern(LT.format_pattern(d['pattern']))))
            except (KeyError, TypeError, ValueError):
                continue
        return out

    def import_lin(self, path: str | None = None) -> int:
        """Types de traits d'un fichier .lin ajoutés à la liste (et retenus)."""
        if path is None:
            path, _f = QFileDialog.getOpenFileName(self, tr('Types de traits'), '',
                                                   tr('Types de traits (*.lin);;Tous les fichiers (*)'))
            if not path:
                return 0
        try:
            data = open(path, 'rb').read(4_000_000)
        except OSError as ex:
            QMessageBox.warning(self, tr('Pointillés'), str(ex))
            return 0
        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError:
            text = data.decode('cp1252', 'replace')
        items, warnings = LT.parse_lin(text)
        known = {t.name.lower() for t in self.types}
        new = [t for t in items if t.name.lower() not in known]
        self.types += new
        for t in new:
            self.kind.addItem(f'{t.name} — {t.description}' if t.description else t.name, t.name)
        mine = self._imported() + new
        self.settings.setValue(KEY + 'types_lin', json.dumps(
            [{'name': t.name, 'description': t.description, 'pattern': t.pattern} for t in mine], ensure_ascii=False))
        if new:
            self.kind.setCurrentIndex(self.kind.findData(new[0].name))
        msg = tr('{0} type(s) de traits lu(s)').format(len(new))
        if warnings:
            msg += '\n\n' + '\n'.join(warnings[:12])
        if path and self.isVisible():
            QMessageBox.information(self, tr('Pointillés'), msg)
        return len(new)

    def _type(self, name: str):
        return next((t for t in self.types if t.name == name), None)

    def _sync_kind(self) -> None:
        t = self._type(self.kind.currentData() or '')
        if t is not None:
            self.pattern.setText(LT.format_pattern(t.pattern))

    def _kind_changed(self) -> None:
        self._sync_kind()
        self._update()

    def _pattern_edited(self) -> None:
        t = self._type(self.kind.currentData() or '')
        try:
            same = t is not None and LT.parse_pattern(self.pattern.text()) == t.pattern
        except ValueError:
            same = False
        if not same and self.kind.currentIndex() != 0:
            self.kind.blockSignals(True)
            self.kind.setCurrentIndex(0)                 # motif retouché : un motif à soi
            self.kind.blockSignals(False)
        self._update()

    # --- aperçu ------------------------------------------------------------------------------
    def _update(self) -> None:
        try:
            pat = LT.parse_pattern(self.pattern.text())
        except ValueError:
            self.error.setText(tr('Motif à corriger : des longueurs en mm, au moins un tiret ou un point'))
            self.ok.setEnabled(False)
            self.preview.setPixmap(QPixmap())
            return
        self.error.setText('')
        self.ok.setEnabled(True)
        self.preview.setPixmap(self.draw_preview(pat, self.scale.value(), self.dot.value()))

    def draw_preview(self, pattern, scale: float, dot: float) -> QPixmap:
        pm = QPixmap(PREVIEW_W, PREVIEW_H)
        pm.fill(Qt.GlobalColor.transparent)
        total = sum(abs(d) for d in pattern) * scale
        span = max(3 * total, 1e-6)
        k = (PREVIEW_W - 8) / span
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self.palette().text().color(), 2)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        p.setPen(pen)
        y = PREVIEW_H / 2
        for a, b in LT.ranges(span, pattern, scale) or [(0.0, span)]:
            if b - a > 1e-9:
                p.drawLine(QPointF(4 + a * k, y), QPointF(4 + b * k, y))
            else:
                r = max(1.5, dot * k / 2)
                p.drawEllipse(QPointF(4 + a * k, y), r, r)
        p.end()
        return pm

    # --- résultat ----------------------------------------------------------------------------
    def values(self) -> dict:
        """{'pattern', 'scale', 'fit', 'dot', 'keep'} ; réglages retenus."""
        pat = LT.parse_pattern(self.pattern.text())
        s = self.settings
        s.setValue(KEY + 'type', self.kind.currentData() or '')
        s.setValue(KEY + 'motif', LT.format_pattern(pat))
        s.setValue(KEY + 'echelle', self.scale.value())
        s.setValue(KEY + 'ajuster', self.fit.isChecked())
        s.setValue(KEY + 'point', self.dot.value())
        s.setValue(KEY + 'garder', self.keep.isChecked())
        return {'pattern': pat, 'scale': self.scale.value(), 'fit': self.fit.isChecked(), 'dot': self.dot.value(),
                'keep': self.keep.isChecked()}
