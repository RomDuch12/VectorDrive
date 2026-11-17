"""Icônes dessinées au vol (aucun fichier image, aucune licence tierce)."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

_INK_LIGHT = QColor('#2b3a55')      # encre sur fond clair
_INK_DARK = QColor('#c8d3ea')       # encre sur fond sombre (thème sombre de Windows)
_INK = _INK_LIGHT
_ACCENT = QColor('#d0451b')


def dark_theme() -> bool:
    """Fond de fenêtre sombre (thème sombre du système) ?"""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    return bool(app) and app.palette().window().color().lightness() < 128


def _inks() -> tuple[str, str]:
    """Encre et accent des icônes du thème appliqué."""
    from .theme import current
    c = current().colors
    return c.get('icon') or (_INK_DARK if dark_theme() else _INK_LIGHT).name(), c.get('icon_accent') or '#d0451b'


def _icon(draw) -> QIcon:
    global _INK, _ACCENT
    ink, acc = _inks()
    _INK, _ACCENT = QColor(ink), QColor(acc)               # lus par les fonctions de dessin
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(_INK, 4)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    draw(p)
    p.end()
    return QIcon(pm)


def _accent(p, w=4):
    pen = QPen(_ACCENT, w)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)


def _arrow(p):
    path = QPainterPath()
    path.moveTo(18, 8); path.lineTo(18, 52); path.lineTo(29, 41)
    path.lineTo(37, 58); path.lineTo(44, 55); path.lineTo(36, 38); path.lineTo(51, 38)
    path.closeSubpath()
    p.setBrush(QColor('#ffffff'))
    p.drawPath(path)


def _rect(p):
    p.drawRect(QRectF(10, 16, 44, 32))


def _ellipse(p):
    p.drawEllipse(QRectF(8, 14, 48, 36))


def _line(p):
    p.drawLine(QPointF(10, 52), QPointF(54, 12))
    _accent(p, 7)
    p.drawPoint(QPointF(10, 52)); p.drawPoint(QPointF(54, 12))


def _open(p):
    p.drawRect(QRectF(8, 18, 48, 34)); p.drawLine(QPointF(8, 18), QPointF(20, 10))
    p.drawLine(QPointF(20, 10), QPointF(32, 10)); p.drawLine(QPointF(32, 10), QPointF(36, 18))


def _save(p):
    p.drawRect(QRectF(10, 10, 44, 44)); p.drawRect(QRectF(20, 10, 24, 14)); p.drawRect(QRectF(18, 34, 28, 20))


def _quit(p):
    """Quitter : porte ouverte et flèche qui sort."""
    p.drawRect(QRectF(10, 8, 26, 48))
    _accent(p)
    p.drawLine(QPointF(26, 32), QPointF(56, 32))
    p.drawLine(QPointF(46, 22), QPointF(56, 32))
    p.drawLine(QPointF(46, 42), QPointF(56, 32))


def _new(p):
    path = QPainterPath(); path.moveTo(14, 6); path.lineTo(40, 6); path.lineTo(50, 16)
    path.lineTo(50, 58); path.lineTo(14, 58); path.closeSubpath(); p.drawPath(path)


def _import(p):
    _new(p); _accent(p); p.drawLine(QPointF(32, 18), QPointF(32, 46))
    p.drawLine(QPointF(22, 36), QPointF(32, 46)); p.drawLine(QPointF(42, 36), QPointF(32, 46))


def _export(p):
    _new(p); _accent(p); p.drawLine(QPointF(32, 46), QPointF(32, 18))
    p.drawLine(QPointF(22, 28), QPointF(32, 18)); p.drawLine(QPointF(42, 28), QPointF(32, 18))


def _undo(p):
    path = QPainterPath(); path.moveTo(16, 30); path.arcTo(QRectF(16, 16, 36, 30), 180, -220)
    p.drawPath(path); p.drawLine(QPointF(16, 30), QPointF(10, 20)); p.drawLine(QPointF(16, 30), QPointF(26, 26))


def _redo(p):
    p.translate(64, 0); p.scale(-1, 1); _undo(p)


def _zoom_fit(p):
    p.drawEllipse(QRectF(10, 10, 32, 32)); p.drawLine(QPointF(38, 38), QPointF(56, 56))
    _accent(p, 3); p.drawRect(QRectF(18, 18, 16, 16))


def _zoom_in(p):
    p.drawEllipse(QRectF(10, 10, 32, 32)); p.drawLine(QPointF(38, 38), QPointF(56, 56))
    p.drawLine(QPointF(19, 26), QPointF(33, 26)); p.drawLine(QPointF(26, 19), QPointF(26, 33))


def _zoom_out(p):
    p.drawEllipse(QRectF(10, 10, 32, 32)); p.drawLine(QPointF(38, 38), QPointF(56, 56))
    p.drawLine(QPointF(19, 26), QPointF(33, 26))


def _mirror_h(p):
    p.drawLine(QPointF(32, 6), QPointF(32, 58))
    p.drawPolygon([QPointF(26, 14), QPointF(8, 50), QPointF(26, 50)])
    _accent(p); p.drawPolygon([QPointF(38, 14), QPointF(56, 50), QPointF(38, 50)])


def _mirror_v(p):
    p.translate(64, 0); p.rotate(90); _mirror_h(p)


def _rotate(p):
    path = QPainterPath(); path.moveTo(52, 32); path.arcTo(QRectF(12, 12, 40, 40), 0, 270)
    p.drawPath(path); _accent(p); p.drawLine(QPointF(32, 12), QPointF(40, 6)); p.drawLine(QPointF(32, 12), QPointF(40, 18))


def _align(kind):
    def d(p):
        if kind in ('left', 'right', 'hcenter'):
            x = {'left': 10, 'right': 54, 'hcenter': 32}[kind]
            _accent(p); p.drawLine(QPointF(x, 6), QPointF(x, 58)); p.setPen(QPen(_INK, 4))
            w1, w2 = 36, 22
            for y, w in ((14, w1), (38, w2)):
                x0 = {'left': 10, 'right': 54 - w, 'hcenter': 32 - w / 2}[kind]
                p.drawRect(QRectF(x0, y, w, 14))
        else:
            y = {'top': 10, 'bottom': 54, 'vcenter': 32}[kind]
            _accent(p); p.drawLine(QPointF(6, y), QPointF(58, y)); p.setPen(QPen(_INK, 4))
            for x, h in ((14, 36), (38, 22)):
                y0 = {'top': 10, 'bottom': 54 - h, 'vcenter': 32 - h / 2}[kind]
                p.drawRect(QRectF(x, y0, 14, h))
    return d


def _center_plate(p):
    p.drawRect(QRectF(6, 12, 52, 40)); _accent(p); p.drawEllipse(QRectF(22, 22, 20, 20))


def _group(p):
    p.drawRect(QRectF(8, 8, 26, 22)); p.drawEllipse(QRectF(28, 28, 28, 28))
    pen = QPen(_ACCENT, 2, Qt.PenStyle.DashLine); p.setPen(pen); p.drawRect(QRectF(4, 4, 56, 56))


def _ungroup(p):
    p.drawRect(QRectF(6, 6, 24, 20)); p.drawEllipse(QRectF(32, 32, 26, 26))


def _delete(p):
    _accent(p, 6); p.drawLine(QPointF(14, 14), QPointF(50, 50)); p.drawLine(QPointF(50, 14), QPointF(14, 50))


def _oops(p):
    """Rappeler l'effacement : l'objet effacé en tirets, la flèche qui le
    ramène."""
    p.setPen(QPen(_INK, 3, Qt.PenStyle.DashLine))
    p.drawRect(QRectF(24, 24, 32, 32))
    _accent(p, 5)
    path = QPainterPath(QPointF(40, 40))
    path.lineTo(QPointF(40, 18))
    path.arcTo(QRectF(10, 6, 30, 24), 0, 180)
    path.lineTo(QPointF(10, 30))
    p.drawPath(path)
    p.drawPolyline([QPointF(33, 33), QPointF(40, 40), QPointF(47, 33)])


def _change_point(p):
    """Changer par un point : deux traits et un cercle tirés vers le point
    cliqué."""
    p.drawLine(QPointF(6, 54), QPointF(40, 22))
    p.drawLine(QPointF(6, 30), QPointF(40, 22))
    p.drawEllipse(QPointF(40, 22), 18, 18)
    _accent(p, 3)
    p.drawLine(QPointF(34, 22), QPointF(46, 22))
    p.drawLine(QPointF(40, 16), QPointF(40, 28))


def _measure(p):
    p.drawRect(QRectF(6, 22, 52, 20))
    for i, x in enumerate(range(12, 56, 8)):
        p.drawLine(QPointF(x, 22), QPointF(x, 30 if i % 2 else 34))


def _plate(p):
    p.setBrush(QColor('#e8e2d0')); p.drawRoundedRect(QRectF(6, 14, 52, 36), 8, 8)


def _grid(p):
    pen = QPen(_INK, 2); p.setPen(pen)
    for v in range(8, 60, 12):
        p.drawLine(QPointF(v, 6), QPointF(v, 58)); p.drawLine(QPointF(6, v), QPointF(58, v))


def _direction(p):
    p.drawEllipse(QRectF(10, 10, 44, 44)); _accent(p)
    p.drawLine(QPointF(54, 32), QPointF(46, 24)); p.drawLine(QPointF(54, 32), QPointF(60, 22))


def _fill(p):
    p.setBrush(QColor('#9db4d8')); p.drawEllipse(QRectF(10, 10, 44, 44))


def _copy(p):
    p.drawRect(QRectF(8, 8, 32, 38)); p.setBrush(QColor('#ffffff')); p.drawRect(QRectF(24, 20, 32, 38))


def _paste(p):
    p.drawRect(QRectF(10, 12, 40, 46)); _accent(p); p.drawRect(QRectF(22, 6, 16, 10))


def _cut(p):
    p.drawEllipse(QRectF(8, 40, 16, 16)); p.drawEllipse(QRectF(40, 40, 16, 16))
    p.drawLine(QPointF(20, 42), QPointF(46, 6)); p.drawLine(QPointF(44, 42), QPointF(18, 6))


def _select_all(p):
    pen = QPen(_INK, 3, Qt.PenStyle.DashLine); p.setPen(pen); p.drawRect(QRectF(6, 6, 52, 52))
    p.setPen(QPen(_INK, 4)); p.drawRect(QRectF(14, 16, 16, 14)); p.drawEllipse(QRectF(34, 32, 18, 18))


def _invert(p):
    _select_all(p); _accent(p); p.drawLine(QPointF(10, 54), QPointF(54, 10))


def _duplicate_scaled(p):
    path = QPainterPath(QPointF(6, 54))
    path.cubicTo(QPointF(20, 10), QPointF(44, 10), QPointF(58, 30))
    p.drawPath(path)
    _accent(p)
    for x, y, r in ((10, 46, 4), (26, 24, 6), (48, 20, 8)):
        p.drawEllipse(QRectF(x - r, y - r, 2 * r, 2 * r))


def _variables(p):
    p.drawRect(QRectF(8, 10, 48, 44))
    for y in (24, 38):
        p.drawLine(QPointF(8, y), QPointF(56, y))
    p.drawLine(QPointF(28, 10), QPointF(28, 54))
    _accent(p)
    p.drawLine(QPointF(36, 16), QPointF(36, 20))


def _insert_variable(p):
    f = p.font(); f.setPixelSize(30); f.setBold(True); p.setFont(f)
    p.drawText(QRectF(4, 8, 56, 48), Qt.AlignmentFlag.AlignCenter, 'A')
    _accent(p)
    p.drawLine(QPointF(10, 12), QPointF(10, 52)); p.drawLine(QPointF(54, 12), QPointF(54, 52))


def _variables_produce(p):
    for i in range(3):
        p.drawRect(QRectF(6 + i * 6, 6 + i * 6, 34, 26))
    _accent(p)
    p.drawLine(QPointF(30, 46), QPointF(54, 46)); p.drawLine(QPointF(46, 38), QPointF(54, 46))
    p.drawLine(QPointF(46, 54), QPointF(54, 46))


def _selection_modes(p):
    pen = QPen(_INK, 3, Qt.PenStyle.DashLine); p.setPen(pen); p.drawRect(QRectF(6, 6, 36, 36))
    _accent(p)
    p.drawLine(QPointF(44, 52), QPointF(58, 52)); p.drawLine(QPointF(51, 45), QPointF(51, 59))


def _lasso(p):
    path = QPainterPath(QPointF(14, 40))
    path.cubicTo(QPointF(0, 10), QPointF(50, 0), QPointF(56, 24))
    path.cubicTo(QPointF(60, 44), QPointF(30, 50), QPointF(22, 42))
    p.drawPath(path)
    _accent(p)
    p.drawLine(QPointF(22, 42), QPointF(18, 58))


def _text_arcs(p):
    p.drawArc(QRectF(6, 14, 52, 52), 30 * 16, 120 * 16)
    _accent(p)
    p.drawArc(QRectF(14, 22, 36, 36), 30 * 16, 120 * 16)


def _char_map(p):
    for i in range(3):
        for j in range(3):
            p.drawRect(QRectF(6 + i * 18, 6 + j * 18, 16, 16))
    _accent(p)
    f = p.font(); f.setPixelSize(14); f.setBold(True); p.setFont(f)
    p.drawText(QRectF(24, 24, 16, 16), Qt.AlignmentFlag.AlignCenter, 'Ø')


def _font_recognize(p):
    f = p.font(); f.setPixelSize(36); f.setBold(True); p.setFont(f)
    p.drawText(QRectF(2, 2, 36, 44), Qt.AlignmentFlag.AlignCenter, 'A')
    _accent(p)
    p.drawEllipse(QRectF(30, 28, 20, 20)); p.drawLine(QPointF(47, 45), QPointF(58, 58))


def _texture(p):
    from ..core.texture import curve_points, fit
    pts = fit(curve_points('hilbert', 2), (8, 8, 56, 56))
    _accent(p)
    for a, b in zip(pts, pts[1:]):
        p.drawLine(QPointF(*a), QPointF(*b))


def _cut_pattern(p):
    p.drawRect(QRectF(6, 10, 52, 44))
    _accent(p)
    p.drawLine(QPointF(24, 10), QPointF(24, 54)); p.drawLine(QPointF(40, 10), QPointF(40, 54))
    p.drawLine(QPointF(6, 32), QPointF(58, 32))


def _leds(p):
    p.drawRoundedRect(QRectF(6, 14, 52, 36), 6, 6)
    _accent(p)
    for x in (16, 32, 48):
        p.drawEllipse(QRectF(x - 4, 28, 8, 8))


def _marquetry(p):
    p.drawRoundedRect(QRectF(6, 10, 52, 44), 8, 8)
    _accent(p)
    p.drawRoundedRect(QRectF(18, 22, 28, 20), 6, 6)


def _select_filter(p):
    pen = QPen(_INK, 3, Qt.PenStyle.DashLine); p.setPen(pen); p.drawRect(QRectF(6, 6, 52, 52))
    _accent(p)
    p.drawPolygon([QPointF(14, 16), QPointF(50, 16), QPointF(36, 32), QPointF(36, 48), QPointF(28, 44),
                   QPointF(28, 32)])


def _pdf(p):
    _new(p); _accent(p); f = p.font(); f.setPixelSize(16); f.setBold(True); p.setFont(f)
    p.drawText(QRectF(14, 26, 36, 24), Qt.AlignmentFlag.AlignCenter, 'BAT')


def _polygon(p):
    pts = [QPointF(32 + 24 * math.cos(math.radians(90 + 72 * i)), 34 - 24 * math.sin(math.radians(90 + 72 * i)))
           for i in range(5)]
    p.drawPolygon(pts)


def _rect3(p):
    """Rectangle 3 points : le rectangle incliné, son premier côté en accent
    entre les deux premiers points, le troisième point en face."""
    pts = [QPointF(10, 44), QPointF(40, 56), QPointF(54, 21), QPointF(24, 9)]
    p.drawPolygon(pts)
    _accent(p, 4)
    p.drawLine(pts[0], pts[1])
    _accent(p, 8)
    for q in (pts[0], pts[1], pts[2]):
        p.drawPoint(q)


def _ellipse_axis(p):
    """Ellipse par axe : l'ellipse inclinée, son axe en accent entre ses deux
    bouts."""
    p.save()
    p.translate(32, 32)
    p.rotate(-30)
    p.drawEllipse(QRectF(-26, -14, 52, 28))
    _accent(p, 3)
    p.drawLine(QPointF(-26, 0), QPointF(26, 0))
    _accent(p, 8)
    p.drawPoint(QPointF(-26, 0))
    p.drawPoint(QPointF(26, 0))
    p.restore()


def _polygon_edge(p):
    """Polygone par côté : l'hexagone posé sur son côté du bas, tracé en
    accent entre ses deux points."""
    pts = [QPointF(32 + 22 * math.cos(math.radians(-120 + 60 * i)), 32 - 22 * math.sin(math.radians(-120 + 60 * i)))
           for i in range(6)]
    p.drawPolygon(pts)
    _accent(p, 4)
    p.drawLine(pts[0], pts[1])
    _accent(p, 8)
    p.drawPoint(pts[0])
    p.drawPoint(pts[1])


def _polyline(p):
    p.drawPolyline([QPointF(8, 50), QPointF(22, 18), QPointF(40, 40), QPointF(56, 12)])
    _accent(p, 6)
    for q in ((8, 50), (22, 18), (40, 40), (56, 12)):
        p.drawPoint(QPointF(*q))


def _bezier(p):
    path = QPainterPath()
    path.moveTo(8, 52)
    path.cubicTo(8, 8, 56, 56, 56, 12)
    p.drawPath(path)
    _accent(p, 2)
    p.drawLine(QPointF(8, 52), QPointF(8, 8))
    p.drawLine(QPointF(56, 12), QPointF(56, 56))


def _star(p):
    pts = [QPointF(32 + (26 if i % 2 == 0 else 11) * math.cos(math.radians(90 + 36 * i)),
                   34 - (26 if i % 2 == 0 else 11) * math.sin(math.radians(90 + 36 * i))) for i in range(10)]
    p.drawPolygon(pts)


def _spiral(p):
    path = QPainterPath()
    path.moveTo(32, 32)
    for i in range(1, 181):
        th = i / 180 * 3 * 2 * math.pi
        r = 24 * i / 180
        path.lineTo(32 + r * math.cos(th), 32 - r * math.sin(th))
    p.drawPath(path)
    _accent(p, 6)
    p.drawPoint(QPointF(32 + 24, 32))


def _approximate(p):
    pts = [(6, 50), (14, 30), (22, 22), (32, 20), (42, 26), (50, 38), (58, 44)]
    for a, b in zip(pts, pts[1:]):
        p.drawLine(QPointF(*a), QPointF(*b))
    _accent(p, 3)
    path = QPainterPath()
    path.moveTo(6, 50)
    path.cubicTo(14, 10, 46, 10, 58, 44)
    p.drawPath(path)


def _segment(p):
    path = QPainterPath()
    path.moveTo(6, 50)
    path.cubicTo(14, 6, 50, 6, 58, 50)
    p.drawPath(path)
    _accent(p, 3)
    pts = [(6, 50), (12, 30), (22, 18), (32, 15), (42, 18), (52, 30), (58, 50)]
    for a, b in zip(pts, pts[1:]):
        p.drawLine(QPointF(*a), QPointF(*b))


def _arc(p):
    path = QPainterPath()
    path.moveTo(8, 48)
    path.quadTo(32, -4, 56, 48)
    p.drawPath(path)
    _accent(p, 6)
    for q in ((8, 48), (32, 22), (56, 48)):
        p.drawPoint(QPointF(*q))


def _arc_center(p):
    """Arc centre, départ, fin : l'arc et ses deux rayons depuis le centre."""
    p.drawArc(QRectF(8, 22, 48, 48), 0, 135 * 16)
    _accent(p, 3)
    p.drawLine(QPointF(32, 46), QPointF(56, 46))
    p.drawLine(QPointF(32, 46), QPointF(15, 29))
    _accent(p, 7)
    p.drawPoint(QPointF(32, 46))


