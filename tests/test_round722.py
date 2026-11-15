"""Round 722 : profilés (FRAME MEMBER) — plat, rond, tubes, cornière, U, I —
couchés le long des traits ou en poteaux sur les marqueurs, d'après
SolidCraft."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import solids as SO
from vectordrive.core.geom import Contour, Line, Path, polyline


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestProfiles(unittest.TestCase):
    def area(self, kind, *dims):
        return abs(SO.region(SO.profile_path(kind, *dims)).area())

    def test_sections(self):
        self.assertAlmostEqual(self.area('plat', 40, 10), 400.0)
        self.assertAlmostEqual(self.area('rond', 20) / (math.pi * 100), 1.0, delta=0.002)
        self.assertAlmostEqual(self.area('tube_rect', 40, 30, 3), 1200 - 34 * 24)
        self.assertAlmostEqual(self.area('tube_rond', 42.4, 0, 3.2) / (math.pi * (21.2 ** 2 - 18 ** 2)), 1.0,
                               delta=0.002)
        self.assertAlmostEqual(self.area('corniere', 50, 50, 5), 50 * 5 + 45 * 5)
        self.assertAlmostEqual(self.area('u', 50, 100, 8, 6), 2 * 50 * 8 + 6 * 84)
        self.assertAlmostEqual(self.area('i', 50, 100, 7, 4.5), 2 * 50 * 7 + 4.5 * 86)
        for k in SO.PROFILES:                                                    # centrées sur l'encombrement
            x0, y0, x1, y1 = SO.profile_path(k, 40, 30, 3).bbox()
            self.assertAlmostEqual(x0 + x1, 0.0)
            self.assertAlmostEqual(y0 + y1, 0.0)
        for args in (('tube_rect', 40, 30, 15), ('i', 40, 30, 3, 40), ('plat', 0, 10), ('x', 10, 10, 1)):
            with self.assertRaises(SO.SolidError):
                SO.profile_path(*args)

    def test_member_post(self):
        m = SO.member(Contour([Line((0, 0), (100, 0))]), 'i', 50, 100, 7, 4.5)
        self.assertAlmostEqual(m.volume(), (2 * 50 * 7 + 4.5 * 86) * 100, delta=1.0)
        self.assertEqual(m.bounds(), (0.0, -25.0, 0.0, 100.0, 25.0, 100.0))       # couché sur le plan
        c = SO.member(Contour([Line((0, 0), (100, 0))]), 'rond', 20, z=50.0, on_plane=False)
        self.assertAlmostEqual(c.bounds()[2], 40.0, places=4)                     # centré à Z
        frame = SO.member(polyline([(0, 0), (200, 0), (200, 100), (0, 100)], closed=True), 'tube_rect', 40, 40, 3)
        self.assertAlmostEqual(frame.volume(), (1600 - 34 ** 2) * 600, delta=2.0)  # onglets : longueur sur l'axe
        self.assertEqual(frame.bounds()[:3], (-20.0, -20.0, 0.0))
        p = SO.post(10, 10, 5, 50, 'corniere', 30, 30, 3, angle=45)
        self.assertAlmostEqual(p.volume(), (30 * 3 + 27 * 3) * 50, delta=0.5)
        self.assertEqual((p.bounds()[2], p.bounds()[5]), (5.0, 55.0))
        with self.assertRaises(SO.SolidError):
            SO.post(0, 0, 0, 0, 'plat', 10, 10)


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
        from vectordrive.core import forms as F
        from vectordrive.core.document import Shape
        w, c = self.w, self.w.canvas
        line = Shape(path=Path([polyline([(0, 0), (100, 0), (100, 60)])]))
        c.doc.add(line)
        marker = F.make(F.Marker(cx=30.0, cy=30.0))
        c.doc.add(marker)
        c.select([line, marker])
        out = w.solid_frame({'kind': 'corniere', 'width': 30.0, 'height': 30.0, 'thickness': 3.0, 'length': 80.0,
                             'delete': True})
        self.assertEqual(len(out), 2)
        member, post = (SO.of_item(it) for it in out)
        gx = (30 * 3 * 15 + 27 * 3 * 1.5) / 171 - 15                              # centre de la cornière
        self.assertAlmostEqual(member.volume(), 171 * (160 - 2 * gx), delta=2.0)   # onglet : longueur au centre
        self.assertAlmostEqual(post.bounds()[5], 80.0, places=6)
        self.assertNotIn(line, c.doc.active_layer.items)
        c.select([])
        self.assertEqual(w.solid_frame({}), [])

    def test_ribbon_icon(self):
        from vectordrive.ui import icons
        self.assertIn('frame', icons.ICONS)
        self.assertFalse(self.w.A['solid_frame'].icon().isNull())
        self.assertTrue(self.w.A['solid_frame'].toolTip())


if __name__ == '__main__':
    unittest.main()
