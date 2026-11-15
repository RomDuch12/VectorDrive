"""Round 728 : ourlets (HEM) de la tôle pliée — retour à 180° vers la
matière au début ou à la fin de la chaîne, avec un jeu, compté dans le
développé — d'après SolidCraft."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import solids as SO
from vectordrive.core.geom import Path, polyline

L = polyline([(0, 0), (100, 0), (100, 50)])


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestHem(unittest.TestCase):
    def test_flat(self):
        ln0, _ = SO.sheet_flat(L, 2, 2, 0.44)
        ln, bends = SO.sheet_flat(L, 2, 2, 0.44, hems=(15, 20), gap=1)
        bh = math.pi * (0.5 + 0.44 * 2)
        self.assertAlmostEqual(ln, ln0 + 15 + 20 + 2 * bh)
        self.assertEqual([round(b[1]) for b in bends], [180, 90, 180])
        self.assertEqual(bends[0][2], 15.0)                                       # zone d'ourlet après son retour
        self.assertAlmostEqual(bends[-1][3], ln - 20)

    def test_solid(self):
        for hems, g in (((0, 20), 1.0), ((15, 20), 1.0), ((10, 0), 0.0)):
            s = SO.sheet(L, 2, 30, 2, hems=hems, gap=g)
            self.assertAlmostEqual(s.volume() / 60, SO.sheet_flat(L, 2, 2, 0.5, hems=hems, gap=g)[0], delta=0.15)
            self.assertEqual(len(SO.components(s)), 1)
        s = SO.sheet(L, 2, 30, 2, hems=(0, 20), gap=1)
        x0, y0, z0, x1, y1, z1 = s.bounds()
        self.assertAlmostEqual(y1, 52.5, delta=0.05)                              # pli d'ourlet : rayon 0,5 + 2
        r = SO.sheet(L, 2, 30, 2, left=False, hems=(15, 0), gap=1)                # matière à droite : vers -Y
        self.assertAlmostEqual(r.bounds()[1], -5.0)
        self.assertAlmostEqual(r.bounds()[0], -2.5, delta=0.05)

    def test_errors(self):
        for kw in ({'hems': (0, 60)}, {'hems': (-1, 0)}, {'hems': (0, 5), 'gap': -1}):
            with self.assertRaises(SO.SolidError):
                SO.sheet(L, 2, 30, 2, **kw)
        with self.assertRaises(SO.SolidError):                                    # un seul trait : retours croisés
            SO.sheet(polyline([(0, 0), (30, 0)]), 1, 10, 1, hems=(20, 20), gap=0.5)
        self.assertGreater(SO.sheet(polyline([(0, 0), (30, 0)]), 1, 10, 1, hems=(10, 10), gap=0.5).volume(), 0)


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

    def test_action(self):
        from vectordrive.core.document import Shape
        w, c = self.w, self.w.canvas
        line = Shape(path=Path([polyline([(0, 0), (100, 0), (100, 50)])]))
        c.doc.add(line)
        c.select([line])
        new = w.solid_sheet({'thickness': 2.0, 'height': 30.0, 'radius': 2.0, 'k_factor': 0.44, 'side': 'gauche',
                             'hem_start': 0.0, 'hem_end': 20.0, 'hem_gap': 1.0, 'z': 0.0, 'flat': True,
                             'delete': False})
        self.assertEqual(len(new), 3)
        x0, y0, x1, y1 = new[1].path.bbox()
        self.assertAlmostEqual(x1 - x0, SO.sheet_flat(L, 2, 2, 0.44, hems=(0, 20), gap=1)[0], places=6)
        self.assertEqual(len(new[2].path.contours), 2)                            # pli + ourlet


if __name__ == '__main__':
    unittest.main()