def _circle2(p):
    """Cercle 2 points : le cercle et son diamètre entre les deux points."""
    p.drawEllipse(QRectF(8, 8, 48, 48))
    _accent(p, 3)
    p.drawLine(QPointF(15, 49), QPointF(49, 15))
    _accent(p, 7)
    p.drawPoint(QPointF(15, 49))
    p.drawPoint(QPointF(49, 15))


def _text(p):
    f = p.font()
    f.setPixelSize(44)
    f.setBold(True)
    p.setFont(f)
    p.drawText(QRectF(4, 4, 56, 56), Qt.AlignmentFlag.AlignCenter, 'A')


def _node(p):
    path = QPainterPath()
    path.moveTo(6, 50)
    path.cubicTo(20, 6, 44, 6, 58, 50)
    p.drawPath(path)
    p.setBrush(QColor('#ffffff'))
    _accent(p, 3)
    for q in ((6, 50), (32, 17), (58, 50)):
        p.drawRect(QRectF(q[0] - 5, q[1] - 5, 10, 10))


def _bool(kind):
    def d(p):
        a, b = QRectF(6, 10, 32, 32), QRectF(26, 22, 32, 32)
        pa, pb = QPainterPath(), QPainterPath()
        pa.addRect(a)
        pb.addEllipse(b)
        res = {'union': pa.united(pb), 'intersect': pa.intersected(pb),
               'difference': pa.subtracted(pb),
               'xor': pa.united(pb).subtracted(pa.intersected(pb))}[kind]
        p.setBrush(QColor('#9db4d8'))
        p.drawPath(res)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(_INK, 1, Qt.PenStyle.DashLine))
        p.drawRect(a)
        p.drawEllipse(b)
    return d


def _offset(p):
    p.drawRect(QRectF(20, 20, 24, 24))
    _accent(p, 3)
    p.drawRoundedRect(QRectF(8, 8, 48, 48), 12, 12)


def _double_line(p):
    path = QPainterPath()
    path.moveTo(6, 44)
    path.cubicTo(20, 10, 40, 10, 58, 30)
    p.drawPath(path)
    _accent(p, 3)
    p.drawPath(path.translated(0, 12))


def _dashes(p):
    """Courbe en tirets, un point au bout."""
    path = QPainterPath()
    path.moveTo(6, 46)
    path.cubicTo(20, 12, 40, 12, 58, 34)
    pen = QPen(p.pen())
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    pen.setDashPattern([2.2, 1.4])
    p.setPen(pen)
    p.drawPath(path)
    _accent(p, 6)
    p.drawPoint(QPointF(58, 50))


def _tan_circle(p):
    """Cercle tangent à deux traits, points de contact marqués."""
    p.drawLine(QPointF(4, 54), QPointF(60, 54))
    p.drawLine(QPointF(4, 54), QPointF(40, 6))
    p.drawEllipse(QPointF(32, 40), 14, 14)
    _accent(p, 6)
    p.drawPoint(QPointF(32, 54))
    p.drawPoint(QPointF(20.8, 31.6))


def _text_path(p):
    """Lettres posées le long d'une courbe."""
    path = QPainterPath()
    path.moveTo(4, 60)
    path.quadTo(32, 20, 60, 60)
    pen = QPen(p.pen())
    _accent(p, 3)
    p.drawPath(path)
    pen.setWidthF(min(pen.widthF(), 3.0))
    pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    p.setPen(pen)
    for t in (0.18, 0.5, 0.82):                              # trois A en traits, droits sur la courbe
        x = (1 - t) ** 2 * 4 + 2 * t * (1 - t) * 32 + t * t * 60
        y = (1 - t) ** 2 * 60 + 2 * t * (1 - t) * 20 + t * t * 60
        dx, dy = 2 * (1 - t) * 28 + 2 * t * 28, 2 * (1 - t) * -40 + 2 * t * 40
        p.save()
        p.translate(x, y)
        p.rotate(math.degrees(math.atan2(dy, dx)))
        p.drawPolyline([QPointF(-6, -4), QPointF(0, -20), QPointF(6, -4)])
        p.drawLine(QPointF(-3.6, -10.5), QPointF(3.6, -10.5))
        p.restore()


def _measure_radius(p):
    """Cercle, son centre et un rayon fléché."""
    p.drawEllipse(QPointF(30, 34), 22, 22)
    _accent(p, 3)
    p.drawLine(QPointF(30, 34), QPointF(45.6, 18.4))
    p.drawPolyline([QPointF(37, 19), QPointF(45.6, 18.4), QPointF(45, 27)])
    _accent(p, 7)
    p.drawPoint(QPointF(30, 34))


def _dim_arc(p):
    """Cote de longueur d'arc : un arc, l'arc de cote et le symbole d'arc."""
    p.drawArc(QRectF(12, 26, 40, 40), 15 * 16, 150 * 16)
    _accent(p, 3)
    p.drawArc(QRectF(4, 18, 56, 56), 15 * 16, 150 * 16)
    p.drawArc(QRectF(24, 4, 16, 10), 0, 180 * 16)


def _measure_angle(p):
    """Deux côtés et l'arc de leur angle."""
    p.drawLine(QPointF(8, 54), QPointF(58, 54))
    p.drawLine(QPointF(8, 54), QPointF(38, 12))
    _accent(p, 3)
    p.drawArc(QRectF(8 - 28, 54 - 28, 56, 56), 0, int(54.5 * 16))


def _text_merge(p):
    """Lignes éparses réunies en un paragraphe."""
    for x0, x1, y in ((4, 20, 16), (10, 26, 32), (2, 18, 48)):
        p.drawLine(QPointF(x0, y), QPointF(x1, y))
    pen = QPen(p.pen())
    _accent(p, 3)
    p.drawLine(QPointF(30, 32), QPointF(40, 32))
    p.drawPolyline([QPointF(36, 27), QPointF(41, 32), QPointF(36, 37)])
    p.setPen(pen)
    for y in (18, 32, 46):
        p.drawLine(QPointF(46, y), QPointF(60, y))


def _sheets(p):
    """Deux feuilles décalées (comparaison)."""
    p.drawRect(QRectF(6, 6, 30, 40))
    p.drawRect(QRectF(28, 18, 30, 40))


def _compare(p):
    """Deux feuilles et l'écart entre elles."""
    _sheets(p)
    _accent(p, 3)
    p.drawLine(QPointF(12, 54), QPointF(22, 54))
    p.drawLine(QPointF(17, 49), QPointF(17, 59))
    p.drawLine(QPointF(44, 10), QPointF(56, 10))


def _compare_next(p):
    _sheets(p)
    _accent(p, 4)
    p.drawPolyline([QPointF(38, 28), QPointF(48, 38), QPointF(38, 48)])


def _compare_prev(p):
    _sheets(p)
    _accent(p, 4)
    p.drawPolyline([QPointF(48, 28), QPointF(38, 38), QPointF(48, 48)])


def _compare_close(p):
    _sheets(p)
    _accent(p, 4)
    p.drawLine(QPointF(36, 30), QPointF(50, 44))
    p.drawLine(QPointF(50, 30), QPointF(36, 44))


def _fill_toggle(p):
    """Carré à moitié rempli : remplir ou vider."""
    p.drawRect(QRectF(10, 10, 44, 44))
    path = QPainterPath()
    path.addRect(QRectF(10, 10, 22, 44))
    p.fillPath(path, _ACCENT)


def _match_props(p):
    """Pinceau : manche, virole, poils, et la trace laissée."""
    p.drawLine(QPointF(50, 6), QPointF(34, 30))
    p.drawPolygon([QPointF(30, 26), QPointF(40, 33), QPointF(34, 42), QPointF(24, 35)])
    path = QPainterPath()
    path.moveTo(24, 35)
    path.cubicTo(16, 40, 12, 48, 8, 58)
    path.cubicTo(20, 56, 30, 50, 34, 42)
    p.drawPath(path)
    _accent(p, 3)
    p.drawLine(QPointF(40, 58), QPointF(60, 58))


def _fx_scallop(p):
    """Bord en festons : arcs bombés le long d'un rectangle."""
    for i in range(3):                                          # haut et bas
        x = 8 + 16 * i
        p.drawArc(QRectF(x, 8, 16, 12), 0, 180 * 16)
        p.drawArc(QRectF(x, 44, 16, 12), 180 * 16, 180 * 16)
    for j in range(2):                                          # côtés
        y = 14 + 18 * j
        p.drawArc(QRectF(2, y, 12, 18), 90 * 16, 180 * 16)
        p.drawArc(QRectF(50, y, 12, 18), -90 * 16, 180 * 16)


