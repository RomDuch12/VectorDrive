"""Round 203 : ajuster dans le cadre."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom
from vectordrive.core.document import Shape
from vectordrive.core.geom import Affine


class TestFit(unittest.TestCase):
    def test_affine_fit(self):
        m = Affine.fit((0, 0, 10, 5), (100, 100, 140, 120), margin=2.0)
        self.assertAlmostEqual(m.a, 3.2)                                           # 36 × 16 : la hauteur limite
        self.assertAlmostEqual(m.apply((0, 0))[0], 104.0)
        self.assertAlmostEqual(m.apply((10, 5))[0], 136.0)
        self.assertAlmostEqual((m.apply((0, 0))[1] + m.apply((10, 5))[1]) / 2, 110.0)   # centré
        s = Affine.fit((0, 0, 10, 5), (0, 0, 20, 20), stretch=True)
        self.assertEqual((s.a, s.d), (2.0, 4.0))
        line = Affine.fit((0, 0, 10, 0), (0, 0, 20, 8))                            # trait horizontal
        self.assertEqual(line.a, 2.0)
        with self.assertRaises(ValueError):
            Affine.fit((0, 0, 1, 1), (0, 0, 2, 2), margin=1.5)


class TestUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_action(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            logo = Shape(path=geom.Path([geom.circle((0, 0), 5)]))
            frame = Shape(path=geom.Path([geom.rect(50, 50, 30, 12)]))
            for it in (logo, frame):
                w.canvas.doc.add(it)
            w.canvas.selection = [frame, logo]
            out = w.fit_into_frame(1.0, False)
            b = out[0].bbox()
            self.assertAlmostEqual(b[3] - b[1], 10.0, places=4)                     # 12 − 2 × 1
            self.assertAlmostEqual((b[0] + b[2]) / 2, 65.0, places=4)
            self.assertEqual(frame.bbox(), (50.0, 50.0, 80.0, 62.0))                # le cadre ne bouge pas
            w.undo()
            self.assertIn(logo, list(w.canvas.doc.iter_leaves()))
            w.canvas.selection = [logo]
            self.assertEqual(w.fit_into_frame(1.0, False), [])                      # pas de cadre
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
