"""Round 201 : création de texture (motif répété par symétrie, coupé aux contours)."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication
from shapely.geometry import Point, Polygon, box

from vectordrive.core import geom, patterns as PT
from vectordrive.core.document import Shape


def pts(path):
    return [p for c in path.contours for s in c.segments for p in (s.p0, s.p1)]


class TestTile(unittest.TestCase):
    def test_clipped_and_holes(self):
        region = Polygon([(0, 0), (30, 0), (30, 20), (0, 20)], [[(10, 5), (20, 5), (20, 15), (10, 15)]])
        motif, cell, sym = PT.preset_motif('chevrons', 3.0)
        p = PT.tile(region, motif, cell, sym)
        self.assertGreater(len(p.contours), 50)
        grown = region.buffer(1e-6)
        from shapely.geometry import Point as P
        self.assertTrue(all(grown.contains(P(x, y)) for x, y in pts(p)))          # dans la région, pas dans le trou
        self.assertTrue(all(not c.closed for c in p.contours))

    def test_symmetries(self):
        motif = [[(0.0, 0.0), (1.0, 0.5)]]
        self.assertEqual(PT._variant(motif[0], 1, 0, 1, 1, 'miroir_h'), [(1.0, 0.0), (0.0, 0.5)])
        self.assertEqual(PT._variant(motif[0], 0, 1, 1, 1, 'miroir_v'), [(0.0, 1.0), (1.0, 0.5)])
        self.assertEqual(PT._variant(motif[0], 1, 0, 1, 1, 'demi_tour'), [(1.0, 1.0), (0.0, 0.5)])
        self.assertEqual(PT._variant(motif[0], 0, 0, 1, 1, 'demi_tour'), motif[0])
        bricks, cell, sym = PT.preset_motif('briques', 4.0)
        self.assertEqual((cell, sym), ((4.0, 2.0), 'quinconce'))
        p = PT.tile(box(0, 0, 20, 10), bricks, cell, 'quinconce')
        xs_row0 = sorted({round(c.segments[0].p0[0], 6) for c in p.contours if c.segments[0].p0[0] == c.segments[-1].p1[0]
                          and c.segments[0].p0[1] < 1.9})
        self.assertTrue(xs_row0)

    def test_angle_and_guard(self):
        motif, cell, _s = PT.preset_motif('croisillons', 2.0)
        a = PT.tile(Point(0, 0).buffer(10, 32), motif, cell, 'translation', angle=30.0)
        self.assertGreater(len(a.contours), 20)
        with self.assertRaises(ValueError):
            PT.tile(box(0, 0, 500, 500), motif, (0.05, 0.05), 'translation')


class TestUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_action_with_own_strokes(self):
        from vectordrive.ui.main_window import MainWindow
        from vectordrive.ui.shortcuts import TE_ACTIONS
        self.assertEqual(TE_ACTIONS['ID_COMPO_TEXTURING'], 'texture_create')
        w = MainWindow()
        try:
            zone = Shape(path=geom.Path([geom.rect(0, 0, 20, 10)]))
            stroke = Shape(path=geom.Path([geom.Contour([geom.Line((40, 0), (42, 1)), geom.Line((42, 1), (44, 0))],
                                                        False)]))
            for it in (zone, stroke):
                w.canvas.doc.add(it)
            w.canvas.selection = [zone, stroke]
            new = w.texture_create('selection', symmetry='miroir_v')
            self.assertEqual(len(new), 1)
            b = new[0].path.bbox()
            self.assertGreaterEqual(b[0], -1e-6)
            self.assertLessEqual(b[2], 20 + 1e-6)
            w.canvas.selection = [zone]
            self.assertEqual(len(w.texture_create('vagues', 2.0)), 1)
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
