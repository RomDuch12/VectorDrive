"""Fenêtre « Ajouter depuis un catalogue » : les catalogues d'opérations
machine des plugins (documentation de la machine, autre logiciel,
programmes d'exemple) en arbre, une recherche, l'aperçu du bloc ; « Ajouter »
(ou double-clic) les pose dans la liste des opérations FAO."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QPushButton, QSplitter, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                               QWidget)

from ..i18n import tr

ROLE = Qt.ItemDataRole.UserRole
#: dernières opérations ajoutées (« catalogue|famille|nom »), les plus récentes d'abord
RECENT_KEY = 'fao/catalogue_recents'
RECENT_MAX = 15


def _key(e) -> str:
    return '|'.join((e.catalog, e.path, e.name))


def remember(settings, entries) -> list:
    """Opérations ajoutées mises en tête des récentes ; rend la liste."""
    if settings is None:
        return []
    old = settings.value(RECENT_KEY, []) or []
    old = [old] if isinstance(old, str) else list(old)
    new = [_key(e) for e in entries if e.catalog != 'Fichier']
    out = list(dict.fromkeys(new + [k for k in old if k not in new]))[:RECENT_MAX]
    settings.setValue(RECENT_KEY, out)
    return out


class CatalogDialog(QDialog):
    def __init__(self, parent=None, catalogs=None, settings=None):
        super().__init__(parent)
        from .fit import release
        release(self)                                    # fermée : détruite, pas gardée par son parent
        self.settings = settings if settings is not None else getattr(getattr(parent, 'win', None), 'settings', None)
        from ..cam import catalog as C
        self.setWindowTitle(tr('Ajouter depuis un catalogue'))
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.setSizeGripEnabled(True)
        self.resize(1000, 640)
        self.catalogs = catalogs if catalogs is not None else C.catalogs()
        self.chosen: list = []
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr('Rechercher (nom, famille, aide)…'))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        top.addWidget(self.search, 1)
        b = QPushButton(tr('Fichier…'))
        b.setToolTip(tr('Prendre un fichier texte (programme machine, extrait) comme bloc de programme'))
        b.clicked.connect(lambda: self.add_file())
        top.addWidget(b)
        lay.addLayout(top)
        split = QSplitter(Qt.Orientation.Horizontal)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.tree.currentItemChanged.connect(lambda cur, _p: self._preview(cur))
        self.tree.itemDoubleClicked.connect(lambda it, _c: it.data(0, ROLE) is not None and self.accept())
        split.addWidget(self.tree)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self.title = QLabel('')
        f = self.title.font()
        f.setBold(True)
        self.title.setFont(f)
        rl.addWidget(self.title)
        self.note = QLabel('')
        self.note.setWordWrap(True)
        self.note.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        rl.addWidget(self.note)
        self.doc_button = QPushButton(tr('Documentation'))
        self.doc_button.setToolTip(tr('Le document du poste qui décrit l\'opération, ouvert à sa page'))
        self.doc_button.setVisible(False)
        self.doc_button.clicked.connect(lambda: self.open_doc())
        rl.addWidget(self.doc_button)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFont(QFont('Consolas', 9))
        rl.addWidget(self.preview, 1)
        split.addWidget(right)
        split.setSizes([380, 620])
        lay.addWidget(split, 1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText(tr('Ajouter'))
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._fill()

    # --- arbre --------------------------------------------------------------------------
    def _fill(self) -> None:
        self.tree.clear()
        if not self.catalogs:
            it = QTreeWidgetItem([tr('Aucun catalogue : ils viennent des plugins (documentation de la machine, '
                                     'autres logiciels). « Fichier… » prend un fichier texte comme bloc.')])
            self.tree.addTopLevelItem(it)
            return
        recent = self.settings.value(RECENT_KEY, []) if self.settings is not None else []
        recent = [recent] if isinstance(recent, str) else list(recent or [])
        by_key = {_key(e): e for _l, entries, _p in self.catalogs for e in entries}
        found = [by_key[k] for k in recent if k in by_key]
        if found:                                        # les dernières ajoutées, en tête
            top = QTreeWidgetItem([tr('★ Récents')])
            self.tree.addTopLevelItem(top)
            for e in found:
                it = QTreeWidgetItem([e.name])
                it.setData(0, ROLE, e)
                it.setToolTip(0, f'{e.catalog} › {e.path}' if e.path else e.catalog)
                top.addChild(it)
            top.setExpanded(True)
        for label, entries, problem in self.catalogs:
            top = QTreeWidgetItem([tr(label) + (f' — {problem}' if problem else f' ({len(entries)})')])
            self.tree.addTopLevelItem(top)
            nodes = {}
            for e in entries:
                parent = top
                key = ''
                for part in [p for p in str(e.path or '').split('/') if p]:
                    key += '/' + part
                    if key not in nodes:
                        nodes[key] = QTreeWidgetItem([part])
                        parent.addChild(nodes[key])
                    parent = nodes[key]
                it = QTreeWidgetItem([e.name])
                it.setData(0, ROLE, e)
                it.setToolTip(0, e.note or e.name)
                parent.addChild(it)
            top.setExpanded(len(self.catalogs) == 1)

    def entries(self) -> list:
        out = []

        def walk(it):
            e = it.data(0, ROLE)
            if e is not None:
                out.append((it, e))
            for i in range(it.childCount()):
                walk(it.child(i))
        for i in range(self.tree.topLevelItemCount()):
            walk(self.tree.topLevelItem(i))
        return out

    def _filter(self, text: str) -> int:
        """Entrées qui contiennent le texte (nom, rangement, aide) ; rend leur nombre."""
        words = text.lower().split()
        shown = 0

        def visit(it) -> bool:
            e = it.data(0, ROLE)
            if e is not None:
                hay = ' '.join((e.name, e.path, e.note, e.catalog)).lower()
                ok = all(w in hay for w in words)
            else:
                ok = False
                for i in range(it.childCount()):
                    ok = visit(it.child(i)) or ok
            it.setHidden(bool(words) and not ok)
            if words and ok and e is None:
                it.setExpanded(True)
            return ok
        for i in range(self.tree.topLevelItemCount()):
            visit(self.tree.topLevelItem(i))
        for it, _e in self.entries():
            shown += not it.isHidden()
        return shown

    def _preview(self, it) -> None:
        e = it.data(0, ROLE) if it is not None else None
        self.doc_button.setVisible(bool(e is not None and e.doc))
        if e is not None and e.doc:
            self.doc_button.setText(tr('Documentation, p. {0}').format(e.page) if e.page else tr('Documentation'))
        if e is None:
            self.title.setText('')
            self.note.setText('')
            self.preview.setPlainText('')
            return
        self.title.setText(e.name)
        extra = ''
        if e.names:
            extra = tr('Paramètres : {0}').format(', '.join(
                f'{{p{k}}} {n}' for k, n in enumerate(e.names[:6], start=1)))
        self.note.setText('\n'.join(x for x in (e.note, extra) if x))
        try:
            text = e.lines() if e.instruction == 'bloc' else tr('Instruction : {0}').format(e.instruction)
        except Exception as ex:                        # fichier disparu…
            text = tr('Illisible : {0}').format(ex)
        self.preview.setPlainText(text[:20000])

    def open_doc(self, entry=None):
        """Document de l'opération choisie, à sa page ; rend la fenêtre (None : pas de document)."""
        import os
        e = entry or next(iter(self.selected_entries()), None)
        if e is None or not e.doc or not os.path.isfile(e.doc):
            self.note.setText(tr('Document introuvable sur ce poste : {0}').format(e.doc if e else ''))
            return None
        win = getattr(self, '_doc_window', None)
        if win is None:
            win = self._doc_window = self._take_doc_window()
        win.show_page(e.doc, e.page)
        return win

    def _take_doc_window(self):
        """La fenêtre du document : celle laissée par un catalogue précédent (gardée par la fenêtre principale), sinon
        une nouvelle ; enfant de ce catalogue tant qu'il est ouvert, rendue à la fenêtre principale à sa fermeture."""
        from shiboken6 import isValid
        host = self.parentWidget().window() if self.parentWidget() is not None else None
        win = getattr(host, '_vd_doc_window', None)
        if win is not None and isValid(win):
            _reparent(win, self)
        else:
            win = DocWindow(self)
        if host is not None:
            host._vd_doc_window = win
            self.finished.connect(lambda _r=0, w=win, h=host: _reparent(w, h))
        return win

    # --- choix ----------------------------------------------------------------------------
    def selected_entries(self) -> list:
        sel = [it.data(0, ROLE) for it in self.tree.selectedItems() if it.data(0, ROLE) is not None]
        cur = self.tree.currentItem()
        if not sel and cur is not None and cur.data(0, ROLE) is not None:
            sel = [cur.data(0, ROLE)]
        return sel

    def add_file(self, path: str | None = None) -> bool:
        from ..cam import catalog as C
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, tr('Fichier pris comme bloc de programme'), '',
                                                  tr('Programmes et textes (*.simpl *.nc *.h *.txt *.iso *.tap);;'
                                                     'Tous les fichiers (*)'))
            if not path:
                return False
        try:
            e = C.file_entry(path)
        except (OSError, ValueError) as ex:
            self.note.setText(tr('Fichier refusé : {0}').format(ex))
            return False
        self.chosen = [e]
        super().accept()
        return True

    def accept(self) -> None:
        self.chosen = self.selected_entries()
        if self.chosen:
            remember(self.settings, self.chosen)
            super().accept()


