"""Fichier › Ouvrir : navigateur à vignettes. Les dossiers du poste
(lecteurs, Bureau, Documents, dossiers ajoutés), les dessins en vignettes
tracées à la taille choisie (48 à 512 px : la résolution de la vignette
suit sa taille), grand aperçu et fiche du fichier pointé, filtre par
format, recherche par nom, récents (les fichiers ouverts) et favoris ;
Précédent, Parent, Suivant (Alt + flèches) comme l'explorateur. Les
programmes machine (G-code, Heidenhain, SimPL… : ui.nc_preview) y sont
aussi, leur parcours en vignette.
Mêmes mécanismes que la bibliothèque (B) : vignettes dans un fil à part,
celles de l'écran d'abord, gardées pour la séance.

Affichage (r545) : « Détails » comme l'explorateur de Windows (par défaut :
nom, date de modification, type, taille en colonnes triables et
redimensionnables, aucun tracé de vignette — le grand aperçu du fichier
pointé reste), ou « Vignettes ». La recherche filtre le dossier affiché à
la frappe (mots, jokers * et ?) ; Entrée la lance aussi dans les
sous-dossiers (lecture au plus juste, Annuler garde ce qui est trouvé).
"""
from __future__ import annotations

import fnmatch
import math
import os
import pathlib
import time
import unicodedata

from PySide6.QtCore import QByteArray, QFileInfo, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QIcon, QKeySequence, QPalette, QStandardItemModel
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QDialog, QDialogButtonBox,
                               QFileDialog, QFileIconProvider, QHBoxLayout, QHeaderView, QLabel, QListView,
                               QLineEdit, QListWidgetItem, QMenu, QPushButton, QSizePolicy, QStyle,
                               QStyledItemDelegate,
                               QStyleOptionViewItem,
                               QToolButton, QVBoxLayout, QWidget)

from ..i18n import tr
from .nc_preview import NC_EXT
from .symbols import FAVORITES, RECENTS, ROLE_KIND, SymbolPanel, known_stat, walk_files

def _readable() -> tuple:
    """Extensions de tous les dessins que VectorDrive lit (registre du cœur) ; celles de toujours d'abord."""
    from ..io import registry
    first = ('.vnd', '.dxf', '.smb', '.svg', '.ai', '.eps', '.pdf', '.vdz', '.stp', '.step')
    return tuple(dict.fromkeys(first + tuple(e for f in registry.FORMATS if f.reader is not None
                                             for e in f.extensions)))


#: dessins que le navigateur montre : tous ceux que VectorDrive lit, comme Importer
BROWSER_EXT = _readable()
TYPEEDIT_EXT = ('.vnd', '.vnl', '.vnm', '.gvt')
IMAGE_EXT = ('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff', '.gif', '.heic', '.heif', '.avif')
SOLID_EXT = ('.stp', '.step', '.igs', '.iges', '.stl', '.3dxml', '.catpart', '.catproduct', '.cgr', '.catdrawing')
_KNOWN = ('.dxf', '.dwg', '.smb', '.svg', '.ai', '.eps', '.pdf', '.vdz') + TYPEEDIT_EXT + IMAGE_EXT + SOLID_EXT
#: choix du filtre : (libellé, extensions) — les nouveaux à la fin : le filtre retenu l'est par son rang
FILTERS = [('Dessins et programmes', BROWSER_EXT + NC_EXT), ('TypeEdit VND', ('.vnd',)), ('DXF', ('.dxf',)),
           ('Symboles SMB', ('.smb',)), ('SVG', ('.svg',)), ('Illustrator AI', ('.ai',)),
           ('PostScript EPS', ('.eps',)), ('PDF', ('.pdf',)), ('VectorDrive VDZ', ('.vdz',)),
           ('Programmes CN (G-code, Heidenhain…)', NC_EXT), ('Tous les dessins', BROWSER_EXT),
           ('STEP (3D, vue de dessus)', ('.stp', '.step')),
           ('TypeEdit et LaserType (VND, VNL, modèles, GVT)', TYPEEDIT_EXT), ('Images', IMAGE_EXT),
           ('Pièces 3D (STEP, IGES, STL, 3D XML, CATIA)', SOLID_EXT),
           ('Autres dessins (HPGL, EMF, WMF, CorelDRAW, Visio…)', tuple(e for e in BROWSER_EXT if e not in _KNOWN)),
           ('DWG (AutoCAD)', ('.dwg',))]
#: affichage de la liste : clé → libellé ; réglage retenu (Détails, comme Windows, par défaut)
VIEWS = {'details': 'Détails (comme Windows)', 'vignettes': 'Vignettes'}
VIEW_KEY = 'navigateur/vue'
#: colonnes de l'affichage Détails et tri de chacune
COLUMNS = ('Nom', 'Modifié le', 'Type', 'Taille', 'Emplacement')
COLUMN_SORT = ('nom', 'date', 'type', 'taille', 'nom')
COLUMN_WIDTHS = (420, 140, 150, 90, 360)
#: colonne « Emplacement » : montrée quand la liste mêle plusieurs dossiers (Récents, Favoris, Accès rapide)
PLACE_COLUMN = 4
COLUMNS_KEY = 'navigateur/colonnes'
#: la recherche (Entrée) cherche aussi les textes contenus (VND, SMB)
TEXTS_KEY = 'navigateur/textes'
#: dernières recherches lancées (proposées à la frappe)
HISTORY_KEY, HISTORY_MAX = 'navigateur/recherches', 20
#: l'index des dossiers où chercher un dossier, un fichier par son nom (`core.fav_index`), dans les caches
FAV_INDEX_FILE = 'favoris_index.json'
#: les derniers dossiers affichés où ces recherches ont eu lieu : gardés dans l'index (les plus récents)
OTHERS_KEY, OTHERS_MAX = 'navigateur/index_dossiers', 5
#: (date de modification, taille ou None, type) d'une ligne de l'affichage Détails
ROLE_DETAILS = Qt.ItemDataRole.UserRole + 7


def search_texts(base: pathlib.Path, exts, match, index, limit: int, out: list, hits: dict) -> list:
    """Fichiers de `base` (sous-dossiers compris) dont le nom, ou un texte TypeEdit (VND, SMB), répond à
    `match` ; textes des fichiers pas encore lus d'abord, sur plusieurs processus s'il y en a beaucoup
    (index gardé). `hits` : fichier → texte trouvé."""
    every = walk_files(base, exts, None, 1_000_000)
    named = {str(f) for f in every if match(f.name)}
    rest = [f for f in every if str(f) not in named and f.suffix.lower() in ('.vnd', '.smb')]
    index.fill(rest)
    for f in rest:
        t = next((t for t in index.texts(f) if match(t)), None)
        if t is not None:
            hits[str(f)] = t
    out.extend(f for f in every if str(f) in named or str(f) in hits)
    del out[limit:]
    return out


def _layout_of(widget, lay):
    """Disposition (QBoxLayout) qui contient `widget`, cherchée dans `lay` et ses sous-dispositions."""
    for i in range(lay.count()):
        item = lay.itemAt(i)
        if item.widget() is widget:
            return lay
        if item.layout() is not None:
            found = _layout_of(widget, item.layout())
            if found is not None:
                return found
    return None


def matcher(query: str):
    """Filtre de nom de la recherche : tous les mots doivent s'y trouver (sans casse ni accents) ;
    un mot avec * ou ? est un joker (« pla*que », « *.dxf ») ; None si la recherche est vide."""
    words = [_fold(w) for w in str(query or '').split()]
    if not words:
        return None

    def match(name: str) -> bool:
        n = _fold(name)
        for w in words:
            if '*' in w or '?' in w:
                if not (fnmatch.fnmatchcase(n, w) or fnmatch.fnmatchcase(n, f'*{w}*')):
                    return False
            elif w not in n:
                return False
        return True
    return match


def _size_text(size) -> str:
    if size is None:
        return ''
    return f'{max(1, math.ceil(size / 1024)):,} Ko'.replace(',', ' ')


