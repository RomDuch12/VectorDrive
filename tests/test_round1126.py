"""Round 1126 (demande du 20/11, 15 h 32) : « fonction créer un bouton personnalisé qui s'ajoutera dans la barre favori
et colonne Assistant IA : On définit un plan de travail (la selection, le calque, ou tous les calques) et la tache à
effectuer, les règles à respecter, le niveau de controle final, la mémoire et autres données que tu juges pertinent ».
Aucun appel réel : un client simulé."""
import json
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1126.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ['VECTORDRIVE_KEYS_MEMORY'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

import tests  # noqa: E402,F401
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402

BEFORE = 'avant : pas de boutons IA personnalisés'


def reply(text):
    return {'choices': [{'message': {'role': 'assistant', 'content': text}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5}}


def call(name, args, k='k1'):
    return {'choices': [{'message': {'role': 'assistant', 'content': '', 'tool_calls': [
        {'id': k, 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}]},
        'finish_reason': 'tool_calls'}], 'usage': {'prompt_tokens': 10, 'completion_tokens': 5}}


class Buttons(unittest.TestCase):

    def setUp(self):
        self.base = pathlib.Path(tempfile.mkdtemp())
        env = mock.patch.dict(os.environ, {'VECTORDRIVE_ASSISTANT_DIR': str(self.base / 'assistant'),
                                           'VECTORDRIVE_MEMORY': str(self.base / 'memoire.md')})
        env.start()
        self.addCleanup(env.stop)
        try:
            from vectordrive.agent import ai_buttons as AB
        except ImportError:
            self.fail(BEFORE)
        self.AB = AB
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.settings.remove(AB.KEY)
        self.w.settings.remove(self.w.FAV_KEY)
        self.addCleanup(self.clean)
        doc = self.w.canvas.doc
        self.a = Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]), tool=0)
        self.b = Shape(path=geom.Path([geom.rect(40, 0, 20, 10)]), tool=0)
        self.c = Shape(path=geom.Path([geom.rect(80, 0, 20, 10)]), tool=0)
        for s in (self.a, self.b, self.c):
            doc.add(s)
        self.p = self.w.show_assistant_panel()
        self.p.provider.setCurrentIndex(self.p.provider.findData('mistral'))
        self.p.model.setEditText('mistral-large-latest')
        self.bodies = []

    def clean(self):
        self.p.wait(10)
        from shiboken6 import isValid
        if self.p.validation_box is not None and isValid(self.p.validation_box):
            self.p.validation_box.close()
        self.p.shutdown()
        self.w.settings.remove(self.AB.KEY)
        self.w.settings.remove(self.w.FAV_KEY)
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def client(self, replies):
        def send(body):
            self.bodies.append(body)
            return replies.pop(0)
        self.p.client_for = lambda _p: send
        self.p.conv = None

    def make(self, **kw):
        b = self.AB.AIButton(label=kw.pop('label', 'Arrondir'), task=kw.pop('task', 'Arrondis les coins à 2 mm'),
                             **kw)
        self.p._ai_buttons_changed(self.AB.load(self.w.settings) + [b])
        return b

    def test_settings_kept_and_cleaned(self):
        AB = self.AB
        b = AB.AIButton(label='  Mon   bouton ', task='t', scope='nimporte', control='x', turns=999,
                        tools=['cam', 'inconnu'])
        AB.save(self.w.settings, [b, AB.AIButton(label='', task='sans libellé')])
        got = AB.load(self.w.settings)
        self.assertEqual([(x.label, x.scope, x.control, x.turns, x.tools) for x in got],
                         [('Mon bouton', 'selection', 'compte_rendu', 200, ['cam'])])
        self.w.settings.setValue(AB.KEY, '[{"label": 3}, "x", {"id": "../..", "label": "a", "task": "b"}]')
        got = AB.load(self.w.settings)
        self.assertEqual(len(got), 1)
        self.assertTrue(got[0].id.isalnum())
        self.w.settings.setValue(AB.KEY, 'pas du json')
        self.assertEqual(AB.load(self.w.settings), [])

    def test_create_from_the_panel(self):
        d = self.p.new_ai_button(exec_dialog=False)
        d.label.setText('Cadre')
        d.scope.setCurrentIndex(d.scope.findData('calque'))
        d.task.setPlainText('Ajoute un cadre de 5 mm autour')
        d.rules.setPlainText('Coins droits')
        d.control.setCurrentIndex(d.control.findData('verification'))
        d.tools['cam'].setChecked(False)
        d.keep()
        got = self.AB.load(self.w.settings)
        self.assertEqual([(b.label, b.scope, b.rules, b.control, 'cam' in b.tools) for b in got],
                         [('Cadre', 'calque', 'Coins droits', 'verification', False)])
        key = got[0].key
        self.assertIn(key, self.w.A, 'une commande (favoris, raccourcis)')
        self.assertIn(key, self.w.favorite_keys(), 'dans la barre des favoris')
        self.assertIn(got[0].id, self.p.ai_buttons, 'dans la colonne de l’assistant')
        self.assertEqual(self.p.ai_buttons[got[0].id].text(), 'Cadre')

    def test_label_and_task_required(self):
        d = self.p.new_ai_button(exec_dialog=False)
        d.keep()
        self.assertIn('libellé', d.error.text())
        d.label.setText('X')
        d.keep()
        self.assertIn('tâche', d.error.text())
        self.assertEqual(self.AB.load(self.w.settings), [])

    def test_edit_duplicate_and_delete(self):
        b = self.make()
        self.w.add_favorite(b.key)
        d = self.p.edit_ai_button(b.id, exec_dialog=False)
        d.label.setText('Arrondir 3 mm')
        d.favorite.setChecked(False)
        d.keep()
        self.assertEqual(self.w.A[b.key].text(), 'Arrondir 3 mm')
        self.assertNotIn(b.key, self.w.favorite_keys())
        d2 = self.p.new_ai_button(exec_dialog=False, source=self.AB.find(self.w.settings, b.id))
        self.assertEqual(d2.task.toPlainText(), 'Arrondis les coins à 2 mm')
        d2.keep()
        self.assertEqual(len(self.AB.load(self.w.settings)), 2)
        self.assertTrue(self.p.delete_ai_button(b.id))
        self.assertNotIn(b.key, self.w.A)
        self.assertEqual([x.label for x in self.AB.load(self.w.settings)], ['Arrondir 3 mm 2'])
        menu = self.p._ai_menu(self.AB.load(self.w.settings)[0].id, None, exec_menu=False)
        self.assertGreaterEqual(len(menu.actions()), 5)

    def test_the_request(self):
        from vectordrive.agent import memories as M
        from vectordrive.ui import assistant_buttons as UB
        M.add('Plaques', 'détourage 6 mm, finition 2 mm', description='plaques de porte', new=True)
        b = self.make(rules='Ne pas toucher au texte', memory='Plaques', control='verification')
        self.w.canvas.select([self.a, self.b])
        items, desc = UB.scope_items(self.w, 'selection')
        text = UB.compose(self.AB.find(self.w.settings, b.id), items, desc)
        self.assertIn('Bouton « Arrondir »', text)
        self.assertIn(f'{self.a.id}, {self.b.id}', text)
        self.assertNotIn(self.c.id, text)
        self.assertIn('Arrondis les coins à 2 mm', text)
        self.assertIn('Ne pas toucher au texte', text)
        self.assertIn('<memory>', text)
        self.assertIn('détourage 6 mm', text)
        self.assertIn('vérifie ton travail', text)
        items, desc = UB.scope_items(self.w, 'tous')
        self.assertEqual(len(items), 3)
        b2 = self.AB.AIButton(label='x', task='y', memory='Disparue')
        self.assertIn('n’existe plus', UB.compose(b2, items, desc))

    def test_run_with_its_tools_and_turns(self):
        b = self.make(tools=['memory'], turns=7)
        self.w.canvas.select([self.a])
        self.client([call('move_objects', {'ids': [self.a.id], 'dx': 5, 'dy': 0}), reply('Fait.')])
        self.assertTrue(self.p.run_button(b.id))
        self.assertTrue(self.p.wait(20))
        first = self.bodies[0]
        names = {t['function']['name'] for t in first['tools']}
        self.assertNotIn('cam_add_operation', names, 'ses outils : pas la FAO')
        self.assertNotIn('run_command', names)
        self.assertIn('memory_topics', names)
        self.assertTrue(any(m.get('role') == 'user' and 'Bouton « Arrondir »' in str(m.get('content'))
                            for m in first['messages']))
        self.assertEqual(self.p.conv.max_steps, 7)
        a = next(it for L in self.w.canvas.doc.layers for it in L.items if it.id == self.a.id)
        self.assertAlmostEqual(a.bbox()[0], 5.0, msg='déplacé')
        self.assertNotIn('hors du plan', self.p.status.text())
        self.assertIsNone(self.p._override, 'la demande suivante : les options')

    def test_change_outside_the_scope_is_said(self):
        b = self.make()
        self.w.canvas.select([self.a])
        self.client([call('move_objects', {'ids': [self.c.id], 'dx': 5, 'dy': 0}), reply('Fait.')])
        self.assertTrue(self.p.run_button(b.id))
        self.assertTrue(self.p.wait(20))
        self.assertIn('1 objet(s) hors du plan de travail', self.p.status.text())

    def test_validation_keep_or_undo(self):
        b = self.make(control='validation', scope='tous')
        self.client([call('move_objects', {'ids': [self.a.id], 'dx': 5, 'dy': 0}), reply('Fait.')])
        self.assertTrue(self.p.run_button(b.id))
        self.assertTrue(self.p.wait(20))
        box = self.p.validation_box
        self.assertIsNotNone(box, 'Garder / Défaire')
        from PySide6.QtWidgets import QApplication
        self.assertIsNone(QApplication.activeModalWidget(), 'non modale : l’assistant n’est pas bloqué')
        self.assertIn('1 modification', box.text())
        a = next(it for L in self.w.canvas.doc.layers for it in L.items if it.id == self.a.id)
        self.assertAlmostEqual(a.bbox()[0], 5.0, msg='déplacé')
        box.undo_button.click()
        app.processEvents()
        a = next(it for L in self.w.canvas.doc.layers for it in L.items if it.id == self.a.id)
        self.assertAlmostEqual(a.bbox()[0], 0.0, msg='défait')

    def test_refusals(self):
        b = self.make()
        self.w.canvas.select([])
        self.assertFalse(self.p.run_button(b.id))
        self.assertIn('Rien de sélectionné', self.p.status.text())
        self.assertFalse(self.p.run_button('inconnu'))
        self.assertIsNone(self.p._button_run)

    def test_undo_is_only_the_buttons_steps(self):
        b = self.make(control='validation', scope='tous')
        self.w.push_undo('avant')                        # un pas de l'utilisateur, d'avant le bouton
        self.client([call('move_objects', {'ids': [self.a.id], 'dx': 5, 'dy': 0}), reply('Fait.')])
        self.assertTrue(self.p.run_button(b.id))
        self.assertTrue(self.p.wait(20))
        box = self.p.validation_box
        self.assertIn('1 modification', box.text())
        n = len(self.w._undo)
        self.w.undo()                                    # Ctrl+Z avant Défaire
        box.undo_button.click()
        app.processEvents()
        self.assertIn('Ctrl+Z à la main', self.p.status.text())
        self.assertEqual(len(self.w._undo), n - 1, 'Défaire n’a pas touché au pas de l’utilisateur')

    def test_steps_of_the_user_during_the_request_are_not_undone(self):
        b = self.make(control='validation', scope='tous')
        self.client([call('move_objects', {'ids': [self.a.id], 'dx': 5, 'dy': 0}), reply('Fait.')])
        self.assertTrue(self.p.run_button(b.id))
        self.assertTrue(self.p.wait(20))
        self.p._button_run = None                        # déjà fini : refait à la main avec un pas en plus
        run = {'button': self.AB.find(self.w.settings, b.id), 'pushes': self.w._undo_pushes, 'tool_steps': 1,
               'stack': self.w._undo, 'mark': self.w._undo[-1] if self.w._undo else None,
               'outside': {}, 'doc': self.w.canvas.doc}
        self.w.push_undo('outil')
        self.w.push_undo('utilisateur')                  # posé pendant la demande, pas par ses outils
        self.p._button_run = run
        self.p._after_button()
        n = len(self.w._undo)
        self.p.validation_box.undo_button.click()
        app.processEvents()
        self.assertEqual(len(self.w._undo), n, 'rien défait')
        self.assertIn('Ctrl+Z à la main', self.p.status.text())

    def test_send_failure_leaves_nothing_behind(self):
        b = self.make(tools=['memory'], turns=5)
        self.w.canvas.select([self.a])
        with mock.patch.object(type(self.p), 'send', return_value=False):
            self.assertFalse(self.p.run_button(b.id))
        self.assertIsNone(self.p._override)
        self.assertIsNone(self.p._button_run)
        with mock.patch.object(type(self.p), 'send', side_effect=RuntimeError('x')):
            with self.assertRaises(RuntimeError):
                self.p.run_button(b.id)
        self.assertIsNone(self.p._override)
        self.assertIsNone(self.p._button_run)

    def test_options_still_win(self):
        self.w.settings.setValue('assistant/outils_fao', False)
        self.addCleanup(self.w.settings.remove, 'assistant/outils_fao')
        self.w.settings.setValue('assistant/outils_memoire', False)
        self.addCleanup(self.w.settings.remove, 'assistant/outils_memoire')
        from vectordrive.agent import memories as M
        M.add('Plaques', 'détourage 6 mm', new=True)
        b = self.make(memory='Plaques')
        self.w.canvas.select([self.a])
        self.client([reply('Fait.')])
        self.assertTrue(self.p.run_button(b.id))
        self.assertTrue(self.p.wait(20))
        names = {t['function']['name'] for t in self.bodies[0]['tools']}
        self.assertNotIn('cam_add_operation', names, 'retirée par les options : ne revient pas')
        from vectordrive.ui import assistant_options as AO
        self.assertIn('memory', AO.without(self.w.settings))
        self.assertNotIn('détourage 6 mm', json.dumps(self.bodies[0], ensure_ascii=False))

    def test_button_without_its_memory_gets_no_memory_in_the_system_text(self):
        from vectordrive.agent import memories as M
        M.add('Plaques', 'détourage 6 mm', description='plaques de porte', new=True)
        b = self.make(tools=['cam'])
        self.w.canvas.select([self.a])
        self.client([reply('Fait.')])
        self.assertTrue(self.p.run_button(b.id))
        self.assertTrue(self.p.wait(20))
        self.assertNotIn('Plaques', json.dumps(self.bodies[0], ensure_ascii=False), 'ni la liste des mémoires')

    def test_openai_conversation_kept(self):
        self.p.provider.setCurrentIndex(self.p.provider.findData('openai'))
        self.p.client_for = lambda _p: object()
        self.p.conv = None
        c = self.p.conversation()
        c._backend.last_id, c._backend._pending = 'resp_1', [{'type': 'function_call_output'}]
        self.p._override = (('cam',), 5)
        c2 = self.p.conversation()
        self.assertIsNot(c2, c)
        self.assertEqual((c2._backend.last_id, c2._backend._pending), ('resp_1', [{'type': 'function_call_output'}]))
        self.p._override = None

    def test_undo_refused_while_another_request_runs(self):
        b = self.make(control='validation', scope='tous')
        self.client([call('move_objects', {'ids': [self.a.id], 'dx': 5, 'dy': 0}), reply('Fait.')])
        self.assertTrue(self.p.run_button(b.id))
        self.assertTrue(self.p.wait(20))
        box = self.p.validation_box
        with mock.patch.object(type(self.p), 'running', new_callable=mock.PropertyMock, return_value=True):
            box.undo_button.click()
        app.processEvents()
        self.assertIn('Une demande est en cours', self.p.status.text())
        a = next(it for L in self.w.canvas.doc.layers for it in L.items if it.id == self.a.id)
        self.assertAlmostEqual(a.bbox()[0], 5.0, msg='rien défait')

    def test_command_updated_in_place_and_conversation_kept(self):
        b = self.make(new_chat=False, tools=['memory'])
        a = self.w.A[b.key]
        d = self.p.edit_ai_button(b.id, exec_dialog=False)
        d.label.setText('Autre')
        d.keep()
        self.assertIs(self.w.A[b.key], a, 'la même commande (onglets à soi, favoris)')
        self.assertEqual(a.text(), 'Autre')
        self.assertIn(b.key, self.w._default_shortcuts, 'un raccourci possible')
        self.w.canvas.select([self.a])
        self.client([reply('Fait.'), reply('Corrigé.')])
        self.assertTrue(self.p.run_button(b.id))
        self.assertTrue(self.p.wait(20))
        self.p.send('corrige ceci')
        self.assertTrue(self.p.wait(20))
        self.assertTrue(any('Bouton « Autre »' in str(m.get('content')) for m in self.bodies[1]['messages']),
                        'la demande d’après continue la discussion du bouton')
        self.assertTrue(self.p.delete_ai_button(b.id))
        self.assertNotIn(b.key, self.w._default_shortcuts)

    def test_favorite_runs_it_and_the_assistant_never_does(self):
        b = self.make()
        with mock.patch.object(type(self.p), 'run_button', return_value=True) as run:
            self.w.A[b.key].trigger()
        run.assert_called_once_with(b.id)
        from vectordrive.agent.tools import denied
        self.assertTrue(denied(b.key), 'l’assistant ne lance jamais un bouton IA')


if __name__ == '__main__':
    unittest.main()
