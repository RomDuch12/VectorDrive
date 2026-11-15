"""Design STEP : « Pièce dans ce trou » — la paroi d'un alésage choisie dans
la vue 3D d'une pièce STEP (`core.holefit` : axe, entrée, fond, diamètre,
profondeur ; débouchant ou borgne), une pièce des générateurs (goupille,
roulement, bague, douille, colonne, éjecteur, bague de centrage) proposée au
diamètre de l'alésage et posée dedans, dans les mêmes alésages au besoin ; ses
cotes changées à la main ; enregistrée seule ou avec la pièce percée dans un
STEP (géométrie exacte, coordonnées du fichier de la pièce).
"""
from __future__ import annotations

import pathlib

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QSplitter, QVBoxLayout, QWidget)

from ..core import brep as B
from ..core import holefit as H
from ..core import screwfit as F
from ..core import stepgen as G
from ..i18n import tr
from .screw_dialog import PART_COLOR, READ_ERRORS, UnitsError, read_part, write_with_part
from .step_edit_dialog import STEP_FILTER
from .stepgen_dialog import Preview, param_widget, set_widget, widget_value

#: où chaque pièce est posée dans l'alésage (dit sous la proposition)
PLACES = {
    'goupille': 'au ras de l\'entrée, la plus longue de la série dans la profondeur',
    'roulement': 'au ras de l\'entrée',
    'bague': 'au ras de l\'entrée, toute la profondeur',
    'douille': 'la collerette sur l\'entrée, le corps dans toute la profondeur',
    'colonne': 'la collerette contre la sortie, la colonne qui dépasse de l\'entrée',
    'ejecteur': 'le bout au ras de l\'entrée, la tête juste sous la sortie',
    'bague_centrage': 'au fond d\'un alésage borgne, au ras de l\'entrée d\'un débouchant',
}


