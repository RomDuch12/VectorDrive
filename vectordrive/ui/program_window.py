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
        self.file = QComboBox()
        self.file.setToolTip(tr('Le programme tient en plusieurs fichiers : celui qui est montré'))
        self.file.currentIndexChanged.connect(self._show_file)
        self.file.hide()
        lay.addWidget(self.file)
        self.text = CodeView()                           # numéros de ligne, blocs repliables, plages surlignées
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        f = QFont('Consolas')
        f.setStyleHint(QFont.StyleHint.Monospace)
        self.text.setFont(f)
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
        lay.addWidget(self.split, 1)
        self.status = QLabel('')
        self.status.setWordWrap(True)
        from PySide6.QtWidgets import QToolButton
        foot = QHBoxLayout()                             # la ligne d'état, puis replier / déplier (petits : la
        foot.addWidget(self.status, 1)                   # fenêtre n'en est pas élargie)
        fold_tip = tr('Replier chaque parcours sous sa première ligne (▸ dans la marge le déplie)')
        unfold_tip = tr('Déplier tous les blocs du programme')
        center_tip = tr('Le programme au centre, à la place du dessin, entre les colonnes — ou de retour dans sa fenêtre')
        outline_tip = tr('Le plan du programme : la liste de ses séquences et de ses parcours, à gauche du texte')
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
        lay.addLayout(foot)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(LIVE_MS)
        self.timer.timeout.connect(self._live_refresh)

    def set_centered(self, on: bool) -> None:
        """Le bouton ▣ dit si le programme est au centre, à la place du dessin."""
        self.buttons['center'].setChecked(bool(on))

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
        if self.live.isChecked() and self.isVisible():
            self.timer.start()

    def showEvent(self, ev):                             # noqa: N802 (API Qt)
        super().showEvent(ev)
        QTimer.singleShot(0, self._shown)

    def _shown(self) -> None:
        if self.isVisible() and (self.live.isChecked() or not self.files):
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
            want = None if plain else self.text.document()
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
        if not self.isVisible() and scroll:
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
