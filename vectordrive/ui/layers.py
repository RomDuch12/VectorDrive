"""Panneau Calques (calque = outil = couleur, comme TypeEdit) et éditeur
de la table des outils."""
from __future__ import annotations

import unicodedata

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView, QLineEdit,
                               QMenu, QPushButton, QStyle, QStyledItemDelegate, QStyleOptionButton, QTableWidget,
                               QTableWidgetItem, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from ..core.document import Group, Layer, Tool
from ..i18n import tr


def swatch(color: str, size: int = 14) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(QColor(color))
    return QIcon(pm)


def _leaves(items):
    for it in items:
        if isinstance(it, Group):
            yield from _leaves(it.children)
        else:
            yield it


def _set_tool(items, tool: int) -> None:
    for it in items:
        it.tool = tool
        if isinstance(it, Group):
            _set_tool(it.children, tool)


def _plain(text: str) -> str:
    """Pour comparer : sans casse ni accents (« Plan GRAVE » trouve « gravé »)."""
    return ''.join(c for c in unicodedata.normalize('NFD', text) if not unicodedata.combining(c)).casefold()


#: ligne du calque des trajectoires FAO (pas un calque du dessin)
TRAJ = '__trajectoires__'
#: une ligne du calque Trajectoires dépliée : un parcours (son rang dans la liste des parcours en UserRole + 1)
TRAJ_PATH = '__parcours__'


class CheckHeader(QHeaderView):
    """En-tête du panneau des calques : une case au-dessus de celles des calques, qui les coche ou les décoche tous ;
    partielle quand certains seulement sont affichés."""

    def __init__(self, panel):
        super().__init__(Qt.Orientation.Horizontal, panel.tree)
        self.panel = panel
        self.state = Qt.CheckState.Checked
        self.setSectionsClickable(True)
        self.setToolTip(tr('Case de la première colonne : afficher ou masquer tous les calques '
                           '(le calque actif reste affiché)') + '\n' +
                        tr('Glisser le bord d’un titre : largeur de la colonne ; double-clic sur le titre : largeur de '
                           'son contenu (retenues)'))
        self.sectionDoubleClicked.connect(self._double)

    def _double(self, index: int) -> None:
        """Double-clic sur un titre : la case de la première colonne prend le second clic ; une autre colonne
        s'ajuste à son contenu."""
        if index == self.panel.COL_VIS:
            self.panel.toggle_all()
        elif index >= 0:
            self.panel.auto_width(index)

    def _indicator(self) -> int:
        return self.style().pixelMetric(QStyle.PixelMetric.PM_IndicatorWidth, None, self)

    def box_rect(self, rect: QRect) -> QRect:
        n = self._indicator()
        return QRect(rect.x() + (rect.width() - n) // 2, rect.y() + (rect.height() - n) // 2, n, n)

    def paintSection(self, painter, rect, index) -> None:          # noqa: N802 (API Qt)
        painter.save()
        super().paintSection(painter, rect, index)
        painter.restore()
        if index != self.panel.COL_VIS:
            return
        opt = QStyleOptionButton()
        opt.rect = self.box_rect(rect)
        on = {Qt.CheckState.Checked: QStyle.StateFlag.State_On, Qt.CheckState.Unchecked: QStyle.StateFlag.State_Off}
        opt.state = QStyle.StateFlag.State_Enabled | on.get(self.state, QStyle.StateFlag.State_NoChange)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_IndicatorCheckBox, opt, painter, self)

    def sectionSizeFromContents(self, index):                      # noqa: N802 (API Qt)
        size = super().sectionSizeFromContents(index)
        if index == self.panel.COL_VIS:
            size.setWidth(max(size.width(), self._indicator() + 10))
        return size

    def mousePressEvent(self, ev) -> None:                         # noqa: N802 (API Qt)
        if ev.button() == Qt.MouseButton.LeftButton and self.logicalIndexAt(ev.position().toPoint()) == self.panel.COL_VIS:
            self.panel.toggle_all()
            ev.accept()
            return
        super().mousePressEvent(ev)


