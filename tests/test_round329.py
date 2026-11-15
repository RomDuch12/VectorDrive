"""Round 329 : raccord entre deux traits (comme RACCORD en DAO) — prolongés
ou coupés jusqu'au coin, arc tangent, coin vif au rayon 0, refus."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('VECTORDRIVE_SETTINGS', os.path.join(tempfile.mkdtemp(), 'vd_test.ini'))

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from vectordrive.core import fillet2 as F2, geom
from vectordrive.core.document import Shape

app = QApplication.instance() or QApplication([])


def lines():
    # horizontal qui s'arrête avant le coin, vertical qui le dépasse
    return geom.polyline([(0, 0), (8, 0)]), geom.polyline([(10, -3), (10, 20)])


class TestFillet2(unittest.TestCase):
    def test_sharp(self):
        a, b = lines()
        na, nb, arc = F2.fillet(a, (2, 0), b, (10, 15), 0.0)
        self.assertIsNone(arc)
        self.assertEqual(na.segments[-1].end, (10.0, 0.0))                  # prolongé jusqu'au coin
        self.assertEqual(nb.segments[0].start, (10.0, 0.0))                 # coupé au coin (le bas retiré)
        self.assertEqual(nb.segments[-1].end, (10, 20))

    def test_arc(self):
        a, b = lines()
        na, nb, arc = F2.fillet(a, (2, 0), b, (10, 15), 3.0)
        self.assertEqual(tuple(round(v, 9) for v in na.end), (7.0, 0.0))
        self.assertEqual(tuple(round(v, 9) for v in nb.start), (10.0, 3.0))
        for s in arc.segments:                                             # sur le cercle de centre (7, 3)
            for t in (0.0, 0.5, 1.0):
                p = s.point(t)
                self.assertAlmostEqual(math.dist(p, (7, 3)), 3.0, 6)
        self.assertIsNone(F2.fillet(a, (2, 0), b, (10, 15), 50.0))           # rayon trop grand
        self.assertIsNone(F2.fillet(a, (2, 0), geom.polyline([(0, 5), (8, 5)]), (2, 5), 1.0))   # parallèles

    def test_tool(self):
        from vectordrive.ui.main_window import MainWindow
        w = MainWindow()
        try:
            c = w.canvas
            a, b = (Shape(path=geom.Path([x])) for x in lines())
            c.doc.add(a)
            c.doc.add(b)
            c.fillet_radius = 2.0
            w.set_tool('fillet2')
            t = c.tool_obj
            e = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(0, 0), QPointF(0, 0), Qt.MouseButton.LeftButton,
                            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            t.press(c.to_screen(2, 0), (2.0, 0.0), e)
            t.press(c.to_screen(10, 15), (10.0, 15.0), e)
            items = c.doc.layers[0].items
            self.assertEqual(len(items[0].path.contours), 2)                   # trait + arc
            self.assertAlmostEqual(items[1].path.contours[0].start[1], 2.0, 6)
            w.undo()
            self.assertEqual(len(c.doc.layers[0].items[0].path.contours), 1)
        finally:
            w.set_tool('select')
            w.modified = False
            w.close()


if __name__ == '__main__':
    unittest.main()
