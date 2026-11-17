"""Round 1072 : réponse du 17/11 à la question 48 (« liste unique »), 1re étape — un plugin met ses opérations dans la
liste des opérations du panneau FAO, comme des lignes qu'on place entre les parcours ; le programme les reçoit à leur
rang."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1072.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

BEFORE = 'avant : un plugin ne pouvait pas mettre ses opérations dans la liste du panneau FAO'
KEY = 'essai_ops'


class Provider:
    """Un plugin d'essai : ses opérations dans `doc.extra[KEY]` ([{'id', 'label', 'on'}])."""
    label = 'Essai'
    posts = ()

    def __init__(self):
        self.calls = []

    def rows(self, doc):
        return [{'ref': o['id'], 'label': o['label'], 'tool': 'T9', 'tip': 'bulle ' + o['id'],
                 'enabled': o.get('on', True)} for o in doc.extra.get(KEY, [])]

    def set_enabled(self, doc, ref, on):
        self.calls.append(('set_enabled', ref, on))
        for o in doc.extra.get(KEY, []):
            if o['id'] == ref:
                o['on'] = on

    def edit(self, win, ref):
        self.calls.append(('edit', ref))

    def reload(self, win, ref, ids):
        self.calls.append(('reload', ref, list(ids)))
        return True

    def remove(self, win, ref):
        self.calls.append(('remove', ref))
        doc = win.canvas.doc
        doc.extra[KEY] = [o for o in doc.extra.get(KEY, []) if o['id'] != ref]
        return True


def register(provider):
    from vectordrive import plugins
    assert hasattr(plugins.Api, 'add_operation_provider'), BEFORE
    plugins.Api(plugins.REGISTRY, None).add_operation_provider(KEY, provider)


def unregister():
    from vectordrive import plugins
    getattr(plugins.REGISTRY, 'op_providers', {}).pop(KEY, None)


class Model(unittest.TestCase):

    def setUp(self):
        self.p = Provider()
        register(self.p)
        self.addCleanup(unregister)

    def doc_setup(self, ops=('a', 'b')):
        from vectordrive.cam import model
        from vectordrive.core.document import Document
        d = Document()
        d.extra[KEY] = [{'id': k, 'label': 'Op ' + k.upper()} for k in ops]
        s = model.CamSetup()
        s.operations = [model.Operation(name='Gravure', kind='gravure')]
        return d, s

    def test_sync_adds_follows_and_removes(self):
        from vectordrive.cam import external
        d, s = self.doc_setup()
        changed, gone = external.sync(s, d, s.post)
        self.assertTrue(changed)
        self.assertEqual([o.name for o in s.operations], ['Gravure', 'Op A', 'Op B'])   # après, dans son ordre
        self.assertTrue(all(external.is_external(o) for o in s.operations[1:]))
        self.assertEqual(s.operations[1].params['ref'], 'a')
        self.assertEqual(external.sync(s, d, s.post), (False, []))                     # rien de neuf
        s.operations.insert(0, s.operations.pop(2))                                     # B placée en tête
        d.extra[KEY][0]['label'] = 'Op A bis'
        d.extra[KEY][0]['on'] = False
        self.assertTrue(external.sync(s, d, s.post)[0])
        self.assertEqual([o.name for o in s.operations], ['Op B', 'Gravure', 'Op A bis'])   # sa place gardée
        self.assertFalse(s.operations[2].enabled)
        gone_id = s.operations[0].id
        d.extra[KEY] = d.extra[KEY][:1]                                                  # B retirée par le plugin
        self.assertEqual(external.sync(s, d, s.post), (True, [gone_id]))
        self.assertEqual([o.name for o in s.operations], ['Gravure', 'Op A bis'])

    def test_kept_through_the_document(self):
        from vectordrive.cam import external, model
        d, s = self.doc_setup()
        external.sync(s, d, s.post)
        model.store(d, s)
        back = model.setup_of(d)
        self.assertEqual([(o.kind, o.instruction, o.params.get('ref')) for o in back.operations[1:]],
                         [('instruction', 'externe', 'a'), ('instruction', 'externe', 'b')])

    def test_duplicate_removed(self):
        import copy
        from vectordrive.cam import external
        d, s = self.doc_setup(('a',))
        external.sync(s, d, s.post)
        twin = copy.deepcopy(s.operations[1])
        twin.id = 'autre'
        s.operations.append(twin)                                                        # « Dupliquer »
        self.assertEqual(external.sync(s, d, s.post), (True, ['autre']))

    def test_other_machine_kept_not_written(self):
        from vectordrive.cam import external, strategies
        d, s = self.doc_setup(('a',))
        external.sync(s, d, s.post)
        op = s.operations[1]
        tp = strategies.compute(d, s, op)
        self.assertEqual(tp.cycles, [{'kind': 'instruction', 'name': 'externe', 'params': op.params}], BEFORE)
        self.assertEqual(tp.warnings, [])
        self.p.posts = ('une_autre_machine',)
        self.assertEqual(external.sync(s, d, s.post), (False, []))                       # gardée, pas retirée
        self.assertEqual(len(s.operations), 2)
        tp = strategies.compute(d, s, op)
        self.assertEqual(tp.cycles, [])
        self.assertTrue(tp.warnings)
        s.post = 'une_autre_machine'
        self.assertEqual(strategies.compute(d, s, op).cycles[0]['params']['ref'], 'a')

    def test_plugin_gone(self):
        from vectordrive.cam import external, strategies
        d, s = self.doc_setup(('a',))
        external.sync(s, d, s.post)
        unregister()
        self.assertEqual(external.sync(s, d, s.post), (False, []))
        self.assertTrue(strategies.compute(d, s, s.operations[1]).warnings)

    def test_faulty_plugin(self):
        from vectordrive.cam import external
        d, s = self.doc_setup(('a',))
        external.sync(s, d, s.post)

        def boom(doc):
            raise RuntimeError('essai')
        self.p.rows = boom
        self.assertEqual(external.sync(s, d, s.post), (False, []))                       # rien retiré
        self.assertEqual(len(s.operations), 2)


