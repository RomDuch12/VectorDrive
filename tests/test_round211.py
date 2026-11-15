"""Round 211 : Mes outils en lot (un dossier et ses sous-dossiers), outils
de Mes outils dans les parcours de la palette, dossier des programmes hors
de VectorDrive, export public plus strict (programmes, dessins, tous les
fichiers texte)."""
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

ROOT = pathlib.Path(__file__).resolve().parents[1]


def write_tools(p: pathlib.Path, tools: list[tuple[str, str, float]]) -> pathlib.Path:
    from vectordrive.cam import model, toollib
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(toollib.to_json([model.CamTool(name=n, kind=k, diameter=d, number=i + 1)
                                  for i, (n, k, d) in enumerate(tools)]), encoding='utf-8')
    return p


def tree() -> pathlib.Path:
    root = pathlib.Path(tempfile.mkdtemp()) / 'Outils atelier'
    write_tools(root / 'Datron' / 'fraises.json', [('Fraise 1', 'fraise', 1.0), ('Fraise 2', 'fraise', 2.0)])
    (root / 'Datron' / 'coniques.csv').write_text('name;kind;diameter;angle;tip\nConique 20°;conique;3;20;0.1\n',
                                                 encoding='utf-8')
    write_tools(root / 'gravure.json', [('Conique 30°', 'conique', 3.175)])
    (root / 'notes.txt').write_text('pas des outils', encoding='utf-8')
    (root / 'Datron' / 'abime.json').write_text('{pas du json', encoding='utf-8')
    (root / 'Datron' / '~$verrou.csv').write_text('x', encoding='utf-8')
    return root


class TestImportTree(unittest.TestCase):
    def test_folders_from_disk(self):
        from vectordrive.cam import toollib as L
        imported, notes, errors = L.import_tree(tree())
        self.assertEqual(sorted(imported), ['Datron/coniques', 'Datron/fraises', 'gravure'])
        self.assertEqual([t.name for t in imported['Datron/fraises']], ['Fraise 1', 'Fraise 2'])
        self.assertEqual(imported['Datron/coniques'][0].kind, 'conique')
        self.assertTrue(all(t.folder == f for f, ts in imported.items() for t in ts))
        self.assertEqual(len(errors), 1)
        self.assertIn('abime.json', errors[0])                              # un fichier abîmé n'arrête pas le lot

    def test_typeedit_folders_become_subfolders(self):
        from vectordrive.cam import model, tooldb, toollib as L
        root = pathlib.Path(tempfile.mkdtemp())
        (root / 'TypeEdit').mkdir()
        (root / 'TypeEdit' / 'base.Dbt').write_bytes(tooldb.write_bytes(
            [model.CamTool(name='Conique 60°', kind='conique', diameter=3.0, angle=60.0, tip=0.2)], 'Gravure'))
        imported, _n, errors = L.import_tree(root)
        self.assertEqual(errors, [])
        self.assertEqual(list(imported), ['TypeEdit/base/Gravure'])

    def test_add_replace_and_prefixes(self):
        from vectordrive.cam import model, toollib as L
        lib = [model.CamTool(name='ancienne', folder='Datron/fraises'), model.CamTool(name='seule')]
        imported, _n, _e = L.import_tree(tree())
        n, names = L.add_folders(lib, {k: list(v) for k, v in imported.items()}, replace=False)
        self.assertEqual(n, 4)
        self.assertIn('Datron/fraises (2)', names)                          # doublé : nom libre
        lib2 = [model.CamTool(name='ancienne', folder='Datron/fraises')]
        imported, _n, _e = L.import_tree(tree())
        L.add_folders(lib2, imported, replace=True)
        self.assertNotIn('ancienne', [t.name for t in lib2])                 # remplacé
        self.assertEqual(L.rename_folder(lib2, 'Datron', 'DATRON AG'), 3)    # sous-dossiers suivis
        self.assertEqual(sorted(L.folders(lib2)), ['DATRON AG/coniques', 'DATRON AG/fraises', 'gravure'])
        self.assertEqual([t.name for t in L.delete_folder(lib2, 'DATRON AG')], ['Conique 30°'])
        t = model.CamTool(name='x')
        L.set_folder([t], ' Datron /  Fraises ')
        self.assertEqual(t.folder, 'Datron/Fraises')
        self.assertEqual(L.folder_parts('a/ b /c'), ['a', 'b', 'c'])


class TestLibraryDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_import_folder_nested(self):
        from vectordrive.cam import toollib as L
        from vectordrive.ui.toollib_dialog import ToolLibraryDialog
        lib = pathlib.Path(tempfile.mkdtemp()) / 'tools.json'
        dlg = ToolLibraryDialog(None, None, lib)
        self.assertEqual(dlg.import_folder(tree(), replace=False), 4)
        self.assertTrue(lib.exists())                                          # tools.json créé
        node = dlg.tree.topLevelItem(dlg.tree.topLevelItemCount() - 1)     # 1043 : un seul arbre, Mes outils en bas
        self.assertTrue(node.text(0).startswith('📚 '), node.text(0))
        tops = [node.child(i).text(0) for i in range(node.childCount())]
        self.assertEqual(tops, ['📁 Datron', '📁 gravure'])
        datron = node.child(0)
        self.assertEqual(sorted(datron.child(i).text(0) for i in range(datron.childCount())),
                         ['📁 coniques', '📁 fraises'])
        self.assertIn(str(lib), dlg.info.text())                              # où est le tools.json
        self.assertEqual(dlg.import_folder(tree(), replace=True), 4)          # réimport : remplacé, pas doublé
        self.assertEqual(len(L.load(lib)), 4)
        dlg.select_folder('Datron/fraises')
        self.assertEqual(dlg.selected_folder(), 'Datron/fraises')
        dlg.select_folder('Datron')
        self.assertTrue(dlg.delete_folder(confirm=False))
        self.assertEqual([t.name for t in L.load(lib)], ['Conique 30°'])
        dlg.close()

    def test_several_files(self):
        from vectordrive.ui.toollib_dialog import ToolLibraryDialog
        tmp = pathlib.Path(tempfile.mkdtemp())
        a = write_tools(tmp / 'a.json', [('A', 'fraise', 1.0)])
        b = write_tools(tmp / 'b.json', [('B', 'fraise', 2.0)])
        dlg = ToolLibraryDialog(None, None, tmp / 'lib.json')
        from PySide6.QtWidgets import QDialog
        from vectordrive.ui.tool_import import ToolImportDialog
        with mock.patch('vectordrive.ui.toollib_dialog.QFileDialog.getOpenFileNames',
                        return_value=([str(a), str(b)], '')),                 mock.patch.object(ToolImportDialog, 'exec', lambda d: QDialog.DialogCode.Accepted):
            self.assertEqual(dlg.import_dialog(), 2)                      # round 238 : aperçu accepté
        self.assertEqual(sorted(t.folder for t in dlg.mine), ['a', 'b'])
        dlg.close()


class TestPaletteUsesMyTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def setUp(self):
        self._env = os.environ.get('VECTORDRIVE_TOOLS')
        self.lib = write_tools(pathlib.Path(tempfile.mkdtemp()) / 'tools.json',
                               [('Conique Datron 20°', 'conique', 3.0), ('Fraise Datron Ø2', 'fraise', 2.0)])
        os.environ['VECTORDRIVE_TOOLS'] = str(self.lib)
        self.w.modified = False                          # sinon « continuer sans enregistrer ? » (modal)
        self.w.new_document()

    def tearDown(self):
        if self._env is None:
            os.environ.pop('VECTORDRIVE_TOOLS', None)
        else:
            os.environ['VECTORDRIVE_TOOLS'] = self._env

    def _square(self):
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        sh = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]), tool=0)
        self.w.canvas.doc.active_layer.items.append(sh)
        self.w.canvas.select([sh])
        return sh

    def test_tool_taken_from_my_tools(self):
        self._square()
        op = self.w.cam_panel.new_operation('trace', exec_dialog=False)
        s = self.w.cam_panel.setup()
        self.assertEqual(s.tool(op.tool_id).name, 'Conique Datron 20°')    # pas un outil inventé
        self.assertEqual(s.tool(op.tool_id).folder, '')
        self.assertEqual(len(s.tools), 1)

    def test_form_offers_my_tools(self):
        from vectordrive.ui import cam_panel as CP
        self._square()
        seen = []

        def fake_exec(dlg):
            seen.append([dlg.widgets['tool_id'].itemData(i) for i in range(dlg.widgets['tool_id'].count())])
            i = dlg.widgets['tool_id'].findText('📁 Mes outils — Fraise Datron Ø2')
            dlg.widgets['tool_id'].setCurrentIndex(i)
            return 1
        with mock.patch.object(CP.FieldsDialog, 'exec', fake_exec):
            op = self.w.cam_panel.new_operation('decoupe')
        self.assertIn('__choisir__', seen[0])                 # round 239 : Mes outils par dossiers, pas en liste
        s = self.w.cam_panel.setup()
        self.assertEqual(s.tool(op.tool_id).name, 'Fraise Datron Ø2')        # copié dans le document


class TestProgramFolder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def test_never_inside_vectordrive(self):
        p = self.w.cam_panel
        self.w.path = str(ROOT / 's42.vnd')                                    # dessin rangé dans les sources
        d = p.program_dir()
        self.assertFalse(d.resolve().is_relative_to(ROOT.resolve()))
        tmp = pathlib.Path(tempfile.mkdtemp())
        self.w.path = str(tmp / 'plaque.vnd')
        self.assertEqual(p.program_dir(), tmp)                                 # à côté du dessin
        self.w.path = None


class TestPublicExport(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(ROOT / 'outils'))
        import exporter_public
        self.E = exporter_public

    def test_production_files_refused(self):
        files = ['s42.simpl', 'a/b.000', 'vectordrive/ressources/vnd_modele.vnd', 'client.vnd', 'outils/x.py',
                 'prog.NC', 'tests/test_round20.py']
        self.assertEqual(self.E.production_files(files), ['s42.simpl', 'a/b.000', 'client.vnd', 'prog.NC'])

    def test_every_text_file_scanned(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        (tmp / 'Cargo.lock').write_text('nom = "ClientX"\n', encoding='utf-8')
        (tmp / 'image.bin').write_bytes(b'\0\0ClientX')
        (tmp / 'natif' / 'vendor').mkdir(parents=True)
        (tmp / 'natif' / 'vendor' / 'x.rs').write_text('ClientX', encoding='utf-8')
        with mock.patch.object(self.E, 'ROOT', tmp):
            hits = self.E.scan(['Cargo.lock', 'image.bin', 'natif/vendor/x.rs'], ['clientx'])
        self.assertEqual(hits, ['Cargo.lock:1 : clientx'])

    def test_gitignore(self):
        text = (ROOT / '.gitignore').read_text(encoding='utf-8')
        for pat in ('/*.simpl', '/*.nc', '/*.cljob', '/*.vnd'):
            self.assertIn(pat, text)


class TestLibraryOption(unittest.TestCase):
    def test_chosen_file(self):
        from vectordrive.cam import toollib as L
        from vectordrive.ui.options import BY_KEY
        self.assertEqual(BY_KEY['fao/bibliotheque'].kind, 'file')
        env = os.environ.pop('VECTORDRIVE_TOOLS', None)
        try:
            L.CHOSEN_PATH = r'D:\Atelier\tools.json'
            self.assertEqual(L.default_path(), pathlib.Path(r'D:\Atelier\tools.json'))
            L.CHOSEN_PATH = ''
            self.assertEqual(L.default_path().name, 'tools.json')
        finally:
            L.CHOSEN_PATH = ''
            if env is not None:
                os.environ['VECTORDRIVE_TOOLS'] = env


if __name__ == '__main__':
    unittest.main()