def _xline(p):
    """Ligne de construction : un trait qui traverse tout, par un point."""
    p.drawLine(QPointF(4, 54), QPointF(60, 10))
    p.drawPolyline([QPointF(4, 46), QPointF(4, 54), QPointF(12, 54)])
    p.drawPolyline([QPointF(52, 10), QPointF(60, 10), QPointF(60, 18)])
    _accent(p, 3)
    p.drawEllipse(QRectF(27, 27, 10, 10))


def _center_line(p):
    """Ligne d'axe : un trait mixte entre deux traits."""
    p.drawLine(QPointF(8, 14), QPointF(56, 14))
    p.drawLine(QPointF(8, 50), QPointF(56, 50))
    _accent(p, 3)
    for x0, x1 in ((2, 22), (28, 36), (42, 62)):
        p.drawLine(QPointF(x0, 32), QPointF(x1, 32))


def _remove_loops(p):
    path = QPainterPath()
    path.moveTo(6, 44)
    path.lineTo(30, 44)
    path.cubicTo(52, 44, 44, 14, 32, 22)
    path.cubicTo(24, 28, 30, 44, 58, 44)
    p.drawPath(path)
    _accent(p, 3)
    p.drawLine(QPointF(40, 10), QPointF(56, 26))
    p.drawLine(QPointF(56, 10), QPointF(40, 26))


def _same_size(kind):
    def draw(p):
        p.drawRect(QRectF(6, 20, 20, 24) if kind != 'h' else QRectF(6, 14, 22, 36))
        _accent(p, 3)
        if kind == 'w':
            p.drawRect(QRectF(34, 26, 20, 12))
        elif kind == 'h':
            p.drawRect(QRectF(36, 14, 20, 36))
        else:
            p.drawRect(QRectF(34, 20, 20, 24))
    return draw


def _node_icon(kind):
    def draw(p):
        if kind == 'node_line':
            path = QPainterPath()
            path.moveTo(8, 48)
            path.cubicTo(20, 8, 44, 8, 56, 48)
            pen = p.pen()
            pen.setStyle(Qt.PenStyle.DotLine)
            p.setPen(pen)
            p.drawPath(path)
            _accent(p, 3)
            p.drawLine(QPointF(8, 48), QPointF(56, 48))
        elif kind == 'node_curve':
            p.drawLine(QPointF(8, 48), QPointF(56, 48))
            _accent(p, 3)
            path = QPainterPath()
            path.moveTo(8, 48)
            path.cubicTo(20, 8, 44, 8, 56, 48)
            p.drawPath(path)
        elif kind in ('node_smooth', 'node_symmetric'):
            path = QPainterPath()
            path.moveTo(6, 50)
            path.cubicTo(14, 20, 24, 20, 32, 20)
            path.cubicTo(40, 20, 50, 20, 58, 50)
            p.drawPath(path)
            _accent(p, 3)
            a = 14 if kind == 'node_symmetric' else 10
            p.drawLine(QPointF(32 - a, 20), QPointF(32 + 14, 20))
            p.drawEllipse(QPointF(32, 20), 3, 3)
        else:
            horiz = kind == 'node_align_h'
            _accent(p, 2)
            if horiz:
                p.drawLine(QPointF(4, 32), QPointF(60, 32))
            else:
                p.drawLine(QPointF(32, 4), QPointF(32, 60))
            p.setPen(QPen(_INK, 3))
            for t in (14, 32, 50):
                q = QPointF(t, 32) if horiz else QPointF(32, t)
                p.drawRect(QRectF(q.x() - 4, q.y() - 4, 8, 8))
    return draw


def _node_refine(p):
    """Courbe et points doublés."""
    path = QPainterPath()
    path.moveTo(6, 48)
    path.cubicTo(18, 10, 46, 10, 58, 48)
    p.drawPath(path)
    p.setPen(QPen(_INK, 3))
    for x, y in ((6, 48), (32, 20), (58, 48)):
        p.drawRect(QRectF(x - 4, y - 4, 8, 8))
    _accent(p, 3)
    for x, y in ((14, 30), (50, 30)):
        p.drawRect(QRectF(x - 4, y - 4, 8, 8))


def _node_portion(kind):
    def draw(p):
        path = QPainterPath()
        path.moveTo(6, 50)
        path.cubicTo(14, 14, 50, 14, 58, 50)
        pen = p.pen()
        pen.setStyle(Qt.PenStyle.DotLine)
        p.setPen(pen)
        p.drawPath(path)
        _accent(p, 3)
        if kind == 'segment':
            p.drawLine(QPointF(6, 50), QPointF(58, 50))
        else:
            p.drawLine(QPointF(6, 50), QPointF(32, 12))
            p.drawLine(QPointF(32, 12), QPointF(58, 50))
        p.setPen(QPen(_INK, 3))
        for x in (6, 58):
            p.drawRect(QRectF(x - 4, 46, 8, 8))
    return draw


def _view_plane(kind):
    """Pièce vue de côté (YZ) ou de face (ZX) : profil et axes."""
    def draw(p):
        p.drawLine(QPointF(8, 54), QPointF(56, 54))
        p.drawLine(QPointF(8, 54), QPointF(8, 8))
        _accent(p, 3)
        p.setBrush(QColor('#c9a27a'))
        p.drawRect(QRectF(16, 34, 34, 14) if kind == 'yz' else QRectF(14, 30, 40, 18))
        p.setPen(QPen(_INK, 2))
        f = p.font()
        f.setPixelSize(13)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(22, 6, 36, 20), Qt.AlignmentFlag.AlignCenter, kind.upper())
    return draw


def _node_project(kind):
    """Point projeté sur un repère (trait), flèche de projection."""
    def draw(p):
        p.drawLine(QPointF(4, 48), QPointF(60, 48) if kind != 'perp' else QPointF(60, 20))
        p.setPen(QPen(_INK, 3))
        src = QPointF(22, 14) if kind != 'h' else QPointF(10, 30)
        p.drawRect(QRectF(src.x() - 4, src.y() - 4, 8, 8))
        _accent(p, 3)
        if kind == 'v':
            dst = QPointF(22, 48)
        elif kind == 'h':
            p.drawLine(QPointF(48, 8), QPointF(48, 56))
            dst = QPointF(48, 30)
        else:
            dst = QPointF(32.3, 34.9)                       # pied de la perpendiculaire
        p.drawLine(src, dst)
        p.drawEllipse(dst, 4, 4)
    return draw


def _align_center(p):
    """Deux objets centrés l'un sur l'autre, croix du centre."""
    p.drawRect(QRectF(8, 14, 48, 36))
    p.drawRect(QRectF(22, 24, 20, 16))
    _accent(p, 2)
    p.drawLine(QPointF(32, 6), QPointF(32, 58))
    p.drawLine(QPointF(4, 32), QPointF(60, 32))


def _contour_move(p):
    """Objet à deux contours, le petit déplacé (flèche)."""
    p.drawRect(QRectF(6, 10, 40, 44))
    pen = p.pen()
    pen.setStyle(Qt.PenStyle.DotLine)
    p.setPen(pen)
    p.drawEllipse(QPointF(20, 32), 8, 8)
    _accent(p, 3)
    p.drawEllipse(QPointF(44, 32), 8, 8)
    p.drawLine(QPointF(24, 48), QPointF(42, 48))
    p.drawLine(QPointF(42, 48), QPointF(36, 44))
    p.drawLine(QPointF(42, 48), QPointF(36, 52))


def _axis_align(kind):
    """Pièce penchée redressée autour d'un pivot, axe en pointillés."""
    def draw(p):
        pen = p.pen()
        pen.setStyle(Qt.PenStyle.DotLine)
        p.setPen(pen)
        tilted = QPainterPath()
        tilted.moveTo(16, 50)
        tilted.lineTo(44, 40)
        tilted.lineTo(36, 18)
        tilted.lineTo(8, 28)
        tilted.closeSubpath()
        p.drawPath(tilted)
        p.setPen(QPen(_INK, 3))
        if kind == 'v':
            p.drawRect(QRectF(16, 14, 22, 36))
        else:
            p.drawRect(QRectF(16, 28, 36, 22))
        _accent(p, 2)
        pen = p.pen()
        pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        if kind == 'v':
            p.drawLine(QPointF(16, 4), QPointF(16, 60))
        else:
            p.drawLine(QPointF(4, 50), QPointF(60, 50))
        p.setPen(QPen(_INK, 2))
        p.setBrush(QColor('#e04a2a'))
        p.drawEllipse(QPointF(16, 50), 4, 4)
    return draw


def _text_columns(p):
    for x in (8, 36):
        for k in range(5):
            y = 12 + k * 10
            p.drawLine(QPointF(x, y), QPointF(x + (20 if k % 2 == 0 else 16), y))
    _accent(p, 2)
    p.drawLine(QPointF(32, 8), QPointF(32, 56))


def _mirror_axis(p):
    path = QPainterPath()
    path.moveTo(10, 50)
    path.lineTo(26, 14)
    path.lineTo(30, 44)
    path.closeSubpath()
    p.drawPath(path)
    _accent(p, 2)
    pen = p.pen()
    pen.setStyle(Qt.PenStyle.DashLine)
    p.setPen(pen)
    p.drawLine(QPointF(36, 6), QPointF(36, 58))
    p.setPen(QPen(_INK, 3))
    path2 = QPainterPath()
    path2.moveTo(62, 50)
    path2.lineTo(46, 14)
    path2.lineTo(42, 44)
    path2.closeSubpath()
    p.drawPath(path2)


def _blend(p):
    p.drawLine(QPointF(6, 52), QPointF(30, 52))
    p.drawLine(QPointF(52, 30), QPointF(52, 6))
    _accent(p, 3)
    path = QPainterPath()
    path.moveTo(30, 52)
    path.quadTo(52, 52, 52, 30)
    p.drawPath(path)


def _blend_curve(p):
    """Raccord en courbe : deux traits reliés par une courbe dans leur
    prolongement."""
    p.drawLine(QPointF(4, 46), QPointF(22, 46))
    p.drawLine(QPointF(42, 18), QPointF(60, 18))
    _accent(p, 3)
    path = QPainterPath()
    path.moveTo(22, 46)
    path.cubicTo(36, 46, 28, 18, 42, 18)
    p.drawPath(path)


def _dim_jogged(p):
    """Cote radiale à ressaut : un grand arc, la ligne qui part près du bord
    et rejoint le rayon par un ressaut."""
    p.drawArc(QRectF(-40, 6, 100, 100), 30 * 16, 60 * 16)
    _accent(p, 3)
    p.drawPolyline([QPointF(8, 58), QPointF(8, 44), QPointF(20, 36), QPointF(20, 22), QPointF(30, 6)])
    p.drawPolyline([QPointF(23, 14), QPointF(30, 6), QPointF(29, 17)])


def _dim_jog_line(p):
    """Ressaut de cote : une ligne de cote coupée d'un zigzag."""
    p.drawLine(QPointF(4, 22), QPointF(4, 50))
    p.drawLine(QPointF(60, 22), QPointF(60, 50))
    _accent(p, 3)
    p.drawPolyline([QPointF(6, 36), QPointF(26, 36), QPointF(30, 24), QPointF(34, 48), QPointF(38, 36),
                    QPointF(58, 36)])
    p.drawPolyline([QPointF(12, 31), QPointF(6, 36), QPointF(12, 41)])
    p.drawPolyline([QPointF(52, 31), QPointF(58, 36), QPointF(52, 41)])


def _dim_inspect(p):
    """Cote d'inspection : la valeur dans un cadre à bouts ronds, séparée du
    taux."""
    p.drawLine(QPointF(4, 46), QPointF(60, 46))
    p.drawLine(QPointF(4, 38), QPointF(4, 54))
    p.drawLine(QPointF(60, 38), QPointF(60, 54))
    _accent(p, 3)
    p.drawRoundedRect(QRectF(8, 14, 48, 20), 10, 10)
    p.drawLine(QPointF(38, 14), QPointF(38, 34))
    p.drawLine(QPointF(16, 24), QPointF(32, 24))
    p.drawLine(QPointF(43, 24), QPointF(51, 24))


def _dim_space(p):
    """Espacer les cotes : trois lignes de cote parallèles à intervalle égal."""
    p.drawLine(QPointF(8, 60), QPointF(8, 6))
    p.drawLine(QPointF(56, 60), QPointF(56, 6))
    _accent(p, 3)
    for y in (14, 30, 46):
        p.drawLine(QPointF(10, y), QPointF(54, y))
        p.drawPolyline([QPointF(16, y - 4), QPointF(10, y), QPointF(16, y + 4)])
        p.drawPolyline([QPointF(48, y - 4), QPointF(54, y), QPointF(48, y + 4)])


def _gdt(p):
    """Cadre de tolérancement : trois cases, le symbole de localisation dans
    la première, la valeur, la référence."""
    p.drawRect(QRectF(2, 20, 60, 24))
    p.drawLine(QPointF(24, 20), QPointF(24, 44))
    p.drawLine(QPointF(46, 20), QPointF(46, 44))
    _accent(p, 3)
    p.drawEllipse(QPointF(13, 32), 5, 5)
    p.drawLine(QPointF(5, 32), QPointF(21, 32))
    p.drawLine(QPointF(13, 24), QPointF(13, 40))
    p.drawLine(QPointF(29, 32), QPointF(41, 32))
    p.drawPolyline([QPointF(49, 40), QPointF(54, 25), QPointF(59, 40)])
    p.drawLine(QPointF(51, 35), QPointF(57, 35))


def _coil(p):
    """Ressort : les spires d'une hélice vues de côté (le devant en couleur)."""
    for i in range(4):
        y = 50 - i * 11
        p.drawLine(QPointF(52, y), QPointF(12, y - 5.5))
    _accent(p, 4)
    for i in range(4):
        y = 50 - i * 11
        p.drawLine(QPointF(12, y + 5.5), QPointF(52, y))


def _thread(p):
    """Filetage : une tige et ses filets en biais."""
    p.drawRect(QRectF(20, 6, 24, 52))
    _accent(p, 3)
    for i in range(6):
        y = 14 + i * 8
        p.drawLine(QPointF(16, y + 3), QPointF(48, y - 3))


def _hole3d(p):
    """Perçage 3D : un bloc coupé, un trou lamé fini en pointe."""
    p.drawPolyline([QPointF(6, 14), QPointF(18, 14), QPointF(18, 26), QPointF(26, 26), QPointF(26, 46),
                    QPointF(32, 54), QPointF(38, 46), QPointF(38, 26), QPointF(46, 26), QPointF(46, 14),
                    QPointF(58, 14), QPointF(58, 58), QPointF(6, 58), QPointF(6, 14)])
    _accent(p, 3)
    p.drawLine(QPointF(32, 6), QPointF(32, 60))


