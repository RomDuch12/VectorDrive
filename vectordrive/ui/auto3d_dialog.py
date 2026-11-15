"""Fenêtre « Automatisme d'usinage 3D » (cam.auto3d) : une suite d'étapes
choisie (livrée, d'un plugin ou de l'utilisateur), ses outils proposés
d'après la pièce, tout modifiable — étapes ajoutées, retirées, déplacées,
outil, surépaisseur, passes, sens — puis enregistrée sous un nom ou
appliquée : les opérations sont créées dans le panneau FAO."""
from __future__ import annotations

import copy
import dataclasses

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QDoubleSpinBox, QHBoxLayout, QInputDialog, QLabel, QMessageBox,
                               QPushButton, QTableWidget, QTableWidgetItem, QToolButton, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from ..cam import auto3d as A
from ..i18n import tr

#: colonnes du tableau des étapes
COLUMNS = ('Active', 'Étape', 'Stratégie', 'Outil', 'Surépaisseur 3D (mm)', 'Passe en Z (mm)',
           'Entre passes (mm)', 'Crête (mm)', 'Sens')
COL_ON, COL_NAME, COL_KIND, COL_TOOL, COL_STOCK, COL_STEP, COL_OVER, COL_CREST, COL_DIR = range(9)
#: largeur de la colonne « Outil » (px) : au moins, au plus (la liste déroulée montre le nom entier)
TOOL_COL = (180, 380)
#: stratégies proposées pour une étape
STEP_LABELS = {'ebauche3d': 'Ébauche 3D (paliers en Z)', 'reprise3d': 'Reprise 3D (reste de l\'outil d\'avant)',
               'surface3d': 'Balayage 3D (surface)', 'niveaux3d': 'Niveaux constants (parois)'}
DIRS = {'x': 'Selon X', 'y': 'Selon Y', 'xy': 'Croisé (X puis Y)'}
#: nature d'outil d'une stratégie quand on la change
KIND_TOOL = {'ebauche3d': ('fraise', 'gros'), 'reprise3d': ('fraise', 'moyen'), 'surface3d': ('boule', 'fin'),
             'niveaux3d': ('boule', 'fin')}
#: champs du formulaire « Réglages de l'étape » tenus par la fenêtre (zone, prise, outil d'avant…) : masqués
STEP_HIDDEN = ('id', 'geometry', 'catalog', 'drawings', 'folder', 'machines', 'name', 'instruction', 'params',
               'ref_tool_id', 'sources', 'items', 'model_path', 'faces3d', 'contours3d', 'setup_face', 'body3d',
               'enabled', 'link_previous', 'surface2d', 'contours3d_pl', 'body3d_ref')
#: champs montrés mais choisis dans le tableau (stratégie, outil)
STEP_LOCKED = ('kind', 'tool_id')


def _spin(v: float, special: str = '') -> QDoubleSpinBox:
    w = QDoubleSpinBox()
    w.setDecimals(3)
    w.setRange(0.0, 1000.0)
    w.setSingleStep(0.05)
    w.setValue(float(v or 0.0))
    if special:
        w.setSpecialValueText(tr(special))
    return w


