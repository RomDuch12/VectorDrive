"""Dessins semblables et dossiers indexés (demande du 27/11 : « New fonction reconnaissance dessin/forme
user_full_parametrable : Indexage manuel de certains dossiers pour accélérer par la suite. Assistant IA peut accèder à
cet index. »).

Une fenêtre non modale, trois onglets :
- Recherche : d'après la sélection (sinon le dessin entier), un fichier, ou des critères (dimensions, contours, texte
  contenu, nom) → les dessins de l'index classés par ressemblance, avec leur score et leur croquis ; double clic :
  ouvert ;
- Ressemblance : invariances (taille, rotation, miroir, emplacement), poids de chaque critère, exigence, seuil,
  nombre de résultats ;
- Index : les dossiers choisis (ajout, retrait), les formats, les réglages de l'indexation, « Mettre à jour
  l'index » à la main, dans un fil de calcul (avancement, Annuler) : on continue de travailler pendant ce temps.

Tous les réglages sont retenus (`formes/…`) ; la liste des dossiers est aussi celle où l'assistant IA peut lire
(`agent.folder_tools`)."""
from __future__ import annotations

import json
import os
import pathlib

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QMessageBox, QProgressBar, QPushButton, QSpinBox, QTabWidget, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from ..core import shape_index as SI
from ..i18n import tr

KEY_FOLDERS = 'formes/dossiers'
KEY_EXTS = 'formes/formats'
KEY_PARAMS = 'formes/indexation'
KEY_MATCH = 'formes/ressemblance'
KEY_SOURCE = 'formes/source'
KEY_CRITERIA = 'formes/criteres'
#: taille des croquis de la liste, de l'aperçu (px)
ICON_PX = 48
PREVIEW_PX = 160
#: les critères : clé → (libellé, bulle)
CRITERIA_LABELS = {
    'contour': ('Silhouette', 'Le plus grand contour fermé (sinon le plus long ouvert), comparé point à point'),
    'moments': ('Répartition des traits', 'Moments d’inertie de tous les contours : la disposition d’ensemble'),
    'aspect': ('Allongement', 'Rapport des axes d’inertie (largeur / hauteur si l’orientation compte)'),
    'count': ('Nombre de contours', ''),
    'holes': ('Nombre de trous', 'Contours fermés compris dans un nombre impair d’autres'),
    'fill': ('Remplissage', 'Aire pleine rapportée à celle de l’enveloppe convexe'),
    'size': ('Taille', 'Comptée seulement si la taille compte'),
    'position': ('Emplacement', 'Compté seulement si l’emplacement compte'),
}


# --- les réglages retenus -------------------------------------------------------------------------------------
def _json(settings, key, default):
    try:
        v = json.loads(str(settings.value(key, '') or ''))
    except ValueError:
        return default
    return v if isinstance(v, type(default)) else default


def folders(settings) -> list:
    """Les dossiers choisis pour l'index (et lisibles par l'assistant IA)."""
    return [f for f in _json(settings, KEY_FOLDERS, []) if isinstance(f, str) and f.strip()]


def set_folders(settings, paths) -> None:
    out = []
    for p in paths:
        p = os.path.abspath(str(p))
        if all(os.path.normcase(p) != os.path.normcase(o) for o in out):
            out.append(p)
    settings.setValue(KEY_FOLDERS, json.dumps(out, ensure_ascii=False))


def exts(settings) -> tuple:
    raw = settings.value(KEY_EXTS, None)
    if raw is None or not str(raw).strip():
        return SI.DEFAULT_EXTS
    return SI.norm_exts(str(raw).replace(',', ' ').split()) or SI.DEFAULT_EXTS


def params(settings) -> SI.Params:
    return SI.from_dict(SI.Params, _json(settings, KEY_PARAMS, {}))


def match(settings) -> SI.Match:
    return SI.from_dict(SI.Match, _json(settings, KEY_MATCH, {}))


def index():
    """L'index des formes, partagé (dans le dossier des données)."""
    return SI.shared()


