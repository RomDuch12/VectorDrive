"""Le programme machine dans sa fenêtre (demande du 14/11 : « Le bouton posttraiter devient "icone programme" machine
coloré et bien visible qui ouvre une nouvelle fenetre avec coloration syntaxique, maj temps réel ou manuelle,
transparence réglable, sélecteur postpro/machine, directement relié aux différents panneaux fao, peut se placer à la
place du canva »).

`ProgramPanel` est le contenu d'un panneau ancrable comme les autres (`ui.columns`) : détaché dans sa fenêtre, dans
une colonne, ou en plein écran translucide par-dessus le dessin — à sa place quand l'opacité est au plus haut. Il
montre le programme que le post-processeur du dessin écrirait pour les parcours montrés (les mêmes fichiers, le même
encodage que l'écriture), coloré ; il suit le panneau FAO et le dessin en direct, ou à la demande ; l'opération
choisie dans le panneau FAO y est retrouvée ; il dit quand des opérations actives sont cachées, donc hors du
programme ; « Enregistrer… » écrit le programme (le post-traitement de toujours).
"""
from __future__ import annotations

import re

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (QColor, QFont, QIcon, QPainter, QPen, QPixmap, QSyntaxHighlighter, QTextCharFormat,
                           QTextCursor, QTextFormat)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
                               QTextEdit, QVBoxLayout, QWidget)

from ..i18n import tr
from .code_view import CodeView, fold_regions

LIVE_KEY = 'fao/programme_direct'
#: le plan du programme (la liste des séquences et des parcours, à gauche du texte) montré (retenu)
OUTLINE_KEY = 'fao/programme_plan'
#: la vue du programme (menu « Vue ») : taille du texte (0 : d'origine), numéros de ligne, retour à la ligne, couleurs
VIEW_KEY = 'fao/programme_vue'
#: les parties apportées par les plugins (`host_panel`) : dépliées ou repliées, retenu par clé
SECTION_KEY = 'fao/programme_parties'
#: le texte du programme dans une colonne à part quand des parties de plugin sont montrées (option F10)
TEXT_COLUMN_KEY = 'fao/programme_texte_colonne'
#: tailles du texte permises (points)
TEXT_SIZES = (6, 32)


def _flag(v, default: bool) -> bool:
    if v is None or v == '':
        return default
    return v in (True, 'true', '1', 1)
#: au-delà de tant de comparaisons (lignes × parcours), les plages des parcours ne sont pas cherchées (un très long
#: programme reste vif : numéros de ligne et blocs du langage seulement)
MAX_SECTION_WORK = 4_000_000
#: attente après le dernier changement du panneau FAO avant de réécrire le programme (ms)
LIVE_MS = 400
#: en direct, un programme de plus de mouvements que cela n'est pas réécrit à chaque changement (« Mettre à jour »)
LIVE_MAX_MOVES = 200_000
#: au-delà (texte entier, ou une seule ligne), la coloration est coupée : le texte reste lisible et la fenêtre vive
MAX_COLORED = 400_000
MAX_LINE = 20_000
#: extensions des programmes HPGL : le point-virgule y termine chaque ordre, ce n'est pas un commentaire
HPGL_EXT = ('.plt', '.hpgl', '.hpg', '.hgl')

_VALUE = r'[-+]?(?:\d+\.?\d*|\.\d+)'
#: (rôle, expression) — l'ordre compte : les derniers l'emportent (commentaires et chaînes en dernier)
RULES = (
    ('number', r'(?<![\d.])' + _VALUE),                  # la valeur, même collée à sa lettre : X12.5, F1200, Y-3, PD10
    ('axis', r'(?<![A-Za-z])[XYZABCUVWIJKR](?=[-+.\d])'),
    ('feed', r'(?<![A-Za-z])[FS](?=[-+.\d])'),
    ('tool', r'(?<![A-Za-z])[TDH]\d+'),
    ('g', r'(?<![A-Za-z])G\d+(?:\.\d+)?'),
    ('m', r'(?<![A-Za-z])M\d+'),
    ('line', r'^\s*N\d+'),
    ('keyword', r'\b(?:module|endmodule|program|endprogram|export|import|using|end|if|else|endif|for|endfor|while|'
                r'endwhile|return|Tool|Spindle|Rpm|SpraySystem|Absolute|Relative)\b'),
    ('string', r'"[^"\n]*"'),
    ('comment', r'\([^)\n]*\)|(?:^|(?<=\s))#(?!\d).*$|//.*$|^%.*$|@[^@\n]*@'),
    ('semicolon', r';.*$'),                              # commentaire après « ; » — sauf en HPGL
)
#: couleurs par rôle : (thème clair, thème sombre)
COLORS = {
    'number': ('#0b7285', '#66d9e8'), 'axis': ('#1864ab', '#74c0fc'), 'feed': ('#a61e4d', '#faa2c1'),
    'tool': ('#d9480f', '#ffa94d'), 'g': ('#5f3dc4', '#b197fc'), 'm': ('#c2255c', '#f783ac'),
    'line': ('#868e96', '#868e96'), 'keyword': ('#5f3dc4', '#b197fc'), 'string': ('#862e9c', '#e599f7'),
    'comment': ('#2b8a3e', '#8ce99a'), 'semicolon': ('#2b8a3e', '#8ce99a'),
}
BOLD = ('g', 'm', 'tool', 'keyword')
ITALIC = ('comment', 'semicolon')


