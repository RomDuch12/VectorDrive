"""Cases d'un formulaire que l'on range à sa guise : chaque section (une QGroupBox) se glisse par son titre vers une
autre place ou une autre colonne ; un clic sur son titre la plie ou la déplie ; la disposition et les cases pliées sont
gardées dans les réglages (clé donnée), reprises à la prochaine ouverture. Clic droit sur un titre : le nombre de
colonnes (1 à 4), tout plier, tout déplier, la disposition d'origine."""
from __future__ import annotations

import json

from PySide6.QtCore import QEvent, QMimeData, QPoint, QSize, Qt
from PySide6.QtGui import QColor, QDrag, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QFrame, QGroupBox, QHBoxLayout, QMenu, QScrollArea, QToolTip,
                               QVBoxLayout, QWidget)

from ..i18n import tr

MIME = 'application/x-vectordrive-case'
#: hauteur de la poignée d'une case quand sa bande de titre est inconnue (px)
GRIP_H = 22
MAX_COLS = 4
#: hauteur sans limite d'une case dépliée (QWIDGETSIZE_MAX)
UNLIMITED = 16777215
#: devant le titre d'une case pliée
FOLDED_MARK = '▸ '
#: largeur d'écran laissée hors des colonnes de cases (schéma du formulaire, marges) quand elles réclament la largeur
#: de leurs cases (px)
SCREEN_RESERVE = 360


def screen_width(widget) -> int:
    """Largeur disponible de l'écran de `widget` (px) ; 0 : inconnue."""
    scr = widget.screen() if widget is not None else None
    if scr is None:
        scr = QApplication.primaryScreen()
    return scr.availableGeometry().width() if scr is not None else 0


def hint() -> str:
    return tr('Glissez le titre de la case pour la ranger ailleurs ; un clic sur le titre la plie ou la déplie ; '
              'clic droit : colonnes, tout plier ou déplier, disposition d’origine')


def in_title(box, y) -> bool:
    """`y` (coordonnées de la case) dans la bande de son titre : la marge du haut que la QGroupBox lui réserve."""
    return y < (box.contentsRect().top() or GRIP_H)


def split(order: list, n: int) -> list[list]:
    """`order` réparti en `n` colonnes de même nombre de cases à une près (les premières ont la case de plus) ;
    jamais de colonne vide s'il y a assez de cases."""
    q, r = divmod(len(order), n)
    out, i = [], 0
    for c in range(n):
        k = q + (c < r)
        out.append(list(order[i:i + k]))
        i += k
    return out


class _Column(QWidget):
    """Une colonne de cases ; reçoit les cases glissées (un trait montre où elles iront)."""

    def __init__(self, board):
        super().__init__()
        self.board = board
        self.setAcceptDrops(True)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.addStretch(1)
        self._mark = None                                  # y du trait d'insertion pendant un glisser

    def tiles(self) -> list:
        out = []
        for i in range(self.lay.count()):
            w = self.lay.itemAt(i).widget()
            if w is not None:
                out.append(w)
        return out

    def index_at(self, y: int) -> int:
        """Rang d'insertion pour un lâcher à la hauteur `y` : avant la première case visible dont le milieu est plus
        bas."""
        shown = [t for t in self.tiles() if not t.isHidden()]
        for t in shown:
            if y < t.geometry().center().y():
                return self.tiles().index(t)
        return len(self.tiles())

    def _ours(self, e) -> bool:
        """Une case de ce formulaire (pas une glissée depuis un autre formulaire ouvert, qui a les mêmes sections)."""
        src = e.source()
        return e.mimeData().hasFormat(MIME) and (src is None or src in self.board.tiles.values())

    def dragEnterEvent(self, e) -> None:                   # noqa: N802 — API Qt
        if self._ours(e):
            e.acceptProposedAction()

    def dragMoveEvent(self, e) -> None:                    # noqa: N802 — API Qt
        if not self._ours(e):
            return
        e.acceptProposedAction()
        y = e.position().toPoint().y()
        i = self.index_at(y)
        tiles = self.tiles()
        self._mark = tiles[i].geometry().top() - 2 if i < len(tiles) else \
            (max((t.geometry().bottom() for t in tiles if not t.isHidden()), default=0) + 2)
        self.board.autoscroll(self, y)
        self.update()

    def dragLeaveEvent(self, e) -> None:                   # noqa: N802 — API Qt
        self._mark = None
        self.update()

    def dropEvent(self, e) -> None:                        # noqa: N802 — API Qt
        self._mark = None
        self.update()
        if not self._ours(e):
            return
        key = bytes(e.mimeData().data(MIME)).decode('utf-8')
        self.board.move_case(key, self.board.columns.index(self), self.index_at(e.position().toPoint().y()))
        e.acceptProposedAction()

    def paintEvent(self, e) -> None:                       # noqa: N802 — API Qt
        super().paintEvent(e)
        if self._mark is not None:
            p = QPainter(self)
            p.setPen(QPen(QColor(self.palette().highlight().color()), 3))
            p.drawLine(4, self._mark, self.width() - 4, self._mark)
            p.end()


