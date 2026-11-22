"""Round 1139 (demande du 22/11 : « integrer les meilleurs moteurs mistral locaux pour GPU 4go 8go 12go 16go dans les
possibilités assistants ») : Mistral en local par Ollama. Aucun appel réel, aucun téléchargement : Ollama, la carte
graphique et les consoles sont simulés."""
import os
import tempfile
import unittest
import urllib.error
from unittest import mock
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1139.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ['VECTORDRIVE_KEYS_MEMORY'] = '1'
from PySide6.QtWidgets import QApplication  # noqa: E402
app = QApplication.instance() or QApplication([])
import tests  # noqa: E402,F401

BEFORE = 'avant : pas de Mistral en local'


def LM():
    try:
        from vectordrive.agent import local_models
    except ImportError:
        raise AssertionError(BEFORE) from None
    return local_models


class Tools:
    """Un jeu d'outils minimal : `mesure` rend la largeur du dessin."""

    def __init__(self):
        self.calls = []

    def specs(self):
        return [{'name': 'mesure', 'description': 'Largeur du dessin', 'inputSchema': {'type': 'object',
                                                                                       'properties': {}}}]

    def call(self, name, args):
        self.calls.append((name, args))
        return [{'type': 'text', 'text': 'largeur 80 mm'}]


def native(text='', calls=(), done='stop'):
    msg = {'role': 'assistant', 'content': text}
    if calls:
        msg['tool_calls'] = [{'function': {'name': n, 'arguments': a}} for n, a in calls]
    return {'model': 'x', 'message': msg, 'done': True, 'done_reason': done, 'prompt_eval_count': 900,
            'eval_count': 40}


class Tiers(unittest.TestCase):

    def test_recommend_by_gpu(self):
        L = LM()
        self.assertEqual([t.gpu_gb for t in L.TIERS], [4, 8, 12, 16])
        self.assertTrue(all(t.model.startswith(('ministral-3:', 'mistral-small3.2:')) for t in L.TIERS))
        for gb, model in ((None, 'ministral-3:3b'), (2, 'ministral-3:3b'), (3.8, 'ministral-3:3b'),
                          (6, 'ministral-3:3b'), (7.8, 'ministral-3:8b'), (11.8, 'ministral-3:14b'),
                          (16, 'mistral-small3.2:24b'), (24, 'mistral-small3.2:24b')):
            self.assertEqual(L.recommend(gb).model, model, gb)
        self.assertIs(L.tier_of(' Ministral-3:8B '), L.TIERS[1])
        self.assertIsNone(L.tier_of('mistral-small:latest'))
        self.assertIn('◀', L.table_text(12).splitlines()[2])

    def test_gpu_memory(self):
        L = LM()
        self.assertEqual(L.gpu_memory_gb(run=lambda a: '16384\n8192\n', read=lambda k, n: None), 16.0)
        boom = mock.Mock(side_effect=OSError('pas de nvidia-smi'))
        four = (4 * 1024 ** 3).to_bytes(8, 'little')
        got = L.gpu_memory_gb(run=boom, read=lambda k, n: four if k.endswith('0000') and 'qw' in n else None)
        self.assertEqual(got, 4.0)
        self.assertIsNone(L.gpu_memory_gb(run=boom, read=lambda k, n: None))

    def test_addresses(self):
        L = LM()
        for raw, base in (('', 'http://localhost:11434'), ('http://localhost:11434/', 'http://localhost:11434'),
                          ('http://atelier:11434/api/chat', 'http://atelier:11434'),
                          ('http://127.0.0.1:11434/v1/chat/completions', 'http://127.0.0.1:11434')):
            self.assertEqual(L.base_url(raw), base)
        for ok in ('http://localhost:11434', 'http://192.168.1.20:11434', 'http://atelier-gpu:11434',
                   'http://poste.local:11434', 'https://ollama.exemple.fr'):
            self.assertTrue(L.address_ok(ok), ok)
        for ok in ('http://[::1]:11434', 'http://[fd00::5]:11434', 'http://3dprinter:11434'):
            self.assertTrue(L.address_ok(ok), ok)
        for bad in ('http://exemple.fr:11434', 'http://8.8.8.8:11434', 'http://u:p@localhost:11434',
                    'ftp://localhost', 'localhost:11434', 'http://[2001:4860:4860::8888]:11434',
                    'http://134744072:11434', 'http://0x8080808:11434', 'http://[::ffff:8.8.8.8]:11434',
                    'http://0.0.0.0:11434', 'http://localhost:abc'):
            self.assertFalse(L.address_ok(bad), bad)

    def test_status(self):
        L = LM()
        pages = {'/api/version': {'version': '0.32.13'},
                 '/api/tags': {'models': [{'name': 'mistral-small:latest'}, {'name': 'ministral-3:8b'}]}}
        got = L.status('', get=lambda url, t: pages[url[len('http://localhost:11434'):]])
        self.assertEqual(got, {'running': True, 'version': '0.32.13',
                               'models': ['ministral-3:8b', 'mistral-small:latest'], 'error': ''})
        self.assertTrue(L.has_model(got['models'], 'mistral-small'))
        self.assertFalse(L.has_model(got['models'], 'ministral-3:14b'))

        def down(url, t):
            raise urllib.error.URLError(ConnectionRefusedError('refusé'))
        self.assertFalse(L.status('', get=down)['running'])
        self.assertEqual(L.status('http://exemple.fr:11434')['error'], 'adresse refusée')
        self.assertTrue(L.version_ok('0.13.1') and L.version_ok('0.32.13') and L.version_ok('0.14.0-rc1'))
        self.assertFalse(L.version_ok('0.12.9'))

    def test_pull_console_and_start_need_ollama(self):
        L = LM()
        seen = []
        with mock.patch.object(L, 'exe', lambda: r'C:\Ollama\ollama.exe'):
            self.assertTrue(L.pull('ministral-3:8b', popen=lambda a, **k: seen.append(a)))
            self.assertTrue(L.start(popen=lambda a, **k: seen.append(a)))
        self.assertIn('pull', seen[0])
        self.assertEqual(seen[0][-1], 'ministral-3:8b')
        with mock.patch.object(L, 'exe', lambda: None):
            self.assertFalse(L.pull('ministral-3:8b', popen=lambda a, **k: self.fail('rien lancé')))
            self.assertFalse(L.start(popen=lambda a, **k: self.fail('rien lancé')))


