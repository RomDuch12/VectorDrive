"""Import d'outils en deux temps : voir d'abord, puis importer ce qu'on a
choisi, là où on le range.

Les outils lus (un ou plusieurs fichiers, ou tout un dossier) s'affichent
dans l'arborescence de leur fichier — dossiers d'une base TypeEdit
compris —, chacun avec sa silhouette et sa fiche. Les doublons sont
repérés : ceux déjà dans Mes outils, et ceux répétés dans l'import même
(une base de plusieurs centaines d'outils en contient souvent). Ils sont
décochés d'office. On coche ce qu'on veut (un dossier coche tout son
contenu), on choisit le dossier où ranger l'import, et on importe la
sélection.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QPushButton, QSplitter, QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator,
                               QVBoxLayout, QWidget)

from ..cam import toollib
from ..i18n import tr

ROLE_TOOL = Qt.ItemDataRole.UserRole
ROLE_FOLDER = Qt.ItemDataRole.UserRole + 1
#: racine de Mes outils (le dossier de l'import y est créé tel quel)
ROOT = ''


class ToolImportDialog(QDialog):
    """`imported` : {dossier: [CamTool]} (toollib.import_tree / import_files) ;
    `library` : Mes outils, pour repérer les doublons."""

    def __init__(self, parent, imported: dict, library: list, notes=(), errors=()):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)
        self.setWindowTitle(tr('Importer des outils'))
        self.setSizeGripEnabled(True)
        avail = self.screen().availableGeometry() if self.screen() is not None else None
        self.resize(min(1100, avail.width() - 40) if avail else 1000, min(720, avail.height() - 60) if avail else 680)
        self.imported = imported
        self.library = list(library)
        self.tools = {t.id: t for ts in imported.values() for t in ts}
        self.dups: dict[str, str] = {}                  # id → raison
        seen: list = []
        for ts in imported.values():
            for t in ts:
                d = toollib.find_duplicate(t, self.library)
                if d is not None:
                    self.dups[t.id] = tr('déjà dans Mes outils : {0} ({1})').format(d.name, toollib.folder_of(d))
                else:
                    d = toollib.find_duplicate(t, seen)
                    if d is not None:
                        self.dups[t.id] = tr('répété dans l\'import : {0}').format(toollib.folder_of(d))
                seen.append(t)
        lay = QVBoxLayout(self)
        n = len(self.tools)
        head = QLabel(tr('{0} outil(s) lu(s) dans {1} dossier(s), dont {2} doublon(s) (décochés). Cochez ce qu\'il '
                         'faut importer.').format(n, len(imported), len(self.dups)))
        head.setWordWrap(True)
        lay.addWidget(head)
        row = QHBoxLayout()
        self.filter = QLineEdit()
        self.filter.setPlaceholderText(tr('Chercher (nom, référence, fabricant, Ø)'))
        self.filter.textChanged.connect(self._filter)
        row.addWidget(self.filter, 1)
        for text, slot in ((tr('Tout cocher'), lambda: self.check_all(True)),
                           (tr('Tout décocher'), lambda: self.check_all(False)),
                           (tr('Décocher les doublons'), self.uncheck_duplicates)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, f=slot: f())
            row.addWidget(b)
        lay.addLayout(row)
        split = QSplitter()
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([tr('Outil'), 'Ø', tr('Fabricant'), tr('Référence'), tr('Remarque')])
        hh = self.tree.header()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setStretchLastSection(False)
        self.tree.currentItemChanged.connect(self._current)
        split.addWidget(self.tree)
        side = QWidget()
        sl = QVBoxLayout(side)
        self.preview = QLabel()
        from .toollib_dialog import PREVIEW
        self.preview.setFixedSize(*PREVIEW)
        sl.addWidget(self.preview)
        self.card = QLabel()
        self.card.setWordWrap(True)
        self.card.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        sl.addWidget(self.card)
        sl.addStretch(1)
        split.addWidget(side)
        split.setSizes([700, 260])
        lay.addWidget(split, 1)
        dest = QHBoxLayout()
        dest.addWidget(QLabel(tr('Ranger dans')))
        self.dest = QComboBox()
        self.dest.setEditable(True)
        self.dest.addItem(tr('(Mes outils, à la racine)'), ROOT)
        for f in toollib.folders(self.library):
            if f != toollib.NO_FOLDER:
                self.dest.addItem('📁 ' + f, f)
        self.dest.setToolTip(tr('Dossier de Mes outils où ranger l\'import ; un nom nouveau crée le dossier'))
        dest.addWidget(self.dest, 1)
        self.keep_tree = QCheckBox(tr('Garder l\'arborescence du fichier'))
        self.keep_tree.setChecked(True)
        self.keep_tree.setToolTip(tr('Décoché : tous les outils cochés vont directement dans le dossier choisi'))
        dest.addWidget(self.keep_tree)
        lay.addLayout(dest)
        if notes or errors:
            extra = QLabel('\n'.join([tr('Non lus : {0}').format(len(errors))] * bool(errors) + list(errors)[:4]
                                     + list(notes)[:4]))
            extra.setWordWrap(True)
            extra.setStyleSheet('color: #868e96;')
            lay.addWidget(extra)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.ok = bb.addButton(tr('Importer la sélection'), QDialogButtonBox.ButtonRole.AcceptRole)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.count = QLabel()
        lay.addWidget(self.count)
        self._fill()
        self.tree.itemChanged.connect(lambda *_a: self._update_count())
        self._update_count()

    # --- arbre ---------------------------------------------------------------------------------
    def _folder(self, nodes: dict, name: str) -> QTreeWidgetItem:
        parts = toollib.folder_parts(name) or [name]
        parent = None
        for i, part in enumerate(parts):
            key = toollib.SEP.join(parts[:i + 1])
            it = nodes.get(key)
            if it is None:
                it = nodes[key] = QTreeWidgetItem(['📁 ' + part])
                it.setData(0, ROLE_FOLDER, key)
                it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate)
                it.setCheckState(0, Qt.CheckState.Checked)
                (self.tree.addTopLevelItem(it) if parent is None else parent.addChild(it))
            parent = it
        return parent

    def _fill(self) -> None:
        self.tree.blockSignals(True)
        nodes: dict = {}
        red = QBrush(QColor('#c92a2a'))
        for folder, ts in self.imported.items():
            g = self._folder(nodes, folder)
            for t in ts:
                why = self.dups.get(t.id, '')
                it = QTreeWidgetItem([t.name, f'{t.diameter:g}', t.vendor, t.ref, why])
                it.setData(0, ROLE_TOOL, t.id)
                it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                it.setCheckState(0, Qt.CheckState.Unchecked if why else Qt.CheckState.Checked)
                if why:
                    it.setForeground(4, red)
                g.addChild(it)
        self.tree.expandAll()
        self.tree.blockSignals(False)

    def _tool_items(self):
        it = QTreeWidgetItemIterator(self.tree)
        while it.value():
            if it.value().data(0, ROLE_TOOL):
                yield it.value()
            it += 1

    def check_all(self, on: bool) -> None:
        state = Qt.CheckState.Checked if on else Qt.CheckState.Unchecked
        for i in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(i).setCheckState(0, state)

    def uncheck_duplicates(self) -> None:
        for it in self._tool_items():
            if it.data(0, ROLE_TOOL) in self.dups:
                it.setCheckState(0, Qt.CheckState.Unchecked)

    def set_checked(self, tool_ids, on: bool = True) -> None:
        ids = set(tool_ids)
        for it in self._tool_items():
            if it.data(0, ROLE_TOOL) in ids:
                it.setCheckState(0, Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)

    def _filter(self, text: str) -> None:
        q = text.strip().lower()
        for it in self._tool_items():
            t = self.tools[it.data(0, ROLE_TOOL)]
            it.setHidden(bool(q) and q not in f'{t.name} {t.ref} {t.vendor} {t.diameter:g}'.lower())

    def _current(self, it, _prev=None) -> None:
        tid = it.data(0, ROLE_TOOL) if it is not None else None
        t = self.tools.get(tid)
        if t is None:
            self.preview.clear()
            self.card.setText('')
            return
        from .toollib_dialog import silhouette
        self.preview.setPixmap(silhouette(t))
        lines = [f'<b>{t.name}</b>', f'T{t.number} — {tr(t.kind)} Ø {t.diameter:g}']
        if t.kind == 'conique':
            lines.append(tr('Angle {0:g}°, pointe {1:g} mm').format(t.angle, t.tip))
        if t.ref or t.vendor:
            lines.append(f'{t.vendor} {t.ref}'.strip())
        if t.feed or t.spindle:
            lines.append(tr('Avance {0:g} mm/min, broche {1:g} tr/min').format(t.feed, t.spindle))
        if tid in self.dups:
            lines.append(f'<span style="color:#c92a2a">{self.dups[tid]}</span>')
        self.card.setText('<br>'.join(lines))

    def _update_count(self) -> None:
        n = len(self.checked_ids())
        self.count.setText(tr('{0} outil(s) coché(s)').format(n))
        self.ok.setEnabled(n > 0)

    # --- résultat ----------------------------------------------------------------------------------
    def checked_ids(self) -> list[str]:
        return [it.data(0, ROLE_TOOL) for it in self._tool_items() if it.checkState(0) == Qt.CheckState.Checked]

    def destination(self) -> str:
        i = self.dest.currentIndex()
        text = self.dest.currentText().strip()
        if i >= 0 and self.dest.itemText(i) == text:
            return self.dest.itemData(i) or ROOT
        return toollib.join_folder(text.lstrip('📁').strip())

    def chosen(self) -> dict:
        """{dossier de Mes outils: [outils cochés]}."""
        ids = set(self.checked_ids())
        dest = self.destination()
        out: dict = {}
        for folder, ts in self.imported.items():
            keep = [t for t in ts if t.id in ids]
            if not keep:
                continue
            name = toollib.join_folder(dest, folder) if self.keep_tree.isChecked() else (dest or folder)
            out.setdefault(name or toollib.NO_FOLDER, []).extend(keep)
        return out
