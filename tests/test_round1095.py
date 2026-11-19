"""Round 1095 : les crédits de l'assistant IA — jetons et coût de chaque tour (Claude, ChatGPT, Mistral), comptés pour
la session et pour le dessin (retenus dans son .vdz seulement s'il y a eu une dépense), prix modifiables, plafond par
session ; Mistral en premier."""
import json
import os
import tempfile
import unittest
import weakref
from types import SimpleNamespace as NS

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1095.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class Tools:
    def specs(self):
        return [{'name': 'noop', 'description': 'n', 'inputSchema': {'type': 'object', 'properties': {}}}]

    def call(self, name, args):
        return [{'type': 'text', 'text': 'ok'}]


def mistral_reply(text, p_in, p_out, cached=0):
    u = {'prompt_tokens': p_in, 'completion_tokens': p_out}
    if cached:
        u['prompt_tokens_details'] = {'cached_tokens': cached}
    return {'choices': [{'message': {'content': text}, 'finish_reason': 'stop'}], 'usage': u}


class Credits(unittest.TestCase):
    def test_cost_and_totals(self):
        from vectordrive.agent import credits as CR
        table = dict(CR.PRICES)
        t = CR.add(None, 'mistral', 'mistral-large-latest', {'in': 1_000_000, 'out': 100_000}, table)
        self.assertAlmostEqual(t['cout'], 2.0 + 0.6)
        self.assertEqual((t['entree'], t['sortie'], t['tours']), (1_000_000, 100_000, 1))
        t2 = CR.add(t, 'anthropic', 'claude-opus-5-5', {'in': 1000, 'out': 0, 'cache': 1_000_000, 'write': 1000},
                    table)
        self.assertAlmostEqual(t2['cout'] - t['cout'], (1000 * 4 + 1_000_000 * 0.2 + 1000 * 4 * 1.25) / 1e6)
        self.assertEqual(t['tours'], 1)                                    # l'ancien total n'est pas touché
        self.assertEqual(set(t2['par_modele']), {'mistral:mistral-large-latest', 'anthropic:claude-opus-5-5'})
        t3 = CR.add(t2, 'openai', 'gpt-6-astra', {'in': 500, 'out': 500}, table)
        self.assertAlmostEqual(t3['cout'], t2['cout'])                     # sans prix : jetons seulement
        self.assertEqual(t3['sans_prix'], ['openai:gpt-6-astra'])
        self.assertEqual(CR.tokens(t3), CR.tokens(t2) + 1000)
        self.assertFalse(CR.spent(None))
        self.assertTrue(CR.spent(t))
        self.assertEqual(CR.money_text(0.0042, '$'), '0,0042 $')          # sous un centime : 4 chiffres
        self.assertEqual(CR.money_text(2.6, '€', '.'), '2.60 €')

    def test_prices_from_settings(self):
        from vectordrive.agent import credits as CR
        st = QSettings(os.path.join(tempfile.mkdtemp(), 'p.ini'), QSettings.Format.IniFormat)
        self.assertEqual(CR.prices(st), CR.PRICES)
        CR.save_prices(st, {'mistral:mon-modele': (1, 2, 0.5)})
        self.assertEqual(CR.prices(st), {'mistral:mon-modele': (1.0, 2.0, 0.5)})
        st.setValue(CR.KEY_PRICES, '{}')
        self.assertEqual(CR.prices(st), {})                                # tous retirés : aucun prix
        st.setValue(CR.KEY_PRICES, 'pas du json')
        self.assertEqual(CR.prices(st), CR.PRICES)
        self.assertEqual(CR.currency(st), '$')
        st.setValue(CR.KEY_CAP, '1,5')
        self.assertEqual(CR.cap(st), 0.0)                                  # illisible : sans plafond
        st.setValue(CR.KEY_CAP, 1.5)
        self.assertEqual(CR.cap(st), 1.5)


