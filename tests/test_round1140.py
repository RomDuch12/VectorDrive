"""Round 1140 (demande du 22/11 après-midi : « vd desktop doit pouvoir gérer entièrement l'install de ollama, de son
modèle et son utilisation ») : installer Ollama depuis VectorDrive, télécharger le modèle avec l'avancement,
démarrer Ollama tout seul, « Tout préparer ». Aucun appel réel, aucun téléchargement, rien d'installé : Ollama,
l'installateur, sa signature et le réseau sont simulés."""
import io
import os
import pathlib
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest import mock
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1140.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ['VECTORDRIVE_KEYS_MEMORY'] = '1'
from PySide6.QtWidgets import QApplication  # noqa: E402
app = QApplication.instance() or QApplication([])
import tests  # noqa: E402,F401
from vectordrive.agent import local_models as L  # noqa: E402

BEFORE = 'avant : Ollama ne s’installe pas depuis VectorDrive'


def need(name):
    if not hasattr(L, name):
        raise AssertionError(BEFORE)
    return getattr(L, name)


class Resp:
    """Une réponse HTTP simulée (urllib ou http.client)."""

    def __init__(self, data=b'', status=200, url=None, length=None):
        self._f, self.status = io.BytesIO(data), status
        self._url = url or 'https://release-assets.githubusercontent.com/x/OllamaSetup.exe'
        self.headers = {'Content-Length': str(len(data) if length is None else length)}

    def geturl(self):
        return self._url

    def read(self, n=-1):
        return self._f.read(n)

    def readline(self):
        return self._f.readline()

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class Opener:
    def __init__(self, result):
        self.result, self.asked = result, []

    def open(self, req, timeout=None):
        self.asked.append(req.full_url)
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


class Conn:
    """Une connexion http.client simulée pour /api/pull."""

    def __init__(self, resp=None, error=None):
        self.resp, self.error, self.sent, self.closed = resp, error, [], False

    def request(self, method, path, body=None, headers=None):
        if self.error is not None:
            raise self.error
        self.sent.append((method, path, body))

    def getresponse(self):
        return self.resp

    def close(self):
        self.closed = True


def lines(*items):
    import json
    return b''.join(json.dumps(i).encode() + b'\n' for i in items)


class Address(unittest.TestCase):

    def test_on_this_machine(self):
        here = need('on_this_machine')
        for url in ('', 'http://localhost:11434', 'http://127.0.0.1:11434/api/chat', 'http://[::1]:11434'):
            self.assertTrue(here(url), url)
        for url in ('http://atelier:11434', 'http://192.168.1.20:11434', 'http://localhost:8080',
                    'https://ollama.exemple.fr', 'http://localhost'):
            self.assertFalse(here(url), url)

    def test_installer_hosts_and_redirects(self):
        need('INSTALLER_URL')
        self.assertTrue(L.INSTALLER_URL.startswith('https://ollama.com/'))
        for url in ('https://ollama.com/download/OllamaSetup.exe',
                    'https://github.com/ollama/ollama/releases/download/v1/OllamaSetup.exe',
                    'https://release-assets.githubusercontent.com/github-production-release-asset/1/2'):
            self.assertTrue(L._host_ok(url), url)
        for url in ('http://github.com/x', 'https://evilgithub.com/x', 'https://ollama.com.evil.fr/x',
                    'https://exemple.fr/OllamaSetup.exe'):
            self.assertFalse(L._host_ok(url), url)
        req = urllib.request.Request(L.INSTALLER_URL)
        with self.assertRaises(L.SetupError) as cm:
            L._SafeRedirect().redirect_request(req, None, 302, 'Found', {}, 'https://exemple.fr/setup.exe')
        self.assertEqual(cm.exception.reason, 'source')
        ok = L._SafeRedirect().redirect_request(req, None, 302, 'Found', {},
                                                'https://github.com/ollama/ollama/releases/latest/download/x.exe')
        self.assertIsNotNone(ok)


