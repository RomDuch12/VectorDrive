"""Round 636 : pièce 3D posée sur n'importe quelle face plane (placement
'n:x,y,z', pas seulement les six faces des axes) pour usiner le dessus —
faces d'appui stables proposées, pièce alignée sur les axes ; vue 3D :
« Poser la pièce sur cette face », « Tourner cette face vers l'outil »."""
import math
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from tests.test_round591 import face_under, pocket_stl
from vectordrive.core import placement3d as P3
from vectordrive.core import solids as SO

app = QApplication.instance() or QApplication([])
SLOPE = (10 / math.hypot(10, 30), 0.0, 30 / math.hypot(10, 30))       # normale sortante du biais du coin


def wedge_stl():
    """Coin 30 × 20 × 10 : pleine hauteur en X 0, nul en X 30 (biais de 632 mm²)."""
    from vectordrive.io import stl_write
    f = pathlib.Path(tempfile.mkdtemp()) / 'coin.stl'
    stl_write.write_stl(str(f), SO.wedge(0, 0, 0, 30, 20, 10).triangles())
    return str(f)


class TestRotations(unittest.TestCase):
    def test_rest_matrix(self):
        rng = np.random.default_rng(3)
        for _ in range(100):
            n = rng.normal(size=3)
            n /= np.linalg.norm(n)
            R = P3.rest_matrix(n)
            self.assertTrue(np.allclose(R @ n, (0, 0, -1), atol=1e-9))
            self.assertTrue(np.allclose(R @ R.T, np.eye(3), atol=1e-9))
            self.assertAlmostEqual(float(np.linalg.det(R)), 1.0, places=9)
        self.assertTrue(np.allclose(P3.rest_matrix((0, 0, 1)) @ (0, 0, 1), (0, 0, -1)))     # retournée

    def test_faces(self):
        for key, R in P3.FACES.items():                  # une normale d'axe : une des six faces
            self.assertEqual(P3.face_for_rest(R.T @ np.array([0, 0, -1.0])), key)
        k = P3.face_for_rest(SLOPE)
        self.assertTrue(k.startswith('n:'))
        self.assertTrue(np.allclose(P3.normal_of(k), SLOPE, atol=1e-6))
        self.assertTrue(np.allclose(P3.Placement(k).rotation() @ SLOPE, (0, 0, -1), atol=1e-6))
        self.assertTrue(np.allclose(P3.face_matrix('n:abc'), np.eye(3)))     # illisible : comme lue
        self.assertEqual(P3.face_for_rest((0.003, 0, -1)), '+Z')             # à 0,2° de l'axe
        self.assertEqual(P3.face_label(k), 'Posée sur une face plane')

    def test_align(self):
        self.assertEqual(P3.align_rot([(0, 0), (10, 10), (9, 11), (-1, 1)]), -45.0)
        self.assertEqual(P3.align_rot([(0, 0), (2, 0), (2, 10), (0, 10)]), 90.0)        # grand côté suivant X
        self.assertEqual(P3.align_rot([(0, 0), (10, 0), (10, 2), (0, 2)]), 0.0)


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestRestFaces(unittest.TestCase):
    def test_wedge(self):
        from vectordrive.io import model3d
        m = model3d.load(wedge_stl())
        faces = P3.rest_faces(m)
        self.assertEqual(len(faces), 5)
        key, area, _f = faces[0]
        self.assertTrue(np.allclose(P3.normal_of(key), SLOPE, atol=1e-5))
        self.assertAlmostEqual(area, 20 * math.hypot(10, 30), places=3)
        self.assertEqual([f[0] for f in faces[1:3]], ['+Z', '+X'])           # dessous 600, dos 200
        self.assertEqual(sorted(f[0] for f in faces[3:]), ['+Y', '-Y'])
        placed = model3d.placed(m, P3.Placement(key))
        t = placed.triangles[np.asarray(m.face_ids()) == faces[0][2]]
        self.assertLess(float(np.ptp(t[:, :, 2])), 1e-4)                    # le biais à plat…
        self.assertAlmostEqual(float(t[:, :, 2].min()), placed.bounds()[2], places=4)   # … en bas

    def test_concave_floor_is_no_support(self):
        from vectordrive.io import model3d
        faces = P3.rest_faces(model3d.load(pocket_stl()))
        self.assertEqual(sorted(f[0] for f in faces), sorted(P3.FACES))     # le fond de la poche n'en est pas une
        self.assertEqual(faces[0][0], '+Z')
        self.assertAlmostEqual(faces[0][1], 800.0, places=3)


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestUi(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.w.open_path(wedge_stl())
        self.w._ensure_panel3d()
        self.p = self.w.panel3d
        self.assertTrue(self.p.refresh())

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def slope_triangles(self, m, fid):
        return m.triangles[np.asarray(m.face_ids()) == fid]

    def test_rest_and_up(self):
        p = self.p
        fid = face_under(p.view.model, 10, 10)
        p.view.set_selection(faces=[fid])
        pl = p.rest_on_selection()
        self.assertTrue(pl.face.startswith('n:'))
        self.assertEqual(pl.rot, 0.0)                                        # déjà aligné sur X
        self.assertEqual(self.w.canvas.doc.extra['placement3d']['face'], pl.face)
        p.refresh()
        t = self.slope_triangles(p.view.model, fid)
        self.assertAlmostEqual(float(t[:, :, 2].max()), p.view.model.bounds()[2], places=3)   # posée dessus
        self.w.place_model3d(placement=P3.Placement())
        p.refresh()
        p.view.set_selection(faces=[fid])
        pl = p.rest_on_selection(up=True)
        self.assertTrue(np.allclose(P3.normal_of(pl.face), [-c for c in SLOPE], atol=1e-5))
        p.refresh()
        t = self.slope_triangles(p.view.model, fid)
        self.assertAlmostEqual(float(t[:, :, 2].min()), p.view.model.bounds()[5], places=3)   # vers l'outil
        p.view.set_selection(faces=[])
        self.assertIsNone(p.rest_on_selection())

    def test_dialog_proposes_slope(self):
        dlg = self.w.place_model3d(exec_dialog=False)
        combo = dlg.fields['face']
        texts = [combo.itemText(i) for i in range(combo.count())]
        self.assertTrue(any(t.startswith('Posée sur une face plane de 632') for t in texts), texts)
        self.assertEqual(combo.count(), 7)                                   # six faces + le biais


if __name__ == '__main__':
    unittest.main()
