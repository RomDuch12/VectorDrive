"""Simulation d'enlèvement de matière : image ombrée des parcours cochés,
volume enlevé, profondeur atteinte, image enregistrable ; la matière qui
reste après une opération choisie, et ce qu'elle enlève."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QHBoxLayout,
                               QLabel, QPushButton, QScrollArea, QSlider, QVBoxLayout)

from ..cam import simulate
from ..i18n import tr


class SimDialog(QDialog):
    #: largeur de l'image à l'échelle 1 dans la fenêtre (pixels), et zooms du clic droit
    VIEW_WIDTH = 940
    ZOOMS = (1, 2, 4, 8)
    #: matière gardée après chaque opération pour « Matière après » (octets) ; au-delà, les plus anciennes sont refaites
    #: au besoin
    STATES_BYTES = 160 * 2 ** 20

    def __init__(self, parent, toolpaths, setup, stock=None, contours=(), on_relief=None, upto=None):
        """`upto` : identifiant d'opération — la matière qui reste après elle (« Matière après »)."""
        super().__init__(parent)
        self.on_relief = on_relief                       # poser l'objet relief sur le dessin
        self.stock = stock                               # brut placé : la matière part de son haut
        self.contours = list(contours)                   # le dessin : [points] (TE : contour théorique)
        self.zoom = 1
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        self.setWindowTitle(tr('Simulation de l\'usinage'))
        self.resize(980, 720)
        self.toolpaths, self.setup = toolpaths, setup
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel(tr('Pas de la simulation')))
        self.res = QDoubleSpinBox()
        self.res.setRange(0.0, 5.0)
        self.res.setDecimals(3)
        self.res.setSuffix(' mm')
        self.res.setSpecialValueText(tr('automatique'))
        try:
            from .. import portable
            from .options import value
            self.res.setValue(value(portable.settings(), 'fao/simulation_pas'))
        except Exception:                               # réglages illisibles : automatique
            pass
        row.addWidget(self.res)
        b = QPushButton(tr('Recalculer'))
        b.clicked.connect(self.run)
        row.addWidget(b)
        self.spans = simulate.op_spans(self.toolpaths)    # les opérations, dans l'ordre d'usinage
        self.after_label = QLabel(tr('Matière après'))
        self.after = QComboBox()
        self.after.addItem(tr('Toutes les opérations'))
        ops = {o.id: o for o in getattr(setup, 'operations', None) or ()}
        for n, (op_id, i, _j, _a, _b) in enumerate(self.spans, 1):
            self.after.addItem(f'{n}. {self._span_name(ops.get(op_id), i)}')
        self.after.setToolTip(tr('La matière qui reste après cette opération, pour les suivantes ; ce qu\'elle enlève, en vert'))
        last = [n for n, sp in enumerate(self.spans, 1) if upto is not None and sp[0] == upto]
        if last:                                         # une opération en plusieurs endroits : après le dernier
            self.after.setCurrentIndex(last[-1])
        several = len(self.spans) > 1 or bool(last)
        self.after.currentIndexChanged.connect(self.show_after)
        for w in (self.after_label, self.after):
            row.addWidget(w)
            if not several:                              # une seule opération : rien à choisir
                w.hide()
        row.addStretch(1)
        self.info = QLabel('')
        row.addWidget(self.info)
        lay.addLayout(row)
        self.view = QLabel()
        self.view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.view.installEventFilter(self)
        self.view.setToolTip(tr('Clic droit : agrandir ; Maj + clic droit : réduire'))
        sa = self.scroll = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setWidget(self.view)
        lay.addWidget(sa, 1)
        row = QHBoxLayout()
        row.addWidget(QLabel(tr('Profondeur de la vue')))
        self.level = QDoubleSpinBox()
        self.level.setDecimals(3)
        self.level.setSuffix(' mm')
        self.level.setToolTip(tr('À cette altitude, ce qui est enlevé apparaît en bleu ; à 0, le relief ombré'))
        self.level_slider = QSlider(Qt.Orientation.Horizontal)
        self.level_slider.setRange(0, 1000)
        self.level_slider.setMinimumWidth(180)
        self.level.valueChanged.connect(self._level_typed)
        self.level_slider.valueChanged.connect(self._level_moved)
        row.addWidget(self.level_slider)
        row.addWidget(self.level)
        self.show_theory = QCheckBox(tr('Théorique'))
        self.show_theory.setToolTip(tr('Le contour du dessin, en rouge, pour comparer l\'usinage au dessin'))
        self.show_theory.setEnabled(bool(self.contours))
        self.show_bottom = QCheckBox(tr('En fond'))
        self.show_bottom.setToolTip(tr('Le fond de gravure ressort en orange'))
        self.show_moves = QCheckBox(tr('Hors matière'))
        self.show_moves.setToolTip(tr('Les déplacements de l\'outil le long du parcours, même hors de la matière, en pointillés bleus'))
        self.show_cut = QCheckBox(tr('Cette opération'))
        self.show_cut.setToolTip(tr('Ce que l\'opération choisie dans « Matière après » enlève, en vert'))
        self.show_cut.setChecked(True)
        self.show_cut.setEnabled(False)
        if not several:
            self.show_cut.hide()
        for box in (self.show_theory, self.show_bottom, self.show_moves, self.show_cut):
            box.toggled.connect(self.refresh)
            row.addWidget(box)
        row.addStretch(1)
        lay.addLayout(row)
        row = QHBoxLayout()
        b = QPushButton(tr('Enregistrer l\'image…'))
        b.clicked.connect(lambda: self.save_image())
        row.addWidget(b)
        self.relief_button = QPushButton(tr('Poser en relief sur le dessin'))
        self.relief_button.setToolTip(tr('La matière simulée devient un objet relief du plan actif, à sa place sur le dessin'))
        self.relief_button.clicked.connect(lambda: self.lay_relief())
        self.relief_button.setVisible(on_relief is not None)
        row.addWidget(self.relief_button)
        row.addStretch(1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.reject)
        row.addWidget(bb)
        lay.addLayout(row)
        self.image = None
        self.cut, self.gone = None, 0.0                  # ce que l'opération choisie enlève : booléens de la grille, mm³
        self._states = {}
        self._laid = set()                               # les choix de « Matière après » déjà posés en relief
        self.run()

    def _span_name(self, op, i: int) -> str:
        if op is not None:
            from ..cam import model
            return op.name or tr(model.op_kinds().get(op.kind, op.kind))
        return getattr(self.toolpaths[i], 'name', '') or tr('Parcours {0}').format(i + 1)

    def run(self) -> None:
        from .progress import Cancelled, run
        try:
            self.full = run(self, tr('Simulation de l\'usinage'), simulate.simulate, self.toolpaths, self.setup,
                            res=self.res.value() or None, stock=self.stock)
        except Cancelled:
            self.info.setText(tr('Simulation annulée'))
            return
        self._states = {}                                # matière après chaque opération (rang → SimResult), sur cette grille
        self._laid = set()
        self.show_after()

    def _state(self, states: dict, full, k: int):
        """La matière après l'opération de rang k de « Matière après » (-1 : le brut ; la dernière : la simulation
        complète), reprise de la plus proche gardée avant elle. Les étapes calculées sont gardées dans `states` (dans la
        limite de STATES_BYTES, les plus récentes) : passer d'une opération à la suivante ne refait que celle-ci."""
        if k == len(self.spans) - 1:
            return full
        if k in states:
            states[k] = states.pop(k)                    # la plus récente en dernier
            return states[k]
        j = max((i for i in states if i < k), default=None)
        cur = states[j] if j is not None else simulate.blank(full)
        for b in range((j if j is not None else -1) + 1, k + 1):
            cur = simulate.advance(self.toolpaths, self.setup, cur, self.spans[b][3], self.spans[b][4])
            states[b] = cur
            while len(states) > 1 and sum(s.H.nbytes for s in states.values()) > self.STATES_BYTES:
                states.pop(next(iter(states)))
        return cur

    def _op_states(self, states: dict, full, k: int):
        """(matière après le rang k, ce que son opération a enlevé jusque-là : booléens de la grille, mm³) — tous ses
        rangs jusqu'à k quand des parcours d'une autre opération la coupent dans la liste."""
        op = self.spans[k][0]
        cut, gone = None, 0.0
        for b in range(k + 1):
            if b != k and (op is None or self.spans[b][0] != op):
                continue
            before, after = self._state(states, full, b - 1), self._state(states, full, b)
            m = before.H - after.H > 1e-6
            cut = m if cut is None else (cut | m)
            gone += after.removed - before.removed
        return self._state(states, full, k), cut, gone

    def show_after(self, *_a) -> None:
        """La matière après l'opération choisie dans « Matière après » (toutes : la simulation complète), ce que
        celle-ci enlève en vert ; sans refaire la simulation complète. Annulée : la simulation complète, et le message."""
        full = getattr(self, 'full', None)
        if full is None:
            return
        k = self.after.currentIndex() - 1
        r, self.cut, self.gone, cancelled = full, None, 0.0, False
        if 0 <= k < len(self.spans):
            from .progress import Cancelled, run
            try:
                r, self.cut, self.gone = run(self, tr('Simulation de l\'usinage'), self._op_states, self._states, full, k)
            except Cancelled:
                cancelled = True
                self.after.blockSignals(True)
                self.after.setCurrentIndex(0)
                self.after.blockSignals(False)
        self.show_cut.setEnabled(self.cut is not None)
        self.result = r
        deepest = max(0.0, -float(r.deepest))
        self.level.blockSignals(True)
        self.level.setRange(-deepest, 0.0)
        self.level.setSingleStep(max(0.001, deepest / 50))
        self.level.blockSignals(False)
        low = self.level.minimum()                       # la valeur ramenée dans la plage : le curseur suit
        self.level_slider.blockSignals(True)
        self.level_slider.setValue(round(1000 * self.level.value() / low) if low < 0 else 0)
        self.level_slider.blockSignals(False)
        self.refresh()
        self.relief_button.setEnabled(self.after.currentIndex() not in self._laid)
        if self.cut is None:
            self.info.setText(tr('Pas {0} mm — volume enlevé {1} mm³ — profondeur {2} mm').format(
                f'{r.res:.3f}', f'{r.removed:.1f}', f'{deepest:.3f}'))
        else:
            self.info.setText(tr('Pas {0} mm — après « {1} » : volume enlevé {2} mm³, dont {3} mm³ par cette opération — '
                                 'profondeur {4} mm').format(f'{r.res:.3f}', self.after.currentText(), f'{r.removed:.1f}',
                                                             f'{self.gone:.1f}', f'{deepest:.3f}'))
        if cancelled:
            self.info.setText(tr('Simulation annulée') + ' — ' + self.info.text())
        r = full                                         # les alertes : de tout le programme
        alerts = []
        if getattr(r, 'collisions', None):
            alerts.append(tr('{0} collision(s) du porte-outil : {1}').format(
                len(r.collisions), next(w for w in r.warnings if w.startswith('collision : porte-outil'))))
        if getattr(r, 'rapid_hits', None):
            alerts.append(tr('{0} déplacement(s) rapide(s) dans la matière : {1}').format(
                len(r.rapid_hits), next(w for w in r.warnings if w.startswith('collision : déplacement rapide'))))
        if alerts:
            self.info.setText('\n'.join([self.info.text()] + alerts))
            self.info.setStyleSheet('color: #c0392b; font-weight: bold;')
        else:
            self.info.setStyleSheet('')

    def lay_relief(self):
        """La matière simulée, en objet relief. Rend l'objet posé (None : rien de creusé)."""
        if self.on_relief is None or getattr(self, 'result', None) is None:
            return None
        img = simulate.to_relief(self.result, name=tr('Simulation'))
        if img is None:
            self.info.setText(tr('Rien de creusé : pas de relief à poser.'))
            return None
        self.on_relief(img)
        self.relief_button.setEnabled(False)             # une fois par état : un second serait le même
        self._laid.add(self.after.currentIndex())
        return img

    def _level_typed(self, value: float) -> None:
        low = self.level.minimum()
        self.level_slider.blockSignals(True)
        self.level_slider.setValue(round(1000 * value / low) if low < 0 else 0)
        self.level_slider.blockSignals(False)
        self.refresh()

    def _level_moved(self, pos: int) -> None:
        self.level.blockSignals(True)
        self.level.setValue(self.level.minimum() * pos / 1000)
        self.level.blockSignals(False)
        self.refresh()

    def _lines(self, image, painter, lines, pen) -> None:
        """Des traits en mm, sur l'image de la simulation (Y vers le haut)."""
        r = self.result
        k = image.width() / r.H.shape[1] / r.res
        h = image.height()
        painter.setPen(pen)
        for pts in lines:
            if len(pts) >= 2:
                painter.drawPolyline(QPolygonF([QPointF((p[0] - r.x0) * k, h - (p[1] - r.y0) * k) for p in pts]))

    def _tool_lines(self) -> list:
        """Le chemin de l'outil, parcours par parcours : un trait par parcours."""
        from ..cam.model import arc_points
        out = []
        k = self.after.currentIndex() - 1
        upto = self.spans[k][2] if 0 <= k < len(self.spans) else len(self.toolpaths)
        for tp in self.toolpaths[:upto]:                 # jusqu'à l'opération choisie
            pts = []
            for m in tp.moves:
                if m.is_arc and pts:
                    pts += arc_points(pts[-1], m, 0.05)
                else:
                    pts.append((m.x, m.y, m.z))
            out.append(pts)
        return out

    def refresh(self) -> None:
        """L'image, selon les réglages : sans refaire la simulation."""
        if getattr(self, 'result', None) is None:
            return
        level = self.level.value()
        cut = getattr(self, 'cut', None)
        image = simulate.render(self.result, width=1600, level=level if level < 0 else None,
                                bottom=self.show_bottom.isChecked(), mark=cut if self.show_cut.isChecked() else None)
        if self.show_moves.isChecked() or (self.show_theory.isChecked() and self.contours):
            image = image.convertToFormat(QImage.Format.Format_RGB32)
            p = QPainter(image)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            if self.show_moves.isChecked():
                self._lines(image, p, self._tool_lines(), QPen(QColor('#1c7ed6'), 1.5, Qt.PenStyle.DashLine))
            if self.show_theory.isChecked():
                self._lines(image, p, self.contours, QPen(QColor('#e03131'), 2.0))
            p.end()
        self.image = image
        self.show_image()

    def show_image(self) -> None:
        pm = QPixmap.fromImage(self.image)
        want = self.VIEW_WIDTH * self.zoom
        if pm.width() != want:
            pm = pm.scaledToWidth(want, Qt.TransformationMode.SmoothTransformation)
        self.view.setPixmap(pm)

    def zoom_at(self, x: float, y: float, out: bool = False) -> None:
        """Clic droit (TE) : plus grand, ou plus petit avec Maj, en gardant le point cliqué au centre de la fenêtre."""
        i = self.ZOOMS.index(self.zoom) + (-1 if out else 1)
        if not 0 <= i < len(self.ZOOMS):
            return
        ratio = self.ZOOMS[i] / self.zoom
        self.zoom = self.ZOOMS[i]
        self.show_image()
        self.view.adjustSize()
        bar_x, bar_y = self.scroll.horizontalScrollBar(), self.scroll.verticalScrollBar()
        bar_x.setValue(round(x * ratio - self.scroll.viewport().width() / 2))
        bar_y.setValue(round(y * ratio - self.scroll.viewport().height() / 2))

    def eventFilter(self, obj, ev) -> bool:
        if obj is self.view and ev.type() == QEvent.Type.MouseButtonPress and ev.button() == Qt.MouseButton.RightButton:
            self.zoom_at(ev.position().x(), ev.position().y(), bool(ev.modifiers() & Qt.KeyboardModifier.ShiftModifier))
            return True
        return super().eventFilter(obj, ev)

    def done(self, r: int) -> None:
        self._states = {}                                # la matière gardée par opération : libérée à la fermeture
        super().done(r)

    def save_image(self, path: str | None = None) -> None:
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, tr('Image de la simulation'), 'simulation.png', 'PNG (*.png)')
        if path and self.image is not None:
            self.image.save(path)
