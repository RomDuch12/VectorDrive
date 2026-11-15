"""Round 720 : nervure (RIB / WEB) et bossage plastique (BOSS), posés sur le
dessus de la matière, d'après SolidCraft."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import geom
from vectordrive.core import solids as SO
from vectordrive.core.geom import Contour, Line, Path


def _tray():
    """Bac 60 × 40 × 20, fond et parois de 2 mm, ouvert dessus."""
    return SO.shell(SO.box(0, 0, 0, 60, 40, 20), 2.0, open_top=True)


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestTopAt(unittest.TestCase):
    def test_top_at(self):
        t = _tray()
        self.assertAlmostEqual(SO.top_at(t, 30, 20), 2.0, places=4)              # le fond du bac
        self.assertAlmostEqual(SO.top_at(t, 1, 20), 20.0, places=4)              # le haut d'une paroi
        self.assertIsNone(SO.top_at(t, 100, 20))


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestRib(unittest.TestCase):
    def test_rib(self):
        t = _tray()
        line = Contour([Line((30, 10), (30, 30))])                               # à prolonger
        r = SO.rib(t, line, 2.0)
        self.assertAlmostEqual(r.volume() - t.volume(), 2 * 36 * 18, delta=1.0)  # de paroi à paroi, fond à haut
        self.assertEqual(r.bounds(), t.bounds())
        self.assertEqual(len(SO.components(r)), 1)
        low = SO.rib(t, line, 2.0, top=12.0)
        self.assertAlmostEqual(low.volume() - t.volume(), 2 * 36 * 10, delta=1.0)
        short = SO.rib(t, line, 2.0, extend=False)
        self.assertAlmostEqual(short.volume() - t.volume(), 2 * 20 * 18, delta=1.0)
        web = SO.rib(r, Contour([Line((10, 20), (50, 20))]), 1.5)              # croise la première
        self.assertAlmostEqual(web.volume() - r.volume(), 1.5 * 56 * 18 - 1.5 * 2 * 18, delta=1.5)
        with self.assertRaises(SO.SolidError):
            SO.rib(t, line, 0.0)
        with self.assertRaises(SO.SolidError):
            SO.rib(t, line, 2.0, top=-5.0)
        with self.assertRaises(SO.SolidError):
            SO.rib(t, Contour([Line((100, 100), (120, 100))]), 2.0, extend=False)


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestBoss(unittest.TestCase):
    def test_boss(self):
        t = _tray()
        b = SO.boss(t, 30, 20, 8.0, 10.0)
        self.assertAlmostEqual(b.volume() - t.volume(), math.pi * 16 * 10, delta=1.0)
        self.assertAlmostEqual(b.bounds()[5], 20.0, places=6)                    # fond à 2 + 10 < 20
        tall = SO.boss(t, 30, 20, 8.0, 25.0)
        self.assertAlmostEqual(tall.bounds()[5], 27.0, places=4)                 # posé sur le fond
        holed = SO.boss(t, 30, 20, 8.0, 10.0, hole_diameter=3.0, hole_depth=6.0, draft=1.0)
        r_top = 4 - 10 * math.tan(math.radians(1.0))
        cone = math.pi * 10 / 3 * (16 + 4 * r_top + r_top ** 2)
        self.assertAlmostEqual(holed.volume() - t.volume(), cone - math.pi * 2.25 * 6, delta=1.0)
        ribbed = SO.boss(t, 30, 20, 8.0, 10.0, ribs=4, rib_offset=2.0)
        extra = 4 * 1.2 * 4.0 * 8                                                 # hors du fût : 4 × 1,2 × 4 × 8
        self.assertGreater(ribbed.volume() - b.volume(), 0.95 * extra)
        self.assertLess(ribbed.volume() - b.volume(), 1.05 * extra)
        on_plane = SO.boss(SO.box(0, 0, 0, 20, 20, 5), 10, 10, 6.0, 4.0, z0=5.0)
        self.assertAlmostEqual(on_plane.bounds()[5], 9.0, places=6)
        for kw in ({'draft': 30.0}, {'ribs': 100}, {'hole_diameter': 9.0}):
            with self.assertRaises(SO.SolidError):
                SO.boss(t, 30, 20, 8.0, 10.0, **kw)


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

    def add(self, contour):
        from vectordrive.core.document import Shape
        sh = Shape(path=Path([contour]))
        self.w.canvas.doc.add(sh)
        return sh

    def test_rib_boss(self):
        from vectordrive.core.document import Shape
        w, c = self.w, self.w.canvas
        tray = SO.make_shape(_tray())
        c.doc.add(tray)
        v0 = SO.of_item(tray).volume()
        line = self.add(Contour([Line((30, 10), (30, 30))]))
        c.select([tray, line])
        new = w.solid_rib({'thickness': 2.0})
        self.assertEqual(len(new), 1)
        self.assertAlmostEqual(SO.of_item(new[0]).volume() - v0, 2 * 36 * 18, delta=1.0)
        self.assertNotIn(line, c.doc.active_layer.items)                          # traits retirés
        v1 = SO.of_item(new[0]).volume()
        spots = [self.add(geom.circle((15, 20), 3.0)), self.add(geom.circle((45, 20), 3.0))]
        c.select([new[0]] + spots)
        bossed = w.solid_boss({'height': 8.0, 'hole_diameter': 2.0, 'draft': 0.0})
        self.assertEqual(len(bossed), 1)
        self.assertAlmostEqual(SO.of_item(bossed[0]).volume() - v1, 2 * math.pi * (9 - 1) * 8, delta=1.0)
        c.select(spots)
        self.assertEqual(w.solid_boss({}), [])
        self.assertEqual(w.solid_rib({}), [])
        self.assertTrue(all(isinstance(it, Shape) for it in bossed))

    def test_ribbon_icons(self):
        from vectordrive.ui import icons
        for k, a in (('rib', 'solid_rib'), ('boss', 'solid_boss')):
            self.assertIn(k, icons.ICONS)
            self.assertFalse(self.w.A[a].icon().isNull())
            self.assertTrue(self.w.A[a].toolTip())


if __name__ == '__main__':
    unittest.main()
