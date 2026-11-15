"""Round 397 : couleurs pour daltoniens (TypeEdit : ColourBlind)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.ui import cam_panel as CP

app = QApplication.instance() or QApplication([])


class TestColourBlind(unittest.TestCase):
    def test_toggle(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            self.assertEqual(CP.path_colors(), CP.PATH_COLORS)
            w.set_colour_blind(True)
            self.assertEqual(CP.path_colors(), CP.PATH_COLORS_CB)
            self.assertTrue(w.A['colour_blind'].isChecked())
            self.assertIn(w.settings.value('vue/daltonien'), (True, 'true'))
            self.assertEqual(len(set(CP.PATH_COLORS_CB)), len(CP.PATH_COLORS_CB))
        finally:
            w.set_colour_blind(False)
            w.modified = False
            w.close()
        self.assertEqual(CP.path_colors(), CP.PATH_COLORS)


if __name__ == '__main__':
    unittest.main()