def _pipe(p):
    """Tube : un tube coudé, l'intérieur visible au bout."""
    p.drawPolyline([QPointF(6, 18), QPointF(40, 18), QPointF(52, 30), QPointF(52, 58)])
    p.drawPolyline([QPointF(6, 34), QPointF(32, 34), QPointF(36, 38), QPointF(36, 58)])
    p.drawEllipse(QRectF(2, 18, 8, 16))
    _accent(p, 3)
    p.drawEllipse(QRectF(36, 54, 16, 6))


def _bounding(p):
    """Volume englobant : une pièce et le pavé tireté autour."""
    _accent(p, 3)
    p.drawEllipse(QRectF(18, 22, 28, 28))
    p.drawRect(QRectF(26, 12, 12, 12))
    pen = QPen(_INK, 3)
    pen.setStyle(Qt.PenStyle.DashLine)
    p.setPen(pen)
    p.drawRect(QRectF(8, 6, 48, 50))


def _rib(p):
    """Nervure : une coque vue en coupe, le mur ajouté entre ses parois."""
    p.drawPolyline([QPointF(6, 10), QPointF(6, 54), QPointF(58, 54), QPointF(58, 10)])
    p.drawPolyline([QPointF(12, 10), QPointF(12, 48), QPointF(52, 48), QPointF(52, 10)])
    _accent(p, 3)
    p.drawRect(QRectF(28, 22, 8, 26))


def _boss(p):
    """Bossage : un fût percé posé sur un plancher, ses nervures."""
    p.drawLine(QPointF(4, 54), QPointF(60, 54))
    _accent(p, 3)
    p.drawPolyline([QPointF(24, 54), QPointF(26, 14), QPointF(38, 14), QPointF(40, 54)])
    p.drawPolyline([QPointF(10, 54), QPointF(24, 32)])
    p.drawPolyline([QPointF(54, 54), QPointF(40, 32)])
    p.setPen(QPen(_INK, 2))
    p.drawLine(QPointF(32, 14), QPointF(32, 34))


def _wrap_emboss(p):
    """Relief sur cylindre : un cylindre couché, une lettre posée sur son
    pourtour."""
    p.drawLine(QPointF(10, 18), QPointF(54, 18))
    p.drawLine(QPointF(10, 50), QPointF(54, 50))
    p.drawEllipse(QRectF(4, 18, 12, 32))
    p.drawArc(QRectF(48, 18, 12, 32), -90 * 16, 180 * 16)
    _accent(p, 3)
    p.drawPolyline([QPointF(24, 42), QPointF(32, 24), QPointF(40, 42)])
    p.drawLine(QPointF(27, 36), QPointF(37, 36))


def _frame(p):
    """Profilé : une poutrelle en I vue en bout, sa longueur en fuite."""
    p.drawPolyline([QPointF(22, 10), QPointF(58, 4)])
    p.drawPolyline([QPointF(22, 54), QPointF(58, 48)])
    p.drawLine(QPointF(58, 4), QPointF(58, 48))
    _accent(p, 3)
    p.drawPolyline([QPointF(6, 10), QPointF(38, 10), QPointF(38, 16), QPointF(25, 16), QPointF(25, 48),
                    QPointF(38, 48), QPointF(38, 54), QPointF(6, 54), QPointF(6, 48), QPointF(19, 48),
                    QPointF(19, 16), QPointF(6, 16), QPointF(6, 10)])


def _lip(p):
    """Lèvre : coupe de la paroi d'une coque, la lèvre levée sur l'arête
    intérieure de son bord."""
    p.drawPolyline([QPointF(10, 58), QPointF(10, 30), QPointF(26, 30)])
    p.drawPolyline([QPointF(34, 30), QPointF(34, 50), QPointF(58, 50)])
    _accent(p, 3)
    p.drawPolyline([QPointF(26, 30), QPointF(26, 12), QPointF(34, 12), QPointF(34, 30)])


def _snap_fit(p):
    """Clip : un bras en porte-à-faux sur un plancher, le crochet en bout."""
    p.drawLine(QPointF(4, 56), QPointF(60, 56))
    _accent(p, 3)
    p.drawPolyline([QPointF(24, 56), QPointF(24, 8), QPointF(32, 8), QPointF(44, 24), QPointF(32, 24),
                    QPointF(32, 56)])


def _rest_pad(p):
    """Appui : un plot bas en dépouille posé sur une plaque."""
    p.drawRect(QRectF(4, 40, 56, 16))
    _accent(p, 3)
    p.drawPolyline([QPointF(16, 40), QPointF(21, 26), QPointF(43, 26), QPointF(48, 40)])


def _bent_sheet(p):
    """Tôle pliée : un profil en U aux coins arrondis, son flan à plat
    dessous avec les axes de pli."""
    path = QPainterPath(QPointF(8, 8))
    path.lineTo(8, 30)
    path.quadTo(8, 36, 14, 36)
    path.lineTo(50, 36)
    path.quadTo(56, 36, 56, 30)
    path.lineTo(56, 8)
    p.drawPath(path)
    _accent(p, 3)
    p.drawRect(QRectF(4, 46, 56, 12))
    p.setPen(QPen(_INK, 2, Qt.PenStyle.DashLine))
    p.drawLine(QPointF(22, 46), QPointF(22, 58))
    p.drawLine(QPointF(42, 46), QPointF(42, 58))


def _sheet_tray(p):
    """Bac en tôle : le développé en croix, axes de pli en tirets."""
    p.drawPolygon([QPointF(20, 4), QPointF(44, 4), QPointF(44, 20), QPointF(60, 20), QPointF(60, 44),
                   QPointF(44, 44), QPointF(44, 60), QPointF(20, 60), QPointF(20, 44), QPointF(4, 44),
                   QPointF(4, 20), QPointF(20, 20)])
    p.setPen(QPen(_ACCENT, 2, Qt.PenStyle.DashLine))
    p.drawRect(QRectF(20, 20, 24, 24))


def _sheet_fold(p):
    """Plier la tôle : une tôle à plat, le trait de pli en tirets, le rabat
    relevé au-delà."""
    p.drawPolygon([QPointF(4, 56), QPointF(36, 56), QPointF(44, 40), QPointF(12, 40)])
    p.drawPolygon([QPointF(36, 56), QPointF(44, 40), QPointF(44, 8), QPointF(36, 24)])
    p.setPen(QPen(_ACCENT, 2, Qt.PenStyle.DashLine))
    p.drawLine(QPointF(36, 56), QPointF(44, 40))
    _accent(p, 3)
    p.drawArc(QRectF(46, 20, 14, 24), 90 * 16, -180 * 16)


def _draft_analysis(p):
    """Analyse de surface : une pièce en dépouille, dessus vert, flancs
    jaunes, dessous rouge, et la flèche de démoulage."""
    for (a, b), col in ((((18, 34), (46, 34)), '#33bf4d'), (((18, 34), (8, 58)), '#f2cc26'),
                        (((46, 34), (56, 58)), '#f2cc26'), (((8, 58), (56, 58)), '#d93833')):
        pen = QPen(QColor(col), 5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(*a), QPointF(*b))
    _accent(p, 3)
    p.drawLine(QPointF(32, 26), QPointF(32, 4))
    p.drawPolyline([QPointF(25, 11), QPointF(32, 4), QPointF(39, 11)])


def _perforate(p):
    """Perforer : une tôle percée de trous en quinconce."""
    p.drawRect(QRectF(4, 8, 56, 48))
    _accent(p, 2)
    for j, y in enumerate((18, 32, 46)):
        for x in ((14, 28, 42) if j % 2 == 0 else (21, 35, 49)):
            p.drawEllipse(QPointF(x + (2 if j % 2 == 0 else 0), y), 4, 4)


def _scale3d(p):
    """Échelle 3D : un petit cube et le même agrandi, une flèche de l'un à
    l'autre."""
    p.drawRect(QRectF(6, 34, 18, 18))
    p.drawPolyline([QPointF(6, 34), QPointF(12, 28), QPointF(30, 28), QPointF(30, 46), QPointF(24, 52)])
    p.drawLine(QPointF(24, 34), QPointF(30, 28))
    _accent(p, 3)
    p.drawRect(QRectF(26, 18, 30, 30))
    p.drawPolyline([QPointF(26, 18), QPointF(34, 10), QPointF(62, 10)])
    p.drawLine(QPointF(56, 18), QPointF(62, 10))


def _cells(p):
    """Cellules : deux volumes qui se recouvrent, leur partie commune
    remplie."""
    p.drawEllipse(QRectF(4, 14, 36, 36))
    p.drawEllipse(QRectF(24, 14, 36, 36))
    _accent(p, 3)
    path = QPainterPath()
    path.addEllipse(QRectF(4, 14, 36, 36))
    other = QPainterPath()
    other.addEllipse(QRectF(24, 14, 36, 36))
    p.setBrush(_ACCENT)
    p.drawPath(path.intersected(other))
    p.setBrush(Qt.BrushStyle.NoBrush)


def _sym_draw(p):
    path = QPainterPath()
    path.moveTo(32, 56)
    path.cubicTo(50, 56, 56, 40, 46, 30)
    path.cubicTo(38, 22, 52, 12, 32, 8)
    p.drawPath(path)
    _accent(p, 3)
    p.drawPath(_mirror_path(path))
    pen = QPen(_ACCENT, 1, Qt.PenStyle.DashLine)
    p.setPen(pen)
    p.drawLine(QPointF(32, 4), QPointF(32, 60))


def _sym_curve_path():
    path = QPainterPath()
    path.moveTo(14, 44)
    path.cubicTo(14, 26, 34, 14, 50, 26)
    return path


def _sym_mark(p, h=False, v=False):
    p.setPen(QPen(_ACCENT, 1, Qt.PenStyle.DashLine))
    if h:
        p.drawLine(QPointF(4, 32), QPointF(60, 32))
    if v:
        p.drawLine(QPointF(32, 4), QPointF(32, 60))


def _sym_ox(p):
    from PySide6.QtGui import QTransform
    path = QPainterPath()
    path.moveTo(10, 32)
    path.cubicTo(12, 10, 52, 10, 54, 32)
    p.drawPath(path)
    _accent(p, 3)
    p.drawPath(QTransform(1, 0, 0, -1, 0, 64).map(path))
    _sym_mark(p, h=True)


def _sym_oy(p):
    path = QPainterPath()
    path.moveTo(32, 10)
    path.cubicTo(10, 12, 10, 52, 32, 54)
    p.drawPath(path)
    _accent(p, 3)
    p.drawPath(_mirror_path(path))
    _sym_mark(p, v=True)


def _sym_both(p):
    from PySide6.QtGui import QTransform
    path = QPainterPath()
    path.moveTo(32, 12)
    path.cubicTo(44, 12, 52, 20, 52, 32)
    p.drawPath(path)
    _accent(p, 3)
    for t in (QTransform(-1, 0, 0, 1, 64, 0), QTransform(1, 0, 0, -1, 0, 64), QTransform(-1, 0, 0, -1, 64, 64)):
        p.drawPath(t.map(path))
    _sym_mark(p, h=True, v=True)


def _sym_origin(p):
    from PySide6.QtGui import QTransform
    path = _sym_curve_path()
    path.cubicTo(58, 32, 48, 48, 32, 32)
    p.drawPath(path)
    _accent(p, 3)
    p.drawPath(QTransform(-1, 0, 0, -1, 64, 64).map(path))
    p.drawEllipse(QPointF(32, 32), 2, 2)


def _mirror_path(path):
    from PySide6.QtGui import QTransform
    return QTransform(-1, 0, 0, 1, 64, 0).map(path)


def _explode(p):
    for (a, b) in (((10, 50), (22, 14)), ((28, 10), (52, 10)), ((56, 16), (44, 52)), ((38, 56), (14, 56))):
        p.drawLine(QPointF(*a), QPointF(*b))
    _accent(p, 5)
    for q in ((25, 12), (54, 13), (41, 54), (12, 53)):
        p.drawPoint(QPointF(*q))


def _remove_contours(p):
    p.drawRect(QRectF(6, 8, 48, 48))
    _accent(p, 3)
    pen = p.pen()
    pen.setStyle(Qt.PenStyle.DotLine)
    p.setPen(pen)
    p.drawEllipse(QRectF(18, 20, 24, 24))
    p.setPen(QPen(_ACCENT, 3))
    p.drawLine(QPointF(44, 40), QPointF(60, 56))
    p.drawLine(QPointF(60, 40), QPointF(44, 56))


def _news(p):
    p.drawRoundedRect(QRectF(10, 8, 44, 48), 4, 4)
    for y in (22, 32, 42):
        p.drawLine(QPointF(18, y), QPointF(46, y))
    _accent(p, 3)
    path = QPainterPath()
    for k in range(10):
        import math as _m
        r = 10 if k % 2 == 0 else 4
        a = _m.radians(90 + 36 * k)
        q = QPointF(50 + r * _m.cos(a), 14 - r * _m.sin(a))
        path.moveTo(q) if k == 0 else path.lineTo(q)
    path.closeSubpath()
    p.drawPath(path)


def _command_search(p):
    p.drawEllipse(QRectF(10, 10, 30, 30))
    _accent(p, 6)
    p.drawLine(QPointF(36, 36), QPointF(54, 54))


def _marker(p):
    p.drawLine(QPointF(8, 32), QPointF(56, 32))
    p.drawLine(QPointF(32, 8), QPointF(32, 56))
    _accent(p, 3)
    p.drawEllipse(QPointF(32, 32), 12, 12)


def _bbox_frame(p):
    _accent(p, 3)
    p.drawRoundedRect(QRectF(6, 12, 52, 40), 6, 6)
    p.setPen(QPen(_INK, 3))
    p.drawLine(QPointF(16, 26), QPointF(48, 26))
    p.drawLine(QPointF(16, 38), QPointF(40, 38))


def _punch(p):
    p.drawRect(QRectF(6, 14, 40, 36))
    _accent(p, 3)
    p.drawEllipse(QRectF(30, 6, 28, 28))


def _trim(p):
    p.drawLine(QPointF(20, 6), QPointF(20, 58))
    p.drawLine(QPointF(44, 6), QPointF(44, 58))
    p.drawLine(QPointF(6, 32), QPointF(20, 32))
    p.drawLine(QPointF(44, 32), QPointF(58, 32))
    _accent(p, 3)
    pen = p.pen()
    pen.setStyle(Qt.PenStyle.DotLine)
    p.setPen(pen)
    p.drawLine(QPointF(20, 32), QPointF(44, 32))


