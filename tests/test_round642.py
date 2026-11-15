"""Round 642 : la pièce se voit en mode sombre — arêtes claires sur fond
sombre (modèle et matériel de serrage), traits jamais noirs (shader) ; couleur de la pièce et des arêtes au
choix (menu « Couleurs » de la vue 3D), retenues dans les réglages."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from vectordrive.io.model3d import Model3D
from vectordrive.ui import view3d as V3

app = QApplication.instance() or QApplication([])


def cube():
    t = np.array([[[0, 0, 0], [1, 0, 0], [1, 1, 0]], [[0, 0, 0], [1, 1, 0], [0, 1, 0]]], np.float32)
    cols = np.array([[0.7, 0.74, 0.8], [0.2, 0.3, 0.9]], np.float32)
    segs = np.array([[[0, 0, 0], [1, 0, 0]]], np.float32)
    return Model3D(t, cols, segs, 'essai')


class TestColors(unittest.TestCase):
    def test_edge_for_background(self):
        self.assertEqual(V3.edge_for(QColor('#ffffff')), V3.EDGE)
        self.assertEqual(V3.edge_for(QColor('#1e1e1e')), V3.EDGE_DARK_BG)
        self.assertGreater(sum(V3.EDGE_DARK_BG), 2.0)                         # clair : lisible sur noir

    def test_lines_not_lit(self):
        # traits (arêtes, grille, brut) : normale nulle — normalize(0) donnait NaN, tracés en noir
        self.assertIn('if (lit > 0.0)', V3.VS)
        g, _step = V3.grid_lines(0, 0, 10, 10, 0.0, color=V3.GRID_DARK_BG)
        self.assertTrue(np.allclose(g[:, 3:6], 0.0))
        self.assertTrue(np.allclose(g[:, 6:9], V3.GRID_DARK_BG))
        self.assertLess(sum(V3.GRID_DARK_BG), sum(V3.EDGE_DARK_BG))          # grille sous les arêtes

    def test_hex_round_trip(self):
        self.assertEqual(V3.hex_of((1.0, 0.5, 0.0)), '#ff8000')
        r, g, b = V3.rgb_of('#ff8000')
        self.assertAlmostEqual(r, 1.0)
        self.assertAlmostEqual(g, 128 / 255)
        self.assertIsNone(V3.rgb_of(''))
        self.assertIsNone(V3.rgb_of('pas une couleur'))
        self.assertEqual(V3.hex_of(None), '')

    def test_model_arrays_colors(self):
        tri, edge = V3.model_arrays(cube())
        self.assertTrue(np.allclose(tri[3:6, 6:9], [0.2, 0.3, 0.9]))           # couleurs du fichier
        self.assertTrue(np.allclose(edge[:, 6:9], V3.EDGE))
        tri, edge = V3.model_arrays(cube(), [1], face_color=(1.0, 0.0, 0.0), edge_color=(0.9, 0.9, 0.9))
        self.assertTrue(np.allclose(tri[:3, 6:9], [1.0, 0.0, 0.0]))            # une couleur pour la pièce
        self.assertTrue(np.allclose(tri[3:6, 6:9], V3.PICKED_FACE))            # face choisie : toujours orange
        self.assertTrue(np.allclose(edge[:, 6:9], 0.9))


class TestPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w._ensure_panel3d()

    @classmethod
    def tearDownClass(cls):
        cls.w.panel3d.reset_colors()
        cls.w.modified = False
        cls.w.close()

    def test_edges_follow_background(self):
        v = self.w.panel3d.view
        v.edge_color = None
        v._background = lambda: QColor('#202226')                            # thème sombre
        self.assertEqual(v.edge_rgb(), V3.EDGE_DARK_BG)
        v._background = lambda: QColor('#f4f5f7')
        self.assertEqual(v.edge_rgb(), V3.EDGE)
        del v._background

    def test_choice_kept(self):
        p = self.w.panel3d
        p.set_colors(part=(0.9, 0.6, 0.1))
        self.assertEqual(p.view.part_color, (0.9, 0.6, 0.1))
        self.assertIsNone(p.view.edge_color)                                   # arêtes : inchangées
        st = self.w.settings
        self.assertEqual(st.value(V3.PART_COLOR_KEY), V3.hex_of((0.9, 0.6, 0.1)))
        p.set_colors(edge=(1.0, 1.0, 1.0))
        self.assertEqual(p.view.edge_rgb(), (1.0, 1.0, 1.0))
        q = V3.Panel3D(self.w)                                                 # nouvelle vue : couleurs reprises
        self.assertAlmostEqual(q.view.part_color[0], 0.9, places=2)
        self.assertEqual(q.view.edge_color, (1.0, 1.0, 1.0))
        q.deleteLater()
        p.reset_colors()
        self.assertIsNone(p.view.part_color)
        self.assertEqual(st.value(V3.PART_COLOR_KEY), '')
        texts = [a.text() for a in p.color_btn.menu().actions()]
        self.assertIn('Couleurs d\'origine', texts)

    def test_choose_from_dialog(self):
        from PySide6.QtWidgets import QColorDialog
        p = self.w.panel3d
        old = QColorDialog.getColor
        QColorDialog.getColor = staticmethod(lambda *a, **k: QColor('#00ff00'))
        try:
            p.choose_color('part')
        finally:
            QColorDialog.getColor = old
        self.assertEqual(p.view.part_color, (0.0, 1.0, 0.0))
        p.reset_colors()


if __name__ == '__main__':
    unittest.main()
