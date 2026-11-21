"""Round 1131 (demande du 20/11, 21 h 48) : les profils de l'assistant (mode Avancé) : des réglages nommés, jamais
la clé d'API."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1131.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ['VECTORDRIVE_KEYS_MEMORY'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

import tests  # noqa: E402,F401

BEFORE = 'avant : pas de profils de l’assistant'


class Profiles(unittest.TestCase):

    def setUp(self):
        from unittest import mock
        env = mock.patch.dict(os.environ, {})          # jamais la clé d'une variable du poste
        env.start()
        self.addCleanup(env.stop)
        for v in ('MISTRAL_API_KEY', 'ANTHROPIC_API_KEY', 'OPENAI_API_KEY'):
            os.environ.pop(v, None)
        try:
            from vectordrive.ui import assistant_profiles as PR
        except ImportError:
            self.fail(BEFORE)
        self.PR = PR
        from vectordrive.agent import keys
        self.keys = keys
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.reset()
        self.addCleanup(self.clean)
        self.p = self.w.show_assistant_panel()
        self.p.mode.setCurrentIndex(self.p.mode.findData('avance'))

    def reset(self):
        for k in self.PR.PROFILE_KEYS + (self.PR.KEY, 'assistant/mode'):
            self.w.settings.remove(k)

    def clean(self):
        self.p.shutdown()
        self.keys.forget('mistral')
        self.reset()
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def test_shown_in_advanced_only(self):
        self.assertTrue(self.p.profile_box.isVisibleTo(self.p))
        self.p.mode.setCurrentIndex(self.p.mode.findData('debutant'))
        self.assertFalse(self.p.profile_box.isVisibleTo(self.p))

    def test_keep_and_use(self):
        st = self.w.settings
        self.keys.save('mistral', 'sk-secret-123')
        self.p.provider.setCurrentIndex(self.p.provider.findData('mistral'))
        self.p.model.setEditText('mistral-small-latest')
        st.setValue('assistant/outils_fao', False)
        st.setValue('assistant/tours_max', 12)
        self.assertEqual(self.p.keep_profile('  Rapide  '), 'Rapide')
        self.assertNotIn('sk-secret', str(st.value(self.PR.KEY)), 'jamais la clé')
        self.assertEqual(self.p.profile.currentData(), 'Rapide')
        self.p.provider.setCurrentIndex(self.p.provider.findData('anthropic'))
        st.setValue('assistant/outils_fao', True)
        st.remove('assistant/tours_max')
        self.assertTrue(self.p.use_profile('rapide'), 'sans la casse')
        self.assertEqual(self.p.slug(), 'mistral')
        self.assertEqual(self.p.model.currentText(), 'mistral-small-latest')
        from vectordrive.ui.options import value
        self.assertFalse(value(st, 'assistant/outils_fao'))
        self.assertEqual(value(st, 'assistant/tours_max'), 12)
        self.assertIn('Rapide', self.p.status.text())

    def test_unset_values_come_back_to_default(self):
        st = self.w.settings
        self.p.keep_profile('Neuf')
        st.setValue('assistant/tours_max', 99)
        self.p.use_profile('Neuf')
        self.assertFalse(st.contains('assistant/tours_max'), 'pas dans le profil : la valeur d’office')

    def test_replace_remove_and_limits(self):
        PR = self.PR
        self.p.keep_profile('A')
        self.w.settings.setValue('assistant/tours_max', 7)
        self.p.keep_profile('a')
        self.assertEqual([p['name'] for p in PR.load(self.w.settings)], ['a'], 'le même nom : remplacé')
        acts = self.p.btn_profile_del.menu().actions()
        self.assertEqual([a.text() for a in acts], ['a'], 'Retirer : un menu des profils')
        self.w.settings.setValue('assistant/tours_max', 50)
        acts[0].trigger()
        self.assertEqual(PR.load(self.w.settings), [])
        from vectordrive.ui.options import value
        self.assertEqual(value(self.w.settings, 'assistant/tours_max'), 50, 'retiré sans être pris')
        self.assertFalse(self.p.btn_profile_del.isEnabled(), 'plus de profil : rien à retirer')
        self.assertIsNone(self.p.keep_profile('   '))
        for i in range(PR.MAX_PROFILES):
            self.assertIsNotNone(PR.keep(self.w.settings, f'P{i}'))
        self.assertIsNone(self.p.keep_profile('Un de trop'))
        self.assertIn('au plus', self.p.status.text())
        self.w.settings.setValue(PR.KEY, 'pas du json')
        self.assertEqual(PR.load(self.w.settings), [])
        self.w.settings.setValue(PR.KEY, '[{"name": "x", "values": {"assistant/cle": "s", "assistant/tours_max": 3}}]')
        self.assertEqual(PR.load(self.w.settings)[0]['values'], {'assistant/tours_max': 3}, 'ses réglages seulement')
        self.w.settings.setValue(PR.KEY, '[{"name": "y", "values": {"assistant/outils_memoire": null}}]')
        self.assertEqual(PR.load(self.w.settings)[0]['values'], {}, 'une valeur nulle : absente')
        self.w.settings.setValue(PR.KEY, '[' * 100000 + ']' * 100000)
        self.assertEqual(PR.load(self.w.settings), [], 'trop imbriqué : aucun profil, sans planter')

    def test_never_a_secret_nor_the_cap(self):
        st = self.w.settings
        self.keys.save('mistral', 'sk-secret-cle-tres-longue')
        st.setValue('assistant/consignes', 'Ma clé : sk-secret-cle-tres-longue')
        st.setValue('assistant/adresse_mistral', 'http://serveur/sk-AbCdEfGh1234567890xyz')
        st.setValue('assistant/plafond_session', 5.0)
        st.setValue('assistant/tours_max', 12)
        self.p.keep_profile('Sûr')
        raw = str(st.value(self.PR.KEY))
        self.assertNotIn('sk-', raw, 'une clé collée dans un champ : laissée de côté')
        self.assertNotIn('plafond', raw)
        st.setValue('assistant/plafond_session', 5.0)
        self.p.use_profile('Sûr')
        from vectordrive.ui.options import value
        self.assertEqual(value(st, 'assistant/plafond_session'), 5.0, 'un profil ne lève pas le plafond')
        self.assertEqual(value(st, 'assistant/tours_max'), 12)
        st.remove('assistant/plafond_session')
        st.remove('assistant/consignes')
        st.remove('assistant/adresse_mistral')


if __name__ == '__main__':
    unittest.main()
