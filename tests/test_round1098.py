"""Round 1098 (demande du 19/11, 16 h 37 : « F10 Fenetre de gestion complete de tous les raccourcis possibles ») :
l'onglet Raccourcis des options ; la fenêtre des raccourcis : place dans le ruban, vues, touche cherchée, autres
touches, rétablir une commande, copier, exporter, importer ; les touches fixes du plan de travail."""
import json
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1098.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class Win(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.show()
        app.processEvents()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def dialog(self):
        dlg = self.w.shortcuts_dialog(exec_dialog=False)
        self.addCleanup(dlg.deleteLater)
        return dlg

    def row(self, dlg, key):
        return next(r for r in range(dlg.table.rowCount())
                    if dlg.table.item(r, 0).data(Qt.ItemDataRole.UserRole) == key)


class Window(Win):

    def test_places_in_the_ribbon(self):
        places = self.w.action_places()
        self.assertTrue(places['tool_node'].endswith('› Mode Point'))
        dlg = self.dialog()
        self.assertEqual(dlg.table.columnCount(), 4)
        self.assertEqual(dlg.table.item(self.row(dlg, 'tool_node'), 3).text(), places['tool_node'])

    def test_views(self):
        dlg = self.dialog()
        n_all = dlg._filter()
        dlg.view.setCurrentIndex(dlg.view.findData('none'))
        none = dlg._filter()
        dlg.view.setCurrentIndex(dlg.view.findData('set'))
        some = dlg._filter()
        self.assertEqual(none + some, n_all)
        self.assertTrue(dlg.table.isRowHidden(self.row(dlg, 'tool_node')) is False)     # P
        dlg.view.setCurrentIndex(dlg.view.findData('mine'))
        self.assertEqual(dlg._filter(), 0)
        dlg.custom['zoom_fit'] = ['F9']
        dlg.refresh()
        self.assertEqual(dlg._filter(), 1)

    def test_who_uses_a_key(self):
        dlg = self.dialog()
        seq = dlg.mapping()['tool_node'][0]
        dlg.find_key.setKeySequence(QKeySequence(seq))
        shown = [dlg.table.item(r, 0).data(Qt.ItemDataRole.UserRole) for r in range(dlg.table.rowCount())
                 if not dlg.table.isRowHidden(r)]
        self.assertIn('tool_node', shown)
        self.assertTrue(all(seq in dlg.mapping()[k] for k in shown))

    def test_other_key_reset_row_and_clash(self):
        dlg = self.dialog()
        dlg.select_key('zoom_fit')
        dlg.edit.setKeySequence(QKeySequence('Ctrl+Alt+F9'))
        dlg.add_other()
        self.assertEqual(dlg.mapping()['zoom_fit'][-1], 'Ctrl+Alt+F9')
        first = dlg.mapping()['zoom_fit'][:-1]
        dlg.select_key('undo')
        dlg.add_other()                                           # la même touche : retirée de Tout voir
        self.assertNotIn('Ctrl+Alt+F9', dlg.mapping()['zoom_fit'])
        self.assertIn('Ctrl+Alt+F9', dlg.mapping()['undo'])
        self.assertIn('Tout voir', dlg.info.text())
        dlg.reset_row()
        self.assertNotIn('undo', dlg.custom)
        dlg.select_key('zoom_fit')
        dlg.reset_row()
        self.assertEqual(dlg.custom, {})
        self.assertEqual(dlg.mapping()['zoom_fit'], first)                # les touches du jeu

    def test_copy_export_import(self):
        dlg = self.dialog()
        dlg.filter.setText('Tout voir')
        text = dlg.copy_list()
        self.assertTrue(text.startswith('Commande\tRaccourci\tAutres touches\tOù (ruban)\n'))
        self.assertIn('Tout voir', text)
        self.assertEqual(QApplication.clipboard().text(), text)
        dlg.custom = {'zoom_fit': ['F9']}
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'r.json')
            self.assertTrue(dlg.export_file(f))
            data = json.loads(open(f, encoding='utf-8').read())
            self.assertEqual(data['reglages'], {'zoom_fit': ['F9']})
            other = self.dialog()
            self.assertTrue(other.import_mine(f))
            self.assertEqual(other.custom, {'zoom_fit': ['F9']})
            self.assertEqual(other.mapping()['zoom_fit'][0], 'F9')
            bad = os.path.join(tmp, 'b.json')
            open(bad, 'w', encoding='utf-8').write('[1, 2]')
            from unittest import mock
            with mock.patch('PySide6.QtWidgets.QMessageBox.warning') as warn:
                self.assertFalse(other.import_mine(bad))
                self.assertTrue(warn.called)

    def test_fixed_keys_tab(self):
        from vectordrive.ui.shortcuts import FIXED_KEYS
        dlg = self.dialog()
        self.assertEqual(dlg.pages.count(), 2)
        self.assertEqual(dlg.fixed.rowCount(), len(FIXED_KEYS))
        self.assertIn('Mode Point', [dlg.fixed.item(r, 0).text() for r in range(dlg.fixed.rowCount())])


