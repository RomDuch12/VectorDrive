"""Fenêtre des accrochages (F3, comme dans TypeEdit) : non bloquante, elle
reste ouverte à côté du dessin. Accrochage actif ou non, points accrochés
(nœuds, intersections, milieux, centres, quadrants, guides, contour,
grille), choix rapides, rayon d'attraction en pixels. Tout est relié aux
commandes du ruban : cocher ici ou là, c'est la même chose."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton,
                               QSpinBox, QVBoxLayout)

from ..i18n import tr

MODES = ('node', 'intersection', 'middle', 'center', 'centroid', 'quadrant', 'perpendicular', 'tangent',
         'extension', 'parallel', 'guide', 'nearest', 'grid')
TIPS = {'node': 'Extrémités et nœuds des contours', 'intersection': 'Croisements de deux contours',
        'middle': 'Milieu de chaque segment', 'center': 'Centre des arcs, des cercles et des objets',
        'quadrant': 'Points à 0°, 90°, 180° et 270° des cercles et des arcs',
        'centroid': 'Centre de gravité de la surface des contours fermés',
        'perpendicular': 'Pied de la perpendiculaire menée du dernier point cliqué',
        'tangent': 'Point de tangence depuis le dernier point cliqué sur un cercle ou un arc',
        'extension': 'Prolongement d\'un trait droit dont on a survolé le bout',
        'parallel': 'Parallèle, depuis le dernier point cliqué, au dernier trait droit survolé',
        'guide': 'Guides du dessin (et leurs croisements)',
        'nearest': 'N\'importe quel point d\'un contour (si rien d\'autre n\'est proche)',
        'grid': 'Nœuds de la grille (si rien d\'autre n\'est proche)'}


class SnapWindow(QDialog):
    vd_keep = True                  # réemployée (gardée par la fenêtre) : pas libérée à la fermeture

    def __init__(self, win):
        super().__init__(win, Qt.WindowType.Tool)
        self.win = win
        self.setWindowTitle(tr('Accrochages'))
        lay = QVBoxLayout(self)
        self.enabled = QCheckBox(tr('Accrochage actif (Maj+F3)'))
        f = self.enabled.font()
        f.setBold(True)
        self.enabled.setFont(f)
        self.enabled.toggled.connect(lambda on: win.A['snap'].setChecked(on))
        win.A['snap'].toggled.connect(self._sync_enabled)
        lay.addWidget(self.enabled)
        g = QGroupBox(tr('Accrocher aux'))
        grid = QGridLayout(g)
        self.boxes = {}
        for i, k in enumerate(MODES):
            act = win.A[f'snap_{k}']
            b = QCheckBox(act.text())
            b.setIcon(act.icon())
            b.setToolTip(tr(TIPS[k]))
            b.toggled.connect(lambda on, a=act: a.setChecked(on))
            act.toggled.connect(lambda on, bb=b: self._sync_box(bb, on))
            grid.addWidget(b, i // 2, i % 2)
            self.boxes[k] = b
        lay.addWidget(g)
        row = QHBoxLayout()
        row.addWidget(QLabel(tr('Choix rapide')))
        for label, modes in win.SNAP_PRESETS[:2] + ((tr('Aucun'), set()),):   # celui d'office, Tous, Aucun
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, m=set(modes): self.set_modes(m))
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(QLabel(tr('Rayon d\'attraction')))
        self.radius = QSpinBox()
        self.radius.setRange(2, 50)
        self.radius.setSuffix(' px')
        self.radius.setToolTip(tr('Distance au curseur, à l\'écran, sous laquelle un point est accroché'))
        self.radius.valueChanged.connect(self._radius)
        row.addWidget(self.radius)
        row.addStretch(1)
        lay.addLayout(row)
        hint = QLabel(tr('Ctrl+D / Ctrl+F : mode précédent / suivant'))
        hint.setStyleSheet('color: #868e96;')
        lay.addWidget(hint)
        self.sync()

    def _sync_enabled(self, on: bool) -> None:
        self.enabled.blockSignals(True)
        self.enabled.setChecked(on)
        self.enabled.blockSignals(False)

    @staticmethod
    def _sync_box(b, on: bool) -> None:
        b.blockSignals(True)
        b.setChecked(on)
        b.blockSignals(False)

    def sync(self) -> None:
        """Cases d'après les commandes et le canevas."""
        self._sync_enabled(self.win.A['snap'].isChecked())
        for k, b in self.boxes.items():
            self._sync_box(b, self.win.A[f'snap_{k}'].isChecked())
        self.radius.blockSignals(True)
        self.radius.setValue(int(self.win.canvas.snap_px))
        self.radius.blockSignals(False)

    def set_modes(self, modes: set) -> None:
        for k in MODES:
            self.win.A[f'snap_{k}'].setChecked(k in modes)
        if modes and not self.win.A['snap'].isChecked():
            self.win.A['snap'].setChecked(True)

    def _radius(self, v: int) -> None:
        self.win.canvas.snap_px = int(v)
        self.win.settings.setValue('accrochage/rayon', int(v))
