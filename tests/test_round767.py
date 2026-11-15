"""Lettres : crénage manuel, décalage, hauteur, largeur, rotation de chaque lettre ; exposant et indice."""
import math
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from vectordrive.core import text as TX
from vectordrive.core.document import Document, Group, Layer, Text
from vectordrive.core.geom import Affine
from vectordrive.io import native, te_clip, vnd, vnd_write as VW
from vectordrive.ui.letters_dialog import LettersDialog
from vectordrive.ui.main_window import MainWindow

app = QApplication.instance() or QApplication([])
FONT = 'Arial'


def make(s='HHH', **kw):
    kw.setdefault('size', 10.0)
    t = Text(text=s, font=FONT, **kw)
    t.outline = TX.outline_for(t)
    return t


def with_fx(s, fx, **kw):
    t = make(s, **kw)
    TX.set_char_fx(t, fx)
    t.outline = TX.outline_for(t)
    return t


def letters(t):
    """Les boîtes des lettres d'un texte en H : deux jambes et une barre = un contour par lettre."""
    return [c.bbox() for c in t.outline.contours]


class TestLayout(unittest.TestCase):
    def setUp(self):
        self.base = letters(make())

    def assertBox(self, a, b, places=6):
        for x, y in zip(a, b):
            self.assertAlmostEqual(x, y, places=places)

    def test_nothing_set_changes_nothing(self):
        self.assertEqual(letters(with_fx('HHH', {})), self.base)

    def test_kern_moves_the_letter_and_what_follows(self):
        got = letters(with_fx('HHH', {1: {'kern': 20.0}}))
        self.assertBox(got[0], self.base[0])
        for i in (1, 2):
            self.assertAlmostEqual(got[i][0], self.base[i][0] + 2.0, places=6)         # 20 % de 10 mm

    def test_negative_kern(self):
        got = letters(with_fx('HHH', {2: {'kern': -30.0}}))
        self.assertAlmostEqual(got[2][0], self.base[2][0] - 3.0, places=6)
        self.assertBox(got[1], self.base[1])

    def test_dx_dy_move_that_letter_only(self):
        got = letters(with_fx('HHH', {1: {'dx': 10.0, 'dy': -50.0}}))
        self.assertAlmostEqual(got[1][0], self.base[1][0] + 1.0, places=6)
        self.assertAlmostEqual(got[1][1], self.base[1][1] - 5.0, places=6)
        self.assertBox(got[0], self.base[0])
        self.assertBox(got[2], self.base[2])

    def test_height_scales_the_letter_and_pulls_what_follows(self):
        got = letters(with_fx('HHH', {0: {'h': 50.0}}))
        self.assertAlmostEqual(got[0][3] - got[0][1], (self.base[0][3] - self.base[0][1]) / 2, places=6)
        self.assertAlmostEqual(got[0][2] - got[0][0], (self.base[0][2] - self.base[0][0]) / 2, places=6)
        pitch = self.base[1][0] - self.base[0][0]
        self.assertAlmostEqual(got[1][0], self.base[1][0] - pitch / 2, places=6)
        self.assertAlmostEqual(got[1][3] - got[1][1], self.base[1][3] - self.base[1][1], places=6)

    def test_width_scales_x_only(self):
        got = letters(with_fx('HHH', {0: {'w': 200.0}}))
        self.assertAlmostEqual(got[0][2] - got[0][0], (self.base[0][2] - self.base[0][0]) * 2, places=6)
        self.assertAlmostEqual(got[0][3] - got[0][1], self.base[0][3] - self.base[0][1], places=6)
        pitch = self.base[1][0] - self.base[0][0]
        self.assertAlmostEqual(got[1][0], self.base[1][0] + pitch, places=6)

    def test_rotation_turns_around_the_letter(self):
        t = with_fx('HHH', {1: {'rot': 90.0}})
        got = letters(t)
        w, h = self.base[1][2] - self.base[1][0], self.base[1][3] - self.base[1][1]
        self.assertAlmostEqual(got[1][2] - got[1][0], h, places=6)                     # couchée
        self.assertAlmostEqual(got[1][3] - got[1][1], w, places=6)
        cx, cy = (got[1][0] + got[1][2]) / 2, (got[1][1] + got[1][3]) / 2
        bx, by = (self.base[1][0] + self.base[1][2]) / 2, (self.base[1][1] + self.base[1][3]) / 2
        self.assertLess(math.hypot(cx - bx, cy - by), 0.3)                             # reste à sa place
        self.assertBox(got[2], self.base[2])                                           # ne pousse rien

    def test_superscript_and_subscript(self):
        sup = letters(with_fx('HHH', {2: TX.SUPERSCRIPT}))[2]
        sub = letters(with_fx('HHH', {2: TX.SUBSCRIPT}))[2]
        self.assertGreater(sup[3], self.base[2][3])                                    # dépasse le haut des capitales
        self.assertGreater(sup[1], 0.0)
        self.assertLess(sub[1], 0.0)                                                   # passe sous la ligne de base
        self.assertAlmostEqual(sup[3] - sup[1], (self.base[2][3] - self.base[2][1]) * 0.6, places=6)

    def test_follows_text_size(self):
        got = letters(with_fx('HHH', {1: {'kern': 20.0}}, size=20.0))
        b = letters(make(size=20.0))
        self.assertAlmostEqual(got[1][0], b[1][0] + 4.0, places=6)

    def test_centred_uses_the_new_width(self):
        t = with_fx('HHH', {1: {'kern': 100.0}}, align='center')
        x0, _y0, x1, _y1 = t.outline.bbox()
        self.assertAlmostEqual(x0 + x1, make(align='center').outline.bbox()[0] + make(align='center').outline.bbox()[2], places=6)
        self.assertGreater(x1 - x0, 10.0)

    def test_right_aligned_ends_at_zero(self):
        plain = make(align='right').outline.bbox()[2]
        t = with_fx('HHH', {1: {'kern': 50.0}}, align='right')
        self.assertAlmostEqual(t.outline.bbox()[2], plain, places=6)

    def test_second_line_counts_its_position(self):
        t = with_fx('HH\nHH', {3: {'dy': 100.0}})
        p = make('HH\nHH')
        got, base = letters(t), letters(p)
        self.assertEqual(got[0], base[0])
        self.assertEqual(got[1], base[1])
        self.assertAlmostEqual(got[2][1], base[2][1] + 10.0, places=6)                 # position 3 : première lettre de la ligne 2
        self.assertEqual(got[3], base[3])

    def test_justified(self):
        t = with_fx('HHHH\nHH', {5: {'kern': 10.0}}, align='justify')
        self.assertEqual(len(letters(t)), 6)

    def test_placed_within_the_matrix(self):
        t = with_fx('HHH', {1: {'kern': 20.0}}, matrix=Affine.translation(100, 50))
        self.assertAlmostEqual(letters(t)[1][0], self.base[1][0] + 2.0 + 100.0, places=6)

    def test_underline_stays_one_bar(self):
        plain = make('HHH')
        plain.extra['underline'] = True
        plain.outline = TX.outline_for(plain)
        t = with_fx('HHH', {2: TX.SUPERSCRIPT})
        t.extra['underline'] = True
        t.outline = TX.outline_for(t)
        self.assertEqual(len(t.outline.contours), len(plain.outline.contours))

    def test_underline_follows_a_kern(self):
        t = with_fx('HHH', {2: {'kern': 50.0}})
        t.extra['underline'] = True
        t.outline = TX.outline_for(t)
        bar = t.outline.contours[-1].bbox()
        self.assertAlmostEqual(bar[2], letters(t)[2][2], places=6)

    def test_with_italic(self):
        t = with_fx('HHH', {1: {'kern': 20.0}})
        t.extra['italic'] = 12.0
        t.outline = TX.outline_for(t)
        self.assertEqual(len(t.outline.contours), 3)

    def test_small_caps_keep_their_advance(self):
        plain = make('aaa')
        plain.extra['small_caps'] = True
        plain.outline = TX.outline_for(plain)
        t = with_fx('aaa', {0: {'h': 100.0, 'kern': 10.0}})
        t.extra['small_caps'] = True
        t.outline = TX.outline_for(t)
        self.assertAlmostEqual(t.outline.bbox()[2], plain.outline.bbox()[2] + 1.0, places=6)

    def test_max_length_counts_the_kern(self):
        t = with_fx('HHHHHH', {3: {'kern': 200.0}})
        t.extra['max_length'] = {'length': 30.0, 'by': 'line'}
        t.outline = TX.outline_for(t)
        self.assertLessEqual(t.outline.bbox()[2], 30.5)

    def test_curved_text_follows_them(self):
        t = make('HHH')
        from vectordrive.core.geom import Contour, Line
        t.extra['on_path'] = Contour([Line((0, 0), (100, 0))], False)
        plain = TX.outline_for(t)
        TX.set_char_fx(t, {1: {'kern': 50.0}})
        self.assertGreater(TX.outline_for(t).bbox()[2], plain.bbox()[2])


