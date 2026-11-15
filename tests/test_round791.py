"""Round 791 : une police par lettre."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from vectordrive.core import fonts
from vectordrive.core import text as TX
from vectordrive.core.document import Text
from vectordrive.core.geom import Contour, Line


def second_font():
    """Une police d'une autre forme que VD Trait, parmi celles de la machine ; sinon None."""
    for name in ('Arial', 'DejaVu Sans', 'Liberation Sans', 'Segoe UI', 'Times New Roman', 'Verdana', 'Tahoma'):
        if fonts.is_available(name) and fonts.find_font(name) != fonts.find_font('VD Trait'):
            return name
    return None


TRAIT = 'VD Trait'
OTHER = second_font()
LINE = Contour([Line((0, 0), (300, 0))], False)


def nodes(path):
    return [tuple(round(v, 6) for v in p) for c in path.contours for s in c.segments for p in (s.start, s.end)]


def make(text='HH', font=TRAIT, **extra):
    t = Text(text=text, font=font, size=10.0)
    t.extra.update(extra)
    return t


class TestValues(unittest.TestCase):
    def test_kept(self):
        self.assertEqual(TX.clean_char_fx({0: {'font': 'X'}}), {0: {'font': 'X'}})

    def test_with_other_settings(self):
        self.assertEqual(TX.clean_char_fx({0: {'font': 'X', 'h': 50.0, 'w': 100.0}}), {0: {'font': 'X', 'h': 50.0}})

    def test_empty_or_wrong_dropped(self):
        for bad in ('', '   ', None, 5, ['a']):
            self.assertEqual(TX.clean_char_fx({0: {'font': bad}}), {})

    def test_stored_and_read_back(self):
        t = make()
        TX.set_char_fx(t, {1: {'font': 'X'}})
        self.assertEqual(t.extra['chars'], {'1': {'font': 'X'}})
        self.assertEqual(TX.char_fx(t), {1: {'font': 'X'}})

    def test_follows_its_letter_when_the_text_changes(self):
        t = make('HH')
        TX.set_char_fx(t, {1: {'font': 'X'}})
        t.text = 'AHH'
        self.assertEqual(TX.char_fx(t), {2: {'font': 'X'}})


@unittest.skipUnless(OTHER, 'pas de seconde police sur cette machine')
class TestLayout(unittest.TestCase):
    def whole(self, text, font):
        return TX.layout(text, font, 10.0, kerning=False)

    def test_all_letters_same_as_a_text_in_that_font(self):
        want = self.whole('HEH', OTHER).bbox()
        got = TX.layout('HEH', TRAIT, 10.0, kerning=False, fx={i: {'font': OTHER} for i in range(3)}).bbox()
        for a, b in zip(got, want):
            self.assertAlmostEqual(a, b, places=6)

    def test_one_letter_in_another_font_changes_the_next_position(self):
        plain = TX.layout('HH', TRAIT, 10.0, kerning=False)
        mixed = TX.layout('HH', TRAIT, 10.0, kerning=False, fx={0: {'font': OTHER}})
        self.assertNotEqual(nodes(plain), nodes(mixed))
        adv = fonts.glyph(*fonts.find_font(OTHER), 'H')[1] * TX.em_for_height(fonts.find_font(OTHER), 10.0) / fonts.metrics(*fonts.find_font(OTHER))['upem']
        trait_h = self.whole('H', TRAIT).bbox()
        self.assertAlmostEqual(mixed.bbox()[2], adv + trait_h[2], places=6)      # le 2ᵉ H suit la chasse de la lettre changée

    def test_height_stays_the_same_body(self):
        mine = self.whole('H', OTHER).bbox()
        got = TX.layout('H', TRAIT, 10.0, kerning=False, fx={0: {'font': OTHER}}).bbox()
        self.assertAlmostEqual(got[3], mine[3], places=6)

    def test_with_height_and_width_settings(self):
        got = TX.layout('H', TRAIT, 10.0, kerning=False, fx={0: {'font': OTHER, 'h': 200.0}}).bbox()
        mine = self.whole('H', OTHER).bbox()
        self.assertAlmostEqual(got[3] - got[1], 2 * (mine[3] - mine[1]), places=6)

    def test_rotation_with_another_font(self):
        got = TX.layout('H', TRAIT, 10.0, kerning=False, fx={0: {'font': OTHER, 'rot': 180.0}}).bbox()
        mine = self.whole('H', OTHER).bbox()
        self.assertAlmostEqual(got[3] - got[1], mine[3] - mine[1], places=5)

    def test_on_a_curve_same_as_straight(self):
        fx = {1: {'font': OTHER}}
        got = TX.on_path('HHH', TRAIT, 10.0, LINE, fx=fx).bbox()
        want = TX.layout('HHH', TRAIT, 10.0, kerning=False, fx=fx).bbox()
        for a, b in zip(got, want):
            self.assertAlmostEqual(a, b, places=6)

    def test_on_a_curve_with_every_setting(self):
        fx = {1: {'font': OTHER, 'h': 150.0, 'w': 70.0, 'rot': 30.0, 'dx': 10.0, 'dy': 5.0, 'kern': 10.0}}
        got = TX.on_path('HHH', TRAIT, 10.0, LINE, fx=fx).bbox()
        want = TX.layout('HHH', TRAIT, 10.0, kerning=False, fx=fx).bbox()
        for a, b in zip(got, want):
            self.assertAlmostEqual(a, b, places=6)

    def test_on_path_rotated_tangent_unaffected_by_scale_name(self):
        up = Contour([Line((0, 0), (0, 300))], False)
        got = TX.on_path('H', TRAIT, 10.0, up, fx={0: {'font': OTHER}}).bbox()
        self.assertLess(got[2], 1.0)                     # la lettre reste à gauche de la courbe qui monte
        self.assertGreater(got[3], 1.0)

    def test_arc_warp(self):
        plain = TX.arc_warp('HH', TRAIT, 10.0, (0, 0), 40.0)
        mixed = TX.arc_warp('HH', TRAIT, 10.0, (0, 0), 40.0, fx={0: {'font': OTHER}})
        self.assertNotEqual(nodes(plain), nodes(mixed))

    def test_small_caps_with_another_font(self):
        got = TX.layout('h', TRAIT, 10.0, kerning=False, small_caps=True, fx={0: {'font': OTHER}}).bbox()
        mine = self.whole('H', OTHER).bbox()
        self.assertAlmostEqual((got[3] - got[1]) / (mine[3] - mine[1]), TX.SMALL_CAPS, places=5)

    def test_outline_of_an_item(self):
        t = make('HH')
        plain = TX.outline_for(t)
        TX.set_char_fx(t, {0: {'font': OTHER}})
        self.assertNotEqual(nodes(TX.outline_for(t)), nodes(plain))


