"""Fenêtre « Espace de travail » : la table de la machine et le matériel de
serrage — étaux, mandrins, brides, cales, blocs, modèles STEP / STL —
autour de la pièce (`core.workspace`) : liste des éléments, dimensions et
position de chacun, étau ou mandrin placé pour serrer le brut avec la
prise voulue (ou proposée d'après les parcours), vérification des
collisions, espaces gardés sous un nom ; export STEP et exemples STEP à
retoucher dans un logiciel de CAO."""
from __future__ import annotations

import copy

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QMenu,
                               QMessageBox, QPushButton, QVBoxLayout, QWidget)

from ..core import workspace as WS
from ..i18n import tr

#: position : (attribut, libellé, minimum, maximum)
PLACE = (('x', 'X (mm)', -10000.0, 10000.0), ('y', 'Y (mm)', -10000.0, 10000.0),
         ('z', 'Z de la base (mm, haut de la pièce à 0)', -10000.0, 10000.0), ('rot', 'Rotation (°)', -360.0, 360.0))


class WorkspaceDialog(QDialog):
    """`ws` : l'espace du dessin ; `box` : le brut posé (core.stock3d.StockBox)
    ou None ; `toolpaths`, `setup` : les parcours calculés et le réglage FAO
    (prise proposée, vérification)."""

    def __init__(self, parent, ws: WS.Workspace, box=None, toolpaths=(), setup=None, *, setup_key=('', -1),
                 doc=None):
        super().__init__(parent)
        from .fit import release
        release(self)                                    # fermée : détruite, pas gardée par son parent
        self.doc = doc
        self.setup_key = (WS.norm_face(doc, setup_key[0] or '', None, int(setup_key[1])), int(setup_key[1]))
        title = tr('Espace de travail')
        if self.setup_key != ('', -1):                               # une autre prise : son propre matériel
            from ..cam.auto3d import SIDE_LABELS
            face, body = self.setup_key
            bits = [b for b in ((tr('corps {0}').format(body + 1) if body >= 0 else ''),
                                tr(SIDE_LABELS.get(face, face)) if face else '') if b]
            title += ' — ' + tr('prise : {0}').format(', '.join(bits))
        self.setWindowTitle(title)
        self.ws = copy.deepcopy(ws)
        self.box, self.toolpaths, self.setup = box, list(toolpaths or ()), setup
        if setup is not None:                                        # les parcours de cette prise seulement
            ops = {o.id: o for o in setup.operations}            # (comme le contrôle avant écriture)
            self.toolpaths = [t for t in self.toolpaths if WS.op_setup(ops.get(t.op_id), doc) == self.setup_key]
        self._loading = False
        lay = QVBoxLayout(self)
        intro = QLabel(tr('La table de la machine et le matériel de serrage autour de la pièce (Z 0 : le haut de la '
                          'pièce) : montrés dans la vue 3D ; les parcours qui les touchent, outil ou porte-outil, '
                          'sont signalés avant l\'écriture du programme.'))
        intro.setWordWrap(True)
        lay.addWidget(intro)
        # bibliothèque
        lib = QHBoxLayout()
        self.library = QComboBox()
        lib.addWidget(QLabel(tr('Espaces gardés')))
        lib.addWidget(self.library, 1)
        self.load_btn = QPushButton(tr('Charger'))
        self.load_btn.setToolTip(tr('Remplace les éléments par ceux de l\'espace choisi, l\'étau (ou le mandrin) '
                                    'serrant le brut'))
        self.load_btn.clicked.connect(lambda: self.load_library())
        lib.addWidget(self.load_btn)
        self.save_btn = QPushButton(tr('Enregistrer sous…'))
        self.save_btn.clicked.connect(lambda: self.save_library())
        lib.addWidget(self.save_btn)
        self.del_btn = QPushButton(tr('Supprimer'))
        self.del_btn.clicked.connect(lambda: self.delete_library())
        lib.addWidget(self.del_btn)
        self.step_btn = QPushButton(tr('STEP'))
        self.step_btn.setToolTip(tr('Exporter l\'espace en STEP, ou écrire les exemples (étaux, mandrins, broche, '
                                    'machine, table) à modifier dans un logiciel de CAO puis à réimporter'))
        sm = QMenu(self.step_btn)
        sm.addAction(tr('Exporter cet espace en STEP…'), lambda: self.export_step())
        sm.addAction(tr('Écrire les exemples STEP…'), lambda: self.write_examples())
        self.step_btn.setMenu(sm)
        lib.addWidget(self.step_btn)
        lay.addLayout(lib)
        self.library.currentIndexChanged.connect(lambda _i: self._library_buttons())
        # éléments
        mid = QHBoxLayout()
        left = QVBoxLayout()
        self.list = QListWidget()
        self.list.currentRowChanged.connect(lambda _r: self.load_element())
        left.addWidget(self.list, 1)
        btns = QHBoxLayout()
        self.add_btn = QPushButton(tr('Ajouter'))
        menu = QMenu(self.add_btn)
        for k, (label, _p) in WS.KINDS.items():
            menu.addAction(tr(label), (lambda k=k: self.add_element(k)) if k != 'modele' else (lambda: self.add_model()))
        self.add_btn.setMenu(menu)
        btns.addWidget(self.add_btn)
        b = QPushButton(tr('Dupliquer'))
        b.clicked.connect(lambda: self.duplicate_element())
        btns.addWidget(b)
        self.remove_btn = QPushButton(tr('Retirer'))
        self.remove_btn.clicked.connect(lambda: self.remove_element())
        btns.addWidget(self.remove_btn)
        left.addLayout(btns)
        mid.addLayout(left, 1)
        self.form_box = QWidget()
        form = QFormLayout(self.form_box)
        self.name = QLineEdit()
        self.name.textEdited.connect(lambda _t: self.store_element())
        form.addRow(tr('Nom'), self.name)
        self.visible = QCheckBox(tr('Montré et vérifié'))
        self.visible.toggled.connect(lambda _on: self.store_element())
        form.addRow('', self.visible)
        self.place: dict = {}
        for key, label, lo, hi in PLACE:
            sp = self._spin(lo, hi)
            self.place[key] = sp
            form.addRow(tr(label), sp)
        self.spins: dict = {}
        self.rows: dict = {}
        for kind, (_label, params) in WS.KINDS.items():
            for key, label, _default in params:
                sp = self._spin(0.0, 100000.0, 0 if key in WS.INTEGER else 3)
                lab = QLabel(tr(label))
                form.addRow(lab, sp)
                self.spins[(kind, key)], self.rows[(kind, key)] = sp, lab
        prow = QHBoxLayout()
        self.path = QLineEdit()
        self.path.editingFinished.connect(lambda: self.store_element())
        prow.addWidget(self.path, 1)
        b = QPushButton(tr('Choisir…'))
        b.clicked.connect(lambda: self.choose_model())
        prow.addWidget(b)
        self.path_row = QWidget()
        self.path_row.setLayout(prow)
        self.path_label = QLabel(tr('Fichier STEP ou STL'))
        form.addRow(self.path_label, self.path_row)
        mid.addWidget(self.form_box, 2)
        lay.addLayout(mid, 1)
        # serrage
        grip = QHBoxLayout()
        grip.addWidget(QLabel(tr('Prise dans les mors (mm)')))
        self.grip = self._spin(0.0, 1000.0)
        self.grip.setValue(5.0)
        grip.addWidget(self.grip)
        self.clamp_btn = QPushButton(tr('Serrer le brut'))
        self.clamp_btn.setToolTip(tr('Étau ou mandrin choisi centré sur le brut, ouverture à sa largeur, la prise '
                                     'voulue dans les mors ; le reste de l\'espace le suit'))
        self.clamp_btn.clicked.connect(lambda: self.clamp())
        grip.addWidget(self.clamp_btn)
        self.auto_btn = QPushButton(tr('Prise proposée'))
        self.auto_btn.setToolTip(tr('Le plus de prise possible sans que les mors montent à moins d\'1 mm sous les '
                                    'coupes les plus basses près d\'eux'))
        self.auto_btn.clicked.connect(lambda: self.propose_grip())
        grip.addWidget(self.auto_btn)
        grip.addStretch(1)
        self.check_btn = QPushButton(tr('Vérifier les parcours'))
        self.check_btn.clicked.connect(lambda: self.check())
        grip.addWidget(self.check_btn)
        lay.addLayout(grip)
        self.info = QLabel()
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.fill_library()
        self.fill_list(0)

    def _spin(self, lo: float, hi: float, decimals: int = 3) -> QDoubleSpinBox:
        sp = QDoubleSpinBox()
        sp.setRange(lo, hi)
        sp.setDecimals(decimals)
        sp.valueChanged.connect(lambda _v: self.store_element())
        return sp

    def value(self) -> WS.Workspace:
        return copy.deepcopy(self.ws)

    # --- éléments -----------------------------------------------------------------------
    def current(self) -> WS.Element | None:
        r = self.list.currentRow()
        return self.ws.elements[r] if 0 <= r < len(self.ws.elements) else None

    def fill_list(self, row: int = -1) -> None:
        self._loading = True
        self.list.clear()
        for e in self.ws.elements:
            kind = tr(WS.KINDS[e.kind][0])
            text = e.label() if not e.name or e.name == kind else f'{e.label()} ({kind})'
            self.list.addItem(text if e.visible else tr('{0} — masqué').format(text))
        self._loading = False
        self.list.setCurrentRow(min(max(row, 0), len(self.ws.elements) - 1) if self.ws.elements else -1)
        self.load_element()

    def load_element(self) -> None:
        if self._loading:
            return
        e = self.current()
        self.form_box.setEnabled(e is not None)
        self.remove_btn.setEnabled(e is not None)
        self._loading = True
        try:
            self.name.setText(e.name if e else '')
            self.visible.setChecked(bool(e and e.visible))
            for key, sp in self.place.items():
                sp.setValue(float(getattr(e, key)) if e else 0.0)
            for (kind, key), sp in self.spins.items():
                on = e is not None and e.kind == kind
                sp.setVisible(on)
                self.rows[(kind, key)].setVisible(on)
                if on:
                    sp.setValue(e.p(key))
            on = e is not None and e.kind == 'modele'
            self.path_row.setVisible(on)
            self.path_label.setVisible(on)
            self.path.setText(e.path if e else '')
        finally:
            self._loading = False
        self.refresh()

    def store_element(self) -> None:
        """Champs → élément choisi."""
        e = self.current()
        if self._loading or e is None:
            return
        e.name = self.name.text().strip()
        e.visible = self.visible.isChecked()
        for key, sp in self.place.items():
            setattr(e, key, float(sp.value()))
        for (kind, key), sp in self.spins.items():
            if kind == e.kind:
                e.params[key] = float(sp.value())
        e.path = self.path.text().strip()
        r = self.list.currentRow()
        item = self.list.item(r)
        if item is not None:
            kind = tr(WS.KINDS[e.kind][0])
            text = e.label() if not e.name or e.name == kind else f'{e.label()} ({kind})'
            item.setText(text if e.visible else tr('{0} — masqué').format(text))
        self.refresh()

    def add_element(self, kind: str, path: str = '') -> WS.Element:
        """Nouvel élément ; un étau ou un mandrin serre le brut s'il est connu,
        un autre élément est posé sous le brut (ou sous la pièce)."""
        import pathlib
        e = WS.Element(kind, pathlib.Path(path).stem if path else tr(WS.KINDS[kind][0]), path=path)
        if kind in ('etau', 'mandrin') and self.box is not None:
            e = WS.clamp_stock(e, self.box, self.grip.value())
        elif self.box is not None:                                  # sous le brut ; une bride sur son bord
            e.x, e.y = self.box.center
            if kind == 'bride':
                e.x, e.z = self.box.x0, self.box.top
            elif kind in ('table', 'machine'):                       # sous tout le reste
                e.z = min([self.box.bottom] + [x.z for x in self.ws.elements]) - e.p('sz')
            elif kind == 'broche':                                   # au-dessus du brut, à l'aplomb
                e.z = self.box.top + 50.0
            elif kind in ('cale', 'bloc'):
                e.z = self.box.bottom - e.p('sz')
            elif kind == 'cylindre':
                e.z = self.box.bottom - e.p('height')
            else:
                t = WS.triangles(e)
                e.z = self.box.bottom - (float(t[:, :, 2].max()) if len(t) else 0.0)
        self.ws.elements.append(e)
        self.fill_list(len(self.ws.elements) - 1)
        return e

    def add_model(self) -> WS.Element | None:
        """Modèle STEP / STL du matériel (étau du fabricant, montage, machine) :
        le fichier choisi, posé sous le brut."""
        f, _ = QFileDialog.getOpenFileName(self, tr('Modèle du matériel'), '',
                                           tr('Modèles 3D (*.step *.stp *.stl);;Tous les fichiers (*)'))
        return self.add_element('modele', path=f) if f else None

    def duplicate_element(self) -> None:
        e = self.current()
        if e is not None:
            self.ws.elements.insert(self.list.currentRow() + 1, copy.deepcopy(e))
            self.fill_list(self.list.currentRow() + 1)

    def remove_element(self) -> None:
        r = self.list.currentRow()
        if 0 <= r < len(self.ws.elements):
            del self.ws.elements[r]
            self.fill_list(r)

    def choose_model(self) -> None:
        f, _ = QFileDialog.getOpenFileName(self, tr('Modèle du matériel'), self.path.text(),
                                           tr('Modèles 3D (*.step *.stp *.stl);;Tous les fichiers (*)'))
        if f:
            self.path.setText(f)
            self.store_element()

    # --- serrage ------------------------------------------------------------------------
    def _clamping(self) -> WS.Element | None:
        e = self.current()
        if e is not None and e.kind in ('etau', 'mandrin'):
            return e
        k = WS.clamping(self.ws)
        return self.ws.elements[k] if k >= 0 else None

    def clamp(self) -> bool:
        """L'étau (ou mandrin) choisi — sinon le premier — serre le brut ; le reste suit."""
        e = self._clamping()
        if e is None or self.box is None:
            self.info.setText(tr('Pour serrer le brut : un étau ou un mandrin, et le brut de la pièce 3D réglé '
                                 '(FAO ▸ Brut de la pièce 3D…).'))
            return False
        k = self.ws.elements.index(e)
        self.ws.elements.insert(0, self.ws.elements.pop(k))         # celui-là mène : le reste le suit
        self.ws = WS.fit_to_stock(self.ws, self.box, self.grip.value())
        self.ws.elements.insert(k, self.ws.elements.pop(0))
        self.fill_list(k)
        return True

    def propose_grip(self) -> list[str]:
        """Prise proposée d'après les parcours (core.workspace.auto_grip), puis serrage."""
        e = self._clamping()
        if e is None or self.box is None:
            self.clamp()
            return []
        g, warn = WS.auto_grip(e, self.box, self.toolpaths, self.setup) if self.setup is not None \
            else WS.grip_for(self.box, None, e.p('jaw_h'))
        self.grip.setValue(g)
        self.clamp()
        if warn:
            self.info.setText(self.info.text() + '\n' + '\n'.join(warn))
        return warn

    def check(self) -> list:
        """Collisions des parcours calculés avec le matériel montré."""
        if self.setup is None or not self.toolpaths:
            self.info.setText(tr('Aucun parcours calculé à vérifier.'))
            return []
        hits = WS.collisions(self.toolpaths, self.setup, self.ws, only=self.setup_key, doc=self.doc)
        if hits:
            self.info.setText('\n'.join([tr('⛔ {0} collision(s) :').format(len(hits))]
                                        + [WS.hit_text(h) for h in hits]))
        else:
            self.info.setText(tr('Aucun parcours ne touche le matériel ({0} parcours vérifiés).')
                              .format(len(self.toolpaths)))
        return hits

    def refresh(self) -> None:
        """Ce qu'il faut savoir de l'élément choisi : haut des mors, prise dans le brut."""
        e = self.current()
        lines = []
        if not self.ws.elements:
            lines.append(tr('Aucun élément : ajouter un étau, un mandrin, une bride… ou charger un espace gardé.'))
        elif e is not None and e.kind in ('etau', 'mandrin'):
            top = WS.jaw_top(e)
            lines.append(tr('Haut des mors : Z {0} mm').format(WS._mm(top)))
            if self.box is not None:
                g = top - self.box.bottom
                if g <= 0:
                    lines.append(tr('Les mors sont sous le brut : ils ne le serrent pas.'))
                elif top > self.box.top + 1e-6:
                    lines.append(tr('Les mors montent au-dessus du brut de {0} mm.').format(WS._mm(top - self.box.top)))
                else:
                    lines.append(tr('Prise dans le brut : {0} mm').format(WS._mm(g)))
                    if g < WS.MIN_GRIP - 1e-9:
                        lines.append(tr('Moins que la prise minimale de {0} mm.').format(WS._mm(WS.MIN_GRIP)))
        elif e is not None and e.kind == 'modele' and e.path and not len(WS.triangles(e)):
            lines.append(tr('Modèle illisible ou introuvable : rien n\'est montré ni vérifié.'))
        if self.box is None:
            lines.append(tr('Brut de la pièce 3D non réglé : l\'étau ne peut pas être placé sur lui.'))
        self.clamp_btn.setEnabled(self.box is not None)
        self.auto_btn.setEnabled(self.box is not None)
        self.check_btn.setEnabled(bool(self.toolpaths) and self.setup is not None)
        self.info.setText('\n'.join(lines))

    # --- bibliothèque -------------------------------------------------------------------
    def fill_library(self, select: str = '') -> None:
        self.library.blockSignals(True)
        self.library.clear()
        origins = {'cœur': tr('livré'), 'plugin': tr('plugin'), 'utilisateur': tr('les miens')}
        for name, (origin, _ws) in sorted(WS.all_workspaces().items(), key=lambda kv: kv[0].lower()):
            self.library.addItem(f'{name} ({origins.get(origin, origin)})', name)
        self.library.setCurrentIndex(max(0, self.library.findData(select)))
        self.library.blockSignals(False)
        self._library_buttons()

    def _library_buttons(self) -> None:
        name = self.library.currentData()
        self.load_btn.setEnabled(name is not None)
        self.del_btn.setEnabled(name in WS.user_workspaces())

    def load_library(self, name: str = '') -> bool:
        name = name or self.library.currentData() or ''
        found = WS.all_workspaces().get(name)
        if found is None:
            return False
        ws = copy.deepcopy(found[1])
        if self.box is not None:
            ws = WS.fit_to_stock(ws, self.box, self.grip.value())
        self.ws.elements = ws.elements
        self.ws.name = ws.name
        self.ws.origin = ws.origin                       # « par rapport au brut » : posé quand le brut est connu
        self.fill_list(0)
        return True

    def save_library(self, name: str = '') -> str:
        if not name:
            name, ok = QInputDialog.getText(self, tr('Enregistrer l\'espace de travail'), tr('Nom'),
                                            text=self.ws.name or '')
            if not ok:
                return ''
        name = name.strip()
        if not name or not self.ws.elements:
            return ''
        ws = self.value()
        ws.name = name
        try:
            WS.save_user(ws)
        except OSError as exc:
            QMessageBox.warning(self, tr('Espace de travail'), str(exc))
            return ''
        self.ws.name = name
        self.fill_library(name)
        return name

    def export_step(self, path: str = '') -> str:
        """L'espace (éléments montrés, à leur place) en STEP ; rend le chemin écrit."""
        if not path:
            import os
            start = os.path.join(str(WS.user_dir()), WS.ascii_stem(self.ws.name or tr('espace')) + '.step')
            path, _ = QFileDialog.getSaveFileName(self, tr('Exporter l\'espace de travail en STEP'), start,
                                                  tr('STEP (*.step *.stp)'))
            if not path:
                return ''
        try:
            n = WS.to_step(self.value(), path)
        except OSError as exc:
            QMessageBox.warning(self, tr('Espace de travail'), str(exc))
            return ''
        self.info.setText(tr('{0} volume(s) écrit(s) dans {1}').format(n, path))
        return path

    def write_examples(self, folder: str = '', open_folder: bool = True) -> list:
        """Exemples STEP (espaces livrés et matériel seul) écrits dans le dossier
        des espaces de travail (sous-dossier « exemples_step »), dossier ouvert."""
        folder = folder or str(WS.user_dir() / 'exemples_step')
        try:
            files = WS.write_examples(folder)
        except OSError as exc:
            QMessageBox.warning(self, tr('Espace de travail'), str(exc))
            return []
        self.info.setText(tr('{0} exemples STEP dans {1} : à ouvrir et modifier dans un logiciel de CAO, puis à '
                             'ajouter ici comme « Modèle 3D importé »').format(len(files), folder))
        if open_folder:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
        return files

    def delete_library(self, name: str = '') -> bool:
        name = name or self.library.currentData() or ''
        ok = WS.delete_user(name)
        self.fill_library()
        return ok
