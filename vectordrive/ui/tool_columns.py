"""Colonnes des listes d'outils (demande du 14/11, 19 h 45) : « Choisir un outil » et la bibliothèque d'outils
montrent les caractéristiques des outils en colonnes, avec l'arborescence des dossiers en plus — à déplacer (glisser
un titre), à montrer ou cacher (clic droit sur les titres), retenues d'une fois sur l'autre. Le n° T n'est montré
que si sa colonne l'est.

`COLUMNS` : (clé, titre) ; `values(t)` : (texte, clé de tri) de chaque colonne ; `install(tree, settings, key,
shown)` règle l'en-tête d'un arbre ; `row(t)` : la ligne d'un outil (`tool_filters.tool_item`).

Colonnes de vitesse (demande du 27/11 : « Tools : colonnes avances écrire mm/min en très petit sous le label
d'avance ») : leur en-tête montre « Avance » et, dessous, « mm/min » en très petit (`UnitHeader`, `unit_header`)."""
from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QFont, QFontMetrics, QPalette
from PySide6.QtWidgets import QHeaderView, QMenu, QStyle, QStyleOptionHeaderV2

from ..i18n import tr

#: colonnes : (clé, titre) ; la première, le nom, reste toujours montrée
COLUMNS = (('name', 'Outil'), ('diameter', 'Ø'), ('vendor', 'Fabricant'), ('ref', 'Référence'), ('number', 'T'),
           ('kind', 'Nature'), ('cut_length', 'L coupe'), ('stickout', 'Dépassement'), ('flutes', 'Dents'),
           ('angle', 'Angle'), ('spindle', 'Broche (tr/min)'), ('feed', 'Avance (mm/min)'),
           ('finish_feed', 'Finition (mm/min)'), ('plunge', 'Plongée (mm/min)'), ('ramp_feed', 'Rampe (mm/min)'), ('step_down', 'Passe Z'),
           ('stepover', 'Recouvrement'), ('folder', 'Dossier'), ('machines', 'Machines'), ('drawings', 'Dessins'))
KEYS = tuple(k for k, _ in COLUMNS)
#: colonnes montrées d'office
SHOWN = ('name', 'diameter', 'cut_length', 'vendor', 'ref')
#: colonnes de vitesse : le libellé, et l'unité de leur titre en très petit dessous (`UnitHeader`)
UNIT_KEYS = ('spindle', 'feed', 'finish_feed', 'plunge', 'ramp_feed')
#: taille de l'unité sous le libellé : part de la police de l'en-tête, et plancher (points)
UNIT_SCALE, UNIT_MIN_PT = 0.68, 5.5


def split_unit(title) -> tuple:
    """« Avance (mm/min) » → (« Avance », « mm/min ») ; un titre sans unité entre parenthèses finales : (titre, '')."""
    t = str(title or '')
    i = t.rfind(' (')
    if i <= 0 or not t.endswith(')') or len(t) - i <= 3:
        return t, ''
    return t[:i], t[i + 2:-1]


