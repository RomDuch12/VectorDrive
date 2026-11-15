"""Les modèles d'un parcours en liste à colonnes (demande du 14/11 : « Modèles parcours : liste déroulante colonnes
filtres arrangements possibles »).

La liste déroulante « Modèle » du formulaire d'un parcours (`TemplateCombo`) se déroule en tableau (`TemplatePopup`) :
une ligne par modèle, avec son dossier, son outil, son diamètre, sa profondeur, sa passe, son avance, la puissance du
laser, son origine et sa description. Un champ filtre la liste à la frappe : tous les mots, sans casse ni accents, le
point valant la virgule, dans toutes les colonnes — ou dans une seule, « colonne:valeur » (« outil:cyl »). Un clic sur
un en-tête trie ; les colonnes se déplacent à la souris, se montrent ou se cachent par le clic droit sur l'en-tête
(« Colonnes par défaut » les remet). Tri, ordre, largeurs, colonnes montrées et taille donnée à la liste sont retenus.
"""
from __future__ import annotations

import unicodedata

from PySide6.QtCore import QByteArray, QElapsedTimer, QEvent, QObject, QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QGuiApplication, QMouseEvent
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QFrame, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QMenu, QPushButton, QSizeGrip, QTreeWidget, QTreeWidgetItem, QVBoxLayout)

from ..i18n import tr

#: colonnes : clé, titre, nombre (aligné à droite, trié comme un nombre)
COLUMNS = (('name', 'Modèle', False), ('folder', 'Dossier', False), ('tool', 'Outil', False),
           ('diameter', 'Ø (mm)', True), ('depth', 'Prof. (mm)', True), ('step_down', 'Passe Z (mm)', True),
           ('feed', 'Avance (mm/min)', True), ('power', 'Puissance (%)', True), ('origin', 'Origine', False),
           ('description', 'Description', False))
KEYS = [k for k, _t, _n in COLUMNS]
#: colonnes cachées d'office (« Colonnes par défaut »)
HIDDEN = ('power',)
#: largeurs d'office (px) ; la dernière colonne prend le reste
WIDTHS = {'name': 200, 'folder': 110, 'tool': 140, 'diameter': 60, 'depth': 75, 'step_down': 85, 'feed': 100,
          'power': 85, 'origin': 70}
#: taille d'office de la liste déroulée
SIZE = (900, 380)
ORIGINS = {'plugin': 'Fourni', 'utilisateur': 'À moi'}
STATE_KEY = 'fao/modeles_liste'
#: nombre de colonnes de l'état d'en-tête retenu : un état d'une autre version n'est pas repris
STATE_COLUMNS_KEY = 'fao/modeles_liste_colonnes'
SIZE_KEY = 'fao/modeles_liste_taille'
ROLE = Qt.ItemDataRole.UserRole


def fold(s) -> str:
    """Pour la recherche et le tri : sans casse ni accents."""
    return ''.join(c for c in unicodedata.normalize('NFKD', str(s).casefold()) if not unicodedata.combining(c))


def search_fold(s) -> str:
    """Pour le filtre : `fold`, et le point vaut la virgule (« 0.5 » trouve « 0,5 »)."""
    return fold(s).replace('.', ',')


def _number(v) -> float | None:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def row_of(name: str, origin: str, tpl: dict) -> dict:
    """Ce que la liste montre du modèle `name` : son premier parcours et l'outil que le formulaire chargera (le premier
    du modèle, comme `FieldsDialog.load_template`)."""
    from ..cam import templates as TPL
    ops = [o for o in tpl.get('operations') or [] if isinstance(o, dict)]
    op = ops[0] if ops else {}
    tools = [t for t in tpl.get('tools') or [] if isinstance(t, dict)]
    tool = tools[0] if tools else {}
    return {'name': TPL.label_of(tpl) or name, 'folder': str(tpl.get('dossier') or ''),
            'tool': str(tool.get('name') or ''), 'diameter': _number(tool.get('diameter')),
            'depth': _number(op.get('depth')),
            'step_down': _number(op.get('step_down')) or _number(tool.get('step_down')),
            'feed': _number(op.get('feed')) or _number(tool.get('feed')),
            'power': _number(op.get('power')) or None,
            'origin': ORIGINS.get(origin, origin), 'description': str(tpl.get('description') or ''),
            'operations': len(ops)}


