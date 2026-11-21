"""Round 1134 (demande du 20/11, 22 h : « fournir a assistant ai le meilleur environnement de génération step pour
débutants et avances et expert ») : les outils STEP de l'assistant — catalogue (débutant), contours du dessin
(avancé) ; chaque fichier dans son dossier STEP, relu, jamais par-dessus un fichier qui n'est pas le sien."""
import json
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1134.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

import tests  # noqa: E402,F401
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402

BEFORE = 'avant : l’assistant ne faisait pas de STEP'
STEP_TOOLS = ('step_families', 'step_family', 'step_generate', 'step_from_drawing', 'step_check')


class Base(unittest.TestCase):

    def setUp(self):
        from vectordrive.agent import tools as T
        from vectordrive.ui.main_window import MainWindow
        self.T = T
        self.base = pathlib.Path(tempfile.mkdtemp())
        env = mock.patch.dict(os.environ, {'VECTORDRIVE_ASSISTANT_DIR': str(self.base / 'assistant')})
        env.start()
        self.addCleanup(env.stop)
        self.w = MainWindow()
        self.addCleanup(self.clean)
        self.tools = T.ToolSet(self.w, extended=True)
        for name in STEP_TOOLS:
            self.assertIn(name, self.tools.names(), BEFORE)
        self.folder = self.base / 'assistant' / 'copies' / 'step'

    def clean(self):
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()

    def call(self, tool, **args):
        return json.loads(self.tools.call(tool, args)[0]['text'])

    def refused(self, tool, **args):
        from vectordrive.agent.protocol import ToolError
        with self.assertRaises(ToolError) as cm:
            self.tools.call(tool, args)
        return str(cm.exception)

    def count(self):
        return sum(len(L.items) for L in self.w.canvas.doc.layers)


class Declared(Base):

    def test_group_option_and_buttons(self):
        from vectordrive.agent import ai_buttons as AB
        from vectordrive.ui import assistant_buttons as UB
        from vectordrive.ui import assistant_options as AO
        from vectordrive.ui.options import BY_KEY, value
        for n in STEP_TOOLS:
            self.assertEqual(self.T.TOOL_GROUPS[n], 'step', n)
        self.assertEqual(AO.TOOL_GROUPS['assistant/outils_step'], 'step')
        self.assertIn('assistant/outils_step', BY_KEY)
        self.assertTrue(value(self.w.settings, 'assistant/outils_step'), 'permis d’office')
        self.assertIn('step', AB.GROUPS)
        self.assertIn('step', UB.GROUP_LABELS)
        without = self.T.ToolSet(self.w, extended=True, without=('step',))
        self.assertFalse(set(STEP_TOOLS) & set(without.names()), 'retirés par l’option')
        self.assertFalse(set(STEP_TOOLS) & set(self.T.ToolSet(self.w).names()), 'pas sur le serveur local')

    def test_documentation_and_instructions(self):
        from vectordrive.agent import chat
        got = self.call('read_documentation', topic='step')
        self.assertIn('step_generate', got['text'])
        self.assertIn('step_from_drawing', got['text'])
        self.assertIn('"step"', self.refused('read_documentation', topic='rien'))
        self.assertIn('step_generate', chat.SYSTEM)

    def test_catalogue(self):
        got = self.call('step_families')
        self.assertIn('Visserie', got['categories'])
        self.assertIn('chc', [f['key'] for f in got['families']])
        only = self.call('step_families', category='visserie')['families']
        self.assertTrue(only and all(f['category'] == 'Visserie' for f in only))
        fam = self.call('step_family', key='chc')
        size = next(p for p in fam['parameters'] if p['key'] == 'size')
        self.assertIn('M4', [c['value'] for c in size['choices']])
        self.assertIn('step_families', self.refused('step_family', key='rien'))


