"""Round 982 : un panneau ancrable peut aller dans sa propre fenêtre — réduire, agrandir, fermer, plein écran — et en
revenir (`ui/panel_window`, `MainWindow.dock_as_window`)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r982.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QDockWidget, QLabel  # noqa: E402

app = QApplication.instance() or QApplication([])
KEYS = ('min', 'max', 'close')


class PanelInItsWindow(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.dock = QDockWidget('Essai', self.w)
        self.dock.setObjectName('essai_982')
        self.content = QLabel('contenu')
        self.dock.setWidget(self.content)
        self.w.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock)
        for k in ('en_fenetre', 'plein_ecran', 'geometrie'):
            self.w.settings.remove(f'essai/fenetre/{k}')

    def tearDown(self):
        host = getattr(self.dock, '_as_window', None)
        if host is not None and host.in_window():
            host.to_dock(show=False)
        self.w.modified = False
        self.w.close()

    def host(self):
        make = getattr(self.w, 'dock_as_window', None)
        self.assertIsNotNone(make)                       # avant : détaché, un panneau n'a ni réduire, ni agrandir
        return make(self.dock, 'essai/fenetre')

    def shown(self, win):
        return [win.buttons[k].isVisibleTo(win) for k in KEYS]

    def test_window_with_its_buttons_and_full_screen(self):
        host = self.host()
        self.assertIs(self.w.dock_as_window(self.dock), host)                 # un seul par panneau
        self.assertFalse(host.in_window())
        win = host.to_window(full_screen=False)
        self.assertIs(win.content(), self.content)
        self.assertIs(host.content(), self.content)
        self.assertTrue(win.isVisible() and win.isWindow() and win.parent() is None)
        self.assertFalse(self.dock.isVisible())
        self.assertEqual(win.windowTitle(), 'Essai')
        self.assertFalse(win.testAttribute(Qt.WidgetAttribute.WA_QuitOnClose))  # ne retient pas l'application
        self.assertEqual(self.shown(win), [False] * 3)                        # la barre de titre du système suffit
        self.assertTrue(win.buttons['dock'].isVisibleTo(win) and win.buttons['full'].isVisibleTo(win))
        win.buttons['full'].click()
        self.assertTrue(win.is_full_screen())
        self.assertEqual(self.shown(win), [True] * 3)                         # plein écran : réduire, agrandir, fermer
        self.assertTrue(win.title.isVisibleTo(win))
        win.buttons['min'].click()
        self.assertTrue(win.isMinimized())
        win.setWindowState(win.windowState() & ~Qt.WindowState.WindowMinimized)
        win.buttons['max'].click()                                            # agrandir : hors du plein écran
        self.assertFalse(win.is_full_screen())
        self.assertTrue(win.isMaximized())
        self.assertEqual(self.shown(win), [False] * 3)
        self.assertEqual(win.toggle_maximized(), 'normal')
        self.assertTrue(win.toggle_full_screen())
        QTest.keyClick(win, Qt.Key.Key_Escape)                                # Échap sort du plein écran
        self.assertFalse(win.is_full_screen())

    def test_close_dock_and_reopen(self):
        host = self.host()
        self.assertFalse(host.wants_window())
        self.assertFalse(host.open(show=False))                               # rien de retenu : ancré
        win = host.to_window(full_screen=True)
        self.assertTrue(host.wants_window())
        win.close()                                                           # fermer : le panneau est fermé
        self.assertIs(self.dock.widget(), self.content)
        self.assertFalse(self.dock.isVisible() or win.isVisible())
        self.assertFalse(host.is_open())
        self.assertTrue(host.open())                                          # rouvert où il était : sa fenêtre,
        self.assertTrue(host.in_window() and win.isVisible())
        self.assertTrue(win.is_full_screen())                                 # en plein écran comme à sa fermeture
        self.assertTrue(host.is_open())
        win.buttons['dock'].click()                                           # ancrer : de retour dans le panneau
        self.assertIs(self.dock.widget(), self.content)
        self.assertFalse(self.dock.isHidden())                                # montré, dans la fenêtre principale
        self.assertFalse(win.isVisible() or host.wants_window())
        self.assertTrue(host.toggle())                                        # et de l'un à l'autre
        self.assertFalse(host.toggle())

    def test_main_window_closed_takes_the_panel_back(self):
        host = self.host()
        self.w.show()
        win = host.to_window(full_screen=False)
        self.assertTrue(win.isVisible())
        self.w.modified = False
        self.w.close()
        app.processEvents()
        self.assertIs(self.dock.widget(), self.content)                       # la fenêtre du panneau ne lui survit pas
        self.assertFalse(win.isVisible())
        self.assertTrue(host.wants_window())                                  # et rouvrira comme elle était


if __name__ == '__main__':
    unittest.main()
