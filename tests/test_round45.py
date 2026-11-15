"""Round 45 : recherche de symboles par les textes qu'ils contiennent."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import text as TX
from vectordrive.core.document import Text
from vectordrive.core.geom import Affine
from vectordrive.io import smb


def make_symbol(path, txt):
    t = Text(text=txt, font='Arial', size=4, matrix=Affine())
    t.outline = TX.outline_for(t)
    smb.write([t], path, live_texts=True)


class TestSymbolSearch(unittest.TestCase):
    def test_search_by_text_and_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = pathlib.Path(tmp) / 'lib'
            d.mkdir()
            make_symbol(d / 'plaque_porte.smb', 'Référence OT0550 gravée')
            make_symbol(d / 'autre.smb', 'Rien à voir')
            idx = smb.TextIndex(pathlib.Path(tmp) / 'index.json')
            r = smb.search([d], 'ot0550', idx)
            self.assertEqual([(f.name, h) for f, h in r], [('plaque_porte.smb', 'Référence OT0550 gravée')])
            self.assertTrue((pathlib.Path(tmp) / 'index.json').exists())
            # accents et casse ignorés ; nom de fichier aussi
            self.assertEqual(len(smb.search([d], 'REFERENCE', smb.TextIndex(idx.path))), 1)
            self.assertEqual([f.name for f, _h in smb.search([d], 'porte', None)], ['plaque_porte.smb'])
            # symbole modifié : relu
            make_symbol(d / 'autre.smb', 'OT0550 aussi')
            self.assertEqual(len(smb.search([d], 'OT0550', smb.TextIndex(idx.path))), 2)

    def test_panel(self):
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from PySide6.QtCore import QSettings
        from vectordrive.ui.symbols import SymbolPanel
        with tempfile.TemporaryDirectory() as tmp:
            d = pathlib.Path(tmp) / 'lib'
            d.mkdir()
            make_symbol(d / 's1.smb', 'Cuir pleine fleur')
            st = QSettings(str(pathlib.Path(tmp) / 'r.ini'), QSettings.Format.IniFormat)
            st.setValue('symboles/dossiers', [str(d)])
            p = SymbolPanel(st)
            p.search.setText('pleine')
            p._search()
            self.assertEqual(p.list.count(), 1)
            self.assertIn('Cuir pleine fleur', p.list.item(0).text())


if __name__ == '__main__':
    unittest.main()
