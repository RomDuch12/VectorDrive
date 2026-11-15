"""Round 910 : plein écran. Windows : un liseré d'un pixel autour de la fenêtre en plein écran (la vue OpenGL ne fait
plus passer la fenêtre en plein écran exclusif, qui clignote). Option « Garder la barre des tâches » : VectorDrive sans
cadre sur la zone de travail de l'écran, la barre des tâches de Windows visible et utilisable ; retenue, reprise
aussitôt en plein écran."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r910.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class FullScreen(unittest.TestCase):

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

    def frameless(self) -> bool:
        return bool(self.w.windowFlags() & Qt.WindowType.FramelessWindowHint)

    def test_full_screen_gets_its_border(self):
        with mock.patch.object(type(self.w), '_border_in_full_screen', return_value=True) as border:
            self.w.A['full_screen'].trigger()
        self.assertEqual(self.w.full_screen_mode(), 'full')    # round 956 : plus le plein écran de Qt
        self.assertTrue(self.w.is_full_screen())
        self.assertEqual(border.call_count, 1)
        self.assertFalse(self.w._border_in_full_screen())       # hors de Windows (essais) : rien à faire
        self.w.A['full_screen'].trigger()                       # round 923 : 2e appui, la barre des tâches gardée
        self.w.A['full_screen'].trigger()
        self.assertFalse(self.w.is_full_screen())

    def test_keeping_the_taskbar(self):
        w = self.w
        a = w.A['full_screen_taskbar']
        self.assertTrue(a.isCheckable())
        w.A['full_screen'].trigger()                              # round 923 : F12, puis F12 : la barre gardée
        w.A['full_screen'].trigger()
        self.assertTrue(w.keeps_taskbar() and a.isChecked())
        self.assertFalse(w.isFullScreen())                        # pas le plein écran de Windows
        self.assertTrue(w.is_full_screen())
        self.assertTrue(self.frameless())
        avail = w.screen().availableGeometry()                     # la zone de travail : la barre reste
        g = w.geometry()
        self.assertEqual((g.x(), g.y(), g.width()), (avail.x(), avail.y(), avail.width()))
        # écran factice de 800 px : pas plus haut que lui, sauf la hauteur minimale de la fenêtre
        self.assertLessEqual(g.height(), max(avail.height(), w.minimumSizeHint().height()))
        self.assertTrue(w.wants_full_screen())
        w.A['full_screen'].trigger()
        self.assertFalse(w.is_full_screen())
        self.assertFalse(self.frameless())
        self.assertTrue(w.isMaximized())

    def test_switching_while_in_full_screen(self):
        w = self.w
        with mock.patch.object(type(w), '_border_in_full_screen', return_value=True):
            w.set_full_screen(True)
            self.assertEqual(w.full_screen_mode(), 'full')      # round 956 : sans cadre dans les deux pleins écrans
            w.set_keep_taskbar(True)
            self.assertEqual(w.full_screen_mode(), 'taskbar')
            self.assertTrue(self.frameless() and w.is_full_screen())
            w.set_keep_taskbar(False)
        self.assertEqual(w.full_screen_mode(), 'full')
        self.assertTrue(self.frameless())
        self.assertFalse(w.A['full_screen_taskbar'].isChecked())

    def test_the_option_is_kept_and_shown(self):
        self.w.set_keep_taskbar(True)
        self.w.settings.sync()
        from vectordrive.ui.main_window import MainWindow
        other = MainWindow()
        try:
            self.assertTrue(other.A['full_screen_taskbar'].isChecked())
        finally:
            other.modified = False
            other.close()
        r = self.w.ribbon
        shown = {b.defaultAction() for i in range(r.count()) if r.page(i) for g in r.page(i).groups() for b in g.buttons()}
        self.assertIn(self.w.A['full_screen_taskbar'], shown)


if __name__ == '__main__':
    unittest.main()
