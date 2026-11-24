"""Round 1150 (demande du 24/11) : « Assistant IA verrouille son onglet pour travailler jusque fin travail ou annul
user, on doit pouvoir travailler sur les autres onglets »."""
import json
import os
import tempfile
import threading
import unittest
import weakref
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1150.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ.setdefault('VECTORDRIVE_KEYS_MEMORY', '1')

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent, QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : l’assistant refusait d’agir dès qu’on regardait un autre onglet, et son onglet restait modifiable'


def reply(text):
    return {'choices': [{'message': {'role': 'assistant', 'content': text}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5}}


def call(name, args, k='k1'):
    return {'choices': [{'message': {'role': 'assistant', 'content': '', 'tool_calls': [
        {'id': k, 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}]},
        'finish_reason': 'tool_calls'}], 'usage': {'prompt_tokens': 10, 'completion_tokens': 5}}


def press(button=Qt.MouseButton.LeftButton):
    return QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(10, 10), QPointF(10, 10), button, button,
                       Qt.KeyboardModifier.NoModifier)


class Lock(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict(os.environ, {})
        env.start()
        self.addCleanup(env.stop)
        for v in ('MISTRAL_API_KEY', 'ANTHROPIC_API_KEY', 'OPENAI_API_KEY'):
            os.environ.pop(v, None)
        from vectordrive.agent import keys
        from vectordrive.ui.main_window import MainWindow
        self.keys = keys
        self.w = w = MainWindow()
        if not w.docs:
            w.new_document()
        w.settings.remove('assistant/mode')
        self.p = w.show_assistant_panel()
        self.p.provider.setCurrentIndex(self.p.provider.findData('mistral'))
        self.p.mode.setCurrentIndex(self.p.mode.findData('avance'))
        self.addCleanup(self.clean)
        w.canvas.doc.add(Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]), tool=1))
        w.canvas.invalidate()
        self.a = w.docs[w.doc_index]                                        # l'onglet de l'assistant
        w.new_document()
        self.b = w.docs[w.doc_index]                                        # celui de l'utilisateur
        self.mine = Shape(path=geom.Path([geom.rect(50, 50, 5, 5)]), tool=1)
        w.canvas.doc.add(self.mine)
        w.canvas.invalidate()

    def clean(self):
        self.p.wait(10)
        self.p.shutdown()
        self.keys.forget('mistral')
        self.w.agent_lock(None)
        self.w.settings.remove('assistant/mode')
        for t in self.w.docs:
            t.modified = False
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def pages_on(self):
        r = self.w.ribbon
        return all(r.widget(k).isEnabled() for k in range(r.count()))

    def count(self, tab):
        doc = self.w.canvas.doc if self.w.docs[self.w.doc_index] is tab else tab.doc
        return sum(len(L.items) for L in doc.layers)

    def test_tool_runs_in_its_tab_while_user_elsewhere(self):
        w, p = self.w, self.p
        w.canvas.select([self.mine])
        marker = object()
        w.canvas.tool_obj = marker                                          # un outil à moitié tracé
        scale = w.canvas.scale
        run = p._runner([weakref.ref(self.a)])

        def draw():
            w.push_undo('assistant')
            w.canvas.doc.add(Shape(path=geom.Path([geom.rect(20, 0, 10, 10)]), tool=1))
            w._on_doc_changed()
            return w.docs[w.doc_index]
        self.assertIs(run(draw), self.a, BEFORE)                            # dans son onglet
        self.assertIs(w.docs[w.doc_index], self.b)                          # le mien revient
        self.assertEqual(w.canvas.selection, [self.mine])                   # tel quel
        self.assertIs(w.canvas.tool_obj, marker)
        self.assertEqual(w.canvas.scale, scale)
        self.assertEqual(self.count(self.a), 2)
        self.assertEqual(self.count(self.b), 1)
        self.assertTrue(self.a.modified)
        self.assertEqual(len(self.a.undo), 1)                              # son pas, sur sa pile
        w.canvas.tool_obj = None

    def test_locked_tab_refuses_edits(self):
        w = self.w
        w.agent_lock(self.a)
        self.assertTrue(self.a.label().startswith('🔒'))
        self.assertFalse(w.agent_tab_locked())                              # je regarde l'autre : libre
        self.assertTrue(self.pages_on())
        w.switch_tab(w.docs.index(self.a))
        self.assertTrue(w.agent_tab_locked())
        self.assertFalse(self.pages_on())                                # grisé
        self.assertTrue(w.doc_bar.isEnabled())                              # les onglets de dessin, non
        self.assertTrue(w._agent_banner.isVisibleTo(w))
        self.assertTrue(w._agent_filter.eventFilter(w.canvas, press()))     # clic : mangé
        self.assertFalse(w._agent_filter.eventFilter(w.canvas, press(Qt.MouseButton.MiddleButton)))   # vue : permise
        self.assertTrue(w._agent_filter.eventFilter(
            w.canvas, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)))
        n = self.count(self.a)
        w.A['select_all'].trigger()
        w.A['delete'].trigger()                                             # refusées
        self.assertEqual(self.count(self.a), n)
        w.canvas.select(list(w.canvas.doc.iter_items()))
        w._fx_depth = 1                                                     # lancée par une autre (Ctrl+K)
        try:
            w.A['delete'].trigger()
        finally:
            w._fx_depth = 0
        w.canvas.select([])
        self.assertEqual(self.count(self.a), n)
        act = w.A['text_compress_line']                                     # à cocher : refusée aussi
        was = act.isChecked()
        act.trigger()
        self.assertEqual(act.isChecked(), was)
        rulers = w.A['rulers']                                              # une bascule d'affichage, cochée par
        want = not rulers.isChecked()                                       # le programme : pas annulée
        rulers.setChecked(want)
        self.assertEqual(rulers.isChecked(), want)
        rulers.setChecked(not want)
        w.A['zoom_fit'].trigger()                                           # la vue : permise
        self.assertFalse(w.close_tab(w.docs.index(self.a)))                 # fermeture refusée
        dock = w.dock_assistant.widget()
        self.assertTrue(dock.isEnabled())                                   # l'assistant (Arrêter) reste
        w.switch_tab(w.docs.index(self.b))
        self.assertTrue(self.pages_on())                               # ailleurs : tout libre
        self.assertFalse(w._agent_banner.isVisibleTo(w))
        w.agent_lock(None)
        self.assertFalse(self.a.label().startswith('🔒'))
        w.switch_tab(w.docs.index(self.a))
        self.assertTrue(self.pages_on())
        self.assertTrue(w.close_tab(w.docs.index(self.b), answer='discard'))

    def test_open_does_not_replace_a_held_empty_tab(self):
        w = self.w
        w.close_tab(w.docs.index(self.a), answer='discard')
        w.new_document()
        empty = w.docs[w.doc_index]
        self.assertTrue(empty.pristine())
        w.agent_lock(empty)
        w.new_document()                                                    # (l'onglet vide n'est pas repris)
        self.assertIn(empty, w.docs)
        self.assertIsNot(w.docs[w.doc_index], empty)

    def test_request_holds_then_releases(self):
        w, p = self.w, self.p
        w.switch_tab(w.docs.index(self.a))
        self.keys.save('mistral', 'sk-essai')
        gate = threading.Event()
        answers = [call('add_rectangle', {'x': 30, 'y': 0, 'width': 10, 'height': 10}), reply('Fait.')]

        def send(body):
            gate.wait(10)
            return answers.pop(0)
        p.client_for = lambda _p: send
        p.conv = None
        self.assertTrue(p.send('Ajoute un carré'))
        self.assertIs(w.agent_tab(), self.a)                                # tenu pendant la demande
        w.switch_tab(w.docs.index(self.b))                                  # je travaille ailleurs
        w.push_undo('moi')
        w.canvas.doc.add(Shape(path=geom.Path([geom.rect(70, 0, 5, 5)]), tool=1))
        w._on_doc_changed()
        gate.set()
        self.assertTrue(p.wait(20))
        app.processEvents()
        self.assertIsNone(w.agent_tab())                                    # rendu à la fin
        self.assertIs(w.docs[w.doc_index], self.b)                          # je suis resté sur le mien
        self.assertEqual(self.count(self.a), 2, BEFORE)                     # son carré, dans son onglet
        self.assertEqual(self.count(self.b), 2)                             # le mien, dans le mien

    def test_stop_releases(self):
        w, p = self.w, self.p
        w.switch_tab(w.docs.index(self.a))
        self.keys.save('mistral', 'sk-essai')
        gate = threading.Event()

        def send(body):
            gate.wait(10)
            return reply('Bonjour.')
        p.client_for = lambda _p: send
        p.conv = None
        self.assertTrue(p.send('Bonjour'))
        self.assertTrue(w.agent_tab_locked())
        w._agent_banner.stop.click()                                        # « Arrêter l'assistant »
        self.assertIsNone(w.agent_tab())                                    # rendu tout de suite
        self.assertTrue(self.pages_on())
        from vectordrive.agent.protocol import ToolError
        with self.assertRaises(ToolError):                                  # plus aucun outil de la demande
            p._runner([weakref.ref(self.a)])(lambda: 'fait')
        gate.set()
        self.assertTrue(p.wait(20))
        app.processEvents()
        self.assertIsNone(w.agent_tab())
        self.assertTrue(self.pages_on())

    def test_my_steps_elsewhere_do_not_spoil_keep_or_undo(self):
        w = self.w
        w.agent_lock(self.a)
        before = getattr(w, '_undo_pushes_elsewhere', 0)
        w.push_undo('moi')                                                  # dans l'autre onglet
        self.assertEqual(w._undo_pushes_elsewhere, before + 1)
        run = self.p._runner([weakref.ref(self.a)])
        run(lambda: w.push_undo('assistant'))                               # le sien : pas compté ailleurs
        self.assertEqual(w._undo_pushes_elsewhere, before + 1)
        w.switch_tab(w.docs.index(self.a))
        w.push_undo('assistant, son onglet affiché')                        # verrouillé : le sien aussi
        self.assertEqual(w._undo_pushes_elsewhere, before + 1)

    def test_its_commands_run_in_its_shown_tab(self):
        w = self.w
        w.switch_tab(w.docs.index(self.a))
        w.agent_lock(self.a)
        self.assertTrue(w.agent_tab_locked())
        run = self.p._runner([weakref.ref(self.a)])
        run(lambda: w.A['select_all'].trigger())                            # ses commandes : pas refusées
        self.assertEqual(len(w.canvas.selection), 1)
        self.assertTrue(w.agent_tab_locked())                               # l'utilisateur, toujours tenu à l'écart

    def test_views_and_selections_stay_apart(self):
        w = self.w
        w.agent_lock(self.a)
        lay = w.canvas.doc.active_layer
        w.canvas.solo_layer = lay.id                                        # mon calque seul
        w._props_brush = brush = ('objet', {})                              # mon pinceau
        run = self.p._runner([weakref.ref(self.a)])
        seen = run(lambda: (w.canvas.solo_layer, w._props_brush, len(list(w.canvas.shown_items()))
                            if hasattr(w.canvas, 'shown_items') else 1))
        self.assertIsNone(seen[0])                                          # son affichage, pas le mien
        self.assertIsNone(seen[1])
        self.assertEqual(seen[2], 1)                                        # son dessin, visible
        self.assertEqual(w.canvas.solo_layer, lay.id)
        self.assertIs(w._props_brush, brush)
        self.assertNotEqual((self.a.view_state or {}).get('solo'), lay.id)  # ma vue pas écrite dans son onglet
        w._props_brush = None
        run(lambda: w.canvas.select(list(w.canvas.doc.iter_items())))       # il choisit…
        got = run(lambda: len(w.canvas.selection))                          # … et le retrouve à l'outil suivant
        self.assertEqual(got, 1)
        self.assertEqual(w.canvas.selection, [])                            # la mienne, vide, inchangée

    def test_its_selection_follows_when_i_leave(self):
        w = self.w
        w.switch_tab(w.docs.index(self.a))
        w.agent_lock(self.a)
        run = self.p._runner([weakref.ref(self.a)])
        run(lambda: w.A['select_all'].trigger())                            # affiché : il choisit
        w.switch_tab(w.docs.index(self.b))                                  # je pars
        self.assertEqual(run(lambda: len(w.canvas.selection)), 1)           # il retrouve son choix
        w.switch_tab(w.docs.index(self.a))                                  # je reviens
        self.assertEqual(run(lambda: len(w.canvas.selection)), 1)

    def test_my_ribbon_does_not_jump(self):
        w = self.w
        w.agent_lock(self.a)
        k = w.ribbon.currentIndex()
        with mock.patch.object(w, '_text_context', side_effect=AssertionError('ruban changé')):
            self.p._runner([weakref.ref(self.a)])(lambda: w.canvas.select(list(w.canvas.doc.iter_items())))
        self.assertEqual(w.ribbon.currentIndex(), k)

    def test_free_commands_change_nothing(self):
        self.assertNotIn('show_all', self.w.AGENT_FREE)
        self.assertNotIn('doc_info', self.w.AGENT_FREE)

    def test_held_tab_neither_reloaded_nor_replaced(self):
        w = self.w
        w.switch_tab(w.docs.index(self.a))
        w.agent_lock(self.a)
        m = w.doc_tab_menu(w.doc_index, exec_menu=False)
        acts = {a.text(): a for a in m.actions()}
        self.assertFalse(acts['Fermer'].isEnabled())
        self.assertFalse(w.reload_tab(confirm=False))
        from vectordrive.core.document import Document
        i = w._open_in_tab(Document(), None, at=w.docs.index(self.a))
        self.assertIn(self.a, w.docs)
        self.assertIsNot(w.docs[i], self.a)

    def test_tool_waits_while_user_busy(self):
        from vectordrive.agent.protocol import ToolError
        p = self.p
        with mock.patch.object(p.bridge, 'run', side_effect=[ToolError('the user is dragging something in '
                                                                       'VectorDrive: try again in a moment'), 'fait']):
            self.assertEqual(p._runner([weakref.ref(self.a)])(lambda: 'x'), 'fait')
        with mock.patch.object(p.bridge, 'run', side_effect=ToolError('a dialog is open')):
            with self.assertRaises(ToolError):
                p._runner([weakref.ref(self.a)])(lambda: 'x')


if __name__ == '__main__':
    unittest.main()
