"""Round 250 : vue 3D revue — barre sur deux rangées, projection
orthogonale ou perspective, affichage ombré / ombré et arêtes / filaire,
trièdre des axes, tout voir (F), plan de coupe en Z, rapides affichables ;
et deux plantages évités (cases d'une liste refaite pendant leur signal)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


def model():
    import numpy as np
    from vectordrive.io.model3d import Model3D
    tris = np.array([[[0, 0, 0], [30, 0, 0], [0, 20, 0]], [[0, 0, 10], [30, 0, 10], [0, 20, 10]]], np.float32)
    return Model3D(tris, np.ones((2, 3), np.float32), np.array([[[0, 0, 0], [0, 0, 10]]], np.float32))


class TestView(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.view3d import View3D
        self.v = View3D()
        self.v.resize(400, 300)
        self.v.set_model(model())

    def tearDown(self):
        self.v.deleteLater()

    def test_triad_follows_camera(self):
        v = self.v
        v.set_view('dessus')
        axes = {n: (dx, dy) for n, dx, dy in v.triad_axes()}
        self.assertAlmostEqual(axes['X'][0], 1.0, 3)                    # X vers la droite
        self.assertAlmostEqual(axes['Y'][1], -1.0, 2)                   # Y vers le haut de l'écran
        self.assertLess(math.hypot(*axes['Z']), 0.01)                   # Z vers soi
        v.set_view('face')
        axes = {n: (dx, dy) for n, dx, dy in v.triad_axes()}
        self.assertLess(axes['Z'][1], -0.9)                             # de face : Z vers le haut
        v.grab()                                                        # dessin (trièdre compris) sans erreur

    def test_ortho_display_clip_fit(self):
        v = self.v
        persp = v.camera()
        v.set_ortho(True)
        self.assertNotEqual(list(persp.data()), list(v.camera().data()))
        v.set_display('filaire')
        self.assertEqual(v.display, 'filaire')
        v.set_display('inconnu')
        self.assertEqual(v.display, 'aretes')
        self.assertEqual(v.z_range(), (0.0, 10.0))
        v.set_clip(0.5)
        self.assertAlmostEqual(v.clip, 5.0)
        v.set_clip(1.0)
        self.assertIsNone(v.clip)
        v.zoom, v.yaw = 3.0, 12.0
        v.fit()
        self.assertEqual((v.zoom, v.yaw), (1.0, 12.0))                  # orientation gardée


class TestPanel(unittest.TestCase):
    def test_controls(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            p = w._ensure_panel3d()
            p.ortho.setChecked(True)
            self.assertTrue(p.view.ortho)
            p.display.setCurrentIndex(p.display.findData('ombre'))
            self.assertEqual(p.view.display, 'ombre')
            p.rapids.setChecked(True)
            self.assertTrue(p.view.show_rapids)
            p.clip.setValue(40)
            self.assertIsNotNone(p.view.clip)
            p.clip.setValue(100)
            self.assertIsNone(p.view.clip)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
