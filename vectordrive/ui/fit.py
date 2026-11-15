"""Fenêtres à la largeur de leur contenu : à l'ouverture, une fenêtre
s'élargit (sans dépasser l'écran) tant qu'une de ses colonnes, listes ou
tableaux devrait défiler horizontalement — la place des volets voisins
d'un séparateur est prise d'abord. Les textes et les vues graphiques, qui
défilent d'eux-mêmes, ne comptent pas.

    from .fit import no_hscroll
    no_hscroll(self)          # dans le __init__ d'une fenêtre
    VScroll(panneau)          # volet qui ne défile que verticalement (dock)
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QEvent, QObject, QSize, Qt, QTimer
from PySide6.QtWidgets import (QAbstractScrollArea, QDialog, QScrollArea, QSplitter, QTableView, QTreeView,
                               QWidget)

#: marge gardée au bord de l'écran
SCREEN_MARGIN = 20
#: largeur gardée à un volet sans zone défilante
MIN_PANE = 80


def wanted(sa: QAbstractScrollArea) -> int | None:
    """Largeur du contenu d'une zone défilante (px) ; None pour les textes,
    vues graphiques et défilements voulus (propriété `vd_hscroll_ok`)."""
    if sa.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff or sa.property('vd_hscroll_ok'):
        return None
    if isinstance(sa, QScrollArea):
        w = sa.widget()
        if w is None or not sa.widgetResizable():
            return None
        return max(w.minimumSizeHint().width(), w.minimumSize().width())
    if isinstance(sa, QTableView):
        return sa.horizontalHeader().length()
    if isinstance(sa, QTreeView):
        if sa.header().isHidden() and sa.header().stretchLastSection():
            return None
        return sa.header().length()
    return None


def missing(sa: QAbstractScrollArea) -> int:
    """Largeur qui manque (px) à une zone défilante pour ne pas défiler."""
    w = wanted(sa)
    return 0 if w is None else max(0, w - sa.viewport().width())


def overflow(window: QWidget) -> int:
    """Largeur qui manque (px) à la zone défilante la plus à l'étroit."""
    return max((missing(sa) for sa in window.findChildren(QAbstractScrollArea) if sa.isVisibleTo(window)),
               default=0)


def _splitter_pane(sa: QWidget):
    """(séparateur, indice) du volet de QSplitter qui contient `sa`, ou None."""
    child, p = sa, sa.parentWidget()
    while p is not None:
        if isinstance(p, QSplitter):
            return p, p.indexOf(child)
        if p.isWindow():
            return None
        child, p = p, p.parentWidget()
    return None


def _room(pane: QWidget, size: int) -> int:
    """Place qu'un volet peut céder sans faire défiler ses propres zones."""
    areas = [sa for sa in ([pane] if isinstance(pane, QAbstractScrollArea) else []) +
             pane.findChildren(QAbstractScrollArea) if sa.isVisibleTo(pane.window()) and wanted(sa) is not None]
    if areas:
        return max(0, min(sa.viewport().width() - wanted(sa) for sa in areas))
    return max(0, size - max(pane.minimumSizeHint().width(), MIN_PANE))


def _rebalance(window: QWidget) -> bool:
    """Volets de séparateur trop étroits pour leur contenu : la place est
    prise aux autres volets, sans les faire défiler à leur tour. Rend True
    si quelque chose a changé."""
    changed = False
    for sa in window.findChildren(QAbstractScrollArea):
        if not sa.isVisibleTo(window):
            continue
        need = missing(sa)
        pane = _splitter_pane(sa) if need > 0 else None
        if pane is None or pane[1] < 0:
            continue
        split, i = pane
        sizes = split.sizes()
        before = list(sizes)
        others = sorted((j for j in range(len(sizes)) if j != i), key=lambda j: -sizes[j])
        for j in others:
            take = min(need, _room(split.widget(j), sizes[j]))
            if take > 0:
                sizes[j] -= take
                sizes[i] += take
                need -= take
            if need <= 0:
                break
        if sizes != before:
            split.setSizes(sizes)
            changed = True
    return changed


