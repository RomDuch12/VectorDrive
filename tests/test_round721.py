"""Round 721 : relief ou gravure d'un dessin enroulé sur un volume
cylindrique couché (EMBOSS sur cylindre), d'après SolidCraft."""
import math
import os
import tempfile
import unittest

import numpy as np

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import solids as SO
from vectordrive.core.geom import Path, rect


def _rod(axis='x'):
    """Cylindre couché de rayon 10, long de 60, axe à Z = 0."""
    if axis == 'x':
        return SO.revolve(Path([rect(0, 0, 60, 10)]), ((0, 0), (1, 0)))
    return SO.revolve(Path([rect(0, 0, 10, 60)]), ((0, 0), (0, 1)))


def _sector(length, width, r0, r1):
    return length * (width / 10.0) * (r1 ** 2 - r0 ** 2) / 2


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestWrap(unittest.TestCase):
    def test_lying_cylinder(self):
        self.assertEqual(SO.lying_cylinder(_rod('x')), ('x', (0.0, 0.0), 10.0))
        axis, (c, zc), r = SO.lying_cylinder(_rod('y'))
        self.assertEqual(axis, 'y')
        self.assertAlmostEqual(r, 10.0)
        self.assertIsNone(SO.lying_cylinder(SO.box(0, 0, 0, 10, 20, 5)))

    def test_emboss_deboss(self):
        rod = _rod('x')
        p = Path([rect(20, -3, 20, 6)])
        e = SO.wrap_emboss(rod, p, 1.0)
        self.assertAlmostEqual(e.volume() - rod.volume(), _sector(20, 6, 10, 11), delta=1.0)
        self.assertAlmostEqual(e.bounds()[5], 11.0, places=4)
        V = e.verts[(e.verts[:, 0] > 21) & (e.verts[:, 0] < 39)]
        self.assertLessEqual(np.hypot(V[:, 1], V[:, 2]).max(), 11.0 + 1e-6)     # posé sur le pourtour
        g = SO.wrap_emboss(rod, p, 1.0, deboss=True)
        self.assertAlmostEqual(rod.volume() - g.volume(), _sector(20, 6, 9, 10), delta=1.0)
        self.assertEqual(len(SO.components(e)), 1)
        y = _rod('y')
        ey = SO.wrap_emboss(y, Path([rect(-3, 20, 6, 20)]), 1.0)
        self.assertAlmostEqual(ey.volume() - y.volume(), _sector(20, 6, 10, 11), delta=1.0)
        side = SO.wrap_emboss(rod, Path([rect(20, 8, 10, 4)]), 0.5)              # loin de la ligne de dessus
        V = side.verts[np.hypot(side.verts[:, 1], side.verts[:, 2]) > 10.2]
        th = np.arctan2(V[:, 1], V[:, 2])                                         # depuis le dessus vers +Y
        self.assertAlmostEqual(th.min(), 0.8, delta=0.01)                          # arc = écart / rayon
        self.assertAlmostEqual(th.max(), 1.2, delta=0.01)

    def test_errors(self):
        rod = _rod('x')
        p = Path([rect(20, -3, 20, 6)])
        with self.assertRaises(SO.SolidError):
            SO.wrap_emboss(SO.box(0, 0, 0, 10, 20, 5), p, 1.0)                     # pas un cylindre
        with self.assertRaises(SO.SolidError):
            SO.wrap_emboss(rod, Path([rect(20, -40, 10, 80)]), 1.0)                # plus d'un demi-tour
        with self.assertRaises(SO.SolidError):
            SO.wrap_emboss(rod, p, 10.0, deboss=True)
        with self.assertRaises(SO.SolidError):
            SO.wrap_emboss(rod, p, 0.0)
        self.assertGreater(SO.wrap_emboss(SO.box(0, -10, -10, 60, 20, 20), p, 1.0, axis='x').volume(), 0)


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
        from vectordrive.core.document import Shape, Text
        w, c = self.w, self.w.canvas
        rod = SO.make_shape(_rod('x'))
        c.doc.add(rod)
        v0 = SO.of_item(rod).volume()
        shape = Shape(path=Path([rect(10, -3, 10, 6)]))
        text = Text(text='I', outline=Path([rect(40, -2, 4, 4)]))
        c.doc.add(shape)
        c.doc.add(text)
        c.select([rod, shape, text])
        new = w.solid_wrap_emboss({'depth': 1.0, 'mode': 'gravure', 'delete': True})
        self.assertEqual(len(new), 1)
        removed = _sector(10, 6, 9, 10) + _sector(4, 4, 9, 10)
        self.assertAlmostEqual(v0 - SO.of_item(new[0]).volume(), removed, delta=1.0)
        self.assertNotIn(text, c.doc.active_layer.items)
        c.select([new[0]])
        self.assertEqual(w.solid_wrap_emboss({}), [])                             # rien à enrouler

    def test_ribbon_icon(self):
        from vectordrive.ui import icons
        self.assertIn('wrap_emboss', icons.ICONS)
        self.assertFalse(self.w.A['solid_wrap_emboss'].icon().isNull())
        self.assertTrue(self.w.A['solid_wrap_emboss'].toolTip())


if __name__ == '__main__':
    unittest.main()
