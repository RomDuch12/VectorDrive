"""Round 1136 (demande du 20/11, 22 h) : le STEP clé en main dans le panneau de l'assistant — une suggestion
(Débutant), trois modèles de boutons IA ; un bouton lancé reçoit les outils STEP s'il les permet, et eux seuls
écrivent. Aucun appel réel : un client simulé."""
import json
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1136.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ['VECTORDRIVE_KEYS_MEMORY'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

import tests  # noqa: E402,F401
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402

BEFORE = 'avant : pas de modèle STEP'
STEP_TEMPLATES = ('Pièce STEP du dessin', 'Pièce tournée STEP', 'Plaque et visserie STEP')
KEYS = ('ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'MISTRAL_API_KEY')


def reply(text):
    return {'choices': [{'message': {'role': 'assistant', 'content': text}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5}}


def call(name, args, k='k1'):
    return {'choices': [{'message': {'role': 'assistant', 'content': '', 'tool_calls': [
        {'id': k, 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}]},
        'finish_reason': 'tool_calls'}], 'usage': {'prompt_tokens': 10, 'completion_tokens': 5}}


class StepPanel(unittest.TestCase):

    def setUp(self):
        self.base = pathlib.Path(tempfile.mkdtemp())
        env = mock.patch.dict(os.environ, {'VECTORDRIVE_ASSISTANT_DIR': str(self.base / 'assistant'),
                                           'VECTORDRIVE_MEMORY': str(self.base / 'memoire.md')})
        env.start()
        self.addCleanup(env.stop)
        keys = mock.patch.dict(os.environ)               # les clés du poste : jamais lues ici
        keys.start()
        self.addCleanup(keys.stop)
        for k in KEYS:
            os.environ.pop(k, None)
        from vectordrive.agent import ai_buttons as AB
        self.AB = AB
        if 'Pièce STEP du dessin' not in [t[0] for t in AB.TEMPLATES]:
            self.fail(BEFORE)
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.settings.remove(AB.KEY)
        self.addCleanup(self.clean)
        doc = self.w.canvas.doc
        self.plate = Shape(path=geom.Path([geom.rect(0, 0, 60, 40)]), tool=0)
        doc.add(self.plate)
        self.p = self.w.show_assistant_panel()
        self.p.provider.setCurrentIndex(self.p.provider.findData('mistral'))
        self.p.model.setEditText('mistral-large-latest')
        self.bodies = []
        self.folder = self.base / 'assistant' / 'copies' / 'step'

    def clean(self):
        self.p.wait(10)
        from shiboken6 import isValid
        if self.p.validation_box is not None and isValid(self.p.validation_box):
            self.p.validation_box.close()
        self.p.shutdown()
        self.w.settings.remove(self.AB.KEY)
        self.w.settings.remove('assistant/mode')
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

    def from_template(self, label):
        i = [t[0] for t in self.AB.TEMPLATES].index(label)
        b = self.AB.template(i)
        self.p._ai_buttons_changed(self.AB.load(self.w.settings) + [b])
        return b

    def test_templates_and_suggestion(self):
        for label in STEP_TEMPLATES:
            i = [t[0] for t in self.AB.TEMPLATES].index(label)
            b = self.AB.template(i)
            self.assertIn('step', b.tools, label)
            self.assertNotIn('cam', b.tools, label)
            self.assertEqual(b.scope, 'selection')
        texts = [a.text() for a in self.p.ai_add.menu().actions() if a.text()]
        for label in STEP_TEMPLATES:
            self.assertIn(label, texts)
        self.assertIn('Fais-moi une vis CHC M5 × 20 en STEP', [b.text() for b in self.p.suggestions])

    def test_step_button_gets_the_step_tools_and_writes(self):
        hole = Shape(path=geom.Path([geom.circle((30, 20), 5)]), tool=0)
        self.w.canvas.doc.add(hole)
        ids = [self.plate.id, hole.id]
        b = self.from_template('Pièce STEP du dessin')
        self.w.canvas.select([it for L in self.w.canvas.doc.layers for it in L.items if it.id in ids])
        n = sum(len(L.items) for L in self.w.canvas.doc.layers)
        self.client([call('step_from_drawing', {'ids': ids, 'thickness': 10, 'inner': 'round_holes', 'pocket': 2,
                                                'name': 'Plaque'}), reply('Fait : 60 × 40 × 10 mm.')])
        self.assertTrue(self.p.run_button(b.id))
        self.assertTrue(self.p.wait(30))
        names = {t['function']['name'] for t in self.bodies[0]['tools']}
        self.assertTrue({'step_generate', 'step_from_drawing', 'step_build', 'step_check'} <= names)
        self.assertNotIn('cam_add_operation', names, 'ses outils seulement')
        result = next(m for m in self.bodies[1]['messages'] if m.get('role') == 'tool')
        got = json.loads(result['content'])
        self.assertTrue(got['read_back']['ok'], got)
        self.assertTrue((self.folder / 'Plaque.step').is_file())
        self.assertEqual(sum(len(L.items) for L in self.w.canvas.doc.layers), n, 'le dessin inchangé')

    def test_plate_and_screws_assembly(self):
        from vectordrive.agent import tools as T
        from vectordrive.agent.protocol import ToolError
        holes = [Shape(path=geom.Path([geom.circle(c, 2.2)]), tool=0) for c in ((10, 10), (50, 30))]
        for h in holes:
            self.w.canvas.doc.add(h)
        ids = [self.plate.id] + [h.id for h in holes]
        ts = T.ToolSet(self.w, extended=True)
        spec = {'bodies': [{'name': 'plaque', 'drawing': ids, 'thickness': 10, 'inner': 'round_holes',
                            'pocket': 2}] + [
            {'name': f'vis{k}', 'part': 'chc', 'values': {'size': 'M4', 'length': 16},
             'placement': {'origin': [c[0], c[1], 10]}} for k, c in enumerate(((10, 10), (50, 30)))]}
        dry = json.loads(ts.call('step_build', {'spec': spec, 'dry_run': True})[0]['text'])
        self.assertEqual(dry['bodies'], 3)
        x0, y0, z0, x1, y1, z1 = dry['bounds_mm']
        self.assertAlmostEqual(x0, 0, delta=0.01)                # la plaque où sont ses contours
        self.assertAlmostEqual(x1, 60, delta=0.01)
        self.assertAlmostEqual(z0, -6, delta=0.01)               # la tige de 16 sous le dessus (Z = 10)
        self.assertGreater(z1, 10)                               # les têtes sur le dessus
        n = sum(len(L.items) for L in self.w.canvas.doc.layers)
        got = json.loads(ts.call('step_build', {'spec': spec, 'name': 'Plaque_vis', 'add_to_drawing': True})[0]['text'])
        self.assertTrue(got['read_back']['ok'], got['read_back'])
        self.assertTrue((self.folder / 'Plaque_vis.step').is_file())
        self.assertEqual(sum(len(L.items) for L in self.w.canvas.doc.layers), n + 3)
        new = [it for L in self.w.canvas.doc.layers for it in L.items][-3:]
        bx = new[0].bbox()
        self.assertAlmostEqual(min(bx[0], bx[2]), 0, delta=0.05, msg='posée sur place, pas centrée')
        for bad, word in (({'name': 'p', 'drawing': ['nope'], 'thickness': 10}, 'bodies[0].drawing'),
                          ({'name': 'p', 'drawing': ids, 'thickness': 0}, 'bodies[0].drawing'),
                          ({'name': 'p', 'slabs': [], 'thickness': 3}, 'go with "drawing"')):
            with self.assertRaises(ToolError) as cm:
                ts.call('step_build', {'spec': {'bodies': [bad]}, 'dry_run': True})
            self.assertIn(word, str(cm.exception))

    def test_button_without_step_gets_none(self):
        b = self.AB.AIButton(label='Sans STEP', task='Décris la sélection', tools=['memory'])
        self.p._ai_buttons_changed(self.AB.load(self.w.settings) + [b])
        self.w.canvas.select([self.plate])
        self.client([reply('Un rectangle.')])
        self.assertTrue(self.p.run_button(b.id))
        self.assertTrue(self.p.wait(20))
        names = {t['function']['name'] for t in self.bodies[0]['tools']}
        self.assertFalse({n for n in names if n.startswith('step_')}, names)


if __name__ == '__main__':
    unittest.main()
