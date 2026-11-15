"""Round 558 : Ouvrir — « Dans les textes » : la recherche (Entrée) trouve aussi les fichiers VND et SMB
dont un texte TypeEdit (client, référence…) répond, index gardé d'une fois sur l'autre."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication

from vectordrive.core.document import Text
from vectordrive.io import smb
from vectordrive.ui import file_browser as FB

app = QApplication.instance() or QApplication([])


class TestInTexts(unittest.TestCase):
    def setUp(self):
        self.d = pathlib.Path(tempfile.mkdtemp())
        from vectordrive.core import text as TX
        t = Text(text='CLIENT DUPONT', font='Arial', size=5.0)
        t.outline = TX.outline_for(t)
        (self.d / 'Sous').mkdir()
        smb.write([t], self.d / 'Sous' / 'plaque.smb', live_texts=True)
        (self.d / 'autre.dxf').write_text('0\nEOF\n', encoding='ascii')
        self.s = QSettings(os.path.join(tempfile.mkdtemp(), 's.ini'), QSettings.Format.IniFormat)

    def test_texts_found(self):
        self.assertIn('CLIENT DUPONT', smb.texts_of((self.d / 'Sous' / 'plaque.smb').read_bytes()))
        p = FB.FileBrowserPanel(self.s)
        p.EXTS = FB.BROWSER_EXT
        p._text_index = smb.TextIndex(self.d / 'index.json')
        p.show_folder(self.d)
        p.search.setText('dupont')
        p._search()
        self.assertEqual(p.list.count(), 0)                                    # nom seul : rien
        p.in_texts.setChecked(True)
        p._search()
        items = [p.list.item(i) for i in range(p.list.count())]
        self.assertEqual([pathlib.Path(it.data(Qt.ItemDataRole.UserRole)).name for it in items], ['plaque.smb'])
        self.assertIn('CLIENT DUPONT', items[0].toolTip())
        self.assertTrue((self.d / 'index.json').exists())                    # index gardé
        self.assertIn(self.s.value(FB.TEXTS_KEY), (True, 'true'))
        p.deleteLater()

    def test_checkbox_next_to_deep(self):
        p = FB.FileBrowserPanel(self.s)
        nav = FB._layout_of(p.deep, p.layout())
        self.assertIsNotNone(nav)
        self.assertEqual(nav.indexOf(p.in_texts) + 1, nav.indexOf(p.deep))
        p.deleteLater()


if __name__ == '__main__':
    unittest.main()
