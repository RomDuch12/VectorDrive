"""Filtres des outils (gestionnaire et « Choisir un outil »), tri des listes
d'outils par colonne et plein écran de ces fenêtres.

FilterBar : recherche, nature, plage de Ø, fabricant et « Adaptés à » (les
outils proposés pour une stratégie, dans l'ordre réglé : cam.toolprefs).
"""
from __future__ import annotations

import itertools

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit, QToolButton,
                               QWidget)

#: silhouettes d'outils en icône, par cotes (elles ne changent pas d'un affichage à l'autre)
_ICONS: dict = {}
#: réglage : n'afficher que les outils de la machine du réglage FAO
MACHINE_ONLY = 'outils/machine_seule'


def tool_icon(t, w: int = 22, h: int = 40):
    """Silhouette de l'outil en petite icône (cache par cotes)."""
    import json
    from PySide6.QtGui import QIcon
    key = (t.kind, t.diameter, t.tip, t.angle, t.cut_length, t.stickout, t.holder_diameter,
           json.dumps(t.geometry, sort_keys=True, default=str), json.dumps(t.profile, default=str), w, h)
    ic = _ICONS.get(key)
    if ic is None:
        from .toollib_dialog import silhouette
        ic = _ICONS[key] = QIcon(silhouette(t, w, h))
        if len(_ICONS) > 2000:
            _ICONS.clear()
    return ic


def machine_labels(machines_dir: str = '') -> dict:
    """Clé de post-processeur → libellé (pour les fiches d'outils)."""
    try:
        from ..cam import post
        return dict(post.posts(machines_dir))
    except Exception:                                  # post-processeurs illisibles : les clés
        return {}

from ..cam import model, toollib, toolprefs
from ..i18n import tr