class Backends(unittest.TestCase):
    def conv(self, provider, client):
        from vectordrive.agent.chat import Conversation
        seen = []
        c = Conversation(provider, '', 'cle', Tools(), client=client, on_usage=seen.append)
        return c, seen

    def test_mistral_first_and_usage(self):
        from vectordrive.agent.chat import PROVIDERS
        from vectordrive.ui.options import BY_KEY
        self.assertEqual(next(iter(PROVIDERS)), 'mistral')
        self.assertEqual(BY_KEY['assistant/fournisseur'].default, 'mistral')
        replies = [mistral_reply('Bonjour', 1200, 30, cached=200)]
        c, seen = self.conv('mistral', lambda body: replies.pop(0))
        c.send('salut')
        self.assertEqual(seen, [{'in': 1000, 'out': 30, 'cache': 200}])

    def test_claude_usage(self):
        class Stream:
            def __init__(self, msg):
                self.msg = msg

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def __iter__(self):
                return iter([NS(type='text', text='Oui')])

            def get_final_message(self):
                return self.msg

        msg = NS(content=[NS(type='text', text='Oui')], stop_reason='end_turn',
                 usage=NS(input_tokens=10, output_tokens=5, cache_read_input_tokens=300,
                          cache_creation_input_tokens=None))
        client = NS(messages=NS(stream=lambda **kw: Stream(msg)))
        c, seen = self.conv('anthropic', client)
        c.send('?')
        self.assertEqual(seen, [{'in': 10, 'out': 5, 'cache': 300, 'write': 0}])

    def test_openai_usage_and_none(self):
        resp = NS(id='r1', output=[], output_text='Oui', status='completed',
                  usage=NS(input_tokens=1000, output_tokens=40, input_tokens_details=NS(cached_tokens=600)))
        client = NS(responses=NS(create=lambda **kw: resp))
        c, seen = self.conv('openai', client)
        c.send('?')
        self.assertEqual(seen, [{'in': 400, 'out': 40, 'cache': 600}])
        bare = NS(id='r2', output=[], output_text='Oui', status='completed')   # sans usage : rien dit
        c2, seen2 = self.conv('openai', NS(responses=NS(create=lambda **kw: bare)))
        c2.send('?')
        self.assertEqual(seen2, [])

    def test_failing_display_does_not_break(self):
        from vectordrive.agent.chat import Conversation

        def boom(_u):
            raise RuntimeError('fenêtre fermée')
        c = Conversation('mistral', '', 'cle', Tools(), client=lambda b: mistral_reply('ok', 5, 5), on_usage=boom)
        self.assertEqual(c.send('?'), 'ok')


class Panel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.resize(1400, 900)
        cls.w.show()
        app.processEvents()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        from vectordrive.agent import credits as CR
        self.w.settings.remove(CR.KEY_PRICES)
        self.w.settings.remove(CR.KEY_CAP)
        self.p = self.w.show_assistant_panel()
        self.p.session_credits = None
        self.p.provider.setCurrentIndex(self.p.provider.findData('mistral'))
        self.p.model.setEditText('mistral-large-latest')
        self.w.canvas.doc.extra.pop(CR.KEY, None)
        self.w.modified = False

    def ask(self, replies, text='Bonjour'):
        self.p.client_for = lambda _p: (lambda body: replies.pop(0))
        self.p.conv = None                                                 # une discussion neuve, sur ce client
        self.assertTrue(self.p.send(text))
        self.assertTrue(self.p.wait(20))

    def test_session_and_drawing_and_vdz(self):
        from vectordrive.agent import credits as CR
        from vectordrive.io import native
        self.ask([mistral_reply('Salut', 1_000_000, 100_000)])
        s = self.p.session_credits
        self.assertAlmostEqual(s['cout'], 2.6)
        mine = self.w.canvas.doc.extra[CR.KEY]
        self.assertAlmostEqual(mine['cout'], 2.6)
        self.assertEqual(mine['par_modele']['mistral:mistral-large-latest']['tours'], 1)
        self.assertFalse(self.w.modified)                                 # dessin vide jamais enregistré
        text = self.p.credits.text()
        self.assertIn('2,60 $', text)
        self.assertIn('ce dessin', text)
        self.assertIn('mistral:mistral-large-latest', self.p.credits.toolTip())
        path = os.path.join(tempfile.mkdtemp(), 'c.vdz')
        native.write(self.w.canvas.doc, path)
        again = native.read(path)
        self.assertAlmostEqual(again.extra[CR.KEY]['cout'], 2.6)
        from vectordrive.core.document import Document
        bare = os.path.join(tempfile.mkdtemp(), 'b.vdz')
        native.write(Document(), bare)                                     # sans dépense : rien de retenu
        self.assertNotIn(CR.KEY, native.read(bare).extra)

    def test_credits_follow_the_conversation_tab(self):
        from vectordrive.agent import credits as CR
        from vectordrive.ui.doctabs import DocTab
        from vectordrive.core.document import Document
        other = DocTab(Document(), os.path.join(tempfile.mkdtemp(), 'autre.vdz'), False)   # un dessin enregistré
        self.w.docs.append(other)
        try:
            self.p._on_usage(([weakref.ref(other)], 'mistral', 'mistral-small-latest', {'in': 1_000_000, 'out': 0}))
            self.assertAlmostEqual(other.doc.extra[CR.KEY]['cout'], 0.2)
            self.assertTrue(other.modified)
            self.assertNotIn(CR.KEY, self.w.canvas.doc.extra)             # pas au dessin affiché
            self.assertAlmostEqual(self.p.session_credits['cout'], 0.2)
            self.assertIn('ce dessin : ' + 'rien', self.p.credits.text())
        finally:
            self.w.docs.remove(other)

    def test_cap(self):
        from vectordrive.agent import credits as CR
        self.w.settings.setValue(CR.KEY_CAP, 1.0)
        self.ask([mistral_reply('Salut', 1_000_000, 0)])                  # 2 $ : au-delà du plafond
        self.p.client_for = lambda _p: (lambda body: mistral_reply('x', 1, 1))
        self.p.conv = None
        self.assertFalse(self.p.send('Encore'))
        self.assertIn('Plafond', self.p.status.text())
        self.w.settings.remove(CR.KEY_CAP)
        self.assertTrue(self.p.send('Encore'))
        self.assertTrue(self.p.wait(20))

    def test_options_price_table(self):
        from vectordrive.agent import credits as CR
        from vectordrive.ui import assistant_options as AO
        dlg = self.w.options_dialog(exec_dialog=False, page='Assistant')
        try:
            table = dlg.assistant_prices
            self.assertEqual(AO.read_prices(table), CR.PRICES)
            table.item(0, 1).setText('3,5')
            dlg.accept()
            self.assertEqual(CR.prices(self.w.settings)[table.item(0, 0).text()][0], 3.5)
        finally:
            dlg.deleteLater()
        dlg = self.w.options_dialog(exec_dialog=False, page='Assistant')
        try:
            self.assertEqual(AO.read_prices(dlg.assistant_prices)[next(iter(CR.PRICES))][0], 3.5)
        finally:
            dlg.reject()
            dlg.deleteLater()
        self.w.settings.remove(CR.KEY_PRICES)


