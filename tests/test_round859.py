"""Round 859 : orientation de sortie (manuel de TE, page 819)."""
import math
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', os.path.join(tempfile.mkdtemp(), 'session'))
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')

from vectordrive.cam import model as M
from vectordrive.cam import post
from vectordrive.cam.model import Move, Toolpath

RECT = (0.0, 0.0, 100.0, 50.0)                            # une plaque de 100 x 50


def path(*moves):
    tp = Toolpath('op', 'outil', name='p')
    tp.moves = list(moves)
    return tp


def one_point(how, x=10.0, y=20.0, rect=RECT):
    tps, _o, _b = post.oriented([path(Move('feed', x, y, -1.0))], how, rect)
    m = tps[0].moves[0]
    return round(m.x, 6), round(m.y, 6)


class TestPoints(unittest.TestCase):
    """Le point (10, 20) d'une plaque de 100 x 50."""

    def test_initial(self):
        self.assertEqual(one_point('normal'), (10.0, 20.0))

    def test_mirror_on_y(self):
        self.assertEqual(one_point('miroir_y'), (90.0, 20.0))

    def test_mirror_on_x(self):
        self.assertEqual(one_point('miroir_x'), (10.0, 30.0))

    def test_half_turn(self):
        self.assertEqual(one_point('r180'), (90.0, 30.0))

    def test_quarter_clockwise(self):
        # le coin bas gauche passe en haut à gauche d'une plaque de 50 x 100
        self.assertEqual(one_point('r90h', 0.0, 0.0), (0.0, 100.0))
        self.assertEqual(one_point('r90h'), (20.0, 90.0))

    def test_quarter_anticlockwise(self):
        self.assertEqual(one_point('r90a', 0.0, 0.0), (50.0, 0.0))
        self.assertEqual(one_point('r90a'), (30.0, 10.0))

    def test_mirror_then_quarter_anticlockwise(self):
        self.assertEqual(one_point('miroir_r90a'), (30.0, 90.0))

    def test_mirror_then_quarter_clockwise(self):
        self.assertEqual(one_point('miroir_r90h'), (20.0, 10.0))

    def test_every_corner_stays_on_the_oriented_plate(self):
        for how in post.ORIENTATIONS:
            W, H = (50.0, 100.0) if how in post.QUARTERS else (100.0, 50.0)
            got = {one_point(how, x, y) for x in (0.0, 100.0) for y in (0.0, 50.0)}
            self.assertEqual(got, {(0.0, 0.0), (W, 0.0), (0.0, H), (W, H)}, how)

    def test_a_plate_away_from_zero(self):
        self.assertEqual(one_point('miroir_y', 15.0, 25.0, (5.0, 5.0, 105.0, 55.0)), (95.0, 25.0))
        self.assertEqual(one_point('r90h', 5.0, 5.0, (5.0, 5.0, 105.0, 55.0)), (5.0, 105.0))

    def test_unknown_or_no_plate(self):
        tp = path(Move('feed', 10.0, 20.0, -1.0))
        self.assertIs(post.oriented([tp], 'normal', RECT)[0][0], tp)
        self.assertIs(post.oriented([tp], 'de travers', RECT)[0][0], tp)
        self.assertIs(post.oriented([tp], 'r90h', None)[0][0], tp)
        self.assertIs(post.oriented([tp], 'r90h', (0.0, 0.0, 0.0, 0.0))[0][0], tp)

    def test_the_source_is_left_alone(self):
        tp = path(Move('feed', 10.0, 20.0, -1.0))
        post.oriented([tp], 'r180', RECT)
        self.assertEqual((tp.moves[0].x, tp.moves[0].y), (10.0, 20.0))

    def test_z_does_not_change(self):
        tps = post.oriented([path(Move('feed', 10.0, 20.0, -1.5))], 'r90h', RECT)[0]
        self.assertEqual(tps[0].moves[0].z, -1.5)


class TestArcs(unittest.TestCase):

    def arc(self, how, kind='arc_ccw'):
        start = Move('feed', 20.0, 10.0, -1.0)
        end = Move(kind, 10.0, 20.0, -1.0, 10.0, 10.0)        # quart de cercle autour de (10, 10)
        return post.oriented([path(start, end)], how, RECT)[0][0].moves

    def test_a_turn_keeps_the_direction(self):
        for how in ('r180', 'r90h', 'r90a'):
            self.assertEqual(self.arc(how)[1].kind, 'arc_ccw')

    def test_a_mirror_changes_it(self):
        for how in post.MIRRORS:
            self.assertEqual(self.arc(how)[1].kind, 'arc_cw')
            self.assertEqual(self.arc(how, 'arc_cw')[1].kind, 'arc_ccw')

    def test_the_centre_follows(self):
        for how in post.ORIENTATIONS:
            a, b = self.arc(how)
            ra = math.dist((a.x, a.y), (b.cx, b.cy))
            rb = math.dist((b.x, b.y), (b.cx, b.cy))
            self.assertAlmostEqual(ra, 10.0, places=6)
            self.assertAlmostEqual(rb, 10.0, places=6)

    def test_the_arc_stays_the_same_quarter(self):
        for how in post.ORIENTATIONS:
            a, b = self.arc(how)
            _r, _a0, sweep = M.arc_sweep((a.x, a.y), b)
            self.assertAlmostEqual(abs(sweep), math.pi / 2, places=6, msg=how)


