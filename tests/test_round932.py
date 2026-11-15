"""Round 932 : corrections trouvées en relisant les rounds 928 à 930 (outil d'un programme lu, F2, bibliothèque)."""
import json
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r932.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QInputDialog

app = QApplication.instance() or QApplication([])

from vectordrive.cam import model as M  # noqa: E402
from vectordrive.cam import ncread, toollib  # noqa: E402
from vectordrive.plugins import REGISTRY  # noqa: E402

PROG = """%
T3 M6 (MYSTERE A932)
S18000 M3
G0 X0 Y0 Z5
G1 Z-0.3 F300
G1 X10 Y0 F900
G0 Z5
T4 M6 (MYSTERE B932)
G0 X20 Y0
G1 Z-0.2 F250
G1 X40 Y0 F1200
G0 Z5
M30
"""


def datron():
    return [M.CamTool(name='Cyl 2 932', kind='fraise', diameter=2.0, ref='D932-2', folder='Datron/Fraises')]


class Base(unittest.TestCase):
    def setUp(self):
        d = tempfile.mkdtemp()
        self.tools_file = os.path.join(d, 'tools.json')
        self.alias_file = os.path.join(d, 'associations_programmes.json')
        self.env = mock.patch.dict(os.environ, {'VECTORDRIVE_TOOLS': self.tools_file})
        self.env.start()
        self.libs = mock.patch.dict(REGISTRY.tool_libraries, {'Datron': datron}, clear=True)
        self.libs.start()

    def tearDown(self):
        self.libs.stop()
        self.env.stop()


class Aliases(Base):

    def test_damaged_file_is_set_aside_and_bom_is_read(self):
        info = {'name': 'MYSTERE A932'}
        with open(self.alias_file, 'w', encoding='utf-8') as f:
            f.write('{abîmé')
        self.assertTrue(ncread.remember(info, datron()[0]))
        self.assertEqual(len(ncread.load_aliases()), 1)
        aside = pathlib.Path(self.alias_file).with_name('associations_programmes.abime.json')
        self.assertEqual(aside.read_text(encoding='utf-8'), '{abîmé')        # gardé, pas écrasé
        data = {'version': 1, 'associations': [{'programme': {'name': 'X932'}, 'outil': {'name': 'Cyl 2 932'}},
                                               {'programme': {'name': 'Y932'}, 'outil': {'name': 'Cyl 2 932'}}]}
        with open(self.alias_file, 'w', encoding='utf-8-sig') as f:          # avec BOM (Bloc-notes)
            json.dump(data, f)
        self.assertEqual(len(ncread.load_aliases()), 2)
        self.assertEqual([p.name for p in pathlib.Path(self.alias_file).parent.glob('*.tmp')], [])

    def test_unreachable_file_is_not_rewritten(self):
        ncread.remember({'name': 'MYSTERE A932'}, datron()[0])
        before = pathlib.Path(self.alias_file).read_bytes()
        with mock.patch.object(pathlib.Path, 'read_text', side_effect=PermissionError('partage absent')):
            with self.assertRaises(OSError):
                ncread.remember({'name': 'MYSTERE B932'}, datron()[0])
            with self.assertRaises(OSError):
                ncread.forget({'name': 'MYSTERE A932'})
        self.assertEqual(pathlib.Path(self.alias_file).read_bytes(), before)


