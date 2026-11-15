"""Round 718 : ressort (COIL) et filetage ISO modélisé (tige filetée,
taraudage), d'après SolidCraft."""
import math
import os
import tempfile
import unittest
from unittest import mock

import numpy as np

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import geom
from vectordrive.core import solids as SO
from vectordrive.core.geom import Path


def _radii(s, cx, cy, z0, z1, r_max=1e9):
    V = s.verts
    r = np.hypot(V[:, 0] - cx, V[:, 1] - cy)
    keep = (V[:, 2] > z0) & (V[:, 2] < z1) & (r < r_max)
    return r[keep]


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestMetric(unittest.TestCase):
    def test_designations(self):
        self.assertEqual(SO.parse_metric('M8'), (8.0, 1.25))
        self.assertEqual(SO.parse_metric(' m8 x 1 '), (8.0, 1.0))
        self.assertEqual(SO.parse_metric('M1,6'), (1.6, 0.35))
        for bad in ('M7', 'X8', 'M8x9', '', 'M8x0'):
            with self.assertRaises(SO.SolidError):
                SO.parse_metric(bad)
        self.assertEqual(SO.format_metric(8.0, 1.25), 'M8')
        self.assertEqual(SO.format_metric(8.0, 1.0), 'M8x1')
        self.assertEqual(SO.format_metric(1.6, 0.35), 'M1.6')
        self.assertEqual(SO.metric_for(8.0), (8.0, 1.25))
        self.assertEqual(SO.metric_for(6.8, internal=True), (8.0, 1.25))      # perçage d - pas
        self.assertEqual(SO.metric_for(10.2, internal=True), (12.0, 1.75))
        self.assertIsNone(SO.metric_for(100.0))


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestCoil(unittest.TestCase):
    def test_round(self):
        s = SO.coil(5, 5, 1, 20, 5, 6, 2)
        length = 6 * math.hypot(math.pi * 20, 5)
        self.assertAlmostEqual(s.volume() / (length * math.pi), 1.0, delta=0.02)
        x0, y0, z0, x1, y1, z1 = s.bounds()
        self.assertAlmostEqual(x1, 5 + 11, places=3)
        self.assertAlmostEqual(z0, 1.0, places=6)                                # posé sur Z0
        self.assertAlmostEqual(z1, 1 + 2 + 6 * 5, places=6)
        self.assertEqual(len(SO.components(s)), 1)

    def test_square_position_hand(self):
        s = SO.coil(0, 0, 0, 20, 5, 3, 2, square=True, position=-1)            # diamètre hors tout
        self.assertAlmostEqual(s.bounds()[3], 10.0, places=6)
        self.assertAlmostEqual(s.volume() / (3 * math.hypot(math.pi * 18, 5) * 4), 1.0, delta=0.01)
        self.assertAlmostEqual(SO.coil(0, 0, 0, 20, 5, 3, 2, position=1).bounds()[3], 12.0, places=3)
        right = SO.coil(0, 0, 0, 20, 4, 0.25, 2).verts.mean(axis=0)
        left = SO.coil(0, 0, 0, 20, 4, 0.25, 2, left=True).verts.mean(axis=0)
        self.assertGreater(right[1], 5.0)                                        # sens direct en montant
        self.assertAlmostEqual(left[1], -right[1])

    def test_errors(self):
        for args in ((2, 5, 3, 2, False, -1),                                    # la section touche l'axe
                     (20, 1.5, 3, 2),                                            # pas sous la section
                     (20, 5, 300, 2),                                            # trop de tours
                     (20, 5, 0, 2)):
            with self.assertRaises(SO.SolidError):
                SO.coil(0, 0, 0, *args)
        self.assertGreater(SO.coil(0, 0, 0, 20, 0, 0.5, 2).volume(), 0)        # moins d'un tour : pas libre


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestThread(unittest.TestCase):
    def test_rod(self):
        s = SO.threaded_rod(3, 4, 2, 20, 'M8')
        self.assertEqual(s.name, 'Tige filetée M8')
        b = s.bounds()
        self.assertAlmostEqual(b[3], 3 + 4.0, places=4)
        self.assertAlmostEqual(b[2], 2.0, places=6)
        self.assertAlmostEqual(b[5], 22.0, places=6)
        r = _radii(s, 3, 4, 5, 19)
        h = 1.25 * math.sqrt(3) / 2
        self.assertAlmostEqual(r.min(), 4 - 5 * h / 8, places=3)               # fond de filet ISO 68-1
        self.assertAlmostEqual(r.max(), 4.0, places=4)
        d2 = 8 - 0.6495 * 1.25                                                 # diamètre sur flancs
        self.assertAlmostEqual(s.volume() / (math.pi * (d2 / 2) ** 2 * 20), 1.0, delta=0.03)
        self.assertEqual(len(SO.components(s)), 1)
        lh = SO.threaded_rod(3, 4, 2, 20, 'M8', left=True)
        self.assertAlmostEqual(lh.volume(), s.volume(), places=3)
        plain = SO.threaded_rod(0, 0, 0, 20, 'M8x1', chamfer=False)
        self.assertEqual(plain.name, 'Tige filetée M8x1')
        self.assertGreater(plain.volume(), SO.threaded_rod(0, 0, 0, 20, 'M8x1').volume())

    def test_tapped(self):
        b = SO.box(0, 0, 0, 30, 30, 20)
        s = SO.tapped_hole(b, 15, 15, 'M8', 12)
        r = _radii(s, 15, 15, 9, 19, 6)
        self.assertAlmostEqual(r.min(), 3.375, delta=0.01)                     # perçage 6,75
        self.assertAlmostEqual(r.max(), 4.0, places=4)                         # filet jusqu'au nominal
        tip = s.verts[np.hypot(s.verts[:, 0] - 15, s.verts[:, 1] - 15) < 1e-6]
        self.assertAlmostEqual(tip[:, 2].min(), 20 - 14.5 - 3.375 / math.tan(math.radians(59)), places=4)
        self.assertGreater(b.volume() - s.volume(), math.pi * 3.375 ** 2 * 14.5)
        t = SO.tapped_hole(b, 15, 15, 'M8', 12, through=True)
        bottom = _radii(t, 15, 15, -1e-6, 1e-6, 6)
        self.assertAlmostEqual(bottom.min(), 3.375, delta=0.01)                # débouche dessous
        self.assertGreater(b.volume() - t.volume(), math.pi * 3.375 ** 2 * 20)
        with self.assertRaises(SO.SolidError):
            SO.tapped_hole(b, 15, 15, 'M7', 12)
        with self.assertRaises(SO.SolidError):
            SO._thread_groove(0, 0, 8, 1.25, 0, 10, 2.0, False)              # tige trop fine


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

    def circle(self, c, r):
        from vectordrive.core.document import Shape
        sh = Shape(path=Path([geom.circle(c, r)]))
        self.w.canvas.doc.add(sh)
        return sh

    def test_coil(self):
        w = self.w
        w.canvas.select([self.circle((50, 50), 15)])
        out = w.solid_coil({'size': 2.0, 'pitch': 4.0, 'turns': 3.0})
        self.assertEqual(len(out), 1)
        s = SO.of_item(out[0])
        self.assertAlmostEqual(s.bounds()[3], 50 + 16, delta=0.01)             # diamètre du cercle
        w.canvas.select([])
        self.assertEqual(len(w.solid_coil({'diameter': 10.0, 'size': 1.0, 'pitch': 2.0, 'turns': 2.0})), 1)
        self.assertEqual(w.solid_coil({'pitch': 1.0}), [])                     # se recoupe : message

    def test_thread(self):
        w, c = self.w, self.w.canvas
        c.select([self.circle((0, 0), 5)])
        out = w.solid_thread({'designation': '', 'length': 15.0})
        self.assertEqual(len(out), 1)
        self.assertIn('M10', out[0].name)
        c.select([])
        box = w.solid_primitive('box', {'dx': 40.0, 'dy': 40.0, 'dz': 15.0})
        b = SO.of_item(box[0]).bounds()
        hole = self.circle(((b[0] + b[3]) / 2, (b[1] + b[4]) / 2), 3.4)
        v0 = SO.of_item(box[0]).volume()
        c.select([box[0], hole])
        new = w.solid_thread({'mode': 'taraudage', 'designation': '', 'length': 10.0})
        self.assertEqual(len(new), 1)
        self.assertLess(SO.of_item(new[0]).volume(), v0 - math.pi * 3.375 ** 2 * 10)
        w.undo()
        self.assertTrue(any(SO.of_item(it) is not None and abs(SO.of_item(it).volume() - v0) < 1e-6
                            for it in c.doc.active_layer.items))
        c.select([])
        with mock.patch.object(w.statusBar(), 'showMessage') as sm:
            self.assertEqual(w.solid_thread({'mode': 'taraudage'}), [])        # pas de volume
            self.assertTrue(sm.called)

    def test_ribbon_icons(self):
        from vectordrive.ui import icons
        for k, a in (('coil', 'solid_coil'), ('thread', 'solid_thread')):
            self.assertIn(k, icons.ICONS)
            self.assertFalse(self.w.A[a].icon().isNull())
            self.assertTrue(self.w.A[a].toolTip())


if __name__ == '__main__':
    unittest.main()
