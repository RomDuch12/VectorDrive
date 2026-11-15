"""Round 654 : vue 3D par prise — les trajectoires d'une surface posée en 2D
montrées sur sa prise seulement (et sa prise dans la liste), celles du
dessin plus dessinées sur la pièce tournée autrement."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from tests.test_round596 import two_boxes_stl
from tests.test_round649 import rect
from tests.test_round653 import faces
from vectordrive.cam import model
from vectordrive.core import surface2d as S2

app = QApplication.instance() or QApplication([])


@unittest.skipUnless(__import__('vectordrive.core.solids', fromlist=['x']).available(), 'manifold3d absent')
class TestSetupView(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.open_path(two_boxes_stl())
        self.w._ensure_panel3d()
        self.p = self.w.panel3d
        self.assertTrue(self.p.refresh())

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_surface_paths_on_their_setup(self):
        w, p, cp = self.w, self.p, self.w.cam_panel
        doc = w.canvas.doc
        path = p.machining_path()
        ground = doc.layers[0]
        mark = rect(1, 1, 5, 3, tool=ground.tool)
        ground.items.append(mark)
        L = S2.add_layer(doc, S2.pose(doc, path, [faces(path)['x20']]))
        engr = rect(2, 2, 2, 1, tool=L.tool)
        L.items.append(engr)
        s = cp.setup()
        t = model.CamTool(kind='fraise', diameter=1.0, name='F1', number=1, spindle=10000)
        s.tools.append(t)
        top = model.Operation(kind='gravure', name='Dessus', tool_id=t.id, items=[mark.id], depth=0.2)
        side = model.Operation(kind='gravure', name='Côté', tool_id=t.id, items=[engr.id], depth=0.2)
        s.operations = [top, side]
        cp.save(s)
        self.assertEqual(cp.setup().operations[1].setup_face, '+X')          # rattachée à la surface
        tps = cp.compute()
        self.assertEqual(len([tp for tp in tps if tp.moves]), 2)
        self.assertTrue(p.refresh())
        self.assertIn(('+X', -1), p.setup_groups())                           # sa prise dans la liste
        by_id = {o.id: o.name for o in cp.setup().operations}
        shown = lambda: sorted(by_id.get(tp.op_id) for tp in p.view.model_paths)   # noqa: E731
        p.setup_view.setCurrentIndex(p.setup_view.findData('+X|-1'))
        p.refresh()
        self.assertEqual(shown(), ['Côté'])
        p.setup_view.setCurrentIndex(p.setup_view.findData('|-1'))
        p.refresh()
        self.assertEqual(shown(), ['Dessus'])                                 # le côté n'est pas sur le dessus


if __name__ == '__main__':
    unittest.main()
