"""Round 551 : Ouvrir — affichage, tri et taille des vignettes par défaut dans F10 › Fichiers ; largeurs des
colonnes retenues ; Ctrl+F : la recherche, Échap : effacée."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from vectordrive.ui import file_browser as FB
from vectordrive.ui import options as O

app = QApplication.instance() or QApplication([])


class TestOpenSettings(unittest.TestCase):
    def setUp(self):
        self.s = QSettings(os.path.join(tempfile.mkdtemp(), 's.ini'), QSettings.Format.IniFormat)

    def test_options(self):
        for key in (FB.VIEW_KEY, FB.SORT_KEY, 'navigateur/taille'):
            self.assertIn(key, O.BY_KEY)
        self.assertEqual(O.BY_KEY[FB.VIEW_KEY].default, 'details')
        self.s.setValue(FB.VIEW_KEY, 'vignettes')                      # réglé dans F10 : le navigateur suit
        p = FB.FileBrowserPanel(self.s)
        self.assertEqual(p._view, 'vignettes')
        p.deleteLater()

    def test_columns_kept(self):
        p = FB.FileBrowserPanel(self.s)
        p.columns.resizeSection(0, 250)
        self.assertEqual(int(self.s.value(FB.COLUMNS_KEY)[0]), 250)
        p.deleteLater()
        q = FB.FileBrowserPanel(self.s)
        self.assertEqual(q.columns.sectionSize(0), 250)
        q.deleteLater()

    def test_escape_clears(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        p = FB.FileBrowserPanel(self.s)
        p.show()
        p.search.setFocus()
        p.search.setText('abc')
        QTest.keyClick(p.search, Qt.Key.Key_Escape)
        self.assertEqual(p.search.text(), '')
        p.deleteLater()


if __name__ == '__main__':
    unittest.main()
