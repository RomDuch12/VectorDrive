"""Round 391 : aperçu du reste de matière (TypeEdit : FAO › Pré-traitement)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import model as M, strategies as S
from vectordrive.core import geom
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


class TestRest(unittest.TestCase):
    def test_corners(self):
        reg = S.region([geom.Path([geom.rect(0, 0, 20, 10)])], 0.01)
        t = M.CamTool(name='F', kind='droite', diameter=4)
        rest, r = S.rest_zones(reg, t)
        self.assertEqual(r, 2.0)
        self.assertAlmostEqual(rest.area, 4 * (4 - math.pi), 1)      # quatre coins de 2 × 2 moins un quart de disque
        rest2, _ = S.rest_zones(reg, M.CamTool(name='F', kind='droite', diameter=0.0))
        self.assertTrue(rest2.is_empty)

    def test_narrow_slot(self):
        reg = S.region([geom.Path([geom.rect(0, 0, 30, 1.5)])], 0.01)  # rainure de 1,5 : Ø2 ne passe pas
        rest, _ = S.rest_zones(reg, M.CamTool(name='F', kind='droite', diameter=2))
        self.assertAlmostEqual(rest.area, 45.0, 3)

    def test_window(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            s = Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]))
            w.canvas.doc.add(s)
            w.canvas.select([s])
            g = w.rest_preview(M.CamTool(name='F4', kind='droite', diameter=4))
            self.assertEqual(len(g.children), 4)
            L = w.canvas.doc.layers[-1]
            self.assertTrue(L.extra.get('rest_preview'))
            self.assertIn(g, L.items)
            w.canvas.select([s])
            self.assertIsNone(w.rest_preview(M.CamTool(name='F0', kind='droite', diameter=0.0)))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
