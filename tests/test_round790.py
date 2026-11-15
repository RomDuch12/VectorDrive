"""Round 790 : les réglages par lettre sur un texte en arc ou sur une courbe."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from vectordrive.core import text as TX
from vectordrive.core.document import Text
from vectordrive.core.geom import Affine, Contour, Line, Path

FONT = 'VD Trait'
LINE = Contour([Line((0, 0), (300, 0))], False)
UP = Contour([Line((0, 0), (0, 300))], False)


def nodes(path):
    return [tuple(round(v, 6) for v in p) for c in path.contours for s in c.segments for p in (s.start, s.end)]


def straight(text, fx=None, **kw):
    """Le même texte, droit, sans crénage : `on_path` n'en met pas."""
    return TX.layout(text, FONT, 10.0, kerning=False, fx=fx, **kw)


def curved(text, fx=None, contour=LINE, **kw):
    return TX.on_path(text, FONT, 10.0, contour, fx=fx, **kw)


def make(text='HHHH', **extra):
    t = Text(text=text, font=FONT, size=10.0)
    t.extra.update(extra)
    return t


class TestOnPath(unittest.TestCase):
    def test_nothing_set_changes_nothing(self):
        self.assertEqual(nodes(curved('ABC', {})), nodes(curved('ABC')))
        self.assertEqual(nodes(curved('ABC', None)), nodes(curved('ABC')))

    def test_same_as_straight_text_on_a_straight_line(self):
        for fx in ({1: {'kern': 40.0}}, {1: {'dx': 30.0}}, {1: {'dy': 25.0}}, {1: {'h': 150.0}}, {1: {'w': 60.0}},
                   {1: {'rot': 30.0}}, {0: {'h': 200.0, 'w': 50.0, 'rot': 45.0, 'dx': 10.0, 'dy': -10.0, 'kern': 5.0},
                                        2: {'rot': -20.0}}):
            got, want = curved('HAH', fx).bbox(), straight('HAH', fx).bbox()
            for a, b in zip(got, want):
                self.assertAlmostEqual(a, b, places=6, msg=str(fx))

    def test_kern_pushes_what_follows(self):
        a = curved('HHH').bbox()
        b = curved('HHH', {1: {'kern': 50.0}}).bbox()
        self.assertAlmostEqual(b[2] - a[2], 5.0, places=6)

    def test_dx_moves_only_the_letter(self):
        a = curved('HHH').bbox()
        b = curved('HHH', {2: {'dx': 50.0}}).bbox()
        self.assertAlmostEqual(b[2] - a[2], 5.0, places=6)
        c = curved('HHH', {0: {'dx': 10.0}}).bbox()
        self.assertAlmostEqual(c[2], a[2], places=6)     # les suivantes restent

    def test_dy_goes_away_from_the_curve(self):
        a = curved('H', contour=UP).bbox()
        b = curved('H', {0: {'dy': 100.0}}, contour=UP).bbox()
        self.assertAlmostEqual(b[0] - a[0], -10.0, places=6)     # la courbe monte : « au-dessus » est à gauche
        self.assertAlmostEqual(b[1], a[1], places=6)

    def test_height_scales_the_letter(self):
        a = curved('H').bbox()
        b = curved('H', {0: {'h': 200.0}}).bbox()
        self.assertAlmostEqual((b[3] - b[1]) / (a[3] - a[1]), 2.0, places=6)

    def test_width_scales_only_across(self):
        a = curved('H').bbox()
        b = curved('H', {0: {'w': 50.0}}).bbox()
        self.assertAlmostEqual((b[2] - b[0]) / (a[2] - a[0]), 0.5, places=6)
        self.assertAlmostEqual(b[3] - b[1], a[3] - a[1], places=6)

    def test_half_turn_keeps_the_size_and_the_height_on_the_line(self):
        a = curved('H').bbox()
        b = curved('H', {0: {'rot': 180.0}}).bbox()
        self.assertAlmostEqual(b[3] - b[1], a[3] - a[1], places=6)
        self.assertAlmostEqual(b[2] - b[0], a[2] - a[0], places=6)
        self.assertAlmostEqual(b[1], a[1], places=6)     # autour du milieu de sa hauteur : elle reste sur sa ligne

    def test_centred_text_counts_the_settings(self):
        wide = curved('HHH', {1: {'w': 300.0}}, align='center').bbox()
        self.assertAlmostEqual((wide[0] + wide[2]) / 2, 150.0, delta=1.5)

    def test_right_aligned_text_counts_the_settings(self):
        got = curved('HHH', {1: {'kern': 100.0}}, align='right').bbox()
        self.assertLessEqual(got[2], 300.0 + 1e-6)
        self.assertGreater(got[2], 297.0)

    def test_on_a_circle_the_letter_stays_tangent(self):
        from vectordrive.core.geom import arc
        circle = arc((0, 0), 50.0, 270.0, -360.0)
        plain = TX.on_path('H', FONT, 10.0, circle, align='center')
        moved = TX.on_path('H', FONT, 10.0, circle, align='center', fx={0: {'dy': 50.0}})
        rp = max(math.hypot(*s.start) for c in plain.contours for s in c.segments)
        rm = max(math.hypot(*s.start) for c in moved.contours for s in c.segments)
        self.assertAlmostEqual(rm - rp, 5.0, delta=0.2)


