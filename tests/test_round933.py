"""Round 933 : les outils retenus pour les programmes lus, en liste (Bibliothèque d'outils, « Outils des programmes
lus… ») : les voir, en oublier ; un fichier abîmé ou inaccessible n'est ni réécrit ni mis de côté en le regardant."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r933.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from vectordrive.cam import model as M  # noqa: E402
from vectordrive.cam import ncread  # noqa: E402


class Aliases(unittest.TestCase):

    def setUp(self):
        d = tempfile.mkdtemp()
        self.tools_file = os.path.join(d, 'tools.json')
        self.alias = pathlib.Path(d) / 'associations_programmes.json'
        self.env = mock.patch.dict(os.environ, {'VECTORDRIVE_TOOLS': self.tools_file})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.a = M.CamTool(name='Cyl 2 933', kind='fraise', diameter=2.0, ref='D933-2')
        self.b = M.CamTool(name='V60 933', kind='conique', diameter=3.0, angle=60.0)

    def dialog(self):
        from vectordrive.ui.tool_picker import ProgramAliasesDialog
        dlg = ProgramAliasesDialog()
        self.addCleanup(dlg.deleteLater)
        return dlg

    def test_list_and_forget(self):
        ncread.remember({'name': 'MYSTERE A933', 'number': 3}, self.a)
        ncread.remember({'ref': 'R-B933'}, self.b)
        dlg = self.dialog()
        self.assertEqual(dlg.path, self.alias)                                # à côté de Mes outils
        self.assertEqual(dlg.tree.topLevelItemCount(), 2)
        first = dlg.tree.topLevelItem(0)
        self.assertIn('MYSTERE A933', first.text(0))
        self.assertIn('T3', first.text(0))
        self.assertIn('Cyl 2 933', first.text(1))
        self.assertIn('Ø2', first.text(1))
        self.assertFalse(dlg.forget_button.isEnabled())                       # rien de choisi
        first.setSelected(True)
        self.assertTrue(dlg.forget_button.isEnabled())
        dlg.forget_button.click()
        left = ncread.load_aliases()
        self.assertEqual([a['programme'] for a in left], [{'ref': 'R-B933'}])
        self.assertEqual(dlg.tree.topLevelItemCount(), 1)
        self.assertIn('V60 933', dlg.tree.topLevelItem(0).text(1))

    def test_empty_damaged_and_unreachable(self):
        dlg = self.dialog()
        self.assertEqual(dlg.tree.topLevelItemCount(), 0)
        self.assertIn('Aucun outil retenu', dlg.state.text())
        self.alias.write_text('{abîmé', encoding='utf-8')
        dlg = self.dialog()
        self.assertIn('abîmé', dlg.state.text())
        self.assertEqual(self.alias.read_text(encoding='utf-8'), '{abîmé')    # regardé : ni réécrit ni mis de côté
        self.assertFalse(self.alias.with_name('associations_programmes.abime.json').exists())
        self.assertFalse(dlg.forget_button.isEnabled())
        self.alias.unlink()
        ncread.remember({'name': 'MYSTERE A933'}, self.a)
        before = self.alias.read_bytes()
        dlg = self.dialog()
        dlg.tree.topLevelItem(0).setSelected(True)
        with mock.patch.object(pathlib.Path, 'read_text', side_effect=PermissionError('partage absent')):
            self.assertEqual(dlg.forget_selected(), 0)
        self.assertIn('inaccessible', dlg.state.text())
        self.assertEqual(self.alias.read_bytes(), before)

    def test_a_reference_with_nothing_readable_is_still_one_tool(self):
        odd = {'ref': '/'}                                                    # ni chiffre ni lettre : aucune référence lisible
        self.assertTrue(ncread.remember(odd, self.a))
        self.assertTrue(ncread.remember(odd, self.b))                         # remplacée, pas ajoutée
        left = ncread.load_aliases()
        self.assertEqual(len(left), 1)
        self.assertEqual(ncread.alias_of(odd, left)['name'], 'V60 933')
        dlg = self.dialog()
        dlg.tree.topLevelItem(0).setSelected(True)
        self.assertEqual(dlg.forget_selected(), 1)                            # et elle s'oublie
        self.assertEqual(ncread.load_aliases(), [])

    def test_from_the_tool_library(self):
        from vectordrive.ui.toollib_dialog import ToolLibraryDialog
        ncread.remember({'name': 'MYSTERE A933'}, self.a)
        lib = ToolLibraryDialog(None)
        self.addCleanup(lib.deleteLater)
        act = lib.acts['aliases']
        self.assertIn(act, lib.buttons['more'].menu().actions())
        self.assertIn(act, lib.context_menu(exec_menu=False).actions())
        dlg = lib.program_aliases(exec_dialog=False)
        self.addCleanup(dlg.deleteLater)
        self.assertEqual(dlg.tree.topLevelItemCount(), 1)


if __name__ == '__main__':
    unittest.main()
