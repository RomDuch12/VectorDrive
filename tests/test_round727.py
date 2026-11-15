"""Round 727 : échelle 3D (SCALE) des volumes, uniforme ou par axe, autour du
centre du dessous, du centre ou de l'origine, d'après SolidCraft."""
import os
import tempfile
import unittest

import numpy as np

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import solids as SO


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestScaling(unittest.TestCase):
    def test_matrix(self):
        m = SO.scaling(2, 3, 0.5, (10, 20, 0))
        self.assertTrue(np.allclose(m @ [10, 20, 0, 1], [10, 20, 0, 1]))          # point fixe
        self.assertTrue(np.allclose(m @ [11, 21, 4, 1], [12, 23, 2, 1]))
        s = SO.box(0, 0, 0, 10, 20, 5).transformed(SO.scaling(1.02, 1.02, 1.02, (5, 10, 0)))
        self.assertAlmostEqual(s.volume(), 1000 * 1.02 ** 3, places=6)
        self.assertEqual(tuple(round(v, 6) for v in s.bounds()), (-0.1, -0.2, 0.0, 10.1, 20.2, 5.1))
        for f in ((0, 1, 1), (1, -1, 1)):
            with self.assertRaises(SO.SolidError):
                SO.scaling(*f)


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
        w, c = self.w, self.w.canvas
        a = SO.make_shape(SO.box(0, 0, 2, 10, 10, 10))
        b = SO.make_shape(SO.box(30, 0, 0, 10, 10, 4))
        c.doc.add(a)
        c.doc.add(b)
        c.select([a, b])
        new = w.solid_scale3d({'factor': 1.0, 'per_axis': True, 'fx': 2.0, 'fy': 1.0, 'fz': 0.5,
                               'origin': 'dessous', 'together': False})
        self.assertEqual(len(new), 2)
        self.assertEqual(SO.of_item(new[0]).bounds(), (-5.0, 0.0, 2.0, 15.0, 10.0, 7.0))   # dessous fixe
        self.assertEqual(SO.of_item(new[1]).bounds(), (25.0, 0.0, 0.0, 45.0, 10.0, 2.0))
        c.select(new)
        new = w.solid_scale3d({'factor': 2.0, 'per_axis': False, 'origin': 'origine', 'together': True})
        self.assertEqual(SO.of_item(new[1]).bounds(), (50.0, 0.0, 0.0, 90.0, 20.0, 4.0))
        c.select(new)
        self.assertEqual(w.solid_scale3d({'factor': 0.0, 'per_axis': False, 'origin': 'centre',
                                          'together': True}), [])                  # facteur nul refusé
        c.select([])
        self.assertEqual(w.solid_scale3d({}), [])

    def test_ribbon_icon(self):
        from vectordrive.ui import icons
        self.assertIn('scale3d', icons.ICONS)
        self.assertFalse(self.w.A['solid_scale3d'].icon().isNull())
        self.assertTrue(self.w.A['solid_scale3d'].toolTip())


if __name__ == '__main__':
    unittest.main()
