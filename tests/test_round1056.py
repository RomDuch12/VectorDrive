"""Round 1056 : demande du 15/11 (question 42 : « queue serveur MCP ») — un assistant se branche sur le dessin ouvert
par le protocole MCP : les messages, les outils de dessin (un pas d'annulation chacun), le serveur HTTP local et la
fenêtre « Assistant (serveur MCP) »."""
import base64
import http.client
import importlib.util
import json
import os
import socket
import tempfile
import threading
import time
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1056.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : aucun assistant ne peut se brancher sur le dessin'
KEYS = ('agent/serveur', 'agent/port', 'agent/jeton')


def there() -> bool:
    return importlib.util.find_spec('vectordrive.agent') is not None


def free_port() -> int:
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def post(port, token, payload, headers=None, method='POST', path='/mcp'):
    """Une demande HTTP au serveur local : (code, JSON rendu ou None)."""
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=20)
    h = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}
    if token:
        h['Authorization'] = 'Bearer ' + token
    h.update(headers or {})
    c.request(method, path, body=json.dumps(payload).encode('utf-8') if payload is not None else None, headers=h)
    r = c.getresponse()
    data = r.read()
    c.close()
    return r.status, (json.loads(data) if data else None)


def pumped(fn, *a, **k):
    """`fn` dans un autre fil pendant que l'interface tourne (un outil appelé par HTTP s'exécute dans son fil)."""
    box = {}

    def run():
        try:
            box['out'] = fn(*a, **k)
        except Exception as ex:                          # noqa: BLE001 — rendue à l'essai
            box['error'] = ex
    t = threading.Thread(target=run, daemon=True)
    t.start()
    end = time.monotonic() + 30
    while t.is_alive() and time.monotonic() < end:
        app.processEvents()
        time.sleep(0.002)
    if 'error' in box:
        raise box['error']
    assert 'out' in box, 'pas de réponse en 30 s'
    return box['out']


def rpc(method, params=None, msg_id=1):
    m = {'jsonrpc': '2.0', 'id': msg_id, 'method': method}
    if params is not None:
        m['params'] = params
    return m


class FakeTools:
    """Deux outils sans fenêtre, pour le protocole seul."""

    def specs(self):
        return [{'name': 'echo', 'description': 'd', 'inputSchema': {'type': 'object', 'properties': {}}}]

    def call(self, name, arguments):
        from vectordrive.agent.protocol import ToolError, text_content
        if name == 'echo':
            return [text_content(arguments)]
        if name == 'refuse':
            raise ToolError('no such object')
        raise KeyError(name)


