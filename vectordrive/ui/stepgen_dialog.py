"""Design STEP : générer des pièces STEP en vraies faces (`core.stepgen`) —
familles rangées par catégorie (visserie, transmission, brut, moule),
paramètres, aperçu ombré qu'on fait tourner (glisser), volume, masse et
encombrement ; enregistrer dans le dépôt STEP (la pièce, ou toute la gamme
de la famille), ajouter au dessin comme volume (la description de la pièce
gardée avec lui), ouvrir le STEP dans un onglet.

Le dépôt : un dossier choisi une fois (réglage `step/depot`), une
sous-dossier par catégorie.
"""
from __future__ import annotations

import math
import pathlib

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QSpinBox, QSplitter, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from ..core import brep as B
from ..core import stepgen as G
from ..i18n import tr

DEPOT_KEY = 'step/depot'
#: masse volumique pour la masse affichée (g/cm³) selon la couleur de la pièce
DENSITY = {G.STEEL: 7.85, G.ZINC: 7.85, G.BLACK: 7.85, G.BRASS: 8.5, G.ALU: 2.7}
MATERIAL = {G.STEEL: 'acier', G.ZINC: 'acier', G.BLACK: 'acier', G.BRASS: 'laiton', G.ALU: 'aluminium'}


def depot(settings) -> str:
    """Dossier du dépôt STEP (réglage ; par défaut Documents/VectorDrive/STEP)."""
    v = settings.value(DEPOT_KEY, '') if settings is not None else ''
    return str(v) if v else str(pathlib.Path.home() / 'Documents' / 'VectorDrive' / 'STEP')


def param_widget(p, changed):
    """Le champ du paramètre `p` d'un générateur (liste, entier ou nombre) à sa valeur par défaut ; `changed`
    appelé à chaque valeur finie (pas à chaque chiffre tapé)."""
    if p.kind == 'choice':
        w = QComboBox()
        for c in p.choices:
            w.addItem(tr(G.CHOICE_LABELS.get(c, c)) if isinstance(c, str) else f'{c:g}', c)
        w.setCurrentIndex(max(0, list(p.choices).index(p.default) if p.default in p.choices else 0))
        w.currentIndexChanged.connect(changed)
    elif p.kind == 'int':
        w = QSpinBox()
        w.setRange(int(p.lo), int(p.hi))
        w.setKeyboardTracking(False)
        w.setValue(int(p.default))
        w.valueChanged.connect(changed)
    else:
        w = QDoubleSpinBox()
        w.setDecimals(2)
        w.setRange(p.lo, p.hi)
        w.setKeyboardTracking(False)
        w.setValue(float(p.default))
        w.setSuffix(f' {p.unit}' if p.unit else '')
        w.valueChanged.connect(changed)
    return w


def set_widget(w, value) -> None:
    """La valeur montrée par un champ de `param_widget`."""
    if isinstance(w, QComboBox):
        w.setCurrentIndex(w.findData(value))
    else:
        w.setValue(value)


def widget_value(w):
    """La valeur d'un champ de `param_widget`."""
    return w.currentData() if isinstance(w, QComboBox) else w.value()


