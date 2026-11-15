"""Round 586 : imprimer un dessin vide — « Rien à imprimer » au lieu d'une feuille blanche ; indication de la
recherche de la bibliothèque à jour (noms, textes des SMB et VND)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class TestEmpty(unittest.TestCase):
    def test_empty(self):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.symbols import SymbolPanel
        w = MainWindow()
        try:
            self.assertFalse(w.print_dialog(exec_dialog=False, what='dessin'))
            self.assertIn('Rien à imprimer', w.statusBar().currentMessage())
        finally:
            w.modified = False
            w.close()
        self.assertIn('VND', SymbolPanel.SEARCH_HINT)


if __name__ == '__main__':
    unittest.main()
