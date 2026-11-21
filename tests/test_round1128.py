"""Round 1128 (demande du 20/11, 21 h 48) : « optimiser parametrage utilisation débutant clé en main et utilisation
avancée de l'assistant IA ». Le mode Débutant / Avancé du panneau. Aucun appel réel : un client simulé."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1128.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ['VECTORDRIVE_KEYS_MEMORY'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

import tests  # noqa: E402,F401

BEFORE = 'avant : pas de mode Débutant / Avancé'


def reply(text):
    return {'choices': [{'message': {'role': 'assistant', 'content': text}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5}}


class Modes(unittest.TestCase):

    def setUp(self):
        from unittest import mock
        env = mock.patch.dict(os.environ, {})          # jamais la clé d'une variable du poste
        env.start()
        self.addCleanup(env.stop)
        for v in ('MISTRAL_API_KEY', 'ANTHROPIC_API_KEY', 'OPENAI_API_KEY'):
            os.environ.pop(v, None)
        from vectordrive.agent import keys
        from vectordrive.agent.chat import PROVIDERS
        self.keys = keys
        for p in PROVIDERS:
            keys.forget(p)
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.settings.remove('assistant/mode')
        self.w.settings.remove('assistant/fournisseur')
        self.addCleanup(self.clean)

    def clean(self):
        p = getattr(self, 'p', None)
        if p is not None:
            p.wait(10)
            p.shutdown()
        from vectordrive.agent.chat import PROVIDERS
        for prov in PROVIDERS:
            self.keys.forget(prov)
        self.w.settings.remove('assistant/mode')
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def panel(self):
        self.p = self.w.show_assistant_panel()
        if not hasattr(self.p, 'mode'):
            self.fail(BEFORE)
        return self.p

    def shown(self, w):
        return w.isVisibleTo(self.p)

    def test_option_exists(self):
        from vectordrive.ui.options import BY_KEY
        self.assertIn('assistant/mode', BY_KEY, BEFORE)
        self.assertEqual(BY_KEY['assistant/mode'].default, 'debutant')

    def test_beginner_without_a_key(self):
        p = self.panel()
        self.assertEqual(p.mode.currentData(), 'debutant', 'jamais choisi, sans clé : Débutant')
        self.assertEqual(self.w.settings.value('assistant/mode'), 'debutant', 'retenu : F10 le montre')
        self.assertTrue(self.shown(p.steps), 'les premiers pas')
        for w in (p.provider, p.key, p.btn_save, p.get_key):
            self.assertTrue(self.shown(w))
        for w in (p.model, p.url, p.summary, p.btn_memory, p.btn_add_memory):
            self.assertFalse(self.shown(w))
        self.assertTrue(self.shown(p.btn_more))
        self.assertEqual([a.text() for a in p.btn_more.menu().actions()], ['Mémoire…', 'Ajouter à une mémoire…'])
        self.assertTrue(self.shown(p.suggest_box), 'des exemples de demandes')

    def test_beginner_key_then_change(self):
        p = self.panel()
        p.key.setText('sk-essai')
        p.save_key()
        self.assertFalse(self.shown(p.steps))
        self.assertTrue(self.shown(p.summary))
        self.assertIn('Mistral', p.summary.text())
        self.assertIn('Changer', p.summary.text())
        for w in (p.provider, p.key, p.btn_save):
            self.assertFalse(self.shown(w), 'la clé retenue : une ligne courte')
        self.assertIn('mistral-', p.summary.text(), 'le modèle qui sert, dit')
        p._open_setup('setup')
        self.assertTrue(self.shown(p.key))
        self.assertTrue(self.shown(p.provider))
        self.assertTrue(self.shown(p.model), 'le modèle aussi : il sert toujours')
        self.assertTrue(self.shown(p.url))
        self.assertIn('Masquer', p.summary.text())
        p.url.setText('http://localhost:9999')
        p._open_setup('setup')
        self.assertFalse(self.shown(p.key), 'Masquer : la ligne courte seule')
        self.assertIn('localhost:9999', p.summary.text(), 'un serveur choisi : dit')
        p.url.setText('')
        p._open_setup('setup')
        p.key.setText('sk-autre')
        p.save_key()
        self.assertTrue(self.shown(p.summary), 'retenue : la ligne courte revient')
        self.assertFalse(self.shown(p.key))

    def test_options_show_the_panel_default(self):
        self.keys.save('mistral', 'sk-deja')
        self.w.settings.remove('assistant/mode')
        d = self.w.options_dialog(exec_dialog=False, page='Assistant')
        self.addCleanup(d.deleteLater)
        self.assertEqual(d.widgets['assistant/mode'].currentData(), 'avance', 'une clé retenue : Avancé, comme le panneau')

    def test_advanced_shows_everything(self):
        p = self.panel()
        p.mode.setCurrentIndex(p.mode.findData('avance'))
        self.assertEqual(self.w.settings.value('assistant/mode'), 'avance')
        for w in (p.provider, p.model, p.url, p.key, p.btn_memory, p.btn_add_memory):
            self.assertTrue(self.shown(w))
        for w in (p.steps, p.summary, p.btn_more, p.suggest_box):
            self.assertFalse(self.shown(w))
        p.provider.setCurrentIndex(p.provider.findData('anthropic'))
        self.assertFalse(self.shown(p.url), 'l’adresse : Mistral seulement')

    def test_default_with_a_stored_key_is_advanced(self):
        self.keys.save('mistral', 'sk-deja')
        from vectordrive.ui.assistant_panel import mode_of
        self.assertEqual(mode_of(self.w.settings, self.keys), 'avance', 'l’assistant servait déjà')
        self.w.settings.setValue('assistant/mode', 'debutant')
        self.assertEqual(mode_of(self.w.settings, self.keys), 'debutant', 'choisi : gardé')

    def test_suggestions(self):
        p = self.panel()
        p.suggestions[1].click()
        self.assertEqual(p.input.toPlainText(), 'Ajoute un cadre à 5 mm autour de la sélection')
        self.assertFalse(p.running, 'pas envoyé : à relire')
        p.provider.setCurrentIndex(p.provider.findData('mistral'))
        p.client_for = lambda _p: (lambda body: reply('Voici.'))
        p.conv = None
        self.assertTrue(p.send('Décris ce dessin'))
        self.assertTrue(p.wait(20))
        self.assertFalse(self.shown(p.suggest_box), 'la discussion commencée')
        p.new_chat()
        self.assertTrue(self.shown(p.suggest_box), 'nouvelle discussion : les exemples reviennent')

    def test_options_follow(self):
        p = self.panel()
        self.w.settings.setValue('assistant/mode', 'avance')
        p.apply_settings()
        self.assertEqual(p.mode.currentData(), 'avance')
        self.assertTrue(self.shown(p.model))
        dlg = p.open_options(exec_dialog=False)
        self.assertEqual(dlg.tabs.tabText(dlg.tabs.currentIndex()), 'Assistant')
        dlg.deleteLater()


if __name__ == '__main__':
    unittest.main()
