"""Plan de travail : affichage, zoom, sélection, déplacement, outils.

Repère du document : mm, Y vers le haut. Repère écran : pixels, Y vers le
bas. `view` = transformation document → écran (échelle + décalage).

Le rendu passe par QPainter avec un cache de `QPainterPath` par objet ;
un moteur GPU (QRhi) prendra le relais pour les très gros fichiers.
"""
from __future__ import annotations

import math
import weakref

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (QBrush, QFont, QPolygonF, QColor, QKeyEvent, QMouseEvent, QPainter,
                           QPainterPath, QPainterPathStroker, QPen, QPixmap, QTransform,
                           QWheelEvent)
from PySide6.QtWidgets import QWidget

from ..core import geom
from ..core.document import Document, Group, Image, Item, Shape, Text
from ..core.geom import Affine, Conic, Cubic, Line, Path
from ..core.snap import LABELS as SNAP_LABELS, Snap
from .theme import canvas_colors, ink

HANDLE_PX = 7
#: glisser-déposer de la sélection du dessin (vers la Bibliothèque) : le contenu est la sélection elle-même
SELECTION_MIME = 'application/x-vectordrive-selection'


def selection_token() -> bytes:
    """Ce que porte le glisser-déposer de la sélection : cette instance. Venu d'une autre, il est refusé (la
    sélection à enregistrer ou à déplacer n'est pas la sienne)."""
    import os
    return str(os.getpid()).encode('ascii')


def own_selection_drag(ev) -> bool:
    """Un glisser-déposer de la sélection du dessin parti de cette instance ?"""
    md = ev.mimeData()
    return md.hasFormat(SELECTION_MIME) and bytes(md.data(SELECTION_MIME)) == selection_token()


PICK_PX = 5
#: rectangle de sélection tiré du bas vers le haut (sélectionne ce qu'il touche)
CROSSING_COLOR = '#2e9e4f'


def canvas_background(cc: dict, height: int):
    """Fond du plan de travail : uni, ou dégradé vertical (bg vers bg2)."""
    from PySide6.QtGui import QBrush, QLinearGradient
    if cc.get('bg2') and cc['bg2'] != cc['bg']:
        g = QLinearGradient(0, 0, 0, max(1, height))
        g.setColorAt(0, QColor(cc['bg']))
        g.setColorAt(1, QColor(cc['bg2']))
        return QBrush(g)
    return QColor(cc['bg'])


def conic_cubics_fast(c: Conic, tol: float = 1e-3) -> list:
    """Cubiques d'un arc conique (w < 1 : arc d'ellipse ou de cercle) pour
    l'affichage, sans recherche adaptative : coupes au milieu exactes
    (w' = √((1 + w) / 2)) autant que l'erreur estimée (rayon × θ⁶ / 55 000,
    θ l'angle de l'arc) l'exige, puis une cubique par morceau, points de
    contrôle à 4w / (3(1 + w)) des tangentes. Rend des quadruplets de points."""
    w = c.w
    if not 0.0 < w < 1.0:
        return [(cb.p0, cb.p1, cb.p2, cb.p3) for cb in c.to_cubics(tol)]
    p0, p1, p2 = c.p0, c.p1, c.p2
    theta = 2.0 * math.acos(w)
    sh = math.sin(theta / 2)
    chord = math.hypot(p2[0] - p0[0], p2[1] - p0[1])
    r = chord / (2.0 * sh) if sh > 1e-12 else 0.0
    err = r * theta ** 6 / 55000.0
    depth = 0
    while err > tol and depth < 6:
        err /= 64.0                                   # θ moitié : θ⁶ / 64
        depth += 1
    pieces = [(p0, p1, p2, w)]
    for _ in range(depth):
        nxt = []
        for a0, a1, a2, ww in pieces:
            k = 1.0 + ww
            m1 = ((a0[0] + ww * a1[0]) / k, (a0[1] + ww * a1[1]) / k)
            m2 = ((ww * a1[0] + a2[0]) / k, (ww * a1[1] + a2[1]) / k)
            mid = ((a0[0] + 2 * ww * a1[0] + a2[0]) / (2 * k), (a0[1] + 2 * ww * a1[1] + a2[1]) / (2 * k))
            w2 = math.sqrt(k / 2.0)
            nxt += [(a0, m1, mid, w2), (mid, m2, a2, w2)]
        pieces = nxt
    out = []
    for a0, a1, a2, ww in pieces:
        f = 4.0 * ww / (3.0 * (1.0 + ww))
        out.append((a0, (a0[0] + f * (a1[0] - a0[0]), a0[1] + f * (a1[1] - a0[1])),
                    (a2[0] + f * (a1[0] - a2[0]), a2[1] + f * (a1[1] - a2[1])), a2))
    return out


def to_qpath(p: Path) -> QPainterPath:
    q = QPainterPath()
    q.setFillRule(Qt.FillRule.OddEvenFill)
    for c in p.contours:
        if not c.segments:
            continue
        q.moveTo(*c.start)
        for s in c.segments:
            if isinstance(s, Line):
                q.lineTo(*s.p1)
            elif isinstance(s, Cubic):
                q.cubicTo(*s.p1, *s.p2, *s.p3)
            elif isinstance(s, Conic):
                if abs(s.w - 1) < 1e-12:
                    q.quadTo(*s.p1, *s.p2)
                else:
                    for _a, c1, c2, c3 in conic_cubics_fast(s, 1e-3):
                        q.cubicTo(*c1, *c2, *c3)
        if c.closed:
            q.closeSubpath()
    return q


def dib_to_qimage(data: bytes):
    """DIB (BITMAPINFOHEADER + palette + pixels) → QImage, via un en-tête
    de fichier BMP reconstitué."""
    import struct
    from PySide6.QtGui import QImage
    if len(data) < 40:
        return None
    hsize, _w, _h, _pl, bpp, _comp, _sz, _x, _y, clr_used = struct.unpack_from('<IiiHHIIiiI', data, 0)
    ncol = clr_used or (1 << bpp if bpp <= 8 else 0)
    off = 14 + hsize + 4 * ncol
    bmp = b'BM' + struct.pack('<IHHI', 14 + len(data), 0, 0, off) + data
    img = QImage()
    img.loadFromData(bmp, 'BMP')
    return None if img.isNull() else img


def item_path(it: Item) -> Path | None:
    if isinstance(it, Shape):
        return it.path
    if isinstance(it, Text):
        if it.outline is None:
            _late_outline(it)
        return it.outline
    return None


#: textes restés sans tracé (police absente ou illisible) : {id : (réf. faible, police, chaîne)} — pas d'essai à chaque
#: rendu, un nouvel essai si la police ou la chaîne change
_NO_OUTLINE: dict = {}


def _late_outline(t: Text) -> None:
    """Texte lu sans tracé (DXF, conversion…) : tracé au premier affichage et gardé dans le texte (demande du 15/11 :
    les cotes des dessins d'outils ne s'affichaient pas). Police absente : rien — pas de police de remplacement ici,
    le texte passe par `missing_fonts` (VD Géo dans une copie de son calque)."""
    if not (t.text or '').strip():
        return
    got = _NO_OUTLINE.get(id(t))
    if got is not None and got[0]() is t and got[1:] == (t.font, t.text):
        return
    from ..core import missing_fonts as MF
    from ..core import text as TX
    try:
        if not MF.absent(t):
            t.outline = TX.outline_for(t)
    except Exception:                                    # noqa: BLE001 — police illisible : le texte reste sans tracé
        pass
    if t.outline is None:
        if len(_NO_OUTLINE) > 20000:
            _NO_OUTLINE.clear()
        _NO_OUTLINE[id(t)] = (weakref.ref(t), t.font, t.text)


def _cull_rect(q: QPainterPath) -> QRectF:
    """Rectangle de tri à l'affichage, jamais plat : `QRectF.intersects` est faux pour un rectangle sans largeur ou sans
    hauteur — un trait seul horizontal ou vertical (ligne de cote, axe) n'était pas dessiné (demande du 15/11)."""
    r = q.controlPointRect()
    if r.width() <= 0 or r.height() <= 0:
        e = 1e-6 * max(1.0, r.width(), r.height(), abs(r.x()), abs(r.y()))
        r = r.adjusted(-e, -e, e, e)
    return r


def _polyline_touches(P, rect) -> bool:
    """La polyligne (tableau n × 2) entre-t-elle dans le rectangle ou le
    traverse-t-elle ? Un segment coupe le rectangle si leurs encombrements
    se chevauchent et que les quatre coins ne sont pas tous du même côté."""
    import numpy as np
    x0, y0, x1, y1 = rect
    if ((P[:, 0] >= x0) & (P[:, 0] <= x1) & (P[:, 1] >= y0) & (P[:, 1] <= y1)).any():
        return True
    A, B = P[:-1], P[1:]
    m = ((np.minimum(A[:, 0], B[:, 0]) <= x1) & (np.maximum(A[:, 0], B[:, 0]) >= x0)
         & (np.minimum(A[:, 1], B[:, 1]) <= y1) & (np.maximum(A[:, 1], B[:, 1]) >= y0))
    if not m.any():
        return False
    A, B = A[m], B[m]
    dx, dy = B[:, 0] - A[:, 0], B[:, 1] - A[:, 1]
    s = np.stack([dx * (cy - A[:, 1]) - dy * (cx - A[:, 0])
                  for cx, cy in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))], axis=1)
    return bool(((s.min(1) <= 0) & (s.max(1) >= 0)).any())


def touches_rect(item: Item, rect, tol: float = 0.01) -> bool:
    """L'objet touche-t-il le rectangle (x0, y0, x1, y1) en mm : un de ses
    traits y entre ou le traverse (`tol` : aplatissement des courbes) ;
    objet plein : le rectangle est dans sa surface ; image : encombrement."""
    import numpy as np
    x0, y0, x1, y1 = rect
    for leaf in _leaves([item], visible_only=True):
        if isinstance(leaf, Image):
            b = leaf.bbox()
            if b and b[0] <= x1 and b[2] >= x0 and b[1] <= y1 and b[3] >= y0:
                return True
            continue
        p = item_path(leaf)
        if not p:
            continue
        for c in p.contours:
            if not c.segments:
                continue
            b = c.bbox()
            if b[0] > x1 or b[2] < x0 or b[1] > y1 or b[3] < y0:
                continue
            if x0 <= b[0] and b[2] <= x1 and y0 <= b[1] and b[3] <= y1:
                return True
            if _polyline_touches(np.asarray(c.flatten(tol), float), rect):
                return True
        if getattr(leaf, 'filled', False) and to_qpath(p).contains(QPointF((x0 + x1) / 2, (y0 + y1) / 2)):
            return True
    return False


