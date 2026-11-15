"""Round 696 : onglets de ruban à soi — plusieurs, nommés, placés (en premier,
en dernier, après un onglet), libellés de boutons choisis, exportés et
importés ; clic droit sur le ruban : ajouter une commande à un onglet à soi,
la retirer, renommer ou supprimer l'onglet."""
import json
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QPoint, QSettings
from PySide6.QtGui import QAction, QContextMenuEvent
from PySide6.QtWidgets import QApplication, QMessageBox, QToolButton

from vectordrive.ui import ribbon_editor as RE

app = QApplication.instance() or QApplication([])


def fresh() -> QSettings:
    return QSettings(os.path.join(tempfile.mkdtemp(), 'p.ini'), QSettings.Format.IniFormat)


def tab(title, pos='debut', *keys, **labels):
    return {'titre': title, 'position': pos,
            'groupes': [{'titre': 'G', 'commandes': [dict({'key': k, 'big': True},
                                                         **({'texte': labels[k]} if k in labels else {}))
                                                    for k in keys]}]}


class TestSettings(unittest.TestCase):
    def test_load_save_all(self):
        s = fresh()
        self.assertEqual([t['titre'] for t in RE.load_all(s)], ['Mon onglet'])
        RE.save_all(s, [tab('A', 'debut', 'open'), tab('B', 'fin', 'save'), tab('C', 'apres:Dessin', 'new')])
        self.assertEqual([t['titre'] for t in RE.load_all(s)], ['A', 'B', 'C'])
        self.assertEqual(RE.load(s)['titre'], 'A')                     # le premier : réglage d'avant
        self.assertEqual(RE.load_all(s)[2]['position'], 'apres:Dessin')
        RE.save_all(s, [tab('A')])
        self.assertIsNone(s.value(RE.MORE))
        RE.save_all(s, [])
        self.assertEqual(RE.load_all(s)[0]['titre'], 'Mon onglet')

    def test_garbage(self):
        s = fresh()
        s.setValue(RE.MORE, 'pas du json')
        self.assertEqual(len(RE.load_all(s)), 1)
        s.setValue(RE.MORE, json.dumps([{'titre': 'X', 'position': 'apres:', 'groupes': [
            {'titre': 'G', 'commandes': [{'key': 'open', 'texte': '  '}, {'key': 'save', 'texte': 'Garder'}]}]},
            'x', 3]))
        tabs = RE.load_all(s)
        self.assertEqual(len(tabs), 2)
        self.assertEqual(tabs[1]['position'], 'debut')                 # « après » sans onglet : en premier
        self.assertEqual(tabs[1]['groupes'][0]['commandes'], [{'key': 'open'}, {'key': 'save', 'texte': 'Garder'}])

    def test_free_title(self):
        self.assertEqual(RE.free_title('Aide', {'Aide', 'Aide (2)'}), 'Aide (3)')
        self.assertEqual(RE.free_title('Atelier', {'Aide'}), 'Atelier')


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.resize(1600, 900)

    @classmethod
    def tearDownClass(cls):
        cls.clear()
        cls.w.modified = False
        cls.w.close()

    @classmethod
    def clear(cls):
        for k in (RE.KEY, RE.MORE, RE.HIDDEN):
            cls.w.settings.remove(k)
        cls.w._build_custom_tab()

    def setUp(self):
        self.clear()

    def builtin(self) -> list:
        r = self.w.ribbon
        return [r.tabText(i) for i in range(r.count()) if r.isTabVisible(i)
                and not r.widget(i).property('ribbon_custom') and r.tabText(i) != self.w.text_tab_title]

    def titles(self) -> list:
        r = self.w.ribbon
        return [r.tabText(i) for i in range(r.count())]

    def buttons(self, title) -> list:
        r = self.w.ribbon
        i = self.titles().index(title)
        return [b for b in r.widget(i).findChildren(QToolButton) if b.defaultAction() is not None]


