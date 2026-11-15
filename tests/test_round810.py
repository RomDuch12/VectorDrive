"""Round 810 : restant de plaque."""
import math
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication
from shapely.geometry import Polygon

from vectordrive.core import pathops
from vectordrive.core import remnant as RE
from vectordrive.core.document import Group, Layer, Plate, Shape, Text
from vectordrive.core.geom import Path, circle, polyline, rect

app = QApplication.instance() or QApplication([])
PLATE = Plate(width=200.0, height=100.0)


def box(x, y, w, h=None):
    return Shape(path=Path([rect(x, y, w, h if h is not None else w)]))


def disc(x, y, r):
    return Shape(path=Path([circle((x, y), r)]))


def spec(mode='standard', gap=0.0, min_area=0.0, min_side=0.0):
    return RE.RemnantSpec(mode=mode, gap=gap, min_area=min_area, min_side=min_side)


def poly(path):
    """Le tracé rendu en polygone shapely, trous compris."""
    rings = [c.flatten(0.01) for c in path.contours]
    return Polygon(rings[0], rings[1:]).buffer(0)


class LargestRect(unittest.TestCase):
    def test_nothing_in_the_way(self):
        self.assertEqual(RE.largest_rect(0, 0, 200, 100, []), (0, 0, 200, 100))

    def test_box_in_a_corner(self):
        self.assertEqual(RE.largest_rect(0, 0, 200, 100, [(0, 0, 50, 50)]), (50, 0, 200, 100))

    def test_box_in_the_middle(self):
        got = RE.largest_rect(0, 0, 200, 100, [(90, 40, 110, 60)])
        self.assertEqual((got[2] - got[0]) * (got[3] - got[1]), 9000)

    def test_two_boxes(self):
        got = RE.largest_rect(0, 0, 100, 100, [(0, 0, 40, 40), (60, 60, 100, 100)])
        self.assertAlmostEqual((got[2] - got[0]) * (got[3] - got[1]), 3600.0)

    def test_box_past_the_edge(self):
        self.assertEqual(RE.largest_rect(0, 0, 200, 100, [(150, -50, 400, 400)]), (0, 0, 150, 100))

    def test_box_outside(self):
        self.assertEqual(RE.largest_rect(0, 0, 200, 100, [(300, 0, 400, 50)]), (0, 0, 200, 100))

    def test_all_taken(self):
        self.assertIsNone(RE.largest_rect(0, 0, 200, 100, [(0, 0, 200, 100)]))

    def test_too_narrow(self):
        boxes = [(0, 5, 200, 100)]
        self.assertEqual(RE.largest_rect(0, 0, 200, 100, boxes), (0, 0, 200, 5))
        self.assertIsNone(RE.largest_rect(0, 0, 200, 100, boxes, 10.0))

    def test_min_side_picks_a_smaller_one(self):
        # le plus grand est une bande de 5 × 200 ; la seule assez large fait 20 × 20
        boxes = [(0, 5, 180, 100), (180, 20, 200, 100)]
        self.assertEqual(RE.largest_rect(0, 0, 200, 100, boxes, 10.0), (180, 0, 200, 20))

    def test_many_boxes_stay_free(self):
        boxes = [(i * 2.0, j * 2.0, i * 2.0 + 1, j * 2.0 + 1) for i in range(500) for j in range(3)]
        got = RE.largest_rect(0, 0, 1000, 100, boxes)
        self.assertEqual(got[1], 5.0)
        for b in boxes[:50]:
            self.assertTrue(b[3] <= got[1] + 1e-9)


