"""Round 956 : en plein écran la fenêtre n'a plus de barre de titre ; ses boutons — Réduire, Fenêtre, Fermer —
paraissent tout à droite de la rangée des onglets, dans les deux pleins écrans du cycle de F12."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r956.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QToolButton  # noqa: E402

app = QApplication.instance() or QApplication([])


class WindowButtons(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.show()
        border = mock.patch.object(type(self.w), '_border_in_full_screen', return_value=True)
        border.start()
        self.addCleanup(border.stop)

    def tearDown(self):
        self.w.settings.remove('fenetre/plein_ecran_barre')
        self.w.settings.setValue('fenetre/plein_ecran', False)
        self.w.modified = False
        self.w.close()

    def box(self):
        box = getattr(self.w.ribbon, 'window_buttons', None)
        self.assertIsNotNone(box, 'pas de boutons de fenêtre dans le ruban')                    # avant
        return box

    def test_the_cycle_does_not_rely_on_qt(self):
        """Sur un vrai poste, Qt ne se croit plus en plein écran dès que la fenêtre n'est pas exactement à la taille
        de l'écran : la boucle de F12 doit tenir son état elle-même."""
        w = self.w
        with mock.patch.object(type(w), 'isFullScreen', return_value=False):
            got = [w.cycle_full_screen() for _ in range(4)]
        self.assertEqual(got, ['full', 'taskbar', 'window', 'full'])        # avant : 'full' à chaque appui
        self.assertEqual(w.full_screen_mode(), 'full')
        self.assertFalse(w.windowState() & Qt.WindowState.WindowFullScreen)  # pas le plein écran de Qt
        self.assertTrue(w.windowFlags() & Qt.WindowType.FramelessWindowHint)
        g, screen = w.geometry(), w.screen().geometry()
        self.assertEqual((g.x(), g.y(), g.width()), (screen.x(), screen.y(), screen.width()))
        w.set_keep_taskbar(True)                                            # d'un plein écran à l'autre : sans cadre
        self.assertEqual(w.full_screen_mode(), 'taskbar')
        self.assertTrue(w.windowFlags() & Qt.WindowType.FramelessWindowHint)
        w.set_full_screen(False)
        self.assertEqual(w.full_screen_mode(), '')
        self.assertFalse(w.windowFlags() & Qt.WindowType.FramelessWindowHint)
        self.assertTrue(w.isVisible() and not w.isMinimized())              # round 977 : la fenêtre d'avant le plein écran

    def test_shown_whenever_the_title_bar_is_gone(self):
        w, box = self.w, self.box()
        self.assertTrue(box.isHidden())                                     # en fenêtre : la barre de titre a les siens
        self.assertEqual([b.objectName() for b in box.findChildren(QToolButton)],
                         ['ribbonWindowMinimize', 'ribbonWindowRestore', 'ribbonWindowClose'])
        corner = w.ribbon._corner_layout
        self.assertEqual(corner.indexOf(box), corner.count() - 1)           # tout à droite, après Options et Aide
        self.assertEqual(w.cycle_full_screen(), 'full')
        self.assertFalse(box.isHidden())
        self.assertEqual(w.cycle_full_screen(), 'taskbar')                  # la barre des tâches gardée : sans cadre
        self.assertFalse(box.isHidden())
        self.assertEqual(w.cycle_full_screen(), 'window')
        self.assertTrue(box.isHidden())
        self.assertTrue(all(b.toolTip() and b.text() for b in box.findChildren(QToolButton)))

    def test_they_do_what_the_title_bar_did(self):
        w, box = self.w, self.box()
        minimize, restore, close = box.findChildren(QToolButton)
        w.set_full_screen(True)
        with mock.patch.object(type(w), 'showMinimized') as shown:
            minimize.click()
        shown.assert_called_once()
        with mock.patch.object(type(w), 'close') as closed:
            close.click()
        closed.assert_called_once()
        restore.click()
        self.assertFalse(w.is_full_screen())
        self.assertTrue(box.isHidden())
        self.assertFalse(w.A['full_screen'].isChecked())

    def test_a_window_opened_in_full_screen_has_them(self):
        w, box = self.w, self.box()
        w.set_keep_taskbar(True)
        w.set_full_screen(True)                                             # comme au lancement, plein écran retenu
        self.assertFalse(box.isHidden())
        self.assertTrue(w.apply_ribbon_layout() in (True, False))          # le ruban refait garde ses boutons
        self.assertFalse(getattr(w.ribbon, 'window_buttons').isHidden())


if __name__ == '__main__':
    unittest.main()
