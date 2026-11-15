"""Design STEP : « Vis dans ce trou » — la paroi d'un trou choisie dans la
vue 3D d'une pièce STEP, le trou reconnu (`core.screwfit` : passage, lamé,
fraisé, taraudé ; débouchant ou borgne), la vis normalisée proposée (taille,
longueur) et posée dans le trou, dans les mêmes trous au besoin ; la vis
enregistrée seule ou avec la pièce dans un STEP (géométrie exacte,
coordonnées du fichier de la pièce).
"""
from __future__ import annotations

import os
import pathlib
import tempfile

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QSplitter, QVBoxLayout, QWidget)
from PySide6.QtCore import Qt

from ..core import brep as B
from ..core import screwfit as F
from ..core import stepgen as G
from ..i18n import tr
from .step_edit_dialog import STEP_FILTER
from .stepgen_dialog import Preview

#: familles de vis proposées (clé du générateur)
SCREWS = ('chc', 'h', 'fhc', 'bhc')


def kind_text(kind: str) -> str:
    return {'lamage': tr('lamé'), 'fraisure': tr('fraisé'), 'passage': tr('de passage'),
            'taraude': tr('taraudé')}.get(kind, kind)
PART_COLOR = (0.78, 0.80, 0.84)


def read_part(path):
    """(triangles, face de chaque triangle, descriptions des faces) de la pièce STEP, coordonnées du fichier."""
    import numpy as np
    from ..core import progress as P
    from ..io.neostep import step3d

    def prog(frac, msg):
        P.step(int(frac * 1000), 1000, msg)
        return True
    m = step3d.lire_modele(str(path), axe_haut='Z', progress=prog)
    return np.asarray(m.triangles, float).reshape(-1, 3, 3), np.asarray(m.face_de, dtype=np.int64), list(m.faces)


def file_units(path) -> tuple:
    """(mm par unité de longueur, radians par unité d'angle) du fichier STEP."""
    from ..io.neostep import step3d as S
    mod = S._Modele(S.lire_entites(pathlib.Path(path).read_text(encoding='latin-1')))
    return round(float(mod.unite()), 9), round(float(S._unite_angle(mod)), 12)


#: erreurs du lecteur STEP et de l'extraction des corps (comme la fenêtre « Corps d'un STEP »)
READ_ERRORS = (OSError, ValueError, RuntimeError, KeyError, IndexError, TypeError)


class UnitsError(ValueError):
    """La pièce n'est pas en millimètres et radians comme les corps qu'on lui ajoute."""


def write_with_part(path, bodies: list, out: str, kind: str = 'ajout') -> None:
    """La pièce STEP `path` et les corps `bodies` (millimètres) réunis dans `out`, chaque corps à sa place ;
    UnitsError si la pièce est dans d'autres unités."""
    from ..io import step_extract as X
    fd, tmp = tempfile.mkstemp(suffix='.step')
    os.close(fd)
    try:
        B.write(tmp, bodies, kind)
        if file_units(path) != file_units(tmp):
            raise UnitsError(str(path))
        X.combine([(str(path), None, None), (tmp, None, None)], out, name=pathlib.Path(out).stem)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


