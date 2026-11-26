"""Icône d'œil (montré / caché) des listes : peinte, sans fichier d'image ni police d'émojis."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QRegion
from PySide6.QtWidgets import QApplication, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QToolTip


def eye_pixmap(on: bool, color: str = '', size: int = 18) -> QPixmap:
    """Un œil ouvert (iris de la couleur `color`, gris foncé sans elle) ou barré, sur fond transparent."""
    s = float(size)
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    line = QColor('#495057' if on else '#adb5bd')
    p.setPen(QPen(line, max(1.2, s / 12)))
    lid = QPainterPath(QPointF(s * 0.06, s * 0.5))
    lid.quadTo(QPointF(s * 0.5, s * 0.06), QPointF(s * 0.94, s * 0.5))
    lid.quadTo(QPointF(s * 0.5, s * 0.94), QPointF(s * 0.06, s * 0.5))
    p.drawPath(lid)
    if on:
        p.setBrush(QColor(color) if color else line)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(s * 0.5, s * 0.5), s * 0.19, s * 0.19)
    else:
        p.drawLine(QPointF(s * 0.16, s * 0.86), QPointF(s * 0.84, s * 0.14))
    p.end()
    return pm


def eye_icon(on: bool, color: str = '', size: int = 18) -> QIcon:
    """L'icône de l'œil : ouvert (`on`), à la couleur du tracé qu'il montre, ou barré."""
    return QIcon(eye_pixmap(on, color, size))


#: couleurs du bouton marche/arrêt : en marche, en partie (des parcours à l'arrêt), à l'arrêt
POWER_COLORS = {True: '#2f9e44', None: '#e8a33d', False: '#adb5bd'}


def power_pixmap(on, size: int = 18) -> QPixmap:
    """Le bouton marche/arrêt (⏻ : un cercle ouvert en haut, un trait) : vert en marche, gris clair à l'arrêt ; `on`
    None : en partie (orangé mi-teinte : une partie de ses parcours est à l'arrêt)."""
    s = float(size)
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(POWER_COLORS[None if on is None else bool(on)]), max(1.6, s / 8))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawArc(QRectF(s * 0.16, s * 0.2, s * 0.68, s * 0.68), 120 * 16, 300 * 16)   # ouvert entre 60° et 120°
    p.drawLine(QPointF(s * 0.5, s * 0.08), QPointF(s * 0.5, s * 0.5))
    p.end()
    return pm


def power_icon(on, size: int = 18) -> QIcon:
    """L'icône du bouton marche/arrêt : en marche (`on`, vert), à l'arrêt (gris), en partie (None, orangé)."""
    return QIcon(power_pixmap(on, size))


_CHECK = QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
_DECO = QStyleOptionViewItem.ViewItemFeature.HasDecoration


def _state(check) -> bool | None:
    """L'état d'une case : True (cochée), False, None (en partie)."""
    return None if check == Qt.CheckState.PartiallyChecked else check == Qt.CheckState.Checked


class IconCheckDelegate(QStyledItemDelegate):
    """La case à cocher d'une liste peinte en icône cliquable (demande du 25/11 : un bouton marche/arrêt à la place de
    la case ; l'œil) : la case garde tout son rôle — clic, Espace, `itemChanged` —, seule sa peinture change.
    `icon(index, état)` : son icône ; `tip(index, état)` : sa bulle (état : True, False, None en partie).
    `extra` : (bulle(index), clic(index)) —
    l'icône de la ligne (sa décoration) devient elle aussi un bouton."""

    def __init__(self, parent, icon, tip, extra=None):
        super().__init__(parent)
        self._icon, self._tip, self._extra = icon, tip, extra

    def _opt(self, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        w = opt.widget
        return opt, w, (w.style() if w is not None else QApplication.style())

    def check_rect(self, option, index) -> QRect:
        """La place de la case (de l'icône qui la remplace) dans la ligne `option.rect`."""
        opt, w, style = self._opt(option, index)
        if not opt.features & _CHECK:
            return QRect()
        return style.subElementRect(QStyle.SubElement.SE_ItemViewItemCheckIndicator, opt, w)

    def extra_rect(self, option, index) -> QRect:
        """La place de l'icône de la ligne, quand elle est un bouton (`extra`)."""
        if self._extra is None:
            return QRect()
        opt, w, style = self._opt(option, index)
        if not opt.features & _DECO:
            return QRect()
        return style.subElementRect(QStyle.SubElement.SE_ItemViewItemDecoration, opt, w)

    def paint(self, painter, option, index) -> None:
        opt, w, style = self._opt(option, index)
        if not opt.features & _CHECK:
            super().paint(painter, option, index)
            return
        box = style.subElementRect(QStyle.SubElement.SE_ItemViewItemCheckIndicator, opt, w)
        painter.save()                                   # la ligne entière, sauf la case
        painter.setClipRegion(QRegion(opt.rect).subtracted(QRegion(box)), Qt.ClipOperation.IntersectClip)
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, w)
        painter.restore()
        painter.save()                                   # à la place de la case : le fond de la ligne, puis l'icône
        painter.setClipRect(box, Qt.ClipOperation.IntersectClip)
        style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, opt, painter, w)
        painter.restore()
        side = min(box.width(), box.height()) + 4
        r = QRect(0, 0, side, side)
        r.moveCenter(box.center())
        self._icon(index, _state(opt.checkState)).paint(painter, r.intersected(opt.rect))

    def editorEvent(self, event, model, option, index) -> bool:
        if self._extra is not None and event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease,
                                                        QEvent.Type.MouseButtonDblClick) \
                and event.button() == Qt.MouseButton.LeftButton \
                and self.extra_rect(option, index).contains(event.position().toPoint()):
            if event.type() == QEvent.Type.MouseButtonRelease:
                self._extra[1](index)
            return True                                  # l'icône de la ligne : son bouton, pas un clic sur la ligne
        return super().editorEvent(event, model, option, index)

    def tip_at(self, option, index, pos) -> str:
        """La bulle de l'icône sous `pos` ('' : ailleurs dans la ligne, sa propre bulle)."""
        if self.check_rect(option, index).contains(pos):
            opt, _w, _style = self._opt(option, index)
            return self._tip(index, _state(opt.checkState))
        if self.extra_rect(option, index).contains(pos):
            return self._extra[0](index)
        return ''

    def helpEvent(self, event, view, option, index) -> bool:
        if event is not None and event.type() == QEvent.Type.ToolTip and index.isValid():
            text = self.tip_at(option, index, event.pos())
            if text:
                QToolTip.showText(event.globalPos(), text, view)
                return True
        return super().helpEvent(event, view, option, index)
