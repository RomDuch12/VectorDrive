"""Round 162 : textes variables de TypeEdit (Variables, Insérer un texte
variable, Séries, Date et Heure)."""
import datetime
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import variables as V
from vectordrive.core.document import Document, Text

NOW = datetime.datetime(2026, 10, 18, 17, 5, 9)


class TestCore(unittest.TestCase):
    def test_render_and_dates(self):
        vals = {'Nom': 'Dupont', 'N': '7'}
        self.assertEqual(V.render('M. |Nom| n° |N|', vals, NOW), 'M. Dupont n° 7')
        self.assertEqual(V.render('|Inconnue|', vals, NOW), '|Inconnue|')
        self.assertEqual(V.render('|Date|', {}, NOW), '18/10/2026')
        self.assertEqual(V.render('|Date dddd d MMMM yyyy|', {}, NOW), 'dimanche 18 octobre 2026')
        self.assertEqual(V.render('|Date yy-MM-dd|', {}, NOW), '26-10-18')
        self.assertEqual(V.render('|Heure HH:mm:ss|', {}, NOW), '17:05:09')
        self.assertEqual(V.render('|Heure h tt|', {}, NOW), '5 PM')
        self.assertEqual(V.tokens('|A| et |B| et |A|'), ['A', 'B'])

    def test_series(self):
        self.assertEqual(V.series(18, 2, end=26), ['18', '20', '22', '24', '26'])        # chambres paires
        self.assertEqual(V.series(1, 1, 3, width='###'), ['001', '002', '003'])
        self.assertEqual(V.series(7, 1, 2, width='N°###', before='[', after=']'), ['[N°007]', '[N°008]'])
        self.assertEqual(V.series(25, 1, 3, kind='alphabétique'), ['Y', 'Z', 'AA'])
        self.assertEqual(V.series(9, 1, 3, kind='alphanumérique'), ['A9', 'A10', 'B1'])

    def test_table_and_import(self):
        t = V.parse_data('Nom;Prénom\nDupont;Jean\nMartin;Lise\n')
        self.assertEqual((t.names, t.rows), (['Nom', 'Prénom'], [['Dupont', 'Jean'], ['Martin', 'Lise']]))
        t = V.parse_data('a\tb\nc', header=False)
        self.assertEqual((t.names, t.rows), (['VAR1', 'VAR2'], [['a', 'b'], ['c', '']]))
        t.add_variable('X', ['1'])
        self.assertEqual(t.rows, [['a', 'b', '1'], ['c', '', '']])
        t.rename('X', 'Y')
        t.remove_variable('VAR2')
        self.assertEqual((t.names, t.row(1)), (['VAR1', 'Y'], {'VAR1': 'c', 'Y': ''}))
        with self.assertRaises(ValueError):
            t.add_variable('Y')
        self.assertEqual(V.VarTable.from_dict(t.to_dict()), t)

    def test_apply_row(self):
        d = Document()
        tx = d.add(Text(text='Chambre |N|', font='Police absente'))
        plain = d.add(Text(text='fixe'))
        V.store(d, V.VarTable(['N'], [['18'], ['20']]))
        V.apply_row(d, 1)
        self.assertEqual((tx.text, tx.extra['template']), ('Chambre 20', 'Chambre |N|'))
        self.assertEqual(V.table_of(d).current, 1)
        V.apply_row(d, 0)
        self.assertEqual(tx.text, 'Chambre 18')
        self.assertEqual(plain.text, 'fixe')
        self.assertNotIn('template', plain.extra)
        V.show_templates(d)
        self.assertEqual(tx.text, 'Chambre |N|')


class TestUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_dialog(self):
        from vectordrive.ui.variables_dialog import SeriesDialog, VariablesDialog
        dlg = VariablesDialog(None, V.VarTable(['Nom'], [['A'], ['B']], 1))
        self.assertEqual(dlg.state.currentIndex(), 1)
        self.assertTrue(dlg.add_variable('Num'))
        dlg.fill_column('Num', V.series(1, 1, 3))
        t = dlg.table()
        self.assertEqual(t.names, ['Nom', 'Num'])
        self.assertEqual(t.rows, [['A', '1'], ['B', '2'], ['', '3']])
        dlg.grid.setCurrentCell(0, 0)
        self.assertTrue(dlg.rename_variable('Prénom'))
        self.assertEqual(dlg.table().names, ['Prénom', 'Num'])
        s = SeriesDialog(None, ['Num'])
        s.start.setValue(18)
        s.step.setValue(2)
        s.use_end.setChecked(True)
        s.end.setValue(22)
        self.assertEqual(s.values(), ['18', '20', '22'])
        self.assertIn('(3)', s.preview.text())

    def test_import_file(self):
        from vectordrive.ui.variables_dialog import VariablesDialog
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'noms.txt')
            with open(f, 'w', encoding='cp1252') as fh:
                fh.write('Nom;Ville\nLéa;Brest\n')
            dlg = VariablesDialog(None, V.VarTable())
            self.assertTrue(dlg.import_file(f, header=True))
            self.assertEqual(dlg.table().rows, [['Léa', 'Brest']])

    def test_window_commands(self):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual((TE_ACTIONS['ID_BAR_VARIABLE'], TE_ACTIONS['ID_BAR_VARALPHA']),
                         ('variables', 'insert_variable'))
        w = MainWindow()
        try:
            doc = w.canvas.doc
            new = w.insert_variable('Nom')
            self.assertEqual(new[0].extra['template'], '|Nom|')
            self.assertEqual(V.table_of(doc).names, ['Nom'])
            w.insert_variable('Date dd/MM')                                 # même texte : ajouté au modèle
            self.assertEqual(new[0].extra['template'], '|Nom| |Date dd/MM|')
            self.assertEqual(V.table_of(doc).names, ['Nom'])                # la date n'est pas une variable
            changed = w.apply_variables(V.VarTable(['Nom'], [['Ana'], ['Bob']], 1))
            self.assertEqual(changed, new)
            self.assertTrue(new[0].text.startswith('Bob '))
            w.undo()
            self.assertEqual(V.table_of(w.canvas.doc).rows, [])
            self.assertEqual(V.table_of(w.canvas.doc).names, ['Nom'])
            w.redo()
            self.assertEqual(V.table_of(w.canvas.doc).rows, [['Ana'], ['Bob']])
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
