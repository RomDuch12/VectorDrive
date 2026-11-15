"""Round 742 : Polygone circonscrit (POLYGON, option Circonscrit, d'après
CADCraft) — Maj avec l'outil Polygone : le pointeur au milieu d'un côté."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))


class TestPolygonSide(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.resize(1000, 700)

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def drag(self, a, b, mods):
        from PySide6.QtCore import QEvent, QPointF, Qt
        from PySide6.QtGui import QMouseEvent
        w = self.w
        w.canvas.poly_sides = 6
        w.set_tool('polygon')
        t = w.canvas.tool_obj
        ev = QMouseEvent(QEvent.Type.MouseMove, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton,
                         Qt.MouseButton.LeftButton, mods)
        t.press(QPointF(0, 0), a, ev)
        t.move(QPointF(0, 0), b, ev)
        t.release(QPointF(0, 0), b, ev)
        w.set_tool('select')
        return [s.p0 for s in w.canvas.doc.active_layer.items[-1].path.contours[0].segments]

    def test_vertex_or_side(self):
        from PySide6.QtCore import Qt
        K = Qt.KeyboardModifier
        self.w.canvas.doc.active_layer.items = []
        v = self.drag((0, 0), (10, 0), K.NoModifier)                     # inscrit : un sommet au pointeur
        self.assertTrue(any(math.dist(p, (10, 0)) < 1e-6 for p in v))
        v = self.drag((0, 0), (10, 0), K.AltModifier)                    # Alt : le milieu d'un côté au pointeur
        self.assertFalse(any(math.dist(p, (10, 0)) < 1e-3 for p in v))
        self.assertTrue(all(abs(math.hypot(*p) - 10 / math.cos(math.pi / 6)) < 1e-6 for p in v))
        mids = [((v[i][0] + v[i - 1][0]) / 2, (v[i][1] + v[i - 1][1]) / 2) for i in range(6)]
        self.assertTrue(any(math.dist(m, (10, 0)) < 1e-6 for m in mids))
        v = self.drag((0, 0), (0, -7), K.AltModifier | K.ControlModifier)     # Ctrl + Alt : côté en haut
        self.assertTrue(any(abs(p[1] - 7) < 1e-6 for p in v) and max(p[1] for p in v) < 7 + 1e-6)
        self.assertTrue(self.w.A['tool_polygon'].toolTip())


if __name__ == '__main__':
    unittest.main()