class TestMissingFont(unittest.TestCase):
    def test_unknown_font_never_crashes(self):
        got = TX.layout('HH', TRAIT, 10.0, kerning=False, fx={0: {'font': 'Police Absente De Partout'}})
        self.assertTrue(got.contours)
        got = TX.on_path('HH', TRAIT, 10.0, LINE, fx={0: {'font': 'Police Absente De Partout'}})
        self.assertTrue(got.contours)

    def test_font_setting_alone_on_stroke_font(self):
        got = TX.layout('HH', TRAIT, 10.0, kerning=False, fx={0: {'font': TRAIT}})
        self.assertEqual(nodes(got), nodes(TX.layout('HH', TRAIT, 10.0, kerning=False)))


class TestDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.t = make('HHH')
        self.t.outline = TX.outline_for(self.t)
        self.w.canvas.doc.layers[0].items[:] = [self.t]
        self.w.canvas.invalidate()
        self.w.canvas.select([self.t])
        self.d = self.w.text_letters_dialog(exec_dialog=False)

    def tearDown(self):
        self.d.reject()
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()

    def test_box_shows_the_text_font(self):
        self.assertEqual(self.d.font_box.currentText(), TRAIT)

    def test_sets_the_chosen_letters(self):
        self.d.select(1, 3)
        self.d.set_font('X')
        self.assertEqual(self.d.fx, {1: {'font': 'X'}, 2: {'font': 'X'}})
        self.assertEqual(TX.char_fx(self.t), {1: {'font': 'X'}, 2: {'font': 'X'}})

    def test_box_follows_the_letter(self):
        self.d.select(1, 2)
        self.d.set_font('X')
        self.d.select(0)
        self.assertEqual(self.d.font_box.currentText(), TRAIT)
        self.d.select(1)
        self.assertEqual(self.d.font_box.currentText(), 'X')

    def test_loading_a_letter_changes_nothing(self):
        self.d.select(1, 2)
        self.d.set_font('X')
        with mock.patch.object(self.d, 'apply') as applied:
            self.d.select(0)
            self.d.select(1)
        applied.assert_not_called()

    def test_text_font_removes_the_setting(self):
        self.d.select(1, 2)
        self.d.set_font('X')
        self.d.set_font(TRAIT)
        self.assertEqual(TX.char_fx(self.t), {})

    def test_same_font_again_does_not_redraw(self):
        self.d.select(1, 2)
        self.d.set_font('X')
        with mock.patch.object(self.d, 'apply') as applied:
            self.d.set_font('X')
        applied.assert_not_called()

    def test_normal_removes_it_too(self):
        self.d.select(1, 2)
        self.d.set_font('X')
        self.d.put({})
        self.assertEqual(TX.char_fx(self.t), {})

    def test_keeps_other_settings(self):
        self.d.select(1, 2)
        self.d.set_value('h', 150.0)
        self.d.set_font('X')
        self.assertEqual(TX.char_fx(self.t), {1: {'h': 150.0, 'font': 'X'}})

    def test_cancel_restores(self):
        self.d.select(1, 2)
        self.d.set_font('X')
        self.d.reject()
        self.assertEqual(TX.char_fx(self.t), {})

    def test_no_letter_disables(self):
        d = self.w.text_letters_dialog(exec_dialog=False)
        d.select(3)
        self.assertFalse(d.font_box.isEnabled())
        d.reject()


class TestReplaceFont(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.t = make('HHH')
        self.w.canvas.doc.layers[0].items[:] = [self.t]

    def tearDown(self):
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()

    def test_changes_the_letters_too_and_keeps_other_settings(self):
        TX.set_char_fx(self.t, {1: {'font': 'X', 'h': 150.0}, 2: {'font': 'X'}})
        self.assertEqual(self.w.replace_font([self.t], 'Y'), 1)
        self.assertEqual(self.t.font, 'Y')
        self.assertEqual(TX.char_fx(self.t), {1: {'h': 150.0}})

    def test_same_font_with_mixed_letters_still_cleans(self):
        TX.set_char_fx(self.t, {1: {'font': 'X'}})
        self.assertEqual(self.w.replace_font([self.t], TRAIT), 1)
        self.assertEqual(TX.char_fx(self.t), {})

    def test_same_font_without_letters_does_nothing(self):
        self.assertEqual(self.w.replace_font([self.t], TRAIT), 0)


if __name__ == '__main__':
    unittest.main()
