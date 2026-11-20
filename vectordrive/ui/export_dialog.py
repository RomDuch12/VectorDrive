"""Exporter (Maj+E) : la sélection (ou tout le dessin) dans le format
choisi, avec des **modèles d'export** — un nom, un format et ses réglages
(textes vivants du VND, résolution et fond des images…) — enregistrés dans
les réglages et proposés d'un clic, comme les modèles de parcours.

Seuls les réglages du format choisi sont montrés ; le fichier écrit est
relu (dessin : objets retrouvés ; image : dimensions) et le résultat
annoncé avec « Ouvrir le dossier » ; la fenêtre propose aussi le dossier
du dernier export.
"""
from __future__ import annotations

import json
import pathlib

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                               QHBoxLayout, QInputDialog, QLabel, QListWidget, QListWidgetItem, QMessageBox,
                               QPushButton, QVBoxLayout, QWidget)

from ..i18n import tr

#: réglages d'un modèle : (clé, libellé, défaut) — ceux des images et des VND
OPTIONS = [
    ('vnd_textes_vivants', 'VND : textes modifiables dans TypeEdit', True),
    ('dxf_calques_outils', 'DXF : un calque par outil (Outil 1, Outil 2… ; sinon les calques du dessin)', False),
    ('dpi', 'Image : résolution (dpi)', 300.0),
    ('transparent', 'Image : fond transparent', False),
    ('plaque', 'Image : avec la plaque', True),
    ('marge', 'Image : marge (mm)', 2.0),
    ('trait', 'Image : épaisseur de trait (mm)', 0.1),
    ('rempli', 'Image : formes remplies', False),
]
RASTER_EXT = ('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff', '.gif')
#: réglage → nature des formats qui s'en servent ('vnd', 'image')
OPTION_KIND = {'vnd_textes_vivants': 'vnd', 'dxf_calques_outils': 'dxf', 'dpi': 'image', 'transparent': 'image', 'plaque': 'image',
               'marge': 'image', 'trait': 'image', 'rempli': 'image'}
#: réglage : dernier fichier exporté
LAST_KEY = 'export/dernier'
#: réglage : format et réglages du dernier export (proposés la fois suivante)
LAST_CHOICE_KEY = 'export/dernier_choix'
#: version du dernier choix et des modèles : 2, textes modifiables dans TypeEdit cochés d'office (round 988)
CHOICE_VERSION = 2
#: formats « page » : la sélection exportée y est cadrée sur elle-même, sans la plaque
PAGE_EXT = RASTER_EXT + ('.pdf', '.svg', '.ai', '.eps', '.ps', '.plt', '.hpgl', '.hpg', '.hgl', '.gl2')


def upgrade(t: dict) -> dict:
    """Dernier choix ou modèle d'avant la version 2 : les textes modifiables dans TypeEdit y sont cochés (ils étaient
    décochés d'office, à l'essai) ; ceux enregistrés depuis gardent ce qu'on y a mis."""
    try:
        old = int(t.get('v', 1) or 1) < CHOICE_VERSION
    except (TypeError, ValueError):
        old = True
    if old:
        opts = t.get('options')
        if isinstance(opts, dict) and 'vnd_textes_vivants' in opts:
            opts['vnd_textes_vivants'] = True
        t['v'] = CHOICE_VERSION
    return t


def load_last_choice(settings) -> dict:
    try:
        d = json.loads(str(settings.value(LAST_CHOICE_KEY, '') or '{}'))
        return upgrade(d) if isinstance(d, dict) else {}
    except (ValueError, TypeError):
        return {}


def save_last_choice(settings, choice: dict) -> None:
    settings.setValue(LAST_CHOICE_KEY, json.dumps({'v': CHOICE_VERSION, 'format': choice.get('format'),
                                                   'options': choice.get('options')}, ensure_ascii=False))


def kind_of(fmt) -> str:
    """Nature d'un format pour ses réglages : 'image', 'vnd', 'machine' ou 'dessin'."""
    exts = tuple(e.lower() for e in getattr(fmt, 'extensions', ()) or ())
    if exts and exts[0] in RASTER_EXT:
        return 'image'
    if exts and exts[0] in ('.vnd', '.vnl', '.vnm'):
        return 'vnd'
    if '.dxf' in exts or '.dwg' in exts:                 # (le DWG est écrit par un DXF)
        return 'dxf'
    return 'machine' if getattr(fmt, 'machine', False) else 'dessin'


