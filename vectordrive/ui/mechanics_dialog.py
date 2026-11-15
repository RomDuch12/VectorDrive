"""Fenêtre « Mécanismes » de la vue 3D (core.mechanics) : repérage des
contacts et des liaisons entre les corps de la pièce (réglages), mouvement
libre de chaque corps (course, sens, animé ou non) et animation dans la
vue 3D — curseur fermé → ouvert, lecture en va-et-vient ; contrôle des
collisions sur la course. Fenêtre non modale : la vue se tourne pendant
l'animation. Les réglages du repérage et ceux de chaque mouvement (animé,
course, sens) sont gardés avec le dessin (`doc.extra['mecanismes']`), pour
cette pièce (mêmes corps)."""
from __future__ import annotations

from dataclasses import replace

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout,
                               QHeaderView, QLabel, QPushButton, QSlider, QTableWidget, QTableWidgetItem,
                               QVBoxLayout)

from ..core import mechanics as M
from ..i18n import tr

#: pas de l'animation (ms) et avancement par pas
TICK_MS = 40
TICK_STEP = 0.02
#: réglages gardés avec le dessin
KEY = 'mecanismes'
#: positions contrôlées sur la course (collisions)
CLASH_STEPS = 24


def _dir_text(v) -> str:
    v = np.round(np.asarray(v, dtype=float), 3) + 0.0
    names = {(1, 0, 0): '+X', (-1, 0, 0): '−X', (0, 1, 0): '+Y', (0, -1, 0): '−Y', (0, 0, 1): '+Z', (0, 0, -1): '−Z'}
    key = tuple(int(round(c)) if abs(abs(c) - 1) < 1e-3 or abs(c) < 1e-3 else 9 for c in v)
    if key in names:
        return names[key]
    return '(' + ', '.join(f'{c:.2f}'.replace('.', ',') for c in v) + ')'


