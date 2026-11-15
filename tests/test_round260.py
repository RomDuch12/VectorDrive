"""Round 260 : TypeArt — balayage simple (cadre : intérieur ou extérieur
selon le sens du chemin, coins aigus / chanfreinés / arrondis) et tube."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import galbe as GB, geom, sweep as SW
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])
PROF = [(0, 0), (0, 2), (1, 3), (3, 3), (4, 1.5), (5, 0)]          # moulure de 5 mm, 3 mm de haut
SQUARE = [(0, 0), (40, 0), (40, 30), (0, 30)]                      # sens trigonométrique


def at(img, x, y):
    H, x0, y1, res = GB.decode(img)
    return float(H[int((y1 - y) / res), int((x - x0) / res)])


class TestProfile(unittest.TestCase):
    def test_envelope_and_table(self):
        import numpy as np
        e = SW.envelope([(0, 0), (2, 2), (4, 0), (0, 0)], np.array([1.0, 2.0, 5.0]))
        self.assertAlmostEqual(e[0], 1.0)
        self.assertAlmostEqual(e[1], 2.0)
        self.assertTrue(math.isnan(e[2]))
        x, h = SW.profile_table([(10, 5), (12, 8), (15, 5)], 0.5)
        self.assertAlmostEqual(x[-1], 5.0)
        self.assertAlmostEqual(float(h.max()), 3.0)


class TestSweep(unittest.TestCase):
    def test_inside_outside_by_direction(self):
        spec = SW.SweepSpec(resolution=0.1, margin=0)
        inner = SW.sweep(SQUARE, True, PROF, spec)
        self.assertAlmostEqual(at(inner, 20, 2.05), 3.0, 1)                    # 2 mm dans le cadre
        self.assertAlmostEqual(at(inner, 20, 15), 0.0, 3)                      # le milieu reste au fond
        outer = SW.sweep(list(reversed(SQUARE)), True, PROF, spec)
        self.assertAlmostEqual(at(outer, 20, -2.05), 3.0, 1)                   # sens horaire : dehors
        self.assertAlmostEqual(at(outer, 20, 2.0), 0.0, 3)

    def test_corners(self):
        out = {c: SW.sweep(list(reversed(SQUARE)), True, PROF, SW.SweepSpec(corners=c, resolution=0.1, margin=0))
               for c in ('aigu', 'chanfrein', 'arrondi')}
        # près du coin extérieur (−4, −4) : seul le coin aigu y met de la matière
        self.assertGreater(at(out['aigu'], -3.95, -3.95), 0.5)
        self.assertEqual(at(out['arrondi'], -3.95, -3.95), 0.0)
        self.assertEqual(at(out['chanfrein'], -3.95, -3.95), 0.0)
        self.assertGreater(at(out['chanfrein'], -2.0, -2.0), 0.5)
        with self.assertRaises(ValueError):
            SW.sweep(SQUARE, False, PROF, SW.SweepSpec())

    def test_tube(self):
        prof = [(0, 0), (2, 2), (4, 0)]
        img = SW.sweep([(0, 0), (30, 0)], False, prof, SW.SweepSpec(kind='tube', resolution=0.05, margin=0))
        self.assertAlmostEqual(at(img, 15, 0.02), 2.0, 1)
        self.assertAlmostEqual(at(img, 15, 1.0), 1.0, 1)
        self.assertAlmostEqual(at(img, 15, -1.0), 1.0, 1)


class TestWindow(unittest.TestCase):
    def test_sweep_command(self):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui import shortcuts as SC
        w = MainWindow()
        try:
            c = w.canvas
            path = Shape(path=geom.Path([geom.polyline(SQUARE, closed=True)]))
            prof = Shape(path=geom.Path([geom.polyline(PROF)]))
            c.doc.add(path)
            c.doc.add(prof)
            c.select([path, prof])
            img = w.typeart_sweep(SW.SweepSpec(resolution=0.2, margin=0))
            self.assertIsNotNone(img)
            self.assertAlmostEqual(img.extra['galbe']['relief_depth'], 3.0, 1)
            c.select([prof, path])                                                  # profil ouvert d'abord
            self.assertIsNone(w.typeart_sweep(SW.SweepSpec(), kind='simple'))
            self.assertEqual(SC.TE_ACTIONS['ID_TART_TUBE_SWEEPING'], 'typeart_sweep_tube')
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
