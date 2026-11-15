"""Round 918 : un outil proposé sans nom (« T3 ») n'est pas repris en silence d'un programme à l'autre ; une référence
d'outil collée par « _ » ou « - » dans le commentaire, ou qui contient une espace, est reconnue ; la pointe d'un cône
suivie d'un mot n'est pas tronquée ; un préréglage de texte mal formé est écarté sans planter."""
import json
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r918.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from vectordrive.cam import model as M  # noqa: E402
from vectordrive.cam import ncread  # noqa: E402


class RefInTheComment(unittest.TestCase):

    def test_joined_or_spaced_refs(self):
        mine = M.CamTool(name='Fraise 918', kind='fraise', diameter=2.0, ref='0918443G')
        spaced = M.CamTool(name='Autre 918', kind='fraise', diameter=3.0, ref='ABC 91845')
        libs = [('Atelier', [mine, spaced])]
        for comment in ('FR2_0918443G', 'FR2-0918443G', '0918443G.', 'D2 (0918443g)', 'FR2_0918443G_Z2'):
            with self.subTest(comment=comment):
                self.assertEqual(ncread.match_tool({'name': comment}, '', libs), (mine, 'Atelier'))
        self.assertEqual(ncread.match_tool({'name': 'FRAISE ABC 91845'}, '', libs), (spaced, 'Atelier'))
        for comment in ('X0918443GB', 'FR20918443G', '0918443G5', 'ABC 918456'):
            with self.subTest(comment=comment):                        # pas un mot entier
                self.assertEqual(ncread.match_tool({'name': comment}, '', libs), (None, ''))

    def test_not_the_whole_part_of_a_decimal(self):
        mine = M.CamTool(name='Fraise 918', kind='fraise', diameter=2.0, ref='91845')
        libs = [('Atelier', [mine])]
        self.assertEqual(ncread.match_tool({'name': 'L 91845,5'}, '', libs), (None, ''))
        self.assertEqual(ncread.match_tool({'name': 'REF_91845'}, '', libs), (mine, 'Atelier'))


class ConeTip(unittest.TestCase):

    def test_tip_followed_by_a_word(self):
        for name, tip in (('1_Fr_30__0_6 Balay', 0.6), ('Fr_30__0_6mm', 0.6), ('7_Fr_60__0_2.', 0.2),
                          ('Fr_30__0_15 L4', 0.15), ('2_Fr_90__1', 1.0), ('5_Fr_60__0_Z1', 0.0)):
            with self.subTest(name=name):
                c = ncread.cotes_of_name(name)
                self.assertEqual(c.get('kind'), 'conique')
                self.assertAlmostEqual(c['tip'], tip)
        self.assertEqual(ncread.cotes_of_name('5_Fr_60__0_Z1').get('flutes'), 1)

    def test_diameter_and_length_not_truncated(self):
        self.assertAlmostEqual(ncread.cotes_of_name('3_Fr2_5 Balay')['diameter'], 2.5)
        self.assertAlmostEqual(ncread.cotes_of_name('3_Fr2_5_Z2_Lg6_5 ALU')['cut_length'], 6.5)
        self.assertAlmostEqual(ncread.cotes_of_name('3_Fr2_5_Z2_Lg6_5 ALU')['diameter'], 2.5)
        self.assertNotIn('diameter', ncread.cotes_of_name('Fr2.5'))     # pas la partie entière d'un décimal


