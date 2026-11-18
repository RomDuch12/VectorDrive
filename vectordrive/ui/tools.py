"""Outils interactifs du plan de travail (création et Mode Point).

Chaque outil reçoit les événements du `Canvas` (positions écran et
document) et dessine son aperçu par-dessus. Ils ne touchent au document
qu'en fin de geste, par `canvas.commit_shape` ou, pour le Mode Point, en
modifiant le tracé de l'objet édité après `canvas.undo_push()`.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF

from ..core import geom, nodes
from ..core.document import Shape, Text
from ..core.geom import Contour, Cubic, Line, Path

SNAP_PX = 7


def _cc(role: str) -> str:
    from .theme import canvas_colors
    return canvas_colors()[role]


def _pen(color=None, w=1, style=Qt.PenStyle.SolidLine) -> QPen:
    p = QPen(QColor(color or _cc('preview')), w, style)
    p.setCosmetic(True)
    return p


class Tool:
    cursor = Qt.CursorShape.CrossCursor

    def __init__(self, canvas):
        self.c = canvas

    def press(self, sp: QPointF, dp, ev) -> None: ...
    def move(self, sp: QPointF, dp, ev) -> None: ...
    def release(self, sp: QPointF, dp, ev) -> None: ...
    def double(self, sp: QPointF, dp, ev) -> None: ...
    def key(self, ev) -> bool: return False
    def wants_key(self, ev) -> bool: return False       # la touche passe avant les raccourcis
    def paint(self, p: QPainter) -> None: ...
    def cancel(self) -> None: ...
    def points(self) -> list | None: return None        # F2 : les points du tracé en cours, si l'outil en a
    def set_points(self, pts: list) -> None: ...
    def end_points(self) -> None: ...

    def preview(self, p: QPainter, path: Path | None, color=None) -> None:
        if not path:
            return
        from .canvas import to_qpath
        p.save()
        p.setTransform(self.c.view())
        p.setPen(_pen(color))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(to_qpath(path))
        p.restore()


def _ctrl(ev) -> bool:
    return ev is not None and bool(ev.modifiers() & Qt.KeyboardModifier.ControlModifier)


def _shift(ev) -> bool:
    return ev is not None and bool(ev.modifiers() & Qt.KeyboardModifier.ShiftModifier)


def _snap45(a, b):
    w, h = b[0] - a[0], b[1] - a[1]
    ang = round(math.atan2(h, w) / (math.pi / 4)) * (math.pi / 4)
    L = math.hypot(w, h)
    return (a[0] + L * math.cos(ang), a[1] + L * math.sin(ang))


# --- formes par glissé -----------------------------------------------------------

class RadialTool(Tool):
    """Polygone, étoile ou spirale : du centre vers un sommet ou vers le bout
    extérieur de la spirale (Ctrl : en haut ; Maj : spirale en sens horaire ;
    polygone et étoile, deux points opposés comme dans TypeEdit ; Alt : polygone
    circonscrit — le pointeur au milieu d'un côté)."""

    def __init__(self, canvas, kind: str):
        super().__init__(canvas)
        self.kind = kind
        self.a = self.b = None

    def press(self, sp, dp, ev):
        self.a = self.b = dp

    def move(self, sp, dp, ev):
        if self.a is not None:
            self.b = dp
            self.ctrl = _ctrl(ev)
            self.shift = bool(ev.modifiers() & Qt.KeyboardModifier.ShiftModifier) if ev is not None else False
            self.alt = bool(ev.modifiers() & Qt.KeyboardModifier.AltModifier) if ev is not None else False
            self.c.overlay_update()

    def spec(self):
        """Forme paramétrée (core.forms) du tracé en cours : réglages de
        l'outil, centre et taille à la souris."""
        if self.a is None or self.b is None:
            return None
        centre = self.a
        if getattr(self, 'shift', False) and self.kind != 'spiral':
            centre = ((self.a[0] + self.b[0]) / 2, (self.a[1] + self.b[1]) / 2)    # deux points opposés
        r = geom.dist(centre, self.b)
        if r < 1e-6:
            return None
        ang = 90.0 if getattr(self, 'ctrl', False) else math.degrees(
            math.atan2(self.b[1] - centre[1], self.b[0] - centre[0]))
        n = max(3, int(self.c.poly_sides))
        s = self.c.form_default(self.kind)
        s.cx, s.cy, s.angle = centre[0], centre[1], ang
        if self.kind == 'spiral':
            ratio = (s.r_in / s.r_out) if s.r_out > 0 else 0.0
            s.r_out, s.r_in, s.turns = r, r * ratio, self.c.spiral_turns
            s.clockwise = getattr(self, 'shift', False)
        elif self.kind == 'star':
            ratio = (s.r_in / s.r_out) if s.r_out > 0 else self.c.star_ratio
            s.branches, s.r_out, s.r_in = n, r, r * ratio
        else:
            side = getattr(self, 'alt', False)            # circonscrit : le pointeur au milieu d'un côté
            s.sides, s.size, s.size_mode = n, r, ('cote' if side else 'sommet')
            if side:
                s.angle += 180.0 / n
        return s

    def _path(self):
        s = self.spec()
        return s.build() if s is not None else None

    def release(self, sp, dp, ev):
        self.b = dp
        s = self.spec()
        self.a = self.b = None
        if s is not None:
            self.c.commit_form(s)

    def paint(self, p):
        self.preview(p, self._path())

    def cancel(self):
        self.a = self.b = None


# --- formes point par point ------------------------------------------------------

class LassoTool(Tool):
    """Sélection au lasso (TypeEdit) : clics = sommets d'un lasso
    polygonal ; glisser = lasso à main levée. Double-clic, Entrée ou fin du
    glissé : les objets que le lasso touche sont pris, selon l'opérateur de
    sélection en cours (et le filtre F9) ; Ctrl : ajouter ou retirer."""
    cursor = Qt.CursorShape.CrossCursor

    def __init__(self, canvas):
        super().__init__(canvas)
        self.pts: list = []
        self.hover = None
        self.free = False
        self._down = None

    def press(self, sp, dp, ev):
        self._down = (sp, _ctrl(ev))
        if not self.pts or geom.dist(self.pts[-1], dp) > 1e-9:
            self.pts.append(dp)
        self.c.overlay_update()

    def move(self, sp, dp, ev):
        held = bool(ev.buttons() & Qt.MouseButton.LeftButton)
        if held and self._down is not None:
            s0 = self._down[0]
            if self.free or math.hypot(sp.x() - s0.x(), sp.y() - s0.y()) > 4:
                self.free = True
                a = self.c.to_screen(*self.pts[-1])
                if math.hypot(a.x() - sp.x(), a.y() - sp.y()) > 2:
                    self.pts.append(dp)
        self.hover = dp
        self.c.overlay_update()

    def release(self, sp, dp, ev):
        if self.free:
            self._finish(self._down[1] if self._down else False)
        self._down = None

    def double(self, sp, dp, ev):
        self._finish(_ctrl(ev))

    def key(self, ev):
        if ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._finish(False)
            return True
        if ev.key() == Qt.Key.Key_Backspace and self.pts:
            self.pts.pop()
            self.c.overlay_update()
            return True
        return False

    def _finish(self, ctrl: bool) -> None:
        pts, self.pts, self.hover, self.free = self.pts, [], None, False
        if len(pts) >= 3:
            self.c.apply_pick(self.c.lasso_items(pts), ctrl=ctrl)
        self.c.overlay_update()

    def paint(self, p):
        pts = self.pts + ([self.hover] if self.hover and self.pts and not self.free else [])
        if len(pts) >= 2:
            self.preview(p, Path([geom.polyline(pts, closed=len(pts) > 2)]))

    def cancel(self):
        self.pts, self.hover, self.free, self._down = [], None, False, None


class PolylineTool(Tool):
    """Clic = sommet ; double-clic ou Entrée = fin ; clic sur le premier
    sommet = contour fermé ; Ctrl = angles multiples de 45°."""

    def __init__(self, canvas):
        super().__init__(canvas)
        self.pts: list = []
        self.hover = None

    def _snap_first(self, dp):
        if len(self.pts) >= 3:
            a = self.c.to_screen(*self.pts[0])
            b = self.c.to_screen(*dp)
            if math.hypot(a.x() - b.x(), a.y() - b.y()) < SNAP_PX:
                return True
        return False

    def press(self, sp, dp, ev):
        if self.pts and _ctrl(ev):
            dp = _snap45(self.pts[-1], dp)
        if self._snap_first(dp):
            self._finish(closed=True)
            return
        if not self.pts or geom.dist(self.pts[-1], dp) > 1e-9:
            self.pts.append(dp)
        self.c.overlay_update()

    def move(self, sp, dp, ev):
        self.hover = _snap45(self.pts[-1], dp) if self.pts and _ctrl(ev) else dp
        self.c.overlay_update()

    def double(self, sp, dp, ev):
        self._finish(closed=False)

    def key(self, ev):
        if ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._finish(closed=False)
            return True
        if ev.key() == Qt.Key.Key_Backspace and self.pts:
            self.pts.pop()
            self.c.overlay_update()
            return True
        return False

    def points(self) -> list:
        return list(self.pts)

    def set_points(self, pts: list) -> None:
        self.pts = list(pts)

    def end_points(self) -> None:
        self._finish(closed=False)

    def _finish(self, closed: bool):
        pts, self.pts, self.hover = self.pts, [], None
        if len(pts) >= 2:
            self.c.commit_shape(Path([geom.polyline(pts, closed=closed and len(pts) > 2)]))

    def paint(self, p):
        pts = self.pts + ([self.hover] if self.hover and self.pts else [])
        if len(pts) >= 2:
            self.preview(p, Path([geom.polyline(pts)]))

    def cancel(self):
        self.pts, self.hover = [], None


class PolyCurveTool(Tool):
    """Polycourbe : des segments et des arcs qui se suivent sans cassure. Tab : segments libres, arcs tangents,
    segments tangents, à tout moment. Retour arrière : retire le dernier morceau ; Entrée ou double-clic : fin ;
    clic sur le premier point : fermée ; Ctrl : segment libre à 45°."""
    MODES = ('line', 'arc', 'tangent')

    def __init__(self, canvas):
        super().__init__(canvas)
        self.first = None
        self.parts: list = []                            # par morceau : ses segments, sa direction à l'arrivée
        self.mode = 'line'
        self.hover = None
        self._say()

    def _say(self) -> None:
        from ..i18n import tr
        label = {'line': tr('Polycourbe : segments libres'), 'arc': tr('Polycourbe : arcs tangents'),
                 'tangent': tr('Polycourbe : segments tangents')}[self.mode]
        win = self.c.window()
        if hasattr(win, 'statusBar'):
            win.statusBar().showMessage(label + ' — ' + tr('Tab : option suivante'), 6000)

    def _at(self):
        return self.parts[-1][0][-1].end if self.parts else self.first

    def _direction(self):
        return self.parts[-1][1] if self.parts else None

    def _part(self, dp, ev=None, closing: bool = False):
        """Le morceau de la position actuelle jusqu'à dp : (segments, direction), ou None s'il n'y en a pas."""
        at, direction = self._at(), self._direction()
        if at is None:
            return None
        mode = self.mode if direction is not None else 'line'
        if closing and mode == 'tangent':                # le premier point n'est pas sur la tangente : on le rejoint
            mode = 'line'
        if mode == 'arc':
            return geom.tangent_arc(at, direction, dp)
        if mode == 'tangent':
            along = (dp[0] - at[0]) * direction[0] + (dp[1] - at[1]) * direction[1]
            if along <= 1e-9:
                return None
            dp = (at[0] + direction[0] * along, at[1] + direction[1] * along)
        elif _ctrl(ev) and not closing:
            dp = _snap45(at, dp)
        length = geom.dist(at, dp)
        if length <= 1e-9:
            return None
        return [Line(at, dp)], ((dp[0] - at[0]) / length, (dp[1] - at[1]) / length)

    def _near_first(self, dp) -> bool:
        if self.first is None or not self.parts or (len(self.parts) < 2 and self.mode != 'arc'):
            return False
        a = self.c.to_screen(*self.first)
        b = self.c.to_screen(*dp)
        return math.hypot(a.x() - b.x(), a.y() - b.y()) < SNAP_PX

    def press(self, sp, dp, ev):
        if self.first is None:
            self.first = dp
        elif self._near_first(dp):
            part = self._part(self.first, closing=True)
            if part is None and geom.dist(self._at(), self.first) > 1e-9:    # droit derrière : pas d'arc pour y revenir
                return
            if part is not None:
                self.parts.append(part)
            self._finish(closed=True)
            return
        else:
            part = self._part(dp, ev)
            if part is not None:
                self.parts.append(part)
        self.c.overlay_update()

    def move(self, sp, dp, ev):
        at = self._at()
        if at is not None and _ctrl(ev) and (self.mode == 'line' or self._direction() is None):
            dp = _snap45(at, dp)
        self.hover = dp
        self.c.overlay_update()

    def double(self, sp, dp, ev):
        self._finish(closed=False)

    def wants_key(self, ev) -> bool:
        if ev.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            return True
        return self.first is not None and ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Backspace)

    def key(self, ev):
        k = ev.key()
        if k in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            step = -1 if k == Qt.Key.Key_Backtab else 1
            self.mode = self.MODES[(self.MODES.index(self.mode) + step) % len(self.MODES)]
            self._say()
            self.c.overlay_update()
            return True
        if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._finish(closed=False)
            return True
        if k == Qt.Key.Key_Backspace and self.first is not None:
            if self.parts:
                self.parts.pop()
            else:
                self.first = None
            self.c.overlay_update()
            return True
        return False

    def _segments(self) -> list:
        return [s for segs, _d in self.parts for s in segs]

    def _finish(self, closed: bool) -> None:
        segs = self._segments()
        self.first, self.parts, self.hover = None, [], None
        if segs:
            self.c.commit_shape(Path([Contour(segs, closed)]))

    def paint(self, p):
        segs = self._segments()
        part = self._part(self.hover) if self.hover is not None else None
        if part is not None:
            segs = segs + part[0]
        if segs:
            self.preview(p, Path([Contour(segs, False)]))

    def cancel(self):
        self.first, self.parts, self.hover = None, [], None


class SplineTool(PolylineTool):
    """Courbe par points (comme SPLINE en DAO, outil Courbure) : chaque clic
    est un point de passage d'une courbe lisse ; double-clic ou Entrée =
    fin ; clic sur le premier point = courbe fermée."""

    def _finish(self, closed: bool):
        pts, self.pts, self.hover = self.pts, [], None
        if len(pts) >= 2:
            self.c.commit_shape(Path([geom.through_points(pts, closed=closed and len(pts) > 2)]))

    def paint(self, p):
        pts = self.pts + ([self.hover] if self.hover and self.pts else [])
        if len(pts) >= 2:
            self.preview(p, Path([geom.through_points(pts)]))


class SymCurveTool(Tool):
    """Courbe symétrique (TypeEdit) : on dessine une partie, la courbe se complète d'un seul tenant par rapport à l'axe
    horizontal, à l'axe vertical, aux deux ou à l'origine, pris au centre de la plaque.

    Clic : un point de la courbe. Ctrl (ou Maj) maintenue en déplaçant : un point à l'endroit où commence le déplacement,
    en angle (ou tangent). F : courbe fermée ou ouverte. Double-clic ou Entrée : fin. Retour arrière : retire le dernier.
    """

    def __init__(self, canvas, mode: str):
        super().__init__(canvas)
        self.mode = mode
        self.pts: list = []
        self.corners: set = set()
        self.hover = None
        self.closed = True
        self._held = False
        self._say()

    def _say(self) -> None:
        from ..i18n import tr
        self.c.measured.emit(tr('Courbe fermée. F : courbe ouverte ; double-clic ou Entrée : fin') if self.closed
                             else tr('Courbe ouverte. F : courbe fermée ; double-clic ou Entrée : fin'))

    def points(self) -> list:
        return list(self.pts)

    def set_points(self, pts: list) -> None:
        self.pts = list(pts)
        self.corners = {i for i in self.corners if i < len(self.pts)}

    def end_points(self) -> None:
        self._finish()

    def _contour(self, pts=None) -> Contour:
        from ..core.symmetric import sym_curve
        return sym_curve(self.pts if pts is None else pts, self.mode, self.c.symmetry_center(), self.closed, self.corners,
                         SNAP_PX / max(self.c.scale, 1e-9))

    def _add(self, dp, corner: bool) -> None:
        if not self.pts or geom.dist(self.pts[-1], dp) > 1e-9:
            self.pts.append(dp)
            if corner:
                self.corners.add(len(self.pts) - 1)

    def press(self, sp, dp, ev):
        self._add(dp, _ctrl(ev))
        self.c.overlay_update()

    def move(self, sp, dp, ev):
        self.hover = dp
        ctrl = _ctrl(ev)
        held = ctrl or (ev is not None and bool(ev.modifiers() & Qt.KeyboardModifier.ShiftModifier))
        if held and not self._held and self.pts:
            self._add(dp, ctrl)
        self._held = held
        self.c.overlay_update()

    def double(self, sp, dp, ev):
        self._finish()

    def wants_key(self, ev) -> bool:
        k = ev.key()
        if k == Qt.Key.Key_F:
            return not ev.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
        return bool(self.pts) and k in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Backspace)

    def key(self, ev) -> bool:
        if not self.wants_key(ev):
            return False
        if ev.key() == Qt.Key.Key_F:
            self.closed = not self.closed
            self._say()
        elif ev.key() == Qt.Key.Key_Backspace:
            self.pts.pop()
            self.corners.discard(len(self.pts))
        else:
            self._finish()
        self.c.overlay_update()
        return True

    def _finish(self) -> None:
        contour = self._contour()
        self.cancel()
        if not contour.segments:
            return
        # la symétrie est déjà faite : le dessin symétrique ou la rosace en cours ne s'y ajoutent pas
        saved = self.c.symmetric, self.c.cyclic
        self.c.symmetric, self.c.cyclic = False, 0
        try:
            self.c.commit_shape(Path([contour]))
        finally:
            self.c.symmetric, self.c.cyclic = saved

    def cancel(self):
        self.pts, self.corners, self.hover, self._held = [], set(), None, False

    def paint(self, p):
        cx, cy = self.c.to_screen(*self.c.symmetry_center()).x(), self.c.to_screen(*self.c.symmetry_center()).y()
        p.setPen(_pen(_cc('symmetry'), 1, Qt.PenStyle.DashDotLine))
        if self.mode != 'oy':
            p.drawLine(QPointF(0, cy), QPointF(self.c.width(), cy))
        if self.mode != 'ox':
            p.drawLine(QPointF(cx, 0), QPointF(cx, self.c.height()))
        if self.pts:
            pts = self.pts + ([self.hover] if self.hover else [])
            self.preview(p, Path([self._contour(pts)]))


class DoubleLineTool(PolylineTool):
    """Ligne double (TypeEdit : Ligne simple/double) : clics comme pour une
    polyligne ; tracée en deux traits parallèles d'après `canvas.dline`
    (largeur, calage, bouts)."""

    def _path(self, pts, closed=False):
        from ..core.doubleline import double_line
        o = getattr(self.c, 'dline', None) or {}
        return double_line(pts, o.get('width', 2.0), o.get('justify', 'centre'), o.get('ends', 'ouvert'), closed,
                           o.get('corners', 'aigu'), o.get('left'), o.get('right'))

    def _finish(self, closed: bool):
        pts, self.pts, self.hover = self.pts, [], None
        if len(pts) >= 2:
            path = self._path(pts, closed and len(pts) > 2)
            if path.contours:
                self.c.commit_shape(path)

    def paint(self, p):
        pts = self.pts + ([self.hover] if self.hover and self.pts else [])
        if len(pts) >= 2:
            self.preview(p, self._path(pts))


class ArcTool(Tool):
    """Arc par trois points : départ, passage, arrivée. Maj sur le troisième clic (TypeEdit) : départ, arrivée, puis la
    courbure."""
    NEED = 3                            # les clics qui posent la forme

    def __init__(self, canvas):
        super().__init__(canvas)
        self.pts: list = []
        self.hover = None
        self.last = False

    def points(self) -> list:
        return list(self.pts)

    def set_points(self, pts: list) -> None:
        """F2 : les points saisis remplacent ceux du tracé ; le dernier attendu pose la forme."""
        self.pts = []
        for x, y in pts[:self.NEED]:
            if self.c.tool_obj is not self:
                break
            self.c.click_at(x, y)

    def _arc(self, third, last: bool):
        a, b = self.pts
        return geom.arc_3points(a, third, b) if last else geom.arc_3points(a, b, third)

    def press(self, sp, dp, ev):
        if len(self.pts) == 2:
            c = self._arc(dp, _shift(ev))
            self.pts = []
            if c is not None:
                self.c.commit_shape(Path([c]))
        else:
            self.pts.append(dp)
        self.c.overlay_update()

    def move(self, sp, dp, ev):
        self.hover = dp
        self.last = _shift(ev)
        self.c.overlay_update()

    def paint(self, p):
        if len(self.pts) == 1 and self.hover:
            self.preview(p, Path([geom.polyline([self.pts[0], self.hover])]))
        elif len(self.pts) == 2 and self.hover:
            c = self._arc(self.hover, self.last)
            if c:
                self.preview(p, Path([c]))

    def cancel(self):
        self.pts, self.hover = [], None