class MechanicsDialog(QDialog):
    def __init__(self, panel):
        super().__init__(panel)
        self.setWindowTitle(tr('Mécanismes'))
        self.panel = panel
        self.view = panel.view
        self.model = self.view.model
        self.motions: list = []
        self.enabled: dict = {}
        self.k = 0.0
        self.direction = 1.0
        self.auto_amount: dict = {}                      # course repérée de chaque corps (avant réglage)
        self.mans = None                                 # volumes fermés des corps (au premier contrôle)
        self.failed: dict = {}
        self.doc = self._doc()                           # le dessin de la pièce (la fenêtre reste ouverte)
        self.saved = self._load()
        lay = QVBoxLayout(self)
        box = QGroupBox(tr('Repérage'))
        f = QFormLayout(box)
        st = M.Settings(**self.saved.get('settings', {}))
        self.tol = self._spin(st.tol, 3, 0.0, 10.0, tr('Écart toléré entre deux faces en contact (jeu du plan de joint)'))
        self.angle = self._spin(st.angle, 2, 0.01, 10.0, tr('Écart toléré entre deux directions'))
        self.min_area = self._spin(st.min_area, 2, 0.0, 1e6, tr('Recouvrement minimal d\'un contact plan'))
        self.clearance = self._spin(st.clearance, 3, 0.0, 5.0, tr('Jeu toléré entre deux cylindres (ajustement)'))
        self.fixed = QComboBox()
        self.fixed.addItem(tr('Le plus gros'), -1)
        for b in range(self.model.body_count()):
            self.fixed.addItem(self.model.body_name(b), b)
        self.fixed.setCurrentIndex(max(0, self.fixed.findData(st.fixed)))
        self.travel = self._spin(st.travel, 1, 0.0, 10000.0, tr('Course des translations ; 0 : de quoi dégager le corps'))
        self.travel.setSpecialValueText(tr('auto'))
        self.turn = self._spin(st.turn, 1, 0.0, 360.0, tr('Rotation des pivots'))
        for label, w in ((tr('Contact : écart (mm)'), self.tol), (tr('Directions : écart (°)'), self.angle),
                         (tr('Contact plan : recouvrement mini (mm²)'), self.min_area),
                         (tr('Cylindres : jeu (mm)'), self.clearance), (tr('Corps fixe'), self.fixed),
                         (tr('Course (mm)'), self.travel), (tr('Rotation des pivots (°)'), self.turn)):
            f.addRow(label, w)
        b = QPushButton(tr('Repérer'))
        b.clicked.connect(lambda: self.detect())
        f.addRow(b)
        lay.addWidget(box)
        lay.addWidget(QLabel(tr('Liaisons')))
        self.joints_table = QTableWidget(0, 4)
        self.joints_table.setHorizontalHeaderLabels([tr('Corps'), tr('Avec'), tr('Liaison'), tr('Direction')])
        self.joints_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.joints_table.verticalHeader().setVisible(False)
        self.joints_table.setMaximumHeight(150)
        lay.addWidget(self.joints_table)
        lay.addWidget(QLabel(tr('Mouvements')))
        self.moves_table = QTableWidget(0, 5)
        self.moves_table.setHorizontalHeaderLabels([tr('Animé'), tr('Corps'), tr('Mouvement'), tr('Course'),
                                                    tr('Inverser')])
        self.moves_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.moves_table.verticalHeader().setVisible(False)
        self.moves_table.setMaximumHeight(170)
        lay.addWidget(self.moves_table)
        row = QHBoxLayout()
        self.play = QPushButton(tr('Animer'))
        self.play.setCheckable(True)
        self.play.toggled.connect(self._play)
        row.addWidget(self.play)
        row.addWidget(QLabel(tr('Fermé')))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.valueChanged.connect(lambda v: self.set_progress(v / 100.0, from_slider=True))
        row.addWidget(self.slider, 1)
        row.addWidget(QLabel(tr('Ouvert')))
        lay.addLayout(row)
        row = QHBoxLayout()
        b = QPushButton(tr('Contrôler les collisions'))
        b.setToolTip(tr('Les corps, fermés en volumes, déplacés pas à pas sur la course : volume commun = '
                        'interpénétration'))
        b.clicked.connect(lambda: self.check_collisions())
        row.addWidget(b)
        b = QPushButton(tr('Course jusqu\'à la butée'))
        b.setToolTip(tr('Chaque mouvement seul : sa course réduite à ce qu\'il parcourt avant de heurter un autre '
                        'corps'))
        b.clicked.connect(lambda: self.stop_at_collisions())
        row.addWidget(b)
        self.clash_label = QLabel()
        self.clash_label.setWordWrap(True)
        row.addWidget(self.clash_label, 1)
        lay.addLayout(row)
        self.status = QLabel()
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        self.timer = QTimer(self)
        self.timer.setInterval(TICK_MS)
        self.timer.timeout.connect(self._tick)
        self.detect(store=False)                         # ouvrir la fenêtre ne modifie pas le dessin

    def _spin(self, v, dec, lo, hi, tip):
        w = QDoubleSpinBox()
        w.setDecimals(dec)
        w.setRange(lo, hi)
        w.setValue(v)
        w.setToolTip(tip)
        return w

    def settings(self) -> M.Settings:
        return M.Settings(tol=self.tol.value(), angle=self.angle.value(), min_area=self.min_area.value(),
                          clearance=self.clearance.value(), fixed=int(self.fixed.currentData()),
                          travel=self.travel.value(), turn=self.turn.value())

    # --- réglages gardés avec le dessin ---------------------------------------------------------
    def _doc(self):
        win = getattr(self.panel, 'win', None)
        return getattr(getattr(win, 'canvas', None), 'doc', None)

    def signature(self) -> list:
        """Les corps de la pièce : nom et boîte (au dixième) de chacun."""
        T = np.asarray(self.model.triangles, dtype=np.float64)
        ids = self.model.body_ids()
        out = []
        for b in range(self.model.body_count()):
            P = T[ids == b].reshape(-1, 3)
            box = np.round(np.r_[P.min(axis=0), P.max(axis=0)], 1).tolist() if len(P) else []
            out.append([self.model.body_name(b), [float(x) + 0.0 for x in box]])
        return out

    def _load(self) -> dict:
        """Réglages enregistrés pour cette pièce ({} : aucun, ou ceux d'une
        autre pièce — autres corps)."""
        doc = self.doc
        d = doc.extra.get(KEY) if doc is not None and isinstance(doc.extra, dict) else None
        if not isinstance(d, dict) or d.get('bodies') != self.model.body_count() \
                or d.get('signature') != self.signature():
            return {}
        fields = M.Settings.__dataclass_fields__
        return {'settings': {k: v for k, v in (d.get('settings') or {}).items() if k in fields},
                'moves': dict(d.get('moves') or {})}

    def store(self) -> None:
        """Enregistre les réglages dans le dessin (modifié s'ils changent)."""
        import dataclasses
        doc = self.doc
        if doc is None or doc is not self._doc() or not isinstance(doc.extra, dict):
            return                                       # un autre dessin est montré : rien à y écrire
        moves = {str(m.body): {'kind': m.kind, 'joint': m.joint, 'on': bool(self.enabled.get(m.body, True)),
                               'amount': float(m.amount), 'auto': float(self.auto_amount.get(m.body, m.amount)),
                               'invert': bool(m.inverted)}
                 for m in self.shown_motions()}
        d = {'bodies': self.model.body_count(), 'signature': self.signature(),
             'settings': dataclasses.asdict(self.settings()), 'moves': moves}
        if doc.extra.get(KEY) != d:
            doc.extra[KEY] = d
            self.saved = {'settings': d['settings'], 'moves': moves}
            win = self.panel.win
            win.modified = True
            if hasattr(win, '_title'):
                win._title()

    def _restore_moves(self) -> None:
        """Réglages enregistrés appliqués aux mouvements repérés (même corps,
        même genre de mouvement et de liaison) ; la course réglée, tant que la
        course repérée n'a pas changé (sinon « Course » et « Rotation des
        pivots » ne serviraient plus)."""
        for m in self.shown_motions():
            s = (self.saved.get('moves') or {}).get(str(m.body))
            if not isinstance(s, dict) or (s.get('kind'), s.get('joint')) != (m.kind, m.joint):
                continue
            self.enabled[m.body] = bool(s.get('on', True))
            try:
                if abs(float(s['auto']) - m.amount) < 1e-6:
                    m.amount = float(s.get('amount', m.amount))
            except (KeyError, TypeError, ValueError):
                pass
            if s.get('invert'):
                m.axis = tuple((-np.asarray(m.axis, dtype=float)).tolist())
                m.inverted = True

    def detect(self, store: bool = True) -> None:
        st = self.settings()
        cs = M.contacts(self.model, st)
        js = M.joints(self.model, st, cs)
        self.motions = M.motions(self.model, st, js)
        self.enabled = {m.body: True for m in self.motions}
        self.auto_amount = {m.body: m.amount for m in self.motions}
        self._restore_moves()
        name = self.model.body_name
        self.joints_table.setRowCount(len(js))
        for r, j in enumerate(js):
            for c, text in enumerate((name(j.a), name(j.b), tr(M.JOINTS.get(j.kind, j.kind)),
                                      _dir_text(j.axis) if j.kind != 'encastrement' else '—')):
                self.joints_table.setItem(r, c, QTableWidgetItem(text))
        self._fill_moves()
        ground = M.fixed_body(self.model, st)
        alone = self.model.body_count() - 1 - len(js) if js else self.model.body_count() - 1
        self.status.setText(tr('{0} contact(s), {1} liaison(s), {2} corps mobile(s) — fixe : {3}').format(
            len(cs), len(js), len(self.shown_motions()), name(ground))
            + (tr(' — {0} corps sans contact').format(alone) if alone > 0 and not js else ''))
        self.set_progress(self.k)
        if store:
            self.store()

    def _solids(self) -> bool:
        """Volumes fermés des corps (calculés une fois) ; False s'il n'y en a
        pas deux à contrôler (compte rendu affiché)."""
        from PySide6.QtWidgets import QApplication
        if self.mans is None:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                self.mans, self.failed = M.body_manifolds(self.model)
            finally:
                QApplication.restoreOverrideCursor()
        if len(self.mans) >= 2:
            return True
        self.clash_label.setText(tr('Moins de deux corps fermés en volumes : rien à contrôler') + (
            '\n' + tr('Non contrôlés (pas un volume fermé) : {0}').format(
                ', '.join(self.model.body_name(b) for b in sorted(self.failed))) if self.failed else ''))
        return False

    def stop_at_collisions(self) -> dict:
        """Course de chaque mouvement animé réduite à sa course libre (seul,
        avant sa première collision) ; rend {corps: course libre}."""
        if not self._solids():
            return {}
        name = self.model.body_name
        found, lines = {}, []
        for m in self.shown_motions():
            if not self.enabled.get(m.body, True):
                continue
            t = M.free_travel(self.mans, self.active(), m.body)
            unit = 'mm' if m.kind == 'translation' else '°'
            if t is None:
                lines.append(tr('{0} : libre sur toute la course ({1})').format(
                    name(m.body), f'{m.amount:.1f} {unit}'.replace('.', ',')))
                continue
            if t <= 0:
                lines.append(tr('{0} : bloqué dès le départ — course gardée (sens à inverser ?)').format(
                    name(m.body)))
                continue
            found[m.body] = t
            m.amount = t
            lines.append(tr('{0} : butée à {1}').format(name(m.body), f'{t:.2f} {unit}'.replace('.', ',')))
        self._fill_moves()
        self.clash_label.setText('\n'.join(lines) or tr('Aucun mouvement animé'))
        self.set_progress(self.k)
        self.store()
        return found

    def check_collisions(self, steps: int = CLASH_STEPS) -> list:
        """Collisions des corps pendant le mouvement réglé (mouvements animés) ;
        la vue se met à la première trouvée. Rend les collisions."""
        if not self._solids():
            return []
        clashes = M.collisions(self.mans, self.active(), steps)
        name = self.model.body_name
        moving = {m.body: m for m in self.active() if m.kind != 'fixe' and m.amount > 0}
        lines = []
        for c in clashes[:4]:
            if c.k <= 0:
                lines.append(tr('{0} et {1} s\'interpénètrent au repos ({2} mm³)').format(
                    name(c.a), name(c.b), f'{c.volume:.1f}'.replace('.', ',')))
                continue
            own = [moving[x] for x in (c.a, c.b) if x in moving]
            at = ''
            if len(own) == 1:                            # un seul des deux a son propre mouvement : sa course
                m = own[0]
                unit = 'mm' if m.kind == 'translation' else '°'
                at = f' — {m.amount * c.k:.1f} {unit}'.replace('.', ',')
            lines.append(tr('{0} heurte {1} à {2} % de la course{3} ({4} mm³)').format(
                name(c.a), name(c.b), f'{100 * c.k:.0f}', at, f'{c.volume:.1f}'.replace('.', ',')))
        if len(clashes) > 4:
            lines.append(tr('… et {0} autre(s)').format(len(clashes) - 4))
        if not clashes:
            lines.append(tr('Aucune collision sur la course ({0} positions)').format(steps))
        if self.failed:
            lines.append(tr('Non contrôlés (pas un volume fermé) : {0}').format(
                ', '.join(name(b) for b in sorted(self.failed))))
        self.clash_label.setText('\n'.join(lines))
        if clashes:
            self.set_progress(clashes[0].k)
        return clashes

    def shown_motions(self) -> list:
        """Mouvements à régler (les corps encastrés suivent leur parent)."""
        return [m for m in self.motions if m.kind != 'fixe']

    def _fill_moves(self) -> None:
        t = self.moves_table
        shown = self.shown_motions()
        for r in range(t.rowCount()):                    # anciens widgets : détruits plus tard, cachés tout de suite
            for c in (0, 3, 4):
                old = t.cellWidget(r, c)
                if old is not None:
                    old.hide()
        t.setRowCount(len(shown))
        for r, m in enumerate(shown):
            on = QCheckBox()
            on.setChecked(self.enabled.get(m.body, True))
            on.toggled.connect(lambda v, b=m.body: self._enable(b, v))
            t.setCellWidget(r, 0, on)
            t.setItem(r, 1, QTableWidgetItem(self.model.body_name(m.body)))
            kind = (tr('Translation {0}') if m.kind == 'translation' else tr('Rotation autour de {0}')).format(
                _dir_text(m.axis))
            t.setItem(r, 2, QTableWidgetItem(kind + f' — {tr(M.JOINTS.get(m.joint, m.joint))}'))
            amt = self._spin(m.amount, 1, 0.0, 100000.0, tr('mm pour une translation, degrés pour une rotation'))
            amt.valueChanged.connect(lambda v, mo=m: self._amount(mo, v))
            t.setCellWidget(r, 3, amt)
            inv = QCheckBox()
            inv.setChecked(bool(m.inverted))
            inv.toggled.connect(lambda _v, mo=m: self._invert(mo))
            t.setCellWidget(r, 4, inv)

    def _enable(self, b: int, on: bool) -> None:
        self.enabled[b] = on
        self.set_progress(self.k)
        self.store()

    def _amount(self, mo, v: float) -> None:
        mo.amount = v
        self.set_progress(self.k)
        self.store()

    def _invert(self, mo) -> None:
        mo.axis = tuple((-np.asarray(mo.axis, dtype=float)).tolist())
        mo.inverted = not mo.inverted
        self.set_progress(self.k)
        self.store()

    def active(self) -> list:
        """Mouvements montrés : un mouvement non animé garde sa course à zéro
        (le corps suit encore son parent)."""
        return [m if m.kind == 'fixe' or self.enabled.get(m.body, True) else replace(m, amount=0.0)
                for m in self.motions]

    def set_progress(self, k: float, from_slider: bool = False) -> None:
        """Avancement 0 (fermé) → 1 (ouvert) : corps déplacés dans la vue."""
        self.k = max(0.0, min(1.0, float(k)))
        if not from_slider:
            self.slider.blockSignals(True)
            self.slider.setValue(int(round(self.k * 100)))
            self.slider.blockSignals(False)
        moves = M.poses(self.active(), self.k) if self.k > 0 else {}
        self.view.set_body_moves({b: (R, t) for b, (R, t) in moves.items()
                                  if not (np.allclose(R, np.eye(3)) and not np.any(t))})

    def _play(self, on: bool) -> None:
        if on:
            self.timer.start()
        else:
            self.timer.stop()

    def _tick(self) -> None:
        k = self.k + self.direction * TICK_STEP
        if k >= 1.0 or k <= 0.0:
            self.direction = -self.direction
        self.set_progress(k)

    def done(self, r) -> None:
        self.timer.stop()
        self.view.set_body_moves({})                     # la pièce revient fermée
        super().done(r)
