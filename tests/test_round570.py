"""Round 570 : Ouvrir en Détails — colonne « Emplacement » (dossier de chaque fichier) dans les listes qui
mêlent plusieurs dossiers (Récents, Favoris, Accès rapide), masquée dans un dossier."""
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


class TestPlace(unittest.TestCase):
    def test_recents_show_place(self):
        a, b = pathlib.Path(tempfile.mkdtemp()), pathlib.Path(tempfile.mkdtemp())
        for d in (a, b):
            (d / 'plaque.dxf').write_text('0\nEOF\n', encoding='ascii')
        s = QSettings(os.path.join(tempfile.mkdtemp(), 's.ini'), QSettings.Format.IniFormat)
        s.setValue('fichiers/recents', [str(a / 'plaque.dxf'), str(b / 'plaque.dxf')])
        p = FB.FileBrowserPanel(s)
        p.EXTS = FB.BROWSER_EXT
        p.show_recents()
        self.assertFalse(p.columns.isSectionHidden(FB.PLACE_COLUMN))
        places = [p.list.item(i).data(FB.ROLE_DETAILS)[3] for i in range(p.list.count())]
        self.assertEqual(sorted(places), sorted([str(a), str(b)]))            # même nom, deux dossiers
        p.show_folder(a)
        self.assertTrue(p.columns.isSectionHidden(FB.PLACE_COLUMN))
        p.deleteLater()


if __name__ == '__main__':
    unittest.main()
