"""Round 268 : textures de relief — relief d'une image (PhotoArt), texturing
algorithmique (fractal), tissage."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.core import galbe as GB, geom, texture3d as T3
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])
XS = np.arange(0, 20, 0.1)
X, Y = np.meshgrid(XS, XS[::-1])


class TestTextures(unittest.TestCase):
    def test_photo(self):
        h = T3.photo_heights(np.array([0.0, 0.5, 1.0]), T3.PhotoSpec(z_black=-1, z_white=3))
        self.assertEqual(h.tolist(), [-1.0, 1.0, 3.0])
        g = T3.photo_heights(np.array([0.5]), T3.PhotoSpec(z_black=0, z_white=1, gamma=2.0))
        self.assertAlmostEqual(float(g[0]), 0.25)

    def test_fractal(self):
        for kind, _l in T3.FRACTALS:
            h = T3.fractal(X, Y, T3.FractalSpec(kind=kind, height=0.8, frequency=0.2))
            self.assertAlmostEqual(float(h.max()), 0.8)
            self.assertAlmostEqual(float(h.min()), 0.0)
        a = T3.fractal(X, Y, T3.FractalSpec(seed=2))
        self.assertTrue(np.array_equal(a, T3.fractal(X, Y, T3.FractalSpec(seed=2))))   # même tirage
        self.assertFalse(np.array_equal(a, T3.fractal(X, Y, T3.FractalSpec(seed=3))))

    def test_weave(self):
        s = T3.WeaveSpec(pitch=5, width=4, height=1)
        h = T3.weave(X, Y, s)
        self.assertAlmostEqual(float(h.max()), 1.0, 2)
        # deux croisements voisins sur un même fil : dessus puis dessous
        a = T3.weave(np.array([[0.0]]), np.array([[0.0]]), s)[0, 0]
        b = T3.weave(np.array([[5.0]]), np.array([[0.0]]), s)[0, 0]
        self.assertAlmostEqual(a, b, 6)                                             # toujours un fil dessus
        A = T3.weave(np.array([[0.0]]), np.array([[1.2]]), s)[0, 0]                 # le long du fil dessous
        self.assertGreater(a, 0.9)
        self.assertLess(A, a)


class TestWindow(unittest.TestCase):
    def test_commands(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            zone = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]))
            c.doc.add(zone)
            c.select([zone])
            img = w.relief_texture('weave', T3.WeaveSpec(resolution=0.1))
            self.assertIsNotNone(img)
            self.assertAlmostEqual(img.extra['galbe']['relief_depth'], 1.0, 1)
            c.select([img])
            img2 = w.relief_texture('fractal', T3.FractalSpec(height=0.3, mode='ajouter'))
            self.assertGreater(img2.extra['galbe']['relief_depth'], 1.0)
            photo = GB.encode(np.tile(np.linspace(0, 1, 50), (20, 1)), 20.0, 10.0, 0.2, GB.GalbeSpec())
            photo.extra.pop('galbe')                                                # une image ordinaire
            c.doc.add(photo)
            c.select([photo])
            rel = w.relief_texture('photo', T3.PhotoSpec(z_black=0, z_white=2, smooth=0, resolution=0.2))
            H, *_ = GB.decode(rel)
            self.assertAlmostEqual(float(H.max() - H.min()), 2.0, 1)
            c.select([])
            self.assertIsNone(w.relief_texture('weave', T3.WeaveSpec()))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
