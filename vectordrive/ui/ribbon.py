"""Ruban façon TypeEdit : onglets, groupes d'icônes titrés, et zone
d'informations sur la sélection en bout de ruban. Réglable (F10 >
Apparence) : taille des icônes, libellés, légendes des groupes ; réduit
aux onglets par un double-clic (un clic sur un onglet le déplie le temps
d'une commande).

Jamais de défilement horizontal : quand la fenêtre est trop étroite pour un
onglet, ses petits boutons perdent d'abord leur libellé (icône seule, le nom
en infobulle), du groupe le plus large au plus étroit ; puis les groupes se
replient en **familles**, de la droite vers la gauche, comme le ruban de
TypeEdit 13 — un bouton par famille, et un clic dessus déroule la barre de
la famille. Option (F10 > Apparence) : familles toujours repliées. Les
libellés des grands boutons passent sur deux lignes (comme TypeEdit) : un
onglet tient en Full HD, et s'étale tout entier sur un écran plus large."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QFont, QFontMetrics, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy,
                               QTabWidget, QToolButton, QVBoxLayout, QWidget)

SCROLL_H = 0            # plus de barre de défilement horizontale (familles repliées)
SMALL_ROWS = 3          # petits boutons empilés par colonnes de trois, comme dans TypeEdit
#: taille des icônes (grands et petits boutons) ; voir Ribbon.configure
BIG_ICON = 28
SMALL_ICON = 16
#: tailles proposées dans les options
ICON_SIZES = {'petites': (22, 16), 'normales': (28, 16), 'grandes': (36, 20)}
#: repli des groupes en familles : selon la place, ou toujours
FAMILIES = ('place', 'toujours')


class FamilyPopup(QFrame):
    """Barre déroulée d'une famille repliée : le contenu du groupe, sous son
    bouton ; se referme après une commande ou un clic à côté."""

    def __init__(self, group: 'RibbonGroup'):
        super().__init__(group, Qt.WindowType.Popup)
        self.setObjectName('ribbonFamilyPopup')
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setAutoFillBackground(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 3, 4, 3)
        lay.setSpacing(0)
        self.title = QLabel(group.title.text())
        self.title.setObjectName('ribbonGroupTitle')
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.title)
        self.lay = lay

    def hold(self, body: QWidget) -> None:
        self.lay.insertWidget(0, body, 1)

    def show_under(self, button: QWidget) -> None:
        self.adjustSize()
        pos = button.mapToGlobal(QPoint(0, button.height()))
        scr = button.screen().availableGeometry() if button.screen() is not None else None
        if scr is not None:
            pos.setX(max(scr.left(), min(pos.x(), scr.right() - self.width())))
            if pos.y() + self.height() > scr.bottom():
                pos.setY(button.mapToGlobal(QPoint(0, 0)).y() - self.height())
        self.move(pos)
        self.show()


class ViewSwitch(QToolButton):
    """Le va-et-vient 2D / 3D : les deux toujours écrits, le mode en cours (propriété `vd_mode` de
    l'action) mis en valeur, l'autre grisé ; un clic, où que ce soit, bascule."""

    SIDES = (('2d', '2D'), ('3d', '3D'))

    def sides(self) -> tuple:
        """Les deux côtés (clé, texte) : ceux que donne la commande (propriété `vd_sides` : Simple / Expert), sinon
        2D / 3D."""
        a = self.defaultAction()
        got = a.property('vd_sides') if a is not None else None
        return tuple((str(k), str(t)) for k, t in got) if got else self.SIDES

    def sizeHint(self) -> QSize:                         # noqa: N802 (API Qt)
        f = QFont(self.font())
        f.setBold(True)
        m = QFontMetrics(f)
        return QSize(2 * (max(m.horizontalAdvance(t) for _k, t in self.sides()) + 16) + 2, m.height() + 10)

    def minimumSizeHint(self) -> QSize:                  # noqa: N802 (API Qt)
        return self.sizeHint()

    def paintEvent(self, _ev) -> None:                   # noqa: N802 (API Qt)
        a = self.defaultAction()
        mode = a.property('vd_mode') if a is not None else None
        pal = self.palette()
        hint = self.sizeHint()
        w, h = min(self.width() - 2, hint.width() - 2), min(self.height() - 2, hint.height() - 2)
        box = QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        shape = QPainterPath()
        shape.addRoundedRect(box, 4, 4)
        p.setClipPath(shape)
        sides = self.sides()
        for i, (key, text) in enumerate(sides):
            cell = QRectF(box.x() + i * w / 2, box.y(), w / 2, h)
            on = mode == key
            if on:
                p.fillRect(cell, pal.color(QPalette.ColorRole.Highlight))
            f = QFont(self.font())
            f.setBold(on)
            p.setFont(f)
            p.setPen(pal.color(QPalette.ColorRole.HighlightedText) if on
                     else pal.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText))
            p.drawText(cell, Qt.AlignmentFlag.AlignCenter, text)
            if not on and mode in [k for k, _t in sides]:      # l'autre : un fin liseré de la couleur du mode en cours
                p.setPen(QPen(pal.color(QPalette.ColorRole.Highlight), 1.2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(cell.adjusted(1.5, 1.5, -1.5, -1.5), 3, 3)
        p.setClipping(False)
        p.setPen(QPen(pal.color(QPalette.ColorRole.Highlight if self.underMouse() else QPalette.ColorRole.Mid), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(box, 4, 4)
        p.end()


class RibbonGroup(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setObjectName('ribbonGroup')
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 0)
        lay.setSpacing(0)
        self._lay = lay
        #: contenu du groupe (ses boutons) ; replié, il passe dans la barre déroulée
        self.body = QWidget(self)
        self._row = QHBoxLayout(self.body)
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(1)
        lay.addWidget(self.body, 1)
        #: bouton de la famille (groupe replié)
        self.family = QToolButton(self)
        self.family.setObjectName('ribbonFamily')
        self.family.setAutoRaise(True)
        self.family.setProperty('ribbon_family', True)
        self.family.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.family.setText(f'{title} ▾')
        self.family.clicked.connect(self.unroll)
        self.family.hide()
        lay.addWidget(self.family, 1)
        lab = QLabel(title)
        lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lab.setObjectName('ribbonGroupTitle')
        lab.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)   # la place en trop va aux boutons
        lay.addWidget(lab, 0, Qt.AlignmentFlag.AlignBottom)
        self.title = lab
        self._col: QVBoxLayout | None = None
        #: petits éléments par colonne (le formulaire de Mise en forme : deux rangées, comme le Rapido de TypeEdit)
        self.rows = SMALL_ROWS
        self.collapsed = False
        self.captions = True
        self.popup: FamilyPopup | None = None
        #: (élément, grand ?) dans l'ordre d'ajout — None : petit contrôle
        self._entries: list = []
        #: compact : grands boutons rendus petits, sur trois rangées (un long
        #: groupe, comme le Mode Point de TypeEdit, tient sans se replier)
        self.compact = False
        #: icônes seules : petits boutons sans libellé (la place manque)
        self.iconic = False
        #: petits boutons des rangées d'un formulaire (Mise en forme) : comme les autres petits boutons, libellés
        #: quand la place suffit, icônes seules sinon
        self.row_buttons: list = []
        self.labels = True
        #: rien à montrer (aucune de ses commandes n'est visible, ou le mode simple les cache toutes) : groupe caché
        self.vacant = False
        #: la page du groupe (posée par `RibbonPage.group`) : par elle, le ruban
        self.page = None
        #: rangement du mode simple en place : (éléments montrés, agrandis) ; None : la disposition expert
        self._arranged = None
        #: petits boutons montrés en grands par le mode simple (groupe qui n'en a qu'un ou deux)
        self._promoted: set = set()

    # --- famille repliée ----------------------------------------------------------------
    def buttons(self) -> list:
        """Boutons de commande du groupe, dans l'ordre (celui de la disposition expert, même rangé à nouveau)."""
        out = []
        for w, _big in self._entries:
            if isinstance(w, QToolButton) and w.defaultAction() is not None:
                out.append(w)
            else:                                         # une rangée de formulaire : ses boutons
                out += [b for b in w.findChildren(QToolButton) if b.defaultAction() is not None]
        known = {id(b) for b in out}
        return out + [b for b in self.body.findChildren(QToolButton)
                      if b.defaultAction() is not None and id(b) not in known]

    # --- boutons montrés ------------------------------------------------------------------
    def _ribbon(self):
        return getattr(self.page, 'ribbon', None)

    def refresh_visibility(self, allowed=None) -> bool:
        """Chaque bouton de commande montré si sa commande est visible et que `allowed(commande)` le permet (None :
        tout permis) ; `vacant` : le groupe n'a plus rien à montrer. Rend vrai s'il lui reste quelque chose."""
        cmds = self.buttons()
        states = {}
        for b in cmds:
            a = b.defaultAction()
            states[id(b)] = a.isVisible() and (allowed is None or bool(allowed(a)))
        shown = any(states.values())
        other = any(big is None and not (isinstance(w, QToolButton) and w.defaultAction() is not None)
                    for w, big in self._entries)             # un champ, une rangée de formulaire : toujours là
        arrangement = self._arrangement(allowed, states)
        if arrangement != self._arranged:                 # mode simple : rangé d'après ce qu'il montre
            self._arranged = arrangement
            self._relayout(arrangement)
        for b in cmds:
            on = states[id(b)]
            if b.isHidden() == on:
                b.setVisible(on)
        self.vacant = bool(cmds) and not shown and not other
        return not self.vacant

    @staticmethod
    def _is_command(w) -> bool:
        return isinstance(w, QToolButton) and w.defaultAction() is not None

    def _arrangement(self, allowed, states: dict):
        """Mode simple (`allowed`) : (indices des éléments montrés, agrandis ?) ; None : la disposition expert."""
        if allowed is None:
            return None
        keep = tuple(i for i, (w, _big) in enumerate(self._entries)
                     if not self._is_command(w) or states.get(id(w), False))
        cmds = [self._entries[i] for i in keep]
        promote = (not self.compact and 0 < len(cmds) <= 2 and all(self._is_command(w) and big is False
                                                                    for w, big in cmds))
        return keep, promote

    def _relayout(self, arrangement) -> None:
        """Les éléments du groupe rangés à nouveau : d'après la disposition expert (ordre, grands et petits), les
        petits montrés empilés sans trou et les cachés hors des colonnes (`arrangement`, mode simple), ou tous à leur
        place (None)."""
        keep, promote = arrangement if arrangement is not None else (None, False)
        hidden = {id(w): w.isHidden() for w, big in self._entries if not self._is_command(w)}
        for w, _big in self._entries:                   # sortis des colonnes avant de les défaire
            w.setParent(self.body)
        while self._row.count():
            item = self._row.takeAt(0)
            w = item.widget()
            if w is not None and all(w is not e for e, _b in self._entries):
                w.setParent(None)
                w.deleteLater()
        self._col = None
        self._promoted = set()
        for i, (w, big) in enumerate(self._entries):
            if keep is not None and i not in keep:
                continue                                 # caché : hors des colonnes (son bouton reste caché)
            command = self._is_command(w)
            if command and ((big and not self.compact) or promote):
                if not big:
                    self._promoted.add(id(w))
                w.setProperty('ribbon_big', True)
                style_button(w, True, self.labels)
                self._col = None
                self._row.addWidget(w)
            elif command and big is False and not self.compact and w.property('ribbon_slot'):
                style_button(w, False, self._small_labels())  # petit bouton inséré à sa place (`insert_after`)
                w.setProperty('ribbon_big', False)
                self._col = None
                self._row.addWidget(w)
            else:
                if command and big is not None:         # un bouton de machine (`add_widget`) garde son allure
                    w.setProperty('ribbon_big', False)
                    style_button(w, False, self._small_labels())
                self._stack(w)
            if not command:
                w.setVisible(not hidden.get(id(w), False))
        self.body.layout().invalidate()
        self.body.layout().activate()

    def _follow(self, b: QToolButton) -> None:
        """La commande d'un bouton a changé : s'il doit se montrer ou se cacher (commande propre à une machine), le
        ruban refait ses groupes et ses onglets."""
        try:
            a = b.defaultAction()
            if a is None:
                return
            ribbon = self._ribbon()
            allowed = ribbon.mode_filter if ribbon is not None else None
            on = a.isVisible() and (allowed is None or bool(allowed(a)))
            if b.isHidden() != on:
                return
            if ribbon is not None:
                ribbon.refresh_visibility()
            else:
                self.refresh_visibility(allowed)
        except RuntimeError:                              # bouton détruit
            pass

    def _family_look(self) -> None:
        """Icône de la famille : celle du premier grand bouton ; infobulle :
        les commandes qu'elle regroupe."""
        acts = [b.defaultAction() for b in self.buttons()]
        big = [b.defaultAction() for b in self.buttons() if b.property('ribbon_big')]
        icon = next((a.icon() for a in big + acts if not a.icon().isNull()), None)
        if icon is not None:
            self.family.setIcon(icon)
        self.family.setIconSize(QSize(BIG_ICON, BIG_ICON))
        names = [a.text().replace('&', '') for a in acts]
        self.family.setToolTip(self.title.text() + ('\n' + '\n'.join('• ' + n for n in names[:14]) if names else '')
                               + ('\n…' if len(names) > 14 else ''))

    def set_collapsed(self, on: bool) -> None:
        """Replie le groupe en famille (un bouton) ou le déplie."""
        on = bool(on)
        if on == self.collapsed:
            return
        self.collapsed = on
        if on:
            self.set_iconic(False)                       # barre déroulée : la place des libellés
            if self.popup is None:
                self.popup = FamilyPopup(self)
            self.popup.title.setVisible(self.captions)
            self._family_look()
            self.popup.hold(self.body)
            self.body.show()
            self.family.show()
            self.title.hide()
        else:
            if self.popup is not None:
                self.popup.hide()
            self._lay.insertWidget(0, self.body, 1)
            self.body.show()
            self.family.hide()
            self.title.setVisible(self.captions)

    def unroll(self) -> None:
        """Déroule la barre de la famille sous son bouton."""
        if self.collapsed and self.popup is not None:
            self.popup.show_under(self.family)

    def _command_clicked(self) -> None:
        if self.popup is not None and self.popup.isVisible():
            self.popup.hide()

    def expanded_width(self) -> int:
        m = self._lay.contentsMargins()
        return max(self.body.sizeHint().width(), self.title.sizeHint().width() if self.captions else 0) \
            + m.left() + m.right()

    def collapsed_width(self) -> int:
        m = self._lay.contentsMargins()
        return self.family.sizeHint().width() + m.left() + m.right()

    def _stack(self, w: QWidget) -> None:
        """Petit élément : dans la colonne en cours (trois au plus)."""
        if self._col is None or self._col.count() >= self.rows:
            holder = QWidget(self.body)
            self._col = QVBoxLayout(holder)
            self._col.setContentsMargins(0, 0, 0, 0)
            self._col.setSpacing(0)
            self._col.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            self._row.addWidget(holder)
        self._col.addWidget(w, 0, Qt.AlignmentFlag.AlignLeft)

    def add(self, action: QAction, *, big: bool = True) -> QToolButton:
        b = self._button(action, big)
        self._entries.append((b, big))
        if big and not self.compact:
            self._col = None
            self._row.addWidget(b)
        else:
            if big:
                b.setProperty('ribbon_big', False)
            style_button(b, False, self._small_labels())
            self._stack(b)
        return b

    def big_count(self) -> int:
        return sum(1 for _w, big in self._entries if big)

    def small_count(self) -> int:
        return sum(1 for _w, big in self._entries if big is False or (big and self.compact)) + len(self.row_buttons)

    def _small_labels(self) -> bool:
        return self.labels and not self.iconic

    def set_iconic(self, on: bool) -> None:
        """Petits boutons en icônes seules (le libellé en infobulle), ou avec
        leur libellé."""
        on = bool(on)
        if on == self.iconic:
            return
        self.iconic = on
        for w, big in self._entries:
            if (big is False or (big and self.compact)) and id(w) not in self._promoted:
                style_button(w, False, self._small_labels())
        for b in self.row_buttons:                      # rangées d'un formulaire
            style_button(b, False, self._small_labels())
            row = b.parentWidget()
            if row is not None and row.layout() is not None:
                row.layout().invalidate()
                row.updateGeometry()
        for i in range(self._row.count()):              # colonnes : tailles en cache oubliées tout de suite
            col = self._row.itemAt(i).widget()
            if col is not None and col.layout() is not None:
                col.layout().invalidate()
                col.updateGeometry()
        self.body.layout().invalidate()
        self.body.layout().activate()

    def set_compact(self, on: bool) -> None:
        """Grands boutons en petits, empilés par trois (ou l'inverse)."""
        on = bool(on)
        if on == self.compact or not self.big_count():
            return
        self.compact = on
        self._arranged, self._promoted = None, set()     # la disposition expert, refaite : le mode simple la reprend
        self._relayout(None)                             # une seule règle de rangement (petits boutons à leur place)
        for w, _big in self._entries:
            w.show()
        ribbon = self._ribbon()                          # les boutons viennent d'être remontrés : ceux à cacher le sont
        self.refresh_visibility(ribbon.mode_filter if ribbon is not None else None)
        self.body.layout().invalidate()
        self.body.layout().activate()

    def _button(self, action: QAction, big: bool) -> QToolButton:
        b = ViewSwitch(self.body) if action.property('vd_switch') else QToolButton(self.body)
        b.setDefaultAction(action)
        b.setAutoRaise(True)
        b.setProperty('ribbon_big', big)
        if action.menu() is not None:
            b.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        style_button(b, big, True)
        # Qt remet le texte de l'action à chaque changement : libellé recoupé après lui
        action.changed.connect(lambda b=b: _rewrap(b))
        action.changed.connect(lambda b=b: self._follow(b))        # commande cachée ou montrée : son bouton aussi
        b.triggered.connect(lambda _a: self._command_clicked())   # famille déroulée : refermée après la commande
        return b

    def add_widget(self, w: QWidget) -> None:
        """Petit contrôle (champ numérique…), empilé comme les petits boutons."""
        self._entries.append((w, None))
        self._stack(w)

    def insert_after(self, existing: QAction, action: QAction, *, big: bool = True) -> QToolButton | None:
        """Grand bouton juste après celui de `existing` (grand bouton de ce
        groupe) ; None si ce groupe n'a pas ce bouton."""
        for i in range(self._row.count()):
            w = self._row.itemAt(i).widget()
            if isinstance(w, QToolButton) and w.defaultAction() is existing:
                b = self._button(action, big)
                b.setProperty('ribbon_slot', True)        # à sa place, même petit : le mode simple la lui rend
                self._row.insertWidget(i + 1, b)
                k = next((j for j, (e, _b) in enumerate(self._entries) if e is w), len(self._entries) - 1)
                self._entries.insert(k + 1, (b, big))
                return b
        return None


def two_lines(text: str, fm) -> str:
    """Libellé d'un grand bouton coupé en deux lignes à l'espace qui rend la
    plus longue des deux la plus courte (tel quel : un seul mot, ou court)."""
    words = text.split(' ')
    if len(words) < 2 or fm.horizontalAdvance(text) <= max(52, 2 * BIG_ICON):
        return text
    best, cut = None, text
    for i in range(1, len(words)):
        a, b = ' '.join(words[:i]), ' '.join(words[i:])
        w = max(fm.horizontalAdvance(a), fm.horizontalAdvance(b))
        if best is None or w < best:
            best, cut = w, f'{a}\n{b}'
    return cut


def _rewrap(b: QToolButton) -> None:
    """Libellé d'un grand bouton recoupé (texte de l'action changé)."""
    try:
        if b.property('ribbon_big') and b.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextUnderIcon:
            style_button(b, True, True)
    except RuntimeError:                                  # bouton détruit
        pass


def style_button(b: QToolButton, big: bool, labels: bool) -> None:
    """Taille d'icône et libellé d'un bouton du ruban."""
    a = b.defaultAction()
    text = a.text() if a is not None else b.text().replace('\n', ' ')
    if big:
        b.setIconSize(QSize(BIG_ICON, BIG_ICON))
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon if labels
                             else Qt.ToolButtonStyle.ToolButtonIconOnly)
        shown = two_lines(text, b.fontMetrics()) if labels else text
        if b.text() != shown:
            b.setText(shown)
        width = max(b.fontMetrics().horizontalAdvance(line.replace('&', '')) for line in shown.split('\n'))
        b.setMinimumWidth(max(52, width + 12) if labels else 0)
    else:
        b.setIconSize(QSize(SMALL_ICON, SMALL_ICON))
        b.setMinimumWidth(0)                              # un grand bouton rendu petit (groupe compact)
        if a is not None and b.text() != a.text():
            b.setText(a.text())                           # une ligne : le libellé à côté de l'icône
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon if labels
                             else Qt.ToolButtonStyle.ToolButtonIconOnly)


