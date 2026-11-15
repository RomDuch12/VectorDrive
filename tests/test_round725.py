"""Round 725 : bac en tôle (fond dans un contour convexe, bords tombés à
90° sur chaque côté, coins ouverts) et son développé en croix, d'après
SolidCraft."""
import math
import os
import tempfile
import unittest

import numpy as np

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import solids as SO
from vectordrive.core.geom import Path, polyline, rect


def _area(ring):
    x, y = ring[:, 0], ring[:, 1]
    return 0.5 * float((x * np.roll(y, -1) - np.roll(x, -1) * y).sum())


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestTray(unittest.TestCase):
    def test_tray(self):
        t, h, r = 1.5, 20.0, 1.5
        s = SO.tray(rect(0, 0, 100, 60), t, h, r)
        self.assertEqual(s.bounds(), (0.0, 0.0, 0.0, 100.0, 60.0, 20.0))         # le contour à l'extérieur des bords
        exp = 94 * 54 * t + 2 * (94 + 54) * (math.pi / 4 * ((r + t) ** 2 - r ** 2) + t * (h - t - r))
        self.assertAlmostEqual(s.volume(), exp, delta=exp * 0.002)
        self.assertEqual(len(SO.components(s)), 1)
        cw = SO.tray(polyline([(0, 0), (0, 60), (100, 60), (100, 0)], closed=True), t, h, r, z=4.0)   # sens indirect
        self.assertAlmostEqual(cw.volume(), s.volume(), delta=1e-6)
        self.assertEqual(cw.bounds()[2], 4.0)
        hexa = polyline([(40 * math.cos(math.radians(a)), 40 * math.sin(math.radians(a))) for a in range(0, 360, 60)],
                        closed=True)
        self.assertEqual(len(SO.components(SO.tray(hexa, 1, 15, 1))), 1)

    def test_flat(self):
        t, h, r = 1.5, 20.0, 1.5
        ring, axes = SO.tray_flat(rect(0, 0, 100, 60), t, h, r, 0.44)
        ba = math.pi / 2 * (r + 0.44 * t)
        ext = ba + h - r - t
        self.assertAlmostEqual(_area(ring), 94 * 54 + 2 * (94 + 54) * ext)       # croix : coins ouverts
        self.assertEqual(len(ring), 12)
        self.assertAlmostEqual(float(ring[:, 0].min()), 3 - ext)
        self.assertEqual(len(axes), 4)
        (a, b) = axes[0]                                                          # côté bas : axe à ba/2 sous le fond
        self.assertAlmostEqual(a[1], 3 - ba / 2)
        self.assertAlmostEqual(b[0] - a[0], 94.0)
        s = SO.tray(rect(0, 0, 100, 60), t, h, r)
        k5, _ = SO.tray_flat(rect(0, 0, 100, 60), t, h, r, 0.5)                   # fibre moyenne : volume / épaisseur
        self.assertAlmostEqual(_area(k5), s.volume() / t, delta=_area(k5) * 0.002)

    def test_errors(self):
        for c, kw in ((polyline([(0, 0), (50, 0), (25, 10), (50, 40), (0, 40)], closed=True), {}),   # concave
                      (rect(0, 0, 3, 3), {}),                                                       # trop petit
                      (polyline([(0, 0), (10, 0), (10, 10)]), {}),                                  # ouvert
                      (rect(0, 0, 50, 50), {'height': 2.0}),
                      (rect(0, 0, 50, 50), {'thickness': 0.0})):
            with self.assertRaises(SO.SolidError):
                SO.tray(c, kw.get('thickness', 1.0), kw.get('height', 10.0), 1.0)
        with self.assertRaises(SO.SolidError):
            SO.tray_flat(rect(0, 0, 50, 50), 1, 10, 1, -0.1)


@unittest.skipUnless(SO.available(), 'manifold3d absent')
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
        shape = Shape(path=Path([rect(0, 0, 100, 60)]))
        c.doc.add(shape)
        c.select([shape])
        new = w.solid_tray({'thickness': 1.5, 'height': 20.0, 'radius': 1.5, 'k_factor': 0.44, 'z': 0.0,
                            'flat': True, 'delete': False})
        self.assertEqual(len(new), 3)                                             # bac, flan, axes de pli
        self.assertEqual(SO.of_item(new[0]).bounds()[3:], (100.0, 60.0, 20.0))
        x0, y0, x1, y1 = new[1].path.bbox()
        self.assertAlmostEqual(x0, 120.0)                                         # à droite du contour
        self.assertEqual(len(new[2].path.contours), 4)
        self.assertIn(shape, c.doc.active_layer.items)
        c.select([])
        self.assertEqual(w.solid_tray({}), [])

    def test_ribbon_icon(self):
        from vectordrive.ui import icons
        self.assertIn('sheet_tray', icons.ICONS)
        self.assertFalse(self.w.A['solid_tray'].icon().isNull())
        self.assertTrue(self.w.A['solid_tray'].toolTip())


if __name__ == '__main__':
    unittest.main()
