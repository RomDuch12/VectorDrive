"""Round 843 : Convertir des courbes, contours ouverts repérés, Inverser l'ordre d'un objet combiné, classement depuis un coin."""
import math
import os
import random
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from vectordrive.core import fitshape as FS
from vectordrive.core import geom, selsort as SS
from vectordrive.core.document import Group, Layer, Plate, Shape
from vectordrive.core.geom import Affine, Contour, Path
from vectordrive.ui import shortcuts as S
from vectordrive.ui.main_window import MainWindow

app = QApplication.instance() or QApplication([])


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol


class Convert(unittest.TestCase):
    def assertSameBox(self, c, want, tol=1e-3):
        for a, b in zip(c.bbox(), want):
            self.assertAlmostEqual(a, b, delta=tol)

    def test_a_circle_stays_the_same_circle(self):
        c = FS.to_circle(geom.circle((100.0, 50.0), 7.0))
        self.assertSameBox(c, (93.0, 43.0, 107.0, 57.0))

    def test_a_polygon_gives_a_real_circle(self):
        pts = [(10 * math.cos(i * math.pi / 8), 10 * math.sin(i * math.pi / 8)) for i in range(16)]
        c = FS.to_circle(geom.polyline(pts, closed=True).close())
        self.assertFalse(any(isinstance(s, geom.Line) for s in c.segments))
        self.assertAlmostEqual(c.bbox()[2], 10.0, delta=0.2)

    def test_an_ellipse_is_found_again_with_its_axes_and_angle(self):
        place = Affine.translation(30.0, -20.0) @ Affine.rotation(25.0) @ Affine.scaling(12.0, 5.0)
        src = geom.circle((0.0, 0.0), 1.0).transformed(place)
        got = FS.to_ellipse(src)
        self.assertAlmostEqual(abs(got.signed_area()), math.pi * 60.0, delta=0.05)
        q = got.flatten(0.01)
        inv = place.inverse()
        for p in q:
            self.assertAlmostEqual(math.hypot(*inv.apply(p)), 1.0, delta=0.005)

    def test_a_circle_as_ellipse_is_round(self):
        got = FS.to_ellipse(geom.circle((0.0, 0.0), 5.0))
        b = got.bbox()
        self.assertAlmostEqual(b[2] - b[0], 10.0, delta=0.01)
        self.assertAlmostEqual(b[3] - b[1], 10.0, delta=0.01)

    def test_a_rectangle_is_found_again(self):
        got = FS.to_rectangle(geom.rect(10.0, 20.0, 30.0, 8.0))
        self.assertSameBox(got, (10.0, 20.0, 40.0, 28.0), tol=1e-6)
        self.assertEqual(len(got.segments), 4)

    def test_a_turned_rectangle_keeps_its_angle(self):
        src = geom.rect(-15.0, -4.0, 30.0, 8.0).transformed(Affine.rotation(30.0))
        got = FS.to_rectangle(src)
        for p in (s.end for s in got.segments):
            self.assertLess(min(math.dist(p, s.end) for s in src.segments), 1e-6)

    def test_a_turned_square_keeps_its_angle(self):
        src = geom.rect(-5.0, -5.0, 10.0, 10.0).transformed(Affine.rotation(20.0))
        got = FS.to_rectangle(src)
        for p in (s.end for s in got.segments):
            self.assertLess(min(math.dist(p, s.end) for s in src.segments), 1e-6)

    def test_a_shaky_rectangle(self):
        random.seed(843)
        pts = []
        for (x0, y0), (x1, y1) in (((0, 0), (40, 0)), ((40, 0), (40, 20)), ((40, 20), (0, 20)), ((0, 20), (0, 0))):
            for i in range(25):
                t = i / 25
                pts.append((x0 + (x1 - x0) * t + random.uniform(-0.1, 0.1), y0 + (y1 - y0) * t + random.uniform(-0.1, 0.1)))
        got = FS.to_rectangle(geom.polyline(pts, closed=True).close())
        b = got.bbox()
        self.assertAlmostEqual(b[2] - b[0], 40.0, delta=1.0)
        self.assertAlmostEqual(b[3] - b[1], 20.0, delta=1.0)

    def test_the_direction_is_kept(self):
        for c in (geom.rect(0.0, 0.0, 10.0, 6.0), geom.rect(0.0, 0.0, 10.0, 6.0).reversed()):
            for make in FS.MAKERS.values():
                self.assertEqual(make(c).signed_area() > 0, c.signed_area() > 0)

    def test_far_from_the_origin(self):
        got = FS.to_rectangle(geom.rect(1e6, 2e6, 30.0, 8.0))
        self.assertAlmostEqual(got.bbox()[0], 1e6, delta=1e-4)

    def test_a_straight_line_has_no_shape(self):
        p = Path([geom.polyline([(0.0, 0.0), (10.0, 0.0)])])
        self.assertEqual(FS.convert(p, 'rectangle')[1], 0)
        self.assertIs(FS.convert(p, 'rectangle')[0].contours[0], p.contours[0])

    def test_each_contour_on_its_own(self):
        p = Path([geom.rect(0.0, 0.0, 10.0, 10.0), geom.rect(20.0, 0.0, 10.0, 10.0)])
        out, n = FS.convert(p, 'cercle')
        self.assertEqual(n, 2)
        self.assertEqual(len(out.contours), 2)


