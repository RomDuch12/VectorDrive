"""Round 1132 (demande du 20/11, 21 h 48) : « Vérifier » la clé d'un clic ; enregistrer la discussion. Aucun appel
réel : un client simulé."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1132.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ['VECTORDRIVE_KEYS_MEMORY'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

import tests  # noqa: E402,F401

BEFORE = 'avant : ni « Vérifier » ni « Enregistrer la discussion »'


def reply(text):
    return {'choices': [{'message': {'role': 'assistant', 'content': text}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5}}


class Refused(Exception):
    status_code = 401


class Check(unittest.TestCase):

    def setUp(self):
        from unittest import mock
        env = mock.patch.dict(os.environ, {})          # jamais la clé d'une variable du poste
        env.start()
        self.addCleanup(env.stop)
        for v in ('MISTRAL_API_KEY', 'ANTHROPIC_API_KEY', 'OPENAI_API_KEY'):
            os.environ.pop(v, None)
        from vectordrive.agent import keys
        self.keys = keys
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.settings.remove('assistant/mode')
        self.addCleanup(self.clean)
        self.p = self.w.show_assistant_panel()
        if not hasattr(self.p, 'check_key'):
            self.fail(BEFORE)
        self.p.provider.setCurrentIndex(self.p.provider.findData('mistral'))
        self.dir = pathlib.Path(tempfile.mkdtemp())

    def clean(self):
        self.p.wait(10)
        self.p.shutdown()
        self.keys.forget('mistral')
        self.w.settings.remove('assistant/mode')
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def test_check_button_needs_a_key(self):
        self.assertFalse(self.p.btn_check.isEnabled(), 'sans clé : rien à vérifier')
        self.p.key.setText('sk-essai')
        self.p.save_key()
        self.p._open_setup()
        self.assertTrue(self.p.btn_check.isEnabled())
        self.assertTrue(self.p.btn_check.isVisibleTo(self.p))

    def test_check_ok(self):
        self.keys.save('mistral', 'sk-essai')
        bodies = []
        self.p.client_for = lambda _p: (lambda body: bodies.append(body) or reply('OK'))
        self.p.conv = None
        self.assertTrue(self.p.check_key())
        self.assertTrue(self.p.wait(20))
        self.assertIn('Connexion vérifiée', self.p.status.text())
        self.assertTrue(any('réponds seulement' in str(m.get('content')) for m in bodies[0]['messages']
                            if m.get('role') == 'user'), 'la courte demande envoyée')
        self.assertIsNone(self.p.conv, 'à part : la discussion n’est pas touchée')
        self.assertNotIn('réponds seulement', self.p.view.toPlainText())
        self.assertEqual(len(bodies[0]['tools']), 1, 'sans les outils du dessin')
        self.assertFalse(self.w.modified, 'le dessin n’est pas marqué modifié')
        self.assertFalse(self.p._checking)

    def test_check_refused_key(self):
        self.keys.save('mistral', 'sk-faux')

        def send(_body):
            raise Refused('bad key')
        self.p.client_for = lambda _p: send
        self.p.conv = None
        self.assertTrue(self.p.check_key())
        self.assertTrue(self.p.wait(20))
        self.assertIn('Clé refusée', self.p.status.text())
        self.assertFalse(self.p._checking)

    def test_save_discussion(self):
        self.assertIsNone(self.p.save_discussion(str(self.dir / 'vide.txt')), 'vide : rien')
        self.p.client_for = lambda _p: (lambda body: reply('Un rectangle de 20 × 10 mm.'))
        self.p.conv = None
        self.assertTrue(self.p.send('Décris le dessin'))
        self.assertTrue(self.p.wait(20))
        t = self.p.save_discussion(str(self.dir / 'd.txt'))
        text = pathlib.Path(t).read_text(encoding='utf-8')
        self.assertIn('Décris le dessin', text)
        self.assertIn('20 × 10 mm', text)
        m = pathlib.Path(self.p.save_discussion(str(self.dir / 'd.md'))).read_text(encoding='utf-8')
        self.assertIn('20 × 10 mm', m)
        h = pathlib.Path(self.p.save_discussion(str(self.dir / 'd.html'))).read_text(encoding='utf-8')
        self.assertIn('<html', h.lower())
        self.assertEqual(sorted(x.name for x in self.dir.iterdir()), ['d.html', 'd.md', 'd.txt'], 'aucun provisoire')
        self.assertIsNone(self.p.save_discussion(str(self.dir / 'absent' / 'x.txt')))
        self.assertIn('non enregistrée', self.p.status.text())


if __name__ == '__main__':
    unittest.main()
