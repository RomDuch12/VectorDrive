"""Registre des formats : extension → lecteur / écrivain. Les programmes
machine (SimPl, CLJOB…) sont apportés par les plugins (`Api.add_format`)."""
from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Callable

from ..core.document import Document


@dataclass(frozen=True)
class Format:
    key: str
    label: str
    extensions: tuple[str, ...]
    reader: Callable[[str], Document] | None = None
    writer: Callable[[Document, str], None] | None = None
    export: Callable | None = None          # export(fenêtre, chemin) : réglages puis écriture (plugins)
    machine: bool = False                   # programme machine : dessin vérifié avant l'écriture
    save_label: str = ''                    # libellé à l'écriture, quand elle ne fait pas l'inverse de la lecture

    def written_label(self) -> str:
        """Le libellé du format dans « Enregistrer sous » et « Exporter »."""
        return self.save_label or self.label


def _lazy(module: str, attr: str):
    def call(*a, **k):
        import importlib
        mod = importlib.import_module(f'vectordrive.io.{module}')
        return getattr(mod, attr)(*a, **k)
    return call


FORMATS: tuple[Format, ...] = (
    Format('vdz', 'VectorDrive', ('.vdz',), _lazy('native', 'read'), _lazy('native', 'write')),
    Format('vnd', 'TypeEdit / Gravostyle', ('.vnd',), _lazy('vnd', 'read'), _lazy('vnd_write', 'write')),
    Format('dxf', 'AutoCAD DXF', ('.dxf',), _lazy('dxf', 'read'), _lazy('dxf', 'write')),
    Format('dwg', 'AutoCAD DWG (par ODA File Converter)', ('.dwg',), _lazy('dwg', 'read'), _lazy('dwg', 'write')),
    Format('svg', 'SVG', ('.svg',), _lazy('svg', 'read'), _lazy('svg', 'write')),
    Format('pdf', 'PDF', ('.pdf',), _lazy('pdf', 'read'), _lazy('pdf', 'write')),
    Format('ai', 'Adobe Illustrator', ('.ai',), _lazy('registry', '_read_ai'), _lazy('pdf', 'write')),
    Format('step', 'STEP (vue de dessus)', ('.stp', '.step'), _lazy('step', 'read'), _lazy('write3d', 'write_step'),
           save_label='STEP (le dessin en volume)'),
    Format('iges', 'IGES (vue de dessus)', ('.igs', '.iges'), _lazy('iges', 'read'), _lazy('iges_write', 'write'),
           save_label='IGES'),
    Format('mesh', 'STL / 3D XML (vue de dessus)', ('.stl', '.3dxml'), _lazy('mesh3d', 'read'),
           _lazy('write3d', 'write_mesh'), save_label='STL / 3D XML (le dessin en volume)'),
    Format('catia', 'CATIA (par un convertisseur en STEP)', ('.catpart', '.catproduct', '.cgr', '.catdrawing'),
           _lazy('mesh3d', 'read_catia'), None),
    Format('eps', 'EPS / PostScript', ('.eps', '.ps'), _lazy('postscript', 'read'), _lazy('postscript', 'write')),
    Format('smb', 'Symbole TypeEdit', ('.smb',), _lazy('smb', 'read'), _lazy('smb', 'write_document')),
    Format('gvt', 'TypeEdit GVT', ('.gvt',), _lazy('vnd', 'read'), None),
    # dessin LaserType et modèle TypeEdit : la même archive que le VND, écrite de même (TypeEdit 13 les rouvre)
    Format('vnl', 'Dessin LaserType', ('.vnl',), _lazy('vnd', 'read'), _lazy('vnd_write', 'write')),
    Format('vnm', 'Modèle TypeEdit', ('.vnm',), _lazy('vnd', 'read'), _lazy('vnd_write', 'write')),
    Format('image', 'Image (PNG, JPEG…)', ('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff', '.gif'),
           _lazy('raster', 'read'), _lazy('raster', 'write')),
    Format('hpgl', 'HPGL (traceurs, découpeuses)', ('.plt', '.hpgl', '.hpg', '.hgl', '.gl2'), _lazy('hpgl', 'read'), _lazy('hpgl', 'write')),
    Format('inkscape', 'CorelDRAW, EMF, WMF, Visio (par Inkscape)', ('.cdr', '.cmx', '.emf', '.wmf', '.vsd', '.vsdx', '.wpg'),
           _lazy('inkscape_import', 'read'), None),
    # écrits par Inkscape ; après le format qui les lit : `by_extension` rend celui-là, `writer_for` celui-ci
    Format('metafile', 'EMF, WMF (par Inkscape)', ('.emf', '.wmf'), _lazy('inkscape_import', 'read'),
           _lazy('inkscape_export', 'write')),
)


