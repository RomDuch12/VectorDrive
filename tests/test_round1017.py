"""Round 1017 : demande du 14/11, 19 h 45 — « La colonne droite affiche pour l'outil sélectionné le dxf le step et
toutes les specs outil modifiables (et affichable en colonne si user le souhaite) »."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r1017.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from vectordrive.cam import model, toollib  # noqa: E402


class Settings(dict):
    def value(self, k, d=None):
        return self.get(k, d)

    def setValue(self, k, v):                                                # noqa: N802
        self[k] = v


class Sheet(unittest.TestCase):

    def setUp(self):
        self._env = os.environ.get('VECTORDRIVE_TOOLS')
        d = tempfile.mkdtemp()
        self.path = os.path.join(d, 'tools.json')
        os.environ['VECTORDRIVE_TOOLS'] = self.path
        self.dxf = os.path.join(d, 'outil.dxf')
        with open(self.dxf, 'w', encoding='ascii') as f:
            f.write('0\nEOF\n')
        self.mine = model.CamTool(name='Mine 1017', diameter=1.5875, number=1234, feed=500.0, folder='Datron/Fraises',
                                  geometry={'D2': 3.0}, drawings={'dxf': self.dxf, 'step': os.path.join(d, 'x.step')})
        self.other = model.CamTool(name='Autre 1017', diameter=2.0, number=7, feed=300.0)
        toollib.save([self.mine, self.other], self.path)
        self.plugin = model.CamTool(name='Plugin 1017', diameter=3.0, number=5)
        self.doc_tool = model.CamTool(name='Doc 1017', diameter=1.0, number=6)

    def tearDown(self):
        if self._env is None:
            os.environ.pop('VECTORDRIVE_TOOLS', None)
        else:
            os.environ['VECTORDRIVE_TOOLS'] = self._env

    def library(self, new_ids=False):
        out = {}
        for t in (self.mine, self.other, self.plugin):
            c = model.CamTool.from_dict(t.to_dict())
            if new_ids:                                                       # fichier sans identifiants : autres ids
                c.id = model.new_id()
            out[c.id] = c
        return out

    def picker(self, st=None, cls=None, new_ids=False):
        from vectordrive.ui.tool_picker import ToolPickerDialog
        dlg = (cls or ToolPickerDialog)(None, [self.doc_tool], self.library(new_ids),
                                        settings=st if st is not None else Settings())
        self.addCleanup(dlg.deleteLater)
        return dlg

    def select(self, dlg, name):
        it = next(i for i in dlg._items() if i.data(0, Qt.ItemDataRole.UserRole) and name in i.text(0))
        dlg.tree.setCurrentItem(it)
        return it

    def on_disk(self, name):
        return {t.name: t for t in toollib.load(self.path)}[name]

    def test_sheet_of_a_tool_of_mine_saved_in_the_library(self):
        from vectordrive.ui import tool_columns as TC
        from vectordrive.ui.tool_sheet import MINE
        dlg = self.picker()
        self.select(dlg, 'Mine 1017')
        sheet = dlg.sheet                                                     # avant : pas de fiche, un résumé
        self.assertEqual(sheet.source, MINE)
        self.assertEqual(sheet.w['feed'].value(), 500.0)
        self.assertTrue(sheet.save_btn.isEnabled())
        self.assertEqual(sheet.drawing_paths, {'dxf': self.dxf})              # le STEP absent du disque : rien
        self.assertFalse(sheet.drawing_buttons[('dxf', 'open')].isEnabled())  # pas ouverte sur VectorDrive
        sheet.w['feed'].setValue(820.0)
        sheet.w['ref'].setText('R-1017')
        sheet.w['ref'].textEdited.emit('R-1017')
        self.assertTrue(sheet.save())
        again = self.on_disk('Mine 1017')
        self.assertEqual((again.feed, again.ref), (820.0, 'R-1017'))         # réécrit dans Mes outils
        self.assertEqual((again.diameter, again.number), (1.5875, 1234))     # le reste : valeurs exactes
        self.assertEqual((again.folder, again.geometry, again.drawings['dxf']), ('Datron/Fraises', {'D2': 3.0}, self.dxf))
        self.assertEqual(again.catalog.get('reference'), 'R-1017')
        it = next(i for i in dlg._items() if i.data(0, Qt.ItemDataRole.UserRole) and 'Mine 1017' in i.text(0))
        self.assertEqual(it.text(TC.KEYS.index('feed')), '820')              # la ligne suit
        self.assertIs(dlg.tree.currentItem(), it)
        self.assertTrue(dlg.edited)

    def test_unsaved_sheet_kept_and_search_kept(self):
        dlg = self.picker(new_ids=True)                                       # ids d'un autre chargement
        dlg.search.setText('1017')
        self.select(dlg, 'Mine 1017')
        self.assertEqual(dlg.sheet.source, 'mine')                            # reconnu comme le même outil
        dlg.sheet.w['feed'].setValue(640.0)                                   # modifié, pas enregistré…
        self.select(dlg, 'Autre 1017')                                        # … un autre outil montré : enregistré
        self.assertEqual(self.on_disk('Mine 1017').feed, 640.0)
        app.processEvents()
        self.assertIn('Autre 1017', dlg.tree.currentItem().text(0))         # la recherche garde l'outil montré
        dlg.sheet.w['spindle'].setValue(12345.0)
        dlg._pick(dlg.tree.currentItem())                                     # OK : enregistré avant de choisir
        self.assertEqual(self.on_disk('Autre 1017').spindle, 12345.0)

    def test_plugin_read_only_document_tool_and_program(self):
        from vectordrive.ui.tool_picker import ProgramToolDialog
        from vectordrive.ui.tool_sheet import DOC, DOC_RO, PLUGIN
        dlg = self.picker()
        self.select(dlg, 'Plugin 1017')
        self.assertEqual(dlg.sheet.source, PLUGIN)
        self.assertFalse(dlg.sheet.save_btn.isEnabled())
        self.assertFalse(dlg.sheet.w['feed'].isEnabled())
        self.assertFalse(dlg.sheet.save())
        self.select(dlg, 'Doc 1017')
        self.assertEqual(dlg.sheet.source, DOC)
        dlg.sheet.w['diameter'].setValue(1.5)
        self.assertTrue(dlg.sheet.save())
        self.assertEqual(self.doc_tool.diameter, 1.5)                         # l'outil du document
        prog = self.picker(cls=ProgramToolDialog)
        self.select(prog, 'Doc 1017')
        self.assertEqual(prog.sheet.source, DOC_RO)                           # outil d'un programme : en lecture

    def test_shown_as_a_column(self):
        from vectordrive.ui import tool_columns as TC
        st = Settings()
        dlg = self.picker(st)
        self.select(dlg, 'Mine 1017')
        h, t_col = dlg.tree.header(), TC.KEYS.index('number')
        box = dlg.sheet.col_boxes['number']
        self.assertFalse(box.isChecked())
        box.setChecked(True)                                                  # « en colonne » : la colonne T
        self.assertFalse(h.isSectionHidden(t_col))
        self.assertIn('outils/choix_colonnes/entete', st)
        TC.set_shown(dlg.tree, 'number', False, st, 'outils/choix_colonnes')  # clic droit : la case suit
        self.assertFalse(box.isChecked())
        self.assertTrue(dlg.sheet.col_boxes['diameter'].isChecked())
        self.assertNotIn('tip', dlg.sheet.col_boxes)                          # sans colonne : pas de case
        self.assertIn('tip', dlg.sheet.w)


if __name__ == '__main__':
    unittest.main()
