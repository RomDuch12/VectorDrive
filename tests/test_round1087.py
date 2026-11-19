"""Round 1087 (demande du 18/11 soir) : « Selection ensemble contours : bouton de rotation à la souris »."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1087.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402

app = QApplication.instance() or QApplication([])


def mouse(kind, pos, mods=Qt.KeyboardModifier.NoModifier):
    t = {'press': QEvent.Type.MouseButtonPress, 'move': QEvent.Type.MouseMove, 'release': QEvent.Type.MouseButtonRelease}[kind]
    btn = Qt.MouseButton.LeftButton
    return QMouseEvent(t, QPointF(pos), QPointF(pos), btn, btn if kind != 'release' else Qt.MouseButton.NoButton, mods)


class Knob(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.resize(1200, 800)
        self.w.show()
        app.processEvents()
        self.addCleanup(self.close)
        c = self.w.canvas
        self.a = Shape(path=geom.Path([geom.rect(0, 0, 40, 10)]), tool=0)
        self.b = Shape(path=geom.Path([geom.rect(0, 20, 40, 10)]), tool=0)
        c.doc.add(self.a)
        c.doc.add(self.b)
        c.zoom_fit() if hasattr(c, 'zoom_fit') else None
        app.processEvents()
        c.select([self.a, self.b])                       # un ensemble de contours

    def close(self):
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def knob(self):
        c = self.w.canvas
        bb = c.selection_bbox()
        top = c.to_screen((bb[0] + bb[2]) / 2, bb[3])
        return QPointF(top.x(), top.y() - c.KNOB_PX)

    def test_dragging_the_knob_turns_the_selection(self):
        c = self.w.canvas
        k = self.knob()
        self.assertTrue(c.knob_at(k), 'avant : pas de bouton de rotation')
        cx, cy = 20.0, 15.0
        centre = c.to_screen(cx, cy)
        right = QPointF(centre.x() + (centre.y() - k.y()), centre.y())    # un quart de tour, sens horaire
        c.mousePressEvent(mouse('press', k))
        c.mouseMoveEvent(mouse('move', right))
        c.mouseReleaseEvent(mouse('release', right))
        bb = c.selection_bbox()
        self.assertAlmostEqual(bb[2] - bb[0], 30.0, places=3)             # 40 × 30 devenu 30 × 40
        self.assertAlmostEqual(bb[3] - bb[1], 40.0, places=3)
        self.assertAlmostEqual((bb[0] + bb[2]) / 2, cx, places=3)
        self.w.undo()
        items = [x for L in self.w.canvas.doc.layers for x in L.items if isinstance(x, Shape)]
        boxes = sorted(tuple(round(v, 6) for v in x.bbox()) for x in items)
        self.assertEqual(boxes, [(0.0, 0.0, 40.0, 10.0), (0.0, 20.0, 40.0, 30.0)])

    def test_a_click_on_the_knob_shows_the_rotation_handles(self):
        c = self.w.canvas
        k = self.knob()
        self.assertFalse(c.rot_mode)
        c.mousePressEvent(mouse('press', k))
        c.mouseReleaseEvent(mouse('release', k))
        self.assertTrue(c.rot_mode)
        self.assertEqual(len(c.selection), 2)
        c.mousePressEvent(mouse('press', k))
        c.mouseReleaseEvent(mouse('release', k))
        self.assertFalse(c.rot_mode)
        bb = c.selection_bbox()
        c.mousePressEvent(mouse('press', k))                                # un clic qui tremble de 2 pixels
        c.mouseMoveEvent(mouse('move', k + QPointF(2, 0)))
        c.mouseReleaseEvent(mouse('release', k + QPointF(2, 0)))
        self.assertTrue(c.rot_mode)
        self.assertEqual(c.selection_bbox(), bb)                             # rien n'a tourné

    def test_no_knob_in_another_tool_or_without_selection(self):
        c = self.w.canvas
        k = self.knob()
        c.rot_knob = False
        self.assertFalse(c.knob_at(k))
        c.rot_knob = True
        c.select([])
        self.assertFalse(c.knob_at(k))

    def test_the_ribbon_button(self):
        w = self.w
        self.assertIn('rotate_mouse', w.A)
        w.A['rotate_mouse'].trigger()
        self.assertTrue(w.canvas.rot_mode)
        self.assertEqual(len(w.canvas.selection), 2)
        w.canvas.select([])
        with mock.patch.object(w.statusBar(), 'showMessage') as said:
            w.A['rotate_mouse'].trigger()
        self.assertTrue(said.called)


if __name__ == '__main__':
    unittest.main()
