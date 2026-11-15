"""Round 703 : Cercle tangent (d'après CADCraft) — rayon donné tangent à
deux traits droits, cercles ou arcs, ou tangent à trois objets ; la solution
retenue touche les objets au plus près des clics. Icône « texte sur courbe »
qui manquait."""
import math
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import geom
from vectordrive.core import tancircle as TC
from vectordrive.core.geom import Contour, Cubic, Line

X = ('line', (0.0, 0.0), (1.0, 0.0))
Y = ('line', (0.0, 0.0), (0.0, 1.0))


def tangent(obj, c, r):
    if obj[0] == 'line':
        a, b = obj[1], obj[2]
        L = math.dist(a, b)
        return abs(abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) / L - r) < 1e-6
    d = math.dist(c, obj[1])
    return abs(d - (obj[2] + r)) < 1e-6 or abs(d - abs(obj[2] - r)) < 1e-6


class TestTTR(unittest.TestCase):
    def test_corner_quadrant_from_picks(self):
        c, r = TC.ttr(X, (5, 0), Y, (0, 5), 5.0)
        self.assertEqual((round(c[0], 9), round(c[1], 9), r), (5.0, 5.0, 5.0))
        c, _r = TC.ttr(X, (-5, 0), Y, (0, 5), 5.0)
        self.assertAlmostEqual(c[0], -5.0)                                       # l'autre quart, d'après les clics
        c, _r = TC.ttr(X, (5, 0), Y, (0, -5), 5.0)
        self.assertAlmostEqual(c[1], -5.0)

    def test_line_and_circle(self):
        ci = ('circle', (20.0, 10.0), 5.0)
        c, r = TC.ttr(X, (12, 0), ci, (16, 7), 4.0)
        self.assertTrue(tangent(X, c, r) and tangent(ci, c, r))
        self.assertLess(c[0], 20)                                                # du côté cliqué
        two = ('circle', (0.0, 0.0), 3.0), ('circle', (10.0, 0.0), 3.0)
        c, r = TC.ttr(two[0], (0, 3), two[1], (10, 3), 4.0)
        self.assertTrue(all(tangent(o, c, r) for o in two))
        self.assertGreater(c[1], 0)

    def test_impossible(self):
        far = ('line', (0.0, 20.0), (1.0, 20.0))
        self.assertIsNone(TC.ttr(X, (0, 0), far, (0, 20), 5.0))                  # parallèles trop écartées
        self.assertIsNone(TC.ttr(X, (0, 0), Y, (0, 0), 0.0))
        self.assertIsNone(TC.ttr(X, (0, 0), Y, (0, 0), float('nan')))


class TestTTT(unittest.TestCase):
    def test_incircle(self):
        hyp = ('line', (30.0, 0.0), (0.0, 40.0))
        c, r = TC.ttt([(X, (10, 0)), (Y, (0, 10)), (hyp, (18, 16))])
        self.assertAlmostEqual(c[0], 10.0, places=6)
        self.assertAlmostEqual(c[1], 10.0, places=6)
        self.assertAlmostEqual(r, 10.0, places=6)

    def test_three_circles(self):
        cs = [('circle', (0.0, 0.0), 1.0), ('circle', (10.0, 0.0), 1.0), ('circle', (5.0, 8.0), 1.0)]
        got = TC.ttt([(cs[0], (1, 0.5)), (cs[1], (9, 0.5)), (cs[2], (5, 7))])
        self.assertIsNotNone(got)
        self.assertTrue(all(tangent(o, *got) for o in cs))
        self.assertLess(math.dist(got[0], (5, 3)), 2)                            # celui du milieu

    def test_parallel_lines(self):
        top = ('line', (0.0, 10.0), (1.0, 10.0))
        c, r = TC.ttt([(X, (5, 0)), (top, (5, 10)), (Y, (0, 5))])
        self.assertEqual((round(c[0], 6), round(c[1], 6), round(r, 6)), (5.0, 5.0, 5.0))


