"""Round 796 : parcellisation."""
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

from vectordrive.cam import model, panels as PN
from vectordrive.cam.model import CamSetup, Move, Toolpath


def path(*moves, **kw):
    return Toolpath(op_id='o', tool_id='t', moves=list(moves), **kw)


def line(x0, y0, x1, y1, z=-1.0, safe=5.0):
    return path(Move('rapid', x0, y0, safe), Move('plunge', x0, y0, z), Move('feed', x1, y1, z), Move('rapid', x1, y1, safe))


def cut_length(tp):
    total = 0.0
    prev = None
    for m in tp.moves:
        if prev is not None and m.kind != 'rapid':
            if m.is_arc:
                total += model.arc_length(prev, m)
            else:
                total += math.hypot(m.x - prev[0], m.y - prev[1])
        prev = (m.x, m.y, m.z)
    return total


class TestPlan(unittest.TestCase):
    def test_count(self):
        self.assertEqual(PN.count(100, 100, 0), 1)
        self.assertEqual(PN.count(100.5, 100, 0), 2)
        self.assertEqual(PN.count(200, 100, 0), 2)
        self.assertEqual(PN.count(190, 100, 10), 2)
        self.assertEqual(PN.count(191, 100, 10), 3)

    def test_all_fits(self):
        got = PN.plan((0, 0, 50, 50), 100, 100)
        self.assertEqual(len(got), 1)
        self.assertEqual((got[0].x1, got[0].y1, got[0].x2, got[0].y2), (0, 0, 50, 50))

    def test_keep_full_size(self):
        got = PN.plan((0, 0, 50, 50), 100, 100, fit_last=False)
        self.assertEqual((got[0].x2, got[0].y2), (100, 100))

    def test_grid_covers(self):
        got = PN.plan((0, 0, 250, 150), 100, 100)
        self.assertEqual(len(got), 6)
        self.assertEqual(max(p.x2 for p in got), 250)
        self.assertEqual(max(p.y2 for p in got), 150)
        self.assertEqual({p.width for p in got}, {100, 50})

    def test_overlap(self):
        got = PN.plan((0, 0, 190, 50), 100, 100, overlap=10)
        self.assertEqual([(p.x1, p.x2) for p in got], [(0, 100), (90, 190)])

    def test_never_larger_than_asked(self):
        for p in PN.plan((-13, 7, 412, 333), 90, 70, overlap=5):
            self.assertLessEqual(p.width, 90 + 1e-9)
            self.assertLessEqual(p.height, 70 + 1e-9)

    def test_order_bottom_left_by_rows(self):
        got = PN.plan((0, 0, 200, 200), 100, 100, order='bl_rows')
        self.assertEqual([(p.x1, p.y1) for p in got], [(0, 0), (100, 0), (0, 100), (100, 100)])

    def test_order_bottom_left_by_columns(self):
        got = PN.plan((0, 0, 200, 200), 100, 100, order='bl_cols')
        self.assertEqual([(p.x1, p.y1) for p in got], [(0, 0), (0, 100), (100, 0), (100, 100)])

    def test_order_top_left(self):
        got = PN.plan((0, 0, 200, 200), 100, 100, order='tl_rows')
        self.assertEqual([(p.x1, p.y2) for p in got], [(0, 200), (100, 200), (0, 100), (100, 100)])

    def test_top_left_fits_the_last_row_downward(self):
        got = PN.plan((0, 0, 100, 150), 100, 100, order='tl_rows')
        self.assertEqual([(p.y1, p.y2) for p in got], [(50, 150), (0, 50)])

    def test_neighbours(self):
        for order in PN.ORDERS:
            got = PN.plan((0, 0, 200, 200), 100, 100, order=order)
            top_right = next(p for p in got if p.x2 == 200 and p.y2 == 200)
            bottom_left = next(p for p in got if p.x1 == 0 and p.y1 == 0)
            self.assertFalse(top_right.right or top_right.top, order)
            self.assertTrue(bottom_left.right and bottom_left.top, order)

    def test_ranks(self):
        self.assertEqual([p.rank for p in PN.plan((0, 0, 300, 100), 100, 100)], [1, 2, 3])

    def test_refused(self):
        with self.assertRaises(ValueError):
            PN.plan((0, 0, 10, 10), 0, 10)
        with self.assertRaises(ValueError):
            PN.plan((0, 0, 10, 10), 10, 10, overlap=10)
        with self.assertRaises(ValueError):
            PN.plan((0, 0, 10000, 10000), 10, 10)

    def test_nothing(self):
        self.assertEqual(PN.plan(None, 10, 10), [])

    def test_origin(self):
        p = PN.Panel(1, 1, 1, 10, 20, 30, 60)
        self.assertEqual(p.origin(), (10, 20))
        self.assertEqual(p.origin('top_left'), (10, 60))
        self.assertEqual(p.origin('center'), (20, 40))