class TestValues(unittest.TestCase):
    def test_neutral_dropped(self):
        self.assertEqual(TX.clean_char_fx({0: {'kern': 0.0, 'h': 100.0}, 1: {'dy': 5.0, 'w': 100.0}}), {1: {'dy': 5.0}})

    def test_size_stays_above_zero(self):
        self.assertEqual(TX.clean_char_fx({0: {'h': 0.0, 'w': -20.0}}), {0: {'h': 1.0, 'w': 1.0}})

    def test_bad_values_dropped(self):
        self.assertEqual(TX.clean_char_fx({0: {'kern': float('nan'), 'dx': float('inf'), 'dy': 'abc', 'rot': None}}), {})

    def test_set_leaves_no_trace_when_empty(self):
        t = with_fx('HHH', {1: {'kern': 5.0}})
        TX.set_char_fx(t, {})
        self.assertNotIn('chars', t.extra)
        self.assertNotIn('chars_text', t.extra)

    def test_new_dict_for_undo(self):
        t = with_fx('HHH', {1: {'kern': 5.0}})
        before = t.extra
        TX.set_char_fx(t, {1: {'kern': 9.0}})
        self.assertIsNot(t.extra, before)
        self.assertEqual(before['chars'], {'1': {'kern': 5.0}})

    def test_bad_stored_data_ignored(self):
        t = make()
        t.extra['chars'] = ['n', 'importe', 'quoi']
        self.assertEqual(TX.char_fx(t), {})
        self.assertEqual(len(TX.outline_for(t).contours), 3)

    def test_out_of_range_ignored(self):
        t = make('HH')
        t.extra['chars'] = {'9': {'kern': 5.0}, 'x': {}}
        self.assertEqual(TX.char_fx(t), {})


