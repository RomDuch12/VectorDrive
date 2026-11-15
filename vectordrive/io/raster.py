"""Images bitmap : ouverture d'une image comme document (à sa taille
réelle, d'après sa résolution) et export du dessin en PNG ou JPEG.

Qt (QtGui) sert au décodage et au rendu ; il faut une QGuiApplication
(l'interface en a une ; les outils en ligne de commande en créent une).
"""
from __future__ import annotations

import pathlib
import struct
from dataclasses import dataclass

from ..core.document import Document, Group, Image, Shape, Text
from ..core.geom import Affine, Path

MM_PER_INCH = 25.4


def _app():
    from PySide6.QtGui import QGuiApplication
    return QGuiApplication.instance() or QGuiApplication([])


def qimage_of(item):
    """QImage d'un objet Image du dessin (DIB comme TypeEdit, PNG…) ; None
    si elle ne se lit pas."""
    from PySide6.QtGui import QImage
    if item.fmt == 'dib':
        from ..ui.canvas import dib_to_qimage
        q = dib_to_qimage(item.data)
    else:
        q = QImage.fromData(item.data)
    return None if q is None or q.isNull() else q


# --- lecture ----------------------------------------------------------------------

def image_size_mm(img, default_dpi: float = 96.0) -> tuple[float, float]:
    """Taille en mm d'une QImage d'après sa résolution (96 dpi si absente)."""
    dpmx, dpmy = img.dotsPerMeterX(), img.dotsPerMeterY()
    dx = dpmx / 1000.0 if dpmx > 100 else default_dpi / MM_PER_INCH
    dy = dpmy / 1000.0 if dpmy > 100 else default_dpi / MM_PER_INCH
    return img.width() / dx, img.height() / dy


#: pixels au-delà desquels une image est réduite à l'ouverture (≈ 7 000 × 7 000, 200 Mo décodés)
MAX_PIXELS = 50_000_000


def load_image(path, max_pixels: int | None = None):
    """QImage d'un fichier image, quelle que soit sa taille. Qt refuse par
    défaut toute image de plus de 256 Mo décodés (une photo de 8 200 px de
    côté) : la limite est levée, et une image de plus de `max_pixels` est
    réduite à la lecture (JPEG : décodage réduit, l'original n'est jamais
    chargé). Rend (image, taille d'origine en px, remarque ou None) ;
    ValueError avec la raison de Qt si elle ne se lit pas."""
    import math
    _app()
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QImageReader
    QImageReader.setAllocationLimit(0)
    r = QImageReader(str(path))
    r.setAutoTransform(True)                         # photo de téléphone : redressée d'après l'orientation EXIF
    size = r.size()
    cap = MAX_PIXELS if max_pixels is None else max_pixels
    note = None
    if size.isValid() and cap and size.width() * size.height() > cap:
        k = math.sqrt(cap / (size.width() * size.height()))
        w, h = max(1, int(size.width() * k)), max(1, int(size.height() * k))
        r.setScaledSize(QSize(w, h))
        note = f'image réduite de {size.width()} × {size.height()} à {w} × {h} px à l\'ouverture'
    img = r.read()
    if img.isNull():
        raise ValueError(f'image illisible : {pathlib.Path(path).name} ({r.errorString()})')
    if size.isValid() and r.transformation().value & 4:  # tournée d'un quart de tour : côtés échangés
        size = QSize(size.height(), size.width())
        if note:
            note = note.replace(f'à {w} × {h} px', f'à {h} × {w} px')
    return img, (size if size.isValid() else img.size()), note


def read(path) -> Document:
    from PySide6.QtCore import QBuffer, QIODevice
    img, orig, note = load_image(path)
    w_mm, h_mm = image_size_mm(img)
    if (img.width(), img.height()) != (orig.width(), orig.height()):     # réduite : taille réelle de l'original
        w_mm, h_mm = w_mm * orig.width() / img.width(), h_mm * orig.height() / img.height()
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, 'PNG')
    im = Image(data=bytes(buf.data()), fmt='png', matrix=Affine(w_mm, 0, 0, -h_mm, 0, h_mm),
               name=pathlib.Path(path).stem)
    doc = Document(source_path=str(path), source_format='image')
    doc.add(im)
    doc.report.append(f'image {orig.width()} × {orig.height()} px, {w_mm:.1f} × {h_mm:.1f} mm')
    if note:
        doc.report.append(note)
    return doc


def to_dib(data: bytes, fmt: str) -> bytes | None:
    """Image (PNG, JPEG…) → DIB 24 bits (BITMAPINFOHEADER + pixels), la
    forme que TypeEdit range dans ses VND."""
    if fmt == 'dib':
        return data
    _app()
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtGui import QColor, QImage, QPainter
    img = QImage.fromData(data)
    if img.isNull():
        return None
    flat = QImage(img.size(), QImage.Format.Format_RGB888)
    flat.fill(QColor('white'))
    p = QPainter(flat)
    p.drawImage(0, 0, img)
    p.end()
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    flat.save(buf, 'BMP')
    bmp = bytes(buf.data())
    return bmp[14:] if bmp[:2] == b'BM' else None


# --- export -------------------------------------------------------------------------