class PartHoleDialog(QDialog):
    """La pièce posée dans un alésage de la pièce `path` dont `face` est une paroi (ou la première des faces
    `face` qui en est une)."""

    def __init__(self, win=None, path: str = '', face=None):
        super().__init__(win)
        self.win = win
        self.setWindowTitle(tr('Pièce dans ce trou'))
        self.resize(900, 580)
        self.path = str(path or '')
        self.faces = [] if face is None else [int(f) for f in face] if isinstance(face, (list, tuple, set)) \
            else [int(face)]
        self.face = self.faces[0] if self.faces else None
        self.part = None                       # (T, face_of, infos)
        self.prep = None                       # la pièce préparée pour l'analyse (screwfit.Part)
        self.bore = None
        self.bores: list = []
        self.widgets: dict = {}
        self.written: list = []
        lay = QVBoxLayout(self)
        self.hole = QLabel('')
        self.hole.setWordWrap(True)
        lay.addWidget(self.hole)
        split = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        col = QVBoxLayout(left)
        top = QFormLayout()
        self.family = QComboBox()
        for k in H.FAMILIES:
            self.family.addItem(tr(G.FAMILIES[k].label), k)
        top.addRow(tr('Pièce :'), self.family)
        col.addLayout(top)
        self.form = QFormLayout()
        col.addLayout(self.form)
        self.flip = QCheckBox(tr('Entrer par l\'autre côté'))
        self.all = QCheckBox(tr('Tous les alésages identiques'))
        self.b_propose = QPushButton(tr('Proposer de nouveau'))
        self.b_propose.setToolTip(tr('Les cotes proposées pour cet alésage, à la place de celles changées'))
        self.note = QLabel('')
        self.note.setWordWrap(True)
        for w in (self.flip, self.all, self.b_propose, self.note):
            col.addWidget(w)
        col.addStretch(1)
        split.addWidget(left)
        self.preview = Preview()
        split.addWidget(self.preview)
        split.setStretchFactor(1, 1)
        lay.addWidget(split, 1)
        self.info = QLabel('')
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        row = QHBoxLayout()
        self.b_save = QPushButton(tr('Enregistrer seule…'))
        self.b_save.setToolTip(tr('La pièce posée dans l\'alésage (ou dans chacun), seule dans un fichier STEP, '
                                  'aux coordonnées de la pièce percée'))
        self.b_save.clicked.connect(lambda: self.save())
        self.b_both = QPushButton(tr('Avec la pièce percée…'))
        self.b_both.setToolTip(tr('La pièce percée et ce qui est posé dans ses alésages dans un seul fichier STEP'))
        self.b_both.clicked.connect(lambda: self.save_with_part())
        b_close = QPushButton(tr('Fermer'))
        b_close.clicked.connect(self.reject)
        row.addWidget(self.b_save)
        row.addWidget(self.b_both)
        row.addStretch(1)
        row.addWidget(b_close)
        lay.addLayout(row)
        self.family.currentIndexChanged.connect(lambda _i: self.propose())
        self.flip.toggled.connect(lambda _on: self.analyse())
        self.all.toggled.connect(lambda _on: self.refresh())
        self.b_propose.clicked.connect(lambda: self.propose())
        self._enable(False)
        if self.path and self.faces:
            self.load()

    # -- alésage --
    def load(self) -> bool:
        from ..core.progress import Cancelled
        from . import progress
        try:
            self.part = progress.run(self, tr('Lecture du STEP'), read_part, self.path)
        except Cancelled:
            return False
        except READ_ERRORS as ex:
            self._say(tr('Lecture impossible : {0}').format(ex))
            return False
        T, fo, infos = self.part
        self.prep = F.Part(T, fo, infos)
        for f in self.faces:                           # la première face choisie qui est la paroi d'un alésage
            try:
                H.bore(T, fo, infos, f, part=self.prep)
            except (F.FitError, IndexError):
                continue
            self.face = f
            break
        return self.analyse()

    def analyse(self) -> bool:
        """L'alésage de la face (entrée retournée si coché), les mêmes alésages, puis la proposition."""
        if self.part is None or self.face is None:
            return False
        T, fo, infos = self.part
        try:
            b = H.bore(T, fo, infos, int(self.face), self.flip.isChecked(), part=self.prep)
        except (F.FitError, IndexError) as ex:
            self.bore, self.bores = None, []
            self._say(tr('Pas d\'alésage pour cette face : {0}').format(ex))
            self._enable(False)
            self.all.setEnabled(False)
            self.flip.setEnabled(self.flip.isChecked())      # pour revenir en arrière seulement
            self.refresh()
            return False
        self.bore = b
        self.bores = H.same_bores(T, fo, infos, b, part=self.prep)
        self.flip.setEnabled(b.through)
        self.all.setText(tr('Tous les alésages identiques ({0})').format(len(self.bores)))
        self.all.setEnabled(len(self.bores) > 1)
        self.hole.setText(tr('Alésage Ø{0:g}, {1}, profondeur {2:g} mm').format(
            round(b.diameter, 3), tr('débouchant') if b.through else tr('borgne'), round(b.depth, 3)))
        self.family.setEnabled(True)
        self.b_propose.setEnabled(True)
        return self.propose()

    # -- pièce --
    def propose(self) -> bool:
        """Les cotes proposées pour la pièce choisie dans l'alésage ; False si elle n'y va pas (dit)."""
        key = self.family.currentData()
        if self.bore is None or key is None:
            return False
        try:
            v = H.propose(self.bore, key)
        except (F.FitError, G.GenError) as ex:
            self._build_form(key, None)
            self.note.setText(tr('Ne va pas dans cet alésage : {0}').format(ex))
            self._fits(False)
            self.refresh()
            return False
        self._build_form(key, v)
        self.note.setText(tr('Proposée au Ø{0:g} de l\'alésage, posée {1} ; les cotes se changent').format(
            round(self.bore.diameter, 3), tr(PLACES[key])))
        self._fits(True)
        self.refresh()
        return True

    def _build_form(self, key: str, values: dict | None) -> None:
        while self.form.rowCount():
            self.form.removeRow(0)
        self.widgets = {}
        for p in G.FAMILIES[key].params:
            w = param_widget(p, lambda *_a: self.refresh())
            if values is not None and p.key in values:
                w.blockSignals(True)
                set_widget(w, values[p.key])
                w.blockSignals(False)
            self.widgets[p.key] = w
            self.form.addRow(tr(p.label), w)

    def set_value(self, key: str, value) -> None:
        """Une cote de la pièce montrée (essais)."""
        set_widget(self.widgets[key], value)

    def current_values(self) -> dict:
        """Les cotes montrées, contrôlées (GenError)."""
        return G.values(self.family.currentData(), **{k: widget_value(w) for k, w in self.widgets.items()})

    def targets(self) -> list:
        if self.bore is None:
            return []
        return list(self.bores) if self.all.isChecked() and self.all.isEnabled() else [self.bore]

    def bodies(self) -> list:
        """Les pièces posées (une par alésage visé), nommées."""
        if self.bore is None or not self.b_save.isEnabled():
            return []
        key = self.family.currentData()
        v = self.current_values()
        out = []
        bores = self.targets()
        for i, b in enumerate(bores):
            for body in H.parts(b, key, v):
                if len(bores) > 1:
                    body.name = f'{body.name} ({i + 1})'
                out.append(body)
        return out

    def refresh(self) -> None:
        import numpy as np
        if self.bore is None or self.part is None:
            self.preview.set_bodies([])
            return
        T = self.part[0]
        reach = max(3.0 * self.bore.diameter, 2.0 * self.bore.depth, 20.0)
        near = np.linalg.norm(T.mean(axis=1) - self.bore.entry, axis=1) <= reach    # la pièce autour de l'alésage
        meshes = [(T[near], PART_COLOR)] if near.any() else []
        try:
            added = self.bodies()
        except G.GenError as ex:
            self.info.setText(str(ex))
            self.preview.set_bodies(meshes)
            return
        meshes += [(B.mesh(b), b.color) for b in added if np.linalg.norm(
            np.asarray(b.matrix)[:3, 3] - self.bore.entry) <= reach + 2.0 * self.bore.depth]
        self.preview.set_bodies(meshes)
        if not added:
            self.info.setText('')
            return
        n = len(self.targets())
        text = [tr('{0} × {1}').format(n, tr(G.FAMILIES[self.family.currentData()].label))]
        up, down = H.outside(self.bore, added[:len(added) // n])          # la pièce du premier alésage
        if up:
            text.append(tr('dépasse de {0:g} mm de l\'entrée').format(up))
        if down:
            text.append(tr('dépasse de {0:g} mm de la sortie').format(down) if self.bore.through
                        else tr('entre de {0:g} mm dans la matière au fond').format(down))
        self.info.setText(' ; '.join(text))

    def _fits(self, on: bool) -> None:
        for w in [self.b_save, self.b_both] + list(self.widgets.values()):
            w.setEnabled(on)

    def _enable(self, on: bool) -> None:
        self.family.setEnabled(on)
        self.b_propose.setEnabled(on)
        self._fits(on)

    def _say(self, text: str) -> None:
        self.hole.setText(text)
        if self.isVisible():
            QMessageBox.warning(self, tr('Pièce dans ce trou'), text)

    # -- écrire --
    def _default(self, suffix: str) -> str:
        src = pathlib.Path(self.path)
        return str(src.parent / f'{src.stem}_{suffix}{self.family.currentData()}.step')

    def save(self, out: str | None = None) -> str | None:
        """Les pièces posées seules dans `out` (demandé si None)."""
        try:
            bodies = self.bodies()
        except G.GenError as ex:
            self._say(str(ex))
            return None
        if not bodies:
            return None
        if out is None:
            out, _f = QFileDialog.getSaveFileName(self, tr('Enregistrer la pièce posée'), self._default(''),
                                                  STEP_FILTER)
            if not out:
                return None
        try:
            B.write(out, bodies, pathlib.Path(out).stem)
        except (OSError, ValueError) as ex:
            self._say(tr('Écriture impossible : {0}').format(ex))
            return None
        self._done(out)
        return out

    def save_with_part(self, out: str | None = None) -> str | None:
        """La pièce percée et ce qui est posé dans `out` (demandé si None)."""
        try:
            bodies = self.bodies()
        except G.GenError as ex:
            self._say(str(ex))
            return None
        if not bodies:
            return None
        if out is None:
            out, _f = QFileDialog.getSaveFileName(self, tr('Avec la pièce percée'), self._default('avec_'),
                                                  STEP_FILTER)
            if not out:
                return None
        try:
            write_with_part(self.path, bodies, out, self.family.currentData())
        except UnitsError:
            self._say(tr('La pièce percée n\'est pas en millimètres et radians : enregistrer la pièce posée seule, '
                         'puis les réunir dans un logiciel de CAO'))
            return None
        except READ_ERRORS as ex:
            self._say(tr('Écriture impossible : {0}').format(ex))
            return None
        self._done(out)
        return out

    def _done(self, path: str) -> None:
        self.written.append(path)
        self.info.setText(tr('Écrit : {0}').format(path))
        if self.win is not None and hasattr(self.win, 'statusBar'):
            self.win.statusBar().showMessage(self.info.text(), 8000)
