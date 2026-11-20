"""La fenêtre des congés et chanfreins : on clique les arêtes sur le volume, en 3D (core.edge_blend)."""
from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QHBoxLayout,
                               QLabel, QPushButton, QVBoxLayout)

from ..core import edge_blend as EB
from ..core import solids as SO
from ..i18n import tr
from .view3d import View3D


def _spin(value: float) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setDecimals(3)
    s.setRange(0.001, 10000.0)
    s.setSingleStep(0.5)
    s.setSuffix(' mm')
    s.setValue(value)
    return s


class EdgesDialog(QDialog):
    def __init__(self, win, solid, last: dict | None = None):
        super().__init__(win)
        from .fit import release
        release(self)                                    # fermée : détruite, pas gardée par son parent
        self.solid = solid
        self.chains = EB.sharp_chains(solid)
        last = last or {}
        self.setWindowTitle(tr('Congés et chanfreins'))
        self.resize(1000, 680)
        root = QHBoxLayout(self)
        self.view = View3D(self)
        self.view.setMinimumSize(420, 320)
        self.model = SO.to_model([solid])
        self.view.set_model(self.model)
        self.view.set_display('aretes')
        self.view.show_plate = False
        self.view.select_mode = 'aretes'
        self.view.set_edge_chains([c.points for c in self.chains])
        self.view.selectionChanged.connect(self.selection_changed)
        root.addWidget(self.view, 1)

        side = QVBoxLayout()
        self.note = QLabel(tr('Cliquez les arêtes sur le volume ; un second clic en retire une. '
                              'Glisser fait tourner la vue, la molette zoome.'))
        self.note.setWordWrap(True)
        side.addWidget(self.note)
        form = QFormLayout()
        self.kind = QComboBox()
        self.kind.addItem(tr('Congé'), 'fillet')
        self.kind.addItem(tr('Chanfrein'), 'chamfer')
        self.kind.setCurrentIndex(1 if last.get('kind') == 'chamfer' else 0)
        form.addRow(tr('Forme'), self.kind)
        self.radius = _spin(float(last.get('radius', 2.0) or 2.0))
        self.radius.setToolTip(tr('Congé : le rayon. Chanfrein : la distance le long de chaque face.'))
        form.addRow(tr('Rayon ou distance'), self.radius)
        end = float(last.get('radius_end', 0.0) or 0.0)
        self.variable = QCheckBox(tr('Variable le long de l’arête'))
        self.variable.setChecked(end > 0.0)
        form.addRow(self.variable)
        self.end = _spin(end if end > 0.0 else float(last.get('radius', 2.0) or 2.0))
        self.end.setEnabled(end > 0.0)
        self.variable.toggled.connect(self.end.setEnabled)
        form.addRow(tr('À l’autre bout'), self.end)
        side.addLayout(form)

        row = QHBoxLayout()
        self.all_button = QPushButton(tr('Toutes'))
        self.all_button.clicked.connect(lambda _=False: self.choose(range(len(self.chains))))
        self.out_button = QPushButton(tr('Saillantes'))
        self.out_button.clicked.connect(lambda _=False: self.choose(k for k, c in enumerate(self.chains) if c.convex))
        self.in_button = QPushButton(tr('Rentrantes'))
        self.in_button.clicked.connect(lambda _=False: self.choose(k for k, c in enumerate(self.chains) if not c.convex))
        self.none_button = QPushButton(tr('Aucune'))
        self.none_button.clicked.connect(lambda _=False: self.choose(()))
        for b in (self.all_button, self.out_button, self.in_button, self.none_button):
            row.addWidget(b)
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

        chosen = []
        for q in last.get('picks') or ():                # une étape reprise : ses arêtes, celles qu'on retrouve
            try:
                chosen.append(EB.find(self.chains, q))
            except EB.EdgeBlendError:
                pass
        self.choose(chosen)

    def picks(self) -> list:
        return [self.chains[k].middle() for k in sorted(self.view.sel_edges)]

    def values(self) -> dict:
        return {'kind': self.kind.currentData(), 'radius': self.radius.value(),
                'radius_end': self.end.value() if self.variable.isChecked() else 0.0, 'picks': self.picks()}

    def choose(self, ranks) -> None:
        self.view.set_edge_selection(ranks)

    def selection_changed(self) -> None:
        n = len(self.view.sel_edges)
        if not self.chains:
            self.status.setText(tr('Ce volume n’a pas d’arête vive.'))
        else:
            self.status.setText(tr('{0} arête(s) choisie(s) sur {1}').format(n, len(self.chains)))

    def show_preview(self, on: bool) -> None:
        """Le volume tel qu'il sera ; les clics ne choisissent plus rien tant qu'on le regarde."""
        chosen = set(self.view.sel_edges)
        if not on:
            self.view.set_model(self.model)
            self.view.set_edge_chains([c.points for c in self.chains])
            self.view.set_edge_selection(chosen)
            return
        try:
            result = EB.apply(self.solid, self.values())
        except SO.SolidError as ex:
            self.status.setText(str(ex))
            self.preview_button.blockSignals(True)
            self.preview_button.setChecked(False)
            self.preview_button.blockSignals(False)
            return
        self.kept = chosen
        self.view.set_edge_chains([])
        self.view.sel_edges = chosen                     # gardées pour le retour
        self.view.set_model(SO.to_model([result]))
        self.view.sel_edges = chosen

    def accept(self) -> None:
        """Rien ne se ferme sur une erreur : les arêtes choisies ne sont pas perdues."""
        if self.preview_button.isChecked():
            self.preview_button.setChecked(False)
        try:
            EB.apply(self.solid, self.values())
        except SO.SolidError as ex:
            self.status.setText(str(ex))
            return
        super().accept()
