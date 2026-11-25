"""Round 241 : F3 ouvre la fenêtre des accrochages (Maj+F3 : actif ou non) ;
accrochage aux quadrants des cercles et des arcs."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


class TestQuadrant(unittest.TestCase):
    def test_circle_and_arc(self):
        from vectordrive.core import geom
        from vectordrive.core.document import Shape
        from vectordrive.core.snap import Snap, _quadrants
        sh = Shape(path=geom.Path([geom.circle((10, 10), 5)]))
        sn = Snap(enabled=True, modes={'quadrant'})
        hit = sn.query(15.3, 10.2, 1.0, [sh])
        self.assertEqual(hit.kind, 'quadrant')
        self.assertAlmostEqual(hit.x, 15.0, 6)
        self.assertAlmostEqual(hit.y, 10.0, 6)
        self.assertIsNone(sn.query(13.5, 13.5, 0.5, [sh]))               # à 45° : pas un quadrant
        # arc de 0° à 120° : 0° et 90° seulement
        pts = _quadrants((0, 0), 2.0, 0.0, 120.0)
        self.assertEqual([(round(x, 6), round(y, 6)) for x, y in pts], [(2.0, 0.0), (0.0, 2.0)])
        pts = _quadrants((0, 0), 2.0, 10.0, -100.0)                       # sens horaire : de 10° à -90°
        self.assertEqual([(round(x, 6), round(y, 6)) for x, y in pts], [(2.0, 0.0), (0.0, -2.0)])


class TestSnapWindow(unittest.TestCase):
    def setUp(self):
        from vectordrive.ui.main_window import MainWindow
        self.w = MainWindow()

    def tearDown(self):
        self.w.modified = False
        self.w.close()

    def test_f3_window(self):
        w = self.w
        self.assertEqual(w.A['snap_window'].shortcut().toString(), 'F3')
        self.assertEqual(w.A['snap'].shortcut().toString(), 'Shift+F3')
        sw = w.snap_window()
        self.assertFalse(w.dock_snap.isHidden())                            # 0.920.0 : un panneau de colonne
        sw.enabled.setChecked(True)
        self.assertTrue(w.canvas.snap.enabled)
        sw.boxes['quadrant'].setChecked(True)
        self.assertIn('quadrant', w.canvas.snap.modes)
        w.A['snap_node'].setChecked(False)                                  # le ruban : la fenêtre suit
        self.assertFalse(sw.boxes['node'].isChecked())
        sw.set_modes(set())
        self.assertEqual(w.canvas.snap.modes, set())
        sw.set_modes({'grid'})
        self.assertEqual(w.canvas.snap.modes, {'grid'})
        sw.radius.setValue(15)
        self.assertEqual(w.canvas.snap_px, 15)
        self.assertEqual(int(w.settings.value('accrochage/rayon')), 15)
        w.snap_window()                                                     # F3 de nouveau : refermée
        self.assertTrue(w.dock_snap.isHidden())
        w.settings.setValue('accrochage/rayon', 8)
        w.settings.remove('options/tolerance')                              # round 1153 : le rayon l'écrit aussi


if __name__ == '__main__':
    unittest.main()
