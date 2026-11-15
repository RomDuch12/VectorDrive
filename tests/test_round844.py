"""Round 844 : Duplication sur courbe : plusieurs courbes, par déformation, selon une courbe ; Interpoler entre deux objets."""
import math
import os
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication

from vectordrive.core import duplicate as D
from vectordrive.core import forms, geom, morph as M
from vectordrive.core.document import Layer, Plate, Shape
from vectordrive.core.geom import Conic, Contour, Cubic, Line, Path
from vectordrive.core.pathops import _to_shapely
from vectordrive.ui.dialogs import DuplicateDialog
from vectordrive.ui.main_window import MainWindow

app = QApplication.instance() or QApplication([])


def shape(*contours):
    return Shape(path=Path(list(contours)))


def center(item):
    b = item.bbox()
    return round((b[0] + b[2]) / 2, 6), round((b[1] + b[3]) / 2, 6)


class Morph(unittest.TestCase):
    def test_same_structure_stays_exact(self):
        a = Path([geom.rect(0.0, 0.0, 10.0, 10.0)])
        b = Path([geom.rect(0.0, 0.0, 20.0, 30.0)])
        m = M.interpolate(a, b, 0.5).contours[0]
        self.assertEqual(len(m.segments), 4)
        self.assertTrue(all(isinstance(s, Line) for s in m.segments))
        self.assertEqual(geom.Path([m]).bbox(), (0.0, 0.0, 15.0, 20.0))

    def test_ends_are_the_two_shapes(self):
        a = Path([geom.rect(0.0, 0.0, 10.0, 10.0)])
        b = Path([geom.rect(5.0, 5.0, 20.0, 30.0)])
        self.assertEqual(M.interpolate(a, b, 0.0).bbox(), a.bbox())
        self.assertEqual(M.interpolate(a, b, 1.0).bbox(), b.bbox())

    def test_two_circles_stay_circles(self):
        a, b = Path([geom.circle((0.0, 0.0), 10.0)]), Path([geom.circle((0.0, 0.0), 20.0)])
        m = M.interpolate(a, b, 0.5)
        self.assertLess(len(m.contours[0].segments), 12)
        for q in m.contours[0].flatten(0.01):
            self.assertAlmostEqual(math.hypot(*q), 15.0, delta=0.02)

    def test_line_and_curve_mix(self):
        a = Contour([Line((0.0, 0.0), (10.0, 0.0))], False)
        b = Contour([Cubic((0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0))], False)
        m = M.interpolate(Path([a]), Path([b]), 0.5).contours[0]
        self.assertIsInstance(m.segments[0], Cubic)
        self.assertAlmostEqual(m.segments[0].point(0.5)[1], 3.75, places=6)

    def test_a_square_into_a_circle_is_resampled(self):
        a, b = Path([geom.rect(-10.0, -10.0, 20.0, 20.0)]), Path([geom.circle((0.0, 0.0), 10.0)])
        m = M.interpolate(a, b, 0.5).contours[0]
        self.assertTrue(m.closed)
        area = _to_shapely(Path([m])).area
        self.assertGreater(area, math.pi * 100.0 * 0.98)
        self.assertLess(area, 400.0)

    def test_opposite_directions_do_not_twist(self):
        a = Path([geom.rect(0.0, 0.0, 10.0, 10.0)])
        b = Path([geom.rect(0.0, 0.0, 10.0, 10.0).reversed()])
        self.assertAlmostEqual(abs(M.interpolate(a, b, 0.5).contours[0].signed_area()), 100.0)

    def test_another_start_point_does_not_twist(self):
        r = geom.rect(0.0, 0.0, 10.0, 10.0)
        other = Contour(list(r.segments[2:]) + list(r.segments[:2]), True)
        self.assertAlmostEqual(abs(M.interpolate(Path([r]), Path([other]), 0.5).contours[0].signed_area()), 100.0)

    def test_open_contour_taken_backwards(self):
        a = Path([geom.polyline([(0.0, 0.0), (10.0, 0.0)])])
        b = Path([geom.polyline([(10.0, 5.0), (0.0, 5.0)])])
        m = M.interpolate(a, b, 0.5).contours[0]
        self.assertEqual(m.start, (0.0, 2.5))

    def test_different_counts_refused(self):
        with self.assertRaises(ValueError):
            M.interpolate(Path([geom.rect(0.0, 0.0, 1.0, 1.0)]), Path(), 0.5)

    def test_several_contours(self):
        a = Path([geom.rect(0.0, 0.0, 10.0, 10.0), geom.rect(2.0, 2.0, 2.0, 2.0)])
        b = Path([geom.rect(0.0, 0.0, 20.0, 10.0), geom.rect(2.0, 2.0, 4.0, 2.0)])
        self.assertEqual(len(M.interpolate(a, b, 0.5).contours), 2)


