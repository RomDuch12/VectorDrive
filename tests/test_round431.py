"""Round 431 : bibliothèque d'outils — sélection multiple, réordonner, glisser-déposer, dossiers vides,
renommer."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from vectordrive.cam import model, toollib

app = QApplication.instance() or QApplication([])


def lib(tmp):
    tools = []
    for name, folder in (('A', 'Datron'), ('B', 'Datron'), ('C', 'Datron'), ('D', 'Laser')):
        t = model.CamTool(name=name)
        t.folder = folder
        tools.append(t)
    p = tmp / 'tools.json'
    toollib.save(tools, p)
    return p


class TestToollibCore(unittest.TestCase):
    def test_place_shift_folders(self):
        tools = [model.CamTool(name=n) for n in 'ABCD']
        toollib.set_folder(tools[:3], 'X')
        toollib.set_folder(tools[3:], 'Y')
        toollib.place(tools, [tools[2]], before=tools[0])
        self.assertEqual([t.name for t in tools], ['C', 'A', 'B', 'D'])
        toollib.place(tools, [tools[0]], 'Y')                               # dans Y, à la fin de Y
        self.assertEqual([(t.name, toollib.folder_of(t)) for t in tools][-1], ('C', 'Y'))
        self.assertTrue(toollib.shift(tools, [tools[1]], -1))
        self.assertEqual([t.name for t in tools], ['B', 'A', 'D', 'C'])
        self.assertFalse(toollib.shift(tools, [tools[0]], -1))              # déjà en tête de son dossier
        p = pathlib.Path(tempfile.mkdtemp()) / 'tools.json'
        toollib.save(tools, p, ['Vide/Sous'])
        self.assertEqual(toollib.load_folders(p), ['Vide/Sous'])
        toollib.save(tools, p)                                              # None : les dossiers restent
        self.assertEqual(toollib.load_folders(p), ['Vide/Sous'])
        self.assertEqual(len(toollib.load(p)), 4)


class TestDialog(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.toollib_dialog import ToolLibraryDialog
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.dlg = ToolLibraryDialog(None, None, lib(self.tmp))

    def tearDown(self):
        self.dlg.close()

    def pick(self, *names):
        self.dlg.tree.clearSelection()
        for it in self.dlg._items():
            t = self.dlg.tool_by_id(it.data(0, Qt.ItemDataRole.UserRole))
            if t is not None and t.name in names:
                it.setSelected(True)
                self.dlg.tree.setCurrentItem(it)
                it.setSelected(True)
        for it in self.dlg._items():
            t = self.dlg.tool_by_id(it.data(0, Qt.ItemDataRole.UserRole))
            if t is not None and t.name in names:
                it.setSelected(True)

    def folder_item(self, name):
        return next(it for it in self.dlg._items() if it.data(0, Qt.ItemDataRole.UserRole + 1) == name)

    def tool_item(self, name):
        return next(it for it in self.dlg._items()
                    if (t := self.dlg.tool_by_id(it.data(0, Qt.ItemDataRole.UserRole))) and t.name == name)

    def test_multi_move_delete(self):
        self.pick('A', 'B')
        self.assertEqual([t.name for t in self.dlg.selected_tools()], ['A', 'B'])
        self.assertTrue(self.dlg.move_to_folder('Laser'))
        self.assertEqual({t.name: toollib.folder_of(t) for t in self.dlg.mine}['B'], 'Laser')
        self.pick('A', 'D')
        self.assertEqual(self.dlg.delete(confirm=False), 2)
        self.assertEqual(sorted(t.name for t in toollib.load(self.dlg.path)), ['B', 'C'])

    def test_drag_drop_and_shift(self):
        self.pick('C')
        self.assertTrue(self.dlg.dropped(self.tool_item('A')))              # C avant A
        self.assertEqual([t.name for t in self.dlg.mine][:3], ['C', 'A', 'B'])
        self.pick('A')
        self.assertTrue(self.dlg.dropped(self.folder_item('Laser')))        # A dans Laser
        self.assertEqual(toollib.folder_of(next(t for t in self.dlg.mine if t.name == 'A')), 'Laser')
        self.pick('B')
        self.assertTrue(self.dlg.shift(-1))
        self.assertEqual([t.name for t in self.dlg.mine if toollib.folder_of(t) == 'Datron'], ['B', 'C'])

    def test_folders_and_rename(self):
        self.dlg.tree.setCurrentItem(self.folder_item('Datron'))
        self.dlg.tree.clearSelection()
        full = self.dlg.new_folder('Fraises')
        self.assertEqual(full, 'Datron/Fraises')
        self.assertIn('Datron/Fraises', toollib.load_folders(self.dlg.path))   # vide, mais gardé
        self.folder_item('Datron/Fraises')
        self.pick('A')
        self.dlg.move_to_folder('Datron/Fraises')
        self.assertNotIn('Datron/Fraises', toollib.load_folders(self.dlg.path))   # plus vide : liste nettoyée
        self.pick('B')
        self.assertTrue(self.dlg.rename('B2'))
        self.assertIn('B2', [t.name for t in toollib.load(self.dlg.path)])
        self.dlg.tree.setCurrentItem(self.folder_item('Laser'))
        self.assertTrue(self.dlg.rename('Laser CO2'))
        self.assertEqual(toollib.folder_of(next(t for t in self.dlg.mine if t.name == 'D')), 'Laser CO2')


if __name__ == '__main__':
    unittest.main()