class ProposalNotReused(unittest.TestCase):

    def setUp(self):
        self.tools_file = os.path.join(tempfile.mkdtemp(), 'tools.json')
        self.env = mock.patch.dict(os.environ, {'VECTORDRIVE_TOOLS': self.tools_file})
        self.env.start()
        self.lib = mock.patch('vectordrive.cam.toollib.library', return_value=[])
        self.lib.start()
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.cp = self.w.cam_panel
        s = self.cp.setup()
        s.tools, s.operations = [], []
        self.cp.save(s)

    def tearDown(self):
        self.w.modified = False
        self.w.close()
        self.lib.stop()
        self.env.stop()

    def read(self, text, name):
        with mock.patch.object(ncread, 'libraries', return_value=[]):
            return ncread.read(text, name)

    def test_unnamed_tool_of_another_program_is_asked(self):
        a = self.read('%\nT3 M6\nS18000 M3\nG0 X0 Y0 Z5\nG1 Z-0.2 F300\nG1 X5 F900\nM30\n', 'a918.nc')
        b = self.read('%\nT3 M6\nS9000 M3\nG0 X0 Y0 Z5\nG1 Z-0.5 F100\nG1 X5 F400\nM30\n', 'b918.nc')
        self.assertEqual(a.tool_guess.name, 'T3')                       # proposé sous un nom générique
        with mock.patch.object(self.cp, 'ask_program_tool', return_value='keep') as ask:
            got_a, new_a = self.cp.program_tool(a)
            s = self.cp.setup()
            s.tools.append(got_a)
            self.cp.save(s)
            got_b, new_b = self.cp.program_tool(b)
        self.assertEqual(ask.call_count, 2)                              # le second aussi est proposé
        self.assertTrue(new_b)
        self.assertNotEqual(got_b.id, got_a.id)
        self.assertEqual(got_b.spindle, 9000.0)

    def test_user_tool_named_like_a_proposal_is_not_taken(self):
        s = self.cp.setup()
        mine = M.CamTool(name='T1', ref='XYZ918', kind='conique', angle=30.0, number=1)
        s.tools = [mine]
        self.cp.save(s)
        c = self.read('%\nT1 M6\nS20000 M3\nG0 X0 Y0 Z5\nG1 Z-0.2 F300\nG1 X5 F900\nM30\n', 'c918.nc')
        with mock.patch.object(self.cp, 'ask_program_tool', return_value='keep') as ask:
            got, new = self.cp.program_tool(c)
        ask.assert_called_once()
        self.assertNotEqual(got.id, mine.id)
        # un outil reconnu dans une bibliothèque, déjà dans le document : repris, sans rien demander
        lib = M.CamTool(name='Fraise atelier 918', kind='fraise', diameter=2.0, ref='0918777G', number=4)
        s = self.cp.setup()
        mine = M.CamTool.from_dict(lib.to_dict())
        mine.id = M.new_id()
        s.tools = [mine]
        self.cp.save(s)
        tp = M.Toolpath(op_id='', tool_id='', name='essai 918', source='nc')
        tp.tool_info = {'name': 'FR2_0918777G', 'number': 4}
        tp.tool_guess, tp.tool_source = lib, 'Atelier'
        with mock.patch.object(self.cp, 'ask_program_tool') as ask:
            got, new = self.cp.program_tool(tp)
        ask.assert_not_called()
        self.assertEqual((got.id, new), (mine.id, False))


class MalformedPresets(unittest.TestCase):

    def test_unhashable_values_are_dropped(self):
        from vectordrive.ui import text_presets as TP
        bad = {'attrs': {'align': ['left'], 'size': 4.0},
               'extra': {'spacing_mode': {'x': 1}, 'line_mode': {'mode': ['fixed'], 'value': 7.0}}}
        n = TP.norm(bad)
        self.assertEqual(n['attrs'], {'size': 4.0})
        self.assertEqual(n['extra'], {})
        ok = TP.norm({'attrs': {'align': 'center'}, 'extra': {'spacing_mode': 'tight', 'line_mode': {'mode': 'fixed'}}})
        self.assertEqual((ok['attrs']['align'], ok['extra']['spacing_mode'], ok['extra']['line_mode']['mode']),
                         ('center', 'tight', 'fixed'))

    def test_saved_malformed_preset_loads(self):
        from vectordrive.ui import text_presets as TP

        class Settings:
            def __init__(self, raw):
                self.raw = raw

            def value(self, key, default=None):
                return self.raw

        raw = json.dumps({'Mal formé 918': {'attrs': {'align': ['left'], 'size': 5.0},
                                            'extra': {'spacing_mode': [1]}}})
        got = TP.load(Settings(raw))
        self.assertEqual(got['Mal formé 918']['attrs'].get('size'), 5.0)
        self.assertNotIn('align', got['Mal formé 918']['attrs'])


if __name__ == '__main__':
    unittest.main()
