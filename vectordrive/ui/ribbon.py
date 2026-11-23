"""Ruban façon TypeEdit : onglets et groupes d'icônes titrés (la sélection :
dans la barre d'état, au pied de la fenêtre). Réglable (F10 >
Apparence) : taille des icônes, libellés, légendes des groupes ; réduit
aux onglets par son petit bouton ˄ / ˅ au bout de la rangée des onglets (ou
Ctrl+F1), et par lui seul.

Quand la fenêtre est trop étroite pour un onglet, ses petits boutons
perdent d'abord leur libellé (icône seule, le nom en infobulle), du groupe le
plus large au plus étroit, puis les longs groupes passent sur trois rangées ;
s'il ne tient toujours pas, l'onglet défile de côté (la molette sur la page, la
petite barre sous elle). Jamais de groupe replié en un bouton qui déroule une
barre flottante (round 1094 : au clic gauche, elle passait pour un menu du clic
droit). Les libellés des grands boutons passent sur deux lignes (comme
TypeEdit) : un onglet tient en Full HD, et s'étale tout entier sur un écran
plus large."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QFont, QFontMetrics, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy,
                               QTabWidget, QToolButton, QVBoxLayout, QWidget)

SMALL_ROWS = 3          # petits boutons empilés par colonnes de trois, comme dans TypeEdit
#: taille des icônes (grands et petits boutons) ; voir Ribbon.configure
BIG_ICON = 28
SMALL_ICON = 16
#: tailles proposées dans les options
ICON_SIZES = {'petites': (22, 16), 'normales': (28, 16), 'grandes': (36, 20)}


class RibbonScroll(QScrollArea):
    """La zone d'une page du ruban : quand l'onglet ne tient pas en largeur, la molette (n'importe où sur la page)
    le fait défiler de côté."""

    def wheelEvent(self, ev) -> None:                    # noqa: N802 (API Qt)
        bar = self.horizontalScrollBar()
        d = ev.angleDelta()
        step = d.x() if abs(d.x()) > abs(d.y()) else d.y()
        if bar.maximum() > 0 and step:
            bar.setValue(bar.value() - step)
            ev.accept()
            return
        ev.ignore()


class _WheelGuard(QObject):
    """Un champ du ruban (nombre, liste) sans le focus laisse la molette à l'onglet, qui défile : passer dessus en
    faisant défiler ne change pas sa valeur ; cliqué (le focus), il la prend comme avant."""

    def eventFilter(self, obj, ev):                      # noqa: N802 (API Qt)
        if ev.type() == QEvent.Type.Wheel and isinstance(obj, QWidget) and not obj.hasFocus():
            p = obj.parentWidget()
            while p is not None and not isinstance(p, RibbonScroll):
                p = p.parentWidget()
            if p is not None:
                p.wheelEvent(ev)
                return True
        return False


_GUARD: list = []


def _guard_wheel(root: QWidget) -> None:
    """Les champs (nombres, listes) sous `root` : la molette sans le focus fait défiler l'onglet."""
    from PySide6.QtWidgets import QAbstractSpinBox, QComboBox
    if not _GUARD:
        _GUARD.append(_WheelGuard())
    for w in root.findChildren(QAbstractSpinBox) + root.findChildren(QComboBox):
        if not w.property('ribbon_wheel'):
            w.setProperty('ribbon_wheel', True)
            w.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # la molette seule ne lui donne plus le focus
            w.installEventFilter(_GUARD[0])


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
        #: contenu du groupe (ses boutons)
        self.body = QWidget(self)
        self._row = QHBoxLayout(self.body)
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(1)
        lay.addWidget(self.body, 1)
        lab = QLabel(title)
        lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lab.setObjectName('ribbonGroupTitle')
        lab.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)   # la place en trop va aux boutons
        lay.addWidget(lab, 0, Qt.AlignmentFlag.AlignBottom)
        self.title = lab
        self._col: QVBoxLayout | None = None
        #: petits éléments par colonne (le formulaire de Mise en forme : deux rangées, comme le Rapido de TypeEdit)
        self.rows = SMALL_ROWS
        self.captions = True
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
        #: (élément, grand ?) dans l'ordre où le groupe a été bâti : la taille et la place choisies au clic droit
        #: (round 1141) partent toujours de lui, et le rétablissent
        self._origin: list = []
        #: identifiant stable du groupe (posé par la fenêtre) : la clé de ses réglages de boutons
        self.group_id = None

    # --- boutons ----------------------------------------------------------------------------
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
        # tous ses boutons déplacés ailleurs (round 1141) : vide, caché aussi
        self.vacant = (bool(cmds) and not shown and not other) or (not self._entries and bool(self._origin))
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

    def expanded_width(self) -> int:
        m = self._lay.contentsMargins()
        return max(self.body.sizeHint().width(), self.title.sizeHint().width() if self.captions else 0) \
            + m.left() + m.right()

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
        self._origin.append((b, big))
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
        return b

    def add_widget(self, w: QWidget) -> None:
        """Petit contrôle (champ numérique…), empilé comme les petits boutons."""
        self._entries.append((w, None))
        self._origin.append((w, None))
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
                k = next((j for j, (e, _b) in enumerate(self._origin) if e is w), len(self._origin) - 1)
                self._origin.insert(k + 1, (b, big))
                return b
        return None

    def entry_of(self, w) -> int:
        """Rang de `w` parmi les éléments du groupe (-1 : pas un des siens, ou dans une rangée de formulaire)."""
        return next((i for i, (e, _b) in enumerate(self._entries) if e is w), -1)

    def entry_big(self, w):
        """Grand bouton (True), petit (False), ou petit contrôle sans taille au choix (None) ; None s'il n'est pas là."""
        i = self.entry_of(w)
        return self._entries[i][1] if i >= 0 else None


