"""Round 267 : export STL — reliefs sur socle et formes fermées extrudées,
maillages étanches bien orientés, relus par le lecteur STL."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.core import galbe as GB, geom
from vectordrive.core.document import Shape
from vectordrive.io import mesh3d, stl_write as W

app = QApplication.instance() or QApplication([])


class TestMeshes(unittest.TestCase):
    def test_heightmap_watertight(self):
        H = np.zeros((50, 100))
        H[:, 50:] = 1.0
        t = W.heightmap_mesh(H, 0, 5, 0.1, base=1.0)
        self.assertAlmostEqual(W.volume(t), 9.9 * 4.9 * 1.0 + 4.9 * 4.9 * 1.0 + 0.05 * 4.9, 1)   # volume positif
        edges = {}
        for tri in np.round(t, 6):
            for i in range(3):
                e = tuple(sorted((tuple(tri[i]), tuple(tri[(i + 1) % 3]))))
                edges[e] = edges.get(e, 0) + 1
        self.assertTrue(all(v == 2 for v in edges.values()))                     # étanche
        self.assertEqual(len(W.heightmap_mesh(H, 0, 5, 0.1, stride=2)) < len(t), True)

    def test_extrude(self):
        import shapely
        sq = shapely.Polygon([(0, 0), (10, 0), (10, 10), (0, 10)], [[(3, 3), (3, 7), (7, 7), (7, 3)]])
        e = W.extrude_mesh(sq, 2.0)
        self.assertAlmostEqual(W.volume(e), (100 - 16) * 2.0, 6)
        f = os.path.join(tempfile.mkdtemp(), 'a.stl')
        self.assertEqual(W.write_stl(f, e), len(e))
        self.assertEqual(os.path.getsize(f), 84 + 50 * len(e))
        self.assertEqual(mesh3d.read(f).bbox(), (0.0, 0.0, 10.0, 10.0))


class TestCommand(unittest.TestCase):
    def test_export(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            img = GB.encode(np.ones((20, 20)), 0.0, 2.0, 0.1, GB.GalbeSpec())
            sq = Shape(path=geom.Path([geom.rect(5, 0, 4, 4)]))
            c.doc.add(img)
            c.doc.add(sq)
            c.select([img, sq])
            f = os.path.join(tempfile.mkdtemp(), 'b.stl')
            n = w.export_stl(f, {'base': 1.0, 'height': 2.0})
            self.assertGreater(n, 0)
            bb = mesh3d.read(f).bbox()
            self.assertAlmostEqual(bb[2], 9.0, 3)
            c.select([])
            self.assertEqual(w.export_stl(f, {}), 0)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