class TestOrigin(unittest.TestCase):

    def test_the_centre_stays_the_centre(self):
        _t, o, _b = post.oriented([], 'r90h', RECT, (50.0, 25.0))
        self.assertEqual(o, (25.0, 50.0))

    def test_the_lower_left_corner_stays(self):
        _t, o, _b = post.oriented([], 'miroir_r90h', RECT, (0.0, 0.0))
        self.assertEqual(o, (0.0, 0.0))

    def test_without_origin(self):
        self.assertEqual(post.oriented([], 'r180', RECT)[1], (0.0, 0.0))

    def test_normal_keeps_it(self):
        self.assertIsNone(post.oriented([], 'normal', RECT)[1])

    def test_the_box(self):
        _t, _o, box = post.oriented([], 'r90a', RECT, None, (0.0, 0.0, -5.0, 100.0, 50.0, 0.0))
        self.assertEqual(box, (0.0, 0.0, -5.0, 50.0, 100.0, 0.0))

    def test_the_cycles_follow(self):
        tp = path(Move('feed', 10.0, 20.0, -1.0))
        tp.cycles = [{'x': 10.0, 'y': 20.0, 'kind': 'percage'}, 'autre']
        c = post.oriented([tp], 'miroir_y', RECT)[0][0].cycles
        self.assertEqual((c[0]['x'], c[0]['y']), (90.0, 20.0))
        self.assertEqual(c[1], 'autre')
        self.assertEqual(tp.cycles[0]['x'], 10.0)


class TestSetup(unittest.TestCase):

    def test_it_survives_the_file(self):
        from vectordrive.core.document import Document
        doc = Document()
        s = M.setup_of(doc)
        self.assertEqual(s.output_orient, 'normal')
        s.output_orient = 'r90h'
        M.store(doc, s)
        self.assertEqual(M.setup_of(doc).output_orient, 'r90h')


class TestPanel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()

    def test_the_labels_match(self):
        self.assertEqual(set(self.win.cam_panel.ORIENT_LABELS), set(post.ORIENTATIONS))

    def test_the_setting(self):
        p = self.win.cam_panel
        self.assertTrue(p.orient_dialog('r180'))
        self.assertEqual(p.setup().output_orient, 'r180')
        self.assertFalse(p.orient_dialog('de travers'))
        self.assertEqual(p.setup().output_orient, 'r180')
        p.orient_dialog('normal')

    def test_the_program_gets_the_oriented_paths(self):
        from PySide6.QtWidgets import QMessageBox
        from vectordrive.core.document import Plate
        p = self.win.cam_panel
        self.win.canvas.doc.plate = Plate(width=100.0, height=50.0)
        p.orient_dialog('r90h')
        tp = Toolpath('', '', name='x')
        tp.moves = [Move('feed', 10.0, 20.0, -1.0)]
        got = {}

        def fake(key, tps, s, **kw):
            got.update(tps=tps, **kw)
            return post.PostResult('', ['rien'], '.nc')
        with mock.patch.object(p, 'current_paths', lambda: [tp]), mock.patch.object(post, 'posts', lambda d='': {'x': ('x', None)}),                 mock.patch.object(post, 'run', fake), mock.patch.object(QMessageBox, 'warning'):
            p.post_process()
        p.orient_dialog('normal')
        m = got['tps'][0].moves[0]
        self.assertEqual((m.x, m.y), (20.0, 90.0))
        self.assertEqual(got['box_mm'][3:5], (50.0, 100.0))
        self.assertEqual((tp.moves[0].x, tp.moves[0].y), (10.0, 20.0))

    def test_the_window(self):
        from PySide6.QtWidgets import QInputDialog
        p = self.win.cam_panel
        with mock.patch.object(QInputDialog, 'getItem', return_value=(p.ORIENT_LABELS['r90a'], True)):
            self.assertTrue(p.orient_dialog())
        self.assertEqual(p.setup().output_orient, 'r90a')
        with mock.patch.object(QInputDialog, 'getItem', return_value=('', False)):
            self.assertFalse(p.orient_dialog())
        self.assertEqual(p.setup().output_orient, 'r90a')
        p.orient_dialog('normal')


if __name__ == '__main__':
    unittest.main()
