"""Round 207 : enrouler le dessin sur un cylindre ou un cône (aperçu de dessus)."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.cam import wrap as WR
from vectordrive.core import geom
from vectordrive.core.document import Shape


class TestWrapPath(unittest.TestCase):
    def test_line_and_limits(self):
        p = geom.Path([geom.Contour([geom.Line((-10, 2), (10, 2))], False)])
        w = WR.Wrap('cylindre_y', 20.0)
        out = WR.wrap_path(p, w)
        pts = [s.p0 for s in out.contours[0].segments] + [out.contours[0].segments[-1].p1]
        self.assertGreater(len(pts), 3)                                             # densifié
        self.assertAlmostEqual(pts[-1][0], 20 * math.sin(10 / 20))                  # serré vers les bords
        self.assertTrue(all(abs(y - 2) < 1e-9 for _x, y in pts))
        self.assertIsNone(WR.wrap_path(geom.Path([geom.rect(0, 0, 40, 5)]), WR.Wrap('cylindre_y', 20.0)))
        self.assertIsNone(WR.wrap_path(p, WR.Wrap('cylindre_y', 0.0)))
        cone = WR.wrap_path(geom.Path([geom.rect(-5, 0, 10, 50)]), WR.Wrap('cone_y', 10.0, radius2=20.0, length=50.0))
        b = cone.bbox()
        self.assertGreater(b[2], 20.0 * math.sin(0.5) - 1e-6)                       # plus large au grand rayon


class TestUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_action(self):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual((TE_ACTIONS['ID_CYLPROJ'], TE_ACTIONS['ID_CONPROJ']), ('wrap_drawing_cyl', 'wrap_drawing_cone'))
        w = MainWindow()
        try:
            sh = Shape(path=geom.Path([geom.rect(-8, -3, 16, 6)]))
            w.canvas.doc.add(sh)
            w.canvas.selection = [sh]
            new = w.wrap_drawing('cylindre', WR.Wrap('cylindre_y', 15.0))
            self.assertEqual(len(new), 1)
            self.assertIn(sh, list(w.canvas.doc.iter_leaves()))                       # original gardé
            self.assertLess(new[0].path.bbox()[2], 8.0)
            self.assertEqual(w.wrap_drawing('cylindre', WR.Wrap('cylindre_y', 3.0)), [])   # au-delà du quart de tour
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