def _extend(p):
    p.drawLine(QPointF(50, 6), QPointF(50, 58))
    p.drawLine(QPointF(6, 32), QPointF(24, 32))
    _accent(p, 3)
    p.drawLine(QPointF(24, 32), QPointF(50, 32))
    p.drawLine(QPointF(42, 26), QPointF(50, 32))
    p.drawLine(QPointF(42, 38), QPointF(50, 32))


def _stamp(p):
    p.drawRoundedRect(QRectF(10, 6, 44, 30), 4, 4)
    p.drawRect(QRectF(26, 36, 12, 10))
    p.drawRoundedRect(QRectF(16, 46, 32, 10), 3, 3)
    _accent(p, 3)
    for x in (18, 26, 34, 42):
        p.drawLine(QPointF(x, 14), QPointF(x + 4, 28))


def _envelope(p):
    path = QPainterPath()
    path.moveTo(8, 44)
    path.quadTo(32, 28, 56, 44)
    path.lineTo(56, 22)
    path.quadTo(32, 2, 8, 22)
    path.closeSubpath()
    p.drawPath(path)
    _accent(p, 3)
    for k in range(1, 4):
        x = 8 + 12 * k
        t = (x - 8) / 48
        top = (1 - t) ** 2 * 22 + 2 * (1 - t) * t * 2 + t * t * 22
        bot = (1 - t) ** 2 * 44 + 2 * (1 - t) * t * 28 + t * t * 44
        p.drawLine(QPointF(x, top + 3), QPointF(x, bot - 3))


def _bend_path(p):
    path = QPainterPath()
    path.moveTo(6, 46)
    path.cubicTo(20, 10, 44, 10, 58, 46)
    p.drawPath(path)
    _accent(p, 3)
    for k in range(5):
        t = (k + 0.5) / 5
        u = 1 - t
        x = u ** 3 * 6 + 3 * u * u * t * 20 + 3 * u * t * t * 44 + t ** 3 * 58
        y = u ** 3 * 46 + 3 * u * u * t * 10 + 3 * u * t * t * 10 + t ** 3 * 46
        dx = 3 * u * u * 14 + 6 * u * t * 24 + 3 * t * t * 14
        dy = 3 * u * u * -36 + 3 * t * t * 36
        n = (dx * dx + dy * dy) ** 0.5 or 1.0
        p.drawLine(QPointF(x, y), QPointF(x + dy / n * 11, y - dx / n * 11))


def _shadow(p):
    from PySide6.QtGui import QFont
    _accent(p, 3)
    f = QFont('Arial', 30, QFont.Weight.Black)
    path = QPainterPath()
    path.addText(14, 46, f, 'S')
    for k in range(1, 7):
        p.drawPath(path.translated(k, k))
    p.setPen(QPen(_INK, 2))
    p.setBrush(QColor('white'))
    p.drawPath(path)


def _normalize(p):
    path = QPainterPath()
    path.moveTo(8, 48)
    path.lineTo(56, 16)
    path.lineTo(56, 48)
    path.lineTo(8, 16)
    path.closeSubpath()
    p.drawPath(path)
    _accent(p, 8)
    p.drawPoint(QPointF(32, 32))


def _stroke(p):
    pen = QPen(QColor('#9db4d8'), 14)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawLine(QPointF(14, 48), QPointF(50, 16))
    p.setPen(QPen(_INK, 3))
    p.drawLine(QPointF(14, 48), QPointF(50, 16))


def _fillet(p):
    path = QPainterPath()
    path.moveTo(8, 56)
    path.lineTo(8, 30)
    path.quadTo(8, 8, 30, 8)
    path.lineTo(56, 8)
    p.drawPath(path)


def _chamfer(p):
    p.drawPolyline([QPointF(8, 56), QPointF(8, 26), QPointF(26, 8), QPointF(56, 8)])
    _accent(p, 6)
    p.drawPoint(QPointF(8, 26))
    p.drawPoint(QPointF(26, 8))


def _node_delete(p):
    _node(p)
    _accent(p, 4)
    p.drawLine(QPointF(24, 6), QPointF(40, 26))
    p.drawLine(QPointF(40, 6), QPointF(24, 26))


def _break(p):
    p.drawLine(QPointF(6, 32), QPointF(26, 32))
    p.drawLine(QPointF(38, 32), QPointF(58, 32))
    _accent(p, 3)
    p.drawLine(QPointF(28, 16), QPointF(36, 48))


def _join(p):
    p.drawLine(QPointF(6, 40), QPointF(28, 24))
    p.drawLine(QPointF(36, 24), QPointF(58, 40))
    _accent(p, 3)
    p.drawLine(QPointF(28, 24), QPointF(36, 24))


def _to_curves(p):
    _text(p)
    _accent(p, 2)
    for q in ((14, 52), (32, 10), (50, 52)):
        p.drawRect(QRectF(q[0] - 3, q[1] - 3, 6, 6))


def _magnet(p):
    path = QPainterPath()
    path.moveTo(14, 10); path.lineTo(14, 34)
    path.arcTo(QRectF(14, 18, 36, 36), 180, 180)
    path.lineTo(50, 10)
    p.drawPath(path)
    _accent(p, 6)
    p.drawLine(QPointF(14, 12), QPointF(14, 18)); p.drawLine(QPointF(50, 12), QPointF(50, 18))


def _snap_kind(kind):
    def draw(p):
        p.drawLine(QPointF(8, 50), QPointF(56, 14))
        _accent(p, 3)
        p.setBrush(Qt.BrushStyle.NoBrush)
        if kind == 'node':
            p.drawRect(QRectF(22, 22, 20, 20))
        elif kind == 'middle':
            path = QPainterPath()
            path.moveTo(32, 18); path.lineTo(44, 42); path.lineTo(20, 42); path.closeSubpath()
            p.drawPath(path)
        elif kind == 'center':
            p.drawEllipse(QRectF(21, 21, 22, 22)); p.drawPoint(QPointF(32, 32))
        elif kind == 'perpendicular':
            p.drawLine(QPointF(32, 20), QPointF(32, 44)); p.drawLine(QPointF(32, 44), QPointF(44, 44))
            p.drawLine(QPointF(32, 38), QPointF(38, 38)); p.drawLine(QPointF(38, 38), QPointF(38, 44))
        elif kind == 'parallel':
            p.drawLine(QPointF(14, 40), QPointF(40, 14)); p.drawLine(QPointF(24, 50), QPointF(50, 24))
        elif kind == 'extension':
            p.setPen(QPen(p.pen().color(), 3, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(30, 30), QPointF(56, 14))
        elif kind == 'tangent':
            p.drawEllipse(QRectF(22, 26, 20, 20)); p.drawLine(QPointF(14, 26), QPointF(50, 26))
        elif kind == 'centroid':
            p.drawEllipse(QRectF(21, 21, 22, 22))
            p.drawLine(QPointF(32, 16), QPointF(32, 48)); p.drawLine(QPointF(16, 32), QPointF(48, 32))
        elif kind == 'intersection':
            p.drawLine(QPointF(8, 14), QPointF(56, 50))
            p.drawLine(QPointF(24, 24), QPointF(40, 40)); p.drawLine(QPointF(40, 24), QPointF(24, 40))
        elif kind == 'guide':
            p.setPen(QPen(p.pen().color(), 3, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(32, 6), QPointF(32, 58))
            p.drawEllipse(QRectF(26, 34, 12, 12))
        elif kind == 'nearest':
            path = QPainterPath()
            path.moveTo(22, 22); path.lineTo(42, 22); path.lineTo(22, 42); path.lineTo(42, 42); path.closeSubpath()
            p.drawPath(path)
        else:
            for x in (16, 32, 48):
                for y in (16, 32, 48):
                    p.drawPoint(QPointF(x, y))
            p.drawLine(QPointF(26, 26), QPointF(38, 38)); p.drawLine(QPointF(38, 26), QPointF(26, 38))
    return draw


def _equation_curve(p):
    from PySide6.QtGui import QFont
    p.setFont(QFont('Times New Roman', 24, QFont.Weight.Normal, True))
    p.drawText(QRectF(2, 2, 60, 30), Qt.AlignmentFlag.AlignCenter, 'f(t)')
    _accent(p, 3)
    path = QPainterPath(QPointF(6, 46))
    path.cubicTo(QPointF(18, 22), QPointF(24, 22), QPointF(32, 46))
    path.cubicTo(QPointF(40, 70), QPointF(46, 70), QPointF(58, 46))
    p.drawPath(path)


def _guilloche(p):
    import math as _m
    for k in range(4):
        path = QPainterPath()
        for i in range(121):
            a = i / 120 * _m.tau
            r = 21 + 7 * _m.sin(6 * a + k * _m.pi / 2)
            q = QPointF(32 + r * _m.cos(a), 32 + r * _m.sin(a))
            if i:
                path.lineTo(q)
            else:
                path.moveTo(q)
        if k == 3:
            _accent(p, 2)
        p.drawPath(path)


def _text_letters(p):
    from PySide6.QtGui import QFont
    p.setFont(QFont('Arial', 30, QFont.Weight.Bold))
    p.drawText(QRectF(2, 16, 36, 40), Qt.AlignmentFlag.AlignCenter, 'A')
    _accent(p, 4)
    p.setFont(QFont('Arial', 16, QFont.Weight.Bold))
    p.drawText(QRectF(36, 4, 24, 26), Qt.AlignmentFlag.AlignCenter, '2')


def _spell_check(p):
    from PySide6.QtGui import QFont
    p.setFont(QFont('Arial', 22, QFont.Weight.Bold))
    p.drawText(QRectF(4, 6, 56, 30), Qt.AlignmentFlag.AlignCenter, 'Abc')
    _accent(p, 4)
    path = QPainterPath(QPointF(14, 44))
    path.lineTo(26, 56)
    path.lineTo(50, 34)
    p.drawPath(path)


def _transform_again(p):
    p.drawRect(QRectF(8, 34, 20, 20))
    _accent(p, 3)
    path = QPainterPath(QPointF(18, 26))
    path.cubicTo(QPointF(20, 8), QPointF(42, 8), QPointF(46, 26))
    p.drawPath(path)
    p.drawLine(QPointF(46, 26), QPointF(38, 20))
    p.drawLine(QPointF(46, 26), QPointF(52, 18))


def _transform_again_copy(p):
    p.drawRect(QRectF(6, 34, 20, 20))
    p.setPen(QPen(_INK, 3, Qt.PenStyle.DashLine))
    p.drawRect(QRectF(38, 34, 20, 20))
    _accent(p, 3)
    path = QPainterPath(QPointF(16, 28))
    path.cubicTo(QPointF(20, 8), QPointF(44, 8), QPointF(48, 28))
    p.drawPath(path)
    p.drawLine(QPointF(48, 28), QPointF(40, 22))
    p.drawLine(QPointF(48, 28), QPointF(54, 20))


def _transform_each(p):
    for x, y in ((8, 10), (36, 10), (8, 38), (36, 38)):
        p.drawRect(QRectF(x, y, 16, 16))
    _accent(p, 3)
    for x, y in ((16, 18), (44, 18), (16, 46), (44, 46)):
        p.drawEllipse(QRectF(x - 2, y - 2, 4, 4))


def _duplicate(p):
    p.drawRect(QRectF(8, 30, 20, 20))
    p.setPen(QPen(_INK, 3, Qt.PenStyle.DashLine))
    p.drawRect(QRectF(22, 20, 20, 20))
    _accent(p, 4)
    p.drawRect(QRectF(36, 10, 20, 20))


def _area(p):
    p.setBrush(QColor('#f2c4b3'))
    path = QPainterPath()
    path.moveTo(10, 50); path.lineTo(18, 14); path.lineTo(52, 10); path.lineTo(56, 48); path.closeSubpath()
    p.drawPath(path)
    _accent(p, 3)
    p.drawText(QRectF(10, 14, 46, 36), Qt.AlignmentFlag.AlignCenter, 'm²')


def _options(p):
    p.drawEllipse(QRectF(20, 20, 24, 24))
    for k in range(8):
        a = k * math.pi / 4
        p.drawLine(QPointF(32 + 14 * math.cos(a), 32 + 14 * math.sin(a)),
                   QPointF(32 + 24 * math.cos(a), 32 + 24 * math.sin(a)))
    _accent(p, 5)
    p.drawPoint(QPointF(32, 32))


def _tools(p):
    for i, c in enumerate(('#d0451b', '#2f7d32', '#1f5fbf', '#c09000')):
        p.setBrush(QColor(c))
        p.drawRect(QRectF(10, 8 + i * 12, 12, 9))
        p.drawLine(QPointF(28, 12.5 + i * 12), QPointF(54, 12.5 + i * 12))


def _about(p):
    p.drawEllipse(QRectF(8, 8, 48, 48))
    _accent(p, 6)
    p.drawLine(QPointF(32, 28), QPointF(32, 46))
    p.drawPoint(QPointF(32, 18))


def _update(p):
    path = QPainterPath()
    path.arcMoveTo(QRectF(10, 10, 44, 44), 30)
    path.arcTo(QRectF(10, 10, 44, 44), 30, 300)
    p.drawPath(path)
    _accent(p, 4)
    p.drawLine(QPointF(32, 20), QPointF(32, 42))
    p.drawLine(QPointF(24, 34), QPointF(32, 42)); p.drawLine(QPointF(40, 34), QPointF(32, 42))


def _ruler(p):
    p.save()
    p.translate(32, 32); p.rotate(-35)
    p.drawRect(QRectF(-26, -8, 52, 16))
    for k in range(-20, 24, 6):
        p.drawLine(QPointF(k, -8), QPointF(k, -8 + (8 if k % 12 == 4 else 4)))
    p.restore()


def _barcode(p):
    _accent(p, 2)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_INK)
    x = 8.0
    for w in (3, 1, 2, 1, 4, 1, 1, 3, 2, 1, 3, 1, 2):
        if int(x) % 2 == 0:
            p.drawRect(QRectF(x, 10, w * 1.6, 44))
        x += w * 1.6 + 1.2


def _dedupe(p):
    p.drawRect(QRectF(10, 18, 30, 30))
    p.setPen(QPen(_ACCENT, 3, Qt.PenStyle.DashLine))
    p.drawRect(QRectF(16, 12, 30, 30))
    _accent(p, 5)
    p.drawLine(QPointF(40, 40), QPointF(56, 56)); p.drawLine(QPointF(56, 40), QPointF(40, 56))


def _text_arc(p):
    path = QPainterPath()
    path.arcMoveTo(QRectF(8, 14, 48, 48), 160)
    path.arcTo(QRectF(8, 14, 48, 48), 160, -140)
    p.drawPath(path)
    _accent(p, 3)
    f = p.font(); f.setPixelSize(20); f.setBold(True); p.setFont(f)
    p.drawText(QRectF(8, 2, 48, 30), Qt.AlignmentFlag.AlignCenter, 'abc')


def _save_symbol(p):
    p.drawRect(QRectF(8, 8, 36, 36))
    p.drawEllipse(QRectF(16, 16, 20, 20))
    _accent(p, 4)
    p.drawLine(QPointF(48, 30), QPointF(48, 56)); p.drawLine(QPointF(35, 43), QPointF(61, 43))


def _text_horizontal(p):
    """Texte (TypeEdit : Rapido) : des lettres sur une ligne, la flèche de l'écriture."""
    f = p.font(); f.setPixelSize(30); f.setBold(True); p.setFont(f)
    p.drawText(QRectF(2, 4, 60, 36), Qt.AlignmentFlag.AlignCenter, 'Ab')
    _accent(p, 3)
    p.drawLine(QPointF(10, 50), QPointF(52, 50))
    p.drawLine(QPointF(52, 50), QPointF(45, 44)); p.drawLine(QPointF(52, 50), QPointF(45, 56))


def _text_vertical(p):
    """Texte vertical : les lettres l'une sous l'autre, la flèche vers le bas."""
    f = p.font(); f.setPixelSize(24); f.setBold(True); p.setFont(f)
    p.drawText(QRectF(4, 2, 34, 30), Qt.AlignmentFlag.AlignCenter, 'A')
    p.drawText(QRectF(4, 30, 34, 30), Qt.AlignmentFlag.AlignCenter, 'b')
    _accent(p, 3)
    p.drawLine(QPointF(50, 8), QPointF(50, 54))
    p.drawLine(QPointF(50, 54), QPointF(44, 47)); p.drawLine(QPointF(50, 54), QPointF(56, 47))


def _text_box(p):
    p.setPen(QPen(_INK, 2, Qt.PenStyle.DashLine))
    p.drawRect(QRectF(6, 14, 52, 36))
    _accent(p, 3)
    f = p.font(); f.setPixelSize(22); f.setBold(True); p.setFont(f)
    p.drawText(QRectF(6, 14, 52, 36), Qt.AlignmentFlag.AlignCenter, 'Ab')


def _combine(p):
    p.setBrush(QColor('#c9d6ec'))
    path = QPainterPath()
    path.addRect(QRectF(8, 12, 48, 40))
    path.addEllipse(QRectF(22, 22, 20, 20))
    path.setFillRule(Qt.FillRule.OddEvenFill)
    p.drawPath(path)


def _uncombine(p):
    p.drawRect(QRectF(6, 10, 36, 36))
    _accent(p, 4)
    p.drawEllipse(QRectF(36, 30, 22, 22))


def _nest(p):
    p.drawRect(QRectF(6, 6, 52, 52))
    _accent(p, 3)
    p.drawRect(QRectF(18, 18, 28, 28))
    p.setPen(QPen(_INK, 3))
    p.drawEllipse(QRectF(27, 27, 10, 10))


def _distribute(kind):
    def draw(p):
        horiz = kind in ('h', 'hc')
        for k in range(3):
            if horiz:
                p.drawRect(QRectF(6 + k * 19, 18, 13, 28))
            else:
                p.drawRect(QRectF(18, 6 + k * 19, 28, 13))
        _accent(p, 2)
        if horiz:
            p.drawLine(QPointF(4, 54), QPointF(60, 54))
        else:
            p.drawLine(QPointF(54, 4), QPointF(54, 60))
    return draw


def _braille(p):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_INK)
    for cx, dots in ((14, (0, 1, 3)), (40, (0, 2, 4, 5))):
        for k in dots:
            col, row = (k // 3, k % 3)
            p.drawEllipse(QPointF(cx + col * 12, 14 + row * 17), 4.5, 4.5)


def _halftone(p):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_INK)
    for i in range(6):
        for j in range(6):
            r = 0.6 + 4.2 * (i + j) / 10
            p.drawEllipse(QPointF(7 + i * 10, 7 + j * 10), r, r)


