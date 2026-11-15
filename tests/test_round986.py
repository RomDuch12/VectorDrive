"""Round 986 : retours de l'atelier — dans une sélection de plusieurs objets, chacun a son cadre pointillé (un groupe,
un seul) ; l'accrochage est actif d'office, sur les nœuds et les intersections (pas la grille), une fois même pour qui
l'avait laissé éteint ; au survol, un petit cercle entoure le point accroché et un fil le relie au pointeur, aussi
avec la flèche de sélection."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r986.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QImage, QMouseEvent, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Group, Shape  # noqa: E402

app = QApplication.instance() or QApplication([])
KEYS = ('options/accrochage', 'options/accrochage_986')


def prefs(**values):
    """Les réglages avant d'ouvrir la fenêtre : accrochage du premier lancement (rien), ou ceux donnés."""
    from vectordrive.portable import settings
    st = settings()
    for k in KEYS:
        st.remove(k)
    for k, v in values.items():
        st.setValue(k.replace('__', '/'), v)
    st.sync()


def window():
    from vectordrive.ui.main_window import MainWindow
    w = MainWindow()
    w.settings.setValue('fenetre/plein_ecran', False)
    w.resize(1200, 800)
    w.show()
    app.processEvents()
    return w


def close(w):
    w.modified = False
    for t in getattr(w, 'docs', []):
        t.modified = False
    w.close()
    app.processEvents()


def restore():
    """Les essais d'avant gardent l'accrochage éteint (graine de tests/__init__)."""
    prefs(options__accrochage=False, options__accrochage_986='1')


class Spy(QPainter):
    """Retient ce que peignent les fonctions du plan de travail (écrites en Python)."""

    def __init__(self, dev):
        super().__init__(dev)
        self.rects, self.lines, self.ellipses = [], [], []

    def drawRect(self, *a):                                   # noqa: N802 (API Qt)
        self.rects.append(QRectF(a[0]) if len(a) == 1 else QRectF(*a))
        super().drawRect(*a)

    def drawLine(self, *a):                                   # noqa: N802 (API Qt)
        self.lines.append(a)
        super().drawLine(*a)

    def drawEllipse(self, *a):                                # noqa: N802 (API Qt)
        self.ellipses.append(a)
        super().drawEllipse(*a)


def spy_paint(c, fn):
    img = QImage(c.size(), QImage.Format.Format_ARGB32)
    img.fill(0)
    p = Spy(img)
    try:
        fn(p)
    finally:
        p.end()
    return p


def screen_rect(c, b):
    return QRectF(c.to_screen(b[0], b[1]), c.to_screen(b[2], b[3])).normalized()


def near(r1, r2, tol=0.6):
    return all(abs(u - v) <= tol for u, v in ((r1.left(), r2.left()), (r1.top(), r2.top()),
                                            (r1.right(), r2.right()), (r1.bottom(), r2.bottom())))


class Frames(unittest.TestCase):

    def test_each_selected_object_has_its_frame(self):
        """Trois objets choisis (dont un groupe) : trois cadres, celui du groupe autour de ses deux objets ; un seul
        objet choisi : seulement le cadre à poignées."""
        prefs(options__accrochage=False, options__accrochage_986='1')
        w = window()
        try:
            c, d = w.canvas, w.canvas.doc
            a = Shape(path=geom.Path([geom.circle((10, 10), 5)]))
            b = Shape(path=geom.Path([geom.circle((40, 10), 5)]))
            g = Group(children=[Shape(path=geom.Path([geom.rect(0, 30, 8, 8)])),
                                Shape(path=geom.Path([geom.rect(30, 40, 8, 8)]))])
            for it in (a, b, g):
                d.add(it)
            c.select([a, b, g])
            frames = c.selection_frames()
            self.assertEqual(len(frames), 3)
            want = [screen_rect(c, it.bbox()) for it in (a, b, g)]
            for f, r in zip(frames, want):
                self.assertTrue(near(f, r), (f, r))
            p = spy_paint(c, c._paint_selection)
            for r in want:
                self.assertTrue(any(near(x, r) for x in p.rects), r)      # chacun peint
            self.assertTrue(any(near(x, screen_rect(c, c.selection_bbox())) for x in p.rects))
            c.select([a])
            self.assertEqual(c.selection_frames(), [])
        finally:
            close(w)
            restore()


