"""Colonne de gauche de la FAO, comme la fenêtre « Créer un parcours » de
TypeEdit : le bouton **Outils** (Mes outils, le tools.json en dossiers), puis
trois dossiers — « Parcours type » (les parcours de base, par familles ;
sous chacun, les modèles des plugins), « Mes modèles » (vos modèles et leurs
dossiers), « TypeEdit » (la palette et les modèles importés de TypeEdit) —,
tous renommables, et tout en bas « usiner la sélection ou les couleurs ». Un
clic sur un parcours ouvre son formulaire pour les contours sélectionnés,
prérempli avec ses dernières valeurs ; un clic sur un modèle l'ouvre déjà
rempli."""
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
ROLE_ROOT = Qt.ItemDataRole.UserRole + 4       # dossier « Mes modèles » : y déposer, c'est sortir du dossier
ROLE_GROUP = Qt.ItemDataRole.UserRole + 5      # dossier de la palette (« type », « fam:Usinage 2D », « user », « te »…)
ROLE_DEFAULT = Qt.ItemDataRole.UserRole + 6    # son nom d'origine
ROLE_PROCESS = Qt.ItemDataRole.UserRole + 7    # un process de « Mes process » (plusieurs opérations)
ROLE_PDIR = Qt.ItemDataRole.UserRole + 8       # un dossier de « Mes process » (à part de ceux de « Mes modèles »)
ROLE_FAMILY = Qt.ItemDataRole.UserRole + 9     # une famille des parcours unifiés (clé de cam_panel.UNIFIED)
#: noms donnés aux dossiers de la palette (JSON {dossier: nom})
NAMES = 'fao/palette/noms'


class TemplateTree(QTreeWidget):
    """Arbre de la palette : vos modèles et leurs dossiers se rangent par
    glisser-déposer (sur un dossier, ou sur « Mes modèles » pour les sortir
    de tout dossier) ; `dropped(objets, dossier)` fait le rangement."""

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
            elif it.data(0, ROLE_FOLDER):                # un dossier de « Mes process » : à part
                out.append(('pdossier' if it.data(0, ROLE_PDIR) else 'dossier', str(it.data(0, ROLE_FOLDER))))
        return out

    @staticmethod
    def zone(item):
        """Le dossier de la palette (« user », « process »…) où se trouve la ligne `item`."""
        while item is not None and item.parent() is not None:
            item = item.parent()
        return item.data(0, ROLE_GROUP) if item is not None else None

    def same_zone(self, target) -> bool:
        """Un dépôt reste dans son dossier de la palette : un modèle ne va pas dans « Mes process », ni un process dans
        « Mes modèles » (un modèle repris de TypeEdit va toujours dans « Mes modèles »)."""
        z = self.zone(target) == 'process'
        return all((self.zone(it) == 'process') == z for it in self.selectedItems()
                   if it.data(0, ROLE_ORIGIN) == 'utilisateur')

    def dragMoveEvent(self, ev) -> None:
        super().dragMoveEvent(ev)
        target = self.itemAt(ev.position().toPoint())
        if self.target_folder(target) is None or not self.moving() or not self.same_zone(target):
            ev.ignore()

    def dropEvent(self, ev) -> None:
        target = self.itemAt(ev.position().toPoint())
        folder = self.target_folder(target)
        objs = self.moving()
        ev.setDropAction(Qt.DropAction.IgnoreAction)     # l'arbre est refait d'après les fichiers
        ev.accept()
        if folder is not None and objs and self.same_zone(target):
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


def is_process(tpl: dict, key) -> bool:
    """Un modèle de l'utilisateur va dans « Mes process » (demande du 15/11, 23 h 30) : marqué process, ou de plusieurs
    opérations (le réglage d'une gravure : `key`, son parcours, est None). Pas ceux importés de TypeEdit."""
    return bool(tpl.get('process') or key is None) and not from_typeedit(tpl)


def process_suffix(tpl: dict) -> str:
    """« — 4 opération(s) » : la taille du process."""
    return '  — ' + tr('{0} opération(s)').format(len(tpl.get('operations') or []))


def process_tip(tpl: dict, name: str) -> str:
    """Bulle d'un process : sa description, ses opérations, ce que fait le clic."""
    from ..cam import model
    lines = [str(tpl.get('description') or name)]
    for d in tpl.get('operations') or []:
        if isinstance(d, dict):
            kind = str(d.get('kind') or '')
            lines.append('• ' + (str(d.get('name') or '').strip() or tr(model.op_kinds().get(kind, kind))))
    lines.append(tr('Clic : l’appliquer au dessin ; puis ⟳ sur chaque opération pour ses formes'))
    return '\n'.join(lines)