class Installer(unittest.TestCase):

    def setUp(self):
        need('download_installer')
        self.dir = pathlib.Path(tempfile.mkdtemp())

    def test_download(self):
        data = b'MZ' + b'x' * (3 << 20)
        seen = []
        got = L.download_installer(self.dir, on_progress=lambda d, t: seen.append((d, t)), opener=Opener(Resp(data)))
        self.assertEqual(got, self.dir / 'OllamaSetup.exe')
        self.assertEqual(got.read_bytes(), data)
        self.assertEqual(seen[-1], (len(data), len(data)))
        self.assertGreater(len(seen), 2, 'l’avancement au fil du téléchargement')
        self.assertFalse((self.dir / 'OllamaSetup.exe.part').exists())

    def test_download_refusals(self):
        cases = ((Resp(b'MZ1234', url='https://exemple.fr/OllamaSetup.exe'), 'source'),
                 (Resp(b'<html>proxy</html>'), 'file'),
                 (Resp(b'MZ12', length=10), 'download'),
                 (urllib.error.URLError(ConnectionRefusedError('pare-feu')), 'download'),
                 (urllib.error.HTTPError(L.INSTALLER_URL, 403, 'Forbidden', {}, None), 'download'))
        for result, reason in cases:
            with self.assertRaises(L.SetupError, msg=reason) as cm:
                L.download_installer(self.dir, opener=Opener(result))
            self.assertEqual(cm.exception.reason, reason)
            self.assertEqual(list(self.dir.iterdir()), [], 'aucun fichier laissé')
        stop = threading.Event()
        stop.set()
        with self.assertRaises(L.Cancelled):
            L.download_installer(self.dir, cancel=stop, opener=Opener(Resp(b'MZ' * 10)))
        self.assertEqual(list(self.dir.iterdir()), [])

    def test_signature(self):
        trusted = need('trusted')
        good = 'Valid|CN=Ollama Inc., O=Ollama Inc., L=Toronto, S=Ontario, C=CA'
        self.assertTrue(trusted('x.exe', run=lambda _p: good))
        self.assertTrue(trusted('x.exe', run=lambda _p: 'Valid|CN=Ollama Inc., O="Ollama Inc.", C=CA'))
        for out in ('Valid|CN=Ollama Inc.Evil, O=Ollama Inc.Evil', 'NotSigned|', 'HashMismatch|O=Ollama Inc.',
                    'Valid|CN=Autre, O=Autre', '', None, 'Valid|CN=x, OU="a, O=Ollama Inc., b", O=Autre',
                    'Valid|CN="x, O=Ollama Inc.", O=Autre', 'Valid|O=Autre, O=Ollama Inc.'):
            self.assertFalse(trusted('x.exe', run=lambda _p, out=out: out), out)

    def test_install_checks_signature_before_running(self):
        setup = self.dir / 'OllamaSetup.exe'

        def fake_download(folder, on_progress=None, cancel=None, opener=None):
            setup.parent.mkdir(exist_ok=True)           # retiré, vide, après chaque installation
            setup.write_bytes(b'MZ')
            if on_progress is not None:
                on_progress(2, 2)
            return setup
        ran, steps = [], []

        class Proc:
            def __init__(self, code):
                self.code = code

            def wait(self):
                return self.code

        with mock.patch.object(L, 'download_installer', fake_download), \
                mock.patch.object(L, 'exe', lambda: r'C:\Users\x\AppData\Local\Programs\Ollama\ollama.exe'):
            path = L.install(self.dir, on_step=steps.append, on_progress=lambda d, t: None,
                             run=lambda _p: 'Valid|CN=Ollama Inc., O=Ollama Inc.',
                             popen=lambda args, **k: ran.append(args) or Proc(0))
            self.assertTrue(path.endswith('ollama.exe'))
            self.assertEqual(steps, ['download', 'verify', 'install'])
            self.assertEqual(ran[0][0], str(setup))
            self.assertIn('/SILENT', ran[0])
            self.assertIn('/CLOSEAPPLICATIONS', ran[0], 'un Ollama en marche fermé pour la mise à jour')
            self.assertFalse(setup.exists(), 'l’installateur retiré après')
            ran.clear()
            with self.assertRaises(L.SetupError) as cm:
                L.install(self.dir, run=lambda _p: 'Valid|CN=Autre, O=Autre', popen=lambda a, **k: ran.append(a))
            self.assertEqual(cm.exception.reason, 'signature')
            self.assertEqual(ran, [], 'un installateur mal signé n’est jamais lancé')
            self.assertFalse(setup.exists())
            with self.assertRaises(L.SetupError) as cm:
                L.install(self.dir, run=lambda _p: 'Valid|O=Ollama Inc.', popen=lambda a, **k: Proc(5))
            self.assertEqual((cm.exception.reason, cm.exception.detail), ('installer', '5'))
            with self.assertRaises(L.SetupError) as cm:
                L.install(self.dir, run=lambda _p: 'Valid|O=Ollama Inc.',
                          popen=mock.Mock(side_effect=OSError('bloqué par la stratégie')))
            self.assertEqual(cm.exception.reason, 'installer', 'un lancement refusé est dit, pas une erreur brute')
        with mock.patch.object(L, 'download_installer', fake_download), mock.patch.object(L, 'exe', lambda: None):
            with self.assertRaises(L.SetupError) as cm:
                L.install(self.dir, run=lambda _p: 'Valid|O=Ollama Inc.', popen=lambda a, **k: Proc(0))
            self.assertEqual(cm.exception.reason, 'missing')

    def test_install_cleanup_and_last_cancel(self):
        job = self.dir / 'job'
        job.mkdir()
        with mock.patch.object(L, 'download_installer', mock.Mock(side_effect=L.SetupError('download', 'x'))):
            with self.assertRaises(L.SetupError):
                L.install(job)
        self.assertFalse(job.exists(), 'le dossier du travail retiré après un échec')
        job.mkdir()
        stop = threading.Event()

        def fake_download(folder, on_progress=None, cancel=None, opener=None):
            f = pathlib.Path(folder) / 'OllamaSetup.exe'
            f.write_bytes(b'MZ')
            return f
        steps = []

        def on_step(k):
            steps.append(k)
            if k == 'install':
                stop.set()                               # Annuler pile à ce moment
        with mock.patch.object(L, 'download_installer', fake_download):
            with self.assertRaises(L.Cancelled):
                L.install(job, on_step=on_step, cancel=stop, run=lambda _p: 'Valid|O=Ollama Inc.',
                          popen=lambda a, **k: self.fail('jamais lancé après Annuler'))
        self.assertEqual(steps, ['download', 'verify', 'install'])
        self.assertFalse(job.exists())

    def test_winget_console(self):
        seen = []
        with mock.patch.object(L, 'winget', lambda: None):
            self.assertFalse(L.install_winget(popen=lambda a, **k: self.fail('rien lancé')))
        with mock.patch.object(L, 'winget', lambda: r'C:\winget.exe'):
            self.assertTrue(L.install_winget(popen=lambda a, **k: seen.append((a, k))))
        args, kw = seen[0]
        self.assertTrue(args[0].lower().endswith(r'system32\cmd.exe'), 'cmd de Windows, par son chemin')
        self.assertEqual(args[1], '/k')
        self.assertIn('Ollama.Ollama', args)
        self.assertNotIn('--accept-package-agreements', args, 'l’utilisateur accepte lui-même dans la console')


