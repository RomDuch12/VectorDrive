"""Round 638 : fenêtre « Espace de travail » (FAO ▸ menu, vue 3D) — éléments,
dimensions, position ; étau serrant le brut, le reste de l'espace le
suivant ; prise proposée d'après les parcours ; vérification ; espaces
gardés ; matériel dessiné dans la vue 3D."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from tests.test_round637 import BOX, path, vise
from vectordrive.cam import model
from vectordrive.core import solids as SO
from vectordrive.core import stock3d
from vectordrive.core import workspace as WS

app = QApplication.instance() or QApplication([])


class TestCore(unittest.TestCase):
    def test_edges(self):
        self.assertEqual(len(WS.edges(WS.Element('etau'))), 3 * 12)
        self.assertEqual(len(WS.edges(vise())), 5 * 12)                       # avec ses cales
        self.assertEqual(len(WS.edges(WS.Element('cylindre'))), 2 * WS.SEGMENTS + 4)
        self.assertEqual(len(WS.edges(WS.Element('modele'))), 0)

    def test_fit_to_stock(self):
        ws = WS.Workspace(elements=[WS.Element('table', z=-200), WS.Element('etau', x=100, y=50, z=-150)])
        box = stock3d.StockBox(0, 0, 20, 40, 0, -10)                           # plus long en Y : étau tourné
        out = WS.fit_to_stock(ws, box, 4)
        table, et = out.elements
        self.assertEqual((et.x, et.y, et.rot), (10, 20, 90.0))
        self.assertAlmostEqual(WS.jaw_top(et), -6)
        self.assertAlmostEqual(table.x, 0 + 10 - 100)                           # même déplacement que l'étau…
        self.assertAlmostEqual(table.y, 0 + 20 - 50)
        self.assertEqual(table.rot, 0.0)                                        # … sans tourner (axes machine)
        self.assertAlmostEqual(table.z - et.z, -200 + 150)                      # même écart en Z
        self.assertEqual(ws.elements[1].x, 100)                                 # l'original intact
        self.assertEqual(WS.fit_to_stock(WS.Workspace(elements=[WS.Element('bloc')]), box, 4).elements[0].x, 0)

    def test_auto_grip(self):
        tool = model.CamTool(kind='fraise', diameter=4)
        setup = model.CamSetup(tools=[tool])
        tps = [path([('rapid', 5, 1, 5), ('feed', 5, 1, -4), ('feed', 35, 1, -4)], tool)]
        self.assertEqual(WS.auto_grip(WS.Element('etau'), BOX, tps, setup), (7, []))   # 1 mm sous -4
        self.assertEqual(WS.auto_grip(WS.Element('etau'), BOX, [], setup), (13, []))


class TestDialog(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.workspace_dialog import WorkspaceDialog
        self.old = os.environ.get('VECTORDRIVE_WORKSPACES')
        os.environ['VECTORDRIVE_WORKSPACES'] = tempfile.mkdtemp()
        self.mill = model.CamTool(kind='fraise', diameter=6)
        self.setup = model.CamSetup(tools=[self.mill])
        self.bad = path([('rapid', -10, -5, 5), ('feed', -10, -5, -9), ('feed', 50, -5, -9)], self.mill, 'Détourage')
        self.dlg = WorkspaceDialog(None, WS.Workspace(), BOX, [self.bad], self.setup)

    def tearDown(self):
        if self.old is None:
            os.environ.pop('VECTORDRIVE_WORKSPACES', None)
        else:
            os.environ['VECTORDRIVE_WORKSPACES'] = self.old

    def test_elements_and_clamp(self):
        d = self.dlg
        self.assertIn('Aucun élément', d.info.text())
        e = d.add_element('etau')
        self.assertEqual((e.x, e.y, e.p('opening')), (20, 10, 20))
        self.assertIn('Prise dans le brut : 5 mm', d.info.text())
        self.assertFalse(d.spins[('mandrin', 'clamp')].isVisibleTo(d))
        self.assertTrue(d.spins[('etau', 'jaw_h')].isVisibleTo(d))
        d.grip.setValue(8)
        self.assertTrue(d.clamp())
        self.assertAlmostEqual(WS.jaw_top(d.value().elements[0]), -4)
        d.place['z'].setValue(-200)                                             # mors sous le brut
        self.assertIn('ne le serrent pas', d.info.text())
        t = d.add_element('table')
        self.assertAlmostEqual(t.z, -200 - 40)                                 # sous l'étau
        self.assertEqual(d.list.count(), 2)
        d.duplicate_element()
        self.assertEqual(len(d.value().elements), 3)
        d.remove_element()
        d.list.setCurrentRow(0)
        d.name.setText('Étau Kurt')
        d.store_element()
        self.assertEqual(d.list.item(0).text(), 'Étau Kurt (Étau)')
        self.assertEqual(d.value().elements[0].name, 'Étau Kurt')

    def test_propose_and_check(self):
        d = self.dlg
        d.add_element('etau')
        warn = d.propose_grip()
        self.assertEqual(d.grip.value(), 2)                                     # coupe à -9 contre le mors, 1 mm de garde
        self.assertTrue(warn and 'prise minimale' in warn[0])
        d.grip.setValue(5)
        d.clamp()
        hits = d.check()
        self.assertEqual(len(hits), 1)
        self.assertIn('collision', d.info.text())
        d.visible.setChecked(False)
        self.assertEqual(d.check(), [])
        self.assertIn('Aucun parcours ne touche', d.info.text())
        self.assertIn('masqué', d.list.item(0).text())

    def test_library(self):
        d = self.dlg
        self.assertTrue(d.load_library('Étau de 125 mm'))
        e = d.value().elements[0]
        self.assertAlmostEqual(WS.jaw_top(e), BOX.bottom + 5)                  # serre le brut
        d.add_element('table')
        self.assertEqual(d.save_library('Atelier'), 'Atelier')
        self.assertIn('Atelier', WS.user_workspaces())
        self.assertEqual(d.library.currentData(), 'Atelier')
        self.assertTrue(d.del_btn.isEnabled())
        d.ws.elements = []
        d.fill_list()
        self.assertTrue(d.load_library('Atelier'))
        self.assertEqual([x.kind for x in d.value().elements], ['etau', 'table'])
        self.assertTrue(d.delete_library('Atelier'))
        self.assertNotIn('Atelier', WS.user_workspaces())

    def test_without_stock(self):
        from vectordrive.ui.workspace_dialog import WorkspaceDialog
        d = WorkspaceDialog(None, WS.Workspace(elements=[WS.Element('etau')]), None)
        self.assertIn('non réglé', d.info.text())
        self.assertFalse(d.clamp())
        self.assertFalse(d.check_btn.isEnabled())


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestWindow(unittest.TestCase):
    def test_panel_and_view(self):
        from tests.test_round591 import pocket_stl
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.open_path(pocket_stl())
            w._ensure_panel3d()
            p = w.panel3d
            self.assertTrue(p.refresh())
            cp = w.cam_panel
            cp.set_stock(stock3d.Stock3D('bloc', sx=50, sy=30, sz=14, top=1))
            dlg = cp.workspace_dialog(exec_dialog=False, model=p.view.model)
            self.assertIsNotNone(dlg.box)
            dlg.add_element('etau')
            cp.set_workspace(dlg.value())
            self.assertEqual(w.canvas.doc.extra['workspace']['elements'][0]['kind'], 'etau')
            tri, edge = p.view.fixture
            self.assertIsNotNone(tri)
            top = float(tri[:, 2].max()) - p.view.model_dz
            self.assertAlmostEqual(top, -13 + 5, places=4)                     # bas du brut + prise
            self.assertEqual(len(edge), 2 * 5 * 12)
            again = cp.workspace_dialog(exec_dialog=False, model=p.view.model)
            self.assertEqual(len(again.value().elements), 1)                    # repris du dessin
            cp.set_workspace(WS.Workspace())
            self.assertNotIn('workspace', w.canvas.doc.extra)
            self.assertEqual(p.view.fixture, (None, None))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
