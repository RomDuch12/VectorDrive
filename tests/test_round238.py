"""Round 238 : import d'outils en deux temps — aperçu (arborescence du
fichier, silhouette, doublons décochés), sélection multiple, rangement
choisi ; une base TypeEdit importée seule garde ses dossiers."""
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


def tools():
    from vectordrive.cam.model import CamTool
    return [CamTool(name='Ø3 Z1 L13', kind='fraise', diameter=3.0, number=248, ref='R-3', vendor='V'),
            CamTool(name='30° 0.2', kind='conique', diameter=4.0, angle=30.0, tip=0.2, number=61),
            CamTool(name='ø3 z1 L13', kind='fraise', diameter=3.0, number=12, ref='R-3', vendor='V')]


class TestDuplicates(unittest.TestCase):
    def test_same_tool(self):
        from vectordrive.cam import toollib
        from vectordrive.cam.model import CamTool
        a, b, c = tools()
        self.assertTrue(toollib.same_tool(a, c))                       # même référence
        self.assertFalse(toollib.same_tool(a, b))
        d = CamTool(name='30°  0.2', kind='conique', diameter=4.0, angle=30.0, tip=0.2)
        self.assertTrue(toollib.same_tool(b, d))                       # même nom (espaces), mêmes cotes
        d.tip = 0.1
        self.assertFalse(toollib.same_tool(b, d))
        self.assertIs(toollib.find_duplicate(c, [a, b]), a)


class TestImport(unittest.TestCase):
    def setUp(self):
        from vectordrive.cam import tooldb
        self.dir = pathlib.Path(tempfile.mkdtemp())
        self.dbt = self.dir / 'Atelier.Dbt'
        self.dbt.write_bytes(tooldb.write_bytes(tools(), 'Fraises'))
        self.lib = self.dir / 'tools.json'
        self._old = os.environ.get('VECTORDRIVE_TOOLS')
        os.environ['VECTORDRIVE_TOOLS'] = str(self.lib)

    def tearDown(self):
        if self._old is None:
            os.environ.pop('VECTORDRIVE_TOOLS', None)
        else:
            os.environ['VECTORDRIVE_TOOLS'] = self._old

    def test_import_files_keeps_dbt_folders(self):
        from vectordrive.cam import toollib
        imported, _n, errors = toollib.import_files([self.dbt])
        self.assertEqual(errors, [])
        self.assertEqual(list(imported), ['Atelier/Fraises'])
        self.assertEqual(len(imported['Atelier/Fraises']), 3)

    def test_preview_dialog(self):
        from vectordrive.cam import toollib
        from vectordrive.cam.model import CamTool
        from vectordrive.ui.tool_import import ToolImportDialog
        imported, _n, _e = toollib.import_files([self.dbt])
        mine = [CamTool(name='30° 0.2', kind='conique', diameter=4.0, angle=30.0, tip=0.2, folder='Datron')]
        dlg = ToolImportDialog(None, imported, mine)
        try:
            ts = imported['Atelier/Fraises']
            self.assertEqual(set(dlg.dups), {ts[1].id, ts[2].id})        # dans Mes outils ; répété dans l'import
            self.assertEqual(dlg.checked_ids(), [ts[0].id])
            dlg.check_all(True)
            self.assertEqual(len(dlg.checked_ids()), 3)
            dlg.uncheck_duplicates()
            self.assertEqual(dlg.chosen(), {'Atelier/Fraises': [ts[0]]})
            dlg.dest.setCurrentIndex(dlg.dest.findData('Datron'))
            self.assertEqual(list(dlg.chosen()), ['Datron/Atelier/Fraises'])
            dlg.keep_tree.setChecked(False)
            self.assertEqual(list(dlg.chosen()), ['Datron'])
            dlg.dest.setEditText('Nouveau / Sous')
            self.assertEqual(list(dlg.chosen()), ['Nouveau/Sous'])
            dlg.filter.setText('30°')
            hidden = [it.isHidden() for it in dlg._tool_items()]
            self.assertEqual(hidden, [True, False, True])
            items = list(dlg._tool_items())
            dlg.tree.setCurrentItem(items[1])
            self.assertIn('Mes outils', dlg.card.text())
        finally:
            dlg.deleteLater()

    def test_library_dialog(self):
        from vectordrive.cam import toollib
        from vectordrive.ui.toollib_dialog import ToolLibraryDialog
        dlg = ToolLibraryDialog(None)
        try:
            self.assertEqual(dlg.import_file(self.dbt), 3)               # import direct : dossiers gardés
            self.assertEqual(toollib.folders(dlg.mine), ['Atelier/Fraises'])
            pre = dlg.import_preview(*toollib.import_files([self.dbt]), exec_dialog=False)
            self.assertEqual(pre.checked_ids(), [])                     # tout est déjà là
            pre.check_all(True)
            pre.dest.setEditText('Doubles')
            pre.keep_tree.setChecked(False)
            self.assertEqual(dlg.add_chosen(pre.chosen()), 3)
            self.assertEqual(toollib.folders(toollib.load(self.lib)), ['Atelier/Fraises', 'Doubles'])
            pre.deleteLater()
        finally:
            dlg.deleteLater()


if __name__ == '__main__':
    unittest.main()
