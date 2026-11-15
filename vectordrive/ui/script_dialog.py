"""La fenêtre des scripts de forme : la liste, le texte, l'essai et le lancement."""
from __future__ import annotations

import pathlib

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QVBoxLayout, QWidget)

from ..core import shapescript as SS
from ..i18n import tr

_EXAMPLE = """' NewCurve, MoveTo, LineTo, ArcHTo, ArcTTo, ClosePath : x, y, z (m)
Dim n, r, i, a
n = 6
r = 0.020
If NewCurve Then
  MoveTo r, 0, 0
  For i = 1 To n - 1
    a = i * 8 * Atn(1) / n
    LineTo r * Cos(a), r * Sin(a), 0
  Next
  ClosePath
End If
"""


def why(ex: SS.ScriptError) -> str:
    """Le message d'une erreur de script, avec son numéro de ligne."""
    text = {
        'syntax': tr('Erreur de syntaxe près de « {0} ».'),
        'array': tr('Tableau trop grand.'),
        'index': tr('Indice hors du tableau.'),
        'number': tr('« {0} » n’est pas un nombre.'),
        'steps': tr('Le script ne s’arrête pas : il a dépassé le nombre de pas permis.'),
        'zero': tr('Division par zéro.'),
        'value': tr('Valeur impossible ({0}).'),
        'depth': tr('Trop d’appels imbriqués.'),
        'include': tr('Script repris introuvable : {0}.'),
        'args': tr('Mauvais nombre d’arguments pour {0}.'),
        'unsupported': tr('{0} agit sur le document de TypeEdit : ce n’est pas repris ici.'),
        'unknown': tr('Fonction inconnue : {0}.'),
        'segments': tr('Le script dessine trop de segments.'),
    }.get(ex.key, '{0}').format(ex.arg)
    where = tr('Ligne {0}').format(ex.line) if ex.line else ''
    if ex.file:
        where = f'{ex.file}, {where}' if where else ex.file
    return f'{where} : {text}' if where else text


class ParamBox(QDialog):
    """La boîte que construit un script (WndScriptApi.AddEdit puis DoModalDynamic)."""

    def __init__(self, parent, title: str, edits: list):
        super().__init__(parent)
        self.setWindowTitle(title or tr('Script'))
        self.fields: dict[str, QLineEdit] = {}
        form = QFormLayout(self)
        for ident, label, default in edits:
            box = QLineEdit(default)
            self.fields[ident] = box
            form.addRow(label, box)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> dict:
        return {k: v.text() for k, v in self.fields.items()}


def make_host(parent, script: pathlib.Path | None, params=(), reedit=None) -> SS.Host:
    """Ce qu'un script voit de l'application : ses boîtes s'ouvrent au-dessus de `parent`."""
    def ask(title, default):
        text, ok = QInputDialog.getText(parent, tr('Script'), title, text=default)
        return text if ok else None

    def dialog(title, edits):
        box = ParamBox(parent, title, edits)
        return box.values() if box.exec() == QDialog.DialogCode.Accepted else None

    def show(text):
        QMessageBox.information(parent, tr('Script'), text)

    return SS.Host(params=list(params), ask=ask, dialog=dialog, show=show, reedit=reedit,
                   folder=script.parent if script is not None else None,
                   profile=SS.load_values(script) if script is not None else {})


