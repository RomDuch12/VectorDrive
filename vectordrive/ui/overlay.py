"""Fenêtres FAO en plein écran translucide : la fenêtre (opérations et
parcours, création de parcours) couvre le plan de travail, son opacité se
règle pour voir le dessin dessous, et la molette continue de zoomer le
dessin — sauf au-dessus d'une liste, d'une liste déroulante ou d'un champ
numérique, qui gardent leur défilement (Ctrl + molette : toujours le dessin)."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (QAbstractItemView, QAbstractSpinBox, QComboBox, QHBoxLayout, QLabel, QPlainTextEdit,
                               QSlider, QTextEdit, QToolButton, QWidget)

from ..i18n import tr

#: opacité la plus faible permise (la fenêtre reste lisible)
MIN_OPACITY = 0.25


def _keeps_wheel(w) -> bool:
    """Le widget (ou un parent proche) défile lui-même à la molette."""
    while w is not None:
        if isinstance(w, (QAbstractItemView, QComboBox, QAbstractSpinBox, QSlider, QPlainTextEdit, QTextEdit)):
            return True                                  # (un texte long — le programme machine — défile aussi)
        if w.isWindow():
            return False
        w = w.parentWidget()
    return False


class Overlay(QObject):
    """Plein écran translucide pour un QDockWidget de la fenêtre principale."""

    def __init__(self, win, dock, key: str):
        super().__init__(dock)
        self.win, self.dock, self.key = win, dock, key
        self.active = False
        self._bar = None

    # --- réglages -------------------------------------------------------------------
    def opacity(self) -> float:
        try:
            v = float(self.win.settings.value(f'fenetres/{self.key}/opacite', 0.75))
        except (TypeError, ValueError):
            v = 0.75
        return max(MIN_OPACITY, min(1.0, v))

    def set_opacity(self, v: float) -> None:
        v = max(MIN_OPACITY, min(1.0, float(v)))
        self.win.settings.setValue(f'fenetres/{self.key}/opacite', v)
        if self.active:
            self.dock.setWindowOpacity(v)
        if self._bar is not None:
            self._bar.slider.blockSignals(True)
            self._bar.slider.setValue(int(round(v * 100)))
            self._bar.slider.blockSignals(False)

    # --- plein écran ------------------------------------------------------------------
    def target_rect(self):
        """Le plan de travail (zone centrale) en coordonnées de l'écran."""
        st = self.win.stage
        tl = st.mapToGlobal(st.rect().topLeft())
        from PySide6.QtCore import QRect
        return QRect(tl, st.size())

    def set_active(self, on: bool) -> bool:
        on = bool(on)
        d = self.dock
        if on:
            if not self.active:                          # où il était : détaché (sa place, sa taille) ou ancré
                self._was_floating = d.isFloating() and not d.isHidden()
                self._was_geometry = d.geometry()
            d.setVisible(True)
            d.setFloating(True)
            self._bar = _Bar(self)
            d.setTitleBarWidget(self._bar)
            lay = self.win.layout()
            if lay is not None:                          # le plan de travail s'élargit sans la fenêtre : on le mesure après
                lay.activate()
            d.setGeometry(self.target_rect())
            d.setWindowOpacity(self.opacity())
            self._watch(d, True)
            self.win.stage.installEventFilter(self)      # le plan de travail change : la fenêtre suit
            d.raise_()
        else:
            self.win.stage.removeEventFilter(self)
            self._watch(d, False)
            d.setWindowOpacity(1.0)
            bar = getattr(d, '_vd_bar', None)            # la barre de titre commune des panneaux (`ui.columns`)
            d.setTitleBarWidget(bar)
            if bar is not None:
                bar.show()
            self._bar = None
            if self.active:
                if getattr(self, '_was_floating', False):
                    d.setGeometry(self._was_geometry)    # il était détaché : il le reste, à sa place
                else:
                    d.setFloating(False)
        self.active = on
        self.win.settings.setValue(f'fenetres/{self.key}/plein', on)
        return on

    def toggle(self) -> bool:
        return self.set_active(not self.active)

    def _watch(self, w, on: bool) -> None:
        for x in [w] + w.findChildren(QWidget):
            if on:
                x.installEventFilter(self)
            else:
                x.removeEventFilter(self)

    def eventFilter(self, obj, ev) -> bool:                  # noqa: N802 (API Qt)
        if ev.type() == QEvent.Type.ChildAdded and self.active:
            ch = ev.child()
            if isinstance(ch, QWidget):
                ch.installEventFilter(self)
        if obj is self.win.stage and ev.type() in (QEvent.Type.Resize, QEvent.Type.Move) and self.active:
            self.dock.setGeometry(self.target_rect())
            return False
        if ev.type() != QEvent.Type.Wheel or not self.active:
            return False
        ctrl = bool(ev.modifiers() & Qt.KeyboardModifier.ControlModifier)
        if not ctrl and _keeps_wheel(obj):
            return False
        return self.forward(ev)

    def forward(self, ev) -> bool:
        """La molette passe au plan de travail, au même endroit de l'écran."""
        c = self.win.canvas
        pos = c.mapFromGlobal(ev.globalPosition().toPoint())
        we = QWheelEvent(QPointF(pos), ev.globalPosition(), ev.pixelDelta(), ev.angleDelta(), ev.buttons(),
                         ev.modifiers() & ~Qt.KeyboardModifier.ControlModifier, ev.phase(), ev.inverted())
        from PySide6.QtWidgets import QApplication
        QApplication.sendEvent(c, we)
        return True


class _Bar(QWidget):
    """Barre de titre en plein écran : titre, opacité, retour, fermer."""

    def __init__(self, ov: Overlay):
        super().__init__()
        self.ov = ov
        self.setObjectName('overlayBar')
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 2, 4, 2)
        lay.addWidget(QLabel(ov.dock.windowTitle()))
        lay.addStretch(1)
        lay.addWidget(QLabel(tr('Opacité')))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(int(MIN_OPACITY * 100), 100)
        self.slider.setValue(int(round(ov.opacity() * 100)))
        self.slider.setFixedWidth(160)
        self.slider.setToolTip(tr('Opacité de la fenêtre : baissez-la pour voir le dessin dessous'))
        self.slider.valueChanged.connect(lambda v: ov.set_opacity(v / 100.0))
        lay.addWidget(self.slider)
        back = QToolButton()
        back.setText('⧉')
        back.setToolTip(tr('Quitter le plein écran'))
        back.clicked.connect(lambda: ov.set_active(False))
        lay.addWidget(back)
        close = QToolButton()
        close.setText('✕')
        close.setToolTip(tr('Fermer la fenêtre'))
        close.clicked.connect(lambda: (ov.set_active(False), ov.dock.close()))
        lay.addWidget(close)