class Panel(unittest.TestCase):

    def setUp(self):
        from vectordrive.cam import model
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        from vectordrive.ui.main_window import MainWindow
        self.pr = Provider()
        register(self.pr)
        self.addCleanup(unregister)
        self.w = MainWindow()
        self.addCleanup(self.close)
        self.p = self.w.cam_panel
        doc = self.w.canvas.doc
        sh = Shape(path=geom.Path([geom.rect(0, 0, 20, 14)]), tool=0)
        doc.add(sh)
        s = self.p.setup()
        tool = model.CamTool(name='Cyl 2', diameter=2.0, number=1, cut_length=7, step_down=1.0, spindle=20000)
        s.tools = [tool]
        s.operations = [model.Operation(name='Gravure', kind='gravure', tool_id=tool.id, items=[sh.id], depth=0.2)]
        self.p.save(s)
        doc.extra[KEY] = [{'id': 'a', 'label': 'Op A'}]
        self.w.modified = False
        self.p.refresh()

    def close(self):
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()

    def labels(self):
        t = self.p.ops
        return [t.item(r, 0).text().replace(' (1 obj.)', '') for r in range(t.rowCount())]

    def test_a_row_after_the_operations(self):
        self.assertEqual(self.labels(), ['Gravure', 'Op A'], BEFORE)
        t = self.p.ops
        self.assertEqual(t.item(1, 1).text(), 'Essai')
        self.assertEqual(t.item(1, 2).text(), 'T9')
        self.assertEqual(t.item(1, 0).toolTip(), 'bulle a')
        self.assertFalse(self.w.modified)                                                # rien fait par l'utilisateur

    def test_check_edit_reload_remove(self):
        t = self.p.ops
        t.item(1, 0).setCheckState(Qt.CheckState.Unchecked)
        self.assertIn(('set_enabled', 'a', False), self.pr.calls)
        self.assertFalse(self.p.setup().operations[1].enabled)
        self.p._select_row(t, 1)
        self.assertIsNone(self.p.edit_op())
        self.assertIn(('edit', 'a'), self.pr.calls)
        self.assertTrue(self.p.retarget_op(1, ['x']))
        self.assertIn(('reload', 'a', ['x']), self.pr.calls)
        self.p._select_row(t, 1)
        self.p.remove_op()
        self.assertIn(('remove', 'a'), self.pr.calls)
        self.assertEqual(self.labels(), ['Gravure'])

    def test_placed_between_and_written_in_order(self):
        t = self.p.ops
        self.p._select_row(t, 1)
        self.p.move_op(-1)                                                               # avant la gravure
        self.assertEqual(self.labels(), ['Op A', 'Gravure'])
        self.assertEqual([o.name for o in self.p.setup().operations], ['Op A', 'Gravure'])
        paths = self.p.compute()
        self.assertEqual([tp.name for tp in paths], ['Op A', 'Gravure'])
        self.assertEqual(paths[0].cycles[0]['params']['ref'], 'a')
        self.w.canvas.doc.extra[KEY].append({'id': 'b', 'label': 'Op B'})               # le plugin en ajoute une
        self.p.refresh()
        self.assertEqual(self.labels(), ['Op A', 'Gravure', 'Op B'])
        self.w.canvas.doc.extra[KEY] = [{'id': 'b', 'label': 'Op B'}]                   # et en retire une
        self.p.refresh()
        self.assertEqual(self.labels(), ['Gravure', 'Op B'])
        self.assertNotIn('Op A', [tp.name for tp in self.p.toolpaths])                  # pas de parcours orphelin



