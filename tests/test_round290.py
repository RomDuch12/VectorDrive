"""Round 290 : barre de texte de TypeEdit — ses commandes (italique,
souligné, casse, ligne de base, justification, interlignage, compression,
table des caractères, miroir) reliées aux commandes de VectorDrive."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.ui import shortcuts as SC

app = QApplication.instance() or QApplication([])


class TestRapido(unittest.TestCase):
    def test_links(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            for cmd in ('IDB_ITALIQUE', 'IDB_SOULIGNE', 'IDB_PETITES_MAJUSCULES', 'IDB_JUSTIFIER',
                        'IDB_INTERLIGNAGE_TYPOGRAPHIQUE', 'IDB_COMPRESSION_LIGNE', 'IDB_LISTE_CARACTERES',
                        'IDB_POS_SOUS_LIGNE_BASE', 'IDB_REPRODUIRE_STYLE'):
                self.assertIn(SC.TE_ACTIONS[cmd], w.A, cmd)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
