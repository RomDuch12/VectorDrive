"""Aperçu du reste de matière (manuel de TE, pages 690 à 695 imprimées) : là où l'outil ne passe pas, en rouge, avec le cercle de
l'outil et de sa surépaisseur au curseur, et un bon à tirer en PDF."""
from __future__ import annotations

import datetime
import pathlib

from PySide6.QtCore import QPointF, QRectF, Qt, QUrl, Signal
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout, QWidget)

from ..cam import model as M
from ..cam import strategies as S
from ..i18n import tr
from . import path_report as PR

REGION_COLOR = '#dfe6ee'
REST_COLOR = '#e03131'


def painter_path(shape) -> QPainterPath:
    """Une géométrie shapely (surfaces) en chemin, trous compris (pair-impair)."""
    path = QPainterPath()
    path.setFillRule(Qt.FillRule.OddEvenFill)
    for poly in getattr(shape, 'geoms', [shape]):
        if poly.is_empty or not hasattr(poly, 'exterior'):
            continue
        for ring in [poly.exterior, *poly.interiors]:
            pts = list(ring.coords)
            path.moveTo(pts[0][0], pts[0][1])
            for p in pts[1:]:
                path.lineTo(p[0], p[1])
            path.closeSubpath()
    return path


def thick_only(rest, thickness: float):
    """Sans les zones plus minces que `thickness` : elles comptent pour usinées (TE)."""
    if thickness <= 0 or rest.is_empty:
        return rest
    return rest.buffer(-thickness / 2).buffer(thickness / 2)


class RestView(QWidget):
    """La région, le reste en rouge et l'outil au curseur. Y vers le haut. La molette agrandit autour du curseur."""

    moved = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(420, 320)
        self.setMouseTracking(True)
        self.region = QPainterPath()
        self.rest = QPainterPath()
        self.radius = 0.0                                # outil au niveau de la coupe
        self.outer = 0.0                                 # outil et surépaisseur
        self.at = None                                   # le curseur, en mm
        self.zoom = 1.0
        self.centre = None

    def bounds(self) -> QRectF:
        return self.region.boundingRect()

    def transform(self, rect: QRectF) -> tuple:
        """(échelle, x du centre de `rect`, y du centre de `rect`, centre en mm)."""
        b = self.bounds()
        c = self.centre if self.centre is not None else b.center()
        w, h = max(b.width(), 1e-6), max(b.height(), 1e-6)
        k = min((rect.width() - 20) / w, (rect.height() - 20) / h) * self.zoom
        return k, rect.center().x(), rect.center().y(), c

    def to_mm(self, pos: QPointF) -> tuple:
        k, ox, oy, c = self.transform(QRectF(self.rect()))
        return c.x() + (pos.x() - ox) / k, c.y() - (pos.y() - oy) / k

    def to_px(self, x: float, y: float) -> QPointF:
        k, ox, oy, c = self.transform(QRectF(self.rect()))
        return QPointF(ox + (x - c.x()) * k, oy - (y - c.y()) * k)

    def zoom_by(self, factor: float, at=None) -> None:
        """Plus grand ou plus petit, le point `at` (mm) restant sous le curseur."""
        new = min(200.0, max(1.0, self.zoom * factor))
        b = self.bounds()
        if at is not None:
            pos = self.to_px(*at)
            self.zoom = new
            x, y = self.to_mm(pos)
            c = self.centre if self.centre is not None else b.center()
            self.centre = QPointF(c.x() + at[0] - x, c.y() + at[1] - y)
        else:
            self.zoom = new
        if self.zoom <= 1.0:
            self.centre = None
        self.update()

    def fit(self) -> None:
        self.zoom, self.centre = 1.0, None
        self.update()

    def draw(self, p: QPainter, rect: QRectF, cursor: bool = True) -> None:
        """La scène dans `rect` (la fenêtre, ou l'image du bon à tirer)."""
        p.fillRect(rect, QColor('white'))
        if self.region.isEmpty():
            return
        k, ox, oy, c = self.transform(rect)
        p.save()
        p.setClipRect(rect)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.translate(ox, oy)
        p.scale(k, -k)
        p.translate(-c.x(), -c.y())
        p.setPen(QPen(QColor('#58677a'), 0))
        p.setBrush(QBrush(QColor(REGION_COLOR)))
        p.drawPath(self.region)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(REST_COLOR)))
        p.drawPath(self.rest)
        if cursor and self.at is not None and self.radius > 0:
            p.setBrush(Qt.BrushStyle.NoBrush)
            at = QPointF(*self.at)
            p.setPen(QPen(QColor('#1c7ed6'), 0))
            p.drawEllipse(at, self.radius, self.radius)
            if self.outer > self.radius:
                p.setPen(QPen(QColor('#1c7ed6'), 0, Qt.PenStyle.DashLine))
                p.drawEllipse(at, self.outer, self.outer)
        p.restore()

    def image(self, width: int = 1400) -> QImage:
        """L'ensemble, sans curseur ni agrandissement, pour le bon à tirer."""
        b = self.bounds()
        ratio = b.height() / b.width() if b.width() > 0 else 1.0
        im = QImage(width, max(200, min(int(width * max(ratio, 0.2)), 2 * width)), QImage.Format.Format_RGB32)
        was = self.zoom, self.centre
        self.zoom, self.centre = 1.0, None
        p = QPainter(im)
        self.draw(p, QRectF(im.rect()), cursor=False)
        p.end()
        self.zoom, self.centre = was
        return im

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        self.draw(p, QRectF(self.rect()))
        p.end()

    def mouseMoveEvent(self, ev) -> None:
        self.at = self.to_mm(ev.position())
        self.moved.emit(*self.at)
        self.update()

    def leaveEvent(self, _ev) -> None:
        self.at = None
        self.update()

    def wheelEvent(self, ev) -> None:
        self.zoom_by(1.25 if ev.angleDelta().y() > 0 else 0.8, self.to_mm(ev.position()))