class TestEditing(unittest.TestCase):
    def test_letter_added_before(self):
        self.assertEqual(TX.follow_edit('abc', 'xabc', {1: {'kern': 5.0}}), {2: {'kern': 5.0}})

    def test_letter_added_after(self):
        self.assertEqual(TX.follow_edit('abc', 'abcd', {1: {'kern': 5.0}}), {1: {'kern': 5.0}})

    def test_letter_removed_goes_with_it(self):
        self.assertEqual(TX.follow_edit('abc', 'ac', {1: {'kern': 5.0}, 2: {'dy': 1.0}}), {1: {'dy': 1.0}})

    def test_all_retyped(self):
        self.assertEqual(TX.follow_edit('abc', 'xyz', {1: {'kern': 5.0}}), {})

    def test_outline_follows_a_new_text(self):
        t = with_fx('HHH', {1: {'kern': 20.0}})
        t.text = 'HHHH'
        t.outline = TX.outline_for(t)
        self.assertEqual(t.extra['chars_text'], 'HHHH')
        self.assertEqual(len(letters(t)), 4)
        self.assertIn('1', t.extra['chars'])

    def test_read_does_not_change_the_item(self):
        t = with_fx('HHH', {1: {'kern': 20.0}})
        t.text = 'xHHH'
        self.assertEqual(TX.char_fx(t), {2: {'kern': 20.0}})
        self.assertEqual(t.extra['chars_text'], 'HHH')


