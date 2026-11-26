"""Informations et comptes rendus d'un parcours d'usinage (manuel de TE, pages 665 à 672 imprimées) : la fenêtre des informations,
le choix du contenu, le compte rendu du parcours et le compte rendu final, en PDF."""
from __future__ import annotations

import html
import math
import pathlib
from dataclasses import dataclass

from PySide6.QtCore import QRectF, QUrl
from PySide6.QtGui import QImage, QPageSize, QPdfWriter, QPixmap, QTextDocument
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGridLayout,
                               QGroupBox, QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout)

from ..cam import model as M
from ..cam import strategies, timing as TM
from ..i18n import tr


def _mm(v: float, digits: int = 3) -> str:
    return f'{float(v):.{digits}f} mm'.replace('.', ',')


def nature(paths) -> str:
    """'2D' : une seule cote de coupe. '2,5D' : plusieurs cotes, à plat. '3D' : l'outil descend surtout en avançant. Une rampe
    d'entrée, courte devant le reste, ne change rien."""
    levels, flat, sloped = set(), 0.0, 0.0
    for tp in paths:
        prev = None
        for m in tp.moves:
            if prev is not None and m.kind != 'rapid':
                if m.is_arc:
                    d = M.arc_length((prev.x, prev.y, prev.z), m)
                else:
                    d = math.hypot(m.x - prev.x, m.y - prev.y)
                if d > 1e-6:
                    if abs(m.z - prev.z) > 1e-6:
                        sloped += d
                    else:
                        flat += d
                        levels.add(round(m.z, 4))
            prev = m
    if sloped > flat:
        return '3D'
    return '2,5D' if len(levels) > 1 else '2D'


def plan_names(doc, op) -> list:
    """Les plans (calques) des objets usinés par l'opération, dans l'ordre du document."""
    used = {id(it) for it in strategies.source_items(doc, op)}

    def has(it) -> bool:
        return id(it) in used or any(has(c) for c in getattr(it, 'children', ()))
    return [L.name for L in doc.layers if any(has(it) for it in L.items)]


def facts(doc, setup, op, paths, spec=None) -> dict:
    """Ce qu'on sait du parcours d'une opération : longueurs en mm (dans la matière, en rapide), durée en s, encombrement."""
    feed = rapid = seconds = 0.0
    boxes = []
    for tp in paths:
        a, b = tp.lengths()
        feed, rapid = feed + a, rapid + b
        seconds += TM.path_seconds(tp, setup, spec or TM.TimingSpec())
        if tp.bbox() is not None:
            boxes.append(tp.bbox())
    box = None
    if boxes:
        box = tuple(min(b[i] for b in boxes) for i in range(3)) + tuple(max(b[i] for b in boxes) for i in range(3, 6))
    return {'feed': feed, 'rapid': rapid, 'seconds': seconds, 'box': box, 'nature': nature(paths), 'plans': plan_names(doc, op),
            'kind': M.OP_KINDS.get(op.kind, op.kind), 'depth': op.depth, 'z_start': op.z_start}


@dataclass
class ReportOptions:
    """Le contenu choisi (TE : Contenu du compte rendu du parcours outil)."""
    tool_general: bool = True
    tool_geometry: bool = True
    feeds: bool = True
    spindle: bool = True
    path_general: bool = True
    duration: bool = True
    length: bool = True
    use_factor: bool = False
    factor: float = 100.0                                # % de la durée (compte rendu final)
    notes: str = ''                                      # vide : pas de notes
    image: str = ''                                      # vide : pas d'image
    show_pdf: bool = True

    def duration_of(self, seconds: float) -> float:
        """La durée totale : multipliée par le facteur, s'il est choisi."""
        return seconds * self.factor / 100.0 if self.use_factor else seconds


CSS = ('body{font-family:Arial,sans-serif;font-size:10pt} h1{font-size:18pt} h2{font-size:11pt;margin:10px 0 2px 0} '
       'h3{font-size:10pt;margin:6px 0 2px 0} p{margin:1px 0 1px 12px} td,th{padding:4px}')


def _lines(rows) -> str:
    return ''.join(f'<p>{html.escape(a)} : {html.escape(str(b))}</p>' for a, b in rows if b not in ('', None))


def _h2(text: str) -> str:
    return f'<h2>{html.escape(text)}</h2>'


def _h3(text: str) -> str:
    return f'<h3>{html.escape(text)}</h3>'


