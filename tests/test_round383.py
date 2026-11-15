"""Round 383 : sélection cyclique (DAO : SELECTIONCYCLING) — Alt+clic
choisit tour à tour les objets superposés sous le curseur."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


def alt_click(c, x, y):
    p = c.to_screen(x, y)
    e = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(p), QPointF(p), Qt.MouseButton.LeftButton,
                    Qt.MouseButton.LeftButton, Qt.KeyboardModifier.AltModifier)
    c.mousePressEvent(e)
    c.mouseReleaseEvent(QMouseEvent(QEvent.Type.MouseButtonRelease, QPointF(p), QPointF(p), Qt.MouseButton.LeftButton,
                                    Qt.MouseButton.NoButton, Qt.KeyboardModifier.AltModifier))


class TestCycling(unittest.TestCase):
    def test_cycle(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            shapes = [Shape(path=geom.Path([geom.rect(0, 0, 10, 10)])) for _ in range(3)]   # trois carrés superposés
            for s in shapes:
                c.doc.add(s)
            self.assertEqual(len(c.pick_all(c.to_screen(10, 5))), 3)
            self.assertIs(c.pick(c.to_screen(10, 5)), shapes[2])                # le plus haut
            seen = []
            for _ in range(4):
                alt_click(c, 10, 5)
                seen.append(c.selection[0])
            self.assertEqual(seen, [shapes[2], shapes[1], shapes[0], shapes[2]])   # tour à tour, puis on reboucle
            self.assertEqual(c.pick_all(c.to_screen(50, 50)), [])
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