class Generate(Base):

    def test_written_read_back_and_overwrite_rules(self):
        got = self.call('step_generate', key='chc', values={'size': 'M4', 'length': 12}, name='Vis essai')
        p = pathlib.Path(got['saved'])
        self.assertEqual(p, self.folder / 'Vis essai.step')
        self.assertTrue(p.read_text(encoding='utf-8').startswith('ISO-10303-21;'))
        self.assertTrue(got['read_back']['ok'], got['read_back'])
        self.assertEqual(got['read_back']['solids'], 1)
        for a, b in zip(got['read_back']['bounds_mm'], got['bounds_mm']):
            self.assertAlmostEqual(a, b, delta=0.2, msg='relu : le même encombrement, axe Z tel quel')
        self.assertEqual(got['bodies'], 1)
        self.assertAlmostEqual(got['size_mm'][2], 16.0, delta=0.05)    # tête 4 + tige 12
        self.assertEqual(got['values']['size'], 'M4')
        self.assertFalse(got['replaced'])
        self.assertIn('overwrite', self.refused('step_generate', key='chc', name='Vis essai'))
        again = self.call('step_generate', key='chc', values={'size': 'M5', 'length': 12}, name='Vis essai.step',
                          overwrite=True)
        self.assertTrue(again['replaced'])
        foreign = self.folder / 'Pas le sien.step'
        foreign.write_text('à l’utilisateur', encoding='utf-8')
        self.assertIn('never overwritten', self.refused('step_generate', key='ecrou', name='Pas le sien',
                                                        overwrite=True))
        self.assertEqual(foreign.read_text(encoding='utf-8'), 'à l’utilisateur', 'inchangé')
        self.assertEqual([x.name for x in self.folder.iterdir() if x.name.startswith('.~')], [], 'aucun provisoire')
        listed = self.call('step_check')
        mine = {f['name']: f['yours'] for f in listed['files']}
        self.assertEqual(mine, {'Vis essai.step': True, 'Pas le sien.step': False})
        self.assertTrue(self.call('step_check', name='Vis essai')['ok'])
        self.assertFalse(self.call('step_check', name='Pas le sien.step')['ok'], 'illisible : dit')
        self.assertIn('STEP folder', self.refused('step_check', name='../r1134.ini'))

    def test_default_name_and_bad_values(self):
        got = self.call('step_generate', key='chc', values={'size': 'M2.5', 'length': 10})
        name = pathlib.Path(got['saved']).name
        self.assertTrue(name.endswith('.step') and '.' not in name[:-5], name)
        self.assertIn('M2_5', name)
        self.refused('step_generate', key='chc', values={'size': 'M99'})
        self.refused('step_generate', key='chc', values={'inconnu': 1})
        self.refused('step_generate', key='chc', values=[1])
        self.assertIn('step_families', self.refused('step_generate', key='rien'))
        self.assertIn('name', self.refused('step_generate', key='ecrou', name='a/b'))
        self.refused('step_generate', key='chc', values={'size': 'M4', 'length': True})   # un vrai n'est pas 1
        self.refused('step_generate', key='goupille', values={'d': float('nan')})
        self.refused('step_generate', key='chc', values={'key': 'x'})
        self.refused('step_generate', key='chc', values={'length': [10]})

    def test_locked_layer_nothing_written(self):
        from vectordrive.core import solids as SO
        if not SO.available():
            self.skipTest('manifold3d absent')
        layer = self.w.canvas.doc.active_layer
        layer.locked = True
        self.addCleanup(setattr, layer, 'locked', False)
        self.assertIn('locked', self.refused('step_generate', key='ecrou', name='Bloque', add_to_drawing=True))
        self.assertFalse((self.folder / 'Bloque.step').exists(), 'refusé avant d’écrire')

    def test_added_to_drawing_one_undo_step(self):
        from vectordrive.core import solids as SO
        if not SO.available():
            self.skipTest('manifold3d absent')
        n = self.count()
        got = self.call('step_generate', key='ecrou', values={'size': 'M6'}, name='Ecrou', add_to_drawing=True)
        self.assertEqual(len(got['added']), 1)
        self.assertEqual(self.count(), n + 1)
        it = self.tools._find(got['added'][0])
        self.assertEqual(it.extra['stepgen']['key'], 'ecrou')
        self.w.undo()
        self.assertEqual(self.count(), n, 'un pas d’annulation')


class FromDrawing(Base):

    def add(self, *contours):
        sh = Shape(path=geom.Path(list(contours)), tool=0)
        self.w.canvas.doc.add(sh)
        return sh

    def test_extruded_plate_with_hole(self):
        plate = self.add(geom.rect(0, 0, 60, 40))
        hole = self.call('add_ellipse', cx=30, cy=20, rx=5, ry=5)['ids'][0]
        self.w.canvas.select([])
        self.assertIn('ids', self.refused('step_from_drawing', thickness=5))      # rien de choisi
        got = self.call('step_from_drawing', ids=[plate.id, hole], thickness=5, name='Plaque')
        self.assertTrue(got['read_back']['ok'], got['read_back'])
        self.assertEqual([round(x) for x in got['size_mm']], [60, 40, 5])
        full = 60 * 40 * 5
        self.assertAlmostEqual(got['volume_mm3'], full - 3.14159 * 25 * 5, delta=full * 0.01)
        pocket = self.call('step_from_drawing', ids=[plate.id, hole], thickness=5, inner='pockets', pocket=2,
                           name='Plaque poche')
        self.assertGreater(pocket['volume_mm3'], got['volume_mm3'])
        self.assertIn('pocket', self.refused('step_from_drawing', ids=[plate.id, hole], thickness=5,
                                             inner='pockets', pocket=9, name='x'))
        self.assertIn('thickness', self.refused('step_from_drawing', ids=[plate.id], name='y'))
        self.refused('step_from_drawing', ids=[plate.id], name='z', thickness=True)
        self.refused('step_from_drawing', ids=[plate.id], name='z', thickness=5, inner=['holes'])

    def test_turned_and_open_refused(self):
        prof = self.add(geom.rect(0, 0, 10, 20))
        got = self.call('step_from_drawing', ids=[prof.id], shape='turned', name='Axe')
        self.assertTrue(got['read_back']['ok'], got['read_back'])
        self.assertEqual([round(x) for x in got['size_mm']], [20, 20, 20])
        line = self.call('add_polyline', points=[[0, 50], [30, 50]])['ids'][0]
        self.assertIn('closed', self.refused('step_from_drawing', ids=[line], thickness=3))

    def test_extruded_added_in_place(self):
        from vectordrive.core import solids as SO
        if not SO.available():
            self.skipTest('manifold3d absent')
        plate = self.add(geom.rect(100, 50, 40, 20))
        got = self.call('step_from_drawing', ids=[plate.id], thickness=3, name='Sur place', add_to_drawing=True)
        it = self.tools._find(got['added'][0])
        x0, y0, z0, x1, y1, z1 = SO.of_item(it).bounds()
        self.assertEqual([round(v) for v in (x0, y0, z0, x1, y1, z1)], [100, 50, 0, 140, 70, 3], 'sur ses contours')


if __name__ == '__main__':
    unittest.main()
