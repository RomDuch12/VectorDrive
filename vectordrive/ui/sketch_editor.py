"""Fenêtre de l'esquisse contrainte (core.sketch) : on dessine, on dit ce qui doit rester vrai, on cote.

Une contrainte ou une cote qui contredirait les autres est refusée, et la fenêtre dit lesquelles : l'esquisse reste
toujours juste. Ce qui reste libre est en bleu, ce qui est entièrement tenu dans la couleur du texte.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QGridLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel,
                               QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSizePolicy, QVBoxLayout, QWidget)

from ..core import sketch as SK
from ..i18n import tr

_HIT = 7.0
#: droit à ce point près (degrés) : le trait se pose horizontal ou vertical
_AUTO_DEG = 2.0
#: au-delà, l'esquisse se traînerait
MAX_ENTITIES = 500
_GLYPHS = {'coincident': 'o', 'on_line': 'o', 'on_circle': 'o', 'horizontal': 'H', 'vertical': 'V', 'h_points': 'H',
           'v_points': 'V', 'parallel': '//', 'perpendicular': '⊥', 'collinear': '—', 'tangent_lc': 'T', 'tangent_cc': 'T',
           'equal_ll': '=', 'equal_cc': '=', 'concentric': '◎', 'midpoint': 'M', 'symmetric': 'S', 'fix': 'F'}


def kind_label(kind: str) -> str:
    return {'coincident': tr('Coïncident'), 'on_line': tr('Point sur le trait'), 'on_circle': tr('Point sur le cercle'),
            'horizontal': tr('Horizontal'), 'vertical': tr('Vertical'), 'h_points': tr('Points à l’horizontale'),
            'v_points': tr('Points à la verticale'), 'parallel': tr('Parallèles'), 'perpendicular': tr('Perpendiculaires'),
            'collinear': tr('Dans l’axe'), 'tangent_lc': tr('Tangent'), 'tangent_cc': tr('Tangents'),
            'equal_ll': tr('Égaux'), 'equal_cc': tr('Égaux'), 'concentric': tr('Concentriques'), 'midpoint': tr('Milieu'),
            'symmetric': tr('Symétriques'), 'fix': tr('Fixe'), 'distance': tr('Distance'), 'distance_x': tr('Distance en X'),
            'distance_y': tr('Distance en Y'), 'point_line': tr('Distance au trait'), 'length': tr('Longueur'),
            'radius': tr('Rayon'), 'diameter': tr('Diamètre'), 'angle': tr('Angle')}.get(kind, kind)


def value_text(c: SK.Constraint) -> str:
    v = float(c.value)
    if c.kind == 'radius':
        return f'R{v:g}'
    if c.kind == 'diameter':
        return f'Ø{v:g}'
    if c.kind == 'angle':
        return f'{v:g}°'
    return f'{v:g}'


class SketchView(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.ed = editor
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(520, 420)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.k, self.ox, self.oy = 4.0, 60.0, 360.0
        self.tool = 'select'
        self.clicks: list = []                           # points déjà posés de la forme en cours : (id ou None, x, y)
        self.cursor = None
        self.drag = None                                 # {id : décalage} ou {cercle : rayon}
        self.drag_from = None
        self.pan_from = None
        self.selected: list = []
        self.labels: list = []                           # (rectangle à l'écran, contrainte)
        self.fit_pending = True

    # --- repères ---------------------------------------------------------------------------------------------------
    def to_screen(self, x: float, y: float) -> QPointF:
        return QPointF(self.ox + x * self.k, self.oy - y * self.k)

    def to_doc(self, p: QPointF) -> tuple[float, float]:
        return (p.x() - self.ox) / self.k, (self.oy - p.y()) / self.k

    def fit(self) -> None:
        sk = self.ed.sketch
        xs, ys = [], []
        for x, y in sk.points.values():
            xs.append(x)
            ys.append(y)
        for v in sk.circles.values():
            cx, cy = sk.points[v['c']]
            xs += [cx - v['r'], cx + v['r']]
            ys += [cy - v['r'], cy + v['r']]
        if not xs:
            xs, ys = [0.0, 100.0], [0.0, 100.0]
        w, h = max(max(xs) - min(xs), 1.0), max(max(ys) - min(ys), 1.0)
        self.k = max(1e-3, min((self.width() - 80) / w, (self.height() - 80) / h))
        self.ox = (self.width() - w * self.k) / 2 - min(xs) * self.k
        self.oy = (self.height() + h * self.k) / 2 + min(ys) * self.k
        self.update()

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        if self.fit_pending and self.width() > 0:
            self.fit_pending = False
            self.fit()

    # --- ce qui est sous la souris ---------------------------------------------------------------------------------
    def point_at(self, p: QPointF):
        best, near = None, _HIT
        for k, (x, y) in self.ed.sketch.points.items():
            q = self.to_screen(x, y)
            d = math.hypot(q.x() - p.x(), q.y() - p.y())
            if d <= near:
                best, near = k, d
        return best

    def _on_arc(self, v: dict, x: float, y: float) -> bool:
        if v['a'] is None:
            return True
        sk = self.ed.sketch
        cx, cy = sk.points[v['c']]
        ax, ay = sk.points[v['a']]
        bx, by = sk.points[v['b']]
        turn = (math.atan2(y - cy, x - cx) - math.atan2(ay - cy, ax - cx)) % (2 * math.pi)
        sweep = (math.atan2(by - cy, bx - cx) - math.atan2(ay - cy, ax - cx)) % (2 * math.pi)
        return turn <= sweep if v['ccw'] else (2 * math.pi - turn) % (2 * math.pi) <= (2 * math.pi - sweep) % (2 * math.pi)

    def entity_at(self, p: QPointF):
        sk = self.ed.sketch
        x, y = self.to_doc(p)
        best, near = None, _HIT / self.k
        for k, v in sk.lines.items():
            ax, ay = sk.points[v['p']]
            bx, by = sk.points[v['q']]
            dx, dy = bx - ax, by - ay
            t = ((x - ax) * dx + (y - ay) * dy) / max(dx * dx + dy * dy, 1e-12)
            t = max(0.0, min(1.0, t))
            d = math.hypot(x - ax - t * dx, y - ay - t * dy)
            if d <= near:
                best, near = k, d
        for k, v in sk.circles.items():
            cx, cy = sk.points[v['c']]
            d = abs(math.hypot(x - cx, y - cy) - v['r'])
            if d <= near and self._on_arc(v, x, y):
                best, near = k, d
        return best

    def snap(self, p: QPointF) -> tuple:
        """(point existant ou None, x, y)."""
        k = self.point_at(p)
        if k is not None:
            return (k, *self.ed.sketch.points[k])
        return (None, *self.to_doc(p))

    def _point(self, click: tuple) -> int:
        return click[0] if click[0] is not None else self.ed.sketch.add_point(click[1], click[2])

    # --- souris ----------------------------------------------------------------------------------------------------
    def mousePressEvent(self, ev) -> None:
        self.setFocus()
        p = ev.position()
        if ev.button() == Qt.MouseButton.MiddleButton:
            self.pan_from = (p, self.ox, self.oy)
            return
        if ev.button() == Qt.MouseButton.RightButton:
            self.cancel()
            return
        if ev.button() != Qt.MouseButton.LeftButton:
            return
        if self.tool == 'select':
            self.press_select(p, bool(ev.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)))
        else:
            self.press_draw(p)
        self.update()

    def press_select(self, p: QPointF, add: bool) -> None:
        hit = self.point_at(p)
        if hit is None:
            hit = self.entity_at(p)
        if hit is None:
            if not add:
                self.selected = []
                self.ed.selection_changed()
            return
        if add:
            if hit in self.selected:
                self.selected.remove(hit)
            else:
                self.selected.append(hit)
        elif hit not in self.selected:
            self.selected = [hit]
        self.ed.selection_changed()
        self.start_drag(hit, p)

    def start_drag(self, hit: int, p: QPointF) -> None:
        sk = self.ed.sketch
        x, y = self.to_doc(p)
        if hit in sk.points:
            self.drag = {hit: (sk.points[hit][0] - x, sk.points[hit][1] - y)}
        elif hit in sk.lines:
            v = sk.lines[hit]
            self.drag = {k: (sk.points[k][0] - x, sk.points[k][1] - y) for k in (v['p'], v['q'])}
        else:
            self.drag = {hit: 0.0}
        self.drag_from = sk.to_dict()

    def press_draw(self, p: QPointF) -> None:
        click = self.snap(p)
        if self.tool == 'line':
            if not self.clicks:
                self.clicks = [click]
                return
            start = self.clicks[-1]
            if click[0] is not None and click[0] == start[0]:
                return
            if math.hypot(click[1] - start[1], click[2] - start[2]) < 1e-6:
                return
            self.ed.begin_change()
            sk = self.ed.sketch
            a = self._point(start)
            auto = self._auto_kind(start, click) if self.ed.auto_box.isChecked() and click[0] is None else None
            if auto == 'horizontal':
                click = (None, click[1], start[2])
            elif auto == 'vertical':
                click = (None, start[1], click[2])
            b = self._point(click)
            ln = sk.add_line(a, b, self.ed.construction_box.isChecked())
            if auto:
                sk.add_constraint(auto, ln)
            self.clicks = [(b, *sk.points[b])]
            self.ed.commit()
        elif self.tool == 'rect':
            if not self.clicks:
                self.clicks = [click]
                return
            start = self.clicks[0]
            self.clicks = []
            if abs(click[1] - start[1]) < 1e-6 or abs(click[2] - start[2]) < 1e-6:
                return
            self.ed.begin_change()
            self.ed.sketch.add_rect(start[1], start[2], click[1], click[2])
            self.ed.commit()
        elif self.tool == 'circle':
            if not self.clicks:
                self.clicks = [click]
                return
            start = self.clicks[0]
            self.clicks = []
            r = math.hypot(click[1] - start[1], click[2] - start[2])
            if r < 1e-6:
                return
            self.ed.begin_change()
            self.ed.sketch.add_circle(self._point(start), r, self.ed.construction_box.isChecked())
            self.ed.commit()
        elif self.tool == 'arc':
            self.clicks.append(click)
            if len(self.clicks) < 3:
                return
            c, a, b = self.clicks
            self.clicks = []
            ra = math.hypot(a[1] - c[1], a[2] - c[2])
            if ra < 1e-6 or math.hypot(b[1] - c[1], b[2] - c[2]) < 1e-6:
                return
            self.ed.begin_change()
            sk = self.ed.sketch
            ang = math.atan2(b[2] - c[2], b[1] - c[1])
            if b[0] is None:                             # le bout tombe sur le cercle ; un point existant reste où il est
                b = (None, c[1] + ra * math.cos(ang), c[2] + ra * math.sin(ang))
            ccw = (a[1] - c[1]) * (b[2] - c[2]) - (a[2] - c[2]) * (b[1] - c[1]) >= 0
            sk.add_arc(self._point(c), self._point(a), self._point(b), ccw, self.ed.construction_box.isChecked())
            self.ed.commit()

    @staticmethod
    def _auto_kind(a: tuple, b: tuple):
        dx, dy = abs(b[1] - a[1]), abs(b[2] - a[2])
        if math.degrees(math.atan2(dy, dx)) <= _AUTO_DEG:
            return 'horizontal'
        if math.degrees(math.atan2(dx, dy)) <= _AUTO_DEG:
            return 'vertical'
        return None

    def mouseMoveEvent(self, ev) -> None:
        p = ev.position()
        self.cursor = p
        if self.pan_from is not None:
            at, ox, oy = self.pan_from
            self.ox, self.oy = ox + p.x() - at.x(), oy + p.y() - at.y()
        elif self.drag is not None and ev.buttons() & Qt.MouseButton.LeftButton:
            self.drag_to(p)
        self.update()

    def drag_to(self, p: QPointF) -> None:
        sk = self.ed.sketch
        x, y = self.to_doc(p)
        hold: dict = {}
        for k, off in self.drag.items():
            if k in sk.points:
                hold[k] = (x + off[0], y + off[1])
            else:
                cx, cy = sk.points[sk.circles[k]['c']]
                hold[k] = max(1e-3, math.hypot(x - cx, y - cy))
        sk.solve(hold=hold, analyse=False)

    def mouseReleaseEvent(self, ev) -> None:
        if ev.button() == Qt.MouseButton.MiddleButton:
            self.pan_from = None
            return
        if self.drag is not None and ev.button() == Qt.MouseButton.LeftButton:
            before, self.drag, self.drag_from = self.drag_from, None, None
            if before != self.ed.sketch.to_dict():
                self.ed.undo_stack.append(before)
                self.ed.redo_stack.clear()
                self.ed.refresh()

    def mouseDoubleClickEvent(self, ev) -> None:
        p = ev.position()
        for box, c in self.labels:
            if box.contains(p):
                self.ed.edit_value(c)
                return
        if self.tool == 'line':
            self.clicks = []
            self.update()

    def wheelEvent(self, ev) -> None:
        p = ev.position()
        x, y = self.to_doc(p)
        self.k = max(1e-3, min(1e4, self.k * (1.2 if ev.angleDelta().y() > 0 else 1 / 1.2)))
        self.ox, self.oy = p.x() - x * self.k, p.y() + y * self.k
        self.update()

    def cancel(self) -> bool:
        """La forme en cours, puis l'outil ; rien à annuler : False."""
        if self.clicks:
            self.clicks = []
        elif self.tool != 'select':
            self.ed.set_tool('select')
        else:
            return False
        self.update()
        return True

    def keyPressEvent(self, ev) -> None:
        if ev.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.ed.delete_selection()
        elif ev.key() == Qt.Key.Key_Escape:
            self.cancel()
        else:
            super().keyPressEvent(ev)

    # --- dessin ----------------------------------------------------------------------------------------------------
    def _pen(self, eid: int, free: bool, construction: bool) -> QPen:
        hot = eid in self.selected or eid in self.ed.shown_refs
        color = QColor('#e07b00') if hot else QColor('#2a6fdb') if free else self.palette().text().color()
        if construction and not hot:
            color = QColor(140, 140, 140)
        pen = QPen(color, 2.4 if hot else 1.5)
        if construction:
            pen.setStyle(Qt.PenStyle.DashLine)
        return pen

    def paintEvent(self, _ev) -> None:
        qp = QPainter(self)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing)
        qp.fillRect(self.rect(), self.palette().base())
        sk = self.ed.sketch
        rep = self.ed.report
        qp.setPen(QPen(QColor(150, 150, 150, 120), 1))
        o = self.to_screen(0, 0)
        qp.drawLine(QPointF(o.x(), 0), QPointF(o.x(), self.height()))
        qp.drawLine(QPointF(0, o.y()), QPointF(self.width(), o.y()))
        for k, v in sk.lines.items():
            free = v['p'] in rep.free_points or v['q'] in rep.free_points
            qp.setPen(self._pen(k, free, v['construction']))
            qp.drawLine(self.to_screen(*sk.points[v['p']]), self.to_screen(*sk.points[v['q']]))
        for k, v in sk.circles.items():
            free = v['c'] in rep.free_points or k in rep.free_radii
            qp.setPen(self._pen(k, free, v['construction']))
            c = self.to_screen(*sk.points[v['c']])
            r = v['r'] * self.k
            box = QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r)
            if v['a'] is None:
                qp.drawEllipse(box)
            else:
                start, sweep = sk._arc_angles(v)
                qp.drawArc(box, int(start * 16), int(sweep * 16))
        for k, (x, y) in sk.points.items():
            q = self.to_screen(x, y)
            hot = k in self.selected or k in self.ed.shown_refs
            color = QColor('#e07b00') if hot else QColor('#2a6fdb') if k in rep.free_points else self.palette().text().color()
            qp.setPen(Qt.PenStyle.NoPen)
            qp.setBrush(color)
            qp.drawEllipse(q, 3.0, 3.0)
        qp.setBrush(Qt.BrushStyle.NoBrush)
        self._paint_constraints(qp)
        self._paint_preview(qp)
        qp.end()

    def _anchor(self, c: SK.Constraint) -> QPointF:
        """Où écrire une contrainte : près de ce qu'elle tient."""
        sk = self.ed.sketch
        r = c.refs[-1] if c.kind in ('midpoint', 'on_line', 'on_circle', 'point_line') else c.refs[0]
        if r in sk.points:
            return self.to_screen(*sk.points[r])
        if r in sk.lines:
            v = sk.lines[r]
            a, b = self.to_screen(*sk.points[v['p']]), self.to_screen(*sk.points[v['q']])
            return QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2)
        v = sk.circles[r]
        c0 = self.to_screen(*sk.points[v['c']])
        return QPointF(c0.x() + v['r'] * self.k * 0.71, c0.y() - v['r'] * self.k * 0.71)

    def _paint_constraints(self, qp: QPainter) -> None:
        self.labels = []
        used: dict = {}
        fm = qp.fontMetrics()
        for c in self.ed.sketch.constraints:
            at = self._anchor(c)
            key = (round(at.x()), round(at.y()))
            shift = used.get(key, 0)
            used[key] = shift + 1
            valued = SK.KINDS[c.kind][1] and c.kind != 'fix'
            text = value_text(c) if valued else _GLYPHS.get(c.kind, '?')
            w = fm.horizontalAdvance(text) + 6
            box = QRectF(at.x() + 6 + shift * (w + 2), at.y() - fm.height() - 3, w, fm.height() + 2)
            hot = c.id in self.ed.shown_constraints
            qp.fillRect(box, QColor(255, 225, 190, 235) if hot else QColor(255, 255, 255, 215))
            qp.setPen(QColor('#b0300a') if hot else QColor('#7a4a00') if valued else QColor('#3b6e3b'))
            qp.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
            if valued:
                self.labels.append((box, c))

    def _paint_preview(self, qp: QPainter) -> None:
        if not self.clicks or self.cursor is None:
            return
        qp.setPen(QPen(QColor('#e07b00'), 1, Qt.PenStyle.DashLine))
        last = self.clicks[-1]
        a = self.to_screen(last[1], last[2])
        if self.tool == 'rect':
            qp.drawRect(QRectF(a, self.cursor))
        elif self.tool == 'circle':
            r = math.hypot(self.cursor.x() - a.x(), self.cursor.y() - a.y())
            qp.drawEllipse(a, r, r)
        else:
            qp.drawLine(a, self.cursor)


