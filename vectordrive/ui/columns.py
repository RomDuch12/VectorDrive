"""Colonnes de panneaux de la fenêtre principale (demandes du 14/11).

- Chaque panneau ancrable a la même barre de titre : son nom, puis « plein écran translucide », « détacher »
  (ou ancrer) et « fermer ». Un clic droit sur la barre, ou sur l'onglet du panneau quand plusieurs partagent une
  colonne, donne les mêmes fonctions, plus « Colonne de gauche » / « Colonne de droite ».
- Un panneau envoyé dans une colonne s'y range en onglet avec ceux qui y sont déjà ; sa colonne est retenue.
- « En onglet avec › » un autre panneau de sa colonne (Dimensions (F2) et Calques, par exemple), « Sortir des
  onglets » : deux panneaux partagent un onglet, ou non ; retenu pour les lancements suivants. D'office, Dimensions
  (F2) et Calques partagent le même groupe d'onglets.
- « Au-dessus de › », « Au-dessous de › » un autre panneau : la colonne partagée en hauteur, les deux montrés à la
  fois (demande du 15/11, 8 h 40) ; retenu pour les lancements suivants.
- Un clic droit sur un bouton de colonne ouvre la fenêtre de la colonne : tous les panneaux qu'elle peut accueillir,
  un œil chacun pour l'y montrer ou l'en retirer ; « ✕ » ou un clic droit dans la fenêtre la ferme.
- Deux boutons montrent ou cachent la colonne de gauche et celle de droite ; les panneaux cachés ainsi reviennent
  ensemble, les mêmes onglets devant.
- Un clic sur l'onglet CAD du ruban range les panneaux FAO ; un clic sur un onglet FAO les rétablit (réglage
  `fao/panneaux_onglet`). Seuls les clics comptent : un onglet qui change de lui-même (outil Texte, bascule 2D / 3D)
  ne range ni ne rétablit rien.

Les réglages sont sous `panneaux_colonnes/` (« colonnes/ » est celui des colonnes de texte).
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QTimer
from PySide6.QtWidgets import (QApplication, QDockWidget, QFrame, QGridLayout, QHBoxLayout, QLabel, QMenu, QSizeGrip,
                               QSizePolicy, QTabBar, QToolButton, QVBoxLayout, QWidget)

from ..i18n import tr

SIDES = ('gauche', 'droite')
#: les onglets des panneaux d'une colonne : 'court' (une icône et un libellé court ; d'office) ou 'entier' (le titre du
#: panneau, comme avant) — demande du 15/11, 22 h 30 : « Onglets colonnes pas assez de place »
TAB_MODES = ('court', 'entier')
#: icône d'onglet des panneaux du cœur, par nom de panneau
TAB_ICONS = {'dims': 'tab_dims', 'layers': 'tab_layers', 'symbols': 'tab_library', 'fao': 'tab_paths',
             'fao_liste': 'tab_ops', 'programme': 'tab_program', 'polices': 'tab_fonts'}
#: mots de liaison jamais laissés au bout d'un libellé court tiré d'un titre
LINK_WORDS = frozenset(('et', 'de', 'du', 'des', 'la', 'le', 'les', 'à', 'au', 'aux', 'en', 'pour', 'sur', 'ou',
                        '—', '-', '&', 'and', 'of', 'the', 'or', 'for'))


def full_title(dock) -> str:
    """Le titre entier du panneau (celui de sa barre, des menus, de sa fenêtre) : le titre de sa fenêtre Qt peut
    être son libellé court, que Qt écrit sur son onglet."""
    return str(dock.property('vd_titre') or dock.windowTitle())


def short_title(dock) -> str:
    """Le libellé court du panneau, pour son onglet : celui des panneaux du cœur ; celui qu'un plugin a donné
    (propriété `vd_court`) ; sinon le début de son titre (ses premiers mots, 14 caractères au plus)."""
    known = {'dims': 'F2', 'layers': tr('Calques'), 'symbols': tr('Biblio'), 'fao': tr('Parcours'),
             'fao_liste': tr('Opérations'), 'programme': tr('Programme'), 'polices': tr('Police')}
    name = dock.objectName()
    if name in known:
        return known[name]
    given = str(dock.property('vd_court') or '').strip()
    if given:
        return given
    title = full_title(dock).strip()
    if len(title) <= 14:
        return title
    tail = title.split(' — ', 1)[1].strip() if ' — ' in title else title     # « Machine — Panneau » : le panneau
    words = []
    for word in tail.replace(':', ' ').split():
        if words and len(' '.join(words + [word])) > 14:
            break
        words.append(word)
    while len(words) > 1 and words[-1].lower() in LINK_WORDS:               # pas de « et », de « de » au bout
        words.pop()
    short = ' '.join(words)
    return short if len(short) <= 14 else short[:13].rstrip() + '…'


def tab_icon(dock):
    """L'icône de l'onglet du panneau (une fenêtre et sa barre pour un panneau sans icône à lui)."""
    from . import icons
    return icons.icon(TAB_ICONS.get(dock.objectName(), 'tab_panel'))
AREAS = {'gauche': Qt.DockWidgetArea.LeftDockWidgetArea, 'droite': Qt.DockWidgetArea.RightDockWidgetArea}
#: panneaux montrés seulement à la demande (F3, le tableau des panneaux, leur commande) : une colonne rouverte sans
#: rien de retenu pour elle ne les fait pas paraître ; montrés puis cachés avec leur colonne, ils reviennent avec elle
ON_DEMAND = ('polices', 'accrochages', 'historique')
KEY = 'panneaux_colonnes'


class DockBar(QWidget):
    """Barre de titre d'un panneau : son nom, plein écran translucide, détacher / ancrer, fermer. Les clics qu'elle
    ne prend pas vont au panneau : il se déplace et s'ancre comme avec la barre d'origine."""

    def __init__(self, columns, dock):
        super().__init__(dock)
        from .flow import ElideLabel
        self.columns, self.dock = columns, dock
        self.setObjectName('dockBar')
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)   # le fond des thèmes (`QWidget#dockBar`)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 1, 2, 1)
        lay.setSpacing(1)
        self.title = ElideLabel(full_title(dock))        # un long titre s'abrège : il n'élargit pas la colonne
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        # (un titre changé : `Columns._retitled` remet le titre entier ici)
        lay.addWidget(self.title, 1)
        self.buttons = {}
        for key, text, tip, slot in (
                ('plein', '⛶', tr('Plein écran translucide : opacité réglable, la molette zoome le dessin'),
                 lambda: columns.toggle_overlay(dock)),
                ('detacher', '⧉', tr('Détacher le panneau dans sa fenêtre, ou le remettre dans sa colonne'),
                 lambda: columns.toggle_floating(dock)),
                ('fermer', '✕', tr('Fermer le panneau'), lambda: columns.close(dock))):
            b = self.buttons[key] = QToolButton()
            b.setText(text)
            b.setAutoRaise(True)
            b.setToolTip(tip)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.clicked.connect(lambda _=False, s=slot: s())
            lay.addWidget(b)

    def contextMenuEvent(self, ev):                      # noqa: N802 (API Qt)
        self.columns.show_menu(self.dock, ev.globalPos())


class Columns(QObject):
    """Les panneaux ancrables de la fenêtre `win`, rangés en colonne de gauche et colonne de droite."""

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self._busy = False
        self._docks: list = []                           # les panneaux pris en charge (leur objet Python gardé)
        self._panels: dict = {}                          # fenêtres des colonnes ouvertes (clic droit des boutons)
        self._scan_due = False
        self._titling = False                            # le titre court posé par nous : pas un nouveau titre
        self._dress_due = False
        self._adopt_new()
        self.restore()
        win.installEventFilter(self)                     # panneaux et barres d'onglets nés plus tard
        self._watch_tabs()
        self.sync()

    def _st(self):
        return self.win.settings

    # --- les panneaux ------------------------------------------------------------------------------------------
    def docks(self) -> list:
        return list(self._docks)

    def _adopt_new(self) -> None:
        for d in self.win.findChildren(QDockWidget, options=Qt.FindChildOption.FindDirectChildrenOnly):
            self.adopt(d)

    def adopt(self, dock) -> None:
        """La barre de titre commune pour ce panneau ; ses changements tiennent les boutons de colonne à jour."""
        if any(d is dock for d in self._docks):
            return
        self._docks.append(dock)
        if not dock.property('vd_titre'):
            dock.setProperty('vd_titre', dock.windowTitle())     # son titre entier, avant le libellé court
        dock.windowTitleChanged.connect(lambda t, d=dock: self._retitled(d, t))
        dock._vd_bar = DockBar(self, dock)
        self._dress(dock)
        dock.setTitleBarWidget(dock._vd_bar)
        # détaché, le panneau n'a plus le cadre de Windows (sa barre de titre est la nôtre) : une poignée dans son
        # coin bas droit le redimensionne
        dock._vd_grip = QSizeGrip(dock)
        dock._vd_grip.setVisible(False)
        dock.installEventFilter(self)
        dock.visibilityChanged.connect(lambda _v: self.sync())
        dock.dockLocationChanged.connect(lambda _a, d=dock: self._located(d))
        dock.topLevelChanged.connect(lambda _f, d=dock: (self._place_grip(d), self.sync()))

    # --- titres et onglets (demande du 15/11, 22 h 30) -----------------------------------------------------------
    def tab_mode(self) -> str:
        """'court' : une icône et un libellé court sur les onglets (d'office) ; 'entier' : le titre du panneau."""
        v = str(self._st().value(f'{KEY}/onglets', 'court') or 'court')
        return v if v in TAB_MODES else 'court'

    def set_tab_mode(self, mode: str) -> None:
        self._st().setValue(f'{KEY}/onglets', mode if mode in TAB_MODES else 'court')
        for d in self.docks():
            self._dress(d)
        self.dress_tabs()

    def _dress(self, dock) -> None:
        """Le titre de la fenêtre du panneau : son libellé court, ou son titre entier — c'est lui que Qt écrit sur
        l'onglet (et y remet, si on change le texte de l'onglet). La barre du panneau garde le titre entier."""
        want = short_title(dock) if self.tab_mode() == 'court' else full_title(dock)
        if dock.windowTitle() != want:
            self._titling = True
            try:
                dock.setWindowTitle(want)
            finally:
                self._titling = False
        if dock.toggleViewAction().text() != full_title(dock):   # (le menu d'office de Qt : le titre entier)
            dock.toggleViewAction().setText(full_title(dock))

    def _retitled(self, dock, title: str) -> None:
        """Un titre posé d'ailleurs (un plugin renomme son panneau) : c'est son nouveau titre entier, gardé tel quel
        sur l'onglet aussi."""
        if self._titling:
            return
        dock.setProperty('vd_titre', title)
        bar = getattr(dock, '_vd_bar', None)
        if bar is not None:
            bar.title.setText(title)
        self.dress_later()

    def dress_later(self) -> None:
        if not self._dress_due:
            self._dress_due = True
            QTimer.singleShot(0, self.dress_tabs)

    def dress_tabs(self, refresh: bool = False) -> None:
        """Les onglets des panneaux : une icône devant le libellé court (aucune devant un titre entier), le titre
        entier en bulle. Qt refait l'onglet d'un panneau remontré : son icône est reposée ici. `refresh` : toutes
        les icônes refaites (thème changé : une autre encre)."""
        self._dress_due = False
        short = self.tab_mode() == 'court'
        try:
            bars = self.win.findChildren(QTabBar, options=Qt.FindChildOption.FindDirectChildrenOnly)
        except RuntimeError:                             # fenêtre détruite entre-temps
            return
        for bar in bars:
            for i in range(bar.count()):
                d = self.dock_at(bar, i)
                if d is None:
                    continue
                if short and (refresh or bar.tabIcon(i).isNull()):
                    bar.setTabIcon(i, tab_icon(d))
                elif not short and not bar.tabIcon(i).isNull():
                    from PySide6.QtGui import QIcon
                    bar.setTabIcon(i, QIcon())
                if bar.tabToolTip(i) != full_title(d):
                    bar.setTabToolTip(i, full_title(d))

    def _place_grip(self, dock) -> None:
        """La poignée de redimensionnement : montrée quand le panneau est détaché, dans son coin bas droit."""
        grip = getattr(dock, '_vd_grip', None)
        if grip is None:
            return
        ov = self.overlay(dock, create=False)
        on = dock.isFloating() and not (ov is not None and ov.active)
        if on:
            s = grip.sizeHint()
            grip.setGeometry(dock.width() - s.width(), dock.height() - s.height(), s.width(), s.height())
            grip.raise_()
        grip.setVisible(on)

    def _located(self, dock) -> None:
        """Le panneau a changé de place (glissé à la souris aussi) : sa colonne est retenue."""
        if not self._busy:
            side = self.side(dock)
            if side:
                st = self._st()
                name = dock.objectName()
                if str(st.value(f'{KEY}/place/{name}', '') or '') not in ('', side):   # glissé dans l'autre colonne
                    st.remove(f'{KEY}/partage/{name}')
                    self._unsplit_from(name)
                st.setValue(f'{KEY}/place/{name}', side)
        self.sync()

    def side(self, dock) -> str | None:
        """'gauche' ou 'droite' : la colonne où le panneau est ancré ; None : détaché, ou ailleurs."""
        if dock.isFloating():
            return None
        area = self.win.dockWidgetArea(dock)
        return next((s for s, a in AREAS.items() if a == area), None)

    def column(self, side: str) -> list:
        """Les panneaux ancrés dans la colonne `side`, cachés compris."""
        return [d for d in self.docks() if self.side(d) == side]

    def in_front(self, dock) -> bool:
        """Le panneau montré est-il devant, dans son groupe d'onglets (pas recouvert par un voisin) ?"""
        return not dock.isHidden() and not dock.visibleRegion().isEmpty()

    def _quiet(self, fn) -> None:
        """`fn` sans que les commandes « Panneau FAO » et « Bibliothèque » réagissent : cacher une colonne ne ferme
        pas l'autre panneau FAO et ne change pas ce qui est retenu pour le prochain lancement. Leurs boutons disent
        ensuite ce qui est montré."""
        was, self._busy = self._busy, True
        try:
            fn()
        finally:
            self._busy = was
        if not self._busy:
            follow = getattr(self.win, 'dock_actions_follow', None)
            if follow is not None:
                follow()
            self.sync()

    def busy(self) -> bool:
        return self._busy

    # --- d'une colonne à l'autre ---------------------------------------------------------------------------------
    def move(self, dock, side: str, remember: bool = True, show: bool = True) -> None:
        """Le panneau ancré dans la colonne `side`, en onglet avec ceux qui y sont déjà (le groupe le plus fourni,
        montré de préférence), et mis devant. `show` faux (au lancement) : rangé sans être montré ni mis devant."""
        if side not in AREAS:
            return
        ov = self.overlay(dock, create=False)
        if ov is not None and ov.active:
            ov.set_active(False)
        there = [d for d in self.column(side) if d is not dock]
        others = [d for d in there if not d.isHidden()] or there
        hidden = dock.isHidden()
        self.win._docks_before_cam = None                # la disposition d'avant la FAO n'est plus à rendre
        front = [d for d in others if self.in_front(d)] if not show else []

        def do():
            dock.setFloating(False)
            self.win.addDockWidget(AREAS[side], dock)
            if others:
                self.win.tabifyDockWidget(max(others, key=lambda d: len(self.win.tabifiedDockWidgets(d))), dock)
            if show:
                dock.setVisible(True)
                dock.raise_()
            else:
                dock.setVisible(not hidden)
                for d in front:                          # les onglets qui étaient devant le restent
                    d.raise_()
        self._quiet(do)
        if remember:
            st = self._st()
            st.setValue(f'{KEY}/place/{dock.objectName()}', side)
            st.remove(f'{KEY}/onglet/{dock.objectName()}')   # envoyé dans une colonne : ni en onglet retenu, ni seul
            st.remove(f'{KEY}/seul/{dock.objectName()}')
            st.remove(f'{KEY}/partage/{dock.objectName()}')  # ni au-dessus ou au-dessous d'un autre
            self._unsplit_from(dock.objectName())        # ni repère de ceux qui l'étaient par rapport à lui

    def restore(self) -> None:
        """Au lancement : chaque panneau dans la colonne retenue pour lui, sans le montrer ni le mettre devant ; un
        panneau détaché d'office (le programme machine) aussi, une fois rangé dans une colonne."""
        for d in self.docks():
            want = str(self._st().value(f'{KEY}/place/{d.objectName()}', '') or '')
            if want in AREAS and self.side(d) != want:
                self.move(d, want, remember=False, show=False)
        st = self._st()
        for d in self.docks():                           # seuls d'abord, puis en onglet : comme on les a laissés,
            name = d.objectName()                        # quel que soit l'ordre des panneaux
            if (str(st.value(f'{KEY}/seul/{name}', '')).lower() in ('1', 'true')
                    and not st.value(f'{KEY}/onglet/{name}', '') and self.win.tabifiedDockWidgets(d)):
                self.untab(d, remember=False, show=False)
        for d in self.docks():
            want = str(st.value(f'{KEY}/onglet/{d.objectName()}', '') or '')
            other = next((o for o in self.docks() if o.objectName() == want), None) if want else None
            if other is not None and self.side(other) is not None and self.side(other) == self.side(d):
                if other not in self.win.tabifiedDockWidgets(d):
                    self.tab_with(d, other, remember=False, show=False)
        for d in self.docks():                           # au-dessus ou au-dessous d'un autre panneau
            want, _sep, where = str(st.value(f'{KEY}/partage/{d.objectName()}', '') or '').partition('|')
            other = next((o for o in self.docks() if o.objectName() == want), None) if want else None
            if other is not None and other is not d and self.side(other) is not None \
                    and self.side(other) == self.side(d):
                self.split_with(d, other, where != 'dessus', remember=False, show=False)
        self._f2_with_layers()
        self._cad_names = [n for n in str(self._st().value(f'{KEY}/rangees_cad', '') or '').split(',') if n]

    # --- en onglets dans une colonne (demande du 14/11, soir) ----------------------------------------------------
    def _f2_with_layers(self) -> None:
        """D'office, Dimensions (F2) et Calques dans le même groupe d'onglets de leur colonne, Dimensions devant ;
        pas s'ils ont été séparés (« Sortir des onglets » sur l'un ou l'autre), si Dimensions est en onglet avec un
        autre panneau ou s'ils sont dans deux colonnes."""
        st = self._st()
        if st.value(f'{KEY}/onglet/dims', '') or any(
                str(st.value(f'{KEY}/seul/{n}', '')).lower() in ('1', 'true') or st.value(f'{KEY}/partage/{n}', '')
                for n in ('dims', 'layers')):
            return
        dims = next((d for d in self.docks() if d.objectName() == 'dims'), None)
        layers = next((d for d in self.docks() if d.objectName() == 'layers'), None)
        if dims is None or layers is None or layers in self.win.tabifiedDockWidgets(dims):
            return
        if self.side(layers) is None or self.side(dims) != self.side(layers):
            return
        if self.tab_with(dims, layers, remember=False, show=False) and not dims.isHidden():
            self._quiet(dims.raise_)

    def tab_with(self, dock, other, remember: bool = True, show: bool = True) -> bool:
        """`dock` en onglet avec `other`, dans la colonne de `other` (Dimensions (F2) et Calques, par exemple) ; mis
        devant si `show` (sinon les onglets qui étaient devant le restent). Retenu (`remember`) : au lancement
        suivant, ils se retrouvent ensemble. Rend vrai s'ils partagent un onglet."""
        side = self.side(other)
        if side is None or dock is other:
            return False
        front = [d for d in self.column(side) if self.in_front(d)] if not show else []
        hidden = dock.isHidden()

        def do():
            if self.side(dock) != side:
                dock.setFloating(False)
                self.win.addDockWidget(AREAS[side], dock)
            self.win.tabifyDockWidget(other, dock)
            if show:
                dock.setVisible(True)
                dock.raise_()
            else:
                dock.setVisible(not hidden)
                for d in front:
                    d.raise_()
        self._quiet(do)
        if remember:
            self.win._docks_before_cam = None            # fermer la FAO ne défait pas ce choix
            st = self._st()
            st.setValue(f'{KEY}/onglet/{dock.objectName()}', other.objectName())
            st.remove(f'{KEY}/partage/{dock.objectName()}')
            self._unsplit_from(dock.objectName())
            st.remove(f'{KEY}/seul/{dock.objectName()}')  # `other` sorti de son groupe le reste : au lancement,
                                                          # les « seuls » d'abord, puis ce couple
            st.setValue(f'{KEY}/place/{dock.objectName()}', side)
        self.sync()
        return other in self.win.tabifiedDockWidgets(dock)

    def untab(self, dock, remember: bool = True, show: bool = True) -> bool:
        """`dock` sorti de son groupe d'onglets : seul, sous les autres panneaux de sa colonne. Retenu : ni lui, ni
        ceux qui avaient été mis en onglet avec lui, ne s'y retrouvent au lancement suivant. Rend vrai s'il est
        seul."""
        side = self.side(dock)
        group = list(self.win.tabifiedDockWidgets(dock)) if side is not None else []
        if not group:
            return False
        hidden = dock.isHidden()

        def do():
            self.win.removeDockWidget(dock)
            self.win.addDockWidget(AREAS[side], dock, Qt.Orientation.Vertical)
            dock.setVisible(True if show else not hidden)
            if show:
                dock.raise_()
        self._quiet(do)
        if remember:
            self.win._docks_before_cam = None            # fermer la FAO ne défait pas ce choix
            st = self._st()
            st.remove(f'{KEY}/onglet/{dock.objectName()}')
            st.remove(f'{KEY}/partage/{dock.objectName()}')
            self._unsplit_from(dock.objectName())
            for d in self.docks():                       # tous ceux mis en onglet avec lui, même cachés
                if str(st.value(f'{KEY}/onglet/{d.objectName()}', '') or '') == dock.objectName():
                    st.remove(f'{KEY}/onglet/{d.objectName()}')
            st.setValue(f'{KEY}/seul/{dock.objectName()}', True)
        self.sync()
        return not self.win.tabifiedDockWidgets(dock)

    def split_with(self, dock, other, below: bool = True, remember: bool = True, show: bool = True) -> bool:
        """`dock` au-dessous (`below`) ou au-dessus de `other`, dans la colonne de `other` : la colonne partagée en
        hauteur, les deux montrés à la fois (demande du 15/11, 8 h 40). Sous un panneau en onglets (Calques avec la
        Bibliothèque…), `dock` va sous leur groupe ; au-dessus, `other` quitte ses onglets pour venir sous `dock`.
        Retenu (`remember`) pour les lancements suivants. Rend vrai s'ils sont dans la même colonne, hors des onglets
        l'un de l'autre."""
        side = self.side(other)
        if side is None or dock is other:
            return False
        ov = self.overlay(dock, create=False)
        if ov is not None and ov.active:
            ov.set_active(False)                         # du plein écran translucide : de retour d'abord
        front = [d for d in self.column(side) if self.in_front(d)] if not show else []
        hidden = dock.isHidden()

        def do():
            first, second = (other, dock) if below else (dock, other)
            mates = [m for m in self.win.tabifiedDockWidgets(other) if m is not dock and not m.isHidden()]
            shown = not other.isHidden()
            self.win.removeDockWidget(dock)              # hors de ses onglets
            dock.setFloating(False)
            if below and mates:                          # sous un groupe d'onglets montrés : en bas de la colonne
                self.win.addDockWidget(AREAS[side], dock, Qt.Orientation.Vertical)
            else:
                # les deux remis à neuf : Qt garde sinon un groupe d'onglets d'un seul panneau, où le partage
                # donnerait un onglet (une colonne qui n'a que ce groupe, par exemple)
                self.win.removeDockWidget(other)
                self.win.addDockWidget(AREAS[side], first, Qt.Orientation.Vertical)
                self.win.splitDockWidget(first, second, Qt.Orientation.Vertical)
                other.setVisible(shown)
            dock.setVisible(True if show else not hidden)
            if show:
                dock.raise_()
            else:
                for d in front:
                    d.raise_()
        self._quiet(do)
        if remember:
            self.win._docks_before_cam = None            # fermer la FAO ne défait pas ce choix
            st = self._st()
            name = dock.objectName()
            st.setValue(f'{KEY}/partage/{name}', f'{other.objectName()}|{"dessous" if below else "dessus"}')
            st.remove(f'{KEY}/onglet/{name}')
            st.remove(f'{KEY}/seul/{name}')
            st.remove(f'{KEY}/partage/{other.objectName()}')   # l'autre n'est plus rangé par rapport à un troisième
            self._unsplit_from(name)                     # ni un troisième par rapport à lui
            st.setValue(f'{KEY}/place/{name}', side)
        self.sync()
        return self.side(dock) == side and other not in self.win.tabifiedDockWidgets(dock)

    def _shares(self) -> dict:
        """{panneau : son repère} retenus (« Au-dessus de », « Au-dessous de »), repères absents compris."""
        st = self._st()
        st.beginGroup(f'{KEY}/partage')
        try:
            return {k: str(st.value(k, '') or '').partition('|')[0] for k in st.childKeys()}
        finally:
            st.endGroup()

    def _unsplit_from(self, name: str) -> None:
        """Ceux qui étaient rangés au-dessus ou au-dessous de `name` ne le sont plus : il a changé de place."""
        st = self._st()
        for k, target in self._shares().items():
            if target == name:
                st.remove(f'{KEY}/partage/{k}')

    def split_names(self) -> set:
        """Les panneaux partagés en hauteur (retenu) : ceux rangés par rapport à un autre, et leurs repères."""
        out = set()
        for k, target in self._shares().items():
            out.update((k, target))
        return out

    # --- la fenêtre d'une colonne (clic droit sur son bouton) ------------------------------------------------------
    def show_panel(self, side: str, button=None):
        """La fenêtre de la colonne `side`, sous son bouton (ou au milieu de la fenêtre) ; rouverte si elle l'était."""
        if side not in AREAS:
            return None
        import time
        shut, self._panel_shut = getattr(self, '_panel_shut', None), None
        if button is not None and shut is not None and shut[0] == side and time.monotonic() - shut[1] < 0.4:
            return None                                  # fermée à l'instant par l'appui sur ce même bouton
        old = self._panels.pop(side, None)
        if old is not None:
            try:
                old.close()
                old.deleteLater()
            except RuntimeError:                         # déjà détruite
                pass
        p = self._panels[side] = ColumnPanel(self, side)
        p.adjustSize()
        if button is not None:
            at = button.mapToGlobal(QPoint(button.width() - p.width(), button.height()))
        else:
            at = self.win.mapToGlobal(self.win.rect().center() - p.rect().center())
        screen = self.win.screen().availableGeometry() if self.win.screen() is not None else None
        if screen is not None:
            at.setX(max(screen.left(), min(at.x(), screen.right() - p.width())))
            at.setY(max(screen.top(), min(at.y(), screen.bottom() - p.height())))
        p.move(at)
        p.clamp()                                        # dans l'écran où elle est (celui du bouton)
        p.show()
        p.raise_()
        return p

    def panel(self, side: str):
        """La fenêtre de la colonne `side` si elle est ouverte."""
        p = self._panels.get(side)
        try:
            return p if p is not None and p.isVisible() else None
        except RuntimeError:
            return None

    def show_in(self, dock, side: str, on: bool) -> None:
        """L'œil de la fenêtre d'une colonne : `dock` montré dans la colonne `side` (la FAO ouverte pour ses
        panneaux), ou retiré (fermé)."""
        if not on:
            self.close(dock)
            return
        w = self.win
        act = getattr(w, 'A', {}).get('cam_panel')
        if dock in (getattr(w, 'dock_cam', None), getattr(w, 'dock_paths', None)) and act is not None \
                and not act.isChecked():
            act.trigger()                                # la FAO ouverte : ses deux panneaux
        host = getattr(dock, '_as_window', None)
        if host is not None and host.in_window():        # panneau d'un plugin dans sa propre fenêtre : rendu au panneau
            host.to_dock()
        if dock is getattr(w, 'dock_program', None):
            w.show_program()                             # montré et à jour, comme par son bouton
        if dock.isFloating() or self.side(dock) != side:
            self.move(dock, side)
        else:
            self._quiet(lambda: (dock.setVisible(True), dock.raise_()))

    # --- montrer, cacher une colonne -----------------------------------------------------------------------------
    def shown(self, side: str) -> bool:
        return any(not d.isHidden() for d in self.column(side))

    def _gated(self, dock) -> bool:
        """Panneau qui ne se montre pas d'office avec sa colonne : les panneaux FAO quand la FAO est fermée, le
        programme machine, ceux d'un plugin (réservés à une machine)."""
        w = self.win
        if dock in (getattr(w, 'dock_cam', None), getattr(w, 'dock_paths', None)):
            act = getattr(w, 'A', {}).get('cam_panel')
            return not (act is not None and act.isChecked())
        return dock.objectName().startswith('plugin_') or dock is getattr(w, 'dock_program', None)

    def _memory(self, side: str) -> tuple:
        """(panneaux retenus cachés avec la colonne, ceux qui étaient devant)."""
        raw = str(self._st().value(f'{KEY}/cachees/{side}', '') or '')
        names, _sep, front = raw.partition('|')
        return [n for n in names.split(',') if n], [n for n in front.split(',') if n]

    def set_shown(self, side: str, on: bool) -> bool:
        """La colonne `side` montrée ou cachée ; cachée, ses panneaux sont retenus (et ceux qui étaient devant) et
        reviennent ensemble. Rend l'état obtenu."""
        key = f'{KEY}/cachees/{side}'
        col = self.column(side)
        self.win._docks_before_cam = None
        if not on:
            there = [d for d in col if not d.isHidden()]
            if there:
                kept, kept_front = self._memory(side)    # déjà cachés avec elle et pas revenus : toujours retenus
                still = [d.objectName() for d in col if d.isHidden() and d.objectName() in kept]
                front = [d.objectName() for d in there if self.in_front(d)]
                names = [d.objectName() for d in there] + still
                self._st().setValue(key, ','.join(names) + '|' + ','.join(front or kept_front))
                self._quiet(lambda: [d.setVisible(False) for d in there])
        elif not self.shown(side):
            names, front = self._memory(side)
            back = [d for d in col if d.objectName() in names and not self._gated(d)] \
                or [d for d in col if not self._gated(d) and d.objectName() not in ON_DEMAND]

            def do():
                for d in back:
                    d.setVisible(True)
                for d in back:
                    if d.objectName() in front:
                        d.raise_()
            if back:
                self._quiet(do)
            self._st().remove(key)                       # revenue : plus rien de retenu pour elle
        self.sync()
        return self.shown(side)

    def toggle(self, side: str) -> bool:
        return self.set_shown(side, not self.shown(side))

    def sync(self) -> None:
        """Les deux boutons de colonne disent ce qui est montré."""
        if self._busy:
            return
        acts = getattr(self.win, 'A', {})
        for side, key in zip(SIDES, ('col_left', 'col_right')):
            a = acts.get(key)
            if a is not None and a.isChecked() != self.shown(side):
                blocked = a.blockSignals(True)
                a.setChecked(self.shown(side))
                a.blockSignals(blocked)
                a.changed.emit()                         # son bouton se repeint
        for side in SIDES:                               # les fenêtres de colonne ouvertes suivent
            p = self.panel(side)
            if p is not None:
                p.refresh_later()
        self.dress_later()                               # un onglet refait par Qt : son icône, sa bulle

    # --- les fonctions d'un panneau --------------------------------------------------------------------------------
    def overlay(self, dock, create: bool = True):
        """Le plein écran translucide du panneau (`ui.overlay.Overlay`) ; ceux de la FAO sont ceux de la fenêtre."""
        w = self.win
        for which, d in (('paths', getattr(w, 'dock_paths', None)), ('palette', getattr(w, 'dock_cam', None))):
            if d is dock:
                return w.overlays[which]
        ov = getattr(dock, '_vd_overlay', None)
        if ov is None and create:
            from .overlay import Overlay
            ov = dock._vd_overlay = Overlay(w, dock, dock.objectName() or 'panneau')
        return ov

    def toggle_overlay(self, dock) -> bool:
        ov = self.overlay(dock)
        on = ov.set_active(not ov.active)
        self._place_grip(dock)
        self.sync()
        return on

    def toggle_floating(self, dock) -> bool:
        """Détaché dans sa fenêtre, ou de retour dans sa colonne (en onglet avec les panneaux qui y sont) ; rend
        vrai s'il est détaché."""
        w = self.win
        ov = self.overlay(dock, create=False)
        if ov is not None and ov.active:
            ov.set_active(False)                         # du plein écran : de retour à sa place d'avant
            return dock.isFloating()
        host = getattr(dock, '_as_window', None)
        if host is not None:                             # panneau d'un plugin qui a sa propre fenêtre
            host.toggle()
            return bool(host.in_window())
        if dock is getattr(w, 'dock_paths', None) and not dock.isFloating():
            return w.toggle_paths_window(True)           # sa place et sa taille de fenêtre détachée
        if dock.isFloating():
            want = str(self._st().value(f'{KEY}/place/{dock.objectName()}', '') or '')
            self.move(dock, want if want in AREAS else 'droite')
            if dock is getattr(w, 'dock_paths', None):
                w.settings.setValue('fao/liste_detachee', False)
            return False
        dock.setFloating(True)
        return True

    def close(self, dock) -> None:
        """Le panneau fermé ; la palette des parcours fermée ferme la FAO (ses deux panneaux), comme toujours."""
        ov = self.overlay(dock, create=False)
        if ov is not None and ov.active:
            ov.set_active(False)
        w = self.win
        act = getattr(w, 'A', {}).get('cam_panel')
        if dock is getattr(w, 'dock_cam', None) and act is not None and act.isChecked():
            act.setChecked(False)
        dock.close()
        follow = getattr(w, 'dock_actions_follow', None)
        if follow is not None:
            follow()

    def menu(self, dock, parent=None) -> QMenu:
        """Le menu du clic droit d'un panneau (sa barre de titre, son onglet)."""
        m = QMenu(parent or self.win)
        from PySide6.QtWidgets import QWidgetAction
        table = QWidgetAction(m)                         # en tête : tous les panneaux, Gauche / Masqué / Droite
        table.setObjectName('panneaux')
        box = QWidget()
        inner = QVBoxLayout(box)
        inner.setContentsMargins(8, 4, 8, 4)
        inner.addWidget(PanelRows(self, self.side(dock) or 'droite', done=m.close, parent=box))
        table.setDefaultWidget(box)
        m.addAction(table)
        m.addSeparator()
        ov = self.overlay(dock, create=False)
        a = m.addAction(tr('Plein écran translucide'))
        a.setCheckable(True)
        a.setChecked(bool(ov is not None and ov.active))
        a.triggered.connect(lambda _=False: self.toggle_overlay(dock))
        a = m.addAction(tr('Ancrer') if dock.isFloating() else tr('Détacher'))
        a.triggered.connect(lambda _=False: self.toggle_floating(dock))
        m.addSeparator()
        here = self.side(dock)
        for side, label in zip(SIDES, (tr('Colonne de gauche'), tr('Colonne de droite'))):
            a = m.addAction(label)
            a.setCheckable(True)
            a.setChecked(here == side)
            a.setEnabled(here != side)
            a.triggered.connect(lambda _=False, s=side: self.move(dock, s))
        if here in AREAS:                                # partager un onglet avec un autre panneau de la colonne
            group = self.win.tabifiedDockWidgets(dock)
            others = [d for d in self.column(here) if d is not dock and not d.isHidden() and d not in group]
            if others:
                sub = QMenu(tr('En onglet avec'), m)     # enfant du menu : vit autant que lui
                sub.setObjectName('en_onglet_avec')
                m.addMenu(sub)
                for d in others:
                    a = sub.addAction(full_title(d))
                    a.triggered.connect(lambda _=False, o=d: self.tab_with(dock, o))
            if group:
                a = m.addAction(tr('Sortir des onglets'))
                a.triggered.connect(lambda _=False: self.untab(dock))
        near = [d for d in (self.column(here) if here in AREAS else [d for d in self.docks() if self.side(d)])
                if d is not dock and not d.isHidden()]
        for title, name, below in ((tr('Au-dessus de'), 'au_dessus_de', False),
                                   (tr('Au-dessous de'), 'au_dessous_de', True)):
            if near:                                     # la colonne partagée en hauteur avec un autre panneau
                sub = QMenu(title, m)
                sub.setObjectName(name)
                m.addMenu(sub)
                for d in near:
                    a = sub.addAction(full_title(d))
                    a.triggered.connect(lambda _=False, o=d, b=below: self.split_with(dock, o, b))
        m.addSeparator()
        a = m.addAction(tr('Titres entiers dans les onglets'))    # sinon : une icône et un libellé court
        a.setCheckable(True)
        a.setChecked(self.tab_mode() == 'entier')
        a.triggered.connect(lambda on=False: self.set_tab_mode('entier' if on else 'court'))
        a = m.addAction(tr('Fermer'))
        a.triggered.connect(lambda _=False: self.close(dock))
        return m

    def show_menu(self, dock, at) -> None:
        """Le menu du panneau ouvert au point `at` de l'écran."""
        m = self.menu(dock)
        m.exec(at)
        m.deleteLater()

    # --- les onglets des panneaux ----------------------------------------------------------------------------------
    def _watch_tabs(self) -> None:
        for bar in self.win.findChildren(QTabBar, options=Qt.FindChildOption.FindDirectChildrenOnly):
            if not bar.property('vd_columns'):
                bar.setProperty('vd_columns', True)
                bar.installEventFilter(self)

    def _scan(self) -> None:
        self._scan_due = False
        self._adopt_new()                                # un panneau créé après coup (plugin) : la même barre
        self._watch_tabs()
        self.sync()
        self.dress_tabs()

    def dock_at(self, bar, index: int):
        """Le panneau de l'onglet `index` d'une barre d'onglets de panneaux : celui que Qt y a mis (son adresse),
        sinon celui du même titre parmi les panneaux ancrés et montrés."""
        if index < 0:
            return None
        try:
            import shiboken6
            ptr = int(bar.tabData(index) or 0)
            for d in self.docks():
                if ptr and int(shiboken6.getCppPointer(d)[0]) == ptr:
                    return d
        except (ImportError, TypeError, ValueError):
            pass
        title = bar.tabText(index)
        named = [d for d in self.docks() if not d.isFloating() and d.windowTitle() == title]
        return next((d for d in named if not d.isHidden()), named[0] if named else None)

    def eventFilter(self, obj, ev) -> bool:              # noqa: N802 (API Qt)
        t = ev.type()
        if obj is self.win:
            if t == QEvent.Type.ChildAdded and not self._scan_due:
                self._scan_due = True
                QTimer.singleShot(0, self._scan)
            return False
        if isinstance(obj, QDockWidget):
            if t in (QEvent.Type.Resize, QEvent.Type.Show):
                self._place_grip(obj)                    # la poignée reste dans le coin
            return False
        if t == QEvent.Type.Paint and isinstance(obj, QTabBar) and not self._dress_due \
                and any(obj.tabIcon(i).isNull() for i in range(obj.count())) and self.tab_mode() == 'court':
            self.dress_later()                           # un onglet que Qt vient de refaire, sans son icône
        if t == QEvent.Type.ContextMenu and isinstance(obj, QTabBar):
            dock = self.dock_at(obj, obj.tabAt(ev.pos()))
            if dock is not None:
                self.show_menu(dock, ev.globalPos())
                return True
        return False

    # --- l'onglet CAD range la FAO -----------------------------------------------------------------------------------
    def fao_docks(self) -> list:
        """Les panneaux de la FAO : la palette des parcours, les opérations, le programme machine, ceux des plugins."""
        w = self.win
        out = [d for d in (getattr(w, 'dock_cam', None), getattr(w, 'dock_paths', None),
                           getattr(w, 'dock_program', None)) if d is not None]
        return out + list((getattr(w, 'plugin_docks', None) or {}).values())

    def put_away(self) -> list:
        """Les panneaux FAO que l'onglet CAD a rangés, encore cachés (retenus d'un lancement à l'autre)."""
        names = getattr(self, '_cad_names', [])
        return [d for d in self.fao_docks() if d.objectName() in names and d.isHidden()]

    def _remember_cad(self, docks) -> None:
        self._cad_names = [d.objectName() for d in docks]
        if docks:
            self._st().setValue(f'{KEY}/rangees_cad', ','.join(self._cad_names))
        else:
            self._st().remove(f'{KEY}/rangees_cad')

    def _plugin_ok(self, dock) -> bool:
        """Un panneau de plugin peut-il revenir : pas dans sa propre fenêtre, et de la machine du dessin ?"""
        host = getattr(dock, '_as_window', None)
        if host is not None and host.in_window():
            return False
        allowed = getattr(self.win, 'plugin_dock_allowed', None)
        return True if allowed is None else bool(allowed(dock))

    def tab_clicked(self, kind: str) -> None:
        """Un onglet du ruban cliqué (`kind` : 'cad', 'fao' ou '') : CAD range les panneaux FAO montrés, un onglet FAO
        les rétablit — les mêmes, les mêmes onglets devant."""
        from .options import value
        w = self.win
        if kind not in ('cad', 'fao') or not value(w.settings, 'fao/panneaux_onglet'):
            return
        if kind == 'cad':
            there = [d for d in self.fao_docks() if not d.isHidden()]
            if not there:
                return
            for d in there:
                ov = self.overlay(d, create=False)
                if ov is not None and ov.active:
                    ov.set_active(False)
            self._cad_front = [d.objectName() for d in there if self.in_front(d)]
            self._remember_cad(self.put_away() + there)
            self._quiet(lambda: [d.setVisible(False) for d in there])
            w.statusBar().showMessage(tr('Onglet CAD : panneaux FAO rangés ; un onglet FAO les rétablit'), 5000)
            return
        back = [d for d in self.put_away() if not d.objectName().startswith('plugin_') or self._plugin_ok(d)]
        self._remember_cad([])
        if not back:
            return
        front = getattr(self, '_cad_front', [])

        def do():
            for d in back:
                d.setVisible(True)
            for d in back:
                if not d.isFloating() and d.objectName() in front:
                    d.raise_()
        self._quiet(do)


#: les trois places d'un panneau (demande du 15/11, 19 h 35) : clé, libellé, bulle
PLACES = (('gauche', 'Gauche', 'Montré dans la colonne de gauche (un second clic : masqué)'),
          ('masque', 'Masqué', 'Retiré des colonnes'),
          ('droite', 'Droite', 'Montré dans la colonne de droite (un second clic : masqué)'))


class PanelRows(QWidget):
    """Tous les panneaux que les colonnes accueillent, une ligne chacun : Gauche, Masqué, Droite — le même tableau
    dans la fenêtre d'une colonne et en tête du clic droit d'un panneau (demande du 15/11, 19 h 35). `side` : la
    colonne d'où il est ouvert (ses panneaux d'abord) ; `done()` : appelé après un choix."""

    def __init__(self, columns, side: str = 'droite', done=None, parent=None):
        super().__init__(parent)
        self.columns, self.side, self.done = columns, side if side in SIDES else 'droite', done
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(1)
        #: panneau → {place: bouton} ; `eyes` : le bouton de la colonne d'où le tableau est ouvert
        self.choices, self.eyes = {}, {}
        allowed = getattr(columns.win, 'plugin_dock_allowed', None)
        for i, d in enumerate(self.rows()):
            where, hidden = columns.side(d), d.isHidden()
            central = self._central(d)                   # le programme machine mis au centre : ni caché, ni en colonne
            state = 'centre' if central else 'masque' if hidden else (where or 'ailleurs')
            barred = hidden and d.objectName().startswith('plugin_') and allowed is not None and not allowed(d)
            grid.addWidget(QLabel(full_title(d)), i, 0)
            row = {}
            for col, (key, text, tip) in enumerate(PLACES, 1):
                b = QToolButton()
                b.setText(tr(text))
                b.setCheckable(True)
                b.setChecked(state == key)
                b.setAutoRaise(True)
                b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                b.setToolTip(tr(tip))
                if barred and key != 'masque':
                    b.setEnabled(False)                  # réservé à une autre machine
                    b.setToolTip(tr('Panneau réservé à une autre machine que celle du dessin'))
                b.clicked.connect(lambda _=False, dk=d, place=key: self.choose(dk, place))
                row[key] = b
                grid.addWidget(b, i, col)
            if central or (not hidden and d.isFloating()):
                note = QLabel(tr('au centre') if central else tr('détaché'))
                note.setEnabled(False)
                grid.addWidget(note, i, len(PLACES) + 1)
            self.choices[d.objectName()] = row
            self.eyes[d.objectName()] = row[self.side]

    def _central(self, dock) -> bool:
        w = self.columns.win
        centered = getattr(w, 'program_centered', None)
        return dock is getattr(w, 'dock_program', None) and callable(centered) and bool(centered())

    def rows(self) -> list:
        """Les panneaux listés : ceux de la colonne d'où le tableau est ouvert d'abord, puis les autres, par nom."""
        c = self.columns
        return sorted(c.docks(), key=lambda d: (c.side(d) != self.side, full_title(d).lower()))

    def choose(self, dock, place: str) -> None:
        """Le panneau `dock` mis à sa place : une colonne (la FAO ouverte pour ses panneaux), ou masqué — aussi par
        un second clic sur la colonne où il est déjà."""
        c = self.columns
        central = self._central(dock)
        if central:                                      # le programme rentre d'abord dans son panneau
            c.win.program_center(False)
        if place not in SIDES and dock.isHidden() and not central:
            pass                                         # déjà masqué : rien (fermer un panneau FAO caché fermerait la FAO)
        else:
            c.win._docks_before_cam = None               # la disposition retenue avant la FAO ne vaut plus
            if place not in SIDES or (c.side(dock) == place and not dock.isHidden() and not dock.isFloating()
                                      and not central):
                c.close(dock)
            else:
                c.show_in(dock, place, True)
        if self.done is not None:
            self.done()


class ColumnPanel(QFrame):
    """La fenêtre d'une colonne (clic droit sur son bouton, demande du 15/11, 8 h 40) : tous les panneaux que les
    colonnes accueillent, ceux de cette colonne d'abord ; Gauche, Masqué, Droite pour chacun. La même des deux côtés :
    sans titre (demande du 16/11, 23 h 25) ; un clic ailleurs, Échap ou un clic droit dans la fenêtre la ferme."""

    def __init__(self, columns, side: str):
        super().__init__(columns.win, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.columns, self.side = columns, side
        self.setObjectName('columnPanel')
        self.setFrameShape(QFrame.Shape.StyledPanel)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 6, 8)
        lay.setSpacing(4)
        self.body = None
        self._due = False
        self._watching = False                           # le filtre « clic ailleurs » posé sur l'application
        self.refresh()

    def rows(self) -> list:
        """Les panneaux listés : ceux de cette colonne d'abord, puis les autres, par nom."""
        c = self.columns
        return sorted(c.docks(), key=lambda d: (c.side(d) != self.side, full_title(d).lower()))

    def shown_here(self, dock) -> bool:
        return self.columns.side(dock) == self.side and not dock.isHidden()

    def refresh_later(self) -> None:
        if not self._due:
            self._due = True
            QTimer.singleShot(0, self.refresh)

    def refresh(self) -> None:
        """Les lignes refaites : un œil, le nom, où le panneau est s'il n'est pas dans cette colonne."""
        self._due = False
        try:
            lay = self.layout()
        except RuntimeError:                             # fenêtre détruite entre-temps
            return
        if self.body is not None:
            self.body.hide()
            self.body.deleteLater()
        # le tableau commun aux deux colonnes : Gauche, Masqué, Droite pour chaque panneau (pas tout de suite refait
        # après un choix : le bouton cliqué est encore là)
        self.body = PanelRows(self.columns, self.side, done=self.refresh_later, parent=self)
        self.eyes, self.choices = self.body.eyes, self.body.choices
        lay.addWidget(self.body)
        self.body.show()
        lay.activate()                                   # la taille de la fenêtre d'après ses lignes neuves
        right = self.geometry().right() if self.isVisible() else None
        self.resize(self.sizeHint())
        if right is not None:
            self.clamp(right)                            # élargie vers la gauche, sous son bouton

    def clamp(self, right=None) -> None:
        """Le bord droit gardé (`right`), la fenêtre dans l'écran où elle est."""
        from PySide6.QtGui import QGuiApplication
        g = self.geometry()
        if right is not None:
            g.moveRight(right)
        scr = QGuiApplication.screenAt(g.center()) or self.screen()
        if scr is not None:
            a = scr.availableGeometry()
            g.moveLeft(max(a.left(), min(g.left(), a.right() - g.width())))
            g.moveTop(max(a.top(), min(g.top(), a.bottom() - g.height())))
        self.move(g.topLeft())

    def _eye(self, dock, on: bool) -> None:
        self.columns.show_in(dock, self.side, on)
        self.refresh_later()                             # pas tout de suite : l'œil cliqué est encore là

    def contextMenuEvent(self, ev):                      # noqa: N802 (API Qt)
        self.close()
        ev.accept()

    # --- un clic ailleurs la ferme, comme un menu (sans prendre la souris ni le clavier : le clic va où il est fait) --
    def showEvent(self, ev):                             # noqa: N802 (API Qt)
        super().showEvent(ev)
        app = QApplication.instance()
        if app is not None and not self._watching:
            app.installEventFilter(self)
            self._watching = True

    def hideEvent(self, ev):                             # noqa: N802 (API Qt)
        self._unwatch()
        super().hideEvent(ev)

    def _unwatch(self) -> None:
        app = QApplication.instance()
        if self._watching and app is not None:
            app.removeEventFilter(self)
        self._watching = False

    def eventFilter(self, obj, ev):                      # noqa: N802 (API Qt)
        t = ev.type()
        if t in (QEvent.Type.MouseButtonPress, QEvent.Type.NonClientAreaMouseButtonPress) and self.isVisible():
            try:
                at = ev.globalPosition().toPoint()
            except (AttributeError, RuntimeError):
                return False
            if not self.frameGeometry().contains(at):    # ailleurs : dans VectorDrive, hors de la fenêtre
                import time
                # un second clic droit sur son bouton la ferme sans la rouvrir (le menu vient au relâchement)
                self.columns._panel_shut = (self.side, time.monotonic())
                self.close()
        elif t in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress) and self.isVisible()                 and getattr(ev, 'key', lambda: None)() == Qt.Key.Key_Escape:
            # Échap : pour elle, où qu'aille le clavier (elle ne le prend pas : Windows ne l'active pas) — pas un
            # raccourci de la fenêtre ; fermée à l'appui, qui ne va pas plus loin
            ev.accept()
            if t == QEvent.Type.KeyPress:
                self.close()
            return True
        elif t == QEvent.Type.ApplicationDeactivate and self.isVisible():
            self.close()                                 # un clic dans une autre application
        return False

    def keyPressEvent(self, ev):                         # noqa: N802 (API Qt)
        if ev.key() == Qt.Key.Key_Escape:
            self.close()
            ev.accept()
            return
        super().keyPressEvent(ev)