def machine_icon(size: int = 40) -> QIcon:
    """L'icône « programme machine » : une fraiseuse à portique, colorée (bâti bleu, broche orange, table grise) et
    des lignes de programme — dessinée ici, sans fichier."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    u = size / 40.0
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor('#868e96'))                      # la table
    p.drawRoundedRect(QRectF(3 * u, 30 * u, 34 * u, 6 * u), 2 * u, 2 * u)
    p.setBrush(QColor('#1c7ed6'))                      # le portique : deux montants, une traverse
    p.drawRoundedRect(QRectF(5 * u, 8 * u, 5 * u, 23 * u), 1.5 * u, 1.5 * u)
    p.drawRoundedRect(QRectF(30 * u, 8 * u, 5 * u, 23 * u), 1.5 * u, 1.5 * u)
    p.drawRoundedRect(QRectF(5 * u, 5 * u, 30 * u, 7 * u), 2 * u, 2 * u)
    p.setBrush(QColor('#f76707'))                      # la broche et sa fraise
    p.drawRoundedRect(QRectF(16 * u, 9 * u, 8 * u, 12 * u), 1.5 * u, 1.5 * u)
    p.drawRect(QRectF(19 * u, 21 * u, 2 * u, 7 * u))
    p.setPen(QPen(QColor('#ffffff'), max(1.0, 1.2 * u)))   # trois lignes de programme sur la traverse
    for k, w in enumerate((10, 16, 7)):
        p.drawLine(int(8 * u), int((6.5 + 1.8 * k) * u), int((8 + w) * u), int((6.5 + 1.8 * k) * u))
    p.end()
    return QIcon(pm)


class Highlighter(QSyntaxHighlighter):
    """Coloration d'un programme machine quel qu'il soit (ISO, HPGL, SimPL…) : commentaires, mots G et M, outils,
    axes, avances, nombres, chaînes, quelques mots de langage. `hpgl` : le point-virgule n'y ouvre pas un commentaire."""

    def __init__(self, document, dark: bool = False):
        super().__init__(document)
        self.dark, self.hpgl = bool(dark), False
        self.rules = []
        self._build()

    def _build(self) -> None:
        self.rules = []
        for role, pattern in RULES:
            if role == 'semicolon' and self.hpgl:
                continue
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(COLORS[role][1 if self.dark else 0]))
            if role in BOLD:
                fmt.setFontWeight(QFont.Weight.Bold)
            if role in ITALIC:
                fmt.setFontItalic(True)
            self.rules.append((role, re.compile(pattern), fmt))

    def set_dark(self, dark: bool) -> None:
        self.dark = bool(dark)
        self._build()
        self.rehighlight()

    def set_kind(self, extension: str) -> None:
        """Le genre du programme, d'après l'extension de son fichier."""
        hpgl = str(extension or '').lower() in HPGL_EXT
        if hpgl != self.hpgl:
            self.hpgl = hpgl
            self._build()

    def roles(self, text: str) -> list:
        """[(début, longueur, rôle)] de la ligne `text`, dans l'ordre d'application (les derniers l'emportent)."""
        return [(m.start(), m.end() - m.start(), 'comment' if role == 'semicolon' else role)
                for role, rx, _f in self.rules for m in rx.finditer(text)]

    def role_at(self, text: str, i: int) -> str:
        """Le rôle du caractère de rang `i` de la ligne `text` ('' : aucun)."""
        got = ''
        for a, n, role in self.roles(text):
            if a <= i < a + n:
                got = role
        return got

    def highlightBlock(self, text: str) -> None:        # noqa: N802 (API Qt)
        for _role, rx, fmt in self.rules:
            for m in rx.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)


def _fold(s: str) -> str:
    """Sans casse ni accents : un nom d'opération retrouvé dans un programme écrit en ASCII."""
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFKD', s or '') if not unicodedata.combining(c)).lower()


