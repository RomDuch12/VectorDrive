"""Lettre par lettre : choisir des lettres dans le texte et les régler. Effet immédiat sur le dessin."""
from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QPlainTextEdit,
                               QPushButton, QVBoxLayout)

from ..core import text as TX
from ..core.spell import _char_index
from ..i18n import tr

#: pas du clavier (Alt+flèches), en % de la hauteur ; Maj : cinq fois plus
KEY_STEP = 1.0
#: réglage, libellé, mini, maxi, pas, suffixe
FIELDS = (('kern', 'Crénage (décale aussi ce qui suit)', -500.0, 500.0, 1.0, ' %'),
          ('dx', 'Décalage en X', -500.0, 500.0, 1.0, ' %'),
          ('dy', 'Décalage en Y', -500.0, 500.0, 1.0, ' %'),
          ('h', 'Hauteur', 1.0, 1000.0, 5.0, ' %'),
          ('w', 'Largeur', 1.0, 1000.0, 5.0, ' %'),
          ('rot', 'Rotation', -360.0, 360.0, 5.0, ' °'))


class LettersDialog(QDialog):
    """`apply(réglages)` pose les réglages sur le texte et refait le dessin ; `initial` : ceux d'avant, repris par Annuler."""

    def __init__(self, parent, item, apply):
        super().__init__(parent)
        from .fit import release
        release(self)                                    # fermée : détruite, pas gardée par son parent
        self.item = item
        self.apply = apply
        self.initial = TX.char_fx(item)
        self.fx = {i: dict(f) for i, f in self.initial.items()}
        self._loading = False
        self.setWindowTitle(tr('Lettres'))
        v = QVBoxLayout(self)
        v.addWidget(QLabel(tr('Choisir les lettres dans le texte. Sans choix : la lettre qui suit le curseur. '
                              'Les distances sont en % de la hauteur du texte.')))
        self.view = QPlainTextEdit(item.text)
        self.view.setReadOnly(True)
        self.view.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse
                                          | Qt.TextInteractionFlag.TextSelectableByKeyboard)
        self.view.setMaximumHeight(90)
        f = QFont(self.view.font())
        f.setPointSize(f.pointSize() + 4)
        self.view.setFont(f)
        self.view.selectionChanged.connect(self.load)
        self.view.cursorPositionChanged.connect(self.load)
        self.view.installEventFilter(self)
        v.addWidget(self.view)
        form = QFormLayout()
        from .dialogs import FontBox
        self.font_box = FontBox()
        self.font_box.setToolTip(tr('La police des lettres choisies ; celle du texte les remet comme le reste'))
        self.font_box.activated.connect(lambda _=0: self.set_font(self.font_box.currentText()))
        self.font_box.lineEdit().editingFinished.connect(lambda: self.set_font(self.font_box.currentText()))
        form.addRow(tr('Police'), self.font_box)
        self.fields = {}
        for key, label, lo, hi, step, suffix in FIELDS:
            b = QDoubleSpinBox()
            b.setRange(lo, hi)
            b.setDecimals(1)
            b.setSingleStep(step)
            b.setSuffix(suffix)
            b.valueChanged.connect(lambda value, k=key: self.set_value(k, value))
            form.addRow(tr(label), b)
            self.fields[key] = b
        v.addLayout(form)
        row = QHBoxLayout()
        self.b_sup = QPushButton(tr('Exposant'))
        self.b_sub = QPushButton(tr('Indice'))
        self.b_normal = QPushButton(tr('Normal'))
        self.b_normal.setToolTip(tr('Retire les réglages des lettres choisies'))
        for b in (self.b_sup, self.b_sub, self.b_normal):
            b.setAutoDefault(False)
            row.addWidget(b)
        self.b_sup.clicked.connect(lambda: self.put(TX.SUPERSCRIPT))
        self.b_sub.clicked.connect(lambda: self.put(TX.SUBSCRIPT))
        self.b_normal.clicked.connect(lambda: self.put({}))
        v.addLayout(row)
        v.addWidget(QLabel(tr('Alt+flèches : crénage et décalage en Y, plus vite avec Maj.')))
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        v.addWidget(box)
        self.load()

    def indices(self) -> list[int]:
        """Les lettres choisies, en positions du texte. Un saut de ligne n'est pas une lettre."""
        c = self.view.textCursor()
        s = self.item.text
        a, b = _char_index(s, c.selectionStart()), _char_index(s, c.selectionEnd())
        got = range(a, b) if b > a else ([a] if a < len(s) else [])
        return [i for i in got if s[i] != '\n']

    def select(self, a: int, b: int | None = None) -> None:
        """Choisit les lettres a … b-1, ou place le curseur devant la lettre a."""
        s = self.item.text
        unit = lambda i: len(s[:i].encode('utf-16-le', 'surrogatepass')) // 2
        c = self.view.textCursor()
        c.setPosition(unit(a))
        if b is not None:
            c.setPosition(unit(b), QTextCursor.MoveMode.KeepAnchor)
        self.view.setTextCursor(c)

    def load(self) -> None:
        """Les champs montrent les réglages de la première lettre choisie."""
        got = self.indices()
        f = self.fx.get(got[0], {}) if got else {}
        self._loading = True
        for key, b in self.fields.items():
            b.setEnabled(bool(got))
            b.setValue(float(f.get(key, TX.CHAR_NEUTRAL[key])))
        self.font_box.setEnabled(bool(got))
        self.font_box.setCurrentFont(f.get('font') or self.item.font)
        self._loading = False

    def _changed(self) -> None:
        self.fx = TX.clean_char_fx(self.fx)
        self.apply({i: dict(f) for i, f in self.fx.items()})

    def set_value(self, key: str, value: float) -> None:
        if self._loading:
            return
        for i in self.indices():
            self.fx.setdefault(i, {})[key] = float(value)
        self._changed()

    def set_font(self, name: str) -> None:
        """Les lettres choisies dans cette police. Celle du texte : le réglage disparaît, elles le suivront s'il change."""
        if self._loading:
            return
        name = name.strip()
        changed = False
        for i in self.indices():
            f = self.fx.setdefault(i, {})
            if name and name != self.item.font:
                changed = changed or f.get('font') != name
                f['font'] = name
            elif 'font' in f:
                del f['font']
                changed = True
        if changed:
            self._changed()

    def put(self, values: dict) -> None:
        """Les lettres choisies reçoivent ces réglages, à la place des leurs."""
        for i in self.indices():
            self.fx[i] = dict(values)
        self._changed()
        self.load()

    def nudge(self, key: str, delta: float) -> None:
        for i in self.indices():
            f = self.fx.setdefault(i, {})
            f[key] = float(f.get(key, TX.CHAR_NEUTRAL[key])) + delta
        self._changed()
        self.load()

    def eventFilter(self, obj, ev) -> bool:
        if obj is self.view and ev.type() == QEvent.Type.KeyPress and ev.modifiers() & Qt.KeyboardModifier.AltModifier:
            step = KEY_STEP * (5.0 if ev.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1.0)
            move = {Qt.Key.Key_Left: ('kern', -step), Qt.Key.Key_Right: ('kern', step),
                    Qt.Key.Key_Up: ('dy', step), Qt.Key.Key_Down: ('dy', -step)}.get(ev.key())
            if move:
                self.nudge(*move)
                return True
        return super().eventFilter(obj, ev)

    def reject(self) -> None:
        if self.fx != self.initial:
            self.fx = {i: dict(f) for i, f in self.initial.items()}
            self.apply(self.initial)
        super().reject()
