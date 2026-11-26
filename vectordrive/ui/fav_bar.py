"""La barre des favoris (demande du 15/11, 20 h 50) : clic droit sur un de ses boutons, « Afficher les libellés »
(retenu, pour toute la barre) et « Agencer les favoris à la souris » : un mode où l'on range les boutons en les
glissant ; l'ordre est retenu. Les favoris sont dans leur barre, tout en haut, ou à la suite de la barre d'accès rapide
de TypeEdit 13 (seuls ceux qu'ils y ont ajoutés se déplacent alors)."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QMimeData, QObject, QPoint, Qt, QTimer
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QApplication, QToolButton
from shiboken6 import isValid

from ..i18n import tr

#: réglage : les libellés à côté des icônes des favoris
LABELS_KEY = 'ruban/favoris_libelles'
#: type MIME d'un favori glissé (la clé de sa commande)
MIME = 'application/x-vectordrive-favorite'
#: propriété posée sur les boutons qui se déplacent, pendant l'agencement
ARRANGING = 'vd_fav_arranging'
#: propriété : la feuille de style du bouton avant l'agencement
_OLD_STYLE = 'vd_fav_style'
#: propriété : le libellé posé par les favoris (à retirer quand le bouton n'est plus favori)
_LABELLED = 'vd_fav_labelled'
#: les boutons à ranger, pendant l'agencement
STYLE = ' QToolButton { border: 1px dashed palette(highlight); border-radius: 3px; }'


def labels_on(settings) -> bool:
    return str(settings.value(LABELS_KEY, False)).lower() in ('true', '1')


def host_of(win):
    """La barre qui porte les favoris : la leur, ou la barre d'accès rapide de TypeEdit 13 ; None sans favoris."""
    for bar in (getattr(win, 'fav_bar', None), getattr(win, '_fav_host', None)):
        if bar is not None and isValid(bar):
            return bar
    return None


def buttons(win, host, movable: bool = False) -> list:
    """(clé, bouton) des favoris de `host`, de gauche à droite ; `movable` : seulement ceux qui se rangent (tous dans
    leur barre ; dans celle de TypeEdit 13, ceux qu'ils y ont ajoutés)."""
    added = {id(a) for a in getattr(win, '_fav_added', ())}
    own = host is getattr(win, 'fav_bar', None)
    out = []
    for k in win.favorite_keys():
        a = win.favorite_action(k)                       # (un bouton Mode de TypeEdit 13 aussi : round 1164)
        if movable and not own and id(a) not in added:
            continue
        b = host.widgetForAction(a)
        if isinstance(b, QToolButton) and isValid(b):
            out.append((k, b))
    out.sort(key=lambda kb: kb[1].geometry().x())
    return out


def decorate(win) -> None:
    """Après chaque remplissage des favoris : les libellés si le réglage le dit ; le mode d'agencement, s'il est en
    cours, posé sur les boutons du moment (fini s'il n'y a plus de favoris)."""
    old = getattr(win, '_fav_arranger', None)
    if old is not None:
        old.close()
        win._fav_arranger = None
    host = host_of(win)
    if host is None:
        win._fav_arranging = False
        return
    for b in host.findChildren(QToolButton):             # un bouton qui n'est plus favori : le style de sa barre
        if b.property(_LABELLED):
            b.setToolButtonStyle(host.toolButtonStyle())
            b.setProperty(_LABELLED, None)
    if labels_on(win.settings):
        for _k, b in buttons(win, host):
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            b.setProperty(_LABELLED, True)
    if getattr(win, '_fav_arranging', False):
        win._fav_arranger = Arranger(win, host)


def set_labels(win, on: bool) -> None:
    if on:
        win.settings.setValue(LABELS_KEY, True)
    else:
        win.settings.remove(LABELS_KEY)
    decorate(win)