class Auto3DDialog(QDialog):
    """`cp` : panneau FAO (outils du document, Mes outils) ; `model3d` :
    la pièce ; zone : `faces`, `loops` (vides : toute la pièce) ; `setup`
    (face vers l'outil, corps) : usinages de cette prise seulement — la
    pièce (ou le corps) telle qu'elle y est posée est `model3d`, la zone y
    est choisie (`view_loops` : ses contours tels que montrés)."""

    def __init__(self, parent, cp, model3d, *, model_path: str = '', faces=(), loops=(), depth: float = 0.0,
                 sides_model=None, setup=None, view_loops=None):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)                                 # assez large pour toutes les colonnes, à l'ouverture
        self.setWindowTitle(tr('Automatisme d\'usinage 3D'))
        self.cp, self.model3d = cp, model3d
        self.sides_model = sides_model if sides_model is not None else model3d   # prises : pièce telle que lue
        self.shown_setup = (str(setup[0] or ''), int(setup[1])) if setup is not None else None
        self.model_path, self.faces, self.loops, self.depth = model_path, list(faces), list(loops), float(depth)
        self.info = A.analyze(model3d, faces, loops if view_loops is None else view_loops)
        self.doc_tools = list(cp.setup().tools) if cp is not None else []
        self.edited_tools: set = set()                   # outils modifiés ici (copies) : leurs identifiants
        self.library = list(cp.library_tools()) if cp is not None else []
        self.seq = A.Sequence()
        self.planned: list = []
        self._filling = False
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel(tr('Automatisme')))
        self.choice = QComboBox()
        self.choice.setMinimumWidth(260)
        row.addWidget(self.choice, 1)
        self.save_btn = QPushButton(tr('Enregistrer sous…'))
        self.save_btn.setToolTip(tr('Garder cette suite d\'étapes (outils, réglages) sous un nom, pour la '
                                    'réappliquer à d\'autres pièces'))
        self.save_btn.clicked.connect(lambda: self.save_as())
        row.addWidget(self.save_btn)
        self.del_btn = QPushButton(tr('Supprimer'))
        self.del_btn.clicked.connect(lambda: self.delete_current())
        row.addWidget(self.del_btn)
        lay.addLayout(row)
        self.desc = QLabel()
        self.desc.setWordWrap(True)
        lay.addWidget(self.desc)
        self.zone = QLabel(self._zone_text())
        self.zone.setWordWrap(True)
        lay.addWidget(self.zone)
        srow = QHBoxLayout()
        self.stock_text = QLabel()
        self.stock_text.setWordWrap(True)
        srow.addWidget(self.stock_text, 1)
        self.stock_btn = QPushButton(tr('Brut…'))
        self.stock_btn.setToolTip(tr('Bloc, barre ronde ou plaque d\'où la pièce est usinée : l\'ébauche part de son '
                                     'haut et vide tout le brut autour de la pièce'))
        self.stock_btn.clicked.connect(lambda: self.edit_stock())
        self.stock_btn.setEnabled(cp is not None)
        srow.addWidget(self.stock_btn)
        lay.addLayout(srow)
        wrow = QHBoxLayout()
        self.ws_text = QLabel()
        self.ws_text.setWordWrap(True)
        wrow.addWidget(self.ws_text, 1)
        self.jaws_box = QCheckBox(tr('Rester au-dessus des mors'))
        self.jaws_box.setChecked(True)
        self.jaws_box.setToolTip(tr('Première prise : aucune opération ne descend à moins d\'1 mm du haut des mors de '
                                    'l\'étau ; le dessous se fait dans une autre prise'))
        self.jaws_box.toggled.connect(lambda _on: self._jaws_changed())
        wrow.addWidget(self.jaws_box)
        self.ws_btn = QPushButton(tr('Espace de travail…'))
        self.ws_btn.setToolTip(tr('Étau, mandrin, brides autour de la pièce : la prise dans les mors borne la '
                                  'profondeur de la première prise'))
        self.ws_btn.clicked.connect(lambda: self.edit_workspace())
        self.ws_btn.setEnabled(cp is not None)
        wrow.addWidget(self.ws_btn)
        lay.addLayout(wrow)
        self._update_stock()
        self._update_workspace()
        whole = QHBoxLayout()
        whole.addWidget(QLabel(tr('Corps')))
        self.body_mode = QComboBox()
        self.body_mode.addItem(tr('Toute la pièce'), 'piece')
        if model3d.body_count() > 1 and not (self.faces or self.loops):
            self.body_mode.addItem(tr('Chaque corps séparément'), 'chacun')
            for b in range(model3d.body_count()):
                self.body_mode.addItem(model3d.body_name(b), b)
        self.body_mode.setToolTip(tr('Pièce à plusieurs corps : usiner chaque corps comme une pièce à part'))
        if self.shown_setup is not None:                 # prise de l'onglet de la vue 3D : elle seule
            b = self.shown_setup[1]
            self.body_mode.clear()
            self.body_mode.addItem(self.sides_model.body_name(b) if b >= 0 else tr('Toute la pièce'),
                                   b if b >= 0 else 'piece')
            self.body_mode.setEnabled(False)
        whole.addWidget(self.body_mode)
        whole.addWidget(QLabel(tr('Prises')))
        self.side_mode = QComboBox()
        self.side_mode.addItem(tr('Comme le dessin'), 'dessin')
        self.side_mode.addItem(tr('Toutes les faces (prises proposées)'), 'toutes')
        self.side_mode.addItem(tr('Faces choisies'), 'choisies')
        self.side_mode.setToolTip(tr('Toutes les faces : les prises (dessus, dessous, côtés) qui atteignent toute la '
                                     'surface, chacune précédée d\'un message « poser la pièce » ; faces choisies : '
                                     'celles que vous cochez'))
        if self.shown_setup is not None:
            self.side_mode.clear()
            self.side_mode.addItem(self._side_text(self.shown_setup[0]), 'prise')
            self.side_mode.setEnabled(False)
            tip = tr('Usinages créés dans la prise de l\'onglet de la vue 3D ({0}) ; une autre prise : son '
                     'onglet, ou l\'onglet « Ensemble », « Comme le dessin »').format(self._setup_text())
            self.body_mode.setToolTip(tip)
            self.side_mode.setToolTip(tip)
        whole.addWidget(self.side_mode)
        whole.addStretch(1)
        lay.addLayout(whole)
        from ..core import access3d
        self.side_row = QWidget()
        srow2 = QHBoxLayout(self.side_row)
        srow2.setContentsMargins(0, 0, 0, 0)
        srow2.addWidget(QLabel(tr('Faces vers l\'outil')))
        self.side_checks = {}
        for s in access3d.SIDES:                         # dans l'ordre des prises (dessus d'abord)
            cb = QCheckBox(tr(A.SIDE_LABELS.get(s, s)))
            cb.toggled.connect(lambda _on: self._side_checked())
            srow2.addWidget(cb)
            self.side_checks[s] = cb
        srow2.addStretch(1)
        self.side_row.setVisible(False)
        self._sides_touched = False
        self._reach_cache: dict = {}
        lay.addWidget(self.side_row)
        self.sides_text = QLabel()
        self.sides_text.setWordWrap(True)
        lay.addWidget(self.sides_text)
        self._sides_cache: dict = {}
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels([tr(c) for c in COLUMNS])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setMinimumWidth(900)
        self.table.setMinimumHeight(180)
        lay.addWidget(self.table, 1)
        btns = QHBoxLayout()
        for text, fn in ((tr('Ajouter une étape'), self.add_step), (tr('Retirer'), self.remove_step),
                         (tr('Monter'), lambda: self.move_step(-1)), (tr('Descendre'), lambda: self.move_step(1))):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, f=fn: f())
            btns.addWidget(b)
        self.settings_btn = QPushButton(tr('Réglages de l\'étape…'))
        self.settings_btn.setToolTip(tr('Tous les réglages de l\'opération que crée l\'étape choisie (rampe, pentes, '
                                        'vitesses, hauteurs…) ; ceux que vous changez sont gardés avec l\'étape'))
        self.settings_btn.clicked.connect(lambda: self.step_settings())
        btns.addWidget(self.settings_btn)
        self.tool_btn = QPushButton(tr('Outil de l\'étape…'))
        self.tool_btn.setToolTip(tr('L\'outil proposé ou choisi pour l\'étape, à modifier (diamètre, longueur '
                                    'utile, avance, vitesse…) : la copie modifiée devient l\'outil de l\'étape, '
                                    'ajoutée au dessin avec les usinages ; l\'outil d\'origine ne change pas'))
        self.tool_btn.clicked.connect(lambda: self.step_tool())
        btns.addWidget(self.tool_btn)
        btns.addStretch(1)
        lay.addLayout(btns)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        lay.addWidget(self.summary)
        self.preview_btn = QToolButton()
        self.preview_btn.setCheckable(True)
        self.preview_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.preview_btn.setArrowType(Qt.ArrowType.RightArrow)
        self.preview_btn.setToolTip(tr('Les usinages qui seront créés, prise par prise : outil, profondeur, remarques'))
        self.preview_btn.toggled.connect(lambda on: self._show_preview(on))
        lay.addWidget(self.preview_btn)
        self.preview = QTreeWidget()
        self.preview.setColumnCount(4)
        self.preview.setHeaderLabels([tr('Usinage'), tr('Outil'), tr('Profondeur (mm)'), tr('Remarque')])
        self.preview.setMinimumHeight(120)
        self.preview.setVisible(False)
        lay.addWidget(self.preview, 1)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.button(QDialogButtonBox.StandardButton.Ok).setText(tr('Créer les usinages'))
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay.addWidget(box)
        self._fill_choices()
        self.choice.currentIndexChanged.connect(lambda _i: self.load(self.choice.currentData()))
        self.body_mode.currentIndexChanged.connect(lambda _i: self._fill_table())
        self.side_mode.currentIndexChanged.connect(lambda _i: self._side_mode_changed())
        self.load(self.choice.currentData())

    # --- textes ---------------------------------------------------------------------------
    def _zone_text(self) -> str:
        f = lambda v: f'{v:.1f}'.rstrip('0').rstrip('.').replace('.', ',')     # noqa: E731
        i = self.info
        where = (tr('{0} face(s) choisie(s)').format(len(self.faces)) if self.faces else
                 tr('{0} contour(s) choisi(s)').format(len(self.loops)) if self.loops else tr('toute la pièce'))
        text = tr('Zone : {0} — {1} × {2} mm, profondeur {3} mm').format(where, f(i.size_x), f(i.size_y), f(i.depth))
        if i.min_radius > 0:
            text += tr(' — plus petit rayon creux {0} mm').format(f(i.min_radius))
        if self.shown_setup is not None:
            text += tr(' — prise de l\'onglet : {0}').format(self._setup_text())
        return text

    def _side_text(self, face: str) -> str:
        if face in A.SIDE_LABELS:
            return tr(A.SIDE_LABELS[face])
        from ..core import placement3d as P3
        return tr(P3.face_label(face))

    def _setup_text(self) -> str:
        """« Corps 2, dessous » : la prise de l'onglet de la vue 3D."""
        face, b = self.shown_setup
        return '{0}, {1}'.format(self.sides_model.body_name(b) if b >= 0 else tr('toute la pièce'),
                                 self._side_text(face))

    def _fill_choices(self, select: str = '') -> None:
        self.choice.blockSignals(True)
        self.choice.clear()
        origin_label = {'cœur': '', 'plugin': tr(' (plugin)'), 'utilisateur': tr(' (mien)')}
        for name, (origin, _s) in A.all_sequences().items():
            self.choice.addItem(tr(name) + origin_label.get(origin, ''), name)
        i = self.choice.findData(select) if select else 0
        self.choice.setCurrentIndex(max(0, i))
        self.choice.blockSignals(False)

    # --- suite --------------------------------------------------------------------------------
    def load(self, name) -> None:
        found = A.all_sequences().get(name)
        if found is None:
            return
        origin, seq = found
        self.seq = copy.deepcopy(seq)
        self.desc.setText(tr(seq.description))
        self.del_btn.setEnabled(origin == 'utilisateur')
        self._fill_table()

    def _tools_for(self, kind: str) -> list:
        ids = {t.id for t in self.doc_tools}
        return [t for t in self.doc_tools if t.kind == kind] + \
            [t for t in self.library if t.kind == kind and t.id not in ids]

    def _bodies(self) -> list:
        mode = self.body_mode.currentData()
        return list(range(self.model3d.body_count())) if mode == 'chacun' else \
            ([int(mode)] if isinstance(mode, int) else [-1])

    def chosen_sides(self) -> list:
        """Faces cochées (« Faces choisies »), dans l'ordre des prises."""
        return [s for s, cb in self.side_checks.items() if cb.isChecked()]

    def groups(self) -> list:
        """[(corps, [prises])] d'après les choix « Corps » et « Prises » (la
        prise de l'onglet de la vue 3D seule, si elle est donnée)."""
        if self.shown_setup is not None:
            return [(self.shown_setup[1], [self.shown_setup[0]])]
        out = []
        mode = self.side_mode.currentData()
        for b in self._bodies():
            if mode == 'toutes':
                out.append((b, [s for s, _g in self._sides(b)] or ['']))
            elif mode == 'choisies':
                out.append((b, self.chosen_sides() or ['']))
            else:
                out.append((b, ['']))
        return out

    def _reach_res(self) -> float:
        return max(0.3, min(1.0, max(self.info.size_x, self.info.size_y) / 400))

    def _side_model(self, body: int):
        from ..cam import mill3d
        return mill3d.submodel(self.sides_model, body) if body >= 0 else self.sides_model

    def _sides(self, body: int) -> list:
        """Prises proposées pour un corps (ou toute la pièce), calculées une fois."""
        if body not in self._sides_cache:
            from ..core import access3d
            plan, left = access3d.plan_sides(self._side_model(body), self._reach_res(),
                                             cache=self._reach_cache.setdefault(body, {}))   # gardé pour « choisies »
            self._sides_cache[body] = plan
            self._sides_left = getattr(self, '_sides_left', {})
            self._sides_left[body] = left
        return self._sides_cache[body]

    def _left(self, body: int, sides) -> float:
        """Part de la surface hors d'atteinte des prises `sides` (proposées : celle
        du plan ; choisies : calculée, faces gardées d'un choix à l'autre)."""
        if self.side_mode.currentData() == 'toutes':
            return getattr(self, '_sides_left', {}).get(body, 0.0)
        from ..core import access3d
        if self.shown_setup is not None and any(s not in access3d.SIDES for s in sides):
            return 0.0                                   # posée sur une face plane : pas mesurée
        return access3d.left_out(self._side_model(body), sides, self._reach_res(),
                                 self._reach_cache.setdefault(body, {}))

    def _side_mode_changed(self) -> None:
        """« Faces choisies » : les cases, cochées d'abord comme les prises proposées."""
        choose = self.side_mode.currentData() == 'choisies'
        self.side_row.setVisible(choose)
        if choose and not self._sides_touched:
            want = {s for b in self._bodies() for s, _g in self._sides(b)} or {'+Z'}
            for s, cb in self.side_checks.items():
                cb.blockSignals(True)
                cb.setChecked(s in want)
                cb.blockSignals(False)
        self._fill_table()

    def _side_checked(self) -> None:
        self._sides_touched = True
        if self.side_mode.currentData() == 'choisies':
            self._fill_table()

    def _infos(self, groups) -> dict:
        from ..cam import mill3d
        if self.shown_setup is not None:                 # la pièce montrée est déjà celle de la prise
            return {-1: self.info, self.shown_setup[1]: self.info}
        out = {-1: self.info}
        for b, _s in groups:
            if b >= 0:
                out[b] = A.analyze(mill3d.submodel(self.model3d, b))
                out[b].stock_top = self.info.stock_top
                out[b].floor = self.info.floor
        return out

    # --- brut -----------------------------------------------------------------------------
    def _update_stock(self) -> None:
        """Brut du réglage FAO autour de la pièce : sa ligne, ses contrôles,
        et le haut d'où part l'ébauche."""
        from ..core import stock3d
        st = stock3d.of_setup(self.cp.setup()) if self.cp is not None else stock3d.Stock3D()
        box = stock3d.box_for(self.cp.doc, self.cp.setup(), self.model3d) if self.cp is not None else None
        self.info.stock_top = max(0.0, box.top) if box is not None else 0.0
        lines = [tr('Brut : ') + stock3d.describe(st, box)]
        if box is not None:
            lines += stock3d.check(box, self.model3d.bounds())
        self.stock_text.setText(' — '.join(lines))

    def edit_stock(self, exec_dialog: bool = True):
        """Fenêtre « Brut de la pièce 3D » ; la suite est replanifiée."""
        if self.cp is None:
            return None
        dlg = self.cp.stock_dialog(exec_dialog=exec_dialog, model=self.model3d)
        if exec_dialog:
            self._update_stock()
            self._fill_table()
        return dlg

    # --- espace de travail ----------------------------------------------------------------
    def _update_workspace(self) -> None:
        """Étau (ou mandrin) de l'espace de travail : sa ligne, et la profondeur
        au plus de la première prise."""
        from ..core import workspace as WS
        ws = WS.of(self.cp.doc, *(self.shown_setup or ('', -1))) if self.cp is not None else WS.Workspace()
        floor, el = WS.jaw_floor(ws)
        others = len((self.cp.doc.extra.get(WS.KEY_SETUPS) or {})) if self.cp is not None else 0
        if others and self.shown_setup is not None and WS.own(self.cp.doc, *self.shown_setup):
            others -= 1                                  # celui de la prise montrée : le sien, pas un autre
        self.jaws_box.setVisible(el is not None or others > 0)
        self.info.floor = floor if el is not None and self.jaws_box.isChecked() else 0.0
        if not ws.elements:
            self.ws_text.setText(tr('Espace de travail : aucun (ni étau ni mandrin vérifié)'))
        elif el is None:
            k = WS.clamping(ws)
            self.ws_text.setText(tr('Espace de travail : {0} élément(s)').format(len(ws.elements)) if k < 0 else
                                 tr('Espace de travail : « {0} », haut des mors Z {1} mm — sous la pièce')
                                 .format(ws.elements[k].label(), WS._mm(WS.jaw_top(ws.elements[k]))))
        else:
            self.ws_text.setText(tr('Espace de travail : « {0} », haut des mors Z {1} mm — première prise jusqu\'à '
                                    '{2} mm de profondeur').format(el.label(), WS._mm(WS.jaw_top(el)), WS._mm(floor)))
        if others:
            self.ws_text.setText(self.ws_text.text() + ' — ' + tr('{0} autre(s) prise(s) tenue(s) dans leur propre '
                                                                    'espace').format(others))

    def _floors(self, groups) -> dict:
        """{(face, corps): profondeur au plus} de chaque prise, selon les mors
        de son espace de travail (le sien, celui du dessin pour la face du
        dessin ou un corps seul — dans son repère —, aucun pour une pièce
        retournée sans le sien) ; mors ignorés : aucune."""
        from ..core import workspace as WS
        out = {}
        if self.cp is None or not self.jaws_box.isChecked():
            return out
        for b, sides in groups:
            for sd in sides:
                f, el = WS.jaw_floor(WS.of(self.cp.doc, sd, b))
                out[(sd, b)] = f if el is not None else 0.0
        return out

    def _jaws_changed(self) -> None:
        self._update_workspace()
        self._fill_table()

    def edit_workspace(self, exec_dialog: bool = True):
        """Fenêtre « Espace de travail » ; la suite est replanifiée."""
        if self.cp is None:
            return None
        dlg = self.cp.workspace_dialog(exec_dialog=exec_dialog, model=self.model3d,
                                       setup=self.shown_setup or ('', -1))
        if exec_dialog:
            self._update_workspace()
            self._fill_table()
        return dlg

    def _replan(self) -> None:
        defaults = self.cp._op_defaults() if self.cp is not None else {}
        groups = self.groups()
        names = {b: self.sides_model.body_name(b) for b in range(self.sides_model.body_count())}
        home, own = ('',), {}
        if self.cp is not None:
            from ..cam import mill3d
            from ..core import placement3d as P3
            from ..core import workspace as WS
            from ..io import model3d
            home = ('', WS.drawing_face(self.cp.doc, self.model_path or None))
            path = self.model_path or model3d.source_of(self.cp.doc) or ''
            for b in range(self.sides_model.body_count() if path and mill3d._is_source(self.cp.doc, path) else 0):
                p = P3.body_of(self.cp.doc, b)
                if p is not None:                                              # positionné à part : sa pose
                    own[b] = p.face or '+Z'
        self.planned = A.plan_all(self.seq, self.doc_tools, self.library, self._infos(groups), groups=groups,
                                  model_path=self.model_path, faces=self.faces, loops=self.loops, depth=self.depth,
                                  defaults=defaults, body_names=names, floors=self._floors(groups), home=home,
                                  own_faces=own, keep_zone=self.shown_setup is not None)
        f = lambda s: tr(A.SIDE_LABELS.get(s, s))                              # noqa: E731
        lines = []
        for b, sides in groups:
            if sides != ['']:
                left = self._left(b, sides)
                lines.append(tr('{0} : {1}').format(names.get(b, tr('Pièce')) if b >= 0 else tr('Pièce'),
                                                    ', '.join(f(s) for s in sides))
                             + (tr(' (hors d\'atteinte : {0} %)').format(f'{left * 100:.1f}'.replace('.', ','))
                                if left > 0.001 else ''))
        self.sides_text.setText(tr('Prises — ') + ' ; '.join(lines) if lines else '')

    def _fill_table(self) -> None:
        self._filling = True
        self._replan()
        by_step = {}
        for p in self.planned:                               # la première opération de chaque étape
            if p.step is not None:
                by_step.setdefault(id(p.step), p)
        for r in range(self.table.rowCount()):           # anciens widgets cachés tout de suite : Qt ne les
            for c in range(self.table.columnCount()):    # détruit qu'au prochain tour de la boucle d'événements
                old = self.table.cellWidget(r, c)
                if old is not None:
                    old.hide()
        self.table.setRowCount(len(self.seq.steps))
        for r, st in enumerate(self.seq.steps):
            on = QCheckBox()
            on.setChecked(st.enabled)
            on.toggled.connect(lambda v, s=st: self._set(s, 'enabled', v))
            self.table.setCellWidget(r, COL_ON, on)
            it = QTableWidgetItem(tr(st.name) if st.name else '')
            it.setToolTip(_params_text(st.params))
            self.table.setItem(r, COL_NAME, it)
            kind = QComboBox()
            for k, lab in STEP_LABELS.items():
                kind.addItem(tr(lab), k)
            kind.setCurrentIndex(max(0, kind.findData(st.kind)))
            kind.currentIndexChanged.connect(lambda _i, s=st, w=kind: self._set_kind(s, w.currentData()))
            self.table.setCellWidget(r, COL_KIND, kind)
            p = by_step.get(id(st))
            tool = QComboBox()
            prop = p.tool if p is not None else None
            suffix = {'document': '', 'bibliotheque': tr(' — de Mes outils'), 'nouveau': tr(' — nouvel outil')}
            if p is not None:
                tool.addItem(tr('Proposé : {0}').format(_tool_text(prop)) + suffix.get(p.origin, ''), '')
            for t in self._tools_for(st.tool_kind):
                tool.addItem(_tool_text(t), t.id)
            if st.rule == 'outil' and st.tool_id:
                tool.setCurrentIndex(max(0, tool.findData(st.tool_id)))
            tool.setToolTip(tr('« Proposé » : choisi d\'après la pièce ({0}) ; sinon l\'outil choisi').format(
                tr(A.RULES.get(st.rule if st.rule != 'outil' else KIND_TOOL.get(st.kind, ('', 'fin'))[1], ''))))
            tool.currentIndexChanged.connect(lambda _i, s=st, w=tool: self._set_tool(s, w.currentData()))
            self.table.setCellWidget(r, COL_TOOL, tool)
            op = p.op if p is not None else None
            for col, key, special in ((COL_STOCK, 'stock', ''), (COL_STEP, 'step_down', 'auto'),
                                      (COL_OVER, 'stepover_mm', 'auto')):
                shown = st.params.get(key, getattr(op, key, 0.0) if key == 'stock' and op is not None else 0.0)
                w = _spin(shown or 0.0, special)
                if op is not None and key != 'stock' and not st.params.get(key):
                    w.setToolTip(tr('auto : {0} mm').format(f'{getattr(op, key, 0.0):g}'.replace('.', ',')))
                w.valueChanged.connect(lambda v, s=st, k=key: self._set_param(s, k, v))
                self.table.setCellWidget(r, col, w)
            crest = _spin(st.params.get('crete') or 0.0, 'auto')
            crest.setDecimals(3)
            crest.setSingleStep(0.005)
            crest.setEnabled(st.tool_kind == 'boule' and st.kind != 'ebauche3d')
            crest.setToolTip(tr('Hauteur de la crête laissée entre deux passes de la fraise boule : la distance entre '
                                'passes (ou la passe en Z des niveaux constants) en découle, sauf si elle est '
                                'donnée — auto : {0} mm').format(f'{A.CRETE:g}'.replace('.', ',')))
            crest.valueChanged.connect(lambda v, s=st: self._set_param(s, 'crete', v))
            self.table.setCellWidget(r, COL_CREST, crest)
            d = QComboBox()
            for k, lab in DIRS.items():
                d.addItem(tr(lab), k)
            d.setCurrentIndex(max(0, d.findData(st.params.get('raster_dir', 'x'))))
            d.setEnabled(st.kind in ('surface3d', 'reprise3d'))
            d.currentIndexChanged.connect(lambda _i, s=st, w=d: self._set_param(s, 'raster_dir', w.currentData()))
            self.table.setCellWidget(r, COL_DIR, d)
        self.table.resizeColumnsToContents()
        lo, hi = TOOL_COL
        self.table.setColumnWidth(COL_TOOL, max(lo, min(self.table.columnWidth(COL_TOOL), hi)))
        self._filling = False
        self._summary()
        if not getattr(self, '_names_hooked', False):
            self.table.itemChanged.connect(self._name_changed)
            self._names_hooked = True

    def _auto_tips(self) -> None:
        """Valeurs « auto » de la passe en Z et de l'entre-passes d'après le plan."""
        firsts = {}
        for p in self.planned:
            if p.step is not None:
                firsts.setdefault(id(p.step), p)
        for r, st in enumerate(self.seq.steps):
            p = firsts.get(id(st))
            for col, key in ((COL_STEP, 'step_down'), (COL_OVER, 'stepover_mm')):
                w = self.table.cellWidget(r, col)
                if w is not None and p is not None and not st.params.get(key):
                    w.setToolTip(tr('auto : {0} mm').format(f'{getattr(p.op, key, 0.0):g}'.replace('.', ',')))

    def _show_preview(self, on: bool) -> None:
        self.preview_btn.setArrowType(Qt.ArrowType.DownArrow if on else Qt.ArrowType.RightArrow)
        self.preview.setVisible(on)

    def _fill_preview(self) -> None:
        """Aperçu : les usinages qui seront créés, sous la prise (« poser la
        pièce ») à laquelle ils appartiennent."""
        self.preview.clear()
        under = None
        n = 0
        for p in self.planned:
            if p.tool is None:                             # instruction : une nouvelle prise
                under = QTreeWidgetItem(self.preview, [p.op.name, '', '', ''])
                under.setFirstColumnSpanned(True)
                under.setExpanded(True)
                continue
            n += 1
            name = tr(p.step.name) if p.step is not None and p.step.name else tr(STEP_LABELS.get(p.op.kind, p.op.kind))
            depth = f'{p.op.depth:g}'.replace('.', ',') if p.op.depth > 0 else tr('toute la pièce')
            notes = []
            if p.origin == 'nouveau':
                notes.append(tr('outil à créer'))
            elif p.origin == 'bibliotheque':
                notes.append(tr('outil copié de Mes outils'))
            if p.jaws:
                notes.append(tr('arrêtée au-dessus des mors'))
            if p.limited:
                notes.append(tr('limitée à la longueur utile de l\'outil'))
            QTreeWidgetItem(under if under is not None else self.preview,
                            [name, _tool_text(p.tool), depth, ', '.join(notes)])
        for c in range(self.preview.columnCount()):
            self.preview.resizeColumnToContents(c)
        self.preview_btn.setText(tr('Aperçu des usinages ({0})').format(n))

    def _summary(self) -> None:
        self._fill_preview()
        if not self.planned:
            self.summary.setText(tr('Aucune étape active'))
            return
        news = list({id(p.tool): p for p in self.planned if p.origin == 'nouveau'}.values())
        libs = list({p.tool.id: p for p in self.planned if p.origin == 'bibliotheque'}.values())
        parts = [tr('{0} usinage(s) seront créés').format(sum(1 for p in self.planned if p.tool is not None))]
        if libs:
            parts.append(tr('{0} outil(s) copiés de Mes outils dans le document').format(len(libs)))
        if news:
            parts.append(tr('{0} outil(s) à créer : {1}').format(len(news), ', '.join(p.tool.name for p in news)))
        jaws = [p for p in self.planned if p.jaws]
        if jaws:
            parts.append(tr('{0} opération(s) arrêtée(s) à {1} mm de profondeur, au-dessus des mors de l\'étau '
                            '(le dessous : une autre prise)').format(len(jaws), f'{jaws[0].jaws:g}'.replace('.', ',')))
        short = list({id(p.tool): p for p in self.planned if p.limited}.values())
        if short:
            parts.append(tr('profondeur limitée à la longueur utile de : {0} (outils plus longs, ou autres '
                            'prises)').format(', '.join(f'{p.tool.name} ({p.limited:g} mm)'.replace('.', ',')
                                                       for p in short)))
        self.summary.setText(' — '.join(parts))

    def _name_changed(self, item) -> None:
        if self._filling or item.column() != COL_NAME:
            return
        r = item.row()
        if 0 <= r < len(self.seq.steps):
            self.seq.steps[r].name = item.text()
            self._replan()

    def _set(self, st, key: str, v) -> None:
        if self._filling:
            return
        setattr(st, key, v)
        self._replan()
        self._summary()

    def _set_kind(self, st, kind: str) -> None:
        if self._filling:
            return
        st.kind = kind
        st.tool_kind, st.rule = KIND_TOOL.get(kind, ('boule', 'fin'))
        st.tool_id = ''
        self._fill_table()

    def _set_tool(self, st, tool_id: str) -> None:
        if self._filling:
            return
        st.rule, st.tool_id = ('outil', tool_id) if tool_id else (KIND_TOOL.get(st.kind, ('', 'fin'))[1], '')
        self._fill_table()

    def _set_param(self, st, key: str, v) -> None:
        if self._filling:
            return
        if isinstance(v, float) and v == 0.0 and key != 'stock':
            st.params.pop(key, None)                      # 0 : automatique
        else:
            st.params[key] = v
        self._replan()
        self._auto_tips()
        self._summary()
        r = next((i for i, s in enumerate(self.seq.steps) if s is st), -1)
        it = self.table.item(r, COL_NAME) if r >= 0 else None
        if it is not None:
            it.setToolTip(_params_text(st.params))

    def _row(self) -> int:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        return rows[0].row() if rows else self.table.currentRow()

    def step_settings(self, row: int | None = None, exec_dialog: bool = True):
        """« Réglages de l'étape… » : le formulaire complet de l'opération que
        crée l'étape (sa première prise) ; les champs changés deviennent des
        réglages de l'étape — pour toutes ses prises, gardés à l'enregistrement
        de la suite. Rend le formulaire (sans l'ouvrir si `exec_dialog` est faux)."""
        r = self._row() if row is None else row
        if not 0 <= r < len(self.seq.steps):
            return None
        st = self.seq.steps[r]
        p = next((p for p in self.planned if p.step is st), None)
        if p is None:
            if exec_dialog:
                QMessageBox.information(self, tr('Réglages de l\'étape'),
                                        tr('Étape inactive : cochez-la pour la régler'))
            return None
        from .cam_panel import FieldsDialog
        op = copy.deepcopy(p.op)
        tools = list(self.doc_tools) + ([p.tool] if all(t.id != p.tool.id for t in self.doc_tools) else [])
        dlg = FieldsDialog(self, tr('Réglages de l\'étape « {0} »').format(tr(st.name) if st.name else
                                                                           tr(STEP_LABELS.get(st.kind, st.kind))),
                           op, None, tools, hidden=STEP_HIDDEN)
        for n in STEP_LOCKED:                                # choisis dans le tableau
            w = dlg.widgets.get(n)
            if w is not None:
                w.setEnabled(False)
        base = copy.deepcopy(op)                             # valeurs telles que le formulaire les montre (arrondies)
        dlg.obj = base
        dlg.apply()
        dlg.obj = op

        def done(ok) -> None:
            if not ok:
                return
            dlg.apply()
            for f in dataclasses.fields(op):
                if f.name in STEP_HIDDEN or f.name in STEP_LOCKED:
                    continue
                v = getattr(op, f.name)
                if v != getattr(base, f.name):
                    st.params[f.name] = copy.deepcopy(v)
            self._fill_table()
            self.table.selectRow(r)
        if not exec_dialog:
            dlg.finished.connect(lambda res: done(res == QDialog.DialogCode.Accepted))
            dlg.finished.connect(lambda _res: dlg.deleteLater())
            return dlg
        done(dlg.exec())
        dlg.deleteLater()
        return dlg

    def step_tool(self, row: int | None = None, exec_dialog: bool = True):
        """« Outil de l'étape… » : l'outil proposé ou choisi pour l'étape dans
        son formulaire ; validé, une copie modifiée (la même si elle l'est
        déjà) devient l'outil choisi de l'étape — ajoutée au dessin à la
        création des usinages ; l'outil d'origine (du dessin, de Mes outils)
        ne change pas. Rend le formulaire (sans l'ouvrir si `exec_dialog` est
        faux)."""
        r = self._row() if row is None else row
        if not 0 <= r < len(self.seq.steps):
            return None
        st = self.seq.steps[r]
        p = next((p for p in self.planned if p.step is st), None)
        if p is None or p.tool is None:
            if exec_dialog:
                QMessageBox.information(self, tr('Outil de l\'étape'),
                                        tr('Étape inactive : cochez-la pour régler son outil'))
            return None
        from ..cam import model
        from .cam_panel import FieldsDialog
        own = p.tool.id in self.edited_tools
        t = p.tool if own else model.CamTool.from_dict(dict(p.tool.to_dict(), id=model.new_id()))
        name = t.name
        dlg = FieldsDialog(self, tr('Outil de l\'étape « {0} »').format(tr(st.name) if st.name else
                                                                        tr(STEP_LABELS.get(st.kind, st.kind))), t)

        def done(ok) -> None:
            if not ok:
                return
            dlg.apply()
            if not own:
                if t.name == name:                           # nom inchangé : la copie se distingue
                    t.name = tr('{0} (modifié)').format(name)
                self.doc_tools.append(t)
                self.edited_tools.add(t.id)
            st.rule, st.tool_id = 'outil', t.id
            self._fill_table()
            self.table.selectRow(r)
        if not exec_dialog:
            dlg.finished.connect(lambda res: done(res == QDialog.DialogCode.Accepted))
            dlg.finished.connect(lambda _res: dlg.deleteLater())
            return dlg
        done(dlg.exec())
        dlg.deleteLater()
        return dlg

    def add_step(self) -> None:
        self.seq.steps.append(A.Step('surface3d', tr('Finition'), 'boule', 'fin',
                                     params={'raster_dir': 'xy', 'crete': A.CRETE}))
        self._fill_table()
        self.table.selectRow(len(self.seq.steps) - 1)

    def remove_step(self) -> None:
        r = self._row()
        if 0 <= r < len(self.seq.steps):
            del self.seq.steps[r]
            self._fill_table()

    def move_step(self, d: int) -> None:
        r = self._row()
        q = r + d
        if 0 <= r < len(self.seq.steps) and 0 <= q < len(self.seq.steps):
            s = self.seq.steps
            s[r], s[q] = s[q], s[r]
            self._fill_table()
            self.table.selectRow(q)

    def save_as(self, name: str | None = None) -> str | None:
        if name is None:
            name, ok = QInputDialog.getText(self, tr('Enregistrer l\'automatisme'), tr('Nom'),
                                            text=self.choice.currentData() or '')
            if not ok or not name.strip():
                return None
        seq = copy.deepcopy(self.seq)
        seq.name = name.strip()
        if not seq.description:
            seq.description = self.desc.text()
        for st in seq.steps:                                 # un outil du document n'existe pas ailleurs
            if st.rule == 'outil' and st.tool_id and st.tool_id not in {t.id for t in self.library}:
                st.rule, st.tool_id = KIND_TOOL.get(st.kind, ('', 'fin'))[1], ''
        A.save_user(seq)
        self._fill_choices(seq.name)
        self.load(seq.name)
        return seq.name

    def delete_current(self, confirm: bool = True) -> bool:
        name = self.choice.currentData()
        origin = A.all_sequences().get(name, ('', None))[0]
        if origin != 'utilisateur':
            return False
        if confirm and QMessageBox.question(self, tr('Supprimer l\'automatisme'),
                                            tr('Supprimer « {0} » ?').format(name)) != QMessageBox.StandardButton.Yes:
            return False
        A.delete_user(name)
        self._fill_choices()
        self.load(self.choice.currentData())
        return True


def _params_text(params: dict) -> str:
    """Réglages propres d'une étape, en clair (info-bulle de son nom)."""
    if not params:
        return ''
    from .cam_panel import LABELS, STOCK_3D
    out = []
    for k, v in params.items():
        lab = tr('Crête (mm)') if k == 'crete' else tr(STOCK_3D) if k == 'stock' else tr(LABELS.get(k, k))
        if isinstance(v, bool):
            v = tr('oui') if v else tr('non')
        elif isinstance(v, float):
            v = f'{v:g}'.replace('.', ',')
        out.append(f'{lab} : {v}')
    return tr('Réglages de l\'étape') + '\n' + '\n'.join(out)


def _tool_text(t) -> str:
    if t is None:
        return ''
    d = f'{t.diameter:g}'.replace('.', ',')
    num = f'T{t.number} ' if getattr(t, 'number', 0) else ''
    return f'{num}{t.name} (Ø{d})' if d not in (t.name or '') else f'{num}{t.name}'

