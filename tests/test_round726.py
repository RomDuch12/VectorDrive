"""Round 726 : perforation — trous ronds en quinconce ou en grille carrée
dans les contours fermés choisis, à une marge des bords, des découpes et
des traits ouverts (axes de pli), d'après SolidCraft."""
import math
import os
import tempfile
import unittest

import numpy as np

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import perforate as PF
from vectordrive.core.geom import Contour, Line, Path, circle, rect

PLATE = Path([rect(0, 0, 100, 50)])


class TestPerforate(unittest.TestCase):
    def test_grids(self):
        P = PF.holes(PLATE, 3, 5, 3, align='gauche')                              # quinconce, marge 3
        self.assertEqual(len(P), 5 * 19 + 5 * 18)
        self.assertEqual(P[0].tolist(), [4.5, 4.5])                               # coin bas gauche + marge + rayon
        self.assertAlmostEqual(P[19][0], 7.0)                                     # rangée impaire : demi-pas
        self.assertAlmostEqual(P[19][1], 4.5 + 5 * math.sqrt(3) / 2)
        self.assertEqual(len(PF.holes(PLATE, 3, 5, 3, square=True, align='gauche')), 9 * 19)
        self.assertEqual(PF.holes(PLATE, 3, 5, 3, align='droite')[0].tolist(), [95.5, 4.5])
        self.assertEqual(len(PF.holes(PLATE, 3, 5, align='gauche')), len(P))       # marge par défaut : le diamètre
        C = PF.holes(PLATE, 3, 5, 3, square=True)                                 # centrée : marges égales
        self.assertEqual(len(C), 9 * 19)
        self.assertAlmostEqual(C[:, 0].min(), 100 - C[:, 0].max())
        self.assertAlmostEqual(C[:, 1].min(), 50 - C[:, 1].max())
        C = PF.holes(PLATE, 3, 5, 3)
        even = C[np.isclose(C[:, 1], C[:, 1].min())]
        self.assertAlmostEqual(even[:, 0].min(), 100 - even[:, 0].max())
        self.assertAlmostEqual(C[:, 1].min(), 50 - C[:, 1].max())

    def test_clearance(self):
        cut = Path([rect(0, 0, 100, 50), circle((50, 25), 10)])
        P = PF.holes(cut, 3, 5, 3)
        self.assertTrue(np.all(np.hypot(P[:, 0] - 50, P[:, 1] - 25) >= 10 + 4.5 - 1e-6))   # découpe libre
        axis = Contour([Line((50, 0), (50, 50))])
        P = PF.holes(PLATE, 3, 5, 3, keep_clear=[axis])
        self.assertTrue(np.all(np.abs(P[:, 0] - 50) >= 4.5 - 1e-9))               # loin de l'axe de pli
        self.assertLess(len(P), 185)
        self.assertEqual(len(PF.holes(Path([rect(0, 0, 8, 8)]), 3, 5, 3)), 0)       # trop petit : aucun

    def test_perforate_and_errors(self):
        path, n, ratio = PF.perforate(PLATE, 3, 5, 3)
        self.assertEqual((n, len(path.contours)), (185, 185))
        self.assertAlmostEqual(ratio, 185 * math.pi * 2.25 / 5000)
        self.assertAlmostEqual(PF.region_area(Path([rect(0, 0, 100, 50), rect(10, 10, 20, 20)])), 4600.0)
        for args in ((PLATE, 0, 5), (PLATE, 5, 4), (PLATE, 3, 5, -1), (Path([Contour([Line((0, 0), (9, 9))])]), 3, 5),
                     (Path([rect(0, 0, 10000, 10000)]), 1, 1.5), (PLATE, 3, 5, 3, False, (), 'haut')):
            with self.assertRaises(ValueError):
                PF.holes(*args)


class TestUi(unittest.TestCase):
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

    def test_action(self):
        from vectordrive.core.document import Shape
        w, c = self.w, self.w.canvas
        plate = Shape(path=Path([rect(0, 0, 100, 50)]))
        hole = Shape(path=Path([circle((50, 25), 10)]))                            # découpe : autre forme
        axis = Shape(path=Path([Contour([Line((20, 0), (20, 50))])]))
        for it in (plate, hole, axis):
            c.doc.add(it)
        c.select([plate, hole, axis])
        out = w.perforate_dialog({'diameter': 3.0, 'pitch': 5.0, 'margin': 3.0, 'pattern': 'quinconce',
                                  'align': 'centre'})
        self.assertEqual(len(out), 1)
        P = np.array([np.mean(ct.flatten(0.05), axis=0) for ct in out[0].path.contours])   # centres des trous
        self.assertGreater(len(P), 100)
        self.assertTrue(np.all(np.hypot(P[:, 0] - 50, P[:, 1] - 25) >= 14.5 - 0.05))
        self.assertTrue(np.all(np.abs(P[:, 0] - 20) >= 4.5 - 0.05))
        self.assertIn('ajouré', w.statusBar().currentMessage())
        x0, y0, x1, y1 = out[0].path.bbox()
        self.assertGreaterEqual(x0, 3.0 - 1e-6)
        c.select([axis])
        self.assertEqual(w.perforate_dialog({}), [])                               # pas de contour fermé

    def test_ribbon_icon(self):
        from vectordrive.ui import icons
        self.assertIn('perforate', icons.ICONS)
        self.assertFalse(self.w.A['perforate'].icon().isNull())
        self.assertTrue(self.w.A['perforate'].toolTip())


if __name__ == '__main__':
    unittest.main()
