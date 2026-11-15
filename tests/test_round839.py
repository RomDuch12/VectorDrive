"""Round 839 : Contour du trait complet (TypeEdit : Couteaux) : coins, bouts, original gardé, enveloppe et marge."""
import math
import os
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication

from vectordrive.core import strokehull as EN
from vectordrive.core import geom
from vectordrive.core.document import Layer, Plate, Shape
from vectordrive.core.geom import Path
from vectordrive.core.pathops import _to_shapely
from vectordrive.ui import shortcuts as S
from vectordrive.ui.main_window import MainWindow

app = QApplication.instance() or QApplication([])
BEND = Path([geom.polyline([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)])])


def area(p):
    return _to_shapely(p).area


class Stroke(unittest.TestCase):
    def test_flat_ends_stop_at_the_end_of_the_line(self):
        o = EN.stroke(Path([geom.polyline([(0.0, 0.0), (10.0, 0.0)])]), 1.0, 'aigu', 'plat')
        self.assertEqual(tuple(round(v, 6) for v in o.bbox()), (0.0, -1.0, 10.0, 1.0))
        self.assertAlmostEqual(area(o), 20.0, places=6)

    def test_round_ends_go_past_it(self):
        o = EN.stroke(Path([geom.polyline([(0.0, 0.0), (10.0, 0.0)])]), 1.0, 'arrondi', 'arrondi')
        self.assertAlmostEqual(o.bbox()[0], -1.0, places=3)
        self.assertAlmostEqual(area(o), 20.0 + math.pi, delta=0.01)

    def test_corners(self):
        sharp = area(EN.stroke(BEND, 1.0, 'aigu', 'plat'))
        chamfer = area(EN.stroke(BEND, 1.0, 'chanfrein', 'plat'))
        rounded = area(EN.stroke(BEND, 1.0, 'arrondi', 'plat'))
        self.assertAlmostEqual(sharp, 40.0, places=6)
        self.assertAlmostEqual(chamfer, 39.5, places=6)
        self.assertAlmostEqual(rounded, 39.0 + math.pi / 4, delta=0.01)

    def test_the_sharp_corner_reaches_the_corner_of_the_band(self):
        o = EN.stroke(BEND, 1.0, 'aigu', 'plat')
        self.assertAlmostEqual(o.bbox()[2], 11.0, places=6)
        self.assertAlmostEqual(o.bbox()[1], -1.0, places=6)
        q = max((p for pts in o.flatten(0.01) for p in pts), key=lambda p: p[0] - p[1])
        self.assertEqual(tuple(round(v, 6) for v in q), (11.0, -1.0))

    def test_a_very_closed_angle_does_not_shoot_away(self):
        p = Path([geom.polyline([(0.0, 0.0), (100.0, 0.0), (0.0, 0.5)])])
        o = EN.stroke(p, 1.0, 'aigu', 'plat')
        self.assertLess(o.bbox()[2], 100.0 + 1.0 * EN.MITRE_LIMIT + 0.1)

    def test_a_closed_contour_has_no_ends(self):
        ring = EN.stroke(Path([geom.rect(0.0, 0.0, 10.0, 10.0)]), 1.0, 'aigu', 'plat')
        self.assertEqual(len(ring.contours), 2)
        self.assertAlmostEqual(area(ring), 12.0 * 12.0 - 8.0 * 8.0, places=6)

    def test_round_keeps_real_arcs(self):
        o = EN.stroke(Path([geom.circle((0.0, 0.0), 10.0)]), 1.0)
        self.assertLess(sum(len(c.segments) for c in o.contours), 40)

    def test_negative_radius_is_a_radius(self):
        self.assertAlmostEqual(area(EN.stroke(BEND, -1.0, 'aigu', 'plat')), 40.0, places=6)

    def test_zero_or_unknown_refused(self):
        with self.assertRaises(ValueError):
            EN.stroke(BEND, 0.0)
        with self.assertRaises(ValueError):
            EN.stroke(BEND, 1.0, 'pointu')


