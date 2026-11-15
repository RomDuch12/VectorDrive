"""Round 19 : redimensionner et tourner à la souris (poignées)."""
import math
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom
from vectordrive.core.document import Shape
from vectordrive.core.geom import Path


class TestMatrices(unittest.TestCase):
    def setUp(self):
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from vectordrive.ui.canvas import Canvas
        self.C = Canvas
        self.bb = (0, 0, 20, 10)

    def test_corner_proportional(self):
        m = self.C.scale_matrix(self.bb, 4, (40, -10))           # bas-droite tiré vers (40, -10)
        x0, y0 = m.apply((0, 0))
        x1, y1 = m.apply((20, 10))
        self.assertAlmostEqual(abs(x1 - x0) / abs(y1 - y0), 2.0, places=9)   # proportions gardées
        self.assertEqual(m.apply((0, 10)), (0.0, 10.0))           # coin opposé fixe

    def test_corner_free_and_side(self):
        m = self.C.scale_matrix(self.bb, 4, (40, -10), free=True)
        self.assertEqual((m.apply((20, 0))), (40.0, -10.0))
        m = self.C.scale_matrix(self.bb, 3, (30, 99))              # côté droit : X seulement
        self.assertEqual(m.apply((20, 10)), (30.0, 10.0))
        m = self.C.scale_matrix(self.bb, 3, (30, 0), centered=True)
        self.assertEqual(m.apply((10, 5)), (10.0, 5.0))            # centre fixe

    def test_rotation(self):
        m, a = self.C.rotation_matrix(self.bb, (20, 5), (10, 15))   # du côté droit vers le haut
        self.assertAlmostEqual(a, 90, places=9)
        m, a = self.C.rotation_matrix(self.bb, (20, 5), (19, 8), step=15)
        self.assertEqual(a % 15, 0)


class TestMouse(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def ev(self, kind, pos, button=None, buttons=None, mods=None):
        from PySide6.QtCore import QEvent, QPointF, Qt
        from PySide6.QtGui import QMouseEvent
        b = button if button is not None else Qt.MouseButton.LeftButton
        return QMouseEvent(kind, QPointF(pos), QPointF(pos), b, buttons if buttons is not None else b,
                           mods if mods is not None else Qt.KeyboardModifier.NoModifier)

    def drag(self, c, a, b):
        from PySide6.QtCore import QEvent, Qt
        c.mousePressEvent(self.ev(QEvent.Type.MouseButtonPress, a))
        c.mouseMoveEvent(self.ev(QEvent.Type.MouseMove, b, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton))
        c.mouseReleaseEvent(self.ev(QEvent.Type.MouseButtonRelease, b))

    def test_scale_then_rotate(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.resize(1000, 700)
            w.show()
            self.app.processEvents()
            c = w.canvas
            sh = c.doc.add(Shape(path=Path([geom.rect(0, 0, 20, 10)])))
            c.fit((-30, -30, 60, 40))
            c.select([sh])
            br = c.to_screen(20, 0)                                  # poignée bas-droite
            self.drag(c, br, c.to_screen(40, -10))
            bb = c.selection_bbox()
            self.assertAlmostEqual(bb[2] - bb[0], 40, delta=0.5)
            self.assertAlmostEqual(bb[3] - bb[1], 20, delta=0.5)     # proportionnel
            # second clic sur l'objet : mode rotation
            inside = c.to_screen(bb[0] + (bb[2] - bb[0]) * 0.25, bb[1])   # sur le trait, hors poignée
            from PySide6.QtCore import QEvent
            c.mousePressEvent(self.ev(QEvent.Type.MouseButtonPress, inside))
            c.mouseReleaseEvent(self.ev(QEvent.Type.MouseButtonRelease, inside))
            self.assertTrue(c.rot_mode)
            bb = c.selection_bbox()
            cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
            tr_ = c.to_screen(bb[2], bb[3])                          # coin haut-droite
            # le faire tourner de 90° autour du centre
            vx, vy = bb[2] - cx, bb[3] - cy
            self.drag(c, tr_, c.to_screen(cx - vy, cy + vx))
            bb2 = c.selection_bbox()
            self.assertAlmostEqual(bb2[2] - bb2[0], bb[3] - bb[1], delta=0.5)
            self.assertAlmostEqual(bb2[3] - bb2[1], bb[2] - bb[0], delta=0.5)
            self.assertTrue(c.rot_mode)                              # reste en mode rotation
            c.select([])
            self.assertFalse(c.rot_mode)
            w.undo()
            w.undo()
            self.assertAlmostEqual(c.doc.layers[0].items[0].bbox()[2], 20, places=9)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
