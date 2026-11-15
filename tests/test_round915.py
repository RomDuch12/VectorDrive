"""Round 915 : l'outil d'un programme lu — un outil de même nom mais d'une autre référence est un autre outil, dans les
bibliothèques comme dans le document (le programme le propose alors à la création) ; un outil sans référence se
reconnaît toujours à son nom ; références multiples (« A / B ») comparées une à une."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'r915.ini'))
os.environ.setdefault('VECTORDRIVE_SESSION', tempfile.mkdtemp())
os.environ['VECTORDRIVE_NO_TYPEEDIT'] = '1'

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from vectordrive.cam import model as M  # noqa: E402
from vectordrive.cam import ncread  # noqa: E402


def tool(name='Fr2_Z2_Lg6 915', ref='915111'):
    return M.CamTool(name=name, kind='fraise', diameter=2.0, ref=ref, number=3)


class Libraries(unittest.TestCase):

    def test_same_name_other_ref_is_another_tool(self):
        t = tool()
        info = {'ref': '915222', 'name': 'Fr2_Z2_Lg6 915'}
        self.assertEqual(ncread.match_tool(info, '', [('Atelier', [t])]), (None, ''))
        bare = tool(ref='')                                                  # sans référence : son nom suffit
        self.assertEqual(ncread.match_tool(info, '', [('Atelier', [t, bare])]), (bare, 'Atelier'))
        self.assertEqual(ncread.match_tool({'name': 'Fr2_Z2_Lg6 915'}, '', [('Atelier', [t])]), (t, 'Atelier'))

    def test_name_in_the_label_with_another_ref(self):
        t = tool()
        self.assertEqual(ncread.match_tool({'ref': '915222'}, 'Op_1 — Fr2_Z2_Lg6 915', [('Atelier', [t])]),
                         (None, ''))
        self.assertEqual(ncread.match_tool({}, 'Op_1 — Fr2_Z2_Lg6 915', [('Atelier', [t])]), (None, ''))   # 917

    def test_several_refs_compared_one_by_one(self):
        t = tool(ref='0915283Q / 114915')
        self.assertTrue(ncread.same_identity(t, {'ref': '114915'}))
        self.assertTrue(ncread.same_identity(t, {'ref': 'AUTRE915 / 114915'}))
        self.assertFalse(ncread.same_identity(t, {'ref': 'AUTRE915 / 999915'}))
        self.assertTrue(ncread.other_ref(t, '999915'))
        self.assertFalse(ncread.other_ref(t, ''))
        self.assertFalse(ncread.other_ref(tool(ref=''), '999915'))


class Document(unittest.TestCase):

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

    def read_part(self, info):
        tp = M.Toolpath(op_id='', tool_id='', name='essai 915', source='nc')
        tp.tool_info = dict(info)
        tp.tool_guess, tp.tool_source = ncread.proposal(tp.tool_info, tp.name), ''
        return tp

    def with_document_tools(self, *tools):
        s = self.cp.setup()
        s.tools = list(tools)
        self.cp.save(s)

    def test_document_tool_of_the_same_name_but_another_ref_is_not_taken(self):
        mine = tool(name='ESSAI915 D2', ref='915AAA')
        self.with_document_tools(mine)
        tp = self.read_part({'name': 'ESSAI915 D2', 'ref': '915BBB', 'number': 3})
        with mock.patch.object(self.cp, 'ask_program_tool', return_value='keep') as ask:
            got, new = self.cp.program_tool(tp)
        ask.assert_called_once()                                             # inconnu : proposé à la création
        self.assertTrue(new)
        self.assertNotEqual(got.id, mine.id)
        self.assertEqual((got.ref, got.name), ('915BBB', 'ESSAI915 D2'))
        self.assertNotEqual(got.number, mine.number)                         # numéro libre dans le document

    def test_document_tool_with_one_of_the_refs_or_without_ref_is_kept(self):
        for mine in (tool(name='Autre nom 915', ref='915BBB'), tool(name='ESSAI915 D2', ref='')):
            with self.subTest(ref=mine.ref):
                self.with_document_tools(mine)
                tp = self.read_part({'name': 'ESSAI915 D2', 'ref': 'AUTRE915 / 915BBB'})
                with mock.patch.object(self.cp, 'ask_program_tool') as ask:
                    got, new = self.cp.program_tool(tp)
                ask.assert_not_called()
                self.assertEqual(got.id, mine.id)
                self.assertFalse(new)


if __name__ == '__main__':
    unittest.main()