def sketch_pixmap(sketch, px: int, color='#202020') -> QPixmap:
    """Le croquis d'une fiche d'index (coordonnées 0 à 255, Y vers le haut) dessiné sur fond blanc."""
    pm = QPixmap(px, px)
    pm.fill(QColor('white'))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setPen(QPen(QColor(color), max(1.0, px / 80)))
    m = max(2, px // 16)
    k = (px - 2 * m) / 255.0
    for flat in sketch or ():
        pts = [QPointF(m + flat[i] * k, px - m - flat[i + 1] * k) for i in range(0, len(flat) - 1, 2)]
        if len(pts) >= 2:
            p.drawPolyline(pts)
    p.end()
    return pm


def _spin(lo, hi, val, dec=2, suffix='', tip=''):
    b = QDoubleSpinBox()
    b.setRange(lo, hi)
    b.setDecimals(dec)
    b.setValue(val)
    if suffix:
        b.setSuffix(suffix)
    if tip:
        b.setToolTip(tip)
    return b


def _ispin(lo, hi, val, tip=''):
    b = QSpinBox()
    b.setRange(lo, hi)
    b.setValue(int(val))
    if tip:
        b.setToolTip(tip)
    return b


class ShapeSearchDialog(QDialog):
    """La fenêtre ; `win` : la fenêtre principale (réglages, dessin, sélection, ouverture d'un fichier)."""

    PAGES = ('recherche', 'ressemblance', 'index')

    def __init__(self, win):
        super().__init__(win)
        from .fit import release
        release(self)
        self.win = win
        self.settings = win.settings
        self.setWindowTitle(tr('Dessins semblables'))
        self.setModal(False)
        col = QVBoxLayout(self)
        self.tabs = QTabWidget()
        col.addWidget(self.tabs)
        self.tabs.addTab(self._search_page(), tr('Recherche'))
        self.tabs.addTab(self._match_page(), tr('Ressemblance'))
        self.tabs.addTab(self._index_page(), tr('Index'))
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(lambda: self._poll())
        self.finished.connect(lambda _r=0: self.save())
        self._load()
        self._poll()
        if self.job() is not None and self.job().running:
            self.timer.start()

    # --- onglet Recherche ---------------------------------------------------------------------------------
    def _search_page(self) -> QWidget:
        page = QWidget()
        col = QVBoxLayout(page)
        row = QHBoxLayout()
        row.addWidget(QLabel(tr('Chercher d’après')))
        self.source = QComboBox()
        self.source.addItem(tr('La sélection (sinon le dessin entier)'), 'selection')
        self.source.addItem(tr('Un fichier'), 'fichier')
        self.source.addItem(tr('Des critères'), 'criteres')
        self.source.currentIndexChanged.connect(lambda _i=0: self._source_changed())
        row.addWidget(self.source, 1)
        col.addLayout(row)
        self.file_row = QWidget()
        fr = QHBoxLayout(self.file_row)
        fr.setContentsMargins(0, 0, 0, 0)
        self.file = QLineEdit()
        self.file.setPlaceholderText(tr('Le dessin dont chercher les semblables'))
        browse = QPushButton(tr('Parcourir…'))
        browse.clicked.connect(lambda _=False: self.browse_file())
        fr.addWidget(self.file, 1)
        fr.addWidget(browse)
        col.addWidget(self.file_row)
        self.crit = QGroupBox(tr('Critères (0 : sans borne)'))
        g = QGridLayout(self.crit)
        self.c_wmin, self.c_wmax = _spin(0, 1e6, 0, 1, ' mm'), _spin(0, 1e6, 0, 1, ' mm')
        self.c_hmin, self.c_hmax = _spin(0, 1e6, 0, 1, ' mm'), _spin(0, 1e6, 0, 1, ' mm')
        self.c_nmin, self.c_nmax = _ispin(0, 1000000, 0), _ispin(0, 1000000, 0)
        g.addWidget(QLabel(tr('Au moins')), 0, 1)
        g.addWidget(QLabel(tr('Au plus')), 0, 2)
        for r, (label, a, b) in enumerate(((tr('Largeur'), self.c_wmin, self.c_wmax),
                                           (tr('Hauteur'), self.c_hmin, self.c_hmax),
                                           (tr('Contours'), self.c_nmin, self.c_nmax)), 1):
            g.addWidget(QLabel(label), r, 0)
            g.addWidget(a, r, 1)
            g.addWidget(b, r, 2)
        self.c_text = QLineEdit()
        self.c_text.setPlaceholderText(tr('Mots d’un texte du dessin (sans casse ni accents)'))
        self.c_name = QLineEdit()
        self.c_name.setPlaceholderText(tr('Une partie du nom du fichier'))
        g.addWidget(QLabel(tr('Texte contenu')), 4, 0)
        g.addWidget(self.c_text, 4, 1, 1, 2)
        g.addWidget(QLabel(tr('Nom du fichier')), 5, 0)
        g.addWidget(self.c_name, 5, 1, 1, 2)
        col.addWidget(self.crit)
        row = QHBoxLayout()
        self.go = QPushButton(tr('Chercher'))
        self.go.setDefault(True)
        self.go.clicked.connect(lambda _=False: self.search())
        row.addWidget(self.go)
        self.status = QLabel()
        self.status.setWordWrap(True)
        row.addWidget(self.status, 1)
        col.addLayout(row)
        body = QHBoxLayout()
        self.results = QTreeWidget()
        self.results.setRootIsDecorated(False)
        self.results.setHeaderLabels([tr('Score'), tr('Fichier'), tr('Dimensions'), tr('Contours'), tr('Dossier')])
        self.results.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results.setIconSize(QPixmap(ICON_PX, ICON_PX).size())
        self.results.setToolTip(tr('Double clic : ouvrir le dessin'))
        self.results.itemDoubleClicked.connect(lambda it, _c=0: self.open_result(it))
        self.results.currentItemChanged.connect(lambda cur, _p=None: self._preview(cur))
        body.addWidget(self.results, 1)
        side = QVBoxLayout()
        self.preview = QLabel()
        self.preview.setFixedSize(PREVIEW_PX, PREVIEW_PX)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet('background: white; border: 1px solid #b0b0b0;')
        side.addWidget(self.preview)
        self.details = QLabel()
        self.details.setWordWrap(True)
        self.details.setFixedWidth(PREVIEW_PX)
        self.details.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        side.addWidget(self.details, 1)
        open_b = QPushButton(tr('Ouvrir'))
        open_b.clicked.connect(lambda _=False: self.open_result(self.results.currentItem()))
        side.addWidget(open_b)
        body.addLayout(side)
        col.addLayout(body, 1)
        return page

    # --- onglet Ressemblance -----------------------------------------------------------------------------
    def _match_page(self) -> QWidget:
        page = QWidget()
        col = QVBoxLayout(page)
        inv = QGroupBox(tr('Ne comptent pas'))
        v = QVBoxLayout(inv)
        self.inv = {'scale': QCheckBox(tr('La taille : agrandie ou réduite, reconnue')),
                    'rotation': QCheckBox(tr('L’orientation : tournée, reconnue')),
                    'mirror': QCheckBox(tr('Le sens : retournée en miroir, reconnue')),
                    'position': QCheckBox(tr('L’emplacement sur la plaque'))}
        for b in self.inv.values():
            v.addWidget(b)
        col.addWidget(inv)
        wg = QGroupBox(tr('Poids des critères (0 : ignoré)'))
        form = QFormLayout(wg)
        self.weights = {}
        for c in SI.CRITERIA:
            label, tip = CRITERIA_LABELS[c]
            b = _spin(0, 100, getattr(SI.Match(), 'w_' + c), 1, tip=tr(tip) if tip else '')
            self.weights[c] = b
            form.addRow(tr(label), b)
        col.addWidget(wg)
        form = QFormLayout()
        self.severity = _spin(0.25, 10, SI.Match().severity, 2,
                              tip=tr('Chaque ressemblance élevée à cette puissance : 1, indulgent ; plus haut, '
                                     'seules les formes très proches gardent un score élevé'))
        self.threshold = _spin(0, 100, SI.Match().threshold, 1, ' %', tr('Les dessins sous ce score ne sont pas '
                                                                            'montrés'))
        self.limit = _ispin(1, 10000, SI.Match().limit)
        form.addRow(tr('Exigence'), self.severity)
        form.addRow(tr('Seuil de ressemblance'), self.threshold)
        form.addRow(tr('Résultats au plus'), self.limit)
        col.addLayout(form)
        reset = QPushButton(tr('Valeurs d’office'))
        reset.clicked.connect(lambda _=False: self._show_match(SI.Match()))
        col.addWidget(reset)
        col.addStretch(1)
        return page

    # --- onglet Index ------------------------------------------------------------------------------------
    def _index_page(self) -> QWidget:
        page = QWidget()
        col = QVBoxLayout(page)
        box = QGroupBox(tr('Dossiers indexés (sous-dossiers compris)'))
        v = QVBoxLayout(box)
        self.folder_list = QListWidget()
        self.folder_list.setToolTip(tr('L’assistant IA peut aussi lire ces dossiers (lecture seule), si l’option '
                                       '« Il lit les dossiers indexés » est cochée (F10 › Assistant)'))
        v.addWidget(self.folder_list)
        row = QHBoxLayout()
        add = QPushButton(tr('Ajouter un dossier…'))
        add.clicked.connect(lambda _=False: self.add_folder())
        rem = QPushButton(tr('Retirer'))
        rem.clicked.connect(lambda _=False: self.remove_folder())
        row.addWidget(add)
        row.addWidget(rem)
        row.addStretch(1)
        v.addLayout(row)
        col.addWidget(box)
        form = QFormLayout()
        self.formats = QLineEdit()
        self.formats.setToolTip(tr('Extensions séparées par des espaces. Jamais les images ni les formats lus par un '
                                   'autre logiciel (DWG, CorelDRAW…)'))
        form.addRow(tr('Formats'), self.formats)
        P = SI.Params()
        self.p_min = _spin(0, 1000, P.min_size, 2, ' mm', tr('Un contour plus petit (diagonale) est ignoré'))
        self.p_rel = _spin(0, 50, P.min_rel, 2, ' %', tr('De même, en part de la taille du dessin'))
        self.p_texts = QCheckBox(tr('Compter les contours des textes'))
        self.p_texts.setToolTip(tr('Leurs mots sont toujours retenus pour la recherche par texte'))
        self.p_hidden = QCheckBox(tr('Compter les objets et calques masqués'))
        self.p_points = _ispin(16, 512, P.points, tr('Points de la silhouette comparée : plus, plus fin et plus '
                                                     'lent'))
        self.p_prec = _spin(0.01, 5, P.precision, 2, ' %', tr('Écart toléré à l’aplatissement des courbes, en part '
                                                               'de la taille du dessin'))
        self.p_max = _ispin(10, 5000, P.max_contours, tr('Pour les trous et le remplissage : les plus grands '
                                                         'contours seulement'))
        form.addRow(tr('Taille mini des contours'), self.p_min)
        form.addRow(tr('Taille mini relative'), self.p_rel)
        form.addRow(self.p_texts)
        form.addRow(self.p_hidden)
        form.addRow(tr('Finesse de la silhouette'), self.p_points)
        form.addRow(tr('Précision des courbes'), self.p_prec)
        form.addRow(tr('Contours au plus (trous)'), self.p_max)
        col.addLayout(form)
        row = QHBoxLayout()
        self.update_b = QPushButton(tr('Mettre à jour l’index'))
        self.update_b.setToolTip(tr('Seuls les fichiers neufs ou changés (taille, date) sont lus ; tous, si les '
                                    'réglages de l’indexation ont changé'))
        self.update_b.clicked.connect(lambda _=False: self.start_update())
        self.cancel_b = QPushButton(tr('Annuler'))
        self.cancel_b.setEnabled(False)
        self.cancel_b.clicked.connect(lambda _=False: self.cancel_update())
        row.addWidget(self.update_b)
        row.addWidget(self.cancel_b)
        col.addLayout(row)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setValue(0)
        col.addWidget(self.bar)
        self.index_status = QLabel()
        self.index_status.setWordWrap(True)
        col.addWidget(self.index_status)
        col.addStretch(1)
        return page

    # --- réglages ----------------------------------------------------------------------------------------
    def _load(self) -> None:
        s = self.settings
        k = self.source.findData(str(s.value(KEY_SOURCE, 'selection') or 'selection'))
        self.source.setCurrentIndex(max(0, k))
        self._show_match(match(s))
        P = params(s)
        self.p_min.setValue(P.min_size)
        self.p_rel.setValue(P.min_rel)
        self.p_texts.setChecked(P.texts)
        self.p_hidden.setChecked(P.hidden)
        self.p_points.setValue(P.points)
        self.p_prec.setValue(P.precision)
        self.p_max.setValue(P.max_contours)
        self.formats.setText(' '.join(exts(s)))
        self.folder_list.clear()
        self.folder_list.addItems(folders(s))
        c = _json(s, KEY_CRITERIA, {})
        for key, w in (('wmin', self.c_wmin), ('wmax', self.c_wmax), ('hmin', self.c_hmin), ('hmax', self.c_hmax)):
            w.setValue(float(c.get(key, 0) or 0) if isinstance(c.get(key, 0), (int, float)) else 0.0)
        for key, w in (('nmin', self.c_nmin), ('nmax', self.c_nmax)):
            w.setValue(int(c.get(key, 0)) if isinstance(c.get(key, 0), int) else 0)
        self.c_text.setText(str(c.get('texte', '') or ''))
        self.c_name.setText(str(c.get('nom', '') or ''))
        self._source_changed()
        self._show_summary()

    def _show_match(self, m: SI.Match) -> None:
        for f, b in self.inv.items():
            b.setChecked(bool(getattr(m, f)))
        for c, b in self.weights.items():
            b.setValue(float(getattr(m, 'w_' + c)))
        self.severity.setValue(m.severity)
        self.threshold.setValue(m.threshold)
        self.limit.setValue(m.limit)

    def current_match(self) -> SI.Match:
        d = {f: b.isChecked() for f, b in self.inv.items()}
        d.update({'w_' + c: b.value() for c, b in self.weights.items()})
        d.update(severity=self.severity.value(), threshold=self.threshold.value(), limit=self.limit.value())
        return SI.from_dict(SI.Match, d)

    def current_params(self) -> SI.Params:
        return SI.from_dict(SI.Params, {'min_size': self.p_min.value(), 'min_rel': self.p_rel.value(),
                                        'texts': self.p_texts.isChecked(), 'hidden': self.p_hidden.isChecked(),
                                        'points': self.p_points.value(), 'precision': self.p_prec.value(),
                                        'max_contours': self.p_max.value()})

    def current_exts(self) -> tuple:
        return SI.norm_exts(self.formats.text().replace(',', ' ').split()) or SI.DEFAULT_EXTS

    def current_folders(self) -> list:
        return [self.folder_list.item(i).text() for i in range(self.folder_list.count())]

    def save(self) -> None:
        """Tous les réglages de la fenêtre retenus."""
        import dataclasses
        s = self.settings
        s.setValue(KEY_SOURCE, self.source.currentData())
        s.setValue(KEY_MATCH, json.dumps(dataclasses.asdict(self.current_match())))
        s.setValue(KEY_PARAMS, json.dumps(dataclasses.asdict(self.current_params())))
        s.setValue(KEY_EXTS, ' '.join(self.current_exts()))
        set_folders(s, self.current_folders())
        s.setValue(KEY_CRITERIA, json.dumps({'wmin': self.c_wmin.value(), 'wmax': self.c_wmax.value(),
                                             'hmin': self.c_hmin.value(), 'hmax': self.c_hmax.value(),
                                             'nmin': self.c_nmin.value(), 'nmax': self.c_nmax.value(),
                                             'texte': self.c_text.text(), 'nom': self.c_name.text()},
                                            ensure_ascii=False))

    def show_page(self, page: str) -> None:
        if page in self.PAGES:
            self.tabs.setCurrentIndex(self.PAGES.index(page))

    def _source_changed(self) -> None:
        src = self.source.currentData()
        self.file_row.setVisible(src == 'fichier')
        self.crit.setVisible(src == 'criteres')

    # --- les dossiers ------------------------------------------------------------------------------------
    def add_folder(self, path: str | None = None) -> bool:
        if path is None:
            path = QFileDialog.getExistingDirectory(self, tr('Dossier à indexer'), self.win._last_dir('ouvrir'))
            if not path:
                return False
        path = os.path.abspath(path)
        if any(os.path.normcase(path) == os.path.normcase(f) for f in self.current_folders()):
            return False
        self.folder_list.addItem(path)
        set_folders(self.settings, self.current_folders())
        self._show_summary()
        return True

    def remove_folder(self) -> bool:
        row = self.folder_list.currentRow()
        if row < 0:
            return False
        self.folder_list.takeItem(row)
        set_folders(self.settings, self.current_folders())
        self._show_summary()
        return True

    # --- la mise à jour, en arrière-plan ---------------------------------------------------------------------
    def job(self):
        return getattr(self.win, '_shape_job', None)

    def start_update(self, reader=None) -> bool:
        """La mise à jour de l'index lancée dans un fil de calcul ; rend faux s'il n'y a pas de dossier ou si une
        mise à jour est déjà en cours."""
        j = self.job()
        if (j is not None and j.running) or index().updating.locked():
            self.index_status.setText(tr('Une mise à jour de l’index est déjà en cours (une autre fenêtre) : '
                                         'réessayez quand elle sera finie.') if j is None or not j.running
                                      else tr('Une mise à jour de l’index est déjà en cours.'))
            return False
        roots = self.current_folders()
        if not roots:
            self.index_status.setText(tr('Ajoutez d’abord un dossier à indexer.'))
            return False
        self.save()
        from .symbols import is_hidden
        self.win._shape_job = SI.IndexJob(index(), roots, self.current_exts(), self.current_params(), reader=reader,
                                          hidden=is_hidden).start()
        self.update_b.setEnabled(False)
        self.cancel_b.setEnabled(True)
        self.bar.setRange(0, 0)                          # le parcours des dossiers : sans fin connue
        self.index_status.setText(tr('Parcours des dossiers…'))
        self.timer.start()
        return True

    def cancel_update(self) -> None:
        j = self.job()
        if j is not None and j.running:
            j.cancel()
            self.index_status.setText(tr('Annulation… (le fichier en cours est fini, l’index gardé)'))

    def _poll(self) -> None:
        j = self.job()
        running = j is not None and j.running
        self.update_b.setEnabled(not running)
        self.cancel_b.setEnabled(running and not j.task.cancelled.is_set())
        if running:
            if j.task.text:
                self.bar.setRange(0, 1000)
                self.bar.setValue(int(1000 * max(0.0, min(1.0, j.task.fraction))))
                self.index_status.setText(tr('Lecture {0}').format(j.task.text))
            return
        self.timer.stop()
        self.bar.setRange(0, 1000)
        if j is not None and not getattr(j, '_shown', False):
            j._shown = True
            self.bar.setValue(1000 if j.result and not j.result.get('annule') else 0)
            self._show_summary(j)
        elif j is None:
            self.bar.setValue(0)

    def _show_summary(self, j=None) -> None:
        idx = index()
        roots = self.current_folders()
        s = idx.summary(roots)
        text = tr('{0} fichiers dans l’index, {1} dessins reconnus, {2} illisibles.').format(
            s['files'], s['drawings'], s['unreadable'])
        stale = idx.stale(self.current_params(), roots)
        if idx.error:                                    # l'index n'a pas pu être enregistré
            text += '\n' + tr('Index non enregistré : {0}').format(idx.error)
        if stale:
            text += ' ' + tr('{0} à relire (réglages changés).').format(stale)
        if j is not None and isinstance(j.error, SI.Busy):     # celle d'une autre fenêtre du programme
            text = tr('Une mise à jour de l’index est déjà en cours (une autre fenêtre) : réessayez quand elle sera '
                      'finie.') + '\n' + text
        elif j is not None and j.error is not None:
            text = tr('Mise à jour interrompue : {0}').format(j.error) + '\n' + text
        elif j is not None and j.result:
            r = j.result
            head = tr('Annulée : ce qui est lu est gardé.') if r.get('annule') else tr('Index à jour.')
            text = (head + ' ' + tr('{0} lus, {1} inchangés, {2} oubliés.').format(r['lus'], r['gardes'], r['oublies'])
                    + '\n' + text)
            if r.get('injoignables'):
                text += '\n' + tr('Injoignables (leur index est gardé) : {0}').format(', '.join(r['injoignables']))
        self.index_status.setText(text)
        self.update_b.setText(tr('Mettre à jour l’index') if s['files'] else tr('Indexer maintenant'))

    # --- la recherche -------------------------------------------------------------------------------------
    def browse_file(self) -> None:
        from ..io import registry
        path, _f = QFileDialog.getOpenFileName(self, tr('Dessin de référence'), self.win._last_dir('ouvrir'),
                                               registry.filter_string())
        if path:
            self.file.setText(path)

    def query(self) -> tuple:
        """(signature cherchée, chemin à écarter, message) selon la source choisie."""
        P = self.current_params()
        src = self.source.currentData()
        if src == 'fichier':
            path = self.file.text().strip()
            if not path or not os.path.isfile(path):
                return None, None, tr('Choisissez un fichier.')
            rec = index().files.get(SI.key_of(path))
            st = os.stat(path)
            if rec and rec.get('sig') and rec.get('p') == P.digest() and rec.get('size') == st.st_size \
                    and rec.get('mtime') == st.st_mtime:
                return rec['sig'], path, ''
            from .progress import Cancelled, run
            try:
                got = run(self, tr('Lecture de {0}').format(pathlib.Path(path).name),
                          lambda: SI.describe(SI.read_drawing(path), P))
            except Cancelled:
                return None, None, tr('Annulé.')
            except Exception as ex:                      # noqa: BLE001 — fichier illisible : dit
                return None, None, tr('Lecture impossible : {0}').format(ex)
            return got['sig'], path, ''
        sel = list(self.win.canvas.selection)
        items = sel or SI.doc_items(self.win.canvas.doc, P.hidden)
        sig = SI.signature(items, P)
        return sig, (None if sel else getattr(self.win, 'path', None)), ''

    def search(self) -> list:
        """La recherche lancée ; rend les lignes montrées [(score ou None, fiche)]."""
        self.save()
        self.results.clear()
        self.preview.clear()
        self.details.clear()
        idx = index()
        roots = self.current_folders()                   # les fiches des dossiers retirés : jamais montrées
        P = self.current_params()
        if not roots or not idx.summary(roots)['files']:
            self.status.setText(tr('L’index est vide : choisissez des dossiers puis « Indexer maintenant » '
                                   '(onglet Index).'))
            return []
        rows = []
        if self.source.currentData() == 'criteres':
            def rng(a, b):
                lo, hi = a.value(), b.value()
                return (lo or None, hi or None) if (lo or hi) else None
            recs = idx.find(width=rng(self.c_wmin, self.c_wmax), height=rng(self.c_hmin, self.c_hmax),
                            contours=rng(self.c_nmin, self.c_nmax), text=self.c_text.text(),
                            name=self.c_name.text(), folders=roots, limit=self.limit.value())
            rows = [(None, r) for r in recs]
        else:
            if not idx.records(P, roots) and idx.stale(P, roots):
                self.status.setText(tr('L’index est à mettre à jour : les réglages de l’indexation ont changé '
                                       '(onglet Index, « Mettre à jour l’index »).'))
                return []
            sig, skip, why = self.query()
            if sig is None:
                self.status.setText(why or tr('Rien à comparer : aucun contour assez grand.'))
                return []
            found = idx.search(sig, self.current_match(), P, folders=roots, exclude=[skip] if skip else ())
            rows = [(s, r) for s, r, _sims in found]
        for s, r in rows:
            self._add_row(s, r)
        if self.results.topLevelItemCount():
            self.results.setCurrentItem(self.results.topLevelItem(0))
        n = len(idx.records(P, roots))
        self.status.setText(tr('{0} résultat(s) parmi {1} dessins indexés.').format(len(rows), n))
        return rows

    def _add_row(self, s, rec) -> None:
        p = pathlib.Path(rec['path'])
        from ..i18n import decimal_sep
        sep = decimal_sep()
        dims = ' × '.join(f'{float(rec.get(k, 0) or 0):.1f}'.replace('.', sep) for k in ('w', 'h'))
        it = QTreeWidgetItem(['' if s is None else f'{s:.0f} %', p.name, dims, str(rec.get('contours', 0)),
                              str(p.parent)])
        it.setData(0, Qt.ItemDataRole.UserRole, rec['path'])
        it.setData(1, Qt.ItemDataRole.UserRole, rec)
        it.setIcon(1, QIcon(sketch_pixmap(rec.get('sketch'), ICON_PX)))
        it.setToolTip(1, rec['path'])
        self.results.addTopLevelItem(it)

    def _preview(self, it) -> None:
        if it is None:
            self.preview.clear()
            self.details.clear()
            return
        rec = it.data(1, Qt.ItemDataRole.UserRole) or {}
        self.preview.setPixmap(sketch_pixmap(rec.get('sketch'), PREVIEW_PX))
        lines = [pathlib.Path(rec.get('path', '')).name]
        if rec.get('layers'):
            lines.append(tr('Calques : {0}').format(', '.join(L['name'] for L in rec['layers'][:8])))
        if rec.get('texts'):
            lines.append(tr('Textes : {0}').format(' · '.join(t[:30] for t in rec['texts'][:6])))
        self.details.setText('\n'.join(lines))

    def open_result(self, it) -> bool:
        if it is None:
            return False
        path = it.data(0, Qt.ItemDataRole.UserRole)
        if not path or not os.path.isfile(path):
            QMessageBox.warning(self, tr('Dessins semblables'), tr('Fichier introuvable : {0}').format(path))
            return False
        return bool(self.win.open_path(path))
