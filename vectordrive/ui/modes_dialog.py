"""« Commandes du mode simple » (réponse du 16/11 à la question 10 : « liste simple-expert réglable dans F10 ») :
toutes les commandes du ruban, onglet par onglet, une case chacune — cochée, son bouton est montré en mode simple ;
décochée, il est réservé au mode expert. Le mode expert montre toujours tout. Ouverte depuis Options (F10) › Général.

Seul l'écart à la répartition d'office est gardé (`ui.modes.move`) ; « Répartition d'office » y revient."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QHeaderView, QLabel, QLineEdit, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout)

from ..i18n import tr
from . import modes

ROLE_KEY = Qt.ItemDataRole.UserRole
CHECKED, UNCHECKED = Qt.CheckState.Checked, Qt.CheckState.Unchecked


def ribbon_commands(win) -> list:
    """[(titre de l'onglet, [(clé, libellé, groupe, raccourcis)])] : les commandes de la fenêtre qui ont un bouton
    dans le ruban, dans l'ordre du ruban ; une commande n'est listée qu'une fois par onglet. Les onglets d'une
    disposition importée (TypeEdit) ne sont listés que s'ils sont montrés ; deux onglets du même titre (« CAD » en 2D
    et en 3D) sont distingués."""
    from .ribbon import RibbonGroup
    from .ribbon_editor import RelayAction
    keys = {id(a): k for k, a in win.A.items()}
    r = win.ribbon
    out = []
    for i in range(r.count()):
        page = r.page(i) if hasattr(r, 'page') else r.widget(i).widget()
        if page is None or (r.widget(i).property('te_layout') and not r.isTabVisible(i)):
            continue
        rows, seen = [], set()
        groups = page.groups() if hasattr(page, 'groups') else page.findChildren(RibbonGroup)
        for g in groups:
            title = next((lab.text() for lab in g.findChildren(QLabel) if lab.objectName() == 'ribbonGroupTitle'), '')
            for b in g.buttons():
                act = b.defaultAction()
                src = act.src if isinstance(act, RelayAction) else act
                key = keys.get(id(src)) if src is not None else None
                if key is None or key in seen:
                    continue
                seen.add(key)
                rows.append((key, src.text().replace('&', ''), title,
                             ', '.join(s.toString() for s in src.shortcuts())))
        if rows:
            kind = str(page.property('vd_cad') or '')
            out.append([r.tabText(i), rows, kind.upper()])
    titles = [t for t, _rows, _k in out]
    named = []
    for n, (title, rows, kind) in enumerate(out):
        if titles.count(title) > 1:                      # deux onglets du même titre : 2D / 3D, sinon leur rang
            title = f'{title} ({kind or titles[:n + 1].count(title)})'
        named.append((title, rows))
    return named


class SimpleModeDialog(QDialog):
    """La liste des commandes du ruban, à cocher pour le mode simple."""

    def __init__(self, win, parent=None):
        super().__init__(parent or win)
        self.win = win
        self.plugin_keys = tuple(win._plugin_action_keys()) if hasattr(win, '_plugin_action_keys') else ()
        self.setWindowTitle(tr('Commandes du mode simple'))
        self.setSizeGripEnabled(True)
        self.resize(640, 680)
        lay = QVBoxLayout(self)
        help_text = tr('Cochée : le bouton de la commande est montré en mode simple ; décochée : il est réservé au mode expert, qui montre tout. Les raccourcis et la recherche de commande donnent toujours tout.')
        note = QLabel(help_text)
        note.setWordWrap(True)
        lay.addWidget(note)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr('Chercher une commande…'))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.filter)
        lay.addWidget(self.search)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([tr('Commande'), tr('Groupe'), tr('Raccourci')])
        self.tree.setRootIsDecorated(True)
        hh = self.tree.header()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in (1, 2):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        lay.addWidget(self.tree, 1)
        self.count = QLabel()
        lay.addWidget(self.count)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
                              | QDialogButtonBox.StandardButton.RestoreDefaults)
        bb.button(QDialogButtonBox.StandardButton.RestoreDefaults).setText(tr('Répartition d’office'))
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        bb.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(self.restore_defaults)
        lay.addWidget(bb)
        self._syncing = False
        self._was: dict = {}                             # clé → montrée en mode simple, à l'ouverture
        self.fill()
        self.tree.itemChanged.connect(self._changed)

    # --- la liste ------------------------------------------------------------------------------
    def fill(self) -> None:
        st = self.win.settings
        self.tree.clear()
        self._was = {}
        for tab, rows in ribbon_commands(self.win):
            top = QTreeWidgetItem([tab])                 # sa case : celles de ses commandes MONTRÉES (`_changed`) — pas
            top.setFlags(top.flags() | Qt.ItemFlag.ItemIsUserCheckable)   # l'automatisme de Qt, qui prend les cachées
            top.setCheckState(0, UNCHECKED)
            self.tree.addTopLevelItem(top)
            for key, text, group, keys in rows:
                on = self._was.setdefault(key, modes.in_simple(key, st, self.plugin_keys))
                it = QTreeWidgetItem([text, group, keys])
                it.setData(0, ROLE_KEY, key)
                it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                it.setCheckState(0, CHECKED if on else UNCHECKED)
                top.addChild(it)
            top.setExpanded(True)
        self._sync_tabs()
        self._count()

    def _sync_tabs(self) -> None:
        """La case de chaque onglet d'après toutes ses commandes : cochée, décochée, ou partielle."""
        was, self._syncing = self._syncing, True
        try:
            for i in range(self.tree.topLevelItemCount()):
                top = self.tree.topLevelItem(i)
                on = [top.child(k).checkState(0) == CHECKED for k in range(top.childCount())]
                state = CHECKED if all(on) else UNCHECKED if not any(on) else Qt.CheckState.PartiallyChecked
                if top.checkState(0) != state:
                    top.setCheckState(0, state)
        finally:
            self._syncing = was

    def rows(self) -> list:
        """Les lignes de commandes (pas celles des onglets)."""
        from .tree_memory import items
        return [it for it in items(self.tree) if it.data(0, ROLE_KEY)]

    def states(self) -> dict:
        """clé → cochée (montrée en mode simple)."""
        return {str(it.data(0, ROLE_KEY)): it.checkState(0) == CHECKED for it in self.rows()}

    def set_checked(self, key: str, on: bool) -> None:
        """Coche ou décoche la commande `key`, dans tous les onglets où elle a un bouton."""
        for it in self.rows():
            if it.data(0, ROLE_KEY) == key:
                it.setCheckState(0, CHECKED if on else UNCHECKED)

    def _changed(self, item, _col: int) -> None:
        if self._syncing:
            return
        key = item.data(0, ROLE_KEY)
        self._syncing = True
        try:
            if key:                                      # la même commande dans un autre onglet : la même case
                keys = {str(key): item.checkState(0)}
            else:                                        # la case d'un onglet : ses commandes montrées, pas celles
                state = UNCHECKED if item.checkState(0) == UNCHECKED else CHECKED     # que la recherche cache
                keys = {str(item.child(k).data(0, ROLE_KEY)): state for k in range(item.childCount())
                        if not item.child(k).isHidden()}
            for it in self.rows():
                state = keys.get(str(it.data(0, ROLE_KEY)))
                if state is not None and it.checkState(0) != state:
                    it.setCheckState(0, state)
        finally:
            self._syncing = False
        self._sync_tabs()
        self._count()

    def _count(self) -> None:
        st = self.states()
        self.count.setText(tr('{0} commande(s) sur {1} montrées en mode simple').format(sum(st.values()), len(st)))

    def filter(self, text: str = '') -> int:
        """Seules les commandes dont le libellé, le groupe ou le raccourci contient `text` ; rend leur nombre."""
        q = text.strip().lower()
        n = 0
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            shown = 0
            for k in range(top.childCount()):
                it = top.child(k)
                hit = not q or any(q in it.text(c).lower() for c in range(3)) or q in top.text(0).lower()
                it.setHidden(not hit)
                shown += hit
            top.setHidden(not shown)
            n += shown
        return n

    def restore_defaults(self) -> None:
        """Les cases comme la répartition d'office (rien n'est écrit avant OK). À OK, tous les écarts retenus sont
        oubliés — ceux de commandes qui n'ont pas de bouton en ce moment aussi (plugin absent) — puis ceux des cases
        changées depuis sont écrits."""
        self._reset = True
        for it in self.rows():
            on = modes.default_simple(str(it.data(0, ROLE_KEY)), self.plugin_keys)
            it.setCheckState(0, CHECKED if on else UNCHECKED)

    def accept(self) -> None:
        st = self.win.settings
        changed = 0
        if getattr(self, '_reset', False):               # « Répartition d'office » : on repart de zéro
            changed = len(modes._keys(st, modes.PLUS)) + len(modes._keys(st, modes.MINUS))
            st.setValue(modes.PLUS, [])
            st.setValue(modes.MINUS, [])
            self._was = {key: modes.default_simple(key, self.plugin_keys) for key in self._was}
        for key, on in self.states().items():
            if on != self._was.get(key):
                modes.move(st, key, on, self.plugin_keys)
                changed += 1
        if changed and hasattr(self.win, 'set_ui_mode'):
            self.win.set_ui_mode(self.win.ui_mode(), announce=False)     # le ruban suit tout de suite
        super().accept()