class ZoomTool(Tool):
    """Zoom fenêtre : glisser un rectangle le cadre ; un clic rapproche."""
    cursor = Qt.CursorShape.CrossCursor

    def __init__(self, canvas):
        super().__init__(canvas)
        self.a = self.b = None

    def press(self, sp, dp, ev):
        self.a = self.b = QPointF(sp)

    def move(self, sp, dp, ev):
        if self.a is not None:
            self.b = QPointF(sp)
            self.c.overlay_update()

    def release(self, sp, dp, ev):
        if self.a is None:
            return
        a, self.a = self.a, None
        if abs(sp.x() - a.x()) < 5 and abs(sp.y() - a.y()) < 5:
            self.c.zoom_at(1.6, QPointF(sp))
        else:
            (x0, y0), (x1, y1) = self.c.to_doc(a), self.c.to_doc(QPointF(sp))
            self.c.fit((min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))
        self.c.overlay_update()

    def paint(self, p):
        if self.a is not None and self.b is not None:
            p.setPen(_pen(None, 1, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRectF(self.a, self.b).normalized())

    def cancel(self):
        self.a = self.b = None


class BreakLineTool(ArcTool):
    """Ligne de coupure : deux clics, le symbole de rupture entre eux
    (hauteur `canvas.breakline_size`, 0 : un sixième de la longueur)."""
    NEED = 2

    def _contour(self, a, b):
        from ..core.cadtools import break_line
        return break_line(a, b, float(getattr(self.c, 'breakline_size', 0.0) or 0.0))

    def press(self, sp, dp, ev):
        self.pts.append(dp)
        if len(self.pts) == 2:
            c = self._contour(*self.pts)
            self.pts = []
            if c is not None:
                self.c.commit_shape(Path([c]))
        self.c.overlay_update()

    def paint(self, p):
        if len(self.pts) == 1 and self.hover:
            c = self._contour(self.pts[0], self.hover)
            if c is not None:
                self.preview(p, Path([c]))


class Circle3Tool(ArcTool):
    """Cercle passant par trois points."""

    def press(self, sp, dp, ev):
        from ..core.shapes import circle_3points
        self.pts.append(dp)
        if len(self.pts) == 3:
            c = circle_3points(*self.pts)
            self.pts = []
            if c is not None:
                self.c.commit_shape(Path([c]))
        self.c.overlay_update()

    def paint(self, p):
        from ..core.shapes import circle_3points
        if len(self.pts) == 1 and self.hover:
            self.preview(p, Path([geom.polyline([self.pts[0], self.hover])]))
        elif len(self.pts) == 2 and self.hover:
            c = circle_3points(self.pts[0], self.pts[1], self.hover)
            if c:
                self.preview(p, Path([c]))


class Circle2Tool(ArcTool):
    """Cercle par deux points : les bouts d'un diamètre."""
    NEED = 2

    def press(self, sp, dp, ev):
        from ..core.shapes import circle_2points
        self.pts.append(dp)
        if len(self.pts) == 2:
            c = circle_2points(*self.pts)
            self.pts = []
            if c is not None:
                self.c.commit_shape(Path([c]))
        self.c.overlay_update()

    def paint(self, p):
        from ..core.shapes import circle_2points
        if len(self.pts) == 1 and self.hover:
            c = circle_2points(self.pts[0], self.hover)
            if c:
                self.preview(p, Path([c, geom.polyline([self.pts[0], self.hover])]))


class ArcCenterTool(ArcTool):
    """Arc par centre, départ et fin : le centre, le départ (le rayon), puis
    la direction de fin ; sens trigonométrique, Ctrl : sens horaire. F2 : le centre, le rayon et les angles en chiffres."""
    by_angles = True

    def __init__(self, canvas):
        super().__init__(canvas)
        self.cw = False

    def press(self, sp, dp, ev):
        from ..core.shapes import arc_center
        self.pts.append(dp)
        if len(self.pts) == 3:
            c = arc_center(*self.pts, clockwise=_ctrl(ev))
            self.pts = []
            if c is not None:
                self.c.commit_shape(Path([c]))
        self.c.overlay_update()

    def move(self, sp, dp, ev):
        self.cw = _ctrl(ev)
        super().move(sp, dp, ev)

    def paint(self, p):
        from ..core.shapes import arc_center
        if len(self.pts) == 1 and self.hover:
            self.preview(p, Path([geom.polyline([self.pts[0], self.hover])]))
        elif len(self.pts) == 2 and self.hover:
            c = arc_center(self.pts[0], self.pts[1], self.hover, clockwise=self.cw)
            guide = geom.polyline([self.pts[1], self.pts[0], self.hover])
            self.preview(p, Path([c, guide] if c else [guide]))


class RectThreeTool(ArcTool):
    """Rectangle 3 points : deux clics pour un côté (il donne l'inclinaison),
    un troisième pour l'autre côté ; coins du rectangle par défaut."""

    def _spec(self, c):
        from ..core.forms import rect_by_3points
        return rect_by_3points(self.pts[0], self.pts[1], c, self.c.form_default('rect'))

    def press(self, sp, dp, ev):
        self.pts.append(dp)
        if len(self.pts) == 3:
            s = self._spec(dp)
            self.pts = []
            if s is not None:
                self.c.commit_form(s)
        self.c.overlay_update()

    def paint(self, p):
        if len(self.pts) == 1 and self.hover:
            self.preview(p, Path([geom.polyline([self.pts[0], self.hover])]))
        elif len(self.pts) == 2 and self.hover:
            s = self._spec(self.hover)
            self.preview(p, s.build() if s else Path([geom.polyline(self.pts)]))


class EllipseAxisTool(ArcTool):
    """Ellipse par axe : les deux bouts d'un axe, puis un clic à la distance
    voulue du centre pour l'autre demi-axe ; l'ellipse suit l'inclinaison de
    l'axe."""

    def press(self, sp, dp, ev):
        from ..core.forms import ellipse_by_axis
        self.pts.append(dp)
        if len(self.pts) == 3:
            s = ellipse_by_axis(*self.pts)
            self.pts = []
            if s is not None:
                self.c.commit_form(s)
        self.c.overlay_update()

    def paint(self, p):
        from ..core.forms import ellipse_by_axis
        if len(self.pts) == 1 and self.hover:
            self.preview(p, Path([geom.polyline([self.pts[0], self.hover])]))
        elif len(self.pts) == 2 and self.hover:
            a, b = self.pts
            m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            s = ellipse_by_axis(a, b, self.hover)
            guide = [geom.polyline([a, b]), geom.polyline([m, self.hover])]
            self.preview(p, Path(s.build().contours + guide if s else guide))


class PolygonEdgeTool(ArcTool):
    """Polygone par côté : deux clics, les bouts d'un côté ; le polygone (nombre
    de côtés du ruban) se pose à gauche du côté tracé, Ctrl : à droite."""
    NEED = 2

    def __init__(self, canvas):
        super().__init__(canvas)
        self.right = False

    def _spec(self, b, right):
        from ..core.forms import polygon_on_edge
        return polygon_on_edge(self.pts[0], b, self.c.poly_sides, right, self.c.form_default('polygon'))

    def press(self, sp, dp, ev):
        self.pts.append(dp)
        if len(self.pts) == 2:
            s = self._spec(dp, _ctrl(ev))
            self.pts = []
            if s is not None:
                self.c.commit_form(s)
        self.c.overlay_update()

    def move(self, sp, dp, ev):
        self.right = _ctrl(ev)
        super().move(sp, dp, ev)

    def paint(self, p):
        if len(self.pts) == 1 and self.hover:
            s = self._spec(self.hover, self.right)
            if s is not None:
                self.preview(p, s.build())


class TanCircleTool(Tool):
    """Cercle tangent (comme CERCLE TTR / TTT en DAO) : clic sur deux traits
    droits, cercles ou arcs, près des points de contact voulus — cercle du
    rayon réglé tangent aux deux ; rayon 0 : un 3e clic, cercle tangent aux
    trois (`core.tancircle`). Aperçu au survol de l'objet qui achève."""
    cursor = Qt.CursorShape.PointingHandCursor

    def __init__(self, canvas):
        super().__init__(canvas)
        self.picks: list = []                # [(objet, point cliqué)]
        self.ghost = None

    def _radius(self) -> float:
        return float(getattr(self.c, 'tan_circle_radius', 0.0) or 0.0)

    def _need(self) -> int:
        return 2 if self._radius() > 0 else 3

    def _object(self, sp, dp):
        from ..core import tancircle as TC
        hit = self.c.pick(sp)
        return TC.pick(hit.path, dp) if isinstance(hit, Shape) else None

    def _solve(self, picks):
        from ..core import tancircle as TC
        if len(picks) == 2 and self._radius() > 0:
            return TC.ttr(picks[0][0], picks[0][1], picks[1][0], picks[1][1], self._radius())
        if len(picks) == 3:
            return TC.ttt(picks)
        return None

    def press(self, sp, dp, ev):
        from ..i18n import tr
        obj = self._object(sp, dp)
        if obj is None:
            self.c.measured.emit(tr('Cliquez un trait droit, un cercle ou un arc, près du point de contact'))
            return
        self.picks.append((obj, dp))
        self.ghost = None
        if len(self.picks) < self._need():
            self.c.measured.emit(tr('Objet {0} sur {1} : cliquez le suivant, près du point de contact').format(
                len(self.picks), self._need()))
            self.c.overlay_update()
            return
        got, self.picks = self._solve(self.picks), []
        self.c.overlay_update()
        if got is None:
            self.c.measured.emit(tr('Aucun cercle tangent à ces objets (rayon trop petit ou objets parallèles)'))
            return
        self.c.commit_shape(Path([geom.circle(got[0], got[1])]))

    def move(self, sp, dp, ev):
        ghost = None
        if self.picks and len(self.picks) == self._need() - 1:
            obj = self._object(sp, dp)
            if obj is not None:
                ghost = self._solve(self.picks + [(obj, dp)])
        if ghost != self.ghost:
            self.ghost = ghost
            self.c.overlay_update()

    def paint(self, p):
        if self.ghost:
            self.preview(p, Path([geom.circle(self.ghost[0], self.ghost[1])]))

    def cancel(self):
        self.picks, self.ghost = [], None


class BezierTool(Tool):
    """Plume : clic = point anguleux, cliquer-glisser = point lisse (poignées
    symétriques) ; clic sur le premier point = fermé ; Entrée = fin."""

    def __init__(self, canvas):
        super().__init__(canvas)
        self.nodes: list[list] = []     # [point, poignée sortante (vecteur)]
        self.drag = False
        self.hover = None

    def points(self) -> list:
        return [n[0] for n in self.nodes]

    def set_points(self, pts: list) -> None:
        self.nodes = [[tuple(p), self.nodes[i][1] if i < len(self.nodes) else (0.0, 0.0)] for i, p in enumerate(pts)]

    def end_points(self) -> None:
        self._finish(False)

    def press(self, sp, dp, ev):
        if len(self.nodes) >= 2:
            a = self.c.to_screen(*self.nodes[0][0])
            if math.hypot(a.x() - sp.x(), a.y() - sp.y()) < SNAP_PX:
                self._finish(True)
                return
        self.nodes.append([dp, (0.0, 0.0)])
        self.drag = True

    def move(self, sp, dp, ev):
        if self.drag and self.nodes:
            n = self.nodes[-1]
            n[1] = (dp[0] - n[0][0], dp[1] - n[0][1])
        self.hover = dp
        self.c.overlay_update()

    def release(self, sp, dp, ev):
        self.drag = False

    def double(self, sp, dp, ev):
        if self.nodes and len(self.nodes) > 1:
            self.nodes.pop()            # le double-clic a ajouté un point en trop
        self._finish(False)

    def key(self, ev):
        if ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._finish(False)
            return True
        if ev.key() == Qt.Key.Key_Backspace and self.nodes:
            self.nodes.pop()            # on reprend à l'avant-dernier point
            self.c.overlay_update()
            return True
        return False

    def _segments(self, nodes, closed):
        segs = []
        pairs = list(zip(nodes, nodes[1:])) + ([(nodes[-1], nodes[0])] if closed else [])
        for (a, ha), (b, hb) in pairs:
            if ha == (0.0, 0.0) and hb == (0.0, 0.0):
                if geom.dist(a, b) > 1e-9:
                    segs.append(Line(a, b))
            else:
                segs.append(Cubic(a, (a[0] + ha[0], a[1] + ha[1]), (b[0] - hb[0], b[1] - hb[1]), b))
        return segs

    def _finish(self, closed):
        nodes, self.nodes = self.nodes, []
        if len(nodes) >= 2:
            segs = self._segments(nodes, closed)
            if segs:
                self.c.commit_shape(Path([Contour(segs, closed)]))

    def paint(self, p):
        nodes = list(self.nodes)
        if not self.drag and self.hover and nodes:
            nodes = nodes + [[self.hover, (0.0, 0.0)]]
        if len(nodes) >= 2:
            self.preview(p, Path([Contour(self._segments(nodes, False), False)]))
        p.setPen(_pen())
        for pt, h in self.nodes:
            s = self.c.to_screen(*pt)
            p.drawRect(QRectF(s.x() - 3, s.y() - 3, 6, 6))
            if h != (0.0, 0.0):
                for sign in (1, -1):
                    q = self.c.to_screen(pt[0] + sign * h[0], pt[1] + sign * h[1])
                    p.drawLine(s, q)
                    p.drawEllipse(q, 3, 3)

    def cancel(self):
        self.nodes = []


class DimensionTool(Tool):
    """Cote (core.dims), comme TypeEdit — Tab : type suivant :
    alignée, horizontale, verticale (clic au départ, clic à l'arrivée, clic
    pour placer la ligne de cote ; Ctrl : horizontale ou verticale) ;
    angulaire (premier point, sommet, second point, clic pour le rayon de
    l'arc) ; radiale (clic sur un cercle ou un arc, clic pour placer le
    texte) ; radiale à ressaut (de même, puis clic pour le départ de la
    ligne, près du centre : grands rayons) ; longueur d'arc (clic sur un
    arc, clic pour le rayon de l'arc de cote). Options : clic droit sur le
    bouton Cote, double-clic sur une cote."""
    #: accroché aux points sans F3 si l'accrochage intuitif est choisi
    intuitive_snap = True
    MODES = (('libre', 'Cote alignée'), ('horizontale', 'Cote horizontale'), ('verticale', 'Cote verticale'),
             ('angulaire', 'Cote angulaire'), ('radiale', 'Cote radiale'), ('arc', 'Cote de longueur d\'arc'),
             ('ordonnee', 'Cote en ordonnée'), ('repere', 'Repère (flèche et texte)'), ('chaine', 'Cotation en chaîne'),
             ('base', 'Cotation depuis une ligne de base'), ('rayon_ressaut', 'Cote radiale à ressaut'))
    #: cotation depuis une ligne de base : écart entre deux lignes de cote (× hauteur du texte)
    BASE_STEP = 2.2

    def __init__(self, canvas, mode: str = 'libre'):
        super().__init__(canvas)
        self.pts: list = []
        self.hover = None
        self.mode = mode
        self.prev = None                 # dernière cote linéaire (chaîne : on repart de son arrivée)
        self.base = None                 # ligne de base : la première cote, et le rang de la suivante
        self.base_k = 1

    def _linear_ref(self):
        """Cote linéaire de référence : la dernière posée par l'outil, sinon
        celle qui est sélectionnée."""
        from ..core.dims import dim_of
        if self.prev is not None:
            return self.prev
        for it in self.c.selection:
            d = dim_of(it)
            if d is not None and d.kind in ('libre', 'horizontale', 'verticale'):
                self.prev = d
                return d
        return None

    def _continued(self, hover):
        """Cote suivante en chaîne (départ = arrivée de la précédente, même
        ligne de cote) ou depuis la ligne de base (même départ, ligne décalée)."""
        from ..core.dims import Dim, _direction
        ref = self._linear_ref() if self.mode == 'chaine' else (self.base or self._linear_ref())
        if ref is None or hover is None:
            return None
        if self.mode == 'base' and self.base is None:
            self.base, self.base_k = ref, 1
        start = tuple(ref.points[1] if self.mode == 'chaine' else ref.points[0])
        p2 = tuple(hover)                                # point coté réel (lignes d'attache jusqu'à lui)
        u = _direction(ref)
        n = (-u[1], u[0])
        line = ref.points[0][0] * n[0] + ref.points[0][1] * n[1] + ref.offset
        if self.mode == 'base':
            sg = 1.0 if ref.offset >= 0 else -1.0
            line += sg * self.base_k * self.BASE_STEP * ref.style.text_height
        d = Dim(ref.kind, [start, p2], line - (start[0] * n[0] + start[1] * n[1]), self.style())
        if ref.kind == 'libre':
            d.offset = ref.offset + ((self.base_k * self.BASE_STEP * ref.style.text_height *
                                      (1.0 if ref.offset >= 0 else -1.0)) if self.mode == 'base' else 0.0)
        return d if d.value() > 1e-9 else None

    def _second(self, dp):
        """Point d'arrivée selon le type de cote (horizontale : même Y que
        le départ, verticale : même X)."""
        if not self.pts:
            return dp
        a = self.pts[0]
        if self.mode == 'horizontale':
            return (dp[0], a[1])
        if self.mode == 'verticale':
            return (a[0], dp[1])
        return dp

    def key(self, ev) -> bool:
        if ev.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            keys = [m for m, _l in self.MODES]
            step = -1 if ev.key() == Qt.Key.Key_Backtab else 1
            old = self.mode
            self.mode = keys[(keys.index(self.mode) + step) % len(keys)]
            linear = ('libre', 'horizontale', 'verticale')
            if self.mode == 'base':
                self.base, self.base_k = None, 1
            clicks = ('radiale', 'rayon_ressaut', 'arc', 'ordonnee', 'repere')
            if (old in linear) != (self.mode in linear) or self.mode in clicks or old in clicks:
                self.pts = []                              # autre façon de cliquer : on reprend
            elif len(self.pts) > 1 and self.mode in linear:
                self.pts[1] = self._second(self.pts[1])   # l'arrivée suit le nouveau type
            label = dict(self.MODES)[self.mode]
            win = self.c.window()
            if hasattr(win, 'statusBar'):
                from ..i18n import tr
                win.statusBar().showMessage(tr(label) + ' — ' + tr('Tab : autre type de cote'), 4000)
            self.c.overlay_update()
            return True
        return False

    def wants_key(self, ev) -> bool:
        return ev.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab)

    def style(self):
        fn = getattr(self.c, 'dim_style_fn', None)
        if fn is not None:
            try:
                return fn()
            except Exception:                            # noqa: BLE001 — réglage illisible
                pass
        from ..core.dims import DimStyle
        return DimStyle(text_height=self.c.dim_text)

    def _circle_at(self, dp):
        """(centre, rayon) du cercle ou de l'arc sous le point, ou None."""
        from ..core.shapes import fit_circle
        tol = SNAP_PX / self.c.scale
        best = None
        for it in self.c.shown_items():
            for leaf in _shape_leaves(it):
                b = leaf.bbox()
                if not b or not (b[0] - tol <= dp[0] <= b[2] + tol and b[1] - tol <= dp[1] <= b[3] + tol):
                    continue
                for c in leaf.path.contours:
                    for s in c.segments:
                        cp = getattr(s, 'circle_params', None)
                        r = cp() if cp is not None else None
                        if r is not None and abs(geom.dist(r[0], dp) - r[1]) < tol:
                            if best is None or abs(geom.dist(r[0], dp) - r[1]) < best[2]:
                                best = (r[0], r[1], abs(geom.dist(r[0], dp) - r[1]))
                    if best is None:
                        f = fit_circle(c)
                        if f is not None and abs(geom.dist(f[0], dp) - f[1]) < tol:
                            best = (f[0], f[1], 0.0)
        return (best[0], best[1]) if best else None

    def _arc_at(self, sp, dp):
        """L'arc de cercle sous le point (morceaux du même cercle réunis) :
        (début, centre, fin, point au milieu du morceau cliqué), ou None
        (cercle entier, autre trait)."""
        from ..core import measuregeom as MG
        path = _picked_path(self.c, sp)
        info = MG.radius_info(path, dp) if path is not None else None
        if info is None or info['kind'] != 'arc':
            return None
        c, i, _t, _d = MG.segment_at(path, dp)
        return info['start'], info['center'], info['end'], c.segments[i].point(0.5)

    def dim(self, hover):
        """Cote en cours (core.dims.Dim) d'après les clics et la souris."""
        from ..core.dims import Dim
        if hover is None:
            return None
        st = self.style()
        if self.mode == 'angulaire':
            if len(self.pts) < 2:
                return None
            p1, v = self.pts[0], self.pts[1]
            p3 = self.pts[2] if len(self.pts) > 2 else hover
            r = geom.dist(v, hover) if len(self.pts) > 2 else max(geom.dist(v, p1), 5.0)
            return Dim('angulaire', [p1, v, p3], r, st)
        if self.mode in ('chaine', 'base'):
            return self._continued(hover)
        if self.mode == 'ordonnee':                        # point coté, puis bout du trait
            if not self.pts:
                return None
            o = getattr(self.c, 'origin', None) or (0.0, 0.0)            # origine du dessin
            return Dim('ordonnee', [tuple(o), self.pts[0], hover], 0.0, st)
        if self.mode == 'repere':                          # pointe, puis coude ; texte demandé
            if not self.pts:
                return None
            return Dim('repere', [self.pts[0], hover], 0.0, st)
        if self.mode == 'rayon_ressaut' and len(self.pts) == 2:     # le rayon, puis le départ de la ligne
            d = self.pts[1]
            return Dim('radiale', list(d.points[:2]) + [hover], d.offset, d.style)
        if self.mode in ('radiale', 'rayon_ressaut'):
            if not self.pts:
                return None
            c, r = self.pts[0]
            d = geom.dist(c, hover)
            if d < 1e-9:
                return None
            u = ((hover[0] - c[0]) / d, (hover[1] - c[1]) / d)
            p = (c[0] + u[0] * r, c[1] + u[1] * r)
            return Dim('radiale', [c, p], d - r, st)
        if self.mode == 'arc':                             # l'arc, puis le rayon de l'arc de cote
            if not self.pts:
                return None
            R = geom.dist(self.pts[0][1], hover)
            return Dim('arc', list(self.pts[0]), R, st) if R > 1e-9 else None
        if len(self.pts) < 2:
            return None
        p1, p2 = self.pts[0], self.pts[1]
        if self.mode == 'horizontale':
            n = (0.0, 1.0)
        elif self.mode == 'verticale':
            n = (-1.0, 0.0)
        else:
            L = geom.dist(p1, p2)
            if L < 1e-9:
                return None
            n = (-(p2[1] - p1[1]) / L, (p2[0] - p1[0]) / L)
        off = (hover[0] - p1[0]) * n[0] + (hover[1] - p1[1]) * n[1]
        return Dim(self.mode, [p1, p2], off, st)

    def press(self, sp, dp, ev):
        if self.mode in ('chaine', 'base'):
            d = self._continued(dp)
            if d is None:
                win = self.c.window()
                if hasattr(win, 'statusBar') and self._linear_ref() is None:
                    from ..i18n import tr
                    win.statusBar().showMessage(tr('Posez (ou sélectionnez) d\'abord une cote linéaire'), 4000)
                return
            self.c.commit_dim(d)
            if self.mode == 'chaine':
                self.prev = d
            else:
                self.base_k += 1
            return
        if self.mode in ('ordonnee', 'repere'):
            if not self.pts:
                self.pts = [dp]
                return
            d = self.dim(dp)
            self.pts = []
            if d is not None and self.mode == 'repere':
                fn = getattr(self.c, 'leader_text_fn', None)
                text = fn() if fn is not None else None
                if text is None:
                    return                                   # texte abandonné
                d.style.prefix, d.style.suffix = text, ''
            if d is not None:
                self.c.commit_dim(d)
            return
        if self.mode == 'rayon_ressaut' and len(self.pts) == 1:
            d = self.dim(dp)
            if d is not None:
                self.pts.append(d)
            return
        if self.mode in ('radiale', 'rayon_ressaut'):
            if not self.pts:
                c = self._circle_at(dp)
                if c is None:
                    win = self.c.window()
                    if hasattr(win, 'statusBar'):
                        from ..i18n import tr
                        win.statusBar().showMessage(tr('Cote radiale : cliquer sur un cercle ou un arc'), 4000)
                    return
                self.pts = [c]
                return
            d = self.dim(dp)
            self.pts = []
            if d is not None:
                self.c.commit_dim(d)
            return
        if self.mode == 'arc':
            if not self.pts:
                a = self._arc_at(sp, dp)
                if a is None:
                    win = self.c.window()
                    if hasattr(win, 'statusBar'):
                        from ..i18n import tr
                        win.statusBar().showMessage(tr('Cote de longueur d\'arc : cliquer sur un arc'), 4000)
                    return
                self.pts = [a]
                return
            d = self.dim(dp)
            self.pts = []
            if d is not None:
                self.c.commit_dim(d)
            return
        if self.mode == 'angulaire':
            if len(self.pts) < 3:
                self.pts.append(dp)
                return
            d = self.dim(dp)
            self.pts = []
            if d is not None:
                self.c.commit_dim(d)
            return
        if len(self.pts) == 1 and _ctrl(ev):
            a = self.pts[0]
            dp = (dp[0], a[1]) if abs(dp[0] - a[0]) > abs(dp[1] - a[1]) else (a[0], dp[1])
        elif len(self.pts) == 1:
            dp = self._second(dp)
        if len(self.pts) < 2:
            self.pts.append(dp)
            return
        d = self.dim(dp)
        self.pts = []
        if d is not None:
            self.c.commit_dim(d)
            self.prev, self.base = d, None              # la suivante peut partir de celle-ci

    def move(self, sp, dp, ev):
        self.hover = dp
        self.c.overlay_update()

    def paint(self, p):
        from ..core.dims import build
        d = self.dim(self.hover)
        if d is not None:
            parts = build(d)
            self.preview(p, Path([c for part in parts for c in part.contours]))
        elif self.pts and self.hover is not None and self.mode not in ('radiale', 'rayon_ressaut', 'arc', 'ordonnee',
                                                                       'repere'):
            q = self._second(self.hover) if self.mode != 'angulaire' else self.hover
            self.preview(p, Path([geom.polyline(list(self.pts[-1:]) + [q])]))

    def cancel(self):
        self.pts, self.hover = [], None


def _shape_leaves(it):
    from ..core.document import Group, Shape
    if isinstance(it, Group):
        for ch in it.children:
            yield from _shape_leaves(ch)
    elif isinstance(it, Shape) and it.path:
        yield it


#: touches de la saisie d'un texte (les autres raccourcis restent à la fenêtre)
_TYPING_KEYS = (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Backspace, Qt.Key.Key_Delete, Qt.Key.Key_Left,
                Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Home, Qt.Key.Key_End, Qt.Key.Key_Tab,
                Qt.Key.Key_Backtab, Qt.Key.Key_Escape)


def _printable(s: str) -> bool:
    """Des caractères qui s'écrivent, les espaces insécables compris (Alt+0160, AltGr+Espace)."""
    import unicodedata
    return bool(s) and all(ch.isprintable() or unicodedata.category(ch) == 'Zs' for ch in s)


