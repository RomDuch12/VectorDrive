"""Round 795 : texte de droite à gauche."""
import os
import tempfile
import unicodedata
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from vectordrive.core import fonts, rtl
from vectordrive.core import text as TX
from vectordrive.core.document import Text

ALEF, BEH, LAM, MEEM, SEEN, REH, WAW, TEH = 'ا', 'ب', 'ل', 'م', 'س', 'ر', 'و', 'ت'
FATHA = 'َ'
TATWEEL = 'ـ'
PEH = 'پ'


def form(ch):
    """'isolated', 'initial', 'medial' ou 'final' d'une forme de présentation ; None pour une lettre ordinaire."""
    d = unicodedata.decomposition(ch)
    return d[1:d.index('>')] if d.startswith('<') else None


def base(ch):
    return chr(int(unicodedata.decomposition(ch).split()[1], 16))


def arabic_font():
    for name in ('Arial', 'Times New Roman', 'Tahoma', 'Segoe UI', 'DejaVu Sans'):
        if fonts.is_available(name) and 'ﺍ' in fonts.char_set(name):
            return name
    return None


ARABIC = arabic_font()


class TestShape(unittest.TestCase):
    def forms(self, text):
        return [form(c) for c in rtl.shape(text)]

    def test_alone(self):
        self.assertEqual(self.forms(BEH), ['isolated'])

    def test_three_letters_join(self):
        self.assertEqual(self.forms(BEH + BEH + BEH), ['initial', 'medial', 'final'])

    def test_keeps_the_letters(self):
        got = rtl.shape(BEH + SEEN + MEEM)
        self.assertEqual([base(c) for c in got], [BEH, SEEN, MEEM])

    def test_right_joining_letter_cuts_the_word(self):
        self.assertEqual(self.forms(BEH + ALEF + BEH), ['initial', 'final', 'isolated'])

    def test_word_with_reh_and_waw(self):
        self.assertEqual(self.forms(REH + WAW + BEH), ['isolated', 'isolated', 'isolated'])

    def test_space_cuts(self):
        self.assertEqual(self.forms(BEH + ' ' + BEH), ['isolated', None, 'isolated'])

    def test_marks_do_not_cut(self):
        got = rtl.shape(BEH + FATHA + BEH)
        self.assertEqual([form(got[0]), got[1], form(got[2])], ['initial', FATHA, 'final'])

    def test_tatweel_joins(self):
        got = rtl.shape(BEH + TATWEEL + BEH)
        self.assertEqual([form(got[0]), got[1], form(got[2])], ['initial', TATWEEL, 'final'])

    def test_persian_letter(self):
        self.assertEqual(self.forms(PEH + PEH), ['initial', 'final'])

    def test_lam_alef_is_one_character(self):
        got = rtl.shape(LAM + ALEF)
        self.assertEqual(len(got), 1)
        self.assertEqual(got, 'ﻻ')

    def test_lam_alef_after_a_joining_letter(self):
        got = rtl.shape(BEH + LAM + ALEF)
        self.assertEqual(got, 'ﺑﻼ')

    def test_mark_on_the_lam_stays(self):
        got = rtl.shape(LAM + FATHA + ALEF)
        self.assertEqual(got, 'ﻻ' + FATHA)

    def test_latin_left_alone(self):
        self.assertEqual(rtl.shape('Abc 12'), 'Abc 12')

    def test_font_without_the_form(self):
        self.assertEqual(rtl.shape(BEH, has=lambda _c: False), BEH)

    def test_font_with_only_some_forms(self):
        iso = rtl.shape(BEH)
        self.assertEqual(rtl.shape(BEH, has={iso}.__contains__), iso)
        self.assertEqual(rtl.shape(BEH + BEH, has={iso}.__contains__), BEH + BEH)


class TestOrder(unittest.TestCase):
    def test_hebrew_is_reversed(self):
        self.assertEqual(rtl.visual_line('אבג'), 'גבא')

    def test_latin_stays_in_order(self):
        self.assertEqual(rtl.visual_line('abc'), 'abc')

    def test_latin_inside_arabic(self):
        got = rtl.visual_line(BEH + ' abc ' + MEEM)
        self.assertEqual(got, MEEM + ' abc ' + BEH)

    def test_digits_stay_in_order(self):
        got = rtl.visual_line(BEH + ' 123 ' + MEEM)
        self.assertEqual(got, MEEM + ' 123 ' + BEH)

    def test_decimal_number_in_one_piece(self):
        got = rtl.visual_line(BEH + ' 12.5')
        self.assertEqual(got, '12.5 ' + BEH)

    def test_percent_stays_with_its_number(self):
        got = rtl.visual_line(BEH + ' 50% ' + MEEM)
        self.assertEqual(got, MEEM + ' 50% ' + BEH)

    def test_brackets_turn_around(self):
        got = rtl.visual_line('(' + BEH + ')')
        self.assertEqual(got, '(' + BEH + ')')

    def test_two_latin_words_keep_their_order(self):
        got = rtl.visual_line(BEH + ' ab cd ' + MEEM)
        self.assertEqual(got, MEEM + ' ab cd ' + BEH)

    def test_mark_stays_after_its_letter(self):
        got = rtl.visual_line(BEH + FATHA + MEEM)
        self.assertEqual(got, MEEM + BEH + FATHA)

    def test_empty(self):
        self.assertEqual(rtl.visual_line(''), '')

    def test_lines_are_separate(self):
        self.assertEqual(rtl.visual('אב\nגד'), 'בא\nדג')

    def test_visual_shapes_then_orders(self):
        got = rtl.visual(BEH + BEH)
        self.assertEqual([form(c) for c in got], ['final', 'initial'])