class TestPick(unittest.TestCase):
    def test_objects_of_drawing(self):
        sq = geom.Path([geom.rect(0, 0, 20, 10)])
        o = TC.pick(sq, (7, 0.3))
        self.assertEqual(o[0], 'line')
        self.assertEqual({o[1][1], o[2][1]}, {0.0})
        o = TC.pick(geom.Path([geom.circle((3, 4), 6)]), (9.1, 4))
        self.assertEqual(o[0], 'circle')
        self.assertAlmostEqual(o[2], 6.0)
        self.assertAlmostEqual(o[1][0], 3.0)
        self.assertIsNone(TC.pick(geom.Path([Contour([Cubic((0, 0), (1, 5), (4, 5), (5, 0))], False)]), (2, 3)))
        self.assertIsNone(TC.object_of(Line((1, 1), (1, 1))))


class Ev:
    def modifiers(self):
        from PySide6.QtCore import Qt
        return Qt.KeyboardModifier.NoModifier


class TestTool(unittest.TestCase):
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

    def lines(self):
        from vectordrive.core.document import Shape
        c = self.w.canvas
        a = Shape(path=geom.Path([Contour([Line((0, 0), (60, 0))], False)]))
        b = Shape(path=geom.Path([Contour([Line((0, 0), (0, 60))], False)]))
        c.doc.add(a)
        c.doc.add(b)
        return a, b

    def click(self, x, y):
        self.w.canvas.tool_obj.press(self.w.canvas.to_screen(x, y), (x, y), Ev())

    def test_two_lines_and_radius(self):
        from PySide6.QtWidgets import QInputDialog
        self.lines()
        with mock.patch.object(QInputDialog, 'getDouble', return_value=(8.0, True)):
            self.w.set_tool('tan_circle')
        self.assertAlmostEqual(self.w.canvas.tan_circle_radius, 8.0)
        n = len(list(self.w.canvas.doc.iter_leaves()))
        self.click(10, 0)
        tool = self.w.canvas.tool_obj
        tool.move(self.w.canvas.to_screen(0, 12), (0, 12), Ev())
        self.assertIsNotNone(tool.ghost)                                         # aperçu au survol
        self.click(0, 12)
        leaves = list(self.w.canvas.doc.iter_leaves())
        self.assertEqual(len(leaves), n + 1)
        bb = leaves[-1].path.bbox()
        self.assertEqual([round(v, 6) for v in bb], [0.0, 0.0, 16.0, 16.0])
        self.w.undo()
        self.assertEqual(len(list(self.w.canvas.doc.iter_leaves())), n)

    def test_three_objects_and_cancel(self):
        from PySide6.QtWidgets import QInputDialog
        from vectordrive.core.document import Shape
        self.lines()
        self.w.canvas.doc.add(Shape(path=geom.Path([Contour([Line((30, 0), (0, 40))], False)])))
        with mock.patch.object(QInputDialog, 'getDouble', return_value=(0.0, True)):
            self.w.set_tool('tan_circle')
        n = len(list(self.w.canvas.doc.iter_leaves()))
        for x, y in ((10, 0), (0, 10), (18, 16)):
            self.click(x, y)
        got = list(self.w.canvas.doc.iter_leaves())[-1].path.bbox()
        self.assertEqual(len(list(self.w.canvas.doc.iter_leaves())), n + 1)
        self.assertEqual([round(v, 5) for v in got], [0.0, 0.0, 20.0, 20.0])  # cercle inscrit
        with mock.patch.object(QInputDialog, 'getDouble', return_value=(0.0, False)):
            self.w.set_tool('tan_circle')
        self.assertEqual(self.w.canvas.tool, 'select')                          # rayon abandonné

    def test_icons_and_ribbon(self):
        from vectordrive.ui import icons
        for k in ('tan_circle', 'text_path'):
            self.assertIn(k, icons.ICONS)
        self.assertFalse(self.w.A['tool_tan_circle'].icon().isNull())
        self.assertIn('tool_tan_circle', self.w.PALETTES['palette_shapes'][1])


if __name__ == '__main__':
    unittest.main()
