"""Les fenêtres où l'on clique des faces sur un volume, en 3D : la dépouille (core.draft3d), le
déplacement de faces (core.face_move) et leur suppression (core.face_delete)."""
from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel,
                               QPushButton, QVBoxLayout)

from ..core import draft3d as DR
from ..core import face_delete as FD
from ..core import face_move as FM
from ..core import solids as SO
from ..i18n import tr
from .view3d import View3D


class FacesDialog(QDialog):
    """La vue, les faces cliquées, l'aperçu, et rien de fermé sur une erreur. Le reste aux classes filles :
    `fill(form, row, last)` pour les réglages, `settings()` pour leurs valeurs, `compute(values)` pour le résultat."""
    TITLE = ''

    def __init__(self, win, solid, last: dict | None = None):
        super().__init__(win)
        self.solid = solid
        self.faces = DR._faces(solid)
        last = last or {}
        self.setWindowTitle(tr(self.TITLE))
        self.resize(1000, 680)
        root = QHBoxLayout(self)
        self.view = View3D(self)
        self.view.setMinimumSize(420, 320)
        self.model = SO.to_model([solid])
        self.view.set_model(self.model)
        self.view.set_display('aretes')
        self.view.show_plate = False
        self.view.select_mode = 'faces'
        self.view.selectionChanged.connect(self.selection_changed)
        root.addWidget(self.view, 1)

        side = QVBoxLayout()
        self.note = QLabel(tr('Cliquez une face sur le volume, Ctrl+clic pour en ajouter ou en retirer. '
                              'Glisser fait tourner la vue, la molette zoome.'))
        self.note.setWordWrap(True)
        side.addWidget(self.note)
        form = QFormLayout()
        row = QHBoxLayout()
        self.none_button = QPushButton(tr('Aucune'))
        self.none_button.clicked.connect(lambda _=False: self.choose(()))
        self.fill(form, row, last)
        row.addWidget(self.none_button)
        side.addLayout(form)
        side.addLayout(row)
        self.preview_button = QPushButton(tr('Aperçu'))
        self.preview_button.setCheckable(True)
        self.preview_button.toggled.connect(self.show_preview)
        side.addWidget(self.preview_button)
        self.status = QLabel('')
        self.status.setWordWrap(True)
        side.addWidget(self.status)
        side.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        side.addWidget(buttons)
        root.addLayout(side)
        self.kept: set = set()
        chosen = []
        for q in last.get('picks') or ():                # une étape reprise : ses faces, celles qu'on retrouve
            try:
                chosen.append(DR.find(self.faces, q))
            except DR.DraftError:
                pass
        self.choose(chosen)

    def fill(self, form, row, last: dict) -> None:
        raise NotImplementedError

    def settings(self) -> dict:
        raise NotImplementedError

    def compute(self, values: dict):
        raise NotImplementedError

    def picks(self) -> list:
        return [DR.pick_of(self.solid, f, self.faces) for f in sorted(self.view.sel_faces)]

    def values(self) -> dict:
        return dict(self.settings(), picks=self.picks())

    def choose(self, faces) -> None:
        self.view.set_selection(faces=faces)
        self.selection_changed()

    def selection_changed(self) -> None:
        self.status.setText(tr('{0} face(s) choisie(s)').format(len(self.view.sel_faces)))

    def show_preview(self, on: bool) -> None:
        if not on:
            self.view.set_model(self.model)
            self.view.select_mode = 'faces'
            self.view.set_selection(faces=self.kept)
            return
        try:
            result = self.compute(self.values())
        except SO.SolidError as ex:
            self.status.setText(str(ex))
            self.preview_button.blockSignals(True)
            self.preview_button.setChecked(False)
            self.preview_button.blockSignals(False)
            return
        self.kept = set(self.view.sel_faces)
        self.view.select_mode = 'off'
        self.view.set_model(SO.to_model([result]))

    def accept(self) -> None:
        """Rien ne se ferme sur une erreur : les faces choisies ne sont pas perdues."""
        if self.preview_button.isChecked():
            self.preview_button.setChecked(False)
        try:
            self.compute(self.values())
        except SO.SolidError as ex:
            self.status.setText(str(ex))
            return
        super().accept()


class DeleteFacesDialog(FacesDialog):
    TITLE = 'Supprimer des faces'

    def fill(self, form, row, last: dict) -> None:
        tip = QLabel(tr('Pour un perçage, une poche ou un bossage, leurs parois suffisent.'))
        tip.setWordWrap(True)
        form.addRow(tip)

    def settings(self) -> dict:
        return {}

    def compute(self, values: dict):
        return FD.apply(self.solid, values)