def widen(window: QWidget, passes: int = 8) -> int:
    """Élargit `window` jusqu'à ce que rien ne défile horizontalement, dans
    la limite de l'écran (la fenêtre est ramenée dedans) ; rend la largeur
    ajoutée."""
    scr = window.screen().availableGeometry() if window.screen() is not None else None
    added = 0
    for _ in range(passes):
        if window.layout() is not None:
            window.layout().activate()
        if _rebalance(window):                         # d'abord la place des volets voisins
            continue
        need = overflow(window)
        if need <= 0:
            break
        limit = scr.width() - 2 * SCREEN_MARGIN if scr is not None else 1 << 20
        new_w = min(window.width() + need + 2, limit)
        if new_w <= window.width():
            break
        added += new_w - window.width()
        window.resize(new_w, window.height())
    if added and scr is not None and window.isWindow():
        g = window.frameGeometry()
        x = min(max(g.x(), scr.left() + SCREEN_MARGIN // 2), scr.right() - g.width() - SCREEN_MARGIN // 2)
        if x != g.x():
            window.move(max(scr.left(), x), g.y())
    return added


class _Fitter(QObject):
    """À la première apparition de la fenêtre : `widen`, une seule fois."""

    def eventFilter(self, obj, ev) -> bool:                      # noqa: N802 (API Qt)
        if ev.type() == QEvent.Type.Show:
            obj.removeEventFilter(self)
            QTimer.singleShot(0, lambda o=obj: _safe_widen(o))
        return False


def _safe_widen(w: QWidget) -> None:
    try:
        if w.isVisible():
            w.setProperty('vd_widened', widen(w))
    except RuntimeError:                                        # fenêtre déjà détruite
        pass


def no_hscroll(window: QWidget) -> None:
    """Élargir `window` à sa première apparition (voir `widen`) ; une
    fenêtre de dialogue est aussi libérée une fois finie (`release`)."""
    f = _Fitter(window)
    window.installEventFilter(f)
    window._vd_fitter = f                                       # gardé vivant avec la fenêtre
    if isinstance(window, QDialog):
        release(window)


def release(dialog: QDialog) -> None:
    """Une fenêtre de dialogue a la fenêtre principale pour parent : fermée,
    elle restait en vie avec tous ses widgets (un formulaire FAO en vaut
    260, la fenêtre des options 400) — une journée d'atelier en accumule des
    milliers, qui ralentissent chaque changement de thème ou de disposition.
    Détruite (deleteLater) une fois finie, quand le code qui a appelé son
    `exec()` a rendu la main : il peut lire ses champs aussi longtemps qu'il
    tourne, même après une autre boîte (voir `flush`). Une fenêtre réemployée
    (montrée plusieurs fois) le refuse : attribut de classe `vd_keep = True`."""
    if getattr(dialog, 'vd_keep', False) or dialog.property('vd_keep') or getattr(dialog, '_vd_released', False):
        return                                                  # (posé deux fois : le code appelant serait le nôtre)
    dialog._vd_released = True
    run = dialog.exec

    def exec_(*args):
        dialog._vd_caller = sys._getframe(1)                    # le code qui lira ses champs au retour
        return run(*args)
    dialog.exec = exec_
    dialog.finished.connect(lambda _result=0, d=dialog: _retire(d))


#: fenêtres de dialogue finies, pas encore détruites : (fenêtre, code qui a appelé son exec() ou None)
_DONE: list = []
#: un passage de `flush` est déjà demandé
_ARMED = [False]
#: délai avant de revoir les fenêtres dont le code appelant tourne encore (ms) ; après `PATIENT` passages sans
#: rien libérer (un code appelant qui ne rend jamais la main : le programme lui-même), dix fois plus long
RETRY_MS = 300
PATIENT = 40
_IDLE = [0]


def _retire(dialog: QDialog) -> None:
    _DONE.append((dialog, getattr(dialog, '_vd_caller', None)))
    _arm(0)


def _arm(ms: int) -> None:
    if not _ARMED[0]:
        _ARMED[0] = True
        QTimer.singleShot(ms, _tick)


def _tick() -> None:
    _ARMED[0] = False
    flush()


def _running(frame) -> bool:
    """Le code de `frame` est-il encore en cours (sur la pile d'appels) ?"""
    f = sys._getframe()
    while f is not None:
        if f is frame:
            return True
        f = f.f_back
    return False


def flush() -> int:
    """Détruit les fenêtres de dialogue finies dont le code appelant a rendu la main ; rend le nombre de celles qui
    attendent encore. Avant, la destruction suivait la fermeture à la première boucle d'événements venue — celle
    d'une boîte de fichier de Windows, d'un message ou d'une progression ouverts ensuite par le même code, qui
    lisait alors les champs d'une fenêtre détruite (« Internal C++ object already deleted », muet dans la version
    installée : la commande semblait ne rien faire)."""
    later = []
    for dialog, caller in _DONE:
        if caller is not None and _running(caller):
            later.append((dialog, caller))
            continue
        try:
            dialog.deleteLater()
        except RuntimeError:                                    # déjà détruite avec sa fenêtre parente
            pass
    _IDLE[0] = _IDLE[0] + 1 if len(later) == len(_DONE) else 0
    _DONE[:] = later
    if later:
        _arm(RETRY_MS * (10 if _IDLE[0] > PATIENT else 1))
    return len(later)


class VScroll(QScrollArea):
    """Volet qui défile verticalement seulement : sa hauteur minimale reste
    petite (la fenêtre principale tient dans l'écran même quand le volet
    est haut), sa largeur minimale est celle de son contenu (rien n'y est
    coupé, rien ne défile horizontalement). Le contenu prend toute la
    hauteur visible, ou sa hauteur minimale quand elle est plus grande :
    seul ce qui dépasse défile."""

    def __init__(self, widget: QWidget, min_height: int = 160, parent: QWidget | None = None):
        super().__init__(parent)
        self.min_height = min_height
        self.setWidgetResizable(False)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(widget)
        widget.installEventFilter(self)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.fit)

    def needed(self, width: int) -> int:
        """Hauteur minimale du contenu à la largeur `width` (textes à la
        ligne compris)."""
        w = self.widget()
        h = max(w.minimumSizeHint().height(), w.minimumHeight())
        lay = w.layout()
        if lay is not None and lay.hasHeightForWidth():
            h = max(h, lay.totalMinimumHeightForWidth(width))
        return h

    def fit(self) -> None:
        """Contenu à la largeur visible ; hauteur visible ou minimale."""
        w = self.widget()
        if w is None:
            return
        width = self.viewport().width()
        size = QSize(width, max(self.viewport().height(), self.needed(width)))
        if w.size() != size:
            w.resize(size)

    def eventFilter(self, obj, ev) -> bool:                      # noqa: N802 (API Qt)
        if obj is self.widget() and ev.type() == QEvent.Type.LayoutRequest:
            self.updateGeometry()                               # sa largeur réclamée suit le contenu
            self._timer.start(0)                                # après la mise en page du contenu
        return super().eventFilter(obj, ev)

    def viewportEvent(self, ev) -> bool:                         # noqa: N802 (API Qt)
        if ev.type() == QEvent.Type.Resize:
            self.fit()
        return super().viewportEvent(ev)

    def minimumSizeHint(self) -> QSize:                          # noqa: N802 (API Qt)
        w = self.widget()
        if w is None:
            return super().minimumSizeHint()
        width = max(w.minimumSizeHint().width(), w.minimumWidth()) + self.verticalScrollBar().sizeHint().width()
        return QSize(width, min(self.min_height, max(w.minimumSizeHint().height(), 1)))

    def sizeHint(self) -> QSize:                                 # noqa: N802 (API Qt)
        w = self.widget()
        if w is None:
            return super().sizeHint()
        hint = w.sizeHint()
        return QSize(max(hint.width(), self.minimumSizeHint().width()), hint.height())