def _text(v) -> str:
    if v is None:
        return ''
    if isinstance(v, float):
        return f'{v:g}'.replace('.', ',')
    return str(v)


class _Row(QTreeWidgetItem):
    """Une ligne triée par la valeur de sa colonne : les nombres comme des nombres, les textes sans casse ni accents ;
    les cases vides à la fin, dans un sens comme dans l'autre."""

    def __lt__(self, other) -> bool:
        tree = self.treeWidget()
        c = tree.sortColumn() if tree is not None else 0
        if not 0 <= c < len(COLUMNS):
            return False
        a, b = self.data(c, ROLE), other.data(c, ROLE)
        empty_a, empty_b = a in (None, ''), b in (None, '')
        if empty_a or empty_b:
            if empty_a == empty_b:
                return False
            down = tree is not None and tree.header().sortIndicatorOrder() == Qt.SortOrder.DescendingOrder
            return empty_a if down else empty_b      # Qt retourne l'ordre en décroissant : le vide reste en bas
        return a < b


class _SwallowClicks(QObject):
    """Le temps d'un double clic après un choix à la souris : le second clic, là où était la liste, ne tombe pas sur le
    formulaire dessous."""

    def __init__(self, area: QRect):
        app = QApplication.instance()
        super().__init__(app)
        self.area = QRect(area)
        self.clock = QElapsedTimer()
        self.clock.start()
        self.limit = max(150, QApplication.doubleClickInterval())
        app.installEventFilter(self)

    def stop(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self.deleteLater()

    def eventFilter(self, obj, ev) -> bool:              # noqa: N802 (API Qt)
        if self.clock.elapsed() > self.limit:
            self.stop()
            return False
        if ev.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick,
                         QEvent.Type.MouseButtonRelease) and isinstance(ev, QMouseEvent):
            if self.area.contains(ev.globalPosition().toPoint()):
                if ev.type() == QEvent.Type.MouseButtonRelease:
                    self.stop()                            # le double clic est fini
                return True
        return False


