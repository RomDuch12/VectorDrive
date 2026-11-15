"""Round 204 : palettes de TypeEdit en menus surgissants."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication


class TestPalettes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_mapping(self):
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual(TE_ACTIONS['ID_COMPO_SHOWPALALIGN'], 'palette_align')
        self.assertEqual(TE_ACTIONS['ID_COMPO_SHOWPALSPECIALEFFECTS'], 'palette_effects')
        self.assertEqual(TE_ACTIONS['ID_COMPO_SHOWPALFXTART'], 'palette_typeart')
        self.assertEqual(TE_ACTIONS['ID_OPENPAL_METIER'], 'palette_trades')

    def test_menus(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            for key, (_title, keys) in MainWindow.PALETTES.items():
                self.assertTrue(all(k in w.A for k in keys), key)                 # aucune commande absente
                w.A[key].trigger()                                                 # sans bloquer
                m = w._last_palette
                self.assertEqual(len(m.actions()), len(keys))
                m.close()
            self.assertIn(w.A['texture_create'], w.show_palette('palette_effects').actions())
            w._last_palette.close()
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
