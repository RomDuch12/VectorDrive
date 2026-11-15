"""Round 574 : Ouvrir — dernières recherches retenues (20 au plus, sans doublon) et proposées à la frappe."""
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


class TestHistory(unittest.TestCase):
    def test_history(self):
        d = pathlib.Path(tempfile.mkdtemp())
        (d / 'plaque.dxf').write_text('0\nEOF\n', encoding='ascii')
        s = QSettings(os.path.join(tempfile.mkdtemp(), 's.ini'), QSettings.Format.IniFormat)
        p = FB.FileBrowserPanel(s)
        p.EXTS = FB.BROWSER_EXT
        p.show_folder(d)
        for q in ('plaque', 'logo', 'Plaque'):
            p.search.setText(q)
            p._search()
        self.assertEqual(p.search_history(), ['Plaque', 'logo'])                # récente d'abord, sans doublon
        self.assertEqual(p.search.completer().model().stringList(), ['Plaque', 'logo'])
        for i in range(30):
            p.remember_search(f'q{i}')
        self.assertEqual(len(p.search_history()), FB.HISTORY_MAX)
        q = FB.FileBrowserPanel(s)                                             # retenues d'une fois sur l'autre
        self.assertEqual(q.search.completer().model().stringList()[0], 'q29')
        p.deleteLater()
        q.deleteLater()


if __name__ == '__main__':
    unittest.main()
