"""Design STEP : les corps d'un fichier STEP (`io.step_extract`) — listés
avec leur nombre de faces et montrés dans un aperçu qu'on fait tourner ;
les corps cochés extraits dans un fichier, ou chacun dans le sien (un moule
en trois parties : trois STEP), déplacés au besoin (translation, rotation
autour d'un axe) ; géométrie exacte, noms, couleurs et unités gardés.

Les coordonnées restent celles du fichier d'origine : les pièces séparées
se remettent à leur place quand on les réunit (`step_combine` de la fenêtre
principale).
"""
from __future__ import annotations

import math
import pathlib

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSplitter,
                               QVBoxLayout, QWidget)

from ..i18n import tr
from ..io import step_extract as X
from .stepgen_dialog import Preview, depot

STEP_FILTER = 'STEP (*.step *.stp *.STEP *.STP)'
#: erreurs d'un fichier illisible ou d'une écriture impossible, dites sans fermer la fenêtre
ERRORS = (OSError, ValueError, RuntimeError, KeyError, IndexError, TypeError)


def rotation(axis: str, degrees: float):
    """Rotation de `degrees` autour de l'axe 'X', 'Y' ou 'Z' (3×3, quarts de tour exacts)."""
    a = math.radians(degrees)
    c, s = math.cos(a), math.sin(a)
    c, s = (0.0 if abs(c) < 1e-12 else c), (0.0 if abs(s) < 1e-12 else s)
    if axis == 'X':
        return [[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]]
    if axis == 'Y':
        return [[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]]
    return [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]


def read_all(path) -> tuple:
    """(corps `step_extract.bodies`, maillages `read_meshes`) du STEP, avec avancement."""
    return X.bodies(path), read_meshes(path)


def read_meshes(path) -> list:
    """[(triangles (n, 3, 3), couleur)] par corps du STEP, dans les coordonnées du fichier (une pièce couchée
    n'est pas redressée ici : les déplacements se donnent dans ces coordonnées)."""
    import numpy as np
    from ..core import progress as P
    from ..io.model3d import ALU
    from ..io.neostep import step3d

    def prog(frac, msg):
        P.step(int(frac * 1000), 1000, msg)
        return True
    m = step3d.lire_modele(str(path), axe_haut='Z', progress=prog)
    T = np.asarray(m.triangles, float).reshape(-1, 3, 3)
    cols = np.asarray(m.couleurs, float).reshape(-1, 3) if len(m.couleurs) == len(T) \
        else np.tile(np.array(ALU), (len(T), 1))
    fd = np.asarray(m.face_de, dtype=np.int64) if len(getattr(m, 'face_de', ())) == len(T) else None
    if fd is None or not m.corps or not m.faces:
        return [(T, tuple(cols.mean(0)) if len(T) else ALU)]
    per = np.array([int(f.get('corps', -1)) for f in m.faces], dtype=np.int64)[fd]
    out = []
    for k in range(len(m.corps)):
        sel = per == k
        out.append((T[sel], tuple(cols[sel].mean(0)) if sel.any() else ALU))
    return out