class ScrewDialog(QDialog):
    """La vis d'un trou de la pièce `path` dont `face` est une paroi (ou la première des faces `face`
    qui en est une)."""

    def __init__(self, win=None, path: str = '', face=None):
        super().__init__(win)
        self.win = win
        self.setWindowTitle(tr('Vis dans ce trou'))
        self.resize(860, 560)
        self.path = str(path or '')
        self.faces = [] if face is None else [int(f) for f in face] if isinstance(face, (list, tuple, set)) \
            else [int(face)]
        self.face = self.faces[0] if self.faces else None
        self.part = None                       # (T, face_of, infos)
        self.prep = None                       # la pièce préparée pour l'analyse (screwfit.Part)
        self.fit = None
        self.holes: list = []
        self.written: list = []
        lay = QVBoxLayout(self)
        self.hole = QLabel('')
        self.hole.setWordWrap(True)
        lay.addWidget(self.hole)
        split = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        form = QFormLayout(left)
        self.family = QComboBox()
        for k in SCREWS:
            self.family.addItem(tr(G.FAMILIES[k].label), k)
        self.size = QComboBox()
        self.length = QComboBox()
        self.flip = QCheckBox(tr('Tête de l\'autre côté'))
        self.all = QCheckBox(tr('Tous les trous identiques'))
        form.addRow(tr('Vis :'), self.family)
        form.addRow(tr('Taille :'), self.size)
        form.addRow(tr('Longueur :'), self.length)
        form.addRow(self.flip)
        form.addRow(self.all)
        self.note = QLabel('')
        self.note.setWordWrap(True)
        form.addRow(self.note)
        split.addWidget(left)
        self.preview = Preview()
        split.addWidget(self.preview)
        split.setStretchFactor(1, 1)
        lay.addWidget(split, 1)
        self.info = QLabel('')
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        row = QHBoxLayout()
        self.b_save = QPushButton(tr('Enregistrer la vis…'))
        self.b_save.setToolTip(tr('La vis (ou les vis) posée dans le trou, seule dans un fichier STEP, aux '
                                  'coordonnées de la pièce'))
        self.b_save.clicked.connect(lambda: self.save())
        self.b_both = QPushButton(tr('Pièce et vis…'))
        self.b_both.setToolTip(tr('La pièce et ses vis dans un seul fichier STEP'))
        self.b_both.clicked.connect(lambda: self.save_with_part())
        b_close = QPushButton(tr('Fermer'))
        b_close.clicked.connect(self.reject)
        row.addWidget(self.b_save)
        row.addWidget(self.b_both)
        row.addStretch(1)
        row.addWidget(b_close)
        lay.addLayout(row)
        self.family.currentIndexChanged.connect(lambda _i: self._fill_sizes())
        self.size.currentIndexChanged.connect(lambda _i: self._fill_lengths())
        self.length.currentIndexChanged.connect(lambda _i: self.refresh())
        self.flip.toggled.connect(lambda _on: self.analyse(propose=True))
        self.all.toggled.connect(lambda _on: self.refresh())
        self._enable(False)
        if self.path and self.faces:
            self.load()

    # -- trou --
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
        for f in self.faces:                           # la première face choisie qui est une paroi de trou
            try:
                F.analyse(T, fo, infos, f, part=self.prep)
            except (F.FitError, IndexError):
                continue
            self.face = f
            break
        return self.analyse(propose=True)

    def analyse(self, propose: bool = False) -> bool:
        if self.part is None or self.face is None:
            return False
        T, fo, infos = self.part
        try:
            if not 0 <= int(self.face) < len(infos):
                raise F.FitError(tr('face inconnue'))
            fit = F.analyse(T, fo, infos, int(self.face), self.flip.isChecked(), part=self.prep)
        except F.FitError as ex:
            self.fit, self.holes = None, []
            self._say(tr('Pas de vis pour cette face : {0}').format(ex))
            self._enable(False)
            self.all.setEnabled(False)
            self.flip.setEnabled(self.flip.isChecked())      # pour revenir en arrière seulement
            self.refresh()
            return False
        self.fit = fit
        self.holes = F.same_holes(T, fo, infos, fit, part=self.prep)
        self.flip.setEnabled(fit.through)
        self.all.setText(tr('Tous les trous identiques ({0})').format(len(self.holes)))
        self.all.setEnabled(len(self.holes) > 1)
        text = tr('Trou {0} Ø{1:g}, {2}, longueur {3:g} mm').format(
            kind_text(fit.kind), round(fit.diameter, 3),
            tr('débouchant') if fit.through else tr('borgne'), round(fit.depth, 3))
        if fit.counterbore is not None:
            text += ' — ' + tr('lamage Ø{0:g} × {1:g}').format(round(2 * fit.counterbore[0], 3),
                                                                round(fit.counterbore[1], 3))
        self.hole.setText(text)
        if propose:
            p = F.propose(fit)
            self.set_screw(p['family'], p['size'], p['length'])
            self.note.setText(tr('Proposée : {0}').format(p['note']) + (
                '' if p['exact'] else ' — ' + tr('diamètre du trou hors norme : taille la plus proche')))
        self._enable(True)
        self.refresh()
        return True

    # -- vis --
    def set_screw(self, family: str, size: str, length: float) -> None:
        for w in (self.family, self.size, self.length):
            w.blockSignals(True)
        self.family.setCurrentIndex(max(0, self.family.findData(family)))
        self._fill_sizes(refresh=False)
        self.size.setCurrentIndex(max(0, self.size.findData(size)))
        self._fill_lengths(refresh=False)
        i = self.length.findData(float(length))
        self.length.setCurrentIndex(i if i >= 0 else 0)
        for w in (self.family, self.size, self.length):
            w.blockSignals(False)
        self.refresh()

    def _fill_sizes(self, refresh: bool = True) -> None:
        key = self.family.currentData()
        old = self.size.currentData()
        self.size.blockSignals(True)
        self.size.clear()
        for s in G.FAMILIES[key].params[0].choices:
            self.size.addItem(s, s)
        i = self.size.findData(old)
        self.size.setCurrentIndex(i if i >= 0 else min(self.size.count() - 1, self.size.findData('M6')))
        self.size.blockSignals(False)
        self._fill_lengths(refresh)

    def _fill_lengths(self, refresh: bool = True) -> None:
        key, size = self.family.currentData(), self.size.currentData()
        old = self.length.currentData()
        self.length.blockSignals(True)
        self.length.clear()
        lens = F.lengths(key, size) if size else []
        for L in lens:
            self.length.addItem(f'{L:g} mm', float(L))
        if lens:
            near = min(lens, key=lambda L: abs(L - (old if old is not None else 20.0)))
            self.length.setCurrentIndex(self.length.findData(float(near)))
        self.length.blockSignals(False)
        if refresh:
            self.refresh()

    def screw_values(self) -> tuple:
        return self.family.currentData(), self.size.currentData(), self.length.currentData()

    def targets(self) -> list:
        if self.fit is None:
            return []
        return list(self.holes) if self.all.isChecked() and self.all.isEnabled() else [self.fit]

    def bodies(self) -> list:
        """Les vis posées (une par trou visé), nommées."""
        key, size, length = self.screw_values()
        if self.fit is None or not size or length is None:
            return []
        out = []
        holes = self.targets()
        for i, h in enumerate(holes):
            for b in F.screw(h, key, size, float(length)):
                if len(holes) > 1:
                    b.name = f'{b.name} ({i + 1})'
                out.append(b)
        return out

    def refresh(self) -> None:
        import numpy as np
        if self.fit is None or self.part is None:
            self.preview.set_bodies([])
            return
        try:
            screws = self.bodies()
        except G.GenError as ex:
            self.info.setText(str(ex))
            self.preview.set_bodies([])
            return
        T = self.part[0]
        seat = self.fit.seat
        reach = max(3.0 * float(self.length.currentData() or 20.0), 6.0 * self.fit.radius)
        near = np.linalg.norm(T.mean(axis=1) - seat, axis=1) <= reach    # la pièce autour du trou
        meshes = [(T[near], PART_COLOR)] if near.any() else []
        meshes += [(B.mesh(b), b.color) for b in screws if np.linalg.norm(
            np.asarray(b.matrix)[:3, 3] - seat) <= reach]
        self.preview.set_bodies(meshes)
        key, size, length = self.screw_values()
        self.info.setText(tr('{0} vis {1} × {2:g} mm').format(len(self.targets()), size, float(length)))

    def _enable(self, on: bool) -> None:
        for w in (self.family, self.size, self.length, self.b_save, self.b_both):
            w.setEnabled(on)

    def _say(self, text: str) -> None:
        self.hole.setText(text)
        if self.isVisible():
            QMessageBox.warning(self, tr('Vis dans ce trou'), text)

    # -- écrire --
    def _default(self, suffix: str) -> str:
        src = pathlib.Path(self.path)
        _key, size, length = self.screw_values()
        return str(src.parent / f'{src.stem}_{suffix}_{size}x{float(length):g}.step')

    def save(self, out: str | None = None) -> str | None:
        """Les vis seules dans `out` (demandé si None)."""
        bodies = self.bodies()
        if not bodies:
            return None
        if out is None:
            out, _f = QFileDialog.getSaveFileName(self, tr('Enregistrer la vis'), self._default('vis'), STEP_FILTER)
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
        """La pièce et ses vis dans `out` (demandé si None)."""
        bodies = self.bodies()
        if not bodies:
            return None
        if out is None:
            out, _f = QFileDialog.getSaveFileName(self, tr('Pièce et vis'), self._default('avec_vis'), STEP_FILTER)
            if not out:
                return None
        try:
            write_with_part(self.path, bodies, out, 'vis')
        except UnitsError:
            self._say(tr('La pièce n\'est pas en millimètres et radians comme les vis : enregistrer la vis '
                         'seule, puis la réunir à la pièce dans un logiciel de CAO'))
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