def load_templates(settings) -> list[dict]:
    try:
        data = json.loads(str(settings.value('export/modeles', '') or '[]'))
        return [upgrade(t) for t in data if isinstance(t, dict) and t.get('nom')]
    except (ValueError, TypeError):
        return []


def save_templates(settings, templates: list[dict]) -> None:
    settings.setValue('export/modeles', json.dumps(templates, ensure_ascii=False))


def formats() -> list:
    """Formats qu'on sait écrire (cœur et plugins), images comprises."""
    from ..io import registry
    out = [f for f in registry.all_formats() if f.writer or f.export]
    return out


class ExportDialog(QDialog):
    """Choix du modèle / format / réglages, puis « Exporter… »."""

    def __init__(self, win, selection: bool):
        super().__init__(win)
        self.win = win
        self.setWindowTitle(tr('Exporter'))
        self.templates = load_templates(win.settings)
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        lay.addLayout(row)
        left = QVBoxLayout()
        row.addLayout(left, 1)
        left.addWidget(QLabel(tr('Modèles d\'export')))
        self.list = QListWidget()
        self.list.itemClicked.connect(self._pick)
        self.list.itemDoubleClicked.connect(lambda _i: self.accept())
        left.addWidget(self.list, 1)
        btns = QHBoxLayout()
        self.save_btn = QPushButton(tr('Enregistrer comme modèle…'))
        self.save_btn.clicked.connect(self._save_template)
        self.del_btn = QPushButton(tr('Supprimer'))
        self.del_btn.clicked.connect(self._delete_template)
        btns.addWidget(self.save_btn)
        btns.addWidget(self.del_btn)
        left.addLayout(btns)
        right = QFormLayout()
        row.addLayout(right, 1)
        self.only_sel = QCheckBox(tr('La sélection seulement'))
        self.only_sel.setChecked(selection)
        self.only_sel.setEnabled(selection)
        self.only_sel.setToolTip(tr('Image, PDF, SVG : cadrés sur la sélection, sans la plaque'))
        right.addRow(self.only_sel)
        self.format = QComboBox()
        self._formats = {f.key: f for f in formats()}
        for f in self._formats.values():
            self.format.addItem(f'{tr(f.written_label())} ({", ".join(f.extensions)})', f.key)
        right.addRow(tr('Format'), self.format)
        self.right = right
        self.no_option = QLabel()
        self.no_option.setWordWrap(True)
        self.no_option.setStyleSheet('color: #868e96;')
        right.addRow(self.no_option)
        self.fields: dict[str, QWidget] = {}
        for key, label, default in OPTIONS:
            if isinstance(default, bool):
                w = QCheckBox()
                w.setChecked(default)
            else:
                w = QDoubleSpinBox()
                w.setRange(0.0, 10000.0)
                w.setDecimals(2)
                w.setValue(float(default))
            self.fields[key] = w
            right.addRow(tr(label), w)
        self.format.currentIndexChanged.connect(self._format_changed)
        self.only_sel.toggled.connect(self._format_changed)
        last = load_last_choice(win.settings)            # le dernier export : son format, ses réglages
        if last.get('format'):
            self.apply_template(last)
        self._format_changed()
        self._fill()
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.go = bb.addButton(tr('Exporter…'), QDialogButtonBox.ButtonRole.AcceptRole)
        self.last = str(win.settings.value(LAST_KEY, '') or '')
        self.last_btn = bb.addButton(tr('Dossier du dernier export'), QDialogButtonBox.ButtonRole.ResetRole)
        self.last_btn.setToolTip(self.last or tr('Aucun export pour l\'instant'))
        self.last_btn.setEnabled(bool(self.last) and pathlib.Path(self.last).parent.is_dir())
        self.last_btn.clicked.connect(self.reveal_last)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        from .fit import no_hscroll
        no_hscroll(self)

    def _format_changed(self, *_a) -> None:
        """Seuls les réglages du format choisi : VND, image, ou aucun."""
        kind = kind_of(self._formats.get(self.format.currentData()))
        shown = 0
        for key, w in self.fields.items():
            on = OPTION_KIND.get(key) == kind
            self.right.setRowVisible(w, on)
            shown += on
        self.fields['plaque'].setEnabled(not self.only_sel.isChecked())      # la sélection seule : sans la plaque
        f = self._formats.get(self.format.currentData())
        if shown:
            self.no_option.setVisible(False)
        else:
            self.no_option.setText(tr('Fichier machine : ses réglages sont demandés à l\'écriture.')
                                   if kind == 'machine' or (f is not None and f.export is not None)
                                   else tr('Pas de réglage pour ce format.'))
            self.no_option.setVisible(True)
        self.adjustSize()

    def reveal_last(self) -> bool:
        """Le dossier du dernier export, le fichier sélectionné."""
        from .reveal import reveal
        return bool(self.last) and reveal(self.last)

    # --- modèles ---------------------------------------------------------------------------
    def _fill(self) -> None:
        self.list.clear()
        for t in self.templates:
            it = QListWidgetItem(f"{t['nom']}  —  {t.get('format', '')}")
            it.setData(Qt.ItemDataRole.UserRole, t['nom'])
            self.list.addItem(it)

    def _pick(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.ItemDataRole.UserRole)
        t = next((x for x in self.templates if x['nom'] == name), None)
        if t is not None:
            self.apply_template(t)

    def apply_template(self, t: dict) -> None:
        i = self.format.findData(t.get('format'))
        if i >= 0:
            self.format.setCurrentIndex(i)
        for key, w in self.fields.items():
            if key in (t.get('options') or {}):
                v = t['options'][key]
                if isinstance(w, QCheckBox):
                    w.setChecked(bool(v))
                else:
                    w.setValue(float(v))

    def current(self) -> dict:
        """Format et réglages affichés."""
        opts = {k: (w.isChecked() if isinstance(w, QCheckBox) else w.value()) for k, w in self.fields.items()}
        return {'format': self.format.currentData(), 'options': opts}

    def _save_template(self) -> None:
        name, ok = QInputDialog.getText(self, tr('Modèle d\'export'), tr('Nom du modèle'))
        if not ok or not name.strip():
            return
        name = name.strip()
        t = {'nom': name, 'v': CHOICE_VERSION, **self.current()}
        self.templates = [x for x in self.templates if x['nom'] != name] + [t]
        self.templates.sort(key=lambda x: x['nom'].lower())
        save_templates(self.win.settings, self.templates)
        self._fill()

    def _delete_template(self) -> None:
        it = self.list.currentItem()
        if it is None:
            return
        name = it.data(Qt.ItemDataRole.UserRole)
        self.templates = [x for x in self.templates if x['nom'] != name]
        save_templates(self.win.settings, self.templates)
        self._fill()