class Arranger(QObject):
    """Le mode d'agencement sur la barre `host` : un appui sur un favori ne lance plus sa commande, on le glisse ;
    déposé sur la barre, il se range avant le bouton sous lequel il tombe (ou au bout). « Terminer l'agencement », au
    bout de la barre, ou le même clic droit, y met fin."""

    def __init__(self, win, host):
        super().__init__(host)
        self.win, self.host = win, host
        self.press = None
        self.drops = host.acceptDrops()
        host.setAcceptDrops(True)
        host.installEventFilter(self)
        self.items = buttons(win, host, movable=True)
        for _k, b in self.items:
            b.setProperty(_OLD_STYLE, b.styleSheet())
            b.setProperty(ARRANGING, True)
            b.setStyleSheet(b.styleSheet() + STYLE)
            b.installEventFilter(self)
        self.dragging = False
        self.pending = None                              # le rangement d'un dépôt, fait après le glisser
        self.done = host.addAction(tr('Terminer l’agencement'))
        self.done.setToolTip(tr('Agencement des favoris : glissez les boutons pour les ranger ; ce bouton y met fin'))
        self.done.triggered.connect(lambda _=False: QTimer.singleShot(0, lambda: win.arrange_favorites(False)))
        b = host.widgetForAction(self.done)
        if b is not None:                                # pas le menu des favoris : ce n'en est pas un
            b.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def close(self) -> None:
        if isValid(self.host):
            self.host.removeEventFilter(self)
            self.host.setAcceptDrops(self.drops)
            if isValid(self.done):
                self.host.removeAction(self.done)
        if isValid(self.done):
            self.done.deleteLater()
        for _k, b in self.items:
            if isValid(b):
                b.removeEventFilter(self)
                b.setStyleSheet(b.property(_OLD_STYLE) or '')
                b.setProperty(ARRANGING, None)
                b.setProperty(_OLD_STYLE, None)
        self.items = []
        if isValid(self):
            self.deleteLater()

    def before_at(self, pos: QPoint):
        """La clé du favori devant lequel se range un favori déposé en `pos` (coordonnées de la barre) ; None : au
        bout."""
        for k, b in self.items:
            if isValid(b) and pos.x() < b.geometry().center().x():
                return k
        return None

    def eventFilter(self, obj, ev):                      # noqa: N802 — API Qt
        t = ev.type()
        if obj is self.host:
            if t in (QEvent.Type.DragEnter, QEvent.Type.DragMove) and ev.mimeData().hasFormat(MIME):
                ev.setDropAction(Qt.DropAction.MoveAction)
                ev.accept()
                return True
            if t == QEvent.Type.Drop and ev.mimeData().hasFormat(MIME):
                key = bytes(ev.mimeData().data(MIME)).decode('utf-8')
                before = self.before_at(ev.position().toPoint())
                ev.setDropAction(Qt.DropAction.MoveAction)
                ev.accept()
                if self.dragging:                        # Linux, macOS : le glisser tourne encore ; après lui
                    self.pending = (key, before)
                else:
                    self.apply(key, before)
                return True
            return False
        if not (isinstance(obj, QToolButton) and obj.property(ARRANGING)):
            return False
        if t in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick) \
                and ev.button() != Qt.MouseButton.LeftButton:
            return False                                 # clic droit : le menu des favoris, comme d'habitude
        if t == QEvent.Type.MouseButtonPress:
            self.press = (obj, ev.position().toPoint())
            return True                                  # pas de commande pendant l'agencement
        if t == QEvent.Type.MouseMove:
            if self.press is not None and self.press[0] is obj and ev.buttons() & Qt.MouseButton.LeftButton \
                    and (ev.position().toPoint() - self.press[1]).manhattanLength() >= QApplication.startDragDistance():
                self.press = None
                self.drag(obj)
            return True
        if t in (QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick):
            self.press = None
            return True
        return False

    def drag(self, b) -> None:
        key = next((k for k, x in self.items if x is b), None)    # sa clé de favori (`te_mode:…` : round 1164)
        if key is None:
            return
        mime = QMimeData()
        mime.setData(MIME, key.encode('utf-8'))
        d = QDrag(b)
        d.setMimeData(mime)
        d.setPixmap(b.grab())
        d.setHotSpot(QPoint(b.width() // 2, b.height() // 2))
        self.dragging = True
        try:
            d.exec(Qt.DropAction.MoveAction)
        finally:
            self.dragging = False
        if self.pending is not None:
            key, before = self.pending
            self.pending = None
            self.apply(key, before)

    def apply(self, key: str, before) -> None:
        """Le rangement d'un dépôt, au tour suivant : la barre se refait (ses boutons, celui du glisser compris)."""
        win = self.win
        QTimer.singleShot(0, lambda: win.move_favorite(key, before))
