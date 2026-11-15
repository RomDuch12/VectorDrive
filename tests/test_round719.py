"""Round 719 : perçages 3D (simple, lamé, fraisé, pointe de foret), tube le
long d'un trait et volume englobant, d'après SolidCraft."""
import math
import os
import tempfile
import unittest

import numpy as np

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import geom
from vectordrive.core import solids as SO
from vectordrive.core.geom import Contour, Line, Path


def _radii(s, cx, cy, z0, z1, r_max=1e9):
    V = s.verts
    r = np.hypot(V[:, 0] - cx, V[:, 1] - cy)
    return r[(V[:, 2] > z0) & (V[:, 2] < z1) & (r < r_max)]


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestHole(unittest.TestCase):
    def setUp(self):
        self.b = SO.box(0, 0, 0, 40, 40, 20)

    def test_simple_and_point(self):
        s = SO.hole(self.b, 20, 20, 6.0, 10.0)
        self.assertAlmostEqual(self.b.volume() - s.volume(), math.pi * 9 * 10, delta=1.0)
        self.assertAlmostEqual(_radii(s, 20, 20, 9.99, 20.01, 5).max(), 3.0, places=3)
        p = SO.hole(self.b, 20, 20, 6.0, 10.0, point=True)
        tip = p.verts[np.hypot(p.verts[:, 0] - 20, p.verts[:, 1] - 20) < 1e-6]
        self.assertAlmostEqual(tip[:, 2].min(), 10 - 3 / math.tan(math.radians(59)), places=4)
        t = SO.hole(self.b, 20, 20, 6.0)                                           # débouchant
        self.assertAlmostEqual(self.b.volume() - t.volume(), math.pi * 9 * 20, delta=2.0)
        self.assertAlmostEqual(_radii(t, 20, 20, -1e-6, 1e-6, 5).min(), 3.0, places=3)
        self.assertEqual(t.name, self.b.name)

    def test_counterbore_countersink(self):
        s = SO.hole(self.b, 20, 20, 6.6, kind='lame', cb_diameter=11.0, cb_depth=6.4)
        removed = math.pi * (5.5 ** 2 * 6.4 + 3.3 ** 2 * 13.6)
        self.assertAlmostEqual((self.b.volume() - s.volume()) / removed, 1.0, delta=0.01)
        r = _radii(s, 20, 20, 13.59, 13.61, 7)                                    # fond du lamage
        self.assertAlmostEqual(r.max(), 5.5, places=3)
        self.assertAlmostEqual(r.min(), 3.3, places=3)
        d = SO.hole(self.b, 20, 20, 6.0, kind='lame')                              # 0 : 1,8 d × d
        self.assertAlmostEqual(_radii(d, 20, 20, 13.99, 14.01, 7).max(), 5.4, places=3)
        f = SO.hole(self.b, 20, 20, 6.6, kind='fraise', cs_diameter=13.0)
        top = _radii(f, 20, 20, 19.99, 20.01, 8)
        self.assertAlmostEqual(top.max(), 6.5, places=3)                           # fraisure à 90°
        ring = _radii(f, 20, 20, 20 - 3.2 - 0.01, 20 - 3.2 + 0.01, 8)               # la fraisure rejoint le trou
        self.assertAlmostEqual(ring.min(), 3.3, places=3)
        self.assertAlmostEqual(ring.max(), 3.3, places=3)
        for kw in ({'kind': 'lame', 'cb_diameter': 5.0}, {'kind': 'lame', 'cb_depth': 15.0, 'depth': 10.0},
                   {'kind': 'fraise', 'cs_diameter': 5.0}, {'kind': 'fraise', 'cs_diameter': 40.0, 'depth': 3.0},
                   {'depth': 0.0}):
            with self.assertRaises(SO.SolidError):
                SO.hole(self.b, 20, 20, 6.0, **kw)
        with self.assertRaises(SO.SolidError):
            SO.hole(self.b, 20, 20, 0.0)


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestPipeBounding(unittest.TestCase):
    def test_pipe(self):
        line = Contour([Line((0, 0), (50, 0))])
        s = SO.pipe(line, 10.0)
        self.assertAlmostEqual(s.volume() / (math.pi * 25 * 50), 1.0, delta=0.01)
        b = s.bounds()
        self.assertAlmostEqual(b[2], 0.0, places=3)                               # posé sur le plan
        self.assertAlmostEqual(b[5], 10.0, places=3)
        h = SO.pipe(line, 10.0, 2.0, z=20.0)
        self.assertAlmostEqual(h.volume() / (math.pi * (25 - 9) * 50), 1.0, delta=0.01)
        self.assertAlmostEqual(h.bounds()[2], 15.0, places=3)
        ring = SO.pipe(geom.circle((0, 0), 30), 6.0, 1.0)                          # fermé : un anneau
        self.assertAlmostEqual(ring.volume() / (math.pi * (9 - 4) * 2 * math.pi * 30), 1.0, delta=0.01)
        bend = SO.pipe(Contour([Line((0, 0), (40, 0)), Line((40, 0), (40, 30))]), 8.0, 1.0)
        self.assertEqual(len(SO.components(bend)), 1)
        for args in ((0.0,), (10.0, 5.0), (10.0, -1.0)):
            with self.assertRaises(SO.SolidError):
                SO.pipe(line, *args)

    def test_bounding(self):
        a = SO.sphere(0, 0, 10, 10)
        b = SO.cylinder(30, 0, 0, 5, 40)
        box = SO.bounding([a, b], 2.0)
        lo = np.minimum(a.bounds()[:3], b.bounds()[:3]) - 2
        hi = np.maximum(a.bounds()[3:], b.bounds()[3:]) + 2
        for got, want in zip(box.bounds(), list(lo) + list(hi)):
            self.assertAlmostEqual(got, want, places=4)
        cyl = SO.bounding([a, b], 1.0, 'cylindre')
        x0, y0, z0, x1, y1, z1 = cyl.bounds()
        self.assertAlmostEqual((z0, z1), (-1.0, 41.0))
        self.assertAlmostEqual((x0 + x1) / 2, 12.5, places=3)
        with self.assertRaises(SO.SolidError):                                    # tout dedans : reste vide
            SO.boolean('subtract', [SO.boolean('union', [a, b]), cyl])
        with self.assertRaises(SO.SolidError):
            SO.bounding([])


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()
        cls.w.resize(1000, 700)

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def add(self, contour):
        from vectordrive.core.document import Shape
        sh = Shape(path=Path([contour]))
        self.w.canvas.doc.add(sh)
        return sh

    def test_hole_pipe_bounding(self):
        w, c = self.w, self.w.canvas
        c.select([])
        box = w.solid_primitive('box', {'dx': 40.0, 'dy': 40.0, 'dz': 15.0})
        b = SO.of_item(box[0]).bounds()
        cx, cy = (b[0] + b[3]) / 2, (b[1] + b[4]) / 2
        circles = [self.add(geom.circle((cx - 10, cy), 3.3)), self.add(geom.circle((cx + 10, cy), 4.5))]
        v0 = SO.of_item(box[0]).volume()
        c.select([box[0]] + circles)
        new = w.solid_hole({'kind': 'lame', 'through': True})
        self.assertEqual(len(new), 1)
        s = SO.of_item(new[0])
        self.assertAlmostEqual(_radii(s, cx + 10, cy, -1e-6, 1e-6, 6).min(), 4.5, delta=0.01)
        self.assertLess(s.volume(), v0 - math.pi * (3.3 ** 2 + 4.5 ** 2) * 15)
        w.undo()
        c.select(circles)
        self.assertEqual(w.solid_hole({}), [])                                     # pas de volume
        line = self.add(Contour([Line((0, 0), (60, 0)), Line((60, 0), (60, 40))]))
        c.select([line])
        tubes = w.solid_pipe({'diameter': 8.0, 'wall': 1.5})
        self.assertEqual(len(tubes), 1)
        self.assertIn(line, c.doc.active_layer.items)
        c.select(tubes)
        env = w.solid_bounding({'margin': 0.0})
        self.assertEqual(SO.of_item(env[0]).bounds(), SO.of_item(tubes[0]).bounds())

    def test_ribbon_icons(self):
        from vectordrive.ui import icons
        for k, a in (('hole3d', 'solid_hole'), ('pipe', 'solid_pipe'), ('bounding', 'solid_bounding')):
            self.assertIn(k, icons.ICONS)
            self.assertFalse(self.w.A[a].icon().isNull())
            self.assertTrue(self.w.A[a].toolTip())


if __name__ == '__main__':
    unittest.main()