class Canvas(QWidget):
    cursorMoved = Signal(float, float)
    snapMoved = Signal(float, float, str)   # point accroché (sinon le pointeur) et sa nature ('' : aucune)
    selectionChanged = Signal()
    documentChanged = Signal()
    toolFinished = Signal()
    fileDropped = Signal(str, float, float)
    textRequested = Signal(float, float)
    itemDoubleClicked = Signal(object)
    noteDoubleClicked = Signal(int)         # indice de la note (post-it)
    measured = Signal(str)            # résultat de l'outil de mesure
    viewChanged = Signal()            # zoom ou panoramique (règles)
    guideDoubleClicked = Signal(int)
    obliqueDoubleClicked = Signal(int)
    arrowStepChanged = Signal(float)  # pas des flèches saisi (0 : pas des options)
    toolExitRequested = Signal()      # clic droit (sans glisser) dans un mode : retour à la sélection
    rightClicked = Signal(str)        # clic droit (sans glisser) en sélection : action réglée (F5)
    stepRequested = Signal(int, int)  # Ctrl+flèche : demander le pas, puis déplacer dans ce sens (dx, dy)
    originChanged = Signal()          # origine du dessin déplacée

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._hover_pos = None            # dernière position du pointeur survolant la vue (sans bouton)
        self.selectionChanged.connect(self._hover_cursor_after_change)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setAcceptDrops(True)
        self.doc = Document()
        self.scale = 3.0                  # px par mm
        self._views: list = []             # vues précédentes (zoom précédent)
        self._view_t = 0.0
        self.ox, self.oy = 60.0, 600.0    # position écran de l'origine
        self.selection: list[Item] = []
        self.tool = 'select'
        self.nudge_mm = 1.0
        self.arrow_step = None             # pas des flèches saisi après Ctrl+flèche (None : options)
        self.handle_px = HANDLE_PX         # taille des poignées (options)
        self.highlight_px = 2              # épaisseur du trait des objets sélectionnés (options)
        self.step_gap_mm = 0.0             # écart ajouté à ce pas
        #: maintien du bouton avant qu'un glisser déplace la sélection (ms) :
        #: un clic qui bouge un peu ne déplace rien par mégarde (comme TypeEdit)
        self.move_delay_ms = 250
        #: fonction (point écran) → vrai : un déplacement qui sort de la vue et arrive là part en glisser-déposer
        #: (le pointeur sur une Bibliothèque montrée)
        self.drag_out_ok = None
        self._out_grab = None             # point saisi pendant ce glisser-déposer (le reposer dans la vue : déplacé)
        self.show_direction = False       # Ctrl+7 : contours colorés selon leur sens (sans flèche)
        self.show_arrows = False          # F10 › Affichage : flèche de sens au départ de chaque contour
        self.intuitive_snap = False       # cotation : accrochage aux points même sans F3 (TypeEdit)
        self._intuitive = None
        self.show_starts = False          # points de départ des contours (carrés), comme TypeEdit
        self.show_nodes = False           # points de contrôle de tous les contours (carré : angle, rond : lisse)
        self.show_fill = False
        self.tool_colors = True           # Ctrl+8 : traits à la couleur de leur outil (sinon tous à l'encre)
        self._light_images: dict = {}     # images claires sur fond transparent (affichées sur fond sombre)
        self._orient: dict = {}           # Ctrl+7 : tracés rangés par sens, par objet
        self.show_grid = False
        self.show_origin = True           # repère de l'origine du dessin
        self.origin_preview = None        # origine glissée depuis le coin des règles
        self.engrave_preview = False       # traits à la largeur réelle de l'outil
        self.solo_layer = None             # onglet de calque : id du seul calque affiché
        self.toolpaths: list = []          # FAO : (parcours, couleur) affichés
        self.toolpaths_visible = True       # calque « Trajectoires » (panneau des calques)
        #: points d'intersection repérés (fenêtre « Intersections ») : [(x, y, nature)]
        self.cross_marks: list = []
        #: comparaison de dessins montrée (core.compare.Comparison, voir MainWindow.compare_with) ; None : aucune
        self.compare = None
        self._cmp_q: dict = {}
        self.show_rapids = True
        self._tp_cache: dict = {}
        #: id(tracé) → (tracé, QPainterPath, rectangle). Les tracés ne sont
        #: jamais modifiés en place (un objet modifié reçoit un nouveau
        #: tracé) : l'entrée vaut tant que le tracé existe, et sert aussi aux
        #: copies qui le partagent (annuler / refaire, presse-papiers).
        self._cache: dict[int, tuple] = {}
        self._images: dict[int, object] = {}
        self._drag = None                 # état du geste en cours
        self._last_mouse = QPointF()
        self.undo_push = None             # rappel fourni par la fenêtre
        self.tool_obj = None              # outil interactif (vectordrive.ui.tools)
        self.poly_sides = 6
        #: réglages par défaut des formes paramétrées : type → forme (core.forms)
        self.form_defaults_fn = None
        self.point_dialog_fn = None       # Mode Point : double-clic sur un point (fenêtre principale)
        #: options des prochaines cotes (core.dims.DimStyle)
        self.dim_style_fn = None
        self.star_ratio = 0.5
        self.spiral_turns = 3.0
        self.marker_size = 3.0
        self.symmetric = False            # dessin symétrique (axe vertical au centre de la plaque)
        self.cyclic = 0                   # symétrie cyclique : nombre de copies tournées (0 : sans)
        self.show_notes = True            # notes (post-it) visibles
        self.current_tool_index = 0
        self.dim_text = 3.5
        self.snap = Snap()                # accrochage F3
        self.snap_px = 8
        self._snap_hit = None
        self._tab_held = False                           # Tab enfoncée : échelle depuis le centre (TypeEdit)
        self._snap_cycle = 0                             # Alt : rang du point d'accrochage choisi
        self._snap_cycle_at = None
        self._snap_at = None                             # dernière position accrochée, et ce qu'elle excluait
        self._snap_exclude = ()
        # scène en cache : les repeints dus à la souris (aperçus, accrochage,
        # glissés) ne redessinent que les surimpressions
        self._scene = None
        self._scene_k = None
        self._scene_dirty = True
        #: zoom sur un gros dessin : image de la scène mise à l'échelle tout de
        #: suite, rendu net après une courte pause (`ZOOM_REFINE_MS`)
        self._render_ms = 0.0
        self._force_render = False
        #: vue (échelle, ox, oy) laissée par le dernier « Tout voir » ; None : jamais cadré
        self._fit_view = None
        from PySide6.QtCore import QTimer
        self._refine = QTimer(self)
        self._refine.setSingleShot(True)
        self._refine.setInterval(self.ZOOM_REFINE_MS)
        self._refine.timeout.connect(self._refine_now)
        self._prune = False
        self.rot_mode = False             # second clic sur la sélection : poignées de rotation
        self.rot_knob = True              # le bouton de rotation au-dessus du cadre de la sélection (r1087)
        self.pivot = None                 # centre de rotation déplacé (document) ; None : le milieu de la sélection
        self.frozen_picked = []           # objets gelés désignés au clic : à part de la sélection, rien ne les modifie
        self.guide_preview = None         # guide en cours de création depuis une règle
        self.ruler_dragging = None        # la règle d'où il part, tant que le bouton est enfoncé
        self.oblique_preview = None       # ligne de construction en cours : (x, y, angle)
        self._view_emitted = None

    # --- repères ------------------------------------------------------------
    def view(self) -> QTransform:
        return QTransform(self.scale, 0, 0, -self.scale, self.ox, self.oy)

    def to_doc(self, p: QPointF) -> tuple[float, float]:
        return ((p.x() - self.ox) / self.scale, (self.oy - p.y()) / self.scale)

    def to_screen(self, x: float, y: float) -> QPointF:
        return QPointF(self.ox + x * self.scale, self.oy - y * self.scale)

    def snap_doc(self, pos: QPointF, exclude=(), skip_guide=None, skip_oblique=None) -> tuple[float, float]:
        """Point du document sous `pos`, accroché si F3 est actif ; `skip_guide`, `skip_oblique` : le guide qu'on tire,
        qui ne s'accroche pas à lui-même."""
        x, y = self.to_doc(pos)
        hit = None
        if self.snap.enabled:
            self.snap.guides = self.guides if skip_guide is None else \
                [g for i, g in enumerate(self.guides) if i != skip_guide]
            self.snap.obliques = self.oblique_guides if skip_oblique is None else \
                [g for i, g in enumerate(self.oblique_guides) if i != skip_oblique]
            items = [it for L in self.doc.layers if self.layer_shown(L) for it in L.items if it.visible]
            hit = self.snap.query(x, y, self.snap_px / self.scale, items, exclude=exclude)
            self._snap_at, self._snap_exclude = pos, exclude
            if self._snap_cycle:
                if (pos - self._snap_cycle_at).manhattanLength() > self.SNAP_CYCLE_PX:
                    self._snap_cycle = 0                 # la souris est partie : on repart du plus proche
                else:
                    every = self.snap.query_all(x, y, self.snap_px / self.scale, items, exclude=exclude)
                    if every:
                        hit = every[self._snap_cycle % len(every)]
        elif self.intuitive_snap and getattr(self.tool_obj, 'intuitive_snap', False):
            # accrochage intuitif (TypeEdit) : la cotation s'accroche aux points sans F3
            from ..core.snap import Snap
            if self._intuitive is None:
                self._intuitive = Snap(enabled=True, modes={'node', 'middle', 'center', 'intersection', 'quadrant'})
            items = [it for L in self.doc.layers if self.layer_shown(L) for it in L.items if it.visible]
            hit = self._intuitive.query(x, y, self.snap_px / self.scale, items, exclude=exclude)
        self._snap_hit = hit
        out = (hit.x, hit.y) if hit else (x, y)
        self.snapMoved.emit(out[0], out[1], hit.kind if hit else '')   # la barre d'état montre le point accroché
        return out

    def cycle_snap(self) -> bool:
        """Alt (TypeEdit : multi-accrochage) : le point d'accrochage suivant sous le curseur. Rend True s'il y en a un autre."""
        from ..i18n import tr
        pos = self._snap_at
        if not self.snap.enabled or pos is None:
            return False
        x, y = self.to_doc(pos)
        items = [it for L in self.doc.layers if self.layer_shown(L) for it in L.items if it.visible]
        every = self.snap.query_all(x, y, self.snap_px / self.scale, items, exclude=self._snap_exclude)
        if len(every) < 2:
            return False
        if not self._snap_cycle or (pos - self._snap_cycle_at).manhattanLength() > self.SNAP_CYCLE_PX:
            self._snap_cycle, self._snap_cycle_at = 0, pos
        self._snap_cycle += 1
        k = self._snap_cycle % len(every)
        self.measured.emit(tr('Point d\'accrochage {0} sur {1} : {2} (Alt : suivant)').format(
            k + 1, len(every), tr(SNAP_LABELS.get(every[k].kind, every[k].kind))))
        if self.tool_obj is not None:
            self.tool_obj.move(pos, self.snap_doc(pos, self._tool_exclude()), self._Click(pos))
        else:
            self.snap_doc(pos, self._snap_exclude)
        self.overlay_update()
        return True

    def _tool_exclude(self):
        f = getattr(self.tool_obj, 'snap_exclude', None)
        return f() if f else ()

    # --- guides ---------------------------------------------------------------
    @property
    def guides(self) -> list:
        """Guides du document : [['h', y] | ['v', x]] (mm)."""
        return self.doc.extra.setdefault('guides', [])

    def add_guide(self, axis: str, value: float) -> None:
        if self.undo_push:
            self.undo_push()
        self.guides.append([axis, float(value)])
        self.documentChanged.emit()
        self.overlay_update()

    def remove_guide(self, i: int, *, record: bool = True) -> None:
        if record and self.undo_push:
            self.undo_push()
        del self.guides[i]
        self.documentChanged.emit()
        self.overlay_update()

    def guide_at(self, pos: QPointF, px: float = 4.0) -> int | None:
        best, best_d = None, px
        for i, (axis, v) in enumerate(self.guides):
            s = self.to_screen(v, v)
            d = abs(pos.y() - s.y()) if axis == 'h' else abs(pos.x() - s.x())
            if d <= best_d:
                best, best_d = i, d
        return best

    # --- lignes de construction (guides obliques, comme XLINE en DAO) ------------
    #: [[x, y, angle°]] : clé à part des guides droits — une version qui ne la connaît pas l'ignore
    OBLIQUES = 'guides_obliques'
    SNAP_CYCLE_PX = 4                                    # Alt : la souris peut bouger de si peu sans perdre le rang

    @property
    def oblique_guides(self) -> list:
        g = self.doc.extra.get(self.OBLIQUES)
        return g if isinstance(g, list) else []

    def _push_obliques(self) -> None:
        if self.undo_push:
            try:
                self.undo_push(keys=(self.OBLIQUES,))
            except TypeError:                            # rappel sans réglages du document (essais)
                self.undo_push()

    def add_oblique_guide(self, x: float, y: float, angle: float) -> str:
        """Ligne de construction par (x, y) à `angle` degrés ; horizontale ou
        verticale : guide ordinaire. Rend 'h', 'v' ou 'o'."""
        a = float(angle) % 180.0
        if min(a, 180.0 - a) < 1e-6:
            self.add_guide('h', y)
            return 'h'
        if abs(a - 90.0) < 1e-6:
            self.add_guide('v', x)
            return 'v'
        self._push_obliques()
        self.doc.extra.setdefault(self.OBLIQUES, []).append([float(x), float(y), round(a, 9)])
        self.documentChanged.emit()
        self.overlay_update()
        return 'o'

    def remove_oblique(self, i: int, *, record: bool = True) -> None:
        if record:
            self._push_obliques()
        g = self.doc.extra[self.OBLIQUES]
        del g[i]
        if not g:
            self.doc.extra.pop(self.OBLIQUES)
        self.documentChanged.emit()
        self.overlay_update()

    def oblique_at(self, pos: QPointF, px: float = 4.0) -> int | None:
        x, y = self.to_doc(pos)
        best, best_d = None, px / max(self.scale, 1e-12)
        for i, (gx, gy, a) in enumerate(self.oblique_guides):
            t = math.radians(a)
            d = abs(-(x - gx) * math.sin(t) + (y - gy) * math.cos(t))
            if d <= best_d:
                best, best_d = i, d
        return best

    def _paint_guides(self, p: QPainter) -> None:
        gs = list(self.guides)
        if self.guide_preview is not None:
            gs.append(list(self.guide_preview))
        obl = list(self.oblique_guides) + ([list(self.oblique_preview)] if self.oblique_preview is not None else [])
        if not gs and not obl:
            return
        pen = QPen(QColor(canvas_colors()['guide']), 1, Qt.PenStyle.DashLine)
        p.setPen(pen)
        for axis, v in gs:
            s = self.to_screen(v, v)
            if axis == 'h':
                p.drawLine(QPointF(0, s.y()), QPointF(self.width(), s.y()))
            else:
                p.drawLine(QPointF(s.x(), 0), QPointF(s.x(), self.height()))
        if obl:
            R = math.hypot(self.width(), self.height())
            cx, cy = self.width() / 2, self.height() / 2
            for gx, gy, a in obl:
                o = self.to_screen(gx, gy)
                t = math.radians(a)
                ux, uy = math.cos(t), -math.sin(t)            # écran : Y vers le bas
                k = (cx - o.x()) * ux + (cy - o.y()) * uy      # pied du centre de la vue sur la ligne
                mx, my = o.x() + k * ux, o.y() + k * uy
                p.drawLine(QPointF(mx - R * ux, my - R * uy), QPointF(mx + R * ux, my + R * uy))

    # --- origine du dessin ------------------------------------------------------
    @property
    def origin(self) -> tuple[float, float]:
        """Origine des coordonnées affichées (règles, position, barre
        d'état), en mm du dessin ; (0, 0) par défaut. Elle ne déplace rien :
        les fichiers écrits gardent le zéro du dessin."""
        o = self.doc.extra.get('origine')
        try:
            return float(o[0]), float(o[1])
        except (TypeError, ValueError, IndexError):
            return 0.0, 0.0

    def set_origin(self, x: float, y: float) -> None:
        if abs(x) < 1e-12 and abs(y) < 1e-12:
            self.doc.extra.pop('origine', None)
        else:
            self.doc.extra['origine'] = [float(x), float(y)]
        self.documentChanged.emit()
        self.originChanged.emit()
        self.overlay_update()

    def _paint_origin(self, p: QPainter) -> None:
        """Repère de l'origine : flèches X (rouge) et Y (verte)."""
        marks = []
        if self.show_origin:
            marks.append((self.origin, False))
        if self.origin_preview is not None:
            marks.append((self.origin_preview, True))
        for (x, y), preview in marks:
            s = self.to_screen(x, y)
            p.save()
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            f = QFont(self.font())
            f.setPointSizeF(7.5)
            f.setBold(True)
            p.setFont(f)
            L = 34
            for (dx, dy), col, lab in (((1, 0), QColor(215, 48, 39), 'X'), ((0, -1), QColor(26, 152, 80), 'Y')):
                pen = QPen(col, 1.5 if preview else 2, Qt.PenStyle.DashLine if preview else Qt.PenStyle.SolidLine)
                p.setPen(pen)
                e = QPointF(s.x() + dx * L, s.y() + dy * L)
                p.drawLine(s, e)
                head = QPolygonF([e, QPointF(e.x() - dx * 8 + dy * 4, e.y() - dy * 8 + dx * 4),
                                  QPointF(e.x() - dx * 8 - dy * 4, e.y() - dy * 8 - dx * 4)])
                p.setBrush(col)
                p.setPen(QPen(col, 1))
                p.drawPolygon(head)
                p.drawText(QPointF(e.x() + (4 if dx else 5), e.y() + (4 if dx else 4)), lab)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(canvas_colors()['snap']), 1.5))
            p.drawEllipse(s, 4, 4)
            p.restore()

    # --- document -----------------------------------------------------------
    def set_document(self, doc: Document) -> None:
        self.doc = doc
        self.selection = []
        self._cache.clear()
        self._views = []                 # zoom précédent : jamais la vue d'un autre dessin
        self.fit()
        self._views = []
        self.selectionChanged.emit()
        self.update()

    def invalidate(self, items=None) -> None:
        """Le document a changé. Les chemins d'affichage restent en cache :
        chaque entrée est revalidée par l'identité de l'objet et de son
        tracé ; les entrées d'objets disparus sont purgées au prochain
        rendu complet."""
        if items is not None:
            for it in items:
                for leaf in _leaves([it]):
                    src = item_path(leaf)
                    if src is not None:
                        self._cache.pop(id(src), None)
        self._prune = True
        self.update()

    def _leaf_count(self) -> int:
        return sum(1 for L in self.doc.layers for _ in _leaves(L.items))

    def _prune_caches(self) -> None:
        live = set()
        for L in self.doc.layers:
            for leaf in _leaves(L.items):
                src = leaf.data if isinstance(leaf, Image) else item_path(leaf)
                live.add(id(src))
        for d in (self._cache, self._images):
            for k in [k for k in d if k not in live]:
                del d[k]
        self._prune = False

    def update(self, *args) -> None:
        """Repeint complet (scène recalculée)."""
        self._scene_dirty = True
        super().update(*args)

    def overlay_update(self) -> None:
        """Repeint des seules surimpressions (aperçus d'outils, accrochage,
        rectangle de sélection, glissé) : la scène vient du cache si rien
        d'autre n'a changé."""
        super().update()

    def _entry(self, it: Item):
        """(tracé, QPainterPath, rectangle) de l'objet, depuis le cache."""
        src = item_path(it)
        if not src:
            return None
        e = self._cache.get(id(src))
        if e is not None and e[0] is src:
            return e
        q = to_qpath(src)
        e = (src, q, _cull_rect(q))
        self._cache[id(src)] = e
        return e

    def _oriented(self, src) -> list:
        """[(sens, QPainterPath)] d'un tracé (Ctrl+7), depuis le cache."""
        e = self._orient.get(id(src))
        if e is None or e[0] is not src:
            from ..core.orient import split
            e = (src, [(k, to_qpath(pth)) for k, pth in split(src).items()])
            self._orient[id(src)] = e
            if len(self._orient) > 20000:
                self._orient = {id(src): e}
        return e[1]

    def orient_colors(self) -> dict:
        """Ctrl+7 : couleur de chaque sens selon le thème — fond sombre : vert et bleu clairs, ouverts en blanc ;
        fond clair : vert et bleu foncés, ouverts en noir."""
        from ..core.orient import colors
        from .icons import dark_theme
        return colors(dark_theme())

    def _qpath(self, it: Item) -> QPainterPath | None:
        e = self._entry(it)
        return e[1] if e else None

    def remember_view(self) -> None:
        """Garde la vue courante pour « zoom précédent » (une rafale de
        molette compte pour un seul pas)."""
        import time
        now = time.monotonic()
        if not (self._views and now - self._view_t < 0.6):
            self._views.append((self.scale, self.ox, self.oy))
            del self._views[:-50]
        self._view_t = now

    def previous_view(self) -> bool:
        if not self._views:
            return False
        self.scale, self.ox, self.oy = self._views.pop()
        self._view_t = 0.0
        self.update()
        return True

    def fit(self, box=None) -> None:
        self.remember_view()
        box = (box or self.doc.bbox(include_plate=True, visible_only=True) or self.doc.bbox(include_plate=True)
               or self.doc.extra.get('page_mm'))
        if box and len(box) == 6:
            box = (box[0], box[1], box[3], box[4])
        if not box:
            box = (0, 0, 200, 150)
        x0, y0, x1, y1 = box
        w, h = max(x1 - x0, 1e-3), max(y1 - y0, 1e-3)
        W, H = max(self.width(), 100), max(self.height(), 100)
        self.scale = min(W / w, H / h) * 0.9
        self.ox = W / 2 - (x0 + w / 2) * self.scale
        self.oy = H / 2 + (y0 + h / 2) * self.scale
        self._fit_view = (self.scale, self.ox, self.oy)
        self.update()

    def zoom_at(self, factor: float, at: QPointF) -> None:
        self.remember_view()
        x, y = self.to_doc(at)
        self.scale = max(1e-3, min(self.scale * factor, 1e5))
        self.ox = at.x() - x * self.scale
        self.oy = at.y() + y * self.scale
        # la vue a changé, pas le dessin : la clé de vue impose le rendu (ou
        # l'aperçu mis à l'échelle sur un gros dessin)
        self.overlay_update()

    # --- rendu --------------------------------------------------------------
    def _view_key(self):
        return (self.scale, self.ox, self.oy, self.width(), self.height(), self.devicePixelRatioF())

    #: rendu au-delà duquel le zoom passe par l'aperçu (ms), pause avant le rendu net
    ZOOM_PREVIEW_MS = 25.0
    ZOOM_REFINE_MS = 140

    def _refine_now(self) -> None:
        self._force_render = True
        self.update()

    def _zoom_preview(self, key) -> float | None:
        """Facteur d'échelle si la vue a seulement zoomé depuis la scène en
        cache et que son rendu est lent ; None sinon."""
        if self._force_render or self._render_ms < self.ZOOM_PREVIEW_MS or self._scene_k is None:
            return None
        if self._scene_k[3:] != key[3:] or self._scene_k[0] == key[0]:
            return None
        k = key[0] / self._scene_k[0]
        return k if 0.02 < k < 50 else None

    def paintEvent(self, ev) -> None:
        key = self._view_key()
        cached = self._scene is not None and not self._scene_dirty
        p = QPainter(self)
        k = self._zoom_preview(key) if cached else None
        if cached and self._scene_k == key:
            p.drawPixmap(0, 0, self._scene)
        elif k is not None:
            # zoom sur un gros dessin : scène en cache mise à l'échelle
            # (écran ancien → nouveau : X = X₀·k + ox − ox₀·k), rendu net après une pause
            p.fillRect(self.rect(), canvas_background(canvas_colors(), self.height()))
            p.save()
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            p.translate(self.ox - self._scene_k[1] * k, self.oy - self._scene_k[2] * k)
            p.scale(k, k)
            p.drawPixmap(0, 0, self._scene)
            p.restore()
            self._refine.start()
        elif cached and self._drag and self._drag.get('kind') == 'pan' and \
                self._scene_k[0] == key[0] and self._scene_k[3:] == key[3:]:
            # panoramique : image de la scène décalée, recalcul au relâcher
            p.fillRect(self.rect(), canvas_background(canvas_colors(), self.height()))
            p.drawPixmap(QPointF(self.ox - self._scene_k[1], self.oy - self._scene_k[2]), self._scene)
        else:
            dpr = self.devicePixelRatioF()
            pm = QPixmap(max(1, int(self.width() * dpr)), max(1, int(self.height() * dpr)))
            pm.setDevicePixelRatio(dpr)
            sp = QPainter(pm)
            import time as _t
            t0 = _t.perf_counter()
            self._paint_scene(sp)
            sp.end()
            self._render_ms = (_t.perf_counter() - t0) * 1000.0
            self._force_render = False
            self._scene, self._scene_k, self._scene_dirty = pm, key, False
            if getattr(self, '_prune', False) and len(self._cache) > 3 * max(1, self._leaf_count()) + 2000:
                # purge seulement si le cache dépasse nettement le dessin : les
                # états récents d'annuler / refaire restent prêts à afficher
                self._prune_caches()
            p.drawPixmap(0, 0, pm)
        if self._view_emitted != key:
            self._view_emitted = key
            self.viewChanged.emit()
        self._paint_guides(p)
        self._paint_origin(p)
        self._paint_symmetry(p)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._paint_gesture(p)
        if self.tool_obj is not None:
            self.tool_obj.paint(p)
        self._paint_snap(p)
        p.end()

    def _paint_scene(self, p: QPainter) -> None:
        """Fond, page, grille, plaque, objets, sens, cadre de sélection."""
        self._inks = {}                                  # encres du repeint : une par couleur d'outil
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cc = canvas_colors()
        p.fillRect(self.rect(), canvas_background(cc, self.height()))
        v = self.view()
        # page de travail
        page = self.doc.extra.get('page_mm')
        if page and len(page) == 6:
            r = v.mapRect(QRectF(page[0], page[1], page[3] - page[0], page[4] - page[1]))
            p.fillRect(r.translated(4, 4), QColor(0, 0, 0, 60))
            p.fillRect(r, QColor(cc['page']))
        else:
            p.fillRect(self.rect(), QColor(cc['blank']))
        if self.show_grid:
            self._paint_grid(p)
        # plaque
        if self.doc.plate and self.doc.plate.visible:
            pl = self.doc.plate
            q = to_qpath(Path([geom.rect(pl.x, pl.y, pl.width, pl.height, pl.corner_radius)]))
            p.save()
            p.setTransform(v)
            p.setBrush(QColor(cc['plate']))
            pen = QPen(QColor(cc['plate_edge']), 0)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.drawPath(q)
            if pl.has_margins():                             # zone gravable : cadre pointillé
                ux0, uy0, ux1, uy1 = pl.usable()
                mp = QPen(QColor(cc['plate_edge']), 0, Qt.PenStyle.DashLine)
                mp.setCosmetic(True)
                p.setPen(mp)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(QRectF(ux0, uy0, ux1 - ux0, uy1 - uy0))
            p.restore()
        # objets
        visible = self.rect()
        inv = v.inverted()[0]
        vis_doc = inv.mapRect(QRectF(visible))
        p.save()
        p.setTransform(v)
        sel_ids = {id(x) for x in _leaves(self.selection)}
        ocolors = self.orient_colors() if self.show_direction else None    # Ctrl+7 : thème lu une fois par repeint
        for L in self.doc.layers:
            if not self.layer_shown(L):
                continue
            for leaf in _leaves(L.items, visible_only=True):
                if isinstance(leaf, Image):
                    self._paint_image(p, leaf, id(leaf) in sel_ids)
                    continue
                e = self._entry(leaf)
                if e is None:
                    continue
                q, r = e[1], e[2]
                if not r.intersects(vis_doc):
                    continue
                color = QColor(self._color(leaf) if self.tool_colors else self._black_ink())
                if self.engrave_preview:
                    w = self.doc.tool_width(leaf.tool)
                    if w > 0:
                        wide = QColor(color)
                        wide.setAlpha(120)
                        wp = QPen(wide, w)
                        wp.setCapStyle(Qt.PenCapStyle.RoundCap)
                        wp.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                        p.setPen(wp)
                        p.setBrush(Qt.BrushStyle.NoBrush)
                        p.drawPath(q)
                pen = QPen(color, 0)
                pen.setCosmetic(True)
                if id(leaf) in sel_ids:
                    pen = QPen(QColor(cc['selection']), max(1, int(self.highlight_px)))
                    pen.setCosmetic(True)
                p.setPen(pen)
                if isinstance(leaf.extra, dict) and 'solide' in leaf.extra:
                    c2 = QColor(color)                     # volume 3D : silhouette hachurée (même en Remplissage)
                    c2.setAlpha(110)
                    p.setBrush(QBrush(c2, Qt.BrushStyle.BDiagPattern))
                elif self.show_fill or getattr(leaf, 'filled', False):
                    c2 = QColor(color)                   # Ctrl+9 : rempli de la couleur de l'outil
                    c2.setAlpha(90)                      # translucide : les formes dedans restent visibles
                    p.setBrush(c2)
                else:
                    p.setBrush(Qt.BrushStyle.NoBrush)
                if self.show_direction and id(leaf) not in sel_ids:
                    if p.brush().style() != Qt.BrushStyle.NoBrush:
                        p.setPen(Qt.PenStyle.NoPen)
                        p.drawPath(q)
                        p.setBrush(Qt.BrushStyle.NoBrush)
                    for key, oq in self._oriented(e[0]):     # Ctrl+7 : vert horaire, bleu anti-horaire, noir ouvert
                        op_ = QPen(QColor(ocolors[key]), 0)
                        op_.setCosmetic(True)
                        p.setPen(op_)
                        p.drawPath(oq)
                else:
                    p.drawPath(q)
                if 'trou' in leaf.extra:
                    # trou de perçage : croix au centre, comme dans TypeEdit
                    c, h = r.center(), 0.7 * r.width()
                    p.drawLine(QPointF(c.x() - h, c.y()), QPointF(c.x() + h, c.y()))
                    p.drawLine(QPointF(c.x(), c.y() - h), QPointF(c.x(), c.y() + h))
        p.restore()
        self._paint_bruts(p, v)
        if self.toolpaths and self.toolpaths_visible:
            self._paint_toolpaths(p, v)
        if self.compare is not None and getattr(self.compare, 'doc', None) is self.doc:
            self._paint_compare(p, v, vis_doc)
        if self.show_direction:
            self._paint_directions(p)
        if self.show_arrows:
            self._paint_direction_arrows(p)
        if self.show_starts or self.show_nodes:
            self._paint_points(p)
        if self.cross_marks:
            self._paint_cross_marks(p)
        if getattr(self, 'flash_paths', None) and getattr(self, '_flash_on', False):
            self._paint_flash(p)
        if not (self.tool_obj is not None and type(self.tool_obj).__name__ == 'NodeTool'):
            self._paint_selection(p)

    # --- comparaison de dessins -----------------------------------------------
    #: ajouté (ici seulement), enlevé (dans l'autre seulement), modifié
    COMPARE_COLORS = {'added': '#2fbf71', 'removed': '#e5484d', 'changed': '#f5a524'}

    def _compare_qpath(self, it):
        """QPainterPath d'un objet de la comparaison (texte de l'autre dessin :
        contour calculé une fois)."""
        e = self._cmp_q.get(id(it))
        if e is not None and e[0] is it:
            return e[1]
        from ..core.compare import outline
        pth = outline(it)
        q = to_qpath(pth) if pth else None
        self._cmp_q[id(it)] = (it, q)
        return q

    def _paint_compare(self, p: QPainter, v, vis_doc) -> None:
        cmp_ = self.compare
        p.save()
        p.setTransform(v)
        p.setBrush(Qt.BrushStyle.NoBrush)

        def draw(items, color, width, style=Qt.PenStyle.SolidLine, alpha=255):
            c = QColor(color)
            c.setAlpha(alpha)
            pen = QPen(c, width, style)
            pen.setCosmetic(True)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            for it in items:
                q = self._compare_qpath(it)
                if q is not None and _cull_rect(q).intersects(vis_doc):
                    p.drawPath(q)
        col = self.COMPARE_COLORS
        draw(cmp_.removed, col['removed'], 1.6, Qt.PenStyle.DashLine)
        draw([b for _a, b, _w in cmp_.changed], col['changed'], 1.4, Qt.PenStyle.DashLine)
        draw(cmp_.added, col['added'], 4, alpha=150)
        draw([a for a, _b, _w in cmp_.changed], col['changed'], 4, alpha=150)
        p.restore()
        if cmp_.at is not None and 0 <= cmp_.at < len(cmp_.regions):
            x0, y0, x1, y1 = cmp_.regions[cmp_.at]
            r = QRectF(self.to_screen(x0, y1), self.to_screen(x1, y0)).normalized().adjusted(-6, -6, 6, 6)
            p.setPen(QPen(QColor(canvas_colors()['frame']), 1, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(r)
        # légende : nombres par couleur, en bas à gauche
        fm = p.fontMetrics()
        h = fm.height() + 4
        x, y = 8, self.height() - 8 - h
        for key, n in (('added', len(cmp_.added)), ('removed', len(cmp_.removed)), ('changed', len(cmp_.changed))):
            label = f'{n}'
            w = fm.horizontalAdvance(label) + h + 8
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 110))
            p.drawRoundedRect(QRectF(x, y, w, h), 4, 4)
            p.setBrush(QColor(col[key]))
            p.drawRect(QRectF(x + 4, y + 4, h - 8, h - 8))
            p.setPen(QColor('#ffffff'))
            p.drawText(QRectF(x + h, y, w - h, h), int(Qt.AlignmentFlag.AlignVCenter), label)
            x += w + 4

    # --- FAO : parcours affichés --------------------------------------------
    def set_toolpaths(self, items) -> None:
        """Parcours à afficher : [(Toolpath, couleur)]."""
        self.toolpaths = list(items)
        self._tp_cache = {}
        self.invalidate()

    #: tranches de profondeur des trajectoires en 2.5D (de la surface au plus profond)
    DEPTH_BANDS = 4

    def _toolpath_bands(self, tp):
        """Trajectoire en 2.5D : avances rangées par tranche de profondeur
        (une teinte par tranche, de la surface au fond), rapides à part."""
        key = id(tp)
        if key not in self._tp_cache:
            n = self.DEPTH_BANDS
            bands = [QPainterPath() for _ in range(n)]
            rapid = QPainterPath()
            lines = tp.polylines(max(0.005, 0.5 / max(self.scale, 1e-6)))
            deep = min((z for kind, pts in lines if kind != 'rapid' for _x, _y, z in pts), default=0.0)
            span = -deep if deep < -1e-9 else 0.0
            for kind, pts in lines:
                if kind == 'rapid':
                    rapid.moveTo(pts[0][0], pts[0][1])
                    for x, y, _z in pts[1:]:
                        rapid.lineTo(x, y)
                    continue
                cur = None
                px, py = pts[0][0], pts[0][1]
                for x, y, z in pts[1:]:
                    b = min(n - 1, int(-z / span * n)) if span and z < 0 else 0
                    if b != cur:
                        bands[b].moveTo(px, py)
                        cur = b
                    bands[b].lineTo(x, y)
                    px, py = x, y
            self._tp_cache[key] = (tp, bands, rapid)
        return self._tp_cache[key][1:]

    def _toolpath_paths(self, tp):
        """(avances, rapides) en deux chemins (compte des segments, essais)."""
        bands, rapid = self._toolpath_bands(tp)
        feed = QPainterPath()
        for b in bands:
            feed.addPath(b)
        return feed, rapid

    #: au-delà de ce nombre de segments affichés, les parcours sont tracés au trait fin
    HEAVY_PATHS = 200_000

    def heavy_toolpaths(self) -> bool:
        """Beaucoup de segments à tracer : un trait de 1,2 px antialiasé coûte
        100 × plus qu'un trait fin (le contour du trait est calculé segment
        par segment — 2 millions de segments : 23 s contre 0,2 s)."""
        return sum(b.elementCount() for tp, _c in self.toolpaths
                   for b in self._toolpath_bands(tp)[0]) > self.HEAVY_PATHS

    #: couleur des zones que signalent les parcours (îles gardées malgré l'arrondi des angles…)
    ZONE_COLOR = '#f08c00'

    def _paint_toolpaths(self, p: QPainter, v) -> None:
        p.save()
        p.setTransform(v)
        p.setBrush(Qt.BrushStyle.NoBrush)
        width = 0 if self.heavy_toolpaths() else 1.2
        n = self.DEPTH_BANDS
        for tp, color in self.toolpaths:
            bands, rapid = self._toolpath_bands(tp)
            if self.show_rapids:
                pen = QPen(QColor(canvas_colors()['frame']), 0, Qt.PenStyle.DashLine)
                pen.setCosmetic(True)
                p.setPen(pen)
                p.drawPath(rapid)
            base = QColor(color)
            for i, b in enumerate(bands):              # 2.5D : clair en surface, foncé au fond
                if b.isEmpty():
                    continue
                c = base.lighter(150 - 50 * i // max(1, n - 1)) if i < n // 2 else base.darker(100 + 60 * i // n)
                pen = QPen(c, width)
                pen.setCosmetic(True)
                p.setPen(pen)
                p.drawPath(b)
        zones = [z for tp, _c in self.toolpaths for z in (getattr(tp, 'zones', None) or []) if len(z.get('pts') or ()) >= 3]
        if zones:                                      # zones que signalent les parcours (îles gardées…) : orange
            fill = QColor(self.ZONE_COLOR)
            fill.setAlpha(90)
            pen = QPen(QColor(self.ZONE_COLOR), 2.0)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.setBrush(fill)
            for z in zones[:2000]:
                p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in z['pts']]))
        p.restore()

    # --- contours qui clignotent (formes à la base d'un parcours, `ui.fao_guard`) --------------------------------
    def flash(self, paths, ms: int = 2000) -> None:
        """Les contours `paths` (tracés du dessin) clignotent `ms` millisecondes par-dessus le dessin."""
        from PySide6.QtCore import QTimer
        self.flash_paths = [q for q in paths or [] if q is not None]
        timer = getattr(self, '_flash_timer', None)
        if not self.flash_paths:                         # rien (ou un autre dessin) : arrêté
            if timer is not None:
                timer.stop()
            self._flash_on = False
            self.update()
            return
        qp = QPainterPath()                              # un seul tracé, fait une fois (pas à chaque peinture)
        for q in self.flash_paths[:5000]:
            qp.addPath(to_qpath(q))
        self._flash_qpath, self._flash_smooth = qp, len(self.flash_paths) <= 300
        if timer is None:
            timer = self._flash_timer = QTimer(self)
            timer.setInterval(250)
            timer.timeout.connect(self._flash_tick)
        self._flash_left = max(1, int(ms) // 250)
        self._flash_on = True
        timer.start()
        self.update()

    def _flash_tick(self) -> None:
        self._flash_left -= 1
        self._flash_on = not self._flash_on and self._flash_left > 0
        if self._flash_left <= 0:
            self._flash_timer.stop()
            self.flash_paths = []
            self._flash_on = False
        self.update()

    def _paint_flash(self, p: QPainter) -> None:
        from .cam_panel import COLOUR_BLIND
        p.save()
        smooth = getattr(self, '_flash_smooth', True)    # beaucoup de contours : sans lissage, trait fin
        p.setRenderHint(QPainter.RenderHint.Antialiasing, smooth)
        p.setTransform(self.view())
        pen = QPen(QColor('#d55e00' if COLOUR_BLIND['on'] else '#f03e3e'), 3.0 if smooth else 2.0)
        pen.setCosmetic(True)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(self._flash_qpath)
        p.restore()

    def _paint_cross_marks(self, p: QPainter) -> None:
        """Points d'intersection : cercle rouge (boucle), orange (entre
        contours), violet (entre objets)."""
        from .cam_panel import COLOUR_BLIND
        colors = {'self': '#d55e00', 'contours': '#e69f00', 'objets': '#cc79a7', 'doublon': '#0072b2'} \
            if COLOUR_BLIND['on'] else {'self': '#e03131', 'contours': '#f08c00', 'objets': '#9c36b5',
                                        'doublon': '#1971c2'}
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for x, y, kind in self.cross_marks[:5000]:
            c = self.to_screen(x, y)
            p.setPen(QPen(QColor(colors.get(kind, '#e03131')), 1.6))
            p.drawEllipse(c, 5.0, 5.0)
            p.drawLine(c - QPointF(2.5, 2.5), c + QPointF(2.5, 2.5))
            p.drawLine(c - QPointF(2.5, -2.5), c + QPointF(2.5, -2.5))
        p.restore()

    def _paint_snap(self, p: QPainter) -> None:
        h = self._snap_hit
        if not self.snap.enabled:
            return
        col = QColor(canvas_colors()['snap'])
        if self.snap.tracking and self.snap.tracked:      # points acquis : petites croix
            p.setPen(QPen(col, 1.2))
            for x, y in self.snap.tracked:
                c = self.to_screen(x, y)
                p.drawLine(c - QPointF(3, 0), c + QPointF(3, 0))
                p.drawLine(c - QPointF(0, 3), c + QPointF(0, 3))
        if h is None:
            return
        c = self.to_screen(h.x, h.y)
        if self._snap_at is not None and (self._snap_at - c).manhattanLength() > 3 * self.snap_px + 4:
            return                                       # repère d'une position passée (zoom, touche, défilement) : rien
        if h.kind in ('tracking', 'extension', 'parallel'):  # lignes de repérage en pointillé, prolongées
            pen = QPen(col, 1.0, Qt.PenStyle.DashLine)
            p.setPen(pen)
            for x0, y0, x1, y1 in self.snap.track_lines:
                a, b = self.to_screen(x0, y0), self.to_screen(x1, y1)
                d = b - a
                n = max(1e-9, (d.x() ** 2 + d.y() ** 2) ** 0.5)
                p.drawLine(a, b + d / n * 40)
        p.setPen(QPen(col, 1.6))
        p.setBrush(Qt.BrushStyle.NoBrush)
        r = 5.0
        if h.kind == 'node':
            p.drawRect(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r))
        elif h.kind == 'middle':
            from PySide6.QtGui import QPolygonF
            p.drawPolygon(QPolygonF([QPointF(c.x(), c.y() - r - 1), QPointF(c.x() + r + 1, c.y() + r),
                                     QPointF(c.x() - r - 1, c.y() + r)]))
        elif h.kind == 'center':
            p.drawEllipse(c, r, r)
            p.drawPoint(c)
        elif h.kind == 'perpendicular':
            p.drawLine(c - QPointF(r, -r), c + QPointF(r, r))
            p.drawLine(c - QPointF(r, -r), c - QPointF(r, r))
            p.drawLine(QPointF(c.x() - r, c.y()), QPointF(c.x(), c.y()))
            p.drawLine(QPointF(c.x(), c.y()), QPointF(c.x(), c.y() + r))
        elif h.kind == 'tangent':
            p.drawEllipse(c, r * 0.8, r * 0.8)
            p.drawLine(c - QPointF(r + 2, r * 0.8), c + QPointF(r + 2, -r * 0.8))
        elif h.kind == 'centroid':
            p.drawEllipse(c, r, r)
            p.drawLine(c - QPointF(r + 2, 0), c + QPointF(r + 2, 0))
            p.drawLine(c - QPointF(0, r + 2), c + QPointF(0, r + 2))
        elif h.kind == 'nearest':
            from PySide6.QtGui import QPolygonF
            p.drawPolygon(QPolygonF([QPointF(c.x() - r, c.y() - r), QPointF(c.x() + r, c.y() - r),
                                     QPointF(c.x() - r, c.y() + r), QPointF(c.x() + r, c.y() + r)]))
        else:
            p.drawLine(c - QPointF(r, r), c + QPointF(r, r))
            p.drawLine(c - QPointF(r, -r), c + QPointF(r, -r))
        at = self._snap_at
        p.setPen(QPen(col, 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(c, self.SNAP_RING_PX, self.SNAP_RING_PX)   # le point accroché, entouré
        if at is not None and (at - c).manhattanLength() > 0.5:
            p.drawLine(QPointF(at), c)                   # le fil : du pointeur au point qu'il prendra

    #: rayon du cercle qui entoure le point accroché (px)
    SNAP_RING_PX = 9.0

    def _paint_image(self, p: QPainter, im: Image, selected: bool) -> None:
        e = self._images.get(id(im.data))
        q = e[1] if e is not None and e[0] is im.data else None
        if q is None:
            q = dib_to_qimage(im.data) if im.fmt == 'dib' else None
            if q is None:
                from PySide6.QtGui import QImage
                q = QImage.fromData(im.data)
            self._images[id(im.data)] = (im.data, q)
        if q is None or q.isNull():
            return
        m = im.matrix
        # carré unité (u vers la droite, v vers le bas) → document
        t = QTransform(m.a / q.width(), m.b / q.width(), m.c / q.height(), m.d / q.height(), m.e, m.f)
        p.save()
        p.setTransform(t * p.transform())
        light = self._light_images.get(id(im.data))
        if light is None or light[0] is not im.data:
            from .dialogs import light_on_transparent
            light = self._light_images[id(im.data)] = (im.data, light_on_transparent(q))
        if light[1]:                                     # blanc sur transparent : fond sombre, sinon invisible
            p.fillRect(QRectF(0, 0, q.width(), q.height()), QColor(70, 70, 70))
        p.drawImage(0, 0, q)
        p.restore()
        if selected:
            pen = QPen(QColor(canvas_colors()['selection']), 0)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            poly = QPainterPath()
            c = im.corners()
            poly.moveTo(*c[0])
            for pt in c[1:]:
                poly.lineTo(*pt)
            poly.closeSubpath()
            p.drawPath(poly)

    def _black_ink(self) -> str:
        """Encre unique (couleurs d'outils coupées), gardée pour le repeint comme les autres."""
        cache = self.__dict__.setdefault('_inks', {})
        got = cache.get('#000000')
        if got is None:
            got = cache['#000000'] = ink('#000000')
        return got

    def _color(self, it: Item) -> str:
        c = self.doc.item_color(it)
        cache = self.__dict__.setdefault('_inks', {})
        got = cache.get(c)
        if got is None:                                  # thème lu une fois par couleur et par repeint
            got = cache[c] = ink(c)
        return got

    def _paint_grid(self, p: QPainter) -> None:
        step = self.snap.grid_step if self.snap.grid_step > 0 else 10.0
        while step * self.scale < 12:
            step *= 5
        x0, y1 = self.to_doc(QPointF(0, 0))
        x1, y0 = self.to_doc(QPointF(self.width(), self.height()))
        pen = QPen(QColor(*canvas_colors()['grid']), 1)
        p.setPen(pen)
        x = math.floor(x0 / step) * step
        while x <= x1:
            s = self.to_screen(x, 0).x()
            p.drawLine(QPointF(s, 0), QPointF(s, self.height()))
            x += step
        y = math.floor(y0 / step) * step
        while y <= y1:
            s = self.to_screen(0, y).y()
            p.drawLine(QPointF(0, s), QPointF(self.width(), s))
            y += step

    def order_marks(self) -> list:
        """Rang des objets (TypeEdit : ordre des contours) : ceux de la
        sélection dans son ordre, sinon tous les objets affichés dans l'ordre
        du dessin (celui de l'usinage) ; [(rang, (x, y) du départ)]."""
        items = list(self.selection) or [it for it in self.shown_items()]
        out = []
        for n, it in enumerate(items, start=1):
            start = None
            for leaf in _leaves([it]):
                path = item_path(leaf)
                c = next((c for c in (path.contours if path else []) if c.segments), None)
                if c is not None:
                    start = c.segments[0].point(0.0)
                    break
            if start is None:
                bb = it.bbox()
                if not bb:
                    continue
                start = (bb[0], bb[3])
            out.append((n, start))
        return out

    def _paint_directions(self, p: QPainter) -> None:
        """Ctrl+7 (TypeEdit : Ctrl+T) : rang de chaque objet (le sens se lit à la
        couleur des contours ; les flèches sont un réglage à part, `show_arrows`)."""
        p.setPen(QPen(QColor(canvas_colors()['direction']), 1))
        f = p.font()
        f.setPixelSize(11)
        f.setBold(True)
        p.setFont(f)
        for n, (x, y) in self.order_marks()[:2000]:
            A = self.to_screen(x, y)
            p.drawText(A + QPointF(5, -5), str(n))

    def _paint_direction_arrows(self, p: QPainter) -> None:
        """F10 › Affichage « Flèches de sens » : flèche au départ de chaque
        contour, dans le sens du parcours (indépendante de Ctrl+7)."""
        p.setPen(QPen(QColor(canvas_colors()['direction']), 1))
        for leaf in _leaves(self.shown_items()):
            path = item_path(leaf)
            if not path:
                continue
            for c in path.contours:
                if not c.segments:
                    continue
                s = c.segments[0]
                a, b = s.point(0.0), s.point(0.05)
                A, B = self.to_screen(*a), self.to_screen(*b)
                ang = math.atan2(B.y() - A.y(), B.x() - A.x())
                for da in (2.6, -2.6):
                    p.drawLine(A, A + QPointF(math.cos(ang + da) * 8, math.sin(ang + da) * 8))
                p.drawEllipse(A, 2, 2)

    #: au-delà, les points de contrôle ne sont plus dessinés (lisibilité, vitesse)
    MAX_NODE_MARKS = 20000

    def point_marks(self) -> tuple[list, list]:
        """(départs [(x, y)], points de contrôle [(x, y, lisse)]) des contours
        affichés — ceux demandés par les options d'affichage."""
        from ..core import nodes as N
        starts, marks = [], []
        for leaf in _leaves(self.shown_items()):
            path = item_path(leaf)
            if not path:
                continue
            for c in path.contours:
                if not c.segments:
                    continue
                if self.show_starts:
                    starts.append(tuple(c.segments[0].start))
                if self.show_nodes and len(marks) < self.MAX_NODE_MARKS:
                    for k in range(N.node_count(c)):
                        x, y = N.node_point(c, k)
                        marks.append((x, y, N.is_smooth(c, k)))
        return starts, marks

    def _paint_points(self, p: QPainter) -> None:
        """Points de départ (gros carré plein) et points de contrôle (petit
        carré : angle ; rond : point lisse)."""
        starts, marks = self.point_marks()
        p.save()
        col = QColor(canvas_colors()['direction'])
        p.setPen(QPen(col, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for x, y, smooth in marks:
            c = self.to_screen(x, y)
            if smooth:
                p.drawEllipse(c, 2.5, 2.5)
            else:
                p.drawRect(QRectF(c.x() - 2.5, c.y() - 2.5, 5, 5))
        p.setBrush(col)
        for x, y in starts[:self.MAX_NODE_MARKS]:
            c = self.to_screen(x, y)
            p.drawRect(QRectF(c.x() - 3.5, c.y() - 3.5, 7, 7))
        p.restore()

    def selection_bbox(self):
        return geom.bbox_union(it.bbox() for it in self.selection)

    #: au-delà, pas de cadre par objet (une sélection de tout un gros dessin)
    FRAMES_MAX = 400

    def selection_frames(self) -> list:
        """Plusieurs objets choisis : le cadre de chacun, à l'écran (un groupe en a un, ses objets non) ; un seul
        objet : aucun, le cadre à poignées est le sien."""
        sel = self.selection
        if not 1 < len(sel) <= self.FRAMES_MAX:
            return []
        out = []
        for it in sel:
            b = it.bbox()
            if b:
                out.append(QRectF(self.to_screen(b[0], b[1]), self.to_screen(b[2], b[3])).normalized())
        return out

    def _paint_bruts(self, p: QPainter, v) -> None:
        """Bruts des ensembles : un cadre pointillé, qui n'est ni gravé ni usiné."""
        from ..core import brut as BR
        pen = None
        for L in self.doc.layers:
            if not self.layer_shown(L):
                continue
            for _it, b in BR.walk(L.items):
                if pen is None:
                    p.save()
                    p.setTransform(v)
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    pen = QPen(QColor('#8c4d0d'), 0, Qt.PenStyle.DashLine)
                    pen.setCosmetic(True)
                    p.setPen(pen)
                c = b['corners']
                for k in range(4):
                    a, e = c[k], c[(k + 1) % 4]
                    p.drawLine(QPointF(a[0], a[1]), QPointF(e[0], e[1]))
        if pen is not None:
            p.restore()

    def frozen_selected(self) -> list:
        """Les objets gelés désignés, s'ils sont encore dans le dessin et encore gelés."""
        return [it for it in self.frozen_picked if it.locked and self.doc.layer_of(it) is not None]

    def _paint_frozen(self, p: QPainter) -> None:
        """Un objet gelé désigné : dans sa couleur à lui, sans poignées."""
        frozen = self.frozen_selected()
        if not frozen:
            return
        p.save()
        p.setTransform(self.view())
        pen = QPen(QColor(canvas_colors().get('frozen', '#ff00ff')), 2)
        pen.setCosmetic(True)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for leaf in _leaves(frozen):
            q = self._qpath(leaf)
            if q is not None:
                p.drawPath(q)
        p.restore()

    def _paint_selection(self, p: QPainter) -> None:
        self._paint_frozen(p)
        bb = self.selection_bbox()
        if not bb:
            return
        a = self.to_screen(bb[0], bb[1])
        b = self.to_screen(bb[2], bb[3])
        r = QRectF(a, b).normalized()
        cc = canvas_colors()
        pen = QPen(QColor(cc['frame']), 1, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(r)
        frames = self.selection_frames()
        if frames:                                       # plusieurs objets : le cadre de chacun, en points
            p.setPen(QPen(QColor(cc['frame']), 1, Qt.PenStyle.DotLine))
            for f in frames:
                p.drawRect(f)
        p.setPen(QPen(QColor(cc['frame']), 1))
        p.setBrush(QColor(cc['handle']))
        c = self.to_screen(*self.pivot) if self.pivot is not None else r.center()
        if self.rot_mode:
            for h in self._handles(r)[0::2]:
                p.drawEllipse(h, self.handle_px / 2 + 1, self.handle_px / 2 + 1)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(c, 6, 6)
        else:
            for h in self._handles(r):
                p.drawRect(QRectF(h.x() - self.handle_px / 2, h.y() - self.handle_px / 2, self.handle_px, self.handle_px))
        p.drawLine(c - QPointF(5, 0), c + QPointF(5, 0))
        p.drawLine(c - QPointF(0, 5), c + QPointF(0, 5))
        k = self._knob(r)
        if k is not None:                                # le bouton de rotation, relié au milieu du haut du cadre
            p.setPen(QPen(QColor(cc['frame']), 1))
            p.drawLine(QPointF(r.center().x(), r.top()), k + QPointF(0, self.KNOB_R))
            p.setBrush(QColor(cc['handle']))
            p.drawEllipse(k, self.KNOB_R, self.KNOB_R)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(k.x() - 3, k.y() - 3, 6, 6), 60 * 16, 270 * 16)      # la flèche qui tourne
            p.drawLine(k + QPointF(1.5, -2.6), k + QPointF(3.5, -3.2))

    KNOB_PX = 26.0                                       # le bouton de rotation : au-dessus du cadre, à l'écran
    KNOB_R = 6.0

    def _knob(self, r: QRectF):
        """Où est le bouton de rotation pour le cadre `r` de la sélection (à l'écran) ; None : pas de bouton (autre outil,
        réglage)."""
        if not self.rot_knob or self.tool != 'select' or self.tool_obj is not None:
            return None
        return QPointF(r.center().x(), r.top() - self.KNOB_PX)

    def knob_at(self, pos: QPointF) -> bool:
        """Le bouton de rotation de la sélection sous `pos`."""
        bb = self.selection_bbox() if self.selection else None
        if not bb:
            return False
        k = self._knob(QRectF(self.to_screen(bb[0], bb[1]), self.to_screen(bb[2], bb[3])).normalized())
        return k is not None and abs(k.x() - pos.x()) <= self.KNOB_R + 3 and abs(k.y() - pos.y()) <= self.KNOB_R + 3

    def toggle_rot_mode(self, on=None) -> None:
        """Poignées de rotation ou d'échelle de la sélection (second clic sur elle, le bouton de rotation, Rotation à la
        souris) ; `on` : imposé."""
        from ..i18n import tr
        self.rot_mode = (not self.rot_mode) if on is None else bool(on)
        if self.rot_mode:
            self.measured.emit(tr('Rotation : tirer un coin. Le centre se déplace à la souris, Maj+clic le remet au '
                                  'milieu ; Maj : garder l\'original ; Ctrl : par pas de 15° ; F2 : en chiffres'))
        else:
            self.measured.emit(tr('Échelle : tirer un coin ou un côté. Maj : garder l\'original ; Tab : depuis le '
                                  'centre ; Ctrl : par pas de 100 % ; Ctrl+Alt : un coin sans proportions ; F2 : en '
                                  'chiffres'))
        self.update()

    @staticmethod
    def doc_handles(bb) -> list[tuple[float, float]]:
        """Poignées dans le repère du document (Y vers le haut), dans l'ordre
        haut-gauche, haut, haut-droite, droite, bas-droite, bas, bas-gauche,
        gauche — l'opposée de la poignée i est (i + 4) % 8."""
        x0, y0, x1, y1 = bb
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        return [(x0, y1), (cx, y1), (x1, y1), (x1, cy), (x1, y0), (cx, y0), (x0, y0), (x0, cy)]

    def rotation_center(self, bb) -> tuple:
        return self.pivot if self.pivot is not None else ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)

    def pivot_at(self, pos: QPointF) -> bool:
        """Le centre de rotation sous le curseur : au milieu en mode rotation, ou déjà déplacé."""
        if (not self.rot_mode and self.pivot is None) or self.tool != 'select' or self.tool_obj is not None:
            return False
        bb = self.selection_bbox()
        if not bb:
            return False
        q = self.to_screen(*self.rotation_center(bb))
        return abs(q.x() - pos.x()) <= 6 and abs(q.y() - pos.y()) <= 6

    def handle_at(self, pos: QPointF) -> int | None:
        bb = self.selection_bbox()
        if not bb or self.tool != 'select' or self.tool_obj is not None:
            return None
        for i, (x, y) in enumerate(self.doc_handles(bb)):
            if self.rot_mode and i % 2:
                continue                                  # rotation : coins seulement
            q = self.to_screen(x, y)
            if abs(q.x() - pos.x()) <= self.handle_px and abs(q.y() - pos.y()) <= self.handle_px:
                return i
        return None

    @staticmethod
    def scale_matrix(bb, i: int, p, *, free: bool = False, centered: bool = False, anchor=None, whole: bool = False) -> Affine:
        """Transformation qui amène la poignée i en p : coins proportionnels
        (sauf `free`), côtés sur un seul axe ; `centered` : autour du centre ; `anchor` : autour de ce point ;
        `whole` : par pas de 100 %, soit 1, 2, 3 fois ou, en diminuant, 1/2, 1/3."""
        hs = Canvas.doc_handles(bb)
        hx, hy = hs[i]
        if anchor is not None:
            ax, ay = anchor
        else:
            ax, ay = ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2) if centered else hs[(i + 4) % 8]
        def ratio(num, den):
            return num / den if abs(den) > 1e-12 else 1.0
        sx = ratio(p[0] - ax, hx - ax)
        sy = ratio(p[1] - ay, hy - ay)
        if i in (1, 5):
            sx = 1.0
        elif i in (3, 7):
            sy = 1.0
        elif not free:
            # projection sur la diagonale : échelle unique, signe conservé
            dx, dy = hx - ax, hy - ay
            s = ((p[0] - ax) * dx + (p[1] - ay) * dy) / max(dx * dx + dy * dy, 1e-24)
            sx = sy = s
        if whole:
            def step(v):
                a = abs(v)
                return math.copysign(max(1.0, round(a)) if a >= 1.0 else 1.0 / max(1.0, round(1.0 / max(a, 1e-6))), v)
            sx, sy = step(sx), step(sy)
        sx = sx if abs(sx) > 1e-6 else 1e-6
        sy = sy if abs(sy) > 1e-6 else 1e-6
        return Affine.translation(ax, ay) @ Affine.scaling(sx, sy) @ Affine.translation(-ax, -ay)

    @staticmethod
    def rotation_matrix(bb, start, p, *, step: float = 0.0, center=None) -> tuple[Affine, float]:
        cx, cy = center if center is not None else ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)
        a = math.degrees(math.atan2(p[1] - cy, p[0] - cx) - math.atan2(start[1] - cy, start[0] - cx))
        a = (a + 180) % 360 - 180
        if step:
            a = round(a / step) * step
        return Affine.rotation(a, (cx, cy)), a

    @staticmethod
    def _handles(r: QRectF) -> list[QPointF]:
        return [r.topLeft(), QPointF(r.center().x(), r.top()), r.topRight(),
                QPointF(r.right(), r.center().y()), r.bottomRight(),
                QPointF(r.center().x(), r.bottom()), r.bottomLeft(),
                QPointF(r.left(), r.center().y())]

    def _paint_moving(self, p: QPainter) -> int:
        """Sélection en cours de manipulation (repère déjà posé) : ses tracés si
        l'aperçu est actif (TypeEdit : F4), sinon son seul rectangle englobant
        en pointillés ; rend le nombre de tracés dessinés."""
        if not getattr(self, 'drag_preview', True):
            bb = self.selection_bbox()
            if bb:
                p.drawRect(QRectF(bb[0], bb[1], bb[2] - bb[0], bb[3] - bb[1]))
            return 0
        n = 0
        for leaf in _leaves(self.selection):
            q = self._qpath(leaf)
            if q is not None:
                p.drawPath(q)
                n += 1
        return n

    def _paint_gesture(self, p: QPainter) -> None:
        d = self._drag
        if not d:
            return
        if d['kind'] == 'band':
            self._band_follow_view(d)
            r = QRectF(d['start'], d['now']).normalized()
            crossing = self.band_is_crossing(d)
            # du bas vers le haut (objets touchés) : vert, tirets longs ; sinon (objets dedans) : couleur d'aperçu
            band = QColor(CROSSING_COLOR) if crossing else QColor(canvas_colors()['preview'])
            p.setPen(QPen(band, 1, Qt.PenStyle.DashDotLine if crossing else Qt.PenStyle.DashLine))
            band.setAlpha(30)
            p.setBrush(band)
            p.drawRect(r)
        elif d['kind'] == 'move':
            dx, dy = d['delta']
            p.save()
            p.setTransform(QTransform.fromTranslate(dx, dy) * self.view())
            pen = QPen(QColor(canvas_colors()['selection']), 0, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            p.setPen(pen)
            self._paint_moving(p)
            p.restore()
        elif d['kind'] in ('scale', 'rotate') and d.get('m') is not None:
            m = d['m']
            p.save()
            p.setTransform(QTransform(m.a, m.b, m.c, m.d, m.e, m.f) * self.view())
            pen = QPen(QColor(canvas_colors()['selection']), 0, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            self._paint_moving(p)
            p.restore()
            if d['kind'] == 'rotate':
                p.setPen(QColor(canvas_colors()['selection']))
                p.drawText(d['now'] + QPointF(12, -12), f"{d.get('angle', 0.0):.1f}°")
        elif d['kind'] == 'draw':
            path = self._draft_path(d)
            if path:
                p.save()
                p.setTransform(self.view())
                pen = QPen(QColor(canvas_colors()['preview']), 0)
                pen.setCosmetic(True)
                p.setPen(pen)
                p.drawPath(to_qpath(path))
                p.restore()

    # --- sélection ----------------------------------------------------------
    @staticmethod
    def band_is_crossing(d: dict) -> bool:
        """Rectangle de sélection tiré du bas vers le haut : il sélectionne
        les objets qu'il touche (pas seulement ceux qu'il contient)."""
        return d['now'].y() < d['start'].y()

    def band_items(self, start: QPointF, now: QPointF, boxes: bool = False) -> list[Item]:
        """Objets de premier niveau pris par le rectangle de sélection
        (coins à l'écran) : ceux qu'il contient ; tiré du bas vers le haut,
        aussi ceux qu'il touche (un trait y entre ou le traverse). `boxes`
        (Maj, TypeEdit) : aussi ceux dont la boîte englobante y entre."""
        r = QRectF(start, now).normalized()
        a = self.to_doc(r.topLeft())
        b = self.to_doc(r.bottomRight())
        x0, x1 = min(a[0], b[0]), max(a[0], b[0])
        y0, y1 = min(a[1], b[1]), max(a[1], b[1])
        crossing = self.band_is_crossing({'start': start, 'now': now})
        tol = max(0.5 / self.scale, 1e-4)
        out = []
        for L in self.doc.layers:
            if not self.layer_shown(L) or L.locked:
                continue
            for it in L.items:
                bb = it.bbox()
                if not bb or not it.visible or it.locked or not self._passes_filter(it):
                    continue
                if x0 <= bb[0] and bb[2] <= x1 and y0 <= bb[1] and bb[3] <= y1:
                    out.append(it)
                elif boxes and bb[0] <= x1 and bb[2] >= x0 and bb[1] <= y1 and bb[3] >= y0:
                    out.append(it)
                elif (crossing and bb[0] <= x1 and bb[2] >= x0 and bb[1] <= y1 and bb[3] >= y0
                      and touches_rect(it, (x0, y0, x1, y1), tol)):
                    out.append(it)
        return out

    def _band_follow_view(self, d: dict) -> None:
        """Le coin de départ du rectangle de sélection reste au même point du dessin quand la vue change pendant le
        geste (molette, plusieurs fois, depuis plusieurs centres ; zoom au clavier) : seul l'autre coin suit le
        pointeur."""
        if d.get('start_doc') is not None:
            d['start'] = self.to_screen(*d['start_doc'])

    def select_band(self, d: dict) -> None:
        self.apply_pick(self.band_items(d['start'], d['now'], boxes=d.get('boxes', False)), ctrl=d.get('add', False))
        mode, self.sort_armed = getattr(self, 'sort_armed', None), None
        fn = getattr(self, 'sort_fn', None)
        if mode is not None and fn is not None:         # classement demandé d'avance : le rectangle dit le coin de départ
            fn(mode, from_right=d['start'].x() > d['now'].x(), from_bottom=d['start'].y() > d['now'].y())

    def lasso_items(self, pts: list) -> list:
        """Objets de premier niveau que touche le lasso (polygone en
        coordonnées du dessin) : un de leurs tracés le croise ou y entre ; un
        objet sans tracé (image…) par son encombrement."""
        from shapely.geometry import LineString, Polygon, box
        try:
            lasso = Polygon(pts).buffer(0)
        except Exception:
            return []
        if lasso.is_empty:
            return []
        tol = max(0.5 / self.scale, 1e-4)
        out = []
        for L in self.doc.layers:
            if not self.layer_shown(L) or L.locked:
                continue
            for it in L.items:
                bb = it.bbox()
                if not bb or not it.visible or it.locked or not self._passes_filter(it):
                    continue
                if not lasso.intersects(box(*bb)):
                    continue
                lines = []
                for leaf in _leaves([it]):
                    path = getattr(leaf, 'path', None) or getattr(leaf, 'outline', None)
                    for c in (path.contours if path else []):
                        fl = c.flatten(tol)
                        if len(fl) >= 2:
                            lines.append(LineString(fl))
                if not lines or any(lasso.intersects(g) for g in lines):
                    out.append(it)
        return out

    def apply_pick(self, items: list, ctrl: bool = False) -> None:
        """Objets cliqués ou pris par le rectangle, selon l'opérateur de
        sélection (TypeEdit : standard, zone, ajout, désélection, garder)."""
        from ..core.selsort import combine
        op = getattr(self, 'select_op', 'standard')
        if op == 'standard':
            self.select(items, add=ctrl)
        else:
            self.select(combine(self.selection, items, op, ctrl))

    def pick(self, pos: QPointF) -> Item | None:
        """Objet de premier niveau sous le curseur (le plus haut d'abord)."""
        got = self.pick_all(pos, first_only=True)
        return got[0] if got else None

    def pick_all(self, pos: QPointF, first_only: bool = False, frozen: bool = False) -> list:
        """Objets de premier niveau sous le curseur, du plus haut au plus bas
        (sélection cyclique) ; `frozen` : seulement les objets gelés."""
        out = []
        x, y = self.to_doc(pos)
        tol = PICK_PX / self.scale
        stroker = QPainterPathStroker()
        stroker.setWidth(2 * tol)
        pt = QPointF(x, y)
        for L in reversed(self.doc.layers):
            if not self.layer_shown(L) or L.locked:
                continue
            for top in reversed(L.items):
                if not top.visible or bool(top.locked) != frozen or not self._passes_filter(top):
                    continue
                bb = top.bbox()
                if not bb or not (bb[0] - tol <= x <= bb[2] + tol and bb[1] - tol <= y <= bb[3] + tol):
                    continue
                for leaf in _leaves([top]):
                    if isinstance(leaf, Image):
                        b2 = leaf.bbox()
                        if b2[0] <= x <= b2[2] and b2[1] <= y <= b2[3]:
                            out.append(top)
                            break
                        continue
                    q = self._qpath(leaf)
                    if q is None:
                        continue
                    if stroker.createStroke(q).contains(pt) or (getattr(leaf, 'filled', False) and q.contains(pt)):
                        out.append(top)
                        break
                if first_only and out:
                    return out
        return out

    def _say_cycled(self, k: int, n: int) -> None:
        from ..i18n import tr
        self.measured.emit(tr('Objet {0} sur {1} sous le curseur (Alt+clic : suivant)').format(k, n))

    def cycle_pick(self, pos: QPointF):
        """Sélection cyclique : l'objet sous le curseur qui suit le seul
        objet choisi (le plus haut sinon) ; rend (objet, rang, nombre)."""
        hits = self.pick_all(pos)
        if not hits:
            return None, 0, 0
        k = 0
        if len(self.selection) == 1:
            k = next(((i + 1) % len(hits) for i, h in enumerate(hits) if h is self.selection[0]), 0)
        self.select([hits[k]])
        return hits[k], k + 1, len(hits)

    def extent_step(self, horizontal: bool) -> float | None:
        """Pas de Ctrl+flèche : largeur (ou hauteur) de la sélection plus
        l'écart des options ; None si la sélection est plate dans ce sens."""
        bb = self.selection_bbox()
        if not bb:
            return None
        size = (bb[2] - bb[0]) if horizontal else (bb[3] - bb[1])
        step = size + self.step_gap_mm
        return step if step > 1e-9 else None

    def pick_frozen(self, pos: QPointF, add: bool = False) -> bool:
        """Un clic sur un objet gelé le désigne, pour pouvoir le dégeler ; Ctrl : plusieurs. Il ne se modifie pas pour autant."""
        got = self.pick_all(pos, first_only=True, frozen=True)
        if not got:
            return False
        if not add:
            self.frozen_picked = got
        elif any(x is got[0] for x in self.frozen_picked):
            self.frozen_picked = [x for x in self.frozen_picked if x is not got[0]]
        else:
            self.frozen_picked = self.frozen_picked + got
        from ..i18n import tr
        self.measured.emit(tr('Objet gelé : il ne se modifie pas ; le bouton Geler le dégèle'))
        self.update()
        return True

    def select(self, items: list[Item], *, add: bool = False) -> None:
        self.rot_mode = False
        self.pivot = None
        if not add:
            self.frozen_picked = []
        frozen = [it for it in items if it.locked]       # d'où que vienne la demande, un objet gelé n'entre pas dans la sélection
        if frozen:
            self.frozen_picked = self.frozen_picked + [it for it in frozen if not any(it is x for x in self.frozen_picked)]
            items = [it for it in items if not it.locked]
        if add:
            ids = {id(i) for i in self.selection}
            for it in items:
                if id(it) in ids:
                    self.selection = [s for s in self.selection if s is not it]
                else:
                    self.selection.append(it)
        else:
            self.selection = list(items)
        self.selectionChanged.emit()
        self.update()

    # --- calques en onglets : un seul calque affiché -----------------------
    def layer_shown(self, L) -> bool:
        """Calque affiché et sélectionnable : visible, et seul calque montré
        quand un onglet de calque est choisi."""
        return L.visible and (self.solo_layer is None or L.id == self.solo_layer)

    def shown_items(self):
        for L in self.doc.layers:
            if self.layer_shown(L):
                yield from (it for it in L.items if it.visible)

    def set_solo(self, layer_id) -> None:
        """Onglet de calque : `layer_id` seul affiché (None = tous)."""
        if layer_id == self.solo_layer:
            return
        self.solo_layer = layer_id
        if layer_id is not None:
            keep = [it for it in self.selection
                    if any(L.id == layer_id and any(x is it for x in L.items) for L in self.doc.layers)]
            if len(keep) != len(self.selection):
                self.selection = keep
                self.selectionChanged.emit()
        self.invalidate()

    def _passes_filter(self, it) -> bool:
        """Filtre de sélection (F9) : l'objet est-il d'une nature choisie ?"""
        active = getattr(self, 'pick_filter', None)
        if active is None:
            return True
        from ..core import selfilter
        return selfilter.allowed(it, active)

    def select_all(self) -> None:
        self.select([it for L in self.doc.layers if self.layer_shown(L) and not L.locked
                     for it in L.items if it.visible and not it.locked and self._passes_filter(it)])

    def invert_selection(self) -> None:
        ids = {id(i) for i in self.selection}
        self.select([it for L in self.doc.layers if self.layer_shown(L) and not L.locked
                     for it in L.items if id(it) not in ids and it.visible and not it.locked and self._passes_filter(it)])

    # --- transformations de la sélection -----------------------------------
    #: dernière transformation faite sur la sélection (Répéter la transformation)
    last_transform: Affine | None = None

    def transform_selection(self, m: Affine, *, record: bool = True) -> None:
        if not self.selection:
            return
        if record:
            self.last_transform = m
        if record and self.undo_push:
            self.undo_push()
        ids = {id(s): s for s in self.selection}
        new_sel = []
        qt = QTransform(m.a, m.b, m.c, m.d, m.e, m.f)
        for L in self.doc.layers:
            for i, it in enumerate(L.items):
                if id(it) in ids:
                    t = it.transformed(m)
                    L.items[i] = t
                    new_sel.append(t)
                    # chemins d'affichage : transformés par Qt plutôt que reconstruits
                    for old, new in zip(_leaves([it]), _leaves([t])):
                        src = item_path(new)
                        e = self._entry(old) if src else None
                        if e is not None:
                            q = qt.map(e[1])
                            self._cache[id(src)] = (src, q, _cull_rect(q))
        self.selection = new_sel
        self.documentChanged.emit()
        self.selectionChanged.emit()
        self.update()

    #: rayon du raccord et taille du chanfrein entre deux traits (mm), réglés par la fenêtre principale
    fillet_radius = 2.0
    chamfer_size = 2.0

    def fillet_two(self, a, pa, b, pb, radius=None, chamfer: bool = False) -> bool:
        """Raccord entre les traits a et b cliqués en pa et pb (core.fillet2),
        annulable ; l'arc rejoint le premier trait. False si impossible."""
        from ..core import fillet2 as F2
        r = (self.chamfer_size if chamfer else self.fillet_radius) if radius is None else radius
        ia = next((i for i, c in enumerate(a.path.contours) if not c.closed and c.segments), None)
        ib = next((i for i, c in enumerate(b.path.contours) if not c.closed and c.segments), None)
        if ia is None or ib is None:
            return False
        ia = min((i for i, c in enumerate(a.path.contours) if not c.closed and c.segments),
                 key=lambda i: min(geom.dist(pa, s.start) for s in a.path.contours[i].segments))
        ib = min((i for i, c in enumerate(b.path.contours) if not c.closed and c.segments),
                 key=lambda i: min(geom.dist(pb, s.start) for s in b.path.contours[i].segments))
        got = F2.fillet(a.path.contours[ia], pa, b.path.contours[ib], pb, max(0.0, r), chamfer)
        if got is None:
            return False
        na, nb, arc = got
        if self.undo_push:
            self.undo_push()
        ca = list(a.path.contours)
        ca[ia] = na
        if arc is not None:
            ca.append(arc)
        a.path = Path(ca)
        cb = list(b.path.contours)
        cb[ib] = nb
        b.path = Path(cb)
        self.invalidate([a, b])
        self.documentChanged.emit()
        self.update()
        return True

    #: rayon de la gomme (mm)
    eraser_radius = 1.0

    def blob_paint(self, points, radius: float) -> int:
        """Pinceau à aplat (core.eraser.paint) : la zone peinte, réunie aux
        formes fermées visibles de l'outil courant qu'elle touche, devient une
        forme pleine (annulable). Rend le nombre de formes fondues."""
        from ..core import eraser as ER
        from ..core.pathops import _to_shapely
        region = ER.eraser_region(points, radius)
        tool = self.current_tool_index
        touched = []
        for L in self.doc.layers:
            if not self.layer_shown(L):
                continue
            for it in L.items:
                if isinstance(it, Shape) and it.visible and not it.locked and it.tool == tool and \
                        any(c.closed for c in it.path.contours):
                    b = it.bbox()
                    if b and _to_shapely(Path([c for c in it.path.contours if c.closed])).intersects(region):
                        touched.append(it)
        new = ER.paint([s.path for s in touched], region)
        if not new.contours:
            return 0
        if self.undo_push:
            self.undo_push()
        ids = {id(s) for s in touched}
        for L in self.doc.layers:
            L.items = [it for it in L.items if id(it) not in ids]
        sh = Shape(path=new, tool=tool, filled=True)
        self.doc.add(sh)
        self.select([sh])
        self.invalidate()
        self.documentChanged.emit()
        self.update()
        return len(touched)

    def erase(self, points, radius: float) -> int:
        """Gomme (core.eraser) sur les formes de la sélection, sinon toutes
        les formes visibles et libres ; annulable. Rend le nombre d'objets
        touchés."""
        from ..core import eraser as ER
        region = ER.eraser_region(points, radius)
        changes = []
        for s in self._punch_targets():                  # comme l'emporte-pièce : ni caché, ni verrouillé
            new = ER.erase(s.path, region)
            if new is not None:
                changes.append((s, new))
        if not changes:
            return 0
        if self.undo_push:
            self.undo_push()
        gone = set()
        for s, new in changes:
            if new.contours:
                s.path = new
            else:
                gone.add(id(s))
        if gone:
            self._drop_leaves(gone)                      # une forme gommée en entier quitte aussi son groupe
        self.invalidate()
        self.documentChanged.emit()
        self.update()
        return len(changes)

    # --- emporte-pièce à la souris (demande du 18/11) -----------------------------------------
    def _punch_targets(self, among=None, skip=()) -> list:
        """Les formes que l'emporte-pièce peut couper : les formes visibles et libres des calques montrés et non
        verrouillés — celles de la sélection seulement, s'il y en a une. `among` : des objets (groupes compris) à la
        place de la sélection ; une liste vide : tout le dessin. `skip` : des objets épargnés (la forme prise pour
        pointeur). Reconnus par leur identifiant, que Ctrl+Z garde (il remet des copies des objets)."""
        def key(s):
            return getattr(s, 'id', None) or id(s)
        pool = self.selection if among is None else among
        chosen = {key(s) for s in _leaves(pool)} if pool else None
        spared = {key(s) for s in _leaves(list(skip))} if skip else set()
        return [s for L in self.doc.layers if self.layer_shown(L) and not getattr(L, 'locked', False)
                for s in _leaves(L.items, True)
                if isinstance(s, Shape) and s.visible and not s.locked and (chosen is None or key(s) in chosen)
                and key(s) not in spared]

    def _drop_leaves(self, gone: set) -> None:
        """Les objets d'identité dans `gone` retirés du dessin, où qu'ils soient (dans un groupe aussi : un groupe
        vidé part avec eux) ; la sélection suit."""
        def keep(items):
            out = []
            for it in items:
                if id(it) in gone:
                    continue
                if isinstance(it, Group):
                    it.children = keep(it.children)
                    if not it.children:
                        continue
                out.append(it)
            return out
        for L in self.doc.layers:
            L.items = keep(L.items)
        self.selection = keep(list(self.selection))

    def _punch_nearest(self, dp, reach: float, among=None, skip=()):
        """(forme, rang du contour) du contour le plus proche de `dp` à moins de `reach` mm ; None : aucun."""
        from ..core import punchtool as PT
        best = None
        for s in self._punch_targets(among, skip):
            b = s.bbox()
            if not b or dp[0] < b[0] - reach or dp[0] > b[2] + reach or dp[1] < b[1] - reach or dp[1] > b[3] + reach:
                continue
            i, d = PT.nearest_contour(s.path, dp)
            if i >= 0 and d <= reach and (best is None or d < best[2]):
                best = (s, i, d)
        return best

    def punch_preview(self, dp, spec: dict, among=None, skip=()):
        """Ce que l'emporte-pièce montre sous la souris : (forme posée ou None, morceau retiré ou None) ; `among`,
        `skip` : voir `_punch_targets`."""
        from ..core import punchtool as PT
        kind = spec.get('kind', 'segment')
        if kind == 'segment':
            hit = self._punch_nearest(dp, max(12.0 / max(self.scale, 1e-9), 1e-6), among, skip)
            if hit is None:
                return None, None
            pc = PT.removed_piece(hit[0].path.contours[hit[1]], dp, float(spec.get('length', 0.0)))
            return None, (Path([pc]) if pc is not None and pc.segments else None)
        if kind == 'forme':                              # la forme prise pour pointeur, telle quelle, sous la souris
            return PT.place(spec.get('stamp'), dp), None
        size = float(spec.get('diameter', 0.0)) if kind == 'cercle' else float(spec.get('width', 0.0))
        return PT.region(kind, dp, size, float(spec.get('height', 0.0)), float(spec.get('angle', 0.0))), None

    def punch_at(self, dp, spec: dict, among=None, reach: float | None = None, before=None, skip=()) -> int:
        """L'emporte-pièce appliqué au point `dp` : segment — le contour le plus proche (à 12 px, ou à `reach` mm)
        perd la longueur réglée ; rectangle, cercle, forme — tout ce que la forme couvre est retiré. `among`, `skip` :
        voir `_punch_targets` ; `before()` : appelé à la place du pas d'annulation, juste avant de changer le dessin
        (l'assistant). Annulable ; rend le nombre de formes changées."""
        from ..core import punchtool as PT
        kind = spec.get('kind', 'segment')
        changes = []
        if kind == 'segment':
            near = max(12.0 / max(self.scale, 1e-9), 1e-6) if reach is None else max(float(reach), 1e-6)
            hit = self._punch_nearest(dp, near, among, skip)
            if hit is not None:
                s, i, _d = hit
                rest = PT.remove_length(s.path.contours[i], dp, float(spec.get('length', 0.0)))
                if rest is not None:
                    changes.append((s, Path(list(s.path.contours[:i]) + rest + list(s.path.contours[i + 1:]))))
        else:
            shape, _pc = self.punch_preview(dp, spec)
            if shape is not None:
                for s in self._punch_targets(among, skip):
                    new = PT.punch_region(s.path, shape, bool(getattr(s, 'filled', False)),
                                          open_closed=bool(spec.get('open_closed', False)))
                    if new is not None:
                        changes.append((s, new))
        if not changes:
            return 0
        if before is not None:
            before()
        elif self.undo_push:
            self.undo_push()
        gone = set()
        for s, new in changes:
            kept = [c for c in new.contours if c.segments]
            if kept:
                s.path = Path(kept)
                if getattr(s, 'filled', False) and not any(c.closed for c in kept):
                    s.filled = False                     # une surface ouverte par l'emporte-pièce : un trait
            else:
                gone.add(id(s))
        if gone:
            self._drop_leaves(gone)
        self.invalidate()
        self.documentChanged.emit()
        self.update()
        return len(changes)

    #: saisie de point en cours : ('m2p', [points]) ou ('from', [base]) ; None sinon
    point_mode = None
    #: décalage demandé pour « Depuis » : fonction() → (dx, dy) ou None (fenêtre principale)
    ask_offset_fn = None

    def start_point_mode(self, kind: str) -> bool:
        """Le prochain point de l'outil courant sera le milieu de deux points
        cliqués ('m2p') ou un point de base cliqué plus un décalage ('from')."""
        if self.tool_obj is None:
            return False
        self.point_mode = (kind, [])
        return True

    def _point_modifier(self, dp):
        """Clic pendant une saisie de point : None tant qu'elle n'est pas
        finie, puis le point obtenu (rendu à l'outil)."""
        if self.point_mode is None:
            return dp
        kind, pts = self.point_mode
        pts.append(dp)
        if kind == 'm2p':
            if len(pts) < 2:
                from ..i18n import tr
                self.measured.emit(tr('Milieu : second point'))
                return None
            self.point_mode = None
            return ((pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2)
        self.point_mode = None                           # 'from' : base, puis décalage demandé
        off = self.ask_offset_fn() if self.ask_offset_fn is not None else None
        if off is None:
            return None
        return (pts[0][0] + off[0], pts[0][1] + off[1])

    def place_copies(self, items, dx: float, dy: float) -> int:
        """Copies des objets décalées de (dx, dy), ajoutées au calque de
        chacun (annulable) ; rend leur nombre."""
        from ..core.geom import Affine
        if not items:
            return 0
        if self.undo_push:
            self.undo_push()
        m = Affine.translation(dx, dy)
        for it in items:
            L = self.doc.layer_of(it) or self.doc.active_layer
            L.items.append(it.clone().transformed(m))
        self.invalidate()
        self.documentChanged.emit()
        self.update()
        return len(items)

    def tab_marks(self) -> list:
        """Pontets posés à la main sur les formes visibles : [(x, y)]."""
        return [tuple(p[:2]) for L in self.doc.layers if self.layer_shown(L)
                for leaf in _leaves(L.items, True) if isinstance(leaf, Shape)
                for p in (leaf.extra.get('tabs_xy') or [])]

    def lead_marks(self) -> list:
        """Entrées et sorties posées à la main sur les formes visibles : [(x, y)]."""
        return [tuple(p[:2]) for L in self.doc.layers if self.layer_shown(L)
                for leaf in _leaves(L.items, True) if isinstance(leaf, Shape)
                for p in (leaf.extra.get('lead_xy') or [])]

    def lead_pick(self, dp):
        """Au point cliqué : (forme, indice de sa marque, point de la marque), ou (forme, None, point du contour fermé le plus
        proche, à moins de quelques pixels), ou None."""
        import math
        from shapely.geometry import LineString, Point
        tol = 3 * PICK_PX / max(self.scale, 1e-9)
        best = None
        for L in self.doc.layers:
            if not self.layer_shown(L) or L.locked:
                continue
            for leaf in _leaves(L.items, True):
                if not isinstance(leaf, Shape) or not leaf.visible:
                    continue
                for i, m in enumerate(leaf.extra.get('lead_xy') or []):
                    if math.dist(m[:2], dp) <= tol:
                        return leaf, i, (m[0], m[1])
                for c in leaf.path.contours:
                    pts = c.flatten(0.01)
                    if not c.closed or len(pts) < 3:
                        continue
                    ring = LineString(list(pts) + [pts[0]])
                    d = ring.distance(Point(dp))
                    if d <= tol and (best is None or d < best[0]):
                        q = ring.interpolate(ring.project(Point(dp)))
                        best = (d, leaf, (q.x, q.y))
        return None if best is None else (best[1], None, best[2])

    def toggle_tab(self, dp):
        """Pontet à la main au point cliqué : ôté s'il y en a un tout près,
        sinon posé sur le contour fermé le plus proche (à moins de quelques
        pixels). Rend True (posé), False (ôté) ou None (rien)."""
        import math
        from shapely.geometry import LineString, Point
        tol = 3 * PICK_PX / max(self.scale, 1e-9)
        best = None
        for L in self.doc.layers:
            if not self.layer_shown(L) or L.locked:
                continue
            for leaf in _leaves(L.items, True):
                if not isinstance(leaf, Shape) or not leaf.visible:
                    continue
                marks = leaf.extra.get('tabs_xy') or []
                for i, m in enumerate(marks):
                    if math.dist(m[:2], dp) <= tol:
                        if self.undo_push:
                            self.undo_push()
                        del marks[i]
                        if not marks:
                            leaf.extra.pop('tabs_xy', None)
                        self.documentChanged.emit()
                        return False
                for c in leaf.path.contours:
                    pts = c.flatten(0.01)
                    if not c.closed or len(pts) < 3:
                        continue
                    ring = LineString(list(pts) + [pts[0]])
                    d = ring.distance(Point(dp))
                    if d <= tol and (best is None or d < best[0]):
                        q = ring.interpolate(ring.project(Point(dp)))
                        best = (d, leaf, (q.x, q.y))
        if best is None:
            return None
        if self.undo_push:
            self.undo_push()
        best[1].extra.setdefault('tabs_xy', []).append([best[2][0], best[2][1]])
        self.documentChanged.emit()
        return True

    #: contour de zone : écart toléré entre les traits (mm, 0 : zones fermées seulement)
    boundary_gap = 0.0

    def boundary_at(self, dp, islands: bool = True):
        """Contour de zone : nouvelle forme fermée sur la zone cliquée,
        délimitée par les traits visibles (annulable) ; None si aucune."""
        from ..core.boundary import boundary_at
        paths = []
        for L in self.doc.layers:
            if not self.layer_shown(L):
                continue
            for leaf in _leaves(L.items, True):
                if not leaf.visible:
                    continue
                path = leaf.path if isinstance(leaf, Shape) else getattr(leaf, 'outline', None)
                if path:
                    paths.append(path)
        new = boundary_at(paths, dp, islands=islands, gap=float(self.boundary_gap or 0.0))
        if new is None or not new.contours:
            return None
        if self.undo_push:
            self.undo_push()
        sh = Shape(path=new, tool=self.current_tool_index)
        self.doc.add(sh)
        self.select([sh])
        self.documentChanged.emit()
        self.update()
        return sh

    def stretch(self, rect, dx: float, dy: float) -> int:
        """Étirer : nœuds des formes (de la sélection, sinon toutes les formes
        visibles et libres) pris dans `rect` déplacés de (dx, dy). Annulable ;
        rend le nombre de nœuds déplacés."""
        from ..core import stretch as ST
        shapes = [s for s in _leaves(self.selection) if isinstance(s, Shape)] if self.selection else \
            [s for L in self.doc.layers if self.layer_shown(L) for s in _leaves(L.items, True)
             if isinstance(s, Shape) and s.visible]
        changes = []
        for s in shapes:
            if s.locked or not s.path:
                continue
            new, n = ST.stretch_path(s.path, rect, dx, dy)
            if n:
                changes.append((s, new, n))
        if not changes:
            return 0
        if self.undo_push:
            self.undo_push()
        for s, new, _n in changes:
            s.path = new
        self.invalidate([s for s, _p, _n in changes])
        self.documentChanged.emit()
        self.update()
        return sum(n for _s, _p, n in changes)

    def other_segments(self, it, within=None) -> list:
        """Les segments des objets affichés autres que `it` ; `within` : seulement ceux des objets qui touchent ces bornes."""
        others = []
        for L in self.doc.layers:
            if not self.layer_shown(L):
                continue
            for leaf in _leaves(L.items, True):
                if leaf is it:
                    continue
                path = leaf.path if isinstance(leaf, Shape) else getattr(leaf, 'outline', None)
                if not path:
                    continue
                lb = path.bbox()
                if within is not None and (not lb or lb[0] > within[2] or lb[2] < within[0] or lb[1] > within[3]
                                           or lb[3] < within[1]):
                    continue
                for c in path.contours:
                    others += c.segments
        return others

    def trim_at(self, sp: QPointF, dp, mode: str = 'trim') -> bool:
        """Tronquer (supprimer le morceau cliqué entre deux intersections) ou
        prolonger (le bout le plus proche jusqu'au premier objet) la forme
        sous le curseur. Annulable ; False si rien n'a changé."""
        from ..core import trim as TR
        it = self.pick(sp)
        if not isinstance(it, Shape) or it.locked:
            return False
        others = self.other_segments(it, it.bbox() if mode == 'trim' else None)
        fn = {'trim': TR.trim, 'extend_arc': TR.extend_arc}.get(mode, TR.extend)
        new = fn(it.path, others, dp)
        if new is None:
            return False
        if self.undo_push:
            self.undo_push()
        if any(c.segments for c in new.contours):
            it.path = Path([c for c in new.contours if c.segments])
            self.invalidate([it])
        else:
            L = self.doc.layer_of(it)
            if L is not None:
                L.items = [x for x in L.items if x is not it]
            self.selection = [x for x in self.selection if x is not it]
            self.invalidate()
        self.documentChanged.emit()
        self.update()
        return True

    def symmetry_axis(self) -> float:
        """Abscisse de l'axe du dessin symétrique : milieu de la plaque, sinon 0."""
        pl = self.doc.plate
        return pl.x + pl.width / 2 if pl is not None else 0.0

    def symmetry_center(self) -> tuple[float, float]:
        """Centre de la symétrie cyclique : centre de la plaque, sinon l'origine."""
        pl = self.doc.plate
        return (pl.x + pl.width / 2, pl.y + pl.height / 2) if pl is not None else (0.0, 0.0)

    def _paint_symmetry(self, p: QPainter) -> None:
        if self.symmetric:
            p.setPen(QPen(QColor(canvas_colors()['symmetry']), 1, Qt.PenStyle.DashDotLine))
            x = self.to_screen(self.symmetry_axis(), 0).x()
            p.drawLine(QPointF(x, 0), QPointF(x, self.height()))
        if self.cyclic >= 2:
            import math
            p.setPen(QPen(QColor(canvas_colors()['symmetry']), 1, Qt.PenStyle.DashDotLine))
            c = self.to_screen(*self.symmetry_center())
            r = math.hypot(self.width(), self.height())
            for k in range(self.cyclic):
                a = math.radians(90 + 360.0 * k / self.cyclic)
                p.drawLine(c, QPointF(c.x() + r * math.cos(a), c.y() - r * math.sin(a)))
        self._paint_notes(p)

    # --- notes (post-it) -----------------------------------------------------------------
    NOTE_W, NOTE_PAD = 180, 6

    def notes(self) -> list:
        n = self.doc.extra.get('notes') if isinstance(self.doc.extra, dict) else None
        return n if isinstance(n, list) else []

    def _note_rect(self, note) -> QRectF:
        from PySide6.QtGui import QFontMetrics
        fm = QFontMetrics(self.font())
        lines = str(note.get('text', '')).split('\n') or ['']
        h = fm.height() * max(1, len(lines)) + 2 * self.NOTE_PAD
        w = min(self.NOTE_W * 2, max(80, max(fm.horizontalAdvance(l) for l in lines) + 2 * self.NOTE_PAD))
        pt = self.to_screen(float(note.get('x', 0.0)), float(note.get('y', 0.0)))
        return QRectF(pt.x(), pt.y() - h, w, h)

    def note_at(self, pos: QPointF) -> int | None:
        if not self.show_notes:
            return None
        for i in reversed(range(len(self.notes()))):
            if self._note_rect(self.notes()[i]).contains(pos):
                return i
        return None

    def _paint_notes(self, p: QPainter) -> None:
        if not self.show_notes:
            return
        for note in self.notes():
            r = self._note_rect(note)
            p.setPen(QPen(QColor('#b38f00'), 1))
            p.setBrush(QColor(note.get('color') or '#fff2a8'))
            p.drawRect(r)
            p.setPen(QColor('#3a3000'))
            p.drawText(r.adjusted(self.NOTE_PAD, self.NOTE_PAD, -self.NOTE_PAD, -self.NOTE_PAD),
                       int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop), str(note.get('text', '')))

    def _arm_move(self, drag) -> None:
        """Délai de maintien écoulé : le glisser peut déplacer (curseur
        « déplacement » pour le signaler)."""
        if self._drag is drag and not drag.get('armed'):
            drag['armed'] = True
            self.setCursor(Qt.CursorShape.SizeAllCursor)

    def copy_selection(self, m: Affine) -> list:
        """Copies transformées de la sélection, chacune dans le calque de son
        original ; les originaux ne bougent pas. Annulable ; les copies
        deviennent la sélection."""
        if not self.selection:
            return []
        if self.undo_push:
            self.undo_push()
        out = []
        for it in self.selection:
            c = it.clone().transformed(m)
            L = self.doc.layer_of(it)
            if L is not None:
                L.items.append(c)
            else:
                self.doc.add(c)
            out.append(c)
        self.invalidate()
        self.select(out)
        self.documentChanged.emit()
        return out

    def commit_shape(self, path: Path, *, back_to_select: bool = True) -> Shape:
        """Ajoute une forme dessinée par un outil (annulable), la sélectionne ;
        en dessin symétrique, avec son reflet (raccordé s'il touche l'axe)."""
        if self.symmetric:
            from ..core.symmetric import mirror_join
            from .tools import SNAP_PX
            path = mirror_join(path, self.symmetry_axis(), SNAP_PX / max(self.scale, 1e-9))
        if self.cyclic >= 2:
            # symétrie cyclique : n copies tournées autour du centre de la plaque
            cx, cy = self.symmetry_center()
            path = Path([c.transformed(Affine.rotation(360.0 * k / self.cyclic, (cx, cy)))
                         for k in range(self.cyclic) for c in path.contours])
        if self.undo_push:
            self.undo_push()
        sh = Shape(path=path, tool=self.current_tool_index)
        self.doc.add(sh)
        self.select([sh])
        self.documentChanged.emit()
        if back_to_select:
            self.toolFinished.emit()
        return sh

    def commit_dim(self, dim):
        """Cote paramétrée (core.dims) : groupe annulable, sélectionné ; None pour une cote nulle (deux clics au même
        point, un arc sans longueur), pas posée."""
        from ..core import dims
        if not dims.drawable(dim):
            win = self.window()
            if hasattr(win, 'statusBar'):
                from ..i18n import tr
                win.statusBar().showMessage(tr('Cote nulle : rien n’est posé.'), 4000)
            return None
        if self.undo_push:
            self.undo_push()
        g = dims.group(dim, tool=self.current_tool_index)
        self.doc.add(g)
        self.select([g])
        self.documentChanged.emit()
        return g

    def commit_dimension(self, parts) -> None:
        """Cote = groupe de trois formes : traits, flèches pleines, valeur."""
        from ..core.document import Group
        if self.undo_push:
            self.undo_push()
        lines, heads, txt = parts
        g = Group(children=[Shape(path=lines, tool=self.current_tool_index),
                            Shape(path=heads, filled=True, tool=self.current_tool_index),
                            Shape(path=txt, filled=True, tool=self.current_tool_index)], name='Cote')
        self.doc.add(g)
        self.select([g])
        self.documentChanged.emit()

    # --- souris -------------------------------------------------------------
    #: molette (TypeEdit F5) : 'zoom' ou 'defilement' (Ctrl : zoom, Maj : défilement horizontal)
    wheel_mode = 'zoom'
    #: zoom de la molette inversé (F5) : vers soi pour rapprocher
    wheel_invert = False
    #: clic droit sans glisser, en sélection (TypeEdit F5) : 'aucun', 'zoom', 'annuler', 'poser', 'geler'
    right_click = 'aucun'

    def wheelEvent(self, ev: QWheelEvent) -> None:
        mods = ev.modifiers()
        if self.wheel_mode == 'defilement' and not mods & Qt.KeyboardModifier.ControlModifier:
            d = ev.angleDelta().y() / 120 * 40
            if mods & Qt.KeyboardModifier.ShiftModifier:
                self.ox += d
            else:
                self.oy += d
            self.overlay_update()
            return
        step = ev.angleDelta().y() / 120
        f = 1.2 ** (-step if self.wheel_invert else step)
        self.zoom_at(f, ev.position())

    #: pointeurs montrés au survol d'une poignée de la sélection (ou de son centre de rotation)
    HANDLE_CURSORS = (Qt.CursorShape.SizeFDiagCursor, Qt.CursorShape.SizeVerCursor, Qt.CursorShape.SizeBDiagCursor,
                      Qt.CursorShape.SizeHorCursor, Qt.CursorShape.CrossCursor, Qt.CursorShape.SizeAllCursor,
                      Qt.CursorShape.PointingHandCursor)     # le bouton de rotation

    def _hover_cursor_after_change(self) -> None:
        """La sélection a changé (Suppr, Échap, Ctrl+A, défaire…) : le pointeur qui montrait une poignée redevient
        celui de l'outil s'il n'y a plus de poignée sous lui — sans attendre que la souris bouge."""
        if getattr(self, '_drag', None) or getattr(self, 'tool', None) != 'select' or \
                getattr(self, 'tool_obj', None) is not None:
            return                                       # (aussi pendant la construction de la vue)
        if self.cursor().shape() not in self.HANDLE_CURSORS:
            return
        pos = self._hover_pos
        shape = self._handle_cursor(pos) if pos is not None else None
        if shape is not None:
            self.setCursor(shape)                        # une poignée de la nouvelle sélection : sa flèche à elle
            return
        if pos is not None and self.oblique_guides and self.oblique_at(pos) is not None:
            return                                       # sur un guide oblique : sa flèche reste
        self.unsetCursor()

    def _handle_cursor(self, pos):
        """Le pointeur d'une poignée de la sélection sous `pos` (ou de son centre de rotation), sinon None."""
        if not self.selection:
            return None
        if self.knob_at(pos):
            return Qt.CursorShape.PointingHandCursor
        h = self.handle_at(pos)
        if self.pivot_at(pos) and (h is None or self.pivot is not None):
            return Qt.CursorShape.SizeAllCursor
        if h is None:
            return None
        if self.rot_mode:
            return Qt.CursorShape.CrossCursor
        return (Qt.CursorShape.SizeFDiagCursor, Qt.CursorShape.SizeVerCursor,
                Qt.CursorShape.SizeBDiagCursor, Qt.CursorShape.SizeHorCursor)[h % 4]

    def leaveEvent(self, ev) -> None:                    # noqa: N802 (API Qt)
        self._hover_pos = None                           # le pointeur n'est plus sur la vue
        if not self._drag and self.tool_obj is None:
            self._drop_snap_mark()                       # ni repère ni fil laissés derrière lui
        super().leaveEvent(ev)

    def _drop_snap_mark(self) -> None:
        self._snap_at = None                             # Alt (point suivant) : pas depuis une position passée
        if self._snap_hit is not None:
            self._snap_hit = None
            self.overlay_update()
            from PySide6.QtGui import QCursor
            x, y = self.to_doc(QPointF(self.mapFromGlobal(QCursor.pos())))
            self.snapMoved.emit(x, y, '')                # la barre d'état : plus de point accroché

    #: au-delà de ce nombre d'objets, la flèche de sélection ne cherche pas d'accroche au survol (le tracé, oui)
    HOVER_SNAP_MAX = 5000

    def _hover_snap_ok(self) -> bool:
        """Accroche cherchée au survol avec la flèche : pas sur un très gros dessin (chaque mouvement de la souris
        parcourrait tout). Le compte est gardé tant que les calques gardent leur nombre d'objets."""
        key = (id(self.doc), tuple(len(L.items) for L in self.doc.layers))
        if getattr(self, '_hover_leaves', (None, 0))[0] != key:
            self._hover_leaves = (key, self._leaf_count())
        return self._hover_leaves[1] <= self.HOVER_SNAP_MAX

    def mousePressEvent(self, ev: QMouseEvent) -> None:
        pos = ev.position()
        self._last_mouse = pos
        if ev.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton):
            if self.tool_obj is None:
                self._snap_hit = None                    # la vue défile : le repère ne la suit pas
            self._drag = {'kind': 'pan', 'start': pos, 'ox': self.ox, 'oy': self.oy}
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if ev.button() != Qt.MouseButton.LeftButton:
            return
        if self.tool_obj is not None:
            dp = self.snap_doc(pos, self._tool_exclude())
            dp = self._point_modifier(dp)
            if dp is None:                       # saisie de point en cours (milieu, depuis…)
                self.overlay_update()
                return
            self.snap.anchor = dp                # repérage polaire : depuis le dernier point cliqué
            self.tool_obj.press(pos, dp, ev)
            self.overlay_update()            # un document modifié a déjà forcé le recalcul
            return
        if self.tool != 'select':
            x, y = self.snap_doc(pos)
            self.snap.anchor = (x, y)
            self._drag = {'kind': 'draw', 'tool': self.tool, 'a': (x, y), 'b': (x, y),
                          'mods': ev.modifiers()}
            return
        ni = self.note_at(pos)
        if ni is not None:
            if self.undo_push:
                self.undo_push()                 # déplacer une note s'annule
            n = self.notes()[ni]
            self._drag = {'kind': 'note', 'index': ni, 'start': pos, 'xy': (float(n['x']), float(n['y']))}
            return
        ctrl = bool(ev.modifiers() & Qt.KeyboardModifier.ControlModifier)
        if ev.modifiers() & Qt.KeyboardModifier.AltModifier and not ctrl and self.handle_at(pos) is None \
                and not self.knob_at(pos):               # Alt sur le bouton de rotation : une copie tournée
            it, k, n = self.cycle_pick(pos)              # Alt+clic : objets superposés tour à tour
            if it is not None:
                self._say_cycled(k, n)
                return
        if self.knob_at(pos) and not (self.pivot is not None and self.pivot_at(pos)):   # un centre posé là : lui
            self._drag = {'kind': 'rotate', 'start': pos, 'now': pos, 'bb': self.selection_bbox(), 'handle': None,
                          'p0': self.to_doc(pos), 'm': None, 'knob': True}
            return
        h = self.handle_at(pos)
        if self.pivot_at(pos) and (h is None or self.pivot is not None):
            if ev.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.pivot = None                        # Maj+clic : le centre revient au milieu de la sélection
                self.update()
            else:
                self._drag = {'kind': 'pivot', 'start': pos, 'now': pos}
            return
        gi = self.guide_at(pos) if h is None else None
        if gi is not None and self.pick(pos) is None:
            if self.undo_push:
                self.undo_push()                 # déplacer ou supprimer un guide s'annule
            self._drag = {'kind': 'guide', 'index': gi, 'start': pos}
            return
        oi = self.oblique_at(pos) if h is None and gi is None else None
        if oi is not None and self.pick(pos) is None:
            self._push_obliques()                # ligne de construction : glissée parallèlement, ou supprimée
            self._drag = {'kind': 'oblique', 'index': oi, 'start': pos}
            return
        if h is not None:
            bb = self.selection_bbox()
            kind = 'rotate' if self.rot_mode else 'scale'
            self._drag = {'kind': kind, 'start': pos, 'now': pos, 'bb': bb, 'handle': h,
                          'p0': self.to_doc(pos), 'm': None}
            return
        hit = self.pick(pos)
        op = getattr(self, 'select_op', 'standard')
        if hit is not None and op in ('ajout', 'retrait', 'garder'):
            self.apply_pick([hit])                       # opérateur : le clic choisit, sans déplacer
            return
        if hit is not None:
            if ctrl and op == 'standard':
                self.select([hit], add=True)
                return
            was = any(s is hit for s in self.selection)
            if not was:
                self.select([hit])
            # point saisi : accroché sur l'objet lui-même (on déplace « par » un nœud)
            import time
            self._drag = {'kind': 'move', 'start': pos, 'delta': (0.0, 0.0), 'grab': self.snap_doc(pos),
                          'was_selected': was, 't0': time.monotonic(), 'armed': self.move_delay_ms <= 0}
            if self.move_delay_ms > 0:
                from PySide6.QtCore import QTimer
                drag = self._drag
                QTimer.singleShot(int(self.move_delay_ms), lambda: self._arm_move(drag))
        else:
            if not ctrl and op in ('standard', 'zone'):
                self.select([])
            self._drag = {'kind': 'band', 'start': pos, 'now': pos, 'add': ctrl, 'start_doc': self.to_doc(pos),
                          'boxes': bool(ev.modifiers() & Qt.KeyboardModifier.ShiftModifier)}

    def mouseMoveEvent(self, ev: QMouseEvent) -> None:
        pos = ev.position()
        x, y = self.to_doc(pos)
        self.cursorMoved.emit(x, y)
        d = self._drag
        if not d:
            self._hover_pos = pos
            if self.tool == 'select' and self.tool_obj is None and not self.selection and \
                    self.cursor().shape() in self.HANDLE_CURSORS:
                self.unsetCursor()                       # plus de poignée : le pointeur de l'outil
            if self.tool == 'select' and self.tool_obj is None and (self.guides or self.oblique_guides) and \
                    (not self.selection or self.handle_at(pos) is None):
                gi = self.guide_at(pos)
                if gi is not None:
                    self.setCursor(Qt.CursorShape.SplitVCursor if self.guides[gi][0] == 'h'
                                   else Qt.CursorShape.SplitHCursor)
                    self._drop_snap_mark()                   # sur un guide : le tirer, pas accrocher
                    return
                if self.oblique_at(pos) is not None:
                    self.setCursor(Qt.CursorShape.SizeAllCursor)
                    self._drop_snap_mark()
                    return
                if not self.selection:
                    self.unsetCursor()
            if self.tool == 'select' and self.tool_obj is None and self.selection:
                shape = self._handle_cursor(pos)
                if shape is None:
                    self.unsetCursor()
                else:
                    self.setCursor(shape)
            if self.tool_obj is not None:
                self.tool_obj.move(pos, self.snap_doc(pos, self._tool_exclude()), ev)
                self.overlay_update()
            elif self.snap.enabled:
                had = self._snap_hit
                if self.tool == 'select' and (self._handle_cursor(pos) is not None or not self._hover_snap_ok()):
                    self._drop_snap_mark()               # poignée : un glisser met à l'échelle ; gros dessin : rien au survol
                else:
                    self.snap_doc(pos)                   # aussi avec la flèche : le point qu'un glisser prendrait
                if self.tool != 'select' or had is not None or self._snap_hit is not None:
                    self.overlay_update()
            return
        if d['kind'] == 'pan':
            self.ox = d['ox'] + pos.x() - d['start'].x()
            self.oy = d['oy'] + pos.y() - d['start'].y()
        elif d['kind'] == 'guide':
            gx, gy = self.snap_doc(pos, skip_guide=d['index'])
            g = self.guides[d['index']]
            g[1] = gy if g[0] == 'h' else gx
        elif d['kind'] == 'oblique':
            g = self.oblique_guides[d['index']]
            g[0], g[1] = self.snap_doc(pos, skip_oblique=d['index'])
        elif d['kind'] == 'band':
            self._band_follow_view(d)
            d['now'] = pos
        elif d['kind'] == 'note':
            n = self.notes()[d['index']]
            n['x'] = d['xy'][0] + (pos.x() - d['start'].x()) / self.scale
            n['y'] = d['xy'][1] - (pos.y() - d['start'].y()) / self.scale
        elif d['kind'] == 'move':
            if not d.get('armed', True):
                import time
                if (time.monotonic() - d['t0']) * 1000 < self.move_delay_ms:
                    return                           # pas encore tenu assez longtemps : rien ne bouge
                self._arm_move(d)
            if self.selection and self.drag_out_ok is not None and self.drag_out_ok(ev.globalPosition().toPoint()):
                self.drag_selection_out(d)               # arrivée sur une Bibliothèque (même par-dessus la vue)
                return
            if self.snap.enabled:
                tx, ty = self.snap_doc(pos, exclude=self.selection)
                gx, gy = d['grab']
                dx, dy = tx - gx, ty - gy
            else:
                dx = (pos.x() - d['start'].x()) / self.scale
                dy = -(pos.y() - d['start'].y()) / self.scale
            if ev.modifiers() & Qt.KeyboardModifier.ControlModifier:
                if abs(dx) > abs(dy):
                    dy = 0.0
                else:
                    dx = 0.0
            d['delta'] = (dx, dy)
        elif d['kind'] == 'draw':
            d['b'] = self.snap_doc(pos)
            d['mods'] = ev.modifiers()
        elif d['kind'] == 'scale':
            mods = ev.modifiers()
            pt = self.snap_doc(pos, exclude=self.selection)
            ctrl, alt = bool(mods & Qt.KeyboardModifier.ControlModifier), bool(mods & Qt.KeyboardModifier.AltModifier)
            d['m'] = self.scale_matrix(d['bb'], d['handle'], pt, free=ctrl and alt, whole=ctrl and not alt,
                                       centered=self._tab_held or (ctrl and not alt), anchor=self.pivot)
            d['now'] = pos
        elif d['kind'] == 'rotate' and d.get('knob') and d.get('m') is None and \
                (pos - d['start']).manhattanLength() <= 3:
            d['now'] = pos                               # le bouton : un clic qui tremble ne tourne rien
        elif d['kind'] == 'rotate':
            step = 15.0 if ev.modifiers() & Qt.KeyboardModifier.ControlModifier else 0.0
            d['m'], d['angle'] = self.rotation_matrix(d['bb'], d['p0'], self.to_doc(pos), step=step, center=self.pivot)
            d['now'] = pos
        elif d['kind'] == 'pivot':
            self.pivot = self.snap_doc(pos)              # accroché aux points avec F3, ceux de la sélection compris
            d['now'] = pos
        self.overlay_update()

    def mouseReleaseEvent(self, ev: QMouseEvent) -> None:
        d = self._drag
        self._drag = None
        self._snap_hit = None
        if d and d['kind'] == 'pan':
            self.setCursor(self.tool_obj.cursor if self.tool_obj is not None else Qt.CursorShape.ArrowCursor)
            self.update()                    # scène recalculée à la nouvelle position
            moved = (ev.position() - d['start']).manhattanLength() > 3
            if ev.button() == Qt.MouseButton.RightButton and not moved and self.tool != 'select':
                self.toolExitRequested.emit()  # clic droit dans un mode (cote, tracé…) : retour à la sélection
            elif ev.button() == Qt.MouseButton.RightButton and not moved and self.right_click != 'aucun':
                if self.right_click == 'zoom':
                    self.zoom_at(1.5, ev.position())
                else:
                    self.rightClicked.emit(self.right_click)
            return
        if d and d['kind'] == 'note':
            self.documentChanged.emit()
            self.update()
            return
        if self.tool_obj is not None:
            self.tool_obj.release(ev.position(), self.snap_doc(ev.position(), self._tool_exclude()), ev)
            self.update()
            return
        if not d and self.tool != 'select':              # glisser pris par F2 (take_draft) : le pointeur de l'outil
            return                                       # reste
        self.unsetCursor()
        if not d:
            return
        if d['kind'] in ('guide', 'oblique'):
            pos = ev.position()
            if not self.rect().contains(pos.toPoint()):
                if d['kind'] == 'guide':
                    self.remove_guide(d['index'], record=False)     # ramené sur une règle : supprimé
                else:
                    self.remove_oblique(d['index'], record=False)
            elif (pos - d['start']).manhattanLength() > 1:
                self.documentChanged.emit()
            self.update()
            return
        if d['kind'] == 'band':
            self._band_follow_view(d)
            r = QRectF(d['start'], d['now']).normalized()
            if r.width() < 3 and r.height() < 3:
                self.pick_frozen(d['start'], d.get('add', False))
                self.update()
                return
            self.select_band(d)
        elif d['kind'] == 'move':
            dx, dy = d['delta']
            if abs(dx) > 1e-9 or abs(dy) > 1e-9:
                if ev.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self.copy_selection(Affine.translation(dx, dy))     # Maj au relâchement : copie
                else:
                    self.transform_selection(Affine.translation(dx, dy))
            elif d.get('was_selected'):
                self.toggle_rot_mode()                   # second clic sur la sélection : redimensionner / tourner
        elif d['kind'] in ('scale', 'rotate'):
            if d.get('m') is not None and not d['m'].is_identity:
                keep, pivot = self.rot_mode, self.pivot
                mods = ev.modifiers()
                free = d['kind'] == 'scale' and mods & Qt.KeyboardModifier.ControlModifier    # Ctrl+Alt : sans proportions
                if mods & Qt.KeyboardModifier.ShiftModifier or (mods & Qt.KeyboardModifier.AltModifier and not free):
                    self.copy_selection(d['m'])          # Maj ou Alt : l'original reste
                else:
                    self.transform_selection(d['m'])
                self.rot_mode, self.pivot = keep, pivot
            elif ev.modifiers() & Qt.KeyboardModifier.AltModifier and \
                    (ev.position() - d['start']).manhattanLength() <= 3:     # Alt+clic sans geste sur une poignée
                it, k, n = self.cycle_pick(d['start'])
                if it is not None:
                    self._say_cycled(k, n)
            elif d.get('knob') and (ev.position() - d['start']).manhattanLength() <= 3:
                self.toggle_rot_mode()                   # un clic sur le bouton de rotation : les poignées basculent
        elif d['kind'] == 'draw':
            spec = self._draft_spec(d)
            path = self._draft_path(d) if spec is None else spec.build()
            if spec is not None:
                self.commit_form(spec)               # rectangle, cercle, ellipse : paramètres gardés
            elif path:
                self.commit_shape(path)              # symétries, annulation, sélection
            else:
                self.toolFinished.emit()
        self.update()

    def take_gesture(self) -> dict | None:
        """Le déplacement, la rotation ou l'échelle en cours à la souris, qu'on interrompt pour le finir en chiffres."""
        d = self._drag
        if d is None or d.get('kind') not in ('move', 'rotate', 'scale', 'pivot') or not d.get('armed', True):
            return None
        self._drag = None
        self.update()
        return d

    def take_draft(self):
        """Le tracé d'une forme en cours à la souris (rectangle, ellipse, cercle ; polygone, étoile, spirale), qu'on
        interrompt pour le finir en chiffres (F2) : rend la forme commencée — sa position et sa taille à cet instant
        (Ctrl, Maj comme le tracé), le reste aux réglages retenus de l'outil ; sans taille encore : la forme retenue,
        au point du clic. None : aucun tracé de forme en cours. Le glisser est abandonné (aperçu effacé, relâcher le
        bouton ne pose plus rien)."""
        d, take = self._drag, getattr(self.tool_obj, 'take_draft', None)
        self.draft_anchor = None                         # rectangle, ellipse : le coin cliqué et le sens du glisser
        if d is not None and d.get('kind') == 'draw' and d['tool'] in ('rect', 'ellipse', 'circle'):
            self._drag = None
            kind, at, spec = d['tool'], d['a'], self._draft_spec(d)
            mods = d.get('mods') or Qt.KeyboardModifier.NoModifier
            if kind != 'circle' and spec is not None and not (mods & Qt.KeyboardModifier.ShiftModifier):
                (ax, ay), (bx, by) = d['a'], d['b']      # (Maj : tracé depuis le centre, qui reste le centre)
                self.draft_anchor = (ax, ay, 1.0 if bx >= ax else -1.0, 1.0 if by >= ay else -1.0)
        elif take is not None:
            got = take()                                 # polygone, étoile, spirale : l'outil rend son glisser
            if got is None:
                return None
            kind, at, spec = got
        else:
            return None
        keep = self.form_default(kind)
        if spec is None:                                 # pas encore de taille : la forme retenue, au point du clic
            spec = keep
            spec.cx, spec.cy = at
        else:
            for name in ('width', 'height'):             # un côté sans longueur : celui retenu
                if getattr(spec, name, 1.0) < 1e-6:
                    setattr(spec, name, getattr(keep, name))
        self._snap_hit = None
        self.update()
        return spec

    # --- points par coordonnées --------------------------------------------------------
    class _Click:
        """Clic simulé (bouton gauche, sans modificateur) pour un point saisi."""

        def __init__(self, pos):
            self._pos = pos

        def position(self):
            return self._pos

        @staticmethod
        def modifiers():
            return Qt.KeyboardModifier.NoModifier

        @staticmethod
        def button():
            return Qt.MouseButton.LeftButton

        @staticmethod
        def buttons():
            return Qt.MouseButton.LeftButton

    def click_at(self, x: float, y: float) -> bool:
        """Un clic de l'outil de dessin courant au point exact (x, y) du
        dessin, sans accrochage ; False si l'outil n'en prend pas."""
        if self.tool_obj is None:
            return False
        sp = self.to_screen(x, y)
        ev = self._Click(sp)
        tool = self.tool_obj
        tool.press(sp, (x, y), ev)
        if self.tool_obj is tool:                    # l'outil a pu finir (forme posée) au clic
            tool.release(sp, (x, y), ev)
        self.overlay_update()
        return True

    def draw_between(self, a, b):
        """Rectangle, ellipse ou trait de `a` à `b` (outil courant)."""
        d = {'tool': self.tool, 'a': tuple(a), 'b': tuple(b), 'mods': None}
        spec = self._draft_spec(d)
        if spec is not None:
            return self.commit_form(spec)
        path = self._draft_path(d)
        return self.commit_shape(path) if path else None

    def form_default(self, kind: str):
        """Forme par défaut de ce type (réglages de l'outil)."""
        from ..core import forms
        if self.form_defaults_fn is not None:
            try:
                return self.form_defaults_fn(kind)
            except Exception:                         # noqa: BLE001 — réglage illisible
                pass
        return forms.TYPES[kind]()

    def _draft_spec(self, d):
        """Rectangle, cercle ou ellipse tracé, en forme paramétrée ; None sinon."""
        if d['tool'] not in ('rect', 'ellipse', 'circle'):
            return None
        path = self._draft_path(d)
        if path is None:
            return None
        if d['tool'] == 'circle':                        # le centre au premier point, le rayon jusqu'au second
            spec = self.form_default('circle')
            spec.cx, spec.cy = d['a']
            spec.diameter = 2 * math.hypot(d['b'][0] - d['a'][0], d['b'][1] - d['a'][1])
            return spec
        x0, y0, x1, y1 = path.bbox()
        spec = self.form_default(d['tool'])
        spec.cx, spec.cy, spec.width, spec.height = (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0
        spec.angle = 0.0
        return spec

    def commit_form(self, spec, *, back_to_select: bool = True):
        """Ajoute une forme paramétrée (annulable), la sélectionne ; en
        dessin symétrique ou cyclique, une courbe ordinaire."""
        from ..core import forms
        if self.symmetric or self.cyclic >= 2:
            return self.commit_shape(spec.build(), back_to_select=back_to_select)
        if self.undo_push:
            self.undo_push()
        sh = forms.make(spec, tool=self.current_tool_index)
        self.doc.add(sh)
        self.select([sh])
        self.documentChanged.emit()
        if back_to_select:
            self.toolFinished.emit()
        return sh

    def _draft_path(self, d) -> Path | None:
        (ax, ay), (bx, by) = d['a'], d['b']
        mods = d.get('mods') or Qt.KeyboardModifier.NoModifier
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        from_center = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        w, h = bx - ax, by - ay
        if abs(w) < 1e-6 and abs(h) < 1e-6:
            return None
        t = d['tool']
        if t == 'circle':                           # cercle : du centre au rayon
            return Path([geom.circle((ax, ay), math.hypot(w, h))])
        if t in ('rect', 'ellipse'):
            if ctrl and not from_center:           # carré / cercle
                s = max(abs(w), abs(h))
                w, h = math.copysign(s, w or 1), math.copysign(s, h or 1)
            if from_center:
                x0, y0, W, H = ax - w, ay - h, 2 * w, 2 * h
            else:
                x0, y0, W, H = ax, ay, w, h
            x0, W = (x0 + W, -W) if W < 0 else (x0, W)
            y0, H = (y0 + H, -H) if H < 0 else (y0, H)
            if t == 'rect':
                return Path([geom.rect(x0, y0, W, H)])
            return Path([geom.ellipse((x0 + W / 2, y0 + H / 2), W / 2, H / 2)])
        if t == 'line':
            if ctrl:                                # 0 / 45 / 90°
                ang = round(math.atan2(h, w) / (math.pi / 4)) * (math.pi / 4)
                L = math.hypot(w, h)
                bx, by = ax + L * math.cos(ang), ay + L * math.sin(ang)
            return Path([geom.polyline([(ax, ay), (bx, by)])])
        return None

    def mouseDoubleClickEvent(self, ev: QMouseEvent) -> None:
        pos = ev.position()
        self.last_double = QPointF(pos)                  # le point du double clic (un texte repris : son mot)
        if ev.button() == Qt.MouseButton.MiddleButton:  # double-clic sur la molette : tout voir (TypeEdit)
            self.fit()
            return
        if ev.button() != Qt.MouseButton.LeftButton:
            return
        if self.tool_obj is not None:
            self.tool_obj.double(pos, self.snap_doc(pos, self._tool_exclude()), ev)
            self.update()
            return
        ni = self.note_at(pos)
        if ni is not None:
            self.noteDoubleClicked.emit(ni)
            return
        hit = self.pick(pos)
        if hit is not None:
            self.itemDoubleClicked.emit(hit)
            return
        gi = self.guide_at(pos)
        if gi is not None:
            self.guideDoubleClicked.emit(gi)
            return
        oi = self.oblique_at(pos)
        if oi is not None:
            self.obliqueDoubleClicked.emit(oi)

    # --- glisser-déposer -----------------------------------------------------
    def drag_selection_out(self, d, exec_drag: bool = True):
        """Le déplacement en cours sort de la vue : il s'arrête (rien n'a bougé) et la sélection part en
        glisser-déposer — lâchée sur la Bibliothèque : ajoutée ; de nouveau dans la vue : déplacée là ; ailleurs :
        rien. Rend le QDrag."""
        from PySide6.QtCore import QMimeData
        from PySide6.QtGui import QDrag
        self._drag = None
        self._snap_hit = None                            # le repère d'accrochage du déplacement arrêté
        self.unsetCursor()
        self._out_grab = d.get('grab') or self.to_doc(d['start'])
        mime = QMimeData()
        mime.setData(SELECTION_MIME, selection_token())
        drag = QDrag(self)
        drag.setMimeData(mime)
        self.overlay_update()
        if exec_drag:
            try:
                drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction, Qt.DropAction.CopyAction)
            finally:
                self._out_grab = None
        return drag

    def _accept_selection(self, ev) -> bool:
        """La sélection sortie de cette vue y revient : déplacée (Maj : copiée) — le curseur le dit."""
        if not (own_selection_drag(ev) and self._out_grab is not None):
            return False
        shift = bool(ev.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        ev.setDropAction(Qt.DropAction.CopyAction if shift else Qt.DropAction.MoveAction)
        ev.accept()
        return True

    def dragEnterEvent(self, ev) -> None:
        if not self._accept_selection(ev) and ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dragMoveEvent(self, ev) -> None:
        if not self._accept_selection(ev) and ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev) -> None:
        if ev.mimeData().hasFormat(SELECTION_MIME):
            if not own_selection_drag(ev):               # d'une autre instance : rien
                return
            grab, self._out_grab = self._out_grab, None
            if grab is not None and self.selection:      # sortie puis revenue : déplacée là (Maj : copie, Ctrl : axe)
                tx, ty = self.snap_doc(ev.position(), exclude=self.selection) if self.snap.enabled else \
                    self.to_doc(ev.position())
                self._snap_hit = None
                dx, dy = tx - grab[0], ty - grab[1]
                mods = ev.modifiers()
                if mods & Qt.KeyboardModifier.ControlModifier:
                    if abs(dx) > abs(dy):
                        dy = 0.0
                    else:
                        dx = 0.0
                if abs(dx) > 1e-9 or abs(dy) > 1e-9:
                    if mods & Qt.KeyboardModifier.ShiftModifier:
                        self.copy_selection(Affine.translation(dx, dy))
                    else:
                        self.transform_selection(Affine.translation(dx, dy))
                ev.setDropAction(Qt.DropAction.CopyAction if mods & Qt.KeyboardModifier.ShiftModifier
                                 else Qt.DropAction.MoveAction)
                ev.accept()
                self.update()
            return
        x, y = self.to_doc(ev.position())
        for url in ev.mimeData().urls():
            if url.isLocalFile():
                self.fileDropped.emit(url.toLocalFile(), x, y)
        ev.acceptProposedAction()

    # --- clavier ------------------------------------------------------------
    def event(self, ev) -> bool:
        if ev.type() == QEvent.Type.ShortcutOverride and self.tool_obj is not None \
                and self.tool_obj.wants_key(ev):
            ev.accept()
            return True
        # Tab change le focus avant keyPressEvent : un outil qui le veut (type
        # de cote) le reçoit ici
        if ev.type() == QEvent.Type.KeyPress and ev.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab) \
                and self.tool_obj is not None and self.tool_obj.wants_key(ev):
            if self.tool_obj.key(ev):
                self.update()
            return True
        # Tab avec une sélection : elle reste ici pour l'échelle depuis le centre, sans passer au champ suivant
        if ev.type() == QEvent.Type.KeyPress and ev.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab) \
                and self.tool_obj is None and self.selection:
            self._tab_held = True
            return True
        if (ev.type() == QEvent.Type.KeyRelease and ev.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab)
                and not ev.isAutoRepeat()) or ev.type() == QEvent.Type.FocusOut:
            self._tab_held = False
        return super().event(ev)

    def keyPressEvent(self, ev: QKeyEvent) -> None:
        if self.tool_obj is not None and self.tool_obj.key(ev):
            self.update()
            return
        k = ev.key()
        if k == Qt.Key.Key_Alt and not ev.isAutoRepeat() and self.cycle_snap():
            return
        dirs = {Qt.Key.Key_Left: (-1, 0), Qt.Key.Key_Right: (1, 0), Qt.Key.Key_Up: (0, 1), Qt.Key.Key_Down: (0, -1)}
        if k in dirs and ev.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Ctrl+flèche : « pas de déplacement ? » — la valeur validée déplace
            # la sélection dans ce sens et devient le pas des flèches suivantes
            self.stepRequested.emit(*dirs[k])
            return
        if k in dirs and self.selection:
            mods = ev.modifiers()
            dx, dy = dirs[k]
            if mods & Qt.KeyboardModifier.ShiftModifier:
                step = 10 * self.nudge_mm
            else:
                step = self.arrow_step or self.nudge_mm
            self.transform_selection(Affine.translation(dx * step, dy * step))
            return
        if k == Qt.Key.Key_Escape:
            self._drag = None
            if self.tool_obj is not None:
                self.tool_obj.cancel()
            if self.tool != 'select':
                self.toolFinished.emit()
            else:
                self.select([])
            return
        super().keyPressEvent(ev)

    def keyReleaseEvent(self, ev: QKeyEvent) -> None:
        """Une touche relâchée : à l'outil en cours s'il le veut (`key_release`, vrai : prise), sinon comme avant."""
        release = getattr(self.tool_obj, 'key_release', None)
        if release is not None and release(ev):
            self.update()
            return
        super().keyReleaseEvent(ev)

    def resizeEvent(self, ev) -> None:
        # première taille, ou taille rejouée par Qt (plan de travail redimensionné pendant qu'il était caché :
        # ancienne taille -1) : « Tout voir », sauf si la vue a été zoomée ou déplacée depuis le dernier cadrage
        if ev.oldSize().width() <= 0 and (self._fit_view is None or
                                          self._fit_view == (self.scale, self.ox, self.oy)):
            self.fit()
        super().resizeEvent(ev)


def _leaves(items, visible_only: bool = False):
    for it in items:
        if visible_only and not it.visible:
            continue
        if isinstance(it, Group):
            yield from _leaves(it.children, visible_only)
        else:
            yield it
