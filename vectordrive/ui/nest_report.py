"""Le rapport d'imbrication en PDF : les réglages, puis chaque plan rempli avec son dessin."""
from __future__ import annotations

import html
import pathlib

from PySide6.QtCore import QPointF, QRectF, Qt, QUrl
from PySide6.QtGui import QColor, QImage, QPainter, QPageSize, QPainterPath, QPdfWriter, QPen, QTextDocument

from ..core.nest_report import plane_rows
from ..core.nesting_shape import _leaf_contours
from ..i18n import tr

IMAGE_W, IMAGE_H = 900, 600


def _yes(value) -> str:
    return tr('Oui') if value else tr('Non')


def _settings_rows(kept: dict) -> list[tuple[str, str]]:
    """Les réglages de la dernière imbrication ; rien si le document n'en a pas eu."""
    if not kept:
        return []
    corner = {'haut_gauche': tr('En haut à gauche'), 'haut_droit': tr('En haut à droite'),
              'bas_gauche': tr('En bas à gauche'), 'bas_droit': tr('En bas à droite')}
    rows = [(tr('Marge au bord de la plaque (mm)'), f"{kept.get('margin', 0):g}"),
            (tr('Écart entre objets (mm)'), f"{kept.get('gap', 0):g}"),
            (tr('Quart de tour permis'), _yes(kept.get('allow_rotate'))),
            (tr('Selon la vraie forme des objets (sinon : leurs rectangles)'), _yes(kept.get('shape')))]
    if kept.get('shape'):
        rows += [(tr('Forme : angles permis (°, ex. 0;90;180 ; vide : d’après le pas)'), str(kept.get('angles', ''))),
                 (tr('Forme : pas de rotation (°, 90 : quarts de tour)'), f"{kept.get('angle_step', 0):g}"),
                 (tr('Forme : ranger aussi dans les trous des autres'), _yes(kept.get('in_holes'))),
                 (tr('Forme : retournement permis (miroir)'), _yes(kept.get('allow_mirror'))),
                 (tr('Forme : précision (mm ; plus fin : plus serré, plus long)'), f"{kept.get('precision', 0):g}")]
    rows += [(tr('Point de départ'), corner.get(str(kept.get('corner')), str(kept.get('corner', '')))),
             (tr('Direction'), tr('Verticale') if kept.get('vertical') else tr('Horizontale')),
             (tr('Plaques utilisées'), str(kept.get('plates', 0))),
             (tr('Objets rangés'), str(kept.get('placed', 0))),
             (tr('Objets qui n’ont pas tenu'), str(kept.get('unplaced', 0)))]
    if kept.get('tries'):
        rows += [(tr('Optimiseur : essais faits'), str(kept['tries'])),
                 (tr('Optimiseur : meilleure direction'),
                  tr('Verticale') if kept.get('best_vertical') else tr('Horizontale')),
                 (tr('Optimiseur : remplissage du meilleur essai (rectangles des objets)'),
                  f"{kept.get('filled', 0) * 100:.1f} %")]
    return rows


def _plane_rows_text(row) -> list[tuple[str, str]]:
    return [(tr('Largeur de la plaque (mm)'), f'{row.width:.2f}'),
            (tr('Hauteur de la plaque (mm)'), f'{row.height:.2f}'),
            (tr('Épaisseur (mm)'), f'{row.thickness:.2f}'),
            (tr('Surface de la plaque (mm²)'), f'{row.surface:.0f}'),
            (tr('Nombre de pièces imbriquées'), str(row.pieces)),
            (tr('Surface des pièces (mm²)'), f'{row.pieces_area:.0f}'),
            (tr('Surface de découpe des pièces (mm²)'), f'{row.cut_area:.0f}'),
            (tr('Largeur de découpe des pièces (mm)'), f'{row.cut_width:.2f}'),
            (tr('Hauteur de découpe des pièces (mm)'), f'{row.cut_height:.2f}'),
            (tr('Remplissage de la plaque'), f'{row.filled * 100:.1f} %')]


def _table(rows: list[tuple[str, str]]) -> str:
    cells = ''.join(f'<tr><td>{html.escape(a)}</td><td align="right"><b>{html.escape(b)}</b></td></tr>' for a, b in rows)
    return f'<table cellspacing="0" cellpadding="3" border="1" width="100%">{cells}</table>'


