"""Round 1069 : demande du 17/11 — « prio assistant ia Claude inapp (chercher aussi une compatibilité Mistral et
chatGPT) ». Le panneau « Assistant IA » : une discussion avec Claude (SDK anthropic, en flux), ChatGPT (SDK openai,
API Responses) ou Mistral (chat completions en HTTP), qui agissent sur le dessin avec les outils de l'assistant.
Aucun appel réel : des clients simulés ; aucune clé du poste (gestionnaire d'identifiants jamais touché)."""
import importlib.util
import json
import os
import tempfile
import unittest
from types import SimpleNamespace as NS

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1069.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ['VECTORDRIVE_KEYS_MEMORY'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : pas d’assistant IA dans l’application'


def there() -> bool:
    return importlib.util.find_spec('vectordrive.agent.chat') is not None


class FakeTools:
    """Deux outils : `add` rend un id, `pic` une image ; `bad` refuse ; tout appel est noté."""

    def __init__(self):
        self.calls = []

    def specs(self):
        sch = {'type': 'object', 'properties': {'w': {'type': 'number'}}, 'required': [], 'additionalProperties': False}
        return [{'name': n, 'description': f'tool {n}', 'inputSchema': sch, 'annotations': {}}
                for n in ('add', 'pic', 'bad')]

    def call(self, name, args):
        from vectordrive.agent.protocol import ToolError
        self.calls.append((name, args))
        if name == 'bad':
            raise ToolError('a dialog is open')
        if name == 'pic':
            return [{'type': 'image', 'data': 'QUJD', 'mimeType': 'image/png'}]
        if name not in ('add',):
            raise KeyError(name)
        return [{'type': 'text', 'text': '{"id": "o1"}'}]


# --- Anthropic simulé : messages.stream(...) ------------------------------------------------------------
def block(kind, **kw):
    return NS(type=kind, **kw)


class FakeStream:
    def __init__(self, msg, chunks):
        self.msg, self.chunks = msg, chunks

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        for c in self.chunks:
            yield NS(type='text', text=c)

    def get_final_message(self):
        return self.msg


class FakeAnthropic:
    def __init__(self, turns):
        self.turns = list(turns)                         # [(contenu, stop_reason)]
        self.requests = []
        self.messages = self

    def stream(self, **kw):
        self.requests.append({**kw, 'messages': list(kw['messages'])})
        content, stop = self.turns.pop(0)
        chunks = [b.text for b in content if b.type == 'text']
        return FakeStream(NS(content=content, stop_reason=stop), chunks)


# --- OpenAI simulé : responses.create(...) ---------------------------------------------------------------
class FakeOpenAI:
    def __init__(self, turns):
        self.turns = list(turns)                         # [(texte, [(call_id, nom, arguments)])]
        self.requests = []
        self.responses = self

    def create(self, **kw):
        self.requests.append(kw)
        text, calls = self.turns.pop(0)
        out = [NS(type='function_call', call_id=c, name=n, arguments=a) for c, n, a in calls]
        return NS(id=f'resp_{len(self.requests)}', output=out, output_text=text, status='completed')


class FakeMistral:
    def __init__(self, turns):
        self.turns = list(turns)
        self.requests = []

    def __call__(self, body):
        self.requests.append(json.loads(json.dumps(body)))
        return self.turns.pop(0)


def conv(provider, client, tools=None, **kw):
    from vectordrive.agent.chat import Conversation
    seen = {'text': [], 'tools': []}
    c = Conversation(provider, '', 'cle-d-essai', tools or FakeTools(), client=client,
                     on_text=seen['text'].append, on_tool=lambda *a: seen['tools'].append(a), **kw)
    return c, seen


class Claude(unittest.TestCase):

    def setUp(self):
        self.assertTrue(there(), BEFORE)

    def test_tool_round_trip(self):
        """Un outil demandé, exécuté, son résultat rendu avec l'id de l'appel ; le texte en flux ; la requête : le
        modèle d'office, le système, les outils (schéma, entrées en flux), le cache."""
        from vectordrive.agent.chat import SYSTEM
        fake = FakeAnthropic([
            ([block('text', text='Je dessine.'), block('tool_use', id='tu1', name='add', input={'w': 4})], 'tool_use'),
            ([block('text', text='Fait : 4 mm.')], 'end_turn')])
        tools = FakeTools()
        c, seen = conv('anthropic', fake, tools)
        self.assertEqual(c.send('un carré'), 'Je dessine.\nFait : 4 mm.')
        self.assertEqual(tools.calls, [('add', {'w': 4})])
        self.assertEqual(seen['text'], ['Je dessine.', 'Fait : 4 mm.'])
        r0, r1 = fake.requests
        self.assertEqual(r0['model'], 'claude-opus-5-5')
        self.assertEqual(r0['system'], SYSTEM)
        self.assertEqual(r0['cache_control'], {'type': 'ephemeral'})
        self.assertEqual([t['name'] for t in r0['tools']], ['add', 'pic', 'bad'])
        self.assertTrue(all(t['eager_input_streaming'] and t['input_schema']['type'] == 'object' for t in r0['tools']))
        self.assertEqual(r0['messages'], [{'role': 'user', 'content': 'un carré'}])
        self.assertEqual([m['role'] for m in r1['messages']], ['user', 'assistant', 'user'])
        res = r1['messages'][2]['content'][0]
        self.assertEqual((res['type'], res['tool_use_id'], res['is_error']), ('tool_result', 'tu1', False))
        self.assertEqual(res['content'], [{'type': 'text', 'text': '{"id": "o1"}'}])
        self.assertIs(r1['tools'], r0['tools'])                   # outils figés : le cache et le raisonnement tiennent

    def test_errors_and_images(self):
        """Un refus, un outil inconnu, une entrée qui n'est pas un objet : dits au modèle (is_error) ; une image
        rendue en base64."""
        fake = FakeAnthropic([
            ([block('tool_use', id='a', name='bad', input={}), block('tool_use', id='b', name='nope', input={}),
              block('tool_use', id='c', name='add', input='x'), block('tool_use', id='d', name='pic', input={})],
             'tool_use'),
            ([block('text', text='ok')], 'end_turn')])
        c, seen = conv('anthropic', fake)
        c.send('essai')
        res = fake.requests[1]['messages'][2]['content']
        self.assertEqual([r['is_error'] for r in res], [True, True, True, False])
        self.assertIn('a dialog is open', res[0]['content'][0]['text'])
        self.assertIn('unknown tool', res[1]['content'][0]['text'])
        self.assertEqual(res[3]['content'], [{'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png',
                                                                          'data': 'QUJD'}}])
        self.assertEqual(len(seen['tools']), 4)

    def test_cut_input_not_run(self):
        """Coupé par max_tokens au milieu d'un appel : l'outil n'est pas exécuté."""
        fake = FakeAnthropic([([block('tool_use', id='a', name='add', input={'w': 1})], 'max_tokens')])
        tools = FakeTools()
        c, _seen = conv('anthropic', fake, tools)
        self.assertIn('coupée', c.send('long'))
        self.assertEqual(tools.calls, [])
        self.assertEqual(c.notes, ['cut'])

    def test_stop_between_tools(self):
        """Arrêté entre deux outils : le second n'est pas exécuté, chaque appel a sa réponse ; la demande suivante
        s'ajoute au même message (jamais deux messages de l'utilisateur de suite)."""
        from vectordrive.agent.chat import Stopped
        fake = FakeAnthropic([
            ([block('tool_use', id='a', name='add', input={}), block('tool_use', id='b', name='add', input={})],
             'tool_use'),
            ([block('text', text='repris')], 'end_turn')])
        tools = FakeTools()
        c, _seen = conv('anthropic', fake, tools)
        c.on_tool = lambda *a: c.stop()                          # arrêt pendant le premier outil
        with self.assertRaises(Stopped):
            c.send('deux')
        self.assertEqual(len(tools.calls), 1)
        last = c._backend.messages[-1]
        self.assertEqual([r['tool_use_id'] for r in last['content']], ['a', 'b'])
        c.on_tool = lambda *a: None
        self.assertEqual(c.send('continue'), 'repris')
        roles = [m['role'] for m in fake.requests[-1]['messages']]
        self.assertEqual(roles, ['user', 'assistant', 'user'])
        self.assertEqual(fake.requests[-1]['messages'][-1]['content'][-1], {'type': 'text', 'text': 'continue'})

    def test_refusal_and_cut_text(self):
        """Refus avec des appels d'outils : aucun exécuté, chacun a sa réponse ; texte coupé : la note « coupée »."""
        fake = FakeAnthropic([
            ([block('tool_use', id='a', name='add', input={})], 'refusal'),
            ([block('text', text='début…')], 'max_tokens')])
        tools = FakeTools()
        c, _seen = conv('anthropic', fake, tools)
        c.send('x')
        self.assertEqual(tools.calls, [])
        self.assertEqual(c._backend.messages[-1]['content'][0]['tool_use_id'], 'a')
        c.send('y')
        self.assertEqual(c.notes, ['cut'])

    def test_types_checked_and_display_failure(self):
        """Une entrée du mauvais type (tronquée en flux, par exemple) est refusée avant l'outil ; un affichage qui
        casse ne casse pas la discussion."""
        fake = FakeAnthropic([
            ([block('tool_use', id='a', name='add', input={'w': 'large'}),
              block('tool_use', id='b', name='add', input={'w': True}),
              block('tool_use', id='c', name='add', input={'w': 2})], 'tool_use'),
            ([block('text', text='ok')], 'end_turn')])
        tools = FakeTools()
        c, _seen = conv('anthropic', fake, tools)

        def broken(*_a):
            raise RuntimeError('panneau détruit')
        c.on_tool = broken
        self.assertEqual(c.send('types'), 'ok')
        self.assertEqual(tools.calls, [('add', {'w': 2})])
        res = fake.requests[1]['messages'][2]['content']
        self.assertEqual([r['is_error'] for r in res], [True, True, False])
        self.assertIn('type number', res[0]['content'][0]['text'])

    def test_step_limit(self):
        fake = FakeAnthropic([([block('tool_use', id=str(i), name='add', input={})], 'tool_use') for i in range(3)])
        c, _seen = conv('anthropic', fake, max_steps=3)
        self.assertIn('trop de tours', c.send('boucle'))

    def test_unknown_provider(self):
        from vectordrive.agent.chat import Conversation
        with self.assertRaises(ValueError):
            Conversation('autre', '', 'k', FakeTools(), client=object())


