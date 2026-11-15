"""Fiche d'un outil, colonne de droite de « Choisir un outil » (demande du 14/11, 19 h 45) : silhouette, dessins DXF et
STEP de l'outil (ouvrir dans un onglet, poser au clic sur le dessin), caractéristiques modifiables — celles qui ont une
colonne peuvent aussi s'y montrer (case « en colonne », comme le clic droit sur les titres).

« Enregistrer la fiche » : un outil de Mes outils est réécrit dans sa bibliothèque (tools.json) ; un outil du document
est modifié dans le document (gardé avec le formulaire de l'opération) ; un outil d'une bibliothèque de plugin est en
lecture seule (« Garder dans Mes outils » depuis la bibliothèque d'outils pour le modifier). Seuls les champs changés
sont écrits ; une fiche modifiée est enregistrée d'elle-même avant de choisir l'outil ou d'en montrer un autre."""
from __future__ import annotations

import pathlib

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from ..cam import model, toollib
from ..i18n import tr

#: champs de la fiche : (attribut de l'outil, genre) ; le titre est celui de sa colonne (`tool_columns.COLUMNS`),
#: sinon `TITLES`
FIELDS = (('name', 'text'), ('kind', 'kind'), ('number', 'int'), ('diameter', 'num'), ('tip', 'num'),
          ('angle', 'num'), ('cut_length', 'num'), ('stickout', 'num'), ('holder_diameter', 'num'),
          ('flutes', 'int'), ('spindle', 'num'), ('feed', 'num'), ('finish_feed', 'num'), ('plunge', 'num'), ('ramp_feed', 'num'),
          ('step_down', 'num'), ('stepover', 'num'), ('power', 'num'), ('frequency', 'num'), ('vendor', 'text'),
          ('ref', 'text'), ('notes', 'text'))
TITLES = {'name': 'Nom', 'tip': 'Pointe (mm)', 'holder_diameter': 'Ø de l\'écrou de pince / porte-outil (mm)',
          'power': 'Puissance laser (%)', 'frequency': 'Fréquence laser (kHz)', 'notes': 'Notes'}
#: d'où vient l'outil : Mes outils, le document, un plugin (lecture seule), le document en lecture seule (outil d'un
#: programme lu : modifiable dans la liste des outils de la FAO)
MINE, DOC, PLUGIN, DOC_RO = 'mine', 'doc', 'plugin', 'doc_lecture'
DRAWING_TIPS = {'open': 'Ouvrir ce dessin de l’outil dans un nouvel onglet',
                'place': 'Poser ce dessin de l’outil à la souris, sur le dessin en cours'}


def _title(key: str) -> str:
    from .tool_columns import COLUMNS
    return TITLES.get(key) or dict(COLUMNS)[key]


