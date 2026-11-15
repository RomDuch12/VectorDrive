"""Round 569 : Ouvrir — un chemin tapé dans la recherche puis Entrée : son dossier (ou le fichier ouvert),
comme la barre d'adresse de l'explorateur ; F5 actualise."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from vectordrive.ui import file_browser as FB

app = QApplication.instance() or QApplication([])


class TestTypedPath(unittest.TestCase):
    def test_folder_and_file(self):
        d = pathlib.Path(tempfile.mkdtemp())
        (d / 'Sous').mkdir()
        f = d / 'Sous' / 'a.dxf'
        f.write_text('0\nEOF\n', encoding='ascii')
        s = QSettings(os.path.join(tempfile.mkdtemp(), 's.ini'), QSettings.Format.IniFormat)
        p = FB.FileBrowserPanel(s)
        p.EXTS = FB.BROWSER_EXT
        p.show_folder(d)
        p.search.setText(str(d / 'Sous'))
        p._search()
        self.assertEqual(p._folder, d / 'Sous')
        self.assertEqual(p.search.text(), '')
        opened = []
        p.openRequested.connect(opened.append)
        p.search.setText(f'"{f}"')
        p._search()
        self.assertEqual(opened, [str(f)])
        p.search.setText(str(d / 'absent' / 'x'))                             # chemin absent : recherche
        p._search()
        self.assertIn('fichier(s)', p.where.text())
        p.deleteLater()


if __name__ == '__main__':
    unittest.main()