class TestCut(unittest.TestCase):
    def setUp(self):
        self.a, self.b = PN.plan((0, 0, 200, 100), 100, 100)

    def test_line_over_two_panels(self):
        tp = line(10, 50, 190, 50)
        got = [PN.cut_path(tp, p) for p in (self.a, self.b)]
        self.assertAlmostEqual(cut_length(got[0]), 90)
        self.assertAlmostEqual(cut_length(got[1]), 90)

    def test_stays_in_the_panel(self):
        tp = line(10, 50, 190, 80)
        for p in (self.a, self.b):
            for m in PN.cut_path(tp, p).moves:
                self.assertTrue(p.x1 - 1e-9 <= m.x <= p.x2 + 1e-9 and p.y1 - 1e-9 <= m.y <= p.y2 + 1e-9)

    def test_entry_from_above_then_straight_down(self):
        got = PN.cut_path(line(10, 50, 190, 50), self.b).moves
        self.assertEqual((got[0].kind, got[0].x, got[0].z), ('rapid', 100, 5))
        self.assertEqual((got[1].kind, got[1].x, got[1].z), ('plunge', 100, -1))

    def test_every_exit_rises_in_rapid(self):
        got = PN.cut_path(line(10, 50, 190, 50), self.a).moves
        self.assertEqual((got[-1].kind, got[-1].x, got[-1].z), ('rapid', 100, 5))

    def test_z_follows_the_slope(self):
        tp = path(Move('rapid', 0, 50, 5), Move('feed', 200, 50, -2))
        feed = [m for m in PN.cut_path(tp, self.a).moves if m.kind == 'feed']
        self.assertAlmostEqual(feed[-1].x, 100)
        self.assertAlmostEqual(feed[-1].z, 1.5)

    def test_outside_gives_nothing(self):
        self.assertIsNone(PN.cut_path(line(110, 50, 190, 50), self.a))

    def test_rapids_are_not_cuts(self):
        tp = path(Move('rapid', 10, 50, 5), Move('rapid', 190, 50, 5), Move('plunge', 190, 50, -1), Move('feed', 150, 50, -1))
        self.assertIsNone(PN.cut_path(tp, self.a))

    def test_trace_on_the_frontier_has_one_owner(self):
        tp = line(100, 10, 100, 90)
        self.assertIsNone(PN.cut_path(tp, self.a))
        self.assertAlmostEqual(cut_length(PN.cut_path(tp, self.b)), 80)

    def test_hole_on_the_frontier_has_one_owner(self):
        tp = path(Move('rapid', 100, 50, 5), Move('plunge', 100, 50, -3), Move('rapid', 100, 50, 5))
        self.assertIsNone(PN.cut_path(tp, self.a))
        self.assertIsNotNone(PN.cut_path(tp, self.b))

    def test_top_frontier_has_one_owner(self):
        low, high = PN.plan((0, 0, 100, 200), 100, 100)
        tp = line(10, 100, 90, 100)
        self.assertIsNone(PN.cut_path(tp, low))
        self.assertIsNotNone(PN.cut_path(tp, high))

    def test_overlap_cuts_twice(self):
        a, b = PN.plan((0, 0, 190, 100), 100, 100, overlap=10)
        got = PN.split([line(92, 50, 98, 50)], [a, b], overlap=10)
        self.assertTrue(got[1] and got[2])
        self.assertAlmostEqual(cut_length(got[1][0]), 6)
        self.assertAlmostEqual(cut_length(got[2][0]), 6)

    def test_frontier_with_overlap_stays_in_both(self):
        a, b = PN.plan((0, 0, 190, 100), 100, 100, overlap=10)
        got = PN.split([line(95, 10, 95, 90)], [a, b], overlap=10)
        self.assertTrue(got[1] and got[2])

    def test_length_conserved(self):
        tp = line(3, 7, 397, 293)
        grid = PN.plan((0, 0, 400, 300), 90, 70)
        got = PN.split([tp], grid)
        total = sum(cut_length(x) for v in got.values() for x in v)
        self.assertAlmostEqual(total, math.hypot(394, 286), places=6)

    def test_original_untouched(self):
        tp = line(10, 50, 190, 50)
        before = list(tp.moves)
        uid = tp.uid
        c = PN.cut_path(tp, self.a)
        self.assertEqual(tp.moves, before)
        self.assertNotEqual(c.uid, uid)

    def test_two_passes_stay_separate(self):
        tp = path(Move('rapid', 10, 10, 5), Move('plunge', 10, 10, -1), Move('feed', 90, 10, -1), Move('rapid', 90, 10, 5),
                  Move('rapid', 10, 20, 5), Move('plunge', 10, 20, -1), Move('feed', 90, 20, -1), Move('rapid', 90, 20, 5))
        kinds = [m.kind for m in PN.cut_path(tp, self.a).moves]
        self.assertEqual(kinds.count('plunge'), 2)
        self.assertEqual(kinds.count('feed'), 2)

    def test_continuous_chain_not_broken(self):
        tp = path(Move('rapid', 10, 10, 5), Move('plunge', 10, 10, -1), Move('feed', 50, 10, -1), Move('feed', 50, 40, -1),
                  Move('feed', 10, 40, -1), Move('rapid', 10, 40, 5))
        self.assertEqual([m.kind for m in PN.cut_path(tp, self.a).moves].count('plunge'), 1)

    def test_goes_out_and_back(self):
        tp = path(Move('rapid', 50, 10, 5), Move('plunge', 50, 10, -1), Move('feed', 150, 10, -1), Move('feed', 150, 40, -1),
                  Move('feed', 50, 40, -1), Move('rapid', 50, 40, 5))
        got = PN.cut_path(tp, self.a)
        self.assertEqual([m.kind for m in got.moves].count('plunge'), 2)
        self.assertAlmostEqual(cut_length(got), 100)

    def test_several_toolpaths(self):
        got = PN.split([line(10, 50, 90, 50), line(110, 50, 190, 50)], [self.a, self.b])
        self.assertEqual((len(got[1]), len(got[2])), (1, 1))

    def test_empty_panel(self):
        got = PN.split([line(10, 50, 90, 50)], [self.a, self.b])
        self.assertEqual(got[2], [])

    def test_stop_kept_in_order(self):
        stop = path(cycles=[{'kind': 'instruction', 'text': 'x'}])
        one, two = line(10, 50, 90, 50), line(20, 50, 90, 50)
        got = PN.split([one, stop, two], [self.a, self.b])
        self.assertIs(got[1][1], stop)
        self.assertEqual(got[2], [])

    def test_read_program_feeds_dropped(self):
        tp = line(10, 50, 190, 50)
        tp.feeds = [100.0] * 4
        self.assertIsNone(PN.cut_path(tp, self.a).feeds)


