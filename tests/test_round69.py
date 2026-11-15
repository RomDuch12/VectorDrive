"""Round 69 : dessin symétrique."""
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom
from vectordrive.core import symmetric as S
from vectordrive.core.geom import Contour, Cubic, Line, Path


class TestMirrorJoin(unittest.TestCase):
    def test_both_ends_on_axis_closes(self):
        half = Contour([Line((50, 0), (60, 0)), Cubic((60, 0), (70, 10), (55, 20), (58, 30)),
                        Line((58, 30), (50.0004, 30))], False)
        r = S.mirror_join(Path([half]), 50, 0.001)
        self.assertEqual(len(r.contours), 1)
        c = r.contours[0]
        self.assertTrue(c.closed)
        self.assertEqual(c.start, (50, 0))
        for s1, s2 in zip(c.segments, c.segments[1:] + c.segments[:1]):
            self.assertEqual(s1.end, s2.start)                        # continu, fermeture comprise
        bb = c.bbox()
        self.assertAlmostEqual(bb[0] + bb[2], 100, places=9)           # symétrique autour de x = 50

    def test_one_end_extends(self):
        arch = Contour([Cubic((50, 10), (52, 20), (60, 20), (65, 10))], False)
        r = S.mirror_join(Path([arch]), 50, 0.001)
        self.assertEqual(len(r.contours), 1)
        self.assertFalse(r.contours[0].closed)
        self.assertEqual((r.contours[0].start, r.contours[0].end), ((35, 10), (65, 10)))

    def test_far_and_closed_are_copied(self):
        r = S.mirror_join(Path([geom.circle((60, 0), 2), Contour([Line((70, 0), (80, 0))], False)]), 50)
        self.assertEqual(len(r.contours), 4)
        self.assertEqual([round(v, 9) for v in r.contours[1].bbox()], [38, -2, 42, 2])


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_symmetric_drawing(self):
        from vectordrive.core.document import Plate
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.canvas.doc.plate = Plate(width=100, height=50)
            w.A['sym_draw'].trigger()
            self.assertTrue(w.canvas.symmetric)
            self.assertEqual(w.canvas.symmetry_axis(), 50)
            w.canvas.commit_shape(Path([Contour([Line((50, 10), (70, 10)), Line((70, 10), (50, 30))], False)]))
            sh = w.canvas.selection[0]
            self.assertEqual(len(sh.path.contours), 1)
            self.assertTrue(sh.path.contours[0].closed)                 # losange refermé par son reflet
            self.assertEqual([round(v, 9) for v in sh.bbox()], [30, 10, 70, 30])
            w.A['sym_draw'].trigger()
            self.assertFalse(w.canvas.symmetric)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
