"""Round 269 : galbe — compression (aucune, sur la longueur,
proportionnelle), galbe asymétrique au profil dessiné ; une forme qui
touche le bord de la carte (fond 0 mm) garde son bord."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import shapely
from PySide6.QtWidgets import QApplication

from vectordrive.core import galbe as GB, geom
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])
L_SHAPE = shapely.union_all([shapely.box(0, 0, 30, 4), shapely.box(0, 0, 10, 20)])   # barre de 4 + barre de 10


def heights(comp, **kw):
    H, x0, y1, res = GB.heightmap(L_SHAPE, GB.GalbeSpec(z_max=2, distance=4, compression=comp, margin=0,
                                                       resolution=0.1, **kw))
    return lambda x, y: float(H[int((y1 - y) / res), int((x - x0) / res)])


class TestCompression(unittest.TestCase):
    def test_modes(self):
        none, length, prop = heights('aucune'), heights('longueur'), heights('proportionnelle')
        self.assertLess(none(25, 2), 1.9)                                         # trop étroite : sous Z max.
        self.assertAlmostEqual(none(5, 12), 2.0, 2)
        self.assertAlmostEqual(length(25, 2), 2.0, 2)                             # Z max. sur toute l'arête
        self.assertAlmostEqual(length(5, 12), 2.0, 2)
        self.assertAlmostEqual(prop(25, 2), 2.0 * 1.95 / 4, 1)                    # proportionnelle à la largeur
        self.assertAlmostEqual(prop(5, 12), 2.0, 2)

    def test_ridge(self):
        import numpy as np
        d = np.array([[0, 1, 2, 1, 0], [0, 1, 2, 1, 0]], float)
        self.assertEqual(GB.ridge_distance(d).tolist(), [[0, 2, 2, 2, 0], [0, 2, 2, 2, 0]])

    def test_border_and_profile(self):
        H, *_ = GB.heightmap(shapely.box(0, 0, 30, 4), GB.GalbeSpec(z_max=2, distance=4, margin=0))
        self.assertLess(float(H[-1, 150]), 0.6)                                   # bord de la carte = bord
        spec = GB.GalbeSpec(margin=0, profile_pts=[(10, 0), (11, 1), (13, 1.5)])  # profil dessiné : 3 mm, 1,5 mm
        self.assertEqual(GB.profile_length(spec), 3.0)
        self.assertAlmostEqual(float(GB.profile(spec, [1.0])[0]), 1.0)
        self.assertAlmostEqual(float(GB.profile(spec, [9.0])[0]), 1.5)


class TestWindow(unittest.TestCase):
    def test_profile_from_selection(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            sq = Shape(path=geom.Path([geom.rect(0, 0, 20, 20)]))
            prof = Shape(path=geom.Path([geom.polyline([(40, 0), (41, 0.5), (44, 0.5)])]))
            c.doc.add(sq)
            c.doc.add(prof)
            c.select([sq, prof])
            img = w.galbe_dialog(GB.GalbeSpec(margin=1, resolution=0.2))
            self.assertAlmostEqual(img.extra['galbe']['relief_depth'], 0.5, 2)       # hauteur du profil dessiné
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
