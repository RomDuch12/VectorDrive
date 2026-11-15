"""Round 792 : l'éditeur de polices."""
import os
import pathlib
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from vectordrive.core import fontedit as FE
from vectordrive.core import fonts, svgfonts
from vectordrive.core import text as TX
from vectordrive.core.document import Shape, Text
from vectordrive.core.geom import Contour, Line, Path, circle, polyline, rect


def square(x=0.0, y=0.0, w=70.0, h=100.0):
    return Path([rect(x, y, w, h)])


def stroke():
    """Un trait ouvert : ce qui fait une police monotrait."""
    return Path([polyline([(0, 0), (50, 100), (100, 0)], False)])


class Isolated(unittest.TestCase):
    """Le dossier des polices de l'utilisateur est un dossier d'essai ; on le rend à la fin."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.environ.get('VECTORDRIVE_CACHE')
        os.environ['VECTORDRIVE_CACHE'] = self.tmp.name
        fonts.font_changed()

    def tearDown(self):
        fonts.font_changed()                             # tant que l'inventaire visé est celui de l'essai
        if self.old is None:
            del os.environ['VECTORDRIVE_CACHE']
        else:
            os.environ['VECTORDRIVE_CACHE'] = self.old
        fonts.refresh()
        self.tmp.cleanup()

    def folder(self) -> pathlib.Path:
        return fonts.user_font_dir()


def draft(name='Essai Editeur'):
    d = FE.Draft(name=name)
    d.put(ord('H'), square(), 80.0, 100.0)
    d.put(ord('I'), stroke(), 110.0, 100.0)
    return d


class TestDraft(unittest.TestCase):
    def test_scale_from_cap_height(self):
        d = draft()
        self.assertEqual(d.glyph_units(ord('H')).bbox(), (0.0, 0.0, 490.0, 700.0))
        self.assertAlmostEqual(d.glyphs[ord('H')][1], 560.0)

    def test_back_in_mm(self):
        d = draft()
        for a, b in zip(d.glyph_mm(ord('H'), 100.0).bbox(), (0, 0, 70, 100)):
            self.assertAlmostEqual(a, b, places=3)
        self.assertAlmostEqual(d.adv_mm(ord('H'), 100.0), 80.0)

    def test_other_cap_height(self):
        d = FE.Draft()
        d.put(ord('H'), square(h=10.0, w=7.0), 8.0, 10.0)
        self.assertEqual(d.glyph_units(ord('H')).bbox(), (0.0, 0.0, 490.0, 700.0))

    def test_y_stays_up(self):
        d = FE.Draft()
        d.put(ord('g'), square(y=-20.0, h=50.0), 80.0, 100.0)
        box = d.glyph_units(ord('g')).bbox()
        self.assertAlmostEqual(box[1], -140.0)
        self.assertAlmostEqual(box[3], 210.0)

    def test_open_stays_open(self):
        d = draft()
        self.assertFalse(d.glyph_units(ord('I')).contours[0].closed)
        self.assertTrue(d.glyph_units(ord('H')).contours[0].closed)

    def test_circle_keeps_its_box(self):
        d = FE.Draft()
        d.put(ord('O'), Path([circle((50, 50), 50)]), 110.0, 100.0)
        for a, b in zip(d.glyph_mm(ord('O'), 100.0).bbox(), (0, 0, 100, 100)):
            self.assertAlmostEqual(a, b, places=2)

    def test_remove_takes_its_pairs(self):
        d = draft()
        d.set_kern(ord('H'), ord('I'), -5.0, 100.0)
        d.remove(ord('H'))
        self.assertNotIn(ord('H'), d.glyphs)
        self.assertEqual(d.kern, {})

    def test_kern_zero_removes(self):
        d = draft()
        d.set_kern(ord('H'), ord('I'), -5.0, 100.0)
        self.assertAlmostEqual(d.kern_mm(ord('H'), ord('I'), 100.0), -5.0)
        d.set_kern(ord('H'), ord('I'), 0.0, 100.0)
        self.assertEqual(d.kern, {})

    def test_sample_text(self):
        d = draft()
        self.assertAlmostEqual(d.text_units('HH').bbox()[2], 560.0 + 490.0)
        d.set_kern(ord('H'), ord('H'), -10.0, 100.0)
        self.assertAlmostEqual(d.text_units('HH').bbox()[2], 490.0 + 490.0)

    def test_sample_ignores_missing(self):
        self.assertEqual(draft().text_units('?').contours, [])


class TestPlaced(unittest.TestCase):
    def test_on_line(self):
        self.assertEqual(FE.placed(square(30, 40), True).bbox(), (0.0, 0.0, 70.0, 100.0))

    def test_before(self):
        self.assertEqual(FE.placed(square(30, 40), True, 5.0).bbox(), (5.0, 0.0, 75.0, 100.0))

    def test_in_place(self):
        self.assertEqual(FE.placed(square(30, -40), False, 5.0).bbox(), (30.0, -40.0, 100.0, 60.0))

    def test_empty(self):
        self.assertEqual(FE.placed(Path(), True).contours, [])


class TestChars(unittest.TestCase):
    def test_valid(self):
        for ch in ('A', 'é', ' ', '\u00a0', '€', '<', '&', '"', "'", ',', '\U0001F600'):
            self.assertTrue(FE.valid_char(ch), repr(ch))

    def test_invalid(self):
        for ch in ('', 'AB', '\t', '\n', '\x01', '\x85', '\u2028', '\ufffe', '\ud800'):
            self.assertFalse(FE.valid_char(ch), repr(ch))


class TestFile(Isolated):
    def test_read_by_svgfonts(self):
        p = self.folder() / 'a.svg'
        draft().save(p)
        f = svgfonts.SvgFont(str(p))
        self.assertEqual(f.name, 'Essai Editeur')
        self.assertEqual(set(f.index), {ord('H'), ord('I')})
        self.assertAlmostEqual(f.cap, 0.7)

    def test_round_trip(self):
        p = self.folder() / 'a.svg'
        d = draft()
        d.set_kern(ord('H'), ord('I'), -5.0, 100.0)
        d.save(p)
        back = FE.load(p)
        self.assertEqual(back.name, d.name)
        self.assertEqual(back.glyphs[ord('H')][0], d.glyphs[ord('H')][0])
        self.assertAlmostEqual(back.glyphs[ord('H')][1], d.glyphs[ord('H')][1])
        self.assertAlmostEqual(back.kern[(ord('H'), ord('I'))], d.kern[(ord('H'), ord('I'))])
        self.assertAlmostEqual(back.cap, 700.0)

    def test_second_save_identical(self):
        p = self.folder() / 'a.svg'
        draft().save(p)
        first = p.read_bytes()
        FE.load(p).save(p)
        self.assertEqual(p.read_bytes(), first)

    def test_awkward_characters(self):
        p = self.folder() / 'a.svg'
        d = FE.Draft(name='N')
        codes = [ord(c) for c in '<>&"\', \U0001F600\u00a0']
        for c in codes:
            d.put(c, square(), 80.0, 100.0)
        d.set_kern(ord(','), ord('"'), -5.0, 100.0)
        d.save(p)
        back = svgfonts.SvgFont(str(p))
        self.assertEqual(set(back.index), set(codes))
        self.assertAlmostEqual(back.kerning(ord(','), ord('"')), -0.035)

    def test_awkward_names(self):
        for name in ('Ma police d’atelier', "Ma police d'atelier", 'A & B', 'A "B"', 'Été <1>'):
            p = self.folder() / 'n.svg'
            FE.Draft(name=name, glyphs={65: ('', 500.0)}).save(p)
            self.assertEqual(svgfonts.font_name(p), name)
            self.assertEqual(svgfonts.SvgFont(str(p)).name, name)

    def test_kerning_sign_like_the_reader(self):
        p = self.folder() / 'a.svg'
        d = draft()
        d.set_kern(ord('H'), ord('I'), -10.0, 100.0)
        d.save(p)
        self.assertAlmostEqual(svgfonts.SvgFont(str(p)).kerning(ord('H'), ord('I')), -0.07)

    def test_failed_write_keeps_the_file(self):
        p = self.folder() / 'a.svg'
        draft().save(p)
        before = p.read_bytes()
        with mock.patch.object(FE.Draft, 'to_svg', side_effect=OSError('plein')):
            with self.assertRaises(OSError):
                draft('Autre').save(p)
        self.assertEqual(p.read_bytes(), before)
        self.assertEqual([f.name for f in self.folder().iterdir()], ['a.svg'])

    def test_no_font_in_a_drawing(self):
        p = self.folder() / 'dessin.svg'
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>', encoding='utf-8')
        with self.assertRaises(ValueError):
            FE.load(p)

    def test_broken_file(self):
        p = self.folder() / 'casse.svg'
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('<svg', encoding='utf-8')
        with self.assertRaises(ET.ParseError):
            FE.load(p)


class TestFileNames(Isolated):
    def test_plain(self):
        self.assertEqual(FE.file_for('Ma police', self.folder()).name, 'Ma police.svg')

    def test_forbidden_characters(self):
        self.assertEqual(FE.file_for('A:B/C?', self.folder()).name, 'A_B_C_.svg')

    def test_reserved_name(self):
        self.assertEqual(FE.file_for('con', self.folder()).name, '_con.svg')

    def test_only_dots(self):
        self.assertEqual(FE.file_for('...', self.folder()).name, 'police.svg')

    def test_no_overwrite(self):
        p = self.folder() / 'A_B.svg'
        draft('A_B').save(p)
        self.assertEqual(FE.file_for('A:B', self.folder()).name, 'A_B 2.svg')

    def test_long_name(self):
        self.assertLessEqual(len(FE.file_for('x' * 500, self.folder()).name), 104)


class TestWithText(Isolated):
    def saved(self, d=None):
        d = d or draft()
        p = self.folder() / 'Essai Editeur.svg'
        d.save(p)
        fonts.font_changed()
        return p

    def test_listed(self):
        self.saved()
        self.assertIn('Essai Editeur', fonts.svg_families())
        self.assertTrue(fonts.is_available('Essai Editeur'))

    def test_text_height(self):
        self.saved()
        box = TX.layout('H', 'Essai Editeur', 10.0, kerning=False).bbox()
        self.assertAlmostEqual(box[3] - box[1], 10.0, places=6)

    def test_text_advance(self):
        self.saved()
        box = TX.layout('HH', 'Essai Editeur', 10.0, kerning=False).bbox()
        self.assertAlmostEqual(box[2], 8.0 + 7.0, places=6)

    def test_kerning_used_by_the_text(self):
        d = draft()
        d.set_kern(ord('H'), ord('H'), -10.0, 100.0)
        self.saved(d)
        box = TX.layout('HH', 'Essai Editeur', 10.0, kerning=True).bbox()
        self.assertAlmostEqual(box[2], 7.0 + 7.0, places=6)

    def test_single_line_font_stays_open(self):
        self.saved()
        got = TX.layout('I', 'Essai Editeur', 10.0, kerning=False)
        self.assertFalse(got.contours[0].closed)

    def test_rewrite_is_seen_at_once(self):
        p = self.saved()
        TX.layout('H', 'Essai Editeur', 10.0, kerning=False)
        fonts.characters('Essai Editeur')
        d = FE.load(p)
        d.put(ord('H'), square(w=140.0), 150.0, 100.0)
        d.put(ord('Z'), square(), 80.0, 100.0)
        d.save(p)
        fonts.font_changed()
        self.assertAlmostEqual(TX.layout('H', 'Essai Editeur', 10.0, kerning=False).bbox()[2], 14.0, places=6)
        self.assertIn('Z', fonts.characters('Essai Editeur'))

    def test_name_taken(self):
        p = self.saved()
        self.assertTrue(FE.name_taken('Essai Editeur'))
        self.assertFalse(FE.name_taken('Essai Editeur', p))
        self.assertTrue(FE.name_taken('essai  editeur', self.folder() / 'autre.svg'))
        self.assertFalse(FE.name_taken('Absente De Partout'))

    def test_builtin_name_taken(self):
        self.assertTrue(FE.name_taken('VD Trait'))

    def test_clone_svg(self):
        self.saved()
        got = FE.clone('Essai Editeur', 'Copie')
        self.assertEqual(got.name, 'Copie')
        self.assertEqual(set(got.glyphs), {ord('H'), ord('I')})
        self.assertAlmostEqual(got.glyphs[ord('H')][1], 560.0)

    def test_clone_picks_characters(self):
        self.saved()
        self.assertEqual(set(FE.clone('Essai Editeur', 'Copie', chars='HX').glyphs), {ord('H')})

    def test_clone_stroke_font(self):
        got = FE.clone('VD Trait', 'Copie', chars='HI ')
        self.assertEqual(set(got.glyphs), {ord('H'), ord('I'), ord(' ')})
        self.assertFalse(got.glyph_units(ord('I')).contours[0].closed)
        box = got.glyph_units(ord('H')).bbox()
        self.assertAlmostEqual(box[3], got.cap, places=2)

    def test_clone_refused_for_plugin_fonts(self):
        from vectordrive.core import fontformats
        fmt = fontformats.FontFormat('Essai', ('.essai792',), font_name=lambda p: None, glyph=lambda p, c: None,
                                     metrics=lambda p: {})
        with mock.patch.dict(fontformats.FORMATS, {'.essai792': fmt}), \
                mock.patch.object(fonts, 'is_available', return_value=True), \
                mock.patch.object(fonts, 'find_font', return_value=('C:/x/police.essai792', 0)):
            self.assertFalse(FE.can_clone('X'))
            fmt.clonable = True
            self.assertTrue(FE.can_clone('X'))
        self.assertFalse(FE.can_clone('Absente De Partout'))
        self.assertTrue(FE.can_clone('VD Trait'))


class WindowCase(Isolated):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.d = self.w.font_editor()
        self.layer = self.w.canvas.doc.layers[0]
        self.layer.items[:] = []

    def tearDown(self):
        self.d.dirty = False
        self.d.close()
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        super().tearDown()

    def draw(self, path):
        s = Shape(path=path)
        self.layer.items.append(s)
        self.w.canvas.invalidate()
        self.w.canvas.select([s])
        return s

    def add(self, ch, path):
        self.draw(path)
        self.d.char_edit.setText(ch)
        return self.d.add_selection()


class TestEditor(WindowCase):
    def test_one_window(self):
        self.assertIs(self.w.font_editor(), self.d)
        self.assertFalse(self.d.isModal())

    def test_action_in_the_ribbon(self):
        self.assertIn('font_editor', self.w.A)
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual(TE_ACTIONS['ID_COMPO_TEXTEEDITFONT'], 'font_editor')

    def test_add_selection(self):
        self.assertTrue(self.add('H', square(30, 40)))
        self.assertEqual(self.d.draft.glyph_mm(ord('H'), 100.0).bbox()[:2], (0.0, 0.0))
        self.assertAlmostEqual(self.d.draft.adv_mm(ord('H'), 100.0), 80.0)
        self.assertTrue(self.d.dirty)
        self.assertEqual(self.d.current_code(), ord('H'))
        self.assertEqual(self.d.list.count(), 1)

    def test_keeps_the_drawing(self):
        s = self.draw(square())
        self.d.char_edit.setText('H')
        self.d.add_selection()
        self.assertEqual(self.layer.items, [s])

    def test_spaces_settings(self):
        self.d.before.setValue(5.0)
        self.d.after.setValue(20.0)
        self.add('H', square())
        self.assertAlmostEqual(self.d.draft.glyph_mm(ord('H'), 100.0).bbox()[0], 5.0, places=3)
        self.assertAlmostEqual(self.d.draft.adv_mm(ord('H'), 100.0), 95.0)

    def test_in_place_for_a_descender(self):
        self.d.place.setCurrentIndex(1)
        self.add('g', square(y=-30.0, h=80.0))
        self.assertAlmostEqual(self.d.draft.glyph_mm(ord('g'), 100.0).bbox()[1], -30.0, places=3)

    def test_group_and_text_selection(self):
        from vectordrive.core.document import Group
        a, b = Shape(path=square()), Shape(path=square(x=100.0))
        g = Group(children=[a, b])
        self.layer.items.append(g)
        self.w.canvas.select([g])
        self.d.char_edit.setText('H')
        self.assertTrue(self.d.add_selection())
        self.assertEqual(len(self.d.draft.glyph_units(ord('H')).contours), 2)
        t = Text(text='H', font='VD Trait', size=100.0)
        t.outline = TX.outline_for(t)
        self.layer.items.append(t)
        self.w.canvas.select([t])
        self.d.char_edit.setText('T')
        self.assertTrue(self.d.add_selection())
        self.assertTrue(self.d.draft.glyph_units(ord('T')).contours)

    def test_needs_one_character(self):
        self.draw(square())
        for bad in ('', 'AB'):
            self.d.char_edit.setText(bad)
            with mock.patch('vectordrive.ui.font_editor.QMessageBox.information') as said:
                self.assertFalse(self.d.add_selection())
            said.assert_called_once()
        self.assertEqual(self.d.draft.glyphs, {})

    def test_needs_a_selection(self):
        self.w.canvas.select([])
        self.d.char_edit.setText('H')
        with mock.patch('vectordrive.ui.font_editor.QMessageBox.information') as said:
            self.assertFalse(self.d.add_selection())
        said.assert_called_once()

    def test_space_without_drawing(self):
        self.w.canvas.select([])
        self.d.char_edit.setText(' ')
        self.assertTrue(self.d.add_selection())
        self.assertAlmostEqual(self.d.draft.adv_mm(32, 100.0), 30.0)
        self.assertEqual(self.d.draft.glyphs[32][0], '')

    def test_replace_asks(self):
        from PySide6.QtWidgets import QMessageBox
        self.add('H', square())
        with mock.patch('vectordrive.ui.font_editor.QMessageBox.question', return_value=QMessageBox.StandardButton.No):
            self.assertFalse(self.add('H', square(w=10.0)))
        self.assertAlmostEqual(self.d.draft.glyph_mm(ord('H'), 100.0).bbox()[2], 70.0, places=3)
        with mock.patch('vectordrive.ui.font_editor.QMessageBox.question', return_value=QMessageBox.StandardButton.Yes):
            self.assertTrue(self.add('H', square(w=10.0)))
        self.assertAlmostEqual(self.d.draft.glyph_mm(ord('H'), 100.0).bbox()[2], 10.0, places=3)

    def test_picking_fills_the_fields(self):
        self.add('H', square())
        self.add('I', stroke())
        self.d.list.setCurrentRow(0)
        self.assertEqual(self.d.char_edit.text(), 'H')
        self.assertAlmostEqual(self.d.adv_box.value(), 80.0)
        self.assertEqual(self.d.code_label.text(), 'U+0048')

    def test_change_the_width(self):
        self.add('H', square())
        self.d.dirty = False
        self.d.adv_box.setValue(90.0)
        self.d.set_adv()
        self.assertAlmostEqual(self.d.draft.adv_mm(ord('H'), 100.0), 90.0)
        self.assertTrue(self.d.dirty)

    def test_same_width_changes_nothing(self):
        self.add('H', square())
        self.d.dirty = False
        self.d.set_adv()
        self.assertFalse(self.d.dirty)

    def test_nothing_chosen_disables(self):
        self.assertFalse(self.d.insert_button.isEnabled())
        self.assertFalse(self.d.delete_button.isEnabled())
        self.assertFalse(self.d.adv_box.isEnabled())
        self.add('H', square())
        self.assertTrue(self.d.insert_button.isEnabled())

    def test_insert_then_add_again_stays_the_same(self):
        self.d.place.setCurrentIndex(1)
        self.d.after.setValue(13.0)
        self.add('g', square(y=-30.0, h=80.0))
        before = self.d.draft.glyphs[ord('g')]
        self.layer.items[:] = []
        got = self.d.insert_glyph()
        self.assertIs(self.layer.items[0], got)
        self.assertEqual(self.w.canvas.selection, [got])
        self.assertEqual(self.d.place.currentIndex(), 1)
        self.assertAlmostEqual(self.d.after.value(), 13.0, places=3)
        from PySide6.QtWidgets import QMessageBox
        with mock.patch('vectordrive.ui.font_editor.QMessageBox.question', return_value=QMessageBox.StandardButton.Yes):
            self.assertTrue(self.d.add_selection())
        after = self.d.draft.glyphs[ord('g')]
        self.assertEqual(self.d.draft.glyph_units(ord('g')).bbox(), FE._parsed(before[0]).bbox())
        self.assertAlmostEqual(after[1], before[1], places=2)

    def test_insert_is_undone(self):
        self.add('H', square())
        self.layer.items[:] = []
        self.d.insert_glyph()
        self.assertEqual(len(self.w.canvas.doc.layers[0].items), 1)
        self.w.undo()
        self.assertEqual(self.w.canvas.doc.layers[0].items, [])

    def test_insert_a_blank_says_so(self):
        self.w.canvas.select([])
        self.d.char_edit.setText(' ')
        self.d.add_selection()
        with mock.patch('vectordrive.ui.font_editor.QMessageBox.information') as said:
            self.assertIsNone(self.d.insert_glyph())
        said.assert_called_once()
        self.assertEqual(self.layer.items, [])

    def test_delete(self):
        self.add('H', square())
        self.add('I', stroke())
        self.d.list.setCurrentRow(0)
        self.d.delete_glyph()
        self.assertEqual(set(self.d.draft.glyphs), {ord('I')})
        self.assertEqual(self.d.current_code(), ord('I'))
        self.d.delete_glyph()
        self.assertEqual(self.d.draft.glyphs, {})
        self.assertIsNone(self.d.current_code())

    def test_kerning(self):
        self.add('A', square())
        self.add('V', square())
        self.d.pair_edit.setText('AV')
        self.d.kern_box.setValue(-7.0)
        self.assertTrue(self.d.apply_kern())
        self.assertAlmostEqual(self.d.draft.kern_mm(ord('A'), ord('V'), 100.0), -7.0)
        self.assertEqual(self.d.kern_list.count(), 1)
        self.d.pair_edit.clear()
        self.d.kern_box.setValue(0.0)
        self.d.kern_list.setCurrentRow(0)
        self.assertEqual(self.d.pair_edit.text(), 'AV')
        self.assertAlmostEqual(self.d.kern_box.value(), -7.0)
        self.d.kern_box.setValue(0.0)
        self.d.apply_kern()
        self.assertEqual(self.d.kern_list.count(), 0)

    def test_kerning_needs_two(self):
        self.d.pair_edit.setText('A')
        with mock.patch('vectordrive.ui.font_editor.QMessageBox.information') as said:
            self.assertFalse(self.d.apply_kern())
        said.assert_called_once()

    def test_preview_follows(self):
        self.add('H', square())
        self.d.sample.setText('HH')
        self.assertEqual(len(self.d.preview.path.contours), 2)
        self.d.sample.setText('')
        self.assertEqual(self.d.preview.path.contours, [])

    def test_painting_does_not_fail(self):
        self.add('H', square())
        self.add('I', stroke())
        self.d.sample.setText('HI')
        self.assertFalse(self.d.preview.grab().isNull())
        self.assertFalse(self.d.grab().isNull())


class TestSave(WindowCase):
    def test_needs_a_name(self):
        self.add('H', square())
        with mock.patch('vectordrive.ui.font_editor.QMessageBox.information') as said:
            self.assertFalse(self.d.save_font())
        said.assert_called_once()
        self.assertTrue(self.d.dirty)

    def test_needs_a_character(self):
        self.d.name_edit.setText('Essai Vide')
        with mock.patch('vectordrive.ui.font_editor.QMessageBox.information') as said:
            self.assertFalse(self.d.save_font())
        said.assert_called_once()

    def test_saved_and_usable(self):
        self.add('H', square())
        self.d.name_edit.setText('Essai Atelier')
        self.assertTrue(self.d.save_font())
        self.assertFalse(self.d.dirty)
        self.assertEqual(self.d.path.parent, self.folder())
        self.assertIn('Essai Atelier', fonts.svg_families())
        self.assertAlmostEqual(TX.layout('H', 'Essai Atelier', 10.0, kerning=False).bbox()[3], 10.0, places=6)

    def test_name_edit_marks_it_changed(self):
        self.d.name_edit.setText('X')
        self.assertFalse(self.d.dirty)
        self.d.name_edit.textEdited.emit('Y')
        self.assertTrue(self.d.dirty)

    def test_second_save_same_file(self):
        self.add('H', square())
        self.d.name_edit.setText('Essai Atelier')
        self.d.save_font()
        first = self.d.path
        self.add('I', stroke())
        self.assertTrue(self.d.save_font())
        self.assertEqual(self.d.path, first)
        self.assertEqual([f.name for f in self.folder().glob('*.svg')], [first.name])
        self.assertIn('I', fonts.characters('Essai Atelier'))

    def test_rename_same_file(self):
        self.add('H', square())
        self.d.name_edit.setText('Essai Un')
        self.d.save_font()
        first = self.d.path
        self.d.name_edit.setText('Essai Deux')
        self.assertTrue(self.d.save_font())
        self.assertEqual(self.d.path, first)
        self.assertEqual(svgfonts.font_name(first), 'Essai Deux')
        self.assertIn('Essai Deux', fonts.svg_families())
        self.assertNotIn('Essai Un', fonts.svg_families())

    def test_taken_name_refused(self):
        self.add('H', square())
        self.d.name_edit.setText('VD Trait')
        with mock.patch('vectordrive.ui.font_editor.QMessageBox.information') as said:
            self.assertFalse(self.d.save_font())
        said.assert_called_once()
        self.assertEqual(list(self.folder().glob('*.svg')) if self.folder().is_dir() else [], [])

    def test_file_outside_is_never_written(self):
        with tempfile.TemporaryDirectory() as out:
            src = pathlib.Path(out) / 'dehors.svg'
            draft('Essai Dehors').save(src)
            before = src.read_bytes()
            self.assertTrue(self.d.open_font(str(src)))
            self.add('Z', square())
            self.assertTrue(self.d.save_font())
            self.assertEqual(src.read_bytes(), before)
            self.assertEqual(self.d.path.parent, self.folder())
            self.assertEqual(self.d.name_edit.text(), 'Essai Dehors')

    def test_write_failure_says_so(self):
        self.add('H', square())
        self.d.name_edit.setText('Essai Disque')
        with mock.patch.object(FE.Draft, 'save', side_effect=OSError('plein')), \
                mock.patch('vectordrive.ui.font_editor.QMessageBox.critical') as said:
            self.assertFalse(self.d.save_font())
        said.assert_called_once()
        self.assertTrue(self.d.dirty)

    def test_texts_of_the_drawing_follow(self):
        self.add('H', square())
        self.d.name_edit.setText('Essai Suivi')
        self.d.save_font()
        t = Text(text='H', font='Essai Suivi', size=10.0)
        t.outline = TX.outline_for(t)
        other = Text(text='H', font='VD Trait', size=10.0)
        other.outline = TX.outline_for(other)
        keep = other.outline
        self.layer.items[:] = [t, other]
        self.d.draft.put(ord('H'), square(w=140.0), 150.0, 100.0)
        self.d.dirty = True
        self.assertTrue(self.d.save_font())
        self.assertAlmostEqual(t.outline.bbox()[2], 14.0, places=6)
        self.assertIs(other.outline, keep)

    def test_letter_font_counts_too(self):
        self.add('H', square())
        self.d.name_edit.setText('Essai Lettre')
        self.d.save_font()
        t = Text(text='HH', font='VD Trait', size=10.0)
        TX.set_char_fx(t, {0: {'font': 'Essai Lettre'}})
        t.outline = TX.outline_for(t)
        self.layer.items[:] = [t]
        self.assertEqual(self.w.font_redrawn('Essai Lettre'), 1)


class TestLeaving(WindowCase):
    def test_new_unchanged_goes_straight(self):
        with mock.patch('vectordrive.ui.font_editor.QMessageBox.question', side_effect=AssertionError):
            self.d.new_font()

    def buttons(self):
        from PySide6.QtWidgets import QMessageBox
        return QMessageBox.StandardButton

    def test_new_asks_when_changed(self):
        self.add('H', square())
        with mock.patch('vectordrive.ui.font_editor.QMessageBox.question', return_value=self.buttons().Cancel):
            self.d.new_font()
        self.assertEqual(set(self.d.draft.glyphs), {ord('H')})
        with mock.patch('vectordrive.ui.font_editor.QMessageBox.question', return_value=self.buttons().Discard):
            self.d.new_font()
        self.assertEqual(self.d.draft.glyphs, {})
        self.assertFalse(self.d.dirty)
        self.assertIsNone(self.d.path)

    def test_save_answer_saves(self):
        self.add('H', square())
        self.d.name_edit.setText('Essai Sortie')
        with mock.patch('vectordrive.ui.font_editor.QMessageBox.question', return_value=self.buttons().Save):
            self.assertTrue(self.d.ask_discard())
        self.assertIn('Essai Sortie', fonts.svg_families())

    def test_save_answer_that_fails_stays(self):
        self.add('H', square())
        with mock.patch('vectordrive.ui.font_editor.QMessageBox.question', return_value=self.buttons().Save), \
                mock.patch('vectordrive.ui.font_editor.QMessageBox.information'):
            self.assertFalse(self.d.ask_discard())

    def test_close_can_be_cancelled(self):
        self.add('H', square())
        with mock.patch('vectordrive.ui.font_editor.QMessageBox.question', return_value=self.buttons().Cancel):
            self.assertFalse(self.d.close())
        self.assertTrue(self.d.isVisible())

    def test_escape_can_be_cancelled(self):
        self.add('H', square())
        with mock.patch('vectordrive.ui.font_editor.QMessageBox.question', return_value=self.buttons().Cancel):
            self.d.reject()
        self.assertTrue(self.d.isVisible())

    def test_closing_the_main_window_asks(self):
        from PySide6.QtGui import QCloseEvent
        self.add('H', square())
        ev = QCloseEvent()
        with mock.patch('vectordrive.ui.font_editor.QMessageBox.question', return_value=self.buttons().Cancel):
            self.w.closeEvent(ev)
        self.assertFalse(ev.isAccepted())

    def test_open_refuses_what_is_no_font(self):
        with tempfile.TemporaryDirectory() as out:
            p = pathlib.Path(out) / 'dessin.svg'
            p.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding='utf-8')
            with mock.patch('vectordrive.ui.font_editor.QMessageBox.information') as said:
                self.assertFalse(self.d.open_font(str(p)))
            said.assert_called_once()

    def test_clone(self):
        self.assertTrue(self.d.clone_font('VD Trait'))
        self.assertTrue(self.d.dirty)
        self.assertIsNone(self.d.path)
        self.assertIn(ord('H'), self.d.draft.glyphs)
        self.assertNotEqual(self.d.name_edit.text(), 'VD Trait')
        self.assertTrue(self.d.save_font())
        self.assertTrue(fonts.is_available(self.d.name_edit.text()))

    def test_clone_refused(self):
        with mock.patch('vectordrive.ui.font_editor.QMessageBox.information') as said:
            self.assertFalse(self.d.clone_font('Absente De Partout'))
        said.assert_called_once()


if __name__ == '__main__':
    unittest.main()
