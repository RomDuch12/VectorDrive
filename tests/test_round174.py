"""Round 174 : liste des caractères (TypeEdit, Rapido)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import fonts
from vectordrive.core.document import Text

FONT = next((f for f in ('Arial', 'DejaVu Sans', 'Segoe UI', 'Calibri') if fonts.is_available(f)), None)


@unittest.skipIf(FONT is None, 'aucune police de référence')
class TestCharMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_characters(self):
        chars = fonts.characters(FONT)
        self.assertIn('Ø', chars)
        self.assertIn('A', chars)
        self.assertNotIn('\n', chars)
        self.assertEqual(list(chars), sorted(chars, key=ord))
        self.assertEqual(fonts.characters('Police qui n existe pas'), ())

    def test_dialog_blocks(self):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual((TE_ACTIONS['ID_RAPIDO_LISTCAR_DLL'], TE_ACTIONS['ID_RAPIDO_MIRROR']),
                         ('char_map', 'mirror_h'))
        w = MainWindow()
        try:
            dlg = w.char_map_dialog()
            dlg.font_box.setCurrentFont(FONT)
            dlg.block.setCurrentIndex(dlg.block.findData('Latin-1 (accents, ©, °, ±…)'))
            chars = [dlg.grid.item(i).data(0x0100) for i in range(dlg.grid.count())]
            self.assertIn('°', chars)
            self.assertTrue(all(0xA0 <= ord(c) <= 0xFF for c in chars))
            dlg.close()
        finally:
            w.modified = False
            w.close()

    def test_insert_into_texts(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            t = w.canvas.doc.add(Text(text='Ø 12', font=FONT, size=5))
            v = w.canvas.doc.add(Text(text='N° |N|', font=FONT, size=5))
            v.extra['template'] = 'N° |N|'
            w.canvas.select([t, v])
            dlg = w.char_map_dialog()
            row = [i for i in range(dlg.grid.count()) if dlg.grid.item(i).data(0x0100) == '±']
            if row:
                dlg.grid.setCurrentRow(row[0])
                self.assertEqual(dlg.insert(), '±')
            else:
                w.insert_characters('±')
            self.assertEqual(t.text, 'Ø 12±')
            self.assertEqual(v.extra['template'], 'N° |N|±')
            w.undo()
            self.assertEqual(w.canvas.doc.layers[0].items[-2].text, 'Ø 12')
        finally:
            w.modified = False
            w.close()

    def test_clipboard_without_text(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.canvas.select([])
            self.assertEqual(w.insert_characters('©'), [])
            self.assertEqual(QApplication.clipboard().text(), '©')
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