class Pull(unittest.TestCase):

    def setUp(self):
        need('pull_stream')

    def test_progress_and_success(self):
        resp = Resp(lines({'status': 'pulling manifest'},
                          {'status': 'pulling a', 'digest': 'sha256:a', 'total': 1000, 'completed': 100},
                          {'status': 'pulling b', 'digest': 'sha256:b', 'total': 3000, 'completed': 0},
                          {'status': 'pulling a', 'digest': 'sha256:a', 'total': 1000, 'completed': 1000},
                          {'status': 'pulling b', 'digest': 'sha256:b', 'total': 3000, 'completed': 3000},
                          {'status': 'verifying sha256 digest'}, {'status': 'success'}))
        conn = Conn(resp)
        seen = []
        L.pull_stream('ministral-3:8b', '', on_progress=lambda s, d, t: seen.append((s, d, t)),
                      connect=lambda: conn)
        self.assertEqual(conn.sent[0][:2], ('POST', '/api/pull'))
        self.assertIn(b'"ministral-3:8b"', conn.sent[0][2])
        conn = Conn(Resp(lines({'status': 'success'})))
        L.pull_stream('m:1b', 'https://srv.atelier.fr/ollama', connect=lambda: conn)
        self.assertEqual(conn.sent[0][1], '/ollama/api/pull', 'le chemin de l’adresse gardé')
        self.assertEqual(seen[2], ('pulling b', 100, 4000), 'toutes les parties réunies')
        self.assertEqual(seen[-1], ('success', 4000, 4000))
        self.assertTrue(conn.closed)

    def test_errors(self):
        cases = ((Conn(Resp(b'{"error":"pull model manifest: file does not exist"}', status=500)), 'pull'),
                 (Conn(Resp(lines({'status': 'pulling manifest'}, {'error': 'disque plein'}))), 'pull'),
                 (Conn(Resp(lines({'status': 'pulling manifest'}))), 'pull'),        # coupé avant « success »
                 (Conn(error=ConnectionRefusedError('refusé')), 'down'))
        for conn, reason in cases:
            with self.assertRaises(L.SetupError, msg=reason) as cm:
                L.pull_stream('ministral-3:8b', '', connect=lambda conn=conn: conn)
            self.assertEqual(cm.exception.reason, reason)
        with self.assertRaises(L.SetupError) as cm:
            L.pull_stream('ministral-3:8b', 'http://8.8.8.8:11434', connect=lambda: self.fail('pas de connexion'))
        self.assertEqual(cm.exception.reason, 'address')
        stop = threading.Event()
        stop.set()
        conn = Conn(Resp(lines({'status': 'pulling manifest'}, {'status': 'success'})))
        with self.assertRaises(L.Cancelled):
            L.pull_stream('ministral-3:8b', '', cancel=stop, connect=lambda: conn)
        self.assertTrue(conn.closed, 'la connexion fermée : Ollama arrête le téléchargement')


