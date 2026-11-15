"""Round 307 : SculptArt — Miroir (TypeEdit) : le geste reproduit autour du
centre du relief, par un axe horizontal, vertical, deux axes ou n axes."""
import math
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


class TestMaps(unittest.TestCase):
    def test_maps(self):
        c = (0.0, 0.0)
        pts = {tuple(round(v, 9) for v in SC.mirrored((3, 1), c, m)) for m in SC.mirror_maps('deux')}
        self.assertEqual(pts, {(3, 1), (3, -1), (-3, 1), (-3, -1)})
        self.assertEqual(SC.mirrored((3, 1), (1, 1), SC.mirror_maps('v')[1]), (-1, 1))
        m5 = SC.mirror_maps('multi', 5)
        self.assertEqual(len(m5), 10)
        for a, b, cc, d in m5:                                        # isométries
            self.assertAlmostEqual(abs(a * d - b * cc), 1.0)
        img = {tuple(round(v, 6) + 0.0 for v in SC.mirrored((1, 0), c, m)) for m in m5}
        self.assertEqual(len(img), 5)                                 # 5 axes : 5 copies d'un point de l'axe
        self.assertNotIn((-1.0, 0.0), img)                            # pas de reflet par un axe vertical
        self.assertEqual(len({tuple(round(v, 6) for v in SC.mirrored((0.3, 0.7), c, m)) for m in m5}), 10)
        self.assertEqual(len(SC.mirror_maps('aucun')), 1)
        self.assertEqual(len(SC.mirror_maps('multi', 40)), 20)        # au plus 10 axes


class TestTool(unittest.TestCase):
    def test_paint_mirrored(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            img = GB.encode(np.zeros((100, 100)), 0.0, 10.0, 0.1, GB.GalbeSpec())
            c.doc.add(img)
            c.select([img])
            w.sculpt_dialog({'brush': 'ajouter', 'radius': 0.8, 'strength': 0.5, 'mirror': 'deux', 'mirror_axes': 4})
            t = c.tool_obj
            ev = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton,
                             Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            t.press(c.to_screen(2, 2), (2.0, 2.0), ev)
            t.release(c.to_screen(2, 2), (2.0, 2.0), ev)
            H, x0, y1, res = GB.decode(c.doc.layers[0].items[0])

            def at(x, y):
                return float(H[int((y1 - y) / res), int((x - x0) / res)])
            for x, y in ((2, 2), (8, 2), (2, 8), (8, 8)):                # les quatre coins, autour du centre (5, 5)
                self.assertGreater(at(x, y), 0.3, (x, y))
            self.assertLess(at(5, 5), 0.01)
            w.sculpt_dialog({'brush': 'ajouter', 'radius': 1.0, 'strength': 0.4, 'mirror': 'aucun'})
            self.assertEqual(c.sculpt_params['mirror'], 'aucun')
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
