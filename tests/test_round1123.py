"""Round 1123 (demande du 20/11, 15 h 59) : « Assistant IA peut générer des programmes FAO, sélectionner la machine, et
retoucher le programme à la demande » — les outils FAO de l'assistant."""
import json
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1123.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from tests import _posts  # noqa: E402
from vectordrive.core import geom  # noqa: E402
from vectordrive.core.document import Shape  # noqa: E402

BEFORE = 'avant : l’assistant ne touchait pas à la FAO'
CAM = ('cam_machines', 'cam_set_machine', 'cam_presets', 'cam_tools', 'cam_operations', 'cam_operation_settings',
       'cam_add_operation', 'cam_edit_operation', 'cam_remove_operation', 'cam_move_operation', 'cam_compute',
       'cam_program')


class CamTools(unittest.TestCase):

    def setUp(self):
        from vectordrive.agent.tools import ToolSet
        from vectordrive.ui.main_window import MainWindow
        self.posts = _posts.registered('essai1')
        self.posts.__enter__()
        self.posts2 = _posts.registered('essai2')
        self.posts2.__enter__()
        self.w = MainWindow()
        self.addCleanup(self.clean)
        self.w.cam_panel._fill_posts()
        self.tools = ToolSet(self.w, extended=True)
        for name in CAM:
            self.assertIn(name, self.tools.names(), BEFORE)
        self.sh = Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]), tool=0)
        self.w.canvas.doc.add(self.sh)

    def clean(self):
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()
        app.processEvents()
        self.posts2.__exit__(None, None, None)
        self.posts.__exit__(None, None, None)

    def call(self, tool, **args):
        return json.loads(self.tools.call(tool, args)[0]['text'])

    def refused(self, tool, **args):
        from vectordrive.agent.protocol import ToolError
        steps = len(self.w._undo)
        with self.assertRaises(ToolError) as cm:
            self.tools.call(tool, args)
        self.assertEqual(len(self.w._undo), steps, 'un refus ne laisse pas de pas d’annulation')
        return str(cm.exception)

    def add(self, **kw):
        got = self.call('cam_add_operation', preset='decoupe', ids=[self.sh.id], **kw)
        return got['operation']

    def test_machines_and_choice(self):
        got = self.call('cam_machines')
        keys = [m['key'] for m in got['machines']]
        self.assertIn('essai1', keys)
        self.assertIn('essai2', keys)
        other = next(k for k in ('essai1', 'essai2') if k != got['current'])
        steps = len(self.w._undo)
        self.assertTrue(self.call('cam_set_machine', key=other)['changed'])
        self.assertEqual(self.w.cam_panel.setup().post, other)
        self.assertEqual(len(self.w._undo), steps + 1, 'un pas d’annulation')
        self.w.undo()
        self.assertNotEqual(self.w.cam_panel.setup().post, other, 'Ctrl+Z rend la machine d’avant')
        self.assertIn('no machine', self.refused('cam_set_machine', key='inconnue'))

    def test_add_operation_computed(self):
        op = self.add()
        from vectordrive.ui.cam_panel import presets
        self.assertEqual(op['kind'], presets()['decoupe'][1])
        self.assertTrue(op['computed'], 'calculée')
        self.assertEqual(op['objects'], 1)
        ops = self.call('cam_operations')['operations']
        self.assertEqual([o['id'] for o in ops], [op['id']])
        self.w.undo()
        self.assertEqual(self.w.cam_panel.setup().operations, [], 'un pas d’annulation : Ctrl+Z la retire')

    def test_add_with_settings_tool_and_name(self):
        op = self.add()
        tid = self.call('cam_tools')['tools'][0]['id']
        op2 = self.call('cam_add_operation', preset='decoupe', ids=[self.sh.id], tool_id=tid, name='Détourage',
                        settings={'depth': 2.5, 'climb': False})['operation']
        o = next(x for x in self.w.cam_panel.setup().operations if x.id == op2['id'])
        self.assertEqual((o.name, o.depth, o.climb, o.tool_id), ('Détourage', 2.5, False, tid))
        self.assertTrue(op2['computed'])
        self.assertNotEqual(op['id'], op2['id'])

    def test_settings_checked_before_any_change(self):
        self.assertIn('not a setting', self.refused('cam_add_operation', preset='decoupe', ids=[self.sh.id],
                                                    settings={'kind': 'poche'}))
        self.assertIn('expected', self.refused('cam_add_operation', preset='decoupe', ids=[self.sh.id],
                                               settings={'depth': 'deux'}))
        self.assertIn('no preset', self.refused('cam_add_operation', preset='nimporte'))
        self.assertIn('no tool', self.refused('cam_add_operation', preset='decoupe', ids=[self.sh.id],
                                              tool_id='x'))
        self.w.canvas.select([])
        self.assertIn('nothing to machine', self.refused('cam_add_operation', preset='decoupe'))
        self.assertEqual(self.w.cam_panel.setup().operations, [])

    def test_edit_recomputes(self):
        op = self.add()
        tp0 = next(t for t in self.w.cam_panel.toolpaths if t.op_id == op['id'])
        got = self.call('cam_edit_operation', id=op['id'], settings={'depth': 3.0}, name='Plus profond')
        self.assertEqual(got['operation']['name'], 'Plus profond')
        o = next(x for x in self.w.cam_panel.setup().operations if x.id == op['id'])
        self.assertEqual(o.depth, 3.0)
        tp1 = next(t for t in self.w.cam_panel.toolpaths if t.op_id == op['id'])
        self.assertIsNot(tp1, tp0, 'recalculée')
        self.assertLess(min(m.z for m in tp1.moves), min(m.z for m in tp0.moves) - 0.4)
        settings = self.call('cam_operation_settings', id=op['id'])['settings']
        self.assertEqual(settings['depth'], 3.0)
        self.assertIn('nothing to change', self.refused('cam_edit_operation', id=op['id']))
        self.assertIn('no operation', self.refused('cam_edit_operation', id='x', name='a'))

    def test_disable_removes_its_toolpath(self):
        op = self.add()
        self.call('cam_edit_operation', id=op['id'], enabled=False)
        self.assertFalse(any(t.op_id == op['id'] for t in self.w.cam_panel.toolpaths))
        self.assertTrue(self.call('cam_compute')['computed'] == [])

    def test_move_and_remove(self):
        a, b = self.add(), self.add()
        got = self.call('cam_move_operation', id=b['id'], index=0)
        self.assertEqual(got['order'], [b['id'], a['id']])
        self.assertEqual([t.op_id for t in self.w.cam_panel.toolpaths][:1], [b['id']], 'les parcours suivent')
        self.call('cam_remove_operation', id=a['id'])
        self.assertEqual([o.id for o in self.w.cam_panel.setup().operations], [b['id']])
        self.assertFalse(any(t.op_id == a['id'] for t in self.w.cam_panel.toolpaths))
        self.w.undo()
        self.assertEqual(len(self.w.cam_panel.setup().operations), 2, 'Ctrl+Z la rend')

    def test_compute_and_program(self):
        op = self.add()
        self.assertEqual(self.call('cam_compute', ids=[op['id']])['computed'], [op['id']])
        prog = self.call('cam_program')
        self.assertTrue(prog['files'], prog)
        text = prog['files'][0]['text']
        self.assertIn('(ESSAI', text)
        self.assertIn('G1', text)
        self.assertEqual(os.listdir(tempfile.gettempdir()).count(prog['files'][0]['name']), 0)

    def test_fixed_fields_bounds_and_choices(self):
        op = self.add()
        tid = self.call('cam_tools')['tools'][0]['id']
        for k, v in (('tool_id', tid), ('ref_tool_id', tid), ('name', 'x'), ('enabled', False), ('gravure_rule', 0),
                     ('finish_rule', 0), ('link_rule', 0), ('sweep_rule', 0), ('restart_from', 1),
                     ('restart_to', 2), ('instruction', 'externe'), ('model_path', 'C:/x.stp'),
                     ('wrap_model', 'C:/x.stp')):
            self.assertIn('not a setting', self.refused('cam_edit_operation', id=op['id'], settings={k: v}), k)
        for k, v in (('copies_x', 100000), ('laser_passes', 10 ** 6), ('tabs', -1), ('resolution', 1e-6),
                     ('step_down', 0.001), ('depth', 1e9), ('ramp_angle', 95.0), ('side', 'gauche'),
                     ('thread', 'M99'), ('wobble', 'zigzag'), ('climb', 1), ('depth', 'deux'), ('feed', -100.0),
                     ('spindle', -1.0), ('step_down', -0.5), ('safe_z', -1.0), ('depth', 0.0), ('depth', 600.0)):
            self.assertIn('expected', self.refused('cam_edit_operation', id=op['id'], settings={k: v}), k)
        self.assertIn("'interieur'", self.refused('cam_edit_operation', id=op['id'], settings={'side': 'gauche'}))
        got = self.call('cam_edit_operation', id=op['id'], settings={'side': 'interieur', 'step_down': 0.0,
                                                                      'pass_depths': '0,3 0,2', 'depth': 1.23456})
        o = next(x for x in self.w.cam_panel.setup().operations if x.id == op['id'])
        self.assertEqual((o.side, o.pass_depths, o.depth), ('interieur', '0,3 0,2', 1.235))
        self.assertTrue(got['operation']['computed'])
        self.assertIn('"name"', self.refused('cam_edit_operation', id=op['id'], name='   '))

    def test_ranges(self):
        self.assertIn('CAM panel', self.refused('cam_add_operation', preset='gamme_relief', ids=[self.sh.id]))
        from vectordrive.ui.cam_panel import presets
        if 'gamme' in presets():
            self.assertIn('cam_edit_operation', self.refused('cam_add_operation', preset='gamme', ids=[self.sh.id],
                                                             settings={'depth': 1.0}))

    def test_frozen_objects_refused(self):
        self.sh.locked = True
        self.assertIn('frozen', self.refused('cam_add_operation', preset='decoupe', ids=[self.sh.id]))
        self.assertEqual(self.w.cam_panel.setup().operations, [])

    def test_move_keeps_linked_operations_together(self):
        a, b, c = self.add(), self.add(), self.add()
        self.call('cam_edit_operation', id=b['id'], settings={'link_previous': True})
        tp_b = next(t for t in self.w.cam_panel.toolpaths if t.op_id == b['id'])
        steps = len(self.w._undo)
        got = self.call('cam_move_operation', id=a['id'], index=2)
        self.assertEqual(got['order'], [c['id'], a['id'], b['id']], 'la liée suit sa tête, d’un bloc')
        self.assertEqual(len(self.w._undo), steps + 1, 'un seul pas, recalculs compris')
        got = self.call('cam_move_operation', id=c['id'], index=1)
        self.assertEqual(got['order'], [a['id'], b['id'], c['id']], 'jamais au milieu d’un bloc')
        got = self.call('cam_move_operation', id=b['id'], index=0)
        self.assertEqual(got['order'], [b['id'], a['id'], c['id']], 'une liée seule, comme dans le panneau')
        self.assertIn(b['id'], got['recomputed'], 'ses précédentes ont changé : recalculée')
        self.assertIsNot(next(t for t in self.w.cam_panel.toolpaths if t.op_id == b['id']), tp_b)

    def test_move_up_into_a_block_goes_before_it(self):
        a, b, c = self.add(), self.add(), self.add()
        self.call('cam_edit_operation', id=b['id'], settings={'link_previous': True})
        got = self.call('cam_move_operation', id=c['id'], index=1)
        self.assertEqual(got['order'], [c['id'], a['id'], b['id']], 'en montant : avant le bloc visé')

    def test_nothing_added_leaves_no_step(self):
        from unittest import mock
        steps, self.w.modified = len(self.w._undo), False
        with mock.patch.object(self.w.cam_panel, 'new_operation', return_value=None):
            got = self.call('cam_add_operation', preset='decoupe', ids=[self.sh.id])
        self.assertEqual(got['added'], [])
        self.assertEqual(len(self.w._undo), steps)
        self.assertFalse(self.w.modified, 'rien d’ajouté : le dessin pas marqué modifié')
        self.assertFalse(getattr(self.w, '_undo_held', False))

    def test_locked_layer_refused(self):
        self.w.canvas.doc.layer_of(self.sh).locked = True
        self.assertIn('locked layer', self.refused('cam_add_operation', preset='decoupe', ids=[self.sh.id]))

    def test_option_removes_the_group(self):
        from vectordrive.agent.tools import ToolSet
        t = ToolSet(self.w, extended=True, without=('cam',))
        self.assertFalse(set(CAM) & set(t.names()))
        from vectordrive.ui.assistant_options import TOOL_GROUPS
        self.assertEqual(TOOL_GROUPS['assistant/outils_fao'], 'cam')

    def test_mcp_server_without_cam(self):
        from vectordrive.agent.tools import ToolSet
        self.assertFalse(set(CAM) & set(ToolSet(self.w).names()), 'le serveur MCP : comme avant (outils du panneau)')


if __name__ == '__main__':
    unittest.main()
