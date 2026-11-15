"""Colonnes des listes d'outils (demande du 14/11, 19 h 45) : « Choisir un outil » et la bibliothèque d'outils
montrent les caractéristiques des outils en colonnes, avec l'arborescence des dossiers en plus — à déplacer (glisser
un titre), à montrer ou cacher (clic droit sur les titres), retenues d'une fois sur l'autre. Le n° T n'est montré
que si sa colonne l'est.

`COLUMNS` : (clé, titre) ; `values(t)` : (texte, clé de tri) de chaque colonne ; `install(tree, settings, key,
shown)` règle l'en-tête d'un arbre ; `row(t)` : la ligne d'un outil (`tool_filters.tool_item`)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QMenu

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
    disposition retenue sous `key` (`settings`). D'office : `shown`."""
    tree.setColumnCount(len(COLUMNS))
    tree.setHeaderLabels([tr(label) for _k, label in COLUMNS])
    h = tree.header()
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
