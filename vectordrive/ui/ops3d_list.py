"""Liste « Usinages » à côté de la vue 3D : les opérations de la prise
montrée (toutes : prise « Toutes », pièce sans prises), leur outil, leur
parcours — modifier l'opération ou son outil, recalculer, dupliquer,
monter, descendre, supprimer le parcours seul ou l'opération, sans ouvrir
le panneau FAO : ses commandes, sur la même opération (choisie aussi dans
son tableau)."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QItemSelectionModel, Qt, QTimer
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QLabel, QMenu, QToolButton, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from ..i18n import tr

#: boutons sous la liste : actions du ruban FAO 3D (mêmes commandes)
BUTTONS = ('cam3d_op_edit', 'cam3d_op_tool', 'cam3d_op_recompute', 'cam3d_op_duplicate', 'cam3d_op_up',
           'cam3d_op_down', 'cam3d_path_remove', 'cam3d_op_remove')
#: réglage : liste montrée à côté de la vue 3D (s'il y a des usinages)
SHOWN_KEY = 'vue3d/usinages'
#: colonnes
COLUMNS = ('Usinage', 'Outil', 'Parcours')


class Ops3DList(QWidget):
    """`panel` : le panneau de la vue 3D (prise montrée) ; les opérations
    sont celles du panneau FAO de la fenêtre."""

    def __init__(self, panel):
        super().__init__(panel)
        self.panel = panel
        self.win = panel.win
        self._filling = False
        self._in_change = False                          # case cochée : la liste refaite après le signal
        self._refill = QTimer(self)
        self._refill.setSingleShot(True)
        self._refill.setInterval(0)
        self._refill.timeout.connect(self.fill)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 2, 2, 2)
        lay.setSpacing(2)
        self.title = QLabel(tr('Usinages'))
        self.title.setToolTip(tr('Usinages de la prise montrée : double clic pour les modifier, Suppr pour les '
                                 'supprimer, clic droit pour les autres commandes ; la case active ou désactive'))
        lay.addWidget(self.title)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(len(COLUMNS))
        self.tree.setHeaderLabels([tr(c) for c in COLUMNS])
        self.tree.setRootIsDecorated(False)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(lambda pos: self.menu(pos))
        self.tree.itemSelectionChanged.connect(self._picked)
        self.tree.itemDoubleClicked.connect(lambda _it, _c: self.edit())
        self.tree.itemChanged.connect(self._checked)
        self.tree.installEventFilter(self)               # Suppr, Ctrl+M : pour la liste, pas pour la fenêtre
        lay.addWidget(self.tree, 1)
        self.empty = QLabel(tr('Aucun usinage dans cette prise : « Automatisme… » ou les commandes du groupe '
                               '« Usinage 3D » du ruban FAO 3D'))
        self.empty.setWordWrap(True)
        lay.addWidget(self.empty)
        row = QHBoxLayout()
        row.setSpacing(0)
        A = getattr(self.win, 'A', None) or {}
        self.buttons = []
        for k in BUTTONS:                                # mêmes actions que le ruban : mêmes commandes
            if k in A:
                b = QToolButton()
                b.setDefaultAction(A[k])
                b.setAutoRaise(True)
                b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
                row.addWidget(b)
                self.buttons.append(b)
        row.addStretch(1)
        lay.addLayout(row)
        self.setMinimumWidth(240)
        self.setVisible(False)

    def _key(self, ev):
        """Commande d'une touche de la liste : Suppr (supprimer l'usinage),
        Ctrl+M (le modifier) ; None sinon."""
        mods = ev.modifiers() & ~Qt.KeyboardModifier.KeypadModifier
        if ev.key() == Qt.Key.Key_Delete and mods == Qt.KeyboardModifier.NoModifier:
            return self.remove_op
        if ev.key() == Qt.Key.Key_M and mods == Qt.KeyboardModifier.ControlModifier:
            return self.edit
        return None

    def eventFilter(self, obj, ev) -> bool:
        """Suppr dans la liste supprime l'usinage — « Effacer » (Suppr) du
        dessin n'est pas lancé : la touche est réclamée avant les raccourcis."""
        if obj is self.tree and ev.type() in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress):
            fn = self._key(ev)
            if fn is not None:
                if ev.type() == QEvent.Type.ShortcutOverride:
                    ev.accept()
                else:
                    fn()
                return True
        return super().eventFilter(obj, ev)

    # --- contenu ------------------------------------------------------------------------
    def cp(self):
        return getattr(self.win, 'cam_panel', None)

    def wanted(self) -> bool:
        st = getattr(self.win, 'settings', None)
        v = st.value(SHOWN_KEY, True) if st is not None else True
        return v not in (False, 'false', '0', 0)

    def ops(self) -> list:
        """Opérations montrées : celles de la prise de l'onglet de la vue 3D
        (comme ses trajectoires), sinon toutes."""
        cp = self.cp()
        if cp is None:
            return []
        every = list(cp.setup().operations)
        p = self.panel
        src = p._model_source()
        if src is None or p.all_setups() or p.setup_view.count() <= 1:
            return every
        from ..core import workspace as WS
        doc = self.win.canvas.doc
        face, body = p.current_setup()
        want = (WS.norm_face(doc, face, src, body), body)
        return [o for o in every if o.kind != 'instruction' and WS.op_setup(o, doc) == want]

    def fill(self) -> None:
        """Liste refaite (l'opération choisie le reste) ; montrée s'il y a
        des usinages et qu'elle est voulue."""
        if self._in_change:                              # l'élément coché sert encore à Qt : pas détruit ici
            self._refill.start()
            return
        cp = self.cp()
        keep = self.current_id()
        self._filling = True
        self.tree.clear()
        shown = self.ops()
        if cp is not None:
            from ..cam import model, toollib
            from .tool_filters import tool_icon
            s = cp.setup()
            done = {t.op_id for t in cp.toolpaths if t.op_id}
            for o in shown:
                t = s.tool(o.tool_id)
                kind = tr(model.op_kinds().get(o.kind, o.kind))
                if o.kind == 'instruction':
                    state = ''
                else:
                    state = tr('calculé') if o.id in done else tr('à calculer') if o.enabled else tr('désactivé')
                it = QTreeWidgetItem([o.name or kind, toollib.short_label(t) if t is not None else '—', state])
                it.setData(0, Qt.ItemDataRole.UserRole, o.id)
                it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                it.setCheckState(0, Qt.CheckState.Checked if o.enabled else Qt.CheckState.Unchecked)
                it.setToolTip(0, kind if o.kind == 'instruction' else
                              tr('{0} — profondeur {1} mm').format(kind, f'{o.depth:g}'))
                if t is not None:
                    it.setIcon(1, tool_icon(t, 12, 22))
                    it.setToolTip(1, toollib.summary(t))
                self.tree.addTopLevelItem(it)
                if o.id == keep:
                    it.setSelected(True)
                    self.tree.setCurrentItem(it)
            for c in range(len(COLUMNS)):
                self.tree.resizeColumnToContents(c)
        self._filling = False
        n = len(shown)
        self.title.setText(tr('Usinages ({0})').format(n))
        self.empty.setVisible(n == 0)
        self.setVisible(self.wanted() and cp is not None and bool(cp.setup().operations))

    def current_id(self) -> str:
        items = self.tree.selectedItems()
        return str(items[0].data(0, Qt.ItemDataRole.UserRole) or '') if items else ''

    def select(self, op_id: str) -> bool:
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            if it.data(0, Qt.ItemDataRole.UserRole) == op_id:
                self.tree.setCurrentItem(it)
                it.setSelected(True)
                return True
        return False

    def show_ops(self, ops) -> None:
        """Usinages créés (automatisme) : la liste montrée, le premier choisi."""
        st = getattr(self.win, 'settings', None)
        if st is not None and not self.wanted():
            st.setValue(SHOWN_KEY, True)
        self._sync_toggle()
        self.fill()
        for o in ops or []:
            if o.kind != 'instruction' and self.select(o.id):
                break
        n = len([o for o in ops or [] if o.kind != 'instruction'])
        if n:
            self.win.statusBar().showMessage(
                tr('{0} usinage(s) créé(s) — liste « Usinages » : double clic pour modifier, Suppr pour '
                   'supprimer').format(n), 8000)

    def toggle(self, on: bool) -> None:
        """Liste montrée ou cachée (retenu) ; sans usinage, le dire."""
        st = getattr(self.win, 'settings', None)
        if st is not None:
            st.setValue(SHOWN_KEY, bool(on))
        self.fill()
        cp = self.cp()
        if on and (cp is None or not cp.setup().operations):
            self.win.statusBar().showMessage(tr('Aucun usinage : « Automatisme… » ou les commandes du groupe '
                                                '« Usinage 3D » en créent'), 6000)

    def _sync_toggle(self) -> None:
        a = (getattr(self.win, 'A', None) or {}).get('cam3d_ops_list')
        if a is not None and a.isChecked() != self.wanted():
            a.blockSignals(True)
            a.setChecked(self.wanted())
            a.blockSignals(False)

    # --- choix ----------------------------------------------------------------------------
    def _picked(self) -> None:
        """L'opération choisie ici l'est aussi dans le tableau du panneau FAO."""
        if self._filling:
            return
        cp, oid = self.cp(), self.current_id()
        if cp is None or not oid:
            return
        r = next((i for i, o in enumerate(cp.setup().operations) if o.id == oid), -1)
        if r >= 0:
            self._panel_row(r)

    def _checked(self, item, column: int) -> None:
        if self._filling or column != 0:
            return
        cp = self.cp()
        oid = item.data(0, Qt.ItemDataRole.UserRole)
        s = cp.setup() if cp is not None else None
        op = next((o for o in s.operations if o.id == oid), None) if s is not None else None
        if op is None:
            return
        self._in_change = True
        try:
            op.enabled = item.checkState(0) == Qt.CheckState.Checked
            cp.save(s)
        finally:
            self._in_change = False
        cp._schedule_3d()                                  # trajectoires d'une opération désactivée : cachées

    def _need(self):
        """(réglage, rang, opération) choisie ici, choisie aussi dans le
        tableau du panneau FAO (ses commandes la visent) ; sinon le dire."""
        cp, oid = self.cp(), self.current_id()
        s = cp.setup() if cp is not None else None
        r = next((i for i, o in enumerate(s.operations) if o.id == oid), -1) if s is not None and oid else -1
        if r < 0:
            if cp is not None and cp.setup().operations and not self.isVisible():
                self.toggle(True)
                self._sync_toggle()
            self.win.statusBar().showMessage(tr('Choisissez un usinage dans la liste « Usinages » de la vue 3D'),
                                             6000)
            return None
        self._panel_row(r)
        return s, r, s.operations[r]

    def _panel_row(self, r: int) -> None:
        """Rangée `r` choisie seule dans le tableau du panneau FAO (selectRow
        suit les touches tenues : avec Ctrl, il la décocherait)."""
        t = self.cp().ops
        flags = QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows
        t.selectionModel().setCurrentIndex(t.model().index(r, 0), flags)

    # --- commandes ------------------------------------------------------------------------
    def edit(self, exec_dialog: bool = True):
        """Le formulaire de l'opération (stratégie, outil, passes, zone…) ;
        validé, son parcours est recalculé s'il l'était. La sélection du
        dessin 2D n'y est pas prise. Rend le formulaire."""
        if self._need() is None:
            return None
        dlg = self.cp().edit_op(exec_dialog=exec_dialog, take_selection=False)
        if dlg is not None and not exec_dialog:
            dlg.finished.connect(lambda _r: self.fill())
        else:
            self.fill()
        return dlg

    def edit_tool(self, exec_dialog: bool = True):
        """Le formulaire de l'outil de l'opération ; validé, les parcours
        calculés des opérations qui s'en servent sont recalculés."""
        if self._need() is None:
            return None
        dlg = self.cp().edit_op_tool(exec_dialog=exec_dialog)
        if dlg is not None and not exec_dialog:
            dlg.finished.connect(lambda _r: self.fill())
        else:
            self.fill()
        return dlg

    def recompute(self):
        got = self._need()
        if got is None:
            return None
        s, _r, op = got
        if op.kind == 'instruction':
            return None
        out = self.cp().compute_op(op)
        self.fill()
        return out

    def duplicate(self):
        if self._need() is None:
            return None
        c = self.cp().duplicate_op()
        self.fill()
        if c is not None:
            self.select(c.id)
        return c

    def move(self, d: int) -> bool:
        """Monter (-1) ou descendre (+1) parmi les usinages de la liste : il
        prend la place de son voisin dans la liste (ses parcours le suivent)."""
        got = self._need()
        if got is None:
            return False
        s, r, op = got
        shown = [o.id for o in self.ops()]
        i = shown.index(op.id) if op.id in shown else -1
        if not 0 <= i + d < len(shown) or i < 0:
            return False
        q = next(k for k, o in enumerate(s.operations) if o.id == shown[i + d])
        s.operations[r], s.operations[q] = s.operations[q], s.operations[r]
        cp = self.cp()
        cp.save(s)
        cp._paths_follow({s.operations[r].id, s.operations[q].id}, s)
        self.fill()
        self.select(op.id)
        return True

    def remove_path(self) -> int:
        """Le parcours calculé de l'opération retiré (elle reste : « Recalculer »)."""
        got = self._need()
        if got is None:
            return 0
        n = self.cp().remove_op_paths(got[2])
        if not n:
            self.win.statusBar().showMessage(tr('Pas de parcours calculé pour cet usinage'), 5000)
        self.fill()
        return n

    def remove_op(self) -> bool:
        """L'opération et son parcours supprimés (Annuler la rend)."""
        got = self._need()
        if got is None:
            return False
        _s, _r, op = got
        shown = [o.id for o in self.ops()]
        i = shown.index(op.id) if op.id in shown else -1
        self.cp().remove_op()
        self.fill()
        rest = [o.id for o in self.ops()]
        if rest and i >= 0:                              # la suivante choisie : Suppr plusieurs fois
            self.select(rest[min(i, len(rest) - 1)])
        return True

    def menu(self, pos=None, exec_menu: bool = True):
        if pos is not None:
            it = self.tree.itemAt(pos)
            if it is not None:
                self.tree.setCurrentItem(it)
                it.setSelected(True)
        A = getattr(self.win, 'A', None) or {}
        m = QMenu(self)
        for k in BUTTONS:
            if k in A:
                m.addAction(A[k])
            if k in ('cam3d_op_duplicate', 'cam3d_op_down'):
                m.addSeparator()
        if exec_menu:
            m.exec(self.tree.viewport().mapToGlobal(pos) if pos is not None else self.cursor().pos())
            m.deleteLater()
        return m
