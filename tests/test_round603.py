"""Round 603 : un corps maillé face par face (STEP) devient un volume du dessin — sommets du bord repris
exactement des arêtes partagées, jonctions en T coupées, petits trous bouchés, triangles orientés ; puis
modifié et usiné comme les autres volumes. Ce qui ne ferme pas est signalé, corps par corps."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from tests.test_round595 import box_tris
from vectordrive.core import solids as SO
from vectordrive.core import watertight as WT
from vectordrive.io import model3d

app = QApplication.instance() or QApplication([])


def cracked_box():
    """Pavé 10 × 10 × 10 maillé comme un STEP : le dessus coupé en deux faces par un point au milieu
    d'une arête que la face voisine ne connaît pas (jonction en T), un triangle retourné."""
    t = box_tris(0, 0, 0, 10, 10, 10)
    top = [i for i in range(len(t)) if np.allclose(t[i][:, 2], 10)]
    rest = [t[i] for i in range(len(t)) if i not in top]
    m = (5.0, 0.0, 10.0)                                   # sur l'arête y = 0 du dessus
    new_top = [[(0, 0, 10), m, (0, 10, 10)], [m, (10, 10, 10), (0, 10, 10)], [m, (10, 0, 10), (10, 10, 10)]]
    tris = np.array(rest + [np.array(x, dtype=float) for x in new_top])
    tris[0] = tris[0][::-1]                                # sens d'un triangle inversé
    return tris


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestRepair(unittest.TestCase):
    def test_closed_box(self):
        s = WT.to_solid(box_tris(0, 0, 0, 10, 20, 5))
        self.assertAlmostEqual(s.volume(), 1000.0, 6)

    def test_t_junction_and_orientation(self):
        tris = cracked_box()
        v, idx, rep = WT.repair(tris, 0.01)
        self.assertEqual((rep['bords'], rep['mauvaises']), (0, 0))
        self.assertGreater(rep['jonctions'], 0)
        self.assertAlmostEqual(WT.to_solid(tris).volume(), 1000.0, 6)

    def test_small_hole(self):
        holed = box_tris(0, 0, 0, 10, 10, 10)[1:]             # un triangle manquant : un trou triangulaire
        _v, _i, rep = WT.repair(holed, 0.01)
        self.assertEqual(rep['trous'], 1)
        self.assertAlmostEqual(WT.to_solid(holed).volume(), 1000.0, 6)   # bouché dans son plan

    def test_open_fails(self):
        t = box_tris(0, 0, 0, 10, 10, 10)[:6]                  # la moitié d'un pavé
        with mock.patch.object(WT, 'fill_holes', lambda v, idx, max_perimeter=50.0: (v, idx, 0)):
            with self.assertRaises(SO.SolidError):
                WT.to_solid(t)

    def test_mesher_keeps_edge_points(self):
        from vectordrive.io.neostep import step3d

        class Plan:                                            # surface d'essai : (u, v) ↔ point, aller-retour faux
            periode_u = 0.0

            def uv(self, pts):
                return np.asarray(pts, dtype=float)[:, :2]

            def point(self, UV):
                UV = np.asarray(UV, dtype=float)
                return np.c_[UV, np.full(len(UV), 1e-3)]       # 1 µm à côté : l'aller-retour décale
        pts = np.array([[0, 0, 0.0], [1, 0, 0.0], [1, 1, 0.0]])
        out = step3d._sur_le_bord(Plan(), [(pts, True)],
                                  np.array([[0, 0], [1, 1], [0.75, 0.25], [0.5, 0.5]], dtype=float))
        self.assertEqual(out[0].tolist(), [0, 0, 0])                # point du bord : exact
        self.assertEqual(out[1].tolist(), [1, 1, 0])
        self.assertAlmostEqual(out[2][2], 1e-3, 12)                 # point intérieur : celui de la surface
        self.assertEqual(out[3].tolist(), [0.5, 0.5, 0])            # sur un segment du bord : sa corde (round 629)


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestPanel(unittest.TestCase):
    def test_convert_bodies(self):
        from vectordrive.ui.view3d import Panel3D
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            p = Panel3D(w)
            good, bad = box_tris(0, 0, 0, 10, 10, 10), box_tris(20, 0, 0, 30, 10, 10)[:6]
            tris = np.concatenate([good, bad])
            m = model3d.Model3D(tris, np.ones((len(tris), 3)), np.zeros((0, 2, 3)),
                                body_of=np.r_[np.zeros(len(good), int), np.ones(len(bad), int)],
                                body_names=['Bon', 'Ouvert'])
            p.model = m
            p.view.set_model(m)
            with mock.patch.object(WT, 'fill_holes', lambda v, idx, max_perimeter=50.0: (v, idx, 0)):
                shapes, failed = p.to_volumes(show_report=False)
            self.assertEqual(len(shapes), 1)
            self.assertEqual([n for n, _r in failed], ['Ouvert'])
            vols = SO.doc_solids(w.canvas.doc)
            self.assertEqual(len(vols), 1)
            self.assertAlmostEqual(vols[0][1].volume(), 1000.0, 6)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