class DetailsDelegate(QStyledItemDelegate):
    """Ligne de l'affichage Détails : icône et nom, puis date, type et taille sous les colonnes
    de l'en-tête (QHeaderView : largeurs et défilement horizontal suivis)."""
    ROW = 24

    def __init__(self, header: QHeaderView, parent=None):
        super().__init__(parent)
        self.header = header

    def sizeHint(self, option, index):                              # noqa: N802 (API Qt)
        return QSize(max(200, self.header.length()), self.ROW)

    def paint(self, p, option, index) -> None:
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text = opt.text
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        icon = icon if isinstance(icon, QIcon) else QIcon()
        opt.text, opt.icon = '', QIcon()
        style = opt.widget.style() if opt.widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, p, opt.widget)
        r = option.rect
        sel = bool(option.state & QStyle.StateFlag.State_Selected)
        p.save()
        p.setPen(opt.palette.color(QPalette.ColorRole.HighlightedText if sel else QPalette.ColorRole.Text))
        fm = opt.fontMetrics
        x = r.left() - self.header.offset()
        w = [0 if self.header.isSectionHidden(i) else self.header.sectionSize(i) for i in range(len(COLUMNS))]
        if not icon.isNull():
            icon.paint(p, QRect(x + 4, r.top() + (r.height() - 16) // 2, 16, 16))
        mid = Qt.AlignmentFlag.AlignVCenter
        p.drawText(QRect(x + 26, r.top(), w[0] - 30, r.height()), mid | Qt.AlignmentFlag.AlignLeft,
                   fm.elidedText(text, Qt.TextElideMode.ElideMiddle, max(10, w[0] - 30)))
        det = index.data(ROLE_DETAILS)
        if det:
            mtime, size, kind = det[:3]
            cols = [time.strftime('%d/%m/%Y %H:%M', time.localtime(mtime)) if mtime else '', kind, _size_text(size),
                    det[3] if len(det) > 3 else '']
            x += w[0]
            for i, s in enumerate(cols):
                cw = w[i + 1]
                if not cw:
                    continue
                align = Qt.AlignmentFlag.AlignRight if i == 2 else Qt.AlignmentFlag.AlignLeft
                p.drawText(QRect(x + 6, r.top(), cw - 12, r.height()), mid | align,
                           fm.elidedText(s, Qt.TextElideMode.ElideRight, max(10, cw - 12)))
                x += cw
        p.restore()
FILTER_KEY = 'navigateur/filtre'
#: nœud de l'arbre : accès rapides de Windows
QUICK = '::acces_rapide'
#: la bibli : les dossiers ajoutés (bouton « + », clic droit › Ajouter à la bibli), sous Récents et Favoris
BIBLI = '::bibli'


def _key(path) -> str:
    return os.path.normcase(os.path.abspath(str(path))) if str(path) else ''
#: accès rapides lus pour la séance (None : pas encore lus)
_QUICK: list | None = None
#: Ouvrir : agrandie la première fois, puis sa dernière taille, agrandie ou en plein écran (⛶, F11) comprises
FULL_KEY = 'navigateur/plein_ecran'
GEOMETRY_KEY = 'navigateur/fenetre'
#: tri des fichiers : clé → libellé ; réglage retenu
SORTS = {'nom': 'Nom', 'date': 'Date (récents d\'abord)', 'taille': 'Taille (gros d\'abord)', 'type': 'Type'}
SORT_KEY = 'navigateur/tri'


def filters() -> list:
    """FILTERS avec les programmes des plugins (SimPL…) là où sont les programmes."""
    from .nc_preview import program_exts
    extra = tuple(e for e in program_exts() if e not in NC_EXT)
    return [(label, exts + extra if set(NC_EXT) <= set(exts) else exts) for label, exts in FILTERS]


def _fold(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn')


def system_roots() -> list[pathlib.Path]:
    """Bureau, Documents, dossier personnel, puis les lecteurs."""
    from PySide6.QtCore import QDir, QStandardPaths
    out = []
    for loc in (QStandardPaths.StandardLocation.DesktopLocation, QStandardPaths.StandardLocation.DocumentsLocation,
                QStandardPaths.StandardLocation.HomeLocation):
        p = QStandardPaths.writableLocation(loc)
        if p:
            out.append(pathlib.Path(p))
    out += [pathlib.Path(d.absoluteFilePath()) for d in QDir.drives()]
    import os
    seen, uniq = set(), []
    for p in out:
        k = str(p).lower()
        if k not in seen and os.path.isdir(p):        # lecteur verrouillé, absent… : écarté sans erreur
            seen.add(k)
            uniq.append(p)
    return uniq


def quick_access() -> list[pathlib.Path]:
    """Dossiers de l'accès rapide de l'explorateur Windows (épinglés et
    fréquents, partages réseau compris), dans son ordre ; [] ailleurs ou en
    cas d'échec. Lus une fois par séance (PowerShell, environ 1 s)."""
    global _QUICK
    if _QUICK is not None:
        return list(_QUICK)
    import os
    import subprocess
    out = []
    if os.name == 'nt' and not os.environ.get('VECTORDRIVE_NO_QUICK'):
        cmd = ('[Console]::OutputEncoding = [Text.Encoding]::UTF8; '
               "(New-Object -ComObject Shell.Application).Namespace("
               "'shell:::{679f85cb-0220-4080-b29b-5540cc05aab6}').Items() | "
               'Where-Object { $_.IsFolder } | ForEach-Object { $_.Path }')
        try:
            r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', cmd],
                               capture_output=True, timeout=8, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            for line in r.stdout.decode('utf-8', 'replace').splitlines():
                line = line.strip()
                if line and not line.startswith('::'):                 # « Ce PC », bibliothèques : sans chemin
                    out.append(pathlib.Path(line))
        except (OSError, subprocess.SubprocessError):
            out = []
    _QUICK = out
    return list(out)


class FileBrowserPanel(SymbolPanel):
    """La bibliothèque en navigateur de fichiers : dossiers quelconques, double-clic : ouvrir."""
    openRequested = Signal(str)
    #: lieu affiché changé (boutons Précédent, Parent, Suivant à revoir)
    navigated = Signal()
    #: tri choisi par un clic sur une colonne (clé de SORTS)
    sortChanged = Signal(str)

    EXTS = BROWSER_EXT
    FAV = 'navigateur/favoris'
    ROOTS_KEY = 'navigateur/dossiers'
    DEEP_KEY = 'navigateur/sous_dossiers'
    SIZE_MAX = 512
    SHOW_EXT = True
    LOGOS_SHOWN = False                          # (le filtre des formats décide seul de ce qui est montré)
    SEARCH_HINT = ('Filtrer le dossier affiché (mots, * et ?) — Entrée : chercher aussi dans les sous-dossiers '
                   '(ou aller au chemin tapé)…')

    def __init__(self, settings, parent=None):
        self._size_default = 160
        self._history: list = []                     # lieux vus : dossier (Path), RECENTS, FAVORITES, QUICK
        self._hpos = -1
        self._walking = False
        self._view = str(settings.value(VIEW_KEY, 'details') or 'details')
        if self._view not in VIEWS:
            self._view = 'details'
        self._icons: dict = {}
        self._search_base = None
        self._search_results = False
        self._in_search = False
        super().__init__(settings, parent, big=True)
        self.add_selection.hide()                       # Ouvrir : rien à ajouter à la bibliothèque d'ici
        # en-tête des colonnes (affichage Détails) au-dessus de la liste
        self.columns = QHeaderView(Qt.Orientation.Horizontal)
        model = QStandardItemModel(0, len(COLUMNS), self.columns)
        model.setHorizontalHeaderLabels([tr(c) for c in COLUMNS])
        self.columns.setModel(model)
        self.columns.setSectionsClickable(True)
        self.columns.setSortIndicatorShown(True)
        self.columns.setStretchLastSection(False)
        self.columns.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.columns.setFixedHeight(self.columns.fontMetrics().height() + 10)   # comme l'explorateur
        widths = settings.value(COLUMNS_KEY, None) or []
        for i, cw in enumerate(COLUMN_WIDTHS):
            try:
                cw = max(40, int(float(widths[i])))       # largeurs retenues d'une fois sur l'autre
            except (IndexError, TypeError, ValueError):
                pass
            self.columns.resizeSection(i, cw)
        self.columns.sectionResized.connect(lambda *_a: self._columns_changed())
        self.columns.sectionClicked.connect(self._column_clicked)
        split = self.list.parentWidget()
        sizes = split.sizes()
        box = QWidget()
        bl = QVBoxLayout(box)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)
        split.insertWidget(split.indexOf(self.list), box)
        bl.addWidget(self.columns)
        bl.addWidget(self.list)
        split.setSizes(sizes)
        self.list.horizontalScrollBar().valueChanged.connect(self.columns.setOffset)
        self._plain_delegate = self.list.itemDelegate()
        self._details_delegate = DetailsDelegate(self.columns, self.list)
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(150)
        self._filter_timer.timeout.connect(self._filter_list)
        self.search.textChanged.connect(lambda _t: self._filter_timer.start())
        self.search.setClearButtonEnabled(True)
        from PySide6.QtCore import QStringListModel
        from PySide6.QtWidgets import QCompleter
        self._history_model = QStringListModel(self.search_history(), self)
        comp = QCompleter(self._history_model, self)           # dernières recherches proposées à la frappe
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        self.search.setCompleter(comp)
        self.search.installEventFilter(self)                         # Échap dans la recherche : effacée
        from PySide6.QtWidgets import QCheckBox
        self.in_texts = QCheckBox(tr('Dans les textes'))
        self.in_texts.setToolTip(tr('Entrée cherche aussi les textes TypeEdit des VND et SMB (client, référence…) ; '
                                    'chaque fichier lu une fois, gardé ensuite'))
        self.in_texts.setChecked(settings.value(TEXTS_KEY, 'false') in (True, 'true'))
        self.in_texts.toggled.connect(lambda on: self.settings.setValue(TEXTS_KEY, bool(on)))
        nav = _layout_of(self.deep, self.layout())
        if nav is not None:                                          # à côté de « Sous-dossiers »
            nav.insertWidget(nav.indexOf(self.deep), self.in_texts)
        # deux autres recherches sur la même ligne (demande du 20/11) : un dossier, un fichier dont le nom contient…,
        # parmi les favoris et le dossier affiché, avec tous leurs sous-dossiers (index : `core.fav_index`) ; Entrée
        tip = tr('Cherche parmi les dossiers favoris et le dossier affiché, avec tous leurs sous-dossiers (mots sans '
                 'casse ni accents, * et ?) — Entrée. La première fois, ils sont indexés ; ensuite l\'index répond '
                 'd\'abord, puis les dossiers changés sont relus')
        self.fav_dir = QLineEdit()
        self.fav_dir.setPlaceholderText(tr('Dossier dont le nom contient…'))
        self.fav_file = QLineEdit()
        self.fav_file.setPlaceholderText(tr('Fichier dont le nom contient…'))
        top = _layout_of(self.search, self.layout())
        for i, ed in enumerate((self.fav_dir, self.fav_file)):
            ed.setToolTip(tip)
            ed.setClearButtonEnabled(True)
            ed.installEventFilter(self)                  # Entrée : la recherche (pas le bouton Ouvrir) ; Échap : effacé
            if top is not None:
                top.insertWidget(top.indexOf(self.search) + 1 + i, ed, 1)
        # le bouton « + » (ajouter un dossier) : « + » et l'icône de la bibliothèque (demande du 20/11)
        from .icons import icon
        self.b_bibli = next((b for b in self.findChildren(QPushButton) if b.text() == '+'), None)
        if self.b_bibli is not None:
            self.b_bibli.setIcon(icon('library'))
            self.b_bibli.setToolTip(tr('Ajouter un dossier à la bibli (sous Récents et Favoris)'))
            self.b_bibli.setFixedWidth(52)
        self._apply_view()
        self._sort_indicator()
        self._size_key = 'navigateur/taille'
        try:
            size = int(float(settings.value(self._size_key, 160)))
        except (TypeError, ValueError):
            size = 160
        self.size.setValue(max(self.size.minimum(), min(self.SIZE_MAX, size)))
        self.size.setToolTip(tr('Taille (et résolution) des vignettes (Ctrl + molette sur la liste)'))
        self._quick_job = None
        if _QUICK is None:                               # lus dans un fil : la fenêtre s'ouvre tout de suite
            from concurrent.futures import ThreadPoolExecutor
            self._quick_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='acces_rapide')
            self._quick_job = self._quick_pool.submit(quick_access)
            self._quick_pool.shutdown(wait=False)
            self._quick_timer = QTimer(self)
            self._quick_timer.timeout.connect(self._quick_ready)
            self._quick_timer.start(100)

    # --- affichage : Détails (comme Windows) ou vignettes ---------------------------------------
    def set_view(self, mode: str) -> None:
        """Affichage choisi (VIEWS) : retenu, liste refaite."""
        self._view = mode if mode in VIEWS else 'details'
        self.settings.setValue(VIEW_KEY, self._view)
        self._apply_view()
        self._reshow()

    def _apply_view(self) -> None:
        L = self.list
        details = self._view == 'details'
        if details:
            L.setItemDelegate(self._details_delegate)
            L.setViewMode(QListView.ViewMode.ListMode)
            L.setFlow(QListView.Flow.TopToBottom)
            L.setWrapping(False)
            L.setGridSize(QSize())
            L.setIconSize(QSize(16, 16))
            L.setWordWrap(False)
            L.setUniformItemSizes(True)
            L.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        else:
            L.setItemDelegate(self._plain_delegate)
            L.setViewMode(QListView.ViewMode.IconMode)
            L.setFlow(QListView.Flow.LeftToRight)
            L.setWrapping(True)
            L.setWordWrap(True)
            L.setUniformItemSizes(False)
            L.set_thumb(self.size.value())
        L.setResizeMode(QListView.ResizeMode.Adjust)
        L.setMovement(QListView.Movement.Static)
        L.setDragEnabled(True)
        self.columns.setVisible(details)
        self.size.setEnabled(not details)
        self.size.setVisible(not details)                # Détails : pas de taille de vignettes à régler
        self.size_label.setVisible(not details)
        self.size.setToolTip(tr('Taille (et résolution) des vignettes (Ctrl + molette sur la liste)') if not details
                             else tr('Affichage Détails : pas de vignettes (Affichage › Vignettes pour les voir)'))

    def _reshow(self) -> None:
        """Le lieu affiché relu (affichage, tri ou filtre changés)."""
        if getattr(self, '_recents_shown', False):
            self.show_recents()
        elif getattr(self, '_favs_shown', False):
            self.show_favorites()
        elif getattr(self, '_fav_shown', False) and getattr(self, '_fav_last', None):
            self.show_fav_results(*self._fav_last)       # un dossier, un fichier cherché par son nom
        elif getattr(self, '_bibli_shown', False):
            self.show_bibli()
        elif getattr(self, '_folder', None) is not None:
            self.show_folder(self._folder)

    def _size_changed(self, v: int) -> None:
        if getattr(self, '_view', 'vignettes') == 'details':
            self.settings.setValue(self._size_key, int(v))       # retenue pour l'affichage Vignettes
            self.list.thumb = int(v)
            return
        super()._size_changed(v)

    def eventFilter(self, obj, ev) -> bool:                          # noqa: N802 (API Qt)
        from PySide6.QtCore import QEvent
        if obj in (getattr(self, 'fav_dir', None), getattr(self, 'fav_file', None)) \
                and ev.type() == QEvent.Type.KeyPress:
            if ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.search_favorites('dossier' if obj is self.fav_dir else 'fichier', obj.text().strip())
                return True                              # (pas le bouton Ouvrir de la fenêtre)
            if ev.key() == Qt.Key.Key_Escape and obj.text():
                obj.clear()
                return True
        if obj is getattr(self, 'search', None) and ev.type() == QEvent.Type.KeyPress \
                and ev.key() == Qt.Key.Key_Escape and self.search.text():
            self.search.clear()                          # Échap : recherche effacée (sinon : la boîte se ferme)
            return True
        return super().eventFilter(obj, ev)

    def _columns_changed(self) -> None:
        self.settings.setValue(COLUMNS_KEY, [self.columns.sectionSize(i) for i in range(len(COLUMNS))])
        self.list.doItemsLayout()                                # largeur des lignes : celle des colonnes
        self.list.viewport().update()

    def _column_clicked(self, i: int) -> None:
        mode = COLUMN_SORT[i] if 0 <= i < len(COLUMN_SORT) else 'nom'
        self.set_sort(mode)
        self.sortChanged.emit(mode)

    def _sort_indicator(self) -> None:
        mode = str(self.settings.value(SORT_KEY, 'nom') or 'nom')
        i = COLUMN_SORT.index(mode) if mode in COLUMN_SORT else 0
        self.columns.setSortIndicator(i, Qt.SortOrder.DescendingOrder if mode in ('date', 'taille')
                                      else Qt.SortOrder.AscendingOrder)

    def _type_of(self, f: pathlib.Path) -> str:
        """Type d'un fichier pour la colonne Type : nom du format de VectorDrive (« AutoCAD DXF »,
        « Symbole TypeEdit »…), « Programme … » pour un programme machine, sinon « Fichier XXX »."""
        ext = f.suffix.lower()
        cache = self.__dict__.setdefault('_types', {})
        if ext not in cache:
            from ..io import registry
            from .nc_preview import is_program
            fmt = registry.by_extension(f)
            if is_program(f):
                cache[ext] = tr('Programme {0}').format(ext.lstrip('.').upper())
            elif fmt is not None:
                cache[ext] = tr(fmt.label)
            else:
                cache[ext] = tr('Fichier {0}').format(ext.lstrip('.').upper())
        return cache[ext]

    def _icon_of(self, f: pathlib.Path) -> QIcon:
        """Icône du système pour l'extension de `f` (lue une fois par extension)."""
        ext = f.suffix.lower()
        ic = self._icons.get(ext)
        if ic is None:
            from .symbols import is_remote
            if is_remote(f):                             # réseau : pas de question au partage (hors d'atteinte ?)
                return self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
            try:
                ic = QFileIconProvider().icon(QFileInfo(str(f)))
            except Exception:                            # noqa: BLE001 — icône du système indisponible
                ic = QIcon()
            if ic.isNull():
                ic = self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
            self._icons[ext] = ic
        return ic

    def show_files(self, files, hits: dict | None = None, folders=(), up=None) -> None:
        if self._view != 'details':
            super().show_files(files, hits, folders, up)
        else:
            self._show_details(files, hits, folders, up)
        if self.search.text().strip():
            self._filter_list()

    def _show_details(self, files, hits, folders, up) -> None:
        """Liste comme l'explorateur (Détails) : dossier parent, dossiers, fichiers ; aucune vignette
        à tracer (le grand aperçu du fichier pointé reste)."""
        self._generation = getattr(self, '_generation', 0) + 1
        for job in getattr(self, '_jobs', None) or []:
            job[2].cancel()
        self._jobs = []
        self._timer.stop()
        self.list.setUpdatesEnabled(False)
        try:
            self.list.clear()
            self._pending = []
            base = getattr(self, '_folder', None) if hits is None else self._search_base
            multi = base is None                         # Récents, Favoris, Accès rapide : plusieurs dossiers
            self.columns.setSectionHidden(PLACE_COLUMN, not multi)
            st = self.style()
            if up is not None:
                it = QListWidgetItem(st.standardIcon(QStyle.StandardPixmap.SP_FileDialogToParent), '..')
                it.setData(Qt.ItemDataRole.UserRole, str(up))
                it.setData(ROLE_KIND, 'up')
                it.setToolTip(tr('Dossier parent (Retour arrière)'))
                self.list.addItem(it)
            dir_icon = st.standardIcon(QStyle.StandardPixmap.SP_DirIcon)
            for d in list(folders)[:self.MAX_LISTED]:
                it = QListWidgetItem(dir_icon, d.name or str(d))
                it.setData(Qt.ItemDataRole.UserRole, str(d))
                it.setData(ROLE_KIND, 'dir')
                mtime = known_stat(getattr(self, '_stats', None), d)[0]
                it.setData(ROLE_DETAILS, (mtime, None, tr('Dossier de fichiers'), str(d.parent) if multi else ''))
                it.setToolTip(str(d))
                self.list.addItem(it)
            for f in files:
                name = f.name
                if base is not None and f.parent != base:
                    try:
                        name = '/'.join(f.relative_to(base).parts)          # sous-dossier devant le nom
                    except ValueError:
                        pass
                mtime, size = known_stat(getattr(self, '_stats', None), f)
                it = QListWidgetItem(self._icon_of(f), name)
                it.setData(Qt.ItemDataRole.UserRole, str(f))
                it.setData(ROLE_DETAILS, (mtime, size, self._type_of(f),
                                          str(f.parent) if multi else ''))
                hit = (hits or {}).get(str(f), '')
                it.setToolTip(str(f) + (f'\n{hit}' if hit else ''))
                self.list.addItem(it)
        finally:
            self.list.setUpdatesEnabled(True)

    # --- recherche : filtre à la frappe, sous-dossiers sur Entrée -------------------------------
    def _filter_list(self) -> None:
        """Lignes de la liste dont le nom ne répond pas à la recherche cachées (à la frappe)."""
        text = self.search.text().strip()
        m = matcher(text)
        if m is None and self._search_results and not self._in_search:
            self._search_results = False                 # recherche effacée : le dossier revient
            self._reshow()
            return
        shown = total = 0
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.data(ROLE_KIND) == 'up':
                continue
            total += 1
            hide = m is not None and not m(pathlib.Path(it.data(Qt.ItemDataRole.UserRole)).name)
            it.setHidden(hide)
            shown += not hide
        if m is not None and not self._search_results:
            self.where.setText(tr('« {0} » : {1} sur {2} — Entrée : chercher aussi dans les sous-dossiers')
                               .format(text, shown, total))
        elif m is None and getattr(self, '_folder', None) is not None and not self._search_results:
            self.where.setText(self._crumbs(self._folder))

    def search_history(self) -> list[str]:
        v = self.settings.value(HISTORY_KEY, []) or []
        return [str(x) for x in ([v] if isinstance(v, str) else v) if str(x).strip()]

    def remember_search(self, text: str) -> None:
        """Recherche lancée (Entrée) : en tête de l'historique (HISTORY_MAX au plus)."""
        h = [text] + [x for x in self.search_history() if x.lower() != text.lower()]
        h = h[:HISTORY_MAX]
        self.settings.setValue(HISTORY_KEY, h)
        if hasattr(self, '_history_model'):
            self._history_model.setStringList(h)

    def _clear_search(self) -> None:
        self._bibli_shown = False                        # (un autre lieu montré)
        if getattr(self, '_fav_shown', False) and not self._in_search:
            self._fav_shown = False                      # un autre lieu remplace les résultats cherchés
            self._search_results = False                 # par nom (dossier, fichier)
        if self.search.text() and not self._in_search:
            self.search.blockSignals(True)
            self.search.clear()
            self.search.blockSignals(False)
            self._search_results = False

    def _quick_ready(self) -> None:
        if self._quick_job is None or not self._quick_job.done():
            return
        self._quick_timer.stop()
        self._quick_job = None
        self._fill_quick()

    def _fill_tree(self) -> None:
        bibli = self.bibli_paths()
        self._bibli_keys = keys = {_key(p) for p in bibli}               # (lue une fois : menu, arbre)
        if hasattr(self, '_sys_roots'):                  # les racines suivent (clé branchée depuis, dossier parti…)
            self.roots = self._local_roots(bibli) + list(self._sys_roots)
        super()._fill_tree()
        from PySide6.QtWidgets import QTreeWidgetItem
        # la bibli (les dossiers ajoutés par « + » ou le clic droit) : un nœud sous Récents et Favoris, plus ses
        # dossiers parmi les lecteurs (demande du 20/11)
        for i in reversed(range(2, self.tree.topLevelItemCount())):
            if _key(self.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole) or '') in keys:
                self.tree.takeTopLevelItem(i)
        from .icons import icon
        b = QTreeWidgetItem([tr('Bibli')])
        b.setIcon(0, icon('library'))
        b.setData(0, Qt.ItemDataRole.UserRole, BIBLI)
        b.setToolTip(0, tr('Les dossiers ajoutés à la bibli (bouton + ou clic droit sur un dossier › Ajouter à la bibli)'))
        self.tree.insertTopLevelItem(2, b)
        for p in bibli:
            ch = QTreeWidgetItem([p.name or str(p)])
            ch.setData(0, Qt.ItemDataRole.UserRole, str(p))
            ch.setToolTip(0, str(p))
            b.addChild(ch)
            self._add_placeholder(ch, p)
        b.setExpanded(True)
        q = QTreeWidgetItem(['⚡ ' + tr('Accès rapide')])
        q.setData(0, Qt.ItemDataRole.UserRole, QUICK)
        q.setToolTip(0, tr('Les accès rapides de l\'explorateur Windows'))
        self.tree.insertTopLevelItem(3, q)
        self._fill_quick()

    # --- la bibli ---------------------------------------------------------------------------
    def bibli_paths(self, settings=None) -> list[pathlib.Path]:
        """Les dossiers de la bibli, dans l'ordre d'ajout : ceux qui existent (un partage : sans le lire), sans les
        dossiers déjà montrés d'office (Bureau, Documents, lecteurs : un ancien « + » les retenait aussi)."""
        from .symbols import is_remote
        settings = self.settings if settings is None else settings
        v = settings.value(self.ROOTS_KEY, []) or []
        v = [v] if isinstance(v, str) else list(v)       # (INI : une liste d'un seul élément relue en texte)
        sys_keys = set(getattr(self, '_sys_keys', set()))
        seen, out = set(), []
        for x in v:
            if not isinstance(x, str) or not x:
                continue
            k = _key(x)
            if k in seen or k in sys_keys:
                continue
            seen.add(k)
            p = pathlib.Path(x)
            if is_remote(p) or os.path.isdir(p):
                out.append(p)
        return out

    def in_bibli(self, path) -> bool:
        return _key(path) in getattr(self, '_bibli_keys', set())

    def _bibli_item(self):
        return next((self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())
                     if self.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole) == BIBLI), None)

    @staticmethod
    def _local_roots(paths) -> list[pathlib.Path]:
        """Les dossiers de la bibli comptés parmi les racines (dossier parent, emplacement, corbeille) : pas un
        partage (injoignable, il figerait chaque clic)."""
        from .symbols import is_remote
        return [p for p in paths if not is_remote(p)]

    def select_in_tree(self, path: pathlib.Path) -> None:
        """Le dossier choisi dans l'arbre : sous la Bibli s'il est dans un de ses dossiers."""
        cur = self.tree.currentItem()
        if cur is not None and _key(cur.data(0, Qt.ItemDataRole.UserRole) or '') == _key(path):
            return                                       # déjà choisi (par un clic dans une autre branche)
        r = self._root_of(path)
        node = self._bibli_item() if r is not None and self.in_bibli(r) else None
        if node is None:
            super().select_in_tree(path)
            return
        it = next((node.child(k) for k in range(node.childCount())
                   if _key(node.child(k).data(0, Qt.ItemDataRole.UserRole)) == _key(r)), None)
        try:
            parts = path.resolve().relative_to(r.resolve()).parts
        except (ValueError, OSError):
            return
        for part in parts:
            if it is None:
                return
            it.setExpanded(True)
            self._expand(it)
            it = next((it.child(k) for k in range(it.childCount()) if it.child(k).text(0) == part), None)
        if it is not None:
            self.tree.blockSignals(True)
            self.tree.setCurrentItem(it)
            self.tree.blockSignals(False)

    def selected_paths(self, widget=None) -> list[pathlib.Path]:
        """(Récents, Favoris, la Bibli, Accès rapide : pas des dossiers à renommer ni à jeter.)"""
        return [p for p in super().selected_paths(widget) if not str(p).startswith('::')]

    def _protected(self, path) -> bool:
        """Un dossier de la bibli ou montré d'office (Bureau, lecteurs…) : jamais renommé, jeté ni déplacé ici
        (un partage n'a pas de corbeille)."""
        k = _key(path)
        return k in getattr(self, '_bibli_keys', set()) or k in getattr(self, '_sys_keys', set())

    def place_files(self, files, folder, copy: bool = False) -> int:
        """Déposés sur la Bibli : les dossiers y sont ajoutés ; sur Accès rapide, Récents… : rien ; un dossier de
        la bibli ou un lecteur glissé ailleurs : jamais déplacé."""
        if str(folder) == BIBLI:
            return self.add_to_bibli([pathlib.Path(f) for f in files if os.path.isdir(f)])
        if str(folder).startswith('::'):
            return 0
        files = [f for f in files if not self._protected(f)]
        return super().place_files(files, folder, copy) if files else 0

    def rename(self, path, name=None):
        if self._protected(path):
            return None
        return super().rename(path, name)

    def delete(self, paths, confirm: bool = True) -> int:
        return super().delete([p for p in paths if not self._protected(p)], confirm)

    def current_folder(self):
        """(Récents, Favoris, la Bibli, Accès rapide choisis : pas un dossier — rien n'y est créé ni importé.)"""
        f = super().current_folder()
        return None if f is not None and str(f).startswith('::') else f

    def _set_bibli(self, paths) -> None:
        self.settings.setValue(self.ROOTS_KEY, [str(p) for p in paths])
        self._fill_tree()
        if getattr(self, '_folder', None) is not None:
            self.select_in_tree(self._folder)            # (l'arbre refait : le dossier affiché y reste choisi)
        if getattr(self, '_bibli_shown', False):
            self.show_bibli()

    def add_to_bibli(self, paths) -> int:
        """Les dossiers `paths` ajoutés à la bibli (à la fin) ; rend le nombre ajouté."""
        v = self.settings.value(self.ROOTS_KEY, []) or []
        cur = [str(x) for x in ([v] if isinstance(v, str) else v) if x]
        have = {_key(x) for x in cur}
        have |= set(getattr(self, '_sys_keys', set()))   # (Bureau, Documents, lecteurs : déjà montrés)
        new = [str(pathlib.Path(p)) for p in paths if os.path.isdir(p) and _key(p) not in have]
        if new:
            self._set_bibli(cur + list(dict.fromkeys(new)))
        return len(new)

    def remove_from_bibli(self, paths) -> int:
        v = self.settings.value(self.ROOTS_KEY, []) or []
        cur = [str(x) for x in ([v] if isinstance(v, str) else v) if x]
        gone = {_key(p) for p in paths}
        keep = [x for x in cur if _key(x) not in gone]
        if len(keep) != len(cur):
            self._set_bibli(keep)
        return len(cur) - len(keep)

    def _add_root(self) -> None:
        """Bouton « + » : un dossier choisi, ajouté à la bibli."""
        from PySide6.QtWidgets import QFileDialog
        start = getattr(self, '_folder', None)
        d = QFileDialog.getExistingDirectory(self, tr('Ajouter un dossier à la bibli'), str(start or ''))
        if d:
            self.add_to_bibli([pathlib.Path(d)])

    def show_bibli(self) -> None:
        """Les dossiers de la bibli dans la liste."""
        self._clear_search()
        self._folder = None
        self._recents_shown = self._favs_shown = False
        folders = self.bibli_paths()
        self.show_files([], folders=folders)
        self._bibli_shown = True
        node = self._bibli_item()
        if node is not None:
            self.tree.blockSignals(True)
            self.tree.setCurrentItem(node)
            self.tree.blockSignals(False)
        self.where.setText(tr('Bibli') + f' ({len(folders)})')
        self._visit(BIBLI)

    def _quick_item(self):
        return next((self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())
                     if self.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole) == QUICK), None)

    def _fill_quick(self) -> None:
        """Les accès rapides sous leur nœud (sans lire les dossiers : un partage
        réseau absent ne bloque rien)."""
        from PySide6.QtWidgets import QTreeWidgetItem
        q = self._quick_item()
        if q is None or _QUICK is None:
            return
        q.takeChildren()
        for p in _QUICK:
            ch = QTreeWidgetItem([p.name or str(p)])
            ch.setData(0, Qt.ItemDataRole.UserRole, str(p))
            ch.setToolTip(0, str(p))
            q.addChild(ch)
            self._add_placeholder(ch, p)
        q.setExpanded(True)

    def show_quick(self) -> None:
        """Les accès rapides en dossiers dans la liste."""
        self._clear_search()
        self._folder = None
        self._recents_shown = self._favs_shown = False
        folders = list(_QUICK or [])
        self.show_files([], folders=folders)
        self.where.setText(tr('Accès rapide') + f' ({len(folders)})')
        self._visit(QUICK)

    # --- Précédent, Parent, Suivant -------------------------------------------------------
    def _visit(self, place) -> None:
        """Le lieu affiché noté dans l'historique (sauf s'il y est déjà, ou si on y circule)."""
        if not self._walking and not (0 <= self._hpos < len(self._history) and self._history[self._hpos] == place):
            del self._history[self._hpos + 1:]
            self._history.append(place)
            self._hpos = len(self._history) - 1
        self.navigated.emit()

    def _show_place(self, place) -> None:
        self._walking = True
        try:
            if place == QUICK:
                self.show_quick()
            elif place == BIBLI:
                self.show_bibli()
            elif place == RECENTS:
                self.show_recents()
            elif place == FAVORITES:
                self.show_favorites()
            elif os.path.isdir(place):                     # dossier qui ne répond pas : rien, sans erreur
                self.show_folder(pathlib.Path(place))
        finally:
            self._walking = False
        self.navigated.emit()

    def can_back(self) -> bool:
        return self._hpos > 0

    def can_forward(self) -> bool:
        return self._hpos < len(self._history) - 1

    def can_up(self) -> bool:
        f = getattr(self, '_folder', None)
        return f is not None and self._parent_in_library(f) is not None

    def go_back(self) -> None:
        if self.can_back():
            self._hpos -= 1
            self._show_place(self._history[self._hpos])

    def go_forward(self) -> None:
        if self.can_forward():
            self._hpos += 1
            self._show_place(self._history[self._hpos])

    def show_folder(self, path: pathlib.Path) -> None:
        self._clear_search()                             # comme l'explorateur : la recherche ne suit pas
        super().show_folder(path)
        if os.path.isdir(path):
            self._visit(path)

    def show_favorites(self) -> None:
        self._clear_search()
        super().show_favorites()
        self._visit(FAVORITES)

    def _folder_clicked(self, it) -> None:
        if it.data(0, Qt.ItemDataRole.UserRole) == QUICK:
            self.show_quick()
        elif it.data(0, Qt.ItemDataRole.UserRole) == BIBLI:
            self.show_bibli()
        else:
            super()._folder_clicked(it)

    def sorted_files(self, files) -> list:
        """Fichiers selon le tri choisi (nom, date de modification, taille,
        type puis nom) ; un fichier illisible passe en dernier."""
        files = list(files)
        mode = str(self.settings.value(SORT_KEY, 'nom') or 'nom')

        stats = getattr(self, '_stats', None)

        def stat(p, attr):                               # lue avec le dossier : pas d'accès disque en plus
            mtime, size = known_stat(stats, p)
            return (mtime if attr == 'st_mtime' else size) or 0
        if mode == 'date':
            return sorted(files, key=lambda p: (-stat(p, 'st_mtime'), p.name.lower()))
        if mode == 'taille':
            return sorted(files, key=lambda p: (-stat(p, 'st_size'), p.name.lower()))
        if mode == 'type':
            return sorted(files, key=lambda p: (p.suffix.lower(), p.name.lower()))
        return sorted(files, key=lambda p: p.name.lower())

    def set_sort(self, mode: str) -> None:
        """Tri choisi : retenu, liste refaite."""
        self.settings.setValue(SORT_KEY, mode if mode in SORTS else 'nom')
        if hasattr(self, 'columns'):
            self._sort_indicator()
        if getattr(self, '_folder', None) is not None and not self._search_results:
            self.show_folder(self._folder)

    def _initial_roots(self, settings) -> list[pathlib.Path]:
        sys_roots = system_roots()
        self._sys_roots = sys_roots
        self._sys_keys = {_key(r) for r in sys_roots}
        return self._local_roots(self.bibli_paths(settings)) + sys_roots   # (la bibli : sous son nœud)

    def _parent_in_library(self, path: pathlib.Path) -> pathlib.Path | None:
        return path.parent if path.parent != path else None             # jusqu'à la racine du lecteur

    #: sous-dossiers montrés dans l'arbre (un dossier temporaire en compte des dizaines de milliers)
    MAX_TREE = 2000

    def _add_placeholder(self, it, path: pathlib.Path) -> None:
        from PySide6.QtWidgets import QTreeWidgetItem
        it.addChild(QTreeWidgetItem(['…']))          # sans lire le disque : vu au dépliage

    def _expand(self, it) -> None:
        import os
        from PySide6.QtWidgets import QTreeWidgetItem
        if not (it.childCount() == 1 and it.child(0).text(0) == '…'):
            return
        it.takeChild(0)
        path = pathlib.Path(it.data(0, Qt.ItemDataRole.UserRole))
        from .symbols import is_remote, list_dir
        if is_remote(path):                              # réseau : lu dans le fil de calcul (Annuler s'il tarde)
            from .progress import Cancelled, run
            try:
                listed = run(self, tr('Lecture de {0}').format(path.name or str(path)), list_dir, path, ())
            except (Cancelled, Exception):               # noqa: BLE001 — partage absent : rien à déplier
                listed = None
            names = [d.name for d in listed[1]] if listed else []
        else:
            try:
                with os.scandir(path) as sc:
                    names = sorted((e.name for e in sc if e.is_dir()), key=str.lower)
            except OSError:
                names = []
        for name in names[:self.MAX_TREE]:
            ch = QTreeWidgetItem([name])
            ch.setData(0, Qt.ItemDataRole.UserRole, str(path / name))
            it.addChild(ch)
            self._add_placeholder(ch, path / name)
        if len(names) > self.MAX_TREE:
            more = QTreeWidgetItem([tr('… {0} autres dossiers').format(len(names) - self.MAX_TREE)])
            more.setData(0, Qt.ItemDataRole.UserRole, str(path))
            it.addChild(more)

    def _root_of(self, path: pathlib.Path) -> pathlib.Path | None:
        best = None                                                       # la racine la plus proche
        for r in self.roots:
            try:
                path.resolve().relative_to(r.resolve())
            except (ValueError, OSError):
                continue
            if best is None or len(r.resolve().parts) > len(best.resolve().parts):
                best = r
        return best

    def show_recents(self) -> None:
        """Les derniers fichiers ouverts (Fichier › Récents) que le filtre retient."""
        self._clear_search()
        self._folder = None
        self._recents_shown = True
        self._favs_shown = False
        v = self.settings.value('fichiers/recents', []) or []
        files = [pathlib.Path(p) for p in ([v] if isinstance(v, str) else v)]
        from .symbols import is_remote
        # un fichier d'un partage hors d'atteinte : gardé sans le vérifier (pas d'attente du réseau)
        files = [p for p in files if p.suffix.lower() in self.EXTS and (is_remote(p) or os.path.isfile(p))]
        self.show_files(files, {str(f): '' for f in files})
        self.where.setText(tr('Récents') + f' ({len(files)})')
        self._visit(RECENTS)

    def _search(self) -> None:
        """Entrée : fichiers du dossier affiché ET de ses sous-dossiers dont le nom répond à la
        recherche (mots sans casse ni accents, jokers), lus au plus juste dans le fil de calcul
        (avancement, Annuler garde ce qui est trouvé). Un chemin tapé (comme dans la barre d'adresse de
        l'explorateur) : son dossier affiché, ou le fichier ouvert."""
        text = self.search.text().strip()
        typed = pathlib.Path(text.strip('"')) if ('\\' in text or '/' in text) else None
        try:
            if typed is not None and typed.is_dir():
                self.search.clear()
                self.show_folder(typed)
                return
            if typed is not None and typed.is_file():
                self.search.clear()
                self.openRequested.emit(str(typed))
                return
        except OSError:                                  # chemin réseau absent : recherche ordinaire
            pass
        m = matcher(text)
        base = getattr(self, '_folder', None) or self.current_folder()
        if m is None or base is None or not base.is_dir():
            return
        self.remember_search(text)
        from .progress import Cancelled, run
        found: list = []
        hits: dict = {}
        stopped = False
        in_texts = self.in_texts.isChecked() if hasattr(self, 'in_texts') else False
        index = self._index() if in_texts else None

        try:
            if in_texts:
                run(self, tr('Recherche de « {0} » dans {1}').format(text, base.name or str(base)),
                    search_texts, base, self.EXTS, m, index, self.MAX_LISTED, found, hits)
            else:
                run(self, tr('Recherche de « {0} » dans {1}').format(text, base.name or str(base)), walk_files,
                    base, self.EXTS, m, self.MAX_LISTED, False, found)
        except Cancelled:
            stopped = True
        finally:
            if index is not None:
                index.save()
        found.sort(key=lambda p: [x.lower() for x in p.parts])
        self._in_search = True
        try:
            self._search_base = base
            self._fav_shown = False                      # (plus les résultats d'un dossier, d'un fichier)
            self._search_results = True
            self.show_files(found, {str(f): hits.get(str(f), '') for f in found})
        finally:
            self._in_search = False
        self.where.setText(tr('« {0} » dans {1} : {2} fichier(s)').format(text, base, len(found))
                           + (' — ' + tr('recherche arrêtée') if stopped else ''))

    # --- un dossier, un fichier par son nom, dans les favoris et le dossier affiché (demande du 20/11) ----------
    def fav_index(self):
        """L'index des dossiers où chercher (`core.fav_index`), gardé à côté des autres caches."""
        if getattr(self, '_fav_idx', None) is None:
            from ..core import fav_index, fonts
            from .symbols import is_hidden
            self._fav_idx = fav_index.shared(fonts.cache_file().parent / FAV_INDEX_FILE, hidden=is_hidden)
        return self._fav_idx

    def fav_scope(self) -> tuple:
        """(dossiers favoris, dossier affiché ou None) : où cherchent les deux recherches. Le dossier affiché reste
        celui d'avant tant que leurs résultats sont montrés ; sans dossier affiché, le dossier choisi dans la liste.
        La racine d'un lecteur n'en est pas (tout le disque indexé), sauf si elle est en favori."""
        from .symbols import favorite_paths, is_remote
        favs = favorite_paths(self.settings, self.FAV)
        folder = getattr(self, '_folder', None)
        if folder is None and getattr(self, '_fav_shown', False):
            folder = getattr(self, '_fav_folder', None)
        if folder is None:                               # Favoris, Récents… : le dossier choisi dans la liste
            it = self.list.currentItem()
            if it is not None and it.isSelected() and it.data(ROLE_KIND) == 'dir':
                folder = pathlib.Path(it.data(Qt.ItemDataRole.UserRole))
        if folder is not None and (folder.parent == folder or not (is_remote(folder) or folder.is_dir())):
            folder = None                                # (un partage : vérifié dans le fil de calcul)
        return favs, folder

    def _fav_keep(self) -> list:
        """Tous les favoris, même absents en ce moment (clé débranchée, partage injoignable) : leur index reste."""
        v = self.settings.value(self.FAV, []) or []
        return [pathlib.Path(x) for x in ([v] if isinstance(v, str) else v) if isinstance(x, str) and x]

    def _fav_others(self, folder, favs) -> list:
        """Les derniers dossiers non favoris où l'on a cherché (OTHERS_MAX), `folder` en tête s'il n'est pas déjà
        compris dans un favori : gardés dans l'index."""
        from ..core import fav_index
        v = self.settings.value(OTHERS_KEY, []) or []
        v = [v] if isinstance(v, str) else list(v)       # (INI : une liste d'un seul élément relue en texte)
        others = []
        fk = {fav_index.key_of(f) for f in favs}
        tops = {fav_index.key_of(r) for r in fav_index.top_roots(list(favs) + ([folder] if folder else []))}
        if folder is not None and fav_index.key_of(folder) not in fk and fav_index.key_of(folder) in tops:
            others.append(str(folder))                   # (ni un favori, ni compris dans un favori)
        for o in v:
            if isinstance(o, str) and o and all(os.path.normcase(o) != os.path.normcase(x) for x in others):
                others.append(o)
        others = others[:OTHERS_MAX]
        self.settings.setValue(OTHERS_KEY, others)
        return others

    def search_favorites(self, kind: str, text: str) -> list:
        """Les dossiers (`kind` 'dossier') ou les fichiers ('fichier', du format choisi) dont le nom contient `text`
        (mots sans casse ni accents, * et ?), parmi les favoris et le dossier affiché, avec tous leurs sous-dossiers.
        La première fois, chacun est indexé ; ensuite : d'abord ce que l'index connaît (montré tout de suite),
        vérifié, puis les dossiers changés relus, l'index mis à jour s'il a changé. Annuler garde ce qui est déjà
        vérifié. Ici, aucun accès aux favoris eux-mêmes (un partage injoignable ne fige pas la fenêtre) : tout se
        fait dans le fil de calcul. Rend les résultats."""
        from ..core import fav_index
        from .progress import Cancelled, run
        m = matcher(text)
        if m is None:
            return []
        favs, folder = self.fav_scope()
        roots = fav_index.top_roots(list(favs) + ([folder] if folder is not None else []))
        idx = self.fav_index()
        others = self._fav_others(folder, favs)
        exts = self.EXTS if kind == 'fichier' else None
        # un favori lui-même : par son nom et son extension (vérifié sur le disque avec les autres, dans le fil)
        direct = [p for p in favs if m(p.name) and ((p.suffix.lower() in self.EXTS) if kind == 'fichier'
                                                    else p.suffix.lower() not in BROWSER_EXT)]
        first = None                                     # (None : la recherche consultera l'index elle-même)
        if idx.lock.acquire(timeout=1.0):                # une recherche annulée finit encore son dossier en cours
            try:
                idx.forget(self._fav_keep() + [pathlib.Path(o) for o in others])
                first = idx.lookup(roots, kind, m, exts, self.MAX_LISTED)
            finally:
                idx.lock.release()
        if first:                                        # d'abord ce que l'index connaît : tout de suite
            self.show_fav_results(kind, text, first, folder, checking=True)
        box: dict = {}
        stopped = False
        try:
            found = run(self, tr('Recherche de « {0} »').format(text), idx.search, roots, kind, m, exts,
                        self.MAX_LISTED, first, box, direct)
        except Cancelled:
            stopped = True
            found = []
        ver = list(box.get('verifies', []))              # lu une fois (le fil peut encore l'écrire après Annuler)
        keys = {os.path.normcase(str(p)) for p in ver}
        dk = {os.path.normcase(str(p)) for p in direct}
        rest = [p for p in ver if os.path.normcase(str(p)) not in dk] if stopped else list(found)
        seen, out = set(), []
        for p in [p for p in direct if os.path.normcase(str(p)) in keys] + rest:
            c = os.path.normcase(str(p))
            if c not in seen:
                seen.add(c)
                out.append(p)
        self.show_fav_results(kind, text, out, folder, stopped=stopped)
        return out

    def refresh(self) -> None:
        """F5, un nom changé, un élément supprimé : les résultats cherchés par nom refaits (sinon : le dossier)."""
        if getattr(self, '_bibli_shown', False):         # F5 sur la Bibli : l'arbre et sa liste relus
            self._fill_tree()
            self.show_bibli()
            return
        last = getattr(self, '_fav_last', None)
        if getattr(self, '_fav_shown', False) and last:
            self._fill_tree()
            self.search_favorites(last[0], last[1])
            return
        super().refresh()

    def show_fav_results(self, kind: str, text: str, paths, folder=None, checking: bool = False,
                         stopped: bool = False) -> None:
        if self.search.text():                           # le filtre de la liste cacherait des résultats
            self.search.blockSignals(True)
            self.search.clear()
            self.search.blockSignals(False)
        self._folder = None
        self._unreadable = False
        self._recents_shown = False
        self._favs_shown = False
        self._fav_shown, self._fav_folder = True, folder
        self._bibli_shown = False
        self._fav_last = (kind, text, list(paths), folder)
        self._in_search = True
        try:
            self._search_base = None
            self._search_results = True
            if kind == 'dossier':
                self.show_files([], {}, folders=list(paths))
            else:
                self.show_files(list(paths), {str(f): '' for f in paths})
        finally:
            self._in_search = False
        what = (tr('{0} dossier(s)') if kind == 'dossier' else tr('{0} fichier(s)')).format(len(paths))
        where = tr('« {0} » dans les favoris : {1}').format(text, what) if folder is None else \
            tr('« {0} » dans les favoris et {1} : {2}').format(text, folder, what)
        self.where.setText(where + (' — ' + tr('vérification…') if checking else '')
                           + (' — ' + tr('recherche arrêtée') if stopped else ''))
        self.navigated.emit()                            # (boutons de la fenêtre : pas de dossier parent)

    def _activated(self, it) -> None:
        if it.data(ROLE_KIND) in ('dir', 'up'):
            super()._activated(it)
        else:
            self.openRequested.emit(it.data(Qt.ItemDataRole.UserRole))

    def menu(self, widget, pos, exec_menu: bool = True):
        if widget is self.tree and pos is not None:
            it = self.tree.itemAt(pos)
            if it is not None and it.data(0, Qt.ItemDataRole.UserRole) in (QUICK, BIBLI):
                self.tree.setCurrentItem(it)
                self._folder_clicked(it)
                return None
        m = super().menu(widget, pos, exec_menu=False)
        if m is None:
            return None
        drop = {tr('Enregistrer la sélection du dessin ici…'), tr('Ajouter la sélection du dessin ici…'),
                tr('Enregistrer la sélection sous…')}
        for a in list(m.actions()):                     # rien à enregistrer d'ici
            if a.text() in drop:
                m.removeAction(a)
        self._bibli_action(m, widget)
        files = [p for p in self.selected_paths(widget) if self._is_file(p)] if widget is self.list else []
        if files:
            first = m.actions()[0] if m.actions() else None
            a = m.addAction(tr('Ouvrir'))
            a.triggered.connect(lambda: [self.openRequested.emit(str(f)) for f in files])
            if first is not None:
                m.removeAction(a)
                m.insertAction(first, a)

        if exec_menu:
            from PySide6.QtGui import QCursor
            m.exec(widget.viewport().mapToGlobal(pos) if pos is not None else QCursor.pos())
            m.deleteLater()
        return m

    def _bibli_action(self, m, widget) -> None:
        """Clic droit sur un ou des dossiers : « Ajouter à la bibli » (ou « Retirer de la bibli »), après les
        favoris."""
        from .icons import icon
        paths = self.selected_paths(widget) if (widget is self.tree or self.list.selectedItems()) else []
        paths = [p for p in paths if str(p) not in (QUICK, BIBLI) and not str(p).startswith('::')]
        sys_keys = getattr(self, '_sys_keys', set())
        if not paths or any(_key(p) in sys_keys for p in paths) or not all(self._is_dir(p) for p in paths):
            return                                       # (Bureau, Documents, lecteurs : déjà montrés d'office)
        inside = all(self.in_bibli(p) for p in paths)
        a = QAction(icon('library'), tr('Retirer de la bibli') if inside else tr('Ajouter à la bibli'), m)
        a.triggered.connect(lambda: self.remove_from_bibli(paths) if inside else self.add_to_bibli(paths))
        acts = m.actions()
        fav = next((i for i, x in enumerate(acts) if x.text().endswith((tr('Ajouter aux favoris'),
                                                                        tr('Retirer des favoris')))), None)
        if fav is not None and fav + 1 < len(acts):
            m.insertAction(acts[fav + 1], a)
        else:
            m.addAction(a)

    def set_exts(self, exts) -> None:
        """Filtre par format : dossier (ou récents, favoris) relu."""
        self.EXTS = tuple(exts)
        last = getattr(self, '_fav_last', None)
        if getattr(self, '_fav_shown', False) and last and last[0] == 'fichier':
            self.search_favorites(last[0], last[1])      # des fichiers cherchés : dans le nouveau format
        elif getattr(self, '_recents_shown', False):
            self.show_recents()
        elif getattr(self, '_favs_shown', False):
            self.show_favorites()
        elif getattr(self, '_folder', None) is not None:
            self.show_folder(self._folder)


