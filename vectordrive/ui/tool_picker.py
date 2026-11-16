"""Choix de l'outil d'une opération par dossiers.

Une bibliothèque de plusieurs centaines d'outils ne tient pas dans une
liste déroulante. La liste de l'opération ne montre que les outils du
document (et celui choisi) ; sa dernière ligne, « Choisir dans Mes
outils… », ouvre l'arborescence des dossiers de Mes outils, avec une
recherche (nom, référence, fabricant, Ø) et la silhouette de l'outil.
L'outil choisi rejoint la liste (et le document à la validation du
formulaire, comme avant).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QGridLayout, QHBoxLayout,
                               QHeaderView, QLabel, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout)

from ..cam import model

from ..cam import toollib, toolprefs
from ..i18n import tr

PICK = '__choisir__'
ROLE = Qt.ItemDataRole.UserRole
#: l'affichage de la liste (tree_memory) et le tri : retrouvés à la prochaine ouverture (demande du 15/11, 23 h 45)
VIEW = 'outils/choix_affichage'
SORT = 'outils/choix_tri'


def lib_label(t) -> str:
    return f'📁 {toollib.folder_of(t)} — {t.name}'


class ToolPickerDialog(QDialog):
    """Arbre des dossiers de Mes outils (et des outils du document) ; rend
    la clé choisie : id d'un outil du document ou « lib:<id> »."""

    #: outils du document modifiables dans la fiche de droite (pas pour l'outil d'un programme lu)
    doc_editable = True

    def __init__(self, parent, doc_tools, library: dict, current=None, settings=None, op_kind: str = '',
                 machine: tuple = ('', '')):
        super().__init__(parent)
        self.setWindowTitle(tr('Choisir un outil'))
        self.machine = tuple(machine or ('', ''))
        self.setSizeGripEnabled(True)
        self.resize(720, 560)
        self.settings = settings
        self.library = library
        self.op_kind = op_kind
        self._doc = {t.id: t for t in doc_tools}
        self._doc_list = list(doc_tools)
        self._current_key = current
        lay = QVBoxLayout(self)
        from .tool_filters import FilterBar, open_large
        self.filters = FilterBar(settings, self)
        self.filters.op.hide()                              # la stratégie : celle de l'opération
        self.filters.set_tools(list(library.values()) + list(doc_tools))
        self.filters.set_machine(self.machine[0], self.machine[1], library.values())
        self.filters.changed.connect(lambda: self._filter(self.search.text()))
        self.search = self.filters.text
        self.search.setPlaceholderText(tr('Chercher (nom, référence, fabricant, Ø) — les dossiers s\'ouvrent'))
        lay.addWidget(self.filters)
        row = QHBoxLayout()
        self.only = QCheckBox(tr('Seulement les outils adaptés'))
        pref = toolprefs.pref_for(op_kind, toolprefs.load(settings)) if op_kind else None
        self.only.setVisible(bool(pref and pref['rules']))
        self.only.setChecked(bool(pref and pref['mode'] == 'seuls'))
        if op_kind:
            self.only.setToolTip(tr('Les outils proposés pour : {0}').format(
                tr(model.op_kinds().get(op_kind, op_kind)).split(' (')[0]))
        self.only.toggled.connect(lambda _c: self._filter(self.search.text()))
        row.addWidget(self.only)
        row.addStretch(1)
        self.prefs_btn = QPushButton(tr('Régler les propositions…'))
        self.prefs_btn.setToolTip(tr('Quels outils proposer, et dans quel ordre, pour chaque type d\'opération'))
        self.prefs_btn.clicked.connect(lambda: self.tool_prefs())
        row.addWidget(self.prefs_btn)
        full = QPushButton('⛶')
        full.setToolTip(tr('Plein écran (F11)'))
        full.setShortcut('F11')
        full.clicked.connect(lambda: self.toggle_full_screen())
        row.addWidget(full)
        lay.addLayout(row)
        open_large(self, settings, 'outils/choix_agrandi', full=True)
        row = QHBoxLayout()
        from . import tool_favorites as FAV                # une étoile devant chaque outil, les favoris en tête
        self.tree = FAV.FavoriteTree(self._favorites_moved)
        self.stars = FAV.StarDelegate(self.tree)
        self.tree.setItemDelegateForColumn(0, self.stars)
        self.stars.toggled.connect(self._star_clicked)
        self._opening = False                            # (dépliage fait par la liste elle-même : pas retenu)
        self.tree.itemExpanded.connect(lambda it: self._fav_folded(it, True))
        self.tree.itemCollapsed.connect(lambda it: self._fav_folded(it, False))
        self.tree.header().sortIndicatorChanged.connect(lambda c, _o: self._lock_favorites(c))
        from .tool_columns import install                 # colonnes arrangeables, n° T dans la sienne (cachée)
        install(self.tree, settings, 'outils/choix_colonnes')
        from .tool_filters import sortable
        sortable(self.tree, lambda: self._refill(), settings, SORT)   # clic sur un titre : trier (retenu) ;
        # troisième clic : l'ordre d'origine
        self.tree.header().setToolTip(tr('Clic sur un titre : trier (croissant, décroissant, puis l’ordre d’origine)'))
        from PySide6.QtCore import QSize
        self.tree.setIconSize(QSize(14, 26))
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setStretchLastSection(False)
        self.tree.itemDoubleClicked.connect(lambda it, _c: self._pick(it))
        self.tree.currentItemChanged.connect(self._current)
        row.addWidget(self.tree, 1)
        from .tool_sheet import ToolSheet                 # colonne de droite : la fiche modifiable, DXF et STEP
        self.sheet = ToolSheet(self, self.tree, settings, 'outils/choix_colonnes')
        self.sheet.shared_key = self._key_shared         # une copie renommée : l'original reste favori
        self.sheet.setMinimumWidth(340)
        self.sheet.saved.connect(self._sheet_saved)
        self.preview = self.sheet.preview                  # la silhouette
        self.info = QLabel()                                # la fiche résumée : en infobulle de la silhouette
        self.info.hide()
        self._mine = None
        #: une fiche a été enregistrée (la liste « Outil » du formulaire suit)
        self.edited = False
        row.addWidget(self.sheet)
        lay.addLayout(row, 1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(lambda: self._pick(self.tree.currentItem()))
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.choice = None
        from . import tree_memory as TM                   # l'affichage de la dernière fois
        self._view = TM.load(settings, VIEW)
        self._was_q = False                              # une recherche est tapée
        self._fill(doc_tools, current)
        self._filter('')
        self.search.setFocus()

    def _group(self, nodes: dict, name: str, root=None) -> QTreeWidgetItem:
        from .tool_filters import group_item
        parts = toollib.folder_parts(name) or [name]
        parent = root
        for i, part in enumerate(parts):
            key = toollib.SEP.join(parts[:i + 1])
            it = nodes.get(key)
            if it is None:
                it = nodes[key] = group_item(['📁 ' + part])
                it.setData(0, ROLE + 1, key)
                f = it.font(0)
                f.setBold(True)
                it.setFont(0, f)
                (self.tree.addTopLevelItem(it) if parent is None else parent.addChild(it))
            parent = it
        return parent

    def _refill(self) -> None:
        """L'ordre d'origine (tri retiré), la même recherche."""
        doc_tools, current = getattr(self, '_fill_args', ((), None))
        it = self.tree.currentItem()                       # l'outil choisi le reste
        key = it.data(0, ROLE) if it is not None else None
        self._fill(doc_tools, key or current)
        self._filter(self.search.text())
        self._select_key(key)

    def _select_key(self, key) -> None:
        rows = [i for i in self._items() if key and i.data(0, ROLE) == key and not i.isHidden()]
        g = self.favorites_group()
        if g is not None and not g.isExpanded():          # favoris pliés : la ligne de l'outil hors du groupe
            rows = [i for i in rows if i.parent() is not g] + [i for i in rows if i.parent() is g]
        it = next(iter(rows), None)
        if it is not None and self.tree.currentItem() is not it:
            self._opening = True                          # (Qt déplie les dossiers de la ligne : pas retenu)
            try:
                self.tree.setCurrentItem(it)
            finally:
                self._opening = False

    def _fill(self, doc_tools, current) -> None:
        from . import tool_favorites as FAV
        from .tool_filters import group_item
        self._fill_args = (list(doc_tools), current)
        from . import tree_memory as TM
        if self.tree.topLevelItemCount() and not self.search.text().strip():
            self._view = TM.capture(self.tree)           # l'affichage d'avant : gardé quand la liste se refait
        self.tree.clear()
        cur_item = None
        self._fav_keys = set(FAV.load(self.settings))
        fav_group, fav_rows = None, []
        favs = FAV.ordered(self.settings, list(doc_tools) + list(self.library.values()))
        if favs:                                          # ★ Favoris en tête, dans leur ordre (glisser : le changer)
            fav_group = group_item([tr('★ Favoris') + f'  ({len(favs)})'])
            f = fav_group.font(0)
            f.setBold(True)
            fav_group.setFont(0, f)
            fav_group.setData(0, ROLE + 2, 'favoris')
            fav_group.setToolTip(0, tr('Les outils étoilés : un clic sur l’étoile d’un outil l’ajoute ou le retire ; '
                                       'les glisser pour les ranger'))
            self.tree.addTopLevelItem(fav_group)
            for t in favs:
                it = self._row(t, t.id if t.id in self._doc else 'lib:' + t.id)
                fav_group.addChild(it)
                fav_rows.append(it)
            fav_group.setExpanded(FAV.is_open(self.settings))
        prefs = toolprefs.load(self.settings)
        if self.op_kind and toolprefs.customized(self.op_kind, prefs):     # réglée : les proposés en tête
            best = toolprefs.ordered(list(doc_tools) + list(self.library.values()), self.op_kind, prefs, only=True)
            if best:
                g = group_item([tr('Proposés pour : {0}').format(
                    tr(model.op_kinds().get(self.op_kind, self.op_kind)).split(' (')[0])])
                f = g.font(0)
                f.setBold(True)
                g.setFont(0, f)
                g.setData(0, ROLE + 2, 'proposes')
                self.tree.addTopLevelItem(g)
                for t in best[:toolprefs.LIST_PROPOSALS * 2]:
                    key = t.id if t.id in self._doc else 'lib:' + t.id
                    g.addChild(self._row(t, key))
                g.setExpanded(True)
        if doc_tools:
            g = group_item([tr('Outils du document')])
            f = g.font(0)
            f.setBold(True)
            g.setFont(0, f)
            self.tree.addTopLevelItem(g)
            for t in doc_tools:
                it = self._row(t, t.id)
                g.addChild(it)
                if t.id == current:
                    cur_item = it
            g.setExpanded(True)
        nodes: dict = {}
        tools = sorted(self.library.values(), key=lambda t: (toollib.folder_sort_key(toollib.folder_of(t)), t.diameter,
                                                             t.name.lower()))     # familles dans leur ordre
        for t in tools:
            g = self._group(nodes, toollib.folder_of(t))
            it = self._row(t, 'lib:' + t.id)
            g.addChild(it)
            if current == 'lib:' + t.id:
                cur_item = it
        for key, node in nodes.items():                       # nombre d'outils de chaque dossier
            n = sum(1 for t in tools if toollib.in_folder(t, key))
            node.setText(0, f'{node.text(0)}  ({n})')
            if node.parent() is None:                         # dossiers de la racine ouverts : leur premier niveau en vue
                node.setExpanded(True)
        last = str(self.settings.value('fao/dossier_outil', '') or '') if self.settings is not None else ''
        if last in nodes:
            p = nodes[last]
            while p is not None:
                p.setExpanded(True)
                p = p.parent()
        if cur_item is not None:
            p = cur_item.parent()
            while p is not None:
                p.setExpanded(True)
                p = p.parent()
            self.tree.setCurrentItem(cur_item)
        first = not getattr(self, '_filled', False)
        self._filled = True
        view = getattr(self, '_view', None)
        if view:                                         # l'affichage d'avant (ou de la dernière fois) par-dessus ;
            self._opening = True                         # l'outil de l'opération reste choisi, et en vue
            try:
                TM.restore(self.tree, view, current=first and current is None, reveal=current is not None)
            finally:
                self._opening = False
        # seuls les favoris se glissent, et seulement dans leur groupe (pas quand la liste est triée par une colonne)
        FAV.lock_drops(self.tree, fav_group, fav_rows, draggable=self.tree.sortColumn() < 0)

    def _row(self, t, key) -> QTreeWidgetItem:
        """Ligne d'un outil : silhouette, « nom — Ø2 L4 » et une cellule par colonne (`tool_columns`), fiche en
        infobulle."""
        from .tool_columns import COLUMNS, row
        from .tool_filters import machine_labels, tool_icon
        from .tool_favorites import STAR_ROLE
        it = row(t)
        it.setData(0, ROLE, key)
        it.setData(0, STAR_ROLE, toollib.favorite_key(t) in getattr(self, '_fav_keys', ()))     # ★ ou ☆
        it.setIcon(0, tool_icon(t, 14, 26))
        if not hasattr(self, '_mlabels'):
            self._mlabels = machine_labels()
        tip = toollib.summary(t, self._mlabels)
        for c in range(len(COLUMNS)):
            it.setToolTip(c, tip)
        return it

    def _items(self):
        from .tree_memory import items                   # (jamais de QTreeWidgetItemIterator : voir `items`)
        return items(self.tree)

    def _filter(self, text: str) -> None:
        q = text.strip().lower()
        was = getattr(self, '_was_q', False)
        self._was_q = bool(q)
        if q and not was and self.tree.topLevelItemCount():
            from . import tree_memory as TM               # avant la recherche : l'affichage à remettre après elle
            self._view = TM.capture(self.tree)
        shown = set()
        prefs = toolprefs.load(self.settings)
        only = bool(self.op_kind) and not self.only.isHidden() and self.only.isChecked()
        for it in self._items():
            key = it.data(0, ROLE)
            if not key:
                continue
            t = self._tool(key)
            if t is None:
                ok = not q
            else:
                ok = self.filters.accepts(t) and (not only or toolprefs.suits(t, self.op_kind, prefs))
            it.setHidden(not ok)
            if ok:
                p = it.parent()
                while p is not None:
                    shown.add(id(p))
                    if q:
                        p.setExpanded(True)
                    p = p.parent()
        for it in self._items():
            if not it.data(0, ROLE):
                it.setHidden(id(it) not in shown)
        if q:
            first = next((it for it in self._items() if it.data(0, ROLE) and not it.isHidden()), None)
            if first is not None:
                self.tree.setCurrentItem(first)
        elif was and getattr(self, '_view', None):       # recherche effacée : l'affichage d'avant elle (l'outil
            from . import tree_memory as TM               # trouvé reste choisi, sans rouvrir son dossier)
            self._opening = True
            try:
                TM.restore(self.tree, self._view, current=False)
            finally:
                self._opening = False

    def _tool(self, key):
        if isinstance(key, str) and key.startswith('lib:'):
            return self.library.get(key[4:])
        return getattr(self, '_doc', {}).get(key) if hasattr(self, '_doc') else None

    # --- favoris (demande du 15/11) -----------------------------------------------------------------------------
    def _star_clicked(self, index) -> None:
        """Clic sur l'étoile d'un outil : basculée une fois l'événement de la souris fini (la liste est refaite)."""
        it = self.tree.itemFromIndex(index)
        key = it.data(0, ROLE) if it is not None else None
        if key:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self, lambda k=key: self.toggle_favorite(k))

    def toggle_favorite(self, key):
        """L'outil `key` favori, ou plus ; la liste refaite (même recherche, même outil choisi). Rend son nouvel état
        (None : outil inconnu)."""
        from . import tool_favorites as FAV
        t = self._tool(key)
        if t is None:
            return None
        on = FAV.toggle(self.settings, t)
        self._refill()
        return on

    def _key_shared(self, tool, key) -> bool:
        """Un autre outil de la liste (copie dans le document, original d'une bibliothèque) a la clé de favori `key`."""
        doc = getattr(self, '_fill_args', ((), None))[0]
        return any(x is not tool and toollib.favorite_key(x) == key for x in list(doc) + list(self.library.values()))

    def favorites_group(self):
        """Le groupe « ★ Favoris » (None : aucun favori parmi ces outils)."""
        return next((self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())
                     if self.tree.topLevelItem(i).data(0, ROLE + 2) == 'favoris'), None)

    def _favorites_moved(self) -> None:
        """Favoris glissés dans leur groupe : leur nouvel ordre retenu, la liste refaite après le dépôt."""
        from . import tool_favorites as FAV
        from PySide6.QtCore import QTimer
        g = self.favorites_group()
        if g is None:
            return
        if self.tree.sortColumn() >= 0:                   # triée par une colonne : l'ordre retenu ne change pas
            QTimer.singleShot(0, self, self._refill)
            return
        tools = [self._tool(g.child(i).data(0, ROLE)) for i in range(g.childCount())]
        FAV.reorder(self.settings, [t for t in tools if t is not None])
        QTimer.singleShot(0, self, self._refill)

    def _lock_favorites(self, col=None) -> None:
        """Tri par une colonne : plus rien ne se glisse ; tri retiré : les favoris se rangent de nouveau."""
        from . import tool_favorites as FAV
        g = self.favorites_group()
        rows = [g.child(i) for i in range(g.childCount())] if g is not None else []
        FAV.lock_drops(self.tree, g, rows, draggable=(self.tree.sortColumn() if col is None else col) < 0)

    def _fav_folded(self, it, on: bool) -> None:
        """Groupe « Favoris » plié ou déplié à la main : retenu (pas pendant une recherche, qui ouvre les dossiers, ni
        quand la liste déplie elle-même la ligne choisie)."""
        busy = self._opening or bool(self.search.text().strip())
        if it is not None and it.data(0, ROLE + 2) == 'favoris' and not busy:
            from . import tool_favorites as FAV
            FAV.set_open(self.settings, on)

    def toggle_full_screen(self) -> bool:
        from .tool_filters import toggle_full_screen
        return toggle_full_screen(self)

    def done(self, r) -> None:                                  # noqa: D401 — API Qt
        from .tool_filters import remember_large
        remember_large(self, self.settings, 'outils/choix_agrandi', full=True)
        from . import tree_memory as TM                   # l'affichage de la liste (celui d'avant une recherche)
        TM.save(self.settings, VIEW, getattr(self, '_view', None) if self.search.text().strip()
                else TM.capture(self.tree))
        super().done(r)

    def tool_prefs(self, exec_dialog: bool = True):
        """Régler les outils proposés (pour la stratégie de l'opération), puis
        la liste refaite."""
        from .toolprefs_dialog import ToolPrefsDialog
        dlg = ToolPrefsDialog(self, self.settings, list(self.library.values()), kind=self.op_kind)
        if not exec_dialog:
            return dlg
        if dlg.exec():
            self.refresh()
        return dlg

    def refresh(self) -> None:
        pref = toolprefs.pref_for(self.op_kind, toolprefs.load(self.settings)) if self.op_kind else None
        self.only.setVisible(bool(pref and pref['rules']))
        self._fill(self._doc_list, self._current_key)
        self._filter(self.search.text())

    def _current(self, it, _prev=None) -> None:
        key = it.data(0, ROLE) if it is not None else None
        t = self._tool(key) if key else None
        sheet = self.sheet
        if sheet.modified and sheet.tool is not None and sheet.tool is not t and sheet.save(emit=False):
            self.edited = True                             # fiche modifiée, un autre outil montré : enregistrée
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self, lambda k=key: self._refresh(k))
        if t is None:
            sheet.show_tool(None)
            self.info.clear()
            return
        sheet.show_tool(t, self._source(key))
        from .tool_filters import machine_labels
        if not hasattr(self, '_mlabels'):
            self._mlabels = machine_labels()
        self.info.setText(toollib.summary(t, self._mlabels))
        self.preview.setToolTip(self.info.text())

    def _source(self, key) -> str:
        """D'où vient l'outil `key` : du document, de Mes outils (même id, sinon le même outil : fichier sans
        identifiants), ou d'une bibliothèque de plugin (lecture seule)."""
        from .tool_sheet import DOC, DOC_RO, MINE, PLUGIN
        if not (isinstance(key, str) and key.startswith('lib:')):
            return DOC if self.doc_editable else DOC_RO
        if self._mine is None:
            self._mine = toollib.library()
        t = self.library.get(key[4:])
        if any(x.id == key[4:] for x in self._mine) or (t is not None and toollib.find_match(t, self._mine)):
            return MINE
        return PLUGIN

    def _refresh(self, key) -> None:
        """Fiche enregistrée : la liste refaite (fabricants compris), l'outil `key` choisi, la même recherche."""
        if key:
            self._current_key = key
        self.filters.set_tools(list(self.library.values()) + list(self._doc_list))
        self._fill(self._doc_list, key)
        self._filter(self.search.text())
        self._select_key(key)

    def _sheet_saved(self, t) -> None:
        self.edited = True
        self._refresh(t.id if t.id in self._doc else 'lib:' + t.id)

    def _pick(self, it) -> None:
        if self.sheet.modified and self.sheet.save(emit=False):    # fiche modifiée : enregistrée avant de choisir
            self.edited = True
        key = it.data(0, ROLE) if it is not None else None
        if not key:
            if it is not None:
                it.setExpanded(not it.isExpanded())
            return
        self.choice = key
        if self.settings is not None and isinstance(key, str) and key.startswith('lib:'):
            t = self.library.get(key[4:])
            if t is not None:
                self.settings.setValue('fao/dossier_outil', toollib.folder_of(t))
        self.accept()