class StepBodiesDialog(QDialog):
    """Les corps d'un STEP : cocher, déplacer, extraire dans un fichier ou un fichier par corps."""

    def __init__(self, win=None, path: str | None = None, picks=None):
        super().__init__(win)
        self.win = win
        self.setWindowTitle(tr('Corps d\'un STEP'))
        self.resize(900, 600)
        self.path = ''
        self.mtime = None
        self.bodies: list = []
        self.meshes: list = []
        self.written: list = []
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.file = QLineEdit()
        self.file.setReadOnly(True)
        self.file.setPlaceholderText(tr('Aucun fichier'))
        b_open = QPushButton(tr('Ouvrir…'))
        b_open.clicked.connect(lambda: self.load_file())
        top.addWidget(QLabel(tr('Fichier :')))
        top.addWidget(self.file, 1)
        top.addWidget(b_open)
        lay.addLayout(top)
        split = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self.list = QListWidget()
        self.list.itemChanged.connect(lambda _i: self.refresh())
        ll.addWidget(self.list, 1)
        row = QHBoxLayout()
        for label, on in ((tr('Tout cocher'), True), (tr('Tout décocher'), False)):
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, v=on: self.check_all(v))
            row.addWidget(b)
        ll.addLayout(row)
        box = QGroupBox(tr('Déplacer les corps cochés'))
        form = QFormLayout(box)
        self.d = []
        for axis in 'XYZ':
            sp = QDoubleSpinBox()
            sp.setRange(-100000.0, 100000.0)
            sp.setDecimals(3)
            sp.setSuffix(' mm')
            sp.valueChanged.connect(lambda _v: self.refresh())
            form.addRow(tr('Translation {0} :').format(axis), sp)
            self.d.append(sp)
        self.axis = QComboBox()
        for axis in 'XYZ':
            self.axis.addItem(tr('Autour de {0}').format(axis), axis)
        self.axis.setCurrentIndex(2)
        self.axis.currentIndexChanged.connect(lambda _i: self.refresh())
        self.angle = QDoubleSpinBox()
        self.angle.setRange(-360.0, 360.0)
        self.angle.setDecimals(3)
        self.angle.setSuffix(' °')
        self.angle.valueChanged.connect(lambda _v: self.refresh())
        form.addRow(tr('Rotation :'), self.axis)
        form.addRow(tr('Angle :'), self.angle)
        form.addRow(QLabel(tr('Rotation autour de l\'origine du fichier, puis translation.')))
        ll.addWidget(box)
        split.addWidget(left)
        self.preview = Preview()
        split.addWidget(self.preview)
        split.setStretchFactor(1, 1)
        lay.addWidget(split, 1)
        self.info = QLabel('')
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        bottom = QHBoxLayout()
        self.b_extract = QPushButton(tr('Extraire les corps cochés…'))
        self.b_extract.setToolTip(tr('Les corps cochés dans un seul fichier STEP'))
        self.b_extract.clicked.connect(lambda: self.extract())
        self.b_split = QPushButton(tr('Un fichier par corps…'))
        self.b_split.setToolTip(tr('Chaque corps coché dans son fichier STEP, nommé d\'après le corps'))
        self.b_split.clicked.connect(lambda: self.split())
        self.b_show = QPushButton(tr('Voir les fichiers'))
        self.b_show.setToolTip(tr('Les fichiers écrits dans le navigateur à vignettes'))
        self.b_show.clicked.connect(lambda: self.show_written())
        self.b_show.setEnabled(False)
        b_close = QPushButton(tr('Fermer'))
        b_close.clicked.connect(self.reject)
        for b in (self.b_extract, self.b_split, self.b_show):
            bottom.addWidget(b)
        bottom.addStretch(1)
        bottom.addWidget(b_close)
        lay.addLayout(bottom)
        self._update_buttons()
        if path:
            self.load(path, picks)

    # -- fichier --
    def _start_dir(self) -> str:
        if self.path:
            return str(pathlib.Path(self.path).parent)
        return depot(getattr(self.win, 'settings', None))

    def load_file(self) -> bool:
        path, _f = QFileDialog.getOpenFileName(self, tr('Ouvrir un STEP'), self._start_dir(), STEP_FILTER)
        return self.load(path) if path else False

    def load(self, path, picks=None) -> bool:
        """Lit les corps de `path` ; `picks` : les corps cochés (tous si None)."""
        from ..core.progress import Cancelled
        from . import progress
        import os
        try:
            mtime = os.path.getmtime(path)
            bodies, meshes = progress.run(self, tr('Lecture du STEP'), read_all, path)
        except Cancelled:
            return False
        except ERRORS as ex:
            self._say(tr('Lecture impossible : {0}').format(ex))
            return False
        if not bodies:
            self._say(tr('Aucun corps dans ce fichier.'))
            return False
        self.path, self.bodies, self.mtime = str(path), bodies, mtime
        self.meshes = meshes if len(meshes) == len(bodies) else []
        self.file.setText(self.path)
        sel = set(range(len(bodies))) if picks is None else {int(k) for k in picks}
        self.list.blockSignals(True)
        self.list.clear()
        for k, b in enumerate(bodies):
            it = QListWidgetItem(tr('{0} — {1} faces').format(b.name, b.faces))
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if k in sel else Qt.CheckState.Unchecked)
            self.list.addItem(it)
        self.list.blockSignals(False)
        self.written = []
        self.b_show.setEnabled(False)
        unit = float(bodies[0].extra.get('unit_mm', 1.0))
        self.info.setText(tr('{0} corps').format(len(bodies)) + (
            '' if abs(unit - 1.0) < 1e-9 else ' — ' + tr('unité du fichier : {0} mm').format(f'{unit:g}')))
        self.refresh()
        return True

    # -- choix et déplacement --
    def checked(self) -> list:
        return [k for k in range(self.list.count())
                if self.list.item(k).checkState() == Qt.CheckState.Checked]

    def check_all(self, on: bool = True) -> None:
        self.list.blockSignals(True)
        for k in range(self.list.count()):
            self.list.item(k).setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
        self.list.blockSignals(False)
        self.refresh()

    def set_move(self, dx=0.0, dy=0.0, dz=0.0, axis='Z', angle=0.0) -> None:
        for sp, v in zip(self.d, (dx, dy, dz)):
            sp.blockSignals(True)
            sp.setValue(float(v))
            sp.blockSignals(False)
        self.axis.blockSignals(True)
        self.axis.setCurrentIndex('XYZ'.index(axis))
        self.axis.blockSignals(False)
        self.angle.blockSignals(True)
        self.angle.setValue(float(angle))
        self.angle.blockSignals(False)
        self.refresh()

    def move(self):
        """(R, t mm) donné, ou None (aucun déplacement)."""
        t = [sp.value() for sp in self.d]
        a = self.angle.value()
        if all(abs(v) < 1e-12 for v in t) and abs(a % 360.0) < 1e-12:
            return None
        return rotation(self.axis.currentData(), a), t

    def moves(self, picks) -> dict | None:
        mv = self.move()
        return None if mv is None else {k: mv for k in picks}

    def refresh(self) -> None:
        import numpy as np
        picks = set(self.checked())
        mv = self.move()
        meshes = []
        for k, (T, c) in enumerate(self.meshes):
            if k not in picks or not len(T):
                continue
            if mv is not None:
                T = T @ np.asarray(mv[0]).T + np.asarray(mv[1])
            meshes.append((T, c))
        self.preview.set_bodies(meshes)
        self._update_buttons()

    def _update_buttons(self) -> None:
        on = bool(self.path) and bool(self.checked())
        self.b_extract.setEnabled(on)
        self.b_split.setEnabled(on)

    def _changed_on_disk(self) -> bool:
        """Le fichier a-t-il changé depuis sa lecture ? Alors il est relu (les numéros des corps ont pu changer)
        et rien n'est écrit."""
        import os
        try:
            same = os.path.getmtime(self.path) == self.mtime
        except OSError:
            same = False
        if same:
            return False
        picks = self.checked()
        self._say(tr('Le fichier a changé depuis sa lecture : il est relu, rien n\'est écrit.'))
        info = self.info.text()
        self.load(self.path, picks)
        self.info.setText(info)
        return True

    def _run(self, title: str, fn, *args, **kw):
        """`fn` avec avancement ; None si annulé (fichiers déjà écrits gardés)."""
        from ..core.progress import Cancelled
        from . import progress
        try:
            return progress.run(self, title, fn, *args, **kw)
        except Cancelled:
            return None

    def _say(self, text: str, warn: bool = True) -> None:
        self.info.setText(text)
        if warn and self.isVisible():
            QMessageBox.warning(self, tr('Corps d\'un STEP'), text)

    # -- écrire --
    def extract(self, out: str | None = None) -> str | None:
        """Les corps cochés (déplacés si demandé) dans le fichier `out` (demandé si None)."""
        picks = self.checked()
        if not self.path or not picks:
            return None
        if out is None:
            src = pathlib.Path(self.path)
            name = self.bodies[picks[0]].name if len(picks) == 1 else tr('extrait')
            stem = X.safe_name(f'{src.stem}_{name}') or 'extrait'
            out, _f = QFileDialog.getSaveFileName(self, tr('Extraire les corps cochés'),
                                                  str(src.parent / f'{stem}.step'), STEP_FILTER)
            if not out:
                return None
        if self._changed_on_disk():
            return None
        try:
            path = self._run(tr('Extraire les corps cochés'), X.extract, self.path, picks, out,
                             moves=self.moves(picks))
        except ERRORS as ex:
            self._say(tr('Écriture impossible : {0}').format(ex))
            return None
        if path is None:
            return None
        self._done([path])
        return path

    def split(self, folder: str | None = None, ask: bool = True) -> list:
        """Chaque corps coché dans son fichier, dans `folder` (demandé si None) ; fichiers existants remplacés
        après confirmation si `ask`."""
        picks = self.checked()
        if not self.path or not picks:
            return []
        if folder is None:
            src = pathlib.Path(self.path)
            folder = QFileDialog.getExistingDirectory(self, tr('Dossier des fichiers par corps'), str(src.parent))
            if not folder:
                return []
        names = [pathlib.Path(folder) / f'{s}.step' for s in X.file_stems(self.bodies, picks)]
        there = [p.name for p in names if p.exists()]
        if there and ask:
            r = QMessageBox.question(self, tr('Un fichier par corps'),
                                     tr('Remplacer les fichiers existants ?') + '\n' + '\n'.join(there[:12])
                                     + ('\n…' if len(there) > 12 else ''))
            if r != QMessageBox.StandardButton.Yes:
                return []
        if self._changed_on_disk():
            return []
        try:
            files = self._run(tr('Un fichier par corps'), X.split, self.path, folder, picks,
                              moves=self.moves(picks))
        except ERRORS as ex:
            self._say(tr('Écriture impossible : {0}').format(ex))
            return []
        if files is None:
            return []
        self._done(files)
        return files

    def _done(self, files: list) -> None:
        self.written = list(files)
        self.b_show.setEnabled(bool(files) and self.win is not None)
        where = str(pathlib.Path(files[0]).parent) if files else ''
        self.info.setText(tr('{0} fichier(s) écrit(s) dans {1} : {2}').format(
            len(files), where, ', '.join(pathlib.Path(f).name for f in files[:8]) + ('…' if len(files) > 8 else '')))
        if self.win is not None and hasattr(self.win, 'statusBar'):
            self.win.statusBar().showMessage(self.info.text(), 8000)

    def show_written(self, exec_dialog: bool = True):
        """Le dossier des fichiers écrits dans le navigateur à vignettes."""
        if not self.written or self.win is None:
            return None
        return self.win.file_browser(exec_dialog, folder=str(pathlib.Path(self.written[0]).parent),
                                     exts=('.stp', '.step'), remember=False)