#: données du dessin qui ne suivent pas un export de la sélection (FAO des autres objets, lecture du VND)
_NOT_EXPORTED = ('fao', 'fao_journal', 'work_time', 'compagnon', 'vnd_signature', 'vnd_partial', 'ia_credits')


def selection_document(src, items: list):
    """Document des seuls `items` (copies, à leur place) : chacun dans une
    copie de son calque (nom, outil), dans l'ordre du dessin ; objets d'un
    groupe pris seuls. L'origine, la plaque et les données du dessin suivent."""
    import copy
    from ..core.document import Document, Layer, struct_copy
    ids = {id(it) for it in items}
    layers, found = [], set()

    def walk(lst, out):
        for it in lst:
            if id(it) in ids:
                out.append(struct_copy(it))
                found.add(id(it))
            elif getattr(it, 'children', None):
                walk(it.children, out)
    for L in src.layers:
        picked = []
        walk(L.items, picked)
        if picked:
            c = copy.copy(L)
            c.items, c.extra = picked, dict(L.extra)
            layers.append(c)
    rest = [struct_copy(it) for it in items if id(it) not in found]     # hors du dessin : au calque actif
    if rest:
        act = src.active_layer
        c = next((L for L in layers if L.id == act.id), None)
        if c is None:
            c = copy.copy(act)
            c.items, c.extra = [], dict(act.extra)
            layers.append(c)
        c.items += rest
    doc = Document(layers=layers or [Layer()], tools=src.tools, plate=src.plate)
    doc.active = src.active
    doc.extra = {k: v for k, v in (src.extra or {}).items() if k not in _NOT_EXPORTED}
    return doc