def _head(title: str, sub: str = '') -> str:
    return f'<html><head><style>{CSS}</style></head><body><h1>{html.escape(title)}</h1>' + (f'<p>{html.escape(sub)}</p>' if sub else '')


def toolpath_html(doc, setup, op, paths, opts: ReportOptions, *, spec=None, file_name: str = '', image: bool = False) -> str:
    """Le compte rendu du parcours d'une opération. `image` : la ressource « image » du document est prête."""
    f = facts(doc, setup, op, paths, spec)
    tool = setup.tool(op.tool_id)
    out = [_head(tr('Compte rendu'), tr('Fichier : {0}').format(file_name) if file_name else '')]
    if opts.path_general:
        out.append(_h2(tr('Informations sur le parcours outil')))
        rows = [(tr('Nom du parcours'), op.name), (tr('Z de référence'), _mm(f['z_start'])), (tr('Profondeur totale'), _mm(f['depth'])),
                (tr('Type du parcours'), tr(f['kind']))]
        if f['box'] is not None:
            b = f['box']
            rows += [(tr('Cadre englobant, mini'), f'{_mm(b[0])} ; {_mm(b[1])} ; {_mm(b[2])}'),
                     (tr('Cadre englobant, maxi'), f'{_mm(b[3])} ; {_mm(b[4])} ; {_mm(b[5])}')]
        rows += [('2D / 2,5D / 3D', f['nature']), (tr('Nom du plan'), ', '.join(f['plans']))]
        out.append(_lines(rows))
    if tool is not None and (opts.tool_general or opts.tool_geometry):
        out.append(_h2(tr('Informations sur l\'outil')))
        if opts.tool_general:
            out.append(_h3(tr('Paramètres généraux')))
            out.append(_lines([(tr('Nom de l\'outil'), tool.name), (tr('Référence'), tool.ref), (tr('Fournisseur'), tool.vendor)]))
        if opts.tool_geometry:
            out.append(_h3(tr('Géométrie')))
            out.append(_lines([(tr('Numéro'), tool.number), (tr('Forme'), tr(M.TOOL_KINDS.get(tool.kind, tool.kind))),
                               (tr('Angle'), f'{tool.angle:g}°'.replace('.', ',') if tool.angle else ''),
                               (tr('Troncature'), _mm(tool.tip) if tool.tip else ''), (tr('Diamètre de l\'outil'), _mm(tool.diameter))]))
    if tool is not None and (opts.feeds or opts.spindle):
        out.append(_h2(tr('Vitesse')))
        if opts.feeds:
            out.append(_lines([(tr('Vitesse de plongée'), f'{(op.plunge or tool.plunge):g} mm/min'.replace('.', ',')),
                               (tr('Vitesse d\'avance'), f'{M.op_feed(op, tool):g} mm/min'.replace('.', ','))]))
        if opts.spindle:
            out.append(_lines([(tr('Vitesse de la broche'), f'{(op.spindle or tool.spindle):g} tr/min'.replace('.', ','))]))
    if opts.duration or opts.length:
        out.append(_h2(tr('Durée et longueur du parcours outil')))
        out.append(_lines(([(tr('Durée'), TM.format_duration(f['seconds']))] if opts.duration else [])
                          + ([(tr('Longueur d\'usinage'), _mm(f['feed'], 1))] if opts.length else [])))
    if image:
        out.append('<p><img src="image" width="500"></p>')
    out.append('</body></html>')
    return ''.join(out)


def final_html(doc, setup, ops, paths, opts: ReportOptions, *, spec=None, file_name: str = '') -> str:
    """Le compte rendu final : les parcours, leur outil et leur numéro, la durée totale (multipliée par le facteur), les notes."""
    out = [_head(tr('Compte rendu final'), tr('Fichier : {0}').format(file_name) if file_name else '')]
    heads = ''.join(f'<th>{html.escape(t)}</th>' for t in (tr('Nom du parcours'), tr('Nom de l\'outil'), tr('Numéro')))
    out.append(f'<table border="1" cellspacing="0" width="100%"><tr>{heads}</tr>')
    seconds = length = 0.0
    for op in ops:
        tool = setup.tool(op.tool_id)
        mine = [tp for tp in paths if tp.op_id == op.id]
        f = facts(doc, setup, op, mine, spec)
        seconds, length = seconds + f['seconds'], length + f['feed']
        name, number = (tool.name, tool.number) if tool is not None else ('?', '')
        out.append(f'<tr><td>{html.escape(op.name or tr(f["kind"]))}</td><td>{html.escape(name)}</td><td>{number}</td></tr>')
    out.append('</table>')
    if opts.duration or opts.length:
        out.append(_h2(tr('Durée totale et longueur d\'usinage')))
        out.append(_lines(([(tr('Durée totale d\'usinage'), TM.format_duration(opts.duration_of(seconds)))] if opts.duration else [])
                          + ([(tr('Facteur'), f'{opts.factor:g} %'.replace('.', ','))] if opts.duration and opts.use_factor else [])
                          + ([(tr('Longueur totale d\'usinage'), _mm(length, 1))] if opts.length else [])))
    if opts.notes.strip():
        text = html.escape(opts.notes.strip()).replace(chr(10), '<br>')
        out.append(_h2(tr('Notes')) + f'<p>{text}</p>')
    out.append('</body></html>')
    return ''.join(out)


