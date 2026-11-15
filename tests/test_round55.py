"""Round 55 : spirale."""
import math
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from vectordrive.core import geom


def radial_error(c, center, r_in, r_out, turns, start, ccw):
    span = 2 * math.pi * turns
    b = (r_out - r_in) / span
    s = 1 if ccw else -1
    err = 0.0
    for seg in c.segments:
        for k in range(1, 10):
            x, y = seg.point(k / 10)
            x, y = x - center[0], y - center[1]
            r, phi = math.hypot(x, y), math.atan2(y, x)
            th0 = span - (math.radians(start) - phi) * s
            err = max(err, min(abs(r - (r_in + b * (th0 + 2 * math.pi * n)))
                               for n in range(-int(turns) - 2, int(turns) + 3)))
    return err


class TestSpiral(unittest.TestCase):
    def test_ends_and_accuracy(self):
        for turns, r_in, ccw in ((5, 0, True), (0.5, 10, False), (12.5, 2, True)):
            c = geom.spiral((3, 4), 30, turns, start_deg=90, r_in=r_in, ccw=ccw)
            self.assertFalse(c.closed)
            self.assertAlmostEqual(geom.dist(c.end, (3, 34)), 0, places=9)
            r0 = geom.dist(c.start, (3, 4))
            self.assertAlmostEqual(r0, r_in, places=9)
            self.assertLess(radial_error(c, (3, 4), r_in, 30, turns, 90, ccw), 2e-4)
            # raccords en tangence
            for a, b in zip(c.segments, c.segments[1:]):
                t1 = (a.p3[0] - a.p2[0], a.p3[1] - a.p2[1])
                t2 = (b.p1[0] - b.p0[0], b.p1[1] - b.p0[1])
                self.assertLess(abs(t1[0] * t2[1] - t1[1] * t2[0]) / (math.hypot(*t1) * math.hypot(*t2)), 1e-9)

    def test_direction(self):
        # sens trigonométrique : juste avant la fin, la courbe arrive par le bas (y < 0) quand on finit à droite
        ccw = geom.spiral((0, 0), 10, 2, start_deg=0, ccw=True)
        cw = geom.spiral((0, 0), 10, 2, start_deg=0, ccw=False)
        self.assertLess(ccw.segments[-1].point(0.5)[1], 0)
        self.assertGreater(cw.segments[-1].point(0.5)[1], 0)


class _Ev:
    def __init__(self, mods):
        self._m = mods

    def modifiers(self):
        return self._m


class TestTool(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_mouse_creation(self):
        from PySide6.QtCore import Qt
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            w.turns.setValue(4)
            w.set_tool('spiral')
            t = w.canvas.tool_obj
            ev = _Ev(Qt.KeyboardModifier.NoModifier)
            t.press(None, (10, 10), ev)
            t.move(None, (30, 10), ev)
            t.release(None, (30, 10), ev)
            items = list(w.canvas.doc.iter_items())
            self.assertEqual(len(items), 1)
            c = items[0].path.contours[0]
            self.assertAlmostEqual(geom.dist(c.end, (30, 10)), 0, places=9)
            self.assertAlmostEqual(geom.dist(c.start, (10, 10)), 0, places=9)
            self.assertEqual(w.canvas.spiral_turns, 4)
            w.undo()
            self.assertEqual(list(w.canvas.doc.iter_items()), [])
        finally:
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
