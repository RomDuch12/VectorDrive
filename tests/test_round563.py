"""Round 563 : Ouvrir en Détails — dates et tailles reprises de la lecture du dossier (Windows les donne
avec la liste) : plus un accès disque par fichier (dossier réseau de milliers de fichiers)."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from vectordrive.ui import file_browser as FB

app = QApplication.instance() or QApplication([])


class TestStats(unittest.TestCase):
    def test_no_stat_per_file(self):
        d = pathlib.Path(tempfile.mkdtemp())
        (d / 'Sous').mkdir()
        for i in range(50):
            (d / f'p{i:02d}.dxf').write_text('0\nEOF\n' * (i + 1), encoding='ascii')
            (d / 'Sous' / f'q{i:02d}.dxf').write_text('0\nEOF\n', encoding='ascii')
        s = QSettings(os.path.join(tempfile.mkdtemp(), 's.ini'), QSettings.Format.IniFormat)
        s.setValue(FB.SORT_KEY, 'taille')
        p = FB.FileBrowserPanel(s)
        p.EXTS = FB.BROWSER_EXT
        real = pathlib.Path.stat
        calls = []

        def counted(self, *a, **k):
            if self.suffix.lower() == '.dxf':
                calls.append(self)
            return real(self, *a, **k)
        with mock.patch.object(pathlib.Path, 'stat', counted):
            p.show_folder(d)
            p.deep.setChecked(True)
        self.assertEqual(calls, [])                                            # rien de plus que la liste
        rows = [p.list.item(i) for i in range(p.list.count()) if p.list.item(i).data(FB.ROLE_KIND) is None]
        self.assertEqual(rows[0].text(), 'p49.dxf')                            # tri par taille : la plus grosse
        self.assertGreater(rows[0].data(FB.ROLE_DETAILS)[1], rows[1].data(FB.ROLE_DETAILS)[1])
        self.assertIn('Sous/q00.dxf', [r.text() for r in rows])
        self.assertIsNotNone(next(r for r in rows if r.text() == 'Sous/q00.dxf').data(FB.ROLE_DETAILS)[1])
        p.deep.setChecked(False)
        p.deleteLater()


if __name__ == '__main__':
    unittest.main()