class TestFiles(unittest.TestCase):
    def test_native_keeps_them(self):
        t = with_fx('HHH', {1: {'kern': 20.0, 'rot': 15.0}})
        d = Document()
        d.layers = [Layer(items=[t])]
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, 'a.vdz')
            native.write(d, p)
            back = native.read(p)
        got = next(iter(back.iter_leaves()))
        self.assertEqual(TX.char_fx(got), {1: {'kern': 20.0, 'rot': 15.0}})
        self.assertEqual(TX.outline_for(got).bbox(), t.outline.bbox())

    def test_not_a_typeedit_paragraph(self):
        t = with_fx('HHH', {1: {'kern': 20.0}})
        self.assertTrue(VW.styled(t))
        self.assertFalse(VW.styled(make()))

    def test_vnd_gets_the_real_shape(self):
        t = with_fx('HHH', {1: {'kern': 200.0}})
        d = Document()
        d.layers = [Layer(items=[t])]
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, 'a.vnd')
            VW.write(d, p)
            back = vnd.read(p)
        boxes = [it.bbox() for it in back.iter_leaves()]
        self.assertTrue(boxes)
        x1 = max(b[2] for b in boxes)
        self.assertAlmostEqual(x1, t.outline.bbox()[2], places=2)

    def test_clipboard_for_typeedit_gets_the_real_shape(self):
        t = with_fx('HHH', {1: {'kern': 200.0}})
        items, _rep = te_clip.read(te_clip.build([t]))
        leaves = []

        def walk(xs):
            for x in xs:
                if isinstance(x, Group):
                    walk(x.children)
                else:
                    leaves.append(x)
        walk(items)
        self.assertFalse(any(isinstance(x, Text) for x in leaves))                     # en courbes
        self.assertAlmostEqual(max(x.bbox()[2] for x in leaves), t.outline.bbox()[2], places=2)

    def test_copy_keeps_them(self):
        t = with_fx('HHH', {1: {'kern': 20.0}})
        c = t.transformed(Affine.translation(5, 0))
        self.assertEqual(TX.char_fx(c), TX.char_fx(t))
        self.assertAlmostEqual(TX.outline_for(c).bbox()[0], t.outline.bbox()[0] + 5.0, places=6)


