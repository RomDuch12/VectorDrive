"""Round 818 : import de variables : Unicode, ligne de départ, séparateurs, largeur constante, aperçu."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication

from vectordrive.core import variables as V

app = QApplication.instance() or QApplication([])
ACCENTS = 'Numéro;Prénom\n1;Éloïse\n2;Jérôme\n'


class Decode(unittest.TestCase):
    def test_utf16_with_mark_as_notepad_writes_it(self):
        self.assertEqual(V.decode_text(ACCENTS.encode('utf-16')), ACCENTS)
        self.assertEqual(V.decode_text(b'\xff\xfe' + ACCENTS.encode('utf-16-le')), ACCENTS)
        self.assertEqual(V.decode_text(b'\xfe\xff' + ACCENTS.encode('utf-16-be')), ACCENTS)

    def test_utf32_with_mark(self):
        self.assertEqual(V.decode_text(b'\xff\xfe\x00\x00' + ACCENTS.encode('utf-32-le')), ACCENTS)

    def test_utf16_without_mark(self):
        self.assertEqual(V.decode_text(ACCENTS.encode('utf-16-le')), ACCENTS)
        self.assertEqual(V.decode_text(ACCENTS.encode('utf-16-be')), ACCENTS)

    def test_utf8_with_and_without_mark(self):
        self.assertEqual(V.decode_text(ACCENTS.encode('utf-8')), ACCENTS)
        self.assertEqual(V.decode_text(ACCENTS.encode('utf-8-sig')), ACCENTS)

    def test_ansi(self):
        self.assertEqual(V.decode_text(ACCENTS.encode('cp1252')), ACCENTS)

    def test_bytes_cp1252_cannot_read_do_not_fail(self):
        self.assertIn('a', V.decode_text(b'a\x81\x8d\x90b'))

    def test_chinese_stays_chinese(self):
        s = '编号;名称\n1;北京\n'
        self.assertEqual(V.decode_text(s.encode('utf-16')), s)
        self.assertEqual(V.decode_text(s.encode('utf-8')), s)

    def test_empty(self):
        self.assertEqual(V.decode_text(b''), '')


class Parse(unittest.TestCase):
    def test_as_before(self):
        t = V.parse_data('Nom;Prénom\nDupont;Jean\nMartin;Lise\n')
        self.assertEqual(t.names, ['Nom', 'Prénom'])
        self.assertEqual(t.rows, [['Dupont', 'Jean'], ['Martin', 'Lise']])

    def test_start_counts_blank_lines_too(self):
        text = 'titre du fichier\n\nNom;Age\nA;1\nB;2\n'
        t = V.parse_data(text, start=2)
        self.assertEqual(t.names, ['Nom', 'Age'])
        self.assertEqual(t.rows, [['A', '1'], ['B', '2']])

    def test_start_beyond_the_end(self):
        self.assertEqual(V.parse_data('a;b\n', start=9).names, [])

    def test_negative_start_is_the_beginning(self):
        self.assertEqual(V.parse_data('a;b\nc;d\n', start=-3).names, ['a', 'b'])

    def test_named_separator(self):
        t = V.parse_data('a b\nc d\n', sep=' ', header=False)
        self.assertEqual(t.rows, [['a', 'b'], ['c', 'd']])

    def test_long_separator(self):
        t = V.parse_data('a::b\nc::d\n', sep='::', header=False)
        self.assertEqual(t.rows, [['a', 'b'], ['c', 'd']])

    def test_quotes_protect_the_separator(self):
        t = V.parse_data('"Dupont; Jean";"12, rue ""Haute"""\n', sep=';', header=False)
        self.assertEqual(t.rows, [['Dupont; Jean', '12, rue "Haute"']])

    def test_lone_quote_stays(self):
        t = V.parse_data('5";8"\n', sep=';', header=False)
        self.assertEqual(t.rows, [['5"', '8"']])

    def test_line_separator(self):
        t = V.parse_data('a,b|c,d|', sep=',', header=False, line_sep='|')
        self.assertEqual(t.rows, [['a', 'b'], ['c', 'd']])

    def test_fixed_widths(self):
        t = V.parse_data('AB  123 X\nCD  456 Y\n', widths=[4, 4, 1], header=False)
        self.assertEqual(t.rows, [['AB', '123', 'X'], ['CD', '456', 'Y']])

    def test_one_width_for_all(self):
        t = V.parse_data('AABBCC\nDDEE\n', widths=[2], header=False)
        self.assertEqual(t.rows, [['AA', 'BB', 'CC'], ['DD', 'EE', '']])

    def test_rest_of_a_fixed_line_is_a_column(self):
        t = V.parse_data('AABBzz\n', widths=[2, 2], header=False)
        self.assertEqual(t.rows, [['AA', 'BB', 'zz']])

    def test_fixed_with_short_line(self):
        t = V.parse_data('AABB\nA\n', widths=[2, 2], header=False)
        self.assertEqual(t.rows, [['AA', 'BB'], ['A', '']])

    def test_fixed_header(self):
        t = V.parse_data('NomAge\nabc 12\n', widths=[3, 3])
        self.assertEqual(t.names, ['Nom', 'Age'])
        self.assertEqual(t.rows, [['abc', '12']])

    def test_group_only_following_lines(self):
        t = V.parse_data('a\na\nb\na\n', sep=';', header=False, group=True)
        self.assertEqual(t.rows, [['a'], ['b'], ['a']])
        self.assertEqual(len(V.parse_data('a\na\n', sep=';', header=False).rows), 2)

    def test_widths_text(self):
        self.assertEqual(V.parse_widths('5, 10;3'), [5, 10, 3])
        self.assertEqual(V.parse_widths('x,0,-2,4'), [4])
        self.assertEqual(V.parse_widths(''), [])
        self.assertEqual(V.parse_widths(None), [])

    def test_split_lines_keeps_blanks(self):
        self.assertEqual(V.split_lines('a\n\nb'), ['a', '', 'b'])
        self.assertEqual(V.split_lines('a|\nb', '|'), ['a', 'b'])