class MoveFacesDialog(FacesDialog):
    TITLE = 'Déplacer des faces'

    def fill(self, form, row, last: dict) -> None:
        self.mode = QComboBox()
        self.mode.addItem(tr('Le long de leur normale'), 'normal')
        self.mode.addItem(tr('Par un vecteur'), 'vector')
        self.mode.setCurrentIndex(max(0, self.mode.findData(last.get('mode', 'normal'))))
        form.addRow(tr('Déplacer'), self.mode)

        def spin(value) -> QDoubleSpinBox:
            box = QDoubleSpinBox()
            box.setDecimals(3)
            box.setRange(-FM.MAX_MOVE, FM.MAX_MOVE)
            box.setSuffix(' mm')
            box.setValue(float(value))
            return box
        self.distance = spin(last.get('distance', 1.0))
        self.distance.setToolTip(tr('Positive : la matière avance, et un trou se resserre. Négative : elle recule.'))
        self.distance_label = QLabel(tr('Distance'))
        form.addRow(self.distance_label, self.distance)
        self.dx, self.dy, self.dz = spin(last.get('dx', 0.0)), spin(last.get('dy', 0.0)), spin(last.get('dz', 0.0))
        self.vector_labels = [QLabel('X'), QLabel('Y'), QLabel('Z')]
        for label, box in zip(self.vector_labels, (self.dx, self.dy, self.dz)):
            form.addRow(label, box)
        self.mode.currentIndexChanged.connect(self.mode_changed)
        self.mode_changed()

    def mode_changed(self, _index: int = 0) -> None:
        normal = self.mode.currentData() == 'normal'
        for w in (self.distance_label, self.distance):
            w.setVisible(normal)
        for w in (*self.vector_labels, self.dx, self.dy, self.dz):
            w.setVisible(not normal)

    def settings(self) -> dict:
        return {'mode': self.mode.currentData(), 'distance': self.distance.value(), 'dx': self.dx.value(),
                'dy': self.dy.value(), 'dz': self.dz.value()}

    def compute(self, values: dict):
        return FM.apply(self.solid, values)


class DraftDialog(FacesDialog):
    TITLE = 'Dépouille'

    def fill(self, form, row, last: dict) -> None:
        self.pull = QComboBox()
        for key, label in (('z+', tr('Vers le haut (Z+)')), ('z-', tr('Vers le bas (Z−)')), ('y+', 'Y+'), ('y-', 'Y−'),
                           ('x+', 'X+'), ('x-', 'X−')):
            self.pull.addItem(label, key)
        at = self.pull.findData(last.get('pull', 'z+'))
        self.pull.setCurrentIndex(max(0, at))
        self.pull.setToolTip(tr('Le sens dans lequel la pièce sort du moule'))
        form.addRow(tr('Démoulage'), self.pull)
        self.angle = QDoubleSpinBox()
        self.angle.setDecimals(2)
        self.angle.setRange(-DR.MAX_ANGLE, DR.MAX_ANGLE)
        self.angle.setSuffix(' °')
        self.angle.setToolTip(tr('Positif : la matière recule en avançant dans le sens du démoulage. Négatif : contre-dépouille.'))
        self.angle.setValue(float(last.get('angle', 3.0)))
        form.addRow(tr('Angle'), self.angle)
        self.neutral = QDoubleSpinBox()
        self.neutral.setDecimals(3)
        self.neutral.setRange(-100000.0, 100000.0)
        self.neutral.setSuffix(' mm')
        self.neutral.setToolTip(tr('La hauteur, le long du démoulage, où les faces ne bougent pas'))
        given = last.get('neutral')
        self.neutral.setValue(DR.neutral_default(self.solid, self.pull.currentData()) if given is None else float(given))
        form.addRow(tr('Plan neutre'), self.neutral)
        self.pull.currentIndexChanged.connect(self.pull_changed)
        self.walls_button = QPushButton(tr('Toutes les parois'))
        self.walls_button.clicked.connect(lambda _=False: self.choose(DR.walls(self.faces, self.pull.currentData())))
        row.addWidget(self.walls_button)

    def settings(self) -> dict:
        return {'angle': self.angle.value(), 'neutral': self.neutral.value(), 'pull': self.pull.currentData()}

    def compute(self, values: dict):
        return DR.apply(self.solid, values)

    def pull_changed(self, _index: int = 0) -> None:
        self.neutral.setValue(DR.neutral_default(self.solid, self.pull.currentData()))
