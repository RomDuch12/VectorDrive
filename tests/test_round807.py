"""Round 807 : le texte dans une forme contourne les autres formes sélectionnées."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication
from shapely.geometry import Point, Polygon

from vectordrive.core import textflow as TF
from vectordrive.core.document import Group, Shape, Text
from vectordrive.core.geom import Path, circle, rect
from vectordrive.ui.textflow_dialog import TextFlowDialog

app = QApplication.instance() or QApplication([])
WORDS = ' '.join(['gravure'] * 60)
FONT = 'Arial'


def square(x, y, w, h=None):
    return Path([rect(x, y, w, h if h is not None else w)])


def lines_of(g):
    return [c for c in g.children if isinstance(c, Text)]


def touching(g, poly):
    """Une lettre du groupe entre-t-elle dans ce polygone ?"""
    for t in lines_of(g):
        for c in t.outline.contours:
            pts = c.flatten(0.05)
            if len(pts) >= 3 and Polygon(pts).buffer(0).intersects(poly):
                return True
    return False


class Carve(unittest.TestCase):
    def test_a_hole(self):
        got = TF.carve(square(0, 0, 100), [Path([circle((50, 50), 10)])], 0.0)
        z = TF.region_of(got)
        self.assertAlmostEqual(z.area, 10000 - 314.16, delta=1.0)

    def test_with_a_gap(self):
        got = TF.carve(square(0, 0, 100), [Path([circle((50, 50), 10)])], 5.0)
        self.assertAlmostEqual(TF.region_of(got).area, 10000 - 706.86, delta=3.0)

    def test_across_the_edge(self):
        got = TF.carve(square(0, 0, 100), [square(80, 0, 40, 100)], 0.0)
        self.assertAlmostEqual(TF.region_of(got).area, 8000.0, delta=0.1)
        self.assertAlmostEqual(got.bbox()[2], 80.0, places=6)

    def test_cut_in_two(self):
        got = TF.carve(square(0, 0, 100), [square(45, -5, 10, 110)], 0.0)
        z = TF.region_of(got)
        self.assertEqual(len(z.geoms), 2)
        self.assertAlmostEqual(z.area, 9000.0, delta=0.1)

    def test_nothing_left(self):
        with self.assertRaises(ValueError):
            TF.carve(square(0, 0, 100), [square(-10, -10, 200)], 0.0)

    def test_an_open_obstacle_counts_for_nothing(self):
        from vectordrive.core.geom import polyline
        got = TF.carve(square(0, 0, 100), [Path([polyline([(0, 0), (50, 50)], False)])], 3.0)
        self.assertAlmostEqual(TF.region_of(got).area, 10000.0, delta=0.1)

    def test_the_text_keeps_away(self):
        got = TF.carve(square(0, 0, 100), [Path([circle((50, 50), 15)])], 3.0)
        g, flowed = TF.build(WORDS, FONT, got, TF.FlowSpec(size=4.0, margin=0.0, middle=False))
        self.assertIsNotNone(g)
        self.assertFalse(touching(g, Point(50, 50).buffer(17.5)))
        self.assertGreater(len(flowed.lines), 5)


class Dialog(unittest.TestCase):
    def test_no_gap_field_without_obstacles(self):
        d = TextFlowDialog(None, text='x')
        self.addCleanup(d.deleteLater)
        self.assertIsNone(d.gap)
        self.assertNotIn('gap', d.values())

    def test_gap_field(self):
        d = TextFlowDialog(None, text='x', gap=4.0)
        self.addCleanup(d.deleteLater)
        self.assertEqual(d.values()['gap'], 4.0)


class Command(unittest.TestCase):
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
        self.c = self.win.canvas
        self.doc = self.c.doc
        self.doc.layers[0].items = []
        self.c.selection = []
        self.win._undo.clear()
        self.win.settings.remove('cad/flow_gap')
        self.addCleanup(self.win.settings.remove, 'cad/flow_gap')

    def add(self, path):
        s = Shape(path=path)
        self.doc.add(s)
        return s

    def params(self, **kw):
        return dict({'text': WORDS, 'font': FONT, 'size': 4.0, 'fit': False, 'align': 'left', 'line_spacing': 1.2,
                     'margin': 0.0, 'middle': False, 'gap': 3.0}, **kw)

    def test_the_largest_receives_the_text_whatever_the_order(self):
        big, small = self.add(square(0, 0, 100)), self.add(Path([circle((50, 50), 15)]))
        for order in ([big, small], [small, big]):
            self.c.select(order)
            g = self.win.text_in_shape(params=self.params())
            self.assertIsInstance(g, Group)
            self.assertFalse(touching(g, Point(50, 50).buffer(17.5)))
            self.assertLessEqual(TF.region_child(g).path.bbox()[2], 100.0 + 1e-6)
            self.assertAlmostEqual(TF.region_child(g).path.bbox()[0], 0.0, places=6)
            self.doc.layers[0].items.remove(g)

    def test_obstacles_stay_in_the_drawing(self):
        big, small = self.add(square(0, 0, 100)), self.add(Path([circle((50, 50), 15)]))
        self.c.select([big, small])
        g = self.win.text_in_shape(params=self.params())
        self.assertIn(big, self.doc.layers[0].items)
        self.assertIn(small, self.doc.layers[0].items)
        self.assertIn(g, self.doc.layers[0].items)

    def test_re_editing_keeps_the_way_around(self):
        big, small = self.add(square(0, 0, 100)), self.add(Path([circle((50, 50), 15)]))
        self.c.select([big, small])
        g = self.win.text_in_shape(params=self.params())
        new = self.win.text_flow_edit(g, {'text': WORDS, 'font': FONT, 'size': 3.0, 'fit': False, 'align': 'left',
                                          'line_spacing': 1.2, 'margin': 0.0, 'middle': False})
        self.assertFalse(touching(new, Point(50, 50).buffer(17.5)))

    def test_one_shape_as_before(self):
        big = self.add(square(0, 0, 100))
        self.c.select([big])
        g = self.win.text_in_shape(params=self.params(gap=0.0))
        self.assertIsInstance(g, Group)

    def test_dialog_asks_for_the_gap_only_with_obstacles(self):
        big, small = self.add(square(0, 0, 100)), self.add(Path([circle((50, 50), 15)]))
        seen = []

        def fake(dlg):
            seen.append(dlg.gap)
            dlg.text.setPlainText('')
            return 1
        with mock.patch.object(TextFlowDialog, 'exec', fake):
            self.c.select([big])
            self.win.text_in_shape()
            self.c.select([big, small])
            self.win.text_in_shape()
        self.assertIsNone(seen[0])
        self.assertIsNotNone(seen[1])
        self.assertEqual(float(self.win.settings.value('cad/flow_gap')), seen[1].value())

    def test_nothing_left_says_so(self):
        big, over = self.add(square(0, 0, 100)), self.add(square(0, 0, 100))
        self.c.select([big, over])
        with mock.patch('vectordrive.ui.main_window.QMessageBox.information') as info:
            self.assertIsNone(self.win.text_in_shape(params=self.params()))
        info.assert_called_once()

    def test_an_open_shape_is_not_the_container(self):
        from vectordrive.core.geom import polyline
        big = self.add(square(0, 0, 50))
        line = self.add(Path([polyline([(-500, 0), (500, 500)], False)]))
        self.c.select([line, big])
        g = self.win.text_in_shape(params=self.params())
        self.assertIsInstance(g, Group)
        self.assertAlmostEqual(TF.region_child(g).path.bbox()[2], 50.0, places=6)


if __name__ == '__main__':
    unittest.main()