def _reparent(win, parent) -> None:
    """`win` (fenêtre de document) confiée à `parent`, sans bouger ni se fermer si elle était ouverte."""
    from shiboken6 import isValid
    if not (isValid(win) and isValid(parent)) or win.parentWidget() is parent:
        return
    shown, geo = win.isVisible(), win.geometry()
    win.setParent(parent, win.windowFlags())
    win.setGeometry(geo)
    if shown:
        win.show()


class DocWindow(QDialog):
    """Un document PDF du poste, ouvert à une page (QtPdf, sans autre logiciel)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from PySide6.QtPdf import QPdfDocument
        from PySide6.QtPdfWidgets import QPdfView
        self.vd_keep = True                              # réemployée : pas détruite à la fermeture
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.setSizeGripEnabled(True)
        self.resize(900, 1000)
        self.pdf = QPdfDocument(self)
        self.view = QPdfView(self)
        self.view.setDocument(self.pdf)
        self.view.setPageMode(QPdfView.PageMode.MultiPage)
        self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.view)
        self.path = ''

    def show_page(self, path: str, page: int = 0) -> int:
        """Ouvre `path` (une fois) à la page `page` (1 = la première) ; rend la page montrée (0 : aucune)."""
        from PySide6.QtCore import QPointF
        if path != self.path:
            self.pdf.load(path)
            self.path = path
        n = self.pdf.pageCount()
        if n <= 0:
            return 0
        k = min(max(1, int(page or 1)), n)
        import os
        self.setWindowTitle(f'{os.path.basename(path)} — p. {k}')
        self.show()
        self.raise_()
        from PySide6.QtCore import QTimer
        jump = lambda: self.view.pageNavigator().jump(k - 1, QPointF(), 0)      # noqa: E731
        jump()
        QTimer.singleShot(0, jump)                       # une fois la vue mise en page
        return k