class ChatGPT(unittest.TestCase):

    def setUp(self):
        self.assertTrue(there(), BEFORE)

    def test_responses_round_trip(self):
        """API Responses : outils à plat (strict False), consignes, l'appel rendu par `function_call_output` et
        son call_id, la suite par previous_response_id ; un JSON illisible dit au modèle ; une image en data URL."""
        fake = FakeOpenAI([('', [('c1', 'add', '{"w": 2}'), ('c2', 'add', '{oops'), ('c3', 'pic', '{}')]),
                           ('Fait.', [])])
        tools = FakeTools()
        c, seen = conv('openai', fake, tools)
        self.assertEqual(c.send('trace'), 'Fait.')
        self.assertEqual(tools.calls, [('add', {'w': 2}), ('pic', {})])
        r0, r1 = fake.requests
        self.assertEqual(r0['model'], 'gpt-6-astra')
        self.assertEqual(r0['tools'][0], {'type': 'function', 'name': 'add', 'description': 'tool add',
                                          'parameters': FakeTools().specs()[0]['inputSchema'], 'strict': False})
        self.assertNotIn('previous_response_id', r0)
        self.assertEqual(r1['previous_response_id'], 'resp_1')
        self.assertTrue(r1['instructions'])
        outs = r1['input']
        self.assertEqual([o['call_id'] for o in outs], ['c1', 'c2', 'c3'])
        self.assertEqual(outs[0]['output'], [{'type': 'input_text', 'text': '{"id": "o1"}'}])
        self.assertIn('JSON object', outs[1]['output'][0]['text'])
        self.assertEqual(outs[2]['output'], [{'type': 'input_image', 'image_url': 'data:image/png;base64,QUJD'}])
        self.assertEqual(seen['text'], ['Fait.'])

    def test_stop_answers_every_call(self):
        """Arrêté : les appels qui restent reçoivent une réponse, rendue avec la demande suivante."""
        from vectordrive.agent.chat import Stopped
        fake = FakeOpenAI([('', [('c1', 'add', '{}'), ('c2', 'add', '{}')]), ('ok', [])])
        c, _seen = conv('openai', fake)
        c.on_tool = lambda *a: c.stop()
        with self.assertRaises(Stopped):
            c.send('deux')
        c.on_tool = lambda *a: None
        c.send('suite')
        items = fake.requests[-1]['input']
        self.assertEqual([i.get('call_id') for i in items], ['c1', 'c2', None])
        self.assertEqual(items[-1], {'role': 'user', 'content': 'suite'})

    def test_step_limit_then_resume(self):
        """Limite de tours : les réponses du dernier tour partent avec la demande suivante."""
        fake = FakeOpenAI([('', [('c1', 'add', '{}')]), ('', [('c2', 'add', '{}')]), ('ok', [])])
        c, _seen = conv('openai', fake, max_steps=2)
        self.assertIn('trop de tours', c.send('boucle'))
        c.send('suite')
        self.assertEqual([i.get('call_id') for i in fake.requests[-1]['input']], ['c2', None])

    def test_failure_keeps_answers(self):
        """Une panne du fournisseur après des outils : leurs réponses partent avec la demande suivante."""
        fake = FakeOpenAI([('', [('c1', 'add', '{}')]), ('ok', [])])
        calls = {'n': 0}
        create = fake.create

        def flaky(**kw):
            calls['n'] += 1
            if calls['n'] == 2:
                raise ConnectionError('coupure')
            return create(**kw)
        fake.create = flaky
        c, _seen = conv('openai', fake)
        with self.assertRaises(ConnectionError):
            c.send('un')
        c.send('deux')
        self.assertEqual([i.get('call_id') for i in fake.requests[-1]['input']], ['c1', None])


