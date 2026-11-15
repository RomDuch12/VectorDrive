"""La fenêtre de l'historique d'un volume (core.history3d) : ses étapes dans
l'ordre, de quoi reprendre un réglage, une esquisse, ou suspendre une étape."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout)

from ..core import history3d as HI
from ..i18n import tr
from .fit import no_hscroll


class HistoryDialog(QDialog):
    def __init__(self, win, item):
        super().__init__(win)
        self.win, self.item = win, item
        self.setWindowTitle(tr('Historique du volume'))
        self.resize(620, 460)
        box = QVBoxLayout(self)
        self.note = QLabel(tr('Reprenez un réglage ou une esquisse : le volume se recalcule, à sa place, '
                              'avec tout ce qui vient après.'))
        self.note.setWordWrap(True)
        box.addWidget(self.note)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([tr('Étape'), tr('Réglages')])
        self.tree.setColumnWidth(0, 230)
        self.tree.setUniformRowHeights(True)
        self.tree.currentItemChanged.connect(lambda *_a: self.update_buttons())
        self.tree.itemDoubleClicked.connect(lambda *_a: self.edit())
        box.addWidget(self.tree, 1)
        self.status = QLabel('')
        self.status.setWordWrap(True)
        box.addWidget(self.status)
        row = QHBoxLayout()
        self.edit_button = QPushButton(tr('Modifier…'))
        self.edit_button.clicked.connect(lambda _=False: self.edit())
        self.suspend_button = QPushButton(tr('Suspendre'))
        self.suspend_button.setToolTip(tr('Le volume se recalcule sans cette étape ; elle reste dans la liste'))
        self.suspend_button.clicked.connect(lambda _=False: self.toggle_off())
        close = QPushButton(tr('Fermer'))
        close.clicked.connect(self.accept)
        row.addWidget(self.edit_button)
        row.addWidget(self.suspend_button)
        row.addStretch(1)
        row.addWidget(close)
        box.addLayout(row)
        no_hscroll(self)
        self.refresh()

    # --- la liste -------------------------------------------------------------
    def hist(self) -> dict | None:
        return HI.history_of(self.item)

    def entry_line(self, entry: dict) -> tuple:
        """(titre, détail) d'une entrée."""
        if entry['kind'] == 'solid':
            return tr('Volume de l’étape {0}').format(entry['step'] + 1), entry.get('name', '')
        data = entry['item']
        extra = data.get('extra') or {}
        if 'sketch' in extra:
            return tr('Esquisse'), data.get('name', '')
        if 'solide' in extra:
            return tr('Volume figé'), data.get('name', '')
        return tr('Tracé'), data.get('name', '')

    def refresh(self, ref=None) -> None:
        """La liste d'après l'objet courant, la ligne `ref` choisie (par défaut, la dernière étape)."""
        self.tree.clear()
        hist = self.hist()
        if hist is not None:
            last = len(hist['steps']) - 1
            want = last if ref is None else (ref if isinstance(ref, tuple) else ref % (last + 1))
            current = None
            for i, step in enumerate(hist['steps']):
                title = f'{i + 1}. {self.win.history_title(step)}'
                if step.get('off'):
                    title = tr('{0} (suspendue)').format(title)
                line = QTreeWidgetItem(self.tree, [title, step.get('shown', '')])
                line.setData(0, Qt.ItemDataRole.UserRole, [i])
                line.setToolTip(1, step.get('shown', ''))
                if want == i:
                    current = line
                for k, entry in enumerate(step['inputs']):
                    sub = QTreeWidgetItem(line, list(self.entry_line(entry)))
                    sub.setData(0, Qt.ItemDataRole.UserRole, [i, k])
                    if want == (i, k):
                        current = sub
            self.tree.expandAll()
            if current is not None:
                self.tree.setCurrentItem(current)
        self.update_buttons()

    def current_ref(self):
        """La ligne choisie : le rang d'une étape, ou (étape, entrée) ; None : aucune."""
        line = self.tree.currentItem()
        if line is None:
            return None
        data = line.data(0, Qt.ItemDataRole.UserRole)
        return data[0] if len(data) == 1 else (data[0], data[1])

    def current_entry(self) -> dict | None:
        ref, hist = self.current_ref(), self.hist()
        return HI.at(hist, ref) if ref is not None and hist is not None else None

    def can_edit(self, entry) -> bool:
        if entry is None:
            return False
        return HI.sketch_of(entry) is not None or (HI.is_step(entry) and entry.get('params') is not None)

    def update_buttons(self) -> None:
        entry = self.current_entry()
        step = entry is not None and HI.is_step(entry)
        self.edit_button.setEnabled(self.can_edit(entry))
        self.edit_button.setText(tr('Modifier l’esquisse…') if entry is not None and HI.sketch_of(entry)
                                 else tr('Modifier…'))
        self.suspend_button.setEnabled(step and HI.can_suspend(entry))
        self.suspend_button.setText(tr('Reprendre') if step and entry.get('off') else tr('Suspendre'))

    # --- les gestes -----------------------------------------------------------
    def done_change(self, new, ref) -> None:
        """Après une tentative : le nouvel objet, ou ce qui n'a pas marché."""
        if new is None:
            self.status.setText(self.win.history_error)
            return
        self.item = new
        self.status.setText(tr('Volume recalculé.'))
        self.refresh(ref)

    def edit(self) -> None:
        entry, ref = self.current_entry(), self.current_ref()
        if not self.can_edit(entry):
            return
        if HI.sketch_of(entry) is not None:
            new = self.win.history_edit_sketch(self.item, ref)
        else:
            new = self.win.history_edit_params(self.item, ref)
        self.done_change(new, ref)

    def toggle_off(self) -> None:
        entry, ref = self.current_entry(), self.current_ref()
        if entry is None or not HI.is_step(entry) or not HI.can_suspend(entry):
            return
        self.done_change(self.win.history_set_off(self.item, ref, not entry.get('off')), ref)