class Start(unittest.TestCase):

    def test_ensure_running(self):
        ensure = need('ensure_running')
        up = {'running': True}
        down = {'running': False}
        self.assertTrue(ensure('', status_fn=lambda: up, start_fn=lambda: self.fail('déjà en marche')))
        self.assertFalse(ensure('http://atelier:11434', status_fn=lambda: down,
                                start_fn=lambda: self.fail('jamais un autre poste')))
        with mock.patch.object(L, 'exe', lambda: None):
            self.assertFalse(ensure('', status_fn=lambda: down, start_fn=lambda: self.fail('pas installé')))
        answers = iter([down, down, down, up])
        started = []
        with mock.patch.object(L, 'exe', lambda: r'C:\Ollama\ollama.exe'):
            self.assertTrue(ensure('', status_fn=lambda: next(answers), start_fn=lambda: started.append(1) or True,
                                   sleep=lambda _s: None))
            self.assertEqual(started, [1])
            self.assertFalse(ensure('', status_fn=lambda: down, start_fn=lambda: True, sleep=lambda _s: None,
                                    stopping=lambda: True), 'arrêté par l’utilisateur')
            self.assertFalse(ensure('', status_fn=lambda: down, start_fn=lambda: False))
            self.assertEqual(L.down_reason(''), 'start')
        with mock.patch.object(L, 'exe', lambda: None):
            self.assertEqual(L.down_reason(''), 'notinstalled')
        self.assertEqual(L.down_reason('http://atelier:11434'), 'down')


class Tools:
    def specs(self):
        return [{'name': 'mesure', 'description': 'Largeur', 'inputSchema': {'type': 'object', 'properties': {}}}]

    def call(self, name, args):
        return [{'type': 'text', 'text': 'largeur 80 mm'}]


def native(text):
    return {'model': 'x', 'message': {'role': 'assistant', 'content': text}, 'done': True, 'done_reason': 'stop',
            'prompt_eval_count': 10, 'eval_count': 2}


