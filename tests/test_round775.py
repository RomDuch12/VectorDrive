"""Round 775 : copier dans une forme."""
import math
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())

from PySide6.QtWidgets import QApplication, QMessageBox
from shapely.geometry import Polygon

from vectordrive.core import nesting as N
from vectordrive.core.document import Layer, Plate, Shape, Text
from vectordrive.core.geom import Path, circle, polyline, rect
from vectordrive.ui import shortcuts as S

PLATE = Plate(x=0.0, y=0.0, width=500.0, height=500.0)


def box(w=10.0, h=10.0, x=0.0, y=0.0):
    return Shape(path=Path([rect(x, y, w, h)]))


def poly(item):
    return Polygon(item.path.contours[0].flatten(0.02))


def into(items, region, **kw):
    kw.setdefault('margin', 0.0)
    kw.setdefault('gap', 0.0)
    kw.setdefault('copies', 0)
    kw.setdefault('precision', 0.5)
    return N.nest(items, PLATE, N.NestSpec(region=region, **kw))


class Core(unittest.TestCase):
    def test_square_filled(self):
        res = into([box(10, 10)], Path([rect(100, 100, 42, 42)]), allow_rotate=False)
        self.assertGreaterEqual(len(res.placed), 9)
        self.assertLessEqual(len(res.placed), 16)

    def test_placed_stays_inside_the_region(self):
        target = Polygon(circle((200, 200), 50).flatten(0.01))
        res = into([box(12, 12)], Path([circle((200, 200), 50)]), gap=1.0)
        self.assertGreaterEqual(len(res.placed), 8)
        for it, m in res.placed:
            self.assertTrue(target.contains(poly(it.transformed(m))))

    def test_far_from_the_plate(self):
        res = into([box()], Path([rect(5000, -3000, 30, 30)]))
        b = res.placed[0][0].transformed(res.placed[0][1]).bbox()
        self.assertGreaterEqual(b[0], 5000.0)
        self.assertLessEqual(b[3], -2970.0)

    def test_margin_respected(self):
        target = Polygon(rect(0, 0, 100, 100).flatten(0.01)).buffer(-5.0)
        res = into([box(20, 20)], Path([rect(0, 0, 100, 100)]), margin=5.0, gap=1.0)
        self.assertGreater(len(res.placed), 0)
        for it, m in res.placed:
            self.assertTrue(target.buffer(1e-6).contains(poly(it.transformed(m))))

    def test_gap_respected(self):
        res = into([box(10, 10)], Path([rect(0, 0, 60, 60)]), gap=3.0)
        polys = [poly(it.transformed(m)) for it, m in res.placed]
        self.assertGreater(len(polys), 3)
        for i, a in enumerate(polys):
            for b in polys[i + 1:]:
                self.assertGreaterEqual(a.distance(b), 3.0 - 1e-6)

    def test_hole_of_the_region_stays_empty(self):
        ring = Path([rect(0, 0, 100, 100), rect(25, 25, 50, 50).reversed()])
        hole = Polygon(rect(25, 25, 50, 50).flatten(0.1))
        res = into([box(10, 10)], ring)
        self.assertGreater(len(res.placed), 8)
        for it, m in res.placed:
            self.assertLess(poly(it.transformed(m)).intersection(hole).area, 1e-6)

    def test_concave_region(self):
        ell = Path([polyline([(0, 0), (100, 0), (100, 30), (30, 30), (30, 100), (0, 100)], True)])
        target = Polygon(ell.contours[0].flatten(0.1))
        res = into([box(14, 14)], ell, allow_rotate=False)
        self.assertGreater(len(res.placed), 6)
        for it, m in res.placed:
            self.assertTrue(target.buffer(1e-6).contains(poly(it.transformed(m))))

    def test_counted_copies_stop_at_the_count(self):
        res = into([box(5, 5)], Path([rect(0, 0, 100, 100)]), counts=[3])
        self.assertEqual(len(res.placed), 3)
        self.assertEqual(res.plates, 1)

    def test_no_second_sheet(self):
        res = into([box(30, 30)], Path([rect(0, 0, 40, 40)]), counts=[3])
        self.assertEqual(len(res.placed), 1)
        self.assertEqual(res.sheets, [0])
        self.assertEqual(res.unplaced, [])                       # placé au moins une fois : la commande compte ce qui manque

    def test_too_large_for_the_region(self):
        big = box(90, 90)
        res = into([big], Path([rect(0, 0, 40, 40)]))
        self.assertEqual(res.placed, [])
        self.assertEqual(res.plates, 0)
        self.assertEqual(res.unplaced, [big])

    def test_usage_is_relative_to_the_region(self):
        res = into([box(40, 40)], Path([rect(0, 0, 45, 45)]), allow_rotate=False, precision=0.25, counts=[1])
        self.assertAlmostEqual(res.usage, 1600 / 2025, delta=0.06)

    def test_flat_region(self):
        res = into([box()], Path([polyline([(0, 0), (10, 0)], False)]))
        self.assertEqual(res.placed, [])

    def test_corner(self):
        for corner, xi, x, yi, y in (('haut_gauche', 0, 0.0, 3, 50.0), ('bas_droit', 2, 50.0, 1, 0.0)):
            res = into([box(10, 10)], Path([rect(0, 0, 50, 50)]), counts=[1], corner=corner, allow_rotate=False)
            b = res.placed[0][0].transformed(res.placed[0][1]).bbox()
            self.assertAlmostEqual(b[xi], x, delta=2.5, msg=corner)
            self.assertAlmostEqual(b[yi], y, delta=2.5, msg=corner)

    def test_corner_stays_inside(self):
        target = Polygon(circle((0, 0), 40).flatten(0.01))
        for corner in N.CORNERS:
            res = into([box(10, 10)], Path([circle((0, 0), 40)]), counts=[6], corner=corner)
            self.assertEqual(len(res.placed), 6, corner)
            for it, m in res.placed:
                self.assertTrue(target.contains(poly(it.transformed(m))), corner)

    def test_plate_nesting_unchanged(self):
        self.assertIsNone(N.NestSpec().region)
        res = N.nest([box()], PLATE, N.NestSpec(copies=2))
        self.assertEqual(len(res.placed), 2)