def report_names(source: str, folder: str = '') -> tuple:
    """Les noms proposés : NOM_000_ReportByToolpath.pdf et NOM_000_FinalReport.pdf, dans le dossier du dessin, au premier numéro libre."""
    src = pathlib.Path(source) if source else None
    stem = src.stem if src is not None else 'Parcours'
    where = src.parent if src is not None else pathlib.Path(folder or '.')
    for i in range(1000):
        a, b = where / f'{stem}_{i:03d}_ReportByToolpath.pdf', where / f'{stem}_{i:03d}_FinalReport.pdf'
        if not a.exists() and not b.exists():
            return str(a), str(b)
    return str(where / f'{stem}_ReportByToolpath.pdf'), str(where / f'{stem}_FinalReport.pdf')


def write_pdf(path: str, text: str, title: str, image='') -> None:
    """Écrit le PDF, avec l'image (un chemin ou une QImage) en ressource « image ». OSError si le fichier n'est pas accessible
    (ouvert dans un lecteur, par exemple)."""
    with open(path, 'ab'):                               # QPdfWriter n'en dit rien et laisse un PDF vide
        pass
    writer = QPdfWriter(str(pathlib.Path(path)))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setResolution(150)
    writer.setTitle(title)
    td = QTextDocument()
    td.documentLayout().setPaintDevice(writer)           # les tailles de police comptent en vrais points
    from ..io.raster import read_qimage
    picture = image if isinstance(image, QImage) else (read_qimage(str(image)) if image else QImage())
    if not picture.isNull():
        td.addResource(QTextDocument.ResourceType.ImageResource.value, QUrl('image'), picture)
    td.setHtml(text)
    td.setPageSize(QRectF(0, 0, writer.width(), writer.height()).size())
    td.print_(writer)


def image_ok(path: str) -> bool:
    from ..io.raster import read_qimage
    return bool(path) and not read_qimage(str(path)).isNull()


class PathInfoDialog(QDialog):
    """Informations du parcours outil."""

    def __init__(self, parent, source: str, f: dict):
        super().__init__(parent)
        self.setWindowTitle(tr('Informations du parcours outil'))
        form = QFormLayout(self)
        self.rows = {}

        def row(label: str, value: str) -> None:
            w = QLabel(value)
            self.rows[label] = w
            form.addRow(tr(label), w)
        row('Chemin d\'accès', source or tr('Dessin non enregistré'))
        row('Type de parcours', tr(f['kind']))
        row('Distance d\'usinage', _mm(f['feed'], 1))
        row('Distance d\'usinage rapide', _mm(f['rapid'], 1))
        row('Durée d\'usinage', TM.format_duration(f['seconds']))
        if f['box'] is not None:
            for name, value in zip(('X mini', 'Y mini', 'Z mini', 'X maxi', 'Y maxi', 'Z maxi'), f['box']):
                row(name, _mm(value))
        row('Profondeur', _mm(f['depth']))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)