class _NameOnly(QStyledItemDelegate):
    """Seul le nom d'un calque s'édite (double-clic, F2) : l'outil se choisit dans son menu, le nombre se compte."""

    def createEditor(self, parent, option, index):                # noqa: N802 (API Qt)
        if index.column() != LayersPanel.COL_NAME:
            return None
        return super().createEditor(parent, option, index)

    def setEditorData(self, editor, index) -> None:              # noqa: N802 (API Qt)
        super().setEditorData(editor, index)
        if isinstance(editor, QLineEdit):                        # un calque verrouillé : le nom, sans le cadenas
            editor.setText(editor.text().replace('🔒', '').strip())


class LayersPanel(QWidget):
    COL_VIS, COL_NAME, COL_TOOL, COL_N = range(4)

    def __init__(self, win):
        super().__init__()
        self.win = win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        self.find = QLineEdit()
        self.find.setPlaceholderText(tr('Filtrer les calques…'))
        self.find.setToolTip(tr('Ne montre que les calques dont le nom ou l’outil contient ce texte ; '
                                'Entrée active le premier'))
        self.find.setClearButtonEnabled(True)
        self.find.textChanged.connect(lambda _text: self._apply_filter())
        self.find.returnPressed.connect(self.activate_first)
        lay.addWidget(self.find)
        self.tree = QTreeWidget()
        self.header_box = CheckHeader(self)                   # case de l'en-tête : tous les calques
        self.tree.setHeader(self.header_box)
        self.tree.setHeaderLabels(['', tr('Calque'), tr('Outil'), tr('Objets')])
        self.tree.setRootIsDecorated(False)
        h = self.tree.header()
        # colonnes réglables : glisser un bord ; double-clic sur un titre (ou un bord) : largeur du contenu ; retenues
        h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        h.setSectionResizeMode(self.COL_VIS, QHeaderView.ResizeMode.Fixed)
        h.setStretchLastSection(True)                         # Objets jusqu'au bord : pas de vide à droite
        h.setMinimumSectionSize(24)
        h.resizeSection(self.COL_VIS, h.sectionSizeFromContents(self.COL_VIS).width())
        self._widths_busy = False
        self._widths_set = self._restore_widths()
        h.sectionResized.connect(lambda i, _old, new: self._width_changed(i))
        self.tree.itemChanged.connect(self._changed)
        self.tree.itemClicked.connect(self._clicked)
        self.tree.itemDoubleClicked.connect(self._double)
        # clic droit sur un calque (comme TypeEdit) : lui seul visible, et actif
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._solo_at)
        #: (dessin, calque, {id : visible}) : la visibilité d'avant le dernier « seul visible »
        self._solo_before = None
        self.tree.setItemDelegate(_NameOnly(self.tree))       # double-clic sur le nom : le renommer
        self.tree.setExpandsOnDoubleClick(False)              # Trajectoires : un clic le déplie
        self.tree.itemExpanded.connect(lambda it: self._traj_folded(it, True))
        self.tree.itemCollapsed.connect(lambda it: self._traj_folded(it, False))
        #: calque Trajectoires déplié (une ligne par parcours)
        self.traj_open = False
        lay.addWidget(self.tree, 1)
        bar = QHBoxLayout()
        for text, tip, slot in (('+', tr('Nouveau calque'), self.add_layer),
                                ('−', tr('Supprimer le calque (ses objets vont au calque précédent)'), self.delete_layer),
                                ('↑', tr('Monter'), lambda: self.move_layer(-1)),
                                ('↓', tr('Descendre'), lambda: self.move_layer(1)),
                                ('⇥', tr('Envoyer la sélection dans ce calque'), self.selection_to_layer),
                                ('▣', tr('Sélectionner les objets du calque'), self.select_layer),
                                ('🔒', tr('Verrouiller / déverrouiller'), self.toggle_lock),
                                ('◐', tr('Inverser la visibilité : les calques affichés sont masqués, les masqués '
                                         'affichés'), self.invert_visibility)):
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, s=slot: s())
            bar.addWidget(b)
        bar.addStretch(1)
        tools = QPushButton(tr('Outils…'))
        tools.setToolTip(tr('Table des outils : couleurs et noms'))
        tools.clicked.connect(self.edit_tools)
        bar.addWidget(tools)
        lay.addLayout(bar)
        self._loading = False

    # --- largeur des colonnes ------------------------------------------------------
    #: largeurs retenues des colonnes Calque et Outil (« 140,90 »)
    WIDTHS_KEY = 'calques/largeurs'

    def _restore_widths(self) -> bool:
        """Largeurs retenues des colonnes Calque et Outil ; vrai si elles l'étaient."""
        settings = getattr(self.win, 'settings', None)
        raw = str(settings.value(self.WIDTHS_KEY, '') or '') if settings is not None else ''
        try:
            got = [int(float(x)) for x in raw.split(',') if x.strip()]
        except ValueError:
            got = []
        if len(got) != 2:
            return False
        self._widths_busy = True
        try:
            for c, w in zip((self.COL_NAME, self.COL_TOOL), got):
                self.tree.header().resizeSection(c, max(24, w))
        finally:
            self._widths_busy = False
        return True

    def _default_widths(self) -> None:
        """Première ouverture : la largeur du panneau partagée entre Calque (60 %) et Outil, Objets à son contenu."""
        h = self.tree.header()
        n = max(self.tree.sizeHintForColumn(self.COL_N), h.sectionSizeFromContents(self.COL_N).width())
        rest = max(120, self.tree.viewport().width() - h.sectionSize(self.COL_VIS) - n)
        self._widths_busy = True
        try:
            h.resizeSection(self.COL_NAME, int(rest * 0.6))
            h.resizeSection(self.COL_TOOL, rest - int(rest * 0.6))
        finally:
            self._widths_busy = False

    def showEvent(self, ev) -> None:                           # noqa: N802 (API Qt)
        super().showEvent(ev)
        if not self._widths_set:
            self._widths_set = True
            self._default_widths()

    def _width_changed(self, col: int) -> None:
        """Une largeur glissée ou ajustée : retenue."""
        settings = getattr(self.win, 'settings', None)
        if self._widths_busy or col not in (self.COL_NAME, self.COL_TOOL) or settings is None:
            return
        self._widths_set = True
        h = self.tree.header()
        settings.setValue(self.WIDTHS_KEY, f'{h.sectionSize(self.COL_NAME)},{h.sectionSize(self.COL_TOOL)}')

    def auto_width(self, col: int) -> int:
        """La colonne `col` à la largeur de son contenu et de son titre (retenue) ; rend sa largeur."""
        if col in (self.COL_NAME, self.COL_TOOL):
            self.tree.resizeColumnToContents(col)
        return self.tree.header().sectionSize(col)

    # --- accès ---------------------------------------------------------------
    @property
    def doc(self):
        return self.win.canvas.doc

    def current_layer(self) -> Layer | None:
        it = self.tree.currentItem()
        if it is None:
            return self.doc.active_layer
        lid = it.data(self.COL_NAME, Qt.ItemDataRole.UserRole)
        return next((L for L in self.doc.layers if L.id == lid), None)

    def all_state(self) -> Qt.CheckState:
        """Case de l'en-tête : cochée si tous les calques sont affichés, vide si aucun, partielle sinon."""
        layers = self.doc.layers
        n = sum(1 for L in layers if L.visible)
        return Qt.CheckState.Checked if n == len(layers) else (
            Qt.CheckState.Unchecked if n == 0 else Qt.CheckState.PartiallyChecked)

    def _sync_header(self) -> None:
        self.header_box.state = self.all_state()
        self.header_box.viewport().update()

    def toggle_all(self) -> None:
        """Case de l'en-tête : tous les calques affichés, ou tous masqués s'ils l'étaient déjà ; le calque actif reste
        affiché, comme avec la case « Tous » de la liste des calques."""
        self.win.set_all_layers_visible(self.all_state() != Qt.CheckState.Checked)
        self._sync_header()

    def refresh(self) -> None:
        self._loading = True
        self.tree.clear()
        active = self.doc.active_layer
        for L in self.doc.layers:
            n = sum(1 for _ in _leaves(L.items))
            col = self.doc.tool_color(L.tool)
            tname = next((t.name for t in self.doc.tools if t.index == L.tool), tr('Outil {0}').format(L.tool))
            it = QTreeWidgetItem(['', L.name, tname, str(n)])
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEditable)
            it.setCheckState(self.COL_VIS, Qt.CheckState.Checked if L.visible else Qt.CheckState.Unchecked)
            it.setIcon(self.COL_TOOL, swatch(col))
            it.setData(self.COL_NAME, Qt.ItemDataRole.UserRole, L.id)
            if L is active:
                f = QFont()
                f.setBold(True)
                it.setFont(self.COL_NAME, f)
            if L.locked:
                it.setForeground(self.COL_NAME, QBrush(QColor('#999999')))
                it.setText(self.COL_NAME, L.name + '  🔒')
            self.tree.addTopLevelItem(it)
            if L is active:
                self.tree.setCurrentItem(it)
        tps = list(getattr(getattr(self.win, 'cam_panel', None), 'toolpaths', None) or [])
        if tps:                                             # trajectoires calculées : leur calque
            it = QTreeWidgetItem(['', tr('Trajectoires'), tr('FAO'), str(len(tps))])
            it.setFlags((it.flags() | Qt.ItemFlag.ItemIsUserCheckable) & ~Qt.ItemFlag.ItemIsEditable)
            it.setCheckState(self.COL_VIS, Qt.CheckState.Checked if self.win.canvas.toolpaths_visible
                             else Qt.CheckState.Unchecked)
            it.setData(self.COL_NAME, Qt.ItemDataRole.UserRole, TRAJ)
            f = QFont()
            f.setItalic(True)
            it.setFont(self.COL_NAME, f)
            it.setToolTip(self.COL_NAME, tr('Trajectoires FAO calculées, en 2.5D (teinte selon la profondeur) '
                                            'et en 3D — pas un calque du dessin : ni usiné, ni exporté. Un clic : '
                                            'une ligne par parcours'))
            self.tree.addTopLevelItem(it)
            self._traj_children(it, tps)
        self._loading = False
        self._sync_header()
        self._apply_filter()
        key = (id(self.doc), active.id, active.tool)
        if getattr(self, '_tool_from', None) != key:     # un autre calque, ou son outil changé : sa couleur ; sinon la
            self._tool_from = key                        # couleur courante choisie dans le panneau Couleur est gardée
            self.win.canvas.current_tool_index = active.tool
        if hasattr(self.win, 'lbl_layer'):
            self.win._layer_status()
        if hasattr(self.win, '_refresh_layer_tabs'):
            self.win._refresh_layer_tabs()

    def _apply_filter(self) -> None:
        wanted = _plain(self.find.text().strip())
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            it.setHidden(bool(wanted) and wanted not in _plain(it.text(self.COL_NAME)) and
                         wanted not in _plain(it.text(self.COL_TOOL)))

    def _traj_children(self, row, tps) -> None:
        """Les lignes des parcours sous Trajectoires : case (montré ou caché), nom, outil et sa couleur de parcours,
        nombre de mouvements."""
        from .cam_panel import path_colors
        cp = getattr(self.win, 'cam_panel', None)
        try:
            tools = {t.id: t for t in cp.setup().tools} if cp is not None else {}
        except Exception:                                   # réglage FAO illisible : outils lus des parcours
            tools = {}
        colors = path_colors()
        for i, tp in enumerate(tps):
            tool = tools.get(tp.tool_id) or getattr(tp, 'tool_guess', None)
            tname = getattr(tool, 'name', '') or ('—' if tp.op_id else tr('Programme'))
            src = getattr(tp, 'tool_source', None)
            unknown = not tp.op_id and tool is not None and tp.tool_id not in tools and src == ''
            ch = QTreeWidgetItem(['', tp.name or '—', tname + (' ?' if unknown else ''), str(len(tp.moves))])
            if not tp.op_id and tool is not None:
                tip = (tr('Outil inconnu des bibliothèques : le double-clic propose de le créer, d’après le programme, '
                          'ou de choisir un outil existant') if unknown else
                       tr('Outil choisi à la place de celui du programme : {0}').format(tr(src) if src else
                                                                                        tr('Outils du document'))
                       if getattr(tp, 'tool_alias', False) else
                       tr('Outil reconnu : {0}').format(tr(src)) if src else tr('Outil du document'))
                ch.setToolTip(self.COL_TOOL, tip + '\n' + tr('Double-clic sur l’outil : en choisir un autre (document, '
                                                             'Mes outils, bibliothèques)'))
            ch.setFlags((ch.flags() | Qt.ItemFlag.ItemIsUserCheckable) & ~Qt.ItemFlag.ItemIsEditable)
            ch.setCheckState(self.COL_VIS, Qt.CheckState.Checked if getattr(tp, 'shown', True) else Qt.CheckState.Unchecked)
            ch.setIcon(self.COL_TOOL, swatch(colors[i % len(colors)]))
            ch.setData(self.COL_NAME, Qt.ItemDataRole.UserRole, TRAJ_PATH)
            ch.setData(self.COL_NAME, Qt.ItemDataRole.UserRole + 1, i)
            ch.setToolTip(self.COL_NAME, tr('Double-clic : le formulaire complet de son opération ; validé, le '
                                            'parcours est recalculé') if tp.op_id else
                          tr('Parcours lu d’un programme. Double-clic : en faire une opération (son tracé repris dans '
                             'un calque), au formulaire complet ; validée, son parcours remplace celui du programme'))
            row.addChild(ch)
        row.setExpanded(self.traj_open)
        self._traj_icon(row)

    def _traj_icon(self, row) -> None:
        sp = QStyle.StandardPixmap.SP_ArrowDown if row.isExpanded() else QStyle.StandardPixmap.SP_ArrowRight
        row.setIcon(self.COL_NAME, self.style().standardIcon(sp))

    def _traj_folded(self, item, opened: bool) -> None:
        if item.data(self.COL_NAME, Qt.ItemDataRole.UserRole) == TRAJ:
            self.traj_open = opened
            self._traj_icon(item)

    def traj_row(self):
        """La ligne Trajectoires (None : aucun parcours)."""
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            if it.data(self.COL_NAME, Qt.ItemDataRole.UserRole) == TRAJ:
                return it
        return None

    def show_paths(self) -> None:
        """Trajectoires déplié : une ligne par parcours."""
        self.traj_open = True
        row = self.traj_row()
        if row is not None:
            row.setExpanded(True)

    def sync_paths(self) -> None:
        """Les cases des lignes des parcours suivent la liste des parcours du panneau FAO."""
        row, cp = self.traj_row(), getattr(self.win, 'cam_panel', None)
        if row is None or cp is None:
            return
        self._loading = True
        try:
            for k in range(row.childCount()):
                ch = row.child(k)
                i = ch.data(self.COL_NAME, Qt.ItemDataRole.UserRole + 1)
                if isinstance(i, int) and 0 <= i < len(cp.toolpaths):
                    ch.setCheckState(self.COL_VIS, Qt.CheckState.Checked if getattr(cp.toolpaths[i], 'shown', True)
                                     else Qt.CheckState.Unchecked)
        finally:
            self._loading = False

    def activate_first(self) -> None:
        """Le premier calque montré devient le calque actif."""
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            if not it.isHidden() and it.data(self.COL_NAME, Qt.ItemDataRole.UserRole) != TRAJ:
                self.tree.setCurrentItem(it)
                self._clicked(it, self.COL_NAME)
                return

    # --- édition -------------------------------------------------------------
    def _changed(self, item, col) -> None:
        if self._loading:
            return
        lid = item.data(self.COL_NAME, Qt.ItemDataRole.UserRole)
        if lid == TRAJ_PATH:                                # un parcours montré ou caché
            cp = getattr(self.win, 'cam_panel', None)
            i = item.data(self.COL_NAME, Qt.ItemDataRole.UserRole + 1)
            if col == self.COL_VIS and cp is not None and isinstance(i, int):
                cp.set_path_shown(i, item.checkState(self.COL_VIS) == Qt.CheckState.Checked)
            return
        if lid == TRAJ:
            if col == self.COL_VIS:
                # le panneau est refait : pas pendant le signal de la ligne elle-même
                from PySide6.QtCore import QTimer
                on = item.checkState(self.COL_VIS) == Qt.CheckState.Checked
                QTimer.singleShot(0, lambda: self.win.set_toolpaths_visible(on))
            return
        L = next((x for x in self.doc.layers if x.id == lid), None)
        if L is None:
            return
        if col == self.COL_VIS:
            L.visible = item.checkState(self.COL_VIS) == Qt.CheckState.Checked
            self._sync_header()
            self.win.canvas.update()
        elif col == self.COL_NAME:
            name = item.text(self.COL_NAME).replace('🔒', '').strip()     # le cadenas, même sans ses espaces
            if name and name != L.name:
                self.win.push_undo()
                L.name = name
                self.win._on_doc_changed()

    def _clicked(self, item, col) -> None:
        lid = item.data(self.COL_NAME, Qt.ItemDataRole.UserRole)
        if lid == TRAJ:                                     # un clic (hors de la case) : déplié ou replié
            if col != self.COL_VIS and item.childCount():
                item.setExpanded(not item.isExpanded())
            return
        if lid == TRAJ_PATH:
            return
        L = self.current_layer()
        if L is not None:
            self.doc.active = L.id
            self.win.canvas.current_tool_index = L.tool
            self._mark_active()

    def _solo_at(self, pos) -> None:
        item = self.tree.itemAt(pos)
        if item is None:
            return
        lid = item.data(self.COL_NAME, Qt.ItemDataRole.UserRole)
        if lid in (TRAJ, TRAJ_PATH):
            return
        self.solo(lid)

    def solo(self, lid) -> bool:
        """Clic droit sur un calque (demande du 19/11, comme TypeEdit) : lui seul visible, et actif. Le même clic
        droit sur ce calque, resté seul visible, rend la visibilité d'avant (il reste actif). Rend vrai si fait."""
        doc = self.doc
        L = next((x for x in doc.layers if x.id == lid), None)
        if L is None:
            return False
        memo = self._solo_before
        alone = L.visible and not any(x.visible for x in doc.layers if x is not L)
        if alone and memo is not None and memo[0] == id(doc) and memo[1] == lid:
            for x in doc.layers:
                if x.id in memo[2]:
                    x.visible = memo[2][x.id]
            L.visible = True
            self._solo_before = None
            msg = tr('Calques : la visibilité d’avant est rendue')
        else:
            self._solo_before = (id(doc), lid, {x.id: x.visible for x in doc.layers})
            for x in doc.layers:
                x.visible = x is L
            msg = tr('Calque « {0} » seul visible, et actif (clic droit de nouveau : la visibilité d’avant)').format(
                L.name)
        doc.active = L.id
        self.win.canvas.current_tool_index = L.tool
        follow = getattr(self.win, '_layers_visibility_changed', None)
        if callable(follow):
            follow()
        else:
            self.win.canvas.invalidate()
            self.refresh()
        bar = getattr(self.win, 'statusBar', None)
        if callable(bar):
            bar().showMessage(msg, 6000)
        return True

    def _mark_active(self) -> None:
        """Le calque actif en gras, les cases à jour, sans refaire la liste : le double-clic qui suit le clic tombe
        sur la même ligne (renommer, choisir l'outil)."""
        active = self.doc.active_layer
        by_id = {L.id: L for L in self.doc.layers}
        self._loading = True
        try:
            for i in range(self.tree.topLevelItemCount()):
                it = self.tree.topLevelItem(i)
                L = by_id.get(it.data(self.COL_NAME, Qt.ItemDataRole.UserRole))
                if L is None:
                    continue
                f = it.font(self.COL_NAME)
                f.setBold(L is active)
                it.setFont(self.COL_NAME, f)
        finally:
            self._loading = False
        if hasattr(self.win, 'lbl_layer'):
            self.win._layer_status()
        if hasattr(self.win, '_refresh_layer_tabs'):
            self.win._refresh_layer_tabs()               # onglets ouverts : le calque actif devient visible
        self._loading = True
        try:
            for i in range(self.tree.topLevelItemCount()):
                it = self.tree.topLevelItem(i)
                L = by_id.get(it.data(self.COL_NAME, Qt.ItemDataRole.UserRole))
                if L is not None:
                    it.setCheckState(self.COL_VIS, Qt.CheckState.Checked if L.visible else Qt.CheckState.Unchecked)
        finally:
            self._loading = False
        self._sync_header()

    def _double(self, item, col) -> None:
        lid = item.data(self.COL_NAME, Qt.ItemDataRole.UserRole)
        if lid == TRAJ_PATH:                                # le formulaire de l'opération du parcours
            cp = getattr(self.win, 'cam_panel', None)
            i = item.data(self.COL_NAME, Qt.ItemDataRole.UserRole + 1)
            if cp is not None and isinstance(i, int) and 0 <= i < len(cp.toolpaths):
                tp = cp.toolpaths[i]
                if col == self.COL_TOOL and not tp.op_id:   # l'outil d'un programme lu : en choisir un autre
                    cp.choose_program_tool(tp)
                else:
                    cp.toolpath_form(tp)
            return
        if lid == TRAJ or col != self.COL_TOOL:
            return
        L = self.current_layer()
        menu = QMenu(self)
        for t in self.doc.tools:
            a = menu.addAction(swatch(t.color), f'{t.index} — {t.name}')
            a.setData(t.index)
        chosen = menu.exec(self.tree.viewport().mapToGlobal(self.tree.visualItemRect(item).bottomLeft()))
        menu.deleteLater()                                # libéré au retour à la boucle (chosen lu avant)
        if chosen is not None and L is not None:
            self.win.push_undo()
            L.tool = chosen.data()
            _set_tool(L.items, L.tool)
            self.win.canvas.invalidate()
            self.win._on_doc_changed()

    def add_layer(self) -> None:
        self.win.push_undo()
        n = len(self.doc.layers) + 1
        names = {L.name for L in self.doc.layers}
        name = next(f'Plan {i}' for i in range(n, n + 1000) if f'Plan {i}' not in names)
        tool = (self.doc.active_layer.tool + 1) % max(1, len(self.doc.tools))
        L = Layer(name=name, tool=tool)
        self.doc.layers.append(L)
        self.doc.active = L.id
        self.win._on_doc_changed()

    def delete_layer(self) -> None:
        L = self.current_layer()
        if L is None or len(self.doc.layers) < 2:
            return
        self.win.push_undo()
        i = self.doc.layers.index(L)
        dest = self.doc.layers[i - 1] if i > 0 else self.doc.layers[1]
        dest.items.extend(L.items)
        _set_tool(L.items, dest.tool)
        self.doc.layers.remove(L)
        self.doc.active = dest.id
        self.win.canvas.selection = []
        self.win.canvas.invalidate()
        self.win._on_doc_changed()

    def move_layer(self, d: int) -> None:
        L = self.current_layer()
        if L is None:
            return
        i = self.doc.layers.index(L)
        j = i + d
        if 0 <= j < len(self.doc.layers):
            self.win.push_undo()
            self.doc.layers[i], self.doc.layers[j] = self.doc.layers[j], self.doc.layers[i]
            self.win.canvas.update()
            self.win._on_doc_changed()

    def selection_to_layer(self) -> None:
        L = self.current_layer()
        sel = self.win.canvas.selection
        if L is None or not sel:
            return
        self.win.push_undo()
        ids = {id(s) for s in sel}
        for M in self.doc.layers:
            M.items = [it for it in M.items if id(it) not in ids]
        L.items.extend(sel)
        _set_tool(sel, L.tool)
        self.win.canvas.invalidate()
        self.win._on_doc_changed()

    def select_layer(self) -> None:
        L = self.current_layer()
        if L is not None:
            self.win.canvas.select([it for it in L.items if it.visible])

    def toggle_lock(self) -> None:
        L = self.current_layer()
        if L is not None:
            L.locked = not L.locked
            if L.locked:
                self.win.canvas.select([s for s in self.win.canvas.selection if s not in L.items])
            self.refresh()

    def invert_visibility(self) -> int:
        """Calques affichés masqués et masqués affichés (TypeEdit) ; la
        sélection perd ce qui disparaît. Rend le nombre de calques affichés."""
        for L in self.doc.layers:
            L.visible = not L.visible
        hidden = {id(it) for L in self.doc.layers if not L.visible for it in L.items}
        if any(id(s) in hidden for s in self.win.canvas.selection):
            self.win.canvas.select([s for s in self.win.canvas.selection if id(s) not in hidden])
        self.refresh()
        self.win.canvas.update()
        return sum(1 for L in self.doc.layers if L.visible)

    def edit_tools(self) -> None:
        dlg = ToolsDialog(self.doc.tools, self)
        if dlg.exec():
            self.win.push_undo()
            self.doc.tools = dlg.tools()
            self.win.canvas.invalidate()
            self.win._on_doc_changed()