class Window(Base):

    def setUp(self):
        super().setUp()
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.cp, self.lp = self.w.cam_panel, self.w.layers_panel
        s = self.cp.setup()
        s.tools, s.operations = [], []
        self.cp.save(s)

    def tearDown(self):
        self.w.modified = False
        self.w.close()
        super().tearDown()

    def program(self, text=PROG):
        path = os.path.join(tempfile.mkdtemp(), 'essai.nc')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)
        self.w.open_nc_program(path)
        return [p for p in self.cp.toolpaths if not p.op_id]

    def test_the_choice_window_also_creates_an_unknown_tool(self):
        first, _second = self.program()[:2]
        dlg = self.cp.choose_program_tool(first, exec_dialog=False)
        self.assertIsNotNone(getattr(dlg, 'create_button', None))
        made = M.CamTool(name='MYSTERE A932')
        with mock.patch.object(self.cp, 'create_program_tool', return_value=made) as create:
            dlg.create_button.click()
        create.assert_called_once_with(first)
        self.cp.set_program_tool(first, datron()[0], True, 'Datron')         # connu : rien à créer
        dlg = self.cp.choose_program_tool(first, exec_dialog=False)
        self.assertIsNone(getattr(dlg, 'create_button', None))
        dlg.reject()

    def test_created_from_the_form_the_read_paths_know_it(self):
        from vectordrive.cam import toollib
        from vectordrive.ui import cam_panel as CP
        first, second = self.program()[:2]
        with mock.patch.object(self.cp, 'ask_program_tool', return_value='create'), \
                mock.patch.object(CP.FieldsDialog, 'exec', return_value=1), \
                mock.patch('vectordrive.cam.toollib.library', return_value=[]):     # Mes outils pas relu
            tool, new = self.cp.program_tool(first)
        self.assertTrue(new)
        self.assertEqual((first.tool_source, first.tool_guess.name), ('Mes outils', 'MYSTERE A932'))
        self.assertEqual(second.tool_source, '')                              # un autre outil
        self.assertFalse(self.lp.traj_row().child(0).text(2).endswith(' ?'))
        self.assertEqual([t.name for t in toollib.load(self.tools_file)], ['MYSTERE A932'])   # une fois, pas deux

    def test_the_unknown_window_keeps_earlier_programs(self):
        self.program()
        self.program(PROG.replace('A932', 'C932').replace('B932', 'D932'))
        dlg = self.cp._unknown_dlg
        self.assertEqual(len(dlg.rows), 4)                                    # les deux programmes
        self.assertTrue(dlg.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose))

    def test_choice_window_is_freed(self):
        from vectordrive.ui.tool_picker import ProgramToolDialog
        first = self.program()[0]
        with mock.patch.object(ProgramToolDialog, 'exec', return_value=0), \
                mock.patch.object(ProgramToolDialog, 'deleteLater') as freed:
            self.assertIsNone(self.cp.choose_program_tool(first))
        freed.assert_called_once()

    def test_nothing_kept_without_a_program_key_or_when_saving_fails(self):
        first = self.program()[0]
        first.tool_info = {}                                                  # le programme ne nomme pas l'outil
        s = self.cp.setup()
        doc = M.CamTool(name='Du document 932', diameter=0.8)
        s.tools = [doc]
        self.cp.save(s)
        self.cp.set_program_tool(first, doc, True, '')
        self.assertFalse(os.path.exists(self.tools_file))                     # pas copié dans Mes outils
        self.assertIn('cette fois', self.w.statusBar().currentMessage())
        first.tool_info = {'name': 'MYSTERE A932'}

        def fail(_t):
            self.w.statusBar().showMessage('ÉCHEC 932')
            return False
        with mock.patch.object(self.cp, 'save_program_tool', side_effect=fail):
            self.cp.set_program_tool(first, doc, True, '')
        self.assertEqual(self.w.statusBar().currentMessage(), 'ÉCHEC 932')   # pas caché par « retenu »
        self.assertEqual(ncread.load_aliases(), [])

    def test_f2_during_a_guide_drag_is_not_the_checkbox(self):
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        w = self.w
        sh = Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]))
        w.canvas.doc.add(sh)
        w.canvas.select([sh])
        w.dims.refresh()
        w.resize(1600, 1000)
        w.show()
        w.activateWindow()
        self.addCleanup(w.hide)
        app.processEvents()
        w.canvas.setFocus()
        app.processEvents()
        w.f2()
        app.processEvents()
        fw = QApplication.focusWidget()
        if fw is None or not w.dims.isAncestorOf(fw):
            self.skipTest('pas de focus clavier sur cette plateforme')
        keep = w.dims.keep.isChecked()
        guide = mock.Mock()
        with mock.patch.object(w.canvas, 'ruler_dragging', guide, create=True):
            w.f2()
        guide.ask_position.assert_called_once()
        self.assertEqual(w.dims.keep.isChecked(), keep)


