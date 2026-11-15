"""Round 917 : l'outil d'un programme lu, jamais un autre — un outil dont le nom est seulement contenu dans celui du
programme, ou dont la référence est dans le nom du fichier, n'est pas pris ; une référence écrite en mot entier dans le
commentaire l'est ; la broche est celle de chaque passage d'outil (S modale) ; un cône à pointe entière (« 90__1 ») est
un cône ; un outil proposé ne prend ni le nom ni les cotes du fichier ; la liste des outils triée garde le même outil
choisi après une mise à jour (« − » ne supprime plus un autre outil)."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r917.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from vectordrive.cam import model as M  # noqa: E402
from vectordrive.cam import ncread  # noqa: E402

PASSES = """%
T1 M6 (A917)
S20000 M3
G0 X0 Y0 Z5
G1 Z-0.2 F300
G1 X10 F900
G0 Z5
T2 M6 (B917)
S15000 M3
G0 X20 Y0
G1 Z-0.2 F300
G1 X30 F900
G0 Z5
T3 M6 (C917)
G0 X40 Y0
G1 Z-0.2 F300
G1 X50 F900
G0 Z5
T1 M6 (A917)
S9000 M3
G0 X60 Y0
G1 Z-0.2 F300
G1 X70 F900
G0 Z5
M30
"""


def read(text, name='p917.nc', libs=()):
    with mock.patch.object(ncread, 'libraries', return_value=list(libs)):
        return ncread.read(text, name)


class Matching(unittest.TestCase):

    def test_a_name_only_contained_in_the_program_name_is_not_the_tool(self):
        mine = M.CamTool(name='Fraise D2', diameter=2.0)
        libs = [('Mes outils', [mine])]
        self.assertEqual(ncread.match_tool({'name': 'FRAISE D2 L10', 'number': 3}, 'p.nc — T3 FRAISE D2 L10', libs),
                         (None, ''))
        self.assertEqual(ncread.match_tool({'name': 'Fraise D2 longue', 'ref': 'ZZZ917'}, '', libs), (None, ''))
        tp = read('%\nT3 M6 (FRAISE D2 L10)\nS18000 M3\nG0 X0 Y0 Z5\nG1 Z-0.2 F300\nG1 X5 F900\nM30\n', libs=libs)
        self.assertEqual(tp.tool_source, '')                                 # inconnu : proposé à la création
        self.assertEqual((tp.tool_guess.name, tp.tool_guess.spindle), ('FRAISE D2 L10', 18000.0))
        self.assertEqual(ncread.match_tool({'name': 'fraise d2'}, '', libs), (mine, 'Mes outils'))   # le même nom

    def test_the_file_name_never_tells_the_tool(self):
        mine = M.CamTool(name='Cône 917', kind='conique', angle=30.0, tip=0.2, ref='12345')
        libs = [('Mes outils', [mine])]
        self.assertEqual(ncread.match_tool({'number': 1}, 'Commande_123456.nc T1', libs), (None, ''))
        tp = read('%\nT1 M6\nG0 X0 Y0 Z5\nG1 Z-0.2 F300\nG1 X5 F900\nM30\n', 'Commande_12345 D300.nc', libs)
        self.assertEqual(tp.tool_source, '')
        self.assertEqual(tp.tool_guess.name, 'T1')                           # pas le nom du fichier
        self.assertNotEqual(tp.tool_guess.diameter, 300.0)                   # ni ses cotes

    def test_a_reference_in_the_comment(self):
        mine = M.CamTool(name='Cône 30 917', kind='conique', angle=30.0, tip=0.6, ref='0917283Q / 114917')
        libs = [('Atelier', [mine])]
        for comment in ('0917283Q', 'CONE 0917283Q 30', '114917'):
            with self.subTest(comment=comment):
                self.assertEqual(ncread.match_tool({'name': comment}, '', libs), (mine, 'Atelier'))
        self.assertEqual(ncread.match_tool({'name': 'X0917283QB'}, '', libs), (None, ''))   # pas un mot entier
        self.assertEqual(ncread.match_tool({'name': '1149170'}, '', libs), (None, ''))


class Values(unittest.TestCase):

    def test_spindle_of_each_pass(self):
        tp = read(PASSES)
        self.assertEqual([p.tool_info.get('spindle') for p in tp.parts], [20000.0, 15000.0, 15000.0, 9000.0])
        self.assertEqual(tp.parts[3].tool_guess.spindle, 9000.0)             # T1 repris à 9000 tr/min

    def test_cone_with_a_whole_tip(self):
        self.assertEqual(ncread.cotes_of_name('2_Fr_90__1'), {'number': 2, 'kind': 'conique', 'angle': 90.0,
                                                              'tip': 1.0})
        self.assertEqual(ncread.cotes_of_name('5_Fr_60__0_Z1'), {'number': 5, 'kind': 'conique', 'angle': 60.0,
                                                                 'tip': 0.0, 'flutes': 1})
        self.assertEqual(ncread.cotes_of_name('1_Fr_30__0_6'), {'number': 1, 'kind': 'conique', 'angle': 30.0,
                                                                'tip': 0.6})
        t = ncread.proposal({'name': '2_Fr_90__1'})
        self.assertEqual((t.kind, t.angle, t.tip), ('conique', 90.0, 1.0))
        self.assertLess(t.diameter, 10.0)

    def test_proposal_without_name(self):
        t = ncread.proposal({'number': 4, 'feed': 900.0}, 'Plaque_D300.nc — T4')
        self.assertEqual((t.name, t.number, t.feed), ('T4', 4, 900.0))
        self.assertNotEqual(t.diameter, 300.0)


class SortedTable(unittest.TestCase):

    def setUp(self):
        self.tools_file = os.path.join(tempfile.mkdtemp(), 'tools.json')
        self.env = mock.patch.dict(os.environ, {'VECTORDRIVE_TOOLS': self.tools_file})
        self.env.start()
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.cp = self.w.cam_panel
        self.w.settings.remove(self.cp.TOOLS_SORT_KEY)
        s = self.cp.setup()
        s.tools = [M.CamTool(name=n, number=k + 1, diameter=1.0 + k) for k, n in enumerate(('Zeta', 'Alpha', 'Mid'))]
        s.operations = []
        self.cp.save(s)

    def tearDown(self):
        self.w.settings.remove(self.cp.TOOLS_SORT_KEY)
        self.w.modified = False
        self.w.close()
        self.env.stop()

    def select(self, name):
        r = next(r for r in range(self.cp.tools.rowCount()) if self.cp.tools.item(r, 1).text() == name)
        self.cp._select_row(self.cp.tools, r)

    def test_the_same_tool_stays_chosen_after_a_refresh(self):
        self.cp.tools.horizontalHeader().setSortIndicator(1, Qt.SortOrder.AscendingOrder)
        self.select('Alpha')
        self.cp.refresh()                                                   # après ✎ ou un autre changement
        self.assertEqual(self.cp.setup().tools[self.cp.tool_row_index()].name, 'Alpha')
        self.cp.remove_tool()
        self.assertEqual(sorted(t.name for t in self.cp.setup().tools), ['Mid', 'Zeta'])     # Alpha, pas Zeta
        self.assertEqual(self.cp.tool_row_index(), -1)                      # retiré : rien de choisi


if __name__ == '__main__':
    unittest.main()
