"""Round 639 : automatisme 3D et espace de travail — la première prise ne
descend pas à moins d'1 mm du haut des mors de l'étau (les autres prises :
pièce retournée, sans limite) ; « Espace de travail… » et « Rester au-dessus
des mors » dans sa fenêtre ; modèle STEP / STL ajouté par le choix du fichier."""
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from tests.test_round637 import BOX, vise
from vectordrive.cam import auto3d as A
from vectordrive.cam import model
from vectordrive.core import solids as SO
from vectordrive.core import stock3d
from vectordrive.core import workspace as WS

app = QApplication.instance() or QApplication([])


class TestFloor(unittest.TestCase):
    def test_jaw_floor(self):
        floor, el = WS.jaw_floor(WS.Workspace(elements=[WS.Element('table'), vise()]))
        self.assertEqual((floor, el.kind), (6, 'etau'))                         # mors à -7, 1 mm de garde
        self.assertEqual(WS.jaw_floor(WS.Workspace(elements=[WS.Element('table')])), (0.0, None))
        high = WS.clamp_stock(WS.Element('etau'), stock3d.StockBox(0, 0, 40, 20, 0, -3), 5)   # mors à +2
        self.assertEqual(WS.jaw_floor(WS.Workspace(elements=[high])), (0.0, None))

    def test_plan(self):
        tools = [model.CamTool(kind='fraise', diameter=6, cut_length=30)]
        seq = A.Sequence(steps=[A.Step(kind='ebauche3d', tool_kind='fraise', rule='gros'),
                                A.Step(kind='surface3d', tool_kind='fraise', rule='gros')])
        info = A.PartInfo(40, 20, 10, 0, 20, floor=6.0)
        out = A.plan(seq, tools, [], info)
        self.assertEqual([(p.op.depth, p.jaws) for p in out], [(6.0, 6.0), (6.0, 6.0)])
        info.floor = 0.0
        self.assertEqual([p.jaws for p in A.plan(seq, tools, [], info)], [0.0, 0.0])
        info.floor = 12.0
        self.assertEqual([p.jaws for p in A.plan(seq, tools, [], info)], [0.0, 0.0])   # pièce au-dessus des mors
        info.floor = 6.0
        both = A.plan_all(seq, tools, [], {-1: info}, groups=[(-1, ['', '-Z'])])
        ops = [p for p in both if p.tool is not None]
        self.assertEqual([(p.op.setup_face, p.jaws) for p in ops], [('', 6.0), ('', 6.0), ('-Z', 0.0), ('-Z', 0.0)])
        self.assertEqual(info.floor, 6.0)                                       # l'original intact


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestDialogs(unittest.TestCase):
    def setUp(self):
        from tests.test_round591 import pocket_stl
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.open_path(pocket_stl())
        self.w._ensure_panel3d()
        self.p = self.w.panel3d
        self.assertTrue(self.p.refresh())
        self.cp = self.w.cam_panel
        self.cp.set_stock(stock3d.Stock3D('bloc', sx=50, sy=30, sz=14, top=1))   # bas du brut à -13

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_auto3d(self):
        a3 = self.p.auto3d(exec_dialog=False, sequence='Ébauche, demi-finition, finition')
        self.assertIn('aucun', a3.ws_text.text())
        self.assertFalse(a3.jaws_box.isVisibleTo(a3))
        self.assertFalse([p for p in a3.planned if p.jaws])
        d = self.cp.workspace_dialog(exec_dialog=False, model=self.p.view.model)
        d.add_element('etau')                                                   # prise 5 : mors à -8
        self.cp.set_workspace(d.value())
        a3 = self.p.auto3d(exec_dialog=False, sequence='Ébauche, demi-finition, finition')
        self.assertIn('jusqu\'à 7 mm', a3.ws_text.text())
        self.assertTrue(a3.jaws_box.isVisibleTo(a3))
        jaws = [p for p in a3.planned if p.jaws]
        self.assertTrue(jaws)
        self.assertTrue(all(p.op.depth <= 7 + 1e-9 for p in a3.planned if p.tool is not None))
        self.assertIn('au-dessus des mors', a3.summary.text())
        a3.jaws_box.setChecked(False)
        self.assertFalse([p for p in a3.planned if p.jaws])
        self.assertEqual(a3.info.floor, 0.0)

    def test_add_model(self):
        from vectordrive.io import stl_write
        f = pathlib.Path(tempfile.mkdtemp()) / 'Etau Kurt.stl'
        stl_write.write_stl(str(f), WS._box_tris(0, 0, 50, 20, 0, 0, 30))
        d = self.cp.workspace_dialog(exec_dialog=False, model=self.p.view.model)
        with mock.patch('vectordrive.ui.workspace_dialog.QFileDialog.getOpenFileName', return_value=(str(f), '')):
            e = d.add_model()
        self.assertEqual((e.kind, e.name, e.path), ('modele', 'Etau Kurt', str(f)))
        self.assertAlmostEqual(e.z, -13 - 30, places=4)                        # posé sous le brut
        with mock.patch('vectordrive.ui.workspace_dialog.QFileDialog.getOpenFileName', return_value=('', '')):
            self.assertIsNone(d.add_model())
        self.assertEqual(len(d.value().elements), 1)


if __name__ == '__main__':
    unittest.main()
