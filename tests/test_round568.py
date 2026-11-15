"""Round 568 : F10 › Fichiers « montrer les éléments masqués » (comme l'explorateur) — appliqué à Ouvrir et
à la Bibliothèque."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class TestShowHidden(unittest.TestCase):
    def test_option(self):
        from vectordrive.ui import symbols as S
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.options import BY_KEY
        self.assertFalse(BY_KEY['navigateur/caches'].default)
        w = MainWindow()
        try:
            w.settings.setValue('navigateur/caches', True)
            w.apply_options()
            self.assertTrue(S.SHOW_HIDDEN)
        finally:
            w.settings.setValue('navigateur/caches', False)
            w.apply_options()
            w.modified = False
            w.close()
        self.assertFalse(S.SHOW_HIDDEN)


if __name__ == '__main__':
    unittest.main()
