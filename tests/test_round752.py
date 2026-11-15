"""Round 752 : rouvrir un onglet fermé (clic droit sur la barre d'onglets, les 25 derniers, Ctrl+Maj+T) ;
Ctrl+Maj+chiffre (le chiffre lui-même sur un clavier AZERTY) fait comme Ctrl+& … Ctrl+à."""
import os
import pathlib
import sys
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QMenu

from vectordrive.core import geom
from vectordrive.core.document import Shape
from vectordrive.io import registry

app = QApplication.instance() or QApplication([])
CTRL = Qt.KeyboardModifier.ControlModifier
SHIFT = Qt.KeyboardModifier.ShiftModifier


KEEP = []                                                                     # le menu reste en vie le temps de le lire


def titles(menu):
    KEEP[:] = [menu]
    sub = next(x for x in menu.findChildren(QMenu) if x.title() == 'Rouvrir un onglet fermé')
    return sub, [a.text() for a in sub.actions()]


class TestReopen(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.settings.remove('fichiers/onglets_fermes')
        self.dir = pathlib.Path(tempfile.mkdtemp())

    def tearDown(self):
        for t in self.w.docs:
            t.modified = False
        self.w.modified = False
        self.w.settings.remove('fichiers/onglets_fermes')
        self.w.close()

    def drawing(self, name):
        from vectordrive.core.document import Document, Layer
        d = Document()
        d.layers = [Layer(name='A', items=[Shape(path=geom.Path([geom.rect(0, 0, 5, 5)]))])]
        p = self.dir / name
        registry.save_document(d, p)
        return str(p)

    def test_close_then_reopen(self):
        w = self.w
        a, b = self.drawing('a.svg'), self.drawing('b.svg')
        self.assertTrue(w.open_path(a))
        self.assertTrue(w.open_path(b))
        w.close_tab(w.tab_of(a))
        w.close_tab(w.tab_of(b))
        self.assertEqual([pathlib.Path(p).name for p in w.closed_tabs()], ['b.svg', 'a.svg'])
        sub, names = titles(w.doc_tab_menu(-1, exec_menu=False))
        self.assertTrue(sub.isEnabled())
        self.assertEqual(names, ['b.svg', 'a.svg'])
        self.assertEqual(sub.actions()[0].toolTip(), str(pathlib.Path(b)))
        self.assertTrue(w.reopen_tab())                                       # le dernier fermé
        self.assertGreaterEqual(w.tab_of(b), 0)
        self.assertEqual([pathlib.Path(p).name for p in w.closed_tabs()], ['a.svg'])
        w.A['reopen_tab'].trigger()                                           # Ctrl+Maj+T
        self.assertGreaterEqual(w.tab_of(a), 0)
        self.assertEqual(w.closed_tabs(), [])
        self.assertFalse(w.reopen_tab())                                      # plus rien : un message, pas d'erreur

    def test_menu_empty(self):
        sub, names = titles(self.w.doc_tab_menu(-1, exec_menu=False))
        self.assertFalse(sub.isEnabled())
        self.assertEqual(names, [])

    def test_keeps_25(self):
        w = self.w
        paths = [str(self.dir / f'f{k}.svg') for k in range(30)]
        w.settings.setValue('fichiers/onglets_fermes', paths[:25])
        p = self.drawing('nouveau.svg')
        w.open_path(p)
        w.close_tab(w.tab_of(p))
        got = w.closed_tabs()
        self.assertEqual(len(got), 25)
        self.assertEqual(pathlib.Path(got[0]).name, 'nouveau.svg')
        self.assertEqual(pathlib.Path(got[-1]).name, 'f23.svg')

    def test_missing_file(self):
        w = self.w
        p = self.drawing('parti.svg')
        w.open_path(p)
        w.close_tab(w.tab_of(p))
        os.remove(p)
        _sub, names = titles(w.doc_tab_menu(-1, exec_menu=False))
        self.assertIn('introuvable', names[0])
        self.assertFalse(w.reopen_tab())
        self.assertEqual(w.closed_tabs(), [])                                 # retiré de la liste

    def test_open_again_leaves_list(self):
        w = self.w
        p = self.drawing('x.svg')
        w.open_path(p)
        w.close_tab(w.tab_of(p))
        w.open_path(p)                                                        # rouvert à la main
        self.assertEqual(w.closed_tabs(), [])

    def test_unsaved_drawing(self):
        w = self.w
        keep = self.drawing('garde.svg')
        w.open_path(keep)
        w.new_document()
        w._add_items([Shape(path=geom.Path([geom.rect(0, 0, 3, 3)]))])
        n = len(w.docs)
        self.assertTrue(w.close_tab(answer='discard'))
        self.assertEqual(len(w.docs), n - 1)
        items = w.closed_tabs()
        self.assertEqual(len(items), 1)
        self.assertNotIsInstance(items[0], str)
        self.assertEqual(items[0].undo, [])
        self.assertTrue(w.reopen_tab())
        self.assertEqual(len(w.docs), n)
        self.assertEqual(len(list(w.canvas.doc.iter_items())), 1)
        self.assertEqual(w.closed_tabs(), [])
        for t in w.docs:
            t.modified = False
        w.modified = False

    def test_pristine_not_kept(self):
        w = self.w
        w.new_document()
        w.close_tab()
        self.assertEqual(w.closed_tabs(), [])

    def test_order_mixes_files_and_unsaved(self):
        w = self.w
        p = self.drawing('un.svg')
        w.open_path(p)
        w.new_document()
        w._add_items([Shape(path=geom.Path([geom.rect(0, 0, 3, 3)]))])
        w.close_tab(answer='discard')
        w.close_tab(w.tab_of(p))
        got = w.closed_tabs()
        self.assertEqual(got[0], str(pathlib.Path(p)))                        # fermé en dernier
        self.assertNotIsInstance(got[1], str)

    def test_not_exported_settings(self):
        self.assertIn('fichiers/onglets_fermes', self.w.LOCAL_KEYS)


@unittest.skipUnless(sys.platform == 'win32', 'touches virtuelles de Windows')
class TestShiftDigits(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        # les touches envoyées ne restent pas pour les essais suivants
        from PySide6.QtTest import QTest
        QTest.keyRelease(self.w.canvas, Qt.Key.Key_Shift)
        self.w.modified = False
        self.w.close()

    def press(self, k, vk, text, mods):
        over = QApplication.sendEvent(self.w.canvas, QKeyEvent(QEvent.Type.ShortcutOverride, k, mods, 0, vk, 0, text))
        down = QApplication.sendEvent(self.w.canvas, QKeyEvent(QEvent.Type.KeyPress, k, mods, 0, vk, 0, text))
        app.processEvents()
        return over, down

    def test_shift_digit_same_as_row(self):
        w = self.w
        before = w.A['direction'].isChecked()
        self.assertEqual(self.press(Qt.Key.Key_7, 0x37, '7', CTRL | SHIFT), (True, True))     # AZERTY : Ctrl+Maj+è
        self.assertNotEqual(w.A['direction'].isChecked(), before)
        colors = w.A['tool_colors'].isChecked()
        self.press(Qt.Key.Key_8, 0x38, '8', CTRL | SHIFT)
        self.assertNotEqual(w.A['tool_colors'].isChecked(), colors)

    def test_azerty_row_still_works(self):
        w = self.w
        before = w.A['direction'].isChecked()
        self.press(Qt.Key.Key_Egrave, 0x37, 'è', CTRL)
        self.assertNotEqual(w.A['direction'].isChecked(), before)

    def test_shift_on_qwerty(self):
        w = self.w
        before = w.A['direction'].isChecked()
        self.press(Qt.Key.Key_Ampersand, 0x37, '&', CTRL | SHIFT)                             # QWERTY : Maj+7 = &
        self.assertNotEqual(w.A['direction'].isChecked(), before)

    def test_own_shift_binding_wins(self):
        from PySide6.QtGui import QKeySequence
        w = self.w
        fired = []
        w.A['zoom_fit'].setShortcuts([QKeySequence('Ctrl+Shift+7')])
        w.A['zoom_fit'].triggered.connect(lambda *_a: fired.append(1))
        before = w.A['direction'].isChecked()
        self.press(Qt.Key.Key_7, 0x37, '7', CTRL | SHIFT)
        self.assertEqual(fired, [1])
        self.assertEqual(w.A['direction'].isChecked(), before)

    def test_plain_digit_left_to_qt(self):
        ev = QKeyEvent(QEvent.Type.ShortcutOverride, Qt.Key.Key_7, CTRL, 0, 0x37, 0, '7')
        self.assertFalse(self.w._digit_row(ev))


if __name__ == '__main__':
    unittest.main()
