"""Round 928 : l'outil d'un programme lu, créé ou pointé vers un outil existant (« Retenir ce choix pour les prochaines
fois », reconnu aux lectures suivantes, changé ensuite par un double-clic sur l'outil du parcours) ; les outils inconnus
proposés à la lecture ; le choix d'outil du formulaire d'une opération avec les bibliothèques des plugins (outils
DATRON de l'atelier), les dossiers de la racine ouverts."""
import json
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r928.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication, QDialog

app = QApplication.instance() or QApplication([])

from vectordrive.cam import model as M  # noqa: E402
from vectordrive.cam import ncread, toollib  # noqa: E402
from vectordrive.plugins import REGISTRY  # noqa: E402

PROG = """%
T3 M6 (MYSTERE A928)
S18000 M3
G0 X0 Y0 Z5
G1 Z-0.3 F300
G1 X10 Y0 F900
G0 Z5
T4 M6 (MYSTERE B928)
G0 X20 Y0
G1 Z-0.2 F250
G1 X40 Y0 F1200
G0 Z5
M30
"""


def datron():
    """Une bibliothèque de plugin : deux outils rangés, un sans dossier."""
    return [M.CamTool(name='Cyl 2 928', kind='fraise', diameter=2.0, ref='D928-2', folder='Datron/Fraises'),
            M.CamTool(name='Con 30 928', kind='conique', diameter=3.0, angle=30.0, tip=0.1, ref='D928-30',
                      folder='Datron/Coniques'),
            M.CamTool(name='Sans dossier 928', kind='fraise', diameter=1.0, ref='D928-1')]


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

    def save_mine(self, tools):
        toollib.save(tools, toollib.default_path(), [])


class Library(Base):

    def test_form_offers_the_plugin_libraries(self):
        mine = M.CamTool(name='Mienne 928', diameter=4.0, ref='MINE928', folder='Atelier')
        same = M.CamTool(name='Cyl 2 928', kind='fraise', diameter=2.0, ref='D928-2', folder='Copie')
        self.save_mine([mine, same])
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            cp = w.cam_panel
            s = cp.setup()
            tool = M.CamTool(name='Doc', diameter=1.0)
            s.tools, s.operations = [tool], [M.Operation(kind='poche', tool_id=tool.id)]
            cp.save(s)
            cp.refresh()
            cp._select_row(cp.ops, 0)
            dlg = cp.edit_op(exec_dialog=False, take_selection=False)
            got = {t.name: toollib.folder_of(t) for t in dlg.library.values()}
            self.assertEqual(got, {'Mienne 928': 'Atelier', 'Cyl 2 928': 'Copie',
                                   'Con 30 928': 'Datron/Coniques/Con 30',
                                   'Sans dossier 928': 'Datron/Cylindriques/Cyl 1'})   # vu dans Mes outils : une fois
            dlg.reject()
        finally:
            w.modified = False
            w.close()

    def test_root_folders_are_open(self):
        from vectordrive.ui.tool_picker import ToolPickerDialog
        lib = {t.id: t for t in datron()[:2] + [M.CamTool(name='Import 928', folder='Import TE/Laiton')]}
        dlg = ToolPickerDialog(None, [], lib)
        tops = [dlg.tree.topLevelItem(i) for i in range(dlg.tree.topLevelItemCount())]
        self.assertEqual([t.text(0) for t in tops], ['📁 Datron  (2)', '📁 Import TE  (1)'])
        self.assertTrue(all(t.isExpanded() for t in tops))                   # leur premier niveau en vue
        subs = [tops[0].child(i) for i in range(tops[0].childCount())]
        self.assertIn('📁 Coniques  (1)', [c.text(0) for c in subs])
        self.assertFalse(any(c.isExpanded() for c in subs if c.childCount()))   # pas plus loin
        dlg.deleteLater()