class UnitHeader(QHeaderView):
    """En-tête horizontal dont les colonnes `units` (numéros logiques) montrent leur titre « Avance (mm/min) » sur deux
    lignes : le libellé, puis l'unité en très petit (`UNIT_SCALE`), de la couleur atténuée du thème (celle des textes
    d'exemple de la palette, clair comme sombre). Le titre de la colonne (le modèle) reste entier : le tri, le menu des
    colonnes, la disposition retenue, le texte copié ou cherché le lisent comme avant. Largeur de la colonne : celle du
    libellé (l'unité, plus étroite, dessous) ; hauteur : deux lignes, que les colonnes de vitesse soient montrées ou
    non (l'en-tête ne saute pas quand on en montre une)."""

    def __init__(self, parent=None, units=()):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.units = set(units)
        self._unit_fonts = None                     # (police de l'en-tête, police de l'unité, sa mesure)

    def _unit(self) -> tuple:
        """(police de l'unité, sa QFontMetrics), gardées tant que la police de l'en-tête ne change pas."""
        base = self.font()
        if self._unit_fonts is None or self._unit_fonts[0] != base:
            f = QFont(base)
            if f.pointSizeF() > 0:
                f.setPointSizeF(max(UNIT_MIN_PT, f.pointSizeF() * UNIT_SCALE))
            elif f.pixelSize() > 0:
                f.setPixelSize(max(7, round(f.pixelSize() * UNIT_SCALE)))
            self._unit_fonts = (QFont(base), f, QFontMetrics(f))
        return self._unit_fonts[1], self._unit_fonts[2]

    def unit_font(self) -> QFont:
        return QFont(self._unit()[0])

    def parts(self, logical: int):
        """(titre entier, libellé, unité) de la colonne `logical` si elle montre son unité dessous ; sinon None."""
        m = self.model()
        if logical not in self.units or m is None:
            return None
        text = str(m.headerData(logical, self.orientation(), Qt.ItemDataRole.DisplayRole) or '')
        label, unit = split_unit(text)
        return (text, label, unit) if unit else None

    def sectionSizeFromContents(self, logical: int) -> QSize:        # noqa: N802 — API Qt
        size = super().sectionSizeFromContents(logical)
        parts = self.parts(logical)
        if parts is None:
            return size
        text, label, unit = parts
        fm, um = self.fontMetrics(), self._unit()[1]
        width = size.width() - fm.horizontalAdvance(text) + max(fm.horizontalAdvance(label),
                                                                um.horizontalAdvance(unit))
        return QSize(max(width, 1), size.height() + um.height())

    def sizeHint(self) -> QSize:                                    # noqa: N802 — API Qt
        size = super().sizeHint()
        cols = [c for c in self.units if 0 <= c < self.count() and self.parts(c) is not None]
        if cols:                                                     # cachées comprises : même hauteur
            size.setHeight(max([size.height()] + [self.sectionSizeFromContents(c).height() for c in cols]))
        return size

    def paintSection(self, painter, rect, logical: int) -> None:    # noqa: N802 — API Qt
        parts = self.parts(logical)
        if parts is None or not rect.isValid():
            super().paintSection(painter, rect, logical)
            return
        _text, label, unit = parts
        style = self.style()
        opt = QStyleOptionHeaderV2()
        self.initStyleOption(opt)
        self.initStyleOptionForIndex(opt, logical)
        opt.rect = QRect(rect)
        opt.text = ''
        painter.save()
        style.drawControl(QStyle.ControlElement.CE_Header, opt, painter, self)    # le fond, la flèche du tri
        area = style.subElementRect(QStyle.SubElement.SE_HeaderLabel, opt, self)
        fm = self.fontMetrics()
        ufont, um = self._unit()
        top = area.top() + max(0, (area.height() - fm.height() - um.height()) // 2)
        opt.rect = QRect(area.left(), top, area.width(), fm.height())
        opt.text = fm.elidedText(label, Qt.TextElideMode.ElideRight, max(area.width(), 0))
        style.drawControl(QStyle.ControlElement.CE_HeaderLabel, opt, painter, self)   # le libellé, comme les autres
        painter.setFont(ufont)
        group = QPalette.ColorGroup.Normal if self.isEnabled() else QPalette.ColorGroup.Disabled
        painter.setPen(opt.palette.color(group, QPalette.ColorRole.PlaceholderText))
        align = (opt.textAlignment & Qt.AlignmentFlag.AlignHorizontal_Mask) | Qt.AlignmentFlag.AlignVCenter
        painter.drawText(QRect(area.left(), top + fm.height(), area.width(), um.height()), align,
                         um.elidedText(unit, Qt.TextElideMode.ElideRight, max(area.width(), 0)))
        painter.restore()


def unit_header(view, columns) -> UnitHeader:
    """`view` (QTreeWidget ou QTableWidget) prend un `UnitHeader` dont les colonnes `columns` montrent leur unité en
    très petit sous le libellé. L'en-tête d'avant est remplacé (repris : déplaçable, cliquable, dernière colonne
    étirée, alignement, flèche du tri) : à poser avant de régler l'en-tête et de brancher ses signaux."""
    tree = hasattr(view, 'setHeader')
    old = view.header() if tree else view.horizontalHeader()
    if isinstance(old, UnitHeader):
        old.units = set(columns)
        if old.count():                                   # tailles et hauteur recalculées, titres repeints
            old.headerDataChanged(old.orientation(), 0, old.count() - 1)
        old.updateGeometry()
        old.viewport().update()
        return old
    h = UnitHeader(view, columns)
    h.setSectionsMovable(old.sectionsMovable())
    h.setSectionsClickable(old.sectionsClickable())
    h.setHighlightSections(old.highlightSections())
    h.setStretchLastSection(old.stretchLastSection())
    h.setDefaultAlignment(old.defaultAlignment())
    h.setSortIndicatorShown(old.isSortIndicatorShown())
    h.setSortIndicatorClearable(old.isSortIndicatorClearable())
    h.setSortIndicator(old.sortIndicatorSection(), old.sortIndicatorOrder())
    if tree:
        view.setHeader(h)
    else:
        view.setHorizontalHeader(h)
    return h


def _num(v, unit: str = '') -> str:
    try:
        v = float(v or 0.0)
    except (TypeError, ValueError):
        return ''
    return f'{v:g}{unit}' if v else ''


def values(t) -> list:
    """(texte, clé de tri) de chaque colonne de `COLUMNS` pour l'outil `t`."""
    from ..cam import toollib
    from ..cam.model import TOOL_KINDS
    out = []
    for k in KEYS:
        if k == 'name':
            out.append((f'{t.name} — {toollib.specs(t)}', t.name))
        elif k == 'number':
            out.append((f'T{t.number}', int(t.number or 0)))
        elif k == 'kind':
            text = tr(TOOL_KINDS.get(t.kind, t.kind))
            out.append((text, text))
        elif k == 'angle':
            out.append((_num(t.angle, '°'), float(t.angle or 0.0)))
        elif k == 'stepover':
            v = float(t.stepover or 0.0)
            out.append((f'{v * 100:g} %' if v else '', v))
        elif k == 'flutes':
            out.append((str(t.flutes) if t.flutes else '', int(t.flutes or 0)))
        elif k in ('vendor', 'ref'):
            v = str(getattr(t, k) or '')
            out.append((v, v))
        elif k == 'folder':
            v = toollib.folder_of(t)
            out.append((v, v))
        elif k == 'machines':
            v = ', '.join(t.machines or []) or tr('toutes')
            out.append((v, v))
        elif k == 'drawings':
            d = t.drawings or {}
            v = ' '.join(x.upper() for x in ('dxf', 'step') if d.get(x))
            out.append((v, v))
        else:
            v = float(getattr(t, k, 0.0) or 0.0)
            out.append((_num(v), v))
    return out


def row(t):
    """Ligne d'un outil, une cellule par colonne, chacune avec sa clé de tri ; la fiche en infobulle."""
    from .tool_filters import tool_item
    vals = values(t)
    return tool_item([v[0] for v in vals], tuple(v[1] for v in vals))


def install(tree, settings=None, key: str = '', shown=SHOWN) -> None:
    """L'en-tête de `tree` : les titres de `COLUMNS`, déplaçables ; clic droit : montrer ou cacher une colonne ;
    disposition retenue sous `key` (`settings`). D'office : `shown`. Un en-tête neuf (`UnitHeader` : l'unité des
    colonnes de vitesse en très petit sous le libellé) : brancher ses signaux après `install`."""
    tree.setColumnCount(len(COLUMNS))
    tree.setHeaderLabels([tr(label) for _k, label in COLUMNS])
    h = unit_header(tree, [KEYS.index(k) for k in UNIT_KEYS])
    h.setSectionsMovable(True)
    h.setFirstSectionMovable(False)                     # le nom et l'arborescence restent à gauche
    h.setStretchLastSection(False)
    h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    for c, k in enumerate(KEYS):
        h.setSectionHidden(c, k not in shown)
    h.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def menu(pos) -> None:
        m = column_menu(tree, settings, key, shown)
        m.exec(h.mapToGlobal(pos))
        m.deleteLater()
    h.customContextMenuRequested.connect(menu)
    state = settings.value(f'{key}/entete') if settings is not None and key else None
    same = settings is not None and key and str(settings.value(f'{key}/cles', '') or '') == ' '.join(KEYS)
    if state and same:                                   # disposition retenue pour ces colonnes-là seulement
        default = h.saveState()
        try:
            ok = h.restoreState(state)
        except TypeError:
            ok = False
        if not ok or h.count() != len(COLUMNS):
            h.restoreState(default)
        h.setSectionHidden(0, False)
    if settings is not None and key:
        h.sectionMoved.connect(lambda *_a: remember(tree, settings, key))
        h.sectionResized.connect(lambda *_a: remember(tree, settings, key))


def remember(tree, settings, key: str) -> None:
    if settings is not None and key:
        settings.setValue(f'{key}/entete', tree.header().saveState())
        settings.setValue(f'{key}/cles', ' '.join(KEYS))  # colonnes de cette disposition (changées : oubliée)


def shown_keys(tree) -> list:
    """Les colonnes montrées, dans l'ordre où elles sont vues."""
    h = tree.header()
    cols = sorted(range(len(KEYS)), key=h.visualIndex)
    return [KEYS[c] for c in cols if not h.isSectionHidden(c)]


def listen(tree, fn) -> None:
    """`fn()` à chaque colonne montrée ou cachée par `set_shown` ou « Colonnes par défaut »."""
    if not hasattr(tree, 'vd_column_listeners'):
        tree.vd_column_listeners = []
    tree.vd_column_listeners.append(fn)


def _changed(tree) -> None:
    for fn in list(getattr(tree, 'vd_column_listeners', None) or []):
        fn()


def set_shown(tree, k: str, on: bool, settings=None, key: str = '') -> None:
    if k in KEYS and k != 'name':
        h, c = tree.header(), KEYS.index(k)
        if not on and h.sortIndicatorSection() == c:       # colonne du tri cachée : l'ordre d'origine
            h.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        h.setSectionHidden(c, not on)
        remember(tree, settings, key)
        _changed(tree)


def column_menu(tree, settings=None, key: str = '', shown=SHOWN) -> QMenu:
    """Clic droit sur les titres : chaque colonne, cochée si montrée ; « Colonnes par défaut » (`shown`)."""
    m = QMenu(tree)
    h = tree.header()
    for c, (k, label) in enumerate(COLUMNS):
        if k == 'name':
            continue
        a = m.addAction(tr(label))
        a.setCheckable(True)
        a.setChecked(not h.isSectionHidden(c))
        a.toggled.connect(lambda on, k=k: set_shown(tree, k, on, settings, key))
    m.addSeparator()

    def reset():
        for c, k in enumerate(KEYS):
            h.moveSection(h.visualIndex(c), c)
            h.setSectionHidden(c, k not in shown)
        remember(tree, settings, key)
        _changed(tree)
    m.addAction(tr('Colonnes par défaut'), reset)
    return m