class Library(unittest.TestCase):

    def test_open_browser_has_no_add_selection(self):
        from vectordrive.ui import file_browser as FB
        s = QSettings(os.path.join(tempfile.mkdtemp(), 's.ini'), QSettings.Format.IniFormat)
        p = FB.FileBrowserPanel(s)
        self.addCleanup(p.deleteLater)
        self.assertTrue(p.add_selection.isHidden())
        folder = pathlib.Path(tempfile.mkdtemp())
        (folder / 'Sous932').mkdir()
        p.show_folder(folder)
        for i in range(p.list.count()):
            it = p.list.item(i)
            it.setSelected(str(it.data(0x0100)).endswith('Sous932'))
        m = p.menu(p.list, None, exec_menu=False)
        texts = [a.text() for a in m.actions()]
        self.assertNotIn('Ajouter la sélection du dessin ici…', texts)
        self.assertNotIn('Enregistrer la sélection sous…', texts)

    def test_big_window_on_favorites_and_unreadable_folder(self):
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            docked = pathlib.Path(tempfile.mkdtemp())
            sh = Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]))
            w.canvas.doc.add(sh)
            w.canvas.select([sh])
            w.symbols.show_folder(docked)
            w.library_window(show=False)
            big = w._library_window.panel
            big.show_favorites()
            with mock.patch.object(w, 'save_as_symbol') as save, \
                    mock.patch.object(QInputDialog, 'getText', return_value=('X932', True)):
                big.add_selection.click()
            save.assert_called_once()                                         # Enregistrer sous
            self.assertEqual(list(docked.glob('*.smb')), [])                  # pas le dossier du panneau ancré
            w.symbols.show_folder(docked / 'disparu932')                     # illisible : plus de dossier visé
            self.assertNotEqual(w.symbols.target_folder(), docked)
        finally:
            w.modified = False
            w.close()


class Keys(unittest.TestCase):

    def test_keys_held_by_a_test_are_released_after_it(self):
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QWidget

        class Sink(QWidget):
            def event(self, ev):
                if ev.type() in (ev.Type.KeyPress, ev.Type.KeyRelease, ev.Type.MouseButtonPress,
                                 ev.Type.MouseButtonRelease):
                    ev.accept()
                    return True
                return super().event(ev)

        none = Qt.KeyboardModifier.NoModifier
        sink = Sink()
        self.addCleanup(sink.deleteLater)
        self.addCleanup(QTest.keyRelease, sink, Qt.Key.Key_Control)          # code d'avant : ne rien laisser non plus
        seen = []

        class Inner(unittest.TestCase):
            def test_ctrl_key(self):
                QTest.keyClick(sink, Qt.Key.Key_Right, Qt.KeyboardModifier.ControlModifier)
                seen.append(QApplication.keyboardModifiers())

            def test_shift_click(self):
                QTest.mouseClick(sink, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier)
                seen.append(QApplication.keyboardModifiers())

        for name in ('test_ctrl_key', 'test_shift_click'):
            result = unittest.TestResult()
            Inner(name).run(result)
            self.assertTrue(result.wasSuccessful(), result.errors + result.failures)
            self.assertEqual(QApplication.keyboardModifiers(), none, name)   # relâchées pour l'essai suivant
        self.assertEqual(seen, [Qt.KeyboardModifier.ControlModifier, Qt.KeyboardModifier.ShiftModifier])   # pendant : oui


if __name__ == '__main__':
    unittest.main()