class AfterReview(unittest.TestCase):
    """La relecture : jetons de Claude d'un tour arrêté, dessin marqué modifié s'il a de quoi être gardé, dépense
    pendant un enregistrement, dépenses jamais recopiées (modèle, onglet dupliqué, export de la sélection)."""

    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.show()
        app.processEvents()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def test_stopped_claude_turn_counts_what_was_streamed(self):
        from vectordrive.agent.chat import Conversation, Stopped
        seen = []

        class Stream:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def __iter__(self):
                yield NS(type='message_start', message=NS(usage=NS(input_tokens=900, output_tokens=1,
                                                                    cache_read_input_tokens=0,
                                                                    cache_creation_input_tokens=0)))
                yield NS(type='message_delta', usage=NS(output_tokens=70))
                c.stop()
                yield NS(type='text', text='Je commence')

            def get_final_message(self):
                raise AssertionError('jamais atteint')
        c = Conversation('anthropic', '', 'cle', Tools(), client=NS(messages=NS(stream=lambda **kw: Stream())),
                         on_usage=seen.append)
        with self.assertRaises(Stopped):
            c.send('?')
        self.assertEqual(seen, [{'in': 900, 'out': 70, 'cache': 0, 'write': 0}])

    def usage(self, tokens=1_000_000):
        return ([weakref.ref(self.w.docs[self.w.doc_index])], 'mistral', 'mistral-small-latest', {'in': tokens})

    def test_drawing_with_content_marked_modified(self):
        from vectordrive.agent import credits as CR
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        p = self.w.show_assistant_panel()
        doc = self.w.canvas.doc
        doc.layers[0].items.append(Shape(path=geom.Path([geom.rect(0, 0, 10, 10)])))
        self.w.modified = False
        p._on_usage(self.usage())
        self.assertTrue(self.w.modified)
        self.assertIn(CR.KEY, doc.extra)

    def test_waits_for_a_save_in_progress(self):
        import time
        from vectordrive.agent import credits as CR
        p = self.w.show_assistant_panel()
        doc = self.w.canvas.doc
        before = (doc.extra.get(CR.KEY) or {}).get('tours', 0)
        self.w._writing_doc = True
        p._on_usage(self.usage(10))
        self.assertEqual((doc.extra.get(CR.KEY) or {}).get('tours', 0), before)   # pas pendant l'écriture
        self.w._writing_doc = False
        end = time.monotonic() + 3
        while (doc.extra.get(CR.KEY) or {}).get('tours', 0) == before and time.monotonic() < end:
            app.processEvents()
            time.sleep(0.02)
        self.assertEqual(doc.extra[CR.KEY]['tours'], before + 1)               # notée après, une seule fois

    def test_never_copied(self):
        from vectordrive.agent import credits as CR
        from vectordrive.io import doc_templates
        from vectordrive.ui import export_dialog
        doc = self.w.canvas.doc
        doc.extra[CR.KEY] = CR.add(None, 'mistral', 'mistral-small-latest', {'in': 10}, CR.PRICES)
        self.assertNotIn(CR.KEY, export_dialog.selection_document(doc, []).extra)
        self.assertIn(CR.KEY, export_dialog._NOT_EXPORTED)
        import inspect
        self.assertIn("'ia_credits'", inspect.getsource(doc_templates.save))
        n = len(self.w.docs)
        self.w.duplicate_tab()
        try:
            self.assertEqual(len(self.w.docs), n + 1)
            self.assertNotIn(CR.KEY, self.w.canvas.doc.extra)
        finally:
            self.w.modified = False
            self.w.close_tab(self.w.doc_index) if hasattr(self.w, 'close_tab') else None


if __name__ == '__main__':
    unittest.main()
