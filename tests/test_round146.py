"""Round 146 : « Mes outils » en dossiers (un import = un dossier ;
renommer, fusionner, supprimer, déplacer) et proposés dans le panneau FAO
(formulaire d'opération, menu « Ajouter depuis Mes outils »)."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))


def tools_file(folder: pathlib.Path, name: str, tools: list[tuple[str, float]]) -> pathlib.Path:
    from vectordrive.cam import model, toollib
    p = folder / name
    p.write_text(toollib.to_json([model.CamTool(name=n, diameter=d, number=i + 1)
                                  for i, (n, d) in enumerate(tools)]), encoding='utf-8')
    return p


class TestFolders(unittest.TestCase):
    def test_helpers(self):
        from vectordrive.cam import model, toollib as L
        a, b, c = model.CamTool(name='a'), model.CamTool(name='b', folder='Datron'), model.CamTool(name='c')
        tools = [a, b, c]
        self.assertEqual(L.folders(tools), ['Mes outils', 'Datron'])
        self.assertEqual(L.unique_folder('Datron', tools), 'Datron (2)')
        self.assertEqual(L.unique_folder('Gravure', tools), 'Gravure')
        self.assertEqual(L.rename_folder(tools, 'Datron', 'Fraises'), 1)
        self.assertEqual(b.folder, 'Fraises')
        self.assertEqual(L.merge_folders(tools, 'Fraises', 'Mes outils'), 1)
        self.assertEqual(b.folder, '')                                       # « Mes outils » = sans dossier
        b.folder = 'X'
        self.assertEqual([t.name for t in L.delete_folder(tools, 'X')], ['a', 'c'])
        back = L.from_json(L.to_json(tools))
        self.assertEqual([t.folder for t in back], ['', 'X', ''])


class TestLibraryDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_imports_are_folders(self):
        from vectordrive.cam import toollib as L
        from vectordrive.ui.toollib_dialog import ToolLibraryDialog
        tmp = pathlib.Path(tempfile.mkdtemp())
        lib = tmp / 'mes_outils.json'
        dlg = ToolLibraryDialog(None, None, lib)
        f1 = tools_file(tmp, 'Datron fraises.json', [('Fraise 1', 1.0), ('Fraise 2', 2.0)])
        f2 = tools_file(tmp, 'Gravure TypeEdit.json', [('Conique 30°', 3.175)])
        self.assertEqual(dlg.import_file(f1), 2)
        self.assertEqual(dlg.import_file(f2), 1)
        self.assertEqual(dlg.import_file(f1), 2)                              # réimporté : dossier distinct
        self.assertEqual(L.folders(dlg.mine), ['Datron fraises', 'Gravure TypeEdit', 'Datron fraises (2)'])
        self.assertEqual(dlg.tree.topLevelItemCount(), 3)
        dlg.select_folder('Datron fraises (2)')
        self.assertTrue(dlg.merge_folder('Datron fraises'))
        self.assertEqual(L.folders(dlg.mine), ['Datron fraises', 'Gravure TypeEdit'])
        dlg.select_folder('Gravure TypeEdit')
        self.assertTrue(dlg.rename_folder('Gravure'))
        dlg.select(next(t for t in dlg.mine if t.name == 'Fraise 2'))
        self.assertTrue(dlg.move_to_folder('Grosses fraises'))
        self.assertIn('Grosses fraises', L.folders(dlg.mine))
        dlg.select_folder('Gravure')
        self.assertTrue(dlg.delete_folder(confirm=False))
        self.assertNotIn('Gravure', L.folders(L.load(lib)))                    # enregistré
        self.assertEqual(len(L.load(lib)), 4)
        dlg.close()


class TestCamPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from vectordrive.cam import model, toollib as L
        tmp = pathlib.Path(tempfile.mkdtemp())
        self.lib = tmp / 'mes_outils.json'
        L.save([model.CamTool(name='Fraise 2 mm', diameter=2, number=4, folder='Datron'),
                model.CamTool(name='Conique 30°', kind='conique', diameter=3.175, number=1, folder='Gravure')],
               self.lib)
        self._env = os.environ.get('VECTORDRIVE_TOOLS')
        os.environ['VECTORDRIVE_TOOLS'] = str(self.lib)
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        if self._env is None:
            os.environ.pop('VECTORDRIVE_TOOLS', None)
        else:
            os.environ['VECTORDRIVE_TOOLS'] = self._env
        self.w.modified = False
        self.w.close()

    def test_operation_with_library_tool(self):
        from vectordrive.cam import model
        from vectordrive.ui.cam_panel import FieldsDialog
        panel = self.w.cam_panel
        s = panel.setup()
        self.assertEqual(s.tools, [])
        lib = panel.library_tools()
        self.assertEqual(len(lib), 2)
        o = model.Operation(tool_id='')
        dlg = FieldsDialog(panel, 'essai', o, self.w.canvas.doc, s.tools, library=lib)
        combo = dlg.widgets['tool_id']
        combo.setCurrentIndex(combo.findData('lib:' + lib[1].id))
        dlg.apply()
        self.assertEqual(len(dlg.new_tools), 1)
        self.assertEqual(o.tool_id, dlg.new_tools[0].id)
        self.assertEqual(dlg.new_tools[0].name, 'Conique 30°')
        self.assertEqual(dlg.new_tools[0].folder, '')

    def test_add_op_without_document_tools(self):
        from PySide6.QtWidgets import QDialog
        from vectordrive.ui import cam_panel as CP
        panel = self.w.cam_panel
        orig = CP.FieldsDialog.exec

        def fake_exec(dlg):
            combo = dlg.widgets['tool_id']
            combo.setCurrentIndex(combo.findText('📁 Datron — Fraise 2 mm'))
            return QDialog.DialogCode.Accepted
        CP.FieldsDialog.exec = fake_exec
        try:
            panel.add_op()
        finally:
            CP.FieldsDialog.exec = orig
        s = panel.setup()
        self.assertEqual([t.name for t in s.tools], ['Fraise 2 mm'])
        self.assertEqual(s.operations[-1].tool_id, s.tools[0].id)

    def test_library_menu(self):
        panel = self.w.cam_panel
        m = panel.library_menu(exec_menu=False)
        self.assertEqual(sorted(m.vd_submenus), ['Datron', 'Gravure'])
        m.vd_submenus['Gravure'].actions()[0].trigger()
        tools = panel.setup().tools
        self.assertEqual([t.name for t in tools], ['Conique 30°'])
        self.assertEqual(tools[0].number, 1)


if __name__ == '__main__':
    unittest.main()
