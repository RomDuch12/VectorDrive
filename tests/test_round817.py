"""Round 817 : plume calligraphique."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication

from vectordrive.core import varstroke as VS
from vectordrive.core.document import Layer, Plate, Shape
from vectordrive.core.geom import Path, circle, polyline

app = QApplication.instance() or QApplication([])


def stroke(*pts, closed=False):
    return Path([polyline(list(pts), closed=closed)])


def area(path):
    return sum(c.signed_area() for c in path.contours)


class Nib(unittest.TestCase):
    def test_flat_nib_is_a_segment_of_its_width(self):
        pts = VS.nib(10.0, 0.0, 0.0)
        self.assertAlmostEqual(max(p[0] for p in pts) - min(p[0] for p in pts), 10.0)
        self.assertAlmostEqual(max(abs(p[1]) for p in pts), 0.0)

    def test_angle_turns_it(self):
        pts = VS.nib(10.0, 90.0, 0.0)
        self.assertAlmostEqual(max(p[1] for p in pts) - min(p[1] for p in pts), 10.0)
        self.assertAlmostEqual(max(abs(p[0]) for p in pts), 0.0, places=6)

    def test_round_nib(self):
        for x, y in VS.nib(10.0, 37.0, 1.0):
            self.assertAlmostEqual(math.hypot(x, y), 5.0)

    def test_ratio_is_bounded(self):
        self.assertAlmostEqual(max(math.hypot(*p) for p in VS.nib(10.0, 0.0, 7.0)), 5.0)
        self.assertAlmostEqual(max(abs(p[1]) for p in VS.nib(10.0, 0.0, -1.0)), 0.0)


class Stroke(unittest.TestCase):
    def test_across_the_nib_is_full_width(self):
        """Un trait à l'horizontale, une plume verticale : une bande de toute la largeur."""
        got = VS.nib_stroke(stroke((0, 0), (100, 0)), 10.0, 90.0, 0.0)
        self.assertAlmostEqual(abs(area(got)), 1000.0, delta=0.5)
        bb = got.bbox()
        self.assertAlmostEqual(bb[3] - bb[1], 10.0)

    def test_along_the_nib_is_thin(self):
        got = VS.nib_stroke(stroke((0, 0), (100, 0)), 10.0, 0.0, 0.1)
        bb = got.bbox()
        self.assertAlmostEqual(bb[3] - bb[1], 1.0, delta=0.01)

    def test_flat_along_the_nib_is_nothing(self):
        self.assertEqual(VS.nib_stroke(stroke((0, 0), (100, 0)), 10.0, 0.0, 0.0).contours, [])

    def test_diagonal_gives_the_sine(self):
        got = VS.nib_stroke(stroke((0, 0), (100, 0)), 10.0, 30.0, 0.0)
        self.assertAlmostEqual(abs(area(got)), 100 * 10 * math.sin(math.radians(30)), delta=0.5)

    def test_thick_and_thin_round_a_curve(self):
        got = VS.nib_stroke(Path([circle((0, 0), 50)]), 10.0, 0.0, 0.05)
        self.assertEqual(len(got.contours), 2)                            # l'anneau et son trou
        b = got.bbox()
        self.assertAlmostEqual(b[2] - b[0], 110.0, delta=0.05)            # la plume horizontale déborde de 5 de chaque côté
        self.assertAlmostEqual(b[3] - b[1], 100.5, delta=0.05)            # et presque pas en haut et en bas

    def test_closed_contour_comes_back_to_its_start(self):
        got = VS.nib_stroke(stroke((0, 0), (40, 0), (40, 40), (0, 40), closed=True), 4.0, 45.0, 0.0)
        self.assertEqual(len(got.contours), 2)

    def test_self_crossing_stays_one_valid_shape(self):
        got = VS.nib_stroke(stroke((0, 0), (100, 100), (100, 0), (0, 100)), 6.0, 30.0, 0.1)
        self.assertGreaterEqual(len(got.contours), 1)
        self.assertGreater(abs(area(got)), 100.0)

    def test_several_contours(self):
        p = Path([polyline([(0, 0), (10, 0)], closed=False), polyline([(0, 50), (10, 50)], closed=False)])
        self.assertEqual(len(VS.nib_stroke(p, 2.0, 90.0, 0.0).contours), 2)

    def test_empty(self):
        self.assertEqual(VS.nib_stroke(Path(), 2.0).contours, [])

    def test_zero_width(self):
        self.assertEqual(VS.nib_stroke(stroke((0, 0), (10, 0)), 0.0).contours, [])


class Window(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()
        cls.win.deleteLater()

    def setUp(self):
        self.doc = self.win.canvas.doc
        self.layer = Layer(name='Plan 1')
        self.doc.layers[:] = [self.layer]
        self.doc.active = self.layer.id
        self.doc.plate = Plate(width=100.0, height=100.0)
        self.win._undo.clear()

    def test_replaces_the_stroke_and_keeps_its_tool(self):
        s = Shape(path=stroke((10, 10), (90, 10)), tool=1)
        self.layer.items.append(s)
        self.win.canvas.select([s])
        new = self.win.nib_stroke({'width': 4.0, 'angle': 90.0, 'ratio': 0.0})
        self.assertEqual(len(new), 1)
        self.assertEqual(new[0].tool, 1)
        self.assertEqual(self.layer.items, new)
        self.assertAlmostEqual(new[0].bbox()[3] - new[0].bbox()[1], 4.0)

    def test_undo(self):
        s = Shape(path=stroke((10, 10), (90, 10)))
        self.layer.items.append(s)
        self.win.canvas.select([s])
        self.win.nib_stroke({})
        self.win.undo()
        self.assertFalse(self.win.canvas.doc.layers[0].items[0].path.contours[0].closed)

    def test_nothing_selected(self):
        self.win.canvas.select([])
        self.assertEqual(self.win.nib_stroke({}), [])

    def test_stroke_along_a_flat_nib_stays_put(self):
        s = Shape(path=stroke((10, 10), (90, 10)))
        self.layer.items.append(s)
        self.win.canvas.select([s])
        self.assertEqual(self.win.nib_stroke({'width': 4.0, 'angle': 0.0, 'ratio': 0.0}), [])
        self.assertEqual(self.layer.items, [s])

    def test_action_exists(self):
        self.assertIn('nib_stroke', self.win.A)


if __name__ == '__main__':
    unittest.main()