class TestArcs(unittest.TestCase):
    def setUp(self):
        self.a, self.b = PN.plan((0, 0, 200, 100), 100, 100)

    def half(self, cx):
        return path(Move('rapid', cx - 20, 50, 5), Move('plunge', cx - 20, 50, -1),
                    Move('arc_cw', cx + 20, 50, -1, cx, 50), Move('rapid', cx + 20, 50, 5))

    def test_inside_stays_an_arc(self):
        got = PN.cut_path(self.half(50), self.a)
        self.assertEqual([m.kind for m in got.moves].count('arc_cw'), 1)

    def test_cut_arc_is_flattened(self):
        tp = self.half(100)
        got = PN.split([tp], [self.a, self.b])
        self.assertFalse(any(m.is_arc for v in got.values() for x in v for m in x.moves))
        total = sum(cut_length(x) for v in got.values() for x in v)
        self.assertAlmostEqual(total, math.pi * 20, delta=0.05)

    def test_arc_going_out_though_both_ends_inside(self):
        tp = path(Move('rapid', 95, 30, 5), Move('plunge', 95, 30, -1), Move('arc_ccw', 95, 70, -1, 95, 50), Move('rapid', 95, 70, 5))
        got = PN.cut_path(tp, self.a)
        self.assertFalse(any(m.is_arc for m in got.moves))
        for m in got.moves:
            self.assertLessEqual(m.x, 100 + 1e-6)


