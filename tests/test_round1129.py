"""Round 1129 (demande du 20/11, 21 h 48) : Garder ou Défaire à la fin de chaque demande (d'office en mode
Débutant). Aucun appel réel : un client simulé."""
import json
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1129.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ['VECTORDRIVE_KEYS_MEMORY'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

import tests  # noqa: E402,F401
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402

BEFORE = 'avant : pas de Garder ou Défaire à la fin d’une demande'


def reply(text):
    return {'choices': [{'message': {'role': 'assistant', 'content': text}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5}}


def call(name, args, k='k1'):
    return {'choices': [{'message': {'role': 'assistant', 'content': '', 'tool_calls': [
        {'id': k, 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}]},
        'finish_reason': 'tool_calls'}], 'usage': {'prompt_tokens': 10, 'completion_tokens': 5}}


class Validate(unittest.TestCase):

    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        for k in ('assistant/mode', 'assistant/valider'):
            self.w.settings.remove(k)
        self.addCleanup(self.clean)
        self.a = Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]), tool=0)
        self.w.canvas.doc.add(self.a)
        self.p = self.w.show_assistant_panel()
        if not hasattr(self.p, 'validate_requests'):
            self.fail(BEFORE)
        self.p.provider.setCurrentIndex(self.p.provider.findData('mistral'))

    def clean(self):
        from shiboken6 import isValid
        self.p.wait(10)
        box = getattr(self.p, 'validation_box', None)
        if box is not None and isValid(box):
            box.close()
        self.p.shutdown()
        for k in ('assistant/mode', 'assistant/valider'):
            self.w.settings.remove(k)
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def ask(self, replies):
        def send(body):
            return replies.pop(0)
        self.p.client_for = lambda _p: send
        self.p.conv = None
        self.p.validation_box = None
        self.assertTrue(self.p.send('Déplace le rectangle de 5 mm'))
        self.assertTrue(self.p.wait(20))
        return self.p.validation_box

    def x(self):
        a = next(it for L in self.w.canvas.doc.layers for it in L.items if it.id == self.a.id)
        return a.bbox()[0]

    def move(self):
        return [call('move_objects', {'ids': [self.a.id], 'dx': 5, 'dy': 0}), reply('Fait.')]

    def test_beginner_keep_or_undo(self):
        self.p.mode.setCurrentIndex(self.p.mode.findData('debutant'))
        box = self.ask(self.move())
        self.assertIsNotNone(box, 'Débutant : Garder ou Défaire')
        self.assertEqual(box.windowTitle(), 'Assistant IA')
        self.assertAlmostEqual(self.x(), 5.0)
        box.undo_button.click()
        app.processEvents()
        self.assertAlmostEqual(self.x(), 0.0, msg='défait d’un coup')
        self.assertIn('Modifications de la demande défaites', self.p.status.text())

    def test_nothing_changed_no_box(self):
        self.p.mode.setCurrentIndex(self.p.mode.findData('debutant'))
        self.assertIsNone(self.ask([reply('Ce dessin a un rectangle.')]), 'rien de modifié : rien à demander')

    def test_its_own_undo_tool_counted(self):
        self.p.mode.setCurrentIndex(self.p.mode.findData('debutant'))
        undone = [call('move_objects', {'ids': [self.a.id], 'dx': 5, 'dy': 0}), call('undo', {}, 'k2'),
                  reply('Rien de changé.')]
        self.assertIsNone(self.ask(undone), 'déplacé puis défait par lui : rien à garder')
        redo = [call('move_objects', {'ids': [self.a.id], 'dx': 5, 'dy': 0}), call('undo', {}, 'k2'),
                call('move_objects', {'ids': [self.a.id], 'dx': 7, 'dy': 0}, 'k3'), reply('Fait.')]
        box = self.ask(redo)
        self.assertIsNotNone(box)
        self.assertAlmostEqual(self.x(), 7.0)
        box.undo_button.click()
        app.processEvents()
        self.assertAlmostEqual(self.x(), 0.0, msg='son seul pas restant défait')

    def test_advanced_none_unless_asked(self):
        self.p.mode.setCurrentIndex(self.p.mode.findData('avance'))
        self.assertIsNone(self.ask(self.move()), 'Avancé : appliqué tel quel')
        self.w.settings.setValue('assistant/valider', 'oui')
        self.assertIsNotNone(self.ask(self.move()), 'Toujours')
        self.p.mode.setCurrentIndex(self.p.mode.findData('debutant'))
        self.w.settings.setValue('assistant/valider', 'non')
        self.assertIsNone(self.ask(self.move()), 'Jamais')

    def test_a_button_keeps_its_own_control(self):
        from vectordrive.agent import ai_buttons as AB
        self.p.mode.setCurrentIndex(self.p.mode.findData('debutant'))
        b = AB.AIButton(label='Pousser', task='Déplace', scope='tous', control='aucun')
        self.p._ai_buttons_changed([b])
        self.addCleanup(self.w.settings.remove, AB.KEY)
        replies = self.move()
        self.p.client_for = lambda _p: (lambda body: replies.pop(0))
        self.p.conv = None
        self.p.validation_box = None
        self.assertTrue(self.p.run_button(b.id))
        self.assertTrue(self.p.wait(20))
        self.assertIsNone(self.p.validation_box, 'contrôle « aucun » du bouton : pas de fenêtre')


if __name__ == '__main__':
    unittest.main()
