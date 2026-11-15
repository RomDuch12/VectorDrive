"""Round 906 : l'outil d'un parcours lu d'un programme (SimPL, ISO…) est le même que celui du programme. Il est reconnu
dans Mes outils puis dans les bibliothèques des plugins (le tools.json de l'atelier) par sa référence ou son nom ; un
outil du document de même référence est repris tel quel ; un outil reconnu est copié dans le document ; un outil
inconnu est proposé à la création, référence (ou numéro), broche et avances préremplies, et rejoint Mes outils."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r906.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from vectordrive.cam import model as M  # noqa: E402
from vectordrive.cam import ncread  # noqa: E402
from vectordrive.plugins import REGISTRY  # noqa: E402

PROG = """%
T1 M6 (ESSAI906 D2)
S18000 M3
G0 X0 Y0 Z5
G1 Z-0.3 F300
G1 X10 Y0 F900
G1 X10 Y10
G0 Z5
T2 M6 (0906283Q)
G0 X20 Y0
G1 Z-0.2 F250
G1 X40 Y0 F1200
G0 Z5
M30
"""


def lib_tool():
    return M.CamTool(name='Cône 30 Datron 906', kind='conique', diameter=3.0, tip=0.6, angle=30.0,
                     ref='0906283Q / 114999', feed=1234.0, spindle=31000.0, number=7)


class Names(unittest.TestCase):

    def test_ref_tokens_and_match(self):
        t = lib_tool()
        self.assertEqual(ncread.ref_tokens(t.ref), {'0906283q', '114999'})
        hit, src = ncread.match_tool({'ref': '0906283Q'}, '', [('Mes outils', []), ('Atelier', [t])])
        self.assertIs(hit, t)
        self.assertEqual(src, 'Atelier')
        self.assertEqual(ncread.match_tool({'ref': 'AUTRE'}, 'rien', [('Atelier', [t])]), (None, ''))

    def test_cotes_of_workshop_names(self):
        c = ncread.cotes_of_name
        self.assertEqual(c('1_Fr_30__0_6'), {'number': 1, 'kind': 'conique', 'angle': 30.0, 'tip': 0.6})
        self.assertEqual(c('3_Fr2_Z1_Lg4'), {'number': 3, 'diameter': 2.0, 'flutes': 1, 'cut_length': 4.0})
        self.assertEqual(c('4_Fr14___surfacer'), {'number': 4, 'diameter': 14.0})
        self.assertEqual(c('3__2_Z1_L4'), {'number': 3, 'diameter': 2.0, 'flutes': 1, 'cut_length': 4.0})
        self.assertEqual(c('22_30__0_2_Pl')['angle'], 30.0)

    def test_proposal_takes_the_program_values(self):
        t = ncread.proposal({'name': '44_Fr6_Z2_Lg6', 'ref': '0068460Y', 'vendor': 'DATRON', 'spindle': 32000,
                             'feed': 1500, 'plunge': 250, 'ramp': 300})
        self.assertEqual((t.name, t.kind, t.diameter, t.flutes, t.cut_length, t.number),
                         ('44_Fr6_Z2_Lg6', 'fraise', 6.0, 2, 6.0, 44))
        self.assertEqual((t.ref, t.vendor, t.spindle, t.feed, t.plunge, t.ramp_feed),
                         ('0068460Y', 'DATRON', 32000.0, 1500.0, 250.0, 300.0))
        self.assertIsNone(ncread.proposal({}, 'T1'))


class Reading(unittest.TestCase):

    def test_iso_tells_number_spindle_and_feeds(self):
        with mock.patch('vectordrive.cam.toollib.library', return_value=[]):
            tp = ncread.read(PROG, 'a.nc')
        info = tp.parts[0].tool_info
        self.assertEqual((info['number'], info['name'], info['spindle']), (1, 'ESSAI906 D2', 18000.0))
        self.assertEqual((info['feed'], info['plunge']), (900.0, 300.0))
        self.assertEqual(tp.parts[0].tool_source, '')                       # inconnu : une proposition
        self.assertEqual((tp.parts[0].tool_guess.number, tp.parts[0].tool_guess.spindle), (1, 18000.0))

    def test_plugin_libraries_are_searched(self):
        t = lib_tool()
        with mock.patch('vectordrive.cam.toollib.library', return_value=[]), \
                mock.patch.dict(REGISTRY.tool_libraries, {'Atelier 906': lambda: [t]}):
            tp = ncread.read(PROG, 'a.nc')
        self.assertIs(tp.parts[1].tool_guess, t)                            # référence écrite au changement d'outil
        self.assertEqual(tp.parts[1].tool_source, 'Atelier 906')

    def test_reader_infos_by_label(self):
        """Un lecteur de plugin (SimPL) donne l'outil de chaque changement : nom, référence, broche, avances."""
        def reader(text, name):
            tp = M.Toolpath(op_id='', tool_id='', name=name, source='nc')
            tp.moves = [M.Move('rapid', 0, 0, 5), M.Move('plunge', 0, 0, -1), M.Move('feed', 5, 0, -1),
                        M.Move('rapid', 9, 0, 5), M.Move('plunge', 9, 0, -1), M.Move('feed', 9, 5, -1)]
            tp.tool_changes = [(0, 'Op_1 — 4_Fr14___surfacer'), (3, 'Op_2 — 1_Fr_30__0_6')]
            tp.tool_infos = {'Op_1 — 4_Fr14___surfacer': {'name': '4_Fr14___surfacer', 'ref': '0906443Z',
                                                           'spindle': 32000, 'feed': 4500},
                             'Op_2 — 1_Fr_30__0_6': {'name': '1_Fr_30__0_6', 'ref': '0906283Q', 'feed': 900}}
            return tp
        t = lib_tool()
        with mock.patch('vectordrive.cam.toollib.library', return_value=[]), \
                mock.patch.object(REGISTRY, 'nc_readers', [('Essai 906', ('.e906',), reader, None)]), \
                mock.patch.dict(REGISTRY.tool_libraries, {'Atelier 906': lambda: [t]}):
            tp = ncread.read('x', 'p.e906')
        first, second = tp.parts
        self.assertEqual(first.tool_info['ref'], '0906443Z')
        self.assertEqual((first.tool_guess.diameter, first.tool_guess.spindle, first.tool_guess.number), (14.0, 32000.0, 4))
        self.assertEqual(first.tool_source, '')
        self.assertIs(second.tool_guess, t)                                 # même référence que dans la bibliothèque


