"""Round 923 : F12, appuis successifs — plein écran, plein écran avec la barre des tâches de Windows, la fenêtre."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r923.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class F12(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.settings.remove('fenetre/plein_ecran_barre')
        self.w.showMaximized()

    def tearDown(self):
        self.w.settings.remove('fenetre/plein_ecran_barre')
        self.w.settings.setValue('fenetre/plein_ecran', False)
        self.w.modified = False
        self.w.close()

    def state(self):
        w = self.w
        frameless = bool(w.windowFlags() & Qt.WindowType.FramelessWindowHint)
        return (w.is_full_screen(), w.isFullScreen(), frameless, w.keeps_taskbar(), w.A['full_screen'].isChecked(),
                w.A['full_screen_taskbar'].isChecked(), w.wants_full_screen())

    def test_three_presses(self):
        a = self.w.A['full_screen']
        with mock.patch.object(type(self.w), '_border_in_full_screen', return_value=True):
            a.trigger()
            self.assertEqual(self.state(), (True, False, True, False, True, False, True))       # plein écran
            a.trigger()
            self.assertEqual(self.state(), (True, False, True, True, True, True, True))         # la barre gardée
            a.trigger()
            self.assertEqual(self.state()[:3] + self.state()[4:5] + self.state()[6:], (False, False, False, False, False))
            self.assertTrue(self.w.isMaximized())                                             # la fenêtre
            a.trigger()                                                                       # et ça recommence
            self.assertEqual(self.state()[:4], (True, False, True, False))

    def test_the_cycle_says_where_it_is(self):
        with mock.patch.object(type(self.w), '_border_in_full_screen', return_value=True):
            self.assertEqual([self.w.cycle_full_screen() for _ in range(4)], ['full', 'taskbar', 'window', 'full'])
        self.assertIn('F12', self.w.A['full_screen'].toolTip())
        self.assertIn('3e', self.w.A['full_screen'].toolTip())


if __name__ == '__main__':
    unittest.main()
