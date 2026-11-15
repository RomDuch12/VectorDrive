"""Design STEP : « Pièce du dessin » — les formes fermées choisies dans le
dessin (et les textes, par leur contour) en pièce STEP à vraies faces
(`core.stepdraw`) : épaisseur, contours intérieurs en trous débouchants, en
poches ou les ronds débouchants et les autres en poches ; une pièce par
bord. Forme tournée (`core.steprevolve`) : chaque contour fermé est un
demi-profil tourné autour du trait droit choisi avec lui (sinon de son bord
gauche). Aperçu, enregistrée dans le dépôt ou ailleurs, ouverte en vue 3D.
"""
from __future__ import annotations

import pathlib
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QSplitter, QVBoxLayout, QWidget)

from ..core import brep as B
from ..core import stepdraw as D
from ..core import steprevolve as RV
from ..i18n import tr
from .step_edit_dialog import STEP_FILTER
from .stepgen_dialog import Preview, depot

#: les modes des contours intérieurs, dans l'ordre de la liste
MODE_LABELS = {'trous': 'Trous débouchants', 'poches': 'Poches', 'ronds': 'Ronds débouchants, autres en poche'}
#: les formes, dans l'ordre de la liste
SHAPE_LABELS = {'extrudee': 'Extrudée (une épaisseur)', 'tournee': 'Tournée (autour d\'un axe)'}
#: d'où vient l'axe d'une pièce tournée
AXIS_LABELS = {'trait': 'du trait droit choisi', 'gauche': 'du bord gauche du profil'}
#: sous-dossier du dépôt
FOLDER = 'Dessin'


def file_stem(name: str) -> str:
    """Un nom de fichier sûr tiré du nom de la pièce."""
    s = re.sub(r'[<>:"/\\|?*\s]+', '_', name.strip()).strip('._')
    return s or 'piece'