class FilterBar(QWidget):
    changed = Signal()

    def __init__(self, settings=None, parent=None, *, op_kind: str = ''):
        super().__init__(parent)
        self.settings = settings
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.text = QLineEdit()
        self.text.setPlaceholderText(tr('Chercher (nom, référence, fabricant, Ø, T, dossier)'))
        self.text.setClearButtonEnabled(True)
        lay.addWidget(self.text, 4)
        self.kind = QComboBox()
        self.kind.addItem(tr('Toutes natures'), '')
        for k, lab in model.TOOL_KINDS.items():
            self.kind.addItem(tr(lab).split(' (')[0], k)
        lay.addWidget(self.kind)
        lay.addWidget(QLabel('Ø'))
        self.dmin, self.dmax = QDoubleSpinBox(), QDoubleSpinBox()
        for sb, tip in ((self.dmin, tr('Ø minimal (0 : sans borne)')), (self.dmax, tr('Ø maximal (0 : sans borne)'))):
            sb.setRange(0, 1000)
            sb.setDecimals(2)
            sb.setSpecialValueText('—')
            sb.setToolTip(tip)
            sb.setMaximumWidth(80)
            lay.addWidget(sb)
        self.vendor = QComboBox()
        self.vendor.addItem(tr('Tous fabricants'), '')
        lay.addWidget(self.vendor)
        self.op = QComboBox()
        self.op.addItem(tr('Toutes opérations'), '')
        for k, lab in model.op_kinds().items():
            self.op.addItem(tr('Adaptés à : {0}').format(tr(lab).split(' (')[0]), k)
        self.op.setToolTip(tr('Les outils proposés pour cette stratégie, dans l\'ordre réglé '
                              '(Outils proposés par opération)'))
        lay.addWidget(self.op)
        self.machine_key = ''
        self.mach = QCheckBox()
        self.mach.setVisible(False)
        self.mach.setChecked(not settings or settings.value(MACHINE_ONLY, True) not in (False, 'false', '0', 0))
        self.mach.toggled.connect(self._machine_toggled)
        lay.addWidget(self.mach)
        self.reset_btn = QToolButton()
        self.reset_btn.setText('✕')
        self.reset_btn.setToolTip(tr('Effacer les filtres'))
        self.reset_btn.clicked.connect(self.reset)
        lay.addWidget(self.reset_btn)
        for c, n in ((self.kind, 160), (self.vendor, 150), (self.op, 210)):   # la recherche prend la place
            c.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            c.setMinimumContentsLength(6)
            c.setMaximumWidth(n)
        self.text.setMinimumWidth(160)
        if op_kind:
            self.op.setCurrentIndex(max(0, self.op.findData(op_kind)))
        self.text.textChanged.connect(self.changed)
        for w in (self.kind, self.vendor, self.op):
            w.currentIndexChanged.connect(self.changed)
        for sb in (self.dmin, self.dmax):
            sb.valueChanged.connect(self.changed)

    def set_machine(self, key: str, label: str = '', tools=()) -> None:
        """Machine du réglage FAO : la case « Outils de : … » (cochée : les
        outils réservés à d'autres machines cachés ; décochée : tous).
        Montrée quand un outil au moins est réservé à des machines."""
        self.machine_key = key or ''
        self.mach.setText(tr('Outils de : {0}').format(label or key) if key else '')
        self.mach.setToolTip(tr('Seulement les outils de cette machine (et ceux sans machine désignée) ; '
                                'décocher pour tous les voir'))
        self.mach.setVisible(bool(key) and any(getattr(t, 'machines', None) for t in tools))

    def _machine_toggled(self, on: bool) -> None:
        if self.settings is not None:
            self.settings.setValue(MACHINE_ONLY, bool(on))
        self.changed.emit()

    def set_tools(self, tools) -> None:
        """Fabricants proposés : ceux des outils montrés."""
        cur = self.vendor.currentData()
        self.vendor.blockSignals(True)
        self.vendor.clear()
        self.vendor.addItem(tr('Tous fabricants'), '')
        for v in toollib.vendors(list(tools)):
            self.vendor.addItem(v, v)
        self.vendor.setCurrentIndex(max(0, self.vendor.findData(cur)))
        self.vendor.blockSignals(False)

    def active(self) -> bool:
        return bool(self.text.text().strip() or self.kind.currentData() or self.dmin.value() or self.dmax.value()
                    or self.vendor.currentData() or self.op.currentData())

    def reset(self) -> None:
        for w in (self.text, self.kind, self.dmin, self.dmax, self.vendor, self.op):
            w.blockSignals(True)
        self.text.clear()
        for c in (self.kind, self.vendor, self.op):
            c.setCurrentIndex(0)
        self.dmin.setValue(0)
        self.dmax.setValue(0)
        for w in (self.text, self.kind, self.dmin, self.dmax, self.vendor, self.op):
            w.blockSignals(False)
        self.changed.emit()

    def accepts(self, t) -> bool:
        m = self.machine_key if (not self.mach.isHidden() and self.mach.isChecked()) else ''
        return toollib.matches(t, self.text.text(), self.kind.currentData() or '', self.dmin.value(),
                               self.dmax.value(), self.vendor.currentData() or '') and toollib.for_machine(t, m)

    def apply(self, tools) -> list:
        """Outils qui passent les filtres ; « Adaptés à » : seulement les outils
        proposés pour la stratégie, dans l'ordre réglé."""
        out = [t for t in tools if self.accepts(t)]
        kind = self.op.currentData()
        if kind:
            out = toolprefs.ordered(out, kind, toolprefs.load(self.settings), only=True)
        return out


def toggle_full_screen(dlg) -> bool:
    """⛶ / F11 : la fenêtre en plein écran, ou de nouveau normale (agrandie)."""
    if dlg.windowState() & Qt.WindowState.WindowFullScreen:
        dlg.setWindowState(Qt.WindowState.WindowMaximized)
        return False
    dlg.setWindowState(Qt.WindowState.WindowFullScreen)
    return True


def open_large(dlg, settings, key: str, default: bool = True, full: bool = False) -> None:
    """Fenêtre ouverte agrandie (à toute la taille de l'écran) si c'était le
    cas la dernière fois (par défaut : `default`) ; ⛶ et F11 : plein écran.
    `full` : en plein écran d'office (choix d'un outil, bibliothèque d'outils — demande du 14/11, 19 h 45), sauf si
    on l'a quitté la dernière fois (retenu sous « `key`_plein »)."""
    big = default
    if settings is not None:
        v = settings.value(key, default)
        big = v not in (False, 'false', '0', 0)
        if full:
            full = settings.value(key + '_plein', True) not in (False, 'false', '0', 0)
    if full:
        dlg.setWindowState(Qt.WindowState.WindowFullScreen)
    elif big:
        dlg.setWindowState(Qt.WindowState.WindowMaximized)


