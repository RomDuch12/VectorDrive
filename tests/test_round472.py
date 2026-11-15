"""Round 472 : B (jeu TypeEdit) — la bibliothèque dans sa fenêtre, agrandie ; de nouveau B : fermée."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class TestLibraryKey(unittest.TestCase):
    def test_mapping(self):
        from vectordrive.ui import shortcuts as SC
        self.assertEqual(SC.te_mapping([('ID_PALETTE_LOGO', 'B')]).get('library_big'), ['B'])

    def test_toggle(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            self.assertIn('library_big', w.A)
            self.assertTrue(w.toggle_library_window())
            lw = w._library_window
            self.assertTrue(lw.isVisible())
            self.assertTrue(lw.windowState() & Qt.WindowState.WindowMaximized)
            lw.activateWindow()
            app.processEvents()
            if lw.isActiveWindow():                                       # offscreen : activation possible
                self.assertFalse(w.toggle_library_window())
                self.assertFalse(lw.isVisible())
            lw.close()
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