class Modes(unittest.TestCase):
    def test_simple(self):
        got = RE.remnant(PLATE, [box(0, 0, 50)], spec('simple'))
        self.assertAlmostEqual(got.area, 150 * 100, places=6)
        self.assertAlmostEqual(got.share, 0.75, places=6)

    def test_standard_goes_around_the_boxes(self):
        got = RE.remnant(PLATE, [disc(25, 25, 25)], spec('standard'))
        self.assertAlmostEqual(got.area, 20000 - 2500, places=3)
        self.assertEqual(len(got.path.contours), 1)

    def test_optimised_follows_the_shape(self):
        got = RE.remnant(PLATE, [disc(40, 40, 25)], spec('optimise'))
        self.assertAlmostEqual(got.area, 20000 - math.pi * 625, delta=1.0)

    def test_a_corner_cut_off_by_an_object_is_another_part(self):
        got = RE.remnant(PLATE, [disc(25, 25, 25)], spec('optimise'))
        self.assertEqual(got.others, 1)
        self.assertAlmostEqual(got.area, 20000 - math.pi * 625 - (625 - math.pi * 625 / 4), delta=1.0)

    def test_modes_grow_in_order(self):
        items = [disc(30, 30, 20), disc(30, 70, 20)]
        a, b, c = (RE.remnant(PLATE, items, spec(m)).area for m in ('simple', 'standard', 'optimise'))
        self.assertLessEqual(a, b + 1e-6)
        self.assertLess(b, c)

    def test_gap(self):
        got = RE.remnant(PLATE, [box(0, 0, 50)], spec('standard', gap=2.0))
        self.assertAlmostEqual(got.area, 20000 - 52 * 52, places=3)
        got = RE.remnant(PLATE, [box(0, 0, 50)], spec('simple', gap=2.0))
        self.assertAlmostEqual(got.area, 148 * 100, places=3)
        got = RE.remnant(PLATE, [disc(25, 25, 20)], spec('optimise', gap=2.0))
        self.assertAlmostEqual(got.area, 20000 - math.pi * 22 * 22, delta=1.0)

    def test_object_in_the_middle_leaves_a_hole(self):
        got = RE.remnant(PLATE, [box(90, 40, 20)], spec('standard'))
        self.assertEqual(len(got.path.contours), 2)
        self.assertAlmostEqual(pathops.area(pathops.normalize(got.path)), 20000 - 400, places=3)

    def test_inner_holes_of_an_object_fall_with_it(self):
        ring = Shape(path=Path([rect(50, 20, 60, 60), rect(60, 30, 40, 40)]))
        got = RE.remnant(PLATE, [ring], spec('optimise'))
        self.assertAlmostEqual(got.area, 20000 - 3600, places=3)

    def test_nothing_on_the_plate(self):
        got = RE.remnant(PLATE, [], spec('standard'))
        self.assertAlmostEqual(got.area, 20000.0, places=6)
        self.assertEqual(got.others, 0)

    def test_object_off_the_plate_changes_nothing(self):
        got = RE.remnant(PLATE, [box(500, 500, 10)], spec('optimise'))
        self.assertAlmostEqual(got.area, 20000.0, places=3)

    def test_unknown_mode(self):
        with self.assertRaises(ValueError):
            RE.remnant(PLATE, [], spec('autre'))

    def test_every_mode_stays_on_the_plate_and_off_the_objects(self):
        items = [disc(30, 30, 20), box(100, 10, 40, 30), box(60, 70, 80, 20)]
        round_plate = Plate(width=200.0, height=100.0, corner_radius=15.0)
        for plate in (PLATE, round_plate):
            board = RE._plate_shape(plate)
            for mode in RE.MODES:
                got = RE.remnant(plate, items, spec(mode, gap=1.0, min_side=10.0))
                zone = poly(got.path)
                self.assertLess(zone.difference(board).area, 1e-3, mode)
                for it in items:
                    self.assertLess(zone.intersection(RE._footprint(it, 1.0)).area, 0.05, mode)

    def test_group_text_and_open_curve_count(self):
        group = Group(children=[box(0, 0, 20), box(30, 0, 20)])
        got = RE.remnant(PLATE, [group], spec('optimise'))
        self.assertAlmostEqual(got.area, 20000 - 800, places=3)
        line = Shape(path=Path([polyline([(0, 50), (200, 50)], False)]))
        got = RE.remnant(PLATE, [line], spec('optimise', gap=1.0))
        self.assertAlmostEqual(got.area, 10000 - 200, delta=2.0)
        self.assertEqual(got.others, 1)
        text = Text(text='HHHH', font='Arial', size=20.0)
        got = RE.remnant(PLATE, [text], spec('standard'))
        self.assertLess(got.area, 20000.0)


