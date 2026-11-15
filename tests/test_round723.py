"""Round 723 : pièces plastiques — lèvre ou rainure sur le bord d'une coque
(LIP, GROOVE), clip à crochet (SNAP FIT), appui (REST) — d'après
SolidCraft."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import solids as SO


def _tray():
    """Bac ouvert 40 × 30 × 20, parois et fond de 2."""
    return SO.boolean('subtract', [SO.box(0, 0, 0, 40, 30, 20), SO.box(2, 2, 2, 36, 26, 20)])


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestLip(unittest.TestCase):
    def test_lip_groove(self):
        t = _tray()
        v0 = t.volume()
        a = SO.lip(t, 1.0, 1.5)                                                   # contre l'arête intérieure
        self.assertAlmostEqual(a.volume() - v0, (38 * 28 - 36 * 26) * 1.5, delta=0.01)
        self.assertAlmostEqual(a.bounds()[5], 21.5)
        self.assertEqual(len(SO.components(a)), 1)
        g = SO.lip(t, 1.0, 1.5, groove=True, gap=0.2)                            # élargie et creusée du jeu
        self.assertAlmostEqual(v0 - g.volume(), (38.4 * 28.4 - 36 * 26) * 1.7, delta=0.01)
        self.assertAlmostEqual(g.bounds()[5], 20.0)
        o = SO.lip(t, 1.0, 1.5, outside=True)
        self.assertAlmostEqual(o.volume() - v0, (40 * 30 - 38 * 28) * 1.5, delta=0.01)
        og = SO.lip(t, 1.0, 1.5, groove=True, outside=True)
        self.assertAlmostEqual(v0 - og.volume(), (40 * 30 - 38 * 28) * 1.5, delta=0.01)
        closed = SO.box(0, 0, 0, 10, 10, 5)
        self.assertAlmostEqual(SO.lip(closed, 1.0, 1.0, outside=True).volume() - 500, 36.0, delta=0.01)
        for args, kw in (((closed, 1, 1), {}), ((t, 3, 1), {}), ((t, 0, 1), {}), ((t, 1, 1), {'groove': True, 'gap': -1}),
                         ((t, 1.9, 1), {'groove': True, 'gap': 0.2})):
            with self.assertRaises(SO.SolidError):
                SO.lip(*args, **kw)
        two = SO.boolean('subtract', [SO.box(0, 0, 0, 40, 20, 10), SO.box(2, 2, 2, 17, 16, 10),
                                      SO.box(21, 2, 2, 17, 16, 10)])
        with self.assertRaises(SO.SolidError):                                     # deux ouvertures semblables
            SO.lip(two, 0.5, 1.0)


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestSnapRest(unittest.TestCase):
    def test_snap_fit(self):
        s = SO.snap_fit(10, 20, 5, 12, 1.5, 6, 1, 3)
        self.assertEqual(s.bounds(), (9.25, 17.0, 5.0, 11.75, 23.0, 17.0))        # crochet vers +X
        self.assertAlmostEqual(s.volume(), (1.5 * 12 + 1 * 3 / 2) * 6, delta=1e-6)
        s = SO.snap_fit(10, 20, 5, 12, 1.5, 6, 1, 3, angle=90, base_height=2)
        b = s.bounds()
        self.assertAlmostEqual(b[4], 21.75, places=6)                             # crochet vers +Y
        self.assertAlmostEqual(b[2], 3.0, places=6)                               # pied 2 sous Z0
        self.assertGreater(SO.snap_fit(0, 0, 0, 12, 1.5, 6, 1, 3, join=True).volume(), 117.0)
        with self.assertRaises(SO.SolidError):
            SO.snap_fit(0, 0, 0, 3, 1.5, 6, 1, 3)                                 # crochet plus long que le bras
        with self.assertRaises(SO.SolidError):
            SO.snap_fit(0, 0, 0, 12, 0, 6, 1, 3)

    def test_rest(self):
        r = SO.rest(0, 0, 0, 6, 1)
        self.assertAlmostEqual(r.volume(), math.pi * 9, delta=0.3)
        self.assertEqual(r.bounds()[2:6:3], (0.0, 1.0))
        r = SO.rest(5, 5, 1, 6, 2, length=10, angle=90, draft=10)
        k = 2 * math.tan(math.radians(10))
        self.assertAlmostEqual(r.volume(), 2 / 6 * (60 + 4 * (10 - k) * (6 - k) + (10 - 2 * k) * (6 - 2 * k)),
                               delta=0.01)                                         # tronc de pyramide
        x0, y0, z0, x1, y1, z1 = r.bounds()
        self.assertAlmostEqual(x1 - x0, 6.0, places=4)                            # longueur tournée vers Y
        self.assertAlmostEqual(y1 - y0, 10.0, places=4)
        hollow = SO.rest(0, 0, 0, 10, 2, thickness=1.5)
        self.assertAlmostEqual(hollow.volume(), math.pi * (25 - 3.5 ** 2) * 2, delta=0.6)
        for kw in ({'thickness': 3.0}, {'draft': 60.0}, {'draft': 40.0, 'thickness': 1.0}, {'length': -1.0}):
            with self.assertRaises(SO.SolidError):
                SO.rest(0, 0, 0, 6, 2, **kw)


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

    def test_lip_action(self):
        w, c = self.w, self.w.canvas
        tray = SO.make_shape(_tray())
        c.doc.add(tray)
        c.select([tray])
        new = w.solid_lip({'mode': 'rainure', 'width': 1.0, 'height': 1.5, 'gap': 0.0, 'side': 'interieur'})
        self.assertEqual(len(new), 1)
        self.assertAlmostEqual(_tray().volume() - SO.of_item(new[0]).volume(), (38 * 28 - 36 * 26) * 1.5, delta=0.01)
        c.select([])
        self.assertEqual(w.solid_lip({}), [])

    def test_snap_rest_actions(self):
        from vectordrive.core import forms as F
        w, c = self.w, self.w.canvas
        plate = SO.make_shape(SO.box(0, 0, 0, 50, 30, 3))
        m1, m2 = F.make(F.Marker(cx=10.0, cy=10.0)), F.make(F.Marker(cx=40.0, cy=20.0))
        for it in (plate, m1, m2):
            c.doc.add(it)
        c.select([plate, m1, m2])
        new = w.solid_snap_fit({'length': 12.0, 'thickness': 1.5, 'width': 6.0, 'catch_depth': 1.0,
                                'catch_length': 3.0, 'angle': 0.0, 'base_height': 0.0, 'separate': False})
        self.assertEqual(len(new), 1)                                             # réunis à la plaque
        s = SO.of_item(new[0])
        self.assertEqual(len(SO.components(s)), 1)
        self.assertAlmostEqual(s.volume() - 4500, 2 * 117.0, delta=0.01)
        self.assertAlmostEqual(s.bounds()[5], 15.0)
        c.select([m1, m2])                                                        # sans volume : à part, à Z
        pads = w.solid_rest({'shape': 'rectangle', 'width': 4.0, 'length': 8.0, 'angle': 0.0, 'height': 1.0,
                             'draft': 0.0, 'thickness': 0.0, 'z': 5.0, 'separate': False})
        self.assertEqual(len(pads), 2)
        self.assertAlmostEqual(SO.of_item(pads[0]).volume(), 32.0, delta=1e-6)
        self.assertEqual(SO.of_item(pads[1]).bounds()[2], 5.0)
        c.select([plate])
        self.assertEqual(w.solid_rest({}), [])                                     # pas de marqueur

    def test_ribbon_icons(self):
        from vectordrive.ui import icons
        for k, a in (('lip', 'solid_lip'), ('snap_fit', 'solid_snap_fit'), ('rest_pad', 'solid_rest')):
            self.assertIn(k, icons.ICONS)
            self.assertFalse(self.w.A[a].icon().isNull())
            self.assertTrue(self.w.A[a].toolTip())


if __name__ == '__main__':
    unittest.main()