class TextTool(Tool):
    """Texte (TypeEdit) : un clic pose le départ, la frappe écrit dans le dessin — le texte paraît à chaque lettre,
    avec la mise en forme de l'onglet Mise en forme, et reste sélectionné : un champ changé s'y applique aussitôt.
    Entrée : nouvelle ligne ; Tab : un ressort ; flèches, Origine, Fin : le curseur ; Ctrl+V : colle ; Échap,
    Ctrl+Entrée ou un clic ailleurs : le texte est fini (Échap une 2ᵉ fois : l'outil Sélection). Un clic sur un
    texte droit le reprend à l'endroit cliqué. Toute la saisie d'un texte est un seul pas d'annulation. Sans
    fenêtre (`host` None) : le clic demande le texte (signal textRequested).

    La sélection (de `anchor` à `caret`, positions du texte saisi) : double clic, le mot du caractère cliqué ;
    triple, la ligne ; quadruple, tout le texte ; glisser, Maj+clic, Maj+flèches (Origine, Fin) l'étendent ; la
    frappe, Coller, Suppr, Retour arrière la remplacent ou la retirent ; Ctrl+C (Ctrl+Inser) la copie, Ctrl+X
    (Maj+Suppr) la coupe — pendant la saisie, ces touches ne sont jamais la copie ou la coupe de l'objet. Un clic
    dans la boîte du texte qui s'écrit (creux d'une lettre, espace, bout de ligne) reste dans ce texte. Le texte
    changé sans la frappe (Rechercher / remplacer…) : la sélection s'en va."""
    cursor = Qt.CursorShape.IBeamCursor
    BLINK_MS = 530
    CLICK_PX = 6                                         # clics à la suite : au même endroit, à ça près
    CLICK_S = None                                       # … et dans ce délai (None : celui du double clic du système)

    def __init__(self, canvas, host=None):
        super().__init__(canvas)
        self.host = host
        self.item = None                                 # le texte qui s'écrit, dans le dessin
        self.at = None                                   # départ d'un texte pas encore écrit (rien dans le dessin)
        self._caret = 0                                  # position dans le texte saisi (`caret`)
        self.anchor = None                               # l'autre bout de la sélection ; None : pas de sélection
        self._sel_src = None                             # le texte sur lequel la sélection a été faite
        self._clicks = (0, 0.0, None)                    # clics à la suite : (nombre, heure, point de l'écran)
        self._drag_from = None                           # bouton tenu : la position d'où la sélection se tire
        self.begun = False                               # le pas d'annulation de la saisie est posé
        self.lit = True                                  # curseur allumé (il clignote)
        self.timer = None
        self._caret_key = None
        self._caret_pts = []

    # --- état ------------------------------------------------------------------------------------------------
    @property
    def caret(self) -> int:
        return self._caret

    @caret.setter
    def caret(self, value: int) -> None:
        """Le curseur posé : plus de sélection (qui en veut une pose l'ancre ensuite : `_set_anchor`)."""
        self._caret = int(value)
        self.anchor = None

    def _set_anchor(self, a) -> None:
        self.anchor = a
        self._sel_src = self.source() if a is not None else None

    def selection(self):
        """(début, fin) de la sélection dans le texte saisi ; None s'il n'y en a pas — ou plus : le texte a changé
        sans la frappe depuis qu'elle a été faite."""
        if self.anchor is None or self.item is None:
            return None
        src = self.source()
        if self._sel_src is not None and self._sel_src != src:
            self.anchor = None
            return None
        n = len(src)
        a, b = sorted((max(0, min(n, self.anchor)), max(0, min(n, self._caret))))
        return (a, b) if a < b else None

    def selected_text(self) -> str:
        sel = self.selection()
        return self.source()[sel[0]:sel[1]] if sel else ''

    def select(self, a: int, b: int) -> None:
        """La sélection de `a` à `b` (le curseur en `b`) ; `a` = `b` : le curseur seul."""
        self.caret = b
        self._set_anchor(a if a != b else None)
        self.wake()

    def select_word(self, c: int | None = None) -> None:
        from ..core import text as TX
        self.select(*TX.word_span(self.source(), self._caret if c is None else c))

    def select_line(self, c: int | None = None) -> None:
        from ..core import text as TX
        self.select(*TX.line_span(self.source(), self._caret if c is None else c))

    def select_all(self) -> None:
        self.select(0, len(self.source()))

    def copy_selection(self) -> bool:
        """La sélection dans le presse-papiers (un ressort : une tabulation) ; faux sans sélection."""
        from PySide6.QtWidgets import QApplication
        from ..core.text import SPRING
        s = self.selected_text()
        if not s:
            return False
        QApplication.clipboard().setText(s.replace(SPRING, '\t'))
        return True

    def cut_selection(self) -> bool:
        if not self.copy_selection():
            return False
        self.erase(-1)
        self.wake()
        return True

    def active(self) -> bool:
        """Une saisie en cours : départ posé, ou texte qui s'écrit (encore dans le dessin)."""
        if self.item is not None and self.c.doc.layer_of(self.item) is None:
            self._end()                                  # annulé, autre dessin, groupé : la saisie est close
        return self.item is not None or self.at is not None

    def _vertical(self) -> bool:
        v = self.item.extra.get('vertical') if self.item is not None else None
        return isinstance(v, dict) and isinstance(v.get('text'), str)

    def source(self) -> str:
        """Le texte saisi (texte vertical : celui d'avant, une lettre par ligne dans le dessin)."""
        if self.item is None:
            return ''
        return self.item.extra['vertical']['text'] if self._vertical() else self.item.text

    def _shown_index(self) -> int:
        """La position du curseur dans le texte posé."""
        if not self._vertical():
            return self.caret
        n = len(self.source())
        return 2 * self.caret if self.caret < n else max(0, 2 * n - 1)

    # --- souris ----------------------------------------------------------------------------------------------
    def _count_click(self, sp, least: int = 1) -> int:
        """Le rang de ce clic dans une suite de clics rapprochés (temps du double clic, même endroit)."""
        import time
        from PySide6.QtWidgets import QApplication
        n, t, at = self._clicks
        now = time.monotonic()
        near = at is not None and abs(sp.x() - at[0]) <= self.CLICK_PX and abs(sp.y() - at[1]) <= self.CLICK_PX
        limit = self.CLICK_S if self.CLICK_S is not None else QApplication.doubleClickInterval() / 1000.0
        n = n + 1 if near and now - t <= limit else 1
        n = max(n, least)
        self._clicks = (n, now, (sp.x(), sp.y()))
        return n

    def _points(self) -> list:
        """Les points du curseur du texte qui s'écrit (`core.text.caret_points`), gardés tant qu'il ne change pas."""
        from ..core import text as TX
        t = self.item
        key = (id(t), id(t.outline), t.text)
        if key != self._caret_key:
            self._caret_key, self._caret_pts = key, TX.caret_points(t)
        return self._caret_pts

    def _axes(self) -> tuple:
        """Sur le dessin : (le vecteur d'une hauteur de capitale, celui d'un millimètre le long de la ligne)."""
        from ..core import text as TX
        whole = TX.text_matrix(self.item)
        o, u, d = whole.apply((0.0, 0.0)), whole.apply((0.0, self.item.size)), whole.apply((1.0, 0.0))
        return (u[0] - o[0], u[1] - o[1]), (d[0] - o[0], d[1] - o[1])

    def _inside(self, sp) -> bool:
        """Le point de l'écran est-il dans le texte qui s'écrit : la boîte de ses lignes (de sous la ligne de base
        au haut des capitales), élargie de quelques pixels — le creux d'une lettre, une espace, un bout de ligne."""
        if self.item is None:
            return False
        pts = self._points()
        if not pts:
            return False
        (ux, uy), _d = self._axes()
        xs = [v for x, _y in pts for v in (x - 0.25 * ux, x + ux)]
        ys = [v for _x, y in pts for v in (y - 0.25 * uy, y + uy)]
        x, y = self.c.to_doc(sp)
        m = (self.CLICK_PX + 2) / max(float(self.c.scale), 1e-9)
        return min(xs) - m <= x <= max(xs) + m and min(ys) - m <= y <= max(ys) + m

    def _index_at(self, sp) -> int:
        """La position du texte saisi au plus près du point `sp` de l'écran."""
        from ..core import text as TX
        j = TX.caret_index(self.item, self.c.to_doc(sp))
        return (j + 1) // 2 if self._vertical() else j

    def _char_at(self, sp) -> int:
        """Le rang du caractère cliqué en `sp` : celui d'avant la position la plus proche si le clic est avant elle
        sur la ligne."""
        from ..core import text as TX
        p = self.c.to_doc(sp)
        j = TX.caret_index(self.item, p)
        if self._vertical():
            return j // 2                                # posé une lettre par ligne
        pts = self._points()
        _u, (dx, dy) = self._axes()
        if pts and j < len(pts) and (p[0] - pts[j][0]) * dx + (p[1] - pts[j][1]) * dy < 0 \
                and j > TX.line_span(self.source(), j)[0]:
            return j - 1
        return j

    def _multi(self, n: int, sp) -> None:
        """2ᵉ clic : le mot du caractère cliqué ; 3ᵉ : la ligne ; au-delà : tout le texte."""
        from ..core import text as TX
        self._drag_from = None
        if n == 2:
            self.select(*TX.char_span(self.source(), self._char_at(sp)))
        elif n == 3:
            self.select_line(self._index_at(sp))
        else:
            self.select_all()

    def double_clicked(self, sp) -> None:
        """Le texte vient d'être repris par un double clic (outil Sélection) en `sp` : le mot est sélectionné, et
        les clics suivants continuent la suite (ligne, tout le texte)."""
        import time
        if self.item is None:
            return
        self._clicks = (2, time.monotonic(), (sp.x(), sp.y()))
        self._multi(2, sp)

    def press(self, sp, dp, ev, least: int = 1):
        if self.host is None:
            if least == 1:
                self.c.textRequested.emit(dp[0], dp[1])
            return
        n = self._count_click(sp, least)
        typing = self.item is not None and self.active()
        if n > 1 and typing:
            self._multi(n, sp)                           # le texte qui s'écrit, où que tombe le clic
            return
        if typing and (_shift(ev) or self._inside(sp) or self.c.pick(sp) is self.item):
            old = self.anchor if self.selection() is not None else self._caret
            self.edit(self.item, at=self.c.to_doc(sp))   # dans le texte qui s'écrit : le curseur y va
            if _shift(ev) and old != self._caret:        # Maj+clic : la sélection jusque-là
                self._set_anchor(old)
            self._drag_from = self.anchor if self.anchor is not None else self._caret
            return
        hit = self.c.pick(sp)
        self.finish()
        if hit is not None and self.host.typable(hit):
            self.edit(hit, at=self.c.to_doc(sp))
            self._drag_from = self._caret
        else:
            self.start(dp)

    def double(self, sp, dp, ev):
        self.press(sp, dp, ev, least=2)                  # Qt l'envoie à la place du 2ᵉ appui (et du 4ᵉ)

    def move(self, sp, dp, ev):
        """Bouton gauche tenu depuis un clic dans le texte : la sélection se tire jusqu'à la souris."""
        buttons = getattr(ev, 'buttons', None)
        if self._drag_from is None or self.item is None or buttons is None \
                or not (buttons() & Qt.MouseButton.LeftButton):
            return
        if not self.active():
            self._drag_from = None
            return
        c = self._index_at(sp)
        if c != self._caret:
            self.select(self._drag_from, c)

    def release(self, sp, dp, ev):
        self._drag_from = None

    def start(self, p) -> None:
        """Le départ d'un nouveau texte en `p` : rien dans le dessin avant la première lettre."""
        self.finish()
        self.at = (float(p[0]), float(p[1]))
        self.caret = 0
        self._drag_from = None
        if self.c.selection:
            self.c.select([])
        self.wake()

    def edit(self, t, caret: int | None = None, at=None) -> None:
        """Reprend le texte `t` : le curseur à `caret`, sinon au plus près du point `at` du dessin, sinon à la fin."""
        from ..core import text as TX
        if self.item is not t:
            self.finish()
            self.item, self.begun = t, False
        self.at = None
        n = len(self.source())
        if caret is None and at is not None:
            j = TX.caret_index(t, at)
            caret = (j + 1) // 2 if self._vertical() else j
        self.caret = n if caret is None else max(0, min(n, int(caret)))
        if list(self.c.selection) != [t]:
            self.c.select([t])
        self.wake()

    # --- clavier ---------------------------------------------------------------------------------------------
    def wants_key(self, ev) -> bool:
        if not self.active():
            return False
        k, mods = ev.key(), ev.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        alt = bool(mods & Qt.KeyboardModifier.AltModifier)
        if ctrl and not alt:                             # Ctrl+V colle, Ctrl+Entrée finit ; les autres raccourcis passent
            if k in (Qt.Key.Key_V, Qt.Key.Key_Return, Qt.Key.Key_Enter):
                return True
            # … sauf copier et couper d'un texte qui s'écrit : sa sélection, jamais l'objet (même sans sélection : une
            # touche répétée après la coupe ne supprime pas le texte)
            return self.item is not None and not (mods & Qt.KeyboardModifier.ShiftModifier) \
                and k in (Qt.Key.Key_C, Qt.Key.Key_X, Qt.Key.Key_Insert)
        if alt and not ctrl:                             # Alt : les menus (AltGr, Ctrl+Alt, écrit)
            return False
        return k in _TYPING_KEYS or _printable(ev.text())

    def key(self, ev) -> bool:
        from ..core.text import SPRING
        if not self.active():
            return False
        K = Qt.Key
        k, mods = ev.key(), ev.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        alt = bool(mods & Qt.KeyboardModifier.AltModifier)
        if k == K.Key_Escape or (ctrl and not alt and k in (K.Key_Return, K.Key_Enter)):
            self.finish()
            return True
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        if ctrl and not alt and k == K.Key_V:
            from PySide6.QtWidgets import QApplication
            s = QApplication.clipboard().text()
            self.insert(s.replace('\r\n', '\n').replace('\r', '\n').replace('\t', SPRING))
        elif ctrl and not alt and not shift and self.item is not None and k in (K.Key_C, K.Key_X, K.Key_Insert):
            if k == K.Key_X:
                self.cut_selection()
            else:
                self.copy_selection()
        elif (ctrl and not alt) or (alt and not ctrl):
            return False
        elif k in (K.Key_Return, K.Key_Enter):
            self.insert('\n')
        elif k in (K.Key_Tab, K.Key_Backtab):            # Maj+Tab aussi : le focus ne quitte pas le dessin
            self.insert(SPRING)
        elif k == K.Key_Backspace:
            self.erase(-1)
        elif k == K.Key_Delete:
            if not (shift and self.cut_selection()):     # Maj+Suppr : la sélection coupée
                self.erase(1)
        elif k in (K.Key_Left, K.Key_Right, K.Key_Home, K.Key_End, K.Key_Up, K.Key_Down):
            self.move_caret(k, extend=shift)
        elif _printable(ev.text()):
            self.insert(ev.text())
        else:
            return False
        self.wake()
        return True

    def move_caret(self, k, extend: bool = False) -> None:
        """Le curseur : une lettre, le début ou la fin de la ligne, la ligne d'au-dessus ou d'au-dessous (`move`
        reste le mouvement de la souris, celui de tous les outils). `extend` (Maj) : la sélection suit ; sans lui,
        elle s'en va — gauche et droite posent alors le curseur à son début, à sa fin."""
        K = Qt.Key
        if self._vertical():                             # une lettre par ligne : haut et bas vont de lettre en lettre
            k = {K.Key_Up: K.Key_Left, K.Key_Down: K.Key_Right}.get(k, k)
        src = self.source()
        c = self._caret_in(src)
        sel = self.selection()
        if not extend and sel is not None and k in (K.Key_Left, K.Key_Right):
            self.caret = sel[0] if k == K.Key_Left else sel[1]
            return
        anchor = self.anchor if sel is not None else c
        start = src.rfind('\n', 0, c) + 1
        end = src.find('\n', c)
        end = len(src) if end < 0 else end
        if k == K.Key_Left:
            c = max(0, c - 1)
        elif k == K.Key_Right:
            c = min(len(src), c + 1)
        elif k == K.Key_Home:
            c = start
        elif k == K.Key_End:
            c = end
        elif k == K.Key_Up and start > 0:
            above = src.rfind('\n', 0, start - 1) + 1
            c = min(above + c - start, start - 1)
        elif k == K.Key_Down and end < len(src):
            below = src.find('\n', end + 1)
            c = min(end + 1 + c - start, len(src) if below < 0 else below)
        self.caret = c
        if extend and anchor != c:
            self._set_anchor(anchor)

    # --- le texte ----------------------------------------------------------------------------------------------
    def insert(self, s: str) -> None:
        """`s` écrit au curseur (la première lettre crée le texte)."""
        if not s or not self.active():
            return
        src = self.source()
        c = self._caret_in(src)
        a, b = self.selection() or (c, c)                # la sélection est remplacée
        self._set(src[:a] + s + src[b:], a + len(s))

    def _caret_in(self, src: str) -> int:
        """Le curseur dans le texte : celui-ci a pu changer sans la frappe (Rechercher / remplacer, casse…)."""
        self._caret = max(0, min(self._caret, len(src)))
        return self._caret

    def erase(self, direction: int) -> None:
        """La sélection s'en va ; sans elle, la lettre avant (-1) ou après (+1) le curseur."""
        if not self.active():
            return
        src = self.source()
        c = self._caret_in(src)
        sel = self.selection()
        if sel is not None:
            self._set(src[:sel[0]] + src[sel[1]:], sel[0])
        elif direction < 0 and c > 0:
            self._set(src[:c - 1] + src[c:], c - 1)
        elif direction > 0 and c < len(src):
            self._set(src[:c] + src[c + 1:], c)

    def _set(self, src: str, caret: int) -> None:
        if self.item is None:
            if not src:
                return
            self.item = self.host.typed_text_new(self.at, src)
            self.at, self.begun = None, True
        else:
            if not self.begun:
                self.host.typed_text_begin(self.item)
                self.begun = True
            t = self.item
            if self._vertical():                         # `extra` neuf : la copie d'annulation garde l'ancien
                t.extra['vertical'] = dict(t.extra['vertical'], text=src)
                t.text = '\n'.join(src.replace('\n', ' '))
            else:
                t.text = src
            self.host.typed_text_changed(t)
        self.caret = caret

    def finish(self) -> None:
        """Le texte en cours est fini (resté vide : il s'en va) ; plus de saisie."""
        t, begun = self.item, self.begun
        self._end()
        if t is not None and self.host is not None:
            self.host.typed_text_done(t, begun)
        self.c.update()

    def _end(self) -> None:
        self.item, self.at, self.begun = None, None, False
        self.anchor, self._drag_from = None, None
        if self.timer is not None:
            self.timer.stop()

    def cancel(self) -> None:
        self.finish()

    # --- le curseur --------------------------------------------------------------------------------------------
    def wake(self) -> None:
        """Curseur allumé, clignotement repris."""
        self.lit = True
        if self.timer is None:
            from PySide6.QtCore import QTimer
            self.timer = QTimer(self.c)
            self.timer.setInterval(self.BLINK_MS)
            self.timer.timeout.connect(self._blink)
        self.timer.start()
        self.c.update()

    def _blink(self) -> None:
        if not self.active():
            self.timer.stop()
            self.c.update()
            return
        self.lit = not self.lit
        r = self._caret_rect()
        if r is not None:
            self.c.update(r)                             # le curseur seul se repeint
        else:
            self.c.update()

    def caret_line(self):
        """Le trait du curseur : deux points du dessin (sous la ligne de base, haut des capitales), ou None."""
        from ..core import text as TX
        if self.item is None:
            if self.at is None or self.host is None:
                return None
            h = self.host.new_text_height()
            x, y = self.at
            return (x, y - 0.25 * h), (x, y + h)
        t = self.item
        key = (id(t), id(t.outline), t.text)
        if key != self._caret_key:
            self._caret_key, self._caret_pts = key, TX.caret_points(t)
        pts = self._caret_pts
        if not pts:
            return None
        x, y = pts[min(self._shown_index(), len(pts) - 1)]
        whole = TX.text_matrix(t)
        o, u = whole.apply((0.0, 0.0)), whole.apply((0.0, t.size))
        ux, uy = u[0] - o[0], u[1] - o[1]
        return (x - 0.25 * ux, y - 0.25 * uy), (x + ux, y + uy)

    def _caret_screen(self):
        seg = self.caret_line()
        if seg is None:
            return None
        v = self.c.view()
        return v.map(QPointF(*seg[0])), v.map(QPointF(*seg[1]))

    def _caret_rect(self):
        got = self._caret_screen()
        if got is None:
            return None
        return QRectF(got[0], got[1]).normalized().adjusted(-4, -4, 4, 4).toAlignedRect()

    def selection_quads(self) -> list:
        """La sélection sur le dessin : un quadrilatère par ligne (ou par lettre d'un texte vertical), de sous la
        ligne de base au haut des capitales ; un saut de ligne sélectionné : un quadrilatère étroit en bout de ligne."""
        sel = self.selection()
        if sel is None:
            return []
        t = self.item
        pts = self._points()
        if not pts:
            return []
        a, b = sel
        src = self.source()
        if self._vertical():                             # posé une lettre par ligne
            spans = [(2 * i, 2 * i + 1) for i in range(a, b)]
        else:
            spans, s = [], a
            for i in range(a, b):
                if src[i] == '\n':
                    if i > s:
                        spans.append((s, i))
                    spans.append((i, i))                 # le saut de ligne lui-même
                    s = i + 1
            if b > s:
                spans.append((s, b))
        (ux, uy), (dx, dy) = self._axes()
        top = 1.0                                        # plusieurs lignes : elles ne se recouvrent pas
        k = t.text.find('\n')
        if 0 <= k < len(pts) - 1 and (ux or uy):         # l'interligne, mesuré en hauteurs de capitale
            (ax, ay), (bx, by) = pts[0], pts[k + 1]
            pitch = abs((ax - bx) * ux + (ay - by) * uy) / (ux * ux + uy * uy)
            top = min(1.0, max(0.5, pitch - 0.25))
        w = 0.3 * float(t.size)
        out = []
        for s0, s1 in spans:
            if s1 >= len(pts):
                continue
            x0, y0 = pts[s0]
            x1, y1 = pts[s1] if s1 != s0 else (x0 + w * dx, y0 + w * dy)
            out.append([(x0 - 0.25 * ux, y0 - 0.25 * uy), (x1 - 0.25 * ux, y1 - 0.25 * uy),
                        (x1 + top * ux, y1 + top * uy), (x0 + top * ux, y0 + top * uy)])
        return out

    def paint(self, p: QPainter) -> None:
        if not self.active():
            return
        quads = self.selection_quads()
        if quads:
            v = self.c.view()
            color = QColor(_cc('preview'))
            color.setAlpha(80)
            p.save()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            for q in quads:
                p.drawPolygon(QPolygonF([v.map(QPointF(x, y)) for x, y in q]))
            p.restore()
        if not self.lit:
            return
        got = self._caret_screen()
        if got is None:
            return
        p.save()
        p.setPen(_pen(_cc('preview'), 2))
        p.drawLine(got[0], got[1])
        p.restore()


# --- Mode Point ------------------------------------------------------------------