class DrawingStepDialog(QDialog):
    """La pièce STEP des contours fermés `path` (document : mm, Y vers le haut)."""

    def __init__(self, win=None, path=None, folder: str | None = None, name: str = 'piece', shape: str = 'extrudee'):
        super().__init__(win)
        self.win = win
        self.path = path
        self.folder = folder or depot(getattr(win, 'settings', None))
        self.bodies: list = []
        self.error = ''
        self.saved: list = []
        self.setWindowTitle(tr('Pièce du dessin'))
        self.resize(900, 560)
        lay = QVBoxLayout(self)
        split = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        form = QFormLayout(left)
        self.name = QLineEdit(name)
        self.shape = QComboBox()
        for k, label in SHAPE_LABELS.items():
            self.shape.addItem(tr(label), k)
        self.shape.setCurrentIndex(max(0, self.shape.findData(shape)))
        self.shape.setToolTip(tr('Tournée : chaque contour fermé est un demi-profil, tourné autour du trait droit '
                                 'choisi avec lui (sinon autour de son bord gauche)'))
        self.thickness = QDoubleSpinBox()
        self.thickness.setRange(0.1, 1000.0)
        self.thickness.setDecimals(2)
        self.thickness.setSuffix(' mm')
        self.thickness.setValue(10.0)
        self.mode = QComboBox()
        for k in D.MODES:
            self.mode.addItem(tr(MODE_LABELS[k]), k)
        self.pocket = QDoubleSpinBox()
        self.pocket.setRange(0.01, 1000.0)
        self.pocket.setDecimals(2)
        self.pocket.setSuffix(' mm')
        self.pocket.setValue(2.0)
        for w in (self.thickness, self.pocket):
            w.setKeyboardTracking(False)
        form.addRow(tr('Nom :'), self.name)
        form.addRow(tr('Forme :'), self.shape)
        form.addRow(tr('Épaisseur :'), self.thickness)
        form.addRow(tr('Contours intérieurs :'), self.mode)
        form.addRow(tr('Profondeur des poches :'), self.pocket)
        self.summary = QLabel('')
        self.summary.setWordWrap(True)
        form.addRow(self.summary)
        split.addWidget(left)
        self.preview = Preview()
        split.addWidget(self.preview)
        split.setStretchFactor(1, 1)
        lay.addWidget(split, 1)
        self.info = QLabel('')
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        row = QHBoxLayout()
        self.b_save = QPushButton(tr('Enregistrer…'))
        self.b_save.setToolTip(tr('La pièce dans un fichier STEP (le dépôt, dossier Dessin, proposé)'))
        self.b_save.clicked.connect(lambda: self.save())
        self.b_open = QPushButton(tr('Ouvrir en 3D'))
        self.b_open.setToolTip(tr('La pièce enregistrée dans le dépôt puis ouverte dans un onglet, vue 3D'))
        self.b_open.clicked.connect(lambda: self.open_step())
        b_close = QPushButton(tr('Fermer'))
        b_close.clicked.connect(self.reject)
        for b in (self.b_save, self.b_open, b_close):           # Entrée valide un champ, rien de plus
            b.setAutoDefault(False)
            b.setDefault(False)
        row.addWidget(self.b_save)
        row.addWidget(self.b_open)
        row.addStretch(1)
        row.addWidget(b_close)
        lay.addLayout(row)
        self.thickness.valueChanged.connect(lambda _v: self.refresh())
        self.pocket.valueChanged.connect(lambda _v: self.refresh())
        self.mode.currentIndexChanged.connect(lambda _i: self.refresh())
        self.shape.currentIndexChanged.connect(lambda _i: self.refresh())
        self.name.editingFinished.connect(self.refresh)
        self.refresh()

    def _summary(self) -> None:
        if self.path is None:
            self.summary.setText(tr('Aucun contour'))
            return
        if self.shape.currentData() == 'tournee':
            try:
                s = RV.summary(self.path)
            except Exception:                                   # noqa: BLE001 — dit sous l'aperçu
                self.summary.setText('')
                return
            text = tr('{0} profil(s), autour {1}').format(s['profiles'], tr(AXIS_LABELS[s['axis']]))
            if s['open']:
                text += ' ; ' + tr('{0} ouverts laissés').format(s['open'])
            text += ' ; ' + tr('Ø {0:g} × {1:g} mm').format(round(s['diameter'], 2), round(s['height'], 2))
            self.summary.setText(text)
            return
        s = D.summary(self.path)
        text = tr('{0} contours fermés, dont {1} ronds').format(s['closed'], s['circles'])
        if s['open']:
            text += ' ; ' + tr('{0} ouverts laissés').format(s['open'])
        if s['bounds'] is not None:
            x0, y0, x1, y1 = s['bounds']
            text += ' ; ' + tr('{0:g} × {1:g} mm').format(round(x1 - x0, 2), round(y1 - y0, 2))
        self.summary.setText(text)

    def set_values(self, thickness=None, mode=None, pocket=None, name=None, shape=None) -> None:
        """Les réglages (essais)."""
        if shape is not None:
            self.shape.blockSignals(True)
            self.shape.setCurrentIndex(self.shape.findData(shape))
            self.shape.blockSignals(False)
        for w, v in ((self.thickness, thickness), (self.pocket, pocket)):
            if v is not None:
                w.blockSignals(True)
                w.setValue(float(v))
                w.blockSignals(False)
        if mode is not None:
            self.mode.blockSignals(True)
            self.mode.setCurrentIndex(self.mode.findData(mode))
            self.mode.blockSignals(False)
        if name is not None:
            self.name.setText(name)
        self.refresh()

    def refresh(self) -> None:
        mode = self.mode.currentData()
        turned = self.shape.currentData() == 'tournee'
        self.thickness.setEnabled(not turned)
        self.mode.setEnabled(not turned)
        self.pocket.setEnabled(mode != 'trous' and not turned)
        self._summary()
        self.bodies, self.error = [], ''
        if self.path is not None:
            try:
                if turned:
                    self.bodies = RV.bodies(self.path, self.name.text().strip() or 'piece')
                else:
                    self.bodies = D.bodies(self.path, self.thickness.value(), mode, self.pocket.value(),
                                           self.name.text().strip() or 'piece')
            except D.DrawError as ex:
                self.error = str(ex)
            except Exception as ex:                             # noqa: BLE001 — géométrie que le noyau refuse
                self.error = str(ex) or type(ex).__name__
        else:
            self.error = tr('Aucun contour')
        meshes = []
        if self.bodies:
            try:
                meshes = [(B.mesh(b), b.color) for b in self.bodies]
            except Exception as ex:                             # noqa: BLE001
                self.bodies, self.error = [], str(ex) or type(ex).__name__
        ok = bool(self.bodies)
        self.b_save.setEnabled(ok)
        self.b_open.setEnabled(ok)
        if not ok:
            self.preview.set_bodies([])
            self.info.setText(tr('Pas de pièce : {0}').format(self.error))
            return
        self.preview.set_bodies(meshes)
        if turned:
            self.info.setText(tr('{0} pièce(s) tournée(s)').format(len(self.bodies)))
            return
        self.info.setText(tr('{0} pièce(s), {1:g} mm d\'épaisseur').format(len(self.bodies), self.thickness.value()))

    def target(self) -> pathlib.Path:
        """Le fichier proposé dans le dépôt."""
        return pathlib.Path(self.folder) / FOLDER / f'{file_stem(self.name.text())}.step'

    def save(self, out: str | None = None, confirm: bool = True) -> str | None:
        """La pièce dans `out` (demandé si None, le dépôt proposé) ; rend le chemin."""
        if not self.bodies:
            return None
        if out is None:
            start = str(self.target())
            try:
                self.target().parent.mkdir(parents=True, exist_ok=True)
            except OSError:                                     # dépôt absent ou en lecture seule
                start = self.target().name
            out, _f = QFileDialog.getSaveFileName(self, tr('Enregistrer la pièce'), start, STEP_FILTER)
            if not out:
                return None
        elif pathlib.Path(out).exists() and confirm and QMessageBox.question(
                self, tr('Enregistrer la pièce'), tr('{0} existe déjà. Le remplacer ?').format(pathlib.Path(out).name)) \
                != QMessageBox.StandardButton.Yes:
            return None
        try:
            pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
            B.write(out, self.bodies, pathlib.Path(out).stem)
        except (OSError, ValueError) as ex:
            QMessageBox.warning(self, tr('Enregistrer la pièce'), tr('Écriture impossible : {0}').format(ex))
            return None
        self.saved.append(str(out))
        self.info.setText(tr('Enregistré : {0}').format(out))
        if self.win is not None and hasattr(self.win, 'statusBar'):
            self.win.statusBar().showMessage(self.info.text(), 8000)
        return str(out)

    def open_step(self, confirm: bool = True) -> str | None:
        """La pièce enregistrée dans le dépôt puis ouverte dans un onglet, vue 3D."""
        if self.win is None or not self.bodies:
            return None
        out = self.save(str(self.target()), confirm)
        if out is None or not self.win.open_path(out):
            return None
        self.win.set_view_mode('3d')
        self.accept()
        return out
