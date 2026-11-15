"""Round 263 : dessin technique — diviser, mesurer, allonger, repères de
centre, propriétés de masse."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import cadtools as C, geom
from vectordrive.core.document import Group, Shape

app = QApplication.instance() or QApplication([])


class TestCore(unittest.TestCase):
    def test_divide_measure(self):
        line = geom.polyline([(0, 0), (10, 0)])
        self.assertEqual([(x, y) for x, y, _a in C.divide(line, 4)], [(2.5, 0.0), (5.0, 0.0), (7.5, 0.0)])
        circle = geom.circle((0, 0), 10)
        self.assertEqual(len(C.divide(circle, 6)), 6)                            # fermé : départ compris
        pts = C.measure(circle, 10)
        self.assertEqual(len(pts), 6)                                            # 62,8 mm : 6 repères
        self.assertAlmostEqual(math.hypot(pts[0][0], pts[0][1]), 10, 2)
        self.assertEqual([x for x, _y, _a in C.measure(line, 3, from_end=True)], [7.0, 4.0, 1.0])

    def test_lengthen(self):
        line = geom.polyline([(0, 0), (10, 0)])
        self.assertAlmostEqual(C.contour_length(C.lengthen(line, 'delta', 5)), 15)
        self.assertEqual(C.lengthen(line, 'delta', 5).segments[-1].end, (15.0, 0.0))
        short = C.lengthen(line, 'total', 4, 'debut')
        self.assertAlmostEqual(short.segments[0].start[0], 6.0, 6)
        both = C.lengthen(line, 'pourcent', 150, 'les_deux')
        self.assertEqual((both.segments[0].start, both.segments[-1].end), ((-2.5, 0.0), (12.5, 0.0)))
        arc = geom.Contour(geom.circle((0, 0), 5).segments[:1], False)
        L = C.contour_length(arc)
        self.assertAlmostEqual(C.contour_length(C.lengthen(arc, 'delta', -1)), L - 1, 3)   # coupé dans la courbe
        self.assertAlmostEqual(C.contour_length(C.lengthen(arc, 'delta', 2)), L + 2, 3)    # tangente prolongée
        with self.assertRaises(ValueError):
            C.lengthen(line, 'total', 0)

    def test_center_and_mass(self):
        self.assertEqual(C.circle_of(geom.circle((3, 4), 5)), ((3.0, 4.0), 5.0))
        self.assertIsNone(C.circle_of(geom.rect(0, 0, 20, 10)))
        mark = C.center_mark((0, 0), 5, 2, 2, True)
        self.assertEqual(len(mark.contours), 6)
        self.assertAlmostEqual(max(abs(c.segments[0].end[0]) for c in mark.contours), 7.0)
        m = C.mass_properties(geom.Path([geom.rect(0, 0, 20, 10)]))
        self.assertAlmostEqual(m['area'], 200)
        self.assertEqual(m['centroid'], (10.0, 5.0))
        self.assertAlmostEqual(m['Ixx'], 20 * 10 ** 3 / 12)
        self.assertAlmostEqual(m['Iyy'], 10 * 20 ** 3 / 12)
        self.assertAlmostEqual(m['Ixy'], 0, 6)
        holed = C.mass_properties(geom.Path([geom.rect(0, 0, 20, 10), geom.rect(5, 2, 4, 4)]))
        self.assertAlmostEqual(holed['area'], 184)


class TestWindow(unittest.TestCase):
    def test_commands(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            line = Shape(path=geom.Path([geom.polyline([(0, 0), (20, 0)])]))
            circ = Shape(path=geom.Path([geom.circle((50, 0), 5)]))
            c.doc.add(line)
            c.doc.add(circ)
            c.select([line])
            g = w.cad_points('divide', {'count': 4})
            self.assertIsInstance(g, Group)
            self.assertEqual(len(g.children), 3)
            c.select([line])
            self.assertEqual(len(w.cad_points('measure', {'step': 6.0}).children), 3)
            c.select([line])
            self.assertEqual(w.cad_lengthen({'mode': 'total', 'value': 25.0, 'end': 'fin'}), 1)
            self.assertAlmostEqual(line.path.contours[0].segments[-1].end[0], 25.0)
            c.select([circ, line])
            self.assertEqual(len(w.cad_center_marks({'lines': False}).children), 1)
            c.select([circ])
            m = w.cad_massprop(show=False)
            self.assertAlmostEqual(m['area'], math.pi * 25, 1)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
