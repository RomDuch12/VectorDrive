"""Round 197 : galbe (TypeArt) — relief bombé en carte de hauteurs."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication
from shapely.geometry import Point, box

from vectordrive.cam import model, strategies as S
from vectordrive.core import galbe as GB, geom
from vectordrive.core.document import Document, Shape


class TestProfile(unittest.TestCase):
    def test_ends_and_monotonic(self):
        spec = GB.GalbeSpec(z_max=2.0, distance=4.0, start_angle=90.0, end_angle=0.0)
        z = GB.profile(spec, np.linspace(0, 6, 61))
        self.assertAlmostEqual(z[0], 0.0)
        self.assertAlmostEqual(z[40], 2.0)
        self.assertTrue(np.all(z[40:] == 2.0))                                     # plateau
        self.assertTrue(np.all(np.diff(z) >= -1e-12))
        self.assertGreater(GB.profile(spec, [0.4])[0], 0.4 * 2.0 / 4.0)            # 90° : monte vite au bord
        flat = GB.GalbeSpec(z_max=1.0, z_min=0.5, distance=2.0, start_angle=0.0, end_angle=0.0)
        self.assertAlmostEqual(GB.profile(flat, [0.0])[0], 0.5)

    def test_edt_exact(self):
        inside = np.zeros((9, 9), bool)
        inside[1:8, 1:8] = True
        d = GB._edt(inside)
        self.assertEqual(d[4, 4], 4.0)                                             # 4 pixels du bord
        self.assertEqual(d[1, 1], 1.0)
        self.assertEqual(d[0, 0], 0.0)


class TestMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_disc_dome(self):
        spec = GB.GalbeSpec(z_max=2.0, distance=5.0, resolution=0.1, margin=1.0)
        H, x0, y1, res = GB.heightmap(Point(0, 0).buffer(5.0, 64), spec)
        ny, nx = H.shape
        self.assertAlmostEqual(H.max(), 2.0, delta=0.05)                           # sommet au centre
        self.assertEqual(H[0, 0], 0.0)                                             # fond
        j, i = np.unravel_index(np.argmax(H), H.shape)
        self.assertAlmostEqual(x0 + (i + 0.5) * res, 0.0, delta=0.15)
        narrow = GB.heightmap(box(0, 0, 20, 2), spec)[0]
        self.assertLess(narrow.max(), 1.5)                                         # 1 mm du bord au plus

    def test_image_and_relief(self):
        spec = GB.GalbeSpec(z_max=1.5, distance=3.0, resolution=0.2, margin=1.0)
        reg = S.region([geom.Path([geom.rect(0, 0, 20, 10)]), geom.Path([geom.rect(5, 3, 4, 4)])], 0.01)
        img = GB.build_image(reg, spec)
        b = img.bbox()
        self.assertAlmostEqual(b[0], -1.0, delta=0.21)
        self.assertAlmostEqual(b[3], 11.0, delta=0.21)
        self.assertEqual(img.extra['galbe']['relief_depth'], 1.5)
        d = Document()
        d.plate = None
        d.add(img)
        s = model.CamSetup()
        t = model.CamTool(name='Boule', kind='boule', diameter=1.0, step_down=2.0, feed=800.0)
        s.tools = [t]
        op = model.Operation(kind='relief', tool_id=t.id, depth=1.5, resolution=0.5)
        s.operations = [op]
        tp = S.compute(d, s, op)
        zs = [m.z for m in tp.moves if m.kind == 'feed']
        self.assertAlmostEqual(min(zs), -1.5, delta=0.05)                          # fond à la profondeur
        self.assertGreater(max(zs), -0.2)                                          # sommets à la surface

    def test_action(self):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual(TE_ACTIONS['ID_GALBE_NEWGALBE'], 'galbe')
        w = MainWindow()
        try:
            sh = Shape(path=geom.Path([geom.circle((30, 30), 6)]))
            w.canvas.doc.add(sh)
            w.canvas.selection = [sh]
            img = w.galbe_dialog(GB.GalbeSpec(z_max=1.0, distance=3.0, resolution=0.2))
            self.assertIsNotNone(img)
            self.assertIn(img, list(w.canvas.doc.iter_leaves()))
            w.canvas.selection = []
            self.assertIsNone(w.galbe_dialog(GB.GalbeSpec()))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
