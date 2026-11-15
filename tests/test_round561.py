"""Round 561 : Ouvrir comme l'explorateur — dossiers et fichiers cachés ou système de Windows omis (liste,
sous-dossiers, recherche), en-tête des colonnes à hauteur de ligne, pas de curseur de vignettes en Détails."""
import os
import pathlib
import sys
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from vectordrive.ui import file_browser as FB
from vectordrive.ui.symbols import is_hidden, walk_files

app = QApplication.instance() or QApplication([])


def hide(p: pathlib.Path) -> None:
    import ctypes
    ctypes.windll.kernel32.SetFileAttributesW(str(p), 0x2)


@unittest.skipUnless(sys.platform == 'win32', 'attributs de Windows')
class TestHidden(unittest.TestCase):
    def setUp(self):
        self.d = pathlib.Path(tempfile.mkdtemp())
        (self.d / 'Visible').mkdir()
        (self.d / 'Cache').mkdir()
        (self.d / 'Cache' / 'dedans.dxf').write_text('0\nEOF\n', encoding='ascii')
        (self.d / 'Visible' / 'vu.dxf').write_text('0\nEOF\n', encoding='ascii')
        (self.d / 'secret.dxf').write_text('0\nEOF\n', encoding='ascii')
        (self.d / 'plaque.dxf').write_text('0\nEOF\n', encoding='ascii')
        hide(self.d / 'Cache')
        hide(self.d / 'secret.dxf')

    def test_hidden(self):
        self.assertTrue(is_hidden(self.d / 'Cache'))
        self.assertFalse(is_hidden(self.d / 'Visible'))
        names = sorted(p.name for p in walk_files(self.d, ('.dxf',)))
        self.assertEqual(names, ['plaque.dxf', 'vu.dxf'])
        s = QSettings(os.path.join(tempfile.mkdtemp(), 's.ini'), QSettings.Format.IniFormat)
        p = FB.FileBrowserPanel(s)
        p.EXTS = FB.BROWSER_EXT
        p.show_folder(self.d)
        shown = [p.list.item(i).text() for i in range(p.list.count())]
        self.assertIn('Visible', shown)
        self.assertIn('plaque.dxf', shown)
        self.assertNotIn('Cache', shown)
        self.assertNotIn('secret.dxf', shown)
        self.assertFalse(p.size.isVisibleTo(p))                                # Détails : pas de curseur
        self.assertLess(p.columns.height(), 40)
        p.set_view('vignettes')
        self.assertTrue(p.size.isVisibleTo(p))
        p.set_view('details')
        from vectordrive.ui import symbols as S                              # r568 : éléments masqués montrés
        S.SHOW_HIDDEN = True
        try:
            p.show_folder(self.d)
            shown = [p.list.item(i).text() for i in range(p.list.count())]
            self.assertIn('Cache', shown)
            self.assertIn('secret.dxf', shown)
        finally:
            S.SHOW_HIDDEN = False
        p.deleteLater()


if __name__ == '__main__':
    unittest.main()
