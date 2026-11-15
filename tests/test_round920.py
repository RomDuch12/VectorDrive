"""Round 920 : une référence collée par « _ » n'est pas la décimale d'une cote ; le Ø « __2_5 » n'est pas tronqué ;
une référence après « chiffre, » est reconnue, une variante « -2 » / « _2 » ne fait pas prendre l'outil de la
référence courte, la plus longue référence l'emporte ; un outil proposé au nom long se retrouve dans le document ; un
nombre démesuré dans un préréglage est écarté."""
import json
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r920.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from vectordrive.cam import model as M  # noqa: E402
from vectordrive.cam import ncread  # noqa: E402


class CotesWithAJoinedRef(unittest.TestCase):

    def test_ref_is_not_a_decimal(self):
        self.assertAlmostEqual(ncread.cotes_of_name('FR2_0920443G')['diameter'], 2.0)
        c = ncread.cotes_of_name('3_Fr2_Z2_Lg6_0920443G')
        self.assertAlmostEqual(c['diameter'], 2.0)
        self.assertAlmostEqual(c['cut_length'], 6.0)
        c = ncread.cotes_of_name('1_Fr_30__0_2_0920443G')
        self.assertEqual((c.get('kind'), c.get('angle')), ('conique', 30.0))
        self.assertAlmostEqual(c['tip'], 0.2)
        self.assertNotIn('diameter', ncread.cotes_of_name('FR20920443G'))      # pas un Ø de 8 chiffres

    def test_workshop_diameter_and_fine_tip(self):
        self.assertAlmostEqual(ncread.cotes_of_name('3__2_5 ALU')['diameter'], 2.5)
        self.assertAlmostEqual(ncread.cotes_of_name('1_Fr_30__0_125')['tip'], 0.125)
        self.assertAlmostEqual(ncread.cotes_of_name('4__14_Balay')['diameter'], 14.0)


class RefsInTheComment(unittest.TestCase):

    def test_after_a_digit_and_a_comma(self):
        mine = M.CamTool(name='Fraise 920', kind='fraise', diameter=2.0, ref='0920443G')
        num = M.CamTool(name='Cône 920', kind='conique', angle=30.0, ref='920917')
        libs = [('Atelier', [mine, num])]
        self.assertEqual(ncread.match_tool({'name': 'FR2,0920443G'}, '', libs), (mine, 'Atelier'))
        self.assertEqual(ncread.match_tool({'name': '(D3,920917)'}, '', libs), (num, 'Atelier'))

    def test_variant_and_longest_ref(self):
        short = M.CamTool(name='Court 920', kind='fraise', diameter=2.0, ref='920917')
        variant = M.CamTool(name='Variante 920', kind='fraise', diameter=2.0, ref='920917-2')
        self.assertEqual(ncread.match_tool({'name': 'FRAISE 920917-2'}, '', [('A', [short, variant])]), (variant, 'A'))
        for comment in ('FRAISE 920917-2', 'FRAISE 920917_2'):
            with self.subTest(comment=comment):                          # une variante : pas l'outil court
                self.assertEqual(ncread.match_tool({'name': comment}, '', [('A', [short])]), (None, ''))
        bare = M.CamTool(name='Nu 920', kind='fraise', diameter=1.0, ref='92045')
        spaced = M.CamTool(name='Espacé 920', kind='fraise', diameter=3.0, ref='ABC 92045')
        self.assertEqual(ncread.match_tool({'name': 'FRAISE ABC 92045'}, '', [('A', [bare, spaced])]), (spaced, 'A'))


class LongProposalName(unittest.TestCase):

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

    def part(self, name):
        tp = M.Toolpath(op_id='', tool_id='', name='essai 920', source='nc')
        tp.tool_info = {'name': name, 'number': 3, 'spindle': 18000.0}   # broche lue : une proposition
        tp.tool_guess, tp.tool_source = ncread.proposal(tp.tool_info, tp.name), ''
        return tp

    def test_found_again_in_the_document(self):
        long = 'FRAISE CARBURE 2 DENTS DIAMETRE 2 LONGUEUR UTILE 6 POUR ALUMINIUM ESSAI 920'
        self.assertGreater(len(long), 60)
        with mock.patch.object(self.cp, 'ask_program_tool', return_value='keep') as ask:
            got, new = self.cp.program_tool(self.part(long))
            s = self.cp.setup()
            s.tools.append(got)
            self.cp.save(s)
            again, new2 = self.cp.program_tool(self.part(long))
        self.assertEqual(ask.call_count, 1)                              # pas redemandé, pas en double
        self.assertEqual((again.id, new2), (got.id, False))


class HugeNumberInAPreset(unittest.TestCase):

    def test_dropped(self):
        from vectordrive.ui import text_presets as TP
        n = TP.norm({'attrs': {'size': 10 ** 400, 'width_ratio': 0.9}, 'extra': {'italic': -10 ** 400}})
        self.assertEqual(n['attrs'], {'width_ratio': 0.9})
        self.assertEqual(n['extra'], {})

        class Settings:
            def value(self, key, default=None):
                return json.dumps({'Démesuré 920': {'attrs': {'size': 10 ** 400, 'line_spacing': 1.5}}})

        self.assertEqual(TP.load(Settings())['Démesuré 920']['attrs'], {'line_spacing': 1.5})


if __name__ == '__main__':
    unittest.main()