class NodeTool(Tool):
    """Mode Point : points en courbe (nœuds) et hors courbe (poignées) de
    l'objet sélectionné, comme TypeEdit — départ : gros carré, arrivée d'un
    contour ouvert : petit carré, point continu : rond, angle : carré, hors
    courbe : petit rond relié à son point.

    Clic sur un point (en ou hors courbe) : sélection (Maj : ajoute) ;
    glisser : déplacement de tous les points sélectionnés ; glisser depuis le
    vide (ou la forme) : rectangle de sélection des points (Maj : ajoute) ;
    Tout sélectionner : tous les points ; double-clic sur un point : ses
    attributs (X, Y, en courbe / hors courbe) ; double-clic sur un segment :
    nouveau nœud ; Suppr : supprime ; Maj + → / ← : nœud suivant /
    précédent ; flèches : déplacement fin (le pas des flèches) ; Maj + ↑ / ↓ :
    dix fois le pas ; Ctrl + flèche : « pas de déplacement ? », puis les
    points avancent d'un pas dans ce sens (comme hors mode point).
    """
    cursor = Qt.CursorShape.ArrowCursor

    def __init__(self, canvas):
        super().__init__(canvas)
        self.sel: set[tuple[int, int]] = set()        # (contour, nœud)
        self.first_node: tuple[int, int] | None = None  # le premier point cliqué : il donne la valeur d'un alignement
        self.hsel: set[tuple[int, int, int]] = set()  # points hors courbe : (contour, segment, 1 ou 2)
        self.drag = None
        self.band = None                               # rectangle de sélection : (départ, coin, Maj, base)
        self.pending = None                            # projection en attente du clic sur le repère
        self.mark = None                               # point rouge sur le contour, où « + » ajoute un point : (contour, segment, t)

    def select_all_nodes(self) -> int:
        """Tous les points de la forme active ; rend leur nombre."""
        sh = self.shape()
        if sh is None:
            return 0
        self.sel = {(ci, k) for ci, c in enumerate(sh.path.contours) for k in range(nodes.node_count(c))}
        self.hsel = {(ci, si, w) for ci, c in enumerate(sh.path.contours) for si, w, _h in nodes.handles(c)}
        self.c.overlay_update()
        self.c.selectionChanged.emit()
        return len(self.sel) + len(self.hsel)

    def handles_in_rect(self, a: QPointF, b: QPointF) -> set:
        """Points hors courbe de la forme active dans le rectangle écran."""
        sh = self.shape()
        if sh is None:
            return set()
        x0, x1 = sorted((a.x(), b.x()))
        y0, y1 = sorted((a.y(), b.y()))
        out = set()
        for ci, c in enumerate(sh.path.contours):
            for si, w, h in nodes.handles(c):
                q = self.c.to_screen(*h)
                if x0 <= q.x() <= x1 and y0 <= q.y() <= y1:
                    out.add((ci, si, w))
        return out

    def hit_at(self, sp: QPointF):
        """Point sous le curseur : ('node', contour, k) ou ('handle',
        contour, segment, 1|2), sinon None."""
        return self._hit(sp)

    def nodes_in_rect(self, a: QPointF, b: QPointF) -> set:
        """Points de la forme active dans le rectangle écran (a, b)."""
        sh = self.shape()
        if sh is None:
            return set()
        x0, x1 = sorted((a.x(), b.x()))
        y0, y1 = sorted((a.y(), b.y()))
        out = set()
        for ci, c in enumerate(sh.path.contours):
            for k in range(nodes.node_count(c)):
                q = self.c.to_screen(*nodes.node_point(c, k))
                if x0 <= q.x() <= x1 and y0 <= q.y() <= y1:
                    out.add((ci, k))
        return out

    # cible : la forme sélectionnée
    def shapes(self) -> list:
        """Formes de la sélection (groupes dépliés) dont on montre les points."""
        from .canvas import _leaves
        return [it for it in _leaves(self.c.selection) if isinstance(it, Shape)]

    def shape(self) -> Shape | None:
        """Forme active : celle dont on édite les points (la première de la
        sélection, ou celle dont on a cliqué un point)."""
        shapes = self.shapes()
        if not shapes:
            return None
        active = getattr(self, 'active', None)
        if active is None or all(active is not s for s in shapes):
            self.active = shapes[0]
        return self.active

    def _switch_to(self, sp: QPointF) -> bool:
        """Un point d'une autre forme choisie sous le curseur : elle devient active."""
        cur = self.shape()
        for sh in self.shapes():
            if sh is cur:
                continue
            for c in sh.path.contours:
                pts = [nodes.node_point(c, k) for k in range(nodes.node_count(c))] + [h for _s, _w, h in nodes.handles(c)]
                for p in pts:
                    q = self.c.to_screen(*p)
                    if math.hypot(q.x() - sp.x(), q.y() - sp.y()) < SNAP_PX:
                        self.active = sh
                        self.sel, self.hsel = set(), set()
                        return True
        return False

    def _hit(self, sp: QPointF):
        sh = self.shape()
        if sh is None:
            return None
        for ci, c in enumerate(sh.path.contours):
            for si, which, h in nodes.handles(c):
                q = self.c.to_screen(*h)
                if math.hypot(q.x() - sp.x(), q.y() - sp.y()) < SNAP_PX:
                    return ('handle', ci, si, which)
            for k in range(nodes.node_count(c)):
                q = self.c.to_screen(*nodes.node_point(c, k))
                if math.hypot(q.x() - sp.x(), q.y() - sp.y()) < SNAP_PX:
                    return ('node', ci, k)
        return None

    def _hit_segment(self, dp):
        sh = self.shape()
        if sh is None:
            return None
        tol = SNAP_PX / self.c.scale
        best = None
        for ci, c in enumerate(sh.path.contours):
            for si, s in enumerate(c.segments):
                b = s.bbox()
                if not (b[0] - tol <= dp[0] <= b[2] + tol and b[1] - tol <= dp[1] <= b[3] + tol):
                    continue
                t, d = nodes.nearest_on_segment(s, dp)
                if d < tol and (best is None or d < best[3]):
                    best = (ci, si, t, d)
        return best

    def _set_contour(self, ci: int, c: Contour) -> None:
        sh = self.shape()
        cs = list(sh.path.contours)
        cs[ci] = c
        sh.path = Path(cs)
        self.mark = None
        self.c.invalidate([sh])
        self.c.documentChanged.emit()

    def reference_at(self, sp, dp):
        """Repère sous le curseur : ('guide', axe, valeur) ou ('contour',
        Contour) — contour de l'objet sous le curseur ou de l'objet édité."""
        gi = self.c.guide_at(sp)
        if gi is not None:
            axis, v = self.c.guides[gi]
            return ('guide', axis, v)
        from .canvas import _leaves
        tol = SNAP_PX / self.c.scale
        top = self.c.pick(sp)
        cands = [s for s in _leaves([top]) if isinstance(s, Shape)] if top is not None else []
        own = self.shape()
        if own is not None and all(own is not s for s in cands):
            cands.append(own)
        best = None
        for sh in cands:
            for c in sh.path.contours:
                for s in nodes._all_segments(c):
                    b = s.bbox()
                    if not (b[0] - tol <= dp[0] <= b[2] + tol and b[1] - tol <= dp[1] <= b[3] + tol):
                        continue
                    _t, d = nodes.nearest_on_segment(s, dp)
                    if d < tol and (best is None or d < best[0]):
                        best = (d, c)
        return ('contour', best[1]) if best else None

    def project(self, kind: str, ref) -> int:
        """Projette les nœuds sélectionnés sur le repère ; nombre projeté."""
        sh = self.shape()
        if sh is None or ref is None or not self.sel:
            return 0
        if ref[0] == 'guide':
            fn = lambda p: nodes.project_on_guide(ref[1], ref[2], p, kind)
        else:
            fn = lambda p: nodes.project_point(ref[1], p, kind)
        cs, n = nodes.project_nodes(list(sh.path.contours), self.sel, fn)
        if n and cs != list(sh.path.contours):
            if self.c.undo_push:
                self.c.undo_push()
            sh.path = Path(cs)
            self.c.invalidate([sh])
            self.c.documentChanged.emit()
        return n

    def press(self, sp, dp, ev):
        if self.pending is not None:
            from ..i18n import tr
            kind, self.pending = self.pending, None
            ref = self.reference_at(sp, dp)
            n = self.project(kind, ref)
            self.c.measured.emit(tr('{0} point(s) projeté(s)').format(n) if ref is not None
                                 else tr('Pas de repère ici : projection annulée'))
            self.c.overlay_update()
            return
        h = self._hit(sp)
        if h is None and self._switch_to(sp):
            h = self._hit(sp)
        shift = bool(ev.modifiers() & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier))
        hs = self._hit_segment(dp) if h is None and not shift else None
        self.mark = hs[:3] if hs is not None else None
        if h is None:
            hit = self.c.pick(sp)
            if hit is not None and hit is not self.shape() and self.shape() is None:
                self.c.select([hit])
                self.sel.clear()
            elif hit is not None and hit is not self.shape() and not shift:
                self.c.select([hit])                   # une autre forme : elle devient la forme active
                self.sel.clear()
            else:                                      # vide ou la forme : rectangle de sélection des points
                base = (set(self.sel), set(self.hsel)) if shift else (set(), set())
                if not shift:
                    self.sel.clear()
                    self.hsel.clear()
                self.band = (QPointF(sp), QPointF(sp), shift, base)
            self.c.overlay_update()
            return
        if h[0] == 'node':
            key = (h[1], h[2])
            if shift:
                self.sel ^= {key}
                if key in self.sel and self.first_node not in self.sel:
                    self.first_node = key
            elif key not in self.sel:
                self.sel, self.hsel = {key}, set()
                self.first_node = key
        else:
            key = (h[1], h[2], h[3])
            if shift:
                self.hsel ^= {key}
            elif key not in self.hsel:
                self.sel, self.hsel = set(), {key}
        if self.c.undo_push:
            self.c.undo_push()
        self.drag = (h, dp)
        self.c.overlay_update()

    def move(self, sp, dp, ev):
        if self.band is not None:
            a, _b, shift, base = self.band
            self.band = (a, QPointF(sp), shift, base)
            self.sel = base[0] | self.nodes_in_rect(a, QPointF(sp))
            self.hsel = base[1] | self.handles_in_rect(a, QPointF(sp))
            self.c.overlay_update()
            return
        if not self.drag:
            return
        h, start = self.drag
        sh = self.shape()
        if sh is None:
            return
        if h[0] == 'handle' and not self.sel and self.hsel <= {(h[1], h[2], h[3])}:
            _, ci, si, which = h                         # un seul point hors courbe : suit le curseur (accroché)
            self._set_contour(ci, nodes.move_handle(sh.path.contours[ci], si, which, dp))
        else:
            dx, dy = dp[0] - start[0], dp[1] - start[1]
            self._translate_selected(dx, dy)
            self.drag = (h, dp)
        self.c.overlay_update()

    def _extent_step(self, horizontal: bool) -> float | None:
        """Pas proposé par Ctrl+flèche : étendue des points sélectionnés
        dans ce sens plus l'écart des options ; None si elle est nulle."""
        sh = self.shape()
        if sh is None:
            return None
        cs = sh.path.contours
        pts = [nodes.node_point(cs[ci], k) for ci, k in self.sel
               if ci < len(cs) and k < nodes.node_count(cs[ci])]
        pts += [nodes.handle_point(cs[ci], si, w) for ci, si, w in self.hsel
                if ci < len(cs) and si < len(cs[ci].segments)]
        if len(pts) < 2:
            return None
        i = 0 if horizontal else 1
        size = max(q[i] for q in pts) - min(q[i] for q in pts)
        return size + self.c.step_gap_mm if size > 1e-9 else None

    def _translate_selected(self, dx, dy):
        """Déplace les points sélectionnés, en et hors courbe ; un point hors
        courbe attaché à un nœud déplacé le suit déjà (pas deux fois)."""
        sh = self.shape()
        cs = list(sh.path.contours)
        for ci, si, w in sorted(self.hsel):
            if ci < len(cs) and si < len(cs[ci].segments) and (ci, si, w) in {
                    (ci, s, ww) for s, ww, _h in nodes.handles(cs[ci])}:
                k = nodes.handle_node(cs[ci], si, w)
                if k is not None and (ci, k) in self.sel:
                    continue
                q = nodes.handle_point(cs[ci], si, w)
                cs[ci] = nodes.move_handle(cs[ci], si, w, (q[0] + dx, q[1] + dy))
        for ci, k in sorted(self.sel):
            if ci < len(cs) and k < nodes.node_count(cs[ci]):
                p = nodes.node_point(cs[ci], k)
                cs[ci] = nodes.move_node(cs[ci], k, (p[0] + dx, p[1] + dy))
        sh.path = Path(cs)
        self.c.invalidate([sh])
        self.c.documentChanged.emit()

    def release(self, sp, dp, ev):
        if self.band is not None:
            a, _b, _shift, base = self.band
            self.band = None
            if abs(sp.x() - a.x()) + abs(sp.y() - a.y()) > 3:   # un rectangle tracé, pas un clic sur le contour
                self.mark = None
            self.sel = base[0] | self.nodes_in_rect(a, QPointF(sp))
            self.hsel = base[1] | self.handles_in_rect(a, QPointF(sp))
            self.c.overlay_update()
        self.drag = None
        self.c.selectionChanged.emit()

    def snap_exclude(self):
        # pendant un déplacement de nœud, la forme éditée ne sert pas d'accroche
        return self.c.selection if self.drag else ()

    def double(self, sp, dp, ev):
        h = self._hit(sp)
        fn = getattr(self.c, 'point_dialog_fn', None)
        if h is not None and fn is not None:
            self.drag = None
            fn(h)                                        # attributs du point (TypeEdit)
            return
        hs = self._hit_segment(dp)
        if hs is None:
            return
        self._insert(*hs[:3])

    def _insert(self, ci: int, si: int, t: float) -> None:
        if self.c.undo_push:
            self.c.undo_push()
        sh = self.shape()
        c = nodes.insert_node(sh.path.contours[ci], si, t)
        self._set_contour(ci, c)
        k = si if c.closed else si + 1
        self.sel = {(ci, k)}
        self.c.overlay_update()

    def add_marked(self) -> bool:
        """Ajouter un point (TypeEdit) là où l'on a cliqué sur le contour ; rend vrai s'il y en a un."""
        sh, mark = self.shape(), self.mark
        self.mark = None
        if sh is None or mark is None:
            return False
        ci, si, t = mark
        if ci >= len(sh.path.contours) or si >= len(sh.path.contours[ci].segments):
            return False                                 # le tracé a changé depuis le clic (annuler par exemple)
        self._insert(ci, si, t)
        return True

    def delete_selected(self):
        sh = self.shape()
        if sh is None or not (self.sel or self.hsel):
            return
        if self.c.undo_push:
            self.c.undo_push()
        cs = list(sh.path.contours)
        for ci in {ci for ci, _s, _w in self.hsel}:      # points hors courbe d'abord (les nœuds décalent tout)
            cs[ci] = nodes.remove_handles(cs[ci], [(s, w) for c2, s, w in self.hsel if c2 == ci])
        for ci, k in sorted(self.sel, reverse=True):
            cs[ci] = nodes.delete_node(cs[ci], k)
        sh.path = Path([c for c in cs if c.segments])
        self.sel.clear()
        self.hsel.clear()
        self.c.invalidate([sh])
        self.c.documentChanged.emit()
        self.c.overlay_update()

    def wants_key(self, ev) -> bool:
        """Suppr / Retour arrière sur des points sélectionnés : pour le Mode
        Point, pas pour le raccourci « Effacer » (qui supprimerait l'objet). De
        même « + » s'il y a un point rouge et « - » s'il y a des points, avec ou
        sans Maj et sur le pavé numérique ; sinon ils gardent leur raccourci."""
        if self.shape() is None:
            return False
        typed = ev.modifiers() & ~(Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.KeypadModifier)
        if not typed and ev.key() == Qt.Key.Key_Plus:
            return self.mark is not None
        if not typed and ev.key() == Qt.Key.Key_Minus:
            return bool(self.sel or self.hsel)
        return (bool(self.sel or self.hsel) and not ev.modifiers()
                and ev.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace))

    def key(self, ev):
        sh = self.shape()
        if sh is None:
            return False
        k = ev.key()
        shift = bool(ev.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if k == Qt.Key.Key_Plus and self.mark is not None:
            return self.add_marked()
        if k in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace, Qt.Key.Key_Minus) and (self.sel or self.hsel or k != Qt.Key.Key_Minus):
            self.delete_selected()
            return True
        if shift and k in (Qt.Key.Key_Right, Qt.Key.Key_Left) and sh.path.contours:
            ci, cur = (min(self.sel) if self.sel else (0, -1))
            n = nodes.node_count(sh.path.contours[ci])
            cur = (cur + (1 if k == Qt.Key.Key_Right else -1)) % n
            self.sel = {(ci, cur)}
            self.c.overlay_update()
            return True
        moves = {Qt.Key.Key_Left: (-1, 0), Qt.Key.Key_Right: (1, 0),
                 Qt.Key.Key_Up: (0, 1), Qt.Key.Key_Down: (0, -1)}
        if k in moves and ev.modifiers() & Qt.KeyboardModifier.ControlModifier:
            fn = getattr(self.c, 'ask_step_fn', None)
            if fn is None:
                return False
            step = fn(moves[k][0] != 0, self._extent_step(moves[k][0] != 0))
            if step and (self.sel or self.hsel):
                if self.c.undo_push:
                    self.c.undo_push()
                self._translate_selected(moves[k][0] * step, moves[k][1] * step)
                self.c.overlay_update()
            return True
        if k in moves and (self.sel or self.hsel):
            if self.c.undo_push:
                self.c.undo_push()
            step = self.c.arrow_step or self.c.nudge_mm
            if shift:
                step *= 10
            self._translate_selected(moves[k][0] * step, moves[k][1] * step)
            self.c.overlay_update()
            return True
        return False

    def paint(self, p):
        sh = self.shape()
        if self.mark is not None and sh is not None and self.mark[0] < len(sh.path.contours) \
                and self.mark[1] < len(sh.path.contours[self.mark[0]].segments):
            x, y = sh.path.contours[self.mark[0]].segments[self.mark[1]].point(self.mark[2])
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(220, 0, 0))
            p.drawEllipse(self.c.to_screen(x, y), 4.0, 4.0)
        if self.band is not None:
            a, b = self.band[0], self.band[1]
            pen = _pen(_cc('selection'))
            pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRectF(a, b).normalized())
        sh = self.shape()
        if sh is None:
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        others = [o for o in self.shapes() if o is not sh]
        if others:                                         # les autres formes choisies : points discrets
            col = QColor(_cc('node'))
            col.setAlpha(120)
            p.setPen(_pen(col))
            p.setBrush(Qt.BrushStyle.NoBrush)
            for o in others:
                for c in o.path.contours:
                    for k in range(nodes.node_count(c)):
                        q = self.c.to_screen(*nodes.node_point(c, k))
                        p.drawRect(QRectF(q.x() - 2.5, q.y() - 2.5, 5, 5))
        for ci, c in enumerate(sh.path.contours):
            for si, which, h in nodes.handles(c):
                s = c.segments[si]
                q = self.c.to_screen(*h)
                p.setPen(_pen(_cc('node_line')))
                if isinstance(s, Cubic):
                    base = s.p0 if which == 1 else s.p3
                    p.drawLine(self.c.to_screen(*base), q)
                else:                                    # conique : contrôle relié aux deux bouts
                    p.drawLine(self.c.to_screen(*s.p0), q)
                    p.drawLine(q, self.c.to_screen(*s.p2))
                hs = (ci, si, which) in self.hsel
                p.setPen(_pen(_cc('selection') if hs else _cc('node_line')))
                p.setBrush(QColor(_cc('selection') if hs else _cc('node_fill')))
                p.drawEllipse(q, 3.5 if hs else 3, 3.5 if hs else 3)     # hors courbe : petit rond
            n = nodes.node_count(c)
            for k in range(n):
                q = self.c.to_screen(*nodes.node_point(c, k))
                sel = (ci, k) in self.sel
                p.setPen(_pen(_cc('selection') if sel else _cc('node')))
                p.setBrush(QColor(_cc('selection') if sel else _cc('node_fill')))
                if k == 0:
                    p.drawRect(QRectF(q.x() - 5, q.y() - 5, 10, 10))      # départ : gros carré
                elif not c.closed and k == n - 1:
                    p.drawRect(QRectF(q.x() - 3, q.y() - 3, 6, 6))        # arrivée : petit carré
                elif nodes.is_smooth(c, k):
                    p.drawEllipse(q, 4, 4)                                 # point continu : rond
                else:
                    p.drawRect(QRectF(q.x() - 4, q.y() - 4, 8, 8))        # angle : carré

    def cancel(self):
        self.sel.clear()
        self.hsel.clear()
        self.drag = None
        self.mark = None


class SculptTool(Tool):
    """SculptArt (TypeEdit) : peindre sur le relief choisi (ou celui sous le
    curseur) — ajouter, creuser, lisser, aplanir, bruit ; rayon et force dans
    `canvas.sculpt_params` (réglés depuis la fenêtre principale). Un coup de
    pinceau = un pas d'annulation."""
    cursor = Qt.CursorShape.CrossCursor

    def __init__(self, canvas):
        super().__init__(canvas)
        self.img = None
        self.state = None
        self.last = None
        self.pos = None
        self.rng = None
        self._shown = 0.0

    def params(self) -> dict:
        p = {'brush': 'ajouter', 'radius': 2.0, 'strength': 0.1, 'mirror': 'aucun', 'mirror_axes': 4,
             'mask': 'dedans'}
        p.update(getattr(self.c, 'sculpt_params', None) or {})
        return p

    def copies(self, pt) -> list:
        """Le point et ses reflets (Miroir de SculptArt, autour du centre du relief)."""
        from ..core import sculpt as SC
        p = self.params()
        maps = SC.mirror_maps(p.get('mirror', 'aucun'), int(p.get('mirror_axes', 4) or 4))
        if len(maps) == 1 or self.img is None:
            return [pt]
        b = self.img.bbox()
        center = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
        return [SC.mirrored(pt, center, m) for m in maps]

    def target(self, sp, dp):
        from ..core.document import Image
        cands = [it for it in self.c.selection if isinstance(it, Image) and 'galbe' in it.extra]
        hit = self.c.pick(sp)
        if isinstance(hit, Image) and 'galbe' in hit.extra:
            cands.insert(0, hit)
        for it in cands:
            b = it.bbox()
            if b[0] <= dp[0] <= b[2] and b[1] <= dp[1] <= b[3]:
                return it
        return None

    def press(self, sp, dp, ev):
        import numpy as np
        from ..core import galbe as GB, sculpt as SC
        from ..i18n import tr
        img = self.target(sp, dp)
        got = GB.decode(img) if img is not None else None
        if got is None:
            self.c.measured.emit(tr('SculptArt : cliquez sur un relief (galbe, dôme…) posé droit'))
            return
        if self.c.undo_push:
            self.c.undo_push()
        self.img, self.state, self.last = img, list(got), dp
        self.rng = np.random.default_rng()
        p = self.params()
        H, x0, y1, res = self.state
        self.mask = self._mask(p.get('mask', 'dedans'), H, x0, y1, res)
        self.H0 = H.copy() if self.mask is not None else None
        for q in self.copies(dp):
            SC.dab(H, x0, y1, res, q[0], q[1], float(p['radius']), float(p['strength']), p['brush'], self.rng)
        self._protect()
        self._refresh()

    def _mask(self, mode, H, x0, y1, res):
        """Zone où le pinceau agit (pochoir) : dans (ou hors) des formes fermées
        choisies avec le relief ; None : partout."""
        if mode not in ('dedans', 'dehors'):
            return None
        from ..cam import strategies as S
        from ..core import galbe as GB
        from .canvas import _leaves
        geoms = [g for it in _leaves(self.c.selection) if isinstance(it, Shape) and (g := S.item_geometry(it))]
        if not geoms:
            return None
        reg = S.region(geoms, 0.01)
        if reg is None or reg.is_empty:
            return None
        inside = GB._inside(reg, x0, y1, H.shape[1], H.shape[0], res)
        return inside if mode == 'dedans' else ~inside

    def _protect(self) -> None:
        import numpy as np
        if getattr(self, 'mask', None) is not None and self.state is not None:
            np.copyto(self.state[0], self.H0, where=~self.mask)

    def move(self, sp, dp, ev):
        from ..core import sculpt as SC
        self.pos = QPointF(sp)
        if self.img is not None and self.last is not None:
            p = self.params()
            H, x0, y1, res = self.state
            for a, b in zip(self.copies(self.last), self.copies(dp)):
                SC.stroke(H, x0, y1, res, a, b, float(p['radius']), float(p['strength']), p['brush'],
                          rng=self.rng)
            self._protect()
            self.last = dp
            self._refresh(throttle=True)
        self.c.overlay_update()

    def release(self, sp, dp, ev):
        if self.img is not None:
            self._refresh()
        self.img = self.state = self.last = None

    def _refresh(self, throttle: bool = False) -> None:
        """Image du relief refaite (au plus tous les 0,12 s pendant le geste)."""
        import time
        from ..core import galbe as GB
        if throttle and time.perf_counter() - self._shown < 0.12:
            return
        self._shown = time.perf_counter()
        H, x0, y1, res = self.state
        spec = GB.GalbeSpec.from_dict(self.img.extra.get('galbe') or {})
        new = GB.encode(H, x0, y1, res, spec, self.img.tool, self.img.name or 'Galbe')
        fn = getattr(self.c, 'relief_replace_fn', None)
        if fn is not None and fn(self.img, new):
            self.img = new

    def paint(self, p):
        if self.pos is None:
            return
        r = float(self.params()['radius']) * self.c.scale
        pen = _pen(_cc('selection'))
        pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(self.pos, r, r)

    def cancel(self):
        self.img = self.state = self.last = None


class MarkerTool(Tool):
    """Marqueur : chaque clic pose un repère de calage (croix et cercle) ;
    l'outil reste actif."""

    def press(self, sp, dp, ev):
        s = self.c.form_default('marker')              # aspect choisi (clic droit sur l'outil), éditable ensuite
        s.cx, s.cy, s.size = dp[0], dp[1], self.c.marker_size
        self.c.commit_form(s, back_to_select=False)