class Form(unittest.TestCase):

    def setUp(self):
        self.tools_file = os.path.join(tempfile.mkdtemp(), 'tools.json')
        self.env = mock.patch.dict(os.environ, {'VECTORDRIVE_TOOLS': self.tools_file})
        self.env.start()
        self.lib = mock.patch('vectordrive.cam.toollib.library', return_value=[])
        self.lib.start()
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.cp, self.lp = self.w.cam_panel, self.w.layers_panel
        s = self.cp.setup()
        s.tools, s.operations = [], []
        self.cp.save(s)

    def tearDown(self):
        self.w.modified = False
        self.w.close()
        self.lib.stop()
        self.env.stop()

    def program(self, libraries=None):
        path = os.path.join(tempfile.mkdtemp(), 'essai.nc')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(PROG)
        with mock.patch.dict(REGISTRY.tool_libraries, libraries or {}):
            self.w.open_nc_program(path)
        return list(self.cp.toolpaths)

    def test_a_document_tool_of_the_same_name_is_kept(self):
        s = self.cp.setup()
        mine = M.CamTool(name='ESSAI906 D2', diameter=2.0, number=5)
        s.tools = [mine]
        self.cp.save(s)
        first, _second = self.program()
        with mock.patch.object(self.cp, 'ask_program_tool') as ask:
            dlg = self.cp.toolpath_form(first, exec_dialog=False)
        ask.assert_not_called()
        self.assertEqual(dlg.widgets['tool_id'].currentData(), mine.id)      # le même outil au formulaire
        dlg.accept()
        s = self.cp.setup()
        self.assertEqual(s.operations[-1].tool_id, mine.id)
        self.assertEqual([t.id for t in s.tools], [mine.id])                 # aucun outil ajouté

    def test_a_library_tool_is_copied_as_it_is(self):
        t = lib_tool()
        _first, second = self.program({'Atelier 906': lambda: [t]})
        with mock.patch.object(self.cp, 'ask_program_tool') as ask:
            dlg = self.cp.toolpath_form(second, exec_dialog=False)
        ask.assert_not_called()
        dlg.accept()
        s = self.cp.setup()
        used = s.tool(s.operations[-1].tool_id)
        self.assertEqual((used.name, used.ref, used.feed, used.angle), (t.name, t.ref, 1234.0, 30.0))
        self.assertNotEqual(used.id, t.id)                                    # une copie, au numéro du programme
        self.assertEqual(used.number, 2)

    def test_an_unknown_tool_is_created_with_the_program_values(self):
        first, _second = self.program()
        _row = self.lp.traj_row()
        kid = _row.child(0)
        self.assertTrue(kid.text(2).endswith(' ?'))                           # inconnu, signalé
        from vectordrive.ui import cam_panel as CP
        with mock.patch.object(self.cp, 'ask_program_tool', return_value='create') as ask, \
                mock.patch.object(CP.FieldsDialog, 'exec', return_value=1):
            dlg = self.cp.toolpath_form(first, exec_dialog=False)
        ask.assert_called_once()
        dlg.accept()
        s = self.cp.setup()
        used = s.tool(s.operations[-1].tool_id)
        self.assertEqual((used.name, used.number, used.spindle, used.feed, used.plunge, used.diameter),
                         ('ESSAI906 D2', 1, 18000.0, 900.0, 300.0, 2.0))
        from vectordrive.cam import toollib
        saved = [(t.name, t.folder, t.spindle) for t in toollib.load(self.tools_file)]
        self.assertEqual(saved, [('ESSAI906 D2', 'Outils des programmes', 18000.0)])      # dans Mes outils

    def test_cancelled_creation_changes_nothing(self):
        first, _second = self.program()
        with mock.patch.object(self.cp, 'ask_program_tool', return_value='cancel'):
            self.assertIsNone(self.cp.toolpath_form(first, exec_dialog=False))
        s = self.cp.setup()
        self.assertEqual(s.operations, [])
        self.assertFalse(os.path.exists(self.tools_file))
        self.assertEqual(len(self.w.canvas.doc.layers), 1)


if __name__ == '__main__':
    unittest.main()
