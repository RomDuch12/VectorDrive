"""Round 787 : boutons de script, ligne de commande, Informations reliée."""
import importlib.util
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from vectordrive.core import shapescript as SS

ROOT = pathlib.Path(__file__).resolve().parents[1]
LINE = 'MoveTo 0, 0, 0\nLineTo .01, 0, 0\n'


def load_main():
    spec = importlib.util.spec_from_file_location('vectordrive_main', ROOT / 'VectorDrive.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestParser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = load_main().make_parser()

    def test_te_spelling(self):
        got = self.parser.parse_args(['-SCRIPT', 'ShapeScript\\Cercle.txt', '-SCPARAM', '5.0', '7.5', '12.6'])
        self.assertEqual(got.script, 'ShapeScript\\Cercle.txt')
        self.assertEqual(got.script_params, ['5.0', '7.5', '12.6'])

    def test_long_spelling(self):
        got = self.parser.parse_args(['--script', 'a.txt', '--script-param', 'b'])
        self.assertEqual((got.script, got.script_params), ('a.txt', ['b']))

    def test_negative_values(self):
        self.assertEqual(self.parser.parse_args(['-SCRIPT', 'a', '-SCPARAM', '-1.5', '2']).script_params, ['-1.5', '2'])

    def test_no_script(self):
        got = self.parser.parse_args(['dessin.vnd'])
        self.assertIsNone(got.script)
        self.assertEqual(got.script_params, [])
        self.assertEqual(got.fichier, 'dessin.vnd')

    def test_other_options_still_work(self):
        got = self.parser.parse_args(['--convert', 'a.vnd', '--to', 'svg', '--out', 'b.svg', '--keep'])
        self.assertEqual((got.convert, got.to, got.out, got.keep), ('a.vnd', 'svg', 'b.svg', True))


class TestFind(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        self.env = mock.patch.dict(os.environ, {'VECTORDRIVE_SCRIPTS': str(self.dir / 'mes')})
        self.env.start()
        SS.user_dir().mkdir()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_full_path(self):
        f = self.dir / 'a.txt'
        f.write_text('', encoding='utf-8')
        self.assertEqual(SS.find_script(str(f)), f)

    def test_in_my_scripts_with_or_without_extension(self):
        f = SS.user_dir() / 'a.txt'
        f.write_text('', encoding='utf-8')
        self.assertEqual(SS.find_script('a.txt'), f)
        self.assertEqual(SS.find_script('a'), f)

    def test_te_relative_path(self):
        te = self.dir / 'te' / 'ShapeScript'
        te.mkdir(parents=True)
        f = te / 'Cercle.txt'
        f.write_text('', encoding='utf-8')
        self.assertEqual(SS.find_script('ShapeScript\\Cercle.txt', te), f)
        self.assertIsNone(SS.find_script('ShapeScript\\Cercle.txt'))

    def test_my_script_comes_before_te(self):
        te = self.dir / 'te'
        te.mkdir()
        (te / 'a.txt').write_text('', encoding='utf-8')
        mine = SS.user_dir() / 'a.txt'
        mine.write_text('', encoding='utf-8')
        self.assertEqual(SS.find_script('a.txt', te), mine)

    def test_missing(self):
        self.assertIsNone(SS.find_script('absent.txt', None))


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        self.env = mock.patch.dict(os.environ, {
            'VECTORDRIVE_SCRIPTS': str(self.dir / 'mes'), 'VECTORDRIVE_SETTINGS': str(self.dir / 'r.ini'),
            'VECTORDRIVE_SESSION': str(self.dir / 'session'), 'VECTORDRIVE_CACHE': str(self.dir / 'cache')})
        self.env.start()
        from vectordrive.ui.main_window import MainWindow
        self.win = MainWindow()
        SS.user_dir().mkdir()
        self.script = SS.user_dir() / 'trait.txt'
        self.script.write_text(LINE, encoding='utf-8')

    def tearDown(self):
        for n in range(1, 11):
            self.win.settings.remove(f'scripts/bouton_{n}')
        self.win.canvas.doc.modified = False
        self.win.close()
        self.win.deleteLater()
        self.env.stop()
        self.tmp.cleanup()

    def items(self):
        return list(self.win.canvas.doc.iter_items())


class TestRunFile(Base):
    def test_runs_and_draws(self):
        shape = self.win.run_script_file(str(self.script))
        self.assertIn(shape, self.items())
        self.assertEqual(shape.name, 'trait')

    def test_found_by_name(self):
        self.assertIsNotNone(self.win.run_script_file('trait'))

    def test_parameters_reach_the_script(self):
        f = SS.user_dir() / 'p.txt'
        f.write_text('If GetNbParameters() = 2 Then\nMoveTo 0, 0, 0\nLineTo CDbl(GetAppParameter(1)), 0, 0\nEnd If\n', encoding='utf-8')
        self.assertIsNone(self.win.run_script_file(f))
        self.assertAlmostEqual(self.win.run_script_file(f, ['x', '0.02']).path.bbox()[2], 20.0)

    def test_missing_file_is_said(self):
        with mock.patch('vectordrive.ui.main_window.QMessageBox.warning') as warn:
            self.assertIsNone(self.win.run_script_file('absent.txt'))
        self.assertIn('absent.txt', warn.call_args.args[2])
        self.assertEqual(self.items(), [])

    def test_error_is_said_with_its_line(self):
        f = SS.user_dir() / 'faux.txt'
        f.write_text('a = 1\nb = = 2\n', encoding='utf-8')
        with mock.patch('vectordrive.ui.main_window.QMessageBox.warning') as warn:
            self.assertIsNone(self.win.run_script_file(f))
        self.assertIn('faux.txt', warn.call_args.args[2])
        self.assertIn('2', warn.call_args.args[2])
        self.assertEqual(self.items(), [])


class TestSlots(Base):
    def test_ten_commands(self):
        for n in range(1, 11):
            self.assertIn(f'script_{n}', self.win.A)
        self.assertEqual(self.win.A['script_3'].text(), 'Script 3')

    def test_empty_slot_opens_the_window(self):
        with mock.patch.object(self.win, 'shape_script') as opened:
            self.win.A['script_2'].trigger()
        opened.assert_called_once()
        self.assertEqual(self.items(), [])

    def test_assigned_slot_runs_and_shows_the_name(self):
        self.win.set_script_slot(2, self.script)
        self.assertIn('trait', self.win.A['script_2'].text())
        self.assertIn('2', self.win.A['script_2'].text())
        self.win.A['script_2'].trigger()
        self.assertEqual(len(self.items()), 1)

    def test_slot_with_a_vanished_file_opens_the_window(self):
        self.win.set_script_slot(1, self.dir / 'parti.txt')
        with mock.patch.object(self.win, 'shape_script') as opened:
            self.win.script_slot(1)
        opened.assert_called_once()

    def test_slots_come_back_at_the_next_start(self):
        self.win.set_script_slot(4, self.script)
        from vectordrive.ui.main_window import MainWindow
        other = MainWindow()
        try:
            self.assertIn('trait', other.A['script_4'].text())
        finally:
            other.canvas.doc.modified = False
            other.close()
            other.deleteLater()

    def test_ribbon_editor_offers_them(self):
        dlg = self.win.ribbon_editor(exec_dialog=False)
        try:
            self.assertIn('script_7', self.win.A)
        finally:
            dlg.deleteLater()

    def test_no_slot_on_a_ribbon_by_default(self):
        for i in range(self.win.ribbon.count()):
            for g in self.win.ribbon.page(i).groups():
                for b in g.buttons():
                    act = b.defaultAction()
                    self.assertFalse(act is not None and act is self.win.A['script_1'])


class TestDialog(Base):
    def dialog(self):
        from vectordrive.ui.script_dialog import ScriptDialog
        return ScriptDialog(self.win)

    def test_assign_chosen_slot(self):
        dlg = self.dialog()
        dlg.path = self.script
        self.assertEqual(dlg.assign_slot(5), 5)
        self.assertIn('trait', self.win.A['script_5'].text())
        self.assertIn('5', dlg.message.text())

    def test_assign_asks_which(self):
        dlg = self.dialog()
        dlg.path = self.script
        with mock.patch('vectordrive.ui.script_dialog.QInputDialog.getItem', return_value=(self.win.script_slot_text(3), True)):
            self.assertEqual(dlg.assign_slot(), 3)

    def test_assign_cancelled(self):
        dlg = self.dialog()
        dlg.path = self.script
        with mock.patch('vectordrive.ui.script_dialog.QInputDialog.getItem', return_value=('', False)):
            self.assertIsNone(dlg.assign_slot())

    def test_new_script_is_saved_first(self):
        dlg = self.dialog()
        with mock.patch('vectordrive.ui.script_dialog.QInputDialog.getText', return_value=('neuf', True)):
            self.assertEqual(dlg.assign_slot(1), 1)
        self.assertTrue((SS.user_dir() / 'neuf.txt').is_file())
        self.assertIn('neuf', self.win.A['script_1'].text())

    def test_new_script_not_saved_is_not_assigned(self):
        dlg = self.dialog()
        with mock.patch('vectordrive.ui.script_dialog.QInputDialog.getText', return_value=('', False)):
            self.assertIsNone(dlg.assign_slot(1))
        self.assertEqual(self.win.A['script_1'].text(), 'Script 1')


class TestLink(unittest.TestCase):
    def test_cost_command_left_to_a_plugin(self):
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertNotEqual(TE_ACTIONS.get('ID_FILE_COST'), 'doc_info')


if __name__ == '__main__':
    unittest.main()