# --- tri par colonne --------------------------------------------------------------------------
#: clé de tri d'une cellule (nombre pour Ø, T, avance ; texte sans casse sinon)
SORT_ROLE = Qt.ItemDataRole.UserRole + 7
#: rang d'un dossier ou d'un groupe : gardés dans leur ordre, avant les outils, quel que soit le tri
RANK_ROLE = Qt.ItemDataRole.UserRole + 8
_RANK = itertools.count()


def _key(v):
    return v.casefold() if isinstance(v, str) else v


def sortable(view, on_clear=None, settings=None, key: str = '') -> None:
    """Tri par clic sur un titre de colonne : croissant, décroissant, puis l'ordre d'origine (`on_clear` le refait).
    `settings`, `key` : le tri retenu (« colonne,1 » : décroissant)."""
    h = view.header() if hasattr(view, 'header') else view.horizontalHeader()
    h.setSortIndicatorClearable(True)
    col, order = -1, Qt.SortOrder.AscendingOrder
    if settings is not None and key:
        try:
            c, d = str(settings.value(key, '') or '').split(',')
            col, order = int(c), Qt.SortOrder.DescendingOrder if d == '1' else Qt.SortOrder.AscendingOrder
        except ValueError:
            pass
    h.setSortIndicator(col, order)
    view.setSortingEnabled(True)

    def changed(c, o):
        if settings is not None and key:
            settings.setValue(key, f'{c},{int(o == Qt.SortOrder.DescendingOrder)}' if c >= 0 else '')
        if c < 0 and on_clear is not None:
            on_clear()
    h.sortIndicatorChanged.connect(changed)


def _tree_less(a, b) -> bool:
    tree = a.treeWidget()
    col = tree.sortColumn() if tree is not None else 0
    desc = tree is not None and tree.header().sortIndicatorOrder() == Qt.SortOrder.DescendingOrder
    ra, rb = a.data(0, RANK_ROLE), b.data(0, RANK_ROLE)
    if ra is not None or rb is not None:                 # dossiers et groupes : leur ordre, avant les outils
        if ra is not None and rb is not None:
            return (ra < rb) != desc
        return (ra is not None) != desc
    ka, kb = a.data(col, SORT_ROLE), b.data(col, SORT_ROLE)
    if ka is None or kb is None or type(ka) is not type(kb):
        return a.text(col).casefold() < b.text(col).casefold()
    return ka < kb


def _make_tree_item():
    from PySide6.QtWidgets import QTreeWidgetItem

    class SortTreeItem(QTreeWidgetItem):
        """Ligne d'un arbre d'outils triée par ses clés (voir `_tree_less`)."""

        def __lt__(self, other):                           # noqa: D105
            return _tree_less(self, other)
    return SortTreeItem


def _make_cell():
    from PySide6.QtWidgets import QTableWidgetItem

    class SortCell(QTableWidgetItem):
        """Cellule d'une table d'outils triée par sa clé (nombre ou texte sans casse)."""

        def __lt__(self, other):                           # noqa: D105
            ka, kb = self.data(SORT_ROLE), other.data(SORT_ROLE)
            if ka is None or kb is None or type(ka) is not type(kb):
                return self.text().casefold() < other.text().casefold()
            return ka < kb
    return SortCell


SortTreeItem = _make_tree_item()
SortCell = _make_cell()


def tool_item(texts: list, keys: tuple):
    """Ligne d'un outil dans un arbre : ses textes, et la clé de tri de chaque colonne."""
    it = SortTreeItem(texts)
    for c, k in enumerate(keys):
        it.setData(c, SORT_ROLE, _key(k))
    return it


def group_item(texts: list):
    """Ligne d'un dossier ou d'un groupe : gardée à son rang, avant les outils."""
    it = SortTreeItem(texts)
    it.setData(0, RANK_ROLE, next(_RANK))
    return it


def cell(text: str, key):
    c = SortCell(text)
    c.setData(SORT_ROLE, _key(key))
    return c


def remember_large(dlg, settings, key: str, full: bool = False) -> None:
    if settings is not None:
        st = dlg.windowState()
        settings.setValue(key, bool(st & (Qt.WindowState.WindowMaximized | Qt.WindowState.WindowFullScreen)))
        if full:                                         # plein écran quitté : agrandie la prochaine fois
            settings.setValue(key + '_plein', bool(st & Qt.WindowState.WindowFullScreen))