class TestDialog(unittest.TestCase):
    def setUp(self):
        self.t = make('HHHH')
        self.calls = []
        self.d = LettersDialog(None, self.t, self.apply)

    def tearDown(self):
        self.d.close()

    def apply(self, fx):
        self.calls.append(fx)
        TX.set_char_fx(self.t, fx)
        self.t.outline = TX.outline_for(self.t)

    def test_caret_means_next_letter(self):
        self.d.select(2)
        self.assertEqual(self.d.indices(), [2])

    def test_selection(self):
        self.d.select(1, 3)
        self.assertEqual(self.d.indices(), [1, 2])

    def test_caret_at_the_end_means_nothing(self):
        self.d.select(4)
        self.assertEqual(self.d.indices(), [])
        self.assertFalse(self.d.fields['kern'].isEnabled())

    def test_newline_is_no_letter(self):
        t = make('HH\nHH')
        d = LettersDialog(None, t, lambda fx: None)
        d.select(1, 4)
        self.assertEqual(d.indices(), [1, 3])

    def test_emoji_counts_one_letter(self):
        t = make('😀HH')
        d = LettersDialog(None, t, lambda fx: None)
        d.select(1)
        self.assertEqual(d.indices(), [1])
        d.select(0, 2)
        self.assertEqual(d.indices(), [0, 1])

    def test_value_goes_to_the_drawing(self):
        self.d.select(1, 3)
        self.d.fields['h'].setValue(50.0)
        self.assertEqual(TX.char_fx(self.t), {1: {'h': 50.0}, 2: {'h': 50.0}})

    def test_fields_show_the_letter(self):
        self.d.select(1)
        self.d.fields['kern'].setValue(12.0)
        self.d.select(2)
        self.assertEqual(self.d.fields['kern'].value(), 0.0)
        self.assertEqual(self.d.fields['h'].value(), 100.0)
        self.d.select(1)
        self.assertEqual(self.d.fields['kern'].value(), 12.0)

    def test_loading_changes_nothing(self):
        self.d.select(1)
        self.d.select(2)
        self.assertEqual(self.calls, [])

    def test_superscript_button(self):
        self.d.select(3)
        self.d.b_sup.click()
        self.assertEqual(TX.char_fx(self.t), {3: TX.SUPERSCRIPT})
        self.assertEqual(self.d.fields['h'].value(), 60.0)

    def test_subscript_button(self):
        self.d.select(3)
        self.d.b_sub.click()
        self.assertEqual(TX.char_fx(self.t), {3: TX.SUBSCRIPT})

    def test_normal_button(self):
        self.d.select(3)
        self.d.b_sup.click()
        self.d.b_normal.click()
        self.assertEqual(TX.char_fx(self.t), {})
        self.assertNotIn('chars', self.t.extra)

    def test_alt_arrows_kern(self):
        self.d.select(1)
        QTest.keyClick(self.d.view, Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier)
        QTest.keyClick(self.d.view, Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier)
        self.assertEqual(TX.char_fx(self.t), {1: {'kern': 2.0}})
        self.assertEqual(self.d.indices(), [1])                                        # le curseur n'a pas bougé
        self.assertEqual(self.d.fields['kern'].value(), 2.0)

    def test_alt_shift_goes_faster(self):
        self.d.select(1)
        QTest.keyClick(self.d.view, Qt.Key.Key_Left, Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual(TX.char_fx(self.t), {1: {'kern': -5.0}})

    def test_alt_up_moves_up(self):
        self.d.select(1)
        QTest.keyClick(self.d.view, Qt.Key.Key_Up, Qt.KeyboardModifier.AltModifier)
        self.assertEqual(TX.char_fx(self.t), {1: {'dy': 1.0}})

    def test_plain_arrow_moves_the_caret(self):
        self.d.select(1)
        QTest.keyClick(self.d.view, Qt.Key.Key_Right)
        self.assertEqual(self.d.indices(), [2])
        self.assertEqual(self.calls, [])

    def test_cancel_goes_back(self):
        t = with_fx('HHHH', {0: {'kern': 3.0}})
        calls = []

        def apply(fx):
            calls.append(fx)
            TX.set_char_fx(t, fx)
        d = LettersDialog(None, t, apply)
        d.select(1)
        d.fields['h'].setValue(50.0)
        d.reject()
        self.assertEqual(TX.char_fx(t), {0: {'kern': 3.0}})

    def test_cancel_with_nothing_done(self):
        self.d.reject()
        self.assertEqual(self.calls, [])


class TestWindow(unittest.TestCase):
    def setUp(self):
        self.w = MainWindow()
        self.t = make('HHHH')
        self.w.canvas.doc.layers[0].items[:] = [self.t]
        self.w.canvas.invalidate()
        self.w.canvas.select([self.t])

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_changes_the_drawing_and_undoes_at_once(self):
        d = self.w.text_letters_dialog(exec_dialog=False)
        d.select(1)
        d.fields['kern'].setValue(20.0)
        d.fields['h'].setValue(50.0)
        d.accept()
        item = self.w.canvas.doc.layers[0].items[0]
        self.assertEqual(TX.char_fx(item), {1: {'kern': 20.0, 'h': 50.0}})
        self.assertNotEqual(item.outline.bbox(), make('HHHH').outline.bbox())
        self.w.undo()
        item = self.w.canvas.doc.layers[0].items[0]
        self.assertEqual(TX.char_fx(item), {})
        self.assertEqual(item.outline.bbox(), make('HHHH').outline.bbox())

    def test_no_undo_step_without_change(self):
        n = len(self.w._undo)
        d = self.w.text_letters_dialog(exec_dialog=False)
        d.select(1)
        d.accept()
        self.assertEqual(len(self.w._undo), n)

    def test_needs_one_text(self):
        self.w.canvas.select([])
        self.assertIsNone(self.w.text_letters_dialog(exec_dialog=False))

    def test_two_texts_refused(self):
        other = make('A')
        self.w.canvas.doc.layers[0].items.append(other)
        self.w.canvas.select([self.t, other])
        self.assertIsNone(self.w.text_letters_dialog(exec_dialog=False))

    def test_curved_text_opens_too(self):
        self.t.extra['arc'] = {'center': (0, 0), 'radius': 20.0}
        self.assertIsNotNone(self.w.text_letters_dialog(exec_dialog=False))

    def test_retext_follows(self):
        d = self.w.text_letters_dialog(exec_dialog=False)
        d.select(1)
        d.fields['kern'].setValue(20.0)
        d.accept()
        item = self.w.canvas.doc.layers[0].items[0]
        self.w._retext([(item, 'xHHHH')])
        self.assertEqual(TX.char_fx(item), {2: {'kern': 20.0}})

    def test_in_the_ribbon(self):
        a = self.w.A['text_letters']
        self.assertFalse(a.icon().isNull())
        self.assertTrue(a.toolTip())
        pages = [self.w.ribbon.page(i) for i in range(self.w.ribbon.count())]
        n = sum(1 for page in pages if page for g in page.groups() for b in g.buttons() if b.defaultAction() is a)
        self.assertEqual(n, 1)


if __name__ == '__main__':
    unittest.main()
