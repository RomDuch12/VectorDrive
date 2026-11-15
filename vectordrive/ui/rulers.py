"""Règles graduées autour du canevas (en mm, comme TypeEdit). Un glisser
depuis une règle pose un guide : horizontal depuis la règle du haut,
vertical depuis celle de gauche. Les graduations partent de l'origine du
dessin ; un glisser depuis le coin des règles la place (TypeEdit : « Modifier
l'origine des axes »), un double-clic sur le coin la remet au zéro."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

#: épaisseur des règles (px)
SIZE = 20


def tick_steps(scale: float) -> tuple[float, float]:
    """(pas des graduations, pas des chiffres) en mm pour `scale` px/mm :
    chiffres espacés d'au moins 60 px, graduations d'au moins 6 px."""
    def nice(target):
        e = 10 ** math.floor(math.log10(target))
        for m in (1, 2, 5, 10):
            if m * e >= target:
                return m * e
        return 10 * e
    major = nice(60 / scale)
    minor = nice(6 / scale)
    return min(minor, major), major


def paint_background(w: QWidget, p: QPainter) -> QColor:
    """Fond des règles (couleurs du thème) ; rend la couleur des chiffres."""
    from .theme import canvas_colors
    cc = canvas_colors()
    pal = w.palette()
    bg, fg = pal.window().color(), pal.windowText().color()
    if cc.get('ruler'):                                  # règles du thème (TypeEdit : gris-bleu, chiffres blancs)
        p.fillRect(w.rect(), QColor(cc['ruler']))
        fg = QColor(cc.get('ruler_text') or fg)
    else:
        p.fillRect(w.rect(), bg.darker(108) if bg.lightness() > 128 else bg.lighter(130))
    return fg


class RulerCorner(QWidget):
    """Coin des règles : glisser jusqu'au plan de travail place l'origine du
    dessin (accrochages F3 compris) ; double-clic : retour au zéro du dessin."""

    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.setFixedSize(SIZE, SIZE)
        self._dragging = False
        self.setCursor(Qt.CursorShape.CrossCursor)
        from ..i18n import tr
        self.setToolTip(tr('Origine du dessin : glisser d\'ici jusqu\'au point voulu ; double-clic : retour au '
                           'zéro du dessin'))

    def paintEvent(self, ev) -> None:
        p = QPainter(self)
        fg = paint_background(self, p)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(215, 48, 39), 1.5))
        p.drawLine(QPointF(6, SIZE - 6), QPointF(SIZE - 3, SIZE - 6))
        p.setPen(QPen(QColor(26, 152, 80), 1.5))
        p.drawLine(QPointF(6, SIZE - 6), QPointF(6, 3))
        p.setPen(QPen(fg, 1))
        p.drawEllipse(QPointF(6, SIZE - 6), 2.5, 2.5)
        p.end()

    def point_at(self, global_pos) -> tuple[float, float] | None:
        """Point du dessin sous `global_pos` (accroché), None hors du plan."""
        c = self.canvas
        m = c.mapFromGlobal(global_pos)
        if not c.rect().contains(m):
            return None
        return c.snap_doc(QPointF(m))

    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            self._dragging = True

    def mouseMoveEvent(self, ev) -> None:
        if self._dragging:
            self.canvas.origin_preview = self.point_at(ev.globalPosition().toPoint())
            self.canvas.overlay_update()

    def mouseReleaseEvent(self, ev) -> None:
        if not self._dragging:
            return
        self._dragging = False
        self.drop_at(ev.globalPosition().toPoint())

    def drop_at(self, global_pos) -> bool:
        pt = self.point_at(global_pos)
        self.canvas.origin_preview = None
        if pt is not None:
            self.canvas.set_origin(*pt)
        self.canvas.overlay_update()
        return pt is not None

    def mouseDoubleClickEvent(self, ev) -> None:
        self._dragging = False
        self.canvas.origin_preview = None
        self.canvas.set_origin(0.0, 0.0)


class Ruler(QWidget):
    def __init__(self, canvas, axis: str, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.axis = axis                    # 'h' : règle du haut (x), 'v' : règle de gauche (y)
        if axis == 'h':
            self.setFixedHeight(SIZE)
        else:
            self.setFixedWidth(SIZE)
        self.setMouseTracking(True)
        self._dragging = False
        self.setToolTip('')

    # --- dessin ---------------------------------------------------------------
    def paintEvent(self, ev) -> None:
        c = self.canvas
        p = QPainter(self)
        from .theme import canvas_colors
        cc = canvas_colors()
        fg = paint_background(self, p)
        pen = QPen(fg, 1)
        p.setPen(pen)
        f = QFont(self.font())
        f.setPointSizeF(7)
        p.setFont(f)
        minor, major = tick_steps(c.scale)
        ox, oy = c.origin
        if self.axis == 'h':
            x0 = c.to_doc(QPointF(0, 0))[0] - ox
            x1 = c.to_doc(QPointF(c.width(), 0))[0] - ox
            k = math.floor(x0 / minor)
            while k * minor <= x1:
                v = k * minor
                sx = c.to_screen(v + ox, 0).x()
                is_major = abs(v / major - round(v / major)) < 1e-6
                h = SIZE - 1 if is_major else (SIZE * 0.45 if abs((v / (major / 2)) - round(v / (major / 2))) < 1e-6
                                              else SIZE * 0.25)
                p.drawLine(QPointF(sx, SIZE), QPointF(sx, SIZE - h))
                if is_major:
                    p.drawText(QPointF(sx + 2, 9), f'{v:g}')
                k += 1
            p.drawLine(0, SIZE - 1, self.width(), SIZE - 1)
        else:
            y1 = c.to_doc(QPointF(0, 0))[1] - oy
            y0 = c.to_doc(QPointF(0, c.height()))[1] - oy
            k = math.floor(y0 / minor)
            while k * minor <= y1:
                v = k * minor
                sy = c.to_screen(0, v + oy).y()
                is_major = abs(v / major - round(v / major)) < 1e-6
                w = SIZE - 1 if is_major else (SIZE * 0.45 if abs((v / (major / 2)) - round(v / (major / 2))) < 1e-6
                                              else SIZE * 0.25)
                p.drawLine(QPointF(SIZE, sy), QPointF(SIZE - w, sy))
                if is_major:
                    p.save()
                    p.translate(9, sy - 2)
                    p.rotate(-90)
                    p.drawText(QPointF(0, 0), f'{v:g}')
                    p.restore()
                k += 1
            p.drawLine(SIZE - 1, 0, SIZE - 1, self.height())
        # repère du curseur
        m = c.mapFromGlobal(self.cursor().pos())
        p.setPen(QPen(QColor(cc['snap']), 1))
        if c.rect().contains(m) or self._dragging:
            if self.axis == 'h':
                p.drawLine(QPointF(m.x(), 0), QPointF(m.x(), SIZE))
            else:
                p.drawLine(QPointF(0, m.y()), QPointF(SIZE, m.y()))
        p.end()

    # --- création d'un guide ----------------------------------------------------
    def _guide_axis(self) -> str:
        return 'h' if self.axis == 'h' else 'v'      # haut → guide horizontal, gauche → vertical

    def _value(self, global_pos) -> tuple[float, bool]:
        c = self.canvas
        m = c.mapFromGlobal(global_pos)
        inside = c.rect().contains(m)
        x, y = c.snap_doc(QPointF(m)) if inside else c.to_doc(QPointF(m))
        return (y if self._guide_axis() == 'h' else x), inside

    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self.canvas.ruler_dragging = self
            self.setCursor(Qt.CursorShape.SplitVCursor if self._guide_axis() == 'h' else Qt.CursorShape.SplitHCursor)

    def ask_position(self) -> bool:
        """F2 sans relâcher le bouton (TypeEdit) : la position du repère en chiffres. True : repère posé."""
        from PySide6.QtWidgets import QInputDialog

        from ..i18n import tr
        axis = self._guide_axis()
        shown = self.canvas.guide_preview
        self._dragging = False
        self.canvas.ruler_dragging = None
        self.canvas.guide_preview = None
        self.unsetCursor()
        self.canvas.overlay_update()
        v, ok = QInputDialog.getDouble(self.window(), tr('Repère'), tr('Y (mm)') if axis == 'h' else tr('X (mm)'),
                                       float(shown[1]) if shown else 0.0, -1e7, 1e7, 3)
        if ok:
            self.canvas.add_guide(axis, v)
            self.canvas.overlay_update()
        return bool(ok)

    def mouseMoveEvent(self, ev) -> None:
        if self._dragging:
            v, inside = self._value(ev.globalPosition().toPoint())
            self.canvas.guide_preview = (self._guide_axis(), v) if inside else None
            self.canvas.overlay_update()
        self.update()

    def mouseReleaseEvent(self, ev) -> None:
        if not self._dragging:
            return
        self._dragging = False
        self.canvas.ruler_dragging = None
        self.unsetCursor()
        v, inside = self._value(ev.globalPosition().toPoint())
        self.canvas.guide_preview = None
        if inside:
            self.canvas.add_guide(self._guide_axis(), v)
        self.canvas.overlay_update()
