"""Un panneau dans sa propre fenêtre : réduire, agrandir, fermer, plein écran — et retour dans son panneau ancrable.

Un panneau ancrable détaché (QDockWidget flottant) n'a ni bouton « réduire » ni bouton « agrandir », et ne passe pas
en plein écran. `DockAsWindow` déplace le contenu d'un panneau ancrable dans une vraie fenêtre (`PanelWindow`), et le
rend à son panneau quand la fenêtre se ferme ou qu'on demande « Ancrer ». En plein écran, où la fenêtre n'a plus de
barre de titre, sa barre montre les trois boutons de toute fenêtre : réduire, agrandir (quitter le plein écran),
fermer. Sert aux panneaux des plugins qui demandent de la place.
"""
from __future__ import annotations

from PySide6.QtCore import QByteArray, QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from ..i18n import tr


class PanelWindow(QWidget):
    """Fenêtre d'un panneau : son contenu sous une barre (titre et boutons en plein écran)."""
    #: la fenêtre se ferme (son contenu doit retourner à son panneau)
    closing = Signal()
    #: « Ancrer » demandé
    dock_requested = Signal()

    def __init__(self, title: str = ''):
        super().__init__(None, Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)   # la fenêtre principale fermée, l'application finit
        self.setWindowTitle(title)
        self._content = None
        self._before_full = None                         # état de la fenêtre avant le plein écran
        self.vd_own_close = True                         # en plein écran, sa barre a déjà son « ✕ » (ui.fullclose)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.bar = QWidget()
        self.bar.setObjectName('panel_window_bar')
        row = QHBoxLayout(self.bar)
        row.setContentsMargins(6, 2, 2, 2)
        row.setSpacing(2)
        self.title = QLabel(title)
        row.addWidget(self.title)
        row.addStretch(1)
        self.buttons: dict = {}
        for key, text, tip, slot in (
                ('dock', '⚓', tr('Ancrer : remettre ce panneau dans la fenêtre principale'), self.dock_requested.emit),
                ('full', '⛶', tr('Plein écran (F11) ; Échap pour en sortir'), self.toggle_full_screen),
                ('min', '—', tr('Réduire'), self.showMinimized),
                ('max', '▢', tr('Agrandir, ou quitter le plein écran'), self.toggle_maximized),
                ('close', '✕', tr('Fermer'), self.close)):
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.setAutoRaise(True)
            b.setFixedSize(34, 24)
            b.clicked.connect(lambda _=False, s=slot: s())
            row.addWidget(b)
            self.buttons[key] = b
        lay.addWidget(self.bar)
        self.host = QVBoxLayout()
        self.host.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(self.host, 1)
        from PySide6.QtGui import QKeySequence, QShortcut
        sc = QShortcut(QKeySequence('F11'), self)        # où que soit le curseur dans la fenêtre
        sc.setContext(Qt.ShortcutContext.WindowShortcut)
        sc.activated.connect(self.toggle_full_screen)
        self._sync_bar()

    # --- contenu
    def set_content(self, widget) -> None:
        self._content = widget
        self.host.addWidget(widget)
        widget.show()

    def take_content(self):
        """Le contenu retiré de la fenêtre (à remettre dans son panneau) ; None si elle est vide."""
        w, self._content = self._content, None
        if w is not None:
            self.host.removeWidget(w)
            w.setParent(None)
        return w

    def content(self):
        return self._content

    # --- états
    def is_full_screen(self) -> bool:
        return bool(self.windowState() & Qt.WindowState.WindowFullScreen)

    def set_full_screen(self, on: bool) -> bool:
        """Plein écran, ou retour à la fenêtre d'avant (agrandie si elle l'était) ; rend l'état obtenu."""
        if on and not self.is_full_screen():
            self._before_full = bool(self.windowState() & Qt.WindowState.WindowMaximized)
            self.setWindowState((self.windowState() & ~Qt.WindowState.WindowMinimized) | Qt.WindowState.WindowFullScreen)
        elif not on and self.is_full_screen():
            st = self.windowState() & ~Qt.WindowState.WindowFullScreen
            if self._before_full:
                st |= Qt.WindowState.WindowMaximized
            self.setWindowState(st)
        self._sync_bar()
        return self.is_full_screen()

    def toggle_full_screen(self) -> bool:
        return self.set_full_screen(not self.is_full_screen())

    def toggle_maximized(self) -> str:
        """Bouton « agrandir » : hors du plein écran s'il y est (fenêtre agrandie), sinon agrandie ou rendue à sa
        taille ; rend 'maximized' ou 'normal'."""
        if self.is_full_screen():
            self._before_full = True
            self.set_full_screen(False)
            return 'maximized'
        if self.windowState() & Qt.WindowState.WindowMaximized:
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMaximized)
            return 'normal'
        self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)
        return 'maximized'

    def _sync_bar(self) -> None:
        """En plein écran : titre et boutons de fenêtre dans la barre ; sinon la barre de titre du système suffit."""
        full = self.is_full_screen()
        self.title.setVisible(full)
        for key in ('min', 'max', 'close'):
            self.buttons[key].setVisible(full)

    # --- événements
    def changeEvent(self, ev) -> None:                    # noqa: N802 (API Qt)
        if ev.type() == QEvent.Type.WindowStateChange:
            self._sync_bar()
        super().changeEvent(ev)

    def keyPressEvent(self, ev) -> None:                  # noqa: N802 (API Qt)
        if ev.key() == Qt.Key.Key_Escape and self.is_full_screen():
            self.set_full_screen(False)
            ev.accept()
            return
        super().keyPressEvent(ev)

    def closeEvent(self, ev) -> None:                     # noqa: N802 (API Qt)
        self.closing.emit()
        super().closeEvent(ev)