class TestWindow(Base):
    def test_several_tabs_placed(self):
        w, r = self.w, self.w.ribbon
        b = self.builtin()
        anchor = b[2]
        RE.save_all(w.settings, [tab('Atelier', 'debut', 'open'), tab('Gravure', 'apres:' + anchor, 'save'),
                                 tab('Vide', 'fin'), tab('Fin', 'fin', 'new'), tab('Deux', 'debut', 'proof')])
        w._build_custom_tab()
        t = self.titles()
        self.assertEqual(t[:2], ['Atelier', 'Deux'])                    # en premier, dans l'ordre
        self.assertEqual(t[t.index(anchor) + 1], 'Gravure')
        self.assertNotIn('Vide', t)                                     # onglet sans commande : pas affiché
        self.assertIn('Fin', t)
        self.assertEqual(r.custom_title, 'Atelier')
        self.assertEqual(r.custom_titles, ['Atelier', 'Gravure', 'Fin', 'Deux'])
        self.assertEqual(r.custom_rank, [0, 1, 3, 4])
        self.assertTrue(all(r.isTabVisible(r.indexOf(p)) for p in r.custom_pages))
        n = r.count()
        w._build_custom_tab()                                           # refait sans doublon
        self.assertEqual(r.count(), n)
        menus = [title for title, _g in w._vd_tab_menus()]
        self.assertFalse(set(menus) & set(r.custom_titles))            # disposition TypeEdit 13 : pas reprise

    def test_unknown_anchor_and_builtin_title(self):
        w = self.w
        b = self.builtin()
        RE.save_all(w.settings, [tab(b[1], 'apres:Onglet absent', 'open')])
        w._build_custom_tab()
        t = self.titles()
        self.assertIn(b[1] + ' (2)', t)                                 # jamais le titre d'un autre onglet
        self.assertEqual(t.count(b[1]), 1)

    def test_label(self):
        w, r = self.w, self.w.ribbon
        src = QAction('Essai', w)
        src.setCheckable(True)
        hits = []
        src.triggered.connect(lambda on: hits.append(on))
        w.A['essai696'] = src
        try:
            RE.save_all(w.settings, [tab('Atelier', 'debut', 'essai696', 'open', essai696='Mon libellé')])
            w._build_custom_tab()
            btn = next(b for b in self.buttons('Atelier') if b.defaultAction().text() == 'Mon libellé')
            relay = btn.defaultAction()
            self.assertIsInstance(relay, RE.RelayAction)
            self.assertIs(relay.src, src)
            self.assertIn(relay, w._custom_relays)
            relay.trigger()                                             # la commande d'origine
            self.assertEqual(hits, [True])
            self.assertTrue(src.isChecked() and relay.isChecked())
            src.setChecked(False)                                       # état suivi
            self.assertFalse(relay.isChecked())
            src.setEnabled(False)
            self.assertFalse(relay.isEnabled())
            src.setEnabled(True)
            self.assertEqual(w._action_key(relay), 'essai696')
            RE.save_all(w.settings, [tab('Atelier', 'debut', 'essai696')])
            w._build_custom_tab()                                       # libellé retiré : l'action même
            self.assertEqual(w._custom_relays, [])
            self.assertIs(self.buttons('Atelier')[0].defaultAction(), src)
            src.setEnabled(False)                                       # ancien relais détaché : pas d'erreur
            src.setEnabled(True)
        finally:
            del w.A['essai696']

    def test_menu_command_and_same_groups(self):
        w = self.w
        key = next(k for k, a in w.A.items() if a.menu() is not None)
        two = {'titre': 'G', 'commandes': [{'key': 'open', 'big': True}]}
        RE.save_all(w.settings, [{'titre': 'Atelier', 'position': 'debut', 'groupes': [
            two, dict(two), {'titre': 'M', 'commandes': [{'key': key, 'big': True, 'texte': 'Mon menu'}]}]}])
        w._build_custom_tab()
        bs = self.buttons('Atelier')
        self.assertEqual([b.property('ribbon_custom_at') for b in bs], ['0:0:0', '0:1:0', '0:2:0'])
        relay = bs[2].defaultAction()
        self.assertIs(relay.menu(), w.A[key].menu())                    # menu de la commande d'origine
        self.assertEqual(bs[2].popupMode(), QToolButton.ToolButtonPopupMode.InstantPopup)
        self.assertTrue(w.remove_from_custom_tab('0:1:0'))             # le second groupe, pas le premier
        self.assertEqual([g['titre'] for g in RE.load(w.settings)['groupes']], ['G', 'M'])

    def test_add_remove_by_menu(self):
        w, r = self.w, self.w.ribbon
        b = next(b for i in range(r.count()) if not r.widget(i).property('ribbon_custom')
                 for b in r.widget(i).findChildren(QToolButton) if b.defaultAction() is w.A['open'])
        m = w._ribbon_button_menu(b, None, exec_menu=False)
        texts = [a.text() for a in m.actions()]
        self.assertIn('Ajouter à « Mon onglet »', texts)
        self.assertIn('Ajouter à un nouvel onglet…', texts)
        self.assertIn(w.A['ribbon_editor'].text(), texts)
        self.assertFalse(any(t.startswith('Retirer') for t in texts))
        self.assertEqual(w.add_to_custom_tab('open', 0), 0)
        self.assertEqual(r.custom_title, 'Mon onglet')
        self.assertEqual(w.add_to_custom_tab('open', 0), 0)            # déjà là : pas en double
        self.assertEqual(len(RE.load(w.settings)['groupes'][0]['commandes']), 1)
        self.assertIn('Déjà', w.statusBar().currentMessage())
        self.assertEqual(w.add_to_custom_tab('save', -1, title='Atelier'), 1)
        self.assertEqual(r.custom_titles, ['Mon onglet', 'Atelier'])
        self.assertEqual(w.add_to_custom_tab('new', 1), 1)
        self.assertEqual([c['key'] for c in RE.load_all(w.settings)[1]['groupes'][0]['commandes']], ['save', 'new'])
        cb = next(b for b in self.buttons('Atelier') if b.defaultAction() is w.A['new'])
        self.assertEqual(cb.property('ribbon_custom_at'), '1:0:1')
        texts = [a.text() for a in w._ribbon_button_menu(cb, None, exec_menu=False).actions()]
        self.assertIn('Retirer de « Atelier »', texts)
        self.assertTrue(w.remove_from_custom_tab('1:0:1'))
        self.assertTrue(w.remove_from_custom_tab('1:0:0'))             # groupe vidé : retiré, onglet caché
        self.assertNotIn('Atelier', self.titles())
        self.assertEqual(RE.load_all(w.settings)[1]['groupes'], [])
        self.assertFalse(w.remove_from_custom_tab('9:0:0'))
        self.assertFalse(w.remove_from_custom_tab('x'))

    def test_new_tab_title_never_builtin(self):
        w = self.w
        b = self.builtin()
        self.assertEqual(w.add_to_custom_tab('open', -1, title=b[0]), 1)
        self.assertEqual(RE.load_all(w.settings)[1]['titre'], b[0] + ' (2)')

    def test_tab_menu_rename_remove(self):
        w, r = self.w, self.w.ribbon
        RE.save_all(w.settings, [tab('Atelier', 'debut', 'open'), tab('Gravure', 'fin', 'save')])
        w._build_custom_tab()
        i = self.titles().index('Gravure')
        texts = [a.text() for a in w._ribbon_tab_menu(i, None, exec_menu=False).actions()]
        self.assertIn('Renommer « Gravure »…', texts)
        self.assertIn('Supprimer « Gravure »', texts)
        self.assertIn('Nouvel onglet…', texts)
        other = self.titles().index(self.builtin()[0])
        texts = [a.text() for a in w._ribbon_tab_menu(other, None, exec_menu=False).actions()]
        self.assertFalse(any(t.startswith('Renommer') for t in texts))
        self.assertTrue(w.rename_custom_tab(1, 'Laser'))
        self.assertIn('Laser', self.titles())
        self.assertNotIn('Gravure', self.titles())
        self.assertTrue(w.rename_custom_tab(1, 'Atelier'))             # titre pris : numéroté
        self.assertEqual(RE.load_all(w.settings)[1]['titre'], 'Atelier (2)')
        with mock.patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.No):
            self.assertFalse(w.remove_custom_tab(1))
        self.assertTrue(w.remove_custom_tab(1, ask=False))
        self.assertEqual(r.custom_titles, ['Atelier'])
        self.assertFalse(w.rename_custom_tab(5, 'X'))

    def test_context_events(self):
        w, r = self.w, self.w.ribbon
        ev = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(5, 5), QPoint(5, 5))
        with mock.patch.object(type(w), '_ribbon_tab_menu') as tm:
            self.assertTrue(w.eventFilter(r.tabBar(), ev))
            tm.assert_called_once()
        b = next(b for b in r.findChildren(QToolButton) if b.defaultAction() is w.A['open'])
        with mock.patch.object(type(w), '_ribbon_button_menu') as bm:
            self.assertTrue(w.eventFilter(b, ev))
            bm.assert_called_once()
        rect = next((b for b in r.findChildren(QToolButton) if b.defaultAction() is w.A.get('tool_rect')), None)
        if rect is not None:                                            # outil de forme : ses paramètres, d'abord
            with mock.patch.object(type(w), 'tool_form_dialog') as fd, \
                    mock.patch.object(type(w), '_ribbon_button_menu') as bm:
                self.assertTrue(w.eventFilter(rect, ev))
                fd.assert_called_once()
                bm.assert_not_called()


