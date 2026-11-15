"""Fenêtre de la parcellisation (cam.panels) : les panneaux sur les parcours, leur ordre, ceux qu'on garde."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QGridLayout,
                               QHBoxLayout, QLabel, QListWidget, QPushButton, QSizePolicy, QVBoxLayout, QWidget)

from ..cam import panels as PN
from ..i18n import tr

_TOLERANCE = 0.05


class Preview(QWidget):
    """Les parcours et les panneaux, vus de dessus ; un clic choisit un panneau."""
    picked = Signal(int)

    def __init__(self, toolpaths, parent=None):
        super().__init__(parent)
        self.setMinimumSize(420, 320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.path = QPainterPath()
        for tp in toolpaths:
            for poly in tp.drawing(_TOLERANCE):
                self.path.moveTo(poly[0][0], poly[0][1])
                for x, y in poly[1:]:
                    self.path.lineTo(x, y)
        self.panels: list = []
        self.current = None

    def show_panels(self, panels: list, current) -> None:
        self.panels = panels
        self.current = current
        self.update()

    def _extent(self) -> QRectF:
        r = self.path.boundingRect()
        for p in self.panels:
            r = r.united(QRectF(p.x1, p.y1, p.width, p.height))
        return r

    def _view(self) -> tuple[float, float, float]:
        """(échelle, x, y) : un point du dessin (a, b) se voit en (x + a k, y - b k)."""
        r = self._extent()
        k = min((self.width() - 20) / max(r.width(), 1e-6), (self.height() - 20) / max(r.height(), 1e-6))
        return k, (self.width() - r.width() * k) / 2 - r.x() * k, (self.height() + r.height() * k) / 2 + r.y() * k

    def paintEvent(self, _ev) -> None:
        qp = QPainter(self)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing)
        qp.fillRect(self.rect(), self.palette().base())
        k, ox, oy = self._view()
        qp.save()
        qp.translate(ox, oy)
        qp.scale(k, -k)
        pen = QPen(self.palette().text().color(), 0)
        pen.setCosmetic(True)
        qp.setPen(pen)
        qp.drawPath(self.path)
        qp.restore()
        for p in self.panels:
            on = p is self.current
            box = QRectF(ox + p.x1 * k, oy - p.y2 * k, p.width * k, p.height * k)
            qp.fillRect(box, QColor(230, 150, 40, 70 if on else 22))
            pen = QPen(QColor(200, 110, 20), 2 if on else 1)
            qp.setPen(pen)
            qp.drawRect(box)
            qp.drawText(box, Qt.AlignmentFlag.AlignCenter, str(p.rank))
        qp.end()

    def mousePressEvent(self, ev) -> None:
        k, ox, oy = self._view()
        if k <= 0:
            return
        x, y = (ev.position().x() - ox) / k, (oy - ev.position().y()) / k
        near = [p for p in self.panels if p.x1 <= x <= p.x2 and p.y1 <= y <= p.y2]
        if near:                                         # dans une bande commune : le centre le plus proche
            best = min(near, key=lambda p: math.hypot(x - (p.x1 + p.x2) / 2, y - (p.y1 + p.y2) / 2))
            self.picked.emit(self.panels.index(best))


class PanelsDialog(QDialog):
    """`plate` : cadre (x0, y0, x1, y1) de la plaque, ou None ; `stored` : réglages gardés avec le dessin."""

    def __init__(self, parent, toolpaths, plate=None, stored: dict | None = None):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)
        self.setWindowTitle(tr('Parcellisation'))
        self.setSizeGripEnabled(True)
        self.plate = plate
        self.paths_box = PN.path_bounds(toolpaths)
        self.segments = PN.segments(toolpaths)
        self.panels: list = []
        self.dropped = 0
        stored = stored or {}
        zone = self.paths_box or plate or (0.0, 0.0, 100.0, 100.0)

        def spin(key: str, default: float, low: float, tip: str) -> QDoubleSpinBox:
            w = QDoubleSpinBox()
            w.setRange(low, 100000.0)
            w.setDecimals(2)
            w.setSuffix(' mm')
            w.setToolTip(tip)
            w.setValue(float(stored.get(key, default) or default))
            w.valueChanged.connect(lambda _v: self.rebuild())
            return w

        half = lambda v: max(10.0, math.ceil(v / 2 / 10) * 10)      # noqa: E731
        self.width_box = spin('width', half(zone[2] - zone[0]), 1.0, tr('Largeur d’un panneau, chevauchement compris'))
        self.height_box = spin('height', half(zone[3] - zone[1]), 1.0, tr('Hauteur d’un panneau, chevauchement compris'))
        self.overlap_box = spin('overlap', 0.0, 0.0, tr('Ce que deux panneaux voisins usinent tous deux, pour des bords '
                                                        'francs entre deux plaques'))

        def combo(key: str, items, tip: str) -> QComboBox:
            w = QComboBox()
            w.setToolTip(tip)
            for value, label in items:
                w.addItem(label, value)
            k = w.findData(stored.get(key))
            w.setCurrentIndex(k if k >= 0 else 0)
            w.currentIndexChanged.connect(lambda _i: self.rebuild())
            return w

        self.order_box = combo('order', [('bl_rows', tr('Bas gauche, par rangées')), ('bl_cols', tr('Bas gauche, par colonnes')),
                                         ('tl_rows', tr('Haut gauche, par rangées')), ('tl_cols', tr('Haut gauche, par colonnes'))],
                               tr('Le premier panneau et le sens de l’usinage'))
        zones = [('paths', tr('Ce qui est à usiner'))]
        if plate is not None:
            zones.append(('plate', tr('La plaque')))
        self.zone_box = combo('zone', zones, tr('Ce que les panneaux couvrent'))
        self.origin_box = combo('origin', [('bottom_left', tr('Coin bas gauche')), ('top_left', tr('Coin haut gauche')),
                                           ('center', tr('Centre'))], tr('Le zéro du programme de chaque panneau'))
        self.fit_box = QCheckBox(tr('Réduire les derniers panneaux à ce qui reste'))
        self.fit_box.setChecked(bool(stored.get('fit_last', True)))
        self.fit_box.toggled.connect(lambda _v: self.rebuild())

        form = QFormLayout()
        form.addRow(tr('Largeur'), self.width_box)
        form.addRow(tr('Hauteur'), self.height_box)
        form.addRow(tr('Chevauchement'), self.overlap_box)
        form.addRow(tr('Ordre'), self.order_box)
        form.addRow(tr('Zone'), self.zone_box)
        form.addRow(tr('Zéro'), self.origin_box)
        form.addRow(self.fit_box)

        self.listing = QListWidget()
        self.listing.currentRowChanged.connect(lambda _r: self._shown())
        moves = QGridLayout()
        for k, (label, tip, fn) in enumerate((
                (tr('Premier'), tr('Usiner ce panneau en premier'), self.to_first),
                (tr('Avant'), tr('Usiner ce panneau un rang plus tôt'), self.earlier),
                (tr('Après'), tr('Usiner ce panneau un rang plus tard'), self.later),
                (tr('Dernier'), tr('Usiner ce panneau en dernier'), self.to_last),
                (tr('Retirer'), tr('Ne pas usiner ce panneau'), self.remove),
                (tr('Tout remettre'), tr('Refaire la grille, dans l’ordre choisi'), self.rebuild))):
            b = QPushButton(label)
            b.setToolTip(tip)
            b.clicked.connect(lambda _c=False, f=fn: f())
            moves.addWidget(b, k // 2, k % 2)
        self.info = QLabel()
        self.info.setWordWrap(True)
        side = QVBoxLayout()
        side.addLayout(form)
        side.addWidget(self.listing, 1)
        side.addLayout(moves)
        side.addWidget(self.info)

        self.preview = Preview(toolpaths)
        self.preview.picked.connect(self.listing.setCurrentRow)
        top = QHBoxLayout()
        host = QWidget()
        host.setLayout(side)
        host.setMaximumWidth(360)
        top.addWidget(host)
        top.addWidget(self.preview, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.write_button = buttons.addButton(tr('Écrire les programmes…'), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(top, 1)
        lay.addWidget(buttons)
        self.resize(980, 640)
        self.rebuild()

    def bounds(self):
        zone = self.zone_box.currentData()
        return self.plate if zone == 'plate' and self.plate is not None else self.paths_box

    def values(self) -> dict:
        return {'width': self.width_box.value(), 'height': self.height_box.value(), 'overlap': self.overlap_box.value(),
                'order': self.order_box.currentData(), 'zone': self.zone_box.currentData(),
                'origin': self.origin_box.currentData(), 'fit_last': self.fit_box.isChecked()}

    def rebuild(self) -> None:
        """La grille, sans les panneaux où rien ne tombe."""
        v = self.values()
        try:
            grid = PN.plan(self.bounds(), v['width'], v['height'], v['overlap'], v['order'], v['fit_last'])
        except ValueError as ex:
            self.panels, self.dropped = [], 0
            self.problem = str(ex)
        else:
            self.problem = ''
            kept = PN.occupied(grid, self.segments)
            self.dropped = len(grid) - len(kept)
            self.panels = PN.renumbered(kept)
        self._refill(0)

    def _refill(self, row: int) -> None:
        self.panels = PN.renumbered(self.panels)
        self.listing.blockSignals(True)
        self.listing.clear()
        for p in self.panels:
            self.listing.addItem(tr('{0} : {1} × {2} mm, rangée {3}, colonne {4}').format(
                p.rank, f'{p.width:.1f}', f'{p.height:.1f}', p.row, p.col))
        self.listing.setCurrentRow(min(row, len(self.panels) - 1))
        self.listing.blockSignals(False)
        self._shown()
        if self.problem:
            self.info.setText(tr('Tailles impossibles : le chevauchement doit rester plus petit que le panneau, '
                                 'et {0} panneaux au plus.').format(PN.MAX_PANELS))
        else:
            text = tr('{0} panneau(x)').format(len(self.panels))
            if self.dropped:
                text += ' ; ' + tr('{0} vide(s) retiré(s)').format(self.dropped)
            self.info.setText(text)
        self.write_button.setEnabled(bool(self.panels))

    def _shown(self) -> None:
        r = self.listing.currentRow()
        self.preview.show_panels(self.panels, self.panels[r] if 0 <= r < len(self.panels) else None)

    def _shift(self, to) -> None:
        r = self.listing.currentRow()
        if not 0 <= r < len(self.panels):
            return
        p = self.panels.pop(r)
        k = max(0, min(to(r), len(self.panels)))
        self.panels.insert(k, p)
        self._refill(k)

    def to_first(self) -> None:
        self._shift(lambda _r: 0)

    def earlier(self) -> None:
        self._shift(lambda r: r - 1)

    def later(self) -> None:
        self._shift(lambda r: r + 1)

    def to_last(self) -> None:
        self._shift(lambda _r: len(self.panels))

    def remove(self) -> None:
        r = self.listing.currentRow()
        if 0 <= r < len(self.panels):
            self.panels.pop(r)
            self._refill(r)
