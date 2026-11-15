"""Round 921 : l'outil proposé garde le nom entier du programme — deux noms longs qui ne diffèrent qu'à la fin sont
deux outils, et l'outil créé se retrouve dans Mes outils ; la règle de variante ne vaut que pour une référence qui
finit par un chiffre, suivie de « -2 » / « _2 » en fin de mot."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r921.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from vectordrive.cam import model as M  # noqa: E402
from vectordrive.cam import ncread  # noqa: E402

LONG = 'FRAISE CARBURE 2 DENTS REVETUE POUR ALUMINIUM ET LAITON ESSAI 921 DIAMETRE '


class LongNames(unittest.TestCase):

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

    def part(self, name, spindle):
        tp = M.Toolpath(op_id='', tool_id='', name='essai 921', source='nc')
        tp.tool_info = {'name': name, 'number': 3, 'spindle': spindle}
        tp.tool_guess, tp.tool_source = ncread.proposal(tp.tool_info, tp.name), ''
        return tp

    def test_two_long_names_are_two_tools(self):
        a, b = LONG + '2', LONG + '3'
        self.assertGreater(len(a), 60)
        with mock.patch.object(self.cp, 'ask_program_tool', return_value='keep') as ask:
            got_a, _new = self.cp.program_tool(self.part(a, 18000.0))
            s = self.cp.setup()
            s.tools.append(got_a)
            self.cp.save(s)
            got_b, new_b = self.cp.program_tool(self.part(b, 9000.0))
            again, new_a = self.cp.program_tool(self.part(a, 18000.0))
        self.assertEqual(ask.call_count, 2)                              # B proposé, A retrouvé
        self.assertTrue(new_b)
        self.assertNotEqual(got_b.id, got_a.id)
        self.assertEqual(got_b.spindle, 9000.0)
        self.assertEqual((again.id, new_a), (got_a.id, False))

    def test_created_tool_found_in_my_tools(self):
        created = ncread.proposal({'name': LONG + '2', 'spindle': 18000.0})
        self.assertEqual(created.name, LONG + '2')
        self.assertEqual(ncread.match_tool({'name': LONG + '2'}, '', [('Mes outils', [created])]),
                         (created, 'Mes outils'))
        self.assertEqual(ncread.match_tool({'name': LONG + '3'}, '', [('Mes outils', [created])]), (None, ''))


class VariantRule(unittest.TestCase):

    def test_only_digit_refs_and_short_suffixes(self):
        cone = M.CamTool(name='Cône 921', kind='conique', angle=30.0, tip=0.2, ref='0921283Q / 921917')
        mill = M.CamTool(name='Fraise 921', kind='fraise', diameter=2.0, ref='0921443G')
        libs = [('Atelier', [cone, mill])]
        for comment, want in (('0921283Q_30__0_2', cone), ('921917_30__0_2', cone), ('0921283Q-30-0.2', cone),
                              ('CONE-0921283Q-30DEG', cone), ('0921443G_3', mill), ('0921443G_2_DENTS', mill),
                              ('FR2-0921443G-2D', mill), ('921917_300', cone)):
            with self.subTest(comment=comment):
                self.assertEqual(ncread.match_tool({'name': comment}, '', libs), (want, 'Atelier'))
        for comment in ('FRAISE 921917-2', 'FRAISE 921917_2', '921917_12 L4', '921917.5', '921917,5'):
            with self.subTest(comment=comment):                          # variante ou décimal : pas cet outil
                self.assertEqual(ncread.match_tool({'name': comment}, '', libs), (None, ''))


if __name__ == '__main__':
    unittest.main()
