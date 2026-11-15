"""Round 74 : décomposer, supprimer des contours."""
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import combine as C
from vectordrive.core import geom
from vectordrive.core.document import Shape
from vectordrive.core.geom import Contour, Line, Path


def nested():
    return Path([geom.rect(0, 0, 30, 30), geom.rect(5, 5, 20, 20), geom.rect(10, 10, 5, 5),
                 geom.circle((50, 0), 0.2), Contour([Line((60, 0), (70, 0))], False)])


class TestContours(unittest.TestCase):
    def test_depths(self):
        self.assertEqual(C.contour_depths(nested().contours), [0, 1, 2, 0, -1])

    def test_remove(self):
        p = nested()
        holes = C.remove_contours(p, 'holes')
        self.assertEqual(len(holes.contours), 4)                              # île gardée, trou retiré
        self.assertNotIn((5, 5, 25, 25), [tuple(round(v, 9) for v in c.bbox()) for c in holes.contours])
        outer = C.remove_contours(p, 'outer')
        self.assertEqual(len(outer.contours), 2)                              # le trou + le trait ouvert
        small = C.remove_contours(p, 'small', 1.0)
        self.assertEqual(len(small.contours), 4)                              # le cercle Ø0,4 est retiré

    def test_explode(self):
        parts = C.explode(Path([geom.rect(0, 0, 10, 5), Contour([Line((0, 0), (1, 0)), Line((1, 0), (1, 1))], False)]))
        self.assertEqual(len(parts), 6)
        self.assertTrue(all(len(p.contours) == 1 and not p.contours[0].closed for p in parts))
        # fermeture implicite rendue explicite
        tri = Contour([Line((0, 0), (1, 0)), Line((1, 0), (0, 1))], True)
        self.assertEqual(len(C.explode(Path([tri]))), 3)


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_explode_command(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            sq = Shape(path=Path([geom.rect(0, 0, 10, 10)]), tool=3)
            w._add_items([sq])
            w.canvas.select([sq])
            w.explode_items()
            items = list(w.canvas.doc.iter_items())
            self.assertEqual(len(items), 4)
            self.assertTrue(all(i.tool == 3 for i in items))
            w.undo()
            self.assertEqual(len(list(w.canvas.doc.iter_items())), 1)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