class Along(unittest.TestCase):
    LINE = geom.polyline([(0.0, 0.0), (100.0, 0.0)])

    def test_following_keeps_the_gap(self):
        s = shape(geom.rect(-1.0, 9.0, 2.0, 2.0))         # 10 au-dessus du départ
        got = D.following([s], self.LINE, 3)
        self.assertEqual([center(x) for x in got], [(50.0, 10.0), (100.0, 10.0)])

    def test_following_turns_with_the_curve(self):
        s = shape(geom.rect(-1.0, 9.0, 2.0, 2.0))
        curve = geom.polyline([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)])
        got = D.following([s], curve, 3, rotate=True)
        self.assertEqual(center(got[-1]), (0.0, 10.0))

    def test_following_without_rotation(self):
        s = shape(geom.rect(-1.0, 9.0, 2.0, 2.0))
        curve = geom.polyline([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)])
        self.assertEqual(center(D.following([s], curve, 3, rotate=False)[-1]), (10.0, 20.0))

    def test_following_from_a_marker(self):
        s = shape(geom.rect(4.0, 4.0, 2.0, 2.0))          # 5 ; 5 du marqueur
        got = D.following([s], self.LINE, 2, origin=(0.0, 0.0))
        self.assertEqual(center(got[0]), (105.0, 5.0))

    def test_a_marker_away_from_the_start_goes_on_the_curve_too(self):
        s = shape(geom.rect(4.0, 4.0, 2.0, 2.0))
        got = D.following([s], geom.polyline([(10.0, 0.0), (110.0, 0.0)]), 2, origin=(0.0, 0.0))
        self.assertEqual([center(x) for x in got], [(15.0, 5.0), (115.0, 5.0)])

    def test_following_with_a_spacing(self):
        s = shape(geom.rect(-1.0, -1.0, 2.0, 2.0))
        self.assertEqual(len(D.following([s], self.LINE, 1, spacing=25.0)), 4)

    def test_following_a_closed_curve(self):
        s = shape(geom.rect(-1.0, -1.0, 2.0, 2.0))
        got = D.following([s], geom.rect(0.0, 0.0, 10.0, 10.0), 4, rotate=False)
        self.assertEqual(len(got), 3)
        self.assertIn((10.0, 10.0), [center(x) for x in got])

    def test_morph_goes_from_one_to_the_other(self):
        a = shape(geom.rect(-1.0, -1.0, 2.0, 2.0))
        b = shape(geom.rect(99.0, -5.0, 2.0, 10.0))
        got = D.morph_along(a, b, self.LINE, 5)
        self.assertEqual([center(x) for x in got], [(25.0, 0.0), (50.0, 0.0), (75.0, 0.0)])     # les bouts existent déjà
        self.assertAlmostEqual(got[1].bbox()[3] - got[1].bbox()[1], 6.0)

    def test_morph_away_from_the_ends_creates_every_copy(self):
        a = shape(geom.rect(0.0, 50.0, 2.0, 2.0))
        b = shape(geom.rect(0.0, 60.0, 2.0, 2.0))
        self.assertEqual(len(D.morph_along(a, b, self.LINE, 5)), 5)

    def test_morph_needs_two(self):
        a = shape(geom.rect(0.0, 0.0, 2.0, 2.0))
        self.assertEqual(D.morph_along(a, a, self.LINE, 1), [])