class TestOutline(unittest.TestCase):
    def test_on_path_item(self):
        t = make('HHH', on_path=LINE)
        plain = TX.outline_for(t).bbox()
        TX.set_char_fx(t, {1: {'kern': 50.0}})
        self.assertAlmostEqual(TX.outline_for(t).bbox()[2] - plain[2], 5.0, places=6)

    def test_arc_item(self):
        t = make('HHH', arc={'center': (0, 0), 'radius': 40.0})
        plain = TX.outline_for(t).bbox()
        TX.set_char_fx(t, {1: {'h': 300.0}})
        self.assertGreater(TX.outline_for(t).bbox()[3], plain[3] + 5.0)

    def test_arc_warp_item_all_modes(self):
        for mode in ('simple', 'radial', 'incline'):
            t = make('HHH', arc_warp={'center': (0, 0), 'radius': 40.0, 'mode': mode})
            plain = TX.outline_for(t).bbox()
            TX.set_char_fx(t, {1: {'h': 300.0}})
            self.assertGreater(TX.outline_for(t).bbox()[3], plain[3] + 5.0, mode)

    def test_arc_warp_only_first_line_counts(self):
        t = make('HH\nHH', arc_warp={'center': (0, 0), 'radius': 40.0})
        plain = nodes(TX.outline_for(t))
        TX.set_char_fx(t, {3: {'h': 300.0}})
        self.assertEqual(nodes(TX.outline_for(t)), plain)

    def test_text_change_keeps_them_on_their_letters(self):
        t = make('HHH', on_path=LINE)
        TX.set_char_fx(t, {2: {'h': 200.0}})
        t.text = 'AHHH'
        TX.outline_for(t)
        self.assertEqual(TX.char_fx(t), {3: {'h': 200.0}})
        self.assertEqual(t.extra['chars_text'], 'AHHH')

    def test_springs_do_not_shift_them(self):
        spring = TX.SPRING
        t = make('H' + spring + 'H', on_path=LINE)
        TX.set_char_fx(t, {2: {'h': 200.0}})             # le second H
        other = make('HH', on_path=LINE)
        TX.set_char_fx(other, {1: {'h': 200.0}})
        self.assertEqual(nodes(TX.outline_for(t)), nodes(TX.outline_for(other)))

    def test_no_settings_same_as_before(self):
        t = make('HAH', arc={'center': (0, 0), 'radius': 40.0})
        self.assertEqual(nodes(TX.outline_for(t)), nodes(TX.on_path('HAH', FONT, 10.0, TX.arc_contour((0, 0), 40.0, 10.0), align='left')))

    def test_item_transform_still_applies_to_straight_text(self):
        t = make('H')
        t.matrix = Affine.translation(100, 0)
        TX.set_char_fx(t, {0: {'kern': 10.0}})
        self.assertGreater(TX.outline_for(t).bbox()[0], 99.0)


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.t = make('HHHH', on_path=LINE)
        self.t.outline = TX.outline_for(self.t)
        self.w.canvas.doc.layers[0].items[:] = [self.t]
        self.w.canvas.invalidate()
        self.w.canvas.select([self.t])

    def tearDown(self):
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()

    def test_dialog_changes_the_curved_text_and_undoes(self):
        before = self.t.outline.bbox()
        d = self.w.text_letters_dialog(exec_dialog=False)
        self.assertIsNotNone(d)
        d.apply({1: {'kern': 50.0}})
        now = self.w.canvas.doc.layers[0].items[0]
        self.assertAlmostEqual(now.outline.bbox()[2] - before[2], 5.0, places=6)
        self.w.undo()
        back = self.w.canvas.doc.layers[0].items[0]
        self.assertEqual(back.outline.bbox(), before)
        d.reject()

    def test_dialog_on_an_arc(self):
        t = make('HHHH', arc={'center': (0, 0), 'radius': 40.0})
        t.outline = TX.outline_for(t)
        self.w.canvas.doc.layers[0].items[:] = [t]
        self.w.canvas.select([t])
        d = self.w.text_letters_dialog(exec_dialog=False)
        self.assertIsNotNone(d)
        before = t.outline.bbox()
        d.apply({0: {'h': 200.0}})
        self.assertNotEqual(t.outline.bbox(), before)
        d.reject()

    def test_saved_to_vnd_as_curves(self):
        from vectordrive.core.document import Document
        from vectordrive.io import registry
        TX.set_char_fx(self.t, {1: {'kern': 50.0}})
        self.t.outline = TX.outline_for(self.t)
        doc = self.w.canvas.doc
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, 'a.vnd')
            registry.save_document(doc, f)
            back = registry.open_document(f)
        boxes = [it.bbox() for it in back.iter_leaves()]
        self.assertTrue(boxes)
        x1 = max(b[2] for b in boxes)
        self.assertAlmostEqual(x1, self.t.outline.bbox()[2], delta=0.05)
        self.assertIsInstance(back, Document)


if __name__ == '__main__':
    unittest.main()
