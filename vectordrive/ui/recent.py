"""Fichiers récents en grand menu : détails de chaque fichier (dossier,
format, taille, date), « Ouvrir dans l'explorateur », aperçu du fichier
choisi. Les aperçus (Récents et Ouvrir) sont coupés par défaut — lire chaque
dessin coûte — et se rallument pour la séance seulement (`previews_on`)."""
from __future__ import annotations

import datetime
import os
import pathlib

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from ..i18n import tr

PREVIEW = 220

#: derniers dossiers proposés par Ouvrir, du plus récent au plus ancien
FOLDERS_KEY, FOLDERS_MAX = 'fichiers/dossiers', 10
#: taille retenue de la boîte Ouvrir avec aperçus
DIALOG_KEY = 'ouvrir/fenetre_apercus'
#: aperçus des fichiers allumés pour la séance (jamais enregistré)
_state = {'previews': False}


def previews_on() -> bool:
    return _state['previews']


def set_previews(on: bool) -> None:
    _state['previews'] = bool(on)


def _as_list(value) -> list:
    return [value] if isinstance(value, str) else list(value or [])


def recent_folders(settings) -> list[str]:
    """Les derniers dossiers, du plus récent au plus ancien : ceux notés à chaque ouverture ou
    enregistrement, puis ceux des fichiers récents. Le disque n'est pas lu."""
    notes = _as_list(settings.value(FOLDERS_KEY, []))
    notes += [str(pathlib.Path(p).parent) for p in _as_list(settings.value('fichiers/recents', [])) if p]
    out, seen = [], set()
    for f in notes:
        key = os.path.normcase(str(f))
        if f and key not in seen:
            seen.add(key)
            out.append(str(f))
    return out[:FOLDERS_MAX]


def note_folder(settings, path) -> None:
    """Le dossier du fichier `path` en tête des derniers dossiers."""
    folder = str(pathlib.Path(path).parent)
    rest = [f for f in recent_folders(settings) if os.path.normcase(f) != os.path.normcase(folder)]
    settings.setValue(FOLDERS_KEY, [folder] + rest[:FOLDERS_MAX - 1])


def human_size(n: int) -> str:
    for unit in ('o', 'Ko', 'Mo', 'Go'):
        if n < 1024 or unit == 'Go':
            return f'{n} {unit}' if unit == 'o' else f'{n:.1f} {unit}'.replace('.', ',')
        n /= 1024
    return str(n)


def file_details(path: str) -> dict:
    """Nom, dossier, format, taille et date de modification d'un fichier ;
    `exists` False s'il a disparu (taille et date vides)."""
    from ..io import registry
    p = pathlib.Path(path)
    fmt = registry.by_extension(p)
    d = {'path': str(p), 'name': p.name, 'folder': str(p.parent),
         'format': fmt.label if fmt is not None else p.suffix.upper().lstrip('.'),
         'exists': True, 'size': '', 'modified': '', 'mtime': 0.0}
    from .symbols import is_remote
    if is_remote(p):                                     # réseau : rien demandé au partage (hors d'atteinte ?)
        return d
    d['exists'] = p.is_file()
    if d['exists']:
        st = p.stat()
        d['size'] = human_size(st.st_size)
        d['mtime'] = st.st_mtime
        d['modified'] = datetime.datetime.fromtimestamp(st.st_mtime).strftime('%d/%m/%Y %H:%M')
    return d


def preview_pixmap(path: str, size: int = PREVIEW) -> QPixmap | None:
    """Aperçu d'un dessin (ses contours), gardé pour la séance."""
    from .symbols import _PREVIEWS, preview_image
    key = (str(path), size)
    if key not in _PREVIEWS:
        _PREVIEWS[key] = preview_image(path, size)
    img = _PREVIEWS[key]
    return QPixmap.fromImage(img) if img is not None else None


def cached_preview(path: str, size: int = PREVIEW):
    """(gardé ?, QPixmap ou None) sans rien calculer."""
    from .symbols import _PREVIEWS
    key = (str(path), size)
    if key not in _PREVIEWS:
        return False, None
    img = _PREVIEWS[key]
    return True, (QPixmap.fromImage(img) if img is not None else None)


#: au-delà (octets), l'aperçu d'un récent est calculé en fond (un gros DXF figeait la liste)
SYNC_MAX = 1_500_000


