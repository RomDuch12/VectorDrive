"""Round 324 : utilisation de la souris (TypeEdit F5) — molette en zoom ou en
défilement, clic droit réglable (zoom, défaire, geler), double-clic sur la
molette : tout voir."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Shape
from vectordrive.ui import shortcuts as SC

app = QApplication.instance() or QApplication([])


def wheel(c, dy, mods=Qt.KeyboardModifier.NoModifier):
    ev = QWheelEvent(QPointF(100, 100), QPointF(100, 100), QPoint(0, 0), QPoint(0, dy), Qt.MouseButton.NoButton,
                     mods, Qt.ScrollPhase.NoScrollPhase, False)
    c.wheelEvent(ev)


def right_click(c, pos=QPointF(120, 80)):
    for kind in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
        ev = QMouseEvent(kind, pos, pos, Qt.MouseButton.RightButton,
                         Qt.MouseButton.RightButton if kind == QEvent.Type.MouseButtonPress else Qt.MouseButton.NoButton,
                         Qt.KeyboardModifier.NoModifier)
        (c.mousePressEvent if kind == QEvent.Type.MouseButtonPress else c.mouseReleaseEvent)(ev)


class TestMouse(unittest.TestCase):
    def test_settings(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            w.mouse_settings({'wheel': 'defilement', 'right': 'zoom'})
            s0, oy = c.scale, c.oy
            wheel(c, 120)
            self.assertEqual(c.scale, s0)
            self.assertAlmostEqual(c.oy, oy + 40)                         # défile
            wheel(c, 120, Qt.KeyboardModifier.ControlModifier)
            self.assertGreater(c.scale, s0)                               # Ctrl : zoom
            s1 = c.scale
            right_click(c)
            self.assertAlmostEqual(c.scale, s1 * 1.5)
            sh = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]))
            w._add_items([sh])
            w.mouse_settings({'wheel': 'zoom', 'right': 'annuler'})
            right_click(c)
            self.assertEqual(sum(len(L.items) for L in c.doc.layers), 0)  # défait
            w.mouse_settings({'wheel': 'zoom', 'right': 'aucun'})
            self.assertEqual(SC.TE_ACTIONS['ID_MANIPULER_SOURIS'], 'mouse_settings')
        finally:
            w.mouse_settings({'wheel': 'zoom', 'right': 'aucun'})
            w.modified = False
            w.close()

    def test_middle_double_click(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            c.zoom_at(5.0, QPointF(10, 10))
            s = c.scale
            ev = QMouseEvent(QEvent.Type.MouseButtonDblClick, QPointF(50, 50), QPointF(50, 50),
                             Qt.MouseButton.MiddleButton, Qt.MouseButton.MiddleButton, Qt.KeyboardModifier.NoModifier)
            c.mouseDoubleClickEvent(ev)
            self.assertNotEqual(c.scale, s)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
