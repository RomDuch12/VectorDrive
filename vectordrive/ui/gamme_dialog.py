"""Fenêtre de la gamme à plusieurs outils (manuel de TE, pages 619 à 621) : une ligne par outil, et les réglages de toute la gamme."""
from __future__ import annotations

from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                               QHBoxLayout, QHeaderView, QMessageBox, QPushButton, QTableWidget, QVBoxLayout)

from PySide6.QtCore import Qt

from ..cam import gamme
from ..i18n import tr

#: largeurs de la liste des outils (px) : au moins, au plus
TOOL_WIDTH, TOOL_WIDTH_MAX = 260, 520


def _fit_combo(w) -> None:
    """La liste à la largeur de son plus long libellé (fermée comme dépliée), dans les bornes."""
    fm = w.fontMetrics()
    widest = max((fm.horizontalAdvance(w.itemText(i)) for i in range(w.count())), default=0)
    want = widest + w.iconSize().width() + 48                # l'icône, la flèche, les marges
    w.setMinimumWidth(max(TOOL_WIDTH, min(want, TOOL_WIDTH_MAX)))
    w.view().setMinimumWidth(max(TOOL_WIDTH, want))          # dépliée : les noms entiers


def tool_combo(doc_tools: list, library: dict, settings, current: str = '', none_label: str = '',
               machine: tuple = ('', '')):
    """La liste des outils d'une gamme, comme celle du formulaire d'opération (demande du 18/11 : « gamme bug liste
    choix outils ») : les outils du document (icône, libellé court, fiche en infobulle), puis « Choisir un outil (Mes
    outils, bibliothèques)… ». `none_label` : une première ligne sans outil ; `current` inconnu et pas de
    `none_label` : « — Choisir un outil — » d'abord."""
    from ..cam import toollib
    from .tool_filters import tool_icon
    from .tool_picker import ToolCombo
    w = ToolCombo(library, doc_tools, settings, machine=machine)
    if none_label:
        w.addItem(none_label, '')
    for t in doc_tools:
        w.addItem(tool_icon(t), toollib.short_label(t), t.id)
        w.setItemData(w.count() - 1, toollib.summary(t), Qt.ItemDataRole.ToolTipRole)
    w.finish()
    i = w.findData(current) if current or none_label else -1
    if i < 0 and not none_label:                         # pas d'outil : aucun mis d'office
        w.insertItem(0, tr('— Choisir un outil —'), '')
        i = 0
    w.setCurrentIndex(max(0, i))
    w._last = w.currentIndex()
    _fit_combo(w)
    w.currentIndexChanged.connect(lambda _i: _fit_combo(w))      # un outil de bibliothèque ajouté : sa largeur
    return w


def chosen_key(w) -> str:
    """Ce que la liste désigne : l'identifiant d'un outil du document, 'lib:<id>' pour un outil de bibliothèque, ''
    sans outil (la ligne « Choisir… » : le dernier outil choisi)."""
    from .tool_picker import PICK
    v = w.currentData()
    if v == PICK:
        v = w.itemData(getattr(w, '_last', 0))
        v = '' if v == PICK else v
    return v if isinstance(v, str) else ''


def chosen_tool(w, setup, library: dict) -> str:
    """L'identifiant de l'outil choisi dans `w` ; un outil de Mes outils ou d'une bibliothèque est copié dans les
    outils du document `setup` (une fois : le même outil déjà là est repris), avec un n° de magasin libre."""
    from ..cam import model
    v = chosen_key(w)
    if not v.startswith('lib:'):
        return v
    t = library.get(v[4:])
    if t is None:
        return ''
    same = next((c for c in setup.tools if c.name == t.name and c.kind == t.kind and c.diameter == t.diameter), None)
    if same is not None:
        return same.id
    c = model.CamTool.from_dict(t.to_dict())
    c.id, c.folder = model.new_id(), ''
    used = {x.number for x in setup.tools}
    if c.number in used or c.number <= 0:
        c.number = max(used | {0}) + 1
    setup.tools.append(c)
    return c.id


def _spin(value: float, top: float, suffix: str = ' mm', low: float = 0.0, decimals: int = 3) -> QDoubleSpinBox:
    sp = QDoubleSpinBox()
    sp.setRange(low, top)
    sp.setDecimals(decimals)
    sp.setSuffix(suffix)
    sp.setValue(value)
    return sp


