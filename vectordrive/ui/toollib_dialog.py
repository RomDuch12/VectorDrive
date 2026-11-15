"""Gestionnaire d'outils : bibliothèque (tools.json), fiche de l'outil
(réglages, cotes du fabricant, catalogue), silhouette, dessins DXF / STEP,
catalogues en ligne, import et export (VectorDrive, NeoDrive, TypeEdit .Dbt
en mode de compatibilité, CSV, données fabricant ISO 13399)."""
from __future__ import annotations

import pathlib

from PySide6.QtCore import QItemSelectionModel, QPointF, Qt, QUrl
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout,
                               QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
                               QPlainTextEdit, QPushButton, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from ..cam import catalogs, model, toollib
from ..i18n import tr

MINE = '__mienne__'
DOC = '__document__'
PREVIEW = (220, 300)


def silhouette(tool, w: int = PREVIEW[0], h: int = PREVIEW[1]) -> QPixmap:
    """Silhouette de l'outil debout, partie coupante en or, corps en gris."""
    from ..cam import tooldraw
    pm = QPixmap(w, h)
    pm.fill(QColor('#f4f5f7'))
    try:
        pts, z_cut = tooldraw.outline(tool)
    except Exception:                                 # cotes incohérentes : rien à dessiner
        return pm
    xs, zs = [p[0] for p in pts], [p[1] for p in pts]
    span_x, span_z = max(xs) - min(xs) or 1.0, max(zs) - min(zs) or 1.0
    k = min((w - 30) / span_x, (h - 30) / span_z)
    tr_ = lambda x, z: QPointF(w / 2 + x * k, h - 15 - z * k)      # noqa: E731
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    poly = QPolygonF([tr_(x, z) for x, z in pts])
    p.setPen(QPen(QColor('#40444c'), 1.2))
    p.setBrush(QBrush(QColor('#a7abb3')))
    p.drawPolygon(poly)
    cut = QPainterPath()
    cut.addRect(0, h - 15 - z_cut * k, w, z_cut * k + 15)
    clip = QPainterPath()
    clip.addPolygon(poly)
    p.setBrush(QBrush(QColor('#d9ad40')))
    p.drawPath(clip.intersected(cut))
    p.setPen(QPen(QColor('#c92a2a'), 1, Qt.PenStyle.DashLine))
    p.drawLine(QPointF(w / 2, 6), QPointF(w / 2, h - 6))
    p.end()
    return pm


class CatalogsDialog(QDialog):
    """Fabricants, revendeurs et plateformes : site, recherche d'une référence."""

    def __init__(self, parent, ref: str = '', vendor: str = ''):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        self.setWindowTitle(tr('Catalogues d\'outils en ligne'))
        self.resize(820, 560)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(tr('VectorDrive ne copie aucune donnée de catalogue : il ouvre le site du '
                                'fabricant et importe les fichiers qu\'on y télécharge (Importer…).')))
        row = QHBoxLayout()
        row.addWidget(QLabel(tr('Référence')))
        self.ref = QLineEdit(ref)
        row.addWidget(self.ref, 1)
        lay.addLayout(row)
        self.table = QTableWidget(len(catalogs.VENDORS), 5)
        self.table.setHorizontalHeaderLabels([tr('Nom'), tr('Type'), tr('Pays'), tr('Données'), tr('Remarque')])
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        for r, v in enumerate(catalogs.VENDORS):
            for c, txt in enumerate((v.name, tr(v.kind), v.country, v.formats, tr(v.note) if v.note else '')):
                self.table.setItem(r, c, QTableWidgetItem(txt))
        self.table.doubleClicked.connect(lambda _i: self.search())
        lay.addWidget(self.table, 1)
        start = catalogs.vendor(vendor)
        if start is not None:
            self.table.selectRow(catalogs.VENDORS.index(start))
        row = QHBoxLayout()
        for text, slot in ((tr('Ouvrir le site'), self.open_site), (tr('Chercher la référence'), self.search)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, s=slot: s())
            row.addWidget(b)
        row.addStretch(1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.reject)
        row.addWidget(bb)
        lay.addLayout(row)
        self.opened: list[str] = []

    def current(self):
        r = self.table.currentRow()
        return catalogs.VENDORS[r] if r >= 0 else None

    def _open(self, url: str) -> str:
        self.opened.append(url)
        if not getattr(self, 'dry_run', False):
            QDesktopServices.openUrl(QUrl(url))
        return url

    def open_site(self) -> str | None:
        v = self.current()
        return self._open(catalogs.search_url(v, '')) if v else None

    def search(self) -> str | None:
        v = self.current()
        return self._open(catalogs.search_url(v, self.ref.text())) if v else None


class _LibTree(QTreeWidget):
    """Arbre de Mes outils : glisser des outils sur un dossier les y range,
    sur un outil les place juste avant lui (réordonner)."""

    def __init__(self, on_drop):
        super().__init__()
        self.on_drop = on_drop

    def dropEvent(self, ev) -> None:                           # noqa: N802 (API Qt)
        target = self.itemAt(ev.position().toPoint())
        ev.setDropAction(Qt.DropAction.IgnoreAction)          # l'arbre est refait : pas de déplacement Qt
        ev.accept()
        self.on_drop(target)


