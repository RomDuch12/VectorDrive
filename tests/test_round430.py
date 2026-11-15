"""Round 430 : VectorDrive en plein écran (Maj+F11), retenu."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class TestFullScreen(unittest.TestCase):
    def test_toggle(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            self.assertEqual([k.toString() for k in w.A['full_screen'].shortcuts()], ['F12', 'Shift+F11'])   # 903
            w.A['full_screen'].trigger()
            self.assertEqual(w.full_screen_mode(), 'full')   # round 956 : plus le plein écran de Qt
            self.assertTrue(w.wants_full_screen())
            self.assertTrue(w.A['full_screen'].isChecked())
            w.A['full_screen'].trigger()                     # round 923 : 2e appui, la barre des tâches gardée
            self.assertTrue(w.is_full_screen() and w.keeps_taskbar())
            w.A['full_screen'].trigger()
            self.assertFalse(w.is_full_screen())
            self.assertFalse(w.wants_full_screen())
        finally:
            w.settings.setValue('fenetre/plein_ecran', False)
            w.settings.remove('fenetre/plein_ecran_barre')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