class ToolCombo(QComboBox):
    """Liste des outils du document ; « Choisir dans Mes outils… » ouvre
    ToolPickerDialog. `findData('lib:<id>')` et `findText('📁 dossier —
    nom')` ajoutent au besoin l'outil de Mes outils demandé."""

    def __init__(self, library: dict, doc_tools, settings=None, parent=None, op_kind: str = '',
                 machine: tuple = ('', '')):
        super().__init__(parent)
        self.machine = tuple(machine or ('', ''))
        self.library = library
        self.doc_tools = doc_tools
        self.settings = settings
        self.op_kind = op_kind
        #: outils de Mes outils proposés directement dans la liste (ids)
        self.proposals: list[str] = []
        self._last = 0
        self.activated.connect(self._activated)
        self.currentIndexChanged.connect(self._remember)

    def finish(self) -> None:
        """Après les outils du document : la ligne qui ouvre Mes outils."""
        if self.library:
            if self.proposals:
                self.insertSeparator(self.count())
                for tid in self.proposals:
                    t = self.library.get(tid)
                    if t is not None:
                        from .tool_filters import tool_icon
                        self.addItem(tool_icon(t), lib_label(t) + f' ({toollib.specs(t)})', 'lib:' + t.id)
                        self.setItemData(self.count() - 1, tr('Proposé de Mes outils (copié dans le document '
                                                              'si choisi)'), Qt.ItemDataRole.ToolTipRole)
            self.insertSeparator(self.count())
            self.addItem(tr('📁 Choisir un outil (Mes outils, bibliothèques)…'), PICK)
            self.setToolTip(tr('Outils du document ; la dernière ligne ouvre Mes outils et les bibliothèques des '
                               'plugins, rangés par dossiers (l’outil choisi est copié dans le document)'))

    def _pick_index(self) -> int:
        return QComboBox.findData(self, PICK)

    def _remember(self, i: int) -> None:
        if i >= 0 and self.itemData(i) != PICK:
            self._last = i

    def add_library(self, tid: str) -> int:
        """Ligne de l'outil `tid` de Mes outils (ajoutée avant « Choisir… »)."""
        i = QComboBox.findData(self, 'lib:' + tid)
        if i >= 0:
            return i
        t = self.library.get(tid)
        if t is None:
            return -1
        at = self._pick_index()
        if at < 0:
            at = self.count()
        else:
            at -= 1                                        # avant le séparateur
        self.insertItem(at, lib_label(t), 'lib:' + t.id)
        return at

    def findData(self, data, *args, **kwargs) -> int:          # noqa: N802 — API Qt
        i = QComboBox.findData(self, data, *args, **kwargs)
        if i < 0 and isinstance(data, str) and data.startswith('lib:'):
            i = self.add_library(data[4:])
        return i

    def findText(self, text, *args, **kwargs) -> int:          # noqa: N802 — API Qt
        i = QComboBox.findText(self, text, *args, **kwargs)
        if i < 0:
            t = next((t for t in self.library.values() if lib_label(t) == text), None)
            if t is not None:
                i = self.add_library(t.id)
        return i

    def choose(self, exec_dialog: bool = True):
        """Fenêtre des dossiers ; rend la clé choisie (ou la fenêtre, sans
        l'ouvrir, si `exec_dialog` est faux)."""
        cur = self.itemData(self._last) if 0 <= self._last < self.count() else None
        dlg = ToolPickerDialog(self, self.doc_tools, self.library, cur, self.settings, op_kind=self.op_kind,
                               machine=self.machine)
        if not exec_dialog:
            return dlg
        ok = dlg.exec() == QDialog.DialogCode.Accepted and dlg.choice
        edited = getattr(dlg, 'edited', False)
        dlg.deleteLater()
        if edited:                                       # fiche modifiée dans la fenêtre : textes à jour
            self.refresh_labels()
        if not ok:
            self.setCurrentIndex(self._last)
        else:
            self.set_key(dlg.choice)
        if edited:                                       # le formulaire relit l'outil (valeurs des champs à 0)
            self.currentIndexChanged.emit(self.currentIndex())
        return dlg.choice if ok else None

    def refresh_labels(self) -> None:
        """Textes des outils de la liste, d'après leurs fiches (une fiche modifiée dans « Choisir un outil »)."""
        docs = {t.id: t for t in self.doc_tools}
        for i in range(self.count()):
            d = self.itemData(i)
            if isinstance(d, str) and d in docs:
                self.setItemText(i, toollib.short_label(docs[d]))
            elif isinstance(d, str) and d.startswith('lib:') and d[4:] in self.library:
                t = self.library[d[4:]]
                self.setItemText(i, lib_label(t) + (f' ({toollib.specs(t)})' if self.itemText(i).endswith(')')
                                                    else ''))

    def set_key(self, key) -> None:
        i = self.findData(key)
        self.setCurrentIndex(i if i >= 0 else self._last)

    def _activated(self, i: int) -> None:
        if self.itemData(i) == PICK:
            self.choose()