def _guide(p):
    p.drawRect(QRectF(12, 6, 40, 52))
    for k in range(4):
        p.drawLine(QPointF(19, 18 + k * 9), QPointF(45, 18 + k * 9))
    _accent(p, 6)
    p.drawPoint(QPointF(19, 18))


def _dial(p):
    import math as _m
    p.drawArc(QRectF(8, 8, 48, 48), -45 * 16, 270 * 16)
    for k in range(11):
        a = _m.radians(225 - 27 * k)
        r0 = 18 if k % 5 == 0 else 21
        p.drawLine(QPointF(32 + 24 * _m.cos(a), 32 - 24 * _m.sin(a)), QPointF(32 + r0 * _m.cos(a), 32 - r0 * _m.sin(a)))
    _accent(p, 3)
    p.drawLine(QPointF(32, 32), QPointF(44, 20))


def _check(p):
    p.drawRect(QRectF(8, 6, 40, 52))
    for y in (18, 30, 42):
        p.drawLine(QPointF(16, y), QPointF(36, y))
    _accent(p, 4)
    p.drawLine(QPointF(34, 40), QPointF(42, 50))
    p.drawLine(QPointF(42, 50), QPointF(58, 26))


def _nesting(p):
    p.drawRect(QRectF(4, 6, 56, 52))
    _accent(p, 2)
    p.drawRect(QRectF(9, 11, 22, 14))
    p.drawRect(QRectF(34, 11, 21, 24))
    p.drawRect(QRectF(9, 28, 12, 24))
    p.drawRect(QRectF(24, 38, 31, 14))


def _trace(p):
    p.setPen(QPen(_INK, 2, Qt.PenStyle.DotLine))
    p.drawRect(QRectF(6, 6, 52, 52))
    _accent(p, 4)
    path = QPainterPath()
    path.moveTo(16, 46); path.cubicTo(10, 20, 30, 8, 44, 18); path.cubicTo(56, 28, 44, 52, 16, 46)
    p.drawPath(path)


def _chain(p):
    p.drawLine(QPointF(8, 44), QPointF(26, 20))
    p.drawLine(QPointF(38, 20), QPointF(56, 44))
    _accent(p, 4)
    p.drawLine(QPointF(26, 20), QPointF(38, 20))
    p.drawEllipse(QPointF(26, 20), 3, 3)
    p.drawEllipse(QPointF(38, 20), 3, 3)


def _rulers(p):
    p.drawRect(QRectF(6, 6, 52, 12))
    p.drawRect(QRectF(6, 18, 12, 40))
    for x in range(22, 58, 8):
        p.drawLine(QPointF(x, 18), QPointF(x, 12))
    for y in range(26, 58, 8):
        p.drawLine(QPointF(18, y), QPointF(12, y))
    _accent(p, 2)
    p.setPen(QPen(p.pen().color(), 2, Qt.PenStyle.DashLine))
    p.drawLine(QPointF(40, 22), QPointF(40, 58))


def _theme_dark(p):
    """Croissant de lune : mode sombre."""
    path = QPainterPath()
    path.addEllipse(QRectF(10, 10, 44, 44))
    cut = QPainterPath()
    cut.addEllipse(QRectF(24, 4, 40, 40))
    p.setBrush(_INK)
    p.drawPath(path.subtracted(cut))
    _accent(p, 3)
    p.drawPoint(QPointF(50, 44))


def _themes(p):
    """Palette de peintre : thèmes de l'interface."""
    path = QPainterPath()
    path.addEllipse(QRectF(6, 10, 52, 44))
    hole = QPainterPath()
    hole.addEllipse(QRectF(36, 34, 12, 12))
    p.setBrush(QColor('#f4efe4'))
    p.drawPath(path.subtracted(hole))
    p.setPen(Qt.PenStyle.NoPen)
    for (x, y), col in zip(((16, 20), (29, 15), (42, 20), (15, 34)), ('#d0451b', '#f0a500', '#3d6fc4', '#5cb85c')):
        p.setBrush(QColor(col))
        p.drawEllipse(QRectF(x - 5, y - 5, 10, 10))


def _ribbon(p):
    """Ruban réduit : bandeau et flèche."""
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(6, 10, 52, 16), 3, 3)
    p.drawLine(QPointF(14, 18), QPointF(30, 18))
    _accent(p, 4)
    p.drawLine(QPointF(32, 34), QPointF(32, 54))
    p.drawLine(QPointF(24, 46), QPointF(32, 54))
    p.drawLine(QPointF(40, 46), QPointF(32, 54))


def _view_2d(p):
    """Plan à plat : feuille et tracé."""
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(QRectF(8, 14, 48, 36))
    _accent(p, 4)
    p.drawLine(QPointF(16, 40), QPointF(28, 24))
    p.drawLine(QPointF(28, 24), QPointF(40, 36))
    p.drawLine(QPointF(40, 36), QPointF(48, 22))


def _view_3d(p):
    """Pavé en perspective."""
    p.setBrush(QColor('#c9a27a'))
    top = QPainterPath()
    top.moveTo(8, 22)
    top.lineTo(30, 10)
    top.lineTo(56, 18)
    top.lineTo(34, 30)
    top.closeSubpath()
    p.drawPath(top)
    p.setBrush(QColor('#9dd3a8'))
    front = QPainterPath()
    front.moveTo(8, 22)
    front.lineTo(34, 30)
    front.lineTo(34, 54)
    front.lineTo(8, 44)
    front.closeSubpath()
    p.drawPath(front)
    p.setBrush(QColor('#6f86c8'))
    side = QPainterPath()
    side.moveTo(34, 30)
    side.lineTo(56, 18)
    side.lineTo(56, 42)
    side.lineTo(34, 54)
    side.closeSubpath()
    p.drawPath(side)


def _layer_tabs(p):
    """Onglets au-dessus d'une feuille : un calque à la fois."""
    p.drawRect(QRectF(6, 22, 52, 34))
    p.drawLine(QPointF(6, 22), QPointF(6, 10)); p.drawLine(QPointF(6, 10), QPointF(24, 10))
    p.drawLine(QPointF(24, 10), QPointF(24, 22))
    p.drawLine(QPointF(28, 16), QPointF(42, 16)); p.drawLine(QPointF(42, 16), QPointF(42, 22))
    _accent(p, 3)
    p.drawLine(QPointF(14, 34), QPointF(50, 34)); p.drawLine(QPointF(14, 44), QPointF(40, 44))


def _cam(p):
    """Fraise : queue, partie coupante hélicoïdale."""
    p.drawRect(QRectF(24, 4, 16, 22))
    p.drawLine(QPointF(22, 26), QPointF(42, 26))
    _accent(p, 3)
    for y in (30, 38, 46):
        p.drawLine(QPointF(24, y), QPointF(40, y + 6))
    p.drawLine(QPointF(24, 28), QPointF(24, 54)); p.drawLine(QPointF(40, 28), QPointF(40, 54))
    p.drawLine(QPointF(24, 54), QPointF(32, 60)); p.drawLine(QPointF(40, 54), QPointF(32, 60))


def _cam_compute(p):
    """Parcours en aller-retour dans une poche."""
    p.drawRect(QRectF(8, 8, 48, 48))
    _accent(p, 3)
    path = QPainterPath(QPointF(16, 16))
    for k, y in enumerate((16, 26, 36, 46)):
        x0, x1 = (16, 48) if k % 2 == 0 else (48, 16)
        path.lineTo(x0, y); path.lineTo(x1, y)
        if y < 46:
            path.lineTo(x1, y + 10)
    p.drawPath(path)


def _cam_post(p):
    """Programme machine : feuille de lignes G."""
    p.drawRect(QRectF(12, 6, 40, 52))
    f = p.font(); f.setPixelSize(14); f.setBold(True); p.setFont(f)
    p.drawText(QRectF(14, 8, 36, 18), Qt.AlignmentFlag.AlignCenter, 'G1')
    _accent(p, 3)
    for y in (32, 40, 48):
        p.drawLine(QPointF(18, y), QPointF(46, y))


def _cam_import(p):
    """Parcours TypeEdit : flèche vers un trajet."""
    p.drawLine(QPointF(8, 50), QPointF(24, 30)); p.drawLine(QPointF(24, 30), QPointF(40, 44))
    p.drawLine(QPointF(40, 44), QPointF(56, 20))
    _accent(p, 3)
    p.drawLine(QPointF(32, 6), QPointF(32, 24)); p.drawLine(QPointF(26, 18), QPointF(32, 24))
    p.drawLine(QPointF(38, 18), QPointF(32, 24))


def _quote(p):
    """Devis : feuille et symbole euro."""
    p.drawRect(QRectF(12, 6, 40, 52))
    _accent(p, 4)
    path = QPainterPath()
    path.arcMoveTo(QRectF(20, 18, 26, 26), 50)
    path.arcTo(QRectF(20, 18, 26, 26), 50, 260)
    p.drawPath(path)
    p.drawLine(QPointF(16, 28), QPointF(34, 28)); p.drawLine(QPointF(16, 34), QPointF(32, 34))


def _clear_guides(p):
    p.setPen(QPen(_INK, 2, Qt.PenStyle.DashLine))
    p.drawLine(QPointF(8, 24), QPointF(56, 24)); p.drawLine(QPointF(30, 8), QPointF(30, 56))
    _accent(p, 4)
    p.drawLine(QPointF(38, 38), QPointF(56, 56)); p.drawLine(QPointF(56, 38), QPointF(38, 56))


