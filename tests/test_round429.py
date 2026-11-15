"""Round 429 : usinage par couleur caché par défaut, montré par une case."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class TestColorMode(unittest.TestCase):
    def test_hidden_by_default(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            s = w.settings
            s.setValue('fao/usinage_couleur', False)
            s.setValue('fao/mode_usinage', 'couleur')                  # ancien réglage : sans effet
            pal, cp = w.cam_palette, w.cam_panel
            pal.color_on.setChecked(False)
            self.assertFalse(pal.mode_row.isVisibleTo(pal))
            self.assertEqual(cp.machining_mode(), 'selection')
            pal.color_on.setChecked(True)                              # la case : le choix paraît
            self.assertTrue(pal.mode_row.isVisibleTo(pal))
            self.assertEqual(cp.machining_mode(), 'couleur')
            pal.set_mode('selection')
            self.assertEqual(cp.machining_mode(), 'selection')
            pal.color_on.setChecked(False)
            pal.set_mode('couleur')                                    # choisir les couleurs l'active
            self.assertTrue(pal.color_on.isChecked())
            self.assertEqual(cp.machining_mode(), 'couleur')
        finally:
            w.settings.setValue('fao/usinage_couleur', False)
            w.settings.setValue('fao/mode_usinage', 'selection')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