class SketchEditor(QDialog):
    """`sketch` : l'esquisse à retoucher, gardée intacte tant qu'on n'a pas validé. `ignored` : morceaux que la reprise
    d'un dessin n'a pas su garder, dit une fois à l'ouverture."""

    def __init__(self, parent, sketch: SK.Sketch | None = None, ignored: int = 0):
        super().__init__(parent)
        from .fit import no_hscroll
        no_hscroll(self)
        self.setWindowTitle(tr('Esquisse contrainte'))
        self.setSizeGripEnabled(True)
        self.sketch = sketch.copy() if sketch is not None else SK.Sketch()
        self.undo_stack: list = []
        self.redo_stack: list = []
        self.pending = None
        self.report = SK.Report()
        self.shown_refs: set = set()
        self.shown_constraints: set = set()
        self.message = tr('{0} morceau(x) de courbe laissé(s) de côté : l’esquisse ne garde que les traits et les arcs.').format(
            ignored) if ignored else ''

        self.view = SketchView(self)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.auto_box = QCheckBox(tr('Horizontal et vertical automatiques'))
        self.auto_box.setToolTip(tr('Un trait presque droit se pose droit et le reste'))
        self.auto_box.setChecked(True)
        self.construction_box = QCheckBox(tr('Construction'))
        self.construction_box.setToolTip(tr('Ce qu’on dessine alors guide les autres, sans aller au tracé'))

        self.tool_buttons: dict = {}
        tools = QGridLayout()
        for k, (key, label, tip) in enumerate((
                ('select', tr('Choisir'), tr('Choisir et tirer ; Ctrl pour en choisir plusieurs')),
                ('line', tr('Trait'), tr('Clic après clic ; double-clic ou Échap pour finir')),
                ('rect', tr('Rectangle'), tr('Deux coins')),
                ('circle', tr('Cercle'), tr('Le centre, puis un point du cercle')),
                ('arc', tr('Arc'), tr('Le centre, le départ, l’arrivée')))):
            b = QPushButton(label)
            b.setToolTip(tip)
            b.setCheckable(True)
            b.setAutoDefault(False)
            b.clicked.connect(lambda _c=False, t=key: self.set_tool(t))
            self.tool_buttons[key] = b
            tools.addWidget(b, k // 3, k % 3)
        group_tools = QGroupBox(tr('Dessiner'))
        lay = QVBoxLayout(group_tools)
        lay.addLayout(tools)
        lay.addWidget(self.auto_box)
        lay.addWidget(self.construction_box)
        toggle = QPushButton(tr('Construction ou tracé'))
        toggle.setToolTip(tr('Faire passer la sélection de construction à tracé, ou l’inverse'))
        toggle.setAutoDefault(False)
        toggle.clicked.connect(lambda _c=False: self.toggle_construction())
        lay.addWidget(toggle)

        self.rule_buttons: dict = {}
        rules = QGridLayout()
        for k, (key, label, tip) in enumerate((
                ('coincident', tr('Coïncident'), tr('Deux points ; ou un point et un trait, un point et un cercle')),
                ('horizontal', tr('Horizontal'), tr('Des traits, ou deux points')),
                ('vertical', tr('Vertical'), tr('Des traits, ou deux points')),
                ('parallel', tr('Parallèle'), tr('Deux traits ou plus')),
                ('perpendicular', tr('Perpendiculaire'), tr('Deux traits')),
                ('collinear', tr('Dans l’axe'), tr('Deux traits')),
                ('tangent', tr('Tangent'), tr('Un trait et un cercle, ou deux cercles')),
                ('equal', tr('Égal'), tr('Des traits, ou des cercles')),
                ('concentric', tr('Concentrique'), tr('Deux cercles')),
                ('midpoint', tr('Milieu'), tr('Un point et un trait')),
                ('symmetric', tr('Symétrique'), tr('Deux points et l’axe')),
                ('fix', tr('Fixe'), tr('Des points, ou des traits : ils ne bougeront plus')))):
            b = QPushButton(label)
            b.setToolTip(tip)
            b.setAutoDefault(False)
            b.clicked.connect(lambda _c=False, r=key: self.apply_rule(r))
            self.rule_buttons[key] = b
            rules.addWidget(b, k // 3, k % 3)
        group_rules = QGroupBox(tr('Contraintes'))
        group_rules.setLayout(rules)

        self.dim_buttons: dict = {}
        dims = QGridLayout()
        for k, (key, label, tip) in enumerate((
                ('auto', tr('Cote'), tr('Un trait : longueur ; un cercle : rayon ; deux points : distance ; un point et un trait : distance ; deux traits : angle')),
                ('diameter', tr('Diamètre'), tr('Un cercle')),
                ('distance_x', tr('En X'), tr('Deux points')),
                ('distance_y', tr('En Y'), tr('Deux points')))):
            b = QPushButton(label)
            b.setToolTip(tip)
            b.setAutoDefault(False)
            b.clicked.connect(lambda _c=False, r=key: self.add_dimension(r))
            self.dim_buttons[key] = b
            dims.addWidget(b, 0, k)
        group_dims = QGroupBox(tr('Cotes'))
        group_dims.setLayout(dims)

        self.listing = QListWidget()
        self.listing.currentRowChanged.connect(lambda _r: self.constraint_chosen())
        self.listing.itemDoubleClicked.connect(lambda it: self.edit_value(self.constraint_of(it)))
        remove = QPushButton(tr('Retirer'))
        remove.setToolTip(tr('Retirer la contrainte choisie dans la liste, ou ce qui est sélectionné dans le dessin'))
        remove.setAutoDefault(False)
        remove.clicked.connect(lambda _c=False: self.delete_selection())
        fit = QPushButton(tr('Tout voir'))
        fit.setAutoDefault(False)
        fit.clicked.connect(lambda _c=False: self.view.fit())
        row = QHBoxLayout()
        row.addWidget(remove)
        row.addWidget(fit)

        side = QVBoxLayout()
        side.addWidget(group_tools)
        side.addWidget(group_rules)
        side.addWidget(group_dims)
        side.addWidget(self.listing, 1)
        side.addLayout(row)
        host = QWidget()
        host.setLayout(side)
        host.setMaximumWidth(400)
        top = QHBoxLayout()
        top.addWidget(host)
        top.addWidget(self.view, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.finish)
        buttons.rejected.connect(self.reject)
        whole = QVBoxLayout(self)
        whole.addLayout(top, 1)
        whole.addWidget(self.status)
        whole.addWidget(buttons)
        QShortcut(QKeySequence.StandardKey.Undo, self, activated=self.undo)
        QShortcut(QKeySequence.StandardKey.Redo, self, activated=self.redo)
        self.resize(1120, 760)
        self.set_tool('select')
        self.refresh()

    # --- modifications ---------------------------------------------------------------------------------------------
    def begin_change(self) -> None:
        self.pending = self.sketch.to_dict()

    def commit(self) -> None:
        """Valide le changement commencé : résolu, sinon rendu tel qu'il était ; rend le rapport."""
        rep = self.sketch.solve()
        if not rep.ok:
            names = [self._describe(c) for c in self.sketch.constraints if c.id in rep.conflicts]
            self.shown_constraints = set(rep.conflicts)
            self.sketch = SK.Sketch.from_dict(self.pending)
            self.pending = None
            self.refresh(keep_message=True)
            self.message = tr('Refusé : cela contredirait {0}.').format(', '.join(names) or tr('les autres contraintes'))
            self._show_status()
            self.view.update()
            return rep
        self.undo_stack.append(self.pending)
        self.redo_stack.clear()
        self.pending = None
        self.shown_constraints = set()
        self.message = ''
        self.refresh()
        return rep

    def undo(self) -> None:
        if self.undo_stack:
            self.redo_stack.append(self.sketch.to_dict())
            self.sketch = SK.Sketch.from_dict(self.undo_stack.pop())
            self.view.selected = []
            self.refresh()

    def redo(self) -> None:
        if self.redo_stack:
            self.undo_stack.append(self.sketch.to_dict())
            self.sketch = SK.Sketch.from_dict(self.redo_stack.pop())
            self.view.selected = []
            self.refresh()

    def refresh(self, keep_message: bool = False) -> None:
        self.report = self.sketch.solve()
        if not keep_message and self.report.ok:
            self.message = self.message if self.message and not self.undo_stack else ''
        self.view.selected = [k for k in self.view.selected if self._exists(k)]
        self.fill_list()
        self.selection_changed()
        self._show_status()
        self.view.update()

    def _exists(self, k: int) -> bool:
        s = self.sketch
        return k in s.points or k in s.lines or k in s.circles

    def _show_status(self) -> None:
        rep = self.report
        if not self.sketch.points:
            text = tr('Esquisse vide : choisissez Trait, Rectangle, Cercle ou Arc.')
        elif not rep.ok:
            text = tr('Les contraintes se contredisent.')
        elif rep.dof == 0:
            text = tr('Entièrement contrainte.')
        else:
            text = tr('{0} degré(s) de liberté : ce qui peut encore bouger est en bleu.').format(rep.dof)
        if rep.redundant:
            text += ' ' + tr('{0} contrainte(s) de trop, déjà dite(s) par les autres.').format(len(rep.redundant))
        if self.message:
            text = self.message + '  ' + text
        self.status.setText(text)

    def set_tool(self, tool: str) -> None:
        self.view.tool = tool
        self.view.clicks = []
        for k, b in self.tool_buttons.items():
            b.setChecked(k == tool)
        self.view.setCursor(Qt.CursorShape.ArrowCursor if tool == 'select' else Qt.CursorShape.CrossCursor)
        self.view.update()

    # --- sélection -------------------------------------------------------------------------------------------------
    def _split(self) -> tuple[list, list, list]:
        s = self.sketch
        sel = self.view.selected
        return [k for k in sel if k in s.points], [k for k in sel if k in s.lines], [k for k in sel if k in s.circles]

    def _rule_refs(self, rule: str) -> list[tuple]:
        """Les contraintes qu'une règle donnerait sur la sélection : [(nature, références…)]."""
        p, ln, c = self._split()
        n = (len(p), len(ln), len(c))
        if rule == 'coincident':
            return [('coincident', p[0], p[1])] if n == (2, 0, 0) else [('on_line', p[0], ln[0])] if n == (1, 1, 0) else \
                [('on_circle', p[0], c[0])] if n == (1, 0, 1) else []
        if rule in ('horizontal', 'vertical'):
            if ln and not p and not c:
                return [(rule, k) for k in ln]
            return [('h_points' if rule == 'horizontal' else 'v_points', p[0], p[1])] if n == (2, 0, 0) else []
        if rule in ('parallel', 'perpendicular', 'collinear'):
            if rule == 'parallel' and len(ln) >= 2 and not p and not c:
                return [(rule, ln[0], k) for k in ln[1:]]
            return [(rule, ln[0], ln[1])] if n == (0, 2, 0) else []
        if rule == 'tangent':
            return [('tangent_lc', ln[0], c[0])] if n == (0, 1, 1) else [('tangent_cc', c[0], c[1])] if n == (0, 0, 2) else []
        if rule == 'equal':
            if len(ln) >= 2 and not p and not c:
                return [('equal_ll', ln[0], k) for k in ln[1:]]
            return [('equal_cc', c[0], k) for k in c[1:]] if len(c) >= 2 and not p and not ln else []
        if rule == 'concentric':
            return [('concentric', c[0], c[1])] if n == (0, 0, 2) else []
        if rule == 'midpoint':
            return [('midpoint', p[0], ln[0])] if n == (1, 1, 0) else []
        if rule == 'symmetric':
            return [('symmetric', p[0], p[1], ln[0])] if n == (2, 1, 0) else []
        if rule == 'fix':
            if c:
                return []
            pts = list(p)
            for k in ln:
                v = self.sketch.lines[k]
                pts += [q for q in (v['p'], v['q']) if q not in pts]
            return [('fix', q) for q in pts]
        return []

    def _dim_kind(self, rule: str) -> tuple | None:
        p, ln, c = self._split()
        n = (len(p), len(ln), len(c))
        if rule == 'diameter':
            return ('diameter', c[0]) if n == (0, 0, 1) else None
        if rule in ('distance_x', 'distance_y'):
            return (rule, p[0], p[1]) if n == (2, 0, 0) else None
        return ('length', ln[0]) if n == (0, 1, 0) else ('radius', c[0]) if n == (0, 0, 1) else \
            ('distance', p[0], p[1]) if n == (2, 0, 0) else ('point_line', p[0], ln[0]) if n == (1, 1, 0) else \
            ('angle', ln[0], ln[1]) if n == (0, 2, 0) else None

    def selection_changed(self) -> None:
        for key, b in self.rule_buttons.items():
            b.setEnabled(bool(self._rule_refs(key)))
        for key, b in self.dim_buttons.items():
            b.setEnabled(self._dim_kind(key) is not None)
        self.shown_refs = set()
        self.view.update()

    def constraint_of(self, item: QListWidgetItem):
        k = item.data(Qt.ItemDataRole.UserRole)
        return next((c for c in self.sketch.constraints if c.id == k), None)

    def constraint_chosen(self) -> None:
        it = self.listing.currentItem()
        c = self.constraint_of(it) if it is not None else None
        self.shown_refs = set(c.refs) if c is not None else set()
        self.view.update()

    # --- contraintes et cotes --------------------------------------------------------------------------------------
    def apply_rule(self, rule: str) -> SK.Report | None:
        refs = self._rule_refs(rule)
        if not refs:
            return None
        self.begin_change()
        for kind, *r in refs:
            self.sketch.add_constraint(kind, *r)
        return self.commit()

    def ask_value(self, title: str, value: float) -> float | None:
        v, ok = QInputDialog.getDouble(self, tr('Esquisse contrainte'), title, value, -1e7, 1e7, 4)
        return v if ok else None

    def add_dimension(self, rule: str = 'auto', value: float | None = None) -> SK.Report | None:
        """La cote de la sélection ; proposée à sa valeur du moment."""
        got = self._dim_kind(rule)
        if got is None:
            return None
        kind, *refs = got
        probe = SK.Constraint(0, kind, tuple(refs), 0.0)
        now = abs(self.sketch.value_of(probe))
        if value is None:
            value = self.ask_value(kind_label(kind), round(now, 4))
            if value is None:
                return None
        self.begin_change()
        self.sketch.add_constraint(kind, *refs, value=abs(float(value)))
        return self.commit()

    def edit_value(self, c, value: float | None = None) -> SK.Report | None:
        """Change une cote."""
        if c is None or not SK.KINDS[c.kind][1] or c.kind == 'fix':
            return None
        if value is None:
            value = self.ask_value(kind_label(c.kind), float(c.value))
            if value is None:
                return None
        self.begin_change()
        next(o for o in self.sketch.constraints if o.id == c.id).value = abs(float(value))
        return self.commit()

    def delete_selection(self) -> None:
        """La contrainte choisie dans la liste si la liste a la main, sinon ce qui est sélectionné dans le dessin."""
        sel = list(self.view.selected)
        it = self.listing.currentItem()
        c = self.constraint_of(it) if it is not None and (self.listing.hasFocus() or not sel) else None
        if c is None and not sel:
            return
        self.begin_change()
        if c is not None:
            self.sketch.remove(c.id)
        else:
            for k in sel:
                if self._exists(k):
                    self.sketch.remove(k)
            self.view.selected = []
        self.commit()

    def toggle_construction(self) -> None:
        _p, ln, c = self._split()
        if not ln and not c:
            return
        self.begin_change()
        for k in ln:
            self.sketch.lines[k]['construction'] = not self.sketch.lines[k]['construction']
        for k in c:
            self.sketch.circles[k]['construction'] = not self.sketch.circles[k]['construction']
        self.commit()

    # --- liste -----------------------------------------------------------------------------------------------------
    def _name(self, r: int) -> str:
        s = self.sketch
        if r in s.points:
            return tr('point {0}').format(r)
        if r in s.lines:
            return tr('trait {0}').format(r)
        return tr('cercle {0}').format(r)

    def _describe(self, c: SK.Constraint) -> str:
        text = kind_label(c.kind)
        if SK.KINDS[c.kind][1] and c.kind != 'fix':
            text += ' ' + value_text(c)
        return text + ' (' + ', '.join(self._name(r) for r in c.refs) + ')'

    def fill_list(self) -> None:
        self.listing.blockSignals(True)
        self.listing.clear()
        for c in self.sketch.constraints:
            text = self._describe(c)
            if c.id in self.report.redundant:
                text += ' — ' + tr('de trop')
            it = QListWidgetItem(text)
            it.setData(Qt.ItemDataRole.UserRole, c.id)
            self.listing.addItem(it)
        self.listing.setCurrentRow(-1)
        self.listing.blockSignals(False)

    # --- fin -------------------------------------------------------------------------------------------------------
    def finish(self) -> None:
        if not self.sketch.to_path().contours:
            QMessageBox.information(self, tr('Esquisse contrainte'), tr('Cette esquisse ne donne aucun tracé.'))
            return
        self.accept()

    def keyPressEvent(self, ev) -> None:
        if ev.key() == Qt.Key.Key_Escape:                # Échap arrête le tracé, jamais la fenêtre
            self.view.cancel()
            return
        super().keyPressEvent(ev)