def make(text, font, **extra):
    t = Text(text=text, font=font, size=10.0)
    t.extra.update(extra)
    t.outline = TX.outline_for(t)
    return t


class TestItem(unittest.TestCase):
    def test_off_nothing_changes(self):
        t = make('abc', 'VD Trait')
        self.assertEqual(TX.shown_text(t), 'abc')

    def test_shown_text(self):
        t = make('אב', 'Absente De Partout', rtl=True)
        self.assertEqual(TX.shown_text(t), 'בא')

    def test_kept_in_typing_order(self):
        t = make('אב', 'VD Trait', rtl=True)
        self.assertEqual(t.text, 'אב')

    def test_goes_to_curves_in_vnd(self):
        from vectordrive.io import vnd_write as W
        self.assertTrue(W.styled(make('ab', 'VD Trait', rtl=True)))
        self.assertFalse(W.styled(make('ab', 'VD Trait')))

    def test_copied_with_the_format(self):
        a = make('ab', 'VD Trait', rtl=True)
        b = make('cd', 'VD Trait')
        TX.apply_format(b, TX.text_format(a))
        self.assertTrue(b.extra['rtl'])

    def test_settings_by_letter_ignored(self):
        a = make('abc', 'VD Trait', rtl=True)
        TX.set_char_fx(a, {0: {'h': 300.0}})
        self.assertEqual(TX.outline_for(a).bbox(), make('abc', 'VD Trait', rtl=True).outline.bbox())

    @unittest.skipUnless(ARABIC, 'pas de police arabe sur cette machine')
    def test_joined_word_is_narrower_than_loose_letters(self):
        word = BEH * 4
        shaped = make(word, ARABIC, rtl=True).outline.bbox()
        loose = make(word, ARABIC).outline.bbox()
        self.assertLess(shaped[2] - shaped[0], loose[2] - loose[0])

    @unittest.skipUnless(ARABIC, 'pas de police arabe sur cette machine')
    def test_on_a_curve_and_in_a_box(self):
        from vectordrive.core.geom import Contour, Line
        self.assertTrue(make(BEH * 3, ARABIC, rtl=True, on_path=Contour([Line((0, 0), (200, 0))], False)).outline.contours)
        self.assertTrue(make(BEH * 3, ARABIC, rtl=True, box={'x0': 0, 'y0': 0, 'x1': 60, 'y1': 20}).outline.contours)
        self.assertTrue(make(BEH * 3, ARABIC, rtl=True, underline=True).outline.contours)
        self.assertTrue(make(BEH * 3, ARABIC, rtl=True, max_length={'length': 5.0, 'by': 'line'}).outline.contours)

    @unittest.skipUnless(ARABIC, 'pas de police arabe sur cette machine')
    def test_max_length_is_measured_on_what_is_shown(self):
        t = make(BEH * 6, ARABIC, rtl=True)
        full = t.outline.bbox()
        limited = make(BEH * 6, ARABIC, rtl=True, max_length={'length': (full[2] - full[0]) / 2, 'by': 'line'})
        box = limited.outline.bbox()
        self.assertAlmostEqual(box[2] - box[0], (full[2] - full[0]) / 2, delta=0.5)


class TestWindow(unittest.TestCase):
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

    def put(self, *texts):
        self.w.canvas.doc.layers[0].items[:] = list(texts)
        self.w.canvas.invalidate()
        self.w.canvas.select(list(texts))

    def test_on_and_off(self):
        t = make('ab', 'VD Trait')
        self.put(t)
        self.assertEqual(self.w.toggle_text_rtl(), [t])
        self.assertTrue(t.extra['rtl'])
        self.w.toggle_text_rtl()
        self.assertNotIn('rtl', t.extra)

    def test_mixed_selection_turns_on(self):
        a, b = make('ab', 'VD Trait', rtl=True), make('cd', 'VD Trait')
        self.put(a, b)
        self.w.toggle_text_rtl()
        self.assertTrue(a.extra['rtl'] and b.extra['rtl'])

    def test_undo(self):
        self.put(make('ab', 'VD Trait'))
        self.w.toggle_text_rtl()
        self.w.undo()
        self.assertNotIn('rtl', self.w.canvas.doc.layers[0].items[0].extra)

    def test_nothing_selected(self):
        self.w.canvas.select([])
        self.assertEqual(self.w.toggle_text_rtl(), [])

    def test_link(self):
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual(TE_ACTIONS['ID_RAPIDO_CHAR_PBARABE_DLL'], 'text_rtl')
        self.assertIn('text_rtl', self.w.A)


class TestCache(unittest.TestCase):
    def test_refresh_forgets_the_characters(self):
        fonts.char_set('VD Trait')
        fonts.refresh()
        self.assertEqual(fonts.char_set.cache_info().currsize, 0)


if __name__ == '__main__':
    unittest.main()
