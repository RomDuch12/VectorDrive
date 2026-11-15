"""Round 819 : rechercher / remplacer : taille, police, compression identique, portée."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication

from vectordrive.core import text as TX
from vectordrive.core import textops as TO
from vectordrive.core.document import Group, Layer, Plate, Shape, Text
from vectordrive.core.geom import Path, rect

app = QApplication.instance() or QApplication([])


def make(s='Lot A', font='Arial', size=10.0, **kw):
    t = Text(text=s, font=font, size=size, **kw)
    t.outline = TX.outline_for(t)
    return t


class Lists(unittest.TestCase):
    def test_sizes_keep_the_order_found(self):
        self.assertEqual(TO.sizes_of([make(size=5.0), make(size=3.0), make(size=5.0), make(size=5.00001)]), [5.0, 3.0])

    def test_fonts_keep_the_order_found(self):
        self.assertEqual(TO.fonts_of([make(font='Tahoma'), make(font='Arial'), make(font='Tahoma')]), ['Tahoma', 'Arial'])


class Base(unittest.TestCase):
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
        self.one = Layer(name='Plan 1')
        self.two = Layer(name='Plan 2')
        self.doc.layers[:] = [self.one, self.two]
        self.doc.active = self.one.id
        self.doc.plate = Plate(width=100.0, height=100.0)
        self.win._undo.clear()
        self.a = make('Lot A', size=5.0)
        self.b = make('Lot B', size=7.0, font='Tahoma')
        self.c = make('Lot C', size=5.0)
        self.one.items.extend([self.a, self.b])
        self.two.items.append(self.c)
        self.win.canvas.select([])


class Scope(Base):
    def test_layer_and_all(self):
        self.assertEqual(self.win.texts_in('layer'), [self.a, self.b])
        self.assertEqual(self.win.texts_in('all'), [self.a, self.b, self.c])

    def test_selection(self):
        self.win.canvas.select([self.b])
        self.assertEqual(self.win.texts_in('selection'), [self.b])

    def test_inside_groups(self):
        g = Group(children=[make('dans'), Shape(path=Path([rect(0, 0, 5, 5)]))])
        self.two.items.append(g)
        self.assertEqual(len(self.win.texts_in('all')), 4)


class Replace(Base):
    def test_text_with_a_scope(self):
        got = self.win.replace_in_texts({'scope': 'layer', 'text': True, 'find': 'Lot', 'repl': 'Série'})
        self.assertEqual(got['text'], 2)
        self.assertEqual(self.a.text, 'Série A')
        self.assertEqual(self.c.text, 'Lot C')

    def test_case_and_whole_words(self):
        got = self.win.replace_in_texts({'scope': 'all', 'text': True, 'find': 'lot', 'repl': 'X', 'case': True})
        self.assertEqual(got['text'], 0)
        got = self.win.replace_in_texts({'scope': 'all', 'text': True, 'find': 'Lo', 'repl': 'X', 'whole': True})
        self.assertEqual(got['text'], 0)

    def test_size_from_old_to_new(self):
        before = self.a.outline.bbox()
        got = self.win.replace_in_texts({'scope': 'all', 'size': True, 'old_size': 5.0, 'new_size': 10.0})
        self.assertEqual(got['size'], 2)
        self.assertEqual((self.a.size, self.b.size, self.c.size), (10.0, 7.0, 10.0))
        self.assertGreater(self.a.outline.bbox()[3] - self.a.outline.bbox()[1], (before[3] - before[1]) * 1.5)

    def test_all_sizes(self):
        got = self.win.replace_in_texts({'scope': 'layer', 'size': True, 'all_sizes': True, 'new_size': 3.0})
        self.assertEqual(got['size'], 2)
        self.assertEqual((self.a.size, self.b.size, self.c.size), (3.0, 3.0, 5.0))

    def test_same_size_changes_nothing(self):
        got = self.win.replace_in_texts({'scope': 'all', 'size': True, 'old_size': 5.0, 'new_size': 5.0})
        self.assertEqual(got['size'], 0)
        self.assertEqual(len(self.win._undo), 0)

    def test_bad_size_is_ignored(self):
        got = self.win.replace_in_texts({'scope': 'all', 'size': True, 'all_sizes': True, 'new_size': 0.0})
        self.assertEqual(got['size'], 0)

    def test_font_from_old_to_new(self):
        got = self.win.replace_in_texts({'scope': 'all', 'font': True, 'old_font': 'Tahoma', 'new_font': 'Arial'})
        self.assertEqual(got['font'], 1)
        self.assertEqual(self.b.font, 'Arial')

    def test_font_leaves_the_others(self):
        self.win.replace_in_texts({'scope': 'all', 'font': True, 'old_font': 'Arial', 'new_font': 'Tahoma'})
        self.assertEqual((self.a.font, self.b.font, self.c.font), ('Tahoma', 'Tahoma', 'Tahoma'))

    def test_all_fonts_within_the_scope(self):
        got = self.win.replace_in_texts({'scope': 'layer', 'font': True, 'all_fonts': True, 'new_font': 'Verdana'})
        self.assertEqual(got['font'], 2)
        self.assertEqual((self.a.font, self.b.font, self.c.font), ('Verdana', 'Verdana', 'Arial'))

    def test_letter_fonts_follow(self):
        TX.set_char_fx(self.a, {1: {'font': 'Tahoma', 'dy': 5.0}, 2: {'font': 'Verdana'}})
        self.win.replace_in_texts({'scope': 'layer', 'font': True, 'old_font': 'Tahoma', 'new_font': 'Courier New'})
        fx = TX.char_fx(self.a)
        self.assertEqual(fx[1]['font'], 'Courier New')
        self.assertEqual(fx[1]['dy'], 5.0)
        self.assertEqual(fx[2]['font'], 'Verdana')
        self.assertEqual(self.a.font, 'Arial')

    def test_all_fonts_removes_letter_fonts(self):
        TX.set_char_fx(self.a, {1: {'font': 'Tahoma', 'dy': 5.0}})
        self.win.replace_in_texts({'scope': 'layer', 'font': True, 'all_fonts': True, 'new_font': 'Verdana'})
        self.assertEqual(self.a.font, 'Verdana')
        self.assertNotIn('font', TX.char_fx(self.a)[1])

    def test_compression_is_the_same_everywhere(self):
        self.b.width_ratio = 0.5
        got = self.win.replace_in_texts({'scope': 'all', 'comp': True, 'ratio': 80.0})
        self.assertEqual(got['comp'], 3)
        self.assertEqual({t.width_ratio for t in (self.a, self.b, self.c)}, {0.8})

    def test_compression_drops_an_imposed_width(self):
        self.a.extra['fit'] = {'width': 5.0, 'mode': 'compress'}
        self.win.replace_in_texts({'scope': 'layer', 'comp': True, 'ratio': 100.0})
        self.assertNotIn('fit', self.a.extra)
        self.assertEqual(self.a.width_ratio, 1.0)

    def test_several_at_once_undo_in_one(self):
        self.win.replace_in_texts({'scope': 'all', 'text': True, 'find': 'Lot', 'repl': 'X', 'size': True, 'all_sizes': True,
                                   'new_size': 4.0, 'comp': True, 'ratio': 90.0})
        self.assertEqual(self.a.text, 'X A')
        self.assertEqual(self.a.size, 4.0)
        self.assertEqual(self.a.width_ratio, 0.9)
        self.assertEqual(len(self.win._undo), 1)
        self.win.undo()
        back = self.win.canvas.doc.layers[0].items[0]
        self.assertEqual((back.text, back.size, back.width_ratio), ('Lot A', 5.0, 1.0))

    def test_nothing_found_pushes_no_undo(self):
        got = self.win.replace_in_texts({'scope': 'all', 'text': True, 'find': 'zzz', 'repl': 'X'})
        self.assertFalse(any(got.values()))
        self.assertEqual(len(self.win._undo), 0)

    def test_old_call_still_works(self):
        self.assertEqual(self.win.find_replace('Lot', 'Série'), 3)
        self.assertEqual(self.c.text, 'Série C')

    def test_vnd_source_is_dropped(self):
        self.a.extra['vnd_obj'] = {'x': 1}
        self.a.spacing = 2.0
        self.win.replace_in_texts({'scope': 'layer', 'font': True, 'old_font': 'Arial', 'new_font': 'Tahoma'})
        self.assertNotIn('vnd_obj', self.a.extra)
        self.assertEqual(self.a.spacing, 0.0)


class Window(Base):
    def dlg(self):
        self.win.find_replace_dialog(exec_dialog=False)
        return self.win.last_find_dialog

    def test_no_selection_means_all_planes(self):
        d = self.dlg()
        self.assertFalse(d.scopes['selection'].isEnabled())
        self.assertEqual(d.scope(), 'all')
        self.assertEqual(d.old_size.count(), 2)
        self.assertEqual(d.old_font.count(), 2)
        self.assertEqual(d.old_font.itemText(0), 'Arial')
        d.deleteLater()

    def test_selection_is_offered_first(self):
        self.win.canvas.select([self.b])
        d = self.dlg()
        self.assertEqual(d.scope(), 'selection')
        self.assertEqual(d.old_size.currentData(), 7.0)
        self.assertEqual(d.old_font.currentText(), 'Tahoma')
        d.deleteLater()

    def test_changing_the_scope_refreshes_the_lists(self):
        self.win.canvas.select([self.b])
        d = self.dlg()
        d.scopes['all'].setChecked(True)
        self.assertEqual(d.old_size.count(), 2)
        d.scopes['layer'].setChecked(True)
        self.assertEqual(d.old_size.count(), 2)
        d.deleteLater()

    def test_all_options_grey_the_lists(self):
        d = self.dlg()
        d.all_sizes.setChecked(True)
        self.assertFalse(d.old_size.isEnabled())
        d.all_fonts.setChecked(True)
        self.assertFalse(d.old_font.isEnabled())
        d.deleteLater()

    def test_strongest_compression(self):
        self.b.width_ratio = 0.6
        d = self.dlg()
        d._strongest()
        self.assertAlmostEqual(d.ratio.value(), 60.0)
        d.deleteLater()

    def test_values_travel(self):
        d = self.dlg()
        d.find.setText('Lot')
        d.repl.setText('N')
        d.size_box.setChecked(True)
        d.new_size.setValue(9.0)
        d.font_box.setChecked(True)
        d.comp_box.setChecked(True)
        d.ratio.setValue(75.0)
        v = d.values()
        got = self.win.replace_in_texts(v)
        self.assertEqual(got['text'], 3)
        self.assertEqual(self.a.size, 9.0)
        self.assertEqual(self.a.width_ratio, 0.75)
        d.deleteLater()

    def test_no_text_says_so(self):
        self.one.items[:] = []
        self.two.items[:] = []
        with mock.patch('vectordrive.ui.main_window.QMessageBox.information') as info:
            self.assertIsNone(self.win.find_replace_dialog(exec_dialog=False))
        info.assert_called_once()

    def test_action_runs_the_dialog(self):
        with mock.patch('vectordrive.ui.find_replace_dialog.FindReplaceDialog.exec', return_value=0) as ex:
            self.win.A['find_replace'].trigger()
        ex.assert_called_once()

    def test_not_found_says_so(self):
        with mock.patch('vectordrive.ui.find_replace_dialog.FindReplaceDialog.exec', return_value=1), \
                mock.patch('vectordrive.ui.find_replace_dialog.FindReplaceDialog.values',
                           return_value={'scope': 'all', 'text': True, 'find': 'zzz', 'repl': '', 'size': False, 'font': False, 'comp': False}), \
                mock.patch('vectordrive.ui.main_window.QMessageBox.information') as info:
            self.win.find_replace_dialog()
        info.assert_called_once()
        self.win.settings.remove('texte/rechercher')


if __name__ == '__main__':
    unittest.main()
