"""Round 264 : déformations — zigzag (pointes, vagues), rugosité (graine
fixe), contracter / dilater, torsion."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtWidgets import QApplication

from vectordrive.core import distort as D, geom
from vectordrive.core.document import Shape, Text

app = QApplication.instance() or QApplication([])
CIRCLE = geom.Path([geom.circle((0, 0), 15)])


def radii(path):
    return [math.hypot(*p) for c in path.contours for p in c.flatten(0.05)]


class TestDistort(unittest.TestCase):
    def test_zigzag(self):
        z = D.zigzag(CIRCLE, 1.5, 4)
        r = radii(z)
        self.assertAlmostEqual(max(r), 16.5, 1)
        self.assertAlmostEqual(min(r), 13.5, 1)
        self.assertTrue(z.contours[0].closed)
        self.assertEqual(len(z.contours[0].segments) % 2, 0)                     # la vague se referme
        line = geom.Path([geom.polyline([(0, 0), (20, 0)])])
        zl = D.zigzag(line, 1, 4)
        self.assertEqual(zl.contours[0].segments[0].start, (0, 0))                # bouts en place
        self.assertEqual(zl.contours[0].segments[-1].end, (20, 0))
        smooth = D.zigzag(CIRCLE, 1.5, 4, smooth=True)
        self.assertTrue(all(type(s).__name__ == 'Conic' for s in smooth.contours[0].segments))

    def test_roughen_pucker_twist(self):
        a, b = D.roughen(CIRCLE, 1, 1, seed=3), D.roughen(CIRCLE, 1, 1, seed=3)
        self.assertEqual(a, b)                                                     # même graine : même tracé
        self.assertNotEqual(a, D.roughen(CIRCLE, 1, 1, seed=4))
        self.assertTrue(all(13.9 <= r <= 16.1 for r in radii(a)))
        hexa = geom.Path([geom.polygon((0, 0), 15, 6, 90.0)])
        bloat = D.pucker_bloat(hexa, 0.4)
        self.assertAlmostEqual(math.hypot(*bloat.contours[0].segments[0].start), 15 * 0.6, 6)   # nœud vers le centre
        sq = geom.Path([geom.rect(-10, -10, 20, 20)])
        tw = D.twist(sq, 90)
        self.assertAlmostEqual(max(radii(tw)), math.hypot(10, 10), 3)              # les coins ne tournent pas

    def test_command(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            s = Shape(path=CIRCLE)
            c.doc.add(s)
            c.select([s])
            new = w.distort('zigzag', {'amplitude': 1.0, 'wavelength': 3.0})
            self.assertEqual(len(new), 1)
            self.assertNotIn(s, c.doc.layers[0].items)
            self.assertIn(new[0], c.doc.layers[0].items)
            w.undo()
            self.assertEqual(len(c.doc.layers[0].items), 1)
            c.select([])
            self.assertEqual(w.distort('twist', {}), [])
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
