"""Round 1073 : question 48 (liste unique), suite — une opération de plugin cochée a son parcours d'office, à sa place,
dès qu'il y a des parcours : sa place dans la liste vaut dans le programme sans « Calculer »."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1073.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

BEFORE = 'avant : l’opération de plugin n’avait de parcours qu’après « Calculer »'
KEY = 'essai_ops_1073'


class Provider:
    label = 'Essai'
    posts = ()

    def rows(self, doc):
        return [{'ref': o['id'], 'label': o['label'], 'enabled': o.get('on', True)} for o in doc.extra.get(KEY, [])]


class Paths(unittest.TestCase):

    def setUp(self):
        from vectordrive import plugins
        from vectordrive.cam import model
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        from vectordrive.ui.main_window import MainWindow
        self.pr = Provider()
        plugins.Api(plugins.REGISTRY, None).add_operation_provider(KEY, self.pr)
        self.addCleanup(lambda: plugins.REGISTRY.op_providers.pop(KEY, None))
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

    def close(self):
        self.w.modified = False
        self.w.close()
        self.w.deleteLater()

    def names(self):
        return [tp.name for tp in self.p.toolpaths]

    def add(self, ref, on=True):
        self.w.canvas.doc.extra.setdefault(KEY, []).append({'id': ref, 'label': 'Op ' + ref.upper(), 'on': on})
        self.p.refresh()

    def test_nothing_before_a_computation(self):
        self.add('a')
        self.assertEqual(self.p.toolpaths, [])                                         # rien de calculé : rien

    def test_its_path_at_once_and_at_its_place(self):
        self.p.compute()
        self.assertEqual(self.names(), ['Gravure'])
        self.add('a')
        self.assertEqual(self.names(), ['Gravure', 'Op A'], BEFORE)
        self.assertEqual(self.p.toolpaths[1].cycles[0]['params']['ref'], 'a')
        self.assertEqual(self.p.paths.count(), 2)
        self.p._select_row(self.p.ops, 1)
        self.p.move_op(-1)                                                              # placée avant la gravure
        self.assertEqual(self.names(), ['Op A', 'Gravure'])
        self.add('b')                                                                   # une autre : à la fin
        self.assertEqual(self.names(), ['Op A', 'Gravure', 'Op B'])

    def test_not_when_unchecked_or_for_another_machine(self):
        self.p.compute()
        self.add('a', on=False)
        self.assertEqual(self.names(), ['Gravure'])
        self.pr.posts = ('une_autre_machine',)
        self.add('b')
        self.assertEqual(self.names(), ['Gravure'])


    def ops(self):
        return [o.name for o in self.p.setup().operations]

    def test_counted_computed_not_an_input(self):
        self.p.compute()
        state = self.p._inputs_state()
        self.add('a')
        ext = [o.id for o in self.p.setup().operations if o.name == 'Op A'][0]
        self.assertIn(ext, self.p._memo('_whole'))                                      # comme par son formulaire
        self.assertNotIn(ext, self.p._inputs_state()[2])                               # pas une entrée du calcul
        self.assertEqual(self.p._inputs_state()[2], state[2])

    def test_label_follows_and_orphans_go(self):
        self.p.compute()
        self.add('a')
        self.w.canvas.doc.extra[KEY][0]['label'] = 'Op A2'
        self.p.refresh()
        self.assertEqual(self.names(), ['Gravure', 'Op A2'])
        self.assertEqual(self.p.toolpaths[1].cycles[0]['params']['label'], 'Op A2')
        self.pr.posts = ('une_autre_machine',)                                          # (le plugin ne la rend pas)
        s = self.p.setup()
        s.operations = [o for o in s.operations if o.name != 'Op A2']                    # comme un Ctrl+Z de l'ajout
        self.p.save(s)
        self.p.refresh()
        self.assertEqual(self.names(), ['Gravure'])

    def test_a_replaced_line_keeps_its_place(self):
        self.add('a')
        self.p._select_row(self.p.ops, 1)
        self.p.move_op(-1)
        self.assertEqual(self.ops(), ['Op A', 'Gravure'])
        self.w.canvas.doc.extra[KEY] = [{'id': 'm', 'label': 'Op M'}]                   # remplacée (retouche…)
        self.p.refresh()
        self.assertEqual(self.ops(), ['Op M', 'Gravure'])

if __name__ == '__main__':
    unittest.main()
