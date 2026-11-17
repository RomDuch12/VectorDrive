"""Panneau « Couleur » (demande du 15/11, 20 h 02 : « fenetre apposable en colonne : accrochage […] couleur
Défaire/refaire (gauche par défaut) » ; réponse du 17/11 à la question 46 : « la palette ») : la palette des couleurs
(les outils) du dessin. Un clic sur une couleur colore les objets sélectionnés (un pas d'annulation) et en fait la
couleur courante, celle que prennent les objets dessinés ensuite ; sans sélection, il choisit seulement la couleur
courante, sans rien changer au dessin. Choisir un autre calque reprend sa couleur.
Chaque ligne dit combien d'objets portent cette couleur ; la couleur courante est en gras, celles de la sélection
cochées. Clic droit : changer la couleur de l'outil.

Un panneau de colonne comme les autres (à gauche d'office, masqué tant qu'on ne le demande pas). Il ne prend pas le
clavier : les raccourcis restent au dessin."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QMenu, QVBoxLayout, QWidget

from ..i18n import tr


def _leaves_of(items) -> list:
    from .canvas import _leaves
    return list(_leaves(items))


class ColorPanel(QWidget):
    """`win` : la fenêtre principale (son dessin, sa sélection, `push_undo`)."""

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.signature = None
        self._later = QTimer(self)                       # les rafraîchissements d'un même geste réunis en un
        self._later.setSingleShot(True)
        self._later.setInterval(0)
        self._later.timeout.connect(lambda: self.sync(force=False, now=True))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        self.list = QListWidget()
        self.list.setFocusPolicy(Qt.FocusPolicy.NoFocus)             # le clavier reste au dessin
        self.list.setToolTip(tr('Un clic : les objets sélectionnés prennent cette couleur, qui devient la couleur '
                                'courante (celle des objets dessinés ensuite) ; double clic ou clic droit : '
                                'changer la couleur'))
        self.list.itemClicked.connect(self._clicked)
        #: demande du 17/11 soir : « double clic sur la couleur ouvre une fenetre de selection beaucoup plus avancee ».
        #: Le simple clic attend la durée d'un double clic : un double clic ne recolore pas la sélection (et la liste
        #: n'est pas refaite entre les deux clics, ce qui empêchait Qt de voir le double clic).
        self._click_index = None
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._click_now)
        self._dbl_at = None
        self.list.itemDoubleClicked.connect(self._double_clicked)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        lay.addWidget(self.list, 1)
        self.note = QLabel()
        self.note.setWordWrap(True)
        lay.addWidget(self.note)

    # --- l'état
    def doc(self):
        return self.win.canvas.doc

    def current(self) -> int:
        return int(getattr(self.win.canvas, 'current_tool_index', 0) or 0)

    def counts(self) -> dict:
        """{outil : nombre d'objets du dessin de cette couleur}."""
        out: dict = {}
        for it in self.doc().iter_leaves():
            t = getattr(it, 'tool', None)
            if t is not None:
                out[t] = out.get(t, 0) + 1
        return out

    def chosen(self) -> set:
        """Les couleurs des objets sélectionnés."""
        return {x.tool for x in _leaves_of(self.win.canvas.selection) if getattr(x, 'tool', None) is not None}

    def sync(self, force: bool = False, now: bool = False) -> None:
        """La palette à jour, refaite seulement si ce qu'elle montre a changé (et qu'elle est à l'écran) ; sans
        `force` ni `now`, un peu après (les appels d'un même geste n'en font qu'un)."""
        if not force and not self.isVisible():
            return
        if not force and not now:
            self._later.start()
            return
        self._later.stop()
        doc = self.doc()
        counts = self.counts()
        sig = ([(t.index, t.color, t.name) for t in doc.tools], counts, self.current(), sorted(self.chosen()), id(doc))
        if not force and sig == self.signature:
            return
        self.signature = sig
        from .layers import swatch
        chosen, cur = set(sig[3]), self.current()
        self.list.clear()
        for t in doc.tools:
            n = counts.get(t.index, 0)
            text = f'{t.index} — {t.name or tr("Outil {0}").format(t.index)}'   # numérotés comme les calques
            if n:
                text += f'   ({n})'
            if t.index in chosen:
                text = '✓ ' + text
            it = QListWidgetItem(swatch(t.color, 18), text)
            it.setData(Qt.ItemDataRole.UserRole, t.index)
            if t.index == cur:
                f = it.font()
                f.setBold(True)
                it.setFont(f)
            it.setToolTip(t.color)
            self.list.addItem(it)
        sel = len(self.win.canvas.selection)
        self.note.setText(tr('{0} objet(s) sélectionné(s) : un clic les colore').format(sel) if sel else
                          tr('Rien de sélectionné : un clic choisit la couleur courante'))

    def showEvent(self, ev):                             # noqa: N802 (API Qt)
        super().showEvent(ev)
        self.sync(force=True)

    # --- les gestes
    def _clicked(self, item) -> None:
        from PySide6.QtWidgets import QApplication
        gap = QApplication.doubleClickInterval()
        if self._dbl_at is not None and self._dbl_at.elapsed() < gap:     # le relâché du double clic
            return
        self._click_index = int(item.data(Qt.ItemDataRole.UserRole))
        self._click_timer.start(gap)

    def _click_now(self) -> None:
        index, self._click_index = self._click_index, None
        if index is not None:
            self.apply(index)

    def _double_clicked(self, item) -> None:
        from PySide6.QtCore import QElapsedTimer
        self._click_timer.stop()                         # le simple clic qui précède n'a pas lieu
        self._click_index = None
        self._dbl_at = QElapsedTimer()
        self._dbl_at.start()
        self.pick_color(int(item.data(Qt.ItemDataRole.UserRole)))
        self._dbl_at.restart()

    def apply(self, index: int) -> int:
        """La couleur `index` : donnée aux objets sélectionnés (un pas d'annulation), et couleur courante — celle des
        objets dessinés ensuite, gardée tant qu'on ne choisit pas un autre calque. Sans sélection, le dessin ne change
        pas. Rend le nombre d'objets recolorés."""
        win, doc = self.win, self.doc()
        if not any(t.index == index for t in doc.tools):
            return 0
        win.canvas.current_tool_index = index
        sel = list(win.canvas.selection)
        leaves = [x for x in _leaves_of(sel) if getattr(x, 'tool', None) is not None and x.tool != index]
        tops = [t for t in sel if getattr(t, 'tool', None) is not None and t.tool != index]
        if not leaves and not tops:
            self.sync(force=True)
            return 0
        if hasattr(win, 'finish_typing'):               # une saisie en cours : son pas d'annulation d'abord
            win.finish_typing()
        win.push_undo(tr('Couleur'))
        for t in tops:
            t.tool = index
        for x in leaves:
            x.tool = index
        win.canvas.invalidate()
        win._on_selection()
        win._on_doc_changed()
        win.canvas.current_tool_index = index           # (un rafraîchissement des calques l'aurait remise)
        self.sync(force=True)
        return len(leaves)

    def _menu(self, pos) -> None:
        item = self.list.itemAt(pos)
        if item is None:
            return
        index = int(item.data(Qt.ItemDataRole.UserRole))
        m = QMenu(self)
        m.addAction(tr('Changer la couleur…'), lambda: self.pick_color(index))
        m.exec(self.list.mapToGlobal(pos))

    def pick_color(self, index: int) -> bool:
        tool = next((t for t in self.doc().tools if t.index == index), None)
        if tool is None:
            return False
        from .color_picker import get_color
        c = get_color(tool.color, self, tr('Couleur de l’outil {0}').format(index))
        return c is not None and self.set_tool_color(index, c.name())

    def set_tool_color(self, index: int, color: str) -> bool:
        """La couleur de l'outil `index` changée (un pas d'annulation) ; rend vrai si elle a changé."""
        tool = next((t for t in self.doc().tools if t.index == index), None)
        if tool is None or str(tool.color).lower() == str(color).lower():
            return False
        self.win.push_undo(tr('Couleur de l’outil'))
        tool.color = color
        self.win.canvas.invalidate()
        self.win._on_doc_changed()
        self.sync(force=True)
        return True