def build_html(doc, name: str, gap: float, comment: str = '', image: bool = False, drawings: bool = True) -> str:
    """Le rapport : la page des réglages, puis les plans ; les images sont des ressources `plan<n>` et `image`."""
    parts = [f"<h2>{html.escape(tr('Rapport d’imbrication'))}</h2>", f'<p>{html.escape(name)}</p>',
             f"<h3>{html.escape(tr('Paramètres d’imbrication'))}</h3>"]
    settings = _settings_rows(doc.extra.get('imbrication') or {})
    parts.append(_table(settings) if settings else f"<p>{html.escape(tr('Pas d’imbrication enregistrée dans ce dessin.'))}</p>")
    if comment.strip():
        text = html.escape(comment).replace('\n', '<br>')
        parts.append(f"<h3>{html.escape(tr('Commentaires'))}</h3><p>{text}</p>")
    if image:
        parts.append('<p><img src="image" width="500"></p>')
    for i, row in enumerate(plane_rows(doc, gap)):
        parts.append(f'<div style="page-break-before: always"><h3>{html.escape(tr("Plan : {0}").format(row.name))}</h3></div>')
        parts.append(_table(_plane_rows_text(row)))
        if drawings:
            parts.append(f'<p><img src="plan{i}" width="600"></p>')
    return ''.join(parts)


def plane_image(doc, layer) -> QImage:
    """Le plan sur sa plaque, en traits. Les plaques suivantes d'une même couche restent dans le cadre."""
    img = QImage(IMAGE_W, IMAGE_H, QImage.Format.Format_RGB32)
    img.fill(QColor('white'))
    boxes = [b for b in (it.bbox() for it in layer.items) if b]
    plate = doc.plate
    if plate is not None:
        boxes.append((plate.x, plate.y, plate.x + plate.width, plate.y + plate.height))
    if not boxes:
        return img
    x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
    x1, y1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
    if x1 <= x0 or y1 <= y0:
        return img
    k = min((IMAGE_W - 20) / (x1 - x0), (IMAGE_H - 20) / (y1 - y0))

    def at(x: float, y: float) -> QPointF:
        return QPointF(10 + (x - x0) * k, IMAGE_H - 10 - (y - y0) * k)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    if plate is not None:
        p.setPen(QPen(QColor('#888888'), 1))
        a, b = at(plate.x, plate.y + plate.height), at(plate.x + plate.width, plate.y)
        p.drawRect(QRectF(a, b))
    p.setPen(QPen(QColor(doc.tool_color(layer.tool)).darker(130), 1))
    p.setBrush(Qt.BrushStyle.NoBrush)
    tol = max(0.05, 0.5 / k)
    for it in layer.items:
        for leaf in _leaf_contours(it, tol):
            for pts, closed in leaf:
                path = QPainterPath(at(float(pts[0][0]), float(pts[0][1])))
                for q in pts[1:]:
                    path.lineTo(at(float(q[0]), float(q[1])))
                if closed:
                    path.closeSubpath()
                p.drawPath(path)
    p.end()
    return img


def write_pdf(path, doc, name: str, gap: float, comment: str = '', image_path: str = '') -> None:
    """Écrit le PDF. OSError si le fichier n'est pas accessible (ouvert dans un lecteur, par exemple)."""
    with open(path, 'ab'):                               # QPdfWriter n'en dit rien et laisse un PDF vide
        pass
    writer = QPdfWriter(str(pathlib.Path(path)))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setResolution(150)
    writer.setTitle(tr('Rapport d’imbrication'))
    td = QTextDocument()
    td.documentLayout().setPaintDevice(writer)           # les tailles de police comptent en vrais points
    picture = QImage(str(image_path)) if image_path else QImage()
    for i, layer in enumerate(L for L in doc.layers if L.visible and L.items):
        td.addResource(QTextDocument.ResourceType.ImageResource.value, QUrl(f'plan{i}'), plane_image(doc, layer))
    if not picture.isNull():
        td.addResource(QTextDocument.ResourceType.ImageResource.value, QUrl('image'), picture)
    td.setHtml(build_html(doc, name, gap, comment, image=not picture.isNull()))
    td.setPageSize(QRectF(0, 0, writer.width(), writer.height()).size())
    td.print_(writer)