class Ribbon(QTabWidget):
    #: le ruban vient d'être réduit (True) ou déplié (False) par l'utilisateur
    collapsedChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.collapsed = False
        self.custom_title = None            # titre du premier onglet à soi (« Mon onglet »)
        self.custom_titles: list = []       # titres des onglets à soi affichés
        self.custom_pages: list = []        # leurs pages (dans l'ordre des titres)
        self.custom_rank: list = []         # leur rang dans les réglages (ribbon_editor.load_all)
        self._peek = False
        self._page_h = 0
        self.labels = True
        self.captions = True
        #: repli des groupes en familles : 'place' (quand la place manque) ou 'toujours'
        self.families = 'place'
        #: mode simple : fonction(commande) → son bouton est-il montré ? None (mode expert) : tous
        self.mode_filter = None
        self._refreshing = False
        self.tabBarDoubleClicked.connect(lambda _i: self.toggle_collapsed())
        self.tabBarClicked.connect(self._tab_clicked)
        self.setDocumentMode(True)
        self.setMaximumHeight(118)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.info = QLabel('')
        self.info.setObjectName('ribbonInfo')
        self.info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        # onglets tout à droite (Options, Aide) : leur propre barre, dans le coin
        from PySide6.QtWidgets import QTabBar
        self.right_bar = QTabBar()
        self.right_bar.setObjectName('ribbonRightTabs')
        self.right_bar.setDocumentMode(True)
        self.right_bar.setDrawBase(False)
        self.right_bar.setExpanding(False)
        self.right_bar.tabBarClicked.connect(self._right_clicked)
        self.right_bar.tabBarDoubleClicked.connect(lambda _j: self.toggle_collapsed())
        self._right_pages: list[QWidget] = []
        self._right_visible: dict[int, bool] = {}
        self._syncing = False
        corner = QWidget()
        cl = QHBoxLayout(corner)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(12)
        cl.addWidget(self.info)
        cl.addWidget(self.right_bar, 0, Qt.AlignmentFlag.AlignBottom)
        self._corner_layout = cl
        self.setCornerWidget(corner, Qt.Corner.TopRightCorner)
        #: dernier onglet de gauche (FAO) : les onglets ajoutés ensuite se placent avant lui
        self.last_left: QWidget | None = None
        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.setInterval(0)
        self._fit_timer.timeout.connect(self.fit_current)
        self.currentChanged.connect(lambda _i: self._fit_timer.start())
        self.currentChanged.connect(lambda _i: self._sync_right())

    def add_tab(self, title: str) -> 'RibbonPage':
        """Page de ruban, à la fin des onglets de gauche (avant le dernier,
        FAO, s'il est fixé) ; ses groupes se replient en familles si la
        fenêtre est trop étroite (jamais de défilement horizontal)."""
        i = self.indexOf(self.last_left) if self.last_left is not None else -1
        return self.insert_tab(i if i >= 0 else self.count(), title)

    # --- onglets de droite ----------------------------------------------------------------
    def set_right(self, index: int, on: bool = True, rank: int = 0) -> None:
        """L'onglet `index` passe tout à droite (barre du coin, rangée par
        `rank` : Options 0, Aide 1) ou revient à gauche."""
        w = self.widget(index)
        if w is None:
            return
        vis = self.isTabVisible(index)
        w.setProperty('ribbon_right', bool(on))
        w.setProperty('ribbon_rank', int(rank))
        if on and w not in self._right_pages:
            self._right_pages.append(w)
            self._right_pages.sort(key=lambda p: int(p.property('ribbon_rank') or 0))
        elif not on and w in self._right_pages:
            self._right_pages.remove(w)
        self._right_visible[id(w)] = vis
        QTabWidget.setTabVisible(self, index, vis and not on)
        self._sync_right()

    def is_right(self, index: int) -> bool:
        w = self.widget(index)
        return w is not None and bool(w.property('ribbon_right'))

    def setTabVisible(self, index: int, visible: bool) -> None:          # noqa: N802 (API Qt)
        w = self.widget(index)
        if w is not None:                                # ce qui est demandé est retenu : un onglet sans rien à
            w.setProperty('ribbon_wanted', bool(visible))        # montrer (mode simple) reste caché, et revient avec
            visible = bool(visible) and not w.property('ribbon_vacant')     # ses boutons
        self._show_tab(index, visible)

    def _show_tab(self, index: int, visible: bool) -> None:
        if self.is_right(index):
            self._right_visible[id(self.widget(index))] = bool(visible)
            if not visible and self.currentIndex() == index:
                vis = [i for i in range(self.count()) if self.isTabVisible(i) and i != index]
                if vis:
                    self.setCurrentIndex(vis[0])
            self._sync_right()
            return
        super().setTabVisible(index, visible)

    def isTabVisible(self, index: int) -> bool:                          # noqa: N802 (API Qt)
        if self.is_right(index):
            return self._right_visible.get(id(self.widget(index)), True)
        return super().isTabVisible(index)

    def setTabText(self, index: int, text: str) -> None:                 # noqa: N802 (API Qt)
        super().setTabText(index, text)
        if self.is_right(index):
            self._sync_right()

    def tabRemoved(self, index: int) -> None:                            # noqa: N802 (API Qt)
        super().tabRemoved(index)
        self._right_pages = [w for w in self._right_pages if self.indexOf(w) >= 0]
        self._sync_right()

    def tabInserted(self, index: int) -> None:                           # noqa: N802 (API Qt)
        super().tabInserted(index)
        if self._right_pages:
            self._sync_right()                               # indices décalés

    def right_titles(self) -> list[str]:
        """Onglets de droite visibles, dans l'ordre."""
        return [self.tabText(self.indexOf(w)) for w in self._right_pages
                if self.indexOf(w) >= 0 and self._right_visible.get(id(w), True)]

    def _sync_right(self) -> None:
        """Barre de droite refaite d'après les pages marquées ; onglet choisi
        si la page affichée en est une (sinon aucun : onglet caché d'appui)."""
        if self._syncing:
            return
        self._syncing = True
        try:
            bar = self.right_bar
            bar.blockSignals(True)
            while bar.count():
                bar.removeTab(0)
            bar.addTab('')                                    # appui caché : aucun onglet de droite choisi
            bar.setTabVisible(0, False)
            cur = self.currentWidget()
            sel = 0
            for w in self._right_pages:
                i = self.indexOf(w)
                if i < 0:
                    continue
                j = bar.addTab(self.tabText(i))
                bar.setTabData(j, i)
                bar.setTabVisible(j, self._right_visible.get(id(w), True))
                if w is cur:
                    sel = j
            bar.setCurrentIndex(sel)
            bar.setVisible(bar.count() > 1 and any(bar.isTabVisible(j) for j in range(1, bar.count())))
            bar.blockSignals(False)
        finally:
            self._syncing = False

    def _right_clicked(self, j: int) -> None:
        i = self.right_bar.tabData(j)
        if i is None or not 0 <= int(i) < self.count():
            return
        i = int(i)
        self._tab_clicked(i)
        self.setCurrentIndex(i)
        self._sync_right()

    # --- familles -------------------------------------------------------------------------
    def page(self, i: int) -> 'RibbonPage | None':
        sc = self.widget(i)
        p = sc.widget() if isinstance(sc, QScrollArea) else None
        return p if isinstance(p, RibbonPage) else None

    def set_mode_filter(self, allowed) -> None:
        """Le mode du ruban : `allowed(commande)` dit si son bouton est montré (mode simple) ; None : tous (expert)."""
        self.mode_filter = allowed
        self.refresh_visibility()

    def refresh_visibility(self) -> None:
        """Chaque bouton montré si sa commande est visible et que le mode le permet ; un groupe sans bouton à montrer
        est caché ; un onglet sans groupe à montrer aussi — il revient avec eux, s'il était demandé."""
        if self._refreshing:
            return
        self._refreshing = True
        try:
            for i in range(self.count()):
                page = self.page(i)
                if page is None:
                    continue
                w = self.widget(i)
                has = page.refresh_visibility(self.mode_filter)
                was_vacant = bool(w.property('ribbon_vacant'))
                if has != was_vacant:
                    continue
                wanted = w.property('ribbon_wanted')
                if wanted is None:
                    wanted = True if was_vacant else self.isTabVisible(i)
                    w.setProperty('ribbon_wanted', bool(wanted))
                w.setProperty('ribbon_vacant', not has)
                self._show_tab(i, bool(wanted) and has)
        finally:
            self._refreshing = False
        self.fit_current()

    def set_mode_button(self, action) -> None:
        """Le va-et-vient Simple / Expert : dans la rangée des onglets, à côté de celui du 2D / 3D."""
        b = ViewSwitch(self.cornerWidget(Qt.Corner.TopRightCorner))
        b.setObjectName('ribbonModeButton')
        b.setAutoRaise(True)
        b.setDefaultAction(action)
        view = getattr(self, 'view_button', None)
        at = self._corner_layout.indexOf(view) + 1 if view is not None else self._corner_layout.indexOf(self.info)
        self._corner_layout.insertWidget(at, b, 0, Qt.AlignmentFlag.AlignBottom)
        self.mode_button = b

    def set_column_buttons(self, left, right) -> None:
        """Les deux boutons qui montrent ou cachent la colonne de panneaux de gauche et celle de droite : dans la
        rangée des onglets, après Simple / Expert."""
        box = QWidget(self.cornerWidget(Qt.Corner.TopRightCorner))
        box.setObjectName('ribbonColumnButtons')
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.column_buttons = []
        for action in (left, right):
            b = QToolButton(box)
            b.setAutoRaise(True)
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            b.setDefaultAction(action)
            lay.addWidget(b)
            self.column_buttons.append(b)
        mode = getattr(self, 'mode_button', None)
        at = self._corner_layout.indexOf(mode) + 1 if mode is not None else self._corner_layout.indexOf(self.info)
        self._corner_layout.insertWidget(at, box, 0, Qt.AlignmentFlag.AlignBottom)

    #: boutons de fenêtre, de gauche à droite
    WINDOW_BUTTONS = ('ribbonWindowMinimize', 'ribbonWindowRestore', 'ribbonWindowClose')

    def set_window_buttons(self, minimize, restore, close) -> None:
        """Réduire, Fenêtre, Fermer : tout à droite de la rangée des onglets, pour une fenêtre sans barre de titre
        (plein écran). Cachés tant qu'on ne les montre pas (`show_window_buttons`)."""
        box = QWidget(self.cornerWidget(Qt.Corner.TopRightCorner))
        box.setObjectName('ribbonWindowButtons')
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        for action, name in zip((minimize, restore, close), self.WINDOW_BUTTONS):
            b = QToolButton(box)
            b.setObjectName(name)
            b.setAutoRaise(True)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            b.setDefaultAction(action)
            b.setFixedSize(40, 24)
            lay.addWidget(b)
        box.setStyleSheet('QToolButton#ribbonWindowClose:hover { background: #e81123; color: white; }')
        self._corner_layout.addWidget(box, 0, Qt.AlignmentFlag.AlignTop)
        box.hide()
        self.window_buttons = box

    def show_window_buttons(self, on: bool) -> None:
        box = getattr(self, 'window_buttons', None)
        if box is not None:
            box.setVisible(bool(on))

    def set_view_button(self, action) -> None:
        """Le bouton va-et-vient 2D / 3D : dans la rangée des onglets, visible quel que soit l'onglet choisi."""
        b = ViewSwitch(self.cornerWidget(Qt.Corner.TopRightCorner))
        b.setObjectName('ribbonViewButton')
        b.setAutoRaise(True)
        b.setDefaultAction(action)
        self._corner_layout.insertWidget(self._corner_layout.indexOf(self.info), b, 0, Qt.AlignmentFlag.AlignBottom)
        self.view_button = b

    def set_doc_bar(self, widget: QWidget) -> None:
        """Barre des onglets de dessins : dans la rangée des onglets, entre le
        dernier onglet de gauche (FAO) et ceux de droite (Options, Aide)."""
        widget.setParent(self.cornerWidget(Qt.Corner.TopRightCorner))
        self._corner_layout.insertWidget(0, widget, 0, Qt.AlignmentFlag.AlignBottom)
        widget.show()

    def fit_current(self) -> None:
        """Groupes de l'onglet affiché repliés en familles ce qu'il faut pour
        tenir dans la largeur (tous, avec l'option « toujours »)."""
        i = self.currentIndex()
        p = self.page(i) if i >= 0 else None
        if p is None:
            return
        sc = self.widget(i)
        avail = sc.viewport().width() if sc.viewport().width() > 40 else self.width() - 4
        p.fit(avail, always=self.families == 'toujours')

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        self._fit_timer.start()

    def showEvent(self, ev) -> None:
        super().showEvent(ev)
        self._fit_timer.start()

    def insert_tab(self, index: int, title: str) -> 'RibbonPage':
        page = RibbonPage()
        page.ribbon = self
        scroll = QScrollArea()
        scroll.setWidget(page)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.horizontalScrollBar().setFixedHeight(6)              # seulement si tout replie ne tient pas
        self.insertTab(index, scroll, title)
        return page

    def finalize(self) -> None:
        """À appeler une fois les pages remplies : hauteur commune calée sur
        la page la plus haute (groupes dépliés), puis groupes repliés en
        familles selon la largeur."""
        pages = [self.widget(i) for i in range(self.count())]
        for g in self.findChildren(RibbonGroup):
            g.captions = self.captions
            g.labels = self.labels
            g.set_collapsed(False)                           # hauteur mesurée groupes dépliés
            g.set_compact(False)
            g.title.setVisible(self.captions)
        for sc in pages:
            lay = sc.widget().layout()
            lay.invalidate()
            lay.activate()
        for sc in pages:
            sc.widget().setMinimumHeight(0)
            sc.widget().setMaximumHeight(16777215)
        h = max(sc.widget().sizeHint().height() for sc in pages)
        for sc in pages:
            # la page garde sa hauteur : étirée à celle de la zone, son bas (les
            # légendes des groupes) passerait sous la barre de défilement
            sc.widget().setFixedHeight(h)
            sc.setFixedHeight(h + SCROLL_H + 3)
        self._page_h = h
        self.setMaximumHeight(16777215)
        for b in self.findChildren(QToolButton):
            if b.property('ribbon_big') is not None and not b.property('ribbon_hooked'):
                b.setProperty('ribbon_hooked', True)
                b.clicked.connect(self._command_done)
        self._apply_height()
        self.refresh_visibility()                        # ruban refait : boutons, groupes et onglets selon le mode

    def configure(self, *, big: int = 28, small: int = 16, labels: bool = True, captions: bool = True,
                  families: str | None = None) -> None:
        """Taille des icônes, libellés sous les boutons, légendes des groupes,
        repli en familles ('place' ou 'toujours')."""
        global BIG_ICON, SMALL_ICON
        BIG_ICON, SMALL_ICON = int(big), int(small)
        self.labels = labels
        self.captions = bool(captions)
        if families in FAMILIES:
            self.families = families
        for b in self.findChildren(QToolButton):
            kind = b.property('ribbon_big')
            if kind is not None:
                style_button(b, bool(kind), labels)
            elif b.property('ribbon_family'):
                b.setIconSize(QSize(BIG_ICON, BIG_ICON))
        if self.count():
            self.finalize()

    # --- ruban réduit ------------------------------------------------------------------
    def set_collapsed(self, on: bool) -> None:
        self.collapsed, self._peek = bool(on), False
        self._apply_height()

    def toggle_collapsed(self) -> None:
        self.set_collapsed(not self.collapsed)
        self.collapsedChanged.emit(self.collapsed)

    def _tab_clicked(self, i: int) -> None:
        if self.collapsed:
            self._peek = not (self._peek and i == self.currentIndex())
            self._apply_height()

    def _command_done(self) -> None:
        if self.collapsed and self._peek:
            self._peek = False
            self._apply_height()

    def _apply_height(self) -> None:
        tb = self.tabBar().sizeHint().height()
        if self.collapsed and not self._peek:
            self.setFixedHeight(tb + 2)
        elif self._page_h:
            # hauteur calculée par Qt (barre d'onglets, cadre, page) : le style
            # des onglets (thème, densité) change la hauteur de la barre
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)
            self.setFixedHeight(max(self.sizeHint().height(), tb + self._page_h + SCROLL_H + 5))