@dataclass
class RasterSpec:
    dpi: float = 300.0
    transparent: bool = False
    include_plate: bool = True
    margin: float = 2.0              # mm autour du dessin
    line_mm: float = 0.1             # épaisseur des traits (mm)
    filled: bool = False             # contours fermés remplis (pair-impair)
    tool_widths: bool = True         # largeur de l'outil quand elle est connue
    tool_colors: bool = True         # traits à la couleur de leur outil (sinon noirs)
    orientation: bool = False        # sens des contours : vert anti-horaire, bleu horaire, noir ouvert


def _leaves(items):
    for it in items:
        if not it.visible:
            continue
        if isinstance(it, Group):
            yield from _leaves(it.children)
        else:
            yield it


def render(doc: Document, spec: RasterSpec):
    """Dessin → QImage à `spec.dpi` (repère : y vers le haut)."""
    _app()
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QTransform
    bb = doc.bbox(include_plate=spec.include_plate and doc.plate is not None)
    if not bb:
        raise ValueError('dessin vide : rien à exporter')
    m = spec.margin
    x0, y0, x1, y1 = bb[0] - m, bb[1] - m, bb[2] + m, bb[3] + m
    k = spec.dpi / MM_PER_INCH                    # px par mm
    W, H = max(1, int(round((x1 - x0) * k))), max(1, int(round((y1 - y0) * k)))
    if W * H > 400_000_000:
        raise ValueError(f'image trop grande ({W} × {H} px) : baisser la résolution')
    img = QImage(W, H, QImage.Format.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0) if spec.transparent else QColor('white'))
    dpm = int(round(k * 1000))
    img.setDotsPerMeterX(dpm)
    img.setDotsPerMeterY(dpm)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    view = QTransform(k, 0, 0, -k, -x0 * k, y1 * k)

    def qpath(path: Path) -> QPainterPath:
        q = QPainterPath()
        q.setFillRule(Qt.FillRule.OddEvenFill)
        for poly, closed in ((c.flatten(0.25 / k), c.closed) for c in path.contours if c.segments):
            q.moveTo(*poly[0])
            for pt in poly[1:]:
                q.lineTo(*pt)
            if closed:
                q.closeSubpath()
        return q
    if spec.include_plate and doc.plate is not None and doc.plate.visible:
        from ..core import geom
        pl = doc.plate
        p.setTransform(view)
        p.setPen(QPen(QColor('#8a7a50'), 0))
        p.setBrush(QColor('#e8e2d0'))
        p.drawPath(qpath(Path([geom.rect(pl.x, pl.y, pl.width, pl.height, pl.corner_radius)])))
    for L in doc.layers:
        if not L.visible:
            continue
        for leaf in _leaves(L.items):
            p.setTransform(view)
            if isinstance(leaf, Image):
                from ..ui.canvas import dib_to_qimage
                q = dib_to_qimage(leaf.data) if leaf.fmt == 'dib' else QImage.fromData(leaf.data)
                if q is None or q.isNull():
                    continue
                mm = leaf.matrix
                t = QTransform(mm.a / q.width(), mm.b / q.width(), mm.c / q.height(), mm.d / q.height(), mm.e, mm.f)
                p.setTransform(t * view)
                p.drawImage(0, 0, q)
                continue
            path = leaf.path if isinstance(leaf, Shape) else (leaf.outline if isinstance(leaf, Text) else None)
            if not path:
                continue
            color = QColor(doc.item_color(leaf) if spec.tool_colors else '#000000')
            tw = doc.tool_width(leaf.tool) if spec.tool_widths else 0.0
            pen = QPen(color, tw if tw > 0 else max(spec.line_mm, 0.0))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            if spec.filled or getattr(leaf, 'filled', False):
                c2 = QColor(color)
                p.setBrush(c2)
            else:
                p.setBrush(Qt.BrushStyle.NoBrush)
            if spec.orientation:
                from ..core.orient import COLORS, split
                if p.brush().style() != Qt.BrushStyle.NoBrush:
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawPath(qpath(path))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                for key, part in split(path).items():
                    op = QPen(pen)
                    op.setColor(QColor(COLORS[key]))
                    p.setPen(op)
                    p.drawPath(qpath(part))
                continue
            p.drawPath(qpath(path))
    p.end()
    return img


def write(doc: Document, path, spec: RasterSpec | None = None) -> None:
    spec = spec or RasterSpec()
    img = render(doc, spec)
    suffix = pathlib.Path(path).suffix.lower()
    if suffix in ('.jpg', '.jpeg', '.bmp'):                # sans transparence : fond blanc
        from PySide6.QtGui import QColor, QImage, QPainter
        flat = QImage(img.size(), QImage.Format.Format_RGB32)
        flat.fill(QColor('white'))
        flat.setDotsPerMeterX(img.dotsPerMeterX())
        flat.setDotsPerMeterY(img.dotsPerMeterY())
        p = QPainter(flat)
        p.drawImage(0, 0, img)
        p.end()
        img = flat
    ok = img.save(str(path), None, 92 if suffix in ('.jpg', '.jpeg') else -1)
    if not ok:
        raise ValueError(f'écriture impossible : {path}')


def dib_info(data: bytes) -> tuple[int, int, int]:
    """(largeur, hauteur, bits par pixel) d'une DIB."""
    _h, w, hh, _pl, bpp = struct.unpack_from('<IiiHH', data, 0)
    return w, abs(hh), bpp
