"""Round 958 : en plein écran sur tout l'écran, la fenêtre a de nouveau un vrai liseré d'un pixel (sa surface ne fait
pas tout l'écran : pas de plein écran exclusif pour la vue 3D) ; il est retiré dans les autres états."""
import importlib.util
import os
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r958.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])


def module():
    return importlib.util.find_spec('vectordrive.ui.winborder')


class Border(unittest.TestCase):

    @unittest.skipUnless(sys.platform == 'win32', 'messages de Windows')
    def test_the_filter_answers_the_client_area(self):
        self.assertIsNotNone(module(), 'pas de liseré pour la fenêtre sans cadre')            # avant
        import ctypes
        from ctypes import wintypes
        from vectordrive.ui import winborder
        f = winborder.BorderFilter(0x1234)
        rect = wintypes.RECT(0, 0, 1920, 1080)
        msg = wintypes.MSG()
        msg.hWnd, msg.message, msg.wParam, msg.lParam = 0x1234, winborder.WM_NCCALCSIZE, 1, ctypes.addressof(rect)
        self.assertEqual(f.nativeEventFilter(b'windows_generic_MSG', ctypes.addressof(msg)), (True, 0))
        self.assertEqual((rect.left, rect.top, rect.right, rect.bottom), (1, 1, 1919, 1079))   # un pixel de chaque côté
        msg.hWnd = 0x9999                                                   # une autre fenêtre : pas la nôtre
        self.assertEqual(f.nativeEventFilter(b'windows_generic_MSG', ctypes.addressof(msg)), (False, 0))
        msg.hWnd, msg.message = 0x1234, 0x0005                              # un autre message (WM_SIZE)
        self.assertEqual(f.nativeEventFilter(b'windows_generic_MSG', ctypes.addressof(msg)), (False, 0))
        self.assertEqual((rect.left, rect.top, rect.right, rect.bottom), (1, 1, 1919, 1079))

    def test_only_the_whole_screen_state_has_the_border(self):
        self.assertIsNotNone(module(), 'pas de liseré pour la fenêtre sans cadre')            # avant
        from vectordrive.ui import winborder
        from vectordrive.ui.main_window import MainWindow
        self.assertFalse(winborder.supported())                             # hors écran : rien de natif
        w = MainWindow()
        w.show()
        try:
            self.assertFalse(w._border_in_full_screen())
            with mock.patch.object(winborder, 'set_border', return_value=True) as border:
                self.assertEqual(w.cycle_full_screen(), 'full')
                self.assertEqual([c.args[1] for c in border.call_args_list], [True])
                g, s = w.geometry(), w.screen().geometry()
                self.assertEqual(g.width(), s.width())                      # l'écran, sans débord d'un pixel
                self.assertLessEqual(g.height(), max(s.height(), w.minimumSizeHint().height()))   # écran factice
                m = w.contentsMargins()                                     # la surface a perdu deux pixels
                self.assertEqual((m.left(), m.top(), m.right(), m.bottom()), (0, 0, 2, 2))
                self.assertEqual(w.cycle_full_screen(), 'taskbar')          # la barre des tâches gardée : sans liseré
                self.assertEqual(w.contentsMargins().right(), 0)
                self.assertEqual([c.args[1] for c in border.call_args_list], [True, False])
                self.assertEqual(w.cycle_full_screen(), 'window')
                self.assertEqual([c.args[1] for c in border.call_args_list], [True, False, False])
                self.assertIs(border.call_args_list[0].args[0], w)
        finally:
            w.settings.remove('fenetre/plein_ecran_barre')
            w.settings.setValue('fenetre/plein_ecran', False)
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
