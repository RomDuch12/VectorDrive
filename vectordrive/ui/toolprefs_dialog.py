"""Outils proposés par opération : pour chaque stratégie, les natures, dossiers
ou outils précis à proposer, dans l'ordre ; seulement eux ou en tête ; aperçu
de l'ordre obtenu avec Mes outils ; où ces choix s'appliquent (cam.toolprefs)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QMenu, QPushButton, QSplitter, QVBoxLayout, QWidget)

from ..cam import model, toollib, toolprefs
from ..i18n import tr


class ToolPrefsDialog(QDialog):
    def __init__(self, parent, settings, library=(), kind: str = ''):
        super().__init__(parent)
        self.setWindowTitle(tr('Outils proposés par opération'))
        self.setSizeGripEnabled(True)
        self.resize(1000, 640)
        self.settings = settings
        self.library = list(library or [])
        self.kinds = model.op_kinds()
        saved = toolprefs.load(settings)
        self.prefs = {k: toolprefs.pref_for(k, saved) for k in self.kinds}
        lay = QVBoxLayout(self)
        split = QSplitter()
        self.ops = QListWidget()
        for k, lab in self.kinds.items():
            it = QListWidgetItem(tr(lab))
            it.setData(Qt.ItemDataRole.UserRole, k)
            it.setToolTip(tr(lab))
            self.ops.addItem(it)
        self.ops.currentRowChanged.connect(lambda _r: self._show())
        self.ops.setMinimumWidth(220)
        split.addWidget(self.ops)
        mid = QWidget()
        ml = QVBoxLayout(mid)
        form = QFormLayout()
        self.mode = QComboBox()
        for k, lab in toolprefs.MODES.items():
            self.mode.addItem(tr(lab), k)
        self.mode.currentIndexChanged.connect(lambda _i: self._set('mode', self.mode.currentData()))
        form.addRow(tr('Proposer'), self.mode)
        self.sort = QComboBox()
        for k, lab in toolprefs.SORTS.items():
            self.sort.addItem(tr(lab), k)
        self.sort.currentIndexChanged.connect(lambda _i: self._set('sort', self.sort.currentData()))
        form.addRow(tr('Dans une même ligne'), self.sort)
        ml.addLayout(form)
        hint = QLabel(tr('Outils proposés, dans l\'ordre (un outil prend le rang de la première ligne '
                         'qu\'il remplit) — aucune ligne : tous les outils'))
        hint.setWordWrap(True)
        ml.addWidget(hint)
        self.rules = QListWidget()
        ml.addWidget(self.rules, 1)
        row = QHBoxLayout()
        self.btns = {}
        nat = QPushButton(tr('+ Nature'))
        m = QMenu(nat)
        for k, lab in model.TOOL_KINDS.items():
            m.addAction(tr(lab), lambda kk=k: self.add_rule({'type': 'nature', 'value': kk}))
        nat.setMenu(m)
        row.addWidget(nat)
        self.btns['nature'] = nat
        for key, text, slot in (('dossier', tr('+ Dossier…'), self.add_folder),
                                ('outil', tr('+ Outil…'), self.add_tool),
                                ('up', '↑', lambda: self.move_rule(-1)), ('down', '↓', lambda: self.move_rule(1)),
                                ('del', tr('Retirer'), self.remove_rule),
                                ('reset', tr('Réglage par défaut'), self.reset_kind),
                                ('copy', tr('Appliquer aussi à…'), self.copy_to)):
            if key == 'reset':                                  # deux lignes : tient sur un petit écran
                row.addStretch(1)
                ml.addLayout(row)
                row = QHBoxLayout()
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, s=slot: s())
            row.addWidget(b)
            self.btns[key] = b
        row.addStretch(1)
        ml.addLayout(row)
        split.addWidget(mid)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.addWidget(QLabel(tr('Ordre obtenu avec Mes outils')))
        self.preview = QListWidget()
        right.setMinimumWidth(240)
        rl.addWidget(self.preview, 1)
        split.addWidget(right)
        split.setSizes([260, 440, 300])
        lay.addWidget(split, 1)
        g = QGroupBox(tr('Où ces choix s\'appliquent'))
        gl = QVBoxLayout(g)
        used = QLabel('<br>'.join(f'<b>{tr(who)}</b> : {tr(how)}' for who, how in toolprefs.USED_BY))
        used.setWordWrap(True)
        gl.addWidget(used)
        lay.addWidget(g)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        start = list(self.kinds).index(kind) if kind in self.kinds else 0
        self.ops.setCurrentRow(start)
        self._show()

    # --- état ---------------------------------------------------------------------------------------
    def kind(self) -> str:
        it = self.ops.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it is not None else next(iter(self.kinds))

    def pref(self) -> dict:
        return self.prefs[self.kind()]

    def set_kind(self, kind: str) -> None:
        self.ops.setCurrentRow(list(self.kinds).index(kind))

    def _set(self, key: str, value) -> None:
        if value is not None and self.pref().get(key) != value:
            self.pref()[key] = value
            self._show(keep_combos=True)

    def _show(self, keep_combos: bool = False, row: int | None = None) -> None:
        p = self.pref()
        if not keep_combos:
            for c, key in ((self.mode, 'mode'), (self.sort, 'sort')):
                c.blockSignals(True)
                c.setCurrentIndex(max(0, c.findData(p[key])))
                c.blockSignals(False)
        self.rules.clear()
        for r in p['rules']:
            self.rules.addItem(toolprefs.describe(r, tr))
        if p['rules']:
            self.rules.setCurrentRow(min(len(p['rules']) - 1, row if row is not None else 0))
        for i in range(self.ops.count()):                       # ● : réglage changé
            it = self.ops.item(i)
            k = it.data(Qt.ItemDataRole.UserRole)
            changed = toolprefs.normalized(self.prefs[k]) != toolprefs.default_for(k)
            it.setText(('● ' if changed else '') + tr(self.kinds[k]))
        self.preview.clear()
        ranked = toolprefs.ordered(self.library, self.kind(), {self.kind(): p})
        for t in ranked[:200]:
            ok = toolprefs.suits(t, self.kind(), {self.kind(): p})
            it = QListWidgetItem(f'{"✓" if ok else "·"}  T{t.number} {t.name} — Ø {t.diameter:g}  '
                                 f'({toollib.folder_of(t)})')
            if not ok:
                it.setForeground(Qt.GlobalColor.gray)
            self.preview.addItem(it)
        if not self.library:
            self.preview.addItem(tr('(Mes outils est vide)'))

    # --- règles ---------------------------------------------------------------------------------------
    def add_rule(self, rule: dict) -> None:
        rules = self.pref()['rules']
        if any(r.get('type') == rule.get('type') and r.get('value') == rule.get('value') for r in rules):
            return
        rules.append(dict(rule))
        self._show(keep_combos=True, row=len(rules) - 1)

    def add_folder(self, name: str | None = None) -> bool:
        names = toollib.folders(self.library) if self.library else []
        if name is None:
            if not names:
                return False
            from PySide6.QtWidgets import QInputDialog
            name, ok = QInputDialog.getItem(self, tr('Dossier de Mes outils'), tr('Dossier'), names, 0, False)
            if not ok:
                return False
        if not name:
            return False
        self.add_rule({'type': 'dossier', 'value': name})
        return True

    def add_tool(self, tool=None) -> bool:
        if tool is None:
            if not self.library:
                return False
            from .tool_picker import ToolPickerDialog
            dlg = ToolPickerDialog(self, [], {t.id: t for t in self.library}, settings=self.settings)
            if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.choice:
                return False
            tool = next((t for t in self.library if 'lib:' + t.id == dlg.choice), None)
            if tool is None:
                return False
        self.add_rule(toolprefs.tool_rule(tool))
        return True

    def move_rule(self, d: int) -> bool:
        rules = self.pref()['rules']
        i = self.rules.currentRow()
        j = i + d
        if not (0 <= i < len(rules) and 0 <= j < len(rules)):
            return False
        rules[i], rules[j] = rules[j], rules[i]
        self._show(keep_combos=True, row=j)
        return True

    def remove_rule(self) -> bool:
        rules = self.pref()['rules']
        i = self.rules.currentRow()
        if not 0 <= i < len(rules):
            return False
        del rules[i]
        self._show(keep_combos=True, row=max(0, i - 1))
        return True

    def reset_kind(self) -> None:
        self.prefs[self.kind()] = toolprefs.default_for(self.kind())
        self._show()

    def copy_to(self, kinds=None) -> int:
        """Le réglage de la stratégie choisie, recopié sur d'autres."""
        if kinds is None:
            from PySide6.QtWidgets import QInputDialog
            others = [k for k in self.kinds if k != self.kind()]
            labels = [tr(self.kinds[k]) for k in others]
            lab, ok = QInputDialog.getItem(self, tr('Appliquer aussi à'), tr('Opération'), labels, 0, False)
            if not ok:
                return 0
            kinds = [others[labels.index(lab)]]
        src = toolprefs.normalized(self.pref())
        for k in kinds:
            self.prefs[k] = {'rules': [dict(r) for r in src['rules']], 'mode': src['mode'], 'sort': src['sort']}
        self._show(keep_combos=True)
        return len(kinds)

    def accept(self) -> None:
        if self.settings is not None:
            toolprefs.save(self.settings, self.prefs)
        super().accept()
