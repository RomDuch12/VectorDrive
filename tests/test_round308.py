"""Round 308 : SculptArt — masque (comme les masques de couleur de TypeEdit) :
les formes fermées choisies avec le relief servent de pochoir."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core import galbe as GB, geom
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


def paint(mask):
    from vectordrive.ui.main_window import MainWindow
    w = MainWindow()
    try:
        c = w.canvas
        img = GB.encode(np.zeros((100, 100)), 0.0, 10.0, 0.1, GB.GalbeSpec())
        stencil = Shape(path=geom.Path([geom.rect(0, 0, 5, 10)]))       # moitié gauche
        c.doc.add(img)
        c.doc.add(stencil)
        c.select([img, stencil])
        w.sculpt_dialog({'brush': 'ajouter', 'radius': 3.0, 'strength': 0.5, 'mask': mask})
        t = c.tool_obj
        ev = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton,
                         Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        t.press(c.to_screen(5, 5), (5.0, 5.0), ev)
        t.move(c.to_screen(5, 6), (5.0, 6.0), ev)
        t.release(c.to_screen(5, 6), (5.0, 6.0), ev)
        item = next(it for it in c.doc.layers[0].items if 'galbe' in getattr(it, 'extra', {}))
        H, x0, y1, res = GB.decode(item)
        return float(H[50, 40]), float(H[50, 60])                           # x = 4 et x = 6
    finally:
        w.set_tool('select')
        w.modified = False
        w.close()


class TestMask(unittest.TestCase):
    def test_inside(self):
        left, right = paint('dedans')
        self.assertGreater(left, 0.2)
        self.assertEqual(right, 0.0)

    def test_outside_and_none(self):
        left, right = paint('dehors')
        self.assertEqual(left, 0.0)
        self.assertGreater(right, 0.2)
        left, right = paint('aucun')
        self.assertGreater(left, 0.2)
        self.assertGreater(right, 0.2)


if __name__ == '__main__':
    unittest.main()
