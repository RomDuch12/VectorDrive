"""Round 695 : thème par défaut Crépuscule — poste sans thème choisi :
lancement, options, menu Thème, réglages relus ; un choix gardé l'emporte."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QMenu

from vectordrive.ui import theme as TH
from vectordrive.ui import themes as T

app = QApplication.instance() or QApplication([])
ROOT = pathlib.Path(__file__).resolve().parent.parent


def fresh() -> QSettings:
    return QSettings(os.path.join(tempfile.mkdtemp(), 'p.ini'), QSettings.Format.IniFormat)


class TestDefault(unittest.TestCase):
    def test_key(self):
        from vectordrive.ui.options import value
        self.assertEqual(T.DEFAULT_KEY, 'crepuscule')
        self.assertIn('crepuscule', T.BUILTIN)
        self.assertTrue(T.BUILTIN['crepuscule'].dark)
        s = fresh()
        self.assertEqual(T.chosen_key(s), 'crepuscule')
        self.assertEqual(value(s, 'vue/theme'), 'crepuscule')
        s.setValue('vue/theme', 'clair')                               # un choix : gardé
        self.assertEqual(T.chosen_key(s), 'clair')

    def test_apply(self):
        s = fresh()
        before = TH.current()
        try:
            self.assertTrue(TH.apply_theme(app, str(s.value('vue/theme', T.DEFAULT_KEY)), s))
            self.assertEqual(TH.current().key, 'crepuscule')
        finally:
            TH.apply(app, before)

    @unittest.skipUnless((ROOT / 'VectorDrive.py').exists(), 'lanceur absent')
    def test_launcher(self):
        src = (ROOT / 'VectorDrive.py').read_text(encoding='utf-8')
        self.assertIn("apply_theme(app, str(st.value('vue/theme', DEFAULT_KEY) or DEFAULT_KEY), st)", src)


class TestWindow(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.saved = self.w.settings.value('vue/theme')
        self.w.settings.remove('vue/theme')

    def tearDown(self):
        if self.saved is not None:
            self.w.settings.setValue('vue/theme', self.saved)
        self.w.modified = False
        self.w.close()

    def test_menu(self):
        m = QMenu()
        self.w._fill_theme_menu(m)
        checked = [a.data() for a in m.actions() if a.isCheckable() and a.isChecked()]
        self.assertEqual(checked, ['crepuscule'])
        m.deleteLater()

    def test_editor(self):
        from vectordrive.ui.theme_editor import ThemeEditor
        dlg = ThemeEditor(self.w)
        self.assertEqual(dlg.list.currentItem().data(Qt.ItemDataRole.UserRole), 'crepuscule')
        dlg.deleteLater()


if __name__ == '__main__':
    unittest.main()
