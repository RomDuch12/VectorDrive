"""Round 425 : volumes — réseau en Z."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import solids as S

app = QApplication.instance() or QApplication([])


@unittest.skipUnless(S.available(), 'manifold3d absent')
class TestArrayZ(unittest.TestCase):
    def test_stairs(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            step = S.make_shape(S.box(0, -2, 0, 20, 4, 2))
            c.doc.add(step)
            c.select([step])
            got = w.solid_array_z(params={'count': 4, 'step': 2.0, 'angle': 90.0})
            self.assertEqual(len(got), 4)
            zs = sorted(round(S.of_item(g).bounds()[2], 6) for g in got)
            self.assertEqual(zs, [0, 2, 4, 6])
            top = max(got, key=lambda g: S.of_item(g).bounds()[2])
            b = S.of_item(top).bounds()                                     # 3 × 90° : marche en long sur Y
            self.assertAlmostEqual(b[4] - b[1], 20, places=4)
            w.undo()
            self.assertEqual(len(c.doc.layers[0].items), 1)
            c.select(c.doc.layers[0].items)
            self.assertEqual(w.solid_array_z(params={'count': 1, 'step': 2.0, 'angle': 0.0}), [])
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