class GammeDialog(QDialog):
    """`setup` : les outils du document. `steps` : les lignes de départ. Après OK : `steps()`, `depth`, `stock`, `contour_ref`,
    `skip_frame`, `z_start`. Les outils sont classés à la validation."""
    COLUMNS = ('Outil', 'Usinage', 'Distance entre passes', 'Profondeur', 'Profondeur de passe', 'Finition 3D', 'Angle')

    def __init__(self, parent, setup, steps: list, depth: float = 0.5, library=None, settings=None,
                 machine: tuple = ('', '')):
        super().__init__(parent)
        self.setup_doc = setup
        self.tools = [t for t in setup.tools if t.kind != 'laser']
        #: Mes outils et les bibliothèques des plugins ({id : outil}), proposés par « Choisir un outil… »
        self.library = {t.id: t for t in (library or []) if t.kind != 'laser'}
        self.settings = settings
        self.machine = tuple(machine or ('', ''))
        self.setWindowTitle(tr('Gamme multi-outils'))
        lay = QVBoxLayout(self)
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels([tr(c) for c in self.COLUMNS])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)   # (la colonne Outil prend sa largeur)
        lay.addWidget(self.table, 1)
        row = QHBoxLayout()
        self.add_btn = QPushButton(tr('Ajouter un outil'))
        self.add_btn.clicked.connect(lambda: self.add_step())
        self.del_btn = QPushButton(tr('Retirer'))
        self.del_btn.clicked.connect(self.remove_step)
        row.addWidget(self.add_btn)
        row.addWidget(self.del_btn)
        row.addStretch(1)
        lay.addLayout(row)
        form = QFormLayout()
        self.w_z = _spin(0.0, 1000.0, low=-1000.0)
        self.w_depth = _spin(depth, 1000.0)
        self.w_ref = QComboBox()
        self.w_ref.addItem(tr('En surface'), 'surface')
        self.w_ref.addItem(tr('En fond de gravure'), 'fond')
        self.w_stock = _spin(0.0, 100.0)
        self.w_frame = QCheckBox(tr('Ignorer le cadre englobant'))
        form.addRow(tr('Z de départ'), self.w_z)
        form.addRow(tr('Profondeur totale'), self.w_depth)
        form.addRow(tr('Respect du contour'), self.w_ref)
        form.addRow(tr('Surépaisseur XY laissée pour la finition'), self.w_stock)
        form.addRow('', self.w_frame)
        lay.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        for s in steps:
            self.add_step(s)
        self.fit_width()

    def fit_width(self) -> None:
        """La fenêtre assez large pour montrer toute la table, sans défilement (dans la limite de l'écran)."""
        self.table.resizeColumnsToContents()
        want = self.table.horizontalHeader().length() + 2 * self.table.frameWidth() + 48
        screen = self.screen().availableGeometry().width() if self.screen() is not None else 1600
        self.resize(max(760, self.width(), min(want, screen - 80)), max(self.height(), 420))

    def _used(self) -> set:
        """Les outils déjà dans la gamme (identifiants du document, 'lib:<id>' pour ceux des bibliothèques)."""
        return {chosen_key(self.table.cellWidget(r, 0)) for r in range(self.table.rowCount())} - {''}

    def add_step(self, step=None) -> None:
        """Une ligne de plus : d'office, le premier outil du document qui n'est pas encore dans la gamme ; s'ils y
        sont tous, « — Choisir un outil — » (jamais deux fois le même outil : demande du 18/11)."""
        r = self.table.rowCount()
        if step is None:
            used = self._used()
            step = gamme.Step(next((t.id for t in self.tools if t.id not in used), ''))
        self.table.insertRow(r)
        tool = tool_combo(self.tools, self.library, self.settings, step.tool_id, machine=self.machine)
        tool.currentIndexChanged.connect(lambda _i: self.table.resizeColumnToContents(0))
        mode = QComboBox()
        mode.addItem(tr('Balayage'), 'balayage')
        mode.addItem(tr('Contournage'), 'contournage')
        mode.setCurrentIndex(max(0, mode.findData(step.mode)))
        finish = QCheckBox()
        finish.setChecked(step.finish3d)
        for col, w in enumerate((tool, mode, _spin(step.stepover, 100.0), _spin(step.depth, 1000.0), _spin(step.step_down, 1000.0), finish,
                                 _spin(step.sweep_angle, 360.0, ' °', -360.0, 2))):
            self.table.setCellWidget(r, col, w)

    def remove_step(self) -> None:
        r = self.table.currentRow()
        self.table.removeRow(r if r >= 0 else self.table.rowCount() - 1)

    def steps(self) -> list:
        """Les lignes de la gamme ; un outil de bibliothèque est copié dans le document (voir `chosen_tool`)."""
        cell = self.table.cellWidget
        return [gamme.Step(chosen_tool(cell(r, 0), self.setup_doc, self.library), cell(r, 1).currentData(),
                           cell(r, 2).value(), cell(r, 3).value(),
                           cell(r, 5).isChecked(), cell(r, 6).value(), cell(r, 4).value()) for r in range(self.table.rowCount())]

    @property
    def depth(self) -> float:
        return self.w_depth.value()

    @property
    def stock(self) -> float:
        return self.w_stock.value()

    @property
    def contour_ref(self) -> str:
        return self.w_ref.currentData()

    @property
    def skip_frame(self) -> bool:
        return self.w_frame.isChecked()

    @property
    def z_start(self) -> float:
        return self.w_z.value()

    def messages(self) -> tuple:
        """Les messages de `cam.gamme.problem` ajoutés au round 1078, écrits ici pour être traduits."""
        return (tr('Choisissez un outil pour chaque ligne de la gamme.'),
                tr('Le même outil est sur deux lignes : chaque ligne de la gamme a son outil.'))

    def accept(self) -> None:
        n = len(self.setup_doc.tools)
        why = gamme.problem(self.setup_doc, self.steps(), self.depth)
        if why:
            del self.setup_doc.tools[n:]                 # gamme refusée : aucune copie d'outil gardée
            QMessageBox.warning(self, tr('Gamme multi-outils'), tr(why))
            return
        super().accept()
