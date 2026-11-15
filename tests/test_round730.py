"""Round 730 : plier une tôle plate le long de traits (SHEET FOLD), d'après
SolidCraft — zone de pli au facteur K, côté le plus petit relevé."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import solids as SO
from vectordrive.core.geom import Path, circle, polyline, rect

T, R = 2.0, 2.0
LINE = [((60, -5), (60, 55))]


def _plate():
    return Path([rect(0, 0, 100, 50)])


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestFold(unittest.TestCase):
    def test_one_fold(self):
        s = SO.sheet_fold(_plate(), LINE, T, R, 90, k_factor=0.5)
        ba = math.pi / 2 * (R + 0.5 * T)
        s0 = 60 - ba / 2                                                     # trait au milieu de la zone
        b = s.bounds()
        self.assertAlmostEqual(b[3], s0 + R + T, places=4)                   # face extérieure du rabat
        self.assertAlmostEqual(b[5], T + R + (100 - s0 - ba), places=4)      # rabat debout
        self.assertAlmostEqual(b[0], 0.0, places=6)
        self.assertAlmostEqual(b[2], 0.0, places=6)
        self.assertAlmostEqual(s.volume(), 100 * 50 * T, delta=100 * 50 * T * 1e-3)   # K = 0,5 : rien ne se perd
        self.assertEqual(len(s.manifold().decompose()), 1)

    def test_positions_and_down(self):
        ba = math.pi / 2 * (R + 0.44 * T)
        self.assertAlmostEqual(SO.sheet_fold(_plate(), LINE, T, R, 90, position='moule').bounds()[3], 60.0, places=4)
        self.assertAlmostEqual(SO.sheet_fold(_plate(), LINE, T, R, 90, position='debut').bounds()[3], 60 + R + T,
                               places=4)
        self.assertAlmostEqual(SO.sheet_fold(_plate(), LINE, T, R, 90, position='fin').bounds()[3], 60 - ba + R + T,
                               places=4)
        b = SO.sheet_fold(_plate(), LINE, T, R, 90, position='debut', down=True).bounds()
        self.assertAlmostEqual(b[2], -R - (100 - 60 - ba), places=4)        # rabat vers le bas
        self.assertAlmostEqual(b[5], T, places=6)
        b = SO.sheet_fold(_plate(), LINE, T, R, 180, k_factor=0.5).bounds()
        self.assertAlmostEqual(b[5], 2 * T + 2 * R, places=4)                # rabat rabattu à plat dessus
        self.assertAlmostEqual(SO.sheet_fold(_plate(), LINE, T, R, 90, z=5).bounds()[2], 5.0, places=6)

    def test_several_folds_and_holes(self):
        plate = Path([rect(0, 0, 120, 60), circle((60, 30), 8)])
        s = SO.sheet_fold(plate, [((30, -1), (30, 61)), ((90, 61), (90, -1))], T, R, 90, k_factor=0.5)
        b = s.bounds()
        self.assertAlmostEqual(b[0], 30 + math.pi / 4 * 3 - R - T, places=4)  # le côté le plus petit se lève
        self.assertAlmostEqual(b[3], 120 - b[0], places=4)
        self.assertAlmostEqual(s.volume(), (120 * 60 - math.pi * 64) * T, delta=20)
        self.assertEqual(len(s.manifold().decompose()), 1)
        ring = SO.sheet_fold(Path([rect(0, 0, 100, 60), rect(10, 10, 80, 40)]), [((70, -1), (70, 61))], T, R, 90,
                             k_factor=0.5)                                  # un trait, deux morceaux de pli
        self.assertEqual(len(ring.manifold().decompose()), 1)
        self.assertAlmostEqual(ring.volume(), (6000 - 3200) * T, delta=5)
        tabs = Path([polyline([(0, 0), (100, 0), (100, 80), (70, 80), (70, 30), (30, 30), (30, 80), (0, 80)],
                              closed=True)])
        s = SO.sheet_fold(tabs, [((-1, 55), (31, 55))], T, R, 90, k_factor=0.5)   # seul l'onglet traversé
        self.assertAlmostEqual(s.bounds()[4], 80.0, places=6)
        self.assertAlmostEqual(s.bounds()[5], T + R + 80 - 55 - math.pi / 4 * 3, places=4)
        cross = Path([polyline([(20, 0), (80, 0), (80, 20), (100, 20), (100, 60), (80, 60), (80, 80), (20, 80),
                                (20, 60), (0, 60), (0, 20), (20, 20)], closed=True)])
        edges = [((20, 20), (80, 20)), ((80, 60), (20, 60)), ((20, 20), (20, 60)), ((80, 20), (80, 60))]
        box = SO.sheet_fold(cross, edges, 1.5, 1.5, 90, position='debut')        # boîte : zones hors du fond
        self.assertEqual([round(v, 4) for v in box.bounds()[:5]], [17.0, 17.0, 0.0, 83.0, 63.0])
        self.assertEqual(len(box.manifold().decompose()), 1)
        with self.assertRaises(SO.SolidError):                               # au milieu : les coins se chevauchent
            SO.sheet_fold(cross, edges, 1.5, 1.5, 90)

    def test_errors(self):
        for lines, kw in (([((60, 60), (60, 80))], {}), (LINE + [((61, -5), (61, 55))], {}),
                          (LINE + [((-5, 25), (105, 25))], {}), ([((99, -5), (99, 55))], {}), ([], {}),
                          (LINE, {'radius': 0}), (LINE, {'angle': 0}), (LINE, {'angle': 200}),
                          (LINE, {'position': 'x'}), (LINE, {'angle': 180, 'position': 'moule'})):
            a = {'thickness': T, 'radius': R, 'angle': 90}
            a.update(kw)
            with self.assertRaises(SO.SolidError):
                SO.sheet_fold(_plate(), lines, **a)
        with self.assertRaises(SO.SolidError):                               # flan en deux morceaux
            SO.sheet_fold(Path([rect(0, 0, 10, 10), rect(20, 0, 10, 10)]), [((5, -1), (5, 11))], T, R)


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
        plate = Shape(path=_plate(), name='flan')
        line = Shape(path=Path([polyline([(60, -5), (60, 55)])]), name='pli')
        c.doc.add(plate)
        c.doc.add(line)
        c.select([plate, line])
        new = w.solid_fold({'thickness': T, 'radius': R, 'angle': 90, 'k_factor': 0.5, 'position': 'axe',
                            'direction': 'haut', 'z': 0, 'delete': False})
        self.assertEqual(len(new), 1)
        self.assertAlmostEqual(SO.of_item(new[0]).volume(), 10000, delta=10)
        self.assertIn(plate, c.doc.active_layer.items)
        self.assertIn('1', w.statusBar().currentMessage())
        c.select([plate, line])
        new = w.solid_fold({'thickness': T, 'radius': R, 'angle': 90, 'k_factor': 0.5, 'position': 'axe',
                            'direction': 'bas', 'z': 0, 'delete': True})
        self.assertLess(SO.of_item(new[0]).bounds()[2], -30)
        self.assertNotIn(plate, c.doc.active_layer.items)
        self.assertNotIn(line, c.doc.active_layer.items)
        c.select([])
        self.assertEqual(w.solid_fold({}), [])

    def test_ribbon_icon(self):
        from vectordrive.ui import icons
        self.assertIn('sheet_fold', icons.ICONS)
        self.assertFalse(self.w.A['solid_fold'].icon().isNull())
        self.assertTrue(self.w.A['solid_fold'].toolTip())


if __name__ == '__main__':
    unittest.main()
