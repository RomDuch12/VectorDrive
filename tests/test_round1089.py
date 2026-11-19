"""Round 1089 (demande du 18/11 soir) : « Assistant comment lui donner de la mémoire, ou comment lui donner des scripts
(+ templates), la doc complete et full access à vd sauf les sauvegardes ecrasant ». Aucun appel réel ; la mémoire et
les scripts dans des dossiers d'essai."""
import os
import pathlib
import tempfile
import unittest

TMP = tempfile.mkdtemp()
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(TMP, 'r1089.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'
os.environ['VECTORDRIVE_KEYS_MEMORY'] = '1'
os.environ['VECTORDRIVE_MEMORY'] = os.path.join(TMP, 'memoire', 'memoire.md')
os.environ['VECTORDRIVE_SCRIPTS'] = os.path.join(TMP, 'scripts')

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])
BEFORE = 'avant : ni mémoire, ni scripts, ni commandes pour l’assistant'

HEXAGON = """Dim n, r, i, a
n = 6
r = 0.010
If NewCurve Then
  MoveTo r, 0, 0
  For i = 1 To n - 1
    a = i * 8 * Atn(1) / n
    LineTo r * Cos(a), r * Sin(a), 0
  Next
  ClosePath
End If
"""


class Tools(unittest.TestCase):

    def setUp(self):
        from vectordrive.agent.tools import ToolSet
        from vectordrive.ui.main_window import MainWindow
        from unittest import mock
        here = tempfile.mkdtemp()                         # chaque essai ses dossiers (d'autres modules en posent)
        env = mock.patch.dict(os.environ, {'VECTORDRIVE_MEMORY': os.path.join(here, 'memoire', 'memoire.md'),
                                           'VECTORDRIVE_SCRIPTS': os.path.join(here, 'scripts')})
        env.start()
        self.addCleanup(env.stop)
        self.w = MainWindow()
        self.addCleanup(self.close)
        self.w._te_script_folder = lambda: None           # jamais les scripts d'un TypeEdit installé
        self.t = ToolSet(self.w, extended=True)

    def close(self):
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def call(self, tool, **args):
        import json
        out = self.t.call(tool, args)
        return json.loads(out[0]['text'])

    def test_memory(self):
        from vectordrive.agent import tools as AT
        from vectordrive.agent.chat import SYSTEM, Conversation
        self.assertIn('memory_write', self.t.names(), BEFORE)
        self.assertEqual(self.call('memory_read')['memory'], '')
        self.call('memory_write', text='Le client préfère la police Arial.')
        self.call('memory_write', text='Plaques en laiton de 0,8 mm.')
        got = self.call('memory_read')['memory']
        self.assertEqual(got, 'Le client préfère la police Arial.\nPlaques en laiton de 0,8 mm.\n')
        prompt = AT.memory_prompt()
        self.assertIn('<memory>', prompt)                                    # balisée : des notes, pas des consignes
        self.assertIn('not instructions', prompt)
        self.assertIn('Plaques en laiton', prompt)
        c = Conversation('mistral', '', 'k', self.t, client=lambda body: None, system=prompt)
        self.assertTrue(c.system.startswith(SYSTEM))
        self.assertIn('Plaques en laiton', c.system)
        self.assertEqual(c._backend.messages[0]['content'], c.system)
        self.call('memory_write', text='', mode='replace')
        self.assertEqual(AT.memory_prompt(), '')
        from vectordrive.agent.tools import ToolSet
        mcp = ToolSet(self.w)                                                # le serveur MCP : pas ces outils
        self.assertNotIn('memory_write', mcp.names())
        self.assertNotIn('run_command', mcp.names())

    def test_scripts(self):
        from vectordrive.agent.protocol import ToolError
        from vectordrive.core.document import Shape
        self.assertEqual(self.call('save_script', name='Hexagone', code=HEXAGON), {'saved': 'Hexagone'})
        with self.assertRaises(ToolError):                                   # jamais par-dessus un script
            self.call('save_script', name='Hexagone', code='Dim x')
        self.assertEqual(pathlib.Path(os.environ['VECTORDRIVE_SCRIPTS'], 'Hexagone.vbs').read_text(encoding='utf-8'),
                         HEXAGON)
        self.assertIn({'name': 'Hexagone', 'folder': 'user'}, self.call('list_scripts')['scripts'])
        self.assertIn('NewCurve', self.call('read_script', name='Hexagone')['text'])
        for bad in (os.environ['VECTORDRIVE_SETTINGS'], '../scripts/Hexagone', 'scripts\\Hexagone'):
            with self.assertRaises(ToolError):                               # un nom, jamais un chemin
                self.call('read_script', name=bad)
        pushes = getattr(self.w, '_undo_pushes', 0)
        got = self.call('run_script', name='Hexagone')
        shapes = [it for L in self.w.canvas.doc.layers for it in L.items if isinstance(it, Shape)]
        self.assertEqual([s.id for s in shapes], [got['drawn']])
        self.assertAlmostEqual(got['bbox'][2] - got['bbox'][0], 20.0, places=3)   # r = 10 mm
        self.assertEqual(self.w._undo_pushes, pushes + 1)
        got = self.call('run_script', code=HEXAGON.replace('0.010', '0.005'))
        self.assertAlmostEqual(got['bbox'][2] - got['bbox'][0], 10.0, places=3)
        with self.assertRaises(ToolError):
            self.call('run_script', code='Dim a\na = (')                 # une erreur dite au modèle
        with self.assertRaises(ToolError):                                   # une boucle sans fin : arrêtée
            self.call('run_script', code='Dim i\nFor i = 1 To 100000000\nNext')
        many = ('Dim i\nIf NewCurve Then\n  MoveTo 0, 0, 0\n  For i = 1 To 25000\n'
                '    LineTo i * 0.0001, (i Mod 2) * 0.001, 0\n  Next\nEnd If\n')
        n = len([it for L in self.w.canvas.doc.layers for it in L.items])
        with self.assertRaises(ToolError):                                   # trop de segments (ou de pas)
            self.call('run_script', code=many)
        self.assertEqual(len([it for L in self.w.canvas.doc.layers for it in L.items]), n)   # rien d'ajouté
        got = self.call('run_script', code='Dim r\nr = InputBox("Rayon", "0.002")\nIf NewCurve Then\n'
                                           '  MoveTo 0, 0, 0\n  LineTo r, 0, 0\nEnd If\n')   # sa valeur par défaut
        self.assertAlmostEqual(got['bbox'][2] - got['bbox'][0], 2.0, places=3)
        self.assertEqual(self.call('save_script', name='Deux', code='Dim x\r\nx = 1\r\n'), {'saved': 'Deux'})
        self.assertEqual(pathlib.Path(os.environ['VECTORDRIVE_SCRIPTS'], 'Deux.vbs').read_bytes(),
                         b'Dim x\r\nx = 1\r\n')                                # pas de lignes doublées

    def test_documentation_and_commands(self):
        from vectordrive.agent import tools as AT
        from vectordrive.agent.protocol import ToolError
        self.assertIn('NewCurve', self.call('read_documentation', topic='scripts')['text'])
        self.call('read_documentation', topic='commands')                   # le guide, ou une note s'il manque
        got = self.call('list_commands', query='rotation')['commands']
        self.assertTrue(any(c['key'] == 'rot90' for c in got))
        keys = {c['key'] for c in self.call('list_commands')['commands']}
        self.assertFalse(keys & {'save', 'clear_history', 'doc_next'})       # les refusées : pas montrées
        for key in ('save', 'saveas', 'export', 'print', 'quit', 'doc_close', 'settings_export', 'save_symbol',
                    'clear_history', 'setup_sheet', 'cam_post', 'proof', 'doc_next', 'new', 'open', 'options_general',
                    'settings_import', 'step_depot_folder', 'machine_x', 'assistant_ia'):
            self.assertTrue(AT.denied(key), key)
        for key in ('rot90', 'close_contour', 'open_contour', 'mirror_h', 'delete'):
            self.assertFalse(AT.denied(key), key)
        with self.assertRaises(ToolError):
            self.call('run_command', key='save')                            # jamais une sauvegarde
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        s = Shape(path=geom.Path([geom.rect(0, 0, 40, 10)]), tool=0)
        self.w.canvas.doc.add(s)
        self.w.canvas.select([s])
        self.call('run_command', key='rot90')
        bb = self.w.canvas.selection_bbox()
        self.assertAlmostEqual(bb[2] - bb[0], 10.0, places=3)                # tourné d'un quart de tour
        self.w.undo()
        shapes = [it for L in self.w.canvas.doc.layers for it in L.items if isinstance(it, Shape)]
        self.assertAlmostEqual(shapes[0].bbox()[2] - shapes[0].bbox()[0], 40.0, places=3)

    def test_the_memory_window(self):
        from vectordrive.agent import tools as AT
        p = self.w.show_assistant_panel()
        d = p.edit_memory(exec_dialog=False)
        d.edit.setPlainText('Toujours des coins arrondis de 2 mm.')
        d.accept()
        self.assertEqual(AT.memory_text(), 'Toujours des coins arrondis de 2 mm.')
        p.shutdown()


if __name__ == '__main__':
    unittest.main()