class FileBrowser(QDialog):
    """Boîte Ouvrir à vignettes. `paths` : fichiers choisis après exec()."""

    def __init__(self, win, folder: str = ''):
        super().__init__(win)
        self.win = win
        self.settings = win.settings
        self.paths: list[str] = []
        self.insert = False                              # « Insérer dans le dessin » plutôt qu'ouvrir
        self.setWindowTitle(tr('Ouvrir'))
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.setSizeGripEnabled(True)
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        st = self.style()
        self.b_back = QToolButton()
        self.b_back.setIcon(st.standardIcon(QStyle.StandardPixmap.SP_ArrowBack))
        self.b_back.setToolTip(tr('Précédent (Alt + Gauche)'))
        self.b_up = QToolButton()
        self.b_up.setIcon(st.standardIcon(QStyle.StandardPixmap.SP_ArrowUp))
        self.b_up.setToolTip(tr('Dossier parent (Alt + Haut, Retour arrière)'))
        self.b_forward = QToolButton()
        self.b_forward.setIcon(st.standardIcon(QStyle.StandardPixmap.SP_ArrowForward))
        self.b_forward.setToolTip(tr('Suivant (Alt + Droite)'))
        for b, keys in ((self.b_back, 'Alt+Left'), (self.b_up, 'Alt+Up'), (self.b_forward, 'Alt+Right')):
            b.setAutoRaise(True)
            b.setIconSize(QSize(22, 22))
            b.setShortcut(QKeySequence(keys))
            row.addWidget(b)
        self.b_folders = QToolButton()                   # discret : à plat, sa liste n'est montrée qu'à la demande
        self.b_folders.setText(tr('Derniers dossiers'))
        self.b_folders.setToolTip(tr('Revenir dans un dossier où un dessin a été ouvert ou enregistré'))
        self.b_folders.setAutoRaise(True)
        self.b_folders.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        folders = QMenu(self.b_folders)
        folders.setToolTipsVisible(True)
        folders.aboutToShow.connect(lambda m=folders: self._fill_folders(m))
        self.b_folders.setMenu(folders)
        row.addWidget(self.b_folders)
        row.addSpacing(12)
        row.addWidget(QLabel(tr('Formats')))
        self.filter = QComboBox()
        for label, exts in filters():
            self.filter.addItem(f'{tr(label)} ({", ".join(e.lstrip(".") for e in exts)})', list(exts))
        try:
            self.filter.setCurrentIndex(max(0, min(self.filter.count() - 1, int(self.settings.value(FILTER_KEY, 0)))))
        except (TypeError, ValueError):
            pass
        # sa liste la plus longue imposait 1 480 px à la fenêtre : elle s'élargit s'il y a la place, sa liste reste lisible
        self.filter.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.filter.setMinimumContentsLength(22)
        self.filter.view().setMinimumWidth(self.filter.view().sizeHintForColumn(0) + 24)
        row.addWidget(self.filter, 3)
        row.addSpacing(12)
        row.addWidget(QLabel(tr('Tri')))
        self.sort = QComboBox()
        for key, label in SORTS.items():
            self.sort.addItem(tr(label), key)
        self.sort.setCurrentIndex(max(0, self.sort.findData(str(self.settings.value(SORT_KEY, 'nom') or 'nom'))))
        row.addWidget(self.sort)
        row.addSpacing(12)
        row.addWidget(QLabel(tr('Affichage')))
        self.view = QComboBox()
        for key, label in VIEWS.items():
            self.view.addItem(tr(label), key)
        row.addWidget(self.view)
        row.addStretch(1)
        self.b_full = QToolButton()
        self.b_full.setText('⛶')
        self.b_full.setAutoRaise(True)
        self.b_full.setToolTip(tr('Plein écran (F11) ; de nouveau pour revenir'))
        row.addWidget(self.b_full)
        lay.addLayout(row)
        self.panel = FileBrowserPanel(self.settings, self)
        self.panel.EXTS = tuple(self.filter.currentData())
        self.filter.currentIndexChanged.connect(self._filter_changed)
        self.sort.currentIndexChanged.connect(lambda _i: self.panel.set_sort(self.sort.currentData()))
        self.panel.sortChanged.connect(self._sort_from_columns)
        self.view.setCurrentIndex(max(0, self.view.findData(self.panel._view)))
        self.view.currentIndexChanged.connect(lambda _i: self.panel.set_view(self.view.currentData()))
        self.panel.openRequested.connect(lambda p: self.choose([p]))
        self.panel.printRequested.connect(lambda p: self.win.print_file(p))
        self.panel.insertRequested.connect(lambda p: self.choose([p], insert=True))
        self.panel.list.itemSelectionChanged.connect(self._selection_changed)
        self.panel.navigated.connect(self._nav_buttons)
        from PySide6.QtGui import QShortcut
        QShortcut(QKeySequence.StandardKey.Find, self, activated=lambda: (self.panel.search.setFocus(),
                                                                        self.panel.search.selectAll()))
        QShortcut(QKeySequence('F5'), self, activated=self.panel.refresh)            # actualiser, comme l'explorateur
        self.b_full.clicked.connect(self._toggle_full)
        QShortcut(QKeySequence('F11'), self, activated=self._toggle_full)
        self.b_back.clicked.connect(self.panel.go_back)
        self.b_up.clicked.connect(self.panel.go_up)
        self.b_forward.clicked.connect(self.panel.go_forward)
        lay.addWidget(self.panel, 1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.b_open = bb.addButton(tr('Ouvrir'), QDialogButtonBox.ButtonRole.AcceptRole)
        self.b_insert = bb.addButton(tr('Insérer dans le dessin'), QDialogButtonBox.ButtonRole.ActionRole)
        self.b_insert.setToolTip(tr('Les fichiers choisis posés dans le dessin ouvert (comme Importer)'))
        self.b_system = QPushButton(tr('Boîte de Windows…'))
        self.b_system.setToolTip(tr('La boîte Ouvrir du système (sans vignettes)'))
        bb.addButton(self.b_system, QDialogButtonBox.ButtonRole.ResetRole)
        self.b_open.clicked.connect(lambda: self.choose(self._selected_files()))
        self.b_insert.clicked.connect(lambda: self.choose(self._selected_files(), insert=True))
        self.b_system.clicked.connect(self._system_dialog)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._selection_changed()
        self.resize(1400, 860)
        self._before_full = Qt.WindowState.WindowMaximized
        saved = self.settings.value(GEOMETRY_KEY)
        if not (isinstance(saved, (QByteArray, bytes, bytearray)) and saved and self.restoreGeometry(QByteArray(saved))):
            full = self.settings.value(FULL_KEY, False) in (True, 'true')
            self.setWindowState(Qt.WindowState.WindowFullScreen if full else Qt.WindowState.WindowMaximized)
        start = pathlib.Path(folder) if folder else None
        if start is not None and os.path.isfile(start):
            start = start.parent
        if start is not None and os.path.isdir(start):
            self.panel.show_folder(start)
        else:
            self.panel.show_recents()
        self._nav_buttons()

    def _toggle_full(self) -> None:
        """⛶ et F11 : le plein écran, et retour à la taille d'avant."""
        if self.windowState() & Qt.WindowState.WindowFullScreen:
            self.setWindowState(self._before_full)
        else:
            self._before_full = self.windowState()
            self.setWindowState(Qt.WindowState.WindowFullScreen)

    def folder_choices(self) -> list[pathlib.Path]:
        """Les derniers dossiers à proposer : sans celui affiché ni ceux disparus d'un disque du
        poste ; un dossier réseau n'est pas lu (un partage absent ne bloque rien)."""
        from .recent import recent_folders
        from .symbols import is_remote
        now = getattr(self.panel, '_folder', None)
        now = os.path.normcase(str(now)) if now is not None else None
        out = []
        for f in recent_folders(self.settings):
            p = pathlib.Path(f)
            if os.path.normcase(str(p)) != now and (is_remote(p) or os.path.isdir(p)):
                out.append(p)
        return out

    def _fill_folders(self, menu) -> None:
        menu.clear()
        metrics = menu.fontMetrics()
        for p in self.folder_choices():
            text = metrics.elidedText(str(p), Qt.TextElideMode.ElideMiddle, 640).replace('&', '&&')
            a = menu.addAction(text, lambda f=p: self.panel.show_folder(f))
            a.setToolTip(str(p))
        if menu.isEmpty():
            menu.addAction(tr('Aucun autre dossier')).setEnabled(False)

    def _nav_buttons(self) -> None:
        self.b_back.setEnabled(self.panel.can_back())
        self.b_up.setEnabled(self.panel.can_up())
        self.b_forward.setEnabled(self.panel.can_forward())

    def _sort_from_columns(self, mode: str) -> None:
        self.sort.blockSignals(True)
        self.sort.setCurrentIndex(max(0, self.sort.findData(mode)))
        self.sort.blockSignals(False)

    def _filter_changed(self, i: int) -> None:
        self.settings.setValue(FILTER_KEY, int(i))
        self.panel.set_exts(self.filter.currentData())

    def _selected_files(self) -> list[str]:
        return [str(p) for p in self.panel.selected_paths(self.panel.list) if p.is_file()]

    def _selection_changed(self) -> None:
        ok = bool(self._selected_files())
        self.b_open.setEnabled(ok)
        self.b_insert.setEnabled(ok)

    def choose(self, paths, insert: bool = False) -> None:
        paths = [str(p) for p in paths if pathlib.Path(p).is_file()]
        if not paths:
            return
        self.paths, self.insert = paths, insert
        self.accept()

    def _system_dialog(self) -> None:
        from ..io import registry
        folder = getattr(self.panel, '_folder', None)
        paths, _ = QFileDialog.getOpenFileNames(self, tr('Ouvrir'), str(folder or ''), registry.filter_string())
        self.choose(paths)

    def done(self, r) -> None:                                  # noqa: D401 — API Qt
        self.settings.setValue(FULL_KEY, bool(self.windowState() & Qt.WindowState.WindowFullScreen))
        if self.isVisible():                             # jamais montrée : pas de taille à retenir
            self.settings.setValue(GEOMETRY_KEY, self.saveGeometry())
        self.panel._timer.stop()
        super().done(r)