def program_label(info) -> str:
    """« nom » — référence — T…, ce que le programme dit de son outil."""
    info = info if isinstance(info, dict) else {}
    name = str(info.get('name') or '').strip()
    out = [f'« {name} »' if name else tr('sans nom')]
    if str(info.get('ref') or '').strip():
        out.append(str(info['ref']).strip())
    if info.get('number'):
        out.append(f'T{info["number"]}')
    return ' — '.join(out)


class ProgramToolDialog(ToolPickerDialog):
    """« Choisir un outil existant » à la place de l'outil d'un programme lu : l'arbre de « Choisir un outil »
    (document, Mes outils, bibliothèques des plugins) et la case « Retenir ce choix pour les prochaines fois »."""

    #: le choix « Créer l'outil d'après le programme »
    CREATE = 'creer'
    #: les outils du document se modifient dans la liste des outils de la FAO (le réglage n'est pas enregistré ici)
    doc_editable = False

    def __init__(self, parent, doc_tools, library: dict, current=None, settings=None, info=None,
                 machine: tuple = ('', ''), can_create: bool = False):
        super().__init__(parent, doc_tools, library, current, settings, machine=machine)
        self.setWindowTitle(tr('Outil du programme : choisir un outil existant'))
        lay = self.layout()
        head = QLabel(tr('À la place de l’outil du programme : {0}').format(program_label(info)))
        head.setWordWrap(True)
        lay.insertWidget(0, head)
        self.remember = QCheckBox(tr('Retenir ce choix pour les prochaines fois'))
        self.remember.setChecked(True)
        self.remember.setToolTip(tr('Cochée : les programmes lus ensuite avec le même outil (même référence, sinon même '
                                    'nom ou même numéro) prennent celui-ci. Décochée : pour cette fois, et une '
                                    'association retenue avant est oubliée. Double-clic sur l’outil d’un parcours lu '
                                    '(calque Trajectoires) : en changer.'))
        lay.insertWidget(lay.count() - 1, self.remember)
        self.create_button = None
        if can_create:                                   # outil inconnu : aussi le créer d'après le programme
            self.create_button = QPushButton(tr('Créer l’outil d’après le programme…'))
            self.create_button.setToolTip(tr('Outil inconnu des bibliothèques : le créer d’après le programme (référence ou '
                                      'numéro, broche et avances préremplies), dans Mes outils'))
            self.create_button.clicked.connect(self._create)
            lay.insertWidget(lay.count() - 1, self.create_button)

    def _create(self) -> None:
        self.choice = self.CREATE
        self.accept()