class Preview(QWidget):
    """Aperçu ombré (projection orthogonale, faces du fond retirées, peintes de la plus loin à la plus
    proche) ; glisser : tourner."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tris = None
        self.colors = []
        self.yaw, self.pitch = math.radians(-35.0), math.radians(28.0)
        self._press = None
        self.message = ''
        self.setMinimumSize(260, 260)

    def set_bodies(self, meshes) -> None:
        """[(triangles (n, 3, 3), couleur)…] ; [] : aperçu vide."""
        import numpy as np
        meshes = [(m, c) for m, c in meshes if len(m)]
        if meshes:
            T = np.concatenate([m for m, _c in meshes])
            C = np.concatenate([np.tile(c, (len(m), 1)) for m, c in meshes])
            size = float(np.ptp(T.reshape(-1, 3), axis=0).max()) or 1.0
            for _ in range(3):                           # grands triangles recoupés : l'ordre de peinture tient
                e = np.linalg.norm(T - T[:, [1, 2, 0]], axis=2).max(axis=1)
                big = e > size / 10
                if not big.any():
                    break
                a, b_, c = T[big, 0], T[big, 1], T[big, 2]
                ab, bc, ca = (a + b_) / 2, (b_ + c) / 2, (c + a) / 2
                T = np.concatenate([T[~big], np.stack([a, ab, ca], 1), np.stack([ab, b_, bc], 1),
                                    np.stack([ca, bc, c], 1), np.stack([ab, bc, ca], 1)])
                C = np.concatenate([C[~big]] + [C[big]] * 4)
            self.tris, self.colors = T, C
        else:
            self.tris, self.colors = None, []
        self.update()

    def mousePressEvent(self, ev):
        self._press = (ev.position(), self.yaw, self.pitch)

    def mouseMoveEvent(self, ev):
        if self._press is None:
            return
        p0, yaw, pitch = self._press
        d = ev.position() - p0
        self.yaw = yaw + d.x() * 0.01
        self.pitch = max(-1.5, min(1.5, pitch + d.y() * 0.01))
        self.update()

    def mouseReleaseEvent(self, ev):
        self._press = None

    def paintEvent(self, ev):
        p = QPainter(self)
        try:
            self._paint(p)
        finally:
            p.end()

    def _paint(self, p):
        import numpy as np
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.fillRect(self.rect(), self.palette().base())
        if self.tris is None or not len(self.tris):
            p.setPen(self.palette().text().color())
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.message)
            return
        T = self.tris
        cy, sy, cp, sp = math.cos(self.yaw), math.sin(self.yaw), math.cos(self.pitch), math.sin(self.pitch)
        Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
        Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
        R = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]]) @ Rx @ Rz         # écran : x à droite, y en haut, z vers l'œil
        V = T.reshape(-1, 3) @ R.T
        V = V.reshape(-1, 3, 3)
        n = np.cross(V[:, 1] - V[:, 0], V[:, 2] - V[:, 0])
        L = np.linalg.norm(n, axis=1)
        keep = (n[:, 2] > 0) & (L > 1e-12)
        if not keep.any():
            return
        V, n, L, C = V[keep], n[keep], L[keep], np.asarray(self.colors)[keep]
        lo, hi = V.reshape(-1, 3).min(axis=0), V.reshape(-1, 3).max(axis=0)
        size = max(hi[0] - lo[0], hi[1] - lo[1], 1e-9)
        k = 0.85 * min(self.width(), self.height()) / size
        mx, my = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
        light = np.array([-0.35, 0.45, 0.82])
        light /= np.linalg.norm(light)
        shade = 0.35 + 0.65 * np.clip((n / L[:, None]) @ light, 0, 1)
        order = np.argsort(V[:, :, 2].mean(axis=1))
        w2, h2 = self.width() / 2, self.height() / 2
        for i in order:
            c = C[i] * shade[i]
            col = QColor.fromRgbF(*(float(min(1.0, x)) for x in c))
            p.setPen(QPen(col, 0.8))
            p.setBrush(col)
            p.drawPolygon(QPolygonF([QPointF(w2 + k * (x - mx), h2 - k * (y - my)) for x, y, _z in V[i]]))


class StepGenDialog(QDialog):
    """Fenêtre des générateurs ; `win` : la fenêtre principale (ou None : essais, dossier donné)."""

    def __init__(self, win=None, category: str | None = None, family: str | None = None, folder: str | None = None):
        super().__init__(win)
        self.win = win
        self.settings = getattr(win, 'settings', None)
        self.folder = folder or depot(self.settings)
        self.setWindowTitle(tr('Design STEP — générer une pièce'))
        self.resize(1080, 640)
        self.key = None
        self.widgets: dict = {}
        self.bodies: list = []
        self.error = ''
        self.saved: list = []
        lay = QVBoxLayout(self)
        split = QSplitter(Qt.Orientation.Horizontal, self)
        lay.addWidget(split, 1)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(250)
        self._items = {}
        for cat in G.CATEGORIES:
            top = QTreeWidgetItem([tr(cat)])
            top.setData(0, Qt.ItemDataRole.UserRole, None)
            top.setFlags(top.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.tree.addTopLevelItem(top)
            for key, f in G.FAMILIES.items():
                if f.category == cat:
                    it = QTreeWidgetItem([tr(f.label)])
                    it.setData(0, Qt.ItemDataRole.UserRole, key)
                    it.setToolTip(0, f'{tr(f.label)} — {tr(f.standard)}' if f.standard else tr(f.label))
                    top.addChild(it)
                    self._items[key] = it
            top.setExpanded(category is None or category == cat)
        self.tree.currentItemChanged.connect(self._tree_changed)
        split.addWidget(self.tree)
        mid = QWidget()
        ml = QVBoxLayout(mid)
        self.title = QLabel()
        self.title.setStyleSheet('font-weight: bold')
        self.title.setWordWrap(True)
        ml.addWidget(self.title)
        self.form_host = QWidget()
        self.form = QFormLayout(self.form_host)
        ml.addWidget(self.form_host)
        self.note = QLabel()
        self.note.setWordWrap(True)
        ml.addWidget(self.note)
        ml.addStretch(1)
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        ml.addWidget(self.info)
        row = QHBoxLayout()
        self.folder_label = QLabel()
        self.folder_label.setWordWrap(True)
        row.addWidget(self.folder_label, 1)
        b = QPushButton(tr('Dossier…'))
        b.setToolTip(tr('Choisir le dossier du dépôt STEP'))
        b.clicked.connect(lambda: self.choose_folder())
        row.addWidget(b)
        ml.addLayout(row)
        split.addWidget(mid)
        self.preview = Preview()
        split.addWidget(self.preview)
        split.setSizes([260, 400, 420])
        buttons = QHBoxLayout()
        self.b_save = QPushButton(tr('Enregistrer le STEP'))
        self.b_save.setToolTip(tr('La pièce en STEP dans le dépôt (sous-dossier de sa catégorie)'))
        self.b_save.clicked.connect(lambda: self.save())
        self.b_series = QPushButton(tr('Toute la gamme'))
        self.b_series.setToolTip(tr('Toutes les tailles et longueurs courantes de la famille, un fichier par pièce'))
        self.b_series.clicked.connect(lambda: self.save_series())
        self.b_open = QPushButton(tr('Ouvrir le STEP'))
        self.b_open.setToolTip(tr('Enregistrer la pièce et l\'ouvrir dans un onglet (vue 3D, placement, usinage)'))
        self.b_open.clicked.connect(lambda: self.open_step())
        self.b_add = QPushButton(tr('Ajouter au dessin'))
        self.b_add.setToolTip(tr('La pièce comme volume du dessin, au centre de la plaque'))
        self.b_add.clicked.connect(lambda: self.add_to_drawing())
        close = QPushButton(tr('Fermer'))
        close.clicked.connect(self.reject)
        for w in (self.b_save, self.b_series, self.b_open, self.b_add):
            buttons.addWidget(w)
        buttons.addStretch(1)
        buttons.addWidget(close)
        lay.addLayout(buttons)
        self.b_add.setEnabled(win is not None)
        self.b_open.setEnabled(win is not None)
        self.replace_item = None                           # pièce du dessin remplacée par « Ajouter au dessin »
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self.refresh)
        for b in self.findChildren(QPushButton):          # Entrée dans un champ : pas de bouton par défaut
            b.setAutoDefault(False)
            b.setDefault(False)
        self._show_folder()
        first = family if family in G.FAMILIES else next(
            (k for k, f in G.FAMILIES.items() if category is None or f.category == category), next(iter(G.FAMILIES)))
        self.select_family(first)

    # --- famille et paramètres ----------------------------------------------------------------------------
    def _tree_changed(self, cur, _prev):
        key = cur.data(0, Qt.ItemDataRole.UserRole) if cur is not None else None
        if key and key != self.key:
            self.select_family(key)

    def select_family(self, key: str) -> None:
        f = G.FAMILIES[key]
        self.key = key
        it = self._items[key]
        if self.tree.currentItem() is not it:
            self.tree.blockSignals(True)
            self.tree.setCurrentItem(it)
            it.parent().setExpanded(True)
            self.tree.blockSignals(False)
        self.title.setText(f'{tr(f.label)}' + (f' — {tr(f.standard)}' if f.standard else ''))
        self.note.setText(tr(f.note) if f.note else '')
        while self.form.rowCount():
            self.form.removeRow(0)
        self.widgets = {}
        for p in f.params:
            w = param_widget(p, self._changed)
            self.widgets[p.key] = w
            self.form.addRow(tr(p.label), w)
        self.b_series.setEnabled(f.series is not None)
        self.refresh()

    def set_value(self, key: str, value) -> None:
        """Un paramètre de la famille montrée (essais, gamme)."""
        set_widget(self.widgets[key], value)
        self.refresh()

    def _changed(self, *_):
        self._timer.start()

    def _sync(self) -> None:
        """Une modification en attente (minuterie) reconstruite avant d'agir : jamais d'action sur l'ancienne
        pièce."""
        if self._timer.isActive():
            self.refresh()

    def current_values(self) -> dict:
        """Les valeurs montrées, contrôlées (GenError)."""
        v = {}
        for k, w in self.widgets.items():
            v[k] = widget_value(w)
        return G.values(self.key, **v)

    def refresh(self) -> None:
        """Pièce reconstruite : aperçu, volume, masse, encombrement ; erreur dite."""
        self._timer.stop()
        try:
            v = self.current_values()
            self.bodies = G.build(self.key, v)
            meshes = [(B.mesh(b, n_arc=48, bands=6), b.color) for b in self.bodies]
            self.error = ''
        except (G.GenError, B.BrepError) as ex:
            self.bodies, meshes, self.error = [], [], str(ex)
        self.preview.message = self.error
        self.preview.set_bodies(meshes)
        for w in (self.b_save, self.b_open, self.b_add):
            w.setEnabled(not self.error and (w is self.b_save or self.win is not None))
        if self.error:
            self.info.setText(tr('Impossible : {0}').format(self.error))
            return
        b = self.bodies[0]
        x0, y0, z0, x1, y1, z1 = b.bounds()
        vol = sum(B.volume(x) for x in self.bodies) / 1000.0
        rho = DENSITY.get(tuple(b.color), 7.85)
        self.info.setText(tr('{0}.step\nVolume {1:.3f} cm³ — masse {2:.1f} g ({3})\nEncombrement {4:.2f} × {5:.2f} × '
                             '{6:.2f} mm').format(G.file_name(self.key, v), vol, vol * rho,
                                                  tr(MATERIAL.get(tuple(b.color), 'acier')), x1 - x0, y1 - y0, z1 - z0))

    # --- dépôt --------------------------------------------------------------------------------------------
    def _show_folder(self) -> None:
        self.folder_label.setText(tr('Dépôt : {0}').format(self.folder))

    def choose_folder(self, path: str | None = None) -> str | None:
        if path is None:
            path = QFileDialog.getExistingDirectory(self, tr('Dossier du dépôt STEP'), self.folder)
            if not path:
                return None
        self.folder = str(path)
        if self.settings is not None:
            self.settings.setValue(DEPOT_KEY, self.folder)
        self._show_folder()
        return self.folder

    def target(self) -> pathlib.Path:
        """Fichier de la pièce montrée dans le dépôt."""
        f = G.FAMILIES[self.key]
        return pathlib.Path(self.folder) / f.category / f'{G.file_name(self.key, self.current_values())}.step'

    def save(self, confirm: bool = True) -> str | None:
        """La pièce en STEP dans le dépôt ; rend le chemin (None : impossible ou refusé)."""
        self._sync()
        if self.error:
            return None
        try:
            path = self.target()
        except ValueError as ex:
            QMessageBox.warning(self, tr('Enregistrer le STEP'), str(ex))
            return None
        if path.exists() and confirm and QMessageBox.question(
                self, tr('Enregistrer le STEP'), tr('{0} existe déjà. Le remplacer ?').format(path.name)) \
                != QMessageBox.StandardButton.Yes:
            return None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            G.write(self.key, self.current_values(), path)
        except (OSError, ValueError) as ex:
            QMessageBox.warning(self, tr('Enregistrer le STEP'), str(ex))
            return None
        self.saved.append(str(path))
        self.info.setText(self.info.text() + '\n' + tr('Enregistré : {0}').format(path))
        return str(path)

    def save_series(self, ask: bool = True) -> list:
        """Toute la gamme de la famille dans le dépôt (sous-dossier de la famille) ; rend les fichiers."""
        f = G.FAMILIES[self.key]
        if f.series is None:
            return []
        n = len(f.series())
        out = pathlib.Path(self.folder) / f.category / G.folder_name(self.key)
        there = len(list(out.glob('*.step'))) if out.is_dir() else 0
        question = tr('{0} fichiers STEP dans {1} ?').format(n, out)
        if there:
            question += '\n' + tr('Les {0} fichiers STEP déjà dans ce dossier sont remplacés s\'ils ont le même '
                                   'nom.').format(there)
        if ask and QMessageBox.question(self, tr('Toute la gamme'), question) != QMessageBox.StandardButton.Yes:
            return []
        from .progress import Cancelled, run
        try:
            files = run(self, tr('Toute la gamme'), G.write_series, self.key, out) if self.win is not None \
                else G.write_series(self.key, out)
        except Cancelled:
            return []
        except (OSError, ValueError) as ex:
            QMessageBox.warning(self, tr('Toute la gamme'), str(ex))
            return []
        self.saved += files
        self.info.setText(tr('{0} fichiers enregistrés dans {1}').format(len(files), out))
        return files

    # --- vers le dessin -----------------------------------------------------------------------------------
    def edit_item(self, item) -> bool:
        """La pièce `item` du dessin (ajoutée par les générateurs : `extra['stepgen']`) reprise : sa famille et
        ses valeurs montrées, « Remplacer dans le dessin » au lieu d'« Ajouter au dessin ». Faux si ce n'est
        pas une pièce générée connue."""
        st = getattr(item, 'extra', {}).get('stepgen') if item is not None else None
        if not isinstance(st, dict) or st.get('key') not in G.FAMILIES:
            return False
        self.select_family(st['key'])
        known = {p.key for p in G.FAMILIES[st['key']].params}
        for k, v in dict(st.get('values') or {}).items():
            if k in known:
                self.set_value(k, v)
        self._sync()
        self.replace_item = item
        self._show_replace()
        return True

    def _show_replace(self) -> None:
        if self.replace_item is not None:
            self.b_add.setText(tr('Remplacer dans le dessin'))
            self.b_add.setToolTip(tr('La pièce modifiée à la place de celle du dessin (même milieu en X et Y, '
                                     'même dessous) ; annulable'))
        else:
            self.b_add.setText(tr('Ajouter au dessin'))
            self.b_add.setToolTip(tr('La pièce comme volume du dessin, au centre de la plaque'))

    def _replaced(self):
        """La pièce à remplacer si elle est toujours dans le dessin (premier niveau d'un calque), sinon None."""
        it = self.replace_item
        if it is None or self.win is None:
            return None
        if not any(x is it for L in self.win.canvas.doc.layers for x in L.items):
            self.replace_item = None                       # supprimée, annulée, groupée : ajoutée à neuf
            self._show_replace()
            return None
        return it

    def add_to_drawing(self) -> list:
        """La pièce en volume(s) du dessin, le milieu de son encombrement au centre de la plaque, posée sur
        Z = 0 — ou à la place de la pièce reprise (`edit_item`) : même milieu en X et Y, même dessous ; la
        description gardée (`stepgen`, `at` : la translation appliquée)."""
        import numpy as np
        from ..core import solids as SO
        self._sync()
        if self.error or self.win is None or not self.win._solids_ready():
            return []
        doc = self.win.canvas.doc
        plate = doc.plate
        cx, cy = (plate.x + plate.width / 2, plate.y + plate.height / 2) if plate is not None else (0.0, 0.0)
        z0 = 0.0
        old = self._replaced()
        try:
            if old is not None:                            # à la place de la pièce reprise, où qu'on l'ait mise
                x0, y0, z0, x1, y1, _z1 = SO.of_item(old).bounds()
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            v = self.current_values()
            meshes = [B.mesh(b) for b in self.bodies]
            P = np.concatenate([m.reshape(-1, 3) for m in meshes])
            lo, hi = P.min(axis=0), P.max(axis=0)
            at = [cx - (lo[0] + hi[0]) / 2, cy - (lo[1] + hi[1]) / 2, z0 - lo[2]]
            sols = []
            for b, m in zip(self.bodies, meshes):
                s = SO.from_triangles(m + np.asarray(at), b.name)
                s.color = tuple(b.color)
                sols.append(s)
        except (ValueError, RuntimeError) as ex:              # GenError, BrepError, SolidError
            QMessageBox.warning(self, tr('Ajouter au dessin'), tr('Impossible : {0}').format(ex))
            return []
        new = self.win._put_solids(sols, replace=[old] if old is not None else ())
        for it in new:
            it.extra['stepgen'] = {'key': self.key, 'values': dict(v), 'at': [float(x) for x in at]}
        if old is not None and new:
            self.replace_item = new[0]                     # modifiée encore : remplacée encore
        return new

    def open_step(self) -> str | None:
        """La pièce enregistrée puis ouverte dans un onglet, vue 3D."""
        if self.win is None:
            return None
        self._sync()
        if self.error:
            return None
        try:
            path = self.target()
        except ValueError as ex:
            QMessageBox.warning(self, tr('Ouvrir le STEP'), str(ex))
            return None
        if not path.exists():
            path = self.save()
            if path is None:
                return None
        if not self.win.open_path(str(path)):
            return None
        self.win.set_view_mode('3d')
        self.accept()
        return str(path)
