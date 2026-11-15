"""Round 651 : un corps de la pièce positionné à part de l'ensemble pour son
usinage (pièce d'un moule tenue seule) — sa face vers l'outil, sa rotation,
sa position ; ses usinages dans cette pose, leurs trajectoires ramenées sur
l'ensemble ; prise de la vue 3D, surface 2D du corps."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from tests.test_round596 import FakeDoc, two_boxes_stl
from tests.test_round644 import verts
from tests.test_round649 import face_with
from vectordrive.cam import mill3d, model
from vectordrive.cam import reassemble as RA
from vectordrive.core import placement3d as P3
from vectordrive.core import surface2d as S2
from vectordrive.core import workspace as WS
from vectordrive.core.document import Plate

app = QApplication.instance() or QApplication([])


def plate():
    return Plate(x=0, y=0, width=100, height=100)


def end_face(path):
    """Bout +X du second bloc (X 50)."""
    return face_with(mill3d.raw_model(path), (1, 0, 0), lambda c: np.abs(c[:, 0] - 50) < 1e-6)


class TestPlacement(unittest.TestCase):
    def setUp(self):
        self.path = two_boxes_stl()
        self.doc = FakeDoc(self.path, P3.Placement('+Z', 0.0, 'centre'), plate())

    def test_store(self):
        doc = self.doc
        self.assertIsNone(P3.body_of(doc, 1))
        P3.set_body(doc, 1, P3.Placement('+X', 90.0, 'origine'))
        self.assertEqual(P3.body_of(doc, 1), P3.Placement('+X', 90.0, 'origine'))
        self.assertIsNone(P3.body_of(doc, 0))
        self.assertIsNone(P3.body_of(doc, -1))
        P3.set_body(doc, 1, None)
        self.assertNotIn(P3.KEY_BODIES, doc.extra)
        doc.extra[P3.KEY_BODIES] = {'1': 'x', '0': {'face': '-Z', 'inconnu': 1}}
        self.assertIsNone(P3.body_of(doc, 1))                               # illisible : comme l'ensemble
        self.assertEqual(P3.body_of(doc, 0).face, '-Z')

    def test_side_placement(self):
        doc, f = self.doc, self.path
        P3.set_body(doc, 1, P3.Placement('+X', 90.0, 'centre'))
        p = mill3d.side_placement(doc, f, '', 1)
        self.assertEqual((p.face, p.rot), ('+X', 90.0))
        x0, y0, z0, x1, y1, z1 = mill3d.load_model(doc, f, '', 1).bounds()
        self.assertAlmostEqual(z1 - z0, 10.0, 5)                            # couché sur son bout
        self.assertAlmostEqual((x0 + x1) / 2, 50.0, 5)                      # centré sur la plaque
        self.assertAlmostEqual((y0 + y1) / 2, 50.0, 5)
        p = mill3d.side_placement(doc, f, '-Z', 1)
        self.assertEqual((p.face, p.rot), ('-Z', 90.0))                     # autre prise : sa rotation gardée
        self.assertEqual(mill3d.side_placement(doc, f, '', 0).face, '+Z')   # l'autre corps : comme l'ensemble
        P3.set_body(doc, 1, P3.Placement('-Z', 0.0, 'libre', 7.0, 8.0))
        p = mill3d.side_placement(doc, f, '', 1)
        self.assertEqual((p.face, p.dx, p.dy), ('-Z', 7.0, 8.0))           # position libre : telle quelle

    def test_setup_of_body(self):
        doc, f = self.doc, self.path
        P3.set_body(doc, 1, P3.Placement('+X', 0.0, 'centre'))
        self.assertEqual(WS.drawing_face(doc, f, 1), '+X')
        self.assertEqual(WS.drawing_face(doc, f, 0), '+Z')
        self.assertEqual(WS.norm_face(doc, '+X', f, 1), '')                 # sa pose : « dessus » du corps
        self.assertEqual(WS.norm_face(doc, '+Z', f, 1), '+Z')
        op = model.Operation(kind='surface3d', setup_face='+X', body3d=1, model_path=f)
        self.assertEqual(WS.op_setup(op, doc), ('', 1))
        op = model.Operation(kind='surface3d', setup_face='+X', body3d=0, model_path=f)
        self.assertEqual(WS.op_setup(op, doc), ('+X', 0))

    def test_back_on_assembly(self):
        doc, f = self.doc, self.path
        P3.set_body(doc, 1, P3.Placement('+X', 90.0, 'coin'))
        ref = verts(doc, f, '', -1).reshape(-1, 3, 3)[mill3d.raw_model(f).body_ids() == 1].reshape(-1, 3)
        for face in ('', '-Z', '+Y'):
            op = model.Operation(kind='surface3d', setup_face=face, body3d=1, model_path=f)
            A, b = RA.transform(doc, op)
            np.testing.assert_allclose(verts(doc, f, face, 1) @ A.T + b, ref, atol=1e-4)

    def test_workspace(self):
        doc, f = self.doc, self.path
        doc.extra[WS.KEY] = WS.Workspace(elements=[WS.Element('etau')]).to_dict()
        self.assertEqual(len(WS.of(doc, '', 0).elements), 1)               # corps seul, posé comme l'ensemble
        P3.set_body(doc, 0, P3.Placement('+Z', 0.0, 'centre'))
        self.assertEqual(WS.of(doc, '', 0).elements, [])                    # tenu ailleurs : pas dans cet étau
        WS.store(doc, WS.Workspace(elements=[WS.Element('mandrin')]), '+Z', 0)
        self.assertEqual([e.kind for e in WS.of(doc, '', 0).elements], ['mandrin'])

    def test_surface(self):
        from vectordrive.core.document import Document
        f = self.path
        doc = Document()
        doc.source_path, doc.extra, doc.plate = f, dict(self.doc.extra), plate()
        P3.set_body(doc, 1, P3.Placement('+X', 0.0, 'centre'))
        info = S2.pose(doc, f, [end_face(f)], 1)
        self.assertEqual((info['face'], info['body']), ('+X', 1))
        self.assertAlmostEqual(info['z'], 0.0, 6)                           # le bout en haut
        L = S2.add_layer(doc, info)
        self.assertEqual(S2.layer_key(doc, L), ('', 1))


@unittest.skipUnless(__import__('vectordrive.core.solids', fromlist=['x']).available(), 'manifold3d absent')
class TestWindow(unittest.TestCase):
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

    def test_place_body(self):
        w, p = self.w, self.p
        doc = w.canvas.doc
        path = p.machining_path()
        p.view.sel_faces = {end_face(path)}
        self.assertEqual(p.selected_body(), 1)
        p._fill_use_menu()
        act = next(a for a in p.use_menu.actions() if a.text().startswith('Positionner ce corps à part'))
        self.assertTrue(act.isEnabled())
        dlg = p.place_body(exec_dialog=False)
        self.assertEqual(dlg.fields['face'].currentData(), P3.of(doc).face)  # par défaut : la face de l'ensemble
        dlg.deleteLater()
        n_undo = len(w._undo)
        p.place_body(placement=P3.Placement('+X', 0.0, 'centre'))
        self.assertEqual(len(w._undo), n_undo + 1)
        self.assertEqual(P3.body_of(doc, 1).face, '+X')
        self.assertEqual(p.current_setup(), ('', 1))                        # le corps montré dans sa pose
        x0, _y0, z0, x1, _y1, z1 = p.view.model.bounds()
        self.assertAlmostEqual(z1 - z0, 10.0, 4)
        p.view.sel_faces = {end_face(path)}
        self.assertEqual(p.selected_body(), 1)                              # montré seul : ce corps
        L = p.surface_to_layer()
        self.assertEqual(S2.layer_key(doc, L), ('', 1))
        w.undo()
        w.undo()
        self.assertIsNone(P3.body_of(doc, 1))
        p.place_body(1, placement=P3.Placement('-Z', 0.0, 'centre'))
        self.assertIsNotNone(p.place_body(1, placement=P3.Placement('-Z', 45.0, 'centre')))
        self.assertIsNone(p.place_body(1, reset=True))
        self.assertIsNone(P3.body_of(doc, 1))

    def test_no_body(self):
        p = self.p
        p.view.sel_faces = set()
        self.assertIsNone(p.selected_body())
        self.assertIsNone(p.place_body())
        p.view.sel_faces = {end_face(p.machining_path()), 0}
        if len({int(b) for b in np.asarray(p.view.model.body_ids())[p.view.selected_triangles()]}) > 1:
            self.assertIsNone(p.selected_body())                            # faces de deux corps


if __name__ == '__main__':
    unittest.main()