class Mistral(unittest.TestCase):

    def setUp(self):
        self.assertTrue(there(), BEFORE)

    def test_chat_round_trip(self):
        """Chat completions : le système en tête, outils `function`, l'appel gardé dans le message de l'assistant,
        le résultat en message `tool` (tool_call_id, name) ; une image remplacée par une note."""
        fake = FakeMistral([
            {'choices': [{'message': {'role': 'assistant', 'content': '', 'tool_calls': [
                {'id': 'k1', 'type': 'function', 'function': {'name': 'add', 'arguments': '{"w": 3}'}},
                {'id': 'k2', 'type': 'function', 'function': {'name': 'pic', 'arguments': {}}}]}, 'finish_reason': 'tool_calls'}]},
            {'choices': [{'message': {'role': 'assistant', 'content': 'Voilà.'}, 'finish_reason': 'stop'}]}])
        tools = FakeTools()
        c, _seen = conv('mistral', fake, tools)
        self.assertEqual(c.send('trace'), 'Voilà.')
        self.assertEqual(tools.calls, [('add', {'w': 3}), ('pic', {})])
        r0, r1 = fake.requests
        self.assertEqual(r0['model'], 'mistral-large-latest')
        self.assertEqual(r0['messages'][0]['role'], 'system')
        self.assertEqual(r0['tools'][0]['type'], 'function')
        self.assertEqual(r0['tools'][0]['function']['name'], 'add')
        msgs = r1['messages']
        self.assertEqual([m['role'] for m in msgs], ['system', 'user', 'assistant', 'tool', 'tool'])
        self.assertEqual(len(msgs[2]['tool_calls']), 2)
        self.assertEqual((msgs[3]['tool_call_id'], msgs[3]['name'], msgs[3]['content']), ('k1', 'add', '{"id": "o1"}'))
        self.assertIn('picture not sent', msgs[4]['content'])

    def test_stop_then_resume(self):
        """Arrêté après les outils : la demande suivante ne suit jamais directement un message `tool`."""
        from vectordrive.agent.chat import Stopped
        fake = FakeMistral([
            {'choices': [{'message': {'role': 'assistant', 'content': '', 'tool_calls': [
                {'id': 'k1', 'type': 'function', 'function': {'name': 'add', 'arguments': '{}'}},
                {'id': 'k2', 'type': 'function', 'function': {'name': 'add', 'arguments': '{}'}}]}}]},
            {'choices': [{'message': {'role': 'assistant', 'content': 'ok'}, 'finish_reason': 'stop'}]}])
        c, _seen = conv('mistral', fake)
        c.on_tool = lambda *a: c.stop()
        with self.assertRaises(Stopped):
            c.send('deux')
        c.on_tool = lambda *a: None
        self.assertEqual(c.send('suite'), 'ok')
        roles = [m['role'] for m in fake.requests[-1]['messages']]
        self.assertEqual(roles, ['system', 'user', 'assistant', 'tool', 'tool', 'assistant', 'user'])

    def test_address(self):
        """L'adresse : https, ou http vers cette machine seulement ; jamais d'identifiants dans l'adresse."""
        from vectordrive.agent import chat
        c, _s = conv('mistral', None)
        self.assertEqual(c._backend.url, chat.MISTRAL_URL)
        for ok in ('https://exemple.test/v1/chat/completions', 'http://localhost:11434/v1/chat/completions',
                   'http://127.0.0.1:8080/v1/chat/completions', 'http://[::1]:8080/v1/chat/completions'):
            self.assertEqual(conv('mistral', None, url=ok)[0]._backend.url, ok)
        for bad in ('http://exemple.test/v1', 'http://localhost.exemple.test/v1', 'http://localhost@exemple.test/v1',
                    'https://moi:secret@exemple.test/v1', 'ftp://localhost/v1', 'exemple.test'):
            with self.assertRaises(chat.BadAddress, msg=bad):
                conv('mistral', None, url=bad)