class Review(Win):
    """Relecture : touche reprise, OK des options, Entrée, onglets masqués, import partiel, touches fixes."""

    def test_moved_key_leaves_the_other_command_alone(self):
        dlg = self.dialog()
        m = dlg.mapping()
        owner = next(k for k, v in m.items() if v and k != 'zoom_fit')
        seq = m[owner][0]
        dlg.select_key('zoom_fit')
        dlg.edit.setKeySequence(QKeySequence(seq))
        dlg.assign()
        self.assertEqual(list(dlg.custom), ['zoom_fit'])                  # l'autre commande pas dans mes réglages
        self.assertNotIn(seq, dlg.mapping()[owner])
        dlg.reset_row()
        self.assertIn(seq, dlg.mapping()[owner])                          # rétablir : elle retrouve sa touche

    def test_newest_setting_wins(self):
        dlg = self.dialog()
        dlg.custom = {'undo': ['Ctrl+Alt+F7'], 'zoom_fit': ['F9']}
        dlg.select_key('undo')
        dlg.edit.setKeySequence(QKeySequence('F9'))
        dlg.assign()
        self.assertEqual(dlg.mapping()['undo'][0], 'F9')
        self.assertNotIn('F9', dlg.mapping()['zoom_fit'])

    def test_options_ok_untouched_saves_nothing(self):
        from unittest import mock
        from vectordrive.ui import shortcuts as SC
        dlg = self.w.options_dialog(exec_dialog=False, page='Raccourcis')
        self.addCleanup(dlg.deleteLater)
        with mock.patch.object(SC, 'save') as save:
            dlg.accept()
        self.assertFalse(save.called)

    def test_enter_in_the_page_stays(self):
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent
        dlg = self.w.options_dialog(exec_dialog=False, page='Raccourcis')
        self.addCleanup(dlg.deleteLater)
        ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        ev.ignore()
        dlg.shortcuts_editor.keyPressEvent(ev)
        self.assertTrue(ev.isAccepted())                                  # pas remontée à la fenêtre des options

    def test_hidden_tabs_have_a_place(self):
        r = self.w.ribbon
        places = self.w.action_places()
        hidden = [r.tabText(i) for i in range(r.count()) if not r.isTabVisible(i) and not r.widget(i).property('te_context')]
        if not hidden:
            self.skipTest('aucun onglet masqué')
        self.assertTrue(any('(onglet masqué)' in v for v in places.values()))

    def test_partial_import(self):
        from unittest import mock
        dlg = self.dialog()
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, 'p.json')
            open(f, 'w', encoding='utf-8').write(json.dumps({
                'format': 'vectordrive-raccourcis', 'reglages': {'zoom_fit': 'F9', 'module_absent': ['F7'],
                                                                 'undo': [None, 'Ctrl+Alt+U']}}))
            self.assertTrue(dlg.import_mine(f))
            self.assertEqual(dlg.custom, {'module_absent': ['F7'], 'undo': ['Ctrl+Alt+U']})
            self.assertIn('2 entrée(s) illisible(s)', dlg.info.text())
            bad = os.path.join(tmp, 'b.json')
            open(bad, 'w', encoding='utf-8').write(json.dumps({'format': 'vectordrive-raccourcis',
                                                               'reglages': {'zoom_fit': 'F9'}}))
            with mock.patch('PySide6.QtWidgets.QMessageBox.warning') as warn:
                self.assertFalse(dlg.import_mine(bad))
                self.assertTrue(warn.called)
            self.assertEqual(dlg.custom, {'module_absent': ['F7'], 'undo': ['Ctrl+Alt+U']})   # rien de perdu

    def test_fixed_key_warned(self):
        dlg = self.dialog()
        dlg.select_key('zoom_fit')
        dlg.edit.setKeySequence(QKeySequence('Left'))
        dlg.assign()
        self.assertIn('plan de travail', dlg.info.text())

    def test_search_keeps_the_tab(self):
        dlg = self.w.options_dialog(exec_dialog=False, page='Raccourcis')
        self.addCleanup(dlg.deleteLater)
        i = dlg.tabs.currentIndex()
        dlg.filter_options('zzzz introuvable')
        self.assertEqual(dlg.tabs.currentIndex(), i)
        self.assertTrue(dlg.tabs.isTabEnabled(i))


class OptionsTab(Win):

    def test_tab_in_f10_saved_on_ok(self):
        from vectordrive.ui import shortcuts as SC
        from vectordrive.ui.options import PAGES
        self.assertIn('Raccourcis', PAGES)
        self.assertIn('options_raccourcis', self.w.A)
        dlg = self.w.options_dialog(exec_dialog=False, page='Raccourcis')
        self.addCleanup(dlg.deleteLater)
        ed = dlg.shortcuts_editor
        self.assertTrue(ed.embedded)
        self.assertFalse(ed.bb.isVisible())
        self.assertEqual(dlg.tabs.tabText(dlg.tabs.currentIndex()), 'Raccourcis')
        ed.reject()                                               # Échap dans la page : pas refermée seule
        ed.accept()
        self.assertFalse(ed.isHidden())
        ed.select_key('zoom_fit')
        ed.edit.setKeySequence(QKeySequence('Ctrl+Alt+F8'))
        ed.assign()
        dlg.accept()
        _scheme, _te, custom = SC.load(self.w.settings)
        self.assertEqual(custom.get('zoom_fit', [None])[0], 'Ctrl+Alt+F8')
        self.assertIn(QKeySequence('Ctrl+Alt+F8'), self.w.A['zoom_fit'].shortcuts())
        for k in ('raccourcis/jeu', 'raccourcis/typeedit', 'raccourcis/perso'):
            self.w.settings.remove(k)                             # rien de laissé aux essais d'après (même processus)
        self.w._apply_shortcuts()


if __name__ == '__main__':
    unittest.main()