def export_items(win, items: list, path: str, options: dict | None = None, selection: bool = False) -> None:
    """Écrit `items` (copies, à leur place, dans leurs calques) dans `path`,
    selon son extension : image (réglages des images), VND (textes vivants ou
    non), autre format. `selection` : c'est la sélection seule — dans un
    format « page » (image, PDF, SVG…), cadrée sur elle, sans la plaque."""
    from ..io import raster, registry
    options = dict(options or {})
    doc = selection_document(win.canvas.doc, items)
    if selection:                                        # une plaque de reprise choisie exprès : écrite, comme un dessin
        from ..cam.fixture import PLATE_LAYER
        for L in doc.layers:
            L.extra.pop(PLATE_LAYER, None)
    if selection and pathlib.Path(path).suffix.lower() in PAGE_EXT:
        options['plaque'] = False
    if not options.get('plaque', True):
        doc.plate = None
    if isinstance(doc.extra, dict):
        doc.extra['vnd_textes_vivants'] = bool(options.get('vnd_textes_vivants', True))
        from .options import value
        st = getattr(win, 'settings', None)
        doc.extra['vnd_premier_plan'] = bool(value(st, 'vnd/premier_plan_montre')) if st is not None else False
        doc.extra['dxf_calques_outils'] = bool(options.get('dxf_calques_outils', False))
    suffix = pathlib.Path(path).suffix.lower()
    if suffix in RASTER_EXT:
        spec = raster.RasterSpec(dpi=float(options.get('dpi', 300.0)), transparent=bool(options.get('transparent', False)),
                                 include_plate=bool(options.get('plaque', True)), margin=float(options.get('marge', 2.0)),
                                 line_mm=float(options.get('trait', 0.1)), filled=bool(options.get('rempli', False)),
                                 tool_colors=bool(getattr(win.canvas, 'tool_colors', True)),   # comme à l'écran
                                 orientation=bool(getattr(win.canvas, 'show_direction', False)))
        raster.write(doc, path, spec)
        return
    registry.save_document(doc, path)


def verify_export(path: str, expected: int | None = None) -> tuple[bool, str]:
    """Le fichier écrit relu : (bon, compte rendu). Image : ses dimensions ;
    dessin lisible par VectorDrive : les objets retrouvés (comparés à
    `expected`) ; autre format : sa taille."""
    p = pathlib.Path(path)
    try:
        size = p.stat().st_size
    except OSError:
        return False, tr('Fichier absent après l\'écriture : {0}').format(p)
    if size == 0:
        return False, tr('Fichier vide : {0}').format(p)
    kb = f'{size / 1024:.0f} Ko' if size >= 1024 else f'{size} o'
    if p.suffix.lower() in RASTER_EXT:
        from PySide6.QtGui import QImageReader
        dims = QImageReader(str(p)).size()               # sans la décoder : une grande image passe la limite de Qt
        if not dims.isValid() or dims.width() < 1 or dims.height() < 1:
            return False, tr('Image illisible : {0}').format(p.name)
        return True, tr('Image {0} × {1} px, {2}').format(dims.width(), dims.height(), kb)
    from ..io import registry
    fmt = next((f for f in registry.all_formats() if p.suffix.lower() in f.extensions), None)
    if fmt is None or fmt.reader is None:
        return True, tr('Fichier écrit, {0} (format non relu par VectorDrive)').format(kb)
    if fmt.key in ('step', 'mesh'):                      # une pièce en volume : relue comme telle, pas en vue de dessus
        from ..io import model3d
        try:
            n = len(model3d.load(str(p)).triangles)
        except Exception as ex:                          # noqa: BLE001 — relecture : le compte rendu dit pourquoi
            return False, tr('Fichier écrit mais illisible : {0}').format(ex)
        return (n > 0), tr('Pièce en volume relue ({0} triangles), {1}').format(n, kb)
    try:
        n = len(list(registry.open_document(str(p)).iter_leaves()))
    except Exception as ex:                              # noqa: BLE001 — relecture : le compte rendu dit pourquoi
        return False, tr('Fichier écrit mais illisible : {0}').format(ex)
    if expected is not None and n < expected:
        return False, tr('{0} objet(s) relu(s) sur {1} exportés, {2}').format(n, expected, kb)
    return True, tr('{0} objet(s) relu(s), {1}').format(n, kb)