def target_label(target) -> str:
    """L'outil retenu (`ncread.tool_target`) en clair : nom — référence — Ø."""
    target = target if isinstance(target, dict) else {}
    out = [str(target.get('name') or '').strip() or tr('sans nom')]
    if str(target.get('ref') or '').strip():
        out.append(str(target['ref']).strip())
    try:
        d = float(target.get('diameter') or 0.0)
    except (TypeError, ValueError):
        d = 0.0
    if d > 0:
        out.append(f'Ø{d:g}')
    return ' — '.join(out)


class ProgramAliasesDialog(QDialog):
    """Les outils retenus à la place de ceux des programmes lus (case « Retenir ce choix pour les prochaines fois ») :
    la liste, et « Oublier » pour les choisis. En changer : double-clic sur l'outil d'un parcours lu."""

    def __init__(self, parent=None, path=None):
        super().__init__(parent)
        from ..cam import ncread
        self.path = path or ncread.alias_path()
        self.setWindowTitle(tr('Outils des programmes lus'))
        self.setSizeGripEnabled(True)
        self.resize(720, 420)
        lay = QVBoxLayout(self)
        head = QLabel(tr('Les outils choisis à la place de ceux des programmes lus, retenus pour les prochaines fois. '
                         'Pour en changer : double-clic sur l’outil d’un parcours lu (calque Trajectoires).'))
        head.setWordWrap(True)
        lay.addWidget(head)
        self.tree = QTreeWidget()
        self.tree.setRootIsDecorated(False)
        self.tree.setHeaderLabels([tr('Outil du programme'), tr('Outil retenu')])
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tree.itemSelectionChanged.connect(self._update)
        lay.addWidget(self.tree, 1)
        self.state = QLabel('')
        self.state.setWordWrap(True)
        lay.addWidget(self.state)
        row = QHBoxLayout()
        self.forget_button = QPushButton(tr('Oublier'))
        self.forget_button.setToolTip(tr('Les associations choisies sont oubliées : la prochaine lecture propose de '
                                         'nouveau l’outil du programme'))
        self.forget_button.clicked.connect(self.forget_selected)
        row.addWidget(self.forget_button)
        row.addStretch(1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.reject)
        row.addWidget(bb)
        lay.addLayout(row)
        self.reload()

    def reload(self) -> None:
        """La liste relue du fichier ; abîmé ou inaccessible : dit, et rien ne peut être oublié (rien n'est réécrit)."""
        from ..cam import ncread
        self.tree.clear()
        self.ok = True
        try:
            items = ncread.load_aliases(self.path, strict=True)
        except ValueError:
            items, self.ok = [], False
            self.state.setText(tr('Fichier des associations abîmé : {0} — il sera mis de côté au prochain choix '
                                  'retenu').format(self.path))
        except OSError as e:
            items, self.ok = [], False
            self.state.setText(tr('Fichier des associations inaccessible : {0}').format(e))
        for a in items:
            it = QTreeWidgetItem([program_label(a['programme']), target_label(a['outil'])])
            it.setData(0, ROLE, a['programme'])
            it.setToolTip(0, str(self.path))
            self.tree.addTopLevelItem(it)
        if self.ok:
            self.state.setText(tr('{0} association(s) — {1}').format(len(items), self.path) if items else
                               tr('Aucun outil retenu'))
        self._update()

    def _update(self) -> None:
        self.forget_button.setEnabled(self.ok and bool(self.tree.selectedItems()))

    def forget_selected(self) -> int:
        """Oublie les associations choisies ; rend leur nombre."""
        from ..cam import ncread
        keys = [it.data(0, ROLE) for it in self.tree.selectedItems()]
        n = 0
        try:
            for k in keys:
                n += ncread.forget(k, self.path)
        except OSError as e:
            self.reload()
            self.state.setText(tr('Fichier des associations inaccessible : {0}').format(e))
            return n
        self.reload()
        return n