class Criteria(unittest.TestCase):
    def test_min_area(self):
        items = [box(0, 0, 200, 90)]
        with self.assertRaises(RE.NoRemnant):
            RE.remnant(PLATE, items, spec('standard', min_area=3000.0))
        self.assertAlmostEqual(RE.remnant(PLATE, items, spec('standard', min_area=1000.0)).area, 2000.0, places=3)

    def test_min_side(self):
        for mode in RE.MODES:
            items = [box(0, 0, 200, 95)]
            with self.assertRaises(RE.NoRemnant, msg=mode):
                RE.remnant(PLATE, items, spec(mode, min_side=10.0))

    def test_all_covered(self):
        for mode in RE.MODES:
            with self.assertRaises(RE.NoRemnant, msg=mode):
                RE.remnant(PLATE, [box(-5, -5, 300)], spec(mode))

    def test_narrow_gaps_do_not_count(self):
        items = [box(50, 0, 40, 100), box(95, 0, 40, 100)]
        got = RE.remnant(PLATE, items, spec('standard', min_side=10.0))
        self.assertAlmostEqual(got.area, 65 * 100, places=3)            # le côté droit, pas la fente de 5
        self.assertEqual(got.others, 1)
        self.assertAlmostEqual(got.path.bbox()[0], 135.0, places=6)

    def test_corners_stay_sharp(self):
        got = RE.remnant(PLATE, [box(0, 0, 50)], spec('standard', min_side=20.0))
        self.assertAlmostEqual(got.area, 20000 - 2500, places=3)
        self.assertEqual(len(got.path.contours[0].segments), 6)


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
        self.doc = self.win.canvas.doc
        self.doc.layers[:] = [Layer(name='Plan 1')]
        self.doc.active = self.doc.layers[0].id
        self.doc.plate = Plate(width=200.0, height=100.0)
        self.win.canvas.selection = []
        self.win._undo.clear()
        self.library = tempfile.mkdtemp()
        patcher = mock.patch.dict(os.environ, {'VECTORDRIVE_BIBLIOTHEQUE': self.library})
        patcher.start()
        self.addCleanup(patcher.stop)

    def add(self, shape):
        self.doc.layers[0].items.append(shape)
        return shape

    def test_makes_a_plane_with_a_selected_shape(self):
        it = self.add(box(0, 0, 50))
        self.win.canvas.select([it])
        s = self.win.plate_remnant({'mode': 'standard', 'gap': 0.0})
        self.assertEqual(self.doc.layers[-1].name, 'Restant de plaque')
        self.assertEqual(self.doc.layers[-1].items, [s])
        self.assertEqual(self.win.canvas.selection, [s])
        self.assertEqual(self.doc.layers[-1].tool, s.tool)
        self.assertIn(it, self.doc.layers[0].items)

    def test_active_plane_without_selection(self):
        self.add(box(0, 0, 50))
        s = self.win.plate_remnant({'mode': 'standard', 'gap': 0.0})
        self.assertAlmostEqual(pathops.area(pathops.normalize(s.path)), 17500.0, places=3)

    def test_second_one_gets_its_own_plane(self):
        self.add(box(0, 0, 50))
        self.win.plate_remnant({'gap': 0.0})
        self.win.canvas.selection = []
        self.doc.active = self.doc.layers[0].id
        self.win.plate_remnant({'gap': 0.0})
        self.assertEqual(self.doc.layers[-1].name, 'Restant de plaque 2')

    def test_undo(self):
        self.add(box(0, 0, 50))
        self.win.plate_remnant({'gap': 0.0})
        self.win.undo()
        self.assertEqual(len(self.win.canvas.doc.layers), 1)

    def test_no_plate(self):
        self.doc.plate = None
        with mock.patch('vectordrive.ui.main_window.QMessageBox.information') as info:
            self.assertIsNone(self.win.plate_remnant({'gap': 0.0}))
        info.assert_called_once()

    def test_nothing_fits_says_so(self):
        self.add(box(-5, -5, 300))
        with mock.patch('vectordrive.ui.main_window.QMessageBox.information') as info:
            self.assertIsNone(self.win.plate_remnant({'gap': 0.0}))
        info.assert_called_once()
        self.assertEqual(len(self.doc.layers), 1)

    def test_kept_in_the_library(self):
        from vectordrive.io import smb
        self.add(box(0, 0, 50))
        self.win.plate_remnant({'gap': 0.0, 'to_library': True})
        self.win.canvas.selection = []
        self.doc.active = self.doc.layers[0].id
        self.win.plate_remnant({'gap': 0.0, 'to_library': True})
        folder = pathlib.Path(self.library) / 'Restants de plaque'
        self.assertEqual(sorted(p.name for p in folder.iterdir()), ['Plate0001.smb', 'Plate0002.smb'])
        back = smb.read(folder / 'Plate0001.smb')
        b = next(iter(back.iter_items())).bbox()
        self.assertAlmostEqual(b[2] - b[0], 200.0, places=2)

    def test_library_not_written_by_default(self):
        self.add(box(0, 0, 50))
        self.win.plate_remnant({'gap': 0.0})
        self.assertFalse((pathlib.Path(self.library) / 'Restants de plaque').exists())

    def test_library_error_is_said_not_raised(self):
        self.add(box(0, 0, 50))
        with mock.patch('vectordrive.io.smb.write', side_effect=OSError('refus')):
            s = self.win.plate_remnant({'gap': 0.0, 'to_library': True})
        self.assertIsNotNone(s)

    def test_copies_go_in_the_remnant(self):
        it = self.add(box(0, 0, 150, 100))
        self.win.canvas.select([it])
        remnant = self.win.plate_remnant({'mode': 'simple', 'gap': 0.0})
        small = self.add(box(0, 0, 10))
        self.win.canvas.select([small, remnant])
        res = self.win.copy_into_shape({'count': 4, 'margin': 0.0, 'gap': 1.0})
        self.assertEqual(len(res.placed), 4)
        for s in self.win.canvas.selection:
            self.assertGreaterEqual(s.bbox()[0], 150.0 - 1e-6)


if __name__ == '__main__':
    unittest.main()
