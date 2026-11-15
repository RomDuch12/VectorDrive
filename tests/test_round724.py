"""Round 724 : tôle pliée (CONTOUR FLANGE) le long d'une chaîne de traits
droits, plis au rayon intérieur, et son développé au facteur K, d'après
SolidCraft."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import solids as SO
from vectordrive.core.geom import Contour, Path, arc, polyline

L = polyline([(0, 0), (100, 0), (100, 50)])                                       # équerre, pli à gauche


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestSheet(unittest.TestCase):
    def test_flat(self):
        ln, bends = SO.sheet_flat(L, 2, 2, 0.44)                                  # chaîne = face extérieure
        ba = math.pi / 2 * (2 + 0.44 * 2)
        self.assertAlmostEqual(ln, 96 + 46 + ba)                                  # plats + zone du pli
        (x, angle, a, b), = bends
        self.assertEqual((a, angle), (96.0, 90.0))
        self.assertAlmostEqual(b - a, ba)
        self.assertAlmostEqual(x, 96 + ba / 2)
        ln, bends = SO.sheet_flat(L, 2, 2, 0.44, left=False)                      # chaîne = face intérieure
        self.assertAlmostEqual(ln, 98 + 48 + ba)
        self.assertEqual(bends[0][1], -90.0)
        z = polyline([(0, 0), (30, 0), (50, 20), (80, 20)])
        self.assertEqual([round(b[1]) for b in SO.sheet_flat(z, 1, 1)[1]], [45, -45])
        self.assertEqual(SO.sheet_flat(polyline([(0, 0), (40, 0), (90, 0)]), 1, 1)[1], [])   # sommet aligné

    def test_solid(self):
        for left, box in ((True, (0.0, 0.0, 0.0, 100.0, 50.0, 30.0)), (False, (0.0, -2.0, 0.0, 102.0, 50.0, 30.0))):
            s = SO.sheet(L, 2, 30, 2, left)
            self.assertEqual(tuple(round(v, 6) for v in s.bounds()), box)
            self.assertAlmostEqual(s.volume() / 60, SO.sheet_flat(L, 2, 2, 0.5, left)[0], delta=0.05)  # fibre moyenne
            self.assertEqual(len(SO.components(s)), 1)
        u = SO.sheet(polyline([(0, 40), (0, 0), (60, 0), (60, 40)]), 1.5, 20, 0.0, False, z=5.0)
        self.assertEqual(tuple(round(v, 6) for v in u.bounds()), (-1.5, -1.5, 5.0, 61.5, 40.0, 25.0))

    def test_errors(self):
        for c, kw in ((polyline([(0, 0), (10, 0), (10, 10)], closed=True), {}),
                      (Contour(arc((0, 0), 10, 0, 90).segments), {}),
                      (polyline([(0, 0), (3, 0), (3, 30)]), {'radius': 5.0}),          # trait trop court
                      (polyline([(0, 0), (30, 0), (0, 0.0001)]), {}),                 # rabattu à 180°
                      (L, {'thickness': 0.0})):
            with self.assertRaises(SO.SolidError):
                SO.sheet(c, kw.get('thickness', 1.0), 10, kw.get('radius', 1.0))
        with self.assertRaises(SO.SolidError):
            SO.sheet_flat(L, 1, 1, 1.5)
        with self.assertRaises(SO.SolidError):
            SO.sheet(L, 1, 0, 1)


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
        line = Shape(path=Path([polyline([(0, 0), (100, 0), (100, 50)])]))
        c.doc.add(line)
        c.select([line])
        new = w.solid_sheet({'thickness': 2.0, 'height': 30.0, 'radius': 2.0, 'k_factor': 0.44, 'side': 'gauche',
                             'z': 0.0, 'flat': True, 'delete': True})
        self.assertEqual(len(new), 3)                                             # tôle, flan, axes de pli
        self.assertEqual(SO.of_item(new[0]).bounds()[3:], (100.0, 50.0, 30.0))
        blank, axes = new[1], new[2]
        x0, y0, x1, y1 = blank.path.bbox()
        self.assertAlmostEqual(x1 - x0, 96 + 46 + math.pi / 2 * 2.88, places=6)
        self.assertEqual((y1 - y0, y1), (30.0, -10.0))                            # sous le trait
        self.assertEqual(len(axes.path.contours), 1)
        self.assertNotIn(line, c.doc.active_layer.items)
        self.assertIn('mm', w.statusBar().currentMessage())
        c.select([])
        self.assertEqual(w.solid_sheet({}), [])

    def test_ribbon_icon(self):
        from vectordrive.ui import icons
        self.assertIn('bent_sheet', icons.ICONS)
        self.assertFalse(self.w.A['solid_sheet'].icon().isNull())
        self.assertTrue(self.w.A['solid_sheet'].toolTip())


if __name__ == '__main__':
    unittest.main()