class Conversation(unittest.TestCase):

    def setUp(self):
        LM()
        from vectordrive.agent import chat, keys
        self.chat, self.keys = chat, keys

    def test_provider_without_key(self):
        self.assertIn('local', self.chat.PROVIDERS)
        self.assertEqual(self.chat.PROVIDERS['local'][1], 'ministral-3:8b')
        self.assertEqual(self.keys.load('local'), 'ollama')
        self.assertFalse(self.keys.stored('local'))
        self.assertIn('ollama.com', self.chat.KEY_PAGES['local'])

    def test_native_dialogue_with_context_and_tools(self):
        bodies = []
        answers = [native(calls=[('mesure', {})]), native('Le dessin fait 80 mm.')]

        def client(body):
            bodies.append(body)
            return answers.pop(0)
        tools = Tools()
        used = []
        c = self.chat.Conversation('local', 'ministral-3:14b', self.keys.load('local'), tools, client=client,
                                   context=8192, on_usage=used.append)
        self.assertEqual(c.send('Quelle largeur ?'), 'Le dessin fait 80 mm.')
        self.assertEqual(tools.calls, [('mesure', {})])
        first, second = bodies
        self.assertEqual(first['model'], 'ministral-3:14b')
        self.assertTrue(first['stream'], 'en flux : « Arrêter » coupe entre deux morceaux')
        self.assertEqual(first['options']['num_ctx'], 8192, 'le contexte : plus que les 4 096 d’Ollama')
        self.assertEqual(first['tools'][0]['function']['name'], 'mesure')
        call = second['messages'][-2]
        self.assertEqual(call['tool_calls'][0]['function'], {'name': 'mesure', 'arguments': {}})
        self.assertEqual(second['messages'][-1]['role'], 'tool')
        self.assertEqual(second['messages'][-1]['tool_name'], 'mesure')
        self.assertNotIn('tool_call_id', second['messages'][-1])
        self.assertEqual(used[0]['in'], 900)
        c2 = self.chat.Conversation('local', '', 'ollama', tools, client=lambda b: bodies.append(b) or native('ok'))
        c2.send('?')
        self.assertEqual(bodies[-1]['options']['num_ctx'], 16384, 'd’office')
        self.assertEqual(bodies[-1]['model'], 'ministral-3:8b')

    def test_cut_answer_and_errors(self):
        c = self.chat.Conversation('local', 'ministral-3:3b', 'ollama', Tools(),
                                   client=lambda b: native('long…', done='length'))
        self.assertIn('coupée', c.send('?'))
        with self.assertRaises(self.chat.BadAddress):
            self.chat.Conversation('local', '', 'ollama', Tools(), url='http://exemple.fr:11434')
        c = self.chat.Conversation('local', 'ministral-3:14b', 'ollama', Tools(), url='http://localhost:9')
        b = c._backend
        self.assertEqual(b.url, 'http://localhost:9/api/chat')
        import io
        import threading
        chat = self.chat

        class Resp:
            def __init__(self, status=200, data=b'', wait=None):
                self.status, self._f, self.wait = status, io.BytesIO(data), wait

            def read(self, n=-1):
                return self._f.read(n)

            def readline(self):
                return self._f.readline()

        class Sock:
            def __init__(self):
                self.down = threading.Event()

            def shutdown(self, _how):
                self.down.set()

        class Conn:
            """Une fausse connexion : `result` (réponse ou exception) ; `hold` : attend « Arrêter » (le modèle se
            charge, rien n'arrive encore)."""

            def __init__(self, result=None, hold=False):
                self.result, self.hold, self.sock, self.sent, self.closed = result, hold, Sock(), [], False

            def request(self, method, path, body=None, headers=None):
                self.sent.append((method, path, json.loads(body), headers))

            def getresponse(self):
                if self.hold:
                    if not self.sock.down.wait(5):
                        raise AssertionError('jamais coupé')
                    raise __import__('http.client').client.RemoteDisconnected('coupé')
                if isinstance(self.result, BaseException):
                    raise self.result
                return self.result

            def close(self):
                self.closed = True
        import json
        body = b._native({'model': 'm', 'messages': [], 'tools': [], 'max_tokens': 10})
        lines = [b'{"message":{"role":"assistant","content":"Bon"},"done":false}\n',
                 b'{"message":{"role":"assistant","content":"jour"},"done":false}\n',
                 b'{"message":{"role":"assistant","content":"","tool_calls":[{"function":{"name":"mesure",'
                 b'"arguments":{}}}]},"done":false}\n',
                 b'{"done":true,"done_reason":"stop","prompt_eval_count":12,"eval_count":3}\n']
        cases = ((Resp(404, b'{"error":"model \\"x\\" not found, try pulling it first"}'), chat.MissingModel),
                 (Resp(404, b'404 page not found'), chat.ProviderError),
                 (Resp(500, b'{"error":"model requires more system memory (20 GiB) than is available"}'),
                  chat.LocalError),
                 (ConnectionRefusedError('refusé'), chat.LocalDown),
                 (TimeoutError('délai'), chat.LocalTimeout),
                 (__import__('ssl').SSLError('certificat'), chat.LocalError),
                 (Resp(200, b''.join(lines[:2])), chat.LocalError),             # flux coupé avant la fin
                 (Resp(200, b'{"error":"model failed to load"}\n'), chat.LocalError))
        for result, kind in cases:
            conn = Conn(result)
            with self.assertRaises(kind, msg=repr(result)):
                b._call(body, connect=lambda conn=conn: conn)
            self.assertTrue(conn.closed)
        with self.assertRaises(chat.LocalError) as cm:
            b._call(body, connect=lambda: Conn(Resp(500, b'{"error":"CUDA error: out of memory"}')))
        self.assertTrue(cm.exception.memory)
        conn = Conn(Resp(200, b''.join(lines)))
        got = b._call(body, connect=lambda: conn)
        self.assertEqual(got['message']['content'], 'Bonjour')
        self.assertEqual(got['message']['tool_calls'][0]['function']['name'], 'mesure')
        self.assertEqual(got['eval_count'], 3)
        method, path, sent, headers = conn.sent[0]
        self.assertEqual((method, path), ('POST', '/api/chat'))
        self.assertTrue(sent['stream'])
        self.assertNotIn('Authorization', headers, 'pas de clé envoyée')
        # « Arrêter » pendant le chargement du modèle (aucun morceau encore) : la connexion coupée, Stopped
        held = Conn(hold=True)
        out = {}

        def run():
            try:
                b._call(body, connect=lambda: held)
            except Exception as ex:                      # noqa: BLE001
                out['ex'] = ex
        th = threading.Thread(target=run)
        th.start()
        for _i in range(100):
            if b._conn is held:
                break
            __import__('time').sleep(0.01)
        c.stop()
        th.join(5)
        self.assertIsInstance(out.get('ex'), chat.Stopped)
        self.assertTrue(held.sock.down.is_set())
        with self.assertRaises(chat.Stopped):
            b._call(body, connect=lambda: Conn(Resp(200, b''.join(lines))))
        # arrêté pendant la connexion (pas encore de socket) : la demande ne part jamais, même si une autre demande
        # remet l'arrêt à zéro aussitôt après
        c4 = chat.Conversation('local', 'm', 'ollama', Tools(), url='http://localhost:9')
        slow = Conn(Resp(200, b''.join(lines)))
        slow.sock = None

        def connect():
            __import__('time').sleep(0.4)
            slow.sock = Sock()
        slow.connect = connect
        th = threading.Thread(target=lambda: out.update(ex4=self._catch(c4._backend._call, body, lambda: slow)))
        th.start()
        __import__('time').sleep(0.1)
        c4.stop()
        th.join(2)
        self.assertIsInstance(out.get('ex4'), chat.Stopped)
        c4._stop.clear()                                 # une nouvelle demande remet l'arrêt à zéro
        __import__('time').sleep(0.6)
        self.assertEqual(slow.sent, [], 'l’ancien échange ne part pas')
        with self.assertRaises(chat.LocalError):
            chat._Ollama._from_native({'error': 'out of memory'})

    @staticmethod
    def _catch(fn, *args):
        try:
            fn(*args)
        except Exception as ex:                          # noqa: BLE001
            return ex
        return None

    def test_no_system_proxy(self):
        import urllib.request
        b = self.chat.Conversation('local', 'ministral-3:8b', 'ollama', Tools(), url='http://localhost:9')._backend
        with mock.patch.dict(os.environ, {'HTTP_PROXY': 'http://proxy.exemple.fr:3128'}):
            conn = b._connect()
        self.assertEqual((conn.host, conn.port), ('localhost', 9), 'une connexion directe, jamais par le proxy')
        self.assertIsNone(getattr(conn, '_tunnel_host', None))
        L = LM()
        built = []

        class NoNet:
            def open(self, *_a, **_k):
                raise urllib.error.URLError(ConnectionRefusedError('pas de réseau dans les essais'))

        def spy(*handlers):
            built.append(handlers)
            return NoNet()
        with mock.patch.object(urllib.request, 'build_opener', spy):
            self.assertFalse(L.status('http://localhost:9')['running'])
        self.assertTrue(any(isinstance(h, urllib.request.ProxyHandler) and not h.proxies for h in built[0]))