def preview_pixmap_image(path: str, size: int = PREVIEW):
    """Aperçu (QImage) d'un dessin, dans le fil des aperçus des récents."""
    from .symbols import preview_image
    return preview_image(path, size)


class PreviewToggle(QPushButton):
    """Bouton « Aperçus » : allume ou coupe les aperçus pour la séance."""
    def __init__(self, parent=None):
        super().__init__(tr('Aperçus'), parent)
        self.setCheckable(True)
        self.setChecked(previews_on())
        self.setToolTip(tr('Montrer un aperçu du fichier choisi (pour cette séance ; coupé par défaut, '
                           'plus rapide)'))
        self.toggled.connect(set_previews)


class RecentPanel(QWidget):
    """Contenu du grand menu Récents : liste détaillée, aperçu, boutons."""
    openRequested = Signal(str)
    listChanged = Signal(list)

    COLS = ('name', 'folder', 'format', 'size', 'modified')

    def __init__(self, files: list[str], parent=None):
        super().__init__(parent)
        self.setObjectName('recentPanel')
        self.files = list(files)
        top = QHBoxLayout(self)
        top.setContentsMargins(8, 8, 8, 8)
        left = QVBoxLayout()
        title = QLabel(tr('Fichiers récents'))
        f = title.font()
        f.setBold(True)
        f.setPointSizeF(f.pointSizeF() * 1.2)
        title.setFont(f)
        left.addWidget(title)
        self.tree = QTreeWidget()
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setHeaderLabels([tr('Nom'), tr('Dossier'), tr('Format'), tr('Taille'), tr('Modifié le')])
        h = self.tree.header()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for i in (2, 3, 4):
            h.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.itemDoubleClicked.connect(lambda it, _c: self._open(it))
        self.tree.currentItemChanged.connect(lambda *_: self._current_changed())
        left.addWidget(self.tree, 1)
        row = QHBoxLayout()
        self.b_open = QPushButton(tr('Ouvrir'))
        self.b_open.clicked.connect(lambda: self._open(self.tree.currentItem()))
        self.b_reveal = QPushButton(tr('Ouvrir dans l\'explorateur'))
        self.b_reveal.setToolTip(tr('Montrer le fichier dans son dossier'))
        self.b_reveal.clicked.connect(self.reveal_current)
        self.b_remove = QPushButton(tr('Retirer de la liste'))
        self.b_remove.clicked.connect(self.remove_current)
        self.b_clear = QPushButton(tr('Vider la liste'))
        self.b_clear.clicked.connect(self.clear)
        self.b_previews = PreviewToggle()
        self.b_previews.toggled.connect(lambda _on: self._current_changed())
        for b in (self.b_open, self.b_reveal, self.b_remove, self.b_clear):
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(self.b_previews)
        left.addLayout(row)
        top.addLayout(left, 1)
        self.preview = QLabel()
        self.preview.setObjectName('recentPreview')
        self.preview.setFixedSize(QSize(PREVIEW + 8, PREVIEW + 8))
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setWordWrap(True)
        top.addWidget(self.preview, 0, Qt.AlignmentFlag.AlignTop)
        self.fill()

    def fill(self) -> None:
        self.tree.clear()
        for p in self.files:
            d = file_details(p)
            it = QTreeWidgetItem([d[k] for k in self.COLS])
            it.setData(0, Qt.ItemDataRole.UserRole, d['path'])
            it.setToolTip(0, d['path'])
            it.setToolTip(1, d['folder'])
            if not d['exists']:                          # grisé, mais encore choisi (pour le retirer)
                for i in range(len(self.COLS)):
                    it.setForeground(i, QColor(140, 140, 140))
                it.setText(3, tr('introuvable'))
            self.tree.addTopLevelItem(it)
        if self.tree.topLevelItemCount():
            self.tree.setCurrentItem(self.tree.topLevelItem(0))
        self._current_changed()

    def current_path(self) -> str | None:
        it = self.tree.currentItem()
        return it.data(0, Qt.ItemDataRole.UserRole) if it is not None else None

    def _current_changed(self) -> None:
        p = self.current_path()
        ok = p is not None and pathlib.Path(p).is_file()
        self.b_open.setEnabled(ok)
        self.b_reveal.setEnabled(p is not None and pathlib.Path(p).parent.exists())
        self.b_remove.setEnabled(p is not None)
        self.b_clear.setEnabled(bool(self.files))
        self.preview.setVisible(previews_on())
        if not previews_on():
            return
        if not ok:
            self._show_preview(None, p)
            return
        known, pm = cached_preview(p)
        if known:
            self._show_preview(pm, p)
            return
        try:
            small = pathlib.Path(p).stat().st_size < SYNC_MAX
        except OSError:
            small = True
        if small:                                        # petit fichier : aussitôt (quelques centièmes)
            self._show_preview(preview_pixmap(p), p)
            return
        # aperçu calculé dans un fil : un gros dessin ne fige plus la liste des récents
        from concurrent.futures import ThreadPoolExecutor
        from PySide6.QtCore import QTimer
        if getattr(self, '_ppool', None) is None:
            self._ppool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='apercu_recent')
            self._ptimer = QTimer(self)
            self._ptimer.setInterval(40)
            self._ptimer.timeout.connect(self._preview_ready)
        self.preview.setPixmap(QPixmap())
        self.preview.setText(tr('Aperçu…'))
        self._pjob = (p, self._ppool.submit(preview_pixmap_image, p))
        self._ptimer.start()

    def _show_preview(self, pm, p) -> None:
        if pm is not None:
            self.preview.setPixmap(pm)
        else:
            self.preview.setPixmap(QPixmap())
            self.preview.setText(tr('Pas d\'aperçu') if p else '')

    def _preview_ready(self) -> None:
        job = getattr(self, '_pjob', None)
        if job is None or not job[1].done():
            return
        self._ptimer.stop()
        self._pjob = None
        p, fut = job
        try:
            img = fut.result()
        except Exception:                                # noqa: BLE001 — dessin illisible : pas d'aperçu
            img = None
        from .symbols import _PREVIEWS
        _PREVIEWS[(str(p), PREVIEW)] = img
        if self.current_path() == p:                     # toujours le même fichier choisi
            self._show_preview(QPixmap.fromImage(img) if img is not None else None, p)

    def _open(self, it) -> None:
        if it is None:
            return
        p = it.data(0, Qt.ItemDataRole.UserRole)
        if pathlib.Path(p).is_file():
            self.openRequested.emit(p)

    def reveal_current(self) -> bool:
        from .reveal import reveal
        p = self.current_path()
        return bool(p) and reveal(p)

    def remove_current(self) -> None:
        p = self.current_path()
        if p is None:
            return
        self.files = [f for f in self.files if f != p]
        self.listChanged.emit(list(self.files))
        self.fill()

    def clear(self) -> None:
        self.files = []
        self.listChanged.emit([])
        self.fill()