def _read_ai(path):
    """Illustrator ≥ 9 = PDF ; ≤ 8 = PostScript."""
    from . import pdf, postscript
    if pdf.sniff(path) == 'pdf':
        doc = pdf.read(path)
    else:
        doc = postscript.read(path)
    doc.source_format = 'ai'
    return doc


def all_formats() -> tuple[Format, ...]:
    """Formats du cœur, puis ceux des plugins chargés."""
    try:
        from ..plugins import REGISTRY
        extra = tuple(Format(s.key, s.label, tuple(s.extensions), s.read, s.write, s.export, s.machine)
                      for s in REGISTRY.formats)
    except Exception:                               # pragma: no cover - registre illisible
        extra = ()
    return FORMATS + extra


def by_extension(path) -> Format | None:
    ext = pathlib.Path(path).suffix.lower()
    for f in all_formats():
        if ext in f.extensions:
            return f
    return None


class UnreadableFile(ValueError):
    """Fichier endommagé ou d'une variante non lue : l'erreur de la
    bibliothèque de lecture (zip, PDF, DXF…) gardée en détail."""

    def __init__(self, path, label: str, cause: Exception):
        from ..i18n import tr
        self.cause = cause
        super().__init__(tr('Fichier endommagé ou illisible ({0}) : {1}').format(label, pathlib.Path(path).name)
                         + f'\n({type(cause).__name__} : {str(cause)[:200]})')


def read_for_open(path: str):
    """Document lu pour l'ouverture, ou l'exception rencontrée (rendue, pas
    levée : une lecture de plusieurs fichiers en processus continue)."""
    try:
        return open_document(path)
    except Exception as ex:                              # noqa: BLE001 — rendue à l'appelant
        return ex


def open_document(path) -> Document:
    f = by_extension(path)
    if f is None or f.reader is None:
        raise ValueError(f'format non pris en charge en lecture : {pathlib.Path(path).suffix}')
    try:
        doc = f.reader(str(path))
    except (OSError, ValueError, MemoryError):
        raise
    except Exception as ex:                       # fichier abîmé : erreur interne d'une bibliothèque de lecture
        raise UnreadableFile(path, f.label, ex) from ex
    doc.source_path = str(path)
    doc.source_format = doc.source_format or f.key
    if f.key not in ('vnd', 'vnl', 'vdz'):
        doc.infer_layer_tools()
    return doc


def writer_for(path) -> Format | None:
    """Le format qui écrit `path` : le premier, pour son extension, qui a un écrivain."""
    ext = pathlib.Path(path).suffix.lower()
    return next((f for f in all_formats() if ext in f.extensions and f.writer is not None), None)


def save_document(doc: Document, path) -> None:
    f = writer_for(path)
    if f is None or f.writer is None:
        raise ValueError(f'format non pris en charge en écriture : {pathlib.Path(path).suffix}')
    from ..core.text import ensure_outlines
    ensure_outlines(doc)                             # textes jamais affichés : contours calculés avant d'écrire
    if f.key != 'vdz':                               # une plaque de reprise posée : un repère de VectorDrive, écrit
        from ..cam.fixture import without_plates     # dans le VDZ seulement (réponse du 15/11 à la question 35) ;
        doc = without_plates(doc)                    # le compagnon la garde (`companion.reasons`)
    f.writer(doc, str(path))


def save_formats() -> list:
    """Formats d'« Enregistrer sous » : ceux qu'on sait écrire comme des dessins — pas les programmes machine, qui
    s'exportent avec leurs réglages."""
    return [f for f in all_formats() if f.writer is not None and not f.machine]


def filter_string(*, write: bool = False) -> str:
    """Filtre pour les boîtes de dialogue Qt."""
    fmts = [f for f in all_formats() if ((f.writer or f.export) if write else f.reader)]
    parts = []
    if not write:
        all_ext = ' '.join(f'*{e}' for f in fmts for e in f.extensions)
        parts.append(f'Tous les dessins ({all_ext})')
    for f in fmts:
        parts.append(f'{f.written_label() if write else f.label} ({" ".join("*" + e for e in f.extensions)})')
    return ';;'.join(parts)