# --- taille et place des boutons choisies au clic droit (round 1141) ------------------------------------------------
def _layout_of(g) -> str:
    """La disposition d'un groupe d'après son identifiant (« vd », « te ») : les boutons ne passent pas de l'une à
    l'autre."""
    gid = str(g.group_id or '')
    return gid.split(':', 1)[0] if ':' in gid else ''


def plan_layout(groups, conf: dict, ident) -> dict:
    """Les éléments de chaque groupe d'après l'ordre d'origine (`_origin`) et les réglages `conf` : {identifiant du
    groupe: [[identifiant du bouton, grand ?], …]} (l'ordre choisi des boutons du groupe). Un bouton listé dans un autre
    groupe que le sien, et plus dans le sien, y est déplacé ; un bouton absent des listes (nouveau, ou rétabli) garde
    sa place d'origine, juste après le bouton qui le précédait. `ident(bouton)` : son identifiant (None : il ne bouge
    pas). Rend {groupe: [(élément, grand)]}."""
    groups = list(groups)
    ids = {}
    own = {}                                             # groupe → {identifiant: (bouton, grand)} de son origine
    for g in groups:
        mine = {}
        for w, big in g._origin:
            k = ident(w) if RibbonGroup._is_command(w) else None
            ids[id(w)] = k
            if k and k not in mine:
                mine[k] = (w, big)
        own[g] = mine
    listed, noted = {}, {}
    for g in groups:
        items = [(str(k), b) for k, b in (conf.get(g.group_id) or [])] if g.group_id else []
        # une liste qui ne nomme aucun bouton d'origine de son onglet n'est pas la sienne (identifiant d'un groupe qui
        # a changé : plugin ôté, nouvelle version) : ignorée — une liste vide (tous partis ailleurs) reste la sienne
        page_ids = {k for h in groups if h.page is g.page for k in own[h]}
        if items and not any(k in page_ids for k, _b in items):
            items = []
            noted[g] = False
        else:
            noted[g] = bool(g.group_id) and g.group_id in conf
        listed[g] = items
    moved = {}                                           # (groupe quitté, identifiant) → groupe où il est déplacé
    for g in groups:
        for k, _b in listed[g]:
            if k in own[g]:
                continue
            # il vient d'un groupe du même onglet qui l'a d'origine et ne le liste plus (une même commande peut être
            # dans deux groupes : seul l'exemplaire quitté part) ; sans lui, il reste chez lui
            # (et de la même disposition : les groupes de TypeEdit 13 posés sur la page Fichier partent avec elle)
            src = next((h for h in groups if h.page is g.page and _layout_of(h) == _layout_of(g) and k in own[h]
                        and noted[h] and (h, k) not in moved and all(x != k for x, _b in listed[h])), None)
            if src is not None and all(not (t is g and kk == k) for (_h, kk), t in moved.items()):
                moved[(src, k)] = g
    plan = {}
    for g in groups:
        incoming = {k: src for (src, k), t in moved.items() if t is g}
        rank, size = {}, {}
        for i, (k, b) in enumerate(listed[g]):
            if k in rank or not (k in own[g] or k in incoming):
                continue
            rank[k], size[k] = i, bool(b)
        ents = [(w, big) for w, big in g._origin
                if not ((g, ids.get(id(w))) in moved and own[g][ids[id(w)]][0] is w)]
        for k in sorted(incoming, key=lambda k: rank.get(k, 1 << 30)):
            w, big = own[incoming[k]][k]
            ents.append((w, big))
        ents = [(w, size[ids.get(id(w))] if big is not None and ids.get(id(w)) in size else big) for w, big in ents]
        slots = [i for i, (w, _b) in enumerate(ents) if ids.get(id(w))]
        keyed, last = [], -1
        for seq, i in enumerate(slots):
            k = ids[id(ents[i][0])]
            if k in rank:
                last = rank[k]
                keyed.append(((rank[k], 0, seq), ents[i]))
            else:                                        # pas listé : juste après celui qui le précédait
                keyed.append(((last, 1, seq), ents[i]))
        keyed.sort(key=lambda t: t[0])
        for i, (_key, e) in zip(slots, keyed):
            ents[i] = e
        plan[g] = ents
    return plan


