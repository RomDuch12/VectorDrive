"""Round 366 : dôme par profil — profil dessiné tourné autour d'un axe
vertical, révolution complète ou partielle."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom, primitives3d as P3
from vectordrive.core.document import Shape
from vectordrive.core.relief_ops import z_at

app = QApplication.instance() or QApplication([])

# profil en marche : 4 mm de haut jusqu'au rayon 5, puis pente jusqu'à 0 au rayon 10
PROFILE = [(100, 54), (105, 54), (110, 50)]


class TestRevolution(unittest.TestCase):
    def test_profile(self):
        R, Z = P3.profile_of([(3, 1), (1, 1), (1, 3)])            # rayon égal : le plus haut
        self.assertEqual(R.tolist(), [0.0, 2.0])
        self.assertEqual(Z.tolist(), [2.0, 0.0])

    def test_full(self):
        img = P3.revolution_relief(PROFILE, P3.RevolutionSpec(margin=0), (0, 0))
        self.assertAlmostEqual(z_at(img, 0, 0), 4.0, 1)
        self.assertAlmostEqual(z_at(img, 0, -3), 4.0, 1)
        self.assertAlmostEqual(z_at(img, -7.5, 0), 2.0, 1)
        self.assertAlmostEqual(z_at(img, 0, 7.5), 2.0, 1)

    def test_partial_and_height(self):
        sp = P3.RevolutionSpec(start_angle=0, end_angle=90, height=8, margin=0)
        img = P3.revolution_relief(PROFILE, sp, (0, 0))
        self.assertAlmostEqual(z_at(img, 3, 3), 8.0, 1)            # quart haut-droit
        self.assertAlmostEqual(z_at(img, -3, -3), 0.0, 3)          # hors de la plage d'angles

    def test_window(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            s = Shape(path=geom.Path([geom.polyline(PROFILE)]))
            w.canvas.doc.add(s)
            w.canvas.select([s])
            img = w.relief_revolution(P3.RevolutionSpec(margin=0))
            self.assertAlmostEqual(z_at(img, 100, 50), 4.0, 1)     # autour du point le plus à gauche, en bas
            w.canvas.select([])
            self.assertIsNone(w.relief_revolution(P3.RevolutionSpec()))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