class Keys(unittest.TestCase):

    def setUp(self):
        self.assertTrue(there(), BEFORE)
        from vectordrive.agent import keys
        self.keys = keys
        self.assertFalse(keys._windows())                         # jamais le gestionnaire du poste en essai
        self.addCleanup(lambda: [keys.forget(p) for p in ('anthropic', 'openai', 'mistral')])

    def test_memory_and_environment(self):
        k = self.keys
        k.forget('mistral')
        old = os.environ.pop('MISTRAL_API_KEY', None)
        try:
            self.assertEqual(k.load('mistral'), '')
            os.environ['MISTRAL_API_KEY'] = 'env-cle'
            self.assertEqual(k.load('mistral'), 'env-cle')
            self.assertFalse(k.stored('mistral'))
            self.assertFalse(k.save('mistral', '  la-cle  '))       # hors Windows : pour la session
            self.assertEqual(k.load('mistral'), 'la-cle')
            self.assertTrue(k.stored('mistral'))
            k.forget('mistral')
            self.assertEqual(k.load('mistral'), 'env-cle')
        finally:
            os.environ.pop('MISTRAL_API_KEY', None)
            if old is not None:
                os.environ['MISTRAL_API_KEY'] = old


def release_mouse(w):
    """Un essai d'avant (même processus) a pu laisser un bouton de souris enfoncé pour Qt : l'assistant croirait
    l'utilisateur en train de glisser (`UiBridge.busy`) et refuserait ses outils (round 1071)."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtTest import QTest
    held = QGuiApplication.mouseButtons()
    for b in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton):
        if held & b:
            QTest.mouseRelease(w.canvas, b, Qt.KeyboardModifier.NoModifier, QPoint(5, 5))


class Panel(unittest.TestCase):

    def setUp(self):
        self.assertTrue(there(), BEFORE)
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.resize(1100, 800)
        self.w.show()
        release_mouse(self.w)
        self.forget_settings()                           # rien de retenu par un passage d'avant (même processus)
        self.addCleanup(self.forget_settings)
        self.addCleanup(self.clean)

    def forget_settings(self):
        from vectordrive.ui import assistant_panel as AP
        st = self.w.settings
        for k in ('anthropic', 'openai', 'mistral'):
            st.remove(AP.KEY_MODEL.format(k))
        st.remove(AP.KEY_URL)
        st.remove(AP.KEY_PROVIDER)

    def clean(self):
        dock = getattr(self.w, 'dock_assistant', None)
        panel = dock.widget() if dock is not None else None
        if panel is not None and hasattr(panel, 'shutdown'):
            panel.shutdown()
            panel.wait(5)
        self.w.modified = False
        if self.w.isVisible():                           # déjà fermée par l'essai : pas deux fois
            self.w.close()

    def test_draws_on_the_drawing(self):
        """Une demande : le modèle (simulé) appelle add_rectangle ; le rectangle est dans le dessin, un pas
        d'annulation ; la discussion montre la demande, l'outil et la réponse."""
        from vectordrive.ui import columns
        self.assertIn('assistant', columns.ON_DEMAND)
        self.assertIn('assistant_ia', self.w.A)
        p = self.w.show_assistant_panel()
        self.assertTrue(self.w.dock_assistant.isVisible())
        fake = FakeAnthropic([
            ([block('tool_use', id='r', name='add_rectangle', input={'x': 0, 'y': 0, 'width': 40, 'height': 20})],
             'tool_use'),
            ([block('text', text='Rectangle de 40 × 20 mm.')], 'end_turn')])
        p.provider.setCurrentIndex(p.provider.findData('anthropic'))
        p.client_for = lambda _p: fake
        before = sum(len(L.items) for L in self.w.canvas.doc.layers)
        pushes = getattr(self.w, '_undo_pushes', 0)
        self.assertTrue(p.send('Un rectangle de 40 × 20'))
        self.assertTrue(p.wait(20))
        self.assertEqual(sum(len(L.items) for L in self.w.canvas.doc.layers), before + 1)
        self.assertEqual(self.w._undo_pushes, pushes + 1)
        text = p.view.toPlainText()
        for part in ('Un rectangle de 40 × 20', 'add_rectangle', 'Rectangle de 40 × 20 mm.'):
            self.assertIn(part, text)
        self.assertTrue(p.btn_send.isEnabled())
        self.assertFalse(p.btn_stop.isEnabled())

    def test_settings_and_errors(self):
        """Sans clé : rien ne part ; l'adresse seulement pour Mistral ; un autre modèle : discussion neuve ; les
        erreurs du fournisseur dites en clair."""
        p = self.w.show_assistant_panel()
        p.mode.setCurrentIndex(p.mode.findData('avance'))   # l'adresse : mode Avancé (round 1128)
        self.addCleanup(self.w.settings.remove, 'assistant/mode')
        p.keys.forget('openai')
        old = os.environ.pop('OPENAI_API_KEY', None)
        if old is not None:
            self.addCleanup(os.environ.__setitem__, 'OPENAI_API_KEY', old)
        self.addCleanup(p.keys.forget, 'mistral')
        p.provider.setCurrentIndex(p.provider.findData('openai'))
        self.assertFalse(p.url.isVisibleTo(p))
        self.assertFalse(p.send('bonjour'))
        self.assertIn('clé', p.status.text())
        p.provider.setCurrentIndex(p.provider.findData('mistral'))
        self.assertTrue(p.url.isVisibleTo(p))
        self.assertEqual(p.model.currentText(), 'mistral-large-latest')
        p.keys.save('mistral', 'cle-essai')
        first = p.conversation()
        self.assertIs(p.conversation(), first)
        p.model.setEditText('mistral-small-latest')
        self.assertIsNot(p.conversation(), first)
        from vectordrive.agent.chat import ProviderError
        self.assertIn('401', p.explain(ProviderError(401)))
        self.assertIn('429', p.explain(ProviderError(429)))
        self.assertIn('connexion', p.explain(ConnectionError('x')))
        self.assertIn('nouvelle discussion', p.explain(ProviderError(400, 'prompt is too long: maximum context')))
        p.url.setText('http://exemple.test/v1')
        self.assertFalse(p.send('bonjour'))
        self.assertIn('Adresse refusée', p.status.text())

    def test_close_stops_request(self):
        """La fenêtre fermée pendant une demande : la demande s'arrête, aucun outil ne s'exécute plus ; le texte
        de la réponse n'est pas en gras."""
        p = self.w.show_assistant_panel()
        fake = FakeAnthropic([([block('text', text='Bonjour.')], 'end_turn')])
        p.provider.setCurrentIndex(p.provider.findData('anthropic'))
        p.client_for = lambda _p: fake
        self.assertTrue(p.send('salut'))
        self.assertTrue(p.wait(20))
        doc = p.view.document()
        last = doc.lastBlock()
        it = last.begin()
        fmts = []
        while not it.atEnd():
            frag = it.fragment()
            fmts.append((frag.text(), frag.charFormat().fontWeight() > 500))
            it += 1
        self.assertEqual(fmts[-1], (' Bonjour.', False))
        self.w.modified = False
        self.w.close()
        self.assertTrue(p.bridge.closed)


if __name__ == '__main__':
    unittest.main()
