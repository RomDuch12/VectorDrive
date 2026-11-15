"""Round 794 : les espacements du Rapido : crénage à cinq modes, trois interlignes, casse initiale."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from vectordrive.core import fonts
from vectordrive.core import text as TX
from vectordrive.core.document import Text

FONT = 'VD Trait'


def second_font():
    for name in ('Arial', 'DejaVu Sans', 'Liberation Sans', 'Segoe UI', 'Times New Roman', 'Verdana', 'Tahoma'):
        if fonts.is_available(name):
            return name
    return None


REAL = second_font()


def make(text='HH', font=FONT, size=10.0, **extra):
    t = Text(text=text, font=font, size=size)
    t.extra.update(extra)
    t.outline = TX.outline_for(t)
    return t


def ink(font=FONT, ch='H', size=10.0):
    box = TX.layout(ch, font, size, kerning=False).bbox()
    return box[0], box[2]


class TestTight(unittest.TestCase):
    def test_first_letter_starts_at_zero(self):
        got = TX.layout('H', FONT, 10.0, kerning=False, tight=True).bbox()
        self.assertAlmostEqual(got[0], 0.0, places=7)

    def test_letters_touch(self):
        x0, x1 = ink()
        got = TX.layout('HH', FONT, 10.0, kerning=False, tight=True).bbox()
        self.assertAlmostEqual(got[2], 2 * (x1 - x0), places=6)

    def test_extra_spacing_adds(self):
        x0, x1 = ink()
        got = TX.layout('HH', FONT, 10.0, kerning=False, tight=True, spacing=3.0).bbox()
        self.assertAlmostEqual(got[2], 2 * (x1 - x0) + 3.0, places=6)

    def test_space_keeps_its_place(self):
        plain = TX.layout('HH', FONT, 10.0, kerning=False, tight=True).bbox()
        spaced = TX.layout('H H', FONT, 10.0, kerning=False, tight=True).bbox()
        self.assertGreater(spaced[2], plain[2] + 1.0)

    def test_tighter_than_proportional(self):
        loose = TX.layout('HH', FONT, 10.0, kerning=False).bbox()
        tight = TX.layout('HH', FONT, 10.0, kerning=False, tight=True).bbox()
        self.assertLess(tight[2], loose[2])

    def test_each_line_alone(self):
        got = TX.layout('H\nHH', FONT, 10.0, kerning=False, tight=True).bbox()
        x0, x1 = ink()
        self.assertAlmostEqual(got[2], 2 * (x1 - x0), places=6)

    @unittest.skipUnless(REAL, 'pas de police sur cette machine')
    def test_kerning_counts_with_tight_kern(self):
        for pair in ('AV', 'To', 'VA', 'AT'):
            a = TX.layout(pair, REAL, 10.0, kerning=True, tight=True).bbox()
            b = TX.layout(pair, REAL, 10.0, kerning=False, tight=True).bbox()
            self.assertLessEqual(a[2], b[2] + 1e-9)


class TestModesOfAnItem(unittest.TestCase):
    def test_outline_by_mode(self):
        seen = {}
        for mode in TX.SPACING_MODES:
            t = make('HIH', spacing_mode=mode)
            seen[mode] = t.outline.bbox()[2]
        self.assertLess(seen['tight'], seen['prop'])
        self.assertLess(seen['tight_kern'], seen['typo'] + 1e-9)
        self.assertGreater(seen['fixed'], seen['tight'])

    def test_five_modes_in_the_order_of_the_manual(self):
        self.assertEqual(TX.SPACING_MODES, ('typo', 'prop', 'tight_kern', 'tight', 'fixed'))

    def test_max_length_counts_them(self):
        full = make('HHHH', spacing_mode='tight').outline.bbox()[2]
        t = make('HHHH', spacing_mode='tight', max_length={'length': full / 2, 'by': 'line'})
        self.assertAlmostEqual(t.outline.bbox()[2], full / 2, places=5)

    def test_underline_follows_the_letters(self):
        t = make('HH', spacing_mode='tight', underline=True)
        plain = make('HH', spacing_mode='tight')
        self.assertAlmostEqual(t.outline.bbox()[2], plain.outline.bbox()[2], places=6)

    def test_on_a_curve_nothing_breaks(self):
        from vectordrive.core.geom import Contour, Line
        t = make('HH', spacing_mode='tight', on_path=Contour([Line((0, 0), (100, 0))], False))
        self.assertTrue(t.outline.contours)


class TestLineRatio(unittest.TestCase):
    def pitch(self, t):
        t.outline = TX.outline_for(t)
        return TX.em_for_height(fonts.find_font(t.font), t.size) * t.line_spacing

    def test_none_without_mode(self):
        self.assertIsNone(TX.line_ratio(Text(text='H', font=FONT, size=10.0)))

    def test_fixed_is_the_distance_between_baselines(self):
        t = make('H\nH', line_mode={'mode': 'fixed', 'value': 17.0})
        self.assertAlmostEqual(self.pitch(t), 17.0, places=7)
        box = t.outline.bbox()
        self.assertAlmostEqual(box[3] - box[1], 17.0 + 10.0, places=6)

    def test_fixed_does_not_follow_the_height(self):
        t = make('H\nH', line_mode={'mode': 'fixed', 'value': 17.0})
        t.size = 5.0
        self.assertAlmostEqual(self.pitch(t), 17.0, places=7)

    def test_proportional_adds_to_the_height(self):
        t = make('H\nH', line_mode={'mode': 'prop', 'value': 75.0})
        self.assertAlmostEqual(self.pitch(t), 17.5, places=7)

    def test_proportional_zero_makes_lines_touch(self):
        t = make('H\nH', line_mode={'mode': 'prop', 'value': 0.0})
        box = t.outline.bbox()
        self.assertAlmostEqual(box[3] - box[1], 20.0, places=6)

    def test_proportional_follows_the_height(self):
        t = make('H\nH', line_mode={'mode': 'prop', 'value': 75.0})
        t.size = 20.0
        self.assertAlmostEqual(self.pitch(t), 35.0, places=7)

    def test_typographic_is_the_whole_height_of_the_font(self):
        t = make('H\nH', line_mode={'mode': 'typo', 'value': 100.0})
        ff = fonts.find_font(FONT)
        m = fonts.metrics(*ff)
        em = TX.em_for_height(ff, 10.0)
        self.assertAlmostEqual(self.pitch(t), (m['ascent'] + abs(m['descent'])) / m['upem'] * em, places=6)

    def test_typographic_half(self):
        full = self.pitch(make('H\nH', line_mode={'mode': 'typo', 'value': 100.0}))
        half = self.pitch(make('H\nH', line_mode={'mode': 'typo', 'value': 50.0}))
        self.assertAlmostEqual(half, full / 2, places=7)

    def test_nonsense_is_left_alone(self):
        t = make('H\nH', line_mode={'mode': 'autre', 'value': 5.0})
        self.assertEqual(t.line_spacing, 1.2)

    def test_font_change_keeps_fixed_distance(self):
        t = make('H\nH', line_mode={'mode': 'fixed', 'value': 17.0})
        if REAL:
            t.font = REAL
            self.assertAlmostEqual(self.pitch(t), 17.0, places=7)

    def test_saved_in_native(self):
        from vectordrive.core.document import Document
        from vectordrive.io import registry
        t = make('H\nH', line_mode={'mode': 'prop', 'value': 40.0})
        doc = Document()
        doc.add(t)
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, 'a.vdz')
            registry.save_document(doc, f)
            back = next(iter(registry.open_document(f).iter_leaves()))
        self.assertEqual(back.extra['line_mode'], {'mode': 'prop', 'value': 40.0})

    def test_copied_with_the_format(self):
        a = make('H\nH', line_mode={'mode': 'fixed', 'value': 17.0})
        b = make('X\nX', size=20.0)
        TX.apply_format(b, TX.text_format(a))
        self.assertEqual(b.extra['line_mode'], {'mode': 'fixed', 'value': 17.0})


class WindowCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        self.w.settings.remove('cad/line_fixed')
        self.w.settings.remove('cad/line_prop')
        self.w.settings.remove('cad/line_typo')
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()

    def put(self, *texts):
        self.w.canvas.doc.layers[0].items[:] = list(texts)
        self.w.canvas.invalidate()
        self.w.canvas.select(list(texts))
        return texts[0]

    def current(self):
        return self.w.canvas.doc.layers[0].items[0]


class TestSpacingCommands(WindowCase):
    def test_set_tight(self):
        t = self.put(make('HH'))
        before = t.outline.bbox()[2]
        self.w.set_spacing_mode('tight')
        self.assertEqual(t.extra['spacing_mode'], 'tight')
        self.assertLess(t.outline.bbox()[2], before)

    def test_cycle_goes_round(self):
        t = self.put(make('HH'))
        seen = []
        for _ in range(5):
            self.w.next_spacing_mode()
            seen.append(t.extra.get('spacing_mode', 'typo'))
        self.assertEqual(seen, ['prop', 'tight_kern', 'tight', 'fixed', 'typo'])

    def test_cycle_says_it(self):
        self.put(make('HH'))
        self.w.next_spacing_mode()
        self.assertEqual(self.w.statusBar().currentMessage(), self.w.A['spacing_prop'].text())

    def test_cycle_uses_the_first_text(self):
        a, b = make('HH', spacing_mode='tight'), make('HH')
        self.put(a, b)
        self.w.next_spacing_mode()
        self.assertEqual(a.extra['spacing_mode'], 'fixed')
        self.assertEqual(b.extra['spacing_mode'], 'fixed')

    def test_cycle_undo(self):
        self.put(make('HH'))
        self.w.next_spacing_mode()
        self.w.undo()
        self.assertNotIn('spacing_mode', self.current().extra)

    def test_cycle_without_text(self):
        self.w.canvas.select([])
        self.assertEqual(self.w.next_spacing_mode(), [])


class TestLineCommands(WindowCase):
    def test_fixed(self):
        t = self.put(make('H\nH'))
        self.assertEqual(self.w.set_line_mode('fixed', {'value': 17.0}), [t])
        box = t.outline.bbox()
        self.assertAlmostEqual(box[3] - box[1], 27.0, places=6)

    def test_undo(self):
        self.put(make('H\nH'))
        self.w.set_line_mode('fixed', {'value': 17.0})
        self.w.undo()
        self.assertNotIn('line_mode', self.current().extra)
        self.assertEqual(self.current().line_spacing, 1.2)

    def test_limits(self):
        t = self.put(make('H\nH'))
        self.w.set_line_mode('typo', {'value': -5.0})
        self.assertEqual(t.extra['line_mode']['value'], 0.0)
        self.w.set_line_mode('prop', {'value': -500.0})
        self.assertEqual(t.extra['line_mode']['value'], -100.0)

    def test_starts_from_the_present_distance(self):
        t = self.put(make('H\nH'))
        got = {}
        real = self.w._ask

        def ask(key, title, spec, choices=None, params=None):
            got['value'] = spec[0][2]
            return None
        self.w._ask = ask
        try:
            self.assertEqual(self.w.set_line_mode('fixed', {'value': 1.0}), [])
        finally:
            self.w._ask = real
            self.w.settings.remove('cad/line_fixed')
        self.assertAlmostEqual(got['value'], TX.em_for_height(fonts.find_font(FONT), 10.0) * 1.2, places=7)
        self.assertNotIn('line_mode', t.extra)

    def test_box_text_is_left_alone(self):
        t = make('H\nH', box={'x0': 0, 'y0': 0, 'x1': 50, 'y1': 50})
        self.put(t)
        self.assertEqual(self.w.set_line_mode('fixed', {'value': 17.0}), [])
        self.assertNotIn('line_mode', t.extra)

    def test_value_in_the_bar_replaces_the_mode(self):
        t = self.put(make('H\nH'))
        self.w.set_line_mode('fixed', {'value': 17.0})
        self.w.textbar.apply('line_spacing', 2.0)
        self.assertNotIn('line_mode', t.extra)
        self.assertEqual(t.line_spacing, 2.0)
        self.assertEqual(TX.outline_for(t).bbox(), t.outline.bbox())

    def test_commands_in_the_format_tab(self):
        for k in ('line_fixed', 'line_prop', 'line_typo', 'case_initial', 'spacing_tight', 'spacing_tight_kern'):
            self.assertIn(k, self.w.A)


class TestCaseInitial(WindowCase):
    def test_upper_then_back(self):
        t = self.put(make('Mon Texte'))
        self.w.change_text_case('upper')
        self.assertEqual(t.text, 'MON TEXTE')
        self.assertEqual(self.w.restore_text_case(), 1)
        self.assertEqual(t.text, 'Mon Texte')
        self.assertNotIn('case_source', t.extra)

    def test_several_changes_go_back_to_the_first(self):
        t = self.put(make('Mon Texte'))
        for mode in ('upper', 'lower', 'words', 'lower'):
            self.w.change_text_case(mode)
        self.w.restore_text_case()
        self.assertEqual(t.text, 'Mon Texte')

    def test_small_caps_removed(self):
        t = self.put(make('Mon Texte', small_caps=True))
        self.assertEqual(self.w.restore_text_case(), 1)
        self.assertNotIn('small_caps', t.extra)
        self.assertEqual(t.text, 'Mon Texte')

    def test_text_retouched_keeps_its_letters(self):
        t = self.put(make('Mon Texte'))
        self.w.change_text_case('upper')
        t.text = 'AUTRE CHOSE'
        self.assertEqual(self.w.restore_text_case(), 0)
        self.assertEqual(t.text, 'AUTRE CHOSE')

    def test_retouched_then_changed_starts_again(self):
        t = self.put(make('Mon Texte'))
        self.w.change_text_case('upper')
        t.text = 'Autre Chose'
        self.w.change_text_case('upper')
        self.w.restore_text_case()
        self.assertEqual(t.text, 'Autre Chose')

    def test_nothing_changed_nothing_to_do(self):
        t = self.put(make('Mon Texte'))
        self.assertEqual(self.w.restore_text_case(), 0)
        self.assertEqual(t.text, 'Mon Texte')

    def test_undo(self):
        self.put(make('Mon Texte'))
        self.w.change_text_case('upper')
        self.w.restore_text_case()
        self.w.undo()
        self.assertEqual(self.current().text, 'MON TEXTE')

    @unittest.skipUnless(REAL, 'pas de police à minuscules sur cette machine')
    def test_outline_redrawn(self):
        t = self.put(make('abc', font=REAL))
        low = t.outline.bbox()
        self.w.change_text_case('upper')
        self.assertNotEqual(t.outline.bbox(), low)
        self.w.restore_text_case()
        self.assertEqual(t.outline.bbox(), low)


class TestLinks(unittest.TestCase):
    def test_commands(self):
        from vectordrive.ui.shortcuts import TE_ACTIONS
        for cmd, key in (('ID_RAPIDO_LINE_BTNESPFIXE_DLL', 'line_fixed'), ('ID_RAPIDO_LINE_BTNESPPROP_DLL', 'line_prop'),
                         ('ID_RAPIDO_LINE_BTNESPPROPTYPO_DLL', 'line_typo'), ('IDB_INTERLIGNAGE_CONSTANT', 'line_fixed'),
                         ('IDB_INTERLIGNAGE_PROPORTIONNEL', 'line_prop'), ('IDB_INTERLIGNAGE_TYPOGRAPHIQUE', 'line_typo'),
                         ('ID_RAPIDO_Kernel', 'text_kern_cycle'), ('ID_RAPIDO_CHAR_PBMAJMIN_DLL', 'case_initial'),
                         ('IDB_MAJUSCULES_MINUSCULES', 'case_initial'), ('ID_RAPIDO_CHAR_PBDBLSPACE_DLL', 'text_letters')):
            self.assertEqual(TE_ACTIONS[cmd], key)


if __name__ == '__main__':
    unittest.main()
