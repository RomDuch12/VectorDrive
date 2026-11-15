"""Round 243 : B ouvre la bibliothèque de l'atelier — toujours en tête de
l'arbre (même avec d'autres dossiers enregistrés), dépliée sur ses
sous-dossiers, son contenu en vignettes."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

DXF = """0\nSECTION\n2\nENTITIES\n0\nLINE\n8\n0\n10\n0\n20\n0\n11\n10\n21\n5\n0\nENDSEC\n0\nEOF\n"""


class TestLibraryKey(unittest.TestCase):
    def setUp(self):
        self.lib = pathlib.Path(tempfile.mkdtemp()) / 'bibliotheque'
        (self.lib / 'Plaques').mkdir(parents=True)
        (self.lib / 'Logos').mkdir()
        (self.lib / 'cadre.dxf').write_text(DXF, encoding='ascii')
        (self.lib / 'Plaques' / 'porte.dxf').write_text(DXF, encoding='ascii')
        self._old = os.environ.get('VECTORDRIVE_BIBLIOTHEQUE')
        os.environ['VECTORDRIVE_BIBLIOTHEQUE'] = str(self.lib)

    def tearDown(self):
        if self._old is None:
            os.environ.pop('VECTORDRIVE_BIBLIOTHEQUE', None)
        else:
            os.environ['VECTORDRIVE_BIBLIOTHEQUE'] = self._old

    def test_saved_roots_keep_library_first(self):
        from PySide6.QtCore import QSettings
        from vectordrive.ui.symbols import SymbolPanel
        other = pathlib.Path(tempfile.mkdtemp())
        st = QSettings(str(other / 'r.ini'), QSettings.Format.IniFormat)
        st.setValue('symboles/dossiers', [str(other)])
        p = SymbolPanel(st)
        self.assertEqual(p.roots[0], self.lib)
        self.assertIn(other, p.roots)
        p.open_library()
        top = p.tree.currentItem()
        self.assertTrue(top.isExpanded())
        self.assertEqual(sorted(top.child(i).text(0) for i in range(top.childCount())), ['Logos', 'Plaques'])
        self.assertEqual([p.list.item(i).text() for i in range(p.list.count())],
                         ['Logos', 'Plaques', 'cadre'])                 # round 447 : dossiers, puis fichiers
        p.deep.setChecked(True)                                         # « Sous-dossiers » : leurs fichiers aussi
        self.assertEqual([p.list.item(i).text() for i in range(p.list.count())],
                         ['Logos', 'Plaques', 'cadre', 'Plaques\nporte'])
        p.deep.setChecked(False)
        p.deleteLater()

    def test_b_opens_library(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.dock_symbols.setVisible(False)
            w.A['symbols'].setChecked(False)
            w.A['symbols'].trigger()                                        # B (jeu TypeEdit)
            self.assertTrue(w.dock_symbols.isVisibleTo(w))
            self.assertEqual(pathlib.Path(w.symbols.current_folder()), self.lib)
            self.assertEqual(w.symbols.list.count(), 3)                  # Logos, Plaques, cadre (round 447)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
