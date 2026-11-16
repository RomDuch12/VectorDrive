"""Round 1052 : réponse du 16/11 à la question 10 — « liste simple-expert réglable dans F10 » : Options › Général ›
« Commandes du mode simple… » ouvre la liste des commandes du ruban, onglet par onglet, une case chacune."""
import importlib.util
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1052.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vectordrive.ui import modes  # noqa: E402

app = QApplication.instance() or QApplication([])
ON, OFF = Qt.CheckState.Checked, Qt.CheckState.Unchecked


class SimpleModeList(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.addCleanup(self.clean)
        self.assertIsNotNone(importlib.util.find_spec('vectordrive.ui.modes_dialog'),
                             'avant : la répartition simple / expert ne se règle qu’au clic droit, bouton par bouton')

    def clean(self):
        for k in (modes.PLUS, modes.MINUS, modes.KEY):
            self.w.settings.remove(k)
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()

    def dialog(self):
        dlg = self.w.simple_mode_dialog(exec_dialog=False)
        self.addCleanup(dlg.deleteLater)
        return dlg

    def test_every_ribbon_command_with_its_state(self):
        dlg = self.dialog()
        tabs = [dlg.tree.topLevelItem(i).text(0) for i in range(dlg.tree.topLevelItemCount())]
        self.assertGreaterEqual(len(tabs), 4)
        st = dlg.states()
        self.assertGreater(len(st), 100)                                     # le ruban entier
        plugin = self.w._plugin_action_keys()
        for key, on in st.items():
            self.assertEqual(on, modes.in_simple(key, self.w.settings, plugin), key)
        self.assertTrue(st['tool_rect'])
        self.assertIn(str(sum(st.values())), dlg.count.text())

    def test_unchecked_goes_to_expert_checked_comes_to_simple(self):
        dlg = self.dialog()
        st = dlg.states()
        extra = next(k for k, on in sorted(st.items()) if not on)           # une commande du mode expert seulement
        dlg.set_checked('tool_rect', False)
        dlg.set_checked(extra, True)
        dlg.accept()
        plugin = self.w._plugin_action_keys()
        self.assertFalse(modes.in_simple('tool_rect', self.w.settings, plugin))
        self.assertTrue(modes.in_simple(extra, self.w.settings, plugin))
        self.w.set_ui_mode('simple', announce=False)
        allowed = self.w._mode_filter()
        self.assertFalse(allowed(self.w.A['tool_rect']))                    # le ruban suit
        self.assertTrue(allowed(self.w.A[extra]))
        again = self.dialog()                                                # rouverte : les mêmes cases
        self.assertFalse(again.states()['tool_rect'])
        self.assertTrue(again.states()[extra])

    def test_cancel_changes_nothing(self):
        dlg = self.dialog()
        dlg.set_checked('tool_rect', False)
        dlg.reject()
        self.assertTrue(modes.in_simple('tool_rect', self.w.settings, self.w._plugin_action_keys()))

    def test_a_tab_ticked_during_a_search_leaves_the_hidden_rows(self):
        dlg = self.dialog()
        before = dlg.states()
        self.assertGreater(dlg.filter('rectangle'), 0)
        shown = {it.data(0, Qt.ItemDataRole.UserRole) for it in dlg.rows() if not it.isHidden()}
        for i in range(dlg.tree.topLevelItemCount()):
            top = dlg.tree.topLevelItem(i)
            if not top.isHidden():
                top.setCheckState(0, OFF)                                    # la case de l'onglet, recherche en cours
        after = dlg.states()
        self.assertTrue(shown and not any(after[k] for k in shown))
        for key, on in before.items():
            if key not in shown:
                self.assertEqual(after[key], on, key)                        # les lignes cachées : pas touchées

    def test_default_split_comes_back(self):
        modes.move(self.w.settings, 'tool_rect', False)
        self.w.settings.setValue(modes.PLUS, ['commande_d_un_plugin_absent'])   # un écart sans bouton en ce moment
        dlg = self.dialog()
        self.assertFalse(dlg.states()['tool_rect'])
        dlg.restore_defaults()
        plugin = self.w._plugin_action_keys()
        for key, on in dlg.states().items():
            self.assertEqual(on, modes.default_simple(key, plugin), key)
        self.assertFalse(modes.in_simple('tool_rect', self.w.settings, plugin))     # rien d'écrit avant OK
        dlg.accept()
        self.assertTrue(modes.in_simple('tool_rect', self.w.settings, plugin))
        self.assertEqual(modes._keys(self.w.settings, modes.PLUS) | modes._keys(self.w.settings, modes.MINUS), set())

    def test_tabs_named_apart_and_in_ribbon_order(self):
        dlg = self.dialog()
        tabs = [dlg.tree.topLevelItem(i).text(0) for i in range(dlg.tree.topLevelItemCount())]
        self.assertEqual(len(tabs), len(set(tabs)), tabs)                    # « CAD (2D) », « CAD (3D) » : distingués
        self.assertTrue(any(t.endswith('(2D)') for t in tabs) and any(t.endswith('(3D)') for t in tabs), tabs)

    def test_a_whole_tab_at_once_and_the_same_command_elsewhere(self):
        dlg = self.dialog()
        top = dlg.tree.topLevelItem(0)
        keys = [top.child(i).data(0, Qt.ItemDataRole.UserRole) for i in range(top.childCount())]
        top.setCheckState(0, OFF)                                            # tout l'onglet d'un coup
        st = dlg.states()
        self.assertTrue(keys and not any(st[k] for k in keys))
        rows = {}
        for it in dlg.rows():
            rows.setdefault(it.data(0, Qt.ItemDataRole.UserRole), []).append(it)
        for key, its in rows.items():                                        # la même commande dans deux onglets :
            self.assertEqual(len({it.checkState(0) for it in its}), 1, key)  # la même case

    def test_search(self):
        dlg = self.dialog()
        total = len(dlg.rows())
        n = dlg.filter('rectangle')
        self.assertTrue(0 < n < total)
        shown = [it.text(0) for it in dlg.rows() if not it.isHidden()]
        self.assertEqual(len(shown), n)
        self.assertEqual(dlg.filter(''), total)

    def test_opened_from_the_options(self):
        from vectordrive.ui.options import OptionsDialog
        dlg = OptionsDialog(self.w.settings, self.w)
        self.addCleanup(dlg.deleteLater)
        b = getattr(dlg, 'simple_mode_button', None)
        self.assertIsNotNone(b)
        self.assertEqual(b.text(), 'Commandes du mode simple…')
        seen = []
        self.w.simple_mode_dialog = lambda *a, **k: seen.append(1)
        b.click()
        self.assertEqual(seen, [1])


if __name__ == '__main__':
    unittest.main()