class RestPreviewDialog(QDialog):
    """`region` : shapely. `tools` : les outils proposés. `on_lay(outil, reste, rayon)` : poser le reste sur le dessin. `laid` : ce
    qu'elle a rendu."""

    def __init__(self, parent, region, tools, *, tool=None, depth: float = 0.2, stock: float = 0.0, source: str = '', on_lay=None):
        super().__init__(parent)
        self.setWindowTitle(tr('Aperçu du reste de matière'))
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.region = region
        self.tools = list(tools)
        if tool is not None and not any(t.id == tool.id for t in self.tools):
            self.tools.append(tool)
        self.source = source
        self.on_lay = on_lay
        self.laid = None
        self.started = datetime.datetime.now()
        self.rest = None
        self.radius = 0.0
        root = QHBoxLayout(self)
        left = QVBoxLayout()
        root.addLayout(left)
        self.kinds = QComboBox()
        self.kinds.addItem(tr('Tous les outils'), '')
        for kind in dict.fromkeys(t.kind for t in self.tools):
            self.kinds.addItem(tr(M.TOOL_KINDS.get(kind, kind)), kind)
        left.addWidget(self.kinds)
        self.tool_list = QListWidget()
        left.addWidget(self.tool_list, 1)
        form = QFormLayout()
        left.addLayout(form)

        def spin(value: float, tip: str = '') -> QDoubleSpinBox:
            s = QDoubleSpinBox()
            s.setRange(0.0, 1000.0)
            s.setDecimals(3)
            s.setSingleStep(0.05)
            s.setSuffix(' mm')
            s.setValue(value)
            if tip:
                s.setToolTip(tip)
            return s
        self.stock = spin(stock, tr('Elle s\'ajoute au rayon de l\'outil : second cercle au curseur'))
        self.depth = spin(depth, tr('Le rayon d\'un outil conique ou boule dépend de la profondeur'))
        self.thin = spin(0.0, tr('Une zone plus mince compte pour usinée et n\'apparaît pas ; en général, la surépaisseur de la finition'))
        form.addRow(tr('Surépaisseur'), self.stock)
        form.addRow(tr('Profondeur'), self.depth)
        form.addRow(tr('Épaisseur ignorée'), self.thin)
        self.info = QLabel()
        self.info.setWordWrap(True)
        left.addWidget(self.info)
        right = QVBoxLayout()
        root.addLayout(right, 1)
        self.view = RestView()
        self.view.region = painter_path(region)
        self.view.moved.connect(self._moved)
        right.addWidget(self.view, 1)
        row = QHBoxLayout()
        self.coords = QLabel('X - ; Y -')
        row.addWidget(self.coords)
        row.addStretch(1)
        self.fit_button = QPushButton(tr('Zoom maximum'))
        self.fit_button.clicked.connect(self.view.fit)
        self.print_button = QPushButton(tr('Imprimer le bon à tirer…'))
        self.print_button.setToolTip(tr('Un PDF : la simulation, les zones non vidées en rouge, la date, le fichier, l\'outil, la surépaisseur et la profondeur'))
        self.print_button.clicked.connect(lambda: self.print_report())
        self.lay_button = QPushButton(tr('Poser sur le dessin'))
        self.lay_button.setToolTip(tr('Le reste, en formes pleines, sur le calque « Reste de matière »'))
        self.lay_button.clicked.connect(lambda: self.lay())
        self.lay_button.setVisible(on_lay is not None)
        close = QPushButton(tr('Fermer'))
        close.clicked.connect(self.reject)
        for b in (self.fit_button, self.print_button, self.lay_button, close):
            row.addWidget(b)
        right.addLayout(row)
        self.resize(1040, 640)
        self.kinds.currentIndexChanged.connect(lambda _i: self._fill_list())
        self.tool_list.currentRowChanged.connect(lambda _r: self.refresh())
        for s in (self.stock, self.depth, self.thin):
            s.valueChanged.connect(lambda _v: self.refresh())
        self._fill_list(tool)

    def _fill_list(self, tool=None) -> None:
        was = tool if tool is not None else self.tool()
        kind = self.kinds.currentData()
        self.tool_list.blockSignals(True)
        self.tool_list.clear()
        row = 0
        for t in self.tools:
            if kind and t.kind != kind:
                continue
            it = QListWidgetItem(f'T{t.number} {t.name} (Ø{t.diameter:g})')
            it.setData(Qt.ItemDataRole.UserRole, t.id)
            self.tool_list.addItem(it)
            if was is not None and t.id == was.id:
                row = self.tool_list.count() - 1
        if self.tool_list.count():
            self.tool_list.setCurrentRow(row)
        self.tool_list.blockSignals(False)
        self.refresh()

    def tool(self):
        it = self.tool_list.currentItem()
        if it is None:
            return None
        return next((t for t in self.tools if t.id == it.data(Qt.ItemDataRole.UserRole)), None)

    def refresh(self) -> None:
        """Le reste, pour l'outil et les réglages du moment."""
        t = self.tool()
        if t is None:
            self.rest, self.radius = None, 0.0
            self.view.rest = QPainterPath()
            self.view.radius = self.view.outer = 0.0
            self.info.setText(tr('Aucun outil de ce type.'))
            self.lay_button.setEnabled(False)
            self.view.update()
            return
        rest, r = S.rest_zones(self.region, t, self.depth.value(), self.stock.value())
        self.rest, self.radius = thick_only(rest, self.thin.value()), r
        self.view.rest = painter_path(self.rest)
        self.view.outer = r
        self.view.radius = max(0.0, r - self.stock.value())
        area = self.rest.area
        empty = self.rest.is_empty or area < 1e-6
        if empty:
            self.info.setText(tr('L\'outil {0} vide tout : aucun reste de matière.').format(t.name))
        else:
            self.info.setText(tr('Non vidé : {0} mm², {1} % de la surface.').format(f'{area:.2f}'.replace('.', ','),
                                                                                    f'{100 * area / self.region.area:.1f}'.replace('.', ',')))
        self.lay_button.setEnabled(not empty)
        self.view.update()

    def _moved(self, x: float, y: float) -> None:
        self.coords.setText(f'X {x:.3f} ; Y {y:.3f}'.replace('.', ','))

    def lay(self):
        """Pose le reste sur le dessin et ferme."""
        if self.on_lay is None or self.rest is None or self.rest.is_empty:
            return None
        self.laid = self.on_lay(self.tool(), self.rest, self.radius)
        self.accept()
        return self.laid

    def report_html(self) -> str:
        """Le bon à tirer (TE, page 692 imprimée)."""
        t = self.tool()
        rows = [(tr('Date et heure'), self.started.strftime('%d/%m/%Y %H:%M')), (tr('Fichier'), self.source or tr('Dessin non enregistré'))]
        if t is not None:
            rows += [(tr('Outil'), f'T{t.number} {t.name}'), (tr('Forme'), tr(M.TOOL_KINDS.get(t.kind, t.kind))),
                     (tr('Diamètre de l\'outil'), PR._mm(t.diameter)), (tr('Angle'), f'{t.angle:g}°'.replace('.', ',') if t.angle else ''),
                     (tr('Troncature'), PR._mm(t.tip) if t.tip else '')]
        rows += [(tr('Surépaisseur'), PR._mm(self.stock.value())), (tr('Profondeur'), PR._mm(self.depth.value())), (tr('Reste'), self.info.text())]
        return ''.join([PR._head(tr('Bon à tirer : reste de matière')), PR._lines(rows), '<p><img src="image" width="700"></p></body></html>'])

    def print_report(self, path: str | None = None) -> str | None:
        """Écrit le bon à tirer et l'affiche si le chemin vient de la fenêtre. Rend le chemin."""
        asked = path is None
        if asked:
            start = str(pathlib.Path(self.source).with_suffix('')) + '_Reste.pdf' if self.source else ''
            path, _f = QFileDialog.getSaveFileName(self, tr('Imprimer le bon à tirer…'), start, tr('Fichier PDF (*.pdf)'))
            if not path:
                return None
        try:
            PR.write_pdf(path, self.report_html(), tr('Bon à tirer : reste de matière'), self.view.image())
        except OSError as e:
            QMessageBox.warning(self, tr('Imprimer le bon à tirer…'), str(e))
            return None
        if asked:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        return path
