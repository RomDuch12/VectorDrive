"""Round 1142 : clic droit sur un outil à réglages du ruban (étoile, Cote) : le menu du bouton, ses réglages en tête
(action par défaut) ; les déclencher ouvre la fenêtre de réglages de l'outil. Essais 247 et 248 adaptés."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_KEYS_MEMORY', '1')

from PySide6.QtCore import QPoint
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtWidgets import QApplication, QDialog, QToolButton

app = QApplication.instance() or QApplication([])


class RightClick(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        self.w.canvas.doc.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def _button(self, key):
        return next((b for b in self.w.ribbon.findChildren(QToolButton)
                     if b.defaultAction() is self.w.A.get(key)), None)

    def _right_click(self, btn):
        menus = []
        real = type(self.w)._ribbon_button_menu

        def no_wait(w, *a, **k):                                         # le vrai menu, sans l'attendre
            k['exec_menu'] = False
            menus.append(real(w, *a, **k))
            return menus[-1]
        with mock.patch.object(type(self.w), '_ribbon_button_menu', autospec=True, side_effect=no_wait):
            QApplication.sendEvent(btn, QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(2, 2),
                                                          btn.mapToGlobal(QPoint(2, 2))))
        self.assertEqual(len(menus), 1)
        return menus[0]

    def test_star_settings_first(self):
        from vectordrive.ui import form_dialog as FD
        btn = self._button('tool_star')
        self.assertIsNotNone(btn)
        m = self._right_click(btn)
        first = next(a for a in m.actions() if not a.isSeparator())
        self.assertIs(m.defaultAction(), first)                          # réglages en tête, en gras
        seen = []
        self.addCleanup(self.w.settings.remove, 'formes')

        def fake_dialog(d):
            seen.append(d.windowTitle())
            d.set_field('branches', 9)
            return QDialog.DialogCode.Accepted
        with mock.patch.object(FD.FormDialog, 'exec', fake_dialog):
            first.trigger()
        self.assertEqual(len(seen), 1)
        self.assertEqual(FD.defaults(self.w.settings, 'star').branches, 9)

    def test_dim_settings_first(self):
        from vectordrive.ui import dim_dialog as DD
        btn = self._button('tool_dim')
        if btn is None:
            self.skipTest('Cote absente du ruban')
        m = self._right_click(btn)
        self.assertIsNotNone(m.defaultAction())
        with mock.patch.object(DD.DimDialog, 'exec', return_value=QDialog.DialogCode.Rejected) as ex:
            m.defaultAction().trigger()
        ex.assert_called_once()
        texts = [a.text().replace('&', '') for a in m.actions()]
        self.assertTrue(any('Position du bouton' in t for t in texts), texts)   # puis taille et place du bouton


if __name__ == '__main__':
    unittest.main()
