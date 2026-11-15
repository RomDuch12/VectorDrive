"""Round 255 : bibliothèque rangée en sous-dossiers — un dossier montre
aussi les symboles de ses sous-dossiers (la racine n'est plus vide) ; les
vignettes des dessins (DXF…) se font dans un fil à part, sans figer."""
import os
import pathlib
import tempfile
import time
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

DXF = "0\nSECTION\n2\nENTITIES\n0\nLINE\n8\n0\n10\n0\n20\n0\n11\n10\n21\n5\n0\nENDSEC\n0\nEOF\n"


class TestTree(unittest.TestCase):
    def test_subfolders_listed_and_previews_in_background(self):
        from vectordrive.ui import symbols as S
        root = pathlib.Path(tempfile.mkdtemp()) / 'bibliotheque'
        for rel in ('Clients/A/plaque.dxf', 'Clients/B/cadre.dxf', 'Logos/rond.dxf'):
            f = root / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(DXF, encoding='ascii')
        st = QSettings(os.path.join(tempfile.mkdtemp(), 'r.ini'), QSettings.Format.IniFormat)
        st.setValue('symboles/dossiers', [str(root)])
        p = S.SymbolPanel(st)
        p.deep.setChecked(True)                                         # round 447 : « Sous-dossiers » coché
        p.show_folder(root)
        self.assertEqual([p.list.item(i).text() for i in range(p.list.count())],
                         ['Clients', 'Logos', 'Clients/A\nplaque', 'Clients/B\ncadre', 'Logos\nrond'])
        p.show_folder(root / 'Clients')
        self.assertEqual(p.list.count(), 5)                             # .., A, B, et leurs deux fichiers
        t = time.time()
        while (p._pending or p._jobs) and time.time() - t < 20:
            p._load_some()
            time.sleep(0.01)
        self.assertFalse(any(p.list.item(i).icon().isNull() for i in range(p.list.count())))
        p.show_folder(root / 'Logos')                                       # une autre liste : rien de mélangé
        self.assertEqual(p.list.count(), 2)                             # .. et rond
        p.deleteLater()


if __name__ == '__main__':
    unittest.main()