class TemplatePopup(QFrame):
    """La liste à colonnes, déroulée sous la liste déroulante. `chosen(nom)` : un modèle a été choisi ; `none_chosen` :
    « réglages ci-dessous », sans modèle."""
    chosen = Signal(str)
    none_chosen = Signal()

    def __init__(self, parent=None, settings=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.settings = settings
        self.current = ''                                # le modèle choisi à l'ouverture
        self._placed = None                              # taille donnée à l'ouverture (QSize)
        self._user_size = None                           # taille donnée par l'utilisateur, à retenir
        self.setAttribute(Qt.WidgetAttribute.WA_NoMouseReplay)      # un clic sur la liste déroulante : fermée, pas rouverte
        self.setFrameShape(QFrame.Shape.StyledPanel)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText(tr('Filtrer : nom, outil, 0.5… plusieurs mots ; une colonne : outil:cyl'))
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(lambda _t: self.apply_filter())
        self.filter.returnPressed.connect(self._enter)
        self.filter.installEventFilter(self)
        lay.addWidget(self.filter)
        self.tree = QTreeWidget()
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setHeaderLabels([tr(t) for _k, t, _n in COLUMNS])
        h = self.tree.header()
        h.setSectionsMovable(True)
        h.setFirstSectionMovable(False)                    # le nom reste en tête
        h.setStretchLastSection(True)
        h.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        h.customContextMenuRequested.connect(self.show_columns_menu)
        self.tree.setSortingEnabled(True)
        self.tree.itemClicked.connect(lambda it, _c: self._clicked(it))
        self.tree.itemActivated.connect(lambda it, _c: self.choose(it.data(0, ROLE + 1)))
        self.tree.installEventFilter(self)
        lay.addWidget(self.tree, 1)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 16, 0)                # la poignée de taille, en bas à droite
        self.none_button = QPushButton(tr('(réglages ci-dessous)'))
        self.none_button.setFlat(True)
        self.none_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.none_button.setToolTip(tr('Aucun modèle : les réglages du formulaire'))
        self.none_button.clicked.connect(self._none)
        row.addWidget(self.none_button)
        row.addStretch(1)
        self.status = QLabel('')
        self.status.setStyleSheet('color: #868e96;')
        row.addWidget(self.status)
        lay.addLayout(row)
        self.grip = QSizeGrip(self)
        self.default_columns()
        self._default_state = h.saveState()
        self.restore_state()

    # --- contenu -----------------------------------------------------------------------------------------------------
    def fill(self, names, current: str = '') -> None:
        """Les modèles `names` (ceux du parcours), d'après les modèles enregistrés ; `current` : celui qui est choisi."""
        from ..cam import templates as TPL
        known = TPL.all_templates()
        self.current = current or ''
        self.tree.setSortingEnabled(False)
        self.tree.clear()
        for name in names:
            origin, tpl = known.get(name, ('', {'name': name}))
            row = row_of(name, origin, tpl)
            it = _Row()
            for c, (key, _title, number) in enumerate(COLUMNS):
                v = row[key]
                it.setText(c, _text(tr(v) if key == 'origin' and v else v))
                it.setData(c, ROLE, v if number else fold(v))
                if number:
                    it.setTextAlignment(c, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            it.setData(0, ROLE + 1, name)
            # ce qui est montré (origine traduite comprise), pour le filtre
            it.setData(0, ROLE + 2, search_fold(' '.join(it.text(c) for c in range(len(COLUMNS)))))
            if row['operations'] > 1:
                it.setToolTip(0, tr('{0} parcours dans ce modèle : les colonnes montrent le premier').format(
                    row['operations']))
            self.tree.addTopLevelItem(it)
            if name == current:
                self.tree.setCurrentItem(it)
        self.tree.setSortingEnabled(True)
        self.apply_filter()

    def rows(self) -> list:
        return [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())]

    def column_of(self, word: str) -> int:
        """La colonne nommée par `word` (sa clé, ou le début de son titre montré, sans casse ni accents) ; -1 sinon."""
        w = fold(word)
        if not w:
            return -1
        for c, (key, title, _n) in enumerate(COLUMNS):
            if w == key or fold(tr(title)).startswith(w) or fold(title).startswith(w):
                return c
        return -1

    def terms(self) -> list:
        """Le filtre en (colonne ou -1 pour toutes, mot) ; « colonne:valeur » cherche dans une seule colonne."""
        out = []
        for word in self.filter.text().split():
            col, sep, value = word.partition(':')
            c = self.column_of(col) if sep and value else -1
            out.append((c, search_fold(value)) if c >= 0 else (-1, search_fold(word)))
        return out

    def apply_filter(self) -> None:
        terms = self.terms()
        shown = 0
        for it in self.rows():
            ok = all(w in (it.data(0, ROLE + 2) if c < 0 else search_fold(it.text(c))) for c, w in terms)
            it.setHidden(not ok)
            shown += ok
        total = self.tree.topLevelItemCount()
        self.status.setText(tr('{0} modèle(s)').format(total) if shown == total
                            else tr('{0} modèle(s) sur {1}').format(shown, total))

    def visible_names(self) -> list:
        """Les modèles montrés, dans l'ordre affiché (tri compris)."""
        return [it.data(0, ROLE + 1) for it in self._visible_items()]

    def _visible_items(self) -> list:
        return [it for it in self.rows() if not it.isHidden()]

    def choose(self, name) -> None:
        if name:
            self.chosen.emit(str(name))
            self.hide()

    def _clicked(self, it) -> None:
        area = self.frameGeometry()
        self.choose(it.data(0, ROLE + 1))
        if self.isHidden():
            _SwallowClicks(area)                           # le second clic d'un double clic reste ici

    def _none(self) -> None:
        self.none_chosen.emit()
        self.hide()

    def _enter(self) -> None:
        """Entrée dans le filtre : la ligne choisie si elle est montrée, sinon la première montrée. Sans rien taper, sur
        le modèle déjà choisi : la liste se ferme, les réglages du formulaire (peut-être changés) restent."""
        it = self.tree.currentItem()
        if it is None or it.isHidden():
            names = self.visible_names()
            self.choose(names[0] if names else '')
        elif not self.filter.text().strip() and it.data(0, ROLE + 1) == self.current:
            self.hide()
        else:
            self.choose(it.data(0, ROLE + 1))

    def eventFilter(self, obj, ev) -> bool:              # noqa: N802 (API Qt)
        if ev.type() != QEvent.Type.KeyPress:
            return super().eventFilter(obj, ev)
        key = ev.key()
        if obj is self.filter and key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            self.tree.setFocus()                           # flèches depuis le filtre : dans la liste
            if self.tree.currentItem() is None or self.tree.currentItem().isHidden():
                shown = self._visible_items()
                if shown:
                    self.tree.setCurrentItem(shown[0])
            return True
        if obj is self.tree:
            shown = self._visible_items()
            if key == Qt.Key.Key_Up and (not shown or self.tree.currentItem() is shown[0]):
                self.filter.setFocus()                     # ↑ sur la première ligne : retour au filtre
                return True
            if key == Qt.Key.Key_Backspace:
                self.filter.setFocus()
                self.filter.backspace()
                return True
            mods = ev.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
            text = ev.text()
            if text and text.isprintable() and not text.isspace() and not mods:
                self.filter.setFocus()                     # la frappe va au filtre
                self.filter.insert(text)
                return True
        return super().eventFilter(obj, ev)

    # --- colonnes, tri, taille : retenus -----------------------------------------------------------------------------
    def default_columns(self) -> None:
        """Colonnes, largeurs et tri d'office."""
        h = self.tree.header()
        for c, (key, _title, _n) in enumerate(COLUMNS):
            h.setSectionHidden(c, key in HIDDEN)
            if c:
                h.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
            if key in WIDTHS:
                h.resizeSection(c, WIDTHS[key])
        self.tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)

    def reset_columns(self) -> None:
        """« Colonnes par défaut » : l'arrangement d'office (ordre, largeurs, colonnes montrées, tri), retenu."""
        self.tree.header().restoreState(self._default_state)
        self.default_columns()
        self.save_state()

    def columns_menu(self) -> QMenu:
        """Colonnes à montrer (le nom reste), et « Colonnes par défaut »."""
        m = QMenu(self)
        h = self.tree.header()
        for c, (_key, title, _n) in enumerate(COLUMNS):
            if c == 0:
                continue
            a = m.addAction(tr(title))
            a.setCheckable(True)
            a.setChecked(not h.isSectionHidden(c))
            a.toggled.connect(lambda on, col=c: self.set_column_shown(col, on))
        m.addSeparator()
        m.addAction(tr('Colonnes par défaut'), self.reset_columns)
        return m

    def show_columns_menu(self, pos) -> None:
        m = self.columns_menu()
        m.exec(self.tree.header().mapToGlobal(pos))
        m.deleteLater()

    def set_column_shown(self, column: int, on: bool) -> None:
        if column > 0:
            self.tree.header().setSectionHidden(column, not on)
            self.save_state()

    def save_state(self) -> None:
        """L'arrangement des colonnes ; la taille seulement si l'utilisateur l'a donnée (pas celle que la place
        impose)."""
        if self.settings is None:
            return
        self.settings.setValue(STATE_KEY, self.tree.header().saveState())
        self.settings.setValue(STATE_COLUMNS_KEY, len(COLUMNS))
        if self._user_size is not None:
            self.settings.setValue(SIZE_KEY, list(self._user_size))

    def restore_state(self) -> None:
        h = self.tree.header()
        got = self.settings.value(STATE_KEY, None) if self.settings is not None else None
        try:
            same = int(self.settings.value(STATE_COLUMNS_KEY, 0)) == len(COLUMNS)
        except (TypeError, ValueError, AttributeError):
            same = False
        if same and isinstance(got, (QByteArray, bytes, bytearray)) and len(got):
            if not h.restoreState(QByteArray(got)) or h.count() != len(COLUMNS) \
                    or not 0 <= h.sortIndicatorSection() < len(COLUMNS):
                h.restoreState(self._default_state)
                self.default_columns()
            h.setSectionHidden(0, False)
        h.setSortIndicatorShown(True)

    def wanted_size(self, least_width: int) -> tuple:
        w, h = max(least_width, SIZE[0]), SIZE[1]
        got = self.settings.value(SIZE_KEY, None) if self.settings is not None else None
        try:
            w, h = max(least_width, int(got[0])), max(160, int(got[1]))
        except (TypeError, ValueError, IndexError):
            pass
        return w, h

    def place(self, x: int, y: int, w: int, h: int) -> None:
        """Pose la liste (taille d'ouverture : pas une taille voulue par l'utilisateur)."""
        self._placed = QSize(w, h)
        self.setGeometry(x, y, w, h)
        self._placed = self.size()

    def resizeEvent(self, ev) -> None:                   # noqa: N802 (API Qt)
        super().resizeEvent(ev)
        s = self.grip.sizeHint()
        self.grip.move(self.width() - s.width(), self.height() - s.height())
        if self.isVisible() and self._placed is not None and ev.size() != self._placed:
            self._user_size = (ev.size().width(), ev.size().height())     # tirée à la poignée

    def hideEvent(self, ev) -> None:                     # noqa: N802 (API Qt)
        self.save_state()
        super().hideEvent(ev)


