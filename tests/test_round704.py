"""Round 704 : Mesurer un rayon (cercle, arc entier même en plusieurs
morceaux, rayon de courbure d'une courbe, trait droit) et Mesurer un angle
(deux traits droits, côté cliqué ; ou sommet et deux points) — comme
MESUREGEOM en DAO."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import geom
from vectordrive.core import measuregeom as MG
from vectordrive.core.geom import Contour, Cubic, Line, Path


class TestRadius(unittest.TestCase):
    def test_circle_and_arcs(self):
        info = MG.radius_info(Path([geom.circle((3, 4), 6)]), (9.2, 4))
        self.assertEqual(info['kind'], 'circle')
        self.assertAlmostEqual(info['r'], 6.0)
        self.assertAlmostEqual(info['center'][1], 4.0)
        arc = MG.radius_info(Path([geom.arc((0, 0), 10, 0, 120)]), (10, 0.5))
        self.assertEqual(arc['kind'], 'arc')
        self.assertAlmostEqual(arc['sweep'], 120.0, places=6)                    # l'arc entier, pas un morceau
        self.assertAlmostEqual(arc['length'], 10 * math.radians(120), places=6)
        corner = MG.radius_info(Path([geom.rect(0, 0, 20, 10, r=3)]), (19.5, 9.5))
        self.assertEqual((corner['kind'], round(corner['r'], 6), round(corner['sweep'], 6)), ('arc', 3.0, 90.0))

    def test_line_and_curves(self):
        side = MG.radius_info(Path([geom.rect(0, 0, 20, 10, r=3)]), (20.2, 5))
        self.assertEqual((side['kind'], side['length'], side['angle']), ('line', 4.0, 90.0))
        cu = Cubic((0, 0), (0, 5), (5, 10), (10, 10))
        got = MG.radius_info(Path([Contour([cu], False)]), (2, 6))
        self.assertEqual(got['kind'], 'curve')
        p, c = got['point'], got['center']
        self.assertAlmostEqual(math.dist(p, c), got['r'], places=6)
        q = Cubic((0, 0), (10, 0), (20, 0), (30, 0))                             # courbe droite
        self.assertEqual(MG.radius_info(Path([Contour([q], False)]), (15, 1))['kind'], 'flat')
        self.assertIsNone(MG.radius_info(Path(), (0, 0)))

    def test_curvature_of_exact_circle(self):
        k = MG.curvature(geom.arc((0, 0), 7, 10, 60).segments[0], 0.5)
        self.assertAlmostEqual(k[0], 7.0, places=4)
        self.assertLess(math.dist(k[1], (0, 0)), 1e-3)


class TestAngle(unittest.TestCase):
    def test_lines_side_of_clicks(self):
        x, d = ((0, 0), (10, 0)), ((0, 0), (10, 10))
        self.assertAlmostEqual(MG.lines_angle(x, d, (5, 0), (5, 5))['angle'], 45.0)
        self.assertAlmostEqual(MG.lines_angle(x, d, (-5, 0), (5, 5))['angle'], 135.0)  # prolongé : l'autre secteur
        far = MG.lines_angle(((0, 0), (10, 0)), ((20, 5), (30, 15)))
        self.assertEqual(tuple(round(v, 9) for v in far['vertex']), (15.0, 0.0))  # droites prolongées
        par = MG.lines_angle(x, ((0, 3), (10, 3)))
        self.assertEqual((par['angle'], par['vertex'], par['gap']), (0.0, None, 3.0))

    def test_three_points(self):
        self.assertAlmostEqual(MG.angle_3points((0, 0), (1, 0), (0, 1)), 90.0)
        self.assertAlmostEqual(MG.angle_3points((0, 0), (1, 0), (-1, -0.0001)), 179.99427, places=4)
        self.assertIsNone(MG.angle_3points((0, 0), (0, 0), (1, 1)))
        self.assertEqual(MG.line_at(Path([geom.circle((0, 0), 5)]), (5, 0), 1.0), None)


class Ev:
    def modifiers(self):
        from PySide6.QtCore import Qt
        return Qt.KeyboardModifier.NoModifier


class TestTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.msgs = []
        cls.w.canvas.measured.connect(cls.msgs.append)

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def click(self, x, y):
        self.w.canvas.tool_obj.press(self.w.canvas.to_screen(x, y), (x, y), Ev())

    def paint(self):
        from PySide6.QtGui import QImage, QPainter
        img = QImage(400, 300, QImage.Format.Format_ARGB32)
        p = QPainter(img)
        self.w.canvas.tool_obj.paint(p)                                          # aperçu sans erreur
        p.end()

    def test_radius_tool(self):
        from vectordrive.core.document import Group, Shape
        self.w.canvas.doc.add(Group(children=[Shape(path=Path([geom.circle((50, 50), 12.5)]))]))
        self.w.set_tool('measure_radius')
        self.click(62.5, 50)
        self.assertIn('Ø 25.000', self.msgs[-1])                                 # dans un groupe aussi
        self.paint()
        self.click(500, 500)
        self.assertIsNone(self.w.canvas.tool_obj.info)

    def test_angle_tool_lines_and_points(self):
        from vectordrive.core.document import Shape
        c = self.w.canvas
        c.doc.add(Shape(path=Path([Contour([Line((100, 0), (160, 0))], False)])))
        c.doc.add(Shape(path=Path([Contour([Line((100, 0), (130, 30))], False)])))
        self.w.set_tool('measure_angle')
        self.click(140, 0)
        self.click(120, 20)
        self.assertIn('Angle 45.00°', self.msgs[-1])
        self.paint()
        for x, y in ((200, 200), (210, 200), (200, 230)):                       # sommet puis deux points
            self.click(x, y)
        self.assertIn('Angle 90.00°', self.msgs[-1])
        self.paint()

    def test_ribbon_and_icons(self):
        from vectordrive.ui import icons
        for k in ('measure_radius', 'measure_angle'):
            self.assertIn(k, icons.ICONS)
            self.assertFalse(self.w.A[f'tool_{k}'].icon().isNull())
            self.assertTrue(self.w.A[f'tool_{k}'].toolTip())


if __name__ == '__main__':
    unittest.main()
