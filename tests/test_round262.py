"""Round 262 : reliefs TypeArt dans la vue 3D (sommet affleurant, fond à
−profondeur) ; multicopie linéaire / circulaire et perlage dans le relief."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtWidgets import QApplication

from vectordrive.core import galbe as GB, geom, relief_ops as R, typeart as TA
from vectordrive.core.document import Document, Shape

app = QApplication.instance() or QApplication([])


class TestViewer(unittest.TestCase):
    def test_relief_in_3d(self):
        from vectordrive.cam import relief as RL
        d = Document()
        d.plate = None
        img = TA.dome([(10, 10)], TA.DomeSpec(diameter=10, height=2, margin=1, resolution=0.1))
        d.add(img)
        sim = RL.from_drawing(d, res=0.1)
        depth = img.extra['galbe']['relief_depth']
        self.assertAlmostEqual(sim.deepest, -depth, 1)                            # le fond, autour du dôme
        j = int(round((10 - sim.y0) / sim.res))
        i = int(round((10 - sim.x0) / sim.res))
        self.assertGreater(float(sim.H[j, i]), -0.05)                            # le sommet affleure


class TestCopies(unittest.TestCase):
    def test_placements(self):
        self.assertEqual(R.placements_linear(2, 2, 5, 3), [(5, 0, 0.0), (0, 3, 0.0), (5, 3, 0.0)])
        self.assertEqual([a for _x, _y, a in R.placements_circular(4)], [90.0, 180.0, 270.0])
        self.assertEqual([a for _x, _y, a in R.placements_circular(3, 90.0)], [45.0, 90.0])
        on = R.placements_on_curve([(0, 0), (10, 0)], (0, 0), 3)
        self.assertEqual([(x, y) for x, y, _a in on], [(0.0, 0.0), (5.0, 0.0), (10.0, 0.0)])

    def test_multicopy(self):
        H = np.zeros((100, 300))
        H[40:60, 10:30] = 2.0
        zone = H > 0
        out = R.multicopy(H, 0, 10, 0.1, zone, (2, 5), R.placements_linear(3, 1, 8, 0))
        self.assertEqual((out[50, 100], out[50, 180], out[50, 260]), (2.0, 2.0, 0.0))   # hors carte : perdu
        c = R.multicopy(H, 0, 10, 0.1, zone, (10, 5), R.placements_circular(2))
        self.assertEqual(c[50, 180], 2.0)                                        # demi-tour autour de (10, 5)

    def test_window(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            H = np.zeros((100, 300))
            H[40:60, 10:30] = 2.0
            img = GB.encode(H, 0.0, 10.0, 0.1, GB.GalbeSpec())
            zone = Shape(path=geom.Path([geom.rect(0.5, 3.5, 3, 3)]))
            line = Shape(path=geom.Path([geom.polyline([(2, 5), (26, 5)])]))
            for it in (img, zone, line):
                c.doc.add(it)
            c.select([img, zone, line])
            new = w.relief_copy('curve', {'count': 3, 'rotate': True})
            got, *_ = GB.decode(new)
            self.assertAlmostEqual(float(got[50, 140]), 2.0, 3)                  # au milieu de la courbe
            self.assertAlmostEqual(float(got[50, 250]), 2.0, 3)                  # au bout
            c.select([zone])
            self.assertIsNone(w.relief_copy('linear', {}))
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
