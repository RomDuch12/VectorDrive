"""Round 709 : Festons (comme REVCLOUD en DAO, d'après CADCraft) — arcs
réguliers calés sur les coins, bombés vers l'extérieur ou l'intérieur, sens
des contours gardé ; commande des Déformations."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import distort as D
from vectordrive.core import geom
from vectordrive.core.geom import Contour, Line, Path


def ends(c):
    return {(round(s.end[0], 6), round(s.end[1], 6)) for s in c.segments}


class TestScallop(unittest.TestCase):
    def test_rectangle_corners_and_outward(self):
        c = D.scallop(Path([geom.rect(0, 0, 40, 20)]), 5.0).contours[0]
        self.assertTrue(c.closed)
        for corner in ((0, 0), (40, 0), (40, 20), (0, 20)):
            self.assertIn(corner, ends(c))                               # les festons se rejoignent aux coins
        self.assertIn((5.0, 0.0), ends(c))
        x0, y0, x1, y1 = c.bbox()
        self.assertLess(y0, -0.5)                                        # bombés vers l'extérieur
        self.assertGreater(x1, 40.5)
        self.assertAlmostEqual(y0, -5 / 2 * math.tan(math.atan(0.5)), places=3)   # flèche = c/2·tan(θ/4)
        inner = D.scallop(Path([geom.rect(0, 0, 40, 20)]), 5.0, inward=True).contours[0]
        self.assertGreater(inner.bbox()[1], -1e-6)                       # vers l'intérieur
        self.assertLess(abs(inner.signed_area()), abs(geom.rect(0, 0, 40, 20).signed_area()))

    def test_direction_kept_and_circle_uniform(self):
        cw = geom.rect(0, 0, 40, 20).reversed()
        out = D.scallop(Path([cw]), 5.0).contours[0]
        self.assertLess(out.signed_area(), 0)                            # sens horaire gardé
        self.assertLess(out.bbox()[1], -0.5)                             # toujours vers l'extérieur
        circ = D.scallop(Path([geom.circle((0, 0), 10)]), 5.0, bulge=1.0).contours[0]
        r = [math.hypot(*s.end) for s in circ.segments if math.isclose(math.hypot(*s.end), 10, abs_tol=0.002)]
        self.assertEqual(len(r), round(2 * math.pi * 10 / 5))            # 13 festons égaux sur le cercle
        far = max(math.hypot(*p) for p in circ.flatten(0.001))           # sommet d'un demi-cercle
        self.assertAlmostEqual(far, 10 * math.cos(math.pi / 13) + 10 * math.sin(math.pi / 13), delta=0.01)

    def test_open_and_degenerate(self):
        o = D.scallop(Path([Contour([Line((0, 0), (20, 0))])]), 5.0).contours[0]
        self.assertFalse(o.closed)
        self.assertEqual((o.start, o.end), ((0, 0), (20, 0)))
        self.assertLess(o.bbox()[1], 0)                                  # à droite du sens de parcours
        same = Path([geom.rect(0, 0, 4, 4)])
        self.assertIs(D.scallop(same, 0.0), same)
        tiny = D.scallop(Path([geom.rect(0, 0, 4, 4)]), 50.0).contours[0]
        self.assertEqual(len(ends(tiny) & {(0, 0), (4, 0), (4, 4), (0, 4)}), 4)   # un feston par côté au moins


class TestCommand(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def test_distort_scallop(self):
        from vectordrive.core.document import Shape
        from vectordrive.ui import icons
        c = self.w.canvas
        s = Shape(path=Path([geom.rect(0, 0, 30, 30)]), tool=2)
        c.doc.add(s)
        c.select([s])
        new = self.w.distort('scallop', {'step': 10.0, 'bulge': 1.0, 'inward': False})
        self.assertEqual(len(new), 1)
        self.assertEqual(new[0].tool, 2)
        self.assertAlmostEqual(new[0].path.bbox()[0], -5.0, places=4)    # demi-cercles de 10 mm
        self.assertIn('fx_scallop', icons.ICONS)
        self.assertFalse(self.w.A['fx_scallop'].icon().isNull())


if __name__ == '__main__':
    unittest.main()