class _ColumnScroll(QScrollArea):
    """La zone qui défile d'une colonne. À une ou deux colonnes (`share`), elle réclame la largeur de ses cases :
    sinon le bord droit d'une case plus large était coupé, et les flèches de ses champs, sous la colonne voisine ou le
    schéma du formulaire, ne recevaient plus le clic. Jamais plus que sa part de l'écran : au-delà, la barre
    horizontale apparaît (elle n'est montrée que si la case dépasse)."""

    share = 0

    def minimumSizeHint(self) -> QSize:                    # noqa: N802 — API Qt
        s = super().minimumSizeHint()
        w = self.widget()
        if w is None or not 0 < self.share <= 2:
            return s
        need = w.minimumSizeHint().width() + self.verticalScrollBar().sizeHint().width() + 2 * self.frameWidth()
        avail = screen_width(self)
        if avail > 0:
            need = min(need, max(160, (avail - SCREEN_RESERVE) // self.share))
        return QSize(max(s.width(), need), s.height())

    def eventFilter(self, obj, e) -> bool:                 # noqa: N802 — API Qt
        if obj is self.widget() and e.type() == QEvent.Type.LayoutRequest:
            self.updateGeometry()                          # une case a changé : la largeur voulue aussi
        return super().eventFilter(obj, e)


class TileBoard(QWidget):
    """Les cases (`tiles` : {clé: QGroupBox}, dans l'ordre d'origine) en colonnes, chacune dans sa zone qui défile.
    `settings`, `key` : où la disposition est gardée ; `columns` : nombre de colonnes d'origine."""

    def __init__(self, tiles: dict, settings=None, key: str = '', columns: int = 2, parent=None, default=None):
        super().__init__(parent)
        self.tiles = dict(tiles)
        self.settings = settings
        self.key = key
        #: disposition d'origine voulue par le formulaire (listes de clés, une par colonne) ; None : `split`
        self.default = [list(c) for c in default] if default else None
        self.default_columns = len(self.default) if self.default else max(1, min(MAX_COLS, int(columns)))
        self._press = None
        self.columns: list[_Column] = []
        self.scrolls: list[QScrollArea] = []
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(0, 0, 0, 0)
        for name, g in self.tiles.items():
            g.setProperty('vd_case', name)
            g.setProperty('vd_title', g.title())
            g.installEventFilter(self)                     # l'aide : sur la bande du titre seulement (eventFilter)
        self.arrange(self.saved() or self.default_layout())
        #: cases pliées (seul le titre reste) ; gardées sous `{key}_pliees`
        self.folded: set = set()
        for name in self.saved_folds():
            self.fold(name, True, save=False)
        # le focus entre dans une case pliée (Tab, champ montré par le formulaire) : elle se déplie
        QApplication.instance().focusChanged.connect(self._focus_moved)

    def _focus_moved(self, _old, new) -> None:
        try:
            folded = [n for n in self.folded if new is not None and self.tiles[n].isAncestorOf(new)]
        except RuntimeError:                             # case déjà détruite
            return
        for name in folded:
            self.fold(name, False, save=False)           # le temps de la saisie ; la case reste pliée la fois suivante

    # --- disposition -------------------------------------------------------------------------------------------
    def default_layout(self, n: int | None = None) -> list[list[str]]:
        """La disposition d'origine : celle du formulaire s'il en donne une (pour son nombre de colonnes ; une case
        qu'elle ne nomme pas va en bas de la colonne la plus courte) ; sinon les cases dans leur ordre, réparties en
        `n` colonnes de même nombre de cases."""
        if self.default and (n is None or n == len(self.default)):
            cols = [[k for k in c if k in self.tiles] for c in self.default]
            seen = {k for c in cols for k in c}
            for k in self.tiles:
                if k not in seen:
                    min(cols, key=len).append(k)
            return cols
        return split(list(self.tiles), n or self.default_columns)

    def layout_now(self) -> list[list[str]]:
        return [[t.property('vd_case') for t in c.tiles()] for c in self.columns]

    def saved(self) -> list[list[str]] | None:
        if self.settings is None or not self.key:
            return None
        raw = self.settings.value(self.key, '')
        try:
            cols = json.loads(raw) if isinstance(raw, str) and raw else None
        except ValueError:
            return None
        if not isinstance(cols, list) or not cols or len(cols) > MAX_COLS \
                or not all(isinstance(c, list) and all(isinstance(x, str) for x in c) for c in cols):
            return None
        return cols

    def save(self) -> None:
        """La disposition gardée ; les sections gardées que ce formulaire n'a pas (« Autres », celles d'un plugin
        absent cette fois) restent à leur place."""
        if self.settings is None or not self.key:
            return
        cols = self.layout_now()
        for ci, c in enumerate(self.saved() or []):
            for ii, k in enumerate(c):
                if k not in self.tiles and not any(k in d for d in cols):
                    col = cols[min(ci, len(cols) - 1)]
                    col.insert(min(ii, len(col)), k)
        self.settings.setValue(self.key, json.dumps(cols, ensure_ascii=False))

    def arrange(self, cols: list[list[str]]) -> None:
        """Les cases rangées selon `cols` (listes de clés) ; une case inconnue de `cols` (section nouvelle) va en bas
        de la colonne la plus courte ; une clé qui n'est plus une case est oubliée."""
        cols = [[n for n in c if n in self.tiles] for c in cols] or [[]]
        seen = {n for c in cols for n in c}
        dup = set()
        for c in cols:                                   # une clé deux fois : la première place
            keep = []
            for n in c:
                if n not in dup:
                    keep.append(n)
                    dup.add(n)
            c[:] = keep
        for n in self.tiles:
            if n not in seen:
                min(cols, key=len).append(n)
        hidden = {n: g.testAttribute(Qt.WidgetAttribute.WA_WState_ExplicitShowHide) and g.isHidden()
                  for n, g in self.tiles.items()}        # masquées par le formulaire (section vide) : le restent
        focus = QApplication.focusWidget()
        focus = focus if focus is not None and any(g.isAncestorOf(focus) for g in self.tiles.values()) else None
        for g in self.tiles.values():                    # détachées de l'ancienne disposition, gardées
            g.setParent(None)
        for sa in self.scrolls:
            self.row.removeWidget(sa)
            sa.hide()
            sa.deleteLater()
        self.columns, self.scrolls = [], []
        for c in cols:
            col = _Column(self)
            for n in c:
                col.lay.insertWidget(col.lay.count() - 1, self.tiles[n])
            sa = _ColumnScroll()
            sa.setWidgetResizable(True)
            sa.setFrameShape(QFrame.Shape.NoFrame)
            # une ou deux colonnes : la largeur de leurs cases (dans la limite de l'écran) ; 3 ou 4 colonnes
            # étroites : un champ trop large défile — jamais coupé
            sa.share = len(cols) if len(cols) <= 2 else 0
            sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            sa.setWidget(col)
            self.row.addWidget(sa, 1)
            self.columns.append(col)
            self.scrolls.append(sa)
        for n, g in self.tiles.items():
            g.setHidden(hidden[n])
        if focus is not None and focus.isVisibleTo(self):  # le champ en cours garde le focus
            focus.setFocus()

    def move_case(self, key: str, col: int, index: int) -> None:
        """La case `key` mise au rang `index` de la colonne `col` ; disposition gardée."""
        if key not in self.tiles or not 0 <= col < len(self.columns):
            return
        cols = self.layout_now()
        for c_i, c in enumerate(cols):
            if key in c:
                i = c.index(key)
                c.remove(key)
                if c_i == col and i < index:
                    index -= 1
        cols[col].insert(max(0, min(index, len(cols[col]))), key)
        self.arrange(cols)
        self.save()

    def set_columns(self, n: int) -> None:
        """`n` colonnes : les cases gardent leur ordre de lecture (colonne après colonne), réparties à nouveau."""
        n = max(1, min(MAX_COLS, int(n)))
        self.arrange(split([k for c in self.layout_now() for k in c], n))
        self.save()

    def reset(self) -> None:
        self.arrange(self.default_layout())
        for name in list(self.folded):
            self.fold(name, False, save=False)
        if self.settings is not None and self.key:
            self.settings.remove(self.key)
            self.settings.remove(self.key + '_pliees')

    # --- cases pliées ------------------------------------------------------------------------------------------
    def saved_folds(self) -> list[str]:
        if self.settings is None or not self.key:
            return []
        raw = self.settings.value(self.key + '_pliees', '')
        try:
            names = json.loads(raw) if isinstance(raw, str) and raw else []
        except ValueError:
            return []
        return [n for n in names if isinstance(n, str) and n in self.tiles] if isinstance(names, list) else []

    def fold(self, name: str, on: bool, save: bool = True) -> None:
        """La case `name` pliée (seule la bande de son titre reste, « ▸ » devant) ou dépliée ; gardée si `save`."""
        g = self.tiles.get(name)
        if g is None:
            return
        base = str(g.property('vd_title') or g.title())
        if on:
            self.folded.add(name)
            g.setTitle(FOLDED_MARK + base)
            top = g.contentsMargins().top()              # la bande du titre (celle de in_title), sinon d'après la police
            g.setMaximumHeight((top if top > 0 else g.fontMetrics().height() + 6) + 2)
        else:
            self.folded.discard(name)
            g.setTitle(base)
            g.setMaximumHeight(UNLIMITED)
        g.setProperty('vd_folded', on)
        if save:
            self.save_folds()

    def save_folds(self) -> None:
        if self.settings is None or not self.key:
            return
        raw = self.settings.value(self.key + '_pliees', '')
        try:
            old = json.loads(raw) if isinstance(raw, str) and raw else []
        except ValueError:
            old = []
        kept = [n for n in old if isinstance(n, str) and n not in self.tiles] if isinstance(old, list) else []
        self.settings.setValue(self.key + '_pliees', json.dumps(sorted(set(kept) | self.folded), ensure_ascii=False))

    def toggle(self, name: str) -> None:
        self.fold(name, name not in self.folded)

    def fold_all(self, on: bool) -> None:
        for name in self.tiles:
            self.fold(name, on, save=False)
        self.save_folds()

    def autoscroll(self, col, y: int) -> None:
        """Pendant un glisser, près du haut ou du bas de la zone visible : elle défile."""
        sa = self.scrolls[self.columns.index(col)]
        bar = sa.verticalScrollBar()
        top = sa.widget().mapTo(sa.viewport(), QPoint(0, y)).y()
        if top < 24:
            bar.setValue(bar.value() - 20)
        elif top > sa.viewport().height() - 24:
            bar.setValue(bar.value() + 20)

    # --- glisser une case par son titre ------------------------------------------------------------------------
    def eventFilter(self, obj, e) -> bool:                 # noqa: N802 — API Qt
        if isinstance(obj, QGroupBox) and obj.property('vd_case') in self.tiles:
            t = e.type()
            if t == QEvent.Type.MouseButtonPress and e.button() == Qt.MouseButton.LeftButton \
                    and in_title(obj, e.position().y()):
                self._press = (obj, e.position().toPoint())
            elif t == QEvent.Type.MouseMove and self._press is not None and self._press[0] is obj \
                    and (e.position().toPoint() - self._press[1]).manhattanLength() \
                    >= QApplication.startDragDistance():
                self._press = None
                self.drag(obj)
                return True
            elif t == QEvent.Type.MouseButtonRelease:
                clicked = self._press is not None and self._press[0] is obj and e.button() == Qt.MouseButton.LeftButton \
                    and in_title(obj, e.position().y())
                self._press = None
                if clicked:                                # un clic sur le titre, sans glisser : pliée ou dépliée
                    self.toggle(obj.property('vd_case'))
                    return True
            elif t == QEvent.Type.ContextMenu and in_title(obj, e.pos().y()):
                self.menu(e.globalPos())
                return True
            elif t == QEvent.Type.ToolTip and in_title(obj, e.pos().y()):
                QToolTip.showText(e.globalPos(), hint(), obj)   # pas sur les champs : ils montrent les leurs
                return True
        return super().eventFilter(obj, e)

    def drag(self, g) -> None:
        md = QMimeData()
        md.setData(MIME, str(g.property('vd_case')).encode('utf-8'))
        d = QDrag(g)
        d.setMimeData(md)
        d.setPixmap(g.grab().scaledToWidth(min(240, max(60, g.width())), Qt.TransformationMode.SmoothTransformation))
        d.exec(Qt.DropAction.MoveAction)

    def menu(self, pos) -> None:
        m = QMenu(self)
        for n in range(1, MAX_COLS + 1):
            a = m.addAction(tr('{0} colonne(s)').format(n))
            a.setCheckable(True)
            a.setChecked(n == len(self.columns))
            a.triggered.connect(lambda _=False, n=n: self.set_columns(n))
        m.addSeparator()
        m.addAction(tr('Tout plier'), lambda: self.fold_all(True))
        m.addAction(tr('Tout déplier'), lambda: self.fold_all(False))
        m.addSeparator()
        m.addAction(tr('Disposition d’origine'), self.reset)
        m.exec(pos)
        m.deleteLater()