class ProgramPanel(QWidget):
    """Le programme machine des parcours montrés : coloré, en direct ou à la demande."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.files: list = []                           # [(nom de fichier, texte)]
        self.warnings: list = []
        self.note = ''
        self._loading = False
        self._folded: dict = {}                         # fichier → ses lignes sans casse ni accents (`follow_op`)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        row = QHBoxLayout()
        self.machine = QComboBox()
        self.machine.setToolTip(tr('Machine (post-processeur) du dessin : le programme est réécrit pour elle'))
        self.machine.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.machine.setMinimumContentsLength(10)
        self.machine.currentIndexChanged.connect(self._machine_chosen)
        row.addWidget(self.machine, 1)
        self.live = QCheckBox(tr('En direct'))
        self.live.setToolTip(tr('Coché : le programme suit le panneau FAO et le dessin (opérations, parcours montrés, '
                                'machine). Décoché : il attend « Mettre à jour »'))
        self.live.setChecked(win.settings.value(LIVE_KEY, 'true') in (True, 'true'))
        self.live.toggled.connect(self._live_toggled)
        row.addWidget(self.live)
        self.buttons = {}
        for key, text, tip, slot in (
                ('update', tr('Mettre à jour'), tr('Refaire les parcours si le dessin a changé, et réécrire le programme'),
                 lambda: self.refresh(recompute=True)),
                ('all', tr('Tout montrer'), tr('Des opérations actives sont cachées, donc hors du programme : les '
                                               'montrer toutes'), self.show_all),
                ('copy', tr('Copier'), tr('Copier le programme montré'), self.copy),
                ('save', tr('Enregistrer…'), tr('Écrire le programme machine dans un fichier'), self.save)):
            b = self.buttons[key] = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, s=slot: s())
            row.addWidget(b)
        self.buttons['all'].hide()
        lay.addLayout(row)
        from PySide6.QtWidgets import QSplitter as _Split
        #: les parties des plugins (`host_panel`) : clé → (cadre, en-tête, contenu, titre) — NeoDrive, opérations…
        self.hosted: dict = {}
        self.sections_box = QWidget()
        self._sections_lay = QVBoxLayout(self.sections_box)
        self._sections_lay.setContentsMargins(0, 0, 0, 0)
        self._sections_lay.setSpacing(2)
        # les parties l'une sous l'autre, leur hauteur réglée à la souris (demande du 20/11) ; dépliée, chacune a
        # toute sa hauteur : c'est la colonne qui défile si elles n'y tiennent pas, pas une partie
        self.sections_split = _Split(Qt.Orientation.Vertical)
        self.sections_split.setChildrenCollapsible(False)
        self._sections_lay.addWidget(self.sections_split, 1)
        from .fit import VScroll
        self.sections_scroll = VScroll(self.sections_box, min_height=48)
        self.sections_box.hide()
        self.sections_scroll.hide()
        self.viewer = QWidget()                          # le texte du programme : ce qui va au centre (▣) quand des
        vlay = QVBoxLayout(self.viewer)                  # parties de plugin restent dans la colonne
        vlay.setContentsMargins(0, 0, 0, 0)
        self.vsplit = _Split(Qt.Orientation.Vertical)
        self.vsplit.setChildrenCollapsible(False)
        self.vsplit.addWidget(self.sections_scroll)
        self.vsplit.addWidget(self.viewer)
        self.vsplit.setStretchFactor(0, 0)
        self.vsplit.setStretchFactor(1, 1)
        lay.addWidget(self.vsplit, 1)
        self.viewer.installEventFilter(self)             # le texte seul montré au centre : à jour comme le panneau
        self.file = QComboBox()
        self.file.setToolTip(tr('Le programme tient en plusieurs fichiers : celui qui est montré'))
        self.file.currentIndexChanged.connect(self._show_file)
        self.file.hide()
        vlay.addWidget(self.file)
        self.text = CodeView()                           # numéros de ligne, blocs repliables, plages surlignées
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        f = QFont('Consolas')
        f.setStyleHint(QFont.StyleHint.Monospace)
        self.text.setFont(f)
        self._base_size = 9.0                            # la taille « d'origine » (menu Vue), lue dans `apply_view`
        self.colored = True                              # les couleurs du langage (menu Vue)
        self._plain = False                              # programme trop long : sans couleurs de toute façon
        self.highlighter = Highlighter(self.text.document(), self._dark())
        from PySide6.QtWidgets import QHeaderView, QSplitter, QTreeWidget
        self.given: list = []                           # les plages données par le post (`program_preview`)
        self.outline = QTreeWidget()                     # le plan : séquences et parcours du programme montré
        self.outline.setHeaderLabels([tr('Plan du programme'), tr('N° de lignes')])
        self.outline.setRootIsDecorated(True)
        self.outline.setIndentation(12)
        self.outline.header().setStretchLastSection(False)
        self.outline.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.outline.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.outline.itemClicked.connect(lambda it, _c=0: self.goto_section(it))
        self.split = QSplitter(Qt.Orientation.Horizontal)
        self.split.addWidget(self.outline)
        self.split.addWidget(self.text)
        self.split.setStretchFactor(0, 0)
        self.split.setStretchFactor(1, 1)
        self.split.setSizes([190, 600])
        self.outline.setVisible(win.settings.value(OUTLINE_KEY, 'true') in (True, 'true'))
        vlay.addWidget(self.split, 1)
        self.status = QLabel('')
        self.status.setWordWrap(True)
        from PySide6.QtWidgets import QToolButton
        foot = QHBoxLayout()                             # la ligne d'état, puis replier / déplier (petits : la
        foot.addWidget(self.status, 1)                   # fenêtre n'en est pas élargie)
        fold_tip = tr('Replier chaque parcours sous sa première ligne (▸ dans la marge le déplie)')
        unfold_tip = tr('Déplier tous les blocs du programme')
        center_tip = tr('Le programme au centre, à la place du dessin, entre les colonnes — ou de retour dans sa fenêtre')
        outline_tip = tr('Le plan du programme : la liste de ses séquences et de ses parcours, à gauche du texte')
        from PySide6.QtWidgets import QMenu
        b = self.buttons['view'] = QToolButton()         # Vue : taille, numéros, retour à la ligne, couleurs (retenu)
        b.setText(tr('Vue'))
        b.setAutoRaise(True)
        b.setToolTip(tr('Régler la vue du programme : taille du texte, numéros de ligne, retour à la ligne, couleurs, '
                        'plan, blocs repliés'))
        b.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.view_menu = QMenu(b)
        self.view_menu.aboutToShow.connect(self._fill_view_menu)
        b.setMenu(self.view_menu)
        foot.addWidget(b)
        b = self.buttons['update_here'] = QToolButton()  # ⟳ : le texte seul au centre se met à jour lui aussi
        b.setText('⟳')
        b.setAutoRaise(True)
        b.setToolTip(tr('Refaire les parcours si le dessin a changé, et réécrire le programme'))
        b.clicked.connect(lambda _=False: self.refresh(recompute=True))
        b.hide()
        foot.addWidget(b)
        b = self.buttons['outline'] = QToolButton()      # ☰ : le plan montré ou caché (retenu)
        b.setText('☰')
        b.setCheckable(True)
        b.setChecked(not self.outline.isHidden())
        b.setAutoRaise(True)
        b.setToolTip(outline_tip)
        b.clicked.connect(lambda on=False: self.set_outline_shown(on))
        foot.addWidget(b)
        b = self.buttons['center'] = QToolButton()       # ▣ : au centre, à la place du dessin (demande du 15/11)
        b.setText('▣')
        b.setCheckable(True)
        b.setAutoRaise(True)
        b.setToolTip(center_tip)
        b.clicked.connect(lambda _=False: self.win.program_center())
        foot.addWidget(b)
        for key, sign, tip, on in (('fold', '⊟', fold_tip, True), ('unfold', '⊞', unfold_tip, False)):
            b = self.buttons[key] = QToolButton()
            b.setText(sign)
            b.setAutoRaise(True)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, v=on: self.fold_paths(v))
            foot.addWidget(b)
        vlay.addLayout(foot)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(LIVE_MS)
        self.timer.timeout.connect(self._live_refresh)
        self.apply_view()

    def set_centered(self, on: bool) -> None:
        """Le bouton ▣ dit si le programme est au centre, à la place du dessin ; le texte seul au centre montre son
        propre « Mettre à jour » (la rangée du haut est restée dans la colonne)."""
        self.buttons['center'].setChecked(bool(on))
        self.buttons['update_here'].setVisible(self.viewer.parentWidget() is not self.vsplit)
        if on:
            self._sections_changed()
        else:
            self.place_viewer()                          # de retour : sa colonne à part, si des parties

    def dock_viewer(self) -> None:
        """Le texte du programme rendu à sa place (il était au centre) : sa colonne à part, ou son panneau sous les
        parties des plugins."""
        self.place_viewer()

    # --- le texte dans une colonne à part (demande du 20/11 : la colonne Datron, le SimPL à côté) -----------------
    def text_dock(self):
        """Le panneau « Programme : texte » de la fenêtre (None : pas de fenêtre principale)."""
        return getattr(self.win, 'dock_program_text', None)

    def split_wanted(self) -> bool:
        """Le texte dans sa colonne à part : des parties de plugin sont montrées et l'option F10 le veut (d'office)."""
        if self.text_dock() is None or not self.sections_shown():
            return False
        try:
            from .options import value
            return bool(value(self.win.settings, TEXT_COLUMN_KEY))
        except Exception:                                # noqa: BLE001 — réglages illisibles : d'office
            return True

    def place_viewer(self) -> str:
        """Le texte du programme à sa place : 'colonne' (sa colonne à part, à côté de celle des parties), 'panneau'
        (sous les parties, comme avant) ou 'centre' (à la place du dessin : rien ne change). Rend la place."""
        w, d = self.win, self.text_dock()
        centered = getattr(w, 'program_centered', None)
        if callable(centered) and centered():
            self._sections_changed()
            return 'centre'
        if d is not None and self.split_wanted():
            if d.widget() is not self.viewer:
                hold = d.widget()
                d.setWidget(self.viewer)
                if hold is not None and hold is not self.viewer:
                    hold.deleteLater()
                self.viewer.show()
                self.put_text_dock()
                self.text_follow()
            where = 'colonne'
        else:
            if self.viewer.parentWidget() is not self.vsplit:
                if d is not None and d.widget() is self.viewer:
                    d.setWidget(QWidget())
                self.vsplit.addWidget(self.viewer)
                self.vsplit.setStretchFactor(1, 1)
                self.viewer.show()
            if d is not None and not d.isHidden():
                d.hide()
            where = 'panneau'
        self.buttons['update_here'].setVisible(self.viewer.parentWidget() is not self.vsplit)
        self._sections_changed()
        return where

    def text_side(self) -> str:
        """La colonne de la fenêtre Programme, où va le texte ('droite' si elle est détachée)."""
        cols, dp = getattr(self.win, 'columns', None), getattr(self.win, 'dock_program', None)
        side = cols.side(dp) if cols is not None and dp is not None else None
        return side or 'droite'

    def follow_program_side(self) -> None:
        """La fenêtre Programme a changé de colonne (ou s'est détachée) : la colonne du texte la suit."""
        if self.text_side() != getattr(self, '_text_side', None):
            self.put_text_dock()

    def put_text_dock(self, side: str | None = None) -> None:
        """La colonne du texte collée à celle de la fenêtre Programme, du côté du dessin : à droite de la colonne de
        gauche, à gauche de celle de droite (demande du 20/11). Détachée, elle le reste."""
        w, d = self.win, self.text_dock()
        cols = getattr(w, 'columns', None)
        if d is None or cols is None or d.isFloating() or d.widget() is not self.viewer:
            return
        side = side if side in ('gauche', 'droite') else self.text_side()
        self._text_side = self.text_side()
        if getattr(self, '_laid', None) == side and cols.side(d) == side and not w.tabifiedDockWidgets(d):
            return                                       # déjà à sa place (pas refait à chaque machine choisie)
        from .columns import AREAS
        w._docks_before_cam = None                       # la disposition d'avant la FAO n'est plus à rendre
        if side == 'gauche' or not w.isVisible() or w.isMinimized():
            # à gauche, Qt ajoute la colonne à droite : du côté du dessin (fenêtre pas montrée : les places ne se
            # lisent pas, la colonne est seulement ajoutée ; remise à côté la prochaine fois)
            cols._quiet(lambda: w.addDockWidget(AREAS[side], d, Qt.Orientation.Horizontal))
            self._laid = side if side == 'gauche' else None
            return
        # à droite, Qt l'ajouterait au bord de la fenêtre : la colonne remise après elle, ses onglets et ses hauteurs
        blocks = [[m for m in b if m is not d] for b in cols.blocks('droite')]
        blocks = [b for b in blocks if b]
        placed = cols.placed()
        asleep = [x for x in cols.column('droite') if x is not d and x.isHidden()]
        heights = [max(1, b[0].height()) for b in blocks]

        def do():
            for b in blocks:
                for m in b:
                    w.removeDockWidget(m)
            for x in asleep:
                w.removeDockWidget(x)
            w.addDockWidget(AREAS['droite'], d)
            prev = None
            for b in blocks:
                if prev is None:
                    w.addDockWidget(AREAS['droite'], b[0], Qt.Orientation.Horizontal)
                else:
                    w.splitDockWidget(prev, b[0], Qt.Orientation.Vertical)
                for m in b[1:]:
                    w.tabifyDockWidget(b[0], m)
                for m in b:
                    m.setVisible(True)
                prev = b[0]
            main = max(blocks, key=len)[0] if blocks else None
            for x in asleep:                             # les cachés : leur onglet dans le groupe, ou sous la colonne
                if main is None:                         # aucun montré : une seule colonne, en onglets
                    w.addDockWidget(AREAS['droite'], x, Qt.Orientation.Horizontal)
                    main = prev = x
                elif x.objectName() in placed:
                    w.splitDockWidget(prev, x, Qt.Orientation.Vertical)
                else:
                    w.tabifyDockWidget(main, x)
                x.setVisible(False)
            for b in blocks:
                b[0].raise_()
            if blocks:
                w.resizeDocks([b[0] for b in blocks], heights, Qt.Orientation.Vertical)
        cols._quiet(do)
        self._laid = side

    def text_follow(self) -> None:
        """La colonne du texte montrée ou cachée avec la fenêtre Programme (fermée, elle se ferme aussi)."""
        d, dp = self.text_dock(), getattr(self.win, 'dock_program', None)
        if d is None or dp is None or d.widget() is not self.viewer:
            return
        if dp.isHidden() != d.isHidden():
            d.setVisible(not dp.isHidden())
            if not d.isHidden():
                d.raise_()

    # --- les parties apportées par les plugins (atelier SimPL, 17/11) -------------------------------------------
    def host_panel(self, key: str, title: str, widget, shown: bool = True) -> None:
        """`widget` devient une partie repliable de l'onglet Programme, au-dessus du texte : un en-tête (son titre,
        ▾ / ▸) qui la replie ou la déplie (retenu) ; `shown` faux : cachée tant que sa machine n'est pas choisie."""
        from PySide6.QtWidgets import QSizePolicy, QToolButton
        frame = QWidget()
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(0)
        head = QToolButton()
        head.setCheckable(True)
        head.setAutoRaise(True)
        head.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        head.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        head.setStyleSheet('QToolButton { text-align: left; font-weight: bold; }')
        head.setToolTip(tr('Replier ou déplier cette partie (retenu)'))
        fl.addWidget(head)
        fl.addWidget(widget, 1)
        self.hosted[key] = (frame, head, widget, str(title))
        self.sections_split.addWidget(frame)
        self.sections_split.setStretchFactor(self.sections_split.indexOf(frame), 1)
        head.setChecked(_flag(self.win.settings.value(f'{SECTION_KEY}/{key}', 'true'), True))
        head.toggled.connect(lambda on, k=key: self.fold_section(k, not on))
        frame.setVisible(bool(shown))
        self.fold_section(key, not head.isChecked(), remember=False)

    def fold_section(self, key: str, folded: bool, remember: bool = True) -> None:
        """La partie `key` repliée sous son en-tête, ou dépliée ; retenu."""
        if key not in self.hosted:
            return
        frame, head, widget, title = self.hosted[key]
        widget.setVisible(not folded)
        if head.isChecked() == bool(folded):
            blocked = head.blockSignals(True)
            head.setChecked(not folded)
            head.blockSignals(blocked)
        head.setText(('▸ ' if folded else '▾ ') + title)
        i = self.sections_split.indexOf(frame)
        if i >= 0:
            self.sections_split.setStretchFactor(i, 0 if folded else 1)
        frame.setMaximumHeight(head.sizeHint().height() if folded else 16777215)   # repliée : son en-tête
        self.share_sections()
        if remember:
            self.win.settings.setValue(f'{SECTION_KEY}/{key}', not folded)
        self._sections_changed()

    def show_section(self, key: str, on: bool) -> bool:
        """La partie `key` montrée (sa machine choisie) ou cachée. Rend vrai si elle a changé."""
        if key not in self.hosted:
            return False
        frame = self.hosted[key][0]
        if frame.isHidden() != bool(on):
            return False
        frame.setVisible(bool(on))
        self.place_viewer()                              # des parties : le texte dans sa colonne à part
        return True

    def sections_shown(self) -> list:
        """Les clés des parties de plugin montrées (pour la machine du dessin)."""
        return [k for k, e in self.hosted.items() if not e[0].isHidden()]

    def share_sections(self) -> None:
        """Les parties montrées se partagent la hauteur : repliées, leur en-tête ; dépliées, le reste à parts
        égales (le séparateur la règle ensuite à la souris)."""
        sp = self.sections_split
        sizes, free, opened = [], max(0, sp.height()), []
        for i in range(sp.count()):
            f = sp.widget(i)
            if f.isHidden():
                sizes.append(0)
            elif f.maximumHeight() < 16777215:
                sizes.append(f.maximumHeight())
                free -= f.maximumHeight()
            else:
                sizes.append(None)
                opened.append(i)
        each = max(1, free // max(1, len(opened)))
        sp.setSizes([each if h is None else h for h in sizes])

    def _sections_changed(self) -> None:
        shown = self.sections_shown()
        self.sections_box.setVisible(bool(shown))
        self.sections_scroll.setVisible(bool(shown))
        opened = any(not self.hosted[k][2].isHidden() for k in shown)
        if opened or self.viewer.parentWidget() is not self.vsplit:
            self.sections_scroll.setMaximumHeight(16777215)  # (le texte ailleurs : les parties ont toute la place)
            return
        self._sections_lay.activate()
        self.sections_scroll.setMaximumHeight(max(24, self.sections_box.sizeHint().height()))

    # --- la vue (menu « Vue ») -----------------------------------------------------------------------------------
    def view(self) -> dict:
        """La vue retenue : {'taille' (points, 0 : d'origine), 'numeros', 'retour', 'couleurs'}."""
        st = self.win.settings
        try:
            size = int(float(st.value(f'{VIEW_KEY}/taille', 0) or 0))
        except (TypeError, ValueError):
            size = 0
        return {'taille': size if size == 0 else max(TEXT_SIZES[0], min(TEXT_SIZES[1], size)),
                'numeros': _flag(st.value(f'{VIEW_KEY}/numeros', 'true'), True),
                'retour': _flag(st.value(f'{VIEW_KEY}/retour', 'false'), False),
                'couleurs': _flag(st.value(f'{VIEW_KEY}/couleurs', 'true'), True)}

    def set_view(self, key: str, value) -> None:
        """Un réglage de la vue changé, retenu et appliqué."""
        self.win.settings.setValue(f'{VIEW_KEY}/{key}', value)
        self.apply_view()

    def apply_view(self) -> None:
        v = self.view()
        f = QFont('Consolas')                            # sans taille : celle de l'application (réglage des polices)
        f.setStyleHint(QFont.StyleHint.Monospace)
        if v['taille']:
            f.setPointSizeF(float(v['taille']))
        else:
            self.text.setFont(f)
            got = self.text.font().pointSizeF()
            self._base_size = got if got > 0 else 9.0
        self.text.setFont(f)
        self.text.set_numbers(v['numeros'])
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth if v['retour']
                                  else QPlainTextEdit.LineWrapMode.NoWrap)
        self.colored = v['couleurs']
        want = self.text.document() if self.colored and not self._plain else None
        if self.highlighter.document() is not want:
            self.highlighter.setDocument(want)

    def zoom(self, step: int) -> int:
        """Le texte un point plus grand (`step` 1), plus petit (-1), ou à sa taille d'origine (0). Rend la taille."""
        size = self.view()['taille'] or int(round(self._base_size))
        size = 0 if step == 0 else max(TEXT_SIZES[0], min(TEXT_SIZES[1], size + int(step)))
        self.set_view('taille', size)
        return size or int(round(self._base_size))

    def _fill_view_menu(self) -> None:
        m = self.view_menu
        m.clear()
        v = self.view()
        for text, step in ((tr('Agrandir le texte'), 1), (tr('Réduire le texte'), -1), (tr('Taille d’origine'), 0)):
            a = m.addAction(text)
            a.triggered.connect(lambda _=False, s=step: self.zoom(s))
        m.addSeparator()
        for key, text in (('numeros', tr('Numéros de ligne')), ('retour', tr('Retour à la ligne')),
                          ('couleurs', tr('Couleurs du langage'))):
            a = m.addAction(text)
            a.setCheckable(True)
            a.setChecked(v[key])
            a.toggled.connect(lambda on, k=key: self.set_view(k, bool(on)))
        a = m.addAction(tr('Plan du programme'))
        a.setCheckable(True)
        a.setChecked(not self.outline.isHidden())
        a.toggled.connect(lambda on: self.set_outline_shown(bool(on)))
        m.addSeparator()
        m.addAction(tr('Replier chaque parcours')).triggered.connect(lambda _=False: self.fold_paths(True))
        m.addAction(tr('Tout déplier')).triggered.connect(lambda _=False: self.fold_paths(False))

    def _dark(self) -> bool:
        return self.palette().base().color().lightness() < 128

    # --- la machine ----------------------------------------------------------------------------------------------
    def sync_machines(self, key: str | None = None) -> None:
        """La liste des machines : celle du panneau FAO (post-processeurs des plugins, fiches machine) ; `key` : le
        post-processeur dont le programme est montré."""
        src = self.win.cam_panel.post
        self._loading = True
        self.machine.clear()
        for i in range(src.count()):
            self.machine.addItem(src.itemText(i), src.itemData(i))
        at = self.machine.findData(key) if key else -1
        self.machine.setCurrentIndex(at if at >= 0 else src.currentIndex())
        self._loading = False

    def _machine_chosen(self, i: int) -> None:
        if self._loading or i < 0:
            return
        src = self.win.cam_panel.post
        j = src.findData(self.machine.itemData(i))       # par sa clé : les deux listes peuvent différer
        if j >= 0 and src.currentIndex() != j:
            src.setCurrentIndex(j)                       # le panneau FAO l'enregistre dans le dessin et prévient
        self.refresh()

    # --- en direct, à la demande -----------------------------------------------------------------------------------
    def _live_toggled(self, on: bool) -> None:
        self.win.settings.setValue(LIVE_KEY, bool(on))
        if on:
            self.refresh()

    def notify(self) -> None:
        """Le panneau FAO ou le dessin a changé : en direct, le programme est réécrit sous peu (les changements à la
        suite n'en font qu'un) ; caché, il attend d'être montré."""
        if self.live.isChecked() and self._seen():
            self.timer.start()

    def _seen(self) -> bool:
        """Le programme est-il à l'écran : le panneau, ou son texte seul au centre (la fenêtre fermée) ?"""
        return self.isVisible() or self.viewer.isVisible()

    def eventFilter(self, obj, ev):                      # noqa: N802 (API Qt)
        from PySide6.QtCore import QEvent
        if obj is getattr(self, 'viewer', None) and ev.type() == QEvent.Type.Show:
            QTimer.singleShot(0, self._shown)            # le texte seul montré (au centre) : mis à jour
        return super().eventFilter(obj, ev)

    def showEvent(self, ev):                             # noqa: N802 (API Qt)
        super().showEvent(ev)
        QTimer.singleShot(0, self._shown)

    def _shown(self) -> None:
        if self._seen() and (self.live.isChecked() or not self.files):
            self._live_refresh()

    def _live_refresh(self) -> None:
        """La mise à jour en direct : pas pendant un calcul, pas pour un très long programme (« Mettre à jour »)."""
        cp = self.win.cam_panel
        if getattr(cp, '_computing', False):
            self.timer.start()                           # après le calcul
            return
        moves = sum(len(tp.moves) for tp in cp.toolpaths if getattr(tp, 'shown', True))
        if moves > LIVE_MAX_MOVES:
            self.timer.stop()
            self.status.setText(tr('Long programme ({0} mouvements) : « Mettre à jour » le réécrit').format(moves))
            return
        self.refresh()

    def refresh(self, recompute: bool = False) -> str:
        """Le programme réécrit d'après les parcours montrés (`recompute` : refaits d'abord si le dessin a changé) ;
        rend le texte montré."""
        dark = self._dark()
        if dark != self.highlighter.dark:
            self.highlighter.set_dark(dark)
        cp = self.win.cam_panel
        data = cp.program_preview(recompute=recompute)
        self.sync_machines(data.get('key') or None)
        self.files, self.warnings, self.note = list(data['files']), list(data['warnings']), data.get('note', '')
        self.given = [d for d in data.get('sections') or () if isinstance(d, dict)]
        self.hidden = len(cp.hidden_active_ops())
        self.highlighter.set_kind(data.get('extension', ''))
        self._folded = {}
        self._sections_of = {}                           # les plages des parcours : à rechercher
        keep = self.file.currentIndex()
        self._loading = True
        self.file.clear()
        for name, _text in self.files:
            self.file.addItem(name)
        self.file.setVisible(len(self.files) > 1)
        self.file.setCurrentIndex(keep if 0 <= keep < len(self.files) else (0 if self.files else -1))
        self._loading = False
        self._show_file(self.file.currentIndex())
        self.follow_op(scroll=False)
        self.timer.stop()                                # ce qu'il a lui-même déclenché ne le relance pas
        return self.text.toPlainText()

    def _show_file(self, i: int) -> None:
        if self._loading:
            return
        text = self.files[i][1] if 0 <= i < len(self.files) else ''
        self.text.setExtraSelections([])
        if text != self.text.toPlainText():
            bar = self.text.verticalScrollBar()
            at = bar.value()
            plain = len(text) > MAX_COLORED or any(len(line) > MAX_LINE for line in text.split('\n'))
            self._plain = plain
            want = None if plain or not getattr(self, 'colored', True) else self.text.document()
            if self.highlighter.document() is not want:
                self.highlighter.setDocument(want)
            self.text.set_program(text, self.fold_ranges(i))
            bar.setValue(min(at, bar.maximum()))
        self._fill_outline(i)
        parts = []
        if 0 <= i < len(self.files):
            parts.append(tr('{0} — {1} ligne(s)').format(self.files[i][0], len(text.splitlines())))
        hidden = getattr(self, 'hidden', 0)
        if hidden:
            parts.append('⚠ ' + tr('{0} opération(s) active(s) cachée(s) : hors du programme').format(hidden))
        if self.warnings:
            parts.append(tr('{0} avertissement(s)').format(len(self.warnings)))
        if self.note:
            parts.append(self.note)
        self.status.setText(' ; '.join(parts))
        self.status.setToolTip('\n'.join('• ' + str(w) for w in self.warnings[:30]))
        self.buttons['all'].setVisible(bool(hidden))
        self.buttons['copy'].setEnabled(bool(text))
        for key in ('fold', 'unfold'):
            self.buttons[key].setEnabled(bool(self.text.regions))

    def show_all(self) -> None:
        """Les opérations actives cachées de nouveau montrées : le programme est entier."""
        self.win.cam_panel.show_all_paths()
        self.refresh()

    # --- le lien avec le panneau FAO ---------------------------------------------------------------------------------
    def _lines(self, i: int) -> list:
        """Les lignes du fichier `i`, sans casse ni accents (gardées tant que le programme ne change pas)."""
        if i not in self._folded:
            self._folded[i] = _fold(self.files[i][1]).split('\n') if 0 <= i < len(self.files) else []
        return self._folded[i]

    def find_lines(self, name: str) -> list:
        """[(fichier, ligne)] des lignes du programme qui nomment `name` (sans casse ni accents), dans l'ordre."""
        want = _fold(name).strip()
        if not want:
            return []
        return [(i, k) for i in range(len(self.files)) for k, line in enumerate(self._lines(i)) if want in line]

    # --- le plan du programme (demande du 15/11, 20 h 55) ---------------------------------------------------------------
    def given_of(self, i: int) -> list:
        """Les plages données par le post pour le fichier `i`, valides, de haut en bas (les plus larges d'abord)."""
        if not self.given or not 0 <= i < len(self.files):
            return []
        text = self.files[i][1]
        cache = self.__dict__.setdefault('_given_of', {})        # par fichier : (son texte, ses plages)
        kept = cache.get(i)
        if kept is None or kept[0] is not text or kept[1] is not self.given:
            n = text.count('\n') + 1
            out = [d for d in self.given if d.get('file') == i and 0 <= d['first'] <= d['last'] < n]
            kept = cache[i] = (text, self.given, sorted(out, key=lambda d: (d['first'], -d['last'])))
        return kept[2]

    def fold_ranges(self, i: int) -> list:
        """Les plages repliables du fichier `i`, en plus des blocs du langage : celles du post, sinon celles des
        parcours retrouvés par leur nom."""
        given = self.given_of(i)
        if given:
            return [(d['first'], d['last']) for d in given]
        return [(a, b) for a, b, _tp in self.sections(i)]

    def outline_rows(self, i: int | None = None) -> list:
        """[(première ligne, dernière ligne, libellé, genre, opération)] du plan du fichier `i` (celui qui est
        montré) : les plages du post ; sans elles, les parcours retrouvés par leur nom."""
        i = self.file.currentIndex() if i is None else i
        given = self.given_of(i)
        if given:
            return [(d['first'], d['last'], d['label'] or d['name'] or d['kind'], d['kind'], d['op_id'])
                    for d in given]
        return [(a, b, tp.name, 'parcours', tp.op_id) for a, b, tp in self.sections(i)]

    def _fill_outline(self, i: int) -> None:
        from PySide6.QtWidgets import QTreeWidgetItem
        tree = self.outline
        rows = self.outline_rows(i)
        if rows == getattr(self, '_outline_shown', None) and tree.topLevelItemCount():
            return                                       # le même plan : sa ligne choisie, ses branches gardées
        self._outline_shown = rows
        tree.clear()
        stack = []                                       # [(dernière ligne, ligne du plan)] : les plages ouvertes
        for first, last, label, kind, op_id in rows:
            while stack and first > stack[-1][0]:
                stack.pop()
            it = QTreeWidgetItem([label, f'{first + 1}–{last + 1}'])
            it.setData(0, Qt.ItemDataRole.UserRole, (first, last, op_id))
            it.setToolTip(0, f'{label} — {kind}')
            (stack[-1][1].addChild if stack else tree.addTopLevelItem)(it)
            stack.append((last, it))
        tree.expandAll()

    def set_outline_shown(self, on: bool) -> None:
        """Le plan du programme montré ou caché, à gauche du texte ; retenu."""
        self.outline.setVisible(bool(on))
        self.buttons['outline'].setChecked(bool(on))
        self.win.settings.setValue(OUTLINE_KEY, bool(on))

    def goto_section(self, item) -> None:
        """Un clic dans le plan : la plage montrée (dépliée, surlignée, amenée à l'écran) ; son opération, s'il y en
        a une, choisie dans le panneau FAO."""
        data = item.data(0, Qt.ItemDataRole.UserRole) if item is not None else None
        if not data:
            return
        first, last, op_id = data
        cp = self.win.cam_panel
        ops = cp.setup().operations
        row = next((r for r, o in enumerate(ops) if op_id and o.id == op_id), -1)
        fi = self.file.currentIndex()
        if row >= 0 and row not in {x.row() for x in cp.ops.selectedIndexes()}:
            cp.ops.selectRow(row)                        # (le panneau FAO prévient : `follow_op` surligne l'opération)
        if self.file.currentIndex() != fi:               # … et a pu montrer un autre fichier, où elle commence :
            self.file.setCurrentIndex(fi)                # on reste dans celui dont on a cliqué le plan
        view = self.text
        view.reveal(first)
        if view.is_folded(first):
            view.toggle_fold(first)
        view.set_bands([(first, last)])
        block = view.document().findBlockByNumber(first)
        view.setTextCursor(QTextCursor(block))
        view.centerCursor()

    def sections(self, i: int | None = None) -> list:
        """[(première ligne, dernière ligne, parcours)] des parcours montrés dans le fichier `i` (celui qui est
        montré), lignes numérotées de 0. Le post les a données (`PostResult.sections`) : les siennes, exactes.
        Sinon : chacun de la ligne qui le nomme (la n-ième de ce nom, comme `locate`) à celle
        d'avant le parcours suivant ; le dernier jusqu'à la fin du bloc du langage qui le contient, sinon du fichier
        (sans les lignes vides de la fin)."""
        i = self.file.currentIndex() if i is None else i
        if not 0 <= i < len(self.files):
            return []
        given = self.given_of(i)
        if given:
            from types import SimpleNamespace
            return [(d['first'], d['last'], SimpleNamespace(op_id=d['op_id'], name=d['name'] or d['label']))
                    for d in given if d['op_id']]
        cache = self.__dict__.setdefault('_sections_of', {})     # par fichier : (son texte, ses plages) — refaites
        kept = cache.get(i)                                      # quand le texte change (`refresh` les oublie)
        if kept is not None and kept[0] is self.files[i][1]:
            return kept[1]
        out = self._find_sections(i)
        cache[i] = (self.files[i][1], out)
        return out

    def _find_sections(self, i: int) -> list:
        """Les plages des parcours du fichier `i`, cherchées par leur nom (voir `sections`, qui les garde)."""
        cp = self.win.cam_panel
        written = getattr(cp, '_writable', None)         # ceux que le programme écrit : pas une opération désactivée
        paths = [tp for tp in cp.toolpaths if getattr(tp, 'shown', True)]
        shown = [tp for tp in (written(paths) if written is not None else paths) if tp.name]
        raw = self.files[i][1].split('\n')
        if not shown or len(raw) * len(shown) > MAX_SECTION_WORK:
            return []
        if len(self._lines(i)) != len(raw):              # le texte du fichier a changé sans `refresh` : relu
            self._folded.pop(i, None)
        rank, starts, found = {}, [], {}
        for tp in shown:
            key = _fold(tp.name).strip()
            k = rank.get(key, 0)
            rank[key] = k + 1
            if key not in found:
                found[key] = self.find_lines(tp.name)
            if k < len(found[key]) and found[key][k][0] == i and found[key][k][1] < len(raw):
                starts.append((found[key][k][1], tp))
        starts.sort(key=lambda st: st[0])
        blocks = fold_regions(self.files[i][1])
        out = []
        for j, (line, tp) in enumerate(starts):
            if j + 1 < len(starts):
                last = starts[j + 1][0] - 1
            else:
                inside = [b for a, b in blocks if a < line <= b]
                last = min(inside) if inside else len(raw) - 1
            while last > line and not raw[last].strip():
                last -= 1
            if last >= line and not (out and out[-1][0] == line):
                out.append((line, last, tp))
        return out

    def fold_paths(self, on: bool = True) -> None:
        """« Replier » : chaque parcours sous sa première ligne (sans parcours reconnu : les blocs les plus
        profonds du langage) ; « Déplier » : tout le programme montré."""
        view = self.text
        if not on:
            view.fold_all(False)
            return
        heads = {a for a, b, _tp in self.sections() if b > a}
        if heads:
            view.folded = {a for a in heads if view.end_of(a) >= 0}
            view._apply_folds()
        elif view.regions:
            view.fold_all(True, depth=max(view.depth_of(a) for a, _b in view.regions))

    def locate(self, op):
        """(fichier, ligne) où commence l'opération `op` dans le programme : la ligne qui porte le nom de son premier
        parcours montré — la n-ième de ce nom si d'autres parcours montrés avant lui le portent aussi ; None si elle
        est cachée ou introuvable."""
        for fi in range(len(self.files)):               # le post a donné ses plages : la première de l'opération
            for d in self.given_of(fi):
                if d['op_id'] and d['op_id'] == op.id:
                    return fi, d['first']
        cp = self.win.cam_panel
        shown = [tp for tp in cp.toolpaths if getattr(tp, 'shown', True) and tp.name]
        mine = next((tp for tp in shown if tp.op_id == op.id), None)
        if mine is None:
            return None
        rank = sum(1 for tp in shown[:shown.index(mine)] if _fold(tp.name) == _fold(mine.name))
        found = self.find_lines(mine.name)
        if not found:
            return None
        return found[rank] if rank < len(found) else found[0]

    def follow_op(self, scroll: bool = True) -> int:
        """L'opération choisie dans le panneau FAO retrouvée dans le programme : sa première ligne surlignée et,
        quand c'est le choix qui change (`scroll`), amenée à l'écran (dans son fichier). Rend cette ligne ; -1 sans
        elle. Fenêtre cachée : rien."""
        if not self._seen() and scroll:
            return -1
        cp = self.win.cam_panel
        self.text.setExtraSelections([])
        self.text.set_bands([])
        rows = sorted({i.row() for i in cp.ops.selectedIndexes()})
        ops = cp.setup().operations
        chosen = [ops[r] for r in rows if r < len(ops)]
        if not chosen or not self.files:
            return -1
        ids = {o.id for o in chosen}

        def bands() -> None:                             # toute la plage des opérations choisies, dans le fichier
            self.text.set_bands([(a, b) for a, b, tp in self.sections() if tp.op_id in ids])   # montré : discrète
        at = next((found for found in (self.locate(o) for o in chosen) if found is not None), None)
        if at is None:                                   # (la première choisie est cachée : la suivante)
            bands()
            return -1
        fi, line = at
        if fi != self.file.currentIndex():
            if not scroll:
                bands()                                  # dans un autre fichier : montré quand on choisit l'opération
                return -1
            self.file.setCurrentIndex(fi)
        bands()
        if scroll:                                       # choisie à l'instant : son bloc déplié ; un rafraîchissement
            self.text.reveal(line)                       # laisse les replis comme ils sont
            if self.text.is_folded(line):
                self.text.toggle_fold(line)
        block = self.text.document().findBlockByNumber(line)
        sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(QColor(255, 212, 59, 90))
        sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        sel.cursor = QTextCursor(block)
        self.text.setExtraSelections([sel])
        if scroll:
            self.text.setTextCursor(QTextCursor(block))
            self.text.centerCursor()
        return line

    # --- copier, enregistrer ---------------------------------------------------------------------------------------------
    def copy(self) -> None:
        QApplication.clipboard().setText(self.text.toPlainText())
        self.status.setText(tr('Programme copié'))

    def save(self) -> None:
        """Le programme écrit dans un fichier : le post-traitement du panneau FAO (contrôles, journal, dossier)."""
        self.win.cam_panel.post_process()
        self.refresh()

    def sizeHint(self) -> QSize:                         # noqa: N802 (API Qt)
        return QSize(620, 720)