class DockAsWindow(QObject):
    """Le contenu d'un panneau ancrable, au choix dans son panneau ou dans une fenêtre (`PanelWindow`).

    `settings` et `key` : sont retenus sous `key` la place de la fenêtre (`/geometrie`), son plein écran
    (`/plein_ecran`) et le choix de la fenêtre plutôt que du panneau (`/en_fenetre`, voir `wants_window`). Fermer la
    fenêtre ferme le panneau ; « Ancrer » le remet dans la fenêtre principale. La fenêtre principale cachée (fermée),
    le contenu retourne à son panneau."""

    def __init__(self, dock, main_window, settings=None, key: str = ''):
        super().__init__(dock)
        self.dock = dock
        self.main = main_window
        self.settings = settings
        self.key = key
        self.window = None
        if main_window is not None:
            main_window.installEventFilter(self)

    def in_window(self) -> bool:
        return self.window is not None and self.window.content() is not None

    def wants_window(self) -> bool:
        """Le panneau était-il dans sa fenêtre la dernière fois (à rouvrir de même) ?"""
        return self._value('en_fenetre', 'false') in (True, 'true')

    def is_open(self) -> bool:
        """Le panneau est-il montré, dans sa fenêtre ou ancré ?"""
        return (self.in_window() and self.window.isVisible()) or (not self.in_window() and self.dock.isVisible())

    def open(self, show: bool = True) -> bool:
        """Le panneau montré là où il était la dernière fois : sa fenêtre, ou son panneau ancrable ; rend vrai s'il
        est dans sa fenêtre."""
        if self.in_window() or self.wants_window():
            self.to_window(show=show)
        elif show:
            self.dock.show()
            self.dock.raise_()
        return self.in_window()

    def content(self):
        """Le contenu, où qu'il soit."""
        return self.window.content() if self.in_window() else self.dock.widget()

    def to_window(self, full_screen: bool | None = None, show: bool = True):
        """Le contenu du panneau dans sa fenêtre (créée au premier appel) : à sa place retenue, en plein écran si
        demandé (None : comme la dernière fois). Rend la fenêtre."""
        if self.window is None:
            self.window = PanelWindow(str(self.dock.property('vd_titre') or self.dock.windowTitle()))
            self.window.setObjectName((self.dock.objectName() or 'panneau') + '_fenetre')
            self.window.closing.connect(lambda: self.to_dock(show=False, keep_choice=True))
            self.window.dock_requested.connect(lambda: self.to_dock())
        w = self.window
        if not self.in_window():
            content = self.dock.widget()
            if content is None:
                return w
            geo = self.dock.frameGeometry() if self.dock.isFloating() else None
            self.dock.hide()
            w.set_content(content)
            raw = str(self._value('geometrie', '') or '')
            if not (raw and w.restoreGeometry(QByteArray.fromBase64(raw.encode('ascii')))):
                if geo is not None and geo.width() > 200 and geo.height() > 200:
                    w.setGeometry(geo)
                else:
                    w.resize(1150, 700)
        if full_screen is None:
            full_screen = self._value('plein_ecran', 'false') in (True, 'true')
        self._set('en_fenetre', True)
        if show:
            w.show()
        w.set_full_screen(bool(full_screen))
        if show:
            w.raise_()
            w.activateWindow()
        return w

    def to_dock(self, show: bool = True, keep_choice: bool = False) -> None:
        """Le contenu rendu à son panneau ancrable — montré (« Ancrer ») ou non (fenêtre fermée : le panneau est
        fermé, et rouvrira dans sa fenêtre si `keep_choice`). La place de la fenêtre est retenue."""
        if not self.in_window():
            return
        w = self.window
        self._remember()
        if not keep_choice:
            self._set('en_fenetre', False)
        content = w.take_content()
        self.dock.setWidget(content)
        w.hide()
        if show:
            self.dock.show()
            self.dock.raise_()
        else:
            self.dock.hide()

    def toggle(self):
        """De l'un à l'autre ; rend vrai si le contenu est maintenant dans sa fenêtre."""
        if self.in_window():
            self.to_dock()
        else:
            self.to_window(full_screen=False)
        return self.in_window()

    def _value(self, name: str, default):
        if self.settings is None or not self.key:
            return default
        return self.settings.value(f'{self.key}/{name}', default)

    def _set(self, name: str, value) -> None:
        if self.settings is not None and self.key:
            self.settings.setValue(f'{self.key}/{name}', value)

    def _remember(self) -> None:
        w = self.window
        if w is None:
            return
        full = w.is_full_screen()
        self._set('plein_ecran', full)
        if not full and w.isVisible() and not w.isMinimized():
            self._set('geometrie', bytes(w.saveGeometry().toBase64()).decode('ascii'))

    def eventFilter(self, obj, ev) -> bool:               # noqa: N802 (API Qt)
        # la fenêtre principale fermée : la fenêtre du panneau ne lui survit pas. Pas pour un simple passage : F12
        # la cache et la remontre en changeant son cadre, Windows la cache quand elle est réduite
        if obj is self.main and ev.type() == QEvent.Type.Hide and self.in_window() and not ev.spontaneous():
            if getattr(self.main, '_closing', False):
                self.to_dock(show=False, keep_choice=True)
            else:
                QTimer.singleShot(0, self._main_hidden)
        return False

    def _main_hidden(self) -> None:
        """Après une fenêtre principale cachée : refermée pour de bon (ni remontrée, ni réduite) ?"""
        try:
            gone = self.main is not None and not self.main.isVisible() and not self.main.isMinimized()
        except RuntimeError:                              # déjà détruite
            gone = True
        if gone and self.in_window():
            self.to_dock(show=False, keep_choice=True)