class Aliases(Base):

    def test_a_remembered_tool_is_recognized_at_the_next_reading(self):
        mine = M.CamTool(name='Fraise maison 928', diameter=0.5, ref='MAISON928')
        self.save_mine([mine])
        first = ncread.read(PROG, 'essai.nc').parts[0]
        self.assertEqual(first.tool_source, '')                              # inconnu
        self.assertTrue(ncread.remember(first.tool_info, mine))
        again = ncread.read(PROG, 'essai.nc').parts
        self.assertEqual((again[0].tool_guess.name, again[0].tool_source, again[0].tool_alias),
                         ('Fraise maison 928', 'Mes outils', True))
        self.assertEqual(again[1].tool_source, '')                           # l'autre outil : toujours inconnu
        lib = ncread.read(PROG.replace('MYSTERE A928', 'MYSTERE B928'), 'b.nc').parts[0]
        self.assertEqual(lib.tool_source, '')
        ncread.remember(first.tool_info, datron()[1])                         # changé : l'outil d'une bibliothèque
        self.assertEqual(ncread.read(PROG, 'essai.nc').parts[0].tool_guess.name, 'Con 30 928')
        self.assertEqual(len(ncread.load_aliases()), 1)                      # remplacée, pas ajoutée
        self.assertEqual(ncread.forget(first.tool_info), 1)
        self.assertEqual(ncread.read(PROG, 'essai.nc').parts[0].tool_source, '')


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
        return list(self.cp.toolpaths)

    def pick(self, dlg, name):
        it = next(i for i in dlg._items() if i.data(0, 0x0100) and dlg._tool(i.data(0, 0x0100)) is not None
                  and dlg._tool(i.data(0, 0x0100)).name == name)
        dlg._pick(it)

    def test_unknown_tools_are_offered_at_reading(self):
        self.program()
        dlg = self.cp._unknown_dlg
        self.assertTrue(dlg.isVisible())
        self.assertFalse(dlg.isModal())
        self.assertEqual(len(dlg.rows), 2)
        pick = dlg.pick(0, exec_dialog=False)
        self.pick(pick, 'Con 30 928')
        self.assertEqual(dlg.rows[0][3].text(), '✓ Con 30 928')
        self.assertFalse(dlg.rows[0][1].isEnabled())                          # plus rien à créer
        self.cp._unknown_dlg = None
        self.w.settings.setValue('fao/outils_inconnus', False)               # option FAO : sans fenêtre
        try:
            self.program(PROG.replace('928)', '928 BIS)'))
            self.assertIsNone(self.cp._unknown_dlg)
        finally:
            self.w.settings.setValue('fao/outils_inconnus', True)

    def test_a_chosen_tool_is_remembered_or_not(self):
        first, second = self.program()
        dlg = self.cp.choose_program_tool(first, exec_dialog=False)
        self.assertTrue(dlg.remember.isChecked())                             # retenu par défaut
        self.pick(dlg, 'Cyl 2 928')
        self.assertEqual((first.tool_guess.name, first.tool_source, first.tool_alias), ('Cyl 2 928', 'Datron', True))
        self.assertEqual(second.tool_source, '')                              # un autre outil du programme
        with open(self.alias_file, encoding='utf-8') as f:
            saved = json.load(f)['associations']
        self.assertEqual([(a['programme']['name'], a['outil']['ref']) for a in saved], [('MYSTERE A928', 'D928-2')])
        kid = self.lp.traj_row().child(0)
        self.assertFalse(kid.text(2).endswith(' ?'))
        self.assertIn('Datron', kid.toolTip(2))
        again = ncread.read(PROG, 'x.nc').parts[0]
        self.assertEqual(again.tool_guess.ref, 'D928-2')                      # reconnu à la lecture suivante
        dlg = self.cp.choose_program_tool(first, exec_dialog=False)           # changé ensuite, pour cette fois
        dlg.remember.setChecked(False)
        self.pick(dlg, 'Con 30 928')
        self.assertEqual(first.tool_guess.name, 'Con 30 928')
        self.assertEqual(ncread.load_aliases(), [])                           # l'association d'avant oubliée

    def test_a_document_tool_joins_my_tools_when_remembered(self):
        s = self.cp.setup()
        doc = M.CamTool(name='Outil du document 928', diameter=0.8, ref='DOC928', number=7)
        s.tools = [doc]
        self.cp.save(s)
        first, _second = self.program()
        dlg = self.cp.choose_program_tool(first, exec_dialog=False)
        self.pick(dlg, 'Outil du document 928')
        self.assertEqual((first.tool_id, first.tool_alias), (doc.id, True))
        self.assertEqual([(t.name, t.folder) for t in toollib.load(self.tools_file)],
                         [('Outil du document 928', ncread.PROGRAM_FOLDER)])     # pour le retrouver ensuite
        self.assertEqual(ncread.read(PROG, 'x.nc').parts[0].tool_guess.ref, 'DOC928')

    def test_ask_box_can_point_to_an_existing_tool(self):
        first, _second = self.program()
        t = datron()[0]
        with mock.patch.object(self.cp, 'ask_program_tool', return_value='pick'), \
                mock.patch.object(self.cp, 'choose_program_tool', return_value=t, create=True):
            tool, new = self.cp.program_tool(first)
        self.assertEqual((tool.name, tool.ref, new), ('Cyl 2 928', 'D928-2', True))
        self.assertNotEqual(tool.id, t.id)                                    # une copie pour le document

    def test_the_chosen_tool_is_reused_from_the_document(self):
        first, second = self.program()
        t = datron()[0]
        copy = M.CamTool.from_dict(t.to_dict())
        copy.id = M.new_id()
        s = self.cp.setup()
        s.tools = [copy]
        self.cp.save(s)
        first.tool_info = dict(first.tool_info, ref='PROG928')               # le programme donne une autre référence
        first.tool_guess, first.tool_source, first.tool_alias = t, 'Datron', True
        with mock.patch.object(self.cp, 'ask_program_tool') as ask:
            tool, new = self.cp.program_tool(first)
        ask.assert_not_called()
        self.assertEqual((tool.id, new), (copy.id, False))                    # le même, pas une seconde copie

    def test_create_from_the_reading_window(self):
        first, second = self.program(PROG.replace('MYSTERE B928', 'MYSTERE A928'))
        dlg = self.cp._unknown_dlg
        self.assertEqual(len(dlg.rows), 1)                                    # un seul outil, deux parcours
        form = dlg.create(0, exec_dialog=False)
        form.accept()
        self.assertEqual([(t.name, t.folder) for t in toollib.load(self.tools_file)],
                         [('MYSTERE A928', ncread.PROGRAM_FOLDER)])
        self.assertEqual((first.tool_source, second.tool_source), ('Mes outils', 'Mes outils'))
        self.assertEqual(dlg.rows[0][3].text(), '✓ MYSTERE A928')

    def test_double_click_on_the_tool_column(self):
        self.program()
        kid = self.lp.traj_row().child(0)
        with mock.patch.object(self.cp, 'choose_program_tool', create=True) as choose, \
                mock.patch.object(self.cp, 'toolpath_form') as form:
            self.lp._double(kid, self.lp.COL_TOOL)
            choose.assert_called_once()
            form.assert_not_called()
            self.lp._double(kid, self.lp.COL_NAME)
            form.assert_called_once()
        self.assertIn('Double-clic sur l’outil', kid.toolTip(self.lp.COL_TOOL))


if __name__ == '__main__':
    unittest.main()