class ToolLibraryDialog(QDialog):
    """Bibliothèque d'outils de l'utilisateur, outils du document et
    bibliothèques des plugins (en lecture)."""

    NUM = (('diameter', 'Diamètre (mm)'), ('tip', 'Pointe (mm)'), ('angle', 'Angle au sommet (°)'),
           ('cut_length', 'Longueur utile (mm)'), ('spindle', 'Broche (tr/min)'), ('feed', 'Avance (mm/min)'),
           ('finish_feed', 'Avance de finition (mm/min)'), ('plunge', 'Plongée (mm/min)'),
           ('step_down', 'Passe en Z (mm)'), ('stepover', 'Recouvrement (× Ø)'))
    COTES = (('D1', 'D1 Ø de coupe'), ('D2', 'D2 Ø de queue'), ('D3', 'D3 Ø de dégagement'),
             ('L1', 'L1 longueur totale'), ('L2', 'L2 longueur de coupe'), ('L3', 'L3 longueur de dégagement'),
             ('R', 'R rayon'))

    def __init__(self, parent, panel=None, path=None):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)                                 # pas de défilement horizontal à l'ouverture
        self.setWindowTitle(tr('Bibliothèque d\'outils'))
        self.setSizeGripEnabled(True)
        avail = self.screen().availableGeometry() if self.screen() is not None else None
        self.resize(min(1180, avail.width() - 40) if avail else 1080, min(760, avail.height() - 60) if avail else 700)
        self.panel = panel
        self.path = pathlib.Path(path) if path else toollib.default_path()
        self.mine = toollib.load(self.path) if self.path.exists() else []
        #: dossiers créés à la main, même vides (gardés dans tools.json)
        self.empty_folders = toollib.load_folders(self.path)
        self.tools: list = []
        self.current = None
        self.settings = getattr(parent, 'settings', None)
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel(tr('Bibliothèque')))
        self.source = QComboBox()
        self.source.addItem(tr('Mes outils ({0})').format(self.path.name), MINE)
        if panel is not None:
            self.source.addItem(tr('Outils du document'), DOC)
        from ..plugins import REGISTRY
        for name in REGISTRY.tool_libraries:
            self.source.addItem(tr(name), name)
        self.source.currentIndexChanged.connect(self.reload)
        self.source.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.source.setMinimumContentsLength(16)
        top.addWidget(self.source, 1)
        head = top
        top = QHBoxLayout()                                      # les commandes : une ligne à part
        # une seule barre : les commandes rares dans « Plus », et toutes au clic droit
        from PySide6.QtGui import QAction
        from PySide6.QtWidgets import QMenu, QToolButton
        self.acts: dict[str, QAction] = {}
        for key, text, tip, slot in (
                ('new', tr('Nouvel outil'), tr('Un outil dans le dossier choisi'), self.new_tool),
                ('newdir', tr('Nouveau dossier…'), tr('Un sous-dossier du dossier choisi (les outils choisis y '
                                                      'vont)'), self.new_folder),
                ('imp', tr('Importer des fichiers…'), tr('Un ou plusieurs fichiers d\'outils : chacun devient un '
                                                        'dossier de Mes outils'), self.import_dialog),
                ('impdir', tr('Importer un dossier…'), tr('Tous les fichiers d\'outils d\'un dossier et de ses '
                                                         'sous-dossiers, rangés dans Mes outils comme sur le disque'),
                 self.import_folder_dialog),
                ('exp', tr('Exporter…'), tr('Les outils de la bibliothèque montrée, dans un fichier'), self.export_dialog),
                ('up', '↑', tr('Monter les outils choisis dans leur dossier'), lambda: self.shift(-1)),
                ('down', '↓', tr('Descendre les outils choisis dans leur dossier'), lambda: self.shift(1)),
                ('move', tr('Déplacer vers…'), tr('Mettre les outils choisis dans un dossier (existant ou nouveau) — '
                                                  'ou les glisser sur un dossier'), self.move_to_folder),
                ('dup', tr('Dupliquer'), tr('Une copie de l\'outil choisi'), self.duplicate),
                ('ren', tr('Renommer…'), tr('Renommer l\'outil ou le dossier choisi (F2)'), self.rename),
                ('merge', tr('Fusionner le dossier…'), tr('Verser les outils du dossier choisi dans un autre dossier'),
                 self.merge_folder),
                ('del', tr('Supprimer'), tr('Les outils choisis, ou le dossier choisi et ses outils (Suppr)'),
                 self.delete),
                ('draw', tr('Dessins DXF + STEP'), tr('Silhouette et volume de l\'outil choisi, en fichiers'), self.draw),
                ('cat', tr('Catalogues en ligne…'), tr('Sites des fabricants : chercher la référence'),
                 self.open_catalogs),
                ('add', tr('Ajouter au document'), tr('Copie de l\'outil choisi dans les outils du document'),
                 self.add_to_document),
                ('keep', tr('Copier dans mes outils'), tr('Copie de l\'outil choisi dans Mes outils'), self.copy_to_mine),
                ('prefs', tr('Outils par opération…'), tr('Quels outils proposer, et dans quel ordre, pour chaque '
                                                         'type d\'opération'), self.tool_prefs),
                ('machines', tr('Machines…'), tr('Sur quelles machines (post-processeurs) les outils choisis — ou ceux '
                                                 'du dossier choisi — sont montés ; aucune : toutes'),
                 self.set_machines),
                ('aliases', tr('Outils des programmes lus…'), tr('Les outils choisis à la place de ceux des '
                                                                 'programmes lus (case « Retenir ce choix ») : les '
                                                                 'voir, en oublier'), self.program_aliases),
                ('full', '⛶', tr('Plein écran (F11)'), self.toggle_full_screen)):
            a = QAction(text, self)
            a.setToolTip(tip)
            a.setStatusTip(tip)
            a.triggered.connect(lambda _=False, sl=slot: sl())
            self.acts[key] = a
        self.acts['ren'].setShortcut('F2')
        self.acts['del'].setShortcut('Del')
        self.acts['full'].setShortcut('F11')
        for k in ('ren', 'del'):
            self.acts[k].setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self.addAction(self.acts['full'])
        self.buttons = {}

        def button(key, menu_keys=()):
            b = QToolButton()
            b.setDefaultAction(self.acts[key])
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            if menu_keys:
                m = QMenu(b)
                for k in menu_keys:
                    m.addSeparator() if k == '-' else m.addAction(self.acts[k])
                b.setMenu(m)
                b.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
            top.addWidget(b)
            self.buttons[key] = b
            return b
        button('new')
        button('newdir')
        button('imp', ('imp', 'impdir'))
        button('exp')
        button('up')
        button('down')
        button('move')
        self.buttons['take'] = b = QToolButton()                 # l'outil choisi vers l'autre bibliothèque
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        top.addWidget(b)
        more = QToolButton()
        more.setText(tr('Plus'))
        more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        m = QMenu(more)
        for k in ('dup', 'ren', 'merge', 'del', '-', 'machines', 'aliases', '-', 'draw', 'cat', '-', 'add', 'keep', '-',
                  'impdir'):
            m.addSeparator() if k == '-' else m.addAction(self.acts[k])
        more.setMenu(m)
        top.addWidget(more)
        self.buttons['more'] = more
        top.addStretch(1)
        lay.addLayout(head)
        lay.addLayout(top)
        bar_row = top
        top = head
        button('prefs')
        button('full')
        top = bar_row
        from .tool_filters import FilterBar, open_large
        self.filters = FilterBar(self.settings, self)
        self.filters.changed.connect(self.fill)
        try:
            mk = panel.setup().post if panel is not None else ''
            ml = panel.post.currentText() if panel is not None and hasattr(panel, 'post') else mk
        except Exception:                                      # panneau sans réglage FAO (essais)
            mk = ml = ''
        self._machine = (mk or '', ml or mk or '')
        self.filters.set_machine(self._machine[0], self._machine[1], self.mine)
        self.filter = self.filters.text                          # recherche (compatibilité)
        lay.addWidget(self.filters)
        open_large(self, self.settings, 'outils/fenetre_agrandie', full=True)
        split = QSplitter()
        self.tree = _LibTree(self.dropped)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)     # Ctrl / Maj : plusieurs
        self.tree.setDragEnabled(True)
        self.tree.setAcceptDrops(True)
        self.tree.setDropIndicatorShown(True)
        self.tree.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        for k in ('ren', 'del'):
            self.tree.addAction(self.acts[k])
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(lambda _p: self.context_menu())
        from .tool_columns import install                 # colonnes arrangeables, n° T dans la sienne (cachée)
        install(self.tree, self.settings, 'outils/bibliotheque_colonnes')
        from .tool_filters import sortable
        sortable(self.tree, lambda: self.fill())        # clic sur un titre : trier ; troisième clic : l'ordre rangé
        self.tree.header().sortIndicatorChanged.connect(lambda _c, _o: self._order_actions())
        self.tree.header().setToolTip(tr('Clic sur un titre : trier (croissant, décroissant, puis l’ordre rangé ; '
                                         'Monter et Descendre seulement dans l’ordre rangé)'))
        from PySide6.QtCore import QSize
        self.tree.setIconSize(QSize(14, 26))
        self.tree.currentItemChanged.connect(self._select)
        split.addWidget(self.tree)
        right = QWidget()
        rl = QHBoxLayout(right)
        form_w = QWidget()
        form = QFormLayout(form_w)
        self.w = {}
        self.w['name'] = QLineEdit()
        form.addRow(tr('Nom'), self.w['name'])
        self.w['kind'] = QComboBox()
        for k, lab in model.TOOL_KINDS.items():
            self.w['kind'].addItem(tr(lab), k)
        form.addRow(tr('Nature'), self.w['kind'])
        self.w['number'] = QSpinBox()
        self.w['number'].setRange(0, 999)
        form.addRow(tr('N° dans le magasin (T)'), self.w['number'])
        self.w['flutes'] = QSpinBox()
        self.w['flutes'].setRange(0, 99)
        form.addRow(tr('Nombre de dents'), self.w['flutes'])
        for key, lab in self.NUM:
            sb = QDoubleSpinBox()
            sb.setRange(0, 1e6)
            sb.setDecimals(3)
            self.w[key] = sb
            form.addRow(tr(lab), sb)
        g = QGroupBox(tr('Cotes du fabricant'))
        gf = QFormLayout(g)
        for key, lab in self.COTES:
            sb = QDoubleSpinBox()
            sb.setRange(0, 10000)
            sb.setDecimals(3)
            sb.setSpecialValueText('—')
            self.w['g_' + key] = sb
            gf.addRow(tr(lab), sb)
        form.addRow(g)
        g = QGroupBox(tr('Catalogue'))
        gf = QFormLayout(g)
        self.w['vendor'] = QLineEdit()
        gf.addRow(tr('Fabricant'), self.w['vendor'])
        self.w['ref'] = QLineEdit()
        gf.addRow(tr('Référence'), self.w['ref'])
        self.w['c_url'] = QLineEdit()
        gf.addRow(tr('Fiche en ligne'), self.w['c_url'])
        self.w['c_prix'] = QDoubleSpinBox()
        self.w['c_prix'].setRange(0, 1e6)
        self.w['c_prix'].setDecimals(2)
        self.w['c_prix'].setSuffix(' €')
        gf.addRow(tr('Prix'), self.w['c_prix'])
        b = QPushButton(tr('Voir la fiche en ligne'))
        b.clicked.connect(self.open_sheet)
        gf.addRow(b)
        form.addRow(g)
        self.w['notes'] = QPlainTextEdit()
        self.w['notes'].setFixedHeight(54)
        form.addRow(tr('Notes'), self.w['notes'])
        b = QPushButton(tr('Enregistrer la fiche'))
        b.clicked.connect(self.apply)
        form.addRow(b)
        from PySide6.QtWidgets import QScrollArea
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setWidget(form_w)
        rl.addWidget(sc, 1)
        side = QVBoxLayout()
        self.preview = QLabel()
        self.preview.setFixedSize(*PREVIEW)
        side.addWidget(self.preview)
        self.drawings = QLabel()
        self.drawings.setWordWrap(True)
        self.drawings.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        side.addWidget(self.drawings)
        # les dessins de l'outil : ouverts dans un nouvel onglet, ou posés à la souris sur le dessin en cours
        from PySide6.QtWidgets import QGridLayout
        grid = QGridLayout()
        self.drawing_buttons: dict = {}
        for row, kind in enumerate(('dxf', 'step')):
            grid.addWidget(QLabel(kind.upper()), row, 0)
            for col, (what, text, tip) in enumerate(
                    (('open', tr('Ouvrir'), tr('Ouvrir ce dessin de l’outil dans un nouvel onglet')),
                     ('place', tr('Poser au clic'),
                      tr('Poser ce dessin de l’outil à la souris, sur le dessin en cours'))), 1):
                b = QPushButton(text)
                b.setToolTip(tip)
                b.setEnabled(False)
                b.clicked.connect(lambda _=False, k=kind, w=what: self.use_drawing(k, w))
                grid.addWidget(b, row, col)
                self.drawing_buttons[(kind, what)] = b
        side.addLayout(grid)
        side.addStretch(1)
        rl.addLayout(side)
        split.addWidget(right)
        split.setSizes([460, 700])
        lay.addWidget(split, 1)
        self.info = QLabel()
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.reload()

    # --- sources -----------------------------------------------------------------------------
    def source_key(self) -> str:
        return self.source.currentData()

    def editable(self) -> bool:
        return self.source_key() in (MINE, DOC)

    def reload(self) -> None:
        key = self.source_key()
        if key == MINE:
            self.tools = self.mine
        elif key == DOC:
            self.tools = self.panel.setup().tools
        else:
            from ..plugins import REGISTRY
            try:
                self.tools = list(REGISTRY.tool_libraries[key]())
            except Exception as ex:
                self.tools = []
                self.info.setText(str(ex))
        for k in ('new', 'dup', 'del', 'imp'):
            self.acts[k].setEnabled(self.editable())
        for k in ('move', 'merge', 'impdir', 'newdir', 'up', 'down'):
            self.acts[k].setEnabled(key == MINE)
        self.acts['ren'].setEnabled(self.editable())
        self.tree.setDragEnabled(key == MINE)
        self.acts['add'].setEnabled(key != DOC and self.panel is not None)
        self.acts['keep'].setEnabled(key != MINE)
        take = self.acts['add'] if self.acts['add'].isEnabled() else self.acts['keep']
        self.buttons['take'].setDefaultAction(take)
        self.filters.set_tools(self.tools)
        self.fill()

    def persist(self) -> None:
        key = self.source_key()
        if key == MINE:
            have = set(toollib.folders(self.mine))
            self.empty_folders = [f for f in dict.fromkeys(self.empty_folders) if f not in have]
            toollib.save(self.mine, self.path, self.empty_folders)
        elif key == DOC:
            self.panel.save(self.panel.setup())

    # --- liste -----------------------------------------------------------------------------------
    def _folder_item(self, groups: dict, name: str) -> QTreeWidgetItem:
        """Ligne du dossier `name` (« Datron/Fraises » : sous « Datron »),
        créée avec ses parents au besoin."""
        from .tool_filters import group_item
        parts = toollib.folder_parts(name) or [name]
        parent = None
        for i, part in enumerate(parts):
            key = toollib.SEP.join(parts[:i + 1])
            it = groups.get(key)
            if it is None:
                it = groups[key] = group_item(['📁 ' + part])
                it.setData(0, Qt.ItemDataRole.UserRole + 1, key)
                f = it.font(0)
                f.setBold(True)
                it.setFont(0, f)
                if parent is None:
                    self.tree.addTopLevelItem(it)
                else:
                    parent.addChild(it)
            parent = it
        return parent

    def _order_actions(self) -> None:
        """Monter, Descendre : dans Mes outils, et seulement dans l'ordre rangé (pas trié par une colonne)."""
        for k in ('up', 'down'):
            self.acts[k].setEnabled(self.source_key() == MINE and self.tree.sortColumn() < 0)

    def fill(self) -> None:
        from .tool_columns import COLUMNS
        from .tool_columns import row as tool_row
        from .tool_filters import group_item
        q = self.filters.active()
        self.tree.clear()
        groups = {}
        shown = self.filters.apply(self.tools)
        op = self.filters.op.currentData()
        by_folder = self.source_key() == MINE and not op   # Mes outils : par dossier (un import = un dossier)
        if op:                                            # « Adaptés à » : une liste, dans l'ordre proposé
            g = groups[''] = group_item([tr('Proposés pour : {0}').format(
                tr(model.op_kinds().get(op, op)).split(' (')[0])])
            g.setFlags(g.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.tree.addTopLevelItem(g)
        for t in shown:
            if op:
                g = groups['']
            elif by_folder:
                g = self._folder_item(groups, toollib.folder_of(t))
            else:
                g = groups.get(t.kind)
                if g is None:
                    g = groups[t.kind] = group_item([tr(model.TOOL_KINDS.get(t.kind, t.kind))])
                    g.setFlags(g.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                    self.tree.addTopLevelItem(g)
            it = tool_row(t)
            it.setData(0, Qt.ItemDataRole.UserRole, t.id)
            from .tool_filters import tool_icon
            it.setIcon(0, tool_icon(t, 14, 26))
            tip = toollib.summary(t, self._mlabels())
            for c in range(len(COLUMNS)):
                it.setToolTip(c, tip)
            g.addChild(it)
        if by_folder and not q:
            for f in self.empty_folders:                   # dossiers créés, encore vides
                self._folder_item(groups, f)
        self.tree.expandAll()
        self._order_actions()                             # triée : monter, descendre n'ont plus de sens
        text =tr('{0} outil(s)').format(len(self.tools)) if len(shown) == len(self.tools) else \
            tr('{0} outil(s) sur {1}').format(len(shown), len(self.tools))
        if by_folder:
            text += '  —  ' + tr('fichier : {0}').format(self.path)
        self.info.setText(text)

    def offer_machine(self, tools) -> str:
        """Outils importés et machine du réglage FAO connue : l'indication à
        ajouter (ils servent partout ; Machines… pour les réserver — le dossier
        importé reste choisi). Rien n'est changé sans le demander."""
        key, label = getattr(self, '_machine', ('', ''))
        if not key or not tools or not self.editable():
            return ''
        return '\n' + tr('Ces outils servent sur toutes les machines ; Plus › Machines… pour les réserver à « {0} ».'
                          ).format(label)

    def _mlabels(self) -> dict:
        if getattr(self, '_ml', None) is None:
            from .tool_filters import machine_labels
            d = self.panel.machines_dir() if self.panel is not None and hasattr(self.panel, 'machines_dir') else ''
            self._ml = machine_labels(d)
        return self._ml

    def set_machines(self, keys: list | None = None) -> int:
        """Machines des outils choisis (ou du dossier choisi) : liste à cocher
        des post-processeurs ; aucune cochée : l'outil sert partout. Rend le
        nombre d'outils changés."""
        tools = self.selected_tools()
        if not tools:
            folder = self.selected_folder()
            if folder is not None:
                tools = [t for t in self.tools if toollib.in_folder(t, folder)]
        if not tools or not self.editable():
            return 0
        if keys is None:
            from PySide6.QtWidgets import QDialogButtonBox, QListWidget, QListWidgetItem
            labels = self._mlabels()
            dlg = QDialog(self)
            dlg.setWindowTitle(tr('Machines des outils'))
            v = QVBoxLayout(dlg)
            v.addWidget(QLabel(tr('{0} outil(s) : machines où ils sont montés (aucune : toutes)').format(len(tools))))
            lst = QListWidget()
            have = set(tools[0].machines or [])
            for k, lab in list(labels.items()) + [(k, k) for k in sorted(have) if k not in labels]:
                it = QListWidgetItem(tr(lab))
                it.setData(Qt.ItemDataRole.UserRole, k)
                it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                it.setCheckState(Qt.CheckState.Checked if k in have else Qt.CheckState.Unchecked)
                lst.addItem(it)
            v.addWidget(lst, 1)
            bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            bb.accepted.connect(dlg.accept)
            bb.rejected.connect(dlg.reject)
            v.addWidget(bb)
            dlg.resize(460, 420)
            if not dlg.exec():
                return 0
            keys = [lst.item(i).data(Qt.ItemDataRole.UserRole) for i in range(lst.count())
                    if lst.item(i).checkState() == Qt.CheckState.Checked]
        for t in tools:
            t.machines = list(keys)
        self.persist()
        self.filters.set_machine(self._machine[0], self._machine[1], self.tools)
        self.fill()
        return len(tools)

    def tool_by_id(self, tid):
        return next((t for t in self.tools if t.id == tid), None)

    def selected(self):
        it = self.tree.currentItem()
        return self.tool_by_id(it.data(0, Qt.ItemDataRole.UserRole)) if it else None

    def selected_tools(self) -> list:
        """Outils choisis (plusieurs avec Ctrl / Maj), dans l'ordre de la
        bibliothèque ; un dossier choisi compte pour tous ses outils."""
        ids, folders = set(), []
        for it in self.tree.selectedItems():
            tid = it.data(0, Qt.ItemDataRole.UserRole)
            if tid:
                ids.add(tid)
            elif it.data(0, Qt.ItemDataRole.UserRole + 1):
                folders.append(it.data(0, Qt.ItemDataRole.UserRole + 1))
        cur = self.selected()
        if not ids and not folders and cur is not None:
            ids.add(cur.id)
        return [t for t in self.tools if t.id in ids or any(toollib.in_folder(t, f) for f in folders)]

    def dropped(self, target) -> bool:
        """Glisser-déposer : sur un dossier, les outils y vont ; sur un
        outil, ils se placent juste avant lui (dans son dossier)."""
        moving = self.selected_tools()
        if not moving or self.source_key() != MINE or target is None:
            return False
        folder = target.data(0, Qt.ItemDataRole.UserRole + 1)
        before = None
        if not folder:
            before = self.tool_by_id(target.data(0, Qt.ItemDataRole.UserRole))
            if before is None or before in moving:
                return False
            folder = toollib.folder_of(before)
        toollib.place(self.mine, moving, folder, before)
        self.persist()
        self.fill()
        self._reselect(moving)
        return True

    def _reselect(self, tools) -> None:
        ids = {t.id for t in tools}
        self.tree.clearSelection()
        first = None
        for it in self._items():
            if it.data(0, Qt.ItemDataRole.UserRole) in ids:
                it.setSelected(True)
                first = first or it
        if first is not None:
            self.tree.setCurrentItem(first, 0, QItemSelectionModel.SelectionFlag.NoUpdate)

    def shift(self, d: int) -> bool:
        """↑ / ↓ : les outils choisis montent ou descendent dans leur dossier."""
        moving = self.selected_tools()
        if not moving or self.source_key() != MINE or not toollib.shift(self.mine, moving, d):
            return False
        self.persist()
        self.fill()
        self._reselect(moving)
        return True

    def new_folder(self, name: str | None = None) -> str | None:
        """Nouveau sous-dossier du dossier choisi ; les outils choisis y vont
        (aucun : il reste vide, gardé tout de même)."""
        if self.source_key() != MINE:
            return None
        parent = self.selected_folder()
        tools = [t for t in self.selected_tools() if self.tree.currentItem() is not None
                 and self.tree.currentItem().data(0, Qt.ItemDataRole.UserRole)]
        if name is None:
            from PySide6.QtWidgets import QInputDialog
            name, ok = QInputDialog.getText(self, tr('Nouveau dossier'),
                                            tr('Nom (dans « {0} »)').format(parent) if parent else tr('Nom'))
            if not ok:
                return None
        name = (name or '').strip()
        if not name:
            return None
        full = toollib.join_folder(parent, name) if parent and parent != toollib.NO_FOLDER else \
            toollib.join_folder(name)
        if tools:
            toollib.place(self.mine, tools, full)
        elif full not in self.empty_folders:
            self.empty_folders.append(full)
        self.persist()
        self.fill()
        self.select_folder(full)
        return full

    def rename(self, new: str | None = None) -> bool:
        """Renommer (F2) : le dossier choisi, ou l'outil choisi."""
        it = self.tree.currentItem()
        if it is None or not self.editable():
            return False
        if it.data(0, Qt.ItemDataRole.UserRole + 1):
            return self.rename_folder(new)
        t = self.selected()
        if t is None:
            return False
        if new is None:
            from PySide6.QtWidgets import QInputDialog
            new, ok = QInputDialog.getText(self, tr('Renommer l\'outil'), tr('Nouveau nom'), text=t.name)
            if not ok:
                return False
        new = (new or '').strip()
        if not new or new == t.name:
            return False
        t.name = new
        self.persist()
        self.fill()
        self.select(t)
        return True

    def selected_folder(self) -> str | None:
        """Dossier choisi (ligne du dossier, ou dossier de l'outil choisi)."""
        it = self.tree.currentItem()
        if it is None:
            return None
        f = it.data(0, Qt.ItemDataRole.UserRole + 1)
        if f:
            return f
        t = self.selected()
        return toollib.folder_of(t) if t is not None else None

    def _items(self):
        """Toutes les lignes de l'arbre (dossiers et outils), en profondeur."""
        stack = [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount() - 1, -1, -1)]
        while stack:
            it = stack.pop()
            yield it
            stack.extend(it.child(j) for j in range(it.childCount() - 1, -1, -1))

    def select_folder(self, name: str) -> None:
        key = toollib.join_folder(name) or name
        for it in self._items():
            if it.data(0, Qt.ItemDataRole.UserRole + 1) == key:
                self.tree.setCurrentItem(it)
                return

    # --- dossiers de Mes outils ------------------------------------------------------------------
    def move_to_folder(self, name: str | None = None) -> bool:
        tools = self.selected_tools()
        if not tools or self.source_key() != MINE:
            return False
        if name is None:
            from PySide6.QtWidgets import QInputDialog
            names = list(dict.fromkeys(toollib.folders(self.mine) + self.empty_folders))
            cur = toollib.folder_of(tools[0])
            name, ok = QInputDialog.getItem(self, tr('Déplacer vers un dossier'),
                                            tr('Dossier (choisir, ou taper un nouveau nom)'), names,
                                            names.index(cur) if cur in names else 0, True)
            if not ok:
                return False
        if not (name or '').strip():
            return False
        toollib.place(self.mine, tools, name)
        self.persist()
        self.fill()
        self._reselect(tools)
        return True

    def rename_folder(self, new: str | None = None) -> bool:
        old = self.selected_folder()
        if old is None or self.source_key() != MINE:
            return False
        if new is None:
            from PySide6.QtWidgets import QInputDialog
            new, ok = QInputDialog.getText(self, tr('Renommer le dossier'), tr('Nouveau nom'), text=old)
            if not ok:
                return False
        new = (new or '').strip()
        if not new or new == old:
            return False
        toollib.rename_folder(self.mine, old, new)
        self.empty_folders = [toollib.join_folder(new, f[len(old) + 1:]) if f.startswith(old + toollib.SEP)
                              else new if f == old else f for f in self.empty_folders]
        self.persist()
        self.fill()
        self.select_folder(new)
        return True

    def merge_folder(self, target: str | None = None) -> bool:
        src = self.selected_folder()
        if src is None or self.source_key() != MINE:
            return False
        others = [f for f in toollib.folders(self.mine) if f != src]
        if not others:
            return False
        if target is None:
            from PySide6.QtWidgets import QInputDialog
            target, ok = QInputDialog.getItem(self, tr('Fusionner les dossiers'),
                                              tr('Verser « {0} » dans').format(src), others, 0, False)
            if not ok:
                return False
        if target not in others:
            return False
        n = toollib.merge_folders(self.mine, src, target)
        self.persist()
        self.fill()
        self.select_folder(target)
        self.info.setText(tr('{0} outil(s) versé(s) de « {1} » dans « {2} »').format(n, src, target))
        return True

    def delete_folder(self, confirm: bool = True) -> bool:
        name = self.selected_folder()
        if name is None or self.source_key() != MINE:
            return False
        n = sum(1 for t in self.mine if toollib.in_folder(t, name))
        if confirm and QMessageBox.question(
                self, tr('Supprimer le dossier'),
                tr('Supprimer le dossier « {0} » et ses {1} outil(s) ?').format(name, n)) \
                != QMessageBox.StandardButton.Yes:
            return False
        self.mine[:] = toollib.delete_folder(self.mine, name)
        self.empty_folders = [f for f in self.empty_folders if f != name and not f.startswith(name + toollib.SEP)]
        self.tools = self.mine
        self.persist()
        self.fill()
        return True

    def context_menu(self, exec_menu: bool = True):
        """Clic droit sur l'arbre : toutes les commandes de la bibliothèque."""
        from PySide6.QtGui import QCursor
        from PySide6.QtWidgets import QMenu
        m = QMenu(self)
        for k in ('new', 'newdir', '-', 'ren', 'dup', 'move', 'up', 'down', 'merge', 'del', '-', 'machines', 'aliases',
                  '-', 'add', 'keep', '-', 'draw', 'cat'):
            if k == '-':
                m.addSeparator()
            elif self.acts[k].isEnabled():
                m.addAction(self.acts[k])
        if exec_menu:
            m.exec(QCursor.pos())
            m.deleteLater()
        return m

    def toggle_full_screen(self) -> bool:
        from .tool_filters import toggle_full_screen
        return toggle_full_screen(self)

    def done(self, r) -> None:                                  # noqa: D401 — API Qt
        from .tool_filters import remember_large
        remember_large(self, self.settings, 'outils/fenetre_agrandie', full=True)
        super().done(r)

    def program_aliases(self, exec_dialog: bool = True):
        """Les outils retenus pour les programmes lus (tool_picker.ProgramAliasesDialog) ; rend la fenêtre."""
        from .tool_picker import ProgramAliasesDialog
        dlg = ProgramAliasesDialog(self)
        if exec_dialog:
            try:
                dlg.exec()
            finally:
                dlg.deleteLater()
        return dlg

    def tool_prefs(self, exec_dialog: bool = True):
        """Outils proposés pour chaque type d'opération (toolprefs_dialog)."""
        from .toolprefs_dialog import ToolPrefsDialog
        dlg = ToolPrefsDialog(self, self.settings, self.mine)
        if exec_dialog:
            if dlg.exec():
                self.fill()
        return dlg

    def select(self, tool) -> None:
        for it in self._items():
            if it.data(0, Qt.ItemDataRole.UserRole) == tool.id:
                self.tree.setCurrentItem(it)
                return

    def _select(self, *_a) -> None:
        t = self.selected()
        self.current = t
        if t is None:
            self._sync_drawing_buttons()                 # plus d'outil choisi : plus de dessin à ouvrir
            return
        self.w['name'].setText(t.name)
        self.w['kind'].setCurrentIndex(max(0, self.w['kind'].findData(t.kind)))
        self.w['number'].setValue(int(t.number))
        self.w['flutes'].setValue(int(t.flutes))
        for key, _l in self.NUM:
            self.w[key].setValue(float(getattr(t, key)))
        for key, _l in self.COTES:
            self.w['g_' + key].setValue(float(t.geometry.get(key) or 0))
        self.w['vendor'].setText(t.vendor)
        self.w['ref'].setText(t.ref)
        self.w['c_url'].setText(str(t.catalog.get('url', '')))
        self.w['c_prix'].setValue(float(t.catalog.get('prix') or 0))
        self.w['notes'].setPlainText(t.notes)
        self.preview.setPixmap(silhouette(t))
        self.preview.setToolTip(toollib.summary(t, self._mlabels()))
        self.drawings.setText('\n'.join(f'{k.upper()} : {v}' for k, v in t.drawings.items() if k in ('dxf', 'step')))
        self._sync_drawing_buttons()

    # --- dessins de l'outil ---------------------------------------------------------------------------
    def drawing_path(self, kind: str) -> str:
        """Le dessin (« dxf » ou « step ») de l'outil choisi, s'il existe sur le disque ; sinon ''."""
        t = self.selected()
        if t is None:
            return ''
        known = dict(getattr(t, 'drawings', None) or {})
        drawn = getattr(self, '_drawn', None)            # bibliothèque en lecture seule : les dessins tout juste faits
        if drawn and drawn[0] == t.id:
            known.update(drawn[1])
        p = str(known.get(kind) or '')
        return p if p and pathlib.Path(p).is_file() else ''

    def _sync_drawing_buttons(self) -> None:
        win = self.main_window()
        for (kind, _what), b in getattr(self, 'drawing_buttons', {}).items():
            b.setEnabled(win is not None and bool(self.drawing_path(kind)))

    def main_window(self):
        """La fenêtre de VectorDrive d'où « Mes outils » a été ouverte (None : ouverte seule)."""
        w = self.parent()
        while w is not None and not (hasattr(w, 'open_path') and hasattr(w, 'place_symbol_by_click')):
            w = w.parent()
        return w

    def use_drawing(self, kind: str, what: str) -> bool:
        """Le dessin DXF ou STEP de l'outil choisi : ouvert dans un nouvel onglet (« open ») ou posé à la souris sur
        le dessin en cours (« place » : le dessin suit le pointeur, un clic le pose). La fenêtre des outils se
        ferme pour laisser la place au dessin. Rend vrai si c'est parti."""
        path, win = self.drawing_path(kind), self.main_window()
        if not path or win is None:
            return False
        self.accept()
        if what == 'open':
            return bool(win.open_path(path))
        return bool(win.place_symbol_by_click(path))

    # --- édition -------------------------------------------------------------------------------------
    def apply(self) -> None:
        t = self.current
        if t is None or not self.editable():
            return
        t.name = self.w['name'].text().strip() or t.name
        t.kind = self.w['kind'].currentData()
        t.number = self.w['number'].value()
        t.flutes = self.w['flutes'].value()
        for key, _l in self.NUM:
            v = self.w[key].value()
            if key in model.FEED_KEYS and abs(float(getattr(t, key, 0.0) or 0.0) - v) > 5e-4:   # 3 décimales
                model.note_change(t, key, getattr(t, key, 0.0), v, tr('bibliothèque d’outils'))
            setattr(t, key, v)
        geo = dict(t.geometry)
        for key, _l in self.COTES:
            v = self.w['g_' + key].value()
            if v > 0:
                geo[key] = v
            else:
                geo.pop(key, None)
        t.geometry = geo
        t.vendor, t.ref = self.w['vendor'].text().strip(), self.w['ref'].text().strip()
        cat = dict(t.catalog, fournisseur=t.vendor, reference=t.ref)
        url, prix = self.w['c_url'].text().strip(), self.w['c_prix'].value()
        cat.update({'url': url} if url else {})
        cat.update({'prix': prix, 'devise': 'EUR'} if prix else {})
        t.catalog = cat
        t.notes = self.w['notes'].toPlainText()
        self.persist()
        self.fill()
        self.select(t)

    def new_tool(self) -> None:
        t = model.CamTool(name=tr('Nouvel outil'), number=max([x.number for x in self.tools] + [0]) + 1)
        if self.source_key() == MINE:
            toollib.set_folder([t], self.selected_folder() or toollib.NO_FOLDER)
        self.tools.append(t)
        self.persist()
        self.fill()
        self.select(t)

    def duplicate(self) -> None:
        t = self.selected()
        if t is None:
            return
        c = model.CamTool.from_dict(t.to_dict())
        c.id, c.name = model.new_id(), t.name + tr(' (copie)')
        self.tools.append(c)
        self.persist()
        self.fill()
        self.select(c)

    def delete(self, confirm: bool = True) -> int:
        """Supprime les outils choisis (Suppr) ; plusieurs : après confirmation."""
        rows = self.tree.selectedItems()
        if self.source_key() == MINE and rows and all(it.data(0, Qt.ItemDataRole.UserRole + 1) for it in rows) \
                and len(rows) == 1:
            name = self.selected_folder()
            n = sum(1 for t in self.mine if toollib.in_folder(t, name))
            return n if self.delete_folder(confirm) else 0
        tools = self.selected_tools()
        if not tools or not self.editable():
            return 0
        if confirm and len(tools) > 1 and QMessageBox.question(
                self, tr('Supprimer des outils'), tr('Supprimer les {0} outils choisis ?').format(len(tools))) \
                != QMessageBox.StandardButton.Yes:
            return 0
        ids = {id(t) for t in tools}
        self.tools[:] = [t for t in self.tools if id(t) not in ids]
        self.persist()
        self.fill()
        return len(tools)

    # --- échanges ----------------------------------------------------------------------------------------
    def import_file(self, path) -> int:
        try:
            tools, notes = toollib.import_file(path)
        except (OSError, ValueError) as ex:
            QMessageBox.warning(self, tr('Importer des outils'), str(ex))
            return 0
        folder = None
        if self.source_key() == MINE:                      # un import = un dossier distinct
            folder = toollib.unique_folder(pathlib.Path(path).stem, self.mine)
            dbt = pathlib.Path(path).suffix.lower() in ('.dbt', '.dbtsav')
            for t in tools:                                # les dossiers d'une base TypeEdit gardés dessous
                sub = str(t.catalog.get('dossier_typeedit') or '') if dbt else ''
                toollib.set_folder([t], toollib.join_folder(folder, sub) if sub else folder)
        for t in tools:
            t.id = model.new_id()
        self.tools.extend(tools)
        self.persist()
        hint = self.offer_machine(tools)
        self.fill()
        if folder:
            self.select_folder(folder)
        self.info.setText(tr('{0} outil(s) importé(s) de {1}').format(len(tools), pathlib.Path(path).name) + hint
                          + ('\n' + '\n'.join(notes[:8]) if notes else ''))
        return len(tools)

    def import_dialog(self) -> int:
        """Un ou plusieurs fichiers : vus d'abord (ToolImportDialog), puis
        la sélection importée, chacun dans son dossier."""
        paths, _ = QFileDialog.getOpenFileNames(self, tr('Importer des outils'), self._import_start(),
                                                tr(toollib.IMPORT_FILTER))
        if not paths:
            return 0
        self._remember_import(paths[0])
        if self.source_key() != MINE:                      # outils du document : import direct
            return sum(self.import_file(p) for p in paths)
        return self.import_preview(*toollib.import_files(paths))

    def import_preview(self, imported: dict, notes=(), errors=(), *, exec_dialog: bool = True):
        """Aperçu de l'import (doublons décochés, rangement choisi), puis la
        sélection versée dans Mes outils. Rend le nombre d'outils ajoutés
        (ou la fenêtre, sans l'ouvrir, si `exec_dialog` est faux)."""
        from .tool_import import ToolImportDialog
        if self.source_key() != MINE:
            self.source.setCurrentIndex(max(0, self.source.findData(MINE)))
        if not imported:
            self.info.setText(tr('Aucun outil trouvé') + ('\n' + '\n'.join(list(errors)[:8]) if errors else ''))
            return 0
        dlg = ToolImportDialog(self, imported, self.mine, notes, errors)
        if not exec_dialog:
            return dlg
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return 0
        return self.add_chosen(dlg.chosen())

    def add_chosen(self, chosen: dict) -> int:
        """Verse {dossier: [outils]} dans Mes outils (dossiers existants
        complétés : le rangement a été choisi dans l'aperçu)."""
        n = 0
        for folder, tools in chosen.items():
            for t in tools:
                t.id = model.new_id()
                toollib.set_folder([t], folder)
            self.mine.extend(tools)
            n += len(tools)
        self.tools = self.mine
        self.persist()
        hint = self.offer_machine([t for ts in chosen.values() for t in ts])
        self.fill()
        if chosen:
            self.select_folder(next(iter(chosen)))
        self.info.setText(tr('{0} outil(s) importé(s) dans Mes outils ({1})').format(n, self.path) + hint)
        return n

    def _import_start(self) -> str:
        s = getattr(self.parent(), 'settings', None)
        return str(s.value('dossier/import_outils', '') or '') if s is not None else ''

    def _remember_import(self, path) -> None:
        s = getattr(self.parent(), 'settings', None)
        if s is not None:
            p = pathlib.Path(path)
            s.setValue('dossier/import_outils', str(p if p.is_dir() else p.parent))

    def import_folder(self, root, *, replace: bool | None = None) -> int:
        """Import en lot (toollib.import_tree) dans Mes outils : un dossier par
        fichier, les sous-dossiers du disque gardés. Dossier déjà présent :
        remplacé ou doublé (`replace` ; None : demandé). Rend le nombre
        d'outils ajoutés."""
        if self.source_key() != MINE:
            self.source.setCurrentIndex(max(0, self.source.findData(MINE)))
        root = pathlib.Path(root)
        from .progress import Cancelled, run
        try:
            imported, notes, errors = run(self, tr('Import des outils de {0}').format(root.name),
                                          toollib.import_tree, root)
        except Cancelled:
            return 0
        if not imported:
            self.info.setText(tr('Aucun outil trouvé dans {0}').format(root) +
                              ('\n' + '\n'.join(errors[:8]) if errors else ''))
            return 0
        have = set(toollib.folders(self.mine))
        clash = [n for n in imported if n in have]
        if clash and replace is None:
            box = QMessageBox(QMessageBox.Icon.Question, tr('Importer un dossier'),
                              tr('{0} dossier(s) existent déjà dans Mes outils (dont « {1} »).').format(
                                  len(clash), clash[0]), parent=self)
            rep = box.addButton(tr('Remplacer'), QMessageBox.ButtonRole.AcceptRole)
            box.addButton(tr('Ajouter à côté'), QMessageBox.ButtonRole.ActionRole)
            box.addButton(QMessageBox.StandardButton.Cancel)
            box.exec()
            if box.clickedButton() is None or box.buttonRole(box.clickedButton()) == QMessageBox.ButtonRole.RejectRole:
                return 0
            replace = box.clickedButton() is rep
        before = {id(t) for t in self.mine}
        n, names = toollib.add_folders(self.mine, imported, replace=bool(replace))
        self.tools = self.mine
        self.persist()
        hint = self.offer_machine([t for t in self.mine if id(t) not in before])
        self.fill()
        if names:
            self.select_folder(names[0])
        lines = [tr('{0} outil(s) importé(s) dans {1} dossier(s) de Mes outils ({2})').format(
            n, len(names), self.path)]
        if errors:
            lines.append(tr('Non lus : {0}').format(len(errors)))
            lines += errors[:6]
        lines += notes[:6]
        self.info.setText('\n'.join(lines) + hint)
        return n

    def import_folder_dialog(self) -> int:
        d = QFileDialog.getExistingDirectory(self, tr('Dossier d\'outils à importer (sous-dossiers compris)'),
                                             self._import_start())
        if not d:
            return 0
        self._remember_import(d)
        from .progress import Cancelled, run
        try:
            imported, notes, errors = run(self, tr('Import des outils de {0}').format(pathlib.Path(d).name),
                                          toollib.import_tree, pathlib.Path(d))
        except Cancelled:
            return 0
        return self.import_preview(imported, notes, errors)

    def export_file(self, path) -> list:
        notes = toollib.export_file(self.tools, path)
        self.info.setText(tr('{0} outil(s) exportés : {1}').format(len(self.tools), pathlib.Path(path).name)
                          + (('\n' + tr('Non repris par TypeEdit :') + '\n' + '\n'.join(notes[:10])) if notes else ''))
        return notes

    def export_dialog(self) -> None:
        path, flt = QFileDialog.getSaveFileName(self, tr('Exporter les outils'), 'tools.json', tr(toollib.EXPORT_FILTER))
        if path:
            if 'NeoDrive' in flt and not path.lower().endswith('.neodrive.json'):
                path = str(pathlib.Path(path).with_suffix('')) + '.neodrive.json'
            self.export_file(path)

    def draw(self) -> dict | None:
        t = self.selected()
        if t is None:
            return None
        from ..cam import tooldraw
        folder = self.path.parent / 'fiches_outils' / ((t.ref or t.name).replace('/', '_').strip() or t.id)
        out = tooldraw.write_drawings(t, folder)
        if self.editable():
            t.drawings = out
            self.persist()
        self.drawings.setText(f'DXF : {out["dxf"]}\nSTEP : {out["step"]}')
        self._drawn = (t.id, out)
        self._sync_drawing_buttons()
        return out

    def open_catalogs(self, exec_dialog: bool = True):
        t = self.selected()
        dlg = CatalogsDialog(self, t.ref if t else '', t.vendor if t else '')
        if exec_dialog:
            dlg.exec()
        return dlg

    def open_sheet(self) -> None:
        t = self.selected()
        if t is None:
            return
        url = t.catalog.get('url') or ''
        if not url:
            v = catalogs.vendor(t.vendor)
            url = catalogs.search_url(v, t.ref) if v else catalogs.WEB_SEARCH.format(
                q=f'{t.vendor} {t.ref or t.name}'.strip().replace(' ', '+'))
        QDesktopServices.openUrl(QUrl(url))

    def add_to_document(self) -> int:
        t = self.selected()
        if t is None or self.panel is None:
            return 0
        s = self.panel.setup()
        c = model.CamTool.from_dict(t.to_dict())
        c.id = model.new_id()
        if any(x.number == c.number for x in s.tools):
            c.number = max(x.number for x in s.tools) + 1
        s.tools.append(c)
        self.panel.save(s)
        self.info.setText(tr('« {0} » ajouté aux outils du document (T{1})').format(c.name, c.number))
        return 1

    def copy_to_mine(self) -> int:
        t = self.selected()
        if t is None:
            return 0
        c = model.CamTool.from_dict(t.to_dict())
        c.id = model.new_id()
        toollib.set_folder([c], self.source.currentText())       # dossier : la bibliothèque d'origine
        self.mine.append(c)
        toollib.save(self.mine, self.path)
        self.info.setText(tr('« {0} » copié dans mes outils').format(c.name))
        return 1