class TestSafeHeight(unittest.TestCase):
    def test_from_the_rapids(self):
        self.assertEqual(PN.safe_height(line(0, 0, 1, 0, safe=7)), 7)

    def test_no_rapid(self):
        tp = path(Move('feed', 0, 0, -1), Move('feed', 1, 0, -1))
        self.assertEqual(PN.safe_height(tp), -1 + PN.SAFE_MARGIN)

    def test_low_links_do_not_count(self):
        tp = line(0, 0, 1, 0, safe=0.2)
        tp.unfaced = line(0, 0, 1, 0, safe=9).moves
        self.assertEqual(PN.safe_height(tp), 9)
        got = PN.cut_path(tp, PN.Panel(1, 1, 1, -5, -5, 5, 5))
        self.assertEqual(got.moves[0].z, 9)
        self.assertIsNone(got.unfaced)


class TestCycles(unittest.TestCase):
    def setUp(self):
        self.a, self.b = PN.plan((0, 0, 200, 100), 100, 100)

    def test_go_with_their_panel(self):
        tp = path(cycles=[{'kind': 'drill', 'x': 10.0, 'y': 10.0, 'depth': 3}, {'kind': 'drill', 'x': 150.0, 'y': 10.0, 'depth': 3}])
        got = PN.split([tp], [self.a, self.b])
        self.assertEqual([c['x'] for c in got[1][0].cycles], [10.0])
        self.assertEqual([c['x'] for c in got[2][0].cycles], [150.0])

    def test_on_the_frontier_has_one_owner(self):
        tp = path(cycles=[{'kind': 'drill', 'x': 100.0, 'y': 10.0, 'depth': 3}])
        got = PN.split([tp], [self.a, self.b])
        self.assertEqual(got[1], [])
        self.assertEqual(len(got[2]), 1)

    def test_counted_in_the_bounds(self):
        tp = path(cycles=[{'kind': 'drill', 'x': 7.0, 'y': 8.0, 'depth': 3}, {'kind': 'instruction', 'x': 900.0, 'y': 900.0}])
        self.assertEqual(PN.path_bounds([tp]), (7.0, 8.0, 7.0, 8.0))


class TestZone(unittest.TestCase):
    def test_bounds_skip_rapids(self):
        tp = path(Move('rapid', -500, -500, 5), Move('rapid', 10, 10, 5), Move('plunge', 10, 10, -1), Move('feed', 30, 40, -1),
                  Move('rapid', 900, 900, 5))
        self.assertEqual(PN.path_bounds([tp]), (10, 10, 30, 40))

    def test_bounds_see_the_belly_of_an_arc(self):
        tp = path(Move('rapid', -10, 0, 5), Move('plunge', -10, 0, -1), Move('arc_cw', 10, 0, -1, 0, 0))
        box = PN.path_bounds([tp])
        self.assertAlmostEqual(box[3], 10, delta=0.1)

    def test_bounds_empty(self):
        self.assertIsNone(PN.path_bounds([path()]))

    def test_occupied(self):
        grid = PN.plan((0, 0, 300, 100), 100, 100)
        kept = PN.occupied(grid, PN.segments([line(10, 50, 90, 50), line(210, 50, 290, 50)]))
        self.assertEqual([p.rank for p in kept], [1, 3])

    def test_occupied_nothing(self):
        self.assertEqual(PN.occupied(PN.plan((0, 0, 100, 100), 100, 100), PN.segments([path()])), [])

    def test_filled_renumbers(self):
        grid = PN.plan((0, 0, 300, 100), 100, 100)
        kept, cut = PN.filled(grid, PN.split([line(210, 50, 290, 50)], grid))
        self.assertEqual([p.rank for p in kept], [1])
        self.assertEqual(kept[0].x1, 200)
        self.assertEqual(len(cut[1]), 1)

    def test_plate_move(self):
        a, b = PN.plan((0, 0, 200, 100), 100, 100)
        self.assertEqual(PN.plate_move(a, b), (-100, 0))
        self.assertEqual(PN.plate_move(b, a), (100, 0))


