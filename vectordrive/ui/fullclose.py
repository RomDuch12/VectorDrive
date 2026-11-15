"""Toute fenêtre en plein écran a son bouton de fermeture (demande du 15/11) : un « ✕ » en haut à droite, posé dès
que la fenêtre passe en plein écran (elle n'a plus de barre de titre), caché quand elle en sort. Un filtre
d'événements de l'application s'en charge : aucune fenêtre n'a à s'en occuper.

Le ✕ ne couvre jamais un bouton ou un champ : il prend la première place libre de la moitié droite de la bande du
haut ; sans place libre, la mise en page de la fenêtre se resserre à droite, de sa largeur, le temps du plein écran.

La fenêtre principale n'est pas concernée : son plein écran (F12) est une fenêtre sans cadre, avec ses propres boutons
dans le ruban. Une fenêtre qui a déjà son bouton peut s'en dispenser : `fenetre.vd_own_close = True`."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, Qt, QTimer
from PySide6.QtWidgets import (QAbstractButton, QAbstractSlider, QAbstractSpinBox, QApplication, QComboBox, QDialog,
                               QLineEdit, QTabBar, QToolButton, QWidget)

from ..i18n import tr

#: nom du bouton (objectName), pour le retrouver
NAME = 'vd_fullscreen_close'
#: nom du filtre posé sur l'application (une seule fois)
WATCH = 'vd_fullscreen_close_watch'
#: propriété de la fenêtre : les marges de sa mise en page avant qu'elle se resserre pour le ✕ (rendues en sortant)
KEPT = 'vd_fullscreen_close_margins'
#: taille du bouton et marge au coin de la fenêtre (px)
SIZE, MARGIN = 30, 6
#: ce que le ✕ ne doit pas couvrir (un bouton ⛶ en haut à droite, un champ…)
BUSY = (QAbstractButton, QComboBox, QLineEdit, QAbstractSpinBox, QAbstractSlider, QTabBar)

STYLE = (f'QToolButton#{NAME} {{ font-size: 17px; border: none; border-radius: {SIZE // 2}px; '
         'background: rgba(128, 128, 128, 70); }} '
         f'QToolButton#{NAME}:hover {{ background: #e03131; color: white; }}')


def button_of(w: QWidget) -> QToolButton | None:
    """Le ✕ de la fenêtre `w` (None : jamais posé)."""
    return w.findChild(QToolButton, NAME, Qt.FindChildOption.FindDirectChildrenOnly)


def _close(w: QWidget) -> None:
    if isinstance(w, QDialog):
        w.reject()                                       # comme Échap : rien n'est validé
    else:
        w.close()


def _busy(w: QWidget, b: QWidget) -> list:
    """Les rectangles (dans la fenêtre) des boutons, champs, listes déroulantes… de la bande du haut, que le ✕ ne doit
    pas couvrir."""
    band = QRect(0, 0, w.width(), MARGIN + SIZE + 1)
    out = []
    for c in w.findChildren(QWidget):
        if c is b or not isinstance(c, BUSY) or c.window() is not w or not c.isVisibleTo(w):
            continue                                     # (une fenêtre fille n'est pas dans celle-ci)
        r = QRect(c.mapTo(w, QPoint(0, 0)), c.size())
        if r.intersects(band):
            out.append(r)
    return out


def _reserve(w: QWidget) -> bool:
    """Pas de place libre en haut : la mise en page de la fenêtre se resserre à droite, de la largeur du ✕ (ses
    marges d'avant gardées dans `KEPT`). Rend vrai si la place est faite."""
    lay = w.layout()
    if lay is None:
        return False
    if w.property(KEPT) is None:
        m = lay.contentsMargins()
        w.setProperty(KEPT, [m.left(), m.top(), m.right(), m.bottom()])
        lay.setContentsMargins(m.left(), m.top(), m.right() + SIZE + MARGIN, m.bottom())
    return True


def _release(w: QWidget) -> None:
    """Hors du plein écran : la mise en page reprend ses marges d'avant."""
    kept = w.property(KEPT)
    if kept is None:
        return
    lay = w.layout()
    if lay is not None:
        lay.setContentsMargins(*[int(v) for v in kept])
    w.setProperty(KEPT, None)


def place(w: QWidget) -> None:
    """Le ✕ en haut à droite de la fenêtre, au-dessus de son contenu ; s'il y couvrirait un bouton (⛶…), un peu plus
    à gauche, à la première place libre de la moitié droite ; sans place libre, tout à droite, la mise en page
    resserrée d'autant (`_reserve`)."""
    b = button_of(w)
    if b is None:
        return
    right = max(0, w.width() - SIZE - MARGIN)
    x = right
    if w.property(KEPT) is None:                         # place pas encore faite à droite
        busy = _busy(w, b)
        while x > w.width() // 2 and any(QRect(x, MARGIN, SIZE, SIZE).intersects(r) for r in busy):
            x -= SIZE // 3
        if x <= w.width() // 2:
            x = right
            _reserve(w)
    b.move(x, MARGIN)
    b.raise_()


def place_later(w: QWidget) -> None:
    """Le ✕ placé une fois la mise en page de la fenêtre faite (le filtre voit les événements avant elle)."""
    b = button_of(w)
    if b is not None:
        QTimer.singleShot(0, b, lambda: place(w))        # le ✕ détruit (la fenêtre aussi) : rien


def update(w: QWidget) -> bool:
    """Pose, place ou cache le ✕ de la fenêtre `w` selon son état ; rend vrai s'il est montré."""
    full = bool(w.windowState() & Qt.WindowState.WindowFullScreen) and not getattr(w, 'vd_own_close', False)
    b = button_of(w)
    if not full:
        if b is not None:
            b.hide()
        _release(w)
        return False
    if b is None:
        b = QToolButton(w)
        b.setObjectName(NAME)
        b.setText('✕')
        b.setToolTip(tr('Fermer'))
        b.setFixedSize(SIZE, SIZE)
        b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(STYLE)
        b.clicked.connect(lambda: _close(b.window()))    # (pas de référence à la fenêtre : rien ne la retient)
    b.show()
    place(w)
    place_later(w)
    return True


class _Watch(QObject):
    """Filtre de l'application : passage en plein écran, apparition, nouvelle taille ou nouvelle mise en page d'une
    fenêtre."""

    TYPES = (QEvent.Type.WindowStateChange, QEvent.Type.Show, QEvent.Type.Resize, QEvent.Type.LayoutRequest)

    def eventFilter(self, obj, ev) -> bool:              # noqa: N802 (API Qt)
        t = ev.type()
        if t in self.TYPES and isinstance(obj, QWidget) and obj.isWindow():
            if t in (QEvent.Type.Resize, QEvent.Type.LayoutRequest):
                b = button_of(obj)
                if b is not None and not b.isHidden():       # montré (même si la fenêtre ne l'est pas encore)
                    if t == QEvent.Type.Resize:
                        place(obj)
                    place_later(obj)                     # des lignes montrées ou cachées : la bande a changé
            else:
                update(obj)
        return False


def install(app: QApplication | None = None) -> bool:
    """Pose le filtre sur l'application (une seule fois) ; rend vrai s'il est posé."""
    app = app or QApplication.instance()
    if app is None:
        return False
    if app.findChild(QObject, WATCH) is None:
        watch = _Watch(app)
        watch.setObjectName(WATCH)
        app.installEventFilter(watch)
    return True
