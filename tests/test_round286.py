"""Round 286 : gribouillis — zigzag continu dans les formes fermées (un
seul trait si la forme le permet), angle, écart, débord, variation."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import geom, scribble as SB
from vectordrive.core.document import Group, Shape

app = QApplication.instance() or QApplication([])


class TestScribble(unittest.TestCase):
    def test_single_stroke(self):
        r = SB.scribble(geom.Path([geom.circle((0, 0), 15)]), SB.ScribbleSpec(angle=30, spacing=1.5))
        self.assertEqual(len(r.contours), 1)                                       # un seul trait
        self.assertFalse(r.contours[0].closed)
        pts = [r.contours[0].segments[0].start] + [s.end for s in r.contours[0].segments]
        self.assertTrue(all(math.hypot(*p) <= 15 + 1e-6 for p in pts))
        self.assertGreater(len(pts), 30)

    def test_options(self):
        sq = geom.Path([geom.rect(0, 0, 10, 10)])
        over = SB.scribble(sq, SB.ScribbleSpec(angle=0, spacing=1, overshoot=0.5))
        xs = [p[0] for c in over.contours for p in [c.segments[0].start] + [s.end for s in c.segments]]
        self.assertAlmostEqual(min(xs), -0.5)
        a = SB.scribble(sq, SB.ScribbleSpec(variation=0.3, seed=2))
        self.assertEqual(a, SB.scribble(sq, SB.ScribbleSpec(variation=0.3, seed=2)))
        holed = SB.scribble(geom.Path([geom.rect(-15, -15, 30, 30), geom.circle((0, 0), 6)]), SB.ScribbleSpec())
        for c in holed.contours:                                                   # rien dans le trou
            for s in c.segments:
                m = ((s.start[0] + s.end[0]) / 2, (s.start[1] + s.end[1]) / 2)
                self.assertGreater(math.hypot(*m), 5.9)

    def test_command(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            s = Shape(path=geom.Path([geom.circle((0, 0), 10)]), tool=2)
            c.doc.add(s)
            c.select([s])
            g = w.scribble({'spacing': 1.0})
            self.assertIsInstance(g, Group)
            self.assertEqual(g.children[0].tool, 2)
            self.assertIn(s, c.doc.layers[0].items)                                # la forme reste
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