def open_file_dialog(parent, title: str, folder: str, filters: str) -> QFileDialog:
    """Boîte « Ouvrir » (plusieurs fichiers). Aperçus coupés : la boîte du
    système ; allumés : celle de Qt, avec l'aperçu du fichier pointé et le
    bouton pour les couper."""
    dlg = QFileDialog(parent, title, folder, filters)
    dlg.setFileMode(QFileDialog.FileMode.ExistingFiles)
    dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
    if not previews_on():
        return dlg
    dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    side = QWidget()
    side.setObjectName('openPreview')
    box = QVBoxLayout(side)
    box.setContentsMargins(4, 0, 0, 0)
    label = QLabel()
    label.setFixedSize(QSize(PREVIEW + 8, PREVIEW + 8))
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setWordWrap(True)
    toggle = PreviewToggle()
    box.addWidget(label)
    box.addWidget(toggle)
    box.addStretch(1)

    def show(path: str) -> None:
        if not toggle.isChecked():
            label.clear()
            return
        pm = preview_pixmap(path) if path and pathlib.Path(path).is_file() else None
        if pm is not None:
            label.setPixmap(pm)
        else:
            label.setPixmap(QPixmap())
            label.setText(tr('Pas d\'aperçu') if path else '')

    dlg.currentChanged.connect(show)
    toggle.toggled.connect(lambda on: show(dlg.selectedFiles()[0] if on and dlg.selectedFiles() else ''))
    lay = dlg.layout()
    if lay is not None and hasattr(lay, 'addWidget') and hasattr(lay, 'rowCount'):
        lay.addWidget(side, 0, lay.columnCount(), lay.rowCount(), 1)
    dlg.preview_label = label
    dlg.preview_show = show
    dlg.setWindowState(Qt.WindowState.WindowMaximized)          # comme le navigateur : agrandie
    return dlg