def run(win) -> str | None:
    """Maj+E : fenêtre, puis fichier ; rend le chemin écrit, ou None."""
    from PySide6.QtWidgets import QFileDialog
    from ..io import registry
    sel = list(win.canvas.selection)
    dlg = ExportDialog(win, bool(sel))
    if not dlg.exec():
        return None
    cur = dlg.current()
    # lu tout de suite : la boîte de fichier qui suit fait tourner la boucle d'événements, et la fenêtre finie
    # ne doit plus rien avoir à dire après elle
    only = bool(sel and dlg.only_sel.isChecked())
    fmt = next((f for f in formats() if f.key == cur['format']), None)
    if fmt is None:
        return None
    exts = ' '.join('*' + e for e in fmt.extensions)
    start = pathlib.Path(win._last_dir('exporter')) / (pathlib.Path(win.path or 'dessin').stem + fmt.extensions[0])
    path, _ = QFileDialog.getSaveFileName(win, tr('Exporter'), str(start), f'{tr(fmt.written_label())} ({exts})')
    if not path:
        return None
    if not path.lower().endswith(tuple(fmt.extensions)):
        path += fmt.extensions[0]
    win._remember_dir('exporter', path)
    if fmt.machine and not win._confirm_machine_export():
        return None
    if not win.vnd_partial_guard(path):
        return None
    items = sel if only else [it for L in win.canvas.doc.layers for it in L.items]
    expected = None
    try:
        if fmt.export is not None and not only:
            fmt.export(win, path)                       # format d'un plugin : sa fenêtre de réglages
        else:
            from .progress import Cancelled, run
            try:                                         # dans le fil de calcul : la fenêtre reste vivante
                run(win, tr('Exporter : {0}').format(pathlib.Path(path).name), export_items, win, items, path,
                    cur['options'], only)
            except Cancelled:
                return None
            written = selection_document(win.canvas.doc, items)
            if not only and not path.lower().endswith('.vdz'):
                from ..cam.fixture import without_plates    # tout le dessin : sa plaque de reprise n'est pas écrite
                written = without_plates(written)
            expected = sum(1 for _ in written.iter_leaves())
    except Exception as ex:
        if hasattr(win, '_offer_oda') and win._offer_oda(ex):   # DWG sans ODA File Converter : pas une erreur
            return None
        from .. import journal
        journal.record(type(ex), ex, ex.__traceback__, where=f'export {pathlib.Path(path).suffix}')
        QMessageBox.critical(win, tr('Export impossible'), str(ex))
        return None
    if not pathlib.Path(path).exists():
        if expected is not None:                         # notre écriture n'a rien laissé : le dire, plus de silence
            QMessageBox.warning(win, tr('Exporter'), tr('Aucun fichier n’a été écrit : {0}').format(path))
        return None                                      # sinon : fenêtre du plugin abandonnée, rien d'écrit
    win.settings.setValue(LAST_KEY, path)
    save_last_choice(win.settings, cur)
    from .progress import Cancelled, run
    try:                                                 # relecture d'un gros fichier : dans le fil de calcul
        ok, report = run(win, tr('Vérification de {0}').format(pathlib.Path(path).name), verify_export, path,
                         expected)
    except Cancelled:
        ok, report = True, tr('vérification annulée')
    except Exception as ex:                              # noqa: BLE001 — la vérification ne doit pas faire taire l'export
        from .. import journal
        journal.record(type(ex), ex, ex.__traceback__, where='vérification de l’export')
        ok, report = False, str(ex)
    win.statusBar().showMessage(tr('Exporté : {0}').format(path) + ' — ' + report, 8000)
    from .reveal import done_message
    text = tr('Exporté : {0}').format(path) + '\n' + (tr('Vérifié : {0}').format(report) if ok
                                                     else tr('À vérifier : {0}').format(report))
    box = done_message(win, tr('Exporter'), text, path)
    if not ok:
        box.setIcon(QMessageBox.Icon.Warning)
    win._export_report = box
    return path
