"""Round 1091 (demande du 19/11 matin) : « Assistant a son onglet dans parametres dédié avec full customization
possible (scripts et templates de script, mémoire, affichage console, api gestion) ». Aucun appel réel ; clés en
mémoire, mémoire et scripts dans des dossiers d'essai."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1091.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ['VECTORDRIVE_KEYS_MEMORY'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : pas d’onglet Assistant dans les options'
KEYS = ('assistant/fournisseur', 'assistant/modele_mistral', 'assistant/tours_max', 'assistant/outils_commandes',
        'assistant/taille_texte', 'assistant/couleur_vous', 'assistant/montrer_outils', 'assistant/consignes',
        'assistant/dossier_modeles', 'assistant/valeurs_couleur')


class AssistantOptions(unittest.TestCase):

    def setUp(self):
        here = tempfile.mkdtemp()
        env = mock.patch.dict(os.environ, {'VECTORDRIVE_MEMORY': os.path.join(here, 'memoire', 'memoire.md'),
                                           'VECTORDRIVE_SCRIPTS': os.path.join(here, 'scripts')})
        env.start()
        self.addCleanup(env.stop)
        self.scripts = pathlib.Path(here, 'scripts')
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.addCleanup(self.close)
        self.w._te_script_folder = lambda: None
        from vectordrive.ui.options import BY_KEY
        st = self.w.settings
        every = list(BY_KEY) + list(KEYS)                # OK écrit toutes les options : remises comme avant
        saved = {k: st.value(k) for k in every if st.contains(k)}

        def back():
            for k in every:
                st.remove(k)
            for k, v in saved.items():
                st.setValue(k, v)
        self.addCleanup(back)
        for k in KEYS:
            st.remove(k)

    def close(self):
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def page(self):
        from vectordrive.ui.options import SPEC
        dlg = self.w.options_dialog(exec_dialog=False, page='Assistant')
        titles = [t for t, _o in SPEC]
        self.assertIn('Assistant', titles, BEFORE)
        self.assertEqual(dlg.tabs.currentIndex(), titles.index('Assistant'))
        return dlg

    def test_the_tab_keeps_everything(self):
        from vectordrive.agent import tools as AT
        p = self.w.show_assistant_panel()                                  # déjà fait : il doit suivre
        self.addCleanup(p.shutdown)
        dlg = self.page()
        W = dlg.widgets
        W['assistant/fournisseur'].setCurrentIndex(W['assistant/fournisseur'].findData('mistral'))
        W['assistant/modele_mistral'].setText('mistral-small-latest')
        W['assistant/tours_max'].setValue(7)
        W['assistant/outils_commandes'].setChecked(False)
        W['assistant/taille_texte'].setValue(14)
        W['assistant/couleur_vous'].setValue('#aa0000')
        W['assistant/montrer_outils'].setChecked(False)
        dlg.assistant_instructions.setPlainText('Réponds en peu de mots.')
        dlg.assistant_memory.setPlainText('Plaques en laiton de 0,8 mm.')
        dlg.accept()
        st = self.w.settings
        self.assertEqual(st.value('assistant/fournisseur'), 'mistral')
        self.assertEqual(st.value('assistant/consignes'), 'Réponds en peu de mots.')
        self.assertEqual(AT.memory_text(), 'Plaques en laiton de 0,8 mm.')
        # le panneau suit
        self.w.apply_options()                                             # comme après OK de F10
        self.assertEqual(p.slug(), 'mistral')
        self.assertEqual(p.model.currentText(), 'mistral-small-latest')
        self.assertEqual(p.view.font().pointSize(), 14)
        p.client_for = lambda _p: (lambda body: None)
        conv = p.conversation()
        self.assertEqual(conv.max_steps, 7)
        names = conv.tools.names()
        self.assertNotIn('run_command', names)                       # retirées par l'option
        self.assertIn('run_script', names)
        self.assertIn('Réponds en peu de mots.', conv.system)
        self.assertIn('Plaques en laiton', conv.system)
        p._on_tool('⚙ get_document')                                  # outils cachés
        self.assertNotIn('get_document', p.view.toPlainText())
        p._out = p.view
        p._line('<b style="color:{0}">x</b>'.format(p._colors()['user']), raw=True)
        self.assertEqual(p._colors()['user'], '#aa0000')
        # une option changée : nouvelle discussion
        st.setValue('assistant/outils_commandes', True)
        self.assertIsNot(p.conversation(), conv)
        self.assertIn('run_command', p.conversation().tools.names())

    def test_memory_off_and_cleared(self):
        from vectordrive.agent import tools as AT
        from vectordrive.ui import assistant_options as AO
        AT.write_memory('Note ancienne.')
        self.w.settings.setValue('assistant/outils_memoire', False)
        self.addCleanup(self.w.settings.remove, 'assistant/outils_memoire')
        self.assertNotIn('Note ancienne', AO.system_text(self.w.settings))   # pas permise : ni lue, ni outils
        self.assertEqual(AO.without(self.w.settings), ('memory',))
        dlg = self.page()
        dlg.findChild(type(dlg.assistant_instructions))                    # la page est faite
        clear = [b for b in dlg.findChildren(__import__('PySide6.QtWidgets', fromlist=['QPushButton']).QPushButton)
                 if b.text() == 'Effacer la mémoire']
        self.assertEqual(len(clear), 1)
        clear[0].click()
        dlg.accept()
        self.assertEqual(AT.memory_text(), '')

    def test_api_keys(self):
        from vectordrive.agent import keys
        dlg = self.page()
        state, edit, keep, forget, _r = dlg.key_rows['openai']
        edit.setText('sk-essai-1091')
        keep.click()
        self.assertTrue(keys.stored('openai'))
        self.assertEqual(edit.text(), '')                                   # jamais laissée affichée
        self.assertEqual(state.text(), 'Clé : retenue')
        st = self.w.settings
        self.assertFalse(any('sk-essai-1091' in str(st.value(k)) for k in st.allKeys()))   # jamais dans les réglages
        forget.click()
        self.assertFalse(keys.stored('openai'))
        # Entrée dans le champ : la clé retenue, la fenêtre pas validée
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        dlg.show()
        edit.setFocus()
        edit.setText('sk-essai-entree')
        QTest.keyClick(edit, Qt.Key.Key_Return)
        self.assertTrue(keys.stored('openai'))
        self.assertTrue(dlg.isVisible(), 'avant : Entrée validait toute la fenêtre des options')
        keys.forget('openai')
        dlg.reject()

    def test_search_finds_the_custom_parts(self):
        from vectordrive.ui.options import SPEC
        dlg = self.page()
        i = [t for t, _o in SPEC].index('Assistant')
        dlg.tabs.setCurrentIndex(0)
        self.assertGreater(dlg.filter_options('clé'), 0)
        self.assertTrue(dlg.tabs.isTabEnabled(i))                          # avant : onglet grisé
        dlg.filter_options('')
        dlg.tabs.setCurrentIndex(0)
        self.assertGreater(dlg.filter_options('consignes'), 0)
        self.assertEqual(dlg.tabs.currentIndex(), i)
        dlg.reject()

    def test_memory_written_meanwhile_is_kept(self):
        from vectordrive.agent import tools as AT
        AT.write_memory('Première note.\n')
        dlg = self.page()
        dlg.assistant_memory.setPlainText('Première note corrigée.\n')
        AT.write_memory('Première note.\nAjout de l’assistant.\n')        # pendant que la fenêtre est ouverte
        dlg.accept()
        self.assertEqual(AT.memory_text(), 'Première note corrigée.\nAjout de l’assistant.\n')
        AT.write_memory('Avant.\n')
        dlg = self.page()
        dlg.assistant_memory.setPlainText('Corrigée.\n')
        AT.write_memory('Tout réécrit par lui.\n')
        dlg.accept()
        self.assertEqual(AT.memory_text(), 'Tout réécrit par lui.\n')       # rien d'écrasé

    def test_script_templates(self):
        import json
        from vectordrive.agent.tools import ToolSet
        from vectordrive.ui import assistant_options as AO
        folder = AO.templates_dir(self.w.settings)
        self.assertEqual(folder, self.scripts / 'modeles')
        made = AO.seed_templates(folder)
        self.assertEqual(made, folder / 'Exemple.vbs')
        self.assertIsNone(AO.seed_templates(folder))                       # jamais deux fois, jamais par-dessus
        t = ToolSet(self.w, extended=True)
        listed = json.loads(t.call('list_scripts', {})[0]['text'])['scripts']
        self.assertIn({'name': 'Exemple', 'folder': 'templates'}, listed)
        self.assertIn('Exemple', json.loads(t.call('read_script', {'name': 'Exemple'})[0]['text'])['name'])
        other = pathlib.Path(tempfile.mkdtemp())
        self.w.settings.setValue('assistant/dossier_modeles', str(other))
        self.assertEqual(AO.templates_dir(self.w.settings), other)
        self.w.settings.setValue('assistant/dossier_modeles', str(self.scripts))   # le dossier des scripts même
        self.scripts.mkdir(parents=True, exist_ok=True)
        (self.scripts / 'Un.vbs').write_text('Dim x', encoding='utf-8')
        listed = json.loads(t.call('list_scripts', {})[0]['text'])['scripts']
        self.assertEqual([s for s in listed if s['name'] == 'Un'], [{'name': 'Un', 'folder': 'user'}])   # une fois
        blocker = pathlib.Path(tempfile.mkdtemp(), 'fichier')
        blocker.write_text('x', encoding='utf-8')
        self.assertIsNone(AO.seed_templates(blocker / 'modeles'))         # inaccessible : rien, sans erreur
        self.assertFalse(AO._open_folder(blocker / 'modeles'))


if __name__ == '__main__':
    unittest.main()