class Ui(unittest.TestCase):

    def setUp(self):
        LM()
        from vectordrive.agent import keys
        from vectordrive.agent.chat import PROVIDERS
        self.keys = keys
        for p in PROVIDERS:
            keys.forget(p)
        env = mock.patch.dict(os.environ, {})
        env.start()
        self.addCleanup(env.stop)
        for v in ('MISTRAL_API_KEY', 'ANTHROPIC_API_KEY', 'OPENAI_API_KEY'):
            os.environ.pop(v, None)
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        for k in ('assistant/mode', 'assistant/fournisseur', 'assistant/modele_local', 'assistant/adresse_local',
                  'assistant/modeles_local', 'assistant/gpu_local'):
            self.w.settings.remove(k)
        self.addCleanup(self.clean)

    def clean(self):
        p = getattr(self, 'p', None)
        if p is not None:
            p.wait(10)
            p.shutdown()
        for k in ('assistant/mode', 'assistant/fournisseur', 'assistant/modele_local', 'assistant/adresse_local',
                  'assistant/modeles_local', 'assistant/gpu_local', 'assistant/adresse_mistral'):
            self.w.settings.remove(k)
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def test_panel_local_provider(self):
        self.w.settings.setValue('assistant/modeles_local', 'mistral-small:latest|ministral-3:8b')
        self.w.settings.setValue('assistant/adresse_mistral', 'https://mistral.exemple.fr/v1/chat/completions')
        self.p = p = self.w.show_assistant_panel()
        p.mode.setCurrentIndex(p.mode.findData('avance'))
        p.provider.setCurrentIndex(p.provider.findData('local'))
        shown = lambda w: w.isVisibleTo(p)               # noqa: E731
        for w in (p.key, p.btn_save, p.btn_forget):
            self.assertFalse(shown(w), 'sans clé : ni champ, ni Retenir, ni Oublier')
        self.assertTrue(shown(p.url) and shown(p.model))
        self.assertIn('Ollama', p.key_state.text())
        self.assertIn('Installer Ollama', p.get_key.text())
        self.assertEqual(p.url.text(), '', 'l’adresse de Mistral n’est pas celle d’Ollama')
        self.assertEqual(p.url.placeholderText(), 'http://localhost:11434')
        items = [p.model.itemText(i) for i in range(p.model.count())]
        self.assertEqual(items[:4], ['ministral-3:3b', 'ministral-3:8b', 'ministral-3:14b', 'mistral-small3.2:24b'])
        self.assertIn('mistral-small:latest', items, 'les modèles vus chez Ollama')
        self.assertEqual(p.model.currentText(), 'ministral-3:8b')
        p.url.setText('http://atelier:11434')
        p.url.editingFinished.emit()
        self.assertEqual(self.w.settings.value('assistant/adresse_local'), 'http://atelier:11434')
        self.assertEqual(self.w.settings.value('assistant/adresse_mistral'),
                         'https://mistral.exemple.fr/v1/chat/completions', 'chacun son adresse')
        p.provider.setCurrentIndex(p.provider.findData('mistral'))
        self.assertEqual(p.url.text(), 'https://mistral.exemple.fr/v1/chat/completions')
        p.provider.setCurrentIndex(p.provider.findData('local'))
        self.assertEqual(p.url.text(), 'http://atelier:11434')
        bodies = []
        p.client_for = lambda _p: (lambda body: bodies.append(body) or native('Bonjour, je tourne ici.'))
        self.assertTrue(p.send('Bonjour'))
        self.assertTrue(p.wait(20))
        app.processEvents()
        self.assertIn('Bonjour, je tourne ici.', p.view.toPlainText())
        self.assertEqual(bodies[0]['options']['num_ctx'], 16384)
        self.assertIn('Ollama ne répond pas', p.explain(__import__('vectordrive.agent.chat', fromlist=['x'])
                                                        .LocalDown('http://atelier:11434')))
        from vectordrive.agent.chat import MissingModel
        self.assertIn('Télécharger le modèle', p.explain(MissingModel('ministral-3:14b')))
        from vectordrive.agent.chat import LocalError, LocalTimeout
        self.assertIn('Mémoire insuffisante', p.explain(LocalError('model requires more system memory')))
        self.assertIn('Ollama : modèle illisible', p.explain(LocalError('modèle illisible')))
        self.assertIn('pas répondu à temps', p.explain(LocalTimeout('http://localhost:11434', 600)))
        # le plafond des dépenses (atteint avec un fournisseur payant) ne bloque pas le modèle local, gratuit
        self.w.settings.setValue('assistant/plafond_session', 1.0)
        self.addCleanup(self.w.settings.remove, 'assistant/plafond_session')
        p.session_credits = {'cout': 5.0}
        self.assertTrue(p.send('Encore'))
        self.assertTrue(p.wait(20))
        p.provider.setCurrentIndex(p.provider.findData('mistral'))
        self.keys.save('mistral', 'sk-essai')
        self.addCleanup(self.keys.forget, 'mistral')
        self.assertFalse(p.send('Payant'), 'le plafond tient pour les autres')

    def test_beginner_local_summary(self):
        self.w.settings.setValue('assistant/fournisseur', 'local')
        self.p = p = self.w.show_assistant_panel()
        self.assertEqual(p.slug(), 'local')
        self.assertTrue(p.summary.isVisibleTo(p), 'sans clé à coller : la ligne courte d’emblée')
        self.assertIn('sans clé', p.summary.text())
        self.assertFalse(p.steps.isVisibleTo(p))

    def test_options_local_box(self):
        from vectordrive.agent import local_models as L
        d = self.w.options_dialog(exec_dialog=False, page='Assistant')
        self.addCleanup(d.deleteLater)
        self.assertNotIn('local', d.key_rows, 'pas de ligne de clé pour le modèle local')
        self.assertEqual(d.local_tier.count(), 4)
        self.assertEqual(d.widgets['assistant/contexte_local'].value(), 16384)
        with mock.patch.object(L, 'gpu_memory_gb', lambda: 12.0):
            self.assertEqual(d.local_actions['detect'](), 12.0)
        self.assertEqual(d.local_tier.currentData(), 'ministral-3:14b')
        self.assertIn('12 Go', d.local_gpu.text())
        self.assertEqual(float(self.w.settings.value('assistant/gpu_local')), 12.0)
        running = {'running': True, 'version': '0.32.13', 'models': ['ministral-3:8b'], 'error': ''}
        self.assertEqual(d.widgets['assistant/contexte_local'].minimum(), 8192, 'jamais moins que les outils')
        with mock.patch.object(L, 'status', lambda url: running):
            d.local_actions['check']()                   # dans un fil de travail : la fenêtre reste vive
            for _i in range(50):
                app.processEvents()
                if '0.32.13' in d.local_state.text():
                    break
                __import__('time').sleep(0.02)
        self.assertIn('0.32.13', d.local_state.text())
        self.assertIn('à télécharger', d.local_state.text())
        self.assertEqual(self.w.settings.value('assistant/modeles_local'), 'ministral-3:8b')
        with mock.patch.object(L, 'status', lambda url: {**running, 'version': '0.12.0'}):
            d.local_actions['check'](sync=True)
        self.assertIn('0.13.1', d.local_state.text())
        down = {'running': False, 'version': '', 'models': [], 'error': 'refusé'}
        with mock.patch.object(L, 'status', lambda url: down), mock.patch.object(L, 'exe', lambda: None):
            d.local_actions['check'](sync=True)
        self.assertIn('pas installé', d.local_state.text())
        pulled = []
        with mock.patch.object(L, 'pull', lambda m: pulled.append(m) or True):
            self.assertTrue(d.local_actions['pull']())
        self.assertEqual(pulled, ['ministral-3:14b'])
        self.assertIn('9,1 Go', d.local_state.text())
        installed = mock.patch.object(L, 'exe', lambda: r'C:\Ollama\ollama.exe')
        with mock.patch.object(L, 'start', mock.Mock(side_effect=OSError('refusé'))), installed:
            self.assertFalse(d.local_actions['start']())
        self.assertIn('pas lancé', d.local_state.text(), 'installé mais pas lancé : dit tel quel')
        with mock.patch.object(L, 'start', lambda: False), mock.patch.object(L, 'exe', lambda: None):
            self.assertFalse(d.local_actions['start']())
        self.assertIn('pas installé', d.local_state.text())
        d.local_actions['use']()
        self.assertEqual(d.widgets['assistant/fournisseur'].currentData(), 'local')
        self.assertEqual(d.widgets['assistant/modele_local'].text(), 'ministral-3:14b')
        d.accept()
        self.assertEqual(self.w.settings.value('assistant/fournisseur'), 'local')
        from vectordrive.ui.assistant_profiles import PROFILE_KEYS
        for k in ('assistant/modele_local', 'assistant/adresse_local', 'assistant/contexte_local'):
            self.assertIn(k, PROFILE_KEYS)
        self.assertEqual(self.w.settings.value('assistant/modele_local'), 'ministral-3:14b')


if __name__ == '__main__':
    unittest.main()