def _engrave_preview(p):
    p.setPen(QPen(QColor(214, 72, 32, 110), 14, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    path = QPainterPath()
    path.moveTo(10, 46); path.cubicTo(20, 6, 40, 6, 54, 40)
    p.drawPath(path)
    p.setPen(QPen(_INK, 2))
    p.drawPath(path)


def _same(kind):
    def draw(p):
        if kind == 'tool':
            for i, c in enumerate(('#d64820', '#d64820', '#3070c0')):
                p.setPen(QPen(QColor(c), 4))
                p.drawEllipse(QRectF(6 + i * 18, 22, 16, 16))
        else:
            p.drawRect(QRectF(6, 20, 16, 16)); p.drawRect(QRectF(26, 20, 16, 16))
            _accent(p, 3)
            p.drawRect(QRectF(46, 20, 12, 22))
    return draw


def _replace_font(p):
    f = p.font()
    f.setPixelSize(30)
    f.setBold(True)
    p.setFont(f)
    p.drawText(QRectF(2, 4, 30, 34), Qt.AlignmentFlag.AlignCenter, 'A')
    _accent(p, 3)
    f.setItalic(True)
    f.setBold(False)
    p.setFont(f)
    p.drawText(QRectF(30, 24, 32, 36), Qt.AlignmentFlag.AlignCenter, 'a')
    p.drawLine(QPointF(20, 46), QPointF(32, 46))
    p.drawLine(QPointF(32, 46), QPointF(27, 41))


def _hatch(p):
    p.drawEllipse(QRectF(8, 8, 48, 48))
    _accent(p, 2)
    import math as _m
    for k in range(-4, 5):
        d = k * 8
        h = _m.sqrt(max(0.0, 24 * 24 - (d / _m.sqrt(2)) ** 2 * 2)) if abs(d) < 34 else 0
        if h <= 0:
            continue
        cx, cy = 32 + d / 2, 32 - d / 2
        p.drawLine(QPointF(cx - h * 0.7, cy - h * 0.7), QPointF(cx + h * 0.7, cy + h * 0.7))


def _holes(p):
    for cx, cy in ((18, 18), (46, 18), (18, 46), (46, 46)):
        p.drawEllipse(QPointF(cx, cy), 9, 9)
    _accent(p, 2)
    for cx, cy in ((18, 18), (46, 18), (18, 46), (46, 46)):
        p.drawLine(QPointF(cx - 5, cy), QPointF(cx + 5, cy))
        p.drawLine(QPointF(cx, cy - 5), QPointF(cx, cy + 5))


def _fill_plate(p):
    p.drawRect(QRectF(4, 8, 56, 48))
    _accent(p, 2)
    for i in range(3):
        for j in range(3):
            p.drawRect(QRectF(9 + i * 17, 13 + j * 14, 12, 9))


def _to_arcs(p):
    path = QPainterPath()
    path.moveTo(6, 50); path.cubicTo(20, 0, 44, 64, 58, 14)
    p.setPen(QPen(_INK, 2, Qt.PenStyle.DashLine))
    p.drawPath(path)
    _accent(p, 4)
    p.drawArc(QRectF(6, 22, 26, 56), 0, 180 * 16)
    p.drawArc(QRectF(32, -14, 26, 56), 180 * 16, 180 * 16)


def _clip(p):
    p.setPen(QPen(_INK, 2, Qt.PenStyle.DashLine))
    p.drawEllipse(QRectF(26, 4, 36, 36))
    p.setPen(QPen(_INK, 4))
    p.drawRect(QRectF(6, 20, 40, 38))
    _accent(p, 4)
    path = QPainterPath()
    path.arcMoveTo(QRectF(26, 4, 36, 36), 180)
    path.arcTo(QRectF(26, 4, 36, 36), 180, 93)
    p.drawPath(path)


def _order(kind):
    def draw(p):
        top = kind in ('front', 'forward')
        p.setBrush(QColor('#ffffff'))
        back, front = QRectF(8, 8, 30, 30), QRectF(26, 26, 30, 30)
        if top:
            p.drawRect(back)
            p.setBrush(QColor('#f2c4b3'))
            p.drawRect(front)
        else:
            p.setBrush(QColor('#f2c4b3'))
            p.drawRect(front)
            p.setBrush(QColor('#ffffff'))
            p.drawRect(back)
        if kind in ('forward', 'backward'):
            _accent(p, 3)
            y0, y1 = (58, 46) if kind == 'forward' else (46, 58)
            p.drawLine(QPointF(8, y0), QPointF(8, y1))
    return draw


def _freeze(kind):
    def draw(p):
        p.drawRect(QRectF(14, 28, 36, 28))
        path = QPainterPath()
        path.moveTo(22, 28)
        path.lineTo(22, 18)
        path.arcTo(QRectF(22, 6, 20, 24), 180, -180)
        if kind == 'freeze':
            path.lineTo(42, 28)
        else:
            path.lineTo(42, 22)
        p.drawPath(path)
    return draw


def _eye(kind):
    def draw(p):
        path = QPainterPath()
        path.moveTo(6, 32); path.quadTo(32, 6, 58, 32); path.quadTo(32, 58, 6, 32)
        p.drawPath(path)
        p.drawEllipse(QPointF(32, 32), 7, 7)
        if kind == 'hide':
            _accent(p, 4)
            p.drawLine(QPointF(10, 54), QPointF(54, 10))
    return draw


def _print(p):
    p.drawRect(QRectF(16, 6, 32, 18))
    p.setBrush(QColor('#dfe6f2'))
    p.drawRect(QRectF(6, 24, 52, 22))
    p.setBrush(QColor('#ffffff'))
    p.drawRect(QRectF(16, 38, 32, 20))
    _accent(p, 2)
    p.drawLine(QPointF(21, 46), QPointF(43, 46)); p.drawLine(QPointF(21, 52), QPointF(37, 52))


ICONS = {
    'theme_dark': _theme_dark, 'themes': _themes, 'ribbon': _ribbon, 'layer_tabs': _layer_tabs, 'quit': _quit,
    'view_2d': _view_2d, 'view_3d': _view_3d, 'view_yz': _view_plane('yz'), 'view_zx': _view_plane('zx'),
    'axis_v': _axis_align('v'), 'axis_h': _axis_align('h'),
    'align_center': _align_center, 'contour_move': _contour_move,
    'node_project_v': _node_project('v'), 'node_project_h': _node_project('h'),
    'node_project_perp': _node_project('perp'),
    'node_refine': _node_refine, 'node_segment': _node_portion('segment'), 'node_angle': _node_portion('angle'), 'cam': _cam, 'cam_compute': _cam_compute,
    'cam_post': _cam_post, 'cam_import': _cam_import, 'quote': _quote,
    'polyline': _polyline, 'bezier': _bezier, 'star': _star, 'spiral': _spiral, 'arc': _arc, 'approximate': _approximate, 'segment': _segment, 'text': _text,
    'node': _node, 'union': _bool('union'), 'intersect': _bool('intersect'),
    'difference': _bool('difference'), 'xor': _bool('xor'), 'offset': _offset, 'shadow': _shadow, 'envelope': _envelope, 'bend_path': _bend_path, 'stamp': _stamp, 'trim': _trim, 'punch': _punch, 'double_line': _double_line, 'dashes': _dashes, 'tan_circle': _tan_circle, 'text_path': _text_path, 'measure_radius': _measure_radius,
    'fill_toggle': _fill_toggle, 'measure_angle': _measure_angle, 'text_merge': _text_merge, 'xline': _xline, 'center_line': _center_line, 'dim_arc': _dim_arc, 'fx_scallop': _fx_scallop, 'match_props': _match_props, 'compare': _compare,
    'sym_ox': _sym_ox, 'sym_oy': _sym_oy, 'sym_both': _sym_both, 'sym_origin': _sym_origin, 'compare_next': _compare_next, 'compare_prev': _compare_prev, 'compare_close': _compare_close, 'marker': _marker, 'command_search': _command_search, 'news': _news, 'explode': _explode, 'remove_contours': _remove_contours, 'sym_draw': _sym_draw, 'bbox_frame': _bbox_frame, 'blend': _blend, 'blend_curve': _blend_curve, 'gdt': _gdt, 'dim_inspect': _dim_inspect, 'dim_space': _dim_space, 'dim_jogged': _dim_jogged,
    'dim_jog_line': _dim_jog_line, 'coil': _coil, 'thread': _thread, 'hole3d': _hole3d, 'pipe': _pipe, 'rib': _rib, 'boss': _boss, 'wrap_emboss': _wrap_emboss, 'frame': _frame, 'lip': _lip, 'snap_fit': _snap_fit, 'rest_pad': _rest_pad, 'bent_sheet': _bent_sheet, 'sheet_tray': _sheet_tray, 'sheet_fold': _sheet_fold, 'oops': _oops, 'change_point': _change_point, 'arc_center': _arc_center, 'circle2': _circle2, 'polygon_edge': _polygon_edge, 'ellipse_axis': _ellipse_axis, 'rect3': _rect3, 'draft_analysis': _draft_analysis, 'perforate': _perforate, 'scale3d': _scale3d, 'cells': _cells,
    'bounding': _bounding, 'mirror_axis': _mirror_axis, 'text_columns': _text_columns, **{k: _node_icon(k) for k in ('node_line', 'node_curve', 'node_smooth', 'node_symmetric', 'node_align_h', 'node_align_v')}, 'same_w': _same_size('w'), 'same_h': _same_size('h'), 'same_both': _same_size('both'), 'remove_loops': _remove_loops, 'extend': _extend,
    'normalize': _normalize, 'stroke': _stroke, 'fillet': _fillet, 'chamfer': _chamfer,
    'node_delete': _node_delete, 'break': _break, 'join': _join, 'to_curves': _to_curves,
    'select': _arrow, 'rect': _rect, 'ellipse': _ellipse, 'line': _line, 'polygon': _polygon,
    'open': _open, 'save': _save, 'new': _new, 'import': _import, 'export': _export,
    'undo': _undo, 'redo': _redo, 'zoom_fit': _zoom_fit, 'zoom_in': _zoom_in, 'zoom_out': _zoom_out,
    'mirror_h': _mirror_h, 'mirror_v': _mirror_v, 'rotate': _rotate,
    'align_left': _align('left'), 'align_right': _align('right'), 'align_hcenter': _align('hcenter'),
    'align_top': _align('top'), 'align_bottom': _align('bottom'), 'align_vcenter': _align('vcenter'),
    'center_plate': _center_plate, 'group': _group, 'ungroup': _ungroup, 'delete': _delete,
    'measure': _measure, 'plate': _plate, 'grid': _grid, 'direction': _direction, 'fill': _fill,
    'copy': _copy, 'paste': _paste, 'cut': _cut, 'select_all': _select_all, 'invert': _invert, 'select_filter': _select_filter, 'marquetry': _marquetry, 'leds': _leds, 'cut_pattern': _cut_pattern, 'texture': _texture, 'char_map': _char_map, 'font_recognize': _font_recognize, 'text_arcs': _text_arcs, 'lasso': _lasso, 'selection_modes': _selection_modes, 'variables': _variables, 'insert_variable': _insert_variable, 'variables_produce': _variables_produce, 'duplicate_scaled': _duplicate_scaled,
    'pdf': _pdf, 'snap': _magnet, 'snap_node': _snap_kind('node'), 'snap_middle': _snap_kind('middle'),
    'snap_center': _snap_kind('center'), 'snap_grid': _snap_kind('grid'), 'snap_centroid': _snap_kind('centroid'),
    'snap_perpendicular': _snap_kind('perpendicular'), 'snap_tangent': _snap_kind('tangent'),
    'snap_extension': _snap_kind('extension'), 'snap_parallel': _snap_kind('parallel'),
    'snap_intersection': _snap_kind('intersection'), 'snap_nearest': _snap_kind('nearest'),
    'snap_guide': _snap_kind('guide'), 'duplicate': _duplicate,
    'spell_check': _spell_check, 'text_letters': _text_letters,
    'equation_curve': _equation_curve, 'guilloche': _guilloche,
    'transform_again': _transform_again, 'transform_again_copy': _transform_again_copy,
    'transform_each': _transform_each,
    'area': _area, 'options': _options, 'tools': _tools, 'about': _about, 'update': _update,
    'ruler': _ruler, 'barcode': _barcode, 'dedupe': _dedupe, 'text_arc': _text_arc, 'save_symbol': _save_symbol, 'text_box': _text_box, 'text_horizontal': _text_horizontal,
    'text_vertical': _text_vertical,
    'combine': _combine, 'uncombine': _uncombine, 'nest': _nest, 'distribute_h': _distribute('h'),
    'distribute_v': _distribute('v'), 'distribute_hc': _distribute('hc'), 'distribute_vc': _distribute('vc'),
    'braille': _braille, 'halftone': _halftone, 'guide': _guide, 'dial': _dial, 'holes': _holes, 'hatch': _hatch, 'replace_font': _replace_font, 'engrave_preview': _engrave_preview,
    'select_same_tool': _same('tool'), 'select_same_shape': _same('shape'), 'rulers': _rulers, 'clear_guides': _clear_guides, 'chain': _chain, 'trace': _trace, 'nesting': _nesting, 'check': _check, 'fill_plate': _fill_plate, 'to_arcs': _to_arcs, 'clip': _clip,
    'order_front': _order('front'), 'order_back': _order('back'), 'order_forward': _order('forward'),
    'order_backward': _order('backward'), 'freeze': _freeze('freeze'), 'unfreeze': _freeze('unfreeze'),
    'hide': _eye('hide'), 'show_all': _eye('show'), 'print': _print,
}

def _wrap_cylinder(p):
    p.drawEllipse(QRectF(6, 14, 12, 36))                     # bout de la pièce couchée
    p.drawLine(QPointF(12, 14), QPointF(52, 14))
    p.drawLine(QPointF(12, 50), QPointF(52, 50))
    p.drawArc(QRectF(46, 14, 12, 36), -90 * 16, 180 * 16)
    _accent(p, 3)
    for x in (26, 36, 46):                                   # tracé enroulé
        path = QPainterPath()
        path.moveTo(x - 4, 20)
        path.quadTo(x + 3, 32, x - 4, 44)
        p.drawPath(path)


def _wrap_cone(p):
    p.drawEllipse(QRectF(6, 22, 8, 20))
    p.drawLine(QPointF(10, 22), QPointF(52, 10))
    p.drawLine(QPointF(10, 42), QPointF(52, 54))
    p.drawArc(QRectF(46, 10, 12, 44), -90 * 16, 180 * 16)
    _accent(p, 3)
    for x, h in ((26, 9), (36, 13), (46, 17)):
        path = QPainterPath()
        path.moveTo(x - 4, 32 - h)
        path.quadTo(x + 3, 32, x - 4, 32 + h)
        p.drawPath(path)


def _align_justify(p):
    for y in (12, 24, 36, 48):                               # lignes de même largeur
        p.drawLine(QPointF(10, y), QPointF(54, y))
    _accent(p)
    p.drawLine(QPointF(6, 6), QPointF(6, 54))
    p.drawLine(QPointF(58, 6), QPointF(58, 54))


def _text_spring(p):
    """Ressort du texte : entre les bords de la ligne, un ressort qui pousse."""
    p.drawLine(QPointF(6, 14), QPointF(6, 50))
    p.drawLine(QPointF(58, 14), QPointF(58, 50))
    _accent(p, 4)
    p.drawPolyline([QPointF(6, 32), QPointF(14, 32), QPointF(18, 22), QPointF(24, 42), QPointF(30, 22),
                    QPointF(36, 42), QPointF(42, 22), QPointF(46, 32), QPointF(58, 32)])


ICONS.update({'wrap_cylinder': _wrap_cylinder, 'wrap_cone': _wrap_cone, 'align_justify': _align_justify,
              'text_spring': _text_spring})

_cache: dict[str, QIcon] = {}


def _origin(p):
    """Origine du dessin : axes X et Y fléchés."""
    p.drawLine(QPointF(14, 50), QPointF(56, 50))
    p.drawLine(QPointF(14, 50), QPointF(14, 8))
    p.drawLine(QPointF(56, 50), QPointF(48, 44))
    p.drawLine(QPointF(56, 50), QPointF(48, 56))
    p.drawLine(QPointF(14, 8), QPointF(8, 16))
    p.drawLine(QPointF(14, 8), QPointF(20, 16))
    _accent(p, 4)
    p.drawEllipse(QPointF(14, 50), 5, 5)


ICONS['origin'] = _origin


def _shape_script(p):
    """Script de forme : une page de lignes qui dessine."""
    p.drawRoundedRect(QRectF(8, 6, 34, 52), 4, 4)
    for y in (18, 28, 38):
        p.drawLine(QPointF(15, y), QPointF(35, y))
    _accent(p, 4)
    p.drawEllipse(QPointF(46, 40), 11, 11)


ICONS['shape_script'] = _shape_script


def icon(name: str) -> QIcon:
    key = (name,) + _inks()
    if key not in _cache:
        _cache[key] = _icon(ICONS.get(name, _new))
    return _cache[key]


def _clock(p):
    """Compteur : cadran et aiguilles."""
    p.drawEllipse(QPointF(32, 34), 22, 22)
    p.drawLine(QPointF(26, 6), QPointF(38, 6))
    p.drawLine(QPointF(32, 6), QPointF(32, 12))
    _accent(p, 4)
    p.drawLine(QPointF(32, 34), QPointF(32, 20))
    p.drawLine(QPointF(32, 34), QPointF(42, 40))


ICONS['clock'] = _clock


# --- commandes du formulaire de Mise en forme (round 926) : une icône chacune ---------------------------------------
def _letters(p, s, size=32, rect=(2, 6, 60, 46)):
    """Lettres au trait (police monotrait intégrée VD Géo), centrées dans `rect`, capitales de 0,68 × `size` px : sans
    police du système (le rendu hors écran n'en a pas), du même trait que les autres icônes."""
    from PySide6.QtGui import QTransform
    from ..core import text as TX
    from .canvas import to_qpath
    try:
        path = TX.layout(s, 'VD Géo', 1.0)
        x0, y0, x1, y1 = path.bbox()
    except Exception:                                    # police intégrée illisible : l'icône sans ses lettres
        return
    cap = size * 0.68
    x, y, w, h = rect
    t = QTransform(cap, 0, 0, -cap, x + (w - (x1 - x0) * cap) / 2 - x0 * cap, y + h / 2 + cap * (y0 + y1) / 2)
    brush = p.brush()
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(t.map(to_qpath(path)))
    p.setBrush(brush)


def _case_upper(p):
    """MAJUSCULES."""
    _letters(p, 'AB')


def _case_lower(p):
    """minuscules."""
    _letters(p, 'ab')


def _case_words(p):
    """Majuscule Aux Mots : la capitale soulignée."""
    _letters(p, 'Ab')
    _accent(p, 4)
    p.drawLine(QPointF(12, 56), QPointF(30, 56))


def _case_small(p):
    """Petites majuscules : une capitale, une petite capitale."""
    _letters(p, 'A', 40, (0, 6, 36, 48))
    _letters(p, 'A', 24, (32, 20, 30, 34))
    _accent(p, 3)
    p.drawLine(QPointF(4, 56), QPointF(60, 56))


def _case_initial(p):
    """Casse initiale : « Aa » et la flèche du retour."""
    _letters(p, 'Aa', 28, (2, 0, 60, 36))
    _accent(p, 4)
    p.drawArc(QRectF(16, 30, 32, 24), 0, -180 * 16)
    p.drawLine(QPointF(16, 42), QPointF(10, 34))
    p.drawLine(QPointF(16, 42), QPointF(23, 35))


def _text_rtl(p):
    """De droite à gauche : la lettre, la flèche vers la gauche."""
    _letters(p, 'A', 30, (24, 2, 36, 36))
    _accent(p, 4)
    p.drawLine(QPointF(58, 50), QPointF(8, 50))
    p.drawLine(QPointF(8, 50), QPointF(18, 42))
    p.drawLine(QPointF(8, 50), QPointF(18, 58))


def _text_on_baseline(p):
    """Sur la ligne de base : la lettre posée sur la ligne."""
    _letters(p, 'A', 40, (4, 2, 56, 46))
    _accent(p, 4)
    p.drawLine(QPointF(4, 50), QPointF(60, 50))


def _text_under_baseline(p):
    """Sous la ligne de base : la ligne au haut des capitales."""
    _accent(p, 4)
    p.drawLine(QPointF(4, 12), QPointF(60, 12))
    p.setPen(QPen(_INK, 4))
    _letters(p, 'A', 40, (4, 16, 56, 46))


def _lines(p, x0=24):
    for y in (14, 32, 50):
        p.drawLine(QPointF(x0, y), QPointF(58, y))


def _line_fixed(p):
    """Interligne fixe : trois lignes, deux écarts égaux cotés."""
    _lines(p)
    _accent(p, 3)
    p.drawLine(QPointF(10, 14), QPointF(10, 50))
    for y in (14, 32, 50):
        p.drawLine(QPointF(5, y), QPointF(15, y))


def _line_prop(p):
    """Interligne proportionnel : trois lignes et le pour-cent."""
    _lines(p)
    p.setPen(QPen(_ACCENT, 4))
    _letters(p, '%', 34, (0, 14, 24, 36))


def _line_typo(p):
    """Interligne typographique : « Ag », jambages compris entre les deux lignes."""
    _letters(p, 'Ag', 34, (2, 6, 60, 46))
    _accent(p, 3)
    p.drawLine(QPointF(4, 8), QPointF(60, 8))
    p.drawLine(QPointF(4, 58), QPointF(60, 58))


def _squeeze(p, y):
    p.drawLine(QPointF(2, y), QPointF(13, y))
    p.drawLine(QPointF(13, y), QPointF(8, y - 5))
    p.drawLine(QPointF(13, y), QPointF(8, y + 5))
    p.drawLine(QPointF(62, y), QPointF(51, y))
    p.drawLine(QPointF(51, y), QPointF(56, y - 5))
    p.drawLine(QPointF(51, y), QPointF(56, y + 5))


def _text_compress_line(p):
    """Compression ligne : une ligne serrée par les deux bouts."""
    p.setPen(QPen(_INK, 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(20, 32), QPointF(44, 32))
    _accent(p, 4)
    _squeeze(p, 32)


def _text_compress_para(p):
    """Compression paragraphe : toutes les lignes serrées ensemble."""
    p.setPen(QPen(_INK, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    for y, x1 in ((16, 44), (32, 40), (48, 44)):
        p.drawLine(QPointF(20, y), QPointF(x1, y))
    _accent(p, 4)
    _squeeze(p, 32)


def _text_compress_global(p):
    """Compression globale : les lignes à un pourcentage de la plus longue."""
    p.setPen(QPen(_INK, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    for y, x1 in ((16, 40), (32, 30), (48, 36)):
        p.drawLine(QPointF(6, y), QPointF(x1, y))
    p.setPen(QPen(_ACCENT, 4))
    _letters(p, '%', 34, (38, 14, 26, 36))


def _find_replace(p):
    """Rechercher / remplacer : la loupe sur une lettre."""
    p.drawEllipse(QRectF(6, 6, 34, 34))
    _letters(p, 'A', 22, (6, 6, 34, 34))
    _accent(p, 6)
    p.drawLine(QPointF(36, 36), QPointF(56, 56))


def _text_copy_format(p):
    """Reproduire la mise en forme : le pinceau."""
    p.drawRoundedRect(QRectF(10, 6, 40, 18), 4, 4)
    p.drawLine(QPointF(50, 15), QPointF(56, 15))
    p.drawLine(QPointF(56, 15), QPointF(56, 30))
    p.drawLine(QPointF(56, 30), QPointF(32, 30))
    _accent(p, 8)
    p.drawLine(QPointF(32, 30), QPointF(32, 56))


def _text_styles(p):
    """Préréglages de texte : des fiches empilées, la lettre devant."""
    p.drawRect(QRectF(22, 4, 36, 30))
    p.drawRect(QRectF(14, 12, 36, 30))
    p.setBrush(QColor('#ffffff'))
    _accent(p, 4)
    p.drawRect(QRectF(6, 22, 36, 34))
    p.setPen(QPen(_INK, 4))
    _letters(p, 'A', 24, (6, 22, 36, 34))


def _text_preset_save(p):
    """Enregistrer le préréglage : la disquette, la lettre sur l'étiquette."""
    _save(p)
    p.setPen(QPen(_ACCENT, 4))
    _letters(p, 'A', 18, (18, 34, 28, 20))


ICONS.update({'case_upper': _case_upper, 'case_lower': _case_lower, 'case_words': _case_words,
              'case_small': _case_small, 'case_initial': _case_initial, 'text_rtl': _text_rtl,
              'text_on_baseline': _text_on_baseline, 'text_under_baseline': _text_under_baseline,
              'line_fixed': _line_fixed, 'line_prop': _line_prop, 'line_typo': _line_typo,
              'text_compress_line': _text_compress_line, 'text_compress_para': _text_compress_para,
              'text_compress_global': _text_compress_global, 'find_replace': _find_replace,
              'text_copy_format': _text_copy_format, 'text_styles': _text_styles,
              'text_preset_save': _text_preset_save})


# --- onglets des panneaux d'une colonne (demande du 15/11, 22 h 30) -------------------------------------------------
def _tab_dims(p):
    """Dimensions (F2) : une cote entre deux traits d'attache."""
    p.drawLine(QPointF(12, 12), QPointF(12, 52))
    p.drawLine(QPointF(52, 12), QPointF(52, 52))
    _accent(p, 4)
    p.drawLine(QPointF(16, 32), QPointF(48, 32))
    for x, dx in ((16, 8), (48, -8)):
        p.drawLine(QPointF(x, 32), QPointF(x + dx, 25))
        p.drawLine(QPointF(x, 32), QPointF(x + dx, 39))


def _tab_layers(p):
    """Calques : trois feuilles empilées, celle du dessus en couleur."""
    for y in (46, 36):
        p.drawLine(QPointF(8, y), QPointF(32, y + 11))
        p.drawLine(QPointF(32, y + 11), QPointF(56, y))
    _accent(p, 4)
    path = QPainterPath()
    path.moveTo(32, 9); path.lineTo(56, 22); path.lineTo(32, 35); path.lineTo(8, 22)
    path.closeSubpath()
    p.drawPath(path)


def _tab_library(p):
    """Bibliothèque : quatre cases, une en couleur."""
    for x, y in ((9, 9), (36, 9), (9, 36)):
        p.drawRect(QRectF(x, y, 19, 19))
    _accent(p, 4)
    p.drawRect(QRectF(36, 36, 19, 19))


def _tab_paths(p):
    """FAO, les parcours à créer : une fraise au-dessus de son trait."""
    p.drawRect(QRectF(24, 6, 16, 24))
    p.drawLine(QPointF(24, 30), QPointF(32, 41))
    p.drawLine(QPointF(40, 30), QPointF(32, 41))
    _accent(p, 4)
    p.drawLine(QPointF(8, 54), QPointF(56, 54))


def _tab_ops(p):
    """FAO, les opérations : une liste et ses puces."""
    for y in (16, 32, 48):
        p.drawLine(QPointF(24, y), QPointF(54, y))
    _accent(p, 8)
    for y in (16, 32, 48):
        p.drawPoint(QPointF(12, y))


def _tab_program(p):
    """Programme machine : des lignes de code, en retrait."""
    p.drawLine(QPointF(10, 14), QPointF(38, 14))
    p.drawLine(QPointF(20, 26), QPointF(54, 26))
    p.drawLine(QPointF(20, 38), QPointF(46, 38))
    _accent(p, 4)
    p.drawLine(QPointF(10, 50), QPointF(34, 50))


def _tab_fonts(p):
    """Reconnaître une police : un A."""
    p.drawLine(QPointF(14, 52), QPointF(32, 10))
    p.drawLine(QPointF(32, 10), QPointF(50, 52))
    _accent(p, 4)
    p.drawLine(QPointF(22, 38), QPointF(42, 38))


def _assistant(p):
    """Assistant IA : une bulle de discussion, une étincelle dedans."""
    path = QPainterPath()
    path.addRoundedRect(QRectF(6, 8, 52, 36), 10, 10)
    p.drawPath(path)
    p.drawLine(QPointF(18, 44), QPointF(14, 56))
    p.drawLine(QPointF(14, 56), QPointF(28, 44))
    _accent(p, 4)
    p.drawLine(QPointF(32, 16), QPointF(32, 36))
    p.drawLine(QPointF(22, 26), QPointF(42, 26))
    p.drawLine(QPointF(25, 19), QPointF(39, 33))
    p.drawLine(QPointF(39, 19), QPointF(25, 33))


def _tab_panel(p):
    """Un panneau sans icône à lui (celui d'un plugin) : une fenêtre et sa barre."""
    p.drawRect(QRectF(10, 12, 44, 40))
    _accent(p, 4)
    p.drawLine(QPointF(10, 24), QPointF(54, 24))


ICONS.update({'tab_dims': _tab_dims, 'tab_layers': _tab_layers, 'tab_library': _tab_library,
              'tab_paths': _tab_paths, 'tab_ops': _tab_ops, 'tab_program': _tab_program, 'tab_fonts': _tab_fonts,
              'tab_panel': _tab_panel, 'assistant_ia': _assistant, 'tab_assistant': _assistant})
