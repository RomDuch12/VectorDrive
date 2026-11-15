"""Reconnaître une police (demande du 14/11 : « Bouton reconnaissance police dans ruban texte mode simpl peut pointer
sur la dernière capture d'écran et reconnaitre dans le png, petite explication simple du calcul que ça engendre la
première fois pour user inexperimenté »).

La fenêtre compare des lettres aux polices du poste (`core.fontmatch`) : celles des formes sélectionnées (lettres en
courbes), ou celles d'une image — la dernière capture d'écran d'office, l'image du presse-papiers, ou un fichier au
choix. Les polices les plus proches sont listées ; un double clic (ou « Appliquer ») met la police aux textes
sélectionnés, sinon aux prochains textes.
"""
from __future__ import annotations

import os
import pathlib
import threading

from PySide6.QtCore import QEvent, QObject, QStandardPaths, Qt, Signal
from PySide6.QtGui import QGuiApplication, QImage, QPixmap
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QPushButton, QSizePolicy, QSpinBox,
                               QVBoxLayout)

from ..i18n import tr

#: sous-dossiers d'Images où Windows range les captures d'écran (selon la langue et OneDrive)
SHOT_FOLDERS = ('Screenshots', 'Captures d’écran', "Captures d'écran")
IMAGE_EXT = ('.png', '.jpg', '.jpeg', '.bmp', '.webp')
#: plus grand côté de l'image comparée (pixels) : au-delà, elle est réduite
MAX_SIDE = 2400
#: ce que le calcul rend quand il n'a pas de polices à lister : le message
SAID = {'chargee': 'Image trop chargée pour y lire des lettres : cadrez la capture sur le texte',
        'formes': 'Aucune forme trouvée dans cette image',
        'lettres': 'Aucune lettre reconnue : il faut des lettres nettes, bien séparées, sur fond uni',
        'polices': 'Aucune police à comparer'}


def screenshot_dirs() -> list:
    """Les dossiers où chercher la dernière capture d'écran : celui de `VECTORDRIVE_SCREENSHOTS` s'il est donné,
    sinon les dossiers de captures de Windows (Images, OneDrive)."""
    forced = os.environ.get('VECTORDRIVE_SCREENSHOTS')
    if forced:
        return [pathlib.Path(forced)]
    roots = [pathlib.Path(p) for p in QStandardPaths.standardLocations(QStandardPaths.StandardLocation.PicturesLocation)]
    home = pathlib.Path.home()
    roots += [home / 'Pictures', home / 'Images', home / 'OneDrive' / 'Pictures', home / 'OneDrive' / 'Images']
    out = []
    for r in roots:
        for name in SHOT_FOLDERS:
            d = r / name
            if d not in out and d.is_dir():
                out.append(d)
    return out


def last_screenshot() -> pathlib.Path | None:
    """La capture d'écran la plus récente (fichier image), ou None."""
    best, when = None, -1.0
    for d in screenshot_dirs():
        try:
            for f in d.iterdir():
                if f.suffix.lower() in IMAGE_EXT and f.is_file():
                    t = f.stat().st_mtime
                    if t > when:
                        best, when = f, t
        except OSError:
            continue
    return best


def gray_of(image: QImage):
    """L'image en niveaux de gris 0…1 (tableau lignes × colonnes), réduite si elle dépasse `MAX_SIDE` ; un dessin sur
    fond transparent est posé sur un fond uni (`dialogs.qimage_gray`). None pour une image nulle."""
    if image is None or image.isNull():
        return None
    from .dialogs import qimage_gray
    return qimage_gray(image, MAX_SIDE)


class _Relay(QObject):
    progress = Signal(object, int, int)
    done = Signal(object, object)