class Protocol(unittest.TestCase):

    def setUp(self):
        self.assertTrue(there(), BEFORE)
        from vectordrive.agent.protocol import Server
        self.s = Server(FakeTools(), '9.9.9')

    def test_initialize_ping_and_list(self):
        r = self.s.handle(rpc('initialize', {'protocolVersion': '2025-03-26', 'capabilities': {}}))['result']
        self.assertEqual(r['protocolVersion'], '2025-03-26')                 # la version demandée, comprise
        self.assertEqual(r['serverInfo']['name'], 'vectordrive')
        self.assertEqual(r['serverInfo']['version'], '9.9.9')
        self.assertIn('tools', r['capabilities'])
        self.assertIn('millimetres', r['instructions'])
        r = self.s.handle(rpc('initialize', {'protocolVersion': '1999-01-01'}))['result']
        self.assertEqual(r['protocolVersion'], '2025-06-18')                 # inconnue : la plus récente est proposée
        self.assertEqual(self.s.handle(rpc('ping', msg_id='a')), {'jsonrpc': '2.0', 'id': 'a', 'result': {}})
        self.assertEqual(self.s.handle(rpc('tools/list'))['result']['tools'][0]['name'], 'echo')

    def test_notifications_errors_and_batches(self):
        self.assertIsNone(self.s.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'}))
        self.assertTrue(self.s.initialized)
        self.assertEqual(self.s.handle(rpc('no/such'))['error']['code'], -32601)
        self.assertEqual(self.s.handle({'id': 1, 'method': 'ping'})['error']['code'], -32600)
        self.assertEqual(json.loads(self.s.handle_text('{pas du json'))['error']['code'], -32700)
        self.assertIsNone(self.s.handle_text('{"jsonrpc": "2.0", "method": "notifications/cancelled"}'))
        out = self.s.handle([rpc('ping', msg_id=1), {'jsonrpc': '2.0', 'method': 'x'}, rpc('ping', msg_id=2)])
        self.assertEqual([m['id'] for m in out], [1, 2])                     # la notification du lot : sans réponse

    def test_tool_calls(self):
        r = self.s.handle(rpc('tools/call', {'name': 'echo', 'arguments': {'a': 1}}))['result']
        self.assertFalse(r['isError'])
        self.assertEqual(json.loads(r['content'][0]['text']), {'a': 1})
        r = self.s.handle(rpc('tools/call', {'name': 'refuse'}))['result']
        self.assertTrue(r['isError'])                                        # un refus est dit au modèle…
        self.assertIn('no such object', r['content'][0]['text'])
        r = self.s.handle(rpc('tools/call', {'name': 'absent'}))
        self.assertEqual(r['error']['code'], -32602)                         # …un outil inconnu est une erreur


class WithWindow(unittest.TestCase):

    def setUp(self):
        self.assertTrue(there(), BEFORE)
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.addCleanup(self.clean)
        from vectordrive.agent.tools import ToolSet
        self.tools = ToolSet(self.w)

    def clean(self):
        srv = getattr(self.w, '_agent_server', None)
        if srv is not None:
            srv.stop()
        for k in KEYS:
            self.w.settings.remove(k)
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()

    def call(self, name, **args):
        return json.loads(self.tools.call(name, args)[0]['text'])

    def refused(self, name, **args):
        from vectordrive.agent.protocol import ToolError
        with self.assertRaises(ToolError) as cm:
            self.tools.call(name, args)
        return str(cm.exception)

    def items(self):
        return [it for L in self.w.canvas.doc.layers for it in L.items]

    def steps(self):
        return len(self.w._undo)

    def serve(self) -> int:
        """Le réglage lance le serveur sur un port libre ; rend le port (pris entre-temps par un essai voisin : un
        autre)."""
        for _ in range(8):
            port = free_port()
            self.w.settings.setValue('agent/port', port)
            if self.w.agent_sync(True) == '':
                return port
        self.fail('aucun port libre')


class Drawing(WithWindow):

    def test_every_tool_is_listed_with_a_schema(self):
        specs = {s['name']: s for s in self.tools.specs()}
        for name in ('get_document', 'list_objects', 'get_object', 'add_rectangle', 'add_ellipse', 'add_polygon',
                     'add_polyline', 'add_text', 'move_objects', 'rotate_objects', 'scale_objects', 'delete_objects',
                     'boolean', 'select_objects', 'capture', 'undo'):
            self.assertIn(name, specs)
            self.assertEqual(specs[name]['inputSchema']['type'], 'object')
            self.assertTrue(specs[name]['description'])
        self.assertTrue(specs['list_objects']['annotations']['readOnlyHint'])
        self.assertFalse(specs['add_rectangle']['annotations']['readOnlyHint'])
        with self.assertRaises(KeyError):
            self.tools.call('absent', {})

    def test_a_rectangle_is_drawn_selected_and_one_undo_step(self):
        n, steps = len(self.items()), self.steps()
        out = self.call('add_rectangle', x=10, y=20, width=40, height=30)
        self.assertEqual(len(self.items()), n + 1)
        it = self.items()[-1]
        self.assertEqual(out['ids'], [it.id])
        self.assertEqual(out['bbox'], [10.0, 20.0, 50.0, 50.0])
        self.assertEqual([x.id for x in self.w.canvas.selection], [it.id])
        self.assertEqual(self.steps(), steps + 1)                            # un pas, comme une commande
        doc = self.call('get_document')
        self.assertEqual(doc['objects'], n + 1)
        self.assertEqual(doc['selection'], [it.id])
        self.assertEqual(doc['units'], 'mm')
        self.w.undo()
        self.assertEqual(len(self.items()), n)                               # Ctrl+Z le défait

    def test_shapes_and_text_are_listed_and_read(self):
        a = self.call('add_ellipse', cx=0, cy=0, rx=10, ry=5)['ids'][0]
        b = self.call('add_polygon', cx=50, cy=0, radius=10, sides=6)['ids'][0]
        c = self.call('add_polyline', points=[[0, 0], [10, 0], [10, 10]], closed=True)['ids'][0]
        t = self.call('add_text', text='ABC 12', x=5, y=60, size=8)['ids'][0]
        rows = {r['id']: r for r in self.call('list_objects')['objects']}
        self.assertEqual([rows[i]['type'] for i in (a, b, c, t)], ['shape', 'shape', 'shape', 'text'])
        self.assertEqual(rows[t]['text'], 'ABC 12')
        self.assertEqual(rows[a]['bbox'], [-10.0, -5.0, 10.0, 5.0])
        got = self.call('get_object', id=c)
        self.assertTrue(got['contours'][0]['closed'])
        self.assertEqual(got['contours'][0]['points'][:3], [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]])
        got = self.call('get_object', id=t)
        self.assertEqual((got['text'], got['size'], got['x'], got['y']), ('ABC 12', 8.0, 5.0, 60.0))
        self.assertEqual(len(self.call('get_object', id=b)['contours'][0]['points']) >= 6, True)

    def test_move_rotate_scale_keep_the_objects(self):
        i = self.call('add_rectangle', x=0, y=0, width=20, height=10)['ids'][0]
        steps = self.steps()
        out = self.call('move_objects', ids=[i], dx=5, dy=-5)
        self.assertEqual((out['ids'], out['bbox']), ([i], [5.0, -5.0, 25.0, 5.0]))
        out = self.call('rotate_objects', ids=[i], angle=90)                 # autour de son centre
        self.assertEqual(out['bbox'], [10.0, -10.0, 20.0, 10.0])
        out = self.call('scale_objects', ids=[i], sx=2, cx=10, cy=-10)
        self.assertEqual(out['bbox'], [10.0, -10.0, 30.0, 30.0])
        self.assertEqual(self.steps(), steps + 3)
        self.assertEqual([x.id for x in self.items()].count(i), 1)           # le même objet, pas une copie
        self.w.undo()
        self.assertEqual(self.call('list_objects')['objects'][-1]['bbox'], [10.0, -10.0, 20.0, 10.0])

    def test_boolean_replaces_the_shapes(self):
        a = self.call('add_rectangle', x=0, y=0, width=20, height=20)['ids'][0]
        b = self.call('add_rectangle', x=10, y=10, width=20, height=20)['ids'][0]
        c = self.call('add_rectangle', x=90, y=90, width=5, height=5)['ids'][0]
        n, steps = len(self.items()), self.steps()
        out = self.call('boolean', operation='union', ids=[b, a])
        self.assertEqual(len(self.items()), n - 1)
        self.assertEqual(out['bbox'], [0.0, 0.0, 30.0, 30.0])
        self.assertEqual(self.steps(), steps + 1)
        self.assertEqual([x.id for x in self.items()][-2:], [out['ids'][0], c])   # à la place de la première nommée
        self.w.undo()
        self.assertEqual(len(self.items()), n)
        ids = [r['id'] for r in self.call('list_objects')['objects']][-3:-1]
        out = self.call('boolean', operation='difference', ids=ids)          # la première moins l'autre
        self.assertEqual(out['bbox'], [0.0, 0.0, 20.0, 20.0])
        from vectordrive.core import pathops
        self.assertAlmostEqual(abs(pathops.area(self.items()[-2].path)), 300.0, places=3)

    def test_delete_and_select(self):
        a = self.call('add_rectangle', x=0, y=0, width=5, height=5)['ids'][0]
        b = self.call('add_rectangle', x=9, y=0, width=5, height=5)['ids'][0]
        self.assertEqual(self.call('select_objects', ids=[a])['selected'], 1)
        self.assertEqual([x.id for x in self.w.canvas.selection], [a])
        self.assertEqual(self.call('select_objects', ids=[])['selected'], 0)
        n = len(self.items())
        self.assertEqual(self.call('delete_objects', ids=[a, b])['deleted'], 2)
        self.assertEqual(len(self.items()), n - 2)
        self.call('undo')                                                    # l'outil « undo » : un pas de la fenêtre
        self.assertEqual(len(self.items()), n)

    def test_a_refusal_changes_nothing_and_leaves_no_undo_step(self):
        i = self.call('add_rectangle', x=0, y=0, width=5, height=5)['ids'][0]
        n, steps = len(self.items()), self.steps()
        self.assertIn('width', self.refused('add_rectangle', x=0, y=0, width=-1, height=5))
        self.assertIn('unknown argument', self.refused('add_rectangle', x=0, y=0, width=1, height=5, colour='red'))
        self.assertIn('missing argument', self.refused('add_rectangle', x=0, y=0))
        self.assertIn('no object', self.refused('move_objects', ids=['absent'], dx=1, dy=1))
        self.assertIn('two shapes', self.refused('boolean', operation='union', ids=[i]))
        self.assertIn('number', self.refused('move_objects', ids=[i], dx='1', dy=0))
        self.assertIn('no object', self.refused('delete_objects', ids=[i, 'absent']))   # un seul absent : rien n'est fait
        for bad in (float('nan'), float('inf'), 1e300, True, '3'):
            self.assertIn('number', self.refused('add_polyline', points=[[0, 0], [bad, 5]]), bad)
        self.assertIn('different', self.refused('add_polyline', points=[[1, 1], [1, 1], [1, 1]]))
        self.assertIn('number', self.refused('add_rectangle', x=1e300, y=0, width=1e300, height=5))
        self.assertIn('invalid character', self.refused('add_text', text='a\ud83d', x=0, y=0))
        self.assertIn('not installed', self.refused('add_text', text='a', x=0, y=0, font='Police Absente 1056'))
        self.assertIn('integer', self.refused('list_objects', limit=-3))
        self.assertIn('integer', self.refused('capture', width=0))
        self.assertIn('tolerance', self.refused('get_object', id=i, tolerance=1e-9))
        self.items()[-1].locked = True
        self.assertIn('locked', self.refused('delete_objects', ids=[i]))     # un objet gelé n'est pas touché
        self.assertEqual(self.call('select_objects', ids=[i])['selected'], 0)   # ni sélectionné
        self.w.canvas.doc.active_layer.locked = True
        self.assertIn('locked', self.refused('add_rectangle', x=0, y=0, width=5, height=5))   # ni un calque verrouillé
        self.w.canvas.doc.active_layer.locked = False
        self.assertEqual((len(self.items()), self.steps()), (n, steps))

    def test_a_big_shape_is_thinned_and_says_so(self):
        i = self.call('add_polyline', points=[[k, (k * 7) % 13] for k in range(400)])['ids'][0]
        j = self.call('add_ellipse', cx=0, cy=0, rx=30, ry=30)['ids'][0]
        self.call('boolean', operation='union', ids=[j, self.call('add_ellipse', cx=200, cy=0, rx=30, ry=30)['ids'][0]])
        got = self.call('get_object', id=i, max_points=50)
        pts = got['contours'][0]['points']
        self.assertTrue(got['truncated'])
        self.assertEqual(got['points_total'], 400)
        self.assertLessEqual(len(pts), 50)
        self.assertEqual((pts[0], pts[-1]), ([0.0, 0.0], [399.0, 11.0]))     # les bouts gardés
        self.assertNotIn('truncated', self.call('get_object', id=i, max_points=2000))
        two = self.call('get_object', id=self.items()[-1].id, max_points=20)   # deux contours : chacun sa part
        self.assertEqual(two['contours_total'], 2)
        self.assertTrue(all(3 <= len(c['points']) <= 20 for c in two['contours']), two)

    def test_a_child_of_a_group_is_read_but_not_moved_alone(self):
        from vectordrive.core import geom
        from vectordrive.core.document import Group, Shape
        inner = Shape(path=geom.Path([geom.rect(0, 0, 4, 4)]))
        g = Group(children=[Group(children=[inner])])
        self.w.canvas.doc.add(g)
        self.assertEqual(self.call('get_object', id=inner.id)['bbox'], [0.0, 0.0, 4.0, 4.0])
        self.assertEqual(self.call('get_object', id=g.id)['children'][0]['type'], 'group')
        self.assertIn('inside a group', self.refused('move_objects', ids=[inner.id], dx=1, dy=1))
        self.assertEqual(self.call('move_objects', ids=[g.id], dx=1, dy=1)['bbox'], [1.0, 1.0, 5.0, 5.0])

    def test_an_odd_character_does_not_break_the_reply(self):
        from vectordrive.agent.protocol import Server
        from vectordrive.core.document import Text
        self.w.canvas.doc.add(Text(text='a\ud83d', size=5))                  # venu d'un fichier, pas d'un outil
        out = Server(self.tools, '0').handle_text(json.dumps(rpc('tools/call', {'name': 'list_objects'})))
        out.encode('utf-8')                                                  # la réponse s'écrit
        self.assertFalse(json.loads(out)['result']['isError'])

    def test_capture_is_a_png(self):
        self.call('add_rectangle', x=0, y=0, width=40, height=20)
        out = self.tools.call('capture', {'width': 320})
        self.assertEqual((out[0]['type'], out[0]['mimeType']), ('image', 'image/png'))
        self.assertEqual(base64.b64decode(out[0]['data'])[:8], b'\x89PNG\r\n\x1a\n')