class RibbonPage(QWidget):
    def __init__(self):
        super().__init__()
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(2, 2, 2, 2)
        self._lay.setSpacing(0)
        self._lay.addStretch(1)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)

    def group(self, title: str, *, at_start: bool = False) -> RibbonGroup:
        """Nouveau groupe, à la fin de la page (ou au début, `at_start`)."""
        g = RibbonGroup(title)
        g.page = self
        sep = None
        if self._lay.count() > 1:
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.VLine)
            sep.setFrameShadow(QFrame.Shadow.Sunken)
        if at_start:
            self._lay.insertWidget(0, g)
            if sep is not None:
                self._lay.insertWidget(1, sep)
            return g
        if sep is not None:
            self._lay.insertWidget(self._lay.count() - 1, sep)
        self._lay.insertWidget(self._lay.count() - 1, g)
        return g

    def groups(self) -> list[RibbonGroup]:
        return [w for w in (self._lay.itemAt(i).widget() for i in range(self._lay.count()))
                if isinstance(w, RibbonGroup)]

    def remove_group(self, g: RibbonGroup) -> None:
        """Retire le groupe `g` et son séparateur."""
        i = self._lay.indexOf(g)
        if i < 0:
            return
        j = i - 1 if i > 0 else i + 1
        item = self._lay.itemAt(j)
        sep = item.widget() if item is not None else None
        for w in (g, sep if isinstance(sep, QFrame) and not isinstance(sep, RibbonGroup) else None):
            if w is not None:
                self._lay.removeWidget(w)
                w.setParent(None)
                w.deleteLater()

    def refresh_visibility(self, allowed=None) -> bool:
        """Les boutons de chaque groupe montrés selon leur commande et `allowed` ; un groupe sans rien à montrer est
        caché, avec son séparateur. Rend vrai si la page a encore quelque chose à montrer (une page sans groupe :
        toujours)."""
        ws = [self._lay.itemAt(i).widget() for i in range(self._lay.count())]

        def is_sep(w) -> bool:
            return isinstance(w, QFrame) and not isinstance(w, RibbonGroup)
        some, groups = False, 0
        for i, w in enumerate(ws):
            if not isinstance(w, RibbonGroup):
                continue
            groups += 1
            on = w.refresh_visibility(allowed)
            some = some or on
            if w.isHidden() == on:
                w.setVisible(on)
            sep = ws[i - 1] if i > 0 and is_sep(ws[i - 1]) else (ws[i + 1] if i + 1 < len(ws) and is_sep(ws[i + 1])
                                                                 else None)
            if sep is not None and sep.isHidden() == on:
                sep.setVisible(on)
        return some or not groups

    def fit(self, avail: int, *, always: bool = False) -> list[RibbonGroup]:
        """Replie en familles, de la droite vers la gauche, les groupes qu'il
        faut pour que la page tienne dans `avail` pixels (tous avec
        `always`) ; rend les groupes repliés."""
        gs = [g for g in self.groups() if not g.vacant]  # un groupe sans rien à montrer est caché : il ne compte pas
        if not gs:
            return []
        if always:
            want = [len(g.buttons()) > 0 for g in gs]
        else:
            m = self._lay.contentsMargins()
            fixed = m.left() + m.right() + sum(
                w.sizeHint().width() for w in (self._lay.itemAt(i).widget() for i in range(self._lay.count()))
                if w is not None and not isinstance(w, RibbonGroup) and not w.isHidden())
            for g in gs:                                 # largeur pleine d'abord
                g.set_compact(False)
                g.set_iconic(False)
            exp = [g.expanded_width() for g in gs]
            total = fixed + sum(exp)
            # petits boutons en icônes seules, du groupe le plus large au plus étroit
            for i in sorted(range(len(gs)), key=lambda k: -exp[k]):
                if total <= avail - 2:
                    break
                if gs[i].small_count():
                    gs[i].set_iconic(True)
                    w = gs[i].expanded_width()
                    total -= exp[i] - w
                    exp[i] = w
            # un long groupe (beaucoup de grands boutons) trop large : petits
            # boutons sur trois rangées, avant tout repli en famille
            for i in sorted(range(len(gs)), key=lambda k: -exp[k]):
                if total <= avail - 2:
                    break
                if gs[i].big_count() >= 6:
                    gs[i].set_compact(True)
                    w = gs[i].expanded_width()
                    if w < exp[i]:
                        total -= exp[i] - w
                        exp[i] = w
                    else:
                        gs[i].set_compact(False)
            col = [g.collapsed_width() for g in gs]
            want = [False] * len(gs)
            for i in range(len(gs) - 1, -1, -1):
                if total <= avail - 2:
                    break
                if col[i] < exp[i] and gs[i].buttons():
                    want[i] = True
                    total -= exp[i] - col[i]
            for i in range(len(gs)):                     # place rendue par un grand groupe replié
                if want[i] and total + exp[i] - col[i] <= avail - 2:
                    want[i] = False
                    total += exp[i] - col[i]
            for i in range(len(gs)):                     # place restée : libellés rendus, de gauche à droite
                if want[i] or not gs[i].iconic:
                    continue
                gs[i].set_iconic(False)
                w = gs[i].expanded_width()
                if total + w - exp[i] <= avail - 2:
                    total += w - exp[i]
                    exp[i] = w
                else:
                    gs[i].set_iconic(True)
        self.setUpdatesEnabled(False)
        try:
            for g, w in zip(gs, want):
                g.set_collapsed(w)
        finally:
            self.setUpdatesEnabled(True)
        self._lay.invalidate()
        return [g for g, w in zip(gs, want) if w]
