"""Round 479 : 3D — finesse réglable (grille calculée et surface affichée)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core.document import Shape
from vectordrive.core.geom import Path, rect

app = QApplication.instance() or QApplication([])


class TestFinesse(unittest.TestCase):
    def test_finesse(self):
        from vectordrive.ui import view3d as V
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.canvas.doc.add(Shape(path=Path([rect(10, 10, 60, 30)])))
            w.set_view_mode('3d')
            p3 = w.panel3d
            p3.source.setCurrentIndex(p3.source.findData('dessin'))
            n1 = p3.relief.sim.H.size
            p3.finesse.setCurrentIndex(p3.finesse.findData('fine'))
            self.assertEqual(w.settings.value(V.FINESSE_KEY), 'fine')
            self.assertEqual(p3.view.max_side, 900)
            self.assertGreater(p3.relief.sim.H.size, 3 * n1)                  # grille quatre fois plus fine
            strips, per = V.mesh(p3.relief.sim, max_side=p3.view.max_side)
            coarse, per0 = V.mesh(p3.relief.sim)
            self.assertGreater(strips.shape[0] * per, coarse.shape[0] * per0)
            self.assertLess(p3.minimumSizeHint().width(), 800)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
