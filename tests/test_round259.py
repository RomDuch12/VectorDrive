"""Round 259 : TypeArt — cartes de hauteurs 16 bits, dôme (gaussien,
sphérique, cloche de verre), TypeArt extrudé, TypeArt de révolution,
facette par trois points, mode de combinaison global, onglet Relief."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import galbe as GB, geom, typeart as TA
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


def at(img, x, y):
    """Hauteur de la carte au point (x, y)."""
    H, x0, y1, res = GB.decode(img)
    return float(H[int((y1 - y) / res), int((x - x0) / res)])


def region(*paths):
    from vectordrive.cam import strategies as S
    return S.region(list(paths), 0.01)


class TestPrecision(unittest.TestCase):
    def test_16_bits(self):
        import numpy as np
        H = np.linspace(0, 10, 4000).reshape(40, 100)
        img = GB.encode(H, 0, 4, 0.1, GB.GalbeSpec())
        got, *_ = GB.decode(img)
        self.assertLess(float(np.abs(got - H).max()), 10 / 65535 + 1e-9)        # 8 bits : 0,02 mm d'écart
        from vectordrive.cam.advanced import _gray
        g = _gray(img, 100, 40)
        self.assertLess(float(np.abs(g * 10 - H).max()), 0.01)                  # relu pour l'usinage


class TestShapes(unittest.TestCase):
    def test_dome_profiles(self):
        import numpy as np
        r = np.array([0.0, 5.0, 10.0, 11.0])
        for shape in ('gauss', 'sphere', 'bezier'):
            h = TA.dome_profile(shape, r, 10.0, 3.0)
            self.assertAlmostEqual(h[0], 3.0)
            self.assertAlmostEqual(h[2], 0.0, 6)
            self.assertEqual(h[3], 0.0)
            self.assertTrue(0 < h[1] < 3)
        self.assertAlmostEqual(TA.dome_profile('sphere', np.array([5.0]), 10, 3)[0], 3 * math.sqrt(0.75))
        self.assertGreater(TA.dome_profile('bezier', np.array([5.0]), 10, 3)[0],
                           TA.dome_profile('gauss', np.array([5.0]), 10, 3)[0])   # cloche de verre : plus pleine

    def test_dome_and_combine(self):
        spec = TA.DomeSpec(shape='sphere', diameter=10, height=2, resolution=0.1, margin=0)
        img = TA.dome([(0, 0), (20, 0)], spec)
        self.assertAlmostEqual(at(img, 0.05, 0.05), 2.0, 1)
        self.assertAlmostEqual(at(img, 20.05, 0.05), 2.0, 1)
        self.assertAlmostEqual(at(img, 10.0, 0.0), 0.0, 3)
        ext = TA.extrude(region(geom.Path([geom.rect(-5, -5, 30, 10)])), TA.ExtrudeSpec(z=1, mode='ajouter'),
                         onto=img)
        self.assertAlmostEqual(at(ext, 0.05, 0.05), 3.0, 1)                       # ajouté au dôme
        self.assertAlmostEqual(at(ext, 10.0, 0.0), 1.0, 2)

    def test_revolution(self):
        # demi-cercle de rayon 5 autour de l'axe des x : une boule vue de dessus
        pts = [(5 * math.cos(a), 5 * math.sin(a)) for a in [k * math.pi / 60 for k in range(61)]]
        img = TA.revolution(pts, (-10, 0), (10, 0), TA.RevolutionSpec(resolution=0.05, margin=0))
        self.assertAlmostEqual(at(img, 0.0, 0.02), 5.0, 1)
        self.assertAlmostEqual(at(img, 3.0, 0.02), 4.0, 1)
        self.assertAlmostEqual(at(img, 0.0, 3.0), 4.0, 1)                        # √(5² − 3²)
        with self.assertRaises(ValueError):
            TA.revolution(pts, (0, 0), (0, 0), TA.RevolutionSpec())

    def test_plane(self):
        reg = region(geom.Path([geom.rect(0, 0, 10, 10)]))
        img = TA.plane(reg, [(0, 0), (10, 0), (0, 10)], TA.PlaneSpec(z1=0, z2=2, z3=1, margin=0, resolution=0.1))
        self.assertAlmostEqual(at(img, 5.05, 0.05), 1.0, 1)
        self.assertAlmostEqual(at(img, 9.95, 9.95), 3.0, 1)
        with self.assertRaises(ValueError):
            TA.plane(reg, [(0, 0), (5, 0), (10, 0)], TA.PlaneSpec())


class TestWindow(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.c = self.w.canvas

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def marker(self, x, y):
        from vectordrive.core import forms as F
        sh = F.make(F.Marker(cx=x, cy=y))
        self.c.doc.add(sh)
        return sh

    def test_tools_and_modes(self):
        from vectordrive.core.document import Image
        m1, m2, m3 = self.marker(0, 0), self.marker(10, 0), self.marker(0, 10)
        sq = Shape(path=geom.Path([geom.rect(0, 0, 10, 10)]))
        self.c.doc.add(sq)
        self.c.select([m1])
        dome = self.w.typeart_dome(TA.DomeSpec(diameter=8, height=2, margin=0))
        self.assertIsInstance(dome, Image)
        self.c.select([sq, m1, m2, m3, dome])
        fac = self.w.typeart_plane(TA.PlaneSpec(z1=0, z2=1, z3=0, margin=0, mode='maximum'))
        self.assertIsNot(fac, dome)
        self.assertNotIn(dome, self.c.doc.layers[0].items)                      # combiné : remplace l'ancien
        self.c.select([sq])
        self.assertIsNotNone(self.w.typeart_extrude(TA.ExtrudeSpec(z=1.5, margin=0)))
        self.w.A['typeart_mode_soustraire'].trigger()
        self.assertEqual(self.w.typeart_mode(), ('soustraire', False))
        self.assertTrue(self.w.A['typeart_mode_soustraire'].isChecked())
        self.w.A['typeart_mode_limit'].trigger()
        self.assertEqual(self.w.typeart_mode(), ('soustraire', True))
        self.w.A['typeart_mode_limit'].trigger()
        self.w.A['typeart_mode_ajouter'].trigger()
        from vectordrive.ui import shortcuts as SC
        for cmd in ('ID_TART_GALBEONMARKER', 'ID_TART_EXTRUSION', 'ID_TART_REVOLUTION', 'ID_COMBI3'):
            self.assertIn(SC.TE_ACTIONS[cmd], self.w.A)
        r = self.w.ribbon
        self.assertEqual([r.tabText(i) for i in range(r.count())].count('CAD'), 2)   # round 903 : le 3D (l'ancien
        #                                                                           Relief, round 412) est le CAD de la 3D

    def test_revolution_from_line_axis(self):
        prof = Shape(path=geom.Path([geom.polyline([(-4, 0), (-4, 3), (4, 3), (4, 0)])]))
        axis = Shape(path=geom.Path([geom.polyline([(-6, 0), (6, 0)])]))
        self.c.doc.add(prof)
        self.c.doc.add(axis)
        self.c.select([prof, axis])
        img = self.w.typeart_revolution(TA.RevolutionSpec(margin=0, resolution=0.05))
        self.assertIsNotNone(img)
        self.assertAlmostEqual(at(img, 0.0, 0.02), 3.0, 1)                       # cylindre de rayon 3


if __name__ == '__main__':
    unittest.main()
