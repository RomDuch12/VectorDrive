"""Round 411 : ruban TypeEdit — menu Fichier (menu principal), surfaces reliées."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from vectordrive.ui.typeedit_layout import TELayout

app = QApplication.instance() or QApplication([])

MAIN = ['ID_FILE_NEW', 'ID_FILE_OPEN', 'ID_FILE_VIEWER', 'ID_FILE_SAVE', 'ID_FILE_SAVE_AS', 'ID_FICHIER_IMPORTER',
        'ID_FICHIER_EXPORTER', 'ID_FILE_PRINT', 'ID_FILE_PRINT_PREVIEW', 'ID_FILE_PRINT_SETUP', 'ID_FILE_MRU_FILE1',
        'ID_FILE_MRU_FILE2', 'ID_FILE_MRU_FILE3', 'ID_FILE_MRU_FILE4', 'ID_APP_EXIT']


class TestTEMainMenu(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_menu(self):
        """Round 441 : plus de menu Fichier réduit — le bandeau Fichier complet reste, le premier."""
        w = self.w
        self.assertFalse(hasattr(w, '_build_te_main_menu'))
        self.assertTrue(w.file_page.property('ribbon_both'))
        self.assertIsNone(w.ribbon.cornerWidget(Qt.Corner.TopLeftCorner))

    def test_surfaces_linked(self):
        from vectordrive.ui.shortcuts import TE_ACTIONS
        for cmd in ('ID_COMPO_SPHERE', 'ID_COMPO_CYLINDRE', 'ID_CMD_CONE', 'ID_CMD_TORE',
                    'ID_COMPO_CREER_BOX_BREP', 'ID_COMPO_CREER_BILINEAR_SURFACE', 'ID_COMPO_SURFREVOL',
                    'ID_MANIPULER_ZONE_ALIGNER_POINT', 'ID_COMPO_PARALLELPROJECTION'):
            self.assertIn(TE_ACTIONS[cmd], self.w.A, cmd)

    def test_primitive_kind_kept(self):
        w = self.w
        seen = {}

        def fake(key, title, spec, labels, choices=None, onto=None, keep=()):
            seen['kind'], seen['keep'] = spec.kind, keep
            return None
        with mock.patch.object(w, '_typeart_params', fake):
            w.A['relief_torus'].trigger()
        self.assertEqual(seen, {'kind': 'tore', 'keep': ('kind',)})


if __name__ == '__main__':
    unittest.main()
