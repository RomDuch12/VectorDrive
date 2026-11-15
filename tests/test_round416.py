"""Round 416 : volume ↔ relief, STL lu comme volume."""
import math
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.core import solids as S

app = QApplication.instance() or QApplication([])


@unittest.skipUnless(S.available(), 'manifold3d absent')
class TestConversions(unittest.TestCase):
    def test_heights(self):
        H, x0, y1, res = S.heights([S.box(0, 0, 0, 10, 10, 4), S.cylinder(20, 5, 0, 3, 7)], 0.25, 1.0)
        self.assertAlmostEqual(x0, -1)
        self.assertAlmostEqual(y1, 11)
        col = lambda x: int((x - x0) / res)                      # noqa: E731
        row = lambda y: int((y1 - y) / res)                      # noqa: E731
        self.assertAlmostEqual(H[row(5), col(5)], 4)
        self.assertAlmostEqual(H[row(5), col(20)], 7)
        self.assertEqual(H[row(5), col(15)], 0)                  # entre les deux : le plan
        sph = S.heights([S.sphere(0, 0, 0, 10)], 0.2, 0.0)[0]
        self.assertAlmostEqual(sph.max(), 10, delta=0.05)

    def test_heightmap_roundtrip(self):
        H, x0, y1, res = S.heights([S.sphere(0, 0, 0, 10)], 0.2, 1.0)
        v = S.from_heightmap(H, x0, y1, res, floor=2.0)
        b = v.bounds()
        self.assertAlmostEqual(b[2], -2, places=4)
        self.assertAlmostEqual(b[5], 10, delta=0.05)
        expect = 2 / 3 * math.pi * 1000 + (b[3] - b[0]) * (b[4] - b[1]) * 2
        self.assertAlmostEqual(v.volume(), expect, delta=expect * 0.02)

    def test_from_triangles(self):
        b = S.box(0, 0, 0, 10, 10, 10)
        s = S.from_triangles(b.triangles()[:, ::-1])             # retournés : remis à l'endroit
        self.assertAlmostEqual(s.volume(), 1000, places=4)
        with self.assertRaises(S.SolidError):
            S.from_triangles(b.triangles()[:-1])                 # une face manque

    def test_window(self):
        from vectordrive.io import stl_write
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            sh = S.make_shape(S.box(0, 0, 0, 10, 10, 4))
            c.doc.add(sh)
            c.select([sh])
            img = w.solid_to_relief(params={'resolution': 0.25, 'margin': 1.0})
            self.assertIsNotNone(img)
            self.assertAlmostEqual(img.extra['galbe']['relief_depth'], 4, places=3)
            c.select([img])
            vols = w.relief_to_solid(params={'floor': 1.0, 'max_cells': 100_000})
            self.assertEqual(len(vols), 1)
            self.assertAlmostEqual(S.of_item(vols[0]).bounds()[5], 4, places=3)
            p = pathlib.Path(tempfile.mkdtemp()) / 'cube.stl'
            stl_write.write_stl(str(p), S.cylinder(0, 0, 0, 5, 5).triangles())
            got = w.solid_import(str(p))
            self.assertEqual(len(got), 1)
            self.assertEqual(got[0].name, 'cube')
            self.assertAlmostEqual(S.of_item(got[0]).volume(), S.cylinder(0, 0, 0, 5, 5).volume(), places=2)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
