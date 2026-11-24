"""Onglets de documents, en haut de la fenêtre comme dans un navigateur :
plusieurs dessins ouverts à la fois, chacun avec son historique
d'annulation, sa vue et ses parcours.

L'onglet affiché vit dans la fenêtre (`MainWindow.canvas.doc`, `path`,
`modified`, `_undo`, `_redo`, parcours du panneau FAO) ; les autres sont
gardés dans leur `DocTab`, échangés au changement d'onglet."""
from __future__ import annotations

import pathlib
import uuid
from dataclasses import dataclass, field

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QTabBar, QToolButton, QWidget

from ..i18n import tr


@dataclass
class DocTab:
    doc: object
    path: str | None = None
    modified: bool = False
    undo: list = field(default_factory=list)
    redo: list = field(default_factory=list)
    #: vue du plan de travail (échelle, origine x, origine y) ; None : tout le dessin
    view: tuple | None = None
    #: parcours calculés affichés (panneau FAO)
    toolpaths: list = field(default_factory=list)
    #: le reste de la vue de cet onglet (zooms précédents, calque seul, 2D / 3D,
    #: caméra 3D, affichages) ; None : pas encore affiché
    view_state: dict | None = None
    uid: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    #: tenu par l'assistant pendant sa demande (🔒 devant le titre)
    agent_lock: bool = field(default=False, compare=False, repr=False)

    def name(self) -> str:
        src = self.path or getattr(self.doc, 'source_path', None)
        return pathlib.Path(src).name if src else tr('Sans titre')

    def label(self) -> str:
        return ('🔒 ' if self.agent_lock else '') + self.name() + (' *' if self.modified else '')

    def pristine(self) -> bool:
        """Onglet vide jamais touché (réutilisé par Nouveau / Ouvrir)."""
        if self.modified or self.path or getattr(self.doc, 'source_path', None):
            return False
        return not any(L.items for L in getattr(self.doc, 'layers', []))


def same_file(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    try:
        return pathlib.Path(a).resolve() == pathlib.Path(b).resolve()
    except OSError:
        return str(a).lower() == str(b).lower()


class DocTabBar(QWidget):
    """Barre des onglets de documents : onglets fermables et déplaçables,
    « + » pour un nouveau dessin, clic du milieu pour fermer, double-clic
    à côté des onglets pour un nouveau dessin."""
    newRequested = Signal()
    closeRequested = Signal(int)
    tabSelected = Signal(int)
    tabMoved = Signal(int, int)
    menuRequested = Signal(int, object)          # onglet, position à l'écran (clic droit)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('docTabsRow')
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 0)
        lay.setSpacing(2)
        self.tabs = QTabBar(self)
        self.tabs.setObjectName('docTabs')
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setExpanding(False)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideMiddle)
        self.tabs.tabCloseRequested.connect(self.closeRequested.emit)
        self.tabs.currentChanged.connect(self._current)
        self.tabs.tabMoved.connect(self.tabMoved.emit)
        self.tabs.tabBarDoubleClicked.connect(lambda i: self.newRequested.emit() if i < 0 else None)
        self.tabs.installEventFilter(self)
        self.tabs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.customContextMenuRequested.connect(
            lambda pos: self.menuRequested.emit(self.tabs.tabAt(pos), self.tabs.mapToGlobal(pos)))
        lay.addWidget(self.tabs, 0, Qt.AlignmentFlag.AlignBottom)
        self.plus = QToolButton(self)
        self.plus.setObjectName('docTabsNew')
        self.plus.setText('+')
        self.plus.setAutoRaise(True)
        f = self.plus.font()
        f.setPointSizeF(f.pointSizeF() * 1.4)
        f.setBold(True)
        self.plus.setFont(f)
        self.plus.setFixedSize(28, 24)
        self.plus.setToolTip(tr('Nouveau dessin dans un nouvel onglet (Ctrl+N)'))
        self.plus.clicked.connect(self.newRequested.emit)
        lay.addWidget(self.plus, 0, Qt.AlignmentFlag.AlignBottom)
        lay.addStretch(1)
        self._quiet = False

    def _current(self, i: int) -> None:
        if not self._quiet and i >= 0:
            self.tabSelected.emit(i)

    def eventFilter(self, obj, ev) -> bool:                          # noqa: N802 (API Qt)
        from PySide6.QtCore import QEvent
        if obj is self.tabs and ev.type() == QEvent.Type.MouseButtonRelease \
                and ev.button() == Qt.MouseButton.MiddleButton:
            i = self.tabs.tabAt(ev.position().toPoint())
            if i >= 0:
                self.closeRequested.emit(i)
                return True
        if obj is self.tabs and ev.type() == QEvent.Type.MouseButtonDblClick \
                and self.tabs.tabAt(ev.position().toPoint()) < 0:
            self.newRequested.emit()
            return True
        return False

    def sync(self, tabs: list[DocTab], current: int) -> None:
        """Onglets refaits d'après la liste (titres, infobulles, courant)."""
        self._quiet = True
        try:
            while self.tabs.count() > len(tabs):
                self.tabs.removeTab(self.tabs.count() - 1)
            while self.tabs.count() < len(tabs):
                self.tabs.addTab('')
            for i, t in enumerate(tabs):
                self.tabs.setTabText(i, t.label())
                self.tabs.setTabToolTip(i, t.path or getattr(t.doc, 'source_path', None) or tr('Sans titre'))
            if 0 <= current < self.tabs.count():
                self.tabs.setCurrentIndex(current)
        finally:
            self._quiet = False