class Dialog(unittest.TestCase):
    def dlg(self, text=ACCENTS):
        from vectordrive.ui.variables_import import VariablesImportDialog
        return VariablesImportDialog(None, text)

    def test_first_view(self):
        d = self.dlg()
        self.assertTrue(d.raw.toPlainText().startswith('[0] Numéro;Prénom'))
        self.assertIn('[2] 2;Jérôme', d.raw.toPlainText())
        self.assertEqual(d.preview.columnCount(), 2)
        self.assertEqual(d.preview.rowCount(), 2)
        self.assertEqual(d.preview.item(1, 1).text(), 'Jérôme')
        self.assertEqual(d.preview.horizontalHeaderItem(0).text(), 'Numéro')
        self.assertIn('2', d.summary.text())
        d.deleteLater()

    def test_start_moves_the_preview(self):
        d = self.dlg('rebut\nA;B\n1;2\n')
        d.start.setValue(1)
        self.assertEqual(d.table().names, ['A', 'B'])
        self.assertEqual(d.preview.rowCount(), 1)
        d.deleteLater()

    def test_no_header(self):
        d = self.dlg()
        d.header.setChecked(False)
        self.assertEqual(d.table().names, ['VAR1', 'VAR2'])
        self.assertEqual(len(d.table().rows), 3)
        d.deleteLater()

    def test_other_separator(self):
        d = self.dlg('a#b\nc#d\n')
        d.col_sep.setCurrentIndex(d.col_sep.findData('autre'))
        self.assertTrue(d.col_other.isEnabled())
        d.col_other.setText('#')
        self.assertEqual(d.table().names, ['a', 'b'])
        d.deleteLater()

    def test_other_line_separator(self):
        d = self.dlg('a;b$c;d')
        d.line_sep.setCurrentIndex(d.line_sep.findData('autre'))
        d.line_other.setText('$')
        self.assertEqual(d.table().rows, [['c', 'd']])
        d.deleteLater()

    def test_fixed_mode(self):
        d = self.dlg('NomAge\nabc 12\n')
        d.mode.setCurrentIndex(d.mode.findData('fixed'))
        self.assertFalse(d.col_sep.isEnabled())
        self.assertTrue(d.widths.isEnabled())
        d.widths.setText('3,3')
        self.assertEqual(d.table().names, ['Nom', 'Age'])
        d.deleteLater()

    def test_group(self):
        d = self.dlg('N\na\na\n')
        d.group.setChecked(True)
        self.assertEqual(d.table().rows, [['a']])
        d.deleteLater()

    def test_nothing_to_import_blocks_ok(self):
        d = self.dlg('')
        self.assertFalse(d.ok.isEnabled())
        d.deleteLater()

    def test_preview_is_capped(self):
        from vectordrive.ui import variables_import as VI
        d = self.dlg('N\n' + 'x\n' * (VI.SHOWN_ROWS + 50))
        self.assertEqual(d.preview.rowCount(), VI.SHOWN_ROWS)
        self.assertEqual(len(d.table().rows), VI.SHOWN_ROWS + 50)
        d.deleteLater()


class FromVariablesDialog(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.variables_dialog import VariablesDialog
        self.folder = tempfile.mkdtemp()
        self.dlg = VariablesDialog(None, V.VarTable())

    def tearDown(self):
        self.dlg.deleteLater()

    def write(self, name, data):
        p = os.path.join(self.folder, name)
        with open(p, 'wb') as f:
            f.write(data)
        return p

    def test_unicode_file_is_read(self):
        p = self.write('u.txt', ACCENTS.encode('utf-16'))
        self.assertTrue(self.dlg.import_file(p, header=True))
        self.assertEqual(self.dlg.table().names, ['Numéro', 'Prénom'])
        self.assertEqual(self.dlg.table().rows[0], ['1', 'Éloïse'])

    def test_a_bad_byte_no_longer_breaks_the_import(self):
        p = self.write('b.txt', b'a;b\nc\x81;d\n')
        self.assertTrue(self.dlg.import_file(p, header=True))
        self.assertEqual(len(self.dlg.table().rows), 1)

    def test_missing_file_says_so(self):
        with mock.patch('vectordrive.ui.variables_dialog.QMessageBox.warning') as warn:
            self.assertFalse(self.dlg.import_file(os.path.join(self.folder, 'none.txt'), header=True))
        warn.assert_called_once()

    def test_without_header_answer_the_settings_open(self):
        p = self.write('o.txt', ACCENTS.encode('utf-8'))
        with mock.patch('vectordrive.ui.variables_import.VariablesImportDialog.exec', return_value=1):
            self.assertTrue(self.dlg.import_file(p))
        self.assertEqual(self.dlg.table().names, ['Numéro', 'Prénom'])

    def test_cancelling_the_settings_changes_nothing(self):
        p = self.write('c.txt', ACCENTS.encode('utf-8'))
        before = self.dlg.table().names
        with mock.patch('vectordrive.ui.variables_import.VariablesImportDialog.exec', return_value=0):
            self.assertFalse(self.dlg.import_file(p))
        self.assertEqual(self.dlg.table().names, before)


if __name__ == '__main__':
    unittest.main()