class PathReportDialog(QDialog):
    """Le contenu du compte rendu. Après OK : `options()`."""

    def __init__(self, parent, heading: str = ''):
        super().__init__(parent)
        self.setWindowTitle(tr('Contenu du compte rendu du parcours outil'))
        self.image_path = ''
        lay = QVBoxLayout(self)
        if heading:
            lay.addWidget(QLabel(heading))
        grid = QGridLayout()
        lay.addLayout(grid, 1)

        def box(title: str, r: int, c: int, span: int = 1):
            g = QGroupBox(title)
            v = QVBoxLayout(g)
            grid.addWidget(g, r, c, span, 1)
            return v

        def check(v, text: str, hint: str = '') -> QCheckBox:
            b = QCheckBox(tr(text))
            b.setChecked(True)
            v.addWidget(b)
            if hint:
                h = QLabel(tr(hint))
                h.setEnabled(False)
                h.setWordWrap(True)
                v.addWidget(h)
            return b
        v = box(tr('Informations sur l\'outil'), 0, 0)
        self.tool_general = check(v, 'Paramètres généraux', 'Nom, référence, fournisseur')
        self.tool_geometry = check(v, 'Géométrie', 'Numéro, forme, angle, troncature, diamètre')
        v = box(tr('Vitesse'), 0, 1)
        self.feeds = check(v, 'Avance', 'Vitesse de plongée, vitesse d\'avance')
        self.spindle = check(v, 'Broche', 'Vitesse de rotation')
        v = box(tr('Informations sur le parcours outil'), 1, 0)
        self.path_general = check(v, 'Paramètres généraux', 'Z de référence, profondeur totale, type du parcours, cadre englobant, 2D, 2,5D ou 3D, nom du plan')
        v = box(tr('Durée et longueur du parcours outil'), 1, 1)
        self.duration = check(v, 'Durée')
        self.length = check(v, 'Longueur du parcours')
        self.use_factor = check(v, 'Facteur')
        self.use_factor.setChecked(False)
        self.use_factor.setToolTip(tr('La durée totale du compte rendu final est multipliée par ce pourcentage, selon le réglage de la machine'))
        self.factor = QDoubleSpinBox()
        self.factor.setRange(1.0, 1000.0)
        self.factor.setDecimals(1)
        self.factor.setSuffix(' %')
        self.factor.setValue(100.0)
        self.factor.setEnabled(False)
        self.use_factor.toggled.connect(self.factor.setEnabled)
        v.addWidget(self.factor)
        v = box(tr('Notes'), 0, 2)
        self.use_notes = check(v, 'Notes')
        self.use_notes.setChecked(False)
        self.notes = QPlainTextEdit()
        self.notes.setEnabled(False)
        self.notes.setToolTip(tr('Elles figurent dans le compte rendu final'))
        self.use_notes.toggled.connect(self.notes.setEnabled)
        v.addWidget(self.notes, 1)
        v = box(tr('Image'), 1, 2)
        self.use_image = check(v, 'Ajouter une image')
        self.use_image.setChecked(False)
        self.use_image.toggled.connect(self._image_toggled)
        self.preview = QLabel()
        v.addWidget(self.preview, 1)
        row = QHBoxLayout()
        self.show_pdf = QCheckBox(tr('Afficher les comptes rendus en PDF'))
        self.show_pdf.setChecked(True)
        row.addWidget(self.show_pdf)
        row.addStretch(1)
        lay.addLayout(row)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def _image_toggled(self, on: bool) -> None:
        if on and not self.image_path:
            from ..io import heif, raster
            path, _ = QFileDialog.getOpenFileName(self, tr('Ajouter une image'), '',
                                                  tr('Images ({0})').format(raster.image_patterns()))
            if not self.set_image(path):
                self.use_image.setChecked(False)
                why = heif.problem(path) if path else ''
                if why:                                  # HEIC sans décodeur : dit quoi installer
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.warning(self, tr('Ajouter une image'), why)
        elif not on:
            self.set_image('')

    def set_image(self, path: str) -> bool:
        """L'image du compte rendu ; False si le fichier n'est pas une image lisible."""
        from ..io.raster import read_qimage
        img = read_qimage(path)                          # HEIC compris, photo redressée
        if img.isNull():
            self.image_path = ''
            self.preview.clear()
            return False
        self.image_path = path
        self.preview.setPixmap(QPixmap.fromImage(img).scaledToWidth(180))
        return True

    def options(self) -> ReportOptions:
        return ReportOptions(tool_general=self.tool_general.isChecked(), tool_geometry=self.tool_geometry.isChecked(),
                             feeds=self.feeds.isChecked(), spindle=self.spindle.isChecked(),
                             path_general=self.path_general.isChecked(), duration=self.duration.isChecked(),
                             length=self.length.isChecked(), use_factor=self.use_factor.isChecked(), factor=self.factor.value(),
                             notes=self.notes.toPlainText() if self.use_notes.isChecked() else '',
                             image=self.image_path if self.use_image.isChecked() else '', show_pdf=self.show_pdf.isChecked())