def rearrange(plan: dict) -> list:
    """Chaque groupe de `plan` ({groupe: [(élément, grand)]}) rangé ainsi, s'il change : les éléments pris d'abord par
    leur groupe (un bouton déplacé quitte l'autre), puis les groupes refaits (disposition expert ; le mode simple et
    les boutons à cacher, ensuite par `Ribbon.refresh_visibility`). Rend les groupes changés."""
    changed = [g for g, ents in plan.items()
               if [(id(w), b) for w, b in ents] != [(id(w), b) for w, b in g._entries]]
    for g in changed:
        g._entries = list(plan[g])
        for w, _b in g._entries:
            if not g.body.isAncestorOf(w):               # venu d'un autre groupe
                w.setParent(g.body)
    for g in changed:
        g._arranged, g._promoted = None, set()
        g._relayout(None)
        for w, _b in g._entries:
            if g._is_command(w):
                w.show()                                 # le ruban recache ceux à cacher
    return changed


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
        #: place réservée sous les pages à la barre de défilement (sa hauteur quand l'onglet affiché déborde, sinon 0)
        self._bar = 0
        #: mode simple : fonction(commande) → son bouton est-il montré ? None (mode expert) : tous
        self.mode_filter = None
        self._refreshing = False
        self.tabBarClicked.connect(self._tab_clicked)    # (plus de pliage au double clic : le bouton seul, 18/11 soir)
        self.setDocumentMode(True)
        self.setMaximumHeight(118)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.info = QLabel('')
        self.info.setObjectName('ribbonInfo')
        self.info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.info.hide()                                 # la sélection : dans la barre d'état seule (18/11 soir)
        # onglets tout à droite (Options, Aide) : leur propre barre, dans le coin
        from PySide6.QtWidgets import QTabBar
        self.right_bar = QTabBar()
        self.right_bar.setObjectName('ribbonRightTabs')
        self.right_bar.setDocumentMode(True)
        self.right_bar.setDrawBase(False)
        self.right_bar.setExpanding(False)
        self.right_bar.tabBarClicked.connect(self._right_clicked)
        self._right_pages: list[QWidget] = []
        self._right_visible: dict[int, bool] = {}
        self._syncing = False
        corner = QWidget()
        cl = QHBoxLayout(corner)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(12)
        cl.addWidget(self.info)
        cl.addWidget(self.right_bar, 0, Qt.AlignmentFlag.AlignBottom)
        # plier / déplier le ruban : ce petit bouton seul (demande du 18/11 soir : « bouton plier/replier discret seul
        # acteur ») — et Ctrl+F1, la commande « Réduire le ruban »
        from ..i18n import tr
        self.fold_btn = QToolButton()
        self.fold_btn.setObjectName('ribbonFold')
        self.fold_btn.setAutoRaise(True)
        self.fold_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.fold_btn.setText('˄')
        self.fold_btn.setToolTip(tr('Plier le ruban (Ctrl+F1)'))
        self.fold_btn.clicked.connect(lambda: self.toggle_collapsed())
        cl.addWidget(self.fold_btn, 0, Qt.AlignmentFlag.AlignBottom)
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
        FAO, s'il est fixé) ; trop étroite pour la fenêtre, elle défile de
        côté."""
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

    # --- pages ------------------------------------------------------------------------------
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
        """L'onglet affiché ajusté à la largeur (libellés, rangées) ; s'il ne tient toujours pas, il défile de côté
        et la petite barre a sa place sous lui. Jamais de groupe replié en un bouton à barre déroulée (round 1094)."""
        i = self.currentIndex()
        p = self.page(i) if i >= 0 else None
        if p is None:
            return
        sc = self.widget(i)
        avail = sc.width() if sc.width() > 40 else self.width() - 4
        p.fit(avail)
        p.layout().activate()
        self._set_bar(sc.horizontalScrollBar().sizeHint().height() if p.sizeHint().width() > avail else 0)

    def _set_bar(self, bar: int) -> None:
        """La barre de défilement sous les pages : montrée, et sa place prise (les légendes des groupes restent
        visibles), seulement quand l'onglet affiché déborde."""
        pol = Qt.ScrollBarPolicy.ScrollBarAsNeeded if bar else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        for k in range(self.count()):
            sc = self.widget(k)
            if isinstance(sc, QScrollArea):
                sc.setHorizontalScrollBarPolicy(pol)
                if self._page_h:
                    sc.setFixedHeight(self._page_h + bar + 3)
        if bar != self._bar:
            self._bar = bar
            self._apply_height()

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        self._fit_timer.start()

    def showEvent(self, ev) -> None:
        super().showEvent(ev)
        self._fit_timer.start()

    def insert_tab(self, index: int, title: str) -> 'RibbonPage':
        page = RibbonPage()
        page.ribbon = self
        scroll = RibbonScroll()
        scroll.setWidget(page)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # la barre : seulement quand l'onglet affiché déborde (`_set_bar`) ; la molette le fait défiler aussi
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded if self._bar
                                            else Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.insertTab(index, scroll, title)
        return page

    def finalize(self) -> None:
        """À appeler une fois les pages remplies : hauteur commune calée sur
        la page la plus haute, puis l'onglet affiché ajusté à la largeur."""
        pages = [self.widget(i) for i in range(self.count())]
        for g in self.findChildren(RibbonGroup):
            g.captions = self.captions
            g.labels = self.labels
            g.set_compact(False)                             # hauteur mesurée grands boutons
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
            sc.setFixedHeight(h + self._bar + 3)
        self._page_h = h
        self.setMaximumHeight(16777215)
        for b in self.findChildren(QToolButton):
            if b.property('ribbon_big') is not None and not b.property('ribbon_hooked'):
                b.setProperty('ribbon_hooked', True)
                b.clicked.connect(self._command_done)
        for sc in pages:                                 # la molette sur un champ sans le focus : l'onglet défile
            _guard_wheel(sc.widget())
        self._apply_height()
        self.refresh_visibility()                        # ruban refait : boutons, groupes et onglets selon le mode

    def configure(self, *, big: int = 28, small: int = 16, labels: bool = True, captions: bool = True) -> None:
        """Taille des icônes, libellés sous les boutons, légendes des groupes."""
        global BIG_ICON, SMALL_ICON
        BIG_ICON, SMALL_ICON = int(big), int(small)
        self.labels = labels
        self.captions = bool(captions)
        for b in self.findChildren(QToolButton):
            kind = b.property('ribbon_big')
            if kind is not None:
                style_button(b, bool(kind), labels)
        if self.count():
            self.finalize()

    # --- ruban réduit ------------------------------------------------------------------
    def set_collapsed(self, on: bool) -> None:
        self.collapsed, self._peek = bool(on), False
        b = getattr(self, 'fold_btn', None)
        if b is not None:
            from ..i18n import tr
            b.setText('˅' if self.collapsed else '˄')
            b.setToolTip(tr('Déplier le ruban (Ctrl+F1)') if self.collapsed else tr('Plier le ruban (Ctrl+F1)'))
            b.setAutoRaise(not self.collapsed)           # plié : un vrai bouton, qu'on voit (seul moyen de déplier)
        self._apply_height()

    def toggle_collapsed(self) -> None:
        self.set_collapsed(not self.collapsed)
        self.collapsedChanged.emit(self.collapsed)

    def _tab_clicked(self, i: int) -> None:
        """Un clic sur un onglet : sa page (le ruban plié le reste — seul son bouton le déplie ; il ne s'ouvrait le temps
        d'une commande que pour se refermer seul)."""
        return None

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
            self.setFixedHeight(max(self.sizeHint().height(), tb + self._page_h + self._bar + 5))


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

    def fit(self, avail: int) -> bool:
        """La page ajustée à `avail` pixels : petits boutons en icônes seules, du groupe le plus large au plus étroit,
        puis les longs groupes sur trois rangées ; la place restée rend les libellés. Aucun groupe replié (round
        1094) : rend vrai si la page tient, sinon elle défile de côté."""
        gs = [g for g in self.groups() if not g.vacant]  # un groupe sans rien à montrer est caché : il ne compte pas
        if not gs:
            return True
        m = self._lay.contentsMargins()
        fixed = m.left() + m.right() + sum(
            w.sizeHint().width() for w in (self._lay.itemAt(i).widget() for i in range(self._lay.count()))
            if w is not None and not isinstance(w, RibbonGroup) and not w.isHidden())
        self.setUpdatesEnabled(False)
        try:
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
            # un long groupe (beaucoup de grands boutons) trop large : petits boutons sur trois rangées
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
            for i in range(len(gs)):                     # place restée : libellés rendus, de gauche à droite
                if not gs[i].iconic:
                    continue
                gs[i].set_iconic(False)
                w = gs[i].expanded_width()
                if total + w - exp[i] <= avail - 2:
                    total += w - exp[i]
                    exp[i] = w
                else:
                    gs[i].set_iconic(True)
        finally:
            self.setUpdatesEnabled(True)
        self._lay.invalidate()
        return total <= avail - 2