class TestReport(unittest.TestCase):
    def make(self, **kw):
        grid = PN.plan((0, 0, 200, 100), 100, 100)
        tp = line(10, 50, 190, 50)
        tp.name = 'Gravure'
        setup = CamSetup(operations=[model.Operation(id='o', name='g', feed=600)])
        return PN.report(grid, PN.split([tp], grid), setup, (0, 0, 200, 100), 'essai', **kw)

    def test_lists_the_panels(self):
        text = self.make()
        self.assertIn('2 PANNEAUX', text)
        self.assertIn('Panneau 1/2', text)
        self.assertIn('essai_P02', text)
        self.assertIn('Gravure', text)

    def test_plate_move(self):
        self.assertIn('X -100,00 / Y 0,00', self.make())

    def test_given_names(self):
        self.assertIn('a.mcr', self.make(names={1: 'a.mcr'}))

    def test_plain_ascii(self):
        self.assertTrue(self.make(when='2026-11-06 12:00').isascii())

    def test_total(self):
        self.assertIn('Temps estime total', self.make())


class TestSetup(unittest.TestCase):
    def test_kept_with_the_drawing(self):
        s = CamSetup(panels={'width': 120.0})
        self.assertEqual(CamSetup.from_dict(s.to_dict()).panels['width'], 120.0)

    def test_old_file(self):
        self.assertEqual(CamSetup.from_dict({}).panels, {})

    def test_damaged_value(self):
        self.assertEqual(CamSetup.from_dict({'panels': 3}).panels, {})


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def dialog(self, tps=None, plate=None, stored=None):
        from vectordrive.ui.panels_dialog import PanelsDialog
        d = PanelsDialog(None, tps if tps is not None else [line(10, 50, 390, 50), line(10, 150, 30, 150)], plate, stored)
        self.addCleanup(d.deleteLater)
        return d

    def test_opens_with_half_the_zone(self):
        d = self.dialog()
        self.assertEqual(d.width_box.value(), 190)
        self.assertTrue(d.panels)

    def test_stored_values(self):
        d = self.dialog(stored={'width': 123.0, 'height': 77.0, 'overlap': 2.0, 'order': 'tl_cols', 'origin': 'center', 'fit_last': False})
        v = d.values()
        self.assertEqual((v['width'], v['height'], v['overlap'], v['order'], v['origin'], v['fit_last']),
                         (123.0, 77.0, 2.0, 'tl_cols', 'center', False))

    def test_empty_panels_dropped(self):
        d = self.dialog()
        d.width_box.setValue(100)
        d.height_box.setValue(50)
        self.assertLess(len(d.panels), 12)
        self.assertGreater(d.dropped, 0)
        self.assertIn(str(d.dropped), d.info.text())

    def test_impossible_sizes(self):
        d = self.dialog()
        d.overlap_box.setValue(1000)
        self.assertEqual(d.panels, [])
        self.assertFalse(d.write_button.isEnabled())

    def test_order_buttons(self):
        d = self.dialog(stored={'width': 100.0, 'height': 200.0})
        first = d.panels[0]
        last = d.panels[-1]
        d.listing.setCurrentRow(len(d.panels) - 1)
        d.to_first()
        self.assertEqual((d.panels[0].x1, d.panels[0].rank), (last.x1, 1))
        self.assertEqual(d.panels[1].x1, first.x1)
        d.later()
        self.assertEqual(d.panels[1].x1, last.x1)
        d.earlier()
        self.assertEqual(d.panels[0].x1, last.x1)
        d.to_last()
        self.assertEqual(d.panels[-1].x1, last.x1)

    def test_remove_and_rebuild(self):
        d = self.dialog(stored={'width': 100.0, 'height': 200.0})
        n = len(d.panels)
        d.listing.setCurrentRow(0)
        d.remove()
        self.assertEqual(len(d.panels), n - 1)
        self.assertEqual(d.panels[0].rank, 1)
        d.rebuild()
        self.assertEqual(len(d.panels), n)

    def test_plate_zone(self):
        d = self.dialog(plate=(0.0, 0.0, 1000.0, 1000.0))
        d.zone_box.setCurrentIndex(d.zone_box.findData('plate'))
        self.assertEqual(d.bounds(), (0.0, 0.0, 1000.0, 1000.0))

    def test_no_plate_no_plate_zone(self):
        self.assertEqual(self.dialog().zone_box.findData('plate'), -1)

    def test_click_picks(self):
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        d = self.dialog(stored={'width': 100.0, 'height': 200.0})
        d.resize(1000, 700)
        d.show()
        self.app.processEvents()
        v = d.preview
        k, ox, oy = v._view()
        p = d.panels[-1]
        at = QPoint(int(ox + (p.x1 + p.x2) / 2 * k), int(oy - (p.y1 + p.y2) / 2 * k))
        QTest.mouseClick(v, Qt.MouseButton.LeftButton, pos=at)
        self.assertEqual(d.listing.currentRow(), len(d.panels) - 1)
        v.grab()
        d.close()