def top_folder(folder) -> str:
    """Le premier dossier du chemin (« TypeEdit 13 — Meca3 » pour « TypeEdit 13 — Meca3/Atelier »)."""
    parts = [p.strip() for p in str(folder or '').replace(' / ', '/').split('/') if p.strip()]
    return parts[0] if parts else ''


def from_typeedit(tpl: dict) -> bool:
    """Modèle importé de TypeEdit (paramètres de parcours, ou fichier .ttpl) et resté dans son dossier d'import
    (« TypeEdit 13 — Meca3… », « TypeEdit — modèles .ttpl », même renommé : `templates.import_root`) : ce dossier va
    dans « TypeEdit » de la palette, avec tout ce qui y est rangé ; un modèle importé rangé ailleurs par l'utilisateur
    va dans « Mes modèles »."""
    from ..cam import templates as TPL
    return TPL.import_root(tpl) is not None


def te_palette() -> bool:
    """La palette de TypeEdit (TypeEdit_User) est-elle sur ce poste ? Sinon, les favoris viennent d'un plugin."""
    from .shortcuts import user_palette
    return any(k.startswith('cam_') for k in user_palette())



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
        from PySide6.QtWidgets import QToolButton
        from .fold_label import FoldLabel
        hint = self.hint = FoldLabel(hint.text())        # une longue phrase : repliable en une ligne (demande du 15/11)
        hint.set_always(True)
        hint.setStyleSheet('color: #868e96;')
        b = self.hint_fold = QToolButton()               # ▾ replier, ▸ déplier (retenu)
        b.setAutoRaise(True)
        b.setFixedSize(18, 18)
        b.setStyleSheet('QToolButton { padding: 0px; }')
        b.clicked.connect(lambda _=False: self.set_hint_folded(not self.hint.folded()))
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(2)
        row.addWidget(b, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(hint, 1)
        lay.addLayout(row)
        self.set_hint_folded(self.win.settings.value(self.HINT_FOLDED_KEY, 'false') in (True, 'true'), remember=False)
        lay.addWidget(self.color_on)                     # tout en bas (demande du 15/11)
        lay.addWidget(self.mode_row)
        #: clé d'action (cam_new_…) → ligne du parcours
        self.items: dict[str, QTreeWidgetItem] = {}
        self.refresh()

    # --- mode d'usinage ------------------------------------------------------------------------
    #: le texte d'aide du bas de la palette replié en une ligne (retenu)
    HINT_FOLDED_KEY = 'fao/palette/aide_repliee'

    def set_hint_folded(self, on: bool, remember: bool = True) -> None:
        """Le texte d'aide du bas de la palette replié en une ligne (entier en bulle), ou déplié ; retenu."""
        self.hint.set_folded(on)
        if remember:
            self.win.settings.setValue(self.HINT_FOLDED_KEY, bool(on))
        self.hint_fold.setText('▸' if on else '▾')
        self.hint_fold.setToolTip(tr('Déplier ce texte') if on else tr('Replier ce texte en une ligne'))

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
        self._kinds = kinds                              # (`_is_proc`)
        by_preset: dict[str, list] = {}                  # parcours → modèles des plugins, rangés sous lui
        mine: list = []                                  # vos modèles (importés compris) : « Mes modèles », « TypeEdit »
        procs: list = []                                 # vos process : « Mes process »
        te_roots: set = set()                            # dossiers d'import de TypeEdit : l'import a été fait
        for name, (origin, tpl) in sorted(TPL.all_templates().items(), key=lambda kv: kv[0].lower()):
            if origin == 'utilisateur' and from_typeedit(tpl):
                te_roots.add(top_folder(tpl.get('dossier')))
            key = preset_of(tpl, kinds)
            if origin == 'utilisateur' and is_process(tpl, key):
                keys = [kinds.get(d.get('kind')) for d in tpl.get('operations') or [] if isinstance(d, dict)]
                keys = [k for k in keys if k in ps and k not in ('instruction', 'texte_machine')]
                if not keys or any(fits(k) for k in keys):  # pas un process laser pour une fraiseuse (une
                    # instruction machine va à toutes : pas comptée)
                    procs.append((name, origin, tpl, None))
                continue
            if key in ps and fits(key):
                if origin == 'utilisateur':
                    mine.append((name, origin, tpl, key))
                else:
                    by_preset.setdefault(key, []).append((name, origin, tpl))
        from .tree_memory import items                   # (jamais de QTreeWidgetItemIterator : voir `items`)
        was = {}                                         # dossiers de la palette ouverts ou fermés : gardés
        self._open_folders = set()                       # dossiers ouverts : rouverts après un rangement
        for node in items(self.tree):
            if node.data(0, ROLE_GROUP):
                was[str(node.data(0, ROLE_GROUP))] = node.isExpanded()
            if node.data(0, ROLE_FAMILY):
                was['uni:' + str(node.data(0, ROLE_FAMILY))] = node.isExpanded()
            if node.data(0, ROLE_FOLDER) and node.isExpanded():
                self._open_folders.add(str(node.data(0, ROLE_FOLDER)))
        self._was_open = was
        self.tree.clear()
        self.items = {}
        favs = [k[len('cam_new_'):] for k in self.win.cam_panel.favorites() if k.startswith('cam_new_')]
        favs = tuple(k for k in favs if fits(k) and k in ps)
        families = [(t, tuple(k for k in keys if fits(k))) for t, keys in FAMILIES]
        if machine:                                      # machine connue : les familles vidées ne sont pas montrées
            families = [f for f in families if any(k in ps for k in f[1])]
        placed = {k for _t, keys in FAMILIES for k in keys}
        others = tuple(k for k in ps if k not in placed and fits(k))
        if others:
            families.append(('Plugins', others))
        base = self._group('type', tr('Parcours type'))   # les parcours de base réunis (demande du 15/11)
        self.tree.addTopLevelItem(base)
        self._by_preset = by_preset
        # la palette de TypeEdit : dans « TypeEdit » une fois l'import fait, sinon (celle d'un plugin aussi) en tête ici
        te_favs = favs if te_roots and te_palette() else ()
        groups = [('favoris', 'Favoris (palette TypeEdit)', favs)] if favs and not te_favs else []
        unified_rows = []                                # parcours unifiés : [(famille, libellé, parcours offerts)]
        if self.unified():
            from .cam_panel import UNIFIED
            taken = {k for _l, _w, members in UNIFIED.values() for k, _t in members}
            for fam, (title, _list, members) in UNIFIED.items():
                keys = tuple(k for k, _t in members if k in ps and fits(k))
                if keys:
                    unified_rows.append((fam, title, keys))
            later = [('fam:Plugins', 'Plugins', tuple(k for k in ps if k not in taken and fits(k)))]
            later = [g for g in later if g[2]]           # les parcours des plugins : à part, après les familles
        else:
            groups += [('fam:' + title, title, keys) for title, keys in families]
            later = []

        def add_groups(some) -> None:
            for gkey, title, keys in some:
                g = self._group(gkey, tr(title))
                base.addChild(g)
                for key in keys:
                    if key in ps:
                        g.addChild(self._preset_row(key, ps))
                g.setExpanded(was.get(gkey, True))
        add_groups(groups)
        for fam, title, keys in unified_rows:
            base.addChild(self._family_row(fam, title, keys, ps, was))
        add_groups(later)
        base.setExpanded(was.get('type', True))
        self._folder_tree(mine, ps, te_favs, te_roots, procs)

    def unified(self) -> bool:
        """La palette montre les parcours unifiés (9 familles) plutôt que les 22 parcours par dossiers."""
        from .cam_panel import unified
        return unified(self.win.settings)

    def set_unified(self, on: bool) -> None:
        from .cam_panel import UNIFIED_KEY
        self.win.settings.setValue(UNIFIED_KEY, bool(on))
        self.refresh()

    def _family_row(self, fam: str, title: str, keys: tuple, ps: dict, was: dict) -> QTreeWidgetItem:
        """Parcours unifiés : la ligne d'une famille — un clic ouvre son formulaire, où une liste fait choisir le
        parcours ; ses parcours sont dessous, repliés (un clic sur l'un d'eux ouvre le sien). Une famille d'un seul
        parcours : la ligne de ce parcours, au nom de la famille."""
        if len(keys) == 1:
            it = self._preset_row(keys[0], ps)
            it.setText(0, tr(title))
            return it
        g = QTreeWidgetItem([tr(title)])
        act = self.win.A.get(f'cam_new_{keys[0]}')
        if act is not None:
            g.setIcon(0, act.icon())
        g.setData(0, ROLE_FAMILY, fam)
        g.setFlags(g.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
        g.setToolTip(0, ', '.join(tr(ps[k][0]) for k in keys))
        for k in keys:
            g.addChild(self._preset_row(k, ps))
        g.setExpanded(bool(was.get('uni:' + fam, False)))
        return g

    def _preset_row(self, key: str, ps: dict) -> QTreeWidgetItem:
        """La ligne d'un parcours et, dessous, les modèles des plugins pour ce parcours (dans leurs dossiers)."""
        it = self._preset_item(key, ps)
        folders: dict[str, QTreeWidgetItem] = {}
        for name, origin, tpl in getattr(self, '_by_preset', {}).get(key, []):
            parent = it
            folder = str(tpl.get('dossier') or '')
            if folder:
                parent = folders.get(folder)
                if parent is None:
                    parent = folders[folder] = QTreeWidgetItem(['📁 ' + folder])
                    parent.setFlags(parent.flags() & ~Qt.ItemFlag.ItemIsSelectable & ~Qt.ItemFlag.ItemIsDragEnabled)
                    it.addChild(parent)
            label = name.split(' / ', 1)[1] if folder and name.startswith(folder + ' / ') else name
            t = QTreeWidgetItem(['📄 ' + label + memo_suffix(tpl)])
            t.setData(0, ROLE_KIND, key)
            t.setData(0, ROLE_TPL, name)
            t.setData(0, ROLE_ORIGIN, origin)
            t.setToolTip(0, str(tpl.get('description') or name))
            t.setFlags(t.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
            parent.addChild(t)
        return it

    def _group(self, key: str, default: str) -> QTreeWidgetItem:
        """Un dossier de la palette, en gras : « Parcours type » et ses familles, « Mes modèles », « TypeEdit »,
        « Favoris (palette TypeEdit) ». Renommable (F2, clic droit) : son nom vient des réglages (`NAMES`), sinon
        `default`. Choisi pour F2, jamais déplacé."""
        g = QTreeWidgetItem([self.group_name(key, default)])
        f = g.font(0)
        f.setBold(True)
        g.setFont(0, f)
        g.setFlags(g.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
        g.setData(0, ROLE_GROUP, key)
        g.setData(0, ROLE_DEFAULT, default)
        return g

    def _preset_item(self, key: str, ps: dict) -> QTreeWidgetItem:
        """La ligne d'un parcours (clic : son formulaire)."""
        act = self.win.A.get(f'cam_new_{key}')
        it = QTreeWidgetItem([tr(ps[key][0])])
        if act is not None:
            it.setIcon(0, act.icon())
        it.setToolTip(0, self.tip(key))
        it.setData(0, ROLE_KIND, key)
        self.items.setdefault(f'cam_new_{key}', it)
        return it

    def _names(self) -> dict:
        import json
        try:
            d = json.loads(str(self.win.settings.value(NAMES, '') or '{}'))
        except ValueError:
            d = {}
        return d if isinstance(d, dict) else {}

    def group_name(self, key: str, default: str) -> str:
        """Le nom montré du dossier `key` de la palette : celui donné par l'utilisateur, sinon `default`."""
        return str(self._names().get(key) or default)

    def rename_group(self, key: str, label: str | None = None) -> str | None:
        """Renomme le dossier `key` de la palette (« type », « fam:Usinage 2D », « user », « te », « favoris ») ;
        vide : son nom d'origine. Sans `label`, le demande. Rend le nom montré (None : abandon, dossier absent)."""
        import json
        from PySide6.QtWidgets import QInputDialog
        from .tree_memory import items
        node = next((n for n in items(self.tree) if n.data(0, ROLE_GROUP) == key), None)
        if node is None:
            return None
        default = str(node.data(0, ROLE_DEFAULT) or '')
        if label is None:
            label, ok = QInputDialog.getText(self, tr('Renommer le dossier'), tr('Nom (vide : nom d’origine) :'),
                                             text=node.text(0))
            if not ok:
                return None
        label = str(label or '').strip()
        names = self._names()
        if label and label != default:
            names[key] = label
        else:
            names.pop(key, None)
        self.win.settings.setValue(NAMES, json.dumps(names, ensure_ascii=False))
        self.refresh()
        return self.group_name(key, default)

    def _folder_tree(self, entries: list, ps: dict, favs: tuple = (), te_roots: set = frozenset(),
                     procs: list = ()) -> None:
        """Vos modèles dans « Mes modèles », en dossiers ou hors dossier (y déposer un modèle le sort de son dossier) ;
        ceux importés de TypeEdit (dossiers d'import `te_roots`), avec la palette de TypeEdit (`favs`), dans
        « TypeEdit », seulement si l'import a été fait. Leur arborescence est gardée, comme la fenêtre de TypeEdit."""
        from ..cam import templates as TPL
        was = getattr(self, '_was_open', {})
        user = self._group('user', tr('Mes modèles'))
        user.setData(0, ROLE_ROOT, True)
        self.tree.addTopLevelItem(user)
        te_entries = [e for e in entries if top_folder(e[2].get('dossier')) in te_roots]
        own = [e for e in entries if top_folder(e[2].get('dossier')) not in te_roots]
        empty = [tuple(TPL.folder_parts(f)) for f in TPL.empty_folders()]   # dossiers créés, encore vides
        te = None
        if te_roots:
            te = self._group('te', tr('TypeEdit'))
            self.tree.addTopLevelItem(te)
            if favs:
                fav = self._group('favoris', tr('Favoris (palette TypeEdit)'))
                te.addChild(fav)
                for key in favs:
                    fav.addChild(self._preset_row(key, ps))
                fav.setExpanded(was.get('favoris', True))
        self._fill(user, own, ps, [p for p in empty if not (te is not None and p and p[0] in te_roots)])
        user.setExpanded(was.get('user', True))
        proc = self._group('process', tr('Mes process'))   # vos process, juste après vos modèles (demande du 15/11)
        proc.setData(0, ROLE_ROOT, True)
        tip = tr('Vos process : les opérations d’une gravure et leurs outils. Clic : les ajouter au dessin, puis ⟳ sur chaque opération pour lui donner ses formes')
        proc.setToolTip(0, tip)
        self.tree.insertTopLevelItem(self.tree.indexOfTopLevelItem(user) + 1, proc)
        self._fill(proc, list(procs), ps)
        if not procs:                                    # vide : comment le remplir
            from PySide6.QtGui import QBrush, QColor
            hint = QTreeWidgetItem([tr('(clic droit : enregistrer les opérations du dessin)')])
            hint.setFlags(Qt.ItemFlag.ItemIsEnabled)
            hint.setForeground(0, QBrush(QColor('#868e96')))
            proc.addChild(hint)
        proc.setExpanded(was.get('process', True))
        if te is not None:
            self._fill(te, te_entries, ps, [p for p in empty if p and p[0] in te_roots])
            if te.childCount():
                te.setExpanded(was.get('te', True))
            else:                                        # rien pour cette machine (importés pour une autre) : caché
                self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(te))

    def _fill(self, g: QTreeWidgetItem, entries: list, ps: dict, empty: list = ()) -> None:
        """Sous `g` : les modèles `entries` rangés dans leurs dossiers, puis les dossiers vides `empty`, puis les
        modèles hors dossier."""
        folders: dict[tuple, QTreeWidgetItem] = {}
        open_folders = getattr(self, '_open_folders', set())

        def node_of(parts: tuple, origin: str):
            parent = g
            for depth in range(1, len(parts) + 1):
                node = folders.get(parts[:depth])
                if node is None:
                    node = folders[parts[:depth]] = QTreeWidgetItem(['📁 ' + parts[depth - 1]])
                    node.setData(0, ROLE_FOLDER, '/'.join(parts[:depth]))
                    if g.data(0, ROLE_GROUP) == 'process':   # un dossier de « Mes process »
                        node.setData(0, ROLE_PDIR, True)
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
        # ordre de TypeEdit pour les modèles importés (dossiers compris), puis par nom ; hors dossier : à la fin
        def parts_of(tpl):
            folder = str(tpl.get('dossier') or '')
            return tuple(p.strip() for p in folder.replace(' / ', '/').split('/') if p.strip())
        entries = sorted(entries, key=lambda e: (not parts_of(e[2]), e[2].get('ordre') is None,
                                                 e[2].get('ordre') or 0, e[0].lower()))
        loose_from = next((i for i, e in enumerate(entries) if not parts_of(e[2])), len(entries))
        for i, (name, origin, tpl, key) in enumerate(entries):
            if i == loose_from:
                for parts in empty:
                    node_of(parts, 'utilisateur')
            folder = str(tpl.get('dossier') or '')
            parent = node_of(parts_of(tpl), origin)
            label = name[len(folder) + 3:] if name.startswith(folder + ' / ') else name
            if key is None:                              # un process (« Mes process ») : ses opérations
                t = QTreeWidgetItem(['📋 ' + label + process_suffix(tpl)])
                t.setData(0, ROLE_PROCESS, True)
                t.setToolTip(0, process_tip(tpl, name))
            else:
                t = QTreeWidgetItem(['📄 ' + label + memo_suffix(tpl)])
                t.setData(0, ROLE_KIND, key)
                act = self.win.A.get(f'cam_new_{key}')
                if act is not None:
                    t.setIcon(0, act.icon())
                t.setToolTip(0, str(tpl.get('description') or name) + '\n' + tr('Parcours : {0}').format(
                    tr(ps[key][0])))
            t.setData(0, ROLE_TPL, name)
            t.setData(0, ROLE_ORIGIN, origin)
            if origin != 'utilisateur':
                t.setFlags(t.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
            parent.addChild(t)
        if loose_from == len(entries):                   # aucun modèle hors dossier : les dossiers vides à la fin
            for parts in empty:
                node_of(parts, 'utilisateur')

    def tip(self, key: str) -> str:
        """Bulle d'un parcours : celle de sa commande, et s'il part de ses dernières valeurs."""
        act = self.win.A.get(f'cam_new_{key}')
        tip = act.toolTip() if act is not None else ''
        if self.win.cam_panel.last_values(key) is not None:
            tip += ('\n' if tip else '') + tr('Prérempli avec les dernières valeurs utilisées')
        return tip

    def update_tips(self) -> None:
        """Bulles des parcours à jour (dernières valeurs retenues ou oubliées)."""
        from .tree_memory import items
        for item in items(self.tree):
            if item.data(0, ROLE_KIND) and not item.data(0, ROLE_TPL):
                item.setToolTip(0, self.tip(str(item.data(0, ROLE_KIND))))

    def save_last(self, key: str, name: str | None = None) -> str | None:
        """Dernières valeurs du parcours `key` en modèle, dans « Mes modèles » (hors dossier)."""
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
        if item.data(0, ROLE_PROCESS):                   # un process : ajouté au dessin
            self.apply_process(str(item.data(0, ROLE_TPL)))
            return
        if item.data(0, ROLE_FAMILY):                    # parcours unifiés : le formulaire de la famille
            self.win.cam_panel.new_family(str(item.data(0, ROLE_FAMILY)))
            return
        key = item.data(0, ROLE_KIND)
        if not key:
            item.setExpanded(not item.isExpanded())
            return
        self.win.cam_panel.new_operation(key, template=item.data(0, ROLE_TPL) or None)

    def _menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        name = item.data(0, ROLE_TPL) if item is not None else None
        m = QMenu(self)
        if item is not None and item.data(0, ROLE_PROCESS):
            m.addAction(tr('Appliquer au dessin…'), lambda: self.apply_process(str(name)))
            if item.data(0, ROLE_ORIGIN) == 'utilisateur':
                m.addAction(tr('Remplacer par les opérations du dessin'), lambda: self.update_process(str(name)))
        if item is not None and item.data(0, ROLE_FAMILY):
            m.addAction(tr('Nouveau parcours…'), lambda: self._clicked(item))
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
        group = item.data(0, ROLE_GROUP) if item is not None else None
        if group:
            m.addAction(tr('Renommer le dossier…'), lambda: self.rename_group(str(group))).setShortcut(
                QKeySequence('F2'))
            if str(group) in self._names():
                m.addAction(tr('Nom d’origine'), lambda: self.rename_group(str(group), ''))
        folder = item.data(0, ROLE_FOLDER) if item is not None else None
        if folder and item.data(0, ROLE_ORIGIN) == 'utilisateur' and item.data(0, ROLE_PDIR):
            m.addAction(tr('Renommer ou déplacer le dossier…'), lambda: self.rename_process_folder(folder))
        elif folder and item.data(0, ROLE_ORIGIN) == 'utilisateur':
            m.addAction(tr('Nouveau sous-dossier…'), lambda: self.new_folder(folder))
            m.addAction(tr('Renommer ou déplacer le dossier…'), lambda: self.rename_folder(folder))
        objs = self.tree.moving()
        if objs:
            m.addAction(tr('Ranger la sélection dans un dossier…'), lambda: self.move_objects(objs))
            m.addAction(tr('Supprimer la sélection…'), self.delete_selected).setShortcut(QKeySequence.StandardKey.Delete)
        m.addSeparator()
        m.addAction(tr('Enregistrer les opérations du dessin comme process…'), lambda: self.save_process())
        m.addAction(tr('Nouveau dossier…'), lambda: self.new_folder(''))
        m.addAction(tr('Importer les modèles de TypeEdit…'), lambda: self.import_typeedit())
        m.addAction(tr('Actualiser'), self.refresh)
        uni = m.addAction(tr('Parcours unifiés (9 familles)'))
        uni.setCheckable(True)
        uni.setChecked(self.unified())
        uni.toggled.connect(self.set_unified)
        m.popup(self.tree.viewport().mapToGlobal(pos))

    # --- process (demande du 15/11, 23 h 30) ------------------------------------------------------------------------
    def save_process(self, name: str | None = None, description: str = '') -> str | None:
        """Les opérations du dessin et leurs outils en process, dans « Mes process » : à ajouter à une autre gravure
        d'un clic, puis ⟳ sur chaque opération pour ses formes. Sans `name`, le demande. Rend son nom (None : rien)."""
        from PySide6.QtWidgets import QInputDialog
        from ..cam import templates as TPL
        s = self.win.cam_panel.setup()
        if not s.operations:
            if name is None:
                QMessageBox.information(self, tr('Mes process'), tr('Aucune opération à enregistrer.'))
            return None
        asked = name is None
        if asked:
            name, ok = QInputDialog.getText(self, tr('Enregistrer un process'), tr('Nom du process'))
            if not ok:
                return None
        name = str(name or '').replace('/', '-').strip()
        if not name:
            return None
        users = TPL.user_templates()
        # le même nom qu'un process rangé dans un dossier (« Atelier / Plaque » pour « Plaque ») : c'est lui
        key = name if name in users else next((n for n, t in users.items() if self._is_proc(t)
                                               and TPL.label_of(t) == name), name)
        old = users.get(key)
        if old is not None and not self._is_proc(old):   # un modèle d'une opération, un import : pas écrasé
            if asked:
                QMessageBox.information(self, tr('Mes process'),
                                        tr('Un modèle (pas un process) porte déjà ce nom : choisissez-en un autre.'))
            return None
        if old is not None and asked and QMessageBox.question(
                self, tr('Mes process'), tr('Remplacer le process « {0} » ?').format(name)) \
                != QMessageBox.StandardButton.Yes:
            return None
        tpl = TPL.from_setup(s, key, description or str((old or {}).get('description') or ''))
        tpl['process'] = True
        for k in ('dossier', 'ordre'):                   # remplacé : il reste à sa place
            if (old or {}).get(k) is not None:
                tpl[k] = old[k]
        TPL.save_user(tpl)
        self.refresh()
        return key

    def _is_proc(self, tpl: dict) -> bool:
        """Le modèle `tpl` de l'utilisateur est-il un process (« Mes process ») ?"""
        return is_process(tpl, preset_of(tpl, getattr(self, '_kinds', {})))

    def _rows(self):
        """Toutes les lignes de la palette."""
        from .tree_memory import items
        return items(self.tree)

    def _not_proc(self, tpl: dict) -> bool:
        """Un modèle de « Mes modèles » (pas un process) : les dossiers des deux sont à part."""
        return not self._is_proc(tpl)

    def _move_process_folder(self, old: str, new: str) -> int:
        """Les process du dossier `old` (et de ses sous-dossiers) rangés dans `new` : un dossier du même nom dans « Mes
        modèles » n'est pas touché (les dossiers des deux sont à part). Rend le nombre de process déplacés."""
        from ..cam import templates as TPL
        old_p, new_p = TPL.folder_parts(old), TPL.folder_parts(new)
        n = 0
        for name, tpl in list(TPL.user_templates().items()):
            parts = TPL.folder_parts(tpl.get('dossier'))
            if self._is_proc(tpl) and old_p and parts[:len(old_p)] == old_p:
                n += TPL.set_folder(name, '/'.join(new_p + parts[len(old_p):])) is not None
        return n

    def rename_process_folder(self, old: str, new: str | None = None) -> int:
        """Renommer ou déplacer un dossier de « Mes process » (ses process seulement)."""
        if new is None:
            new = self._ask_folder(tr('Renommer ou déplacer le dossier'), old)
            if new is None or new == old:
                return 0
        n = self._move_process_folder(old, new)
        self.refresh()
        return n

    def update_process(self, name: str, confirm: bool = True) -> bool:
        """Le process `name` refait avec les opérations du dessin (son nom, son dossier, sa description gardés)."""
        from ..cam import templates as TPL
        old = TPL.user_templates().get(name)
        s = self.win.cam_panel.setup()
        if old is None or not s.operations:
            if confirm and old is not None:
                QMessageBox.information(self, tr('Mes process'), tr('Aucune opération à enregistrer.'))
            return False
        if confirm and QMessageBox.question(
                self, tr('Mes process'), tr('Remplacer le process « {0} » par les {1} opération(s) du dessin ?').format(
                    name, len(s.operations))) != QMessageBox.StandardButton.Yes:
            return False
        tpl = TPL.from_setup(s, name, str(old.get('description') or ''))
        tpl['process'] = True
        for k in ('dossier', 'ordre'):
            if old.get(k) is not None:
                tpl[k] = old[k]
        TPL.save_user(tpl)
        self.refresh()
        return True

    def apply_process(self, name: str, exec_dialog: bool = True, **kw) -> list:
        """Le process `name` ajouté aux opérations du dessin : la fenêtre du modèle (quoi usiner — d'office les formes
        sélectionnées —, remplacer les opérations ou les compléter). Rend le compte rendu."""
        return self.win.cam_panel.apply_template(name, exec_dialog=exec_dialog, prefer='objets', **kw)

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
        """F2 : renommer le modèle ou le dossier choisi (un dossier de la palette aussi)."""
        objs = self.tree.moving()
        if not objs:
            cur = self.tree.currentItem()
            if cur is not None and cur.isSelected() and cur.data(0, ROLE_GROUP):
                self.rename_group(str(cur.data(0, ROLE_GROUP)))
            return
        if len(objs) != 1:
            return
        what, key = objs[0]
        {'modele': self.rename_template, 'dossier': self.rename_folder}.get(what, self.rename_process_folder)(key)

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
            n += TPL.rename_folder(d, '/'.join(TPL.folder_parts(folder) + [TPL.folder_parts(d)[-1]]),
                                   which=self._not_proc)  # les process d'un dossier du même nom : à part
        for w, k in objs:
            if w == 'modele' and not any(TPL._in(TPL.user_templates().get(k, {}).get('dossier'), d)
                                         for d in dirs + [k2 for w2, k2 in objs if w2 == 'pdossier']):
                n += TPL.set_folder(k, folder) is not None
        for w, d in objs:                                # dossiers de « Mes process » : leurs process seulement
            if w == 'pdossier' and not TPL._in(folder, d):
                n += self._move_process_folder(d, '/'.join(TPL.folder_parts(folder) + [TPL.folder_parts(d)[-1]]))
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
        inside = sum(1 for t in TPL.user_templates().values()  # (les process d'un dossier du même nom : à part)
                     if not self._is_proc(t) and any(TPL._in(t.get('dossier'), d) for d in dirs))
        pdirs = [k for w, k in objs if w == 'pdossier']  # dossiers de « Mes process » : leurs process seulement
        shown = {str(it.data(0, ROLE_TPL)) for it in self._rows() if it.data(0, ROLE_PROCESS)}
        procs = [k for k, t in TPL.user_templates().items()   # ceux montrés (pas ceux d'une autre machine)
                 if k in shown and self._is_proc(t) and any(TPL._in(t.get('dossier'), d) for d in pdirs)]
        msg = tr('Supprimer {0} modèle(s) et {1} dossier(s) ({2} modèle(s) dedans) ?').format(
            len(names), len(dirs) + len(pdirs), inside + len(procs))
        if confirm and QMessageBox.question(self, tr('Modèles d\'usinage'), msg) != QMessageBox.StandardButton.Yes:
            return 0
        n = sum(TPL.delete_folder(d, which=self._not_proc) for d in dirs)
        n += sum(TPL.delete_user(k) for k in names)
        n += sum(TPL.delete_user(k) for k in procs if k not in names)
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
        n = TPL.rename_folder(old, new, which=self._not_proc)   # (ses process : `rename_process_folder`)
        self.refresh()
        return n

    def delete_folder(self, folder: str, confirm: bool = True) -> int:
        from ..cam import templates as TPL
        n = sum(1 for t in TPL.user_templates().values() if TPL._in(t.get('dossier'), folder) and self._not_proc(t))
        if confirm and QMessageBox.question(self, tr('Modèles d\'usinage'),
                                            tr('Supprimer le dossier « {0} » et ses {1} modèle(s) ?').format(
                                                folder, n)) != QMessageBox.StandardButton.Yes:
            return 0
        n = TPL.delete_folder(folder, which=self._not_proc)
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
            src = tpp.source_name(f)
            root = TPL.root_of_source(src)               # son dossier d'import, peut-être renommé depuis
            if presets:
                TPL.delete_imported(root)                # import refait : l'arborescence de TypeEdit, à jour
            for i, p in enumerate(presets):
                tpl = tpp.to_template(p, root)
                if tpl is None:
                    skipped += 1
                    continue
                tpl['ordre'] = i                         # l'ordre de la fenêtre de TypeEdit
                tpl[TPL.SOURCE_KEY], tpl[TPL.ROOT_KEY] = src, root
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
