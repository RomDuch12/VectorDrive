"""Round 278 : SculptArt — pinceaux (ajouter, creuser, lisser, aplanir,
bruit) sur un relief, à la souris, annulables."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core import galbe as GB, sculpt as SC

app = QApplication.instance() or QApplication([])


class TestBrushes(unittest.TestCase):
    def test_dabs(self):
        H = np.zeros((100, 100))
        self.assertTrue(SC.dab(H, 0, 10, 0.1, 5, 5, 1.0, 0.5, 'ajouter'))
        self.assertAlmostEqual(float(H.max()), 0.5, 1)
        self.assertEqual(float(H[0, 0]), 0.0)                                    # hors du pinceau
        SC.dab(H, 0, 10, 0.1, 5, 5, 1.0, 0.5, 'creuser')
        self.assertAlmostEqual(float(np.abs(H).max()), 0.0, 6)
        H[40:60, 40:60] = 1.0
        before = float(np.abs(np.diff(H[50, 35:45])).max())
        for _ in range(5):
            SC.dab(H, 0, 10, 0.1, 4.0, 5.0, 1.0, 0, 'lisser')
        self.assertLess(float(np.abs(np.diff(H[50, 35:45])).max()), before)    # bord gauche adouci
        self.assertFalse(SC.dab(H, 0, 10, 0.1, 50, 50, 1.0, 0.5, 'ajouter'))    # hors de la carte
        n = SC.stroke(np.zeros((100, 100)), 0, 10, 0.1, (1, 5), (9, 5), 1.0, 0.1, 'bruit')
        self.assertGreaterEqual(n, 20)
        F = np.zeros((100, 100))
        F[:, 50:] = 2.0
        SC.dab(F, 0, 10, 0.1, 5.0, 5.0, 2.0, 0, 'aplanir')
        self.assertGreater(float(F[50, 48]), 0.5)                                # ramené vers la hauteur du centre (2)


class TestTool(unittest.TestCase):
    def test_paint_and_undo(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            img = GB.encode(np.zeros((100, 100)), 0.0, 10.0, 0.1, GB.GalbeSpec())
            c.doc.add(img)
            c.select([img])
            w.sculpt_dialog({'brush': 'ajouter', 'radius': 1.0, 'strength': 0.4})
            self.assertEqual(c.tool, 'sculpt')
            t = c.tool_obj
            ev = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton,
                             Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            t.press(c.to_screen(5, 5), (5.0, 5.0), ev)
            t.move(c.to_screen(7, 5), (7.0, 5.0), ev)
            t.release(c.to_screen(7, 5), (7.0, 5.0), ev)
            new = c.doc.layers[0].items[0]
            self.assertIsNot(new, img)
            H, *_ = GB.decode(new)
            self.assertGreater(float(H.max()), 0.3)
            w.undo()
            self.assertIs(c.doc.layers[0].items[0].data, img.data)                 # un coup = une annulation
            self.assertFalse(w.grab().isNull())
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