class Command(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.settings.remove('cad/copy_into')
        cls.win.close()

    def setUp(self):
        self.win.settings.remove('cad/copy_into')
        doc = self.win.canvas.doc
        doc.plate = PLATE
        doc.layers = [Layer(name='Plan 1')]
        doc.active = doc.layers[0].id
        self.obj = box(10, 10, x=300.0, y=300.0)
        self.target = Shape(path=Path([circle((100, 100), 40)]))
        doc.layers[0].items = [self.obj, self.target]
        self.win.canvas.select([self.obj, self.target])

    def _params(self, **kw):
        d = {'count': 0, 'margin': 1.0, 'gap': 1.0, 'allow_rotate': True, 'angle_step': 90.0, 'in_holes': False, 'precision': 0.5}
        d.update(kw)
        return d

    def test_te_command_and_ribbon(self):
        self.assertEqual(S.TE_ACTIONS['ID_MAGICCOPY'], 'copy_into_shape')
        found = [b for i in range(self.win.ribbon.count()) for g in self.win.ribbon.page(i).groups() for b in g.buttons()
                 if b.defaultAction() is self.win.A['copy_into_shape']]
        self.assertEqual(len(found), 1)

    def test_fills_the_shape_and_keeps_originals(self):
        res = self.win.copy_into_shape(self._params())
        items = self.win.canvas.doc.layers[0].items
        self.assertIn(self.obj, items)
        self.assertIn(self.target, items)
        self.assertEqual(len(items), 2 + len(res.placed))
        self.assertGreater(len(res.placed), 8)
        self.assertEqual(self.obj.bbox()[0], 300.0)
        self.assertEqual(len(self.win.canvas.selection), len(res.placed))

    def test_copies_are_new_objects(self):
        self.win.copy_into_shape(self._params(count=2))
        items = self.win.canvas.doc.layers[0].items
        self.assertEqual(len({i.id for i in items}), len(items))

    def test_undo(self):
        self.win.copy_into_shape(self._params())
        self.win.undo()
        self.assertEqual(len(self.win.canvas.doc.layers[0].items), 2)

    def test_report_with_count(self):
        self.win.copy_into_shape(self._params(count=2))
        self.assertIn('2', self.win.statusBar().currentMessage())
        self.assertIn('%', self.win.statusBar().currentMessage())

    def test_report_of_what_did_not_fit(self):
        self.win.canvas.doc.layers[0].items = [self.obj, self.target]
        self.win.canvas.select([self.obj, self.target])
        res = self.win.copy_into_shape(self._params(count=500))
        self.assertLess(len(res.placed), 500)
        self.assertIn(str(500 - len(res.placed)), self.win.statusBar().currentMessage())

    def test_several_objects_counted_each(self):
        other = box(8, 8, x=320.0, y=300.0)
        self.win.canvas.doc.layers[0].items.append(other)
        self.win.canvas.select([self.obj, other, self.target])
        res = self.win.copy_into_shape(self._params(count=2))
        self.assertEqual(len(res.placed), 4)

    def test_text_copies_stay_texts(self):
        t = Text(text='A', font='Arial', size=6.0)
        self.win.canvas.doc.layers[0].items = [t, self.target]
        self.win.canvas.select([t, self.target])
        self.win.copy_into_shape(self._params(count=2))
        self.assertEqual(sum(isinstance(i, Text) for i in self.win.canvas.doc.layers[0].items), 3)

    def test_selection_needs_two_objects(self):
        self.win.canvas.select([self.target])
        with mock.patch.object(QMessageBox, 'information') as info:
            self.assertIsNone(self.win.copy_into_shape(self._params()))
        info.assert_called_once()

    def test_empty_selection(self):
        self.win.canvas.select([])
        with mock.patch.object(QMessageBox, 'information') as info:
            self.assertIsNone(self.win.copy_into_shape(self._params()))
        info.assert_called_once()

    def test_open_target_refused(self):
        line = Shape(path=Path([polyline([(0, 0), (50, 0)], False)]))
        self.win.canvas.doc.layers[0].items.append(line)
        self.win.canvas.select([self.obj, line])
        with mock.patch.object(QMessageBox, 'information') as info:
            self.assertIsNone(self.win.copy_into_shape(self._params()))
        info.assert_called_once()

    def test_nothing_fits(self):
        self.obj.path = Path([rect(300, 300, 400, 400)])
        with mock.patch.object(QMessageBox, 'information') as info:
            res = self.win.copy_into_shape(self._params())
        info.assert_called_once()
        self.assertEqual(res.placed, [])
        self.assertEqual(len(self.win.canvas.doc.layers[0].items), 2)

    def test_cancel(self):
        with mock.patch.object(self.win, '_ask', return_value=None):
            self.assertIsNone(self.win.copy_into_shape())
        self.assertEqual(len(self.win.canvas.doc.layers[0].items), 2)

    def test_copies_in_the_target_layer(self):
        doc = self.win.canvas.doc
        second = Layer(name='Plan 2', items=[self.target])
        doc.layers[0].items = [self.obj]
        doc.layers.append(second)
        self.win.canvas.select([self.obj, self.target])
        res = self.win.copy_into_shape(self._params(count=2))
        self.assertEqual(len(second.items), 1 + len(res.placed))


if __name__ == '__main__':
    unittest.main()