class LocalHttp(WithWindow):

    def setUp(self):
        super().setUp()
        self.srv = self.w.agent_server()
        self.port = self.srv.start(0, 'jeton-d-essai-0123456789')
        self.token = self.srv.token

    def test_guards(self):
        ok = rpc('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {}})
        code, out = post(self.port, self.token, ok)
        self.assertEqual(code, 200)
        self.assertEqual(out['result']['serverInfo']['name'], 'vectordrive')
        self.assertEqual(post(self.port, None, ok)[0], 401)                  # sans jeton
        self.assertEqual(post(self.port, 'autre', ok)[0], 401)
        self.assertEqual(post(self.port, self.token, ok, {'Host': 'exemple.test'})[0], 403)   # nom détourné
        self.assertEqual(post(self.port, self.token, ok, {'Origin': 'https://exemple.test'})[0], 403)   # page web
        self.assertEqual(post(self.port, self.token, ok, path='/autre')[0], 404)
        self.assertEqual(post(self.port, self.token, ok, {'MCP-Protocol-Version': '1999-01-01'})[0], 400)
        self.assertEqual(post(self.port, self.token, None, method='GET')[0], 405)             # pas de flux
        code, out = post(self.port, self.token, {'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        self.assertEqual((code, out), (202, None))
        self.assertEqual(self.srv.url, f'http://127.0.0.1:{self.port}/mcp')
        self.assertEqual(post(self.port, self.token, ok, {'Host': f'localhost:{self.port}'})[0], 200)
        self.assertEqual(post(self.port, self.token, ok, {'Origin': f'http://127.0.0.1:{self.port}'})[0], 200)
        self.assertEqual(post(self.port, self.token.upper(), ok)[0], 401)

    def test_a_tool_is_refused_in_the_middle_of_something(self):
        from PySide6.QtWidgets import QDialog
        msg = rpc('tools/call', {'name': 'add_rectangle', 'arguments': {'x': 1, 'y': 2, 'width': 30, 'height': 10}})
        n, steps = len(self.items()), self.steps()
        dlg = QDialog(self.w)
        dlg.setModal(True)
        dlg.show()
        app.processEvents()
        self.assertIs(QApplication.activeModalWidget(), dlg)
        code, out = pumped(post, self.port, self.token, msg)
        self.assertTrue(out['result']['isError'])                            # une fenêtre modale est ouverte
        self.assertIn('dialog', out['result']['content'][0]['text'])
        dlg.close()
        dlg.deleteLater()
        app.processEvents()
        self.srv.bridge.closed = True                                        # la fenêtre se ferme
        code, out = pumped(post, self.port, self.token, msg)
        self.assertIn('closing', out['result']['content'][0]['text'])
        self.assertEqual((len(self.items()), self.steps()), (n, steps))
        self.srv.bridge.closed = False
        code, out = pumped(post, self.port, self.token, msg)
        self.assertFalse(out['result']['isError'])
        self.assertEqual(self.srv.bridge.busy(), '')

    def test_a_tool_called_over_http_draws_in_the_window(self):
        n, steps = len(self.items()), self.steps()
        code, out = post(self.port, self.token, rpc('tools/list'))
        self.assertIn('add_rectangle', [t['name'] for t in out['result']['tools']])
        msg = rpc('tools/call', {'name': 'add_rectangle', 'arguments': {'x': 1, 'y': 2, 'width': 30, 'height': 10}})
        code, out = pumped(post, self.port, self.token, msg)
        self.assertEqual(code, 200)
        self.assertFalse(out['result']['isError'])
        self.assertEqual(json.loads(out['result']['content'][0]['text'])['bbox'], [1.0, 2.0, 31.0, 12.0])
        self.assertEqual((len(self.items()), self.steps()), (n + 1, steps + 1))
        bad = rpc('tools/call', {'name': 'move_objects', 'arguments': {'ids': ['absent'], 'dx': 1, 'dy': 1}})
        code, out = pumped(post, self.port, self.token, bad)
        self.assertTrue(out['result']['isError'])                            # dit au modèle, rien de changé
        self.assertEqual((len(self.items()), self.steps()), (n + 1, steps + 1))

    def test_stopped_server_answers_no_more(self):
        self.srv.stop()
        self.assertFalse(self.srv.running)
        with self.assertRaises(OSError):
            post(self.port, self.token, rpc('ping'))


class Window(WithWindow):

    def test_the_setting_starts_and_stops_the_server(self):
        self.assertIsNone(getattr(self.w, '_agent_server', None))            # rien de lancé d'office
        port = self.serve()
        srv = self.w._agent_server
        self.assertTrue(srv.running)
        self.assertEqual(srv.port, port)
        token = str(self.w.settings.value('agent/jeton'))
        self.assertGreaterEqual(len(token), 16)                              # fait une fois, retenu
        self.assertEqual(post(port, token, rpc('ping'))[0], 200)
        self.w.apply_options()                                               # ne le relance pas
        self.assertIs(self.w._agent_server, srv)
        self.assertEqual(str(self.w.settings.value('agent/jeton')), token)
        self.w.agent_sync(False)
        self.assertFalse(srv.running)
        self.assertNotIn(self.w.settings.value('agent/serveur'), (True, 'true'))

    def test_a_taken_port_is_said(self):
        busy = socket.socket()
        busy.bind(('127.0.0.1', 0))
        busy.listen(1)
        self.addCleanup(busy.close)
        self.w.settings.setValue('agent/port', busy.getsockname()[1])
        why = self.w.agent_sync(True)
        self.assertIn(str(busy.getsockname()[1]), why)
        self.assertFalse(self.w._agent_server.running)

    def test_the_dialog_gives_what_a_client_needs(self):
        dlg = self.w.agent_dialog(exec_dialog=False)
        self.addCleanup(dlg.deleteLater)
        self.assertFalse(dlg.on.isChecked())                                 # décochée d'office
        self.assertEqual(dlg.state.text(), 'Arrêté')
        dlg.close()
        port = self.serve()
        dlg = self.w.agent_dialog(exec_dialog=False)
        self.addCleanup(dlg.deleteLater)
        self.assertTrue(dlg.on.isChecked())
        srv = self.w._agent_server
        self.assertTrue(srv.running)
        token = srv.token
        self.assertEqual(dlg.url.text(), f'http://127.0.0.1:{port}/mcp')
        self.assertEqual(dlg.header.text(), 'Authorization: Bearer ' + token)
        cmd = dlg.command.text()
        self.assertTrue(cmd.startswith('claude mcp add --transport http '))
        self.assertIn(f'http://127.0.0.1:{port}/mcp', cmd)
        self.assertIn(f'--header "Authorization: Bearer {token}"', cmd)
        self.assertIn(str(port), dlg.state.text())
        new = dlg.renew_token()                                              # l'ancien jeton ne marche plus
        self.assertNotEqual(new, token)
        self.assertEqual(post(port, token, rpc('ping'))[0], 401)
        self.assertEqual(post(port, new, rpc('ping'))[0], 200)
        dlg.on.setChecked(False)                                             # la case arrête et lance le serveur
        self.assertFalse(srv.running)
        self.assertEqual(dlg.state.text(), 'Arrêté')
        dlg.on.setChecked(True)
        self.assertTrue(srv.running or str(port) in dlg.state.text())        # relancé (ou port pris entre-temps : dit)

    def test_closing_the_window_stops_the_server(self):
        self.serve()
        srv = self.w._agent_server
        self.w.modified = False
        self.w.close()
        self.assertFalse(srv.running)

    def test_the_options_have_the_button(self):
        dlg = self.w.options_dialog(exec_dialog=False)
        self.addCleanup(dlg.deleteLater)
        self.assertIn('MCP', dlg.agent_button.text())


if __name__ == '__main__':
    unittest.main()