class Fillet2Tool(Tool):
    """Raccord entre deux traits (comme RACCORD en DAO) : clic sur le 1er
    trait, du côté à garder, puis sur le 2e — prolongés ou coupés et
    raccordés par un arc du rayon réglé (rayon 0 : coin vif). L'outil reste
    actif ; Maj au 2e clic : coin vif quel que soit le rayon."""
    cursor = Qt.CursorShape.PointingHandCursor

    def __init__(self, canvas, chamfer: bool = False):
        super().__init__(canvas)
        self.first = None
        self.chamfer = chamfer

    def press(self, sp, dp, ev):
        from ..i18n import tr
        hit = self.c.pick(sp)
        if not isinstance(hit, Shape) or not any(not c.closed for c in hit.path.contours):
            self.c.measured.emit(tr('Cliquez un trait ouvert'))
            return
        if self.first is None or self.first[0] is hit:
            self.first = (hit, dp)
            self.c.measured.emit(tr('Cliquez le second trait, du côté à garder'))
            return
        sharp = bool(ev is not None and ev.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        a, pa = self.first
        self.first = None
        if not self.c.fillet_two(a, pa, hit, dp, 0.0 if sharp else None, self.chamfer):
            self.c.measured.emit(tr('Raccord impossible (traits parallèles, courbes, ou rayon trop grand)'))

    def cancel(self):
        self.first = None


class CornerTool(Tool):
    """Coins réglables (d'après VectorCraft) : une poignée dans chaque angle des formes
    choisies. La tirer arrondit tous les coins choisis, ou tous ceux de la forme s'il n'y en
    a pas de choisi. Clic : choisir un coin (Ctrl : en ajouter) ; Alt+clic : arrondi, arrondi
    inversé, chanfrein ; double-clic : le rayon au clavier ; Suppr : coin vif ; Maj en
    tirant : par pas de 0,5 mm."""
    cursor = Qt.CursorShape.ArrowCursor
    HIT = 7.0               # rayon de prise d'une poignée (pixels)
    MIN_INSET = 10.0        # une poignée à au moins cette distance de son coin (pixels)
    MIN_SIDE = 30.0         # sous cette longueur de côté à l'écran, pas de poignée
    MAX_WIDGETS = 400
    MAX_SHAPES = 50

    def __init__(self, canvas):
        super().__init__(canvas)
        self.picked = set()         # (id de la forme, clé du coin)
        self.drag = None
        self.preview_paths = []
        self._memo = {}

    # --- ce qui est montré ------------------------------------------------------
    def shapes(self) -> list:
        from ..core import solids as SO
        out = [it for it in self.c.selection if isinstance(it, Shape) and it.path.contours and not SO.is_solid(it)]
        return out[:self.MAX_SHAPES]

    def zoom(self) -> float:
        a, b = self.c.to_screen(0.0, 0.0), self.c.to_screen(1.0, 0.0)
        return math.hypot(b.x() - a.x(), b.y() - a.y())

    def state(self, shape) -> tuple:
        """(tracé d'avant, rayons, sortes, coins) d'une forme, gardés tant qu'elle ne change pas."""
        from ..core import corners as CO
        sign = shape.path.digest()
        got = self._memo.get(id(shape))
        if got is None or got[0] != sign:
            base, radii, kinds = CO.live_of(shape)
            got = (sign, base, radii, kinds, CO.path_corners(base))
            if len(self._memo) > 2 * self.MAX_SHAPES:
                self._memo.clear()
            self._memo[id(shape)] = got
        return got[1:]

    def widgets(self) -> list:
        """[(forme, coin, rayon, sorte, position à l'écran)] des poignées qui se montrent."""
        zoom = self.zoom()
        out = []
        if zoom <= 0.0:
            return out
        for shape in self.shapes():
            _base, radii, kinds, corners = self.state(shape)
            for c in corners:
                if min(c.lu, c.lv) * zoom < self.MIN_SIDE:
                    continue
                r = c.fitted(radii.get(c.key, 0.0))
                k = max(r / c.sin, self.MIN_INSET / (zoom * math.sqrt(1.0 + c.cos)))
                k = min(k, min(c.lu, c.lv) / 2.0)
                out.append((shape, c, r, kinds.get(c.key, 'round'), self.c.to_screen(*c.on_bisector(k))))
                if len(out) >= self.MAX_WIDGETS:
                    return out
        return out

    def widget_at(self, sp):
        best, near = None, self.HIT
        for w in self.widgets():
            d = math.hypot(w[4].x() - sp.x(), w[4].y() - sp.y())
            if d <= near:
                best, near = w, d
        return best

    def targets(self, w=None) -> list:
        """[(forme, coin)] que le geste touche : les coins choisis, sinon tous ceux des formes choisies."""
        shapes = self.shapes()
        picks = [(s, c) for s in shapes for c in self.state(s)[3] if (id(s), c.key) in self.picked]
        if w is not None and picks and (id(w[0]), w[1].key) not in self.picked:
            return [(w[0], w[1])]
        return picks or [(s, c) for s in shapes for c in self.state(s)[3]]

    # --- ce qui change ----------------------------------------------------------
    def _outcome(self, targets, radius=None, kind=None) -> list:
        """[(forme, tracé, données)] avec ces coins à ce rayon ou de cette sorte."""
        from ..core import corners as CO
        by_shape = {}
        for s, c in targets:
            by_shape.setdefault(id(s), (s, []))[1].append(c)
        out = []
        for s, cs in by_shape.values():
            base, radii, kinds, _corners = self.state(s)
            radii, kinds = dict(radii), dict(kinds)
            for c in cs:
                if radius is not None:
                    radii[c.key] = c.fitted(radius)
                if kind is not None:
                    kinds[c.key] = kind
            out.append((s, *CO.settings(base, radii, kinds)))
        return out

    def _commit(self, outcome: list) -> None:
        from ..core import corners as CO
        if not outcome:
            return
        if self.c.undo_push:
            self.c.undo_push()
        for s, path, data in outcome:
            s.path = path
            s.extra = {k: v for k, v in s.extra.items() if k != CO.KEY}
            if data is not None:
                s.extra[CO.KEY] = data
        self.c.invalidate([o[0] for o in outcome])
        self.c.documentChanged.emit()
        self.c.update()

    def set_radius(self, radius: float, w=None) -> None:
        self._commit(self._outcome(self.targets(w), radius=max(0.0, radius)))

    def set_kind(self, kind: str, w=None) -> None:
        self._commit(self._outcome(self.targets(w), kind=kind))

    # --- les gestes -------------------------------------------------------------
    def press(self, sp, dp, ev):
        w = self.widget_at(sp)
        if w is None:
            self.picked.clear()
            hit = self.c.pick(sp)
            self.c.select([hit] if hit is not None else [])
            self.c.overlay_update()
            return
        mods = ev.modifiers() if ev is not None else Qt.KeyboardModifier.NoModifier
        if mods & Qt.KeyboardModifier.AltModifier:
            from ..core import corners as CO
            self.set_kind(CO.KINDS[(CO.KINDS.index(w[3]) + 1) % len(CO.KINDS)], w)
            return
        self.drag = {'w': w, 'from': dp, 'targets': self.targets(w), 'moved': False, 'sp': sp, 'outcome': None}

    def move(self, sp, dp, ev):
        if self.drag is None:
            return
        d = self.drag
        if not d['moved'] and math.hypot(sp.x() - d['sp'].x(), sp.y() - d['sp'].y()) < 3.0:
            return
        d['moved'] = True
        c = d['w'][1]
        r = max(0.0, d['w'][2] + c.radius_change(dp[0] - d['from'][0], dp[1] - d['from'][1]))
        if ev is not None and ev.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            r = round(r * 2.0) / 2.0
        d['outcome'] = self._outcome(d['targets'], radius=r)
        self.preview_paths = [o[1] for o in d['outcome']]
        from ..i18n import tr
        self.c.measured.emit(tr('Rayon : {0} mm').format(f'{c.fitted(r):.3f}'))
        self.c.overlay_update()

    def release(self, sp, dp, ev):
        d, self.drag = self.drag, None
        self.preview_paths = []
        if d is None:
            return
        if d['moved']:
            self._commit(d['outcome'] or [])
        else:                                               # un clic : choisir ce coin
            key = (id(d['w'][0]), d['w'][1].key)
            if _ctrl(ev):
                self.picked.symmetric_difference_update({key})
            else:
                self.picked = {key}
        self.c.overlay_update()

    def double(self, sp, dp, ev):
        from PySide6.QtWidgets import QInputDialog
        from ..i18n import tr
        w = self.widget_at(sp)
        if w is None:
            return
        v, ok = QInputDialog.getDouble(self.c, tr('Coins réglables'), tr('Rayon (mm)'), w[2], 0.0, 1e6, 3)
        if ok:
            self.set_radius(v, w)

    def wants_key(self, ev):
        return ev.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and bool(self.shapes())

    def key(self, ev):
        if ev.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and self.shapes():
            self.set_radius(0.0)
            return True
        if ev.key() == Qt.Key.Key_Escape and (self.picked or self.drag):
            self.cancel()
            self.c.overlay_update()
            return True
        return False

    def cancel(self):
        self.picked.clear()
        self.drag = None
        self.preview_paths = []

    def paint(self, p):
        from PySide6.QtGui import QColor
        for path in self.preview_paths:
            self.preview(p, path)
        for shape, c, _r, _kind, at in self.widgets():
            picked = (id(shape), c.key) in self.picked
            p.setPen(_pen(_cc('measure'), 1.2))
            p.setBrush(QColor(_cc('measure')) if picked else QColor('white'))
            p.drawEllipse(at, 3.5, 3.5)


class LetterTool(Tool):
    """Les lettres d'un texte, à la souris. Clic : choisir une lettre (Ctrl : en ajouter ou en retirer) ;
    glisser : la décaler ; flèches : décaler (Maj : cinq fois plus) ; Alt+flèches gauche et droite : crénage ;
    + et − : taille ; Page préc. et suiv. : rotation ; Suppr : remettre à la normale ; double-clic : la
    fenêtre Lettres. Mêmes réglages que cette fenêtre."""
    cursor = Qt.CursorShape.ArrowCursor
    KEY_STEP = 1.0      # % de la hauteur, comme la fenêtre Lettres
    ROT_STEP = 5.0      # degrés
    SIZE_STEP = 5.0     # %

    def __init__(self, canvas, open_dialog=None):
        super().__init__(canvas)
        self.open_dialog = open_dialog          # (exec_dialog, letter) : la fenêtre Lettres
        self.picked = set()
        self.drag = None
        self.hover = None
        self._memo = None

    # --- ce qui est montré ------------------------------------------------------
    def text(self):
        """Le texte en cours : seul choisi, et posé en ligne droite."""
        from ..core import text as TX
        got = [it for it in self.c.selection if isinstance(it, Text)]
        return got[0] if len(got) == 1 and len(self.c.selection) == 1 and TX.straight(got[0]) else None

    def letters(self, t=None) -> list:
        """[(position dans le texte, contours, boîte)] des lettres dessinées."""
        from ..core import text as TX
        t = t or self.text()
        if t is None:
            return []
        key = (id(t), id(t.outline))
        if self._memo is None or self._memo[0] != key:
            rows = [(i, path, path.bbox()) for i, path in TX.letter_outlines(t)]
            self._memo = (key, rows)
        return self._memo[1]

    def letter_at(self, dp) -> int | None:
        """La lettre sous le pointeur : à la distance de quelques pixels de sa boîte, celle dont le centre est le plus proche."""
        reach = 2.0 / max(self.c.scale, 1e-9)
        best, near = None, None
        for i, _path, box in self.letters():
            if box is None or not (box[0] - reach <= dp[0] <= box[2] + reach and box[1] - reach <= dp[1] <= box[3] + reach):
                continue
            d = math.hypot(dp[0] - (box[0] + box[2]) / 2.0, dp[1] - (box[1] + box[3]) / 2.0)
            if near is None or d < near:
                best, near = i, d
        return best

    # --- ce qui change ----------------------------------------------------------
    def _write(self, t, fx: dict, push: bool = True) -> None:
        from ..core import text as TX
        from ..core.document import drop_source_object
        if push and self.c.undo_push:
            self.c.undo_push()
        TX.set_char_fx(t, fx)
        t.outline = TX.outline_for(t)
        drop_source_object(t)
        self.c.invalidate([t])
        self.c.documentChanged.emit()
        self.c.update()

    def _to_percent(self, t, ddx: float, ddy: float) -> tuple:
        """Un écart sur le dessin, en % de la hauteur du texte le long de ses axes à lui (penché, tourné, étiré)."""
        from ..core import text as TX
        m = TX.text_matrix(t)
        det = m.a * m.d - m.b * m.c
        if abs(det) < 1e-12 or t.size <= 0.0:
            return 0.0, 0.0
        lx, ly = (m.d * ddx - m.c * ddy) / det, (m.a * ddy - m.b * ddx) / det
        return lx / (t.size * max(t.width_ratio, 1e-9)) * 100.0, ly / t.size * 100.0

    def change(self, keys: dict) -> None:
        """Ajoute `keys` (dx, dy, kern, rot : un écart ; h : un écart borné) aux lettres choisies, en une annulation."""
        from ..core import text as TX
        t = self.text()
        if t is None or not self.picked:
            return
        fx = {i: dict(f) for i, f in TX.char_fx(t).items()}
        for i in self.picked:
            f = fx.setdefault(i, {})
            for k, v in keys.items():
                f[k] = float(f.get(k, TX.CHAR_NEUTRAL[k])) + v
                if k == 'h':
                    f[k] = max(1.0, min(1000.0, f[k]))
        self._write(t, TX.clean_char_fx(fx))

    def reset(self) -> None:
        from ..core import text as TX
        t = self.text()
        if t is None or not self.picked:
            return
        fx = {i: dict(f) for i, f in TX.char_fx(t).items() if i not in self.picked}
        self._write(t, fx)

    # --- les gestes -------------------------------------------------------------
    def press(self, sp, dp, ev):
        from ..core import text as TX
        from ..i18n import tr
        i = self.letter_at(dp)
        if i is None:                                   # ailleurs : prendre ce qui s'y trouve, et la lettre si c'est un texte
            hit = self.c.pick(sp)
            self.picked = set()
            self.c.select([hit] if hit is not None else [])
            if isinstance(hit, Text) and not TX.straight(hit):
                self.c.measured.emit(tr('Ce texte suit une courbe : ses lettres se règlent avec Lettres…'))
            self.c.overlay_update()
            i = self.letter_at(dp)
            if i is None:
                return
        t = self.text()
        self.drag = {'text': t, 'letter': i, 'from': dp, 'sp': sp, 'moved': False, 'fx': {k: dict(f) for k, f in TX.char_fx(t).items()}}

    def move(self, sp, dp, ev):
        from ..core import text as TX
        if self.drag is None:
            new = self.letter_at(dp)
            if new != self.hover:
                self.hover = new
                self.c.overlay_update()
            return
        d = self.drag
        if not d['moved']:
            if math.hypot(sp.x() - d['sp'].x(), sp.y() - d['sp'].y()) < 3.0:
                return
            d['moved'] = True
            if d['letter'] not in self.picked:
                self.picked = {d['letter']}
            if self.c.undo_push:
                self.c.undo_push()
        px, py = self._to_percent(d['text'], dp[0] - d['from'][0], dp[1] - d['from'][1])
        fx = {k: dict(f) for k, f in d['fx'].items()}
        for i in self.picked:
            f = fx.setdefault(i, {})
            f['dx'] = float(f.get('dx', 0.0)) + px
            f['dy'] = float(f.get('dy', 0.0)) + py
        self._write(d['text'], TX.clean_char_fx(fx), push=False)

    def release(self, sp, dp, ev):
        d, self.drag = self.drag, None
        if d is None or d['moved']:
            self.c.overlay_update()
            return
        if _ctrl(ev):
            self.picked.symmetric_difference_update({d['letter']})
        else:
            self.picked = {d['letter']}
        self.c.overlay_update()

    def double(self, sp, dp, ev):
        i = self.letter_at(dp)
        if i is not None and self.open_dialog is not None:
            self.open_dialog(True, i)

    def wants_key(self, ev):
        k = Qt.Key
        return bool(self.picked) and self.text() is not None and ev.key() in (
            k.Key_Left, k.Key_Right, k.Key_Up, k.Key_Down, k.Key_Plus, k.Key_Minus, k.Key_PageUp, k.Key_PageDown,
            k.Key_Delete, k.Key_Backspace)

    def key(self, ev):
        k = Qt.Key
        key = ev.key()
        if key == k.Key_Escape and (self.picked or self.drag):
            self.cancel()
            self.c.overlay_update()
            return True
        if not self.wants_key(ev):
            return False
        step = self.KEY_STEP * (5.0 if ev.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1.0)
        if key in (k.Key_Left, k.Key_Right):
            sign = -1.0 if key == k.Key_Left else 1.0
            self.change({'kern' if ev.modifiers() & Qt.KeyboardModifier.AltModifier else 'dx': sign * step})
        elif key in (k.Key_Up, k.Key_Down):
            self.change({'dy': step if key == k.Key_Up else -step})
        elif key in (k.Key_Plus, k.Key_Minus):
            self.change({'h': self.SIZE_STEP if key == k.Key_Plus else -self.SIZE_STEP})
        elif key in (k.Key_PageUp, k.Key_PageDown):
            self.change({'rot': self.ROT_STEP if key == k.Key_PageUp else -self.ROT_STEP})
        else:
            self.reset()
        return True

    def cancel(self):
        self.picked = set()
        self.drag = None
        self.hover = None

    def paint(self, p):
        from PySide6.QtGui import QColor
        rows = self.letters()
        if not rows:
            return
        for i, path, _box in rows:
            if i in self.picked:
                self.preview(p, path, _cc('measure'))
            elif i == self.hover:
                self.preview(p, path, QColor(_cc('measure')).lighter(150).name())


class TrimTool(Tool):
    """Tronquer : clic sur le morceau de trait à supprimer (entre deux
    intersections). Prolonger : clic près du bout d'un trait ouvert, qui
    s'allonge jusqu'au premier objet rencontré. L'outil reste actif."""

    def __init__(self, canvas, mode: str = 'trim'):
        super().__init__(canvas)
        self.mode = mode

    def press(self, sp, dp, ev):
        if not self.c.trim_at(sp, dp, self.mode):
            from ..i18n import tr
            self.c.measured.emit(tr('Rien à tronquer ici') if self.mode == 'trim' else tr('Rien à atteindre dans cette direction'))


class ArrowTool(Tool):
    """Flèche à la souris (TypeEdit) : 1er clic la base de la queue, 2e la pointe, 3e la taille de la pointe, 4e l'épaisseur
    de la queue et la forme de la pointe (filaire : trois clics suffisent). Ctrl : pointe à 45°. Retour arrière : le clic
    précédent. F2 : `numeric()`, la fenêtre de la flèche."""

    def __init__(self, canvas, spec, numeric=None):
        super().__init__(canvas)
        self.spec = spec
        self.numeric = numeric
        self.pts: list = []
        self.hover = None
        self._say()

    @property
    def clicks(self) -> int:
        return 3 if self.spec.style == 'filaire' else 4

    def _say(self) -> None:
        from ..i18n import tr
        msg = (tr('Flèche : la base de la queue ; F2 : en chiffres'), tr('Flèche : la pointe'),
               tr('Flèche : la taille de la pointe'), tr('Flèche : l\'épaisseur de la queue'))
        self.c.measured.emit(msg[min(len(self.pts), 3)])

    def _point(self, dp, ev):
        return _snap45(self.pts[0], dp) if len(self.pts) == 1 and _ctrl(ev) else dp

    def press(self, sp, dp, ev):
        dp = self._point(dp, ev)
        if self.pts and geom.dist(self.pts[0], dp if len(self.pts) == 1 else self.pts[1]) < 1e-6:
            return                                     # pas de flèche sans longueur
        self.pts.append(dp)
        self._say()
        if len(self.pts) >= self.clicks:
            self._finish()
        self.c.overlay_update()

    def move(self, sp, dp, ev):
        self.hover = self._point(dp, ev) if self.pts else dp
        self.c.overlay_update()

    def _finish(self) -> None:
        from ..core.forms import arrow_from_clicks
        spec, pts = self.spec, self.pts
        self.pts, self.hover = [], None
        self.c.commit_form(arrow_from_clicks(spec, pts))

    def wants_key(self, ev) -> bool:
        return (ev.key() == Qt.Key.Key_F2 and self.numeric is not None) or (ev.key() == Qt.Key.Key_Backspace and bool(self.pts))

    def key(self, ev) -> bool:
        if not self.wants_key(ev):
            return False
        if ev.key() == Qt.Key.Key_F2:
            self.numeric()
        else:
            self.pts.pop()
            self._say()
            self.c.overlay_update()
        return True

    def cancel(self) -> None:
        self.pts, self.hover = [], None

    def paint(self, p):
        from ..core.forms import arrow_from_clicks
        pts = self.pts + ([self.hover] if self.hover is not None and self.pts else [])
        if len(pts) >= 2 and geom.dist(pts[0], pts[1]) > 1e-6:
            self.preview(p, arrow_from_clicks(self.spec, pts).build())


class MoveOnCurveTool(Tool):
    """Déplacer un texte sur sa courbe (TypeEdit) : il suit le pointeur le long de sa courbe, un clic le pose. F2 : la
    position en chiffres. `apply(delta)` décale les textes de delta mm ; `numeric()` ouvre la fenêtre."""

    def __init__(self, canvas, texts: list, apply, numeric):
        super().__init__(canvas)
        self.texts = texts
        self.apply = apply
        self.numeric = numeric
        self.last = None
        self.delta = 0.0
        self.curve = texts[0].extra['on_path']
        self.total = geom.walker(self.curve)[0]
        from ..i18n import tr
        self.c.measured.emit(tr('Déplacez le texte le long de la courbe et cliquez ; F2 : sa position en chiffres'))

    def move(self, sp, dp, ev):
        from ..core.text import curve_abscissa
        s = curve_abscissa(self.curve, dp)
        if self.last is not None:
            step = s - self.last
            if self.curve.closed and abs(step) > self.total / 2:        # le point de départ de la courbe est passé
                step -= math.copysign(self.total, step)
            self.delta += step
        self.last = s
        self.c.overlay_update()

    def press(self, sp, dp, ev):
        self.move(sp, dp, ev)
        delta, self.delta = self.delta, 0.0
        if abs(delta) > 1e-9:
            self.apply(delta)
        self.c.toolFinished.emit()

    def wants_key(self, ev) -> bool:
        return ev.key() == Qt.Key.Key_F2

    def key(self, ev) -> bool:
        if not self.wants_key(ev):
            return False
        self.numeric()
        self.c.toolFinished.emit()
        return True

    def cancel(self) -> None:
        self.last = None
        self.delta = 0.0

    def paint(self, p):
        from ..core.text import outline_moved_on_curve
        if self.last is None:
            return
        for t in self.texts:
            self.preview(p, outline_moved_on_curve(t, self.delta))


class ExtendArcTool(Tool):
    """Étendre en arc (TypeEdit) : un clic près du bout d'un arc de cercle, puis un clic vers le point à atteindre : le
    plus proche du pointeur parmi ceux que le cercle rencontre, le premier comme les suivants. L'outil reste actif."""

    def __init__(self, canvas):
        super().__init__(canvas)
        self.it = self.reach = None
        self.k = 0

    def press(self, sp, dp, ev):
        if self.reach is None:
            self._take(sp, dp)
        else:
            self._aim(dp)
            self._apply()
        self.c.overlay_update()

    def _take(self, sp, dp) -> None:
        from ..core import trim as TR
        from ..i18n import tr
        it = self.c.pick(sp)
        if not isinstance(it, Shape) or it.locked:
            self.c.measured.emit(tr('Cliquez sur le départ ou l\'arrivée d\'un arc de cercle'))
            return
        reach = TR.arc_targets(it.path, self.c.other_segments(it), dp)
        if reach is None:
            self.c.measured.emit(tr('Le contour à étendre doit être un arc.'))
            return
        if not reach.targets:
            self.c.measured.emit(tr('Rien à atteindre sur ce cercle'))
            return
        self.it, self.reach, self.k = it, reach, 0
        self.c.measured.emit(tr('Cliquez vers le point à atteindre : {0} sur ce cercle').format(len(reach.targets)))

    def _aim(self, dp) -> None:
        self.k = min(range(len(self.reach.targets)), key=lambda k: geom.dist(self.reach.targets[k][1], dp))

    def _apply(self) -> None:
        it, reach, k = self.it, self.reach, self.k
        self.cancel()
        new = reach.extended(it.path, k)
        if new is None:
            return
        if self.c.undo_push:
            self.c.undo_push()
        it.path = new
        self.c.invalidate([it])
        self.c.documentChanged.emit()
        self.c.update()

    def move(self, sp, dp, ev):
        if self.reach is not None:
            self._aim(dp)
            self.c.overlay_update()

    def cancel(self) -> None:
        self.it = self.reach = None
        self.k = 0

    def paint(self, p):
        if self.reach is None:
            return
        ext = self.reach.extension(self.k)
        if ext is not None:
            self.preview(p, Path([ext]))
        p.setPen(_pen(_cc('preview')))
        for _deg, q in self.reach.targets:
            p.drawEllipse(self.c.to_screen(*q), 4.0, 4.0)


class ContourMoveTool(Tool):
    """Déplacer un contour (TypeEdit) : glisser un contour d'un objet sans
    décombiner l'objet ; ses autres contours ne bougent pas. Contour de
    l'objet sélectionné d'abord, sinon de l'objet sous le curseur ; Ctrl :
    déplacement à 45°. Aperçu en pointillés pendant le glissé."""
    cursor = Qt.CursorShape.SizeAllCursor

    def __init__(self, canvas):
        super().__init__(canvas)
        self.hit = None                                   # (forme, indice du contour)
        self.start = None
        self.cur = None

    def find(self, sp, dp):
        """(forme, indice) du contour le plus proche du point, à quelques
        pixels près ; None sinon."""
        from .canvas import _leaves
        tol = SNAP_PX / self.c.scale
        cands = [s for s in _leaves(self.c.selection) if isinstance(s, Shape)]
        top = self.c.pick(sp)
        if top is not None:
            cands += [s for s in _leaves([top]) if isinstance(s, Shape) and all(s is not x for x in cands)]
        best = None
        for sh in cands:
            for ci, c in enumerate(sh.path.contours):
                if not c.segments:
                    continue
                b = c.bbox()
                if not (b[0] - tol <= dp[0] <= b[2] + tol and b[1] - tol <= dp[1] <= b[3] + tol):
                    continue
                for s in c.segments:
                    sb = s.bbox()
                    if not (sb[0] - tol <= dp[0] <= sb[2] + tol and sb[1] - tol <= dp[1] <= sb[3] + tol):
                        continue
                    _t, d = nodes.nearest_on_segment(s, dp)
                    if d < tol and (best is None or d < best[2]):
                        best = (sh, ci, d)
            if best is not None and best[0] is sh:
                break                                     # la sélection d'abord
        return best[:2] if best else None

    def _delta(self, ev=None):
        if self.start is None or self.cur is None:
            return 0.0, 0.0
        q = _snap45(self.start, self.cur) if ev is not None and _ctrl(ev) else self.cur
        return q[0] - self.start[0], q[1] - self.start[1]

    def press(self, sp, dp, ev):
        self.hit = self.find(sp, dp)
        if self.hit is None:
            from ..i18n import tr
            self.c.measured.emit(tr('Cliquez sur un contour et faites-le glisser'))
            return
        self.start = self.cur = dp

    def move(self, sp, dp, ev):
        if self.hit is not None:
            self.cur = dp
            dx, dy = self._delta(ev)
            from ..i18n import tr
            self.c.measured.emit(tr('Déplacement ΔX {0:.3f}   ΔY {1:.3f}').format(dx, dy))
            self.c.overlay_update()

    def release(self, sp, dp, ev):
        if self.hit is None:
            return
        self.cur = dp
        dx, dy = self._delta(ev)
        sh, ci = self.hit
        self.hit = self.start = self.cur = None
        if math.hypot(dx, dy) < 1e-12:
            return
        if self.c.undo_push:
            self.c.undo_push()
        cs = list(sh.path.contours)
        cs[ci] = cs[ci].transformed(geom.Affine.translation(dx, dy))
        sh.path = Path(cs)
        self.c.invalidate([sh])
        self.c.documentChanged.emit()
        self.c.update()

    def paint(self, p):
        if self.hit is None or self.cur is None:
            return
        sh, ci = self.hit
        dx, dy = self._delta()
        c = sh.path.contours[ci].transformed(geom.Affine.translation(dx, dy))
        from .canvas import to_qpath
        p.save()
        p.setTransform(self.c.view())
        p.setPen(_pen(_cc('preview'), 1, Qt.PenStyle.DashLine))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(to_qpath(Path([c])))
        p.restore()

    def cancel(self):
        self.hit = self.start = self.cur = None


def _put_contours(canvas, sh, ci: int, new: list, keep: bool) -> None:
    """Le contour ci de la forme remplacé par `new` ; s'il ne reste rien, la forme part. `keep` (Maj) : l'original reste."""
    from ..core.document import Group

    def holder(items):
        for it in items:
            if it is sh:
                return items
            if isinstance(it, Group):
                got = holder(it.children)
                if got is not None:
                    return got
        return None
    if canvas.undo_push:
        canvas.undo_push()
    items = next((got for got in (holder(L.items) for L in canvas.doc.layers) if got is not None), None)
    original = sh.clone() if keep else None
    cs = list(sh.path.contours)
    cs[ci:ci + 1] = new
    sh.path = Path(cs)
    if items is not None:
        at = next(i for i, it in enumerate(items) if it is sh)
        if original is not None:
            items.insert(at, original)
            at += 1
        if not cs:
            del items[at]
    if not cs:
        canvas.select([x for x in canvas.selection if x is not sh])
    canvas.invalidate()
    canvas.documentChanged.emit()
    canvas.update()


class ContourEraseTool(Tool):
    """Effacer un contour (TypeEdit) : un clic retire ce contour, sans décombiner l'objet ; Maj : l'original reste."""
    cursor = Qt.CursorShape.CrossCursor
    find = ContourMoveTool.find

    def __init__(self, canvas):
        super().__init__(canvas)
        self.over = None

    def move(self, sp, dp, ev):
        self.over = self.find(sp, dp)
        self.c.overlay_update()

    def press(self, sp, dp, ev):
        hit = self.find(sp, dp)
        self.over = None
        if hit is None:
            from ..i18n import tr
            self.c.measured.emit(tr('Cliquez sur le contour à effacer'))
            return
        _put_contours(self.c, hit[0], hit[1], [], _shift(ev))

    def paint(self, p):
        if self.over is not None:
            sh, ci = self.over
            if ci < len(sh.path.contours):
                self.preview(p, Path([sh.path.contours[ci]]), '#e00000')

    def cancel(self):
        self.over = None


class PortionTool(Tool):
    """Une portion de contour entre deux clics (TypeEdit) : Couper-supprimer, Transformer en segment, en arc, en courbe, en
    angle. Contour fermé : de l'un à l'autre dans le sens horaire, Tab : l'autre portion. Arc, courbe et angle se règlent
    ensuite à la souris, un dernier clic valide. Maj sur le dernier clic : l'original reste. Retour arrière : un pas en arrière."""
    cursor = Qt.CursorShape.CrossCursor
    find = ContourMoveTool.find

    def __init__(self, canvas, kind: str):
        super().__init__(canvas)
        self.kind = kind
        self.first = None                               # (forme, indice, contour, paramètre)
        self.second = None                              # paramètre du second point
        self.hover = None                               # paramètre sous le curseur, ou point de réglage
        self.over = None                                # (contour, paramètre) avant le premier clic
        self.flip = False

    def _on_contour(self, sp, dp):
        """(forme, indice, contour, paramètre) sous le curseur."""
        from ..core.trim import nearest_param
        hit = self.find(sp, dp)
        if hit is None:
            return None
        c = hit[0].path.contours[hit[1]]
        c = c.close() if c.closed else c
        return hit[0], hit[1], c, nearest_param(c, dp)[0]

    def _on_first(self, dp):
        """Le paramètre du point du contour choisi au premier clic, s'il est sous le curseur."""
        from ..core.trim import nearest_param
        g, d = nearest_param(self.first[2], dp)
        return g if d < SNAP_PX / self.c.scale else None

    def _span(self, b):
        from ..core import portion as P
        return P.span(self.first[2], self.first[3], b, not self.flip)

    def _result(self, h=None):
        """Le contour d'après, pour un second point donné."""
        from ..core import portion as P
        c = self.first[2]
        g0, g1 = self._span(self.second)
        if self.kind == 'delete':
            return P.delete(c, g0, g1)
        a, b = P.point_at(c, g0), P.point_at(c, g1)
        return [P.replace(c, g0, g1, P.new_segments(self.kind, a, b, h))]

    def move(self, sp, dp, ev):
        if self.first is None:
            got = self._on_contour(sp, dp)
            self.over = (got[2], got[3]) if got else None
        elif self.second is None:
            self.hover = self._on_first(dp)
        else:
            self.hover = dp
        self.c.overlay_update()

    def press(self, sp, dp, ev):
        from ..core import portion as P
        from ..i18n import tr
        if self.first is None:
            self.first = self._on_contour(sp, dp)
            self.over = self.hover = None
            self.flip = False
            self.c.measured.emit(tr('Cliquez sur le second point du même contour ; Tab : l\'autre portion')
                                 if self.first is not None else tr('Cliquez sur un contour'))
        elif self.second is None:
            g = self._on_first(dp)
            if g is None or geom.dist(P.point_at(self.first[2], g), P.point_at(self.first[2], self.first[3])) < 1e-6:
                self.c.measured.emit(tr('Cliquez sur un autre point du même contour'))
                return
            self.second = g
            self.hover = None
            if self.kind in P.SHAPED:
                self.c.measured.emit(tr('Réglez la forme à la souris, puis cliquez ; Tab : l\'autre portion'))
            else:
                self._commit(None, _shift(ev))
        else:
            self._commit(dp, _shift(ev))
        self.c.overlay_update()

    def _commit(self, h, keep: bool) -> None:
        sh, ci = self.first[0], self.first[1]
        new = self._result(h)
        self.first = self.second = self.hover = None
        _put_contours(self.c, sh, ci, new, keep)

    def wants_key(self, ev) -> bool:
        return self.first is not None and ev.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab, Qt.Key.Key_Backspace)

    def key(self, ev):
        if not self.wants_key(ev):
            return False
        if ev.key() == Qt.Key.Key_Backspace:
            if self.second is not None:
                self.second = None
            else:
                self.first = None
            self.hover = None
        else:
            self.flip = not self.flip
        self.c.overlay_update()
        return True

    def paint(self, p):
        from ..core import portion as P
        p.setPen(_pen('#e00000', 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        if self.first is None:
            if self.over is not None:
                p.drawEllipse(self.c.to_screen(*P.point_at(*self.over)), 5, 5)
            return
        c, a = self.first[2], self.first[3]
        p.drawEllipse(self.c.to_screen(*P.point_at(c, a)), 5, 5)
        if self.second is None:
            if self.hover is not None:
                p.drawEllipse(self.c.to_screen(*P.point_at(c, self.hover)), 5, 5)
                if geom.dist(P.point_at(c, self.hover), P.point_at(c, a)) > 1e-6:
                    self.preview(p, Path([P.portion(c, *self._span(self.hover))]), '#e00000')
            return
        p.drawEllipse(self.c.to_screen(*P.point_at(c, self.second)), 5, 5)
        g0, g1 = self._span(self.second)
        self.preview(p, Path([P.portion(c, g0, g1)]), '#e00000')
        if self.hover is not None:
            segs = P.new_segments(self.kind, P.point_at(c, g0), P.point_at(c, g1), self.hover)
            self.preview(p, Path([Contour(segs, False)]))

    def cancel(self):
        self.first = self.second = self.hover = self.over = None


class ShapeBuilderTool(Tool):
    """Concepteur de formes (comme dans les logiciels de dessin vectoriel) :
    glisser à travers les pièces des formes choisies qui se recouvrent les
    réunit ; clic sur une pièce : elle devient une forme à part ; Alt :
    supprime les pièces touchées."""
    cursor = Qt.CursorShape.CrossCursor

    def __init__(self, canvas):
        super().__init__(canvas)
        self.pts = []

    def press(self, sp, dp, ev):
        self.pts = [dp]
        self.alt = bool(ev is not None and ev.modifiers() & Qt.KeyboardModifier.AltModifier)

    def move(self, sp, dp, ev):
        if self.pts and ev is not None and ev.buttons() & Qt.MouseButton.LeftButton:
            if geom.dist(self.pts[-1], dp) * self.c.scale > 2:
                self.pts.append(dp)
                self.c.overlay_update()

    def release(self, sp, dp, ev):
        from ..i18n import tr
        if not self.pts:
            return
        pts, self.pts = self.pts, []
        fn = getattr(self.c.window(), 'shape_build', None)
        n = fn(pts, getattr(self, 'alt', False)) if fn else 0
        self.c.measured.emit(tr('{0} pièce(s) touchée(s)').format(n) if n else
                             tr('Choisissez des formes qui se recouvrent, puis glissez à travers leurs pièces'))
        self.c.overlay_update()

    def paint(self, p):
        if len(self.pts) >= 2:
            col = QColor(_cc('measure'))
            col.setAlpha(160)
            p.setPen(_pen(col, 3))
            for a, b in zip(self.pts, self.pts[1:]):
                p.drawLine(self.c.to_screen(*a), self.c.to_screen(*b))

    def cancel(self):
        self.pts = []


class BoundaryTool(Tool):
    """Contour de zone (comme CONTOUR en DAO) : chaque clic dans une zone
    fermée par des traits crée la forme de cette zone (îlots en trous ;
    Maj : sans les îlots). Échap : fin."""
    cursor = Qt.CursorShape.PointingHandCursor

    def press(self, sp, dp, ev):
        from ..i18n import tr
        shift = bool(ev is not None and ev.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        sh = self.c.boundary_at(dp, islands=not shift)
        self.c.measured.emit(tr('Contour de zone créé') if sh is not None else tr('Aucune zone fermée ici'))


class ScaleRefTool(Tool):
    """Échelle par référence (comme ÉCHELLE ▸ Référence en DAO) : 1er clic =
    point de base (fixe) et début de la longueur de référence, 2e clic = sa
    fin ; 3e clic : la nouvelle longueur va du point de base à ce point —
    ou Entrée après deux clics : la nouvelle longueur est saisie. La
    sélection est mise à l'échelle autour du point de base."""
    cursor = Qt.CursorShape.CrossCursor

    def __init__(self, canvas):
        super().__init__(canvas)
        self.pts = []
        self.cur = None

    def press(self, sp, dp, ev):
        from ..i18n import tr
        if not self.c.selection:
            self.c.measured.emit(tr('Sélectionnez d\'abord les objets à mettre à l\'échelle'))
            return
        self.pts.append(dp)
        if len(self.pts) == 1:
            self.c.measured.emit(tr('Cliquez la fin de la longueur de référence'))
        elif len(self.pts) == 2:
            if geom.dist(*self.pts) < 1e-9:
                self.pts.pop()
                return
            self.c.measured.emit(tr('Cliquez la nouvelle longueur (depuis le point de base), ou Entrée pour la saisir'))
        else:
            self.apply(geom.dist(self.pts[0], self.pts[2]))
        self.c.overlay_update()

    def apply(self, new_len: float) -> None:
        from ..i18n import tr
        base, ref = self.pts[0], geom.dist(self.pts[0], self.pts[1])
        self.pts, self.cur = [], None
        if ref < 1e-9 or new_len <= 1e-9:
            return
        k = new_len / ref
        m = geom.Affine.translation(base[0], base[1]) @ geom.Affine.scaling(k) @ \
            geom.Affine.translation(-base[0], -base[1])
        self.c.transform_selection(m)
        self.c.measured.emit(tr('Échelle × {0}').format(f'{k:.6g}'))
        self.c.toolFinished.emit()

    def key(self, ev):
        if ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and len(self.pts) == 2:
            fn = getattr(self.c, 'ask_length_fn', None)
            v = fn(geom.dist(*self.pts)) if fn is not None else None
            if v:
                self.apply(float(v))
            return True
        return False

    def move(self, sp, dp, ev):
        if self.pts:
            self.cur = dp
            self.c.overlay_update()

    def paint(self, p):
        if not self.pts:
            return
        p.setPen(_pen(_cc('measure'), 1.5))
        a = self.c.to_screen(*self.pts[0])
        p.drawEllipse(a, 4, 4)
        pts = self.pts[1:] + ([self.cur] if self.cur is not None else [])
        for q in pts[:2]:
            p.drawLine(a, self.c.to_screen(*q))

    def cancel(self):
        self.pts, self.cur = [], None


class RotateRefTool(ScaleRefTool):
    """Rotation par référence (comme ROTATION ▸ Référence en DAO) : 1er clic
    = centre de rotation, 2e clic = direction de référence (un bord de
    l'objet), 3e clic = direction voulue — ou Entrée après deux clics :
    l'angle voulu est saisi (0 : horizontal). Repérage polaire (Maj+F12) utile."""

    def press(self, sp, dp, ev):
        from ..i18n import tr
        if not self.c.selection:
            self.c.measured.emit(tr('Sélectionnez d\'abord les objets à faire tourner'))
            return
        self.pts.append(dp)
        if len(self.pts) == 1:
            self.c.measured.emit(tr('Cliquez la direction de référence'))
        elif len(self.pts) == 2:
            if geom.dist(*self.pts) < 1e-9:
                self.pts.pop()
                return
            self.c.measured.emit(tr('Cliquez la nouvelle direction, ou Entrée pour saisir l\'angle'))
        else:
            if geom.dist(self.pts[0], self.pts[2]) < 1e-9:
                self.pts.pop()
                return
            c, r, n = self.pts
            self.rotate(math.degrees(math.atan2(n[1] - c[1], n[0] - c[0])))
        self.c.overlay_update()

    def rotate(self, new_deg: float) -> None:
        from ..i18n import tr
        c, r = self.pts[0], self.pts[1]
        ref = math.degrees(math.atan2(r[1] - c[1], r[0] - c[0]))
        self.pts, self.cur = [], None
        a = (new_deg - ref + 180.0) % 360.0 - 180.0
        self.c.transform_selection(geom.Affine.rotation(a, c))
        self.c.measured.emit(tr('Rotation de {0}°').format(f'{a:.4g}'))
        self.c.toolFinished.emit()

    def key(self, ev):
        if ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and len(self.pts) == 2:
            fn = getattr(self.c, 'ask_angle_fn', None)
            v = fn() if fn is not None else None
            if v is not None:
                self.rotate(float(v))
            return True
        return False


class ReliefProbeTool(Tool):
    """Sonde de relief (TypeEdit : outils de mesure TypeArt) : clic sur un
    relief = sa cote Z en ce point ; second clic = profil du premier point à
    celui-ci (cotes mini et maxi, pente la plus forte). L'outil reste actif."""
    cursor = Qt.CursorShape.CrossCursor

    def __init__(self, canvas):
        super().__init__(canvas)
        self.a = None
        self.img = None
        self.cur = None

    def _relief_at(self, dp):
        from ..core.document import Image
        for it in reversed([x for L in self.c.doc.layers if self.c.layer_shown(L) for x in L.items]):
            if isinstance(it, Image) and 'galbe' in it.extra:
                b = it.bbox()
                if b[0] <= dp[0] <= b[2] and b[1] <= dp[1] <= b[3]:
                    return it
        return None

    def press(self, sp, dp, ev):
        from ..core import relief_ops as R
        from ..i18n import tr
        img = self.img if self.a is not None else self._relief_at(dp)
        if img is None:
            self.c.measured.emit(tr('Cliquez sur un relief'))
            return
        if self.a is None:
            z = R.z_at(img, *dp)
            self.a, self.img = dp, img
            self.c.measured.emit(tr('Z = {0} mm en X {1}, Y {2} — second clic : profil').format(
                f'{z:.3f}' if z is not None else '?', f'{dp[0]:.2f}', f'{dp[1]:.2f}'))
            return
        prof = R.profile(img, self.a, dp)
        self.a, self.img, self.cur = None, None, None
        if len(prof) < 2:
            return
        zs = [z for _d, z in prof]
        slope = max((abs(z1 - z0) / max(d1 - d0, 1e-9) for (d0, z0), (d1, z1) in zip(prof, prof[1:])), default=0.0)
        self.c.measured.emit(tr('Profil sur {0} mm : Z de {1} à {2} mm, pente maxi {3}°').format(
            f'{prof[-1][0]:.2f}', f'{min(zs):.3f}', f'{max(zs):.3f}', f'{math.degrees(math.atan(slope)):.1f}'))
        self.c.overlay_update()

    def move(self, sp, dp, ev):
        if self.a is not None:
            self.cur = dp
            self.c.overlay_update()

    def paint(self, p):
        if self.a is None or self.cur is None:
            return
        p.setPen(_pen(_cc('measure'), 1.5))
        p.drawLine(self.c.to_screen(*self.a), self.c.to_screen(*self.cur))

    def cancel(self):
        self.a, self.img, self.cur = None, None, None


class FreeDuplicateTool(Tool):
    """Duplication libre (TypeEdit) : la sélection suit le pointeur en
    pointillés ; chaque clic pose une copie (centre de la sélection au point
    cliqué, accrochage F3 compris) ; glisser : la copie suit le point saisi,
    F2 sans relâcher : ce point en chiffres. Ctrl, ou Ctrl en lançant l'outil :
    seulement à l'horizontale ou à la verticale. Échap : fin."""
    cursor = Qt.CursorShape.CrossCursor
    f2_dialog = 'free_copy_dialog'

    def __init__(self, canvas, constrain: bool = False):
        super().__init__(canvas)
        self.constrain = constrain
        self.down = self.down_sp = None
        from .canvas import item_path
        self.items = list(self.c.selection)
        bb = geom.bbox_union(it.bbox() for it in self.items) if self.items else None
        self.center = ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2) if bb else None
        self.outline = Path([c for it in self.items for leaf in _leaves_of(it)
                             if (pp := item_path(leaf)) for c in pp.contours])
        self.hover = None

    def grip(self):
        """Le point de la sélection qui suit le pointeur."""
        return self.down if self.down is not None else self.center

    def _aim(self, dp, ev):
        if self.center is None or not (self.constrain or _ctrl(ev)):
            return dp
        ref = self.grip()
        return (dp[0], ref[1]) if abs(dp[0] - ref[0]) >= abs(dp[1] - ref[1]) else (ref[0], dp[1])

    def move(self, sp, dp, ev):
        self.hover = self._aim(dp, ev)
        self.c.overlay_update()

    def press(self, sp, dp, ev):
        from ..i18n import tr
        if self.center is None:
            self.c.measured.emit(tr('Sélectionnez d\'abord les objets à dupliquer'))
            return
        self.down, self.down_sp = dp, sp

    def release(self, sp, dp, ev):
        if self.down is None:
            return
        moved = geom.dist(self.down, dp) * self.c.scale > 3.0
        grip = self.down if moved else self.center
        target = self._aim(dp, ev) if moved else dp
        self.down = self.down_sp = None
        self.place(target, grip)

    def place(self, target, grip=None) -> None:
        from ..i18n import tr
        grip = self.center if grip is None else grip
        n = self.c.place_copies(self.items, target[0] - grip[0], target[1] - grip[1])
        self.c.measured.emit(tr('Copie posée ({0} objet(s)) — Échap : fin').format(n))

    def cancel(self):
        self.down = self.down_sp = None

    def paint(self, p):
        if self.hover is not None and self.center is not None and self.outline.contours:
            g = self.grip()
            m = geom.Affine.translation(self.hover[0] - g[0], self.hover[1] - g[1])
            self.preview(p, self.outline.transformed(m))


class ArrayDragTool(Tool):
    """Duplication linéaire ou circulaire à la souris (TypeEdit) : glisser, les copies s'affichent en pointillés, relâcher pose.
    Linéaire : le geste donne le pas entre deux copies ; Tab : la dernière copie va au pointeur. Circulaire : le geste
    finit au centre du cercle (accrochage F3 compris). F2 : les mêmes réglages en chiffres. Échap : abandon."""
    cursor = Qt.CursorShape.CrossCursor
    f2_dialog = 'array_dialog'
    MAX_PREVIEW = 5000                                  # au-delà, les copies s'affichent par leur boîte

    def __init__(self, canvas, mode: str, cols: int = 2, rows: int = 1, rotate: bool = True):
        super().__init__(canvas)
        from .canvas import item_path
        self.mode, self.cols, self.rows, self.rotate = mode, max(1, cols), max(1, rows), rotate
        self.items = list(self.c.selection)
        self.parts = []
        for it in self.items:
            path = Path([c for leaf in _leaves_of(it) if (pp := item_path(leaf)) for c in pp.contours])
            bb = it.bbox()
            if path.contours and bb:
                self.parts.append((path, ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)))
        bb = geom.bbox_union(it.bbox() for it in self.items) if self.items else None
        self.center = ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2) if bb else None
        self.down = self.hover = None
        self.to_last = False

    def steps(self, a, b) -> tuple:
        """Le pas (X, Y) pour un geste de a à b."""
        dx, dy = b[0] - a[0], b[1] - a[1]
        if not self.to_last:
            return dx, dy
        if self.cols > 1 and self.rows > 1:
            return dx / (self.cols - 1), dy / (self.rows - 1)
        return dx / max(self.cols - 1, self.rows - 1, 1), dy / max(self.cols - 1, self.rows - 1, 1)

    def values(self, a, b) -> dict:
        """Les réglages de la commande Dupliquer pour ce geste."""
        if self.mode == 'circular':
            return {'mode': 'circular', 'ci_n': self.cols, 'center': b, 'ci_angle': 360.0, 'rotate': self.rotate}
        sx, sy = self.steps(a, b)
        if self.cols > 1 and self.rows > 1:
            return {'mode': 'grid', 'gr_cols': self.cols, 'gr_rows': self.rows, 'gr_dx': sx, 'gr_dy': sy}
        return {'mode': 'linear', 'lin_n': max(self.cols, self.rows) - 1, 'lin_dx': sx, 'lin_dy': sy}

    def matrices(self, a, b, pivot) -> list:
        """Le déplacement de chaque copie, pour un objet centré sur `pivot`."""
        m = geom.Affine
        if self.mode == 'circular':
            out = []
            for k in range(1, self.cols):
                rot = m.rotation(360.0 * k / self.cols, b)
                if self.rotate:
                    out.append(rot)
                else:
                    q = rot.apply(pivot)
                    out.append(m.translation(q[0] - pivot[0], q[1] - pivot[1]))
            return out
        sx, sy = self.steps(a, b)
        if self.cols > 1 and self.rows > 1:
            return [m.translation(i * sx, j * sy) for j in range(self.rows) for i in range(self.cols) if (i, j) != (0, 0)]
        return [m.translation(k * sx, k * sy) for k in range(1, max(self.cols, self.rows))]

    def press(self, sp, dp, ev):
        from ..i18n import tr
        if not self.parts:
            self.c.measured.emit(tr('Sélectionnez d\'abord les objets à dupliquer'))
            return
        self.down = self.hover = dp

    def move(self, sp, dp, ev):
        from ..i18n import tr
        if self.down is None:
            return
        self.hover = _snap45(self.down, dp) if _ctrl(ev) and self.mode != 'circular' else dp
        if self.mode == 'circular':
            self.c.measured.emit(tr('Rayon {0:.3f} mm').format(geom.dist(self.center, self.hover)))
        else:
            self.c.measured.emit(tr('Pas {0:.3f} ; {1:.3f} mm').format(*self.steps(self.down, self.hover)))
        self.c.overlay_update()

    def release(self, sp, dp, ev):
        from ..i18n import tr
        if self.down is None:
            return
        a, b = self.down, (_snap45(self.down, dp) if _ctrl(ev) and self.mode != 'circular' else dp)
        self.down = self.hover = None
        if geom.dist(a, b) * self.c.scale < 3.0:
            self.c.measured.emit(tr('Glissez pour placer les copies, ou F2 pour les chiffres'))
            self.c.overlay_update()
            return
        fn = getattr(self.c, 'duplicate_fn', None)
        if fn is not None:
            fn(self.values(a, b))
        self.c.toolFinished.emit()

    def wants_key(self, ev) -> bool:
        return self.mode == 'linear' and ev.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab)

    def key(self, ev):
        from ..i18n import tr
        if not self.wants_key(ev):
            return False
        self.to_last = not self.to_last
        self.c.measured.emit(tr('La dernière copie va au pointeur') if self.to_last else tr('Le geste donne le pas entre deux copies'))
        self.c.overlay_update()
        return True

    def paint(self, p):
        if self.down is None or self.hover is None:
            return
        many = sum(len(path.contours) for path, _c in self.parts) * max(self.cols * self.rows, 1) > self.MAX_PREVIEW
        for path, pivot in self.parts:
            shown = path
            if many:
                x0, y0, x1, y1 = path.bbox()
                shown = Path([geom.rect(x0, y0, x1 - x0, y1 - y0)])
            for m in self.matrices(self.down, self.hover, pivot):
                self.preview(p, shown.transformed(m))

    def cancel(self):
        self.down = self.hover = None