class Window(unittest.TestCase):
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
        self.c.select([])

    def tearDown(self):
        self.c.select([])

    def add(self, *contours):
        s = shape(*contours)
        self.layer.items.append(s)
        return s

    def v(self, **k):
        return dict({'mode': 'along', 'al_n': 3, 'al_sp': 0.0, 'al_rot': False}, **k)

    def test_several_curves_all_get_copies(self):
        o = self.add(geom.rect(0.0, 50.0, 2.0, 2.0))
        c = self.add(geom.polyline([(0.0, 0.0), (10.0, 0.0)]), geom.polyline([(0.0, 20.0), (10.0, 20.0)]))
        self.c.select([o, c])
        self.assertEqual(len(self.win.duplicate(self.v())), 6)

    def test_one_curve_as_before(self):
        o = self.add(geom.rect(0.0, 50.0, 2.0, 2.0))
        c = self.add(geom.polyline([(0.0, 0.0), (10.0, 0.0)]))
        self.c.select([o, c])
        self.assertEqual(len(self.win.duplicate(self.v())), 3)

    def test_follow(self):
        o = self.add(geom.rect(-1.0, 9.0, 2.0, 2.0))
        c = self.add(geom.polyline([(0.0, 0.0), (100.0, 0.0)]))
        self.c.select([o, c])
        got = self.win.duplicate(self.v(al_kind='follow'))
        self.assertEqual([center(x) for x in got], [(50.0, 10.0), (100.0, 10.0)])

    def test_follow_uses_a_marker_of_the_selection(self):
        o = self.add(geom.rect(14.0, 4.0, 2.0, 2.0))
        spec = forms.from_dict({'kind': 'marker', 'cx': 10.0, 'cy': 0.0, 'size': 2.0})
        mark = Shape(path=spec.build())
        forms.attach(mark, spec)
        self.layer.items.append(mark)
        c = self.add(geom.polyline([(10.0, 0.0), (110.0, 0.0)]))
        self.c.select([o, mark, c])
        got = self.win.duplicate(self.v(al_kind='follow', al_n=2))
        self.assertEqual(len(got), 1)                     # le marqueur n'est pas recopié
        self.assertEqual(center(got[0]), (115.0, 5.0))

    def test_morph(self):
        a = self.add(geom.rect(-1.0, -1.0, 2.0, 2.0))
        b = self.add(geom.rect(99.0, -5.0, 2.0, 10.0))
        c = self.add(geom.polyline([(0.0, 0.0), (100.0, 0.0)]))
        self.c.select([a, b, c])
        self.assertEqual(len(self.win.duplicate(self.v(al_kind='morph', al_n=5))), 3)
        self.win.undo()
        self.assertEqual(len(self.doc.layers[0].items), 3)

    def test_morph_refuses_what_it_cannot_do(self):
        a = self.add(geom.rect(0.0, 0.0, 2.0, 2.0))
        c = self.add(geom.polyline([(0.0, 0.0), (100.0, 0.0)]))
        self.c.select([a, c])
        with mock.patch('vectordrive.ui.main_window.QMessageBox.information') as say:
            self.assertEqual(self.win.duplicate(self.v(al_kind='morph')), [])
        say.assert_called_once()

    def test_morph_with_different_contours_refused(self):
        a = self.add(geom.rect(0.0, 0.0, 2.0, 2.0))
        b = self.add(geom.rect(9.0, 0.0, 2.0, 2.0), geom.rect(20.0, 0.0, 2.0, 2.0))
        c = self.add(geom.polyline([(0.0, 0.0), (100.0, 0.0)]))
        self.c.select([a, b, c])
        with mock.patch('vectordrive.ui.main_window.QMessageBox.information') as say:
            self.assertEqual(self.win.duplicate(self.v(al_kind='morph')), [])
        say.assert_called_once()

    def test_dialog_gives_the_type(self):
        d = DuplicateDialog(self.win)
        try:
            self.assertEqual(d.values()['al_kind'], 'along')
            d.al_kind.setCurrentIndex(d.al_kind.findData('morph'))
            self.assertEqual(d.values()['al_kind'], 'morph')
        finally:
            d.deleteLater()

    def test_interpolate(self):
        a = self.add(geom.rect(0.0, 0.0, 10.0, 10.0))
        b = self.add(geom.rect(40.0, 0.0, 10.0, 10.0))
        self.c.select([a, b])
        new = self.win.interpolate_dialog({'steps': 3})
        self.assertEqual([center(x) for x in new], [(15.0, 5.0), (25.0, 5.0), (35.0, 5.0)])
        self.assertEqual(self.layer.items, [a] + new + [b])
        self.assertEqual(self.c.selection, new)
        self.win.undo()
        self.assertEqual(len(self.doc.layers[0].items), 2)

    def test_interpolate_refuses(self):
        a = self.add(geom.rect(0.0, 0.0, 10.0, 10.0))
        self.c.select([a])
        with mock.patch('vectordrive.ui.main_window.QMessageBox.information') as say:
            self.assertEqual(self.win.interpolate_dialog({'steps': 3}), [])
        say.assert_called_once()

    def test_interpolate_cancelled(self):
        a = self.add(geom.rect(0.0, 0.0, 10.0, 10.0))
        b = self.add(geom.rect(40.0, 0.0, 10.0, 10.0))
        self.c.select([a, b])
        with mock.patch.object(self.win, '_ask', return_value=None):
            self.assertEqual(self.win.interpolate_dialog(), [])
        self.assertEqual(len(self.layer.items), 2)


if __name__ == '__main__':
    unittest.main()
