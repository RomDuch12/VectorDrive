"""Round 193 : dates des textes remises au jour du calcul des parcours (TauDrive)."""
import datetime
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import variables as V
from vectordrive.core.document import Document, Text

MONDAY = datetime.datetime(2026, 10, 12, 9, 0)
WEDNESDAY = datetime.datetime(2026, 10, 14, 15, 30)


def doc_with_texts():
    d = Document()
    dated = Text(text='Lot |Lot| du |Date dd/MM/yy|', font='Arial', size=4.0)
    plain = Text(text='Réf. |Lot|', font='Arial', size=4.0)
    fixed = Text(text='Atelier', font='Arial', size=4.0)
    for t in (dated, plain, fixed):
        d.add(t)
    table = V.VarTable()
    table.add_variable('Lot', ['A12', 'B07'])
    V.store(d, table)
    V.apply_row(d, 0, now=MONDAY)
    return d, dated, plain, fixed


class TestRefresh(unittest.TestCase):
    def test_only_dated_texts(self):
        d, dated, plain, fixed = doc_with_texts()
        self.assertEqual(dated.text, 'Lot A12 du 12/10/26')
        self.assertTrue(V.has_clock(dated.extra['template']))
        self.assertFalse(V.has_clock(plain.extra['template']))
        self.assertEqual(V.refresh_dates(d, MONDAY), [])                          # même jour : rien
        self.assertEqual(V.refresh_dates(d, WEDNESDAY, dry=True), [dated])
        self.assertEqual(dated.text, 'Lot A12 du 12/10/26')                       # sans rien toucher
        self.assertEqual(V.refresh_dates(d, WEDNESDAY), [dated])
        self.assertEqual(dated.text, 'Lot A12 du 14/10/26')
        self.assertEqual((plain.text, fixed.text), ('Réf. A12', 'Atelier'))
        self.assertTrue(V.has_clock('|Heure HH:mm|'))

    def test_produced_states_keep_their_date(self):
        d, dated, _plain, _fixed = doc_with_texts()
        groups, _lay = V.produce([dated], V.table_of(d), now=MONDAY)
        d.add(groups[0])
        V.refresh_dates(d, WEDNESDAY)
        copy = groups[0].children[0]
        self.assertEqual(copy.text, 'Lot A12 du 12/10/26')                        # figé à la production
        self.assertNotIn('template', copy.extra)


class TestPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_panel_setting_and_undo(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            d, dated, _p, _f = doc_with_texts()
            for it in list(d.iter_leaves()):
                w.canvas.doc.add(it)
            V.store(w.canvas.doc, V.table_of(d))
            panel = w.cam_panel
            w.settings.setValue('fao/dates', False)
            self.assertEqual(panel.refresh_dates(WEDNESDAY), 0)
            self.assertEqual(dated.text, 'Lot A12 du 12/10/26')
            w.settings.setValue('fao/dates', True)
            self.assertEqual(panel.refresh_dates(WEDNESDAY), 1)
            self.assertEqual(dated.text, 'Lot A12 du 14/10/26')
            w.undo()
            texts = [t.text for t in w.canvas.doc.iter_leaves() if isinstance(t, Text)]
            self.assertIn('Lot A12 du 12/10/26', texts)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
