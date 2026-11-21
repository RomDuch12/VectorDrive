"""Round 1135 (demande du 20/11, 22 h) : les pièces STEP de l'assistant, niveau expert — `step_build`, des corps
décrits un à un, vérifiés ; le refus dit où ; « dry_run » mesure sans écrire."""
import json
import math
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1135.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

import tests  # noqa: E402,F401

BEFORE = 'avant : pas de description experte'
FLANGE = {'bodies': [{'name': 'flange', 'slabs': [{'z0': 0, 'z1': 12, 'loops': [
    {'rect': [-40, -40, 40, 40], 'r': 6}, {'circle': [0, 0, 10]}, {'circle': [30, 30, 3.2]},
    {'circle': [-30, 30, 3.2]}, {'circle': [-30, -30, 3.2]}, {'circle': [30, -30, 3.2]}]}],
    'holes': [{'z0': 8, 'z1': 12, 'loop': {'circle': [0, 0, 16]}}]}]}


class Build(unittest.TestCase):

    def setUp(self):
        from vectordrive.agent import tools as T
        from vectordrive.ui.main_window import MainWindow
        self.base = pathlib.Path(tempfile.mkdtemp())
        env = mock.patch.dict(os.environ, {'VECTORDRIVE_ASSISTANT_DIR': str(self.base / 'assistant')})
        env.start()
        self.addCleanup(env.stop)
        self.w = MainWindow()
        self.addCleanup(self.clean)
        self.tools = T.ToolSet(self.w, extended=True)
        self.assertIn('step_build', self.tools.names(), BEFORE)
        self.T = T
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

    def test_declared_documented(self):
        from vectordrive.agent import chat
        self.assertEqual(self.T.TOOL_GROUPS['step_build'], 'step')
        self.assertNotIn('step_build', self.T.ToolSet(self.w, extended=True, without=('step',)).names())
        doc = self.call('read_documentation', topic='step')['text']
        self.assertIn('"slabs"', doc)
        self.assertIn('"revolve"', doc)
        self.assertIn('step_build', chat.SYSTEM)

    def test_documented_example_written_and_read_back(self):
        dry = self.call('step_build', spec=FLANGE, dry_run=True)
        self.assertTrue(dry['dry_run'])
        self.assertFalse(self.folder.exists() and any(self.folder.iterdir()), 'rien d’écrit')
        expect = ((6400 - (4 - math.pi) * 36) * 12 - math.pi * (100 * 8 + 256 * 4)   # le perçage sous le lamage
                  - 4 * math.pi * 3.2 ** 2 * 12)
        self.assertAlmostEqual(dry['volume_mm3'], expect, delta=expect * 0.01)
        got = self.call('step_build', spec=FLANGE, name='Bride')
        self.assertTrue(got['read_back']['ok'], got['read_back'])
        self.assertEqual(pathlib.Path(got['saved']).name, 'Bride.step')
        self.assertEqual([round(x) for x in got['size_mm']], [80, 80, 12])

    def test_revolve_part_and_placement(self):
        spec = {'bodies': [
            {'name': 'axe', 'revolve': {'profile': [[0, 10], [20, 10], [20, 6], [50, 6], [52, 5]]},
             'color': [0.8, 0.6, 0.3]},
            {'name': 'vis', 'part': 'chc', 'values': {'size': 'M4', 'length': 10},
             'placement': {'origin': [40, 0, 0], 'rotate_z': 30}},
            {'name': 'cale', 'slabs': [{'z0': 0, 'z1': 5, 'loops': [{'regular': [6, 20], 'cx': 0, 'cy': 0},
                                                                    {'circle': [0, 0, 4]}]}],
             'placement': {'origin': [0, 0, -5], 'z_axis': [0, 0, 1]}}]}
        got = self.call('step_build', spec=spec)
        self.assertEqual(got['bodies'], 3)
        self.assertEqual(pathlib.Path(got['saved']).name, 'assemblage.step')
        self.assertTrue(got['read_back']['ok'], got['read_back'])
        x0, y0, z0, x1, y1, z1 = got['bounds_mm']
        self.assertAlmostEqual(z1, 52, delta=0.01)
        self.assertAlmostEqual(z0, -10, delta=0.01)             # la tige de la vis sous Z = 0
        self.assertGreater(x1, 42)                               # la tête de la vis en X = 40

    def test_refusals_name_the_place(self):
        bad = {'bodies': [{'slabs': [{'z0': 0, 'z1': 5, 'loops': [{'circle': [0, 0, 10]}]}]},
                          {'name': 'b', 'slabs': [{'z0': 0, 'z1': 5, 'loops': [{'circle': [0, 0, -1]}]}]}]}
        self.assertIn('bodies[1].slabs[0].loops[0].circle', self.refused('step_build', spec=bad, dry_run=True))
        cross = {'bodies': [{'name': 'x', 'slabs': [{'z0': 0, 'z1': 5, 'loops': [{'circle': [0, 0, 10]},
                                                                                {'circle': [9, 0, 3]}]}]}]}
        self.assertIn('bodies[0] (x)', self.refused('step_build', spec=cross, dry_run=True))
        gap = {'bodies': [{'slabs': [{'z0': 0, 'z1': 5, 'loops': [{'rect': [0, 0, 10, 10]}]},
                                     {'z0': 6, 'z1': 8, 'loops': [{'rect': [0, 0, 10, 10]}]}]}]}
        self.refused('step_build', spec=gap, dry_run=True)
        for spec in ({}, {'bodies': []}, {'bodies': [{}]}, {'bodies': [{'slabs': [], 'revolve': {}}]},
                     {'bodies': [{'slabs': [{'z0': 0, 'z1': 1, 'loops': [{'circle': [0, 0, 1], 'rect': [0, 0, 1, 1]}]}]}]},
                     {'bodies': [{'slabs': [{'z0': 0, 'z1': 1, 'loops': [{'circle': [0, 0, float('nan')]}]}]}]},
                     {'bodies': [{'slabs': [{'z0': 0, 'z1': 1, 'loops': [{'circle': [0, 0, True]}]}]}]},
                     {'bodies': [{'part': 'rien'}]},
                     {'bodies': [{'part': 'ecrou', 'holes': []}]},
                     {'bodies': [{'revolve': {'profile': [[0, 0], [5, 3]]}}]},
                     {'bodies': [{'slabs': [{'z0': 0, 'z1': 1, 'loops': [{'circle': [0, 0, 1]}]}],
                                  'placement': {'z_axis': [0, 0, 0]}}]},
                     {'bodies': [{'slabs': [{'z0': 0, 'z1': 1, 'loops': [{'circle': [0, 0, 1]}]}],
                                  'holes': [{'z0': 5, 'z1': 6, 'loop': {'circle': [0, 0, 0.5]}}]}]},
                     {'bodies': [{'slabs': [{'z0': 0, 'z1': 1, 'loops': [{'circle': [0, 0, 1]}]}]}] * 51}):
            self.refused('step_build', spec=spec, dry_run=True)
        self.assertFalse(self.folder.exists() and any(self.folder.iterdir()), 'aucun fichier pour un refus')

    def test_holes_cut_only_material(self):
        plate = [{'z0': 0, 'z1': 10, 'loops': [{'rect': [-20, -20, 20, 20]}]}]
        cb = {'z0': 6, 'z1': 10, 'loop': {'circle': [0, 0, 8]}}
        drill = {'z0': 0, 'z1': 10, 'loop': {'circle': [0, 0, 3]}}
        vol = 1600 * 10 - math.pi * (9 * 6 + 64 * 4)
        for holes in ([cb, drill], [drill, cb]):                 # l'ordre des trous ne compte pas
            got = self.call('step_build', spec={'bodies': [{'slabs': plate, 'holes': holes}]}, dry_run=True)
            self.assertAlmostEqual(got['volume_mm3'], vol, delta=vol * 0.01, msg=str(holes))
        # un trou qui entoure toute la pièce, ou posé à côté : il ajouterait de la matière
        for loop in ({'circle': [0, 0, 40]}, {'circle': [50, 0, 3]}):
            msg = self.refused('step_build', spec={'bodies': [{'slabs': plate, 'holes': [
                {'z0': 0, 'z1': 10, 'loop': loop}]}]}, dry_run=True)
            self.assertIn('bodies[0].holes[0]', msg)
        # une fraisure conique sur deux tranches : le cône suit la hauteur du trou
        two = [{'z0': 0, 'z1': 5, 'loops': [{'rect': [-20, -20, 20, 20]}]},
               {'z0': 5, 'z1': 10, 'loops': [{'rect': [-20, -20, 20, 20]}]}]
        cone = {'z0': 0, 'z1': 10, 'loop': {'circle': [0, 0, 2], 'r_top': 6}}
        got = self.call('step_build', spec={'bodies': [{'slabs': two, 'holes': [cone]}]}, dry_run=True)
        vol = 1600 * 10 - math.pi * 10 / 3 * (4 + 12 + 36)
        self.assertAlmostEqual(got['volume_mm3'], vol, delta=vol * 0.01)
        # à cheval sur un perçage (son premier point dedans, le reste dans la matière) : refusé, pas oublié
        bored = [{'z0': 0, 'z1': 10, 'loops': [{'rect': [-20, -20, 20, 20]}, {'circle': [0, 0, 5]}]}]
        msg = self.refused('step_build', spec={'bodies': [{'slabs': bored, 'holes': [
            {'z0': 0, 'z1': 10, 'loop': {'circle': [-4, 0, 3]}}]}]}, dry_run=True)
        self.assertIn('partly overlaps', msg)
        # une fraisure plus étroite que le perçage en bas, plus large en haut : jugée sur toute la tranche
        thin = [{'z0': 0, 'z1': 10, 'loops': [{'rect': [-20, -20, 20, 20]}, {'circle': [0, 0, 4]}]}]
        msg = self.refused('step_build', spec={'bodies': [{'slabs': thin, 'holes': [
            {'z0': 4, 'z1': 10, 'loop': {'circle': [0, 0, 3], 'r_top': 9}}]}]}, dry_run=True)
        self.assertIn('split it', msg)
        conic = [{'z0': 0, 'z1': 10, 'loops': [{'rect': [-20, -20, 20, 20]}, {'circle': [0, 0, 3], 'r_top': 9}]}]
        self.refused('step_build', spec={'bodies': [{'slabs': conic, 'holes': [
            {'z0': 0, 'z1': 10, 'loop': {'circle': [0, 0, 5.5]}}]}]}, dry_run=True)
        # une poche étagée (un bord commun), dans les deux ordres ; le même trou deux fois
        block = [{'z0': 0, 'z1': 10, 'loops': [{'rect': [-30, -30, 30, 30]}]}]
        wide = {'z0': 5, 'z1': 10, 'loop': {'rect': [0, 0, 20, 10]}}
        deep = {'z0': 2, 'z1': 10, 'loop': {'rect': [0, 0, 10, 10]}}
        vol = 3600 * 10 - 200 * 5 - 100 * 3
        for holes in ([wide, deep], [deep, wide], [wide, deep, deep]):
            got = self.call('step_build', spec={'bodies': [{'slabs': block, 'holes': holes}]}, dry_run=True)
            self.assertAlmostEqual(got['volume_mm3'], vol, delta=vol * 0.01, msg=str(holes))
        # une sphère contre un cône : jugée aussi où leurs pentes s'égalent
        coned = [{'z0': 0, 'z1': 5, 'loops': [{'rect': [-20, -20, 20, 20]}, {'circle': [0, 0, 8.5], 'r_top': 0.3}]}]
        self.refused('step_build', spec={'bodies': [{'slabs': coned, 'holes': [
            {'z0': 0, 'z1': 5, 'loop': {'circle': [0, 0, 5], 'sphere': [0, 5]}}]}]}, dry_run=True)
        # une sphère dans une tranche : son rayon suit la sphère (r n'est pas lu)
        ball = {'bodies': [{'slabs': [{'z0': 0, 'z1': 5, 'loops': [{'circle': [0, 0, 1], 'sphere': [0, 10]}]}]}]}
        got = self.call('step_build', spec=ball, dry_run=True)
        vol = math.pi * (100 * 5 - 125 / 3)
        self.assertAlmostEqual(got['volume_mm3'], vol, delta=vol * 0.01)

    def test_revolve_holes_and_bad_polygons(self):
        spec = {'bodies': [{'revolve': {'profile': [[0, 10], [20, 10]], 'holes': [
            {'z0': 0, 'z1': 20, 'loop': {'circle': [0, 0, 4]}}, {'z0': 15, 'z1': 20, 'loop': {'circle': [0, 0, 6]}}]}}]}
        got = self.call('step_build', spec=spec, dry_run=True)
        vol = math.pi * (100 * 20 - 16 * 15 - 36 * 5)
        self.assertAlmostEqual(got['volume_mm3'], vol, delta=vol * 0.01)
        out = {'bodies': [{'revolve': {'profile': [[0, 10], [20, 10]], 'holes': [
            {'z0': 0, 'z1': 20, 'loop': {'circle': [0, 0, 30]}}]}}]}
        self.assertIn('revolve.holes[0]', self.refused('step_build', spec=out, dry_run=True))
        eight = {'bodies': [{'slabs': [{'z0': 0, 'z1': 2, 'loops': [
            {'polygon': [[0, 0], [10, 10], [10, 0], [0, 10]]}]}]}]}
        self.assertIn('crosses itself', self.refused('step_build', spec=eight, dry_run=True))
        twice = {'bodies': [{'slabs': [{'z0': 0, 'z1': 2, 'loops': [
            {'polygon': [[0, 0], [10, 0], [10, 10], [0, 0]]}]}]}]}
        self.assertIn('the same', self.refused('step_build', spec=twice, dry_run=True))


if __name__ == '__main__':
    unittest.main()
