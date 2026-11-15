"""Round 199 : galbes combinés et lissage (TypeArt)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication
from shapely.geometry import Point, box

from vectordrive.core import galbe as GB, geom
from vectordrive.core.document import Shape


def at(img, x, y):
    H, x0, y1, res = GB.decode(img)
    return H[int((y1 - y) / res), int((x - x0) / res)]


class TestCombine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_combine_rules(self):
        old = np.array([[0.0, 1.0, 2.0]])
        new = np.array([[1.0, 1.0, 1.0]])
        inside = np.array([[True, True, False]])
        self.assertEqual(GB.combine(old, new, inside, 'ajouter').tolist(), [[1.0, 2.0, 2.0]])
        self.assertEqual(GB.combine(old, new, inside, 'soustraire').tolist(), [[-1.0, 0.0, 2.0]])
        self.assertEqual(GB.combine(old, new, inside, 'remplacer').tolist(), [[1.0, 1.0, 2.0]])
        self.assertEqual(GB.combine(old, new, inside, 'minimum').tolist(), [[0.0, 1.0, 2.0]])
        self.assertEqual(GB.combine(old, new, inside, 'ajouter', limit=True).tolist(), [[0.0, 2.0, 2.0]])

    def test_encode_decode(self):
        spec = GB.GalbeSpec(z_max=2.0, distance=2.0, resolution=0.2)
        img = GB.build_image(box(0, 0, 10, 10), spec)
        H, x0, y1, res = GB.decode(img)
        self.assertAlmostEqual(H.max(), 2.0, delta=0.01)
        self.assertAlmostEqual(res, 0.2, delta=1e-6)
        self.assertEqual(img.extra['galbe']['base'], 0.0)
        from vectordrive.core.geom import Affine
        self.assertIsNone(GB.decode(img.transformed(Affine.rotation(30.0))))       # tournée : refusée
        self.assertIsNone(GB.decode(img.transformed(Affine.mirror_y(5.0))))        # retournée : refusée
        self.assertIsNotNone(GB.decode(img.transformed(Affine.translation(3.0, 1.0))))
        self.assertIsNone(GB.decode(img.transformed(Affine.scaling(2.0, 1.0))))      # étirée : refusée
        long_ = GB.build_image(box(0, 0, 60, 4), spec)
        self.assertIsNotNone(GB.decode(long_))                                     # carte allongée : lue

    def test_add_and_subtract_onto(self):
        spec = GB.GalbeSpec(z_max=2.0, distance=2.0, resolution=0.2, margin=1.0)
        first = GB.build_image(box(0, 0, 20, 10), spec)
        add = GB.build_image(Point(10, 5).buffer(3, 32), GB.GalbeSpec(z_max=1.0, distance=1.0, resolution=0.2,
                                                                         mode='ajouter'), onto=first)
        self.assertAlmostEqual(at(add, 10, 5), 3.0, delta=0.05)                    # 2 + 1 au centre
        self.assertAlmostEqual(at(add, 3, 5), 2.0, delta=0.05)                     # ailleurs, l'existant
        sub = GB.build_image(Point(30, 5).buffer(3, 32), GB.GalbeSpec(z_max=1.0, distance=1.0, resolution=0.2,
                                                                         mode='soustraire'), onto=first)
        self.assertLess(sub.extra['galbe']['base'], -0.9)                          # creux sous le fond
        self.assertAlmostEqual(at(sub, 30, 5), -1.0, delta=0.05)
        self.assertGreater(sub.bbox()[2], 32.9)                                   # carte agrandie
        lim = GB.build_image(Point(30, 5).buffer(3, 32), GB.GalbeSpec(z_max=1.0, distance=1.0, resolution=0.2,
                                                                         mode='ajouter', limit=True), onto=first)
        self.assertAlmostEqual(at(lim, 30, 5), 0.0, delta=0.02)                    # hors du galbe existant : rien

    def test_smooth(self):
        spec = GB.GalbeSpec(z_max=2.0, distance=0.01, start_angle=90, resolution=0.2, margin=1.0)
        img = GB.build_image(box(0, 0, 10, 10), spec)                              # marche presque verticale
        H0 = GB.decode(img)[0]
        H1 = GB.decode(GB.smooth(img, 3))[0]
        self.assertLess(np.abs(np.diff(H1, axis=1)).max(), np.abs(np.diff(H0, axis=1)).max() * 0.6)
        part = GB.decode(GB.smooth(img, 3, box(-2, -2, 5, 12)))[0]
        self.assertAlmostEqual(np.abs(part[:, -8:] - H0[:, -8:]).max(), 0.0, delta=0.02)   # hors zone : intact


class TestUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_combine_in_place_and_smooth(self):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual(TE_ACTIONS['ID_GALBE_LISSAGE'], 'galbe_smooth')
        w = MainWindow()
        try:
            a = Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]))
            w.canvas.doc.add(a)
            w.canvas.selection = [a]
            img = w.galbe_dialog(GB.GalbeSpec(z_max=2.0, distance=2.0, resolution=0.25))
            b = Shape(path=geom.Path([geom.circle((10, 5), 3)]))
            w.canvas.doc.add(b)
            w.canvas.selection = [img, b]
            new = w.galbe_dialog(GB.GalbeSpec(z_max=1.0, distance=1.0, resolution=0.25, mode='ajouter'))
            leaves = list(w.canvas.doc.iter_leaves())
            self.assertIn(new, leaves)
            self.assertNotIn(img, leaves)                                          # remplacé sur place
            self.assertAlmostEqual(at(new, 10, 5), 3.0, delta=0.05)
            w.canvas.selection = [new]
            sm = w.galbe_smooth(2)
            self.assertIn(sm, list(w.canvas.doc.iter_leaves()))
            w.undo()
            self.assertIn(new, list(w.canvas.doc.iter_leaves()))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
