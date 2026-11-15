"""Round 418 : volumes — balayage, lissage entre sections, mur."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core import solids as S
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


@unittest.skipUnless(S.available(), 'manifold3d absent')
class TestCore(unittest.TestCase):
    def test_sweep(self):
        line = geom.polyline([(0, 0), (50, 0)])
        tube = S.sweep(line, geom.Path([geom.circle((0, 0), 5)]))
        self.assertAlmostEqual(tube.volume(), math.pi * 25 * 50, delta=math.pi * 25 * 50 * 0.01)
        self.assertEqual(tuple(round(v, 4) for v in tube.bounds()), (0, -5, -5, 50, 5, 5))
        elbow = S.sweep(geom.polyline([(0, 0), (50, 0), (50, 30)]), geom.Path([geom.rect(-2, -2, 4, 4)]))
        self.assertAlmostEqual(elbow.volume(), 16 * 80, places=4)                 # onglet : volume exact
        ring = S.sweep(geom.circle((0, 0), 20), geom.Path([geom.circle((0, 0), 5)]))
        self.assertAlmostEqual(ring.volume(), 2 * math.pi ** 2 * 500, delta=150)  # chemin fermé : tore
        hollow = S.sweep(line, geom.Path([geom.rect(-5, -5, 10, 10), geom.rect(-2, -2, 4, 4)]))
        self.assertAlmostEqual(hollow.volume(), 84 * 50, places=4)                # le trou reste un trou
        tw = S.sweep(line, geom.Path([geom.rect(-5, -2, 10, 4)]), twist=90)
        self.assertAlmostEqual(tw.volume(), 2000, delta=80)
        cone = S.sweep(line, geom.Path([geom.circle((0, 0), 5)]), scale_end=0.5)
        self.assertLess(cone.volume(), tube.volume())

    def test_loft_wall(self):
        lo = S.loft([geom.rect(0, 0, 20, 20), geom.rect(5, 5, 10, 10)], [0, 10])
        exact = 10 / 3 * (400 + 100 + math.sqrt(400 * 100))                       # tronc de pyramide
        self.assertAlmostEqual(lo.volume(), exact, delta=exact * 0.01)
        sm = S.loft([geom.rect(0, 0, 20, 20), geom.circle((10, 10), 5), geom.rect(5, 5, 10, 10)], [0, 10, 20],
                    smooth=True)
        self.assertAlmostEqual(sm.bounds()[5], 20)
        with self.assertRaises(S.SolidError):
            S.loft([geom.rect(0, 0, 1, 1)], [0])
        w = S.polysolid(geom.polyline([(0, 0), (50, 0), (50, 30)]), 4, 10, 'gauche')
        self.assertAlmostEqual(w.volume(), 4 * 10 * (50 + 30 - 4), places=3)   # à gauche : coin intérieur
        self.assertAlmostEqual(w.bounds()[1], 0, places=6)


@unittest.skipUnless(S.available(), 'manifold3d absent')
class TestCommands(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()
        self.c = self.w.canvas

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_commands(self):
        path = Shape(path=geom.Path([geom.polyline([(0, 0), (60, 0)])]))
        prof = Shape(path=geom.Path([geom.circle((0, 0), 3)]))
        for it in (path, prof):
            self.c.doc.add(it)
        self.c.select([path, prof])
        got = self.w.solid_sweep(params={'z': 3.0, 'twist': 0.0, 'scale_end': 1.0, 'delete': True})
        self.assertEqual(len(got), 1)
        self.assertAlmostEqual(S.of_item(got[0]).bounds()[2], 0, places=4)
        a = Shape(path=geom.Path([geom.rect(0, 0, 20, 20)]))
        b = Shape(path=geom.Path([geom.rect(5, 5, 10, 10)]))
        for it in (a, b):
            self.c.doc.add(it)
        self.c.select([a, b])
        lo = self.w.solid_loft(params={'step': 10.0, 'heights': '0; 25', 'smooth': False, 'delete': True})
        self.assertAlmostEqual(S.of_item(lo[0]).bounds()[5], 25)
        self.assertEqual(self.w.solid_loft(params={'step': 1.0, 'heights': '', 'smooth': False,
                                                    'delete': True}), [])          # un volume seul choisi
        wall = Shape(path=geom.Path([geom.polyline([(0, 50), (40, 50)])]))
        self.c.doc.add(wall)
        self.c.select([wall])
        ws = self.w.solid_polysolid(params={'width': 2.0, 'height': 8.0, 'justify': 'centre', 'z': 0.0,
                                            'delete': False})
        self.assertAlmostEqual(S.of_item(ws[0]).volume(), 2 * 8 * 40, places=3)


if __name__ == '__main__':
    unittest.main()