class ToolSheet(QWidget):
    """La fiche ; `tree`, `settings`, `columns_key` : la liste dont les cases « en colonne » montrent les colonnes.
    `saved(tool)` : fiche enregistrée. `modified` : un champ changé depuis l'outil montré."""

    saved = Signal(object)

    def __init__(self, parent=None, tree=None, settings=None, columns_key: str = ''):
        super().__init__(parent)
        from .tool_columns import KEYS
        from .toollib_dialog import PREVIEW
        self.tree, self.settings, self.columns_key = tree, settings, columns_key
        self.tool = None
        self.source = ''
        self.modified = False
        self._loading = False
        #: (outil, clé) → vrai si un autre outil de la liste a encore cette clé de favori (fourni par la liste)
        self.shared_key = None
        self._shown: dict = {}
        self._orig = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.preview = QLabel()
        self.preview.setFixedSize(PREVIEW[0] * 3 // 4, PREVIEW[1] * 3 // 4)
        lay.addWidget(self.preview, 0, Qt.AlignmentFlag.AlignHCenter)
        grid = QGridLayout()
        self.drawing_buttons: dict = {}
        self.drawing_paths: dict = {}
        for row, kind in enumerate(('dxf', 'step')):
            grid.addWidget(QLabel(kind.upper()), row, 0)
            for col, (what, text) in enumerate((('open', tr('Ouvrir')), ('place', tr('Poser au clic'))), 1):
                b = QPushButton(text)
                b.setToolTip(tr(DRAWING_TIPS[what]))
                b.setEnabled(False)
                b.clicked.connect(lambda _=False, k=kind, w=what: self.use_drawing(k, w))
                grid.addWidget(b, row, col)
                self.drawing_buttons[(kind, what)] = b
        lay.addLayout(grid)
        form_w = QWidget()
        form = QGridLayout(form_w)
        self.w: dict = {}
        self.col_boxes: dict = {}
        for row, (key, genre) in enumerate(FIELDS):
            if genre == 'text':
                w = QLineEdit()
                w.textEdited.connect(self._touched)
            elif genre == 'kind':
                w = QComboBox()
                for k, lab in model.TOOL_KINDS.items():
                    w.addItem(tr(lab), k)
                w.activated.connect(self._touched)
            elif genre == 'int':
                w = QSpinBox()
                w.setRange(0, 99999)
                w.valueChanged.connect(self._touched)
            else:
                w = QDoubleSpinBox()
                w.setRange(0, 1e7)
                w.setDecimals(4)
                if key == 'stepover':
                    w.setRange(0, 10)
                    w.setSingleStep(0.05)
                    w.setSuffix(' × Ø')
                w.valueChanged.connect(self._touched)
            self.w[key] = w
            form.addWidget(QLabel(tr(_title(key))), row, 0)
            form.addWidget(w, row, 1)
            if key in KEYS and key != 'name':
                box = QCheckBox(tr('en colonne'))
                box.setToolTip(tr('Montrer cette caractéristique en colonne de la liste (aussi : clic droit sur les '
                                  'titres)'))
                box.toggled.connect(lambda on, k=key: self._show_column(k, on))
                form.addWidget(box, row, 2)
                self.col_boxes[key] = box
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setWidget(form_w)
        lay.addWidget(sc, 1)
        row = QHBoxLayout()
        self.note = QLabel()
        self.note.setWordWrap(True)
        row.addWidget(self.note, 1)
        self.history_btn = QPushButton(tr('Historique…'))
        self.history_btn.setAutoDefault(False)
        self.history_btn.setToolTip(tr('Les changements des vitesses de l’outil (avances, broche), datés'))
        self.history_btn.clicked.connect(lambda: show_history(self, self.tool))
        row.addWidget(self.history_btn)
        self.save_btn = QPushButton(tr('Enregistrer la fiche'))
        self.save_btn.setAutoDefault(False)
        self.save_btn.clicked.connect(lambda: self.save())
        row.addWidget(self.save_btn)
        lay.addLayout(row)
        if tree is not None:                             # colonne montrée ou cachée par le clic droit : cases à jour
            from .tool_columns import listen
            listen(tree, self.sync_columns)
        self.show_tool(None)

    def _touched(self, *_a) -> None:
        if not self._loading and self.tool is not None:
            self.modified = True

    # --- colonnes ---------------------------------------------------------------------------------
    _syncing = False

    def _show_column(self, key: str, on: bool) -> None:
        if self.tree is not None and not self._syncing:
            from .tool_columns import set_shown
            set_shown(self.tree, key, on, self.settings, self.columns_key)

    def sync_columns(self) -> None:
        if self.tree is None:
            return
        from .tool_columns import shown_keys
        shown = set(shown_keys(self.tree))
        self._syncing = True
        try:
            for key, box in self.col_boxes.items():
                box.setChecked(key in shown)
        finally:
            self._syncing = False

    # --- outil ------------------------------------------------------------------------------------
    def _value(self, key: str, genre: str):
        w = self.w[key]
        if genre == 'text':
            return w.text()
        if genre == 'kind':
            return w.currentData()
        return w.value()

    def show_tool(self, t, source: str = '') -> None:
        """La fiche de `t` (None : vide) ; `source` : MINE, DOC (modifiables), PLUGIN, DOC_RO (lecture seule)."""
        self.tool, self.source = t, source
        self.modified = False
        self._orig = model.CamTool.from_dict(t.to_dict()) if t is not None else None
        self.sync_columns()
        editable = t is not None and source in (MINE, DOC)
        for w in self.w.values():
            w.setEnabled(editable)
        self.save_btn.setEnabled(editable)
        self.history_btn.setEnabled(t is not None and bool(getattr(t, 'history', None)))
        self.drawing_paths = {}
        self._loading = True
        try:
            for key, genre in FIELDS:
                w, v = self.w[key], (getattr(t, key, None) if t is not None else None)
                if genre == 'text':
                    w.setText(str(v or ''))
                elif genre == 'kind':
                    i = w.findData(v) if v else 0
                    if i < 0:                            # nature inconnue (plugin, version plus récente) : gardée
                        w.addItem(str(v), v)
                        i = w.count() - 1
                    w.setCurrentIndex(i)
                elif genre == 'int':
                    w.setValue(int(v or 0))
                else:
                    w.setValue(float(v or 0.0))
            self._shown = {key: self._value(key, genre) for key, genre in FIELDS}
        finally:
            self._loading = False
        if t is None:
            self.preview.clear()
            self.preview.setToolTip('')
            self.note.clear()
            self._sync_drawings()
            return
        from .toollib_dialog import silhouette
        self.preview.setPixmap(silhouette(t, self.preview.width(), self.preview.height()))
        self.preview.setToolTip(toollib.summary(t))
        self.note.setText({MINE: tr('Mes outils : enregistré dans la bibliothèque'),
                           DOC: tr('Outil du document : gardé avec le formulaire de l’opération'),
                           PLUGIN: tr('Bibliothèque d’un plugin : lecture seule'),
                           DOC_RO: tr('Outil du document : à modifier dans la liste des outils de la FAO')}
                          .get(source, ''))
        for kind in ('dxf', 'step'):
            p = str((t.drawings or {}).get(kind) or '')
            if p and pathlib.Path(p).is_file():
                self.drawing_paths[kind] = p
        self._sync_drawings()

    def read_into(self, t) -> list:
        """Les champs changés depuis l'outil montré, écrits dans `t` (les autres gardent leur valeur exacte) ; le
        catalogue suit le fabricant et la référence. Rend les attributs écrits."""
        done = []
        for key, genre in FIELDS:
            v = self._value(key, genre)
            if v == self._shown.get(key):
                continue
            if genre == 'text':
                v = v.strip()
                if key == 'name' and not v:
                    continue
            elif genre == 'int':
                v = int(v)
            elif genre == 'num':
                v = float(v)
            if key in model.FEED_KEYS and abs(float(getattr(t, key, 0.0) or 0.0) - v) > 1e-9:
                model.note_change(t, key, getattr(t, key, 0.0), v, tr('fiche de l’outil'))
            setattr(t, key, v)
            done.append(key)
        if 'vendor' in done or 'ref' in done:
            t.catalog = dict(t.catalog or {}, fournisseur=t.vendor, reference=t.ref)
        return done

    def save(self, emit: bool = True) -> bool:
        """La fiche dans l'outil (et dans Mes outils pour un de ses outils) ; rend vrai si enregistrée. Fichier
        illisible ou impossible à écrire : rien n'est changé, la raison est écrite sous la fiche."""
        t = self.tool
        if t is None or self.source not in (MINE, DOC):
            return False
        if self.source == MINE:
            path = toollib.default_path()
            try:
                tools = toollib.load(path)
                at = next((i for i, x in enumerate(tools) if x.id == t.id), None)
                if at is None:                           # fichier sans identifiants (NeoDrive…) : le même outil
                    hit = toollib.find_match(self._orig or t, tools)
                    at = next((i for i, x in enumerate(tools) if x is hit), None)
                if at is None:
                    self.note.setText(tr('Outil introuvable dans Mes outils : fiche non enregistrée'))
                    return False
                c = model.CamTool.from_dict(tools[at].to_dict())
                self.read_into(c)
                tools[at] = c
                toollib.save(tools, path)
            except (OSError, ValueError) as ex:
                self.note.setText(tr('Fiche non enregistrée : {0}').format(ex))
                return False
        before = toollib.favorite_key(t)
        self.read_into(t)
        from . import tool_favorites as FAV                # favori renommé, recoté : il le reste, à sa place ;
        shared = self.shared_key is not None and self.shared_key(t, before)    # une copie : l'original aussi
        FAV.rekey(self.settings, before, toollib.favorite_key(t), keep=bool(shared))
        self.show_tool(t, self.source)
        if emit:
            self.saved.emit(t)
        return True

    def save_if_modified(self) -> bool:
        """Une fiche modifiée : enregistrée ; rend vrai si elle l'a été."""
        return bool(self.modified) and self.save()

    # --- dessins ----------------------------------------------------------------------------------
    def main_window(self):
        w = self.parent()
        while w is not None and not (hasattr(w, 'open_path') and hasattr(w, 'place_symbol_by_click')):
            w = w.parent()
        return w

    def _direct(self, win) -> bool:
        """La fenêtre de la fiche s'ouvre directement sur celle de VectorDrive (pas depuis le formulaire d'une
        opération, qui resterait ouvert pendant que le dessin s'ouvre ou se pose)."""
        dlg = self.window()
        p = dlg.parentWidget() if dlg is not None else None
        return p is not None and p.window() is win

    def _sync_drawings(self) -> None:
        win = self.main_window()
        direct = win is not None and self._direct(win)
        for (kind, what), b in self.drawing_buttons.items():
            b.setEnabled(direct and kind in self.drawing_paths)
            tip = tr(DRAWING_TIPS[what])
            if kind in self.drawing_paths:
                tip += '\n' + self.drawing_paths[kind]
                if not direct:
                    tip += '\n' + tr('Depuis la bibliothèque d’outils, ou le formulaire de l’opération fermé')
            b.setToolTip(tip)

    def use_drawing(self, kind: str, what: str) -> bool:
        """Le dessin de l'outil : ouvert dans un nouvel onglet ou posé au clic ; la fenêtre du choix se ferme."""
        path, win = self.drawing_paths.get(kind, ''), self.main_window()
        if not path or win is None or not self._direct(win):
            return False
        dlg = self.window()
        if dlg is not None and dlg is not win and hasattr(dlg, 'reject'):
            dlg.reject()
        if what == 'open':
            return bool(win.open_path(path))
        return bool(win.place_symbol_by_click(path))


#: titres des vitesses dans l'historique
FEED_TITLES = {'spindle': 'Broche (tr/min)', 'feed': 'Avance (mm/min)', 'finish_feed': 'Avance de finition (mm/min)',
               'plunge': 'Plongée (mm/min)', 'ramp_feed': 'Rampe (mm/min)'}


def show_history(parent, tool, exec_dialog: bool = True):
    """L'historique des vitesses de `tool` dans une fenêtre (rendue sans l'ouvrir si `exec_dialog` est faux)."""
    from PySide6.QtWidgets import QDialog, QDialogButtonBox, QPlainTextEdit
    dlg = QDialog(parent)
    dlg.setWindowTitle(tr('Historique des vitesses : {0}').format(getattr(tool, 'name', '') if tool else ''))
    dlg.resize(560, 360)
    lay = QVBoxLayout(dlg)
    text = QPlainTextEdit()
    text.setReadOnly(True)
    lines = model.history_lines(tool, {k: tr(v) for k, v in FEED_TITLES.items()}) if tool is not None else []
    text.setPlainText('\n'.join(lines) or tr('Aucun changement des vitesses enregistré pour cet outil'))
    lay.addWidget(text)
    bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    bb.rejected.connect(dlg.reject)
    lay.addWidget(bb)
    dlg.history_text = text
    if not exec_dialog:
        return dlg
    dlg.exec()
    dlg.deleteLater()
    return None