class AutoStart(unittest.TestCase):

    def setUp(self):
        need('ensure_running')
        from vectordrive.agent import chat
        self.chat = chat

    def conv(self, **kw):
        said = []
        c = self.chat.Conversation('local', 'ministral-3:8b', 'ollama', Tools(), on_status=said.append, **kw)
        return c, said

    def test_started_then_retried(self):
        c, said = self.conv(autostart=True)
        b = c._backend
        b._call = mock.Mock(side_effect=[self.chat.LocalDown(b.base), native('Bonjour')])
        with mock.patch.object(L, 'exe', lambda: r'C:\Ollama\ollama.exe'), \
                mock.patch.object(L, 'ensure_running', mock.Mock(return_value=True)) as ens:
            self.assertIn('Bonjour', c.send('Salut'))
        self.assertEqual(said, ['ollama-start', 'ollama-ready'])
        self.assertEqual(b._call.call_count, 2)
        ens.assert_called_once()

    def test_not_started(self):
        c, said = self.conv(autostart=False)
        c._backend._call = mock.Mock(side_effect=self.chat.LocalDown('http://localhost:11434'))
        with mock.patch.object(L, 'ensure_running', mock.Mock(side_effect=AssertionError('jamais'))):
            with self.assertRaises(self.chat.LocalDown):
                c.send('Salut')
        self.assertEqual(said, [])
        # une seule tentative par discussion
        c, said = self.conv(autostart=True)
        c._backend._call = mock.Mock(side_effect=self.chat.LocalDown('http://localhost:11434'))
        with mock.patch.object(L, 'exe', lambda: r'C:\Ollama\ollama.exe'), \
                mock.patch.object(L, 'ensure_running', mock.Mock(return_value=False)) as ens:
            for _i in range(2):
                with self.assertRaises(self.chat.LocalDown):
                    c.send('Salut')
        ens.assert_called_once()
        # un autre poste : rien n'est démarré
        c = self.chat.Conversation('local', 'ministral-3:8b', 'ollama', Tools(), url='http://atelier:11434',
                                   autostart=True)
        c._backend._call = mock.Mock(side_effect=self.chat.LocalDown('http://atelier:11434'))
        with mock.patch.object(L, 'ensure_running', mock.Mock(side_effect=AssertionError('jamais'))):
            with self.assertRaises(self.chat.LocalDown):
                c.send('Salut')

    def test_stop_while_starting(self):
        c, said = self.conv(autostart=True)
        c._backend._call = mock.Mock(side_effect=self.chat.LocalDown('http://localhost:11434'))

        def slow(*_a, stopping=None, **_k):
            c.stop()
            return stopping()
        with mock.patch.object(L, 'exe', lambda: r'C:\Ollama\ollama.exe'), mock.patch.object(L, 'ensure_running',
                                                                                            slow):
            with self.assertRaises(self.chat.Stopped):
                c.send('Salut')


