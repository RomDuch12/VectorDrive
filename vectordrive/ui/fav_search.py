"""La recherche de boutons de la barre des favoris (demande : « placer barre de recherche bouton dans Favorites_bar,
dans la liste de résultat indiquer emplacement bouton actuel et permettre le menu click droit comme si on le faisait
dans le ruban ») : un champ à loupe au bout de la barre qui porte les favoris (la leur, ou celle d'accès rapide de
TypeEdit 13) ; sans barre des favoris, dans la rangée des onglets du ruban (à gauche d'Options et Aide). Ctrl+K y met
le curseur. Ses résultats, en surimpression sous lui, disent où est le bouton de chaque commande dans la disposition
affichée (onglet › groupe du ruban, menu d'un bouton du ruban, barre des favoris, barre d'accès rapide ; « (mode
expert) » pour un bouton caché en mode simple, un bouton montré d'abord) et son raccourci ; un clic ou Entrée la
lance ; le clic droit ouvre le menu du clic droit de ce bouton dans le ruban — le même, bâti par
`MainWindow._ribbon_button_menu`.

Le champ est un enfant de la barre, pas une de ses actions : ce n'est pas un favori (rien à retirer), l'agencement ne
le range pas, et les actions de la barre restent ses favoris ; la barre lui garde sa place par sa marge de droite."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, Qt, QTimer
from PySide6.QtGui import QKeySequence, QPalette
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QToolButton
from shiboken6 import isValid

from ..i18n import tr
from .command_search import rank
from .icons import icon

#: largeur du champ (loupe comprise), en pixels
WIDTH = 210
#: résultats montrés au plus, et rangées visibles sans défiler
LIMIT, ROWS = 40, 10
#: entre l'onglet, le groupe et le reste d'un emplacement
SEP = ' › '
#: touches que le champ garde pour lui (sinon des raccourcis de la fenêtre : Échap = Sélection, flèches…)
_KEYS = (Qt.Key.Key_Escape, Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown,
         Qt.Key.Key_Return, Qt.Key.Key_Enter)


def search_host(win):
    """La barre qui reçoit le champ : celle des favoris (`fav_bar.host_of`), sinon la barre d'accès rapide de
    TypeEdit 13 (où vont les favoris) ; None : pas de barre (le champ va dans la rangée des onglets du ruban)."""
    from .fav_bar import host_of
    host = host_of(win)
    if host is None:
        te = getattr(win, 'te_quickbar', None)
        host = te if te is not None and isValid(te) else None
    return host


def corner_layout(win):
    """La rangée des onglets du ruban, à droite (`Ribbon._corner_layout`) : le champ y va sans barre des favoris."""
    lay = getattr(getattr(win, 'ribbon', None), '_corner_layout', None)
    return lay if lay is not None and isValid(lay) and lay.parentWidget() is not None else None


def place(win) -> None:
    """Après chaque remplissage des favoris : le champ au bout de leur barre (gardé s'il y est déjà) ; sans barre,
    dans la rangée des onglets du ruban."""
    host, lay = search_host(win), None
    if host is None:
        lay = corner_layout(win)
        host = lay.parentWidget() if lay is not None else None
    old = getattr(win, 'fav_search', None)
    if old is not None and isValid(old) and host is not None and old.host is host:
        old.reposition()
        return
    if old is not None and isValid(old):
        old.remove()
    lst = getattr(win, '_fav_search_list', None)         # (la barre partie avec le champ : sa liste reste)
    if lst is not None and isValid(lst):
        lst.hide()
        lst.deleteLater()
    win._fav_search_list = None
    win.fav_search = SearchBox(win, host, lay) if host is not None else None


def _src(act):
    from .ribbon_editor import RelayAction
    return act.src if isinstance(act, RelayAction) else act


def _text(s: str) -> str:
    return str(s or '').replace('&', '').replace('\n', ' ').strip()


def ribbon_index(win) -> dict:
    """{id(commande) : [(emplacement, bouton ou None)]} des onglets du ruban de la disposition affichée (VectorDrive,
    ou TypeEdit 13 avec Fichier, Aide et les onglets à soi) : « onglet › groupe » d'un bouton ; un bouton Mode de
    TypeEdit 13 compte pour la commande qu'il prend (après les boutons de celle-ci) ; « onglet › bouton › section »
    d'une commande du menu d'un bouton (les onglets de VectorDrive dans TypeEdit 13 : pas de bouton à elle). Un bouton
    que le filtre du mode simple cache (et les commandes de son menu) : « (mode expert) » au bout — pas un bouton
    caché parce que sa commande l'est (propre à une autre machine) : le mode expert n'y changerait rien."""
    r = getattr(win, 'ribbon', None)
    out: dict = {}
    if r is None:
        return out
    te = bool(getattr(win, 'layout_active', False))
    allowed = getattr(r, 'mode_filter', None)            # None : mode expert, tout est permis
    modes = []
    for i in range(r.count()):
        w, page = r.widget(i), r.page(i)
        if page is None or not (w.property('ribbon_custom') or w.property('ribbon_both')
                                or bool(w.property('te_layout')) == te):
            continue                                     # un onglet de l'autre disposition
        tab = _text(r.tabText(i))
        if not r.isTabVisible(i) and not (allowed is not None and w.property('ribbon_vacant')):   # (vidé par le
            ctx = w.property('te_context') or r.tabText(i) == getattr(win, 'text_tab_title', None)   # mode simple :
            tab = (tr('{0} (onglet contextuel)') if ctx else tr('{0} (onglet masqué)')).format(tab)   # ses boutons
        for g in page.groups():                                                                      # le disent)
            where = tab + SEP + _text(g.title.text())
            for b in g.buttons():
                act = b.defaultAction()
                expert = allowed is not None and act.isVisible() and not allowed(act)
                here = tr('{0} (mode expert)').format(where) if expert else where
                origin = win._origin_key(act)
                if origin is not None:                   # bouton Mode : après les boutons de sa commande
                    modes.append((id(win.A[origin]), here, b))
                    continue
                out.setdefault(id(_src(act)), []).append((here, b))
                m = act.menu()
                section = ''
                for a in (m.actions() if m is not None else ()):
                    if a.isSeparator():
                        section = _text(a.text())
                    elif not a.menu():
                        place_ = tab + SEP + _text(act.text()) + (SEP + section if section else '')
                        if expert:
                            place_ = tr('{0} (mode expert)').format(place_)
                        out.setdefault(id(_src(a)), []).append((place_, None))
    for k, where, b in modes:
        out.setdefault(k, []).append((where, b))
    return out


def favorite_ids(win) -> set:
    """id() des commandes des favoris (lues une fois par recherche)."""
    return {id(win.favorite_action(k)) for k in win.favorite_keys()}


def shortcut_label(act) -> str:
    """« Raccourci Ctrl+… » de la commande `act`, ou '' sans raccourci."""
    sc = act.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
    return tr('Raccourci {0}').format(sc) if sc else ''


def places(win, key: str, index: dict | None = None, favs: set | None = None) -> list:
    """[(emplacement, bouton ou None)] de la commande `key` dans la disposition affichée : le ruban (`ribbon_index`),
    la barre des favoris (celle d'accès rapide quand elle les porte, en TypeEdit 13), son raccourci clavier (sans
    bouton). Les boutons montrés d'abord (pas ceux que le mode simple cache), dans cet ordre-là. `index` et `favs`
    (`favorite_ids`) : lus une fois pour toute une recherche."""
    act = win.A.get(key)
    if act is None:
        return []
    index = ribbon_index(win) if index is None else index
    favs = favorite_ids(win) if favs is None else favs
    out, seen = [], set()
    for where, b in index.get(id(act), ()):
        if where not in seen:
            seen.add(where)
            out.append((where, b))
    from .fav_bar import host_of
    host = host_of(win)
    te = getattr(win, 'te_quickbar', None)
    te = te if te is not None and isValid(te) else None
    if id(act) in favs:
        label = tr('Barre d’accès rapide') if host is not None and host is te else tr('Barre des favoris')
        out.append((label, host.widgetForAction(act) if host is not None else None))
    elif te is not None and any(a is act for a in te.actions()):
        out.append((tr('Barre d’accès rapide'), te.widgetForAction(act)))
    out.sort(key=lambda e: not _shown(e[1]))             # (tri stable : l'ordre gardé de part et d'autre)
    sc = shortcut_label(act)
    if sc:
        out.append((sc, None))
    return out


def _shown(b) -> bool:
    """`b` est-il un bouton montré (pas caché par le mode simple) ?"""
    return isinstance(b, QToolButton) and isValid(b) and not b.isHidden()


def menu_button(win, key: str, index: dict | None = None, favs: set | None = None):
    """Le bouton dont la recherche reprend le menu du clic droit : le premier montré de la commande (au ruban, sinon
    un bouton Mode de TypeEdit 13 qui la prend, sinon le sien dans la barre des favoris ou d'accès rapide), à défaut
    le premier caché (mode simple : son menu le rend au mode simple) ; None."""
    found = [b for _w, b in places(win, key, index, favs) if isinstance(b, QToolButton) and isValid(b)]
    return next((b for b in found if not b.isHidden()), found[0] if found else None)


def result_menu(win, key: str, pos=None, exec_menu: bool = True):
    """Le menu du clic droit d'un résultat : celui du clic droit de son bouton (`menu_button`) dans le ruban, par la
    même fonction (`_ribbon_button_menu`, arguments de `_button_menu_args`) ; sans bouton dans la disposition
    affichée, le même menu pour un bouton hors du ruban : ses réglages d'outil, le mode simple, les favoris, les
    onglets à soi (ni taille ni place : il n'est pas rangé au ruban). Rend le menu (bâti seulement si `exec_menu` est
    faux)."""
    act = win.A.get(key)
    if act is None:
        return None
    pos = pos if pos is not None else QPoint(0, 0)
    b = menu_button(win, key)
    kw = win._button_menu_args(b) if b is not None else None
    if kw is not None:
        return win._ribbon_button_menu(b, pos, exec_menu=exec_menu, **kw)
    ghost = QToolButton()                                # un bouton seul, hors de toute barre
    ghost.setDefaultAction(act)
    try:
        return win._ribbon_button_menu(ghost, pos, exec_menu=exec_menu, settings=win._tool_settings(act))
    finally:
        ghost.deleteLater()


class _Field(QLineEdit):
    """Le champ : flèches et pages dans la liste, Entrée lance, Échap ferme la liste (puis vide le champ et rend la
    main au plan de travail) ; touche Menu : le menu du clic droit du résultat choisi."""

    def __init__(self, box):
        super().__init__(box)
        self.box = box

    def event(self, ev):                                 # API Qt
        if ev.type() == QEvent.Type.ShortcutOverride and ev.key() in _KEYS:
            ev.accept()                                  # pour lui, pas pour les raccourcis de la fenêtre
            return True
        return super().event(ev)

    def keyPressEvent(self, ev) -> None:                 # noqa: N802 — API Qt
        box = self.box
        k = ev.key()
        if k in (Qt.Key.Key_Down, Qt.Key.Key_Up, Qt.Key.Key_PageDown, Qt.Key.Key_PageUp):
            if self.text().strip() and not box.results.isVisible():
                box.show_results()
            box.results.keyPressEvent(ev)                # le curseur reste dans le champ
            return
        if k == Qt.Key.Key_Escape:
            if box.results.isVisible():
                box.results.hide()
            else:
                self.clear()
                box.leave()
            return
        if k == Qt.Key.Key_Menu:
            box.menu_current()
            return
        super().keyPressEvent(ev)

    def focusInEvent(self, ev) -> None:                  # noqa: N802 — API Qt
        super().focusInEvent(ev)
        if self.text().strip():
            self.box.show_results()

    def focusOutEvent(self, ev) -> None:                 # noqa: N802 — API Qt
        super().focusOutEvent(ev)
        if ev.reason() != Qt.FocusReason.PopupFocusReason:   # (le menu du clic droit : la liste reste)
            self.box.results.hide()


class SearchBox(QFrame):
    """Le champ à loupe, enfant de la barre `host`, tenu à son bout droit — ou, `corner` donné (la rangée des onglets
    du ruban, sans barre des favoris), rangé dans celle-ci, à gauche d'Options et Aide ; sa liste de résultats,
    enfant de la fenêtre (au-dessus du ruban et du plan de travail), qui le suit quand la fenêtre change de taille."""

    def __init__(self, win, host, corner=None):
        super().__init__(host)
        self.win, self.host, self.corner = win, host, corner
        self.setObjectName('favSearch')
        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 0, 2, 0)
        lay.setSpacing(3)
        self.loupe = QLabel(self)
        self.loupe.setPixmap(icon('command_search').pixmap(16, 16))
        self.edit = _Field(self)
        self.edit.setFocusPolicy(Qt.FocusPolicy.ClickFocus)  # pas par Tab ni d'office à l'ouverture (le plan de
        #                                                      travail garde le clavier) ; Ctrl+K ou un clic
        self.update_hint()
        tip = tr('Chercher un bouton ou une commande : où est son bouton (onglet › groupe), Entrée ou clic la lance, '
                 'clic droit : son menu, comme dans le ruban')
        self.edit.setToolTip(tip)
        self.loupe.setToolTip(tip)
        lay.addWidget(self.loupe)
        lay.addWidget(self.edit, 1)
        self.setFixedWidth(WIDTH)
        self.results = QListWidget(win)
        self.results.setObjectName('favSearchResults')
        self.results.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # le curseur reste dans le champ
        self.results.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.results.hide()
        win._fav_search_list = self.results
        self.edit.textChanged.connect(lambda t: self.refresh(t))
        self.edit.returnPressed.connect(lambda: self.run_current())
        self.results.itemClicked.connect(lambda it: self.run_item(it))
        self.results.customContextMenuRequested.connect(lambda p: self.menu_at(p))
        self._margins = None
        if corner is not None:                           # la rangée des onglets : avant Options et Aide
            bar = getattr(win.ribbon, 'right_bar', None)
            at = corner.indexOf(bar) if bar is not None else -1
            corner.insertWidget(at if at >= 0 else corner.count(), self, 0, Qt.AlignmentFlag.AlignVCenter)
        else:
            m = host.contentsMargins()
            self._margins = (m.left(), m.top(), m.right(), m.bottom())
            host.setContentsMargins(m.left(), m.top(), m.right() + WIDTH + 4, m.bottom())   # sa place, au bout
            host.installEventFilter(self)
        win.installEventFilter(self)                     # la liste suit la fenêtre
        self.reposition()
        self.show()

    def remove(self) -> None:
        """Ôté de sa barre (marge rendue) ou de la rangée des onglets, avec sa liste."""
        if isValid(self.win):
            self.win.removeEventFilter(self)
        if self.corner is not None and isValid(self.corner):
            self.corner.removeWidget(self)
        elif isValid(self.host):
            self.host.removeEventFilter(self)
            self.host.setContentsMargins(*self._margins)
        if isValid(self.results):
            self.results.hide()
            self.results.deleteLater()
        self.hide()
        self.setParent(None)
        self.deleteLater()

    def update_hint(self) -> None:
        """Le texte d'invite, avec le raccourci réel de « Chercher une commande » (rien s'il n'en a pas)."""
        act = self.win.A.get('command_search')
        sc = act.shortcut().toString(QKeySequence.SequenceFormat.NativeText) if act is not None else ''
        self.edit.setPlaceholderText(tr('Chercher un bouton… ({0})').format(sc) if sc else tr('Chercher un bouton…'))

    def showEvent(self, ev) -> None:                     # noqa: N802 — API Qt
        super().showEvent(ev)
        self.update_hint()                               # (raccourcis posés après lui à l'ouverture)

    def eventFilter(self, obj, ev):                      # noqa: N802 — API Qt
        t = ev.type()
        if obj is self.host and t in (QEvent.Type.Resize, QEvent.Type.Move, QEvent.Type.Show,
                                      QEvent.Type.LayoutRequest):
            self.reposition()
        elif obj is self.win and t == QEvent.Type.Resize:
            self._follow()
        return False

    def moveEvent(self, ev) -> None:                     # noqa: N802 — API Qt
        super().moveEvent(ev)
        self._follow()

    def resizeEvent(self, ev) -> None:                   # noqa: N802 — API Qt
        super().resizeEvent(ev)
        self._follow()

    def _follow(self) -> None:
        """La liste ouverte reposée sous le champ (fenêtre ou barre qui change de taille)."""
        lst = getattr(self, 'results', None)
        if lst is not None and isValid(lst) and lst.isVisible():
            self.show_results()

    def reposition(self) -> None:
        """Au bout droit de la barre, centré en hauteur (dans la rangée des onglets : rangé par elle)."""
        if not isValid(self.host):
            return
        if self.corner is None:
            r = self.host.rect()
            h = min(max(self.sizeHint().height(), 20), max(r.height(), 20))
            self.setGeometry(max(0, r.width() - WIDTH - 2), max(0, (r.height() - h) // 2), WIDTH, h)
            self.raise_()
        self._follow()

    def take_focus(self) -> None:
        """Ctrl+K : le curseur dans le champ, son texte choisi (on retape par-dessus)."""
        self.edit.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.edit.selectAll()
        if self.edit.text().strip():
            self.show_results()

    def leave(self) -> None:
        """La main rendue au plan de travail."""
        self.results.hide()
        canvas = getattr(self.win, 'canvas', None)
        if canvas is not None:
            canvas.setFocus()

    def refresh(self, text: str) -> None:
        """Les commandes qui répondent à `text` (comme Ctrl+K : `command_search.rank`), chacune avec l'emplacement de
        son bouton dans la disposition affichée. Les commandes invisibles (d'une autre machine…) n'y sont pas ; une
        commande désactivée y est, grisée : Entrée ou clic ne la lance pas, le clic droit donne son menu."""
        lst = self.results
        lst.clear()
        if not text.strip():
            lst.hide()
            return
        acts = [(k, a) for k, a in self.win.A.items() if k != 'command_search' and a.text() and a.isVisible()]
        index, favs = ribbon_index(self.win), favorite_ids(self.win)
        grey = lst.palette().brush(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text)
        for key, act in rank(text, acts)[:LIMIT]:
            found = places(self.win, key, index, favs)
            where = [w for w, _b in found]
            if not [w for w in where if w != shortcut_label(act)]:   # ni ruban, ni menu, ni barre
                where.insert(0, tr('Pas de bouton dans cette disposition'))
            it = QListWidgetItem(act.icon(), _text(act.text()) + '\n      ' + ' · '.join(where))
            it.setToolTip(act.toolTip() or _text(act.text()))
            it.setData(Qt.ItemDataRole.UserRole, key)
            if not act.isEnabled():
                it.setForeground(grey)
            lst.addItem(it)
        if not lst.count():
            it = QListWidgetItem(tr('Aucune commande ne correspond'))
            it.setFlags(Qt.ItemFlag.NoItemFlags)
            lst.addItem(it)
        else:                                            # le premier résultat activé (une commande grisée choisie
            first = next((i for i in range(lst.count())  # d'office paraîtrait prête à partir)
                          if self.win.A[lst.item(i).data(Qt.ItemDataRole.UserRole)].isEnabled()), 0)
            lst.setCurrentRow(first)
        self.show_results()

    def show_results(self) -> None:
        """La liste sous le champ, dans la fenêtre, au-dessus de tout."""
        lst, win = self.results, self.win
        if not lst.count() or not isValid(self.host):
            return
        at = self.mapTo(win, QPoint(0, self.height()))
        w = min(max(WIDTH, 460), max(win.width() - 8, WIDTH))
        x = max(4, min(at.x() + self.width() - w, win.width() - w - 4))   # aligné sur le bout droit du champ
        rows = sum(max(lst.sizeHintForRow(i), 16) for i in range(min(lst.count(), ROWS)))
        lst.setGeometry(x, at.y() + 1, w, rows + 2 * lst.frameWidth() + 2)
        lst.raise_()
        lst.show()

    def current_key(self):
        it = self.results.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it is not None else None

    def run_current(self) -> None:
        self.run_item(self.results.currentItem())

    def run_item(self, it) -> None:
        """Lance la commande du résultat `it` ; le champ se vide et rend la main au plan de travail. La commande part
        au tour suivant de la boucle (elle peut refaire les favoris, donc ce champ et sa liste, dont le gestionnaire
        est en cours) ; désactivée : un mot en barre d'état, rien d'autre."""
        key = it.data(Qt.ItemDataRole.UserRole) if it is not None else None
        act = self.win.A.get(key) if key else None
        if act is None:
            return
        if not act.isEnabled():
            self.win.statusBar().showMessage(tr('« {0} » n’est pas disponible ici').format(_text(act.text())), 4000)
            return
        self.edit.clear()
        self.leave()
        QTimer.singleShot(0, lambda a=act: a.trigger() if isValid(a) and a.isEnabled() else None)

    def _menu(self, key, gpos, exec_menu: bool):
        """Le menu de `key` en `gpos` : rendu tout de suite s'il n'est que bâti (`exec_menu` faux, essais) ; sinon
        ouvert au tour suivant de la boucle (« Ajouter aux favoris » refait les favoris, donc ce champ et sa liste,
        dont le gestionnaire du clic est en cours) et None."""
        if not exec_menu:
            return result_menu(self.win, key, gpos, exec_menu=False)
        QTimer.singleShot(0, lambda w=self.win: result_menu(w, key, gpos) if isValid(w) else None)
        return None

    def menu_at(self, p, exec_menu: bool = True):
        """Clic droit en `p` (coordonnées de la liste) : le menu du résultat qui est là (`_menu`) ; None hors d'un
        résultat."""
        it = self.results.itemAt(p)
        key = it.data(Qt.ItemDataRole.UserRole) if it is not None else None
        if not key:
            return None
        self.results.setCurrentItem(it)
        return self._menu(key, self.results.viewport().mapToGlobal(p), exec_menu)

    def menu_current(self, exec_menu: bool = True):
        """Le menu du clic droit du résultat choisi (touche Menu, `_menu`) ; None sans résultat."""
        key = self.current_key()
        if not key:
            return None
        lst = self.results
        r = lst.visualItemRect(lst.currentItem())
        return self._menu(key, lst.viewport().mapToGlobal(r.center()), exec_menu)
