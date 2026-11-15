"""Round 650 : Ctrl + touche de la rangée des chiffres quelle que soit la
disposition du clavier — AZERTY : Ctrl+& … Ctrl+à font Ctrl+1 … Ctrl+0
(touche virtuelle Windows VK_0 … VK_9), avant tout autre raccourci."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])
CTRL = Qt.KeyboardModifier.ControlModifier


def key(kind, k, vk, text='', mods=CTRL):
    return QKeyEvent(kind, k, mods, 0, vk, 0, text)


class TestDigitRow(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def press(self, k, vk, text='', mods=CTRL):
        over = QApplication.sendEvent(self.w.canvas, key(QEvent.Type.ShortcutOverride, k, vk, text, mods))
        down = QApplication.sendEvent(self.w.canvas, key(QEvent.Type.KeyPress, k, vk, text, mods))
        app.processEvents()
        return over, down

    def test_azerty(self):
        w = self.w
        before = w.A['direction'].isChecked()
        self.assertEqual(self.press(Qt.Key.Key_Egrave, 0x37, 'è'), (True, True))   # Ctrl+è = Ctrl+7 : Sens
        self.assertNotEqual(w.A['direction'].isChecked(), before)
        colors = w.A['tool_colors'].isChecked()
        self.press(Qt.Key.Key_Underscore, 0x38, '_')                              # Ctrl+_ = Ctrl+8
        self.assertNotEqual(w.A['tool_colors'].isChecked(), colors)
        fired = []
        w.A['zoom_fit'].triggered.connect(lambda *_a: fired.append(1))
        self.press(Qt.Key.Key_Agrave, 0x30, 'à')                                  # Ctrl+à = Ctrl+0 : Tout voir
        self.assertEqual(fired, [1])

    def test_left_to_qt(self):
        w = self.w
        f = w._digit_row
        self.assertFalse(f(key(QEvent.Type.ShortcutOverride, Qt.Key.Key_7, 0x37, '7')))      # déjà un chiffre
        self.assertFalse(f(key(QEvent.Type.ShortcutOverride, Qt.Key.Key_Egrave, 0x37, 'è',
                               Qt.KeyboardModifier.NoModifier)))                             # sans Ctrl : la lettre
        self.assertFalse(f(key(QEvent.Type.ShortcutOverride, Qt.Key.Key_A, 0x41, 'a')))      # hors de la rangée
        self.assertFalse(f(key(QEvent.Type.ShortcutOverride, Qt.Key.Key_Egrave, 0x37, 'è',
                               CTRL | Qt.KeyboardModifier.AltModifier)))                     # AltGr : un caractère
        self.assertFalse(f(key(QEvent.Type.KeyPress, Qt.Key.Key_Egrave, 0x37, 'è')))         # rien en attente
        w.A['direction'].setEnabled(False)
        self.assertFalse(f(key(QEvent.Type.ShortcutOverride, Qt.Key.Key_Egrave, 0x37, 'è')))  # commande inactive


if __name__ == '__main__':
    unittest.main()
