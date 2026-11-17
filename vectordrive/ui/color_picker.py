"""Sélecteur de couleur avancé (demande du 17/11, ~19 h 50 : « Panneau couleur : double clic sur la couleur ouvre une
fenetre de selection beaucoup plus avancee que l'actuelle » ; réponse : « Roue + curseurs »).

- **La roue des teintes** : la teinte tourne autour du centre, la saturation va du centre (gris) au bord (pure) ;
  la **barre de luminosité** à côté règle la valeur (du noir à la couleur pleine). Clic ou glisser dans l'une ou
  l'autre.
- **Les curseurs et leurs champs** : RVB (0 à 255), TSV (teinte 0 à 359°, saturation et valeur 0 à 100 %), CMJN (0 à
  100 %), et le **code hexadécimal** (#RRVVBB, #RVB accepté). Tous suivent la couleur, quelle que soit la façon de la
  changer.
- **L'aperçu avant / après** : la couleur de départ et la nouvelle, côte à côte ; un clic sur la couleur de départ y revient.

Il remplace la fenêtre de couleur de Qt pour les couleurs des outils (panneau Couleur : double clic ou clic droit ;
tableau des outils) et la couleur propre des objets (Édition › Couleur…). `get_color` : la fenêtre, puis la couleur
choisie ou None (Annuler). La fenêtre est détruite après usage (aucune fenêtre de dialogue ne reste en mémoire)."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, QRegularExpression, Qt, Signal
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QLinearGradient, QPainter, QPen, QRadialGradient,
                           QRegularExpressionValidator)
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QSizePolicy, QSlider, QSpinBox, QVBoxLayout, QWidget)

from ..i18n import tr

#: côté mini de la roue (px)
WHEEL = 200


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if v < lo else hi if v > hi else v


class HueWheel(QWidget):
    """La roue : teinte = angle (0° à droite, sens trigonométrique), saturation = distance au centre."""

    picked = Signal(float, float)                        # teinte (0 à 360), saturation (0 à 1)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.h, self.s, self.v = 0.0, 0.0, 1.0
        self.setMinimumSize(WHEEL, WHEEL)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def set_hsv(self, h: float, s: float, v: float) -> None:
        self.h, self.s, self.v = h, s, v
        self.update()

    def _geometry(self) -> tuple:
        r = min(self.width(), self.height()) / 2 - 4
        return QPointF(self.width() / 2, self.height() / 2), max(r, 1.0)

    def point_of(self, h: float, s: float) -> QPointF:
        c, r = self._geometry()
        a = math.radians(h)
        return QPointF(c.x() + math.cos(a) * s * r, c.y() - math.sin(a) * s * r)

    def hs_at(self, x: float, y: float) -> tuple:
        """(teinte, saturation) du point (x, y) du widget ; hors de la roue : sur son bord."""
        c, r = self._geometry()
        dx, dy = x - c.x(), c.y() - y
        return math.degrees(math.atan2(dy, dx)) % 360.0, _clamp(math.hypot(dx, dy) / r)

    def paintEvent(self, _ev):                           # noqa: N802 (API Qt)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c, r = self._geometry()
        rect = QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r)
        hue = QConicalGradient(c, 0.0)                   # 0° à droite, dans le sens trigonométrique comme `hs_at`
        for k in range(7):
            hue.setColorAt(k / 6, QColor.fromHsvF((k / 6) % 1.0, 1.0, 1.0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(hue))
        p.drawEllipse(rect)
        white = QRadialGradient(c, r)                    # le centre gris (saturation nulle)
        white.setColorAt(0.0, QColor(255, 255, 255, 255))
        white.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(white))
        p.drawEllipse(rect)
        p.setBrush(QColor(0, 0, 0, int(round((1.0 - self.v) * 255))))   # la luminosité choisie
        p.drawEllipse(rect)
        m = self.point_of(self.h, self.s)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor('black'), 2))
        p.drawEllipse(m, 6, 6)
        p.setPen(QPen(QColor('white'), 1))
        p.drawEllipse(m, 7.5, 7.5)

    def _pick(self, ev) -> None:
        h, s = self.hs_at(ev.position().x(), ev.position().y())
        self.picked.emit(self.h if s <= 1e-9 else h, s)  # au centre exact : pas de teinte, la courante gardée

    def mousePressEvent(self, ev):                       # noqa: N802 (API Qt)
        if ev.button() == Qt.MouseButton.LeftButton:
            self._pick(ev)

    def mouseMoveEvent(self, ev):                        # noqa: N802 (API Qt)
        if ev.buttons() & Qt.MouseButton.LeftButton:
            self._pick(ev)


class ValueBar(QWidget):
    """La barre de luminosité (valeur) : la couleur pleine en haut, le noir en bas."""

    picked = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.h, self.s, self.v = 0.0, 0.0, 1.0
        self.setFixedWidth(26)
        self.setMinimumHeight(WHEEL)
        self.setCursor(Qt.CursorShape.SizeVerCursor)

    def set_hsv(self, h: float, s: float, v: float) -> None:
        self.h, self.s, self.v = h, s, v
        self.update()

    def _span(self) -> tuple:
        return 6.0, max(self.height() - 6.0, 7.0)

    def value_at(self, y: float) -> float:
        top, bottom = self._span()
        return _clamp((bottom - y) / (bottom - top))

    def paintEvent(self, _ev):                           # noqa: N802 (API Qt)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        top, bottom = self._span()
        g = QLinearGradient(0, top, 0, bottom)
        g.setColorAt(0.0, QColor.fromHsvF((self.h % 360.0) / 360.0, self.s, 1.0))
        g.setColorAt(1.0, QColor(0, 0, 0))
        p.setPen(QPen(QColor(120, 120, 120), 1))
        p.setBrush(QBrush(g))
        p.drawRoundedRect(QRectF(4, top, self.width() - 8, bottom - top), 3, 3)
        y = bottom - self.v * (bottom - top)
        p.setPen(QPen(QColor('black'), 2))
        p.setBrush(QColor('white'))
        p.drawRect(QRectF(1, y - 3, self.width() - 2, 6))

    def mousePressEvent(self, ev):                       # noqa: N802 (API Qt)
        if ev.button() == Qt.MouseButton.LeftButton:
            self.picked.emit(self.value_at(ev.position().y()))

    def mouseMoveEvent(self, ev):                        # noqa: N802 (API Qt)
        if ev.buttons() & Qt.MouseButton.LeftButton:
            self.picked.emit(self.value_at(ev.position().y()))


#: les curseurs : (clé, maximum, suffixe)
CHANNELS = {'rvb': (('r', 255, ''), ('g', 255, ''), ('b', 255, '')),
            'tsv': (('h', 359, '°'), ('s', 100, ' %'), ('v', 100, ' %')),
            'cmjn': (('c', 100, ' %'), ('m', 100, ' %'), ('y', 100, ' %'), ('k', 100, ' %'))}


def channel_labels() -> dict:
    """Les libellés des curseurs (traduits à l'ouverture de la fenêtre)."""
    return {('rvb', 'r'): tr('Rouge'), ('rvb', 'g'): tr('Vert'), ('rvb', 'b'): tr('Bleu'),
            ('tsv', 'h'): tr('Teinte'), ('tsv', 's'): tr('Saturation'), ('tsv', 'v'): tr('Luminosité'),
            ('cmjn', 'c'): tr('Cyan'), ('cmjn', 'm'): tr('Magenta'), ('cmjn', 'y'): tr('Jaune'),
            ('cmjn', 'k'): tr('Noir')}


class ColorPicker(QDialog):
    """La fenêtre : roue, barre de luminosité, curseurs RVB / TSV / CMJN, code hexadécimal, avant / après."""

    def __init__(self, initial, parent=None, title: str = ''):
        super().__init__(parent)
        self.setWindowTitle(title or tr('Couleur'))
        start = QColor(initial) if initial is not None else QColor('#000000')
        if not start.isValid():
            start = QColor('#000000')
        self.before = QColor(start)
        self.h, self.s, self.v = self._hsv_of(start, 0.0)
        self._busy = False
        self.spins: dict = {}
        self.sliders: dict = {}
        root = QVBoxLayout(self)
        top = QHBoxLayout()
        self.wheel = HueWheel()
        self.wheel.picked.connect(lambda h, s: self.set_hsv(h, s, self.v if self.v > 0 else 1.0, 'roue'))
        self.bar = ValueBar()
        self.bar.picked.connect(lambda v: self.set_hsv(self.h, self.s, v, 'barre'))
        top.addWidget(self.wheel, 1)
        top.addWidget(self.bar)
        side = QVBoxLayout()
        labels = channel_labels()
        for group, title_, chans in (('rvb', tr('RVB'), CHANNELS['rvb']), ('tsv', tr('TSV'), CHANNELS['tsv']),
                                     ('cmjn', tr('CMJN'), CHANNELS['cmjn'])):
            box = QGroupBox(title_)
            grid = QGridLayout(box)
            grid.setContentsMargins(6, 4, 6, 4)
            for row, (key, top_, suffix) in enumerate(chans):
                sl = QSlider(Qt.Orientation.Horizontal)
                sl.setRange(0, top_)
                sp = QSpinBox()
                sp.setRange(0, top_)
                sp.setSuffix(suffix)
                sl.valueChanged.connect(lambda val, g=group, k=key: self._channel(g, k, val))
                sp.valueChanged.connect(lambda val, g=group, k=key: self._channel(g, k, val))
                grid.addWidget(QLabel(labels[(group, key)]), row, 0)
                grid.addWidget(sl, row, 1)
                grid.addWidget(sp, row, 2)
                self.sliders[(group, key)], self.spins[(group, key)] = sl, sp
            side.addWidget(box)
        hexrow = QHBoxLayout()
        hexrow.addWidget(QLabel(tr('Code')))
        self.hex = QLineEdit()
        self.hex.setValidator(QRegularExpressionValidator(QRegularExpression(r'#?([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})')))
        self.hex.setToolTip(tr('Code hexadécimal : #RRVVBB (ou #RVB)'))
        self.hex.textEdited.connect(self._hex)
        hexrow.addWidget(self.hex, 1)
        side.addLayout(hexrow)
        side.addStretch(1)
        top.addLayout(side)
        root.addLayout(top, 1)
        prev = QHBoxLayout()
        self.old_btn = QPushButton(tr('Couleur de départ'))
        self.old_btn.setToolTip(tr('Un clic revient à la couleur de départ'))
        self.old_btn.clicked.connect(lambda: self.set_color(self.before, 'avant'))
        self.new_lbl = QLabel(tr('Nouvelle couleur'))
        self.new_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for w in (self.old_btn, self.new_lbl):
            w.setMinimumHeight(34)
            prev.addWidget(w, 1)
        self.old_btn.setStyleSheet(self._swatch_css(self.before))
        root.addLayout(prev)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)
        self._show('')

    # --- l'état
    @staticmethod
    def _hsv_of(c: QColor, keep_h: float) -> tuple:
        h, s, v, _a = c.getHsvF()
        h = keep_h if h < 0 else h * 360.0               # gris : Qt ne donne pas de teinte, la précédente est gardée
        return h % 360.0, _clamp(s), _clamp(v)

    def color(self) -> QColor:
        return QColor.fromHsvF((self.h % 360.0) / 360.0, _clamp(self.s), _clamp(self.v))

    def name(self) -> str:
        return self.color().name()

    def set_hsv(self, h: float, s: float, v: float, source: str = '') -> None:
        self.h, self.s, self.v = h % 360.0, _clamp(s), _clamp(v)
        self._show(source)

    def set_color(self, c, source: str = '') -> None:
        c = QColor(c)
        if not c.isValid():
            return
        h, s, v = self._hsv_of(c, self.h)
        if s <= 0.0 or v <= 0.0:                         # gris ou noir : teinte (et saturation au noir) gardées
            h = self.h
            if v <= 0.0:
                s = self.s
        self.h, self.s, self.v = h, s, v
        self._show(source, exact=c)

    @staticmethod
    def _swatch_css(c: QColor) -> str:
        text = '#000000' if c.lightnessF() > 0.55 else '#ffffff'
        return f'background: {c.name()}; color: {text}; border: 1px solid #777; border-radius: 3px;'

    def _show(self, source: str, exact: QColor | None = None) -> None:
        """Tous les éléments mis à la couleur courante, sauf celui d'où vient le changement (`source`)."""
        if self._busy:
            return
        self._busy = True
        try:
            c = QColor(exact) if exact is not None else self.color()
            self.wheel.set_hsv(self.h, self.s, self.v)
            self.bar.set_hsv(self.h, self.s, self.v)
            cc, mm, yy, kk, _a = c.getCmykF()
            values = {('rvb', 'r'): c.red(), ('rvb', 'g'): c.green(), ('rvb', 'b'): c.blue(),
                      ('tsv', 'h'): int(round(self.h)) % 360, ('tsv', 's'): int(round(self.s * 100)),
                      ('tsv', 'v'): int(round(self.v * 100)),
                      ('cmjn', 'c'): int(round(cc * 100)), ('cmjn', 'm'): int(round(mm * 100)),
                      ('cmjn', 'y'): int(round(yy * 100)), ('cmjn', 'k'): int(round(kk * 100))}
            for key, val in values.items():
                if source == key[0]:
                    continue
                for w in (self.sliders[key], self.spins[key]):
                    w.blockSignals(True)
                    w.setValue(val)
                    w.blockSignals(False)
            if source != 'hex':
                self.hex.setText(c.name())
            self.new_lbl.setStyleSheet(self._swatch_css(c))
            self.new_lbl.setText(tr('Nouvelle couleur') + '  ' + c.name())
        finally:
            self._busy = False

    # --- les changements
    def _channel(self, group: str, key: str, val: int) -> None:
        if self._busy:
            return
        for w in (self.sliders[(group, key)], self.spins[(group, key)]):     # le curseur et son champ ensemble
            if w.value() != val:
                w.blockSignals(True)
                w.setValue(val)
                w.blockSignals(False)
        if group == 'rvb':                               # RVB : entiers, exacts
            get = {k: sp.value() for (g, k), sp in self.spins.items() if g == group}
            self.set_color(QColor(get['r'], get['g'], get['b']), 'rvb')
        elif group == 'tsv':                             # les autres valeurs gardées exactes : pas de dérive d'arrondi
            h, s, v = self.h, self.s, self.v
            if key == 'h':
                h = float(val)
            elif key == 's':
                s = val / 100.0
            else:
                v = val / 100.0
            self.set_hsv(h, s, v, 'tsv')
        else:
            c, m, y, k, _a = self.color().getCmykF()
            cmyk = dict(zip('cmyk', (c, m, y, k)))
            cmyk[key] = val / 100.0
            self.set_color(QColor.fromCmykF(cmyk['c'], cmyk['m'], cmyk['y'], cmyk['k']), 'cmjn')

    def _hex(self, text: str) -> None:
        t = text.strip()
        if not t.startswith('#'):
            t = '#' + t
        if len(t) in (4, 7) and QColor(t).isValid():
            self.set_color(QColor(t), 'hex')


def get_color(initial, parent=None, title: str = '') -> QColor | None:
    """La fenêtre du sélecteur ; rend la couleur choisie, ou None (Annuler). La fenêtre est détruite après."""
    dlg = ColorPicker(initial, parent, title)
    try:
        ok = dlg.exec() == QDialog.DialogCode.Accepted
        return dlg.color() if ok else None
    finally:
        dlg.deleteLater()