class TestEditor(Base):
    def test_several_tabs(self):
        w = self.w
        anchor = self.builtin()[1]
        dlg = w.ribbon_editor(exec_dialog=False)
        self.assertEqual(dlg.tab_choice.count(), 1)
        self.assertGreaterEqual(dlg.pos.findData('apres:' + anchor), 0)
        dlg.add('open')
        self.assertEqual(dlg.new_tab('Gravure'), 1)
        self.assertEqual(dlg.tab_choice.currentText(), 'Gravure')
        self.assertEqual(dlg.title.text(), 'Gravure')
        dlg.add('save')
        dlg.set_label('Garder')
        dlg.pos.setCurrentIndex(dlg.pos.findData('apres:' + anchor))
        self.assertEqual(dlg.tree.topLevelItem(0).child(0).text(0), 'Garder')
        dlg.tab_choice.setCurrentIndex(0)                               # retour au premier : gardé
        self.assertEqual(dlg.title.text(), 'Mon onglet')
        self.assertEqual(dlg.tree.topLevelItem(0).child(0).text(0), w.A['open'].text().replace('&', ''))
        dlg.title.setText('Atelier')
        dlg._renamed('Atelier')
        self.assertEqual(dlg.tab_choice.itemText(0), 'Atelier')
        tabs = dlg.result_tabs()
        self.assertEqual([t['titre'] for t in tabs], ['Atelier', 'Gravure'])
        self.assertEqual(tabs[1]['position'], 'apres:' + anchor)
        self.assertEqual(tabs[1]['groupes'][0]['commandes'][0], {'key': 'save', 'big': True, 'texte': 'Garder'})
        dlg.accept()
        w._build_custom_tab()
        t = self.titles()
        self.assertEqual(w.ribbon.custom_titles, ['Atelier', 'Gravure'])
        self.assertEqual(t[t.index(anchor) + 1], 'Gravure')
        dlg = w.ribbon_editor(exec_dialog=False)                        # rouvert : onglets à soi pas dans la liste
        self.assertNotIn('Gravure', dlg.tab_checks)
        self.assertEqual(dlg.pos.findData('apres:Gravure'), -1)
        self.assertEqual(dlg.tab_choice.count(), 2)
        dlg.tab_choice.setCurrentIndex(1)
        dlg.set_label('')                                               # libellé vide : celui de la commande
        dlg.tree.setCurrentItem(dlg.tree.topLevelItem(0).child(0))
        dlg.set_label('')
        self.assertNotIn('texte', dlg.result_tabs()[1]['groupes'][0]['commandes'][0])
        dlg.remove_tab()
        dlg.remove_tab()
        self.assertEqual([t['titre'] for t in dlg.result_tabs()], ['Mon onglet'])     # jamais aucun

    def test_unique_titles(self):
        w = self.w
        b = self.builtin()
        dlg = w.ribbon_editor(exec_dialog=False)
        dlg.new_tab('Gravure')
        self.assertEqual(dlg.new_tab('Gravure'), 2)
        self.assertEqual(dlg.tab_choice.itemText(2), 'Gravure (2)')
        dlg._renamed(b[0])
        dlg.title.setText(b[0])
        self.assertEqual(dlg.result_tabs()[2]['titre'], b[0] + ' (2)')

    def test_export_import(self):
        w = self.w
        d = tempfile.mkdtemp()
        dlg = w.ribbon_editor(exec_dialog=False)
        dlg.add('open')
        dlg.new_tab('Gravure')
        dlg.add('save')
        dlg.tab_checks[self.builtin()[-1]].setChecked(False)
        path = dlg.export_file(os.path.join(d, 'ruban.json'))
        data = json.loads(pathlib.Path(path).read_text(encoding='utf-8'))
        self.assertEqual([t['titre'] for t in data['onglets']], ['Mon onglet', 'Gravure'])
        self.assertEqual(data['masques'], [self.builtin()[-1]])
        dlg2 = w.ribbon_editor(exec_dialog=False)
        self.assertEqual(dlg2.import_file(path), 2)
        self.assertEqual(dlg2.tab_choice.count(), 2)
        self.assertFalse(dlg2.tab_checks[self.builtin()[-1]].isChecked())
        bad = os.path.join(d, 'bad.json')
        pathlib.Path(bad).write_text('{"onglets": 3}', encoding='utf-8')
        with mock.patch.object(QMessageBox, 'warning') as warn:
            self.assertEqual(dlg2.import_file(bad), 0)
            self.assertEqual(dlg2.import_file(os.path.join(d, 'absent.json')), 0)
            self.assertEqual(warn.call_count, 2)
        self.assertEqual(dlg2.tab_choice.count(), 2)                   # rien changé
        self.assertIsNone(w.settings.value(RE.MORE))                    # validé seulement par OK
        dlg2.accept()
        self.assertEqual([t['titre'] for t in RE.load_all(w.settings)], ['Mon onglet', 'Gravure'])

    def test_new_custom_tab(self):
        w = self.w
        with mock.patch('vectordrive.ui.ribbon_editor.QInputDialog.getText', return_value=('Laser', True)), \
                mock.patch.object(RE.RibbonEditor, 'exec', lambda dlg: (dlg.accept(), 1)[1]):     # OK
            w.new_custom_tab()
        self.assertEqual([t['titre'] for t in RE.load_all(w.settings)], ['Mon onglet', 'Laser'])
        with mock.patch('vectordrive.ui.ribbon_editor.QInputDialog.getText', return_value=('', False)), \
                mock.patch('vectordrive.ui.ribbon_editor.RibbonEditor.exec', return_value=1) as ex:
            w.new_custom_tab()
            ex.assert_not_called()


if __name__ == '__main__':
    unittest.main()
