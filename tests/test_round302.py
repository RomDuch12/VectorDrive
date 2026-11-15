"""Round 302 : étirer (comme ÉTIRER en DAO) — nœuds dans la fenêtre de
capture déplacés, poignées attachées, arcs entiers gardés, annulable."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QImage, QMouseEvent, QPainter
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core import stretch as ST
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


def ev():
    return QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton,
                       Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)


class TestStretch(unittest.TestCase):
    def test_rect(self):
        p = geom.Path([geom.rect(0, 0, 10, 5)])
        new, n = ST.stretch_path(p, (8, -1, 12, 6), 5, 0)                 # côté droit tiré
        self.assertEqual(n, 2)
        b = new.bbox()
        self.assertEqual((b[0], b[2], b[3]), (0, 15, 5))

    def test_curves(self):
        c = geom.circle((0, 0), 5)                                         # arcs entiers déplacés en bloc
        new, n = ST.stretch_path(geom.Path([c]), (-10, -10, 10, 10), 3, 4)
        cp = new.contours[0].segments[0].circle_params()
        self.assertAlmostEqual(cp[0][0], 3, 6)
        self.assertAlmostEqual(cp[0][1], 4, 6)
        cu = geom.Contour([geom.Cubic((0, 0), (1, 1), (2, 1), (3, 0))])
        new, n = ST.stretch_contour(cu, (2.5, -1, 4, 1), 1, 0)            # la poignée suit son nœud
        s = new.segments[0]
        self.assertEqual((s.p0, s.p1, s.p2, s.p3), ((0, 0), (1, 1), (3, 1), (4, 0)))
        self.assertEqual(n, 1)

    def test_tool(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            s = Shape(path=geom.Path([geom.rect(0, 0, 10, 5)]))
            c.doc.add(s)
            w.set_tool('stretch')
            t = c.tool_obj
            for p in ((8, -1), (12, 6), (10, 0)):
                t.press(c.to_screen(*p), p, ev())
            t.move(c.to_screen(14, 0), (14, 0), ev())
            im = QImage(100, 100, QImage.Format.Format_ARGB32)
            pa = QPainter(im)
            t.paint(pa)
            pa.end()
            t.press(c.to_screen(14, 0), (14, 0), ev())
            self.assertEqual(s.path.bbox()[2], 14)
            w.undo()
            self.assertEqual(c.doc.layers[0].items[0].path.bbox()[2], 10)
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
