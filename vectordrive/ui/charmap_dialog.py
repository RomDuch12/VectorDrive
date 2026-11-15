"""Liste des caractères (TypeEdit : Rapido ▸ Liste des caractères) : les
caractères d'une police, par blocs, pour insérer un symbole (Ø, ±, °, ©…)
dans le texte sélectionné."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPixmap, QTransform
from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
                               QVBoxLayout)

from ..core import fonts
from ..i18n import tr
from .dialogs import FontBox

#: blocs proposés : libellé → (premier, dernier) code
BLOCKS = {
    'Tous': (0, 0x10FFFF), 'Latin de base': (0x20, 0x7F), 'Latin-1 (accents, ©, °, ±…)': (0xA0, 0xFF),
    'Latin étendu': (0x100, 0x24F), 'Grec': (0x370, 0x3FF), 'Ponctuation, exposants, monnaies': (0x2000, 0x20CF),
    'Lettres et chiffres spéciaux (™, №, ½…)': (0x2100, 0x218F), 'Flèches': (0x2190, 0x21FF),
    'Mathématiques': (0x2200, 0x22FF), 'Technique (⌀, ⌘…)': (0x2300, 0x23FF), 'Formes géométriques': (0x25A0, 0x25FF),
    'Symboles divers': (0x2600, 0x27BF), 'Usage privé (polices de symboles)': (0xE000, 0xF8FF),
}
#: au-delà, la liste est tronquée (choisir un bloc)
MAX_ITEMS = 1500


class CharMapDialog(QDialog):
    vd_keep = True                  # réemployée (gardée par la fenêtre) : pas libérée à la fermeture

    def __init__(self, win, font: str = 'Arial'):
        super().__init__(win)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        self.win = win
        self.setWindowTitle(tr('Liste des caractères'))
        self.setSizeGripEnabled(True)
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        self.font_box = FontBox()
        self.font_box.setCurrentFont(font)
        self.block = QComboBox()
        for k in BLOCKS:
            self.block.addItem(tr(k), k)
        self.block.setCurrentIndex(self.block.findData('Latin-1 (accents, ©, °, ±…)'))
        row.addWidget(QLabel(tr('Police')))
        row.addWidget(self.font_box, 2)
        row.addWidget(self.block, 2)
        lay.addLayout(row)
        self.grid = QListWidget()
        self.grid.setViewMode(QListWidget.ViewMode.IconMode)
        self.grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.grid.setGridSize(QSize(44, 48))
        self.grid.setIconSize(QSize(32, 32))
        self.grid.setUniformItemSizes(True)
        lay.addWidget(self.grid, 1)
        self.info = QLabel()
        lay.addWidget(self.info)
        btns = QHBoxLayout()
        ins = QPushButton(tr('Insérer'))
        ins.clicked.connect(lambda _=False: self.insert())
        close = QPushButton(tr('Fermer'))
        close.clicked.connect(lambda _=False: self.close())
        btns.addStretch(1)
        btns.addWidget(ins)
        btns.addWidget(close)
        lay.addLayout(btns)
        self.grid.itemDoubleClicked.connect(lambda _it: self.insert())
        self.grid.currentItemChanged.connect(lambda cur, _prev: self._describe(cur))
        self.font_box.currentTextChanged.connect(lambda _t: self.fill())
        self.block.currentIndexChanged.connect(lambda _i: self.fill())
        self.fill()
        self.resize(560, 460)

    def characters(self) -> list[str]:
        lo, hi = BLOCKS.get(self.block.currentData(), (0, 0x10FFFF))
        return [c for c in fonts.characters(self.font_box.currentText()) if lo <= ord(c) <= hi]

    def fill(self) -> None:
        self.grid.clear()
        family = self.font_box.currentText()
        chars = self.characters()
        system = family in QFontDatabase.families()
        qf = QFont(family, 16)
        for ch in chars[:MAX_ITEMS]:
            it = QListWidgetItem()
            it.setData(Qt.ItemDataRole.UserRole, ch)
            it.setToolTip(f'U+{ord(ch):04X}  {ch}')
            if system:
                it.setText(ch)
                it.setFont(qf)
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            else:                                          # police hors du système : le dessin du glyphe
                it.setIcon(self._icon(family, ch))
            self.grid.addItem(it)
        more = len(chars) - MAX_ITEMS
        self.info.setText(tr('{0} caractère(s)').format(len(chars)) +
                          (' — ' + tr('{0} non affichés : choisir un bloc').format(more) if more > 0 else ''))

    @staticmethod
    def _icon(family: str, ch: str) -> QIcon:
        from .canvas import to_qpath
        ff = fonts.find_font(family)
        pm = QPixmap(32, 32)
        pm.fill(QColor(0, 0, 0, 0))
        if ff:
            path, _adv = fonts.glyph(ff[0], ff[1], ch)
            bb = path.bbox() if path.contours else None
            if bb:
                w, h = max(bb[2] - bb[0], 1e-9), max(bb[3] - bb[1], 1e-9)
                k = 26 / max(w, h)
                p = QPainter(pm)
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                t = QTransform()
                t.translate(16 - k * (bb[0] + bb[2]) / 2, 16 + k * (bb[1] + bb[3]) / 2)
                t.scale(k, -k)
                p.setTransform(t)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor('#222'))
                p.drawPath(to_qpath(path))
                p.end()
        return QIcon(pm)

    def current(self) -> str:
        it = self.grid.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it is not None else ''

    def _describe(self, it) -> None:
        if it is not None:
            ch = it.data(Qt.ItemDataRole.UserRole)
            self.info.setText(f'U+{ord(ch):04X}  {ch}')

    def insert(self) -> str:
        ch = self.current()
        if ch:
            self.win.insert_characters(ch)
        return ch