def _leaves_of(it):
    from .canvas import _leaves
    return list(_leaves([it]))


class KnifeLineTool(Tool):
    """Couper un contour (TypeEdit) : glisser un trait à travers des contours, ouverts ou fermés. Ils sont coupés à chaque
    intersection et rien ne bouge (canvas.knife_fn) ; Tab ou Maj : les contours fermés sont refermés le long du trait.
    Ctrl : à 45°."""
    cursor = Qt.CursorShape.CrossCursor

    def __init__(self, canvas):
        super().__init__(canvas)
        self.a = self.b = None
        self.closing = False
        self.marks = []

    def press(self, sp, dp, ev):
        self.a, self.b = dp, dp
        self.marks = []

    def move(self, sp, dp, ev):
        if self.a is not None:
            self.b = _snap45(self.a, dp) if _ctrl(ev) else dp
            fn = getattr(self.c, 'knife_marks_fn', None)
            self.marks = fn(self.a, self.b, self.closing or _shift(ev)) if fn is not None else []
            self.c.overlay_update()

    def wants_key(self, ev) -> bool:
        return ev.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab)

    def key(self, ev):
        from ..i18n import tr
        if not self.wants_key(ev):
            return False
        self.closing = not self.closing
        self.c.measured.emit(tr('Les contours fermés seront refermés le long du trait') if self.closing
                             else tr('Les contours seront seulement coupés'))
        self.c.overlay_update()
        return True

    def release(self, sp, dp, ev):
        from ..i18n import tr
        if self.a is None:
            return
        a, b = self.a, (_snap45(self.a, dp) if _ctrl(ev) else dp)
        closing = self.closing or _shift(ev)
        self.a = self.b = None
        self.marks = []
        self.closing = False                            # Tab vaut pour ce trait
        fn = getattr(self.c, 'knife_fn', None)
        n = fn(a, b, closing) if fn is not None else 0
        self.c.measured.emit(tr('{0} morceau(x)').format(n) if n else tr('Le trait ne coupe aucun contour'))
        self.c.overlay_update()

    def paint(self, p):
        if self.a is not None and self.b is not None:
            self.preview(p, Path([geom.polyline([self.a, self.b])]), QColor(220, 60, 40))
        p.setPen(_pen('#e00000', 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for q in self.marks:                            # les points de découpe : doubles carrés, comme TypeEdit
            s = self.c.to_screen(*q)
            p.drawRect(int(s.x()) - 5, int(s.y()) - 5, 10, 10)
            p.drawRect(int(s.x()) - 2, int(s.y()) - 2, 4, 4)

    def cancel(self):
        self.a = self.b = None
        self.closing = False
        self.marks = []


class TabTool(Tool):
    """Pontets à la main (TypeEdit : ajouter des ponts) : un clic près du
    contour d'une forme fermée y pose un pontet (repère gardé sur la forme,
    extra['tabs_xy'], pris par le détourage) ; un clic sur un pontet l'ôte."""
    cursor = Qt.CursorShape.CrossCursor

    def press(self, sp, dp, ev):
        from ..i18n import tr
        got = self.c.toggle_tab(dp)
        if got is not None:
            self.c.measured.emit(tr('Pontet posé') if got else tr('Pontet ôté'))
        self.c.overlay_update()

    def paint(self, p):
        r = 4.0 / max(self.c.scale, 1e-9)
        marks = [geom.rect(x - r, y - r, 2 * r, 2 * r) for x, y in self.c.tab_marks()]
        if marks:
            self.preview(p, Path(marks), QColor(30, 140, 255))


class LeadTool(Tool):
    """Entrée et sortie d'un contour (TypeEdit : Ponts et E/S tangentielles manuels) : un clic près d'un contour fermé y met le
    départ et demande ses valeurs (repère gardé sur la forme, extra['lead_xy']) ; un clic sur un repère les change ou l'ôte."""
    cursor = Qt.CursorShape.CrossCursor

    def __init__(self, canvas, ask):
        super().__init__(canvas)
        self.ask = ask

    def press(self, sp, dp, ev):
        self.ask(dp)
        self.c.overlay_update()

    def paint(self, p):
        r = 4.0 / max(self.c.scale, 1e-9)
        marks = [geom.circle((x, y), r) for x, y in self.c.lead_marks()]
        if marks:
            self.preview(p, Path(marks), QColor(30, 170, 80))


class PickPointTool(Tool):
    """Un clic (accroché) donne un point à `callback(point)`, puis l'outil
    rend la main — copier avec point de base, coller au point."""
    cursor = Qt.CursorShape.CrossCursor

    def __init__(self, canvas, callback, prompt: str = ''):
        super().__init__(canvas)
        self.callback = callback
        if prompt:
            self.c.measured.emit(prompt)

    def press(self, sp, dp, ev):
        cb, self.callback = self.callback, None
        if cb is not None:
            cb(dp)
        self.c.toolFinished.emit()


class DragRectTool(Tool):
    """Glisser un rectangle (accroché) donne ses bornes à `callback(box)`, puis l'outil rend la main ; F2 : `numeric()`
    le rend en chiffres, ou None pour continuer à la souris. Un simple clic ne fait rien : on glisse."""
    cursor = Qt.CursorShape.CrossCursor
    #: en dessous (mm), ce n'est pas un rectangle
    MIN_SIZE = 0.01

    def __init__(self, canvas, callback, numeric=None, prompt: str = ''):
        super().__init__(canvas)
        self.callback = callback
        self.numeric = numeric
        self.a = self.b = None
        if prompt:
            self.c.measured.emit(prompt)

    def press(self, sp, dp, ev):
        self.a = self.b = dp

    def move(self, sp, dp, ev):
        if self.a is not None:
            self.b = dp
            self.c.overlay_update()

    def release(self, sp, dp, ev):
        if self.a is None:
            return
        a, self.a = self.a, None
        self.b = None
        self.c.overlay_update()
        if abs(dp[0] - a[0]) >= self.MIN_SIZE and abs(dp[1] - a[1]) >= self.MIN_SIZE:
            self._finish((min(a[0], dp[0]), min(a[1], dp[1]), max(a[0], dp[0]), max(a[1], dp[1])))

    def _finish(self, box) -> None:
        cb, self.callback = self.callback, None
        self.c.toolFinished.emit()
        if cb is not None:
            cb(box)

    def wants_key(self, ev) -> bool:
        return ev.key() == Qt.Key.Key_F2 and self.numeric is not None

    def key(self, ev) -> bool:
        if not self.wants_key(ev):
            return False
        box = self.numeric()
        if box is not None:
            self._finish(box)
        return True

    def cancel(self) -> None:
        self.a = self.b = None
        self.callback = None

    def paint(self, p):
        if self.a is not None and self.b is not None:
            x0, x1 = sorted((self.a[0], self.b[0]))
            y0, y1 = sorted((self.a[1], self.b[1]))
            self.preview(p, Path([geom.rect(x0, y0, x1 - x0, y1 - y0)]))


class PlaceGroupTool(Tool):
    """Poser un dessin d'un clic (bibliothèque) : son contour suit le pointeur
    en pointillés, centré dessus (accrochage F3 compris) ; R (Maj+R) le tourne
    de 90° ; le clic donne le point et la rotation à `callback(point, angle)`
    (ou `callback(point)` sans rotation) ; Échap : rien n'est posé."""
    cursor = Qt.CursorShape.CrossCursor
    #: au-delà, le contour suivi est le cadre du dessin (repeint fluide sur les très gros dessins)
    OUTLINE_LEAVES = 2000

    def __init__(self, canvas, group, callback, prompt: str = ''):
        super().__init__(canvas)
        from .canvas import item_path
        self.callback = callback
        bb = group.bbox()
        self.center = ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2) if bb else (0.0, 0.0)
        leaves = _leaves_of(group)
        if len(leaves) > self.OUTLINE_LEAVES and bb:
            self.outline = Path([geom.rect(bb[0], bb[1], bb[2] - bb[0], bb[3] - bb[1])])
        else:
            self.outline = Path([c for leaf in leaves if (pp := item_path(leaf)) for c in pp.contours])
        self.hover = None
        self.angle = 0.0
        if prompt:
            self.c.measured.emit(prompt)

    def move(self, sp, dp, ev):
        self.hover = dp
        self.c.overlay_update()

    def wants_key(self, ev) -> bool:
        return ev.key() == Qt.Key.Key_R                  # R : avant le raccourci du rectangle

    def key(self, ev) -> bool:
        if ev.key() != Qt.Key.Key_R:
            return False
        shift = bool(ev.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        self.angle = (self.angle + (-90.0 if shift else 90.0)) % 360.0
        self.c.overlay_update()
        return True

    def rotation(self) -> geom.Affine:
        """Rotation choisie (R), autour du centre du dessin."""
        cx, cy = self.center
        return geom.Affine.translation(cx, cy) @ geom.Affine.rotation(self.angle) @ geom.Affine.translation(-cx, -cy)

    def press(self, sp, dp, ev):
        cb, self.callback = self.callback, None
        if cb is not None:
            if self.angle:
                cb(dp, self.angle)
            else:
                cb(dp)
        self.c.toolFinished.emit()

    def paint(self, p):
        if self.hover is not None and self.outline.contours:
            m = geom.Affine.translation(self.hover[0] - self.center[0], self.hover[1] - self.center[1])
            self.preview(p, self.outline.transformed(m @ self.rotation()))


class ShaperTool(Tool):
    """Crayon / Shaper : glisser pour dessiner à main levée ; au lâcher, le
    tracé devient la forme qu'il esquisse (trait, rectangle, ellipse ou
    cercle, triangle), sinon une courbe lissée. Maj au lâcher : courbe
    lissée seulement."""
    cursor = Qt.CursorShape.CrossCursor

    def __init__(self, canvas):
        super().__init__(canvas)
        self.pts = []

    def press(self, sp, dp, ev):
        self.pts = [dp]

    def move(self, sp, dp, ev):
        if self.pts and ev is not None and ev.buttons() & Qt.MouseButton.LeftButton:
            if geom.dist(self.pts[-1], dp) * self.c.scale > 1.5:
                self.pts.append(dp)
                self.c.overlay_update()

    def release(self, sp, dp, ev):
        from ..core import shaper as SH
        from ..core.fitcurve import approximate
        from ..i18n import tr
        pts, self.pts = self.pts + [dp], []
        if len(pts) < 3:
            return
        if ev is not None and ev.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            kind, path = 'courbe', approximate(Path([geom.polyline(pts)]), tol=0.05)
        else:
            kind, path = SH.recognize(pts)
        if path.contours:
            self.c.commit_shape(path, back_to_select=False)
            self.c.measured.emit({'trait': tr('Trait'), 'rectangle': tr('Rectangle'), 'ellipse': tr('Ellipse'),
                                  'triangle': tr('Triangle'), 'courbe': tr('Courbe')}.get(kind, kind))
        self.c.overlay_update()

    def paint(self, p):
        if len(self.pts) >= 2:
            p.setPen(_pen(_cc('measure'), 1.5))
            for a, b in zip(self.pts, self.pts[1:]):
                p.drawLine(self.c.to_screen(*a), self.c.to_screen(*b))

    def cancel(self):
        self.pts = []


class EraserTool(Tool):
    """Gomme : glisser efface ce que couvre la gomme ronde (formes de la
    sélection, sinon toutes) ; rayon : canvas.eraser_radius (crochets [ ]
    pour le changer). Un passage = une annulation."""
    cursor = Qt.CursorShape.CrossCursor

    def __init__(self, canvas):
        super().__init__(canvas)
        self.pts = []
        self.hover = None

    def press(self, sp, dp, ev):
        self.pts = [dp]

    def move(self, sp, dp, ev):
        self.hover = dp
        if self.pts and ev is not None and ev.buttons() & Qt.MouseButton.LeftButton:
            if geom.dist(self.pts[-1], dp) * self.c.scale > 1.5:
                self.pts.append(dp)
        self.c.overlay_update()

    def release(self, sp, dp, ev):
        from ..i18n import tr
        pts, self.pts = self.pts + [dp], []
        n = self.c.erase(pts, getattr(self.c, 'eraser_radius', 1.0))
        self.c.measured.emit(tr('{0} objet(s) gommé(s)').format(n) if n else tr('Rien sous la gomme'))
        self.c.overlay_update()

    def key(self, ev):
        if ev.key() in (Qt.Key.Key_BracketLeft, Qt.Key.Key_BracketRight):
            r = getattr(self.c, 'eraser_radius', 1.0)
            self.c.eraser_radius = max(0.05, r / 1.25 if ev.key() == Qt.Key.Key_BracketLeft else r * 1.25)
            self.c.overlay_update()
            return True
        return False

    def paint(self, p):
        r = getattr(self.c, 'eraser_radius', 1.0) * self.c.scale
        p.setPen(_pen(_cc('measure'), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for q in self.pts[-1:] or ([self.hover] if self.hover is not None else []):
            p.drawEllipse(self.c.to_screen(*q), r, r)
        if len(self.pts) >= 2:
            col = QColor(_cc('measure'))
            col.setAlpha(70)
            pen = QPen(col, 2 * r)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            for a, b in zip(self.pts, self.pts[1:]):
                p.drawLine(self.c.to_screen(*a), self.c.to_screen(*b))

    def cancel(self):
        self.pts = []


class PunchTool(Tool):
    """Emporte-pièce (demande du 18/11) : un clic retire d'un contour une longueur donnée (segment : centrée sur le
    point cliqué, mesurée le long du contour), ou ce que couvre un rectangle ou un cercle posé sur le clic. Ce qui
    partira est montré en rouge sous la souris. Tab : la forme suivante ; [ et ] : plus petit, plus grand. L'outil
    reste actif ; chaque clic s'annule à part."""
    cursor = Qt.CursorShape.CrossCursor
    SIZE = {'segment': 'length', 'rectangle': 'width', 'cercle': 'diameter'}

    def __init__(self, canvas, spec: dict | None = None, changed=None):
        super().__init__(canvas)
        self.spec = dict({'kind': 'segment', 'length': 5.0, 'width': 10.0, 'height': 5.0, 'diameter': 5.0,
                          'angle': 0.0}, **(spec or {}))
        self.changed = changed                           # fonction(réglages) : la fenêtre les retient
        self.hover = None
        self.shown = (None, None)                        # (forme posée, morceau retiré) : calculé au mouvement
        self._say()

    def _say(self) -> None:
        from ..i18n import tr
        s = self.spec
        text = {'segment': tr('Emporte-pièce : un clic retire {0} mm du contour').format(f'{s["length"]:g}'),
                'rectangle': tr('Emporte-pièce : un clic retire ce que couvre le rectangle {0} × {1} mm').format(
                    f'{s["width"]:g}', f'{s["height"]:g}'),
                'cercle': tr('Emporte-pièce : un clic retire ce que couvre le cercle Ø {0} mm').format(
                    f'{s["diameter"]:g}')}[s['kind']]
        self.c.measured.emit(text + tr(' — Tab : autre forme ; [ ] : taille'))

    def _look(self) -> None:
        self.shown = self.c.punch_preview(self.hover, self.spec) if self.hover is not None else (None, None)
        self.c.overlay_update()

    def set_spec(self, spec: dict) -> None:
        self.spec.update(spec)
        self._say()
        self._look()

    def move(self, sp, dp, ev):
        self.hover = dp
        self._look()

    def press(self, sp, dp, ev):
        from ..i18n import tr
        n = self.c.punch_at(dp, self.spec)
        self.c.measured.emit(tr('{0} objet(s) coupé(s)').format(n) if n else tr('Rien à retirer ici'))
        self.hover = dp
        self._look()

    def wants_key(self, ev) -> bool:
        return ev.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab)

    def key(self, ev):
        from ..core.punchtool import KINDS
        k = ev.key()
        if k in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            step = -1 if k == Qt.Key.Key_Backtab else 1
            self.spec['kind'] = KINDS[(KINDS.index(self.spec['kind']) + step) % len(KINDS)]
        elif k in (Qt.Key.Key_BracketLeft, Qt.Key.Key_BracketRight):
            f = 1 / 1.25 if k == Qt.Key.Key_BracketLeft else 1.25
            name = self.SIZE[self.spec['kind']]
            self.spec[name] = max(0.01, round(self.spec[name] * f, 3))
            if self.spec['kind'] == 'rectangle':
                self.spec['height'] = max(0.01, round(self.spec['height'] * f, 3))
        else:
            return False
        if self.changed is not None:
            self.changed(dict(self.spec))
        self._say()
        self._look()
        return True

    def paint(self, p):
        if self.hover is None:
            return
        shape, pc = self.shown
        if shape is not None:
            self.preview(p, shape, '#e00000')
        if pc is not None:
            from .canvas import to_qpath
            p.save()
            p.setTransform(self.c.view())
            pen = QPen(QColor('#e00000'), 3.0)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(to_qpath(pc))
            p.restore()

    def cancel(self):
        self.hover = None
        self.shown = (None, None)


class BlobBrushTool(EraserTool):
    """Pinceau à aplat : glisser peint une surface (rond de rayon
    canvas.eraser_radius) qui se fond avec les formes fermées de l'outil
    courant qu'elle touche ; [ et ] : taille."""

    def release(self, sp, dp, ev):
        from ..i18n import tr
        pts, self.pts = self.pts + [dp], []
        n = self.c.blob_paint(pts, getattr(self.c, 'eraser_radius', 1.0))
        self.c.measured.emit(tr('Peint (fondu avec {0} forme(s))').format(n))
        self.c.overlay_update()


class LiquifyTool(Tool):
    """Liquéfier (core.liquify) : glisser déforme les formes choisies, sinon toutes celles que le
    pinceau rencontre. Tordre, contracter et dilater continuent tant qu'on tient le pinceau.
    Crochets [ ] : la taille du pinceau ; Échap pendant le geste : l'abandonner. Un passage = une annulation."""
    cursor = Qt.CursorShape.CrossCursor
    TICK_MS = 80

    def __init__(self, canvas, params):
        super().__init__(canvas)
        self.params = params
        self.pool = None            # [forme, stroke ou None]
        self.dabber = None
        self.hover = None
        self.timer = None

    def _targets(self) -> list:
        from ..core import solids as SO
        from .canvas import _leaves
        sel = list(_leaves(self.c.selection))
        if not sel:
            sel = [it for L in self.c.doc.layers if L.visible and not L.locked for it in _leaves(L.items)]
        return [it for it in sel if isinstance(it, Shape) and it.path.contours and not SO.is_solid(it)]

    def _dab(self, c) -> None:
        from ..core import liquify as LQ
        reach = self.params.reach()
        for rank, entry in enumerate(self.pool):
            shape, stroke = entry
            if stroke is None:
                b = shape.path.bbox()
                if b is None or b[0] > c[0] + reach or b[2] < c[0] - reach or b[1] > c[1] + reach or b[3] < c[1] - reach:
                    continue
                entry[1] = stroke = LQ.PathStroke(shape.path, self.params, salt=float(rank))
            stroke.dab(c)

    def press(self, sp, dp, ev):
        from PySide6.QtCore import QTimer
        from ..core import liquify as LQ
        self.pool = [[s, None] for s in self._targets()]
        self.dabber = LQ.Dabber(self.params)
        for c in self.dabber.push(dp):
            self._dab(c)
        if self.params.kind in LQ.HOLDS:
            self.timer = QTimer(self.c)
            self.timer.setInterval(self.TICK_MS)
            self.timer.timeout.connect(self.tick)
            self.timer.start()
        self.c.overlay_update()

    def tick(self) -> None:
        """Le pinceau tenu immobile : une touche de plus là où il est."""
        if self.dabber is None or self.dabber.last is None:
            return
        for c in self.dabber.push(self.dabber.last):
            self._dab(c)
        self.c.overlay_update()

    def move(self, sp, dp, ev):
        self.hover = dp
        if self.dabber is not None:
            for c in self.dabber.push(dp):
                self._dab(c)
        self.c.overlay_update()

    def _stop(self) -> None:
        if self.timer is not None:
            self.timer.stop()
            self.timer.deleteLater()
            self.timer = None

    def release(self, sp, dp, ev):
        from ..i18n import tr
        self._stop()
        if self.dabber is None:
            return
        for c in self.dabber.push(dp) + self.dabber.tail():
            self._dab(c)
        pool, self.pool, self.dabber = self.pool, None, None
        done = [(s, st.path(final=True)) for s, st in pool if st is not None and st.changed]
        if done:
            if self.c.undo_push:
                self.c.undo_push()
            for s, path in done:
                s.path = path
                s.extra = {k: v for k, v in s.extra.items() if k not in ('forme', 'sketch', 'sketch_box', 'script', 'corners')}
            self.c.invalidate([s for s, _p in done])
            self.c.documentChanged.emit()
        self.c.measured.emit(tr('{0} objet(s) déformé(s)').format(len(done)) if done else tr('Rien sous le pinceau'))
        self.c.overlay_update()
        self.c.update()

    def wants_key(self, ev):
        # Échap n'abandonne que le geste en cours ; hors geste, il quitte l'outil comme partout
        return (ev.key() in (Qt.Key.Key_BracketLeft, Qt.Key.Key_BracketRight)
                or (ev.key() == Qt.Key.Key_Escape and self.dabber is not None))

    def key(self, ev):
        if ev.key() in (Qt.Key.Key_BracketLeft, Qt.Key.Key_BracketRight):
            k = 1 / 1.25 if ev.key() == Qt.Key.Key_BracketLeft else 1.25
            self.params.width = max(0.05, self.params.width * k)
            self.params.height = max(0.05, self.params.height * k)
            self.c.overlay_update()
            return True
        if ev.key() == Qt.Key.Key_Escape and self.dabber is not None:
            self.cancel()
            self.c.overlay_update()
            return True
        return False

    def cancel(self):
        self._stop()
        self.pool = self.dabber = None

    def paint(self, p):
        for _s, st in self.pool or ():
            if st is not None and st.changed:
                self.preview(p, st.path())
        at = self.dabber.last if self.dabber is not None else self.hover
        if at is None:
            return
        p.save()
        p.setPen(_pen(_cc('measure'), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        c = self.c.to_screen(*at)
        p.translate(c)
        p.rotate(-self.params.angle)
        k = self.c.scale
        p.drawEllipse(QPointF(0.0, 0.0), self.params.width / 2.0 * k, self.params.height / 2.0 * k)
        p.restore()


class StretchTool(Tool):
    """Étirer (comme ÉTIRER en DAO) : deux coins d'une fenêtre de capture,
    puis un point de base et sa destination — les nœuds pris dans la fenêtre
    bougent, les segments vers les autres s'étirent. Sélection : seules ses
    formes ; sinon toutes. Accrochage F3 et repérage F11 conseillés."""
    cursor = Qt.CursorShape.CrossCursor

    def __init__(self, canvas):
        super().__init__(canvas)
        self.pts = []
        self.cur = None

    def press(self, sp, dp, ev):
        from ..i18n import tr
        self.pts.append(dp)
        if len(self.pts) < 4:
            self.c.measured.emit([tr('Cliquez le 2e coin de la fenêtre de capture'), tr('Cliquez le point de base'),
                                  tr('Cliquez la destination')][len(self.pts) - 1])
            self.c.overlay_update()
            return
        (x0, y0), (x1, y1), b, d = self.pts
        self.pts, self.cur = [], None
        n = self.c.stretch((x0, y0, x1, y1), d[0] - b[0], d[1] - b[1])
        self.c.measured.emit(tr('{0} nœud(s) déplacé(s)').format(n) if n else tr('Aucun nœud dans la fenêtre'))
        self.c.overlay_update()
        self.c.toolFinished.emit()

    def move(self, sp, dp, ev):
        if self.pts:
            self.cur = dp
            self.c.overlay_update()

    def paint(self, p):
        if not self.pts:
            return
        pts = self.pts + ([self.cur] if self.cur is not None else [])
        pen = _pen(_cc('measure'), 1.2)
        pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        if len(pts) >= 2:                                   # fenêtre de capture
            a, b = self.c.to_screen(*pts[0]), self.c.to_screen(*pts[1])
            p.drawRect(QRectF(a, b).normalized())
        if len(pts) >= 3:
            p.setPen(_pen(_cc('measure'), 1.5))
            a = self.c.to_screen(*pts[2])
            p.drawEllipse(a, 4, 4)
            if len(pts) >= 4:
                p.drawLine(a, self.c.to_screen(*pts[3]))

    def cancel(self):
        self.pts, self.cur = [], None


def align_matrix(s1, d1, s2=None, d2=None, scale: bool = False):
    """Transformation qui amène s1 sur d1 et, avec la seconde paire, la
    direction s1→s2 sur d1→d2 (rotation), à l'échelle d1d2 / s1s2 si `scale`."""
    m = geom.Affine.translation(d1[0] - s1[0], d1[1] - s1[1])
    if s2 is None or d2 is None:
        return m
    a1 = math.atan2(s2[1] - s1[1], s2[0] - s1[0])
    a2 = math.atan2(d2[1] - d1[1], d2[0] - d1[0])
    ls, ld = math.dist(s1, s2), math.dist(d1, d2)
    k = ld / ls if scale and ls > 1e-12 else 1.0
    return (geom.Affine.translation(d1[0], d1[1]) @ geom.Affine.rotation(math.degrees(a2 - a1)) @
            geom.Affine.scaling(k) @ geom.Affine.translation(-s1[0], -s1[1]))


class AlignPointsTool(Tool):
    """Aligner par points (comme ALIGNER en DAO) : 1er point source, 1er point
    destination, 2e point source, 2e point destination — la sélection est
    déplacée et tournée ; Maj au dernier clic : mise à l'échelle aussi.
    Entrée après la première paire : déplacement seul. Accrochage F3 conseillé."""

    def __init__(self, canvas):
        super().__init__(canvas)
        self.pts = []
        self.cur = None

    def press(self, sp, dp, ev):
        from ..i18n import tr
        if not self.c.selection:
            self.c.measured.emit(tr("Sélectionnez d'abord les objets à aligner"))
            return
        self.pts.append(dp)
        steps = [tr('Cliquez la 1re destination'), tr('Cliquez le 2e point source (Entrée : déplacement seul)'),
                 tr('Cliquez la 2e destination (Maj : mise à l\'échelle aussi)')]
        if len(self.pts) < 4:
            self.c.measured.emit(steps[len(self.pts) - 1])
            self.c.overlay_update()
            return
        scale = bool(ev is not None and ev.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        self.apply(align_matrix(*self.pts, scale=scale))

    def apply(self, m) -> None:
        self.pts, self.cur = [], None
        self.c.transform_selection(m)
        self.c.toolFinished.emit()

    def key(self, ev):
        if ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and len(self.pts) >= 2:
            self.apply(align_matrix(self.pts[0], self.pts[1]))
            return True
        return False

    def move(self, sp, dp, ev):
        if self.pts:
            self.cur = dp
            self.c.overlay_update()

    def paint(self, p):
        if not self.pts:
            return
        pts = list(self.pts) + ([self.cur] if self.cur is not None else [])
        p.setPen(_pen(_cc('measure'), 1.5))
        for i in range(0, len(pts) - 1, 2):                 # source → destination
            a, b = self.c.to_screen(*pts[i]), self.c.to_screen(*pts[i + 1])
            p.drawLine(a, b)
            p.drawEllipse(a, 4, 4)
            p.drawRect(QRectF(b.x() - 3, b.y() - 3, 6, 6))
        if len(pts) % 2:
            p.drawEllipse(self.c.to_screen(*pts[-1]), 4, 4)

    def cancel(self):
        self.pts, self.cur = [], None


class AxisAlignTool(Tool):
    """Aligner suivant un axe vertical / horizontal (TypeEdit) : clic sur le
    point de pivot, puis sur le point opposé ; la sélection tourne autour du
    pivot, de la plus petite rotation, pour que les deux points soient sur un
    même axe vertical (horizontal). Accrochage F3 conseillé (points de
    contrôle) ; aperçu en pointillés pendant le déplacement."""
    PREVIEW_MAX = 20_000                                  # segments : au-delà, pas d'aperçu du tracé

    def __init__(self, canvas, axis: str = 'v'):
        super().__init__(canvas)
        self.axis = axis
        self.pivot = None
        self.cur = None

    @staticmethod
    def angle(pivot, q, axis: str) -> float:
        """Rotation (degrés, sens trigonométrique, |a| ≤ 90) qui amène q sur
        l'axe vertical ('v') ou horizontal ('h') passant par le pivot."""
        ang = math.degrees(math.atan2(q[1] - pivot[1], q[0] - pivot[0]))
        d = ((90.0 if axis == 'v' else 0.0) - ang) % 180.0
        return d - 180.0 if d > 90.0 else d

    def matrix(self, q):
        return geom.Affine.rotation(self.angle(self.pivot, q, self.axis), self.pivot)

    def press(self, sp, dp, ev):
        from ..i18n import tr
        if not self.c.selection:
            self.c.measured.emit(tr('Sélectionnez d\'abord l\'objet à redresser'))
            return
        if self.pivot is None:
            self.pivot, self.cur = dp, dp
            self.c.measured.emit(tr('Cliquez sur le point à amener sur l\'axe'))
            return
        if math.dist(self.pivot, dp) < 1e-9:
            return
        m = self.matrix(dp)
        self.pivot = self.cur = None
        self.c.transform_selection(m)
        self.c.toolFinished.emit()

    def move(self, sp, dp, ev):
        if self.pivot is not None:
            from ..i18n import tr
            self.cur = dp
            if math.dist(self.pivot, dp) > 1e-9:
                self.c.measured.emit(tr('Rotation {0:.3f}°').format(self.angle(self.pivot, dp, self.axis)))
            self.c.overlay_update()

    def paint(self, p):
        if self.pivot is None or self.cur is None:
            return
        A, B = self.c.to_screen(*self.pivot), self.c.to_screen(*self.cur)
        p.setPen(_pen(_cc('measure'), 1.5))
        p.drawLine(A, B)
        p.drawEllipse(A, 4, 4)
        p.setPen(_pen(_cc('measure'), 1, Qt.PenStyle.DashLine))
        if self.axis == 'v':
            p.drawLine(QPointF(A.x(), 0), QPointF(A.x(), self.c.height()))
        else:
            p.drawLine(QPointF(0, A.y()), QPointF(self.c.width(), A.y()))
        if math.dist(self.pivot, self.cur) <= 1e-9:
            return
        from .canvas import _leaves, item_path, to_qpath
        cs = [c for leaf in _leaves(self.c.selection) for c in (item_path(leaf).contours if item_path(leaf) else [])]
        if not cs or sum(len(c.segments) for c in cs) > self.PREVIEW_MAX:
            return
        path = Path(cs).transformed(self.matrix(self.cur))
        p.save()
        p.setTransform(self.c.view())
        p.setPen(_pen(_cc('preview'), 1, Qt.PenStyle.DashLine))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(to_qpath(path))
        p.restore()

    def cancel(self):
        self.pivot = self.cur = None


class MeasureTool(Tool):
    """Mesure : clic au départ, clic à l'arrivée (accrochage F3 conseillé).
    Affiche la distance, ΔX, ΔY et l'angle ; un nouveau clic recommence.
    `rect` (distance rectangle de TypeEdit, Maj+D) : le rectangle des deux
    points, ses côtés X et Y et sa diagonale XY."""

    def __init__(self, canvas, rect: bool = False):
        super().__init__(canvas)
        self.a = None
        self.b = None
        self.done = False
        self.rect = rect

    @staticmethod
    def describe_rect(a, b) -> str:
        from ..i18n import tr
        dx, dy = abs(b[0] - a[0]), abs(b[1] - a[1])
        return tr('X {0:.3f} mm   Y {1:.3f} mm   XY {2:.3f} mm').format(dx, dy, math.hypot(dx, dy))

    def _text(self) -> str:
        return self.describe_rect(self.a, self.b) if self.rect else self.describe(self.a, self.b)

    @staticmethod
    def describe(a, b) -> str:
        from ..i18n import tr
        dx, dy = b[0] - a[0], b[1] - a[1]
        ang = math.degrees(math.atan2(dy, dx))
        return tr('Distance {0:.3f} mm   ΔX {1:.3f}   ΔY {2:.3f}   angle {3:.2f}°').format(
            math.hypot(dx, dy), dx, dy, ang)

    def press(self, sp, dp, ev):
        if self.a is None or self.done:
            self.a, self.b, self.done = dp, dp, False
            return
        if _ctrl(ev):
            dp = _snap45(self.a, dp)
        self.b, self.done = dp, True
        self.c.measured.emit(self._text())

    def move(self, sp, dp, ev):
        if self.a is not None and not self.done:
            self.b = _snap45(self.a, dp) if _ctrl(ev) else dp
            self.c.measured.emit(self._text())
            self.c.overlay_update()

    def paint(self, p):
        if self.a is None or self.b is None:
            return
        A, Bp = self.c.to_screen(*self.a), self.c.to_screen(*self.b)
        if self.rect:
            self._paint_rect(p, A, Bp)
            return
        p.setPen(_pen(_cc('measure'), 1.5))
        p.drawLine(A, Bp)
        for q in (A, Bp):
            p.drawEllipse(q, 3, 3)
        txt = self.describe(self.a, self.b).split('   ')[0]
        p.setPen(QColor(_cc('measure')))
        p.drawText(QPointF((A.x() + Bp.x()) / 2 + 8, (A.y() + Bp.y()) / 2 - 8), txt)

    def _paint_rect(self, p, A, Bp):
        """Rectangle des deux points (tirets), diagonale ; X sous le côté
        horizontal du départ, Y à côté du côté vertical de l'arrivée, XY au
        milieu de la diagonale."""
        C = self.c.to_screen(self.b[0], self.a[1])          # coin : X de l'arrivée, Y du départ
        D = self.c.to_screen(self.a[0], self.b[1])
        p.setPen(_pen(_cc('measure'), 1.0, Qt.PenStyle.DashLine))
        p.drawPolygon([A, C, Bp, D])
        p.setPen(_pen(_cc('measure'), 1.5))
        p.drawLine(A, Bp)
        for q in (A, Bp):
            p.drawEllipse(q, 3, 3)
        dx, dy = abs(self.b[0] - self.a[0]), abs(self.b[1] - self.a[1])
        p.setPen(QColor(_cc('measure')))
        fm = p.fontMetrics()
        below = 1 if A.y() >= Bp.y() else -1              # le texte X hors du rectangle
        tx = f'X {dx:.3f}'
        p.drawText(QPointF((A.x() + C.x()) / 2 - fm.horizontalAdvance(tx) / 2,
                           A.y() + (fm.ascent() + 4 if below > 0 else -6)), tx)
        ty = f'Y {dy:.3f}'
        right = Bp.x() >= A.x()
        p.drawText(QPointF(C.x() + 6 if right else C.x() - 6 - fm.horizontalAdvance(ty),
                           (C.y() + Bp.y()) / 2 + fm.ascent() / 2), ty)
        txy = f'XY {math.hypot(dx, dy):.3f}'
        p.drawText(QPointF((A.x() + Bp.x()) / 2 + 8, (A.y() + Bp.y()) / 2 - 8), txy)

    def cancel(self):
        self.a = self.b = None
        self.done = False


def _picked_path(canvas, sp):
    """Tracé de l'objet sous le curseur (groupes : tous leurs objets), ou None."""
    from .canvas import _leaves, item_path
    hit = canvas.pick(sp)
    if hit is None:
        return None
    cs = [c for leaf in _leaves([hit]) if (pp := item_path(leaf)) for c in pp.contours]
    return Path(cs) if cs else None


class MeasureRadiusTool(Tool):
    """Mesurer un rayon (comme MESUREGEOM en DAO) : clic sur un cercle, un
    arc ou une courbe — rayon et diamètre ; arc (même en plusieurs
    morceaux) : angle et longueur ; courbe : rayon de courbure au point
    cliqué ; trait droit : longueur. Un nouveau clic mesure ailleurs."""
    cursor = Qt.CursorShape.PointingHandCursor

    def __init__(self, canvas):
        super().__init__(canvas)
        self.info = None
        self.at = None

    @staticmethod
    def describe(info) -> str:
        from ..i18n import tr
        k = info['kind']
        if k == 'circle':
            return tr('Cercle : rayon {0:.3f} mm   Ø {1:.3f} mm   centre X {2:.3f}  Y {3:.3f}').format(
                info['r'], 2 * info['r'], info['center'][0], info['center'][1])
        if k == 'arc':
            return tr('Arc : rayon {0:.3f} mm   Ø {1:.3f} mm   angle {2:.2f}°   longueur {3:.3f} mm').format(
                info['r'], 2 * info['r'], info['sweep'], info['length'])
        if k == 'line':
            return tr('Trait droit : longueur {0:.3f} mm   angle {1:.2f}°').format(info['length'], info['angle'])
        if k == 'curve':
            return tr('Courbe : rayon de courbure {0:.3f} mm au point cliqué (Ø {1:.3f} mm)').format(
                info['r'], 2 * info['r'])
        return tr('Courbe droite à cet endroit (rayon infini)')

    def press(self, sp, dp, ev):
        from ..core import measuregeom as MG
        from ..i18n import tr
        path = _picked_path(self.c, sp)
        self.info = MG.radius_info(path, dp) if path is not None else None
        self.at = dp
        self.c.measured.emit(self.describe(self.info) if self.info else tr('Cliquez un cercle, un arc ou une courbe'))
        self.c.overlay_update()

    def _touch(self):
        """Point du cercle (ou de la courbe) d'où part le rayon dessiné."""
        info = self.info
        if info['kind'] == 'curve':
            return info['point']
        cx, cy = info['center']
        d = math.hypot(self.at[0] - cx, self.at[1] - cy)
        ux, uy = ((self.at[0] - cx) / d, (self.at[1] - cy) / d) if d > 1e-12 else (1.0, 0.0)
        return cx + ux * info['r'], cy + uy * info['r']

    def paint(self, p):
        if not self.info:
            return
        k = self.info['kind']
        color = _cc('measure')
        p.setPen(_pen(color, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        if k in ('line', 'flat'):
            if k == 'line':
                A, B = self.c.to_screen(*self.info['start']), self.c.to_screen(*self.info['end'])
                p.setPen(_pen(color, 3))
                p.drawLine(A, B)
                p.setPen(QColor(color))
                p.drawText(QPointF((A.x() + B.x()) / 2 + 8, (A.y() + B.y()) / 2 - 8), f'{self.info["length"]:.3f}')
            return
        C, Q = self.c.to_screen(*self.info['center']), self.c.to_screen(*self._touch())
        rs = self.info['r'] * self.c.scale
        if k == 'curve' and rs < 20000:                     # cercle osculateur
            p.setPen(_pen(color, 1.0, Qt.PenStyle.DashLine))
            p.drawEllipse(C, rs, rs)
            p.setPen(_pen(color, 1.5))
        if k == 'arc':
            p.setPen(_pen(color, 3))
            for q in (self.info['start'], self.info['end']):
                p.drawEllipse(self.c.to_screen(*q), 3, 3)
            p.setPen(_pen(color, 1.5))
        p.drawLine(C, Q)
        p.drawLine(QPointF(C.x() - 6, C.y()), QPointF(C.x() + 6, C.y()))
        p.drawLine(QPointF(C.x(), C.y() - 6), QPointF(C.x(), C.y() + 6))
        p.drawEllipse(Q, 3, 3)
        p.setPen(QColor(color))
        p.drawText(QPointF((C.x() + Q.x()) / 2 + 8, (C.y() + Q.y()) / 2 - 8), f'R {self.info["r"]:.3f}')

    def cancel(self):
        self.info = self.at = None


class XLineTool(Tool):
    """Ligne de construction (comme XLINE en DAO, d'après CADCraft) : un 1er
    clic pose le point par où passent les lignes, chaque clic suivant pose
    une ligne par ce point et le point cliqué (Maj : angle par pas de 15°) ;
    Échap pour finir. Horizontale ou verticale : guide ordinaire."""

    def __init__(self, canvas):
        super().__init__(canvas)
        self.base = None

    def _angle(self, dp, ev) -> float:
        a = math.degrees(math.atan2(dp[1] - self.base[1], dp[0] - self.base[0]))
        if ev is not None and ev.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            a = round(a / 15.0) * 15.0
        return a

    def press(self, sp, dp, ev):
        from ..i18n import tr
        if self.base is None:
            self.base = dp
            self.c.measured.emit(tr('Cliquez un point de la ligne (Maj : par 15°) ; Échap pour finir'))
            return
        if math.dist(self.base, dp) < 1e-9:
            return
        self.c.add_oblique_guide(self.base[0], self.base[1], self._angle(dp, ev))
        self.c.oblique_preview = None
        self.c.measured.emit(tr('Ligne posée : un autre clic en pose une autre par le même point ; Échap pour finir'))

    def move(self, sp, dp, ev):
        if self.base is not None and math.dist(self.base, dp) > 1e-9:
            self.c.oblique_preview = (self.base[0], self.base[1], self._angle(dp, ev))
            self.c.overlay_update()

    def paint(self, p):
        if self.base is not None:
            p.setPen(_pen(_cc('preview'), 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(self.c.to_screen(*self.base), 4, 4)

    def cancel(self):
        self.base = None
        self.c.oblique_preview = None
        self.c.overlay_update()


class MeasureAngleTool(Tool):
    """Mesurer un angle (comme MESUREGEOM en DAO) : clic sur deux traits
    droits — angle du secteur où l'on a cliqué (écart s'ils sont
    parallèles) ; ailleurs, trois clics : le sommet, puis un point de
    chaque côté (accrochage F3 conseillé). Un nouveau clic recommence."""

    def __init__(self, canvas):
        super().__init__(canvas)
        self.lines: list = []                # [((a, b), point cliqué)]
        self.pts: list = []
        self.result = None
        self.hover = None

    @staticmethod
    def describe(res) -> str:
        from ..i18n import tr
        if res.get('vertex') is None:
            return tr('Traits parallèles : angle 0°   écart {0:.3f} mm').format(res['gap'])
        a = res['angle']
        return tr('Angle {0:.2f}°   (supplément {1:.2f}°, rentrant {2:.2f}°)').format(a, 180.0 - a, 360.0 - a)

    def _finish(self, res):
        self.result = res
        self.c.measured.emit(self.describe(res))

    def press(self, sp, dp, ev):
        from ..core import measuregeom as MG
        from ..i18n import tr
        if self.result is not None:
            self.cancel()
        if not self.pts:
            path = _picked_path(self.c, sp)
            ln = MG.line_at(path, dp, SNAP_PX / max(self.c.scale, 1e-9)) if path is not None else None
            if ln is not None:
                self.lines.append((ln, dp))
                if len(self.lines) == 2:
                    (l1, p1), (l2, p2) = self.lines
                    self._finish(MG.lines_angle(l1, l2, p1, p2))
                else:
                    self.c.measured.emit(tr('Cliquez le second trait droit, du côté de l\'angle à mesurer'))
                self.c.overlay_update()
                return
            if self.lines:
                self.c.measured.emit(tr('Cliquez un second trait droit (Échap : mesurer en trois points)'))
                return
        self.pts.append(dp)
        if len(self.pts) == 3:
            v, a, b = self.pts
            ang = MG.angle_3points(v, a, b)
            if ang is None:
                self.pts = []
                self.c.measured.emit(tr('Points confondus : pas d\'angle'))
            else:
                self._finish({'angle': ang, 'vertex': v, 'gap': 0.0,
                              'dirs': ((a[0] - v[0], a[1] - v[1]), (b[0] - v[0], b[1] - v[1]))})
        else:
            self.c.measured.emit(tr('Sommet posé : cliquez un point du premier côté') if len(self.pts) == 1
                                 else tr('Cliquez un point du second côté'))
        self.c.overlay_update()

    def move(self, sp, dp, ev):
        if self.pts and self.result is None:
            self.hover = dp
            self.c.overlay_update()

    def _ray(self, V, d, px=70.0):
        L = math.hypot(*d)
        if L < 1e-12:
            return V
        k = px / max(self.c.scale, 1e-9) / L
        return self.c.to_screen(V[0] + d[0] * k, V[1] + d[1] * k)

    def paint(self, p):
        color = _cc('measure')
        p.setPen(_pen(color, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for (a, b), _q in self.lines:
            p.setPen(_pen(color, 3))
            p.drawLine(self.c.to_screen(*a), self.c.to_screen(*b))
            p.setPen(_pen(color, 1.5))
        res = self.result
        if res is None:
            pts = self.pts + ([self.hover] if self.hover is not None and self.pts else [])
            if len(pts) >= 2:
                V = self.c.to_screen(*pts[0])
                for q in pts[1:]:
                    p.drawLine(V, self.c.to_screen(*q))
            return
        if res.get('vertex') is None:
            return
        v = res['vertex']
        V = self.c.to_screen(*v)
        U, W = self._ray(v, res['dirs'][0]), self._ray(v, res['dirs'][1])
        p.drawLine(V, U)
        p.drawLine(V, W)
        a1 = math.degrees(math.atan2(-(U.y() - V.y()), U.x() - V.x()))
        a2 = math.degrees(math.atan2(-(W.y() - V.y()), W.x() - V.x()))
        span = (a2 - a1 + 180.0) % 360.0 - 180.0
        r = 34.0
        p.drawArc(QRectF(V.x() - r, V.y() - r, 2 * r, 2 * r), int(a1 * 16), int(span * 16))
        mid = math.radians(a1 + span / 2)
        p.setPen(QColor(color))
        p.drawText(QPointF(V.x() + (r + 10) * math.cos(mid), V.y() - (r + 10) * math.sin(mid)), f'{res["angle"]:.2f}°')

    def cancel(self):
        self.lines, self.pts, self.result, self.hover = [], [], None, None


class CenterLineTool(Tool):
    """Ligne d'axe (comme CENTERLINE en DAO) : clic sur deux traits droits —
    un trait sur leur axe, du milieu des débuts au milieu des fins, qui
    déborde de `extend` mm ; en trait mixte avec `dashed`. L'outil reste
    actif pour la paire suivante (Échap pour finir)."""

    def __init__(self, canvas, extend: float = 2.0, dashed: bool = False, scale: float = 0.25):
        super().__init__(canvas)
        self.extend, self.dashed, self.scale = extend, dashed, scale
        self.first = None                    # premier trait : (a, b)
        self.hover = None                    # ligne d'axe prévue sous le curseur : (début, fin)

    def _line(self, sp, dp):
        from ..core import measuregeom as MG
        path = _picked_path(self.c, sp)
        return MG.line_at(path, dp, SNAP_PX / max(self.c.scale, 1e-9)) if path is not None else None

    def press(self, sp, dp, ev):
        from ..core import cadtools as C
        from ..i18n import tr
        ln = self._line(sp, dp)
        if ln is None:
            self.c.measured.emit(tr('Cliquez un trait droit'))
            return
        if self.first is None:
            self.first = ln
            self.c.measured.emit(tr('Cliquez le second trait droit'))
            self.c.overlay_update()
            return
        if ln == self.first:
            self.c.measured.emit(tr('Cliquez un autre trait droit'))
            return
        got = C.center_line(self.first, ln, self.extend)
        self.first, self.hover = None, None
        if got is None:
            self.c.measured.emit(tr('Ces traits ne donnent pas de ligne d\'axe'))
        else:
            self.c.commit_shape(C.axis_path(*got, self.dashed, self.scale), back_to_select=False)
            self.c.measured.emit(tr('Ligne d\'axe posée ({0:.3f} mm) : cliquez deux autres traits ; Échap pour '
                                    'finir').format(math.dist(*got)))
        self.c.overlay_update()

    def move(self, sp, dp, ev):
        from ..core import cadtools as C
        if self.first is None:
            return
        ln = self._line(sp, dp)
        hv = C.center_line(self.first, ln, self.extend) if ln is not None and ln != self.first else None
        if hv != self.hover:
            self.hover = hv
            self.c.overlay_update()

    def paint(self, p):
        color = _cc('measure')
        if self.first is not None:
            p.setPen(_pen(color, 3))
            p.drawLine(self.c.to_screen(*self.first[0]), self.c.to_screen(*self.first[1]))
        if self.hover is not None:
            p.setPen(_pen(color, 1.5, Qt.PenStyle.DashDotLine))
            p.drawLine(self.c.to_screen(*self.hover[0]), self.c.to_screen(*self.hover[1]))

    def cancel(self):
        self.first, self.hover = None, None


class WidthTool(Tool):
    """La largeur d'un trait, à la souris. Clic sur le trait : un point de largeur ; glisser : sa largeur (Alt : un seul
    côté ; Ctrl : le déplacer le long du trait) ; Suppr : retirer le point sous le pointeur ; Entrée ou double-clic :
    valider, le trait devient une bande pleine ; Échap : abandonner."""
    cursor = Qt.CursorShape.ArrowCursor
    GRAB_PX = 7.0
    PICK_PX = 9.0
    START = 2.0         # largeur d'un trait qui n'en a pas encore (mm)

    def __init__(self, canvas):
        super().__init__(canvas)
        self.reset()

    def reset(self) -> None:
        self.item = None
        self.line = []          # le premier contour, en points
        self.along = []         # abscisse relative de chaque point
        self.closed = False
        self.knots = []         # [t, gauche, droite] en mm, par t croissant
        self.drag = None
        self.hover = None

    # --- le trait ---------------------------------------------------------------
    def take(self, item) -> bool:
        """Prend ce trait : ses points de largeur partent de rien."""
        if not isinstance(item, Shape) or not item.path.contours or not item.path.contours[0].segments:
            return False
        c = item.path.contours[0]
        pts = c.flatten(0.02)
        if c.closed and math.dist(pts[0], pts[-1]) > 1e-9:
            pts = list(pts) + [pts[0]]
        if len(pts) < 2:
            return False
        lengths = [0.0]
        for a, b in zip(pts, pts[1:]):
            lengths.append(lengths[-1] + math.dist(a, b))
        if lengths[-1] <= 0.0:
            return False
        self.item, self.line, self.closed = item, [tuple(p[:2]) for p in pts], c.closed
        self.along = [v / lengths[-1] for v in lengths]
        self.knots = []
        self.c.select([item])
        return True

    def foot(self, dp) -> tuple:
        """Le point du trait le plus proche : (t, point, normale à gauche, distance)."""
        best = None
        for i, (a, b) in enumerate(zip(self.line, self.line[1:])):
            dx, dy = b[0] - a[0], b[1] - a[1]
            n = dx * dx + dy * dy
            if n <= 0.0:
                continue
            u = max(0.0, min(1.0, ((dp[0] - a[0]) * dx + (dp[1] - a[1]) * dy) / n))
            q = (a[0] + u * dx, a[1] + u * dy)
            d = math.dist(dp, q)
            if best is None or d < best[3]:
                t = self.along[i] + u * (self.along[i + 1] - self.along[i])
                root = math.sqrt(n)
                best = (t, q, (-dy / root, dx / root), d)
        return best

    def at(self, t: float) -> tuple:
        """Le point d'abscisse t et sa normale à gauche."""
        from bisect import bisect_right
        i = min(max(bisect_right(self.along, t) - 1, 0), len(self.line) - 2)
        while i < len(self.line) - 2 and self.along[i + 1] <= self.along[i]:
            i += 1
        span = self.along[i + 1] - self.along[i]
        u = (t - self.along[i]) / span if span > 0 else 0.0
        a, b = self.line[i], self.line[i + 1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        root = math.hypot(dx, dy) or 1.0
        return (a[0] + u * dx, a[1] + u * dy), (-dy / root, dx / root)

    def spec(self):
        from ..core.varstroke import VarStrokeSpec
        return VarStrokeSpec(profile='points', knots=[tuple(k) for k in self.knots])

    def handles(self) -> list:
        """(n° du point, côté, position) : les deux poignées de chaque point."""
        out = []
        for n, (t, left, right) in enumerate(self.knots):
            p, nr = self.at(t)
            out.append((n, 'left', (p[0] + nr[0] * left, p[1] + nr[1] * left)))
            out.append((n, 'right', (p[0] - nr[0] * right, p[1] - nr[1] * right)))
        return out

    def handle_at(self, dp):
        reach = self.GRAB_PX / max(self.c.scale, 1e-9)
        best, near = None, reach
        for n, side, q in self.handles():
            d = math.dist(dp, q)
            if d <= near:
                best, near = (n, side), d
        return best

    def add_knot(self, t: float) -> int:
        from ..core.varstroke import sides_at
        left, right = sides_at(self.spec(), t) if self.knots else (self.START / 2.0, self.START / 2.0)
        self.knots.append([t, left, right])
        self.knots.sort(key=lambda k: k[0])
        return next(i for i, k in enumerate(self.knots) if k[0] == t)

    # --- la souris --------------------------------------------------------------
    def press(self, sp, dp, ev):
        if ev is not None and ev.button() != Qt.MouseButton.LeftButton:
            return
        if self.item is None:
            found = self.c.pick(sp)
            if not self.take(found):
                from ..i18n import tr
                self.c.measured.emit(tr('Cliquez sur un trait.'))
                return
        got = self.handle_at(dp)
        if got is not None:
            self.drag = got
            return
        f = self.foot(dp)
        if f[3] * self.c.scale <= self.PICK_PX:
            self.drag = (self.add_knot(f[0]), 'both')
            self.c.overlay_update()
            return
        found = self.c.pick(sp)
        if found is not self.item and isinstance(found, Shape):         # un autre trait : on l'essaie à sa place
            if not self.knots:
                self.take(found)
                self.c.overlay_update()

    def move(self, sp, dp, ev):
        if self.drag is None:
            hover = self.handle_at(dp) if self.item is not None else None
            if hover != self.hover:
                self.hover = hover
                self.c.overlay_update()
            return
        n, side = self.drag
        mods = ev.modifiers() if ev is not None else Qt.KeyboardModifier.NoModifier
        if mods & Qt.KeyboardModifier.ControlModifier:                  # le long du trait
            k = self.knots[n]
            k[0] = self.foot(dp)[0]
            self.knots.sort(key=lambda v: v[0])
            self.drag = (next(i for i, v in enumerate(self.knots) if v is k), side)
        else:
            k = self.knots[n]
            p, nr = self.at(k[0])
            d = abs((dp[0] - p[0]) * nr[0] + (dp[1] - p[1]) * nr[1])
            over_left = (dp[0] - p[0]) * nr[0] + (dp[1] - p[1]) * nr[1] >= 0.0
            if mods & Qt.KeyboardModifier.AltModifier:                  # un seul côté
                if (side == 'left') if side != 'both' else over_left:
                    k[1] = d
                else:
                    k[2] = d
            else:
                k[1] = k[2] = d
            from ..i18n import tr
            self.c.measured.emit(tr('Largeur : {0} mm').format(f'{k[1] + k[2]:.3f}'))
        self.c.overlay_update()

    def release(self, sp, dp, ev):
        self.drag = None
        self.c.overlay_update()

    def double(self, sp, dp, ev):
        self.apply()

    def wants_key(self, ev) -> bool:
        return self.item is not None and ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Delete,
                                                      Qt.Key.Key_Backspace, Qt.Key.Key_Escape)

    def key(self, ev) -> bool:
        if self.item is None:
            return False
        k = ev.key()
        if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.apply()
            return True
        if k == Qt.Key.Key_Escape:
            self.cancel()
            return True
        if k in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self.hover is not None and self.hover[0] < len(self.knots):
                del self.knots[self.hover[0]]
                self.hover = None
                self.c.overlay_update()
            return True
        return False

    def apply(self) -> bool:
        """Le trait devient une bande pleine, annulable d'un coup."""
        from ..core.document import drop_source_object
        from ..core.varstroke import var_stroke
        if self.item is None or not self.knots:
            return False
        got = var_stroke(self.item.path, self.spec())
        if not got.contours:
            return False
        if self.c.undo_push:
            self.c.undo_push()
        item = self.item
        item.path = got
        drop_source_object(item)
        self.reset()
        self.c.invalidate([item])
        self.c.documentChanged.emit()
        self.c.update()
        return True

    def cancel(self) -> None:
        self.reset()
        self.c.overlay_update()

    # --- l'aperçu ---------------------------------------------------------------
    def paint(self, p: QPainter) -> None:
        if self.item is None:
            return
        from ..core.varstroke import var_stroke
        path = var_stroke(self.item.path, self.spec()) if self.knots else self.item.path
        self.preview(p, path, _cc('measure'))
        p.save()
        p.setBrush(QColor(_cc('measure')))
        for n, side, q in self.handles():
            s = self.c.to_screen(*q)
            big = 4.0 if self.hover == (n, side) or (self.drag is not None and self.drag[0] == n) else 3.0
            p.setPen(_pen(_cc('measure')))
            p.drawRect(QRectF(s.x() - big, s.y() - big, 2 * big, 2 * big))
        p.restore()
