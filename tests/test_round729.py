"""Round 729 : cellules (BOUNDARY FILL) — morceaux délimités par les volumes
choisis et vides qu'ils enferment, en volumes à part, d'après SolidCraft."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import solids as SO


def _box_and_lid():
    tray = SO.boolean('subtract', [SO.box(0, 0, 0, 40, 30, 20), SO.box(2, 2, 2, 36, 26, 20)])
    return tray, SO.box(0, 0, 20, 40, 30, 2)


@unittest.skipUnless(SO.available(), 'manifold3d absent')
class TestCells(unittest.TestCase):
    def test_pieces(self):
        a, b = SO.box(0, 0, 0, 10, 10, 10), SO.box(5, 0, 0, 10, 10, 10)
        cells = SO.boundary_cells([a, b])
        self.assertEqual(sorted(round(c.volume(), 6) for c in cells), [500.0, 500.0, 500.0])   # A-B, B-A, A∩B
        three = SO.boundary_cells([a, b, SO.box(0, 5, 0, 15, 10, 10)])
        self.assertAlmostEqual(sum(c.volume() for c in three), 225 * 10, places=4)                # la réunion
        self.assertEqual(len(three), 7)
        ring = SO.boolean('subtract', [SO.box(0, 0, 0, 30, 10, 5), SO.box(10, -1, -1, 10, 12, 7)])
        self.assertEqual(len(SO.boundary_cells([ring])), 2)                       # un morceau par corps

    def test_cavities(self):
        tray, lid = _box_and_lid()
        cav = SO.boundary_cells([tray, lid], pieces=False, cavities=True)
        self.assertEqual(len(cav), 1)
        self.assertAlmostEqual(cav[0].volume(), 36 * 26 * 18, places=4)
        self.assertEqual(cav[0].bounds(), (2.0, 2.0, 2.0, 38.0, 28.0, 20.0))
        both = SO.boundary_cells([tray, lid], cavities=True)
        self.assertEqual(len(both), 3)                                            # bac, couvercle, vide
        with self.assertRaises(SO.SolidError):
            SO.boundary_cells([tray], pieces=False, cavities=True)                 # bac ouvert : pas de vide fermé
        with self.assertRaises(SO.SolidError):
            SO.boundary_cells([])


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
        tray, lid = (SO.make_shape(s) for s in _box_and_lid())
        c.doc.add(tray)
        c.doc.add(lid)
        c.select([tray, lid])
        new = w.solid_cells({'mode': 'cavites', 'keep': True})
        self.assertEqual(len(new), 1)
        self.assertAlmostEqual(SO.of_item(new[0]).volume(), 16848.0, places=3)
        self.assertIn(tray, c.doc.active_layer.items)
        self.assertIn('16848.0', w.statusBar().currentMessage())
        c.select([tray, lid])
        new = w.solid_cells({'mode': 'morceaux', 'keep': False})
        self.assertEqual(len(new), 2)
        self.assertNotIn(lid, c.doc.active_layer.items)
        c.select([])
        self.assertEqual(w.solid_cells({}), [])

    def test_ribbon_icon(self):
        from vectordrive.ui import icons
        self.assertIn('cells', icons.ICONS)
        self.assertFalse(self.w.A['solid_cells'].icon().isNull())
        self.assertTrue(self.w.A['solid_cells'].toolTip())


if __name__ == '__main__':
    unittest.main()