class Ownership(Panel):
    """Qui retire, coche ou copie une opération de plugin : le plugin quand il est là et écrit pour cette machine ;
    sinon, elle se retire comme une autre."""

    test_a_row_after_the_operations = test_check_edit_reload_remove = None      # déjà dans Panel
    test_placed_between_and_written_in_order = None

    def test_checkbox_stays_without_set_enabled(self):
        del Provider.set_enabled                                                         # facultatif
        self.addCleanup(setattr, Provider, 'set_enabled', Model_set_enabled)
        self.p.ops.item(1, 0).setCheckState(Qt.CheckState.Unchecked)
        self.p.refresh()
        self.assertFalse(self.p.setup().operations[1].enabled)                          # décochée, elle le reste
        self.w.canvas.doc.extra[KEY][0]['on'] = False                                   # le plugin la décoche,
        self.p.refresh()
        self.w.canvas.doc.extra[KEY][0]['on'] = True                                    # puis la recoche : suivi
        self.p.refresh()
        self.assertTrue(self.p.setup().operations[1].enabled)

    def test_removed_when_the_plugin_is_gone(self):
        unregister()
        self.p.refresh()
        self.assertEqual(self.labels(), ['Gravure', 'Op A'])                            # gardée, sa place aussi
        self.p._select_row(self.p.ops, 1)
        self.assertIsNone(self.p.edit_op())
        self.p._select_row(self.p.ops, 1)
        self.p.remove_op()
        self.assertEqual(self.labels(), ['Gravure'], 'avant : impossible à retirer sans son plugin')
        self.assertNotIn(('remove', 'a'), self.pr.calls)

    def test_other_machine_removed_here_not_in_the_plugin(self):
        self.pr.posts = ('une_autre_machine',)
        self.p.refresh()
        self.p._select_row(self.p.ops, 1)
        self.p.remove_op()
        self.assertEqual(self.labels(), ['Gravure'])
        self.assertNotIn(('remove', 'a'), self.pr.calls)                                # le plugin la garde
        self.assertEqual(len(self.w.canvas.doc.extra[KEY]), 1)

    def test_not_duplicated_nor_kept_in_a_process(self):
        from vectordrive.cam import templates
        self.p._select_row(self.p.ops, 1)
        self.assertIsNone(self.p.duplicate_op())
        self.assertEqual(self.labels(), ['Gravure', 'Op A'])
        tpl = templates.from_setup(self.p.setup(), 'essai')
        self.assertEqual([o['name'] for o in tpl['operations']], ['Gravure'])

    def test_paths_list_follows(self):
        self.p.compute()
        self.assertEqual(self.p.paths.count(), 2)
        self.w.canvas.doc.extra[KEY] = []
        self.p.refresh()
        self.assertEqual([tp.name for tp in self.p.toolpaths], ['Gravure'])
        self.assertEqual(self.p.paths.count(), 1)                                       # la liste aussi


Model_set_enabled = Provider.set_enabled


if __name__ == '__main__':
    unittest.main()