class Sort(unittest.TestCase):
    def items(self):
        # trois colonnes, deux rangées
        return [Shape(path=Path([geom.rect(float(x), float(y), 2.0, 2.0)]), name=f'{x},{y}')
                for y in (0, 10) for x in (0, 10, 20)]

    def names(self, *a, **k):
        return [i.name for i in SS.sort(self.items(), *a, **k)]

    def test_default_is_top_left(self):
        self.assertEqual(self.names('h'), ['0,10', '10,10', '20,10', '0,0', '10,0', '20,0'])
        self.assertEqual(self.names('v'), ['0,10', '0,0', '10,10', '10,0', '20,10', '20,0'])

    def test_from_the_bottom_left(self):
        self.assertEqual(self.names('h', from_bottom=True), ['0,0', '10,0', '20,0', '0,10', '10,10', '20,10'])
        self.assertEqual(self.names('v', from_bottom=True), ['0,0', '0,10', '10,0', '10,10', '20,0', '20,10'])

    def test_from_the_top_right(self):
        self.assertEqual(self.names('h', from_right=True), ['20,10', '10,10', '0,10', '20,0', '10,0', '0,0'])
        self.assertEqual(self.names('v', from_right=True), ['20,10', '20,0', '10,10', '10,0', '0,10', '0,0'])

    def test_zig_zag_from_the_bottom_right(self):
        self.assertEqual(self.names('hz', from_right=True, from_bottom=True), ['20,0', '10,0', '0,0', '0,10', '10,10', '20,10'])
        self.assertEqual(self.names('vz', from_right=True, from_bottom=True), ['20,0', '20,10', '10,10', '10,0', '0,0', '0,10'])

    def test_inverse_ignores_the_corner(self):
        items = self.items()
        self.assertEqual(SS.sort(items, 'inverse', from_right=True), list(reversed(items)))


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
        self.c.scale = 8.0
        self.c.select([])
        self.c.sort_armed = None
        self.c.cross_marks = []

    def tearDown(self):
        self.c.select([])
        self.c.cross_marks = []

    def add(self, *contours):
        s = Shape(path=Path(list(contours)))
        self.layer.items.append(s)
        return s

    def test_convert_replaces_the_selection(self):
        s = self.add(geom.rect(0.0, 0.0, 10.0, 10.0))
        self.c.select([s])
        self.win.convert_curves({'kind': 'cercle'})
        self.assertFalse(any(isinstance(x, geom.Line) for x in self.layer.items[0].path.contours[0].segments))
        self.win.undo()
        self.assertEqual(len(self.doc.layers[0].items[0].path.contours[0].segments), 4)

    def test_convert_needs_a_selection(self):
        s = self.add(geom.rect(0.0, 0.0, 10.0, 10.0))
        before = s.path
        self.win.convert_curves({'kind': 'cercle'})
        self.assertIs(self.layer.items[0].path, before)

    def test_convert_cancelled(self):
        s = self.add(geom.rect(0.0, 0.0, 10.0, 10.0))
        self.c.select([s])
        with mock.patch.object(self.win, '_ask', return_value=None):
            self.win.convert_curves()
        self.assertIs(self.layer.items[0], s)

    def test_shift_keeps_the_original_when_converting(self):
        self.assertIn('convert_curves', MainWindow.KEEP_ORIGINAL)
        self.assertIn('stroke', MainWindow.KEEP_ORIGINAL)

    def test_real_window(self):
        s = self.add(geom.rect(0.0, 0.0, 10.0, 10.0))
        self.c.select([s])
        self.win.settings.remove('cad/convertir_courbes')
        try:
            with mock.patch('vectordrive.ui.dialogs.ParamsDialog.exec', return_value=1):
                self.win.convert_curves()
            self.assertIsNot(self.layer.items[0], s)
        finally:
            self.win.settings.remove('cad/convertir_courbes')

    def test_open_contours_are_marked_at_both_ends(self):
        self.add(geom.polyline([(0.0, 0.0), (10.0, 0.0)]), geom.rect(20.0, 0.0, 5.0, 5.0))
        self.assertEqual(self.win.mark_open_contours(), 1)
        self.assertEqual(sorted((x, y) for x, y, _k in self.c.cross_marks), [(0.0, 0.0), (10.0, 0.0)])

    def test_open_contours_in_a_group_or_only_the_selection(self):
        a = Shape(path=Path([geom.polyline([(0.0, 0.0), (10.0, 0.0)])]))
        g = Group(children=[a])
        b = self.add(geom.polyline([(0.0, 5.0), (10.0, 5.0)]))
        self.layer.items.insert(0, g)
        self.assertEqual(self.win.mark_open_contours(), 2)
        self.c.select([b])
        self.assertEqual(self.win.mark_open_contours(), 1)

    def test_none_open(self):
        self.add(geom.rect(0.0, 0.0, 10.0, 10.0))
        self.assertEqual(self.win.mark_open_contours(), 0)
        self.assertEqual(self.c.cross_marks, [])

    def test_ctrl_on_the_command(self):
        self.add(geom.polyline([(0.0, 0.0), (10.0, 0.0)]))
        with mock.patch.object(MainWindow, '_ctrl_held', staticmethod(lambda: True)):
            self.assertIsNone(self.win.intersections())
        self.assertEqual(len(self.c.cross_marks), 2)

    def test_reverse_in_a_combined_object(self):
        a, b = geom.rect(0.0, 0.0, 1.0, 1.0), geom.rect(5.0, 0.0, 1.0, 1.0)
        s = self.add(a, b)
        self.c.select([s])
        self.assertEqual(self.win.group_reverse(), 1)
        self.assertEqual(s.path.contours, [b, a])
        self.win.undo()
        self.assertEqual(self.doc.layers[0].items[0].path.contours, [a, b])

    def test_reverse_still_does_groups(self):
        x, y = Shape(path=Path([geom.rect(0.0, 0.0, 1.0, 1.0)])), Shape(path=Path([geom.rect(5.0, 0.0, 1.0, 1.0)]))
        g = Group(children=[x, y])
        self.layer.items.append(g)
        self.c.select([g])
        self.assertEqual(self.win.group_reverse(), 1)
        self.assertEqual(g.children, [y, x])

    def test_reverse_with_nothing_to_do(self):
        s = self.add(geom.rect(0.0, 0.0, 1.0, 1.0))
        self.c.select([s])
        self.assertEqual(self.win.group_reverse(), 0)

    def _row(self):
        return [self.add(geom.rect(float(x), 0.0, 2.0, 2.0)) for x in (0, 10, 20)]

    def test_sort_without_selection_waits_for_the_rectangle(self):
        items = self._row()
        self.assertEqual(self.win.sort_selection('h'), 0)
        self.assertEqual(self.c.sort_armed, 'h')
        a = QPointF(self.c.to_screen(30.0, -5.0))
        b = QPointF(self.c.to_screen(-5.0, 10.0))
        self.c.select_band({'start': a, 'now': b})
        self.assertEqual(self.layer.items, list(reversed(items)))      # de droite à gauche
        self.assertIsNone(self.c.sort_armed)

    def test_a_rectangle_from_the_left_sorts_from_the_left(self):
        items = self._row()
        self.win.sort_selection('h')
        self.c.select_band({'start': QPointF(self.c.to_screen(-5.0, 10.0)), 'now': QPointF(self.c.to_screen(30.0, -5.0))})
        self.assertEqual(self.layer.items, items)

    def test_a_plain_rectangle_does_not_sort(self):
        items = self._row()
        self.c.select_band({'start': QPointF(self.c.to_screen(30.0, -5.0)), 'now': QPointF(self.c.to_screen(-5.0, 10.0))})
        self.assertEqual(self.layer.items, items)

    def test_with_a_selection_it_sorts_at_once(self):
        items = self._row()
        self.c.select(list(reversed(items)))
        self.assertGreaterEqual(self.win.sort_selection('h'), 0)
        self.assertIsNone(self.c.sort_armed)
        self.assertEqual(self.layer.items, items)

    def test_one_selected_object_still_explains(self):
        items = self._row()
        self.c.select(items[:1])
        self.assertEqual(self.win.sort_selection('h'), 0)
        self.assertIsNone(self.c.sort_armed)

    def test_typeedit_command(self):
        self.assertEqual(S.TE_ACTIONS['ID_COMPO_CONVENCERCLE'], 'convert_curves')


if __name__ == '__main__':
    unittest.main()
