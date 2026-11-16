"""Round 1057 : question 42, suite — `VectorDrive --mcp`, le pont « entrée et sortie standard » vers le serveur MCP
local du VectorDrive ouvert (pour Claude Desktop, qui lance lui-même ses serveurs)."""
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import time
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1057.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])
ROOT = pathlib.Path(__file__).resolve().parents[1]
BEFORE = 'avant : pas de pont --mcp, un client qui lance ses serveurs ne peut pas joindre VectorDrive'
KEYS = ('agent/serveur', 'agent/port', 'agent/jeton')
TOKEN = 'jeton-d-essai-0123456789'


def there() -> bool:
    return importlib.util.find_spec('vectordrive.agent.stdio') is not None


def pumped(fn, *a, **k):
    """`fn` dans un autre fil pendant que l'interface tourne (un outil s'exécute dans le fil de l'interface)."""
    box = {}

    def run():
        try:
            box['out'] = fn(*a, **k)
        except Exception as ex:                          # noqa: BLE001 — rendue à l'essai
            box['error'] = ex
    t = threading.Thread(target=run, daemon=True)
    t.start()
    end = time.monotonic() + 150
    while t.is_alive() and time.monotonic() < end:
        app.processEvents()
        time.sleep(0.002)
    if 'error' in box:
        raise box['error']
    assert 'out' in box, 'pas de réponse en 150 s'
    return box['out']


class Other:
    """Un autre logiciel sur un port de cette machine : `reply(handler)` répond à ses POST ; `seen` : les en-têtes
    Authorization reçus."""

    def __init__(self, reply):
        import http.server
        seen = self.seen = []

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_a):
                pass

            def do_POST(self):                           # noqa: N802
                seen.append(self.headers.get('Authorization'))
                self.rfile.read(int(self.headers.get('Content-Length') or 0))
                reply(self)

            do_GET = do_POST                             # noqa: N815
        self.http = http.server.HTTPServer(('127.0.0.1', 0), H)
        self.port = self.http.server_address[1]
        self.url = f'http://127.0.0.1:{self.port}/mcp'
        threading.Thread(target=self.http.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True).start()

    def close(self):
        self.http.shutdown()
        self.http.server_close()


def send(h, code, body=b'', headers=()):
    h.send_response(code)
    for k, v in headers:
        h.send_header(k, v)
    h.send_header('Content-Length', str(len(body)))
    h.end_headers()
    h.wfile.write(body)


def line(method, params=None, msg_id=1) -> str:
    m = {'jsonrpc': '2.0', 'id': msg_id, 'method': method}
    if params is not None:
        m['params'] = params
    return json.dumps(m)