class FontRecognizeDialog(QDialog):
    """Reconnaître une police d'après des lettres en courbes ou une image. `win` : la fenêtre principale ; `start` : la
    source d'emblée ('selection', 'image', 'presse-papiers') ; `docked` : le panneau de colonne qui la porte (« Fermer »
    le ferme ; Échap arrête seulement la reconnaissance)."""

    def __init__(self, win, start: str | None = None, docked=None):
        super().__init__(win)
        self.docked = docked
        self.setObjectName('fontRecognize')
        if docked is not None:
            self.setWindowFlags(Qt.WindowType.Widget)     # dans son panneau, pas une fenêtre à part
        from ..core import fontmatch
        from .fontlist import proposal_count
        self.win = win
        self.setWindowTitle(tr('Reconnaître une police'))
        self.results: list = []
        self._token = None
        self._thread = None
        self._loaded = (None, None)                       # (clé du fichier, image) : lu une fois
        self._relay = _Relay(self)
        self._relay.progress.connect(self._progress)
        self._relay.done.connect(self._done)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.source = QComboBox()
        self.source.addItem(tr('Les lettres en courbes sélectionnées'), 'selection')
        self.source.addItem(tr('Une image : la dernière capture d’écran, ou un fichier'), 'image')
        self.source.addItem(tr('L’image du presse-papiers'), 'presse-papiers')
        form.addRow(tr('Lettres à reconnaître'), self.source)
        row = QHBoxLayout()
        self.path = QLineEdit()
        self.path.setToolTip(tr('L’image où lire les lettres : une capture d’écran d’un texte net, sur fond uni'))
        row.addWidget(self.path, 1)
        self.last_button = QPushButton(tr('Dernière capture'))
        self.last_button.setToolTip(tr('La capture d’écran la plus récente du dossier des captures de Windows'))
        self.last_button.clicked.connect(lambda _=False: self.use_last_screenshot())
        row.addWidget(self.last_button)
        self.browse_button = QPushButton(tr('Parcourir…'))
        self.browse_button.clicked.connect(lambda _=False: self.browse())
        row.addWidget(self.browse_button)
        for b in (self.last_button, self.browse_button):   # Entrée dans le champ ne les déclenche pas
            b.setAutoDefault(False)
        self.path_row = row
        form.addRow(tr('Image'), row)
        self.count = QSpinBox()
        self.count.setRange(1, 50)
        self.count.setValue(proposal_count(getattr(win, 'settings', None)))
        form.addRow(tr('Polices proposées'), self.count)
        lay.addLayout(form)
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(90)
        lay.addWidget(self.preview)
        self.explain = QLabel(tr(
            'Comment ça marche : VectorDrive dessine les lettres de chaque police installée et les compare aux vôtres. '
            'La première fois, ce dessin prend de quelques secondes à une minute selon le nombre de polices ; il est '
            'gardé, et les fois suivantes la réponse est presque immédiate.'))
        self.explain.setWordWrap(True)
        lay.addWidget(self.explain)
        self.advice = QLabel(tr('Pour une image : un texte net, sur fond uni, cadré au plus près des lettres.'))
        self.advice.setWordWrap(True)
        lay.addWidget(self.advice)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda _it: self.apply())
        lay.addWidget(self.list, 1)
        self.status = QLabel('')
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        bb = QDialogButtonBox()
        self.go = bb.addButton(tr('Reconnaître'), QDialogButtonBox.ButtonRole.ActionRole)
        self.go.clicked.connect(lambda _=False: self._go_or_stop())
        self.apply_button = bb.addButton(tr('Appliquer'), QDialogButtonBox.ButtonRole.ApplyRole)
        self.apply_button.setToolTip(tr('Mettre la police choisie aux textes sélectionnés, sinon aux prochains textes'))
        self.apply_button.clicked.connect(lambda _=False: self.apply())
        self.apply_button.setEnabled(False)
        close = bb.addButton(QDialogButtonBox.StandardButton.Close)
        close.clicked.connect(self.reject)
        for b in (self.apply_button, close):
            b.setAutoDefault(False)
        self.go.setAutoDefault(True)
        self.go.setDefault(True)                           # Entrée : reconnaître
        lay.addWidget(bb)
        self.source.currentIndexChanged.connect(lambda _i: self._source_changed())
        self.path.editingFinished.connect(self._show_preview)
        # la première fois (aucune forme de police gardée) : l'explication est mise en avant
        try:
            first = not any(fontmatch.cache_dir().iterdir())
        except OSError:
            first = True
        self.explain.setStyleSheet('font-weight: bold;' if first else '')
        if docked is not None:                            # dans une colonne : à sa largeur, pas plus large
            self.preview.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            self.source.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            self.source.setMinimumContentsLength(16)
            docked.visibilityChanged.connect(lambda on: None if on or not docked.isHidden() else self.stop())
        self.renew(start)
        if docked is None:
            self.resize(560, 660)

    def renew(self, start: str | None = None) -> None:
        """La source d'emblée (`start`, sinon selon ce qui est là) et l'image sur la dernière capture : à l'ouverture,
        et chaque fois que le bouton remontre le panneau."""
        if self._token is not None:
            self.stop()
        self.status.setText('')
        # le champ de l'image pointe toujours sur la dernière capture ; d'office : les lettres en courbes sélectionnées
        # s'il y en a, sinon cette capture, sinon l'image du presse-papiers
        shot = last_screenshot()
        if shot is not None:
            self.path.setText(str(shot))
        want = start or ('selection' if self.selection_paths() else 'image')
        if want == 'image' and shot is None and not self.clipboard_image().isNull():
            want = 'presse-papiers'
        self.source.setCurrentIndex(max(0, self.source.findData(want)))
        self._source_changed()
        if want == 'image' and shot is None:
            self.status.setText(tr('Aucune capture d’écran trouvée : choisissez une image avec « Parcourir… »'))

    # --- les sources -------------------------------------------------------------------------------------------
    def selection_paths(self) -> list:
        """Les tracés des formes sélectionnées, groupes ouverts ; les textes n'en sont pas (leur police est connue)."""
        from ..core.document import Text
        from .canvas import _leaves, item_path
        canvas = getattr(self.win, 'canvas', None)
        return [p for p in (item_path(it) for it in _leaves(getattr(canvas, 'selection', None) or [])
                            if not isinstance(it, Text)) if p]

    def clipboard_image(self) -> QImage:
        return QGuiApplication.clipboard().image()

    def use_last_screenshot(self) -> bool:
        """Le champ de l'image pointe sur la dernière capture d'écran ; faux s'il n'y en a pas."""
        f = last_screenshot()
        if f is None:
            self.status.setText(tr('Aucune capture d’écran trouvée : choisissez une image avec « Parcourir… »'))
            return False
        self.path.setText(str(f))
        if self.source.currentData() != 'image':
            self.source.setCurrentIndex(self.source.findData('image'))
        self._show_preview()
        return True

    def browse(self) -> None:
        start = self.path.text().strip() or next((str(d) for d in screenshot_dirs()), '')
        path, _ = QFileDialog.getOpenFileName(self, tr('Image où reconnaître une police'), start,
                                              tr('Images ({0})').format(' '.join('*' + e for e in IMAGE_EXT)))
        if path:
            self.path.setText(path)
            self.source.setCurrentIndex(self.source.findData('image'))
            self._show_preview()

    def _file_image(self) -> QImage:
        """L'image du fichier choisi, lue une fois (photo redressée, grande image réduite : `io.raster.load_image`) ;
        nulle si elle ne se lit pas."""
        path = self.path.text().strip()
        if not path:
            return QImage()
        try:
            key = (path, os.stat(path).st_mtime_ns)
        except OSError:
            return QImage()
        if self._loaded[0] != key:
            from ..io.raster import load_image
            try:
                img = load_image(path, MAX_SIDE * MAX_SIDE)[0]
            except (ValueError, OSError):
                img = QImage()
            self._loaded = (key, img)
        return self._loaded[1]

    def image(self) -> QImage:
        """L'image de la source choisie (nulle : rien)."""
        kind = self.source.currentData()
        if kind == 'presse-papiers':
            return self.clipboard_image()
        if kind == 'image':
            return self._file_image()
        return QImage()

    def _source_changed(self) -> None:
        kind = self.source.currentData()
        for i in range(self.path_row.count()):
            w = self.path_row.itemAt(i).widget()
            if w is not None:
                w.setEnabled(kind == 'image')
        self._show_preview()

    def _show_preview(self) -> None:
        img = self.image()
        if img.isNull():
            self.preview.setPixmap(QPixmap())
            kind = self.source.currentData()
            if kind == 'selection':
                self.preview.setText(tr('{0} tracé(s) sélectionné(s)').format(len(self.selection_paths())))
            elif kind == 'image' and self.path.text().strip():
                self.preview.setText(tr('Image illisible'))
            else:
                self.preview.setText(tr('Pas d’image'))
            return
        wide = max(120, self.preview.width() - 4) if self.docked is not None else 520
        self.preview.setPixmap(QPixmap.fromImage(img).scaled(wide, 160, Qt.AspectRatioMode.KeepAspectRatio,
                                                             Qt.TransformationMode.SmoothTransformation))

    # --- la reconnaissance ---------------------------------------------------------------------------------------
    def names(self) -> list:
        """Les polices comparées : celles de la liste des polices, sous leur nom affiché et dans son ordre."""
        box = getattr(getattr(self.win, 'textbar', None), 'font', None)
        if box is not None and hasattr(box, 'itemText'):
            got = [box.itemText(i) for i in range(box.count())]
            if any(got):
                return [n for n in got if n]
        from PySide6.QtGui import QFontDatabase
        from ..core import fonts
        qt = list(QFontDatabase.families())
        return sorted(qt + fonts.unlisted_families(qt), key=str.lower)

    def recognize(self, wait: bool = False) -> None:
        """Les polices les plus proches des lettres de la source, calculées dans un fil (la lecture des formes de
        l'image aussi) ; `wait` : attendre la fin (essais)."""
        from ..core import fontmatch
        kind = self.source.currentData()
        paths, gray = [], None
        if kind == 'selection':
            paths = self.selection_paths()
            if not paths:
                self.status.setText(tr('Sélectionnez d’abord des lettres en courbes dans le dessin'))
                return
        else:
            img = self.image()
            if img.isNull():
                self.status.setText(tr('Image illisible : choisissez-en une autre avec « Parcourir… »')
                                    if kind == 'image' and self.path.text().strip() else tr('Pas d’image'))
                return
            gray = gray_of(img)
        names, count = self.names(), self.count.value()
        st = getattr(self.win, 'settings', None)
        if st is not None:
            from .fontlist import COUNT_KEY
            st.setValue(COUNT_KEY, int(count))
        token = object()
        self._token = token
        self.list.clear()
        self.results = []
        self.apply_button.setEnabled(False)
        self.go.setText(tr('Arrêter'))
        self.status.setText(tr('Reconnaissance…'))
        relay = self._relay

        def emit(sig, *args):
            try:
                sig.emit(*args)
            except RuntimeError:                       # la fenêtre n'est plus là
                pass

        def work():
            cancel = lambda: self._token is not token  # noqa: E731
            try:
                found = paths
                if gray is not None:
                    try:
                        found = fontmatch.image_paths(gray)
                    except ValueError:                 # photo, trame : trop de détails pour y lire des lettres
                        found = None
                if found is None:
                    res = 'chargee'
                elif not found:
                    res = 'formes'
                else:
                    sel = fontmatch.selection_images(found)
                    if not len(sel):
                        res = 'lettres'
                    else:
                        res = fontmatch.rank(found, names, count,
                                             progress=lambda i, n: emit(relay.progress, token, i, n),
                                             cancel=cancel, sel=sel) or 'polices'
            except Exception as e:                     # noqa: BLE001 — dit dans la fenêtre
                res = e
            if not cancel():
                emit(relay.done, token, res)
        self._thread = threading.Thread(target=work, daemon=True, name='reconnaissance des polices')
        self._thread.start()
        if wait:
            self._thread.join()
            QGuiApplication.processEvents()

    def _go_or_stop(self) -> None:
        if self._token is not None:
            self.stop()
            self.status.setText(tr('Reconnaissance arrêtée'))
        else:
            self.recognize()

    def stop(self) -> None:
        self._token = None
        self.go.setText(tr('Reconnaître'))

    def _progress(self, token, done: int, total: int) -> None:
        if token is self._token and total:
            self.status.setText(tr('Polices comparées : {0} sur {1} (leurs formes sont gardées : la prochaine fois, '
                                   'c’est immédiat)').format(done, total))

    def _done(self, token, res) -> None:
        if token is not self._token:
            return
        self.stop()
        self.list.clear()
        self.results = []
        self.apply_button.setEnabled(False)
        if isinstance(res, Exception):
            self.status.setText(tr('Reconnaissance impossible : {0}').format(res))
            return
        if isinstance(res, str) or not res:
            self.status.setText(tr(SAID.get(res or 'polices', SAID['polices'])))
            return
        self.results = list(res)
        for name, near in self.results:
            it = QListWidgetItem(f'{name}  —  {round(100 * near)} %')
            it.setData(Qt.ItemDataRole.UserRole, name)
            self.list.addItem(it)
        self.list.setCurrentRow(0)
        self.apply_button.setEnabled(True)
        self.status.setText(tr('{0} police(s) proche(s), la plus proche d’abord : double clic pour l’appliquer').format(
            len(self.results)))

    # --- le choix ----------------------------------------------------------------------------------------------------
    def chosen(self) -> str:
        it = self.list.currentItem()
        return str(it.data(Qt.ItemDataRole.UserRole)) if it is not None else ''

    def apply(self) -> int:
        """La police choisie mise aux textes sélectionnés (rend le nombre de textes changés) ; sans texte sélectionné,
        elle devient celle des prochains textes."""
        name = self.chosen()
        if not name:
            return 0
        from .textbar import selected_texts
        had = len(selected_texts(self.win)) if hasattr(self.win, 'canvas') else 0
        fn = getattr(self.win, 'apply_recognized_font', None)
        n = int(fn(name)) if fn is not None else 0
        if n:
            self.status.setText(tr('« {0} » appliquée à {1} texte(s)').format(name, n))
        elif had:
            self.status.setText(tr('Les textes sélectionnés ont déjà la police « {0} »').format(name))
        else:
            self.status.setText(tr('« {0} » : la police des prochains textes').format(name))
        return n

    def done(self, r: int) -> None:
        self.stop()
        if self.docked is None:
            super().done(r)
            return
        cols = getattr(self.win, 'columns', None)          # dans son panneau : « Fermer » le ferme
        if cols is not None:
            cols.close(self.docked)
        else:
            self.docked.hide()

    def event(self, ev) -> bool:                            # noqa: N802 (API Qt)
        if self.docked is not None and ev.type() == QEvent.Type.ShortcutOverride \
                and ev.key() == Qt.Key.Key_Escape:
            ev.accept()                                     # Échap pour lui, pas pour l'outil Sélection
            return True
        return super().event(ev)

    def keyPressEvent(self, ev) -> None:                    # noqa: N802 (API Qt)
        if self.docked is not None and ev.key() == Qt.Key.Key_Escape:
            if self._token is not None:                     # dans son panneau : Échap ne le ferme pas
                self.stop()
                self.status.setText(tr('Reconnaissance arrêtée'))
            ev.accept()
            return
        super().keyPressEvent(ev)

    def resizeEvent(self, ev) -> None:                      # noqa: N802 (API Qt)
        super().resizeEvent(ev)
        if self.docked is not None and self.preview.pixmap() is not None and not self.preview.pixmap().isNull():
            self._show_preview()                            # l'aperçu à la largeur du panneau
