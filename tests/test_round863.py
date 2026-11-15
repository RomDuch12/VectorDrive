"""Round 863 : grouper les programmes (manuel de TE, page 816 imprimée)."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', os.path.join(tempfile.mkdtemp(), 'session'))
os.environ.setdefault('VECTORDRIVE_NO_TYPEEDIT', '1')

from vectordrive.cam import model as M
from vectordrive.cam import post
from vectordrive.cam.model import Move, Toolpath


def path(op_id, name='p'):
    tp = Toolpath(op_id, 't', name=name)
    tp.moves = [Move('feed', 1.0, 2.0, -1.0)]
    return tp


class TestGroups(unittest.TestCase):

    def setUp(self):
        self.a, self.b, self.c = path('1', 'Trous'), path('2', 'Tour'), path('3', 'Fond')
        self.plans = {'1': 'Haut', '2': 'Bas', '3': 'Haut'}

    def plan_of(self, tp):
        return self.plans[tp.op_id]

    def test_everything(self):
        self.assertEqual(post.program_groups([self.a, self.b], 'tout'), [('', [self.a, self.b])])

    def test_unknown_is_everything(self):
        self.assertEqual(post.program_groups([self.a, self.b], 'autre', self.plan_of), [('', [self.a, self.b])])

    def test_by_plan_keeps_the_order(self):
        got = post.program_groups([self.a, self.b, self.c], 'plan', self.plan_of)
        self.assertEqual(got, [('Haut', [self.a, self.c]), ('Bas', [self.b])])

    def test_one_plan_needs_no_suffix(self):
        got = post.program_groups([self.a, self.c], 'plan', self.plan_of)
        self.assertEqual(got, [('', [self.a, self.c])])

    def test_by_plan_without_function(self):
        self.assertEqual(post.program_groups([self.a, self.b], 'plan'), [('', [self.a, self.b])])

    def test_no_plan(self):
        got = post.program_groups([self.a, self.b], 'plan', lambda tp: '' if tp is self.a else 'Bas')
        self.assertEqual(got[0], ('sans_nom', [self.a]))

    def test_by_path_is_numbered(self):
        got = post.program_groups([self.a, self.b], 'parcours')
        self.assertEqual(got, [('01_Trous', [self.a]), ('02_Tour', [self.b])])

    def test_one_operation_with_several_paths(self):
        twice = path('1', 'Trous')
        got = post.program_groups([self.a, twice, self.b], 'parcours')
        self.assertEqual(got, [('01_Trous', [self.a, twice]), ('02_Tour', [self.b])])

    def test_one_path_needs_no_suffix(self):
        self.assertEqual(post.program_groups([self.a], 'parcours'), [('', [self.a])])

    def test_forbidden_characters(self):
        a, b = path('1', 'a/b:c?'), path('2', ' . ')
        got = post.program_groups([a, b], 'parcours')
        self.assertEqual(got[0][0], '01_a_b_c_')
        self.assertEqual(got[1][0], '02_sans_nom')

    def test_nothing(self):
        self.assertEqual(post.program_groups([], 'parcours'), [('', [])])


class TestSetup(unittest.TestCase):

    def test_it_survives_the_file(self):
        from vectordrive.core.document import Document
        doc = Document()
        s = M.setup_of(doc)
        self.assertEqual(s.program_group, 'tout')
        s.program_group = 'plan'
        M.store(doc, s)
        self.assertEqual(M.setup_of(doc).program_group, 'plan')


class TestPanel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.win = MainWindow()
        cls.p = cls.win.cam_panel

    @classmethod
    def tearDownClass(cls):
        cls.win.modified = False
        cls.win.close()

    def tearDown(self):
        self.p.group_dialog('tout')

    def test_the_setting(self):
        self.assertTrue(self.p.group_dialog('plan'))
        self.assertEqual(self.p.setup().program_group, 'plan')
        self.assertFalse(self.p.group_dialog('de travers'))
        self.assertEqual(self.p.setup().program_group, 'plan')

    def test_the_window(self):
        from PySide6.QtWidgets import QInputDialog
        with mock.patch.object(QInputDialog, 'getItem', return_value=(self.p.GROUP_LABELS['parcours'], True)):
            self.assertTrue(self.p.group_dialog())
        self.assertEqual(self.p.setup().program_group, 'parcours')
        with mock.patch.object(QInputDialog, 'getItem', return_value=('', False)):
            self.assertFalse(self.p.group_dialog())
        self.assertEqual(self.p.setup().program_group, 'parcours')

    def test_the_plan_of_a_path(self):
        from vectordrive.core import geom
        from vectordrive.core.document import Layer, Shape
        doc = self.win.canvas.doc
        s = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]))
        layer = Layer(name='Plan X', items=[s])
        doc.layers[:] = [layer]
        doc.active = layer.id
        setup = self.p.setup()
        op = M.Operation(kind='gravure', items=[s.id])
        setup.operations[:] = [op]
        self.p.save(setup)
        self.assertEqual(self.p._plan_of_path(Toolpath(op.id, 't')), 'Plan X')
        self.assertEqual(self.p._plan_of_path(Toolpath('parti', 't')), '')
        setup.operations[:] = []
        self.p.save(setup)

    def write(self, how, folder, tps, *, answer=None):
        """Le post-traitement avec un post-processeur d'essai : rend les appels."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        calls = []

        def fake(key, part, s, *, title='', stem='', box_mm=None, out_dir='', origin=None, machine=None):
            calls.append((stem, list(part)))
            return post.PostResult('G0', [f'note {stem}'], '.nc', 'ascii', [(stem + '.nc', 'G0\n')])
        self.p.group_dialog(how)
        target = os.path.join(folder, 'prog.nc')
        asked = mock.patch.object(QMessageBox, 'question', return_value=answer) if answer is not None else mock.patch.object(QMessageBox, 'question', side_effect=AssertionError('pas de question'))
        with mock.patch.object(self.p, 'current_paths', lambda *a, **k: tps), mock.patch.object(post, 'posts', lambda d='': {'x': ('x', None)}), \
                mock.patch.object(post, 'run', fake), mock.patch.object(self.p, 'preflight', lambda *a, **k: True), \
                mock.patch.object(QFileDialog, 'getSaveFileName', return_value=(target, '')), \
                mock.patch('vectordrive.ui.progress.run', lambda win, title, fn, *a: []), \
                mock.patch('vectordrive.ui.reveal.done_message') as done, asked:
            self.p.post_process()
        self.done = done
        return calls

    def test_one_file_by_default(self):
        with tempfile.TemporaryDirectory() as d:
            tps = [path('1', 'A'), path('2', 'B')]
            calls = [c for c in self.write('tout', d, tps) if c[0] != 'programme']
            self.assertEqual([c[0] for c in calls], ['prog'])
            self.assertEqual(sorted(f.name for f in pathlib.Path(d).glob('*.nc')), ['prog.nc'])

    def test_one_file_per_path(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = path('1', 'A'), path('2', 'B')
            calls = [c for c in self.write('parcours', d, [a, b]) if c[0] != 'programme']
            self.assertEqual([c[0] for c in calls], ['prog_01_A', 'prog_02_B'])
            self.assertEqual(calls[0][1], [a])
            self.assertEqual(sorted(f.name for f in pathlib.Path(d).glob('*.nc')), ['prog_01_A.nc', 'prog_02_B.nc'])

    def test_the_message_names_every_file_and_warning(self):
        with tempfile.TemporaryDirectory() as d:
            self.write('parcours', d, [path('1', 'A'), path('2', 'B')])
            msg = self.done.call_args[0][2]
            for word in ('prog_01_A.nc', 'prog_02_B.nc', 'note prog_01_A', 'note prog_02_B'):
                self.assertIn(word, msg)

    def test_existing_files_ask_first(self):
        from PySide6.QtWidgets import QMessageBox
        with tempfile.TemporaryDirectory() as d:
            old = pathlib.Path(d) / 'prog_01_A.nc'
            old.write_text('ancien', encoding='utf-8')
            self.write('parcours', d, [path('1', 'A'), path('2', 'B')], answer=QMessageBox.StandardButton.No)
            self.assertEqual(old.read_text(encoding='utf-8'), 'ancien')
            self.assertFalse((pathlib.Path(d) / 'prog_02_B.nc').exists())

    def test_replacing_when_accepted(self):
        from PySide6.QtWidgets import QMessageBox
        with tempfile.TemporaryDirectory() as d:
            old = pathlib.Path(d) / 'prog_01_A.nc'
            old.write_text('ancien', encoding='utf-8')
            self.write('parcours', d, [path('1', 'A'), path('2', 'B')], answer=QMessageBox.StandardButton.Yes)
            self.assertNotEqual(old.read_text(encoding='utf-8'), 'ancien')

    def test_the_file_chosen_in_the_window_is_not_asked_twice(self):
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d) / 'prog.nc').write_text('ancien', encoding='utf-8')
            self.write('tout', d, [path('1', 'A')])           # 'pas de question' sinon
            self.assertNotEqual((pathlib.Path(d) / 'prog.nc').read_text(encoding='utf-8'), 'ancien')


if __name__ == '__main__':
    unittest.main()
