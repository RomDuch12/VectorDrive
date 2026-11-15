"""Round 341 : crayon et reconnaissance de formes (comme Shaper) — trait,
rectangle (droit ou à 45°), cercle, ellipse, triangle, sinon courbe."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

import numpy as np
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core import shaper as SH

app = QApplication.instance() or QApplication([])
rng = np.random.default_rng(5)


def wobble(pts, a=0.2):
    return [(x + rng.normal(0, a), y + rng.normal(0, a)) for x, y in pts]


def along(poly, n=20):
    out = []
    for p, q in zip(poly, poly[1:]):
        out += [(p[0] + (q[0] - p[0]) * k / n, p[1] + (q[1] - p[1]) * k / n) for k in range(n)]
    return out + [poly[-1]]


class TestRecognize(unittest.TestCase):
    def test_shapes(self):
        k, p = SH.recognize(wobble(along([(0, 0), (40, 1)]), 0.1))
        self.assertEqual(k, 'trait')
        k, p = SH.recognize(wobble(along([(0, 0), (40, 0), (40, 20), (0, 20), (0, 0.5)])))
        self.assertEqual(k, 'rectangle')
        b = p.bbox()
        self.assertAlmostEqual(b[2] - b[0], 40, 0)
        circ = [(20 * math.cos(t), 20 * math.sin(t)) for t in np.linspace(0, 2 * math.pi * 0.98, 80)]
        k, p = SH.recognize(wobble(circ))
        self.assertEqual(k, 'ellipse')
        self.assertAlmostEqual(p.bbox()[2] - p.bbox()[0], 40, 0)
        ell = [(30 * math.cos(t), 12 * math.sin(t)) for t in np.linspace(0, 2 * math.pi * 0.98, 80)]
        k, p = SH.recognize(wobble(ell))
        self.assertEqual(k, 'ellipse')
        self.assertAlmostEqual(p.bbox()[3] - p.bbox()[1], 24, 0)
        k, p = SH.recognize(wobble(along([(0, 0), (40, 0), (20, 30), (0.5, 0.5)])))
        self.assertEqual(k, 'triangle')
        s = [(x, 10 * math.sin(x / 5)) for x in np.linspace(0, 60, 80)]
        self.assertEqual(SH.recognize(s)[0], 'courbe')

    def test_tool(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            w.set_tool('shaper')
            t = c.tool_obj
            pts = along([(0, 0), (40, 0), (40, 20), (0, 20), (0, 0.3)], 10)

            def e(kind, buttons):
                return QMouseEvent(kind, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton, buttons,
                                   Qt.KeyboardModifier.NoModifier)
            t.press(c.to_screen(*pts[0]), pts[0], e(QEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton))
            for q in pts[1:]:
                t.move(c.to_screen(*q), q, e(QEvent.Type.MouseMove, Qt.MouseButton.LeftButton))
            t.release(c.to_screen(*pts[-1]), pts[-1], e(QEvent.Type.MouseButtonRelease, Qt.MouseButton.NoButton))
            items = c.doc.layers[0].items
            self.assertEqual(len(items), 1)
            self.assertEqual(len(items[0].path.contours[0].segments), 4)
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
