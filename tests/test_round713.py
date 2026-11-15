"""Round 713 : Raccord en courbe (comme BLEND en DAO, d'après CADCraft) —
courbe tangente ou lisse entre les bouts les plus proches de deux traits
ouverts (ou les deux bouts d'un trait), jointe ou à part, annulable."""
import math
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from vectordrive.core import blend as B
from vectordrive.core.geom import Contour, Line, Path


def _dir(a, b):
    n = math.dist(a, b)
    return ((b[0] - a[0]) / n, (b[1] - a[1]) / n)


def _curv0(s):
    """Courbure d'une Bézier à son départ."""
    (x0, y0), (x1, y1), (x2, y2) = s.controls()[:3]
    d1 = (3 * (x1 - x0), 3 * (y1 - y0))
    d2 = (6 * (x2 - 2 * x1 + x0), 6 * (y2 - 2 * y1 + y0))
    return abs(d1[0] * d2[1] - d1[1] * d2[0]) / math.hypot(*d1) ** 3


class TestCore(unittest.TestCase):
    a = Contour([Line((0, 0), (20, 0))], False)
    b = Contour([Line((50, 20), (30, 20))], False)

    def test_tangent(self):
        c = B.curve_bridge((20, 0), (1, 0), (30, 20), (-1, 0))
        s = c.segments[0]
        self.assertEqual(len(c.segments), 1)
        d = math.dist((20, 0), (30, 20))
        self.assertAlmostEqual(s.p1[0] - 20, d / 3)                               # poignées au tiers
        self.assertAlmostEqual(s.p1[1], 0.0)
        self.assertAlmostEqual(30 - s.p2[0], d / 3)
        self.assertIsNone(B.curve_bridge((1, 1), (1, 0), (1, 1), (0, 1)))

    def test_smooth(self):
        c = B.curve_bridge((20, 0), (1, 0), (30, 20), (-1, 0), smooth=True)
        segs = c.segments
        self.assertGreater(len(segs), 1)
        self.assertEqual((segs[0].start, segs[-1].end), ((20, 0), (30, 20)))     # bouts exacts
        self.assertAlmostEqual(_dir(segs[0].start, segs[0].p1)[1], 0.0)          # part dans le prolongement
        self.assertAlmostEqual(_dir(segs[-1].p2, segs[-1].end)[1], 0.0)
        for s, t in zip(segs, segs[1:]):                                         # jonctions sans coin
            self.assertEqual(s.end, t.start)
            u, v = _dir(s.p2, s.end), _dir(t.start, t.p1)
            self.assertAlmostEqual(u[0] * v[0] + u[1] * v[1], 1.0, places=9)
        tan = B.curve_bridge((20, 0), (1, 0), (30, 20), (-1, 0))
        self.assertLess(_curv0(segs[0]), _curv0(tan.segments[0]) / 3)           # presque sans courbure au départ

    def test_bridge(self):
        c, j = B.bridge(self.a, self.b)
        self.assertEqual((c.start, c.end), ((20, 0), (30, 20)))                  # bouts les plus proches
        self.assertFalse(j.closed)
        self.assertEqual(len(j.segments), 3)
        self.assertEqual((j.start, j.end), ((0, 0), (50, 20)))
        u = Contour([Line((0, 10), (0, 0)), Line((0, 0), (20, 0)), Line((20, 0), (20, 10))], False)
        c, j = B.bridge(u)                                                       # un seul trait : fermé
        self.assertTrue(j.closed)
        self.assertEqual((c.start, c.end), ((20, 10), (0, 10)))
        self.assertGreater(c.segments[0].p1[1], 10)                              # monte dans le prolongement
        self.assertIsNone(B.bridge(Contour([Line((0, 0), (1, 0)), Line((1, 0), (0, 0))], True)))
        self.assertIsNone(B.bridge(self.a, Contour([Line((20, 0), (30, 5))], False)))   # bouts qui se touchent
        self.assertIsNone(B.bridge(self.a))                                      # trait droit seul


class TestDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from vectordrive.ui.main_window import MainWindow
        cls.w = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.w.modified = False
        cls.w.close()

    def shapes(self):
        from vectordrive.core.document import Shape
        c = self.w.canvas
        s1 = Shape(path=Path([Contour([Line((0, 0), (20, 0))], False)]), tool=1)
        s2 = Shape(path=Path([Contour([Line((50, 20), (30, 20))], False)]), tool=2)
        c.doc.add(s1)
        c.doc.add(s2)
        return s1, s2

    def test_join_and_apart(self):
        w, c = self.w, self.w.canvas
        s1, s2 = self.shapes()
        n = len(c.doc.active_layer.items)
        c.select([s1, s2])
        out = w.blend_curve_dialog({'smooth': False, 'join': True})
        self.assertEqual(len(out), 1)
        self.assertEqual(len(c.doc.active_layer.items), n - 1)                   # un seul tracé
        self.assertEqual(len(out[0].path.contours[0].segments), 3)
        self.assertEqual(out[0].tool, 1)
        w.undo()
        self.assertEqual(len(c.doc.active_layer.items), n)
        s1, s2 = self.shapes()                                                   # l'annulation rend des copies
        n = len(c.doc.active_layer.items)
        c.select([s1, s2])
        out = w.blend_curve_dialog({'smooth': True, 'join': False})
        self.assertEqual(len(c.doc.active_layer.items), n + 1)                   # la courbe à part
        self.assertTrue(any(it is s1 for it in c.doc.active_layer.items))
        self.assertGreater(len(out[0].path.contours[0].segments), 1)
        from vectordrive.core.document import Shape
        u = Shape(path=Path([Contour([Line((0, 10), (0, 0)), Line((0, 0), (20, 0)), Line((20, 0), (20, 10))], False)]))
        c.doc.add(u)
        c.select([u])
        out = w.blend_curve_dialog({'smooth': False, 'join': True})
        self.assertTrue(out[0].path.contours[0].closed)                          # un trait seul : refermé
        with mock.patch('vectordrive.ui.main_window.QMessageBox.information') as mb:
            c.select([])
            self.assertEqual(w.blend_curve_dialog({'smooth': False, 'join': True}), [])
            self.assertTrue(mb.called)

    def test_ribbon_icon(self):
        from vectordrive.ui import icons
        self.assertIn('blend_curve', icons.ICONS)
        a = self.w.A['blend_curve']
        self.assertFalse(a.icon().isNull())
        self.assertTrue(a.toolTip())


if __name__ == '__main__':
    unittest.main()
