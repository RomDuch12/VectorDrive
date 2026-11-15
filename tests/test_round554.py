"""Round 554 : correctif — « Sous-dossiers » et la recherche d'Ouvrir sur un dossier d'au moins 25
sous-dossiers (avancement indéterminé « n dossiers lus » : la fonction appelée n'existait pas)."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from vectordrive.core import progress as P
from vectordrive.ui import file_browser as FB
from vectordrive.ui.symbols import walk_files

app = QApplication.instance() or QApplication([])


def many_dirs(n: int = 60) -> pathlib.Path:
    d = pathlib.Path(tempfile.mkdtemp())
    for i in range(n):
        sub = d / f'dossier {i:02d}'
        sub.mkdir()
        (sub / f'plaque {i}.dxf').write_text('0\nEOF\n', encoding='ascii')
    return d


class TestManyFolders(unittest.TestCase):
    def test_walk_reports(self):
        d = many_dirs()
        task = P.Task('essai')
        token = P.attach(task)
        try:
            found = walk_files(d, ('.dxf',))
        finally:
            P.detach(token)
        self.assertEqual(len(found), 60)
        self.assertEqual(task.fraction, -1.0)                                  # indéterminé
        self.assertIn('dossiers lus', task.text)

    def test_browser(self):
        d = many_dirs()
        s = QSettings(os.path.join(tempfile.mkdtemp(), 's.ini'), QSettings.Format.IniFormat)
        p = FB.FileBrowserPanel(s)
        p.EXTS = FB.BROWSER_EXT
        p.show_folder(d)
        p.deep.setChecked(True)
        self.assertEqual(sum(1 for i in range(p.list.count()) if p.list.item(i).data(FB.ROLE_KIND) is None), 60)
        p.deep.setChecked(False)
        p.search.setText('plaque 1')
        p._search()
        self.assertIn('fichier(s)', p.where.text())
        p.deleteLater()


if __name__ == '__main__':
    unittest.main()
