"""Round 358 : courbe par points (SPLINE par points de lissage) — passe par
tous les points, sans angle, ouverte ou fermée."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom

app = QApplication.instance() or QApplication([])
PTS = [(0, 0), (10, 8), (20, 0), (30, 8)]


def turn(a, b):
    u = (a.p3[0] - a.p2[0], a.p3[1] - a.p2[1])         # tangente d'arrivée du premier
    v = (b.p1[0] - b.p0[0], b.p1[1] - b.p0[1])         # tangente de départ du suivant
    return abs(math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1]))


class TestSpline(unittest.TestCase):
    def test_open(self):
        c = geom.through_points(PTS)
        self.assertEqual(len(c.segments), 3)
        self.assertEqual([s.start for s in c.segments] + [c.segments[-1].end], PTS)   # passe par les points
        for a, b in zip(c.segments, c.segments[1:]):
            self.assertLess(turn(a, b), 1e-9)                                         # sans angle

    def test_closed(self):
        c = geom.through_points([(0, 0), (10, 0), (10, 10), (0, 10)], closed=True)
        self.assertTrue(c.closed)
        self.assertEqual(len(c.segments), 4)
        self.assertLess(turn(c.segments[-1], c.segments[0]), 1e-9)
        self.assertEqual(len(geom.through_points([(0, 0), (5, 5)]).segments), 1)

    def test_tool(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            w.set_tool('spline')
            t = c.tool_obj
            e = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton,
                            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            for p in PTS:
                t.press(c.to_screen(*p), p, e)
            t.key(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier))
            sh = c.doc.layers[0].items[0]
            self.assertTrue(all(s.kind == 'C' for s in sh.path.contours[0].segments))
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