class ToolsDialog(QDialog):
    """Table des outils : numéro, nom, couleur (double-clic pour changer)."""

    def __init__(self, tools: list[Tool], parent=None):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        self.setWindowTitle(tr('Outils'))
        self.resize(420, 360)
        lay = QVBoxLayout(self)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(['N°', tr('Nom'), tr('Couleur'), tr('Largeur (mm)')])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.cellDoubleClicked.connect(self._pick)
        lay.addWidget(self.table)
        for t in tools:
            self._add(t)
        row = QHBoxLayout()
        add = QPushButton(tr('Ajouter'))
        add.clicked.connect(lambda: self._add(Tool(self.table.rowCount(), '#808080', tr('Outil {0}').format(self.table.rowCount() + 1))))
        rem = QPushButton(tr('Retirer le dernier'))
        rem.clicked.connect(lambda: self.table.setRowCount(max(1, self.table.rowCount() - 1)))
        row.addWidget(add)
        row.addWidget(rem)
        row.addStretch(1)
        lay.addLayout(row)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _add(self, t: Tool) -> None:
        r = self.table.rowCount()
        self.table.insertRow(r)
        n = QTableWidgetItem(str(t.index))
        n.setFlags(n.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(r, 0, n)
        self.table.setItem(r, 1, QTableWidgetItem(t.name))
        c = QTableWidgetItem(t.color)
        c.setIcon(swatch(t.color))
        c.setFlags(c.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(r, 2, c)
        self.table.setItem(r, 3, QTableWidgetItem(f'{getattr(t, "width", 0.0):g}'))

    def _pick(self, row: int, col: int) -> None:
        if col != 2:
            return
        from .color_picker import get_color
        c = get_color(QColor(self.table.item(row, 2).text()), self, tr('Couleur de l\'outil'))
        if c is not None:
            it = self.table.item(row, 2)
            it.setText(c.name())
            it.setIcon(swatch(c.name()))

    def tools(self) -> list[Tool]:
        def width(r):
            it = self.table.item(r, 3)
            try:
                return max(0.0, float((it.text() if it else '0').replace(',', '.')))
            except ValueError:
                return 0.0
        return [Tool(int(self.table.item(r, 0).text()), self.table.item(r, 2).text(),
                     self.table.item(r, 1).text(), width(r)) for r in range(self.table.rowCount())]