class TemplateCombo(QComboBox):
    """Liste déroulante des modèles d'un parcours : ses entrées sont celles d'une liste ordinaire (le texte et, en
    donnée, le nom du modèle ; la première : « réglages ci-dessous », sans nom) ; déroulée, elle montre la liste à
    colonnes."""

    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        if settings is None:
            from .. import portable
            settings = portable.settings()
        self.settings = settings
        self._popup = None
        self.setToolTip(tr('Les modèles de ce parcours, en liste à colonnes : filtre à la frappe, tri par un clic sur '
                           'un en-tête, colonnes au choix par le clic droit sur l’en-tête'))

    def names(self) -> list:
        return [self.itemData(i) for i in range(self.count()) if self.itemData(i)]

    def popup(self) -> TemplatePopup:
        """La liste à colonnes, à jour des entrées de la liste."""
        if self._popup is None:
            self._popup = TemplatePopup(self, self.settings)
            self._popup.chosen.connect(self._chosen)
            self._popup.none_chosen.connect(self._none)
        self._popup.fill(self.names(), self.currentData() or '')
        none = self.findData('')
        self._popup.none_button.setVisible(none >= 0)
        if none >= 0:
            self._popup.none_button.setText(self.itemText(none))
        return self._popup

    def _chosen(self, name: str) -> None:
        i = self.findData(name)
        if i >= 0:
            if i == self.currentIndex():                   # le même modèle redemandé : ses réglages reviennent
                self.currentIndexChanged.emit(i)
            else:
                self.setCurrentIndex(i)

    def _none(self) -> None:
        i = self.findData('')
        if i >= 0:
            self.setCurrentIndex(i)

    def _screen(self):
        """L'écran où est la liste (plusieurs écrans : celui de la liste, pas forcément celui de la fenêtre)."""
        return QGuiApplication.screenAt(self.mapToGlobal(self.rect().center())) or self.screen()

    def showPopup(self) -> None:                         # noqa: N802 (API Qt)
        if not self.names():                               # aucun modèle : la liste ordinaire (une ligne)
            super().showPopup()
            return
        p = self.popup()
        w, h = p.wanted_size(self.width())
        screen = self._screen()
        area = screen.availableGeometry() if screen is not None else None
        at = self.mapToGlobal(QPoint(0, self.height()))
        if area is not None:
            w, h = min(w, area.width() - 16), min(h, area.height() - 16)
            at.setX(max(area.left() + 8, min(at.x(), area.right() - w - 8)))
            if at.y() + h > area.bottom() - 8:             # pas la place dessous : au-dessus
                at.setY(max(area.top() + 8, self.mapToGlobal(QPoint(0, 0)).y() - h))
        p.filter.clear()
        p.place(at.x(), at.y(), w, h)
        p.show()
        p.filter.setFocus()
        it = p.tree.currentItem()
        if it is not None:
            p.tree.scrollToItem(it, QAbstractItemView.ScrollHint.PositionAtCenter)   # le modèle choisi, à l'écran

    def hidePopup(self) -> None:                         # noqa: N802 (API Qt)
        if self._popup is not None and self._popup.isVisible():
            self._popup.hide()
        super().hidePopup()