class ScriptDialog(QDialog):
    """Les scripts de l'utilisateur, et ceux de TypeEdit s'il est installé (ceux-là en lecture seule)."""

    def __init__(self, win, te_folder: pathlib.Path | None = None):
        super().__init__(win)
        self.win = win
        self.te_folder = te_folder
        self.path: pathlib.Path | None = None
        self.setWindowTitle(tr('Scripts de forme'))
        self.resize(980, 640)
        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._picked)
        self.edit = QPlainTextEdit()
        font = QFont('Consolas', 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.edit.setFont(font)
        self.edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        split = QSplitter()
        split.addWidget(self.list)
        right = QWidget()
        lay = QVBoxLayout(right)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.edit, 1)
        lay.addWidget(self.message)
        split.addWidget(right)
        split.setSizes([260, 720])

        self.new_button = QPushButton(tr('Nouveau'))
        self.save_button = QPushButton(tr('Enregistrer'))
        self.slot_button = QPushButton(tr('Placer sur un bouton…'))
        self.slot_button.setToolTip(tr('Script 1 à Script 10 : des boutons à ajouter au ruban ou à appeler par un raccourci'))
        self.slot_button.clicked.connect(lambda _=False: self.assign_slot())
        self.test_button = QPushButton(tr('Essayer'))
        self.test_button.setToolTip(tr('Lance le script sans rien ajouter au dessin et dit ce qu’il dessine'))
        self.run_button = QPushButton(tr('Dessiner'))
        self.run_button.setDefault(True)
        close = QPushButton(tr('Fermer'))
        self.new_button.clicked.connect(self.new_script)
        self.save_button.clicked.connect(lambda _=False: self.save_script())
        self.test_button.clicked.connect(lambda _=False: self.try_script())
        self.run_button.clicked.connect(lambda _=False: self.draw_script())
        close.clicked.connect(self.reject)
        row = QHBoxLayout()
        for b in (self.new_button, self.save_button, self.slot_button):
            row.addWidget(b)
        row.addStretch(1)
        for b in (self.test_button, self.run_button, close):
            row.addWidget(b)
        outer = QVBoxLayout(self)
        outer.addWidget(split, 1)
        outer.addLayout(row)
        self.refresh()
        self.new_script()

    def refresh(self, select: pathlib.Path | None = None) -> None:
        self.list.blockSignals(True)
        self.list.clear()

        def section(title, folder):
            files = SS.scripts_in(folder) if folder is not None else []
            if not files:
                return
            head = QListWidgetItem(title)
            head.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list.addItem(head)
            for f in files:
                it = QListWidgetItem('  ' + f.stem)
                it.setData(Qt.ItemDataRole.UserRole, str(f))
                self.list.addItem(it)
                if select is not None and f == select:
                    self.list.setCurrentItem(it)

        section(tr('Mes scripts'), SS.user_dir())
        section(tr('Scripts de TypeEdit (lecture seule)'), self.te_folder)
        self.list.blockSignals(False)

    def _read_only(self) -> bool:
        return self.path is not None and self.te_folder is not None and self.path.parent == self.te_folder

    def _picked(self, item, _previous=None) -> None:
        name = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not name:
            return
        self.path = pathlib.Path(name)
        self.edit.setPlainText(SS.read_text(self.path))
        self.edit.setReadOnly(self._read_only())
        self.save_button.setText(tr('Enregistrer une copie') if self._read_only() else tr('Enregistrer'))
        self.message.clear()

    def new_script(self) -> None:
        self.list.setCurrentItem(None)
        self.path = None
        self.edit.setReadOnly(False)
        self.edit.setPlainText(_EXAMPLE)
        self.save_button.setText(tr('Enregistrer'))
        self.message.clear()

    def save_script(self, name: str | None = None) -> pathlib.Path | None:
        """Enregistre dans « Mes scripts » ; les scripts de TypeEdit ne sont jamais réécrits."""
        target = None if self.path is None or self._read_only() else self.path
        if target is None:
            if name is None:
                suggest = self.path.stem if self.path is not None else ''
                name, ok = QInputDialog.getText(self, tr('Enregistrer'), tr('Nom du script'), text=suggest)
                if not ok:
                    return None
            name = ''.join(c for c in name if c not in '\\/:*?"<>|').strip()
            if not name:
                return None
            target = SS.user_dir() / (name + '.txt')
            if target.exists() and QMessageBox.question(self, tr('Enregistrer'), tr('Remplacer « {0} » ?').format(name)) \
                    != QMessageBox.StandardButton.Yes:
                return None
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix('.tmp')
            tmp.write_text(self.edit.toPlainText(), encoding='utf-8')
            tmp.replace(target)
        except OSError as ex:
            self.message.setText(str(ex))
            return None
        self.path = target
        self.edit.setReadOnly(False)
        self.save_button.setText(tr('Enregistrer'))
        self.refresh(target)
        self.message.setText(tr('Enregistré : {0}').format(target.name))
        return target

    def assign_slot(self, n: int | None = None) -> int | None:
        """Place le script affiché sur un des dix boutons ; un script pas encore enregistré l'est d'abord."""
        if self.path is None and self.save_script() is None:
            return None
        if n is None:
            names = [self.win.script_slot_text(k) for k in range(1, 11)]
            name, ok = QInputDialog.getItem(self, tr('Placer sur un bouton…'), tr('Bouton'), names, 0, False)
            if not ok:
                return None
            n = names.index(name) + 1
        self.win.set_script_slot(n, self.path)
        self.message.setText(tr('Sur le bouton {0} : ajoutez-le au ruban par Personnaliser le ruban, ou donnez-lui un raccourci.').format(n))
        return n

    def _show_error(self, ex: SS.ScriptError) -> None:
        self.message.setText(why(ex))
        if ex.line and not ex.file:
            cursor = QTextCursor(self.edit.document().findBlockByNumber(ex.line - 1))
            cursor.select(QTextCursor.SelectionType.LineUnderCursor)
            self.edit.setTextCursor(cursor)
            self.edit.setFocus()

    def try_script(self):
        """Le résultat du script, dit sans toucher au dessin. Ni les valeurs gardées ne changent."""
        try:
            got = SS.run(self.edit.toPlainText(), make_host(self, self.path))
        except SS.ScriptError as ex:
            self._show_error(ex)
            return None
        n = sum(len(c.segments) for c in got.contours)
        closed = sum(1 for c in got.contours if c.closed)
        text = tr('{0} contours, dont {1} fermés, {2} segments.').format(len(got.contours), closed, n)
        if got.contours:
            from ..core.geom import Path
            x0, y0, x1, y1 = Path(got.contours).bbox()
            text += ' ' + tr('{0:.3f} × {1:.3f} mm').format(x1 - x0, y1 - y0)
        if 'html' in got.notes:
            text += ' ' + tr('Sa boîte HTML n’est pas ouverte : il tourne avec ses valeurs gardées.')
        self.message.setText(text)
        return got

    def draw_script(self):
        try:
            item = self.win.run_shape_script(self.edit.toPlainText(), self.path)
        except SS.ScriptError as ex:
            self._show_error(ex)
            return None
        if item is None:
            self.message.setText(tr('Le script n’a rien dessiné.'))
            return None
        self.accept()
        return item
