"""Colonnes de panneaux de la fenêtre principale (demandes du 14/11).

- Chaque panneau ancrable a la même barre de titre : son nom, puis « plein écran translucide », « détacher »
  (ou ancrer) et « fermer ».
- Demande du 27/11 (« pour tout élément s'affichant dans les colonnes, possibilité click droit seul dans la colonne.
  Reviser complétement cette gestion d'affichage trop brouillonne ») : un seul modèle, le même partout. Chaque panneau
  est « Seul à gauche » ou « Seul à droite » — son onglet dans le groupe d'onglets de cette colonne —, ou « Au-dessus
  de › X » / « Au-dessous de › X » — la colonne de X partagée en hauteur avec lui, et seulement alors — ; sinon masqué
  (ou détaché). Un clic droit sur tout ce qu'une colonne montre (la barre du panneau, son onglet, le fond de son
  contenu ; « Disposition › » au bas des menus propres de ses listes) ouvre ce même menu court, l'état du panneau
  coché (`state`) ; le tableau des panneaux dit la même chose (« onglet », « au-dessus de X »…). Un panneau qui ne
  partage plus la hauteur avec personne (son partenaire remis en onglet, envoyé ailleurs, rangé par rapport à un autre)
  reprend son onglet (`_release`) ; un panneau rangé au-dessus ou au-dessous d'un autre, masqué : son repère prend
  son onglet le temps qu'il revienne (`_lonely_targets`, `_rejoin`) ; le repère masqué puis remontré prend son onglet
  (round 1162). « En onglet avec › » et « Sortir des onglets » ne sont plus au menu ; leurs réglages d'avant (`seul/`,
  `onglet/`) sont remis à ce modèle une fois par poste (`MODEL_KEY`).
- Un panneau envoyé dans une colonne y prend son onglet, dans le groupe d'onglets de la colonne — jamais avec un
  panneau rangé à part ; sa colonne est retenue. Un panneau masqué, montré par son bouton, sa commande ou le menu de Qt,
  y prend aussi son onglet : il n'est jamais empilé avec un autre, sauf « Au-dessus de » / « Au-dessous de » choisi
  (demande du 23/11). Le groupe d'onglets est toujours en bas de la colonne : les panneaux
  rangés hors des onglets s'empilent au-dessus de lui (demande du 19/11). Depuis le 25/11 : jamais en onglet sur la
  colonne Datron (la fenêtre Programme et ses parties de plugin) ; sans groupe d'onglets, son propre bloc — à côté de
  la colonne Datron, sa propre colonne ; une colonne rouverte, la FAO rouverte ou refermée, une machine choisie, la
  disposition d'un lancement (une fois par poste) font de même.
- Le texte du programme fermé dans sa colonne à part : la colonne rétrécit de sa largeur, le dessin gagne la place ;
  rouvert, elle s'élargit d'autant (demande du 25/11).
- Avant le 27/11 : « En onglet avec › » un autre panneau de sa colonne, « Sortir des onglets » ; `tab_with` et `untab`
  restent pour le rangement d'office (Dimensions (F2) et Calques dans le même groupe d'onglets) et les réglages d'avant.
- « Au-dessus de › », « Au-dessous de › » un autre panneau : la colonne partagée en hauteur, les deux montrés à la
  fois (demande du 15/11, 8 h 40) ; retenu pour les lancements suivants. C'est le seul partage de colonne voulu : depuis
  le 27/11 (« FAO et opérations je n'arrive pas à lui octroyer son onglet colonne de droite »), « En onglet avec › » un
  panneau seul que l'utilisateur n'a pas sorti des onglets (le repère d'un « Au-dessous de », Dimensions d'office
  au-dessus de Calques…) les met tous deux dans le groupe d'onglets de la colonne, pas en paire à part (un panneau
  sorti des onglets par « Sortir des onglets » garde sa paire, round 1013) ; « Colonne de droite » (de gauche) d'un
  panneau déjà dans cette colonne mais hors de son groupe d'onglets lui donne son onglet, et « Droite » (« Gauche »)
  de sa ligne du tableau aussi, au lieu de le masquer (exception à la règle du 15/11 : un second clic masque) ; un
  panneau reposé à la souris dans des onglets oublie qu'il était rangé à part, et la disposition d'avant la FAO ne
  revient plus par-dessus à sa fermeture ; les opérations FAO rouvertes n'emmènent plus Dimensions hors du groupe. Une
  fois par poste (`FAO_TABS_KEY`), la palette FAO et les opérations laissées en paire à part par une version d'avant
  (réglages, ou disposition de la session) sont rendues à leur groupe d'onglets (un panneau FAO caché : à sa
  réouverture) ; « Au-dessus de / Au-dessous de » est gardé. La disposition d'un premier lancement (la palette FAO à gauche, les opérations en onglet à droite) n'est
  qu'un défaut.
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
from PySide6.QtWidgets import (QApplication, QDockWidget, QFrame, QGraphicsView, QGridLayout, QHBoxLayout, QLabel,
                               QMenu, QSizeGrip, QSizePolicy, QTabBar, QToolButton, QVBoxLayout, QWidget)

from ..i18n import tr

SIDES = ('gauche', 'droite')
#: les onglets des panneaux d'une colonne : 'court' (une icône et un libellé court ; d'office) ou 'entier' (le titre du
#: panneau, comme avant) — demande du 15/11, 22 h 30 : « Onglets colonnes pas assez de place »
TAB_MODES = ('court', 'entier')
#: icône d'onglet des panneaux du cœur, par nom de panneau
TAB_ICONS = {'dims': 'tab_dims', 'layers': 'tab_layers', 'symbols': 'tab_library', 'fao': 'tab_paths',
             'fao_liste': 'tab_ops', 'programme': 'tab_program', 'polices': 'tab_fonts',
             'assistant': 'tab_assistant', 'couleur': 'themes', 'programme_texte': 'tab_program'}
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
             'fao_liste': tr('Opérations'), 'programme': tr('Programme'), 'polices': tr('Police'),
             'assistant': tr('Assistant'), 'programme_texte': tr('Texte')}
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
ON_DEMAND = ('polices', 'accrochages', 'historique', 'assistant', 'couleur')
KEY = 'panneaux_colonnes'
#: réglage : le rangement d'office de Dimensions (F2) et Calques, décidé une fois par poste - 'dessus' (poste neuf,
#: depuis 0.928.0 : Dimensions au-dessus de Calques, réponse du 17/11 à la question 36) ou 'onglet' (poste déjà servi :
#: les deux en onglets, comme avant)
F2_KEY = f'{KEY}/f2_rangement'
#: réglages de la fenêtre (sa place à la fermeture, `MainWindow.GEOMETRY_KEY` ; plein écran ou non, et la barre des
#: tâches, écrits même en plein écran) : l'un d'eux présent, le poste a déjà servi
USED_KEYS = ('fenetre/geometrie', 'fenetre/plein_ecran', 'fenetre/plein_ecran_barre')
#: réglage : les panneaux restés seuls hors des onglets sans y avoir été rangés ont été remis dans le groupe de leur
#: colonne (une fois par poste, round 1162)
REGROUPED_KEY = f'{KEY}/regroupes'
#: réglage : la palette FAO et les opérations rendues à leur groupe d'onglets (une fois par poste, demande du 27/11 :
#: une version d'avant les laissait en paire à part, la colonne partagée)
FAO_TABS_KEY = f'{KEY}/fao_onglets'
FAO_KEYS_KEY = f'{KEY}/fao_onglets_cles'        # leurs réglages `seul/`, `onglet/` déjà remis en ordre
FAO_NAMES = ('fao', 'fao_liste')
#: réglage : le modèle de disposition du 27/11 en place (« Seul à gauche / à droite », « Au-dessus de / Au-dessous
#: de »), les réglages `seul/` et `onglet/` d'avant remis à ce modèle (une fois par poste)
MODEL_KEY = f'{KEY}/modele'
#: jamais proposés comme repère d'un « Au-dessus de / Au-dessous de » : la fenêtre Programme et son texte
NOT_PARTNERS = ('programme', 'programme_texte')
#: la largeur laissée au dessin, au moins, quand le texte du programme rouvert élargit sa colonne (px)
DRAWING_MIN = 320


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
                ('fermer', '✕', tr('Masquer le panneau'), lambda: columns.close(dock))):   # le mot du menu (27/11)
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
        self._settling = False                           # la colonne refaite : pas de nouveau tour
        self._settle_due = False
        self._sep_down = False                           # un séparateur de colonnes tiré à la souris (25/11)
        self._freeing = False                            # `free_program` en cours (`put_text_dock` la rappelle)
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
        dock._vd_was_hidden = dock.isHidden()            # masqué : montré plus tard, il prendra son onglet
        dock.installEventFilter(self)
        dock.visibilityChanged.connect(lambda _v: self.sync())
        dock.dockLocationChanged.connect(lambda _a, d=dock: self._located(d))
        dock.topLevelChanged.connect(lambda f, d=dock: (self._place_grip(d), self._docked(d, f), self.sync()))

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
        if not self._busy and dock is not getattr(self.win, 'dock_program_text', None):
            side = self.side(dock)
            if side:
                st = self._st()
                name = dock.objectName()
                if str(st.value(f'{KEY}/place/{name}', '') or '') not in ('', side):   # glissé dans l'autre colonne
                    st.remove(f'{KEY}/partage/{name}')
                    self._unsplit_from(name)
                st.setValue(f'{KEY}/place/{name}', side)
        self.sync()

    def _docked(self, dock, floating: bool) -> None:
        """Le panneau ancré de nouveau hors de nos fonctions — reposé à la souris, un double clic sur sa barre ; pas
        le retour du plein écran translucide — : regardé une fois les places faites (`_hand_docked`)."""
        try:
            if floating or self._busy or self._settling or not self.win.isVisible():
                return
        except RuntimeError:                             # fenêtre détruite entre-temps
            return
        ov = self.overlay(dock, create=False)
        if ov is not None and ov.active:
            return
        QTimer.singleShot(0, self, lambda d=dock: self._hand_docked(d))

    def _partners_alone(self, name: str, keep=()) -> None:
        """Ceux rangés au-dessus ou au-dessous de `name` (sauf `keep`) ne le sont plus : `name` vient de prendre son
        onglet. Depuis le 27/11 (un seul modèle : son onglet, ou au-dessus / au-dessous d'un autre), ils reprennent
        aussi le leur (`_release`) ; avant, ils restaient à part, seuls (`seul/`)."""
        st = self._st()
        gone = [k for k, target in self._shares().items() if target == name and k not in keep]
        for k in gone:
            st.remove(f'{KEY}/partage/{k}')
            st.remove(f'{KEY}/seul/{k}')
        self._release(gone)

    def _hand_docked(self, dock) -> None:
        """Le panneau reposé à la main (demande du 27/11) : la disposition d'avant la FAO n'est plus rendue à sa
        fermeture (elle le défaisait) ; reposé dans des onglets, il n'est plus rangé au-dessus ou au-dessous d'un autre
        (ceux rangés par rapport à lui : leur onglet, comme `_joined`), et dans le groupe d'onglets de sa colonne, plus
        « sorti des onglets » (Dimensions d'office au-dessus de Calques : retenu en onglet) : le lancement suivant ne le
        ressort pas. Reposé seul, rien n'est retenu (remontré plus tard, il prend son onglet)."""
        w = self.win
        try:
            if self._busy or dock.isFloating() or dock.isHidden() or not w.isVisible():
                return
        except RuntimeError:                             # panneau ou fenêtre détruits entre-temps
            return
        side = self.side(dock)
        if side is None or self._datron(dock) or dock is getattr(w, 'dock_program_text', None):
            return
        w._docks_before_cam = None                       # rangé à la main : fermer la FAO ne le défait pas
        mates = w.tabifiedDockWidgets(dock)
        if not mates or not self.host_ok(mates):
            return
        st, name = self._st(), dock.objectName()
        before = self.split_names()
        st.remove(f'{KEY}/partage/{name}')
        if dock in self.main_group(side):
            st.remove(f'{KEY}/seul/{name}')
            if str(st.value(f'{KEY}/onglet/{name}', '') or '') not in ('', *(m.objectName() for m in mates)):
                st.remove(f'{KEY}/onglet/{name}')
            self._partners_alone(name)                   # ses repérés : leur onglet aussi (27/11)
            self._joined(dock, mates)                    # (Dimensions retenu en onglet)
        else:                                            # avec un panneau rangé à part : ce couple, retenu
            self._partners_alone(name)
            st.setValue(f'{KEY}/onglet/{name}', mates[0].objectName())
            st.remove(f'{KEY}/seul/{name}')
        st.setValue(f'{KEY}/place/{name}', side)
        self._release(before - self.split_names() - {name})   # son repère, plus partagé : son onglet (27/11)

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
        prog = getattr(self.win, 'program_panel', None)
        if dock is getattr(self.win, 'dock_program_text', None) and prog is not None:
            self._quiet(lambda: dock.setFloating(False))  # la colonne du texte : collée à celle du programme,
            prog.put_text_dock(side)                     # jamais en onglet
            if show:
                self._quiet(lambda: (dock.setVisible(True), dock.raise_()))
            return
        ov = self.overlay(dock, create=False)
        if ov is not None and ov.active:
            ov.set_active(False)
        there = [d for d in self.column(side) if d is not dock]
        others = [d for d in there if not d.isHidden()] or there
        hidden = dock.isHidden()
        self.win._docks_before_cam = None                # la disposition d'avant la FAO n'est plus à rendre
        front = [d for d in others if self.in_front(d)] if not show else []
        was = self.side(dock)                            # en paire à part (onglets faits à la souris) : l'autre,
        pair = [] if was is None or dock in self.main_group(was) else self.win.tabifiedDockWidgets(dock)   # (27/11)
        group = self.main_group(side, without=dock)      # son onglet dans le groupe de la colonne (demande du 19/11)
        if not group and not [d for d in others if not d.isHidden()]:   # colonne cachée : son groupe
            group = [d for d in there if d.objectName() not in self.placed() and self.host_ok([d])][:1]
        if self._datron(dock):                           # la colonne Datron : jamais en onglet (demande du 25/11)
            group = []
        # à côté d'elle : sa propre colonne, si le dessin garde sa place (sinon sous la fenêtre Programme)
        near = not group and not self._datron(dock) and self._beside(side)
        beside = near and self._room_beside(dock)
        if near and not beside:
            self.free_program()                          # en groupe (voisins cachés), le partage en ferait un onglet

        def do():
            dock.setFloating(False)
            if beside:
                self.win.removeDockWidget(dock)
                self.win.addDockWidget(AREAS[side], dock, Qt.Orientation.Horizontal)
            elif near:
                self.win.removeDockWidget(dock)
                self.win.splitDockWidget(self.win.dock_program, dock, Qt.Orientation.Vertical)
            else:
                self.win.addDockWidget(AREAS[side], dock)
            if group:
                self.win.tabifyDockWidget(group[0], dock)
            if show:
                dock.setVisible(True)
                dock.raise_()
            else:
                dock.setVisible(not hidden)
                for d in front:                          # les onglets qui étaient devant le restent
                    d.raise_()
        self._quiet(do)
        text = prog.text_dock() if prog is not None and dock is getattr(self.win, 'dock_program', None) else None
        if text is not None and prog.split_wanted():
            prog._laid = None                            # la fenêtre Programme à parties ancrée : son texte refait
            if not text.isHidden():                      # à côté d'elle, pas elle sous leur zone (25/11) ; caché,
                prog.put_text_dock(side)                 # à sa réouverture
        if remember:
            st = self._st()
            before = self.split_names()
            st.setValue(f'{KEY}/place/{dock.objectName()}', side)
            st.remove(f'{KEY}/onglet/{dock.objectName()}')   # envoyé dans une colonne : ni en onglet retenu, ni seul
            st.remove(f'{KEY}/seul/{dock.objectName()}')
            st.remove(f'{KEY}/partage/{dock.objectName()}')  # ni au-dessus ou au-dessous d'un autre
            if dock.objectName() == 'dims' and group and str(st.value(F2_KEY, '') or '') == 'dessus':
                head = next((d for d in group if d.objectName() == 'layers'), group[0])
                st.setValue(f'{KEY}/onglet/dims', head.objectName())   # poste neuf : son onglet retenu (27/11)
            self._unsplit_from(dock.objectName())        # ni repère de ceux qui l'étaient par rapport à lui : eux, et
            free = before - self.split_names() - {dock.objectName()}   # le sien, reprennent leur onglet ; l'autre
            for m in pair:                               # de sa paire à part, resté seul, aussi
                if not m.isHidden() and not m.isFloating() and not self.win.tabifiedDockWidgets(m):
                    st.remove(f'{KEY}/seul/{m.objectName()}')
                    if str(st.value(f'{KEY}/onglet/{m.objectName()}', '') or '') == dock.objectName():
                        st.remove(f'{KEY}/onglet/{m.objectName()}')
                    free.add(m.objectName())
            self._release(free)
        if show:
            self.settle(side)

    def restore(self) -> None:
        """Au lancement : chaque panneau dans la colonne retenue pour lui, sans le montrer ni le mettre devant ; un
        panneau détaché d'office (le programme machine) aussi, une fois rangé dans une colonne."""
        for d in self.docks():
            want = str(self._st().value(f'{KEY}/place/{d.objectName()}', '') or '')
            if want in AREAS and self.side(d) != want:
                self.move(d, want, remember=False, show=False)
        st = self._st()
        self._model_once()                               # (une fois par poste : le modèle du 27/11)
        self._fao_keys_once()                            # (une fois par poste : FAO et Opérations en onglets, 27/11)
        for d in self.docks():                           # seuls d'abord, puis en onglet : comme on les a laissés,
            name = d.objectName()                        # quel que soit l'ordre des panneaux
            if (str(st.value(f'{KEY}/seul/{name}', '')).lower() in ('1', 'true')
                    and not st.value(f'{KEY}/onglet/{name}', '') and self.win.tabifiedDockWidgets(d)):
                self.untab(d, remember=False, show=False)
        for d in self.docks():
            want = str(st.value(f'{KEY}/onglet/{d.objectName()}', '') or '')
            other = next((o for o in self.docks() if o.objectName() == want), None) if want else None
            if other is not None and self.side(other) is not None and self.side(other) == self.side(d) \
                    and not self._program_pair(d, other):   # (avec la fenêtre Programme à parties : plus, 25/11)
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
        self._settle_due = True                          # les onglets en bas : à la première fois montrée

    # --- le modèle du 27/11 : seul à gauche, seul à droite, au-dessus ou au-dessous d'un autre ------------------------
    def _model_once(self) -> None:
        """Une fois par poste (`MODEL_KEY`), avant le rangement du lancement : les réglages d'avant le modèle du 27/11
        sont remis à ce modèle — « Sortir des onglets » (`seul/`) et « En onglet avec » (`onglet/`) retirés : chaque
        panneau qu'ils rangeaient reprend son onglet dans sa colonne. Gardés : « Au-dessus de / Au-dessous de »
        (`partage/`), la colonne de chacun (`place/`), et `onglet/dims` (Dimensions mis dans les onglets sur un poste
        neuf : « Seul à … »). Des réglages retirés : la disposition (celle d'une session) suit à la première fenêtre
        montrée (`_model_layout_once`) ; `MODEL_KEY` vaut 1 jusque-là (réglages remis, disposition à ranger), 2 ensuite
        — comme `FAO_KEYS_KEY` puis `FAO_TABS_KEY`."""
        st = self._st()
        done = str(st.value(MODEL_KEY, '') or '')
        if done in ('1', '2'):
            self._model_due = done == '1'                # (la disposition pas encore rangée : à la fenêtre montrée)
            return
        old = False
        for group in ('seul', 'onglet'):
            st.beginGroup(f'{KEY}/{group}')
            names = list(st.childKeys())
            st.endGroup()
            for n in names:
                if group == 'onglet' and n == 'dims':
                    continue
                st.remove(f'{KEY}/{group}/{n}')
                old = True
        st.setValue(MODEL_KEY, 1 if old else 2)          # rien d'avant : rien à ranger
        self._model_due = old

    def _model_layout_once(self) -> None:
        """À la première fenêtre montrée après `_model_once` (des réglages d'avant retirés) : les panneaux montrés hors
        du groupe d'onglets de leur colonne — seuls ou en paire à part, comme la disposition de la session les remet —
        sans y être rangés (`placed` : au-dessus ou au-dessous d'un autre, Dimensions d'office au-dessus de Calques) y
        reprennent leur onglet. Une colonne rangée côte à côte à la souris est laissée."""
        if not getattr(self, '_model_due', False):
            return
        try:
            if not self.win.isVisible() or self.win.isMinimized():
                return                                   # la fenêtre réduite : à la première fois montrée en grand
        except RuntimeError:
            return
        self._model_due = False
        placed, text = self.placed(), getattr(self.win, 'dock_program_text', None)
        for side in SIDES:
            blocks = [b for b in self.blocks(side) if self.host_ok(b)]
            main = self.main_group(side)
            if len(blocks) < 2 or not main or self._side_by_side(blocks):
                continue
            for b in blocks:
                if set(map(id, b)) == set(map(id, main)):
                    continue
                for d in b:
                    if d.objectName() not in placed and d is not text and not d.isFloating():
                        self.move(d, side, remember=False, show=False)
        self._st().setValue(MODEL_KEY, 2)                # rangé : plus jamais

    def _shares_where(self) -> dict:
        """{panneau : (son repère, 'dessus' | 'dessous')} retenus (« Au-dessus de », « Au-dessous de »)."""
        st = self._st()
        st.beginGroup(f'{KEY}/partage')
        try:
            out = {}
            for k in st.childKeys():
                target, _sep, where = str(st.value(k, '') or '').partition('|')
                out[k] = (target, 'dessus' if where == 'dessus' else 'dessous')
            return out
        finally:
            st.endGroup()

    def _apart(self, dock) -> bool:
        """`dock` est-il montré, ancré, hors de tout groupe d'onglets (sauf la colonne Datron) ?"""
        try:
            if dock.isHidden() or dock.isFloating():
                return False
        except RuntimeError:
            return False
        mates = self.win.tabifiedDockWidgets(dock)
        return not (mates and self.host_ok(mates))

    def partner(self, dock) -> tuple:
        """('dessus' | 'dessous', autre) : `dock` partage la hauteur de sa colonne avec `autre`, au-dessus ou au-dessous
        de lui — son choix retenu, celui de l'autre vu de son côté (le repère d'un « Au-dessous de » est au-dessus), ou
        Dimensions d'office au-dessus de Calques (poste neuf) ; (None, None) : avec personne. La vraie disposition
        compte (une session remise, un panneau glissé à la souris) : les deux montrés, hors des onglets, et leur ordre
        celui de la colonne — un partenaire masqué ou mis en onglets n'est pas coché au menu."""
        here = self.side(dock)
        if here is None or not self._apart(dock):
            return None, None
        by = {d.objectName(): d for d in self.docks()}
        name, shares = dock.objectName(), self._shares_where()

        def real(other):                                 # au-dessus ou au-dessous de lui, à l'écran
            try:
                self.win.layout().activate()
                up = other.mapTo(self.win, QPoint(0, 0)).y() < dock.mapTo(self.win, QPoint(0, 0)).y()
            except RuntimeError:
                return None
            return 'dessous' if up else 'dessus'
        if name in shares:
            target, where = shares[name]
            other = by.get(target)
            if other is not None and other is not dock and self.side(other) == here and self._apart(other):
                return real(other) or where, other
        for k, (target, where) in shares.items():
            other = by.get(k)
            if target == name and other is not None and other is not dock and self.side(other) == here \
                    and self._apart(other):
                return real(other) or ('dessous' if where == 'dessus' else 'dessus'), other
        st, layers = self._st(), by.get('layers')
        if name == 'dims' and str(st.value(F2_KEY, '') or '') == 'dessus' and not st.value(f'{KEY}/onglet/dims', '') \
                and layers is not None and not layers.isHidden() and self.side(layers) == here \
                and layers not in self.win.tabifiedDockWidgets(dock):
            return 'dessus', layers
        return None, None

    def state(self, dock) -> tuple:
        """La disposition du panneau dans le modèle du 27/11 : ('gauche' | 'droite', None) — son onglet dans le groupe
        de cette colonne (ou le seul bloc d'une colonne sans groupe, la colonne Datron) ; ('dessus' | 'dessous',
        autre) — au-dessus ou au-dessous de `autre` (`partner`) ; ('masque', None) ; ('detache', None) ; ('hors',
        None) : dans une colonne, mais rangé autrement (à la souris : seul hors des onglets, en paire à part)."""
        try:
            if dock.isHidden():
                return 'masque', None
            if dock.isFloating():
                return 'detache', None
        except RuntimeError:
            return 'masque', None
        here = self.side(dock)
        if here is None:
            return 'hors', None
        where, other = self.partner(dock)
        if other is not None:
            return where, other
        if self._datron(dock) or dock is getattr(self.win, 'dock_program_text', None):
            return here, None
        if dock in self.main_group(here) or not self.main_group(here, without=dock):
            return here, None
        return 'hors', None

    def _lonely_targets(self) -> None:
        """Un panneau rangé au-dessus ou au-dessous d'un autre a été masqué : son repère, resté seul hors des onglets,
        y reprend son onglet (demande du 27/11 : jamais un panneau laissé seul sans l'avoir choisi). Le choix du
        panneau masqué est gardé (`partage/`) : remontré, il revient près de son repère (`_rejoin`). Le repère masqué
        lui-même (son partenaire resté) : rien — remontré, il prend son onglet (round 1162)."""
        try:
            if self._busy or self._settling or not self.win.isVisible() or self.win.isMinimized():
                return
        except RuntimeError:
            return
        by = {d.objectName(): d for d in self.docks()}
        shares = self._shares()
        done = set()
        for k, target in shares.items():
            d, t = by.get(k), by.get(target)
            if d is None or t is None or not d.isHidden() or target in done or not self._apart(t) \
                    or self._datron(t) or t is getattr(self.win, 'dock_program_text', None):
                continue
            mine = by.get(shares.get(target, ''))       # encore partagé avec un autre panneau montré : laissé
            if (mine is not None and not mine.isHidden()) or any(
                    o != k and by.get(o) is not None and not by[o].isHidden()
                    for o, x in shares.items() if x == target):
                continue
            side = self.side(t)
            group = self.main_group(side, without=t) if side else []
            if not group:
                continue
            front = [x for x in group if self.in_front(x)]
            self._quiet(lambda g=group[0], x=t, f=front: (self.win.tabifyDockWidget(g, x), x.setVisible(True),
                                                          [m.raise_() for m in f]))
            done.add(target)
            self.settle(side)

    def _rejoin(self, dock) -> None:
        """`dock`, rangé au-dessus ou au-dessous d'un autre (`partage/`), vient d'être remontré : si son repère a pris
        son onglet pendant qu'il était masqué (`_lonely_targets`), ou lui-même est revenu dans des onglets, il retourne
        au-dessus ou au-dessous de lui (demande du 27/11)."""
        try:
            if self._busy or self._settling or dock.isHidden() or dock.isFloating() or not self.win.isVisible():
                return
        except RuntimeError:
            return
        target, _sep, where = str(self._st().value(f'{KEY}/partage/{dock.objectName()}', '') or '').partition('|')
        other = next((d for d in self.docks() if d.objectName() == target), None) if target else None
        if other is None or other is dock or other.isHidden() or other.isFloating() or self.side(other) is None:
            return
        if self._apart(dock) and self._apart(other) and self.side(dock) == self.side(other):
            return                                       # déjà à sa place
        self.split_with(dock, other, where != 'dessus', remember=False)

    def _release(self, names) -> None:
        """Ceux de `names` qui ne partagent plus la hauteur avec personne — leur partenaire remis en onglet, envoyé
        dans l'autre colonne ou rangé par rapport à un autre — reprennent leur onglet dans le groupe de leur colonne
        (modèle du 27/11 : jamais un panneau laissé seul hors des onglets sans l'avoir choisi). Pas ceux encore rangés à
        part (`placed` : un autre partage, Dimensions d'office au-dessus de Calques, le texte du programme), ni un
        panneau caché (remontré, il prendra son onglet), détaché, déjà en onglets ou de la colonne Datron."""
        try:
            if not names or not self.win.isVisible():
                return
        except RuntimeError:
            return
        placed = self.placed()
        for n in sorted(names):
            d = next((x for x in self.docks() if x.objectName() == n), None)
            try:
                if d is None or n in placed or d.isHidden() or d.isFloating() or self._datron(d):
                    continue
            except RuntimeError:                         # panneau détruit entre-temps
                continue
            side = self.side(d)
            mates = self.win.tabifiedDockWidgets(d)
            if side is None or (mates and self.host_ok(mates)):
                continue
            self._take_tab(d, side)

    def set_alone(self, dock, side: str) -> None:
        """« Seul à gauche » / « Seul à droite » (demande du 27/11) : le panneau montré (la FAO ouverte pour ses
        panneaux, comme par le tableau), son onglet dans le groupe d'onglets de cette colonne — plus au-dessus ni
        au-dessous d'un autre (`move`, retenu)."""
        if side not in AREAS:
            return
        if dock.isHidden() or dock.isFloating() or self.side(dock) != side:
            self.show_in(dock, side, True)
        if self.state(dock)[0] != side:
            self.move(dock, side)

    # --- FAO et Opérations rendus à leurs onglets, une fois par poste (demande du 27/11) ------------------------------
    def fao_migrated(self) -> bool:
        return str(self._st().value(FAO_TABS_KEY, '')).lower() in ('1', 'true')

    def _fao_keys_once(self) -> None:
        """Avant le rangement du lancement, tant que le poste n'a pas été remis en ordre (`FAO_TABS_KEY`) : ni la
        palette FAO ni les opérations ne restent « sorties des onglets », ni en onglet avec l'une l'autre ou avec un
        panneau sorti des onglets — la paire à part qu'une version d'avant laissait (« En onglet avec » un panneau
        seul). « Au-dessus de / Au-dessous de » (`partage/`), vrai choix, n'est jamais touché. Une seule fois
        (`FAO_KEYS_KEY`) : un choix fait ensuite, la disposition pas encore remise en ordre, est gardé."""
        st = self._st()
        if self.fao_migrated() or str(st.value(FAO_KEYS_KEY, '')).lower() in ('1', 'true'):
            return
        st.setValue(FAO_KEYS_KEY, True)
        alone = {d.objectName() for d in self.docks()
                 if str(st.value(f'{KEY}/seul/{d.objectName()}', '')).lower() in ('1', 'true')}
        for n in FAO_NAMES:
            want = str(st.value(f'{KEY}/onglet/{n}', '') or '')
            if want in FAO_NAMES or want in alone:
                st.remove(f'{KEY}/onglet/{n}')
        for n in FAO_NAMES:
            st.remove(f'{KEY}/seul/{n}')

    def _fao_docks_main(self) -> list:
        w = self.win
        return [d for d in (getattr(w, 'dock_cam', None), getattr(w, 'dock_paths', None)) if d is not None]

    def _fao_layout_once(self) -> None:
        """À la première fenêtre montrée (la disposition de la session remise), tant que le poste n'a pas été remis en
        ordre : la palette FAO et les opérations montrées, hors de leur groupe d'onglets sans « Au-dessus de /
        Au-dessous de », y prennent leur onglet (`move`, retenu). La FAO fermée : à sa première ouverture
        (`fao_opened`). Le réglage n'est écrit qu'une fois ce rangement fait."""
        if self.fao_migrated():
            return
        try:
            if not self.win.isVisible() or self.win.isMinimized():
                self._fao_due = True                     # la fenêtre réduite : à la première fois montrée en grand
                return
        except RuntimeError:
            return
        act = getattr(self.win, 'A', {}).get('cam_panel')
        docks = self._fao_docks_main()
        if not docks or act is None or not act.isChecked() or all(d.isHidden() for d in docks):
            self._fao_due = True                         # FAO fermée (ou rangée par l'onglet CAD) : plus tard
            return
        self._fao_due = not self._fao_tabs(docks)

    def fao_opened(self) -> None:
        """La FAO ouverte (`_toggle_cam_panel`, l'onglet FAO du ruban), un panneau FAO montré (sa colonne rouverte,
        les opérations rouvertes seules, la fenêtre réduite rendue) : le rangement de `_fao_layout_once` s'il
        attendait."""
        if not getattr(self, '_fao_due', False) or self.fao_migrated() or self._busy or self._settling:
            return
        try:
            if not self.win.isVisible() or self.win.isMinimized():
                return
        except RuntimeError:
            return
        docks = self._fao_docks_main()
        if docks and any(not d.isHidden() for d in docks):
            self._fao_due = not self._fao_tabs(docks, settle=True)

    def _fao_tabs(self, docks, settle: bool = False) -> bool:
        """Le rangement : chaque panneau FAO montré hors du groupe d'onglets de sa colonne y prend son onglet ; une
        paire FAO devenue le groupe de la colonne y reçoit les panneaux restés seuls (`regroup` : pas ceux rangés à
        part). Les panneaux rangés par l'utilisateur (`split_names`, `chosen`) sont laissés. Rend vrai, et écrit le
        réglage, si aucun panneau FAO ancré n'a été sauté parce que caché (sa colonne cachée, les opérations fermées
        seules) : sinon, à sa réouverture."""
        skip, sides, waiting = self.split_names() | self.chosen(), set(), False
        for d in docks:
            try:
                if d.isFloating() or d.objectName() in skip or self._datron(d):
                    continue
                if d.isHidden():
                    waiting = True
                    continue
            except RuntimeError:
                continue
            side = self.side(d)
            if side is None:
                continue
            sides.add(side)
            if d not in self.main_group(side) and self.main_group(side, without=d):
                self.move(d, side, remember=True, show=False)
        for side in sides:                               # [Calques] seul + [FAO, Opérations] : tous ensemble
            blocks = self.blocks(side)
            if len(blocks) > 1 and not self._side_by_side([b for b in blocks if self.host_ok(b)]):
                self.regroup([b[0] for b in blocks if len(b) == 1])
        if not waiting:
            self._st().setValue(FAO_TABS_KEY, True)
        for side in sides if settle else ():
            self.settle(side)
        return not waiting

    # --- le groupe d'onglets toujours en bas de la colonne (demande du 19/11) ---------------------------------------
    def placed(self) -> set:
        """Les panneaux rangés à part, hors du groupe d'onglets de leur colonne : sortis des onglets, au-dessus ou
        au-dessous d'un autre (et ce repère), Dimensions au-dessus de Calques d'office (poste neuf)."""
        st = self._st()
        out = self.split_names()
        for d in self.docks():
            if str(st.value(f'{KEY}/seul/{d.objectName()}', '')).lower() in ('1', 'true'):
                out.add(d.objectName())
        if str(st.value(F2_KEY, '') or '') == 'dessus' and not st.value(f'{KEY}/onglet/dims', ''):
            out.add('dims')
        out.add('programme_texte')                      # le texte du programme : sa colonne à part
        return out

    def chosen(self) -> set:
        """Les panneaux que l'utilisateur a lui-même rangés à part — sortis des onglets, mis au-dessus ou au-dessous
        d'un autre (pas ce repère) — et le texte du programme : remontrés, ils restent où ils sont ; tout autre panneau
        remontré prend son onglet dans le groupe (demande du 25/11 : Dimensions d'office au-dessus de Calques, ou le
        repère d'un « Au-dessous de », aussi)."""
        st = self._st()
        out = set(self._shares())
        for d in self.docks():
            if str(st.value(f'{KEY}/seul/{d.objectName()}', '')).lower() in ('1', 'true'):
                out.add(d.objectName())
        out.add('programme_texte')
        return out

    def _datron(self, dock) -> bool:
        """Le panneau fait-il la colonne Datron : le texte du programme, ou la fenêtre Programme quand des parties
        de plugin y sont montrées (`add_panel(host='programme')`) ?"""
        w = self.win
        if dock is getattr(w, 'dock_program_text', None):
            return True
        prog = getattr(w, 'program_panel', None)
        return dock is getattr(w, 'dock_program', None) and prog is not None and bool(prog.sections_shown())

    def host_ok(self, block) -> bool:
        """Un bloc peut-il accueillir l'onglet d'un autre panneau : pas la colonne Datron, ni un groupe d'onglets où
        elle est (demande du 25/11 : jamais en onglet par-dessus la fenêtre Programme et ses parties)."""
        return not any(self._datron(m) for m in block)

    def _beside(self, side: str) -> bool:
        """La colonne Datron (la fenêtre Programme et ses parties) est-elle montrée dans la colonne `side` ?"""
        dp = getattr(self.win, 'dock_program', None)
        return dp is not None and not dp.isHidden() and self.side(dp) == side and self._datron(dp)

    def _room_beside(self, dock) -> bool:
        """Une colonne de plus pour `dock`, à côté de la colonne Datron, laisserait-elle au dessin `DRAWING_MIN` ?"""
        central = self.win.centralWidget()
        need = max(dock.minimumSizeHint().width(), dock.sizeHint().width()) + self._gap()
        return central is None or central.width() - need >= DRAWING_MIN

    def free_program(self) -> bool:
        """La fenêtre Programme devenue colonne Datron (ses parties de plugin montrées) encore en onglet avec
        d'autres panneaux — une disposition d'avant, ancrée sous une autre machine — : sortie de son groupe, son texte
        refait à côté d'elle ; le groupe accueille de nouveau les panneaux remontrés (25/11). Rend vrai si elle en est
        sortie."""
        w = self.win
        dp, prog = getattr(w, 'dock_program', None), getattr(w, 'program_panel', None)
        if getattr(self, '_freeing', False):             # déjà en cours (`put_text_dock` la rappelle) : une fois
            return False
        try:
            if dp is None or prog is None or dp.isHidden() or dp.isFloating() or not self._datron(dp):
                return False
            w.layout().activate()                        # les onglets à jour avant de les lire
            side, mates = self.side(dp), w.tabifiedDockWidgets(dp)
        except RuntimeError:                             # fenêtre détruite entre-temps
            return False
        if side is None or not (mates or self._in_tabs(dp)):
            return False

        def do():
            w.removeDockWidget(dp)
            w.addDockWidget(AREAS[side], dp, Qt.Orientation.Vertical)
            dp.setVisible(True)
            dp.raise_()
        self._freeing = True
        try:
            self._quiet(do)
            prog._laid = None
            prog.put_text_dock(side)
        finally:
            self._freeing = False
        return True

    def _in_tabs(self, dock) -> bool:
        """`dock` est-il dans un groupe d'onglets, même seul montré (ses voisins cachés) ? `tabifiedDockWidgets` ne
        compte que les montrés ; la barre d'onglets de Qt le porte encore (vérifié au round 1162 : un panneau partagé
        sous lui y deviendrait alors un onglet)."""
        try:
            import shiboken6
            from PySide6.QtWidgets import QTabBar
            ptr = int(shiboken6.getCppPointer(dock)[0])
            bars = self.win.findChildren(QTabBar, options=Qt.FindChildOption.FindDirectChildrenOnly)
            return any(int(bar.tabData(i) or 0) == ptr for bar in bars for i in range(bar.count()))
        except (ImportError, TypeError, ValueError, RuntimeError):
            return False

    def _program_pair(self, *docks) -> bool:
        """La fenêtre Programme ou son texte parmi `docks`, des parties de plugin existant (la colonne Datron) : une
        clé `onglet/` d'avant qui les met en onglet n'est pas réappliquée au lancement (25/11)."""
        w = self.win
        if not getattr(getattr(w, 'program_panel', None), 'hosted', None):
            return False
        mine = (getattr(w, 'dock_program', None), getattr(w, 'dock_program_text', None))
        return any(d is not None and d in mine for d in docks)

    def _joined(self, dock, group) -> None:
        """`dock` remontré a pris son onglet : ce qui le rangeait à part ne le ressort pas au lancement suivant — un
        panneau rangé au-dessus ou au-dessous de lui reste à part, seul ; Dimensions d'office au-dessus de Calques
        est retenu en onglet."""
        st, name = self._st(), dock.objectName()
        for k, target in self._shares().items():
            if target == name:
                st.remove(f'{KEY}/partage/{k}')
                st.setValue(f'{KEY}/seul/{k}', True)
        if name == 'dims' and str(st.value(F2_KEY, '') or '') == 'dessus' and not st.value(f'{KEY}/onglet/dims', ''):
            other = next((d for d in group if d.objectName() == 'layers'), group[0])
            st.setValue(f'{KEY}/onglet/dims', other.objectName())

    def _in_program_column(self, dock) -> bool:
        """`dock` est-il empilé dans la colonne de la fenêtre Programme ou dans celle de son texte ?"""
        x = dock.mapTo(self.win, QPoint(0, 0)).x()
        for d in (getattr(self.win, 'dock_program', None), getattr(self.win, 'dock_program_text', None)):
            if d is not None and not d.isHidden() and not d.isFloating() and \
                    abs(d.mapTo(self.win, QPoint(0, 0)).x() - x) <= 2:
                return True
        return False

    def blocks(self, side: str) -> list:
        """Les blocs montrés de la colonne `side`, de haut en bas : un panneau seul, ou un groupe d'onglets (celui de
        devant d'abord)."""
        col = [d for d in self.column(side) if not d.isHidden()]
        try:
            self.win.layout().activate()                 # les places d'après les derniers changements
        except RuntimeError:
            return []
        seen, out = set(), []
        for d in col:
            if id(d) in seen:
                continue
            group = [d] + [m for m in self.win.tabifiedDockWidgets(d) if m in col and m is not d]
            group.sort(key=lambda m: not self.in_front(m))
            seen.update(id(m) for m in group)
            out.append(group)
        # un onglet de derrière est mis hors de la fenêtre par Qt : la place du bloc est celle du plus bas
        out.sort(key=lambda b: max(m.mapTo(self.win, QPoint(0, 0)).y() for m in b))
        return out

    def main_group(self, side: str, without=None) -> list:
        """Le groupe d'onglets de la colonne : le plus fourni des blocs montrés, sauf un panneau seul rangé à part
        et la colonne Datron, seule ou en onglets (le plus bas à égalité) ; [] : aucun. `without` : un panneau qui n'y
        compte pas."""
        placed = self.placed()
        best = []
        for b in self.blocks(side):
            b = [m for m in b if m is not without]
            # des onglets (même avec un panneau rangé à part d'office, Dimensions avec la FAO), ou un panneau seul
            # que l'utilisateur n'a pas rangé à part
            if b and (len(b) > 1 or b[0].objectName() not in placed) and len(b) >= len(best) and self.host_ok(b):
                best = b
        return best

    def settle(self, side: str) -> bool:
        """Le groupe d'onglets de la colonne mis en bas, sous les panneaux rangés à part, s'il n'y est pas : la
        colonne refaite dans cet ordre, les mêmes devant, les mêmes hauteurs. Rend vrai si elle a été refaite."""
        if side not in AREAS or self._settling:
            return False
        if not self.win.isVisible() or self.win.isMinimized():
            self._settle_due = True                      # les places ne se lisent pas : à la prochaine fois montrée
            return False
        blocks = self.blocks(side)
        main = self.main_group(side)
        if len(blocks) < 2 or not main or set(map(id, blocks[-1])) == set(map(id, main)):
            return False
        if self._side_by_side(blocks):                   # rangés côte à côte à la souris : laissés comme ils sont
            return False
        k = next(i for i, b in enumerate(blocks) if set(map(id, b)) == set(map(id, main)))
        above, below = blocks[:k], blocks[k + 1:]
        if above and len(above[-1]) == 1 and all(len(b) == 1 for b in below):
            return self._lift(above[-1][0], [b[0] for b in below])
        order = [b for b in blocks if set(map(id, b)) != set(map(id, main))] + [main]
        heights = [max(1, b[0].height()) for b in order]   # celle de l'onglet de devant
        front = [b[0] for b in order]
        placed = self.placed()
        # les panneaux cachés de la colonne (la FAO fermée…) : leur onglet dans le groupe, pour quand ils reviennent
        asleep = [d for d in self.column(side) if d.isHidden() and d.objectName() not in placed
                  and not self._datron(d)]                # (ni la colonne Datron cachée : jamais en onglet, 25/11)

        def do():
            for b in order:
                for d in b:
                    self.win.removeDockWidget(d)
            for b in order:
                self.win.addDockWidget(AREAS[side], b[0], Qt.Orientation.Vertical)
                for d in b[1:]:
                    self.win.tabifyDockWidget(b[0], d)
                for d in b:
                    d.setVisible(True)
            for d in asleep:
                self.win.tabifyDockWidget(main[0], d)
                d.setVisible(False)
            for d in front:
                d.raise_()
            self.win.resizeDocks(front, heights, Qt.Orientation.Vertical)
        self._settling = True
        try:
            self._quiet(do)
        finally:
            self._settling = False
        return True

    def _lift(self, anchor, docks: list) -> bool:
        """Les panneaux seuls `docks`, sous le groupe d'onglets, remis juste sous `anchor` (seul, au-dessus du groupe) :
        le groupe n'est pas touché (ni caché, ni remontré), ses onglets restent comme ils sont."""
        heights = [max(1, d.height()) for d in docks]

        def do():
            prev = anchor
            for d in docks:
                self.win.removeDockWidget(d)
                self.win.splitDockWidget(prev, d, Qt.Orientation.Vertical)
                d.setVisible(True)
                prev = d
            self.win.resizeDocks(docks, heights, Qt.Orientation.Vertical)
        self._settling = True
        try:
            self._quiet(do)
        finally:
            self._settling = False
        return True

    def _side_by_side(self, blocks: list) -> bool:
        """Deux blocs de la colonne l'un à côté de l'autre (glissés ainsi à la souris) ?"""
        boxes = []
        for b in blocks:
            at = b[0].mapTo(self.win, QPoint(0, 0))
            boxes.append((at.x(), at.y(), at.y() + b[0].height()))
        for i, (xa, ya, za) in enumerate(boxes):
            for xb, yb, zb in boxes[i + 1:]:
                if abs(xa - xb) > 2 and min(za, zb) - max(ya, yb) > 4:
                    return True
        return False

    # --- en onglets dans une colonne (demande du 14/11, soir) ----------------------------------------------------
    def f2_mode(self) -> str:
        """Le rangement d'office de Dimensions et Calques (`F2_KEY`), décidé au premier lancement qui le demande."""
        st = self._st()
        mode = str(st.value(F2_KEY, '') or '')
        if mode not in ('dessus', 'onglet'):
            mode = 'onglet' if any(st.contains(k) for k in USED_KEYS) else 'dessus'
            st.setValue(F2_KEY, mode)
        return mode

    def _f2_with_layers(self) -> None:
        """D'office, sur un poste neuf, Dimensions (F2) au-dessus de Calques, les deux montrés (réponse du 17/11 à la
        question 36 : les panneaux rangés comme à leur création, Calques devant dans son groupe d'onglets) ; sur un poste déjà servi (`USED_KEYS`), dans le même groupe d'onglets
        de leur colonne, Dimensions devant, comme avant. Rien de cela s'ils ont été séparés (« Sortir des onglets »
        sur l'un ou l'autre), rangés par rapport à un autre ou repère d'un autre (27/11), si Dimensions est en
        onglet avec un autre panneau ou s'ils sont dans deux colonnes."""
        st = self._st()
        first = str(st.value(F2_KEY, '') or '') not in ('dessus', 'onglet')
        mode = self.f2_mode()
        shared = self.split_names()                      # rangés par rapport à un autre, ou son repère (27/11)
        if st.value(f'{KEY}/onglet/dims', '') or any(
                str(st.value(f'{KEY}/seul/{n}', '')).lower() in ('1', 'true') or n in shared
                for n in ('dims', 'layers')):
            return
        dims = next((d for d in self.docks() if d.objectName() == 'dims'), None)
        layers = next((d for d in self.docks() if d.objectName() == 'layers'), None)
        if dims is None or layers is None:
            return
        if self.side(layers) is None or self.side(dims) != self.side(layers):
            return
        if mode == 'dessus':                             # les panneaux comme créés : Dimensions au-dessus du groupe
            if first and not layers.isHidden():          # de Calques (Bibliothèque, FAO...), Calques devant
                self._quiet(layers.raise_)
            return
        if layers in self.win.tabifiedDockWidgets(dims):
            return
        if self.tab_with(dims, layers, remember=False, show=False) and not dims.isHidden():
            self._quiet(dims.raise_)

    def tab_with(self, dock, other, remember: bool = True, show: bool = True) -> bool:
        """`dock` en onglet avec `other`, dans la colonne de `other` (Dimensions (F2) et Calques, par exemple) ; mis
        devant si `show` (sinon les onglets qui étaient devant le restent). Retenu (`remember`) : au lancement
        suivant, ils se retrouvent ensemble. Rend vrai s'ils partagent un onglet. Choisi (`remember`) avec un panneau
        seul de la colonne : les deux prennent leur onglet dans le groupe d'onglets de la colonne, plutôt qu'une paire
        à part (`_group_to_join`, demande du 27/11)."""
        side = self.side(other)
        if side is None or dock is other:
            return False
        group = self._group_to_join(dock, other, side) if remember else []
        if group:
            return self._bring_into_group(dock, other, group, side, show)
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
        if show:
            self.settle(side)
        self.sync()
        return other in self.win.tabifiedDockWidgets(dock)

    def _group_to_join(self, dock, other, side: str) -> list:
        """« En onglet avec › » `other` choisi pour `dock` alors que `other` est seul dans la colonne `side` sans que
        l'utilisateur l'y ait rangé (le repère d'un « Au-dessous de », Dimensions d'office au-dessus de Calques, un
        panneau resté seul) : le groupe d'onglets de la colonne que les deux doivent rejoindre — en faire une paire à
        part partagerait la colonne (demande du 27/11). [] : une paire comme avant — pas de groupe, ou `other` rangé à
        part par l'utilisateur (« Sortir des onglets », « Au-dessus de » : `chosen`, round 1013)."""
        try:
            if dock.isHidden() or other.isHidden() or other.isFloating() or self._datron(dock) \
                    or self.win.tabifiedDockWidgets(other) or not self.host_ok([other]):
                return []
        except RuntimeError:
            return []
        if other.objectName() in self.chosen():
            return []
        return [m for m in self.main_group(side, without=dock) if m is not other]

    def _bring_into_group(self, dock, other, group: list, side: str, show: bool = True) -> bool:
        """`dock` et `other` en onglets dans `group`, le groupe de la colonne `side` (`_group_to_join`) : ni l'un ni
        l'autre n'est plus rangé à part ; un troisième rangé au-dessus ou au-dessous de l'un d'eux reste à part, seul
        (`_partners_alone`, comme `_joined`) ; retenus en onglet avec le panneau de tête du groupe (Calques de
        préférence) pour les lancements suivants. `dock` mis devant si `show`. Rend vrai s'ils partagent un onglet."""
        head = next((m for m in group if m.objectName() == 'layers'), group[0])
        front = [d for d in self.column(side) if self.in_front(d)] if not show else []

        def do():
            for x in (other, dock):
                if x not in self.win.tabifiedDockWidgets(head):
                    if self.side(x) != side:
                        x.setFloating(False)
                        self.win.addDockWidget(AREAS[side], x)
                    self.win.tabifyDockWidget(head, x)
                x.setVisible(True)
            if show:
                dock.raise_()
            else:
                for d in front:
                    d.raise_()
        self._quiet(do)
        self.win._docks_before_cam = None                # fermer la FAO ne défait pas ce choix
        st, pair = self._st(), (dock.objectName(), other.objectName())
        for x in (dock, other):
            name = x.objectName()
            st.setValue(f'{KEY}/onglet/{name}', head.objectName())
            st.remove(f'{KEY}/partage/{name}')
            st.remove(f'{KEY}/seul/{name}')
            self._partners_alone(name, keep=pair)
            st.setValue(f'{KEY}/place/{name}', side)
        if show:
            self.settle(side)
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
        if show:
            self.settle(side)                            # au-dessus du groupe d'onglets, qui reste en bas
        self.sync()
        return not self.win.tabifiedDockWidgets(dock)

    def split_with(self, dock, other, below: bool = True, remember: bool = True, show: bool = True) -> bool:
        """`dock` au-dessous (`below`) ou au-dessus de `other`, dans la colonne de `other` : la colonne partagée en
        hauteur, les deux montrés à la fois (demande du 15/11, 8 h 40). Sous un panneau en onglets (Calques avec la
        Bibliothèque…), `dock` va sous leur groupe ; au-dessus, `other` quitte ses onglets pour venir sous `dock`.
        Retenu (`remember`) pour les lancements suivants. Rend vrai s'ils sont dans la même colonne, hors des onglets
        l'un de l'autre. Depuis le 19/11, sous un panneau en onglets aussi, `other` quitte ses onglets : les deux
        au-dessus du groupe d'onglets, qui reste en bas de la colonne."""
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
            shown = not other.isHidden()
            self.win.removeDockWidget(dock)              # hors de ses onglets
            dock.setFloating(False)
            # les deux remis à neuf : Qt garde sinon un groupe d'onglets d'un seul panneau, où le partage donnerait un
            # onglet (une colonne qui n'a que ce groupe, par exemple)
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
            before = self.split_names()
            name = dock.objectName()
            st.setValue(f'{KEY}/partage/{name}', f'{other.objectName()}|{"dessous" if below else "dessus"}')
            st.remove(f'{KEY}/onglet/{name}')
            st.remove(f'{KEY}/seul/{name}')
            st.remove(f'{KEY}/partage/{other.objectName()}')   # l'autre n'est plus rangé par rapport à un troisième
            self._unsplit_from(name)                     # ni un troisième par rapport à lui
            st.setValue(f'{KEY}/place/{name}', side)
            # son repère d'avant, celui de l'autre, ceux rangés par rapport à lui : plus partagés, leur onglet (27/11)
            self._release(before - self.split_names() - {name, other.objectName()})
        if show:
            self.settle(side)                            # le groupe d'onglets sous eux
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

    def _join_group(self, dock) -> bool:
        """Un panneau masqué vient d'être montré hors de nos fonctions (son bouton, sa commande, le menu de Qt) : son
        onglet dans le groupe d'onglets de sa colonne, comme par l'œil de la fenêtre de la colonne — jamais empilé avec
        un autre panneau (demande du 23/11). Laissé où il est : détaché, rangé à part par l'utilisateur
        (« Au-dessus de », « Au-dessous de », sorti des onglets : `chosen`), déjà en onglet, ou seul groupe de sa
        colonne ; déjà en onglet, il est mis devant. Depuis le 27/11, rangé au-dessus ou au-dessous d'un autre dont la
        place a changé pendant qu'il était masqué : il y revient (`_rejoin`). Rend vrai s'il a été mis en onglet."""
        try:
            if self._busy or self._settling or dock.isHidden() or dock.isFloating() or not self.win.isVisible():
                return False
        except RuntimeError:                             # panneau ou fenêtre détruits entre-temps
            return False
        side = self.side(dock)
        if side is None or dock is getattr(self.win, 'dock_program_text', None):
            return False
        if dock.objectName() in self.chosen():
            self._rejoin(dock)                           # rangé à part : de retour près de son repère (27/11)
            return False
        return self._take_tab(dock, side)

    def _take_tab(self, dock, side: str) -> bool:
        """`dock`, montré dans la colonne `side`, y prend son onglet dans le groupe d'onglets (demande du 25/11) : déjà
        dans des onglets (sans la colonne Datron), il est mis devant ; en onglet avec la colonne Datron, il en sort ;
        sans groupe d'onglets, il forme son propre bloc — à côté de la colonne Datron, sa propre colonne. La colonne
        Datron elle-même (la fenêtre Programme et ses parties de plugin) n'est jamais mise en onglet. Qt
        ne compte que les panneaux montrés dans `tabifiedDockWidgets` (vérifié au round 1162). Rend vrai s'il a été
        mis en onglet."""
        w = self.win
        if self._datron(dock):                           # la colonne Datron elle-même : jamais en onglet — en onglet
            if dock is getattr(w, 'dock_program', None):   # (rangée cachée dans un groupe), elle en sort
                self.free_program()
            return False
        mates = w.tabifiedDockWidgets(dock)
        if mates and self.host_ok(mates):                # déjà dans des onglets : mis devant, puisque montré
            self._quiet(dock.raise_)
            return False
        group = self.main_group(side, without=dock)
        if group:
            self._quiet(lambda: (w.tabifyDockWidget(group[0], dock), dock.setVisible(True), dock.raise_()))
            self._joined(dock, group)
            self.settle(side)                            # le groupe d'onglets toujours en bas
            return dock in w.tabifiedDockWidgets(group[0])
        beside = self._beside(side) and self._room_beside(dock)   # (le dessin garde sa place : sinon sous la colonne)
        if mates or (beside and self._in_program_column(dock)):
            dp = getattr(w, 'dock_program', None)
            under = not beside and self._beside(side)    # pas la place d'une colonne : sous la fenêtre Programme
            if under:
                self.free_program()                      # en groupe (voisins cachés), le partage en ferait un onglet

            def own():                                   # son propre bloc (sa colonne, à côté de la colonne Datron)
                w.removeDockWidget(dock)
                if under:
                    w.splitDockWidget(dp, dock, Qt.Orientation.Vertical)
                else:
                    w.addDockWidget(AREAS[side], dock,
                                    Qt.Orientation.Horizontal if beside else Qt.Orientation.Vertical)
                dock.setVisible(True)
                dock.raise_()
            self._quiet(own)
        return False

    def regroup(self, docks) -> int:
        """Les panneaux `docks`, remontrés ensemble par nos fonctions (la colonne rouverte, la FAO rouverte par son
        onglet ou refermée, la disposition d'un lancement) : chacun resté seul hors des onglets sans y avoir été rangé
        (« Au-dessus de », « Au-dessous de », sorti des onglets, Dimensions d'office au-dessus de Calques : `placed`)
        prend son onglet dans le groupe de sa colonne, comme un panneau remontré seul (demande du 25/11). Rangé
        au-dessus ou au-dessous d'un autre : de retour à sa place (`_rejoin`, 27/11). Rend le nombre de panneaux mis
        en onglet."""
        try:
            if not self.win.isVisible() or self.win.isMinimized():
                return 0
        except RuntimeError:
            return 0
        placed, n, shares = self.placed(), 0, self._shares()
        for d in docks:
            try:
                if d.objectName() in shares and not d.isHidden():
                    self._rejoin(d)                      # « Au-dessus de / Au-dessous de » : à sa place (27/11)
                    continue
                if d is getattr(self.win, 'dock_program', None) and self._datron(d):
                    self.free_program()                  # remontrée encore en onglet (rangée cachée) : elle en sort
                if d.isHidden() or d.isFloating() or d.objectName() in placed or self._datron(d):
                    continue
            except RuntimeError:                         # panneau détruit entre-temps
                continue
            side = self.side(d)
            mates = self.win.tabifiedDockWidgets(d)
            if side is None or (mates and self.host_ok(mates)):
                continue
            n += bool(self._take_tab(d, side))
        return n

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
            was_hidden = dock.isHidden()
            self._quiet(lambda: (dock.setVisible(True), dock.raise_()))
            if was_hidden and dock.objectName() not in self.chosen():
                self._take_tab(dock, side)               # revenu : son onglet dans le groupe (demande du 25/11)
            elif was_hidden:
                self._rejoin(dock)                       # rangé à part : de retour près de son repère (27/11)
            self.settle(side)

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
        return dock.objectName().startswith('plugin_') or dock is getattr(w, 'dock_program', None) or \
            dock is getattr(w, 'dock_program_text', None)

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
            text = getattr(self.win, 'dock_program_text', None)   # le texte du programme revient avec elle si
            prog = getattr(self.win, 'dock_program', None)       # la fenêtre Programme est restée montrée
            back = [d for d in col if d.objectName() in names and (not self._gated(d) or (
                d is text and prog is not None and not prog.isHidden()))] \
                or [d for d in col if not self._gated(d) and d.objectName() not in ON_DEMAND]

            def do():
                for d in back:
                    d.setVisible(True)
                for d in back:
                    if d.objectName() in front:
                        d.raise_()
            if back:
                self._quiet(do)
                self.regroup(back)                       # revenus seuls hors des onglets : leur onglet (25/11)
                self.settle(side)
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
        w = self.win
        if dock is getattr(w, 'dock_program', None) and callable(getattr(w, 'program_centered', None)) and \
                w.program_centered():
            w.program_center(False)                      # pas de plein écran par-dessus le programme au centre
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
            if dock is getattr(w, 'dock_program_text', None) and hasattr(w, 'program_panel'):
                want = w.program_panel.text_side()       # ancrée : à côté de la fenêtre Programme
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

    def fill_layout(self, m, dock) -> None:
        """Les entrées du modèle du 27/11 dans le menu `m` : « Seul à gauche », « Seul à droite », « Au-dessus de › »,
        « Au-dessous de › » (les panneaux montrés dans les colonnes, ceux de la sienne d'abord), « Masquer » ; l'état du
        panneau coché (`state`), son entrée grisée (il y est déjà)."""
        kind, other = self.state(dock)
        tips = (tr('Son onglet dans le groupe d’onglets de la colonne de gauche'),
                tr('Son onglet dans le groupe d’onglets de la colonne de droite'))
        for side, label, tip in zip(SIDES, (tr('Seul à gauche'), tr('Seul à droite')), tips):
            a = m.addAction(label)
            a.setObjectName(f'seul_{side}')
            a.setCheckable(True)
            a.setChecked(kind == side)
            a.setEnabled(kind != side)
            a.setToolTip(tip)
            a.triggered.connect(lambda _=False, s=side: self.set_alone(dock, s))
        here = self.side(dock)
        near = [d for d in self.docks() if d is not dock and self.side(d) is not None and not d.isHidden()
                and d.objectName() not in NOT_PARTNERS]  # (la fenêtre Programme, son texte : la colonne Datron)
        near.sort(key=lambda d: self.side(d) != here)    # ceux de sa colonne d'abord
        for title, name, below in ((tr('Au-dessus de'), 'au_dessus_de', False),
                                   (tr('Au-dessous de'), 'au_dessous_de', True)):
            sub = QMenu(title, m)                        # enfant du menu : vit autant que lui
            sub.setObjectName(name)
            m.addMenu(sub)
            sub.menuAction().setEnabled(bool(near))
            for d in near:
                a = sub.addAction(full_title(d))
                a.setCheckable(True)
                a.setChecked(d is other and kind == ('dessous' if below else 'dessus'))
                a.triggered.connect(lambda _=False, o=d, b=below: self.split_with(dock, o, b))
        fao = dock is getattr(self.win, 'dock_cam', None)   # la palette masquée ferme la FAO : dit
        a = m.addAction(tr('Masquer (ferme la FAO)') if fao else tr('Masquer'))
        a.setObjectName('masquer')
        a.setCheckable(True)
        a.setChecked(kind == 'masque')
        a.setEnabled(kind != 'masque')
        a.triggered.connect(lambda _=False: self.close(dock))
        m.setToolTipsVisible(True)

    def menu(self, dock, parent=None, table: bool = True) -> QMenu:
        """Le menu du clic droit d'un panneau (sa barre de titre, son onglet, le fond de son contenu ; sa ligne du
        tableau des panneaux, alors sans le tableau : `table` faux). Demande du 27/11 : court, le même partout — Seul à
        gauche, Seul à droite, Au-dessus de ›, Au-dessous de ›, Masquer (`fill_layout`), puis plein écran translucide,
        détacher seul, titres entiers ; le tableau de tous les panneaux (Gauche / Masqué / Droite, demande du 15/11)
        dans « Tous les panneaux › », au bas du menu (avant : en tête)."""
        m = QMenu(parent or self.win)
        self.fill_layout(m, dock)
        m.addSeparator()
        ov = self.overlay(dock, create=False)
        a = m.addAction(tr('Plein écran translucide'))
        a.setCheckable(True)
        a.setChecked(bool(ov is not None and ov.active))
        a.triggered.connect(lambda _=False: self.toggle_overlay(dock))
        a = m.addAction(tr('Ancrer') if dock.isFloating() else tr('Détacher seul'))   # lui seul quitte la colonne
        a.triggered.connect(lambda _=False: self.toggle_floating(dock))
        a = m.addAction(tr('Titres entiers dans les onglets'))    # sinon : une icône et un libellé court
        a.setCheckable(True)
        a.setChecked(self.tab_mode() == 'entier')
        a.triggered.connect(lambda on=False: self.set_tab_mode('entier' if on else 'court'))
        if table:
            from PySide6.QtWidgets import QWidgetAction
            sub = QMenu(tr('Tous les panneaux'), m)
            sub.setObjectName('tous_les_panneaux')
            m.addMenu(sub)
            table = QWidgetAction(sub)                   # Gauche / Masqué / Droite pour chacun (demande du 15/11)
            table.setObjectName('panneaux')
            box = QWidget()
            inner = QVBoxLayout(box)
            inner.setContentsMargins(8, 4, 8, 4)
            inner.addWidget(PanelRows(self, self.side(dock) or 'droite', done=lambda: (sub.close(), m.close()),
                                      parent=box))
            table.setDefaultWidget(box)
            sub.addAction(table)
        return m

    def show_menu(self, dock, at, table: bool = True, parent=None):
        """Le menu du panneau ouvert au point `at` de l'écran ; rend l'action choisie (None : aucune)."""
        m = self.menu(dock, parent, table)
        chosen = m.exec(at)
        m.deleteLater()
        return chosen

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
            if t in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease) \
                    and ev.button() == Qt.MouseButton.LeftButton:
                self._sep_down = t == QEvent.Type.MouseButtonPress   # (un séparateur tiré : `_hand_check`)
            if t == QEvent.Type.ChildAdded and not self._scan_due:
                self._scan_due = True
                QTimer.singleShot(0, self._scan)
            if t == QEvent.Type.Show and self._settle_due:
                self._settle_due = False                 # la première fois montrée : les onglets en bas
                QTimer.singleShot(0, self.settle_all)
            if t == QEvent.Type.WindowStateChange and getattr(self, '_fao_due', False) and not self.win.isMinimized():
                QTimer.singleShot(0, self, self.fao_opened)   # la fenêtre réduite rendue : le rangement qui attendait
            if t == QEvent.Type.WindowStateChange and getattr(self, '_model_due', False) and not self.win.isMinimized():
                QTimer.singleShot(0, self, self._model_layout_once)   # (le modèle du 27/11, s'il attendait)
            if t in (QEvent.Type.Show, QEvent.Type.Hide):
                self._win_shown = t == QEvent.Type.Show  # (fermée, réduite : `_lonely_targets` jamais programmé)
            return False
        if isinstance(obj, QDockWidget):
            if t == QEvent.Type.ContextMenu and self._background_menu(obj, ev):
                return True                              # le fond de son contenu (aucun menu propre) : son menu (27/11)
            if t in (QEvent.Type.Resize, QEvent.Type.Show):
                self._place_grip(obj)                    # la poignée reste dans le coin
            if t == QEvent.Type.Show and getattr(self, '_fao_due', False) and obj in self._fao_docks_main():
                QTimer.singleShot(0, self, self.fao_opened)   # le rangement d'une fois par poste qui attendait
            if obj is getattr(self.win, 'dock_program_text', None):
                if t == QEvent.Type.HideToParent and obj.isHidden() and not obj.isWindow():
                    self._text_closed(obj)               # sa colonne rétrécit d'autant (demande du 25/11)
                elif t == QEvent.Type.Show:
                    self._text_opened(obj)               # elle s'élargit d'autant
            elif t == QEvent.Type.Resize:
                self._hand_check(obj)                    # une voisine du texte fermé réglée à la souris ?
            if t == QEvent.Type.HideToParent and obj.isHidden() and not obj.isWindow():
                # fermé ancré, fenêtre montrée ou non (pas la fenêtre réduite ; pas détaché : Qt masque aussi un
                # panneau qu'on repose à la souris, ou qu'on ancre de nouveau, pendant qu'il est encore une fenêtre)
                obj._vd_was_hidden = True
                # rangé par rapport à un autre, masqué par l'utilisateur (pas par nos fonctions : l'onglet CAD, la
                # FAO) : son repère, resté seul, reprend son onglet (27/11)
                # Jamais la fenêtre fermée : à la fin de l'interpréteur, Python détruit les fenêtres fermées encore
                # vivantes, Qt masque leurs panneaux ; lire les réglages ou armer une minuterie sur `Columns` en
                # pleine destruction finissait en violation d'accès (round 1185). `_win_shown` : un simple drapeau.
                if getattr(self, '_win_shown', False) and not (self._busy or self._settling) \
                        and obj.objectName() in self._shares():
                    QTimer.singleShot(0, self, self._lonely_targets)
            elif t == QEvent.Type.Show and getattr(obj, '_vd_was_hidden', False):
                obj._vd_was_hidden = False
                if not (self._busy or self._settling):   # montré par nos fonctions : déjà à sa place
                    QTimer.singleShot(0, lambda d=obj: self._join_group(d))
            elif t == QEvent.Type.ShowToParent and not obj.isVisible():
                obj._vd_was_hidden = False               # montré fenêtre cachée (disposition du lancement) : laissé
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

    def _background_menu(self, dock, ev) -> bool:
        """Un clic droit sur le fond du contenu de `dock`, qu'aucun élément n'a pris (demande du 27/11) : son menu.
        Seulement un vrai `QContextMenuEvent`, et pas au-dessus d'une vue qui se glisse au bouton droit (une vue 2D ou
        3D) : rien n'y est ouvert à son relâchement. Rend vrai si le menu a été ouvert."""
        from PySide6.QtGui import QContextMenuEvent
        if not isinstance(ev, QContextMenuEvent):
            return False
        try:
            from PySide6.QtOpenGLWidgets import QOpenGLWidget
            views = (QGraphicsView, QOpenGLWidget)
        except ImportError:                              # (sans le module OpenGL de Qt)
            views = (QGraphicsView,)
        w = dock.childAt(dock.mapFromGlobal(ev.globalPos()))
        while w is not None and w is not dock:
            if isinstance(w, views):
                return False
            w = w.parentWidget()
        self.show_menu(dock, ev.globalPos())
        return True

    def settle_all(self) -> None:
        try:
            self._regroup_once()
            self._fao_layout_once()                      # (une fois par poste, 27/11)
            self._model_layout_once()                    # (le modèle du 27/11, une fois par poste)
            self._lonely_targets()                       # un repère resté seul, son partenaire masqué : son onglet
            for side in SIDES:
                self.settle(side)
        except RuntimeError:                             # fenêtre détruite entre-temps
            pass

    def _regroup_once(self) -> None:
        """Une fois par poste, à la première fenêtre montrée (round 1162) : les panneaux montrés restés seuls hors
        des onglets sans y avoir été rangés — une disposition d'avant, une session où ils s'empilaient — prennent leur
        onglet dans le groupe de leur colonne. Une colonne rangée côte à côte à la souris est laissée."""
        st = self._st()
        if str(st.value(REGROUPED_KEY, '')).lower() in ('1', 'true') or not self.win.isVisible() \
                or self.win.isMinimized():
            return
        self.free_program()                              # la colonne Datron encore en onglet : sortie d'abord
        for side in SIDES:
            blocks = self.blocks(side)
            if len(blocks) > 1 and not self._side_by_side([b for b in blocks if self.host_ok(b)]):
                self.regroup([b[0] for b in blocks if len(b) == 1])
        st.setValue(REGROUPED_KEY, True)

    # --- le texte du programme fermé : sa colonne rétrécit d'autant (demande du 25/11) -------------------------------
    def _widths(self, side: str, without=None) -> list:
        """[(panneau, largeur)] : un panneau montré devant par colonne de panneaux côte à côte, du côté `side`."""
        out, xs = [], []
        for d in self.column(side):
            if d is without or d.isHidden() or not self.in_front(d):
                continue
            x = d.mapTo(self.win, QPoint(0, 0)).x()
            if any(abs(x - o) <= 2 for o in xs):
                continue
            xs.append(x)
            out.append((d, d.width()))
        return out

    def _text_closed(self, dock) -> None:
        """Le texte du programme fermé dans sa colonne (sa croix, l'œil, la fenêtre Programme fermée, plus de
        parties de plugin…) : les colonnes voisines gardent leur largeur, le dessin gagne la sienne ; retenu pour la
        réouverture. Rien pendant une disposition refaite par nous (la colonne cachée, l'onglet CAD) ni pendant que le
        programme va au centre (▣ : il en revient à la même largeur) ; détaché, rien ne bouge."""
        w, self._sep_down = self.win, False              # (un appui resté sans relâchement : plus compté)
        try:
            if not w.isVisible() or w.isMinimized():
                return
        except RuntimeError:
            return
        side = self.side(dock)
        if side is None:
            return
        keep = self._widths(side, without=dock)          # (lues avant que Qt ne leur donne sa place)
        shrink = not (self._busy or self._settling or getattr(w, '_program_moving', False))
        span = (dock.mapTo(w, QPoint(0, 0)).x(), dock.width())
        central = w.centralWidget()
        floor = min(DRAWING_MIN, central.width()) if central is not None else 0   # le dessin, au moins, rouvert
        dock._vd_room = (dock.width(), keep, shrink, floor)
        # les largeurs laissées par `_shrink` ; sans rétrécir, celles d'à présent (un réglage à la souris d'ici la
        # réouverture n'est pas écrasé)
        dock._vd_after = None if shrink else {id(d): wd for d, wd in keep}
        if shrink:
            QTimer.singleShot(0, lambda: self._shrink(dock, span, keep))

    def _gap(self) -> int:
        """La largeur d'un séparateur entre deux colonnes de panneaux (px)."""
        from PySide6.QtWidgets import QStyle
        return self.win.style().pixelMetric(QStyle.PixelMetric.PM_DockWidgetSeparatorExtent, None, self.win)

    def _shrink(self, dock, span, keep) -> None:
        """Les colonnes du côté du texte fermé à leur largeur d'avant : celle lue à la fermeture, sinon (un onglet
        venu devant entre-temps) celle d'à présent moins la place du texte, pour la colonne qui l'a prise."""
        try:
            if not dock.isHidden():                      # rouvert entre-temps
                return
            w = self.win
            w.layout().activate()                        # les places d'après la fermeture
            known = {id(d): wd for d, wd in keep}
            x, width = span
            docks, widths = [], []
            for d, now in self._widths(self.side(dock) or '', without=dock):
                at = d.mapTo(w, QPoint(0, 0)).x()
                if id(d) in known:
                    want = known[id(d)]
                elif at <= x + width and at + now >= x:  # elle a pris la place du texte
                    want = now - width - self._gap()
                else:
                    want = now
                docks.append(d)
                widths.append(max(1, want))
            if docks:
                w.resizeDocks(docks, widths, Qt.Orientation.Horizontal)
                w.layout().activate()
                dock._vd_after = {id(d): d.width() for d in docks}
        except RuntimeError:                             # fenêtre détruite entre-temps
            pass

    def _hand_check(self, dock) -> None:
        """Le texte du programme fermé : une voisine qui change de largeur pendant qu'un séparateur de colonnes est
        tiré à la souris (bouton appuyé sur la fenêtre elle-même) — la largeur retenue est oubliée, sa réouverture
        laisse Qt faire sa place ; venu de Qt (autre panneau, fenêtre), sa nouvelle largeur est suivie. Lu à la
        volée : à la réouverture, Qt a déjà repris de la place aux voisines."""
        text = getattr(self.win, 'dock_program_text', None)
        after = getattr(text, '_vd_after', None) if text is not None else None
        if not after or id(dock) not in after or self._busy or self._settling \
                or getattr(self.win, '_program_moving', False):
            return
        try:
            if not text.isHidden() or dock.isHidden() or dock.isFloating():
                return
            if not getattr(self, '_sep_down', False):
                after[id(dock)] = dock.width()           # venu de Qt : suivi
            elif abs(dock.width() - after[id(dock)]) > 4:
                text._vd_room = text._vd_after = None    # à la souris : oubliée
        except RuntimeError:                             # fenêtre détruite entre-temps
            pass

    def _text_opened(self, dock) -> None:
        """Le texte du programme rouvert dans sa colonne : la largeur qu'il avait, les voisines la leur — la colonne
        s'élargit d'autant, le dessin gardant au moins `DRAWING_MIN` (ou la largeur qu'il avait, moindre) ; revenu
        sans avoir rétréci la colonne (▣, la colonne cachée), les largeurs d'avant sa fermeture. Une largeur réglée à
        la souris entre-temps : rien de retenu, Qt fait sa place."""
        self._sep_down = False                           # (un appui resté sans relâchement : plus compté)
        room, dock._vd_room = getattr(dock, '_vd_room', None), None
        after, dock._vd_after = getattr(dock, '_vd_after', None), None
        if room is None or dock.isFloating():
            return
        width, keep, shrunk, floor = room
        side = self.side(dock)
        if shrunk and side is not None:                  # les voisines à leur largeur d'avant la réouverture (suivie
            keep = [(d, (after or {}).get(id(d), wd))    # par `_hand_check` : Qt leur reprend déjà de la place)
                    for d, wd in self._widths(side, without=dock)]
        QTimer.singleShot(0, lambda: self._widen(dock, width, keep, floor))

    def _widen(self, dock, width, keep, floor) -> None:
        w = self.win
        try:
            if dock.isHidden() or dock.isFloating() or not w.isVisible():
                return
            side = self.side(dock)
            live = [(d, wd) for d, wd in keep if not d.isHidden() and not d.isFloating() and self.side(d) == side]
            w.layout().activate()                        # les largeurs données par Qt à la réouverture
            grow = width + sum(wd for _d, wd in live) - dock.width() - sum(d.width() for d, _w in live)
            central = w.centralWidget()
            free = (central.width() if central is not None else 0) - floor
            if grow > free:                              # le dessin garde son minimum
                width = max(dock.minimumSizeHint().width(), width - (grow - free))
            w.resizeDocks([dock] + [d for d, _w in live], [width] + [wd for _d, wd in live], Qt.Orientation.Horizontal)
        except RuntimeError:                             # fenêtre détruite entre-temps
            pass

    # --- l'onglet CAD range la FAO -----------------------------------------------------------------------------------
    def fao_docks(self) -> list:
        """Les panneaux de la FAO : la palette des parcours, les opérations, le programme machine, ceux des plugins."""
        w = self.win
        out = [d for d in (getattr(w, 'dock_cam', None), getattr(w, 'dock_paths', None),
                           getattr(w, 'dock_program', None), getattr(w, 'dock_program_text', None))
               if d is not None]
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
        if self.regroup(back):                           # revenus seuls hors des onglets : leur onglet (25/11)
            self._quiet(lambda: [d.raise_() for d in back if not d.isFloating() and d.objectName() in front])
        self.fao_opened()                                # (le rangement d'une fois par poste qui attendait, 27/11)


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
            name = QLabel(full_title(d))
            # clic droit sur la ligne : le menu du panneau (Au-dessus de, Au-dessous de, Détacher seul…)
            name.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            name.customContextMenuRequested.connect(
                lambda pos, dk=d, lab=name: self.row_menu(dk, lab.mapToGlobal(pos)))
            name.setToolTip(tr('Clic droit : seul à gauche ou à droite, au-dessus ou au-dessous d’un autre panneau…'))
            grid.addWidget(name, i, 0)
            row = {}
            for col, (key, text, tip) in enumerate(PLACES, 1):
                b = QToolButton()
                b.setText(tr(text))
                b.setCheckable(True)
                b.setChecked(state == key)
                b.setAutoRaise(True)
                b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                b.setToolTip(tr(tip))
                if key == state and key in SIDES and columns.state(d)[0] != key:   # rangé autrement (27/11)
                    b.setToolTip(tr('Hors de son groupe d’onglets : un clic lui y donne son onglet'))
                if barred and key != 'masque':
                    b.setEnabled(False)                  # réservé à une autre machine
                    b.setToolTip(tr('Panneau réservé à une autre machine que celle du dessin'))
                b.clicked.connect(lambda _=False, dk=d, place=key: self.choose(dk, place))
                row[key] = b
                grid.addWidget(b, i, col)
            text = self.where(d, central)                # sa disposition, dans les mots du menu (27/11)
            if text:
                note = QLabel(text)
                note.setObjectName('disposition')
                note.setEnabled(False)
                grid.addWidget(note, i, len(PLACES) + 1)
            self.choices[d.objectName()] = row
            self.eyes[d.objectName()] = row[self.side]

    def row_menu(self, dock, at) -> None:
        """Le menu du panneau de la ligne, sans le tableau."""
        chosen = self.columns.show_menu(dock, at, table=False, parent=self)
        if chosen is not None and self.done is not None:   # Échap : rien de fait, le menu d'autour reste ouvert
            self.done()

    def where(self, dock, central: bool = False) -> str:
        """Ce que la ligne dit de la disposition du panneau, dans les mots de son menu (demande du 27/11) : « seul »
        (seul à gauche ou à droite), « au-dessus de X », « au-dessous de X », « hors des onglets » (rangé autrement, à
        la souris) ; « détaché », « au centre » ; rien s'il est masqué."""
        if central:
            return tr('au centre')
        kind, other = self.columns.state(dock)
        if kind == 'detache':
            return tr('détaché')
        if kind in SIDES:
            return tr('seul')
        if kind == 'dessus' and other is not None:
            return tr('au-dessus de {0}').format(full_title(other))
        if kind == 'dessous' and other is not None:
            return tr('au-dessous de {0}').format(full_title(other))
        return tr('hors des onglets') if kind == 'hors' else ''

    def _central(self, dock) -> bool:
        w = self.columns.win
        centered = getattr(w, 'program_centered', None)
        whole = getattr(w, '_program_part', None) is getattr(w, 'program_panel', None)   # texte seul : rangé
        return dock is getattr(w, 'dock_program', None) and callable(centered) and bool(centered()) and whole

    def rows(self) -> list:
        """Les panneaux listés : ceux de la colonne d'où le tableau est ouvert d'abord, puis les autres, par nom."""
        c = self.columns
        return sorted(c.docks(), key=lambda d: (c.side(d) != self.side, full_title(d).lower()))

    def choose(self, dock, place: str) -> None:
        """Le panneau `dock` mis à sa place : une colonne (la FAO ouverte pour ses panneaux), ou masqué — aussi par
        un second clic sur la colonne où il est déjà (15/11). Sauf, depuis le 27/11, un panneau montré dans la colonne
        mais pas « seul » dans cette colonne (au-dessus ou au-dessous d'un autre, hors des onglets : `Columns.state`,
        le modèle du menu, 27/11) : le clic lui y donne son onglet (`Columns.set_alone`) ; la palette FAO ainsi cliquée
        ne ferme plus la FAO."""
        c = self.columns
        central = self._central(dock)
        if central:                                      # le programme rentre d'abord dans son panneau
            c.win.program_center(False)
        if place not in SIDES and dock.isHidden() and not central:
            pass                                         # déjà masqué : rien (fermer un panneau FAO caché fermerait la FAO)
        else:
            c.win._docks_before_cam = None               # la disposition retenue avant la FAO ne vaut plus
            if place in SIDES and not central and c.side(dock) == place and not dock.isHidden() \
                    and c.state(dock)[0] != place:
                c.set_alone(dock, place)                 # rangé autrement : son onglet, pas masqué (27/11)
            elif place not in SIDES or (c.side(dock) == place and not dock.isHidden() and not dock.isFloating()
                                        and not central):
                c.close(dock)
            else:
                c.show_in(dock, place, True)
        if self.done is not None:
            self.done()


def _dock_of(widget) -> tuple:
    """(panneau de colonne, `Columns`) qui montre `widget` ; (None, None) : hors d'un panneau de colonne."""
    dock = widget
    while dock is not None and not isinstance(dock, QDockWidget):
        dock = dock.parentWidget()
    cols = getattr(dock.parentWidget(), 'columns', None) if dock is not None else None
    if cols is None or not any(d is dock for d in cols.docks()):
        return None, None
    return dock, cols


def panel_menu(widget) -> QMenu | None:
    """Le menu du panneau de colonne qui montre `widget` (le même que sa barre de titre), pour un clic droit là où
    sa liste n'a pas de menu propre — une zone vide (demande du 27/11). None : hors d'un panneau de colonne."""
    dock, cols = _dock_of(widget)
    return cols.menu(dock) if dock is not None else None


def add_layout_menu(menu, widget) -> QMenu | None:
    """« Disposition › » au bas du menu contextuel propre d'un élément montré dans une colonne (`widget` : sa liste,
    son arbre…), sans remplacer ce menu : les mêmes entrées que le clic droit du panneau — Seul à gauche, Seul à
    droite, Au-dessus de ›, Au-dessous de ›, Masquer (demande du 27/11). Rien hors d'un panneau de colonne (une fenêtre
    de dialogue, par exemple). Rend le sous-menu, ou None."""
    dock, cols = _dock_of(widget)
    if dock is None:
        return None
    menu.addSeparator()
    sub = QMenu(tr('Disposition'), menu)
    sub.setObjectName('disposition')
    cols.fill_layout(sub, dock)
    menu.addMenu(sub)
    return sub


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
            if not self.frameGeometry().contains(at) and QApplication.activePopupWidget() is None:
                # ailleurs : dans VectorDrive, hors de la fenêtre (pas dans le menu d'une de ses lignes)
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
