"""Icône d'œil (montré / caché) des listes : peinte, sans fichier d'image ni police d'émojis."""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


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