class TestWrite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()

    def cam(self):
        return self.w.cam_panel

    def test_action(self):
        self.assertIn('cam_panels', self.w.A)
        self.assertTrue(callable(getattr(self.cam(), 'post_panels', None)))

    def test_nothing_to_cut(self):
        import vectordrive.ui.cam_panel as CP
        cam = self.cam()
        with mock.patch.object(CP.QMessageBox, 'information') as box, mock.patch.object(cam, 'current_paths', return_value=[]):
            cam.post_panels()
        box.assert_called_once()

    def write(self, tps, panels, values, bounds):
        from tests._posts import registered
        cam = self.cam()
        with tempfile.TemporaryDirectory() as d, registered():
            from vectordrive.cam import post
            key = next(iter(post.posts('')))
            cam.setup().post = key
            with mock.patch('vectordrive.ui.reveal.done_message', return_value=None):
                got = cam.write_panels(key, tps, panels, values, os.path.join(d, 'job.nc'), bounds)
            return [(f.name, f.read_text(encoding='utf-8', errors='replace')) for f in got]

    def test_one_program_per_panel(self):
        grid = PN.plan((0, 0, 200, 100), 100, 100)
        got = self.write([line(10, 50, 190, 50)], grid, {'overlap': 0.0, 'origin': 'bottom_left'}, (0, 0, 200, 100))
        names = [n for n, _t in got]
        self.assertEqual(len(names), 3)
        self.assertTrue(names[0].startswith('job_P01'))
        self.assertTrue(names[1].startswith('job_P02'))
        self.assertEqual(names[2], 'job_panneaux.txt')
        self.assertIn('Panneau 2/2', got[2][1])

    def test_empty_panels_not_written(self):
        grid = PN.plan((0, 0, 300, 100), 100, 100)
        got = self.write([line(210, 50, 290, 50)], grid, {'overlap': 0.0, 'origin': 'bottom_left'}, (0, 0, 300, 100))
        self.assertEqual(len(got), 2)
        self.assertTrue(got[0][0].startswith('job_P01'))

    def test_each_program_starts_at_its_own_zero(self):
        grid = PN.plan((0, 0, 200, 100), 100, 100)
        got = self.write([line(110, 50, 190, 50)], grid, {'overlap': 0.0, 'origin': 'bottom_left'}, (0, 0, 200, 100))
        text = got[0][1]
        self.assertNotIn('190', text)
        self.assertRegex(text, r'X\s*90')

    def test_nothing_falls_in(self):
        import vectordrive.ui.cam_panel as CP
        grid = PN.plan((500, 500, 600, 600), 100, 100)
        with mock.patch.object(CP.QMessageBox, 'information') as box:
            self.assertEqual(self.write([line(10, 50, 90, 50)], grid, {}, (0, 0, 100, 100)), [])
        box.assert_called_once()


if __name__ == '__main__':
    unittest.main()