class SnapAtStart(unittest.TestCase):

    def tearDown(self):
        restore()

    def test_first_launch_snaps_on_nodes_and_intersections(self):
        prefs()
        w = window()
        try:
            self.assertTrue(w.A['snap'].isChecked())
            self.assertTrue(w.canvas.snap.enabled)
            self.assertEqual(w.canvas.snap.modes, {'node', 'intersection', 'guide'})
            for k in ('middle', 'center', 'grid', 'nearest'):
                self.assertFalse(w.A[f'snap_{k}'].isChecked(), k)
            for k in ('node', 'intersection', 'guide'):
                self.assertTrue(w.A[f'snap_{k}'].isChecked(), k)
        finally:
            close(w)

    def test_left_off_is_switched_on_once(self):
        """Laissé éteint avant : allumé une fois ; éteint de nouveau dans F10, il le reste."""
        prefs(options__accrochage=False)
        w = window()
        try:
            self.assertTrue(w.A['snap'].isChecked())
            self.assertIn(w.settings.value('options/accrochage'), (True, 'true'))
            self.assertEqual(str(w.settings.value('options/accrochage_986')), '1')
        finally:
            close(w)
        from vectordrive.portable import settings
        st = settings()
        st.setValue('options/accrochage', False)
        st.sync()
        w = window()
        try:
            self.assertFalse(w.A['snap'].isChecked())
        finally:
            close(w)

    def test_options_ok_does_not_switch_it_back_on(self):
        """Éteint d'un Maj+F3, puis F10 › OK pour autre chose : il reste éteint ; le choix d'office est un choix rapide."""
        prefs()
        w = window()
        try:
            self.assertTrue(w.A['snap'].isChecked())
            w.A['snap'].setChecked(False)
            w.apply_options()
            self.assertFalse(w.A['snap'].isChecked())
            self.assertEqual(w.SNAP_PRESETS[0][1], {'node', 'intersection', 'guide'})
            w._cycle_snap(1)
            w._cycle_snap(-1)
            self.assertEqual(w.canvas.snap.modes, {'node', 'intersection', 'guide'})   # on y revient
        finally:
            close(w)

    def test_a_dragged_guide_follows_the_pointer(self):
        """Un guide tiré ne s'accroche pas à lui-même : il suit le pointeur, même tout près de sa place."""
        prefs()
        w = window()
        try:
            c = w.canvas
            w.A['snap'].setChecked(True)                                         # accrochage aux guides (d'office ici)
            w.A['snap_guide'].setChecked(True)
            c.scale, c.ox, c.oy = 4.0, 100.0, 500.0
            c.guides.append(['h', 10.0])
            for y in (10.4, 10.9, 11.5):
                p = QPointF(c.to_screen(50.0, y))
                c._drag = {'kind': 'guide', 'index': len(c.guides) - 1, 'start': p}
                c.mouseMoveEvent(QMouseEvent(QEvent.Type.MouseMove, p, p, Qt.MouseButton.NoButton,
                                             Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
                self.assertAlmostEqual(c.guides[-1][1], y, places=6)
            c._drag = None
        finally:
            close(w)


class HoverRing(unittest.TestCase):

    def test_ring_and_wire_while_hovering_with_the_arrow(self):
        prefs()
        w = window()
        try:
            c, d = w.canvas, w.canvas.doc
            s = Shape(path=geom.Path([geom.rect(0, 0, 30, 20)]))
            d.add(s)
            c.invalidate()
            self.assertEqual(c.tool, 'select')
            node = c.to_screen(30, 20)
            at = node + QPointF(4, 3)
            p0 = QPointF(at)
            c.mouseMoveEvent(QMouseEvent(QEvent.Type.MouseMove, p0, p0, Qt.MouseButton.NoButton,
                                         Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier))
            h = c._snap_hit
            self.assertIsNotNone(h)
            self.assertEqual((h.kind, round(h.x, 6), round(h.y, 6)), ('node', 30.0, 20.0))
            p = spy_paint(c, c._paint_snap)
            ring = [e for e in p.ellipses if len(e) == 3 and abs(e[0].x() - node.x()) < 0.01
                    and abs(e[0].y() - node.y()) < 0.01 and abs(e[1] - c.SNAP_RING_PX) < 0.01]
            self.assertTrue(ring, p.ellipses)
            wire = [ln for ln in p.lines if len(ln) == 2 and (ln[0] - at).manhattanLength() < 0.01
                    and (ln[1] - node).manhattanLength() < 0.01]
            self.assertTrue(wire, p.lines)
            far = QPointF(c.to_screen(15, 60))
            c.mouseMoveEvent(QMouseEvent(QEvent.Type.MouseMove, far, far, Qt.MouseButton.NoButton,
                                         Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier))
            self.assertIsNone(c._snap_hit)
            c.mouseMoveEvent(QMouseEvent(QEvent.Type.MouseMove, p0, p0, Qt.MouseButton.NoButton,
                                         Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier))
            c.leaveEvent(QEvent(QEvent.Type.Leave))
            self.assertIsNone(c._snap_hit)                                     # sorti de la vue : plus de repère
            # repère d'une position passée (la molette a zoomé sans bouger la souris) : rien de peint
            c.mouseMoveEvent(QMouseEvent(QEvent.Type.MouseMove, p0, p0, Qt.MouseButton.NoButton,
                                         Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier))
            self.assertIsNotNone(c._snap_hit)
            c.zoom_at(4.0, QPointF(10, 10))
            p = spy_paint(c, c._paint_snap)
            self.assertEqual((p.ellipses, p.lines), ([], []))
            # sur la poignée d'une forme choisie : un glisser la met à l'échelle, pas d'accroche montrée
            c.zoom_at(0.25, QPointF(10, 10))
            c.select([s])
            corner = QPointF(c.to_screen(*c.doc_handles(c.selection_bbox())[2]))
            c.mouseMoveEvent(QMouseEvent(QEvent.Type.MouseMove, corner, corner, Qt.MouseButton.NoButton,
                                         Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier))
            self.assertIsNotNone(c._handle_cursor(corner))
            self.assertIsNone(c._snap_hit)
        finally:
            close(w)
            restore()


if __name__ == '__main__':
    unittest.main()