class Envelope(unittest.TestCase):
    L = Path([geom.polyline([(0.0, 0.0), (30.0, 0.0), (30.0, 5.0), (5.0, 5.0), (5.0, 30.0), (0.0, 30.0)], closed=True)])

    def closed_one(self, e):
        self.assertEqual(len(e.contours), 1)
        self.assertTrue(e.contours[0].closed)

    def test_rectangle(self):
        e = EN.envelope(self.L, 'rectangle', 2.0)
        self.closed_one(e)
        self.assertEqual(e.bbox(), (-2.0, -2.0, 32.0, 32.0))

    def test_circle(self):
        e = EN.envelope(self.L, 'cercle', 2.0)
        self.closed_one(e)
        x0, y0, x1, y1 = e.bbox()
        self.assertAlmostEqual((x1 - x0) / 2, 30.0 * math.sqrt(2) / 2 + 2.0, delta=0.05)

    def test_every_envelope_covers_the_drawing(self):
        for kind in EN.ENVELOPES:
            with self.subTest(kind):
                e = EN.envelope(self.L, kind, 0.0)
                self.closed_one(e)
                self.assertGreaterEqual(area(e) + 0.01, area(self.L))
                self.assertLess(_to_shapely(self.L).difference(_to_shapely(e).buffer(0.01)).area, 0.01)

    def test_areas_come_in_the_right_order(self):
        rect, conv, conc = [area(EN.envelope(self.L, k, 0.0)) for k in ('rectangle', 'convexe', 'concave')]
        self.assertLess(conv, rect)
        self.assertLess(conc, conv)                     # la concave économise la matière

    def test_margin_grows_the_area(self):
        for kind in EN.ENVELOPES:
            with self.subTest(kind):
                self.assertGreater(area(EN.envelope(self.L, kind, 2.0)), area(EN.envelope(self.L, kind, 0.0)))

    def test_concave_joins_separate_pieces(self):
        p = Path([geom.rect(0.0, 0.0, 10.0, 10.0), geom.rect(14.0, 0.0, 10.0, 10.0), geom.rect(100.0, 0.0, 10.0, 10.0)])
        self.closed_one(EN.envelope(p, 'concave', 0.0))

    def test_an_envelope_has_no_hole(self):
        ring = Path([geom.rect(0.0, 0.0, 30.0, 30.0), geom.rect(10.0, 10.0, 10.0, 10.0)])
        self.closed_one(EN.envelope(ring, 'concave', 1.0))

    def test_open_lines_and_a_single_line(self):
        for kind in EN.ENVELOPES:
            with self.subTest(kind):
                e = EN.envelope(Path([geom.polyline([(0.0, 0.0), (10.0, 0.0)])]), kind, 1.0)
                self.closed_one(e)
                self.assertGreater(area(e), 0.0)

    def test_empty(self):
        self.assertEqual(EN.envelope(Path(), 'convexe', 1.0).contours, [])

    def test_unknown(self):
        with self.assertRaises(ValueError):
            EN.envelope(self.L, 'triangle')


class Dialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()
        cls.win.deleteLater()

    def setUp(self):
        self.c = self.win.canvas
        self.doc = self.c.doc
        self.layer = Layer(name='Plan 1')
        self.doc.layers[:] = [self.layer]
        self.doc.active = self.layer.id
        self.doc.plate = Plate(width=200.0, height=100.0)
        self.win._undo.clear()
        self.s = Shape(path=Path([geom.polyline([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)])]))
        self.layer.items.append(self.s)
        self.c.select([self.s])

    def test_defaults_replace_the_line(self):
        out = self.win.stroke_dialog({'radius': 1.0})
        self.assertEqual(self.layer.items, out)
        self.assertEqual(self.c.selection, out)
        self.assertAlmostEqual(area(out[0].path), 39.0 + math.pi / 4 + math.pi, delta=0.02)

    def test_keep_adds_above_the_original(self):
        out = self.win.stroke_dialog({'radius': 1.0, 'keep': True})
        self.assertEqual(self.layer.items, [self.s] + out)

    def test_undo_of_keep(self):
        n = len(self.win._undo)
        self.win.stroke_dialog({'radius': 1.0, 'keep': True})
        self.assertEqual(len(self.win._undo), n + 1)
        self.win.undo()
        self.assertEqual(len(self.doc.layers[0].items), 1)

    def test_undo_of_replace(self):
        self.win.stroke_dialog({'radius': 1.0})
        self.win.undo()
        self.assertEqual(len(self.doc.layers[0].items), 1)
        self.assertFalse(self.doc.layers[0].items[0].path.contours[0].closed)

    def test_corner_and_end_reach_the_result(self):
        out = self.win.stroke_dialog({'radius': 1.0, 'corner': 'aigu', 'end': 'plat'})
        self.assertAlmostEqual(area(out[0].path), 40.0, places=6)

    def test_envelope_comes_too(self):
        out = self.win.stroke_dialog({'radius': 1.0, 'corner': 'aigu', 'end': 'plat', 'envelope': 'rectangle', 'margin': 2.0})
        self.assertEqual(len(out), 2)
        self.assertEqual(out[1].path.bbox(), (-2.0, -3.0, 13.0, 12.0))

    def test_envelope_goes_round_all_the_selection(self):
        k = Shape(path=Path([geom.polyline([(50.0, 0.0), (60.0, 0.0)])]))
        self.layer.items.append(k)
        self.c.select([self.s, k])
        out = self.win.stroke_dialog({'radius': 1.0, 'envelope': 'rectangle', 'margin': 0.0})
        self.assertEqual(len(out), 3)
        self.assertAlmostEqual(out[2].path.bbox()[2], 61.0, places=3)

    def test_zero_radius_does_nothing(self):
        self.assertEqual(self.win.stroke_dialog({'radius': 0.0}), [])
        self.assertEqual(self.layer.items, [self.s])

    def test_no_selection(self):
        self.c.select([])
        self.assertEqual(self.win.stroke_dialog({'radius': 1.0}), [])

    def test_cancel(self):
        with mock.patch.object(self.win, '_ask', return_value=None):
            self.assertEqual(self.win.stroke_dialog(), [])
        self.assertEqual(self.layer.items, [self.s])

    def test_the_ribbon_action_opens_the_window(self):
        with mock.patch.object(self.win, '_ask', return_value=None) as ask:
            self.win.A['stroke'].trigger()
        ask.assert_called_once()

    def test_typeedit_command(self):
        self.assertEqual(S.TE_ACTIONS['ID_COMPOBOOLCOUTEAU'], 'stroke')


if __name__ == '__main__':
    unittest.main()