class Ui(unittest.TestCase):

    def setUp(self):
        need('ensure_running')
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.keys = ('assistant/fournisseur', 'assistant/modele_local', 'assistant/adresse_local',
                     'assistant/modeles_local', 'assistant/gpu_local', 'assistant/demarrage_local', 'assistant/mode')
        for k in self.keys:
            self.w.settings.remove(k)
        self.addCleanup(self.clean)

    def clean(self):
        p = getattr(self, 'p', None)
        if p is not None:
            p.wait(10)
            p.shutdown()
        for k in self.keys:
            self.w.settings.remove(k)
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def test_option_and_panel(self):
        from vectordrive.ui.options import BY_KEY
        from vectordrive.ui.assistant_profiles import PROFILE_KEYS
        self.assertIs(BY_KEY['assistant/demarrage_local'].default, True)
        self.assertIn('assistant/demarrage_local', PROFILE_KEYS)
        self.w.settings.setValue('assistant/fournisseur', 'local')
        self.p = p = self.w.show_assistant_panel()
        self.assertEqual(p.slug(), 'local')
        self.assertTrue(p.conversation().autostart)
        self.w.settings.setValue('assistant/demarrage_local', False)
        self.assertFalse(p.conversation().autostart, 'le réglage repris à la demande suivante')
        from vectordrive.agent.chat import LocalDown
        self.assertIn('Tout préparer', p.explain(LocalDown('http://localhost:11434')))
        self.assertIn('allumez le poste', p.explain(LocalDown('http://atelier:11434')))
        thread, p._thread = p._thread, mock.Mock(is_alive=lambda: True)
        try:
            p._on_status('ollama-start')
        finally:
            p._thread = thread
        self.assertIn('démarrage d’Ollama', p.status.text())

    def dialog(self, answer=True):
        d = self.w.options_dialog(exec_dialog=False, page='Assistant')
        self.addCleanup(d.deleteLater)
        asked = []
        d.local_confirm = lambda title, text: asked.append(text) or answer
        return d, asked

    def test_prepare_everything(self):
        d, asked = self.dialog()
        with mock.patch.object(L, 'exe', lambda: None):
            d.local_tier.setCurrentIndex(d.local_tier.findData('ministral-3:8b'))
            d.local_tier.setCurrentIndex(d.local_tier.findData('ministral-3:3b'))
        self.assertIn('○ 1.', d.local_steps.text(), 'Ollama pas installé : l’étape 1 à faire')
        calls = []

        def install(folder, on_step=None, on_progress=None, cancel=None):
            on_step('download')
            on_progress(5, 10)
            calls.append('install')
            return r'C:\Ollama\ollama.exe'

        def pull(m, url, on_progress=None, cancel=None):
            on_progress('pulling', 1, 2)
            calls.append(('pull', m))
        running = {'running': True, 'version': '0.40.17', 'models': [], 'error': ''}
        with mock.patch.object(L, 'exe', lambda: None), mock.patch.object(L, 'install', install), \
                mock.patch.object(L, 'ensure_running', lambda *a, **k: True), \
                mock.patch.object(L, 'status', lambda url, **k: running), mock.patch.object(L, 'pull_stream', pull), \
                mock.patch('sys.platform', 'win32'):
            self.assertTrue(d.local_actions['prepare'](sync=True))
        self.assertIn('installer Ollama', asked[0])
        self.assertIn('3 Go', asked[0])
        self.assertEqual(calls, ['install', ('pull', 'ministral-3:3b')])
        self.assertEqual(d.widgets['assistant/fournisseur'].currentData(), 'local')
        self.assertEqual(d.widgets['assistant/modele_local'].text(), 'ministral-3:3b')
        self.assertIn('prêt', d.local_state.text())
        steps = d.local_steps.text()
        for n in ('1.', '2.', '3.', '4.'):
            self.assertIn('✔ ' + n, steps)

    def test_prepare_refused_or_failed(self):
        d, asked = self.dialog(answer=False)
        with mock.patch.object(L, 'exe', lambda: None), mock.patch('sys.platform', 'win32'), \
                mock.patch.object(L, 'install', mock.Mock(side_effect=AssertionError('sans accord'))):
            self.assertFalse(d.local_actions['prepare'](sync=True))
            self.assertFalse(d.local_actions['install'](sync=True))
        self.assertEqual(len(asked), 2)
        d, asked = self.dialog()
        winget = []
        with mock.patch.object(L, 'exe', lambda: None), mock.patch('sys.platform', 'win32'), \
                mock.patch.object(L, 'install', mock.Mock(side_effect=L.SetupError('signature'))):
            d.local_actions['install'](sync=True)
        self.assertIn('pas signé par Ollama Inc.', d.local_state.text())
        with mock.patch.object(L, 'exe', lambda: None), mock.patch('sys.platform', 'win32'), \
                mock.patch.object(L, 'install', mock.Mock(side_effect=L.SetupError('download', 'proxy'))), \
                mock.patch.object(L, 'winget', lambda: r'C:\winget.exe'), \
                mock.patch.object(L, 'install_winget', lambda: winget.append(1) or True):
            d.local_actions['install'](sync=True)
        self.assertEqual(winget, [1], 'winget proposé quand le téléchargement échoue')
        self.assertIn('winget', asked[-1])
        with mock.patch.object(L, 'exe', lambda: r'C:\Ollama\ollama.exe'):
            self.assertFalse(d.local_actions['install']())
        self.assertIn('déjà installé', d.local_state.text())
        # trop ancien : « Installer Ollama… » le met à jour
        d.local_known['version'] = '0.12.0'
        upd = []
        fresh = {'running': True, 'version': '0.40.17', 'models': [], 'error': ''}
        with mock.patch.object(L, 'exe', lambda: r'C:\Ollama\ollama.exe'), mock.patch('sys.platform', 'win32'), \
                mock.patch.object(L, 'install', lambda *a, **k: upd.append(1) or 'x'), \
                mock.patch.object(L, 'ensure_running', lambda url, **k: upd.append(url) or True), \
                mock.patch.object(L, 'status', lambda url, **k: upd.append(url) or fresh):
            self.assertTrue(d.local_actions['install'](sync=True))
        self.assertEqual(upd, [1, L.DEFAULT_URL, L.DEFAULT_URL], 'puis Ollama de ce poste, quelle que soit l’adresse')
        self.assertEqual(d.local_known['version'], '', 'revue à la prochaine vérification')
        # un autre poste trop ancien : pas de réinstallation ici
        d.widgets['assistant/adresse_local'].setText('http://atelier:11434')
        d.local_known['version'] = '0.12.0'
        with mock.patch.object(L, 'exe', lambda: r'C:\Ollama\ollama.exe'):
            self.assertFalse(d.local_actions['install']())
        d.widgets['assistant/adresse_local'].setText('')
        d.local_known['version'] = ''
        old = {'running': True, 'version': '0.12.0', 'models': [], 'error': ''}
        d.local_tier.setCurrentIndex(d.local_tier.findData('ministral-3:8b'))
        with mock.patch.object(L, 'exe', lambda: r'C:\Ollama\ollama.exe'), \
                mock.patch.object(L, 'ensure_running', lambda *a, **k: True), \
                mock.patch.object(L, 'status', lambda url, **k: old), \
                mock.patch.object(L, 'pull_stream', mock.Mock(side_effect=AssertionError('trop ancien'))):
            d.local_actions['prepare'](sync=True)
        self.assertIn('trop ancien', d.local_state.text())
        self.assertEqual(d.local_known['version'], '0.12.0', 'retenue : « Installer Ollama » le mettra à jour')
        upd = []
        with mock.patch.object(L, 'exe', lambda: r'C:\Ollama\ollama.exe'), mock.patch('sys.platform', 'win32'), \
                mock.patch.object(L, 'install', lambda *a, **k: upd.append(1) or 'x'), \
                mock.patch.object(L, 'ensure_running', lambda *a, **k: True), \
                mock.patch.object(L, 'status', lambda url, **k: old):
            self.assertTrue(d.local_actions['install'](sync=True))
        self.assertEqual(upd, [1])
        self.assertIn('toujours en version 0.12.0', d.local_state.text())
        with mock.patch.object(L, 'exe', lambda: r'C:\Ollama\ollama.exe'), \
                mock.patch.object(L, 'ensure_running', lambda *a, **k: False):
            d.local_actions['pull'](sync=True)
        self.assertIn('ne démarre pas', d.local_state.text())

    def test_pull_progress_and_cancel(self):
        d, _asked = self.dialog()
        go = threading.Event()

        def pull(m, url, on_progress=None, cancel=None):
            on_progress('pulling', 3 * 10 ** 9, 6 * 10 ** 9)
            go.set()
            while not cancel.is_set():
                time.sleep(0.01)
            raise L.Cancelled()
        with mock.patch.object(L, 'ensure_running', lambda *a, **k: True), mock.patch.object(L, 'pull_stream', pull):
            self.assertTrue(d.local_actions['pull']())
            self.assertTrue(go.wait(5))
            for _i in range(50):
                app.processEvents()
                if d.local_bar.value() == 500:
                    break
                time.sleep(0.02)
            self.assertTrue(d.local_bar.isVisibleTo(d) and d.local_cancel.isVisibleTo(d))
            self.assertEqual(d.local_bar.value(), 500)
            self.assertIn('3 Go / 6 Go', d.local_state.text())
            self.assertFalse(d.local_tier.isEnabled(), 'le palier figé pendant le travail')
            d.local_cancel.click()
            for _i in range(100):
                app.processEvents()
                if not d.local_bar.isVisibleTo(d):
                    break
                time.sleep(0.02)
        self.assertFalse(d.local_bar.isVisibleTo(d))
        self.assertIn('Annulé', d.local_state.text())
        self.assertTrue(d.local_tier.isEnabled())

    def test_prepare_keeps_its_model(self):
        d, _asked = self.dialog()
        d.local_tier.setCurrentIndex(d.local_tier.findData('ministral-3:14b'))
        go, release = threading.Event(), threading.Event()

        def pull(m, url, on_progress=None, cancel=None):
            go.set()
            release.wait(5)
        running = {'running': True, 'version': '0.40.17', 'models': [], 'error': ''}
        with mock.patch.object(L, 'exe', lambda: r'C:\Ollama\ollama.exe'), \
                mock.patch.object(L, 'ensure_running', lambda *a, **k: True), \
                mock.patch.object(L, 'status', lambda url, **k: running), mock.patch.object(L, 'pull_stream', pull):
            self.assertTrue(d.local_actions['prepare']())
            self.assertTrue(go.wait(5))
            self.assertFalse(d.local_tier.isEnabled(), 'figé pendant le travail')
            d.local_tier.setCurrentIndex(d.local_tier.findData('ministral-3:3b'))   # changé quand même (code)
            release.set()
            for _i in range(100):
                app.processEvents()
                if 'prêt' in d.local_state.text():
                    break
                time.sleep(0.02)
        self.assertEqual(d.widgets['assistant/modele_local'].text(), 'ministral-3:14b', 'celui qu’on a téléchargé')
        self.assertEqual(d.local_tier.currentData(), 'ministral-3:14b')


if __name__ == '__main__':
    unittest.main()
