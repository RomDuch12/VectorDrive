"""Round 305 : TypeArt — balayage entre deux chemins (profil tendu du
premier au second, sens des chemins accordé), morphing entre deux profils,
hauteur proportionnelle à l'écart."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import galbe as GB, geom, sweep as SW
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])
ARCH = [(0, 0), (5, 4), (10, 0)]                    # profil : pointe de 4 mm au milieu
FLAT = [(0, 0), (0, 1), (10, 1), (10, 0)]           # profil plat de 1 mm


def at(img, x, y):
    H, x0, y1, res = GB.decode(img)
    return float(H[int((y1 - y) / res), int((x - x0) / res)])


class TestTwoRails(unittest.TestCase):
    def test_straight(self):
        a = [(0, 0), (40, 0)]
        b = [(40, 10), (0, 10)]                               # sens opposé : retourné
        img = SW.sweep_two(a, b, False, ARCH, SW.SweepSpec(resolution=0.1, margin=0))
        self.assertAlmostEqual(at(img, 20, 5), 4.0, 1)            # milieu de la section
        self.assertAlmostEqual(at(img, 20, 2.5), 2.0, 1)
        self.assertLess(at(img, 20, 0.2), 0.3)

    def test_widening_and_proportional(self):
        a = [(0, 0), (40, 0)]
        b = [(0, 10), (40, 20)]                               # écart 10 → 20
        spec = SW.SweepSpec(resolution=0.1, margin=0)
        img = SW.sweep_two(a, b, False, ARCH, spec)
        self.assertAlmostEqual(at(img, 39.5, 9.9), 4.0, 0)        # milieu, au bout large : même hauteur
        spec.proportional = True
        img = SW.sweep_two(a, b, False, ARCH, spec)
        self.assertAlmostEqual(at(img, 39.5, 9.9), 8.0, 0)        # deux fois plus large : deux fois plus haut

    def test_morph(self):
        a = [(0, 0), (40, 0)]
        b = [(0, 10), (40, 10)]
        img = SW.sweep_two(a, b, False, ARCH, SW.SweepSpec(resolution=0.1, margin=0), profile2_pts=FLAT)
        self.assertAlmostEqual(at(img, 0.3, 5), 4.0, 0)            # départ : arche
        self.assertAlmostEqual(at(img, 39.7, 5), 1.0, 0)           # arrivée : plat
        self.assertAlmostEqual(at(img, 20, 5), 2.5, 0)

    def test_closed_ring(self):
        outer = geom.circle((0, 0), 20).flatten(0.01)
        inner = geom.circle((0, 0), 10).flatten(0.01)[::-1]
        img = SW.sweep_two(outer, inner, True, ARCH, SW.SweepSpec(resolution=0.2, margin=0))
        self.assertAlmostEqual(at(img, 15, 0.3), 4.0, 0)           # couronne : arche au milieu
        self.assertAlmostEqual(at(img, -15, 0.3), 4.0, 0)
        self.assertLess(at(img, 0, 0), 0.01)                       # trou du milieu vide

    def test_command(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            items = [Shape(path=geom.Path([geom.polyline(p)])) for p in ([(0, 0), (40, 0)], [(0, 10), (40, 10)], ARCH)]
            for it in items:
                c.doc.add(it)
            c.select(items)
            img = w.typeart_sweep(SW.SweepSpec(kind='deux_chemins', resolution=0.2, margin=0))
            self.assertIsNotNone(img)
            self.assertAlmostEqual(img.extra['galbe']['relief_depth'], 4.0, 0)
            c.select(items[:2])
            self.assertIsNone(w.typeart_sweep(SW.SweepSpec(kind='deux_chemins')))
            self.assertIn('typeart_sweep_two', w.A)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
