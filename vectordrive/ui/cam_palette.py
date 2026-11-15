"""Colonne de gauche de la FAO, comme la fenêtre « Créer un parcours » de
TypeEdit : le bouton **Outils** (Mes outils, le tools.json en dossiers),
« usiner la sélection ou les couleurs », et les parcours disponibles, rangés
par familles ; sous chacun, ses modèles (les vôtres, ceux des plugins, ceux
importés de TypeEdit). Un clic sur un parcours ouvre son formulaire pour
les contours sélectionnés, prérempli avec ses dernières valeurs ; un clic
sur un modèle l'ouvre déjà rempli."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QHBoxLayout, QLabel, QMenu, QMessageBox, QPushButton,
                               QRadioButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from ..i18n import tr

#: familles de parcours (clés de cam_panel.PRESETS), dans l'ordre de TypeEdit
FAMILIES = [
    ('Usinage 2D', ('trace', 'percage', 'percage_fraise', 'taraudage', 'chanfrein')),
    ('Usinage 2D-3D', ('decoupe', 'gravure', 'surfacage', 'reste')),
    ('Usinage 3D', ('gravure3d', 'prismatique', 'decoupe3d', 'relief', 'gamme_relief', 'finition', 'finition25d', 'gamme')),
    ('Laser', ('laser', 'laser_decoupe', 'laser_gravure')),
    ('Machine', ('instruction', 'texte_machine')),
]
ROLE_KIND = Qt.ItemDataRole.UserRole           # clé du parcours
ROLE_TPL = Qt.ItemDataRole.UserRole + 1        # nom du modèle
ROLE_ORIGIN = Qt.ItemDataRole.UserRole + 2     # origine du modèle (utilisateur, plugin)
ROLE_FOLDER = Qt.ItemDataRole.UserRole + 3     # chemin du dossier (« TypeEdit 13 — Meca3/Atelier »)
ROLE_ROOT = Qt.ItemDataRole.UserRole + 4       # groupe « Modèles (dossiers) » : y déposer, c'est sortir du dossier


class TemplateTree(QTreeWidget):
    """Arbre de la palette : vos modèles et leurs dossiers se rangent par
    glisser-déposer (sur un dossier, ou sur « Modèles (dossiers) » pour les
    sortir de tout dossier) ; `dropped(objets, dossier)` fait le rangement."""

    def __init__(self, dropped):
        super().__init__()
        self.dropped = dropped
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    @staticmethod
    def target_folder(item) -> str | None:
        """Dossier où mène un dépôt sur `item` ('' : hors dossier), None : refusé."""
        from ..cam import templates as TPL
        if item is None:
            return None
        if item.data(0, ROLE_ROOT):
            return ''
        if item.data(0, ROLE_FOLDER) and item.data(0, ROLE_ORIGIN) == 'utilisateur':
            return str(item.data(0, ROLE_FOLDER))
        if item.data(0, ROLE_TPL) and item.data(0, ROLE_ORIGIN) == 'utilisateur':
            tpl = TPL.user_templates().get(str(item.data(0, ROLE_TPL))) or {}
            return '/'.join(TPL.folder_parts(tpl.get('dossier')))
        return None

    def moving(self) -> list:
        """[('modele', nom) | ('dossier', chemin)] des lignes choisies qui se déplacent."""
        out = []
        for it in self.selectedItems():
            if it.data(0, ROLE_ORIGIN) != 'utilisateur':
                continue
            if it.data(0, ROLE_TPL):
                out.append(('modele', str(it.data(0, ROLE_TPL))))
            elif it.data(0, ROLE_FOLDER):
                out.append(('dossier', str(it.data(0, ROLE_FOLDER))))
        return out

    def dragMoveEvent(self, ev) -> None:
        super().dragMoveEvent(ev)
        if self.target_folder(self.itemAt(ev.position().toPoint())) is None or not self.moving():
            ev.ignore()

    def dropEvent(self, ev) -> None:
        folder = self.target_folder(self.itemAt(ev.position().toPoint()))
        objs = self.moving()
        ev.setDropAction(Qt.DropAction.IgnoreAction)     # l'arbre est refait d'après les fichiers
        ev.accept()
        if folder is not None and objs:
            self.dropped(objs, folder)


def memo_suffix(tpl: dict) -> str:
    """« — T248 Ø3 Z1 L13 » : l'outil du modèle (le premier, et combien d'autres)."""
    memo = [str(m) for m in tpl.get('outils_memo') or []]
    if not memo:
        tools = tpl.get('tools') or []
        memo = [f"T{t.get('number', 0)} {t.get('name', '')}" for t in tools if isinstance(t, dict)]
    if not memo:
        return ''
    first = memo[0].split(' — ')[0]
    return f'  — {first}' + (f' (+{len(memo) - 1})' if len(memo) > 1 else '')


def preset_of(tpl: dict, kinds: dict) -> str | None:
    """Parcours d'un modèle d'une seule opération (champ `preset`, sinon
    d'après sa stratégie, `kinds` : stratégie → parcours) ; None pour un
    modèle à plusieurs opérations (réglage complet)."""
    if tpl.get('preset'):
        return str(tpl['preset'])
    ops = tpl.get('operations') or []
    if len(ops) != 1 or not isinstance(ops[0], dict):
        return None
    return kinds.get(ops[0].get('kind'))



def color_enabled(settings) -> bool:
    """L'usinage par couleur est-il proposé (case cochée par l'utilisateur) ?"""
    return settings.value('fao/usinage_couleur', 'false') in (True, 'true')


def machining_mode(settings) -> str:
    """'selection' (par défaut, et toujours tant que l'usinage par couleur
    n'est pas proposé) ou 'couleur'."""
    if not color_enabled(settings):
        return 'selection'
    v = str(settings.value('fao/mode_usinage', 'selection') or 'selection')
    return v if v in ('selection', 'couleur') else 'selection'


class CamPalette(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        row = QHBoxLayout()
        self.tools_btn = QPushButton(tr('🧰 Outils'))
        self.tools_btn.setToolTip(tr('Mes outils : le fichier tools.json, en dossiers (importer, ranger, catalogues)'))
        self.tools_btn.clicked.connect(lambda: self.win.cam_panel.tool_library())
        row.addWidget(self.tools_btn, 1)
        self.import_btn = QPushButton(tr('Modèles TypeEdit…'))
        self.import_btn.setToolTip(tr('Importer les modèles de parcours du TypeEdit de ce poste (paramètres de '
                                      'parcours et fichiers .ttpl), pour les retrouver ici'))
        self.import_btn.clicked.connect(lambda: self.import_typeedit())
        row.addWidget(self.import_btn)
        lay.addLayout(row)
        from PySide6.QtWidgets import QCheckBox
        self.color_on = QCheckBox(tr('Usinage par couleur'))
        self.color_on.setToolTip(tr('Montrer le choix « Usiner : la sélection / les couleurs » (usinage par couleur '
                                    'de TypeEdit) ; décoché, un nouveau parcours usine la sélection'))
        self.color_on.setChecked(color_enabled(self.win.settings))
        lay.addWidget(self.color_on)
        self.mode_row = QWidget()
        mode = QHBoxLayout(self.mode_row)
        mode.setContentsMargins(0, 0, 0, 0)
        mode.addWidget(QLabel(tr('Usiner')))
        self.by_selection = QRadioButton(tr('la sélection'))
        self.by_selection.setToolTip(tr('Un nouveau parcours usine les contours sélectionnés'))
        self.by_color = QRadioButton(tr('les couleurs'))
        self.by_color.setToolTip(tr('Un nouveau parcours usine toutes les formes des couleurs de la sélection '
                                    '(ou du calque actif), comme l\'usinage par couleur de TypeEdit'))
        group = QButtonGroup(self)
        group.addButton(self.by_selection)
        group.addButton(self.by_color)
        mode.addWidget(self.by_selection)
        mode.addWidget(self.by_color)
        mode.addStretch(1)
        lay.addWidget(self.mode_row)
        (self.by_selection if self.mode() == 'selection' else self.by_color).setChecked(True)
        self.by_selection.toggled.connect(lambda on: self.set_mode('selection' if on else 'couleur'))
        self.mode_row.setVisible(self.color_on.isChecked())
        self.color_on.toggled.connect(self.set_color_enabled)
        self.tree = TemplateTree(self.move_objects)
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.itemClicked.connect(self._clicked)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu)
        for keys, slot in ((QKeySequence.StandardKey.Delete, self.delete_selected), ('F2', self.rename_selected)):
            sc = QShortcut(QKeySequence(keys), self.tree)
            sc.setContext(Qt.ShortcutContext.WidgetShortcut)
            sc.activated.connect(slot)
        lay.addWidget(self.tree, 1)
        hint = QLabel(tr('Un clic sur un parcours ouvre son formulaire pour les contours sélectionnés, prérempli '
                         'avec ses dernières valeurs ; un clic sur un modèle l\'ouvre déjà rempli. Vos modèles se '
                         'rangent par glisser-déposer ; Suppr, F2 et clic droit pour le reste.'))
        hint.setWordWrap(True)
        hint.setStyleSheet('color: #868e96;')
        lay.addWidget(hint)
        #: clé d'action (cam_new_…) → ligne du parcours
        self.items: dict[str, QTreeWidgetItem] = {}
        self.refresh()

    # --- mode d'usinage ------------------------------------------------------------------------
    def mode(self) -> str:
        return machining_mode(self.win.settings)

    def set_mode(self, mode: str) -> None:
        if mode == 'couleur' and not self.color_on.isChecked():
            self.color_on.setChecked(True)               # choisir les couleurs, c'est activer l'usinage par couleur
        self.win.settings.setValue('fao/mode_usinage', mode)
        (self.by_selection if mode == 'selection' else self.by_color).setChecked(True)

    def set_color_enabled(self, on: bool) -> None:
        """Case « Usinage par couleur » : le choix du mode paraît (retenu) ;
        décochée, on revient à l'usinage de la sélection."""
        self.win.settings.setValue('fao/usinage_couleur', bool(on))
        self.mode_row.setVisible(bool(on))
        (self.by_selection if self.mode() == 'selection' else self.by_color).setChecked(True)

    # --- arbre ---------------------------------------------------------------------------------
    def refresh(self) -> None:
        from ..cam import templates as TPL
        from .cam_panel import presets
        ps = presets()
        machine = getattr(self.win, '_machine_kind', '')    # 'fraiseuse', 'laser', ou '' : machine inconnue, tout

        def fits(key: str) -> bool:
            """Le parcours va-t-il à la machine du dessin ? Un parcours laser pour un laser, les autres pour une
            fraiseuse ; l'instruction machine pour toutes."""
            if not machine or key == 'instruction' or key not in ps:
                return True
            return (ps[key][3] == 'laser') == (machine == 'laser')
        kinds = {}
        for key, (_label, kind, _kw, _tk) in ps.items():
            kinds.setdefault(kind, key)
        by_preset: dict[str, list] = {}
        in_folders: list = []                            # modèles rangés en dossiers : leur arborescence est gardée
        for name, (origin, tpl) in sorted(TPL.all_templates().items(), key=lambda kv: kv[0].lower()):
            key = preset_of(tpl, kinds)
            if key in ps and fits(key):
                if str(tpl.get('dossier') or ''):
                    in_folders.append((name, origin, tpl, key))
                else:
                    by_preset.setdefault(key, []).append((name, origin, tpl))
        expanded = {self.tree.topLevelItem(i).text(0) for i in range(self.tree.topLevelItemCount())
                    if self.tree.topLevelItem(i).isExpanded()}
        from PySide6.QtWidgets import QTreeWidgetItemIterator
        self._open_folders = set()                       # dossiers ouverts : rouverts après un rangement
        it = QTreeWidgetItemIterator(self.tree)
        while it.value() is not None:
            if it.value().data(0, ROLE_FOLDER) and it.value().isExpanded():
                self._open_folders.add(str(it.value().data(0, ROLE_FOLDER)))
            it += 1
        self.tree.clear()
        self.items = {}
        favs = [k[len('cam_new_'):] for k in self.win.cam_panel.favorites() if k.startswith('cam_new_')]
        favs = [k for k in favs if fits(k)]
        families = ([(tr('Favoris (palette TypeEdit)'), tuple(favs))] if favs else []) + \
            [(tr(t), tuple(k for k in keys if fits(k))) for t, keys in FAMILIES]
        if machine:                                      # machine connue : les familles vidées ne sont pas montrées
            families = [f for f in families if any(k in ps for k in f[1])]
        placed = {k for _t, keys in FAMILIES for k in keys}
        others = tuple(k for k in ps if k not in placed and fits(k))
        if others:
            families.append((tr('Plugins'), others))
        for title, keys in families:
            g = QTreeWidgetItem([title])
            f = g.font(0)
            f.setBold(True)
            g.setFont(0, f)
            g.setFlags(g.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.tree.addTopLevelItem(g)
            for key in keys:
                if key not in ps:
                    continue
                act = self.win.A.get(f'cam_new_{key}')
                it = QTreeWidgetItem([tr(ps[key][0])])
                if act is not None:
                    it.setIcon(0, act.icon())
                it.setToolTip(0, self.tip(key))
                it.setData(0, ROLE_KIND, key)
                g.addChild(it)
                self.items.setdefault(f'cam_new_{key}', it)
                folders: dict[str, QTreeWidgetItem] = {}
                for name, origin, tpl in by_preset.get(key, []):
                    parent = it
                    folder = str(tpl.get('dossier') or '')
                    if folder:
                        parent = folders.get(folder)
                        if parent is None:
                            parent = folders[folder] = QTreeWidgetItem(['📁 ' + folder])
                            parent.setFlags(parent.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                            it.addChild(parent)
                    label = name.split(' / ', 1)[1] if folder and name.startswith(folder + ' / ') else name
                    t = QTreeWidgetItem(['📄 ' + label + memo_suffix(tpl)])
                    t.setData(0, ROLE_KIND, key)
                    t.setData(0, ROLE_TPL, name)
                    t.setData(0, ROLE_ORIGIN, origin)
                    t.setToolTip(0, str(tpl.get('description') or name))
                    parent.addChild(t)
            g.setExpanded(not expanded or title in expanded)
        if in_folders or TPL.empty_folders():
            self._folder_tree(in_folders, ps, expanded)

    def _folder_tree(self, entries: list, ps: dict, expanded: set) -> None:
        """Modèles enregistrés en dossiers (les vôtres, ceux importés de
        TypeEdit) : un groupe « Modèles » qui garde leur arborescence au lieu
        de les répartir par type de parcours — comme la fenêtre de TypeEdit."""
        title = tr('Modèles (dossiers)')
        g = QTreeWidgetItem([title])
        f = g.font(0)
        f.setBold(True)
        g.setFont(0, f)
        g.setFlags(g.flags() & ~Qt.ItemFlag.ItemIsSelectable & ~Qt.ItemFlag.ItemIsDragEnabled)
        g.setData(0, ROLE_ROOT, True)
        self.tree.insertTopLevelItem(0, g)
        folders: dict[tuple, QTreeWidgetItem] = {}
        open_folders = getattr(self, '_open_folders', set())

        def node_of(parts: tuple, origin: str):
            parent = g
            for depth in range(1, len(parts) + 1):
                node = folders.get(parts[:depth])
                if node is None:
                    node = folders[parts[:depth]] = QTreeWidgetItem(['📁 ' + parts[depth - 1]])
                    node.setData(0, ROLE_FOLDER, '/'.join(parts[:depth]))
                    if origin == 'utilisateur':
                        node.setData(0, ROLE_ORIGIN, origin)
                    else:                                # dossier d'un plugin : ni choisi, ni déplacé
                        node.setFlags(node.flags() & ~Qt.ItemFlag.ItemIsSelectable & ~Qt.ItemFlag.ItemIsDragEnabled)
                    parent.addChild(node)
                    node.setExpanded('/'.join(parts[:depth]) in open_folders)
                elif origin == 'utilisateur' and not node.data(0, ROLE_ORIGIN):
                    node.setData(0, ROLE_ORIGIN, origin)
                    node.setFlags(node.flags() | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled)
                parent = node
            return parent
        # ordre de TypeEdit pour les modèles importés (dossiers compris), puis par nom
        entries = sorted(entries, key=lambda e: (e[2].get('ordre') is None, e[2].get('ordre') or 0, e[0].lower()))
        for name, origin, tpl, key in entries:
            folder = str(tpl.get('dossier') or '')
            parts = tuple(p.strip() for p in folder.replace(' / ', '/').split('/') if p.strip())
            parent = node_of(parts, origin)
            label = name[len(folder) + 3:] if name.startswith(folder + ' / ') else name
            t = QTreeWidgetItem(['📄 ' + label + memo_suffix(tpl)])
            t.setData(0, ROLE_KIND, key)
            t.setData(0, ROLE_TPL, name)
            t.setData(0, ROLE_ORIGIN, origin)
            act = self.win.A.get(f'cam_new_{key}')
            if act is not None:
                t.setIcon(0, act.icon())
            t.setToolTip(0, str(tpl.get('description') or name) + '\n' + tr('Parcours : {0}').format(tr(ps[key][0])))
            if origin != 'utilisateur':
                t.setFlags(t.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
            parent.addChild(t)
        from ..cam import templates as TPL
        for folder in TPL.empty_folders():               # dossiers créés, encore vides
            node_of(tuple(TPL.folder_parts(folder)), 'utilisateur')
        g.setExpanded(not expanded or title in expanded)

    def tip(self, key: str) -> str:
        """Bulle d'un parcours : celle de sa commande, et s'il part de ses dernières valeurs."""
        act = self.win.A.get(f'cam_new_{key}')
        tip = act.toolTip() if act is not None else ''
        if self.win.cam_panel.last_values(key) is not None:
            tip += ('\n' if tip else '') + tr('Prérempli avec les dernières valeurs utilisées')
        return tip

    def update_tips(self) -> None:
        """Bulles des parcours à jour (dernières valeurs retenues ou oubliées)."""
        from PySide6.QtWidgets import QTreeWidgetItemIterator
        it = QTreeWidgetItemIterator(self.tree)
        while it.value() is not None:
            item = it.value()
            if item.data(0, ROLE_KIND) and not item.data(0, ROLE_TPL):
                item.setToolTip(0, self.tip(str(item.data(0, ROLE_KIND))))
            it += 1

    def save_last(self, key: str, name: str | None = None) -> str | None:
        """Dernières valeurs du parcours `key` en modèle, rangé sous ce parcours."""
        from ..cam import templates as TPL
        last = self.win.cam_panel.last_values(key)
        if last is None:
            return None
        if name is None:
            from PySide6.QtWidgets import QInputDialog
            from .cam_panel import presets
            name, ok = QInputDialog.getText(self, tr('Modèle d\'usinage'), tr('Nom du modèle'),
                                            text=tr(presets()[key][0]))
            if not ok:
                return None
            if name.strip() in TPL.user_templates() and QMessageBox.question(
                    self, tr('Modèles d\'usinage'), tr('Remplacer le modèle « {0} » ?').format(name.strip())) \
                    != QMessageBox.StandardButton.Yes:
                return None
        name = (name or '').strip()
        if not name:
            return None
        TPL.save_user({**last, 'name': name, 'preset': key})
        self.refresh()
        return name

    def forget_last(self, key: str) -> bool:
        return self.win.cam_panel.forget_last(key)

    def _clicked(self, item: QTreeWidgetItem, _col: int = 0) -> None:
        key = item.data(0, ROLE_KIND)
        if not key:
            item.setExpanded(not item.isExpanded())
            return
        self.win.cam_panel.new_operation(key, template=item.data(0, ROLE_TPL) or None)

    def _menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        name = item.data(0, ROLE_TPL) if item is not None else None
        m = QMenu(self)
        if item is not None and item.data(0, ROLE_KIND):
            m.addAction(tr('Nouveau parcours…'), lambda: self._clicked(item))
            key = str(item.data(0, ROLE_KIND))
            if not name and self.win.cam_panel.last_values(key) is not None:
                m.addAction(tr('Enregistrer les dernières valeurs comme modèle…'), lambda: self.save_last(key))
                m.addAction(tr('Revenir aux réglages d\'origine'), lambda: self.forget_last(key))
        if item is not None and item not in self.tree.selectedItems() and item.flags() & Qt.ItemFlag.ItemIsSelectable:
            self.tree.setCurrentItem(item)               # clic droit hors sélection : cette ligne seule
        if name and item.data(0, ROLE_ORIGIN) == 'utilisateur':
            m.addAction(tr('Renommer le modèle…'), lambda: self.rename_template(name)).setShortcut(QKeySequence('F2'))
            m.addAction(tr('Ranger dans un dossier…'), lambda: self.move_template(name))
        folder = item.data(0, ROLE_FOLDER) if item is not None else None
        if folder and item.data(0, ROLE_ORIGIN) == 'utilisateur':
            m.addAction(tr('Nouveau sous-dossier…'), lambda: self.new_folder(folder))
            m.addAction(tr('Renommer ou déplacer le dossier…'), lambda: self.rename_folder(folder))
        objs = self.tree.moving()
        if objs:
            m.addAction(tr('Ranger la sélection dans un dossier…'), lambda: self.move_objects(objs))
            m.addAction(tr('Supprimer la sélection…'), self.delete_selected).setShortcut(QKeySequence.StandardKey.Delete)
        m.addSeparator()
        m.addAction(tr('Nouveau dossier…'), lambda: self.new_folder(''))
        m.addAction(tr('Importer les modèles de TypeEdit…'), lambda: self.import_typeedit())
        m.addAction(tr('Actualiser'), self.refresh)
        m.popup(self.tree.viewport().mapToGlobal(pos))

    # --- modèles -------------------------------------------------------------------------------
    def delete_template(self, name: str, confirm: bool = True) -> bool:
        from ..cam import templates as TPL
        if confirm and QMessageBox.question(self, tr('Modèles d\'usinage'),
                                            tr('Supprimer le modèle « {0} » ?').format(name)) \
                != QMessageBox.StandardButton.Yes:
            return False
        ok = TPL.delete_user(name)
        self.refresh()
        return ok

    def new_folder(self, parent: str = '', name: str | None = None) -> str | None:
        """Nouveau dossier de modèles (dans `parent`), gardé même vide."""
        from PySide6.QtWidgets import QInputDialog
        from ..cam import templates as TPL
        if name is None:
            name, ok = QInputDialog.getText(self, tr('Nouveau dossier'), tr('Nom du dossier :'))
            if not ok:
                return None
        name = str(name).replace('/', '-').strip()
        if not name:
            return None
        folder = TPL.add_folder('/'.join(TPL.folder_parts(parent) + [name]))
        self._open_folders = getattr(self, '_open_folders', set()) | {parent}
        self.refresh()
        return folder

    def rename_template(self, name: str, label: str | None = None) -> str | None:
        from PySide6.QtWidgets import QInputDialog
        from ..cam import templates as TPL
        tpl = TPL.user_templates().get(name)
        if tpl is None:
            return None
        if label is None:
            label, ok = QInputDialog.getText(self, tr('Renommer le modèle'), tr('Nom :'), text=TPL.label_of(tpl))
            if not ok:
                return None
        new = TPL.rename_template(name, label)
        if new is None and label:
            QMessageBox.information(self, tr('Modèles d\'usinage'), tr('Un modèle porte déjà ce nom dans ce dossier.'))
        self.refresh()
        return new

    def rename_selected(self) -> None:
        """F2 : renommer le modèle ou le dossier choisi."""
        objs = self.tree.moving()
        if len(objs) != 1:
            return
        what, key = objs[0]
        (self.rename_template if what == 'modele' else self.rename_folder)(key)

    def move_objects(self, objs: list, folder: str | None = None) -> int:
        """Range modèles et dossiers (glissés, ou choisis) dans `folder`
        ('' : hors dossier ; demandé si None) ; rend le nombre de modèles déplacés."""
        from ..cam import templates as TPL
        if folder is None:
            folder = self._ask_folder(tr('Ranger dans un dossier'), '')
            if folder is None:
                return 0
        folder = '/'.join(TPL.folder_parts(folder))
        dirs = [k for w, k in objs if w == 'dossier']
        n = 0
        for d in dirs:
            if TPL._in(folder, d):
                continue                                 # un dossier ne va pas dans lui-même
            if folder:
                TPL.add_folder(folder)
            n += TPL.rename_folder(d, '/'.join(TPL.folder_parts(folder) + [TPL.folder_parts(d)[-1]]))
        for w, k in objs:
            if w == 'modele' and not any(TPL._in(TPL.user_templates().get(k, {}).get('dossier'), d) for d in dirs):
                n += TPL.set_folder(k, folder) is not None
        self._open_folders = getattr(self, '_open_folders', set()) | {folder}
        self.refresh()
        return n

    def delete_selected(self, confirm: bool = True) -> int:
        """Suppr : supprime les modèles et dossiers choisis (après confirmation)."""
        from ..cam import templates as TPL
        objs = self.tree.moving()
        if not objs:
            return 0
        dirs = [k for w, k in objs if w == 'dossier']
        names = [k for w, k in objs if w == 'modele']
        inside = sum(1 for t in TPL.user_templates().values() if any(TPL._in(t.get('dossier'), d) for d in dirs))
        msg = tr('Supprimer {0} modèle(s) et {1} dossier(s) ({2} modèle(s) dedans) ?').format(len(names), len(dirs),
                                                                                           inside)
        if confirm and QMessageBox.question(self, tr('Modèles d\'usinage'), msg) != QMessageBox.StandardButton.Yes:
            return 0
        n = sum(TPL.delete_folder(d) for d in dirs)
        n += sum(TPL.delete_user(k) for k in names)
        self.refresh()
        return n

    def _ask_folder(self, title: str, current: str) -> str | None:
        from PySide6.QtWidgets import QInputDialog
        from ..cam import templates as TPL
        names = TPL.user_folders()
        items = [current] + [n for n in names if n != current]
        v, ok = QInputDialog.getItem(self, title, tr('Dossier (« Atelier/Laiton » pour un sous-dossier ; '
                                                     'vide : hors dossier)'), items, 0, True)
        return v.strip() if ok else None

    def move_template(self, name: str, folder: str | None = None) -> str | None:
        """Range un modèle dans un dossier (demandé si `folder` est None)."""
        from ..cam import templates as TPL
        tpl = TPL.user_templates().get(name) or {}
        if folder is None:
            folder = self._ask_folder(tr('Ranger le modèle'), str(tpl.get('dossier') or ''))
            if folder is None:
                return None
        new = TPL.set_folder(name, folder)
        self.refresh()
        return new

    def rename_folder(self, old: str, new: str | None = None) -> int:
        from ..cam import templates as TPL
        if new is None:
            new = self._ask_folder(tr('Renommer ou déplacer le dossier'), old)
            if new is None or new == old:
                return 0
        n = TPL.rename_folder(old, new)
        self.refresh()
        return n

    def delete_folder(self, folder: str, confirm: bool = True) -> int:
        from ..cam import templates as TPL
        n = sum(1 for t in TPL.user_templates().values() if TPL._in(t.get('dossier'), folder))
        if confirm and QMessageBox.question(self, tr('Modèles d\'usinage'),
                                            tr('Supprimer le dossier « {0} » et ses {1} modèle(s) ?').format(
                                                folder, n)) != QMessageBox.StandardButton.Yes:
            return 0
        n = TPL.delete_folder(folder)
        self.refresh()
        return n

    def import_typeedit(self, files=None, *, quiet: bool = False) -> int:
        """Modèles de parcours du TypeEdit du poste (CONFIG/PathParam_*.TPP)
        et ses .ttpl (PRESET) en modèles d'usinage ; rend leur nombre.
        Chaque fichier va dans son propre dossier (« TypeEdit 13 — Meca3 »),
        ses dossiers dessous : rien n'est mêlé aux autres modèles. Les outils
        des fiches (numéro, nom, référence) sont gardés avec chaque modèle."""
        from ..cam import templates as TPL
        from ..cam import tpp
        files_given = files
        files = tpp.installed() if files is None else list(files)
        n, skipped = 0, 0
        for f in files:
            try:
                presets = tpp.read(f)
            except OSError:
                continue
            if presets:
                TPL.delete_imported(tpp.source_name(f))  # import refait : l'arborescence de TypeEdit, à jour
            for i, p in enumerate(presets):
                tpl = tpp.to_template(p, tpp.source_name(f))
                if tpl is None:
                    skipped += 1
                    continue
                tpl['ordre'] = i                         # l'ordre de la fenêtre de TypeEdit
                TPL.save_user(tpl)
                n += 1
        try:
            if files_given is None:
                n += self.win.cam_panel.import_installed_ttpl()
        except Exception:                                # pas de TypeEdit, ou .ttpl illisible
            pass
        self.refresh()
        msg = tr('{0} modèle(s) de parcours importé(s) de TypeEdit').format(n)
        if skipped:
            msg += tr(' ({0} sans équivalent, TypeArt…)').format(skipped)
        if not files and not n:
            msg = tr('Aucun paramètre de parcours TypeEdit sur ce poste')
        if quiet:
            self.win.statusBar().showMessage(msg, 8000)
        else:
            QMessageBox.information(self, tr('Modèles TypeEdit'), msg)
        return n