class UnknownToolsDialog(QDialog):
    """À la lecture d'un programme : ses outils inconnus des bibliothèques, chacun à créer d'après le programme ou à
    remplacer par un outil existant. Non modale : fermée, les outils restent inconnus (« ? » dans le calque
    Trajectoires, où le double-clic les propose encore)."""

    def __init__(self, panel, tps):
        super().__init__(panel)
        self.panel = panel
        self.setWindowTitle(tr('Outils inconnus du programme'))
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)     # fermée : libérée (et ses parcours avec)
        lay = QVBoxLayout(self)
        head = QLabel(tr('Ces outils du programme ne sont dans aucune bibliothèque : créez-les d’après le programme '
                         '(référence ou numéro, broche et avances préremplies), ou choisissez un outil existant à '
                         'leur place.'))
        head.setWordWrap(True)
        lay.addWidget(head)
        grid = QGridLayout()
        self.rows = []
        for i, tp in enumerate(tps):
            what = QLabel(program_label(getattr(tp, 'tool_info', None) or {}) + f'  ({tp.name or "—"})')
            what.setWordWrap(True)
            create = QPushButton(tr('Créer l’outil…'))
            pick = QPushButton(tr('Choisir un outil existant…'))
            state = QLabel('')
            create.clicked.connect(lambda _=False, k=i: self.create(k))
            pick.clicked.connect(lambda _=False, k=i: self.pick(k))
            for c, w in enumerate((what, create, pick, state)):
                grid.addWidget(w, i, c)
            self.rows.append((tp, create, pick, state))
        grid.setColumnStretch(0, 1)
        lay.addLayout(grid)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.button(QDialogButtonBox.StandardButton.Close).setText(tr('Plus tard'))
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def create(self, k: int, exec_dialog: bool = True):
        """Créer l'outil de la ligne `k` ; rend l'outil (ou la fenêtre sans l'ouvrir)."""
        tp = self.rows[k][0]
        got = self.panel.create_program_tool(tp, exec_dialog)
        if not exec_dialog:                                 # après la fenêtre du panneau (reliée avant)
            got.finished.connect(lambda r: r == QDialog.DialogCode.Accepted and self.solved(k))
            return got
        if got is not None:
            self.solved(k)
        return got

    def pick(self, k: int, exec_dialog: bool = True):
        """Un outil existant pour la ligne `k` ; rend l'outil (ou la fenêtre sans l'ouvrir)."""
        tp = self.rows[k][0]
        got = self.panel.choose_program_tool(tp, exec_dialog)
        if not exec_dialog:                                 # après la fenêtre du panneau (reliée avant)
            got.finished.connect(lambda r: r == QDialog.DialogCode.Accepted and self.solved(k))
            return got
        if got is not None:
            self.solved(k)
        return got

    def solved(self, k: int) -> None:
        tp, create, pick, state = self.rows[k]
        t = getattr(tp, 'tool_guess', None)
        if t is None or not getattr(tp, 'tool_source', ''):         # toujours inconnu (enregistrement en défaut)
            return
        try:
            create.setEnabled(False)
            pick.setText(tr('Changer…'))
            state.setText('✓ ' + (t.name if t is not None else ''))
        except RuntimeError:                             # fenêtre fermée (libérée) pendant le choix
            pass