RECT = line('tools/call', {'name': 'add_rectangle', 'arguments': {'x': 0, 'y': 0, 'width': 12, 'height': 6}}, 2)
INIT = line('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {}})


class Offline(unittest.TestCase):
    """VectorDrive fermé ou serveur arrêté : le pont répond lui-même."""

    def setUp(self):
        self.assertTrue(there(), BEFORE)
        from vectordrive.agent.stdio import Bridge
        self.b = Bridge(lambda: ('', ''), '9.9.9')

    def test_the_bridge_answers_alone(self):
        r = json.loads(self.b.handle_line(INIT))['result']
        self.assertEqual(r['serverInfo'], {'name': 'vectordrive', 'title': 'VectorDrive', 'version': '9.9.9'})
        names = [t['name'] for t in json.loads(self.b.handle_line(line('tools/list')))['result']['tools']]
        self.assertIn('add_rectangle', names)                                # l'assistant voit les outils
        r = json.loads(self.b.handle_line(RECT))
        self.assertEqual(r['id'], 2)
        self.assertTrue(r['result']['isError'])
        self.assertIn('not running', r['result']['content'][0]['text'])      # et sait quoi demander
        self.assertIsNone(self.b.handle_line('{"jsonrpc": "2.0", "method": "notifications/initialized"}'))
        self.assertIsNone(self.b.handle_line('   \n'))

    def test_a_closed_port_is_offline_too(self):
        from vectordrive.agent.stdio import Bridge
        import socket
        s = socket.socket()
        s.bind(('127.0.0.1', 0))                                             # pris, mais personne n'écoute
        self.addCleanup(s.close)
        port = s.getsockname()[1]
        b = Bridge(lambda: (f'http://127.0.0.1:{port}/mcp', TOKEN), '9.9.9')
        self.assertTrue(json.loads(b.handle_line(RECT))['result']['isError'])
        self.assertEqual(json.loads(b.handle_line(INIT))['result']['serverInfo']['version'], '9.9.9')

    def other(self, reply):
        from vectordrive.agent.stdio import Bridge
        o = Other(reply)
        self.addCleanup(o.close)
        return o, Bridge(lambda: (o.url, TOKEN), '9.9.9', timeout=20)

    def test_another_program_on_the_port_is_never_copied(self):
        page = b'<html>\n<body>bonjour</body>\n</html>\n'
        for reply in (lambda h: send(h, 200, page, (('Content-Type', 'text/html'),)),
                      lambda h: send(h, 200, b'{"jsonrpc": "2.0", "id": 1, "result": {}}'),      # pas signé
                      lambda h: send(h, 404, b'rien'), lambda h: send(h, 405),
                      lambda h: h.wfile.write(b'pas du HTTP\r\n\r\n')):
            o, b = self.other(reply)
            r = json.loads(b.handle_line(INIT))
            self.assertEqual(r['result']['serverInfo']['version'], '9.9.9')  # la réponse du pont, pas la sienne
            self.assertTrue(json.loads(b.handle_line(RECT))['result']['isError'])
            self.assertEqual(len(o.seen), 2)

    def test_a_redirection_never_carries_the_token_away(self):
        target, _b = self.other(lambda h: send(h, 200, b'{}'))
        for code in (301, 302, 303, 307, 308):
            o, b = self.other(lambda h, c=code: send(h, c, b'', (('Location', target.url),)))
            self.assertEqual(json.loads(b.handle_line(INIT))['result']['serverInfo']['version'], '9.9.9')
        self.assertEqual(target.seen, [])                                    # jamais suivie

    def test_no_answer_in_time_is_not_taken_for_closed(self):
        import socket
        from vectordrive.agent.stdio import Bridge
        s = socket.socket()
        s.bind(('127.0.0.1', 0))
        s.listen(1)                                                          # la connexion se fait, rien ne répond
        self.addCleanup(s.close)
        b = Bridge(lambda: (f'http://127.0.0.1:{s.getsockname()[1]}/mcp', TOKEN), '9.9.9', timeout=0.5)
        r = json.loads(b.handle_line(RECT))
        self.assertEqual(r['id'], 2)
        self.assertIn('did not answer in time', r['error']['message'])       # peut-être fait : à relire avant de refaire

    def test_nothing_stops_the_bridge(self):
        from vectordrive.agent.stdio import serve
        odd = ['{pas du json', '{"jsonrpc": "2.0", "id": 3, "method": "\\ud800"}',
               json.dumps({'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {'name': 'a\ud800'}}),
               '[]', '[' * 5000, line('ping', msg_id=9)]
        out = io.BytesIO()
        self.assertEqual(serve(io.BytesIO(('\n'.join(odd) + '\n').encode('utf-8', 'surrogatepass')), out, self.b), 0)
        lines = out.getvalue().decode('ascii').splitlines()                  # tout en ASCII, une réponse par ligne
        self.assertEqual(json.loads(lines[-1]), {'jsonrpc': '2.0', 'id': 9, 'result': {}})
        for x in lines:
            json.loads(x)

    def test_lines_in_lines_out(self):
        from vectordrive.agent.stdio import serve
        data = (INIT + '\n' + '{"jsonrpc": "2.0", "method": "notifications/initialized"}\n' + '\n'
                + line('ping', msg_id=7) + '\n').encode('utf-8')
        out = io.BytesIO()
        self.assertEqual(serve(io.BytesIO(data), out, self.b), 0)
        lines = out.getvalue().decode('utf-8').splitlines()
        self.assertEqual([json.loads(x)['id'] for x in lines], [1, 7])       # une ligne par demande, rien d'autre

    def test_the_launcher_has_the_option(self):
        spec = importlib.util.spec_from_file_location('vectordrive_main_1057', ROOT / 'VectorDrive.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(mod.make_parser().parse_args(['--mcp']).mcp)


class Online(unittest.TestCase):

    def setUp(self):
        self.assertTrue(there(), BEFORE)
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.addCleanup(self.clean)
        self.srv = self.w.agent_server()
        self.port = self.srv.start(0, TOKEN)

    def clean(self):
        self.srv.stop()
        for k in KEYS:
            self.w.settings.remove(k)
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()

    def items(self):
        return [it for L in self.w.canvas.doc.layers for it in L.items]

    def bridge(self, token=TOKEN):
        from vectordrive.agent.stdio import Bridge
        return Bridge(lambda: (self.srv.url, token), '9.9.9')

    def test_messages_reach_the_open_window(self):
        b = self.bridge()
        import vectordrive
        r = json.loads(b.handle_line(INIT))['result']
        self.assertEqual(r['serverInfo']['version'], vectordrive.__version__)   # la réponse de la fenêtre, pas du pont
        n = len(self.items())
        r = json.loads(pumped(b.handle_line, RECT))
        self.assertFalse(r['result']['isError'])
        self.assertEqual(len(self.items()), n + 1)
        self.assertIsNone(b.handle_line('{"jsonrpc": "2.0", "method": "notifications/initialized"}'))

    def test_a_renewed_token_is_said(self):
        r = json.loads(self.bridge('ancien-jeton-0123456789').handle_line(line('ping', msg_id=5)))
        self.assertEqual(r['id'], 5)
        self.assertIn('token', r['error']['message'])

    def test_the_settings_tell_where_the_server_is(self):
        from vectordrive.agent import stdio
        st = self.w.settings
        st.remove('agent/jeton')
        st.sync()
        self.assertEqual(stdio.locate(), ('', ''))                           # jamais lancé : rien à joindre
        st.setValue('agent/port', self.port)
        st.setValue('agent/jeton', TOKEN)
        st.sync()
        self.assertEqual(stdio.locate(), ('', ''))                           # serveur pas demandé : rien n'est envoyé
        st.setValue('agent/serveur', True)
        st.sync()
        self.assertEqual(stdio.locate(), (f'http://127.0.0.1:{self.port}/mcp', TOKEN))
        from unittest import mock
        from vectordrive import portable
        with mock.patch.object(portable, 'settings', return_value=st) as asked:
            stdio.locate()
        asked.assert_called_once_with(migrate=False)                         # lus sans rien reprendre ni écrire

    def test_the_command_bridges_a_client_to_the_window(self):
        ini = os.path.join(tempfile.mkdtemp(), 'pont.ini')
        st = QSettings(ini, QSettings.Format.IniFormat)
        st.setValue('agent/serveur', True)
        st.setValue('agent/port', self.port)
        st.setValue('agent/jeton', TOKEN)
        st.sync()
        env = dict(os.environ, VECTORDRIVE_SETTINGS=ini)
        n = len(self.items())
        data = (INIT + '\n' + RECT + '\n').encode('utf-8')
        done = pumped(subprocess.run, [sys.executable, str(ROOT / 'VectorDrive.py'), '--mcp'], input=data,
                      capture_output=True, env=env, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        lines = done.stdout.decode('utf-8').splitlines()
        self.assertEqual(len(lines), 2, done.stdout[-400:])                  # deux demandes, deux lignes, rien d'autre
        self.assertEqual(json.loads(lines[0])['result']['serverInfo']['name'], 'vectordrive')
        self.assertFalse(json.loads(lines[1])['result']['isError'])
        self.assertEqual(len(self.items()), n + 1)                           # dessiné dans la fenêtre ouverte

    def test_the_dialog_gives_the_claude_desktop_entry(self):
        dlg = self.w.agent_dialog(exec_dialog=False)
        self.addCleanup(dlg.deleteLater)
        entry = json.loads(dlg.desktop.text())['mcpServers']['vectordrive']
        self.assertEqual(entry['args'][-1], '--mcp')
        self.assertTrue(os.path.isfile(entry['command']))
        self.assertTrue(os.path.isfile(entry['args'][0]))                    # hors exécutable : Python et le lanceur


if __name__ == '__main__':
    unittest.main()
